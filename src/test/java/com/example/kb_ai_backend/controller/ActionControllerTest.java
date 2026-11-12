package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.action.*;
import com.example.kb_ai_backend.action.rules.RiskLevelRule;
import com.example.kb_ai_backend.audit.HashChainAuditLog;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ActionControllerTest {
    MockMvc mvc;
    DemoOtpSender otp;
    ObjectMapper json = new ObjectMapper();

    @BeforeEach void setup() {
        Clock clock = Clock.systemUTC();
        otp = new DemoOtpSender();
        var audit = new HashChainAuditLog(clock);
        var service = new ActionService(new PolicyEngine(List.of(new RiskLevelRule())), new MockActionExecutor(clock),
                otp, audit, clock, Duration.ofMinutes(5), Duration.ofMinutes(10), 3);
        mvc = MockMvcBuilders.standaloneSetup(new ActionController(service, audit, otp, true)).build();
    }

    String prepare(String type) throws Exception {
        var response = mvc.perform(post("/api/actions").contentType("application/json")
                        .content("{\"type\":\"" + type + "\",\"params\":{}}"))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        return (String) json.readValue(response, Map.class).get("actionId");
    }

    @Test void protectiveActionPreparesAndExecutes() throws Exception {
        String id = prepare("CARD_FREEZE_ALL");
        mvc.perform(post("/api/actions/" + id + "/confirm"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("EXECUTED"))
                .andExpect(jsonPath("$.result.frozenCards").isArray());
    }

    @Test void highRiskActionReturnsDemoOtpAndRejectsWrongCode() throws Exception {
        mvc.perform(post("/api/actions").contentType("application/json")
                        .content("{\"type\":\"SMART_WITHDRAWAL_CODE\",\"params\":{}}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.decision").value("STEP_UP"))
                .andExpect(jsonPath("$.otpRequired").value(true))
                .andExpect(jsonPath("$.demoOtp").isString());

        String id = prepare("SMART_WITHDRAWAL_CODE");
        mvc.perform(post("/api/actions/" + id + "/confirm").contentType("application/json").content("{\"otp\":\"abc\"}"))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.error").value("OTP_MISMATCH"))
                .andExpect(jsonPath("$.remainingOtpAttempts").value(2));

        String code = otp.lastCodeFor(id).orElseThrow();
        mvc.perform(post("/api/actions/" + id + "/confirm").contentType("application/json").content("{\"otp\":\"" + code + "\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.status").value("EXECUTED"));
    }

    @Test void unknownActionTypeIsRejected() throws Exception {
        mvc.perform(post("/api/actions").contentType("application/json").content("{\"type\":\"TRANSFER_ALL_MONEY\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("INVALID_REQUEST"));
    }

    @Test void otherUserGetsNotFound() throws Exception {
        String id = prepare("CARD_FREEZE_ALL");
        mvc.perform(post("/api/actions/" + id + "/confirm").header("X-User-Id", "someone-else"))
                .andExpect(status().isNotFound());
    }

    @Test void auditChainCanBeVerifiedOverApi() throws Exception {
        String id = prepare("CARD_FREEZE_ALL");
        mvc.perform(post("/api/actions/" + id + "/confirm")).andExpect(status().isOk());
        mvc.perform(get("/api/audit/verify"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.valid").value(true))
                .andExpect(jsonPath("$.size").value(2));
        mvc.perform(get("/api/audit").param("subject", id))
                .andExpect(jsonPath("$[0].event").value("ACTION_PREPARED"))
                .andExpect(jsonPath("$[1].event").value("ACTION_EXECUTED"));
    }
}
