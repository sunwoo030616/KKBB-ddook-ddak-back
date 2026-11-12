package com.example.kb_ai_backend.action;

import java.util.Map;

/**
 * 실제 금융 API를 호출하는 어댑터 포트.
 * Mock → 금융사 Sandbox → KB 운영 API 순서로 구현체만 바꾼다.
 */
public interface ActionExecutor {

    Map<String, Object> execute(ActionType type, String userId, Map<String, Object> params);
}
