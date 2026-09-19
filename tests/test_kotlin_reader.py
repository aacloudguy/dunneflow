"""The Kotlin reader: the mask, the declaration tree, and what a `{` is not.

Kotlin is a far more regular language to read than C++ — no preprocessor, no headers, no
most vexing parse — and almost everything here is about the three places that regularity
stops: an expression body with no braces, a file full of lambdas that are not declarations,
and a string that carries code inside it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from dunneflow.extractors.kotlin import decls, names, scopes
from dunneflow.extractors.kotlin.ctx import Ctx
from dunneflow.extractors.kotlin.extract import extract_file
from dunneflow.extractors.kotlin.lexer import mask
from dunneflow.extractors.kotlin.tokens import tokenize

RAW = '"' * 3


def ctx_of(src: str, path: str = "m.kt", package: str = "") -> Ctx:
    m = mask(src)
    toks = tokenize(m.code_only(), m)
    return Ctx(path=path, module="m", package=package, masked=m, toks=toks,
               root=scopes.build(toks, m))


def tree(src: str) -> list[tuple[str, str, bool]]:
    return [(s.kind.value, s.name, s.braced) for s in scopes.walk(ctx_of(src).root)
            if s.kind is not scopes.ScopeKind.FILE]


def routine_names(src: str) -> list[str]:
    return [r.qualname for r in decls.read(ctx_of(src))[0]]


def facts(src: str):
    """One in-memory file through the whole reader, so what is tested is what runs."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "m.kt"
        path.write_text(src, encoding="utf-8")
        return extract_file(path, root)


def code(src: str) -> str:
    return mask(src).code_only()


# ------------------------------------------------------------------- the mask --- #

def test_a_block_comment_nests():
    """Kotlin's rule, and the **opposite** of C++'s for the same three characters.

    A scanner that closes at the first `*/` reads the tail of the outer comment as code; one
    that counts depth in C++ reads the rest of that file as comment. Two readers, two rules,
    which is the concrete reason the two lexers are not one module.
    """
    out = code("a() /* outer /* inner */ still */ b()")
    assert "a()" in out and "b()" in out
    assert "still" not in out


def test_a_raw_string_ends_at_the_last_quote_of_a_run():
    """Four quotes, `x`, four quotes is a raw string containing `"x"`.

    The closing delimiter is the *last* three of the four. Taking the first three ends it a
    character early and the mask is inverted for the rest of the file.
    """
    out = code(f'val s = {RAW}"x"{RAW}; f()')
    assert "f()" in out
    assert "x" not in out.replace("val s", "")


def test_a_raw_string_hides_its_braces():
    out = code(f'val s = {RAW}{{ not a brace }}{RAW}; f()')
    assert "{" not in out and "}" not in out


def test_a_template_hides_the_braces_it_nests():
    out = code('val s = "${ if (a) 1 else 2 }"; f()')
    assert "{" not in out and "}" not in out
    assert "f()" in out


def test_an_interpolated_string_is_told_from_a_plain_one():
    """The first reader with something true to put in `LiteralKind.INTERPOLATED`.

    The text reported for `"$name"` is a *template*, not a constant the program holds —
    which is a different fact and is why the field exists.
    """
    got = {lit.text: lit.kind.value for lit in facts(
        'fun f() {\n  val a = "$name here"\n  val b = "plain text"\n}\n').literals}
    assert got.get("$name here") == "INTERPOLATED"
    assert got.get("plain text") == "PLAIN"


# --------------------------------------------------- the dotted contract, in Kotlin --- #

@pytest.mark.parametrize(("written", "folded"), [
    ("a.b.c", "a.b.c"),
    # Clause 5 — and Kotlin is where it earns its place. `?.` is most of the calls in
    # idiomatic Kotlin, and split into `?` and `.` every one of them is unnameable.
    ("a?.b!!.c", "a.b.c"),
    ("Timber.tag(x).d", "Timber.tag.d"),
    ("listOf<String>", "listOf"),
    ("items[0].run", ""),
    ("this.foo", "this.foo"),
])
def test_the_written_name_folds_by_the_shared_contract(written, folded):
    assert names.fold(tokenize(written), 0)[0] == folded


def test_a_backtick_name_is_one_identifier():
    """``fun `reads a deck from disk`()`` is legal and is how Kotlin spells a test name.

    Split on the spaces it is four identifiers and no function.
    """
    assert [t.text for t in tokenize("fun `reads a deck`()")][:2] == ["fun", "reads a deck"]


# ------------------------------------------------------- what a declaration is --- #

def test_an_expression_body_is_a_routine():
    """`fun f() = expr` has no braces and is the commonest shape in idiomatic Kotlin.

    It is the first function in the first file of the demo corpus. A reader that looks for
    `{` finds none of them.
    """
    got = tree('private fun alarmManager(c: Context): AlarmManager =\n'
               '    c.getSystemService(ALARM) as AlarmManager\n\nfun next() { }\n')
    assert got == [("function", "alarmManager", False), ("function", "next", True)]


def test_a_multiline_expression_body_does_not_swallow_the_next_declaration():
    got = tree("fun a(): Int =\n    1 +\n    2\n\nfun b() { }\n")
    assert [n for _, n, _ in got] == ["a", "b"]


def test_a_declaration_with_no_body_is_not_a_routine():
    """The C++ reader's rule arrived at from the other direction.

    An `interface` member and an `abstract fun` state a contract; the routine is wherever it
    is implemented, which in Kotlin is an ordinary function in the same map.
    """
    assert routine_names("interface Repo {\n  fun all(): List<Deck>\n}\n") == []


def test_an_abstract_declaration_does_not_steal_the_next_functions_body():
    """The guard compared against where the scan started instead of the token before it.

    `abstract fun go()` then `private fun done() { … }` walked past `private`, past `done`,
    and took `done`'s braces as `go`'s body: the abstract declaration became a routine, the
    real one disappeared, and both facts were wrong in the same two lines.
    """
    assert routine_names(
        "abstract class A {\n  abstract fun go()\n  private fun done() { x() }\n}\n"
    ) == ["A.done"]


def test_a_lambda_is_not_a_scope():
    """Most braces in a Kotlin file open nothing.

    Keyed on braces rather than on the declaration keyword, every `items.forEach { … }` is a
    scope and a class with three methods has forty.
    """
    assert tree("fun f() {\n  items.forEach { save(it) }\n  x.apply { y = 1 }\n}\n") == [
        ("function", "f", True)]


def test_a_companion_object_is_named_the_way_kotlin_names_it():
    """`Companion` is how it is addressed from Java and how it appears in a stack trace.

    `<anonymous>` would be this reader inventing a word for something already named.
    """
    assert tree("class C {\n  companion object {\n    fun make() = C()\n  }\n}\n") == [
        ("type", "C", True), ("type", "Companion", True), ("function", "make", False)]


def test_a_package_is_in_the_qualname_and_the_file_is_in_the_id():
    """Kotlin states its own namespace; the file is where the body is.

    Two files in one package can each declare a top-level `fun render()`, and both are real.
    """
    src = "package com.x.y\n\nfun render(): String = \"a\"\n"
    a = decls.read(ctx_of(src, path="a.kt", package="com.x.y"))[0][0]
    b = decls.read(ctx_of(src, path="b.kt", package="com.x.y"))[0][0]
    assert a.qualname == b.qualname == "com.x.y.render"
    assert a.id != b.id


def test_suspend_is_kotlins_async_and_is_read_off_the_modifier():
    """A suspending function is one the compiler rewrites, and the keyword is the only place
    that is stated — there is nothing in the body to look for."""
    rs, _, _, _ = decls.read(ctx_of("suspend fun load(id: Long): Deck? { return null }"))
    assert rs[0].is_async is True


def test_a_return_type_is_read_and_an_absent_one_is_left_absent():
    """The header runs to the body, not to the closing paren — Kotlin writes the return type
    after the parameters, so a header cut at `)` has nothing after it to read.

    An absent type means `Unit`, and writing `Unit` in would be this reader asserting
    something the file does not say.
    """
    rs, _, _, _ = decls.read(ctx_of(
        "fun a(x: Int): AlarmManager = y()\nfun b(x: Int) { }\n"))
    assert [r.returns for r in rs] == ["AlarmManager", None]


def test_a_data_classes_fields_are_in_its_primary_constructor():
    """There is no body at all, and every field is in the parameter list.

    Only `val`/`var` parameters are properties: a plain constructor parameter is an argument
    the constructor uses and forgets, and the language is explicit about the difference.
    """
    _, structs, _, _ = decls.read(ctx_of(
        "data class S(\n    val dueCards: Int,\n    val eta: Int,\n    tmp: String,\n)\n"))
    assert [f.name for f in structs[0].fields] == ["dueCards", "eta"]


def test_only_const_val_is_a_constant():
    """Every `val` in Kotlin is an immutable *binding*, including a local one.

    Admitting them all would put every local binding in the corpus into the constants table,
    which is the internal computation this tool exists not to report.
    """
    consts = decls.read(ctx_of(
        'const val ACTION = "x"\nval computed = compute()\n'
        'fun f() { val local = 1 }\n'))[3]
    assert [c.name for c in consts] == ["ACTION"]


# ------------------------------------------------------ calls, control, the file --- #

def test_a_named_argument_is_recorded_as_one():
    """The field Python fills and C++ structurally cannot, because C++ has no such syntax."""
    got = facts('fun f() { open(path = "a.txt", mode = "r") }').calls
    args = [(a.keyword, a.expr) for c in got if c.callee_expr == "open" for a in c.args]
    assert args == [("path", '"a.txt"'), ("mode", '"r"')]


def test_a_when_is_a_decision_and_its_else_is_the_default():
    """`ArmKind.CASE` and `DEFAULT` already exist for a `switch` and mean exactly this."""
    f = facts("fun f(x: Int) {\n  when (x) {\n    1 -> a()\n    2 -> b()\n"
              "    else -> c()\n  }\n}\n")
    point = [c for c in f.control if c.word == "when"]
    assert point and point[0].kind.value == "DECISION"
    assert {a.kind.value for a in f.control_arms} == {"case", "default"}


def test_a_for_always_has_a_once_span():
    """Kotlin has only `for (x in items)`, so unlike C++ there is no three-clause variant to
    tell it from. That is the language rather than a choice this reader made."""
    point = [c for c in facts("fun f() { for (x in items) { use(x) } }").control
             if c.word == "for"]
    assert point and point[0].once_start > 0


def test_a_control_keyword_is_never_a_call():
    f = facts("fun f() { if (x) { g() } while (y) { h() } }")
    assert sorted(c.callee_expr for c in f.calls) == ["g", "h"]


def test_every_call_is_external_and_says_so():
    """Resolving a Kotlin call needs types: an extension function is chosen by static
    receiver type, and `apply`/`let`/`run`/`with` change what `this` means."""
    f = facts("fun f() { g() }")
    assert all(c.external and c.callee_id is None for c in f.calls)


def test_the_probe_file_reads_as_a_whole_program():
    """The Kotlin quarter of the tree `tools/fingerprints.py` gates against.

    If this stops being true the gate compares a stamp over an empty map, which is the
    nothing it exists to refuse (rule 37).
    """
    root = Path(__file__).resolve().parent / "fixtures" / "polyglot"
    f = extract_file(root / "probe.kt", root)
    assert f.errors == []
    assert [r.qualname for r in f.routines] == [
        "probe.loadConfig", "probe.root", "probe.main"]
    assert [e.kind.value for e in f.entrypoints] == ["MAIN"]
    assert {b.kind.value for b in f.boundaries} == {"FILE", "ENV", "STDIO"}
    assert [s.name for s in f.structures] == ["Setting"]
    assert [c.name for c in f.constants] == ["RETRIES"]
    assert {lit.kind.value for lit in f.literals} == {"PLAIN", "INTERPOLATED"}
