package com.llmeval.relay.engine;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The turn loop — RELAY's referee. The Java half of ADR-0002.
 *
 * <p>Every ordering decision here is on the conformance path: the order ticks are charged, the
 * order lanes rotate, the order standings sort. A port that is merely <em>correct</em> is not
 * enough — it has to be correct the same way.
 */
public final class Game {

    public static final String ENGINE_VERSION = "0.1.0";

    public static final List<String> COLORS = List.of("red", "green", "yellow", "blue");

    public static final int PHASE_ATTEMPTS = 2;

    public static final int TICK_ANSWER = 2;
    public static final int TICK_ESCALATE = 5;
    public static final int TICK_WRONG = 4;
    public static final int TICK_PASS = 3;

    public static final int ESCALATION_QUOTA = 8;
    public static final int MAX_STALLS = 3;
    public static final int MAX_NOTE_CHARS = 240;

    private final GameConfig config;
    private final EventSink sink;
    private final List<Stage> track;
    private final Map<String, Lane> lanes = new LinkedHashMap<>();
    private final List<NoteRecord> notes = new ArrayList<>();
    private List<Map<String, Object>> turnEvents = new ArrayList<>();

    private int quota;
    private int turn;
    private int rotation = -1;
    private String finisher;

    public Game(GameConfig config, EventSink sink) {
        this.config = config;
        this.sink = sink;
        this.track = Track.generate(new Rng(config.seed), config.stages);
        this.quota = config.escalationQuota;
        for (String color : COLORS) {
            lanes.put(color, new Lane());
        }
    }

    public List<Stage> track() {
        return track;
    }

    public int quota() {
        return quota;
    }

    // -- public ----------------------------------------------------------

    public Outcome play(Map<String, Runner> runners) {
        emitStart(runners);

        List<Map<String, Object>> stages = new ArrayList<>();
        for (Stage stage : track) {
            // Built key by key, not via Map.of: that factory makes an UNORDERED map, and
            // copying one into a LinkedHashMap preserves whatever order it happened to have.
            // The digest sorts keys so conformance would still pass — but the raw transcript
            // would stop being byte-comparable with Python's, which is a guarantee worth more
            // than the two lines it costs.
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("id", stage.id());
            entry.put("family", stage.family());
            entry.put("prompt", stage.prompt());
            stages.add(entry);
        }
        emit("track_generated", ordered("stages", stages));

        while (turn < config.maxTurns && finisher == null && !allStalled()) {
            String color = nextLane();
            if (color == null) {
                break;
            }
            turn++;
            playTurn(color, runners.get(color));
        }

        String reason = finisher != null ? "finished" : allStalled() ? "all_stalled" : "turn_cap";

        List<Map<String, Object>> key = new ArrayList<>();
        for (Stage stage : track) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("id", stage.id());
            entry.put("tier", stage.tier());
            entry.put("answer", stage.answer());
            key.add(entry);
        }

        List<Map<String, Object>> standings = standings();
        Map<String, Object> ended = new LinkedHashMap<>();
        ended.put("reason", reason);
        ended.put("turns_played", turn);
        ended.put("track_key", key);
        ended.put("standings", standings);
        emit("game_ended", ended);
        return new Outcome(reason, turn, standings);
    }

    // -- turn ------------------------------------------------------------

    private void playTurn(String color, Runner runner) {
        turnEvents = new ArrayList<>();
        Lane lane = lanes.get(color);
        Stage stage = track.get(lane.position);

        Map<String, Object> started = new LinkedHashMap<>();
        started.put("player", color);
        started.put("stage", stage.id());
        emit("turn_started", started);

        EscalationDesk desk = desk(color, stage);
        Attempt attempt = ask(color, runner, stage, desk);
        String note = vetNote(color, attempt.note());

        boolean escalated = desk.used();
        int charged = escalated ? TICK_ESCALATE
                : attempt.answer() == null ? TICK_PASS : TICK_ANSWER;
        boolean correct = attempt.answer() != null
                && Track.normalise(attempt.answer()).equals(Track.normalise(stage.answer()));

        String reason;
        if (attempt.answer() == null) {
            lane.passes++;
            lane.stalls++;
            reason = "passed";
        } else if (correct) {
            lane.correct++;
            lane.position++;
            lane.stalls = 0;
            reason = "cleared";
        } else {
            lane.wrong++;
            lane.stalls++;
            charged += TICK_WRONG;
            reason = "missed";
        }

        if (escalated) {
            lane.escalations++;
        }
        lane.ticks += charged;
        lane.history.add(new AttemptRecord(turn, stage.id(), stage.family(), escalated, correct));
        if (note != null) {
            notes.add(new NoteRecord(turn, color, note));
        }

        Map<String, Object> attempted = new LinkedHashMap<>();
        attempted.put("player", color);
        attempted.put("stage", stage.id());
        attempted.put("answer", attempt.answer());
        attempted.put("escalated", escalated);
        attempted.put("correct", correct);
        attempted.put("ticks_charged", charged);
        attempted.put("ticks_total", lane.ticks);
        attempted.put("quota_left", quota);
        attempted.put("note", note);
        emit("stage_attempted", attempted);

        if (lane.position >= track.size()) {
            lane.finished = true;
            finisher = color;
            reason = "finished";
            Map<String, Object> done = new LinkedHashMap<>();
            done.put("player", color);
            done.put("ticks", lane.ticks);
            emit("runner_finished", done);
        }

        Map<String, Object> ended = new LinkedHashMap<>();
        ended.put("player", color);
        ended.put("reason", reason);
        emit("turn_ended", ended);

        if (runner instanceof Reflector reflector) {
            reflector.reflect(new TurnEnd(view(color, stage), color, turn, reason, turnEvents));
        }
    }

    /** The desk is built once per turn, so a runner that asks twice pays twice. */
    private Attempt ask(String color, Runner runner, Stage stage, EscalationDesk desk) {
        for (int attemptNo = 1; attemptNo <= PHASE_ATTEMPTS; attemptNo++) {
            TurnContext ctx = new TurnContext(view(color, stage), color, turn, desk, attemptNo);
            Attempt attempt;
            try {
                attempt = runner.attempt(ctx);
            } catch (RuntimeException e) {  // a broken agent passes; it does not crash the race
                invalid(color, "attempt", "runner error: " + e.getClass().getSimpleName(),
                        attemptNo);
                continue;
            }
            if (attempt == null) {
                invalid(color, "attempt", "no attempt returned", attemptNo);
                continue;
            }
            return attempt;
        }
        return Attempt.pass();
    }

    private EscalationDesk desk(String color, Stage stage) {
        return new EscalationDesk(stage, () -> quota, () -> quota--, config.anchor,
                () -> invalid(color, "escalate", "shared quota exhausted", 1));
    }

    private String vetNote(String color, String note) {
        if (note == null) {
            return null;
        }
        if (note.length() > config.maxNoteChars) {
            invalid(color, "note", "note too long", 1);
            return null;
        }
        return note;
    }

    // -- plumbing --------------------------------------------------------

    private RunnerView view(String color, Stage stage) {
        Lane lane = lanes.get(color);
        List<LaneSnapshot> snapshots = new ArrayList<>();
        for (String c : COLORS) {
            Lane other = lanes.get(c);
            snapshots.add(new LaneSnapshot(c, other.position, other.ticks, other.escalations,
                    other.finished));
        }
        return new RunnerView(color, stage.publicView(), lane.position, lane.ticks, track.size(),
                quota, snapshots, notes, lane.history);
    }

    private String nextLane() {
        for (int i = 0; i < COLORS.size(); i++) {
            rotation = (rotation + 1) % COLORS.size();
            String color = COLORS.get(rotation);
            if (!lanes.get(color).finished) {
                return color;
            }
        }
        return null;
    }

    private boolean stalled(String color) {
        Lane lane = lanes.get(color);
        return lane.finished || lane.stalls > config.maxStalls;
    }

    /** Only a spent quota can strand the table. */
    private boolean allStalled() {
        if (quota > 0) {
            return false;
        }
        for (String color : COLORS) {
            if (!stalled(color)) {
                return false;
            }
        }
        return true;
    }

    private void invalid(String color, String phase, String reason, int attempt) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("player", color);
        payload.put("phase", phase);
        payload.put("reason", reason);
        payload.put("attempt", attempt);
        emit("invalid_action", payload);
    }

    private List<Map<String, Object>> standings() {
        List<String> ranked = new ArrayList<>(COLORS);
        ranked.sort(Comparator
                .comparingInt((String c) -> -lanes.get(c).position)
                .thenComparingInt(c -> lanes.get(c).ticks)
                .thenComparingInt(COLORS::indexOf));

        List<Map<String, Object>> out = new ArrayList<>();
        for (int i = 0; i < ranked.size(); i++) {
            Lane lane = lanes.get(ranked.get(i));
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("player", ranked.get(i));
            row.put("rank", i + 1);
            row.put("stages_cleared", lane.position);
            row.put("ticks", lane.ticks);
            row.put("finished", lane.finished);
            row.put("escalations", lane.escalations);
            row.put("correct", lane.correct);
            row.put("wrong", lane.wrong);
            row.put("passes", lane.passes);
            out.add(row);
        }
        return out;
    }

    // -- emission --------------------------------------------------------

    private static Map<String, Object> ordered(String key, Object value) {
        Map<String, Object> map = new LinkedHashMap<>();
        map.put(key, value);
        return map;
    }

    private void emit(String type, Map<String, Object> payload) {
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("type", type);
        record.put("payload", payload);
        turnEvents.add(record);
        sink.emit(type, payload, turn);
    }

    private void emitStart(Map<String, Runner> runners) {
        List<Map<String, Object>> players = new ArrayList<>();
        for (String color : COLORS) {
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("color", color);
            Map<String, Object> configured = config.players.get(color);
            if (configured != null) {
                meta.putAll(configured);
            }
            meta.putIfAbsent("agent",
                    runners.get(color) == null ? "unknown" : runners.get(color).name());
            players.add(meta);
        }

        Map<String, Object> tiers = new LinkedHashMap<>();
        tiers.put("1", 0);
        tiers.put("2", 0);
        tiers.put("3", 0);
        for (Stage stage : track) {
            String k = Integer.toString(stage.tier());
            tiers.put(k, (Integer) tiers.get(k) + 1);
        }

        Map<String, Object> engine = new LinkedHashMap<>();
        engine.put("language", "java");
        engine.put("version", ENGINE_VERSION);

        Map<String, Object> trackShape = new LinkedHashMap<>();
        trackShape.put("stages", track.size());
        trackShape.put("tiers", tiers);

        Map<String, Object> ticks = new LinkedHashMap<>();
        ticks.put("answer", TICK_ANSWER);
        ticks.put("escalate", TICK_ESCALATE);
        ticks.put("wrong", TICK_WRONG);
        ticks.put("pass", TICK_PASS);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("seed", config.seed);
        payload.put("max_turns", config.maxTurns);
        payload.put("escalation_quota", config.escalationQuota);
        payload.put("max_stalls", config.maxStalls);
        payload.put("max_note_chars", config.maxNoteChars);
        payload.put("ruleset", config.ruleset);
        payload.put("stack", config.stack);
        payload.put("engine", engine);
        payload.put("track", trackShape);
        payload.put("ticks", ticks);
        payload.put("players", players);

        putIfPresent(payload, "profile", config.profile);
        putIfPresent(payload, "prompt_set", config.promptSet);
        putIfPresent(payload, "framework", config.framework);
        putIfPresent(payload, "host", config.host);
        putIfPresent(payload, "anchor", config.anchorMeta);
        emit("game_started", payload);
    }

    private static void putIfPresent(Map<String, Object> payload, String key, Object value) {
        if (value != null) {
            payload.put(key, value);
        }
    }

    private static final class Lane {
        int position;
        int ticks;
        int stalls;
        int escalations;
        int correct;
        int wrong;
        int passes;
        boolean finished;
        final List<AttemptRecord> history = new ArrayList<>();
    }
}
