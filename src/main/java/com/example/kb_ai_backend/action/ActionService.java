package com.example.kb_ai_backend.action;

import com.example.kb_ai_backend.audit.HashChainAuditLog;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * AI는 화면만 제안하고, 실제 실행은 여기서만 일어난다.
 *
 * prepare: 정책 평가 → DENY면 즉시 차단, STEP_UP이면 OTP 발송, ALLOW면 사용자 확인 대기
 * confirm: 만료·소유자·OTP 확인 후 어댑터로 실행 (같은 액션은 한 번만 실행됨)
 *
 * 같은 Idempotency-Key로 다시 요청하면 새 액션을 만들지 않고 기존 액션을 돌려준다
 * (네트워크 재시도·버튼 연타로 카드 충전이 두 번 되는 일을 막기 위함).
 */
public class ActionService {

    private final PolicyEngine policy;
    private final ActionExecutor executor;
    private final OtpSender otpSender;
    private final HashChainAuditLog audit;
    private final Clock clock;
    private final Duration actionTtl;
    private final Duration velocityWindow;
    private final int maxOtpAttempts;
    private final CardFreezeReceiptStore freezeReceipts;

    private final SecureRandom random = new SecureRandom();
    private final ConcurrentHashMap<String, PendingAction> actions = new ConcurrentHashMap<>();
    private final Map<IdempotencyScope, String> idempotencyKeys = new HashMap<>();
    private final Map<AttemptScope, Deque<Instant>> attempts = new HashMap<>();
    private Instant nextCleanupAt = Instant.MIN;

    private record IdempotencyScope(String userId, String key) {}
    private record AttemptScope(String userId, ActionType type) {}

    public ActionService(PolicyEngine policy, ActionExecutor executor, OtpSender otpSender, HashChainAuditLog audit,
                         Clock clock, Duration actionTtl, Duration velocityWindow, int maxOtpAttempts) {
        this(policy, executor, otpSender, audit, clock, actionTtl, velocityWindow, maxOtpAttempts, null);
    }

    public ActionService(PolicyEngine policy, ActionExecutor executor, OtpSender otpSender, HashChainAuditLog audit,
                         Clock clock, Duration actionTtl, Duration velocityWindow, int maxOtpAttempts,
                         CardFreezeReceiptStore freezeReceipts) {
        this.policy = policy;
        this.executor = executor;
        this.otpSender = otpSender;
        this.audit = audit;
        this.clock = clock;
        this.actionTtl = actionTtl;
        this.velocityWindow = velocityWindow;
        this.maxOtpAttempts = maxOtpAttempts;
        this.freezeReceipts = freezeReceipts;
    }

    public synchronized ActionView prepare(String userId, ActionType type, Map<String, Object> params, String idempotencyKey) {
        if (userId == null || userId.isBlank()) throw new ActionException(ActionException.Code.INVALID_REQUEST, "사용자 정보가 없습니다.");
        if (type == null) throw new ActionException(ActionException.Code.INVALID_REQUEST, "허용되지 않은 액션입니다.");
        Map<String, Object> safeParams;
        try {
            safeParams = params == null ? Map.of() : Map.copyOf(params);
        } catch (NullPointerException invalid) {
            throw new ActionException(ActionException.Code.INVALID_REQUEST, "파라미터에 빈 값을 보낼 수 없습니다.");
        }
        Instant now = clock.instant();
        purgeOld(now);
        IdempotencyScope scope = idempotencyKey == null || idempotencyKey.isBlank()
                ? null : new IdempotencyScope(userId, idempotencyKey);
        if (scope != null) {
            if (freezeReceipts != null) {
                var receipt = freezeReceipts.findByKey(userId, idempotencyKey);
                if (receipt.isPresent()) {
                    return replay(receipt.get(), freezeReceipts.fingerprint(type, safeParams));
                }
            }
            String existingId = idempotencyKeys.get(scope);
            if (existingId != null) {
                PendingAction existing = actions.get(existingId);
                if (existing != null) {
                    if (existing.type != type || !existing.params.equals(safeParams)) {
                        throw keyConflict();
                    }
                    return viewAt(existing, now);
                }
            }
        }

        Long amountKrw = amountFor(type, safeParams);
        int recent = recordAttempt(userId, type, now);
        PolicyDecision decision = policy.evaluate(new ActionContext(userId, type, amountKrw, now, recent));

        var action = new PendingAction(UUID.randomUUID().toString(), userId, type, safeParams, decision,
                now.plus(actionTtl), scope == null ? null : scope.key());
        switch (decision.outcome()) {
            case DENY -> action.status = ActionStatus.DENIED;
            case STEP_UP -> {
                String code = String.format("%06d", random.nextInt(1_000_000));
                action.otpHash = otpHash(action.id, code);
                action.status = ActionStatus.AWAITING_OTP;
                otpSender.send(userId, action.id, code);
            }
            case ALLOW -> action.status = ActionStatus.AWAITING_CONFIRM;
        }
        var details = new LinkedHashMap<String, Object>();
        details.put("type", type.name());
        details.put("decision", decision.outcome().name());
        details.put("rules", String.join(",", decision.findings().stream().map(PolicyFinding::ruleId).toList()));
        if (amountKrw != null) details.put("amountKrw", amountKrw);
        audit.append(decision.outcome() == PolicyOutcome.DENY ? "ACTION_DENIED" : "ACTION_PREPARED", userId, action.id, details);
        actions.put(action.id, action);
        if (scope != null) idempotencyKeys.put(scope, action.id);
        return action.view();
    }

    public ActionView confirm(String userId, String actionId, String otp) {
        var stored = storedReceipt(userId, actionId);
        if (stored.isPresent()) {
            return confirmedResult(storedResult(stored.get()));
        }
        PendingAction action = find(userId, actionId);
        synchronized (action) {
            expireIfPending(action, clock.instant());
            switch (action.status) {
                case EXECUTED -> { return action.view(); } // 재요청은 같은 결과 반환, 재실행 안 함
                case DENIED -> throw new ActionException(ActionException.Code.DENIED, String.join(" ", action.decision.reasons()));
                case LOCKED -> throw new ActionException(ActionException.Code.LOCKED, "인증에 여러 번 실패해 잠긴 요청입니다. 처음부터 다시 진행해주세요.");
                case EXPIRED -> throw new ActionException(ActionException.Code.EXPIRED, "확인 시간이 지났습니다. 다시 요청해주세요.");
                case FAILED -> throw executionFailed();
                default -> { }
            }
            boolean needsOtp = action.status == ActionStatus.AWAITING_OTP;
            if (needsOtp) verifyOtp(action, otp);
            String fingerprint = null;
            if (action.type == ActionType.CARD_FREEZE_ALL && freezeReceipts != null) {
                fingerprint = freezeReceipts.fingerprint(action.type, action.params);
                if (!freezeReceipts.reserve(userId, action.id, action.idempotencyKey, fingerprint)) {
                    var receipt = freezeReceipts.findById(userId, action.id)
                            .or(() -> freezeReceipts.findByKey(userId, action.idempotencyKey));
                    if (receipt.isEmpty()) throw executionInProgress();
                    return confirmedResult(replay(receipt.get(), fingerprint));
                }
            }
            if (needsOtp) {
                clearOtp(action);
                audit.append("OTP_PASSED", userId, action.id, Map.of());
            }

            try {
                action.result = Map.copyOf(executor.execute(action.type, userId, action.params));
            } catch (RuntimeException e) {
                action.status = ActionStatus.FAILED;
                audit.append("ACTION_FAILED", userId, action.id, Map.of("type", action.type.name(), "error", e.getClass().getSimpleName()));
                saveReceipt(action, fingerprint);
                throw new ActionException(ActionException.Code.EXECUTION_FAILED, "금융 시스템 처리 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.");
            }
            action.status = ActionStatus.EXECUTED;
            audit.append("ACTION_EXECUTED", userId, action.id, Map.of("type", action.type.name()));
            saveReceipt(action, fingerprint);
            return action.view();
        }
    }

    public ActionView get(String userId, String actionId) {
        var receipt = storedReceipt(userId, actionId);
        if (receipt.isPresent()) return storedResult(receipt.get());
        return viewAt(find(userId, actionId), clock.instant());
    }

    private Optional<CardFreezeReceiptStore.Receipt> storedReceipt(String userId, String actionId) {
        if (freezeReceipts == null || userId == null || userId.isBlank() || actionId == null) return Optional.empty();
        var local = actions.get(actionId);
        if (local != null && local.type != ActionType.CARD_FREEZE_ALL) return Optional.empty();
        return freezeReceipts.findById(userId, actionId);
    }

    private void saveReceipt(PendingAction action, String fingerprint) {
        if (fingerprint != null) {
            freezeReceipts.complete(action.userId, action.idempotencyKey,
                    new CardFreezeReceiptStore.Receipt(fingerprint, action.view()));
        }
    }

    private static ActionView replay(CardFreezeReceiptStore.Receipt receipt, String fingerprint) {
        if (!receipt.fingerprint().equals(fingerprint)) throw keyConflict();
        return storedResult(receipt);
    }

    private static ActionView storedResult(CardFreezeReceiptStore.Receipt receipt) {
        if (receipt.result() == null) throw executionInProgress();
        return receipt.result();
    }

    private static ActionView confirmedResult(ActionView view) {
        if (view.status() == ActionStatus.FAILED) throw executionFailed();
        return view;
    }

    private static ActionException keyConflict() {
        return new ActionException(ActionException.Code.IDEMPOTENCY_CONFLICT, "같은 요청 키로 다른 액션 또는 파라미터를 보냈습니다.");
    }

    private static ActionException executionInProgress() {
        return new ActionException(ActionException.Code.EXECUTION_IN_PROGRESS, "이미 실행 요청을 받았습니다. 같은 요청으로 결과를 다시 확인해주세요.");
    }

    private static ActionException executionFailed() {
        return new ActionException(ActionException.Code.EXECUTION_FAILED, "실행에 실패한 요청입니다. 다시 요청해주세요.");
    }

    private ActionView viewAt(PendingAction action, Instant now) {
        synchronized (action) {
            expireIfPending(action, now);
            return action.view();
        }
    }

    private void expireIfPending(PendingAction action, Instant now) {
        if (now.isBefore(action.expiresAt)
                || (action.status != ActionStatus.AWAITING_OTP && action.status != ActionStatus.AWAITING_CONFIRM)) return;
        action.status = ActionStatus.EXPIRED;
        clearOtp(action);
        audit.append("ACTION_EXPIRED", action.userId, action.id, Map.of("type", action.type.name()));
    }

    private void clearOtp(PendingAction action) {
        action.otpHash = null;
        otpSender.discard(action.id);
    }

    private void verifyOtp(PendingAction action, String otp) {
        if (otp == null || otp.isBlank()) {
            throw new ActionException(ActionException.Code.OTP_REQUIRED, "인증번호를 입력해주세요.", maxOtpAttempts - action.otpFailures);
        }
        boolean ok = MessageDigest.isEqual(
                action.otpHash.getBytes(StandardCharsets.UTF_8),
                otpHash(action.id, otp.trim()).getBytes(StandardCharsets.UTF_8));
        if (ok) return;
        action.otpFailures++;
        audit.append("OTP_FAILED", action.userId, action.id, Map.of("failures", action.otpFailures));
        if (action.otpFailures >= maxOtpAttempts) {
            action.status = ActionStatus.LOCKED;
            clearOtp(action);
            audit.append("ACTION_LOCKED", action.userId, action.id, Map.of("type", action.type.name()));
            throw new ActionException(ActionException.Code.LOCKED, "인증에 여러 번 실패해 잠겼어요. 처음부터 다시 진행해주세요.", 0);
        }
        throw new ActionException(ActionException.Code.OTP_MISMATCH, "인증번호가 맞지 않아요.", maxOtpAttempts - action.otpFailures);
    }

    private PendingAction find(String userId, String actionId) {
        PendingAction action = actionId == null ? null : actions.get(actionId);
        // 다른 사용자의 액션은 존재 여부도 알려주지 않는다
        if (action == null || !action.userId.equals(userId)) {
            throw new ActionException(ActionException.Code.NOT_FOUND, "요청을 찾을 수 없습니다.");
        }
        return action;
    }

    private static Long amountFor(ActionType type, Map<String, Object> params) {
        if (type != ActionType.TRAVEL_CARD_CHARGE) return null;
        Object raw = params.get("amountKrw");
        if (raw instanceof Number n) {
            try {
                return new BigDecimal(n.toString()).longValueExact();
            } catch (ArithmeticException | NumberFormatException invalid) {
                // 소수, 범위를 벗어난 금액, 비유한 수는 요청 오류로 처리한다.
            }
        }
        throw new ActionException(ActionException.Code.INVALID_REQUEST, "충전 금액(amountKrw)을 원 단위 정수로 보내주세요.");
    }

    private int recordAttempt(String userId, ActionType type, Instant now) {
        var history = attempts.computeIfAbsent(new AttemptScope(userId, type), ignored -> new ArrayDeque<>());
        trimAttempts(history, now.minus(velocityWindow));
        history.addLast(now);
        return history.size();
    }

    private static void trimAttempts(Deque<Instant> history, Instant from) {
        while (!history.isEmpty() && history.peekFirst().isBefore(from)) history.pollFirst();
    }

    /** 준비 요청이 들어올 때 만료된 기록을 한 번씩 정리한다. */
    private void purgeOld(Instant now) {
        if (now.isBefore(nextCleanupAt)) return;
        nextCleanupAt = now.plusSeconds(30);
        Instant cutoff = now.minus(actionTtl.multipliedBy(12));
        actions.values().removeIf(action -> {
            if (!now.isBefore(action.expiresAt)) otpSender.discard(action.id);
            return action.expiresAt.isBefore(cutoff);
        });
        idempotencyKeys.values().removeIf(id -> !actions.containsKey(id));
        Instant attemptsFrom = now.minus(velocityWindow);
        attempts.values().removeIf(history -> {
            trimAttempts(history, attemptsFrom);
            return history.isEmpty();
        });
    }

    private static String otpHash(String actionId, String code) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest((actionId + ":" + code).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    private static final class PendingAction {
        final String id;
        final String userId;
        final ActionType type;
        final Map<String, Object> params;
        final PolicyDecision decision;
        final Instant expiresAt;
        final String idempotencyKey;
        ActionStatus status;
        String otpHash;
        int otpFailures;
        Map<String, Object> result;

        PendingAction(String id, String userId, ActionType type, Map<String, Object> params,
                      PolicyDecision decision, Instant expiresAt, String idempotencyKey) {
            this.id = id;
            this.userId = userId;
            this.type = type;
            this.params = params;
            this.decision = decision;
            this.expiresAt = expiresAt;
            this.idempotencyKey = idempotencyKey;
        }

        synchronized ActionView view() {
            return new ActionView(id, type, type.label(), status, decision.outcome(), decision.reasons(),
                    status == ActionStatus.AWAITING_OTP, expiresAt, result);
        }
    }
}
