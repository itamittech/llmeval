package com.llmeval.relay.engine;

import java.util.ArrayList;
import java.util.List;

/**
 * Stage generation and answer checking.
 *
 * <p>Every sentence built here is a corpus byte: the whole track rides inside
 * {@code track_generated}, so the conformance digest covers it. This class must agree with
 * {@code relay_engine/track.py} to the space — including the space that joins sentences and the
 * question mark that ends them.
 *
 * <p>The tier never reaches the prose. A generator that made hard stages read as harder would
 * hand the runners the one thing the game asks them to judge, and it would pass every test that
 * only checked answers.
 */
public final class Track {

    private Track() {}

    public static final List<String> FAMILIES = List.of("chain", "cipher", "order");

    public static final int TRACK_STAGES = 10;
    public static final int[] TIER_MULTISET = {1, 1, 1, 1, 2, 2, 2, 2, 3, 3};

    static final int[] CHAIN_STEPS = {0, 2, 4, 6};
    static final List<String> CIPHER_SHORT =
            List.of("iron", "moss", "lamp", "reed", "sail", "vine", "clay", "dusk");
    static final List<String> CIPHER_LONG =
            List.of("mariner", "lantern", "kestrel", "harvest", "tundra", "cobalt",
                    "quarry", "silence");
    static final List<String> ORDER_NAMES =
            List.of("ada", "brun", "cyd", "dev", "esme", "fen", "gil", "hana");
    static final int[] ORDER_ITEMS = {0, 3, 4, 5};
    static final String[] ORDINALS = {"first", "second", "third", "fourth", "fifth"};

    /** How an answer is compared: forgiving about wrapping, strict about the token. */
    public static String normalise(String answer) {
        String trimmed = answer.strip();
        while (trimmed.endsWith(".")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed.strip().toLowerCase();
    }

    public static List<Stage> generate(Rng rng) {
        return generate(rng, TRACK_STAGES);
    }

    /** Draw order is spec: tiers first (one shuffle), then each stage's family and body. */
    public static List<Stage> generate(Rng rng, int stages) {
        List<Integer> tiers = new ArrayList<>();
        for (int i = 0; i < stages; i++) {
            tiers.add(TIER_MULTISET[i]);
        }
        rng.shuffle(tiers);

        List<Stage> built = new ArrayList<>();
        for (int index = 0; index < stages; index++) {
            String family = FAMILIES.get(rng.below(FAMILIES.size()));
            int tier = tiers.get(index);
            String[] body = switch (family) {
                case "chain" -> chain(rng, tier);
                case "cipher" -> cipher(rng, tier);
                default -> order(rng, tier);
            };
            built.add(new Stage(String.format("stage-%02d", index + 1), family, tier,
                    body[0], body[1]));
        }
        return built;
    }

    // -- families --------------------------------------------------------

    private static String[] chain(Rng rng, int tier) {
        int value = rng.between(1, 20);
        List<String> parts = new ArrayList<>();
        parts.add("Start with " + value + ".");
        // Multiplying by three only appears at tier 3.
        int kinds = tier < 3 ? 3 : 4;
        for (int step = 0; step < CHAIN_STEPS[tier]; step++) {
            int kind = rng.below(kinds);
            if (kind == 0) {
                int n = rng.between(2, 10);
                value += n;
                parts.add("Add " + n + ".");
            } else if (kind == 1) {
                int n = rng.between(2, 10);
                value -= n;
                parts.add("Subtract " + n + ".");
            } else if (kind == 2) {
                value *= 2;
                parts.add("Double it.");
            } else {
                value *= 3;
                parts.add("Triple it.");
            }
        }
        parts.add("What number do you end with?");
        return new String[] {String.join(" ", parts), Integer.toString(value)};
    }

    private static String[] cipher(Rng rng, int tier) {
        List<String> pool = tier == 1 ? CIPHER_SHORT : CIPHER_LONG;
        String word = pool.get(rng.below(pool.size()));
        int shift = rng.between(1, 25);
        String encoded = caesar(word, shift).toUpperCase();

        String prompt;
        if (tier < 3) {
            prompt = "Every letter of a word was shifted forward " + shift
                    + " places through the alphabet, wrapping from z back to a, giving "
                    + encoded + ". What was the original word?";
        } else {
            prompt = "Every letter of a word was shifted forward through the alphabet by the "
                    + "same unknown number of places, wrapping from z back to a, giving "
                    + encoded + ". The original word begins with '" + word.charAt(0)
                    + "'. What was the original word?";
        }
        return new String[] {prompt, word};
    }

    static String caesar(String word, int shift) {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < word.length(); i++) {
            out.append((char) ('a' + (word.charAt(i) - 'a' + shift) % 26));
        }
        return out.toString();
    }

    private static String[] order(Rng rng, int tier) {
        int count = ORDER_ITEMS[tier];
        List<String> order = rng.sample(ORDER_NAMES, count);

        List<String> facts = new ArrayList<>();
        for (int i = 0; i < count - 1; i++) {
            facts.add(order.get(i) + " is somewhere before " + order.get(i + 1) + ".");
        }
        if (tier == 3) {
            // True, and it rules out nothing the chain did not already rule out.
            facts.add(order.get(rng.below(count - 1)) + " is not last.");
        }
        rng.shuffle(facts);

        int position = rng.below(count);
        String prompt = count + " runners crossed the line one at a time. "
                + String.join(" ", facts)
                + " Who finished " + ORDINALS[position] + "? Answer with one name.";
        return new String[] {prompt, order.get(position)};
    }
}
