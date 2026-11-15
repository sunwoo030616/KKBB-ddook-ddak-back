package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.SemanticMenuSelectionService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.Map;

@RestController
@RequestMapping("/api/menus/select")
public class MenuSelectionController {
    private final SemanticMenuSelectionService service;
    public MenuSelectionController(SemanticMenuSelectionService service) { this.service = service; }
    public record Request(String message) {}
    @PostMapping
    public SemanticMenuSelectionService.Result select(@RequestBody Request request) {
        return service.select(request == null ? null : request.message());
    }
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> error(ResponseStatusException error) {
        return ResponseEntity.status(error.getStatusCode()).body(Map.of("status", error.getStatusCode().value(), "error", error.getReason()));
    }
}
