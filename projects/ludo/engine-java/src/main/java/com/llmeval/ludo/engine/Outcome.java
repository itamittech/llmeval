package com.llmeval.ludo.engine;

import java.util.List;
import java.util.Map;

/** How a game ended. */
public record Outcome(String reason, int turnsPlayed, List<Map<String, Object>> standings) {

    /** First place. Python exposes this as a {@code @property}; Java as a plain accessor. */
    public String winner() {
        return (String) standings.get(0).get("player");
    }
}
