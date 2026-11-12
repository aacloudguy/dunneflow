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
    final List<Extends> extending = new ArrayList<>();
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
        // `detectors.ArgCondition` (`when_arg`): the rule applies only for some values of one
        // argument. Java has no keyword arguments, so only the position is read.
        Integer whenIndex;
        final Set<String> whenIn = new HashSet<>();
        final Set<String> whenNotIn = new HashSet<>();
        // Said on whatever rule matches instead, when `when_arg` could not decide.
        String undecided = "";
        // A fixed phrase after the evidence.
        String note = "";

        /** {@code ArgCondition.decide}: TRUE, FALSE, or null for undecided. An absent
         *  argument, a literal or a {@code not_in} entry decides no; anything else that is not
         *  in {@code in} -- a variable, a call -- is undecided, and never matches (rule 49). */
        Boolean decide(List<String> texts, List<Boolean> literal) {
            if (whenIndex == null || whenIndex < 0 || whenIndex >= texts.size()) {
                return Boolean.FALSE;
            }
            String v = texts.get(whenIndex);
            if (whenIn.contains(v)) {
                return Boolean.TRUE;
            }
            if (literal.get(whenIndex) || whenNotIn.contains(v)) {
                return Boolean.FALSE;
            }
            return null;
        }

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

    /**
     * {@code extends:} -- what a class is <b>by what it extends</b>, which no file can say of
     * itself and the edge pass can (rule 95). One of two things follows from a match. With
     * {@code boundary}, a call on a receiver of such a type whose body the tree does not hold
     * is a touch: {@code owners.save(o)} on a Spring Data repository is the database. With
     * {@code entrypoint}, a method of such a class that overrides one of the framework's
     * {@code methods} is a way in: nothing in the program calls {@code doGet}.
     */
    static final class Extends {
        final Set<String> types = new HashSet<>();
        String boundary = "";
        String direction = "BOTH";
        String salience = "normal";
        String entrypoint = "";
        final Set<String> methods = new HashSet<>();
        String evidence = "";

        /** The first of this rule's types among {@code lineage}, or null. */
        String among(Set<String> lineage) {
            String found = null;
            for (String t : types) {
                // The smallest name, so the answer does not depend on a set's order (rule 105).
                if (lineage.contains(t) && (found == null || t.compareTo(found) < 0)) {
                    found = t;
                }
            }
            return found;
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
            Object when = Json.get(b, "when_arg");
            if (when != null) {
                if (Json.get(when, "index") instanceof Long n) {
                    r.whenIndex = n.intValue();
                } else {
                    // Refused rather than defaulted: a condition with no position decides
                    // nothing, and would read as "never" without a word (rule 49).
                    r.whenIndex = -1;
                }
                r.whenIn.addAll(Json.strings(Json.get(when, "in")));
                r.whenNotIn.addAll(Json.strings(Json.get(when, "not_in")));
            }
            r.undecided = orEmpty(Json.str(b, "undecided"));
            r.note = orEmpty(Json.str(b, "note"));
            boundaries.add(r);
        }
        for (Object e : Json.list(raw, "entrypoints")) {
            Entry r = new Entry();
            r.kind = orEmpty(Json.str(e, "kind"));
            r.decoratorMethod.addAll(Json.strings(Json.get(e, "decorator_method")));
            r.evidence = orEmpty(Json.str(e, "evidence"));
            entrypoints.add(r);
        }
        for (Object x : Json.list(raw, "extends")) {
            Extends r = new Extends();
            r.types.addAll(Json.strings(Json.get(x, "types")));
            r.boundary = orEmpty(Json.str(x, "boundary"));
            String d = Json.str(x, "direction");
            if (d != null && !d.isEmpty()) {
                r.direction = d;
            }
            String s = Json.str(x, "salience");
            if (s != null && !s.isEmpty()) {
                r.salience = s;
            }
            r.entrypoint = orEmpty(Json.str(x, "entrypoint"));
            r.methods.addAll(Json.strings(Json.get(x, "methods")));
            r.evidence = orEmpty(Json.str(x, "evidence"));
            // A rule that names no type, or says neither thing, decides nothing: left out
            // rather than read as "every class" (rule 49). A way in with no methods named
            // would be every method of the class, which is the same mistake.
            if (r.types.isEmpty() || (r.boundary.isEmpty() == r.entrypoint.isEmpty())
                || (!r.entrypoint.isEmpty() && r.methods.isEmpty())) {
                continue;
            }
            extending.add(r);
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

    /** A matching rule, and the blind spot the conditioned rules before it left. */
    record Match(Boundary rule, String blind) { }

    /** The first matching rule, so order in the YAML is meaningful. A rule conditioned on an
     *  argument is decided on {@code texts}; one that cannot be decided does not match, and
     *  its {@code undecided} sentence is the blind spot of the rule that does. */
    Match matchCall(String dotted, List<String> texts, List<Boolean> literal) {
        List<String> blind = new ArrayList<>();
        for (Boundary b : boundaries) {
            if (!b.matches(dotted)) {
                continue;
            }
            if (b.whenIndex != null) {
                Boolean yes = b.decide(texts, literal);
                if (yes == null && !b.undecided.isEmpty()) {
                    blind.add(b.undecided);
                }
                if (!Boolean.TRUE.equals(yes)) {
                    continue;
                }
            }
            return new Match(b, String.join("; ", blind));
        }
        return new Match(null, String.join("; ", blind));
    }

    /**
     * The rule a call is a touch by, <b>where the checker has typed it</b>: {@code qualified}
     * is the declaring type's own name and the method's, {@code jakarta.ws.rs.client
     * .SyncInvoker.get}. Matched against {@code exact} entries and nothing else, as Go's
     * typed methods are: {@code method}, {@code prefix} and {@code contains} are written for
     * a spelling, and a spelling's looseness has no business deciding a type's name. A rule
     * conditioned on an argument is left to the file's own pass, which has the arguments.
     */
    Boundary typed(String qualified) {
        for (Boundary b : boundaries) {
            if (b.whenIndex == null && b.exact.contains(qualified)) {
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
