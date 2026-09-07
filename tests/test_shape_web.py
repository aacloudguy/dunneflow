"""ALGORITHMS, served: five lanes, their denominators, and what they left out.

The judgement is `resolve/shape.py`'s and is tested in `test_shape.py`. What is tested
here is the arrangement, and every test is a way this page can be confidently wrong: a
lane that vanishes when it finds nothing, a count that is not a count of the rows beneath
it, a denominator that flatters the lane by counting only what it holds, a row that
cannot be opened.
"""

from __future__ import annotations

import pytest

from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import shape as webshape

PROGRAM = '''\
import sqlite3


def helper(row):
    return row


def rate(conn, rows):
    for row in rows:
        conn.execute("INSERT INTO widgets (id) VALUES (?)", (row,))


def nested(conn, groups):
    for group in groups:
        for row in group:
            conn.execute("INSERT INTO widgets (id) VALUES (?)", (row,))


def quiet(rows):
    total = 0
    for row in rows:
        total += len(row)
    return total


def forking(conn, row):
    if row.kind == "a":
        conn.execute("INSERT INTO seals (id) VALUES (?)", (row.id,))
    else:
        helper(row)


def ladder(row):
    if row.kind == "a":
        return 1
    elif row.kind == "b":
        return 2
    else:
        return 3


def refusing(row):
    if not row:
        return None
    return helper(row)


def recovering(conn, row):
    try:
        helper(row)
    except OSError:
        conn.execute("INSERT INTO audit (id) VALUES (?)", (row,))
'''


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    tree = tmp_path_factory.mktemp("shapeweb_program")
    (tree / "m.py").write_text(PROGRAM)
    st = Store(tmp_path_factory.mktemp("shapeweb_graph") / "graph.db")
    analyze_tree(tree, st)
    resolve_calls(st)
    st.conn.commit()
    yield st
    st.close()


@pytest.fixture(scope="module")
def body(store):
    return webshape.for_program(store)


def _lane(body, key):
    return next(x for x in body["lanes"] if x["key"] == key)


def test_every_lane_is_served_in_its_declared_order(body):
    """Five lanes, always, whatever this program holds.

    The list is fixed for the curiosities' reason: a lane that appears only when it has
    something to say cannot be told from one nobody has measured, and the reader has no
    way to ask which happened.
    """
    assert [x["key"] for x in body["lanes"]] == [lane.key for lane in webshape.LANES]


def test_a_lane_with_nothing_in_it_is_still_a_lane(body):
    """Society has no `match` at all, and this program has none either.

    Design rule 21: absent and empty are different answers, and the empty one has a
    denominator to state — *these many decisions were measured and not one is a match*.
    """
    matches = _lane(body, "matches")
    assert matches["n"] == 0 and matches["rows"] == []
    assert matches["population"] > 0, "an empty lane with no denominator says nothing"


def test_a_lane_count_is_a_count_of_the_rows_beneath_it(body):
    """One is the other counted, so the headline and the list cannot disagree (rule 13)."""
    for lane in body["lanes"]:
        assert lane["n"] == len(lane["rows"]), lane["key"]


def test_a_denominator_is_the_whole_population_and_not_the_lane(body):
    """*261 of 1,950*, never *261 loops*.

    The whole point of the judgement is that most of a program's loops are not subjects.
    A lane that hides its denominator claims its rows are all there is, which is the
    silent filter design rule 1 refuses.
    """
    rates = _lane(body, "rates")
    q = body["quiet"]
    assert rates["population"] == q["loops"]
    assert rates["n"] + q["still_loops"] + q["calling_loops"] == q["loops"], (
        "the three bands do not partition the loops, so one of them is being counted twice"
    )
    forks = _lane(body, "forks")
    assert forks["population"] == q["decisions"] > forks["n"]


def test_what_is_left_out_is_counted_where_a_reader_can_see_it(body):
    """Four lanes holding a fraction of what was measured is a claim about the rest."""
    q = body["quiet"]
    assert q["guards"] > 0, "this program's refusals went missing"
    assert q["loops"] and q["decisions"] and q["handlers"]
    assert body["points"] > sum(x["n"] for x in body["lanes"])


def test_a_row_carries_what_it_takes_to_open_it(body):
    """`node` is the routine, because that is what selecting a loop means today.

    A span is not a node in the graph and minting one to make the row clickable would be
    a link to nothing. `point` rides beside it so a surface that selects the span itself
    does not invent a second id for one fact (rule 30).
    """
    for lane in body["lanes"]:
        for row in lane["rows"]:
            assert row["node"], f"{lane['key']} row cannot be opened: {row['where']}"
            assert row["point"], f"{lane['key']} row has no identity of its own"
            assert row["why"], "a row states no reason"
            assert ":" in row["where"]


def test_the_rates_lane_puts_a_loop_inside_a_loop_first(body):
    """The headline of the feature: a boundary once per pass of a loop that is itself
    once per pass. It is also the row that says *which* loop it is inside, by line."""
    rows = _lane(body, "rates")["rows"]
    assert rows and rows[0]["inside"], "a nested rate is not sorted to the top"
    assert rows[0]["inside"]["line"] < rows[0]["line"]
    assert body["quiet"]["nested_rates"] == sum(1 for r in rows if r["inside"])
    assert not rows[-1]["inside"], "every rate in this fixture is nested; it should not be"


def test_a_handler_row_can_name_what_it_caught(body):
    """A `try` has no header by design, so its row would print nothing at all.

    Its `except` clauses are what the recovery lane is about, and they come off the arms
    with the count of what moves in each — which is what lets the page mark the one that
    acts without a second sentence to say so.
    """
    rows = _lane(body, "recoveries")["rows"]
    assert rows, "the fixture no longer recovers by moving something"
    assert rows[0]["header"] == "", "a try has acquired a header"
    caught = [a for a in rows[0]["arm_moves"] if a["kind"] == "except"]
    assert caught and caught[0]["header"] == "OSError", caught
    assert any(a["n"] for a in caught), "no handler arm moves anything, so the lane is wrong"
