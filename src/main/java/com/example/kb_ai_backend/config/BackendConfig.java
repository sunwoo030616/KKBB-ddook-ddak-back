package com.example.kb_ai_backend.config;

import com.example.kb_ai_backend.action.*;
import com.example.kb_ai_backend.action.rules.AmountLimitRule;
import com.example.kb_ai_backend.action.rules.NightTimeRule;
import com.example.kb_ai_backend.action.rules.RiskLevelRule;
import com.example.kb_ai_backend.action.rules.VelocityRule;
import com.example.kb_ai_backend.audit.HashChainAuditLog;
import com.example.kb_ai_backend.session.InMemorySessionStore;
import com.example.kb_ai_backend.session.SessionStore;
import com.example.kb_ai_backend.trace.TraceStore;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.time.Clock;
import java.time.Duration;
import java.time.ZoneId;
import java.util.List;

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

    @Bean
    public TraceStore traceStore(Clock clock,
                                 @Value("${app.trace.retention-minutes:60}") long retentionMinutes,
                                 @Value("${app.trace.max-traces:500}") int maxTraces) {
        return new TraceStore(clock, Duration.ofMinutes(retentionMinutes), maxTraces);
    }

    @Bean
    public PolicyEngine policyEngine(@Value("${app.policy.step-up-krw:1000000}") long stepUpKrw,
                                     @Value("${app.policy.deny-krw:5000000}") long denyKrw,
                                     @Value("${app.policy.night-start-hour:0}") int nightStart,
                                     @Value("${app.policy.night-end-hour:6}") int nightEnd,
                                     @Value("${app.policy.zone:Asia/Seoul}") String zone,
                                     @Value("${app.policy.max-attempts:3}") int maxAttempts) {
        return new PolicyEngine(List.of(
                new RiskLevelRule(),
                new AmountLimitRule(stepUpKrw, denyKrw),
                new NightTimeRule(ZoneId.of(zone), nightStart, nightEnd),
                new VelocityRule(maxAttempts)));
    }

    @Bean
    public HashChainAuditLog auditLog(Clock clock) {
        return new HashChainAuditLog(clock);
    }

    @Bean
    public DemoOtpSender otpSender() {
        return new DemoOtpSender();
    }

    @Bean
    public ActionExecutor actionExecutor(Clock clock) {
        return new MockActionExecutor(clock);
    }

    @Bean
    public ActionService actionService(PolicyEngine policyEngine, ActionExecutor executor, DemoOtpSender otpSender,
                                       HashChainAuditLog auditLog, Clock clock,
                                       @Value("${app.action.ttl-minutes:5}") long ttlMinutes,
                                       @Value("${app.policy.velocity-window-minutes:10}") long windowMinutes,
                                       @Value("${app.action.max-otp-attempts:3}") int maxOtpAttempts) {
        return new ActionService(policyEngine, executor, otpSender, auditLog, clock,
                Duration.ofMinutes(ttlMinutes), Duration.ofMinutes(windowMinutes), maxOtpAttempts);
    }
}
