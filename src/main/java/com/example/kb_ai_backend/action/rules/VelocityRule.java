package com.example.kb_ai_backend.action.rules;

import com.example.kb_ai_backend.action.*;

import java.util.Optional;

/**
 * 짧은 시간에 같은 액션이 반복되면 차단 (탈취된 세션의 자동화 공격, 중복 클릭 폭주 방지).
 * 보호성 액션은 반복돼도 막지 않는다 — 분실 상황에서 카드 정지를 막으면 안 되기 때문.
 */
public class VelocityRule implements PolicyRule {

    private final int maxAttempts;

    public VelocityRule(int maxAttempts) {
        if (maxAttempts < 1) throw new IllegalArgumentException("maxAttempts는 1 이상");
        this.maxAttempts = maxAttempts;
    }

    @Override
    public String id() { return "velocity"; }

    @Override
    public Optional<PolicyFinding> evaluate(ActionContext context) {
        if (context.type().risk() == RiskLevel.PROTECTIVE) return Optional.empty();
        if (context.recentAttempts() <= maxAttempts) return Optional.empty();
        return Optional.of(new PolicyFinding(id(), PolicyOutcome.DENY,
                "짧은 시간에 같은 요청이 반복돼 잠시 차단했어요. 잠시 후 다시 시도해주세요."));
    }
}
