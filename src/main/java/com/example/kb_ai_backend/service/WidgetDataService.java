package com.example.kb_ai_backend.service;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 최종 확정된 9개 위젯의 mock 데이터를 만드는 클래스입니다.
 * 실제 KB 기능 이름/동작 방식을 최대한 반영해서 mock 데이터를 만들었습니다
 * (예: 스마트ATM출금의 1회용 인증번호, 이체한도 관련 실제 체계 등).
 */
@Service
public class WidgetDataService {

    public Map<String, Object> buildWidget(String widgetId) {
        return switch (widgetId) {

            // ───────────── ① 해외여행 캔버스 ─────────────

            case "currency_exchange_widget" -> Map.of(
                    "type", "currency_exchange_widget",
                    "title", "모바일 환전 신청",
                    "targetCurrency", "USD",
                    "requestedAmount", 500,
                    "currentRate", 1385.2,
                    "pickupLocation", "인천공항 제1터미널 KB국민은행 환전소",
                    "pickupAvailableFrom", "출국 2시간 전부터 수령 가능"
            );

            case "dcc_block_toggle" -> Map.of(
                    "type", "dcc_block_toggle",
                    "title", "해외원화결제(DCC) 차단",
                    "description", "해외 원화 결제 시 3~8% 추가 수수료를 막아줍니다",
                    "enabled", false,
                    "targetCard", "국민 트래블러스 체크카드"
            );

            case "card_overseas_toggle" -> Map.of(
                    "type", "card_overseas_toggle",
                    "title", "카드 해외결제 설정",
                    "cards", List.of(
                            Map.of("cardName", "국민 트래블러스 체크카드", "last4", "7710", "overseasEnabled", true),
                            Map.of("cardName", "국민 다담카드", "last4", "9930", "overseasEnabled", false)
                    )
            );

            // ───────────── ② 동아리/운영진 캔버스 ─────────────

            case "group_account_status" -> Map.of(
                    "type", "group_account_status",
                    "title", "홍보팀 모임통장 현황",
                    "balance", 1240000,
                    "recentTransactions", List.of(
                            Map.of("desc", "회식비 결제", "amount", -380000, "date", "07-24"),
                            Map.of("desc", "대관료 이체", "amount", -150000, "date", "07-20")
                    )
            );

            case "expense_split_widget" -> {
                // N빵 정산: 총액을 인원수로 나누는 실제 계산 로직 (LLM 호출 없이 자바 코드로 처리)
                int totalAmount = 480000;
                int memberCount = 15;
                int perPerson = totalAmount / memberCount;

                yield Map.of(
                        "type", "expense_split_widget",
                        "title", "홍보팀 회식비 정산",
                        "totalAmount", totalAmount,
                        "memberCount", memberCount,
                        "perPersonAmount", perPerson,
                        "unpaidMembers", List.of("김OO", "이OO", "박OO")
                );
            }

            case "receipt_share_widget" -> Map.of(
                    "type", "receipt_share_widget",
                    "title", "영수증 모아보기",
                    "receipts", List.of(
                            Map.of("merchant", "OO고깃집", "amount", 380000, "date", "07-24"),
                            Map.of("merchant", "OO스터디룸", "amount", 150000, "date", "07-20")
                    )
            );

            // ───────────── ③ 지갑/스마트폰 분실 응급 캔버스 ─────────────

            case "card_freeze_all" -> Map.of(
                    "type", "card_freeze_all",
                    "title", "전 카드 일괄 정지",
                    "cards", List.of(
                            Map.of("cardName", "국민 노리카드", "last4", "4821", "frozen", true),
                            Map.of("cardName", "국민 다담카드", "last4", "9930", "frozen", true)
                    ),
                    "confirmMessage", "보유하신 카드 2건이 모두 정지되었습니다"
            );

            case "atm_smart_withdrawal" -> Map.of(
                    "type", "atm_smart_withdrawal",
                    "title", "스마트ATM출금",
                    "authCode", "482913",
                    "expiresInSeconds", 180,
                    "dailyLimit", 1000000,
                    "description", "가까운 ATM에서 '예금출금 > 스마트ATM출금' 선택 후 인증번호 입력"
            );

            case "mobile_id_guide" -> Map.of(
                    "type", "mobile_id_guide",
                    "title", "모바일 신분증 안내",
                    "steps", List.of(
                            "KB스타뱅킹 > 인증/보안 메뉴 이동",
                            "본인 명의 휴대폰 인증",
                            "모바일 신분증 발급 완료"
                    )
            );

            default -> Map.of(
                    "type", "unknown",
                    "title", "알 수 없는 위젯: " + widgetId
            );
        };
    }
}
