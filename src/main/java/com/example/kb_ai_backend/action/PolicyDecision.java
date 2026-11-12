package com.example.kb_ai_backend.action;

import java.util.List;

public record PolicyDecision(PolicyOutcome outcome, List<PolicyFinding> findings) {

    public PolicyDecision {
        findings = List.copyOf(findings);
    }

    public List<String> reasons() {
        return findings.stream().map(PolicyFinding::reason).toList();
    }
}
