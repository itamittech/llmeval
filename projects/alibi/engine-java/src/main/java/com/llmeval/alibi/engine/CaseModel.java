package com.llmeval.alibi.engine;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The case: elements, cast, and the deal. Direct port of the Python engine's {@code case.py} —
 * element ids are the normative vocabulary, display names are how the fiction speaks, and the
 * draw order of {@link #deal} is spec.
 */
public final class CaseModel {

    public static final List<String> DIMENSIONS = List.of("who", "how", "where");

    public static final List<String> WHO = List.of(
            "curator", "magician", "heiress", "chef", "photographer", "inspector");
    public static final List<String> HOW = List.of(
            "sleight-of-hand", "duplicate-key", "service-hatch", "blackout", "forged-pass");
    public static final List<String> WHERE = List.of(
            "ballroom", "vault-room", "kitchen", "terrace", "library", "cloakroom",
            "gallery", "garden");

    /** Canonical order over all 19 elements: who, then how, then where. */
    public static final List<String> ALL_ELEMENTS;

    public static final Map<String, String> DISPLAY;

    static {
        List<String> all = new ArrayList<>(WHO);
        all.addAll(HOW);
        all.addAll(WHERE);
        ALL_ELEMENTS = List.copyOf(all);

        Map<String, String> display = new LinkedHashMap<>();
        display.put("curator", "Curator Meera Joshi");
        display.put("magician", "the magician Vikram Rao");
        display.put("heiress", "the heiress Tara Kapoor");
        display.put("chef", "Chef Antoine D'Souza");
        display.put("photographer", "the photographer Zoya Khan");
        display.put("inspector", "retired Inspector Balbir Singh");
        display.put("sleight-of-hand", "sleight of hand");
        display.put("duplicate-key", "a duplicate key");
        display.put("service-hatch", "the service hatch");
        display.put("blackout", "a staged blackout");
        display.put("forged-pass", "a forged pass");
        display.put("ballroom", "the ballroom");
        display.put("vault-room", "the vault room");
        display.put("kitchen", "the kitchen");
        display.put("terrace", "the terrace");
        display.put("library", "the library");
        display.put("cloakroom", "the cloakroom");
        display.put("gallery", "the gallery");
        display.put("garden", "the garden");
        DISPLAY = Map.copyOf(display);
    }

    public static List<String> elements(String dimension) {
        return switch (dimension) {
            case "who" -> WHO;
            case "how" -> HOW;
            case "where" -> WHERE;
            default -> throw new IllegalArgumentException("unknown dimension: " + dimension);
        };
    }

    public static String dimensionOf(String element) {
        for (String dim : DIMENSIONS) {
            if (elements(dim).contains(element)) {
                return dim;
            }
        }
        throw new IllegalArgumentException("unknown element: " + element);
    }

    private final Map<String, String> solution;      // who/how/where, insertion order
    private final Map<Color, List<String>> hands;    // canonical-sorted, four each

    private CaseModel(Map<String, String> solution, Map<Color, List<String>> hands) {
        this.solution = solution;
        this.hands = hands;
    }

    /** The sealed truth, keys in who/how/where order. */
    public Map<String, String> solution() {
        return solution;
    }

    public List<String> hand(Color color) {
        return hands.get(color);
    }

    public Color holderOf(String element) {
        for (Color color : Color.values()) {
            if (hands.get(color).contains(element)) {
                return color;
            }
        }
        return null;
    }

    /**
     * Seal one element per dimension, shuffle the rest, deal four each. Draw order is spec:
     * solution picks in who/how/where order, one shuffle of the 16 remaining elements in
     * canonical order, round-robin red/green/yellow/blue, hands sorted back to canonical order.
     */
    public static CaseModel deal(Rng rng) {
        Map<String, String> solution = new LinkedHashMap<>();
        for (String dim : DIMENSIONS) {
            List<String> pool = elements(dim);
            solution.put(dim, pool.get(rng.below(pool.size())));
        }

        List<String> remaining = new ArrayList<>();
        for (String element : ALL_ELEMENTS) {
            if (!solution.containsValue(element)) {
                remaining.add(element);
            }
        }
        rng.shuffle(remaining);

        Map<Color, List<String>> hands = new EnumMap<>(Color.class);
        Color[] colors = Color.values();
        for (Color color : colors) {
            hands.put(color, new ArrayList<>());
        }
        for (int i = 0; i < remaining.size(); i++) {
            hands.get(colors[i % colors.length]).add(remaining.get(i));
        }
        for (Color color : colors) {
            hands.get(color).sort(Comparator.comparingInt(ALL_ELEMENTS::indexOf));
        }
        return new CaseModel(solution, hands);
    }
}
