package com.example.kb_ai_backend;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Map;

import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("presentation")
class PresentationApplicationTests {
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;

    @ParameterizedTest
    @CsvSource(delimiter = '|', textBlock = """
            지갑을 잃어버렸어. 카드 정지하고 현금 찾는 방법이랑 신분증 재발급도 알려줘. | card_freeze_all | atm_smart_withdrawal | id_reissue_status_widget
            상하이로 3박 4일 여행 가는데 환전, QR 결제, 여행자보험 준비해줘. | travel_card_charge_widget | overseas_qr_payment_widget | travel_insurance_widget
            테니스 동아리 총무야. 이번 달 회비 수납 현황이랑 지출 리포트, 카드 안전 설정 보여줘. | group_account_status | expense_report_widget | group_card_safety_widget
            """)
    void originalExamplesRenderTheirThreeWidgets(String message, String first, String second, String third) throws Exception {
        var result = mvc.perform(post("/api/canvas").contentType("application/json")
                        .content(json.writeValueAsString(Map.of("message", message))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.demo").value(true))
                .andExpect(jsonPath("$.status").value("ready"))
                .andExpect(jsonPath("$.widgets[*].type", containsInAnyOrder(first, second, third)));

        if (first.equals("travel_card_charge_widget")) {
            result.andExpect(jsonPath("$.widgets[?(@.type == 'travel_card_charge_widget')].currency",
                            containsInAnyOrder("CNY")))
                    .andExpect(jsonPath("$.widgets[?(@.type == 'travel_card_charge_widget')].supported",
                            containsInAnyOrder(true)));
        }
    }

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
