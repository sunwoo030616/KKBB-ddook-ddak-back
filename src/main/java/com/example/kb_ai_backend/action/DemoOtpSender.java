package com.example.kb_ai_backend.action;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/** 시연용: 발송 대신 마지막 번호를 보관해 두고, 설정이 켜져 있을 때만 응답에 노출한다. */
public class DemoOtpSender implements OtpSender {

    private final ConcurrentHashMap<String, String> lastCodes = new ConcurrentHashMap<>();

    @Override
    public void send(String userId, String actionId, String code) {
        lastCodes.put(actionId, code);
    }

    @Override
    public void discard(String actionId) {
        lastCodes.remove(actionId);
    }

    public Optional<String> lastCodeFor(String actionId) {
        return Optional.ofNullable(lastCodes.get(actionId));
    }
}
