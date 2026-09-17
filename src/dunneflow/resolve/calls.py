"""Turning call expressions into edges — the driver.

This module used to *be* Python's resolver: it split `callee_expr` on dots, knew `self`
and `cls`, walked `__init__.py` packages, and asked this interpreter what its builtins
were. All of that is `resolve/python/calls.py` now, and what is left here is the part that
is true whatever language is being read.

**Three things live here so that a new resolver inherits them rather than remembering
them** (rule 51):

* **A call that touches a boundary is never also an internal edge** (rule 2). `conn.execute
  (...)` is sqlite3, not a local routine that happens to be called `execute`; resolving it
  inward invented 919 edges on the first real target and made an unrelated function look
  like the most depended-upon code in the program. The judgement is made *before* dispatch,
  so a resolver never sees such a row and cannot be the one to get it wrong.
* **One place writes `UPDATE calls SET callee_id`.** v1 had three, each getting `external`,
  `suppressed` and `ambiguous` right on its own; a fourth resolver would have had to get
  them right again by reading the other three. A resolver now answers `Edge` or `NoEdge`
  and does no arithmetic at all.
* **The counting.** Per language *and* in total, because a figure has to say what it counts
  (rule 32) and *4,823 calls* over a polyglot map says nothing about which half resolved.

**Three answers where a language has no resolver, never two** (design rule 21). A language
with one is resolved; a language with none has every call left external **and is named**,
with how many calls that was. The second is not hypothetical and not a placeholder: a
TypeScript map arrives one chunk before TypeScript's supplied edges do, and a map with
routines, boundaries and no internal TypeScript edges is honest and shippable — as long as
it says so. Silence there would read exactly like a program that calls nothing.
"""

from __future__ import annotations

from ..schema import Confidence
from ..store import Store
from .contract import CallRow, Edge, Resolver, ResolveStats
from .python.calls import resolve as _resolve_python

# `ResolveStats` is re-exported deliberately: it was this module's type for a year and
# `cli.py` and fourteen test files ask this module for it. The contract moved; the address
# did not (rule 30).
__all__ = ["RESOLVERS", "ResolveStats", "resolve_calls"]

# Which resolver answers for which language. The registry's shape one subject over, and
# named here rather than derived from a dotted string in a manifest for the same reason
# `ingest._IN_PROCESS` is: what runs in this process is decided by a file that is under
# test, never by a data file.
RESOLVERS: dict[str, Resolver] = {"python": _resolve_python}


def resolve_calls(store: Store) -> ResolveStats:
    """Resolve every call site in the store, in place.

    One pass over `calls` joined to `files` for the language, grouped, dispatched, and
    written once. The join is how a call finds its language: `calls` has no `lang` column
    of its own, and adding one would be a second copy of a fact `files` already states
    (rule 40).
    """
    stats = ResolveStats()
    updates: list[tuple[str | None, str, int, int, int]] = []

    # Grouped in Python rather than by `ORDER BY lang`, because the rowid order within a
    # language has to be the order the decisions come back in and a sort would be a second
    # thing to keep in step.
    work: dict[str, list[tuple[int, CallRow]]] = {}
    for row in store.query(
        "SELECT c.rowid AS rowid, c.file AS file, c.caller_id AS caller_id,"
        "       c.callee_expr AS callee_expr, c.at_boundary AS at_boundary,"
        "       f.lang AS lang"
        "  FROM calls c LEFT JOIN files f ON f.path = c.file"
    ):
        stats.total += 1
        lang = row["lang"]
        if lang is None:
            # `calls.file` is written from a `FileFacts` that also wrote the `files` row,
            # so this cannot happen — and skipping it would leave a call resolved by
            # nobody with no symptom anywhere, which is `walk._by_language`'s argument one
            # table over (rule 49).
            raise ValueError(
                f"the call to {row['callee_expr']!r} at {row['file']} belongs to no file "
                f"in this map. `calls` and `files` are written from one set of facts, so "
                f"a call whose file is not there means the graph has been written by two "
                f"things that disagree."
            )
        per = stats.langs.setdefault(lang, ResolveStats())
        per.total += 1

        if row["at_boundary"]:
            # Rule 2, and it is judged here so that no resolver can decide otherwise.
            per.external += 1
            per.suppressed += 1
            updates.append((None, Confidence.INFERRED.value, 1, 0, row["rowid"]))
            continue

        work.setdefault(lang, []).append((row["rowid"], CallRow(
            file=row["file"], caller_id=row["caller_id"],
            callee_expr=row["callee_expr"],
        )))

    for lang, pairs in work.items():
        per = stats.langs[lang]
        resolver = RESOLVERS.get(lang)
        if resolver is None:
            # Every call left external, and the language named with its count. Not a
            # failure and not silence: this build cannot see the far end of these calls,
            # which is what external means (rule 26).
            stats.unresolved_langs[lang] = len(pairs)
            per.external += len(pairs)
            updates.extend(
                (None, Confidence.INFERRED.value, 1, 0, rowid) for rowid, _ in pairs
            )
            continue

        rows = [r for _, r in pairs]
        decisions = list(resolver(store, lang, rows))
        if len(decisions) != len(rows):
            # A resolver pairs with its rows by position, so a short or long answer is not
            # a smaller map — it is every decision after the discrepancy landing on the
            # wrong call site. Refused rather than zipped (rule 49).
            raise ValueError(
                f"the {lang} resolver was given {len(rows):,} call sites and answered "
                f"{len(decisions):,}. Decisions are paired with rows by position, so an "
                f"answer of the wrong length does not lose edges, it misplaces them."
            )

        for (rowid, _), d in zip(pairs, decisions, strict=True):
            if isinstance(d, Edge):
                if d.confidence is Confidence.CERTAIN:
                    per.certain += 1
                else:
                    per.inferred += 1
                if d.inherited:
                    per.inherited += 1
                updates.append((d.target, d.confidence.value, 0, 0, rowid))
            else:
                # An edge lost to ambiguity is not the same as a call that leaves the
                # program. Recording the candidate count makes a missing connection
                # visible instead of invisible — which is the whole point when the
                # program under study may itself be broken.
                if d.suppressed:
                    per.suppressed += 1
                if d.candidates > 1:
                    per.ambiguous += 1
                updates.append((None, Confidence.INFERRED.value, 1,
                                d.candidates if d.candidates > 1 else 0, rowid))

    # `total` is already the whole count; the rest is folded up from the languages so the
    # published figure and the per-language ones cannot disagree (rule 13).
    whole = stats.total
    stats.total = 0
    for per in stats.langs.values():
        stats.add(per)
    if stats.total != whole:
        raise ValueError(
            f"{whole:,} call sites were read and the per-language figures add up to "
            f"{stats.total:,}."
        )

    with store.batch():
        store.conn.executemany(
            "UPDATE calls SET callee_id = ?, confidence = ?, external = ?, ambiguous = ?"
            " WHERE rowid = ?",
            updates,
        )
    return stats
