package com.llmeval.ludo.springai;

import java.util.List;

import org.springframework.ai.chat.messages.AssistantMessage;
import org.springframework.ai.chat.messages.Message;
import org.springframework.ai.chat.metadata.ChatResponseMetadata;
import org.springframework.ai.chat.metadata.DefaultUsage;
import org.springframework.ai.chat.model.ChatModel;
import org.springframework.ai.chat.model.ChatResponse;
import org.springframework.ai.chat.model.Generation;
import org.springframework.ai.chat.prompt.Prompt;

/**
 * A scripted model, implemented through Spring AI's own {@link ChatModel}
 * interface — the same seam a provider binding implements, and the harness
 * contract's §8 requirement made concrete for the third stack: the fake sits
 * at the framework's extension point, so everything above it (the
 * {@code ChatClient}, metering, the whole turn loop) runs exactly as it
 * would live, with only the network call replaced.
 *
 * <p>Usage numbers are deterministic pretend-values — chars/4, the same
 * heuristic the Strands scripted model uses — so token accounting and the
 * budget ceiling are exercisable offline, and all-zero usage can't hide a
 * broken meter.
 */
public final class ScriptedChatModel implements ChatModel {

    /** The script ran out — the run asked for more replies than it committed. */
    public static final class ScriptExhausted extends RuntimeException {
        ScriptExhausted(String message) {
            super(message);
        }
    }

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
        int input = Math.max(1, inputChars / 4);
        int output = Math.max(1, reply.length() / 4);

        return new ChatResponse(
                List.of(new Generation(new AssistantMessage(reply))),
                ChatResponseMetadata.builder()
                        .model("scripted")
                        .usage(new DefaultUsage(input, output))
                        .build());
    }
}
