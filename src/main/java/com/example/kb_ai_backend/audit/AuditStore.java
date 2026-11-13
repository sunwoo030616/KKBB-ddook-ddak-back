package com.example.kb_ai_backend.audit;

import java.util.List;

public interface AuditStore {
    record Head(long size, String hash) {}

    Head head();

    /** Append only if the supplied head still identifies the end of the chain. */
    boolean append(Head expected, AuditEntry entry);

    List<AuditEntry> entries();
}
