"""A table answers as a table, and not as the first routine that touches it.

The defect this file guards is three sessions old and has been fixed twice already one
subject over: `detail.fold` undid it for a box of methods and `plate.py` undid it for a
plate of 926 nodes. Selecting a table did it a third time -- `selectFromNav` replaced the
whole request with the routines that touch it, so the inspector answered truthfully about
something nobody had clicked.
"""

from __future__ import annotations

from dunneflow.web import table


def test_a_table_answers_as_a_table_and_not_as_a_node(analyzed):
    """`kind` is the whole guard. Calling it a ROUTINE would put the wrong word in the
    inspector's head and the wrong answer in every check that reads it (rule 30)."""
    d = table.describe(analyzed, "widgets")
    assert d["found"] is True
    assert d["kind"] == "TABLE"
    assert d["id"] == "widgets" == d["label"], (
        "a table's id is its name -- minting `tbl:widgets` would be a second id space "
        "for a fact the program already states")


def test_a_table_fills_the_skeleton_every_other_specimen_fills(analyzed):
    """`viewInspector` has one rendering path with a default for every key (rule 51), so
    a specimen that omits one renders through code that was never asked about it."""
    d = table.describe(analyzed, "widgets")
    assert set(d["in"]) == {"callers", "entrypoints"}
    assert set(d["touches"]) == {"boundaries", "sql", "net", "artefacts"}
    assert set(d["governance"]) == {"annotations", "comments"}
    assert "out" in d and "where" in d and "identity" in d


def test_the_operation_counts_add_up(analyzed):
    """A pane printing *"27 operations, 12 writes, 8 reads"* has silently filtered seven
    of them -- `CREATE TABLE`, `BEGIN` and `COMMIT` are neither (design rule 1)."""
    i = table.describe(analyzed, "widgets")["identity"]
    assert i["writes"] + i["reads"] + i["other"] == i["ops"], i
    assert i["ops"] == len(table.describe(analyzed, "widgets")["in"]["callers"]), (
        "the operation count and the list of touchers are two populations under one name")


def test_a_declared_table_carries_its_columns_in_the_order_they_were_written(analyzed):
    """`idx` is the position in the `CREATE TABLE`, so ordering by it quotes the
    statement rather than sorting it."""
    i = table.describe(analyzed, "widgets")["identity"]
    assert [c["name"] for c in i["columns"]] == ["id", "name", "qty"]
    assert i["origin"] == "declared here"


def test_a_table_declared_once_hands_the_source_pane_a_place_to_open(analyzed):
    """And only then. Two `CREATE TABLE`s for one name are two answers, and opening the
    first would be a position mistaken for a meaning (rule 1)."""
    d = table.describe(analyzed, "widgets")
    assert d["where"] and d["where"]["file"].endswith(".py")
    assert d["where"]["first"] == d["where"]["last"] > 0


def test_a_table_this_program_only_touches_is_described_not_refused(analyzed):
    """A program that reads somebody else's schema declares nothing, and 12 of Society's
    65 tables are exactly that. Refusing them would blank the pane on the tables a reader
    most wants explained (design rule 21)."""
    got = analyzed.query(
        "SELECT DISTINCT tbl FROM sql_ops"
        " WHERE tbl <> '' AND tbl NOT IN (SELECT name FROM db_tables) LIMIT 1")
    only_touched = [r["tbl"] for r in got]
    if not only_touched:                      # the sample declares everything it touches
        return
    d = table.describe(analyzed, only_touched[0])
    assert d["found"] is True
    assert d["identity"]["origin"].startswith("not declared in this program")
    assert d["where"] is None, "a table declared nowhere was given a place to open"


def test_a_name_nothing_mentions_is_refused_with_a_sentence(analyzed):
    """Different from a real table nothing loops over, and the two look identical on a
    blank pane (design rule 21)."""
    d = table.describe(analyzed, "no_such_table_anywhere")
    assert d["found"] is False
    assert "no_such_table_anywhere" in d["reason"]
    assert d["kind"] == "TABLE", "a refusal that forgets what was asked about"


def test_a_table_carries_the_loops_that_reach_it(analyzed):
    """The links back. The sample has no loop over `widgets`, and blank is an answer
    that says why it is blank rather than an absent block."""
    b = table.describe(analyzed, "widgets")["loops"]
    assert b["sentence"] == "not reached from inside any loop"
    assert b["loops"] == 0 and b["rows"] == []
