package com.llmeval.ludo.springai;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/**
 * One agent's beliefs: notes with kinds, plus durable facts that recency can
 * never drop. Private, persistent across turns, deliberately unreliable — it
 * records what the agent believes, including what it was lied to about, and
 * nothing here reconciles it against the board.
 *
 * <p><strong>Hand-rolled, and recorded as such.</strong> Spring AI's
 * {@code ChatMemory} is conversation history, not a key-value belief store —
 * there is no {@code AgentState} equivalent, so this is a legitimate
 * <em>Manual</em> under ADR-0008's rule, logged in the capability matrix.
 * The rendered format matches the Python stacks' byte for byte, because the
 * {@code {{memory}}} variable is observable surface.
 */
public final class Memory {

    public record Note(String kind, String text, int turn, String about) {}

    static final Set<String> KINDS = Set.of("opponent_model", "commitment", "strategy", "observation");
    static final String DEFAULT_KIND = "observation";

    private final List<Note> notes = new ArrayList<>();
    private final List<String> durable = new ArrayList<>();

    public Note write(String text, int turn, String kind, String about) {
        Note note = new Note(KINDS.contains(kind) ? kind : DEFAULT_KIND,
                text == null ? "" : text.strip(), turn, about);
        notes.add(note);
        return note;
    }

    public void absorb(String summary) {
        if (summary != null && !summary.isBlank()) durable.add(summary.strip());
    }

    public List<Note> notes() {
        return List.copyOf(notes);
    }

    /** The {@code {{memory}}} variable: durable facts first, freshest notes last. */
    public String render(int limit) {
        List<String> lines = new ArrayList<>();
        for (String fact : durable) lines.add("- (durable) " + fact);
        int start = Math.max(0, notes.size() - limit);
        for (Note note : notes.subList(start, notes.size())) {
            String about = note.about() == null ? "" : " [" + note.about() + "]";
            lines.add("- turn " + note.turn() + " (" + note.kind() + ")" + about + ": " + note.text());
        }
        return lines.isEmpty() ? "(nothing yet)" : String.join("\n", lines);
    }
}
