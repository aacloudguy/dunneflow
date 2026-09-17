"""Which definition a TypeScript call meant — looked up, never argued for.

`resolve/python/calls.py` is four hundred lines of argument: dotted parts, receiver words,
relative imports, base classes, a bare name that exactly one routine in the program
answers to. None of that is here, and its absence is the whole point of the chunk. The
TypeScript checker resolved the symbol inside the plugin's own process; what reaches this
module is `supplied_edges`, and the only thing the host can do that the plugin could not is
**turn a location into an id**.

**Targets arrive as locations and never as ids** (`PLAN-v2.md` §1g). A plugin minting ids
would be a second implementation of `make_id` in the one place a disagreement is least
recoverable — two ids that look exactly like ids and match nothing in the map, with no
symptom anywhere but a thin graph. So the plugin says *this file, this line, this name* and
this module asks the routines it stored.

**Four answers, and three of them are honest forms of *no*.**

| what the reader said | what this returns |
|---|---|
| nothing at all about this call site | `NoEdge()` — external, never guessed by name |
| several declarations competed | `NoEdge(candidates=n)` — ambiguous, as a name collision is |
| a location this map holds a routine at | `Edge(id, CERTAIN, supplied=True)` |
| a location this map holds no routine at | `NoEdge()` — external by construction (rule 26) |

The fourth is the one worth dwelling on: a call into `node_modules`, into `lib.dom.d.ts`
or into a `.svelte` file the walk never read is a call that **certainly happens** and whose
far end this map cannot see. That is what external means, and it is reached here by
construction rather than by a rule somebody had to remember.

**A bare name is never matched.** `resolve/python/calls.py`'s `INFERRED` tier exists
because Python cannot always say which definition a name meant and *exactly one routine has
that name* is a real argument. A checker needs no such argument and did not make one, so
this module has no `INFERRED` branch at all — not an unused one, none. Marking a supplied
edge `INFERRED` would blur precisely what rule 6 says never to blur, and would make
*"Inferred facts: none"* at `GET /api/about` false (see `resolve/contract.py`'s table).

**How a location becomes a routine, and why the fallback is counted rather than trusted.**
The plugin computes a declaration's line with the same function the extractor computes
`line_start` with, walking the same source file objects, so an **exact** `(file,
line_start)` match is what should happen every time. It is still not the only branch,
because "should" is an argument and this tool measures: a declaration can be reported at a
line the extractor recorded differently — a decorated member, an arrow inside a call — and
the honest recovery is the innermost routine whose span contains the line, which is
`resolve/shape.py`'s and `web/search.py`'s existing shape. **Both are counted** and the
counts ride out on `Report`, because a fallback doing real work means the two sides disagree
about where a declaration starts, and that is a defect to find rather than a convenience to
enjoy (rule 49: a plausible answer is what hides the failure).

**And the name is checked, not merely carried.** A line that has drifted lands on *some*
routine, and a silently wrong edge is worse than a missing one (rule 1). Where the reader
named the target and the routine found is called something else, no edge is returned and the
mismatch is counted.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field

from ...schema import Confidence
from ...store import Store
from ..contract import CallRow, Decision, Edge, NoEdge

LANG = "typescript"


@dataclass(slots=True)
class Report:
    """What the lookup did, for the run to say out loud.

    Not `ResolveStats`: these are facts about **this module's** matching and not about the
    map's edges, and folding them in would put a diagnostic in the row a reader reads as a
    count of the program (rule 32). Held on the module's last run, read by the one caller
    that wants it and by the tests.
    """

    supplied: int = 0        # rows the reader gave a target for
    exact: int = 0           # matched a routine's own first line
    by_span: int = 0         # matched by the innermost routine containing the line
    no_routine: int = 0      # a location this map holds no routine at: external
    name_mismatch: int = 0   # a location whose routine is called something else
    ambiguous: int = 0       # several declarations competed: no edge
    unsupplied: int = 0      # call sites the reader said nothing about

    def sentence(self) -> str:
        """*typescript: 3,104 edges supplied, 12 landed on no routine.*

        Empty where nothing was supplied, so a map with no TypeScript in it reads exactly
        as it always did. The two recovery figures are said **only when they are not
        nought**, because a line that reports a zero every run is a line nobody reads by
        the time it matters.
        """
        if not self.supplied and not self.unsupplied:
            return ""
        parts = [f"{self.supplied:,} supplied"]
        if self.by_span:
            parts.append(f"{self.by_span:,} matched by span rather than by first line")
        if self.name_mismatch:
            parts.append(f"{self.name_mismatch:,} landed on a routine of another name")
        if self.no_routine:
            parts.append(f"{self.no_routine:,} named a place this map holds no routine — "
                         f"external")
        if self.ambiguous:
            parts.append(f"{self.ambiguous:,} had several declarations — no edge")
        if self.unsupplied:
            parts.append(f"{self.unsupplied:,} the checker could not resolve")
        return f"{LANG} edges: " + ", ".join(parts)


# The last run's report, for `cli.py` to print. A module-level value rather than a return
# is what keeps `Resolver`'s signature the seam's and not this language's -- the protocol
# yields decisions and nothing else, and a resolver that widened it would make every other
# resolver's signature a lie (rule 30).
LAST = Report()


@dataclass(slots=True)
class _Routines:
    """Every TypeScript routine in the map, indexed for a location lookup.

    Two indexes over one pass, because the question is asked two ways and a second pass
    would be a second answer. `first` is the line a routine starts on; `spans` is the same
    routines per file, sorted by where they start, so the innermost one containing a line
    is found by a bisect and a short walk back rather than by scanning a file's routines.
    """

    first: dict[tuple[str, int], list[tuple[str, str]]] = field(default_factory=dict)
    spans: dict[str, list[tuple[int, int, str, str]]] = field(default_factory=dict)
    starts: dict[str, list[int]] = field(default_factory=dict)


def _index(store: Store) -> _Routines:
    ix = _Routines()
    for r in store.query(
        "SELECT id, name, file, line_start, line_end FROM routines WHERE lang = ?",
        (LANG,),
    ):
        key = (r["file"], r["line_start"])
        ix.first.setdefault(key, []).append((r["id"], r["name"]))
        ix.spans.setdefault(r["file"], []).append(
            (r["line_start"], r["line_end"], r["id"], r["name"])
        )
    for file, rows in ix.spans.items():
        rows.sort()
        ix.starts[file] = [row[0] for row in rows]
    return ix


def _containing(ix: _Routines, file: str, line: int) -> tuple[str, str] | None:
    """The innermost routine whose span holds `line`, or nothing.

    Innermost is *latest start that still contains the line*, which is what a nested
    function needs: an arrow inside a method is inside the method's span too, and the
    method is not what the checker pointed at. Bounded to the routines that start at or
    before the line (rule 55: the bound is on the work, not only on the answer).
    """
    starts = ix.starts.get(file)
    if not starts:
        return None
    rows = ix.spans[file]
    for i in range(bisect_right(starts, line) - 1, -1, -1):
        line_start, line_end, rid, name = rows[i]
        if line_start <= line <= line_end:
            return rid, name
    return None


def _supplied(store: Store) -> dict[str, tuple[str, int, str, int]]:
    """`site_id -> (file, line, name, candidates)`, as this language's reader said it.

    One statement and one dictionary rather than a query per call site: `calls` and
    `supplied_edges` are two tables written by two passes, and joining them in SQL would
    make the resolver's answer depend on an ordering the driver owns (rule 66). The map's
    whole TypeScript answer is a few thousand rows.
    """
    return {
        r["site_id"]: (r["file"], r["line"], r["name"], r["candidates"])
        for r in store.query(
            "SELECT site_id, file, line, name, candidates FROM supplied_edges"
            " WHERE lang = ?", (LANG,)
        )
    }


def resolve(store: Store, lang: str, rows: Sequence[CallRow]) -> list[Decision]:
    """One decision per row, in the order the rows were given.

    `lang` is accepted and not read, as Python's is: the signature is the seam's, and this
    resolver is registered for exactly one language.

    **A list rather than a generator**, unlike Python's, and for one reason: `LAST` is
    finished when the last row is, so a caller that read one decision and stopped would
    leave the report describing the run before it. The driver drains it either way; a trap
    that only springs for a second caller is one nobody finds (rule 35).
    """
    global LAST                                        # noqa: PLW0603 — see `LAST`
    out: list[Decision] = []
    report = Report()
    supplied = _supplied(store)
    ix = _index(store)

    for row in rows:
        found = supplied.get(row.site_id)
        if found is None:
            # The checker said nothing about this call. Left external and **never guessed
            # by name** -- that refusal is the whole payoff of reading with the native
            # toolchain rather than around it (rule 1).
            report.unsupplied += 1
            out.append(NoEdge())
            continue

        file, line, name, candidates = found
        if not file:
            # Several declarations competed, or the checker declined. `candidates` is the
            # number; the driver turns >1 into `ambiguous` and 0 into a plain external.
            if candidates > 1:
                report.ambiguous += 1
            else:
                report.unsupplied += 1
            out.append(NoEdge(candidates=candidates))
            continue

        report.supplied += 1
        hit: tuple[str, str] | None = None
        exact = ix.first.get((file, line))
        if exact is not None and len(exact) == 1:
            hit = exact[0]
            report.exact += 1
        elif exact is not None:
            # Two routines starting on one line, which TypeScript can write --
            # `const f = () => g(), h = () => i()`. The name is what tells them apart, and
            # where it does not, nothing does (rule 5: never match on a bare name).
            named = [pair for pair in exact if pair[1] == name]
            if len(named) == 1:
                hit = named[0]
                report.exact += 1
            else:
                # Counted as ambiguous here because that is what the driver will make of
                # it: a figure in this report that disagreed with the figure beside it
                # would be two numbers about one thing (rule 40).
                report.ambiguous += 1
                out.append(NoEdge(candidates=len(exact)))
                continue
        else:
            hit = _containing(ix, file, line)
            if hit is not None:
                report.by_span += 1

        if hit is None:
            # A location this map holds no routine at: node_modules, a `.d.ts`, a `.svelte`
            # file the walk never read. The call happens and the far end is not here, which
            # is what external means (rule 26).
            report.no_routine += 1
            out.append(NoEdge())
            continue

        rid, found_name = hit
        if name and found_name != name:
            # The line landed on a routine, and it is not the one the reader named. A
            # silently wrong edge is worse than a missing one (rule 1), so this is no edge
            # and a counted disagreement rather than a quiet acceptance.
            report.name_mismatch += 1
            out.append(NoEdge())
            continue

        out.append(Edge(rid, Confidence.CERTAIN, supplied=True))

    LAST = report
    return out
