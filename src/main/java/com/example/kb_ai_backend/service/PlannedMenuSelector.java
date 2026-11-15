package com.example.kb_ai_backend.service;

import org.springframework.stereotype.Service;
import java.util.*;
import java.util.concurrent.TimeUnit;

/** Executes arbitrary independently planned outcomes against the real menu catalog. */
@Service
public class PlannedMenuSelector {
    public record Task(String id,String query,String evidence,String basis){}
    public record Plan(String status,List<Task> tasks) {
        public Plan {
            if(!Set.of("ready","no_match","needs_clarification").contains(status)||tasks==null||tasks.size()>8)
                throw new IllegalArgumentException("Invalid task plan");
            tasks=List.copyOf(tasks);var ids=new HashSet<String>();var queries=new HashSet<String>();
            for(var t:tasks)if(t==null||t.id()==null||!ids.add(t.id())||t.query()==null||t.query().isBlank()||t.query().length()>300||!queries.add(t.query().strip())||t.evidence()==null||t.evidence().isBlank()||!Set.of("explicit","suggested").contains(t.basis()))throw new IllegalArgumentException("Invalid planned task");
            if(status.equals("ready")==tasks.isEmpty())throw new IllegalArgumentException("Inconsistent plan status");
        }
    }
    public record Selection(String status,List<SemanticMenuRecommendationService.Recommendation> recommendations,
                            List<SemanticMenuRecommendationService.Review> reviews,Map<String,List<String>> candidates,
                            long retrievalMs,long selectionMs,int jevCalls){}
    private final JevDecisionClient jev;
    private final SemanticMenuRetriever retrieval;
    private final MenuCatalog catalog;
    public PlannedMenuSelector(JevDecisionClient jev,SemanticMenuRetriever retrieval,MenuCatalog catalog){this.jev=jev;this.retrieval=retrieval;this.catalog=catalog;}
    public Selection select(String message,Plan plan){
        if(!plan.status().equals("ready"))return new Selection(plan.status(),List.of(),List.of(),Map.of(),0,0,0);
        for(var t:plan.tasks())if(!message.contains(t.evidence()))throw new IllegalArgumentException("Task evidence must quote the redacted input");
        var candidates=new LinkedHashMap<String,List<MenuCatalog.Menu>>();long start=System.nanoTime();
        for(var t:plan.tasks())candidates.put(t.id(),retrieval.retrieve(t.query(),20));
        long retrievalMs=elapsed(start);var first=choose(message,plan.tasks(),candidates);long selectionMs=first.durationMs();int calls=1;
        var answers=new LinkedHashMap<>(first.answers());
        var unresolved=plan.tasks().stream().filter(t->{var a=answers.get(t.id());return a.confidence()<.6||Set.of("no_match","unsure").contains(a.choice());}).toList();
        if(!unresolved.isEmpty()){
            start=System.nanoTime();for(var t:unresolved)candidates.put(t.id(),retrieval.retrieve(t.query(),40));retrievalMs+=elapsed(start);
            var second=choose(message,unresolved,candidates);answers.putAll(second.answers());selectionMs+=second.durationMs();calls++;
        }
        var selected=new LinkedHashMap<String,SemanticMenuRecommendationService.Recommendation>();var reviews=new ArrayList<SemanticMenuRecommendationService.Review>();
        for(var t:plan.tasks()){
            var a=answers.get(t.id());
            if(a.confidence()<.6||Set.of("no_match","unsure","skip").contains(a.choice())){
                reviews.add(new SemanticMenuRecommendationService.Review("coverage",t.id(),"planned_outcome_not_covered",a.choice(),a.confidence()));continue;
            }
            if(candidates.get(t.id()).stream().noneMatch(m->m.id().equals(a.choice())))throw new IllegalStateException("Selection outside retrieved candidates");
            if(selected.containsKey(a.choice())){
                reviews.add(new SemanticMenuRecommendationService.Review("coverage",t.id(),"independent_outcomes_collapsed_to_same_menu",a.choice(),a.confidence()));continue;
            }
            selected.put(a.choice(),new SemanticMenuRecommendationService.Recommendation(catalog.find(a.choice()),t.id(),t.query(),t.basis(),t.evidence(),a.confidence(),null));
        }
        var evidence=new LinkedHashMap<String,List<String>>();candidates.forEach((k,v)->evidence.put(k,v.stream().map(MenuCatalog.Menu::id).toList()));
        return new Selection(selected.isEmpty()?"needs_clarification":reviews.isEmpty()?"ready":"partial",List.copyOf(selected.values()),List.copyOf(reviews),Collections.unmodifiableMap(evidence),retrievalMs,selectionMs,calls);
    }
    private JevDecisionClient.Decisions choose(String message,List<Task> tasks,Map<String,List<MenuCatalog.Menu>> candidates){
        var questions=new LinkedHashMap<String,JevDecisionClient.Question>();var context=new LinkedHashMap<String,Object>();
        for(var t:tasks){
            var choices=new LinkedHashMap<String,String>();candidates.get(t.id()).forEach(m->choices.put(m.id(),m.name()));choices.put("no_match","No candidate directly performs this task");choices.put("unsure","The requested outcome is ambiguous");choices.put("skip","The original request excludes or has already completed this task");
            questions.put(t.id(),new JevDecisionClient.Question("독립 업무 「"+t.query()+"」 하나를 직접 처리하는 가장 구체적인 메뉴를 고른다. 다른 질문의 답은 가정하지 않는다. 원문의 부정·완료·제외를 우선한다. 신청/변경/조회/해지와 은행/카드사 등 대상을 구별한다. 요청을 직접 실행하는 세부 메뉴가 있으면 상위 관리·목록·방법 안내 메뉴보다 그 세부 메뉴를 선택한다. 후보에 없으면 no_match, 근거 부족은 unsure.",choices));
            context.put(t.id(),Map.of("outcome",t.query(),"evidence",t.evidence(),"basis",t.basis(),"menus",candidates.get(t.id()).stream().map(m->Map.of("id",m.id(),"name",m.name(),"purpose",m.description(),"when",m.selectWhen())).toList()));
        }
        return jev.decide(Map.of("user_request",message,"tasks",context),questions);
    }
    private static long elapsed(long start){return TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-start);}
}
