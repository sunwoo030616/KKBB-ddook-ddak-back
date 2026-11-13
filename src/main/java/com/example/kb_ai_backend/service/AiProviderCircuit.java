package com.example.kb_ai_backend.service;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.OptionalLong;

/** One circuit per provider. Tickets from before opening cannot close an open circuit. */
final class AiProviderCircuit {
    private final Clock clock;
    private final int threshold;
    private final Duration cooldown;
    private long generation;
    private int failures;
    private Instant retryAt;
    private boolean probing;

    AiProviderCircuit(Clock clock, int threshold, Duration cooldown) {
        if (threshold < 1 || cooldown.isNegative() || cooldown.isZero()) {
            throw new IllegalArgumentException("AI circuit threshold and cooldown must be positive");
        }
        this.clock = clock;
        this.threshold = threshold;
        this.cooldown = cooldown;
    }

    synchronized OptionalLong acquire() {
        if (retryAt == null) return OptionalLong.of(generation);
        if (probing || clock.instant().isBefore(retryAt)) return OptionalLong.empty();
        probing = true;
        return OptionalLong.of(generation);
    }

    synchronized void finish(long ticket, boolean providerFailure) {
        if (ticket != generation) return;
        if (!providerFailure) {
            if (probing) generation++;
            retryAt = null;
            probing = false;
            failures = 0;
        } else if (probing || ++failures >= threshold) {
            generation++;
            retryAt = clock.instant().plus(cooldown);
            probing = false;
            failures = 0;
        }
    }
}
