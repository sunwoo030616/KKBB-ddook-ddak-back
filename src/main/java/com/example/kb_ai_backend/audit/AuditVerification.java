package com.example.kb_ai_backend.audit;

/** brokenAtSeq: 처음으로 체인이 깨진 기록 번호 (정상이면 null) */
public record AuditVerification(boolean valid, int size, Long brokenAtSeq, String headHash) {}
