package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.JevCanvasService;
import com.example.kb_ai_backend.trace.DecisionTrace;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/canvas")
public class CanvasController {

    private final JevCanvasService canvas;

    public CanvasController(JevCanvasService canvas) {
        this.canvas = canvas;
    }

    public record CanvasRequest(String message, String sessionId) {}

    @PostMapping
    public Map<String, Object> generateCanvas(@RequestBody CanvasRequest request) {

        if (request == null) return canvas.compose(null);
        // sessionId가 있으면 이전 대화(되묻기)를 이어서 처리한다
        return request.sessionId() == null
                ? canvas.compose(request.message())
                : canvas.compose(request.message(), request.sessionId());
    }

    /** 화면이 왜 이렇게 구성됐는지: 위젯별 판정·신뢰도, 슬롯, 되묻기 여부, 단계별 지연 */
    @GetMapping("/{requestId}/trace")
    public Map<String, Object> trace(@PathVariable String requestId) {
        return canvas.trace(requestId)
                .map(DecisionTrace::toMap)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "트레이스를 찾을 수 없습니다. (보관 기간 1시간)"));
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> error(ResponseStatusException error) {
        return ResponseEntity.status(error.getStatusCode()).body(Map.of(
                "status", error.getStatusCode().value(), "error", error.getReason()));
    }
}
