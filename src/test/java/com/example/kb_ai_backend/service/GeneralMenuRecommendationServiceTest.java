package com.example.kb_ai_backend.service;
import org.junit.jupiter.api.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
class GeneralMenuRecommendationServiceTest {
    @Test void masksBeforePlannerAndSelectorAndReportsHybridHonestly(){var planner=mock(MenuTaskPlanner.class);var selector=mock(PlannedMenuSelector.class);var plan=new PlannedMenuSelector.Plan("no_match",List.of());when(planner.plan(anyString())).thenReturn(new MenuTaskPlanner.Planning(plan,10));when(selector.select(anyString(),eq(plan))).thenReturn(new PlannedMenuSelector.Selection("no_match",List.of(),List.of(),Map.of(),0,0,0));var service=new GeneralMenuRecommendationService(planner,selector);var r=service.compose("010-1234-5678 요리");verify(planner).plan("[민감정보] 요리");verify(selector).select("[민감정보] 요리",plan);assertEquals("llm_planner_e5_jev",r.metrics().retrievalMode());assertEquals(0,r.metrics().jevCalls());}
}
