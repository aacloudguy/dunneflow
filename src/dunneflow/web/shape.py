"""ALGORITHMS: the loops and decisions worth reading, served as a worklist.

`resolve/shape.py` judges every control point in the program. This arranges the ones it
found into lanes, and it is a **doorway** rather than a report -- the Curiosities and
Anomalies precedent, a page reached from the navigator and not a fourth centre mode.

**Four lanes, and a fifth that is empty on purpose.** A rate, a fork, a ladder and a
recovery are four different things to notice, and folding them into one ranked list
would put a 61-line `try` beside a nested `for` under a heading that could only be
called "interesting". `match` is the fifth: Comitia holds **none**, and a lane that
silently vanishes cannot be told from one that looked and found nothing (design rule 21).

**Every lane states its population, and the population is the honest denominator.** Not
"250 loops" but *250 of 1,950* -- the whole point of the judgement is that most of a
program's loops are not subjects, and a lane that hides its denominator is claiming its
rows are all there is. The quiet bands are stated too, on the page rather than per lane:
1,230 loops move nothing, 3,931 branches are refusals, and those two numbers are what
make the four lanes credible.

**Unbounded.** A lane is a list and not a diagram, so rule 8's bound never applies --
793 rows over Comitia, every one of them. What *is* bounded is the work: the judgement
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


def _where(p: Point) -> tuple[str, int, str]:
    """Where a point is, as a key that is actually an order.

    All five lanes ended `(p.file, p.line_start)`, which ties — and the tie is the one
    `CLAUDE.md` already names: `[a for a in [b for b in c]]` is **two comprehensions on
    one line**, and `tools/ordering.py:169` is a real instance of it. So two rows of the
    worklist swapped places between two readings of one map, decided by the order the
    rows came back in (rule 66).

    `point_id` is the point's own identity and is what `tools/golden.py` sorts `control`
    by, so the two agree on what a total order over control points is. Written once and
    spread into each key rather than typed out five times: five copies is five places to
    forget the third element (rule 51), which is how the first two got written.
    """
    return (p.file, p.line_start, p.point_id)


def _grouped(moves: list[Any]) -> list[dict[str, Any]]:
    """One entry per **place**, described by the row that says the most about it.

    An `INSERT` arrives as a `DATABASE` row and a `SQL` row on one line: the same act at
    two altitudes, and the reader wants the lower one -- *writes `spec_seals`*, not
    *DATABASE*. So the specific row leads and the others are named beside it rather than
    drawn as separate acts, which is what makes the count and the drawing agree (rule 13).
    """
    by_line: dict[int, list[Any]] = {}
    for m in moves:
        by_line.setdefault(m.line, []).append(m)
    out: list[dict[str, Any]] = []
    for line in sorted(by_line):
        rows = by_line[line]
        lead = next((m for m in rows if m.kind in (shape.SQL, shape.NET)), rows[0])
        out.append({
            "kind": lead.kind, "what": lead.what, "detail": lead.detail, "line": line,
            # What else was recorded at this place, so nothing is dropped silently
            # (design rule 1) and nothing is counted twice (rule 32).
            "also": [m.kind for m in rows if m is not lead],
            "table": lead.what if lead.kind == shape.SQL and lead.what else "",
        })
    return out


def _moves(point: Point) -> list[dict[str, Any]]:
    return _grouped(point.moves)[:_SHOWN_MOVES]


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
        "n_moves": shape.places(point.moves),
        "calls": point.calls,
        # The loop this one is written inside, where there is one -- named rather than
        # implied by the depth beside it, which counts every enclosing `if` as well.
        "inside": ({"header": inside.header, "line": inside.line_start,
                    "kind": inside.kind.value} if inside else None),
        "arm_moves": [{"kind": a.kind.value, "header": a.header, "line": a.line_start,
                       "n": shape.places(a.moves)} for a in point.arms],
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

    105 ms warm on Comitia for the judgement, and the arranging is arithmetic over what
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
                   key=lambda p: (not p.in_loop, -shape.places(p.moves), *_where(p)))
    forks = sorted((p for p in decisions if p.forks and not _is_match(p)),
                   key=lambda p: (-p.arms_declared, -shape.places(p.moves), *_where(p)))
    ladders = sorted((p for p in decisions if p.arms_declared >= 3 and not _is_match(p)),
                     key=lambda p: (-p.arms_declared, *_where(p)))
    recoveries = sorted((p for p in handlers if p.recovers),
                        key=lambda p: (-shape.places(
                                           [m for a in p.arms
                                            if a.kind in shape.RECOVERY_ARMS
                                            for m in a.moves]),
                                       *_where(p)))
    matches = sorted((p for p in decisions if _is_match(p)),
                     key=lambda p: (-p.arms_declared, *_where(p)))

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
        # rule 1 at the scale that matters here: four lanes holding 793 of 9,625 points
        # is a claim about the other 8,832, and it has to be the reader's to check.
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


# --------------------------------------------------------------------------- #
# The ribbon: one routine's whole shape, nested as it is written
# --------------------------------------------------------------------------- #
#
# **A nested outline, and deliberately not a graph.** The canonical drawing of structured
# control flow is Nassi and Shneiderman's (1972): nested rectangles, loops wrapping their
# contents, decisions splitting a block, and **no arrows at all** -- because structured
# code has no `goto` to draw. Python source never lost that structure, so there is no
# control-flow graph to recover, no dominator tree, and no layout pass: `ast` handed the
# nesting back as written and the store kept it as spans. The other readers record the
# same spans, so the ribbon is drawn the same way for every language.
#
# So this reads top to bottom like the source, it cannot move under a gesture (rule 73),
# it needs no vendored library, and it scrolls -- which is how this reader reads.
#
# **Guards are in, and this is where they belong.** 3,931 of Comitia's branches are
# refusals; a worklist of them would be a list of the program, and a routine's own shape
# without them would be a lie about the routine. The bound is the reader opening one
# routine, which is `/api/flow`'s own argument (rule 45).

def _place(blocks: list[dict[str, Any]], line: int) -> list[dict[str, Any]]:
    """The innermost list of children whose span holds this line.

    Walked from the outside in, taking the last container that still contains the line --
    so a write inside a loop inside a decision's second arm lands in that arm, once. A
    move belongs to exactly one place in the drawing: repeating it at every enclosing
    level would draw one act four times and make a rate look like a rate of four.
    """
    here = blocks
    while True:
        for block in here:
            if block.get("type") != "point":
                continue
            if not (block["line_start"] <= line <= block["line_end"]):
                continue
            for arm in block.get("arms", ()):
                if arm["line_start"] <= line <= arm["line_end"]:
                    here = arm["children"]
                    break
            else:
                here = block["children"]
            break
        else:
            return here


def _block(point: Point) -> dict[str, Any]:
    """One span, ready to draw, with its arms as empty rooms to fill."""
    return {
        "type": "point", "point": point.point_id, "kind": point.kind.value,
        "line_start": point.line_start, "line_end": point.line_end,
        "header": point.header, "arms_declared": point.arms_declared,
        "exits": point.exits, "why": point.why, "band": point.band,
        "significant": point.significant, "depth": point.depth,
        "children": [],
        "arms": [{"idx": a.idx, "kind": a.kind.value, "header": a.header,
                  "line_start": a.line_start, "line_end": a.line_end,
                  "children": []} for a in point.arms],
    }


def outline_for(store: Store, routine_id: str) -> dict[str, Any]:
    """One routine's shape: every span it holds, and everything that moves inside them.

    Three passes and no recursion over the store: the points come back in source order
    with the widest first, which is exactly the order a stack needs; the moving things
    and the calls are placed afterwards, each into the innermost span that holds it.
    """
    row = store.query(
        "SELECT id, name, qualname, module, file, line_start, line_end, docstring"
        " FROM routines WHERE id = ?", (routine_id,))
    if not row:
        # Not an error and not an empty ribbon: a fold, a boundary and a table are all
        # selectable and none of them is a routine, so the pane has to say which of the
        # two silences this is (design rule 21).
        # A whole sentence, capital and stop. It was a fragment written to follow
        # something, and both surfaces render it standing on its own -- so the pane read
        # *"No shape to draw. that is not a routine"*, which is what a glance catches and
        # no test was ever going to.
        return {"found": False,
                "reason": "That is not a routine, so it has no shape of its own."}
    r = row[0]

    # Outermost first, so every ancestor is already in the tree when a point is placed --
    # which is what makes `_place` enough on its own. A stack was here as well and was
    # doing nothing this ordering did not already do; two mechanisms deciding one nesting
    # is the shape rule 40 is about.
    blocks: list[dict[str, Any]] = []
    for point in shape.outline(store, routine_id):
        _place(blocks, point.line_start).append(_block(point))

    # Grouped by place through the same function the lanes use, so a routine's ribbon and
    # its row on the worklist cannot count differently (rule 51). `table` is declared
    # rather than inferred from the kind by the client, because "this row names a table"
    # and "this row's target happens to look like one" are different facts that look
    # identical on the wire (rule 30).
    for move in _grouped(shape.moves_in_routine(store, routine_id)):
        _place(blocks, move["line"]).append({"type": "move", **move})

    for c in store.query(
        "SELECT line, callee_id, callee_expr FROM calls"
        " WHERE caller_id = ? AND callee_id IS NOT NULL AND line IS NOT NULL"
        # `site_id` last, because `describe(measure(conn))` is two calls on one line and
        # the ribbon drew them in whichever order the rows happened to be in. Same key as
        # `queries.ROUTINE_CALLEES`, so the ribbon and the inspector agree about a line.
        " ORDER BY line, callee_expr, site_id", (routine_id,),
    ):
        _place(blocks, int(c["line"])).append({
            "type": "call", "line": int(c["line"]), "node": c["callee_id"],
            "expr": c["callee_expr"] or "",
            # A routine that calls itself is worth saying out loud: it is the one shape
            # in this drawing that a nested outline cannot show by nesting.
            "recursive": c["callee_id"] == routine_id,
        })

    _sort(blocks)
    return {
        "found": True,
        "routine": {"id": r["id"], "name": r["name"], "qualname": r["qualname"],
                    "module": r["module"], "file": r["file"],
                    "line_start": r["line_start"], "line_end": r["line_end"],
                    "lines": int(r["line_end"]) - int(r["line_start"]) + 1},
        "blocks": blocks,
        # What the ribbon holds, so a collapsed one can say what is inside it and an
        # empty one can say it is empty rather than unbuilt (design rule 21).
        "counts": _tally(blocks, {}),
    }


def _sort(blocks: list[dict[str, Any]]) -> None:
    """Everything in the order it is written, at every level."""
    blocks.sort(key=lambda b: (b.get("line_start", b.get("line", 0)),
                               0 if b["type"] == "point" else 1))
    for block in blocks:
        if block["type"] != "point":
            continue
        _sort(block["children"])
        for arm in block["arms"]:
            _sort(arm["children"])


def _tally(blocks: list[dict[str, Any]], out: dict[str, int],
           inside: bool = False) -> dict[str, int]:
    """Spans by kind, and the moves and calls **inside** a span.

    The inspector's sentence is *"N things move inside them"*, and until 2026-10-02 `moves`
    and `calls` were counted wherever they sat -- so a routine whose one database write
    came after both its loops said *1 thing moves inside them* about a write outside both
    (BACKLOG 18, rule 32). What sits at the top level is not inside anything.
    """
    for block in blocks:
        if block["type"] == "point":
            out[block["kind"]] = out.get(block["kind"], 0) + 1
            _tally(block["children"], out, True)
            for arm in block["arms"]:
                _tally(arm["children"], out, True)
        elif inside:
            key = "moves" if block["type"] == "move" else "calls"
            out[key] = out.get(key, 0) + 1
    return out


# --------------------------------------------------------------------------- #
# The other direction: what loops over a named thing
# --------------------------------------------------------------------------- #

def _loop_sentence(loops: int, deepest: int, places: int) -> str:
    """The pane's own words. Worded here for `Lane`'s reason: the client lays out, it
    does not word.

    **What is counted is loops, and the places are said separately** (rule 32). *3 loops*
    and *3 writes* are different numbers and a single figure would be whichever one the
    reader assumed -- the loop count answers *how many times could this run in a pass*,
    the places answer *how many acts are in there*. `places` is `resolve.shape.places`, so
    an `INSERT` recorded as a `DATABASE` row and a `SQL` row is one act here as it is
    everywhere else (rule 51).
    """
    # **"reached", and deliberately not "written".** The record's phrasing for a table
    # was *"written from inside 3 loops"*, which is false the moment one of them only
    # reads -- and 8 of `worktree_allocations`' 27 operations are reads. One verb for a
    # table and a boundary also means one sentence rather than two that drift (rule 51).
    if not loops:
        return "not reached from inside any loop"
    head = "reached from inside 1 loop" if loops == 1 else \
        f"reached from inside {loops:,} loops"
    # **The nesting clause states the deepest chain, never how many are in one.**
    # "one of those is inside another" is a count, and `deepest` is a maximum: 89 loops
    # with a deepest of 1 may have forty nested ones, and the sentence would have said
    # there was one (rule 32).
    if deepest:
        head += (", the deepest of them inside another loop" if deepest == 1
                 else f", the deepest of them {deepest} loops down")
    tail = "1 place" if places == 1 else f"{places:,} places"
    return f"{head} — {tail} in all"


def loops_around(store: Store, *, table: str | None = None,
                 boundary: tuple[str, str] | None = None) -> dict[str, Any]:
    """What loops over a table or a boundary, for the pane that stands at one.

    The *"and vice versa"* half: ALGORITHMS asks what a loop touches, and this is a
    reader standing at a table asking what loops over them. `resolve.shape.enclosing`
    does the fact and this does the wording, which is the split every other surface here
    already keeps.

    **Only the loops are counted, and everything enclosing is returned.** A table written
    from inside one arm of a decision is a fact about that table, so the rows hold every
    enclosing span (design rule 1); the sentence is about loops because that is the
    question a rate answers and the one the figure is being asked. Both numbers come off
    the same list, so the headline and the rows it opens cannot disagree (rule 13).
    """
    points = shape.enclosing(store, table=table, boundary=boundary)
    deep = shape.nesting(points)
    loops = [p for p in points
             if p.kind in (ControlKind.LOOP, ControlKind.COMPREHENSION)]
    moves: list[Any] = []
    for p in loops:
        moves.extend(p.moves)

    return {
        "loops": len(loops),
        "points": len(points),
        "deepest": max((deep[p.point_id] for p in loops), default=0),
        "places": shape.places(moves),
        "sentence": _loop_sentence(len(loops), max((deep[p.point_id] for p in loops),
                                                   default=0), shape.places(moves)),
        # Every enclosing span, innermost first, in the worklist's own row shape -- so a
        # figure that counts things opens exactly those things (rule 32), and a row here
        # and a row on the Algorithms page are the same row.
        "rows": [dict(_row(p), nested=deep[p.point_id]) for p in points],
    }
