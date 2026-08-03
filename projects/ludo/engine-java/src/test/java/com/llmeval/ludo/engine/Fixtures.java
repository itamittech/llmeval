package com.llmeval.ludo.engine;

import java.util.EnumMap;
import java.util.Map;
import java.util.function.IntSupplier;

/** Shared test helpers. */
final class Fixtures {

    private Fixtures() {}

    static Map<Color, Decider> firstLegal() {
        Map<Color, Decider> deciders = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            deciders.put(color, new FirstLegal());
        }
        return deciders;
    }

    static Map<Color, Decider> allOf(Decider decider) {
        Map<Color, Decider> deciders = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            deciders.put(color, decider);
        }
        return deciders;
    }

    /**
     * Deterministic dice for rules that are hard to reach by luck.
     *
     * <p>Python's tests assign {@code game.dice} on a live object; Java needs the seam the
     * package-private {@link Game} constructor provides.
     */
    static IntSupplier scriptedDice(int[] script, int tail) {
        return new IntSupplier() {
            private int index;

            @Override
            public int getAsInt() {
                return index < script.length ? script[index++] : tail;
            }
        };
    }

    static Game gameWithDice(GameConfig config, EventSink sink, int[] script, int tail) {
        return new Game(config, sink, scriptedDice(script, tail));
    }
}
