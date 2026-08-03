package com.llmeval.ludo.engine;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/**
 * A read-only window onto {@link GameState}, handed to deciders.
 *
 * <p>An agent may inspect the board; it may not change it. Arrays are cloned and lists wrapped,
 * so a decider that writes to what it was given corrupts only its own copy.
 *
 * <p><strong>Honest about the limit</strong>, exactly as in Python. Java's access control is
 * stronger than a leading underscore, but reflection still gets through, and nothing here stops
 * a decider that holds a {@link GameState} from another route. The point is that cheating
 * requires obviously-wrong code a reviewer will spot. The guarantee that actually matters is
 * that the <em>LLM</em> can only ever return a move choice, which the engine validates
 * regardless (ADR-0004).
 */
public final class StateView {

    private final GameState state;

    StateView(GameState state) {
        this.state = state;
    }

    /** One colour's four token positions. A copy — writing to it changes nothing. */
    public int[] tokens(Color color) {
        return state.tokens(color).clone();
    }

    /** Every colour's positions — the full public board. */
    public Map<Color, int[]> board() {
        Map<Color, int[]> copy = new EnumMap<>(Color.class);
        state.tokens().forEach((color, positions) -> copy.put(color, positions.clone()));
        return copy;
    }

    public int tokensHome(Color color) {
        return state.tokensHome(color);
    }

    public int progress(Color color) {
        return state.progress(color);
    }

    public boolean hasFinished(Color color) {
        return state.hasFinished(color);
    }

    /** Colours that are already home, in finishing order. */
    public List<Color> finished() {
        return List.copyOf(state.finished());
    }

    /** A copy — mutating it changes nothing. */
    public PlayerStats stats(Color color) {
        return state.stats(color).copy();
    }
}
