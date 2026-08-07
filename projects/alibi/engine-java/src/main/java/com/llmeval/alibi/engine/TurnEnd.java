package com.llmeval.alibi.engine;

import java.util.List;
import java.util.Map;

/** Handed to an optional reflector after its own turn resolves. */
public record TurnEnd(DetectiveView view, Color color, int turn, String reason,
                      List<Map<String, Object>> events) {}
