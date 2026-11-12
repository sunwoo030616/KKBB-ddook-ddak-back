package com.example.kb_ai_backend.feedback;

public enum FeedbackEvent {
    SHOWN,      // 화면에 노출됨 (서버가 자동 기록)
    CLICKED,    // 위젯을 눌러 사용함
    COMPLETED,  // 위젯 안의 업무를 끝까지 마침 (충전·정지 완료 등)
    DISMISSED   // 닫거나 숨김
}
