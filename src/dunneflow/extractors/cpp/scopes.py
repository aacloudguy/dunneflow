"""The brace tree, and what each `{` turns out to have been.

Phase 3, and the shape everything above hangs off. `ast` hands the Python reader a tree; this
is the tree, built by hand, and the whole of what makes a routine's `class_name` and a
qualname's prefix answerable.

## Headers are read forwards, from statement boundaries

The naive way is to look backwards from a `{` at the token before it, and it is wrong in
both directions at once: `Foo::Foo(int x) : x_(x) {` ends in `)` and is a constructor, and
`int a[] = {` ends in `=` and is not a function at all. So the tree is built first — braces
match, and nothing about C++ makes that hard once the lexer has hidden the ones inside
strings — and each `{` then carries the **token run since the last `;`, `{` or `}`**, which
is the statement that introduced it. That run is what gets classified.

It is also the only reading that survives a member-initialiser list, which is a sequence of
call-shaped groups sitting between the parameters and the body.

## What a `{` can be, and the one refusal that matters

`namespace`, a record (`class`/`struct`/`union`/`enum`), a function body, `extern "C"`, or an
ordinary block. **A declaration with no body never appears here at all** — it ends at a `;`
and opens no brace — which is what dissolves the header-and-`.cpp` double: a prototype in
`Foo.h` is not a routine, so the definition in `Foo.cpp` is the only place that name is
minted, and there is never a pair to reconcile.

`SCOPE_KEYWORDS` is checked at the *start* of the run after attributes and macros are
stepped over, because Unreal writes `UCLASS(Blueprintable) class FOO_API AThing : public
AActor {` and the class keyword is four tokens in.

## What is deliberately not attempted

A macro that opens a scope. `preprocessor.py` blanks every directive line before this pass
runs, so `#define BEGIN_NS(x) namespace x {` contributes no brace — which loses the scope
rather than misplacing every scope after it. Stated in `extract.RESIDUE`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum

from . import names
from .tokens import Token, TokenKind

# Keywords that make the run a record declaration. `enum` is here as well as in
# `RECORD_KEYWORDS` because an enum body is a scope for naming purposes -- `Color::Red` --
# even though it holds no routines.
RECORD_KEYWORDS = frozenset({"class", "struct", "union", "enum"})

# Stepped over while looking for what a run really starts with. Attributes, export and
# template headers, and the specifiers Unreal and everyone else put in front of a class.
_SKIP_LEADING = frozenset({
    "template", "export", "inline", "static", "constexpr", "consteval", "constinit",
    "extern", "friend", "virtual", "explicit", "mutable", "thread_local", "typename",
    "final", "alignas",
})

# A run led by one of these is a control statement and belongs to `control.py`, never to a
# routine or a record. `catch` and `else` are here for the same reason.
# `public:`, `private:`, `protected:` — a label, never an initialiser list.
_ACCESS_LABELS = frozenset({"public", "private", "protected"})

CONTROL_WORDS = frozenset({
    "if", "else", "for", "while", "do", "switch", "try", "catch", "co_await",
})

# Trailing tokens that may sit between a parameter list's `)` and the body's `{` without
# making the run something other than a function.
_TRAILING_OK = frozenset({
    "const", "noexcept", "override", "final", "volatile", "mutable", "requires",
    "&", "&&", "->", "throw", "try", "constexpr",
})


class ScopeKind(Enum):
    FILE = "file"
    NAMESPACE = "namespace"
    RECORD = "record"
    FUNCTION = "function"
    LINKAGE = "linkage"
    BLOCK = "block"


@dataclass(slots=True)
class Scope:
    """One `{ … }` and what introduced it.

    `open_tok`/`close_tok` are indices into the token list, not offsets: everything above
    walks tokens, and an offset is asked for only at the moment a line number is wanted.
    """

    kind: ScopeKind
    name: str = ""
    # The tokens of the statement that introduced this scope, `template<…>` and all.
    header: list[Token] = field(default_factory=list)
    open_tok: int = -1
    close_tok: int = -1
    parent: Scope | None = None
    children: list[Scope] = field(default_factory=list)
    # Which of `RECORD_KEYWORDS` opened it, for a record.
    record_word: str = ""
    # `private` inside a `class` until a label says otherwise, `public` inside a `struct`.
    # Only meaningful for a RECORD's direct children.
    default_visibility: str = "public"

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

        Namespaces and records contribute; a function body and a block do not, because a
        routine declared inside a function is not `outer.inner` in any sense C++ recognises
        — it is a lambda or a local class, and neither is addressed that way.
        """
        parts = [s.name for s in [*self.ancestors(), self]
                 if s.kind in (ScopeKind.NAMESPACE, ScopeKind.RECORD) and s.name]
        return ".".join(parts)

    def enclosing_record(self) -> Scope | None:
        for s in reversed([*self.ancestors(), self]):
            if s.kind is ScopeKind.RECORD:
                return s
        return None


def build(toks: list[Token]) -> Scope:
    """The whole file as one FILE scope with the tree under it.

    One forward pass. A `{` pushes, a `}` pops, and the run since the last statement
    boundary is handed to `classify`.
    """
    root = Scope(kind=ScopeKind.FILE)
    stack = [root]
    run_start = 0
    n = len(toks)

    for i in range(n):
        t = toks[i]
        if t.kind is not TokenKind.PUNCT:
            continue
        if t.text == "{":
            header = toks[run_start:i]
            kind, name, word = classify(header)
            scope = Scope(kind=kind, name=name, header=list(header), open_tok=i,
                          parent=stack[-1], record_word=word,
                          default_visibility="private" if word == "class" else "public")
            stack[-1].children.append(scope)
            stack.append(scope)
            run_start = i + 1
        elif t.text == "}":
            if len(stack) > 1:
                stack.pop().close_tok = i
            run_start = i + 1
        elif t.text == ";":
            run_start = i + 1
        elif (t.text == ":" and i > 0 and toks[i - 1].kind is TokenKind.IDENT
              and toks[i - 1].text in _ACCESS_LABELS):
            # **An access label ends a statement**, and it has to, because `:` is also how
            # a member-initialiser list begins. Without this the run before a method's body
            # reaches back past `public:` to whatever preceded it -- in every UObject that
            # is `GENERATED_BODY()`, whose `()` then reads as the parameter list and whose
            # trailing `public :` reads as an initialiser list. The class's first method is
            # then called `GENERATED_BODY`, takes nothing, and owns the body of the method
            # a reader was actually looking for.
            run_start = i + 1

    # An unbalanced file: everything still open ends where the tokens do. Recorded rather
    # than refused -- a truncated or macro-mangled file still has facts above the break,
    # and losing the whole file to one unmatched brace is the recall rule 1 does not ask for.
    while len(stack) > 1:
        stack.pop().close_tok = n - 1
    return root


def classify(header: list[Token]) -> tuple[ScopeKind, str, str]:
    """What the run before a `{` says the `{` is. Returns (kind, name, record word)."""
    if not header:
        return ScopeKind.BLOCK, "", ""

    lead = _first_meaningful(header)
    if lead is None:
        return ScopeKind.BLOCK, "", ""

    if lead.kind is TokenKind.IDENT and lead.text in CONTROL_WORDS:
        return ScopeKind.BLOCK, "", ""

    if lead.kind is TokenKind.IDENT and lead.text == "namespace":
        return ScopeKind.NAMESPACE, _namespace_name(header, lead), ""

    if lead.kind is TokenKind.IDENT and lead.text == "extern":
        return ScopeKind.LINKAGE, "", ""

    # A function is decided before a record, because `enum class E : int {` and a function
    # returning an enum are told apart by whether a parameter list is present at all.
    if (fn := function_name(header)) is not None:
        return ScopeKind.FUNCTION, fn, ""

    idx = _record_keyword(header)
    if idx is not None:
        return ScopeKind.RECORD, _record_name(header, idx), header[idx].text

    return ScopeKind.BLOCK, "", ""


def declarator_span(header: list[Token]) -> tuple[int, int, str] | None:
    """Where the declared name starts, where its parameter list opens, and the name.

    **One walk, three callers** (rule 51). `function_name` wants the name, `routines._params`
    wants the `(`, and `routines._returns` and `_decorators` want to know where the name
    *begins* so they can take what is in front of it. Written separately they disagree about
    a constructor's initialiser list or a macro wearing a parameter list, and the disagreement
    shows up as a return type with the class name glued on the end.
    """
    i = _skip_leading(header)
    n = len(header)

    while i < n:
        if header[i].kind is TokenKind.IDENT and header[i].text == "operator":
            start = i
            name, j = _operator_name(header, i)
            if name is None:
                return None
            return (start, j, name) if _params_then_qualifiers(header, j) else None

        name, j = names.fold_declarator(header, i)
        if name and j < n and header[j].kind is TokenKind.PUNCT and header[j].text == "(":
            if j + 1 < n and header[j + 1].text in ("*", "&"):
                return None
            close = _matching(header, j)
            if close is None:
                return None
            if _only_qualifiers(header, close + 1):
                return i, j, name
            i = close + 1
            continue
        if j > i:
            i = j
            continue
        i += 1
    return None


def function_name(header: list[Token]) -> str | None:
    """The declarator of a function definition, folded, or `None` if this is not one.

    The rule is *a name, then a parameter list, then nothing but qualifiers*. Read forwards
    from the declarator rather than backwards from the `{`, which is what makes a
    constructor's member-initialiser list a non-event: it sits after the parameters and is
    stepped over with everything else that is allowed to.
    """
    span = declarator_span(header)
    return None if span is None else span[2]


def _params_then_qualifiers(header: list[Token], i: int) -> bool:
    n = len(header)
    if i >= n or header[i].kind is not TokenKind.PUNCT or header[i].text != "(":
        return False
    close = _matching(header, i)
    return close is not None and _only_qualifiers(header, close + 1)


def _only_qualifiers(header: list[Token], i: int) -> bool:
    """Is everything from `i` to the end allowed between a parameter list's `)` and the `{`?

    Two rejections, and Unreal supplied both within four tokens of each other.

    **A second parameter list before any `:` means this candidate was not the parameters.**
    `GENERATED_BODY() void Tick(float D) override {` is the class-body idiom on every
    UObject there is, and read left to right the first name-followed-by-parens is the
    *macro*: without this the routine is called `GENERATED_BODY`, takes no arguments, and
    owns `Tick`'s body. A member-initialiser list is the one thing that legitimately puts
    more call-shaped groups after the parameters, and it always follows a `:` — so the `:`
    returns True immediately and everything after it is initialisers, not declarators.

    **A record keyword is never a qualifier.** `UCLASS(Blueprintable) class FOO_API AThing
    : public AActor {` has a name, a parameter list and then a base clause, which is the
    exact shape of a constructor — and it is a class. `class`, `struct`, `union` and `enum`
    cannot appear between a parameter list and a body in any legal declaration, so one
    here means the candidate was a macro and the run is a record.
    """
    n = len(header)
    while i < n:
        t = header[i]
        if t.kind is TokenKind.PUNCT:
            if t.text == ":":
                return True         # a member-initialiser list; the rest is initialisers
            if t.text == "(":
                return False        # a later declarator: this candidate was a macro
            if t.text in _TRAILING_OK or t.text == "<":
                i += 1
                continue
            return False
        if t.kind is TokenKind.IDENT:
            if t.text in RECORD_KEYWORDS:
                return False        # a record wearing a macro's parameter list
            i += 1
            continue
        i += 1
    return True


def _operator_name(header: list[Token], i: int) -> tuple[str | None, int]:
    """`operator==`, `operator()`, `operator[]`, `operator bool`, `operator new`.

    Its own case because the first `(` after `operator` is sometimes the *name* and
    sometimes the parameters, and reading `operator()(int)` as a nullary operator taking
    nothing silently garbles every functor in the corpus.
    """
    n = len(header)
    j = i + 1
    parts: list[str] = ["operator"]
    if j < n and header[j].kind is TokenKind.PUNCT and header[j].text == "(":
        if j + 1 < n and header[j + 1].text == ")":
            return "operator()", j + 2
        return None, j
    if j < n and header[j].kind is TokenKind.PUNCT and header[j].text == "[":
        if j + 1 < n and header[j + 1].text == "]":
            return "operator[]", j + 2
        return None, j
    while j < n:
        t = header[j]
        if t.kind is TokenKind.PUNCT and t.text == "(":
            break
        parts.append(t.text)
        j += 1
    if len(parts) == 1:
        return None, j
    return "operator" + "".join(parts[1:]), j


def _skip_leading(header: list[Token]) -> int:
    """Step over `template<…>`, attributes, and the specifiers before a declarator."""
    i, n = 0, len(header)
    while i < n:
        t = header[i]
        if t.kind is TokenKind.IDENT and t.text == "template":
            j = i + 1
            if j < n and header[j].text == "<":
                close = _matching_angle(header, j)
                i = (close + 1) if close is not None else j
                continue
            i = j
            continue
        if t.kind is TokenKind.PUNCT and t.text == "[" and i + 1 < n and header[i + 1].text == "[":
            close = _matching(header, i)
            i = (close + 1) if close is not None else i + 1
            continue
        if t.kind is TokenKind.IDENT and t.text in _SKIP_LEADING:
            i += 1
            continue
        break
    return i


def _first_meaningful(header: list[Token]) -> Token | None:
    i = _skip_leading(header)
    return header[i] if i < len(header) else None


def _record_keyword(header: list[Token]) -> int | None:
    """Where the `class`/`struct`/`union`/`enum` is, after attributes and macros.

    Unreal writes `UCLASS(Blueprintable) class FOO_API AThing : public AActor {`, so the
    keyword is four tokens in and looking only at the first is looking at `UCLASS`.
    """
    for i, t in enumerate(header):
        if t.kind is TokenKind.IDENT and t.text in RECORD_KEYWORDS:
            return i
    return None


def _record_name(header: list[Token], idx: int) -> str:
    """The declared name, stepping over `class` after `enum` and any export macro.

    `class FOO_API AThing : public AActor` names `AThing`: the last identifier before the
    base-clause `:` or the end, because an API export macro sits between the keyword and
    the name and is spelled differently in every module.
    """
    i = idx + 1
    if (i < len(header) and header[i].kind is TokenKind.IDENT
            and header[i].text in ("class", "struct")):
        i += 1                      # `enum class E`
    last = ""
    while i < len(header):
        t = header[i]
        if t.kind is TokenKind.PUNCT:
            if t.text in (":", "<"):
                break
            i += 1
            continue
        last = t.text
        i += 1
    return last


def _namespace_name(header: list[Token], lead: Token) -> str:
    """`namespace A`, `namespace A::B` (C++17), or anonymous.

    An anonymous namespace keeps the empty name deliberately: it contributes nothing to a
    qualname, which is exactly what C++ means by one — the name is unutterable from outside
    the translation unit. It used to feed a linkage check on a routine's identity; that
    check is gone, because the file is in every identity now and there is nothing left for
    linkage to decide (see `routines._routine`).
    """
    i = header.index(lead) + 1
    parts: list[str] = []
    while i < len(header):
        t = header[i]
        if t.kind is TokenKind.IDENT:
            parts.append(t.text)
        elif t.kind is TokenKind.PUNCT and t.text not in ("::",):
            break
        i += 1
    return ".".join(parts)


def _matching(toks: list[Token], i: int) -> int | None:
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


def _matching_angle(toks: list[Token], i: int) -> int | None:
    depth = 0
    for j in range(i, len(toks)):
        t = toks[j]
        if t.kind is TokenKind.PUNCT:
            if t.text == "<":
                depth += 1
            elif t.text == ">":
                depth -= 1
                if depth == 0:
                    return j
    return None


def walk(scope: Scope) -> Iterator[Scope]:
    """Every scope under `scope`, including it, depth first."""
    yield scope
    for child in scope.children:
        yield from walk(child)
