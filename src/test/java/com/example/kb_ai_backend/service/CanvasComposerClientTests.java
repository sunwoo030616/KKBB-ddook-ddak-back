package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class CanvasComposerClientTests {
    @Test void forwardsStructuredScreenAndRevision() throws Exception {
        var http = new RestTemplate();
        var mock = MockRestServiceServer.bindTo(http).build();
        mock.expect(requestTo("http://localhost:8767/canvas/compose"))
            .andExpect(method(HttpMethod.POST))
            .andExpect(content().json("{\"message\":\"대출 상환 화면\",\"expected_revision\":0}"))
            .andRespond(withSuccess("{\"status\":\"composed\",\"revision\":1,\"widgets\":[{\"type\":\"loan_inputs_widget\"}]}", MediaType.APPLICATION_JSON));
        var client = new CanvasComposerClient(http, "http://localhost:8767/");
        var response = client.compose(new ObjectMapper().readTree("{\"message\":\"대출 상환 화면\",\"expected_revision\":0}"));
        assertEquals(200, response.getStatusCode().value());
        assertEquals(-1, response.getHeaders().getContentLength());
        assertTrue(response.getBody().toString().contains("loan_inputs_widget"));
        mock.verify();
    }

    @Test void revisionConflictRetainsStatusAndSuppressesUpstreamDetails() throws Exception {
        var http = new RestTemplate();
        var mock = MockRestServiceServer.bindTo(http).build();
        mock.expect(requestTo("http://localhost:8767/canvas/compose"))
            .andRespond(withStatus(HttpStatus.CONFLICT).body("DO_NOT_LEAK_INTERNAL_BODY"));
        var response = new CanvasComposerClient(http, "http://localhost:8767")
            .compose(new ObjectMapper().readTree("{\"message\":\"변경\"}"));
        assertEquals(409, response.getStatusCode().value());
        assertFalse(response.getBody().toString().contains("DO_NOT_LEAK"));
        mock.verify();
    }
    @Test void asyncSubmissionAndPollingKeepStatusAndJobIdentity() throws Exception {
        var http = new RestTemplate();
        var mock = MockRestServiceServer.bindTo(http).build();
        mock.expect(requestTo("http://localhost:8767/canvas/jobs"))
            .andExpect(method(HttpMethod.POST))
            .andRespond(withStatus(HttpStatus.ACCEPTED).contentType(MediaType.APPLICATION_JSON).body("{\"job_id\":\"job-one\",\"status\":\"queued\"}"));
        mock.expect(requestTo("http://localhost:8767/canvas/jobs/job-one"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(withSuccess("{\"job_id\":\"job-one\",\"status\":\"completed\",\"result\":{\"widgets\":[]}}", MediaType.APPLICATION_JSON));
        var client = new CanvasComposerClient(http, "http://localhost:8767");
        assertEquals(202, client.submitJob(new ObjectMapper().readTree("{\"request\":{\"message\":\"여행 화면\"}}" )).getStatusCode().value());
        assertTrue(client.jobStatus("job-one").getBody().toString().contains("completed"));
        mock.verify();
    }
}
