package com.example.kb_ai_backend.action;

/** 추가 인증 번호 발송 (운영: SMS·푸시, 개발: 메모리 보관) */
public interface OtpSender {

    void send(String userId, String actionId, String code);

    /** 발송 뒤 번호를 보관하는 구현체는 인증이 끝나면 제거한다. */
    default void discard(String actionId) {}
}
