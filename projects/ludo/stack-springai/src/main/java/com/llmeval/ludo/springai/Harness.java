package com.llmeval.ludo.springai;

import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.messages.UserMessage;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.function.FunctionToolCallback;
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
 * <p>The engine drives and calls three hooks per turn (harness-contract §2);
 * this class answers them over {@link ChatClient}:
 *
 * <ul>
 *   <li><b>negotiate</b> — the floor-passing table of ADR-0009. Spring AI has
 *       no swarm orchestrator, so the loop over floor-holders is harness code
 *       (a recorded <em>Manual</em>) — but the floor-pass action itself is a
 *       real framework tool ({@code pass_floor}, a {@link FunctionToolCallback})
 *       whose schema reaches the model as framework-authored text, exactly
 *       ADR-0009's boundary. The guardrail gate lives inside the tool: a
 *       blocked message never delivers, and the model reads why.
 *   <li><b>choose / reflect</b> — one conversation per agent, carried by the
 *       framework's {@link ChatMemory} through a {@link MessageChatMemoryAdvisor}.
 *       The conversation grows turn over turn; past the game's context budget,
 *       the oldest exchanges are summarised into durable memory — the
 *       summariser is hand-rolled because Spring AI has no summarising memory,
 *       another recorded Manual.
 * </ul>
 *
 * <p>Every model call's usage is read from the framework's response metadata
 * into one {@code llm_call}. With internal tool execution, a tool round-trip
 * is two invocations inside one call — usage is aggregated by the scripted
 * model and the granularity loss is a capability-matrix finding.
 *
 * <p>Session persistence is opt-in via the {@code sessionDir} constructor:
 * conversations persist through the framework's JDBC repository, beliefs
 * through {@link #persist()} — the split lives in {@link Session}.
 */
public final class Harness {

    /** Raised by choose once the ceiling is spent; the engine records a forfeit. */
    public static final class BudgetSpent extends RuntimeException {
        BudgetSpent(String message) {
            super(message);
        }
    }

    /** The floor-pass action's input — the schema the framework describes to the model. */
    public record PassFloor(String to, String message, String note) {}

    private static final Pattern JSON_OBJECT = Pattern.compile("\\{.*}", Pattern.DOTALL);
    private static final int PRESERVE_RECENT_MESSAGES = 4;
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
    private final ChatMemory conversations;
    private final MessageChatMemoryAdvisor memoryAdvisor;
    private final Session session;
    private final EventSink sink;
    private final RecentWindow window;
    private final Game game;

    private long spent;
    private int turn;

    public Harness(ModelsConfig.Profile profile, Prompts prompts,
                   Map<Color, ChatModel> models, EventSink destination,
                   int seed, int gameIndex, Integer maxTurns) {
        this(profile, prompts, models, destination, seed, gameIndex, maxTurns, null);
    }

    /**
     * With a {@code sessionDir}, agent-side state survives the process:
     * conversations through the framework's JDBC repository, beliefs through
     * {@link #persist()}. Constructing over a directory that already holds a
     * session IS the restore — see {@link Session}.
     */
    public Harness(ModelsConfig.Profile profile, Prompts prompts,
                   Map<Color, ChatModel> models, EventSink destination,
                   int seed, int gameIndex, Integer maxTurns, Path sessionDir) {
        this.prompts = prompts;
        this.budgets = profile.budgets();
        this.seatByColor = ModelsConfig.seating(profile, gameIndex);

        // One tee: engine and harness events share one sequence (ADR-0003).
        this.window = new RecentWindow(30);
        this.sink = new EventSink.TeeSink(destination, window);

        // The framework's conversation memory, one conversation per colour.
        // The window is set far above the game's own budget so OUR compaction
        // triggers first — the framework's only strategy is silent truncation.
        // With a session, the memory is backed by the framework's JDBC
        // repository instead of the in-memory default: every exchange the
        // advisor saves is then written through to disk as it happens.
        this.session = sessionDir == null ? null : Session.open(sessionDir);
        MessageWindowChatMemory.Builder memoryBuilder =
                MessageWindowChatMemory.builder().maxMessages(400);
        if (session != null) memoryBuilder.chatMemoryRepository(session.conversations());
        this.conversations = memoryBuilder.build();
        this.memoryAdvisor = MessageChatMemoryAdvisor.builder(conversations).build();

        Map<Color, Memory> restored = session == null ? Map.of() : session.loadBeliefs();
        Map<Color, Map<String, Object>> players = new EnumMap<>(Color.class);
        for (Color color : Color.values()) {
            clients.put(color, ChatClient.create(models.get(color)));
            memories.put(color, restored.getOrDefault(color, new Memory()));
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
        try {
            return game.play(deciders);
        } finally {
            persist();
        }
    }

    /**
     * Save what the framework does not hold. Conversations need no call here —
     * with a session, the JDBC repository wrote every exchange as it happened.
     * Beliefs do: {@link Memory} never touches the framework, so skipping this
     * would lose every note silently while the conversations survived. That
     * asymmetry is the capability-matrix finding, pinned by a test.
     */
    public void persist() {
        if (session != null) session.saveBeliefs(memories);
    }

    List<Message> conversation(Color color) {
        return conversations.get(color.label());
    }

    Memory memory(Color color) {
        return memories.get(color);
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

    /** Everything one table run needs to remember between floor holdings. */
    private static final class TableState {
        Color holder;
        Color nextHolder;
        String lastMessage;
        boolean delivered;
        int passes;

        TableState(Color opener) {
            holder = opener;
        }
    }

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

        TableState state = new TableState(start.color());
        ToolCallback passFloor = passFloorTool(state);

        while (true) {
            state.delivered = false;
            String context = briefings.get(state.holder) + "\n\n" + task
                    + (state.lastMessage == null ? ""
                       : "\n\nMessage addressed to you this conversation: " + state.lastMessage);

            ChatResponse response = clients.get(state.holder).prompt()
                    .system(systemPrompt(state.holder))
                    .user(context)
                    .toolCallbacks(passFloor)
                    .call()
                    .chatResponse();
            meter(state.holder, "negotiate", response);

            if (!state.delivered || state.passes >= budgets.maxFloorPasses()) return;
            state.holder = state.nextHolder;
        }
    }

    /**
     * The floor-pass action as a real framework tool. The delivery decision —
     * length cap, guardrail gate, inbox fan-out, events — happens INSIDE the
     * tool, so what the model gets back is the truth about what was delivered.
     */
    private ToolCallback passFloorTool(TableState state) {
        Function<PassFloor, String> execute = (pass) -> {
            if (state.passes >= budgets.maxFloorPasses()) {
                return "the table is closed: the floor-pass cap was reached";
            }
            Color to = pass.to() == null ? null : BY_LABEL.get(pass.to());
            String message = pass.message();
            if (to == null || to == state.holder || message == null || message.isBlank()) {
                return "not delivered: name one other player and give the message";
            }
            if (message.length() > budgets.maxMessageChars()) {
                return "not delivered: over the " + budgets.maxMessageChars()
                        + "-character limit — say it shorter";
            }
            Guardrails.Violation violation = Guardrails.check(message);
            String note = pass.note();
            if (violation == null && note != null && !note.isBlank()) {
                violation = Guardrails.check(note);
            }
            if (violation != null) {
                emit("guardrail_triggered", payload("player", state.holder.label(),
                        "rule", violation.rule(), "action", "blocked",
                        "source", "harness", "detail", violation.reason()));
                return "message not delivered: " + violation.reason();
            }

            emit("message_sent", payload("player", state.holder.label(),
                    "to", to.label(), "text", message));
            inbox.get(to).add("from " + state.holder.label() + ": \"" + message + "\"");
            if (note != null && !note.isBlank() && note.length() <= budgets.maxMessageChars()) {
                emit("message_sent", payload("player", state.holder.label(), "to", null, "text", note));
                for (Color other : Color.values()) {
                    if (other != state.holder) {
                        inbox.get(other).add("(table) from " + state.holder.label() + ": \"" + note + "\"");
                    }
                }
            }
            state.delivered = true;
            state.nextHolder = to;
            state.lastMessage = message;
            state.passes++;
            return "delivered to " + to.label();
        };

        return FunctionToolCallback.builder("pass_floor", execute)
                .description("Send one message to one named player (red, green, yellow or blue) "
                        + "and pass them the floor. Optionally include a public table note every "
                        + "player will see. This is the only way to speak; reply without calling "
                        + "it to end the conversation.")
                .inputType(PassFloor.class)
                .build();
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

        String prompt;
        if (ctx.attempt() == 1) {
            maybeCompact(ctx.color());
            prompt = prompts.turn("decide").render(Map.of(
                    "turn", ctx.turn(),
                    "color", ctx.color().label(),
                    "die", ctx.die(),
                    "board", renderBoard(ctx.state()),
                    "legal_moves", renderMoves(ctx.legalMoves()),
                    "recent_events", window.render(),
                    "memory", memories.get(ctx.color()).render(40)));
        } else {
            // Same conversation, so the model sees its own rejected answer.
            prompt = prompts.turn("retry").render(Map.of(
                    "reason", "not a legal move for this roll",
                    "rejected", lastReply.getOrDefault(ctx.color(), "(no parseable reply)"),
                    "legal_moves", renderMoves(ctx.legalMoves())));
        }

        String reply = askInConversation(ctx.color(), "move", prompt);
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
            Map<String, Object> data = tryJson(askInConversation(end.color(), "reflect", prompt));
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

    // -- compaction (harness-contract §5): a recorded Manual ---------------

    /**
     * Spring AI's only conversation-management strategy is a sliding window —
     * silent truncation, exactly what §5 forbids replacing summarisation with.
     * So the summariser is harness code: past the game's context budget, the
     * oldest exchanges are summarised (by the agent's own model, metered as
     * {@code purpose: "compact"}), folded into durable memory, and the
     * framework's {@link ChatMemory} is rebuilt as summary + recent.
     */
    private void maybeCompact(Color color) {
        List<Message> history = conversations.get(color.label());
        int tokensBefore = estimateTokens(history) + systemPrompt(color).length() / 4;
        if (tokensBefore <= budgets.maxContextTokens()) return;
        if (history.size() <= PRESERVE_RECENT_MESSAGES) return;

        List<Message> oldest = history.subList(0, history.size() - PRESERVE_RECENT_MESSAGES);
        List<Message> recent = List.copyOf(history.subList(oldest.size(), history.size()));

        StringBuilder transcript = new StringBuilder();
        for (Message message : oldest) {
            transcript.append(message.getMessageType()).append(": ")
                      .append(message.getText()).append("\n");
        }
        String summary = askOneShot(color, "compact",
                "Summarise this earlier part of your game so far in at most three sentences, "
                        + "first person, keeping any deals and suspicions:\n\n" + transcript)
                .strip();

        memories.get(color).absorb(summary);
        conversations.clear(color.label());
        List<Message> rebuilt = new ArrayList<>();
        rebuilt.add(new UserMessage("(summary of earlier turns) " + summary));
        rebuilt.add(new AssistantMessage("Noted."));
        rebuilt.addAll(recent);
        conversations.add(color.label(), rebuilt);

        emit("context_compacted", payload("player", color.label(),
                "tokens_before", tokensBefore,
                "tokens_after", estimateTokens(conversations.get(color.label())),
                "summary", summary));
    }

    private static int estimateTokens(List<Message> messages) {
        int chars = 0;
        for (Message message : messages) {
            String text = message.getText();
            if (text != null) chars += text.length();
        }
        return chars / 4;
    }

    // -- the model boundary ------------------------------------------------

    /** Decide and reflect live in one framework-held conversation per agent. */
    private String askInConversation(Color color, String purpose, String user) {
        ChatResponse response = clients.get(color).prompt()
                .system(systemPrompt(color))
                .user(user)
                .advisors(memoryAdvisor)
                .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, color.label()))
                .call()
                .chatResponse();
        meter(color, purpose, response);
        return response.getResult().getOutput().getText();
    }

    /** Table and compaction calls are one-shot: the conversation is for the game. */
    private String askOneShot(Color color, String purpose, String user) {
        ChatResponse response = clients.get(color).prompt()
                .system(systemPrompt(color))
                .user(user)
                .call()
                .chatResponse();
        meter(color, purpose, response);
        return response.getResult().getOutput().getText();
    }

    /** One llm_call per client call, usage from the framework's own metadata. */
    private void meter(Color color, String purpose, ChatResponse response) {
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
