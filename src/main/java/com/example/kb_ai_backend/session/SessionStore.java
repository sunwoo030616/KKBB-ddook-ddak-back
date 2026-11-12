package com.example.kb_ai_backend.session;

import java.util.Optional;

/** 대화 세션의 조회, 생성, 조건부 갱신을 관리한다. */
public interface SessionStore {

    Optional<ConversationSession> find(String sessionId);

    /** 읽었던 리비전이 여전히 최신일 때만 저장하고 TTL을 연장한다. */
    boolean save(ConversationSession session);

    ConversationSession create();
}
