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


def _busiest(comps):
    """The compartment with the most arrows of any lane.

    Not the most `inside` arrows: the sample tree is a single file, so every routine folds
    into one box and every arrow it has is a **crossing** to a port. Picking on `inside`
    alone chose an empty drawing and asserted over nothing -- a guard passing because it
    found no cases is rule 37 in its own file.
    """
    return max(comps.values(),
               key=lambda c: len(c.inside) + len(c.out) + len(c.into))


def _opened(analyzed: Store, comps):
    """The largest box, opened -- the second level, where the CALL arrows are."""
    import json
    box_of, label_of = diagram.box_index(comps)
    box = max((b for c in comps.values() for b in c.boxes if b.kind != "touch"),
              key=lambda b: b.holds)
    args = {"ids": json.dumps(list(box.members))}
    rows = analyzed.query
    touches = [dict(r) for r in rows(queries.FOLD_BOUNDARIES, args)]
    for t in touches:
        t["weight"] = 1
    return diagram.build_inside(
        box.id, box,
        [dict(r) for r in rows(queries.FOLD_MEMBERS, args)],
        [dict(r) for r in rows(queries.FOLD_INNER_CALLS, args)],
        [dict(r) for r in rows(queries.FOLD_CALLS_OUT, args)],
        [dict(r) for r in rows(queries.FOLD_CALLS_IN, args)],
        touches, box_of, label_of)


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


# --------------------------------------------------------------------------- #
# An edge, and what it says it carries. Same discipline as the tests above: run the
# real fold over the sample tree, because the failure worth catching here is a
# drawing whose arrows are all correct and all unanswerable.
# --------------------------------------------------------------------------- #


def test_every_arrow_carries_an_identity_that_names_two_real_boxes(analyzed: Store) -> None:
    """An arrow with no id is an arrow nothing can be asked about.

    `dot()` wrote `id=` on nodes only, so every edge carried Graphviz's own auto id and a
    click on one routed nowhere. This asserts the whole round trip -- the id is emitted,
    it splits, and both halves are boxes that exist in the drawing -- because emitting an
    id that does not split, or splits into something the compartment has never heard of,
    looks exactly like emitting a good one.
    """
    comps = diagram.build(_model(analyzed))
    # **Both levels, and both lanes.** The sample tree folds to one box per compartment, so
    # its only arrows are crossings to ports; the within-drawing arrows appear at the second
    # level. The first version checked the busiest compartment alone and survived a mutation
    # that stripped the id from exactly the lane this corpus has none of (rule 37).
    drawings = [_busiest(comps), _opened(analyzed, comps)]
    lanes = sum(len(c.inside) + len(c.out) + len(c.into) for c in drawings)
    assert lanes, "neither drawing has an arrow at all"
    seen = 0
    for c in drawings:
        src = diagram.dot(c, ports=True)
        known = {b.id for b in (*c.boxes, *c.ports)}
        edges = [ln for ln in src.splitlines() if " -> " in ln]
        for ln in edges:
            assert 'id="' in ln, f"an arrow with no identity: {ln.strip()}"
            eid = ln.split('id="', 1)[1].split('"', 1)[0]
            ends = diagram.split_edge(eid)
            assert ends, f"an arrow id that is not two ends: {eid}"
            assert ends[0] in known and ends[1] in known, (
                f"an arrow names a box this drawing does not hold: {eid}"
            )
            seen += 1
    assert seen == lanes, (
        f"{lanes} arrows in the two models and {seen} in their sources -- one of the lanes "
        "is drawn without being emitted, or emitted twice"
    )


def test_no_box_id_contains_the_edge_separator(analyzed: Store) -> None:
    """The claim the split rests on, asserted over every box in the program.

    `split_edge` partitions on the **first** separator, which is exact only while no box id
    can contain one. If one ever could, the split would name a box that does not exist and
    the flow panel would answer confidently about nothing (rule 30) -- silently, because
    every other step in the chain would still work.
    """
    comps = diagram.build(_model(analyzed))
    for c in comps.values():
        for b in (*c.boxes, *c.ports):
            assert diagram.EDGE_SEP not in b.id, (
                f"{b.id} contains {diagram.EDGE_SEP!r}, so an edge id built from it cannot "
                "be split back into its two ends"
            )


def test_an_arrow_keeps_the_kind_of_flow_and_not_only_its_weight(analyzed: Store) -> None:
    """A TOUCH and a CALL were indistinguishable in the payload.

    The lanes were `Counter[(src, dst)] -> weight`, so the kind was computed on the way in
    and dropped on the way out. Asserted over the *program* rather than over a constructed
    pair: the sample tree touches a database and calls its own routines, so both kinds are
    there to be told apart, and a mutation that reinstated a bare weight would still add up.
    """
    comps = diagram.build(_model(analyzed))
    seen: set[str] = set()
    # Both levels. The sample tree is one file, so at compartment level every routine folds
    # into one box and the only arrows are TOUCH crossings; the CALL arrows appear when that
    # box is opened. Asserting over one level would assert over one kind.
    for c in [*comps.values(), _opened(analyzed, comps)]:
        for lane in (c.inside, c.out, c.into):
            for pair, kinds in lane.items():
                assert kinds, f"an arrow with no kind at all: {pair}"
                seen |= set(kinds)
                got = diagram.edge_flow(c, *pair)
                assert got is not None, f"{pair} is drawn and cannot be looked up"
                assert got[1] == sum(kinds.values()), (
                    "an arrow's weight and the sum of its kinds disagree -- two answers to "
                    "one number (rule 13)"
                )
    assert {"CALL", "TOUCH"} <= seen, (
        f"the program folds to only {sorted(seen)}, so this cannot tell a kept kind from a "
        "constant"
    )


def test_an_arrow_that_is_not_there_is_none_rather_than_empty(analyzed: Store) -> None:
    """"No such arrow" and "the arrow carries nothing" are different claims."""
    comps = diagram.build(_model(analyzed))
    c = max(comps.values(), key=lambda x: len(x.boxes))
    assert diagram.edge_flow(c, "not|a|box", "nor|is|this") is None


def test_the_edge_payload_names_every_arrow_the_drawing_draws(analyzed: Store) -> None:
    """The hover card reads this map, so a missing arrow is a card that never appears."""
    comps = diagram.build(_model(analyzed))
    c = _busiest(comps)
    payload = diagram.edge_payload(c)
    for lane in (c.inside, c.out, c.into):
        for src, dst in lane:
            eid = diagram.edge_id(src, dst)
            assert eid in payload, f"{eid} is drawn and is not in the payload"
            assert payload[eid]["from"] == src and payload[eid]["to"] == dst


# --------------------------------------------------------------------------- #
# Binding an argument to a parameter: the one place this chunk makes a claim about
# meaning rather than about position, and therefore the one place rule 1 bites.
# A false binding is worse than no binding -- "this argument is that parameter" is
# exactly the confident, plausible, wrong answer the tool exists not to produce.
# --------------------------------------------------------------------------- #

from dunneflow.web.detail import bind_arguments  # noqa: E402


def _arg(idx, expr, keyword=None, splat=False):
    return {"idx": idx, "expr": expr, "keyword": keyword, "splat": splat}


def _param(name, kind="positional", type_=None):
    return {"name": name, "kind": kind, "type": type_, "dflt": None}


def test_a_keyword_binds_by_name_and_needs_nothing_else() -> None:
    out, why = bind_arguments([_arg(0, "5.0", keyword="timeout")],
                              [_param("url"), _param("timeout", type_="float")],
                              callee_expr="get", resolved=True)
    assert out[0]["binds"]["name"] == "timeout"
    assert out[0]["binds"]["type"] == "float"
    assert why == ""


def test_a_positional_binds_by_index_when_the_callee_is_plain() -> None:
    out, why = bind_arguments([_arg(0, "a"), _arg(1, "b")],
                              [_param("first"), _param("second")],
                              callee_expr="go", resolved=True)
    assert [x["binds"]["name"] for x in out] == ["first", "second"]
    assert why == ""


def test_an_unresolved_callee_binds_nothing_and_says_why() -> None:
    """There is no parameter list on the far side. A blank would read as "no such name"."""
    out, why = bind_arguments([_arg(0, "a")], [], callee_expr="whatever", resolved=False)
    assert out[0]["binds"] is None
    assert "not resolved" in why


def test_a_variadic_callee_binds_no_position() -> None:
    out, why = bind_arguments([_arg(0, "a")],
                              [_param("first"), _param("rest", kind="vararg")],
                              callee_expr="go", resolved=True)
    assert out[0]["binds"] is None
    assert "*args" in why


def test_a_keyword_still_binds_on_a_variadic_callee() -> None:
    """The refusal is about *position*. A name is a name however the callee is shaped."""
    out, _ = bind_arguments([_arg(0, "1", keyword="mode")],
                            [_param("rest", kind="vararg"),
                             _param("mode", kind="keyword")],
                            callee_expr="go", resolved=True)
    assert out[0]["binds"]["name"] == "mode"


def test_a_splat_binds_to_nothing_ever() -> None:
    out, _ = bind_arguments([_arg(0, "*xs", splat=True), _arg(1, "**kw", splat=True)],
                            [_param("a"), _param("b")],
                            callee_expr="go", resolved=True)
    assert [x["binds"] for x in out] == [None, None]


def test_a_positional_after_a_splat_is_unbindable_too() -> None:
    """`f(*xs, b)` puts `b` at an index nobody can compute.

    The easy version of this rule stops at the splat and carries on one place out, which
    binds `b` to the second parameter -- a specific, plausible, wrong answer.
    """
    out, _ = bind_arguments([_arg(0, "*xs", splat=True), _arg(1, "b")],
                            [_param("first"), _param("second")],
                            callee_expr="go", resolved=True)
    assert out[1]["binds"] is None


def test_self_dot_a_method_skips_the_receiver() -> None:
    """`self.render(x)` passes `x` to the *second* parameter, and that is certain.

    The dot binds the receiver, and the head being `self` is what makes it knowable rather
    than likely. Without the offset every argument of every method call lands one parameter
    early -- which is not a missing answer, it is a wrong one.
    """
    out, why = bind_arguments([_arg(0, "x")],
                              [_param("self"), _param("width", type_="int")],
                              callee_expr="self.render", resolved=True)
    assert out[0]["binds"]["name"] == "width"
    assert why == ""


def test_a_dotted_call_to_a_method_refuses_rather_than_guessing() -> None:
    """`obj.render(x)` and `Cls.render(obj, x)` are the same routine, written two ways.

    Nothing in the expression says which, so nothing is claimed -- and the pane says why,
    because a blank beside an argument reads as "no such parameter", which is different
    and false.
    """
    out, why = bind_arguments([_arg(0, "x")],
                              [_param("self"), _param("width")],
                              callee_expr="enrollment.render", resolved=True)
    assert out[0]["binds"] is None
    assert "receiver" in why


def test_a_plain_dotted_call_to_a_function_still_binds() -> None:
    """`mod.helper(x)` has a dot and no receiver, so the refusal above must not catch it."""
    out, why = bind_arguments([_arg(0, "x")], [_param("path")],
                              callee_expr="os.path.join", resolved=True)
    assert out[0]["binds"]["name"] == "path"
    assert why == ""


# --------------------------------------------------------------------------- #
# Ways in as nodes: the world outside, reaching in
#
# Tom: *"I could look at the Diagram and see the various Ways In as nodes on a Diagram and
# chase them inbound to see how the data flows into the system."*
#
# Three properties matter and only the first is about drawing: the entries must not disturb
# what the panel already counts, a box must measure *this* compartment, and the bound on the
# arrows must be stated.
# --------------------------------------------------------------------------- #


def _ways_for(store: Store) -> dict[str, list[str]]:
    from dunneflow.web.waysin import listing
    out: dict[str, list[str]] = {}
    for w in listing(store):
        for nid in w["nodes"]:
            names = out.setdefault(nid, [])
            if w["name"] not in names:
                names.append(w["name"])
    return out


def test_a_way_in_becomes_a_box_on_the_compartment_it_enters(analyzed: Store) -> None:
    model = build(analyzed)
    comps = diagram.build(model, _ways_for(analyzed))
    entries = [b for c in comps.values() for b in c.entries]
    assert entries, "no way in reached any compartment"
    assert all(b.kind == "wayin" for b in entries)
    assert all(b.detail.get("wayin") for b in entries), "an entry box cannot name its way in"


def test_the_counts_a_panel_prints_do_not_change(analyzed: Store) -> None:
    """Rule 32: a count says what it counts.

    "24 boxes over 237 routines" is about the program's own code. A way in is the world
    outside reaching into it, so it gets its own list and its own lane -- folded into `boxes`
    it would have grown that number by one and quietly changed what it meant.
    """
    model = build(analyzed)
    plain = diagram.build(model)
    withways = diagram.build(model, _ways_for(analyzed))
    for cid, c in plain.items():
        a, b = c.stats, withways[cid].stats
        for key in ("boxes", "routines", "inside", "crossing", "ports"):
            assert a[key] == b[key], f"{cid}.{key} changed from {a[key]} to {b[key]}"


def test_a_way_in_holds_what_it_starts_here_not_what_it_reaches(analyzed: Store) -> None:
    """Rule 24: a measurement must measure the thing it names.

    On Mensores `mensores` reaches 1,381 routines and starts 106 of them in `pkg:cli`. A box
    on `pkg:cli` labelled with the first number would be a fact about somewhere else.
    """
    model = build(analyzed)
    comps = diagram.build(model, _ways_for(analyzed))
    for c in comps.values():
        for b in c.entries:
            assert b.holds == len(b.members) > 0
            for nid in b.members:
                assert any(nid in box.members for box in c.boxes), \
                    "a way in claims a routine that is not in this compartment"


def test_the_arrow_bound_is_per_way_in_and_is_stated(analyzed: Store) -> None:
    """Rule 8: bound a diagram, and only a diagram -- and say by how much.

    Bounded over the compartment instead of per entry, one way in fanning out to 39 boxes
    would push another way in's single arrow out of the picture entirely.
    """
    model = build(analyzed)
    comps = diagram.build(model, _ways_for(analyzed))
    for c in comps.values():
        drawn = c.entry_arrows()
        per_src: dict[str, int] = {}
        for src, _ in drawn:
            per_src[src] = per_src.get(src, 0) + 1
        assert all(n <= diagram.ENTRY_ARROWS for n in per_src.values())
        assert c.stats["entry_hidden"] == len(c.entered) - len(drawn)
        assert set(drawn) <= set(c.entered), "an arrow is drawn that is not in the lane"


def test_a_compartment_with_no_way_in_draws_exactly_what_it_did(analyzed: Store) -> None:
    """46 of Mensores' 53 compartments are entered from nowhere, and must be untouched."""
    model = build(analyzed)
    plain = diagram.build(model)
    withways = diagram.build(model, _ways_for(analyzed))
    quiet = [cid for cid, c in withways.items() if not c.entries]
    assert quiet, "every compartment has a way in; this guard is blind"
    for cid in quiet:
        assert diagram.dot(plain[cid]) == diagram.dot(withways[cid])


def test_both_emitters_draw_the_same_entries_under_the_same_bound(analyzed: Store) -> None:
    """`dot` is drawn and `mermaid` is copied out; describing different graphs is the one
    thing offering both may never do."""
    model = build(analyzed)
    comps = diagram.build(model, _ways_for(analyzed))
    drew = 0
    for c in comps.values():
        if not c.entries:
            continue
        drew += 1
        d, mm = diagram.dot(c), diagram.mermaid(c)
        for b in c.entries:
            assert b.label in d and b.label in mm
        assert d.count("style=bold") == len(c.entry_arrows())
        assert mm.count("==>") == len(c.entry_arrows())
    assert drew, "no compartment had an entry to compare"


def test_an_entry_box_is_findable_and_an_entry_arrow_is_known(analyzed: Store) -> None:
    """A click has to resolve. A box the drawing carries and `find_box` cannot see is a
    shape (rule 30), and an arrow missing from `edge_payload` gives no card at all."""
    model = build(analyzed)
    comps = diagram.build(model, _ways_for(analyzed))
    c = next(x for x in comps.values() if x.entries and x.entry_arrows())
    b = c.entries[0]
    found = diagram.find_box(comps, b.id)
    assert found and found[1].id == b.id
    src, dst = c.entry_arrows()[0]
    payload = diagram.edge_payload(c)
    eid = diagram.edge_id(src, dst)
    assert eid in payload, "an entry arrow carries no card"
    assert payload[eid]["entry"] is True, "an entry arrow is not marked as one"
    assert diagram.edge_flow(c, src, dst) is not None, "an entry arrow reads as no arrow"
