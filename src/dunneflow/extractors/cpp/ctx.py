"""What every phase above the tree needs, assembled once and passed down.

Five views of one file, all at the same offsets, and a module that wants three of them
should not be the module that decides how they are built. `extract.py` builds this; every
other module takes it and reads.

**One offset table, five views** (rule 51). `Masked.line_at` answers about all of them
because none of them ever changes a length — `code_only`, `without_comments` and
`Preprocessed.code` all blank rather than remove, which is the whole reason a token found
in the last of them can still be given a line number by the first.
"""

from __future__ import annotations

from dataclasses import dataclass

from .lexer import Masked
from .preprocessor import Preprocessed
from .scopes import Scope
from .tokens import Token


@dataclass(frozen=True, slots=True)
class Ctx:
    path: str
    module: str
    masked: Masked
    pre: Preprocessed
    toks: list[Token]
    root: Scope

    @property
    def text(self) -> str:
        """The spliced source. Byte slices for `CallArg.expr` come from here (rule 75)."""
        return self.masked.text

    def line(self, offset: int) -> int:
        return self.masked.line_at(offset)

    def tok_line(self, i: int) -> int:
        """The physical line of token `i`, which is the only way a token has one."""
        return self.masked.line_at(self.toks[i].start)

    def slice(self, first: int, last: int) -> str:
        """Source between two token indices, inclusive, **as written**.

        Never re-rendered. What a reader is shown has to be findable in the file they open
        (rules 8 and 75), and this reader has no unparser to re-render with anyway.
        """
        a = self.toks[first]
        b = self.toks[last]
        return self.text[a.start:b.start + len(b.text)]
