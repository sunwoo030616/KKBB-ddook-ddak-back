package com.example.kb_ai_backend.action;

import java.security.SecureRandom;
import java.time.Clock;
import java.util.List;
import java.util.Map;

/** 개발·시연용 모의 실행기. 실제 카드사·계좌 API를 부르지 않는다. */
public class MockActionExecutor implements ActionExecutor {

    private static final List<String> DEMO_CARDS = List.of("KB국민 노리2 체크카드", "톡톡카드");
    private final SecureRandom random = new SecureRandom();
    private final Clock clock;

    public MockActionExecutor(Clock clock) {
        this.clock = clock;
    }

    @Override
    public Map<String, Object> execute(ActionType type, String userId, Map<String, Object> params) {
        String at = clock.instant().toString();
        return switch (type) {
            case CARD_FREEZE_ALL -> Map.of("frozenCards", DEMO_CARDS, "frozenAt", at);
            case CARD_UNFREEZE_ALL -> Map.of("unfrozenCards", DEMO_CARDS, "unfrozenAt", at);
            case SMART_WITHDRAWAL_CODE -> Map.of(
                    "authCode", String.format("%06d", random.nextInt(1_000_000)),
                    "expiresInSeconds", 1800, "issuedAt", at);
            case TRAVEL_CARD_CHARGE -> Map.of(
                    "chargedKrw", params.getOrDefault("amountKrw", 0),
                    "currency", params.getOrDefault("currency", "-"), "chargedAt", at);
        };
    }
}
