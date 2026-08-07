package com.llmeval.relay.engine;

/**
 * One stage of the track, secrets included.
 *
 * <p>Only the engine ever holds one of these. What a runner sees is {@link #publicView()}, which
 * has no tier and no answer — the seal is a type rather than a rule, so a harness cannot reach for
 * what it was not given.
 */
public record Stage(String id, String family, int tier, String prompt, String answer) {

    public PublicStage publicView() {
        return new PublicStage(id, family, prompt);
    }
}
