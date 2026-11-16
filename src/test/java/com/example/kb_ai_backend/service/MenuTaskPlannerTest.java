package com.example.kb_ai_backend.service;
import com.fasterxml.jackson.databind.*;
import org.junit.jupiter.api.*;
import org.springframework.http.*;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
class MenuTaskPlannerTest {
    RestTemplate client;MockRestServiceServer server;MenuTaskPlanner planner;ObjectMapper mapper=new ObjectMapper();
    @BeforeEach void setup()throws Exception{client=new RestTemplate();server=MockRestServiceServer.bindTo(client).build();planner=new MenuTaskPlanner(client,new MenuCatalog(mapper),"test","gpt-4o-mini-2024-07-18");}
    void reply(String content,String finish)throws Exception{server.expect(requestTo("https://api.openai.com/v1/chat/completions")).andExpect(method(HttpMethod.POST)).andExpect(jsonPath("$.store").value(false)).andExpect(jsonPath("$.response_format.json_schema.strict").value(true)).andRespond(withSuccess(mapper.writeValueAsString(Map.of("choices",List.of(Map.of("finish_reason",finish,"message",Map.of("content",content))))),MediaType.APPLICATION_JSON));}
    @Test void parsesArbitraryIndependentTasksWithQuotedEvidence()throws Exception{reply("{\"status\":\"ready\",\"tasks\":[{\"query\":\"통장사본 발급\",\"evidence\":\"계좌를 증빙\",\"basis\":\"explicit\"},{\"query\":\"자동이체 해지\",\"evidence\":\"정기 송금을 중단\",\"basis\":\"explicit\"}]}","stop");assertEquals(2,planner.plan("계좌를 증빙하고 정기 송금을 중단").plan().tasks().size());server.verify();}
    @Test void rejectsTasksWhoseEvidenceWasNotInUserRequest()throws Exception{reply("{\"status\":\"ready\",\"tasks\":[{\"query\":\"대출\",\"evidence\":\"대출 신청\",\"basis\":\"explicit\"}]}","stop");assertThrows(ResponseStatusException.class,()->planner.plan("아무것도 신청하지 않음"));}
    @Test void rejectsTruncatedResponseEvenWhenItsJsonLooksValid()throws Exception{reply("{\"status\":\"no_match\",\"tasks\":[]}","length");assertThrows(ResponseStatusException.class,()->planner.plan("요리"));}
    @Test void rejectsReadyWithoutTasks()throws Exception{reply("{\"status\":\"ready\",\"tasks\":[]}","stop");assertThrows(ResponseStatusException.class,()->planner.plan("송금"));}
    @Test void noKeyFailsBeforeNetwork(){var p=new MenuTaskPlanner(client,uncheckedCatalog(),"","model");assertThrows(ResponseStatusException.class,()->p.plan("송금"));server.verify();}
    MenuCatalog uncheckedCatalog(){try{return new MenuCatalog(mapper);}catch(Exception e){throw new RuntimeException(e);}}
}
