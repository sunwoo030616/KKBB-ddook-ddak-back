package com.example.kb_ai_backend.service;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/** 발표 시연에서만 사용하는 고정 입력과 예시 환율. */
@Component
@Profile({"presentation", "oidc-demo"})
public class PresentationScenarios {

    private static final List<String> LOST_WALLET = List.of(
            "card_freeze_all", "atm_smart_withdrawal", "id_reissue_status_widget");
    private static final List<String> OVERSEAS_TRAVEL = List.of(
            "travel_card_charge_widget", "overseas_qr_payment_widget", "travel_insurance_widget");
    private static final List<String> CLUB_DUES = List.of(
            "group_account_status", "expense_report_widget", "group_card_safety_widget");

    private static final Map<String, List<String>> WIDGETS = Map.of(
            "지갑을 잃어버렸어. 카드 정지하고 현금 찾는 방법이랑 신분증 재발급도 알려줘", LOST_WALLET,
            "지갑을 분실했어요", LOST_WALLET,
            "지갑을 잃어버렸어. 긴급 조치 화면을 만들어줘", LOST_WALLET,
            "상하이로 3박 4일 여행 가는데 환전, QR 결제, 여행자보험 준비해줘", OVERSEAS_TRAVEL,
            "상하이로 3박 4일 여행 가는데 환전과 QR 결제, 보험을 준비해줘", OVERSEAS_TRAVEL,
            "상하이로 3박 4일 여행 가는데 준비해줘", OVERSEAS_TRAVEL,
            "테니스 동아리 총무야. 이번 달 회비 수납 현황이랑 지출 리포트, 카드 안전 설정 보여줘", CLUB_DUES,
            "여행 환전이랑 보험 알려줘", List.of("travel_card_charge_widget", "travel_insurance_widget"),
            "여행 환전과 QR 결제 준비해줘", List.of("travel_card_charge_widget", "overseas_qr_payment_widget"),
            "분실 카드 정지해줘", List.of("card_freeze_all"));

    public WidgetSelectionExperimentService.Result select(String message) {
        String normalized = message.strip().replaceAll("\\s+", " ").replaceFirst("[.!?]+$", "");
        var widgets = WIDGETS.getOrDefault(normalized, List.of());
        var decisions = widgets.stream().collect(java.util.stream.Collectors.toMap(
                id -> id, id -> new WidgetSelectionExperimentService.Decision("include", null)));
        return new WidgetSelectionExperimentService.Result(
                "presentation", "fixed-scenarios", "widget_selection_only", widgets, decisions,
                false, 0, null, null);
    }

    public Double exchangeRate(String currency) {
        return switch (currency.toUpperCase(Locale.ROOT)) {
            case "CNY" -> 190.0;
            case "JPY" -> 9.0;
            case "USD" -> 1_380.0;
            default -> null;
        };
    }
}
