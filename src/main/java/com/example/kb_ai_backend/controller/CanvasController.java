package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.OpenAiApiService;
import com.example.kb_ai_backend.service.WidgetDataService;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/canvas")
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

        // 방어 코드: message가 없거나 빈 값이면 OpenAI 호출 없이 바로 빈 응답 반환
        String userMessage = request == null ? null : request.message();
        if (userMessage == null || userMessage.isBlank()) {
            return Map.of(
                    "greeting", "무엇을 도와드릴까요?",
                    "widgets", List.of()
            );
        }

        OpenAiApiService.WidgetSelection selection = openAiApiService.selectWidgets(userMessage);

        List<Map<String, Object>> widgets = selection.widgets().stream()
                .map(widgetId -> widgetDataService.buildWidget(
                        widgetId, selection.currency(), selection.destination(),
                        selection.requestedAmount(), selection.clubName(), selection.tripDays()))
                .collect(Collectors.toList());

        String greeting = widgetDataService.buildGreeting(
                selection.widgets(), selection.destination(), selection.clubName());

        return Map.of(
                "greeting", greeting,
                "widgets", widgets
        );
    }
}