package com.llmeval.alibi.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class RulesTest {

    /** A puppet detective the tests steer per phase. */
    private static class Stub implements Detective {
        Suggestion suggestion;
        Triple accusation;

        @Override
        public Suggestion suggest(TurnContext ctx) {
            return suggestion;
        }

        @Override
        public String show(ShowContext ctx) {
            return ctx.options().get(0);
        }

        @Override
        public Triple accuse(TurnContext ctx) {
            return accusation;
        }

        @Override
        public Belief conclude(TurnContext ctx) {
            Map<String, Double> confidence = new LinkedHashMap<>();
            for (String dim : CaseModel.DIMENSIONS) {
                confidence.put(dim, 0.5);
            }
            return new Belief(CaseModel.WHO.get(0), CaseModel.HOW.get(0),
                    CaseModel.WHERE.get(0), confidence);
        }

        @Override
        public String name() {
            return "stub";
        }
    }

    private static Map<Color, Detective> stubs() {
        Map<Color, Detective> detectives = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            detectives.put(color, new Stub());
        }
        return detectives;
    }

    @Test
    void dealPartitionsElements() {
        CaseModel caseModel = CaseModel.deal(new Rng(9));
        Set<String> dealt = new HashSet<>();
        int total = 0;
        for (Color color : Color.values()) {
            List<String> hand = caseModel.hand(color);
            assertEquals(4, hand.size());
            dealt.addAll(hand);
            total += hand.size();
        }
        assertEquals(16, total);
        assertEquals(16, dealt.size());
        for (String element : caseModel.solution().values()) {
            assertFalse(dealt.contains(element));
        }
    }

    @Test
    void archiveTruthModelHolds() {
        for (int seed = 1; seed <= 10; seed++) {
            Rng rng = new Rng(seed);
            CaseModel caseModel = CaseModel.deal(rng);
            Archive archive = Archive.generate(caseModel, rng);

            assertEquals(20, archive.documents().size());
            List<String> herrings = archive.redHerrings();
            assertEquals(3, herrings.size());

            Set<String> solution = new HashSet<>(caseModel.solution().values());
            for (Archive.Document doc : archive.documents()) {
                if (doc.assertsNot() == null) {
                    continue;
                }
                if (doc.truthful()) {
                    assertFalse(solution.contains(doc.assertsNot()),
                            "seed " + seed + ": truthful doc targets the solution");
                } else {
                    assertTrue(solution.contains(doc.assertsNot()),
                            "seed " + seed + ": herring misses the solution");
                }
            }
        }
    }

    @Test
    void nobodyCanRefuteTheSolution() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Game game = new Game(new GameConfig(1, 1), sink);
        Map<String, String> s = game.caseModel().solution();
        Map<Color, Detective> detectives = stubs();
        ((Stub) detectives.get(Color.RED)).suggestion =
                new Suggestion(s.get("who"), s.get("how"), s.get("where"));
        game.play(detectives);

        Map<String, Object> refutation = sink.events().stream()
                .filter(e -> "refutation_made".equals(e.get("type")))
                .findFirst().orElseThrow();
        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) refutation.get("payload");
        assertNull(payload.get("refuter"));
        assertNull(payload.get("element"));
    }

    @Test
    void correctAccusationWins() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Game game = new Game(new GameConfig(3, 40), sink);
        Map<String, String> s = game.caseModel().solution();
        Map<Color, Detective> detectives = stubs();
        ((Stub) detectives.get(Color.RED)).accusation =
                new Triple(s.get("who"), s.get("how"), s.get("where"));
        Outcome outcome = game.play(detectives);

        assertEquals("solved", outcome.reason());
        assertEquals(Color.RED, outcome.winner());
        assertEquals(1, outcome.turnsPlayed());
    }

    @Test
    void wrongAccusationEliminates() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Game game = new Game(new GameConfig(4, 6), sink);
        Map<String, String> s = game.caseModel().solution();
        Map<Color, Detective> detectives = stubs();
        String wrongWho = CaseModel.WHO.stream()
                .filter(e -> !e.equals(s.get("who"))).findFirst().orElseThrow();
        ((Stub) detectives.get(Color.RED)).accusation =
                new Triple(wrongWho, s.get("how"), s.get("where"));
        Outcome outcome = game.play(detectives);

        assertTrue(sink.events().stream().anyMatch(e -> "detective_eliminated".equals(e.get("type"))));
        assertNull(outcome.winner());
    }

    @Test
    void eliminationBotsSolveEveryCase() {
        for (int seed = 1; seed <= 5; seed++) {
            Outcome outcome = new Game(new GameConfig(seed, 60), new EventSink.ListSink())
                    .play(allBots());
            assertEquals("solved", outcome.reason(), "seed " + seed);
            assertNotNull(outcome.winner());
        }
    }

    @Test
    void searchIsDeterministicAndBounded() {
        Rng rng = new Rng(7);
        Archive archive = Archive.generate(CaseModel.deal(rng), rng);
        List<String> first = ids(archive.search("vault key manager"));
        List<String> second = ids(archive.search("vault key manager"));
        assertEquals(first, second);
        assertTrue(first.size() <= Archive.SEARCH_K);
        assertEquals(List.of(), archive.search("zzzz qqqq xxxx"));
    }

    private static List<String> ids(List<Archive.Document> docs) {
        List<String> ids = new ArrayList<>();
        for (Archive.Document doc : docs) {
            ids.add(doc.id());
        }
        return ids;
    }

    private static Map<Color, Detective> allBots() {
        Map<Color, Detective> detectives = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            detectives.put(color, new EliminationBot());
        }
        return detectives;
    }
}
