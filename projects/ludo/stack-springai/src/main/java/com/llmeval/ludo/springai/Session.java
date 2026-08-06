package com.llmeval.ludo.springai;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import org.h2.jdbcx.JdbcDataSource;
import org.springframework.ai.chat.memory.ChatMemoryRepository;
import org.springframework.ai.chat.memory.repository.jdbc.JdbcChatMemoryRepository;
import org.springframework.ai.chat.memory.repository.jdbc.JdbcChatMemoryRepositoryDialect;
import org.springframework.jdbc.core.JdbcTemplate;
import org.yaml.snakeyaml.Yaml;

import com.llmeval.ludo.engine.Color;
import com.llmeval.ludo.engine.Json;

/**
 * Opt-in session persistence: a directory where a game's agent-side state
 * survives the process. Off by default — games are independent experiments
 * unless someone deliberately decides otherwise (open question 18), the same
 * stance as the Strands stack.
 *
 * <p>Two stores with two owners, and the split is the capability-matrix
 * finding:
 *
 * <ul>
 *   <li><b>Conversations — the framework's.</b> Spring AI persists chat
 *       memory through its {@link ChatMemoryRepository} abstraction, and every
 *       shipped backend is a database (eight SQL dialects; no file store). Here
 *       that is {@link JdbcChatMemoryRepository} over an embedded H2 file —
 *       pure Java, no server, the file <em>is</em> the database. Because the
 *       repository is the memory's actual backing store, every exchange the
 *       advisor saves is written through as it happens: there is no sync
 *       moment to forget — the Strands finding (sync runs on the framework's
 *       schedule), inverted.
 *   <li><b>Beliefs — ours.</b> {@link Memory} never touches the framework
 *       (there is no {@code AgentState} equivalent to put it in), so the
 *       framework cannot persist it. {@code beliefs.json} is written by
 *       {@code Harness.persist()} in {@code play()}'s finally, and read back
 *       here at construction.
 * </ul>
 *
 * <p>Constructing a harness over a directory that already holds a session is
 * the restore: the repository reads the database on demand, and the beliefs
 * file is loaded before the first turn. No explicit load call exists or is
 * needed.
 *
 * <p>One more note for readers arriving from Spring Boot: Boot's
 * autoconfiguration would create the repository's table on startup. Without
 * Boot, {@link #ensureSchema} runs the module's own DDL — shipped inside the
 * jar as {@code schema-h2.sql} — the one piece of glue the starter would have
 * hidden.
 */
final class Session {

    private final Path dir;
    private final DataSource dataSource;
    private final JdbcTemplate jdbc;

    private Session(Path dir, DataSource dataSource, JdbcTemplate jdbc) {
        this.dir = dir;
        this.dataSource = dataSource;
        this.jdbc = jdbc;
    }

    static Session open(Path dir) {
        try {
            Files.createDirectories(dir);
        } catch (IOException e) {
            throw new UncheckedIOException("cannot create session directory " + dir, e);
        }
        JdbcDataSource dataSource = new JdbcDataSource();
        dataSource.setURL("jdbc:h2:file:"
                + dir.resolve("conversations").toAbsolutePath().toString().replace('\\', '/'));
        JdbcTemplate jdbc = new JdbcTemplate(dataSource);
        ensureSchema(jdbc);
        return new Session(dir, dataSource, jdbc);
    }

    /** The framework's persistence primitive, dialect auto-detected from the URL. */
    ChatMemoryRepository conversations() {
        return JdbcChatMemoryRepository.builder()
                .jdbcTemplate(jdbc)
                .dialect(JdbcChatMemoryRepositoryDialect.from(dataSource))
                .build();
    }

    private static void ensureSchema(JdbcTemplate jdbc) {
        Integer present = jdbc.queryForObject(
                "select count(*) from information_schema.tables where table_name = 'SPRING_AI_CHAT_MEMORY'",
                Integer.class);
        if (present != null && present > 0) return;
        try (InputStream in = JdbcChatMemoryRepository.class.getResourceAsStream("schema-h2.sql")) {
            String ddl = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            for (String statement : ddl.split(";")) {
                if (!statement.isBlank()) jdbc.execute(statement.strip());
            }
        } catch (IOException e) {
            throw new UncheckedIOException("cannot read the framework's schema-h2.sql", e);
        }
    }

    // -- beliefs: the half the framework has no place for -------------------

    @SuppressWarnings("unchecked")
    Map<Color, Memory> loadBeliefs() {
        Map<Color, Memory> restored = new EnumMap<>(Color.class);
        Path file = dir.resolve("beliefs.json");
        if (!Files.exists(file)) return restored;
        Map<String, Object> data;
        try {
            data = new Yaml().load(Files.readString(file, StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException("cannot read " + file, e);
        }
        for (Color color : Color.values()) {
            if (!(data.get(color.label()) instanceof Map<?, ?> entry)) continue;
            Memory memory = new Memory();
            if (entry.get("durable") instanceof List<?> facts) {
                for (Object fact : facts) memory.absorb(String.valueOf(fact));
            }
            if (entry.get("notes") instanceof List<?> notes) {
                // Replaying through write() re-applies the kind and text rules,
                // so a hand-edited file cannot smuggle in an invalid note.
                for (Object item : notes) {
                    if (!(item instanceof Map)) continue;
                    Map<String, Object> note = (Map<String, Object>) item;
                    memory.write(String.valueOf(note.get("text")),
                            note.get("turn") instanceof Number n ? n.intValue() : 0,
                            (String) note.get("kind"),
                            (String) note.get("about"));
                }
            }
            restored.put(color, memory);
        }
        return restored;
    }

    void saveBeliefs(Map<Color, Memory> memories) {
        Map<String, Object> out = new LinkedHashMap<>();
        for (Color color : Color.values()) {
            Memory memory = memories.get(color);
            List<Map<String, Object>> notes = new ArrayList<>();
            for (Memory.Note note : memory.notes()) {
                Map<String, Object> n = new LinkedHashMap<>();
                n.put("kind", note.kind());
                n.put("text", note.text());
                n.put("turn", note.turn());
                n.put("about", note.about());
                notes.add(n);
            }
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("durable", memory.durable());
            entry.put("notes", notes);
            out.put(color.label(), entry);
        }
        try {
            Files.writeString(dir.resolve("beliefs.json"), Json.compact(out), StandardCharsets.UTF_8);
        } catch (IOException e) {
            throw new UncheckedIOException("cannot write beliefs.json", e);
        }
    }
}
