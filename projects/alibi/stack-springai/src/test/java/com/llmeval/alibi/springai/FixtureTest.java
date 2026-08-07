package com.llmeval.alibi.springai;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.Test;

/** ADR-0007's rule: the committed fixture regenerates byte-identically. */
class FixtureTest {

    private static final Path FIXTURE = Path.of("../games/scripted-springai-seed7.jsonl");

    @Test
    void demoRegeneratesTheCommittedFixture(@org.junit.jupiter.api.io.TempDir Path tmp)
            throws Exception {
        Path out = tmp.resolve("out.jsonl");
        Demo.main(new String[] {out.toString()});
        assertTrue(Files.exists(FIXTURE),
                "fixture missing — run the demo and commit its output");
        assertArrayEquals(Files.readAllBytes(FIXTURE), Files.readAllBytes(out));
    }
}
