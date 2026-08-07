package com.llmeval.alibi.engine;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * A read-only, single-detective window onto the game.
 *
 * <p>Unlike LUDO's shared {@code StateView}, what red may see and what blue may see are different
 * objects, built from different slices of state. Privacy is by construction: another detective's
 * hand is not behind an access check — it simply is not in this object.
 */
public final class DetectiveView {

    private final Color color;
    private final List<String> hand;
    private final Map<String, Color> shown;
    private final List<Color> eliminated;
    private final List<SuggestionRecord> log;

    DetectiveView(Color color, List<String> hand, Map<String, Color> shown,
                  List<Color> eliminated, List<SuggestionRecord> log) {
        this.color = color;
        this.hand = List.copyOf(hand);
        this.shown = new LinkedHashMap<>(shown);
        this.eliminated = List.copyOf(eliminated);
        this.log = List.copyOf(log);
    }

    public Color color() {
        return color;
    }

    public List<String> myHand() {
        return hand;
    }

    /** Exhibits opponents have shown me, element to who showed it. */
    public Map<String, Color> shownToMe() {
        return new LinkedHashMap<>(shown);
    }

    /** Own hand plus everything shown — the certain eliminations, canonical order. */
    public List<String> knownNotSolution() {
        Set<String> seen = new HashSet<>(hand);
        seen.addAll(shown.keySet());
        List<String> out = new ArrayList<>();
        for (String element : CaseModel.ALL_ELEMENTS) {
            if (seen.contains(element)) {
                out.add(element);
            }
        }
        return out;
    }

    public List<Color> eliminated() {
        return eliminated;
    }

    /** The public record: every suggestion, who refuted, never what. */
    public List<SuggestionRecord> suggestions() {
        return log;
    }
}
