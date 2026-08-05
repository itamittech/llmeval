package com.llmeval.ludo.springai;

import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

import org.springframework.ai.chat.model.ChatModel;

import com.llmeval.ludo.engine.Color;
import com.llmeval.ludo.engine.EventSink;
import com.llmeval.ludo.engine.Outcome;

/**
 * One scripted game, end to end — free, offline, deterministic.
 *
 * <pre>./mvnw -q exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"</pre>
 *
 * Same seed and the same story as the Strands demo — red proposes an alliance
 * with a table note, blue accepts — so the two stacks' fixtures are
 * comparable: identical engine events from identical dice, with each
 * framework's own mechanics visible in the agent events between them. The
 * transcript this writes is the committed UI fixture, and ADR-0007's rule is
 * that the UI renders it with ZERO source changes.
 */
public final class Demo {

    private Demo() {}

    static Map<Color, ChatModel> scripts() {
        List<String> decides = new ArrayList<>();
        for (int i = 0; i < 7; i++) decides.add("{\"token\": 0, \"to\": 0, \"reasoning\": \"press on\"}");
        List<String> reflects = List.of(
                "{\"notes\": [{\"kind\": \"strategy\", \"text\": \"long game ahead\"}]}",
                "{\"notes\": [{\"kind\": \"strategy\", \"text\": \"long game ahead\"}]}");

        Map<Color, List<String>> perColor = new EnumMap<>(Color.class);
        // A floor pass costs two entries: the pass_floor tool call, then the
        // reply after its result — the same rhythm as the Strands scripts.
        List<String> red = new ArrayList<>(List.of(
                "{\"tool\": \"pass_floor\", \"args\": {\"to\": \"blue\", "
                        + "\"message\": \"ally against yellow?\", \"note\": \"I want a quiet table\"}}",
                "(floor passed)",
                "(nothing further)"));
        red.addAll(decides);
        red.addAll(reflects);
        perColor.put(Color.RED, red);

        List<String> blue = new ArrayList<>(List.of(
                "{\"tool\": \"pass_floor\", \"args\": {\"to\": \"red\", "
                        + "\"message\": \"agreed - yellow first\"}}",
                "(floor passed)",
                "(quiet)"));
        blue.addAll(decides);
        blue.addAll(reflects);
        perColor.put(Color.BLUE, blue);

        for (Color color : List.of(Color.GREEN, Color.YELLOW)) {
            List<String> script = new ArrayList<>(List.of("(quiet)"));
            script.addAll(decides);
            script.addAll(reflects);
            perColor.put(color, script);
        }

        Map<Color, ChatModel> models = new EnumMap<>(Color.class);
        perColor.forEach((color, script) -> models.put(color, new ScriptedChatModel(script)));
        return models;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            System.err.println("usage: Demo <out.jsonl>");
            System.exit(2);
        }
        Path out = Path.of(args[0]);
        try (Writer writer = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
            Harness harness = new Harness(
                    ModelsConfig.load("dev"), Prompts.load(), scripts(),
                    new EventSink.JsonlSink(writer), 7, 0, 4);
            Outcome outcome = harness.play();
            System.out.printf("%s: %s after %d turns%n", out, outcome.reason(), outcome.turnsPlayed());
        }
    }
}
