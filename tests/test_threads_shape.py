"""Code that runs the same shape, which no call edge can say.

Two routines that each loop over one table never call one another; two that branch on the
same test are coupled through a decision. The call graph records neither, and the
`algorithm` lane is the only place in the product that can.

The failure this file is written against is `3cfce1b`'s: **a thread that counts one
population and opens another.** It renders perfectly either way -- "2 other routines" over
a button that opens nine -- so every test here checks the figure against the destination
rather than checking the figure.
"""

from __future__ import annotations

import pytest

from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import threads

PROGRAM = '''\
import sqlite3


def helper(row):
    return row


def writer_one(conn, rows):
    """Loops over `seals`. So does `writer_two`, and they never call each other."""
    for row in rows:
        conn.execute("INSERT INTO seals (id) VALUES (?)", (row,))


def writer_two(conn, rows):
    """The other end of that coupling."""
    for row in rows:
        conn.execute("UPDATE seals SET id = ? WHERE id = ?", (row, row))


def lonely_writer(conn, rows):
    """Loops over a table nothing else loops over. The answer is *nothing else does*."""
    for row in rows:
        conn.execute("INSERT INTO alone (id) VALUES (?)", (row,))


def straight_writer(conn, row):
    """Touches `seals` and loops over nothing. Not a neighbour of the two above."""
    conn.execute("INSERT INTO seals (id) VALUES (?)", (row,))


def decides_one(conn, row):
    if row.kind == "witness":
        conn.execute("INSERT INTO seals (id) VALUES (?)", (row,))
    else:
        helper(row)


def decides_two(conn, row):
    if row.kind == "witness":
        helper(row)
    else:
        conn.execute("INSERT INTO alone (id) VALUES (?)", (row,))


def decides_alone(conn, row):
    if row.kind == "nobody_else_tests_this":
        helper(row)
    else:
        conn.execute("INSERT INTO alone (id) VALUES (?)", (row,))


def refusing(row):
    if not row:
        return None
    return helper(row)
'''


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    tree = tmp_path_factory.mktemp("threadshape_program")
    (tree / "m.py").write_text(PROGRAM)
    st = Store(tmp_path_factory.mktemp("threadshape_graph") / "graph.db")
    analyze_tree(tree, st)
    resolve_calls(st)
    st.conn.commit()
    yield st
    st.close()


def _rid(store: Store, name: str) -> str:
    rows = store.query("SELECT id FROM routines WHERE name = ?", (name,))
    assert rows, f"the fixture no longer defines {name}"
    return str(rows[0]["id"])


def _algo(store: Store, name: str) -> list[dict]:
    rid = _rid(store, name)
    row = store.query("SELECT module, name FROM routines WHERE id = ?", (rid,))[0]
    body = threads.for_node(store, rid, module=row["module"], name=row["name"])
    return [t for t in body["threads"] if t["kind"] == "algorithm"]


def test_two_routines_that_loop_over_one_table_are_neighbours(store):
    """Neither calls the other, and no call edge records the coupling."""
    got = _algo(store, "writer_one")
    tables = [t for t in got if t["subject"]["kind"] == "looped_table"]
    assert [t["label"] for t in tables] == ["seals"], tables
    assert tables[0]["count"] == 1, "writer_two is not being seen"
    assert "you loop over it" in tables[0]["why"]


def test_a_thread_opens_exactly_the_routines_it_counted(store):
    """`3cfce1b`'s rule, and the reason `looped_table` exists beside `table`.

    `TABLE_ROUTINES` would open every routine that touches `seals` -- including
    `straight_writer`, which loops over nothing -- while the figure beside it counts only
    the ones that loop. One number, one destination (rule 32).
    """
    rid = _rid(store, "writer_one")
    for t in _algo(store, "writer_one"):
        sub = t["subject"]
        opened = threads.cohort(store, sub["kind"], sub["key"])
        assert opened["found"] is True, opened
        others = [n for n in opened["nodes"] if n != rid]
        assert len(others) == t["count"], (
            f"{sub['kind']} {sub['key']!r} counts {t['count']} and opens {len(others)}")

    seals = threads.cohort(store, "looped_table", "seals")
    assert _rid(store, "straight_writer") not in seals["nodes"], (
        "a routine that touches the table without looping is in the loop cohort")
    assert _rid(store, "writer_two") in seals["nodes"]


def test_a_table_nothing_else_loops_over_still_says_so(store):
    """*"You are the only one"* is the answer a reader most wants at a table they are
    about to change, and it is exactly what a `HAVING others > 0` deletes (design rule 1).
    """
    got = [t for t in _algo(store, "lonely_writer")
           if t["subject"]["kind"] == "looped_table"]
    assert [t["label"] for t in got] == ["alone"]
    assert got[0]["count"] == 0
    assert got[0]["why"] == "you loop over it · nothing else does"


def test_a_routine_that_loops_over_nothing_gets_no_table_thread(store):
    """`straight_writer` touches `seals` and loops over nothing. The boundary lane already
    tells it who else touches the table; this lane is about what runs the same shape."""
    assert not [t for t in _algo(store, "straight_writer")
                if t["subject"]["kind"] == "looped_table"]


def test_two_routines_that_make_one_decision_are_neighbours(store):
    """`decides_one` and `decides_two` branch on the same written test and differ in every
    other way -- different arms, different tables, no call between them."""
    got = [t for t in _algo(store, "decides_one")
           if t["subject"]["kind"] == "decision"]
    assert [t["label"] for t in got] == ['row.kind == "witness"'], got
    assert got[0]["count"] == 1
    assert "as written" in got[0]["why"], (
        "the thread no longer states that the comparison is textual, which is its whole "
        "blind spot")

    opened = threads.cohort(store, "decision", 'row.kind == "witness"')
    assert set(opened["nodes"]) == {_rid(store, "decides_one"), _rid(store, "decides_two")}


def test_a_test_nobody_else_makes_is_not_a_neighbour(store):
    """1,348 of Society's 1,516 distinct headers are made once. Keeping them would bury
    the 168 that mean something -- and unlike a table, a decision made once is simply this
    routine's own line rather than a shared thing nobody happens to share."""
    assert not [t for t in _algo(store, "decides_alone")
                if t["subject"]["kind"] == "decision"]


def test_a_refusal_is_not_a_decision(store):
    """`resolve/shape.py` draws that line and this lane keeps it. 3,931 of Society's
    9,625 points are guards, and admitting them would drown every real decision."""
    for name in ("refusing", "decides_one"):
        for t in _algo(store, name):
            assert "not row" not in t["label"], (
                f"a guard reached the decision lane from {name}")


def test_rarity_sorts_first(store):
    """The test 321 routines make is the least interesting thing on the list; the one two
    others make is the discovery. The boundary lane sorts this way and so does this."""
    got = _algo(store, "decides_one")
    assert [t["count"] for t in got] == sorted(t["count"] for t in got)
