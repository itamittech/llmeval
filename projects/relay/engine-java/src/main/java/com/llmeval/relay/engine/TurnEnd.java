package com.llmeval.relay.engine;

import java.util.List;
import java.util.Map;

/** Handed to a {@link Reflector} once its own turn has resolved. */
public record TurnEnd(RunnerView view, String color, int turn, String reason,
                      List<Map<String, Object>> events) {

    public TurnEnd {
        events = List.copyOf(events);
    }
}
