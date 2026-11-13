package com.example.kb_ai_backend.audit;

import com.example.kb_ai_backend.feedback.FeedbackEvent;
import com.example.kb_ai_backend.feedback.FeedbackRanker;
import com.example.kb_ai_backend.feedback.RedisFeedbackStore;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@EnabledIfEnvironmentVariable(named = "KKBB_TEST_REDIS", matches = "true")
class RedisObservabilityStoreTest {
    @Autowired StringRedisTemplate redis;
    @Autowired ObjectMapper mapper;

    @Test
    void independentWritersContinueOneChainAndRestartCanReadIt() throws Exception {
        String key = "test:audit:" + UUID.randomUUID();
        var writers = List.of(log(key), log(key));
        var pool = Executors.newFixedThreadPool(writers.size());
        try {
            var futures = writers.stream().map(writer -> pool.submit(() -> {
                for (int i = 0; i < 20; i++) {
                    writer.append("PREPARED", "actor", "subject", Map.of("otp", "123456"));
                }
            })).toList();
            for (var future : futures) future.get(15, TimeUnit.SECONDS);
            var restarted = log(key);
            assertEquals(40, restarted.entries().size());
            assertTrue(restarted.verify().valid());
            assertTrue(restarted.entries().stream().allMatch(e -> "***".equals(e.details().get("otp"))));
            assertEquals(41, restarted.append("CONFIRMED", "actor", "subject", Map.of()).seq());
        } finally {
            pool.shutdownNow();
            redis.delete(key);
        }
    }

    @Test
    void feedbackCountsAndRankingSurviveNewInstances() {
        String prefix = "test:feedback:" + UUID.randomUUID() + ":";
        try {
            var original = ranker(prefix);
            original.record("widget", FeedbackEvent.SHOWN);
            original.record("widget", FeedbackEvent.CLICKED);
            var restarted = ranker(prefix);
            assertEquals(original.stats("widget"), restarted.stats("widget"));
            restarted.record("widget", FeedbackEvent.COMPLETED);
            assertEquals(1, original.stats("widget").completed());
            assertEquals(List.of("widget", "other"), restarted.rank(List.of("other", "widget")));
        } finally {
            redis.delete(prefix + "widget");
        }
    }

    private HashChainAuditLog log(String key) {
        return new HashChainAuditLog(Clock.systemUTC(), new RedisAuditStore(redis, mapper, key));
    }

    private FeedbackRanker ranker(String prefix) {
        return new FeedbackRanker(Set.of("widget", "other"), 1, new RedisFeedbackStore(redis, prefix));
    }
}
