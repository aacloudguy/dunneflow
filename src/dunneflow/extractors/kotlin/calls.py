"""Call sites, their arguments as written, and the boundaries the rules recognise.

Every call is **external** and no `callee_id` is ever set: `supplies_edges` is false because
resolving a Kotlin call needs types — extension functions are chosen by static receiver type,
and `apply`/`let`/`run`/`with` change what `this` means inside a block. A name-matched edge
would be wrong often enough to make the map untrustworthy (rule 5). The walk names the count,
which is the shippable state the architecture describes.

**Kotlin has named arguments and they are recorded.** `CallArg.keyword` carries `name =` where
the caller wrote one — the field Python fills and C++ structurally cannot, because C++ has no
such syntax. That is worth having: a boundary rule can name a `target_arg` by position, and a
reader looking at a call site can see which argument was which without counting.

**A trailing lambda is an argument.** `withContext(Dispatchers.IO) { … }` passes a block, and
the block is sliced as written like any other argument. It is not a second call and it is not
a routine.
"""

from __future__ import annotations

from collections.abc import Iterator

from ...detectors import RuleSet
from ...schema import BoundaryHit, BoundaryKind, CallArg, CallSite, Routine, call_site_id
from . import names
from .ctx import Ctx
from .scopes import Scope, ScopeKind
from .tokens import Token, TokenKind

# Followed by `(` and never a call. Without this every `if (x)` is a call to `if`.
_NOT_CALLS = frozenset({
    "if", "else", "while", "for", "do", "when", "try", "catch", "finally", "return",
    "throw", "is", "as", "in", "by", "fun", "val", "var", "class", "object", "interface",
    "init", "constructor", "super", "typeof",
})


def read(ctx: Ctx, rules: RuleSet, owners: dict[int, Routine]
         ) -> tuple[list[CallSite], list[BoundaryHit]]:
    calls: list[CallSite] = []
    boundaries: list[BoundaryHit] = []
    ordinals: dict[tuple[str, str], int] = {}

    for scope, owner in _bodies(ctx, owners):
        lo = scope.body_start + (1 if scope.braced else 0)
        hi = scope.body_end
        i = lo
        while i < hi:
            t = ctx.toks[i]
            if t.kind is not TokenKind.IDENT or t.text in _NOT_CALLS:
                i += 1
                continue
            made = _one(ctx, i, hi, owner, ordinals)
            if made is None:
                i += 1
                continue
            site, nxt = made
            calls.append(site)
            for rule in rules.boundaries:
                if not rule.matches_call(site.callee_expr):
                    continue
                target = ""
                if rule.target_arg is not None and rule.target_arg < len(site.args):
                    target = site.args[rule.target_arg].expr
                boundaries.append(BoundaryHit(
                    routine_id=owner.id, kind=rule.kind, direction=rule.direction,
                    target=target, line=site.line, evidence=site.callee_expr,
                    salience=rule.salience))
                # **A Unix-domain socket is not also the network.** Every other rule that
                # matches is its own fact here, and `java.net.` would make
                # `java.net.UnixDomainSocketAddress.of` NETWORK as well as LOCAL_IPC: two
                # numbers about one act (rule 40). So LOCAL_IPC, written first, ends it.
                if rule.kind is BoundaryKind.LOCAL_IPC:
                    break
            i = nxt
    return calls, boundaries


def _bodies(ctx: Ctx, owners: dict[int, Routine]) -> Iterator[tuple[Scope, Routine]]:
    """Each function scope with its routine. A nested function owns its own calls; a lambda
    does not exist here, so its calls belong to the function that encloses it."""
    for scope in _walk(ctx.root):
        owner = owners.get(scope.body_start)
        if owner is not None and scope.body_end >= 0:
            yield scope, owner


def _walk(scope: Scope) -> Iterator[Scope]:
    if scope.kind is ScopeKind.FUNCTION:
        yield scope
    for child in scope.children:
        yield from _walk(child)


def _one(ctx: Ctx, i: int, hi: int, owner: Routine,
         ordinals: dict[tuple[str, str], int]) -> tuple[CallSite, int] | None:
    toks = ctx.toks
    expr, j = names.fold_declarator(toks, i)
    if not expr or j >= hi:
        return None
    if toks[j].kind is not TokenKind.PUNCT or toks[j].text != "(":
        return None

    # Clause 2: the chain may continue through this call, and the arguments belong to the
    # **last** call in it — `Room.databaseBuilder(c).build()` passes nothing to `build`, and
    # taking the first parentheses would hand it `c`.
    full, end = names.fold(toks, i)
    pair = _last_top_call(toks, i, min(end, hi)) if full else None
    if full and pair is not None:
        expr, open_i, close = full, pair[0], pair[1]
    else:
        plain = names.matching(toks, j)
        if plain is None or plain >= hi:
            return None
        open_i, close = j, plain

    key = (owner.id, expr)
    n = ordinals.get(key, 0)
    ordinals[key] = n + 1
    return CallSite(
        caller_id=owner.id,
        callee_expr=expr,
        line=ctx.tok_line(i),
        external=True,
        site_id=call_site_id(owner.id, expr, n),
        args=_args(ctx, open_i, close),
        # **No `new` in Kotlin**, so this is False for every call. A constructor invocation
        # is spelled exactly like a function call and telling them apart needs a symbol
        # table (clause 7's structural absence, stated in `extract.RESIDUE`).
        is_construction=False,
    ), close + 1


def _last_top_call(toks: list[Token], i: int, end: int) -> tuple[int, int] | None:
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
    out: list[CallArg] = []
    for idx, group in enumerate(_split_top(ctx.toks, open_i + 1, close_i)):
        if not group:
            continue
        keyword = None
        # `name = value` at the top of an argument is a named argument — unless the `=` is
        # part of a comparison, which it cannot be, `==` being its own token.
        if (len(group) > 2 and group[0].kind is TokenKind.IDENT
                and group[1].kind is TokenKind.PUNCT and group[1].text == "="):
            keyword = group[0].text
            group = group[2:]
        splat = group[0].kind is TokenKind.PUNCT and group[0].text == "*"
        if splat:
            group = group[1:]
        if not group:
            continue
        a, b = group[0], group[-1]
        out.append(CallArg(idx=idx,
                           expr=ctx.text[a.start:b.start + len(b.text)].strip(),
                           keyword=keyword, splat=splat))
    return out


def _split_top(toks: list[Token], lo: int, hi: int) -> list[list[Token]]:
    out: list[list[Token]] = []
    cur: list[Token] = []
    depth = 0
    for i in range(lo, min(hi, len(toks))):
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
