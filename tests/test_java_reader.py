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

