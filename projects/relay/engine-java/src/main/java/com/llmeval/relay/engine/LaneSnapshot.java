package com.llmeval.relay.engine;

/** What everyone can see of one lane. No reasoning, no memory, no answers. */
public record LaneSnapshot(String color, int position, int ticks, int escalations,
                           boolean finished) {}
