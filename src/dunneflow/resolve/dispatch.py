"""Which bodies a dispatched call may reach, where its own checker said: looked up, never argued.

**A `dynamic` call is resolved, to a slot several bodies fill.** The checker named the
method and named every body in the tree that can answer it; which one runs is the
object's, at run time. Until 2026-11-02 only the count crossed the wire (`candidates`), so
every walk stopped at the call: traccar's protocol layer sits behind one abstract `decode`
with 271 bodies, Netty calls it, and 3,575 of 4,296 routines read as reachable from no way
in. Tom's decision that day: walks cross into every body, **by dispatch**, and the map
never draws it as an edge.

**So this is `resolve/ipc.py`'s shape, not `supplied.py`'s.** The answer is a second fact
beside the call graph (`dispatch_links`), which every recursive walk in `store.py` crosses
as an arm of its own, and which no `calls.callee_id` ever holds (rule 2). A link says *may
run*, and every surface that shows one says so.

**It is not inference** (design rule 28). Each body was named by a checker that resolved
the call, by location, exactly as a supplied edge's one target is. Nothing here matches a
name, so *"Inferred facts: none"* stays true of a map that has these.

**Located as an edge's target is, by the same index** (`supplied._index`): an exact first
line, else the innermost routine whose span holds the line, and the name checked either
way. A body that lands on nothing, or on a routine of another name, is counted and not
linked (rule 1), and the counts ride out on `DispatchStats` for the run to say.

**This module names no language.** It reads `supplied_edges.answers`, which any reader may
fill; Java's is the first that does (`plugins/java/.../Edges.java`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..store import Store
from .supplied import _containing, _index, _Routines

HOW = "by dispatch"


@dataclass(slots=True)
class DispatchStats:
    """What the linker found: per language, sites linked and bodies they may reach."""

    sites: dict[str, int] = field(default_factory=dict)
    bodies: dict[str, int] = field(default_factory=dict)
    missed: dict[str, int] = field(default_factory=dict)

    def sentence(self) -> str:
        """*java dispatch: 284 calls may reach 1,930 bodies, crossed by every walk.*"""
        parts = []
        for lang in sorted(self.sites):
            said = (f"{lang} dispatch: {self.sites[lang]:,} calls may reach "
                    f"{self.bodies[lang]:,} bodies, crossed by every walk and never drawn "
                    f"as an edge")
            if self.missed.get(lang):
                said += f" ({self.missed[lang]:,} named a place this map holds no such routine)"
            parts.append(said)
        return "; ".join(parts)


def resolve_dispatch(store: Store) -> DispatchStats:
    """Replace `dispatch_links` whole, from what every reader said about its `dynamic` calls."""
    stats = DispatchStats()
    store.conn.execute("DELETE FROM dispatch_links")
    langs = [str(r["lang"]) for r in store.query(
        "SELECT DISTINCT lang FROM supplied_edges"
        " WHERE reason = 'dynamic' AND answers != '[]' ORDER BY lang")]
    rows: list[tuple[str, str, str, str]] = []
    for lang in langs:
        ix = _index(store, lang)
        sites = 0
        bodies = 0
        missed = 0
        for r in store.query(
            "SELECT site_id, caller_id, answers FROM supplied_edges"
            " WHERE lang = ? AND reason = 'dynamic' AND answers != '[]'"
            " ORDER BY site_id", (lang,),
        ):
            linked = 0
            seen: set[str] = set()
            for file, line, name in json.loads(r["answers"]):
                hit = _locate(ix, str(file), int(line), str(name))
                if hit is None:
                    missed += 1
                    continue
                if hit in seen:
                    continue
                seen.add(hit)
                rows.append((r["site_id"], r["caller_id"], hit, HOW))
                linked += 1
            if linked:
                sites += 1
                bodies += linked
        if sites or missed:
            stats.sites[lang] = sites
            stats.bodies[lang] = bodies
            stats.missed[lang] = missed
    with store.batch():
        store.conn.executemany(
            "INSERT INTO dispatch_links(site_id, caller_id, routine_id, how)"
            " VALUES(?,?,?,?)", rows)
    return stats


def _locate(ix: _Routines, file: str, line: int, name: str) -> str | None:
    """The routine an answer names, by `supplied.resolve`'s rule, or nothing."""
    exact = ix.first.get((file, line))
    if exact is not None:
        named = [rid for rid, n in exact if n == name]
        return named[0] if len(named) == 1 else None
    hit = _containing(ix, file, line)
    if hit is None or hit[1] != name:
        return None
    return hit[0]
