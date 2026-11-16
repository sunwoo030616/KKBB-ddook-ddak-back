package com.example.kb_ai_backend.service;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.test.web.client.MockRestServiceServer;
import java.util.Map;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;
import static org.junit.jupiter.api.Assertions.*;
class JevDecisionClientTest {
    Map<String,JevDecisionClient.Question> questions(){return Map.of("need_1",new JevDecisionClient.Question("choose",Map.of("known","known","none","none")));}
    @Test void rejectsUnknownChoiceEvenWhenConfidenceIsHigh() {
        var client=new RestTemplate();var server=MockRestServiceServer.createServer(client);
        server.expect(requestTo("https://api.typesafe.ai/v1/systemone")).andRespond(withSuccess("{\"answers\":{\"need_1\":{\"type\":\"choice\",\"choice\":\"invented\",\"confidence\":0.99}}}",MediaType.APPLICATION_JSON));
        var service=new JevDecisionClient(client,"test-key","test-model");
        assertEquals(502,assertThrows(ResponseStatusException.class,()->service.decide(Map.of(),questions())).getStatusCode().value());server.verify();
    }
    @Test void missingKeyMakesNoRequest() {
        var client=new RestTemplate();var server=MockRestServiceServer.createServer(client);
        assertEquals(503,assertThrows(ResponseStatusException.class,()->new JevDecisionClient(client,"","test").decide(Map.of(),questions())).getStatusCode().value());server.verify();
    }
    @Test void repeatedProviderFailureOpensCircuitWithoutAnotherRequest() {
        var client=new RestTemplate();var server=MockRestServiceServer.createServer(client);
        server.expect(org.springframework.test.web.client.ExpectedCount.times(3),anything()).andRespond(withServerError());
        var service=new JevDecisionClient(client,"test-key","test-model");
        for(int i=0;i<3;i++)assertEquals(502,assertThrows(ResponseStatusException.class,()->service.decide(Map.of(),questions())).getStatusCode().value());
        assertEquals(503,assertThrows(ResponseStatusException.class,()->service.decide(Map.of(),questions())).getStatusCode().value());server.verify();
    }

    @Test void binaryAnswersAreProbabilitiesNotChoiceConfidence() {
        var client=new RestTemplate();var server=MockRestServiceServer.createServer(client);
        server.expect(anything()).andRespond(withSuccess("{\"answers\":{\"menu_a\":{\"type\":\"noul\",\"noul\":0.8}}}",MediaType.APPLICATION_JSON));
        var result=new JevDecisionClient(client,"test-key","test-model").judge(Map.of(),Map.of("menu_a","필요한가?"));
        assertEquals(.8,result.answers().get("menu_a"));server.verify();
    }
    @Test void binaryOutOfRangeIsRejected() {
        var client=new RestTemplate();var server=MockRestServiceServer.createServer(client);
        server.expect(anything()).andRespond(withSuccess("{\"answers\":{\"menu_a\":{\"type\":\"noul\",\"noul\":1.2}}}",MediaType.APPLICATION_JSON));
        assertEquals(502,assertThrows(ResponseStatusException.class,()->new JevDecisionClient(client,"test-key","test-model").judge(Map.of(),Map.of("menu_a","필요한가?"))).getStatusCode().value());server.verify();
    }

}
