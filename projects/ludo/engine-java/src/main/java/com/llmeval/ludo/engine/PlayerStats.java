package com.llmeval.ludo.engine;

/**
 * Running counters for one colour.
 *
 * <p>Mutable, matching the Python {@code @dataclass}: the engine increments these in place as a
 * game runs, and a three-sixes cancellation reverts them via {@link Snapshot}.
 */
public final class PlayerStats {

    public int capturesMade;
    public int capturesSuffered;
    public int turnsForfeited;

    public PlayerStats() {
        this(0, 0, 0);
    }

    public PlayerStats(int capturesMade, int capturesSuffered, int turnsForfeited) {
        this.capturesMade = capturesMade;
        this.capturesSuffered = capturesSuffered;
        this.turnsForfeited = turnsForfeited;
    }

    /** A detached copy — mutating the result changes nothing. */
    public PlayerStats copy() {
        return new PlayerStats(capturesMade, capturesSuffered, turnsForfeited);
    }
}
