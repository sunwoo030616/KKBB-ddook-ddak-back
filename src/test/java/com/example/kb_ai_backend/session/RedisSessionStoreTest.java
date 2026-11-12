package com.example.kb_ai_backend.session;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(properties = "app.session.redis-enabled=true")
@EnabledIfEnvironmentVariable(named = "KKBB_TEST_REDIS", matches = "true")
class RedisSessionStoreTest {
    @Autowired SessionStore sessions;
    @Autowired StringRedisTemplate redis;
    @Autowired ObjectMapper mapper;
    @Autowired Clock clock;

    @Test void anotherStoreResumesTheSessionAndRejectsAnOlderRevision() {
        var initial = sessions.create();
        var waiting = initial.withSlots(new TravelSlots("JPY", null, 20000, null))
                .awaiting(List.of("overseas_qr_payment_widget"), List.of("destination"));
        String key = "kkbb:session:" + initial.id();
        try {
            assertTrue(sessions.save(waiting));
            var restarted = new RedisSessionStore(redis, mapper, clock, Duration.ofMinutes(30), "kkbb:session:");
            var saved = restarted.find(initial.id()).orElseThrow();
            assertEquals(waiting.slots(), saved.slots());
            assertEquals(waiting.pendingWidgets(), saved.pendingWidgets());
            assertEquals(waiting.missingSlots(), saved.missingSlots());
            assertEquals(1, saved.revision());
            assertFalse(restarted.save(initial));

            redis.expire(key, Duration.ofMinutes(5));
            assertTrue(restarted.save(saved.resolved()));
            assertTrue(redis.getExpire(key, TimeUnit.SECONDS) > 25 * 60);

            redis.expireAt(key, java.time.Instant.EPOCH);
            assertTrue(sessions.find(initial.id()).isEmpty());
            assertFalse(restarted.save(saved));
        } finally {
            redis.delete(key);
        }
    }
}
