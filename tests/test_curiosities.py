"""What came out furthest from the middle, and whether the panel can be trusted about it.

Every test here is a way this panel can be wrong while looking right, and the first one
is the one the whole design rests on: **the query a card offers must be the query that
produced the card**. A number beside a query that returns something else is worse than a
number alone — it invites a reader to check, and then misleads them (rule 13).

The fixtures are built to make the answers *decidable by hand*. A program where the most
commented routine is obvious, the middle is countable on fingers, and a deliberate tie
exists, so a wrong answer is wrong visibly rather than plausibly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import curiosities


def _store(tmp_path: Path, source: str, name: str = "m.py") -> Store:
    """A one-file program, extracted **and resolved**.

    The resolve pass is not optional here and its absence is not obvious: `calls.callee_id`
    is filled by `resolve_calls`, so an extract-only fixture has no resolved callers at all
    and the `callers` family comes back silent -- which this panel would report honestly and
    a test would read as a measure that does not work.
    """
    tree = tmp_path / "tree"
    tree.mkdir(exist_ok=True)
    src = tree / name
    src.write_text(source)
    store = Store(tmp_path / "graph.db")
    analyze_tree(tree, store)
    resolve_calls(store)
    store.conn.commit()
    return store


# One routine is plainly the most commented, plainly the longest, and plainly the most
# called; two closures are deliberately nested to the same depth so a tie is exercised.
PROGRAM = '''\
import sqlite3

# a
# b
# c
# d
def busy(one, two, three):
    """Docstring, which is not a comment."""
    # e
    # f
    x = one
    # g
    y = two
    # h
    return x, y


def caller_a():
    busy(1, 2, 3)


def caller_b():
    busy(4, 5, 6)


def caller_c():
    busy(7, 8, 9)


def quiet():
    # one comment only
    return 1


def outer_one():
    def middle():
        def inner():
            return 1
        return inner
    return middle


def outer_two():
    def middle():
        def inner():
            return 2
        return inner
    return middle


def touches(conn: sqlite3.Connection):
    # Plan 12-01
    conn.execute("INSERT INTO ledger (a) VALUES (1)")
    conn.execute("SELECT a FROM ledger")
    conn.execute("SELECT a FROM ledger")
    conn.execute("SELECT a FROM ledger")


def also_governed():
    # Plan 12-01 again, from a second routine
    return 1


class Governed:
    """A structure carrying Plan 12-01, in its docstring where a structure's own
    annotations are mined from.

    Deliberate, and it is the defect this fixture exists to hold: an annotation's owner
    is a routine *or a structure*, so a measure counting every owner and calling the
    total "routines" comes out one higher than the set following the card opens. A
    comment on a class body would not do it -- rule 18 files those under module scope,
    which is a routine, and the first version of this fixture was written that way and
    could not tell the defect from the fix.
    """

    field: int = 0
'''


def _by_key(body: dict) -> dict[str, dict]:
    return {c["key"]: c for c in body["curiosities"]}


# --------------------------------------------------------------------------- #
# Rule 13: the query is the provenance, so it must return what is printed
# --------------------------------------------------------------------------- #

def test_every_cards_own_query_returns_exactly_what_the_card_prints(tmp_path):
    """The strongest form available: run the shipped SQL and compare, number by number.

    A card offers `dunneflow query --sql "…"` as its proof. If that statement returns
    anything but the four numbers beside it, the offer is worse than no offer at all --
    it is an invitation to check, and then a different answer. Three of the first
    twenty-seven measured naming conventions failed exactly this way.

    Re-running the *shipped string* rather than the module constant matters: it is what
    reaches the reader, and a card that trimmed, wrapped or interpolated its SQL on the
    way out would pass a check made against `queries.py`.
    """
    store = _store(tmp_path, PROGRAM)
    body = curiosities.for_program(store)
    assert body["curiosities"], "nothing measured -- this test is blind"

    for card in body["curiosities"]:
        rows = store.query(card["sql"], {})
        assert rows, f"{card['key']}: the query the card offers returns nothing"
        row = dict(rows[0])
        assert row["value"] == card["value"], card["key"]
        assert row["middle"] == card["middleValue"], card["key"]
        assert row["ties"] == card["ties"], card["key"]
        assert row["population"] == card["population"], card["key"]


def test_the_printed_ratio_is_the_two_printed_numbers_divided(tmp_path):
    """Rule 13 again, on the one number that is computed rather than queried.

    The ratio is the panel's ordering *and* its headline claim, so it must be derivable
    from the two numbers on the same card. A ratio taken from anywhere else would rank
    the list by something the reader cannot check.
    """
    store = _store(tmp_path, PROGRAM)
    for card in curiosities.for_program(store)["curiosities"]:
        if card["middleValue"]:
            assert card["ratio"] == card["value"] / card["middleValue"], card["key"]
            assert card["ratioText"].endswith("× the middle"), card["key"]
        else:
            assert card["ratio"] is None, card["key"]
            assert "nothing to divide by" in card["ratioText"], card["key"]


# --------------------------------------------------------------------------- #
# The measurements themselves, against a program small enough to count by hand
# --------------------------------------------------------------------------- #

def test_the_extremum_is_the_thing_a_reader_would_have_picked(tmp_path):
    store = _store(tmp_path, PROGRAM)
    cards = _by_key(curiosities.for_program(store))

    # Eight comments inside `busy` and its leading block; every other routine has one.
    assert cards["comments"]["what"] == "busy"
    assert cards["comments"]["value"] == 8
    # A docstring is not a comment (rule 9) and must not have been counted as one.
    assert "Docstring" not in cards["comments"]["middle"]

    assert cards["callers"]["what"] == "busy"
    assert cards["callers"]["value"] == 3

    assert cards["params"]["what"] == "busy"
    assert cards["params"]["value"] == 3

    assert cards["lines"]["what"] == "busy"

    # `ledger` is read three times and written once.
    assert cards["table"]["what"] == "ledger"
    assert cards["table"]["value"] == 3.0


def test_the_module_scope_is_named_as_the_module_it_is(tmp_path):
    """`<module>` is a real node (rule 18) and on its own the name says nothing.

    One renderer for both panels -- `threads.label_of` -- so the doorway panel and the
    threads panel cannot start calling the same node two different things.
    """
    store = _store(tmp_path, "# a\n# b\n# c\nX = 1\n")
    cards = _by_key(curiosities.for_program(store))
    assert cards["comments"]["what"] == "m", cards["comments"]["what"]
    assert "<module>" not in cards["comments"]["what"]


def test_a_tie_is_counted_and_the_named_one_is_an_example(tmp_path):
    """Naming one of several as though it were unique is a false claim, quietly.

    Two closures are nested identically in the fixture. The card must say so; which of
    the two it names is arbitrary and stable, and that is exactly why the count has to
    be there.
    """
    store = _store(tmp_path, PROGRAM)
    depth = _by_key(curiosities.for_program(store))["depth"]
    assert depth["ties"] >= 2, depth
    assert depth["tie"], "a tie exists and the card says nothing about it"
    assert f"{depth['ties'] - 1:,} other" in depth["tie"], depth["tie"]


def test_nothing_ties_and_the_card_says_nothing_about_ties(tmp_path):
    """The other half, and it is the half a bare `if` gets wrong.

    "1 other is as long" on a unique extremum is a claim about a routine that does not
    exist, and a tie sentence reading "0 others" is the same defect wearing arithmetic.
    """
    store = _store(tmp_path, PROGRAM)
    comments = _by_key(curiosities.for_program(store))["comments"]
    assert comments["ties"] == 1
    assert comments["tie"] == "", comments["tie"]


# --------------------------------------------------------------------------- #
# Ordering, completeness, and saying what was not measured
# --------------------------------------------------------------------------- #

def test_the_panel_is_ordered_by_distance_from_the_middle(tmp_path):
    """Not by declaration order, which is what it would fall back to unnoticed.

    Asserted over a program where the two orders genuinely differ, because a list that
    happens to come out in declaration order proves nothing about how it was sorted.
    """
    store = _store(tmp_path, PROGRAM)
    body = curiosities.for_program(store)
    ratios = [c["ratio"] for c in body["curiosities"]]
    ranked = [r for r in ratios if r is not None]
    assert ranked == sorted(ranked, reverse=True), ratios
    # A ratio that cannot be computed is as far out as anything can be, so it leads.
    assert all(r is None for r in ratios[:len(ratios) - len(ranked)])

    declared = [f.key for f in curiosities.FAMILIES]
    shown = [c["key"] for c in body["curiosities"]]
    assert shown != [k for k in declared if k in shown], (
        "the panel came out in declaration order, so this fixture cannot tell a sorted "
        "list from an unsorted one -- change the fixture, not the assertion"
    )


def test_a_measure_with_nothing_to_measure_is_named_rather_than_dropped(tmp_path):
    """Design rule 1: nine cards and ten cards are different claims.

    A program that runs no SQL has no lopsided table, and a reader looking at a panel
    with that card missing cannot tell a measure that was taken and came out empty from
    one that was never taken at all.
    """
    store = _store(tmp_path, "def f():\n    return 1\n")
    body = curiosities.for_program(store)
    assert "table" in body["silent"], body["silent"]
    assert body["families"] == len(curiosities.FAMILIES)
    assert len(body["curiosities"]) + len(body["silent"]) == body["families"]


def test_every_family_is_answered_or_named_and_none_goes_missing(tmp_path):
    """The partition, asserted as one. A family that is neither shown nor named as
    silent has vanished, and a fixed complete list is the only reason rule 8's bound
    never has to arise here."""
    store = _store(tmp_path, PROGRAM)
    body = curiosities.for_program(store)
    seen = {c["key"] for c in body["curiosities"]} | set(body["silent"])
    assert seen == {f.key for f in curiosities.FAMILIES}


# --------------------------------------------------------------------------- #
# Rule 30: a card that goes nowhere is worse than an absent card
# --------------------------------------------------------------------------- #

def test_every_card_carries_a_subject_a_router_can_act_on(tmp_path):
    store = _store(tmp_path, PROGRAM)
    for card in curiosities.for_program(store)["curiosities"]:
        s = card["subject"]
        assert s["type"] in {"node", "cohort"}, card["key"]
        if s["type"] == "node":
            assert s["id"], f"{card['key']}: a node subject with no id opens nothing"
        else:
            assert s["kind"] and s["key"], card["key"]


def test_a_middle_of_zero_is_stated_rather_than_divided_by(tmp_path):
    """Rule 49: the plausible value is what hides the failure.

    A large number over nothing is not "infinitely interesting", it is a question the
    arithmetic cannot answer, and `value / max(middle, 1)` would print a confident ratio
    that is really just the value wearing a multiplication sign.

    Driven through `_card` with a constructed row rather than through a corpus, and that
    is the honest place for it: every shipped query groups over things that *have* the
    measure, so no real program can produce a middle of zero and a fixture pretending to
    would be a fixture about nothing. The branch exists for the family nobody has written
    yet, so it is tested where it can actually be reached.
    """
    store = _store(tmp_path, PROGRAM)
    fam = next(f for f in curiosities.FAMILIES if f.subject == "node")
    row = dict(store.query(fam.sql, {})[0])
    row["middle"] = 0
    card = curiosities._card(fam, row)
    assert card["ratio"] is None, card["ratio"]
    assert "nothing to divide by" in card["ratioText"], card["ratioText"]
    assert "×" not in card["ratioText"], (
        "a ratio is printed for a value with no middle beneath it -- the number is the "
        "value again, wearing a multiplication sign"
    )


def test_a_card_that_counts_its_cohort_opens_exactly_what_it_counted(tmp_path):
    """The number on the card and the set the follow opens must be the same set.

    The governance card said "121 routines carry one governance id" and opened **112**,
    because an annotation's owner is a routine *or a structure* and the measure counted
    both while `GOVERNANCE_ROUTINES` -- which resolves the cohort -- has always been
    scoped to routines. Two defects in one clause: a wrong noun (rule 32) and a number a
    reader catches out the moment they click it.

    Written against `counts_its_cohort` rather than against the governance family, so the
    next cohort measured by its own size is covered without anyone remembering. Found by
    following the card and counting what came back, not by any check that existed.
    """
    from dunneflow.web import threads

    store = _store(tmp_path, PROGRAM)
    body = curiosities.for_program(store)
    claims = {f.key for f in curiosities.FAMILIES if f.counts_its_cohort}
    assert claims, "no family counts its own cohort -- this test is blind"

    checked = 0
    for card in body["curiosities"]:
        if card["key"] not in claims:
            continue
        s = card["subject"]
        assert s["type"] == "cohort", f"{card['key']} counts a cohort and is not one"
        opened = threads.cohort(store, s["kind"], s["key"])
        assert opened["found"], card["key"]
        assert len(opened["nodes"]) == card["value"], (
            f"{card['key']}: the card counts {card['value']} and following it opens "
            f"{len(opened['nodes'])} -- the number and the set are not the same set"
        )
        checked += 1
    assert checked, "no cohort-counting card was measured by this fixture"


def test_a_family_naming_an_unknown_subject_kind_is_a_named_error(tmp_path):
    """Design rule 16: routed from a table, so an unhandled case says its own name.

    The alternative -- falling through to whatever builder happens to be first -- is a
    card that opens confidently onto the wrong thing, which is this panel's own history.
    """
    store = _store(tmp_path, PROGRAM)
    fam = curiosities.FAMILIES[0]
    broken = curiosities.Family(
        key=fam.key, sql=fam.sql, head=fam.head, head_one=fam.head_one,
        middle=fam.middle, tie=fam.tie, tie_one=fam.tie_one,
        whence_label=fam.whence_label, subject="a-kind-nothing-builds")
    row = dict(store.query(broken.sql, {})[0])
    with pytest.raises(KeyError, match="a-kind-nothing-builds"):
        curiosities._card(broken, row)


def test_a_node_family_with_no_node_yields_no_card(tmp_path):
    """A subject with an empty id renders, highlights, and goes nowhere (rule 30).

    Refused and counted as silent rather than shipped: an absent card is an honest
    absence, a card that does nothing is a wall painted to look like a door.
    """
    store = _store(tmp_path, PROGRAM)
    fam = next(f for f in curiosities.FAMILIES if f.subject == "node")
    row = dict(store.query(fam.sql, {})[0])
    row["node"] = ""
    assert curiosities._card(fam, row) is None


# --------------------------------------------------------------------------- #
# The prose, which is prose the moment something prints it (rule 44's companion)
# --------------------------------------------------------------------------- #

def test_a_value_of_one_is_not_reported_in_the_plural(tmp_path):
    store = _store(tmp_path, "# only one\ndef f():\n    return 1\n")
    cards = _by_key(curiosities.for_program(store))
    assert cards["comments"]["value"] == 1
    assert cards["comments"]["head"] == "1 comment on one routine", cards["comments"]["head"]


def test_a_count_is_never_printed_with_a_decimal_point(tmp_path):
    """A ratio is real and a count is not. `1,126.0 comments` and `9.0 reads` are the
    same defect in opposite directions, and both only ever get noticed by the reader."""
    store = _store(tmp_path, PROGRAM)
    for card in curiosities.for_program(store)["curiosities"]:
        if isinstance(card["value"], int):
            assert ".0" not in card["head"], card["head"]


def test_no_template_placeholder_reaches_the_reader(tmp_path):
    """A sentence with `{middle}` still in it is a template that never got formatted,
    and it renders perfectly -- which is why nothing else would catch it."""
    store = _store(tmp_path, PROGRAM)
    for card in curiosities.for_program(store)["curiosities"]:
        for field in ("head", "middle", "tie", "ratioText"):
            assert "{" not in card[field], (card["key"], field, card[field])


def test_every_family_declares_prose_for_both_numbers(tmp_path):
    """A middle sentence with no `{middle}` in it prints a number-free claim, and a head
    with no `{value}` prints the same headline for every program. Both render."""
    for fam in curiosities.FAMILIES:
        assert "{value}" in fam.head, fam.key
        assert "{middle}" in fam.middle, fam.key
        assert "{population}" in fam.middle, fam.key
        assert "{others}" in fam.tie, fam.key
        # And the singular, for `head_one`'s reason. `_card` pluralises the *noun* only, so
        # a family with one spelling says "1 other carry as many" -- the kind of thing only
        # the reader ever notices, on a panel that says twelve of them in a row.
        assert "{others}" in fam.tie_one, fam.key
        assert fam.tie_one != fam.tie, (
            f"{fam.key} spells its tie the same way for one and for many; one of the two "
            f"readings is wrong and it is always the singular")
        assert fam.subject in curiosities.SUBJECTS, fam.key
