package com.example.kb_ai_backend.session;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 단일 인스턴스용 세션 저장소.
 * - 마지막 사용 후 ttl이 지나면 만료 (조회 시점에 지연 삭제)
 * - 세션 수가 maxSessions를 넘으면 만료 세션부터, 그래도 넘으면 가장 오래된 세션부터 정리
 */
public class InMemorySessionStore implements SessionStore {

    private final ConcurrentHashMap<String, ConversationSession> sessions = new ConcurrentHashMap<>();
    private final Clock clock;
    private final Duration ttl;
    private final int maxSessions;

    public InMemorySessionStore(Clock clock, Duration ttl, int maxSessions) {
        if (ttl.isNegative() || ttl.isZero()) throw new IllegalArgumentException("ttl은 0보다 커야 합니다.");
        if (maxSessions < 1) throw new IllegalArgumentException("maxSessions는 1 이상이어야 합니다.");
        this.clock = clock;
        this.ttl = ttl;
        this.maxSessions = maxSessions;
    }

    @Override
    public Optional<ConversationSession> find(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) return Optional.empty();
        ConversationSession session = sessions.get(sessionId);
        if (session == null) return Optional.empty();
        if (expired(session, clock.instant())) {
            sessions.remove(sessionId, session);
            return Optional.empty();
        }
        return Optional.of(session);
    }

    @Override
    public boolean save(ConversationSession session) {
        Instant now = clock.instant();
        ConversationSession next = session.advancedAt(now);
        return sessions.computeIfPresent(session.id(), (id, current) -> {
            if (expired(current, now)) return null;
            return current.revision() == session.revision() ? next : current;
        }) == next;
    }

    @Override
    public synchronized ConversationSession create() {
        var session = ConversationSession.start(UUID.randomUUID().toString(), clock.instant());
        sessions.put(session.id(), session);
        if (sessions.size() > maxSessions) evict(session.id());
        return session;
    }

    int size() {
        return sessions.size();
    }

    private boolean expired(ConversationSession session, Instant now) {
        return !now.isBefore(session.updatedAt().plus(ttl));
    }

    private void evict(String newSessionId) {
        Instant now = clock.instant();
        sessions.values().removeIf(s -> expired(s, now));
        while (sessions.size() > maxSessions) {
            sessions.values().stream()
                    .filter(session -> !session.id().equals(newSessionId))
                    .min(Comparator.comparing(ConversationSession::updatedAt))
                    .ifPresent(oldest -> sessions.remove(oldest.id(), oldest));
        }
    }
}
