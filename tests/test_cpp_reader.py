"""The C++ reader above the lexer: scopes, routines, calls, control and identity.

Every test here is a shape that was wrong at some point while the reader was being written,
and most of them were wrong in a way that produced a *plausible* map rather than an error.
That is the argument for the file: a C++ reader with no compiler cannot be checked by
compiling anything, so what checks it is a list of shapes whose right answer is known.

The Unreal shapes are not decoration. `UCLASS(...) class FOO_API AThing : public AActor`
and `GENERATED_BODY()` are on essentially every class in the demo corpus, and each of them
broke the reader in a different way before it was right.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.extractors.cpp import names, routines, scopes
from dunneflow.extractors.cpp.ctx import Ctx
from dunneflow.extractors.cpp.extract import extract_file
from dunneflow.extractors.cpp.lexer import mask
from dunneflow.extractors.cpp.preprocessor import scan
from dunneflow.extractors.cpp.tokens import tokenize


def ctx_of(src: str, path: str = "m.cpp") -> Ctx:
    m = mask(src)
    pre = scan(m)
    toks = tokenize(pre.code, m)
    return Ctx(path=path, module="m", masked=m, pre=pre, toks=toks,
               root=scopes.build(toks))


def kinds(src: str) -> list[tuple[str, str]]:
    return [(s.kind.value, s.name) for s in scopes.walk(ctx_of(src).root)
            if s.kind is not scopes.ScopeKind.FILE]


def routine_names(src: str) -> list[str]:
    return [r.qualname for r in routines.read(ctx_of(src))[0]]


def fold(src: str) -> str:
    return names.fold(tokenize(src), 0)[0]


# ------------------------------------------------- the dotted contract, in C++ --- #

@pytest.mark.parametrize(("written", "folded"), [
    ("FGuid::ExportTextItem", "FGuid.ExportTextItem"),
    ("ptr->Method", "ptr.Method"),
    ("obj.Method", "obj.Method"),
    ("A::B::C::d", "A.B.C.d"),
    # Clause 2 — and this one is the commonest file boundary in the demo corpus.
    ("IFileManager::Get().Delete", "IFileManager.Get.Delete"),
    ("a.b(1).c(2).d", "a.b.c.d"),
    # Clause 6. Without it every templated call in Unreal is a name nothing matches.
    ("TArray<FString>::Add", "TArray.Add"),
    ("MakeShared<FThing>", "MakeShared"),
    # `>>` has to split, or the outer list never closes.
    ("TArray<TArray<int>>::Add", "TArray.Add"),
    # Clause 3 — naming this would mean deciding what `handlers[k]` holds.
    ("handlers[k].run", ""),
    # Clause 8: the receiver word is written as written.
    ("this->Foo", "this.Foo"),
    ("Outer::~Outer", "Outer.~Outer"),
])
def test_the_three_separators_fold_to_one_name(written, folded):
    """`::`, `->` and `.` are three *acts* and one *name*.

    A rule matching `FFileHelper.SaveStringToFile` has to fire whether the code reached it
    through a scope, a pointer or a reference — and a reader that spelled them differently
    would not fail, it would make every rule miss, and the map would come back with no
    boundaries at all, looking exactly like a program that has none.
    """
    assert fold(written) == folded


# ------------------------------------------------------------- what a `{` is --- #

def test_a_declaration_with_no_body_is_not_a_routine():
    """The rule the whole reader is built on, and it settles two problems at once.

    Unreal is 51,282 headers against 23,322 `.cpp`. Read as declarations they would roughly
    double the map with rows that have nothing in them — and there would then be a header's
    `void C::d();` and a `.cpp`'s `void C::d() {}` to reconcile, which `make_id` cannot do
    because `module` is per file. Refusing the declaration dissolves both.
    """
    assert kinds("class C { void d(); };") == [("record", "C")]
    assert routine_names("class C { void d(); };") == []


def test_an_out_of_line_definition_and_a_nested_one_fold_to_the_same_name():
    """`void A::B::C::d()` at file scope, and `void C::d()` inside `namespace A::B`."""
    flat = routine_names("void A::B::C::d() { int x = 1; }")
    nested = routine_names("namespace A { namespace B { void C::d() { int x = 1; } } }")
    assert flat == nested == ["A.B.C.d"]


def test_a_constructors_member_initialiser_list_is_not_a_parameter_list():
    """`Foo::Foo(int x) : x_(x), y_(0) {` ends in `)` and is a definition.

    Read backwards from the `{` this is indistinguishable from an expression; read forwards
    from the declarator the initialisers are simply what follows a `:`, and a `:` is where
    the qualifier scan stops.
    """
    assert routine_names("Foo::Foo(int x) : x_(x), y_(0) { }") == ["Foo.Foo"]


def test_a_braced_initialiser_is_not_a_function():
    assert ("function", "") not in kinds("int a[] = {1,2,3};")
    assert routine_names("int a[] = {1,2,3};\nvoid f() { }") == ["f"]


def test_a_function_pointer_declaration_is_not_a_routine():
    assert routine_names("void (*fp)(int) = nullptr;\nvoid g() { }") == ["g"]


def test_an_operator_owns_the_parentheses_that_are_part_of_its_name():
    """`operator()(int)` is a nullary-looking name taking one argument.

    Treating the first `(` after `operator` as the parameter list silently garbles every
    functor in the corpus — and `operator<<` is defined 180 times in one Unreal module.
    """
    got = routine_names(
        "struct S { int operator()(int a) const { return a; } "
        "bool operator==(const S& o) const { return true; } };")
    assert got == ["S.operator()", "S.operator=="]


def test_a_template_header_is_stepped_over():
    assert routine_names("template<typename T>\nvoid Apply(T v) { }") == ["Apply"]


# ------------------------------------------------ the two Unreal shapes --- #

def test_a_macro_wearing_a_parameter_list_is_not_a_function():
    """`UCLASS(Blueprintable) class FOO_API AThing : public AActor {`.

    A name, a parameter list and then a base clause — the exact shape of a constructor. The
    tell is that a record keyword can never sit between a parameter list and a body, so one
    there means the candidate was a macro. Without it the class is a routine called
    `UCLASS` and the class itself is not in the map at all.
    """
    got = kinds("UCLASS(Blueprintable)\nclass FOO_API AThing : public AActor\n{\n};")
    assert got == [("record", "AThing")]


def test_generated_body_does_not_steal_the_first_methods_body():
    """`GENERATED_BODY()` carries no `;`, so it runs into the method after it.

    Two defects met here. The macro's own `()` reads as a parameter list, so the first
    method of every UObject was called `GENERATED_BODY` and owned `Tick`'s body; and
    `public:` after it reads as a member-initialiser list, because `:` is how one begins.
    An access label is a statement boundary for exactly that reason.
    """
    src = ("UCLASS()\nclass FOO_API AThing : public AActor\n{\n"
           "    GENERATED_BODY()\npublic:\n"
           "    void Tick(float D) override { Count += 1; }\n"
           "private:\n    void Secret() { }\n    int Count = 0;\n};")
    rs, structs, _, _ = routines.read(ctx_of(src))
    assert [r.qualname for r in rs] == ["AThing.Tick", "AThing.Secret"]
    assert [r.visibility for r in rs] == ["public", "private"]
    assert [f.name for f in structs[0].fields] == ["Count"]


def test_each_macro_argument_becomes_its_own_decorator():
    """The one idea that lets Blueprint be a way in with no new rule grammar.

    `EntrypointRule.matches_decorator` tests a decorator's *name* and has no `contains`
    form, so flattened into one string `BlueprintCallable` is matchable by nothing the
    detector grammar can express. Split, the existing exact-match list reaches it.
    """
    src = ('class A {\n UFUNCTION(BlueprintCallable, Category="Combat")\n'
           ' void Fire(int R) { Shoot(R); }\n};')
    rs, _, _, _ = routines.read(ctx_of(src))
    assert rs[0].decorators == ["UFUNCTION", "BlueprintCallable", "Category"]
    assert rs[0].returns == "void", "the annotation leaked into the return type"


def test_a_macro_in_a_default_argument_is_not_a_decorator():
    """`void Fire(const FString& N = TEXT("x"))` registers nothing.

    Decorators sit *before* the declarator and parameters after it, so the scan is bounded
    by where the name begins. Scanned over the whole header, `TEXT` — a string wrapper — is
    recorded as a registration.
    """
    src = 'class A { void Fire(const FString& N = TEXT("x")) { } };'
    rs, _, _, _ = routines.read(ctx_of(src))
    assert rs[0].decorators == []


def test_a_return_type_does_not_take_the_class_qualifier_with_it():
    """`void AThing::Fire(` returns `void`, not `void AThing`.

    Walking back from the `(` over "identifiers and `::`" eats the qualifier, because a
    qualifier is made of exactly the tokens a return type is made of. The one walk that
    knows where the name begins is the one that decides where the type ends.
    """
    rs, _, _, _ = routines.read(ctx_of("void AThing::Fire(int R) { }"))
    assert rs[0].returns == "void"
    rs2, _, _, _ = routines.read(ctx_of("FORCEINLINE static int Helper(int a) { return a; }"))
    assert rs2[0].returns == "int", "a storage specifier is not part of a type"


# ------------------------------------------------------------------ identity --- #

def test_a_name_defined_in_two_files_is_two_routines():
    """The file is part of a routine's identity, and Unreal proved it has to be.

    `IoDispatcherFilesystemStats.h` gives its methods empty inline bodies under one arm of
    an `#if` and the `.cpp` defines them for real. Both arms are read as live, so **221
    qualnames in 400 files had a body in two places** and the store refused the second with
    `UNIQUE constraint failed: routines.id`.
    """
    a = routines.read(ctx_of("void C::d() { }", path="a.h"))[0][0]
    b = routines.read(ctx_of("void C::d() { }", path="a.cpp"))[0][0]
    assert a.qualname == b.qualname == "C.d"
    assert a.id != b.id, "two files' definitions of one name collided"


def test_two_definitions_in_one_file_are_two_identities():
    """Overloads, and both arms of an `#ifdef` read as live. Neither replaces the other."""
    rs, _, _, _ = routines.read(ctx_of(
        "void f(int a) { }\nvoid f(const char* b) { }\nvoid f(double c) { }"))
    assert [r.qualname for r in rs] == ["f", "f", "f"]
    assert len({r.id for r in rs}) == 3


def test_a_record_declared_twice_in_one_file_is_two_identities():
    """The same defect one table over — it refused `structures.id` on the second run."""
    _, structs, _, _ = routines.read(ctx_of(
        "#ifdef A\nstruct S { int x; };\n#else\nstruct S { int y; };\n#endif"))
    assert [s.name for s in structs] == ["S", "S"]
    assert len({s.id for s in structs}) == 2


# -------------------------------------------------------- calls and boundaries --- #

def test_a_chained_call_takes_its_arguments_from_the_last_call():
    """`IFileManager::Get().FileExists(*InPath)` touches `*InPath`.

    Taking them from the parentheses the fold started at sliced from `Get()`'s `(` to
    `FileExists(...)`'s `)`, so every chained boundary in Unreal recorded a target of
    `').FileExists(*InPath'` — a string that is in the file, starts mid-expression, and is
    an argument to nothing.
    """
    facts = _facts("void f() { IFileManager::Get().FileExists(*InPath); }")
    hit = [b for b in facts.boundaries if b.evidence == "IFileManager.Get.FileExists"]
    assert hit and hit[0].target == "*InPath"


def test_a_string_literal_argument_is_still_an_argument():
    """A boundary's target is usually a literal, and literals are blanked for the matcher.

    So `getenv("HOME")` came back with an empty target — in a reader whose whole job at a
    boundary is to say *what* it touches. The mask puts them back as single tokens, at the
    same offsets, so a `{` inside one still cannot be mistaken for a brace.
    """
    facts = _facts('void f() { const char* h = getenv("HOME"); }')
    assert [b.target for b in facts.boundaries if b.evidence == "getenv"] == ['"HOME"']


def test_a_control_keyword_is_never_a_call():
    """Without this every `if (x)` is a call to a routine named `if`."""
    facts = _facts("void f() { if (x) { g(); } while (y) { h(); } }")
    assert sorted(c.callee_expr for c in facts.calls) == ["g", "h"]


def test_every_call_is_external_and_says_so():
    """`supplies_edges` is false: a C++ call cannot be resolved without types, and a
    name-matched edge in a language with overloading would be wrong often enough to make
    the whole map untrustworthy (rule 5). The walk names the count."""
    facts = _facts("void f() { g(); }")
    assert all(c.external and c.callee_id is None for c in facts.calls)


# ------------------------------------------------------------------- control --- #

def test_the_control_vocabulary_maps_without_inventing_an_arm_word():
    facts = _facts(
        "void f() {\n"
        "  for (auto& x : xs) { use(x); }\n"
        "  while (a) { b(); }\n"
        "  if (c) { d(); } else if (e) { g(); } else { h(); }\n"
        "  switch (k) { case 1: p(); break; default: q(); }\n"
        "  try { r(); } catch (const E& ex) { s(); }\n"
        "}")
    got = {(c.kind.value, c.word) for c in facts.control}
    assert ("LOOP", "for") in got
    assert ("LOOP", "while") in got
    assert ("DECISION", "if") in got
    assert ("DECISION", "switch") in got
    assert ("HANDLER", "try") in got
    arms = {a.kind.value for a in facts.control_arms}
    assert {"if", "else if", "else", "case", "default", "try", "catch"} <= arms


def test_a_range_for_records_its_container_as_the_once_span():
    """The one thing evaluated before the first pass — Python's `for x in y`, exactly.

    A three-clause `for` gets nothing: its init is arithmetic and its condition and
    increment run every pass, which is `while`'s shape.
    """
    ranged = _facts("void f() { for (auto& x : Items) { use(x); } }").control[0]
    assert ranged.once_start > 0
    three = _facts("void f() { for (int i = 0; i < n; ++i) { use(i); } }").control[0]
    assert (three.once_start, three.once_end) == (0, 0)


def test_a_short_if_that_leaves_is_a_guard():
    guard = _facts("void f() { if (!ok) { return; } work(); }").control[0]
    assert guard.kind.value == "GUARD"


def test_a_point_with_one_way_through_it_gets_no_arms():
    """The schema's own rule: an arm row is a choice that was recorded."""
    facts = _facts("void f() { if (x) { a(); } }")
    assert facts.control_arms == []


# ------------------------------------------------------------------- the file --- #

def test_the_probe_file_reads_as_a_whole_program():
    """The smallest real C++ in this repository, read end to end.

    It is the tree `tools/fingerprints.py` gates against, so if this stops being true the
    gate is comparing a stamp over an empty map — which is the nothing it exists to refuse
    (rule 37).
    """
    root = Path(__file__).resolve().parent / "fixtures" / "polyglot"
    facts = extract_file(root / "probe.cpp", root)
    assert facts.errors == []
    assert [r.qualname for r in facts.routines] == ["probe.LoadConfig", "main"]
    assert [e.kind.value for e in facts.entrypoints] == ["MAIN"]
    assert {b.kind.value for b in facts.boundaries} == {"FILE", "ENV", "STDIO"}
    assert [s.name for s in facts.structures] == ["Setting"]
    assert [c.name for c in facts.constants if c.name == "Retries"]
    assert {i.module for i in facts.imports} == {"cstdio", "cstdlib", "string", "vector"}


def _facts(src: str):
    """One in-memory file through the whole reader, so what is tested is what runs."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "m.cpp"
        path.write_text(src, encoding="utf-8")
        return extract_file(path, root)
