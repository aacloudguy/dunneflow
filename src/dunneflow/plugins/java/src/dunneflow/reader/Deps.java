package dunneflow.reader;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

/**
 * The jars a tree depends on, where this machine already holds them. <b>Read, never
 * fetched</b> (design rule 14).
 *
 * <p>A call into a library javac cannot see is {@code untyped}. A call into one it can see
 * is {@code outside}, with the library's own qualified name as its far end. That is the
 * whole difference this class makes, and it is the frontier Tom asked to know as much about
 * as possible. Nothing here changes an edge inside the program.
 *
 * <p><b>What a tree declares is read from its build files</b>, the way the build tool
 * would read them, as far as a reader can without running it:
 * <ul>
 * <li><b>Maven</b>: each {@code pom.xml}'s effective model, meaning its parent chain
 *     (in the tree by {@code relativePath}, else from the cache), its properties, its
 *     {@code dependencyManagement} and the BOMs that imports. Then the dependencies,
 *     resolved through their own cached POMs, transitively, nearest first, honouring
 *     {@code optional}, scopes and exclusions, as Maven mediates them.</li>
 * <li><b>Gradle</b>: the coordinates written in a dependency configuration, as a string,
 *     a map or a version-catalog alias ({@code gradle/libs.versions.toml}). {@code $name} is
 *     filled from {@code gradle.properties} and from {@code ext}, {@code def} and
 *     {@code val} assignments. {@code platform(…)} is a BOM. <b>The Spring Boot plugin's
 *     version is a BOM too</b> ({@code spring-boot-dependencies}), because that is what the
 *     plugin applies and a versionless Boot dependency means nothing without it. That one
 *     is a rule written here, and it is stated as one.</li>
 * </ul>
 *
 * <p><b>Where it looks</b>: Maven's local repository ({@code ~/.m2/repository}, or the
 * {@code localRepository} of {@code ~/.m2/settings.xml}, or
 * {@code -Dmaven.repo.local} in {@code MAVEN_OPTS}) and Gradle's module cache
 * ({@code $GRADLE_USER_HOME}, else {@code ~/.gradle}). Those are the knobs the two tools
 * themselves read.
 *
 * <p><b>The residue, stated.</b> No build script runs, so a coordinate a Gradle script
 * computes, a {@code buildSrc} convention plugin or a version range is not resolved. Each
 * is listed as not found, never guessed. Profiles are not activated. A Gradle
 * {@code .module} file's variants are not read, only the POM published beside it.
 *
 * <p><b>Deterministic</b> (rule 66): the build files are read in path order, mediation is
 * breadth-first in declaration order, and the classpath is sorted.
 */
final class Deps {
    static final class Result {
        final List<Path> jars = new ArrayList<>();
        /** {@code g:a:v} of every jar put on the classpath. */
        final List<String> read = new ArrayList<>();
        /** {@code g:a:v}, or {@code g:a} where no version could be named, of every
         *  dependency declared or reached and not on this machine. */
        final List<String> absent = new ArrayList<>();
        final List<String> notes = new ArrayList<>();
    }

    private static final Set<String> SKIP_DIRS = Set.of(
        "build", "target", "out", ".gradle", ".idea", "node_modules", ".git", "generated");
    private static final Set<String> GRADLE_CONFIGS = Set.of(
        "implementation", "api", "compileOnly", "compileOnlyApi", "runtimeOnly", "compile",
        "provided", "runtime");

    private static final class Dep {
        String g = "";
        String a = "";
        String v = "";
        String scope = "compile";
        String type = "jar";
        boolean optional;
        final Set<String> exclusions = new HashSet<>();

        String ga() {
            return g + ":" + a;
        }
    }

    private static final class Model {
        String g = "";
        String a = "";
        String v = "";
        final Map<String, String> props = new HashMap<>();
        /** {@code g:a} -> version, own entries first, then imported BOMs, then the parent's. */
        final Map<String, String> managed = new LinkedHashMap<>();
        final List<Dep> deps = new ArrayList<>();
    }

    private final Path root;
    private final Path m2;
    private final Path gradle;
    private final Result result = new Result();
    private final Map<String, Model> models = new HashMap<>();
    private final Set<String> missingPoms = new TreeSet<>();
    private final DocumentBuilderFactory xml;

    private Deps(Path root) {
        this.root = root;
        this.m2 = mavenRepo();
        this.gradle = gradleCache();
        xml = DocumentBuilderFactory.newInstance();
        try {
            // A POM is somebody else's file: no DTD, no external entity, no network.
            xml.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            xml.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            xml.setXIncludeAware(false);
            xml.setExpandEntityReferences(false);
        } catch (javax.xml.parsers.ParserConfigurationException e) {
            throw new IllegalStateException("the JDK's XML parser cannot be made safe", e);
        }
    }

    static Result resolve(Path root) {
        Deps d = new Deps(root);
        try {
            d.run();
        } catch (IOException e) {
            d.result.notes.add("dependencies: the tree's build files could not be listed: " + e);
        }
        return d.result;
    }

    // --------------------------------------------------------------- where --- //

    private static Path home() {
        return Path.of(System.getProperty("user.home"));
    }

    private static Path mavenRepo() {
        String opts = System.getenv("MAVEN_OPTS");
        if (opts != null) {
            Matcher m = Pattern.compile("-Dmaven\\.repo\\.local=(\\S+)").matcher(opts);
            if (m.find()) {
                return Path.of(m.group(1));
            }
        }
        Path settings = home().resolve(".m2").resolve("settings.xml");
        if (Files.isRegularFile(settings)) {
            try {
                Matcher m = Pattern.compile("<localRepository>\\s*([^<]+?)\\s*</localRepository>")
                    .matcher(Files.readString(settings));
                if (m.find()) {
                    return Path.of(m.group(1).replace("${user.home}", home().toString()));
                }
            } catch (IOException ignored) {
                // An unreadable settings file is Maven's default repository.
            }
        }
        return home().resolve(".m2").resolve("repository");
    }

    private static Path gradleCache() {
        String gh = System.getenv("GRADLE_USER_HOME");
        Path base = gh != null && !gh.isBlank() ? Path.of(gh) : home().resolve(".gradle");
        return base.resolve("caches").resolve("modules-2").resolve("files-2.1");
    }

    /** The cached file of one artefact, or null: Maven's layout first, then Gradle's. */
    private Path cached(String g, String a, String v, String ext) {
        if (g.isEmpty() || a.isEmpty() || v.isEmpty()) {
            return null;
        }
        Path p = m2.resolve(g.replace('.', '/')).resolve(a).resolve(v).resolve(a + "-" + v + "." + ext);
        if (Files.isRegularFile(p)) {
            return p;
        }
        Path dir = gradle.resolve(g).resolve(a).resolve(v);
        if (Files.isDirectory(dir)) {
            try (Stream<Path> hashes = Files.list(dir)) {
                for (Path h : hashes.sorted().toList()) {
                    Path f = h.resolve(a + "-" + v + "." + ext);
                    if (Files.isRegularFile(f)) {
                        return f;
                    }
                }
            } catch (IOException ignored) {
                // An unreadable cache entry is an absent one.
            }
        }
        return null;
    }

    // ----------------------------------------------------------------- run --- //

    private void run() throws IOException {
        List<Path> poms = new ArrayList<>();
        List<Path> gradles = new ArrayList<>();
        List<Path> props = new ArrayList<>();
        List<Path> catalogs = new ArrayList<>();
        try (Stream<Path> s = Files.walk(root)) {
            s.filter(p -> {
                for (Path part : root.relativize(p)) {
                    if (SKIP_DIRS.contains(part.toString())) {
                        return false;
                    }
                }
                return Files.isRegularFile(p);
            }).sorted().forEach(p -> {
                String n = p.getFileName().toString();
                switch (n) {
                    case "pom.xml" -> poms.add(p);
                    case "build.gradle", "build.gradle.kts" -> gradles.add(p);
                    case "gradle.properties" -> props.add(p);
                    case "libs.versions.toml" -> catalogs.add(p);
                    default -> { }
                }
            });
        }
        if (poms.isEmpty() && gradles.isEmpty()) {
            return;
        }
        // The program's own modules, by coordinate: a dependency on one is source, not a jar.
        Set<String> own = new HashSet<>();
        List<Model> treeModels = new ArrayList<>();
        for (Path p : poms) {
            Model m = treeModel(p);
            if (m != null) {
                own.add(m.g + ":" + m.a);
                treeModels.add(m);
            }
        }
        List<Dep> direct = new ArrayList<>();
        Map<String, String> managed = new LinkedHashMap<>();
        for (Model m : treeModels) {
            m.managed.forEach(managed::putIfAbsent);
            for (Dep d : m.deps) {
                if (!d.scope.equals("test") && !own.contains(d.ga())) {
                    direct.add(d);
                }
            }
        }
        gradle(gradles, props, catalogs, direct, managed, own);
        mediate(direct, managed);
        if (!missingPoms.isEmpty()) {
            result.notes.add("dependencies: " + missingPoms.size() + " POMs are not on this "
                + "machine, so what they depend on was not followed");
        }
    }

    // ------------------------------------------------------------- maven --- //

    private Document parse(Path p) {
        try (InputStream in = Files.newInputStream(p)) {
            DocumentBuilder b = xml.newDocumentBuilder();
            b.setErrorHandler(null);
            return b.parse(in);
        } catch (Exception e) {
            result.notes.add("dependencies: " + p.getFileName() + " at " + p
                + " is not a POM this reader can read (" + e.getClass().getSimpleName() + ")");
            return null;
        }
    }

    private static Element child(Element e, String name) {
        if (e == null) {
            return null;
        }
        for (Node n = e.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element c && c.getTagName().equals(name)) {
                return c;
            }
        }
        return null;
    }

    private static List<Element> children(Element e, String name) {
        List<Element> out = new ArrayList<>();
        if (e == null) {
            return out;
        }
        for (Node n = e.getFirstChild(); n != null; n = n.getNextSibling()) {
            if (n instanceof Element c && c.getTagName().equals(name)) {
                out.add(c);
            }
        }
        return out;
    }

    private static String text(Element e, String name) {
        Element c = child(e, name);
        return c == null ? "" : c.getTextContent().strip();
    }

    /** A POM in the tree, with its parent found where {@code relativePath} says. */
    private Model treeModel(Path pom) {
        String key = "tree:" + pom;
        if (models.containsKey(key)) {
            return models.get(key);
        }
        models.put(key, null); // a parent cycle reads as no parent, not as recursion
        Document doc = parse(pom);
        Model m = doc == null ? null : model(doc.getDocumentElement(), pom.getParent());
        models.put(key, m);
        return m;
    }

    /** A POM from the cache, by coordinate. */
    private Model cachedModel(String g, String a, String v) {
        String key = g + ":" + a + ":" + v;
        if (models.containsKey(key)) {
            return models.get(key);
        }
        models.put(key, null);
        Path p = cached(g, a, v, "pom");
        if (p == null) {
            missingPoms.add(key);
            return null;
        }
        Document doc = parse(p);
        Model m = doc == null ? null : model(doc.getDocumentElement(), null);
        models.put(key, m);
        return m;
    }

    /** One POM's effective model: the parent's first, then its own over it. */
    private Model model(Element project, Path dir) {
        Model m = new Model();
        Element parent = child(project, "parent");
        Model pm = null;
        if (parent != null) {
            String pg = text(parent, "groupId");
            String pa = text(parent, "artifactId");
            String pv = text(parent, "version");
            String rel = text(parent, "relativePath");
            if (dir != null && child(parent, "relativePath") == null) {
                rel = "../pom.xml";
            }
            if (dir != null && !rel.isEmpty()) {
                Path pp = dir.resolve(rel).normalize();
                if (Files.isDirectory(pp)) {
                    pp = pp.resolve("pom.xml");
                }
                if (pp.startsWith(root) && Files.isRegularFile(pp)) {
                    pm = treeModel(pp);
                    if (pm != null && !(pm.g + ":" + pm.a).equals(pg + ":" + pa)) {
                        pm = null;
                    }
                }
            }
            if (pm == null) {
                pm = cachedModel(pg, pa, pv);
            }
            if (pm != null) {
                m.props.putAll(pm.props);
            }
            m.g = pg;
            m.v = pv;
            m.props.put("parent.version", pv);
            m.props.put("project.parent.version", pv);
            m.props.put("project.parent.groupId", pg);
        }
        if (!text(project, "groupId").isEmpty()) {
            m.g = text(project, "groupId");
        }
        m.a = text(project, "artifactId");
        if (!text(project, "version").isEmpty()) {
            m.v = text(project, "version");
        }
        Element props = child(project, "properties");
        if (props != null) {
            for (Node n = props.getFirstChild(); n != null; n = n.getNextSibling()) {
                if (n instanceof Element p) {
                    m.props.put(p.getTagName(), p.getTextContent().strip());
                }
            }
        }
        for (String k : List.of("project.version", "pom.version", "version")) {
            m.props.put(k, m.v);
        }
        for (String k : List.of("project.groupId", "pom.groupId", "groupId")) {
            m.props.put(k, m.g);
        }
        m.props.put("project.artifactId", m.a);
        m.g = fill(m.g, m.props);
        m.v = fill(m.v, m.props);
        // Own management first, then the BOMs it imports, then the parent's: nearest wins.
        Element dm = child(child(project, "dependencyManagement"), "dependencies");
        List<Dep> imports = new ArrayList<>();
        for (Element de : children(dm, "dependency")) {
            Dep d = dep(de, m.props);
            if (d.scope.equals("import") && d.type.equals("pom")) {
                imports.add(d);
            } else if (!d.v.isEmpty()) {
                m.managed.putIfAbsent(d.ga(), d.v);
            }
        }
        for (Dep d : imports) {
            Model bom = cachedModel(d.g, d.a, d.v);
            if (bom != null) {
                bom.managed.forEach(m.managed::putIfAbsent);
            } else {
                result.absent.add(d.g + ":" + d.a + ":" + d.v + " (a BOM)");
            }
        }
        if (pm != null) {
            pm.managed.forEach(m.managed::putIfAbsent);
            m.deps.addAll(pm.deps);
        }
        for (Element de : children(child(project, "dependencies"), "dependency")) {
            Dep d = dep(de, m.props);
            if (d.v.isEmpty()) {
                d.v = m.managed.getOrDefault(d.ga(), "");
            }
            m.deps.add(d);
        }
        return m;
    }

    private Dep dep(Element de, Map<String, String> props) {
        Dep d = new Dep();
        d.g = fill(text(de, "groupId"), props);
        d.a = fill(text(de, "artifactId"), props);
        d.v = fill(text(de, "version"), props);
        if (!text(de, "scope").isEmpty()) {
            d.scope = text(de, "scope");
        }
        if (!text(de, "type").isEmpty()) {
            d.type = text(de, "type");
        }
        d.optional = "true".equals(text(de, "optional"));
        for (Element ex : children(child(de, "exclusions"), "exclusion")) {
            d.exclusions.add(text(ex, "groupId") + ":" + text(ex, "artifactId"));
        }
        return d;
    }

    /** {@code ${name}} filled from a model's properties, as often as it nests. */
    private static String fill(String s, Map<String, String> props) {
        for (int i = 0; i < 10 && s.contains("${"); i++) {
            Matcher m = Pattern.compile("\\$\\{([^}]+)}").matcher(s);
            StringBuilder out = new StringBuilder();
            boolean changed = false;
            while (m.find()) {
                String v = props.get(m.group(1));
                if (v != null) {
                    changed = true;
                }
                m.appendReplacement(out, Matcher.quoteReplacement(v != null ? v : m.group()));
            }
            m.appendTail(out);
            s = out.toString();
            if (!changed) {
                break;
            }
        }
        return s;
    }

    // ------------------------------------------------------------ gradle --- //

    private static final Pattern ASSIGN = Pattern.compile(
        "(?m)^\\s*(?:def\\s+|val\\s+|var\\s+|ext\\.|project\\.ext\\.)?(\\w+)\\s*=\\s*[\"']([^\"'$]+)[\"']");
    private static final Pattern SET = Pattern.compile(
        "set\\(\\s*[\"'](\\w+)[\"']\\s*,\\s*[\"']([^\"'$]+)[\"']\\s*\\)");
    private static final Pattern STRING_DEP = Pattern.compile(
        "(?m)^\\s*(\\w+)\\s*\\(?\\s*(platform\\(|enforcedPlatform\\()?\\s*[\"']([^\"']+)[\"']");
    private static final Pattern MAP_DEP = Pattern.compile(
        "(?m)^\\s*(\\w+)\\s*\\(?\\s*group\\s*[:=]\\s*[\"']([^\"']+)[\"']\\s*,\\s*name\\s*[:=]\\s*"
        + "[\"']([^\"']+)[\"'](?:\\s*,\\s*version\\s*[:=]\\s*[\"']([^\"']+)[\"'])?");
    private static final Pattern CATALOG_DEP = Pattern.compile(
        "(?m)^\\s*(\\w+)\\s*\\(?\\s*(platform\\(|enforcedPlatform\\()?\\s*libs\\.([\\w.]+)");
    private static final Pattern BOOT_PLUGIN = Pattern.compile(
        "id\\s*\\(?\\s*[\"']org\\.springframework\\.boot[\"']\\s*\\)?\\s*version\\s*[\"']([^\"']+)[\"']");

    private void gradle(List<Path> gradles, List<Path> propFiles, List<Path> catalogs,
                        List<Dep> direct, Map<String, String> managed, Set<String> own)
            throws IOException {
        if (gradles.isEmpty()) {
            return;
        }
        Map<String, String> vars = new HashMap<>();
        for (Path p : propFiles) {
            for (String line : Files.readAllLines(p)) {
                int eq = line.indexOf('=');
                if (eq > 0 && !line.strip().startsWith("#")) {
                    vars.putIfAbsent(line.substring(0, eq).strip(), line.substring(eq + 1).strip());
                }
            }
        }
        Map<String, String> texts = new LinkedHashMap<>();
        for (Path p : gradles) {
            String t = Files.readString(p);
            texts.put(p.toString(), t);
            for (Pattern pat : List.of(ASSIGN, SET)) {
                Matcher m = pat.matcher(t);
                while (m.find()) {
                    vars.putIfAbsent(m.group(1), m.group(2));
                }
            }
        }
        Map<String, String[]> catalog = new HashMap<>();
        for (Path c : catalogs) {
            readCatalog(c, catalog);
        }
        List<Dep> boms = new ArrayList<>();
        for (Map.Entry<String, String> e : texts.entrySet()) {
            String t = e.getValue();
            Matcher boot = BOOT_PLUGIN.matcher(t);
            if (boot.find()) {
                Dep d = new Dep();
                d.g = "org.springframework.boot";
                d.a = "spring-boot-dependencies";
                d.v = boot.group(1);
                boms.add(d);
            }
            Matcher m = STRING_DEP.matcher(t);
            while (m.find()) {
                if (!GRADLE_CONFIGS.contains(m.group(1))) {
                    continue;
                }
                String[] parts = gradleFill(m.group(3), vars).split(":");
                if (parts.length < 2) {
                    continue;
                }
                Dep d = new Dep();
                d.g = parts[0];
                d.a = parts[1];
                d.v = parts.length > 2 ? parts[2] : "";
                d.scope = m.group(1).startsWith("compileOnly") || m.group(1).equals("provided")
                    ? "provided" : "compile";
                (m.group(2) != null ? boms : direct).add(d);
            }
            Matcher mm = MAP_DEP.matcher(t);
            while (mm.find()) {
                if (!GRADLE_CONFIGS.contains(mm.group(1))) {
                    continue;
                }
                Dep d = new Dep();
                d.g = gradleFill(mm.group(2), vars);
                d.a = gradleFill(mm.group(3), vars);
                d.v = mm.group(4) == null ? "" : gradleFill(mm.group(4), vars);
                direct.add(d);
            }
            Matcher cm = CATALOG_DEP.matcher(t);
            while (cm.find()) {
                if (!GRADLE_CONFIGS.contains(cm.group(1))) {
                    continue;
                }
                String alias = cm.group(3).replace('.', '-');
                String[] gav = catalog.get(alias);
                if (gav == null) {
                    result.absent.add("libs." + cm.group(3) + " (not in the version catalog)");
                    continue;
                }
                Dep d = new Dep();
                d.g = gav[0];
                d.a = gav[1];
                d.v = gav[2];
                (cm.group(2) != null ? boms : direct).add(d);
            }
        }
        direct.removeIf(d -> own.contains(d.ga()));
        for (Dep b : boms) {
            Model bom = cachedModel(b.g, b.a, b.v);
            if (bom == null) {
                result.absent.add(b.g + ":" + b.a + ":" + b.v + " (a BOM)");
                continue;
            }
            managed.putIfAbsent(b.ga(), b.v);
            bom.managed.forEach(managed::putIfAbsent);
        }
    }

    /** {@code $name} and {@code ${name}}, from what the build files assign. */
    private static String gradleFill(String s, Map<String, String> vars) {
        Matcher m = Pattern.compile("\\$\\{?([\\w.]+?)}?(?=[^\\w.]|$)").matcher(s);
        StringBuilder out = new StringBuilder();
        while (m.find()) {
            String key = m.group(1);
            String v = vars.get(key);
            if (v == null && key.contains(".")) {
                v = vars.get(key.substring(key.lastIndexOf('.') + 1));
            }
            m.appendReplacement(out, Matcher.quoteReplacement(v != null ? v : m.group()));
        }
        m.appendTail(out);
        return out.toString();
    }

    /** {@code [versions]} and {@code [libraries]} of a version catalog, aliases in their
     *  dashed form ({@code libs.netty.buffer} is {@code netty-buffer}). */
    private static void readCatalog(Path p, Map<String, String[]> out) throws IOException {
        Map<String, String> versions = new HashMap<>();
        String section = "";
        List<String[]> libs = new ArrayList<>();
        for (String raw : Files.readAllLines(p)) {
            String line = raw.strip();
            if (line.startsWith("#") || line.isEmpty()) {
                continue;
            }
            if (line.startsWith("[")) {
                section = line.replaceAll("[\\[\\]\\s]", "");
                continue;
            }
            int eq = line.indexOf('=');
            if (eq < 0) {
                continue;
            }
            String key = line.substring(0, eq).strip().replace('_', '-').replace('.', '-');
            String val = line.substring(eq + 1).strip();
            if (section.equals("versions")) {
                versions.put(key, unquote(val));
            } else if (section.equals("libraries")) {
                libs.add(new String[] {key, val});
            }
        }
        for (String[] lib : libs) {
            String val = lib[1];
            String g;
            String a;
            String v = "";
            if (val.startsWith("\"")) {
                String[] parts = unquote(val).split(":");
                if (parts.length < 2) {
                    continue;
                }
                g = parts[0];
                a = parts[1];
                v = parts.length > 2 ? parts[2] : "";
            } else {
                String module = field(val, "module");
                if (!module.isEmpty()) {
                    String[] parts = module.split(":");
                    g = parts[0];
                    a = parts.length > 1 ? parts[1] : "";
                } else {
                    g = field(val, "group");
                    a = field(val, "name");
                }
                String ref = field(val, "version.ref");
                v = !ref.isEmpty() ? versions.getOrDefault(ref.replace('_', '-').replace('.', '-'), "")
                    : field(val, "version");
            }
            out.put(lib[0], new String[] {g, a, v});
        }
    }

    private static String field(String inline, String name) {
        Matcher m = Pattern.compile(Pattern.quote(name) + "\\s*=\\s*\"([^\"]*)\"").matcher(inline);
        return m.find() ? m.group(1) : "";
    }

    private static String unquote(String s) {
        s = s.strip();
        return s.length() >= 2 && s.startsWith("\"") && s.endsWith("\"")
            ? s.substring(1, s.length() - 1) : s;
    }

    // ---------------------------------------------------------- mediation --- //

    /** Maven's rule, breadth first: the nearest declaration of a {@code g:a} wins, and the
     *  root's management sets the version of anything it names, however deep. */
    private void mediate(List<Dep> direct, Map<String, String> managed) {
        record Item(Dep dep, Set<String> excluded) {}
        Deque<Item> queue = new ArrayDeque<>();
        for (Dep d : direct) {
            queue.add(new Item(d, d.exclusions));
        }
        Map<String, String> chosen = new LinkedHashMap<>();
        Set<String> absent = new TreeSet<>();
        while (!queue.isEmpty()) {
            Item it = queue.removeFirst();
            Dep d = it.dep();
            if (chosen.containsKey(d.ga()) || !(d.type.equals("jar") || d.type.equals("bundle"))) {
                continue;
            }
            String v = managed.getOrDefault(d.ga(), d.v);
            if (v.isEmpty() || v.contains("${") || v.contains("$") || v.startsWith("[")
                || v.startsWith("(")) {
                absent.add(d.ga() + (v.isEmpty() ? " (no version named)" : " (version " + v + ")"));
                chosen.put(d.ga(), "");
                continue;
            }
            chosen.put(d.ga(), v);
            Model m = cachedModel(d.g, d.a, v);
            if (m == null) {
                continue;
            }
            for (Dep t : m.deps) {
                // Transitively, only what a consumer gets: compile and runtime, not optional.
                if (t.optional || !(t.scope.equals("compile") || t.scope.equals("runtime"))) {
                    continue;
                }
                if (it.excluded().contains(t.ga()) || it.excluded().contains(t.g + ":*")
                    || it.excluded().contains("*:*")) {
                    continue;
                }
                Set<String> ex = new HashSet<>(it.excluded());
                ex.addAll(t.exclusions);
                if (t.v.isEmpty()) {
                    t.v = m.managed.getOrDefault(t.ga(), "");
                }
                queue.addLast(new Item(t, ex));
            }
        }
        List<String> keys = new ArrayList<>(chosen.keySet());
        keys.sort(null);
        for (String ga : keys) {
            String v = chosen.get(ga);
            if (v.isEmpty()) {
                continue;
            }
            String[] p = ga.split(":", 2);
            Path jar = cached(p[0], p[1], v, "jar");
            if (jar != null) {
                result.jars.add(jar);
                result.read.add(ga + ":" + v);
            } else if (cached(p[0], p[1], v, "pom") == null) {
                absent.add(ga + ":" + v);
            }
            // A POM with no jar beside it is a POM-only artefact (a starter, a BOM): nothing
            // to read, and nothing missing.
        }
        result.absent.addAll(absent);
    }
}
