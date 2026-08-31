"""The stack's two altitudes: every thing the program declares, and one node per file.

The fixture here is its own, and that is the point rather than convenience. `conftest`'s
sample program is a **single module**, so folding it produces one node and every claim
below would pass on code that cannot fold at all -- which is rule 64's shape exactly: a
suite whose fixtures lack the thing under test reports success about a question it never
asked.

So this one has three modules in two packages, calls that stay inside a file, calls that
cross one, a call recorded twice at two confidences, and boundaries of two kinds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import graph as G
from dunneflow.web.detail import classify, describe
from dunneflow.web.serve import build_payload, default_level, read_level

# `_a` calls its own neighbour (an inner call, counted and never drawn), `_b` twice, and
# touches two boundary kinds. `_b` calls back into `_a`, so the pair crosses in both
# directions and the plates each hold one end.
MOD_A = '''
"""Package alpha's front door."""
import os
import sqlite3

LIMIT = 10                      # WHY: the queue never holds more than this


class Ticket:
    ident: str
    tries: int


def _helper(n: int) -> int:
    return n + LIMIT


def start(n: int) -> int:
    from demo.beta.worker import run, drain
    os.environ["DEMO_MODE"]
    return run(_helper(n)) + drain(n)


def store(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO tickets (id) VALUES (?)", ("x",))
'''

MOD_B = '''
"""Package beta's worker."""
import os


RETRIES = 3


def run(n: int) -> int:
    from demo.alpha.front import _helper
    print("running")
    return _helper(n) * RETRIES


def drain(n: int) -> int:
    os.environ["DEMO_DRAIN"]
    return run(n)
'''

MOD_C = '''
"""A third file, so a package can hold more than one."""


def spare() -> int:
    return 1


def spare_two() -> int:
    return spare()
'''


@pytest.fixture(scope="module")
def levelled(tmp_path_factory):
    root = tmp_path_factory.mktemp("levelled")
    (root / "demo" / "alpha").mkdir(parents=True)
    (root / "demo" / "beta").mkdir(parents=True)
    (root / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (root / "demo" / "alpha" / "__init__.py").write_text("", encoding="utf-8")
    (root / "demo" / "beta" / "__init__.py").write_text("", encoding="utf-8")
    (root / "demo" / "alpha" / "front.py").write_text(MOD_A, encoding="utf-8")
    (root / "demo" / "beta" / "worker.py").write_text(MOD_B, encoding="utf-8")
    (root / "demo" / "beta" / "spare.py").write_text(MOD_C, encoding="utf-8")

    db = tmp_path_factory.mktemp("levelgraph") / "graph.db"
    store = Store(db)
    analyze_tree(root, store)
    resolve_calls(store)
    store.optimize()
    yield store
    store.close()


def _routine_level(store: Store) -> G.GraphModel:
    # Threshold 1 so nothing is merged: these guards are about the *fold to modules*, and
    # a plate quietly renamed `<small>` underneath them would be a second variable.
    return G.build(store, level="routine", min_disk=1)


def _module_level(store: Store) -> G.GraphModel:
    return G.build(store, level="module", min_disk=1)


# --------------------------------------------------------------------------- #
# The fold loses nothing
# --------------------------------------------------------------------------- #

def test_every_node_folds_into_exactly_one(levelled: Store) -> None:
    """The total, not the cases.

    Rule 18's lesson: the defect that cost 9,659 comments was a whole *category* nobody
    had thought to name, and the test that would have caught it counts the population and
    demands none go unclaimed. So this asserts that the folded counts add back up to the
    routine level exactly -- a kind of node the fold forgets shows up here as arithmetic
    that does not close, whatever it happens to be called.
    """
    fine = _routine_level(levelled)
    coarse = _module_level(levelled)

    assert coarse.stats["folded_from"] == len(fine.nodes)
    claimed = sum(int(n.detail["folded"]) for n in coarse.nodes)
    assert claimed == len(fine.nodes), (
        f"{len(fine.nodes)} things went in and the folded nodes account for {claimed}"
    )
    # And every folded node says what it stands for, by kind, adding to its own total.
    for n in coarse.nodes:
        holds = n.detail["holds"]
        assert sum(holds.values()) == n.detail["folded"], f"{n.id} cannot count itself"
        assert holds, f"{n.id} stands for nothing"


def test_a_module_node_is_one_file(levelled: Store) -> None:
    coarse = _module_level(levelled)
    front = next(n for n in coarse.nodes if n.id == "mod:demo.alpha.front")
    assert front.kind == "MODULE"
    assert front.label == "front"                      # the leaf, as a plate is named
    assert front.detail["module"] == "demo.alpha.front"
    assert front.detail["file"].endswith("front.py")
    assert front.disk == "pkg:alpha"
    # One routine, one class and one constant at least -- the point being that three
    # different fact kinds land on one node.
    assert set(front.detail["holds"]) >= {"ROUTINE", "STRUCTURE", "CONSTANT"}


def test_externals_fold_by_kind_onto_one_plate(levelled: Store) -> None:
    """1,920 of Mensores' 10,015 nodes are boundary targets with no module. Left alone
    they are 77% of the module picture and none of them answers the question this
    altitude asks."""
    coarse = _module_level(levelled)
    outside = [n for n in coarse.nodes if n.disk == G.OUTSIDE_DISK]
    assert outside, "nothing outside the program reached the outside plate"
    assert all(n.id.startswith("outside:") for n in outside)
    # One node per kind, never one per target.
    assert len({n.id for n in outside}) == len(outside)
    kinds = {n.id.partition(":")[2] for n in outside}
    assert {"ENV", "STDIO"} <= kinds, kinds
    # Nothing the program declares ends up out here, and nothing outside it ends up on a
    # package plate -- design rule 8's whole claim about where an external is drawn.
    assert not [n for n in coarse.nodes
                if n.id.startswith("mod:") and n.disk.startswith("ext:")]
    assert not [n for n in coarse.nodes
                if n.id.startswith("outside:") and n.disk.startswith("pkg:")]


# --------------------------------------------------------------------------- #
# The edges, counted from the store
# --------------------------------------------------------------------------- #

def _unique_calls(model: G.GraphModel) -> set[tuple[str, str]]:
    """The connections, once each. `m.edges` holds a crossing twice by design (rule 23)."""
    return {(e.src, e.dst) for e in model.edges if e.kind == "CALL"}


def test_module_calls_are_counted_from_the_store(levelled: Store) -> None:
    """Aggregating the *drawn* model would double every crossing, silently and plausibly.

    `packages.py` warned about this before anything needed the warning, so the guard
    computes the answer a second way -- straight out of `calls`, joined to the modules --
    and demands the picture match it. A number that is twice the truth still looks like a
    number.
    """
    coarse = _module_level(levelled)
    drawn = _unique_calls(coarse)

    expected = {
        (f"mod:{r['src']}", f"mod:{r['dst']}")
        for r in levelled.query(
            "SELECT src.module AS src, dst.module AS dst FROM calls c"
            " JOIN routines src ON src.id = c.caller_id"
            " JOIN routines dst ON dst.id = c.callee_id"
            " WHERE c.at_boundary = 0 AND src.module <> dst.module"
        )
    }
    assert expected, "the fixture has no cross-module calls; this guard is blind"
    assert drawn == expected


def test_a_crossing_is_drawn_on_both_plates_and_an_inner_link_once(levelled: Store) -> None:
    """Folding must not undo rule 23. Each crossing is still stored twice -- once per
    plate, each copy ending in a shadow -- because that is what lets both plates lay out
    under the same forces."""
    coarse = _module_level(levelled)
    by_disk: dict[tuple[str, str], set[str]] = {}
    for e in coarse.edges:
        if e.kind != "CALL":
            continue
        by_disk.setdefault((e.src, e.dst), set()).add(e.disk)

    home = {n.id: n.disk for n in coarse.nodes}
    for (src, dst), disks in by_disk.items():
        crosses = home[src] != home[dst]
        assert len(disks) == (2 if crosses else 1), (
            f"{src} -> {dst} is drawn on {sorted(disks)}"
        )


def test_a_module_calling_itself_is_counted_and_never_drawn(levelled: Store) -> None:
    """`_helper` is called by `start` in the same file, and `run` by `drain` in another.

    A line from a node to itself is not a connection between two things -- but a fold that
    dropped it without saying so would be design rule 1's silent filter, so the count is
    on the model and on the card.
    """
    coarse = _module_level(levelled)
    assert not [e for e in coarse.edges if e.src == e.dst], "a node was drawn calling itself"
    assert coarse.stats["edges_within_node"] > 0

    inner = int(levelled.query(
        "SELECT COUNT(*) AS n FROM calls c"
        " JOIN routines src ON src.id = c.caller_id"
        " JOIN routines dst ON dst.id = c.callee_id"
        " WHERE c.at_boundary = 0 AND src.module = dst.module"
    )[0]["n"])
    # Compared to the *grouped* row count the model folds, not to the raw calls: the
    # model reads `CALL_EDGES`, which is already one row per (caller, callee, confidence).
    grouped = int(levelled.query(
        "SELECT COUNT(*) AS n FROM ("
        "  SELECT 1 FROM calls c"
        "  JOIN routines src ON src.id = c.caller_id"
        "  JOIN routines dst ON dst.id = c.callee_id"
        "  WHERE c.at_boundary = 0 AND src.module = dst.module"
        "  GROUP BY c.caller_id, c.callee_id, c.confidence)"
    )[0]["n"])
    assert inner > 0
    assert coarse.stats["edges_within_node"] == grouped


class _OnlyCalls:
    """A store that answers `CALL_EDGES` with these rows and every other query with none.

    Routed on the query text rather than on call order, so a reordering of `_add_edges`
    cannot make this fixture answer the wrong question in silence.
    """

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def query(self, sql: str, params: object = None) -> list[dict[str, object]]:
        from dunneflow.web import queries

        return self.rows if sql == queries.CALL_EDGES else []


def test_a_folded_edge_keeps_its_strongest_confidence() -> None:
    """Design rule 5 spends the dashed edge on *we are not sure this call exists*.

    "This module calls that one" is certain the moment one of the calls under it is, so
    folding a CERTAIN and an INFERRED call into an INFERRED edge would understate a claim
    the store can prove (rule 6). Built by hand rather than fished out of the fixture,
    because the claim is about the arithmetic and not about which pair happens to have
    one of each.
    """
    model = G.GraphModel()
    model.nodes = [G.Node(id="a", label="a", kind="ROUTINE", disk="pkg:x",
                          detail={"module": "m.a", "file": "a.py"}),
                   G.Node(id="b", label="b", kind="ROUTINE", disk="pkg:x",
                          detail={"module": "m.a", "file": "a.py"}),
                   G.Node(id="c", label="c", kind="ROUTINE", disk="pkg:y",
                          detail={"module": "m.c", "file": "c.py"})]
    disk_of = {n.id: n.disk for n in model.nodes}
    fold = G._fold_to_modules(model, disk_of)

    # **Both orders**, and that is what makes it a claim about strength rather than about
    # arrival. Written with one order it passed a mutation that simply took whichever call
    # came last -- the guard being weak rather than the mutation (rule 59's companion), for
    # the fourteenth time in this file's record.
    for pair in ([("a", "INFERRED", 2), ("b", "CERTAIN", 1)],
                 [("a", "CERTAIN", 1), ("b", "INFERRED", 2)]):
        model.edges.clear()
        store = _OnlyCalls([{"src": src, "dst": "c", "confidence": conf, "weight": w}
                            for src, conf, w in pair])
        G._add_edges(store, model, disk_of, fold)        # type: ignore[arg-type]
        edges = [e for e in model.edges if e.kind == "CALL"]
        assert edges, f"the fold dropped both calls, given {pair}"
        assert {e.confidence for e in edges} == {"CERTAIN"}, pair
        assert {e.weight for e in edges} == {3}, "the folded weight is not the sum"


def test_the_weakest_alone_stays_weak() -> None:
    """The other half of the same claim, and the reason it is a second test: a fold that
    simply stamped CERTAIN on everything would pass the one above perfectly."""
    model = G.GraphModel()
    model.nodes = [G.Node(id="a", label="a", kind="ROUTINE", disk="pkg:x",
                          detail={"module": "m.a", "file": "a.py"}),
                   G.Node(id="c", label="c", kind="ROUTINE", disk="pkg:y",
                          detail={"module": "m.c", "file": "c.py"})]
    disk_of = {n.id: n.disk for n in model.nodes}
    fold = G._fold_to_modules(model, disk_of)
    store = _OnlyCalls([{"src": "a", "dst": "c", "confidence": "INFERRED", "weight": 2}])
    G._add_edges(store, model, disk_of, fold)            # type: ignore[arg-type]
    assert {e.confidence for e in model.edges if e.kind == "CALL"} == {"INFERRED"}


def test_routine_level_never_aggregates(levelled: Store) -> None:
    """The fold is what aggregates, and only the fold.

    At routine level each store row is already one edge -- `CALL_EDGES` groups by caller,
    callee *and confidence* -- so merging two rows that differ only in confidence would
    quietly change a picture nothing asked to change.
    """
    fine = _routine_level(levelled)
    home = {n.id: n.disk for n in fine.nodes}
    rows = [r for r in levelled.query(
        "SELECT caller_id AS src, callee_id AS dst FROM calls"
        " WHERE callee_id IS NOT NULL AND at_boundary = 0"
        " GROUP BY caller_id, callee_id, confidence")]
    assert rows, "the fixture resolved no calls; this guard is blind"
    # Every row is drawn: once inside a plate, twice across one (rule 23). The two counts
    # are the same number arrived at from the store and from the model.
    expected = sum(2 if home.get(str(r["src"])) != home.get(str(r["dst"])) else 1
                   for r in rows if str(r["src"]) in home and str(r["dst"]) in home)
    assert len([e for e in fine.edges if e.kind == "CALL"]) == expected


# --------------------------------------------------------------------------- #
# The threshold is the reader's
# --------------------------------------------------------------------------- #

def test_each_level_carries_its_own_default_threshold(levelled: Store) -> None:
    """8 is right for routines and wrong for modules: applied at module level on Mensores
    it folds 21 of the 45 packages away, because a package with six modules is a real
    package while a package with six routines is not much of a plate.

    Asserted on `build` rather than only on `read_level`, and that is the whole of it --
    every other guard here passes an explicit threshold, so a `build` that reached for the
    routine default whatever it was asked survived a mutation until this existed.
    """
    assert G.MIN_DISK_BY_LEVEL["module"] != G.MIN_DISK_BY_LEVEL["routine"], (
        "the two defaults are equal, so nothing below can tell them apart"
    )
    for level in G.LEVELS:
        assert G.build(levelled, level=level).stats["min_disk"] == \
            G.MIN_DISK_BY_LEVEL[level]


def test_the_threshold_moves_plates_and_states_what_it_merged(levelled: Store) -> None:
    loose = G.build(levelled, level="module", min_disk=1)
    tight = G.build(levelled, level="module", min_disk=64)

    assert loose.stats["disks_merged"] == 0
    assert loose.stats["disks_merged_nodes"] == 0
    assert tight.stats["disks_merged"] > loose.stats["disks_merged"]
    assert tight.stats["disks"] < loose.stats["disks"]
    # Rule 32: the number names what it measures. `disks_merged` counts plates and
    # `disks_merged_nodes` counts nodes, and the second is walked from the nodes that
    # actually moved rather than inferred from the first.
    moved = len([n for n in tight.nodes if "home" in n.detail])
    assert tight.stats["disks_merged_nodes"] == moved
    # Nothing is lost by merging -- it is a plate that goes, never a node.
    assert len(tight.nodes) == len(loose.nodes)


def test_a_merged_plate_stays_in_its_own_band(levelled: Store) -> None:
    """Everything used to land on `pkg:<small>`, which is a *package* plate -- so on
    Mensores the four QUEUE targets, the unnamed QUEUE touch and the one LLM_API endpoint
    have been drawn among the code that reaches them for as long as `<small>` has existed.

    Nothing could see it, because a merged plate is supposed to hold things from
    elsewhere. Design rule 8 says an external is a first-class node *at the boundary*.
    """
    tight = G.build(levelled, level="routine", min_disk=64)
    for n in tight.nodes:
        home = n.detail.get("home")
        if home is None:
            continue
        assert n.disk.partition(":")[0] == str(home).partition(":")[0], (
            f"{n.id} moved from {home} to {n.disk}, across the boundary line"
        )
    # And the two carry different names, or the legend states one word for two plates.
    names = [d["name"] for d in tight.disks]
    assert len(names) == len(set(names)), f"two plates share a name: {names}"


# --------------------------------------------------------------------------- #
# What the server will and will not answer
# --------------------------------------------------------------------------- #

def test_an_unknown_level_is_refused_rather_than_defaulted() -> None:
    """A silent fallback would answer a question nobody asked with a picture that looks
    exactly right -- design rule 16's dead control, in a query string."""
    with pytest.raises(ValueError, match="unknown level"):
        read_level({"level": ["package"]})
    with pytest.raises(ValueError, match="whole number"):
        read_level({"level": ["module"], "minDisk": ["lots"]})


def test_the_threshold_is_clamped_and_the_default_is_per_level() -> None:
    assert read_level({}) == default_level()
    assert read_level({"level": ["module"]}) == ("module", G.MIN_DISK_BY_LEVEL["module"])
    assert read_level({"level": ["module"], "minDisk": ["999"]})[1] == G.MIN_DISK_CEILING
    assert read_level({"level": ["module"], "minDisk": ["-4"]})[1] == G.MIN_DISK_FLOOR


def test_the_payload_names_the_level_it_is(levelled: Store) -> None:
    """The page holds one payload per level and has to be able to ask what it is holding
    rather than remember what it asked for -- rule 67's shape: a control naming one thing
    while the picture draws another."""
    for level in G.LEVELS:
        payload = build_payload(levelled, "demo", level=level, min_disk=1)
        assert payload["level"] == level
        assert payload["stats"]["min_disk"] == 1
        assert payload["program"] == "demo"
        assert len(payload["nodes"]["id"]) == payload["stats"]["nodes"] + \
            payload["stats"]["shadows"]


# --------------------------------------------------------------------------- #
# The card and the picture
# --------------------------------------------------------------------------- #

def test_an_id_says_what_it_is(levelled: Store) -> None:
    assert classify("mod:demo.alpha.front") == ("MODULE", {"module": "demo.alpha.front"})
    assert classify("outside:STDIO") == ("OUTSIDE", {"kind": "STDIO"})
    # And the prefixes that were already here still resolve to what they always did.
    assert classify("bnd:ENV:DEMO_MODE")[0] == "BOUNDARY"
    assert classify("art:x.md")[0] == "ARTEFACT"
    assert classify("const:m.LIMIT")[0] == "CONSTANT"


def test_the_module_card_agrees_with_the_picture(levelled: Store) -> None:
    """Rule 13 over two answers to one question. The inspector counts neighbours from
    `calls` joined to `routines`; the stack draws them from the fold. If the two disagree,
    a reader clicking a node is told something the picture does not show."""
    coarse = _module_level(levelled)
    drawn = _unique_calls(coarse)
    checked = 0
    for node in [n for n in coarse.nodes if n.id.startswith("mod:")]:
        card = describe(levelled, node.id)
        assert card["found"], node.id
        card_in = {f"mod:{r['module']}" for r in card["in"]["callers"]}
        card_out = {f"mod:{r['module']}" for r in card["out"]["calls"]}
        assert card_in == {a for a, b in drawn if b == node.id}, node.id
        assert card_out == {b for a, b in drawn if a == node.id}, node.id
        # What the node stands for is the same number in both places.
        assert card["identity"]["folded"] == node.detail["folded"], node.id
        assert card["identity"]["holds"] == node.detail["holds"], node.id
        checked += 1
    assert checked >= 3, f"only {checked} modules; this guard is barely looking"


def test_the_outside_card_counts_the_kind_and_not_one_endpoint(levelled: Store) -> None:
    """`bnd:` answers for one endpoint. This node stands for every endpoint of its kind,
    so borrowing that card would state one target's callers over all of them (rule 32)."""
    coarse = _module_level(levelled)
    env = next(n for n in coarse.nodes if n.id == "outside:ENV")
    card = describe(levelled, "outside:ENV")
    assert card["found"] and card["kind"] == "BOUNDARY"
    assert card["identity"]["source_status"] == "OPAQUE"
    assert card["identity"]["folded"] == env.detail["folded"]
    assert len(card["holds"]["targets"]) == card["identity"]["folded"]
    assert card["identity"]["hits"] >= card["identity"]["folded"]


def test_an_id_the_store_never_heard_of_is_not_found(levelled: Store) -> None:
    """`found: false` and an empty shape are different claims, and only one of them means
    the map is wrong."""
    assert describe(levelled, "mod:demo.nowhere")["found"] is False
    assert describe(levelled, "outside:TELEPATHY")["found"] is False


def test_the_sample_program_still_builds_at_both_levels(analyzed: Store) -> None:
    """A one-module program folds to one node, and that is the right answer rather than
    an edge case: the guards above use their own fixture precisely because this one cannot
    tell a working fold from a broken one."""
    for level in G.LEVELS:
        model = G.build(analyzed, level=level)
        assert model.level == level
        assert model.nodes


def test_the_level_names_are_the_only_ones_that_exist(levelled: Store) -> None:
    """Routed from the table, so a third level added later cannot be half-wired: the
    thresholds and the names are the same list or this fails (rule 36)."""
    assert set(G.LEVELS) == set(G.MIN_DISK_BY_LEVEL)
    assert default_level()[0] in G.LEVELS
    with pytest.raises(ValueError, match="unknown level"):
        G.build(levelled, level="galaxy")


def test_the_docs_name_the_source_of_truth() -> None:
    """`layout.py` says every disk is drawn the same size. That note is still true and
    still load-bearing -- the plate-sizing request reverses it, and when it does the
    comment must move with the code rather than stand contradicting it."""
    text = Path(__file__).resolve().parents[1].joinpath(
        "src/dunneflow/web/layout.py").read_text(encoding="utf-8")
    assert "Disks are drawn the same size" in text
