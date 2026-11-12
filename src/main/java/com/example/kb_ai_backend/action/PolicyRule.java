package com.example.kb_ai_backend.action;

import java.util.Optional;

/** 정책 규칙 하나. 해당 없으면 empty를 반환한다. */
public interface PolicyRule {

    String id();

    Optional<PolicyFinding> evaluate(ActionContext context);
}
