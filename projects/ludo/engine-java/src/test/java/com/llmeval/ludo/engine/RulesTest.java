package com.llmeval.ludo.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * The edge cases resolved in game-rules.md.
 *
 * <p>Both engines implement that document; neither is the authority. These mirror the Python
 * suite's rule tests so a divergence is caught here with a readable message, rather than as an
 * opaque digest mismatch twenty vectors later.
 */
class RulesTest {

    private static GameState state() {
        return new GameState();
    }

    @Test
    void onlyASixReleasesFromBase() {
        GameState s = state();
        for (int die = 1; die <= 5; die++) {
            assertTrue(Moves.legalMoves(s, Color.RED, die).isEmpty(), "die " + die);
        }
        List<Move> moves = Moves.legalMoves(s, Color.RED, 6);
        assertEquals(4, moves.size(), "one per token in base");
        assertEquals(new Move(0, Board.BASE, Board.START), moves.get(0));
    }

    @Test
    void movesAreOrderedByTokenIndex() {
        // The conformance vectors depend on this: FirstLegal takes element zero.
        GameState s = state();
        s.tokens(Color.RED)[0] = 10;
        s.tokens(Color.RED)[1] = 5;
        s.tokens(Color.RED)[2] = 20;

        List<Move> moves = Moves.legalMoves(s, Color.RED, 3);
        assertEquals(List.of(0, 1, 2), moves.stream().map(Move::token).toList());
    }

    @Test
    void homeNeedsAnExactRoll() {
        GameState s = state();
        s.tokens(Color.RED)[0] = 54; // two short of home

        assertTrue(Moves.legalMoves(s, Color.RED, 3).isEmpty(), "overshooting is not legal");
        List<Move> exact = Moves.legalMoves(s, Color.RED, 2);
        assertEquals(1, exact.size());
        assertEquals(Board.HOME, exact.get(0).to());
    }

    @Test
    void aTokenAtHomeNeverMovesAgain() {
        GameState s = state();
        s.tokens(Color.RED)[0] = Board.HOME;
        assertTrue(Moves.legalMoves(s, Color.RED, 1).stream().noneMatch(m -> m.token() == 0));
    }

    @Test
    void landingOnALoneOpponentCaptures() {
        GameState s = state();
        // Red position 5 -> absolute 5. Green needs absolute 5, i.e. green position 44.
        s.tokens(Color.RED)[0] = 4;
        s.tokens(Color.GREEN)[0] = 44;
        assertEquals(5, (int) Board.toSquare(Color.RED, 5));
        assertEquals(5, (int) Board.toSquare(Color.GREEN, 44));

        List<Capture> captures = Moves.applyMove(s, Color.RED, new Move(0, 4, 5));
        assertEquals(1, captures.size());
        assertEquals(Color.GREEN, captures.get(0).victim());
        assertEquals(Board.BASE, s.tokens(Color.GREEN)[0], "victim goes back to base");
        assertEquals(1, s.stats(Color.RED).capturesMade);
        assertEquals(1, s.stats(Color.GREEN).capturesSuffered);
    }

    @Test
    void noCaptureOnASafeSquare() {
        GameState s = state();
        // Absolute 8 is a safe square. Red reaches it from position 7 with a 1.
        s.tokens(Color.RED)[0] = 7;
        s.tokens(Color.GREEN)[0] = 47; // green position 47 -> absolute 8
        assertEquals(8, (int) Board.toSquare(Color.RED, 8));
        assertEquals(8, (int) Board.toSquare(Color.GREEN, 47));
        assertTrue(Board.SAFE_SQUARES.contains(8));

        List<Capture> captures = Moves.applyMove(s, Color.RED, new Move(0, 7, 8));
        assertTrue(captures.isEmpty(), "safe squares shelter the occupant");
        assertEquals(47, s.tokens(Color.GREEN)[0], "green did not move");
    }

    @Test
    void twoOpponentTokensBlockThePath() {
        GameState s = state();
        s.tokens(Color.RED)[0] = 0;
        // Green pair on absolute 3 == green position 42.
        s.tokens(Color.GREEN)[0] = 42;
        s.tokens(Color.GREEN)[1] = 42;
        assertEquals(3, (int) Board.toSquare(Color.GREEN, 42));

        assertTrue(Moves.legalMoves(s, Color.RED, 5).stream().noneMatch(m -> m.token() == 0),
                "cannot pass a block");
        assertTrue(Moves.legalMoves(s, Color.RED, 3).stream().noneMatch(m -> m.token() == 0),
                "cannot land on a block either");
        assertFalse(Moves.legalMoves(s, Color.RED, 2).isEmpty(), "stopping short is fine");
    }

    @Test
    void ownTokensNeverBlockTheirOwner() {
        GameState s = state();
        s.tokens(Color.RED)[0] = 0;
        s.tokens(Color.RED)[1] = 3;
        s.tokens(Color.RED)[2] = 3;
        assertFalse(Moves.legalMoves(s, Color.RED, 3).stream().noneMatch(m -> m.token() == 0));
    }

    @Test
    void threeSixesCancelTheWholeTurn() {
        EventSink.ListSink sink = new EventSink.ListSink();
        Game game = Fixtures.gameWithDice(new GameConfig(1, 1), sink, new int[] {6, 6, 6}, 1);
        game.play(Fixtures.allOf(new FirstLegal()));

        assertEquals(0, game.state().progress(Color.RED), "everything the turn did was reverted");
        String lastTurnEnd = sink.events().stream()
                .filter(e -> "turn_ended".equals(e.get("type")))
                .map(e -> {
                    @SuppressWarnings("unchecked")
                    var payload = (java.util.Map<String, Object>) e.get("payload");
                    return (String) payload.get("reason");
                })
                .findFirst().orElseThrow();
        assertEquals("three_sixes", lastTurnEnd);
    }

    @Test
    void colourRelativePositionsMapToTheSharedCircuit() {
        assertEquals(0, (int) Board.toSquare(Color.RED, 0));
        assertEquals(13, (int) Board.toSquare(Color.GREEN, 0));
        assertEquals(26, (int) Board.toSquare(Color.YELLOW, 0));
        assertEquals(39, (int) Board.toSquare(Color.BLUE, 0));

        // Off the shared circuit: private to one colour, so no absolute square.
        assertEquals(null, Board.toSquare(Color.RED, Board.BASE));
        assertEquals(null, Board.toSquare(Color.RED, Board.HOME_ENTRY));
        assertEquals(null, Board.toSquare(Color.RED, Board.HOME));
    }

    @Test
    void progressCountsBaseAsZeroAndHomeAsFiftySeven() {
        assertEquals(0, Board.tokenProgress(Board.BASE));
        assertEquals(1, Board.tokenProgress(Board.START));
        assertEquals(57, Board.tokenProgress(Board.HOME));

        GameState s = state();
        assertEquals(0, s.progress(Color.RED));
        for (int i = 0; i < Board.TOKENS_PER_PLAYER; i++) {
            s.tokens(Color.RED)[i] = Board.HOME;
        }
        assertEquals(228, s.progress(Color.RED), "4 x 57");
        assertTrue(s.hasFinished(Color.RED));
    }

    @Test
    void snapshotCopiesRatherThanAliases() {
        GameState s = state();
        Snapshot before = s.snapshot();
        s.tokens(Color.RED)[0] = 10;
        s.stats(Color.RED).capturesMade = 3;

        s.restore(before);
        assertEquals(Board.BASE, s.tokens(Color.RED)[0]);
        assertEquals(0, s.stats(Color.RED).capturesMade);
    }
}
