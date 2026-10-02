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
    (tree / "m.py").write_text(PROGRAM, encoding="utf-8")
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
    """*250 of 1,950*, never *250 loops*.

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


# --------------------------------------------------------------------- the ribbon --- #
#
# One routine's whole shape, nested as it is written. A tree, so the failures worth
# guarding are the ones a tree has: a thing drawn at the wrong level, a thing drawn twice,
# a thing drawn nowhere.


def _rid(store, name: str) -> str:
    rows = store.query("SELECT id FROM routines WHERE name = ?", (name,))
    assert rows, f"the fixture has no routine called {name}"
    return str(rows[0]["id"])


def _walk(blocks, out=None, depth=0):
    out = [] if out is None else out
    for b in blocks:
        out.append((depth, b["type"], b.get("kind", ""), b.get("line", b.get("line_start"))))
        if b["type"] == "point":
            _walk(b["children"], out, depth + 1)
            for arm in b["arms"]:
                _walk(arm["children"], out, depth + 1)
    return out


def test_the_ribbon_nests_as_the_source_does(store):
    """A loop inside a loop is drawn inside it, and nothing decides that but the spans.

    Nassi and Shneiderman's drawing needs no control-flow graph because structured source
    never lost its structure — so this is a containment test and nothing more.
    """
    body = webshape.outline_for(store, _rid(store, "nested"))
    assert body["found"]
    outer = body["blocks"][0]
    assert outer["kind"] == "LOOP"
    inner = [b for b in outer["children"] if b["type"] == "point"]
    assert len(inner) == 1 and inner[0]["kind"] == "LOOP", (
        "the inner loop is not drawn inside the outer one"
    )
    assert [b["type"] for b in inner[0]["children"]] == ["move"], (
        "the write is not inside the inner loop"
    )
    assert outer["why"].endswith("once per pass"), outer["why"]
    assert "1 of them" not in inner[0]["why"], "a single write is being counted twice"


def test_a_moving_thing_is_drawn_once_and_at_its_innermost_span(store):
    """Twice over: once per *place*, and once per *level*.

    Repeating it at every enclosing level would draw one act four times, and make a rate
    look like a rate of four. Drawing the boundary row and the SQL row as two acts does
    the same thing on one line -- an `INSERT` is a `DATABASE` row and a `SQL` row, the
    same statement described at two altitudes, and 569 of Society's 991 SQL operations
    are one of these pairs.
    """
    body = webshape.outline_for(store, _rid(store, "nested"))
    moves = [x for x in _walk(body["blocks"]) if x[1] == "move"]
    assert len(moves) == 1, f"one write, drawn {len(moves)} times"
    assert moves[0][0] == 2, f"the write is drawn at depth {moves[0][0]}, not inside both loops"
    block = body["blocks"][0]["children"][0]["children"][0]
    assert block["kind"] == "SQL" and block["what"] == "widgets", (
        f"the place is led by the vaguer of its two descriptions: {block}"
    )
    assert block["also"] == ["DATABASE"], (
        "the other description was dropped rather than named beside it (design rule 1)"
    )


def test_a_decisions_arms_hold_what_is_written_in_them(store):
    """The fork lane's whole question, one level down: which way out writes."""
    body = webshape.outline_for(store, _rid(store, "forking"))
    point = body["blocks"][0]
    assert point["kind"] == "DECISION" and len(point["arms"]) == 2
    first, second = point["arms"]
    assert [b["type"] for b in first["children"]] == ["move"], first
    assert first["children"][0]["also"], "the arm's write lost the description beside it"
    assert [b["type"] for b in second["children"]] == ["call"], second


def test_a_guard_is_drawn_and_says_how_it_leaves(store):
    """The one place refusals belong. A routine's shape without them is a lie about the
    routine; a worklist of them is a list of the program."""
    body = webshape.outline_for(store, _rid(store, "refusing"))
    guards = [b for b in body["blocks"] if b.get("kind") == "GUARD"]
    assert guards, "the refusal is not drawn"
    assert guards[0]["exits"] == "return", guards[0]


def test_a_node_that_is_not_a_routine_is_refused_with_a_sentence(store):
    """A fold, a boundary and a table are all selectable and none has a shape of its own.

    A blank pane would say the routine had none, which is a different and false claim
    (design rule 21).
    """
    body = webshape.outline_for(store, "no-such-node")
    assert body["found"] is False
    assert body["reason"], "a refusal with no sentence is a blank pane"
    # A *sentence*, and both surfaces render it standing alone under their own heading.
    # It was a fragment, and the pane read "No shape to draw. that is not a routine".
    assert body["reason"][0].isupper() and body["reason"].endswith("."), (
        f"the refusal is a fragment, not a sentence: {body['reason']!r}")


def test_a_routine_that_runs_straight_through_is_an_answer(store):
    """`blocks: []` on a routine that exists is *not* the same silence as a refusal."""
    body = webshape.outline_for(store, _rid(store, "helper"))
    assert body["found"] is True
    assert body["blocks"] == [] and body["counts"] == {}
    assert body["routine"]["qualname"].endswith("helper")


# --------------------------------------------------------------------------- #
# The other direction: what loops over a named thing
# --------------------------------------------------------------------------- #

def test_a_table_is_told_how_many_loops_reach_it_and_how_deep(store):
    """`widgets` is written from `rate`'s loop and from both of `nested`'s.

    Three loops, and the deepest is one inside another -- which is the whole point of
    the clause: a boundary reached once per pass of a loop that is itself once per pass
    is a quadratic reach into the outside world.
    """
    b = webshape.loops_around(store, table="widgets")
    assert b["loops"] == 3, b["sentence"]
    assert b["deepest"] == 1, "the nested loop is not being seen as nested"
    assert "3 loops" in b["sentence"] and "inside another loop" in b["sentence"]


def test_the_sentence_counts_loops_and_says_the_places_separately(store):
    """*3 loops* and *3 writes* are different numbers (rule 32).

    A single figure would be read as whichever one the reader assumed, and the two are
    not the same: `nested`'s two loops hold one write between them.
    """
    b = webshape.loops_around(store, table="widgets")
    assert b["places"] < b["loops"] + b["places"], "the two figures collapsed into one"
    assert f"{b['loops']} loops" in b["sentence"]
    assert f"{b['places']} places" in b["sentence"]
    assert b["places"] == 2, (
        f"two writes to `widgets` sit inside loops, not {b['places']} -- `nested`'s "
        "two loops hold one write between them and counting spans would say three")


def test_the_nesting_clause_states_a_depth_and_never_a_count(store):
    """`deepest` is a maximum, so wording it as *"one of those is inside another"* is a
    claim about how many that nothing measured -- 89 loops with a deepest of 1 may have
    forty nested ones."""
    b = webshape.loops_around(store, table="widgets")
    assert "one of those" not in b["sentence"], b["sentence"]
    assert "the deepest of them" in b["sentence"], b["sentence"]


def test_a_table_reached_from_a_decision_and_no_loop_says_so_and_still_has_rows(store):
    """`seals` is written from one arm of `forking` and from no loop at all.

    The sentence is about loops and the rows are about every enclosing span, because a
    table written from inside a decision is a fact about that table (design rule 1). A
    pane that returned nothing here would have dropped the point for failing a test it
    was never asked.
    """
    b = webshape.loops_around(store, table="seals")
    assert b["loops"] == 0 and b["sentence"] == "not reached from inside any loop"
    assert b["rows"], "the decision that writes `seals` came back as nothing"
    assert {r["kind"] for r in b["rows"]} == {"DECISION"}


def test_a_row_here_is_the_same_row_the_worklist_draws(store):
    """One row shape, so a fix to the worklist's row is a fix to the pane's (rule 51)."""
    b = webshape.loops_around(store, table="widgets")
    lane_row = _lane(webshape.for_program(store), "rates")["rows"][0]
    for row in b["rows"]:
        assert set(lane_row) <= set(row), (
            f"the pane's row is missing {sorted(set(lane_row) - set(row))}")
        assert row["node"] and row["point"] and row["why"] and ":" in row["where"]
        assert "nested" in row, "a pane row cannot say how deep it sits"


def test_nothing_is_reached_from_inside_a_loop_in_a_program_with_none(store):
    """The blank answer is a sentence, not an empty block (design rule 21)."""
    b = webshape.loops_around(store, boundary=("ENV", "NOTHING_READS_THIS"))
    assert b == {"loops": 0, "points": 0, "deepest": 0, "places": 0,
                 "sentence": "not reached from inside any loop", "rows": []}


def test_the_inspector_counts_only_what_moves_inside_a_span(tmp_path):
    """BACKLOG 18: the sentence is "N things move inside them", and a write after both
    loops was counted in N. What sits at the top of a routine is not inside anything."""
    tree = tmp_path / "prog"
    tree.mkdir()
    (tree / "m.py").write_text(
        "import sqlite3\n"
        "\n"
        "def helper(x):\n"
        "    return x\n"
        "\n"
        "def after(conn, rows):\n"
        "    for row in rows:\n"
        "        helper(row)\n"
        "    conn.execute('INSERT INTO done (id) VALUES (1)')\n"
        "    helper(rows)\n",
        encoding="utf-8")
    st = Store(tmp_path / "graph.db")
    try:
        analyze_tree(tree, st)
        resolve_calls(st)
        counts = webshape.outline_for(st, _rid(st, "after"))["counts"]
        assert counts.get("LOOP") == 1, counts
        assert counts.get("moves", 0) == 0, f"the write after the loop was counted: {counts}"
        assert counts.get("calls") == 1, f"only `helper(row)` is inside the loop: {counts}"
    finally:
        st.close()
