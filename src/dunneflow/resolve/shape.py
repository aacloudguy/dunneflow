"""What moves inside a loop or a decision, and whether that makes it worth reading.

`extractors/python/extract.py` records a control point as **a span and nothing more**.
This is the other half: the range join that says what is *inside* one, and the single
test that says whether a reader should be shown it.

**The judgement, in one sentence.** A loop or a decision is a subject only where
something *moves* inside it. A loop that increments a counter is the internal
computation `CLAUDE.md` excludes; a loop that issues one network call per item is a
**rate**, and a rate is flow. A branch whose arms compute different numbers is
arithmetic; a branch where one arm writes to a table and the other does not is a
**decision about what leaves the program**. That test lives here and nowhere else
(rule 51) -- the worklist, the ribbon, the panes and the detector all ask this module,
because a judgement written twice is two judgements waiting to disagree.

**Nothing is dropped for failing it** (design rule 1). A loop over nothing is a fact
about the program, and it is the 1,230 of them that make the 250 credible: a worklist
that shows only its hits cannot be told from one that found only those. Every point
comes back with a `band` and a `why`, and the surface decides what to draw.

**The join is a range and not a relationship.** `boundaries`, `net_calls`, `sql_ops` and
`calls` each already carry `routine_id` and `line`, so *inside* is
`routine_id = ? AND line BETWEEN line_start AND line_end` -- the inverse of the lookup
`web/search.py` does to say which routine a hit sits in. No table joins a control point
to a boundary, because such a table would be a second copy of a fact the two already
state between them (rule 40).

**A move is counted once at a line, and the parts are kept.** 569 of Society's 991 SQL
operations sit on a line that is also a `boundaries` row, and 29 of its 32 network calls
do -- summing the three tables reports a loop holding one write as holding two, and it
did, in the sentence that gives 28 of the 250 rates their number. What is deduplicated is
the *place*; what is kept is what each table had to say about it, because "writes
`spec_seals`" and "DATABASE" are the same act described at two altitudes and the reader
wants the first one. Every count goes through `places` (rule 51); every description stays
in `moves`.

**A test is not an arm.** `if fetch_row():` reaches a boundary from the decision's own
header, which belongs to no arm -- so the arm-difference test sees it in neither and the
decision is not called a fork on account of it. That is deliberate: attributing it to the
arm written below it would be a position mistaken for a meaning (rule 1).

**And an iterable is not a body.** `for row in conn.execute(q).fetchall():` runs one
query, before the first pass -- but it is written on a line inside the loop's own span, so
the range join above read it as one query *per* pass and said so, about 11 of Society's
261 rates, in the sentence that is this feature's headline. **A span cannot tell what a
loop is over from what it does** (rule 85), which is why `ControlPoint` records the lines
it evaluates once and why `Point.repeated` -- never `Point.moves` -- is what the band and the
judgement are taken over. A `for ... else` runs once too and comes off the same way,
through the arm that already records it.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, field

from ..schema import ArmKind, ControlKind
from ..store import Store

# What a point turned out to be, in the reader's words. Three bands and never two: a
# point that moves something, a point that only calls something, and a point where
# nothing this map can see happens at all. Collapsing the middle into either end would
# be the flattening `Store.finished` refuses -- "it calls a routine, and we did not
# follow it" is not "nothing happens here".
MOVES = "MOVES"
CALLS = "CALLS"
STILL = "STILL"

# Bands in worklist order, so a surface listing them cannot invent an order of its own.
BANDS = (MOVES, CALLS, STILL)

# What a `sql_ops` row and a `net_calls` row are called where they are shown beside
# boundary kinds. Not `BoundaryKind` members: they are the same act said in more detail,
# and giving them one of those names would claim they came from the boundary detector.
SQL = "SQL"
NET = "NET"

# The arms of a `try` that run when the guarded body did not finish. The 396 handlers
# that recover by moving something are counted over exactly these, which is why the set
# is named rather than written into the test: a `finally` moves something on *every*
# path, including the one where nothing failed, and calling that a recovery would be a
# claim about failure drawn from a line that says nothing about it.
RECOVERY_ARMS = frozenset({ArmKind.EXCEPT})


def places(moves: list[Move]) -> int:
    """How many *acts* these rows describe, which is not how many rows there are.

    `boundaries`, `sql_ops` and `net_calls` describe one statement at two altitudes: an
    `INSERT` is a `DATABASE` row and a `SQL` row on the same line, and 569 of Society's
    991 SQL operations sit on a line that is also a boundary. Counting rows says *two
    things move here* about one write -- and it said so about **28 of the 250** loops this
    feature exists to report, in the sentence that gives their rate.

    So a **place is the unit a reader is counting** and the rows are what is known about
    it. Everything a surface prints as "how many" comes through here (rule 51), because
    two ways of counting one thing is the defect rule 32 is written against.
    """
    return len({m.line for m in moves})


@dataclass(slots=True, frozen=True)
class Move:
    """One thing that moves, at one line.

    `what` is the target as the detector recorded it -- a table, a URL, a path, an
    environment variable. Never shortened here; what a surface does about a long one is
    the surface's decision (rule 8).
    """

    line: int
    kind: str      # a BoundaryKind, or SQL, or NET
    what: str
    detail: str = ""   # the SQL verb, the HTTP verb, the direction -- what the row added


@dataclass(slots=True)
class Arm:
    """One way through a point, with what moves inside it."""

    idx: int
    kind: ArmKind
    line_start: int
    line_end: int
    header: str
    moves: list[Move] = field(default_factory=list)
    calls: int = 0


@dataclass(slots=True)
class Point:
    """One control point, joined to what is inside it and judged once.

    `why` is filled on every point, including the ones that pass: a reader who is shown
    a loop is owed the reason as much as one who is not shown it, and a sentence that
    exists only for failures is a sentence nobody can check.
    """

    point_id: str
    routine_id: str
    routine: str          # qualname, for a surface that has to name it
    module: str
    file: str
    kind: ControlKind
    line_start: int
    line_end: int
    depth: int
    header: str
    arms_declared: int    # what the extractor counted: ways out, flattened
    exits: str
    moves: list[Move] = field(default_factory=list)
    calls: int = 0
    arms: list[Arm] = field(default_factory=list)
    band: str = STILL
    significant: bool = False
    why: str = ""
    # The loop this point is written inside, in this routine, or "". **Not `depth > 1`**:
    # `depth` counts every enclosing control point, so a loop inside an `if` has depth 2
    # and is not nested at all. On Society the two answers are 98 and 9, and the second
    # is the one worth reading -- a boundary reached once per pass of a loop that is
    # itself once per pass is a quadratic reach into the outside world, which the first
    # number quietly buries under a hundred `if`s.
    in_loop: str = ""
    # The lines this point evaluates once before the first pass -- a `for`'s iterable, a
    # comprehension's first generator -- as `ControlPoint` recorded them. 0/0 for a
    # `while`, for every decision, and for a loop written on one line, where the element
    # and the iterable share a line and nothing can be excluded honestly.
    once_start: int = 0
    once_end: int = 0
    # The word the source opened with: `for`, `async for`, `while`, `if`, `try`, `match`,
    # and "" for a comprehension. Read rather than inferred from the header, because a
    # `while` and a `for` are one `ControlKind` and opposite facts (rule 30).
    word: str = ""

    @property
    def once(self) -> list[Move]:
        """What this point is *over*, evaluated before the first pass.

        Empty for everything but a `for` or a comprehension whose iterable moves
        something -- 11 of Society's loops. Kept rather than discarded (design rule 1):
        the query is really written there, the ribbon draws it where it stands, and the
        loop's own sentence names it. What it must not do is count as a rate.
        """
        if not self.once_start:
            return []
        return [m for m in self.moves if self.once_start <= m.line <= self.once_end]

    @property
    def repeated(self) -> list[Move]:
        """What actually happens every time this point runs.

        `moves` minus the iterable, and minus a `for ... else`, which runs once when the
        loop was never broken out of. The `else` comes off through the arm that already
        records its span rather than through a second fact (rule 40); Society has 2 such
        loops and neither is a rate either way, which is why this is two lines and not a
        feature.

        **Everything that counts a loop counts this** -- the band, the judgement, the
        lanes. `moves` stays what is written inside the span, because that is what the
        ribbon draws and what a reader sees.
        """
        skip = {m.line for m in self.once}
        if self.kind in (ControlKind.LOOP, ControlKind.COMPREHENSION):
            for arm in self.arms:
                if arm.kind is ArmKind.ELSE:
                    skip.update(m.line for m in arm.moves)
        return [m for m in self.moves if m.line not in skip]

    @property
    def forks(self) -> bool:
        """Do this point's arms differ in what moves?

        The question a `DECISION` exists to be asked, and it is answered over the arms
        rather than over the span: a span holding one write says nothing about which way
        out performed it, and that is the whole difference between arithmetic and a
        decision about what leaves.
        """
        if len(self.arms) < 2:
            return False
        return len({places(a.moves) for a in self.arms}) > 1

    @property
    def recovers(self) -> bool:
        """Does something move on the way out of a failure?"""
        return any(a.moves for a in self.arms if a.kind in RECOVERY_ARMS)


@dataclass(slots=True)
class ShapeReport:
    """Every control point in the program, judged, in file and line order."""

    points: list[Point] = field(default_factory=list)

    def by_kind(self, kind: ControlKind) -> list[Point]:
        return [p for p in self.points if p.kind == kind]

    def counts(self) -> dict[str, int]:
        """The populations, as a surface has to state them (design rule 1).

        Every number here is a count of rows in `points`, so a lane's headline and its
        list cannot disagree (rule 13).
        """
        out: dict[str, int] = defaultdict(int)
        for p in self.points:
            out[p.kind.value] += 1
            out[f"{p.kind.value}:{p.band}"] += 1
            if p.significant:
                out["significant"] += 1
                out[f"{p.kind.value}:significant"] += 1
        return dict(out)


# --------------------------------------------------------------------------- #
# The join
# --------------------------------------------------------------------------- #

# The three tables that record something leaving or entering the program, each already
# carrying `routine_id` and `line`. Written as one shape -- routine, line, kind, target,
# detail -- so the join reads them without knowing which is which, and a fourth table
# added later is a line here rather than a branch in three places (rule 51).
_MOVE_QUERIES = (
    "SELECT routine_id, line, kind, target, direction AS detail FROM boundaries",
    "SELECT routine_id, line, 'SQL' AS kind, tbl AS target, operation AS detail"
    " FROM sql_ops",
    "SELECT routine_id, line, 'NET' AS kind, destination AS target,"
    " CASE WHEN verb = '' THEN protocol ELSE verb END AS detail FROM net_calls",
)


def _moves_by_routine(store: Store) -> dict[str, list[Move]]:
    """Every moving thing in the program, grouped by the routine it sits in.

    One pass per table rather than one query per point: 9,625 points against three
    tables is 28,875 statements, and the same rows read three times over. The bound is
    on the *work* and not only on the answer (rule 55) -- what comes back is every
    moving thing once, sorted, and every point then costs two bisections.
    """
    seen: set[tuple[str, int, str, str]] = set()
    out: dict[str, list[Move]] = defaultdict(list)
    for sql in _MOVE_QUERIES:
        for r in store.query(sql):
            rid, line = r["routine_id"], r["line"]
            if not rid or line is None:
                continue
            key = (rid, int(line), r["kind"], r["target"] or "")
            if key in seen:
                continue
            seen.add(key)
            out[rid].append(Move(line=int(line), kind=r["kind"], what=r["target"] or "",
                                 detail=r["detail"] or ""))
    for moves in out.values():
        moves.sort(key=lambda m: m.line)
    return out


def _calls_by_routine(store: Store) -> dict[str, list[int]]:
    """The lines where a routine calls another routine in this program.

    Resolved calls only. An unresolved one may be a boundary nobody detected or a name
    that means nothing here, and counting it would put a loop in the middle band on the
    strength of a guess (rule 6).
    """
    out: dict[str, list[int]] = defaultdict(list)
    for r in store.query(
        "SELECT caller_id, line FROM calls WHERE callee_id IS NOT NULL AND line IS NOT NULL"
    ):
        out[r["caller_id"]].append(int(r["line"]))
    for lines in out.values():
        lines.sort()
    return out


def enclosing_loops(points: list[Point]) -> None:
    """Fill `in_loop` for one routine's points, in place. They must be in source order.

    A stack sweep rather than a containment search: the points arrive sorted by where
    they start and, where two start together, widest first, so an open loop is on the
    stack exactly while the lines being read are inside it.

    `depth` breaks the one tie lines cannot. `[a for a in [b for b in c]]` is two
    comprehensions occupying the same single line, and the only thing separating them is
    that one is written inside the other -- which is what `depth` records.
    """
    stack: list[Point] = []
    for point in points:
        while stack and (stack[-1].line_end < point.line_start
                         or stack[-1].depth >= point.depth):
            stack.pop()
        if stack:
            point.in_loop = stack[-1].point_id
        if point.kind in (ControlKind.LOOP, ControlKind.COMPREHENSION):
            stack.append(point)


def _within(moves: list[Move], lo: int, hi: int) -> list[Move]:
    lines = [m.line for m in moves]
    return moves[bisect_left(lines, lo):bisect_right(lines, hi)]


def _count_within(lines: list[int], lo: int, hi: int) -> int:
    return bisect_right(lines, hi) - bisect_left(lines, lo)


# --------------------------------------------------------------------------- #
# The judgement
# --------------------------------------------------------------------------- #

def judge(point: Point) -> None:
    """Band the point, decide whether it is a subject, and say why. In place.

    **The band and the judgement are different questions.** The band says what is inside
    the span -- one fact, the same for every kind. Whether that makes the point worth a
    reader's attention depends on what the point *is*: a boundary inside a loop is a
    rate, the same boundary inside a `try` is a recovery, and inside a guard it is a
    precondition that happens to fetch something. Answering both with one number is how
    a worklist ends up listing 3,931 refusals.
    """
    # **Over `repeated`, never `moves`.** For every decision, guard and handler the two
    # are the same list, so this moves nothing there; for a loop it is the difference
    # between *a query per pass* and *a query, then a loop*. The band has to carry the
    # correction as well as the judgement, because `web/shape.py` builds the rates lane
    # from `band == MOVES` and the page's three loop numbers have to keep summing to
    # 1,950 -- two answers to one question is rule 13's defect, and it would show up as a
    # lane that disagrees with its own denominator.
    point.band = MOVES if point.repeated else (CALLS if point.calls else STILL)

    if point.kind in (ControlKind.LOOP, ControlKind.COMPREHENSION):
        _judge_loop(point)
    elif point.kind == ControlKind.DECISION:
        _judge_decision(point)
    elif point.kind == ControlKind.HANDLER:
        _judge_handler(point)
    else:
        _judge_guard(point)


def _judge_loop(point: Point) -> None:
    """A loop is a subject where something moves **on every pass**, because that is a rate.

    Counted over `repeated`: what a loop is *over* runs once, before the first pass, and
    `for row in conn.execute(q).fetchall():` is one query however many rows come back.
    Read over the whole span it was 11 of Society's 261 rates, each of them saying *once
    per pass* about a thing that happens once.
    """
    n = places(point.repeated)
    # **The iterable is named, never dropped** (design rule 1). It is a clause on whichever
    # band the loop lands in rather than a fourth band, in the shape the nesting clause
    # below already uses: a loop that fetches once and then calls per pass is a `CALLS`
    # loop with something worth saying about its first line.
    once = places(point.once)
    over = ""
    if once and n:
        over = " \u2014 and what it is over moves something too, once, before the first pass"
    elif once == 1:
        over = " \u2014 the one thing that moves here is what it is over, evaluated once"
    elif once:
        over = (f" \u2014 the {once} things that move here are what it is over, evaluated"
                " once")
    if n:
        point.significant = True
        per = "once per pass" if n == 1 else f"{n} of them, once per pass"
        # Named from the enclosing *loop* and never from `depth`, which counts every
        # enclosing control point: 98 of Society's 250 boundary loops sit at a depth
        # above 1, and **10** of them are inside another loop. The first number reads as
        # the second and is not it.
        nested = " \u2014 and it is inside another loop" if point.in_loop else ""
        point.why = f"something moves inside this loop, {per}{nested}{over}"
    elif point.calls:
        point.why = (f"calls {point.calls} routine{'s' if point.calls != 1 else ''} of this"
                     f" program, and nothing moves at these lines{over}")
    else:
        point.why = f"nothing that moves happens inside it{over}"


def _judge_decision(point: Point) -> None:
    """A decision is a subject where its arms differ in what moves, or where it is a
    ladder: three ways out is a shape a reader has to hold in their head, whatever is in
    them. The two tests find near-disjoint sets -- 7 of Society's 78 forks are also
    ladders -- which is why both are here and neither is a special case of the other.
    """
    if point.forks:
        point.significant = True
        moving = sum(1 for a in point.arms if places(a.moves))
        point.why = (f"its {len(point.arms)} ways out differ in what moves:"
                     f" {moving} of them move something and the rest do not")
    elif point.arms_declared >= 3:
        point.significant = True
        # How many of them act, in the same sentence. A ladder is here on its shape, and
        # a reader's next question is always which way out does anything -- asked of the
        # arms, and answered in the one place that has them (rule 51), rather than by a
        # second line on the page saying the same thing in other words (rule 41).
        moving = sum(1 for a in point.arms if places(a.moves))
        acts = (f", and {moving} of them move something" if moving
                else ", and none of them moves anything")
        point.why = f"{point.arms_declared} ways out of one decision{acts}"
    elif point.moves:
        point.why = "every way out of it moves the same things"
    elif point.calls:
        point.why = "it chooses between calls, and nothing moves at these lines"
    else:
        point.why = "nothing that moves happens in any arm"


def _judge_handler(point: Point) -> None:
    """A `try` is a subject where the recovery itself moves something.

    Not where the *body* does: 742 of Society's 1,531 handlers guard something that
    touches a boundary, which is what a `try` is for and says nothing a reader did not
    expect. 396 of them do something on the way out -- write a row, post a message,
    delete a file -- and that is a second act nobody reading the happy path will see.
    """
    if point.recovers:
        point.significant = True
        n = places([m for a in point.arms if a.kind in RECOVERY_ARMS for m in a.moves])
        point.why = (f"something moves while recovering from a failure \u2014"
                     f" {n} of them, on a path the happy case never takes")
    elif point.moves:
        point.why = "it guards something that moves, and its handlers move nothing"
    elif point.calls:
        point.why = "it guards a call, and nothing moves at these lines"
    else:
        point.why = "nothing that moves happens inside it"


def _judge_guard(point: Point) -> None:
    """A guard is never a worklist item, and that is not a measure of its importance.

    3,931 of Society's 6,144 branches are refusals -- 62%, the largest shape in the
    program -- and a worklist of them would be a list of the whole program. A guard is
    read where it belongs, in the shape of the routine it stands at the top of, and
    that is why it is recorded rather than skipped at extraction.
    """
    # The word the source used, in the present tense a sentence needs. Read off `exits`
    # rather than off the header, because "if not x: return" and "if not x: raise" are
    # the same sentence and opposite facts -- which is why `exits` is recorded at all.
    leaves = {"return": "returns", "raise": "raises",
              "continue": "skips the pass", "break": "leaves the loop"}
    point.why = (f"a precondition: it {leaves.get(point.exits, 'leaves')},"
                 " and a refusal is read in the routine, not in a worklist")


# --------------------------------------------------------------------------- #
# The whole program
# --------------------------------------------------------------------------- #

_POINTS_SQL = """
SELECT c.point_id, c.routine_id, c.file, c.kind, c.line_start, c.line_end,
       c.depth, c.header, c.arms, c.exits, c.word, c.once_start, c.once_end,
       COALESCE(r.qualname, '') AS qualname, COALESCE(r.module, '') AS module
  FROM control c
  LEFT JOIN routines r ON r.id = c.routine_id
 ORDER BY c.file, c.line_start, c.line_end DESC
"""

_ARMS_SQL = """
SELECT point_id, routine_id, idx, kind, line_start, line_end, header
  FROM control_arms
 ORDER BY point_id, idx
"""


def measure(store: Store) -> ShapeReport:
    """Every control point in the program, joined to what moves inside it and judged.

    A whole-corpus pass, like `naming.measure`: four statements, and then arithmetic
    over what they returned. On Society that is 9,625 points, 2,269 arms and 4,174
    moving things.
    """
    moves = _moves_by_routine(store)
    calls = _calls_by_routine(store)

    arms_by_point: dict[str, list[Arm]] = defaultdict(list)
    for r in store.query(_ARMS_SQL):
        arms_by_point[r["point_id"]].append(Arm(
            idx=int(r["idx"]), kind=ArmKind(r["kind"]),
            line_start=int(r["line_start"]), line_end=int(r["line_end"]),
            header=r["header"] or "",
        ))

    report = ShapeReport()
    for r in store.query(_POINTS_SQL):
        rid = r["routine_id"]
        rmoves, rcalls = moves.get(rid, []), calls.get(rid, [])
        lo, hi = int(r["line_start"]), int(r["line_end"])
        point = Point(
            point_id=r["point_id"], routine_id=rid, routine=r["qualname"],
            module=r["module"], file=r["file"], kind=ControlKind(r["kind"]),
            line_start=lo, line_end=hi, depth=int(r["depth"]), header=r["header"] or "",
            arms_declared=int(r["arms"]), exits=r["exits"] or "",
            word=r["word"] or "",
            once_start=int(r["once_start"] or 0), once_end=int(r["once_end"] or 0),
            moves=_within(rmoves, lo, hi), calls=_count_within(rcalls, lo, hi),
            arms=arms_by_point.get(r["point_id"], []),
        )
        for arm in point.arms:
            arm.moves = _within(rmoves, arm.line_start, arm.line_end)
            arm.calls = _count_within(rcalls, arm.line_start, arm.line_end)
        report.points.append(point)
    # Nesting is a question about a routine and is asked once the routine's points are
    # all here; judging happens after, because a rate's sentence turns on the answer.
    # Grouped by routine and **not** by file: a closure defined inside a loop starts its
    # own body at depth 0, and sweeping a file's points as one run would read the two
    # routines' spans as one nest.
    by_routine: dict[str, list[Point]] = defaultdict(list)
    for point in report.points:
        by_routine[point.routine_id].append(point)
    for group in by_routine.values():
        enclosing_loops(group)
    for point in report.points:
        judge(point)
    return report


def moves_in_routine(store: Store, routine_id: str) -> list[Move]:
    """Everything that moves inside one routine, deduplicated by place, in line order.

    Its own function because two callers need the same list and only one of them wants
    the points: `outline` bands the spans, and the ribbon has to hang each moving thing
    on the innermost span that holds it. Two copies of this loop would be two answers to
    "what is a move" the first time either was touched (rule 51).
    """
    moves: list[Move] = []
    seen: set[tuple[int, str, str]] = set()
    for sql in _MOVE_QUERIES:
        for r in store.query(f"{sql} WHERE routine_id = ?", (routine_id,)):
            if r["line"] is None:
                continue
            key = (int(r["line"]), r["kind"], r["target"] or "")
            if key in seen:
                continue
            seen.add(key)
            moves.append(Move(line=int(r["line"]), kind=r["kind"],
                              what=r["target"] or "", detail=r["detail"] or ""))
    moves.sort(key=lambda m: m.line)
    return moves


def outline(store: Store, routine_id: str) -> list[Point]:
    """One routine's whole shape, guards included, in the order it is written.

    The same function as `measure` one scope down, and deliberately not a filter over
    it: a reader opening one routine must not pay for the other 9,600 points (rule 45),
    and the judgement has to be the same one either way (rule 51).

    Ordered by where each point starts, and by the *widest* first where two start on the
    same line -- a `for x in [y for y in z]` is a loop containing a comprehension, and
    the containing one has to be drawn first for the nesting to read at all.
    """
    moves = moves_in_routine(store, routine_id)
    calls = sorted(int(r["line"]) for r in store.query(
        "SELECT line FROM calls WHERE caller_id = ? AND callee_id IS NOT NULL"
        " AND line IS NOT NULL", (routine_id,)))

    arms_by_point: dict[str, list[Arm]] = defaultdict(list)
    for r in store.query(
        "SELECT * FROM control_arms WHERE routine_id = ? ORDER BY point_id, idx",
        (routine_id,),
    ):
        arms_by_point[r["point_id"]].append(Arm(
            idx=int(r["idx"]), kind=ArmKind(r["kind"]),
            line_start=int(r["line_start"]), line_end=int(r["line_end"]),
            header=r["header"] or "",
        ))

    out: list[Point] = []
    for r in store.query(
        "SELECT c.*, COALESCE(r.qualname,'') AS qualname, COALESCE(r.module,'') AS module"
        " FROM control c LEFT JOIN routines r ON r.id = c.routine_id"
        " WHERE c.routine_id = ? ORDER BY c.line_start, c.line_end DESC",
        (routine_id,),
    ):
        lo, hi = int(r["line_start"]), int(r["line_end"])
        point = Point(
            point_id=r["point_id"], routine_id=routine_id, routine=r["qualname"],
            module=r["module"], file=r["file"], kind=ControlKind(r["kind"]),
            line_start=lo, line_end=hi, depth=int(r["depth"]), header=r["header"] or "",
            arms_declared=int(r["arms"]), exits=r["exits"] or "",
            word=r["word"] or "",
            once_start=int(r["once_start"] or 0), once_end=int(r["once_end"] or 0),
            moves=_within(moves, lo, hi), calls=_count_within(calls, lo, hi),
            arms=arms_by_point.get(r["point_id"], []),
        )
        for arm in point.arms:
            arm.moves = _within(moves, arm.line_start, arm.line_end)
            arm.calls = _count_within(calls, arm.line_start, arm.line_end)
        out.append(point)
    enclosing_loops(out)
    for point in out:
        judge(point)
    return out


# --------------------------------------------------------------------------- #
# The other direction
# --------------------------------------------------------------------------- #

# Where a named thing is touched, as `(routine_id, line)`. Two statements because a
# table and a boundary are asked for differently and neither is the other's default: a
# caller that means "the table `spec_seals`" and a caller that means "the DATABASE
# boundary named `spec_seals`" are asking about the same writes through different
# doors, and guessing which from the shape of a string is rule 30's defect.
#
# `sql_ops.tbl` rides `ix_sqlops_table`. `boundaries(kind, target)` has no index and is
# a scan of 4,070 rows, measured at under 20 ms on Society -- an index kept up to date
# for that is a fact to maintain for nothing (rule 24 in the mirror: measure before
# spending).
#
# The `EXISTS` is the bound on the work and not on the answer (rule 55). `enclosing`
# pays one `outline` per routine, so the routines that touch the thing at no enclosing
# line at all are the ones worth never loading: 524 routines touch Society's unnamed
# `FILE` boundary and 389 of them hold a point around it.
_TOUCH_TABLE = """
SELECT o.routine_id, o.line FROM sql_ops o
 WHERE o.tbl = :name AND o.routine_id IS NOT NULL AND o.line IS NOT NULL
   AND EXISTS (SELECT 1 FROM control c WHERE c.routine_id = o.routine_id
                AND o.line BETWEEN c.line_start AND c.line_end)
"""

_TOUCH_BOUNDARY = """
SELECT b.routine_id, b.line FROM boundaries b
 WHERE b.kind = :kind AND COALESCE(b.target, '') = COALESCE(:target, '')
   AND b.routine_id IS NOT NULL AND b.line IS NOT NULL
   AND EXISTS (SELECT 1 FROM control c WHERE c.routine_id = b.routine_id
                AND b.line BETWEEN c.line_start AND c.line_end)
"""


def enclosing(store: Store, *, table: str | None = None,
              boundary: tuple[str, str] | None = None) -> list[Point]:
    """The control points a named thing is touched from inside, innermost first.

    The reverse of `outline`, and the half that makes ALGORITHMS a doorway rather than
    a page: `outline` asks *what does this loop touch*, and a reader standing at a table
    asks *what loops over me*.

    **It is `outline` per routine and not a query of its own** (rule 51). The judgement,
    the nesting sweep and `places` are the ones the worklist and the ribbon already ask,
    so a point cannot be banded one way here and another way there -- which is exactly
    what a second range join written for this question would have produced. The bound is
    the routines that touch the thing, which is a handful for a table and never the
    program (rule 55).

    Every enclosing point comes back, of every kind, judged and with its `why` -- not
    only the loops and not only the ones that pass, because a table written from inside
    a decision is a fact about that table and design rule 1 says a surface may choose
    not to draw it but this may not choose not to say it. The chain is whole: a loop
    that contains an inner loop contains the inner loop's lines too, so following
    `in_loop` from any point reaches every point above it without leaving this list.
    """
    if (table is None) == (boundary is None):
        raise ValueError(
            "enclosing() names exactly one thing: table= or boundary=(kind, target)")

    if table is not None:
        rows = store.query(_TOUCH_TABLE, {"name": table})
    else:
        kind, target = boundary  # type: ignore[misc]
        rows = store.query(_TOUCH_BOUNDARY, {"kind": kind, "target": target})

    lines_by_routine: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        lines_by_routine[r["routine_id"]].append(int(r["line"]))

    out: list[Point] = []
    for routine_id, lines in lines_by_routine.items():
        touched = sorted(set(lines))
        for point in outline(store, routine_id):
            # **Inside, and not what it is over.** A loop whose only touch of this table
            # is its own iterable does not reach it once per pass; it reaches it once,
            # before the first pass. Two of Society's 64 tables have such a loop, and
            # without this the pane says *"reached from inside 1 loop"* about a query the
            # loop is written over -- `_judge_loop`'s defect arriving at the sentence
            # chunk 5 built, which is why the same `once` span decides both (rule 51).
            inside = [ln for ln in touched
                      if not (point.once_start
                              and point.once_start <= ln <= point.once_end)]
            if _count_within(inside, point.line_start, point.line_end):
                out.append(point)
    # Innermost first, the way `web/search.py` reads a hit's scope (rule 10): the
    # narrowest span is the one that says the most about the line, and a reader shown
    # the routine-wide `try` before the loop inside it has been told the least useful
    # true thing first.
    out.sort(key=lambda p: (p.file, p.line_start, p.line_end - p.line_start))
    return out


def nesting(points: list[Point]) -> dict[str, int]:
    """How many loops each point is written inside, over the points given.

    Counted by following `in_loop`, which is a containment answer, and **never from
    `depth`** -- `depth` counts every enclosing control point, so a loop written inside
    an `if` reads as nested when it is nested in nothing. On Society the two answers
    over the rates are 98 and 9, and only the second is the quadratic reach into the
    outside world a reader is being warned about.

    A point whose `in_loop` names something outside this list stops the walk rather
    than raising: `enclosing` returns whole chains, but a caller narrowing the list
    first is asking about what it kept, and answering a shorter number is right where
    inventing the rest would not be.
    """
    by_id = {p.point_id: p for p in points}
    out: dict[str, int] = {}

    def walk(point: Point, seen: frozenset[str]) -> int:
        if point.point_id in out:
            return out[point.point_id]
        above = by_id.get(point.in_loop) if point.in_loop else None
        # `seen` guards a cycle that cannot happen from a stack sweep but would hang
        # rather than fail if a future filler ever wrote one (rule 43).
        depth = 0 if above is None or above.point_id in seen else 1 + walk(
            above, seen | {point.point_id})
        out[point.point_id] = depth
        return depth

    for p in points:
        walk(p, frozenset())
    return out
