package com.example.kb_ai_backend.action.rules;

import com.example.kb_ai_backend.action.*;

import java.util.Optional;

/** 고위험 액션은 항상 추가 인증. 보호성 액션은 판단하지 않는다 (다른 규칙도 보호성 액션은 건너뜀). */
public class RiskLevelRule implements PolicyRule {

    @Override
    public String id() { return "risk-level"; }

    @Override
    public Optional<PolicyFinding> evaluate(ActionContext context) {
        if (context.type().risk() == RiskLevel.HIGH) {
            return Optional.of(new PolicyFinding(id(), PolicyOutcome.STEP_UP,
                    context.type().label() + "은(는) 고위험 액션이라 추가 인증이 필요해요."));
        }
        return Optional.empty();
    }
}
