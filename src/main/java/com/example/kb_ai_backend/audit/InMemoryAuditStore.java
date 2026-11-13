package com.example.kb_ai_backend.audit;

import java.util.ArrayList;
import java.util.List;

final class InMemoryAuditStore implements AuditStore {
    private final List<AuditEntry> entries = new ArrayList<>();

    @Override
    public synchronized Head head() {
        return new Head(entries.size(), entries.isEmpty() ? HashChainAuditLog.GENESIS
                : entries.get(entries.size() - 1).hash());
    }

    @Override
    public synchronized boolean append(Head expected, AuditEntry entry) {
        if (!head().equals(expected)) return false;
        entries.add(entry);
        return true;
    }

    @Override
    public synchronized List<AuditEntry> entries() {
        return List.copyOf(entries);
    }
}
