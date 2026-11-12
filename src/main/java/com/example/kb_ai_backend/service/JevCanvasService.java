package com.example.kb_ai_backend.service;

import com.example.kb_ai_backend.session.ConversationSession;
import com.example.kb_ai_backend.session.InMemorySessionStore;
import com.example.kb_ai_backend.session.SessionStore;
import com.example.kb_ai_backend.session.SlotRequirements;
import com.example.kb_ai_backend.session.TravelSlots;
import com.example.kb_ai_backend.trace.DecisionTrace;
import com.example.kb_ai_backend.trace.TraceStore;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.time.Duration;
import java.util.*;

/**
 * jev 선택 1회 → 서버 검증 → 세션 슬롯 병합 → 위젯 구성.
 * 필수 정보가 빠진 위젯만 보류하고 clarification_widget으로 그 정보만 되묻는다.
 * 다음 발화가 빠진 정보를 채우면 jev를 다시 부르지 않고 세션에 남은 위젯을 마저 그린다.
 * 모든 요청은 판단 과정을 DecisionTrace로 남긴다 (GET /api/canvas/{requestId}/trace).
 */
@Service
public class JevCanvasService {
    static final Set<String> TRAVEL_WIDGETS = Set.of(
            "travel_card_charge_widget", "overseas_qr_payment_widget", "travel_insurance_widget");
    private static final CanvasParameters.Values NO_VALUES = new CanvasParameters.Values(null, null, null, null, false);

    private final WidgetSelectionExperimentService selector;
    private final CanvasParameters parameters;
    private final WidgetDataService data;
    private final SessionStore sessions;
    private final TraceStore traces;
    private final Clock clock;

    public JevCanvasService(WidgetSelectionExperimentService selector, CanvasParameters parameters, WidgetDataService data) {
        this(selector, parameters, data, new InMemorySessionStore(Clock.systemUTC(), Duration.ofMinutes(30), 10_000));
    }

    public JevCanvasService(WidgetSelectionExperimentService selector, CanvasParameters parameters,
                            WidgetDataService data, SessionStore sessions) {
        this(selector, parameters, data, sessions, new TraceStore(Clock.systemUTC(), Duration.ofHours(1), 500), Clock.systemUTC());
    }

    @Autowired
    public JevCanvasService(WidgetSelectionExperimentService selector, CanvasParameters parameters,
                            WidgetDataService data, SessionStore sessions, TraceStore traces, Clock clock) {
        this.selector = selector; this.parameters = parameters; this.data = data;
        this.sessions = sessions; this.traces = traces; this.clock = clock;
    }

    public Optional<DecisionTrace> trace(String requestId) {
        return traces.find(requestId);
    }

    public Map<String, Object> compose(String message) {
        return compose(message, null);
    }

    public Map<String, Object> compose(String message, String sessionId) {
        String requestId = Optional.ofNullable(MDC.get("requestId")).orElseGet(() -> UUID.randomUUID().toString());
        var trace = new DecisionTrace(requestId, clock.instant(), message == null ? 0 : message.length());
        try {
            Map<String, Object> body = compose(message, sessionId, trace);
            body.put("requestId", requestId);
            trace.finish((String) body.get("status"), renderedTypes(body));
            return body;
        } catch (RuntimeException e) {
            trace.fail(e);
            throw e;
        } finally {
            traces.save(trace);
        }
    }

    private Map<String, Object> compose(String message, String sessionId, DecisionTrace trace) {
        if (message == null || message.isBlank()) return response("무엇을 도와드릴까요?", "empty", List.of(), sessionId);
        if (message.length() > 2000) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "message는 2000자 이내로 입력하세요.");

        long started = System.nanoTime();
        ConversationSession session = sessions.find(sessionId).orElseGet(sessions::create);
        boolean continuing = session.id().equals(sessionId);
        trace.stage("session", started, continuing ? "기존 세션 이어감" : "새 세션");
        trace.session(session.id(), false);

        // 직전 응답에서 되물은 정보에 답한 경우: 선택을 다시 하지 않고 보류된 위젯을 마저 그린다
        if (session.awaitingClarification()) {
            var resumed = resume(message, session, trace);
            if (resumed != null) return resumed;
        }

        started = System.nanoTime();
        var selection = selector.select(message, "jev");
        trace.stage("selection", started, "jev 응답 " + selection.durationMs() + "ms");
        trace.selection(selection.provider(), selection.model(), selection.needsReview(), selection.widgets(), candidates(selection));
        var ids = selection.widgets();
        if (ids == null || ids.size() > 3 || new HashSet<>(ids).size() != ids.size()
                || ids.stream().anyMatch(id -> !WidgetSelectionExperimentService.WIDGETS.containsKey(id)))
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "위젯 선택 결과가 올바르지 않습니다.");
        if (selection.needsReview()) return response("필요한 금융 기능을 조금 더 구체적으로 알려주세요.", "needs_clarification", List.of(), session.id());
        if (ids.isEmpty()) return response("여행 준비, 모임 회비 관리, 분실 대응 중 필요한 기능을 알려주세요.", "unsupported", List.of(), session.id());

        boolean travel = ids.stream().anyMatch(TRAVEL_WIDGETS::contains);
        started = System.nanoTime();
        var values = travel ? parameters.extract(message) : NO_VALUES;
        trace.stage("parameters", started, travel ? "여행 정보 규칙 추출" : "추출 대상 아님");
        if (values.needsReview()) return response("여행지·통화·금액·기간을 하나씩 명확하게 입력해주세요.", "needs_clarification", List.of(), session.id());

        TravelSlots slots = travel ? session.slots().mergedWith(toSlots(values)) : session.slots();
        return render(ids, slots, session, "필요한 기능을 모았어요.", trace);
    }

    private Map<String, Object> resume(String message, ConversationSession session, DecisionTrace trace) {
        long started = System.nanoTime();
        var values = parameters.extract(message);
        if (values.needsReview()) return null;
        var answer = toSlots(values);
        if (answer.isEmpty()) return null; // 답이 아니라 새 요청으로 본다
        trace.stage("resume", started, "되묻기 응답으로 판단, 위젯 선택 생략");
        trace.session(session.id(), true);
        return render(session.pendingWidgets(), session.slots().mergedWith(answer), session, "알려주신 정보로 마저 채웠어요.", trace);
    }

    private Map<String, Object> render(List<String> ids, TravelSlots slots, ConversationSession session,
                                       String readyGreeting, DecisionTrace trace) {
        long started = System.nanoTime();
        var slotValues = new LinkedHashMap<String, Object>();
        slotValues.put("currency", slots.currency());
        slotValues.put("destination", slots.destination());
        slotValues.put("amount", slots.amount());
        slotValues.put("tripDays", slots.tripDays());
        trace.slots(slotValues);
        var ready = ids.stream().filter(id -> SlotRequirements.missingFor(id, slots).isEmpty()).toList();
        var blocked = ids.stream().filter(id -> !ready.contains(id)).toList();
        var widgets = new ArrayList<Map<String, Object>>();
        for (String id : ready) {
            widgets.add(data.buildWidget(id, slots.currency(), slots.destination(), slots.amount(), null, slots.tripDays()));
        }

        var missing = SlotRequirements.missingFor(blocked, slots);
        trace.missingSlots(missing);
        trace.stage("build", started, ready.size() + "개 위젯 구성");
        if (missing.isEmpty()) {
            sessions.save(session.withSlots(slots).resolved());
            return response(readyGreeting, "ready", widgets, session.id());
        }

        widgets.add(clarificationWidget(blocked, missing));
        sessions.save(session.withSlots(slots).awaiting(blocked, missing));
        String question = SlotRequirements.guide(missing.get(0)).question();
        String greeting = ready.isEmpty() ? question : "준비된 기능부터 보여드릴게요. " + question;
        return response(greeting, "needs_clarification", widgets, session.id());
    }

    private Map<String, Object> clarificationWidget(List<String> blocked, List<String> missing) {
        var guides = missing.stream().map(SlotRequirements::guide).map(g -> Map.<String, Object>of(
                "slot", g.slot(), "label", g.label(), "question", g.question(), "examples", g.examples())).toList();
        return Map.of(
                "type", "clarification_widget",
                "title", "이것만 알려주시면 바로 채워드릴게요",
                "missingSlots", guides,
                "pendingWidgets", blocked);
    }

    private static List<DecisionTrace.Candidate> candidates(WidgetSelectionExperimentService.Result selection) {
        if (selection.decisions() == null) return List.of();
        return selection.decisions().entrySet().stream()
                .map(e -> new DecisionTrace.Candidate(e.getKey(), e.getValue().choice(), e.getValue().confidence()))
                .toList();
    }

    @SuppressWarnings("unchecked")
    private static List<String> renderedTypes(Map<String, Object> body) {
        return ((List<Map<String, Object>>) body.get("widgets")).stream()
                .map(w -> w == null ? "null" : String.valueOf(w.get("type"))).toList();
    }

    private static TravelSlots toSlots(CanvasParameters.Values values) {
        return new TravelSlots(values.currency(), values.destination(), values.amount(), values.tripDays());
    }

    private Map<String, Object> response(String greeting, String status, List<?> widgets, String sessionId) {
        var body = new LinkedHashMap<String, Object>();
        body.put("greeting", greeting);
        body.put("status", status);
        body.put("widgets", widgets);
        if (sessionId != null) body.put("sessionId", sessionId);
        return body;
    }
}
