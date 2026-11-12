package com.example.kb_ai_backend.action;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/** 프론트에 내려주는 액션 상태 */
public record ActionView(String actionId, ActionType type, String label, ActionStatus status,
                         PolicyOutcome decision, List<String> reasons, boolean otpRequired,
                         Instant expiresAt, Map<String, Object> result) {}
