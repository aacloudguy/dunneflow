"""Every string this file spells out, reported and never judged.

`FileFacts.literals` is the seam the string-literal split created: a reader says **what
strings are there** and `ingest/literals.py` decides, in the host and for every language at
once, whether one is SQL, a filename, a glob or nothing at all. That is what keeps
`detectors/<lang>.yaml` an extension point a plugin never has to be rebuilt for, and it is
what stops one string being read two ways in a `.cpp` and a `.ts` — rule 51 in the fact
contract, which is the most expensive place to have it.

So this module decides nothing. It finds the spans the lexer already marked and hands them
over with their owner and their line.

**A raw string is a `PLAIN` literal.** `LiteralKind` tells a plain string from an
interpolation placeholder, and C++ has no interpolation: `R"json({"k":1})json"` is a string
whose contents happen to be JSON, and its delimiters are not part of it. `printf`'s `%s` is
a *runtime* format and not syntax — the string is exactly what is in the file — so nothing
here is `INTERPOLATED`, which is a structural absence rather than an unwritten rule.

A concatenation — `"a" "b"` — is two literals here and one string to a compiler. Reported as
written, because joining them would invent a string that appears nowhere in the file (rule
8's argument, one direction over).
"""

from __future__ import annotations

from collections.abc import Iterator

from ...schema import LiteralKind, Routine, StringLiteral
from .ctx import Ctx
from .lexer import Span
from .scopes import Scope

# The two spans that are a string. A char literal is not one: `'x'` is a number with a
# spelling, and admitting it would put every `'\n'` in the corpus into the literal table.
_STRING_SPANS = (Span.STRING, Span.RAW_STRING)

# Below this a string cannot be a fact worth the payload. **Three, not six** — six is SQL's
# own floor and would put a four-character filename outside the map, which the host measured
# when the split was made.
_MIN = 3


def read(ctx: Ctx, owners: dict[int, Routine],
         module_scope: Routine) -> tuple[list[StringLiteral], int]:
    """Every literal, attributed to the routine it sits in, and how many were dropped.

    A string outside any routine belongs to the **module scope**, which is prepared and not
    yet claimed: `ingest.literals.judge` claims it if one of these turns out to be a fact.
    A reader cannot know that — what a string *means* is the host's answer — which is
    exactly why the scope is prepared here rather than minted on demand. Minting it on
    demand is what invented 65 routines when the split was first made.
    """
    m = ctx.masked
    out: list[StringLiteral] = []
    dropped = 0
    ranges = _owner_ranges(ctx, owners)

    i = 0
    n = len(m.text)
    while i < n:
        if m.kind[i] not in _STRING_SPANS:
            i += 1
            continue
        kind = m.kind[i]
        j = i
        while j < n and m.kind[j] is kind:
            j += 1
        text = _body(m.text[i:j], kind)
        if len(text) >= _MIN:
            out.append(StringLiteral(
                routine_id=_owner_at(ranges, i, module_scope).id,
                line=m.line_at(i),
                text=text,
                kind=LiteralKind.PLAIN,
            ))
        else:
            dropped += 1
        i = j
    return out, dropped


def _body(raw: str, kind: Span) -> str:
    """The string's contents, without its quotes or its raw delimiter.

    Escapes are **not** processed: `"a\\nb"` is reported with the backslash in it, because
    what the host matches against is the text in the file and a reader that decoded it
    would hand `ingest.literals` a string nobody wrote.
    """
    if kind is Span.RAW_STRING:
        open_paren = raw.find("(")
        close = raw.rfind(")")
        if 0 <= open_paren < close:
            return raw[open_paren + 1:close]
        return raw
    body = raw
    if body.startswith(("u8", "u", "U", "L", "R")):
        body = body[body.find('"'):] if '"' in body else body
    return body.strip('"')


def _owner_ranges(ctx: Ctx, owners: dict[int, Routine]) -> list[tuple[int, int, Routine]]:
    """Offset ranges for every routine body, innermost last.

    Sorted by width so `_owner_at` can take the narrowest match — the same innermost-span
    rule `web/search.py` uses to decide which scope a line belongs to (rule 10).
    """
    out: list[tuple[int, int, Routine]] = []
    for scope in _all(ctx.root):
        owner = owners.get(scope.open_tok)
        if owner is None or scope.close_tok < 0:
            continue
        lo = ctx.toks[scope.open_tok].start
        hi = ctx.toks[scope.close_tok].start
        out.append((lo, hi, owner))
    out.sort(key=lambda r: r[1] - r[0], reverse=True)
    return out


def _all(scope: Scope) -> Iterator[Scope]:
    yield scope
    for child in scope.children:
        yield from _all(child)


def _owner_at(ranges: list[tuple[int, int, Routine]], offset: int,
              module_scope: Routine) -> Routine:
    found = module_scope
    for lo, hi, owner in ranges:
        if lo <= offset <= hi:
            found = owner
    return found


def module_routine(ctx: Ctx) -> Routine:
    """The file's own scope, **prepared and not claimed**.

    A file's module scope is a routine only where something belongs to it. This builds the
    row so the host can claim it if a string turns out to be a fact, and leaves it out of
    `routines` otherwise — the shape `FileFacts.module_scope` documents, and the one that
    stops a file with a stray string at the top from growing a routine nobody wrote.
    """
    from ...schema import definition_id
    return Routine(
        id=definition_id(
            ctx.path, f"{ctx.module}.<module>" if ctx.module else "<module>"),
        name="<module>",
        qualname=f"{ctx.module}.<module>" if ctx.module else "<module>",
        module=ctx.module,
        file=ctx.path,
        line_start=1,
        line_end=max(1, len(ctx.masked.line_starts)),
    )


def module_scope_used(ctx: Ctx, owners: dict[int, Routine]) -> bool:
    """Is there any work at file scope for the module routine to own?

    Only the things this reader records as belonging to a routine count — a call or a
    literal outside every body. A `#include` is a fact about the file rather than about a
    routine, so a file that is nothing but includes does not grow a scope.
    """
    ranges = _owner_ranges(ctx, owners)
    m = ctx.masked
    for i, span in enumerate(m.kind):
        if span in _STRING_SPANS and not any(lo <= i <= hi for lo, hi, _ in ranges):
            return True
    return False

