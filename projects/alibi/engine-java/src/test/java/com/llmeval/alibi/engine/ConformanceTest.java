package com.llmeval.alibi.engine;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

/**
 * The decisive test: replay every vector the Python engine recorded — corpus bytes included —
 * and match every digest. One divergent comma in a template, one {@code >>} for a {@code >>>},
 * one draw out of order, and this fails with the seed that caught it.
 */
class ConformanceTest {

    private static final Path VECTORS =
            Path.of("../../../shared/conformance/alibi-vectors.json");

    @Test
    void matchesEveryPythonVector() throws Exception {
        assertTrue(Files.exists(VECTORS), "vectors file missing: " + VECTORS.toAbsolutePath());

        @SuppressWarnings("unchecked")
        Map<String, Object> expected =
                (Map<String, Object>) Json.parse(Files.readString(VECTORS, StandardCharsets.UTF_8));

        List<String> failures = Conformance.check(expected);
        assertEquals(List.of(), failures);
    }

    @Test
    void digestIsStableAcrossRuns() {
        Map<String, Object> a = Conformance.runVector(1, 60);
        Map<String, Object> b = Conformance.runVector(1, 60);
        assertEquals(a.get("digest"), b.get("digest"));
    }
}
