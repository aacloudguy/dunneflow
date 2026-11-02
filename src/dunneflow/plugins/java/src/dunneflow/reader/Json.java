package dunneflow.reader;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * JSON, as much of it as the protocol needs, written here because the JDK has none.
 *
 * <p>Vendoring a library would be a dependency fetched once and trusted forever, for a wire
 * where this reader builds every frame itself ({@code Facts.java} is generated from
 * {@code schema.py}) or reads a handful of keys out of one. So the decoder is a plain
 * recursive one, and the encoder is an interface.
 *
 * <p><b>{@link #writeString} is the one place a string is escaped</b>, and it escapes
 * everything outside printable ASCII as {@code \\uXXXX}. A frame is then ASCII whatever the
 * source held, so no platform's default charset can reach the wire, and a line the host
 * cannot read is impossible to write from here. Python's decoder joins a surrogate pair
 * back into one character, so nothing is lost.
 *
 * <p>Decoded values are plain Java: {@code null}, {@link Boolean}, {@link Long} for an
 * integral number, {@link Double} otherwise, {@link String}, {@link List} and
 * {@link LinkedHashMap}. Objects keep their keys in the order they were read.
 */
public final class Json {
    private Json() {}

    /** A record that writes itself. Every generated type is one. */
    public interface Writable {
        void writeJson(StringBuilder out);
    }

    // ------------------------------------------------------------- writing --- //

    public static void writeString(StringBuilder out, String s) {
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
                    if (c < 0x20 || c > 0x7e) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
    }

    /** Any value this reader sends: a record, an enum, a list, a map, or a scalar. */
    public static void write(StringBuilder out, Object v) {
        if (v == null) {
            out.append("null");
        } else if (v instanceof Writable w) {
            w.writeJson(out);
        } else if (v instanceof String s) {
            writeString(out, s);
        } else if (v instanceof Boolean b) {
            out.append(b ? "true" : "false");
        } else if (v instanceof Long || v instanceof Integer) {
            out.append(v);
        } else if (v instanceof Double d) {
            if (d.isNaN() || d.isInfinite()) {
                throw new IllegalArgumentException("JSON has no " + d);
            }
            out.append(d);
        } else if (v instanceof List<?> list) {
            out.append('[');
            for (int i = 0; i < list.size(); i++) {
                if (i > 0) {
                    out.append(',');
                }
                write(out, list.get(i));
            }
            out.append(']');
        } else if (v instanceof Map<?, ?> map) {
            out.append('{');
            boolean[] first = {true};
            for (Map.Entry<?, ?> e : map.entrySet()) {
                field(out, first, String.valueOf(e.getKey()), e.getValue());
            }
            out.append('}');
        } else {
            throw new IllegalArgumentException("not a JSON value: " + v.getClass());
        }
    }

    public static void field(StringBuilder out, boolean[] first, String name, Object v) {
        if (!first[0]) {
            out.append(',');
        }
        first[0] = false;
        writeString(out, name);
        out.append(':');
        write(out, v);
    }

    public static void field(StringBuilder out, boolean[] first, String name, long v) {
        field(out, first, name, (Object) v);
    }

    public static void field(StringBuilder out, boolean[] first, String name, boolean v) {
        field(out, first, name, (Object) v);
    }

    public static void field(StringBuilder out, boolean[] first, String name, double v) {
        field(out, first, name, (Object) v);
    }

    /** One frame under construction: {@code t} first, then whatever is put. */
    public static final class Frame {
        private final Map<String, Object> members = new LinkedHashMap<>();

        public Frame(String t) {
            members.put("t", t);
        }

        public Frame put(String key, Object value) {
            members.put(key, value);
            return this;
        }

        public String finish() {
            StringBuilder out = new StringBuilder();
            write(out, members);
            return out.toString();
        }
    }

    // ------------------------------------------------------------- reading --- //

    /** Decode one frame. An error names the offset, for whoever reads the line it came from. */
    public static Object parse(String text) {
        Parser p = new Parser(text);
        p.ws();
        Object v = p.value();
        p.ws();
        if (p.i != text.length()) {
            throw new IllegalArgumentException("trailing text at " + p.i);
        }
        return v;
    }

    public static Object get(Object obj, String key) {
        return obj instanceof Map<?, ?> m ? m.get(key) : null;
    }

    public static String str(Object obj, String key) {
        return get(obj, key) instanceof String s ? s : null;
    }

    public static List<?> list(Object obj, String key) {
        return get(obj, key) instanceof List<?> l ? l : List.of();
    }

    /** Every string in a list, skipping anything that is not one. */
    public static List<String> strings(Object v) {
        List<String> out = new ArrayList<>();
        if (v instanceof List<?> l) {
            for (Object x : l) {
                if (x instanceof String s) {
                    out.add(s);
                }
            }
        }
        return out;
    }

    private static final class Parser {
        private final String s;
        private int i;

        Parser(String s) {
            this.s = s;
        }

        private IllegalArgumentException bad(String what) {
            return new IllegalArgumentException(what + " at " + i);
        }

        void ws() {
            while (i < s.length() && " \t\r\n".indexOf(s.charAt(i)) >= 0) {
                i++;
            }
        }

        Object value() {
            if (i >= s.length()) {
                throw bad("end of input");
            }
            char c = s.charAt(i);
            switch (c) {
                case '{':
                    return object();
                case '[':
                    return array();
                case '"':
                    return string();
                case 't':
                    return literal("true", Boolean.TRUE);
                case 'f':
                    return literal("false", Boolean.FALSE);
                case 'n':
                    return literal("null", null);
                default:
                    return number();
            }
        }

        private Object literal(String word, Object v) {
            if (!s.startsWith(word, i)) {
                throw bad("unexpected text");
            }
            i += word.length();
            return v;
        }

        private Map<String, Object> object() {
            Map<String, Object> out = new LinkedHashMap<>();
            i++;
            ws();
            if (i < s.length() && s.charAt(i) == '}') {
                i++;
                return out;
            }
            while (true) {
                ws();
                if (i >= s.length() || s.charAt(i) != '"') {
                    throw bad("expected a key");
                }
                String k = string();
                ws();
                if (i >= s.length() || s.charAt(i) != ':') {
                    throw bad("expected ':'");
                }
                i++;
                ws();
                out.put(k, value());
                ws();
                if (i < s.length() && s.charAt(i) == ',') {
                    i++;
                } else if (i < s.length() && s.charAt(i) == '}') {
                    i++;
                    return out;
                } else {
                    throw bad("expected ',' or '}'");
                }
            }
        }

        private List<Object> array() {
            List<Object> out = new ArrayList<>();
            i++;
            ws();
            if (i < s.length() && s.charAt(i) == ']') {
                i++;
                return out;
            }
            while (true) {
                ws();
                out.add(value());
                ws();
                if (i < s.length() && s.charAt(i) == ',') {
                    i++;
                } else if (i < s.length() && s.charAt(i) == ']') {
                    i++;
                    return out;
                } else {
                    throw bad("expected ',' or ']'");
                }
            }
        }

        private String string() {
            StringBuilder out = new StringBuilder();
            i++;
            while (true) {
                if (i >= s.length()) {
                    throw bad("unterminated string");
                }
                char c = s.charAt(i++);
                if (c == '"') {
                    return out.toString();
                }
                if (c != '\\') {
                    out.append(c);
                    continue;
                }
                if (i >= s.length()) {
                    throw bad("unterminated escape");
                }
                char e = s.charAt(i++);
                switch (e) {
                    case '"' -> out.append('"');
                    case '\\' -> out.append('\\');
                    case '/' -> out.append('/');
                    case 'b' -> out.append('\b');
                    case 'f' -> out.append('\f');
                    case 'n' -> out.append('\n');
                    case 'r' -> out.append('\r');
                    case 't' -> out.append('\t');
                    case 'u' -> {
                        if (i + 4 > s.length()) {
                            throw bad("short \\u escape");
                        }
                        out.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
                        i += 4;
                    }
                    default -> throw bad("unknown escape");
                }
            }
        }

        private Object number() {
            int start = i;
            boolean integral = true;
            while (i < s.length()) {
                char c = s.charAt(i);
                if (c == '.' || c == 'e' || c == 'E') {
                    integral = false;
                } else if (!(c == '-' || c == '+' || (c >= '0' && c <= '9'))) {
                    break;
                }
                i++;
            }
            String text = s.substring(start, i);
            if (text.isEmpty()) {
                throw bad("unexpected character");
            }
            try {
                return integral ? (Object) Long.parseLong(text) : (Object) Double.parseDouble(text);
            } catch (NumberFormatException ex) {
                throw bad("bad number " + text);
            }
        }
    }
}
