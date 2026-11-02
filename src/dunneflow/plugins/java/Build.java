// Builds the Java reader: `java Build.java <output>`, run by the host in this directory.
//
// **The build is one command, so the build is a Java program.** The host's `build` seam
// runs one argv, and a JDK has no single command that both compiles and makes a jar. This
// file is run by the JDK's own single-file source launcher. It compiles `src/` with the
// system compiler and writes the jar with `java.util.jar`. There is no Maven, no Gradle and
// no download, so building the reader is never egress (design rule 14).
//
// **A `java` with no compiler is refused, by name.** A JRE runs this file and has no
// `ToolProvider.getSystemJavaCompiler()`. A build that wrote an empty jar would then be
// started, fail its handshake, and blame the reader; so it exits non-zero and says what
// the machine is missing (rules 49 and 89).
//
// **`--release 17`**, because 17 is the floor `plugin.json` declares. The reader is built on
// the machine that runs it, so this is about what it may use, not where it may go.
//
// **The jar is reproducible from its bytes.** Every entry carries one fixed time, and the
// entries are sorted, so one source tree on one JDK writes one jar (rule 66).

import java.io.IOException;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.util.ArrayList;
import java.util.List;
import java.util.jar.Attributes;
import java.util.jar.JarEntry;
import java.util.jar.JarOutputStream;
import java.util.jar.Manifest;
import java.util.stream.Stream;
import javax.tools.JavaCompiler;
import javax.tools.ToolProvider;

public class Build {
    private static final FileTime EPOCH = FileTime.fromMillis(315532800000L); // 1980-01-01

    public static void main(String[] args) throws IOException {
        if (args.length != 1) {
            System.err.println("usage: java Build.java <output jar>");
            System.exit(2);
        }
        Path output = Path.of(args[0]);
        JavaCompiler javac = ToolProvider.getSystemJavaCompiler();
        if (javac == null) {
            System.err.println(
                "this `java` (" + System.getProperty("java.home") + ") is a runtime with no "
                + "compiler: a JRE, not a JDK. The Java reader is javac and needs a JDK 17 "
                + "or newer on PATH; or run again with `--without java`.");
            System.exit(3);
        }
        List<String> sources = new ArrayList<>();
        try (Stream<Path> s = Files.walk(Path.of("src"))) {
            s.filter(p -> p.toString().endsWith(".java")).sorted()
                .forEach(p -> sources.add(p.toString()));
        }
        Path classes = Files.createTempDirectory("dunneflow-java-reader-");
        try {
            List<String> argv = new ArrayList<>(List.of(
                "--release", "17", "-encoding", "UTF-8", "-proc:none", "-nowarn",
                "-d", classes.toString()));
            argv.addAll(sources);
            int rc = javac.run(null, null, null, argv.toArray(new String[0]));
            if (rc != 0) {
                System.err.println("javac exited " + rc + " compiling the Java reader");
                System.exit(rc);
            }
            Manifest mf = new Manifest();
            mf.getMainAttributes().put(Attributes.Name.MANIFEST_VERSION, "1.0");
            mf.getMainAttributes().put(Attributes.Name.MAIN_CLASS, "dunneflow.reader.Main");
            List<Path> built = new ArrayList<>();
            try (Stream<Path> s = Files.walk(classes)) {
                s.filter(Files::isRegularFile).sorted().forEach(built::add);
            }
            try (OutputStream raw = Files.newOutputStream(output);
                 JarOutputStream jar = new JarOutputStream(raw)) {
                JarEntry m = new JarEntry("META-INF/MANIFEST.MF");
                m.setLastModifiedTime(EPOCH);
                jar.putNextEntry(m);
                mf.write(jar);
                jar.closeEntry();
                for (Path p : built) {
                    JarEntry e = new JarEntry(classes.relativize(p).toString().replace('\\', '/'));
                    e.setLastModifiedTime(EPOCH);
                    jar.putNextEntry(e);
                    jar.write(Files.readAllBytes(p));
                    jar.closeEntry();
                }
            }
        } finally {
            try (Stream<Path> s = Files.walk(classes)) {
                s.sorted((a, b) -> b.getNameCount() - a.getNameCount()).forEach(p -> {
                    try {
                        Files.deleteIfExists(p);
                    } catch (IOException ignored) {
                        // a scratch directory left behind is the OS's to clear
                    }
                });
            }
        }
    }
}
