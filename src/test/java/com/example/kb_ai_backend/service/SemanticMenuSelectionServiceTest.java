package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.http.*;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class SemanticMenuSelectionServiceTest {
    final ObjectMapper mapper = new ObjectMapper();
    MenuCatalog catalog;
    SemanticMenuRetriever retriever;
    MockRestServiceServer server;
    SemanticMenuSelectionService service;
    @BeforeEach void setup() throws Exception {
        catalog = new MenuCatalog(mapper);
        retriever = mock(SemanticMenuRetriever.class);
        var client = new RestTemplate(); server = MockRestServiceServer.createServer(client);
        service = new SemanticMenuSelectionService(retriever, catalog, client, "test-key", "jev-test", 20, 0.6);
        when(retriever.retrieve(anyString(), eq(20))).thenReturn(List.of(catalog.find("kb_menu_0554"), catalog.find("kb_menu_0555")));
    }
    String answer(String id, double confidence) throws Exception {
        return mapper.writeValueAsString(Map.of("answers",Map.of("menu",Map.of("type","choice","choice",id,"confidence",confidence))));
    }
    @Test void searchesBeforeExactlyOneDecisionAndRedactsOutboundRequest() throws Exception {
        server.expect(requestTo("https://api.typesafe.ai/v1/systemone"))
                .andExpect(header("Authorization", "Bearer test-key"))
                .andExpect(jsonPath("$.state.user_request").value("국민카드 분실 [민감정보]"))
                .andExpect(jsonPath("$.state.menu_catalog.length()").value(2))
                .andExpect(jsonPath("$.questions.menu.criteria.kb_menu_0555").value("국민카드 분실해제"))
                .andRespond(withSuccess(answer("kb_menu_0554", .95), MediaType.APPLICATION_JSON));
        var result = service.select("국민카드 분실 010-1234-5678");
        assertEquals("selected", result.status()); assertEquals("e5_jev",result.pipeline());
        assertEquals("kb_menu_0554", result.menus().get(0).id()); assertEquals(1,result.jevCalls());
        verify(retriever,times(1)).retrieve("국민카드 분실 [민감정보]",20); server.verify();
    }
    @Test void neverAcceptsAnIdOutsideRetrievedCandidates() throws Exception {
        server.expect(anything()).andRespond(withSuccess(answer("kb_menu_0323", .99),MediaType.APPLICATION_JSON));
        assertEquals(502,assertThrows(ResponseStatusException.class,()->service.select("환전")).getStatusCode().value());server.verify();
    }
    @Test void abstainsForLowConfidenceAndNoMatch() throws Exception {
        server.expect(anything()).andRespond(withSuccess(answer("kb_menu_0555", .2),MediaType.APPLICATION_JSON));
        server.expect(anything()).andRespond(withSuccess(answer("no_match", .99),MediaType.APPLICATION_JSON));
        var low = service.select("카드"); assertEquals("needs_clarification",low.status());assertTrue(low.menus().isEmpty());
        var none = service.select("날씨");assertEquals("no_match",none.status());assertTrue(none.menus().isEmpty());server.verify();
    }
    @Test void retrievalFailureNeverCallsJev() {
        when(retriever.retrieve(anyString(),eq(20))).thenThrow(new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"search unavailable"));
        assertEquals(503,assertThrows(ResponseStatusException.class,()->service.select("분실")).getStatusCode().value());server.verify();
    }
    @Test void rejectsBadInputWithoutSearch() {
        assertEquals(400,assertThrows(ResponseStatusException.class,()->service.select(" ")).getStatusCode().value());
        verifyNoInteractions(retriever);server.verify();
    }
    @Test void preservesReviewedInventoryAndEvaluationLabels() throws Exception {
        assertEquals(585,catalog.all().size());assertNull(catalog.find("kb_menu_0001"));
        try(var input=getClass().getResourceAsStream("/menu-selection-cases-20.json")) {
            var cases=mapper.readTree(input);assertEquals(20,cases.size());
            for(var row:cases)assertNotNull(catalog.find(row.path("expected").asText()));
        }
        assertTrue(catalog.find("kb_menu_0207").selectWhen().stream().anyMatch(s->s.contains("해지")));
        var root=(com.fasterxml.jackson.databind.node.ObjectNode)mapper.readTree(getClass().getResourceAsStream("/kb_starbanking_menu_structure_cleaned.json"));
        ((com.fasterxml.jackson.databind.node.ArrayNode)root.path("menus")).add(root.path("menus").get(0).deepCopy());root.put("menu_count",586);
        assertThrows(IllegalStateException.class,()->new MenuCatalog(mapper,mapper.writeValueAsBytes(root)));
    }
}
