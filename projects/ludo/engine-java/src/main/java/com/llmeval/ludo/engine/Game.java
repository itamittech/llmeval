package com.llmeval.ludo.engine;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.IntSupplier;

/**
 * The turn loop.
 *
 * <p>Drives a game to completion or to the turn cap, emitting the shared event stream as it
 * goes. Knows nothing about agents beyond the {@link Decider} interface.
 */
public final class Game {

    public static final String ENGINE_VERSION = "0.1.0";

    /** Consecutive sixes that forfeit the turn and revert everything done in it. */
    public static final int SIX_LIMIT = 3;

    /** Chances an agent gets to produce a legal move before forfeiting the turn. */
    public static final int MOVE_ATTEMPTS = 2;

    private final GameConfig config;
    private final EventSink sink;
    private final GameState state = new GameState();
    private final IntSupplier die;

    private int turn;
    private int rotation = -1;

    /** Engine events emitted during the current turn, handed to {@link Decider#reflect}. */
    private List<Map<String, Object>> turnEvents = new ArrayList<>();

    public Game(GameConfig config, EventSink sink) {
        this(config, sink, new Dice(config.seed())::roll);
    }

    /**
     * Package-private seam for tests that need a scripted die.
     *
     * <p>A real difference between the two engines, not a stylistic one. The Python tests write
     * {@code game.dice = ScriptedDice(...)} directly — the language lets you replace an
     * attribute on a live object, so no seam has to be designed in advance. Java has no such
     * escape hatch, so reaching a rule like three-sixes cancellation deterministically requires
     * the production class to have anticipated the need. That asymmetry is worth knowing before
     * the same question arrives in the Spring AI stack.
     */
    Game(GameConfig config, EventSink sink, IntSupplier die) {
        this.config = config;
        this.sink = sink;
        this.die = die;
    }

    public GameState state() {
        return state;
    }

    // -- public ----------------------------------------------------------

    public Outcome play(Map<Color, Decider> deciders) {
        emitStart(deciders);

        // Stop at three finishers: the fourth player's place is already decided.
        while (turn < config.maxTurns() && state.finished().size() < 3) {
            Color color = nextPlayer();
            turn++;
            playTurn(color, deciders.get(color));
        }

        String reason = state.finished().size() >= 3 ? "completed" : "turn_cap";
        List<Map<String, Object>> result = state.standings();

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("reason", reason);
        payload.put("turns_played", turn);
        payload.put("standings", result);
        emit("game_ended", payload);

        return new Outcome(reason, turn, result);
    }

    // -- turn ------------------------------------------------------------

    /**
     * One turn, with the two optional agent hooks around the roll loop.
     *
     * <p>Neither hook is wrapped in a try/catch, unlike {@code choose}. The engine absorbs a
     * failure only when it has a defined in-game meaning — a bad {@code choose} forfeits the
     * turn, which is a real outcome. A model provider erroring mid-negotiation has no such
     * meaning, so it belongs to the harness that made the call. Swallowing it here would produce
     * a transcript that lies about what happened.
     */
    private void playTurn(Color color, Decider decider) {
        turnEvents = new ArrayList<>();

        Map<String, Object> started = new LinkedHashMap<>();
        started.put("player", color.label());
        emit("turn_started", started);

        // One view for the whole turn: agents inspect, they do not mutate.
        StateView view = new StateView(state);

        decider.negotiate(new TurnStart(view, color, turn));

        String reason = rollLoop(color, decider, view);

        Map<String, Object> ended = new LinkedHashMap<>();
        ended.put("player", color.label());
        ended.put("reason", reason);
        emit("turn_ended", ended);

        decider.reflect(new TurnEnd(view, color, turn, reason, List.copyOf(turnEvents)));
    }

    /**
     * Roll, decide, resolve — repeating on a six or a capture.
     *
     * <p>Returns the reason the turn ended, which the caller emits. One exit means
     * {@link Decider#reflect} cannot be skipped down some branch.
     */
    private String rollLoop(Color color, Decider decider, StateView view) {
        Snapshot before = state.snapshot();
        int sixes = 0;
        int rollIndex = 0;

        while (true) {
            int roll = die.getAsInt();

            Map<String, Object> rolled = new LinkedHashMap<>();
            rolled.put("player", color.label());
            rolled.put("value", roll);
            rolled.put("roll_index", rollIndex);
            emit("dice_rolled", rolled);
            rollIndex++;

            sixes = roll == 6 ? sixes + 1 : 0;
            if (sixes == SIX_LIMIT) {
                // Cancel the whole turn, including movement and captures.
                state.restore(before);
                return "three_sixes";
            }

            List<Move> moves = Moves.legalMoves(state, color, roll);
            if (moves.isEmpty()) {
                return "no_legal_move";
            }

            Move move = decide(color, decider, roll, moves, view);
            if (move == null) {
                state.stats(color).turnsForfeited++;
                return "illegal_move";
            }

            boolean captured = apply(color, move);

            if (state.hasFinished(color)) {
                state.finished().add(color);
                Map<String, Object> finished = new LinkedHashMap<>();
                finished.put("player", color.label());
                finished.put("rank", state.finished().size());
                emit("player_finished", finished);
                return "moved";
            }

            if (roll == 6 || captured) {
                Map<String, Object> extra = new LinkedHashMap<>();
                extra.put("player", color.label());
                extra.put("reason", roll == 6 ? "six" : "capture");
                emit("extra_roll_granted", extra);
                continue;
            }

            return "moved";
        }
    }

    private boolean apply(Color color, Move move) {
        List<Capture> captures = Moves.applyMove(state, color, move);

        Map<String, Object> made = new LinkedHashMap<>();
        made.put("player", color.label());
        made.put("token", move.token());
        made.put("from", move.frm());
        made.put("to", move.to());
        made.put("from_square", Board.toSquare(color, move.frm()));
        made.put("to_square", Board.toSquare(color, move.to()));
        emit("move_made", made);

        for (Capture capture : captures) {
            Map<String, Object> taken = new LinkedHashMap<>();
            taken.put("captor", color.label());
            taken.put("captor_token", move.token());
            taken.put("victim", capture.victim().label());
            taken.put("victim_token", capture.victimToken());
            taken.put("square", capture.square());
            emit("token_captured", taken);
        }

        if (move.to() == Board.HOME) {
            Map<String, Object> home = new LinkedHashMap<>();
            home.put("player", color.label());
            home.put("token", move.token());
            emit("token_home", home);
        }

        return !captures.isEmpty();
    }

    /** Ask for a move, rejecting illegal ones rather than correcting them. */
    private Move decide(Color color, Decider decider, int die, List<Move> moves, StateView view) {
        Set<Move> allowed = new HashSet<>(moves);

        for (int attempt = 1; attempt <= MOVE_ATTEMPTS; attempt++) {
            TurnContext ctx = new TurnContext(view, color, die, List.copyOf(moves), turn, attempt);

            Move move;
            try {
                move = decider.choose(ctx);
            } catch (RuntimeException exc) {
                // A broken agent forfeits; it does not crash the game.
                Map<String, Object> rejected = new LinkedHashMap<>();
                rejected.put("player", color.label());
                rejected.put("token", null);
                rejected.put("requested_to", null);
                rejected.put("reason", "decider error: " + exc.getClass().getSimpleName());
                rejected.put("attempt", attempt);
                emit("illegal_move_rejected", rejected);
                continue;
            }

            if (move != null && allowed.contains(move)) {
                return move;
            }

            Map<String, Object> rejected = new LinkedHashMap<>();
            rejected.put("player", color.label());
            rejected.put("token", move == null ? null : move.token());
            rejected.put("requested_to", move == null ? null : move.to());
            rejected.put("reason", "not a legal move for this roll");
            rejected.put("attempt", attempt);
            emit("illegal_move_rejected", rejected);
        }

        return null;
    }

    private Color nextPlayer() {
        while (true) {
            rotation = (rotation + 1) % Color.values().length;
            Color color = Color.values()[rotation];
            if (!state.hasFinished(color)) {
                return color;
            }
        }
    }

    // -- emission --------------------------------------------------------

    private void emit(String type, Map<String, Object> payload) {
        Map<String, Object> event = sink.emit(type, payload, turn);
        // Also buffered for the turn, so `reflect` gets what happened without the harness having
        // to reconstruct it from the sink.
        turnEvents.add(event);
    }

    private void emitStart(Map<Color, Decider> deciders) {
        List<Map<String, Object>> players = new ArrayList<>();
        for (Color color : Color.values()) {
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("color", color.label());
            Map<String, Object> configured = config.players().get(color);
            if (configured != null) {
                meta.putAll(configured);
            }
            if (!meta.containsKey("agent")) {
                Decider decider = deciders.get(color);
                meta.put("agent", decider == null ? "unknown" : decider.name());
            }
            players.add(meta);
        }

        Map<String, Object> engine = new LinkedHashMap<>();
        engine.put("language", "java");
        engine.put("version", ENGINE_VERSION);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("seed", config.seed());
        payload.put("max_turns", config.maxTurns());
        payload.put("ruleset", config.ruleset());
        payload.put("stack", config.stack());
        payload.put("engine", engine);
        payload.put("players", players);
        emit("game_started", payload);
    }
}
