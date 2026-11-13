package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.feedback.FeedbackEvent;
import com.example.kb_ai_backend.feedback.FeedbackRanker;
import com.example.kb_ai_backend.trace.TraceStore;
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

    private final TraceStore traces;

    public FeedbackController(FeedbackRanker ranker, TraceStore traces) {
        this.ranker = ranker;
        this.traces = traces;
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
        if (request.requestId() == null || request.requestId().isBlank()
                || request.widgetType() == null || !ranker.supports(request.widgetType())) {
            return ResponseEntity.badRequest().body(Map.of("error", "requestId와 지원하는 widgetType이 필요합니다."));
        }
        var trace = traces.find(request.requestId());
        if (trace.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", "화면 요청을 찾을 수 없습니다."));
        }
        if (!trace.get().containsRenderedWidget(request.widgetType())) {
            return ResponseEntity.badRequest().body(Map.of("error", "이 화면에 표시된 위젯만 기록할 수 있습니다."));
        }
        trace.get().recordFeedbackOnce(request.widgetType(), event,
                () -> ranker.record(request.widgetType(), event));
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(Map.of("widgetType", request.widgetType(), "score", ranker.score(request.widgetType())));
    }

    @GetMapping("/scores")
    public Map<String, FeedbackRanker.Stats> scores() {
        return ranker.snapshot();
    }
}
