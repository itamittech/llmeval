package com.llmeval.ludo.engine;

import java.util.ArrayList;
import java.util.List;

/**
 * Legal move generation and application — the rulebook.
 *
 * <p>Everything enforced here is specified in {@code docs/projects/ludo/game-rules.md},
 * including the edge cases resolved there. Both engines implement that document; neither is
 * the authority.
 */
public final class Moves {

    private Moves() {}

    /**
     * Every move {@code color} may make with {@code die}, ordered by token index.
     *
     * <p>The order is stable and part of the engine's contract: the deterministic
     * {@link FirstLegal} decider used by conformance vectors depends on it.
     */
    public static List<Move> legalMoves(GameState state, Color color, int die) {
        List<Move> moves = new ArrayList<>();
        int[] positions = state.tokens(color);

        for (int token = 0; token < positions.length; token++) {
            int pos = positions[token];
            if (pos == Board.HOME) {
                continue;
            }

            if (pos == Board.BASE) {
                // Only a 6 releases a token, and only onto its own start square.
                if (die == 6 && canLand(state, color, Board.START)) {
                    moves.add(new Move(token, Board.BASE, Board.START));
                }
                continue;
            }

            int target = pos + die;
            if (target > Board.HOME) {
                continue; // home must be reached by exact count
            }
            if (!pathClear(state, color, pos, target)) {
                continue;
            }
            if (!canLand(state, color, target)) {
                continue;
            }
            moves.add(new Move(token, pos, target));
        }

        return moves;
    }

    /** Move a token and resolve any capture. Assumes {@code move} is legal. */
    public static List<Capture> applyMove(GameState state, Color color, Move move) {
        state.tokens(color)[move.token()] = move.to();

        Integer square = Board.toSquare(color, move.to());
        if (square == null || Board.isSafe(square)) {
            return List.of();
        }

        List<Capture> captures = new ArrayList<>();
        for (Color other : Color.values()) {
            if (other == color) {
                continue;
            }
            int[] positions = state.tokens(other);
            for (int j = 0; j < positions.length; j++) {
                if (square.equals(Board.toSquare(other, positions[j]))) {
                    positions[j] = Board.BASE;
                    captures.add(new Capture(other, j, square));
                    state.stats(other).capturesSuffered++;
                    state.stats(color).capturesMade++;
                }
            }
        }

        return captures;
    }

    // -- internals ------------------------------------------------------------

    /**
     * Two or more tokens of one other colour: impassable and unlandable.
     *
     * <p>Blocks apply on safe squares too, and never obstruct their own owner.
     */
    private static boolean opponentBlock(GameState state, Color color, int square) {
        for (Color other : Color.values()) {
            if (other == color) {
                continue;
            }
            int count = 0;
            for (int position : state.tokens(other)) {
                Integer at = Board.toSquare(other, position);
                if (at != null && at == square) {
                    count++;
                }
            }
            if (count >= 2) {
                return true;
            }
        }
        return false;
    }

    private static boolean canLand(GameState state, Color color, int position) {
        Integer square = Board.toSquare(color, position);
        if (square == null) {
            return true; // home column and home are private to this colour
        }
        return !opponentBlock(state, color, square);
    }

    /** Check the squares strictly between {@code frm} and {@code to} for opponent blocks. */
    private static boolean pathClear(GameState state, Color color, int frm, int to) {
        for (int position = frm + 1; position < to; position++) {
            if (position > Board.LAST_CIRCUIT) {
                break; // home column: no opponent can be there
            }
            Integer square = Board.toSquare(color, position);
            if (square != null && opponentBlock(state, color, square)) {
                return false;
            }
        }
        return true;
    }
}
