package dunneflow.reader;

import com.sun.source.tree.CompilationUnitTree;
import com.sun.source.util.JavacTask;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import javax.tools.Diagnostic;
import javax.tools.DiagnosticCollector;
import javax.tools.JavaCompiler;
import javax.tools.JavaFileObject;
import javax.tools.SimpleJavaFileObject;
import javax.tools.StandardJavaFileManager;
import javax.tools.ToolProvider;

/**
 * One file's facts. This is chunk 1 of the Java reader: the file parses or it says why,
 * and its module scope is named the way every other reader names one. Routines, calls,
 * boundaries and the rest arrive in chunk 2.
 *
 * <p><b>javac is given the host's text, never the file.</b> {@link Source} hands it
 * {@code SOURCE_TEXT}, so every position javac reports is an offset into the text the
 * host hashed. Left to read the file itself, javac would see a CRLF file's carriage
 * returns and the bytes Python replaced, and every column after either would be somebody
 * else's.
 */
public final class Extract {
    private Extract() {}

    public static final String MODULE_SCOPE = "<module>";

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

        private static URI uri(String rel) {
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
        if (!parsed.errors.isEmpty()) {
            // A parse error is a fact about the file, never a failure of the reader: the
            // host records it and the rest of the tree is read.
            ff.errors.addAll(parsed.errors);
            return ff;
        }
        ff.module_scope = moduleScope(rel, ff.module, source);
        return ff;
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
        r.docstring = "Declarations at file level: the package, imports and type headers.";
        r.body_hash = Ids.hashSource(source);
        return r;
    }
}
