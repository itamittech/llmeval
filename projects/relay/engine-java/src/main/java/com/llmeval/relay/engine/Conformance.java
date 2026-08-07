package com.llmeval.relay.engine;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Cross-engine conformance — the Java side of ADR-0002.
 *
 * <p>This engine does not generate vectors; it only checks the committed ones. Python is the
 * reference implementation, and a Java engine that could rewrite the expectations it is being
 * held to would be marking its own homework.
 */
public final class Conformance {

    private Conformance() {}

    public static final int DEFAULT_MAX_TURNS = 80;

    /** Drop the one field that must differ between engines. */
    static Map<String, Object> forDigest(Map<String, Object> event) {
        if (!"game_started".equals(event.get("type"))) {
            return event;
        }
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) event.get("payload");
        Map<String, Object> stripped = new LinkedHashMap<>(payload);
        stripped.remove("engine");
        Map<String, Object> copy = new LinkedHashMap<>(event);
        copy.put("payload", stripped);
        return copy;
    }

    public static String digest(List<Map<String, Object>> events) {
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            for (Map<String, Object> event : events) {
                sha.update(Json.canonical(forDigest(event)).getBytes(StandardCharsets.UTF_8));
                sha.update((byte) '\n');
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : sha.digest()) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is required by the JDK", e);
        }
    }

    public static Map<String, Object> runVector(int seed, int maxTurns) {
        EventSink.ListSink sink = new EventSink.ListSink();
        GameConfig config = new GameConfig(seed, maxTurns);
        Map<String, Runner> runners = new LinkedHashMap<>();
        for (String color : Game.COLORS) {
            runners.put(color, new LadderRunner());
        }
        Outcome outcome = new Game(config, sink).play(runners);

        List<Map<String, Object>> standings = new ArrayList<>();
        for (Map<String, Object> row : outcome.standings()) {
            Map<String, Object> slim = new LinkedHashMap<>();
            slim.put("player", row.get("player"));
            slim.put("rank", row.get("rank"));
            slim.put("stages_cleared", row.get("stages_cleared"));
            slim.put("ticks", row.get("ticks"));
            slim.put("escalations", row.get("escalations"));
            standings.add(slim);
        }

        Map<String, Object> vector = new LinkedHashMap<>();
        vector.put("seed", seed);
        vector.put("max_turns", maxTurns);
        vector.put("decider", LadderRunner.NAME);
        vector.put("reason", outcome.reason());
        vector.put("turns_played", outcome.turnsPlayed());
        vector.put("events", sink.events().size());
        vector.put("standings", standings);
        vector.put("digest", digest(sink.events()));
        return vector;
    }

    /** Locate {@code shared/conformance/relay-vectors.json} by walking up from the cwd. */
    public static Path vectorsPath() {
        Path here = Paths.get("").toAbsolutePath();
        while (here != null) {
            Path candidate = here.resolve("shared/conformance/relay-vectors.json");
            if (Files.exists(candidate)) {
                return candidate;
            }
            here = here.getParent();
        }
        throw new IllegalStateException("relay-vectors.json not found above " + Paths.get("").toAbsolutePath());
    }

    @SuppressWarnings("unchecked")
    public static List<String> check() throws IOException {
        Map<String, Object> file =
                (Map<String, Object>) Json.parse(Files.readString(vectorsPath()));
        List<String> failures = new ArrayList<>();

        for (Object entry : (List<Object>) file.get("vectors")) {
            Map<String, Object> want = (Map<String, Object>) entry;
            int seed = (int) toLong(want.get("seed"));
            int maxTurns = (int) toLong(want.get("max_turns"));
            Map<String, Object> got = runVector(seed, maxTurns);

            for (String field : List.of("digest", "reason", "turns_played", "events",
                    "standings")) {
                if (!equalish(want.get(field), got.get(field))) {
                    failures.add("seed " + seed + ": " + field + " expected " + want.get(field)
                            + ", got " + got.get(field));
                }
            }
        }
        return failures;
    }

    private static long toLong(Object value) {
        return ((Number) value).longValue();
    }

    /**
     * The parser produces {@code Long} where the engine produces {@code Integer}, and standings
     * arrive as {@code List<Map>} on both sides. Compare through a normalised view rather than
     * teaching the parser about the engine's boxing.
     */
    private static boolean equalish(Object want, Object got) {
        if (want instanceof Number a && got instanceof Number b) {
            return a.longValue() == b.longValue();
        }
        if (want instanceof List<?> a && got instanceof List<?> b) {
            if (a.size() != b.size()) {
                return false;
            }
            for (int i = 0; i < a.size(); i++) {
                if (!equalish(a.get(i), b.get(i))) {
                    return false;
                }
            }
            return true;
        }
        if (want instanceof Map<?, ?> a && got instanceof Map<?, ?> b) {
            if (!new HashMap<>(a).keySet().equals(new HashMap<>(b).keySet())) {
                return false;
            }
            for (Map.Entry<?, ?> e : a.entrySet()) {
                if (!equalish(e.getValue(), b.get(e.getKey()))) {
                    return false;
                }
            }
            return true;
        }
        return want == null ? got == null : want.equals(got);
    }
}
