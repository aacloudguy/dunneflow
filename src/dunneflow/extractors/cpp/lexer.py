"""Which bytes are code, and which physical line each one came from.

Phases -1 and 0. Everything above this asks `Masked` and never the raw text, for the reason
`markdown.py` scans for fences before it scans for headings: a `{` inside a string literal
is not a brace, and a reader that cannot tell is a reader whose every later answer is a
guess about which.

## Why splicing comes first, and it is not an ordering preference

A line continuation is `\\` immediately before a newline, and the standard removes it in
translation phase 2 -- *before* comments are recognised in phase 3. So

    // this comment continues \\
    ReallyImportantCall();

is one comment and that call does not exist. Recognise comments first and the call is read,
attributed to whatever routine encloses it, and reported as flow that the compiler never
sees. It is rare and it is not hypothetical: it is the standard's own order, and getting it
backwards produces a fact rather than losing one, which is the direction rule 1 cares about.

Splicing changes offsets, so the physical line of everything above has to come from
somewhere. `Masked.line_at` is that somewhere, and **nothing above this module may count
newlines** -- in a spliced stream the count is wrong by however many continuations preceded
it, and wrong in a way that grows down the file.

## The three lexical traps, each paid for by a language rule rather than a preference

* **A raw string is not a string.** `R"delim( … )delim"` runs to the exact closing sequence
  and processes no escapes, so `R"(a\\)"` ends at the `)"` and not one byte earlier. Unreal
  embeds shader source, JSON and regular expressions this way; a reader that treats one as
  an ordinary literal desynchronises on the first backslash and reads the rest of the file
  as string.
* **`'` is not always a char literal.** C++14 digit separators write `1'000'000`, and a `'`
  taken for a quote there swallows everything to the next one. So the mask tracks whether it
  is inside a numeric literal, which is the one piece of token structure this phase needs.
* **Block comments do not nest.** `/* /* */` is closed, and a reader that counts depth reads
  the rest of the file as comment.

Trigraphs and digraphs are **not handled**, and that is a stated residue rather than an
oversight: trigraphs were removed from the language in C++17, digraphs are vanishingly rare
in modern code, and this reader's corpus is C++17-and-later with vendored third-party trees
excluded by discovery. Named in `extract.RESIDUE` so nobody has to find out by reading here.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from enum import Enum


class Span(Enum):
    """What one byte of the spliced stream is.

    `CODE` is the only one anything above this reads for structure. The rest are kept rather
    than blanked because they are facts in their own right -- a comment is what a routine
    says about itself, and a string is what `ingest.literals` judges.
    """

    CODE = "code"
    LINE_COMMENT = "line_comment"
    BLOCK_COMMENT = "block_comment"
    STRING = "string"
    RAW_STRING = "raw_string"
    CHAR = "char"


# The identifier characters a raw-string delimiter may hold, and the bound on it. Both are
# the standard's: at most 16 characters, and none of them whitespace, `(`, `)` or `\`. The
# bound matters -- without it an unterminated `R"` reads to the end of the file looking for
# a delimiter that is not there.
_RAW_DELIM_MAX = 16
_NOT_IN_DELIM = frozenset(' \t\n\r\f\v()\\')

# A `'` directly after one of these is a digit separator rather than a quote, provided a
# numeric literal is already open. Hex digits are here because `0xFF'FF` is legal.
_DIGITS = frozenset("0123456789abcdefABCDEF")
_IDENT = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$")


@dataclass(frozen=True, slots=True)
class Masked:
    """The spliced stream, what each byte of it is, and the way back to the file.

    `text` is not the file: continuations have gone, so an offset here is not an offset
    there. That is the whole reason `line_at` exists and the whole reason nothing above
    counts newlines.
    """

    text: str
    kind: tuple[Span, ...]
    # Offset in the SPLICED stream at which each physical line's content begins -- one
    # entry per physical line of the original file, whether or not it was continued onto
    # the line above. A reader opens the file at the line this reports, so the question is
    # where a token *is*, never which logical line it belongs to.
    line_starts: tuple[int, ...]
    # How many continuations were removed. Zero for almost every file, and the number worth
    # having when one is not read the way somebody expected.
    continuations: int

    def line_at(self, offset: int) -> int:
        """The physical line `offset` fell on, 1-based."""
        return bisect_right(self.line_starts, offset)

    def is_code(self, offset: int) -> bool:
        return self.kind[offset] is Span.CODE

    def code_only(self) -> str:
        """The stream with everything that is not code replaced by spaces.

        Same length and same offsets, so a match found in it indexes straight back into
        `text` and into `line_at`. Blanked rather than removed for that reason alone -- a
        compacted copy would need a second offset table, which is a second answer to the
        question `line_at` already answers (rule 51).

        Newlines are kept whatever span they are in, so a line-oriented rule reading this
        still sees the file's shape.
        """
        out = []
        for ch, kind in zip(self.text, self.kind, strict=True):
            out.append(ch if kind is Span.CODE or ch == "\n" else " ")
        return "".join(out)

    def without_comments(self) -> str:
        """The stream with comments blanked and **literals kept as written**.

        `code_only()` is for structure and blanks strings, which is right for a brace
        matcher and wrong for the one place a string literal *is* the syntax: `#include
        "Misc/Guid.h"`. Read off `code_only()` the path is a run of spaces and every
        project-relative include in the corpus disappears — measured on the first fixture,
        where `<vector>` came back and `"Misc/Guid.h"` did not, which in Unreal is almost
        all of them.

        So a directive is **found** on `code_only()`, where a `#` inside a raw string has
        already been blanked and cannot be mistaken for one, and **read** here. Two views of
        one stream at the same offsets, which is why neither needs its own line table.
        """
        out = []
        for ch, kind in zip(self.text, self.kind, strict=True):
            hide = kind in (Span.LINE_COMMENT, Span.BLOCK_COMMENT)
            out.append(" " if hide and ch != "\n" else ch)
        return "".join(out)


def logical(src: str) -> tuple[str, tuple[int, ...], int]:
    """Phase -1: splice line continuations, and record where the physical lines went.

    Returns the spliced text, the offset each physical line starts at *within it*, and how
    many continuations were removed.

    A continuation is `\\` immediately before a newline, and `\\\r\n` counts -- a CRLF file
    that `ingest.contract.SOURCE_TEXT` has already normalised cannot reach here with one,
    but this function is also the one a test hands raw bytes to, and a rule that holds only
    for pre-normalised input is a rule with a hole in it.
    """
    out: list[str] = []
    starts = [0]
    removed = 0
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        if ch == "\\":
            j = i + 1
            if j < n and src[j] == "\r":
                j += 1
            if j < n and src[j] == "\n":
                # The continuation and its newline both go -- but the physical line that
                # followed it still gets an entry, pointing at the offset its content now
                # begins at. **Every physical line has one, continued or not**, and that is
                # the whole correctness of `line_at`: a reader opens the file at the line
                # this reports, so what is wanted is where a token *is*, not which logical
                # line it belongs to. Skipping the entry loses a line number per
                # continuation and the error compounds down the file -- written that way
                # first, and caught by a four-line fixture.
                removed += 1
                i = j + 1
                out_len = len(out)
                starts.append(out_len)
                continue
        out.append(ch)
        if ch == "\n":
            starts.append(len(out))
        i += 1
    return "".join(out), tuple(starts), removed


def mask(src: str) -> Masked:
    """Phases -1 and 0 together: splice, then say what every byte is.

    One forward pass, no lookbehind beyond a single character, and no backtracking. The
    state is which span is open; the only structure it carries is whether a numeric literal
    is in progress, which is what tells `1'000'000` from `'x'`.
    """
    text, starts, continuations = logical(src)
    n = len(text)
    kind: list[Span] = [Span.CODE] * n
    i = 0
    in_number = False
    while i < n:
        ch = text[i]

        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                kind[k] = Span.LINE_COMMENT
            i = j
            in_number = False
            continue

        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            # No nesting: the standard says the first `*/` closes it, whatever is between.
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                kind[k] = Span.BLOCK_COMMENT
            i = j
            in_number = False
            continue

        if ch in "Rr" and i + 1 < n and text[i + 1] == '"' and not _ident_before(text, i):
            end = _raw_string_end(text, i + 2)
            if end is not None:
                for k in range(i, end):
                    kind[k] = Span.RAW_STRING
                i = end
                in_number = False
                continue
            # No closing delimiter anywhere. Fall through and read it as an ordinary
            # string, which is what the rest of the file most likely is -- and which at
            # worst mis-spans one broken file rather than the whole translation unit.

        if ch == '"':
            j = _quoted_end(text, i, '"')
            for k in range(i, j):
                kind[k] = Span.STRING
            i = j
            in_number = False
            continue

        if ch == "'":
            if in_number and i + 1 < n and text[i + 1] in _DIGITS:
                # A digit separator: `1'000`, `0xFF'FF`. Code, not a literal.
                i += 1
                continue
            j = _quoted_end(text, i, "'")
            for k in range(i, j):
                kind[k] = Span.CHAR
            i = j
            in_number = False
            continue

        # Track whether a numeric literal is open, which is the only reason this loop
        # carries any token structure at all.
        if ch.isdigit() and not in_number:
            in_number = not _ident_before(text, i)
        elif in_number and ch not in _DIGITS and ch not in ".xXbBoOeEpP+-_'":
            in_number = False
        i += 1

    return Masked(text=text, kind=tuple(kind), line_starts=starts,
                  continuations=continuations)


def _ident_before(text: str, i: int) -> bool:
    """Is the character before `i` part of an identifier?

    Two callers and two different reasons. `R"` is a raw string only where the `R` opens a
    token -- in `FOOR"x"` it does not, and in `u8R"(…)"` it does, which is why the check is
    on the character before the prefix rather than on the prefix's own spelling. And a digit
    is the start of a numeric literal only where it does not continue an identifier, or
    every `a1'b` would open one.
    """
    return i > 0 and text[i - 1] in _IDENT


def _raw_string_end(text: str, after_quote: int) -> int | None:
    """Offset just past a raw string that opened at `after_quote - 2`, or `None`.

    The delimiter is everything up to the `(`, bounded at 16 characters and forbidding
    whitespace, parentheses and backslash -- all three the standard's. `None` means no
    closing sequence exists, which is a broken file and is reported as one rather than
    swallowing the remainder.
    """
    n = len(text)
    j = after_quote
    while j < n and j - after_quote <= _RAW_DELIM_MAX and text[j] not in _NOT_IN_DELIM:
        j += 1
    if j >= n or text[j] != "(":
        return None
    close = ")" + text[after_quote:j] + '"'
    end = text.find(close, j + 1)
    return None if end < 0 else end + len(close)


def _quoted_end(text: str, start: int, quote: str) -> int:
    """Offset just past an ordinary quoted literal, honouring backslash escapes.

    An unterminated literal ends at the newline rather than running to the end of the file.
    That is not the language's rule -- it is a malformed program either way -- but it bounds
    the damage to the line that is actually wrong, where the other choice reads every
    remaining brace in the file as string and produces a map of nothing.
    """
    n = len(text)
    i = start + 1
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == quote:
            return i + 1
        if ch == "\n":
            return i
        i += 1
    return n
