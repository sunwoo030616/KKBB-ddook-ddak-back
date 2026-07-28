package com.example.kb_ai_backend.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class WidgetDataService {

    public Map<String, Object> buildWidget(String widgetId) {
        return switch (widgetId) {

            // ───────────── ① 해외여행 캔버스 ─────────────

            case "travel_card_charge_widget" -> Map.of(
                    "type", "travel_card_charge_widget",
                    "title", "위안화(CNY) 충전하셨나요?",
                    "currency", "CNY",
                    "cardBalance", 0,
                    "exchangeRate", 189.2,
                    "rateDescription", "우대환율 100% 적용 중",
                    "chargeButtonLabel", "뚝딱 충전하기",
                    "quickAmounts", List.of(100, 500, 1000),
                    "suggestedAmount", 2000,
                    "estimatedKrw", 378400
            );

            case "overseas_qr_payment_widget" -> Map.of(
                    "type", "overseas_qr_payment_widget",
                    "title", "현지 QR 결제 준비하기",
                    "linkedCard", "내 트래블 카드",
                    "merchantNetwork", "상하이 현지 가맹점 (Alipay+)",
                    "benefits", List.of(
                            "디즈니랜드 기념품 샵 결제 혜택",
                            "루자방루역 주변 맛집 캐시백"
                    ),
                    "agreements", List.of(
                            Map.of("label", "해외 결제망(Alipay+) 이용 동의", "required", true),
                            Map.of("label", "개인정보 제3자 제공 동의", "required", true)
                    )
            );

            case "travel_insurance_widget" -> Map.of(
                    "type", "travel_insurance_widget",
                    "title", "상하이, 든든하게 준비할까요?",
                    "description", "출국 전 나에게 맞는 보장을 선택해 보세요.",
                    "plans", List.of(
                            Map.of(
                                    "planName", "일반형",
                                    "coverages", List.of(
                                            "현지 질병/상해 의료비 최대 2천만원",
                                            "휴대폰 도난 및 파손 최대 30만원",
                                            "항공기 및 수하물 지연 최대 10만원"
                                    ),
                                    "finalPrice", 3500
                            ),
                            Map.of(
                                    "planName", "고급형",
                                    "coverages", List.of(
                                            "현지 질병/상해 의료비 최대 3천만원",
                                            "휴대폰 도난 및 파손 최대 50만원",
                                            "항공기 및 수하물 지연 최대 20만원"
                                    ),
                                    "finalPrice", 5200
                            )
                    )
            );

            // ───────────── ② 동아리/운영진 캔버스 ─────────────

            case "group_account_status" -> Map.of(
                    "type", "group_account_status",
                    "title", "7월 동아리 회비 수납 현황",
                    "syncDescription", "KB 모임통장 연동 완료 (AI 입금 자동 매칭 중)",
                    "balance", 1450000,
                    "paidCount", 22,
                    "totalCount", 25,
                    "unpaidMembers", List.of("김스타", "이국민", "박깨비"),
                    "notice", "AI를 통한 확인이므로 한 번 더 확인하는 것이 좋습니다."
            );

            case "expense_report_widget" -> Map.of(
                    "type", "expense_report_widget",
                    "title", "이번 달 지출 리포트",
                    "biggestExpense", Map.of("label", "강남 테니스장 대관료", "amount", 450000),
                    "categories", List.of(
                            Map.of("label", "시설 대관료", "percent", 50, "amount", 450000),
                            Map.of("label", "식비 및 회식", "percent", 30, "amount", 270000),
                            Map.of("label", "장비 및 기타", "percent", 20, "amount", 180000)
                    ),
                    "totalAmount", 900000,
                    "shareTitle", "5월 테니스 동아리 결산"
            );

            case "group_card_safety_widget" -> Map.of(
                    "type", "group_card_safety_widget",
                    "title", "모임 전용 체크카드 안심 관리",
                    "toggles", List.of(
                            Map.of(
                                    "label", "실시간 결제 투명 알림",
                                    "description", "투명한 장부 운영을 위해 켜두는 것을 권장해요.",
                                    "enabled", true
                            ),
                            Map.of(
                                    "label", "일일 결제 한도 50만원 제한",
                                    "description", "큰 금액 결제 시에만 한도를 풀어 안전하게 관리하세요.",
                                    "enabled", true
                            )
                    )
            );

            // ───────────── ③ 지갑/스마트폰 분실 응급 캔버스 ─────────────

            case "card_freeze_all" -> Map.of(
                    "type", "card_freeze_all",
                    "title", "보유 카드 일괄 정지",
                    "cards", List.of(
                            Map.of("cardName", "KB국민 노리2 체크카드", "frozen", true),
                            Map.of("cardName", "톡톡카드", "frozen", true)
                    ),
                    "warningText", "분실된 카드의 모든 결제가 차단됩니다.",
                    "confirmMessage", "모든 카드가 안전하게 정지되었어요! 분실된 카드의 결제가 차단되었습니다."
            );

            case "atm_smart_withdrawal" -> Map.of(
                    "type", "atm_smart_withdrawal",
                    "title", "카드 없는 스마트 출금",
                    "authCode", "987654",
                    "expiresInSeconds", 1800,
                    "nearestAtm", Map.of(
                            "name", "여의도본점 ATM",
                            "distance", "150m",
                            "address", "서울 영등포구 여의도동..."
                    ),
                    "steps", List.of(
                            "ATM 화면에서 '스마트출금' 선택",
                            "복사한 인증번호 입력",
                            "출금할 금액 입력",
                            "현금 수령"
                    )
            );

            case "id_reissue_status_widget" -> Map.of(
                    "type", "id_reissue_status_widget",
                    "title", "분실 신고 및 재발급 신청 완료",
                    "items", List.of(
                            Map.of("idType", "주민등록증", "status", "신고 및 재발급 완료", "expectedPeriod", "3~4주"),
                            Map.of("idType", "운전면허증", "status", "신고 및 재발급 완료", "expectedPeriod", "1~2주")
                    ),
                    "description", "정부24 및 경찰청 민원 포털과 연동되어 안전하게 처리됩니다."
            );

            default -> Map.of(
                    "type", "unknown",
                    "title", "알 수 없는 위젯: " + widgetId
            );
        };
    }
}