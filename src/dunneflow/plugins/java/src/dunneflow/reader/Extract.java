package dunneflow.reader;

import com.sun.source.tree.AnnotationTree;
import com.sun.source.tree.AssignmentTree;
import com.sun.source.tree.BlockTree;
import com.sun.source.tree.CaseTree;
import com.sun.source.tree.CatchTree;
import com.sun.source.tree.ClassTree;
import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.tree.DoWhileLoopTree;
import com.sun.source.tree.EnhancedForLoopTree;
import com.sun.source.tree.ExpressionStatementTree;
import com.sun.source.tree.ExpressionTree;
import com.sun.source.tree.ForLoopTree;
import com.sun.source.tree.IdentifierTree;
import com.sun.source.tree.IfTree;
import com.sun.source.tree.ImportTree;
import com.sun.source.tree.LambdaExpressionTree;
import com.sun.source.tree.LineMap;
import com.sun.source.tree.LiteralTree;
import com.sun.source.tree.MemberSelectTree;
import com.sun.source.tree.MethodInvocationTree;
import com.sun.source.tree.MethodTree;
import com.sun.source.tree.ModifiersTree;
import com.sun.source.tree.NewClassTree;
import com.sun.source.tree.ParameterizedTypeTree;
import com.sun.source.tree.ParenthesizedTree;
import com.sun.source.tree.StatementTree;
import com.sun.source.tree.SwitchExpressionTree;
import com.sun.source.tree.SwitchTree;
import com.sun.source.tree.Tree;
import com.sun.source.tree.TryTree;
import com.sun.source.tree.TypeCastTree;
import com.sun.source.tree.VariableTree;
import com.sun.source.tree.WhileLoopTree;
import com.sun.source.util.JavacTask;
import com.sun.source.util.SourcePositions;
import com.sun.source.util.TreeScanner;
import com.sun.source.util.Trees;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import javax.lang.model.element.Modifier;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.SimpleJavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/**
 * One file's facts.
 *
 * <p>{@code plugins/rust/src/extract.rs} and {@code plugins/typescript/src/extract.ts} are
 * the models, and this agrees with them wherever the languages let it. Where Java differs,
 * the difference is said at the place it is decided.
 *
 * <p><b>Identity first</b> (LANGUAGES.md: decide it before writing the reader). The module
 * is the file's dotted path, as every reader's is. The <b>qualname is the package's</b>,
 * as Kotlin's is, because that is how a Java author addresses a method: a class is
 * {@code pkg.Outer.Inner}, a method {@code pkg.Outer.m}, a constructor
 * {@code pkg.Outer.Outer} (Java writes it with the class's name, as C++ does). A local
 * class carries the method it is declared in, {@code pkg.Outer.m.Local.run}, and an
 * anonymous one takes javac's {@code $n}, counted within its method: {@code pkg.Outer.m.$1.run}
 * (rule 10).
 * Overloads take an ordinal through {@code definition_id}, so the second {@code m} in a
 * file is {@code #2}: that is order-dependent, which is the same stated residue Kotlin's
 * and C++'s ordinals carry. Nothing else mints an id.
 *
 * <p><b>A method with no body is not a routine</b>: an interface's or an abstract class's
 * declaration is a shape another class fills, and it is recorded as a field of the
 * structure that declares it (C++'s lesson, LANGUAGES.md).
 *
 * <p><b>A lambda is not a routine.</b> What it calls belongs to the method it is written
 * in. Streams are the house style, so {@code .forEach(x -> …)} and its kin are recorded
 * as a COMPREHENSION span where the function is written in place, as TypeScript's are;
 * a method reference ({@code this::f}) passes a name and is not a call.
 *
 * <p><b>What runs outside any method is the module scope's</b> (rule 18): a field's
 * initialiser and an initialiser block both run at construction or class load, and no
 * routine in the source is where they are written.
 *
 * <p><b>javac is given the host's text, never the file.</b> {@link Source} hands it
 * {@code SOURCE_TEXT}, so every offset javac reports is into the text the host hashed. Every
 * slice is taken from that text and never re-rendered, so {@code header} and
 * {@code callee_expr} are what the author wrote.
 */
public final class Extract {
    public static final String MODULE_SCOPE = "<module>";
    private static final int LITERAL_MIN = 3;
    private static final int LITERAL_MAX = 200_000;
    /** The stream and collection operations that take a function and loop over it. */
    private static final Set<String> ITERATION = Set.of(
        "forEach", "forEachOrdered", "map", "mapToInt", "mapToLong", "mapToDouble",
        "mapToObj", "flatMap", "filter", "reduce", "anyMatch", "allMatch", "noneMatch",
        "removeIf", "replaceAll", "takeWhile", "dropWhile", "peek", "computeIfAbsent");

    private static JavaCompiler compiler;
    private static StandardJavaFileManager files;

    /** The system compiler, asked for once. The build already refused a JRE (Build.java),
     *  so this can be missing only on a machine whose JDK changed under a built reader. */
    static synchronized JavaCompiler compiler() {
        if (compiler == null) {
            compiler = ToolProvider.getSystemJavaCompiler();
            if (compiler == null) {
                throw new IllegalStateException(
                    "this `java` has no compiler (a JRE, not a JDK); the Java reader needs a JDK");
            }
            files = compiler.getStandardFileManager(null, Locale.ROOT, StandardCharsets.UTF_8);
        }
        return compiler;
    }

    static synchronized StandardJavaFileManager fileManager() {
        compiler();
        return files;
    }

    /** The host's text, as a file javac can read. */
    static final class Source extends SimpleJavaFileObject {
        final String rel;
        private final String text;

        Source(String rel, String text) {
            super(uri(rel), Kind.SOURCE);
            this.rel = rel;
            this.text = text;
        }

        static URI uri(String rel) {
            try {
                return new URI("mem", null, "/" + rel, null);
            } catch (URISyntaxException e) {
                throw new IllegalArgumentException(rel, e);
            }
        }

        @Override
        public CharSequence getCharContent(boolean ignoreEncodingErrors) {
            return text;
        }
    }

    /** {@code src/main/java/a/B.java} -> {@code src.main.java.a.B}: the file's own dotted
     *  path, as every reader spells a module, so {@code probe.java} is module {@code probe}
     *  beside {@code probe.go} and {@code probe.py} ({@code test_identity}). */
    public static String moduleName(String rel) {
        String stem = rel.endsWith(".java") ? rel.substring(0, rel.length() - 5) : rel;
        List<String> parts = new ArrayList<>();
        for (String p : stem.split("/")) {
            if (!p.isEmpty()) {
                parts.add(p);
            }
        }
        return String.join(".", parts);
    }

    /** The trees and the errors of one parse, with no attribution: a file's facts are its
     *  own, so the cache key that is its hash stays the whole of what they depend on
     *  (rule 95). Attribution is the edge pass's. */
    static final class Parsed {
        final CompilationUnitTree unit;
        final JavacTask task;
        final List<String> errors;

        Parsed(CompilationUnitTree unit, JavacTask task, List<String> errors) {
            this.unit = unit;
            this.task = task;
            this.errors = errors;
        }
    }

    static Parsed parse(String rel, String source) {
        DiagnosticCollector<JavaFileObject> diags = new DiagnosticCollector<>();
        JavacTask task = (JavacTask) compiler().getTask(
            null, fileManager(), diags, List.of("-proc:none", "-Xlint:none"), null,
            List.of(new Source(rel, source)));
        CompilationUnitTree unit;
        try {
            Iterable<? extends CompilationUnitTree> units = task.parse();
            unit = units.iterator().hasNext() ? units.iterator().next() : null;
        } catch (java.io.IOException e) {
            throw new IllegalStateException("javac could not read text it was handed", e);
        }
        List<String> errors = new ArrayList<>();
        for (Diagnostic<? extends JavaFileObject> d : diags.getDiagnostics()) {
            if (d.getKind() == Diagnostic.Kind.ERROR) {
                errors.add(d.getLineNumber() + ":" + d.getColumnNumber() + " "
                    + d.getMessage(Locale.ROOT));
            }
        }
        return new Parsed(unit, task, errors);
    }

    public static Facts.FileFacts extractFile(String rel, String source, Rules rules) {
        Facts.FileFacts ff = new Facts.FileFacts();
        ff.path = rel;
        ff.lang = Main.LANG;
        ff.module = moduleName(rel);
        ff.content_hash = Ids.hashSource(source);
        Parsed parsed = parse(rel, source);
        if (!parsed.errors.isEmpty() || parsed.unit == null) {
            // A parse error is a fact about the file, never a failure of the reader: the
            // host records it and the rest of the tree is read.
            ff.errors.addAll(parsed.errors);
            return ff;
        }
        new Ex(rel, ff.module, source, parsed.unit, parsed.task, rules, ff, null).run();
        return ff;
    }

    /** What the edge pass needs to know about one call, told by the same walk that minted
     *  its {@code site_id}, so the two passes cannot disagree about which call is which. */
    interface SiteSink {
        void site(Tree node, String siteId, String callerId, String dotted, boolean atBoundary,
                  boolean construction);
    }

    /** One file's facts out of a tree some other task parsed: the edge pass's entry, which
     *  walks every file of a compilation <i>before</i> javac attributes it, so a member
     *  javac adds (a default constructor, a record's accessors) can never move an ordinal. */
    static Facts.FileFacts walk(String rel, String source, CompilationUnitTree unit,
                                JavacTask task, Rules rules, SiteSink sink) {
        Facts.FileFacts ff = new Facts.FileFacts();
        ff.path = rel;
        ff.lang = Main.LANG;
        ff.module = moduleName(rel);
        ff.content_hash = Ids.hashSource(source);
        new Ex(rel, ff.module, source, unit, task, rules, ff, sink).run();
        return ff;
    }

    /** Where a declaration starts once its annotations are behind it: a routine's first
     *  line is its modifiers or its type, never an {@code @Override} two lines up. The one
     *  function both passes use, so a target's line is the line its routine was stored at. */
    static long declStart(SourcePositions pos, CompilationUnitTree unit, String src, Tree decl,
                          ModifiersTree mods) {
        long s = pos.getStartPosition(unit, decl);
        if (mods != null) {
            for (AnnotationTree a : mods.getAnnotations()) {
                s = Math.max(s, pos.getEndPosition(unit, a));
            }
        }
        while (s >= 0 && s < src.length() && Character.isWhitespace(src.charAt((int) s))) {
            s++;
        }
        return s;
    }

    // =================================================================== walk === //

    /** One file's walk. A {@link TreeScanner} whose overrides are the facts. */
    private static final class Ex extends TreeScanner<Void, Void> {
        final String path;
        final String module;
        final String src;
        final Rules rules;
        final Facts.FileFacts ff;
        final CompilationUnitTree unit;
        final SourcePositions pos;
        final LineMap lines;
        final String pkg;
        final Comments.Scan scanned;
        final int[] docEnds;
        final SiteSink sink;

        final List<Facts.Routine> routines = new ArrayList<>();
        /** Indices into {@code routines}, innermost last. */
        final Deque<Integer> scope = new ArrayDeque<>();
        /** The qualified name of each open class, innermost last, and its simple name. */
        final Deque<String[]> classes = new ArrayDeque<>();
        final Facts.Routine moduleScope;
        boolean moduleClaimed;
        final Map<String, Long> seenQual = new HashMap<>();
        final Map<String, Long> seenType = new HashMap<>();
        final Map<String, Long> callOrd = new HashMap<>();
        final Map<String, Long> ctrlOrd = new HashMap<>();
        /** The anonymous classes counted so far, per method or class they are written in. */
        final Map<String, Integer> anonymous = new HashMap<>();
        /** Calls whose value is thrown away ({@code java.yaml} on {@code unawaited_async}). */
        final Set<Tree> discarded = java.util.Collections.newSetFromMap(new IdentityHashMap<>());
        long depth;
        /** The enum constant whose body is the next class visited. */
        String enumBody;

        Ex(String rel, String module, String src, CompilationUnitTree unit, JavacTask task,
           Rules rules, Facts.FileFacts ff, SiteSink sink) {
            this.path = rel;
            this.module = module;
            this.src = src;
            this.rules = rules;
            this.ff = ff;
            this.sink = sink;
            this.unit = unit;
            this.pos = Trees.instance(task).getSourcePositions();
            this.lines = unit.getLineMap();
            this.pkg = unit.getPackageName() == null ? "" : text(unit.getPackageName());
            this.scanned = Comments.scan(src);
            // The scan finds blocks in text order, so their ends are already sorted.
            this.docEnds = scanned.docs.stream().mapToInt(d -> d.end).toArray();
            this.moduleScope = moduleScope(rel, module, src);
        }

        void run() {
            for (ImportTree imp : unit.getImports()) {
                importRec(imp);
            }
            for (Tree t : unit.getTypeDecls()) {
                scan(t, null);
            }
            landComments();
            if (moduleClaimed) {
                routines.add(0, moduleScope);
            }
            ff.routines.addAll(routines);
            // Always sent, claimed or not: a string names its owner before anybody knows
            // whether it is a fact (rule 96, `extract.ts:moduleScope`).
            ff.module_scope = moduleScope;
        }

        // -------------------------------------------------------- positions --- //

        long start(Tree t) {
            return pos.getStartPosition(unit, t);
        }

        long end(Tree t) {
            return pos.getEndPosition(unit, t);
        }

        long line(long offset) {
            return offset < 0 ? 0 : lines.getLineNumber(offset);
        }

        long lineOf(Tree t) {
            return line(start(t));
        }

        long endLineOf(Tree t) {
            long e = end(t);
            return e <= 0 ? lineOf(t) : line(Math.max(0, e - 1));
        }

        /** A node as written, sliced from the host's text and never re-rendered. */
        String text(Tree t) {
            if (t == null) {
                return "";
            }
            long a = start(t);
            long b = end(t);
            if (a < 0 || b < a || b > src.length()) {
                return "";
            }
            return src.substring((int) a, (int) b);
        }

        long declStart(Tree decl, ModifiersTree mods) {
            return Extract.declStart(pos, unit, src, decl, mods);
        }

        /** The Javadoc that ends just before a declaration, with only blank text between.
         *  Only the last block ending at or before the declaration can be its Javadoc, so it
         *  is found by a binary search and checked once. Scanning every block for every
         *  declaration, with a substring each, was cubic on the Android SDK's largest files
         *  and held one reader at 100% for 25 minutes (rule 55: bound the work). */
        String javadocFor(Tree decl) {
            long s = start(decl);
            int lo = 0;
            int hi = docEnds.length - 1;
            int at = -1;
            while (lo <= hi) {
                int mid = (lo + hi) >>> 1;
                if (docEnds[mid] <= s) {
                    at = mid;
                    lo = mid + 1;
                } else {
                    hi = mid - 1;
                }
            }
            if (at < 0) {
                return null;
            }
            Comments.Doc d = scanned.docs.get(at);
            for (int i = d.end; i < s; i++) {
                if (!Character.isWhitespace(src.charAt(i))) {
                    return null;
                }
            }
            return d.text.isEmpty() ? null : d.text;
        }

        // ------------------------------------------------------------ owner --- //

        String ownerId() {
            Integer i = scope.peekLast();
            if (i != null) {
                return routines.get(i).id;
            }
            moduleClaimed = true;
            return moduleScope.id;
        }

        String classPrefix() {
            String[] top = classes.peekLast();
            return top != null ? top[0] : pkg;
        }

        static String join(String a, String b) {
            return a.isEmpty() ? b : a + "." + b;
        }

        // ---------------------------------------------------------- imports --- //

        void importRec(ImportTree imp) {
            String q = text(imp.getQualifiedIdentifier()).replaceAll("\\s+", "");
            int dot = q.lastIndexOf('.');
            Facts.ImportRec r = new Facts.ImportRec();
            r.module = dot > 0 ? q.substring(0, dot) : q;
            r.name = dot > 0 ? q.substring(dot + 1) : q;
            r.alias = "";
            r.is_from = dot > 0;
            r.line = lineOf(imp);
            ff.imports.add(r);
        }

        // ---------------------------------------------------------- classes --- //

        @Override
        public Void visitClass(ClassTree c, Void v) {
            String simple = c.getSimpleName().toString();
            String prefix;
            Integer enclosingRoutine = scope.peekLast();
            boolean inBody = enclosingRoutine != null
                && (classes.isEmpty() || routineInside(enclosingRoutine));
            if (simple.isEmpty() && enumBody != null) {
                simple = enumBody;
                enumBody = null;
                prefix = classPrefix();
            } else if (simple.isEmpty()) {
                // An anonymous class takes javac's `$n` spelling, numbered within the method
                // or class it is written in, so an edit elsewhere does not renumber it.
                prefix = inBody ? routines.get(enclosingRoutine).qualname : classPrefix();
                int n = anonymous.merge(prefix, 1, Integer::sum);
                simple = "$" + n;
            } else {
                prefix = inBody ? routines.get(enclosingRoutine).qualname : classPrefix();
            }
            String qual = join(prefix, simple);
            boolean anon = c.getSimpleName().toString().isEmpty();
            if (!anon) {
                structure(c, simple, qual);
            }
            classes.addLast(new String[] {qual, simple, c.getKind().name()});
            openClassTrees.addLast(c);
            for (Tree m : c.getMembers()) {
                if (m instanceof VariableTree f && isEnumConstant(f)) {
                    // An enum constant's arguments are code, and a constant with a body is a
                    // class named by the constant: `pkg.E.RED.m`, not an anonymous `$n`.
                    NewClassTree nc = (NewClassTree) f.getInitializer();
                    for (ExpressionTree a : nc.getArguments()) {
                        scan(a, null);
                    }
                    if (nc.getClassBody() != null) {
                        enumBody = f.getName().toString();
                        scan(nc.getClassBody(), null);
                    }
                } else if (m instanceof VariableTree f) {
                    if (f.getInitializer() != null) {
                        scan(f.getInitializer(), null);
                    }
                } else if (m instanceof BlockTree b) {
                    scan(b, null);
                } else {
                    scan(m, null);
                }
            }
            classes.removeLast();
            openClassTrees.removeLast();
            return null;
        }

        /** Is this open routine inside the innermost open class, rather than outside it? */
        boolean routineInside(int idx) {
            String cls = classes.peekLast()[0];
            return routines.get(idx).qualname.startsWith(cls + ".");
        }

        void structure(ClassTree c, String simple, String qual) {
            Tree.Kind k = c.getKind();
            Facts.StructureKind kind = switch (k) {
                case INTERFACE, ANNOTATION_TYPE -> Facts.StructureKind.INTERFACE;
                case ENUM -> Facts.StructureKind.ENUM;
                default -> Facts.StructureKind.CLASS;
            };
            Facts.DataStructure ds = new Facts.DataStructure();
            long n = seenType.merge(qual, 1L, Long::sum);
            ds.id = Ids.definitionId(path, qual, n);
            ds.name = simple;
            ds.kind = kind;
            ds.module = module;
            ds.file = path;
            ds.line = line(declStart(c, c.getModifiers()));
            ds.docstring = javadocFor(c);
            if (c.getExtendsClause() != null) {
                ds.bases.add(text(c.getExtendsClause()));
            }
            for (Tree t : c.getImplementsClause()) {
                ds.bases.add(text(t));
            }
            boolean iface = kind == Facts.StructureKind.INTERFACE;
            for (Tree m : c.getMembers()) {
                if (m instanceof VariableTree f) {
                    Facts.Field_ fd = new Facts.Field_();
                    fd.name = f.getName().toString();
                    // An enum constant has no written type; it is a member of the enum.
                    boolean constant = k == Tree.Kind.ENUM && isEnumConstant(f);
                    fd.type = constant ? null : text(f.getType());
                    fd.default_ = f.getInitializer() == null || constant ? null
                        : text(f.getInitializer());
                    String doc = javadocFor(f);
                    fd.comment = doc == null ? null : doc.lines().findFirst().orElse(null);
                    ds.fields.add(fd);
                    constant(f, iface, constant, simple);
                } else if (m instanceof MethodTree mt && mt.getBody() == null
                    && mt.getReturnType() != null) {
                    // A declaration another class fills: a field of its shape (see above).
                    Facts.Field_ fd = new Facts.Field_();
                    fd.name = mt.getName().toString();
                    fd.type = signature(mt);
                    ds.fields.add(fd);
                }
            }
            ff.structures.add(ds);
            if (kind != Facts.StructureKind.INTERFACE) {
                Facts.ClassDef_ cd = new Facts.ClassDef_();
                cd.name = simple;
                cd.qualname = qual;
                cd.module = module;
                cd.file = path;
                cd.line = ds.line;
                cd.bases.addAll(ds.bases);
                ff.classes.add(cd);
            }
        }

        /** javac writes {@code RED(1)} as a field of the enum's type whose initialiser is a
         *  {@code new} it made itself. That construction is not in the source (there is no
         *  {@code new} in the text it spans), so it is not a call anybody wrote. */
        boolean isEnumConstant(VariableTree f) {
            return f.getInitializer() instanceof NewClassTree nc && !text(nc).startsWith("new");
        }

        String signature(MethodTree mt) {
            long a = declStart(mt, mt.getModifiers());
            long b = mt.getBody() != null ? start(mt.getBody()) : end(mt);
            if (a < 0 || b < a || b > src.length()) {
                return "";
            }
            String s = src.substring((int) a, (int) b).strip();
            return s.endsWith(";") ? s.substring(0, s.length() - 1).strip() : s;
        }

        /** {@code static final} with a value, or any field of an interface: a name with a
         *  value, which is what a constant is (rule 19). An enum's members are constants of
         *  their enum. */
        void constant(VariableTree f, boolean iface, boolean enumConstant, String owner) {
            Set<Modifier> flags = f.getModifiers().getFlags();
            boolean isConst = enumConstant || iface
                || (flags.contains(Modifier.STATIC) && flags.contains(Modifier.FINAL));
            if (!isConst || (f.getInitializer() == null && !enumConstant)) {
                return;
            }
            Facts.Constant k = new Facts.Constant();
            k.name = f.getName().toString();
            k.value = enumConstant ? k.name : text(f.getInitializer());
            k.line = lineOf(f);
            k.type = enumConstant ? owner : text(f.getType());
            k.is_final = true;
            String doc = javadocFor(f);
            k.comment = doc == null ? null : doc.lines().findFirst().orElse(null);
            k.private_ = !(iface || enumConstant || flags.contains(Modifier.PUBLIC));
            ff.constants.add(k);
        }

        // --------------------------------------------------------- routines --- //

        @Override
        public Void visitMethod(MethodTree m, Void v) {
            if (m.getBody() == null) {
                return null; // a declaration with no body is not a routine (see above)
            }
            String[] cls = classes.peekLast();
            String clsQual = cls == null ? pkg : cls[0];
            String clsName = cls == null ? null : cls[1];
            boolean ctor = m.getReturnType() == null;
            String name = ctor ? clsName : m.getName().toString();
            String qual = join(clsQual, name);
            Set<Modifier> flags = m.getModifiers().getFlags();
            Facts.Routine r = new Facts.Routine();
            long n = seenQual.merge(qual, 1L, Long::sum);
            r.id = Ids.definitionId(path, qual, n);
            r.name = name;
            r.qualname = qual;
            r.module = module;
            r.file = path;
            r.line_start = line(declStart(m, m.getModifiers()));
            r.line_end = endLineOf(m);
            // **Always declared.** A constructor returns nothing and says so by having no
            // type; `null` would mean *undeclared*, which no Java method is, and Go's
            // `MISSING_RETURN_TYPE` finding is what that costs (rule 98).
            r.returns = ctor ? "" : text(m.getReturnType());
            for (AnnotationTree a : m.getModifiers().getAnnotations()) {
                r.decorators.add(text(a.getAnnotationType()).replaceAll("\\s+", ""));
            }
            for (VariableTree p : m.getParameters()) {
                Facts.Param fp = new Facts.Param();
                fp.name = p.getName().toString();
                String t = text(p.getType());
                if (text(p).contains("...")) {
                    fp.kind = "vararg";
                    t = t.endsWith("...") ? t : t + "...";
                }
                fp.type = t;
                r.params.add(fp);
            }
            r.docstring = javadocFor(m);
            r.is_method = !flags.contains(Modifier.STATIC);
            r.class_name = clsName;
            r.is_nested = !scope.isEmpty();
            r.visibility = flags.contains(Modifier.PUBLIC) || inInterface() ? "public" : "private";
            r.body_hash = Ids.hashSource(text(m.getBody()));
            routines.add(r);
            int idx = routines.size() - 1;
            if (!ctor && isMain(m, flags)) {
                wayIn(idx);
            }
            for (AnnotationTree a : m.getModifiers().getAnnotations()) {
                String dotted = text(a.getAnnotationType()).replaceAll("\\s+", "");
                Rules.Entry rule = rules.matchDecorator(dotted);
                if (rule != null) {
                    declaredWayIn(idx, rule, a);
                }
            }
            scope.addLast(idx);
            long saved = depth;
            depth = 0;
            scan(m.getBody(), null);
            depth = saved;
            scope.removeLast();
            return null;
        }

        /** An interface's methods are public whether or not they say so. */
        boolean inInterface() {
            String[] top = classes.peekLast();
            return top != null && (top[2].equals("INTERFACE") || top[2].equals("ANNOTATION_TYPE"));
        }

        /** {@code public static void main(String[] args)}, or {@code String... args}. */
        boolean isMain(MethodTree m, Set<Modifier> flags) {
            if (!rules.entryNames.contains(m.getName().toString())
                || !flags.contains(Modifier.STATIC) || m.getParameters().size() != 1) {
                return false;
            }
            String t = text(m.getParameters().get(0)).replaceAll("\\s+", "");
            return t.startsWith("String[]") || t.startsWith("String...")
                || t.startsWith("java.lang.String[]") || t.startsWith("java.lang.String...")
                || t.matches("(final)?String\\w+\\[\\]");
        }

        void wayIn(int idx) {
            Facts.Routine r = routines.get(idx);
            Facts.Entrypoint ep = new Facts.Entrypoint();
            ep.id = Ids.entrypointId(path, List.of(r.qualname, "main"));
            ep.kind = Facts.EntrypointKind.MAIN;
            ep.name = r.name;
            ep.routine_id = r.id;
            ep.module = module;
            ep.evidence = r.name + "() at " + path + ":" + r.line_start;
            ff.entrypoints.add(ep);
        }

        /** A way in an annotation declares (`java.yaml` `entrypoints`). Its name is the
         *  annotation as written with the class's own prefix where the class carries one of
         *  the same rules, so `@RequestMapping("/owners")` over `@GetMapping("/{id}")` reads
         *  `GetMapping /owners/{id}`. */
        void declaredWayIn(int idx, Rules.Entry rule, AnnotationTree a) {
            Facts.Routine r = routines.get(idx);
            Facts.EntrypointKind kind = entrypointKind(rule.kind);
            String ann = text(a.getAnnotationType()).replaceAll("\\s+", "");
            String simple = ann.substring(ann.lastIndexOf('.') + 1);
            String value = annotationValue(a);
            String name = r.name;
            if (kind == Facts.EntrypointKind.HTTP_ROUTE) {
                String route = classRoute(rule) + (value == null ? "" : value);
                name = simple + (route.isEmpty() ? "" : " " + route);
            }
            Facts.Entrypoint ep = new Facts.Entrypoint();
            ep.id = Ids.entrypointId(path, List.of(r.qualname, kind.wire));
            ep.kind = kind;
            ep.name = name;
            ep.routine_id = r.id;
            ep.module = module;
            ep.evidence = "@" + simple + " " + r.name + "() at " + path + ":" + r.line_start
                + (rule.evidence.isEmpty() ? "" : ": " + rule.evidence);
            ff.entrypoints.add(ep);
        }

        /** The route a class's own annotation declares, for the same rule. */
        String classRoute(Rules.Entry rule) {
            ClassTree c = openClassTrees.peekLast();
            if (c == null) {
                return "";
            }
            for (AnnotationTree a : c.getModifiers().getAnnotations()) {
                Rules.Entry r = rules.matchDecorator(
                    text(a.getAnnotationType()).replaceAll("\\s+", ""));
                if (r != null && entrypointKind(r.kind) == Facts.EntrypointKind.HTTP_ROUTE) {
                    String v = annotationValue(a);
                    if (v != null) {
                        return v;
                    }
                }
            }
            return "";
        }

        final Deque<ClassTree> openClassTrees = new ArrayDeque<>();

        /** The first string an annotation is given: {@code @X("a")}, {@code @X(value="a")}
         *  or {@code @X(path={"a", …})}, as the source writes it. */
        String annotationValue(AnnotationTree a) {
            for (ExpressionTree arg : a.getArguments()) {
                ExpressionTree e = arg;
                if (arg instanceof AssignmentTree as) {
                    String key = text(as.getVariable()).strip();
                    if (!key.equals("value") && !key.equals("path")) {
                        continue;
                    }
                    e = as.getExpression();
                }
                String s = firstString(e);
                if (s != null) {
                    return s;
                }
            }
            return null;
        }

        String firstString(Tree e) {
            if (e instanceof LiteralTree l && l.getValue() instanceof String s) {
                return s;
            }
            if (e instanceof com.sun.source.tree.NewArrayTree na && na.getInitializers() != null
                && !na.getInitializers().isEmpty()) {
                return firstString(na.getInitializers().get(0));
            }
            return null;
        }

        Facts.EntrypointKind entrypointKind(String wire) {
            for (Facts.EntrypointKind k : Facts.EntrypointKind.values()) {
                if (k.wire.equals(wire) || k.name().equals(wire)) {
                    return k;
                }
            }
            // The host validated the rules file; an unknown kind cannot arrive.
            throw new IllegalStateException("java.yaml names a way in this reader does not know: "
                + wire);
        }

        // -------------------------------------------------------------- calls --- //

        @Override
        public Void visitExpressionStatement(ExpressionStatementTree s, Void v) {
            // `f(x);` throws the value away. For a future that runs, that is what the
            // detector is told; a call whose value is bound, returned or passed on is not.
            if (s.getExpression() instanceof MethodInvocationTree || s.getExpression()
                instanceof NewClassTree) {
                discarded.add(s.getExpression());
            }
            return super.visitExpressionStatement(s, v);
        }

        @Override
        public Void visitMethodInvocation(MethodInvocationTree m, Void v) {
            String dotted = callee(m.getMethodSelect());
            call(dotted, m, m.getArguments(), false);
            maybeComprehension(m);
            return super.visitMethodInvocation(m, v);
        }

        @Override
        public Void visitNewClass(NewClassTree n, Void v) {
            String dotted = typeName(n.getIdentifier());
            // `outer.new Inner()` is still the construction of `Inner`.
            call(dotted, n, n.getArguments(), true);
            if (n.getEnclosingExpression() != null) {
                scan(n.getEnclosingExpression(), null);
            }
            for (ExpressionTree a : n.getArguments()) {
                scan(a, null);
            }
            if (n.getClassBody() != null) {
                scan(n.getClassBody(), null);
            }
            return null;
        }

        @Override
        public Void visitAnnotation(AnnotationTree a, Void v) {
            // An annotation's arguments are configuration — a route, a column name, a
            // message — and never a value the program moves at run time.
            return null;
        }

        @Override
        public Void visitLiteral(LiteralTree l, Void v) {
            if (l.getKind() == Tree.Kind.STRING_LITERAL && l.getValue() instanceof String s) {
                int len = s.codePointCount(0, s.length());
                if (len < LITERAL_MIN || len > LITERAL_MAX) {
                    ff.literals_dropped++;
                } else {
                    Facts.StringLiteral lit = new Facts.StringLiteral();
                    lit.routine_id = ownerId();
                    lit.line = lineOf(l);
                    lit.text = s;
                    ff.literals.add(lit);
                }
            }
            return null;
        }

        void call(String dotted, Tree site, List<? extends ExpressionTree> args,
                  boolean construction) {
            if (dotted.isEmpty()) {
                return; // clause 3: no name at the root, and `""` is never matched
            }
            long line = lineOf(site);
            Rules.Boundary rule = rules.matchCall(dotted);
            String caller = ownerId();
            String key = caller + "\0" + dotted;
            long ordinal = callOrd.merge(key, 1L, Long::sum) - 1;
            Facts.CallSite cs = new Facts.CallSite();
            cs.caller_id = caller;
            cs.callee_expr = dotted;
            cs.line = line;
            cs.site_id = Ids.callSiteId(caller, dotted, ordinal);
            // Rule 2: a call that touches a boundary is never also an internal edge.
            cs.at_boundary = rule != null;
            cs.is_construction = construction;
            for (int i = 0; i < args.size(); i++) {
                Facts.CallArg a = new Facts.CallArg();
                a.idx = i;
                a.expr = text(args.get(i));
                cs.args.add(a);
            }
            ff.calls.add(cs);
            if (sink != null) {
                sink.site(site, cs.site_id, caller, dotted, rule != null, construction);
            }
            if (rule != null) {
                Facts.BoundaryHit hit = new Facts.BoundaryHit();
                hit.routine_id = caller;
                hit.kind = boundaryKind(rule.kind);
                hit.direction = direction(rule.direction);
                hit.target = target(args, rule);
                hit.line = line;
                hit.evidence = dotted;
                hit.salience = rule.salience;
                ff.boundaries.add(hit);
            }
            network(dotted, line, site, args);
        }

        String target(List<? extends ExpressionTree> args, Rules.Boundary rule) {
            if (rule.targetArg == null || rule.targetArg >= args.size()) {
                return "";
            }
            ExpressionTree a = args.get(rule.targetArg);
            String s = firstString(a);
            return s != null ? s : text(a);
        }

        void network(String dotted, long line, Tree site, List<? extends ExpressionTree> args) {
            Rules.Net lib = rules.matchNetwork(dotted);
            if (lib == null) {
                return;
            }
            String last = dotted.substring(dotted.lastIndexOf('.') + 1);
            Facts.NetworkCall nc = new Facts.NetworkCall();
            nc.routine_id = ownerId();
            nc.expr = dotted;
            nc.protocol = lib.protocol;
            nc.line = line;
            nc.is_async = lib.isAsync;
            nc.awaited = !discarded.contains(site);
            for (String verb : rules.verbs) {
                if (verb.equalsIgnoreCase(last)) {
                    nc.verb = last.toUpperCase(Locale.ROOT);
                }
            }
            if (!args.isEmpty()) {
                String s = firstString(args.get(0));
                nc.destination = s != null ? s : text(args.get(0));
            }
            Integer timed = rules.timed.get(dotted);
            if (timed != null && timed < args.size()) {
                ExpressionTree a = args.get(timed);
                nc.timeout = a instanceof LiteralTree ? text(a) : "set";
            }
            ff.network.add(nc);
        }

        /** {@code .forEach(x -> …)}: a loop that is an expression, recorded only where the
         *  function is written here (TypeScript's rule, {@code maybeComprehension}). */
        void maybeComprehension(MethodInvocationTree m) {
            if (!(m.getMethodSelect() instanceof MemberSelectTree sel)) {
                return;
            }
            String last = sel.getIdentifier().toString();
            if (!ITERATION.contains(last) || m.getArguments().isEmpty()
                || !(m.getArguments().get(0) instanceof LambdaExpressionTree fn)) {
                return;
            }
            String header = text(sel);
            long[] once = once(sel.getExpression(), fn);
            addPoint(m, Facts.ControlKind.COMPREHENSION, header, last, 1, "", once);
        }

        // ------------------------------------------------------------ control --- //

        String[] addPoint(Tree node, Facts.ControlKind kind, String header, String word,
                          long arms, String exits, long[] once) {
            String rid = ownerId();
            String key = rid + "\0" + kind.wire + "\0" + header;
            long ordinal = ctrlOrd.merge(key, 1L, Long::sum) - 1;
            String pid = Ids.controlPointId(rid, kind.wire, header, ordinal);
            Facts.ControlPoint p = new Facts.ControlPoint();
            p.point_id = pid;
            p.routine_id = rid;
            p.kind = kind;
            p.line_start = lineOf(node);
            p.line_end = endLineOf(node);
            p.depth = depth;
            p.header = header;
            p.arms = arms;
            p.exits = exits;
            p.word = word;
            p.once_start = once[0];
            p.once_end = once[1];
            ff.control.add(p);
            return new String[] {pid, rid};
        }

        void addArm(String[] p, long idx, Facts.ArmKind kind, Tree node, String header) {
            Facts.ControlArm a = new Facts.ControlArm();
            a.point_id = p[0];
            a.routine_id = p[1];
            a.idx = idx;
            a.kind = kind;
            a.line_start = lineOf(node);
            a.line_end = endLineOf(node);
            a.header = header;
            ff.control_arms.add(a);
        }

        /** The lines a loop evaluates once before its first pass: the evaluated part minus
         *  every line the repeated part also occupies ({@code extract.ts:onceRange}). */
        long[] once(Tree evaluated, Tree repeated) {
            if (evaluated == null) {
                return new long[] {0, 0};
            }
            long s = lineOf(evaluated);
            long e = endLineOf(evaluated);
            long b = lineOf(repeated);
            if (b <= e) {
                e = b - 1;
            }
            return e >= s ? new long[] {s, e} : new long[] {0, 0};
        }

        void inside(Runnable r) {
            depth++;
            try {
                r.run();
            } finally {
                depth--;
            }
        }

        static String unparen(String header) {
            String h = header.strip();
            return h.startsWith("(") && h.endsWith(")") ? h.substring(1, h.length() - 1).strip() : h;
        }

        @Override
        public Void visitIf(IfTree s, Void v) {
            List<IfTree> rungs = new ArrayList<>();
            StatementTree tail = null;
            IfTree cur = s;
            while (true) {
                rungs.add(cur);
                StatementTree other = cur.getElseStatement();
                if (other instanceof IfTree next) {
                    cur = next;
                } else {
                    tail = other;
                    break;
                }
            }
            String exits = rungs.size() == 1 && tail == null ? leavesWith(s.getThenStatement()) : "";
            Facts.ControlKind kind = exits.isEmpty() ? Facts.ControlKind.DECISION
                : Facts.ControlKind.GUARD;
            String header = unparen(text(s.getCondition()));
            String[] p = addPoint(s, kind, header, "if", rungs.size() + (tail != null ? 1 : 0),
                exits, new long[] {0, 0});
            for (int i = 0; i < rungs.size(); i++) {
                addArm(p, i, i == 0 ? Facts.ArmKind.IF : Facts.ArmKind.ELSE_IF,
                    rungs.get(i).getThenStatement(), unparen(text(rungs.get(i).getCondition())));
            }
            if (tail != null) {
                addArm(p, rungs.size(), Facts.ArmKind.ELSE, tail, "");
            }
            final StatementTree last = tail;
            inside(() -> {
                for (IfTree r : rungs) {
                    scan(r.getCondition(), null);
                    scan(r.getThenStatement(), null);
                }
                if (last != null) {
                    scan(last, null);
                }
            });
            return null;
        }

        /** How a one-armed decision leaves, read off its last statement: {@code return} and
         *  {@code throw} are the same sentence and opposite facts. */
        String leavesWith(StatementTree body) {
            StatementTree last = body;
            if (body instanceof BlockTree b) {
                List<? extends StatementTree> st = b.getStatements();
                if (st.isEmpty()) {
                    return "";
                }
                last = st.get(st.size() - 1);
            }
            return switch (last.getKind()) {
                case RETURN -> "return";
                case THROW -> "throw";
                case CONTINUE -> "continue";
                case BREAK -> "break";
                case EXPRESSION_STATEMENT -> {
                    ExpressionTree e = ((ExpressionStatementTree) last).getExpression();
                    String c = e instanceof MethodInvocationTree mi ? callee(mi.getMethodSelect()) : "";
                    yield c.equals("System.exit") || c.equals("Runtime.getRuntime.halt") ? "exit" : "";
                }
                default -> "";
            };
        }

        @Override
        public Void visitSwitch(SwitchTree s, Void v) {
            switchLike(s, s.getExpression(), s.getCases());
            return null;
        }

        @Override
        public Void visitSwitchExpression(SwitchExpressionTree s, Void v) {
            switchLike(s, s.getExpression(), s.getCases());
            return null;
        }

        void switchLike(Tree node, ExpressionTree on, List<? extends CaseTree> cases) {
            String header = unparen(text(on));
            String[] p = addPoint(node, Facts.ControlKind.DECISION, header, "switch",
                Math.max(1, cases.size()), "", new long[] {0, 0});
            for (int i = 0; i < cases.size(); i++) {
                CaseTree c = cases.get(i);
                List<? extends ExpressionTree> labels = c.getExpressions();
                boolean isDefault = labels.isEmpty();
                StringBuilder h = new StringBuilder();
                for (ExpressionTree l : labels) {
                    if (h.length() > 0) {
                        h.append(", ");
                    }
                    h.append(text(l));
                }
                addArm(p, i, isDefault ? Facts.ArmKind.DEFAULT : Facts.ArmKind.CASE, c,
                    h.toString());
            }
            scan(on, null);
            inside(() -> {
                for (CaseTree c : cases) {
                    if (c.getStatements() != null) {
                        for (StatementTree st : c.getStatements()) {
                            scan(st, null);
                        }
                    } else {
                        scan(c.getBody(), null);
                    }
                }
            });
        }

        @Override
        public Void visitTry(TryTree t, Void v) {
            long arms = 1 + t.getCatches().size() + (t.getFinallyBlock() != null ? 1 : 0);
            String header = t.getResources().isEmpty() ? "" : resources(t);
            String[] p = addPoint(t, Facts.ControlKind.HANDLER, header, "try", arms, "",
                new long[] {0, 0});
            long idx = 0;
            addArm(p, idx++, Facts.ArmKind.TRY, t.getBlock(), "");
            for (CatchTree c : t.getCatches()) {
                // Java's word is `catch`, and `ArmKind.EXCEPT` is Python's. Spelling one
                // language's arm with the other's word is the same defect as renaming it.
                addArm(p, idx++, Facts.ArmKind.CATCH, c, text(c.getParameter()));
            }
            if (t.getFinallyBlock() != null) {
                addArm(p, idx, Facts.ArmKind.FINALLY, t.getFinallyBlock(), "");
            }
            // The resources are opened once, where they are written, and belong outside.
            for (Tree r : t.getResources()) {
                scan(r, null);
            }
            inside(() -> {
                scan(t.getBlock(), null);
                for (CatchTree c : t.getCatches()) {
                    scan(c.getBlock(), null);
                }
                if (t.getFinallyBlock() != null) {
                    scan(t.getFinallyBlock(), null);
                }
            });
            return null;
        }

        String resources(TryTree t) {
            StringBuilder h = new StringBuilder();
            for (Tree r : t.getResources()) {
                if (h.length() > 0) {
                    h.append("; ");
                }
                h.append(text(r));
            }
            return h.toString();
        }

        @Override
        public Void visitEnhancedForLoop(EnhancedForLoopTree s, Void v) {
            String header = text(s.getVariable()) + " : " + text(s.getExpression());
            // The iterated expression is evaluated once.
            long[] once = once(s.getExpression(), s.getStatement());
            String[] p = addPoint(s, Facts.ControlKind.LOOP, header, "for", 1, "", once);
            addArm(p, 0, Facts.ArmKind.FOR, s.getStatement(), "");
            inside(() -> {
                scan(s.getExpression(), null);
                scan(s.getStatement(), null);
            });
            return null;
        }

        @Override
        public Void visitForLoop(ForLoopTree s, Void v) {
            StringBuilder init = new StringBuilder();
            for (StatementTree st : s.getInitializer()) {
                if (init.length() > 0) {
                    init.append(", ");
                }
                String t = text(st).strip();
                init.append(t.endsWith(";") ? t.substring(0, t.length() - 1) : t);
            }
            StringBuilder upd = new StringBuilder();
            for (ExpressionStatementTree st : s.getUpdate()) {
                if (upd.length() > 0) {
                    upd.append(", ");
                }
                upd.append(text(st.getExpression()));
            }
            String header = init + "; " + text(s.getCondition()) + "; " + upd;
            // The initialiser runs once; the test and the update repeat.
            long[] once = s.getInitializer().isEmpty() ? new long[] {0, 0}
                : once(s.getInitializer().get(0), s.getStatement());
            String[] p = addPoint(s, Facts.ControlKind.LOOP, header, "for", 1, "", once);
            addArm(p, 0, Facts.ArmKind.FOR, s.getStatement(), "");
            inside(() -> {
                for (StatementTree st : s.getInitializer()) {
                    scan(st, null);
                }
                scan(s.getCondition(), null);
                for (ExpressionStatementTree st : s.getUpdate()) {
                    scan(st, null);
                }
                scan(s.getStatement(), null);
            });
            return null;
        }

        @Override
        public Void visitWhileLoop(WhileLoopTree s, Void v) {
            // A `while`'s test re-runs, so it evaluates nothing once.
            String[] p = addPoint(s, Facts.ControlKind.LOOP, unparen(text(s.getCondition())),
                "while", 1, "", new long[] {0, 0});
            addArm(p, 0, Facts.ArmKind.WHILE, s.getStatement(), "");
            inside(() -> {
                scan(s.getCondition(), null);
                scan(s.getStatement(), null);
            });
            return null;
        }

        @Override
        public Void visitDoWhileLoop(DoWhileLoopTree s, Void v) {
            String[] p = addPoint(s, Facts.ControlKind.LOOP, unparen(text(s.getCondition())),
                "do", 1, "", new long[] {0, 0});
            addArm(p, 0, Facts.ArmKind.DO, s.getStatement(), "");
            inside(() -> {
                scan(s.getStatement(), null);
                scan(s.getCondition(), null);
            });
            return null;
        }

        // ----------------------------------------------------------- comments --- //

        /** Every comment that is not Javadoc lands on the innermost routine whose span holds
         *  it, and the module scope owns what no method does (rule 18). */
        void landComments() {
            for (Comments.Found c : scanned.comments) {
                Facts.Routine home = null;
                for (Facts.Routine r : routines) {
                    if (r.line_start <= c.line && c.line <= r.line_end
                        && (home == null || r.line_start >= home.line_start)) {
                        home = r;
                    }
                }
                Facts.Comment fc = new Facts.Comment();
                fc.text = c.text;
                fc.line = c.line;
                fc.leading = c.leading;
                if (home != null) {
                    home.comments.add(fc);
                } else {
                    moduleClaimed = true;
                    moduleScope.comments.add(fc);
                }
            }
        }

        // ------------------------------------------------------------ helpers --- //

        /** The callee of {@code f(…)} as the contract spells it ({@code ingest/dotted.py}). */
        String callee(ExpressionTree sel) {
            if (sel instanceof IdentifierTree id) {
                return id.getName().toString();
            }
            if (sel instanceof MemberSelectTree ms) {
                String base = receiver(ms.getExpression());
                return base.isEmpty() ? "" : base + "." + ms.getIdentifier();
            }
            return "";
        }

        /** The receiver of {@code x.m(…)}, as the contract spells it. */
        String receiver(ExpressionTree e) {
            if (e instanceof IdentifierTree id) {
                return id.getName().toString();
            }
            if (e instanceof MemberSelectTree ms) {
                String base = receiver(ms.getExpression());
                return base.isEmpty() ? "" : base + "." + ms.getIdentifier();
            }
            // Clause 2: a call in the middle folds to its callee, and a construction to
            // the type it builds: `new File(p).exists()` is `File.exists`.
            if (e instanceof MethodInvocationTree mi) {
                return callee(mi.getMethodSelect());
            }
            if (e instanceof NewClassTree nc) {
                return typeName(nc.getIdentifier());
            }
            // Clause 5's shape: a cast and a pair of brackets say how a value is had, not
            // which value it is.
            if (e instanceof ParenthesizedTree p) {
                return receiver(p.getExpression());
            }
            if (e instanceof TypeCastTree tc) {
                return receiver(tc.getExpression());
            }
            // Clause 3: an index, a literal, a lambda, a conditional — nothing to name.
            return "";
        }

        /** {@code Foo}, {@code a.b.Foo} and {@code Foo<T>} are spelt without their type
         *  arguments (clause 6). */
        String typeName(Tree t) {
            if (t instanceof ParameterizedTypeTree pt) {
                return typeName(pt.getType());
            }
            if (t instanceof IdentifierTree id) {
                return id.getName().toString();
            }
            if (t instanceof MemberSelectTree ms) {
                String base = typeName(ms.getExpression());
                return base.isEmpty() ? "" : base + "." + ms.getIdentifier();
            }
            if (t instanceof com.sun.source.tree.AnnotatedTypeTree at) {
                return typeName(at.getUnderlyingType());
            }
            return "";
        }

        static Facts.BoundaryKind boundaryKind(String s) {
            for (Facts.BoundaryKind k : Facts.BoundaryKind.values()) {
                if (k.name().equals(s) || k.wire.equals(s)) {
                    return k;
                }
            }
            // The host validated the rules file; an unknown kind cannot arrive.
            throw new IllegalStateException(
                "detectors/java.yaml names a boundary kind this reader does not know: " + s);
        }

        static Facts.Direction direction(String s) {
            return switch (s) {
                case "IN" -> Facts.Direction.IN;
                case "OUT" -> Facts.Direction.OUT;
                default -> Facts.Direction.BOTH;
            };
        }
    }

    /** The module scope: what a string or a call outside any method belongs to. Always
     *  sent, claimed or not, because a string names its owner before anybody knows whether
     *  it is a fact (rule 96, {@code extract.ts:moduleScope}). */
    static Facts.Routine moduleScope(String rel, String module, String source) {
        String qual = module + "." + MODULE_SCOPE;
        long lines = Math.max(1, source.chars().filter(c -> c == '\n').count());
        Facts.Routine r = new Facts.Routine();
        r.id = Ids.definitionId(rel, qual);
        r.name = MODULE_SCOPE;
        r.qualname = qual;
        r.module = module;
        r.file = rel;
        r.line_start = 1;
        r.line_end = lines;
        r.docstring = "Declarations at file level: field initialisers and initialiser blocks.";
        r.body_hash = Ids.hashSource(source);
        return r;
    }
}
