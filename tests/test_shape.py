"""What moves inside a loop or a decision, and whether that makes it a subject.

Every test here is a way this module can be confidently wrong. The founding exclusion
it amends is narrow on purpose -- *a loop is a subject only where something moves inside
it* -- so the failures worth guarding are the ones that widen it back: a loop over
nothing promoted because it calls something, a decision called a fork because its
*test* touches a boundary, a `finally` counted as a recovery, a guard on a worklist.

The fixture is a program where every answer is decidable by hand.
"""

from __future__ import annotations

import pytest

from dunneflow.resolve import shape
from dunneflow.resolve.calls import resolve_calls
from dunneflow.schema import ControlKind
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

PROGRAM = '''\
import sqlite3

import requests


def helper(row):
    return row


def rate(conn, rows):
    """A loop that issues one call per item. This is a rate, and a rate is flow."""
    for row in rows:
        conn.execute("INSERT INTO widgets (id) VALUES (?)", (row,))


def counting(rows):
    """A loop that moves nothing. A fact about the program, and never a worklist item."""
    total = 0
    for row in rows:
        total += len(row)
    return total


def calling(rows):
    """A loop that calls something of this program, and moves nothing itself."""
    for row in rows:
        helper(row)


def forking(conn, row):
    """One arm writes and the other does not. A decision about what leaves."""
    if row.kind == "witness":
        conn.execute("INSERT INTO seals (id) VALUES (?)", (row.id,))
    else:
        helper(row)


def alike(conn, row):
    """Both arms write. Arithmetic as far as this tool is concerned."""
    if row.kind == "witness":
        conn.execute("INSERT INTO seals (id) VALUES (?)", (row.id,))
    else:
        conn.execute("INSERT INTO seals (id) VALUES (?)", (row.id,))


def tested(conn, row):
    """The boundary is in the *test*, which belongs to no arm."""
    if conn.execute("SELECT 1 FROM seals").fetchone():
        helper(row)
    else:
        helper(row)


def ladder(row):
    """Three ways out and nothing moves in any of them."""
    if row.kind == "a":
        return 1
    elif row.kind == "b":
        return 2
    else:
        return 3


def recovering(conn, url):
    """The handler itself writes -- a second act nobody reading the happy path sees."""
    try:
        requests.post(url, timeout=5.0)
    except OSError:
        conn.execute("INSERT INTO audit (id) VALUES (?)", (url,))


def guarded(conn, url):
    """The body moves and the handler does not. What a `try` is for, and not news."""
    try:
        requests.post(url, timeout=5.0)
    except OSError:
        helper(url)
    finally:
        conn.execute("INSERT INTO audit (id) VALUES (?)", (url,))


def nested(conn, groups):
    """A boundary once per pass of a loop that is itself once per pass."""
    for group in groups:
        for row in group:
            conn.execute("INSERT INTO seals (id) VALUES (?)", (row,))


def under_a_branch(conn, rows):
    """Depth 2 and nested in nothing. The number that reads like the one above."""
    if rows:
        for row in rows:
            conn.execute("INSERT INTO seals (id) VALUES (?)", (row,))


def refusing(row):
    """A refusal. The largest shape in a real program, and never a worklist item."""
    if not row:
        return None
    return helper(row)


def over_a_query(conn):
    """The query is what the loop is *over*: one query, however many rows come back."""
    out = []
    for row in conn.execute("SELECT id FROM seals").fetchall():
        out.append(row[0])
    return out


def over_a_query_and_writing(conn):
    """Both halves on one loop: one query before the first pass, one write per pass."""
    for row in conn.execute("SELECT id FROM seals").fetchall():
        conn.execute("INSERT INTO audit (id) VALUES (?)", (row[0],))


def on_one_line(conn, ids):
    """A comprehension whose element and iterable share a line. Nothing can be excluded."""
    return [conn.execute("SELECT 1 FROM seals WHERE id=?", (i,)) for i in ids]


def polling(conn):
    """A `while` re-runs its test every pass, so its header is not evaluated once."""
    while conn.execute("SELECT done FROM seals").fetchone() is None:
        helper(conn)
'''


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    tree = tmp_path_factory.mktemp("shape_program")
    (tree / "m.py").write_text(PROGRAM)
    st = Store(tmp_path_factory.mktemp("shape_graph") / "graph.db")
    analyze_tree(tree, st)
    resolve_calls(st)
    st.conn.commit()
    yield st
    st.close()


def _by_routine(report: shape.ShapeReport) -> dict[str, list[shape.Point]]:
    out: dict[str, list[shape.Point]] = {}
    for p in report.points:
        out.setdefault(p.routine.rsplit(".", 1)[-1], []).append(p)
    return out


def test_a_loop_is_a_subject_only_where_something_moves_inside_it(store):
    """The amendment, stated as a test. Three loops, one of them a rate."""
    pts = _by_routine(shape.measure(store))
    hot = [p for p in pts["rate"] if p.kind == ControlKind.LOOP][0]
    cold = [p for p in pts["counting"] if p.kind == ControlKind.LOOP][0]
    assert hot.significant and hot.band == shape.MOVES, hot.why
    assert not cold.significant and cold.band == shape.STILL, cold.why
    assert "once per pass" in hot.why, hot.why


def test_a_loop_that_only_calls_something_is_kept_and_is_not_promoted(store):
    """Three bands and never two (design rule 1).

    Dropping it would lose a fact about the program; promoting it would put 467 of
    Society's 1,950 loops on a worklist on the strength of a call nobody followed.
    """
    loop = [p for p in _by_routine(shape.measure(store))["calling"]
            if p.kind == ControlKind.LOOP][0]
    assert loop.band == shape.CALLS, loop.band
    assert not loop.significant
    assert loop.calls == 1 and not loop.moves
    assert "nothing moves at these lines" in loop.why, loop.why


def test_a_query_a_loop_is_over_is_not_a_rate(store):
    """`for row in conn.execute(q).fetchall():` runs one query, not one per pass.

    It is written on a line inside the loop's own span, so the range join read it as a
    rate and said *once per pass* about it -- 11 of Society's 261, in the sentence that
    is this feature's headline. A span cannot tell what a loop is over from what it
    does, which is why `ControlPoint` records the lines it evaluates once.
    """
    loop = [p for p in _by_routine(shape.measure(store))["over_a_query"]
            if p.kind == ControlKind.LOOP][0]
    assert loop.once_start and loop.once_start == loop.line_start
    assert shape.places(loop.once) == 1, "the query is what the loop is over"
    assert not loop.repeated, "nothing happens on a pass of this loop"
    assert not loop.significant and loop.band == shape.STILL, loop.why
    # Named, never dropped (design rule 1): the query is really written there and the
    # ribbon draws it where it stands.
    assert loop.moves, "the move is kept on the point that holds it"
    assert "what it is over" in loop.why and "evaluated once" in loop.why, loop.why


def test_a_loop_can_be_over_a_query_and_still_be_a_rate(store):
    """The two halves are separate facts, and the sentence carries both."""
    loop = [p for p in _by_routine(shape.measure(store))["over_a_query_and_writing"]
            if p.kind == ControlKind.LOOP][0]
    assert loop.significant and loop.band == shape.MOVES, loop.why
    assert shape.places(loop.once) == 1 and shape.places(loop.repeated) == 1
    assert "once per pass" in loop.why, loop.why
    assert "before the first pass" in loop.why, loop.why


def test_a_loop_written_on_one_line_excludes_nothing(store):
    """`[f(x) for x in xs]` puts the element and the iterable on one line.

    A line cannot choose between them, so the range stays empty and the judgement is
    exactly what it was. Taking the iterable's span *without* subtracting the repeated
    lines reclassifies 45 of Society's loops and 34 of them wrongly -- comprehensions
    reaching a boundary would read 42 -> 5 rather than 42 -> 39. Rule 49: a plausible
    value is what hides the failure.
    """
    comp = [p for p in _by_routine(shape.measure(store))["on_one_line"]
            if p.kind == ControlKind.COMPREHENSION][0]
    assert (comp.once_start, comp.once_end) == (0, 0)
    assert not comp.once and comp.repeated == comp.moves
    assert comp.significant and comp.band == shape.MOVES, comp.why


def test_a_while_evaluates_its_header_every_pass(store):
    """A `while` and a `for` are one `ControlKind` and opposite facts about the header.

    So the word is recorded rather than guessed from it (rule 30): `while` and `for x in
    y` both arrive with a header, and only one of them runs it again. A poll loop whose
    test queries is a rate, and reading its test as an iterable would silence it.
    """
    loop = [p for p in _by_routine(shape.measure(store))["polling"]
            if p.kind == ControlKind.LOOP][0]
    assert loop.word == "while"
    assert (loop.once_start, loop.once_end) == (0, 0), "a test is not an iterable"
    assert loop.significant and loop.band == shape.MOVES, loop.why


def test_every_loop_records_the_word_it_was_written_with(store):
    """`exits`' own argument one kind over, and it is asserted over the whole fixture so
    a kind added later cannot arrive wordless."""
    for point in shape.measure(store).points:
        if point.kind is ControlKind.COMPREHENSION:
            assert point.word == "", "a comprehension opens with a bracket"
        else:
            assert point.word in {"for", "async for", "while", "if", "try", "match"}, (
                f"{point.kind} at {point.file}:{point.line_start} has no word"
            )


def test_a_table_is_not_reached_from_inside_the_loop_it_is_the_subject_of(store):
    """`enclosing` is the *"and vice versa"* half, and it inherits the same correction.

    A reader standing at a table asks what loops over it. A loop whose only touch of that
    table is its own iterable does not: it reaches the table once, before the first pass.
    Without this the pane says *"reached from inside 1 loop"* about a query the loop is
    written over -- 2 of Society's 64 tables, and the same `once` span has to decide it
    here and in `_judge_loop`, or a table's sentence and the Algorithms page describe one
    loop two ways (rule 51).
    """
    loops = [p for p in shape.enclosing(store, table="widgets")
             if p.kind == ControlKind.LOOP]
    assert [p.routine.rsplit(".", 1)[-1] for p in loops] == ["rate"], (
        "`over_a_query` reaches `widgets` once, before the first pass, and is not a loop "
        "over it"
    )


def test_a_decision_forks_only_when_its_arms_differ_in_what_moves(store):
    """A branch whose arms both write is arithmetic; one that writes on one side is a
    decision about what leaves the program. 78 of Society's 2,213 decisions fork."""
    pts = _by_routine(shape.measure(store))
    fork = [p for p in pts["forking"] if p.kind == ControlKind.DECISION][0]
    same = [p for p in pts["alike"] if p.kind == ControlKind.DECISION][0]
    assert fork.forks and fork.significant, fork.why
    assert not same.forks and not same.significant, same.why
    assert same.band == shape.MOVES, "the point still holds what its arms hold"


def test_a_boundary_in_the_test_does_not_make_a_fork(store):
    """`if fetch_row():` moves something from the decision's own header, which belongs
    to no arm. Attributing it to the arm written below would be a position mistaken for
    a meaning (rule 1) -- and it would report a fork in a decision whose two arms are
    identical."""
    point = [p for p in _by_routine(shape.measure(store))["tested"]
             if p.kind == ControlKind.DECISION][0]
    assert point.band == shape.MOVES, "the span does not see the boundary in its test"
    assert not any(a.moves for a in point.arms), (
        "an arm claims a move that happened on the test line"
    )
    assert not point.forks and not point.significant, point.why


def test_a_ladder_is_a_subject_on_its_shape_alone(store):
    """Three ways out is a shape a reader has to hold in their head, whatever is in
    them -- and the two decision tests are near-disjoint: 7 of Society's 78 forks are
    also ladders, so neither is a special case of the other."""
    point = [p for p in _by_routine(shape.measure(store))["ladder"]
             if p.kind == ControlKind.DECISION][0]
    assert point.band == shape.STILL, "nothing moves in this ladder, and it still counts"
    assert point.significant and "3 ways out" in point.why, point.why


def test_a_handler_is_a_subject_when_the_recovery_moves_something(store):
    """Not when the body does: 742 of Society's 1,531 handlers guard something that
    touches a boundary, which is what a `try` is for. 396 act on the way out."""
    pts = _by_routine(shape.measure(store))
    recovers = [p for p in pts["recovering"] if p.kind == ControlKind.HANDLER][0]
    guards = [p for p in pts["guarded"] if p.kind == ControlKind.HANDLER][0]
    assert recovers.recovers and recovers.significant, recovers.why
    assert not guards.recovers and not guards.significant, guards.why
    assert guards.band == shape.MOVES, "the try body's own boundary went missing"


def test_a_finally_is_not_a_recovery(store):
    """It runs on every path, including the one where nothing failed. Counting it would
    be a claim about failure drawn from a line that says nothing about it."""
    guards = [p for p in _by_routine(shape.measure(store))["guarded"]
              if p.kind == ControlKind.HANDLER][0]
    finallys = [a for a in guards.arms if a.kind.value == "finally"]
    assert finallys and finallys[0].moves, "the fixture's finally no longer writes"
    assert not guards.recovers, "a finally is being read as a recovery"


def test_a_guard_is_never_a_worklist_item_and_still_says_why(store):
    """3,931 of Society's 6,144 branches are refusals -- a worklist of them is a list of
    the program. It is recorded, banded and explained; it is just not offered."""
    guard = [p for p in _by_routine(shape.measure(store))["refusing"]
             if p.kind == ControlKind.GUARD][0]
    assert not guard.significant
    assert guard.exits == "return"
    assert "precondition" in guard.why and "returns" in guard.why, guard.why


def test_every_point_carries_a_reason_whether_or_not_it_passed(store):
    """A sentence that exists only for failures is a sentence nobody can check."""
    report = shape.measure(store)
    assert report.points, "nothing was measured at all"
    missing = [p for p in report.points if not p.why]
    assert not missing, f"{len(missing)} points state no reason"


def test_the_counts_are_counts_of_the_rows_beneath_them(store):
    """A lane's headline and its list cannot disagree, because one is the other counted
    (rule 13)."""
    report = shape.measure(store)
    counts = report.counts()
    for kind in ControlKind:
        rows = report.by_kind(kind)
        assert counts.get(kind.value, 0) == len(rows), kind
        assert counts.get(f"{kind.value}:significant", 0) == sum(
            1 for p in rows if p.significant), kind
    assert counts["significant"] == sum(1 for p in report.points if p.significant)


def test_one_moving_thing_at_one_line_is_counted_once(store):
    """569 of Society's 991 SQL operations sit on a line that is also a `boundaries`
    row. Summing the three tables reports one write as two, and a loop's *rate* is the
    number a reader will act on."""
    rate = [p for p in _by_routine(shape.measure(store))["rate"]
            if p.kind == ControlKind.LOOP][0]
    places = {m.line for m in rate.moves}
    assert len(places) == 1, "the fixture's loop no longer holds exactly one write"
    kinds = {m.kind for m in rate.moves}
    assert "SQL" in kinds, f"the SQL row was deduplicated away: {kinds}"
    assert len(rate.moves) == len({(m.line, m.kind, m.what) for m in rate.moves}), (
        "the same act at the same line is recorded twice"
    )


def test_one_routine_is_asked_for_by_itself_and_gets_the_same_answer(store):
    """A reader opening one routine must not pay for the other 9,600 points (rule 45),
    and the judgement has to be the same one either way (rule 51)."""
    report = shape.measure(store)
    rid = [p for p in report.points if p.routine.endswith("recovering")][0].routine_id
    whole = [(p.point_id, p.band, p.significant, p.why)
             for p in report.points if p.routine_id == rid]
    alone = [(p.point_id, p.band, p.significant, p.why)
             for p in shape.outline(store, rid)]
    assert whole == alone, "asking about one routine gives a different answer"


def test_inside_another_loop_is_not_deeper_than_one(store):
    """The headline of this whole feature, and the number that impersonates it.

    `depth` counts every enclosing control point, so a loop written inside an `if` has
    depth 2 and is nested in nothing. On Society 104 boundary loops sit deeper than 1
    and **10** are inside another loop -- and the ten are quadratic reaches into the
    outside world, which is a discovery, while the hundred are mostly `if`s.
    """
    pts = _by_routine(shape.measure(store))
    inner = [p for p in pts["nested"] if p.kind == ControlKind.LOOP and p.depth == 2][0]
    branched = [p for p in pts["under_a_branch"] if p.kind == ControlKind.LOOP][0]
    assert inner.in_loop, "a loop inside a loop does not know it"
    assert inner.why.endswith("inside another loop"), inner.why
    assert branched.depth == 2, "the fixture no longer puts this loop under a branch"
    assert not branched.in_loop, "a loop under an `if` is being called nested"
    assert "inside another loop" not in branched.why, branched.why


def test_two_comprehensions_on_one_line_still_nest(store, tmp_path):
    """Lines cannot separate `[a for a in [b for b in c]]`; `depth` is what does.

    Society has one -- a generator inside a list comprehension calling `is_file()` per
    element, which is one of its ten quadratic reaches.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "n.py").write_text(
        "import os\n\n\ndef f(rows):\n"
        "    return [a for a in [os.stat(b) for b in rows]]\n")
    st = Store(tmp_path / "graph.db")
    analyze_tree(tree, st)
    resolve_calls(st)
    st.conn.commit()
    comps = [p for p in shape.measure(st).points
             if p.kind == ControlKind.COMPREHENSION]
    st.close()
    assert len(comps) == 2, f"{len(comps)} comprehensions on that line"
    outer, inner = comps[0], comps[1]
    assert not outer.in_loop and inner.in_loop == outer.point_id, (
        "two comprehensions sharing a line do not nest"
    )


def test_one_statement_is_one_thing_that_moves(store):
    """An `INSERT` is a `DATABASE` row **and** a `SQL` row: one act at two altitudes.

    Counting rows says *two things move here* about one write, and it said so about 33 of
    Society's 261 rates, in the very sentence that gives them their rate. A place is the
    unit a reader counts; the rows are what is known about it.
    """
    rate = [p for p in _by_routine(shape.measure(store))["rate"]
            if p.kind == ControlKind.LOOP][0]
    assert len(rate.moves) > 1, "the fixture's write is no longer recorded twice"
    assert shape.places(rate.moves) == 1, "two descriptions of one write are two places"
    assert "once per pass" in rate.why and "of them" not in rate.why, rate.why


# --------------------------------------------------------------------------- #
# The other direction
# --------------------------------------------------------------------------- #

def test_a_table_is_asked_which_loops_write_it(store):
    """The reverse of `outline`, and the half that makes this a doorway.

    `seals` is written from four routines in the fixture, and the answer has to hold
    every span that encloses one of those writes -- not only the loops, because a table
    written from inside one arm of a decision is a fact about that table (design rule 1).
    """
    pts = shape.enclosing(store, table="seals")
    routines = {p.routine.rsplit(".", 1)[-1] for p in pts}
    assert {"forking", "alike", "nested", "under_a_branch"} <= routines, routines
    assert "rate" not in routines, "a loop writing `widgets` is answering about `seals`"

    kinds = {p.kind for p in pts}
    assert ControlKind.DECISION in kinds, (
        "only the loops came back; a decision that writes is being dropped for failing "
        "a test it was never asked (design rule 1)")


def test_the_deepest_nesting_is_containment_and_not_depth(store):
    """`under_a_branch` is depth 2 and nested in nothing; `nested` is the real one.

    This is the number that impersonates the headline. A pane saying *"deepest nesting
    2"* about a loop written inside an `if` has reported a quadratic reach into the
    outside world that is not there.
    """
    pts = shape.enclosing(store, table="seals")
    deep = shape.nesting(pts)
    loops = {p.routine.rsplit(".", 1)[-1]: p
             for p in pts if p.kind == ControlKind.LOOP}

    inner = [p for p in pts
             if p.kind == ControlKind.LOOP and p.routine.endswith("nested")
             and p.depth == 2][0]
    assert deep[inner.point_id] == 1, "the loop inside a loop is not counted as nested"
    assert loops["under_a_branch"].depth == 2, "the fixture stopped testing the trap"
    assert deep[loops["under_a_branch"].point_id] == 0, (
        "a loop under an `if` is being called nested; this is `depth`, not containment")
    assert max(deep[p.point_id] for p in loops.values()) == 1


def test_the_chain_above_a_point_is_whole(store):
    """A loop containing an inner loop contains the inner loop's lines too.

    So following `in_loop` from anything in the answer reaches everything above it
    without leaving the answer -- which is what lets a caller state a nesting depth at
    all. If `enclosing` ever filtered to the innermost span this silently becomes 0.
    """
    pts = shape.enclosing(store, table="seals")
    have = {p.point_id for p in pts}
    for p in pts:
        if p.in_loop:
            assert p.in_loop in have, (
                f"{p.routine}:{p.line_start} is inside a loop the answer does not hold")


def test_the_reverse_answer_is_the_same_judgement_as_the_forward_one(store):
    """The third entry point, held to the invariant the other two already keep.

    `measure` and `outline` agree by `test_one_routine_is_asked_for_by_itself...`; this
    is the same claim one door over. A second range join written for this question is
    exactly how the band a worklist shows and the band a pane shows come to differ
    (rule 51).
    """
    pts = shape.enclosing(store, table="seals")
    rid = [p for p in pts if p.routine.endswith("nested")][0].routine_id
    mine = sorted((p.point_id, p.band, p.significant, p.why)
                  for p in pts if p.routine_id == rid)
    alone = sorted((p.point_id, p.band, p.significant, p.why)
                   for p in shape.outline(store, rid))
    assert mine and mine == alone, "the reverse door judges a point differently"


def test_a_boundary_is_asked_the_same_question_as_a_table(store):
    """The other door in, and it is a second statement rather than a guessed shape.

    A caller holding `("NETWORK", url)` must not have to spell it as a table name and
    hope the string sorts into the right query (rule 30).
    """
    net = [p for p in shape.enclosing(store, boundary=("NETWORK", ""))
           if p.kind == ControlKind.HANDLER]
    assert not net or all(p.moves for p in net), (
        "a handler came back around a network call with nothing in it")

    with pytest.raises(ValueError, match="exactly one"):
        shape.enclosing(store, table="seals", boundary=("NETWORK", ""))
    with pytest.raises(ValueError, match="exactly one"):
        shape.enclosing(store)


def test_a_table_nothing_loops_over_answers_with_a_list_and_not_an_error(store):
    """Blank is an answer here, and the surface says why it is blank (design rule 21).

    A raise would make *"nothing loops over this"* indistinguishable from *"this table
    does not exist"*, which are different facts a pane has to word differently.
    """
    assert shape.enclosing(store, table="no_such_table_anywhere") == []
