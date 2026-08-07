package com.llmeval.alibi.engine;

import java.util.Map;

/**
 * Game parameters plus the provenance the harness supplies. Optional blocks are null on
 * engine-only runs and then omitted from {@code game_started}, which is what keeps the
 * conformance vectors byte-stable.
 */
public record GameConfig(int seed, int maxTurns, int maxSearchesPerTurn, String ruleset,
                         String stack, Map<Color, Map<String, Object>> players,
                         String profile, Map<String, Object> promptSet,
                         Map<String, Object> framework, Map<String, Object> archivist) {

    public GameConfig(int seed, int maxTurns) {
        this(seed, maxTurns, 2, "baseline", "none", Map.of(), null, null, null, null);
    }
}
