package com.example.kb_ai_backend.audit;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;

import java.util.List;

public final class RedisAuditStore implements AuditStore {
    private static final DefaultRedisScript<List> HEAD = new DefaultRedisScript<>("""
            local tail = redis.call('LINDEX', KEYS[1], -1)
            return {redis.call('LLEN', KEYS[1]), tail or ''}
            """, List.class);

    private static final DefaultRedisScript<Long> APPEND = new DefaultRedisScript<>("""
            if redis.call('LLEN', KEYS[1]) ~= tonumber(ARGV[1]) then return 0 end
            local tail = redis.call('LINDEX', KEYS[1], -1)
            if tail and cjson.decode(tail).hash ~= ARGV[2] then return 0 end
            redis.call('RPUSH', KEYS[1], ARGV[3])
            return 1
            """, Long.class);

    private final StringRedisTemplate redis;
    private final ObjectMapper json;
    private final String key;

    public RedisAuditStore(StringRedisTemplate redis, ObjectMapper json, String key) {
        this.redis = redis;
        this.json = json;
        this.key = key;
    }

    @Override
    public Head head() {
        var result = redis.execute(HEAD, List.of(key));
        if (result == null) throw new IllegalStateException("감사 로그를 읽지 못했습니다.");
        long size = ((Number) result.get(0)).longValue();
        return new Head(size, size == 0 ? HashChainAuditLog.GENESIS : decode((String) result.get(1)).hash());
    }

    @Override
    public boolean append(Head expected, AuditEntry entry) {
        try {
            Long result = redis.execute(APPEND, List.of(key), Long.toString(expected.size()),
                    expected.hash(), json.writeValueAsString(entry));
            if (result == null) throw new IllegalStateException("감사 로그를 저장하지 못했습니다.");
            return result == 1L;
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("감사 로그를 직렬화하지 못했습니다.", e);
        }
    }

    @Override
    public List<AuditEntry> entries() {
        var result = redis.opsForList().range(key, 0, -1);
        if (result == null) throw new IllegalStateException("감사 로그를 읽지 못했습니다.");
        return result.stream().map(this::decode).toList();
    }

    private AuditEntry decode(String entry) {
        try {
            return json.readValue(entry, AuditEntry.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("저장된 감사 로그 형식이 올바르지 않습니다.", e);
        }
    }
}
