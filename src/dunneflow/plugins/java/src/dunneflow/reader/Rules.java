package dunneflow.reader;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * {@code detectors/java.yaml}, as the host sends it in {@code open}.
 *
 * <p>The host loads and validates the rules file ({@code detectors.rules_document}). This
 * reader only reads the keys it acts on. A key it does not know is ignored, and a key it
 * does know in a shape it cannot read is read as empty, never as a guessed default
 * (rule 49).
 *
 * <p><b>Every match is {@code detectors.BoundaryRule.matches_call}'s, spelt again</b>: the
 * same four tests in the same order, including the clause that a bare name is never a
 * method on something. A second implementation that disagreed with the first would make a
 * rule mean two things, one per language (rule 51).
 */
public final class Rules {
    final Object raw;
    final List<Boundary> boundaries = new ArrayList<>();
    final List<Entry> entrypoints = new ArrayList<>();
    final Set<String> entryNames = new HashSet<>();
    /** Longest key first, as {@code load_rules} sorts them. */
    final List<Net> net = new ArrayList<>();
    final List<String> verbs = new ArrayList<>();
    final Map<String, Integer> timed = new LinkedHashMap<>();

    static final class Boundary {
        String kind = "";
        String direction = "BOTH";
        String salience = "normal";
        final Set<String> exact = new HashSet<>();
        final List<String> prefix = new ArrayList<>();
        final Set<String> method = new HashSet<>();
        final List<String> contains = new ArrayList<>();
        Integer targetArg;

        boolean matches(String dotted) {
            if (dotted.isEmpty()) {
                return false;
            }
            if (exact.contains(dotted)) {
                return true;
            }
            for (String p : prefix) {
                if (dotted.startsWith(p)) {
                    return true;
                }
            }
            for (String c : contains) {
                if (dotted.contains(c)) {
                    return true;
                }
            }
            int dot = dotted.lastIndexOf('.');
            // A bare name is a plain call, not a method on something.
            return dot >= 0 && method.contains(dotted.substring(dot + 1));
        }
    }

    static final class Entry {
        String kind = "";
        final Set<String> decoratorMethod = new HashSet<>();
        String evidence = "";

        /** {@code EntrypointRule.matches_decorator}: the last segment, as written. */
        boolean matches(String dotted) {
            if (dotted.isEmpty()) {
                return false;
            }
            int dot = dotted.lastIndexOf('.');
            return decoratorMethod.contains(dot >= 0 ? dotted.substring(dot + 1) : dotted);
        }
    }

    static final class Net {
        String prefix = "";
        String protocol = "";
        boolean isAsync;
    }

    Rules(Object raw) {
        this.raw = raw;
        if (raw == null) {
            return;
        }
        for (Object b : Json.list(raw, "boundaries")) {
            Boundary r = new Boundary();
            r.kind = orEmpty(Json.str(b, "kind"));
            String d = Json.str(b, "direction");
            if (d != null && !d.isEmpty()) {
                r.direction = d;
            }
            String s = Json.str(b, "salience");
            if (s != null && !s.isEmpty()) {
                r.salience = s;
            }
            r.exact.addAll(Json.strings(Json.get(b, "exact")));
            r.prefix.addAll(Json.strings(Json.get(b, "prefix")));
            r.method.addAll(Json.strings(Json.get(b, "method")));
            r.contains.addAll(Json.strings(Json.get(b, "contains")));
            if (Json.get(b, "target_arg") instanceof Long n) {
                r.targetArg = n.intValue();
            }
            boundaries.add(r);
        }
        for (Object e : Json.list(raw, "entrypoints")) {
            Entry r = new Entry();
            r.kind = orEmpty(Json.str(e, "kind"));
            r.decoratorMethod.addAll(Json.strings(Json.get(e, "decorator_method")));
            r.evidence = orEmpty(Json.str(e, "evidence"));
            entrypoints.add(r);
        }
        entryNames.addAll(Json.strings(Json.get(raw, "entry_names")));
        Object network = Json.get(raw, "network");
        if (Json.get(network, "libraries") instanceof Map<?, ?> libs) {
            for (Map.Entry<?, ?> lib : libs.entrySet()) {
                Net n = new Net();
                n.prefix = String.valueOf(lib.getKey());
                n.protocol = orEmpty(Json.str(lib.getValue(), "protocol"));
                n.isAsync = Boolean.TRUE.equals(Json.get(lib.getValue(), "async"));
                net.add(n);
            }
        }
        net.sort((a, b) -> a.prefix.length() != b.prefix.length()
            ? b.prefix.length() - a.prefix.length() : a.prefix.compareTo(b.prefix));
        verbs.addAll(Json.strings(Json.get(network, "verbs")));
        if (Json.get(network, "timed") instanceof Map<?, ?> t) {
            for (Map.Entry<?, ?> e : t.entrySet()) {
                if (e.getValue() instanceof Long n) {
                    timed.put(String.valueOf(e.getKey()), n.intValue());
                }
            }
        }
    }

    private static String orEmpty(String s) {
        return s == null ? "" : s;
    }

    int boundaryCount() {
        return boundaries.size();
    }

    /** The first matching rule, so order in the YAML is meaningful. */
    Boundary matchCall(String dotted) {
        for (Boundary b : boundaries) {
            if (b.matches(dotted)) {
                return b;
            }
        }
        return null;
    }

    /** {@code RuleSet.network_profile}, including the clause that makes a bare key exact:
     *  a key with a dot is a prefix and a key without one is a name (rule 5). */
    Net matchNetwork(String dotted) {
        if (dotted.isEmpty()) {
            return null;
        }
        for (Net n : net) {
            if (dotted.equals(n.prefix) || (n.prefix.contains(".") && dotted.startsWith(n.prefix))) {
                return n;
            }
        }
        return null;
    }

    Entry matchDecorator(String dotted) {
        for (Entry e : entrypoints) {
            if (e.matches(dotted)) {
                return e;
            }
        }
        return null;
    }
}
