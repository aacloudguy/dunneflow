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


def test_a_decision_forks_only_when_its_arms_differ_in_what_moves(store):
    """A branch whose arms both write is arithmetic; one that writes on one side is a
    decision about what leaves the program. 77 of Society's 2,213 decisions fork."""
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
    them -- and the two decision tests are near-disjoint: 7 of Society's 77 forks are
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
