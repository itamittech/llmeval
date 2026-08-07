package com.llmeval.relay.engine;

import java.util.ArrayList;
import java.util.List;

/**
 * Portable seeded randomness — splitmix64 seeding over xorshift64*.
 *
 * <p>Must reproduce {@code relay_engine/rng.py} draw for draw. Java's {@code long} is signed and
 * Python's ints are unbounded, so every shift here is the <em>unsigned</em> {@code >>>}: a signed
 * {@code >>} would sign-extend and the two engines would diverge on roughly half of all states,
 * silently, and only for some seeds.
 *
 * <p>Two iteration orders are part of the spec rather than implementation detail. {@link #shuffle}
 * runs from the last index down to 1. {@link #sample} shuffles a copy of the <em>whole</em> pool
 * and takes the first k, consuming {@code pool.size() - 1} draws rather than k — a port that drew
 * k times would produce a different track from the same seed.
 */
public final class Rng {

    private static final long MULTIPLIER = 0x2545F4914F6CDD1DL;

    private final long seed;
    private long state;

    public Rng(long seed) {
        this.seed = seed;
        long start = splitmix64(seed);
        // xorshift64* cannot recover from an all-zero state.
        this.state = start == 0 ? 0x9E3779B97F4A7C15L : start;
    }

    public long seed() {
        return seed;
    }

    static long splitmix64(long seed) {
        long z = seed + 0x9E3779B97F4A7C15L;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    /** Uniform integer in [0, n). */
    public int below(int n) {
        if (n <= 0) {
            throw new IllegalArgumentException("n must be positive");
        }
        long x = state;
        x ^= x >>> 12;
        x ^= x << 25;
        x ^= x >>> 27;
        state = x;
        // >>> 33 leaves 31 bits, so the value is non-negative and the modulo is plain int work.
        return (int) (((x * MULTIPLIER) >>> 33) % n);
    }

    /** Uniform integer in [low, high]. */
    public int between(int low, int high) {
        return low + below(high - low + 1);
    }

    /** In-place Fisher-Yates, high index down — iteration order is spec. */
    public <T> void shuffle(List<T> items) {
        for (int i = items.size() - 1; i > 0; i--) {
            int j = below(i + 1);
            T swap = items.get(i);
            items.set(i, items.get(j));
            items.set(j, swap);
        }
    }

    /** First k of a shuffled copy. Order of the result is the shuffle's. */
    public <T> List<T> sample(List<T> items, int k) {
        List<T> pool = new ArrayList<>(items);
        shuffle(pool);
        return new ArrayList<>(pool.subList(0, k));
    }
}
