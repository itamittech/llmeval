package com.llmeval.ludo.engine;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Minimal JSON, deliberately hand-rolled.
 *
 * <p>The engine has no dependencies — the Python one is standard-library only, and this one is
 * JDK only — so there is no Jackson or Gson here. That is not asceticism: an engine with a
 * dependency tree is an engine whose behaviour can change when something upstream is bumped, and
 * these two engines are supposed to agree byte for byte across languages and across time.
 *
 * <p>{@link #canonical} must match Python's
 * {@code json.dumps(obj, sort_keys=True, separators=(",", ":"))} <em>exactly</em>. Keys sorted,
 * no spaces, non-ASCII escaped. Every conformance digest is taken over this output, so a stray
 * space would fail all twenty vectors at once — which is the correct outcome, and why the
 * digests are worth having.
 *
 * <p>{@link #parse} handles only what {@code shared/conformance/vectors.json} contains. It is not
 * a general JSON parser and does not try to be.
 */
public final class Json {

    private Json() {}

    // -- writing ---------------------------------------------------------

    /**
     * Stable serialisation with keys sorted, for digests and cross-engine conformance.
     *
     * <p>Matches {@code json.dumps(obj, sort_keys=True, separators=(",", ":"))}.
     */
    public static String canonical(Object value) {
        StringBuilder out = new StringBuilder();
        write(value, out, true);
        return out.toString();
    }

    /**
     * Serialisation preserving insertion order, for transcript files.
     *
     * <p>Matches {@code json.dumps(obj, separators=(",", ":"))} — note the absence of
     * {@code sort_keys}. Python's {@code JsonlSink} does not sort, so a transcript's keys come
     * out in emission order ({@code seq}, {@code turn}, {@code type}, {@code payload}). Sorting
     * here would produce a file that is equally valid and equally schema-conformant, and yet no
     * longer byte-comparable with the Python engine's output for the same seed. That comparison
     * is worth keeping, so the two writers stay distinct.
     */
    public static String compact(Object value) {
        StringBuilder out = new StringBuilder();
        write(value, out, false);
        return out.toString();
    }

    private static void write(Object value, StringBuilder out, boolean sortKeys) {
        switch (value) {
            case null -> out.append("null");
            case String s -> writeString(s, out);
            case Boolean b -> out.append(b ? "true" : "false");
            case Integer i -> out.append(i.intValue());
            case Long l -> out.append(l.longValue());
            case Map<?, ?> map -> writeObject(map, out, sortKeys);
            case List<?> list -> writeArray(list, out, sortKeys);
            default -> throw new IllegalArgumentException(
                    "not serialisable: " + value.getClass().getName());
        }
    }

    private static void writeObject(Map<?, ?> map, StringBuilder out, boolean sortKeys) {
        Map<String, Object> ordered;
        if (sortKeys) {
            // Java's String ordering is UTF-16 code-unit order and Python's is code point order;
            // they agree for every key the schema uses (ASCII), and the schema is where key
            // names are fixed.
            ordered = new TreeMap<>();
        } else {
            ordered = new LinkedHashMap<>();
        }
        map.forEach((k, v) -> ordered.put(String.valueOf(k), v));

        out.append('{');
        boolean first = true;
        for (Map.Entry<String, Object> entry : ordered.entrySet()) {
            if (!first) {
                out.append(',');
            }
            first = false;
            writeString(entry.getKey(), out);
            out.append(':');
            write(entry.getValue(), out, sortKeys);
        }
        out.append('}');
    }

    private static void writeArray(List<?> list, StringBuilder out, boolean sortKeys) {
        out.append('[');
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) {
                out.append(',');
            }
            write(list.get(i), out, sortKeys);
        }
        out.append(']');
    }

    private static void writeString(String s, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                default -> {
                    // Python's json.dumps defaults to ensure_ascii=True.
                    if (c < 0x20 || c > 0x7E) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
    }

    // -- reading ---------------------------------------------------------

    public static Object parse(String text) {
        Parser parser = new Parser(text);
        parser.skipWhitespace();
        Object value = parser.value();
        parser.skipWhitespace();
        if (!parser.atEnd()) {
            throw new IllegalArgumentException("trailing content at offset " + parser.pos);
        }
        return value;
    }

    private static final class Parser {
        private final String src;
        private int pos;

        Parser(String src) {
            this.src = src;
        }

        boolean atEnd() {
            return pos >= src.length();
        }

        void skipWhitespace() {
            while (pos < src.length() && Character.isWhitespace(src.charAt(pos))) {
                pos++;
            }
        }

        Object value() {
            char c = src.charAt(pos);
            return switch (c) {
                case '{' -> object();
                case '[' -> array();
                case '"' -> string();
                case 't' -> literal("true", Boolean.TRUE);
                case 'f' -> literal("false", Boolean.FALSE);
                case 'n' -> literal("null", null);
                default -> number();
            };
        }

        private Object literal(String token, Object result) {
            if (!src.startsWith(token, pos)) {
                throw new IllegalArgumentException("bad literal at offset " + pos);
            }
            pos += token.length();
            return result;
        }

        private Map<String, Object> object() {
            Map<String, Object> map = new LinkedHashMap<>();
            pos++; // {
            skipWhitespace();
            if (src.charAt(pos) == '}') {
                pos++;
                return map;
            }
            while (true) {
                skipWhitespace();
                String key = string();
                skipWhitespace();
                pos++; // :
                skipWhitespace();
                map.put(key, value());
                skipWhitespace();
                char c = src.charAt(pos++);
                if (c == '}') {
                    return map;
                }
                if (c != ',') {
                    throw new IllegalArgumentException("expected , or } at offset " + (pos - 1));
                }
            }
        }

        private List<Object> array() {
            List<Object> list = new ArrayList<>();
            pos++; // [
            skipWhitespace();
            if (src.charAt(pos) == ']') {
                pos++;
                return list;
            }
            while (true) {
                skipWhitespace();
                list.add(value());
                skipWhitespace();
                char c = src.charAt(pos++);
                if (c == ']') {
                    return list;
                }
                if (c != ',') {
                    throw new IllegalArgumentException("expected , or ] at offset " + (pos - 1));
                }
            }
        }

        private String string() {
            StringBuilder sb = new StringBuilder();
            pos++; // opening quote
            while (true) {
                char c = src.charAt(pos++);
                if (c == '"') {
                    return sb.toString();
                }
                if (c != '\\') {
                    sb.append(c);
                    continue;
                }
                char esc = src.charAt(pos++);
                switch (esc) {
                    case '"' -> sb.append('"');
                    case '\\' -> sb.append('\\');
                    case '/' -> sb.append('/');
                    case 'n' -> sb.append('\n');
                    case 'r' -> sb.append('\r');
                    case 't' -> sb.append('\t');
                    case 'b' -> sb.append('\b');
                    case 'f' -> sb.append('\f');
                    case 'u' -> {
                        sb.append((char) Integer.parseInt(src.substring(pos, pos + 4), 16));
                        pos += 4;
                    }
                    default -> throw new IllegalArgumentException("bad escape at offset " + pos);
                }
            }
        }

        private Object number() {
            int start = pos;
            while (pos < src.length() && "+-0123456789.eE".indexOf(src.charAt(pos)) >= 0) {
                pos++;
            }
            String token = src.substring(start, pos);
            if (token.contains(".") || token.contains("e") || token.contains("E")) {
                return Double.parseDouble(token);
            }
            return Long.parseLong(token);
        }
    }
}
