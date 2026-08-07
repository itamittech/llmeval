package com.llmeval.alibi.engine;

import java.util.List;
import java.util.Map;

/** How a case ended: reason, length, the revealed truth, and the ranked table. */
public record Outcome(String reason, int turnsPlayed, Map<String, String> solution,
                      List<Map<String, Object>> standings) {

    /** The solver, or null when the case went unsolved. */
    public Color winner() {
        Map<String, Object> top = standings.get(0);
        if (Boolean.TRUE.equals(top.get("solved"))) {
            for (Color color : Color.values()) {
                if (color.json().equals(top.get("player"))) {
                    return color;
                }
            }
        }
        return null;
    }
}
