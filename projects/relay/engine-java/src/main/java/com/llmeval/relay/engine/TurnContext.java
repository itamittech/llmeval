package com.llmeval.relay.engine;

/** Everything a runner gets when asked for a move. {@code attempt} is 1, then 2 after a rejection. */
public record TurnContext(RunnerView view, String color, int turn, EscalationDesk desk,
                          int attempt) {}
