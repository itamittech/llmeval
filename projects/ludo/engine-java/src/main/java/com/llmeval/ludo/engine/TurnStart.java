package com.llmeval.ludo.engine;

/** Handed to {@link Decider#negotiate}, once per turn, before the first roll. */
public record TurnStart(StateView state, Color color, int turn) {}
