package com.example.kb_ai_backend.trace;

import org.junit.jupiter.api.Test;

import java.time.*;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class TraceStoreTest {

    static class MovableClock extends Clock {
        Instant now = Instant.parse("2026-11-12T05:00:00Z");
        @Override public ZoneId getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    @Test void keepsOnlyMostRecentTraces() {
        var clock = new MovableClock();
        var store = new TraceStore(clock, Duration.ofHours(1), 2);
        store.save(new DecisionTrace("r1", clock.instant(), 3));
        store.save(new DecisionTrace("r2", clock.instant(), 3));
        store.save(new DecisionTrace("r3", clock.instant(), 3));
        assertTrue(store.find("r1").isEmpty());
        assertTrue(store.find("r3").isPresent());
    }

    @Test void tracesExpireAfterRetention() {
        var clock = new MovableClock();
        var store = new TraceStore(clock, Duration.ofHours(1), 10);
        store.save(new DecisionTrace("r1", clock.instant(), 3));
        clock.now = clock.now.plus(Duration.ofMinutes(61));
        assertTrue(store.find("r1").isEmpty());
    }

    @Test void mapContainsDecisionsButNotRawMessage() {
        var trace = new DecisionTrace("r1", Instant.EPOCH, 12);
        trace.selection("jev", "jev-latest", false, List.of("card_freeze_all"),
                List.of(new DecisionTrace.Candidate("card_freeze_all", "include", 0.93),
                        new DecisionTrace.Candidate("travel_insurance_widget", "exclude", 0.88)));
        trace.stage("selection", System.nanoTime(), "jev 응답 210ms");
        trace.finish("ready", List.of("card_freeze_all"));

        var map = trace.toMap();
        assertEquals(12, map.get("messageLength"));
        assertFalse(map.containsKey("message"));
        @SuppressWarnings("unchecked")
        var selection = (Map<String, Object>) map.get("selection");
        assertEquals(2, ((List<?>) selection.get("candidates")).size());
        assertEquals("ready", map.get("status"));
    }
}
