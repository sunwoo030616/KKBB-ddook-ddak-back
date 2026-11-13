package com.example.kb_ai_backend.feedback;

import org.springframework.data.redis.core.StringRedisTemplate;

import java.util.EnumMap;
import java.util.Map;

public final class RedisFeedbackStore implements FeedbackStore {
    private final StringRedisTemplate redis;
    private final String keyPrefix;

    public RedisFeedbackStore(StringRedisTemplate redis, String keyPrefix) {
        this.redis = redis;
        this.keyPrefix = keyPrefix;
    }

    @Override
    public void increment(String widget, FeedbackEvent event) {
        redis.opsForHash().increment(keyPrefix + widget, event.name(), 1L);
    }

    @Override
    public Map<FeedbackEvent, Long> counts(String widget) {
        var stored = redis.<String, String>opsForHash().entries(keyPrefix + widget);
        var counts = new EnumMap<FeedbackEvent, Long>(FeedbackEvent.class);
        stored.forEach((event, count) -> counts.put(FeedbackEvent.valueOf(event), Long.parseLong(count)));
        return counts;
    }
}
