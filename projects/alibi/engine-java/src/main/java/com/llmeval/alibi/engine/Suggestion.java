package com.llmeval.alibi.engine;

import java.util.List;

/** The interrogation move. {@code note} is public table talk and may be a lie. */
public record Suggestion(String who, String how, String where, String note) {

    public Suggestion(String who, String how, String where) {
        this(who, how, where, null);
    }

    public List<String> named() {
        return List.of(who, how, where);
    }
}
