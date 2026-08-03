package com.llmeval.ludo.engine;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Board position and running counters.
 *
 * <p>Turn number and whose turn it is live in {@link Game}, not here — they survive a
 * three-sixes cancellation, whereas everything in this class is reverted by it.
 */
public final class GameState {

    private Map<Color, int[]> tokens = new EnumMap<>(Color.class);
    private Map<Color, PlayerStats> stats = new EnumMap<>(Color.class);
    private List<Color> finished = new ArrayList<>();

    public GameState() {
        for (Color color : Color.values()) {
            int[] positions = new int[Board.TOKENS_PER_PLAYER];
            Arrays.fill(positions, Board.BASE);
            tokens.put(color, positions);
            stats.put(color, new PlayerStats());
        }
    }

    public Map<Color, int[]> tokens() {
        return tokens;
    }

    public int[] tokens(Color color) {
        return tokens.get(color);
    }

    public Map<Color, PlayerStats> stats() {
        return stats;
    }

    public PlayerStats stats(Color color) {
        return stats.get(color);
    }

    /** Colours that have got all four tokens home, in finishing order. */
    public List<Color> finished() {
        return finished;
    }

    // -- queries ---------------------------------------------------------

    public int tokensHome(Color color) {
        int count = 0;
        for (int position : tokens.get(color)) {
            if (position == Board.HOME) {
                count++;
            }
        }
        return count;
    }

    /** Total steps travelled by all four tokens. Maximum 4 x 57 = 228. */
    public int progress(Color color) {
        int total = 0;
        for (int position : tokens.get(color)) {
            total += Board.tokenProgress(position);
        }
        return total;
    }

    public boolean hasFinished(Color color) {
        return tokensHome(color) == Board.TOKENS_PER_PLAYER;
    }

    // -- snapshot --------------------------------------------------------

    public Snapshot snapshot() {
        return new Snapshot(
                Snapshot.copyTokens(tokens),
                Snapshot.copyStats(stats),
                new ArrayList<>(finished));
    }

    public void restore(Snapshot snap) {
        tokens = Snapshot.copyTokens(snap.tokens());
        stats = Snapshot.copyStats(snap.stats());
        finished = new ArrayList<>(snap.finished());
    }

    // -- standings -------------------------------------------------------

    /**
     * Final or mid-game ranking.
     *
     * <p>Players who finished are ranked by finishing order. Everyone else is ranked by tokens
     * home, then total progress — which is what makes a turn-capped game scoreable rather than
     * void.
     *
     * <p>The tie-break must match Python exactly. Python's {@code sort(..., reverse=True)}
     * reverses the <em>comparison</em>, not the list, so equal entries keep their original
     * order; {@code Comparator.reversed()} on Java's stable sort behaves the same way. Reversing
     * a sorted list instead would flip ties and diverge.
     */
    public List<Map<String, Object>> standings() {
        List<Color> ranked = new ArrayList<>(finished);

        List<Color> rest = new ArrayList<>();
        for (Color color : Color.values()) {
            if (!finished.contains(color)) {
                rest.add(color);
            }
        }
        rest.sort(Comparator
                .comparingInt(this::tokensHome)
                .thenComparingInt((Color c) -> progress(c))
                .reversed());
        ranked.addAll(rest);

        List<Map<String, Object>> result = new ArrayList<>();
        for (int i = 0; i < ranked.size(); i++) {
            Color color = ranked.get(i);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("player", color.label());
            row.put("rank", i + 1);
            row.put("tokens_home", tokensHome(color));
            row.put("progress", progress(color));
            row.put("finished", finished.contains(color));
            row.put("captures_made", stats.get(color).capturesMade);
            row.put("captures_suffered", stats.get(color).capturesSuffered);
            row.put("turns_forfeited", stats.get(color).turnsForfeited);
            result.add(row);
        }
        return result;
    }
}
