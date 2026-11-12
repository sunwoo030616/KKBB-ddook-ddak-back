package com.example.kb_ai_backend.action;

/** 추가 인증 번호 발송 (운영: SMS·푸시, 개발: 메모리 보관) */
public interface OtpSender {

    void send(String userId, String actionId, String code);
}
