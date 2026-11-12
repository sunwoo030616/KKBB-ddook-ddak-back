package com.example.kb_ai_backend.service;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

class ExchangeRateServiceTest {

    private static class MutableClock extends Clock {
        private volatile Instant now = Instant.parse("2026-11-12T02:00:00Z");

        void advance(Duration by) { now = now.plus(by); }

        @Override public Instant instant() { return now; }
        @Override public ZoneId getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(ZoneId zone) { return Clock.fixed(now, zone); }
    }

    @Test void cachesValidRatesAndRejectsInvalidRates() {
        var clock = new MutableClock();
        var calls = new AtomicInteger();
        var service = new ExchangeRateService(clock, Optional.empty(), () -> {
            calls.incrementAndGet();
            return Map.of("rates", Map.of("JPY", 0.125, "EUR", Double.NaN, "CAD", -1));
        });

        assertEquals(new ExchangeRateService.Quote(8.0, false, false), service.getKrwQuoteFor("jpy"));
        assertNull(service.getKrwQuoteFor("EUR"));
        assertNull(service.getKrwQuoteFor("CAD"));
        assertEquals(1, calls.get());
    }

    @Test void concurrentRequestsUseCachedRateDuringTheSingleRefresh() throws Exception {
        var clock = new MutableClock();
        var calls = new AtomicInteger();
        var refreshing = new CountDownLatch(1);
        var finishRefresh = new CountDownLatch(1);
        var service = new ExchangeRateService(clock, Optional.empty(), () -> {
            if (calls.incrementAndGet() == 1) return Map.of("rates", Map.of("JPY", 0.125));
            refreshing.countDown();
            await(finishRefresh);
            return Map.of("rates", Map.of("JPY", 0.1));
        });
        assertEquals(8.0, service.getKrwQuoteFor("JPY").rate());
        clock.advance(Duration.ofHours(6));

        var pool = Executors.newFixedThreadPool(2);
        try {
            var first = pool.submit(() -> service.getKrwQuoteFor("JPY"));
            await(refreshing);
            var second = pool.submit(() -> service.getKrwQuoteFor("JPY"));
            assertEquals(new ExchangeRateService.Quote(8.0, true, false), second.get(2, TimeUnit.SECONDS));
            assertEquals(2, calls.get());
            finishRefresh.countDown();
            assertEquals(new ExchangeRateService.Quote(10.0, false, false), first.get(2, TimeUnit.SECONDS));
        } finally {
            finishRefresh.countDown();
            pool.shutdownNow();
        }
    }

    @Test void failuresKeepUsableDataAndBackOffButStopServingAfterMaximumAge() {
        var clock = new MutableClock();
        var calls = new AtomicInteger();
        var service = new ExchangeRateService(clock, Optional.empty(), () -> {
            if (calls.incrementAndGet() == 1) return Map.of("rates", Map.of("JPY", 0.125));
            throw new IllegalStateException("unavailable");
        });
        assertEquals(8.0, service.getKrwQuoteFor("JPY").rate());
        clock.advance(Duration.ofHours(6));

        assertTrue(service.getKrwQuoteFor("JPY").stale());
        assertTrue(service.getKrwQuoteFor("JPY").stale());
        assertEquals(2, calls.get());
        clock.advance(Duration.ofHours(18));

        assertNull(service.getKrwQuoteFor("JPY"));
        assertNull(service.getKrwQuoteFor("JPY"));
        assertEquals(3, calls.get());
    }

    private static void await(CountDownLatch latch) {
        try {
            if (!latch.await(5, TimeUnit.SECONDS)) throw new AssertionError("refresh did not reach the expected stage");
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new AssertionError(error);
        }
    }
}
