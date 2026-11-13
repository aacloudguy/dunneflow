"""A Go method is a boundary by its receiver's type, and never by its variable's name.

`r.ReadFile(name)` is a file read when `r` is an `*os.Root` and nothing at all when `r` is
a type of the program's own. Found on Comitia2 (`internal/cli/project_folder.go`,
2026-11-07): every file operation made through an `os.Root` was missing, which is where
code that must not follow a symlink out of a folder does its reading and writing.

The receiver is typed by `go/types` against the packages `go.yaml` declares
(`typed_packages`), one file at a time, so a file's facts depend on that file and the
rules and nothing else (rule 81, rule 95). A receiver whose type is declared in another
file is the residue, and the edge pass counts it in a note that reaches the host.
"""
from __future__ import annotations

import shutil

import pytest

from dunneflow import ingest
from dunneflow.detectors import EVIDENCE_NOTE
from dunneflow.schema import BoundaryHit, FileFacts

GO = ingest.PLUGINS.get("go")

# One routine per method of `os.Root`: (method, arguments, direction, target). `Name` and
# `Close` touch nothing, so their direction is None.
METHODS = [
    ("Open", '"a"', "IN", "a"),
    ("OpenRoot", '"a"', "IN", "a"),
    ("ReadFile", '"a"', "IN", "a"),
    ("Stat", '"a"', "IN", "a"),
    ("Lstat", '"a"', "IN", "a"),
    ("Readlink", '"a"', "IN", "a"),
    ("FS", "", "IN", ""),
    ("Create", '"a"', "OUT", "a"),
    ("WriteFile", '"a", nil, 0o600', "OUT", "a"),
    ("Mkdir", '"a", 0o700', "OUT", "a"),
    ("MkdirAll", '"a", 0o700', "OUT", "a"),
    ("Remove", '"a"', "OUT", "a"),
    ("RemoveAll", '"a"', "OUT", "a"),
    ("Rename", '"a", "b"', "OUT", "a"),
    ("Link", '"a", "b"', "OUT", "a"),
    ("Symlink", '"a", "b"', "OUT", "a"),
    ("Chmod", '"a", 0o600', "OUT", "a"),
    ("Chown", '"a", 1, 2', "OUT", "a"),
    ("Lchown", '"a", 1, 2', "OUT", "a"),
    ("Chtimes", '"a", t, t', "OUT", "a"),
    ("OpenFile", '"a", os.O_RDWR, 0o600', "BOTH", "a"),
    ("Name", "", None, ""),
    ("Close", "", None, ""),
]

METHODS_GO = "package root\n\nimport (\n\t\"os\"\n\t\"time\"\n)\n\n" + "".join(
    f"func m{m}(r *os.Root, t time.Time) {{ r.{m}({args}) }}\n" for m, args, _, _ in METHODS
)

SPECIAL_GO = '''package root

import (
\t"context"
\t"io/fs"
\t"net"
\t"os"
\t"os/exec"
)

var lchown = (*os.Root).Lchown

var stat = os.Stat

var command = exec.Command

type Store struct{}

func (Store) ReadFile(name string) ([]byte, error) { return nil, nil }

type holder struct{ root *os.Root }

type embeds struct{ *os.Root }

func opened(p string) {
\tr, _ := os.OpenRoot(p)
\tr.ReadFile("x")
}

func value(r *os.Root) {
\tf := r.Chmod
\tf("n", 0o600)
}

func useLchown(r *os.Root) { lchown(r, "n", -1, 3) }

func own(r Store) { r.ReadFile("x") }

func walk(r *os.Root, fn fs.WalkDirFunc) { fs.WalkDir(r.FS(), ".", fn) }

func field(h holder) { h.root.Stat("x") }

func embedded(e embeds) { e.ReadFile("x") }

func expr(r *os.Root) { (*os.Root).Chown(r, "n", 1, 2) }

func dial(ctx context.Context, p, network string) {
\tvar d net.Dialer
\td.DialContext(ctx, "unix", p)
\td.DialContext(ctx, "tcp", "h:1")
\td.DialContext(ctx, network, p)
\tvar lc net.ListenConfig
\tlc.Listen(ctx, "unix", p)
}
'''

# `holder` is declared in special.go, so this file alone cannot type `h.root`.
ELSEWHERE_GO = '''package root

func elsewhere(h holder) { h.root.Remove("x") }
'''

FILES = {"methods.go": METHODS_GO, "special.go": SPECIAL_GO, "elsewhere.go": ELSEWHERE_GO}


def _line(source: str, needle: str) -> int:
    lines = [i for i, text in enumerate(source.splitlines(), 1) if needle in text]
    assert len(lines) == 1, (needle, lines)
    return lines[0]


@pytest.fixture(scope="module")
def typed(tmp_path_factory):
    if GO is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    root = tmp_path_factory.mktemp("gotyped")
    (root / "go.mod").write_text("module example.com/root\n\ngo 1.25\n", encoding="utf-8")
    paths = []
    for name, source in FILES.items():
        (root / name).write_text(source, encoding="utf-8")
        paths.append(root / name)
    GO.probe()
    GO.open(root, paths)
    try:
        facts = {ff.path: ff for ff in GO.extract(paths, root)}
        edges = list(GO.edges())
        said = list(GO.edges_said)
    finally:
        GO.close()
    return facts, edges, said


def _rows(ff: FileFacts) -> dict[str, list[BoundaryHit]]:
    names = {r.id: r.name for r in ff.routines}
    out: dict[str, list[BoundaryHit]] = {}
    for b in ff.boundaries:
        out.setdefault(names.get(b.routine_id, "?"), []).append(b)
    return out


def test_every_method_of_os_root_takes_its_package_function_s_kind(typed):
    facts, _, _ = typed
    rows = _rows(facts["methods.go"])
    for method, _, direction, target in METHODS:
        got = rows.get(f"m{method}", [])
        if direction is None:
            assert got == [], f"os.Root.{method} touches nothing: {got}"
            continue
        assert [(b.kind.value, b.direction.value, b.evidence, b.target) for b in got] == [
            ("FILE", direction, f"os.Root.{method}", target)], method


def test_opening_a_root_is_a_read_and_what_it_returns_is_typed(typed):
    facts, _, _ = typed
    got = {(b.evidence, b.target) for b in _rows(facts["special.go"])["opened"]}
    assert got == {("os.OpenRoot", "p"), ("os.Root.ReadFile", "x")}


def test_a_method_expression_in_a_package_variable_is_a_touch_where_it_is_taken(typed):
    """`var lchown = (*os.Root).Lchown` is Comitia2's own shape: the call that follows is
    through a variable and names nothing, so the touch is where the method is taken."""
    facts, _, _ = typed
    ff = facts["special.go"]
    ms = ff.module_scope
    assert ms is not None
    at = _line(SPECIAL_GO, "var lchown")
    got = [b for b in ff.boundaries if b.line == at]
    assert [(b.routine_id, b.kind.value, b.direction.value, b.evidence) for b in got] == [
        (ms.id, "FILE", "OUT", "os.Root.Lchown" + EVIDENCE_NOTE
         + "taken as a value, not called here")]
    assert "useLchown" not in _rows(ff), "the call through the variable names nothing"


def test_a_package_function_taken_as_a_value_is_a_touch_too(typed):
    facts, _, _ = typed
    ff = facts["special.go"]
    at = _line(SPECIAL_GO, "var stat")
    got = [b for b in ff.boundaries if b.line == at]
    assert [(b.direction.value, b.evidence.split(EVIDENCE_NOTE)[0]) for b in got] == [
        ("IN", "os.Stat")]
    # beads' test seam, `execCommandFn = exec.Command`: another program, taken as a value.
    at = _line(SPECIAL_GO, "var command")
    assert [(b.kind.value, b.evidence.split(EVIDENCE_NOTE)[0]) for b in ff.boundaries
            if b.line == at] == [("PROCESS", "exec.Command")]


def test_a_method_value_is_a_touch_where_it_is_taken(typed):
    facts, _, _ = typed
    got = _rows(facts["special.go"])["value"]
    assert [(b.line, b.direction.value, b.evidence.split(EVIDENCE_NOTE)[0]) for b in got] == [
        (_line(SPECIAL_GO, "f := r.Chmod"), "OUT", "os.Root.Chmod")]


def test_a_type_of_the_program_s_own_with_the_same_method_is_not_a_boundary(typed):
    """Rule 30: `r` is a label. Typed by what it is, a `Store`, it touches nothing."""
    facts, edges, _ = typed
    ff = facts["special.go"]
    assert "own" not in _rows(ff)
    own = next(r for r in ff.routines if r.name == "own")
    site = next(c for c in ff.calls if c.caller_id == own.id)
    assert site.callee_expr == "r.ReadFile" and not site.at_boundary
    edge = next(e for e in edges if e.site_id == site.site_id)
    assert (edge.file, edge.name) == ("special.go", "ReadFile")


def test_a_walk_through_a_root_records_the_root_and_the_walk(typed):
    facts, _, _ = typed
    got = {b.evidence for b in _rows(facts["special.go"])["walk"]}
    assert got == {"os.Root.FS", "fs.WalkDir"}


def test_a_field_an_embedding_and_a_method_expression_are_typed_in_one_file(typed):
    facts, _, _ = typed
    rows = _rows(facts["special.go"])
    assert [b.evidence for b in rows["field"]] == ["os.Root.Stat"]
    assert [b.evidence for b in rows["embedded"]] == ["os.Root.ReadFile"]
    assert [(b.evidence, b.target) for b in rows["expr"]] == [("os.Root.Chown", "n")], (
        "a method expression's receiver is its first argument, so the name is the second")


def test_a_typed_boundary_is_never_also_an_edge(typed):
    """Rule 2, for the typed spelling as for the written one."""
    facts, edges, _ = typed
    ff = facts["special.go"]
    opened = next(r for r in ff.routines if r.name == "opened")
    sites = {c.callee_expr: c for c in ff.calls if c.caller_id == opened.id}
    assert sites["r.ReadFile"].at_boundary
    assert sites["r.ReadFile"].site_id not in {e.site_id for e in edges}


def test_a_dialer_and_a_listen_config_decide_on_their_network_argument(typed):
    facts, _, _ = typed
    ff = facts["special.go"]
    got = [(b.kind.value, b.direction.value, b.target, b.evidence)
           for b in _rows(ff)["dial"]]
    blind = ("the network argument is not a literal, so a Unix-domain socket here reads "
             "as NETWORK")
    assert got == [
        ("LOCAL_IPC", "OUT", "p", "net.Dialer.DialContext"),
        ("NETWORK", "OUT", "h:1", "net.Dialer.DialContext"),
        ("NETWORK", "OUT", "p", "net.Dialer.DialContext" + EVIDENCE_NOTE
         + "blind spot: " + blind),
        ("LOCAL_IPC", "IN", "p", "net.ListenConfig.Listen"),
    ]
    assert ff.network == [], "a typed spelling is never offered to network.libraries"


def test_a_receiver_typed_in_another_file_is_counted_and_said(typed):
    """Rule 95 forbids the row and rule 38 forbids the silence: one file cannot type
    `h.root`, so no row is recorded, and the edge pass says how many such calls it saw."""
    facts, _, said = typed
    assert facts["elsewhere.go"].boundaries == []
    assert any(n.startswith("1 call(s) through net.Dialer or net.ListenConfig or os.Root "
                            "are not recorded as boundaries") for n in said), said


def test_every_typed_rule_names_something_the_declarations_declare():
    """A typed entry the declarations do not declare could never match, silently."""
    import re

    from dunneflow.detectors import rules_document

    doc = rules_document("go")
    types: set[tuple[str, str]] = set()
    methods: set[tuple[str, ...]] = set()
    for src in doc["typed_packages"].values():
        found = re.search(r"^package (\w+)", src, re.M)
        assert found is not None
        pkg = found.group(1)
        types |= {(pkg, t) for t in re.findall(r"^type (\w+) ", src, re.M)}
        methods |= {(pkg, t, m) for t, m in
                    re.findall(r"^func \(\w+ \*?(\w+)\) (\w+)\(", src, re.M)}
    typed = {
        tuple(x.split("."))
        for rule in doc["boundaries"] for x in rule.get("exact", [])
        if x.count(".") == 2 and tuple(x.split(".")[:2]) in types
    }
    assert len(typed) > 20 and typed <= methods, sorted(typed - methods)
