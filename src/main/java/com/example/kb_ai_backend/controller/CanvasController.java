package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.JevCanvasService;
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

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> error(ResponseStatusException error) {
        return ResponseEntity.status(error.getStatusCode()).body(Map.of(
                "status", error.getStatusCode().value(), "error", error.getReason()));
    }
}
