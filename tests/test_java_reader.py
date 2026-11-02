"""The Java reader: generated where it can be, pinned where it cannot, and asked through the host.

The three kinds of claim `test_rust_reader.py` makes, and only the last two need a JDK:

- **What is generated is current.** `Facts.java` and the fingerprint list are regenerated
  from `schema.py` and from the tree, and compared.
- **The second implementations agree with the first.** BLAKE2b, every id function and the
  decoding are written again in Java, and the reader's own `--self-test` mode holds them to
  the vectors the host wrote (`tests/fixtures/ids/vectors.json`).
- **The reader answers the host as the host asks.** Built by the host's own `build` seam,
  started through `run`, handshaken, opened and read through `OutOfProcessPlugin` (rule 48's
  shape).

Skipped for two named reasons only, each said in the skip: this build has no Java plugin,
or this machine has no `java` the plugin's toolchain probe accepts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.ingest.contract import ToolchainMissing
from dunneflow.ingest.outofprocess import built_reader, probe_toolchain
from dunneflow.schema import hash_source

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gen_facts_java  # noqa: E402

PLUGIN = ingest.PLUGINS.get("java")
HERE = PLUGIN.manifest.root if PLUGIN is not None else None
VECTORS = ROOT / "tests" / "fixtures" / "ids" / "vectors.json"


def _jdk_missing() -> str:
    if PLUGIN is None:
        return "this build ships no Java reader"
    try:
        probe_toolchain(PLUGIN.manifest)
    except ToolchainMissing as exc:
        return f"no JDK this reader accepts on this machine: {exc}"
    return ""


_WHY = _jdk_missing()
needs_plugin = pytest.mark.skipif(PLUGIN is None, reason="this build ships no Java reader")
needs_jdk = pytest.mark.skipif(bool(_WHY), reason=_WHY or "-")


# ---------------------------------------------------------- generated, no JDK --- #

@needs_plugin
def test_the_reader_s_types_are_the_schema_s():
    assert HERE is not None
    facts = HERE / "src" / "dunneflow" / "reader" / "Facts.java"
    assert facts.read_text(encoding="utf-8") == gen_facts_java.generate(), (
        "Facts.java is not what schema.py generates: "
        "uv run python tools/gen_facts_java.py --write")


@needs_plugin
def test_every_file_the_reader_is_built_from_is_in_the_fingerprint():
    """Rule 12. Named, never globbed — so this is the glob, and it is what catches a file
    added to `src/` without `--write`."""
    assert PLUGIN is not None
    named = list(PLUGIN.manifest.fingerprint)
    assert named == gen_facts_java.fingerprint(), (
        "plugin.json's fingerprint is not the files on disk: "
        "uv run python tools/gen_facts_java.py --write")
    assert {"plugin.json", "Build.java"} <= set(named)
    assert all(n.endswith(".java") or n == "plugin.json" for n in named), (
        "a built class or a jar is an output, not a source")


@needs_plugin
def test_the_build_is_the_jdk_alone_and_the_jar_is_started_by_the_toolchain():
    """No Maven and no Gradle: `java Build.java` compiles with the system compiler and
    writes the jar itself, so building the reader is never egress (design rule 14)."""
    assert PLUGIN is not None
    m = PLUGIN.manifest
    assert m.build == ("java", "Build.java", "{output}")
    assert m.toolchain is not None and m.toolchain.command == "java"
    assert "{reader}" in m.run and "-jar" in m.run
    assert m.toolchain.min_version == "17.0.0"


@needs_plugin
def test_the_judgements_are_declared_and_not_defaulted():
    """A dropped future runs, as Kotlin's does; Java overloads; it has no free functions, so
    no builtins (rule 98's shape: each is a claim about the language, made by it)."""
    from dunneflow.detectors import load_rules

    rules = load_rules("java")
    assert rules.unawaited_async == "runs"
    assert rules.redefinition == "overloads"
    assert list(rules.builtins) == []


@pytest.mark.parametrize("said, ok", [
    ('openjdk version "21.0.5" 2024-10-15 LTS', True),
    ('openjdk version "17.0.12" 2024-07-16', True),
    ('openjdk version "25.0.1" 2025-10-21 LTS', True),
    ('java version "1.8.0_402"', False),
    ("The operation couldn't be completed. Unable to locate a Java Runtime.", False),
])
def test_the_version_probe_reads_what_each_java_says(said, ok):
    """`java -version` writes to stderr, and macOS's `/usr/bin/java` stub answers with no
    version at all, which is refused rather than read as new enough (rule 49)."""
    from dunneflow.ingest.outofprocess import _at_least

    assert _at_least(said, "17.0.0") is ok


# ------------------------------------------------------------- with a JDK ---- #

@pytest.fixture(scope="module")
def jar() -> Path:
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    return built_reader(PLUGIN.manifest)


def _self_test(jar: Path, vectors: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["java", "-jar", str(jar), "--self-test", str(vectors)],
        capture_output=True, text=True, timeout=120, check=False,
    )


@needs_jdk
def test_the_second_implementations_agree_with_the_first(jar):
    out = _self_test(jar, VECTORS)
    assert out.returncode == 0, out.stderr[-3000:]
    assert " 0 disagreeing" in out.stderr


@needs_jdk
def test_a_tampered_vector_is_seen_to_fail(jar, tmp_path):
    """Rule 59: a harness whose every check passes has not shown it can fail."""
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    data["definition_id"][0][3] = "0" * 16
    data["decode"][2][1] = "A"
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    out = _self_test(jar, bad)
    assert out.returncode == 2, out.stderr[-3000:]
    assert "DISAGREES definition_id" in out.stderr and "DISAGREES decode" in out.stderr


@pytest.fixture(scope="module")
def read(tmp_path_factory):
    """A small tree, read in one session through the host: CRLF and mixed bad bytes in
    one file, a parse error in another."""
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    plugin = PLUGIN
    root = tmp_path_factory.mktemp("javatree")
    (root / "Main.java").write_bytes(
        b"class Main {\r\n  public static void main(String[] a) {}\r\n}\r\n"
        b"// \xe2\x82A \xff \xed\xa0\x80 \xf0\x9f\x98\n")
    (root / "Broken.java").write_bytes(b"class Broken {\n  void f( {\n}\n")
    (root / "src" / "main" / "java" / "a").mkdir(parents=True)
    (root / "src" / "main" / "java" / "a" / "B.java").write_bytes(
        b"package a;\npublic class B { void run() {} }\n")
    files = sorted(root.rglob("*.java"))
    plugin.probe()
    plugin.open(root, files)
    try:
        facts = {ff.path: ff for ff in plugin.extract(files, root)}
        edges = list(plugin.edges())
    finally:
        plugin.close()
    return root, facts, edges


def test_the_handshake_agrees_with_the_manifest(read):
    """`open` succeeding is the proof: the handshake refuses the language on any
    disagreement about lang, version, protocol, schema or capability (rule 30)."""
    _, facts, _ = read
    assert facts


def test_a_crlf_file_with_bad_bytes_hashes_as_the_host_hashes_it(read):
    root, facts, _ = read
    ff = facts["Main.java"]
    assert ff.errors == []
    assert ff.content_hash == hash_source(
        (root / "Main.java").read_text(encoding="utf-8", errors="replace"))


def test_a_file_that_will_not_parse_is_facts_with_errors(read):
    _, facts, _ = read
    ff = facts["Broken.java"]
    assert ff.errors and ff.errors[0].startswith("2:"), ff.errors
    assert ff.content_hash, "a parse error is still a file whose bytes are known, so cached"


def test_paths_and_modules_are_spelled_as_every_reader_spells_them(read):
    _, facts, _ = read
    assert set(facts) == {"Main.java", "Broken.java", "src/main/java/a/B.java"}
    assert facts["src/main/java/a/B.java"].module == "src.main.java.a.B"
    assert all(ff.lang == "java" for ff in facts.values())



# ------------------------------------------------------------- facts ------------ #

_OWNER = '''package org.x;

import java.nio.file.Files;
import java.util.*;

/** The owners' controller. */
@RestController
@RequestMapping("/owners")
public class Owner extends Base implements Runnable {
    static final int LIMIT = 10;
    private final List<String> names = new ArrayList<>();

    enum Colour {
        RED(1), GREEN(2) { void m() { tick(); } };
        Colour(int n) {}
        void m() {}
        static void tick() {}
    }

    record Pet(String name, int age) {}

    interface Repo { List<String> all(); }

    Owner(int n) { super(n); }

    /** Shows one owner. */
    @Override
    @GetMapping("/{id}")
    public String show(String id) throws Exception {
        // look it up
        String s = Files.readString(java.nio.file.Path.of(id));
        for (String n : names) {
            if (n.isEmpty()) {
                continue;
            }
            System.out.println(n);
        }
        names.forEach(n -> log(n));
        new Thread(new Runnable() { public void run() { tick(); } }).start();
        return List.<String>of("x").get(0);
    }

    void helper() {}
    void helper(int x) {}
    void log(String s) {}
    void tick() {}
    public void run() {}

    public static void main(String... args) { new Owner(1).show("abc"); }
}
'''


@pytest.fixture(scope="module")
def owner(tmp_path_factory):
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    root = tmp_path_factory.mktemp("owner")
    f = root / "src" / "main" / "java" / "org" / "x" / "Owner.java"
    f.parent.mkdir(parents=True)
    f.write_text(_OWNER, encoding="utf-8")
    PLUGIN.probe()
    PLUGIN.open(root, [f])
    try:
        (ff,) = list(PLUGIN.extract([f], root))
    finally:
        PLUGIN.close()
    assert ff.errors == [], ff.errors
    return ff


def test_a_qualname_is_the_package_s_and_the_module_is_the_file_s(owner):
    """Identity, decided first (LANGUAGES.md): the package is how a Java author addresses a
    method, as Kotlin's is; the file is in the id and the module, as every reader's is."""
    quals = [r.qualname for r in owner.routines]
    assert owner.module == "src.main.java.org.x.Owner"
    assert "org.x.Owner.show" in quals
    assert "org.x.Owner.Owner" in quals, "a constructor is spelt with its class's name"
    assert "org.x.Owner.show.$1.run" in quals, "an anonymous class carries its method (rule 10)"
    assert "org.x.Owner.Colour.GREEN.m" in quals, "an enum constant's body is named by it"
    helpers = [r for r in owner.routines if r.qualname == "org.x.Owner.helper"]
    assert len(helpers) == 2 and helpers[0].id != helpers[1].id, "an overload is a routine"
    assert all(r.file == "src/main/java/org/x/Owner.java" for r in owner.routines)


def test_a_declaration_with_no_body_is_a_field_of_its_shape_and_not_a_routine(owner):
    assert not any(r.name == "all" for r in owner.routines)
    repo = next(s for s in owner.structures if s.name == "Repo")
    assert repo.kind.value == "INTERFACE"
    assert [f.name for f in repo.fields] == ["all"]


def test_a_return_type_is_always_declared(owner):
    """Go's `MISSING_RETURN_TYPE` lesson: `None` means undeclared, and no Java method is."""
    by = {r.qualname: r for r in owner.routines if r.name != "<module>"}
    assert by["org.x.Owner.Owner"].returns == ""
    assert by["org.x.Owner.show"].returns == "String"
    assert by["org.x.Owner.tick"].returns == "void"


def test_the_first_line_is_the_declaration_and_not_its_annotations(owner):
    show = next(r for r in owner.routines if r.qualname == "org.x.Owner.show")
    assert _OWNER.splitlines()[show.line_start - 1].strip().startswith("public String show")
    assert show.decorators == ["Override", "GetMapping"]
    assert show.docstring == "Shows one owner."
    assert [c.text for c in show.comments] == ["look it up"]


def test_an_enum_constant_is_a_member_and_never_a_construction(owner):
    """javac writes `RED(1)` as a `new` it made itself, which nobody wrote (rule 1)."""
    colour = next(s for s in owner.structures if s.name == "Colour")
    assert colour.kind.value == "ENUM"
    assert [f.name for f in colour.fields] == ["RED", "GREEN"]
    assert not any(c.callee_expr == "Colour" for c in owner.calls)
    assert {c.name for c in owner.constants} >= {"RED", "GREEN", "LIMIT"}


def test_ways_in_main_and_a_route_named_with_its_class_s_prefix(owner):
    kinds = {(e.kind.value, e.name) for e in owner.entrypoints}
    assert ("MAIN", "main") in kinds
    assert ("HTTP_ROUTE", "GetMapping /owners/{id}") in kinds


def test_calls_follow_the_dotted_contract_and_boundaries_are_matched(owner):
    calls = {c.callee_expr for c in owner.calls}
    assert {"Files.readString", "java.nio.file.Path.of", "System.out.println",
            "names.forEach", "log", "Thread.start", "List.of.get", "Owner.show"} <= calls
    news = {c.callee_expr for c in owner.calls if c.is_construction}
    assert {"ArrayList", "Thread", "Runnable", "Owner"} <= news
    hits = {(b.kind.value, b.evidence) for b in owner.boundaries}
    assert ("FILE", "Files.readString") in hits and ("STDIO", "System.out.println") in hits
    at = {c.callee_expr for c in owner.calls if c.at_boundary}
    assert at == {"Files.readString", "System.out.println"}, "rule 2, and only those"


def test_a_field_initialiser_belongs_to_the_module_scope(owner):
    """Rule 18: `new ArrayList<>()` on a field runs at construction, in no method written."""
    (alloc,) = [c for c in owner.calls if c.callee_expr == "ArrayList"]
    scope = next(r for r in owner.routines if r.name == "<module>")
    assert alloc.caller_id == scope.id


def test_control_where_something_can_move(owner):
    spans = {(p.kind.value, p.word, p.header, p.exits) for p in owner.control}
    assert ("LOOP", "for", "String n : names", "") in spans
    assert ("GUARD", "if", "n.isEmpty()", "continue") in spans
    assert ("COMPREHENSION", "forEach", "names.forEach", "") in spans


# ------------------------------------------------------------- edges ------------ #

EDGES = ROOT / "tests" / "fixtures" / "java_edges"


@pytest.fixture(scope="module")
def answers():
    """Each call in the edge fixture, by `file:line callee`, with what the reader said."""
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    files = sorted(EDGES.rglob("*.java"))
    PLUGIN.probe()
    PLUGIN.open(EDGES, files)
    try:
        facts = list(PLUGIN.extract(files, EDGES))
        edges = list(PLUGIN.edges())
        tally = (PLUGIN.edges_outside, PLUGIN.edges_unknown)
    finally:
        PLUGIN.close()
    sites = {c.site_id: f"{Path(ff.path).name}:{c.line} {c.callee_expr}"
             for ff in facts for c in ff.calls}
    out = {sites[e.site_id]: e for e in edges}
    assert len(out) == len(edges), "two edges for one site"
    return out, tally


def _to(e) -> str:
    return f"{Path(e.file).name}:{e.line} {e.name}"


def test_a_call_javac_resolved_to_one_body_is_an_edge_to_that_body(answers):
    a, _ = answers
    assert _to(a["Main.java:27 fact"]) == "Main.java:26 fact", "recursion is an edge to itself"
    assert _to(a["Main.java:36 Square.unit"]) == "Square.java:19 unit"
    assert _to(a["Main.java:39 Helper.help"]) == "Helper.java:4 help", "across files"
    assert _to(a["Main.java:54 tick"]) == "Base.java:10 tick", "across build modules"
    assert a["Main.java:36 Square.unit"].how == "non-virtual"
    assert a["Main.java:38 sq.area"].how == "unoverridden"


def test_each_overload_is_its_own_target(answers):
    a, _ = answers
    assert _to(a["Main.java:40 fmt"]) == "Main.java:30 fmt"
    assert _to(a["Main.java:41 fmt"]) == "Main.java:32 fmt"


def test_super_names_a_body_and_final_admits_no_other(answers):
    a, _ = answers
    assert _to(a["Main.java:23 super.greet"]) == "Base.java:6 greet"
    assert a["Main.java:23 super.greet"].how == "non-virtual"
    assert _to(a["Main.java:37 sq.label"]) == "Square.java:15 label"


def test_dispatch_over_several_bodies_is_dynamic_and_never_guessed(answers):
    """Tom's rule (2026-11-01): an interface or abstract method, or one the tree overrides,
    is `dynamic` with the bodies that can answer it counted (rule 1)."""
    a, _ = answers
    area = a["Main.java:35 s.area"]
    assert (area.file, area.reason, area.candidates) == ("", "dynamic", 2)
    assert area.frontier == "org.lib.Shape.area"
    step = a["Base.java:11 step"]
    assert (step.file, step.reason, step.candidates) == ("", "dynamic", 1)
    run = a["Main.java:51 r.run"]
    assert (run.reason, run.candidates, run.frontier) == ("dynamic", 1, "java.lang.Runnable.run"), (
        "a JDK interface the tree implements reaches the tree's anonymous class")


def test_the_frontier_says_where_a_call_stops_and_why(answers):
    a, (outside, unknown) = answers
    add = a["Main.java:43 xs.add"]
    assert (add.reason, add.frontier, add.how) == ("outside", "java.util.List.add", "symbol")
    go = a["Main.java:52 m.go"]
    assert (go.reason, go.frontier) == ("untyped", "m.go"), "a missing class is said, not guessed"
    find = a["Main.java:53 repo.find"]
    assert (find.reason, find.how) == ("outside", "unimplemented")
    assert outside == sum(1 for e in a.values() if e.reason == "outside")
    assert unknown == sum(1 for e in a.values() if not e.file and e.reason != "outside")


def test_a_constructor_nobody_wrote_points_at_the_class_it_builds(answers):
    a, _ = answers
    helper = a["Main.java:39 Helper"]
    assert helper.constructs == "org.app.Helper" and _to(helper) == "Helper.java:3 Helper"
    assert _to(a["Main.java:58 Main"]) == "Main.java:14 Main", "a written one is a routine"


def test_a_call_at_a_boundary_is_never_also_an_edge(answers):
    """Rule 2: `System.out.println` in `Base.greet` is a touch, and sends no edge."""
    a, _ = answers
    assert not any("println" in k for k in a)


def test_every_supplied_edge_lands_on_its_routine_s_first_line(tmp_path):
    """Through the host: the line the reader names is the line the routine was stored at,
    so nothing falls back to a span and nothing lands on a routine of another name."""
    if _WHY:
        pytest.skip(_WHY)
    from dunneflow.resolve import supplied
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    store = Store(tmp_path / "g.db")
    analyze_tree(EDGES, store)
    resolve_calls(store)
    rep = supplied.REPORTS["java"]
    store.close()
    assert rep.supplied == rep.exact > 0 and rep.constructions == 1
    assert (rep.by_span, rep.name_mismatch, rep.no_routine) == (0, 0, 0)


def test_what_javac_said_about_the_edge_pass_reaches_the_summary(tmp_path):
    """Rule 38, through the walk: javac's account of why calls are `untyped` used to go to
    stderr only, so the Android SDK's 900,135 call sites read as "could not resolve" with
    the reason said to nobody."""
    if _WHY:
        pytest.skip(_WHY)
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    src = tmp_path / "t" / "org" / "x"
    src.mkdir(parents=True)
    (src / "A.java").write_text(
        "package org.x;\nimport org.nowhere.Gone;\n"
        "class A { void f() { new Gone().go(); } }\n", encoding="utf-8")
    store = Store(tmp_path / "g.db")
    stats = analyze_tree(tmp_path / "t", store)
    store.close()
    said = [n for n in stats.reader_notes if n.startswith("java edges:")]
    assert said and "javac reported" in said[0]
    assert any("org.nowhere" in n for n in stats.reader_notes)


# ------------------------------------------------- dependencies, never fetched --- #

def _pom(g: str, a: str, v: str, body: str = "", parent: str = "") -> str:
    return (f"<project><modelVersion>4.0.0</modelVersion>{parent}<groupId>{g}</groupId>"
            f"<artifactId>{a}</artifactId><version>{v}</version>{body}</project>")


def _dep(g: str, a: str, v: str = "", extra: str = "") -> str:
    ver = f"<version>{v}</version>" if v else ""
    return (f"<dependency><groupId>{g}</groupId><artifactId>{a}</artifactId>{ver}{extra}"
            "</dependency>")


def _jar(tmp: Path, cls: str) -> bytes:
    """A real jar holding `org.acme.<cls>` with a method `hello()`, compiled by this JDK."""
    import zipfile
    src = tmp / "jarsrc" / cls
    (src / "org" / "acme").mkdir(parents=True)
    (src / "org" / "acme" / f"{cls}.java").write_text(
        f"package org.acme;\npublic class {cls} {{ public void hello() {{}} }}\n", encoding="utf-8")
    out = tmp / "jarout" / cls
    argv = ["javac", "-d", str(out), str(src / "org" / "acme" / f"{cls}.java")]
    subprocess.run(argv, check=True, capture_output=True)  # noqa: S603
    jar = tmp / f"{cls}.jar"
    with zipfile.ZipFile(jar, "w") as z:
        z.write(out / "org" / "acme" / f"{cls}.class", f"org/acme/{cls}.class")
    return jar.read_bytes()


def _m2(repo: Path, g: str, a: str, v: str, pom: str, jar: bytes | None = None) -> None:
    d = repo / g.replace(".", "/") / a / v
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{a}-{v}.pom").write_text(pom, encoding="utf-8")
    if jar is not None:
        (d / f"{a}-{v}.jar").write_bytes(jar)


@pytest.fixture(scope="module")
def deps_tree(tmp_path_factory):
    """A Maven tree and a Gradle tree over one fake repository, and their edges."""
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    tmp = tmp_path_factory.mktemp("deps")
    repo = tmp / "m2"
    g = "org.acme"
    _m2(repo, g, "acme-parent", "1", _pom(g, "acme-parent", "1",
        "<packaging>pom</packaging><properties><lib.version>2.0</lib.version></properties>"
        "<dependencyManagement><dependencies>"
        + _dep(g, "acme-bom", "1", "<type>pom</type><scope>import</scope>")
        + "</dependencies></dependencyManagement>"))
    _m2(repo, g, "acme-bom", "1", _pom(g, "acme-bom", "1",
        "<packaging>pom</packaging><dependencyManagement><dependencies>"
        + _dep(g, "extra", "3.0") + "</dependencies></dependencyManagement>"))
    _m2(repo, g, "lib", "2.0", _pom(g, "lib", "2.0", "<dependencies>"
        + _dep(g, "trans", "1.0") + _dep(g, "opt", "1.0", "<optional>true</optional>")
        + _dep(g, "gone", "1.0") + _dep(g, "tested", "1.0", "<scope>test</scope>")
        + "</dependencies>"), _jar(tmp, "Lib"))
    _m2(repo, g, "extra", "3.0", _pom(g, "extra", "3.0"), _jar(tmp, "Extra"))
    _m2(repo, g, "trans", "1.0", _pom(g, "trans", "1.0"), _jar(tmp, "Trans"))
    for never in ("opt", "gone", "tested"):
        _m2(repo, g, never, "1.0", _pom(g, never, "1.0"), _jar(tmp, never.capitalize()))

    maven = tmp / "maven"
    (maven / "src" / "main" / "java" / "app").mkdir(parents=True)
    (maven / "pom.xml").write_text(_pom("app", "app", "1", "<dependencies>"
        + _dep(g, "lib", "${lib.version}",
               "<exclusions><exclusion><groupId>org.acme</groupId>"
               "<artifactId>gone</artifactId></exclusion></exclusions>")
        + _dep(g, "extra") + _dep(g, "missing", "9") + "</dependencies>",
        parent=f"<parent><groupId>{g}</groupId><artifactId>acme-parent</artifactId>"
               "<version>1</version></parent>"), encoding="utf-8")
    (maven / "src" / "main" / "java" / "app" / "App.java").write_text(
        "package app;\n\nimport org.acme.*;\n\nclass App {\n"
        "    void f(Lib l, Extra e, Trans t, Gone g) {\n"
        "        l.hello();\n        e.hello();\n        t.hello();\n        g.hello();\n"
        "    }\n}\n", encoding="utf-8")

    gradle = tmp / "gradle"
    (gradle / "gradle").mkdir(parents=True)
    (gradle / "src" / "main" / "java" / "app").mkdir(parents=True)
    (gradle / "build.gradle").write_text(
        "ext {\n    libVersion = \"2.0\"\n}\n\ndependencies {\n"
        "    implementation \"org.acme:lib:$libVersion\"\n"
        "    implementation libs.acme.extra\n"
        "    testImplementation \"org.acme:tested:1.0\"\n}\n", encoding="utf-8")
    (gradle / "gradle" / "libs.versions.toml").write_text(
        '[versions]\nextra = "3.0"\n\n[libraries]\n'
        'acme-extra = { module = "org.acme:extra", version.ref = "extra" }\n', encoding="utf-8")
    (gradle / "src" / "main" / "java" / "app" / "App.java").write_text(
        (maven / "src" / "main" / "java" / "app" / "App.java").read_text(encoding="utf-8"),
        encoding="utf-8")

    old = os.environ.get("MAVEN_OPTS")
    os.environ["MAVEN_OPTS"] = f"-Dmaven.repo.local={repo}"
    out = {}
    try:
        for name, root in (("maven", maven), ("gradle", gradle)):
            files = sorted(root.rglob("*.java"))
            PLUGIN.probe()
            PLUGIN.open(root, files)
            try:
                facts = list(PLUGIN.extract(files, root))
                edges = list(PLUGIN.edges())
                read = list(PLUGIN.edges_read_beyond)
                absent = list(PLUGIN.edges_not_present)
            finally:
                PLUGIN.close()
            sites = {c.site_id: c.callee_expr for ff in facts for c in ff.calls}
            out[name] = ({sites[e.site_id]: e for e in edges}, read, absent)
    finally:
        if old is None:
            os.environ.pop("MAVEN_OPTS", None)
        else:
            os.environ["MAVEN_OPTS"] = old
    return out


def test_a_cached_dependency_turns_untyped_into_a_named_far_end(deps_tree):
    """Design rule 14: read from this machine, never fetched. A parent's property, a BOM
    the parent imports, and a dependency's own dependency are each followed."""
    edges, read, absent = deps_tree["maven"]
    for call, owner in (("l.hello", "Lib"), ("e.hello", "Extra"), ("t.hello", "Trans")):
        e = edges[call]
        assert (e.reason, e.frontier) == ("outside", f"org.acme.{owner}.hello"), call
    assert read == ["org.acme:extra:3.0", "org.acme:lib:2.0", "org.acme:trans:1.0"]
    assert "org.acme:missing:9" in absent, "declared and not on this machine: said"


def test_mediation_honours_exclusions_optional_and_scope(deps_tree):
    """`gone` is excluded, `opt` optional and `tested` test-scoped, so none is read even
    though all three are cached, and a call into an excluded one stays untyped."""
    edges, read, _ = deps_tree["maven"]
    assert not any(x in " ".join(read) for x in ("gone", "opt", "tested"))
    assert edges["g.hello"].reason == "untyped"


def test_gradle_variables_and_the_version_catalog_name_the_same_jars(deps_tree):
    edges, read, absent = deps_tree["gradle"]
    # No exclusion is written here, so `gone` is `lib`'s dependency and is read: the two
    # trees differ by exactly what their build files say.
    assert read == ["org.acme:extra:3.0", "org.acme:gone:1.0", "org.acme:lib:2.0",
                    "org.acme:trans:1.0"]
    assert edges["g.hello"].reason == "outside"
    assert edges["l.hello"].reason == "outside" and edges["e.hello"].reason == "outside"
    assert absent == []


# ---------------------------------------------- what the judgements say of it ---- #

_DISPATCH = {
    "Base.java": "package p;\n\npublic abstract class Base {\n    abstract void step();\n\n"
                 "    void tick() {\n        step();\n    }\n}\n",
    "A.java": "package p;\n\nclass A extends Base {\n    void step() {}\n}\n",
    "B.java": "package p;\n\nclass B extends Base {\n    void step() {}\n}\n",
    "Util.java": "package p;\n\nimport org.nowhere.Missing;\n\nclass Util {\n"
                 "    static int width(int n) {\n        return 1;\n    }\n\n"
                 "    static int width(String s) {\n        return 2;\n    }\n\n"
                 "    static void use(Missing m) {\n        width(m.part());\n    }\n\n"
                 "    static void never() {}\n}\n",
}


@pytest.fixture(scope="module")
def judged(tmp_path_factory):
    if _WHY:
        pytest.skip(_WHY)
    from dunneflow.anomalies import detect
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    root = tmp_path_factory.mktemp("judged")
    (root / "p").mkdir()
    for name, text in _DISPATCH.items():
        (root / "p" / name).write_text(text, encoding="utf-8")
    store = Store(root.parent / f"{root.name}.db")
    analyze_tree(root, store)
    resolve_calls(store)
    found = {a.kind: a for a in detect(store, include_tests=False).items}
    store.close()
    return found


def test_dispatch_is_said_as_dispatch_and_not_as_a_shared_name(judged):
    """Tom, 2026-11-02: the finding stands (the edge is not drawn) and says which cause it
    is, off `calls.reason`. A template method calling its abstract step is the design."""
    lost = judged["LOST_EDGE"]
    assert "dispatched to one of 2 implementations" in lost.title
    assert "share the name" not in lost.title
    assert "design working" in lost.blind_spot


def test_a_routine_an_untyped_call_may_reach_is_not_called_dead(judged):
    """`width(m.part())` cannot be typed (`Missing` is nowhere), and with two `width`s javac
    cannot choose, which is traccar's `BufferUtil.indexOf(…, buf)`. Either may be its target,
    so both are left out, and the finding says so (design rule 1)."""
    dead = judged["DEAD_CODE"]
    assert "p.Util.never" in dead.detail and "p.Util.width" not in dead.detail
    assert "2 routines are left out because a call the reader could not type" in dead.blind_spot
