package com.llmeval.relay.springai;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** The committed fixture must be exactly what the demo produces. */
class FixtureTest {

    private static Path fixture() {
        return Prompts.repoRoot().resolve("projects/relay/games/scripted-springai-seed7.jsonl");
    }

    @Test
    void theFixtureIsCommitted() {
        assertTrue(Files.exists(fixture()),
                "run: ./mvnw -q -B compile exec:java "
                + "-Dexec.args=\"../games/scripted-springai-seed7.jsonl\"");
    }

    @Test
    void theDemoRegeneratesItByteForByte(@TempDir Path tmp) throws IOException {
        Path out = tmp.resolve("regenerated.jsonl");
        Demo.main(new String[] {out.toString()});
        assertArrayEquals(Files.readAllBytes(fixture()), Files.readAllBytes(out));
    }
}
