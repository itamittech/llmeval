/*
 * Interfaces vs Protocols — the difference that changes what the repo can do.
 *
 *     java learning/java/examples/02_interfaces_and_defaults.java
 *
 * This is the single most important thing in the port, and it is not a style
 * preference. It decides whether an agent package has to depend on the engine.
 *
 * Python counterpart: typing.Protocol, and @runtime_checkable.
 */

public class InterfacesAndDefaults {

    // The engine's contract. In Python this is a Protocol; here it is an
    // interface, and that one word changes the dependency graph.
    interface Decider {
        String name();

        int choose(int[] legalMoves);

        // OPTIONAL hooks. A default method is Java's answer to Python's
        // "the engine calls it if the object happens to have it".
        default void negotiate(int turn) {}

        default void reflect(String reason) {}
    }

    /** A bot: implements the required method, ignores both hooks. */
    static final class FirstLegal implements Decider {
        public String name() { return "first-legal"; }
        public int choose(int[] legalMoves) { return legalMoves[0]; }
    }

    /** An agent: opts into the hooks by overriding them. */
    static final class TalkativeAgent implements Decider {
        public String name() { return "talkative"; }
        public int choose(int[] legalMoves) { return legalMoves[legalMoves.length - 1]; }

        @Override public void negotiate(int turn) {
            System.out.println("    [turn " + turn + "] proposing an alliance");
        }
        @Override public void reflect(String reason) {
            System.out.println("    noting: the turn ended with " + reason);
        }
    }

    /**
     * Looks exactly like a Decider. Is not one.
     *
     * In Python this class WOULD satisfy the Protocol — shape is all that is
     * checked. Here it satisfies nothing, because it never wrote `implements`.
     */
    static final class LooksRight {
        public String name() { return "impostor"; }
        public int choose(int[] legalMoves) { return legalMoves[0]; }
    }

    static void runTurn(Decider decider, int turn) {
        System.out.println("  " + decider.name() + ":");
        decider.negotiate(turn);                       // once per TURN
        int picked = decider.choose(new int[] {0, 1, 2});
        System.out.println("    chose move index " + picked);
        decider.reflect("moved");                      // once per TURN
    }

    public static void main(String[] args) {
        System.out.println("""
            DEFAULT METHODS: optional without being absent
            ----------------------------------------------""");

        runTurn(new FirstLegal(), 1);
        runTurn(new TalkativeAgent(), 2);

        System.out.println();
        System.out.println("  FirstLegal printed nothing for negotiate/reflect. It did not");
        System.out.println("  skip them - it inherited empty implementations. The engine calls");
        System.out.println("  all three unconditionally and never asks which exist.");

        System.out.println("""

            THE PART THAT MATTERS
            ---------------------""");

        LooksRight impostor = new LooksRight();
        System.out.println("  LooksRight has name() and choose() with the right signatures.");
        System.out.println("  It calls fine on its own: " + impostor.name());
        System.out.println();
        System.out.println("  Is it a Decider? Java will not even let you ASK. Both of these");
        System.out.println("  are compile errors, not `false`:");
        System.out.println();
        System.out.println("      runTurn(impostor, 3);");
        System.out.println("      //  error: incompatible types: LooksRight cannot be");
        System.out.println("      //         converted to Decider");
        System.out.println();
        System.out.println("      impostor instanceof Decider");
        System.out.println("      //  same error - the compiler knows a final class that does");
        System.out.println("      //  not implement Decider can never be one, so the question");
        System.out.println("      //  itself is rejected");
        System.out.println();
        System.out.println("  (Try uncommenting the marked line below and re-running.)");
        System.out.println();

        // UNCOMMENT ME to see it fail:
        // runTurn(impostor, 3);

        System.out.println("  In Python the equivalent class satisfies the Protocol outright.");
        System.out.println("  No import, no inheritance, no compile-time link between the");
        System.out.println("  engine package and the agent package.");

        System.out.println("""

            WHY THE REPO CARES
            ------------------
            Python: an agent is a Decider by SHAPE.
              -> stack-strands and stack-langgraph share one engine while keeping
                 genuinely separate dependency trees. Neither imports the other,
                 and neither needs the engine on a compile classpath.

            Java: an agent is a Decider by DECLARATION.
              -> every Spring AI agent must have ludo-engine on its classpath,
                 and a change to the interface is a recompile for that stack and
                 a no-op for the Python ones.

            Nothing breaks. But the isolation the Python stacks get for free has
            to be arranged deliberately on the JVM - which is exactly the kind of
            difference the capability matrix exists to record.""");

        System.out.println("""

            ONE MORE ASYMMETRY
            ------------------
            Python can also check shape at RUNTIME:

                @runtime_checkable
                class Negotiator(Protocol):
                    def negotiate(self, start) -> None: ...

                isinstance(decider, Negotiator)   # "does it have the method?"

            That asks about method NAMES only - it never checks the signature,
            so an object with a wrongly-shaped negotiate passes the check and
            then fails when called. Java's default methods sidestep the question
            entirely: the method always exists, so there is nothing to test.""");
    }
}
