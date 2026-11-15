package com.example.kb_ai_backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import java.util.function.Function;
import java.util.concurrent.TimeUnit;

/** Atomic independent questions; sequencing and set composition belong in application code. */
@Service
public class JevDecisionClient {
    private static final String URL="https://api.typesafe.ai/v1/systemone";
    private final RestTemplate client;
    private final String key,model;
    private final AiProviderCircuit circuit=new AiProviderCircuit(java.time.Clock.systemUTC(),3,java.time.Duration.ofSeconds(30));
    @Autowired
    public JevDecisionClient(@Value("${JEV_AI_API_KEY:}") String key,@Value("${JEV_MODEL:jev-latest}") String model){this(newClient(),key,model);}
    JevDecisionClient(RestTemplate client,String key,String model){this.client=client;this.key=key;this.model=model;}
    private static RestTemplate newClient(){var f=new SimpleClientHttpRequestFactory();f.setConnectTimeout(3000);f.setReadTimeout(30000);return new RestTemplate(f);}
    public record Question(String instructions,Map<String,String> criteria){}
    public record Choice(String choice,double confidence){}
    public record Decisions(Map<String,Choice> answers,long durationMs){}
    public record BinaryDecisions(Map<String,Double> answers,long durationMs){}
    private record Timed<T>(T value,long ms){}
    public Decisions decide(Map<String,Object> state,Map<String,Question> definitions){
        var questions=new LinkedHashMap<String,Object>();
        definitions.forEach((id,q)->{if(q.criteria().size()<2||q.criteria().size()>255)throw new IllegalArgumentException("Invalid choice count");questions.put(id,Map.of("type","choice","instructions",q.instructions(),"criteria",q.criteria()));});
        var result=execute(state,questions,response->{
            var answers=new LinkedHashMap<String,Choice>();
            definitions.forEach((id,q)->{var a=response.path("answers").path(id);if(!"choice".equals(a.path("type").asText())||!a.path("choice").isTextual()||!a.path("confidence").isNumber())throw invalid();
                String chosen=a.path("choice").asText();double confidence=a.path("confidence").doubleValue();
                if(!q.criteria().containsKey(chosen)||!validProbability(confidence))throw invalid();answers.put(id,new Choice(chosen,confidence));});
            return Collections.unmodifiableMap(answers);
        });
        return new Decisions(result.value(),result.ms());
    }
    public BinaryDecisions judge(Map<String,Object> state,Map<String,String> definitions){
        var questions=new LinkedHashMap<String,Object>();definitions.forEach((id,instructions)->questions.put(id,Map.of("type","noul","instructions",instructions)));
        var result=execute(state,questions,response->{
            var answers=new LinkedHashMap<String,Double>();
            definitions.forEach((id,q)->{var a=response.path("answers").path(id);if(!"noul".equals(a.path("type").asText())||!a.path("noul").isNumber())throw invalid();double probability=a.path("noul").doubleValue();if(!validProbability(probability))throw invalid();answers.put(id,probability);});
            return Collections.unmodifiableMap(answers);
        });
        return new BinaryDecisions(result.value(),result.ms());
    }
    private <T> Timed<T> execute(Map<String,Object> state,Map<String,Object> questions,Function<JsonNode,T> decode){
        if(key==null||key.isBlank())throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"JEV_AI_API_KEY가 실행 환경에 없습니다.");
        if(questions.isEmpty())throw new IllegalArgumentException("Empty questions");
        long ticket=circuit.acquire().orElseThrow(()->new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"상황 판단 서비스가 잠시 쉬고 있어요."));
        boolean failed=true;long start=System.nanoTime();
        try{
            var headers=new HttpHeaders();headers.setContentType(MediaType.APPLICATION_JSON);headers.setBearerAuth(key);
            var response=client.postForObject(URL,new HttpEntity<>(Map.of("model",model,"state",state,"questions",questions),headers),JsonNode.class);
            if(response==null)throw invalid();T value=decode.apply(response);failed=false;return new Timed<>(value,TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-start));
        }catch(HttpStatusCodeException e){failed=e.getStatusCode().value()>=500||Set.of(401,403,429).contains(e.getStatusCode().value());throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,"JEV API 오류: HTTP "+e.getStatusCode().value());}
        catch(ResourceAccessException e){throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT,"JEV 연결 실패 또는 시간 초과");}
        catch(ResponseStatusException e){throw e;}
        catch(Exception e){throw invalid();}
        finally{circuit.finish(ticket,failed);}
    }
    private static boolean validProbability(double v){return Double.isFinite(v)&&v>=0&&v<=1;}
    private static ResponseStatusException invalid(){return new ResponseStatusException(HttpStatus.BAD_GATEWAY,"상황 판단 API 응답 형식이 올바르지 않습니다.");}
}
