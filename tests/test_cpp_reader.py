"""The C and C++ reader: generated where it can be, pinned where it cannot, and asked through
the host.

The three kinds of claim `test_java_reader.py` makes, and only the last two need clang:

- **What is generated is current.** `facts.hpp` and the fingerprint list are regenerated from
  `schema.py` and from the tree, and compared.
- **The second implementations agree with the first.** BLAKE2b, every id function and the
  decoding are written again in C++, and the reader's own `--self-test` holds them to the
  vectors the host wrote (`tests/fixtures/ids/vectors.json`).
- **The reader answers the host as the host asks.** Built by the host's own `build` seam,
  handshaken, opened and read through `OutOfProcessPlugin` (rule 48's shape).

Skipped for two named reasons only, each said in the skip: this build has no C and C++
plugin, or this machine has no `clang++` and libclang the plugin's probe accepts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.ingest.contract import ToolchainMissing
from dunneflow.ingest.outofprocess import built_reader
from dunneflow.schema import ControlKind, FileFacts, hash_source

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gen_facts_cpp  # noqa: E402

PLUGIN = ingest.PLUGINS.get("cpp")
HERE = PLUGIN.manifest.root if PLUGIN is not None else None
VECTORS = ROOT / "tests" / "fixtures" / "ids" / "vectors.json"
FIXTURE = ROOT / "tests" / "fixtures" / "cpp"


def _clang_missing() -> str:
    if PLUGIN is None:
        return "this build ships no C and C++ reader"
    try:
        PLUGIN.probe()
    except ToolchainMissing as exc:
        return f"no clang and libclang this reader accepts on this machine: {exc}"
    return ""


_WHY = _clang_missing()
needs_plugin = pytest.mark.skipif(PLUGIN is None, reason="this build ships no C and C++ reader")
needs_clang = pytest.mark.skipif(bool(_WHY), reason=_WHY or "-")


# -------------------------------------------------------- generated, no clang --- #

@needs_plugin
def test_the_reader_s_types_are_the_schema_s():
    assert HERE is not None
    facts = HERE / "src" / "facts.hpp"
    assert facts.read_text(encoding="utf-8") == gen_facts_cpp.generate(), (
        "facts.hpp is not what schema.py generates: uv run python tools/gen_facts_cpp.py --write")


@needs_plugin
def test_every_file_the_reader_is_built_from_is_in_the_fingerprint():
    """Rule 12. Named, never globbed — so this is the glob, and it is what catches a file
    added to `src/` or `vendor/` without `--write`."""
    assert PLUGIN is not None
    named = list(PLUGIN.manifest.fingerprint)
    assert named == gen_facts_cpp.fingerprint(), (
        "plugin.json's fingerprint is not the files on disk: "
        "uv run python tools/gen_facts_cpp.py --write")
    assert {"plugin.json", "reader.cpp", "vendor/clang-c/Index.h",
            "vendor/LICENSE.TXT"} <= set(named)


@needs_plugin
def test_the_build_is_one_argv_and_libclang_is_never_linked():
    """One command for every platform: nothing names where this machine keeps libclang,
    because the reader opens it at run time (`src/clang.hpp`)."""
    assert PLUGIN is not None
    m = PLUGIN.manifest
    assert m.build[0] == "clang++" and "{output}" in m.build and "reader.cpp" in m.build
    assert not any(a.startswith(("-l", "-L")) for a in m.build), "libclang is opened, not linked"
    assert m.toolchain is not None and m.toolchain.command == "clang++"
    assert m.toolchain.asks_reader, "clang++ answering is not libclang opening"
    assert not m.in_process


@needs_plugin
def test_the_reader_claims_c_and_keeps_every_suffix_the_old_one_had():
    """Tom's decision: one plugin for C and C++, which owns `.h`."""
    assert PLUGIN is not None
    suffixes = set(PLUGIN.manifest.discovery.suffixes)
    assert {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".inl"} <= suffixes
    assert "ThirdParty" in PLUGIN.manifest.discovery.skip_dirs


@pytest.mark.parametrize("said, ok", [
    ("Apple clang version 21.0.0 (clang-2100.3.34.2)", True),
    ("Homebrew clang version 22.1.0", True),
    ("clang version 19.1.5", True),
    ("Ubuntu clang version 18.1.3 (1ubuntu1)", True),
    ("clang version 14.0.0", False),
    ("", False),
])
def test_the_version_probe_reads_what_each_clang_says(said, ok):
    from dunneflow.ingest.outofprocess import _at_least

    assert _at_least(said, "15.0.0") is ok


# -------------------------------------------------------------- with clang --- #

@pytest.fixture(scope="module")
def binary() -> Path:
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    return built_reader(PLUGIN.manifest)


def _self_test(binary: Path, vectors: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(binary), "--self-test", str(vectors)],
        capture_output=True, text=True, timeout=120, check=False,
    )


@needs_clang
def test_the_second_implementations_agree_with_the_first(binary):
    out = _self_test(binary, VECTORS)
    assert out.returncode == 0, out.stderr[-3000:]
    assert " 0 disagreeing" in out.stderr


@needs_clang
def test_a_tampered_vector_is_seen_to_fail(binary, tmp_path):
    """Rule 59: a harness whose every check passes has not shown it can fail."""
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    data["definition_id"][0][3] = "0" * 16
    data["decode"][2][1] = "A"
    bad = tmp_path / "tampered.json"
    bad.write_text(json.dumps(data), encoding="utf-8")
    out = _self_test(binary, bad)
    assert out.returncode == 2, out.stderr[-3000:]
    assert "DISAGREES definition_id" in out.stderr and "DISAGREES decode" in out.stderr


@needs_clang
def test_a_machine_without_libclang_is_a_missing_toolchain_not_a_refused_plugin(monkeypatch):
    """`clang++` answers and libclang cannot be opened: the reader declines the handshake, and
    the walk reads that as *not read, no toolchain* (`walk._runnable`) — never as the build
    defect a `PluginRefused` would stop the run for (rule 49)."""
    assert PLUGIN is not None
    monkeypatch.setenv("DUNNEFLOW_LIBCLANG", "/nowhere/libclang.so")
    with pytest.raises(ToolchainMissing, match="no libclang could be opened"):
        PLUGIN.probe()


def _read(root: Path, files: list[Path]) -> tuple[dict[str, FileFacts], list[str]]:
    assert PLUGIN is not None
    PLUGIN.open(root, files)
    try:
        notes = list(PLUGIN.opened_notes)
        return {ff.path: ff for ff in PLUGIN.extract(files, root)}, notes
    finally:
        PLUGIN.close()


@pytest.fixture(scope="module")
def read():
    if _WHY:
        pytest.skip(_WHY)
    files = sorted(p for p in FIXTURE.rglob("*") if p.is_file())
    return _read(FIXTURE, files)


@needs_clang
def test_every_file_is_read_and_none_is_an_error(read):
    facts, _ = read
    assert set(facts) == {"c/tool.c", "include/lib/store.h", "src/app.cpp"}
    assert all(not ff.errors for ff in facts.values()), {p: ff.errors for p, ff in facts.items()}
    assert {ff.lang for ff in facts.values()} == {"cpp"}


@needs_clang
def test_an_include_directory_is_inferred_from_a_unique_suffix(read):
    """`#include "lib/store.h"` names a file under `include/`, which nothing declares: one
    file in the tree ends with that spelling, so its prefix is an include directory."""
    _, notes = read
    assert any(n.startswith("1 include directories inferred") for n in notes), notes


@needs_clang
def test_routines_are_definitions_named_by_namespace_and_record(read):
    facts, _ = read
    app = {r.qualname: r for r in facts["src/app.cpp"].routines}
    assert set(app) == {"lib.Store.Fire", "lib.FileStore.Load", "classify", "run", "main"}
    fire = app["lib.Store.Fire"]
    assert fire.is_method and fire.class_name == "Store"
    assert [(p.name, p.type) for p in fire.params] == [("Times", "int")]
    header = {r.qualname for r in facts["include/lib/store.h"].routines}
    # An inline body is a routine; a declaration and `= default` are not.
    assert header == {"lib.Store.Count"}


@needs_clang
def test_a_way_in_is_read_off_a_declaration_whose_body_is_elsewhere(read):
    facts, _ = read
    eps = facts["include/lib/store.h"].entrypoints
    assert [(e.kind.value, e.name, e.routine_id) for e in eps] == [("LIBRARY", "Fire", None)]
    mains = [e for ff in facts.values() for e in ff.entrypoints if e.kind.value == "MAIN"]
    assert sorted(e.name for e in mains) == ["main", "main"]


@needs_clang
def test_a_construction_written_as_a_declaration_is_one(read):
    """`std::ifstream in(key);` opens a file. The syntactic reader documented a refusal of this
    shape and never implemented it; clang knows it is a construction."""
    facts, _ = read
    app = facts["src/app.cpp"]
    made = {c.callee_expr for c in app.calls if c.is_construction}
    assert made == {"std.ifstream", "std.vector"}, made
    hits = {(b.kind.value, b.direction.value, b.target) for b in app.boundaries}
    assert ("FILE", "IN", "key") in hits
    # `lib::FileStore store;` constructs nothing anybody wrote parentheses for.
    assert "lib.FileStore" not in {c.callee_expr for c in app.calls}


@needs_clang
def test_a_call_keeps_the_dotted_contract(read):
    facts, _ = read
    calls = {c.callee_expr for c in facts["src/app.cpp"].calls}
    assert {"store.Load", "value.size", "store.Fire", "std.getline", "classify", "run"} <= calls


@needs_clang
def test_an_else_if_ladder_is_one_decision_with_its_arms(read):
    facts, _ = read
    app = facts["src/app.cpp"]
    by_word = {(p.word, p.line_start): p for p in app.control}
    ladder = by_word[("if", 28)]
    assert ladder.kind is ControlKind.DECISION and ladder.arms == 3
    arms = [a.kind.value for a in app.control_arms if a.point_id == ladder.point_id]
    assert arms == ["if", "else if", "else"]
    assert not any(w == "if" and 28 < line <= 34 for w, line in by_word), "an else-if is an arm"
    assert by_word[("for", 40)].once_start == 40
    assert by_word[("switch", 44)].arms == 2
    assert by_word[("try", 50)].kind is ControlKind.HANDLER


@needs_clang
def test_c_is_read(read):
    facts, _ = read
    tool = facts["c/tool.c"]
    assert {r.qualname for r in tool.routines} == {"count_lines", "main"}
    assert {(b.kind.value, b.evidence) for b in tool.boundaries} >= {
        ("FILE", "fopen"), ("ENV", "getenv"), ("STDIO", "printf")}
    guard = [p for p in tool.control if p.word == "if" and p.line_start == 11]
    assert guard and guard[0].kind is ControlKind.GUARD


@needs_clang
def test_a_crlf_file_hashes_as_the_host_reads_it(tmp_path):
    """`SOURCE_TEXT`: the reader parses and hashes the text the host hashed, so a CRLF file is
    not refused as having changed while it was read."""
    f = tmp_path / "crlf.c"
    f.write_bytes(b"int main(void)\r\n{\r\n    return 0;\r\n}\r\n")
    facts, _ = _read(tmp_path, [f])
    ff = facts["crlf.c"]
    assert not ff.errors, ff.errors
    assert ff.content_hash == hash_source(f.read_text(encoding="utf-8", errors="replace"))
    assert [r.line_start for r in ff.routines] == [1]


@needs_clang
def test_an_include_two_files_answer_adds_no_directory(tmp_path):
    """Rule 1: a guess between two headers is a wrong declaration as often as a right one."""
    for d in ("a", "b"):
        (tmp_path / d / "inc").mkdir(parents=True)
        (tmp_path / d / "inc" / "same.h").write_text("int x;\n", encoding="utf-8")
    src = tmp_path / "main.c"
    src.write_text('#include "inc/same.h"\nint main(void) { return 0; }\n', encoding="utf-8")
    files = [src, tmp_path / "a" / "inc" / "same.h", tmp_path / "b" / "inc" / "same.h"]
    _, notes = _read(tmp_path, files)
    assert any("1 answered by more than one file" in n for n in notes), notes


# ------------------------------------------------------------------- edges --- #

@pytest.fixture(scope="module")
def edges():
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    files = sorted(p for p in FIXTURE.rglob("*") if p.is_file())
    PLUGIN.open(FIXTURE, files)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(files, FIXTURE)}
        got = list(PLUGIN.edges())
        return facts, got, list(PLUGIN.edges_said)
    finally:
        PLUGIN.close()


def _by_expr(facts, got):
    site = {c.site_id: (ff.path, c.callee_expr) for ff in facts.values() for c in ff.calls}
    return {site[e.site_id]: e for e in got if e.site_id in site}


@needs_clang
def test_every_call_has_an_answer_and_every_edge_lands_on_a_routine_s_first_line(edges):
    """The host turns a location into an id (`resolve/supplied.py`): an edge whose line is not
    a routine's first line is an edge the map cannot draw."""
    facts, got, _ = edges
    calls = {c.site_id for ff in facts.values() for c in ff.calls}
    assert {e.site_id for e in got} == calls, "every written call is answered, edge or stop"
    starts = {(r.file, r.line_start, r.name) for ff in facts.values() for r in ff.routines}
    landed = [e for e in got if e.file]
    assert landed
    for e in landed:
        assert (e.file, e.line, e.name) in starts, e


@needs_clang
def test_a_call_in_another_call_s_arguments_is_a_call(edges):
    """`printf("%d lines\\n", count_lines(path))`: the syntactic reader stepped over every
    call written inside an argument list."""
    facts, got, _ = edges
    by = _by_expr(facts, got)
    e = by[("c/tool.c", "count_lines")]
    assert (e.file, e.name) == ("c/tool.c", "count_lines")


@needs_clang
def test_an_overridden_method_is_dispatched_with_its_bodies_named(edges):
    """Tom's rule: only a method nothing overrides is CERTAIN. `store.Load(k)` on a
    `Store&` reaches whatever implements the pure virtual — here one body, named, and not
    drawn as an edge."""
    facts, got, _ = edges
    e = _by_expr(facts, got)[("src/app.cpp", "store.Load")]
    assert e.reason == "dynamic" and not e.file
    assert [(a.file, a.name) for a in e.answers] == [("src/app.cpp", "Load")]
    fire = _by_expr(facts, got)[("src/app.cpp", "store.Fire")]
    assert (fire.file, fire.name, fire.reason) == ("src/app.cpp", "Fire", "")


@needs_clang
def test_a_call_outside_the_tree_says_where_it_went(edges):
    facts, got, said = edges
    by = _by_expr(facts, got)
    fopen = by[("c/tool.c", "fopen")]
    assert (fopen.reason, fopen.frontier) == ("outside", "fopen")
    # The inline namespace a standard library hides in is not part of what anybody wrote.
    assert by[("src/app.cpp", "std.getline")].frontier == "std.getline"
    assert any(n.startswith("edges: 3 files parsed by libclang") for n in said), said
