package com.llmeval.alibi.springai;

import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Content guardrails — lenient by design (ADR-0004), byte-for-byte the same
 * three rules as the Python stacks: injection, engine-authority claims, and
 * forged document citations. A note citing a REAL document passes — possibly a
 * misleading one, which is the game.
 */
public final class Guardrails {

    public record Violation(String rule, String reason) {}

    private static final Pattern INJECTION = Pattern.compile(
            "ignore (all |your |previous |the )?(instructions?|prompts?)"
                    + "|disregard (your|the) (instructions?|system prompt)"
                    + "|you are now\\b"
                    + "|system prompt",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern AUTHORITY = Pattern.compile(
            "the engine (confirms|says|revealed|shows)"
                    + "|the case file (confirms|shows|proves|names)"
                    + "|the referee (confirms|says)",
            Pattern.CASE_INSENSITIVE);

    private static final Pattern CITATION = Pattern.compile("\\[?(doc-\\d{3})]?");

    private Guardrails() {}

    /** The violation, or null when the text is merely cunning. */
    public static Violation check(String text, Set<String> validDocIds) {
        if (INJECTION.matcher(text).find()) {
            return new Violation("injection",
                    "instructions aimed at the system, not the players");
        }
        if (AUTHORITY.matcher(text).find()) {
            return new Violation("authority",
                    "claims the engine or case file as a source");
        }
        Matcher m = CITATION.matcher(text);
        while (m.find()) {
            String cited = m.group(1);
            if (!validDocIds.contains(cited)) {
                return new Violation("forgery",
                        "cites " + cited + ", which does not exist in the archive");
            }
        }
        return null;
    }
}
