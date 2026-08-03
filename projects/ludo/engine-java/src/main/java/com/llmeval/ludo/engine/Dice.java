package com.llmeval.ludo.engine;

/**
 * Portable seeded PRNG — xorshift64* seeded through splitmix64.
 *
 * <p>The engine specifies its own generator rather than using {@code java.util.Random} for the
 * same reason the Python engine avoids {@code random}: the two must produce identical sequences
 * from the same seed, and no language's built-in generator is specified compatibly with
 * another's.
 *
 * <p><strong>The trap this class exists to avoid:</strong> Python integers are
 * arbitrary-precision and need an explicit {@code & MASK64} after every multiply and shift;
 * Java's {@code long} wraps for free, so those masks simply disappear. But Java's {@code >>} is
 * <em>arithmetic</em> — it copies the sign bit — while Python is masking an unsigned value. Every
 * right shift here must be {@code >>>}. One {@code >>} and every conformance vector fails, which
 * is exactly what the vectors are for.
 */
public final class Dice {

    private static final long MULTIPLIER = 0x2545F4914F6CDD1DL;
    private static final long GOLDEN_GAMMA = 0x9E3779B97F4A7C15L;

    private final int seed;
    private long state;
    private int rolls;

    public Dice(int seed) {
        this.seed = seed;
        long s = splitmix64(seed);
        // A zero state would make xorshift emit zeros forever; the Python engine
        // substitutes the same constant.
        this.state = (s == 0) ? GOLDEN_GAMMA : s;
    }

    /** Scrambles a small, low-entropy seed into a well-distributed 64-bit state. */
    static long splitmix64(long seed) {
        long z = seed + GOLDEN_GAMMA;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    /** One die face, 1..6. */
    public int roll() {
        long x = state;
        x ^= x >>> 12;
        x ^= x << 25;
        x ^= x >>> 27;
        state = x;
        rolls++;
        return (int) (((x * MULTIPLIER) >>> 33) % 6) + 1;
    }

    public int seed() {
        return seed;
    }

    public int rolls() {
        return rolls;
    }
}
