package com.llmeval.relay.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * The point of two engines: they must agree, or the comparison built on them means nothing.
 *
 * <p>This is the whole ADR-0002 guarantee in one assertion, and for RELAY it covers more than
 * mechanics — every generated stage prompt is inside the digest, and the bot's answers come from
 * parsing those prompts, so a divergence in either shows up here.
 */
class ConformanceTest {

    @Test
    void javaEngineMatchesEveryCommittedVector() throws IOException {
        List<String> failures = Conformance.check();
        assertTrue(failures.isEmpty(), String.join("\n", failures));
    }

    @Test
    void vectorsAreReproducible() {
        assertEquals(Conformance.runVector(7, Conformance.DEFAULT_MAX_TURNS),
                Conformance.runVector(7, Conformance.DEFAULT_MAX_TURNS));
    }

    @Test
    void engineLanguageIsExcludedFromTheDigest() {
        // Same event, different engine block: the digest must not notice.
        assertEquals(Conformance.digest(List.of(startedIn("python"))),
                Conformance.digest(List.of(startedIn("java"))));
    }

    private static Map<String, Object> startedIn(String language) {
        return Map.of("seq", 0, "turn", 0, "type", "game_started",
                "payload", Map.of("seed", 1,
                        "engine", Map.of("language", language, "version", "0.1.0")));
    }
}
