package com.example.kb_ai_backend.session;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.RedisScript;

import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** Redis TTL을 사용하고 읽었던 리비전이 여전히 최신일 때만 세션을 갱신한다. */
public final class RedisSessionStore implements SessionStore {
    private static final RedisScript<Long> SAVE = RedisScript.of("""
            local current = redis.call('GET', KEYS[1])
            if not current or string.match(current, '^(%d+):') ~= ARGV[1] then
                return 0
            end
            redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3])
            return 1
            """, Long.class);

    private final StringRedisTemplate redis;
    private final ObjectMapper mapper;
    private final Clock clock;
    private final Duration ttl;
    private final String keyPrefix;

    public RedisSessionStore(StringRedisTemplate redis, ObjectMapper mapper, Clock clock,
                             Duration ttl, String keyPrefix) {
        if (ttl.toMillis() < 1) throw new IllegalArgumentException("ttl은 1밀리초 이상이어야 합니다.");
        if (keyPrefix.isBlank()) throw new IllegalArgumentException("Redis 세션 키 접두사가 필요합니다.");
        this.redis = redis;
        this.mapper = mapper;
        this.clock = clock;
        this.ttl = ttl;
        this.keyPrefix = keyPrefix;
    }

    @Override
    public Optional<ConversationSession> find(String sessionId) {
        if (sessionId == null || sessionId.isBlank()) return Optional.empty();
        return Optional.ofNullable(redis.opsForValue().get(keyPrefix + sessionId)).map(this::decode);
    }

    @Override
    public boolean save(ConversationSession session) {
        var next = session.advancedAt(clock.instant());
        return Long.valueOf(1).equals(redis.execute(SAVE, List.of(keyPrefix + session.id()),
                Long.toString(session.revision()), encode(next), Long.toString(ttl.toMillis())));
    }

    @Override
    public ConversationSession create() {
        var session = ConversationSession.start(UUID.randomUUID().toString(), clock.instant());
        if (!Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(keyPrefix + session.id(), encode(session), ttl))) {
            throw new IllegalStateException("새 세션 ID를 저장하지 못했습니다.");
        }
        return session;
    }

    private String encode(ConversationSession session) {
        try {
            return session.revision() + ":" + mapper.writeValueAsString(session);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("세션을 저장 가능한 형식으로 변환하지 못했습니다.", e);
        }
    }

    private ConversationSession decode(String encoded) {
        int separator = encoded.indexOf(':');
        if (separator < 0) throw new IllegalStateException("저장된 세션 형식이 올바르지 않습니다.");
        try {
            return mapper.readValue(encoded.substring(separator + 1), ConversationSession.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("저장된 세션을 읽지 못했습니다.", e);
        }
    }
}
