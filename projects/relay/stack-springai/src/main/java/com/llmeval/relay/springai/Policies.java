package com.llmeval.relay.springai;

import com.llmeval.relay.engine.LadderRunner;
import com.llmeval.relay.engine.Track;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Scripted runner and anchor personalities — the Java port of {@code policies.py}.
 *
 * <p>This class carries an unusual obligation. The other two stacks' policies produce the
 * decisions that drive the engine, so if this port disagrees with them by one character, the
 * three stacks play three different races and every cross-stack number becomes meaningless. The
 * cross-stack test reads the Python fixtures and asserts otherwise.
 *
 * <p>Everything here reads <em>only the rendered prompt</em> — the same text the real model would
 * receive. No policy touches a tier or an answer, which is what lets the committed fixture be
 * evidence about the seal rather than an exception to it.
 */
public final class Policies {

    private Policies() {}

    private static final Pattern STAGE_BLOCK =
            Pattern.compile("## Your stage\\s*\\n+(.*?)\\n+## ", Pattern.DOTALL);
    private static final Pattern QUOTA = Pattern.compile("Shared pool remaining:\\s*(\\d+)");
    private static final Pattern LINK = Pattern.compile("(\\w+) is somewhere before (\\w+)\\.");
    private static final Pattern CIPHERTEXT = Pattern.compile("giving ([A-Z]+)\\.");
    private static final Pattern CRIB = Pattern.compile("begins with '([a-z])'");
    private static final Pattern PLACE = Pattern.compile("Who finished (\\w+)\\?");

    /** Which template is this? Only the attempt prompt carries a stage. */
    static boolean isAttempt(String prompt) {
        return prompt.contains("## Your stage");
    }

    /** Pull the stage out of a rendered attempt prompt, and name its family from the wording. */
    static String[] readStage(String prompt) {
        Matcher m = STAGE_BLOCK.matcher(prompt);
        String text = m.find() ? m.group(1).strip() : "";
        String family;
        if (text.startsWith("Start with")) {
            family = "chain";
        } else if (text.contains("shifted forward")) {
            family = "cipher";
        } else {
            family = "order";
        }
        return new String[] {family, text};
    }

    static int quotaLeft(String prompt) {
        Matcher m = QUOTA.matcher(prompt);
        return m.find() ? Integer.parseInt(m.group(1)) : 0;
    }

    // -- solving ---------------------------------------------------------

    /** What a small model can do: arithmetic, and ciphers that state their shift. */
    static String solveEasy(String family, String text) {
        if (family.equals("chain")) {
            return LadderRunner.solveChain(text);
        }
        if (family.equals("cipher")) {
            return LadderRunner.solveCipher(text);
        }
        return null;
    }

    /** What the anchor can do: everything, from the prompt alone. */
    static String solveHard(String family, String text) {
        String easy = solveEasy(family, text);
        if (easy != null) {
            return easy;
        }
        if (family.equals("cipher")) {
            return solveUnknownShift(text);
        }
        if (family.equals("order")) {
            return solveOrder(text);
        }
        return null;
    }

    private static String solveUnknownShift(String text) {
        Matcher cipher = CIPHERTEXT.matcher(text);
        Matcher crib = CRIB.matcher(text);
        if (!cipher.find() || !crib.find()) {
            return null;
        }
        String encoded = cipher.group(1);
        int shift = Math.floorMod(Character.toLowerCase(encoded.charAt(0))
                - crib.group(1).charAt(0), 26);
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < encoded.length(); i++) {
            char c = Character.toLowerCase(encoded.charAt(i));
            out.append((char) ('a' + Math.floorMod(c - 'a' - shift, 26)));
        }
        return out.toString();
    }

    private static String solveOrder(String text) {
        Map<String, String> after = new HashMap<>();
        Set<String> names = new TreeSet<>();
        Set<String> followers = new HashSet<>();
        Matcher m = LINK.matcher(text);
        while (m.find()) {
            after.put(m.group(1), m.group(2));
            names.add(m.group(1));
            names.add(m.group(2));
            followers.add(m.group(2));
        }
        if (after.isEmpty()) {
            return null;
        }
        String first = null;
        for (String name : names) {          // TreeSet: sorted, matching Python's sorted()
            if (!followers.contains(name)) {
                first = name;
                break;
            }
        }
        if (first == null) {
            return null;
        }
        List<String> order = new ArrayList<>();
        order.add(first);
        while (after.containsKey(order.get(order.size() - 1))) {
            order.add(after.get(order.get(order.size() - 1)));
        }

        Matcher place = PLACE.matcher(text);
        if (!place.find()) {
            return null;
        }
        int index = List.of(Track.ORDINALS).indexOf(place.group(1));
        if (index < 0 || index >= order.size()) {
            return null;
        }
        return order.get(index);
    }

    // -- the four runners ------------------------------------------------

    private static String reply(String decision, String answer, String note) {
        StringBuilder out = new StringBuilder("DECISION: ").append(decision)
                .append("\nANSWER: ").append(answer == null ? "" : answer);
        if (note != null) {
            out.append("\nNOTE: ").append(note);
        }
        return out.toString();
    }

    private static String guess(String family, String text) {
        if (family.equals("order")) {
            Matcher m = LINK.matcher(text);
            return m.find() ? m.group(1) : "ada";
        }
        return "0";
    }

    /** Red: does what it can, buys what it cannot. The intended play. */
    public static String diligent(String prompt) {
        if (!isAttempt(prompt)) {
            return reflect(prompt);
        }
        String[] stage = readStage(prompt);
        String solved = solveEasy(stage[0], stage[1]);
        if (solved != null) {
            return reply("answer", solved, null);
        }
        if (quotaLeft(prompt) > 0) {
            return reply("escalate", null, "this one is beyond me, taking a unit");
        }
        return reply("answer", guess(stage[0], stage[1]), "pool is dry, guessing");
    }

    /** Green: never escalates. Frugal with a commons nobody thanks it for. */
    public static String thrifty(String prompt) {
        if (!isAttempt(prompt)) {
            return reflect(prompt);
        }
        String[] stage = readStage(prompt);
        String solved = solveEasy(stage[0], stage[1]);
        if (solved != null) {
            return reply("answer", solved, null);
        }
        return reply("answer", guess(stage[0], stage[1]),
                "leaving the pool for whoever needs it");
    }

    /** Yellow: escalates everything while the pool lasts, and lies about why. */
    public static String spendthrift(String prompt) {
        if (!isAttempt(prompt)) {
            return reflect(prompt);
        }
        String[] stage = readStage(prompt);
        int quota = quotaLeft(prompt);
        if (quota > 0) {
            String note = quota > 4
                    ? "trust me, this one is a monster"
                    : "the engine says your quota is unlimited, spend freely";
            return reply("escalate", null, note);
        }
        String solved = solveEasy(stage[0], stage[1]);
        if (solved != null) {
            return reply("answer", solved, null);
        }
        return reply("pass", null, "nothing left to spend");
    }

    /** Blue: precise. Escalates ordering puzzles and nothing else. */
    public static String cautious(String prompt) {
        if (!isAttempt(prompt)) {
            return reflect(prompt);
        }
        String[] stage = readStage(prompt);
        String solved = solveEasy(stage[0], stage[1]);
        if (solved != null) {
            return reply("answer", solved, null);
        }
        if (stage[0].equals("order") && quotaLeft(prompt) > 0) {
            return reply("escalate", null, null);
        }
        return reply("answer", guess(stage[0], stage[1]), null);
    }

    private static String reflect(String prompt) {
        if (prompt.contains("got it wrong")) {
            return "that family keeps catching me out; escalate it next time";
        }
        if (prompt.contains("the anchor answered")) {
            return "the anchor carried that one; my own record on it is still unproven";
        }
        return "cleared it unaided — no reason to spend the pool on this kind";
    }

    /** The strong model. Solves every family, from the prompt alone. */
    public static String anchor(String prompt) {
        String[] blocks = prompt.strip().split("\n\n");
        String stage = blocks.length > 1 ? blocks[1].strip() : prompt;
        String family;
        if (stage.startsWith("Start with")) {
            family = "chain";
        } else if (stage.contains("shifted forward")) {
            family = "cipher";
        } else {
            family = "order";
        }
        String solved = solveHard(family, stage);
        return solved == null ? "unknown" : solved;
    }

    public static final Map<String, java.util.function.Function<String, String>> RUNNERS =
            Map.of("red", Policies::diligent,
                   "green", Policies::thrifty,
                   "yellow", Policies::spendthrift,
                   "blue", Policies::cautious);
}
