package com.llmeval.ludo.engine;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Cross-engine conformance vectors.
 *
 * <p>ADR-0002 keeps one engine per language rather than one per stack. The Python and Java
 * engines are held to the same rules by these vectors: given a seed and the deterministic
 * {@link FirstLegal} decider, both must produce an identical event stream.
 *
 * <p>Because the decider is deterministic, a vector need only record the seed — the entire game
 * follows from it. The digest covers every event, so any divergence in rules, ordering, or dice
 * shows up as a mismatch.
 */
public final class Conformance {

    public static final int DEFAULT_MAX_TURNS = 400;

    private Conformance() {}

    /**
     * Drop the one field that is <em>required</em> to differ between engines.
     *
     * <p>Must stay in lockstep with {@code conformance.for_digest} in the Python engine — if the
     * two disagree about what is excluded, every vector fails and the message will point at the
     * rules rather than at this function.
     */
    static Map<String, Object> forDigest(Map<String, Object> event) {
        if (!"game_started".equals(event.get("type"))) {
            return event;
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) event.get("payload");

        Map<String, Object> trimmed = new LinkedHashMap<>(payload);
        trimmed.remove("engine");

        Map<String, Object> copy = new LinkedHashMap<>(event);
        copy.put("payload", trimmed);
        return copy;
    }

    /** SHA-256 over the canonical form of every event, minus engine identity. */
    public static String digest(List<Map<String, Object>> events) {
        MessageDigest sha;
        try {
            sha = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is required by the JDK", e);
        }
        for (Map<String, Object> event : events) {
            sha.update(Json.canonical(forDigest(event)).getBytes(java.nio.charset.StandardCharsets.UTF_8));
            sha.update((byte) '\n');
        }
        StringBuilder hex = new StringBuilder();
        for (byte b : sha.digest()) {
            hex.append(String.format("%02x", b));
        }
        return hex.toString();
    }

    /** Play one fully deterministic game and summarise it. */
    public static Map<String, Object> runVector(int seed, int maxTurns) {
        EventSink.ListSink sink = new EventSink.ListSink();
        Map<Color, Decider> deciders = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            deciders.put(color, new FirstLegal());
        }
        Outcome outcome = new Game(new GameConfig(seed, maxTurns), sink).play(deciders);

        List<Map<String, Object>> standings = new ArrayList<>();
        for (Map<String, Object> row : outcome.standings()) {
            Map<String, Object> trimmed = new LinkedHashMap<>();
            trimmed.put("player", row.get("player"));
            trimmed.put("rank", row.get("rank"));
            trimmed.put("tokens_home", row.get("tokens_home"));
            trimmed.put("progress", row.get("progress"));
            standings.add(trimmed);
        }

        Map<String, Object> vector = new LinkedHashMap<>();
        vector.put("seed", seed);
        vector.put("max_turns", maxTurns);
        vector.put("decider", FirstLegal.NAME);
        vector.put("reason", outcome.reason());
        vector.put("turns_played", outcome.turnsPlayed());
        vector.put("events", sink.events().size());
        vector.put("standings", standings);
        vector.put("digest", digest(sink.events()));
        return vector;
    }

    /** Replay every vector and return human-readable mismatches. */
    public static List<String> check(Map<String, Object> expected) {
        List<String> failures = new ArrayList<>();

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> vectors = (List<Map<String, Object>>) expected.get("vectors");

        for (Map<String, Object> want : vectors) {
            int seed = asInt(want.get("seed"));
            int maxTurns = asInt(want.get("max_turns"));
            Map<String, Object> got = runVector(seed, maxTurns);

            for (String field : List.of("digest", "reason", "turns_played", "events", "standings")) {
                if (!equalValues(got.get(field), want.get(field))) {
                    failures.add("seed " + seed + ": " + field
                            + " expected " + Json.canonical(want.get(field))
                            + ", got " + Json.canonical(got.get(field)));
                }
            }
        }
        return failures;
    }

    private static int asInt(Object value) {
        return ((Number) value).intValue();
    }

    /**
     * Compare across the Integer/Long boundary.
     *
     * <p>The parser produces {@code Long} for every JSON integer; the engine produces
     * {@code Integer}. {@code Long.valueOf(3).equals(Integer.valueOf(3))} is {@code false}, so a
     * plain {@code equals} would report every numeric field as a mismatch and bury the real one.
     */
    private static boolean equalValues(Object got, Object want) {
        if (got instanceof Number a && want instanceof Number b) {
            return a.longValue() == b.longValue();
        }
        if (got instanceof List<?> a && want instanceof List<?> b) {
            if (a.size() != b.size()) {
                return false;
            }
            for (int i = 0; i < a.size(); i++) {
                if (!equalValues(a.get(i), b.get(i))) {
                    return false;
                }
            }
            return true;
        }
        if (got instanceof Map<?, ?> a && want instanceof Map<?, ?> b) {
            if (!a.keySet().equals(b.keySet())) {
                return false;
            }
            for (Map.Entry<?, ?> entry : a.entrySet()) {
                if (!equalValues(entry.getValue(), b.get(entry.getKey()))) {
                    return false;
                }
            }
            return true;
        }
        return java.util.Objects.equals(got, want);
    }
}
