package com.llmeval.relay.engine;

/**
 * A runner's own result history — the raw material for self-knowledge.
 *
 * <p>Which family it keeps missing is the one thing worth remembering in this game, and it is
 * derivable from here without any privileged information.
 */
public record AttemptRecord(int turn, String stage, String family, boolean escalated,
                            boolean correct) {}
