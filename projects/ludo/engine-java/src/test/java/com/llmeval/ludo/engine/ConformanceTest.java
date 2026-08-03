package com.llmeval.ludo.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * The test that matters most: this engine must agree with the Python one.
 *
 * <p>ADR-0002 chose one engine per language over one per stack, on the condition that shared
 * vectors keep them honest. This is where that condition is enforced.
 */
class ConformanceTest {

    private static final Path VECTORS =
            Path.of("..", "..", "..", "shared", "conformance", "vectors.json");

    @SuppressWarnings("unchecked")
    private static Map<String, Object> vectors() throws Exception {
        assertTrue(Files.exists(VECTORS), "vectors not found at " + VECTORS.toAbsolutePath());
        return (Map<String, Object>) Json.parse(Files.readString(VECTORS, StandardCharsets.UTF_8));
    }

    @Test
    void everyVectorReproduces() throws Exception {
        List<String> failures = Conformance.check(vectors());
        assertTrue(failures.isEmpty(), () -> String.join("\n", failures));
    }

    @Test
    void aTamperedVectorIsDetected() throws Exception {
        // A check nobody has watched fail proves nothing.
        Map<String, Object> tampered = vectors();
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> list = (List<Map<String, Object>>) tampered.get("vectors");
        list.get(0).put("digest", "0".repeat(64));

        List<String> failures = Conformance.check(tampered);
        assertEquals(1, failures.size(), failures.toString());
        assertTrue(failures.get(0).contains("digest"));
    }

    @Test
    void engineIdentityIsExcludedFromTheDigest() {
        // The whole reason the vectors had to change when this engine arrived: game_started
        // records which engine produced the transcript, and that field is *required* to differ.
        EventSink.ListSink sink = new EventSink.ListSink();
        new Game(new GameConfig(3, 60), sink).play(Fixtures.firstLegal());

        Map<String, Object> started = sink.events().get(0);
        assertEquals("game_started", started.get("type"));

        @SuppressWarnings("unchecked")
        Map<String, Object> payload = (Map<String, Object>) started.get("payload");
        assertTrue(payload.containsKey("engine"), "the event still carries engine identity");

        @SuppressWarnings("unchecked")
        Map<String, Object> forDigest =
                (Map<String, Object>) Conformance.forDigest(started).get("payload");
        assertTrue(!forDigest.containsKey("engine"), "but the digest does not see it");
        assertEquals(payload.get("seed"), forDigest.get("seed"), "everything else survives");
    }
}
