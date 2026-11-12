package com.example.kb_ai_backend;

import com.example.kb_ai_backend.service.WidgetDataService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = "app.action.demo-enabled=true")
@AutoConfigureMockMvc
class DemoActionApplicationTests {
    @Autowired MockMvc mvc;
    @Autowired WidgetDataService widgets;

    @Test void demoModeRegistersMockActionsAndWidgetMetadata() throws Exception {
        assertTrue(widgets.buildWidget("card_freeze_all").containsKey("action"));
        mvc.perform(post("/api/actions").contentType("application/json")
                        .content("""
                                {"type":"CARD_FREEZE_ALL"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("AWAITING_CONFIRM"));
        mvc.perform(get("/api/audit/verify"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.valid").value(true));
    }
}
