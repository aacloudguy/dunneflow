"""Where things sit on a disk, and where the disks sit in the stack.

Two layouts, because design rule 2 says that when two options are genuinely
interchangeable you build both and let real use retire the loser:

* **structural** -- deterministic placement from the program's own structure. Instant,
  stable, and never a hairball. Computed here, and the default.
* **force** -- Fruchterman--Reingold per plate, solved in the browser. Reveals clusters
  the module tree does not. Computed in `static/forcelayout.js`, not here.

Structural is the one that exists first because it is also the *initial state* force
needs: from a good starting arrangement it converges far faster than from noise, and a
seeded start is what makes the result reproducible rather than a different picture every
run. The spiral is that seed, and it is also why the solver needs no random number
generator at all -- from a phyllotaxis start no two nodes ever coincide, so the
degenerate-overlap branch never fires. Measured: changing the seed changes nothing.

**Force is solved on the reader's machine, and this was written the other way round.** It
said "refined in a browser worker and posted back to be stored", and neither half survived
contact. `serve` opens every store `writable=False` (rule 20), so the serving process
cannot store what a worker posts; and at 89 ms on a GPU there is nothing to amortise, so
`queries.py`'s drafted `layout` table stays drafted. What ships is a WebGPU compute shader
with a web-worker fallback for machines without one -- 89 ms against 9.7 s, the same
algorithm both ways.

Nothing *here* uses a random number generator, and the same graph produces the same map on
every machine and every run. **Force keeps the second half of that promise and not the
first**, and the difference is worth stating rather than glossing: each backend is
bit-identical run to run, but a GPU and a CPU arrive at two different arrangements of
equal quality. WGSL may fuse a multiply-add where the source says two operations, and a
force layout is chaotic enough that one last-bit difference is a visibly different picture
a hundred iterations later -- this was tried, with every JS operation forced through
`Math.fround`, and 1.15% of coordinates matched. So what is asserted is equivalence, and
it holds tightly: measured over Mensores, the two backends land every plate within 0.07%
of the same radius and cut edge crossings by the same 91.7%. The page says which one drew
it (design rule 1).
"""

from __future__ import annotations

import math

from .graph import GraphModel

# Golden angle. Successive points at this angle from the centre never line up into
# spokes, which is why a sunflower packs evenly; any rational fraction of a turn does.
GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))

# One disk's radius in world units, and the width of the *widest* plate rather than of
# every plate.
#
# This said that disks are drawn the same size regardless of how much they hold, so a plate
# with 900 nodes and one with 30 read as the same kind of object and density carries the
# information rather than area. **That was tried and it is the wrong way round**, and the
# note is rewritten rather than left standing beside code that contradicts it. At one width
# a plate of 991 and a plate of 6 are a solid mass and a sparse ring, so a reader has to
# compare two textures to learn a number the picture could simply have shown them; on
# Mensores 25 of 53 plates hold under a hundred things and every one of them wasted the
# full footprint of the largest. Area says it, and it is the channel that was going spare.
#
# The sizing itself is **not here**, and that is deliberate. `phyllotaxis` is radially
# uniform, so scaling a plate's placed coordinates by a factor is exactly computing it at a
# smaller radius -- which makes plate width a *view* property like Z and the spreads,
# owned by the renderer, reversible from an unscaled base, and settable without asking the
# server for a second payload. See `applyLayout` in `static/graph.js`, and `plateSize` in
# `static/settings.js` for the strength the reader sets. What is computed here is the
# arrangement every width is a multiple of.
DISK_RADIUS = 1000.0

# Vertical gap between plates. Deliberately small against `DISK_RADIUS`: fifty-one plates
# at half the disk radius apart is a tower ten times taller than it is wide, which reads
# as a column rather than a deck and cannot be framed without losing all detail. At this
# spacing the stack reads the way it is meant to -- cards, slightly fanned.
DISK_GAP = 190.0


def phyllotaxis(index: int, total: int, radius: float = DISK_RADIUS) -> tuple[float, float]:
    """Even placement of `total` points on a disk, deterministic in `index`.

    `sqrt` spacing keeps area per point constant, so the centre does not clot.
    """
    if total <= 1:
        return (0.0, 0.0)
    r = radius * math.sqrt((index + 0.5) / total)
    theta = index * GOLDEN_ANGLE
    return (r * math.cos(theta), r * math.sin(theta))


def structural(model: GraphModel) -> dict[tuple[str, str], tuple[float, float, float]]:
    """Place every drawn thing: real nodes and shadows alike.

    Keyed `(node_id, disk)` because one entity holds a position per disk it appears on --
    its real one, and one for every disk that shadows it.

    Within a disk, nodes are ordered by degree so that the busiest sit nearest the middle.
    That ordering is the only structure this layout imposes, and it is enough to make a
    plate readable **as dots**: what a package mostly does ends up where the eye lands first.

    **It is not enough to make a plate readable as a diagram, and that is now known rather
    than suspected.** A first attempt at the plate diagram drew a labelled box at each of
    these positions and left the placement alone. What came out was a field of names in a
    sunflower with every edge crossing every other, because nothing here ranks a node by
    what calls it -- a diagram's readability comes from its layout algorithm, not from the
    outline of its nodes. The view was withdrawn; see `setDiagram` in `static/shell.js`.

    A diagram wants a **layered** layout: ranks assigned by call direction, ordering within
    a rank chosen to reduce crossings, then coordinates. That is a second layout beside this
    one rather than a replacement, for the reason design rule 2 gives -- this one is right
    for ten thousand dots and would be wrong for eighty boxes, and the reverse.
    """
    degree: dict[tuple[str, str], int] = {}
    for e in model.edges:
        for end in (e.src, e.dst):
            key = (end, e.disk)
            degree[key] = degree.get(key, 0) + 1

    members: dict[str, list[tuple[str, bool]]] = {}
    for n in model.nodes:
        members.setdefault(n.disk, []).append((n.id, False))
    for s in model.shadows:
        members.setdefault(s.disk, []).append((s.node_id, True))

    z_of = disk_heights(model)
    out: dict[tuple[str, str], tuple[float, float, float]] = {}
    for disk, entries in members.items():
        # Busiest first, then by id so the arrangement never depends on row order.
        entries.sort(key=lambda e: (-degree.get((e[0], disk), 0), e[0]))
        z = z_of.get(disk, 0.0)
        for i, (node_id, _is_shadow) in enumerate(entries):
            x, y = phyllotaxis(i, len(entries))
            out[(node_id, disk)] = (x, y, z)
    return out


def disk_heights(model: GraphModel) -> dict[str, float]:
    """Where each plate sits in the stack.

    Externals go underneath the code that reaches them, in one band, so the stack reads
    top-down as *the program, then what it touches*. Within each band, the order is by
    size: the biggest plates near the middle of the stack, which keeps the silhouette
    from being top- or bottom-heavy when it is tilted.

    The order is only a default. Disks shuffle like cards, and the renderer owns that.
    """
    packages = [d for d in model.disks if d["kind"] == "package"]
    externals = [d for d in model.disks if d["kind"] == "external"]
    packages.sort(key=lambda d: (-int(d["nodes"]), str(d["id"])))
    externals.sort(key=lambda d: (-int(d["nodes"]), str(d["id"])))

    heights: dict[str, float] = {}
    for i, d in enumerate(packages):
        heights[str(d["id"])] = (len(packages) - i) * DISK_GAP
    for i, d in enumerate(externals):
        heights[str(d["id"])] = -(i + 1) * DISK_GAP
    return heights
