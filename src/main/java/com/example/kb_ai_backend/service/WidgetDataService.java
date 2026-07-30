package com.example.kb_ai_backend.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 최종 확정된 9개 위젯의 데이터를 만드는 클래스입니다.
 * travel_card_charge_widget은 GPT가 추론한 통화 코드를 받아
 * ExchangeRateService(실시간 API)로 실제 환율을 계산합니다.
 * greeting과 동아리 관련 위젯은 캔버스 종류/동아리명에 따라 동적으로 생성됩니다.
 */
@Service
public class WidgetDataService {

    private final ExchangeRateService exchangeRateService;

    public WidgetDataService(ExchangeRateService exchangeRateService) {
        this.exchangeRateService = exchangeRateService;
    }

    // 통화 코드 -> 표기명 (표에 없는 코드는 코드 그대로 표시)
    private static final Map<String, String> CURRENCY_DISPLAY_NAME = Map.ofEntries(
            Map.entry("CNY", "위안화(CNY)"),
            Map.entry("USD", "달러(USD)"),
            Map.entry("JPY", "엔화(JPY)"),
            Map.entry("EUR", "유로(EUR)"),
            Map.entry("GBP", "파운드(GBP)"),
            Map.entry("THB", "바트(THB)"),
            Map.entry("HKD", "홍콩달러(HKD)"),
            Map.entry("SGD", "싱가포르달러(SGD)"),
            Map.entry("MNT", "투그릭(MNT)"),
            Map.entry("VND", "동(VND)"),
            Map.entry("BTN", "눌트럼(BTN)")
    );

    private String resolveDestinationLabel(String destination) {
        return (destination != null && !destination.isBlank()) ? destination : "이번";
    }

    private String resolveClubLabel(String clubName) {
        return (clubName != null && !clubName.isBlank()) ? clubName : "동아리";
    }

    /** 선택된 위젯 조합(캔버스 종류)에 따라 인사말을 다르게 생성 */
    public String buildGreeting(List<String> widgetIds, String destination, String clubName) {
        boolean isTravel = widgetIds.stream().anyMatch(id ->
                id.equals("travel_card_charge_widget")
                        || id.equals("overseas_qr_payment_widget")
                        || id.equals("travel_insurance_widget"));

        boolean isClub = widgetIds.stream().anyMatch(id ->
                id.equals("group_account_status")
                        || id.equals("expense_report_widget")
                        || id.equals("group_card_safety_widget"));

        boolean isEmergency = widgetIds.stream().anyMatch(id ->
                id.equals("card_freeze_all")
                        || id.equals("atm_smart_withdrawal")
                        || id.equals("id_reissue_status_widget"));

        if (isTravel) {
            return resolveDestinationLabel(destination) + " 여행이라니, 깨비와 함께 즐거운 여행을 준비해봐요!";
        } else if (isClub) {
            return resolveClubLabel(clubName) + " 총무님! 회비 수납부터 장부 공유까지 깨비가 한 화면에 모아뒀어요.";
        } else if (isEmergency) {
            return "많이 놀라셨죠? 깨비가 침착하게 도와드릴게요.";
        }

        return "깨비가 도와드릴게요!";
    }

    public Map<String, Object> buildWidget(String widgetId, String currency, String destination,
                                           Integer requestedAmount, String clubName) {
        return switch (widgetId) {
            case "travel_card_charge_widget" -> buildTravelCardChargeWidget(currency, destination, requestedAmount);
            case "overseas_qr_payment_widget" -> buildOverseasQrPaymentWidget(destination);
            case "travel_insurance_widget" -> buildTravelInsuranceWidget(destination);
            case "group_account_status" -> buildGroupAccountStatus(clubName);
            case "expense_report_widget" -> buildExpenseReportWidget(clubName);
            default -> buildWidget(widgetId);
        };
    }

    private Map<String, Object> buildTravelCardChargeWidget(String currency, String destination, Integer requestedAmount) {
        String label = resolveDestinationLabel(destination);

        // GPT가 추론해준 통화 코드를 그대로 신뢰
        String code = (currency != null && !currency.isBlank()) ? currency.toUpperCase() : null;

        if (code == null) {
            return Map.ofEntries(
                    Map.entry("type", "travel_card_charge_widget"),
                    Map.entry("supported", false),
                    Map.entry("title", label + " 환전, 아직 통화를 확인하지 못했어요"),
                    Map.entry("unsupportedMessage", "어떤 통화인지 정확히 인식하지 못했어요. "
                            + "KB스타뱅킹 앱 내 '실시간환율' 메뉴에서 확인해주세요!")
            );
        }

        Double rate = exchangeRateService.getKrwRateFor(code); // 1 외화 = 몇 원 (실시간 API)

        if (rate == null) {
            return Map.ofEntries(
                    Map.entry("type", "travel_card_charge_widget"),
                    Map.entry("supported", false),
                    Map.entry("title", label + " 환전, 아직 지원되지 않아요"),
                    Map.entry("unsupportedMessage", code + "는 아직 실시간 환전 서비스가 지원되지 않는 통화예요. "
                            + "KB스타뱅킹 앱 내 '실시간환율' 메뉴에서 확인하시거나, 공항 환전소를 이용해주세요!")
            );
        }

        String displayName = CURRENCY_DISPLAY_NAME.getOrDefault(code, code);
        int suggestedAmount = (requestedAmount != null && requestedAmount > 0) ? requestedAmount : 2000;
        long estimatedKrw = Math.round(suggestedAmount * rate);

        return Map.ofEntries(
                Map.entry("type", "travel_card_charge_widget"),
                Map.entry("supported", true),
                Map.entry("title", displayName + " 충전하셨나요?"),
                Map.entry("currency", code),
                Map.entry("cardBalance", 0),
                Map.entry("exchangeRate", Math.round(rate * 100.0) / 100.0),
                Map.entry("rateDescription", "우대환율 100% 적용 중"),
                Map.entry("chargeButtonLabel", "뚝딱 충전하기"),
                Map.entry("quickAmounts", List.of(100, 500, 1000)),
                Map.entry("suggestedAmount", suggestedAmount),
                Map.entry("estimatedKrw", estimatedKrw)
        );
    }

    private Map<String, Object> buildOverseasQrPaymentWidget(String destination) {
        String label = resolveDestinationLabel(destination);
        return Map.ofEntries(
                Map.entry("type", "overseas_qr_payment_widget"),
                Map.entry("title", "현지 QR 결제 준비하기"),
                Map.entry("linkedCard", "내 트래블 카드"),
                Map.entry("merchantNetwork", label + " 현지 가맹점 (Alipay+)"),
                Map.entry("benefits", List.of(
                        label + " 인기 명소 결제 혜택",
                        label + " 맛집 캐시백"
                )),
                Map.entry("agreements", List.of(
                        Map.ofEntries(Map.entry("label", "해외 결제망(Alipay+) 이용 동의"), Map.entry("required", true)),
                        Map.ofEntries(Map.entry("label", "개인정보 제3자 제공 동의"), Map.entry("required", true))
                ))
        );
    }

    private Map<String, Object> buildTravelInsuranceWidget(String destination) {
        String label = resolveDestinationLabel(destination);
        return Map.ofEntries(
                Map.entry("type", "travel_insurance_widget"),
                Map.entry("title", label + ", 든든하게 준비할까요?"),
                Map.entry("description", "출국 전 나에게 맞는 보장을 선택해 보세요."),
                Map.entry("disclaimer", "정부24 및 경찰청 민원 포털과 연동되어 안전하게 처리됩니다."),
                Map.entry("plans", List.of(
                        Map.ofEntries(
                                Map.entry("planName", "실속형"),
                                Map.entry("productName", label + " 안심 플랜 (실속형)"),
                                Map.entry("summary", "기본 의료비 위주"),
                                Map.entry("recommended", false),
                                Map.entry("coverages", List.of(
                                        "현지 질병/상해 의료비 최대 2천만원",
                                        "휴대폰 도난 및 파손 최대 30만원",
                                        "항공기 및 수하물 지연 최대 10만원"
                                )),
                                Map.entry("finalPrice", 3500)
                        ),
                        Map.ofEntries(
                                Map.entry("planName", "고급형"),
                                Map.entry("productName", label + " 안심 플랜 (고급형)"),
                                Map.entry("summary", "휴대폰 파손 포함"),
                                Map.entry("recommended", true),
                                Map.entry("coverages", List.of(
                                        "현지 질병/상해 의료비 최대 3천만원",
                                        "휴대폰 도난 및 파손 최대 50만원",
                                        "항공기 및 수하물 지연 최대 20만원"
                                )),
                                Map.entry("finalPrice", 5200)
                        )
                ))
        );
    }

    private Map<String, Object> buildGroupAccountStatus(String clubName) {
        String label = resolveClubLabel(clubName);
        return Map.ofEntries(
                Map.entry("type", "group_account_status"),
                Map.entry("title", "7월 " + label + " 회비 수납 현황"),
                Map.entry("syncDescription", "KB 모임통장 연동 완료 (AI 입금 자동 매칭 중)"),
                Map.entry("balance", 1450000),
                Map.entry("paidCount", 22),
                Map.entry("totalCount", 25),
                Map.entry("unpaidMembers", List.of("김스타", "이국민", "박깨비")),
                Map.entry("notice", "AI를 통한 확인이므로 한 번 더 확인하는 것이 좋습니다.")
        );
    }

    private Map<String, Object> buildExpenseReportWidget(String clubName) {
        return Map.ofEntries(
                Map.entry("type", "expense_report_widget"),
                Map.entry("title", "이번 달 지출 리포트"),
                Map.entry("biggestExpense", Map.ofEntries(Map.entry("label", "시설 대관료"), Map.entry("amount", 450000))),
                Map.entry("categories", List.of(
                        Map.ofEntries(Map.entry("label", "시설 대관료"), Map.entry("percent", 50), Map.entry("amount", 450000)),
                        Map.ofEntries(Map.entry("label", "식비 및 회식"), Map.entry("percent", 30), Map.entry("amount", 270000)),
                        Map.ofEntries(Map.entry("label", "장비 및 기타"), Map.entry("percent", 20), Map.entry("amount", 180000))
                )),
                Map.entry("totalAmount", 900000),
                Map.entry("shareTitle", "5월 " + resolveClubLabel(clubName) + " 결산")
        );
    }

    public Map<String, Object> buildWidget(String widgetId) {
        return switch (widgetId) {

            case "travel_card_charge_widget" -> buildTravelCardChargeWidget(null, null, null);
            case "overseas_qr_payment_widget" -> buildOverseasQrPaymentWidget(null);
            case "travel_insurance_widget" -> buildTravelInsuranceWidget(null);
            case "group_account_status" -> buildGroupAccountStatus(null);
            case "expense_report_widget" -> buildExpenseReportWidget(null);

            case "group_card_safety_widget" -> Map.ofEntries(
                    Map.entry("type", "group_card_safety_widget"),
                    Map.entry("title", "모임 전용 체크카드 안심 관리"),
                    Map.entry("toggles", List.of(
                            Map.ofEntries(
                                    Map.entry("label", "실시간 결제 투명 알림"),
                                    Map.entry("description", "투명한 장부 운영을 위해 켜두는 것을 권장해요."),
                                    Map.entry("enabled", true)
                            ),
                            Map.ofEntries(
                                    Map.entry("label", "일일 결제 한도 50만원 제한"),
                                    Map.entry("description", "큰 금액 결제 시에만 한도를 풀어 안전하게 관리하세요."),
                                    Map.entry("enabled", true)
                            )
                    ))
            );

            case "card_freeze_all" -> Map.ofEntries(
                    Map.entry("type", "card_freeze_all"),
                    Map.entry("title", "보유 카드 일괄 정지"),
                    Map.entry("cards", List.of(
                            Map.ofEntries(Map.entry("cardName", "KB국민 노리2 체크카드"), Map.entry("frozen", true)),
                            Map.ofEntries(Map.entry("cardName", "톡톡카드"), Map.entry("frozen", true))
                    )),
                    Map.entry("warningText", "분실된 카드의 모든 결제가 차단됩니다."),
                    Map.entry("confirmMessage", "모든 카드가 안전하게 정지되었어요! 분실된 카드의 결제가 차단되었습니다.")
            );

            case "atm_smart_withdrawal" -> Map.ofEntries(
                    Map.entry("type", "atm_smart_withdrawal"),
                    Map.entry("title", "카드 없는 스마트 출금"),
                    Map.entry("authCode", "987654"),
                    Map.entry("expiresInSeconds", 1800),
                    Map.entry("nearestAtm", Map.ofEntries(
                            Map.entry("name", "여의도본점 ATM"),
                            Map.entry("distance", "150m"),
                            Map.entry("address", "서울 영등포구 여의도동...")
                    )),
                    Map.entry("steps", List.of(
                            "ATM 화면에서 '스마트출금' 선택",
                            "복사한 인증번호 입력",
                            "출금할 금액 입력",
                            "현금 수령"
                    ))
            );

            case "id_reissue_status_widget" -> Map.ofEntries(
                    Map.entry("type", "id_reissue_status_widget"),
                    Map.entry("title", "분실 신고 및 재발급 신청 완료"),
                    Map.entry("items", List.of(
                            Map.ofEntries(Map.entry("idType", "주민등록증"), Map.entry("status", "신고 및 재발급 완료"), Map.entry("expectedPeriod", "3~4주")),
                            Map.ofEntries(Map.entry("idType", "운전면허증"), Map.entry("status", "신고 및 재발급 완료"), Map.entry("expectedPeriod", "1~2주"))
                    )),
                    Map.entry("description", "정부24 및 경찰청 민원 포털과 연동되어 안전하게 처리됩니다.")
            );

            default -> Map.ofEntries(
                    Map.entry("type", "unknown"),
                    Map.entry("title", "알 수 없는 위젯: " + widgetId)
            );
        };
    }
}