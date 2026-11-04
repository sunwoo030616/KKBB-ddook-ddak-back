package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.http.MediaType;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/** Local generative screen compiler. The request cannot override its upstream URL. */
@Service
public class CanvasComposerClient {
    private final RestTemplate http;
    private final String baseUrl;

    @Autowired
    public CanvasComposerClient(@Value("${canvas.composer.url:http://127.0.0.1:8767}") String baseUrl) {
        this(createHttp(), baseUrl);
    }

    CanvasComposerClient(RestTemplate http, String baseUrl) {
        this.http = http;
        this.baseUrl = baseUrl.replaceAll("/+$", "");
    }

    private static RestTemplate createHttp() {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(2000);
        factory.setReadTimeout(120000);
        return new RestTemplate(factory);
    }

    public ResponseEntity<?> compose(JsonNode request) { return forward("/canvas/compose", HttpMethod.POST, request); }
    public ResponseEntity<?> submitJob(JsonNode request) { return forward("/canvas/jobs", HttpMethod.POST, request); }
    public ResponseEntity<?> jobStatus(String jobId) { return forward("/canvas/jobs/" + jobId, HttpMethod.GET, null); }

    private ResponseEntity<?> forward(String path, HttpMethod method, JsonNode request) {
        try {
            var upstream = http.exchange(baseUrl + path, method, new HttpEntity<>(request), JsonNode.class);
            // Jackson reserializes the body; an upstream Content-Length would be wrong.
            return ResponseEntity.status(upstream.getStatusCode()).contentType(MediaType.APPLICATION_JSON).body(upstream.getBody());
        } catch (HttpStatusCodeException e) {
            // Preserve actionable validation/revision statuses without leaking model/provider bodies.
            int code = e.getStatusCode().value();
            if (code == 409 || code == 422 || code == 429 || code == 404) {
                String message = switch(code) {
                    case 409 -> "화면이 변경되었습니다. 최신 revision으로 다시 요청해주세요.";
                    case 429 -> "화면 구성 요청이 많습니다. 잠시 후 다시 보내주세요.";
                    case 404 -> "화면 구성 작업이 없거나 만료되었습니다.";
                    default -> "화면 요청 값을 확인해주세요.";
                };
                return ResponseEntity.status(code).body(java.util.Map.of("error", message));
            }
            return ResponseEntity.status(503).body(java.util.Map.of("error", "화면 구성 서비스를 사용할 수 없습니다."));
        } catch (RestClientException e) {
            return ResponseEntity.status(503).body(java.util.Map.of("error", "화면 구성 서비스 연결을 확인해주세요."));
        }
    }
}
