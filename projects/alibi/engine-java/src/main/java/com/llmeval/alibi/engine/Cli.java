package com.llmeval.alibi.engine;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/**
 * Command line for the Java engine. Mirrors the Python CLI's {@code play}, {@code bench}, and
 * {@code conformance}. {@code validate} is deliberately absent, as in LUDO: schema validation
 * needs a schema library and this engine has no dependencies — the Python CLI owns that job.
 */
public final class Cli {

    private Cli() {}

    public static void main(String[] args) throws Exception {
        if (args.length == 0) {
            usage();
            System.exit(2);
        }
        int status = switch (args[0]) {
            case "play" -> play(args);
            case "bench" -> bench(args);
            case "conformance" -> conformance(args);
            default -> {
                System.err.println("unknown command: " + args[0]);
                usage();
                yield 2;
            }
        };
        System.exit(status);
    }

    private static void usage() {
        System.err.println("""
                usage: alibi <command> [options]

                  play         --seed N [--max-turns N] [--out FILE]
                  bench        [--games N] [--max-turns N]
                  conformance  --check [--vectors FILE]
                """);
    }

    private static Map<Color, Detective> bots() {
        Map<Color, Detective> detectives = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            detectives.put(color, new EliminationBot());
        }
        return detectives;
    }

    private static int play(String[] args) throws IOException {
        int seed = intArg(args, "--seed", 1);
        int maxTurns = intArg(args, "--max-turns", 40);
        String out = stringArg(args, "--out", null);

        EventSink.ListSink memory = new EventSink.ListSink();
        Outcome outcome;

        if (out == null) {
            outcome = new Game(new GameConfig(seed, maxTurns), memory).play(bots());
        } else {
            Path path = Path.of(out);
            if (path.getParent() != null) {
                Files.createDirectories(path.getParent());
            }
            try (Writer writer = new BufferedWriter(
                    Files.newBufferedWriter(path, StandardCharsets.UTF_8))) {
                EventSink sink = new EventSink.TeeSink(memory, new EventSink.JsonlSink(writer));
                outcome = new Game(new GameConfig(seed, maxTurns), sink).play(bots());
            }
            System.out.println("wrote " + path + " (" + memory.events().size() + " events)");
        }

        System.out.printf("seed=%d reason=%s turns=%d%n", seed, outcome.reason(), outcome.turnsPlayed());
        System.out.printf("solution: %s / %s / %s%n", outcome.solution().get("who"),
                outcome.solution().get("how"), outcome.solution().get("where"));
        for (Map<String, Object> row : outcome.standings()) {
            System.out.printf("  %d. %-7s belief=%s/3 suggestions=%s searches=%s%s%n",
                    row.get("rank"), row.get("player"), row.get("belief_dimensions_correct"),
                    row.get("suggestions_made"), row.get("searches_made"),
                    Boolean.TRUE.equals(row.get("solved")) ? " SOLVED" : "");
        }
        return 0;
    }

    private static int bench(String[] args) {
        int games = intArg(args, "--games", 200);
        int maxTurns = intArg(args, "--max-turns", 200);

        List<Integer> turns = new ArrayList<>();
        int solved = 0;

        // Seeds start at 1, matching the Python CLI — the two benches must be comparable.
        for (int seed = 1; seed <= games; seed++) {
            Outcome outcome = new Game(new GameConfig(seed, maxTurns), new EventSink.ListSink())
                    .play(bots());
            turns.add(outcome.turnsPlayed());
            if ("solved".equals(outcome.reason())) {
                solved++;
            }
        }

        List<Integer> ordered = new ArrayList<>(turns);
        ordered.sort(Integer::compare);

        System.out.printf("games=%d cap=%d%n", games, maxTurns);
        System.out.printf("solved=%d (%.0f%%)%n", solved, 100.0 * solved / games);
        System.out.printf("turns  min=%d median=%d p90=%d p99=%d max=%d%n",
                ordered.get(0), median(ordered), percentile(ordered, 0.90),
                percentile(ordered, 0.99), ordered.get(ordered.size() - 1));
        return 0;
    }

    private static long median(List<Integer> ordered) {
        int n = ordered.size();
        if (n % 2 == 1) {
            return ordered.get(n / 2);
        }
        return Math.round((ordered.get(n / 2 - 1) + ordered.get(n / 2)) / 2.0);
    }

    private static int percentile(List<Integer> ordered, double p) {
        return ordered.get(Math.min(ordered.size() - 1, (int) (ordered.size() * p)));
    }

    private static int conformance(String[] args) throws IOException {
        String file = stringArg(args, "--vectors", "../../../shared/conformance/alibi-vectors.json");
        Path path = Path.of(file);
        if (!Files.exists(path)) {
            System.err.println("vectors not found: " + path.toAbsolutePath());
            return 2;
        }

        @SuppressWarnings("unchecked")
        Map<String, Object> expected =
                (Map<String, Object>) Json.parse(Files.readString(path, StandardCharsets.UTF_8));

        List<String> failures = Conformance.check(expected);
        if (failures.isEmpty()) {
            System.out.println("conformance: ok");
            return 0;
        }
        System.out.println("conformance: " + failures.size() + " mismatch(es)");
        for (String failure : failures) {
            System.out.println("  " + failure);
        }
        return 1;
    }

    private static String stringArg(String[] args, String flag, String fallback) {
        for (int i = 0; i < args.length - 1; i++) {
            if (args[i].equals(flag)) {
                return args[i + 1];
            }
        }
        return fallback;
    }

    private static int intArg(String[] args, String flag, int fallback) {
        String value = stringArg(args, flag, null);
        return value == null ? fallback : Integer.parseInt(value);
    }
}
