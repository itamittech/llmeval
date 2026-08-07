package com.llmeval.relay.springai;

import com.llmeval.relay.engine.EventSink;
import com.llmeval.relay.engine.Game;
import com.llmeval.relay.engine.Outcome;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * A full scripted race — offline, free, byte-reproducible.
 *
 * <pre>
 *   ./mvnw -q -B compile exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"
 * </pre>
 *
 * <p>Same seed and same policies as both Python stacks, which is the whole point: the engine
 * spine must come out identical, event for event, or the three harnesses are not comparable and
 * every number below them is noise.
 */
public final class Demo {

    public static final int SEED = 7;
    public static final int MAX_TURNS = 24;

    private Demo() {}

    public static Harness build(EventSink sink) {
        Map<String, PolicyChatModel> models = new LinkedHashMap<>();
        for (String color : Game.COLORS) {
            models.put(color, new PolicyChatModel(Policies.RUNNERS.get(color),
                    "scripted-" + color));
        }
        PolicyChatModel anchor = new PolicyChatModel(Policies::anchor, "scripted-anchor");
        return new Harness(ModelsConfig.load("dev"), Prompts.load(), Prompts.loadAnchor(),
                models, anchor, sink, SEED, MAX_TURNS, 0);
    }

    public static void main(String[] args) throws IOException {
        Path out = Path.of(args.length > 0 ? args[0] : "relay-springai.jsonl");
        if (out.getParent() != null) {
            Files.createDirectories(out.getParent());
        }

        Outcome outcome;
        Harness harness;
        try (Writer writer = new BufferedWriter(
                Files.newBufferedWriter(out, StandardCharsets.UTF_8))) {
            harness = build(new EventSink.JsonlSink(writer));
            outcome = harness.play();
        }

        System.out.println("wrote " + out);
        System.out.println("reason=" + outcome.reason() + " turns=" + outcome.turnsPlayed()
                + " quota_left=" + harness.game().quota() + " calls=" + harness.calls());
        for (Map<String, Object> row : outcome.standings()) {
            System.out.printf("  %s. %-7s stages=%2s ticks=%3s escalations=%s "
                            + "correct=%s wrong=%s passes=%s%n",
                    row.get("rank"), row.get("player"), row.get("stages_cleared"),
                    row.get("ticks"), row.get("escalations"), row.get("correct"),
                    row.get("wrong"), row.get("passes"));
        }
    }
}
