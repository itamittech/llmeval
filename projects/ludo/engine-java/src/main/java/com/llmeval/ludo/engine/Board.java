package com.llmeval.ludo.engine;

import java.util.EnumMap;
import java.util.Map;
import java.util.Set;

/**
 * Board geometry and coordinate mapping.
 *
 * <p>Positions are <strong>colour-relative</strong>: every colour measures from its own start
 * square, so movement logic is identical for all four players. Absolute circuit squares are
 * derived only where colours must interact — capture and blocking.
 *
 * <pre>
 * -1        base (off the board)
 *  0        start square
 *  0..50    main circuit, 51 squares
 * 51..55    home column
 * 56        home triangle
 * </pre>
 *
 * <p>A token therefore takes 56 steps from its start square to home, occupying 57 distinct
 * positions. It traverses 51 of the circuit's 52 squares, turning into its home column one
 * square short of a full loop.
 */
public final class Board {

    public static final int CIRCUIT_SIZE = 52;
    public static final int TOKENS_PER_PLAYER = 4;

    public static final int BASE = -1;
    public static final int START = 0;
    public static final int LAST_CIRCUIT = 50;
    public static final int HOME_ENTRY = 51;
    public static final int HOME = 56;

    /** Where each colour joins the circuit. Evenly spaced, 13 apart. */
    private static final Map<Color, Integer> START_SQUARE = new EnumMap<>(Color.class);

    static {
        START_SQUARE.put(Color.RED, 0);
        START_SQUARE.put(Color.GREEN, 13);
        START_SQUARE.put(Color.YELLOW, 26);
        START_SQUARE.put(Color.BLUE, 39);
    }

    /** The four start squares plus a star square 8 ahead of each. No capture here. */
    public static final Set<Integer> SAFE_SQUARES = Set.of(0, 8, 13, 21, 26, 34, 39, 47);

    private Board() {}

    /**
     * Absolute circuit square for a colour-relative position.
     *
     * <p>Returns {@code null} when the token is not on the shared circuit — in its base, its home
     * column, or home — because those are private to one colour and cannot interact with anyone
     * else. Nullable rather than {@code OptionalInt} because this value flows straight into the
     * event stream, where absent means JSON {@code null}.
     */
    public static Integer toSquare(Color color, int position) {
        if (position < START || position > LAST_CIRCUIT) {
            return null;
        }
        return (START_SQUARE.get(color) + position) % CIRCUIT_SIZE;
    }

    public static boolean isSafe(Integer square) {
        return square != null && SAFE_SQUARES.contains(square);
    }

    /**
     * Steps travelled, counting the start square as 1 and home as 57.
     *
     * <p>Base is 0, so leaving the base always registers as progress.
     */
    public static int tokenProgress(int position) {
        return position == BASE ? 0 : position + 1;
    }
}
