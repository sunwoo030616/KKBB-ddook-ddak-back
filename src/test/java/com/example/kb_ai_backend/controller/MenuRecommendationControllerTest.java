package com.example.kb_ai_backend.controller;
import com.example.kb_ai_backend.service.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class MenuRecommendationControllerTest {
    @Test void returnsMenuBundleAndRejectsBlankInput() throws Exception {
        var service=mock(SemanticMenuRecommendationService.class);var catalog=new MenuCatalog(new ObjectMapper());
        var menu=catalog.find("kb_menu_0323");
        when(service.compose("일본 여행")).thenReturn(new SemanticMenuRecommendationService.Result("ready",
            List.of(new SemanticMenuRecommendationService.Recommendation(menu,"foreign_exchange","환전","suggested","상황 제안")),
            new SemanticMenuRecommendationService.Metrics("semantic_only",10,10,10,2)));
        var mvc=MockMvcBuilders.standaloneSetup(new MenuRecommendationController(service,catalog)).build();
        mvc.perform(post("/api/menus/recommend").contentType("application/json").content("{\"message\":\"일본 여행\"}"))
           .andExpect(status().isOk()).andExpect(jsonPath("$.menus[0].id").value("kb_menu_0323"))
           .andExpect(jsonPath("$.catalogSha256").value(catalog.sha256()));
        mvc.perform(post("/api/menus/recommend").contentType("application/json").content("{\"message\":\" \"}"))
           .andExpect(status().isBadRequest());
    }
}
