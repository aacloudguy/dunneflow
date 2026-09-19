"""Routines, records and constants — the things a program declares.

## The refusal this module is built on

**A declaration with no body is not a routine.** It is the single most consequential rule in
the C++ reader and it settles two problems at once.

It settles *what a header is*. Unreal has 51,282 `.h` files against 23,322 `.cpp`, and read
as declarations they would roughly double the map with rows that have nothing in them — the
same argument `.d.ts` won in the TypeScript reader, in a language where the header is not
the exception but the majority of the corpus. A signature is a promise about a routine; the
routine is the body.

And it settles *the header-and-`.cpp` double*, by dissolving it. The fear is that `Foo.h`'s
`void C::d();` and `Foo.cpp`'s `void C::d() {}` become two routines, and they cannot be made
one: `make_id` joins the parts it is given, `module` is per-file, and two files are two keys
by construction. What removes the problem is that the *declaration is not a routine at all*,
so the name is minted exactly once — wherever the body is, inline in the header or out of
line in the `.cpp`. There is never a pair to reconcile. `scopes.py` gives this for free: a
declaration ends at a `;` and opens no brace, so it never reaches the tree.

## Macros in declaration position are decorators, and their arguments are too

`UCLASS(Blueprintable)` and `UFUNCTION(BlueprintCallable, Category="Combat")` sit exactly
where a Python decorator sits and mean exactly what one means: *register this with something*
(rule 7). They are recorded in `Routine.decorators`.

**Each identifier-shaped argument becomes its own decorator string**, so `UFUNCTION(
BlueprintCallable, Category="Combat")` yields `["UFUNCTION", "BlueprintCallable",
"Category"]`. That is not cosmetic: `EntrypointRule.matches_decorator` tests a decorator's
*name* and has no `contains` form, so a rule can never match a substring of one long
argument string. Flattened, `BlueprintCallable` — which is a genuine way in, from Blueprint,
into C++ that nothing else calls — is unmatchable by any rule the detector grammar can
express. Split, it needs no new YAML key at all, and a bare `UFUNCTION()` correctly matches
nothing.

## What is deliberately not guessed at

A macro is recognised by *position*, never by shape: this module does not decide that
`GENERATED_BODY()` is boilerplate or that `UCLASS` is special. It records what is written
and `detectors/cpp.yaml` decides what any of it means.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Literal

from ...schema import (
    ClassDef_,
    Comment,
    Constant,
    DataStructure,
    Field_,
    Param,
    Routine,
    StructureKind,
    definition_id,
    hash_source,
)
from . import names
from .ctx import Ctx
from .lexer import Span
from .scopes import Scope, ScopeKind, declarator_span, walk
from .tokens import Token, TokenKind

# What a record keyword means in `StructureKind`. `union` has no member of its own and is
# a CLASS: the tool's vocabulary is about what a thing *is to a reader*, and a union is a
# shape with fields like the others.
_RECORD_KIND = {
    "class": StructureKind.CLASS,
    "struct": StructureKind.CLASS,
    "union": StructureKind.CLASS,
    "enum": StructureKind.ENUM,
}

_ACCESS = frozenset({"public", "private", "protected"})

# A body holding one of these is a coroutine. C++20's spelling, and the only way to tell
# from the outside: a coroutine is declared exactly like an ordinary function and is one
# because of what its body does.
_COROUTINE = frozenset({"co_await", "co_return", "co_yield"})

# Specifiers that may lead a constant declaration at namespace or class scope.
_CONST_LEAD = ("constexpr", "const", "constinit", "static")

_DOXYGEN = re.compile(r"^\s*(?:/\*+<?|\*+/?|///+<?|//+)\s?")


def read(ctx: Ctx) -> tuple[list[Routine], list[DataStructure], list[ClassDef_],
                            list[Constant]]:
    """Every routine, record and constant this file declares."""
    routines: list[Routine] = []
    structures: list[DataStructure] = []
    classes: list[ClassDef_] = []
    constants: list[Constant] = []
    # **Two tallies, because two tables have a unique id and both can collide.** A name can
    # be declared twice in one file — overloads, and both arms of an `#ifdef` read as live —
    # and that is true of a `struct` exactly as it is of a function. Routines were given the
    # ordinal first and structures were not, so the store refused the second `structures.id`
    # instead of the second `routines.id`: the same defect, one table over, and it took a
    # second run to see because the first one stopped before it got there.
    seen: dict[str, int] = {}
    seen_records: dict[str, int] = {}

    for scope in walk(ctx.root):
        if scope.kind is ScopeKind.FUNCTION:
            routines.append(_routine(ctx, scope, seen))
        elif scope.kind is ScopeKind.RECORD:
            struct, cls = _record(ctx, scope, seen_records)
            structures.append(struct)
            if cls is not None:
                classes.append(cls)
            if scope.record_word == "enum":
                constants.extend(_enum_members(ctx, scope))

    constants.extend(_scope_constants(ctx))
    return routines, structures, classes, constants


# ------------------------------------------------------------------ routines --- #

def _routine(ctx: Ctx, scope: Scope, seen: dict[str, int]) -> Routine:
    qualname = names.join(scope.qual_prefix(), scope.name)
    name = qualname.rsplit(".", 1)[-1]
    rec = scope.enclosing_record()

    # **The file is always part of a routine's identity, and working out why corrected an
    # assumption this reader was designed around.**
    #
    # The design said: fold the file in for internal linkage — `static`, or an anonymous
    # namespace — so two translation units' `Init` do not merge, and leave it out otherwise
    # so that a header's declaration and a `.cpp`'s definition land on one routine. The
    # second half was already wrong when it was written, and the module docstring above says
    # why without drawing the conclusion: **a declaration is not a routine**, so there is no
    # header-and-`.cpp` pair to merge. A routine is a body, a body is in exactly one file,
    # and the file therefore belongs in its identity exactly as a module does for Python.
    #
    # Left out, it is not merely unnecessary — it is wrong, and Unreal produced the proof
    # within one module. `Internal/IO/IoDispatcherFilesystemStats.h` gives its methods empty
    # inline bodies under one arm of an `#if`, and the `.cpp` defines them for real; both
    # arms are read as live (see `preprocessor.py`), so **221 qualnames in 400 files had a
    # body in two places** and the store refused the second with
    # `UNIQUE constraint failed: routines.id`.
    #
    # So there is no linkage question here at all. `Scope.is_internal` and a `static` check
    # were written for this and are gone with it: a distinction that decides nothing is a
    # constant that looks like a decision (rule 35).
    key = definition_id(ctx.path, qualname)
    n = seen.get(key, 0)
    seen[key] = n + 1
    # Two definitions of one name in one file -- overloads, or both arms of an `#ifdef`
    # read as live. Both are kept as separate identities rather than one replacing the
    # other, which is the mechanism Python's reader already uses for a colliding name.
    ident = definition_id(ctx.path, qualname, n + 1)

    start = ctx.tok_line(scope.open_tok)
    end = ctx.tok_line(scope.close_tok) if scope.close_tok >= 0 else start
    header_line = ctx.line(scope.header[0].start) if scope.header else start

    return Routine(
        id=ident,
        name=name,
        qualname=qualname,
        module=ctx.module,
        file=ctx.path,
        line_start=header_line,
        line_end=end,
        params=_params(ctx, scope.header),
        returns=_returns(scope.header),
        decorators=_decorators(scope.header),
        docstring=_leading_comment(ctx, scope),
        comments=_body_comments(ctx, scope),
        is_async=_is_coroutine(ctx, scope),
        is_method=rec is not None or "." in scope.name,
        class_name=(rec.name if rec is not None
                    else (scope.name.rsplit(".", 2)[-2] if "." in scope.name else None)),
        is_nested=any(s.kind is ScopeKind.FUNCTION for s in scope.ancestors()),
        visibility=_visibility(ctx, scope),
        body_hash=hash_source(ctx.slice(scope.open_tok, max(scope.close_tok, scope.open_tok))),
    )


def _params(ctx: Ctx, header: list[Token]) -> list[Param]:
    """The parameter list, as written.

    C++ writes `Type name = default`, which is the reverse of Python's, so the **last**
    identifier before a `,`, `)` or `=` is the name and everything before it is the type.
    An unnamed parameter — `void f(int)`, legal and common in overrides — gets an empty
    name rather than being dropped: it is a parameter, and a signature missing one is a
    signature about a different routine.
    """
    open_i = _param_open(header)
    if open_i is None:
        return []
    close_i = _matching(header, open_i)
    if close_i is None:
        return []
    out: list[Param] = []
    for group in _split_top(header, open_i + 1, close_i):
        if not group:
            continue
        if len(group) == 1 and group[0].text in ("void",):
            continue
        if group[0].kind is TokenKind.PUNCT and group[0].text == "...":
            out.append(Param(name="", type=None, default=None, kind="vararg"))
            continue
        eq = _top_index(group, "=")
        decl, default = (group[:eq], group[eq + 1:]) if eq is not None else (group, [])
        pname, ptype = _split_declarator(decl)
        out.append(Param(
            name=pname,
            type=ptype or None,
            default=_text(ctx, default) if default else None,
            kind="positional",
        ))
    return out


def _split_declarator(decl: list[Token]) -> tuple[str, str]:
    """`const FString& Name` -> ("Name", "const FString&"); `int` -> ("", "int")."""
    if not decl:
        return "", ""
    last = decl[-1]
    if last.kind is TokenKind.IDENT and len(decl) > 1 and last.text not in _TYPE_WORDS:
        return last.text, _raw(decl[:-1])
    return "", _raw(decl)


# Words that are a type all by themselves, so a run ending in one has no parameter name.
_TYPE_WORDS = frozenset({
    "int", "char", "bool", "float", "double", "void", "long", "short", "unsigned",
    "signed", "auto", "size_t", "wchar_t", "char8_t", "char16_t", "char32_t",
})


def _returns(header: list[Token]) -> str | None:
    """Everything between the specifiers and the declarator, which in C++ is the return type.

    `auto f() -> int` puts it after the parameters instead; both are recorded as written and
    neither is normalised, because this reader has nothing to normalise a type against.

    **Taken from `declarator_span` rather than by walking back from the `(`.** Walking back
    over "identifiers and `::`" reads `void AThing::Fire(` as returning `void AThing`,
    because the qualifier is made of exactly the tokens a return type is made of. The one
    walk that already knows where the name begins is the one that decides where it ends.

    Leading specifiers go: `static int Helper(` returns `int`. `static` is linkage, not a
    type, and leaving it in puts two different facts in one column.
    """
    arrow = _top_index(header, "->")
    if arrow is not None:
        return _raw(header[arrow + 1:]) or None
    span = declarator_span(header)
    if span is None:
        return None
    lead = _strip_macros(header[:span[0]])
    lead = [t for t in lead
            if not (t.kind is TokenKind.IDENT and t.text in _SPECIFIERS)]
    return _raw(lead) or None


def _strip_macros(toks: list[Token]) -> list[Token]:
    """Drop `MACRO(...)` invocations, which are annotations and not part of a type.

    The same runs `_decorators` collects, removed from the *other* reading of the same
    tokens — so `UFUNCTION(BlueprintCallable, Category="Combat") void Fire(` returns `void`
    rather than the annotation with the type stuck on the end. Two questions about one
    span, and the tokens can only belong to one of the answers.
    """
    out: list[Token] = []
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if (t.kind is TokenKind.IDENT and _looks_macro(t.text)
                and i + 1 < n and toks[i + 1].kind is TokenKind.PUNCT
                and toks[i + 1].text == "("):
            close = _matching(toks, i + 1)
            if close is not None:
                i = close + 1
                continue
        out.append(t)
        i += 1
    return out


# Linkage, storage and inline-ness. In front of a return type and not part of one.
_SPECIFIERS = frozenset({
    "static", "extern", "inline", "virtual", "explicit", "constexpr", "consteval",
    "constinit", "friend", "thread_local", "mutable", "export", "FORCEINLINE",
})


def _decorators(header: list[Token]) -> list[str]:
    """Macro invocations in declaration position, each argument its own entry.

    See the module docstring: split this way `BlueprintCallable` is matchable by the
    existing `decorator_method` grammar, and flattened it is matchable by nothing.

    Only identifier-shaped arguments are emitted. `Category="Combat"` contributes
    `Category` and not the string, because a rule matching a *value* would be matching the
    name of one game's damage type.
    """
    # **Only what is in front of the declarator.** Scanned over the whole header, a
    # macro-shaped call in a *default argument* becomes a decorator: `void Fire(const
    # FString& N = TEXT("x"))` would register `TEXT`, which is a string wrapper and not a
    # registration of anything. The annotations sit before the name; the parameters are
    # after it, and the span already knows where the line is.
    span = declarator_span(header)
    header = header[:span[0]] if span is not None else header
    out: list[str] = []
    i = 0
    n = len(header)
    while i < n:
        t = header[i]
        if t.kind is not TokenKind.IDENT or not _looks_macro(t.text):
            i += 1
            continue
        if i + 1 < n and header[i + 1].kind is TokenKind.PUNCT and header[i + 1].text == "(":
            close = _matching(header, i + 1)
            if close is None:
                i += 1
                continue
            out.append(t.text)
            for arg in header[i + 2:close]:
                if arg.kind is TokenKind.IDENT and arg.text not in out:
                    out.append(arg.text)
            i = close + 1
            continue
        i += 1
    return out


def _looks_macro(word: str) -> bool:
    """SCREAMING_SNAKE, which is how every C++ codebase spells a macro.

    A convention rather than a rule of the language, and stated as such: a macro spelled
    in lower case is not recognised here. It is the convention Unreal, the standard library
    and every corpus this tool has read all keep, and the alternative — treating every
    `name(...)` before a declaration as a decorator — would make a return type into one.
    """
    return word.isupper() and len(word) > 1 and "_" in word or (word.isupper() and len(word) > 2)


def _is_coroutine(ctx: Ctx, scope: Scope) -> bool:
    if scope.close_tok < 0:
        return False
    return any(t.kind is TokenKind.IDENT and t.text in _COROUTINE
               for t in ctx.toks[scope.open_tok:scope.close_tok])


def _visibility(ctx: Ctx, scope: Scope) -> Literal["public", "private"]:
    """`private` or `public`, from the access label in force where this routine sits.

    A `class` starts private and a `struct` starts public — the only difference between the
    two keywords in the language — and a label changes it for everything after it. Read by
    walking the enclosing record's direct tokens up to this scope's header, which is cheap
    and exact; guessing from the keyword alone would call every method of every class
    private.
    """
    rec = scope.enclosing_record()
    if rec is None or rec.open_tok < 0:
        return "public"
    vis = rec.default_visibility
    start = scope.header[0].start if scope.header else ctx.toks[scope.open_tok].start
    for i in range(rec.open_tok + 1, scope.open_tok):
        t = ctx.toks[i]
        if t.start >= start:
            break
        if (t.kind is TokenKind.IDENT and t.text in _ACCESS
                and i + 1 < len(ctx.toks) and ctx.toks[i + 1].text == ":"):
            vis = "private" if t.text in ("private", "protected") else "public"
    return "private" if vis == "private" else "public"


# ------------------------------------------------------------------- records --- #

def _record(ctx: Ctx, scope: Scope,
            seen: dict[str, int]) -> tuple[DataStructure, ClassDef_ | None]:
    qualname = scope.qual_prefix()
    name = scope.name or "<anonymous>"
    line = ctx.line(scope.header[0].start) if scope.header else ctx.tok_line(scope.open_tok)
    bases = _bases(scope.header)
    kind = _RECORD_KIND.get(scope.record_word, StructureKind.CLASS)
    key = definition_id(ctx.path, qualname or name)
    n = seen.get(key, 0)
    seen[key] = n + 1
    struct = DataStructure(
        id=definition_id(ctx.path, qualname or name, n + 1),
        name=name,
        kind=kind,
        module=ctx.module,
        file=ctx.path,
        line=line,
        fields=_fields(ctx, scope),
        docstring=_leading_comment(ctx, scope),
        bases=bases,
    )
    cls = None
    if kind is StructureKind.CLASS:
        cls = ClassDef_(name=name, qualname=qualname, module=ctx.module, file=ctx.path,
                        line=line, bases=bases)
    return struct, cls


def _bases(header: list[Token]) -> list[str]:
    """`: public AActor, private IThing` -> ["AActor", "IThing"].

    The access specifier is dropped and the name is kept: what a reader wants is what this
    inherits from, and `public` is a fact about the inheritance rather than about the base.
    """
    colon = _top_index(header, ":")
    if colon is None:
        return []
    out: list[str] = []
    for group in _split_top(header, colon + 1, len(header)):
        toks = [t for t in group
                if not (t.kind is TokenKind.IDENT and t.text in _ACCESS | {"virtual"})]
        if toks:
            folded, _ = names.fold_declarator(toks, 0)
            if folded:
                out.append(folded)
    return out


def _fields(ctx: Ctx, scope: Scope) -> list[Field_]:
    """Data members declared directly in this record's body.

    A member is a declaration ending in `;` that is not a function and not a nested type.
    Members of nested records belong to the nested record, so only the record's *direct*
    statements are read.
    """
    if scope.open_tok < 0 or scope.close_tok < 0:
        return []
    out: list[Field_] = []
    for group in _direct_statements(ctx, scope):
        if not group or _param_open(group) is not None:
            continue
        if any(t.kind is TokenKind.IDENT and t.text in ("using", "typedef", "friend")
               for t in group[:2]):
            continue
        eq = _top_index(group, "=")
        decl, default = (group[:eq], group[eq + 1:]) if eq is not None else (group, [])
        fname, ftype = _split_declarator(decl)
        if fname:
            out.append(Field_(name=fname, type=ftype or None,
                              default=_text(ctx, default) if default else None,
                              comment=None))
    return out


def _enum_members(ctx: Ctx, scope: Scope) -> list[Constant]:
    """An enumerator is a name with a value, which is what `Constant` is for (rule 19).

    A bare `Red` has no written value and keeps an empty one rather than being given the
    ordinal a compiler would assign: this reader does not evaluate, and an invented `0`
    would be a number nobody wrote.
    """
    if scope.open_tok < 0 or scope.close_tok < 0:
        return []
    inner = ctx.toks[scope.open_tok + 1:scope.close_tok]
    out: list[Constant] = []
    for group in _split_top(inner, 0, len(inner)):
        if not group or group[0].kind is not TokenKind.IDENT:
            continue
        eq = _top_index(group, "=")
        value = _text(ctx, group[eq + 1:]) if eq is not None else ""
        out.append(Constant(name=group[0].text, value=value,
                            line=ctx.line(group[0].start), is_final=True))
    return out


def _scope_constants(ctx: Ctx) -> list[Constant]:
    """`constexpr`/`const` declarations at namespace or class scope.

    Not inside a function body: a local `const int n = 3;` is the internal computation this
    tool exists not to report, and admitting it would put every loop bound in the map.
    """
    out: list[Constant] = []
    for scope in walk(ctx.root):
        if scope.kind not in (ScopeKind.FILE, ScopeKind.NAMESPACE, ScopeKind.RECORD):
            continue
        for group in _direct_statements(ctx, scope):
            if not group or _param_open(group) is not None:
                continue
            if not any(t.kind is TokenKind.IDENT and t.text in _CONST_LEAD
                       for t in group[:3]):
                continue
            if not any(t.kind is TokenKind.IDENT and t.text in ("constexpr", "const",
                                                                "constinit")
                       for t in group[:3]):
                continue
            eq = _top_index(group, "=")
            if eq is None:
                continue
            fname, ftype = _split_declarator(group[:eq])
            if not fname:
                continue
            out.append(Constant(name=fname, value=_text(ctx, group[eq + 1:]),
                                line=ctx.line(group[0].start), type=ftype or None,
                                is_final=True,
                                private=fname.startswith("_")))
    return out


# ------------------------------------------------------------------ comments --- #

def _leading_comment(ctx: Ctx, scope: Scope) -> str | None:
    """The comment block immediately above a declaration, stripped of its markers.

    This is what a C++ program has instead of a docstring, and it is the only place most
    of them say what a routine is for. Doxygen's four spellings — `/** */`, `/*! */`, `///`
    and `//!` — are all read, because which one a codebase uses is a house style and the
    prose is the same either way.

    Only a block that **touches** the declaration counts: one blank line between a comment
    and a function means the comment was about something else (rule 27, in prose).
    """
    if not scope.header:
        return None
    start = scope.header[0].start
    m = ctx.masked
    i = start - 1
    # Walk back over whitespace, allowing at most one newline: two means a gap.
    newlines = 0
    while i >= 0 and m.text[i] in " \t\r\n":
        if m.text[i] == "\n":
            newlines += 1
            if newlines > 1:
                return None
        i -= 1
    if i < 0 or m.kind[i] not in (Span.LINE_COMMENT, Span.BLOCK_COMMENT):
        return None
    end = i + 1
    while i >= 0 and (m.kind[i] in (Span.LINE_COMMENT, Span.BLOCK_COMMENT)
                      or m.text[i] in " \t\r\n"):
        if m.kind[i] is Span.CODE and m.text[i] == "\n":
            # A newline between two comment lines is fine; one before ordinary code is not.
            prev = i - 1
            while prev >= 0 and m.text[prev] in " \t":
                prev -= 1
            if prev >= 0 and m.kind[prev] not in (Span.LINE_COMMENT, Span.BLOCK_COMMENT):
                break
        i -= 1
    text = m.text[i + 1:end]
    return _strip_comment(text) or None


def _strip_comment(text: str) -> str:
    out = [_DOXYGEN.sub("", line).rstrip() for line in text.splitlines()]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out).strip()


def _body_comments(ctx: Ctx, scope: Scope) -> list[Comment]:
    """Every comment inside the body, with its line and whether it leads a statement.

    Rule 18's argument, one language over: a comment has to land on something, and the
    routine owns what no inner statement does. `leading` is True where the comment is the
    first thing on its line, which is how a reader tells a remark about the next statement
    from a note about this one.
    """
    if scope.open_tok < 0 or scope.close_tok < 0:
        return []
    m = ctx.masked
    lo = ctx.toks[scope.open_tok].start
    hi = ctx.toks[scope.close_tok].start
    out: list[Comment] = []
    i = lo
    while i < hi:
        if m.kind[i] in (Span.LINE_COMMENT, Span.BLOCK_COMMENT):
            j = i
            kind = m.kind[i]
            while j < hi and m.kind[j] is kind:
                j += 1
            text = _strip_comment(m.text[i:j])
            if text:
                line_start = m.text.rfind("\n", 0, i) + 1
                leading = not m.text[line_start:i].strip()
                out.append(Comment(text=text, line=m.line_at(i), leading=leading))
            i = j
            continue
        i += 1
    return out


# ------------------------------------------------------------------ plumbing --- #

def _direct_statements(ctx: Ctx, scope: Scope) -> Iterator[list[Token]]:
    """Each `;`-terminated run directly inside `scope`, skipping nested `{ … }` wholly."""
    if scope.kind is ScopeKind.FILE:
        lo, hi = 0, len(ctx.toks)
    elif scope.open_tok < 0 or scope.close_tok < 0:
        return
    else:
        lo, hi = scope.open_tok + 1, scope.close_tok
    run: list[Token] = []
    depth = 0
    i = lo
    while i < hi:
        t = ctx.toks[i]
        if t.kind is TokenKind.PUNCT and t.text == "{":
            depth += 1
            if depth == 1:
                run = []
        elif t.kind is TokenKind.PUNCT and t.text == "}":
            depth = max(0, depth - 1)
            if depth == 0:
                run = []
        elif depth == 0 and t.kind is TokenKind.PUNCT and t.text == ";":
            if run:
                yield run
            run = []
        elif depth == 0:
            run.append(t)
        i += 1


def _param_open(header: list[Token]) -> int | None:
    """Index of the `(` that opens the parameter list — `scopes.declarator_span`'s answer.

    It was a second copy of that walk, which is the shape rule 51 is about: the two agreed
    on every fixture and would have come apart on the first constructor whose initialiser
    list held a call.
    """
    span = declarator_span(header)
    return None if span is None else span[1]


def _matching(toks: list[Token], i: int) -> int | None:
    open_t = toks[i].text
    close_t = {"(": ")", "[": "]", "{": "}"}[open_t]
    depth = 0
    for j in range(i, len(toks)):
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == open_t:
                depth += 1
            elif t.text == close_t:
                depth -= 1
                if depth == 0:
                    return j
    return None


def _split_top(toks: list[Token], lo: int, hi: int) -> list[list[Token]]:
    """Split `toks[lo:hi]` on top-level commas."""
    out: list[list[Token]] = []
    cur: list[Token] = []
    depth = 0
    for i in range(lo, hi):
        t = toks[i]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([{<":
                depth += 1
            elif t.text in ")]}>":
                depth -= 1
            elif t.text == "," and depth == 0:
                out.append(cur)
                cur = []
                continue
        cur.append(t)
    out.append(cur)
    return out


def _top_index(toks: list[Token], want: str) -> int | None:
    depth = 0
    for i, t in enumerate(toks):
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text in "([{":
            depth += 1
        elif t.text in ")]}":
            depth -= 1
        elif t.text == want and depth == 0:
            return i
    return None


def _raw(toks: list[Token]) -> str:
    return " ".join(t.text for t in toks)


def _text(ctx: Ctx, toks: list[Token]) -> str:
    """As written, from the source — never joined back together from token texts."""
    if not toks:
        return ""
    a, b = toks[0], toks[-1]
    return ctx.text[a.start:b.start + len(b.text)].strip()
