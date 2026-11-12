package com.example.kb_ai_backend.action;

/** 규칙 하나가 내린 판단과 그 이유 (사용자 안내·감사 로그에 그대로 쓰인다) */
public record PolicyFinding(String ruleId, PolicyOutcome outcome, String reason) {}
