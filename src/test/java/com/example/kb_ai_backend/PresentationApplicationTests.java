package com.example.kb_ai_backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("presentation")
class PresentationApplicationTests {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;

    @Test void runsClarificationAndResumeUsingOnlyPresentationData() throws Exception {
        var first = mvc.perform(post("/api/canvas").contentType("application/json")
                        .content(json.writeValueAsString(Map.of("message", "여행 환전이랑 보험 알려줘"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.demo").value(true))
                .andExpect(jsonPath("$.resumedFromSession").value(false))
                .andExpect(jsonPath("$.widgets[0].type").value("travel_insurance_widget"))
                .andExpect(jsonPath("$.widgets[1].type").value("clarification_widget"))
                .andReturn();
        JsonNode partial = json.readTree(first.getResponse().getContentAsByteArray());

        var resumed = mvc.perform(post("/api/canvas").contentType("application/json")
                        .content(json.writeValueAsString(Map.of("message", "엔화로 3만엔",
                                "sessionId", partial.get("sessionId").asText()))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.resumedFromSession").value(true))
                .andExpect(jsonPath("$.widgets[0].currency").value("JPY"))
                .andExpect(jsonPath("$.widgets[0].estimatedKrw").value(270000))
                .andReturn();
        JsonNode complete = json.readTree(resumed.getResponse().getContentAsByteArray());
        mvc.perform(get("/api/canvas/{id}/trace", complete.get("requestId").asText()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.selection").doesNotExist());
        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content(json.writeValueAsString(Map.of("requestId", partial.get("requestId").asText(),
                                "widgetType", "travel_insurance_widget", "event", "dismissed"))))
                .andExpect(status().isAccepted());
    }
}
