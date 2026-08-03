package com.llmeval.ludo.engine;

/**
 * Move choosers, and the two optional per-turn hooks an agent harness plugs into.
 *
 * <p>The engine knows nothing about LLMs. It asks a {@link Decider} to pick from the moves it has
 * already validated as legal — which is what makes cheating structurally impossible (ADR-0004).
 *
 * <p>Three call sites, only the middle one required:
 *
 * <pre>
 * negotiate(TurnStart)   once per turn, before the first roll   optional
 * choose(TurnContext)    once per ROLL                          required
 * reflect(TurnEnd)       once per turn, after it resolves       optional
 * </pre>
 *
 * <p>The per-turn / per-roll distinction is load-bearing. A six or a capture earns another roll,
 * so {@code choose} may run several times in one turn; if negotiation ran with it, an agent on a
 * hot streak would get a free multiplier on both influence and cost. See the harness contract,
 * {@code docs/projects/ludo/harness-contract.md}.
 *
 * <p><strong>Where the two engines genuinely differ.</strong> Python expresses these as
 * {@code Protocol}s: an agent satisfies the contract by shape alone, with no import and no
 * inheritance, so the engine and the agent packages need no compile-time relationship at all.
 * Java needs an explicit {@code implements}, which means every agent must depend on this jar.
 * That is a real framework-comparison data point, not trivia — recorded in the capability
 * matrix.
 */
public interface Decider {

    /** Identity for the event stream. */
    String name();

    /** Pick one of {@code ctx.legalMoves()}. Anything else is rejected by the engine. */
    Move choose(TurnContext ctx);

    /**
     * Optional. Called once per turn, before the first roll.
     *
     * <p>A default method rather than a separate interface, so bot deciders with no model behind
     * them stay valid — which is what keeps the engine fast to test. Python achieves the same
     * with a {@code runtime_checkable} Protocol and a method-presence check.
     */
    default void negotiate(TurnStart start) {}

    /** Optional. Called once per turn, after it resolves. */
    default void reflect(TurnEnd end) {}
}
