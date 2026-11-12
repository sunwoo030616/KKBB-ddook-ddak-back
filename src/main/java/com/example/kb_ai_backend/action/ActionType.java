package com.example.kb_ai_backend.action;

/** 서버가 실행할 수 있는 금융 액션 목록 (allowlist). 여기에 없는 액션은 요청 자체가 거부된다. */
public enum ActionType {
    CARD_FREEZE_ALL(RiskLevel.PROTECTIVE, "보유 카드 일괄 정지"),
    CARD_UNFREEZE_ALL(RiskLevel.HIGH, "카드 정지 해제"),
    SMART_WITHDRAWAL_CODE(RiskLevel.HIGH, "카드 없는 출금 인증번호 발급"),
    TRAVEL_CARD_CHARGE(RiskLevel.MEDIUM, "트래블 카드 충전");

    private final RiskLevel risk;
    private final String label;

    ActionType(RiskLevel risk, String label) {
        this.risk = risk;
        this.label = label;
    }

    public RiskLevel risk() { return risk; }

    public String label() { return label; }
}
