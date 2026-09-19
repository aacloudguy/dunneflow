"""What a Kotlin file declares, and where each declaration ends.

Phase 2. **Not a brace tree keyed on braces**, which is the difference from the C++ reader
and the thing that makes Kotlin its own problem rather than a smaller version of C++'s.

## Most braces in a Kotlin file open nothing

`apply { }`, `let { }`, `forEach { }`, `run { }` and trailing-lambda call syntax mean the
majority of `{` in idiomatic Kotlin are lambdas, not declarations. So a declaration is found
by its **keyword** — `fun`, `class`, `object`, `interface`, `init` — and the brace, if there
is one, is what that declaration's extent happens to be. Keyed the other way round, every
`items.forEach { … }` is a scope and a class with three methods has forty.

## And some declarations have no brace at all

    private fun alarmManager(context: Context): AlarmManager =
        context.getSystemService(Context.ALARM_SERVICE) as AlarmManager

An **expression body** is a routine, it is extremely common — it is the first function in the
first file of the demo corpus — and a reader that looks for `{` finds none of them. Its
extent is found by reading forward from the `=` until a line begins that cannot be a
continuation of the expression: `_expression_end` below, which is the one heuristic in this
module and says so.

## What is deliberately not a routine

A **lambda**, exactly as in the C++ and Python readers: a program has routines, and a routine
is a named place. The calls and boundaries inside `items.forEach { save(it) }` are attributed
to the named function that encloses it — the same residue Python already accepts for the body
of an `if`, and it is stated in `extract.RESIDUE` rather than left to be noticed.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum

from . import names
from .lexer import Masked
from .tokens import Token, TokenKind

# What introduces a type. `enum class` and `data class` are `class` with a modifier in front,
# and `companion object` is `object` — so the keyword is the same and the modifiers are read
# separately.
TYPE_WORDS = frozenset({"class", "object", "interface"})

# Modifiers that may sit in front of a declaration. Read and kept: `suspend` decides whether
# a routine is async, `private` decides its visibility, and `data` decides what kind of
# structure it is.
MODIFIERS = frozenset({
    "public", "private", "protected", "internal", "open", "final", "abstract", "sealed",
    "override", "lateinit", "inner", "enum", "annotation", "data", "value", "companion",
    "const", "inline", "noinline", "crossinline", "external", "infix", "operator",
    "suspend", "tailrec", "vararg", "expect", "actual", "fun", "reified",
})

# Tokens that, at the start of a line, continue the expression above rather than beginning a
# new statement. Kotlin has no statement terminator, so this is what stands in for one.
_CONTINUES = frozenset({
    ".", "?.", "?:", "+", "-", "*", "/", "%", "&&", "||", "==", "!=", "<=", ">=",
    ",", ")", "]", "}", "=", "->", "::", "<", ">",
})

# What, at the start of a line, begins a new declaration — and therefore says the one above
# it has no body. **The set has to include the modifiers**, or `abstract fun go()` followed
# by `private fun done() { … }` walks past `private`, past `done`, and takes `done`'s braces
# as `go`'s body: the abstract declaration becomes a routine, the real one disappears, and
# both facts are wrong in the same two lines.
_STARTS_DECLARATION = TYPE_WORDS | {"fun", "val", "var", "init", "constructor"} | MODIFIERS

# Tokens that, at the *end* of a line, mean the statement is not over.
_TRAILS = frozenset({
    ".", "?.", "?:", "+", "-", "*", "/", "%", "&&", "||", "==", "!=", "<=", ">=",
    ",", "(", "[", "=", "->", "::", ":", "<",
})


class ScopeKind(Enum):
    FILE = "file"
    TYPE = "type"
    FUNCTION = "function"
    INIT = "init"


@dataclass(slots=True)
class Scope:
    kind: ScopeKind
    name: str = ""
    # Every token of the declaration up to its body: modifiers, annotations, the name, the
    # parameter list and the return type.
    header: list[Token] = field(default_factory=list)
    # First and last token index of the body, inclusive. For a braced body these are the
    # braces; for an expression body they are the expression.
    body_start: int = -1
    body_end: int = -1
    braced: bool = True
    parent: Scope | None = None
    children: list[Scope] = field(default_factory=list)
    modifiers: frozenset[str] = frozenset()
    # `class`, `object` or `interface` for a TYPE.
    type_word: str = ""

    def ancestors(self) -> list[Scope]:
        out: list[Scope] = []
        cur = self.parent
        while cur is not None:
            out.append(cur)
            cur = cur.parent
        out.reverse()
        return out

    def qual_prefix(self) -> str:
        """The dotted prefix a declaration inside this scope inherits.

        A type contributes its name; a function does not, because a function declared inside
        a function is local and is not addressed as `outer.inner` in any sense Kotlin
        recognises.
        """
        parts = [s.name for s in [*self.ancestors(), self]
                 if s.kind is ScopeKind.TYPE and s.name]
        return ".".join(parts)

    def enclosing_type(self) -> Scope | None:
        for s in reversed([*self.ancestors(), self]):
            if s.kind is ScopeKind.TYPE:
                return s
        return None


def walk(scope: Scope) -> Iterator[Scope]:
    yield scope
    for child in scope.children:
        yield from walk(child)


def build(toks: list[Token], masked: Masked) -> Scope:
    """The declaration tree. One pass, recursing into each body as it is found."""
    root = Scope(kind=ScopeKind.FILE, body_start=0, body_end=len(toks) - 1)
    _scan(toks, masked, root, 0, len(toks))
    return root


def _scan(toks: list[Token], masked: Masked, parent: Scope, lo: int, hi: int) -> None:
    i = lo
    while i < hi:
        t = toks[i]
        if t.kind is not TokenKind.IDENT:
            i += 1
            continue

        if t.text == "fun":
            scope = _function(toks, masked, i, hi, parent)
            if scope is None:
                i += 1
                continue
            parent.children.append(scope)
            if scope.body_start >= 0:
                _scan(toks, masked, scope, scope.body_start + (1 if scope.braced else 0),
                      scope.body_end)
            i = max(scope.body_end + 1, i + 1)
            continue

        if t.text in TYPE_WORDS:
            scope = _type(toks, masked, i, hi, parent)
            if scope is None:
                i += 1
                continue
            parent.children.append(scope)
            if scope.body_start >= 0:
                _scan(toks, masked, scope, scope.body_start + 1, scope.body_end)
            i = max(scope.body_end + 1, i + 1) if scope.body_start >= 0 else i + 1
            continue

        i += 1


def _function(toks: list[Token], masked: Masked, kw: int, hi: int,
              parent: Scope) -> Scope | None:
    """`fun` at `kw`, through its name, parameters, return type and body."""
    start = _header_start(toks, kw)
    i = kw + 1
    i = _skip_type_params(toks, i, hi)
    name, i = names.fold_declarator(toks, i)
    if not name or i >= hi:
        return None
    if toks[i].kind is not TokenKind.PUNCT or toks[i].text != "(":
        return None
    close = names.matching(toks, i)
    if close is None or close >= hi:
        return None

    body_start, body_end, braced = _body(toks, masked, close + 1, hi)
    # **The header runs to the body, not to the closing paren.** Kotlin writes the return
    # type after the parameter list — `fun f(x: Int): AlarmManager = …` — so a header cut at
    # `)` has nothing after it to read and every routine in the corpus came back with no
    # return type at all. The `=` of an expression body is the boundary, not part of it.
    header_end = close + 1
    if body_start >= 0:
        header_end = body_start if braced else max(close + 1, body_start - 1)
    if body_start < 0:
        # **A declaration with no body is not a routine**, which is the C++ reader's rule
        # arrived at from the other direction: an `interface` member and an `abstract fun`
        # state a contract, and the routine is wherever it is implemented. A pure interface
        # therefore contributes no routines — and loses nothing, because in Kotlin the
        # implementations are ordinary functions in the same map.
        return None
    return Scope(
        kind=ScopeKind.FUNCTION,
        # An extension function is declared `fun String.trimmed()`. The receiver stays in
        # the name as written (clause 4 — nothing is resolved), because `String.trimmed` is
        # what the author wrote and what a rule would be written against.
        name=name,
        header=list(toks[start:header_end]),
        body_start=body_start, body_end=body_end, braced=braced,
        parent=parent,
        modifiers=_modifiers(toks, start, kw),
    )


def _type(toks: list[Token], masked: Masked, kw: int, hi: int,
          parent: Scope) -> Scope | None:
    """`class` / `object` / `interface` at `kw`.

    A type may have **no body at all** — `data class P(val x: Int)` is a complete declaration
    and one of the commonest shapes in the corpus. `body_start` is then -1 and the primary
    constructor is where its fields are.
    """
    start = _header_start(toks, kw)
    i = kw + 1
    if i < hi and toks[i].kind is TokenKind.IDENT and toks[i].text in TYPE_WORDS:
        i += 1                     # `companion object`, `enum class` handled by modifiers
    name = ""
    if i < hi and toks[i].kind is TokenKind.IDENT:
        name = toks[i].text
        i += 1
    if not name and "companion" in _modifiers(toks, start, kw):
        # `companion object { }` declares one with no name written, and Kotlin calls it
        # `Companion` — which is how it is addressed from Java and how it appears in a
        # stack trace. Naming it `<anonymous>` would be this reader inventing a word for
        # something the language has already named.
        name = "Companion"
    i = _skip_type_params(toks, i, hi)

    # The primary constructor, if there is one, then the supertype list, then maybe a body.
    header_end = i
    if i < hi and toks[i].kind is TokenKind.PUNCT and toks[i].text == "(":
        close = names.matching(toks, i)
        if close is None:
            return None
        header_end = close + 1
        i = close + 1
    depth = 0
    body_start = body_end = -1
    j = i
    while j < hi:
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([":
                depth += 1
            elif t.text in ")]":
                depth -= 1
            elif t.text == "{" and depth == 0:
                close = names.matching(toks, j)
                if close is not None:
                    body_start, body_end = j, close
                break
            elif t.text == "}" and depth == 0:
                break
        if (t.kind is TokenKind.IDENT and depth == 0 and j >= 1
                and t.text in _STARTS_DECLARATION
                and masked.line_at(t.start) > masked.line_at(toks[j - 1].start)):
            break              # the next declaration; this type has no body
        j += 1

    return Scope(
        kind=ScopeKind.TYPE,
        name=name or "<anonymous>",
        header=list(toks[start:header_end]),
        body_start=body_start, body_end=body_end, braced=True,
        parent=parent,
        modifiers=_modifiers(toks, start, kw),
        type_word=toks[kw].text,
    )


def _body(toks: list[Token], masked: Masked, i: int,
          hi: int) -> tuple[int, int, bool]:
    """Where a function's body begins and ends, and whether it is braced.

    Three answers, not two. A `{` is a block body; an `=` is an expression body; and neither
    is an **abstract or interface declaration**, which has no body and is not a routine —
    the same rule the C++ reader applies to a prototype, arrived at from the other direction.
    """
    depth = 0
    j = i
    while j < hi:
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == "{" and depth == 0:
                close = names.matching(toks, j)
                return (j, close, True) if close is not None else (-1, -1, True)
            if t.text == "=" and depth == 0:
                end = _expression_end(toks, masked, j + 1, hi)
                return j + 1, end, False
            if t.text in "([<":
                depth += 1
            elif t.text in ")]>":
                depth -= 1
            elif t.text in ("}", ";"):
                break
        # **Compared against the token before it, never against where the scan started.**
        # Guarded with `j > i` this never fired on the *first* token after the parameter
        # list, which is exactly where the next declaration sits when this one has no body.
        if (t.kind is TokenKind.IDENT and depth == 0 and j >= 1
                and t.text in _STARTS_DECLARATION
                and masked.line_at(t.start) > masked.line_at(toks[j - 1].start)):
            break
        j += 1
    return -1, -1, True


def _expression_end(toks: list[Token], masked: Masked, i: int, hi: int) -> int:
    """Where an expression body stops. **The one heuristic in this reader.**

    Kotlin has no statement terminator, so what ends an expression is a newline that nothing
    carries across. A line is a continuation if brackets are still open, if the line above
    ended on something that cannot end a statement (`.`, an operator, a comma, `(`), or if
    this line begins with something that cannot begin one (`.`, `?:`, an operator).

    It is a heuristic and is named as one. What it can get wrong is the *extent* of an
    expression body — never whether the routine exists, never its name, and never its
    parameters. The residue is stated in `extract.RESIDUE`.
    """
    depth = 0
    last = i
    j = i
    while j < hi:
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text in "([{":
                depth += 1
            elif t.text in ")]}":
                depth -= 1
                if depth < 0:
                    return last
        if j > i and depth == 0:
            prev = toks[j - 1]
            if masked.line_at(t.start) > masked.line_at(prev.start):
                starts_new = not (t.kind is TokenKind.PUNCT and t.text in _CONTINUES)
                ended = not (prev.kind is TokenKind.PUNCT and prev.text in _TRAILS)
                if starts_new and ended:
                    return last
        last = j
        j += 1
    return last


def _header_start(toks: list[Token], kw: int) -> int:
    """Back over modifiers and annotations to where the declaration really begins."""
    i = kw
    while i > 0:
        prev = toks[i - 1]
        if prev.kind is TokenKind.IDENT and prev.text in MODIFIERS:
            i -= 1
            continue
        if prev.kind is TokenKind.PUNCT and prev.text in (")", "]"):
            # An annotation with arguments: `@Suppress("x")`. Step over it and keep going if
            # what is in front is the `@`.
            open_i = _open_of(toks, i - 1)
            if open_i is not None and open_i >= 2 and toks[open_i - 2].text == "@":
                i = open_i - 2
                continue
        if prev.kind is TokenKind.IDENT and i >= 2 and toks[i - 2].text == "@":
            i -= 2
            continue
        break
    return i


def _open_of(toks: list[Token], close: int) -> int | None:
    want = {")": "(", "]": "["}[toks[close].text]
    depth = 0
    for j in range(close, -1, -1):
        t = toks[j]
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text == toks[close].text:
            depth += 1
        elif t.text == want:
            depth -= 1
            if depth == 0:
                return j
    return None


def _skip_type_params(toks: list[Token], i: int, hi: int) -> int:
    if i >= hi or toks[i].kind is not TokenKind.PUNCT or toks[i].text != "<":
        return i
    depth = 0
    for j in range(i, hi):
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == "<":
                depth += 1
            elif t.text == ">":
                depth -= 1
                if depth == 0:
                    return j + 1
            elif t.text in ("{", "}", ";"):
                return i
    return i


def _modifiers(toks: list[Token], start: int, kw: int) -> frozenset[str]:
    return frozenset(t.text for t in toks[start:kw]
                     if t.kind is TokenKind.IDENT and t.text in MODIFIERS)


def annotations_of(header: list[Token]) -> list[str]:
    """`@Test`, `@Composable`, `@Serializable(with = X::class)` — the names only.

    Kotlin's annotations are what Python's decorators are and are read the same way (rule 7).
    A call-shaped annotation contributes its **name**, and its identifier-shaped arguments
    contribute theirs, which is the split the C++ reader needed to make `BlueprintCallable`
    reachable by the existing `decorator_method` grammar without a new YAML key.
    """
    out: list[str] = []
    i, n = 0, len(header)
    while i < n:
        t = header[i]
        if t.kind is TokenKind.PUNCT and t.text == "@" and i + 1 < n:
            nxt = header[i + 1]
            if nxt.kind is TokenKind.IDENT:
                if nxt.text not in out:
                    out.append(nxt.text)
                i += 2
                if i < n and header[i].kind is TokenKind.PUNCT and header[i].text == "(":
                    close = names.matching(header, i)
                    if close is not None:
                        for arg in header[i + 1:close]:
                            if arg.kind is TokenKind.IDENT and arg.text not in out:
                                out.append(arg.text)
                        i = close + 1
                continue
        i += 1
    return out
