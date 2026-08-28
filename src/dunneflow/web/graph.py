"""The 2.5D model: a stack of disks, and the shadows that couple them.

Each disk is an ordinary 2D graph. Within a disk, nodes and edges behave exactly as they
would in any force-directed picture. When an edge leaves the disk, the far node appears
here as a **shadow** -- a proxy at its own position on this disk, taking part in this
disk's forces like any other node -- while the real node lives on its own disk. A
**transposition** line joins the two across Z.

This is what makes ten thousand nodes legible. A single plane holding all of Mensores is
a hairball at any zoom; the same graph cut into fifty-five disks is fifty-five pictures,
the largest of which holds 645 nodes. Decomposition, not filtering, is the fix -- and it
is the fix precisely because nothing is thrown away: every cross-disk edge is still drawn,
twice, and the reader can follow it.

One entity therefore holds a position *per disk it appears on*: its real one, plus one for
every disk that shadows it. `layout` is keyed `(node_id, disk)` for that reason.

Nothing here talks to a renderer. It emits plain dictionaries; `serve.py` turns them into
JSON and the browser decides how to draw them.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..store import Store
from . import queries

# A disk holding fewer than this is merged into `<small>` rather than drawn as its own
# plate. Fifty-five disks is a stack; two hundred, most holding one node, is confetti --
# and a plate with one node on it tells the reader nothing that a list would not.
MIN_DISK = 8


@dataclass(slots=True)
class Node:
    """One thing in the program. `disk` is where its *real* copy lives."""

    id: str
    label: str
    kind: str
    disk: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Edge:
    """A connection, always drawn on exactly one disk.

    A cross-disk connection becomes two edges -- one on each disk, each ending in a
    shadow -- plus a transposition. It is never dropped, and never drawn as a line
    floating between plates with no endpoint.
    """

    src: str
    dst: str
    disk: str
    kind: str
    weight: int = 1
    confidence: str = ""


@dataclass(slots=True)
class Shadow:
    """A proxy for a node that really lives elsewhere.

    `node_id` is the real node; `disk` is the disk borrowing it. The pair is the identity,
    which is why a node can be shadowed on many disks without collision.
    """

    node_id: str
    disk: str


@dataclass(slots=True)
class GraphModel:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    shadows: list[Shadow] = field(default_factory=list)
    disks: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "nodes": [
                {"id": n.id, "label": n.label, "kind": n.kind, "disk": n.disk, **n.detail}
                for n in self.nodes
            ],
            "edges": [
                {"src": e.src, "dst": e.dst, "disk": e.disk, "kind": e.kind,
                 "weight": e.weight, "confidence": e.confidence}
                for e in self.edges
            ],
            "shadows": [{"node": s.node_id, "disk": s.disk} for s in self.shadows],
            "disks": self.disks,
            "stats": self.stats,
        }


def root_package(store: Store) -> str:
    """The program's own root package, taken from the data rather than assumed.

    `mensores.cli` and `dunneflow.cli` are both one dotted segment deep; hard-coding a
    prefix length would work on exactly one program.
    """
    rows = store.query(
        "SELECT module, COUNT(*) AS n FROM files"
        " WHERE module <> '' GROUP BY module ORDER BY n DESC"
    )
    roots: dict[str, int] = defaultdict(int)
    for r in rows:
        roots[str(r["module"]).split(".", 1)[0]] += int(r["n"])
    return max(roots.items(), key=lambda kv: kv[1])[0] if roots else ""


def pkg_params(root: str) -> dict[str, Any]:
    # `:cut` is 1-based and points just past "<root>." -- SQLite's substr is 1-indexed.
    return {"root": root, "root_dot": f"{root}.%", "cut": len(root) + 2}


def build(store: Store, *, include_constants: bool = True) -> GraphModel:
    """Assemble the whole stack from the fact store."""
    root = root_package(store)
    params = pkg_params(root)
    m = GraphModel()
    disk_of: dict[str, str] = {}

    def add(node: Node) -> None:
        m.nodes.append(node)
        disk_of[node.id] = node.disk

    for r in store.query(queries.ROUTINE_NODES, params):
        add(Node(
            id=str(r["id"]), label=str(r["label"]), kind="ROUTINE",
            disk=f"pkg:{r['pkg']}",
            detail={"qualname": r["qualname"], "module": r["module"], "file": r["file"],
                    "line": r["line"], "visibility": r["visibility"],
                    "is_async": bool(r["is_async"]), "class_name": r["class_name"]},
        ))

    for r in store.query(queries.STRUCTURE_NODES, params):
        add(Node(
            id=str(r["id"]), label=str(r["label"]), kind="STRUCTURE",
            disk=f"pkg:{r['pkg']}",
            detail={"struct_kind": r["struct_kind"], "module": r["module"],
                    "file": r["file"], "line": r["line"]},
        ))

    if include_constants:
        for r in store.query(queries.CONSTANT_NODES, params):
            add(Node(
                id=str(r["id"]), label=str(r["label"]), kind="CONSTANT",
                disk=f"pkg:{r['pkg']}",
                detail={"module": r["module"], "file": r["file"], "line": r["line"],
                        "private": bool(r["private"])},
            ))

    # Externals. Design rule 8: a program is never alone, and what leaves it is a
    # first-class node rather than an edge trailing off the side of the picture.
    for r in store.query(queries.BOUNDARY_NODES):
        add(Node(
            id=str(r["id"]), label=str(r["label"]), kind="BOUNDARY",
            disk=f"ext:{r['bkind']}",
            detail={"bkind": r["bkind"], "hits": r["hits"], "callers": r["callers"],
                    "direction": r["direction"], "source_status": "OPAQUE"},
        ))
    for r in store.query(queries.UNNAMED_BOUNDARY_NODES):
        add(Node(
            id=str(r["id"]), label=f"({r['bkind']}, unnamed)", kind="BOUNDARY",
            disk=f"ext:{r['bkind']}",
            detail={"bkind": r["bkind"], "hits": r["hits"], "callers": r["callers"],
                    "unnamed": True, "source_status": "OPAQUE"},
        ))

    # Files the program names. Their own plate rather than folded into FILE: a boundary
    # touch is the program *using* a file, and an artefact is the program *naming* one.
    # Reading them as the same thing would put a word the program chose beside a call it
    # made, and rule 17 exists because those names are vocabulary.
    for r in store.query(queries.ARTEFACT_NODES):
        add(Node(
            id=str(r["id"]), label=str(r["label"]), kind="ARTEFACT",
            disk="ext:ARTEFACT",
            detail={"ext": r["ext"], "akind": r["akind"], "mentions": r["mentions"],
                    "namers": r["namers"], "source_status": "OPAQUE"},
        ))

    _fold_small_disks(m, disk_of)
    _add_edges(store, m, disk_of)
    _summarise_disks(m)
    return m


def _fold_small_disks(m: GraphModel, disk_of: dict[str, str]) -> None:
    """Merge disks too small to be worth a plate, and say how many were merged.

    Not a silent filter (design rule 1): the merged disk is drawn and named, and its
    members keep their own `home` so the inspector can still say where a thing really
    lives.
    """
    counts: dict[str, int] = defaultdict(int)
    for d in disk_of.values():
        counts[d] += 1
    small = {d for d, n in counts.items() if n < MIN_DISK}
    if not small:
        return
    for node in m.nodes:
        if node.disk in small:
            node.detail["home"] = node.disk
            node.disk = "pkg:<small>"
            disk_of[node.id] = node.disk
    m.stats["disks_merged"] = len(small)


def _add_edges(store: Store, m: GraphModel, disk_of: dict[str, str]) -> None:
    """Place every edge on a disk, creating shadows where one crosses.

    An edge whose endpoint is not a node -- a call resolved to something outside the
    program, a boundary on a routine that was never extracted -- is counted and dropped
    here rather than drawn to nowhere. The count is reported; a vanished edge that
    nobody counts is the silent filter rule 1 forbids.
    """
    shadow_set: set[tuple[str, str]] = set()
    dangling = 0

    def place(src: str, dst: str, kind: str, weight: int, confidence: str) -> None:
        nonlocal dangling
        ds, dd = disk_of.get(src), disk_of.get(dst)
        if ds is None or dd is None:
            dangling += 1
            return
        if ds == dd:
            m.edges.append(Edge(src, dst, ds, kind, weight, confidence))
            return
        # Crosses. Draw it on both disks, each time ending in a shadow, so each disk's
        # layout feels the pull and the reader can follow the thread from either side.
        m.edges.append(Edge(src, dst, ds, kind, weight, confidence))
        m.edges.append(Edge(src, dst, dd, kind, weight, confidence))
        shadow_set.add((dst, ds))
        shadow_set.add((src, dd))

    for r in store.query(queries.CALL_EDGES):
        place(str(r["src"]), str(r["dst"]), "CALL", int(r["weight"]),
              str(r["confidence"] or ""))
    for r in store.query(queries.BOUNDARY_EDGES):
        place(str(r["src"]), str(r["dst"]), "TOUCH", int(r["weight"]), "")
    for r in store.query(queries.ARTEFACT_EDGES):
        place(str(r["src"]), str(r["dst"]), "NAMES", int(r["weight"]), "")

    m.shadows = [Shadow(n, d) for n, d in sorted(shadow_set)]
    m.stats["dangling_edges"] = dangling


def _summarise_disks(m: GraphModel) -> None:
    """One row per plate: what it holds, so the stack can be listed as well as drawn."""
    real: dict[str, int] = defaultdict(int)
    for n in m.nodes:
        real[n.disk] += 1
    shadowed: dict[str, int] = defaultdict(int)
    for s in m.shadows:
        shadowed[s.disk] += 1
    edges: dict[str, int] = defaultdict(int)
    for e in m.edges:
        edges[e.disk] += 1

    for disk in sorted(set(real) | set(shadowed)):
        kind, _, name = disk.partition(":")
        m.disks.append({
            "id": disk,
            "name": name,
            "kind": "external" if kind == "ext" else "package",
            "nodes": real[disk],
            "shadows": shadowed[disk],
            "edges": edges[disk],
        })

    m.stats.update({
        "nodes": len(m.nodes),
        "edges": len(m.edges),
        "shadows": len(m.shadows),
        "disks": len(m.disks),
        "largest_disk": max(real.values()) if real else 0,
        # What the renderer actually instances: a shadow is drawn too.
        "drawn_nodes": len(m.nodes) + len(m.shadows),
    })
