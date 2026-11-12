package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.action.*;
import com.example.kb_ai_backend.audit.AuditEntry;
import com.example.kb_ai_backend.audit.AuditVerification;
import com.example.kb_ai_backend.audit.HashChainAuditLog;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 위젯의 버튼(카드 정지, 출금 번호 발급, 충전)이 호출하는 실행 API.
 * 사용자 식별은 시연용으로 X-User-Id 헤더를 쓰고, 운영에서는 인증 토큰의 사용자로 대체한다.
 */
@RestController
@ConditionalOnProperty(name = "app.action.demo-enabled", havingValue = "true")
@RequestMapping("/api")
public class ActionController {

    private final ActionService actions;
    private final HashChainAuditLog audit;
    private final DemoOtpSender demoOtp;
    private final boolean exposeDemoOtp;

    public ActionController(ActionService actions, HashChainAuditLog audit, DemoOtpSender demoOtp,
                            @Value("${app.action.expose-demo-otp:true}") boolean exposeDemoOtp) {
        this.actions = actions;
        this.audit = audit;
        this.demoOtp = demoOtp;
        this.exposeDemoOtp = exposeDemoOtp;
    }

    public record PrepareRequest(String type, Map<String, Object> params) {}

    public record ConfirmRequest(String otp) {}

    @PostMapping("/actions")
    public Map<String, Object> prepare(@RequestHeader(value = "X-User-Id", defaultValue = "demo-user") String userId,
                                       @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
                                       @RequestBody PrepareRequest request) {
        ActionType type = parseType(request == null ? null : request.type());
        ActionView view = actions.prepare(userId, type, request.params(), idempotencyKey);
        return body(view, true);
    }

    @PostMapping("/actions/{actionId}/confirm")
    public Map<String, Object> confirm(@RequestHeader(value = "X-User-Id", defaultValue = "demo-user") String userId,
                                       @PathVariable String actionId,
                                       @RequestBody(required = false) ConfirmRequest request) {
        return body(actions.confirm(userId, actionId, request == null ? null : request.otp()), false);
    }

    @GetMapping("/actions/{actionId}")
    public Map<String, Object> get(@RequestHeader(value = "X-User-Id", defaultValue = "demo-user") String userId,
                                   @PathVariable String actionId) {
        return body(actions.get(userId, actionId), false);
    }

    @GetMapping("/audit/verify")
    public AuditVerification verifyAudit() {
        return audit.verify();
    }

    @GetMapping("/audit")
    public List<AuditEntry> auditEntries(@RequestParam(required = false) String subject) {
        return subject == null ? audit.entries() : audit.entriesFor(subject);
    }

    @ExceptionHandler(ActionException.class)
    public ResponseEntity<Map<String, Object>> handle(ActionException e) {
        var body = new LinkedHashMap<String, Object>();
        body.put("error", e.code().name());
        body.put("message", e.getMessage());
        if (e.remainingOtpAttempts() != null) body.put("remainingOtpAttempts", e.remainingOtpAttempts());
        return ResponseEntity.status(statusOf(e.code())).body(body);
    }

    private Map<String, Object> body(ActionView view, boolean includeDemoOtp) {
        var body = new LinkedHashMap<String, Object>();
        body.put("actionId", view.actionId());
        body.put("type", view.type());
        body.put("label", view.label());
        body.put("status", view.status());
        body.put("decision", view.decision());
        body.put("reasons", view.reasons());
        body.put("otpRequired", view.otpRequired());
        body.put("expiresAt", view.expiresAt().toString());
        if (view.result() != null) body.put("result", view.result());
        // 시연 환경에는 문자 발송이 없으므로 설정이 켜져 있을 때만 인증번호를 응답에 실어준다
        if (includeDemoOtp && exposeDemoOtp && view.otpRequired()) {
            demoOtp.lastCodeFor(view.actionId()).ifPresent(code -> body.put("demoOtp", code));
        }
        return body;
    }

    private static ActionType parseType(String raw) {
        if (raw == null) throw new ActionException(ActionException.Code.INVALID_REQUEST, "type이 필요합니다.");
        try {
            return ActionType.valueOf(raw.trim());
        } catch (IllegalArgumentException e) {
            throw new ActionException(ActionException.Code.INVALID_REQUEST, "허용되지 않은 액션입니다: " + raw);
        }
    }

    private static HttpStatus statusOf(ActionException.Code code) {
        return switch (code) {
            case INVALID_REQUEST -> HttpStatus.BAD_REQUEST;
            case NOT_FOUND -> HttpStatus.NOT_FOUND;
            case DENIED -> HttpStatus.FORBIDDEN;
            case EXPIRED -> HttpStatus.GONE;
            case OTP_REQUIRED, OTP_MISMATCH -> HttpStatus.UNPROCESSABLE_ENTITY;
            case LOCKED -> HttpStatus.LOCKED;
            case IDEMPOTENCY_CONFLICT, EXECUTION_IN_PROGRESS -> HttpStatus.CONFLICT;
            case EXECUTION_FAILED -> HttpStatus.BAD_GATEWAY;
            case STORAGE_UNAVAILABLE -> HttpStatus.SERVICE_UNAVAILABLE;
        };
    }
}
