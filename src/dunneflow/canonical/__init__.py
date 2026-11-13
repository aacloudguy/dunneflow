"""Whether two writings are the same expression, per language.

A store records what a caller **wrote** -- `call_args.expr` is a byte slice of the file,
never re-rendered, so a reader who goes looking for the string a panel showed them finds it
(rules 8 and 75). That is the right answer for display and the wrong one for a comparison,
which asks a different question about the same string: are these two the same expression.
Lictores has a `typer.echo` whose message was re-wrapped across two lines with not one
character of its content changed, and comparing what was written puts its caller in
*behaves differently* -- the band that promises what a routine **does** moved.

So this is where that question is answered, and the answer is per language.

**Beside `extractors/` rather than inside it, and that placement is load-bearing.**
`detectors.lang_extraction_inputs()` globs `extractors/python/*.py` into that language's
cache key,
because rule 12 says a cached fact is valid only if the source *and the tool that read it*
are unchanged. Nothing here is read by extraction: a canonicaliser cannot change a single
fact, only whether two facts are judged equal. Living in that glob, editing one would
discard every graph on the machine -- sealed snapshots included, which exist precisely so
they can be read after their source tree is gone (rules 25 and 62). The key's own docstring
sets the test: *scope is decided by asking what this extraction actually reads.*

Adding a language therefore touches three places, and they are three concerns rather than
one split up: `extractors/<lang>/` reads facts, `canonical/<lang>.py` says when two
expressions are the same, and `resolve/<lang>/calls.py` says which definition a call meant.
A language may have the first and neither of the others: its expressions then compare as
written -- which is honest, and is what `canonical` does -- and its calls are left external,
which the map says out loud rather than passing them to somebody else's name rules.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..ingest import language_of
from .python import canonical_expr

# **Which language owns a file is `ingest`'s answer, and this module stopped having one of
# its own on 2026-09-18.** `LANG_SUFFIX` was declared here as `{".py": "python", ".pyi":
# "python"}` under a comment reading *"it is here now because here is the one place that
# consults it"* -- and `ingest/__init__.py`'s own docstring has said since it was written
# that the table **moved there** and became derived from the manifests, quoting that very
# sentence as the thing that stopped being true. The move was recorded and the copy was
# left behind, so the file that says it took the question over was not the one being asked
# it: `canonical()` read the hand-written table and nothing else did.
#
# It had already drifted, which is what a second answer always does. It did not know `.ts`
# existed -- so from the day TypeScript landed, a canonicaliser for it could have been
# written, registered in `CANONICAL` below, and **never once reached**, because the lookup
# that decides whether to call one could not name the language. Nothing failed; the
# comparison simply fell through to *as written* for every TypeScript expression in every
# map, which is exactly what this module's honest fallback looks like from the outside
# (rule 49, and rule 51 for why one question may not have two tables).

# How each language says two writings are the same expression. A language with no entry has
# no canonical form here, and `canonical` says so by returning what it was given.
CANONICAL: dict[str, Callable[[str], str]] = {"python": canonical_expr}


def canonical(expr: str, path: str | Path) -> str:
    """`expr` as the language of `path` would write it, or unchanged if nobody can say.

    The seam that lets `changes.py` ask whether two expressions are the same expression
    without knowing what a language is. It learns that a canonical form *exists*; how one is
    made stays with the language that owns the suffix.

    **Unchanged is an answer, not a failure.** Where no language claims the suffix, the
    comparison falls back to what was written -- the honest question when there is nothing
    better to ask, and not a plausible value standing in for a measurement (rule 49).

    **Two ways to arrive at that fallback, and they are different facts.** No reader claims
    the suffix at all, or one does and has no canonical form here. Both correctly compare as
    written, and neither is inferred from the other -- which is why `language_of` is asked
    first rather than `CANONICAL` being keyed on the suffix directly.
    """
    lang = language_of(path)
    fn = CANONICAL.get(lang or "")
    return fn(expr) if fn is not None else expr
