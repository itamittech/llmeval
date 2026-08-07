package com.llmeval.relay.engine;

import java.util.List;

/**
 * A read-only, single-lane window onto the race.
 *
 * <p>What is absent is the point: no stage here carries a tier or an answer, because judging
 * difficulty unaided is the move the game is made of. A record with unmodifiable lists gives the
 * same guarantee Python's {@code __slots__} + {@code __setattr__} guard gives on the other side.
 */
public record RunnerView(String color, PublicStage stage, int position, int ticks,
                         int trackLength, int quotaLeft, List<LaneSnapshot> lanes,
                         List<NoteRecord> notes, List<AttemptRecord> ownHistory) {

    public RunnerView {
        lanes = List.copyOf(lanes);
        notes = List.copyOf(notes);
        ownHistory = List.copyOf(ownHistory);
    }
}
