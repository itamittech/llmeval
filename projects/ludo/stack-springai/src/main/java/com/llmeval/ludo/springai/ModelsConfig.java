package com.llmeval.ludo.springai;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.yaml.snakeyaml.Yaml;

import com.llmeval.ludo.engine.Color;

/**
 * Reads shared/models.yaml — seats, routes, budgets, profiles — and assigns
 * seats to colours per game. Must agree with the Python stacks' config.py on
 * every value and on the rotation rule (ADR-0006): the config is shared so the
 * experiment is, and a stack that read it differently would be a silent
 * parity break.
 */
public final class ModelsConfig {

    public record Seat(int seat, String access, String provider, String model) {
        public boolean pinned() {
            return model != null && !model.isBlank() && !"TBD".equals(model);
        }
    }

    public record Budgets(int maxTurns, int maxFloorPasses, int maxMessageChars,
                          int maxContextTokens, long maxTokensPerGame) {}

    public record Profile(String name, List<Seat> seats, Seat judge, Budgets budgets,
                          Map<String, Object> inference) {

        /** Provider-narrowed inference settings — top-level scalars plus that
         *  provider's own block, the same merge as config.py's inference_for. */
        @SuppressWarnings("unchecked")
        public Map<String, Object> inferenceFor(String provider) {
            Map<String, Object> merged = new LinkedHashMap<>();
            inference.forEach((key, value) -> {
                if (!(value instanceof Map)) merged.put(key, value);
            });
            Object block = inference.get(provider);
            if (block instanceof Map) merged.putAll((Map<String, Object>) block);
            return merged;
        }
    }

    private ModelsConfig() {}

    public static Profile load(String name) {
        return load(name, Prompts.repoRoot().resolve("shared/models.yaml"));
    }

    @SuppressWarnings("unchecked")
    public static Profile load(String name, Path path) {
        Map<String, Object> raw;
        try {
            raw = new Yaml().load(Files.readString(path, StandardCharsets.UTF_8));
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        Map<String, Object> profiles = (Map<String, Object>) raw.get("profiles");
        Map<String, Object> spec = (Map<String, Object>) profiles.get(name);
        if (spec == null) {
            throw new IllegalArgumentException("no profile " + name + "; have " + profiles.keySet());
        }

        List<Seat> seats = new ArrayList<>();
        for (Map<String, Object> s : (List<Map<String, Object>>) spec.get("seats")) {
            seats.add(new Seat((int) s.get("seat"), (String) s.get("access"),
                    (String) s.get("provider"), (String) s.get("model")));
        }
        seats.sort((a, b) -> Integer.compare(a.seat(), b.seat()));

        Map<String, Object> j = (Map<String, Object>) spec.get("judge");
        Seat judge = new Seat(0, (String) j.get("access"), (String) j.get("provider"),
                (String) j.get("model"));

        Map<String, Object> b = (Map<String, Object>) spec.get("budgets");
        Budgets budgets = new Budgets(
                (int) b.get("max_turns"),
                (int) b.get("max_floor_passes"),
                (int) b.get("max_message_chars"),
                (int) b.get("max_context_tokens"),
                ((Number) b.get("max_tokens_per_game")).longValue());

        Map<String, Object> inference = raw.get("inference") instanceof Map
                ? (Map<String, Object>) raw.get("inference") : Map.of();

        return new Profile(name, List.copyOf(seats), judge, budgets, inference);
    }

    /**
     * Assign seats to colours for one game, rotating with {@code gameIndex} —
     * the same {@code (i + gameIndex) % n} rule as config.py. A full rotation
     * is four games, so any run supporting a claim about models should be a
     * multiple of four (ADR-0006).
     */
    public static Map<Color, Seat> seating(Profile profile, int gameIndex) {
        Color[] colors = Color.values();
        Map<Color, Seat> assigned = new LinkedHashMap<>();
        for (int i = 0; i < colors.length; i++) {
            assigned.put(colors[i], profile.seats().get((i + gameIndex) % colors.length));
        }
        return assigned;
    }
}
