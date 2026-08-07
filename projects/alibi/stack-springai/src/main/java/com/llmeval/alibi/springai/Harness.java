package com.llmeval.alibi.springai;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.ai.chat.client.ChatClient;
import org.springframework.ai.chat.client.advisor.MessageChatMemoryAdvisor;
import org.springframework.ai.chat.memory.ChatMemory;
import org.springframework.ai.chat.memory.MessageWindowChatMemory;
import org.springframework.ai.chat.metadata.Usage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.tool.ToolCallback;
import org.springframework.ai.tool.function.FunctionToolCallback;
import org.yaml.snakeyaml.Yaml;

import com.llmeval.alibi.engine.Archive;
import com.llmeval.alibi.engine.Belief;
import com.llmeval.alibi.engine.CaseModel;
import com.llmeval.alibi.engine.Color;
import com.llmeval.alibi.engine.Detective;
import com.llmeval.alibi.engine.DetectiveView;
import com.llmeval.alibi.engine.EventSink;
import com.llmeval.alibi.engine.Game;
import com.llmeval.alibi.engine.GameConfig;
import com.llmeval.alibi.engine.Outcome;
import com.llmeval.alibi.engine.SearchBudget;
import com.llmeval.alibi.engine.ShowContext;
import com.llmeval.alibi.engine.Suggestion;
import com.llmeval.alibi.engine.SuggestionRecord;
import com.llmeval.alibi.engine.Triple;
import com.llmeval.alibi.engine.TurnContext;
import com.llmeval.alibi.engine.TurnEnd;

/**
 * The ALIBI harness on Spring AI — four {@link ChatClient}s over the engine's
 * detective seams, the archivist as a {@link FunctionToolCallback} executed by
 * the framework's own tool-calling machinery.
 *
 * <p>The grain LUDO recorded holds here too: Spring AI executes tools
 * <em>inside</em> the model call, so a consultation is two model invocations
 * the caller sees as ONE response — one {@code llm_call} with aggregated
 * usage, where the Python stacks emit two. The event counts differ between
 * stacks and the capability matrix says why; smoothing it over here would
 * falsify the comparison.
 *
 * <p>Conversation memory is the framework's ({@code MessageWindowChatMemory} +
 * advisor, one conversation per colour); the notebook is hand-rolled
 * ({@link Notebook}) because the framework still has no belief store — LUDO's
 * Manual, unchanged in game two.
 */
public final class Harness {

    /** Raised by phases once the per-game ceiling is spent. */
    static final class BudgetSpent extends RuntimeException {
        BudgetSpent(String message) {
            super(message);
        }
    }

    /** The archivist tool's input. */
    public record ConsultQuery(String query) {}

    private static final Pattern JSON_OBJECT = Pattern.compile("\\{.*}", Pattern.DOTALL);
    private static final Pattern JSON_ARRAY = Pattern.compile("\\[.*]", Pattern.DOTALL);
    private static final int MEMORY_RENDER_LIMIT = 40;
    private static final int TABLE_LIMIT = 12;
    private static final int MAX_NOTES_PER_REFLECT = 3;
    //: Pinned explicitly — a framework default here would be a silent parity break.
    private static final int CONVERSATION_WINDOW = 24;

    private final Prompts prompts;
    private final ModelsConfig config;
    private final EventSink sink;
    private final Game game;
    private final Map<Color, ChatClient> clients = new EnumMap<>(Color.class);
    private final Map<Color, Notebook> notebooks = new EnumMap<>(Color.class);
    private final Map<Color, ModelsConfig.Seat> seatByColor = new EnumMap<>(Color.class);
    private final Map<Color, Detective> deciders = new EnumMap<>(Color.class);
    private final MessageChatMemoryAdvisor memoryAdvisor;
    private final ToolCallback consultTool;
    private final Set<String> validDocIds;

    private SearchBudget currentBudget;
    private int spent;
    private int turn;
    private int meteredCalls;

    public Harness(ModelsConfig config, Prompts prompts, Map<Color, ChatModel> models,
                   EventSink sink, int seed, int gameIndex, Integer maxTurns) {
        this.config = config;
        this.prompts = prompts;
        this.sink = sink;

        ChatMemory chatMemory = MessageWindowChatMemory.builder()
                .maxMessages(CONVERSATION_WINDOW)
                .build();
        this.memoryAdvisor = MessageChatMemoryAdvisor.builder(chatMemory).build();
        this.consultTool = consultArchivistTool();

        Map<Color, Map<String, Object>> players = new EnumMap<>(Color.class);
        Color[] colors = Color.values();
        for (int i = 0; i < colors.length; i++) {
            Color color = colors[i];
            ModelsConfig.Seat seat = config.seatFor(i, gameIndex);
            seatByColor.put(color, seat);
            Map<String, Object> meta = new LinkedHashMap<>();
            meta.put("seat", seat.seat());
            meta.put("model", "scripted");
            meta.put("access", seat.access());
            players.put(color, meta);
            clients.put(color, ChatClient.create(models.get(color)));
            notebooks.put(color, new Notebook());
            deciders.put(color, new SpringDetective(color));
        }

        int cap = maxTurns != null ? maxTurns : config.budgets().maxTurns();
        Map<String, Object> promptSet = new LinkedHashMap<>();
        promptSet.put("version", prompts.version());
        promptSet.put("hash", prompts.digest());
        Map<String, Object> framework = new LinkedHashMap<>();
        framework.put("name", "springai");
        framework.put("version", springAiVersion());
        Map<String, Object> archivist = new LinkedHashMap<>();
        archivist.put("agent", "baseline-retriever");
        archivist.put("retrieval_profile", config.archivist().retrievalProfile());

        this.game = new Game(new GameConfig(seed, cap,
                config.budgets().maxSearchesPerTurn(), "baseline", "springai",
                players, config.name(), promptSet, framework, archivist), sink);

        Set<String> ids = new HashSet<>();
        for (Archive.Document doc : game.archive().documents()) {
            ids.add(doc.id());
        }
        this.validDocIds = Set.copyOf(ids);
    }

    /** The framework build the lockfile pinned, read from the jar manifest. */
    static String springAiVersion() {
        String version = ChatModel.class.getPackage().getImplementationVersion();
        return version == null ? "unknown" : version;
    }

    public Outcome play() {
        return game.play(deciders);
    }

    public Game game() {
        return game;
    }

    public int spent() {
        return spent;
    }

    public int meteredCalls() {
        return meteredCalls;
    }

    Notebook notebook(Color color) {
        return notebooks.get(color);
    }

    private boolean exhausted() {
        return spent >= config.budgets().maxTokensPerGame();
    }

    // -- the archivist as a framework tool --------------------------------

    private ToolCallback consultArchivistTool() {
        Function<ConsultQuery, String> execute = (consult) -> {
            SearchBudget budget = currentBudget;
            if (budget == null) {
                return "The archivist is unavailable outside your own deliberation.";
            }
            List<Archive.Document> results = budget.search(String.valueOf(consult.query()));
            if (results.isEmpty()) {
                return "The archive has nothing on that.";
            }
            StringBuilder out = new StringBuilder();
            for (Archive.Document doc : results) {
                if (!out.isEmpty()) {
                    out.append("\n");
                }
                out.append("[").append(doc.id()).append("] (").append(doc.kind())
                   .append(") ").append(doc.text());
            }
            return out.toString();
        };
        return FunctionToolCallback.builder("consult_archivist", execute)
                .description("Ask the hotel archivist to search the case archive. Returns "
                        + "the most relevant documents, each tagged with its citable "
                        + "[doc-id]. Quota per turn is limited; an exhausted quota "
                        + "returns nothing.")
                .inputType(ConsultQuery.class)
                .build();
    }

    // -- the engine-facing adapter -----------------------------------------

    private final class SpringDetective implements Detective {

        private final Color color;

        SpringDetective(Color color) {
            this.color = color;
        }

        @Override
        public String name() {
            return "llm-detective";
        }

        @Override
        public Suggestion suggest(TurnContext ctx) {
            turn = ctx.turn();
            if (exhausted()) {
                return null;
            }
            currentBudget = ctx.archive();
            String reply;
            try {
                reply = ask(color, "suggest", true, prompts.turn("suggest").render(Map.of(
                        "turn", ctx.turn(),
                        "color", color.json(),
                        "hand", String.join(", ", ctx.view().myHand()),
                        "eliminated", renderEliminated(ctx.view()),
                        "table", renderTable(ctx.view()),
                        "memory", notebooks.get(color).render(MEMORY_RENDER_LIMIT))));
            } finally {
                currentBudget = null;
            }

            Map<String, Object> data = parseObject(reply);
            maybeReasoning(color, data);
            if ("pass".equals(data.get("action"))) {
                return null;
            }
            if (!"suggest".equals(data.get("action"))) {
                throw new IllegalArgumentException("unknown action " + data.get("action"));
            }
            String note = data.get("note") instanceof String s && !s.isBlank()
                    ? gateNote(color, s.strip()) : null;
            return new Suggestion(String.valueOf(data.get("who")),
                    String.valueOf(data.get("how")),
                    String.valueOf(data.get("where")), note);
        }

        @Override
        public String show(ShowContext ctx) {
            turn = ctx.turn();
            if (exhausted()) {
                throw new BudgetSpent("ceiling spent — the engine chooses");
            }
            Suggestion s = ctx.suggestion();
            String reply = ask(color, "show", false, prompts.turn("show").render(Map.of(
                    "suggester", ctx.suggester().json(),
                    "suggestion", s.who() + " / " + s.how() + " / " + s.where(),
                    "options", String.join(", ", ctx.options()))));
            Map<String, Object> data = parseObject(reply);
            maybeReasoning(color, data);
            return String.valueOf(data.get("show"));
        }

        @Override
        public Triple accuse(TurnContext ctx) {
            turn = ctx.turn();
            if (exhausted()) {
                return null;
            }
            String outcome;
            if (ctx.refutation() != null) {
                outcome = "The " + ctx.refutation().refuter().json()
                        + " detective privately showed you: " + ctx.refutation().element()
                        + ". That element is certainly NOT part of the truth.";
            } else if (ctx.noRefutation() != null) {
                Suggestion s = ctx.noRefutation();
                outcome = "NOBODY could refute your suggestion (" + s.who() + " / "
                        + s.how() + " / " + s.where() + "). If you hold none of those "
                        + "three yourself, that suggestion IS the answer.";
            } else {
                outcome = "You made no suggestion this turn.";
            }

            currentBudget = ctx.archive();
            String reply;
            try {
                reply = ask(color, "accuse", true, prompts.turn("accuse").render(Map.of(
                        "outcome", outcome,
                        "memory", notebooks.get(color).render(MEMORY_RENDER_LIMIT))));
            } finally {
                currentBudget = null;
            }

            Map<String, Object> data = parseObject(reply);
            maybeReasoning(color, data);
            if ("accuse".equals(data.get("action"))) {
                return new Triple(String.valueOf(data.get("who")),
                        String.valueOf(data.get("how")),
                        String.valueOf(data.get("where")));
            }
            if ("wait".equals(data.get("action"))) {
                return null;
            }
            throw new IllegalArgumentException("unknown action " + data.get("action"));
        }

        @Override
        @SuppressWarnings("unchecked")
        public Belief conclude(TurnContext ctx) {
            turn = ctx.turn();
            if (exhausted()) {
                throw new BudgetSpent("ceiling spent — no belief to declare");
            }
            String reply = ask(color, "conclude", false, prompts.turn("conclude").render(Map.of(
                    "candidates", renderCandidates(ctx.view()),
                    "memory", notebooks.get(color).render(MEMORY_RENDER_LIMIT))));
            Map<String, Object> data = parseObject(reply);
            maybeReasoning(color, data);
            Map<String, Object> raw = data.get("confidence") instanceof Map<?, ?> m
                    ? (Map<String, Object>) m : Map.of();
            Map<String, Double> confidence = new LinkedHashMap<>();
            for (String dim : CaseModel.DIMENSIONS) {
                Object value = raw.get(dim);
                confidence.put(dim, value instanceof Number n ? n.doubleValue() : 0.0);
            }
            return new Belief(String.valueOf(data.get("who")),
                    String.valueOf(data.get("how")),
                    String.valueOf(data.get("where")), confidence);
        }

        @Override
        public void reflect(TurnEnd end) {
            if (exhausted()) {
                return;
            }
            String reply = ask(color, "reflect", false, prompts.turn("reflect").render(Map.of(
                    "turn", end.turn(),
                    "turn_summary", renderTurnSummary(end.events()),
                    "memory", notebooks.get(color).render(MEMORY_RENDER_LIMIT))));
            List<Object> notes;
            try {
                notes = parseArray(reply);
            } catch (RuntimeException e) {
                return; // a reflect that says nothing loses only its own notes
            }
            int accepted = 0;
            for (Object raw : notes) {
                if (accepted >= MAX_NOTES_PER_REFLECT || !(raw instanceof Map<?, ?> map)) {
                    continue;
                }
                String text = map.get("text") instanceof String s ? s.strip() : "";
                if (text.isEmpty()) {
                    continue;
                }
                String about = map.get("about") instanceof String a ? a : null;
                if (about != null && !CaseModel.ALL_ELEMENTS.contains(about)
                        && !isColor(about)) {
                    about = null;
                }
                Notebook.Note note = notebooks.get(color).write(
                        text, end.turn(),
                        map.get("kind") instanceof String k ? k : null, about);
                Map<String, Object> payload = new LinkedHashMap<>();
                payload.put("player", color.json());
                payload.put("kind", note.kind());
                payload.put("about", note.about());
                payload.put("text", note.text());
                sink.emit("memory_write", payload, end.turn());
                accepted++;
            }
        }
    }

    // -- asking and metering -----------------------------------------------

    private String ask(Color color, String purpose, boolean withTool, String user) {
        var spec = clients.get(color).prompt()
                .system(systemPrompt(color))
                .user(user)
                .advisors(memoryAdvisor)
                .advisors(a -> a.param(ChatMemory.CONVERSATION_ID, color.json()));
        if (withTool) {
            spec = spec.toolCallbacks(consultTool);
        }
        ChatResponse response = spec.call().chatResponse();
        meter(color, purpose, response);
        return response.getResult().getOutput().getText();
    }

    /** ONE llm_call per client call — a consultation's two invocations arrive
     *  aggregated, which is Spring AI's own grain, recorded not smoothed. */
    private void meter(Color color, String purpose, ChatResponse response) {
        Usage usage = response.getMetadata().getUsage();
        int input = usage.getPromptTokens() == null ? 0 : usage.getPromptTokens();
        int output = usage.getCompletionTokens() == null ? 0 : usage.getCompletionTokens();
        spent += input + output;
        meteredCalls++;

        Map<String, Object> tokens = new LinkedHashMap<>();
        tokens.put("input", input);
        tokens.put("output", output);
        tokens.put("cache_read", 0);
        tokens.put("cache_write", 0);
        ModelsConfig.Seat seat = seatByColor.get(color);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("player", color.json());
        payload.put("model", "scripted");
        payload.put("access", seat.access());
        payload.put("purpose", purpose);
        payload.put("tokens", tokens);
        payload.put("latency_ms", 0);
        sink.emit("llm_call", payload, turn);
    }

    private String systemPrompt(Color color) {
        return prompts.systemPrompt(Map.of(
                "color", color.json(),
                "max_searches_per_turn", config.budgets().maxSearchesPerTurn(),
                "max_note_chars", config.budgets().maxNoteChars()));
    }

    private void maybeReasoning(Color color, Map<String, Object> data) {
        if (data.get("reasoning") instanceof String text && !text.isBlank()) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("player", color.json());
            payload.put("text", text.strip());
            sink.emit("agent_reasoning", payload, turn);
        }
    }

    private String gateNote(Color color, String note) {
        if (note.length() > config.budgets().maxNoteChars()) {
            note = note.substring(0, config.budgets().maxNoteChars());
        }
        Guardrails.Violation violation = Guardrails.check(note, validDocIds);
        if (violation != null) {
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("player", color.json());
            payload.put("rule", violation.rule());
            payload.put("action", "blocked");
            payload.put("source", "harness");
            payload.put("detail", violation.reason());
            sink.emit("guardrail_triggered", payload, turn);
            return null;
        }
        return note;
    }

    // -- renders: the "code renders it" half of the no-logic rule ----------

    static String renderEliminated(DetectiveView view) {
        List<String> known = view.knownNotSolution();
        return known.isEmpty() ? "(none)" : String.join(", ", known);
    }

    static String renderTable(DetectiveView view) {
        List<SuggestionRecord> log = view.suggestions();
        if (log.isEmpty()) {
            return "(no suggestions yet)";
        }
        List<SuggestionRecord> tail =
                log.subList(Math.max(0, log.size() - TABLE_LIMIT), log.size());
        StringBuilder out = new StringBuilder();
        for (SuggestionRecord r : tail) {
            if (!out.isEmpty()) {
                out.append("\n");
            }
            String refuted = r.refuter() != null
                    ? "refuted by " + r.refuter().json() : "NOBODY could refute";
            String note = r.note() != null ? " — note: \"" + r.note() + "\"" : "";
            out.append("- turn ").append(r.turn()).append(": ")
               .append(r.player().json()).append(" suggested ")
               .append(r.who()).append(" / ").append(r.how()).append(" / ")
               .append(r.where()).append(" (").append(refuted).append(")").append(note);
        }
        return out.toString();
    }

    static String renderCandidates(DetectiveView view) {
        Set<String> known = new HashSet<>(view.knownNotSolution());
        List<String> parts = new ArrayList<>();
        for (String dim : CaseModel.DIMENSIONS) {
            List<String> open = new ArrayList<>();
            for (String element : CaseModel.elements(dim)) {
                if (!known.contains(element)) {
                    open.add(element);
                }
            }
            parts.add(dim + ": " + String.join(", ", open));
        }
        return String.join(" | ", parts);
    }

    @SuppressWarnings("unchecked")
    static String renderTurnSummary(List<Map<String, Object>> events) {
        List<String> lines = new ArrayList<>();
        for (Map<String, Object> event : events) {
            String kind = (String) event.get("type");
            Map<String, Object> p = (Map<String, Object>) event.get("payload");
            switch (kind) {
                case "suggestion_made" -> lines.add("you suggested " + p.get("who")
                        + " / " + p.get("how") + " / " + p.get("where"));
                case "refutation_made" -> {
                    if (p.get("refuter") == null) {
                        lines.add("NOBODY could refute your suggestion");
                    } else {
                        lines.add(p.get("refuter") + " privately showed you: "
                                + p.get("element"));
                    }
                }
                case "archive_searched" -> {
                    List<String> results = (List<String>) p.get("results");
                    lines.add("you searched \"" + p.get("query") + "\" -> "
                            + (results.isEmpty() ? "nothing" : String.join(", ", results)));
                }
                case "accusation_made" -> lines.add("you accused " + p.get("who")
                        + " / " + p.get("how") + " / " + p.get("where") + ": "
                        + (Boolean.TRUE.equals(p.get("correct"))
                           ? "CORRECT" : "wrong — you are out"));
                case "invalid_action" -> lines.add("invalid " + p.get("phase")
                        + ": " + p.get("reason"));
                default -> { }
            }
        }
        if (lines.isEmpty()) {
            return "- (a quiet turn)";
        }
        StringBuilder out = new StringBuilder();
        for (String line : lines) {
            if (!out.isEmpty()) {
                out.append("\n");
            }
            out.append("- ").append(line);
        }
        return out.toString();
    }

    private static boolean isColor(String value) {
        for (Color color : Color.values()) {
            if (color.json().equals(value)) {
                return true;
            }
        }
        return false;
    }

    // -- parsing -----------------------------------------------------------

    @SuppressWarnings("unchecked")
    static Map<String, Object> parseObject(String reply) {
        Matcher m = JSON_OBJECT.matcher(reply);
        if (!m.find()) {
            throw new IllegalArgumentException("no JSON object in reply");
        }
        Object parsed = new Yaml().load(m.group());
        if (!(parsed instanceof Map)) {
            throw new IllegalArgumentException("reply is not a JSON object");
        }
        return (Map<String, Object>) parsed;
    }

    @SuppressWarnings("unchecked")
    static List<Object> parseArray(String reply) {
        Matcher m = JSON_ARRAY.matcher(reply);
        if (!m.find()) {
            throw new IllegalArgumentException("no JSON array in reply");
        }
        Object parsed = new Yaml().load(m.group());
        if (!(parsed instanceof List)) {
            throw new IllegalArgumentException("reply is not a JSON array");
        }
        return (List<Object>) parsed;
    }
}
