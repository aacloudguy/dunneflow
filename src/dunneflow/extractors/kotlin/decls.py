"""Routines, types and constants — what a Kotlin file declares.

## Identity includes the file, and it always did here

The C++ reader arrived at that after Unreal refused a write; Kotlin starts there, for the
simpler reason that a Kotlin file states its own `package` and two files in one package can
each declare a top-level `fun render()`. The package is in the qualname because it is what
the author wrote and how the function is addressed; the file is in the id because that is
where the body is.

## A primary constructor is where a data class keeps its fields

    data class SmallWidgetStatus(
        val dueCardsCount: Int,
        val eta: Int,
    )

There is no body at all, and every field is in the parameter list — so a reader that looks
for fields inside braces finds none, on the shape Kotlin uses for every value type it has.
Only `val`/`var` parameters are fields: a plain constructor parameter is an argument, not a
property, and the language is explicit about the difference.
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
    hash_source,
    make_id,
)
from . import names
from .ctx import Ctx
from .lexer import Span
from .scopes import Scope, ScopeKind, annotations_of, walk
from .tokens import Token, TokenKind

_KDOC = re.compile(r"^\s*(?:/\*+|\*+/?|//+)\s?")

# `data` and `value` classes are shapes a reader is meant to see through; `enum` is its own
# kind; everything else is a class. An `interface` is INTERFACE, which the schema has.
_STRUCTURE_KIND = {
    "interface": StructureKind.INTERFACE,
    "object": StructureKind.CLASS,
    "class": StructureKind.CLASS,
}


def read(ctx: Ctx) -> tuple[list[Routine], list[DataStructure], list[ClassDef_],
                            list[Constant]]:
    routines: list[Routine] = []
    structures: list[DataStructure] = []
    classes: list[ClassDef_] = []
    constants: list[Constant] = []
    seen: dict[str, int] = {}
    seen_types: dict[str, int] = {}

    for scope in walk(ctx.root):
        if scope.kind is ScopeKind.FUNCTION:
            routines.append(_routine(ctx, scope, seen))
        elif scope.kind is ScopeKind.TYPE:
            struct, cls = _type(ctx, scope, seen_types)
            structures.append(struct)
            if cls is not None:
                classes.append(cls)
            if "enum" in scope.modifiers:
                constants.extend(_enum_members(ctx, scope))
    constants.extend(_constants(ctx))
    return routines, structures, classes, constants


def _routine(ctx: Ctx, scope: Scope, seen: dict[str, int]) -> Routine:
    qualname = names.join(names.join(ctx.package, scope.qual_prefix()), scope.name)
    name = scope.name.rsplit(".", 1)[-1]
    enclosing = scope.enclosing_type()

    key = make_id(ctx.path, qualname)
    n = seen.get(key, 0)
    seen[key] = n + 1
    # Overloads, and two declarations of one name. Kept as separate identities rather than
    # one silently replacing the other.
    ident = key if n == 0 else make_id(ctx.path, qualname, f"#{n + 1}")

    header_line = ctx.line(scope.header[0].start) if scope.header else 1
    return Routine(
        id=ident,
        name=name,
        qualname=qualname,
        module=ctx.module,
        file=ctx.path,
        line_start=header_line,
        line_end=ctx.tok_line(scope.body_end) if scope.body_end >= 0 else header_line,
        params=_params(ctx, scope.header),
        returns=_returns(ctx, scope.header),
        decorators=annotations_of(scope.header),
        docstring=_leading_comment(ctx, scope),
        comments=_body_comments(ctx, scope),
        # **`suspend` is Kotlin's async**, and it is a modifier rather than something in the
        # body: a suspending function is one the compiler rewrites, and the keyword is the
        # only place that is stated.
        is_async="suspend" in scope.modifiers,
        is_method=enclosing is not None,
        class_name=enclosing.name if enclosing is not None else None,
        is_nested=any(s.kind is ScopeKind.FUNCTION for s in scope.ancestors()),
        visibility=_visibility(scope),
        body_hash=hash_source(ctx.slice(scope.body_start, scope.body_end)
                              if scope.body_start >= 0 else ""),
    )


def _visibility(scope: Scope) -> Literal["public", "private"]:
    """Kotlin is public by default and says so with a keyword when it is not.

    `internal` and `protected` are recorded as private: the schema has two values, and what
    both of those mean to a reader is *not part of the surface*.
    """
    if scope.modifiers & {"private", "internal", "protected"}:
        return "private"
    return "public"


def _params(ctx: Ctx, header: list[Token]) -> list[Param]:
    """`name: Type = default`, which is the reverse of C++ and the same as Python's."""
    open_i = _param_open(header)
    if open_i is None:
        return []
    close_i = names.matching(header, open_i)
    if close_i is None:
        return []
    out: list[Param] = []
    for group in _split_top(header, open_i + 1, close_i):
        group = [t for t in group
                 if not (t.kind is TokenKind.IDENT and t.text in ("val", "var", "vararg"))]
        if not group or group[0].kind is not TokenKind.IDENT:
            continue
        eq = _top_index(group, "=")
        decl, default = (group[:eq], group[eq + 1:]) if eq is not None else (group, [])
        colon = _top_index(decl, ":")
        out.append(Param(
            name=decl[0].text,
            type=_text(ctx, decl[colon + 1:]) if colon is not None else None,
            default=_text(ctx, default) if default else None,
            kind="positional",
        ))
    return out


def _returns(ctx: Ctx, header: list[Token]) -> str | None:
    """The type after the parameter list's `)`. Absent means `Unit`, and is left absent.

    Kotlin infers a return type where it is not written, and writing `Unit` in for it would
    be this reader asserting something the file does not say.
    """
    open_i = _param_open(header)
    if open_i is None:
        return None
    close_i = names.matching(header, open_i)
    if close_i is None or close_i + 1 >= len(header):
        return None
    rest = header[close_i + 1:]
    if not rest or rest[0].kind is not TokenKind.PUNCT or rest[0].text != ":":
        return None
    return _text(ctx, rest[1:]) or None


def _type(ctx: Ctx, scope: Scope,
          seen: dict[str, int]) -> tuple[DataStructure, ClassDef_ | None]:
    qualname = names.join(ctx.package, scope.qual_prefix())
    kind = (StructureKind.ENUM if "enum" in scope.modifiers
            else _STRUCTURE_KIND.get(scope.type_word, StructureKind.CLASS))
    key = make_id(ctx.path, qualname)
    n = seen.get(key, 0)
    seen[key] = n + 1
    line = ctx.line(scope.header[0].start) if scope.header else 1
    bases = _bases(ctx, scope)
    struct = DataStructure(
        id=key if n == 0 else make_id(ctx.path, qualname, f"#{n + 1}"),
        name=scope.name,
        kind=kind,
        module=ctx.module,
        file=ctx.path,
        line=line,
        fields=_fields(ctx, scope),
        docstring=_leading_comment(ctx, scope),
        bases=bases,
        annotations=[],
    )
    cls = None
    if kind is not StructureKind.ENUM:
        cls = ClassDef_(name=scope.name, qualname=qualname, module=ctx.module,
                        file=ctx.path, line=line, bases=bases)
    return struct, cls


def _bases(ctx: Ctx, scope: Scope) -> list[str]:
    """`: Base(), IThing` — the supertype list, which sits after the primary constructor."""
    toks = ctx.toks
    start = scope.header[-1].start if scope.header else None
    if start is None:
        return []
    i = next((k for k, t in enumerate(toks) if t.start == start), None)
    if i is None:
        return []
    i += 1
    if i >= len(toks) or toks[i].kind is not TokenKind.PUNCT or toks[i].text != ":":
        return []
    stop = scope.body_start if scope.body_start >= 0 else len(toks)
    out: list[str] = []
    for group in _split_top(toks, i + 1, stop):
        if group:
            folded, _ = names.fold_declarator(group, 0)
            if folded:
                out.append(folded)
    return out


def _fields(ctx: Ctx, scope: Scope) -> list[Field_]:
    """Primary-constructor properties, and `val`/`var` declared in the body.

    Only `val`/`var` constructor parameters are properties — a plain parameter is an
    argument the constructor uses and forgets, and the language is explicit about which is
    which.
    """
    out: list[Field_] = []
    open_i = _param_open(scope.header)
    if open_i is not None:
        close_i = names.matching(scope.header, open_i)
        if close_i is not None:
            for group in _split_top(scope.header, open_i + 1, close_i):
                if not any(t.kind is TokenKind.IDENT and t.text in ("val", "var")
                           for t in group):
                    continue
                body = [t for t in group if not (t.kind is TokenKind.IDENT
                                                 and t.text in ("val", "var"))]
                if body and body[0].kind is TokenKind.IDENT:
                    colon = _top_index(body, ":")
                    eq = _top_index(body, "=")
                    stop = eq if eq is not None else len(body)
                    out.append(Field_(
                        name=body[0].text,
                        type=_text(ctx, body[colon + 1:stop]) if colon is not None else None,
                        default=_text(ctx, body[eq + 1:]) if eq is not None else None,
                        comment=None))
    for group in _direct_statements(ctx, scope):
        if not group or group[0].kind is not TokenKind.IDENT:
            continue
        lead = [t.text for t in group[:4] if t.kind is TokenKind.IDENT]
        if not ({"val", "var"} & set(lead)):
            continue
        body = [t for t in group if not (t.kind is TokenKind.IDENT
                                         and t.text in _DECL_MODS)]
        if body and body[0].kind is TokenKind.IDENT:
            colon = _top_index(body, ":")
            eq = _top_index(body, "=")
            stop = eq if eq is not None else len(body)
            out.append(Field_(
                name=body[0].text,
                type=_text(ctx, body[colon + 1:stop]) if colon is not None else None,
                default=_text(ctx, body[eq + 1:]) if eq is not None else None,
                comment=None))
    return out


_DECL_MODS = frozenset({
    "val", "var", "const", "private", "public", "internal", "protected", "override",
    "lateinit", "open", "abstract", "final",
})


def _enum_members(ctx: Ctx, scope: Scope) -> list[Constant]:
    """`enum class Mode { FAST, SLOW }` — each name is a constant (rule 19).

    A bare member has no written value and keeps an empty one rather than the ordinal a
    compiler would assign: this reader does not evaluate.
    """
    if scope.body_start < 0:
        return []
    inner = ctx.toks[scope.body_start + 1:scope.body_end]
    out: list[Constant] = []
    for group in _split_top(inner, 0, len(inner)):
        if not group or group[0].kind is not TokenKind.IDENT:
            continue
        if group[0].text in _DECL_MODS or group[0].text in ("fun", "class", "object"):
            break                    # past the members, into the body
        out.append(Constant(name=group[0].text, value="",
                            line=ctx.line(group[0].start), is_final=True))
    return out


def _constants(ctx: Ctx) -> list[Constant]:
    """`const val` at file or object scope — a name with a value, which is what a constant is.

    **`const` only, and that is precision rather than thrift.** Every `val` in Kotlin is an
    immutable *binding*, including a local one inside a function and a property computed per
    instance; `const val` is the one that is a compile-time constant with a literal value.
    Admitting every `val` would put every local binding in the corpus into the constants
    table, which is the internal computation this tool exists not to report.
    """
    out: list[Constant] = []
    for scope in walk(ctx.root):
        if scope.kind is ScopeKind.FUNCTION:
            continue
        for group in _direct_statements(ctx, scope):
            words = [t.text for t in group[:4] if t.kind is TokenKind.IDENT]
            if "const" not in words or "val" not in words:
                continue
            body = [t for t in group
                    if not (t.kind is TokenKind.IDENT and t.text in _DECL_MODS)]
            eq = _top_index(body, "=")
            if eq is None or not body or body[0].kind is not TokenKind.IDENT:
                continue
            colon = _top_index(body[:eq], ":")
            out.append(Constant(
                name=body[0].text,
                value=_text(ctx, body[eq + 1:]),
                line=ctx.line(body[0].start),
                type=_text(ctx, body[colon + 1:eq]) if colon is not None else None,
                is_final=True,
                private=body[0].text.startswith("_"),
            ))
    return out


def _leading_comment(ctx: Ctx, scope: Scope) -> str | None:
    """The KDoc block immediately above a declaration, stripped of its markers.

    Only a block that **touches** the declaration counts: one blank line between a comment
    and a function means the comment was about something else.
    """
    if not scope.header:
        return None
    m = ctx.masked
    i = scope.header[0].start - 1
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
        i -= 1
    return _strip(m.text[i + 1:end]) or None


def _strip(text: str) -> str:
    out = [_KDOC.sub("", line).rstrip() for line in text.splitlines()]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out).strip()


def _body_comments(ctx: Ctx, scope: Scope) -> list[Comment]:
    if scope.body_start < 0 or scope.body_end < 0:
        return []
    m = ctx.masked
    lo = ctx.toks[scope.body_start].start
    hi = ctx.toks[scope.body_end].start
    out: list[Comment] = []
    i = lo
    while i < hi:
        if m.kind[i] in (Span.LINE_COMMENT, Span.BLOCK_COMMENT):
            kind = m.kind[i]
            j = i
            while j < hi and m.kind[j] is kind:
                j += 1
            text = _strip(m.text[i:j])
            if text:
                line_start = m.text.rfind("\n", 0, i) + 1
                out.append(Comment(text=text, line=m.line_at(i),
                                   leading=not m.text[line_start:i].strip()))
            i = j
            continue
        i += 1
    return out


def _direct_statements(ctx: Ctx, scope: Scope) -> Iterator[list[Token]]:
    """Each statement directly inside `scope`, skipping nested braces wholly.

    **Kotlin has no statement terminator**, so a statement ends at a newline that nothing
    carries across — the same question `scopes._expression_end` answers, asked of a simpler
    population: these are declarations, and a declaration's continuation lines all begin
    with something that cannot start one.
    """
    if scope.kind is ScopeKind.FILE:
        lo, hi = 0, len(ctx.toks)
    elif scope.body_start < 0 or scope.body_end < 0:
        return
    else:
        lo, hi = scope.body_start + 1, scope.body_end
    run: list[Token] = []
    depth = 0
    for i in range(lo, hi):
        t = ctx.toks[i]
        if t.kind is TokenKind.PUNCT and t.text in "{([":
            depth += 1
        elif t.kind is TokenKind.PUNCT and t.text in "})]":
            depth -= 1
            if depth < 0:
                break
        if depth == 0 and run and t.kind is not TokenKind.PUNCT:
            prev = ctx.toks[i - 1]
            if (ctx.line(t.start) > ctx.line(prev.start)
                    and not (prev.kind is TokenKind.PUNCT and prev.text in ("=", ",", "("))):
                yield run
                run = []
        if depth == 0 and t.kind is TokenKind.PUNCT and t.text == ";":
            if run:
                yield run
            run = []
            continue
        if depth <= 1:
            run.append(t)
    if run:
        yield run


def _param_open(header: list[Token]) -> int | None:
    depth = 0
    for i, t in enumerate(header):
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text == "<":
            depth += 1
        elif t.text == ">":
            depth -= 1
        elif t.text == "(" and depth == 0:
            return i
    return None


def _split_top(toks: list[Token], lo: int, hi: int) -> list[list[Token]]:
    out: list[list[Token]] = []
    cur: list[Token] = []
    depth = 0
    for i in range(lo, min(hi, len(toks))):
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
        if t.text in "([{<":
            depth += 1
        elif t.text in ")]}>":
            depth -= 1
        elif t.text == want and depth == 0:
            return i
    return None


def _text(ctx: Ctx, toks: list[Token]) -> str:
    if not toks:
        return ""
    a, b = toks[0], toks[-1]
    return ctx.text[a.start:b.start + len(b.text)].strip()
