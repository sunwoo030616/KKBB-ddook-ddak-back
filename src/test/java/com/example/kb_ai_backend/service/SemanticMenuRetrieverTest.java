package com.example.kb_ai_backend.service;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
class SemanticMenuRetrieverTest {
    MenuCatalog catalog; MockRestServiceServer server; SemanticMenuRetriever retriever;
    @BeforeEach void setup() throws Exception {
        catalog=new MenuCatalog(new ObjectMapper());var client=new RestTemplate();server=MockRestServiceServer.createServer(client);
        retriever=new SemanticMenuRetriever(catalog,client,"http://127.0.0.1:18083/search");
    }
    @Test void bindsSearchToExactCatalogAndOnlyReturnsActiveIds() throws Exception {
        server.expect(requestTo("http://127.0.0.1:18083/search"))
                .andExpect(jsonPath("$.catalog_sha256").value(catalog.sha256()))
                .andRespond(withSuccess(new ObjectMapper().writeValueAsString(Map.of("catalog_sha256",catalog.sha256(),"ids",List.of("kb_menu_0554"))),MediaType.APPLICATION_JSON));
        assertEquals("kb_menu_0554",retriever.retrieve("분실",20).get(0).id());server.verify();
    }
    @Test void rejectsStaleCatalogInsteadOfSilentlyUsingOld628Vectors() {
        server.expect(anything()).andRespond(withSuccess("{\"catalog_sha256\":\"stale\",\"ids\":[\"kb_menu_0554\"]}",MediaType.APPLICATION_JSON));
        assertEquals(503,assertThrows(ResponseStatusException.class,()->retriever.retrieve("분실",20)).getStatusCode().value());server.verify();
    }
    @Test void rejectsExcludedIdsAndRemoteEndpoints() throws Exception {
        server.expect(anything()).andRespond(withSuccess(new ObjectMapper().writeValueAsString(Map.of("catalog_sha256",catalog.sha256(),"ids",List.of("kb_menu_0001"))),MediaType.APPLICATION_JSON));
        assertThrows(ResponseStatusException.class,()->retriever.retrieve("인기",20));server.verify();
        assertThrows(IllegalArgumentException.class,()->new SemanticMenuRetriever(catalog,new RestTemplate(),"https://example.com/search"));
    }
}
