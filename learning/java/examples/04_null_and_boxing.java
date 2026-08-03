/*
 * null, Integer vs int, and the == trap that bites at 128.
 *
 *     java learning/java/examples/04_null_and_boxing.java
 *
 * Board.toSquare returns `Integer`, not `int`, because "this token is not on
 * the shared circuit" has to be expressible. That one choice drags in boxing,
 * null checks, and a comparison bug that only appears for large values.
 *
 * Python counterpart: `int | None`, and `is None` vs `==`.
 */

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

public class NullAndBoxing {

    enum Color { RED, GREEN }

    /** Absolute circuit square, or null when the token is off the shared circuit. */
    static Integer toSquare(Color color, int position) {
        if (position < 0 || position > 50) {
            return null;              // base, home column, home: private to one colour
        }
        return ((color == Color.RED ? 0 : 13) + position) % 52;
    }

    public static void main(String[] args) {
        System.out.println("""
            int CANNOT BE NULL. Integer CAN.
            --------------------------------""");

        System.out.println("  toSquare(RED, 5)   = " + toSquare(Color.RED, 5));
        System.out.println("  toSquare(RED, -1)  = " + toSquare(Color.RED, -1) + "    <- in the base");
        System.out.println("  toSquare(RED, 56)  = " + toSquare(Color.RED, 56) + "    <- home");
        System.out.println();
        System.out.println("  `int` has no spare value to mean 'absent' - 0 is a real square.");
        System.out.println("  Python writes this as `int | None`; Java needs the boxed Integer.");
        System.out.println("  The cost is that every caller must now think about null.");

        System.out.println("""

            THE TRAP: == COMPARES REFERENCES
            --------------------------------""");

        Integer smallA = 100, smallB = 100;
        Integer bigA = 1000, bigB = 1000;

        System.out.println("  Integer 100  == Integer 100  -> " + (smallA == smallB));
        System.out.println("  Integer 1000 == Integer 1000 -> " + (bigA == bigB) + "   <- !!");
        System.out.println("  Integer 1000 .equals( 1000 ) -> " + bigA.equals(bigB));
        System.out.println();
        System.out.println("  Java caches boxed Integers from -128 to 127. Inside that range");
        System.out.println("  `==` accidentally works; outside it, the same code silently stops");
        System.out.println("  working. A bug that passes every small test is the worst kind.");
        System.out.println();
        System.out.println("  Board squares are 0..51, so `==` would have survived here -");
        System.out.println("  which is exactly why Moves.applyMove uses .equals() anyway.");
        System.out.println("  Correct-by-luck is not correct.");

        System.out.println("""

            UNBOXING THROWS
            ---------------""");

        Integer absent = toSquare(Color.RED, -1);
        try {
            int square = absent;                    // implicit absent.intValue()
            System.out.println("  unreachable " + square);
        } catch (NullPointerException e) {
            System.out.println("  `int square = toSquare(RED, -1);` -> NullPointerException");
            System.out.println("  Assigning a null Integer to an int calls .intValue() on null.");
        }
        System.out.println();
        System.out.println("  Python's equivalent is quieter and later: None flows onward until");
        System.out.println("  something tries to do arithmetic with it, often far from the cause.");

        System.out.println("""

            HOW THE ENGINE HANDLES IT
            -------------------------""");

        System.out.println("  Check first, then use:");
        for (int position : new int[] {5, -1}) {
            Integer square = toSquare(Color.RED, position);
            String verdict = (square != null && List.of(0, 8, 13, 21).contains(square))
                    ? "safe square"
                    : (square == null ? "off the shared circuit" : "capturable");
            System.out.printf("    position %-3d -> %-4s  %s%n", position, square, verdict);
        }
        System.out.println();
        System.out.println("  isSafe(Integer) takes the boxed type and folds the null check in,");
        System.out.println("  so callers do not each repeat it. Python's is_safe does the same.");

        System.out.println("""

            WHILE WE ARE HERE: EnumMap
            --------------------------""");

        Map<Color, int[]> tokens = new EnumMap<>(Color.class);
        for (Color c : Color.values()) {
            tokens.put(c, new int[] {-1, -1, -1, -1});
        }
        System.out.println("  " + tokens.keySet() + "  <- always in declaration order");
        System.out.println();
        System.out.println("  EnumMap is an array behind the scenes, keyed by ordinal. It is the");
        System.out.println("  natural stand-in for Python's dict[Color, list[int]], and its");
        System.out.println("  guaranteed ordering is load-bearing: the engine iterates colours");
        System.out.println("  in turn order, and a HashMap would scramble that.");
    }
}
