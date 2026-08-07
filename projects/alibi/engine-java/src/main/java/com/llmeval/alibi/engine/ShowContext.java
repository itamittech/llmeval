package com.llmeval.alibi.engine;

import java.util.List;

/** Handed to a compelled refuter. {@code options} are the named elements it holds. */
public record ShowContext(DetectiveView view, Color color, int turn, Color suggester,
                          Suggestion suggestion, List<String> options) {}
