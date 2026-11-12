package com.example.kb_ai_backend.session;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class InMemorySessionStoreTest {

    static class MovableClock extends Clock {
        Instant now = Instant.parse("2026-11-12T03:00:00Z");
        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(java.time.ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
        void advance(Duration d) { now = now.plus(d); }
    }

    @Test void sessionExpiresAfterIdleTtlButSavingExtendsIt() {
        var clock = new MovableClock();
        var store = new InMemorySessionStore(clock, Duration.ofMinutes(30), 100);
        var session = store.create();

        clock.advance(Duration.ofMinutes(20));
        store.save(session.withSlots(new TravelSlots("JPY", "일본", null, null)));
        clock.advance(Duration.ofMinutes(20));
        assertEquals("JPY", store.find(session.id()).orElseThrow().slots().currency());

        clock.advance(Duration.ofMinutes(31));
        assertTrue(store.find(session.id()).isEmpty());
    }

    @Test void oldestSessionIsEvictedWhenCapacityIsExceeded() {
        var clock = new MovableClock();
        var store = new InMemorySessionStore(clock, Duration.ofMinutes(30), 2);
        var first = store.create();
        clock.advance(Duration.ofSeconds(1));
        var second = store.create();
        clock.advance(Duration.ofSeconds(1));
        var third = store.create();

        assertEquals(2, store.size());
        assertTrue(store.find(first.id()).isEmpty());
        assertTrue(store.find(second.id()).isPresent());
        assertTrue(store.find(third.id()).isPresent());
    }

    @Test void unknownOrBlankIdReturnsEmpty() {
        var store = new InMemorySessionStore(new MovableClock(), Duration.ofMinutes(30), 10);
        assertTrue(store.find(null).isEmpty());
        assertTrue(store.find(" ").isEmpty());
        assertTrue(store.find("없는-세션").isEmpty());
    }

    @Test void slotsMergeKeepsPreviousValuesUnlessDestinationChanges() {
        var japan = new TravelSlots("JPY", "일본", 20000, null);
        var withDays = japan.mergedWith(new TravelSlots(null, null, null, 4));
        assertEquals(new TravelSlots("JPY", "일본", 20000, 4), withDays);

        // 여행지가 바뀌면 이전 통화·금액은 이어받지 않는다
        var london = withDays.mergedWith(new TravelSlots(null, "런던", null, null));
        assertEquals(new TravelSlots(null, "런던", null, 4), london);
    }

    @Test void awaitingClarificationNeedsBothPendingWidgetsAndMissingSlots() {
        var session = ConversationSession.start("s", Instant.EPOCH);
        assertFalse(session.awaitingClarification());
        var waiting = session.awaiting(List.of("travel_card_charge_widget"), List.of("currency"));
        assertTrue(waiting.awaitingClarification());
        assertFalse(waiting.resolved().awaitingClarification());
    }
}
