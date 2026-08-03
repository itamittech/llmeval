package com.llmeval.ludo.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * The dice are the sharpest porting trap, so they get pinned directly rather than only through
 * the conformance vectors.
 *
 * <p>The expected sequences below were produced by the Python engine. One {@code >>} where a
 * {@code >>>} belongs and every one of them changes.
 */
class DiceTest {

    private static String firstRolls(int seed, int count) {
        Dice dice = new Dice(seed);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < count; i++) {
            sb.append(dice.roll());
        }
        return sb.toString();
    }

    @Test
    void matchesThePythonEngineExactly() {
        assertEquals("134624356524", firstRolls(1, 12));
        assertEquals("564654553452", firstRolls(7, 12));
        assertEquals("654544633226", firstRolls(42, 12));
        assertEquals("353216266332", firstRolls(2026, 12));
    }

    @Test
    void sameSeedReplaysExactly() {
        assertEquals(firstRolls(99, 50), firstRolls(99, 50));
    }

    @Test
    void differentSeedsDiverge() {
        assertTrue(!firstRolls(1, 30).equals(firstRolls(2, 30)));
    }

    @Test
    void everyFaceAppearsAndRoughlyEvenly() {
        Map<Integer, Integer> counts = new HashMap<>();
        Dice dice = new Dice(7);
        int n = 60_000;
        for (int i = 0; i < n; i++) {
            int face = dice.roll();
            assertTrue(face >= 1 && face <= 6, "face out of range: " + face);
            counts.merge(face, 1, Integer::sum);
        }
        assertEquals(6, counts.size());
        for (int face = 1; face <= 6; face++) {
            int count = counts.get(face);
            // Wide bound: this is a smoke test for a stuck generator, not a statistical claim.
            assertTrue(count > n / 6 * 0.9 && count < n / 6 * 1.1,
                    "face " + face + " appeared " + count + " times");
        }
    }

    @Test
    void rollsAreCounted() {
        Dice dice = new Dice(5);
        for (int i = 0; i < 10; i++) {
            dice.roll();
        }
        assertEquals(10, dice.rolls());
        assertEquals(5, dice.seed());
    }
}
