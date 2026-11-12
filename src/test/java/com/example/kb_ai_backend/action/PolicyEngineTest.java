package com.example.kb_ai_backend.action;

import com.example.kb_ai_backend.action.rules.*;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.ZoneId;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class PolicyEngineTest {
    static final ZoneId SEOUL = ZoneId.of("Asia/Seoul");
    static final Instant AFTERNOON = Instant.parse("2026-11-12T05:00:00Z"); // 14시 KST
    static final Instant NIGHT = Instant.parse("2026-11-11T17:30:00Z");     // 02시 30분 KST

    PolicyEngine engine = new PolicyEngine(List.of(
            new RiskLevelRule(),
            new AmountLimitRule(1_000_000, 5_000_000),
            new NightTimeRule(SEOUL, 0, 6),
            new VelocityRule(3)));

    PolicyDecision decide(ActionType type, Long amount, Instant at, int attempts) {
        return engine.evaluate(new ActionContext("u1", type, amount, at, attempts));
    }

    @Test void protectiveActionIsAllowedEvenAtNightAndWhenRepeated() {
        var decision = decide(ActionType.CARD_FREEZE_ALL, null, NIGHT, 10);
        assertEquals(PolicyOutcome.ALLOW, decision.outcome());
        assertEquals(List.of("default"), decision.findings().stream().map(PolicyFinding::ruleId).toList());
    }

    @Test void highRiskActionAlwaysNeedsStepUp() {
        var decision = decide(ActionType.CARD_UNFREEZE_ALL, null, AFTERNOON, 1);
        assertEquals(PolicyOutcome.STEP_UP, decision.outcome());
        assertEquals("risk-level", decision.findings().get(0).ruleId());
    }

    @Test void smallChargeInDaytimeIsAllowedButLargeChargeNeedsStepUp() {
        assertEquals(PolicyOutcome.ALLOW, decide(ActionType.TRAVEL_CARD_CHARGE, 300_000L, AFTERNOON, 1).outcome());
        assertEquals(PolicyOutcome.STEP_UP, decide(ActionType.TRAVEL_CARD_CHARGE, 1_500_000L, AFTERNOON, 1).outcome());
    }

    @Test void chargeOverHardLimitIsDeniedWhateverElseApplies() {
        var decision = decide(ActionType.TRAVEL_CARD_CHARGE, 6_000_000L, NIGHT, 1);
        assertEquals(PolicyOutcome.DENY, decision.outcome());
        // 차단 사유와 함께 심야 사유도 남는다 (감사 로그에 판단 근거 전체를 기록하기 위함)
        assertEquals(List.of("amount-limit", "night-time"), decision.findings().stream().map(PolicyFinding::ruleId).toList());
    }

    @Test void nightTimeSmallChargeNeedsStepUp() {
        assertEquals(PolicyOutcome.STEP_UP, decide(ActionType.TRAVEL_CARD_CHARGE, 10_000L, NIGHT, 1).outcome());
    }

    @Test void repeatedNonProtectiveRequestsAreDenied() {
        assertEquals(PolicyOutcome.STEP_UP, decide(ActionType.SMART_WITHDRAWAL_CODE, null, AFTERNOON, 3).outcome());
        assertEquals(PolicyOutcome.DENY, decide(ActionType.SMART_WITHDRAWAL_CODE, null, AFTERNOON, 4).outcome());
    }

    @Test void nonPositiveAmountIsDenied() {
        assertEquals(PolicyOutcome.DENY, decide(ActionType.TRAVEL_CARD_CHARGE, 0L, AFTERNOON, 1).outcome());
    }

    @Test void nightWindowCanWrapPastMidnight() {
        var rule = new NightTimeRule(SEOUL, 23, 5);
        var lateEvening = Instant.parse("2026-11-12T14:30:00Z"); // 23시 30분 KST
        assertTrue(rule.evaluate(new ActionContext("u", ActionType.TRAVEL_CARD_CHARGE, 1L, lateEvening, 1)).isPresent());
        assertTrue(rule.evaluate(new ActionContext("u", ActionType.TRAVEL_CARD_CHARGE, 1L, AFTERNOON, 1)).isEmpty());
    }

    @Test void invalidLimitConfigurationFailsFast() {
        assertThrows(IllegalArgumentException.class, () -> new AmountLimitRule(5_000_000, 1_000_000));
        assertThrows(IllegalArgumentException.class, () -> new VelocityRule(0));
    }
}
