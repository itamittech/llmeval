package com.llmeval.relay.springai;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;
import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.metadata.DefaultUsage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.Prompt;

/**
 * A scripted model through Spring AI's own {@link ChatModel} seam.
 *
 * <p>Markedly simpler than ALIBI's, and the reason is worth reading. That one had to implement
 * <strong>internal tool execution</strong> — the loop a real provider binding runs when the model
 * asks for a tool — because the archivist was a tool and skipping the loop would have made the
 * fake lie about what a phase costs. RELAY has no tool. Escalation is a model swap the
 * <em>engine</em> performs, so there is no loop to reproduce and nothing to aggregate.
 *
 * <p>That is why this stack's call counts match the Python ones exactly, where ALIBI's came out
 * 20 against 22. The frameworks did not converge; the protocol stopped asking them to differ.
 *
 * <p>Replies are computed from the latest user message rather than replayed from a list, for the
 * same reason as the other two stacks: a hand-typed list encodes knowledge of the track that a
 * runner is not allowed to have. See {@link Policies}.
 */
public final class PolicyChatModel implements ChatModel {

    private final Function<String, String> decide;
    private final String label;
    private final List<String> seen = new ArrayList<>();
    private final List<String> seenRendered = new ArrayList<>();
    private int calls;

    public PolicyChatModel(Function<String, String> decide, String label) {
        this.decide = decide;
        this.label = label;
    }

    public int calls() {
        return calls;
    }

    public String label() {
        return label;
    }

    /** Everything this model was sent, its own replies included. */
    public List<String> seen() {
        return List.copyOf(seen);
    }

    /**
     * Only what the harness rendered. The seal tests need the distinction: a runner's own past
     * answer comes back as conversation history and proves nothing.
     */
    public List<String> seenRendered() {
        return List.copyOf(seenRendered);
    }

    @Override
    public ChatResponse call(Prompt prompt) {
        calls++;
        String latest = "";
        int inputChars = 0;
        for (Message message : prompt.getInstructions()) {
            String text = message.getText();
            if (text == null) {
                continue;
            }
            inputChars += text.length();
            seen.add(text);
            switch (message.getMessageType()) {
                case USER, SYSTEM -> {
                    seenRendered.add(text);
                    if (message.getMessageType().name().equals("USER")) {
                        latest = text;
                    }
                }
                default -> { }
            }
        }

        String reply = decide.apply(latest);
        return new ChatResponse(
                List.of(new Generation(new AssistantMessage(reply))),
                ChatResponseMetadata.builder()
                        .model(label)
                        .usage(new DefaultUsage(Math.max(1, inputChars / 4),
                                Math.max(1, reply.length() / 4)))
                        .build());
    }
}
