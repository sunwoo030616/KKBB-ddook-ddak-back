package com.example.kb_ai_backend.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.Supplier;

/** 외부 환율을 캐시하고 만료 후 한 요청만 갱신한다. */
@Service
public class ExchangeRateService {

    private static final Logger log = LoggerFactory.getLogger(ExchangeRateService.class);
    private static final String API_URL = "https://open.er-api.com/v6/latest/KRW";
    private static final Duration CACHE_TTL = Duration.ofHours(6);
    private static final Duration MAX_AGE = Duration.ofHours(24);
    private static final Duration RETRY_DELAY = Duration.ofSeconds(30);

    public record Quote(double rate, boolean stale, boolean demo) {}

    private record Snapshot(Map<String, Double> rates, Instant fetchedAt, Instant retryAt) {
        boolean isUsableAt(Instant now) {
            return fetchedAt != null && now.isBefore(fetchedAt.plus(MAX_AGE));
        }

        boolean isFreshAt(Instant now) {
            return fetchedAt != null && now.isBefore(fetchedAt.plus(CACHE_TTL));
        }

        Quote quote(String currency, Instant now) {
            Double rate = isUsableAt(now) ? rates.get(currency) : null;
            return rate == null ? null : new Quote(rate, !isFreshAt(now), false);
        }
    }

    private final Clock clock;
    private final Optional<PresentationScenarios> presentation;
    private final Supplier<Map<?, ?>> fetchRates;
    private final ReentrantLock refreshLock = new ReentrantLock();
    private volatile Snapshot cache = new Snapshot(Map.of(), null, Instant.MIN);

    @Autowired
    public ExchangeRateService(Clock clock, Optional<PresentationScenarios> presentation) {
        this(clock, presentation, newRateFetcher());
    }

    ExchangeRateService(Clock clock, Optional<PresentationScenarios> presentation, Supplier<Map<?, ?>> fetchRates) {
        this.clock = clock;
        this.presentation = presentation;
        this.fetchRates = fetchRates;
    }

    /** 1 외화 단위당 원화 환율. 지원하지 않거나 유효한 데이터가 없으면 null. */
    public Quote getKrwQuoteFor(String currencyCode) {
        if (currencyCode == null || currencyCode.isBlank()) return null;
        String currency = currencyCode.strip().toUpperCase(Locale.ROOT);
        if (presentation.isPresent()) {
            Double rate = presentation.get().exchangeRate(currency);
            return rate == null ? null : new Quote(rate, false, true);
        }

        var now = clock.instant();
        var current = cache;
        if (current.isFreshAt(now) || now.isBefore(current.retryAt())) return current.quote(currency, now);

        if (current.isUsableAt(now)) {
            if (!refreshLock.tryLock()) return current.quote(currency, now);
        } else {
            // 첫 요청 또는 너무 오래된 캐시만 갱신을 기다린다.
            refreshLock.lock();
        }

        try {
            now = clock.instant();
            current = cache;
            if (!current.isFreshAt(now) && !now.isBefore(current.retryAt())) refresh(current);
            return cache.quote(currency, clock.instant());
        } finally {
            refreshLock.unlock();
        }
    }

    private void refresh(Snapshot previous) {
        long started = System.nanoTime();
        boolean refreshed = false;
        try {
            var parsed = parse(fetchRates.get());
            if (!parsed.isEmpty()) {
                cache = new Snapshot(parsed, clock.instant(), Instant.MIN);
                refreshed = true;
            }
        } catch (RuntimeException error) {
            log.warn("exchange_refresh_failed requestId={} errorType={}", MDC.get("requestId"), error.getClass().getSimpleName());
        } finally {
            if (!refreshed) cache = new Snapshot(previous.rates(), previous.fetchedAt(), clock.instant().plus(RETRY_DELAY));
            log.info("performance requestId={} stage=exchange_refresh durationMs={} refreshed={}",
                    MDC.get("requestId"), TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started), refreshed);
        }
    }

    private static Map<String, Double> parse(Map<?, ?> response) {
        if (response == null || !(response.get("rates") instanceof Map<?, ?> rates)) return Map.of();
        var parsed = new HashMap<String, Double>();
        rates.forEach((currency, rate) -> {
            if (currency instanceof String code && rate instanceof Number number) {
                double raw = number.doubleValue();
                double krw = 1.0 / raw;
                if (raw > 0 && Double.isFinite(raw) && Double.isFinite(krw)) {
                    parsed.put(code.toUpperCase(Locale.ROOT), krw);
                }
            }
        });
        return Map.copyOf(parsed);
    }

    private static Supplier<Map<?, ?>> newRateFetcher() {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(2_000);
        factory.setReadTimeout(3_000);
        var client = new RestTemplate(factory);
        return () -> client.getForObject(API_URL, Map.class);
    }
}
