package com.llmeval.relay.engine;

/**
 * The required agent interface. Every return is validated by the engine.
 *
 * <p>One call site, because RELAY is one decision repeated. Note what this costs on the JVM: a
 * Java agent must {@code implement} this, so every stack needs the engine on its compile
 * classpath, while the Python stacks satisfy the same contract structurally with no import at
 * all. Third game, same recorded asymmetry.
 */
public interface Runner {

    Attempt attempt(TurnContext ctx);

    default String name() {
        return "unknown";
    }
}
