package com.llmeval.alibi.springai;

import java.io.IOException;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

import org.springframework.ai.chat.model.ChatModel;

import com.llmeval.alibi.engine.Color;
import com.llmeval.alibi.engine.EventSink;
import com.llmeval.alibi.engine.Outcome;

/**
 * One scripted case, end to end — free, offline, deterministic.
 *
 * <pre>./mvnw -q -B exec:java -Dexec.args="../games/scripted-springai-seed7.jsonl"</pre>
 *
 * <p><strong>The same seed-7 story as the Strands and LangGraph fixtures</strong>:
 * red is fed both red herrings on turn 1, cross-checks the witness on turn 5,
 * and accuses correctly. The engine-event skeletons of all three fixtures must
 * agree — the eval mechanises that check.
 *
 * <p>A consultation costs two script entries (the tool call, then the reply
 * after its result) but produces ONE {@code llm_call}: Spring AI executes the
 * tool inside the model call and aggregates usage — this stack's recorded
 * grain, visible in the fixture's call counts.
 */
public final class Demo {

    private Demo() {}

    static Map<Color, ChatModel> scripts() {
        Map<Color, List<String>> perColor = new EnumMap<>(Color.class);

        perColor.put(Color.RED, List.of(
                // -- turn 1: seduced by the archive --
                "{\"tool\": \"consult_archivist\", \"args\": "
                        + "{\"query\": \"photographer cloakroom service hatch\"}}",
                "{\"action\": \"suggest\", \"who\": \"magician\", \"how\": \"service-hatch\", "
                        + "\"where\": \"terrace\", \"note\": \"The service hatch keeps coming up "
                        + "in the logs.\", \"reasoning\": \"Bluff my own terrace, probe the "
                        + "magician, and watch who twitches at the hatch.\"}",
                "{\"action\": \"wait\"}",
                "{\"who\": \"heiress\", \"how\": \"duplicate-key\", \"where\": \"vault-room\", "
                        + "\"confidence\": {\"who\": 0.25, \"how\": 0.3, \"where\": 0.2}}",
                "[{\"kind\": \"observation\", \"about\": \"photographer\", \"text\": \"Asha Nair "
                        + "puts the photographer on the main stage all night. Check Nair before "
                        + "trusting it.\"}, {\"kind\": \"plan\", \"text\": \"Hatch and cloakroom "
                        + "both conveniently ruled out. Verify those witnesses too.\"}]",
                // -- turn 5: the cross-check --
                "{\"tool\": \"consult_archivist\", \"args\": "
                        + "{\"query\": \"security guard Asha Nair\"}}",
                "{\"action\": \"pass\", \"reasoning\": \"Nair left before ten. Her photographer "
                        + "alibi is secondhand, and the other two convenient exonerations smell "
                        + "the same.\"}",
                "{\"action\": \"accuse\", \"who\": \"photographer\", \"how\": \"service-hatch\", "
                        + "\"where\": \"cloakroom\", \"reasoning\": \"Strike the lying witnesses "
                        + "and the case reads plainly: no alibi, a hatch that was never bolted, "
                        + "a cloakroom that was never watched.\"}",
                "[{\"kind\": \"deduction\", \"about\": \"photographer\", \"text\": \"Nair was in "
                        + "the car park by ten. The photographer never had an alibi.\"}]"));

        perColor.put(Color.GREEN, List.of(
                "{\"show\": \"magician\"}",
                "{\"action\": \"pass\", \"reasoning\": \"Watch the table before spending "
                        + "questions.\"}",
                "{\"action\": \"wait\"}",
                "{\"who\": \"photographer\", \"how\": \"sleight-of-hand\", \"where\": \"terrace\", "
                        + "\"confidence\": {\"who\": 0.2, \"how\": 0.2, \"where\": 0.125}}",
                "[]"));

        perColor.put(Color.YELLOW, List.of(
                "{\"action\": \"pass\"}",
                "{\"action\": \"wait\"}",
                "{\"who\": \"photographer\", \"how\": \"service-hatch\", \"where\": \"kitchen\", "
                        + "\"confidence\": {\"who\": 0.2, \"how\": 0.25, \"where\": 0.14}}",
                "[{\"kind\": \"suspicion\", \"about\": \"red\", \"text\": \"Red pushed the hatch "
                        + "in an open note. Either a lead or a plant.\"}]"));

        perColor.put(Color.BLUE, List.of(
                "{\"action\": \"pass\"}",
                "{\"action\": \"wait\"}",
                "{\"who\": \"chef\", \"how\": \"duplicate-key\", \"where\": \"cloakroom\", "
                        + "\"confidence\": {\"who\": 0.2, \"how\": 0.25, \"where\": 0.14}}",
                "[]"));

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
        if (out.getParent() != null) {
            Files.createDirectories(out.getParent());
        }
        try (Writer writer = Files.newBufferedWriter(out, StandardCharsets.UTF_8)) {
            Harness harness = new Harness(
                    ModelsConfig.load("dev"), Prompts.load(), scripts(),
                    new EventSink.JsonlSink(writer), 7, 0, null);
            Outcome outcome = harness.play();
            System.out.printf("%s: %s after %d turns, %d metered calls, %d scripted tokens%n",
                    out, outcome.reason(), outcome.turnsPlayed(),
                    harness.meteredCalls(), harness.spent());
        }
    }
}
