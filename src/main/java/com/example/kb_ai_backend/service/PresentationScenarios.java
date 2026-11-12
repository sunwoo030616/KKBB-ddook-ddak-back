package com.example.kb_ai_backend.service;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Locale;
import java.util.Map;

/** 발표 시연에서만 사용하는 고정 입력과 예시 환율. */
@Component
@Profile("presentation")
public class PresentationScenarios {

    private static final Map<String, List<String>> WIDGETS = Map.of(
            "여행 환전이랑 보험 알려줘", List.of("travel_card_charge_widget", "travel_insurance_widget"),
            "분실 카드 정지해줘", List.of("card_freeze_all"));

    public WidgetSelectionExperimentService.Result select(String message) {
        var widgets = WIDGETS.getOrDefault(message.strip(), List.of());
        var decisions = widgets.stream().collect(java.util.stream.Collectors.toMap(
                id -> id, id -> new WidgetSelectionExperimentService.Decision("include", null)));
        return new WidgetSelectionExperimentService.Result(
                "presentation", "fixed-scenarios", "widget_selection_only", widgets, decisions,
                false, 0, null, null);
    }

    public Double exchangeRate(String currency) {
        return switch (currency.toUpperCase(Locale.ROOT)) {
            case "JPY" -> 9.0;
            case "USD" -> 1_380.0;
            default -> null;
        };
    }
}
