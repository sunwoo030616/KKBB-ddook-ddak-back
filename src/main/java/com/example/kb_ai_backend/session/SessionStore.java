package com.example.kb_ai_backend.session;

import java.util.Optional;

/**
 * 대화 세션 저장소. 지금은 인메모리 구현만 있고,
 * 인스턴스가 여러 대가 되면 같은 인터페이스로 Redis 구현을 붙인다.
 */
public interface SessionStore {

    Optional<ConversationSession> find(String sessionId);

    /** 저장하면서 마지막 사용 시각을 갱신한다 (TTL 연장) */
    ConversationSession save(ConversationSession session);

    ConversationSession create();
}
