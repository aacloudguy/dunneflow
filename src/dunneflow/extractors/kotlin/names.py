"""How this reader spells a name — `ingest/dotted.py`'s contract, in Kotlin.

The same eight clauses every reader is held to, and Kotlin exercises more of them than C++:

1. **A source-order identifier chain, dot-joined.** `a.b.c()` is `a.b.c`.
2. **A call in the middle folds to its callee.** `Timber.tag(x).d()` is `Timber.tag.d`.
3. **No name at the root gives `""`.** A subscript, a literal, a lambda's receiver.
5. **Nullability is not identity** — and Kotlin is where this clause earns its place.
   `a?.b!!.c()` folds to `a.b.c`. Written into the contract for TypeScript's `?.` and
   spelled the same way here, which is why the fixture case for it is shared.
6. **Type arguments are not part of the name.** `listOf<String>()` is `listOf`.
7. **There is no `new`**, so `CallSite.is_construction` is False for every Kotlin call:
   a constructor invocation is spelled exactly like a function call and telling the two
   apart needs a symbol table. A structural absence, stated rather than guessed at.
8. **The receiver word is `this`**, declared in the manifest.

Clause 4 — no resolution, no alias expansion — this reader could not violate if it tried:
an `import x.y.Z` followed by `Z()` is spelled `Z`, which is what a rule matching the
*written* prefix wants (rule 5).
"""

from __future__ import annotations

from .tokens import Token, TokenKind

# `?.` folds away with `.`: clause 5, nullability is not identity.
_JOINERS = frozenset({".", "?.", "::"})

_NOT_A_NAME = frozenset({
    "return", "if", "else", "while", "for", "do", "when", "try", "catch", "finally",
    "throw", "is", "as", "in", "by", "object", "fun", "val", "var", "class",
})


def fold(toks: list[Token], i: int) -> tuple[str, int]:
    """Fold the expression name at `toks[i]`; `""` means it cannot be named (clause 3)."""
    n = len(toks)
    parts: list[str] = []
    unnameable = False
    while i < n:
        t = toks[i]
        if t.kind is not TokenKind.IDENT or t.text in _NOT_A_NAME:
            break
        parts.append(t.text)
        i += 1
        i = _skip_type_args(toks, i)
        # `!!` asserts non-null and says nothing about the name (clause 5).
        while i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text == "!!":
            i += 1
        while i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in "([":
            close = matching(toks, i)
            if close is None:
                return "", i
            if toks[i].text == "[":
                unnameable = True       # naming it would mean deciding what it holds
            i = close + 1
            while i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text == "!!":
                i += 1
            i = _skip_type_args(toks, i)
        if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in _JOINERS:
            i += 1
            continue
        break
    if unnameable or not parts:
        return "", i
    return ".".join(parts), i


def fold_declarator(toks: list[Token], i: int) -> tuple[str, int]:
    """Fold a name being *declared*, stopping at its parameter list.

    Clause 2 is for expressions: in a declarator the first `(` is the parameters, and
    stepping over it is how a reader ends up with no functions at all — the defect the C++
    reader shipped with for an hour and the reason this is a separate function there too.
    """
    n = len(toks)
    parts: list[str] = []
    while i < n:
        t = toks[i]
        if t.kind is not TokenKind.IDENT or t.text in _NOT_A_NAME:
            break
        parts.append(t.text)
        i += 1
        i = _skip_type_args(toks, i)
        if i < n and toks[i].kind is TokenKind.PUNCT and toks[i].text in _JOINERS:
            i += 1
            continue
        break
    return (".".join(parts) if parts else ""), i


def _skip_type_args(toks: list[Token], i: int) -> int:
    """Step over `<…>` where it balances before the statement ends (clause 6)."""
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
            elif t.text in (";", "{", "}", "="):
                return i            # it never balanced; it was a comparison
        j += 1
    return i


def matching(toks: list[Token], i: int) -> int | None:
    """Index of the bracket closing the one at `i`, or `None`."""
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


def join(prefix: str, name: str) -> str:
    if not prefix:
        return name
    return f"{prefix}.{name}" if name else prefix
