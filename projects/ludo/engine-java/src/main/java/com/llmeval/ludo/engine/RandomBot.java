package com.llmeval.ludo.engine;

/**
 * Uniformly random legal move.
 *
 * <p>Seeded from the same portable RNG as the dice so bot games replay exactly. Used to
 * calibrate the turn cap without spending a single token.
 */
public final class RandomBot implements Decider {

    private final Dice rng;

    public RandomBot(int seed) {
        this.rng = new Dice(seed);
    }

    @Override
    public String name() {
        return "random-bot";
    }

    @Override
    public Move choose(TurnContext ctx) {
        // roll() returns 1..6; reduce to an index without another primitive.
        int pick = 0;
        for (int i = 0; i < 4; i++) {
            pick = pick * 6 + (rng.roll() - 1);
        }
        return ctx.legalMoves().get(pick % ctx.legalMoves().size());
    }
}
