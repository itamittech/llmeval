package com.llmeval.relay.springai;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The runner's notebook — a plain class, because Spring AI still has nowhere to put one.
 *
 * <p>Third game, third time. {@code ChatMemory} is conversation history: messages in, messages
 * out. It is not a key-value state an agent owns, and there is no counterpart to Strands'
 * {@code AgentState} or LangGraph's {@code Store}. So this renders {@code {{memory}}}
 * byte-identically to the Python stacks and the matrix records another <strong>Manual</strong>.
 *
 * <p>What a runner writes here is the only thing worth remembering in this game: what it is bad
 * at. That is also why the missing primitive costs more than it looks — the note is small, but
 * it is the input to the only decision the game contains.
 */
public final class Notebook {

    /** The kinds the event schema allows for this game. */
    public static final Set<String> KINDS = Set.of("self", "rival", "plan", "observation");

    public static final String DEFAULT_KIND = "observation";

    public record Note(String kind, String text, int turn, String about) {}

    private final Map<String, List<Note>> byLane = new LinkedHashMap<>();

    public Note write(String color, String text, int turn, String kind, String about) {
        Note note = new Note(KINDS.contains(kind) ? kind : DEFAULT_KIND, text.strip(), turn, about);
        byLane.computeIfAbsent(color, k -> new ArrayList<>()).add(note);
        return note;
    }

    public List<Note> notes(String color) {
        return List.copyOf(byLane.getOrDefault(color, List.of()));
    }

    /** The {@code {{memory}}} variable — byte-identical rendering to the other stacks. */
    public String render(String color, int limit) {
        List<Note> notes = notes(color);
        if (notes.isEmpty()) {
            return "(nothing yet)";
        }
        List<String> lines = new ArrayList<>();
        for (Note note : notes.subList(Math.max(0, notes.size() - limit), notes.size())) {
            String about = note.about() == null ? "" : " [" + note.about() + "]";
            lines.add("- turn " + note.turn() + " (" + note.kind() + ")" + about + ": "
                    + note.text());
        }
        return String.join("\n", lines);
    }

    public String render(String color) {
        return render(color, 20);
    }
}
