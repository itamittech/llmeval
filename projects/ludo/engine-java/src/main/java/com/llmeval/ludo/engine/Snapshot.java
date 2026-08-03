package com.llmeval.ludo.engine;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/**
 * Everything three consecutive sixes must undo.
 *
 * <p>A {@code record} matches Python's {@code @dataclass(frozen=True)} — but the freezing is
 * shallow in both languages. The arrays and maps inside are still mutable, so
 * {@link GameState#snapshot()} copies their contents rather than storing references. Without
 * that copy the rollback silently does nothing, which is the single easiest bug to introduce
 * here.
 */
public record Snapshot(
        Map<Color, int[]> tokens,
        Map<Color, PlayerStats> stats,
        List<Color> finished) {

    static Map<Color, int[]> copyTokens(Map<Color, int[]> source) {
        Map<Color, int[]> copy = new EnumMap<>(Color.class);
        source.forEach((color, positions) -> copy.put(color, positions.clone()));
        return copy;
    }

    static Map<Color, PlayerStats> copyStats(Map<Color, PlayerStats> source) {
        Map<Color, PlayerStats> copy = new EnumMap<>(Color.class);
        source.forEach((color, stats) -> copy.put(color, stats.copy()));
        return copy;
    }
}
