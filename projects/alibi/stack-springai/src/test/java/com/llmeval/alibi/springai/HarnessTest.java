package com.llmeval.alibi.springai;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

import com.llmeval.alibi.engine.Color;
import com.llmeval.alibi.engine.EventSink;
import com.llmeval.alibi.engine.Json;
import com.llmeval.alibi.engine.Outcome;

/** The scripted game end to end — same story as the Python stacks, Spring grain. */
class HarnessTest {

    private static Harness harness;
    private static EventSink.ListSink sink;
    private static Outcome outcome;
    private static Map<Color, org.springframework.ai.chat.model.ChatModel> models;

    @BeforeAll
    static void play() {
        sink = new EventSink.ListSink();
        models = Demo.scripts();
        harness = new Harness(ModelsConfig.load("dev"), Prompts.load(), models,
                sink, 7, 0, null);
        outcome = harness.play();
    }

    private static List<Map<String, Object>> events(String type) {
        List<Map<String, Object>> found = new ArrayList<>();
        for (Map<String, Object> event : sink.events()) {
            if (type.equals(event.get("type"))) {
                found.add(event);
            }
        }
        return found;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> payload(Map<String, Object> event) {
        return (Map<String, Object>) event.get("payload");
    }

    @Test
    void redSolvesOnTurnFive() {
        assertEquals("solved", outcome.reason());
        assertEquals(5, outcome.turnsPlayed());
        assertEquals(Color.RED, outcome.winner());
    }

    @Test
    void internalToolExecutionAggregatesTheConsultation() {
        // 22 script entries, but two consultations ran INSIDE model calls:
        // the framework loops model -> tool -> model and hands back one
        // response, so this stack meters 20 calls where the Python stacks
        // metered 22. The recorded finding, now visible in a fixture.
        assertEquals(20, harness.meteredCalls());
        assertEquals(20, events("llm_call").size());
    }

    @Test
    void theArchivistToolRanForReal() {
        List<Map<String, Object>> searches = events("archive_searched");
        assertEquals(2, searches.size());
        assertEquals("photographer cloakroom service hatch",
                payload(searches.get(0)).get("query"));
        assertEquals(List.of("doc-016", "doc-018", "doc-013"),
                payload(searches.get(0)).get("results"));
        assertEquals(List.of("doc-002", "doc-009"),
                payload(searches.get(1)).get("results"));
    }

    @Test
    void refutationWasTheDetectivesChoice() {
        Map<String, Object> refutation = payload(events("refutation_made").get(0));
        assertEquals("green", refutation.get("refuter"));
        assertEquals("magician", refutation.get("element"));
        assertEquals("detective", refutation.get("chosen_by"));
    }

    @Test
    void notebookIsHandRolledAndWritten() {
        assertEquals(4, events("memory_write").size());
        assertEquals(3, harness.notebook(Color.RED).size());
    }

    @Test
    void inFictionNotePassedTheGuardrails() {
        assertTrue(events("guardrail_triggered").isEmpty());
        assertEquals("The service hatch keeps coming up in the logs.",
                payload(events("suggestion_made").get(0)).get("note"));
    }

    @Test
    void promptsNeverLeakAnotherHand() {
        for (Color reader : Color.values()) {
            String seen = String.join("\n",
                    ((ScriptedChatModel) models.get(reader)).seen());
            for (Color owner : Color.values()) {
                if (owner == reader) {
                    continue;
                }
                String hand = String.join(", ", harness.game().caseModel().hand(owner));
                assertFalse(seen.contains(hand),
                        reader + " saw " + owner + "'s hand");
            }
        }
    }

    @Test
    void provenanceNamesThisFramework() {
        Map<String, Object> started = payload(sink.events().get(0));
        assertEquals("springai", started.get("stack"));
        assertNotNull(started.get("prompt_set"));
        assertNotNull(started.get("archivist"));
    }

    @Test
    @SuppressWarnings("unchecked")
    void engineSkeletonMatchesThePythonFixtures() throws Exception {
        Path strands = Path.of("../games/scripted-strands-seed7.jsonl");
        assertTrue(Files.exists(strands), "Strands fixture missing");

        Set<String> engineTypes = Set.of("case_dealt", "archive_generated",
                "turn_started", "archive_searched", "suggestion_made",
                "refutation_made", "accusation_made", "detective_eliminated",
                "belief_declared", "invalid_action", "turn_ended", "game_ended");

        List<String> mine = new ArrayList<>();
        for (Map<String, Object> event : sink.events()) {
            if (engineTypes.contains(event.get("type"))) {
                mine.add(event.get("turn") + "|" + event.get("type") + "|"
                        + Json.canonical(event.get("payload")));
            }
        }
        List<String> theirs = new ArrayList<>();
        for (String line : Files.readAllLines(strands, StandardCharsets.UTF_8)) {
            if (line.isBlank()) {
                continue;
            }
            Map<String, Object> event = (Map<String, Object>) Json.parse(line);
            if (engineTypes.contains(event.get("type"))) {
                theirs.add(event.get("turn") + "|" + event.get("type") + "|"
                        + Json.canonical(event.get("payload")));
            }
        }
        assertEquals(theirs, mine);
    }

    @Test
    void promptDigestMatchesThePythonLoaders() throws Exception {
        // Three independent loaders in two languages must hash the same set.
        String fixture = Files.readAllLines(
                Path.of("../games/scripted-strands-seed7.jsonl"),
                StandardCharsets.UTF_8).get(0);
        @SuppressWarnings("unchecked")
        Map<String, Object> started = (Map<String, Object>)
                ((Map<String, Object>) Json.parse(fixture)).get("payload");
        @SuppressWarnings("unchecked")
        Map<String, Object> promptSet = (Map<String, Object>) started.get("prompt_set");
        assertEquals(promptSet.get("hash"), Prompts.load().digest());
    }
}
