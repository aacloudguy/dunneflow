"""What every phase above the tree needs, assembled once and passed down.

`extract.py` builds it; everything else takes it and reads. One offset table serves every
view because nothing ever changes a length — the mask blanks rather than removes (rule 51).
"""

from __future__ import annotations

from dataclasses import dataclass

from .lexer import Masked
from .scopes import Scope
from .tokens import Token


@dataclass(frozen=True, slots=True)
class Ctx:
    path: str
    module: str
    package: str
    masked: Masked
    toks: list[Token]
    root: Scope

    @property
    def text(self) -> str:
        return self.masked.text

    def line(self, offset: int) -> int:
        return self.masked.line_at(offset)

    def tok_line(self, i: int) -> int:
        return self.masked.line_at(self.toks[i].start)

    def slice(self, first: int, last: int) -> str:
        """Source between two token indices, inclusive, **as written** (rules 8 and 75)."""
        a, b = self.toks[first], self.toks[last]
        return self.text[a.start:b.start + len(b.text)]
