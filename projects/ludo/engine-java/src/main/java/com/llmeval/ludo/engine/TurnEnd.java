package com.llmeval.ludo.engine;

import java.util.List;
import java.util.Map;

/**
 * Handed to {@link Decider#reflect}, once per turn, after it resolves.
 *
 * @param reason same value as the {@code turn_ended} event: moved, no_legal_move, illegal_move,
 *               or three_sixes
 * @param events every engine event emitted during this turn, {@code turn_started} through
 *               {@code turn_ended}. Agent-layer events are not here — an agent already knows what
 *               it said.
 */
public record TurnEnd(
        StateView state,
        Color color,
        int turn,
        String reason,
        List<Map<String, Object>> events) {}
