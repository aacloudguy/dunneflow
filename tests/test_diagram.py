"""The compartment diagram, driven rather than read.

Every other check on this view reads source text. That catches a control wired to nothing
and a field nobody sends, and it is blind to the one failure that matters most here: a
build that produces *nothing*. A mutation emptying the compartment cache passed every
source guard in the suite -- the code was all still there, and every drawing was blank.

So these run the real thing over the sample tree: fold it, ask it what it holds, open a
box, and check the numbers agree with the model they came from.
"""

from __future__ import annotations

from dunneflow.store import Store
from dunneflow.web import diagram, queries
from dunneflow.web.graph import build


def _model(analyzed: Store):
    return build(analyzed, level="routine", min_disk=1)


def test_folding_a_program_yields_compartments_with_boxes_in_them(analyzed: Store) -> None:
    """The failure no source guard can see: a build that succeeds and produces nothing."""
    comps = diagram.build(_model(analyzed))
    assert comps, "folding the program produced no compartments at all"
    assert any(c.boxes for c in comps.values()), (
        "every compartment came back empty -- a blank drawing looks exactly like a "
        "compartment that genuinely holds nothing, and this program has none of those"
    )
    for c in comps.values():
        for b in c.boxes:
            assert b.members, f"{b.id} is a box standing for nothing (rule 30)"
            assert b.holds == len(b.members), (
                f"{b.id} counts {b.holds} and names {len(b.members)} -- a count must say "
                "what it counts (rule 32)"
            )
            assert len(b.labels) == len(b.members), (
                f"{b.id} carries {len(b.labels)} names for {len(b.members)} members, so a "
                "hover card names the wrong thing"
            )


def test_a_box_is_found_by_its_own_id_and_a_port_is_too(analyzed: Store) -> None:
    comps = diagram.build(_model(analyzed))
    box = next(b for c in comps.values() for b in c.boxes)
    found = diagram.find_box(comps, box.id)
    assert found is not None, "a box cannot be found by the id the drawing carries"
    assert found[1] is box
    assert found[0].id == box.id.partition("|")[0], (
        "the compartment is not the one the box id names, so a click resolves into the "
        "wrong drawing"
    )
    assert diagram.find_box(comps, "pkg:nope|class|nothing") is None


def test_a_folds_flow_is_the_arithmetic_the_picture_drew(analyzed: Store) -> None:
    """Rule 13: the number beside a claim must be what produced it.

    `flow_of` reads the counters `build` filled, so counting the arrows on the drawing and
    reading the pane cannot disagree. Asserted by recomputing both ways.
    """
    comps = diagram.build(_model(analyzed))
    for c in comps.values():
        for b in c.boxes:
            flow = diagram.flow_of(c, b.id)
            expect_out = (sum(1 for a, _ in c.inside if a == b.id)
                          + sum(1 for a, _ in c.out if a == b.id))
            expect_in = (sum(1 for _, d in c.inside if d == b.id)
                         + sum(1 for _, d in c.into if d == b.id))
            assert len(flow["out"]) == expect_out, f"{b.id}: out disagrees with the model"
            assert len(flow["in"]) == expect_in, f"{b.id}: in disagrees with the model"
            for row in (*flow["in"], *flow["out"]):
                assert row["id"] != b.id, "a box is listed as its own neighbour"
                assert row["label"], "a neighbour with no name is a row that cannot be read"


def test_opening_a_box_draws_the_routines_it_holds(analyzed: Store) -> None:
    """The second altitude, over the real store."""
    comps = diagram.build(_model(analyzed))
    box_of, label_of = diagram.box_index(comps)
    assert box_of, "no node knows which box it lives in, so no crossing can be placed"

    box = max((b for c in comps.values() for b in c.boxes if b.kind != "touch"),
              key=lambda b: b.holds)
    args = {"ids": __import__("json").dumps(list(box.members))}
    rows = analyzed.query
    inside = diagram.build_inside(
        box.id, box,
        [dict(r) for r in rows(queries.FOLD_MEMBERS, args)],
        [dict(r) for r in rows(queries.FOLD_INNER_CALLS, args)],
        [dict(r) for r in rows(queries.FOLD_CALLS_OUT, args)],
        [dict(r) for r in rows(queries.FOLD_CALLS_IN, args)],
        [], box_of, label_of)

    assert inside.boxes, "opening a box drew nothing"
    routines = [b for b in inside.boxes if b.kind == "routine"]
    assert len(routines) == box.holds, (
        "the second level draws a different number of routines than the first level said "
        "it folded -- one of the two numbers is about something else (rule 32)"
    )
    for b in routines:
        assert b.members == [b.id], (
            "a routine box at the second level does not stand for itself, so clicking it "
            "cannot reach the one selection the dashboard shares"
        )
    # A port names a box, never a raw id: every one must be something `label_of` knows.
    for p in inside.ports:
        assert p.detail.get("box") in label_of, (
            f"the port {p.id} stands for something no box index knows -- a control carrying "
            "no identity resolves to nothing (rule 30)"
        )


def test_both_emitters_describe_the_same_graph(analyzed: Store) -> None:
    """Offering DOT and Mermaid is only safe because one `Compartment` makes both."""
    comps = diagram.build(_model(analyzed))
    c = max(comps.values(), key=lambda x: len(x.boxes))
    dot, mmd = diagram.dot(c, ports=True), diagram.mermaid(c)
    for b in c.boxes:
        assert b.label.split("…")[0] in dot, f"{b.label} is drawn by neither name"
        assert b.label.split("…")[0].replace('"', "'") in mmd, f"{b.label} is not exported"
    # One arrow per connection in each, so a reader counting them gets the same answer.
    assert dot.count(" -> ") == len(c.inside) + len(c.out) + len(c.into)
    assert mmd.count("-->") + mmd.count("-.->") == len(c.inside) + len(c.out) + len(c.into)
