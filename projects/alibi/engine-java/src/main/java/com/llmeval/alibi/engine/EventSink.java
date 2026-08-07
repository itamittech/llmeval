package com.llmeval.alibi.engine;

import java.io.IOException;
import java.io.Writer;
import java.io.UncheckedIOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Event emission — the engine's only output.
 *
 * <p>Conforms to {@code shared/schemas/alibi-event.schema.json}, the integration contract for the UI
 * and the evaluation harness (ADR-0003).
 *
 * <p>Engine events carry no timestamps: two runs of the same seed must produce byte-identical
 * transcripts so they can be diffed mechanically — across languages as much as across runs.
 *
 * <p>This is the engine's one real inheritance hierarchy, and a template method: {@link #emit}
 * assigns the sequence number and is fixed; {@link #write} is the only thing subclasses change.
 */
public abstract class EventSink {

    private int seq;

    public Map<String, Object> emit(String type, Map<String, Object> payload, int turn) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("seq", seq);
        event.put("turn", turn);
        event.put("type", type);
        event.put("payload", payload);
        seq++;
        write(event);
        return event;
    }

    protected abstract void write(Map<String, Object> event);

    /** Collects events in memory. Used by tests and short runs. */
    public static final class ListSink extends EventSink {
        private final List<Map<String, Object>> events = new ArrayList<>();

        @Override
        protected void write(Map<String, Object> event) {
            events.add(event);
        }

        public List<Map<String, Object>> events() {
            return events;
        }
    }

    /** Streams events to a JSON Lines file as the game plays. */
    public static final class JsonlSink extends EventSink {
        private final Writer out;

        public JsonlSink(Writer out) {
            this.out = out;
        }

        @Override
        protected void write(Map<String, Object> event) {
            try {
                // compact, not canonical: Python's JsonlSink does not sort keys either, and
                // transcripts from the two engines should stay byte-comparable.
                out.write(Json.compact(event));
                out.write("\n");
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
    }

    /**
     * Fans out to several sinks while keeping one shared sequence.
     *
     * <p>Deliberately calls each child's {@link #write}, not {@link #emit}, so children never
     * renumber.
     */
    public static final class TeeSink extends EventSink {
        private final List<EventSink> sinks;

        public TeeSink(EventSink... sinks) {
            this.sinks = List.of(sinks);
        }

        @Override
        protected void write(Map<String, Object> event) {
            for (EventSink sink : sinks) {
                sink.write(event);
            }
        }
    }
}
