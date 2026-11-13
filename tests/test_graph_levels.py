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

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import graph as G
from dunneflow.web import plateorder
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
    """1,920 of Lictores' 10,015 nodes are boundary targets with no module. Left alone
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
    """8 is right for routines and wrong for modules: applied at module level on Lictores
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
    Lictores the four QUEUE targets, the unnamed QUEUE touch and the one LLM_API endpoint
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
    """`layout.py` used to say every disk is drawn the same size. The plate-sizing work
    reversed that, and this guard reversed with it -- which is the whole reason it was
    written in that form: a comment left standing beside code that contradicts it is worse
    than no comment, because it is the one a reader believes.

    Two halves, and the second is the one that decays. The old claim must be **gone**, or
    the module states both answers; and the note must **name where the sizing now happens**,
    because `DISK_RADIUS` is still computed here and a reader who finds it will otherwise
    conclude this file decides how wide a plate is. It does not -- the renderer does, from
    an unscaled base, because plate width is a view property like Z and the spreads.
    """
    root = Path(__file__).resolve().parents[1]
    text = root.joinpath("src/dunneflow/web/layout.py").read_text(encoding="utf-8")
    assert "Disks are drawn the same size" not in text, (
        "layout.py still claims every disk is one width, and the renderer no longer draws "
        "them that way -- the comment has to move with the code"
    )
    for cited in ("applyLayout", "graph.js", "plateSize"):
        assert cited in text, (
            f"layout.py does not name {cited!r}, so the note leaves a reader at "
            "DISK_RADIUS believing this file decides how wide a plate is drawn"
        )
    # And the thing named must exist, or this is a signpost to nothing (rule 17's converse).
    engine = root.joinpath("src/dunneflow/web/static/graph.js").read_text(encoding="utf-8")
    assert "function applyLayout(" in engine and "opts.plateSize" in engine


# --------------------------------------------------------------------------- #
# The root package, and the two ways of pointing at one program
#
# Found by Tom reading a map, not by any test here. `root_package` used to return the
# *modal* first segment and could not fail: analyse a directory that already **is** a
# package and every module is one segment shallower, so the biggest subpackage wins the
# vote and `package_expr` labels every other module's routines external. On DunneFlow's
# own tree that was **750 of 752 routines drawn as somebody else's code**, on the largest
# plate in the picture, over a map whose cover counts were all correct.
#
# Rule 49: a fallback that yields a plausible value has hidden the failure it was written
# for. The two fixtures below are the same program pointed at two ways, and the whole
# guard is that they answer the same.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def as_package(tmp_path_factory):
    """The same tree, analysed at the package itself rather than at its parent."""
    root = tmp_path_factory.mktemp("aspackage")
    (root / "alpha").mkdir(parents=True)
    (root / "beta").mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "alpha" / "__init__.py").write_text("", encoding="utf-8")
    (root / "beta" / "__init__.py").write_text("", encoding="utf-8")
    (root / "alpha" / "front.py").write_text(MOD_A, encoding="utf-8")
    (root / "beta" / "worker.py").write_text(MOD_B, encoding="utf-8")
    (root / "beta" / "spare.py").write_text(MOD_C, encoding="utf-8")

    db = tmp_path_factory.mktemp("aspackagegraph") / "graph.db"
    store = Store(db)
    analyze_tree(root, store)
    resolve_calls(store)
    store.optimize()
    yield store
    store.close()


def _packages(store: Store) -> set[str]:
    from dunneflow.web import queries
    params = G.pkg_params(G.root_package(store))
    return {str(r["pkg"]) for r in store.query(queries.ROUTINE_NODES, params)}


def test_a_tree_with_one_package_names_it_as_the_root(levelled: Store) -> None:
    assert G.root_package(levelled) == "demo"


def test_analysing_the_package_itself_finds_no_root_rather_than_a_wrong_one(
        as_package: Store) -> None:
    """`""` is the answer, and the modal segment is the defect.

    `beta` holds two of the three files here, exactly as `web` held twenty of DunneFlow's
    sixty-three. A vote with no coverage test elects it and calls the rest of the program
    external.
    """
    assert G.root_package(as_package) == ""


def test_both_ways_of_pointing_at_one_program_group_it_the_same(
        levelled: Store, as_package: Store) -> None:
    """The guard that would have caught it, and the reason the fix is the right one."""
    from_parent = _packages(levelled) - {"<root>"}
    from_package = _packages(as_package) - {"<root>"}
    assert from_parent == from_package == {"alpha", "beta"}


def test_no_routine_of_the_program_is_ever_called_external(
        levelled: Store, as_package: Store) -> None:
    """`routines` holds what was extracted from this program's own files and nothing else.

    The branch fired **0 of 4,786** times on Lictores and 750 of 752 on a map with a wrong
    root -- it never described a fact, only a misreading (rules 26 and 30). It is
    unreachable by construction now, and this is what says so.
    """
    for store in (levelled, as_package):
        assert "<outside the root>" not in _packages(store)
        assert "<external>" not in _packages(store)


def test_every_navigator_package_row_selects_a_plate_that_exists(
        levelled: Store, as_package: Store) -> None:
    """The navigator selects **by plate id**, so a row with no plate selects nothing.

    `COVER_PACKAGES` fills that group and used to take the second dotted segment on its own,
    without knowing the program root -- a second definition of "package" that `PACKAGE_SIZES`
    named as a hazard in a comment and nobody had clicked. Analysed at the parent the two
    agree except for the root module itself (Lictores: **1 dead row of 46**); analysed at the
    package the second segment is a *module* (**36 dead of 48**), which is a navigator whose
    Packages group answers "Nothing to show." three times in four.

    Both queries go through one expression now, so this holds by construction — which is what
    makes it worth asserting rather than hoping.
    """
    from dunneflow.web import queries
    for store in (levelled, as_package):
        params = G.pkg_params(G.root_package(store))
        rows = {str(r["pkg"]) for r in store.query(queries.COVER_PACKAGES, params)}
        plates = {str(r["pkg"]) for r in store.query(queries.PACKAGE_SIZES, params)}
        assert rows, "the navigator's package group is empty"
        assert rows == plates, f"rows selecting nothing: {sorted(rows - plates)}"


# --------------------------------------------------------------------------- #
# A shadow never reaches a hover, so no card may claim it did
# --------------------------------------------------------------------------- #


def test_no_hover_can_carry_a_shadow_and_no_card_claims_one() -> None:
    """Rules 23 and 31 close both paths into `onHover`, so the flag they fed is gone.

    The card drew *"A stand-in. This routine lives on X"* when `h.shadow` was true, and
    nothing could ever set it. `prepare` gives a shadow `radii[i] = 0` and alpha 0, so
    picking never returns one -- measured 2026-09-08 at 1,989 picks over 562 distinct nodes
    across the whole drawn stack, none a shadow, against 5,855 shadows in the payload. The
    only other way an index reaches that handler is the rim arrow, and `pointerData` builds
    every mark through `realIndex` under a comment citing these same two rules. The
    reticule drawn over the top is `pickable: false`, so there was no third path.

    Design rule 16 from the far side: a control wired to a condition that can no longer
    arise looks exactly like one that works, and only looking found it. This guard is what
    stops the flag coming back without the drawing that would justify it -- if a level or
    layout ever draws a shadow, this test is the place that says so.
    """
    root = Path(__file__).resolve().parents[1]
    engine = root.joinpath("src/dunneflow/web/static/graph.js").read_text(encoding="utf-8")
    shell = root.joinpath("src/dunneflow/web/static/shell.js").read_text(encoding="utf-8")

    # The two facts the argument rests on, asserted against the source rather than recalled.
    assert "d.radii[i] = 0;" in engine, (
        "a shadow is no longer drawn at radius zero, so it may now be pickable -- the "
        "hover payload's shadow flag was withdrawn on the claim that it cannot be"
    )
    assert "index: i, at, pos:" in engine, (
        "pointerData no longer carries a resolved index, so the rim arrow may now hand "
        "onHover a shadow"
    )
    assert "pickable: false," in engine, "the reticule is pickable again, which is a third path"

    # And so nothing may emit or read the flag those two facts made unreachable.
    assert "shadow: raw2.shadow[i]" not in engine, (
        "the hover payload carries a shadow flag again; nothing can set it true, so a card "
        "reading it is a control wired to a condition that cannot arise"
    )
    # `${h.shadow` and not `h.shadow`: the note left where the row was names the field it
    # is about, and a guard that cannot tell a mention from a use is rule 37's own defect.
    assert "${h.shadow" not in shell, (
        "the hover card reads h.shadow again, and the engine does not send it"
    )
    assert "A stand-in." not in shell.split("*/")[0] + "".join(
        seg.split("/*")[0] for seg in shell.split("*/")[1:]
    ), "the stand-in row is back in the rendered card rather than in the note about it"


# --------------------------------------------------------------------------- #
# The plate order that keeps crossings short
# --------------------------------------------------------------------------- #


def test_a_crossing_is_counted_once_not_once_per_plate(levelled: Store) -> None:
    """Rule 23's doubling, in the one place a crossing is counted.

    The model holds every cross-plate connection **twice** -- once on each plate, each copy
    ending in a shadow -- because that is what lets both plates lay out under the same
    forces. Counting rows would say every pair is twice as coupled as it is. The doubling
    is uniform, so it changes no ordering and every number printed beside the order (rule
    32); a defect that moves nothing and makes everything wrong is exactly the kind this
    codebase keeps paying for.
    """
    m = _routine_level(levelled)
    w = plateorder.weights(m)
    disk_of = {n.id: n.disk for n in m.nodes}
    rows = sum(1 for e in m.edges
               if disk_of.get(e.src) and disk_of.get(e.dst)
               and disk_of[e.src] != disk_of[e.dst])
    assert sum(w.values()) > 0, "this fixture draws no cross-plate edges; the guard is blind"
    assert sum(w.values()) * 2 == rows, (
        f"{sum(w.values())} counted against {rows} rows -- a crossing is either being "
        "counted once per plate or the model has stopped doubling them"
    )
    # And never a plate against itself: an inner edge costs no vertical distance under any
    # order, so including it would add a constant to every candidate and say nothing.
    assert all(a != b for a, b in w), "a plate is paired with itself"


def test_the_order_is_the_same_on_every_run(levelled: Store) -> None:
    """Rule 66: an order the tool cannot defend is not an order.

    Minimum linear arrangement is NP-hard and this is a local search, so the answer is not
    claimed to be optimal -- it is claimed to be *the same one every time*, seeded from a
    stated order and taking the first strict improvement in a fixed traversal. Without that
    two runs of one build draw two stacks and neither can be compared with the other.
    """
    m = _routine_level(levelled)
    runs = {tuple(plateorder.solve(m)) for _ in range(3)}
    assert len(runs) == 1, "the solve is not deterministic"
    grouped = {tuple(plateorder.solve(m, grouped=True)) for _ in range(3)}
    assert len(grouped) == 1, "the grouped solve is not deterministic"


def test_the_order_holds_every_plate_and_invents_none(levelled: Store) -> None:
    """A plate dropped here is a plate `sortedDisks` silently filters out of the legend."""
    m = _routine_level(levelled)
    seed = plateorder.seed_order(m)
    for grouped in (False, True):
        got = plateorder.solve(m, grouped=grouped)
        assert sorted(got) == sorted(seed), (
            f"grouped={grouped}: the order is not a permutation of the plates")
        assert len(set(got)) == len(got), f"grouped={grouped}: a plate appears twice"


def test_grouped_never_puts_an_external_above_a_package(levelled: Store) -> None:
    """The whole of what `grouped` promises, and the only thing it may cost is travel."""
    m = _routine_level(levelled)
    kind = {str(d["id"]): d.get("kind") for d in m.disks}
    got = [kind.get(d) for d in plateorder.solve(m, grouped=True)]
    assert "package" in got and "external" in got, (
        "this fixture has only one kind of plate; the guard cannot see what it checks")
    first_ext = got.index("external")
    assert "package" not in got[first_ext:], (
        "grouped put a package below an external, which is the one thing it exists to hold")


def test_the_solve_never_makes_the_crossings_longer(levelled: Store) -> None:
    """It is a search that keeps only improvements, so this is a floor rather than a hope.

    Stated as *not worse* rather than as a percentage: the reduction on a three-module
    fixture is not the reduction on a program, and a test asserting Comitia's 82.8% here
    would be measuring the fixture and naming the feature (rule 24).
    """
    m = _routine_level(levelled)
    w = plateorder.weights(m)
    seed = plateorder.seed_order(m)
    for grouped in (False, True):
        got = plateorder.solve(m, grouped=grouped)
        assert plateorder.travel(got, w) <= plateorder.travel(seed, w), (
            f"grouped={grouped}: the search returned an order worse than its seed")


def test_the_spread_bands_add_up_to_the_crossings_they_are_drawn_from(
        levelled: Store) -> None:
    """Rule 32: the bands on screen are shares of a denominator, so they must be all of it.

    The bands are a partition by construction -- 1, 2-3, 4-8, 9-20, 21+ covers every
    distance a crossing can have -- and this is what catches a band edited into a gap.
    """
    m = _routine_level(levelled)
    w = plateorder.weights(m)
    got = plateorder.spread(plateorder.solve(m), w)
    assert sum(n for _, n in got.bands) == got.crossings, (
        f"the bands hold {sum(n for _, n in got.bands)} of {got.crossings} crossings")
    assert got.crossings == sum(w.values()), "the denominator is not the crossings counted"


def test_the_answer_states_both_ends_and_the_saving_between_them(levelled: Store) -> None:
    """A figure with no middle is a claim nobody can weigh -- `curiosities.py`'s rule."""
    m = _routine_level(levelled)
    got = plateorder.answer(m)
    for key in ("order", "grouped", "plates", "pairs", "before", "after", "saved"):
        assert key in got, f"the answer does not carry {key!r}"
    assert got["before"]["crossings"] == got["after"]["crossings"], (
        "the two ends are being measured over different sets of crossings")
    assert got["after"]["total"] <= got["before"]["total"]


def test_the_plate_order_route_reads_the_level_the_same_way_the_stack_does() -> None:
    """One reading of *which altitude*, not two that can drift (rule 51).

    An order names plates and `minDisk` decides which plates exist, so an order fetched at
    one threshold names plates the other has merged into `<small>` -- and `sortedDisks`
    filters those out silently, drawing a short list that reads as a small program (rule
    81). The route therefore keys its cache on exactly what `read_level` returns, plus
    `grouped`, which is a different question rather than a different rendering of one
    answer.

    Read off the source because the alternative is standing a server up to assert a
    dictionary key. What is asserted is the *shape of the key*, which is where rule 81 is
    paid or not.
    """
    src = Path(__file__).resolve().parents[1] / "src/dunneflow/web/serve.py"
    text = src.read_text(encoding="utf-8")
    route = re.search(r"def _r_plateorder\(self.*?\n    def ", text, re.S)
    assert route, "the plate-order route is gone or no longer shaped for this guard"
    body = route.group(0)
    assert "read_level(q)" in body, (
        "the route reads the level its own way; `/api/graph` and this must agree or an "
        "order arrives for an altitude nobody is looking at"
    )
    assert "self.send_error(400" in body, (
        "an unknown level is defaulted rather than refused -- a silent fallback answers a "
        "question nobody asked with a picture that looks exactly right"
    )
    assert re.search(r"key = \(level, min_disk, grouped\)", body), (
        "the cache key does not carry the level, the threshold and the grouping, so one "
        "answer is served for questions with different plate sets (rule 81)"
    )


def test_a_base_holds_its_plate_orders_and_a_switch_cannot_carry_them() -> None:
    """A fact about *this version*, so a frozen record swapped whole throws it away.

    Stated here as well as in `test_base_switch`, because that guard derives its field list
    from the dataclass and would pass just as happily on a field cached in the wrong place.
    This one says *which* place is right and why: `payloads` is the precedent, an order is
    the same kind of thing, and naming it in `PROGRAM_CACHES` as well would be a second
    answer to "when does this go stale" that can drift from the first.
    """
    from dunneflow.web import serve as serve_mod
    fields = serve_mod._Base.__dataclass_fields__
    assert "plate_orders" in fields, "the base no longer holds the plate orders"
    assert "plate_orders" not in serve_mod._Live.PROGRAM_CACHES, (
        "the plate orders are named as a cache to clear as well as being a base field; "
        "one of the two answers will be forgotten when the other moves"
    )
    assert "plate_orders" not in serve_mod._Live.COMPARISON_CACHES


# --------------------------------------------------------------------------- #
# Snap-to-fit, and the floor under it


def _js_engine():
    """Whatever this machine has, or nothing. DunneFlow ships with no Node, ever."""
    engine = next((c for c in ("node", "deno", "bun") if shutil.which(c)), None)
    if engine is None:
        jsc = Path("/System/Library/Frameworks/JavaScriptCore.framework"
                   "/Versions/A/Helpers/jsc")
        engine = str(jsc) if jsc.exists() else None
    return engine


def test_a_fit_on_one_node_still_shows_half_its_plate() -> None:
    """**Snap-to-fit framed a single node as a sphere filling the pane.**

    `bounds` ends `radius: r || 1`, and a selected node with no neighbours to spread it has
    `r === 0` -- so the fit framed a box **two world units** across and drew one magnified
    dot. Reported by Tom: *"you can't tell what you're seeing until you zoom out, then you
    can see giant node spheres."* Measured on Comitia's map before the fix: 3 world units
    visible against a plate 669 across.

    That `|| 1` is rule 49 in one character: *this has no extent* is not a size, and
    substituting a plausible one hides the failure rather than deferring it.

    **The arithmetic is taken from the file, not restated here.** A copy of `fitView`'s
    formula in this test would agree with a broken implementation, which is the failure it
    exists to catch (rule 14's neighbourhood, and this file's own standing rule that every
    list is derived from the source). So `visibleFloor` and the clamp are lifted out of
    `graph.js` by name and run.
    """
    engine = _js_engine()
    if engine is None:
        pytest.skip("no JavaScript engine on this machine to run the arithmetic with")

    root = Path(__file__).resolve().parents[1]
    src = root.joinpath("src/dunneflow/web/static/graph.js").read_text(encoding="utf-8")

    # The clamp, read off the source so a rename or a removal fails here rather than
    # silently restoring the defect.
    assert "const floor = visibleFloor(d, chosen);" in src, (
        "fitView no longer asks visibleFloor for a floor — a lone node will frame as a dot"
    )
    assert "scale = Math.min(scale, Math.min(w, h) / floor);" in src, (
        "the floor is no longer clamped against the tighter pane dimension — a short pane "
        "will crop the plate it was supposed to keep in view"
    )

    share = re.search(r"const PLATE_SHARE = ([0-9.]+);", src)
    assert share, "PLATE_SHARE is gone; how much plate a fit must show is now unstated"
    assert float(share.group(1)) >= 0.5, (
        f"PLATE_SHARE is {share.group(1)} — Tom asked for at least half the hosting plate"
    )

    # And the guarantee itself, exercised. A plate 669 units across, one node on it with no
    # neighbours, in the squattest pane the shell produces.
    prog = f"""
    const PLATE_SHARE = {share.group(1)};
    const plateAcross = 669, w = 258, h = 165;
    // What `bounds` hands back for a selection of one: no extent, and the `|| 1` fudge.
    const bRadius = 1, bHeight = 1;
    const floor = plateAcross * PLATE_SHARE;
    let worst = 1;
    for (const rot of [0, 35, 55, 90]) {{
      const t = rot * Math.PI / 180;
      const vertical = Math.abs(bHeight * Math.cos(t)) + Math.abs(2 * bRadius * Math.sin(t));
      let scale = Math.min((w * 0.90) / (2 * bRadius), (h * 0.88) / vertical);
      scale = Math.min(scale, Math.min(w, h) / floor);
      // The share of the plate visible in the tighter direction.
      worst = Math.min(worst, (Math.min(w, h) / scale) / plateAcross);
    }}
    console.log(worst.toFixed(3));
    """
    r = subprocess.run([engine, "-e", prog], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr or r.stdout
    worst = float(r.stdout.strip())
    assert worst >= 0.5, (
        f"at the worst tilt only {worst:.0%} of the hosting plate stays visible; "
        "a fit on one node is a magnified dot again"
    )
