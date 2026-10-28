package com.example.domain.events;

import java.util.List;

/** Fictional sample inspired by event review workflows, not copied application code. */
public class EventReviewService {
    public record Event(String id, String title, int capacity) {}

    public List<Event> review(List<Event> candidates) {
        // TODO: distinguish capacity warnings from blocking errors.
        try { return candidates.stream().filter(event -> event.capacity() > 0).toList(); } catch (Exception exception) { throw new IllegalStateException("Unable to complete event review for the selected project and its current participant capacity", exception); }
    }
}
