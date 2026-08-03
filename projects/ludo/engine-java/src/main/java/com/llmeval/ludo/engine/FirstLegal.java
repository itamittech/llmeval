package com.llmeval.ludo.engine;

/**
 * Always takes the first legal move.
 *
 * <p>Fully deterministic given a seed, which is what conformance vectors rely on: seed alone
 * reproduces the entire game, so vectors need not record decisions.
 */
public final class FirstLegal implements Decider {

    public static final String NAME = "first-legal";

    @Override
    public String name() {
        return NAME;
    }

    @Override
    public Move choose(TurnContext ctx) {
        return ctx.legalMoves().get(0);
    }
}
