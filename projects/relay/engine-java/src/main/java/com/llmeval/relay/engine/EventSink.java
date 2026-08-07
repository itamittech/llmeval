package com.llmeval.relay.engine;

import java.io.IOException;
import java.io.Writer;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Event emission, conforming to {@code shared/schemas/relay-event.schema.json}.
 *
 * <p>No timestamps: two runs of one seed must produce byte-identical transcripts so they can be
 * diffed mechanically — across processes and, more to the point, across languages.
 */
public abstract class EventSink {

    private int seq;

    public Map<String, Object> emit(String type, Map<String, Object> payload, int turn) {
        Map<String, Object> event = new LinkedHashMap<>();
        event.put("seq", seq++);
        event.put("turn", turn);
        event.put("type", type);
        event.put("payload", payload);
        write(event);
        return event;
    }

    protected abstract void write(Map<String, Object> event);

    /** Collects events in memory. Used by tests and short runs. */
    public static final class ListSink extends EventSink {
        private final List<Map<String, Object>> events = new ArrayList<>();

        public List<Map<String, Object>> events() {
            return events;
        }

        @Override
        protected void write(Map<String, Object> event) {
            events.add(event);
        }
    }

    /** Streams events to a JSON Lines file as the race runs. */
    public static final class JsonlSink extends EventSink {
        private final Writer out;

        public JsonlSink(Writer out) {
            this.out = out;
        }

        @Override
        protected void write(Map<String, Object> event) {
            try {
                out.write(Json.compact(event));
                out.write("\n");
            } catch (IOException e) {
                throw new UncheckedIoException(e);
            }
        }
    }

    /** Fans out to several sinks while keeping one shared sequence. */
    public static final class TeeSink extends EventSink {
        private final EventSink[] sinks;

        public TeeSink(EventSink... sinks) {
            this.sinks = sinks;
        }

        @Override
        protected void write(Map<String, Object> event) {
            for (EventSink sink : sinks) {
                sink.write(event);
            }
        }
    }

    /** Unchecked wrapper, so a sink can satisfy a void signature the engine defines. */
    public static final class UncheckedIoException extends RuntimeException {
        public UncheckedIoException(IOException cause) {
            super(cause);
        }
    }
}
