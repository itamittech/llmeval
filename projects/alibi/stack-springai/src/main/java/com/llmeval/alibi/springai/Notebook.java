package com.llmeval.alibi.springai;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

/**
 * The detective's notebook — hand-rolled, because LUDO's finding holds in the
 * second game too: {@code ChatMemory} is conversation history, not a key-value
 * state an agent owns, and Spring AI still has no belief-store primitive. A
 * legitimate Manual under ADR-0008, recorded in the capability matrix.
 *
 * <p>Renders {@code {{memory}}} byte-identically to the Python stacks, and is
 * deliberately unreliable: red-herring damage included, never corrected.
 */
public final class Notebook {

    public record Note(String kind, String text, int turn, String about) {}

    static final Set<String> KINDS = Set.of("deduction", "suspicion", "plan", "observation");
    static final String DEFAULT_KIND = "observation";

    private final List<Note> notes = new ArrayList<>();

    public Note write(String text, int turn, String kind, String about) {
        Note note = new Note(
                kind != null && KINDS.contains(kind) ? kind : DEFAULT_KIND,
                text.strip(), turn, about);
        notes.add(note);
        return note;
    }

    public String render(int limit) {
        if (notes.isEmpty()) {
            return "(nothing yet)";
        }
        List<Note> tail = notes.subList(Math.max(0, notes.size() - limit), notes.size());
        StringBuilder out = new StringBuilder();
        for (Note note : tail) {
            if (!out.isEmpty()) {
                out.append("\n");
            }
            String about = note.about() == null ? "" : " [" + note.about() + "]";
            out.append("- turn ").append(note.turn()).append(" (").append(note.kind())
               .append(")").append(about).append(": ").append(note.text());
        }
        return out.toString();
    }

    public int size() {
        return notes.size();
    }
}
