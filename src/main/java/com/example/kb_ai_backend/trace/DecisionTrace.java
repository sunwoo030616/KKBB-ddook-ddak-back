package com.example.kb_ai_backend.trace;

import com.example.kb_ai_backend.feedback.FeedbackEvent;

import java.time.Instant;
import java.util.*;

/**
 * 화면 하나가 만들어진 과정 기록 (요청 1건 = 트레이스 1개).
 * "왜 이 위젯이 떴는지 / 왜 안 떴는지"를 설명하고, 느린 단계를 찾는 데 쓴다.
 * 개인정보 보호를 위해 사용자 원문은 저장하지 않고 길이만 남긴다.
 */
public final class DecisionTrace {

    public record Stage(String name, long durationMs, String note) {}

    public record Candidate(String widget, String choice, Double confidence) {}

    private final String requestId;
    private final Instant startedAt;
    private final long startedNanos = System.nanoTime();
    private final int messageLength;
    private final List<Stage> stages = new ArrayList<>();
    private final List<Candidate> candidates = new ArrayList<>();
    private final Map<String, Object> slots = new LinkedHashMap<>();
    private final Map<String, Double> rankingScores = new LinkedHashMap<>();
    private final Map<String, EnumSet<FeedbackEvent>> feedback = new HashMap<>();
    private boolean resumedFromSession;
    private String provider;
    private String model;
    private boolean selectionNeedsReview;
    private List<String> selected = List.of();
    private List<String> missingSlots = List.of();
    private List<String> rendered = List.of();
    private String status;
    private String error;
    private long totalMs;

    public DecisionTrace(String requestId, Instant startedAt, int messageLength) {
        this.requestId = requestId;
        this.startedAt = startedAt;
        this.messageLength = messageLength;
    }

    public String requestId() { return requestId; }

    public Instant startedAt() { return startedAt; }

    /** startNanos부터 지금까지를 한 단계로 기록 */
    public void stage(String name, long startNanos, String note) {
        stages.add(new Stage(name, (System.nanoTime() - startNanos) / 1_000_000, note));
    }

    public void markResumedFromSession() { this.resumedFromSession = true; }

    public void selection(String provider, String model, boolean needsReview, List<String> selected, List<Candidate> candidates) {
        this.provider = provider;
        this.model = model;
        this.selectionNeedsReview = needsReview;
        this.selected = selected == null ? List.of() : List.copyOf(selected);
        this.candidates.clear();
        this.candidates.addAll(candidates);
    }

    public void slots(Map<String, Object> values) { slots.clear(); values.forEach((k, v) -> { if (v != null) slots.put(k, v); }); }

    public void missingSlots(List<String> missing) { this.missingSlots = List.copyOf(missing); }

    public void ranking(Map<String, Double> scores) { rankingScores.clear(); rankingScores.putAll(scores); }

    public void finish(String status, List<String> rendered) {
        this.status = status;
        this.rendered = List.copyOf(rendered);
        this.totalMs = (System.nanoTime() - startedNanos) / 1_000_000;
    }

    public void fail(Throwable e) {
        this.status = "error";
        this.error = e.getClass().getSimpleName() + (e.getMessage() == null ? "" : ": " + e.getMessage());
        this.totalMs = (System.nanoTime() - startedNanos) / 1_000_000;
    }

    public boolean containsRenderedWidget(String widget) {
        return rendered.contains(widget);
    }

    public synchronized boolean markFeedback(String widget, FeedbackEvent event) {
        return feedback.computeIfAbsent(widget, ignored -> EnumSet.noneOf(FeedbackEvent.class)).add(event);
    }

    public List<Stage> stages() { return List.copyOf(stages); }

    public String status() { return status; }

    public boolean resumedFromSession() { return resumedFromSession; }

    public Map<String, Object> toMap() {
        var map = new LinkedHashMap<String, Object>();
        map.put("requestId", requestId);
        map.put("startedAt", startedAt.toString());
        map.put("messageLength", messageLength);
        map.put("status", status);
        if (error != null) map.put("error", error);
        map.put("totalMs", totalMs);
        map.put("resumedFromSession", resumedFromSession);
        if (provider != null) {
            map.put("selection", Map.of(
                    "provider", provider,
                    "model", model == null ? "-" : model,
                    "needsReview", selectionNeedsReview,
                    "selected", selected,
                    "candidates", candidates));
        }
        map.put("slots", Map.copyOf(slots));
        map.put("missingSlots", missingSlots);
        map.put("rankingScores", Map.copyOf(rankingScores));
        map.put("renderedWidgets", rendered);
        map.put("stages", stages);
        return map;
    }
}
