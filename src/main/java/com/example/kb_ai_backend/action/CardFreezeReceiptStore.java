package com.example.kb_ai_backend.action;

import java.util.Map;
import java.util.Optional;

/** 완료 결과와 실행권을 공유하는 모의 카드 정지 전용 저장소. */
public interface CardFreezeReceiptStore {
    record Receipt(String fingerprint, ActionView result) {}

    String fingerprint(ActionType type, Map<String, Object> params);
    Optional<Receipt> findById(String userId, String actionId);
    Optional<Receipt> findByKey(String userId, String idempotencyKey);

    /** 실행 직전에 한 요청만 실행권을 확보한다. */
    boolean reserve(String userId, String actionId, String idempotencyKey, String fingerprint);

    void complete(String userId, String idempotencyKey, Receipt receipt);
}
