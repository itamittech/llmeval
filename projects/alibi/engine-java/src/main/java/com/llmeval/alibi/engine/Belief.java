package com.llmeval.alibi.engine;

import java.util.Map;

/**
 * A declared best guess with per-dimension confidence in [0, 1]. Bot confidences come from
 * {@link EliminationBot#CONFIDENCE} — a literal table, never division, because these values are
 * serialised onto the conformance path and the two languages must emit identical bytes.
 */
public record Belief(String who, String how, String where, Map<String, Double> confidence) {}
