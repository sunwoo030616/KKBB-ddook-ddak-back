package com.example.kb_ai_backend.action.rules;

import com.example.kb_ai_backend.action.*;

import java.time.ZoneId;
import java.util.Optional;

/** 심야 시간대(startHour 이상 ~ endHour 미만)의 비보호성 액션은 추가 인증 */
public class NightTimeRule implements PolicyRule {

    private final ZoneId zone;
    private final int startHour;
    private final int endHour;

    public NightTimeRule(ZoneId zone, int startHour, int endHour) {
        if (startHour < 0 || startHour > 23 || endHour < 0 || endHour > 23) throw new IllegalArgumentException("시간은 0~23");
        this.zone = zone;
        this.startHour = startHour;
        this.endHour = endHour;
    }

    @Override
    public String id() { return "night-time"; }

    @Override
    public Optional<PolicyFinding> evaluate(ActionContext context) {
        if (context.type().risk() == RiskLevel.PROTECTIVE) return Optional.empty();
        int hour = context.at().atZone(zone).getHour();
        boolean night = startHour <= endHour
                ? hour >= startHour && hour < endHour
                : hour >= startHour || hour < endHour; // 예: 23시~5시처럼 자정을 넘는 구간
        if (!night) return Optional.empty();
        return Optional.of(new PolicyFinding(id(), PolicyOutcome.STEP_UP,
                "심야 시간(" + startHour + "시~" + endHour + "시) 요청이라 추가 인증이 필요해요."));
    }
}
