package com.llmeval.alibi.springai;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

import org.yaml.snakeyaml.Yaml;

/**
 * Reads {@code shared/models.yaml}: seats from the shared profiles, budgets and
 * the archivist from the {@code alibi} section. Nothing here decides anything —
 * a stack that picked its own turn cap would be a stack the comparison cannot use.
 */
public final class ModelsConfig {

    public record Seat(int seat, String access, String provider, String model) {
        public boolean pinned() {
            return model != null && !model.isBlank() && !"TBD".equals(model);
        }
    }

    public record Budgets(int maxTurns, int maxSearchesPerTurn, int maxNoteChars,
                          int maxTokensPerGame) {}

    public record Archivist(String provider, String access, String model,
                            String retrievalProfile) {}

    private final String name;
    private final List<Seat> seats;
    private final Budgets budgets;
    private final Archivist archivist;

    private ModelsConfig(String name, List<Seat> seats, Budgets budgets, Archivist archivist) {
        this.name = name;
        this.seats = seats;
        this.budgets = budgets;
        this.archivist = archivist;
    }

    public String name() { return name; }

    public List<Seat> seats() { return seats; }

    public Budgets budgets() { return budgets; }

    public Archivist archivist() { return archivist; }

    /** Seat for one colour index, rotating with gameIndex (ADR-0006). */
    public Seat seatFor(int colorIndex, int gameIndex) {
        return seats.get((colorIndex + gameIndex) % seats.size());
    }

    @SuppressWarnings("unchecked")
    public static ModelsConfig load(String profile) {
        Path path = Prompts.repoRoot().resolve("shared/models.yaml");
        Map<String, Object> raw;
        try {
            raw = new Yaml().load(Files.readString(path, StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }

        Map<String, Object> profiles = (Map<String, Object>) raw.get("profiles");
        Map<String, Object> spec = (Map<String, Object>) profiles.get(profile);
        if (spec == null) {
            throw new IllegalArgumentException("no profile " + profile);
        }

        List<Seat> seats = new ArrayList<>();
        for (Map<String, Object> s : (List<Map<String, Object>>) spec.get("seats")) {
            seats.add(new Seat((int) s.get("seat"), (String) s.get("access"),
                    (String) s.get("provider"), (String) s.get("model")));
        }
        seats.sort(Comparator.comparingInt(Seat::seat));

        Map<String, Object> alibi = (Map<String, Object>) raw.get("alibi");
        Map<String, Object> b =
                (Map<String, Object>) ((Map<String, Object>) alibi.get("budgets")).get(profile);
        Budgets budgets = new Budgets((int) b.get("max_turns"),
                (int) b.get("max_searches_per_turn"), (int) b.get("max_note_chars"),
                (int) b.get("max_tokens_per_game"));

        Map<String, Object> a = (Map<String, Object>) alibi.get("archivist");
        Archivist archivist = new Archivist((String) a.get("provider"),
                (String) a.get("access"), (String) a.get("model"),
                (String) a.get("retrieval_profile"));

        return new ModelsConfig(profile, List.copyOf(seats), budgets, archivist);
    }
}
