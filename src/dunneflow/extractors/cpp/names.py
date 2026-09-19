"""How this reader spells a name, and it spells one in exactly one place.

`ingest/dotted.py` is the contract every rule in every `detectors/*.yaml` is matched
against, and it is the real interface between a reader and the rules: a plugin that spells
expressions differently does not fail, it makes every rule *miss*, and the map comes back
with no boundaries, no ways in and no CLI — looking exactly like a program that has none.

**Three callers and one function** (rule 51). The scope stack joins namespace and class
names into a prefix; a definition's written `A::B::C::d` is folded the same way; and a call
expression's callee is folded the same way again. Written three times they drift, and the
drift is invisible: a qualname built one way and a callee folded another simply never
resolve to each other, which reads as a program whose parts do not call each other.

## The contract, in C++

Clause by clause, from `ingest/dotted.py`:

1. **A source-order identifier chain, dot-joined.** C++ spells the separator three ways and
   all three fold to `.`: `A::b` is scope resolution, `p->q` is through a pointer, `o.f` is
   through a value. They are different *acts* and the same *name*, which is what the
   contract asks for — a rule matching `FFileHelper.SaveStringToFile` has to fire whether
   the code wrote `FFileHelper::SaveStringToFile` or reached it through a reference.
2. **A call in the middle folds to its callee.** `IFileManager::Get().Delete()` becomes
   `IFileManager.Get.Delete`, which is how the commonest Unreal file boundary is written
   and would otherwise be invisible to every rule.
3. **No name at the root gives `""`**, and `""` is never matched. A subscript, a literal, a
   cast, a call on something anonymous — anywhere in the chain, not only at its root.
5. **Nullability is not identity** — nothing to do in C++, which has no `?.`.
6. **Type arguments are not part of the name.** `TArray<FString>::Add` is `TArray.Add`, and
   `MakeShared<FThing>()` is `MakeShared`. Without this every templated call in the corpus
   is a name nothing matches, and in Unreal that is most of them.
7. **`new Foo()` folds to `Foo`, and the construction is recorded separately.**
   `CallSite.is_construction` carries the other half, because `new FSocket(x)` and
   `FSocket(x)` are two facts and flattening them is rule 30.
8. **The receiver word is written as written** — `this`, declared in the manifest.

Clause 4 is *no resolution and no alias expansion*, which this reader could not violate if
it wanted to: it has no symbol table. A `using namespace` is therefore invisible and a name
is whatever the author typed, which is what the rules are written against anyway (rule 5).

## Where the angle brackets are genuinely hard, and what is refused

`<` is a comparison operator and a template bracket, and telling them apart needs types.
This folds a `<…>` group only where it **opens directly after an identifier with no
intervening whitespace-separated operator**, and where the group balances before the
statement ends. `a < b && c > d` does not balance as a template argument list across a `;`,
so it is left alone. The residue is stated rather than guessed at: a genuinely ambiguous
`f(a<b, c>(d))` is read as a template, which is also what a compiler does with it.
"""

from __future__ import annotations

from .tokens import Token, TokenKind

# The three ways C++ spells "the thing inside that thing". All fold to `.` (clause 1).
_JOINERS = frozenset({"::", ".", "->"})

# Keywords that may lead an expression and are never part of a folded name. `new` is
# handled by the caller (clause 7) rather than here.
_NOT_A_NAME = frozenset({
    "return", "if", "while", "for", "switch", "case", "do", "else", "throw", "sizeof",
    "alignof", "static_cast", "dynamic_cast", "const_cast", "reinterpret_cast", "typeid",
    "noexcept", "decltype", "delete", "co_await", "co_return", "co_yield",
})


def fold(toks: list[Token], i: int) -> tuple[str, int]:
    """Fold the name beginning at `toks[i]`, returning it and the index just past it.

    `""` means *this chain cannot be named* (clause 3), and the caller must never match it
    against a rule. It is returned rather than raised because an unnameable expression is
    ordinary — `handlers[k]()` and `(*fp)()` are both perfectly good code — and a reader
    that refused them would stop at the first one.
    """
    n = len(toks)
    parts: list[str] = []
    unnameable = False

    while i < n:
        t = toks[i]
        if t.kind is not TokenKind.IDENT or t.text in _NOT_A_NAME:
            break
        parts.append(t.text)
        i += 1

        # Clause 6: type arguments are not part of the name.
        i = _skip_template(toks, i)

        # Clause 2: a call in the middle folds to its callee. The arguments are stepped
        # over here; the *caller* records them, because an argument list is a fact about a
        # call site and not about a name.
        while i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in "([":
            close = _matching(toks, i)
            if close is None:
                return "", i
            if toks[i].text == "[":
                # Clause 3, and the strict reading: a subscript anywhere in the chain
                # makes the whole chain unnameable, because naming it would mean deciding
                # what `handlers[k]` holds, and deciding that is resolution.
                unnameable = True
            i = close + 1
            i = _skip_template(toks, i)

        if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in _JOINERS:
            i += 1
            if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in ("*", "~"):
                # `p->*pmf` is a pointer-to-member call, and `~` is a destructor's own
                # name. The first cannot be named; the second is kept as part of it.
                if toks[i].text == "~":
                    parts.append("~")
                    nxt = toks[i + 1] if i + 1 < n else None
                    if nxt is not None and nxt.kind is TokenKind.IDENT:
                        parts[-1] = "~" + nxt.text
                        i += 2
                        continue
                return "", i + 1
            continue
        break

    if unnameable or not parts:
        return "", i
    return ".".join(parts), i


def fold_declarator(toks: list[Token], i: int) -> tuple[str, int]:
    """Fold a **declarator** — a name being declared — and stop at its parameter list.

    The same chain as `fold`, minus clause 2. That clause exists for *expressions*, where
    `IFileManager::Get().Delete()` has to fold through the call in the middle; in a
    declarator the first `(` is the parameter list and stepping over it is how a reader
    ends up with no functions at all.

    **Written as one function first, and it recognised none.** `void f()` folded to `f`
    *including* `()`, so `scopes.function_name` never saw a name followed by a parameter
    list and every ordinary function in the corpus came back as an unnamed block — while
    `operator()`, which takes its own path, worked perfectly. Two questions wearing one
    name: what is this expression called, and what is being declared here.
    """
    n = len(toks)
    parts: list[str] = []
    while i < n:
        t = toks[i]
        if t.kind is not TokenKind.IDENT or t.text in _NOT_A_NAME:
            break
        if t.text == "operator":
            break               # `scopes._operator_name` owns this; see its docstring
        parts.append(t.text)
        i += 1
        i = _skip_template(toks, i)
        if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in _JOINERS:
            i += 1
            if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text == "~":
                nxt = toks[i + 1] if i + 1 < n else None
                if nxt is not None and nxt.kind is TokenKind.IDENT:
                    parts.append("~" + nxt.text)
                    i += 2
                    if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in _JOINERS:
                        i += 1
                        continue
                    break
                return "", i
            continue
        break
    return (".".join(parts) if parts else ""), i


def _skip_template(toks: list[Token], i: int) -> int:
    """Step over a `<…>` argument list, or return `i` unchanged.

    **Only where it balances**, which is what keeps `a < b && c > d` from being eaten as a
    template. `>>` is split by the tokeniser when angle depth is open, so
    `TArray<TArray<int>>` closes correctly.
    """
    n = len(toks)
    if i >= n or toks[i].kind is not TokenKind.PUNCT or toks[i].text != "<":
        return i
    depth = 0
    j = i
    while j < n:
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == "<":
                depth += 1
            elif t.text == ">":
                depth -= 1
                if depth == 0:
                    return j + 1
            elif t.text in (";", "{", "}"):
                return i            # it never balanced; it was a comparison
        j += 1
    return i


def _matching(toks: list[Token], i: int) -> int | None:
    """Index of the bracket closing the one at `i`, or `None` if it never closes."""
    open_t = toks[i].text
    close_t = {"(": ")", "[": "]", "{": "}"}[open_t]
    depth = 0
    n = len(toks)
    j = i
    while j < n:
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == open_t:
                depth += 1
            elif t.text == close_t:
                depth -= 1
                if depth == 0:
                    return j
        j += 1
    return None


def join(prefix: str, name: str) -> str:
    """A scope prefix and a declarator, joined without doubling or dropping a dot.

    The one place the two halves of a qualname meet, because `A.B` + `C.d` and `` + `main`
    are the same operation and spelling it at both call sites is how they come apart.
    """
    if not prefix:
        return name
    return f"{prefix}.{name}" if name else prefix
