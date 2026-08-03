package com.llmeval.ludo.engine;

import java.util.List;

/**
 * Everything a decider is allowed to see when choosing a move.
 *
 * @param attempt 1 on the first ask, 2 after an illegal move was rejected
 */
public record TurnContext(
        StateView state,
        Color color,
        int die,
        List<Move> legalMoves,
        int turn,
        int attempt) {

    public TurnContext(StateView state, Color color, int die, List<Move> legalMoves, int turn) {
        this(state, color, die, legalMoves, turn, 1);
    }
}
