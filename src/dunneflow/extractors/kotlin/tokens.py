"""Tokens, over the stream the mask has already made safe to read.

Phase 1. Its own module rather than the C++ reader's for the reason stated there: a shared
one would live in neither language's stamp, and editing it would change what both read while
invalidating nothing (rule 12).

## Two things Kotlin's tokeniser has to know that C++'s does not

* **A backtick-quoted identifier is one name.** ``fun `reads a deck from disk`()`` is legal
  and is how Kotlin test suites spell their names — a tokeniser that splits on the spaces
  finds four identifiers and no function. The whole run between backticks is one `IDENT`.
* **`?.`, `?:` and `!!` are single tokens.** Split into `?` and `.` the null-safe call reads
  as a ternary followed by a member access, and `names.fold` stops at the `?` — so every
  `a?.b()` in the corpus, which is most of the calls in idiomatic Kotlin, becomes unnameable.

Literals arrive as single `STR` tokens carrying their source text, at their own offsets, the
same way the C++ reader learned to do it: a boundary's target is usually a literal, and a
stream with literals blanked has none.
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
    STR = "str"


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    text: str
    start: int


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUM_RE = re.compile(r"\.?\d[\w.]*")

# Longest first. `?.`, `?:` and `!!` before their halves; `::` before `:`.
_PUNCT = (
    "...", "?:", "?.", "::", "->", "==", "!=", "<=", ">=", "&&", "||", "!!", "++", "--",
    "+=", "-=", "*=", "/=", "%=", "..", "@",
    "{", "}", "(", ")", "[", "]", ";", ",", ".", "?", ":", "!", "<", ">",
    "+", "-", "*", "/", "%", "&", "|", "^", "=", "$", "#", "~",
)

_LITERAL_SPANS = (Span.STRING, Span.RAW_STRING, Span.CHAR)


def tokenize(code: str, masked: Masked | None = None) -> list[Token]:
    """One forward pass, no backtracking. `masked` puts the literals back as `STR` tokens."""
    out: list[Token] = []
    i, n = 0, len(code)
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

        if ch == "`":
            j = code.find("`", i + 1)
            if j < 0:
                i += 1
                continue
            out.append(Token(TokenKind.IDENT, code[i + 1:j], i))
            i = j + 1
            continue

        if ch.isalpha() or ch == "_":
            m = _IDENT_RE.match(code, i)
            assert m is not None
            out.append(Token(TokenKind.IDENT, m.group(), i))
            i = m.end()
            continue

        if ch.isdigit():
            m = _NUM_RE.match(code, i)
            assert m is not None
            out.append(Token(TokenKind.NUM, m.group(), i))
            i = m.end()
            continue

        for p in _PUNCT:
            if code.startswith(p, i):
                out.append(Token(TokenKind.PUNCT, p, i))
                i += len(p)
                break
        else:
            i += 1
    return out
