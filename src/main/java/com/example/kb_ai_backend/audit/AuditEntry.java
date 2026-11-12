package com.example.kb_ai_backend.audit;

import java.time.Instant;
import java.util.Map;

/**
 * 감사 로그 한 줄. hash는 (이전 hash + 이 줄의 내용)으로 계산되므로
 * 중간 기록 하나를 고치거나 지우면 그 뒤의 모든 hash가 맞지 않게 된다.
 */
public record AuditEntry(long seq, Instant at, String event, String actor, String subject,
                         Map<String, String> details, String prevHash, String hash) {

    public AuditEntry {
        details = Map.copyOf(details);
    }
}
