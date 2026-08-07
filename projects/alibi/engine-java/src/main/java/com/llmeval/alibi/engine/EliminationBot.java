package com.llmeval.alibi.engine;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Strict-logic deduction — the deterministic decider conformance vectors run on, and a direct
 * port of the Python bot down to its query habits: one fixed archive search per turn (its current
 * top suspect), results ignored, issued <em>before</em> deciding whether to pass. Change either
 * engine's bot and every vector fails.
 */
public final class EliminationBot implements Detective {

    public static final String NAME = "elimination-bot";

    /**
     * 1/n quantised to a literal table — never computed, so the serialised bytes cannot depend on
     * either language's float division or formatting.
     */
    static final Map<Integer, Double> CONFIDENCE = Map.of(
            1, 1.0, 2, 0.5, 3, 0.3333, 4, 0.25, 5, 0.2, 6, 0.1667, 7, 0.1429, 8, 0.125);

    private Triple certain;

    private List<String> candidates(DetectiveView view, String dim) {
        Set<String> known = new HashSet<>(view.knownNotSolution());
        List<String> open = new ArrayList<>();
        for (String element : CaseModel.elements(dim)) {
            if (!known.contains(element)) {
                open.add(element);
            }
        }
        return open;
    }

    private Map<String, List<String>> picks(DetectiveView view) {
        Map<String, List<String>> picks = new LinkedHashMap<>();
        for (String dim : CaseModel.DIMENSIONS) {
            picks.put(dim, candidates(view, dim));
        }
        return picks;
    }

    @Override
    public Suggestion suggest(TurnContext ctx) {
        Map<String, List<String>> picks = picks(ctx.view());
        List<String> who = picks.get("who");
        ctx.archive().search(who.isEmpty() ? "sapphire" : who.get(0));
        if (certain != null || picks.values().stream().allMatch(c -> c.size() == 1)) {
            return null; // nothing left to learn; accuse this turn
        }
        return new Suggestion(picks.get("who").get(0), picks.get("how").get(0),
                picks.get("where").get(0));
    }

    @Override
    public String show(ShowContext ctx) {
        return ctx.options().get(0);
    }

    @Override
    public Triple accuse(TurnContext ctx) {
        if (ctx.noRefutation() != null) {
            Suggestion s = ctx.noRefutation();
            Set<String> held = new HashSet<>(ctx.view().myHand());
            held.retainAll(new HashSet<>(s.named()));
            if (held.isEmpty()) {
                certain = new Triple(s.who(), s.how(), s.where());
            }
        }
        Map<String, List<String>> picks = picks(ctx.view());
        if (certain == null && picks.values().stream().allMatch(c -> c.size() == 1)) {
            certain = new Triple(picks.get("who").get(0), picks.get("how").get(0),
                    picks.get("where").get(0));
        }
        return certain;
    }

    @Override
    public Belief conclude(TurnContext ctx) {
        Map<String, List<String>> picks = picks(ctx.view());
        Map<String, Double> confidence = new LinkedHashMap<>();
        for (String dim : CaseModel.DIMENSIONS) {
            confidence.put(dim, CONFIDENCE.get(picks.get(dim).size()));
        }
        return new Belief(picks.get("who").get(0), picks.get("how").get(0),
                picks.get("where").get(0), confidence);
    }

    @Override
    public String name() {
        return NAME;
    }
}
