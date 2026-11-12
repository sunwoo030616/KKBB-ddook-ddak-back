package com.example.kb_ai_backend.action.rules;

import com.example.kb_ai_backend.action.*;

import java.text.NumberFormat;
import java.util.Locale;
import java.util.Optional;

/** 원화 환산 금액 기준: stepUpKrw 초과면 추가 인증, denyKrw 초과면 차단 */
public class AmountLimitRule implements PolicyRule {

    private final long stepUpKrw;
    private final long denyKrw;

    public AmountLimitRule(long stepUpKrw, long denyKrw) {
        if (stepUpKrw <= 0 || denyKrw < stepUpKrw) throw new IllegalArgumentException("0 < stepUpKrw <= denyKrw 이어야 합니다.");
        this.stepUpKrw = stepUpKrw;
        this.denyKrw = denyKrw;
    }

    @Override
    public String id() { return "amount-limit"; }

    @Override
    public Optional<PolicyFinding> evaluate(ActionContext context) {
        Long amount = context.amountKrw();
        if (amount == null) return Optional.empty();
        if (amount <= 0) {
            return Optional.of(new PolicyFinding(id(), PolicyOutcome.DENY, "금액이 올바르지 않아요."));
        }
        if (amount > denyKrw) {
            return Optional.of(new PolicyFinding(id(), PolicyOutcome.DENY,
                    "1회 한도 " + won(denyKrw) + "을 넘어 앱에서 처리할 수 없어요."));
        }
        if (amount > stepUpKrw) {
            return Optional.of(new PolicyFinding(id(), PolicyOutcome.STEP_UP,
                    won(stepUpKrw) + "을 넘는 금액이라 추가 인증이 필요해요."));
        }
        return Optional.empty();
    }

    private static String won(long amount) {
        return NumberFormat.getNumberInstance(Locale.KOREA).format(amount) + "원";
    }
}
