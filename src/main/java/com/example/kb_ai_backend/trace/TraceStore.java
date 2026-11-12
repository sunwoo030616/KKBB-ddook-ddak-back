package com.example.kb_ai_backend.trace;

import java.time.Clock;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/** 최근 트레이스만 보관 (개수 상한 + 보관 기간). 오래된 것부터 버린다. */
public class TraceStore {

    private final Clock clock;
    private final Duration retention;
    private final LinkedHashMap<String, DecisionTrace> traces;

    public TraceStore(Clock clock, Duration retention, int maxTraces) {
        this.clock = clock;
        this.retention = retention;
        this.traces = new LinkedHashMap<>(16, 0.75f, false) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, DecisionTrace> eldest) {
                return size() > maxTraces;
            }
        };
    }

    public synchronized void save(DecisionTrace trace) {
        traces.put(trace.requestId(), trace);
    }

    public synchronized Optional<DecisionTrace> find(String requestId) {
        DecisionTrace trace = traces.get(requestId);
        if (trace == null) return Optional.empty();
        if (trace.startedAt().plus(retention).isBefore(clock.instant())) {
            traces.remove(requestId);
            return Optional.empty();
        }
        return Optional.of(trace);
    }
}
