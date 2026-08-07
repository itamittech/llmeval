package com.llmeval.alibi.engine;

import java.util.ArrayList;
import java.util.List;

/**
 * Portable seeded randomness — xorshift64* seeded through splitmix64, widened from LUDO's die to
 * "pick below n" and a specified Fisher–Yates shuffle.
 *
 * <p>The draw order is spec, not implementation detail: the Python engine shuffles from the last
 * index down to 1, drawing {@code below(i + 1)} each step, and this class must consume the same
 * draws in the same order or every case — deal, archive, red herrings — diverges at once.
 *
 * <p><strong>The Java trap, same as LUDO's Dice:</strong> every right shift here must be
 * {@code >>>}. Java's {@code >>} copies the sign bit; Python is masking an unsigned value. One
 * {@code >>} and every conformance vector fails, which is exactly what the vectors are for.
 */
public final class Rng {

    private static final long MULTIPLIER = 0x2545F4914F6CDD1DL;
    private static final long GOLDEN_GAMMA = 0x9E3779B97F4A7C15L;

    private long state;

    public Rng(long seed) {
        long s = splitmix64(seed);
        this.state = (s == 0) ? GOLDEN_GAMMA : s;
    }

    static long splitmix64(long seed) {
        long z = seed + GOLDEN_GAMMA;
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
        return (int) (((x * MULTIPLIER) >>> 33) % n);
    }

    /** In-place Fisher–Yates, high index down — iteration order is spec. */
    public <T> void shuffle(List<T> items) {
        for (int i = items.size() - 1; i > 0; i--) {
            int j = below(i + 1);
            T tmp = items.get(i);
            items.set(i, items.get(j));
            items.set(j, tmp);
        }
    }

    /** First k of a shuffled copy. Order of the result is the shuffle's. */
    public <T> List<T> sample(List<T> items, int k) {
        List<T> pool = new ArrayList<>(items);
        shuffle(pool);
        return new ArrayList<>(pool.subList(0, k));
    }
}
