package com.example.kb_ai_backend.action;

/**
 * 액션의 위험 방향.
 * PROTECTIVE는 사용자를 지키는 쪽(카드 정지 등)이라 마찰을 최소화하고,
 * HIGH는 돈이 나가거나 보호를 푸는 쪽이라 추가 인증을 요구한다.
 */
public enum RiskLevel {
    PROTECTIVE, LOW, MEDIUM, HIGH
}
