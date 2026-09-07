"""ALGORITHMS: the loops and decisions worth reading, served as a worklist.

`resolve/shape.py` judges every control point in the program. This arranges the ones it
found into lanes, and it is a **doorway** rather than a report -- the Curiosities and
Anomalies precedent, a page reached from the navigator and not a fourth centre mode.

**Four lanes, and a fifth that is empty on purpose.** A rate, a fork, a ladder and a
recovery are four different things to notice, and folding them into one ranked list
would put a 61-line `try` beside a nested `for` under a heading that could only be
called "interesting". `match` is the fifth: Society holds **none**, and a lane that
silently vanishes cannot be told from one that looked and found nothing (design rule 21).

**Every lane states its population, and the population is the honest denominator.** Not
"261 loops" but *261 of 1,950* -- the whole point of the judgement is that most of a
program's loops are not subjects, and a lane that hides its denominator is claiming its
rows are all there is. The quiet bands are stated too, on the page rather than per lane:
1,222 loops move nothing, 3,931 branches are refusals, and those two numbers are what
make the four lanes credible.

**Unbounded.** A lane is a list and not a diagram, so rule 8's bound never applies --
803 rows over Society, every one of them. What *is* bounded is the work: the judgement
is one pass over the graph, held on the base and computed on the first ask, exactly as
the curiosities are (rule 45).

**A row carries the routine's node id**, so opening one is an ordinary selection: the
stack lights, the inspector fills, the trail records the hop, undo reaches it. It also
carries its `point_id`, because a point is a subject in its own right from chunk 5 on --
a thing that can be kept -- and an id minted later would be a second id space for one
fact (rule 30).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..resolve import shape
from ..resolve.shape import Point
from ..schema import ArmKind, ControlKind
from ..store import Store

# How many moving things a row lists before it says "and n more". **Not rule 8's bound**:
# the row is here whatever it holds, and the count beside it is the whole number. This is
# a line length, and the point's own pane shows every one.
_SHOWN_MOVES = 4


@dataclass(frozen=True)
class Lane:
    """One thing worth noticing, and how the page has to talk about it.

    The prose lives here rather than in the client for `curiosities.Family`'s reason: a
    sentence assembled from a number is prose the moment something prints it, and prose
    belongs where the number's meaning is known. The client lays it out; it does not
    word it.
    """

    key: str
    title: str
    #: What this lane is, in the reader's terms. One sentence, no numbers -- the counts
    #: are computed and stated separately, so the two cannot drift apart (rule 13).
    blurb: str
    #: What the population is, so the denominator is never a bare number (rule 32).
    of: str
    #: Why the rows are in this order. An order the tool cannot defend is not an order
    #: (rule 66), so every lane says its own.
    order: str


LANES = (
    Lane(key="rates", title="A boundary, once per pass",
         blurb="A loop that reaches out of the program on every pass. What a reader is "
               "looking for is the rate: one call per item, one write per row.",
         of="loops and comprehensions",
         order="the ones inside another loop first, then by how much moves"),
    Lane(key="forks", title="Decisions about what leaves",
         blurb="A branch whose arms differ in what moves. One arm writes to a table and "
               "another does not, which is a decision about the outside world rather "
               "than about a number.",
         of="decisions, guards excluded",
         order="how many ways out there are, then how much moves"),
    Lane(key="ladders", title="Three or more ways out",
         blurb="A decision with three or more arms is a shape a reader has to hold in "
               "their head, whatever is inside it.",
         of="decisions, guards excluded",
         order="the widest first"),
    Lane(key="recoveries", title="Something moves while recovering",
         blurb="A handler that writes, posts or deletes on its way out of a failure — a "
               "second act nobody reading the happy path will see.",
         of="try blocks",
         order="how much moves in the handler"),
    Lane(key="matches", title="match statements",
         blurb="A decision that already knows how many ways out it has, and names each "
               "one.",
         of="decisions, guards excluded",
         order="the widest first"),
)


def _moves(point: Point) -> list[dict[str, Any]]:
    return [{"kind": m.kind, "what": m.what, "detail": m.detail, "line": m.line}
            for m in point.moves[:_SHOWN_MOVES]]


def _row(point: Point, *, inside: Point | None = None) -> dict[str, Any]:
    """One point, as a row that can be opened.

    `node` is the routine, because that is what selecting a loop means today: a span is
    not a node in the graph, and inventing one to make the row clickable would be a link
    to nothing (`DOC_DB_TABLES`' argument, one subject over). `point` rides beside it so
    a later surface can select the span itself without minting a second id for it.
    """
    return {
        "point": point.point_id,
        "node": point.routine_id,
        "kind": point.kind.value,
        "routine": point.routine.rsplit(".", 1)[-1] or point.routine,
        "qualname": point.routine,
        "module": point.module,
        "where": f"{point.file}:{point.line_start}",
        "file": point.file,
        "line": point.line_start,
        "line_end": point.line_end,
        "header": point.header,
        "arms": point.arms_declared,
        "depth": point.depth,
        "why": point.why,
        "moves": _moves(point),
        "n_moves": len(point.moves),
        "calls": point.calls,
        # The loop this one is written inside, where there is one -- named rather than
        # implied by the depth beside it, which counts every enclosing `if` as well.
        "inside": ({"header": inside.header, "line": inside.line_start,
                    "kind": inside.kind.value} if inside else None),
        "arm_moves": [{"kind": a.kind.value, "header": a.header, "line": a.line_start,
                       "n": len(a.moves)} for a in point.arms],
    }


def _is_match(point: Point) -> bool:
    """A `match` and an `if` ladder are one `ControlKind`, and their arms are not.

    The extractor records both as `DECISION` -- which is right, they are one question
    with several answers -- so the only thing that distinguishes them is the word that
    opened each arm. Read off the arms rather than recorded a second time, because a
    flag would be a second answer to a question the arms already settle (rule 40).
    """
    return any(a.kind == ArmKind.CASE for a in point.arms)


def for_program(store: Store) -> dict[str, Any]:
    """Every lane, with its rows and its denominator. One pass over the graph.

    91 ms warm on Society for the judgement, and the arranging is arithmetic over what
    it returned. Held on the base by the route that calls this, so a reader pays it once
    a session and only if they open the page.
    """
    report = shape.measure(store)
    by_id = {p.point_id: p for p in report.points}
    loops = [p for p in report.points
             if p.kind in (ControlKind.LOOP, ControlKind.COMPREHENSION)]
    decisions = report.by_kind(ControlKind.DECISION)
    handlers = report.by_kind(ControlKind.HANDLER)
    guards = report.by_kind(ControlKind.GUARD)

    rates = sorted((p for p in loops if p.band == shape.MOVES),
                   key=lambda p: (not p.in_loop, -len(p.moves), p.file, p.line_start))
    forks = sorted((p for p in decisions if p.forks and not _is_match(p)),
                   key=lambda p: (-p.arms_declared, -len(p.moves), p.file, p.line_start))
    ladders = sorted((p for p in decisions if p.arms_declared >= 3 and not _is_match(p)),
                     key=lambda p: (-p.arms_declared, p.file, p.line_start))
    recoveries = sorted((p for p in handlers if p.recovers),
                        key=lambda p: (-sum(len(a.moves) for a in p.arms
                                            if a.kind in shape.RECOVERY_ARMS),
                                       p.file, p.line_start))
    matches = sorted((p for p in decisions if _is_match(p)),
                     key=lambda p: (-p.arms_declared, p.file, p.line_start))

    rows = {
        "rates": [_row(p, inside=by_id.get(p.in_loop)) for p in rates],
        "forks": [_row(p) for p in forks],
        "ladders": [_row(p) for p in ladders],
        "recoveries": [_row(p) for p in recoveries],
        "matches": [_row(p) for p in matches],
    }
    population = {
        "rates": len(loops), "forks": len(decisions), "ladders": len(decisions),
        "recoveries": len(handlers), "matches": len(decisions),
    }

    return {
        "found": True,
        "points": len(report.points),
        "lanes": [{
            "key": lane.key, "title": lane.title, "blurb": lane.blurb,
            "of": lane.of, "order": lane.order,
            "n": len(rows[lane.key]), "population": population[lane.key],
            "rows": rows[lane.key],
        } for lane in LANES],
        # What was measured and is not offered, which is most of the program. Design
        # rule 1 at the scale that matters here: four lanes holding 803 of 9,625 points
        # is a claim about the other 8,822, and it has to be the reader's to check.
        "quiet": {
            "still_loops": sum(1 for p in loops if p.band == shape.STILL),
            "calling_loops": sum(1 for p in loops if p.band == shape.CALLS),
            "loops": len(loops),
            "guards": len(guards),
            "guarded_handlers": sum(1 for p in handlers
                                    if p.band == shape.MOVES and not p.recovers),
            "handlers": len(handlers),
            "alike_decisions": sum(1 for p in decisions
                                   if not p.forks and p.arms_declared < 3),
            "decisions": len(decisions),
            "nested_rates": sum(1 for p in rates if p.in_loop),
        },
    }
