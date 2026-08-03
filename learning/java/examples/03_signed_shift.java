/*
 * >> vs >>> — the bug that would have broken every conformance vector.
 *
 *     java learning/java/examples/03_signed_shift.java
 *
 * This is not a hypothetical. The engine's dice had to reproduce Python's
 * sequence exactly, and one wrong character here changes every roll of every
 * game. It is the sharpest thing in the whole port.
 *
 * Python counterpart: dice.py, where the same algorithm needs `& MASK64` after
 * every operation and has no signed-shift problem at all.
 */

public class SignedShift {

    private static final long MULTIPLIER = 0x2545F4914F6CDD1DL;
    private static final long GOLDEN_GAMMA = 0x9E3779B97F4A7C15L;

    static long splitmix64(long seed) {
        long z = seed + GOLDEN_GAMMA;
        z = (z ^ (z >>> 30)) * 0xBF58476D1CE4E5B9L;
        z = (z ^ (z >>> 27)) * 0x94D049BB133111EBL;
        return z ^ (z >>> 31);
    }

    /** Correct: every right shift is unsigned. */
    static String rollsCorrect(int seed, int count) {
        long state = splitmix64(seed);
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < count; i++) {
            long x = state;
            x ^= x >>> 12;
            x ^= x << 25;
            x ^= x >>> 27;
            state = x;
            out.append((int) (((x * MULTIPLIER) >>> 33) % 6) + 1);
        }
        return out.toString();
    }

    /** One character different. Compiles, runs, produces plausible dice. */
    static String rollsBroken(int seed, int count) {
        long state = splitmix64(seed);
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < count; i++) {
            long x = state;
            x ^= x >>> 12;
            x ^= x << 25;
            x ^= x >> 27;          // <-- signed. THE BUG.
            state = x;
            out.append((int) (((x * MULTIPLIER) >>> 33) % 6) + 1);
        }
        return out.toString();
    }

    public static void main(String[] args) {
        System.out.println("""
            WHAT THE TWO OPERATORS DO
            -------------------------""");

        long negative = -8L;
        System.out.printf("  n        = %d%n", negative);
        System.out.printf("  n >>  1  = %d   <- arithmetic: copies the sign bit in%n", negative >> 1);
        System.out.printf("  n >>> 1  = %d   <- logical: shifts a 0 in%n", negative >>> 1);
        System.out.println();
        System.out.println("  Every Java `long` is SIGNED. There is no unsigned long type, so");
        System.out.println("  the top bit means 'negative' whether you meant it to or not.");
        System.out.println();
        System.out.println("  Python has neither problem and neither operator. Its integers are");
        System.out.println("  arbitrary-precision and never negative unless you make them, so");
        System.out.println("  dice.py masks with & MASK64 instead - and `>>` is always logical.");

        System.out.println("""

            THE SAME ALGORITHM, ONE CHARACTER APART
            ---------------------------------------""");

        // Produced by the Python engine. The Java engine must match these.
        String[][] expected = {
            {"1", "134624356524"},
            {"7", "564654553452"},
            {"42", "654544633226"},
        };

        System.out.printf("  %-6s %-14s %-14s %s%n", "seed", "python", "java >>>", "java >>");
        for (String[] row : expected) {
            int seed = Integer.parseInt(row[0]);
            String correct = rollsCorrect(seed, 12);
            String broken = rollsBroken(seed, 12);
            System.out.printf("  %-6s %-14s %-14s %s%n", seed, row[1], correct, broken);
            if (!correct.equals(row[1])) {
                throw new AssertionError("the correct version stopped matching Python");
            }
        }

        System.out.println();
        System.out.println("  Look at the third column against the second: identical.");
        System.out.println("  Look at the fourth: plausible dice, wrong game.");

        System.out.println("""

            WHY THIS IS THE INTERESTING BUG
            -------------------------------
            It does not crash. It does not warn. Every value is still 1..6, the
            distribution still looks uniform, and a game played with the broken
            version is a perfectly sensible game of Ludo.

            It is simply a DIFFERENT game from the one Python plays - so the two
            engines silently stop being the same engine, which is the one thing
            ADR-0002 exists to prevent.

            That is why the conformance vectors hash every event rather than
            spot-checking a few outcomes, and why DiceTest pins four sequences
            directly: a digest mismatch tells you something broke, but a failing
            DiceTest tells you WHAT.""");

        System.out.println("""

            THE HABIT WORTH TAKING AWAY
            ---------------------------
            In Java, `>>` on a value you are treating as unsigned is almost
            always a bug. Hashes, PRNGs, checksums, bit-packed ids - if the top
            bit can ever be set, use `>>>`.""");
    }
}
