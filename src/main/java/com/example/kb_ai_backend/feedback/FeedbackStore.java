package com.example.kb_ai_backend.feedback;

import java.util.Map;

public interface FeedbackStore {
    void increment(String widget, FeedbackEvent event);
    Map<FeedbackEvent, Long> counts(String widget);
}
