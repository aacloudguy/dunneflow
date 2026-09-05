"""A plate of the stack, described as the thing it is.

**The defect, found by Tom on 2026-09-05 and verified pre-existing rather than
introduced.** Clicking a package in the navigator marked the row `aria-current="true"` and
switched the pane, then left the crumb at *"nothing selected"*, the table at all 4,786
rows, and the inspector saying *"Pick a way in from the cover, **a package from the
navigator**, or a node in the graph"* -- naming the gesture that had just failed. One
cause, three symptoms: `pkg` routed to `selectFromNav({ disks: … })`, which sets
`wanted.disks` and no subject at all.

What it decides is what selecting a package *is*. A plate is not a node (rule 30), and
nominating a member of it is the defect `detail.fold` exists to undo (rules 32 and 74) --
so a plate is a subject of its own kind, answered by `web/plate.py`.

Every guard here was run against a half-working version as well as against nothing, per
rule 37.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dunneflow.store import Store
from dunneflow.web import plate
from dunneflow.web.graph import MIN_DISK_BY_LEVEL, OUTSIDE_DISK, SMALL_DISK
from dunneflow.web.serve import build_payload


@pytest.fixture(scope="module")
def payload(analyzed: Store) -> dict[str, Any]:
    """The stack at the altitude a session opens at, which is what a click selects from."""
    return build_payload(analyzed, "demo", *(("routine", MIN_DISK_BY_LEVEL["routine"])))


@pytest.fixture(scope="module")
def merged(analyzed: Store) -> dict[str, Any]:
    """The same stack with everything merged, so the `<small>` plates are populated.

    `min_disk=64` is the ceiling `read_level` clamps to, and a threshold high enough to
    merge everything is stated in `graph.py` as a legitimate thing to want to see. Here it
    is how the fold-shaped plates get an input at all: the sample tree is small enough that
    the default threshold leaves them empty, and an empty fold cannot exercise the branch
    that says what a fold stands for.
    """
    return build_payload(analyzed, "demo", level="routine", min_disk=64)


def _first_package(payload: dict[str, Any]) -> str:
    ids = [str(d["id"]) for d in payload["disks"]
           if str(d["id"]).startswith("pkg:") and str(d["id"]) not in SMALL_DISK.values()]
    assert ids, "no package plate in this stack; every guard below would be vacuous"
    return ids[0]


# ----------------------------------------------------------- what it answers --- #

def test_a_plate_answers_as_a_plate_and_not_as_a_node(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """`kind` is PLATE, for `detail.fold`'s reason.

    Calling it a ROUTINE would put the wrong word in the inspector's head and the wrong
    answer in every check that reads it -- and the inspector routes on exactly this field,
    so the whole fix rests on it being a kind of its own (rule 30).
    """
    got = plate.describe(analyzed, payload, _first_package(payload))
    assert got["found"] is True
    assert got["kind"] == "PLATE", (
        "a plate reports as some other kind, so the inspector will answer about it in a "
        "shape built for something else -- which is the defect this replaces"
    )
    assert got["identity"]["tag"] == "PACKAGE"


def test_a_plate_that_is_not_at_this_level_says_so_rather_than_looking_empty(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """`(no rows)` is indistinguishable from a true empty answer -- the tool's own rule.

    A plate that exists at one altitude may be merged away at another, so this is a real
    state a reader can reach by changing the Detail control with a package selected, not a
    defensive branch nobody hits.
    """
    got = plate.describe(analyzed, payload, "pkg:nothing.of.the.sort")
    assert got["found"] is False
    assert "no such plate" in got["reason"]
    assert "altitude" in got["reason"], (
        "the refusal does not say why a plate can be missing, which is the half a reader "
        "can act on"
    )


def test_what_a_plate_holds_agrees_with_what_the_model_says_it_holds(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """Rule 13: a claim's query must return exactly what is printed beside it.

    Two readings of one fact travel in this payload -- `identity.nodes`, which the model
    counted while summarising the disks, and `holds`, counted here from the arrays. They
    are printed together, so they have to agree; a comment hoping they do is not a check.

    Every plate, not a sample. The two counts could agree on the ordinary ones and part
    company on exactly the plates that are folds, which is where the counting differs.
    """
    for row in payload["disks"]:
        got = plate.describe(analyzed, payload, str(row["id"]))
        assert got["found"] is True, f"the model lists {row['id']} and this cannot open it"
        assert sum(got["holds"].values()) == got["identity"]["nodes"], (
            f"{row['id']}: the pane counts {sum(got['holds'].values())} nodes and the "
            f"model's own summary says {got['identity']['nodes']}"
        )


def test_a_shadow_is_never_counted_as_a_member(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """Rule 31, from the side it is not usually quoted on.

    A shadow sits on this plate and belongs to another. Counting one would report a plate
    as holding what it borrows -- and worse, asking the store about its id would attribute
    another plate's calls to this one, which is a wrong number that looks like a right one.

    The model's `nodes` count is real nodes only and its `shadows` count is separate, so
    the check is that the pane never lands between them. Asserted where there *are*
    shadows, because a stack with none proves nothing.
    """
    shadowed = [d for d in payload["disks"] if int(d["shadows"] or 0) > 0]
    assert shadowed, "no plate in this stack borrows anything; this guard is blind"
    for row in shadowed:
        got = plate.describe(analyzed, payload, str(row["id"]))
        held = sum(got["holds"].values())
        assert held == int(row["nodes"]), (
            f"{row['id']} counts {held} where the model says {row['nodes']} real nodes "
            f"and {row['shadows']} shadows -- a borrowed node has been counted as held"
        )


# ------------------------------------------------------------- the neighbours --- #

def test_a_package_does_not_report_itself_as_its_own_neighbour(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """Internal traffic is not a package calling a package.

    `FOLD_CALLS_IN`/`OUT` already exclude the id set, which is why they are reused rather
    than reimplemented -- but the far end is then mapped to *its* plate, and two different
    packages can be merged onto one `<small>`. So the plate itself is excluded again after
    the mapping, and this is the check that it is.
    """
    for row in payload["disks"]:
        pid = str(row["id"])
        got = plate.describe(analyzed, payload, pid)
        for side in ("in", "out"):
            assert all(n["plate"] != pid for n in got[side]), (
                f"{pid} lists itself under `{side}`, so its internal calls are being "
                f"reported as traffic with another plate"
            )


def test_a_far_end_on_no_plate_is_counted_rather_than_dropped(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """Design rule 1: no filter is ever silent.

    A call whose far end is on no plate is a real thing -- `_add_edges` counts and drops
    the same case when placing edges -- and a row that vanished is worse than a row that
    says it could not be placed. It carries no plate id, because there is nothing to
    select; the guard is that when it appears it appears as its own row and is marked.
    """
    unplaced = [n for row in payload["disks"]
                for side in ("in", "out")
                for n in plate.describe(analyzed, payload, str(row["id"]))[side]
                if n.get("unplaced")]
    for n in unplaced:
        assert n["plate"] == "", (
            "an unplaced row carries a plate id, so the inspector will offer a selection "
            "that resolves to nothing"
        )
        assert n["weight"] > 0, "an unplaced row with no weight is a row about nothing"
        assert "not on any plate" in n["name"]


def test_the_neighbours_are_counted_from_the_store_and_not_from_the_drawn_edges() -> None:
    """Rule 23, asserted over the source because the wrong answer is plausible.

    The 2.5D model stores every crossing twice, once per plate, each copy ending in a
    shadow. Aggregating `payload["edges"]` here would double every weight -- silently, and
    the numbers would still look like numbers. `packages.py` wrote that warning down before
    anything needed it and this is the second reader that has to obey it.

    A source check rather than a value check, deliberately: a doubled weight is only
    detectable against a separately-computed truth, and computing one here would be a third
    answer to the same question.
    """
    src = Path(plate.__file__ or "").read_text(encoding="utf-8")
    body = src.split("def _neighbours(", 1)[1].split("\ndef ", 1)[0]
    assert 'payload.get("edges")' not in body and '["edges"]' not in body, (
        "`_neighbours` reads the drawn edges, which hold each crossing twice (rule 23) -- "
        "every weight it reports is doubled"
    )
    assert "store.query(sql" in body, "it no longer asks the store at all"


# ------------------------------------------------------------------- the folds --- #

def test_a_fold_says_what_it_stands_for_and_is_never_one_of_them(
        analyzed: Store, merged: dict[str, Any]) -> None:
    """Rule 74, and it is what makes `<small>` readable at all.

    A merged plate is not a package -- it is the place packages too small to draw were put
    -- so the honest answer is the list of what it stands for, each of which is a plate
    the reader could have had at a lower threshold. `identity.merged` says which kind of
    plate this is rather than leaving it to be inferred from a non-empty list, because
    "this is a fold that merged nothing" and "this is not a fold" are different facts
    that look identical on the wire (rule 30).
    """
    folds = [str(d["id"]) for d in merged["disks"] if str(d["id"]) in SMALL_DISK.values()]
    assert folds, "nothing merged even at the ceiling; this guard is blind"

    for pid in folds:
        got = plate.describe(analyzed, merged, pid)
        assert got["identity"]["merged"] is True, f"{pid} does not know it is a fold"
        assert got["stands_for"], f"{pid} stands for nothing, yet things were merged into it"
        assert all(h["plate"] != pid for h in got["stands_for"]), (
            f"{pid} lists itself among the plates it stands for (rule 74)"
        )
        assert sum(h["nodes"] for h in got["stands_for"]) == sum(got["holds"].values()), (
            f"{pid} stands for a different number of nodes than it holds"
        )


def test_an_ordinary_plate_is_not_marked_as_a_fold(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """The other half, and without it the flag above is satisfied by a constant `True`."""
    pid = _first_package(payload)
    got = plate.describe(analyzed, payload, pid)
    assert got["identity"]["merged"] is False
    assert got["stands_for"] == [], (
        "an ordinary package claims to stand for other plates, so the pane will say it "
        "is a fold of itself"
    )


def test_the_merged_plate_ids_are_read_from_graph_and_not_spelled_again() -> None:
    """Rule 51 as a value check rather than as an intention.

    `graph.SMALL_DISK` is what the fold writes. A second list here would agree with it
    until the day one of them was edited, and the failure would be a `<small>` plate that
    silently stops saying what it stands for -- which looks exactly like a plate that
    merged nothing.
    """
    assert frozenset(SMALL_DISK.values()) == plate.MERGED_PLATES
    assert OUTSIDE_DISK not in plate.MERGED_PLATES, (
        "the module-level outside plate is being treated as a fold of small plates; it is "
        "a fold of boundary *kinds*, which is a different thing with a different sentence"
    )


# -------------------------------------------------------------- the ways in --- #

def test_a_command_tree_contributes_its_root_and_not_its_subcommands(
        analyzed: Store, payload: dict[str, Any]) -> None:
    """A plate is where a reader starts, so it names the executables and not the 107.

    `packages.py` ranks its columns outward from the packages that hold a way in, which is
    the same claim one surface over. Listing every subcommand under a plate would bury the
    executables that are the actual answer, and each way in has its own pane that lists
    what it holds (rule 74).
    """
    seen = [w for row in payload["disks"]
            for w in plate.describe(analyzed, payload, str(row["id"]))["ways_in"]]
    assert all(w.get("grp") is not None for w in seen), "a way in row lost its group"
    # The query selects `parent_id IS NULL`; nothing here should carry a parent.
    assert all("parent_id" not in w for w in seen), (
        "a subcommand reached the plate pane, so a tree is being listed as its members"
    )
