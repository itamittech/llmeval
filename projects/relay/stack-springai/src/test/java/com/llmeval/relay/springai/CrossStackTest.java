package com.llmeval.relay.springai;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.llmeval.relay.engine.EventSink;
import com.llmeval.relay.engine.Json;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.Test;

/**
 * Three harnesses, one race.
 *
 * <p>This test reads a fixture written by <em>Python</em>, in another virtual environment, by
 * another framework, and asserts that the engine's own events are identical to this stack's. It
 * is the reason any cross-stack number in the matrix means anything: two stacks that disagree
 * about the race are not comparable at all, and a difference reported without this check would be
 * indistinguishable from a bug.
 */
class CrossStackTest {

    private static final Set<String> ENGINE_EVENTS = Set.of(
            "game_started", "track_generated", "turn_started", "stage_attempted",
            "runner_finished", "invalid_action", "turn_ended", "game_ended");

    /** Keys that are the stack's business rather than the race's. */
    private static final List<String> STACK_KEYS =
            List.of("stack", "framework", "players", "anchor", "engine");

    private static Path games() {
        return Prompts.repoRoot().resolve("projects/relay/games");
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> read(Path path) throws IOException {
        List<Map<String, Object>> events = new ArrayList<>();
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (!line.isBlank()) {
                events.add((Map<String, Object>) Json.parse(line));
            }
        }
        return events;
    }

    @SuppressWarnings("unchecked")
    private static List<String> spine(List<Map<String, Object>> events) {
        List<String> out = new ArrayList<>();
        for (Map<String, Object> event : events) {
            if (!ENGINE_EVENTS.contains(event.get("type"))) {
                continue;
            }
            Map<String, Object> payload =
                    new LinkedHashMap<>((Map<String, Object>) event.get("payload"));
            if ("game_started".equals(event.get("type"))) {
                STACK_KEYS.forEach(payload::remove);
            }
            Map<String, Object> slim = new LinkedHashMap<>();
            slim.put("turn", ((Number) event.get("turn")).intValue());
            slim.put("type", event.get("type"));
            slim.put("payload", payload);
            out.add(Json.canonical(slim));
        }
        return out;
    }

    private static List<Map<String, Object>> ours() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Demo.build(sink).play();
        return sink.events();
    }

    @Test
    void theEngineSpineMatchesTheStrandsFixture() throws IOException {
        Path fixture = games().resolve("scripted-strands-seed7.jsonl");
        Assumptions.assumeTrue(Files.exists(fixture), "Strands fixture not committed");
        assertEquals(spine(read(fixture)), spine(ours()));
    }

    @Test
    void theEngineSpineMatchesTheLangGraphFixture() throws IOException {
        Path fixture = games().resolve("scripted-langgraph-seed7.jsonl");
        Assumptions.assumeTrue(Files.exists(fixture), "LangGraph fixture not committed");
        assertEquals(spine(read(fixture)), spine(ours()));
    }

    /**
     * Three independent loaders, two languages, one digest — the property both earlier games
     * earned, inherited here on day one because the loader is a port of proven code.
     */
    @Test
    @SuppressWarnings("unchecked")
    void thePromptSetHashAgreesAcrossLanguages() throws IOException {
        Path fixture = games().resolve("scripted-strands-seed7.jsonl");
        Assumptions.assumeTrue(Files.exists(fixture), "Strands fixture not committed");

        Map<String, Object> theirs = null;
        for (Map<String, Object> event : read(fixture)) {
            if ("game_started".equals(event.get("type"))) {
                theirs = (Map<String, Object>) ((Map<String, Object>) event.get("payload"))
                        .get("prompt_set");
            }
        }
        assertTrue(theirs != null && ((String) theirs.get("hash")).startsWith("sha256:"));
        assertEquals(theirs.get("hash"), Prompts.load().digest());
    }
}
