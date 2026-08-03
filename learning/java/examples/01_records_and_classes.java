/*
 * Records vs classes — and what "frozen" does and doesn't mean.
 *
 *     java learning/java/examples/01_records_and_classes.java
 *
 * The engine uses both. Move and Capture are records; GameState and PlayerStats
 * are ordinary mutable classes. That split is deliberate, and this file shows
 * why it matters rather than asserting it.
 *
 * Python counterpart: @dataclass(frozen=True) and @dataclass.
 */

import java.util.HashSet;
import java.util.Set;

public class RecordsAndClasses {

    // One line. You get a constructor, accessors, equals, hashCode and toString.
    record Move(int token, int frm, int to) {}

    // The mutable half of the engine. No record, because the whole point is
    // that a turn changes it.
    static final class Stats {
        int capturesMade;

        Stats(int capturesMade) {
            this.capturesMade = capturesMade;
        }
    }

    public static void main(String[] args) {
        System.out.println("""
            RECORDS: value semantics for free
            ---------------------------------""");

        Move a = new Move(0, -1, 0);
        Move b = new Move(0, -1, 0);

        System.out.println("  a         = " + a);
        System.out.println("  a == b    = " + (a == b) + "   <- different objects");
        System.out.println("  a.equals(b) = " + a.equals(b) + "   <- same VALUE");
        System.out.println();
        System.out.println("  In Java `==` on objects asks 'same object?', never 'same value?'.");
        System.out.println("  Python's `==` calls __eq__, so it means the opposite by default.");
        System.out.println("  Python's `is` is the one that matches Java's `==`.");

        System.out.println("""

            WHY THE ENGINE NEEDS THIS
            -------------------------""");

        // Game validates an agent's choice with a set membership test. That only
        // works because Move has value equality AND a matching hashCode - both
        // of which the record generated.
        Set<Move> legal = new HashSet<>();
        legal.add(new Move(0, -1, 0));
        legal.add(new Move(1, 5, 9));

        Move agentChose = new Move(1, 5, 9);      // a fresh object from elsewhere
        System.out.println("  legal.contains(agentChose) = " + legal.contains(agentChose));
        System.out.println("  An agent constructs its own Move; the engine still recognises it.");
        System.out.println("  Written as a plain class without equals/hashCode, this would be");
        System.out.println("  false, and every legal move would be rejected as illegal.");

        System.out.println("""

            "FROZEN" IS SHALLOW - in both languages
            ---------------------------------------""");

        record Holder(Stats stats) {}
        Holder h = new Holder(new Stats(0));

        System.out.println("  before: h.stats().capturesMade = " + h.stats().capturesMade);
        h.stats().capturesMade = 99;              // the record field cannot be reassigned...
        System.out.println("  after : h.stats().capturesMade = " + h.stats().capturesMade);
        System.out.println();
        System.out.println("  `h.stats = ...` would not compile. Mutating what it POINTS AT is");
        System.out.println("  fine. Same trap as Python's frozen dataclass holding a list.");
        System.out.println("  It is why GameState.snapshot() copies rather than storing a");
        System.out.println("  reference - without the copy, three-sixes rollback does nothing.");

        System.out.println("""

            THE ENGINE'S SPLIT
            ------------------
              record  Move, Capture, Snapshot, TurnStart, TurnContext, TurnEnd
              class   GameState, PlayerStats, Dice, Game

            Read it as a question: does a turn change this? If yes, it cannot be
            a record. If no, a record says so in a way the compiler enforces.""");
    }
}
