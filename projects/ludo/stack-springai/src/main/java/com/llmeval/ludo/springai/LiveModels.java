package com.llmeval.ludo.springai;

import java.util.Map;

import org.springframework.ai.anthropic.AnthropicChatOptions;

/**
 * Live provider construction — the settings half, testable without a key.
 *
 * <p>Same shape as the Strands stack's {@code strands_client.py}: turn a
 * {@code shared/models.yaml} seat into pinned framework options, and assert in
 * tests that every pinned setting actually arrives — an unpinned sampling
 * parameter is a parity break that never announces itself.
 *
 * <p>Only the Anthropic direct route is built here — the ADR-0005 control
 * seat. The Bedrock route (Anthropic + Nova) and DeepSeek arrive with live
 * play, alongside Spring Boot and the provider starters; until model IDs are
 * pinned there is nothing true to construct for them, and this class throws
 * rather than pretending.
 */
public final class LiveModels {

    private LiveModels() {}

    /** Pinned options for one seat. Never called with an unpinned seat. */
    public static AnthropicChatOptions anthropicOptions(ModelsConfig.Seat seat,
                                                        Map<String, Object> inference) {
        if (!"anthropic".equals(seat.provider()) || !"direct".equals(seat.access())) {
            throw new UnsupportedOperationException(
                    "no live binding for " + seat.provider() + " via " + seat.access()
                            + " yet — arrives with live play");
        }
        AnthropicChatOptions.Builder options = AnthropicChatOptions.builder()
                .model(seat.model());
        Object maxTokens = inference.get("max_output_tokens");
        if (maxTokens instanceof Number n) {
            options.maxTokens(n.intValue());
        }
        // The Claude 5 effort/thinking controls ride provider-specific fields
        // the current options surface does not expose; they are wired when the
        // live ChatModel is constructed, and the gap is noted in the matrix
        // rather than silently dropped.
        return options.build();
    }
}
