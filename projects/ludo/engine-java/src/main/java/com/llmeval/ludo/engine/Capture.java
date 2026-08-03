package com.llmeval.ludo.engine;

/** What a move knocked out: whose token, which one, and on which absolute square. */
public record Capture(Color victim, int victimToken, int square) {}
