package com.example.kb_ai_backend.service;

import com.example.kb_ai_backend.feedback.FeedbackEvent;
import com.example.kb_ai_backend.feedback.FeedbackRanker;
import com.example.kb_ai_backend.session.InMemorySessionStore;
import com.example.kb_ai_backend.trace.TraceStore;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class JevCanvasRankingTest {

    @SuppressWarnings("unchecked")
    @Test void preferredWidgetIsShownFirstAndExposureIsRecorded() {
        var selector = mock(WidgetSelectionExperimentService.class);
        var data = mock(WidgetDataService.class);
        when(data.buildWidget(anyString(), any(), any(), any(), any(), any()))
                .thenAnswer(call -> Map.of("type", call.getArgument(0)));
        var ranker = new FeedbackRanker(WidgetSelectionExperimentService.WIDGETS.keySet(), 5);
        for (int i = 0; i < 10; i++) {
            ranker.record("id_reissue_status_widget", FeedbackEvent.SHOWN);
            ranker.record("id_reissue_status_widget", FeedbackEvent.CLICKED);
            ranker.record("card_freeze_all", FeedbackEvent.SHOWN);
        }
        var clock = Clock.systemUTC();
        var service = new JevCanvasService(selector, new CanvasParameters(), data,
                new InMemorySessionStore(clock, Duration.ofMinutes(30), 10), new TraceStore(clock, Duration.ofHours(1), 10), ranker, clock);
        var ids = List.of("card_freeze_all", "atm_smart_withdrawal", "id_reissue_status_widget");
        when(selector.select("지갑을 잃어버렸어", "jev")).thenReturn(new WidgetSelectionExperimentService.Result(
                "jev", "t", "s", ids, Map.of(), false, 200, 1L, 1L));

        var response = service.compose("지갑을 잃어버렸어");

        var types = ((List<Map<String, Object>>) response.get("widgets")).stream().map(w -> w.get("type")).toList();
        assertEquals(List.of("id_reissue_status_widget", "atm_smart_withdrawal", "card_freeze_all"), types);
        assertEquals(1, ranker.stats("atm_smart_withdrawal").shown());
        assertEquals(11, ranker.stats("card_freeze_all").shown());
    }
}
