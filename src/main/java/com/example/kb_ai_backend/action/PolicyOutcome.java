package com.example.kb_ai_backend.action;

/** 선언 순서가 곧 엄격함 순서. 여러 규칙의 결과 중 가장 엄격한 것이 최종 결과가 된다. */
public enum PolicyOutcome {
    ALLOW, STEP_UP, DENY;

    public PolicyOutcome stricter(PolicyOutcome other) {
        return other.ordinal() > ordinal() ? other : this;
    }
}
