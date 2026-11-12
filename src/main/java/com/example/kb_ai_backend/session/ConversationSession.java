package com.example.kb_ai_backend.session;

import java.time.Instant;
import java.util.List;

/**
 * 한 사용자의 짧은 대화 상태.
 * slots: 지금까지 확정된 여행 정보, pendingWidgets: 정보가 부족해 아직 못 그린 위젯,
 * missingSlots: 그 위젯을 그리려면 더 받아야 하는 슬롯 이름.
 */
public record ConversationSession(String id, TravelSlots slots, List<String> pendingWidgets,
                                  List<String> missingSlots, Instant updatedAt, long revision) {

    public ConversationSession {
        slots = slots == null ? TravelSlots.EMPTY : slots;
        pendingWidgets = pendingWidgets == null ? List.of() : List.copyOf(pendingWidgets);
        missingSlots = missingSlots == null ? List.of() : List.copyOf(missingSlots);
    }

    public static ConversationSession start(String id, Instant now) {
        return new ConversationSession(id, TravelSlots.EMPTY, List.of(), List.of(), now, 0);
    }

    /** 되묻기 응답을 기다리는 중인지 */
    public boolean awaitingClarification() {
        return !pendingWidgets.isEmpty() && !missingSlots.isEmpty();
    }

    public ConversationSession withSlots(TravelSlots next) {
        return new ConversationSession(id, next, pendingWidgets, missingSlots, updatedAt, revision);
    }

    public ConversationSession awaiting(List<String> widgets, List<String> missing) {
        return new ConversationSession(id, slots, widgets, missing, updatedAt, revision);
    }

    public ConversationSession resolved() {
        return new ConversationSession(id, slots, List.of(), List.of(), updatedAt, revision);
    }

    public ConversationSession advancedAt(Instant now) {
        return new ConversationSession(id, slots, pendingWidgets, missingSlots, now, revision + 1);
    }
}
