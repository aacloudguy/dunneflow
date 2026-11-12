package dunneflow.reader;

import java.io.BufferedReader;
import java.io.FileOutputStream;
import java.io.FileDescriptor;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The Java reader, on the far side of a pipe.
 *
 * <p>{@code plugins/go/main.go} and {@code plugins/rust/src/main.rs} are the worked
 * examples this follows, and the three agree on every rule that matters.
 *
 * <p><b>stdout carries protocol and nothing else.</b> Every diagnostic goes to stderr,
 * which the host drains into a ring buffer and never parses. In Java that is enforced
 * rather than hoped for: the real stdout is taken once, here, and {@code System.out} is
 * then pointed at stderr. A stray {@code System.out.println} anywhere in this reader, or in
 * javac, is a note and never a frame the host cannot read.
 *
 * <p><b>Every reply echoes the request's {@code id}.</b> The host correlates on it.
 *
 * <p><b>A file that will not parse is {@code facts} with an error. A file that made this
 * reader throw is {@code failed}.</b> These are two different facts, and only the second
 * lets the host write the record, because a reader that has just crashed on a file is not
 * the right authority on what that file is.
 */
public final class Main {
    static final long PROTOCOL = 1;
    static final String LANG = "java";
    /** {@code plugin.json}'s. The handshake refuses the language if they differ. */
    static final String VERSION = "0.2.0";

    private final OutputStream out;
    private Path root = Path.of(".").toAbsolutePath();
    private List<Path> files = new ArrayList<>();
    private Rules rules = new Rules(null);

    private Main(OutputStream out) {
        this.out = out;
    }

    /** The other channel: evidence, never a control signal. */
    public static void note(String msg) {
        System.err.println(msg);
    }

    private void send(String frame) {
        // One write and one flush per frame: the host reads lines, and half a line is a
        // frame it cannot read.
        try {
            out.write((frame + "\n").getBytes(StandardCharsets.US_ASCII));
            out.flush();
        } catch (IOException e) {
            System.exit(0); // the host has gone; there is nobody left to answer
        }
    }

    private Json.Frame hello() {
        Map<String, Object> caps = new LinkedHashMap<>();
        caps.put("supplies_edges", true);
        caps.put("supplies_touches", true);
        caps.put("supplies_ways_in", true);
        caps.put("reports_literals", true);
        return new Json.Frame("ready").put("lang", LANG).put("version", VERSION)
            .put("protocol", PROTOCOL).put("schema_version", Facts.SCHEMA_VERSION)
            .put("capabilities", caps);
    }

    private Json.Frame open(Object v) {
        String r = Json.str(v, "root");
        // Absolute, because every path this reader is asked about is made absolute before
        // it is related to the root (`main.go`'s finding, rule 60).
        root = Path.of(r == null ? "." : r).toAbsolutePath().normalize();
        files = new ArrayList<>();
        for (String f : Json.strings(Json.get(v, "files"))) {
            files.add(Path.of(f).toAbsolutePath().normalize());
        }
        rules = new Rules(Json.get(v, "rules"));
        List<String> diagnostics = new ArrayList<>();
        if (rules.boundaryCount() == 0) {
            // Not an error and not silent: a run with no rules is a map with no
            // boundaries, which looks exactly like a program that touches nothing (rule 49).
            note("no boundary rules arrived with this session; the map will report none");
            diagnostics.add("no boundary rules arrived with this session");
        }
        return new Json.Frame("opened").put("files", (long) files.size())
            .put("diagnostics", diagnostics);
    }

    /** The stored spelling of a path: relative to the analysed root, with forward slashes
     *  on every platform (rule 93). */
    String relPath(Path abs) {
        Path rel = abs.startsWith(root) ? root.relativize(abs) : abs;
        String s = rel.toString().replace('\\', '/');
        return s.isEmpty() ? abs.toString().replace('\\', '/') : s;
    }

    private Json.Frame extract(Object v) {
        String p = Json.str(v, "path");
        Path abs = Path.of(p == null ? "" : p).toAbsolutePath().normalize();
        String source;
        try {
            source = Text.readSource(abs);
        } catch (IOException e) {
            // Nothing was read badly; nothing was read. A reader may describe that.
            return new Json.Frame("failed").put("reason", "could not be read: " + e);
        }
        String rel = relPath(abs);
        try {
            Facts.FileFacts ff = Extract.extractFile(rel, source, rules);
            // Echoed rather than assumed: the hash of what was actually read. Encoded here,
            // inside the guard, so a fact the encoder refuses is this file's failure and not
            // the session's (`Facts.java`: a required field left unset throws).
            StringBuilder facts = new StringBuilder();
            ff.writeJson(facts);
            return new Json.Frame("facts").put("hash", Ids.hashSource(source))
                .put("facts", new Json.Raw(facts.toString()));
        } catch (RuntimeException | StackOverflowError e) {
            return new Json.Frame("failed").put("reason", describe(e));
        }
    }

    /** Every call's far end, one frame each: a tree's answer is tens of thousands of them,
     *  and one line holding all of them has no bound. */
    private void edges(Object id) {
        Edges.Found found = Edges.collect(root, files, rules, this::relPath);
        long supplied = 0;
        for (Facts.SuppliedEdge e : found.edges) {
            if (!e.file.isEmpty()) {
                supplied++;
            }
            send(new Json.Frame("edge").put("id", id).put("edge", e).finish());
        }
        for (Facts.SuppliedTouch t : found.touches) {
            send(new Json.Frame("touch").put("id", id).put("touch", t).finish());
        }
        for (Facts.SuppliedWayIn w : found.waysIn) {
            send(new Json.Frame("way_in").put("id", id).put("way_in", w).finish());
        }
        for (String n : found.notes) {
            note(n);
        }
        send(new Json.Frame("edges_done").put("id", id).put("supplied", supplied)
            .put("touches", (long) found.touches.size())
            .put("ways_in", (long) found.waysIn.size())
            .put("unresolved", found.outside + found.unknown)
            .put("outside", found.outside).put("unknown", found.unknown)
            .put("read_beyond", found.readBeyond).put("not_present", found.notPresent)
            .put("notes", found.notes)
            .finish());
    }

    private void handle(String line) {
        Object v;
        try {
            v = Json.parse(line);
        } catch (IllegalArgumentException e) {
            note("unreadable frame (" + e.getMessage() + "): "
                + line.substring(0, Math.min(120, line.length())));
            return;
        }
        Object id = Json.get(v, "id");
        String t = Json.str(v, "t");
        t = t == null ? "" : t;
        Json.Frame reply;
        try {
            switch (t) {
                case "close" -> {
                    send(new Json.Frame("closed").put("id", id).finish());
                    System.exit(0);
                    return;
                }
                case "edges" -> {
                    edges(id);
                    return;
                }
                case "hello" -> reply = hello();
                case "open" -> reply = open(v);
                case "extract" -> reply = extract(v);
                default -> reply = new Json.Frame("error").put("reason", "unknown frame " + t);
            }
        } catch (RuntimeException | StackOverflowError e) {
            reply = new Json.Frame("error").put("reason", describe(e));
        }
        reply.put("id", id);
        send(reply.finish());
    }

    static String describe(Throwable e) {
        StringWriter w = new StringWriter();
        e.printStackTrace(new PrintWriter(w));
        note(w.toString());
        String msg = e.getMessage();
        return e.getClass().getSimpleName() + (msg == null ? "" : ": " + msg);
    }

    public static void main(String[] args) throws IOException {
        if (args.length == 2 && args[0].equals("--self-test")) {
            System.exit(SelfTest.run(Path.of(args[1])));
            return;
        }
        // The protocol's channel, taken before anything can write to it; `System.out` is
        // stderr from here on (see the class comment).
        OutputStream protocol = new FileOutputStream(FileDescriptor.out);
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.err), true,
            StandardCharsets.UTF_8));
        Main m = new Main(protocol);
        BufferedReader in = new BufferedReader(
            new InputStreamReader(System.in, StandardCharsets.UTF_8));
        String line;
        while ((line = in.readLine()) != null) {
            if (!line.isBlank()) {
                m.handle(line.strip());
            }
        }
    }
}
