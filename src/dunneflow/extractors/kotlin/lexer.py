"""Which bytes are code, and which physical line each one came from — Kotlin's answer.

Phase 0, and the C++ reader's phase 0 one language over. **Deliberately not shared with it**,
and that is rule 12 rather than an oversight: `detectors.lang_extraction_inputs` globs
`extractors/<lang>/*` into *that language's* stamp, so a module the two readers had in common
would live in neither key — and editing it would change what both of them read while
invalidating nothing. A reader is self-contained or it is not fingerprinted.

## Three things Kotlin spells differently, and each one bites

* **Block comments nest.** `/* /* */ */` is one comment in Kotlin and two in C++. A scanner
  that closes at the first `*/` reads the tail of the outer comment as code; one that counts
  depth in C++ reads the rest of the file as comment. Same syntax, opposite rules, and the
  only way to be right about both is to write it twice.
* **A raw string is delimited by three quotes and ends at the last quote of a run.** Four
  quotes, then `x`, then four quotes is a raw string containing `"x"`, because the closing
  delimiter is the *last* three of the four. Read as three-plus-one it ends a character early
  and the mask is inverted from there on. (The delimiter is not written out here: this is a
  Python docstring, and a literal triple quote inside one closes it — which is exactly the
  class of mistake this module exists to get right, made in the file that describes it.)
* **A string is interpolated.** `"$name"` and `"${expr}"` carry code inside a literal, and
  `${` nests braces that must not reach the brace matcher. The span is still one literal —
  `LiteralKind.INTERPOLATED` is what says a placeholder was in it — but the interpolation is
  tracked while scanning so a `}` inside one closes the placeholder rather than a block.

There is **no line-continuation splicing** and no preprocessor: Kotlin has neither, so the
offsets here are the file's own and `line_at` is a plain bisect. That is one whole phase the
C++ reader needs and this one does not.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum


class Span(Enum):
    CODE = "code"
    LINE_COMMENT = "line_comment"
    BLOCK_COMMENT = "block_comment"
    STRING = "string"
    RAW_STRING = "raw_string"
    CHAR = "char"


_IDENT = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


@dataclass(frozen=True, slots=True)
class Masked:
    """The source, what each byte of it is, and where the lines start.

    No splicing, so `text` **is** the file and an offset here is an offset there.
    """

    text: str
    kind: tuple[Span, ...]
    line_starts: tuple[int, ...]
    # Offsets at which a `$` interpolation begins, for the literal reader. A span holding one
    # is `INTERPOLATED`; one that does not is `PLAIN`, and the two are different facts.
    interpolations: frozenset[int]

    def line_at(self, offset: int) -> int:
        return bisect_right(self.line_starts, offset)

    def code_only(self) -> str:
        """The stream with everything that is not code blanked, at the same offsets.

        Blanked rather than removed so one offset table serves every view (rule 51), and
        newlines kept whatever span they are in so the file keeps its shape.
        """
        out = []
        for ch, kind in zip(self.text, self.kind, strict=True):
            out.append(ch if kind is Span.CODE or ch == "\n" else " ")
        return "".join(out)


def mask(src: str) -> Masked:
    """One forward pass. The only state is which span is open, and how deeply."""
    n = len(src)
    kind: list[Span] = [Span.CODE] * n
    starts = [0]
    for i, ch in enumerate(src):
        if ch == "\n":
            starts.append(i + 1)
    interpolations: set[int] = set()

    i = 0
    while i < n:
        ch = src[i]

        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                kind[k] = Span.LINE_COMMENT
            i = j
            continue

        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            # **Nesting, which is Kotlin's rule and not C++'s.**
            depth = 0
            j = i
            while j < n:
                if src.startswith("/*", j):
                    depth += 1
                    j += 2
                    continue
                if src.startswith("*/", j):
                    depth -= 1
                    j += 2
                    if depth == 0:
                        break
                    continue
                j += 1
            end = min(j, n)
            for k in range(i, end):
                kind[k] = Span.BLOCK_COMMENT
            i = end
            continue

        if src.startswith('"""', i):
            end, had = _raw_string_end(src, i)
            for k in range(i, end):
                kind[k] = Span.RAW_STRING
            if had:
                interpolations.add(i)
            i = end
            continue

        if ch == '"':
            end, had = _string_end(src, i)
            for k in range(i, end):
                kind[k] = Span.STRING
            if had:
                interpolations.add(i)
            i = end
            continue

        if ch == "'":
            end = _char_end(src, i)
            for k in range(i, end):
                kind[k] = Span.CHAR
            i = end
            continue

        i += 1

    return Masked(text=src, kind=tuple(kind), line_starts=tuple(starts),
                  interpolations=frozenset(interpolations))


def _raw_string_end(src: str, start: int) -> tuple[int, bool]:
    """Past a `\"\"\"…\"\"\"`, and whether it interpolated.

    **The closing delimiter is the last three quotes of a run**, which is the rule that makes
    `\"\"\"\"x\"\"\"\"` a raw string containing `\"x\"`. Taking the first three ends it a
    character early and inverts the mask for the rest of the file.
    """
    n = len(src)
    i = start + 3
    had = False
    while i < n:
        if src[i] == "$" and i + 1 < n and (src[i + 1] == "{" or src[i + 1] in _IDENT):
            had = True
            i += 1
            continue
        if src[i] == '"':
            run = i
            while run < n and src[run] == '"':
                run += 1
            if run - i >= 3:
                return run, had
            i = run
            continue
        i += 1
    return n, had


def _string_end(src: str, start: int) -> tuple[int, bool]:
    """Past an ordinary `"…"`, honouring escapes and `${…}` nesting.

    An unterminated literal ends at the newline: a Kotlin string may not span one, so this is
    the language's rule rather than damage control.
    """
    n = len(src)
    i = start + 1
    had = False
    while i < n:
        ch = src[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            return i + 1, had
        if ch == "\n":
            return i, had
        if ch == "$" and i + 1 < n:
            had = True
            if src[i + 1] == "{":
                depth = 0
                j = i + 1
                while j < n:
                    if src[j] == "{":
                        depth += 1
                    elif src[j] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    elif src[j] == "\n":
                        break
                    j += 1
                i = j + 1
                continue
        i += 1
    return n, had


def _char_end(src: str, start: int) -> int:
    n = len(src)
    i = start + 1
    while i < n:
        if src[i] == "\\":
            i += 2
            continue
        if src[i] == "'":
            return i + 1
        if src[i] == "\n":
            return i
        i += 1
    return n
