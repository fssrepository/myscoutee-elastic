package com.example.domain.notifications;

import java.util.ArrayList;
import java.util.List;

/** A fictional delivery outbox with retryable entries. */
public class NotificationOutbox {
    private final List<String> pending = new ArrayList<>();

    public void add(String message) {
        pending.add(message);
    }

    public List<String> drain() {
        var batch = List.copyOf(pending);
        pending.clear();
        return batch;
    }
}
