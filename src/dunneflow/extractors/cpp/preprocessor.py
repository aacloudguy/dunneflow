"""The directives, and the one thing a brace matcher must never be shown.

Phase 1. Two jobs, and the second is the one that is easy to miss.

**What the directives say.** `#include` is an import — the only statement of dependency a
C++ file makes, and the only one this reader can see, since it never opens the file named.
`#define` of an object-like macro with a value is a constant, which is what most named
numbers in a C codebase are.

**And what they must be hidden from.** A `#define` body is text, not code, and it is under no
obligation to balance. Unreal ships exactly the shape that costs:

    #define BEGIN_NAMESPACE(x) namespace x {
    #define END_NAMESPACE }

Counted by `scopes.py` those are an open brace and a close brace that belong to no scope,
and the brace tree below them is wrong for the rest of the file — every routine attributed
to the wrong class, or to none. So **every directive line is blanked out of the stream the
matcher sees**, along with the bodies of `#if 0`. A macro that opens a scope is therefore
invisible, which is a stated residue and the right side of it: a brace that is not there
loses a scope, and a brace that is there wrongly moves every scope after it.

## `#if 0` is skipped and nothing else is

`#if 0` is the one condition the *language itself* settles: it is false, always, with no
configuration to consult. Every other `#ifdef PLATFORM_WINDOWS`, `#if WITH_EDITOR` and
`#ifndef NDEBUG` is **scanned as live, both arms**, because deciding one needs a build
configuration nobody handed this reader (and on the demo corpus there is none to hand —
see the package docstring). Guessing which arm a compiler would take is exactly the
plausible value rule 49 forbids.

The cost is honest and bounded: two arms of one `#ifdef` can define the same qualname
twice, and both are recorded. `extract.py`'s duplicate-qualname ordinal keeps them as two
identities rather than letting one silently replace the other, which is the same mechanism
Python's reader already uses for two definitions of one name in a file.

**Header guards are not conditional compilation** and are recognised as such: an `#ifndef`
whose body is one `#define` of the same name is the idiom every header in the world opens
with, and reading it as a live branch would be correct and pointless.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...schema import Constant, ImportRec
from .lexer import Masked

# `# include <x>` is legal: whitespace may sit between the `#` and the directive word, and
# before the `#` itself. Matched on the masked stream, so a `#` inside a string never gets
# here.
_DIRECTIVE = re.compile(r"^[ \t]*#[ \t]*(?P<word>[A-Za-z_]+)[ \t]*(?P<rest>.*)$")
_INCLUDE = re.compile(r'^\s*(?:"(?P<q>[^"]+)"|<(?P<a>[^>]+)>)')
# An object-like macro: a name, then whitespace, then a value. A `(` **immediately** after
# the name makes it function-like -- `#define F(a)` is a macro with a parameter and
# `#define F (a)` is a macro whose value is `(a)`, and the only thing that tells them apart
# is the space. That is the language's rule, not a heuristic.
_DEFINE = re.compile(r"^(?P<name>[A-Za-z_]\w*)(?P<fn>\()?(?P<rest>.*)$", re.S)

_IF_OPENERS = frozenset({"if", "ifdef", "ifndef"})
_IF_CLOSERS = frozenset({"endif"})
_IF_MIDDLE = frozenset({"else", "elif", "elifdef", "elifndef"})

# `#if 0`, and its spelling with whitespace. Deliberately only the literal constant: `#if
# 0 && FOO` is an expression, and evaluating expressions is what this module refuses to do.
_ALWAYS_FALSE = re.compile(r"^0\s*(?://.*|/\*.*)?$")


@dataclass(slots=True)
class Preprocessed:
    """What the directives said, and the stream everything above this may look at.

    `code` is `Masked.code_only()` with every directive line and every `#if 0` body blanked
    — same length, same offsets, so `Masked.line_at` still answers about it (rule 51: one
    offset table, not two).
    """

    code: str
    includes: list[ImportRec] = field(default_factory=list)
    defines: list[Constant] = field(default_factory=list)
    # How many `#if 0` regions were skipped, and how many conditional branches were read as
    # live. Counted rather than listed, because the thing to know is whether the number is
    # zero — and a filter nobody can see is design rule 1's subject.
    dead_regions: int = 0
    conditionals: int = 0
    # Directive words this build does not model, with their counts. `#pragma` and
    # `#undef` are here by design; anything else appearing is worth knowing about.
    unread: dict[str, int] = field(default_factory=dict)


def scan(m: Masked) -> Preprocessed:
    """Read the directives, and blank them out of the stream the matcher will see.

    One forward pass over the lines of the masked stream. The `#if` stack carries whether
    the region is dead, so a nested `#ifdef` inside an `#if 0` cannot end it early — the
    bug that makes a skipped region stop one `#endif` too soon and read the rest of the
    file's declarations as live when they are not.
    """
    # **Taken once.** `code_only()` walks the whole file, so asking it per line is quadratic
    # — invisible on a fixture and, at 89,000 files averaging a few hundred lines, the
    # difference between this reader finishing and this reader being abandoned.
    masked = m.code_only()
    # Comments blanked, literals kept: the only view in which `#include "a/b.h"` still has
    # a path in it. See `Masked.without_comments`.
    visible = m.without_comments()
    out = list(masked)
    pre = Preprocessed(code="")
    # Each entry is (is_dead_here, was_dead_above). A region is dead if any enclosing one
    # is, which is what stops `#if 0` / `#ifdef X` / `#endif` / `#endif` reviving it.
    stack: list[tuple[bool, bool]] = []
    dead_depth = 0

    for line_no in range(1, len(m.line_starts) + 1):
        start = m.line_starts[line_no - 1]
        end = (m.line_starts[line_no] if line_no < len(m.line_starts) else len(m.text))
        # **Found on the masked stream, read from the visible one.** The mask is what makes
        # a `#` inside a raw string not a directive; the visible view is what still has a
        # path inside the quotes.
        hit = _DIRECTIVE.match(masked[start:end])

        if hit is None:
            if dead_depth:
                _blank(out, start, end)
            continue

        word = hit.group("word")
        seen = _DIRECTIVE.match(visible[start:end])
        rest = (seen.group("rest") if seen else hit.group("rest")).strip()

        if word in _IF_OPENERS:
            now_dead = bool(dead_depth) or (word == "if" and bool(_ALWAYS_FALSE.match(rest)))
            stack.append((now_dead, bool(dead_depth)))
            if now_dead:
                if not dead_depth:
                    pre.dead_regions += 1
                dead_depth += 1
            else:
                pre.conditionals += 1
        elif word in _IF_MIDDLE:
            # The other arm of a region whose first arm was `#if 0` is **live**, and that is
            # the point of tracking `was_dead_above` separately: `#if 0 ... #else ... #endif`
            # is the commonest way to comment one of two implementations out, and the one
            # that is left is the program.
            if stack:
                was_dead, outer = stack[-1]
                if was_dead and not outer:
                    dead_depth -= 1
                    stack[-1] = (False, outer)
        elif word in _IF_CLOSERS:
            if stack:
                was_dead, _ = stack.pop()
                if was_dead:
                    dead_depth -= 1
        elif not dead_depth:
            if word == "include":
                if rec := _include(rest, line_no):
                    pre.includes.append(rec)
            elif word == "define":
                if const := _define(rest, line_no):
                    pre.defines.append(const)
            else:
                pre.unread[word] = pre.unread.get(word, 0) + 1

        # Every directive line goes, live or dead. See the module docstring: a `#define`
        # body is text and is under no obligation to balance its braces.
        _blank(out, start, end)

    pre.code = "".join(out)
    return pre


def _blank(out: list[str], start: int, end: int) -> None:
    """Replace a region with spaces, keeping newlines so the file keeps its shape."""
    for k in range(start, end):
        if out[k] != "\n":
            out[k] = " "


def _include(rest: str, line: int) -> ImportRec | None:
    """`#include "a/b.h"` and `#include <vector>`, as written and never resolved.

    The path is the module, exactly as the file spells it. **Not resolved against an include
    path** — this reader never opens a file it was not independently asked to walk, so
    `"Misc/Guid.h"` names what the author wrote and matching it to a file in the tree is
    somebody else's question.

    `#include MACRO_NAME` is legal and is refused rather than guessed: expanding it is macro
    expansion, which this reader does not do.
    """
    hit = _INCLUDE.match(rest)
    if hit is None:
        return None
    path = hit.group("q") or hit.group("a")
    return ImportRec(module=path, name="", alias="", is_from=bool(hit.group("q")), line=line)


def _define(rest: str, line: int) -> Constant | None:
    """An object-like macro with a value is a constant. Nothing else here is a fact.

    Three shapes and only the first is recorded:

    * `#define MAX_USERS 100` — a name with a value, which is what `Constant` is for and
      what most named numbers in a C codebase are.
    * `#define MAX(a, b) ((a) > (b) ? (a) : (b))` — **function-like, and not a constant**.
      It has no value, no type and no linkage, and calling it a constant would put an
      expression in a column readers compare for equality. `(` immediately after the name
      is the language's own test, and the space in `#define F (a)` genuinely makes that one
      object-like.
    * `#define GUID_H_` — **no value at all**, which is the header-guard idiom and a few
      hundred per corpus. A constant whose value is the empty string is a row that says
      nothing; it is left out and the residue is stated.

    `is_final` is True because a macro cannot be reassigned — it can be `#undef`ed and
    redefined, which is a different fact this reader does not model.
    """
    hit = _DEFINE.match(rest)
    if hit is None or hit.group("fn"):
        return None
    value = hit.group("rest").strip()
    if not value:
        return None
    return Constant(name=hit.group("name"), value=value, line=line, is_final=True)
