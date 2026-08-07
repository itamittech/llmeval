package com.llmeval.relay.springai;

import com.llmeval.relay.engine.Attempt;
import com.llmeval.relay.engine.EventSink;
import com.llmeval.relay.engine.Game;
import com.llmeval.relay.engine.GameConfig;
import com.llmeval.relay.engine.LaneSnapshot;
import com.llmeval.relay.engine.NoteRecord;
import com.llmeval.relay.engine.Outcome;
import com.llmeval.relay.engine.PublicStage;
import com.llmeval.relay.engine.Reflector;
import com.llmeval.relay.engine.Runner;
import com.llmeval.relay.engine.RunnerView;
import com.llmeval.relay.engine.TurnContext;
import com.llmeval.relay.engine.TurnEnd;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.prompt.Prompt;

/**
 * The RELAY harness on Spring AI — four runner clients and one shared anchor.
 *
 * <p>Deliberately the same shape as the two Python harnesses, because the point is what differs
 * below it. Here the differences are small and every one of them is a row in the matrix:
 *
 * <ul>
 *   <li>the conversation is {@code ChatMemory} behind a {@code MessageChatMemoryAdvisor}, one
 *       conversation id per lane;</li>
 *   <li>the notebook is {@link Notebook}, a plain class, because the framework still has nowhere
 *       to put one — third game, third Manual;</li>
 *   <li>metering reads usage off the {@code ChatResponse} synchronously, with no hook ordering to
 *       get wrong;</li>
 *   <li>the anchor is a second {@code ChatClient} with no memory advisor at all.</li>
 * </ul>
 *
 * <p>And one absence worth more than any of them: <strong>no tool</strong>. ALIBI's Spring AI
 * stack metered 20 calls where the Python stacks metered 22, because internal tool execution
 * hides invocations from the caller. RELAY has no tool, so that finding has nowhere to appear and
 * all three stacks agree. The frameworks did not converge — the protocol stopped asking them to
 * differ.
 */
public final class Harness {

    private static final int NOTES_LIMIT = 8;
    private static final int MAX_NOTES_PER_REFLECT = 2;
    private static final int WINDOW_SIZE = 24;

    // `[^\S\n]*` rather than `\s*`: the latter crosses newlines, so an empty ANSWER: line
    // swallows the NOTE: beneath it and submits a runner's table talk as its answer.
    private static final String SPACE = "[^\\S\\n]*";
    private static final Pattern DECISION = Pattern.compile(
            "(?im)^" + SPACE + "DECISION:" + SPACE + "(answer|escalate|pass)" + SPACE + "$");
    private static final Pattern ANSWER =
            Pattern.compile("(?im)^" + SPACE + "ANSWER:" + SPACE + "(.*)$");
    private static final Pattern NOTE =
            Pattern.compile("(?im)^" + SPACE + "NOTE:" + SPACE + "(.*)$");

    /** What a runner's reply parses into: a decision, maybe an answer, maybe a note. */
    public record Decision(String decision, String answer, String note) {}

    public static Decision parse(String text) {
        Matcher decision = DECISION.matcher(text);
        if (!decision.find()) {
            throw new IllegalArgumentException("no DECISION line in reply");
        }
        Matcher answer = ANSWER.matcher(text);
        String answerText = answer.find() ? answer.group(1).strip() : "";
        Matcher note = NOTE.matcher(text);
        String noteText = note.find() ? note.group(1).strip() : "";
        return new Decision(decision.group(1).toLowerCase(),
                answerText.isEmpty() ? null : answerText,
                noteText.isEmpty() ? null : noteText);
    }

    private final ModelsConfig.Profile profile;
    private final Prompts prompts;
    private final Prompts.Template anchorPrompt;
    private final PolicyChatModel anchorModel;
    private final EventSink sink;
    private final Notebook notebook = new Notebook();
    private final Map<String, ChatClient> clients = new LinkedHashMap<>();
    private final Map<String, Map<String, String>> laneMeta = new LinkedHashMap<>();
    private final Map<String, String> anchorMeta = new LinkedHashMap<>();
    private final ChatClient anchorClient;
    private final Game game;

    private final int maxTokens;
    private int spent;
    private int calls;
    private int turn;
    private String purpose = "attempt";
    private String color = "red";
    private String actor = "runner";

    public Harness(ModelsConfig.Profile profile, Prompts prompts,
                   Prompts.Template anchorPrompt, Map<String, PolicyChatModel> models,
                   PolicyChatModel anchorModel, EventSink sink, int seed, int maxTurns,
                   int gameIndex) {
        this.profile = profile;
        this.prompts = prompts;
        this.anchorPrompt = anchorPrompt;
        this.anchorModel = anchorModel;
        this.sink = sink;
        this.maxTokens = profile.budgets().maxTokensPerGame();

        Map<String, ModelsConfig.Lane> lanes =
                ModelsConfig.laneAssignment(profile, Game.COLORS, gameIndex);
        Map<String, Map<String, Object>> players = new LinkedHashMap<>();

        for (String c : Game.COLORS) {
            ModelsConfig.Lane lane = lanes.get(c);
            laneMeta.put(c, ordered("model", models.get(c).label(), "access", lane.access()));
            // Built key by key. Map.of is not merely unordered — its iteration order is
            // randomised per JVM run, so a payload assembled from one is byte-reproducible
            // within a process and different the next time. The fixture test caught it; the
            // engine hit the same trap in track_generated, where only a file diff did.
            Map<String, Object> player = new LinkedHashMap<>();
            player.put("seat", lane.lane());
            player.put("model", models.get(c).label());
            player.put("access", lane.access());
            players.put(c, player);

            Map<String, Object> systemValues = new TreeMap<>();
            systemValues.put("color", c);
            systemValues.put("escalation_quota", profile.budgets().escalationQuota());
            systemValues.put("max_turns", maxTurns);
            systemValues.put("max_note_chars", profile.budgets().maxNoteChars());

            ChatMemory memory = MessageWindowChatMemory.builder()
                    .maxMessages(WINDOW_SIZE)
                    .build();
            clients.put(c, ChatClient.builder(models.get(c))
                    .defaultSystem(prompts.systemPrompt(systemValues))
                    .defaultAdvisors(MessageChatMemoryAdvisor.builder(memory).build())
                    .build());
        }

        anchorMeta.put("model", anchorModel.label());
        anchorMeta.put("access", profile.anchor().access());
        // No memory advisor, deliberately: the anchor is a model call, not an agent with a
        // situation, and two escalations in a row must not be able to see each other.
        this.anchorClient = ChatClient.builder(anchorModel).build();

        GameConfig config = new GameConfig(seed, maxTurns);
        config.escalationQuota = profile.budgets().escalationQuota();
        config.maxNoteChars = profile.budgets().maxNoteChars();
        config.stack = "springai";
        config.players = new LinkedHashMap<>();
        players.forEach((c, meta) -> config.players.put(c, meta));
        config.anchor = this::callAnchor;
        config.profile = profile.name();
        config.promptSet = ordered("version", prompts.version(), "hash", prompts.digest());
        config.framework = ordered("name", "springai", "version", frameworkVersion());
        config.anchorMeta = new LinkedHashMap<>(anchorMeta);
        this.game = new Game(config, sink);
    }

    /** Two-entry insertion-ordered map. Never {@code Map.of} on a serialised payload. */
    private static <V> Map<String, V> ordered(String k1, V v1, String k2, V v2) {
        Map<String, V> map = new LinkedHashMap<>();
        map.put(k1, v1);
        map.put(k2, v2);
        return map;
    }

    private static String frameworkVersion() {
        Package pkg = ChatClient.class.getPackage();
        String version = pkg == null ? null : pkg.getImplementationVersion();
        return version == null ? "1.1.2" : version;
    }

    public Game game() {
        return game;
    }

    public int calls() {
        return calls;
    }

    public int spent() {
        return spent;
    }

    public Notebook notebook() {
        return notebook;
    }

    public Outcome play() {
        Map<String, Runner> runners = new LinkedHashMap<>();
        for (String c : Game.COLORS) {
            runners.put(c, new LaneRunner(c));
        }
        return game.play(runners);
    }

    // -- the anchor ------------------------------------------------------

    /** What the engine's desk invokes, once the quota has been charged. */
    String callAnchor(PublicStage stage) {
        actor = "anchor";
        purpose = "escalate";
        try {
            ChatResponse response = anchorClient.prompt(
                    new Prompt(anchorPrompt.render(Map.of("stage", stage.prompt()))))
                    .call().chatResponse();
            meter(response);
            String text = response.getResult().getOutput().getText();
            String trimmed = text == null ? "" : text.strip();
            return trimmed.isEmpty() ? "" : trimmed.lines().findFirst().orElse("").strip();
        } finally {
            actor = "runner";
        }
    }

    // -- asking ----------------------------------------------------------

    private String ask(String lane, String phase, int gameTurn, Map<String, Object> values) {
        this.turn = gameTurn;
        this.color = lane;
        this.purpose = phase;
        this.actor = "runner";
        String prompt = prompts.turn(phase).render(values);
        ChatResponse response = clients.get(lane)
                .prompt(prompt)
                .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, lane))
                .call().chatResponse();
        meter(response);
        String text = response.getResult().getOutput().getText();
        return text == null ? "" : text;
    }

    /**
     * Usage rides the response object, read synchronously after the call returns. No hook
     * ordering to get wrong, and — with no tool in this game — nothing aggregated either.
     */
    private void meter(ChatResponse response) {
        var usage = response.getMetadata().getUsage();
        Map<String, Object> tokens = new LinkedHashMap<>();
        tokens.put("input", usage.getPromptTokens() == null ? 0 : usage.getPromptTokens());
        tokens.put("output", usage.getCompletionTokens() == null ? 0 : usage.getCompletionTokens());
        spent += (Integer) tokens.get("input") + (Integer) tokens.get("output");
        calls++;

        Map<String, String> seat = actor.equals("anchor") ? anchorMeta : laneMeta.get(color);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("player", color);
        payload.put("actor", actor);
        payload.put("model", seat.get("model"));
        payload.put("access", seat.get("access"));
        payload.put("purpose", purpose);
        payload.put("tokens", tokens);
        payload.put("latency_ms", 0);
        sink.emit("llm_call", payload, turn);
    }

    private boolean exhausted() {
        return spent >= maxTokens;
    }

    private String gateNote(String lane, int gameTurn, String note) {
        String trimmed = note.length() > profile.budgets().maxNoteChars()
                ? note.substring(0, profile.budgets().maxNoteChars()) : note;
        Guardrails.Violation violation = Guardrails.check(trimmed);
        if (violation != null) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("player", lane);
            payload.put("rule", violation.rule());
            payload.put("action", "blocked");
            payload.put("source", "harness");
            payload.put("detail", violation.reason());
            sink.emit("guardrail_triggered", payload, gameTurn);
            return null;
        }
        return trimmed;
    }

    // -- rendering -------------------------------------------------------

    static String renderLanes(RunnerView view) {
        List<String> lines = new ArrayList<>();
        for (LaneSnapshot lane : view.lanes()) {
            String mark = lane.finished() ? " (finished)" : "";
            String you = lane.color().equals(view.color()) ? " <- you" : "";
            lines.add("- " + lane.color() + ": stage " + (lane.position() + 1) + " of "
                    + view.trackLength() + ", " + lane.ticks() + " ticks, "
                    + lane.escalations() + " escalations" + mark + you);
        }
        return String.join("\n", lines);
    }

    static String renderNotes(RunnerView view) {
        List<NoteRecord> notes = view.notes();
        if (notes.isEmpty()) {
            return "(nobody has said anything)";
        }
        List<String> lines = new ArrayList<>();
        for (NoteRecord n : notes.subList(Math.max(0, notes.size() - NOTES_LIMIT), notes.size())) {
            lines.add("- turn " + n.turn() + ", " + n.player() + ": \"" + n.text() + "\"");
        }
        return String.join("\n", lines);
    }

    static String renderHistory(RunnerView view) {
        var records = view.ownHistory();
        if (records.isEmpty()) {
            return "(this is your first stage)";
        }
        List<String> lines = new ArrayList<>();
        for (var r : records.subList(Math.max(0, records.size() - 12), records.size())) {
            String how = r.escalated() ? "the anchor answered" : "you answered";
            String verdict = r.correct() ? "cleared" : "missed";
            lines.add("- turn " + r.turn() + ", a " + r.family() + " stage: " + how + ", "
                    + verdict);
        }
        Map<String, int[]> byFamily = new TreeMap<>();
        for (var r : records) {
            if (r.escalated()) {
                continue;
            }
            int[] tally = byFamily.computeIfAbsent(r.family(), k -> new int[2]);
            tally[0] += r.correct() ? 1 : 0;
            tally[1] += 1;
        }
        if (!byFamily.isEmpty()) {
            List<String> parts = new ArrayList<>();
            byFamily.forEach((family, tally) ->
                    parts.add(family + " " + tally[0] + "/" + tally[1]));
            lines.add("- on your own, unaided: " + String.join(", ", parts));
        }
        return String.join("\n", lines);
    }

    static String renderTurnSummary(List<Map<String, Object>> events) {
        List<String> lines = new ArrayList<>();
        for (Map<String, Object> event : events) {
            String kind = (String) event.get("type");
            @SuppressWarnings("unchecked")
            Map<String, Object> p = (Map<String, Object>) event.get("payload");
            switch (kind) {
                case "stage_attempted" -> {
                    String who = Boolean.TRUE.equals(p.get("escalated")) ? "the anchor" : "you";
                    String verdict = Boolean.TRUE.equals(p.get("correct"))
                            ? "cleared it" : "got it wrong";
                    lines.add(who + " answered " + p.get("stage") + " and " + verdict + " ("
                            + p.get("ticks_charged") + " ticks, " + p.get("quota_left")
                            + " quota left)");
                }
                case "invalid_action" ->
                        lines.add("invalid " + p.get("phase") + ": " + p.get("reason"));
                case "runner_finished" -> lines.add("you finished the track");
                default -> { }
            }
        }
        if (lines.isEmpty()) {
            return "- (a quiet turn)";
        }
        List<String> bulleted = new ArrayList<>();
        lines.forEach(line -> bulleted.add("- " + line));
        return String.join("\n", bulleted);
    }

    // -- the engine-facing adapter ---------------------------------------

    private final class LaneRunner implements Runner, Reflector {

        private final String lane;

        LaneRunner(String lane) {
            this.lane = lane;
        }

        @Override
        public String name() {
            return "llm-runner";
        }

        @Override
        public Attempt attempt(TurnContext ctx) {
            if (exhausted()) {
                return Attempt.pass();
            }
            RunnerView view = ctx.view();
            Map<String, Object> values = new LinkedHashMap<>();
            values.put("turn", ctx.turn());
            values.put("color", lane);
            values.put("stage", view.stage().prompt());
            values.put("lanes", renderLanes(view));
            values.put("quota_left", view.quotaLeft());
            values.put("notes", renderNotes(view));
            values.put("history", renderHistory(view));
            values.put("memory", notebook.render(lane));

            Decision decision = parse(ask(lane, "attempt", ctx.turn(), values));
            String note = decision.note() == null
                    ? null : gateNote(lane, ctx.turn(), decision.note());

            return switch (decision.decision()) {
                case "escalate" -> new Attempt(ctx.desk().ask(), note);
                case "pass" -> new Attempt(null, note);
                default -> new Attempt(decision.answer(), note);
            };
        }

        @Override
        public void reflect(TurnEnd end) {
            if (exhausted()) {
                return;
            }
            Map<String, Object> values = new LinkedHashMap<>();
            values.put("turn", end.turn());
            values.put("turn_summary", renderTurnSummary(end.events()));
            values.put("memory", notebook.render(lane));

            String reply = ask(lane, "reflect", end.turn(), values).strip();
            if (reply.isEmpty()) {
                return;
            }
            int written = 0;
            for (String raw : reply.lines().toList()) {
                if (written >= MAX_NOTES_PER_REFLECT) {
                    break;
                }
                String line = raw.strip().replaceFirst("^-", "").strip();
                if (line.isEmpty()) {
                    continue;
                }
                Notebook.Note note = notebook.write(lane, line, end.turn(), "self", null);
                written++;
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("player", lane);
                payload.put("kind", note.kind());
                payload.put("about", note.about());
                payload.put("text", note.text());
                sink.emit("memory_write", payload, end.turn());
            }
        }
    }
}
