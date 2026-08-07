package com.llmeval.relay.springai;

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

/**
 * Reading {@code shared/models.yaml} — RELAY's own lanes, budgets and anchor.
 *
 * <p>The first game in this repo that does not use the four shared seats. Its runners are small
 * models on local hardware, so a lane carries a quantisation knob a hosted API has no equivalent
 * for, and {@code access} has a third value, {@code local}. Nothing here decides anything.
 */
public final class ModelsConfig {

    public record Lane(int lane, String access, String provider, String model,
                       String quantisation) {
        public boolean pinned() {
            return model != null && !model.isBlank() && !model.equals("TBD");
        }
    }

    public record Anchor(String provider, String access, String model) {}

    public record Budgets(int maxTurns, int escalationQuota, int maxNoteChars,
                          int maxTokensPerGame) {}

    public record Profile(String name, List<Lane> lanes, Budgets budgets, Anchor anchor) {}

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
        Map<String, Object> relay = (Map<String, Object>) raw.get("relay");
        Map<String, Object> budgets = (Map<String, Object>) relay.get("budgets");
        Map<String, Object> b = (Map<String, Object>) budgets.get(name);
        if (b == null) {
            throw new IllegalArgumentException("no profile " + name + "; have " + budgets.keySet());
        }
        Map<String, Object> a = (Map<String, Object>) relay.get("anchor");

        List<Lane> lanes = new ArrayList<>();
        for (Map<String, Object> lane : (List<Map<String, Object>>) relay.get("lanes")) {
            lanes.add(new Lane((int) lane.get("lane"), (String) lane.get("access"),
                    (String) lane.get("provider"), (String) lane.get("model"),
                    (String) lane.get("quantisation")));
        }
        lanes.sort((x, y) -> Integer.compare(x.lane(), y.lane()));

        return new Profile(name, List.copyOf(lanes),
                new Budgets((int) b.get("max_turns"), (int) b.get("escalation_quota"),
                        (int) b.get("max_note_chars"), (int) b.get("max_tokens_per_game")),
                new Anchor((String) a.get("provider"), (String) a.get("access"),
                        (String) a.get("model")));
    }

    /**
     * Lane to colour for one race, rotating with {@code gameIndex} (ADR-0006).
     *
     * <p>Turn order is an advantage here in a way it never was in LUDO: the runner who moves
     * first reaches the shared pool first. Rotating is not decoration.
     */
    public static Map<String, Lane> laneAssignment(Profile profile, List<String> colors,
                                                   int gameIndex) {
        Map<String, Lane> assignment = new LinkedHashMap<>();
        int n = colors.size();
        for (int i = 0; i < n; i++) {
            assignment.put(colors.get(i), profile.lanes().get((i + gameIndex) % n));
        }
        return assignment;
    }
}
