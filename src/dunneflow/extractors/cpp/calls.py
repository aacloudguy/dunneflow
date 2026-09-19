"""Call sites, their arguments as written, and the boundaries the rules recognise.

## Every call is external, and that is a state rather than a gap

`supplies_edges` is `false` and no `callee_id` is ever set. A C++ call cannot be resolved
without types — three overloads of `Foo` are one written name — and this reader has no
types. The architecture already describes this as shippable: a language with no resolver has
every call left external and is **named with its count**, which is what the walk prints.
What is refused is guessing, because a name-matched edge in a language with overloading,
ADL and `using` declarations would be wrong often enough to make the whole map untrustworthy
(rule 5, with the volume turned up).

## Arguments are sliced, never re-rendered

`CallArg.expr` is a byte slice of the spliced source (rules 8 and 75), so what a panel shows
is findable in the file a reader opens. There is no unparser here to re-render with, which
means the rule enforces itself.

## The one shape that is recognised without being parsed

`std::cout << x` is a boundary and is not call-shaped: no parentheses, so nothing in the
`exact`/`prefix`/`method`/`contains` grammar can reach it, and inventing a match primitive
for one operator is not worth a change to a file every language shares. So a short fixed
list of stream objects is recognised **here, in code**, on the precedent
`extract.py:_maybe_registration` sets in the Python reader: a *shape* lives in code, a *name*
lives in YAML.

## What is refused: the most vexing parse

`std::ifstream f(path);` is a construction that opens a file; `int x(5);` is a variable; and
`Foo x;` is another. They are the same syntax, and telling them apart needs a symbol table.
So a `TYPE name(args);` statement is read as a construction **only where the type is one the
boundary rules already name** — the allow-list discipline `python.yaml`'s artefact extensions
already use. Outside it, nothing is recognised, and that is in `extract.RESIDUE`.
"""

from __future__ import annotations

from collections.abc import Iterator

from ...detectors import RuleSet
from ...schema import (
    BoundaryHit,
    BoundaryKind,
    CallArg,
    CallSite,
    Direction,
    Routine,
    call_site_id,
)
from . import names
from .ctx import Ctx
from .scopes import CONTROL_WORDS, Scope, ScopeKind
from .tokens import Token, TokenKind

# Written with `<<` and `>>` rather than parentheses, so no rule in the grammar can reach
# them. See the module docstring.
_STREAMS = {
    "std.cout": Direction.OUT,
    "std.cerr": Direction.OUT,
    "std.clog": Direction.OUT,
    "std.wcout": Direction.OUT,
    "std.wcerr": Direction.OUT,
    "std.cin": Direction.IN,
    "std.wcin": Direction.IN,
}

# Keywords that are followed by `(` and are not calls. Without this every `if (x)` in the
# corpus is a call to a routine named `if`, and `sizeof(T)` is a call to `sizeof`.
_NOT_CALLS = CONTROL_WORDS | {
    "sizeof", "alignof", "alignas", "decltype", "typeid", "noexcept", "static_assert",
    "return", "throw", "new", "delete", "and", "or", "not", "catch", "requires",
    "static_cast", "dynamic_cast", "const_cast", "reinterpret_cast",
}


def read(ctx: Ctx, rules: RuleSet, owners: dict[int, Routine]
         ) -> tuple[list[CallSite], list[BoundaryHit]]:
    """Every call in every routine, and the boundaries the rules recognise in them.

    `owners` maps a scope's `open_tok` to the routine it produced, so a call found at a
    token index can be attributed without a second walk of the tree.
    """
    calls: list[CallSite] = []
    boundaries: list[BoundaryHit] = []
    ordinals: dict[tuple[str, str], int] = {}

    for scope, owner in _bodies(ctx, owners):
        lo = scope.open_tok + 1
        hi = scope.close_tok if scope.close_tok >= 0 else len(ctx.toks)
        i = lo
        while i < hi:
            t = ctx.toks[i]
            if t.kind is not TokenKind.IDENT:
                i += 1
                continue
            if t.text in _NOT_CALLS:
                # `new Foo(...)` is a construction and the name after it is the callee
                # (clause 7). The keyword itself is never the call.
                if t.text == "new":
                    made = _one(ctx, i + 1, hi, owner, ordinals, construction=True)
                    if made is not None:
                        site, nxt = made
                        calls.append(site)
                        boundaries.extend(_boundaries(ctx, rules, owner, site))
                        i = nxt
                        continue
                i += 1
                continue
            made = _one(ctx, i, hi, owner, ordinals, construction=False)
            if made is None:
                i += 1
                continue
            site, nxt = made
            calls.append(site)
            boundaries.extend(_boundaries(ctx, rules, owner, site))
            i = nxt
        boundaries.extend(_streams(ctx, owner, lo, hi))

    return calls, boundaries


def _bodies(ctx: Ctx, owners: dict[int, Routine]) -> Iterator[tuple[Scope, Routine]]:
    """Each routine scope paired with its routine, innermost work attributed correctly.

    A lambda is **not** a routine (Python's reader mints nothing for `lambda` either), so
    the calls inside one are attributed to the named routine that encloses it — the same
    residue Python already accepts for the body of an `if`. What that costs is that two
    lambdas in one routine put their calls in one flat list, which is stated rather than
    hidden.
    """
    for scope in _walk(ctx.root):
        owner = owners.get(scope.open_tok)
        if owner is not None:
            yield scope, owner


def _walk(scope: Scope) -> Iterator[Scope]:
    if scope.kind is ScopeKind.FUNCTION:
        yield scope
        return                      # inner blocks belong to this routine, not their own
    for child in scope.children:
        yield from _walk(child)


def _one(ctx: Ctx, i: int, hi: int, owner: Routine,
         ordinals: dict[tuple[str, str], int], *, construction: bool
         ) -> tuple[CallSite, int] | None:
    """One call beginning at token `i`, or `None` if there is not one there."""
    toks = ctx.toks
    expr, j = names.fold_declarator(toks, i)
    if not expr or j >= hi:
        return None
    if toks[j].kind is not TokenKind.PUNCT or toks[j].text != "(":
        return None
    close = _matching(toks, j, hi)
    if close is None:
        return None

    # Clause 2: the chain may continue through this call — `Get().Delete(x)`. The
    # **outermost** call is the one recorded, with the whole folded chain as its callee,
    # which is what the rules are written against.
    #
    # And the arguments belong to the **last** call in the chain, not the first. Taking
    # them from `j` — the parentheses the fold happened to start at — sliced from `Get()`'s
    # `(` to `FileExists(...)`'s `)`, so every chained boundary on Unreal recorded a target
    # of `').FileExists(*InPath'`: a string that is in the file, starts mid-expression, and
    # is not an argument to anything.
    full, end = names.fold(toks, i)
    if full and end > close:
        pair = _last_top_call(toks, i, min(end, hi))
        if pair is not None:
            expr, j, close = full, pair[0], pair[1]

    key = (owner.id, expr)
    n = ordinals.get(key, 0)
    ordinals[key] = n + 1
    site = CallSite(
        caller_id=owner.id,
        callee_expr=expr,
        line=ctx.tok_line(i),
        external=True,
        site_id=call_site_id(owner.id, expr, n),
        args=_args(ctx, j, close),
        is_construction=construction,
    )
    return site, close + 1


def _last_top_call(toks: list[Token], i: int, end: int) -> tuple[int, int] | None:
    """The outermost-chain's final `(`…`)` pair, as token indices.

    Only pairs that open at depth zero count: the arguments of the last call, not of one
    nested inside an argument of it.
    """
    depth = 0
    opened = -1
    last: tuple[int, int] | None = None
    for k in range(i, end):
        t = toks[k]
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text == "(":
            if depth == 0:
                opened = k
            depth += 1
        elif t.text == ")":
            depth -= 1
            if depth == 0 and opened >= 0:
                last = (opened, k)
    return last


def _args(ctx: Ctx, open_i: int, close_i: int) -> list[CallArg]:
    """What the caller wrote, sliced from the source and never shortened (rule 8).

    C++ has no keyword arguments, so `CallArg.keyword` is always `None` — a structural
    absence rather than a rule nobody wrote, and stated in `extract.RESIDUE`. A pack
    expansion `args...` sets `splat`, which is the nearest true thing the field says.
    """
    out: list[CallArg] = []
    for idx, group in enumerate(_split_top(ctx.toks, open_i + 1, close_i)):
        if not group:
            continue
        splat = group[-1].kind is TokenKind.PUNCT and group[-1].text == "..."
        body = group[:-1] if splat else group
        if not body:
            continue
        a, b = body[0], body[-1]
        out.append(CallArg(
            idx=idx,
            expr=ctx.text[a.start:b.start + len(b.text)].strip(),
            keyword=None,
            splat=splat,
        ))
    return out


def _boundaries(ctx: Ctx, rules: RuleSet, owner: Routine,
                site: CallSite) -> list[BoundaryHit]:
    out: list[BoundaryHit] = []
    for rule in rules.boundaries:
        if not rule.matches_call(site.callee_expr):
            continue
        target = ""
        if rule.target_arg is not None and rule.target_arg < len(site.args):
            target = site.args[rule.target_arg].expr
        out.append(BoundaryHit(
            routine_id=owner.id,
            kind=rule.kind,
            direction=rule.direction,
            target=target,
            line=site.line,
            evidence=site.callee_expr,
            salience=rule.salience,
        ))
    return out


def _streams(ctx: Ctx, owner: Routine, lo: int, hi: int) -> list[BoundaryHit]:
    """`std::cout << x` and its four siblings, matched on shape because they have none.

    Recorded once per statement rather than once per `<<`: `cout << a << b << c` is one
    write, and counting the operators would say three things move where one does (rule 32).
    """
    out: list[BoundaryHit] = []
    seen_line = -1
    i = lo
    while i < hi:
        expr, j = names.fold_declarator(ctx.toks, i)
        direction = _STREAMS.get(expr) if expr else None
        if direction is not None and j < hi and ctx.toks[j].text in ("<<", ">>"):
            line = ctx.tok_line(i)
            if line != seen_line:
                seen_line = line
                out.append(BoundaryHit(
                    routine_id=owner.id,
                    kind=BoundaryKind.STDIO,
                    direction=direction,
                    target="",
                    line=line,
                    evidence=expr,
                    salience="low",
                ))
            i = j + 1
            continue
        i = max(j, i + 1)
    return out


def _matching(toks: list[Token], i: int, hi: int) -> int | None:
    depth = 0
    for j in range(i, min(len(toks), hi + 1)):
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


def _split_top(toks: list[Token], lo: int, hi: int) -> list[list[Token]]:
    out: list[list[Token]] = []
    cur: list[Token] = []
    depth = 0
    for i in range(lo, hi):
        t = toks[i]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([{":
                depth += 1
            elif t.text in ")]}":
                depth -= 1
            elif t.text == "," and depth == 0:
                out.append(cur)
                cur = []
                continue
        cur.append(t)
    out.append(cur)
    return out
