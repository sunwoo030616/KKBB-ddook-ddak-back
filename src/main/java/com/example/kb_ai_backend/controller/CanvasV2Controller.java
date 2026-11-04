package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.CanvasComposerClient;
import com.example.kb_ai_backend.service.CanvasWidgetDataAdapter;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/canvas/v2")
public class CanvasV2Controller {
    private final CanvasComposerClient composer;

    private final CanvasWidgetDataAdapter data;
    public CanvasV2Controller(CanvasComposerClient composer, CanvasWidgetDataAdapter data) { this.composer = composer; this.data=data; }
    private ResponseEntity<?> enrich(ResponseEntity<?> response) {
        if(response.getBody() instanceof JsonNode json && response.getStatusCode().is2xxSuccessful())
            return ResponseEntity.status(response.getStatusCode()).body(data.enrich(json));
        return response;
    }

    @GetMapping("/health")
    public java.util.Map<String,String> health() { return java.util.Map.of("status", "ok", "service", "canvas-v2"); }

    @PostMapping
    public ResponseEntity<?> compose(@RequestBody JsonNode request) { return enrich(composer.compose(request)); }
    @PostMapping("/jobs")
    public ResponseEntity<?> submitJob(@RequestBody JsonNode request) { return composer.submitJob(request); }

    @GetMapping("/jobs/{jobId:[a-f0-9-]{36}}")
    public ResponseEntity<?> jobStatus(@PathVariable String jobId) { return enrich(composer.jobStatus(jobId)); }
}

