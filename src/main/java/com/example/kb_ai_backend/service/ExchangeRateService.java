package com.example.kb_ai_backend.service;

import org.springframework.stereotype.Service;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;
import java.math.BigDecimal;
import java.math.MathContext;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.function.LongSupplier;

/** Public indicative FX quotes, immutable snapshots, single-flight refresh and outage backoff. */
@Service
public class ExchangeRateService {
    static final String API_URL = "https://open.er-api.com/v6/latest/KRW";
    private final RestTemplate http;
    private final long ttlMillis;
    private final long retryMillis;
    private final LongSupplier clock;
    private final Object refreshLock = new Object();
    private volatile Snapshot snapshot;
    private volatile long lastAttempt = -1;
    private record Snapshot(Map<String,BigDecimal> rates, long fetchedAt, Instant sourceUpdatedAt) {}
    public record Quote(String currency, BigDecimal krwPerUnit, Instant fetchedAt, Instant sourceUpdatedAt, boolean stale, String source) {}

    public ExchangeRateService() { this(createHttp(), 21600000L, 60000L, System::currentTimeMillis); }
    ExchangeRateService(RestTemplate http, long ttlMillis, long retryMillis, LongSupplier clock) {
        this.http=http;this.ttlMillis=ttlMillis;this.retryMillis=retryMillis;this.clock=clock;
    }
    private static RestTemplate createHttp() {
        var factory=new SimpleClientHttpRequestFactory();factory.setConnectTimeout(2000);factory.setReadTimeout(3000);
        return new RestTemplate(factory);
    }
    public Double getKrwRateFor(String code) { var quote=getQuote(code);return quote==null?null:quote.krwPerUnit().doubleValue(); }
    public Quote getQuote(String currency) {
        if(currency==null || !currency.toUpperCase().matches("[A-Z]{3}"))return null;
        String code=currency.toUpperCase();
        var current=snapshot;
        if(current==null || clock.getAsLong()-current.fetchedAt()>=ttlMillis)refresh();
        current=snapshot;
        if(current==null)return null;
        var value=current.rates().get(code);if(value==null)return null;
        return new Quote(code,BigDecimal.ONE.divide(value,MathContext.DECIMAL128),Instant.ofEpochMilli(current.fetchedAt()),
                         current.sourceUpdatedAt(),clock.getAsLong()-current.fetchedAt()>=ttlMillis,API_URL);
    }
    @SuppressWarnings("unchecked")
    private void refresh() {
        synchronized(refreshLock) {
            long now=clock.getAsLong();var current=snapshot;
            if(current!=null && now-current.fetchedAt()<ttlMillis)return;
            if(lastAttempt>=0 && now-lastAttempt<retryMillis)return;
            lastAttempt=now;
            try {
                Map<String,Object> response=http.getForObject(API_URL,Map.class);
                if(response==null || !"success".equals(response.get("result")) || !"KRW".equals(response.get("base_code")))return;
                if(!(response.get("rates") instanceof Map<?,?> raw))return;
                Map<String,BigDecimal> parsed=new HashMap<>();
                for(var entry:raw.entrySet()) {
                    if(!(entry.getKey() instanceof String code) || !code.matches("[A-Z]{3}") || !(entry.getValue() instanceof Number n))continue;
                    double number=n.doubleValue();if(!Double.isFinite(number) || number<=0)continue;
                    parsed.put(code,new BigDecimal(n.toString()));
                }
                if(parsed.isEmpty())return;
                Instant updated=response.get("time_last_update_unix") instanceof Number n?Instant.ofEpochSecond(n.longValue()):null;
                snapshot=new Snapshot(Map.copyOf(parsed),clock.getAsLong(),updated);
            } catch(Exception ignored) {
                // Preserve the last valid snapshot, clearly marked stale. Do not log provider bodies.
            }
        }
    }
}
