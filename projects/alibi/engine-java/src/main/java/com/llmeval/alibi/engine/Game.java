package com.llmeval.alibi.engine;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The turn loop — ALIBI's referee, ported from the Python engine's {@code game.py}.
 *
 * <p>Every payload is built in the same key order as the Python dict literals, so transcripts
 * from the two engines stay byte-comparable line by line, not merely digest-equal.
 */
public final class Game {

    public static final String ENGINE_VERSION = "0.1.0";
    static final int PHASE_ATTEMPTS = 2;

    private final GameConfig config;
    private final EventSink sink;
    private final CaseModel caseModel;
    private final Archive archive;
    private final Map<Color, PlayerState> players = new EnumMap<>(Color.class);
    private final List<SuggestionRecord> log = new ArrayList<>();
    private int turn;
    private int rotation = -1;
    private Color solvedBy;
    private List<Map<String, Object>> turnEvents = new ArrayList<>();
    private Map<Color, Detective> detectives;

    private static final class PlayerState {
        final List<String> hand;
        final Map<String, Color> shown = new LinkedHashMap<>();
        boolean eliminated;
        Belief lastBelief;
        int suggestionsMade;
        int refutationsGiven;
        int searchesMade;

        PlayerState(List<String> hand) {
            this.hand = hand;
        }
    }

    public Game(GameConfig config, EventSink sink) {
        this.config = config;
        this.sink = sink;
        // One RNG, one draw order: the deal consumes first, the archive next.
        Rng rng = new Rng(config.seed());
        this.caseModel = CaseModel.deal(rng);
        this.archive = Archive.generate(caseModel, rng);
        for (Color color : Color.values()) {
            players.put(color, new PlayerState(caseModel.hand(color)));
        }
    }

    CaseModel caseModel() {
        return caseModel;
    }

    Archive archive() {
        return archive;
    }

    // -- public ----------------------------------------------------------

    public Outcome play(Map<Color, Detective> detectives) {
        this.detectives = detectives;
        emitStart(detectives);

        Map<String, Object> hands = new LinkedHashMap<>();
        for (Color color : Color.values()) {
            hands.put(color.json(), new ArrayList<>(players.get(color).hand));
        }
        Map<String, Object> dealt = new LinkedHashMap<>();
        dealt.put("hands", hands);
        emit("case_dealt", dealt);

        List<Object> documents = new ArrayList<>();
        for (Archive.Document doc : archive.documents()) {
            documents.add(doc.payload());
        }
        Map<String, Object> generated = new LinkedHashMap<>();
        generated.put("documents", documents);
        emit("archive_generated", generated);

        while (turn < config.maxTurns() && solvedBy == null && anyActive()) {
            Color color = nextPlayer();
            turn++;
            playTurn(color, detectives.get(color));
        }

        String reason;
        if (solvedBy != null) {
            reason = "solved";
        } else if (!anyActive()) {
            reason = "all_eliminated";
        } else {
            reason = "turn_cap";
        }

        List<Map<String, Object>> standings = standings();
        Map<String, Object> ended = new LinkedHashMap<>();
        ended.put("reason", reason);
        ended.put("turns_played", turn);
        ended.put("solution", new LinkedHashMap<>(caseModel.solution()));
        ended.put("red_herrings", archive.redHerrings());
        ended.put("standings", standings);
        emit("game_ended", ended);

        return new Outcome(reason, turn, caseModel.solution(), standings);
    }

    // -- turn ------------------------------------------------------------

    private void playTurn(Color color, Detective detective) {
        turnEvents = new ArrayList<>();
        Map<String, Object> started = new LinkedHashMap<>();
        started.put("player", color.json());
        emit("turn_started", started);

        SearchBudget budget = budget(color);

        Suggestion suggestion = phaseSuggest(color, detective, budget);
        TurnContext.Refutation refutation = null;
        Suggestion noRefutation = null;

        if (suggestion != null) {
            players.get(color).suggestionsMade++;
            Map<String, Object> made = new LinkedHashMap<>();
            made.put("player", color.json());
            made.put("who", suggestion.who());
            made.put("how", suggestion.how());
            made.put("where", suggestion.where());
            made.put("note", suggestion.note());
            emit("suggestion_made", made);

            RefutationOutcome outcome = resolveRefutation(color, suggestion);
            refutation = outcome.refutation();
            noRefutation = outcome.noRefutation();
        }

        String reason = phaseAccuse(color, detective, budget, refutation, noRefutation);

        if (reason == null) {
            reason = suggestion != null ? "played" : "passed";
            phaseConclude(color, detective, budget);
        }

        Map<String, Object> ended = new LinkedHashMap<>();
        ended.put("player", color.json());
        ended.put("reason", reason);
        emit("turn_ended", ended);

        detective.reflect(new TurnEnd(view(color), color, turn, reason, List.copyOf(turnEvents)));
    }

    private Suggestion phaseSuggest(Color color, Detective detective, SearchBudget budget) {
        for (int attempt = 1; attempt <= PHASE_ATTEMPTS; attempt++) {
            TurnContext ctx = new TurnContext(view(color), color, turn, budget, attempt);
            Suggestion suggestion;
            try {
                suggestion = detective.suggest(ctx);
            } catch (RuntimeException exc) { // a broken agent passes; it does not crash the game
                invalid(color, "suggest", "decider error: " + exc.getClass().getSimpleName(), attempt);
                continue;
            }
            if (suggestion == null || validTriple(suggestion.who(), suggestion.how(), suggestion.where())) {
                return suggestion;
            }
            invalid(color, "suggest", "unknown element or wrong dimension", attempt);
        }
        return null;
    }

    private record RefutationOutcome(TurnContext.Refutation refutation, Suggestion noRefutation) {}

    private RefutationOutcome resolveRefutation(Color suggester, Suggestion suggestion) {
        Set<String> named = new HashSet<>(suggestion.named());
        Color refuter = null;
        for (Color candidate : clockwiseFrom(suggester)) {
            Set<String> overlap = new HashSet<>(players.get(candidate).hand);
            overlap.retainAll(named);
            if (!overlap.isEmpty()) {
                refuter = candidate;
                break;
            }
        }

        if (refuter == null) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("suggester", suggester.json());
            payload.put("refuter", null);
            payload.put("element", null);
            emit("refutation_made", payload);
            log.add(new SuggestionRecord(turn, suggester, suggestion.who(), suggestion.how(),
                    suggestion.where(), suggestion.note(), null));
            return new RefutationOutcome(null, suggestion);
        }

        List<String> options = new ArrayList<>();
        for (String element : players.get(refuter).hand) {
            if (named.contains(element)) {
                options.add(element);
            }
        }

        ShownChoice choice = phaseShow(refuter, suggester, suggestion, options);

        players.get(suggester).shown.put(choice.element(), refuter);
        players.get(refuter).refutationsGiven++;
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("suggester", suggester.json());
        payload.put("refuter", refuter.json());
        payload.put("element", choice.element());
        payload.put("chosen_by", choice.chosenBy());
        emit("refutation_made", payload);
        log.add(new SuggestionRecord(turn, suggester, suggestion.who(), suggestion.how(),
                suggestion.where(), suggestion.note(), refuter));
        return new RefutationOutcome(new TurnContext.Refutation(refuter, choice.element()), null);
    }

    private record ShownChoice(String element, String chosenBy) {}

    private ShownChoice phaseShow(Color refuter, Color suggester, Suggestion suggestion,
                                  List<String> options) {
        Detective detective = detectives.get(refuter);
        ShowContext ctx = new ShowContext(view(refuter), refuter, turn, suggester,
                suggestion, List.copyOf(options));
        String element;
        try {
            element = detective.show(ctx);
        } catch (RuntimeException exc) {
            invalid(refuter, "show", "decider error: " + exc.getClass().getSimpleName(), 1);
            return new ShownChoice(options.get(0), "engine");
        }
        if (options.contains(element)) {
            return new ShownChoice(element, "detective");
        }
        invalid(refuter, "show", "not a held, named element", 1);
        return new ShownChoice(options.get(0), "engine");
    }

    private String phaseAccuse(Color color, Detective detective, SearchBudget budget,
                               TurnContext.Refutation refutation, Suggestion noRefutation) {
        Triple triple = null;
        for (int attempt = 1; attempt <= PHASE_ATTEMPTS; attempt++) {
            TurnContext ctx = new TurnContext(view(color), color, turn, budget, attempt,
                    refutation, noRefutation);
            Triple candidate;
            try {
                candidate = detective.accuse(ctx);
            } catch (RuntimeException exc) {
                invalid(color, "accuse", "decider error: " + exc.getClass().getSimpleName(), attempt);
                continue;
            }
            if (candidate == null) {
                return null;
            }
            if (validTriple(candidate.who(), candidate.how(), candidate.where())) {
                triple = candidate;
                break;
            }
            invalid(color, "accuse", "unknown element or wrong dimension", attempt);
        }

        if (triple == null) {
            return null;
        }

        boolean correct = triple.who().equals(caseModel.solution().get("who"))
                && triple.how().equals(caseModel.solution().get("how"))
                && triple.where().equals(caseModel.solution().get("where"));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("player", color.json());
        payload.put("who", triple.who());
        payload.put("how", triple.how());
        payload.put("where", triple.where());
        payload.put("correct", correct);
        emit("accusation_made", payload);

        if (correct) {
            solvedBy = color;
            return "solved";
        }
        players.get(color).eliminated = true;
        Map<String, Object> eliminated = new LinkedHashMap<>();
        eliminated.put("player", color.json());
        emit("detective_eliminated", eliminated);
        return "eliminated";
    }

    private void phaseConclude(Color color, Detective detective, SearchBudget budget) {
        for (int attempt = 1; attempt <= PHASE_ATTEMPTS; attempt++) {
            TurnContext ctx = new TurnContext(view(color), color, turn, budget, attempt);
            Belief belief;
            try {
                belief = detective.conclude(ctx);
            } catch (RuntimeException exc) {
                invalid(color, "conclude", "decider error: " + exc.getClass().getSimpleName(), attempt);
                continue;
            }
            if (validBelief(belief)) {
                players.get(color).lastBelief = belief;
                Map<String, Object> confidence = new LinkedHashMap<>();
                for (String dim : CaseModel.DIMENSIONS) {
                    confidence.put(dim, belief.confidence().get(dim));
                }
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("player", color.json());
                payload.put("who", belief.who());
                payload.put("how", belief.how());
                payload.put("where", belief.where());
                payload.put("confidence", confidence);
                emit("belief_declared", payload);
                return;
            }
            invalid(color, "conclude", "invalid belief", attempt);
        }
    }

    // -- plumbing --------------------------------------------------------

    private SearchBudget budget(Color color) {
        SearchBudget[] holder = new SearchBudget[1];
        holder[0] = new SearchBudget(archive, config.maxSearchesPerTurn(), (query, results) -> {
            if (results == null) {
                invalid(color, "search", "search quota exhausted", 1);
                return;
            }
            players.get(color).searchesMade++;
            List<String> ids = new ArrayList<>();
            for (Archive.Document doc : results) {
                ids.add(doc.id());
            }
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("player", color.json());
            payload.put("query", query);
            payload.put("results", ids);
            payload.put("quota_left", holder[0].quotaLeft());
            emit("archive_searched", payload);
        });
        return holder[0];
    }

    private DetectiveView view(Color color) {
        PlayerState state = players.get(color);
        List<Color> eliminated = new ArrayList<>();
        for (Color candidate : Color.values()) {
            if (players.get(candidate).eliminated) {
                eliminated.add(candidate);
            }
        }
        return new DetectiveView(color, state.hand, state.shown, eliminated, log);
    }

    private List<Color> clockwiseFrom(Color color) {
        Color[] colors = Color.values();
        int index = color.ordinal();
        List<Color> order = new ArrayList<>();
        for (int k = 1; k < colors.length; k++) {
            order.add(colors[(index + k) % colors.length]);
        }
        return order;
    }

    private boolean anyActive() {
        for (Color color : Color.values()) {
            if (!players.get(color).eliminated) {
                return true;
            }
        }
        return false;
    }

    private Color nextPlayer() {
        while (true) {
            rotation = (rotation + 1) % Color.values().length;
            Color color = Color.values()[rotation];
            if (!players.get(color).eliminated) {
                return color;
            }
        }
    }

    private boolean validTriple(String who, String how, String where) {
        return CaseModel.WHO.contains(who) && CaseModel.HOW.contains(how)
                && CaseModel.WHERE.contains(where);
    }

    private boolean validBelief(Belief belief) {
        if (belief == null || !validTriple(belief.who(), belief.how(), belief.where())) {
            return false;
        }
        Map<String, Double> conf = belief.confidence();
        if (conf == null) {
            return false;
        }
        for (String dim : CaseModel.DIMENSIONS) {
            Double value = conf.get(dim);
            if (value == null || value < 0 || value > 1) {
                return false;
            }
        }
        return true;
    }

    private void invalid(Color color, String phase, String reason, int attempt) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("player", color.json());
        payload.put("phase", phase);
        payload.put("reason", reason);
        payload.put("attempt", attempt);
        emit("invalid_action", payload);
    }

    private int beliefCorrect(Color color) {
        Belief belief = players.get(color).lastBelief;
        if (belief == null) {
            return 0;
        }
        int correct = 0;
        if (belief.who().equals(caseModel.solution().get("who"))) correct++;
        if (belief.how().equals(caseModel.solution().get("how"))) correct++;
        if (belief.where().equals(caseModel.solution().get("where"))) correct++;
        return correct;
    }

    private List<Map<String, Object>> standings() {
        List<Color> ranked = new ArrayList<>(List.of(Color.values()));
        // Solver first; then the still-standing over the eliminated; then sharper
        // final beliefs; then fewer searches; canonical colour order settles dead heats.
        ranked.sort(Comparator
                .comparingInt((Color c) -> c == solvedBy ? 0 : 1)
                .thenComparingInt(c -> players.get(c).eliminated ? 1 : 0)
                .thenComparingInt(c -> -beliefCorrect(c))
                .thenComparingInt(c -> players.get(c).searchesMade)
                .thenComparingInt(Color::ordinal));

        List<Map<String, Object>> standings = new ArrayList<>();
        for (int i = 0; i < ranked.size(); i++) {
            Color color = ranked.get(i);
            PlayerState state = players.get(color);
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("player", color.json());
            row.put("rank", i + 1);
            row.put("solved", color == solvedBy);
            row.put("eliminated", state.eliminated);
            row.put("belief_dimensions_correct", beliefCorrect(color));
            row.put("suggestions_made", state.suggestionsMade);
            row.put("refutations_given", state.refutationsGiven);
            row.put("searches_made", state.searchesMade);
            standings.add(row);
        }
        return standings;
    }

    // -- emission --------------------------------------------------------

    private void emit(String type, Map<String, Object> payload) {
        Map<String, Object> buffered = new LinkedHashMap<>();
        buffered.put("type", type);
        buffered.put("payload", payload);
        turnEvents.add(buffered);
        sink.emit(type, payload, turn);
    }

    private void emitStart(Map<Color, Detective> detectives) {
        List<Object> playerRows = new ArrayList<>();
        for (Color color : Color.values()) {
            Map<String, Object> meta = new LinkedHashMap<>();
            Map<String, Object> given = config.players().get(color);
            if (given != null) {
                meta.putAll(given);
            }
            Detective detective = detectives.get(color);
            meta.putIfAbsent("agent", detective == null ? "unknown" : detective.name());
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("color", color.json());
            row.putAll(meta);
            playerRows.add(row);
        }

        Map<String, Object> engine = new LinkedHashMap<>();
        engine.put("language", "java");
        engine.put("version", ENGINE_VERSION);

        Map<String, Object> caseBlock = new LinkedHashMap<>();
        caseBlock.put("suspects", CaseModel.WHO.size());
        caseBlock.put("methods", CaseModel.HOW.size());
        caseBlock.put("places", CaseModel.WHERE.size());
        caseBlock.put("archive_documents", archive.documents().size());

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("seed", config.seed());
        payload.put("max_turns", config.maxTurns());
        payload.put("max_searches_per_turn", config.maxSearchesPerTurn());
        payload.put("ruleset", config.ruleset());
        payload.put("stack", config.stack());
        payload.put("engine", engine);
        payload.put("case", caseBlock);
        payload.put("players", playerRows);
        if (config.profile() != null) {
            payload.put("profile", config.profile());
        }
        if (config.promptSet() != null) {
            payload.put("prompt_set", config.promptSet());
        }
        if (config.framework() != null) {
            payload.put("framework", config.framework());
        }
        if (config.archivist() != null) {
            payload.put("archivist", config.archivist());
        }
        emit("game_started", payload);
    }
}
