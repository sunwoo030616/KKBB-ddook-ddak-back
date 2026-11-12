package com.example.kb_ai_backend.action;

import java.time.Instant;

/**
 * 정책 판단에 필요한 입력. 규칙은 이 값만 보고 판단한다 (규칙 자체는 상태를 갖지 않음).
 * amountKrw: 원화 환산 금액, 금액이 없는 액션은 null
 * recentAttempts: 같은 사용자가 같은 액션을 최근 구간에 요청한 횟수 (이번 요청 포함)
 */
public record ActionContext(String userId, ActionType type, Long amountKrw, Instant at, int recentAttempts) {}
