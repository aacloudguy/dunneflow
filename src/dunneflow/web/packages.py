"""The package overview: the program at orientation altitude.

One of two layouts inside graph mode, and deliberately not a replacement for the other.
The 2.5D stack holds ten thousand nodes and answers *what is in here*; this holds forty-odd
boxes and answers *what is this shaped like*. `HANDOFF.md` settled that both exist and that
the package graph "is not the endpoint" -- it is the picture you can take in at a glance,
and it stops being readable long before the program does.

**Nothing here is hand-placed.** The ratified design drew this with `x` and `y` written
into a JavaScript array, which is exactly right for settling a design and exactly wrong for
shipping one: pointed at a real store, the same code drew forty-seven rectangles at
`x="undefined"`.

**Counted from the store, never from the drawn model.** The 2.5D model stores every
crossing twice, once per plate, each copy ending in a shadow (rule 23). Aggregating those
would double every weight here, silently and plausibly -- the numbers would still look
like numbers. The store holds each call exactly once.
"""

from __future__ import annotations

from typing import Any

from ..store import Store
from . import queries
from .graph import pkg_params, root_package

# The box, in the same units the client's viewBox uses. Sized for a package name and a
# one-line subtitle at the scale the ratified design settled on.
BOX_W = 190.0
BOX_H = 46.0
COL_GAP = 66.0
ROW_GAP = 22.0
MARGIN = 30.0

# A rank deeper than this wraps into adjacent sub-columns rather than growing a taller
# strip. Twelve is what fits a laptop screen beside the header and the filter strip, which
# is the whole claim this view makes: you can see it at once.
MAX_ROWS = 12
# Sub-columns of one rank sit closer than ranks do, so the eye still groups them.
SUB_GAP = 24.0

# Externals sit beyond the system boundary line, with a gap wide enough that the line reads
# as a division rather than as another column separator.
BOUNDARY_GAP = 90.0


def build(store: Store, root: str | None = None) -> dict[str, Any]:
    """The overview: packages, externals, what passes between them, and where each sits.

    The root is taken from `graph.py` rather than recomputed. Two definitions of "which
    package is this in" would let the overview and the stack disagree about the same
    program, which is the kind of difference nobody notices until they are comparing two
    numbers that were never the same measurement.
    """
    root = root_package(store) if root is None else root
    params = pkg_params(root)

    sizes: dict[str, int] = {}
    for r in store.query(queries.PACKAGE_SIZES, params):
        sizes[str(r["pkg"])] = int(r["n"])

    entries = {str(r["pkg"]) for r in store.query(queries.PACKAGE_ENTRYPOINTS, params)}

    edges: list[dict[str, Any]] = []
    for r in store.query(queries.PACKAGE_EDGES, params):
        src, dst = str(r["src"]), str(r["dst"])
        if src not in sizes or dst not in sizes:
            continue
        edges.append({
            "src": src, "dst": dst, "weight": int(r["weight"]),
            # Rule 6: never blurred. We are certain the two packages are connected when any
            # one call between them is certain, whatever could not be resolved about the
            # rest; INFERRED only when every constituent call was inferred.
            "confidence": "CERTAIN" if int(r["any_certain"]) else "INFERRED",
        })

    externals: dict[str, dict[str, Any]] = {}
    ext_edges: list[dict[str, Any]] = []
    for r in store.query(queries.PACKAGE_BOUNDARY_EDGES, params):
        src, kind = str(r["src"]), str(r["dst"])
        if src not in sizes:
            continue
        e = externals.setdefault(kind, {"id": kind, "kind": kind, "hits": 0, "targets": 0})
        e["hits"] += int(r["weight"])
        e["targets"] += int(r["targets"])
        ext_edges.append({"src": src, "dst": kind, "weight": int(r["weight"])})

    # The commonest destination is what makes a boundary kind mean something: "DATABASE"
    # is a category, "DATABASE · vestiarium.db" is a fact about this program.
    for r in store.query(queries.COVER_BOUNDARIES):
        known = externals.get(str(r["kind"]))
        if known is not None:
            known["detail"] = str(r["common"] or "")
            # **The cover's count, not a sum over the packages drawn here.** A box said
            # NETWORK 2 where the cover said 3, because a touch from a routine outside every
            # drawn package was dropped from one and not the other (BACKLOG 18).
            known["hits"] = int(r["n"])
    for known in externals.values():
        known["targets"] = 0
    for r in store.query(queries.BOUNDARY_KIND_TARGETS):
        known = externals.get(str(r["kind"]))
        if known is not None:
            known["targets"] = int(r["targets"])

    ranks = _rank(sizes, entries, edges)
    nodes = _place(sizes, entries, ranks)
    width, height = _extent(nodes, externals)
    _place_externals(externals, width)

    return {
        "packages": nodes,
        "externals": list(externals.values()),
        "edges": edges,
        "ext_edges": ext_edges,
        "boundary_x": width + BOUNDARY_GAP / 2 if externals else None,
        "width": width + (BOUNDARY_GAP + BOX_W + MARGIN if externals else MARGIN),
        "height": height,
        "box": {"w": BOX_W, "h": BOX_H},
    }


def _rank(sizes: dict[str, int], entries: set[str],
          edges: list[dict[str, Any]]) -> dict[str, int]:
    """How many hops from a way in -- which is the reader's own order.

    A program is its entrypoints, so the leftmost column is where you start and each column
    after it is one call deeper. A package nothing reaches gets the last column rather than
    being dropped: unreachable is a finding, not a reason to hide it.
    """
    out: dict[str, list[str]] = {}
    for e in edges:
        out.setdefault(e["src"], []).append(e["dst"])

    rank = {p: 0 for p in entries if p in sizes}
    if not rank:
        # No entrypoint resolves to a package -- rank from the busiest instead, and the
        # picture is still true, just not rooted where a reader would start.
        busiest = max(sizes, key=lambda p: sizes[p], default=None)
        if busiest is not None:
            rank[busiest] = 0

    frontier = list(rank)
    while frontier:
        nxt = []
        for p in frontier:
            for q in out.get(p, ()):
                if q not in rank:
                    rank[q] = rank[p] + 1
                    nxt.append(q)
        frontier = nxt

    unreached = max(rank.values(), default=0) + 1
    for p in sizes:
        rank.setdefault(p, unreached)
    return rank


def _place(sizes: dict[str, int], entries: set[str],
           ranks: dict[str, int]) -> list[dict[str, Any]]:
    """One column per rank, biggest first down each column, wrapped when a rank is deep.

    Wrapping is the point of this view rather than a nicety. Lictores has forty-seven
    packages over four ranks, and one rank holds thirty of them -- stacked in a single
    column that is a two-thousand-pixel strip, which is a list with boxes round it and not
    a picture. Rule 8 says a bounded thing is only allowed where the whole content sits
    beside it; wrapping bounds nothing and drops nothing, it just stops the drawing being
    taller than any screen. A wrapped rank stays one rank: the sub-columns sit adjacent and
    the reader still reads left to right as depth.
    """
    columns: dict[int, list[str]] = {}
    for pkg, r in ranks.items():
        columns.setdefault(r, []).append(pkg)

    nodes: list[dict[str, Any]] = []
    col_x = MARGIN
    for rank in sorted(columns):
        members = sorted(columns[rank], key=lambda p: (-sizes.get(p, 0), p))
        # Spread evenly rather than filling the first sub-column to the brim: three columns
        # of ten read as one group, while ten-ten-two reads as an afterthought.
        subs = max(1, -(-len(members) // MAX_ROWS))
        per = -(-len(members) // subs)
        for i, pkg in enumerate(members):
            sub, row = divmod(i, per)
            nodes.append({
                "id": pkg,
                "n": sizes.get(pkg, 0),
                "entry": pkg in entries,
                "rank": rank,
                "x": col_x + sub * (BOX_W + SUB_GAP),
                "y": MARGIN + row * (BOX_H + ROW_GAP),
            })
        col_x += subs * (BOX_W + SUB_GAP) - SUB_GAP + COL_GAP
    return nodes


def _extent(nodes: list[dict[str, Any]],
            externals: dict[str, dict[str, Any]]) -> tuple[float, float]:
    right = max((n["x"] + BOX_W for n in nodes), default=MARGIN)
    bottom = max((n["y"] + BOX_H for n in nodes), default=MARGIN)
    ext_bottom = MARGIN + max(len(externals), 1) * (BOX_H + ROW_GAP)
    return right, max(bottom, ext_bottom) + MARGIN


def _place_externals(externals: dict[str, dict[str, Any]], width: float) -> None:
    """Beyond the boundary line, busiest first. Design rule 8: they are first-class nodes."""
    x = width + BOUNDARY_GAP
    for row, e in enumerate(sorted(externals.values(), key=lambda v: -int(v["hits"]))):
        e["x"] = x
        e["y"] = MARGIN + row * (BOX_H + ROW_GAP)
        e.setdefault("detail", "")
