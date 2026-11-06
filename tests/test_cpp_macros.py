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


def _expanded(root: Path, files: dict[str, str]):
    """Facts by file, and every `macro_callee` row, for a tree of several files."""
    paths = []
    for rel, text in files.items():
        (root / rel).write_text(text, encoding="utf-8")
        paths.append(root / rel)
    assert PLUGIN is not None
    PLUGIN.open(root, sorted(paths))
    try:
        facts = {x.path: x for x in PLUGIN.extract(sorted(paths), root)}
        edges = {e.site_id: e for e in PLUGIN.edges()}
        return facts, edges, list(PLUGIN.edge_macros)
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
    assert [(p.word, p.header) for p in ff.control if p.routine_id == aid] == [("if", "WHOLE(all)")]


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


def _defs(ff) -> dict[str, str]:
    return {d.id: d.name for d in ff.macro_defs}


def test_who_wrote_a_routine_s_name_and_who_wrote_its_body_are_two_questions(tmp_path):
    ff, _, _ = _read(tmp_path, (
        "#define SIG(n) void n()\n"
        "#define BODY { }\n"
        "#define WHOLE(n) void n() { }\n"
        "#define PASTED(n) void get_##n() { }\n"
        "#define BEGIN void half() {\n"
        "#define END }\n"
        "SIG(sig_only) { }\n"
        "void body_only() BODY\n"
        "WHOLE(whole)\n"
        "PASTED(x)\n"
        "BEGIN int a; END\n"
        "void hand() { }\n"
    ))
    defs = _defs(ff)
    got = {r.qualname: (defs.get(r.name_by, ""), defs.get(r.body_by, "")) for r in ff.routines}
    assert got == {
        "sig_only": ("SIG", ""),
        "body_only": ("", "BODY"),
        "whole": ("WHOLE", "WHOLE"),
        "get_x": ("PASTED", "PASTED"),
        "half": ("BEGIN", "BEGIN"),
        "hand": ("", ""),
    }


def test_a_redefined_macro_is_a_second_definition_and_not_the_same_name(tmp_path):
    """Folding on the name would put a `system` call under Core's `check`."""
    ff, _, _ = _read(tmp_path, (
        "#define check(x) ((void)0)\n"
        "void a() { check(1); }\n"
        "#undef check\n"
        "#define check(x) system(x)\n"
        "void b() { check(1); }\n"
    ))
    uses = {_routine(ff, q).id: q for q in ("a", "b")}
    by = {uses[s.routine_id]: s.def_id for s in ff.macro_sites if s.routine_id in uses}
    assert by["a"] != by["b"]
    assert sorted((d.name, d.line) for d in ff.macro_defs) == [("check", 1), ("check", 4)]


def test_each_use_says_what_it_stands_in_for(tmp_path):
    ff, _, _ = _read(tmp_path, (
        "#define NOTHING\n"
        "#define ONE 1\n"
        "#define MAKE(n) int n;\n"
        "#define MARK(x)\n"
        "NOTHING\n"                  # line 5: stands for nothing at all
        "MAKE(v)\n"                  # line 6: declares `v`
        "MARK(a)\n"                  # line 7: annotates `f`
        "void f() { int x = ONE; }\n"  # line 8: inside a body
        "struct S { MAKE(m) };\n"    # line 9: inside a record
        "#if ONE\n"                  # line 10: decides what is read, and is not a use
        "#endif\n"
        "struct T { int a; NOTHING };\n"  # line 12: in a record, declaring nothing
        "#define WHOLE(n) void n() { }\n"
        "WHOLE(w)\n"                 # line 14: is `w`, and is not a use inside it
        "void p(int x NOTHING);\n"   # line 15: in a prototype's parameters
        "int table[] = { ONE };\n"   # line 16: in a table
        "namespace n { NOTHING }\n"  # line 17: a namespace declares nothing by holding it
    ))
    got = {(s.name, s.line): (s.position.value, s.routine_id) for s in ff.macro_sites}
    assert got == {
        ("NOTHING", 5): ("file_scope", None),
        ("MAKE", 6): ("declaration", None),
        ("MARK", 7): ("declaration", None),
        ("ONE", 8): ("statement", _routine(ff, "f").id),
        ("MAKE", 9): ("declaration", None),
        ("NOTHING", 12): ("declaration", None),
        ("WHOLE", 14): ("declaration", None),
        ("NOTHING", 15): ("declaration", None),
        ("ONE", 16): ("declaration", None),
        ("NOTHING", 17): ("file_scope", None),
    }
    assert ff.macro_directive_uses == 1


def test_a_definition_says_where_it_came_from(tmp_path):
    """By path: `clang_Location_isInSystemHeader` calls an Unreal module's own headers system
    headers, because they arrive by `-idirafter`. Outside the tree only the last two segments
    are stored, since where an SDK is installed is no fact about the program (rule 60)."""
    out = tmp_path / "elsewhere" / "sys"
    out.mkdir(parents=True)
    tree = tmp_path / "tree"
    tree.mkdir()
    (out / "lib.h").write_text("#define LIBM 1\n", encoding="utf-8")
    (tree / "own.h").write_text("#define OWN 1\n", encoding="utf-8")
    (tree / "compile_commands.json").write_text(
        json.dumps([{"directory": str(tree), "file": "m.cpp",
                     "arguments": ["clang++", f"-I{out}", "-DCMD=3", "-c", "m.cpp"]}]),
        encoding="utf-8")
    ff, _, _ = _read(tree, (
        '#include "own.h"\n#include <lib.h>\n'
        "int a = OWN + LIBM + CMD + __LINE__;\n"
    ))
    got = {d.name: (d.origin.value, d.file) for d in ff.macro_defs}
    assert got["OWN"] == ("tree", "own.h")
    assert got["LIBM"] == ("outside", "sys/lib.h")
    assert got["CMD"] == ("command_line", "")
    assert got["__LINE__"] == ("builtin", "")


def test_a_routine_counts_the_assembly_it_holds(tmp_path):
    ff, _, _ = _read(tmp_path, (
        "void a() { __asm__(\"nop\"); __asm__(\"nop\"); }\n"
        "void b() { }\n"
    ))
    assert (_routine(ff, "a").opaque_asm, _routine(ff, "b").opaque_asm) == (2, 0)


def _through(rows) -> set[tuple[str, str, str]]:
    return {(b.kind.value, b.evidence, b.target) for m in rows for b in m.hits}


def test_a_macro_cannot_hide_a_boundary(tmp_path):
    """`SEND(x)` expanding to `connect` recorded nothing at all. Nested, pasted, object-like
    and with a name given in the arguments: each is a call that leaves the program."""
    facts, _, rows = _expanded(tmp_path, {"m.cpp": _PRELUDE + (
        "#define WRAP(a) connect(a, 0, 0)\n"
        "#define SEND(a) WRAP(a)\n"
        "#define CALL(f, a) f(a, 0, 0)\n"
        "#define PASTE(a, b) a##b\n"
        "#define BARE connect(9, 0, 0)\n"
        "void nested(int fd) { SEND(fd); }\n"
        "void named(int fd) { CALL(connect, fd); }\n"
        "void pasted() { PASTE(con, nect)(1, 0, 0); }\n"
        "void bare() { BARE; }\n"
    )})
    ff = facts["m.cpp"]
    for q in ("nested", "named", "pasted", "bare"):
        rid = _routine(ff, q).id
        got = [m for m in rows if m.routine_id == rid]
        assert any(b.kind.value == "NETWORK" for m in got for b in m.hits), (q, got)
        assert all(m.target_file == "" for m in got)
    # Named where somebody wrote it, and blank where only the macro's body says it.
    assert ("NETWORK", "connect", "fd") in _through(
        [m for m in rows if m.routine_id == _routine(ff, "nested").id])
    assert ("NETWORK", "connect", "") in _through(
        [m for m in rows if m.routine_id == _routine(ff, "bare").id])


def test_a_macro_reaching_the_tree_s_own_function_of_that_name_is_not_a_boundary(tmp_path):
    """Rule 2, and the reason this is decided after every file is parsed: `connect` is defined
    in the other file, and nothing in this one can say so."""
    facts, _, rows = _expanded(tmp_path, {
        "a.cpp": "int connect(int, const void *, int);\n"
                 "#define WRAP(a) connect(a, 0, 0)\n"
                 "void t() { WRAP(1); }\n",
        "b.cpp": "int connect(int, const void *, int) { return 0; }\n",
    })
    row = next(m for m in rows if m.routine_id == _routine(facts["a.cpp"], "t").id)
    assert (row.target_file, row.target_name) == ("b.cpp", "connect")
    assert row.hits == []


def test_written_and_expanded_on_one_line_are_one_act(tmp_path):
    """`UE_LOG` is STDIO by its own name, whatever it calls to do it."""
    facts, _, rows = _expanded(tmp_path, {"m.cpp": (
        "extern \"C\" { int printf(const char *, ...); int puts(const char *); }\n"
        "#define UE_LOG(x) (printf(x), puts(x))\n"
        "void t() { UE_LOG(\"a\"); }\n"
    )})
    ff = facts["m.cpp"]
    assert _hits(ff, "t") == {("STDIO", "UE_LOG")}
    assert _through(rows) == set()
    assert {m.callee for m in rows} == {"printf", "puts"}


def test_a_rule_that_names_a_macro_is_not_contradicted_by_what_it_reaches(tmp_path):
    """Reading Core, `UE_LOG` reaches `FMsg::Logf`, which that tree defines. Beside it the same
    shape under a function's name is a shadow: the rule says which it is about."""
    ff, _, _ = _read(tmp_path, (
        "void logf(const char *);\n"
        "#define UE_LOG(x) logf(x)\n"
        "#define puts(x) logf(x)\n"
        "void a() { UE_LOG(\"x\"); }\n"
        "void b() { puts(\"x\"); }\n"
    ))
    assert _hits(ff, "a") == {("STDIO", "UE_LOG")}
    assert _hits(ff, "b") == set()
    assert {(s.name, s.shadows) for s in ff.macro_sites} == {("UE_LOG", ""), ("puts", "STDIO")}


def test_a_call_written_in_a_macro_s_arguments_does_not_count_twice(tmp_path):
    facts, _, rows = _expanded(tmp_path, {"m.cpp": _PRELUDE + (
        "#define RETRY(e) do { e; } while (0)\n"
        "void t() { RETRY(connect(1, 0, 0)); }\n"
    )})
    assert _hits(facts["m.cpp"], "t") == {("NETWORK", "connect")}
    assert rows == []


def test_a_function_called_through_a_macro_s_lookup_is_indirect(tmp_path):
    """`((fn)dlsym(0, s))()`: the lookup is a boundary, and the call it makes has no name."""
    facts, _, rows = _expanded(tmp_path, {"m.cpp": (
        "extern \"C\" void *dlsym(void *, const char *);\n"
        "typedef int (*fn)();\n"
        "#define FP(s) ((fn)dlsym(0, s))()\n"
        "void t() { FP(\"d\"); }\n"
    )})
    assert _through(rows) == {("PROCESS", "dlsym", '"d"')}
    assert [(m.callee, m.indirect) for m in rows if m.indirect] == [("", True)]


def test_a_macro_named_like_a_boundary_that_reaches_the_tree_is_a_shadow_and_no_boundary(tmp_path):
    ff, edges, _ = _read(tmp_path, (
        "void helper(const char *);\n"
        "#define unlink(x) helper(x)\n"
        "void t() { unlink(\"a\"); }\n"
    ))
    assert _hits(ff, "t") == set()
    assert [(s.name, s.shadows) for s in ff.macro_sites] == [("unlink", "FILE")]
    assert _site(ff, edges, "t", "unlink").frontier == "helper"


def test_a_platform_s_spelling_of_the_same_act_is_not_a_shadow(tmp_path):
    """`open` becoming `open64`, and a library's function under the name, keep the boundary."""
    ff, _, _ = _read(tmp_path, (
        "int open64(const char *, int);\n"
        "#define open(a, b) open64(a, b)\n"
        "void t() { open(\"a\", 0); }\n"
    ))
    assert _hits(ff, "t") == {("FILE", "open")}
    assert [s.shadows for s in ff.macro_sites if s.name == "open"] == [""]


def test_a_macro_of_several_calls_is_expanded_and_not_unfollowable(tmp_path):
    """`unfollowed` says nobody could follow it. This one's places are all in `macro_callees`,
    and rule 40 says those are two numbers."""
    facts, edges, rows = _expanded(tmp_path, {"m.cpp": (
        "void a() {}\nvoid b() {}\n"
        "#define BOTH() (a(), b())\n"
        "void t() { BOTH(); }\n"
    )})
    ff = facts["m.cpp"]
    e = _site(ff, edges, "t", "BOTH")
    assert (e.reason, e.frontier, e.file) == ("expanded", "BOTH", "")
    assert {(m.callee, m.target_name) for m in rows} == {("a", "a"), ("b", "b")}


def test_a_written_call_keeps_its_site_id_beside_a_macro_that_makes_the_same_call(tmp_path):
    base = (
        "extern \"C\" int connect(int, const void *, int);\n"
        "#define WRAP(a) connect(a, 0, 0)\n"
        "void t() { connect(1, 0, 0); }\n"
    )
    plain, _, _ = _read(tmp_path, base)
    with_macro, _, _ = _read(
        tmp_path, base.replace("connect(1, 0, 0); }", "connect(1, 0, 0); WRAP(2); }"))
    site = [c.site_id for c in plain.calls if c.callee_expr == "connect"]
    assert site == [c.site_id for c in with_macro.calls if c.callee_expr == "connect"]


def test_a_loop_in_a_body_a_macro_wrote_is_control_and_says_so(tmp_path):
    ff, _, _ = _read(tmp_path, (
        "void h();\n"
        "#define EACH(n) void n(int k) { for (int i = 0; i < k; i++) { if (i) h(); } }\n"
        "EACH(all)\n"
    ))
    got = [(p.word, p.kind.value, p.depth, p.header, p.line_start) for p in ff.control]
    assert got == [("for", "LOOP", 1, "EACH(all)", 3), ("if", "DECISION", 2, "EACH(all)", 3)]


def test_a_hand_written_body_gets_no_control_from_a_macro_that_expands_to_an_if(tmp_path):
    ff, _, _ = _read(tmp_path, (
        "void h();\n"
        "#define check(x) do { if (!(x)) h(); } while (0)\n"
        "void t(int a) { check(a); }\n"
    ))
    assert ff.control == []


def test_the_store_keeps_a_macro_s_boundaries_with_the_rest_and_replaces_them(tmp_path):
    """They are read as boundaries by everything, and a reread must not double them."""
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    store = Store(tmp_path / "g.db")
    try:
        for reread in range(2):
            (tmp_path / "m.cpp").write_text(_PRELUDE + (
                "#define WRAP(a) connect(a, 0, 0)\n"
                "void t(int fd) { WRAP(fd); }\n"
            ) + "\n" * reread, encoding="utf-8")
            analyze_tree(tmp_path, store)
            rows = store.query(
                "SELECT b.kind, b.evidence, b.target, b.expanded, d.name FROM boundaries b"
                " JOIN macro_defs d ON d.id = b.through_macro")
            assert [tuple(r) for r in rows] == [("NETWORK", "connect", "fd", 1, "WRAP")]
            assert store.query("SELECT callee FROM macro_callees")[0]["callee"] == "connect"
    finally:
        store.close()


@pytest.mark.parametrize(("lang", "word"), [
    ("cpp", "read"), ("rust", "named"), ("go", "none"), ("java", "none"), ("kotlin", "none"),
    ("python", "none"), ("typescript", "none")])
def test_every_language_declares_what_it_knows_of_a_macro(lang, word):
    from dunneflow.detectors import load_rules

    assert load_rules(lang).macro_expansion == word


def test_an_unknown_word_is_refused_and_not_defaulted(tmp_path):
    from dunneflow.detectors import RulesMissing, _macro_expansion

    with pytest.raises(RulesMissing, match="macro_expansion"):
        _macro_expansion("sometimes", "cpp", tmp_path)
    assert _macro_expansion("", "cpp", tmp_path) == ""
