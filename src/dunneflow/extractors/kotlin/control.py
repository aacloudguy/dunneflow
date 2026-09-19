"""Loops, decisions, guards and handlers — spans only, never judgements.

`resolve/shape.py` decides whether a point is a *subject* — whether something moves inside it
— generically, off rows joined by routine and line range, and never asks which language wrote
them. So this module's whole job is accurate spans, and that judgement is reused unmodified.

## `when` is Kotlin's own, and it maps onto `switch`'s vocabulary

`when (x) { 1 -> a(); else -> b() }` is a DECISION whose arms are its branches. `ArmKind.CASE`
and `ArmKind.DEFAULT` already exist for a `switch` and mean exactly this, so nothing is added
to the schema — a `when` branch is a case and its `else` is the default.

**A `when` with no subject is still a decision.** `when { a > 1 -> x(); else -> y() }` is
Kotlin's `if`/`else if` ladder written another way, and reading only the subject form would
miss half of them.

## Three things deliberately not recorded

* **`?:` and `?.`** — the elvis operator and the safe call are Kotlin's ternary, and an
  expression that chooses between two values is the arithmetic this tool exists not to
  report. The schema makes the same argument about Python's `IfExp`.
* **`COMPREHENSION`** — Kotlin has none. A zero population, named rather than silently absent.
* **`map`/`filter`/`forEach`** — a call, not a loop. A rate hidden inside `items.forEach { }`
  is invisible where the same rate written as a `for` is not, and in idiomatic Kotlin that is
  a **larger** residue than the equivalent in C++, because the functional form is the house
  style. Stated plainly in `extract.RESIDUE` rather than softened.
"""

from __future__ import annotations

from collections.abc import Iterator

from ...schema import ArmKind, ControlArm, ControlKind, ControlPoint, Routine, make_id
from . import names
from .ctx import Ctx
from .scopes import Scope, ScopeKind
from .tokens import TokenKind

_WORDS = frozenset({"for", "while", "do", "if", "when", "try"})
_EXITS = ("return", "throw", "continue", "break")
_GUARD_STATEMENTS = 2


def read(ctx: Ctx, owners: dict[int, Routine]) -> tuple[list[ControlPoint],
                                                        list[ControlArm]]:
    points: list[ControlPoint] = []
    arms: list[ControlArm] = []
    for scope in _functions(ctx.root):
        owner = owners.get(scope.body_start)
        if owner is None or scope.body_end < 0:
            continue
        lo = scope.body_start + (1 if scope.braced else 0)
        _scan(ctx, owner, lo, scope.body_end, 1, points, arms)
    return points, arms


def _functions(scope: Scope) -> Iterator[Scope]:
    if scope.kind is ScopeKind.FUNCTION:
        yield scope
    for child in scope.children:
        yield from _functions(child)


def _scan(ctx: Ctx, owner: Routine, lo: int, hi: int, depth: int,
          points: list[ControlPoint], arms: list[ControlArm]) -> None:
    toks = ctx.toks
    i = lo
    while i < hi:
        t = toks[i]
        if t.kind is not TokenKind.IDENT or t.text not in _WORDS:
            i += 1
            continue
        if t.text == "if" and i > lo and toks[i - 1].text == "else":
            i += 1                       # an arm of the ladder above, already counted
            continue

        end, body_lo, body_hi = _span(ctx, i, hi)
        kind, my_arms = _shape(ctx, i, hi)
        point_id = make_id(owner.id, str(ctx.tok_line(i)), t.text, str(len(points)))
        points.append(ControlPoint(
            point_id=point_id, routine_id=owner.id, kind=kind,
            line_start=ctx.tok_line(i), line_end=ctx.tok_line(min(end, hi - 1)),
            depth=depth, header=_header(ctx, i, hi), arms=max(1, len(my_arms)),
            exits=_exits(ctx, body_lo, body_hi), word=t.text,
            once_start=_once(ctx, i, hi)[0], once_end=_once(ctx, i, hi)[1],
        ))
        for idx, (arm_kind, a_lo, a_hi, head) in enumerate(my_arms):
            arms.append(ControlArm(
                point_id=point_id, routine_id=owner.id, idx=idx, kind=arm_kind,
                line_start=ctx.tok_line(a_lo), line_end=ctx.tok_line(min(a_hi, hi - 1)),
                header=head))
        if body_lo < body_hi:
            _scan(ctx, owner, body_lo, min(body_hi, hi), depth + 1, points, arms)
        i = max(end + 1, i + 1)


def _shape(ctx: Ctx, i: int, hi: int) -> tuple[ControlKind, list]:
    word = ctx.toks[i].text
    if word in ("for", "while", "do"):
        return ControlKind.LOOP, []
    if word == "try":
        return ControlKind.HANDLER, _try_arms(ctx, i, hi)
    if word == "when":
        return ControlKind.DECISION, _when_arms(ctx, i, hi)
    arms = _if_arms(ctx, i, hi)
    if len(arms) <= 1 and _is_guard(ctx, i, hi):
        return ControlKind.GUARD, []
    return ControlKind.DECISION, arms


def _if_arms(ctx: Ctx, i: int, hi: int) -> list:
    toks = ctx.toks
    out: list = []
    cur = i
    kind = ArmKind.IF
    while cur < hi:
        end, _, _ = _span(ctx, cur, hi)
        out.append((kind, cur, end, _header(ctx, cur, hi)))
        nxt = end + 1
        if nxt < hi and toks[nxt].kind is TokenKind.IDENT and toks[nxt].text == "else":
            after = nxt + 1
            if after < hi and toks[after].text == "if":
                kind = ArmKind.ELSE_IF
                cur = after
                continue
            e_end, _, _ = _span(ctx, after, hi)
            out.append((ArmKind.ELSE, nxt, e_end, "else"))
        break
    return out if len(out) > 1 else []


def _when_arms(ctx: Ctx, i: int, hi: int) -> list:
    """One arm per `->` branch, and `else` is the default.

    Branches are found by their arrow rather than by their condition, because a condition can
    be a comma-separated list, a range, an `is` check or a bare expression — five shapes with
    one thing in common.
    """
    toks = ctx.toks
    _, body_lo, body_hi = _span(ctx, i, hi)
    out: list = []
    depth = 0
    start = body_lo
    for j in range(body_lo, min(body_hi, hi)):
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([{":
                depth += 1
            elif t.text in ")]}":
                depth -= 1
            elif t.text == "->" and depth == 0:
                is_else = any(x.kind is TokenKind.IDENT and x.text == "else"
                              for x in toks[start:j])
                out.append((ArmKind.DEFAULT if is_else else ArmKind.CASE,
                            start, j, ctx.slice(start, j)))
                nxt = _arm_end(ctx, j + 1, min(body_hi, hi))
                start = nxt
    return out


def _arm_end(ctx: Ctx, i: int, hi: int) -> int:
    toks = ctx.toks
    depth = 0
    for j in range(i, hi):
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([{":
                depth += 1
            elif t.text in ")]}":
                depth -= 1
        if depth == 0 and j > i and ctx.line(t.start) > ctx.line(toks[j - 1].start):
            return j
    return hi


def _try_arms(ctx: Ctx, i: int, hi: int) -> list:
    toks = ctx.toks
    end, _, _ = _span(ctx, i, hi)
    out = [(ArmKind.TRY, i, end, "try")]
    cur = end + 1
    while cur < hi and toks[cur].kind is TokenKind.IDENT and toks[cur].text in ("catch",
                                                                               "finally"):
        kind = ArmKind.CATCH if toks[cur].text == "catch" else ArmKind.FINALLY
        c_end, _, _ = _span(ctx, cur, hi)
        out.append((kind, cur, c_end, _header(ctx, cur, hi)))
        cur = c_end + 1
    return out


def _is_guard(ctx: Ctx, i: int, hi: int) -> bool:
    _, lo, body_hi = _span(ctx, i, hi)
    if lo >= body_hi:
        return False
    body = ctx.toks[lo:min(body_hi, hi)]
    statements = sum(1 for t in body if t.kind is TokenKind.PUNCT and t.text == ";")
    lines = {ctx.line(t.start) for t in body}
    if max(statements, len(lines) - 1) > _GUARD_STATEMENTS:
        return False
    return any(t.kind is TokenKind.IDENT and t.text in _EXITS for t in body)


def _exits(ctx: Ctx, lo: int, hi: int) -> str:
    found: list[str] = []
    for t in ctx.toks[lo:min(hi, len(ctx.toks))]:
        if t.kind is TokenKind.IDENT and t.text in _EXITS and t.text not in found:
            found.append(t.text)
    return ",".join(found)


def _once(ctx: Ctx, i: int, hi: int) -> tuple[int, int]:
    """`for (x in items)` — the container, evaluated once before the first pass.

    Kotlin has only this form of `for`, so unlike C++ there is no three-clause variant to
    tell it from: every `for` here has a once span, and that is the language rather than a
    choice this reader made.
    """
    toks = ctx.toks
    if toks[i].text != "for" or i + 1 >= hi or toks[i + 1].text != "(":
        return 0, 0
    close = names.matching(toks, i + 1)
    if close is None:
        return 0, 0
    for k in range(i + 2, close):
        if toks[k].kind is TokenKind.IDENT and toks[k].text == "in":
            return ctx.tok_line(k + 1), ctx.tok_line(close - 1)
    return 0, 0


def _span(ctx: Ctx, i: int, hi: int) -> tuple[int, int, int]:
    """Where a control statement ends, and where its body begins and ends."""
    toks = ctx.toks
    j = i + 1
    if j < hi and toks[j].kind is TokenKind.PUNCT and toks[j].text == "(":
        close = names.matching(toks, j)
        if close is None:
            return min(i + 1, hi - 1), i + 1, i + 1
        j = close + 1
    if j < hi and toks[j].kind is TokenKind.PUNCT and toks[j].text == "{":
        close = names.matching(toks, j)
        if close is None:
            return hi - 1, j + 1, hi
        return close, j + 1, close
    # An unbraced body: `if (x) return`. Runs to the end of its line.
    end = j
    while end + 1 < hi and ctx.line(toks[end + 1].start) == ctx.line(toks[j].start):
        end += 1
    return end, j, end + 1


def _header(ctx: Ctx, i: int, hi: int) -> str:
    """The statement's header **as written** — never normalised.

    `web/threads.py` compares decision headers as strings to find routines branching on the
    same test, and its blind spot (`x == 1` and `x==1` are two values) is stated there.
    Normalising here would quietly change what that thread means.
    """
    toks = ctx.toks
    j = i + 1
    if j < hi and toks[j].kind is TokenKind.PUNCT and toks[j].text == "(":
        close = names.matching(toks, j)
        if close is not None:
            return ctx.slice(i, close)
    return toks[i].text
