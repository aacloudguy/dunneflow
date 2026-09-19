"""Tokens, over the stream the phases below have already made safe to read.

Phase 2. Input is `preprocessor.Preprocessed.code`: comments, literals, directives and dead
regions are all blanked, at the original offsets, so anything found here is code and its
position still indexes back through `Masked.line_at`.

**Every token carries its offset and nothing else about where it is.** A line number is
asked for at the moment it is needed, from the one table that can answer — the same
discipline `make_id` keeps about identity: a position is what you look up, never what you
store beside the thing.

## The one piece of context this pass carries, and why it must

`>>` is a right shift and it is also two closing angle brackets. C++11 made
`TArray<TArray<int>>` legal precisely by saying the parser decides, and a tokeniser that
always emits one `>>` token leaves `names._skip_template` unable to close the outer list:
the fold then returns the whole rest of the expression, or nothing. So this pass tracks
angle depth and **splits `>>` into two `>` while a `<` is open**.

Angle depth is itself only ever a guess — `a < b >> c` exists — so it is bounded: a `<` is
counted as opening a template only when it directly follows an identifier, and the whole
count is abandoned at `;`, `{` or `}`, which no template argument list crosses. What that
buys is `TArray<TArray<FString>>::Add` folding correctly, which in this corpus is the
common case by a wide margin; what it costs is stated in `extract.RESIDUE`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .lexer import Masked, Span


class TokenKind(Enum):
    IDENT = "ident"
    NUM = "num"
    PUNCT = "punct"
    # A string or character literal, carried as **one** token holding the source text.
    #
    # The stream this pass reads has literals blanked — that is what makes a `{` inside a
    # string not a brace — so without this they are whitespace and simply are not there. The
    # cost is not cosmetic: a boundary's target is usually a literal, so `getenv("HOME")`
    # came back with an empty target and so did `fopen("config.ini")`, in a reader whose
    # whole job at a boundary is to say *what* it touches. Found on the probe tree the
    # fingerprint gate reads, which is the smallest C++ file in this repository.
    STR = "str"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    start: int


_IDENT_RE = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_NUM_RE = re.compile(r"\.?\d[\w.']*(?:[eEpP][+-][\w.']*)*")

# Longest first: the scanner takes the first that matches, so `<<=` must be offered before
# `<<`, and `->` before `-`. `<=>` is C++20's three-way comparison and is one token.
_PUNCT = (
    "<=>", "<<=", ">>=", "...", "->*", ".*",
    "::", "->", "++", "--", "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "##",
    "{", "}", "(", ")", "[", "]", ";", ",", ".", "?", ":", "~", "!",
    "+", "-", "*", "/", "%", "&", "|", "^", "=", "<", ">", "#", "@", "\\",
)

# `>>` is only ever split while one of these has opened a template list.
_OPENS_TEMPLATE_AFTER = TokenKind.IDENT

# Spans that become one `STR` token each when the mask is supplied.
_LITERAL_SPANS = (Span.STRING, Span.RAW_STRING, Span.CHAR)


def tokenize(code: str, masked: Masked | None = None) -> list[Token]:
    """One forward pass. No backtracking, no re-scan, no lookbehind past one token.

    `code` is the stream with comments, literals, directives and dead regions blanked —
    everything structural. `masked` is optional and is what puts the **literals back**, as
    single `STR` tokens carrying their source text: same offsets, so a `{` inside one still
    cannot be mistaken for a brace, and an argument that is a string is still an argument.
    """
    out: list[Token] = []
    i, n = 0, len(code)
    angle = 0
    while i < n:
        if masked is not None and masked.kind[i] in _LITERAL_SPANS:
            kind = masked.kind[i]
            j = i
            while j < n and masked.kind[j] is kind:
                j += 1
            out.append(Token(TokenKind.STR, masked.text[i:j], i))
            i = j
            continue
        ch = code[i]
        if ch in " \t\r\n\f\v":
            i += 1
            continue

        if ch.isalpha() or ch in "_$":
            m = _IDENT_RE.match(code, i)
            assert m is not None
            out.append(Token(TokenKind.IDENT, m.group(), i))
            i = m.end()
            continue

        if ch.isdigit() or (ch == "." and i + 1 < n and code[i + 1].isdigit()):
            m = _NUM_RE.match(code, i)
            assert m is not None
            out.append(Token(TokenKind.NUM, m.group(), i))
            i = m.end()
            continue

        for p in _PUNCT:
            if code.startswith(p, i):
                if p == ">>" and angle > 0:
                    # Two closing brackets, not a shift. Emitted as two tokens at their
                    # own offsets so a caller can still slice the source correctly.
                    out.append(Token(TokenKind.PUNCT, ">", i))
                    out.append(Token(TokenKind.PUNCT, ">", i + 1))
                    angle = max(0, angle - 2)
                    i += 2
                    break
                if p == "<" and out and out[-1].kind is _OPENS_TEMPLATE_AFTER:
                    angle += 1
                elif p == ">" and angle > 0:
                    angle -= 1
                elif p in (";", "{", "}"):
                    # No template argument list crosses one of these, so an angle count
                    # that has survived this far was a comparison all along.
                    angle = 0
                out.append(Token(TokenKind.PUNCT, p, i))
                i += len(p)
                break
        else:
            # A byte this reader has no token for. Skipped rather than refused: it is one
            # character of one file, and stopping would cost the whole file's facts.
            i += 1
    return out


def text_of(code: str, first: Token, last: Token) -> str:
    """The source between two tokens, as written.

    A **byte** slice of the already-spliced stream, never a re-rendering (rules 8 and 75):
    what a reader is shown has to be findable in the file they open.
    """
    return code[first.start:last.start + len(last.text)]
