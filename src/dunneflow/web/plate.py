"""One plate of the stack, described as the thing it is.

**A plate is not a node, and it is not one of the things it holds.** Clicking a package in
the navigator set `wanted.disks` and no subject at all, so the crumb read *"nothing
selected"*, the table went on showing all 4,786 rows, and the inspector answered *"Pick a
way in from the cover, **a package from the navigator**, or a node in the graph"* -- naming
the gesture that had just failed. One cause, three symptoms, and it was pre-existing rather
than introduced.

The obvious fix is the one this file exists instead of: nominating a member. That is
exactly the defect `detail.fold` was written to undo, where a box of sixty-one methods
filled the inspector with whichever one sorted first -- a true answer about something
nobody clicked (rules 32 and 74). A plate holding 926 nodes would make the same mistake
twenty times over.

**Read from the payload that is on screen, never from a second build.** `serve` caches one
columnar payload per `(level, minDisk)`, and that payload is the picture: which plates
survived the merge, what is on each, and which package a merged node came from are all
decisions the model already made. Rebuilding here would cost ~120 ms to produce a *second*
answer to a question that has one, and the two could differ the moment a fold rule changes
(rule 13). So this reads the arrays.

**And the neighbours are counted from the store, never from `m.edges`.** `packages.py`
wrote that warning down before anything needed it: the 2.5D model stores every crossing
twice, once per plate, each copy ending in a shadow (rule 23), so aggregating drawn edges
would double every weight here -- silently, and the numbers would still look like numbers.
The store holds each call exactly once. Shadows are skipped when reading members for the
same reason from the other side: a shadow is never an endpoint (rule 31).

**Five plates, five answers.** `pkg:<name>` is a package; `ext:<KIND>` is a boundary kind
beyond the system line; `ext:ARTEFACT` is the files the program *names* rather than uses;
and `pkg:<small>` and `ext:<small outside>` are folds of plates too small to draw. A fold
says what it stands for and never claims to be one of them (rule 74), and each of the five
gets its own sentence rather than a shared one with a blank in it (design rule 21). A sixth
id exists at module level only: `ext:<outside>`, the one plate every external node folds
onto there (`graph.OUTSIDE_DISK`), which `identity.outside` flags.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..store import Store
from . import queries
from .graph import OUTSIDE_DISK, SMALL_DISK

#: The plates that stand for other plates. Read from `graph.SMALL_DISK` rather than spelled
#: again: it is the same set the fold writes, and two lists of merged-plate ids would agree
#: until the day one of them was edited (rule 51).
MERGED_PLATES = frozenset(SMALL_DISK.values())

#: What each band is called on screen. A `pkg:` plate is the program's own code and an
#: `ext:` plate is beyond the boundary line, which is design rule 8's whole distinction --
#: and the word has to be right, because the tag is the only thing saying which side of the
#: line the reader is looking at.
BAND_TAG = {"pkg": "PACKAGE", "ext": "OUTSIDE"}


def describe(store: Store, payload: dict[str, Any], plate_id: str,
             ways: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The plate on screen, in the shape every other specimen uses.

    `kind: "PLATE"` rather than one of the six `classify()` knows, for `detail.fold`'s
    reason: calling a plate a ROUTINE would put the wrong word in the inspector's head and
    the wrong answer in every check that reads it (rule 30).

    `ways` is `waysin.listing()`, passed in rather than asked for here: `serve` asks for
    it beside the payload and there is exactly one answer to what a way in is (rule 51).
    `None` means the caller has none to give, which is a different state from a plate
    holding none and is why the parameter has no default list to hide behind.
    """
    ways = ways or []
    known = {str(d["id"]): d for d in payload.get("disks") or []}
    row = known.get(plate_id)
    if row is None:
        return {"found": False, "id": plate_id,
                "reason": "no such plate at this level of detail — the stack is drawn "
                          "differently at each altitude, and a plate that exists at one "
                          "may be merged away at another"}

    members, holds, homes = _members(payload, plate_id)
    band = plate_id.partition(":")[0]

    detail: dict[str, Any] = {
        "kind": "PLATE",
        "id": plate_id,
        "label": str(row.get("name") or plate_id),
        "found": True,
        "identity": {
            "plate": plate_id,
            "band": band,
            "tag": BAND_TAG.get(band, band.upper()),
            "name": str(row.get("name") or ""),
            "level": str(payload.get("level") or ""),
            # What the model says it holds, beside what was counted here. They are two
            # readings of one fact and a claim's query must return what is printed beside
            # it (rule 13), so a test asserts they agree rather than a comment hoping so.
            "nodes": int(row.get("nodes") or 0),
            "shadows": int(row.get("shadows") or 0),
            "edges": int(row.get("edges") or 0),
            "merged": plate_id in MERGED_PLATES,
            "outside": plate_id == OUTSIDE_DISK,
        },
        # **The members are counted, not listed.** Every other pane in this dashboard lists
        # what it holds and rule 8 forbids bounding it -- and both are right, because a
        # fold holds sixty-one methods and the reader came to find one of them. A plate
        # holds up to 926, they are *already* the routine list, and that list marks them
        # the moment this plate is selected (design rule 26). Listing them again here would
        # be the same rows in a narrower column, and would cost `FOLD_PARAMS` over 926 ids
        # to render an invocation line nobody asked for.
        "holds": holds,
        # **The member ids, sent rather than derived on the client.**
        #
        # They were read off the drawn payload in the browser for one draft, on the
        # reasoning that the plate's members *are* the nodes on that disk and reading them
        # from the picture is the one answer that cannot disagree with it. The reasoning
        # was right and the premise was not: **there is not always a picture** (rule 87).
        # In Table mode the graph is never mounted, so `graphPayload` is null -- and a
        # package click there marked *0 of 4,786 rows* while the pane beside it correctly
        # said 469. Found by clicking one, in the mode a reader spends most of their time
        # in. Satisfying rule 13 by deriving *from* the render makes the claim exactly as
        # conditional as the render, which is what rule 87 is.
        #
        # Rule 13 is unharmed, because this is computed from that same payload: `serve`
        # hands us `base.payloads[key]`, so the list here and the plate on screen are one
        # reading whether or not the browser has drawn it.
        #
        # Never bounded (rule 8), and it is not a diagram: 926 ids is the largest plate on
        # Lictores, beside a routine list the client already holds 4,786 rows of.
        "members": members,
        # Which plates it stands for, and nothing else claims to be one of them (rule 74).
        # Empty for every plate that is not a fold, which is a different answer from "this
        # fold merged nothing" and is told apart by `identity.merged`.
        "stands_for": homes,
        # **Which question was asked, declared rather than inferred from an empty list.**
        # A package answers "what calls in, what does it call, what does it touch"; a plate
        # beyond the boundary line answers "what reaches it", and the other two are not
        # questions about it at all. Both produce `[]` on the wire and they mean entirely
        # different things (rule 30), so the shell is told which it is holding instead of
        # guessing from a length -- an external plate rendered as a package with three
        # empty sections would say the database is touched by nothing.
        "answers": "outside" if band == "ext" else "package",
    }
    if band == "ext":
        detail["in"] = _reached_by(store, payload, members, plate_id)
        detail["out"] = []
        detail["touches"] = {"kinds": [], "total": 0}
        detail["ways_in"] = []
    else:
        detail["in"] = _neighbours(store, payload, members,
                                   queries.FOLD_CALLS_IN, plate_id)
        detail["out"] = _neighbours(store, payload, members,
                                    queries.FOLD_CALLS_OUT, plate_id)
        detail["touches"] = _touches(store, members)
        detail["ways_in"] = _ways_in(ways, members)
    return detail


def _members(payload: dict[str, Any],
             plate_id: str) -> tuple[list[str], dict[str, int], list[dict[str, Any]]]:
    """The plate's own nodes, what kinds they are, and where the merged ones came from.

    **Real nodes only.** A shadow sits on this plate and belongs to another, so counting
    one here would report a plate as holding what it borrows -- and asking the store about
    its id would attribute another plate's calls to this one. Rule 31 is usually quoted
    about drawing an edge; it is the same rule when reading what is on a plate.

    `home` is written by `_fold_small_disks` onto every node it moves, which is what lets a
    `<small>` plate say what it stands for without re-deciding the merge.
    """
    nodes = payload.get("nodes") or {}
    ids = nodes.get("id") or []
    kinds = nodes.get("kind") or []
    disks = nodes.get("disk") or []
    shadow = nodes.get("shadow") or []
    detail = nodes.get("detail") or []

    members: list[str] = []
    holds: dict[str, int] = defaultdict(int)
    from_home: dict[str, int] = defaultdict(int)
    for i, disk in enumerate(disks):
        if disk != plate_id or shadow[i]:
            continue
        members.append(str(ids[i]))
        holds[str(kinds[i])] += 1
        home = str((detail[i] or {}).get("home") or "")
        if home:
            from_home[home] += 1

    homes = [{"plate": h, "name": h.partition(":")[2], "nodes": n}
             for h, n in sorted(from_home.items(), key=lambda kv: (-kv[1], kv[0]))]
    return members, dict(sorted(holds.items())), homes


def _neighbours(store: Store, payload: dict[str, Any], members: list[str],
                sql: str, plate_id: str) -> list[dict[str, Any]]:
    """Which *plates* reach this one, or are reached by it, counted from the store.

    The queries are `detail.fold`'s own -- one row per connection between a member and
    something outside the set, which is exactly the question one plate over. Reusing them
    rather than writing a plate-shaped pair means the two cannot drift, and it means this
    inherits their one property that matters: they exclude the set itself, so a package's
    internal traffic is not reported as a package calling itself.

    The far end is mapped to *its* plate through the same `disk` column the picture is
    drawn from, so a row here and an arrow there cannot disagree about where something
    lives (rule 13). A far end that is on no plate is dropped and counted rather than
    drawn to nowhere -- `_add_edges` says why, and a vanished edge nobody counts is the
    silent filter design rule 1 forbids.
    """
    if not members:
        return []
    nodes = payload.get("nodes") or {}
    ids = nodes.get("id") or []
    disks = nodes.get("disk") or []
    shadow = nodes.get("shadow") or []
    disk_of = {str(ids[i]): str(disks[i]) for i in range(len(ids)) if not shadow[i]}
    names = {str(d["id"]): str(d.get("name") or d["id"])
             for d in payload.get("disks") or []}

    weights: dict[str, int] = defaultdict(int)
    unplaced = 0
    for r in store.query(sql, {"ids": json.dumps(members)}):
        far = disk_of.get(str(r["other"]))
        if far is None or far == plate_id:
            unplaced += 1
            continue
        weights[far] += int(r["weight"] or 0)

    out = [{"plate": p, "name": names.get(p, p.partition(":")[2] or p), "weight": w}
           for p, w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))]
    if unplaced:
        # Stated as a row of its own rather than folded into a total, because "12 calls to
        # something this map does not draw" and "12 calls to `lictores.cli`" are different
        # facts (rule 32). It has no plate, so it carries no id to select.
        out.append({"plate": "", "name": "not on any plate", "weight": unplaced,
                    "unplaced": True})
    return out


def _reached_by(store: Store, payload: dict[str, Any], members: list[str],
                plate_id: str) -> list[dict[str, Any]]:
    """Which plates reach a plate that is **outside** the program.

    **This is why an external plate is a branch and not a parameter.** A boundary node's id
    is `bnd:<kind>:<target>` and an artefact's is `art:<name>`; neither is a routine id, so
    `FOLD_CALLS_IN` -- which joins `calls.callee_id` against the set -- matched nothing at
    all. Measured before it was noticed: `ext:STDIO` holds 991 nodes and reported **0 in,
    0 out, 0 touches**, which on screen is the claim that nothing in Lictores writes to
    standard output. An empty section is the most confident kind of wrong answer this tool
    can produce, and it produced four of them per external plate.

    `BOUNDARY_EDGES` and `ARTEFACT_EDGES` are the store's own answer and are the *same two
    queries* `graph.py` places these edges from -- so the rows behind this pane and the
    arrows in the picture are one reading (rule 13). Whole-program and already aggregated
    by `(routine, target)`, which is why filtering in Python beats a `json_each` join on a
    computed id that no index can serve.

    A touch is not a call, and the two are never added together (rule 2). The far end is a
    plate rather than a routine for `_neighbours`' reason, and the same unplaced row says
    so when there is one.
    """
    if not members:
        return []
    nodes = payload.get("nodes") or {}
    ids = nodes.get("id") or []
    disks = nodes.get("disk") or []
    shadow = nodes.get("shadow") or []
    disk_of = {str(ids[i]): str(disks[i]) for i in range(len(ids)) if not shadow[i]}
    names = {str(d["id"]): str(d.get("name") or d["id"])
             for d in payload.get("disks") or []}
    mine = set(members)

    weights: dict[str, int] = defaultdict(int)
    unplaced = 0
    for sql in (queries.BOUNDARY_EDGES, queries.ARTEFACT_EDGES):
        for r in store.query(sql):
            if str(r["dst"]) not in mine:
                continue
            far = disk_of.get(str(r["src"]))
            if far is None or far == plate_id:
                unplaced += 1
                continue
            weights[far] += int(r["weight"] or 0)

    out = [{"plate": p, "name": names.get(p, p.partition(":")[2] or p), "weight": w}
           for p, w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))]
    if unplaced:
        out.append({"plate": "", "name": "not on any plate", "weight": unplaced,
                    "unplaced": True})
    return out


def _touches(store: Store, members: list[str]) -> dict[str, Any]:
    """What the plate reaches outside the program, by kind.

    Counted rather than listed, for `holds`' reason: a package touches STDOUT 991 times and
    the list of targets is the boundary plate's own answer, one click away. What a reader
    wants here is the shape -- does this package talk to the database, the network, the
    filesystem -- and a count per kind is that shape exactly.
    """
    if not members:
        return {"kinds": [], "total": 0}
    args = {"ids": json.dumps(members)}
    kinds: dict[str, int] = defaultdict(int)
    for r in store.query(queries.FOLD_BOUNDARIES, args):
        kinds[str(r["kind"])] += 1
    rows = [{"kind": k, "n": n}
            for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"kinds": rows, "total": sum(kinds.values())}


def _ways_in(ways: list[dict[str, Any]], members: list[str]) -> list[dict[str, Any]]:
    """The ways in that land on this plate, read from the one place that answers it.

    A package holding an entrypoint is where a reader starts, which is the whole reason
    `packages.py` ranks its columns outward from them. Never bounded: a plate holding
    forty ways in is a plate whose forty ways in are the answer.

    **This was a query of its own for one draft, and the measurement is why it is not.**
    `SELECT … FROM entrypoints WHERE parent_id IS NULL` looked like the obvious way to
    keep a command tree's root and drop its 107 subcommands. Against Lictores it dropped
    **all 32 MCP_TOOL entrypoints**, every one of which has a parent, and **two of the
    four executables `CLAUDE.md` names as ground truth** -- `lictores` and `lictores-mcp`
    never appeared. A silent filter (design rule 1) reached by writing a second opinion
    about what a way in is, in a file whose own docstring cites rule 51.

    `waysin.listing()` is that one opinion: the cover row, the way-in pane, the diagram
    and now this read the same answer, so a way in cannot be declared on one surface and
    guessed on another. A tree arrives as **one** entry carrying its roots, which is the
    subcommand problem solved by rule 74 rather than by a `WHERE` clause -- a tree is not
    one of the things it holds, and its own pane lists them.

    Membership is *any* root on this plate, not all of them. `lictores` is
    `lictores.cli:app` expanding to 107 commands across 44 files and therefore across
    several plates; a plate holding one of them is a plate that way in enters, which is
    what `_compartments` already means by the same test.
    """
    if not members:
        return []
    on_plate = set(members)
    out: list[dict[str, Any]] = []
    for w in ways:
        roots = [n for n in (w.get("nodes") or []) if n in on_plate]
        if not roots:
            continue
        out.append({
            "name": w.get("name") or "",
            "kind": w.get("kind") or "",
            "declared": bool(w.get("declared")),
            "app": bool(w.get("app")),
            # How much of it is here, beside how much of it there is. A tree with 3 of its
            # 107 roots on this plate is a different fact from one wholly here, and a bare
            # name would say neither (rule 32).
            "here": len(roots),
            "roots": len(w.get("nodes") or []),
        })
    return out
