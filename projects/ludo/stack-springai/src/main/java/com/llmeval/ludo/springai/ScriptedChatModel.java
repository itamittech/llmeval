package com.llmeval.ludo.springai;

import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.metadata.DefaultUsage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.Prompt;
import org.springframework.ai.model.tool.ToolCallingChatOptions;
import org.springframework.ai.model.tool.ToolCallingManager;
import org.springframework.ai.model.tool.ToolExecutionResult;
import org.yaml.snakeyaml.Yaml;

/**
 * A scripted model through Spring AI's own {@link ChatModel} seam — including
 * the part real provider bindings implement and a naive fake would skip:
 * <strong>internal tool execution</strong>. When a scripted reply is a tool
 * call, this model executes it through the framework's {@link ToolCallingManager}
 * and asks itself again with the tool result appended — exactly the loop
 * inside the Anthropic or Bedrock bindings. The floor-passing tool therefore
 * runs for real in tests, not as a simulation of itself.
 *
 * <p>Script entries:
 * <pre>
 *   "plain text"                                   → an assistant text reply
 *   {"tool": "pass_floor", "args": {...}}          → a tool call; the NEXT entry
 *                                                    is the reply after the result
 * </pre>
 *
 * <p>One consequence worth reading twice: a tool round-trip is TWO model
 * invocations inside ONE {@code call()} — and the caller sees one response.
 * Usage is aggregated across the chain so nothing goes unmetered, but
 * per-invocation granularity is lost. That is Spring AI's own behaviour with
 * internal tool execution, and it is recorded as a capability-matrix finding,
 * not smoothed over here.
 */
public final class ScriptedChatModel implements ChatModel {

    /** The script ran out — the run asked for more replies than it committed. */
    public static final class ScriptExhausted extends RuntimeException {
        ScriptExhausted(String message) {
            super(message);
        }
    }

    private static final Pattern JSON_OBJECT = Pattern.compile("\\{.*}", Pattern.DOTALL);

    private final ToolCallingManager toolCallingManager = ToolCallingManager.builder().build();
    private final List<String> replies;
    private int cursor;

    public ScriptedChatModel(List<String> replies) {
        this.replies = List.copyOf(replies);
    }

    /** How many replies have been consumed — an assertion surface for tests. */
    public int calls() {
        return cursor;
    }

    @Override
    public ChatResponse call(Prompt prompt) {
        ChatResponse response = respond(prompt, 0, 0);
        if (response.hasToolCalls()
                && ToolCallingChatOptions.isInternalToolExecutionEnabled(prompt.getOptions())) {
            ToolExecutionResult result = toolCallingManager.executeToolCalls(prompt, response);
            // Ask again with the tool result in view — the provider pattern.
            // Carry the chain's usage forward so the aggregate stays honest.
            DefaultUsage soFar = (DefaultUsage) response.getMetadata().getUsage();
            ChatResponse next = respond(new Prompt(result.conversationHistory(), prompt.getOptions()),
                    soFar.getPromptTokens(), soFar.getCompletionTokens());
            return next;
        }
        return response;
    }

    private ChatResponse respond(Prompt prompt, int carriedInput, int carriedOutput) {
        if (cursor >= replies.size()) {
            throw new ScriptExhausted(
                    "reply " + (cursor + 1) + " requested, only " + replies.size() + " scripted");
        }
        String reply = replies.get(cursor++);

        int inputChars = 0;
        for (Message message : prompt.getInstructions()) {
            String text = message.getText();
            if (text != null) inputChars += text.length();
        }
        int input = carriedInput + Math.max(1, inputChars / 4);
        int output = carriedOutput + Math.max(1, reply.length() / 4);

        AssistantMessage message = toolCall(reply);
        if (message == null) {
            message = new AssistantMessage(reply);
        }
        return new ChatResponse(
                List.of(new Generation(message)),
                ChatResponseMetadata.builder()
                        .model("scripted")
                        .usage(new DefaultUsage(input, output))
                        .build());
    }

    /** A {@code {"tool": name, "args": {...}}} entry becomes a real tool call. */
    @SuppressWarnings("unchecked")
    private AssistantMessage toolCall(String reply) {
        Matcher m = JSON_OBJECT.matcher(reply);
        if (!m.find()) return null;
        Object parsed;
        try {
            parsed = new Yaml().load(m.group());
        } catch (RuntimeException e) {
            return null;
        }
        if (!(parsed instanceof Map<?, ?> map) || !(map.get("tool") instanceof String name)) {
            return null;
        }
        Object args = map.get("args");
        String arguments = args == null ? "{}" : toJson((Map<String, Object>) args);
        return AssistantMessage.builder()
                .content("")
                .toolCalls(List.of(new AssistantMessage.ToolCall(
                        "script-" + cursor, "function", name, arguments)))
                .build();
    }

    private static String toJson(Map<String, Object> map) {
        StringBuilder out = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            if (!first) out.append(",");
            first = false;
            out.append("\"").append(entry.getKey()).append("\":\"")
               .append(String.valueOf(entry.getValue()).replace("\"", "\\\"")).append("\"");
        }
        return out.append("}").toString();
    }
}
