"""Which languages a map actually holds, and the sentence that says so.

Five places in this tool told a reader that **only Python is extracted**. Every one of
them was true, none of them asked, and the claim is the one a polyglot build makes false
in the most damaging direction: a page whose whole subject is *absence* — the mirror, the
traceability lane — explaining an absence with a blind spot the map no longer has.

So the fact is read off the graph, `SELECT DISTINCT lang FROM files`, and the sentence is
composed here and nowhere else (rule 51). It is a **count of what was read**, never a list
of the readers this build ships: a build that can read TypeScript and was pointed at a
Python tree must still say Python, or the sentence describes the tool instead of the map
(rule 24).

The spelling of a language in prose is the plugin's own (`PluginManifest.display`), with
the stored key as the fallback — a map may hold a language whose reader is no longer
installed, and calling it `typescript` is honest where inventing a capitalisation is a
guess about somebody else's product name.
"""

from __future__ import annotations

from collections.abc import Sequence

from .. import ingest
from ..store import Store

# Shipped beside the sentence it produces, because a claim whose query returns something
# else is worse than a claim with no query at all (rule 13).
READ_SQL = "SELECT DISTINCT lang FROM files WHERE lang <> '' ORDER BY lang"


def read(store: Store) -> list[str]:
    """Every language this map holds a file of, in order."""
    return [str(r[0]) for r in store.conn.execute(READ_SQL)]


COUNTS_SQL = ("SELECT lang, COUNT(*) n FROM files WHERE lang <> '' "
              "GROUP BY lang ORDER BY n DESC, lang")


def counts(store: Store) -> dict[str, int]:
    """How many files of each language this map holds.

    The list of languages is one question and *how much of the map each one is* is
    another: a tree read as 628 Python files and 4 TypeScript ones is not a polyglot map,
    and a reader looking at a page of absences is owed the second number as well as the
    first (rule 32).
    """
    return {str(r[0]): int(r[1]) for r in store.conn.execute(COUNTS_SQL)}


def display(lang: str) -> str:
    """How this language is spelled in a sentence: its plugin's word, or its own key."""
    plugin = ingest.PLUGINS.get(lang)
    return plugin.manifest.display if plugin is not None else lang


def named(langs: Sequence[str]) -> str:
    """`Python`, `Python and TypeScript`, `Python, TypeScript and Go`."""
    words = [display(x) for x in langs]
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    return f"{', '.join(words[:-1])} and {words[-1]}"


def only(langs: Sequence[str]) -> str:
    """*Only Python was extracted* — the claim, with what was read filled in.

    **Three answers, never two** (design rule 21). A map that holds no source at all says
    so plainly: it is a different fact from *one language was read*, and a reader looking
    at a page of absences is entitled to know which of the two produced it.
    """
    if not langs:
        return ("**No source was extracted at all.** Every absence on this page is an "
                "absence from a graph with nothing in it to be absent from.")
    if len(langs) == 1:
        return (f"**Only {named(langs)} was extracted.** A word living in a shell script, "
                f"a template, a front end, a sibling service or a database migration is "
                f"absent from this graph and present in the product.")
    return (f"**{named(langs)} were extracted, and nothing else.** A word living in a "
            f"language none of them reads — a shell script, a template, a sibling service "
            f"or a database migration — is absent from this graph and present in the "
            f"product.")


def only_plain(langs: Sequence[str]) -> str:
    """The same claim without Markdown, for the two surfaces that print to a terminal."""
    if not langs:
        return ("no source was extracted at all: absent from this graph says nothing "
                "about the product")
    verb = "is" if len(langs) == 1 else "are"
    return (f"only {named(langs)} {verb} extracted: absent from this graph is not absent "
            f"from the product")
