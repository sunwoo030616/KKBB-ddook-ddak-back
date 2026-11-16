package com.example.kb_ai_backend.service;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;
class PlannedMenuSelectorTest {
    MenuCatalog catalog;JevDecisionClient jev=mock(JevDecisionClient.class);SemanticMenuRetriever retrieval=mock(SemanticMenuRetriever.class);PlannedMenuSelector service;
    @BeforeEach void setup()throws Exception{catalog=new MenuCatalog(new ObjectMapper());service=new PlannedMenuSelector(jev,retrieval,catalog);}
    PlannedMenuSelector.Task task(String id,String query){return new PlannedMenuSelector.Task(id,query,query,"explicit");}
    JevDecisionClient.Decisions answers(Map<String,String> choices){var m=new LinkedHashMap<String,JevDecisionClient.Choice>();choices.forEach((k,v)->m.put(k,new JevDecisionClient.Choice(v,.95)));return new JevDecisionClient.Decisions(m,10);}
    @Test void selectsFourIndependentOutcomesWithoutScenarioRouting(){var ids=List.of("kb_menu_0323","kb_menu_0493","kb_menu_0205","kb_menu_0554");var tasks=new ArrayList<PlannedMenuSelector.Task>();var answers=new LinkedHashMap<String,String>();for(int i=0;i<ids.size();i++){var q="task"+i;tasks.add(task(q,q));when(retrieval.retrieve(q,20)).thenReturn(List.of(catalog.find(ids.get(i))));answers.put(q,ids.get(i));}when(jev.decide(anyMap(),anyMap())).thenReturn(answers(answers));var r=service.select("task0 task1 task2 task3",new PlannedMenuSelector.Plan("ready",tasks));assertEquals(4,r.recommendations().size());assertEquals("ready",r.status());assertEquals(1,r.jevCalls());}
    @Test void expandsOnlyUnresolvedTaskAndReportsMissingOutcome(){var a=catalog.find("kb_menu_0323");var b=catalog.find("kb_menu_0493");when(retrieval.retrieve("one",20)).thenReturn(List.of(a));when(retrieval.retrieve("two",20)).thenReturn(List.of(b));when(retrieval.retrieve("two",40)).thenReturn(List.of(b));when(jev.decide(anyMap(),anyMap())).thenReturn(answers(Map.of("a",a.id(),"b","no_match")),answers(Map.of("b","no_match")));var r=service.select("one two",new PlannedMenuSelector.Plan("ready",List.of(task("a","one"),task("b","two"))));assertEquals("partial",r.status());assertEquals(1,r.reviews().size());verify(retrieval,never()).retrieve("one",40);assertEquals(2,r.jevCalls());}
    @Test void duplicateMenuCannotSilentlyCoverDifferentTasks(){var m=catalog.find("kb_menu_0323");when(retrieval.retrieve(anyString(),eq(20))).thenReturn(List.of(m));when(jev.decide(anyMap(),anyMap())).thenReturn(answers(Map.of("a",m.id(),"b",m.id())));var r=service.select("one two",new PlannedMenuSelector.Plan("ready",List.of(task("a","one"),task("b","two"))));assertEquals("partial",r.status());assertEquals("independent_outcomes_collapsed_to_same_menu",r.reviews().get(0).reason());}
    @Test void rejectsInventedEvidenceBeforeRetrieval(){assertThrows(IllegalArgumentException.class,()->service.select("actual",new PlannedMenuSelector.Plan("ready",List.of(task("a","invented")))));verifyNoInteractions(retrieval,jev);}
    @Test void rejectsDuplicateQueriesAndOverflowInsteadOfTruncating(){assertThrows(IllegalArgumentException.class,()->new PlannedMenuSelector.Plan("ready",List.of(task("a","one"),task("b","one"))));var many=new ArrayList<PlannedMenuSelector.Task>();for(int i=0;i<9;i++)many.add(task("t"+i,"query"+i));assertThrows(IllegalArgumentException.class,()->new PlannedMenuSelector.Plan("ready",many));}
    @Test void negativePlansNeverSearchOrSelect(){assertEquals("no_match",service.select("recipe",new PlannedMenuSelector.Plan("no_match",List.of())).status());verifyNoInteractions(retrieval,jev);}
}
