"""What a macro does to the C and C++ reader's facts, one adversarial shape per test.

clang has already expanded every macro, so nothing here parses one. What goes wrong is the
join between what clang says happened and the tokens somebody wrote: a macro's expansion all
maps to one offset in the file, and a call can be written in its arguments, in its body, or
half of each.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.ingest.contract import ToolchainMissing

PLUGIN = ingest.PLUGINS.get("cpp")


def _clang_missing() -> str:
    if PLUGIN is None:
        return "this build ships no C and C++ reader"
    try:
        PLUGIN.probe()
    except ToolchainMissing as exc:
        return f"no clang and libclang this reader accepts on this machine: {exc}"
    return ""


_WHY = _clang_missing()
pytestmark = pytest.mark.skipif(bool(_WHY), reason=_WHY or "-")


def _read(root: Path, text: str, name: str = "m.cpp"):
    """The one file's facts, its edges by call site, and everything the reader said."""
    f = root / name
    f.write_text(text, encoding="utf-8")
    assert PLUGIN is not None
    PLUGIN.open(root, [f])
    try:
        ff = {x.path: x for x in PLUGIN.extract([f], root)}[name]
        return ff, {e.site_id: e for e in PLUGIN.edges()}, list(PLUGIN.edges_said)
    finally:
        PLUGIN.close()


def _routine(ff, qualname: str):
    found = [r for r in ff.routines if r.qualname == qualname]
    assert len(found) == 1, (qualname, [r.qualname for r in ff.routines])
    return found[0]


def _calls(ff, qualname: str) -> list[str]:
    rid = _routine(ff, qualname).id
    return [c.callee_expr for c in ff.calls if c.caller_id == rid]


def _hits(ff, qualname: str) -> set[tuple[str, str]]:
    rid = _routine(ff, qualname).id
    return {(b.kind.value, b.evidence) for b in ff.boundaries if b.routine_id == rid}


def test_a_record_declared_with_its_variable_is_read_once(tmp_path):
    """`static struct X { X() {} } once;` is Unreal's idiom for run-this-once, and clang shows
    the struct twice: as a declaration, and as the child of the variable. Every method in it
    had two routines, and every boundary in those two boundaries."""
    ff, _, _ = _read(tmp_path, (
        "void h();\n"
        "struct G { G() { h(); } void m() { h(); } } g;\n"
        "void f() { static struct L { L() { h(); } } once; }\n"
    ))
    assert sorted(r.qualname for r in ff.routines) == ["G.G", "G.m", "L.L", "f"]
    assert sorted(s.name for s in ff.structures) == ["G", "L"]


def test_the_header_of_a_local_class_s_constructor_is_not_a_call(tmp_path):
    ff, _, _ = _read(tmp_path, "void f() { static struct L { L() {} } once; }\n")
    assert _calls(ff, "f") == []


def test_a_macro_that_wrote_a_declaration_is_not_the_next_one_s_decorator(tmp_path):
    """A macro expanding to nothing can annotate what follows it, and one that declared
    something cannot: `WHOLE(a)` is `a`, and `b` does not start on its line."""
    ff, _, _ = _read(tmp_path, (
        "#define WHOLE(n) void n() {}\n"
        "#define VAR(n) int n;\n"
        "#define MARK(x)\n"
        "WHOLE(a)\n"
        "void b() {}\n"
        "VAR(v)\n"
        "void c() {}\n"
        "MARK(Thing)\n"
        "void d() {}\n"
    ))
    assert _routine(ff, "b").line_start == 5
    assert "WHOLE" not in _routine(ff, "b").decorators
    assert _routine(ff, "c").line_start == 7
    assert "VAR" not in _routine(ff, "c").decorators
    assert _routine(ff, "d").line_start == 8
    assert {"MARK", "Thing"} <= set(_routine(ff, "d").decorators)
