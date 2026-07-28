package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

/**
 * 최종 확정된 3개 캔버스 기준 위젯 카탈로그입니다.
 *
 * ① 해외여행 캔버스: travel_card_charge_widget, overseas_qr_payment_widget, travel_insurance_widget
 * ② 동아리/운영진 캔버스: group_account_status, expense_report_widget, group_card_safety_widget
 * ③ 지갑/스마트폰 분실 응급 캔버스: card_freeze_all, atm_smart_withdrawal, id_reissue_status_widget
 *
 */
@Service
public class OpenAiApiService {

    private static final String OPENAI_URL = "https://api.openai.com/v1/chat/completions";
    private static final String MODEL = "gpt-4o-mini";

    @Value("${openai.api.key}")
    private String apiKey;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    @SuppressWarnings("unchecked")
    public List<String> selectWidgets(String userMessage) {

        Map<String, Object> widgetsSchema = Map.of(
                "type", "array",
                "description", "화면에 그려야 할 위젯 id 목록. 관련 있는 것만 최대 3개까지.",
                "items", Map.of(
                        "type", "string",
                        "enum", List.of(
                                // ① 해외여행 캔버스
                                "travel_card_charge_widget",   // 트래블카드 CNY 충전
                                "overseas_qr_payment_widget",  // 현지 QR 결제(Alipay+) 연동
                                "travel_insurance_widget",     // 여행자보험 가입

                                // ② 동아리/운영진 캔버스
                                "group_account_status",        // KB 모임통장 회비 수납 현황
                                "expense_report_widget",       // 이번 달 지출 리포트
                                "group_card_safety_widget",    // 모임 전용 체크카드 안심 관리

                                // ③ 지갑/스마트폰 분실 응급 캔버스
                                "card_freeze_all",             // 전 카드 일괄 정지
                                "atm_smart_withdrawal",         // 카드 없는 ATM 스마트출금
                                "id_reissue_status_widget"      // 신분증 분실 신고 및 재발급 완료 안내
                        )
                )
        );

        Map<String, Object> function = Map.of(
                "name", "select_widgets",
                "description", "사용자의 요청을 분석해서 화면에 띄워야 할 금융 위젯들을 고른다.",
                "parameters", Map.of(
                        "type", "object",
                        "properties", Map.of("widgets", widgetsSchema),
                        "required", List.of("widgets")
                )
        );

        Map<String, Object> tool = Map.of(
                "type", "function",
                "function", function
        );

        Map<String, Object> requestBody = Map.of(
                "model", MODEL,
                "messages", List.of(
                        Map.of("role", "system", "content",
                                "너는 은행 앱의 화면 구성 담당자야. 사용자의 요청을 읽고 "
                                        + "select_widgets 함수를 반드시 호출해서, 그 요청을 처리하는 데 "
                                        + "실제로 필요한 위젯만 정확히 골라줘. 애매하면 가장 관련 있는 것 1개만 골라. "
                                        + "예를 들어 해외여행/환전/공항 얘기면 해외여행 관련 위젯들을, "
                                        + "모임/회비/총무 얘기면 동아리 관련 위젯들을, "
                                        + "지갑/카드분실 얘기면 응급 관련 위젯 3개(card_freeze_all, "
                                        + "atm_smart_withdrawal, id_reissue_status_widget)를 함께 골라야 해."),
                        Map.of("role", "user", "content", userMessage)
                ),
                "tools", List.of(tool),
                "tool_choice", Map.of("type", "function", "function", Map.of("name", "select_widgets"))
        );

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + apiKey);
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

        Map<String, Object> response = restTemplate.postForObject(OPENAI_URL, request, Map.class);

        try {
            List<Map<String, Object>> choices = (List<Map<String, Object>>) response.get("choices");
            Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
            List<Map<String, Object>> toolCalls = (List<Map<String, Object>>) message.get("tool_calls");

            Map<String, Object> firstCall = toolCalls.get(0);
            Map<String, Object> functionCall = (Map<String, Object>) firstCall.get("function");

            String argumentsJson = (String) functionCall.get("arguments");
            Map<String, Object> arguments = objectMapper.readValue(argumentsJson, Map.class);

            Object widgets = arguments.get("widgets");
            if (widgets instanceof List) {
                return (List<String>) widgets;
            }
        } catch (Exception e) {
            e.printStackTrace();
        }

        return List.of();
    }
}