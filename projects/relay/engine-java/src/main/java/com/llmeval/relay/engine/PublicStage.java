package com.llmeval.relay.engine;

/** What a runner is allowed to see: the puzzle, and nothing else. */
public record PublicStage(String id, String family, String prompt) {}
