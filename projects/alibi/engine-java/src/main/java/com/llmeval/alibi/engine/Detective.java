package com.llmeval.alibi.engine;

/**
 * The required agent interface. Every return is validated by the engine; a lying detective is
 * still only ever lying (ADR-0004).
 *
 * <p>Java's {@code interface} needs an explicit {@code implements}, so — as with LUDO's
 * {@code Decider} — the Spring AI stack takes a compile-time dependency on this engine. The
 * Python stacks' structural typing has no counterpart here; that asymmetry is a recorded
 * capability-matrix finding, not an accident.
 */
public interface Detective {

    /** The interrogation move; may search the archive mid-thought. Null = pass. */
    Suggestion suggest(TurnContext ctx);

    /** Compelled when able to refute: pick one held, named element to show privately. */
    String show(ShowContext ctx);

    /** After seeing this turn's refutation. Null = no accusation. */
    Triple accuse(TurnContext ctx);

    /** Required: the declared best guess the eval scores. */
    Belief conclude(TurnContext ctx);

    /** Optional hook, mirroring the Python {@code Reflector} protocol. */
    default void reflect(TurnEnd end) {}

    /** Agent name recorded in game_started. */
    default String name() {
        return "unknown";
    }
}
