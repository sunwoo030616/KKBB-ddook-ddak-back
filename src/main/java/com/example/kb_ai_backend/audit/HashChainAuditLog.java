package com.example.kb_ai_backend.audit;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.util.*;

/**
 * 추가만 가능한(append-only) 해시체인 감사 로그.
 * - 각 필드에 길이를 붙여 직렬화한 뒤 이전 해시와 함께 SHA-256으로 계산한다
 * - verify()로 처음부터 다시 계산해 위·변조, 삭제, 순서 변경을 찾아낸다
 * - OTP·인증번호·계좌번호 같은 민감값은 저장 전에 마스킹한다
 *
 * 지금은 메모리에 보관하고, 운영에서는 같은 계산 방식으로 DB/WORM 스토리지에 쌓으면 된다.
 */
public class HashChainAuditLog {

    static final String GENESIS = "0".repeat(64);
    private static final Set<String> SENSITIVE_KEYS = Set.of("otp", "code", "authcode", "password", "pin", "account", "accountnumber", "cardnumber");

    private final Clock clock;
    private final List<AuditEntry> entries = new ArrayList<>();

    public HashChainAuditLog(Clock clock) {
        this.clock = clock;
    }

    public synchronized AuditEntry append(String event, String actor, String subject, Map<String, ?> details) {
        long seq = entries.size() + 1L;
        String prev = entries.isEmpty() ? GENESIS : entries.get(entries.size() - 1).hash();
        var masked = mask(details);
        var at = clock.instant();
        String hash = hash(prev, seq, at.toString(), event, actor, subject, masked);
        var entry = new AuditEntry(seq, at, event, actor, subject, masked, prev, hash);
        entries.add(entry);
        return entry;
    }

    public synchronized List<AuditEntry> entries() {
        return List.copyOf(entries);
    }

    public synchronized List<AuditEntry> entriesFor(String subject) {
        return entries.stream().filter(e -> Objects.equals(e.subject(), subject)).toList();
    }

    public AuditVerification verify() {
        return verify(entries());
    }

    /** 임의의 기록 목록을 검증한다 (외부로 내보낸 로그 검증에도 그대로 사용) */
    public static AuditVerification verify(List<AuditEntry> chain) {
        String prev = GENESIS;
        long expectedSeq = 1;
        for (AuditEntry e : chain) {
            String recomputed = hash(e.prevHash(), e.seq(), e.at().toString(), e.event(), e.actor(), e.subject(), e.details());
            if (e.seq() != expectedSeq || !e.prevHash().equals(prev) || !recomputed.equals(e.hash())) {
                return new AuditVerification(false, chain.size(), e.seq(), null);
            }
            prev = e.hash();
            expectedSeq++;
        }
        return new AuditVerification(true, chain.size(), null, prev);
    }

    static Map<String, String> mask(Map<String, ?> details) {
        var masked = new TreeMap<String, String>();
        if (details == null) return masked;
        details.forEach((k, v) -> {
            String key = k.toLowerCase(Locale.ROOT);
            masked.put(k, SENSITIVE_KEYS.contains(key) ? "***" : String.valueOf(v));
        });
        return masked;
    }

    private static String hash(String prev, long seq, String at, String event, String actor, String subject,
                               Map<String, String> details) {
        var canonical = new StringBuilder();
        appendField(canonical, prev);
        appendField(canonical, Long.toString(seq));
        appendField(canonical, at);
        appendField(canonical, event);
        appendField(canonical, actor);
        appendField(canonical, subject);
        appendField(canonical, Integer.toString(details.size()));
        new TreeMap<>(details).forEach((key, value) -> {
            appendField(canonical, key);
            appendField(canonical, value);
        });
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(canonical.toString().getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", e);
        }
    }
    private static void appendField(StringBuilder buffer, String value) {
        if (value == null) {
            buffer.append("-1:");
        } else {
            buffer.append(value.length()).append(':').append(value);
        }
    }

}
