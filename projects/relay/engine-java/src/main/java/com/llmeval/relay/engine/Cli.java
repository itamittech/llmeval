package com.llmeval.relay.engine;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Engine command line, mirroring {@code python -m relay_engine.cli}.
 *
 * <pre>
 *   ./mvnw -q -B exec:java -Dexec.args="play --seed 7"
 *   ./mvnw -q -B exec:java -Dexec.args="conformance --check"
 * </pre>
 *
 * <p>Vector <em>generation</em> lives only in Python: this engine is held to the expectations, it
 * does not get to write them.
 */
public final class Cli {

    private Cli() {}

    public static void main(String[] args) throws IOException {
        if (args.length == 0) {
            System.err.println("usage: play | track | conformance --check");
            System.exit(2);
        }
        switch (args[0]) {
            case "play" -> System.exit(play(args));
            case "track" -> System.exit(track(args));
            case "conformance" -> System.exit(conformance());
            default -> {
                System.err.println("unknown command: " + args[0]);
                System.exit(2);
            }
        }
    }

    private static int play(String[] args) throws IOException {
        int seed = intArg(args, "--seed", 1);
        int maxTurns = intArg(args, "--max-turns", 60);
        String out = stringArg(args, "--out");

        EventSink.ListSink collector = new EventSink.ListSink();
        GameConfig config = new GameConfig(seed, maxTurns);
        Map<String, Runner> runners = new LinkedHashMap<>();
        for (String color : Game.COLORS) {
            runners.put(color, new LadderRunner());
        }

        Outcome outcome;
        if (out != null) {
            Path path = Path.of(out);
            if (path.getParent() != null) {
                Files.createDirectories(path.getParent());
            }
            try (Writer writer = new BufferedWriter(
                    Files.newBufferedWriter(path, StandardCharsets.UTF_8))) {
                outcome = new Game(config,
                        new EventSink.TeeSink(collector, new EventSink.JsonlSink(writer)))
                        .play(runners);
            }
            System.out.println("wrote " + path + " (" + collector.events().size() + " events)");
        } else {
            outcome = new Game(config, collector).play(runners);
        }

        System.out.println("seed=" + seed + " reason=" + outcome.reason()
                + " turns=" + outcome.turnsPlayed());
        for (Map<String, Object> row : outcome.standings()) {
            System.out.printf("  %s. %-7s stages=%2s ticks=%3s escalations=%2s %s%n",
                    row.get("rank"), row.get("player"), row.get("stages_cleared"),
                    row.get("ticks"), row.get("escalations"),
                    Boolean.TRUE.equals(row.get("finished")) ? "FINISHED" : "");
        }
        return 0;
    }

    /** Print a seed's track with its sealed answers — for reading the generators, not playing. */
    private static int track(String[] args) {
        for (Stage stage : Track.generate(new Rng(intArg(args, "--seed", 1)))) {
            System.out.println(stage.id() + "  tier " + stage.tier() + "  " + stage.family()
                    + " -> " + stage.answer());
            System.out.println("    " + stage.prompt());
        }
        return 0;
    }

    private static int conformance() throws IOException {
        List<String> failures = Conformance.check();
        failures.forEach(System.err::println);
        System.out.println(failures.isEmpty() ? "conformance: ok" : "conformance: FAIL");
        return failures.isEmpty() ? 0 : 1;
    }

    private static int intArg(String[] args, String name, int fallback) {
        String value = stringArg(args, name);
        return value == null ? fallback : Integer.parseInt(value);
    }

    private static String stringArg(String[] args, String name) {
        for (int i = 0; i < args.length - 1; i++) {
            if (args[i].equals(name)) {
                return args[i + 1];
            }
        }
        return null;
    }
}
