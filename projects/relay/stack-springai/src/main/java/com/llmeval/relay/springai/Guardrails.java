package com.llmeval.relay.springai;

import java.util.regex.Pattern;

/**
 * Structural guardrails on RELAY's one free-text channel — the same three rules as the Python
 * stacks, the same leniency tests.
 *
 * <p>ADR-0004, third game: block out-of-fiction attacks, let cunning through. What counts as
 * cunning here is specific and worth naming, because a careless rule would kill the game — a note
 * that lies about a stage's difficulty, or talks a rival into burning the shared pool, is the
 * intended play.
 */
public final class Guardrails {

    public record Violation(String rule, String reason) {}

    private static final Pattern INJECTION = Pattern.compile(
            "ignore (all |the )?(previous|prior|above) (instructions|prompt)"
            + "|disregard your (instructions|system prompt|rules)"
            + "|you are (now|actually) (a|an) \\w+"
            + "|system prompt:"
            + "|<\\s*/?\\s*(system|instructions)\\s*>",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern FORGED_STATE = Pattern.compile(
            "\\bthe engine (says|confirms|ruled|has|awarded)"
            + "|\\bofficial(ly)? (ruling|result)"
            + "|\\byour quota (is|has been) (increased|restored|unlimited)"
            + "|\\b(referee|engine) (grants|gives) you\\b",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern LEAKED_TIER = Pattern.compile(
            "\\bi (was|have been) (told|shown|given) (the|its|this) tier"
            + "|\\bthe (engine|referee|system) (told|showed) me (the|its) tier"
            + "|\\btrack[_ ]key\\b",
            Pattern.CASE_INSENSITIVE);

    private Guardrails() {}

    public static Violation check(String note) {
        if (INJECTION.matcher(note).find()) {
            return new Violation("instruction_injection",
                    "note addresses the reader as a model, not as a rival");
        }
        if (FORGED_STATE.matcher(note).find()) {
            return new Violation("forged_state", "note claims engine authority it cannot have");
        }
        if (LEAKED_TIER.matcher(note).find()) {
            return new Violation("claimed_seal_access",
                    "note claims to have been told a stage's tier");
        }
        return null;
    }
}
