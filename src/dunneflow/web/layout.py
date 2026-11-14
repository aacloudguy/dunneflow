"""Where things sit on a disk, and where the disks sit in the stack.

Two layouts, because design rule 2 says that when two options are genuinely
interchangeable you build both and let real use retire the loser:

* **structural** -- deterministic placement from the program's own structure. Instant,
  stable, and never a hairball. Computed here, and the default.
* **force** -- Fruchterman--Reingold per plate, **coupled through the shadows**, solved in
  the browser. Reveals clusters the module tree does not. Computed in
  `static/forcelayout.js`, not here.

**Coupled, and that is the half this module's own description of a shadow always implied.**
`graph.py` calls a shadow *"a proxy at its own position on this disk, taking part in this
disk's forces like any other node"*, and rule 23 says the model stores every crossing twice
*"which is exactly what lets both plates lay out under the same forces"*. Solved plate by
plate, nothing ever asked them to: a shadow pulled its borrowing plate and the plate never
pulled back, so a shadow sat 0.678 plate-radii from the node it stood for against 0.907 for
two random points in a disc. Now every slot standing for one entity is pulled toward their
common middle, so a plate's arrangement is answerable to what the other plates want, and a
connection that leaves a plate more often goes straight up.

**Coupling needs one coordinate frame, and that is the whole of why it works.** Normalising
each plate onto its own middle at its own radius undoes the pull *after* the solve: two slots
left in exactly the same place are moved apart again by two different translations and two
different scales. Pulling harder cannot reach past it -- snapping every slot onto its group's
mean every single iteration still left only 20 of 5,101 crossings upright. So the whole stack
is normalised once, and a plate then sits where its own contents put it rather than on the
axis. Measured: 0.015 plate-widths off axis at the median, 0.127 at worst. The plate's circle
is **reported** by the layout and read by everything drawn on it, because a middle that used
to be zero for every plate is now three expressions built on a constant that has stopped
being true (rule 51).

**What is left over is the measurement.** A crossing that stays diagonal is one two plates
each want somewhere different, and no arrangement satisfies both -- the worst-aligned entity
on Lictores has *two* shadows, not thirty-nine, so it is tension rather than fan-out. The
count is stated above the picture and the per-node case on the hover card. Numbers, and the
trade against within-plate crossings, in `PERFORMANCE.md`.

**A skewer is not drawn, and could be.** With one frame every entity's slots co-locate
exactly -- all 4,050 of them, to a spread of zero -- so a routine and its stand-ins hold one
position through every plate they appear on. Nothing shows it: what is drawn is the crossing
between two *different* entities, and a spring embedder holds those apart at its own natural
length, so a crossing approaches vertical and never reaches it. The line that would be the
skewer is the transposition, real node to its own stand-in, and rule 23 removed it.

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
it holds tightly: measured over Lictores, the two backends land every plate within 0.07%
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
# Lictores 25 of 53 plates hold under a hundred things and every one of them wasted the
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


# The tightest pair on a phyllotaxis disk of `n` points, as a multiple of `radius / sqrt(n)`.
#
# **Measured, not derived, and it is a constant to four figures**: 1.5460 at n = 6, 9, 12,
# 26, 58, 151, 475, 991 and 4,000. That is what makes node separation a *law* here rather
# than a tuning -- a plate of any size knows exactly how close its two closest dots are, so
# a radius can be chosen that never overlaps instead of one that usually does not.
#
# It is the **minimum** rather than the median (1.69), because a guarantee taken on the
# typical pair is not a guarantee. `test_layout_spacing.py` re-measures it, so a change to the
# placement that moved it could not pass silently.
PHYLLOTAXIS_TIGHTEST = 1.546


def phyllotaxis(index: int, total: int, radius: float = DISK_RADIUS,
                turn: float = 0.0, alone_at_centre: bool = True) -> tuple[float, float]:
    """Even placement of `total` points on a disk, deterministic in `index`.

    `sqrt` spacing keeps area per point constant, so the centre does not clot.

    `turn` rotates the whole spiral. It exists so two sets of points can share a disk
    without sharing a spiral -- see `structural`, where the drawn nodes and the shadows are
    placed separately and must not land on each other.

    **`alone_at_centre` is the one case a rotation cannot separate**, and a test found it
    rather than a review: at the origin every angle is the same point, so a plate holding
    one drawn node and one shadow put both of them there. The centre belongs to the drawn
    nodes -- it is where the eye lands and a shadow is never drawn -- so the shadow spiral
    declines it and a lone shadow takes the ordinary formula's answer instead. Every other
    count already avoids the origin, because the radial term is `index + 0.5`.
    """
    if total <= 1 and alone_at_centre:
        return (0.0, 0.0)
    if total <= 0:
        return (0.0, 0.0)
    r = radius * math.sqrt((index + 0.5) / total)
    theta = index * GOLDEN_ANGLE + turn
    return (r * math.cos(theta), r * math.sin(theta))


def structural(model: GraphModel) -> dict[tuple[str, str], tuple[float, float, float]]:
    """Place every drawn thing: real nodes and shadows alike.

    Keyed `(node_id, disk)` because one entity holds a position per disk it appears on --
    its real one, and one for every disk that shadows it.

    **Two spirals per disk, not one, and the drawn nodes get their own.** This placed real
    nodes and shadows in a single spiral ordered by degree, which sounds even and is not:
    the two kinds segregate by degree, so the drawn nodes come out in contiguous runs and
    inherit the spacing of *all* the placed points rather than their own. Measured on
    Comitia, `ext:<small outside>` drew its six nodes from slots 0-2 and 32-34 of 42 -- two
    blobs, not six dots -- and `ext:FILE` drew 151 in one unbroken block of 788. A plate
    sized for what it draws and packed with five times that many points cannot separate its
    dots at any node size, which is the whole of why they overlapped.

    **A shadow has no claim on the plate's area budget**, because it is a device for the
    third dimension rather than something drawn here (rule 23) -- its slot is empty screen
    space. It still needs *a* position: it takes part in its plate's forces, and a crossing
    has to meet the plate somewhere. So it gets a spiral of its own, rotated half a turn out
    of phase, and the drawn nodes get a spiral of exactly their own number. `n` drawn nodes
    on a disk of radius `R` then sit exactly `PHYLLOTAXIS_TIGHTEST * R / sqrt(n)` apart at
    their closest, which is what lets the renderer choose a radius that never overlaps.

    Within a disk, nodes are ordered by degree so that the busiest sit nearest the middle.
    That ordering is the only structure this layout imposes, and it is enough to make a
    plate readable **as dots**: what a package mostly does ends up where the eye lands first.
    Shadows are ordered by id instead -- their order is not a claim about anything, and
    sorting them by degree is what used to interleave them into the drawn nodes' spacing.

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

    drawn: dict[str, list[str]] = {}
    shades: dict[str, list[str]] = {}
    for n in model.nodes:
        drawn.setdefault(n.disk, []).append(n.id)
    for s in model.shadows:
        shades.setdefault(s.disk, []).append(s.node_id)

    z_of = disk_heights(model)
    out: dict[tuple[str, str], tuple[float, float, float]] = {}
    # Sorted, and not merely for tidiness: a set of strings iterates in an order that
    # depends on the interpreter's hash seed, so building the map from one would vary run to
    # run. This module's promise is that the same graph gives the same map on every machine.
    for disk in sorted(set(drawn) | set(shades)):
        z = z_of.get(disk, 0.0)
        here = drawn.get(disk, [])
        # Busiest first, then by id so the arrangement never depends on row order.
        here.sort(key=lambda i: (-degree.get((i, disk), 0), i))
        for i, node_id in enumerate(here):
            x, y = phyllotaxis(i, len(here))
            out[(node_id, disk)] = (x, y, z)
        ghosts = sorted(shades.get(disk, []))
        for j, node_id in enumerate(ghosts):
            x, y = phyllotaxis(j, len(ghosts), turn=math.pi, alone_at_centre=False)
            out[(node_id, disk)] = (x, y, z)
    return out


def disk_heights(model: GraphModel) -> dict[str, float]:
    """Where each plate sits in the stack.

    Externals go underneath the code that reaches them, in one band, so the stack reads
    top-down as *the program, then what it touches*. Within each band, the order is by
    size, biggest first from the top: the biggest package plate is the top of the stack,
    and the biggest external plate sits directly under the code.

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
