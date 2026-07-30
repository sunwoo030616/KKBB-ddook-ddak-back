package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.Map;

/**
 * 최종 확정된 3개 캔버스 기준 위젯 카탈로그입니다.
 * GPT가 도시/국가명을 보고 통화(ISO 4217)까지 추론하고,
 * 실제 환율 숫자는 서버(ExchangeRateService)가 실시간으로 계산합니다.
 * 동아리 요청이면 동아리 이름(clubName)도 함께 추출합니다.
 *
 * ① 해외여행 캔버스: travel_card_charge_widget, overseas_qr_payment_widget, travel_insurance_widget
 * ② 동아리/운영진 캔버스: group_account_status, expense_report_widget, group_card_safety_widget
 * ③ 지갑/스마트폰 분실 응급 캔버스: card_freeze_all, atm_smart_withdrawal, id_reissue_status_widget
 */
@Service
public class OpenAiApiService {

    private static final String OPENAI_URL = "https://api.openai.com/v1/chat/completions";
    private static final String MODEL = "gpt-4o-mini";

    @Value("${openai.api.key}")
    private String apiKey;

    private final RestTemplate restTemplate = new RestTemplate();
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * widgets: 선택된 위젯 id 목록
     * currency: 메시지의 여행지/통화 언급을 바탕으로 GPT가 추론한 ISO 4217 3자리 코드 (없으면 null)
     * destination: 메시지에 언급된 여행지(도시/국가명, 원문 그대로). 없으면 null
     * requestedAmount: 명시적으로 언급된 금액. 없으면 null
     * clubName: 메시지에 언급된 동아리/모임 이름 (예: "테니스 동아리", "마술 동아리"). 없으면 null
     */
    public record WidgetSelection(List<String> widgets, String currency, String destination,
                                  Integer requestedAmount, String clubName) {}

    private static final WidgetSelection EMPTY_SELECTION =
            new WidgetSelection(List.of(), null, null, null, null);

    @SuppressWarnings("unchecked")
    public WidgetSelection selectWidgets(String userMessage) {

        // 방어 코드: 빈 메시지면 OpenAI 호출 자체를 하지 않음
        if (userMessage == null || userMessage.isBlank()) {
            return EMPTY_SELECTION;
        }

        Map<String, Object> widgetsSchema = Map.of(
                "type", "array",
                "description", "화면에 그려야 할 위젯 id 목록. 관련 있는 것만 최대 3개까지.",
                "items", Map.of(
                        "type", "string",
                        "enum", List.of(
                                // ① 해외여행 캔버스
                                "travel_card_charge_widget",
                                "overseas_qr_payment_widget",
                                "travel_insurance_widget",

                                // ② 동아리/운영진 캔버스
                                "group_account_status",
                                "expense_report_widget",
                                "group_card_safety_widget",

                                // ③ 지갑/스마트폰 분실 응급 캔버스
                                "card_freeze_all",
                                "atm_smart_withdrawal",
                                "id_reissue_status_widget"
                        )
                )
        );

        // enum 제한 없음: GPT가 도시/국가명만으로도 통화 코드를 추론하고,
        // 최종적으로는 ExchangeRateService(실시간 API)가 유효성을 검증하므로 안전함
        Map<String, Object> currencySchema = Map.of(
                "type", List.of("string", "null"),
                "description", "사용자의 메시지에서 여행지나 통화가 언급됐으면, 그 지역에서 실제로 통용되는 "
                        + "통화의 ISO 4217 3자리 코드로 추론해서 채움 (예: '몽골'→MNT, '런던'→GBP, "
                        + "'달러'→USD). 아무 단서도 없으면 null."
        );

        Map<String, Object> destinationSchema = Map.of(
                "type", List.of("string", "null"),
                "description", "사용자가 언급한 여행지(도시 또는 국가명)를 원문 그대로 추출. "
                        + "예: '런던', '상하이', '뉴욕', '몽골'. 언급 없으면 null."
        );

        Map<String, Object> amountSchema = Map.of(
                "type", List.of("integer", "null"),
                "description", "사용자가 명시적으로 언급한 충전/환전 희망 금액(외화 기준 숫자). 언급 없으면 null."
        );

        Map<String, Object> clubNameSchema = Map.of(
                "type", List.of("string", "null"),
                "description", "사용자가 언급한 동아리/모임 이름이나 종류를 원문 그대로 추출 "
                        + "(예: '테니스 동아리', '마술 동아리', '개발 동아리', '농구 모임'). "
                        + "동아리/모임 관련 요청이 아니거나 언급이 없으면 null."
        );

        Map<String, Object> function = Map.of(
                "name", "select_widgets",
                "description", "사용자의 요청을 분석해서 화면에 띄워야 할 금융 위젯들을 고르고, "
                        + "여행지, 통화, 금액, 동아리명도 함께 추출한다.",
                "parameters", Map.of(
                        "type", "object",
                        "properties", Map.of(
                                "widgets", widgetsSchema,
                                "currency", currencySchema,
                                "destination", destinationSchema,
                                "requestedAmount", amountSchema,
                                "clubName", clubNameSchema
                        ),
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
                                        + "실제로 필요한 위젯만 정확히 골라줘. "
                                        + "해외여행 준비, 환전, 출국 관련 요청이면 무조건 travel_card_charge_widget, "
                                        + "overseas_qr_payment_widget, travel_insurance_widget 3개를 전부 함께 골라야 해. "
                                        + "특정 기능 하나만 콕 집어 말한 경우(예: '환전만 알려줘', 'QR결제만 필요해')에만 "
                                        + "그 1개만 골라. "
                                        + "모임/회비/총무 얘기면 동아리 관련 위젯들을 골라야 하고, 이때 어떤 동아리인지 "
                                        + "(예: '테니스 동아리', '마술 동아리') 언급이 있으면 clubName에 원문 그대로 채워줘. "
                                        + "없으면 null로 둬. "
                                        + "지갑/카드분실 얘기면 응급 관련 위젯 3개(card_freeze_all, "
                                        + "atm_smart_withdrawal, id_reissue_status_widget)를 함께 골라야 해. "
                                        + "단, 여행지가 국내(서울, 제주도, 부산 등 한국 지역)라면 "
                                        + "travel_card_charge_widget, overseas_qr_payment_widget, "
                                        + "travel_insurance_widget은 해외여행 전용이므로 절대 고르지 마. "
                                        + "추가로, 메시지에 나온 여행지(도시/국가명)를 destination에 채워줘. "
                                        + "그리고 사용자가 통화를 직접 언급하지 않았어도, destination이 어느 나라인지로 "
                                        + "그 지역에서 실제로 통용되는 통화의 ISO 4217 3자리 코드를 "
                                        + "네가 알고 있는 지식으로 추론해서 currency에 채워줘 "
                                        + "(예: '몽골' → MNT, '부탄' → BTN, '런던' → GBP, '방콕' → THB). "
                                        + "금액이 언급됐으면 requestedAmount에도 채워줘. "
                                        + "단, 이건 '어떤 통화를 쓰는지' 판단만 하는 거야. "
                                        + "그 통화의 실제 환율 숫자는 절대로 네가 임의로 추측해서 만들지 마 — "
                                        + "그건 서버가 실시간 데이터로 계산할 거야."),
                        Map.of("role", "user", "content", userMessage)
                ),
                "tools", List.of(tool),
                "tool_choice", Map.of("type", "function", "function", Map.of("name", "select_widgets"))
        );

        HttpHeaders headers = new HttpHeaders();
        headers.set("Authorization", "Bearer " + apiKey);
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(requestBody, headers);

        // ↓↓↓ 수정 포인트: postForObject 호출 자체도 이제 try 안에 있음.
        // 네트워크 에러, 타임아웃, 401/429 등 OpenAI 쪽 에러가 나도
        // 여기서 잡혀서 안전하게 EMPTY_SELECTION으로 폴백됨.
        try {
            Map<String, Object> response = restTemplate.postForObject(OPENAI_URL, request, Map.class);

            if (response == null) {
                System.err.println("[OpenAiApiService] OpenAI 응답이 null 입니다.");
                return EMPTY_SELECTION;
            }

            List<Map<String, Object>> choices = (List<Map<String, Object>>) response.get("choices");
            if (choices == null || choices.isEmpty()) {
                System.err.println("[OpenAiApiService] choices가 비어있습니다: " + response);
                return EMPTY_SELECTION;
            }

            Map<String, Object> message = (Map<String, Object>) choices.get(0).get("message");
            List<Map<String, Object>> toolCalls = (List<Map<String, Object>>) message.get("tool_calls");
            if (toolCalls == null || toolCalls.isEmpty()) {
                System.err.println("[OpenAiApiService] tool_calls가 비어있습니다: " + message);
                return EMPTY_SELECTION;
            }

            Map<String, Object> firstCall = toolCalls.get(0);
            Map<String, Object> functionCall = (Map<String, Object>) firstCall.get("function");

            String argumentsJson = (String) functionCall.get("arguments");
            Map<String, Object> arguments = objectMapper.readValue(argumentsJson, Map.class);

            Object widgetsObj = arguments.get("widgets");
            List<String> widgets = (widgetsObj instanceof List) ? (List<String>) widgetsObj : List.of();

            String currency = (String) arguments.get("currency");
            String destination = (String) arguments.get("destination");
            String clubName = (String) arguments.get("clubName");

            Integer requestedAmount = null;
            Object amountObj = arguments.get("requestedAmount");
            if (amountObj instanceof Number) {
                requestedAmount = ((Number) amountObj).intValue();
            }

            return new WidgetSelection(widgets, currency, destination, requestedAmount, clubName);

        } catch (RestClientException e) {
            // OpenAI 호출 자체가 실패한 경우 (타임아웃, 네트워크, 401/429 등)
            System.err.println("[OpenAiApiService] OpenAI 호출 실패: " + e.getMessage());
            return EMPTY_SELECTION;
        } catch (Exception e) {
            // 응답은 왔지만 파싱이 실패한 경우
            System.err.println("[OpenAiApiService] 응답 파싱 실패: " + e.getMessage());
            return EMPTY_SELECTION;
        }
    }
}