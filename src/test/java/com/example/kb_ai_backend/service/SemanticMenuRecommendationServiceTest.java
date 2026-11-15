package com.example.kb_ai_backend.service;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
class SemanticMenuRecommendationServiceTest {
    JevDecisionClient jev=mock(JevDecisionClient.class);
    SemanticMenuRetriever retrieval=mock(SemanticMenuRetriever.class);
    SemanticMenuSelectionService single=mock(SemanticMenuSelectionService.class);
    MenuCatalog catalog;SemanticMenuRecommendationService service;
    @BeforeEach void setup() throws Exception {catalog=new MenuCatalog(new ObjectMapper());service=new SemanticMenuRecommendationService(jev,retrieval,catalog,single,.6,.7);}
    JevDecisionClient.Choice choice(String value){return new JevDecisionClient.Choice(value,.95);}
    JevDecisionClient.Decisions route(String mode){return new JevDecisionClient.Decisions(Map.of("route",choice(mode)),10);}
    JevDecisionClient.Decisions answers(Map<String,String> values){var out=new LinkedHashMap<String,JevDecisionClient.Choice>();values.forEach((k,v)->out.put(k,choice(v)));return new JevDecisionClient.Decisions(out,20);}
    @Test void preservesOriginalSingleSelectionAndDoesNotUseFixedNeedTaxonomy(){
        var m=catalog.find("kb_menu_0002");when(jev.decide(anyMap(),anyMap())).thenReturn(route("single"));
        when(single.select("맞춤 상품 추천")).thenReturn(new SemanticMenuSelectionService.Result("selected",List.of(m),List.of(m.id()),.95,"e5_jev",catalog.sha256(),10,20,1));
        var result=service.compose("맞춤 상품 추천");assertEquals("ready",result.status());assertEquals(m,result.recommendations().get(0).menu());assertEquals(2,result.metrics().jevCalls());verifyNoInteractions(retrieval);
    }
    @Test void independentlySelectsActualClausesIncludingTwoPreviouslyUnmappedRequests(){
        var a=catalog.find("kb_menu_0002");var b=catalog.find("kb_menu_0158");
        when(jev.decide(anyMap(),anyMap())).thenReturn(route("multiple"),answers(Map.of("request_1",a.id(),"request_2",b.id())));
        when(retrieval.retrieve("맞춤 상품 추천",20)).thenReturn(List.of(a));when(retrieval.retrieve("해지 골드 계좌 조회",20)).thenReturn(List.of(b));
        var result=service.compose("맞춤 상품 추천 그리고 별개의 업무로, 해지 골드 계좌 조회");
        assertEquals(Set.of(a.id(),b.id()),result.recommendations().stream().map(r->r.menu().id()).collect(java.util.stream.Collectors.toSet()));
        assertEquals(2,result.metrics().jevCalls());verify(jev,times(2)).decide(anyMap(),anyMap());
    }
    @Test void expandsCandidateBudgetOnlyForUnresolvedTasks(){
        var m=catalog.find("kb_menu_0203");when(jev.decide(anyMap(),anyMap())).thenReturn(route("travel"),answers(Map.of("foreign_exchange","no_match","foreign_payment","skip","travel_insurance","skip")),answers(Map.of("foreign_exchange",m.id())));
        when(retrieval.retrieve(anyString(),eq(12))).thenReturn(List.of(m));when(retrieval.retrieve("환전신청",40)).thenReturn(List.of(m));
        var result=service.compose("개발용 후보 확대 시나리오");assertEquals(3,result.metrics().jevCalls());verify(retrieval).retrieve("환전신청",40);verify(retrieval,never()).retrieve("해외 QR 결제",40);
    }
    @Test void travelBundleReturnsThreeAndSkipsAlreadyCompletedInsurance(){
        var a=catalog.find("kb_menu_0323");var b=catalog.find("kb_menu_0413");var c=catalog.find("kb_menu_0602");
        when(retrieval.retrieve("환전신청",12)).thenReturn(List.of(a));when(retrieval.retrieve("해외 QR 결제",12)).thenReturn(List.of(b));when(retrieval.retrieve("KB손해보험 다이렉트 해외여행보험",12)).thenReturn(List.of(c));
        when(jev.decide(anyMap(),anyMap())).thenReturn(route("travel"),answers(Map.of("foreign_exchange",a.id(),"foreign_payment",b.id(),"travel_insurance",c.id())),route("travel"),answers(Map.of("foreign_exchange",a.id(),"foreign_payment",b.id(),"travel_insurance","skip")));
        assertEquals(3,service.compose("일본 여행 가고 싶어").recommendations().size());assertEquals(2,service.compose("일본 여행인데 보험은 완료했어").recommendations().size());
    }
    @Test void unparsedMultipleRequestsUseIndependentBinaryMenuQuestions(){
        var a=catalog.find("kb_menu_0493");var b=catalog.find("kb_menu_0492");when(jev.decide(anyMap(),anyMap())).thenReturn(route("multiple"));when(retrieval.retrieve(anyString(),eq(40))).thenReturn(List.of(a,b));
        when(jev.judge(anyMap(),anyMap())).thenReturn(new JevDecisionClient.BinaryDecisions(Map.of(a.id(),.99,b.id(),.95),20));
        var result=service.compose("통장사본 잔액증명서 둘 다 발급");assertEquals(2,result.recommendations().size());verify(jev,times(1)).decide(anyMap(),anyMap());verify(jev).judge(anyMap(),anyMap());
    }
    @Test void routeUncertaintyDoesNotDiscardOtherwiseSearchableRequest(){
        var m=catalog.find("kb_menu_0493");when(jev.decide(anyMap(),anyMap())).thenReturn(new JevDecisionClient.Decisions(Map.of("route",new JevDecisionClient.Choice("ambiguous",.2)),10));
        when(retrieval.retrieve(anyString(),eq(40))).thenReturn(List.of(m));when(jev.judge(anyMap(),anyMap())).thenReturn(new JevDecisionClient.BinaryDecisions(Map.of(m.id(),.95),20));
        assertEquals("ready",service.compose("내 계좌 증빙").status());
    }
    @Test void masksSensitiveInputBeforeBothRouteAndDelegatedSingleSelection(){
        var m=catalog.find("kb_menu_0323");when(jev.decide(anyMap(),anyMap())).thenReturn(route("single"));
        when(single.select(anyString())).thenReturn(new SemanticMenuSelectionService.Result("selected",List.of(m),List.of(m.id()),.95,"e5_jev",catalog.sha256(),1,1,1));service.compose("환전 연락처 010-1234-5678");
        verify(single).select("환전 연락처 [민감정보]");var states=org.mockito.ArgumentCaptor.forClass(Map.class);verify(jev).decide(states.capture(),anyMap());assertFalse(states.getValue().toString().contains("010-1234-5678"));
    }
    @Test void invalidInputsAndTooManyExplicitTasksAreNotSilentlyTruncated(){
        assertThrows(ResponseStatusException.class,()->service.compose(" "));assertThrows(ResponseStatusException.class,()->service.compose("가".repeat(2001)));verifyNoInteractions(jev);
        when(jev.decide(anyMap(),anyMap())).thenReturn(route("multiple"));assertEquals("needs_clarification",service.compose("통장사본 그리고 환전 그리고 보험 그리고 송금").status());verifyNoInteractions(retrieval);
    }
    @Test void unsupportedRequestsStopOnlyForExplicitCertainRoute(){
        when(jev.decide(anyMap(),anyMap())).thenReturn(route("unrelated"),route("ambiguous"));assertEquals("no_match",service.compose("요리법").status());assertEquals("needs_clarification",service.compose("뭐하지").status());verifyNoInteractions(retrieval,single);
    }
}
