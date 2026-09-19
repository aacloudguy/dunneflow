"""Loops, decisions, guards and handlers — as spans, and never as judgements.

`resolve/shape.py` states the rule once and applies it to every language: *a loop or a
decision is a subject only where something moves inside it*. That judgement is host-side,
runs generically over `ControlPoint`/`ControlArm` rows joined against `boundaries`,
`sql_ops`, `net_calls` and `calls` by routine and line range, and **never asks which
language produced the rows**. So this module's whole job is accurate spans, and it is reused
unmodified.

## Mapping C++ onto a vocabulary that already fits it

| C++ | kind | arms |
|---|---|---|
| `for (a; b; c)` | LOOP `for` | — |
| `for (auto& x : xs)` | LOOP `for` | the container is the `once` span |
| `while (c)` | LOOP `while` | — |
| `do { } while (c)` | LOOP `do` | `ArmKind.DO`, and no second arm |
| `if` / `else if` / `else` | DECISION | `IF`, `ELSE_IF`, `ELSE` |
| `switch` | DECISION | `CASE` per label, `DEFAULT` |
| `try` / `catch` | HANDLER | `TRY`, `CATCH` |

`ArmKind.ELSE_IF` already exists because *"TypeScript has no `elif`: it writes `else if`"* —
C++ writes the same two words, so the same arm kind applies with nothing added.

**`catch` is C++'s own keyword** and `ArmKind.CATCH` is already there, so no arm word is
invented. There is no `finally` and no `else` on a `try` in this language: those two arm
kinds simply never appear, which is a stated absence rather than a filter.

## Three things deliberately not recorded

* **The ternary `?:`**, on the schema's own reasoning about Python's `IfExp`: *an expression
  that chooses between two numbers is the arithmetic this tool exists not to report*.
* **`COMPREHENSION`**, which has no C++ syntax at all — a zero population, named rather than
  silently absent.
* **An STL algorithm.** `std::for_each(v.begin(), v.end(), f)` is a call, not a loop, and no
  synthetic point is minted for one. A per-element rate hidden inside `std::transform` is
  therefore invisible where the same rate written as a range-`for` is not. Unreal's own style
  strongly favours the range-`for`, which is why this is a secondary residue and not a
  primary one — but it is a residue, and it is in `extract.RESIDUE`.
"""

from __future__ import annotations

from collections.abc import Iterator

from ...schema import (
    ArmKind,
    ControlArm,
    ControlKind,
    ControlPoint,
    Routine,
    make_id,
)
from .ctx import Ctx
from .scopes import Scope, ScopeKind
from .tokens import Token, TokenKind

_LOOP_WORDS = {"for", "while", "do"}
_DECISION_WORDS = {"if", "switch"}

# What makes a one-armed `if` a guard rather than a decision: the arm leaves.
_EXITS = ("return", "throw", "continue", "break", "goto", "co_return")

# A guard's body is short. Two statements, which is the same bound Python's reader uses and
# is what separates *refuse and leave* from *do the work in the other branch*.
_GUARD_STATEMENTS = 2


def read(ctx: Ctx, owners: dict[int, Routine]) -> tuple[list[ControlPoint],
                                                        list[ControlArm]]:
    points: list[ControlPoint] = []
    arms: list[ControlArm] = []
    for scope in _function_scopes(ctx.root):
        owner = owners.get(scope.open_tok)
        if owner is None:
            continue
        lo = scope.open_tok + 1
        hi = scope.close_tok if scope.close_tok >= 0 else len(ctx.toks)
        _scan(ctx, owner, lo, hi, depth=1, points=points, arms=arms)
    return points, arms


def _function_scopes(scope: Scope) -> Iterator[Scope]:
    if scope.kind is ScopeKind.FUNCTION:
        yield scope
        return
    for child in scope.children:
        yield from _function_scopes(child)


def _scan(ctx: Ctx, owner: Routine, lo: int, hi: int, depth: int,
          points: list[ControlPoint], arms: list[ControlArm]) -> None:
    """Every control point between `lo` and `hi`, and then the ones inside each of them.

    **`depth` counts enclosing control points and not braces.** `resolve/shape.py` reads
    `in_loop` rather than `depth > 1` precisely because a loop written inside an `if` has
    depth 2 and is nested in nothing; the number here has to mean the same thing it means
    for Python or the two corpora cannot be compared.
    """
    toks = ctx.toks
    i = lo
    while i < hi:
        t = toks[i]
        if t.kind is not TokenKind.IDENT:
            i += 1
            continue
        word = t.text

        if word == "else":
            i += 1                       # consumed as an arm of the `if` that owns it
            continue

        if word in _LOOP_WORDS or word in _DECISION_WORDS or word == "try":
            end, body_lo, body_hi = _statement_span(ctx, i, hi)
            kind, my_arms = _shape(ctx, i, end, hi)
            point_id = make_id(owner.id, str(ctx.tok_line(i)), word,
                               str(len(points)))
            once_start, once_end = _once(ctx, i, hi)
            points.append(ControlPoint(
                point_id=point_id,
                routine_id=owner.id,
                kind=kind,
                line_start=ctx.tok_line(i),
                line_end=ctx.tok_line(min(end, hi - 1)),
                depth=depth,
                header=_header_text(ctx, i, hi),
                arms=max(1, len(my_arms)),
                exits=_exits(ctx, body_lo, body_hi),
                word=word,
                once_start=once_start,
                once_end=once_end,
            ))
            for idx, (arm_kind, a_lo, a_hi, a_head) in enumerate(my_arms):
                arms.append(ControlArm(
                    point_id=point_id, routine_id=owner.id, idx=idx, kind=arm_kind,
                    line_start=ctx.tok_line(a_lo),
                    line_end=ctx.tok_line(min(a_hi, hi - 1)),
                    header=a_head,
                ))
            if body_lo < body_hi:
                _scan(ctx, owner, body_lo, min(body_hi, hi), depth + 1, points, arms)
            i = end + 1
            continue
        i += 1


def _shape(ctx: Ctx, i: int, end: int, hi: int
           ) -> tuple[ControlKind, list[tuple[ArmKind, int, int, str]]]:
    """The kind, and one entry per arm. A point with one way through it gets no arms.

    `ControlArm` rows exist only where a point has more than one way through it — the
    schema's own rule — so a `while` and a `do` produce none.
    """
    toks = ctx.toks
    word = toks[i].text
    if word in ("while", "for"):
        return ControlKind.LOOP, []
    if word == "do":
        return ControlKind.LOOP, []
    if word == "try":
        return ControlKind.HANDLER, _try_arms(ctx, i, hi)
    if word == "switch":
        return ControlKind.DECISION, _switch_arms(ctx, i, hi)
    arms = _if_arms(ctx, i, hi)
    if len(arms) <= 1 and _is_guard(ctx, i, hi):
        return ControlKind.GUARD, []
    return ControlKind.DECISION, arms


def _if_arms(ctx: Ctx, i: int, hi: int) -> list[tuple[ArmKind, int, int, str]]:
    """`if` / `else if` / `else`, flattened exactly as Python's `elif` chain is.

    `else if` is structurally a nested `if` inside the `else`, which is the identical tree
    shape the Python reader's ladder already handles — and `ArmKind.ELSE_IF` exists because
    TypeScript spells it the same two words.
    """
    toks = ctx.toks
    out: list[tuple[ArmKind, int, int, str]] = []
    cur = i
    kind = ArmKind.IF
    while cur < hi:
        end, body_lo, body_hi = _statement_span(ctx, cur, hi)
        out.append((kind, cur, end, _header_text(ctx, cur, hi)))
        nxt = end + 1
        while nxt < hi and toks[nxt].kind is TokenKind.PUNCT and toks[nxt].text == ";":
            nxt += 1
        if nxt < hi and toks[nxt].kind is TokenKind.IDENT and toks[nxt].text == "else":
            after = nxt + 1
            if after < hi and toks[after].kind is TokenKind.IDENT and toks[after].text == "if":
                kind = ArmKind.ELSE_IF
                cur = after
                continue
            e_end, _, _ = _statement_span(ctx, after, hi)
            out.append((ArmKind.ELSE, nxt, e_end, "else"))
        break
    # **A point with one way through it gets no arms**, which is the schema's own rule and
    # not an economy: an arm row is a *choice* that was recorded, and a bare `if` with no
    # `else` offers none. Returned as written first, which put one arm row under every
    # unbranched `if` in the corpus — 54 rows for 48 points on one Unreal file.
    return out if len(out) > 1 else []


def _switch_arms(ctx: Ctx, i: int, hi: int) -> list[tuple[ArmKind, int, int, str]]:
    """One arm per `case` and per `default`, label to label.

    Spans run from one label to the next regardless of fallthrough: a `ControlArm` is *a
    span, and nothing more*, never a reachability claim.
    """
    toks = ctx.toks
    _, body_lo, body_hi = _statement_span(ctx, i, hi)
    out: list[tuple[ArmKind, int, int, str]] = []
    marks: list[tuple[ArmKind, int]] = []
    depth = 0
    for j in range(body_lo, min(body_hi, hi)):
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == "{":
                depth += 1
            elif t.text == "}":
                depth -= 1
            continue
        if depth != 0 or t.kind is not TokenKind.IDENT:
            continue
        if t.text == "case":
            marks.append((ArmKind.CASE, j))
        elif t.text == "default":
            marks.append((ArmKind.DEFAULT, j))
    for n, (kind, start) in enumerate(marks):
        stop = marks[n + 1][1] - 1 if n + 1 < len(marks) else min(body_hi, hi) - 1
        out.append((kind, start, max(start, stop), _header_text(ctx, start, hi)))
    return out


def _try_arms(ctx: Ctx, i: int, hi: int) -> list[tuple[ArmKind, int, int, str]]:
    toks = ctx.toks
    end, _, _ = _statement_span(ctx, i, hi)
    out = [(ArmKind.TRY, i, end, "try")]
    cur = end + 1
    while cur < hi and toks[cur].kind is TokenKind.IDENT and toks[cur].text == "catch":
        c_end, _, _ = _statement_span(ctx, cur, hi)
        out.append((ArmKind.CATCH, cur, c_end, _header_text(ctx, cur, hi)))
        cur = c_end + 1
    return out


def _is_guard(ctx: Ctx, i: int, hi: int) -> bool:
    """A short one-armed `if` whose arm leaves: *refuse and return*, not *decide*."""
    _, lo, body_hi = _statement_span(ctx, i, hi)
    if lo >= body_hi:
        return False
    body = ctx.toks[lo:min(body_hi, hi)]
    statements = sum(1 for t in body if t.kind is TokenKind.PUNCT and t.text == ";")
    if statements > _GUARD_STATEMENTS:
        return False
    return any(t.kind is TokenKind.IDENT and t.text in _EXITS for t in body)


def _exits(ctx: Ctx, lo: int, hi: int) -> str:
    """The words this point's body leaves by, as written.

    `throw` is recorded as the word, which the field allows: `ControlPoint.exits` is a free
    string and not an enum, so C++'s vocabulary needs nothing added to the schema.
    """
    found: list[str] = []
    for t in ctx.toks[lo:min(hi, len(ctx.toks))]:
        if t.kind is TokenKind.IDENT and t.text in _EXITS and t.text not in found:
            found.append(t.text)
    return ",".join(found)


def _once(ctx: Ctx, i: int, hi: int) -> tuple[int, int]:
    """The range-`for` container's line span: the one thing evaluated before the first pass.

    Exactly analogous to Python's `for x in y`. A three-clause `for` gets `0, 0` — its init
    is arithmetic and its condition and increment run every pass, which is `while`'s shape.
    """
    toks = ctx.toks
    if toks[i].text != "for":
        return 0, 0
    j = i + 1
    if j >= hi or toks[j].text != "(":
        return 0, 0
    close = _matching(toks, j, hi)
    if close is None:
        return 0, 0
    depth = 0
    for k in range(j + 1, close):
        t = toks[k]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([{":
                depth += 1
            elif t.text in ")]}":
                depth -= 1
            elif t.text == ";" and depth == 0:
                return 0, 0          # a three-clause `for`
            elif t.text == ":" and depth == 0:
                return ctx.tok_line(k + 1), ctx.tok_line(close - 1)
    return 0, 0


def _statement_span(ctx: Ctx, i: int, hi: int) -> tuple[int, int, int]:
    """Where a control statement ends, and where its body begins and ends.

    Returns `(end, body_lo, body_hi)`. A braced body spans its braces; an unbraced one —
    `if (x) return;` — spans to its `;`, which is a real body and is read as one.
    """
    toks = ctx.toks
    j = i + 1
    if j < hi and toks[j].kind is TokenKind.PUNCT and toks[j].text == "(":
        close = _matching(toks, j, hi)
        if close is None:
            return min(i + 1, hi - 1), i + 1, i + 1
        j = close + 1
    if j < hi and toks[j].kind is TokenKind.PUNCT and toks[j].text == "{":
        close = _matching_brace(toks, j, hi)
        if close is None:
            return hi - 1, j + 1, hi
        return close, j + 1, close
    # An unbraced body runs to the next `;` at this level.
    depth = 0
    for k in range(j, hi):
        t = toks[k]
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text in "([{":
            depth += 1
        elif t.text in ")]}":
            depth -= 1
        elif t.text == ";" and depth == 0:
            return k, j, k
    return max(j, i), j, min(j, hi)


def _matching(toks: list[Token], i: int, hi: int) -> int | None:
    depth = 0
    for j in range(i, min(len(toks), hi)):
        t = toks[j]
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text == "(":
            depth += 1
        elif t.text == ")":
            depth -= 1
            if depth == 0:
                return j
    return None


def _matching_brace(toks: list[Token], i: int, hi: int) -> int | None:
    depth = 0
    for j in range(i, min(len(toks), hi + 1)):
        t = toks[j]
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text == "{":
            depth += 1
        elif t.text == "}":
            depth -= 1
            if depth == 0:
                return j
    return None


def _header_text(ctx: Ctx, i: int, hi: int) -> str:
    """The statement's header **as written**, which is what the ribbon shows a reader.

    Never normalised: `web/threads.py` compares decision headers as strings to find routines
    branching on the same test, and its own blind spot — `x == 1` and `x==1` are two values —
    is stated there. Normalising here would quietly change what that thread means.
    """
    toks = ctx.toks
    j = i + 1
    if j < hi and toks[j].kind is TokenKind.PUNCT and toks[j].text == "(":
        close = _matching(toks, j, hi)
        if close is not None:
            return ctx.slice(i, close)
    return toks[i].text
