package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.feedback.FeedbackRanker;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.Set;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class FeedbackControllerTest {
    @Test void acceptsUserEventsAndRejectsServerOnlyOrUnknownOnes() throws Exception {
        var ranker = new FeedbackRanker(Set.of("card_freeze_all"), 0);
        var mvc = MockMvcBuilders.standaloneSetup(new FeedbackController(ranker)).build();

        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content("{\"widgetType\":\"card_freeze_all\",\"event\":\"clicked\"}"))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.score").isNumber());
        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content("{\"widgetType\":\"card_freeze_all\",\"event\":\"SHOWN\"}"))
                .andExpect(status().isBadRequest());
        mvc.perform(post("/api/feedback").contentType("application/json")
                        .content("{\"widgetType\":\"unknown_widget\",\"event\":\"CLICKED\"}"))
                .andExpect(status().isBadRequest());
        mvc.perform(get("/api/feedback/scores"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.card_freeze_all.clicked").value(1));
    }
}
