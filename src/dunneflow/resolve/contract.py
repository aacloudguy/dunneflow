"""What a resolver is, and the one thing it is never allowed to do.

`ingest/contract.py` says what a *reader* is; this says what a **resolver** is, and the
two are deliberately the same shape one subject over. A reader turns bytes into facts. A
resolver turns one of those facts -- a call expression, which knows only how it was
spelled -- into an edge, or into an honest statement that there is no edge to be had.

**A resolver never writes to the store and never counts.** It answers one call row at a
time and hands back a `Decision`; the driver in `calls.py` does the arithmetic and the one
`UPDATE`. That is rule 51 written into the seam rather than remembered at four call sites:
v1 had three separate places that spelled *no edge*, each getting `external`, `suppressed`
and `ambiguous` right on its own, and a fourth resolver would have had to get them right
again from reading the other three.

The types live here rather than beside the driver because the driver imports the
resolvers and the resolvers import these -- one module for the contract is what stops
that being a cycle.

**What each tier means is per language, and it is written down here because this is what a
third resolver's author reads.** `Confidence` is one enum and the argument behind it is
not; flattening the two would make a word mean whatever the newest resolver decided.

**python.** `CERTAIN` is an import, the enclosing module or the enclosing class pinning the
name. `INFERRED` is *exactly one routine in the whole program has that name*. External is no
match at all, a builtin, or a boundary.

**typescript.** `CERTAIN` is the checker resolving the call to a declaration inside one
routine of this map. `INFERRED` is **never produced**. External is a target outside the map,
several competing declarations, or a call the checker could not resolve.

The TypeScript row is the opinionated half and it is deliberate. Where a checker gives
several declarations -- a merged overload set, an `any`-typed receiver, `obj[k]()` -- the
honest answer is **external with the candidate count in `ambiguous`**, exactly as Python
already answers a name collision. Not `INFERRED`: that word is a claim that a
name-uniqueness argument was made, and for a checker none was made or needed. Marking a
supplied edge `INFERRED` would blur precisely what rule 6 says never to blur, and would
make *"Inferred facts: none"* at `GET /api/about` a false sentence.

**`Edge` and `NoEdge` rather than `str | None`.** A missing target carries two facts the
driver cannot recover: how many definitions competed for the name, and whether the match
was *rejected as implausible* or simply never found. Those are different things -- rule 6
says confidence and certainty are different questions, and this is the same distinction
one level down -- and collapsing them to `None` is how `ambiguous` stops being a number
anybody can act on.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from ..schema import Confidence
from ..store import Store


@dataclass(frozen=True, slots=True)
class Edge:
    """A call site whose target this resolver is prepared to name.

    `inherited` is not Python's alone despite being paid for there: it says the target was
    reached by following a **declared** supertype rather than by a direct match, which is
    a thing any language with inheritance can say. It is counted separately because an
    edge recovered that way is the one most worth being able to find again.

    `supplied` says the far end was **handed over by a toolchain that had already resolved
    it**, rather than argued for from names. It is `inherited`'s shape and it is counted
    for a sharper reason: the two provenances answer different questions and only one of
    them can be wrong about a rebinding. A map that folded them would be unable to say how
    much of itself is a checker's answer and how much is this tool's inference — which is
    the claim `GET /api/about` makes in two rows.
    """

    target: str
    confidence: Confidence
    inherited: bool = False
    supplied: bool = False


@dataclass(frozen=True, slots=True)
class NoEdge:
    """No target, and the two facts that say which kind of *no* this is.

    `candidates` is how many definitions competed -- more than one is why an edge went
    missing, and recording it is what makes a lost connection visible in a program that may
    itself be broken. Zero means *nothing was counted here*, which is its own answer: the
    from-import-outside-the-program case never looks for rivals, because the import has
    already settled the question.

    `suppressed` is *rejected as implausible* as opposed to *merely absent*. The two are
    both fields because one row can be both: a bare call to a builtin is suppressed **and**
    has its rivals counted, and flattening the pair would silently move `ambiguous`.
    """

    candidates: int = 0
    suppressed: bool = False
    # **Not external, and still no edge.** The qualname of one of this program's own
    # classes that the call builds, when that class has no constructor routine to point at
    # -- a dataclass, an enum, a class that inherits `__init__` from outside. The thing
    # built is here; only the routine is missing, because there is none (BACKLOG 14).
    constructs: str = ""
    # **Where the map stops, and why**, where the resolver knows (`SuppliedEdge.frontier`
    # and `reason`, schema 17). Carried to `calls.frontier` and `calls.reason`; empty is
    # *nobody said*, never *nothing to say*.
    frontier: str = ""
    reason: str = ""


Decision = Edge | NoEdge


@dataclass(slots=True)
class ResolveStats:
    total: int = 0
    certain: int = 0
    inferred: int = 0
    external: int = 0
    suppressed: int = 0  # matches rejected as implausible rather than merely absent
    ambiguous: int = 0   # edges lost because several definitions shared the name
    inherited: int = 0   # edges recovered by following a base class
    # Edges a reader's own toolchain handed over, as against edges this tool argued for.
    # Beside `certain` rather than inside it: a supplied edge is CERTAIN, but so is a
    # Python edge pinned by an import, and *how many of these did we not have to guess*
    # is the question this chunk exists to be able to answer (rule 32).
    supplied: int = 0
    # Calls that build one of this program's own classes and have no routine to point at
    # (`NoEdge.constructs`). Neither resolved nor external, so a figure that added
    # `resolved` and `external` up to `total` would be short by exactly these (rule 32).
    constructions: int = 0
    # One entry per language the map holds, filled on the total only, so a figure can say
    # what it counts (rule 32). A map of one language reads exactly as it always did.
    langs: dict[str, ResolveStats] = field(default_factory=dict)
    # Languages whose calls were left external because this build has no resolver for
    # them -- named, because *nothing resolved* and *nothing to resolve* look identical
    # in the numbers and only one of them is a hole (design rule 1).
    unresolved_langs: dict[str, int] = field(default_factory=dict)

    @property
    def resolved(self) -> int:
        return self.certain + self.inferred

    def rate(self) -> float:
        return (self.resolved / self.total * 100) if self.total else 0.0

    def unresolved_sentence(self) -> str:
        """*typescript: 5,119 calls left external — this build has no resolver for it.*

        **The one place those words live** (rule 51), because the field was written in
        chunk 6 and read by nothing until chunk 9 made it fire. `resolve/calls.py`'s own
        docstring already promised the language would be *named*, and `unresolved_langs`
        was filled and printed nowhere — rule 35's shape, an empty view with no symptom,
        in the sentence that is the whole difference between *nothing resolved* and
        *nothing to resolve*.

        Empty where every language has a resolver, so a map of one language reads exactly
        as it always did.
        """
        if not self.unresolved_langs:
            return ""
        listed = ", ".join(
            f"{lang} {n:,}" for lang, n in sorted(self.unresolved_langs.items())
        )
        one = len(self.unresolved_langs) == 1
        return (
            f"left external for want of a resolver: {listed} — this build reads "
            f"{'that language' if one else 'those languages'} and cannot yet see the far "
            f"end of {'its' if one else 'their'} calls"
        )

    def add(self, other: ResolveStats) -> None:
        """Fold one language's figures into the total. Never the `langs` map itself."""
        self.total += other.total
        self.certain += other.certain
        self.inferred += other.inferred
        self.external += other.external
        self.suppressed += other.suppressed
        self.ambiguous += other.ambiguous
        self.inherited += other.inherited
        self.supplied += other.supplied
        self.constructions += other.constructions


@dataclass(frozen=True, slots=True)
class CallRow:
    """One call site, as much of it as any resolver is given.

    Deliberately not a `sqlite3.Row`: a resolver that could reach the other columns could
    reach the whole store through them, and `rowid` is the driver's business -- it is the
    address the one `UPDATE` writes to, and a resolver has no use for it that is not a
    second way to write.

    **`site_id` is here and `rowid` is not, and the difference is the whole of rule 30.**
    A rowid is a position in one database; `site_id` is this call's identity, derived from
    the caller, the expression and an ordinal and never from a line. A reader that supplies
    an edge names the site by that identity, so a resolver that had to match on anything
    else -- file and line, say -- would be a second identity function for call sites, in
    the one place the two could disagree without anybody noticing.
    """

    file: str
    caller_id: str
    callee_expr: str
    site_id: str = ""
    # The callee is a name the calling routine binds itself (`CallSite.bound_locally`), so
    # what it calls is a value, not a definition anything could be matched to by name.
    bound_locally: bool = False


class Resolver(Protocol):
    """One language's answer to *which definition did this call mean*.

    Handed every call row of its own language that is **not** already known to touch a
    boundary -- that judgement is the driver's (rule 2) and a resolver never sees one --
    and the store, for building whatever index it needs. It yields one decision per row,
    **in the order it was given them**, which is what lets the driver pair decisions with
    rowids without a resolver ever holding one.

    A resolver that cannot answer at all yields `NoEdge()` rather than raising: a call it
    cannot see the far end of is an external call, which is the honest answer and is how a
    language whose toolchain supplies edges reports the ones it did not supply (rule 26).
    """

    def __call__(self, store: Store, lang: str,
                 rows: Sequence[CallRow]) -> Iterable[Decision] | Iterator[Decision]:
        ...
