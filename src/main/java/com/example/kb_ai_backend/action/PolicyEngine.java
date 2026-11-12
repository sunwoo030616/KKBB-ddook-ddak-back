package com.example.kb_ai_backend.action;

import java.util.ArrayList;
import java.util.List;

/**
 * 등록된 규칙을 모두 평가해 가장 엄격한 결과를 고른다.
 * 어떤 규칙에도 걸리지 않으면 ALLOW (사용자 최종 확인만 거침).
 */
public class PolicyEngine {

    private final List<PolicyRule> rules;

    public PolicyEngine(List<PolicyRule> rules) {
        this.rules = List.copyOf(rules);
    }

    public PolicyDecision evaluate(ActionContext context) {
        var findings = new ArrayList<PolicyFinding>();
        PolicyOutcome outcome = PolicyOutcome.ALLOW;
        for (PolicyRule rule : rules) {
            var finding = rule.evaluate(context);
            if (finding.isPresent()) {
                findings.add(finding.get());
                outcome = outcome.stricter(finding.get().outcome());
            }
        }
        if (findings.isEmpty()) {
            findings.add(new PolicyFinding("default", PolicyOutcome.ALLOW, "사용자 최종 확인 후 실행합니다."));
        }
        return new PolicyDecision(outcome, findings);
    }

    public List<String> ruleIds() {
        return rules.stream().map(PolicyRule::id).toList();
    }
}
