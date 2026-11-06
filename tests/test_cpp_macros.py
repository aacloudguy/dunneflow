"""What a macro does to the C and C++ reader's facts, one adversarial shape per test.

clang has already expanded every macro, so nothing here parses one. What goes wrong is the
join between what clang says happened and the tokens somebody wrote: a macro's expansion all
maps to one offset in the file, and a call can be written in its arguments, in its body, or
half of each.
"""

from __future__ import annotations

import json
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


_PRELUDE = (
    "extern \"C\" {\n"
    "int connect(int, const void *, int);\n"
    "int rename(const char *, const char *);\n"
    "}\n"
    "void helper(const char *);\n"
)


def _site(ff, edges, qualname: str, expr: str):
    rid = _routine(ff, qualname).id
    found = [edges[c.site_id] for c in ff.calls if c.caller_id == rid and c.callee_expr == expr]
    assert len(found) == 1, (qualname, expr, found)
    return found[0]


def test_a_function_named_in_a_macro_s_arguments_is_the_macro_s_call(tmp_path):
    """`CALL(connect, 1)` writes no call: the macro makes one, starting at that name. It was
    reported as a macro that expands to no call, and reached nothing."""
    ff, edges, _ = _read(tmp_path, _PRELUDE + (
        "#define CALL(f, a) f(a, 0, 0)\n"
        "void t() { CALL(connect, 1); }\n"
    ))
    e = _site(ff, edges, "t", "CALL")
    assert (e.reason, e.frontier) == ("outside", "connect"), e


def test_a_call_written_in_a_macro_s_arguments_stays_the_one_written(tmp_path):
    """And the macro around it is not credited with it, or `RETRY` would be `connect` twice
    over. A member call starts at its receiver, not at its name (`checkf(Key.IsValid())`)."""
    ff, edges, _ = _read(tmp_path, _PRELUDE + (
        "struct K { bool IsValid(); };\n"
        "#define RETRY(e) do { e; } while (0)\n"
        "void t(K key) { RETRY(connect(1, 0, 0)); RETRY(key.IsValid()); }\n"
    ))
    assert _site(ff, edges, "t", "connect").frontier == "connect"
    assert _site(ff, edges, "t", "key.IsValid").frontier == "K.IsValid"
    assert _hits(ff, "t") == {("NETWORK", "connect")}
    rid = _routine(ff, "t").id
    sites = [edges[c.site_id] for c in ff.calls if c.caller_id == rid and c.callee_expr == "RETRY"]
    assert len(sites) == 2
    for e in sites:
        assert (e.reason, e.frontier) == ("unfollowed", "RETRY")
        assert "no call of its own" in e.how


def test_an_operator_in_a_macro_s_arguments_says_nothing_about_the_macro(tmp_path):
    ff, edges, _ = _read(tmp_path, (
        "struct V { V operator+(const V &) const; };\n"
        "#define ID(e) (e)\n"
        "void t(V a, V b) { ID(a + b); }\n"
    ))
    e = _site(ff, edges, "t", "ID")
    assert (e.reason, e.frontier) == ("unfollowed", "ID"), e


def test_a_macro_named_like_a_boundary_that_can_call_nothing_touches_nothing(tmp_path):
    """`#define rename(a, b) 0` recorded FILE OUT at a line where no file is touched."""
    ff, edges, _ = _read(tmp_path, _PRELUDE + (
        "#undef rename\n"
        "#define rename(a, b) 0\n"
        "void t() { rename(\"a\", \"b\"); }\n"
    ))
    assert _hits(ff, "t") == set()
    e = _site(ff, edges, "t", "rename")
    assert (e.reason, e.frontier) == ("unfollowed", "rename")
    assert "no call of its own" in e.how


@pytest.mark.parametrize("body", ["open64", "SOMETHING_ELSE", "other(a)"])
def test_a_macro_with_a_word_in_it_keeps_its_boundary_when_clang_shows_nothing(tmp_path, body):
    """Clang drops a statement it cannot type, so silence does not mean the macro calls
    nothing. `open(a)` over `undeclared` keeps its boundary; the definition has not said no.
    The last word of the body is the one that matters, because a range can stop short of it."""
    ff, edges, _ = _read(tmp_path, (
        f"#define open(a) {body}\n"
        "void t() { open(undeclared); }\n"
    ))
    assert _hits(ff, "t") == {("FILE", "open")}
    e = _site(ff, edges, "t", "open")
    assert e.reason == "unfollowed"
    assert "clang recorded no call" in e.how


def test_a_macro_defined_in_a_header_is_read_from_the_header(tmp_path):
    (tmp_path / "z.h").write_text("#define rename(a, b) 0\n", encoding="utf-8")
    ff, _, _ = _read(tmp_path, '#include "z.h"\nvoid t() { rename(1, 2); }\n')
    assert _hits(ff, "t") == set()


def test_a_file_scope_initialiser_s_call_belongs_to_the_module_scope(tmp_path):
    """No routine is on the stack, so these were not read at all, and one runs before `main`."""
    ff, edges, _ = _read(tmp_path, _PRELUDE + (
        "int getpid();\n"
        "#define INIT() connect(0, 0, 0)\n"
        "int g_macro = INIT();\n"
        "int g_hand = getpid();\n"
        "struct S { int m() { return connect(1, 0, 0); } };\n"
        "S g_s;\n"
    ))
    assert ff.module_scope is not None
    rid = ff.module_scope.id
    # It has to be a routine as well, or the store holds calls that belong to nothing.
    assert [r.name for r in ff.routines if r.id == rid] == ["<module>"]
    calls = {c.callee_expr: c for c in ff.calls if c.caller_id == rid}
    assert set(calls) == {"connect", "getpid"}
    assert {(b.kind.value, b.evidence) for b in ff.boundaries if b.routine_id == rid} == {
        ("NETWORK", "connect")}
    assert edges[calls["getpid"].site_id].reason == "outside"
    assert _hits(ff, "S.m") == {("NETWORK", "connect")}


def test_no_initialiser_means_no_module_scope_routine(tmp_path):
    ff, _, _ = _read(tmp_path, "int a = 1;\nint f() { return a; }\n")
    assert [r.name for r in ff.routines] == ["f"]


def test_an_operator_or_a_sizeof_in_an_initialiser_is_not_a_call(tmp_path):
    """Core's `Inherit = A | B` flags and `UE_ARRAY_COUNT`'s helper, which is only declared."""
    ff, edges, _ = _read(tmp_path, (
        "enum E { A, B };\n"
        "constexpr E operator|(E a, E b) { return a; }\n"
        "E flags = A | B;\n"
        "char (&Helper(const int (&)[3]))[3];\n"
        "#define COUNT(a) sizeof(Helper(a))\n"
        "int arr[3];\n"
        "unsigned long n = COUNT(arr);\n"
        "int f() { return COUNT(arr); }\n"
    ))
    assert _calls(ff, "f") == ["COUNT"]
    assert not [c for c in ff.calls if c.callee_expr in {"operator|", "Helper"}]
    rid = _routine(ff, "f").id
    site = next(c for c in ff.calls if c.caller_id == rid)
    assert (edges[site.site_id].reason, edges[site.site_id].frontier) == ("unfollowed", "COUNT")


def test_a_body_half_written_by_a_macro_has_its_written_half_read(tmp_path):
    """`BEGIN hand(); END`: clang keeps nothing under a statement it cannot type, so with no
    scan `undeclared()` was lost, and so was every guard somebody wrote there."""
    ff, edges, _ = _read(tmp_path, _PRELUDE + (
        "#define BEGIN void half(int n) { helper(\"begin\");\n"
        "#define END }\n"
        "#define WHOLE(n) void n() { helper(\"whole\"); if (1) {} }\n"
        "BEGIN\n"
        "  if (n) { undeclared(n); }\n"
        "  helper(\"mine\");\n"
        "END\n"
        "WHOLE(all)\n"
    ))
    calls = _calls(ff, "half")
    assert calls.count("undeclared") == 1 and calls.count("helper") == 2, calls
    rid = _routine(ff, "half").id
    assert [p.word for p in ff.control if p.routine_id == rid] == ["if"]
    # All of it the macro's: nothing to scan, and what clang named is what there is.
    assert _calls(ff, "all") == ["helper"]
    aid = _routine(ff, "all").id
    assert [p.word for p in ff.control if p.routine_id == aid] == []


def test_what_cannot_be_read_is_counted(tmp_path):
    ff, _, said = _read(tmp_path, _PRELUDE + (
        "#define VIA(f) void via(void (*f)()) { f(); }\n"
        "VIA(p)\n"
        "void a() { __asm__(\"nop\"); }\n"
        "int renamed() __asm__(\"other\");\n"
    ))
    assert _routine(ff, "via")
    text = " ".join(said)
    assert "1 inline assembly statements and 1 assembly labels" in text, said
    assert "1 calls in macro-written bodies" in text, said


def test_a_call_that_leaves_the_tree_meets_the_rules_by_the_name_clang_gave_it(tmp_path):
    """`Hasher.Update` cannot be matched by reading it, and `FSHA1.Update` can. Inside the tree
    the same call is the tree's own: a boundary there would cost it its internal edge."""
    out = tmp_path / "outside"
    out.mkdir()
    tree = tmp_path / "tree"
    tree.mkdir()
    (out / "sha.h").write_text("struct FSHA1 { void Update(); FSHA1(); };\n", encoding="utf-8")
    (tree / "mine.h").write_text("struct FMD5 { void Update(); };\n", encoding="utf-8")
    (tree / "compile_commands.json").write_text(
        json.dumps([{"directory": str(tree), "file": "m.cpp",
                     "arguments": ["clang++", f"-I{out}", "-c", "m.cpp"]}]),
        encoding="utf-8")
    ff, _, _ = _read(tree, (
        '#include <sha.h>\n#include "mine.h"\n'
        "void t(FSHA1 &h, FMD5 &mine) { FSHA1(); h.Update(); mine.Update(); }\n"
    ))
    assert _hits(ff, "t") == {("CRYPTO", "FSHA1.Update")}, ff.errors


def test_a_prefix_does_not_claim_a_path_s_methods_or_a_name_that_shares_its_letters(tmp_path):
    ff, _, _ = _read(tmp_path, (
        "#include <filesystem>\n"
        "void PQueueUp();\n"
        "void t(std::filesystem::path p) { p.string(); PQueueUp(); std::filesystem::exists(p); }\n"
    ))
    assert _hits(ff, "t") == {("FILE", "std.filesystem.exists")}
