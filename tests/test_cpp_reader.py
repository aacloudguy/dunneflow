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
def test_what_loads_code_and_asks_the_kernel_is_a_boundary(tmp_path):
    """Each of these was in no rule, so a hand-written call to one recorded nothing. The target
    is the argument that says what was touched, which differs by call."""
    f = tmp_path / "doors.c"
    f.write_text(
        "void *dlopen(const char *, int);\n"
        "void *dlsym(void *, const char *);\n"
        "void *LoadLibraryW(const short *);\n"
        "void *GetProcAddress(void *, const char *);\n"
        "long ptrace(int, int, void *, void *);\n"
        "int mprotect(void *, unsigned long, int);\n"
        "int VirtualProtect(void *, unsigned long, int, int *);\n"
        "long syscall(long, ...);\n"
        "int WSASend(int, void *, int, int *, int, void *, void *);\n"
        "void *LoadLibraryWithSearchPaths(const char *);\n"
        "void run(const char *lib, const short *wide, void *addr, int pid, int sock) {\n"
        "    void *h = dlopen(lib, 1);\n"
        '    dlsym(h, "start");\n'
        "    void *w = LoadLibraryW(wide);\n"
        '    GetProcAddress(w, "begin");\n'
        "    ptrace(1, pid, 0, 0);\n"
        "    mprotect(addr, 4096, 7);\n"
        "    VirtualProtect(addr, 4096, 64, 0);\n"
        "    syscall(SYS_futex, addr);\n"
        "    WSASend(sock, 0, 1, 0, 0, 0, 0);\n"
        "    LoadLibraryWithSearchPaths(lib);\n"
        "}\n"
    )
    facts, _ = _read(tmp_path, [f])
    hits = {(b.evidence, b.kind.value, b.direction.value, b.target)
            for b in facts["doors.c"].boundaries}
    assert hits == {
        ("dlopen", "FILE", "IN", "lib"),
        ("dlsym", "PROCESS", "IN", '"start"'),
        ("LoadLibraryW", "FILE", "IN", "wide"),
        ("GetProcAddress", "PROCESS", "IN", '"begin"'),
        ("ptrace", "PROCESS", "BOTH", "pid"),
        ("mprotect", "PROCESS", "BOTH", ""),
        ("VirtualProtect", "PROCESS", "BOTH", ""),
        ("syscall", "PROCESS", "BOTH", "SYS_futex"),
        ("WSASend", "NETWORK", "BOTH", "sock"),
    }, hits


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


# ------------------------------------------- rule 98, on tmux, git and nmap --- #
#
# Each of these was found by reading `dunneflow check` and the map against the source of
# a real C tree (chunk 4), and each is the smallest tree that shows it.

def _tree(root: Path, files: dict[str, str]):
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    paths = sorted(root / rel for rel in files)
    assert PLUGIN is not None
    PLUGIN.open(root, paths)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(paths, root)}
        return facts, list(PLUGIN.edges()), list(PLUGIN.opened_notes) + list(PLUGIN.edges_said)
    finally:
        PLUGIN.close()


@needs_clang
def test_an_inactive_arm_and_a_directive_line_are_not_code(tmp_path):
    """`clang_tokenize` lexes the raw text, so both were in the token scan: an inactive arm's
    calls were recorded beside the active one's, and nmap's `#if !defined(LINUX)` was a
    control point with four calls to `defined` in it."""
    facts, _, _ = _tree(tmp_path, {"a.c": (
        "int on(void) { return 1; }\n"
        "int off(void) { return 0; }\n"
        "int f(void) {\n"
        "#if defined(NOT_HERE) && \\\n"
        "    !defined(NOR_HERE)\n"
        "    if (off()) return off();\n"
        "#else\n"
        "    if (on()) return on();\n"
        "#endif\n"
        "    return 0;\n"
        "}\n")})
    ff = facts["a.c"]
    assert [c.callee_expr for c in ff.calls] == ["on", "on"]
    assert [(p.line_start, p.header) for p in ff.control] == [(8, "if (on())")]


@needs_clang
def test_a_call_a_macro_writes_is_the_call_it_expands_to(tmp_path):
    """git's `skip_prefix(...)` is `skip_prefix_impl(...)` written in `git-compat-util.h`.
    The walk judged a cursor by where it was *spelled*, so it never entered one, and 22,348
    of git's calls had nothing to say where they went. A macro that expands to no call says
    that instead (Rust's word for its own `macro_rules!`)."""
    facts, got, _ = _tree(tmp_path, {
        "m.h": "int sp_impl(int);\nint g(int);\n#define SP(x) sp_impl((x))\n"
               "#define ID(x) (x)\n#define N_(s) (s)\n",
        "m.c": '#include "m.h"\nint sp_impl(int x) { return x; }\nint g(int x) { return x; }\n'
               'const char *u(void) { SP(1); ID(g(2)); return N_("text"); }\n'})
    by = _by_expr(facts, got)
    assert (by[("m.c", "SP")].name, by[("m.c", "SP")].line) == ("sp_impl", 2)
    assert by[("m.c", "g")].name == "g"
    n = by[("m.c", "N_")]
    assert (n.reason, n.frontier, n.file) == ("unfollowed", "N_", "")


@needs_clang
def test_of_several_definitions_the_one_a_file_can_see_is_the_one_it_gets(tmp_path):
    """C has one definition of an external function per program, so a file that defines
    what it calls links its own: tmux's `osdep-freebsd.c` and its `cmp_procs`, which two
    other platforms' files define too. A caller that sees none stays without an edge."""
    facts, got, _ = _tree(tmp_path, {
        "a.c": "int dup(void) { return 1; }\nint fa(void) { return dup(); }\n",
        "b.c": "int dup(void) { return 2; }\n",
        "c.c": "int dup(void);\nint fc(void) { return dup(); }\n"})
    by = _by_expr(facts, got)
    assert (by[("a.c", "dup")].file, by[("a.c", "dup")].line) == ("a.c", 1)
    assert (by[("c.c", "dup")].file, by[("c.c", "dup")].candidates) == ("", 2)


@needs_clang
def test_a_redefinition_clang_refused_loses_a_tie(tmp_path):
    """git's `compat/precompose_utf8.c` redefines what `git-compat-util.h` defines `static
    inline` when `PRECOMPOSE_UNICODE` is unset; the build compiles one or the other."""
    facts, got, _ = _tree(tmp_path, {
        "h.h": "static inline int pre(int x) { return x; }\n",
        "p.c": '#include "h.h"\nint pre(int x) { return x + 1; }\n',
        "u.c": '#include "h.h"\nint use(void) { return pre(1); }\n'})
    e = _by_expr(facts, got)[("u.c", "pre")]
    assert (e.file, e.line, e.candidates) == ("h.h", 1, 0)


@needs_clang
def test_the_compiler_s_own_headers_are_found(tmp_path):
    """`stddef.h` is clang's, not the system's. libclang did not find it on LLVM's Linux
    tarball, and every C or C++ file there read on without it."""
    _, _, said = _tree(tmp_path, {
        "a.c": "#include <stddef.h>\n#include <stdarg.h>\nvoid a(void) {}\n",
        "b.cpp": "#include <string>\nvoid b() {}\n"})
    assert not [line for line in said if "file not found" in line], said


@needs_clang
def test_an_inferred_directory_never_shadows_the_system_s_own_headers(tmp_path):
    """nmap's libssh2 carries an OS/400 `stdio.h`: the one file in the tree to answer
    `<stdio.h>`, so its directory was inferred, and as `-I` it shadowed the system's own —
    300 of nmap's files went looking for OS/400's `qadrt.h`."""
    _, got, said = _tree(tmp_path, {
        "os400/include/stdio.h": "#include <qadrt.h>\n",
        "main.c": '#include <stdio.h>\nint main(void) { printf("hi\\n"); return 0; }\n'})
    # The OS/400 header's own parse misses `qadrt.h`, and only that one: `main.c` gets the
    # system's `stdio.h`.
    assert "  1x 'qadrt.h' file not found" in said, said
    assert [(e.reason, e.frontier) for e in got] == [("outside", "printf")]


@needs_clang
def test_a_nameless_record_a_macro_writes_is_not_a_structure(tmp_path):
    """Every `TAILQ_ENTRY(window) entry;` is a `struct { ... }`: tmux had 190 structures
    called `<anonymous>`. One written by hand is still read."""
    facts, _, _ = _tree(tmp_path, {"q.c": (
        "#define ENTRY(t) struct { struct t *next; }\n"
        "struct node { ENTRY(node) link; int v; };\n"
        "struct { int a; } g;\n")})
    assert sorted(s.name for s in facts["q.c"].structures) == ["<anonymous>", "node"]


# --------------------------------------- chunk 5: Unreal Core, old against new --- #

@needs_clang
def test_a_routine_is_named_as_written_not_as_clang_spells_a_template(tmp_path):
    """clang spells a class template's constructor `TBox<T>`, its destructor `~TBox<T>`, and
    `operator T&()` as `operator type-parameter-0-0 &`. Nobody writes or searches for those."""
    facts, _, _ = _tree(tmp_path, {"t.cpp": (
        "template <typename T> struct TBox {\n"
        "  TBox() {}\n"
        "  template <typename U> TBox(U u) {}\n"
        "  ~TBox() {}\n"
        "  operator T&() { return v; }\n"
        "  T v;\n"
        "};\n")})
    names = sorted(r.name for r in facts["t.cpp"].routines if r.name != "<module>")
    assert names == ["TBox", "TBox", "operator T&", "~TBox"]


@needs_clang
def test_a_variable_a_macro_declares_does_not_hide_the_macro_s_call(tmp_path):
    """Unreal's `UE_LOG` declares `LOG_Static(Format, ...)`, a variable whose location is the
    macro's own name, and every `UE_LOG(...)` read as a declaration: 1,825 calls to 43."""
    facts, _, _ = _tree(tmp_path, {"l.cpp": (
        "struct R { R(const char*) {} };\n"
        "void emit(const R&);\n"
        "#define LOG(F) do { static R LOG_Static(F); emit(LOG_Static); } while (0)\n"
        "void f() { LOG(\"hello\"); }\n")})
    assert [c.callee_expr for c in facts["l.cpp"].calls] == ["LOG"]


@needs_clang
def test_a_record_a_macro_names_by_pasting_is_not_a_structure(tmp_path):
    """`DECLARE_CYCLE_STAT(..., STAT_X, ...)` is a `struct FStat_STAT_X`, hundreds of them in
    Core; a record whose name the file writes, as `TAILQ_HEAD(joblist, job)` does, is kept."""
    facts, _, _ = _tree(tmp_path, {"s.cpp": (
        "#define STAT(N) struct FStat_##N { int v; };\n"
        "#define HEAD(N) struct N { int first; };\n"
        "STAT(Draw)\nHEAD(joblist)\n")})
    assert [s.name for s in facts["s.cpp"].structures] == ["joblist"]


@needs_clang
def test_an_include_directory_is_never_above_the_root_without_a_preset(tmp_path):
    """Rule 108, and the gate's third decision: a spelling that names the root's own parent
    (`Core/Public/x.h`, read from inside `Core`) does not make that parent a directory."""
    root = tmp_path / "Core"
    _, _, said = _tree(root, {
        "Public/x.h": "int x(void);\n",
        "a.c": '#include "Core/Public/x.h"\nint main(void) { return x(); }\n'})
    assert any("1 not taken, because the directory they name is above the analysed root" in n
               for n in said), said


@needs_clang
def test_unreal_s_preset_compiles_cpp_as_its_build_tool_does(tmp_path):
    """UnrealBuildTool's Apple toolchain compiles every `.cpp` as Objective-C++, and Mac
    sources are written for it; read as C++, a routine after an `@` was lost. Off Apple the
    preset says nothing, and C++ is C++."""
    _tree(tmp_path, {"Runtime/Core/Public/HAL/Platform.h": "#pragma once\n"})
    facts, _, said = _tree(tmp_path / "Runtime" / "Core", {
        "Private/Mac/Misc.cpp": "void a() { @autoreleasepool { } }\nvoid b() { }\n"})
    objc = any("compiles C++ as objective-c++" in n for n in said)
    assert objc == (sys.platform == "darwin"), said
    if objc:
        names = [r.name for r in facts["Private/Mac/Misc.cpp"].routines if r.name != "<module>"]
        assert names == ["a", "b"]


@needs_clang
def test_a_macro_that_expands_to_several_calls_is_none_of_them(tmp_path):
    """Taking the first call made every Unreal `UE_LOG` the construction of the static variable
    it declares. A macro that wraps a function of its own name is that function (git's
    `error`); one with several callees is a macro, and says so."""
    facts, got, _ = _tree(tmp_path, {"m.cpp": (
        "struct D { int n; };\n"
        "bool quiet(); void basic_log(const char*) {}\n"
        "int error(const char*); int const_error();\n"
        "void *chk(void*, const void*, unsigned long, unsigned long);\n"
        "unsigned long osize(const void*);\n"
        "#define LOG(F) do { static D d; if (!quiet()) basic_log(F); } while (0)\n"
        "#define error(F) (error(F), const_error())\n"
        "#define copy(D, S, N) chk(D, S, N, osize(D))\n"
        'void f(char *a, char *b) { LOG("x"); error("y"); copy(a, b, 1); }\n')})
    by = _by_expr(facts, got)
    log = by[("m.cpp", "LOG")]
    assert (log.reason, log.frontier, log.constructs) == ("unfollowed", "LOG", "")
    err = by[("m.cpp", "error")]
    assert (err.reason, err.frontier) == ("outside", "error")
    # Several calls and none of them here: macOS's fortified `memcpy`. It leaves, as written.
    cp = by[("m.cpp", "copy")]
    assert (cp.reason, cp.frontier) == ("outside", "copy")
    assert not any(c.is_construction for c in facts["m.cpp"].calls)
