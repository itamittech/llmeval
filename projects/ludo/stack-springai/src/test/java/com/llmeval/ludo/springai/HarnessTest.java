package com.llmeval.ludo.springai;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.ai.chat.model.ChatModel;

import com.llmeval.ludo.engine.Color;
import com.llmeval.ludo.engine.EventSink;
import com.llmeval.ludo.engine.Outcome;

/**
 * The turn loop end to end against the scripted ChatModel — the harness
 * contract's §8 seam, at the framework's own extension point. Everything here
 * is offline and deterministic: seeded dice, committed replies.
 */
class HarnessTest {

    private static final Set<String> SCHEMA_TYPES = Set.of(
            "game_started", "turn_started", "dice_rolled", "move_made", "token_captured",
            "token_home", "extra_roll_granted", "illegal_move_rejected", "turn_ended",
            "player_finished", "game_ended",
            "agent_reasoning", "message_sent", "memory_write", "context_compacted",
            "llm_call", "guardrail_triggered");

    private static Map<Color, ChatModel> models(Map<Color, List<String>> scripts) {
        Map<Color, ChatModel> models = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            models.put(color, new ScriptedChatModel(scripts.getOrDefault(color, List.of())));
        }
        return models;
    }

    private static List<Map<String, Object>> ofType(EventSink.ListSink sink, String type) {
        return sink.events().stream().filter(e -> type.equals(e.get("type"))).toList();
    }

    @Test
    void theTableRunsTheFloorPassingProtocol() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Harness harness = new Harness(ModelsConfig.load("dev"), Prompts.load(), models(Map.of(
                Color.RED, List.of(
                        "{\"to\": \"blue\", \"message\": \"ally against yellow?\", \"note\": \"quiet table\"}",
                        "(nothing further)",
                        "{\"token\": 0, \"to\": 0, \"reasoning\": \"out\"}",
                        "{\"notes\": []}"),
                Color.BLUE, List.of("{\"to\": \"red\", \"message\": \"agreed - yellow first\"}"))),
                sink, 7, 0, 1);

        harness.play();   // one turn: red negotiates, rolls, reflects

        List<Map<String, Object>> sent = ofType(sink, "message_sent");
        assertEquals(3, sent.size());
        @SuppressWarnings("unchecked")
        Map<String, Object> first = (Map<String, Object>) sent.get(0).get("payload");
        assertEquals("red", first.get("player"));
        assertEquals("blue", first.get("to"));
        @SuppressWarnings("unchecked")
        Map<String, Object> note = (Map<String, Object>) sent.get(1).get("payload");
        assertEquals(null, note.get("to"));   // the table note is public
        @SuppressWarnings("unchecked")
        Map<String, Object> replyBack = (Map<String, Object>) sent.get(2).get("payload");
        assertEquals("blue", replyBack.get("player"));
        assertEquals("red", replyBack.get("to"));
    }

    @Test
    void everyModelCallEmitsOneLlmCall() {
        // Seed 7, turn 1: red rolls a 5 — no legal move, so choose never runs
        // and the turn is exactly negotiate + reflect. Two calls, two events.
        EventSink.ListSink sink = new EventSink.ListSink();
        Harness harness = new Harness(ModelsConfig.load("dev"), Prompts.load(), models(Map.of(
                Color.RED, List.of(
                        "(quiet)",
                        "{\"notes\": [{\"kind\": \"commitment\", \"about\": \"blue\", \"text\": \"promised\"}]}"))),
                sink, 7, 0, 1);

        harness.play();

        List<Map<String, Object>> calls = ofType(sink, "llm_call");
        assertEquals(2, calls.size());
        for (Map<String, Object> call : calls) {
            @SuppressWarnings("unchecked")
            Map<String, Object> p = (Map<String, Object>) call.get("payload");
            assertEquals("scripted", p.get("model"));
            assertTrue(Set.of("negotiate", "reflect").contains(p.get("purpose")));
            @SuppressWarnings("unchecked")
            Map<String, Object> tokens = (Map<String, Object>) p.get("tokens");
            assertTrue((int) tokens.get("input") > 0);
        }
        List<Map<String, Object>> writes = ofType(sink, "memory_write");
        assertEquals(1, writes.size());
        @SuppressWarnings("unchecked")
        Map<String, Object> written = (Map<String, Object>) writes.get(0).get("payload");
        assertEquals("commitment", written.get("kind"));
        assertEquals("blue", written.get("about"));
    }

    @Test
    void aFullScriptedGameIsWellFormed() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Harness harness = new Harness(ModelsConfig.load("dev"), Prompts.load(), Demo.scripts(),
                sink, 7, 0, 4);

        Outcome outcome = harness.play();

        List<Map<String, Object>> events = sink.events();
        assertEquals("game_started", events.get(0).get("type"));
        assertEquals("game_ended", events.get(events.size() - 1).get("type"));
        assertEquals("turn_cap", outcome.reason());
        for (int i = 0; i < events.size(); i++) {
            assertEquals(i, events.get(i).get("seq"));   // one shared sequence, no gaps
            assertTrue(SCHEMA_TYPES.contains(events.get(i).get("type")));
        }
        assertEquals(ofType(sink, "turn_started").size(), ofType(sink, "turn_ended").size());
    }

    @Test
    void aSpentBudgetForfeitsInsteadOfCrashing() {
        // Ceiling of zero: negotiate and reflect skip, choose throws, the engine
        // records forfeits, and the game still ends with a valid transcript.
        EventSink.ListSink sink = new EventSink.ListSink();
        ModelsConfig.Profile dev = ModelsConfig.load("dev");
        ModelsConfig.Profile broke = new ModelsConfig.Profile(dev.name(), dev.seats(), dev.judge(),
                new ModelsConfig.Budgets(dev.budgets().maxTurns(), dev.budgets().maxFloorPasses(),
                        dev.budgets().maxMessageChars(), dev.budgets().maxContextTokens(), 0));
        Harness harness = new Harness(broke, Prompts.load(), models(Map.of()), sink, 7, 0, 2);

        Outcome outcome = harness.play();

        assertEquals("turn_cap", outcome.reason());
        assertEquals(0, ofType(sink, "llm_call").size());
        assertEquals("game_ended", sink.events().get(sink.events().size() - 1).get("type"));
    }

    @Test
    void promptsLoadWithParityInvariants() {
        Prompts prompts = Prompts.load();
        assertTrue(prompts.digest().startsWith("sha256:"));
        assertEquals(Set.of("negotiate", "briefing", "decide", "retry", "reflect"), prompts.turnNames());
        String once = prompts.systemPrompt(Map.of(
                "color", "red", "max_floor_passes", 3, "max_message_chars", 240));
        assertTrue(once.contains("red"));
        assertTrue(!once.contains("{{"));
        assertThrows(IllegalArgumentException.class, () ->
                prompts.turn("decide").render(Map.of("turn", 1)));
    }

    @Test
    void seatRotationCyclesInFourGames() {
        ModelsConfig.Profile profile = ModelsConfig.load("dev");
        Map<Color, ModelsConfig.Seat> game0 = ModelsConfig.seating(profile, 0);
        Map<Color, ModelsConfig.Seat> game1 = ModelsConfig.seating(profile, 1);
        Map<Color, ModelsConfig.Seat> game4 = ModelsConfig.seating(profile, 4);

        assertEquals(1, game0.get(Color.RED).seat());
        assertEquals(2, game1.get(Color.RED).seat());       // shifted by one
        assertNotEquals(game0.get(Color.RED), game1.get(Color.RED));
        assertEquals(game0, game4);                          // a full rotation is four games
    }
}
