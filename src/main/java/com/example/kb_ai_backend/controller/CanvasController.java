package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.OpenAiApiService;
import com.example.kb_ai_backend.service.WidgetDataService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/canvas")
@CrossOrigin(origins = "*")
public class CanvasController {

    private final OpenAiApiService openAiApiService;
    private final WidgetDataService widgetDataService;

    public CanvasController(OpenAiApiService openAiApiService, WidgetDataService widgetDataService) {
        this.openAiApiService = openAiApiService;
        this.widgetDataService = widgetDataService;
    }

    public record CanvasRequest(String message) {}

    @PostMapping
    public Map<String, Object> generateCanvas(@RequestBody CanvasRequest request) {

        List<String> widgetIds = openAiApiService.selectWidgets(request.message());

        List<Map<String, Object>> widgets = widgetIds.stream()
                .map(widgetDataService::buildWidget)
                .collect(Collectors.toList());

        return Map.of("widgets", widgets);
    }
}