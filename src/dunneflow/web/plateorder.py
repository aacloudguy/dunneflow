"""Which order to stack the plates in, so a crossing does not have to travel far.

The stack orders plates by size -- `defaultOrder` in `graph.js`, packages above externals,
biggest nearest the middle. Nothing in that order knows what links to what, and on Comitia
**73.3% of the 5,101 cross-plate crossings span more than twenty plates**, which is a line
no reader can follow to its other end. The force layout made those crossings *upright*
(`forcelayout.js`); nothing had made them *short*.

## Why this is not the force solver, which is the first thing anyone will ask

Tom asked whether the same layout mechanism could minimise vertical distance and so choose
the order. The literal reading was built and measured first: plates as particles on a line,
springs weighted by how many links two plates share, relaxed and then ranked -- the force
solver one dimension over. It gives **-11.3%**.

The reason is that a spring relaxation minimises `sum(w * dz**2)` and the question is
`sum(w * abs(dz))`. Those have different answers, and worse, the continuous optimum is a
poor guide to the best *permutation*: the relaxed positions rank plates in an order that is
nearly the one you started with, because a plate linked in both directions settles near its
own middle whatever its neighbours do.

What works is searching the permutation directly -- weighted **minimum linear arrangement**,
which is NP-hard in general and trivial at 53 plates: **-82.8%**, mean crossing height 30.78
slots down to 5.31, and a third of all crossings landing on the plate next door against 4%
before. Same evidence as the force solver (the cross-plate edge list, which is the shadow
list rule 23 already maintains); different solver, and this docstring says so rather than
letting the next reader assume one mechanism does both.

## Where the crossings go

Measured on Lictores, routine level, 53 plates and 403 connected pairs:

| how far a crossing travels | by size | by what they link to |
|---|---|---|
| the plate next door        |   190 (3.7%)  | 1,724 (33.8%) |
| 2-3 plates                 |   388 (7.6%)  |   940 (18.4%) |
| 4-8                        |   326 (6.4%)  | 1,341 (26.3%) |
| 9-20                       |   459 (9.0%)  |   975 (19.1%) |
| **21 or more**             | **3,738 (73.3%)** | **121 (2.4%)** |

At module level (38 plates, 1,501 crossings) it is -74.1%, mean 20.56 -> 5.33.

## The grouped variant, and why both are built

The best order **interleaves boundary plates among the packages** -- `ext:DATABASE` just
above `storage`, `ext:STDIO` between `praeco` and `cli`. That reads well, and it also
overturns what the current default *means*: your code on top, the world below. Holding that
grouping costs most of the gain (-29.4% at routine level, -41.4% at module), so the two are
not interchangeable on the numbers -- they are interchangeable on what the reader wants to
see, which is design rule 2's case exactly. Both are built and the reader chooses.

## Determinism, because rule 66

An order the tool cannot defend is not an order. The search is **seeded from one stated
order** and takes the first strict improvement in a fixed traversal, so it is deterministic:
the same graph gives the same answer on every run, and two runs can be compared with each
other. It is *not* claimed to be optimal -- minimum linear arrangement is NP-hard and this
is a local search -- and the honest word for what it returns is the one used throughout:
better, by a stated amount, than the order it started from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .graph import GraphModel

# The bands the spread is reported in. Fixed and complete, so rule 8's bound never arises,
# and stated here rather than in the page because the sentence on screen has to be readable
# off the same computation that produced the number (rule 13).
BANDS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "the plate next door"),
    (2, 3, "2-3 plates away"),
    (4, 8, "4-8 plates away"),
    (9, 20, "9-20 plates away"),
    (21, 10 ** 9, "21 or more plates away"),
)


@dataclass(frozen=True, slots=True)
class Spread:
    """How far the crossings travel under one order. The measure, not the order."""

    total: int             # sum over crossings of how many slots each spans
    crossings: int         # the denominator, so the page never prints a bare count (rule 32)
    mean: float
    worst: int
    bands: tuple[tuple[str, int], ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "crossings": self.crossings,
            "mean": round(self.mean, 2),
            "worst": self.worst,
            "bands": [{"label": lbl, "count": n} for lbl, n in self.bands],
        }


def weights(model: GraphModel) -> dict[tuple[str, str], int]:
    """How many links join each pair of plates.

    **Each crossing counted once.** `model.edges` holds every cross-plate connection
    *twice* -- once on each plate, each copy ending in a shadow -- because that is what
    lets both plates lay out under the same forces (rule 23). Counting rows here would
    say every pair is twice as coupled as it is, which changes no ordering (the doubling
    is uniform) and makes every number printed beside it wrong (rule 32). So the dedupe is
    on the unordered `(src, dst)` pair, which is the connection's own identity.

    Edges within one plate are not crossings and are skipped: they cost no vertical
    distance whatever the order, so including them would add a constant to every candidate
    and slow the search down to say nothing.
    """
    disk_of = {n.id: n.disk for n in model.nodes}
    out: dict[tuple[str, str], int] = {}
    seen: set[tuple[str, str]] = set()
    for e in model.edges:
        a, b = disk_of.get(e.src), disk_of.get(e.dst)
        if a is None or b is None or a == b:
            continue
        conn = (e.src, e.dst) if e.src < e.dst else (e.dst, e.src)
        if conn in seen:
            continue
        seen.add(conn)
        pair = (a, b) if a < b else (b, a)
        out[pair] = out.get(pair, 0) + 1
    return out


def seed_order(model: GraphModel) -> list[str]:
    """The order the search starts from, which is the one the stack uses today.

    Kept identical to `defaultOrder` in `graph.js` -- packages above externals, biggest
    first -- for two reasons. It is what the reduction is *measured against*, so a
    percentage means something; and it is the one stated starting point that makes the
    result deterministic (rule 66). A seed chosen by hashing, or by whatever order the
    store happened to return, would give an answer nobody could reproduce.
    """
    pkg = [d for d in model.disks if d.get("kind") == "package"]
    ext = [d for d in model.disks if d.get("kind") != "package"]
    pkg.sort(key=lambda d: (-int(d.get("nodes", 0)), str(d["id"])))
    ext.sort(key=lambda d: (-int(d.get("nodes", 0)), str(d["id"])))
    return [str(d["id"]) for d in (*pkg, *ext)]


def travel(order: list[str], w: dict[tuple[str, str], int]) -> int:
    """Total vertical distance, in slots, summed over every crossing."""
    slot = {d: i for i, d in enumerate(order)}
    return sum(
        n * abs(slot[a] - slot[b])
        for (a, b), n in w.items()
        if a in slot and b in slot
    )


def spread(order: list[str], w: dict[tuple[str, str], int]) -> Spread:
    """The distribution, so what is claimed on screen is what was computed here."""
    slot = {d: i for i, d in enumerate(order)}
    counts: dict[int, int] = {}
    total = worst = crossings = 0
    for (a, b), n in w.items():
        if a not in slot or b not in slot:
            continue
        d = abs(slot[a] - slot[b])
        counts[d] = counts.get(d, 0) + n
        total += n * d
        crossings += n
        worst = max(worst, d)
    bands = tuple(
        (label, sum(n for d, n in counts.items() if lo <= d <= hi))
        for lo, hi, label in BANDS
    )
    return Spread(total=total, crossings=crossings,
                  mean=(total / crossings if crossings else 0.0),
                  worst=worst, bands=bands)


def _sweep(order: list[str], w: dict[tuple[str, str], int]) -> list[str]:
    """Move one plate to a better slot, over and over, until a whole pass finds none.

    Reinsertion rather than adjacent swaps: a plate whose neighbours are twenty slots away
    has to *travel* to be worth anything, and a swap can only move it one slot at a time
    past arrangements that are each individually worse. Measured, that is the whole
    difference between -11% and -83%.

    **First strict improvement in a fixed traversal**, not the best of the pass, and the
    reason is rule 66 rather than speed: taking the best move needs a tie-break when two
    moves score the same, and any tie-break invented here is an order the tool cannot
    defend. Taking the first one makes the traversal itself the tie-break, and the
    traversal is stated.

    Converges in 7 passes on Comitia's 53 plates and 11 on the 38 at module level.

    The pairs are narrowed to this band's own plates **once**, rather than on each of the
    ~2,800 candidates per pass. Under `grouped` the caller hands the whole program's pairs
    to a sweep over one band, so the filter is doing real work, not defending against a
    case that cannot happen.
    """
    order = list(order)
    n = len(order)
    here = set(order)
    w = {p: c for p, c in w.items() if p[0] in here and p[1] in here}
    best = travel(order, w)
    while True:
        moved = False
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                trial = list(order)
                trial.insert(j, trial.pop(i))
                cost = travel(trial, w)
                if cost < best:
                    order, best, moved = trial, cost, True
        if not moved:
            return order


def solve(model: GraphModel, *, grouped: bool = False) -> list[str]:
    """The plate order that keeps crossings short. `grouped` holds packages above the rest.

    The two bands are solved **separately** under `grouped`, never solved together and then
    sorted into bands: sorting afterwards would take an order chosen for its total travel
    and rearrange it into one nobody measured, which is a number on screen that no longer
    describes the picture under it (rule 13). Solving each band on its own means the figure
    reported is the figure of the thing drawn.
    """
    w = weights(model)
    seed = seed_order(model)
    if not grouped:
        return _sweep(seed, w)
    kind = {str(d["id"]): d.get("kind") for d in model.disks}
    pkg = [d for d in seed if kind.get(d) == "package"]
    ext = [d for d in seed if kind.get(d) != "package"]
    return _sweep(pkg, w) + _sweep(ext, w)


def answer(model: GraphModel, *, grouped: bool = False) -> dict[str, Any]:
    """The order, what it bought, and what it is being compared against.

    All three together, because a reader cannot weigh *"27,067 slot-links"* without the
    157,028 it replaced -- the same argument `curiosities.py` makes for stating a middle
    beside every extremum.
    """
    w = weights(model)
    seed = seed_order(model)
    order = solve(model, grouped=grouped)
    before, after = spread(seed, w), spread(order, w)
    return {
        "order": order,
        "grouped": grouped,
        "plates": len(order),
        "pairs": len(w),
        "before": before.as_json(),
        "after": after.as_json(),
        "saved": (round(100 * (1 - after.total / before.total), 1)
                  if before.total else 0.0),
    }
