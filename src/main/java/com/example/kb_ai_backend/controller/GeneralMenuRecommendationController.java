package com.example.kb_ai_backend.controller;
import com.example.kb_ai_backend.service.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.ResponseEntity;
import java.util.*;
@RestController
@RequestMapping("/api/menus/recommend-general")
public class GeneralMenuRecommendationController {
    private final GeneralMenuRecommendationService service;private final MenuCatalog catalog;
    public GeneralMenuRecommendationController(GeneralMenuRecommendationService service,MenuCatalog catalog){this.service=service;this.catalog=catalog;}
    @PostMapping public MenuRecommendationController.Response recommend(@RequestBody MenuRecommendationController.Request request){
        var result=service.compose(request==null?null:request.message());
        return new MenuRecommendationController.Response(result.status(),result.recommendations().stream().map(r->r.menu()).toList(),result.recommendations(),result.metrics(),result.reviews(),result.candidateIdsByNeed(),catalog.sha256());
    }
    @ExceptionHandler(ResponseStatusException.class) public ResponseEntity<Map<String,Object>> error(ResponseStatusException e){return ResponseEntity.status(e.getStatusCode()).body(Map.of("status",e.getStatusCode().value(),"error",e.getReason()));}
}
