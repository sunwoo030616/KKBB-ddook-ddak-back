package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.feedback.FeedbackEvent;
import com.example.kb_ai_backend.feedback.FeedbackRanker;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Locale;
import java.util.Map;

/** 프론트가 위젯 클릭·완료·닫기를 보내는 API. 노출(SHOWN)은 서버가 화면 생성 시 자동으로 기록한다. */
@RestController
@RequestMapping("/api/feedback")
public class FeedbackController {

    private final FeedbackRanker ranker;

    public FeedbackController(FeedbackRanker ranker) {
        this.ranker = ranker;
    }

    public record FeedbackRequest(String widgetType, String event, String requestId) {}

    @PostMapping
    public ResponseEntity<Map<String, Object>> record(@RequestBody FeedbackRequest request) {
        FeedbackEvent event;
        try {
            event = FeedbackEvent.valueOf(request.event().trim().toUpperCase(Locale.ROOT));
        } catch (RuntimeException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", "event는 CLICKED, COMPLETED, DISMISSED 중 하나입니다."));
        }
        if (event == FeedbackEvent.SHOWN) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", "노출은 서버가 기록합니다."));
        }
        try {
            ranker.record(request.widgetType(), event);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
        }
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(Map.of("widgetType", request.widgetType(), "score", ranker.score(request.widgetType())));
    }

    @GetMapping("/scores")
    public Map<String, FeedbackRanker.Stats> scores() {
        return ranker.snapshot();
    }
}
