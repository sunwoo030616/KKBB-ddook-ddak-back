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

        OpenAiApiService.WidgetSelection selection = openAiApiService.selectWidgets(request.message());

        List<Map<String, Object>> widgets = selection.widgets().stream()
                .map(widgetId -> widgetDataService.buildWidget(
                        widgetId, selection.currency(), selection.destination(),
                        selection.requestedAmount(), selection.clubName()))
                .collect(Collectors.toList());

        String greeting = widgetDataService.buildGreeting(
                selection.widgets(), selection.destination(), selection.clubName());

        return Map.of(
                "greeting", greeting,
                "widgets", widgets
        );
    }
}