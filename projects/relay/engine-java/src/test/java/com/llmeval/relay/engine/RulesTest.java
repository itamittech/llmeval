package com.llmeval.relay.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

/** The rules, asserted on this side of the language boundary rather than assumed. */
class RulesTest {

    private static Map<String, Runner> ladder() {
        Map<String, Runner> runners = new LinkedHashMap<>();
        for (String color : Game.COLORS) {
            runners.put(color, new LadderRunner());
        }
        return runners;
    }

    private static List<Map<String, Object>> eventsOf(EventSink.ListSink sink, String type) {
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

    // -- the generators --------------------------------------------------

    @Test
    void sameSeedSameTrack() {
        assertEquals(Track.generate(new Rng(7)), Track.generate(new Rng(7)));
    }

    @Test
    void trackShapeMatchesTheRules() {
        List<Stage> track = Track.generate(new Rng(3));
        assertEquals(Track.TRACK_STAGES, track.size());
        assertEquals("stage-01", track.get(0).id());
        assertEquals("stage-10", track.get(9).id());

        int[] counts = new int[4];
        for (Stage stage : track) {
            counts[stage.tier()]++;
        }
        assertEquals(4, counts[1]);
        assertEquals(4, counts[2]);
        assertEquals(2, counts[3]);
    }

    @Test
    void chainAnswersAreArithmetic() {
        for (int seed = 1; seed < 40; seed++) {
            for (Stage stage : Track.generate(new Rng(seed))) {
                if (stage.family().equals("chain")) {
                    assertEquals(stage.answer(), LadderRunner.solveChain(stage.prompt()));
                }
            }
        }
    }

    @Test
    void statedShiftCiphersDecodeAndUnknownOnesDoNot() {
        int decoded = 0;
        int withheld = 0;
        for (int seed = 1; seed < 60; seed++) {
            for (Stage stage : Track.generate(new Rng(seed))) {
                if (!stage.family().equals("cipher")) {
                    continue;
                }
                if (stage.tier() < 3) {
                    assertEquals(stage.answer(), LadderRunner.solveCipher(stage.prompt()));
                    decoded++;
                } else {
                    assertTrue(stage.prompt().contains("unknown number of places"));
                    assertNull(LadderRunner.solveCipher(stage.prompt()));
                    withheld++;
                }
            }
        }
        assertTrue(decoded > 10);
        assertTrue(withheld > 0);
    }

    @Test
    void promptsNeverMentionTheTier() {
        for (int seed = 1; seed < 30; seed++) {
            for (Stage stage : Track.generate(new Rng(seed))) {
                String lowered = stage.prompt().toLowerCase();
                assertFalse(lowered.contains("tier"));
                assertFalse(lowered.contains("difficult"));
            }
        }
    }

    // -- the clock and the commons ---------------------------------------

    @Test
    void escalatingDrainsOneSharedUnit() {
        EventSink.ListSink sink = new EventSink.ListSink();
        GameConfig config = new GameConfig(7, 40);
        Game game = new Game(config, sink);
        game.play(ladder());
        assertTrue(game.quota() < config.escalationQuota, "nobody escalated");

        boolean sawEscalation = false;
        for (Map<String, Object> event : eventsOf(sink, "stage_attempted")) {
            if (Boolean.TRUE.equals(payload(event).get("escalated"))) {
                sawEscalation = true;
                assertEquals(Game.TICK_ESCALATE, payload(event).get("ticks_charged"));
            }
        }
        assertTrue(sawEscalation);
    }

    @Test
    void escalatingOnAnEmptyPoolIsRefused() {
        EventSink.ListSink sink = new EventSink.ListSink();
        GameConfig config = new GameConfig(7, 40);
        config.escalationQuota = 0;
        new Game(config, sink).play(ladder());

        boolean refused = false;
        for (Map<String, Object> event : eventsOf(sink, "invalid_action")) {
            refused |= "escalate".equals(payload(event).get("phase"));
        }
        assertTrue(refused);
    }

    // -- the seal --------------------------------------------------------

    @Test
    void noTierEscapesBeforeTheEnd() {
        EventSink.ListSink sink = new EventSink.ListSink();
        new Game(new GameConfig(7, 40), sink).play(ladder());
        for (Map<String, Object> event : sink.events()) {
            if ("game_ended".equals(event.get("type"))) {
                continue;
            }
            assertFalse(Json.canonical(event).contains("\"tier\""),
                    event.get("type") + " leaked a tier");
        }
    }

    @Test
    void trackGeneratedCarriesPromptsOnly() {
        EventSink.ListSink sink = new EventSink.ListSink();
        new Game(new GameConfig(7, 4), sink).play(ladder());
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> stages =
                (List<Map<String, Object>>) payload(eventsOf(sink, "track_generated").get(0))
                        .get("stages");
        for (Map<String, Object> stage : stages) {
            // Order, not just membership. Map.of is unordered, so building this payload from
            // one produced a transcript that passed conformance (the digest sorts keys) while
            // no longer matching Python's byte for byte. Caught by diffing the files, pinned
            // here so it cannot come back.
            assertEquals(List.of("id", "family", "prompt"), List.copyOf(stage.keySet()));
        }
    }

    @Test
    void gameEndedOpensTheSeal() {
        EventSink.ListSink sink = new EventSink.ListSink();
        new Game(new GameConfig(7, 4), sink).play(ladder());
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> key =
                (List<Map<String, Object>>) payload(eventsOf(sink, "game_ended").get(0))
                        .get("track_key");
        assertEquals(Track.TRACK_STAGES, key.size());
        assertEquals(Set.of("id", "tier", "answer"), key.get(0).keySet());
    }

    // -- lanes -----------------------------------------------------------

    @Test
    void fourIdenticalBotsProduceFourIdenticalLanes() {
        // Free invariant the vectors carry: a port that breaks lane symmetry has a bug, and
        // nobody had to predict how it would break.
        EventSink.ListSink sink = new EventSink.ListSink();
        Outcome outcome = new Game(new GameConfig(7, 80), sink).play(ladder());
        Map<String, Object> first = outcome.standings().get(0);
        for (Map<String, Object> row : outcome.standings()) {
            assertEquals(first.get("stages_cleared"), row.get("stages_cleared"));
            assertEquals(first.get("ticks"), row.get("ticks"));
            assertEquals(first.get("escalations"), row.get("escalations"));
        }
    }

    @Test
    void aBrokenRunnerPassesRatherThanCrashingTheRace() {
        Map<String, Runner> broken = new LinkedHashMap<>();
        for (String color : Game.COLORS) {
            broken.put(color, ctx -> {
                throw new IllegalStateException("boom");
            });
        }
        EventSink.ListSink sink = new EventSink.ListSink();
        Outcome outcome = new Game(new GameConfig(7, 2), sink).play(broken);
        assertEquals(2, outcome.turnsPlayed());
        assertNotEquals(0, eventsOf(sink, "invalid_action").size());
    }
}
