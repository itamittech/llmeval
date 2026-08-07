package com.llmeval.alibi.engine;

/**
 * A detective's badge colour — the in-game identity. Turn order is declaration order, and the
 * seat-to-colour mapping rotates between games (ADR-0006), exactly as in LUDO.
 */
public enum Color {
    RED("red"),
    GREEN("green"),
    YELLOW("yellow"),
    BLUE("blue");

    private final String json;

    Color(String json) {
        this.json = json;
    }

    /** The lowercase name the shared schema uses. */
    public String json() {
        return json;
    }
}
