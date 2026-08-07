package com.llmeval.alibi.engine;

/**
 * Everything a detective may see while deciding. {@code refutation}/{@code noRefutation} are set
 * only on the accuse phase: what this turn's suggestion just taught, if anything.
 */
public record TurnContext(DetectiveView view, Color color, int turn, SearchBudget archive,
                          int attempt, Refutation refutation, Suggestion noRefutation) {

    public TurnContext(DetectiveView view, Color color, int turn, SearchBudget archive, int attempt) {
        this(view, color, turn, archive, attempt, null, null);
    }

    /** A refutation as the suggester experienced it: who showed, and what. */
    public record Refutation(Color refuter, String element) {}
}
