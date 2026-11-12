package com.example.kb_ai_backend.action;

public enum ActionStatus {
    AWAITING_CONFIRM, // 정책 통과, 사용자 최종 확인만 남음
    AWAITING_OTP,     // 추가 인증 필요
    EXECUTED,
    DENIED,
    LOCKED,           // OTP 반복 실패
    EXPIRED,
    FAILED            // 외부 실행 실패
}
