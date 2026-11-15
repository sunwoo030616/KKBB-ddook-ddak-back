package com.example.kb_ai_backend.controller;
import com.example.kb_ai_backend.service.SemanticMenuSelectionService;
import org.junit.jupiter.api.Test;
import org.springframework.http.*;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
class MenuSelectionControllerTest {
    @Test void exposesMenuPipelineAndPreservesSearchFailure() throws Exception {
        var service=mock(SemanticMenuSelectionService.class);
        when(service.select("환전")).thenReturn(new SemanticMenuSelectionService.Result("no_match",List.of(),List.of("kb_menu_0323"),.99,"e5_jev","digest",10,100,1));
        when(service.select("분실")).thenThrow(new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"검색 서버 확인 필요"));
        var mvc=MockMvcBuilders.standaloneSetup(new MenuSelectionController(service)).build();
        mvc.perform(post("/api/menus/select").contentType(MediaType.APPLICATION_JSON).content("{\"message\":\"환전\"}"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.pipeline").value("e5_jev")).andExpect(jsonPath("$.jevCalls").value(1));
        mvc.perform(post("/api/menus/select").contentType(MediaType.APPLICATION_JSON).content("{\"message\":\"분실\"}"))
                .andExpect(status().isServiceUnavailable()).andExpect(jsonPath("$.error").value("검색 서버 확인 필요"));
    }
}
