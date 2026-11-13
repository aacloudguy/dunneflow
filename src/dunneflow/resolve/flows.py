"""Tracing what happens after a program is started.

A flow is the reader's own model made concrete: begin at a way in, follow the calls,
and record where the program touches the world. Everything between those two things
is machinery, and machinery that never reaches a boundary is left out.

Every traversal here is bounded -- by depth and by node count -- because the point is
a picture someone can read, not a complete one. An unbounded graph of a 4,500-routine
program is not more informative than a bounded one; it is less.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..schema import BoundaryHit, BoundaryKind, Direction
from ..store import Store
from .entrypoints import binding_note, supplied_whys

DEFAULT_DEPTH = 6
DEFAULT_MAX_NODES = 45


@dataclass(slots=True)
class FlowNode:
    routine_id: str
    name: str
    qualname: str
    module: str
    depth: int
    boundaries: list[BoundaryHit] = field(default_factory=list)


@dataclass(slots=True)
class Flow:
    """One way in, and everything it sets in motion."""

    entry_name: str
    entry_kind: str
    root_id: str | None
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    truncated: bool = False
    total_reachable: int = 0

    def boundary_summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for n in self.nodes:
            for b in n.boundaries:
                out[b.kind.value] = out.get(b.kind.value, 0) + 1
        # Commonest kind first, ties by name — `FILE ×7` and `STDIO ×7` are one order
        # and not two (rule 66).
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _reach(start: str, out: dict[str, list[str]]) -> int:
    """How many traced routines `start` leads to, itself excluded, over the traced edges."""
    seen, todo = {start}, [start]
    while todo:
        for nxt in out.get(todo.pop(), []):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return len(seen) - 1


def trace_flow(
    store: Store,
    root_id: str,
    entry_name: str,
    entry_kind: str = "CLI",
    max_depth: int = DEFAULT_DEPTH,
    max_nodes: int = DEFAULT_MAX_NODES,
    min_salience: str = "normal",
) -> Flow:
    """Breadth-first from one entrypoint, widest-first so the shape appears early."""
    flow = Flow(entry_name=entry_name, entry_kind=entry_kind, root_id=root_id)

    allowed = {"low", "normal", "high"} if min_salience == "low" else (
        {"normal", "high"} if min_salience == "normal" else {"high"}
    )

    seen: set[str] = {root_id}
    order: list[tuple[str, int]] = [(root_id, 0)]
    level = [root_id]

    # One query per depth level rather than one per routine. At six levels that is
    # six round trips instead of several hundred, which matters most on the cold
    # first read where each one would otherwise touch the disk.
    for depth in range(max_depth):
        if not level:
            break
        rows = store.query(
            # **Ordered, and it was not** (rule 66) — and here an undefended order is not
            # cosmetic. The walk is breadth-first and `max_nodes` truncates it, so row
            # order decides *which routines are in the picture at all*, and row order is
            # the order the process pool happened to finish files in. Two analyses of one
            # tree by one build drew different flows.
            #
            # By id rather than by qualname: an id is `make_id`'s, derived from names and
            # never from a position, so it is arbitrary in appearance and identical in
            # every build at every commit — where a join to `routines` for a readable
            # order would cost one per level on the cold read this query was batched to
            # avoid.
            "SELECT DISTINCT caller_id, callee_id FROM calls"
            " WHERE caller_id IN (SELECT value FROM json_each(?))"
            "   AND callee_id IS NOT NULL AND external = 0"
            " ORDER BY caller_id, callee_id",
            (json.dumps(level),),
        )
        nxt: list[str] = []
        for r in rows:
            cid = r["callee_id"]
            flow.edges.append((r["caller_id"], cid))
            if cid in seen:
                continue
            seen.add(cid)
            order.append((cid, depth + 1))
            nxt.append(cid)
        level = nxt

    flow.total_reachable = len(seen)
    if len(order) > max_nodes:
        flow.truncated = True
        # **Shallowest first, then widest reach, then id** (BACKLOG 3, Tom 2026-10-02). The
        # cut used to fall wherever the walk happened to be, which was reproducible and
        # arbitrary -- rule 66's floor. Depth keeps the top of the flow, which is what a
        # reader orients by; within the level the cut falls in, a routine that leads to
        # more of what was traced is the one worth keeping; the id settles the rest.
        # The walk is breadth-first, so `order` is already by depth and only the level the
        # cut falls in has to be ranked -- reach is measured there and nowhere else.
        cut_at = order[max_nodes - 1][1]
        out: dict[str, list[str]] = {}
        for a, b in flow.edges:
            out.setdefault(a, []).append(b)
        reach = {rid: _reach(rid, out) for rid, d in order if d == cut_at}
        order.sort(key=lambda o: (o[1], -reach.get(o[0], 0), o[0]))
        order = order[:max_nodes]

    kept = {rid for rid, _ in order}
    flow.edges = [(a, b) for a, b in flow.edges if a in kept and b in kept]

    ids = [rid for rid, _ in order]
    meta = {
        r["id"]: r
        for r in store.query(
            "SELECT id, name, qualname, module FROM routines"
            " WHERE id IN (SELECT value FROM json_each(?))",
            (json.dumps(ids),),
        )
    }
    bounds_by: dict[str, list[BoundaryHit]] = {}
    for r in store.query(
        "SELECT * FROM boundaries WHERE routine_id IN (SELECT value FROM json_each(?))"
        " ORDER BY line, kind, direction, target, evidence", (json.dumps(ids),)
    ):
        if r["salience"] not in allowed:
            continue
        bounds_by.setdefault(r["routine_id"], []).append(BoundaryHit(
            routine_id=r["routine_id"], kind=BoundaryKind(r["kind"]),
            direction=Direction(r["direction"]), target=r["target"], line=r["line"],
            evidence=r["evidence"], salience=r["salience"],
        ))

    for rid, depth in order:
        row = meta.get(rid)
        if row is None:
            continue
        flow.nodes.append(FlowNode(
            routine_id=rid, name=row["name"], qualname=row["qualname"],
            module=row["module"], depth=depth, boundaries=bounds_by.get(rid, []),
        ))
    return flow


def boundary_index(store: Store, min_salience: str = "normal") -> dict[str, list[dict]]:
    """Every boundary in the program, grouped by kind. The "what does it touch" ledger."""
    sal = ("low", "normal", "high") if min_salience == "low" else (
        ("normal", "high") if min_salience == "normal" else ("high",)
    )
    placeholders = ",".join("?" * len(sal))
    rows = store.query(
        f"""SELECT b.kind, b.direction, b.target, b.evidence, b.salience, b.line,
                   r.qualname, r.module, r.file
              FROM boundaries b JOIN routines r ON b.routine_id = r.id
             WHERE b.salience IN ({placeholders})
             ORDER BY b.kind, b.target, r.qualname, r.file, b.line, b.direction,
                      b.evidence""",
        tuple(sal),
    )
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["kind"], []).append({
            "direction": r["direction"], "target": r["target"], "evidence": r["evidence"],
            "salience": r["salience"], "qualname": r["qualname"], "module": r["module"],
            "file": r["file"], "line": r["line"],
        })
    # Most populous kind first, **ties broken by name** — see `render/page.biggest_first`,
    # which is the same three-quarters of an order written eight times over. Not imported
    # from there: `render/` reads `resolve/` and never the other way round.
    return {k: out[k] for k in sorted(out, key=lambda k: (-len(out[k]), k))}


def entry_reach(store: Store, routine_id: str) -> tuple[int, list[BoundaryKind]]:
    """How much of the program one way in commands, and what it ends up touching."""
    reach = store.reachable_through_macros([routine_id])
    hits = store.boundaries_reached_many([routine_id], through_macros=True)
    kinds = sorted({b.kind for b in hits}, key=lambda k: k.value)
    return len(reach), kinds


#: The annotation kinds that mean *somebody signed off on this*. Named here rather than
#: written into the statement below, so that a surface can say which kinds it asked about
#: and the sentence and the query cannot drift (rule 41).
GOVERNANCE_KINDS: tuple[str, ...] = ("PLAN", "DECISION", "AUDIT_LOCK")


def ways_in_affected(store: Store, routine_ids: list[str]) -> list[dict]:
    """The ways in that reach any of these routines — *impact*'s second half.

    Out of `cmd_impact`, where it was written inline and was the one part of that answer
    living only as print code. `dunneflow impact` and the MCP `impact` tool have to agree
    about which ways in a change disturbs, and two statements cannot be relied upon to
    (rule 51).

    Empty in, empty out, and deliberately so: the caller has already decided there are
    callers to ask about, and `IN ()` is not valid SQL.
    """
    if not routine_ids:
        return []
    return [dict(r) for r in store.query(
        "SELECT DISTINCT name, kind FROM entrypoints"
        " WHERE routine_id IN (SELECT value FROM json_each(:ids))"
        "    OR id IN (SELECT entrypoint_id FROM entrypoint_roots"
        "               WHERE routine_id IN (SELECT value FROM json_each(:ids)))"
        " ORDER BY name",
        {"ids": json.dumps(list(routine_ids))},
    )]


def governance_over(store: Store, routine_ids: list[str]) -> list[str]:
    """The plans, decisions and audit locks recorded against any of these routines.

    The values alone, deduplicated and ordered, because that is what both surfaces print.
    `GOVERNANCE_KINDS` above is the population, stated once.
    """
    if not routine_ids:
        return []
    kinds = ",".join("?" * len(GOVERNANCE_KINDS))
    return [r["value"] for r in store.query(
        "SELECT DISTINCT value FROM annotations"
        " WHERE owner_id IN (SELECT value FROM json_each(?))"
        f" AND kind IN ({kinds}) ORDER BY value",
        (json.dumps(list(routine_ids)), *GOVERNANCE_KINDS),
    )]


def app_command_routines(store: Store, app_id: str, seen: set[str] | None = None) -> list[str]:
    """Every routine reachable as a command of one CLI application, including its
    mounted sub-applications."""
    seen = seen if seen is not None else set()
    if app_id in seen:
        return []
    seen.add(app_id)
    # **Ordered by the name the command is typed under**, which is both a defended order
    # and a readable one. Neither query had one, and the map never showed it: `ways_in`
    # takes `len(roots)` and `reachable_from_many` takes a set, so the list's order reached
    # no document — the *dashboard* sends the list itself, as `nodes` on every row of the
    # cover, and Comitia's 107 ids came back arranged differently between two readings of
    # one map. `routine_id` and `child_id` last, because two commands can share a name.
    out = [
        r["routine_id"]
        for r in store.query(
            "SELECT routine_id FROM entrypoints"
            " WHERE parent_id = ? AND routine_id IS NOT NULL"
            " ORDER BY name, routine_id", (app_id,)
        )
    ]
    for m in store.query(
        "SELECT child_id FROM cli_mounts WHERE parent_id = ? AND child_id IS NOT NULL"
        " ORDER BY name, child_id",
        (app_id,),
    ):
        out.extend(app_command_routines(store, m["child_id"], seen))
    return out


def ways_in(store: Store) -> list[dict]:
    """Distinct ways in, ranked by how much of the program each commands.

    Deduplicated by the routine they actually start, because one entry is commonly
    detected three ways at once -- a console script, a `__main__` guard, and a
    conventionally named `main` -- and listing it three times buries the others.
    Names are preferred in that order of authority.
    """
    rank = {"CLI": 0, "MCP_TOOL": 1, "HTTP_ROUTE": 1, "IPC_COMMAND": 1, "MAIN": 2}
    best: dict[str, dict] = {}
    said = supplied_whys(store)
    # The bodies a way in with none of its own may start. See `entrypoint_roots`.
    answering: dict[str, list[str]] = {}
    for r in store.query("SELECT entrypoint_id, routine_id FROM entrypoint_roots"
                         " ORDER BY entrypoint_id, routine_id"):
        answering.setdefault(str(r["entrypoint_id"]), []).append(str(r["routine_id"]))

    for e in store.entrypoints():
        if e.group:  # a subcommand: reported inside its executable, not beside it
            continue
        roots: list[str] = []
        if e.routine_id:
            roots.append(e.routine_id)
        if e.parent_id:
            roots.extend(r for r in app_command_routines(store, e.parent_id) if r)
        overriders = answering.get(e.id, [])
        roots.extend(overriders)
        # **A declaration that bound nothing is still a way in** (design rule 21). It was
        # dropped here, which was right while the only declarations were Python console
        # scripts -- one that reached no routine really was a broken `[project.scripts]`
        # entry. It is wrong the moment a manifest can declare a way into a language this
        # build has no reader for: DunneNote's three Rust binaries are the front doors of
        # that application, and a panel that silently holds none of them tells a reader
        # the program has no way in.
        #
        # Only a **declared** one is kept. A conventional `main` that resolved to nothing
        # is the old case and still goes: nothing declared it, so there is nothing to
        # report but an absence.
        # And one its reader said has no body, with the reason: a `UFUNCTION`
        # `BlueprintImplementableEvent` is as real a way in as a manifest's, and its body
        # being generated is a fact about it, not an absence.
        if not roots and not e.declared and e.id not in said:
            continue
        # The id, where there are no roots to key on. Every unbound declaration would
        # otherwise collapse onto the empty string and the panel would hold one of them.
        key = (f"app:{e.parent_id}" if e.parent_id
               else (e.routine_id or f"ep:{e.id}"))

        # **A field, not a substring test against a sentence.** This read
        # `"[project.scripts]" in e.evidence` until chunk 12, which is rule 30 in the
        # one place it decides a sort: `declared` is the primary key of the score
        # below, so a `package.json` `bin` -- which can never contain that string --
        # would have ranked below a guessed name for every TypeScript program there
        # is. The provider that read the manifest sets the field.
        declared = e.declared
        score = (0 if declared else 1, rank.get(e.kind.value, 3), len(e.name))
        prev = best.get(key)
        if prev is None or score < prev["_score"]:
            reach = store.reachable_from_many(roots) if roots else []
            kinds = sorted(
                {b.kind for b in store.boundaries_reached_many(roots)},
                key=lambda k: k.value,
            ) if roots else []
            best[key] = {
                "name": e.name, "kind": e.kind.value, "evidence": e.evidence,
                "roots": roots, "reach": len(reach), "kinds": kinds,
                "declared": declared, "aliases": [] if prev is None else prev["aliases"],
                # **Bound, and why not.** A reach of 0 says how much this way in commands
                # and says nothing about whether it commands anything *here*; those are
                # different facts and the second is the one a reader needs in front of a
                # Rust binary (rule 32). `binding_note` words it in one place.
                "bound": bool(roots),
                # Kept where there are overriders: *any of these* is the part of the answer
                # the roots alone cannot say.
                "why": (said.get(e.id, "") if overriders else
                        "" if roots else binding_note(store, e.id).sentence),
                "overriders": bool(overriders),
                # **The app object, when this way in is a command tree rather than a
                # routine.** `lictores` names `lictores.cli:app` -- a Typer object, which
                # is not a routine and has no file to open -- and expands here to the 107
                # commands hung off it. Carried rather than left to be guessed from
                # `len(roots) > 1`, because "this is a tree" and "this happens to start
                # several routines" are different facts that look identical (rule 30), and
                # a reader who clicks the name is owed the tree rather than whichever of
                # its commands a query returned first.
                "app_id": e.parent_id,
                "_score": score,
            }
            if prev is not None:
                best[key]["aliases"] = [*prev["aliases"], prev["name"]]
        else:
            prev["aliases"].append(e.name)

    # Ranked by reach, **and ties broken by name and kind** (rule 66). Two ways in
    # commanding the same number of routines is the ordinary case, not the exotic one:
    # Comitia has two `main` entries reaching 17 and 2, and a `README.md` that listed them
    # in a different order every run was how this whole defect first showed itself.
    out = sorted(best.values(), key=lambda d: (-d["reach"], d["name"], d["kind"],
                                               d["evidence"]))
    for d in out:
        d.pop("_score", None)
    return out
