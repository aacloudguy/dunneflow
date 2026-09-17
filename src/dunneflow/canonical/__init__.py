"""Whether two writings are the same expression, per language.

A store records what a caller **wrote** -- `call_args.expr` is a byte slice of the file,
never re-rendered, so a reader who goes looking for the string a panel showed them finds it
(rules 8 and 75). That is the right answer for display and the wrong one for a comparison,
which asks a different question about the same string: are these two the same expression.
Mensores has a `typer.echo` whose message was re-wrapped across two lines with not one
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

Adding a language therefore touches two places, and they are two concerns rather than one
split in half: `extractors/<lang>/` reads facts, and `canonical/<lang>.py` says when two
expressions are the same. A language may have the first and not the second, and then its
expressions compare as written -- which is honest, and is what `canonical` does.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .python import canonical_expr

# Which language owns a file, by suffix.
#
# **This is the same question `walk.py` used to answer and never asked.** `LANG_SUFFIX` sat
# there declared and read by nothing at all -- a constant that looked like a decision and
# governed no code (rule 35). It is here now because here is the one place that consults it.
LANG_SUFFIX: dict[str, str] = {".py": "python", ".pyi": "python"}

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
    """
    lang = LANG_SUFFIX.get(Path(path).suffix.lower())
    fn = CANONICAL.get(lang or "")
    return fn(expr) if fn is not None else expr
