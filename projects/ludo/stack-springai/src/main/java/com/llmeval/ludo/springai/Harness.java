package com.llmeval.ludo.springai;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.yaml.snakeyaml.Yaml;

import com.llmeval.ludo.engine.Color;
import com.llmeval.ludo.engine.Decider;
import com.llmeval.ludo.engine.EventSink;
import com.llmeval.ludo.engine.Game;
import com.llmeval.ludo.engine.GameConfig;
import com.llmeval.ludo.engine.Json;
import com.llmeval.ludo.engine.Move;
import com.llmeval.ludo.engine.Outcome;
import com.llmeval.ludo.engine.StateView;
import com.llmeval.ludo.engine.TurnContext;
import com.llmeval.ludo.engine.TurnEnd;
import com.llmeval.ludo.engine.TurnStart;

/**
 * The turn loop: the engine's agent hooks, answered with Spring AI.
 *
 * <p>The engine drives and calls three hooks per turn; this class answers them
 * (harness-contract §2). Model access goes through {@link ChatClient} over a
 * {@link ChatModel} — the scripted fake in tests, provider bindings when live —
 * and every call's usage is read from the framework's own response metadata
 * into an {@code llm_call} event.
 *
 * <p><strong>Negotiation is the honest divergence.</strong> Strands has a swarm
 * orchestrator; Spring AI has none, so the floor-passing table of ADR-0009 is
 * orchestrated by this class — a legitimate <em>Manual</em> under ADR-0008,
 * recorded loudly in the capability matrix rather than smoothed over. The
 * observable protocol is identical: the active agent opens, a floor-holder
 * sends one directed message (optionally with a public table note) or ends the
 * conversation, capped by {@code max_floor_passes}. In this first cut the
 * floor-pass action is a parsed JSON reply; the framework-tool form arrives
 * with live play.
 */
public final class Harness {

    /** Raised by choose once the ceiling is spent; the engine records a forfeit. */
    public static final class BudgetSpent extends RuntimeException {
        BudgetSpent(String message) {
            super(message);
        }
    }

    private static final Pattern JSON_OBJECT = Pattern.compile("\\{.*}", Pattern.DOTALL);
    private static final Map<String, Color> BY_LABEL = new LinkedHashMap<>();
    static {
        for (Color c : Color.values()) BY_LABEL.put(c.label(), c);
    }

    private final Prompts prompts;
    private final ModelsConfig.Budgets budgets;
    private final Map<Color, ModelsConfig.Seat> seatByColor;
    private final Map<Color, ChatClient> clients = new EnumMap<>(Color.class);
    private final Map<Color, Memory> memories = new EnumMap<>(Color.class);
    private final Map<Color, List<String>> inbox = new EnumMap<>(Color.class);
    private final Map<Color, String> lastReply = new EnumMap<>(Color.class);
    private final Map<Color, Decider> deciders = new EnumMap<>(Color.class);
    private final EventSink sink;
    private final RecentWindow window;
    private final Game game;

    private long spent;
    private int turn;

    public Harness(ModelsConfig.Profile profile, Prompts prompts,
                   Map<Color, ChatModel> models, EventSink destination,
                   int seed, int gameIndex, Integer maxTurns) {
        this.prompts = prompts;
        this.budgets = profile.budgets();
        this.seatByColor = ModelsConfig.seating(profile, gameIndex);

        // One tee: engine and harness events share one sequence (ADR-0003).
        this.window = new RecentWindow(30);
        this.sink = new EventSink.TeeSink(destination, window);

        Map<Color, Map<String, Object>> players = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            clients.put(color, ChatClient.create(models.get(color)));
            memories.put(color, new Memory());
            inbox.put(color, new ArrayList<>());
            deciders.put(color, new SpringDecider(color));

            ModelsConfig.Seat seat = seatByColor.get(color);
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("agent", "springai:scripted");
            meta.put("seat", seat.seat());
            meta.put("model", "scripted");   // names what actually answers, never the seat's live id
            meta.put("access", seat.access());
            players.put(color, meta);
        }

        int cap = maxTurns != null ? maxTurns : budgets.maxTurns();
        this.game = new Game(new GameConfig(seed, cap, "baseline", "springai", players), sink);
    }

    public Map<Color, Decider> deciders() {
        return deciders;
    }

    public Outcome play() {
        return game.play(deciders);
    }

    private boolean exhausted() {
        return spent >= budgets.maxTokensPerGame();
    }

    // -- the engine-facing plug -------------------------------------------

    /** The implements line the Python stacks never needed — capability matrix, row one. */
    private final class SpringDecider implements Decider {
        private final Color color;

        SpringDecider(Color color) {
            this.color = color;
        }

        @Override
        public String name() {
            return "springai:scripted";
        }

        @Override
        public void negotiate(TurnStart start) {
            Harness.this.negotiate(start);
        }

        @Override
        public Move choose(TurnContext ctx) {
            return Harness.this.choose(ctx);
        }

        @Override
        public void reflect(TurnEnd end) {
            Harness.this.reflect(end);
        }
    }

    // -- negotiate: the floor-passing table (ADR-0009) --------------------

    private void negotiate(TurnStart start) {
        turn = start.turn();
        if (exhausted()) return;
        try {
            runTable(start);
        } catch (RuntimeException e) {
            // A provider failure mid-conversation has no in-game meaning
            // (harness-contract §2.1): the phase is abandoned, the turn goes on.
        }
    }

    private void runTable(TurnStart start) {
        Map<Color, String> briefings = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            briefings.put(color, prompts.turn("briefing").render(Map.of(
                    "color", color.label(),
                    "inbox", drainInbox(color),
                    "memory", memories.get(color).render(40))));
        }
        String task = prompts.turn("negotiate").render(Map.of(
                "turn", start.turn(),
                "active", start.color().label(),
                "board", renderBoard(start.state()),
                "standings", renderStandings(start.state())));

        Color holder = start.color();
        String incoming = null;
        int passes = 0;
        while (true) {
            String context = briefings.get(holder) + "\n\n" + task
                    + (incoming == null ? "" : "\n\nMessage addressed to you this conversation: " + incoming);
            String reply = ask(holder, "negotiate", context);

            Map<String, Object> action = tryJson(reply);
            Color to = action == null ? null : BY_LABEL.get(String.valueOf(action.get("to")));
            String message = action == null ? null : asText(action.get("message"));
            if (to == null || to == holder || message == null || message.isBlank()) {
                return;    // silence — or an unparseable/self-addressed reply — ends the table
            }
            if (message.length() > budgets.maxMessageChars()) {
                return;    // over the cap: not delivered; budget enforcement, not content policy
            }

            emit("message_sent", payload("player", holder.label(), "to", to.label(), "text", message));
            inbox.get(to).add("from " + holder.label() + ": \"" + message + "\"");

            String note = asText(action.get("note"));
            if (note != null && !note.isBlank() && note.length() <= budgets.maxMessageChars()) {
                emit("message_sent", payload("player", holder.label(), "to", null, "text", note));
                for (Color other : Color.values()) {
                    if (other != holder) {
                        inbox.get(other).add("(table) from " + holder.label() + ": \"" + note + "\"");
                    }
                }
            }

            passes++;
            if (passes >= budgets.maxFloorPasses()) return;
            holder = to;
            incoming = message;
        }
    }

    private String drainInbox(Color color) {
        List<String> lines = inbox.get(color);
        if (lines.isEmpty()) return "(none)";
        StringBuilder out = new StringBuilder();
        for (String line : lines) out.append("- ").append(line).append("\n");
        lines.clear();
        return out.toString().stripTrailing();
    }

    // -- choose: the only call that changes the game ----------------------

    private Move choose(TurnContext ctx) {
        turn = ctx.turn();
        if (exhausted()) {
            // The engine records this as a forfeit — the defined in-game outcome —
            // and the game runs on to its cap without model calls.
            throw new BudgetSpent("per-game token ceiling reached");
        }

        String prompt = ctx.attempt() == 1
                ? prompts.turn("decide").render(Map.of(
                        "turn", ctx.turn(),
                        "color", ctx.color().label(),
                        "die", ctx.die(),
                        "board", renderBoard(ctx.state()),
                        "legal_moves", renderMoves(ctx.legalMoves()),
                        "recent_events", window.render(),
                        "memory", memories.get(ctx.color()).render(40)))
                : prompts.turn("retry").render(Map.of(
                        "reason", "not a legal move for this roll",
                        "rejected", lastReply.getOrDefault(ctx.color(), "(no parseable reply)"),
                        "legal_moves", renderMoves(ctx.legalMoves())));

        String reply = ask(ctx.color(), "move", prompt);
        lastReply.put(ctx.color(), reply.strip());

        Map<String, Object> data = tryJson(reply);
        if (data == null) {
            throw new IllegalStateException("no JSON object in reply");  // costs the attempt, not the run
        }
        String reasoning = asText(data.get("reasoning"));
        if (reasoning != null && !reasoning.isBlank()) {
            emit("agent_reasoning", payload("player", ctx.color().label(), "text", reasoning));
        }

        int token = ((Number) data.get("token")).intValue();
        int to = ((Number) data.get("to")).intValue();
        for (Move move : ctx.legalMoves()) {
            if (move.token() == token && move.to() == to) return move;
        }
        // Not legal. Returned anyway: rejecting is the ENGINE's job (ADR-0004).
        int frm = token >= 0 && token <= 3 ? ctx.state().tokens(ctx.color())[token] : -1;
        return new Move(token, frm, to);
    }

    // -- reflect: one memory-write opportunity ----------------------------

    @SuppressWarnings("unchecked")
    private void reflect(TurnEnd end) {
        turn = end.turn();
        if (exhausted()) return;
        List<Map<String, Object>> notes;
        try {
            String prompt = prompts.turn("reflect").render(Map.of(
                    "turn", end.turn(),
                    "color", end.color().label(),
                    "turn_summary", renderEvents(end.events()),
                    "memory", memories.get(end.color()).render(40)));
            Map<String, Object> data = tryJson(ask(end.color(), "reflect", prompt));
            Object raw = data == null ? null : data.get("notes");
            if (!(raw instanceof List)) return;
            notes = (List<Map<String, Object>>) raw;
        } catch (RuntimeException e) {
            return;   // best-effort by contract: a failed reflection loses a note, never the game
        }
        for (Object item : notes) {
            if (!(item instanceof Map)) continue;
            Map<String, Object> note = (Map<String, Object>) item;
            String text = asText(note.get("text"));
            if (text == null || text.isBlank()) continue;
            String aboutLabel = asText(note.get("about"));
            String about = aboutLabel != null && BY_LABEL.containsKey(aboutLabel) ? aboutLabel : null;
            Memory.Note written = memories.get(end.color())
                    .write(text, end.turn(), asText(note.get("kind")), about);
            emit("memory_write", payload("player", end.color().label(), "kind", written.kind(),
                    "about", written.about(), "text", written.text()));
        }
    }

    // -- the model boundary ------------------------------------------------

    /** One model call through the framework: ChatClient in, usage metadata out,
     *  one {@code llm_call} event — never batched (harness-contract §3). */
    private String ask(Color color, String purpose, String user) {
        ChatResponse response = clients.get(color).prompt()
                .system(systemPrompt(color))
                .user(user)
                .call()
                .chatResponse();

        Usage usage = response.getMetadata().getUsage();
        int input = usage.getPromptTokens() == null ? 0 : usage.getPromptTokens();
        int output = usage.getCompletionTokens() == null ? 0 : usage.getCompletionTokens();
        spent += input + output;

        Map<String, Object> tokens = new LinkedHashMap<>();
        tokens.put("input", input);
        tokens.put("output", output);
        tokens.put("cache_read", 0);
        tokens.put("cache_write", 0);
        ModelsConfig.Seat seat = seatByColor.get(color);
        Map<String, Object> p = payload("player", color.label(), "model", "scripted",
                "access", seat.access(), "purpose", purpose);
        p.put("tokens", tokens);
        p.put("latency_ms", 0);
        emit("llm_call", p);

        return response.getResult().getOutput().getText();
    }

    private String systemPrompt(Color color) {
        return prompts.systemPrompt(Map.of(
                "color", color.label(),
                "max_floor_passes", budgets.maxFloorPasses(),
                "max_message_chars", budgets.maxMessageChars()));
    }

    // -- renders: the "code renders it" half of the no-template-logic rule --

    static String position(int p) {
        if (p == -1) return "base";
        if (p == 56) return "home";
        if (p >= 51) return "column+" + (p - 50);
        return String.valueOf(p);
    }

    static String renderBoard(StateView state) {
        StringBuilder out = new StringBuilder();
        for (Color color : Color.values()) {
            out.append("- ").append(color.label()).append(": ");
            int[] tokens = state.tokens(color);
            for (int i = 0; i < tokens.length; i++) {
                if (i > 0) out.append(", ");
                out.append(position(tokens[i]));
            }
            out.append("\n");
        }
        return out.toString().stripTrailing();
    }

    static String renderStandings(StateView state) {
        List<Color> order = new ArrayList<>(List.of(Color.values()));
        order.sort((a, b) -> {
            int byHome = Integer.compare(state.tokensHome(b), state.tokensHome(a));
            return byHome != 0 ? byHome : Integer.compare(state.progress(b), state.progress(a));
        });
        StringBuilder out = new StringBuilder();
        for (Color color : order) {
            out.append("- ").append(color.label()).append(": ")
               .append(state.tokensHome(color)).append(" home, progress ")
               .append(state.progress(color)).append("\n");
        }
        return out.toString().stripTrailing();
    }

    static String renderMoves(List<Move> moves) {
        StringBuilder out = new StringBuilder();
        for (Move m : moves) {
            out.append("- token ").append(m.token()).append(": ")
               .append(position(m.frm())).append(" -> ").append(position(m.to()))
               .append(" (reply {\"token\": ").append(m.token())
               .append(", \"to\": ").append(m.to()).append("})\n");
        }
        return out.toString().stripTrailing();
    }

    static String renderEvents(List<Map<String, Object>> events) {
        if (events.isEmpty()) return "(none)";
        StringBuilder out = new StringBuilder();
        for (Map<String, Object> e : events) {
            out.append("- ").append(e.get("type")).append(": ")
               .append(Json.compact(e.get("payload"))).append("\n");
        }
        return out.toString().stripTrailing();
    }

    /** A rolling window over the merged stream — the {{recent_events}} variable. */
    static final class RecentWindow extends EventSink {
        private final Deque<String> lines = new ArrayDeque<>();
        private final int limit;

        RecentWindow(int limit) {
            this.limit = limit;
        }

        @Override
        protected void write(Map<String, Object> event) {
            String payload = Json.compact(event.get("payload"));
            if (payload.length() > 160) payload = payload.substring(0, 160);
            lines.add("- [turn " + event.get("turn") + "] " + event.get("type") + ": " + payload);
            while (lines.size() > limit) lines.removeFirst();
        }

        String render() {
            return lines.isEmpty() ? "(none yet)" : String.join("\n", lines);
        }
    }

    // -- small helpers -----------------------------------------------------

    /** JSON is a subset of YAML, so the YAML parser already on hand reads it. */
    @SuppressWarnings("unchecked")
    private static Map<String, Object> tryJson(String text) {
        Matcher m = JSON_OBJECT.matcher(text);
        if (!m.find()) return null;
        try {
            Object parsed = new Yaml().load(m.group());
            return parsed instanceof Map ? (Map<String, Object>) parsed : null;
        } catch (RuntimeException e) {
            return null;
        }
    }

    private static String asText(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static Map<String, Object> payload(Object... pairs) {
        Map<String, Object> map = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) map.put((String) pairs[i], pairs[i + 1]);
        return map;
    }

    private void emit(String type, Map<String, Object> payload) {
        sink.emit(type, payload, turn);
    }
}
