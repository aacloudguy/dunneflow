package dunneflow.reader;

import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.Tree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreePath;
import com.sun.source.util.TreePathScanner;
import com.sun.source.util.Trees;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.function.Function;
import javax.lang.model.element.Element;
import javax.lang.model.element.ElementKind;
import javax.lang.model.element.ExecutableElement;
import javax.lang.model.element.Modifier;
import javax.lang.model.element.TypeElement;
import javax.lang.model.util.Elements;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticListener;
import javax.tools.JavaFileObject;

/**
 * Every call's far end, by javac.
 *
 * <p><b>One compilation, every file in it.</b> The tree is parsed in one {@link JavacTask},
 * every unit is walked by the extractor's own walk <i>before</i> attribution (so each site
 * carries the {@code site_id} the facts carry, and a member javac adds later cannot move an
 * ordinal), and then {@code analyze()} attributes the lot. A call's target is
 * {@code Trees.getElement} of the site, and its declaration, where the tree holds one, is
 * named to the host as a <b>file, a line and a name</b>, never an id (PLAN-v2 §1g). The
 * line is {@link Extract#declStart}'s, which is the line the routine was stored at.
 *
 * <p><b>Attribution does not stop at the first error.</b> A tree read without its
 * dependencies is the ordinary case, and javac's default is to stop attributing once any
 * error is reported, which would leave every class after the first missing import without
 * an answer. {@code -XDshould-stop.ifError=FLOW} keeps going to the end of attribution, as
 * the IDEs built on javac do. An unresolvable receiver is then an error type, and its call
 * is {@code untyped}: said, never guessed (rule 1).
 *
 * <p><b>Dispatch, as Tom decided on 2026-11-01.</b> An edge to the method javac resolved is
 * CERTAIN where nothing else can answer: the method is static, private or final, or a
 * constructor, or its class is final (a record is), or the call is {@code super.m()}, or
 * nothing in the tree overrides it. Otherwise the call is {@code dynamic}, with
 * {@code candidates} set to the definitions in the tree that can answer it: an interface or
 * abstract method, or one the tree overrides. That is Go's interface shape, and rule 1: a
 * guess at one of several bodies is a wrong edge as often as it is a right one. A method
 * of the JDK's, or of anything else this tree does not hold, is {@code outside}, with its
 * qualified name as the frontier, unless the tree overrides it, in which case it is
 * {@code dynamic} too: {@code r.run()} on a {@code Runnable} reaches the anonymous class
 * that implements it.
 *
 * <p><b>The residue, stated.</b> javac reads Java and nothing else, so a call from Java
 * into the Kotlin of a mixed tree is {@code untyped}. Annotation processors do not run
 * ({@code -proc:none}), so a Lombok getter or a Dagger component is not there to resolve
 * to. A dependency that is not on this machine is a missing class.
 */
public final class Edges {
    private Edges() {}

    public static final class Found {
        final List<Facts.SuppliedEdge> edges = new ArrayList<>();
        final List<String> notes = new ArrayList<>();
        long outside;
        long unknown;
        /** What was read beyond the tree, and what was looked for and is not here. */
        final List<String> readBeyond = new ArrayList<>();
        final List<String> notPresent = new ArrayList<>();
    }

    /** One call the walk recorded, held until attribution can answer it. */
    private record Site(CompilationUnitTree unit, Tree node, String siteId, String caller,
                        String dotted, boolean construction) {}

    static Found collect(Path root, List<Path> files, Rules rules, Function<Path, String> rel) {
        Found found = new Found();
        if (files.isEmpty()) {
            return found;
        }
        List<Extract.Source> sources = new ArrayList<>();
        Map<String, String> texts = new HashMap<>();
        // javac wraps every file object it is handed, so a unit is ours by its URI and never
        // by its class: a cast was a ClassCastException on the first tree it met.
        Map<java.net.URI, Extract.Source> byUri = new HashMap<>();
        for (Path f : files) {
            try {
                String r = rel.apply(f);
                String text = Text.readSource(f);
                Extract.Source src = new Extract.Source(r, text);
                sources.add(src);
                byUri.put(src.toUri(), src);
                texts.put(r, text);
            } catch (IOException e) {
                found.notes.add("edges: " + f + " could not be read: " + e);
            }
        }
        long[] errors = {0};
        Map<String, Integer> missing = new TreeMap<>();
        DiagnosticListener<JavaFileObject> listen = d -> {
            if (d.getKind() == Diagnostic.Kind.ERROR) {
                errors[0]++;
                if ("compiler.err.cant.resolve.location".equals(d.getCode())
                    || "compiler.err.doesnt.exist".equals(d.getCode())) {
                    String m = d.getMessage(java.util.Locale.ROOT).lines().findFirst().orElse("");
                    missing.merge(m, 1, Integer::sum);
                }
            }
        };
        // The jars the build files name, where this machine holds them (`Deps`): never
        // fetched. Put on a file manager of the edge pass's own, so a file's facts never
        // depend on what happens to be in somebody's cache (rule 95).
        Deps.Result deps = Deps.resolve(root);
        found.readBeyond.addAll(deps.read);
        found.notPresent.addAll(deps.absent);
        found.notes.addAll(deps.notes);
        javax.tools.StandardJavaFileManager fm = Extract.compiler().getStandardFileManager(
            null, java.util.Locale.ROOT, java.nio.charset.StandardCharsets.UTF_8);
        try {
            fm.setLocationFromPaths(javax.tools.StandardLocation.CLASS_PATH, deps.jars);
        } catch (IOException e) {
            found.notes.add("edges: the dependency jars could not be put on the classpath: " + e);
        }
        JavacTask task = (JavacTask) Extract.compiler().getTask(
            null, fm, listen,
            List.of("-proc:none", "-Xlint:none", "-nowarn", "-implicit:none",
                "-XDshould-stop.ifError=FLOW", "-XDshould-stop.ifNoError=FLOW"),
            null, sources);
        List<Site> sites = new ArrayList<>();
        List<CompilationUnitTree> units = new ArrayList<>();
        try {
            for (CompilationUnitTree unit : task.parse()) {
                units.add(unit);
                String r = byUri.get(unit.getSourceFile().toUri()).rel;
                Extract.walk(r, texts.get(r), unit, task, rules,
                    (node, siteId, caller, dotted, atBoundary, construction) -> {
                        // Rule 2: a call that touches a boundary is never also an edge.
                        if (!atBoundary) {
                            sites.add(new Site(unit, node, siteId, caller, dotted, construction));
                        }
                    });
            }
            task.analyze();
        } catch (IOException e) {
            found.notes.add("edges: javac could not read the text it was handed: " + e);
            return found;
        } catch (RuntimeException e) {
            // javac crashed on this tree. Nothing is guessed: every call is left external,
            // and the host counts them as unresolved.
            found.notes.add("edges: javac failed attributing this tree: " + Main.describe(e));
            return found;
        }
        if (errors[0] > 0) {
            found.notes.add("edges: javac reported " + errors[0] + " errors attributing "
                + units.size() + " files; calls whose receiver it could not type are "
                + "`untyped`, never guessed");
            missing.entrySet().stream().sorted((a, b) -> b.getValue() - a.getValue()).limit(8)
                .forEach(e -> found.notes.add("  " + e.getValue() + "x " + e.getKey()));
        }
        new Resolver(task, units, texts, byUri, found).resolve(sites);
        return found;
    }

    /** Attribution's answers, turned into the host's terms. */
    private static final class Resolver {
        final Trees trees;
        final Elements elements;
        final javax.lang.model.util.Types types;
        final SourcePositions pos;
        final Map<String, String> texts;
        final Map<java.net.URI, Extract.Source> byUri;
        final Found found;
        /** Every method the tree declares, by simple name: who can override whom. */
        final Map<String, List<ExecutableElement>> byName = new HashMap<>();
        /** Which of those has a body, and so is a routine. */
        final Set<ExecutableElement> bodies = java.util.Collections.newSetFromMap(
            new IdentityHashMap<>());
        final Map<Element, List<ExecutableElement>> overriders = new IdentityHashMap<>();

        Resolver(JavacTask task, List<CompilationUnitTree> units, Map<String, String> texts,
                 Map<java.net.URI, Extract.Source> byUri, Found found) {
            this.trees = Trees.instance(task);
            this.elements = task.getElements();
            this.types = task.getTypes();
            this.pos = trees.getSourcePositions();
            this.texts = texts;
            this.byUri = byUri;
            this.found = found;
            for (CompilationUnitTree unit : units) {
                new TreePathScanner<Void, Void>() {
                    @Override
                    public Void visitMethod(MethodTree m, Void v) {
                        if (trees.getElement(getCurrentPath()) instanceof ExecutableElement e) {
                            byName.computeIfAbsent(e.getSimpleName().toString(),
                                k -> new ArrayList<>()).add(e);
                            if (m.getBody() != null) {
                                bodies.add(e);
                            }
                        }
                        return super.visitMethod(m, v);
                    }
                }.scan(unit, null);
            }
        }

        void resolve(List<Site> sites) {
            for (Site s : sites) {
                Facts.SuppliedEdge e = new Facts.SuppliedEdge();
                e.site_id = s.siteId();
                e.caller_id = s.caller();
                answer(s, e);
                if (e.file.isEmpty()) {
                    if ("outside".equals(e.reason)) {
                        found.outside++;
                    } else {
                        found.unknown++;
                    }
                }
                found.edges.add(e);
            }
        }

        void answer(Site s, Facts.SuppliedEdge e) {
            Element el;
            try {
                el = trees.getElement(TreePath.getPath(s.unit(), s.node()));
            } catch (RuntimeException ex) {
                el = null;
            }
            if (!(el instanceof ExecutableElement target)) {
                // No symbol: a receiver javac could not type, which is a missing class,
                // a Kotlin file, generated code, or a dependency that is not here.
                e.reason = "untyped";
                e.frontier = s.dotted();
                return;
            }
            TypeElement owner = target.getEnclosingElement() instanceof TypeElement t ? t : null;
            if (guessed(s, target, owner)) {
                // javac chose one of several overloads with an argument it could not type,
                // which is a pick and not an answer: `width(m.part())` went to `width(int)`
                // with nothing to say it was not `width(String)` (rule 1).
                e.reason = "untyped";
                e.frontier = s.dotted();
                return;
            }
            if (s.construction() && owner != null && owner.getNestingKind().name().equals("ANONYMOUS")) {
                // `new Runnable() { … }` builds a class with no name and no structure.
                e.reason = "unfollowed";
                e.frontier = "anonymous " + s.dotted();
                return;
            }
            TreePath decl = trees.getPath(target);
            Extract.Source home = decl == null ? null : ours(decl.getCompilationUnit());
            TypeElement receiver = receiverType(s, target, owner);
            if (home == null) {
                List<ExecutableElement> over = overridersOf(target, receiver);
                if (!nonVirtual(s, target, owner) && !over.isEmpty()) {
                    e.reason = "dynamic";
                    e.candidates = over.size();
                    e.frontier = qualified(target);
                    answers(over, e);
                    return;
                }
                e.reason = "outside";
                e.how = "symbol";
                e.frontier = qualified(target);
                return;
            }
            if (elements.getOrigin(target) != Elements.Origin.EXPLICIT) {
                implicit(s, target, owner, e);
                return;
            }
            boolean hasBody = bodies.contains(target);
            List<ExecutableElement> over = overridersOf(target, receiver);
            if (nonVirtual(s, target, owner) && hasBody) {
                pointAt(decl, target, e);
                e.how = "non-virtual";
                return;
            }
            if (over.isEmpty() && hasBody) {
                pointAt(decl, target, e);
                e.how = "unoverridden";
                return;
            }
            int answering = (hasBody ? 1 : 0)
                + (int) over.stream().filter(bodies::contains).count();
            if (answering == 0) {
                // An interface no class in the tree implements: Spring Data writes the
                // repository at run time, and a library's caller writes the rest.
                e.reason = "outside";
                e.how = "unimplemented";
                e.frontier = qualified(target);
                return;
            }
            e.reason = "dynamic";
            e.candidates = answering;
            e.frontier = qualified(target);
            List<ExecutableElement> all = new ArrayList<>();
            if (hasBody) {
                all.add(target);
            }
            all.addAll(over);
            answers(all, e);
        }

        /** Where each body that may answer a dispatched call is, by the same line rule an
         *  edge's target is named by (`schema.Answer`). Only bodies: a declaration with none
         *  is not a routine, and could not be linked to one. */
        void answers(List<ExecutableElement> bodiesThatMay, Facts.SuppliedEdge e) {
            for (ExecutableElement m : bodiesThatMay) {
                if (!bodies.contains(m)) {
                    continue;
                }
                TreePath decl = trees.getPath(m);
                if (decl == null || ours(decl.getCompilationUnit()) == null) {
                    continue;
                }
                Facts.SuppliedEdge at = new Facts.SuppliedEdge();
                pointAt(decl, m, at);
                Facts.Answer a = new Facts.Answer();
                a.file = at.file;
                a.line = at.line;
                a.name = at.name;
                e.answers.add(a);
            }
        }

        /** Did javac resolve this call with an argument it could not type, among several
         *  overloads that could have taken it? Then its answer is a choice it was forced
         *  to make, and is not one this map may draw. */
        boolean guessed(Site s, ExecutableElement target, TypeElement owner) {
            List<? extends com.sun.source.tree.ExpressionTree> args =
                s.node() instanceof MethodInvocationTree mi ? mi.getArguments()
                : s.node() instanceof com.sun.source.tree.NewClassTree nc ? nc.getArguments()
                : List.of();
            boolean blind = false;
            for (com.sun.source.tree.ExpressionTree a : args) {
                javax.lang.model.type.TypeMirror t;
                try {
                    t = trees.getTypeMirror(TreePath.getPath(s.unit(), a));
                } catch (RuntimeException ex) {
                    t = null;
                }
                if (t == null || t.getKind() == javax.lang.model.type.TypeKind.ERROR) {
                    blind = true;
                    break;
                }
            }
            if (!blind || owner == null) {
                return false;
            }
            int rivals = 0;
            try {
                for (Element m : elements.getAllMembers(owner)) {
                    if (m.getKind() == target.getKind()
                        && m.getSimpleName().contentEquals(target.getSimpleName())) {
                        rivals++;
                    }
                }
            } catch (RuntimeException ex) {
                return true; // its members cannot be listed, so nothing rules a rival out
            }
            return rivals > 1;
        }

        /** A member javac declared and the source did not: a default constructor, a
         *  record's canonical constructor and accessors, an enum's {@code values()}. A
         *  constructor builds one of the program's own types, which has a structure to
         *  point at (`SuppliedEdge.constructs`); anything else has no routine at all. */
        void implicit(Site s, ExecutableElement target, TypeElement owner, Facts.SuppliedEdge e) {
            if (target.getKind() == ElementKind.CONSTRUCTOR && owner != null) {
                TreePath cls = trees.getPath(owner);
                Extract.Source src = cls == null ? null : ours(cls.getCompilationUnit());
                if (src != null && cls.getLeaf() instanceof ClassTree ct) {
                    e.constructs = qualnameOf(cls);
                    e.file = src.rel;
                    e.line = lineOf(cls.getCompilationUnit(), src.rel, ct, ct.getModifiers());
                    e.name = owner.getSimpleName().toString();
                    e.how = "implicit constructor";
                    return;
                }
            }
            e.reason = "unfollowed";
            e.frontier = qualified(target) + " (declared by the compiler, not the source)";
        }

        /** The class's qualname as the extractor spells it: the package, then each
         *  enclosing class. Only named classes reach here (an anonymous one was refused). */
        String qualnameOf(TreePath cls) {
            List<String> parts = new ArrayList<>();
            for (TreePath p = cls; p != null; p = p.getParentPath()) {
                if (p.getLeaf() instanceof ClassTree c) {
                    parts.add(0, c.getSimpleName().toString());
                } else if (p.getLeaf() instanceof MethodTree m) {
                    // A local class carries its method, as the extractor's does (rule 10).
                    parts.add(0, m.getReturnType() == null
                        ? enclosingClassName(p) : m.getName().toString());
                }
            }
            String pkg = cls.getCompilationUnit().getPackageName() == null ? ""
                : cls.getCompilationUnit().getPackageName().toString();
            return pkg.isEmpty() ? String.join(".", parts) : pkg + "." + String.join(".", parts);
        }

        static String enclosingClassName(TreePath p) {
            for (TreePath q = p.getParentPath(); q != null; q = q.getParentPath()) {
                if (q.getLeaf() instanceof ClassTree c) {
                    return c.getSimpleName().toString();
                }
            }
            return "";
        }

        /** The source this unit was read from, if it is one of this tree's. */
        Extract.Source ours(CompilationUnitTree unit) {
            return unit.getSourceFile() == null ? null : byUri.get(unit.getSourceFile().toUri());
        }

        void pointAt(TreePath decl, ExecutableElement target, Facts.SuppliedEdge e) {
            Extract.Source src = ours(decl.getCompilationUnit());
            MethodTree m = (MethodTree) decl.getLeaf();
            e.file = src.rel;
            e.line = lineOf(decl.getCompilationUnit(), src.rel, m, m.getModifiers());
            e.name = target.getKind() == ElementKind.CONSTRUCTOR
                ? target.getEnclosingElement().getSimpleName().toString()
                : target.getSimpleName().toString();
        }

        long lineOf(CompilationUnitTree unit, String rel, Tree decl,
                    com.sun.source.tree.ModifiersTree mods) {
            long at = Extract.declStart(pos, unit, texts.get(rel), decl, mods);
            return unit.getLineMap().getLineNumber(at);
        }

        /** Nothing else can answer: no override is possible, or the call names its body. */
        boolean nonVirtual(Site s, ExecutableElement target, TypeElement owner) {
            Set<Modifier> m = target.getModifiers();
            if (target.getKind() == ElementKind.CONSTRUCTOR || m.contains(Modifier.STATIC)
                || m.contains(Modifier.PRIVATE) || m.contains(Modifier.FINAL)) {
                return true;
            }
            if (owner != null && (owner.getModifiers().contains(Modifier.FINAL)
                || owner.getKind() == ElementKind.RECORD)) {
                return true;
            }
            // `super.m()` is the one call that names a body rather than a slot.
            return s.node() instanceof MethodInvocationTree mi
                && mi.getMethodSelect() instanceof MemberSelectTree ms
                && ms.getExpression() instanceof IdentifierTree id
                && id.getName().contentEquals("super");
        }

        /** The methods in the tree that can answer this call instead of {@code target}: the
         *  ones that override it <b>in a subtype of the receiver's static type</b>. A sibling
         *  class's override can never answer a call on this receiver: {@code Event}'s
         *  {@code setDeviceId()} is {@code Message}'s, whatever {@code Command}, another
         *  subclass of {@code Message}, does with its own (traccar, 2026-11-01). */
        List<ExecutableElement> overridersOf(ExecutableElement target, TypeElement receiver) {
            List<ExecutableElement> all = allOverriders(target);
            if (receiver == null || all.isEmpty()) {
                return all;
            }
            javax.lang.model.type.TypeMirror r = types.erasure(receiver.asType());
            List<ExecutableElement> out = new ArrayList<>();
            for (ExecutableElement m : all) {
                if (types.isSubtype(types.erasure(m.getEnclosingElement().asType()), r)) {
                    out.add(m);
                }
            }
            return out;
        }

        /** The class whose instance the call is made on, as the source types it: the
         *  receiver expression's type, or for a bare {@code m()} the innermost enclosing
         *  class that has {@code m} as a member. Null where it cannot be said, which counts
         *  every override rather than guessing which (rule 1). */
        TypeElement receiverType(Site s, ExecutableElement target, TypeElement owner) {
            if (!(s.node() instanceof MethodInvocationTree mi) || owner == null) {
                return null;
            }
            try {
                if (mi.getMethodSelect() instanceof MemberSelectTree ms) {
                    javax.lang.model.type.TypeMirror t = trees.getTypeMirror(
                        TreePath.getPath(s.unit(), ms.getExpression()));
                    if (t instanceof javax.lang.model.type.TypeVariable tv) {
                        t = tv.getUpperBound();
                    }
                    return t != null && types.asElement(t) instanceof TypeElement te ? te : null;
                }
                javax.lang.model.type.TypeMirror want = types.erasure(owner.asType());
                for (TreePath p = TreePath.getPath(s.unit(), s.node()); p != null;
                     p = p.getParentPath()) {
                    if (p.getLeaf() instanceof ClassTree
                        && trees.getElement(p) instanceof TypeElement te
                        && types.isSubtype(types.erasure(te.asType()), want)) {
                        return te;
                    }
                }
            } catch (RuntimeException ex) {
                return null;
            }
            return null;
        }

        /** Every method in the tree that overrides this one, asked once per method. */
        List<ExecutableElement> allOverriders(ExecutableElement target) {
            return overriders.computeIfAbsent(target, t -> {
                List<ExecutableElement> out = new ArrayList<>();
                for (ExecutableElement m : byName.getOrDefault(
                        target.getSimpleName().toString(), List.of())) {
                    if (m != target && m.getEnclosingElement() instanceof TypeElement mt
                        && elements.overrides(m, target, mt)) {
                        out.add(m);
                    }
                }
                return out;
            });
        }

        /** {@code java.sql.Statement.executeQuery}: the declaring type's own name. */
        static String qualified(ExecutableElement target) {
            String owner = target.getEnclosingElement() instanceof TypeElement t
                ? t.getQualifiedName().toString() : target.getEnclosingElement().toString();
            String name = target.getKind() == ElementKind.CONSTRUCTOR
                ? target.getEnclosingElement().getSimpleName().toString()
                : target.getSimpleName().toString();
            return owner + "." + name;
        }
    }
}
