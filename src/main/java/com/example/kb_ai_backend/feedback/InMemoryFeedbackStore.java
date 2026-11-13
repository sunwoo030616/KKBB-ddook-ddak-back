package com.example.kb_ai_backend.feedback;

import java.util.EnumMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

final class InMemoryFeedbackStore implements FeedbackStore {
    private final Map<String, Map<FeedbackEvent, Long>> counts = new ConcurrentHashMap<>();

    @Override
    public void increment(String widget, FeedbackEvent event) {
        counts.compute(widget, (ignored, previous) -> {
            var next = new EnumMap<FeedbackEvent, Long>(FeedbackEvent.class);
            if (previous != null) next.putAll(previous);
            next.merge(event, 1L, Long::sum);
            return Map.copyOf(next);
        });
    }

    @Override
    public Map<FeedbackEvent, Long> counts(String widget) {
        return counts.getOrDefault(widget, Map.of());
    }
}
