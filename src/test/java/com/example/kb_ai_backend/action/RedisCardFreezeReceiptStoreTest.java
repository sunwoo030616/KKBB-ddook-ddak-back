package com.example.kb_ai_backend.action;

import com.example.kb_ai_backend.audit.HashChainAuditLog;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.redis.core.StringRedisTemplate;

import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static com.example.kb_ai_backend.action.ActionType.CARD_FREEZE_ALL;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@EnabledIfEnvironmentVariable(named = "KKBB_TEST_REDIS", matches = "true")
class RedisCardFreezeReceiptStoreTest {
    @Autowired StringRedisTemplate redis;
    @Autowired ObjectMapper mapper;
    @Autowired Clock clock;

    @Test void completedActionReplaysByKeyAndIdFromAnotherService() {
        var user = UUID.randomUUID().toString();
        var calls = new AtomicInteger();
        ActionExecutor executor = (type, owner, params) -> {
            calls.incrementAndGet();
            return new MockActionExecutor(clock).execute(type, owner, params);
        };
        var original = service(executor);
        var action = original.prepare(user, CARD_FREEZE_ALL, Map.of(), "retry-key");
        var result = original.confirm(user, action.actionId(), null);

        var restarted = service(executor);
        assertEquals(result, restarted.prepare(user, CARD_FREEZE_ALL, Map.of(), "retry-key"));
        assertEquals(result, restarted.get(user, action.actionId()));
        assertEquals(result, restarted.confirm(user, action.actionId(), null));
        assertEquals(1, calls.get());
        assertEquals(ActionException.Code.IDEMPOTENCY_CONFLICT, assertThrows(ActionException.class,
                () -> restarted.prepare(user, CARD_FREEZE_ALL, Map.of("changed", true), "retry-key")).code());
        assertEquals(ActionException.Code.NOT_FOUND, assertThrows(ActionException.class,
                () -> restarted.get("another-user", action.actionId())).code());
    }

    @Test void twoServicesWithTheSameKeyCannotBothExecute() throws Exception {
        var user = UUID.randomUUID().toString();
        var entered = new CountDownLatch(1);
        var release = new CountDownLatch(1);
        var first = service((type, owner, params) -> {
            entered.countDown();
            try {
                if (!release.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("test timed out");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException(e);
            }
            return Map.of("frozenCards", List.of("mock card"));
        });
        var second = service((type, owner, params) -> fail("Only the first request may execute"));
        var a = first.prepare(user, CARD_FREEZE_ALL, Map.of(), "retry-key");
        var b = second.prepare(user, CARD_FREEZE_ALL, Map.of(), "retry-key");
        var workers = Executors.newSingleThreadExecutor();
        try {
            var completion = workers.submit(() -> first.confirm(user, a.actionId(), null));
            assertTrue(entered.await(5, TimeUnit.SECONDS));
            assertEquals(ActionException.Code.EXECUTION_IN_PROGRESS, assertThrows(ActionException.class,
                    () -> second.confirm(user, b.actionId(), null)).code());
            release.countDown();
            assertEquals(completion.get(5, TimeUnit.SECONDS), second.confirm(user, b.actionId(), null));
        } finally {
            release.countDown();
            workers.shutdownNow();
        }
    }

    @Test void unfinishedReservationBlocksExecutionAfterRestart() {
        var user = UUID.randomUUID().toString();
        var id = UUID.randomUUID().toString();
        var store = store();
        assertTrue(store.reserve(user, id, "retry-key", store.fingerprint(CARD_FREEZE_ALL, Map.of())));

        var restarted = service((type, owner, params) -> fail("An unfinished reservation must not execute again"));
        assertEquals(ActionException.Code.EXECUTION_IN_PROGRESS, assertThrows(ActionException.class,
                () -> restarted.prepare(user, CARD_FREEZE_ALL, Map.of(), "retry-key")).code());
        assertEquals(ActionException.Code.EXECUTION_IN_PROGRESS, assertThrows(ActionException.class,
                () -> restarted.confirm(user, id, null)).code());
    }

    private ActionService service(ActionExecutor executor) {
        return new ActionService(new PolicyEngine(List.of()), executor, new DemoOtpSender(), new HashChainAuditLog(clock),
                clock, Duration.ofMinutes(5), Duration.ofMinutes(10), 3, store());
    }

    private RedisCardFreezeReceiptStore store() {
        return new RedisCardFreezeReceiptStore(redis, mapper, Duration.ofMinutes(2));
    }
}
