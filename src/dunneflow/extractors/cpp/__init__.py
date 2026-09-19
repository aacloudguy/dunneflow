"""C++ read the way a reader reads it, with no compiler and no third-party parser.

Stdlib only, the same discipline `extractors/python/` keeps with `ast` and `tokenize` and
`extractors/docs/` keeps with a hand-written scanner. Here it is not a preference: the tool
freezes to a macOS universal2 bundle whose whole runtime dependency list is `pyyaml`, and
neither `tree-sitter` nor `libclang` ships a universal2 wheel -- the same measurement that
put the TypeScript reader on the far side of a pipe.

**And a semantic read was refused on evidence rather than on that principle.** The corpus
this reader was built for is Unreal Engine, and it holds **zero `*.generated.h`**: the tree
has never been built, so UnrealHeaderTool has never run. `clang++ -fsyntax-only` on
`Runtime/Core/Private/Misc/Guid.cpp` dies *fatally* on its first `#include "Misc/Guid.h"` --
one error, no AST, nothing to read. A reader that needs a compilation database would refuse
the one tree it exists for, so this one asks for nothing and answers with less, and says
exactly what less means.

## What that costs, stated once and never softened

No types, no overload resolution, no `#include` following, no macro expansion. `supplies_edges`
is `false` and every call is left external, which the walk names with a count -- a shippable
state the architecture already describes, not a gap. `RESIDUE` at the foot of `extract.py` is
the full list, and it is a deliverable in its own right: a reader whose limits are written
down can be trusted about what it *does* say (rule 1, and design rule 1).

## Five phases, each one forward pass over the last

Order is load-bearing and each phase exists because the one before it makes the next
believable -- `markdown.py`'s *"structure first is what lets the second pass know that a line
inside a fence is code"*, four layers deep instead of two.

1. **splice** -- `lexer.logical()`. Remove `\\` + newline and keep a table back to physical
   lines. First, because a continuation inside a `//` comment swallows the next physical
   line, and every later phase reports through the table rather than by counting newlines.
2. **mask** -- `lexer.mask()`. Which bytes are code, comment, string, char. Nothing above
   this may look at a raw character.
3. **preprocessor** -- `preprocessor.py`. `#include` becomes an import; `#if 0` is the one
   condition the language itself calls dead.
4. **tokenise and match** -- `scopes.py`. The brace tree, and the one name-folding function
   the whole reader shares.
5. **meaning** -- `routines.py`, `control.py`, `calls.py`, `literals.py`.

**No backtracking anywhere.** At 89,000 files a phase that re-reads its own input is not slow,
it is a different program; `extract.py:_segment`'s docstring in the Python reader already
records what `ast.get_source_segment` cost at a two-hundredth of this scale.

## Built in dependency order, and this package does not yet export a reader

`extract_file` is the entry point `ingest._IN_PROCESS` will name, and it is deliberately not
re-exported here until it exists. A package that advertises a name it cannot supply is an
`ImportError` for everything that imports the package at all, including the phases below it
that are finished and tested -- and `plugins/cpp/plugin.json` is written **last**, so the
registry never loads a reader that would find nothing (rule 49).

Landed so far: `lexer.py`.
"""

from __future__ import annotations

__all__: list[str] = []
