package com.example.kb_ai_backend.config;

import com.example.kb_ai_backend.session.InMemorySessionStore;
import com.example.kb_ai_backend.session.SessionStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.Duration;

/**
 * 프레임워크에 의존하지 않는 도메인 객체들을 여기서만 빈으로 등록한다.
 * (세션·정책·감사 로직은 순수 Java라 단위 테스트에서 바로 생성해서 쓴다)
 */
@Configuration
public class BackendConfig {

    @Bean
    public Clock clock() {
        return Clock.systemUTC();
    }

    @Bean
    public SessionStore sessionStore(Clock clock,
                                     @Value("${app.session.ttl-minutes:30}") long ttlMinutes,
                                     @Value("${app.session.max-sessions:10000}") int maxSessions) {
        return new InMemorySessionStore(clock, Duration.ofMinutes(ttlMinutes), maxSessions);
    }
}
