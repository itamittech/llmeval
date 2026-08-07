package com.llmeval.relay.engine;

/**
 * One turn's move. A null answer is a pass.
 *
 * <p>There is no {@code escalated} field, deliberately: escalation is performed by the engine
 * through {@link EscalationDesk}, so it is a receipt rather than something a runner asserts.
 */
public record Attempt(String answer, String note) {

    public Attempt(String answer) {
        this(answer, null);
    }

    public static Attempt pass() {
        return new Attempt(null, null);
    }
}
