package com.example.kb_ai_backend.service;
import org.springframework.stereotype.Service;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
/** Experimental general planner → actual E5 retrieval → independent JEV choices. */
@Service
public class GeneralMenuRecommendationService {
    private final MenuTaskPlanner planner;private final PlannedMenuSelector selector;
    public GeneralMenuRecommendationService(MenuTaskPlanner planner,PlannedMenuSelector selector){this.planner=planner;this.selector=selector;}
    public SemanticMenuRecommendationService.Result compose(String original){
        if(original==null||original.isBlank()||original.length()>2000)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"message는 1~2000자로 입력하세요.");
        String message=AiRequestRedactor.redact(original);var p=planner.plan(message);var s=selector.select(message,p.plan());
        return new SemanticMenuRecommendationService.Result(s.status(),s.recommendations(),new SemanticMenuRecommendationService.Metrics("llm_planner_e5_jev",p.ms(),s.retrievalMs(),s.selectionMs(),s.jevCalls()),s.reviews(),s.candidates());
    }
}
