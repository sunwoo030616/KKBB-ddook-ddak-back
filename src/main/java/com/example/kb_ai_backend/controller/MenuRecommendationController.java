package com.example.kb_ai_backend.controller;

import com.example.kb_ai_backend.service.MenuCatalog;
import com.example.kb_ai_backend.service.GeneralMenuRecommendationService;
import com.example.kb_ai_backend.service.SemanticMenuRecommendationService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;

/** Situation recommendations only; does not execute a financial action or render a widget. */
@RestController
@RequestMapping("/api/menus/recommend")
public class MenuRecommendationController {
    private final GeneralMenuRecommendationService service;
    private final MenuCatalog catalog;
    public MenuRecommendationController(GeneralMenuRecommendationService service, MenuCatalog catalog) {
        this.service=service; this.catalog=catalog;
    }
    public record Request(String message) {}
    public record Response(String status, List<MenuCatalog.Menu> menus,
                           List<SemanticMenuRecommendationService.Recommendation> recommendations,
                           SemanticMenuRecommendationService.Metrics metrics,
                           List<SemanticMenuRecommendationService.Review> reviews,
                           Map<String,List<String>> candidateIdsByNeed, String catalogSha256) {}
    @PostMapping
    public Response recommend(@RequestBody Request request) {
        if(request==null || request.message()==null || request.message().isBlank())
            throw new ResponseStatusException(org.springframework.http.HttpStatus.BAD_REQUEST,"message는 1~2000자로 입력하세요.");
        var result=service.compose(request.message());
        return new Response(result.status(),result.recommendations().stream().map(r->r.menu()).toList(),
                result.recommendations(),result.metrics(),result.reviews(),result.candidateIdsByNeed(),catalog.sha256());
    }
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String,Object>> error(ResponseStatusException e) {
        return ResponseEntity.status(e.getStatusCode()).body(Map.of("status",e.getStatusCode().value(),"error",e.getReason()));
    }
}
