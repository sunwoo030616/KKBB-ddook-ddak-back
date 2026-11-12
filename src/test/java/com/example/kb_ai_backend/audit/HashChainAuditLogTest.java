package com.example.kb_ai_backend.audit;

import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class HashChainAuditLogTest {
    Clock clock = Clock.fixed(Instant.parse("2026-11-12T05:00:00Z"), ZoneOffset.UTC);

    HashChainAuditLog sample() {
        var log = new HashChainAuditLog(clock);
        log.append("ACTION_PREPARED", "u1", "a1", Map.of("type", "CARD_UNFREEZE_ALL", "decision", "STEP_UP"));
        log.append("OTP_FAILED", "u1", "a1", Map.of("attempt", 1, "otp", "123456"));
        log.append("ACTION_EXECUTED", "u1", "a1", Map.of("result", "OK"));
        return log;
    }

    @Test void untouchedChainVerifies() {
        var result = sample().verify();
        assertTrue(result.valid());
        assertEquals(3, result.size());
        assertNull(result.brokenAtSeq());
        assertEquals(64, result.headHash().length());
    }

    @Test void entriesAreLinkedToPreviousHash() {
        var entries = sample().entries();
        assertEquals(HashChainAuditLog.GENESIS, entries.get(0).prevHash());
        assertEquals(entries.get(0).hash(), entries.get(1).prevHash());
        assertEquals(entries.get(1).hash(), entries.get(2).prevHash());
    }

    @Test void modifyingOneEntryIsDetectedAtThatEntry() {
        var entries = new ArrayList<>(sample().entries());
        var original = entries.get(1);
        entries.set(1, new AuditEntry(original.seq(), original.at(), "OTP_PASSED", original.actor(),
                original.subject(), original.details(), original.prevHash(), original.hash()));

        var result = HashChainAuditLog.verify(entries);
        assertFalse(result.valid());
        assertEquals(2L, result.brokenAtSeq());
    }

    @Test void deletingEntryIsDetected() {
        var entries = new ArrayList<>(sample().entries());
        entries.remove(1);
        var result = HashChainAuditLog.verify(entries);
        assertFalse(result.valid());
        assertEquals(3L, result.brokenAtSeq());
    }

    @Test void sensitiveValuesAreMaskedBeforeHashing() {
        var log = sample();
        assertEquals("***", log.entries().get(1).details().get("otp"));
        assertEquals("1", log.entries().get(1).details().get("attempt"));
    }

    @Test void entriesCanBeFilteredBySubject() {
        var log = sample();
        log.append("ACTION_PREPARED", "u2", "a2", Map.of());
        assertEquals(3, log.entriesFor("a1").size());
        assertEquals(1, log.entriesFor("a2").size());
    }
}
