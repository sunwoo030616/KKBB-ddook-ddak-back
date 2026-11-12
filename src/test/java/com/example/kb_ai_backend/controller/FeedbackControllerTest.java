package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.feedback.FeedbackRanker;
import com.example.kb_ai_backend.trace.DecisionTrace;
import com.example.kb_ai_backend.trace.TraceStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.Clock;
import java.time.Duration;
import java.util.List;
import java.util.Set;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class FeedbackControllerTest {
    private MockMvc mvc;

    @BeforeEach void setUp() {
        var ranker = new FeedbackRanker(Set.of("card_freeze_all", "travel_insurance_widget"), 0);
        Clock clock = Clock.systemUTC();
        var traces = new TraceStore(clock, Duration.ofHours(1), 20);
        var trace = new DecisionTrace("shown-request", clock.instant(), 10);
        trace.finish("ready", List.of("card_freeze_all"));
        traces.save(trace);
        mvc = MockMvcBuilders.standaloneSetup(new FeedbackController(ranker, traces)).build();
    }

    @Test void countsTheSameEventOnlyOnceForARenderedWidget() throws Exception {
        for (int attempt = 0; attempt < 2; attempt++) {
            mvc.perform(post("/api/feedback").contentType("application/json")
                            .content(event("card_freeze_all", "clicked", "shown-request")))
                    .andExpect(status().isAccepted())
                    .andExpect(jsonPath("$.score").isNumber());
        }
        mvc.perform(get("/api/feedback/scores"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.card_freeze_all.clicked").value(1));
    }

    @Test void rejectsUnknownRequestsUnshownWidgetsAndServerOnlyEvents() throws Exception {
        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content(event("card_freeze_all", "CLICKED", "unknown-request")))
                .andExpect(status().isNotFound());
        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content(event("travel_insurance_widget", "CLICKED", "shown-request")))
                .andExpect(status().isBadRequest());
        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content(event("card_freeze_all", "SHOWN", "shown-request")))
                .andExpect(status().isBadRequest());
    }

    private static String event(String widget, String event, String requestId) {
        return """
                {"widgetType":"%s","event":"%s","requestId":"%s"}
                """.formatted(widget, event, requestId);
    }
}
