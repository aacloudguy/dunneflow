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

# How much detail the stack is drawn at. `routine` is every thing the program declares;
# `module` folds each file into one node and each boundary kind into one, which is the
# altitude at which a plate is a readable number of boxes rather than a field of dots.
#
# It is a *second way to look at the same facts*, never a filter: nothing is dropped, and
# every node says how many things it stands for. The two are one model built twice, so
# `layout.structural()`, `phyllotaxis`, `disk_heights` and every line of the renderer work
# on either without knowing which one they were handed.
LEVELS = ("routine", "module")

# A disk holding fewer than this is merged into `<small>` rather than drawn as its own
# plate. Fifty-five disks is a stack; two hundred, most holding one node, is confetti --
# and a plate with one node on it tells the reader nothing that a list would not.
#
# **What a plate holds changes with the level, so the threshold does too.** 8 is right for
# routines and wrong for modules: applied at module level on Mensores it folds 21 of the 45
# packages away, because a package with six modules is a real package while a package with
# six routines is not much of a plate. These are the defaults; the reader owns the value
# (design rule 2), and the count of what it merged is always stated.
MIN_DISK_BY_LEVEL = {"routine": 8, "module": 3}

# What the reader may set it to. 1 draws every package, however little it holds -- that is
# confetti, and it is theirs to choose. The ceiling is not a safety rail: a threshold high
# enough to merge everything leaves one plate, which is a legitimate thing to want to see
# and states the 52 it merged. It is here so a hand-typed query string cannot ask for a
# number no program could ever reach.
MIN_DISK_FLOOR = 1
MIN_DISK_CEILING = 64

# The plate every external node folds onto at module level. One word rather than "touches",
# because artefacts land here too and naming a file is not touching one -- the distinction
# the ARTEFACT plate exists to make, and rule 17's reason for making it.
OUTSIDE_DISK = "ext:<outside>"

# Where a plate too small to draw is merged to, per band. Two plates rather than one: see
# `_fold_small_disks`.
SMALL_DISK = {"pkg": "pkg:<small>", "ext": "ext:<small outside>"}


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
    # Which of `LEVELS` this model was built at. A field rather than a `stats` entry
    # because `stats` counts things and this names one; a string in a dict of counts is
    # rule 32's defect one layer down -- a number beside it that measures nothing.
    level: str = "routine"

    # **This model has one serialiser and it lives in `serve.py`.** A `to_json()` here
    # went with it for a while and nothing ever called it: `/api/graph` serves
    # `columnar(build(...))`, which is a different payload -- columnar rather than row,
    # edges as *indices* into the node arrays rather than ids, and carrying the positions,
    # the `real`/`shadow` flags and `edges_unplaced` that a page needs to draw anything.
    # Two serialisers of one model is rule 51 waiting to be paid: the unused one is what
    # the next caller reaches for, and it hands back a payload the page cannot draw with
    # no error anywhere, because both are valid JSON.


def root_package(store: Store) -> str:
    """The program's own root package, taken from the data rather than assumed.

    `mensores.cli` and `dunneflow.cli` are both one dotted segment deep; hard-coding a
    prefix length would work on exactly one program.

    **A root has to account for every file, and `""` is a real answer.** This used to
    return the *modal* first segment and could not fail. Analyse a directory that already
    **is** a package -- `src/dunneflow` rather than `src` -- and every module is one segment
    shallower, no segment is the root, and the biggest subpackage wins the vote: `web`,
    holding 20 of 63 files. `package_expr` then labels the other 43 files' routines
    `<external>`, and **750 of 752 routines are drawn as somebody else's code** on the
    largest plate in the picture, over a map that opens perfectly with every count on the
    cover correct.

    Rule 49 exactly -- a fallback that yields a plausible value has hidden the failure it
    was written for -- and it was found by Tom reading a map, not by any test. Measured over
    four maps, the tell is not marginal: a real root covers **628/628** and **63/63**, a
    wrong one covers **20/63** and **19/61**. So no threshold is needed and none is invented;
    a segment that leaves one file out is not the root of the tree that file is in.

    When there is no single root the tree itself is the root, and a module's package is its
    first segment -- which is what analysing the parent directory would have produced anyway.
    That is `package_expr`'s rootless branch, and it makes the two ways of pointing at one
    program agree instead of one of them lying.

    **The right test was already in the file.** `COVER_ROOT` asks the same question by
    *grouping* -- "one row means every module agrees and the segment is a root; more than one
    means the program has several top-level names and there is nothing to strip" -- and on the
    map that started this it counted **16 heads** and correctly answered *no root*, in the
    same process, off the same store, while this function elected `web`. Two answers to one
    question a hundred lines apart, and only the one nothing important depended on was right.
    They stay separate because they are genuinely different questions -- `COVER_ROOT` decides
    what prefix a narrow *field* may drop, a display decision -- but neither may be the only
    one that checks.
    """
    rows = store.query(
        "SELECT module, COUNT(*) AS n FROM files"
        " WHERE module <> '' GROUP BY module ORDER BY n DESC"
    )
    roots: dict[str, int] = defaultdict(int)
    total = 0
    for r in rows:
        n = int(r["n"])
        roots[str(r["module"]).split(".", 1)[0]] += n
        total += n
    if not roots:
        return ""
    root, held = max(roots.items(), key=lambda kv: kv[1])
    return root if held == total else ""


def pkg_params(root: str) -> dict[str, Any]:
    # `:cut` is 1-based and points just past "<root>." -- SQLite's substr is 1-indexed.
    # An empty root makes `root_dot` and `cut` meaningless rather than wrong: the rootless
    # branch in `package_expr` is chosen on `:root` alone and reads neither.
    return {"root": root, "root_dot": f"{root}.%", "cut": len(root) + 2}


def build(store: Store, *, include_constants: bool = True,
          level: str = "routine", min_disk: int | None = None) -> GraphModel:
    """Assemble the whole stack from the fact store, at the level asked for.

    The nodes are always emitted at routine level and then folded, because the fold is
    what has to be *known* -- a module node that cannot say it stands for 45 routines is a
    node the reader cannot account for (design rule 1). Edges are placed after the fold and
    are read from the store, never aggregated from the drawn model: the 2.5D model stores
    every crossing twice, once per plate (rule 23), so folding drawn edges would double
    every weight silently and plausibly. `packages.py` states the same thing for the same
    reason.
    """
    if level not in LEVELS:
        raise ValueError(f"unknown level {level!r}; expected one of {LEVELS}")
    if min_disk is None:
        min_disk = MIN_DISK_BY_LEVEL[level]
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
                    "is_async": bool(r["is_async"]), "class_name": r["class_name"],
                    **({"by_macro": r["by_macro"]} if r["by_macro"] else {})},
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

    fold = _fold_to_modules(m, disk_of) if level == "module" else None
    _fold_small_disks(m, disk_of, min_disk)
    _add_edges(store, m, disk_of, fold)
    _summarise_disks(m)
    m.stats["min_disk"] = min_disk
    m.level = level
    return m


def _fold_to_modules(m: GraphModel, disk_of: dict[str, str]) -> dict[str, str]:
    """One node per module, one per boundary kind: the stack at orientation altitude.

    Returns the map every edge is read through -- entity id to the node that now stands for
    it -- because the edges have not been placed yet and must be folded on the way in.

    Two rules decide what a thing folds into, and both come from what the reader is asking
    at this height. Anything the program *declares* folds into its **module**, since a
    routine, the constant beside it and the dataclass under it are all this file; the
    question here is which files talk to which. Anything **outside** the program folds into
    its kind and they all share one plate: 991 individual stdout strings and 408 SQL
    statements are 77% of the picture and none of them is the answer to "which modules touch
    the database".

    Every folded node states its own arithmetic in `holds` and `folded`, so nothing on
    screen is a number the reader cannot account for (design rule 1).
    """
    fold: dict[str, str] = {}
    merged: dict[str, Node] = {}
    order: list[str] = []

    for n in m.nodes:
        module = str(n.detail.get("module") or "")
        if module:
            # `mod:` joins `const:`, `bnd:` and `art:` -- `detail.classify()` reads the
            # prefix, so the id is what tells the inspector what it has been handed.
            fid = f"mod:{module}"
            label = module.rpartition(".")[2] or module
            disk = n.disk
            detail: dict[str, Any] = {"module": module, "file": n.detail.get("file", "")}
            kind = "MODULE"
        else:
            # The plate carries the kind, and the unnamed-boundary node is on it too, so
            # the kind is read from where the node sits rather than from a detail key that
            # only some of them have.
            bkind = n.disk.partition(":")[2]
            fid = f"outside:{bkind}"
            label = bkind
            disk = OUTSIDE_DISK
            detail = {"bkind": bkind, "source_status": "OPAQUE"}
            kind = n.kind

        fold[n.id] = fid
        node = merged.get(fid)
        if node is None:
            node = Node(id=fid, label=label, kind=kind, disk=disk, detail=detail)
            node.detail["holds"] = {}
            node.detail["folded"] = 0
            merged[fid] = node
            order.append(fid)
        # A module's file is the first non-empty one seen; a module is one file here, and
        # taking the first rather than asserting it keeps a partially extracted file from
        # blanking the whole node.
        if not node.detail.get("file") and n.detail.get("file"):
            node.detail["file"] = n.detail["file"]
        holds: dict[str, int] = node.detail["holds"]
        holds[n.kind] = holds.get(n.kind, 0) + 1
        node.detail["folded"] += 1

    m.stats["folded_from"] = len(m.nodes)
    m.nodes = [merged[fid] for fid in order]
    disk_of.clear()
    for node in m.nodes:
        disk_of[node.id] = node.disk
    return fold


def _fold_small_disks(m: GraphModel, disk_of: dict[str, str], min_disk: int) -> None:
    """Merge disks too small to be worth a plate, and say how many were merged.

    Not a silent filter (design rule 1): the merged disk is drawn and named, and its
    members keep their own `home` so the inspector can still say where a thing really
    lives. Both counts are stated -- how many plates went, and how many nodes moved --
    because a shorter stack and a smaller program look identical.

    **A plate is merged into its own band**, and that is a fix rather than a precaution.
    Everything used to land on `pkg:<small>`, which is a *package* plate -- so on Mensores
    the four QUEUE targets, the unnamed QUEUE touch and the one LLM_API endpoint have been
    drawn among the code that reaches them since the day `<small>` existed, above the
    boundary line, badged as ours. Design rule 8 says an external is a first-class node at
    the boundary; putting one on a package plate is a lie about where it lives, and nothing
    could see it because a merged plate is *supposed* to hold things from elsewhere.

    The two carry different names as well as different ids: two legend rows both reading
    `<small>` is one word for two plates, which is rule 32 in a list.
    """
    counts: dict[str, int] = defaultdict(int)
    for d in disk_of.values():
        counts[d] += 1
    small = {d for d, n in counts.items() if n < min_disk}
    moved = 0
    if small:
        for node in m.nodes:
            if node.disk in small:
                node.detail["home"] = node.disk
                node.disk = SMALL_DISK.get(node.disk.partition(":")[0], "pkg:<small>")
                disk_of[node.id] = node.disk
                moved += 1
    m.stats["disks_merged"] = len(small)
    m.stats["disks_merged_nodes"] = moved


def _add_edges(store: Store, m: GraphModel, disk_of: dict[str, str],
               fold: dict[str, str] | None = None) -> None:
    """Place every edge on a disk, creating shadows where one crosses.

    An edge whose endpoint is not a node -- a call resolved to something outside the
    program, a boundary on a routine that was never extracted -- is counted and dropped
    here rather than drawn to nowhere. The count is reported; a vanished edge that
    nobody counts is the silent filter rule 1 forbids.

    `fold` maps an entity to the node that stands for it, and is `None` where each entity
    stands for itself. Folding happens **here**, on the way in from the store, where every
    call, touch and naming is seen exactly once -- never over `m.edges`, which holds each
    crossing twice by design (rule 23).
    """
    shadow_set: set[tuple[str, str]] = set()
    dangling = 0
    inner = 0
    # (src, dst, kind) -> [weight, confidence]. Only used when folding: at routine level
    # each row is already one edge, and merging two rows that differ only in confidence
    # would quietly change a picture nothing asked to change.
    agg: dict[tuple[str, str, str], list[Any]] = {}

    def place(src: str, dst: str, kind: str, weight: int, confidence: str) -> None:
        nonlocal dangling, inner
        if fold is not None:
            a, b = fold.get(src), fold.get(dst)
            if a is None or b is None:
                dangling += 1
                return
            if a == b:
                # A module calling itself is not a connection between two things. Counted
                # rather than dropped, and never drawn as a line from a node to itself.
                inner += 1
                return
            key = (a, b, kind)
            prev = agg.get(key)
            if prev is None:
                agg[key] = [weight, confidence]
            else:
                prev[0] += weight
                # **The strongest constituent decides.** "This module calls that one" is
                # certain the moment one of the calls under it is, so blurring the two
                # would understate a claim the store can prove (rule 6).
                if confidence == "CERTAIN":
                    prev[1] = "CERTAIN"
            return
        emit(src, dst, kind, weight, confidence)

    def emit(src: str, dst: str, kind: str, weight: int, confidence: str) -> None:
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
    for r in store.query(queries.IPC_EDGES):
        place(str(r["src"]), str(r["dst"]), "IPC", int(r["weight"]), "INFERRED")

    # Sorted so the same store yields the same picture on every run -- the reason
    # `layout.py` uses no random number generator at all.
    for (a, b, kind), (weight, confidence) in sorted(agg.items()):
        emit(a, b, kind, int(weight), str(confidence))

    m.shadows = [Shadow(n, d) for n, d in sorted(shadow_set)]
    m.stats["dangling_edges"] = dangling
    m.stats["edges_within_node"] = inner


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
        # What the renderer **instances**, which is not what it draws. A shadow gets a
        # vertex so that picking, selection and search keep one index space with no
        # translation table between them -- and then a radius of zero and an alpha of
        # zero, because a shadow is never drawn (rule 23). The name is the buffer length,
        # not a claim about the picture; this comment said "a shadow is drawn too" and was
        # left standing when the rule landed.
        #
        # It is also the count the force layout moves: a shadow takes part in its plate's
        # forces like any other node, which is the reason it exists.
        "drawn_nodes": len(m.nodes) + len(m.shadows),
    })
