package com.llmeval.ludo.engine;

import java.util.EnumMap;
import java.util.Map;

/**
 * Everything a game needs before it starts.
 *
 * @param players per-colour metadata for the {@code game_started} event (agent name, model,
 *                access route)
 * @param profile named profile from shared/models.yaml; null on engine-only runs
 * @param promptSet {@code {"version", "hash"}} of the prompt set that produced this game;
 *                  null on engine-only runs, and then OMITTED from the event — which is what
 *                  keeps the conformance vectors byte-stable
 * @param framework {@code {"name", "version"}} of the agent framework build; null on
 *                  engine-only runs
 */
public record GameConfig(
        int seed,
        int maxTurns,
        String ruleset,
        String stack,
        Map<Color, Map<String, Object>> players,
        String profile,
        Map<String, Object> promptSet,
        Map<String, Object> framework) {

    public GameConfig {
        players = players == null ? new EnumMap<>(Color.class) : players;
    }

    public GameConfig(int seed, int maxTurns, String ruleset, String stack,
                      Map<Color, Map<String, Object>> players) {
        this(seed, maxTurns, ruleset, stack, players, null, null, null);
    }

    public GameConfig(int seed, int maxTurns) {
        this(seed, maxTurns, "baseline", "none", new EnumMap<>(Color.class));
    }
}
