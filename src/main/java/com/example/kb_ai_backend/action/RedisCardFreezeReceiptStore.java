package com.example.kb_ai_backend.action;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.RedisScript;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Supplier;

public final class RedisCardFreezeReceiptStore implements CardFreezeReceiptStore {
    private static final RedisScript<Long> RESERVE = RedisScript.of("""
            if redis.call('EXISTS', KEYS[1], KEYS[2]) > 0 then return 0 end
            redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
            if KEYS[1] ~= KEYS[2] then redis.call('SET', KEYS[2], KEYS[1], 'PX', ARGV[2]) end
            return 1
            """, Long.class);
    private static final RedisScript<Long> COMPLETE = RedisScript.of("""
            if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
            if KEYS[1] ~= KEYS[2] then
                if redis.call('GET', KEYS[2]) ~= KEYS[1] then return 0 end
                redis.call('PEXPIRE', KEYS[2], ARGV[3])
            end
            redis.call('SET', KEYS[1], ARGV[2], 'PX', ARGV[3])
            return 1
            """, Long.class);

    private final StringRedisTemplate redis;
    private final ObjectMapper json;
    private final String ttlMillis;

    public RedisCardFreezeReceiptStore(StringRedisTemplate redis, ObjectMapper json, Duration retention) {
        if (retention.toMillis() < 1) throw new IllegalArgumentException("보관 기간은 1밀리초 이상이어야 합니다.");
        this.redis = redis;
        this.json = json;
        this.ttlMillis = Long.toString(retention.toMillis());
    }

    @Override
    public String fingerprint(ActionType type, Map<String, Object> params) {
        try {
            return digest(json.writer().with(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
                    .writeValueAsString(List.of(type.name(), params)));
        } catch (JsonProcessingException e) {
            throw new ActionException(ActionException.Code.INVALID_REQUEST, "요청 파라미터를 읽을 수 없습니다.");
        }
    }

    @Override
    public Optional<Receipt> findById(String userId, String actionId) {
        return read(actionKey(userId, actionId));
    }

    @Override
    public Optional<Receipt> findByKey(String userId, String idempotencyKey) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) return Optional.empty();
        String pointer = access(() -> redis.opsForValue().get(requestKey(userId, idempotencyKey)));
        if (pointer == null) return Optional.empty();
        var receipt = read(pointer);
        if (receipt.isEmpty()) throw unavailable();
        return receipt;
    }

    @Override
    public boolean reserve(String userId, String actionId, String idempotencyKey, String fingerprint) {
        var keys = keys(userId, actionId, idempotencyKey);
        return Long.valueOf(1).equals(access(() -> redis.execute(RESERVE, keys,
                encode(new Receipt(fingerprint, null)), ttlMillis)));
    }

    @Override
    public void complete(String userId, String idempotencyKey, Receipt receipt) {
        var keys = keys(userId, receipt.result().actionId(), idempotencyKey);
        if (!Long.valueOf(1).equals(access(() -> redis.execute(COMPLETE, keys,
                encode(new Receipt(receipt.fingerprint(), null)), encode(receipt), ttlMillis)))) {
            throw unavailable();
        }
    }

    private Optional<Receipt> read(String key) {
        String value = access(() -> redis.opsForValue().get(key));
        if (value == null) return Optional.empty();
        try {
            return Optional.of(json.readValue(value, Receipt.class));
        } catch (JsonProcessingException e) {
            throw unavailable();
        }
    }

    private String encode(Receipt receipt) {
        try {
            return json.writeValueAsString(receipt);
        } catch (JsonProcessingException e) {
            throw unavailable();
        }
    }

    private static <T> T access(Supplier<T> operation) {
        try {
            return operation.get();
        } catch (DataAccessException e) {
            throw unavailable();
        }
    }

    private static ActionException unavailable() {
        return new ActionException(ActionException.Code.STORAGE_UNAVAILABLE, "카드 정지 기록을 확인할 수 없습니다. 같은 요청으로 다시 확인해주세요.");
    }

    private static List<String> keys(String userId, String actionId, String idempotencyKey) {
        String action = actionKey(userId, actionId);
        return List.of(action, idempotencyKey == null || idempotencyKey.isBlank()
                ? action : requestKey(userId, idempotencyKey));
    }

    private static String actionKey(String userId, String actionId) {
        return prefix(userId) + "action:" + digest(actionId);
    }

    private static String requestKey(String userId, String idempotencyKey) {
        return prefix(userId) + "request:" + digest(idempotencyKey);
    }

    private static String prefix(String userId) {
        return "kkbb:demo-card-freeze:{" + digest(userId) + "}:";
    }

    private static String digest(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
