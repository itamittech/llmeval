package com.llmeval.ludo.engine;

/**
 * The four players, in turn order.
 *
 * <p>Python uses {@code Color = str} with a {@code COLORS} tuple; Java gets a real enum, which
 * is the one place the port is deliberately <em>less</em> literal. {@link #label()} is the
 * lowercase form that goes into events — the wire format is shared with the Python engine and
 * must match byte for byte.
 */
public enum Color {
    RED("red"),
    GREEN("green"),
    YELLOW("yellow"),
    BLUE("blue");

    private final String label;

    Color(String label) {
        this.label = label;
    }

    /** The name as it appears in the event stream. Never {@code toString()} — that yields "RED". */
    public String label() {
        return label;
    }
}
