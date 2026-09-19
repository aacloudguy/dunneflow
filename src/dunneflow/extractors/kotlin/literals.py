"""Every string this file spells out, reported and never judged.

`ingest/literals.py` decides in the host, for every language at once, whether a string is
SQL, a filename or nothing — which is what stops one string being read two ways in a `.kt`
and a `.cpp` (rule 51, in the fact contract).

**Kotlin is the first reader with something true to put in `LiteralKind.INTERPOLATED`.**
`"$name"` and `"${expr}"` carry code inside a literal, so the text reported is not a constant
the program ever holds — it is a template. Python's f-string is the same shape and the field
was made for it; C++ has no interpolation at all and reports `PLAIN` for everything, which is
a structural absence rather than an unwritten rule.
"""

from __future__ import annotations

from collections.abc import Iterator

from ...schema import LiteralKind, Routine, StringLiteral, definition_id
from .ctx import Ctx
from .lexer import Span
from .scopes import Scope

_STRING_SPANS = (Span.STRING, Span.RAW_STRING)

# Three, not six: six is SQL's own floor and would put a four-character filename outside
# the map. The host measured this when the literal split was made.
_MIN = 3


def read(ctx: Ctx, owners: dict[int, Routine],
         module_scope: Routine) -> tuple[list[StringLiteral], int]:
    m = ctx.masked
    out: list[StringLiteral] = []
    dropped = 0
    ranges = _owner_ranges(ctx, owners)
    i, n = 0, len(m.text)
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
                kind=(LiteralKind.INTERPOLATED if i in m.interpolations
                      else LiteralKind.PLAIN),
            ))
        else:
            dropped += 1
        i = j
    return out, dropped


def _body(raw: str, kind: Span) -> str:
    """Contents without the delimiters. Escapes are **not** processed: what the host matches
    against is the text in the file, and a decoded string is one nobody wrote."""
    if kind is Span.RAW_STRING:
        return raw[3:-3] if len(raw) >= 6 and raw.endswith('"""') else raw.strip('"')
    return raw.strip('"')


def _owner_ranges(ctx: Ctx, owners: dict[int, Routine]) -> list[tuple[int, int, Routine]]:
    out: list[tuple[int, int, Routine]] = []
    for scope in _all(ctx.root):
        owner = owners.get(scope.body_start)
        if owner is None or scope.body_end < 0:
            continue
        out.append((ctx.toks[scope.body_start].start,
                    ctx.toks[scope.body_end].start, owner))
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
    """The file's own scope, **prepared and not claimed** — `FileFacts.module_scope`'s shape.

    A file's module scope is a routine only where something belongs to it. Minting it on
    demand is what invented 65 routines when the literal split was first made.
    """
    return Routine(
        id=definition_id(ctx.path, f"{ctx.module}.<module>" if ctx.module else "<module>"),
        name="<module>",
        qualname=f"{ctx.module}.<module>" if ctx.module else "<module>",
        module=ctx.module,
        file=ctx.path,
        line_start=1,
        line_end=max(1, len(ctx.masked.line_starts)),
    )


def module_scope_used(ctx: Ctx, owners: dict[int, Routine]) -> bool:
    ranges = _owner_ranges(ctx, owners)
    m = ctx.masked
    for i, span in enumerate(m.kind):
        if span in _STRING_SPANS and not any(lo <= i <= hi for lo, hi, _ in ranges):
            return True
    return False
