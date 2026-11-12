package com.example.kb_ai_backend.session;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 위젯별 필수 슬롯 정의와 "무엇이 빠졌는지" 계산.
 * 필수 슬롯이 빠진 위젯만 보류하고 나머지 위젯은 바로 그린다.
 */
public final class SlotRequirements {

    public record SlotGuide(String slot, String label, String question, List<String> examples) {}

    private static final Map<String, List<String>> REQUIRED = Map.of(
            "travel_card_charge_widget", List.of("currency"));

    private static final Map<String, SlotGuide> GUIDES = Map.of(
            "currency", new SlotGuide("currency", "통화", "어떤 통화로 환전할까요?",
                    List.of("엔화", "USD", "2만엔")),
            "destination", new SlotGuide("destination", "여행지", "어디로 떠나세요?",
                    List.of("도쿄", "상하이", "런던")),
            "tripDays", new SlotGuide("tripDays", "여행 기간", "며칠 동안 다녀오세요?",
                    List.of("3박4일", "일주일")));

    private SlotRequirements() {}

    public static List<String> missingFor(String widgetId, TravelSlots slots) {
        var missing = new ArrayList<String>();
        for (String slot : REQUIRED.getOrDefault(widgetId, List.of())) {
            if (!filled(slot, slots)) missing.add(slot);
        }
        return missing;
    }

    /** 선택된 위젯 전체에서 빠진 슬롯 (중복 제거, 순서 유지) */
    public static List<String> missingFor(List<String> widgetIds, TravelSlots slots) {
        Set<String> missing = new LinkedHashSet<>();
        widgetIds.forEach(id -> missing.addAll(missingFor(id, slots)));
        return List.copyOf(missing);
    }

    public static SlotGuide guide(String slot) {
        return GUIDES.getOrDefault(slot, new SlotGuide(slot, slot, slot + " 정보를 알려주세요.", List.of()));
    }

    private static boolean filled(String slot, TravelSlots slots) {
        return switch (slot) {
            // KRW는 환전 대상이 아니므로 비어 있는 것으로 본다
            case "currency" -> slots.currency() != null && !slots.currency().equals("KRW");
            case "destination" -> slots.destination() != null;
            case "amount" -> slots.amount() != null;
            case "tripDays" -> slots.tripDays() != null;
            default -> false;
        };
    }
}
