package com.llmeval.ludo.springai;

import java.util.List;
import java.util.regex.Pattern;

/**
 * Content guardrails — the same three deterministic rules as the Python
 * stacks, byte for byte where it matters: what blocks there must block here,
 * what passes there must pass here, or the stacks are playing different games.
 *
 * <p>Lenient by design (ADR-0004): in-game cunning — lies, bluffs, betrayal —
 * always passes. Only the out-of-fiction attack surface of the shared message
 * channel is checked, and the leniency is tested, not assumed.
 */
public final class Guardrails {

    public record Violation(String rule, String reason) {}

    private record Rule(String name, Pattern pattern, String description) {}

    private static final List<Rule> RULES = List.of(
            new Rule("instruction-override",
                    Pattern.compile("(?i)\\b(ignore|disregard|override)\\b[\\s\\S]{0,40}?\\b(instructions?|prompts?)\\b"),
                    "an attempt to overwrite another player's instructions"),
            new Rule("role-smuggling",
                    Pattern.compile("(?im)<system>|\\[system]|\\bsystem prompt\\b|\\bdeveloper (message|prompt)\\b|^\\s*system\\s*:"),
                    "text posing as a system or developer message"),
            new Rule("system-impersonation",
                    Pattern.compile("(?im)\\bi am the (engine|harness|referee|judge|system)\\b|^\\s*(engine|harness)\\s*:"),
                    "a player impersonating the system"));

    private Guardrails() {}

    /** The first rule the text trips, or null — which is the common case. */
    public static Violation check(String text) {
        for (Rule rule : RULES) {
            if (rule.pattern().matcher(text).find()) {
                String snippet = text.length() > 100 ? text.substring(0, 100) : text;
                return new Violation(rule.name(), rule.description() + ": \"" + snippet + "\"");
            }
        }
        return null;
    }
}
