package com.example.kb_ai_backend.feedback;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.LongAdder;

/**
 * 위젯별 반응을 모아 "선택된 위젯들의 순서"만 보정한다.
 * 어떤 위젯을 띄울지는 jev와 서버 검증이 정하고, 여기서는 추가·삭제하지 않는다.
 *
 * 점수 = (min(클릭 + 0.5 × 완료, 노출) + 1) / (노출 + 닫기 + 2)
 *  - 기본은 클릭률, 업무를 끝까지 마친 경우 가산점, 닫기는 감점
 *  - +1, +2는 라플라스 보정: 데이터가 적을 때 한두 번의 클릭으로 순위가 뒤집히지 않게 함
 *  - 노출이 minExposures 미만이면 중립값 0.5를 써서 원래 순서를 유지
 */
public class FeedbackRanker {

    public static final double NEUTRAL = 0.5;

    public record Stats(long shown, long clicked, long completed, long dismissed, double score) {}

    private static final class Counter {
        final LongAdder shown = new LongAdder();
        final LongAdder clicked = new LongAdder();
        final LongAdder completed = new LongAdder();
        final LongAdder dismissed = new LongAdder();
    }

    private final Set<String> knownWidgets;
    private final int minExposures;
    private final ConcurrentHashMap<String, Counter> counters = new ConcurrentHashMap<>();

    public FeedbackRanker(Set<String> knownWidgets, int minExposures) {
        if (minExposures < 0) throw new IllegalArgumentException("minExposures는 0 이상");
        this.knownWidgets = Set.copyOf(knownWidgets);
        this.minExposures = minExposures;
    }

    public boolean supports(String widget) {
        return widget != null && knownWidgets.contains(widget);
    }

    /** 허용 목록에 없는 위젯 이름은 받지 않는다 (임의 키로 메모리가 늘어나는 것 방지) */
    public void record(String widget, FeedbackEvent event) {
        if (!supports(widget)) throw new IllegalArgumentException("알 수 없는 위젯입니다: " + widget);
        Counter c = counters.computeIfAbsent(widget, k -> new Counter());
        switch (event) {
            case SHOWN -> c.shown.increment();
            case CLICKED -> c.clicked.increment();
            case COMPLETED -> c.completed.increment();
            case DISMISSED -> c.dismissed.increment();
        }
    }

    public double score(String widget) {
        return stats(widget).score();
    }

    public Stats stats(String widget) {
        Counter c = counters.get(widget);
        if (c == null) return new Stats(0, 0, 0, 0, NEUTRAL);
        long shown = c.shown.sum(), clicked = c.clicked.sum(), completed = c.completed.sum(), dismissed = c.dismissed.sum();
        double score = shown < minExposures ? NEUTRAL
                : (Math.min(clicked + 0.5 * completed, shown) + 1.0) / (shown + dismissed + 2.0);
        return new Stats(shown, clicked, completed, dismissed, score);
    }

    /** 점수 내림차순, 같으면 원래 순서 유지 (안정 정렬) */
    public List<String> rank(List<String> widgets) {
        var scores = scores(widgets);
        var ordered = new ArrayList<>(widgets);
        ordered.sort(Comparator.comparingDouble((String w) -> scores.get(w)).reversed());
        return ordered;
    }

    public Map<String, Double> scores(List<String> widgets) {
        var scores = new LinkedHashMap<String, Double>();
        widgets.forEach(w -> scores.put(w, score(w)));
        return scores;
    }

    public Map<String, Stats> snapshot() {
        var all = new TreeMap<String, Stats>();
        knownWidgets.forEach(w -> all.put(w, stats(w)));
        return all;
    }
}
