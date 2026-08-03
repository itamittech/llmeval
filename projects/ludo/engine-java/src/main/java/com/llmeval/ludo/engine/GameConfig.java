package com.llmeval.ludo.engine;

import java.util.EnumMap;
import java.util.Map;

/**
 * Everything a game needs before it starts.
 *
 * @param players per-colour metadata for the {@code game_started} event (agent name, model,
 *                access route)
 */
public record GameConfig(
        int seed,
        int maxTurns,
        String ruleset,
        String stack,
        Map<Color, Map<String, Object>> players) {

    public GameConfig {
        players = players == null ? new EnumMap<>(Color.class) : players;
    }

    public GameConfig(int seed, int maxTurns) {
        this(seed, maxTurns, "baseline", "none", new EnumMap<>(Color.class));
    }
}
