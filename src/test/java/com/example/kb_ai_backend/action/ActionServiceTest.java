package com.example.kb_ai_backend.action;

import com.example.kb_ai_backend.action.rules.*;
import com.example.kb_ai_backend.audit.HashChainAuditLog;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

class ActionServiceTest {

    static class MovableClock extends Clock {
        Instant now = Instant.parse("2026-11-12T05:00:00Z"); // 14시 KST
        @Override public ZoneId getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    MovableClock clock;
    DemoOtpSender otp;
    HashChainAuditLog audit;
    AtomicInteger executions;
    ActionService service;

    @BeforeEach void setup() {
        clock = new MovableClock();
        otp = new DemoOtpSender();
        audit = new HashChainAuditLog(clock);
        executions = new AtomicInteger();
        var policy = new PolicyEngine(List.of(new RiskLevelRule(), new AmountLimitRule(1_000_000, 5_000_000),
                new NightTimeRule(ZoneId.of("Asia/Seoul"), 0, 6), new VelocityRule(3)));
        ActionExecutor counting = (type, user, params) -> {
            executions.incrementAndGet();
            return new MockActionExecutor(clock).execute(type, user, params);
        };
        service = new ActionService(policy, counting, otp, audit, clock, Duration.ofMinutes(5), Duration.ofMinutes(10), 3);
    }

    @Test void protectiveActionExecutesWithUserConfirmOnly() {
        var prepared = service.prepare("u1", ActionType.CARD_FREEZE_ALL, Map.of(), null);
        assertEquals(ActionStatus.AWAITING_CONFIRM, prepared.status());
        assertFalse(prepared.otpRequired());

        var done = service.confirm("u1", prepared.actionId(), null);
        assertEquals(ActionStatus.EXECUTED, done.status());
        assertNotNull(done.result().get("frozenCards"));
        assertEquals(1, executions.get());
    }

    @Test void highRiskActionNeedsCorrectOtp() {
        var prepared = service.prepare("u1", ActionType.SMART_WITHDRAWAL_CODE, Map.of(), null);
        assertEquals(ActionStatus.AWAITING_OTP, prepared.status());
        assertTrue(prepared.otpRequired());

        var missing = assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), null));
        assertEquals(ActionException.Code.OTP_REQUIRED, missing.code());

        String code = otp.lastCodeFor(prepared.actionId()).orElseThrow();
        var done = service.confirm("u1", prepared.actionId(), code);
        assertEquals(ActionStatus.EXECUTED, done.status());
        assertEquals(6, ((String) done.result().get("authCode")).length());
    }

    @Test void threeWrongOtpsLockTheActionAndItNeverExecutes() {
        var prepared = service.prepare("u1", ActionType.CARD_UNFREEZE_ALL, Map.of(), null);
        String code = otp.lastCodeFor(prepared.actionId()).orElseThrow();
        String wrong = code.equals("000000") ? "111111" : "000000";

        var first = assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), wrong));
        assertEquals(ActionException.Code.OTP_MISMATCH, first.code());
        assertEquals(2, first.remainingOtpAttempts());
        assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), wrong));
        var third = assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), wrong));
        assertEquals(ActionException.Code.LOCKED, third.code());

        // 잠긴 뒤에는 맞는 번호도 통하지 않는다
        var after = assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), code));
        assertEquals(ActionException.Code.LOCKED, after.code());
        assertEquals(0, executions.get());
    }

    @Test void deniedActionCannotBeConfirmed() {
        var prepared = service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 9_000_000), null);
        assertEquals(ActionStatus.DENIED, prepared.status());
        assertEquals(PolicyOutcome.DENY, prepared.decision());

        var error = assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), null));
        assertEquals(ActionException.Code.DENIED, error.code());
        assertEquals(0, executions.get());
    }

    @Test void confirmingTwiceExecutesOnlyOnce() {
        var prepared = service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 300_000, "currency", "JPY"), null);
        var first = service.confirm("u1", prepared.actionId(), null);
        var second = service.confirm("u1", prepared.actionId(), null);
        assertEquals(first.result(), second.result());
        assertEquals(1, executions.get());
    }

    @Test void sameIdempotencyKeyReturnsSameActionWithoutNewAttempt() {
        var first = service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 300_000), "key-1");
        var retried = service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 300_000), "key-1");
        assertEquals(first.actionId(), retried.actionId());

        var conflict = assertThrows(ActionException.class,
                () -> service.prepare("u1", ActionType.CARD_FREEZE_ALL, Map.of(), "key-1"));
        assertEquals(ActionException.Code.IDEMPOTENCY_CONFLICT, conflict.code());

        // 다른 사용자는 같은 키를 써도 별개
        var other = service.prepare("u2", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 300_000), "key-1");
        assertNotEquals(first.actionId(), other.actionId());
    }

    @Test void expiredActionIsRejected() {
        var prepared = service.prepare("u1", ActionType.CARD_FREEZE_ALL, Map.of(), null);
        clock.now = clock.now.plus(Duration.ofMinutes(6));
        var error = assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), null));
        assertEquals(ActionException.Code.EXPIRED, error.code());
        assertEquals(0, executions.get());
    }

    @Test void otherUsersCannotSeeOrConfirmTheAction() {
        var prepared = service.prepare("u1", ActionType.CARD_FREEZE_ALL, Map.of(), null);
        var error = assertThrows(ActionException.class, () -> service.confirm("u2", prepared.actionId(), null));
        assertEquals(ActionException.Code.NOT_FOUND, error.code());
    }

    @Test void repeatedRequestsInShortWindowAreDenied() {
        for (int i = 0; i < 3; i++) {
            assertEquals(ActionStatus.AWAITING_CONFIRM,
                    service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 10_000), null).status());
        }
        assertEquals(ActionStatus.DENIED,
                service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 10_000), null).status());

        clock.now = clock.now.plus(Duration.ofMinutes(11));
        assertEquals(ActionStatus.AWAITING_CONFIRM,
                service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", 10_000), null).status());
    }

    @Test void chargeWithoutValidAmountIsRejected() {
        var error = assertThrows(ActionException.class,
                () -> service.prepare("u1", ActionType.TRAVEL_CARD_CHARGE, Map.of("amountKrw", "많이"), null));
        assertEquals(ActionException.Code.INVALID_REQUEST, error.code());
    }

    @Test void executorFailureIsRecordedAndNotRetriedSilently() {
        var policy = new PolicyEngine(List.of(new RiskLevelRule()));
        ActionExecutor failing = (type, user, params) -> { throw new IllegalStateException("카드사 응답 없음"); };
        var failingService = new ActionService(policy, failing, otp, audit, clock, Duration.ofMinutes(5), Duration.ofMinutes(10), 3);
        var prepared = failingService.prepare("u1", ActionType.CARD_FREEZE_ALL, Map.of(), null);

        var error = assertThrows(ActionException.class, () -> failingService.confirm("u1", prepared.actionId(), null));
        assertEquals(ActionException.Code.EXECUTION_FAILED, error.code());
        assertEquals(ActionStatus.FAILED, failingService.get("u1", prepared.actionId()).status());
    }

    @Test void everyStepIsWrittenToVerifiableAuditLog() {
        var prepared = service.prepare("u1", ActionType.SMART_WITHDRAWAL_CODE, Map.of(), null);
        assertThrows(ActionException.class, () -> service.confirm("u1", prepared.actionId(), "999999x"));
        service.confirm("u1", prepared.actionId(), otp.lastCodeFor(prepared.actionId()).orElseThrow());

        var events = audit.entriesFor(prepared.actionId()).stream().map(e -> e.event()).toList();
        assertEquals(List.of("ACTION_PREPARED", "OTP_FAILED", "OTP_PASSED", "ACTION_EXECUTED"), events);
        assertTrue(audit.verify().valid());
    }
}
