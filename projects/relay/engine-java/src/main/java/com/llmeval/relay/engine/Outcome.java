package com.llmeval.relay.engine;

import java.util.List;
import java.util.Map;

/** How a race ended, and where everyone finished. */
public record Outcome(String reason, int turnsPlayed, List<Map<String, Object>> standings) {

    public String winner() {
        Map<String, Object> top = standings.get(0);
        return Boolean.TRUE.equals(top.get("finished")) ? (String) top.get("player") : null;
    }
}
