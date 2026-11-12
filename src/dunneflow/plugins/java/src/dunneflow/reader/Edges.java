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
 * <p><b>One compilation, every file in it, up to {@link #DEFAULT_BATCH} files.</b> The tree
 * is parsed in one {@link JavacTask}, every unit is walked by the extractor's own walk
 * <i>before</i> attribution (so each site carries the {@code site_id} the facts carry, and a
 * member javac adds later cannot move an ordinal), and then {@code analyze()} attributes the
 * lot. <b>A bigger tree is attributed in batches</b> ({@link #plan}): the Android SDK's
 * 16,344 files ran a 2 GB heap out after 97 minutes in one. Each batch has the rest of the
 * tree on its source path, so its calls into other batches type, and what each batch learns
 * is written down by name ({@link Index}) so the dispatch rule below is decided over the
 * whole tree once javac is gone. A tree under the cap gives the edges it always did. A call's target is
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
 * <p><b>What a call or a method is by a type, and no spelling says</b> (BACKLOG 45 and 46).
 * A call javac typed to a method the rules name by its declaring type ({@link Rules#typed})
 * is a touch, and so is a call on a receiver whose class extends a type the rules declare
 * ({@code extends:}) where the tree holds no body to run: {@code owners.save(o)} on a Spring
 * Data repository. Such a call is sent as a {@code touch} and <b>never also as an edge</b>
 * (rule 2). A method that overrides a framework's, in a class that extends the framework's
 * declared type, is a way in. Without the framework's jars javac cannot type the supertype,
 * and then its name is read as the file wrote it, through a single-type import or fully
 * qualified, and never through {@code import a.b.*}: that would be choosing a package.
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
        final List<Facts.SuppliedTouch> touches = new ArrayList<>();
        final List<Facts.SuppliedWayIn> waysIn = new ArrayList<>();
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

    /** A method in the tree that overrides another, as the decision needs it once javac is
     *  gone: its key, its class, whether it has a body, and where that body is. */
    private record Over(String key, String ownerKey, boolean hasBody, String file, long line,
                        String name) {}

    /**
     * <b>What every batch learnt about the tree's methods, by name and never by javac's
     * identity</b>, because each batch is its own compilation and its elements die with it.
     * The overrider index is the whole tree's or it is wrong: a batch that never mentions
     * {@code C extends B} never loads it, and a batch-local index called {@code x.hello()}
     * CERTAIN while {@code C.hello} could answer it (probed 2026-11-02, rule 1).
     */
    private static final class Index {
        /** Overridden method's key → the tree's methods that override it, in walk order. */
        final Map<String, List<Over>> overriddenBy = new HashMap<>();
        /** A class's key → the keys of every type it is a subtype of, itself included. */
        final Map<String, Set<String>> closure = new HashMap<>();
        /** One overrider recorded once, however many batches load its class. */
        final Set<String> seen = new java.util.HashSet<>();
    }

    /** A site's question, asked of javac in its batch. A final one is already its answer;
     *  a pending one needs the whole tree's overrider index, which only exists afterwards. */
    private static final class Question {
        final Facts.SuppliedEdge e = new Facts.SuppliedEdge();
        boolean pending;
        String targetKey;
        String receiverKey;
        String frontier;
        boolean home;
        boolean nonVirtual;
        boolean hasBody;
        String file;
        long line;
        String name;
        /** What this call is if its far end turns out to have no body in the tree. */
        Facts.SuppliedTouch touch;
    }

    /** Raised from a task listener to abandon a batch whose heap is nearly full. */
    private static final class HeapFull extends RuntimeException {
        HeapFull(String why) {
            super(why, null, false, false);
        }
    }

    /** Files per compilation. A tree this size or smaller is one compilation, exactly as
     *  it always was; the env var exists so a test can make a small tree several. */
    static int batchCap() {
        String v = System.getenv("DUNNEFLOW_JAVA_BATCH_FILES");
        try {
            return v == null || v.isBlank() ? DEFAULT_BATCH : Math.max(1, Integer.parseInt(v.strip()));
        } catch (NumberFormatException e) {
            return DEFAULT_BATCH;
        }
    }

    static final int DEFAULT_BATCH = 2000;
    /** After a collection, a heap this full abandons the batch rather than thrash (rule 55). */
    static final double HEAP_CEILING = 0.85;

    /**
     * <b>The bound is on the work, not on the answer (rule 55).</b> The Android SDK held
     * javac in garbage collection for 97 minutes before it ran out of heap. Usage after the
     * last collection, read at every task event, stops a batch while there is still room to
     * drop it; the batch is then split and tried again.
     */
    static boolean heapNearlyFull() {
        return heapAfterCollection() >= (long) (Runtime.getRuntime().maxMemory() * HEAP_CEILING);
    }

    /** What the heap held after its last collection, summed over its pools and judged
     *  against the whole heap: a pool judged against its own maximum is a different
     *  question, and the first batched Android run answered it in under a second. */
    static long heapAfterCollection() {
        long used = 0;
        for (java.lang.management.MemoryPoolMXBean p
                : java.lang.management.ManagementFactory.getMemoryPoolMXBeans()) {
            if (p.getType() != java.lang.management.MemoryType.HEAP) {
                continue;
            }
            java.lang.management.MemoryUsage u = p.getCollectionUsage();
            if (u != null) {
                used += u.getUsed();
            }
        }
        return used;
    }

    /** Classes the last compilation attributed: its own, and others off the source path. */
    static final long[] attributed = new long[2];

    static long heapMaxMb() {
        return Runtime.getRuntime().maxMemory() / (1024 * 1024);
    }

    /**
     * The tree in compilations of at most {@link #batchCap} files. Under the cap the files
     * are one compilation in the order they came, which is what every tree before the
     * Android SDK was. Over it they are grouped by directory, which is as near to a package
     * as a path is, in path order so the batches never depend on the order rows arrive in
     * (rules 66 and 105). A directory bigger than the cap is a batch of its own.
     */
    static List<List<List<Path>>> plan(List<Path> files, int cap) {
        List<List<List<Path>>> out = new ArrayList<>();
        if (files.size() <= cap) {
            out.add(List.of(files));
            return out;
        }
        Map<String, List<Path>> byDir = new TreeMap<>();
        for (Path f : files) {
            Path d = f.toAbsolutePath().normalize().getParent();
            byDir.computeIfAbsent(d == null ? "" : d.toString(), k -> new ArrayList<>()).add(f);
        }
        List<List<Path>> cur = new ArrayList<>();
        int n = 0;
        for (List<Path> dir : byDir.values()) {
            if (n > 0 && n + dir.size() > cap) {
                out.add(cur);
                cur = new ArrayList<>();
                n = 0;
            }
            cur.add(dir);
            n += dir.size();
        }
        if (!cur.isEmpty()) {
            out.add(cur);
        }
        return out;
    }

    /**
     * <b>The rest of the tree, for a batch's calls into it: read once, and without its
     * bodies.</b> Two measured costs shaped it. The first batched Android run put the tree's
     * directories on javac's {@code -sourcepath}, and javac listed and read them one file at
     * a time in every compilation, off the external volume: four hours at 3% CPU. And javac
     * attributes a class it loads off the source path as fully as one it was handed --
     * traccar's second compilation of 102 files attributed 915 others -- so every batch was
     * attributing most of the tree again. So every file is read once, here, and held with
     * every method, constructor and initializer body blanked: its interior turned to spaces
     * with each line break kept, so every position and every line number is the file's own.
     * What a batch needs of another file is its signatures, its fields and its constants,
     * and those are untouched.
     */
    static final class SourcePath {
        final Map<String, List<TreeSource>> byPackage = new HashMap<>();
        final Map<java.net.URI, TreeSource> byUri = new HashMap<>();
        final Map<String, TreeSource> byRel = new HashMap<>();
        long chars;
        long blanked;

        static final int PARSE_CHUNK = 500;

        static SourcePath read(List<Path> files, Function<Path, String> rel, List<String> notes) {
            SourcePath sp = new SourcePath();
            for (int i = 0; i < files.size(); i += PARSE_CHUNK) {
                List<Extract.Source> chunk = new ArrayList<>();
                for (Path f : files.subList(i, Math.min(files.size(), i + PARSE_CHUNK))) {
                    try {
                        chunk.add(new Extract.Source(rel.apply(f), Text.readSource(f)));
                    } catch (IOException e) {
                        notes.add("edges: " + f + " could not be read: " + e);
                    }
                }
                sp.add(chunk);
            }
            return sp;
        }

        /** One parse per chunk, to find the bodies; the trees are dropped with the task. */
        private void add(List<Extract.Source> chunk) {
            JavacTask task = (JavacTask) Extract.compiler().getTask(
                null, null, d -> { }, List.of("-proc:none"), null, chunk);
            SourcePositions pos = Trees.instance(task).getSourcePositions();
            Iterable<? extends CompilationUnitTree> units;
            try {
                units = task.parse();
            } catch (IOException e) {
                units = List.of();
            }
            Map<java.net.URI, CompilationUnitTree> parsed = new HashMap<>();
            for (CompilationUnitTree u : units) {
                parsed.put(u.getSourceFile().toUri(), u);
            }
            for (Extract.Source src : chunk) {
                String text = src.getCharContent(true).toString();
                CompilationUnitTree unit = parsed.get(src.toUri());
                String held = unit == null ? text : blank(text, unit, pos);
                String pkg = unit == null || unit.getPackageName() == null ? packageOf(text)
                    : unit.getPackageName().toString();
                String name = src.rel.substring(src.rel.lastIndexOf('/') + 1)
                    .replaceFirst("\\.java$", "");
                TreeSource ts = new TreeSource(src.rel, pkg.isEmpty() ? name : pkg + "." + name,
                    held);
                byPackage.computeIfAbsent(pkg, k -> new ArrayList<>()).add(ts);
                byUri.put(ts.toUri(), ts);
                byRel.put(src.rel, ts);
                chars += text.length();
            }
        }

        /** The text with every body's interior made spaces, line breaks kept. */
        private String blank(String text, CompilationUnitTree unit, SourcePositions pos) {
            char[] out = text.toCharArray();
            new com.sun.source.util.TreeScanner<Void, Void>() {
                void clear(Tree block) {
                    long s = pos.getStartPosition(unit, block);
                    long e = pos.getEndPosition(unit, block);
                    if (s < 0 || e <= s + 1 || e > out.length) {
                        return;
                    }
                    // From the brace, never the start: `static { … }` starts at `static`,
                    // and blanking from there made traccar's `Permission` unparseable and
                    // 105 calls into it `untyped`.
                    while (s < e && out[(int) s] != '{') {
                        s++;
                    }
                    if (e <= s + 1 || out[(int) e - 1] != '}') {
                        return;
                    }
                    for (int k = (int) s + 1; k < e - 1; k++) {
                        if (out[k] != '\n' && out[k] != '\r') {
                            out[k] = ' ';
                        }
                    }
                    blanked += e - s - 2;
                }

                @Override
                public Void visitMethod(MethodTree m, Void v) {
                    if (m.getBody() != null) {
                        clear(m.getBody());
                    }
                    return null; // nothing inside a blanked body is read
                }

                @Override
                public Void visitClass(ClassTree c, Void v) {
                    for (Tree member : c.getMembers()) {
                        if (member instanceof com.sun.source.tree.BlockTree init) {
                            clear(init);
                        } else {
                            member.accept(this, null);
                        }
                    }
                    return null;
                }
            }.scan(unit, null);
            return new String(out);
        }
    }

    /** One of the tree's files as javac's source path holds it: blanked, so attributing it
     *  is the cost of its signatures and never of its bodies. */
    static final class TreeSource extends javax.tools.SimpleJavaFileObject {
        final String rel;
        final String binaryName;
        final String text;

        TreeSource(String rel, String binaryName, String text) {
            super(Extract.Source.uri(rel), Kind.SOURCE);
            this.rel = rel;
            this.binaryName = binaryName;
            this.text = text;
        }

        @Override
        public CharSequence getCharContent(boolean ignoreEncodingErrors) {
            return text;
        }
    }

    /** javac's file manager with {@link SourcePath} as its source path. */
    static final class MemorySourcePath extends javax.tools.ForwardingJavaFileManager<
            javax.tools.StandardJavaFileManager> {
        final SourcePath sp;

        MemorySourcePath(javax.tools.StandardJavaFileManager fm, SourcePath sp) {
            super(fm);
            this.sp = sp;
        }

        @Override
        public boolean hasLocation(Location location) {
            return location == javax.tools.StandardLocation.SOURCE_PATH
                || super.hasLocation(location);
        }

        @Override
        public Iterable<JavaFileObject> list(Location location, String pkg,
                                             Set<JavaFileObject.Kind> kinds, boolean recurse)
                throws IOException {
            if (location != javax.tools.StandardLocation.SOURCE_PATH) {
                return super.list(location, pkg, kinds, recurse);
            }
            List<JavaFileObject> out = new ArrayList<>();
            if (!kinds.contains(JavaFileObject.Kind.SOURCE)) {
                return out;
            }
            out.addAll(sp.byPackage.getOrDefault(pkg, List.of()));
            if (recurse) {
                String below = pkg.isEmpty() ? "" : pkg + ".";
                sp.byPackage.forEach((p, fs) -> {
                    if (!p.equals(pkg) && p.startsWith(below)) {
                        out.addAll(fs);
                    }
                });
            }
            return out;
        }

        @Override
        public String inferBinaryName(Location location, JavaFileObject file) {
            TreeSource ts = sp.byUri.get(file.toUri());
            return ts != null ? ts.binaryName : super.inferBinaryName(location, file);
        }

        @Override
        public boolean isSameFile(javax.tools.FileObject a, javax.tools.FileObject b) {
            if (sp.byUri.containsKey(a.toUri()) || sp.byUri.containsKey(b.toUri())
                || "mem".equals(a.toUri().getScheme()) || "mem".equals(b.toUri().getScheme())) {
                return a.toUri().equals(b.toUri());
            }
            return super.isSameFile(a, b);
        }
    }

    /** The package a compilation unit declares, read off its first tokens: whitespace and
     *  comments, then {@code package a.b;} or not. Empty for the unnamed package, and for
     *  anything this does not recognise, which then contributes its own directory. */
    static String packageOf(String text) {
        int i = skip(text, 0);
        if (!text.startsWith("package", i) || i + 7 >= text.length()
            || Character.isJavaIdentifierPart(text.charAt(i + 7))) {
            return "";
        }
        StringBuilder b = new StringBuilder();
        i += 7;
        while (true) {
            i = skip(text, i);
            if (i >= text.length() || text.charAt(i) == ';') {
                return b.toString();
            }
            char c = text.charAt(i);
            if (c == '.' || Character.isJavaIdentifierPart(c)) {
                b.append(c);
                i++;
            } else {
                return "";
            }
        }
    }

    private static int skip(String t, int i) {
        while (i < t.length()) {
            char c = t.charAt(i);
            if (Character.isWhitespace(c) || c == '﻿') {
                i++;
            } else if (t.startsWith("//", i)) {
                int nl = t.indexOf('\n', i);
                i = nl < 0 ? t.length() : nl + 1;
            } else if (t.startsWith("/*", i)) {
                int end = t.indexOf("*/", i + 2);
                i = end < 0 ? t.length() : end + 2;
            } else {
                break;
            }
        }
        return i;
    }

    /** The test hook: a batch holding a file under this directory fills the heap. */
    private static boolean failsOnPurpose(List<List<Path>> batch) {
        String v = System.getenv("DUNNEFLOW_JAVA_FAIL_BATCH");
        if (v == null || v.isBlank()) {
            return false;
        }
        for (List<Path> dir : batch) {
            for (Path f : dir) {
                if (f.toString().replace('\\', '/').contains(v)) {
                    return true;
                }
            }
        }
        return false;
    }

    private static boolean ranOut(Throwable e) {
        for (Throwable t = e; t != null; t = t.getCause()) {
            if (t instanceof HeapFull || t instanceof OutOfMemoryError) {
                return true;
            }
        }
        return false;
    }

    private static int count(List<List<Path>> batch) {
        return batch.stream().mapToInt(List::size).sum();
    }

    /**
     * Every call's far end, in two phases. <b>Phase A</b> is javac, one compilation per
     * batch, each dropped before the next: what each site asks and everything the tree
     * declares, written down as strings. <b>Phase B</b> is no compiler at all: the whole
     * tree's overrider index, then Tom's dispatch rule over every question in order.
     */
    static Found collect(Path root, List<Path> files, Rules rules, Function<Path, String> rel) {
        Found found = new Found();
        if (files.isEmpty()) {
            return found;
        }
        // The jars the build files name, where this machine holds them (`Deps`): never
        // fetched. Put on a file manager of the edge pass's own, so a file's facts never
        // depend on what happens to be in somebody's cache (rule 95).
        Deps.Result deps = Deps.resolve(root);
        found.readBeyond.addAll(deps.read);
        found.notPresent.addAll(deps.absent);
        found.notes.addAll(deps.notes);

        Map<Path, String> tree = new HashMap<>();
        for (Path f : files) {
            tree.put(f.toAbsolutePath().normalize(), rel.apply(f));
        }
        int cap = batchCap();
        List<List<List<Path>>> planned = plan(files, cap);
        boolean batched = planned.size() > 1;
        long t0 = System.nanoTime();
        SourcePath sp = batched ? SourcePath.read(files, rel, found.notes) : null;
        if (sp != null) {
            Main.note(String.format(
                "edges: read %d files (%.1f M characters) once and blanked %.0f%% of them "
                + "as bodies, in %.1f s", sp.byRel.size(), sp.chars / 1e6,
                100.0 * sp.blanked / Math.max(1, sp.chars), (System.nanoTime() - t0) / 1e9));
        }
        java.util.ArrayDeque<List<List<Path>>> queue = new java.util.ArrayDeque<>(planned);

        Index index = new Index();
        List<Question> questions = new ArrayList<>();
        long[] errors = {0};
        int[] units = {0};
        Map<String, Integer> missing = new TreeMap<>();
        List<String> givenUp = new ArrayList<>();
        int compilations = 0;
        int splits = 0;
        while (!queue.isEmpty()) {
            List<List<Path>> batch = queue.pollFirst();
            if (batched) {
                System.gc(); // the last batch's compilation is garbage; measure without it
            }
            long tb = System.nanoTime();
            long startHeap = heapAfterCollection();
            attributed[0] = 0;
            attributed[1] = 0;
            String failed = attribute(batch, root, rules, rel, tree, sp, deps.jars, index,
                questions, errors, units, missing, found);
            compilations++;
            if (batched) {
                // Progress, on the evidence channel: a pass this long says where it is.
                Main.note(String.format(
                    "edges: compilation %d, %d files, %.1f s%s; %d queued; heap after "
                    + "collection %d of %d MB at its start; attributed %d of its own "
                    + "classes and %d off the source path",
                    compilations, count(batch), (System.nanoTime() - tb) / 1e9,
                    failed == null ? "" : " (" + failed + ")", queue.size(),
                    startHeap / (1024 * 1024), heapMaxMb(), attributed[0], attributed[1]));
            }
            if (failed == null) {
                continue;
            }
            if (!failed.startsWith("heap")) {
                // javac crashed on this batch. Nothing is guessed: its calls are left to
                // the host as unresolved, and the reason is said.
                found.notes.add("edges: javac failed attributing "
                    + (batched ? "a compilation of " + count(batch) + " files" : "this tree")
                    + ": " + failed);
                if (!batched) {
                    return found;
                }
                batch.forEach(d -> givenUp.add(dirOf(d, rel)));
                continue;
            }
            if (batch.size() > 1) {
                splits++;
                int mid = batch.size() / 2;
                queue.addFirst(new ArrayList<>(batch.subList(mid, batch.size())));
                queue.addFirst(new ArrayList<>(batch.subList(0, mid)));
                if (!batched) {
                    batched = true;
                    sp = SourcePath.read(files, rel, found.notes);
                }
            } else {
                givenUp.add(dirOf(batch.get(0), rel));
            }
        }
        if (errors[0] > 0) {
            found.notes.add("edges: javac reported " + errors[0] + " errors attributing "
                + units[0] + " files; calls whose receiver it could not type are "
                + "`untyped`, never guessed");
            missing.entrySet().stream().sorted((a, b) -> b.getValue() - a.getValue()).limit(8)
                .forEach(e -> found.notes.add("  " + e.getValue() + "x " + e.getKey()));
        }
        if (batched) {
            found.notes.add("edges: the tree's " + files.size() + " files were attributed in "
                + compilations + " compilations of at most " + cap + ", each with the rest of "
                + "the tree on its source path"
                + (splits == 0 ? "" : "; " + splits + " filled " + Math.round(HEAP_CEILING * 100)
                    + "% of the " + heapMaxMb() + " MB heap and were split in two"));
        }
        if (!givenUp.isEmpty()) {
            found.notes.add("edges: " + givenUp.size() + " directories could not be attributed "
                + "and were given up, so their calls are unresolved, and any call that could "
                + "dispatch into them is `unfollowed` rather than drawn: "
                + String.join(", ", givenUp.subList(0, Math.min(8, givenUp.size())))
                + (givenUp.size() > 8 ? " and " + (givenUp.size() - 8) + " more" : ""));
        }
        decide(questions, index, !givenUp.isEmpty(), found);
        if (!found.touches.isEmpty()) {
            found.notes.add("edges: " + found.touches.size() + " calls are boundary touches by "
                + "a type javac named or by what the receiver's class extends, and are touches "
                + "rather than calls with no edge");
        }
        if (!found.waysIn.isEmpty()) {
            found.notes.add("edges: " + found.waysIn.size() + " methods are ways in by what "
                + "their class extends");
        }
        return found;
    }

    private static String dirOf(List<Path> dir, Function<Path, String> rel) {
        String r = rel.apply(dir.get(0));
        int slash = r.lastIndexOf('/');
        return slash < 0 ? "." : r.substring(0, slash);
    }

    /** One batch's facts as the walk made them, for the two things the edge pass says in the
     *  walk's own terms: the line a call was stored at, and the routine stored at a place. */
    private static final class Walked {
        final Map<String, Facts.CallSite> calls = new HashMap<>();
        final Map<String, Facts.Routine> routines = new HashMap<>();
        final Set<String> twice = new java.util.HashSet<>();

        void add(Facts.FileFacts ff) {
            for (Facts.CallSite c : ff.calls) {
                calls.put(c.site_id, c);
            }
            for (Facts.Routine r : ff.routines) {
                String k = at(ff.path, r.line_start, r.name);
                if (routines.put(k, r) != null) {
                    twice.add(k); // two routines of one name on one line: neither is named
                }
            }
        }

        static String at(String file, long line, String name) {
            return file + "\u0000" + line + "\u0000" + name;
        }

        Facts.Routine routine(String file, long line, String name) {
            String k = at(file, line, name);
            return twice.contains(k) ? null : routines.get(k);
        }
    }

    /** Phase A for one batch. Null when it was attributed and recorded; otherwise why not,
     *  beginning {@code heap} when it ran out of room and may be split. */
    private static String attribute(List<List<Path>> batch, Path root, Rules rules,
                                    Function<Path, String> rel, Map<Path, String> tree,
                                    SourcePath sp, List<Path> jars, Index index,
                                    List<Question> questions, long[] errors, int[] nUnits,
                                    Map<String, Integer> missing, Found found) {
        if (failsOnPurpose(batch)) {
            return "heap (DUNNEFLOW_JAVA_FAIL_BATCH)";
        }
        List<Extract.Source> sources = new ArrayList<>();
        Map<String, String> texts = new HashMap<>();
        // javac wraps every file object it is handed, so a unit is ours by its URI and never
        // by its class: a cast was a ClassCastException on the first tree it met.
        Map<java.net.URI, Extract.Source> byUri = new HashMap<>();
        for (List<Path> dir : batch) {
            for (Path f : dir) {
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
        }
        long[] batchErrors = {0};
        Map<String, Integer> batchMissing = new TreeMap<>();
        DiagnosticListener<JavaFileObject> listen = d -> {
            // **This batch's own files only.** A class off the source path is blanked, so
            // it reports errors nobody wrote, and it is loaded by every batch that names
            // it: counted there, one error would be counted once per batch (rule 32).
            if (d.getKind() == Diagnostic.Kind.ERROR
                && (d.getSource() == null || byUri.containsKey(d.getSource().toUri()))) {
                batchErrors[0]++;
                if ("compiler.err.cant.resolve.location".equals(d.getCode())
                    || "compiler.err.doesnt.exist".equals(d.getCode())) {
                    String m = d.getMessage(java.util.Locale.ROOT).lines().findFirst().orElse("");
                    batchMissing.merge(m, 1, Integer::sum);
                }
            }
        };
        javax.tools.StandardJavaFileManager fm = Extract.compiler().getStandardFileManager(
            null, java.util.Locale.ROOT, java.nio.charset.StandardCharsets.UTF_8);
        try {
            fm.setLocationFromPaths(javax.tools.StandardLocation.CLASS_PATH, jars);
        } catch (IOException e) {
            found.notes.add("edges: the dependency jars could not be put on the classpath: " + e);
        }
        javax.tools.JavaFileManager files = sp == null ? fm : new MemorySourcePath(fm, sp);
        JavacTask task = (JavacTask) Extract.compiler().getTask(
            null, files, listen,
            // `-Xmaxerrs`: javac stops *reporting* at 100 by default, and the note below
            // said "100 errors" of traccar's 400 (rule 32: a count says what it counts).
            List.of("-proc:none", "-Xlint:none", "-nowarn", "-implicit:none",
                "-Xmaxerrs", String.valueOf(Integer.MAX_VALUE),
                "-XDshould-stop.ifError=FLOW", "-XDshould-stop.ifNoError=FLOW"),
            null, sources);
        task.addTaskListener(new com.sun.source.util.TaskListener() {
            @Override
            public void started(com.sun.source.util.TaskEvent ev) {
                if (ev.getKind() == com.sun.source.util.TaskEvent.Kind.ANALYZE) {
                    // Whose class javac is attributing: this batch's, or one it loaded off
                    // the source path. Said in the progress note; the second is pure cost.
                    boolean own = ev.getSourceFile() != null
                        && byUri.containsKey(ev.getSourceFile().toUri());
                    attributed[own ? 0 : 1]++;
                }
                if (heapNearlyFull()) {
                    throw new HeapFull("heap");
                }
            }
        });
        List<Site> sites = new ArrayList<>();
        List<CompilationUnitTree> units = new ArrayList<>();
        // What the walk stored, as it stored it: a touch is on the line its call was
        // recorded at, and a way in is the routine recorded at that place.
        Walked walked = new Walked();
        try {
            for (CompilationUnitTree unit : task.parse()) {
                units.add(unit);
                String r = byUri.get(unit.getSourceFile().toUri()).rel;
                Facts.FileFacts ff = Extract.walk(r, texts.get(r), unit, task, rules,
                    (node, siteId, caller, dotted, atBoundary, construction) -> {
                        // Rule 2: a call that touches a boundary is never also an edge.
                        if (!atBoundary) {
                            sites.add(new Site(unit, node, siteId, caller, dotted, construction));
                        }
                    });
                walked.add(ff);
            }
            task.analyze();
            Resolver r = new Resolver(task, units, texts, byUri, tree, sp, index, rules, walked);
            List<Question> mine = new ArrayList<>(sites.size());
            for (Site s : sites) {
                mine.add(r.ask(s));
            }
            // Only a batch that finished is counted, so a split batch's errors are not
            // said twice.
            questions.addAll(mine);
            found.waysIn.addAll(r.waysIn);
            errors[0] += batchErrors[0];
            nUnits[0] += units.size();
            batchMissing.forEach((k, v) -> missing.merge(k, v, Integer::sum));
            return null;
        } catch (IOException e) {
            return "javac could not read the text it was handed: " + e;
        } catch (RuntimeException | OutOfMemoryError e) {
            if (ranOut(e)) {
                return "heap";
            }
            return Main.describe(e);
        } finally {
            try {
                fm.close();
            } catch (IOException e) {
                // nothing held that matters once the batch is dropped
            }
        }
    }

    /**
     * Phase B: Tom's dispatch rule over the whole tree's index, in the order the sites
     * were walked. With a directory given up, the index is not the whole tree's, so
     * nothing that depends on <i>no other body</i> may be drawn: only a call no override
     * can reach keeps its edge, and the rest are {@code unfollowed} (rules 1 and 49).
     */
    private static void decide(List<Question> questions, Index index, boolean incomplete,
                               Found found) {
        for (Question q : questions) {
            Facts.SuppliedEdge e = q.e;
            if (q.pending) {
                decide(q, index, incomplete);
            }
            if (q.touch != null && e.file.isEmpty() && e.constructs.isEmpty()
                && ("outside".equals(e.reason) || "untyped".equals(e.reason))) {
                // No body in the tree answers it, and its type says what it is: a touch, and
                // so not an edge and not a call this map could not follow (rule 2).
                found.touches.add(q.touch);
                continue;
            }
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

    private static void decide(Question q, Index index, boolean incomplete) {
        Facts.SuppliedEdge e = q.e;
        if (incomplete && !q.nonVirtual) {
            e.reason = "unfollowed";
            e.frontier = q.frontier + " (whether the tree overrides it is not known: a "
                + "directory could not be attributed)";
            return;
        }
        List<Over> over = overridersOf(index, q.targetKey, q.receiverKey);
        if (!q.home) {
            if (!q.nonVirtual && !over.isEmpty()) {
                e.reason = "dynamic";
                e.candidates = over.size();
                e.frontier = q.frontier;
                answers(over, e);
                return;
            }
            e.reason = "outside";
            e.how = "symbol";
            e.frontier = q.frontier;
            return;
        }
        if (q.nonVirtual && q.hasBody) {
            point(q, e);
            e.how = "non-virtual";
            return;
        }
        if (incomplete) {
            e.reason = "unfollowed";
            e.frontier = q.frontier + " (whether the tree overrides it is not known: a "
                + "directory could not be attributed)";
            return;
        }
        if (over.isEmpty() && q.hasBody) {
            point(q, e);
            e.how = "unoverridden";
            return;
        }
        int answering = (q.hasBody ? 1 : 0) + (int) over.stream().filter(Over::hasBody).count();
        if (answering == 0) {
            // An interface no class in the tree implements: Spring Data writes the
            // repository at run time, and a library's caller writes the rest.
            e.reason = "outside";
            e.how = "unimplemented";
            e.frontier = q.frontier;
            return;
        }
        e.reason = "dynamic";
        e.candidates = answering;
        e.frontier = q.frontier;
        if (q.hasBody) {
            Facts.Answer a = new Facts.Answer();
            a.file = q.file;
            a.line = q.line;
            a.name = q.name;
            e.answers.add(a);
        }
        answers(over, e);
    }

    private static void point(Question q, Facts.SuppliedEdge e) {
        e.file = q.file;
        e.line = q.line;
        e.name = q.name;
    }

    /** Where each body that may answer a dispatched call is, by the same line rule an
     *  edge's target is named by (`schema.Answer`). Only bodies: a declaration with none
     *  is not a routine, and could not be linked to one. */
    private static void answers(List<Over> over, Facts.SuppliedEdge e) {
        for (Over o : over) {
            if (!o.hasBody()) {
                continue;
            }
            Facts.Answer a = new Facts.Answer();
            a.file = o.file();
            a.line = o.line();
            a.name = o.name();
            e.answers.add(a);
        }
    }

    /** The methods in the tree that can answer this call instead of its target: the ones
     *  that override it <b>in a subtype of the receiver's static type</b>. A sibling
     *  class's override can never answer a call on this receiver: {@code Event}'s
     *  {@code setDeviceId()} is {@code Message}'s, whatever {@code Command}, another
     *  subclass of {@code Message}, does with its own (traccar, 2026-11-01). A null
     *  receiver could not be said, and counts every override rather than guessing which. */
    private static List<Over> overridersOf(Index index, String target, String receiver) {
        List<Over> all = index.overriddenBy.getOrDefault(target, List.of());
        if (receiver == null || all.isEmpty()) {
            return all;
        }
        List<Over> out = new ArrayList<>();
        for (Over o : all) {
            Set<String> up = index.closure.get(o.ownerKey());
            if (up == null || up.contains(receiver)) {
                out.add(o);
            }
        }
        return out;
    }

    /** Attribution's answers, turned into the host's terms. */
    private static final class Resolver {
        final Trees trees;
        final Elements elements;
        final javax.lang.model.util.Types types;
        final SourcePositions pos;
        final Map<String, String> texts;
        final Map<java.net.URI, Extract.Source> byUri;
        final Map<Path, String> tree;
        /** The tree held in memory as javac's source path, or null for one compilation. */
        final SourcePath sp;
        final Index index;
        final Rules rules;
        final Walked walked;
        final List<Facts.SuppliedWayIn> waysIn = new ArrayList<>();
        /** Every name a class is a subtype of, as {@link #lineage} reads them. */
        final Map<TypeElement, Set<String>> lineages = new IdentityHashMap<>();
        /** A supertype's methods by name, asked once per type in this batch. */
        final Map<TypeElement, Map<String, List<ExecutableElement>>> declared =
            new IdentityHashMap<>();

        Resolver(JavacTask task, List<CompilationUnitTree> units, Map<String, String> texts,
                 Map<java.net.URI, Extract.Source> byUri, Map<Path, String> tree,
                 SourcePath sp, Index index, Rules rules, Walked walked) {
            this.trees = Trees.instance(task);
            this.elements = task.getElements();
            this.types = task.getTypes();
            this.pos = trees.getSourcePositions();
            this.texts = texts;
            this.byUri = byUri;
            this.tree = tree;
            this.sp = sp;
            this.index = index;
            this.rules = rules;
            this.walked = walked;
            for (CompilationUnitTree unit : units) {
                new TreePathScanner<Void, Void>() {
                    @Override
                    public Void visitMethod(MethodTree m, Void v) {
                        if (trees.getElement(getCurrentPath()) instanceof ExecutableElement e) {
                            declare(getCurrentPath(), m, e);
                        }
                        return super.visitMethod(m, v);
                    }
                }.scan(unit, null);
            }
        }

        /** Write down what this method overrides, and where it is, so a call in any batch
         *  can count it. Only a method can override; javac's own answer decides which. */
        void declare(TreePath path, MethodTree m, ExecutableElement e) {
            if (e.getKind() != ElementKind.METHOD || e.getModifiers().contains(Modifier.STATIC)
                || e.getModifiers().contains(Modifier.PRIVATE)
                || !(e.getEnclosingElement() instanceof TypeElement owner)) {
                return;
            }
            Set<String> up = closure(owner);
            Over self = null;
            String name = e.getSimpleName().toString();
            wayIn(path, m, e, owner);
            for (TypeElement sup : supertypes(owner)) {
                for (ExecutableElement x : declared(sup).getOrDefault(name, List.of())) {
                    if (!sameSlot(e, x, owner)) {
                        continue;
                    }
                    if (self == null) {
                        Facts.SuppliedEdge at = new Facts.SuppliedEdge();
                        pointAt(path, e, at);
                        self = new Over(key(e), key(owner), m.getBody() != null, at.file,
                            at.line, at.name);
                    }
                    String k = key(x);
                    if (index.seen.add(k + "\u0000" + self.file() + ":" + self.line())) {
                        index.overriddenBy.computeIfAbsent(k, z -> new ArrayList<>()).add(self);
                    }
                }
            }
            index.closure.putIfAbsent(key(owner), up);
        }

        /**
         * A way in by inheritance ({@code extends:} with {@code entrypoint}): a method with a
         * body, named by the rule, in a class that extends one of the rule's types, <b>that
         * fills the framework's slot and not one of the program's own</b>. traccar's 69 frame
         * decoders each write a three-argument {@code decode} that overrides traccar's own
         * abstract method; only {@code BaseFrameDecoder}'s is Netty's, and a rule on the name
         * and the class alone would have called all seventy ways in (rule 1).
         */
        void wayIn(TreePath path, MethodTree m, ExecutableElement e, TypeElement owner) {
            if (m.getBody() == null || rules.extending.isEmpty()) {
                return;
            }
            String name = e.getSimpleName().toString();
            for (Rules.Extends rule : rules.extending) {
                if (rule.entrypoint.isEmpty() || !rule.methods.contains(name)) {
                    continue;
                }
                String type = rule.among(lineage(owner));
                if (type == null || !fillsAnOutsideSlot(e, owner, new java.util.HashSet<>())) {
                    continue;
                }
                Facts.EntrypointKind kind = null;
                for (Facts.EntrypointKind k : Facts.EntrypointKind.values()) {
                    if (k.wire.equals(rule.entrypoint)) {
                        kind = k;
                    }
                }
                Facts.SuppliedEdge at = new Facts.SuppliedEdge();
                pointAt(path, e, at);
                Facts.Routine r = at.file == null ? null : walked.routine(at.file, at.line, at.name);
                if (kind == null || r == null) {
                    return; // a kind this build does not have, or no routine stored there
                }
                Facts.SuppliedWayIn w = new Facts.SuppliedWayIn();
                w.id = Ids.entrypointId(at.file, List.of(r.qualname, kind.wire, "extends"));
                w.kind = kind;
                String cls = owner.getSimpleName().length() > 0 ? owner.getSimpleName().toString()
                    : "an anonymous " + type.substring(type.lastIndexOf('.') + 1);
                w.name = cls + "." + name;
                w.routine_id = r.id;
                w.file = at.file;
                w.module = r.module;
                w.evidence = name + "() at " + at.file + ":" + at.line + ": "
                    + (owner.getSimpleName().length() > 0 ? owner.getSimpleName() + " extends "
                        : "an anonymous class extends ") + type
                    + (rule.evidence.isEmpty() ? "" : " — " + rule.evidence);
                waysIn.add(w);
                return;
            }
        }

        /**
         * Does this method override one <b>declared outside the tree</b>, directly or through
         * the tree's own classes? With the framework's jars that is javac's own answer. Without
         * them the framework's method is not there to ask about, and the evidence is the
         * source's: {@code @Override} on a method that overrides nothing javac can see says
         * its author overrode something javac cannot.
         */
        boolean fillsAnOutsideSlot(ExecutableElement e, TypeElement owner, Set<ExecutableElement> seen) {
            if (!seen.add(e)) {
                return false;
            }
            boolean any = false;
            String name = e.getSimpleName().toString();
            for (TypeElement sup : supertypes(owner)) {
                if (sup == owner) {
                    continue; // a method overrides nothing of its own class
                }
                for (ExecutableElement x : declared(sup).getOrDefault(name, List.of())) {
                    if (!sameSlot(e, x, owner)) {
                        continue;
                    }
                    any = true;
                    TreePath decl = trees.getPath(x);
                    if (decl == null || ours(decl.getCompilationUnit()) == null) {
                        return true;
                    }
                    if (fillsAnOutsideSlot(x, sup, seen)) {
                        return true;
                    }
                }
            }
            if (any) {
                return false;
            }
            for (javax.lang.model.element.AnnotationMirror a : e.getAnnotationMirrors()) {
                if (a.getAnnotationType().toString().equals("java.lang.Override")) {
                    return true;
                }
            }
            return false;
        }

        /**
         * javac's {@code overrides}, <b>refused where it was a guess</b>. A parameter whose
         * type javac could not load is an error type, and an error type matches anything:
         * with Netty missing, {@code decode(ctx, Channel, ByteBuf)} "overrides"
         * {@code decode(ctx, ByteBuf, List)}, which would make each of traccar's 69 frame
         * decoders Netty's own slot, and did make {@code BaseFrameDecoder}'s call to its
         * own abstract {@code decode} one that the method making it "may run". Where either
         * side of a parameter is untyped, the two must be written with the same last name:
         * {@code ByteBuf} and {@code io.netty.buffer.ByteBuf} are one type written twice, and
         * refusing that pair would hide an override, which is the worse mistake (rule 1).
         */
        boolean sameSlot(ExecutableElement e, ExecutableElement x, TypeElement owner) {
            if (x == e || !elements.overrides(e, x, owner)) {
                return false;
            }
            List<? extends javax.lang.model.element.VariableElement> a = e.getParameters();
            List<? extends javax.lang.model.element.VariableElement> b = x.getParameters();
            if (a.size() != b.size()) {
                return false;
            }
            for (int i = 0; i < a.size(); i++) {
                javax.lang.model.type.TypeMirror ta = a.get(i).asType();
                javax.lang.model.type.TypeMirror tb = b.get(i).asType();
                boolean blind = ta.getKind() == javax.lang.model.type.TypeKind.ERROR
                    || tb.getKind() == javax.lang.model.type.TypeKind.ERROR;
                if (blind && !lastName(ta.toString()).equals(lastName(tb.toString()))) {
                    return false;
                }
            }
            return true;
        }

        static String lastName(String type) {
            int lt = type.indexOf('<');
            String bare = lt < 0 ? type : type.substring(0, lt);
            return bare.substring(bare.lastIndexOf('.') + 1);
        }

        /**
         * Every type this class is a subtype of, <b>by qualified name</b>: javac's where it
         * could type the supertype, and the file's own words where it could not. A missing
         * dependency leaves {@code extends JpaRepository<Owner, Integer>} an error type whose
         * name javac does not know, and the file does: {@code import org.springframework.data
         * .jpa.repository.JpaRepository;} names exactly one class. An on-demand import
         * ({@code a.b.*}) names a package and is not read (rule 1).
         */
        Set<String> lineage(TypeElement t) {
            Set<String> got = lineages.get(t);
            if (got != null) {
                return got;
            }
            Set<String> out = new java.util.HashSet<>();
            lineages.put(t, out);
            for (TypeElement s : supertypes(t)) {
                boolean typed = s.asType().getKind() != javax.lang.model.type.TypeKind.ERROR;
                if (typed) {
                    out.add(s.getQualifiedName().toString());
                }
                TreePath p;
                try {
                    p = typed ? trees.getPath(s) : null;
                } catch (RuntimeException ex) {
                    p = null;
                }
                if (p == null || !(p.getLeaf() instanceof ClassTree c)) {
                    continue;
                }
                List<Tree> named = new ArrayList<>();
                if (c.getExtendsClause() != null) {
                    named.add(c.getExtendsClause());
                }
                named.addAll(c.getImplementsClause());
                for (Tree n : named) {
                    javax.lang.model.type.TypeMirror m;
                    try {
                        m = trees.getTypeMirror(new TreePath(p, n));
                    } catch (RuntimeException ex) {
                        m = null;
                    }
                    if (m == null || m.getKind() == javax.lang.model.type.TypeKind.ERROR) {
                        String q = written(p.getCompilationUnit(), n);
                        if (q != null) {
                            out.add(q);
                        }
                    }
                }
            }
            return out;
        }

        /** The qualified name a supertype was written as, or null where the file does not
         *  say: its type arguments dropped, its first word looked up among the file's
         *  single-type imports, and a dotted name with no import taken as it stands. */
        static String written(CompilationUnitTree unit, Tree type) {
            Tree bare = type;
            while (true) {
                if (bare instanceof com.sun.source.tree.ParameterizedTypeTree pt) {
                    bare = pt.getType();
                } else if (bare instanceof com.sun.source.tree.AnnotatedTypeTree at) {
                    bare = at.getUnderlyingType();
                } else {
                    break;
                }
            }
            String text = bare.toString().replaceAll("\\s+", "");
            if (text.isEmpty() || !text.matches("[\\w$.]+")) {
                return null;
            }
            int dot = text.indexOf('.');
            String first = dot < 0 ? text : text.substring(0, dot);
            for (com.sun.source.tree.ImportTree imp : unit.getImports()) {
                String q = imp.getQualifiedIdentifier().toString();
                if (!imp.isStatic() && q.endsWith("." + first)) {
                    return q + (dot < 0 ? "" : text.substring(dot));
                }
            }
            return dot < 0 ? null : text;
        }

        /**
         * What this call is, if nothing in the tree answers it. A receiver whose class extends
         * a declared type comes first, because it is the narrower statement; then the method's
         * own declaring type, where javac named one outside the tree.
         */
        Facts.SuppliedTouch touchFor(Site s, ExecutableElement target, TypeElement receiver,
                                     boolean home) {
            Facts.CallSite call = walked.calls.get(s.siteId());
            Extract.Source src = byUri.get(s.unit().getSourceFile().toUri());
            if (call == null || src == null) {
                return null;
            }
            if (receiver == null && target == null
                && s.node() instanceof MethodInvocationTree mi
                && mi.getMethodSelect() instanceof MemberSelectTree ms) {
                // javac could not find the method, and may still have typed what it is called
                // on: `owners.save(o)`, where `save` is declared in a jar that is not here.
                try {
                    javax.lang.model.type.TypeMirror t = trees.getTypeMirror(
                        TreePath.getPath(s.unit(), ms.getExpression()));
                    if (t != null && t.getKind() != javax.lang.model.type.TypeKind.ERROR
                        && types.asElement(t) instanceof TypeElement te) {
                        receiver = te;
                    }
                } catch (RuntimeException ex) {
                    receiver = null;
                }
            }
            boolean objects = target != null && target.getEnclosingElement() instanceof TypeElement o
                && o.getQualifiedName().contentEquals("java.lang.Object");
            if (receiver != null && !objects
                && receiver.asType().getKind() != javax.lang.model.type.TypeKind.ERROR) {
                Set<String> up = null;
                for (Rules.Extends rule : rules.extending) {
                    if (rule.boundary.isEmpty()) {
                        continue;
                    }
                    if (up == null) {
                        up = lineage(receiver);
                    }
                    String type = rule.among(up);
                    if (type != null) {
                        return touch(s, call, src.rel, rule.boundary, rule.direction, rule.salience,
                            receiver.getSimpleName().toString(),
                            receiver.getSimpleName() + " extends " + type
                                + (rule.evidence.isEmpty() ? "" : ": " + rule.evidence));
                    }
                }
            }
            if (target == null || home) {
                return null;
            }
            String qualified = qualified(target);
            Rules.Boundary rule = rules.typed(qualified);
            if (rule == null) {
                return null;
            }
            String to = "";
            if (rule.targetArg != null && rule.targetArg < call.args.size()) {
                to = call.args.get(rule.targetArg).expr;
                if (to.length() >= 2 && to.startsWith("\"") && to.endsWith("\"")
                    && to.indexOf('"', 1) == to.length() - 1) {
                    to = to.substring(1, to.length() - 1);
                }
            }
            return touch(s, call, src.rel, rule.kind, rule.direction, rule.salience, to,
                "typed " + qualified + (rule.note.isEmpty() ? "" : " — " + rule.note));
        }

        Facts.SuppliedTouch touch(Site s, Facts.CallSite call, String file, String kind,
                                  String direction, String salience, String target, String why) {
            Facts.SuppliedTouch t = new Facts.SuppliedTouch();
            for (Facts.BoundaryKind k : Facts.BoundaryKind.values()) {
                if (k.wire.equals(kind)) {
                    t.kind = k;
                }
            }
            for (Facts.Direction d : Facts.Direction.values()) {
                if (d.wire.equals(direction)) {
                    t.direction = d;
                }
            }
            if (t.kind == null || t.direction == null) {
                return null; // a word this build does not have: nothing, never a default
            }
            t.site_id = s.siteId();
            t.file = file;
            t.routine_id = s.caller();
            t.target = target;
            t.line = call.line;
            // The call's spelling first, always (`detectors.EVIDENCE_NOTE`).
            t.evidence = s.dotted() + " — " + why;
            t.salience = salience;
            return t;
        }

        Map<String, List<ExecutableElement>> declared(TypeElement t) {
            return declared.computeIfAbsent(t, z -> {
                Map<String, List<ExecutableElement>> by = new HashMap<>();
                for (Element m : t.getEnclosedElements()) {
                    if (m instanceof ExecutableElement x && m.getKind() == ElementKind.METHOD) {
                        by.computeIfAbsent(x.getSimpleName().toString(),
                            k -> new ArrayList<>()).add(x);
                    }
                }
                return by;
            });
        }

        /** Every type this one is a subtype of, erased, itself first. */
        List<TypeElement> supertypes(TypeElement t) {
            List<TypeElement> out = new ArrayList<>();
            Set<TypeElement> seen = java.util.Collections.newSetFromMap(new IdentityHashMap<>());
            java.util.ArrayDeque<javax.lang.model.type.TypeMirror> todo = new java.util.ArrayDeque<>();
            todo.add(types.erasure(t.asType()));
            while (!todo.isEmpty()) {
                javax.lang.model.type.TypeMirror m = todo.poll();
                if (!(types.asElement(m) instanceof TypeElement te) || !seen.add(te)) {
                    continue;
                }
                out.add(te);
                try {
                    for (javax.lang.model.type.TypeMirror s : types.directSupertypes(m)) {
                        todo.add(types.erasure(s));
                    }
                } catch (RuntimeException ex) {
                    // an error type has no supertypes to list
                }
            }
            return out;
        }

        Set<String> closure(TypeElement t) {
            Set<String> out = new java.util.HashSet<>();
            for (TypeElement s : supertypes(t)) {
                out.add(key(s));
            }
            return out;
        }

        String key(TypeElement t) {
            return elements.getBinaryName(t).toString();
        }

        /** A method's name in every batch: its class's binary name, its name and its erased
         *  parameters. Two batches load one method as two elements and agree on this. */
        String key(ExecutableElement m) {
            StringBuilder b = new StringBuilder();
            b.append(m.getEnclosingElement() instanceof TypeElement t ? key(t)
                : m.getEnclosingElement().toString());
            b.append('#').append(m.getKind() == ElementKind.CONSTRUCTOR ? "<init>"
                : m.getSimpleName().toString()).append('(');
            boolean first = true;
            for (javax.lang.model.element.VariableElement p : m.getParameters()) {
                if (!first) {
                    b.append(',');
                }
                first = false;
                b.append(types.erasure(p.asType()));
            }
            return b.append(')').toString();
        }

        /** Phase A of one site: everything javac can answer now, and what Phase B needs. */
        Question ask(Site s) {
            Question q = new Question();
            Facts.SuppliedEdge e = q.e;
            e.site_id = s.siteId();
            e.caller_id = s.caller();
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
                q.touch = touchFor(s, null, null, false);
                return q;
            }
            TypeElement owner = target.getEnclosingElement() instanceof TypeElement t ? t : null;
            if (guessed(s, target, owner)) {
                // javac chose one of several overloads with an argument it could not type,
                // which is a pick and not an answer: `width(m.part())` went to `width(int)`
                // with nothing to say it was not `width(String)` (rule 1).
                e.reason = "untyped";
                e.frontier = s.dotted();
                q.touch = touchFor(s, target, receiverType(s, target, owner), false);
                return q;
            }
            if (s.construction() && owner != null && owner.getNestingKind().name().equals("ANONYMOUS")) {
                // `new Runnable() { … }` builds a class with no name and no structure.
                e.reason = "unfollowed";
                e.frontier = "anonymous " + s.dotted();
                return q;
            }
            TreePath decl = trees.getPath(target);
            String home = decl == null ? null : ours(decl.getCompilationUnit());
            TypeElement receiver = receiverType(s, target, owner);
            q.receiverKey = receiver == null
                || receiver.asType().getKind() == javax.lang.model.type.TypeKind.ERROR
                ? null : key(receiver);
            q.targetKey = key(target);
            q.frontier = qualified(target);
            q.nonVirtual = nonVirtual(s, target, owner);
            if (elements.getOrigin(target) == Elements.Origin.EXPLICIT || home == null) {
                q.touch = touchFor(s, target, receiver, home != null);
            }
            if (home == null) {
                q.pending = true;
                return q;
            }
            if (elements.getOrigin(target) != Elements.Origin.EXPLICIT) {
                implicit(s, target, owner, e);
                return q;
            }
            q.home = true;
            q.hasBody = decl.getLeaf() instanceof MethodTree mt && mt.getBody() != null;
            Facts.SuppliedEdge at = new Facts.SuppliedEdge();
            pointAt(decl, target, at);
            q.file = at.file;
            q.line = at.line;
            q.name = at.name;
            q.pending = true;
            return q;
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
            // **Counted over the class and what it extends, by hand.** `Elements.getAllMembers`
            // returns nothing at all for a class one of whose supertypes javac could not
            // load, so this said "no rival" of every class that extends a missing library's:
            // traccar's `BaseFrameDecoder` calls its abstract `decode(ctx, channel, buf)`,
            // javac chose the `decode(ctx, in, out)` that makes the call, and the map drew a
            // routine calling itself (2026-11-12). An override is the same slot as what it
            // overrides and is counted once, by its parameters as written.
            Set<String> shapes = new java.util.HashSet<>();
            try {
                boolean ctor = target.getKind() == ElementKind.CONSTRUCTOR;
                for (TypeElement sup : ctor ? List.of(owner) : supertypes(owner)) {
                    for (Element m : sup.getEnclosedElements()) {
                        if (m.getKind() == target.getKind() && m instanceof ExecutableElement x
                            && m.getSimpleName().contentEquals(target.getSimpleName())) {
                            StringBuilder shape = new StringBuilder();
                            for (javax.lang.model.element.VariableElement p : x.getParameters()) {
                                shape.append(lastName(types.erasure(p.asType()).toString()))
                                    .append(',');
                            }
                            shapes.add(shape.toString());
                        }
                    }
                }
            } catch (RuntimeException ex) {
                return true; // its members cannot be listed, so nothing rules a rival out
            }
            return shapes.size() > 1;
        }

        /** A member javac declared and the source did not: a default constructor, a
         *  record's canonical constructor and accessors, an enum's {@code values()}. A
         *  constructor builds one of the program's own types, which has a structure to
         *  point at (`SuppliedEdge.constructs`); anything else has no routine at all. */
        void implicit(Site s, ExecutableElement target, TypeElement owner, Facts.SuppliedEdge e) {
            if (target.getKind() == ElementKind.CONSTRUCTOR && owner != null) {
                TreePath cls = trees.getPath(owner);
                String src = cls == null ? null : ours(cls.getCompilationUnit());
                if (src != null && cls.getLeaf() instanceof ClassTree ct) {
                    e.constructs = qualnameOf(cls);
                    e.file = src;
                    e.line = lineOf(cls.getCompilationUnit(), src, ct, ct.getModifiers());
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

        /** The tree's name for the file this unit was read from, or null when it is not
         *  one of the tree's walked files. A batch's own units are ours by their URI; a
         *  unit javac loaded off the source path is ours by its path. */
        String ours(CompilationUnitTree unit) {
            JavaFileObject fo = unit.getSourceFile();
            if (fo == null) {
                return null;
            }
            Extract.Source src = byUri.get(fo.toUri());
            if (src != null) {
                return src.rel;
            }
            TreeSource held = sp == null ? null : sp.byUri.get(fo.toUri());
            if (held != null) {
                return held.rel;
            }
            if (!"file".equals(fo.toUri().getScheme())) {
                return null;
            }
            try {
                return tree.get(Path.of(fo.toUri()).toAbsolutePath().normalize());
            } catch (RuntimeException ex) {
                return null;
            }
        }

        /** The text the unit was parsed from: the batch's own, or what javac read off the
         *  source path, which is the text its positions count in. */
        String textOf(CompilationUnitTree unit, String rel) {
            String t = texts.get(rel);
            if (t != null) {
                return t;
            }
            try {
                t = unit.getSourceFile().getCharContent(true).toString();
            } catch (IOException ex) {
                t = "";
            }
            texts.put(rel, t);
            return t;
        }

        void pointAt(TreePath decl, ExecutableElement target, Facts.SuppliedEdge e) {
            String src = ours(decl.getCompilationUnit());
            MethodTree m = (MethodTree) decl.getLeaf();
            e.file = src;
            e.line = lineOf(decl.getCompilationUnit(), src, m, m.getModifiers());
            e.name = target.getKind() == ElementKind.CONSTRUCTOR
                ? target.getEnclosingElement().getSimpleName().toString()
                : target.getSimpleName().toString();
        }

        long lineOf(CompilationUnitTree unit, String rel, Tree decl,
                    com.sun.source.tree.ModifiersTree mods) {
            long at = Extract.declStart(pos, unit, textOf(unit, rel), decl, mods);
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
