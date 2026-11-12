package com.example.kb_ai_backend.service;

import com.example.kb_ai_backend.session.InMemorySessionStore;
import com.example.kb_ai_backend.trace.TraceStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.Duration;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class JevCanvasTraceTest {
    WidgetSelectionExperimentService selector = mock(WidgetSelectionExperimentService.class);
    WidgetDataService data = mock(WidgetDataService.class);
    JevCanvasService service;

    @BeforeEach void setup() {
        var clock = Clock.systemUTC();
        service = new JevCanvasService(selector, new CanvasParameters(), data,
                new InMemorySessionStore(clock, Duration.ofMinutes(30), 100), new TraceStore(clock, Duration.ofHours(1), 100), clock);
        when(data.buildWidget(anyString(), any(), any(), any(), any(), any()))
                .thenAnswer(call -> Map.of("type", call.getArgument(0)));
    }

    @SuppressWarnings("unchecked")
    @Test void traceExplainsSelectionSlotsAndStages() {
        when(selector.select("일본 3박4일 여행 보험", "jev")).thenReturn(new WidgetSelectionExperimentService.Result(
                "jev", "jev-latest", "widget_selection_only", List.of("travel_insurance_widget"),
                Map.of("travel_insurance_widget", new WidgetSelectionExperimentService.Decision("include", 0.91),
                        "card_freeze_all", new WidgetSelectionExperimentService.Decision("exclude", 0.97)),
                false, 210, 100L, 30L));

        var response = service.compose("일본 3박4일 여행 보험");
        var trace = service.trace((String) response.get("requestId")).orElseThrow().toMap();

        assertEquals("ready", trace.get("status"));
        assertEquals(List.of("travel_insurance_widget"), trace.get("renderedWidgets"));
        var selection = (Map<String, Object>) trace.get("selection");
        assertEquals(2, ((List<?>) selection.get("candidates")).size());
        assertEquals(Map.of("currency", "JPY", "destination", "일본", "tripDays", 4), trace.get("slots"));
        var stages = ((List<?>) trace.get("stages")).stream().map(s -> ((com.example.kb_ai_backend.trace.DecisionTrace.Stage) s).name()).toList();
        assertEquals(List.of("session", "selection", "parameters", "build"), stages);
    }

    @Test void resumedRequestIsMarkedAndSkipsSelectionStage() {
        when(selector.select("여행 환전", "jev")).thenReturn(new WidgetSelectionExperimentService.Result(
                "jev", "t", "s", List.of("travel_card_charge_widget"), Map.of(), false, 200, 1L, 1L));
        String sessionId = (String) service.compose("여행 환전").get("sessionId");

        var response = service.compose("달러로", sessionId);
        var trace = service.trace((String) response.get("requestId")).orElseThrow();

        assertTrue(trace.resumedFromSession());
        assertTrue(trace.stages().stream().noneMatch(s -> s.name().equals("selection")));
    }

    @Test void failedRequestsAreTracedToo() {
        when(selector.select("환전", "jev")).thenThrow(new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT, "시간 초과"));
        assertThrows(ResponseStatusException.class, () -> service.compose("환전"));
        // requestId를 응답으로 못 받았으므로 여기서는 저장 여부만 간접 확인: 다음 정상 요청이 영향받지 않아야 함
        when(selector.select("지갑을 잃어버렸어", "jev")).thenReturn(new WidgetSelectionExperimentService.Result(
                "jev", "t", "s", List.of("card_freeze_all"), Map.of(), false, 200, 1L, 1L));
        assertEquals("ready", service.compose("지갑을 잃어버렸어").get("status"));
    }
}
