"""Node separation, and the law that makes it a guarantee rather than a hope.

A dot's size used to be a pixel constant and a plate's size a world quantity, so a node
knew nothing about the room its own plate had. Measured on Comitia at the default framing,
**4,990 of 10,052 drawn nodes touched or overlapped a neighbour** and the smallest plate was
5.5 px across holding six of them.

The fix rests on one measured fact: the tightest pair on a phyllotaxis disk of `n` points is
`1.546 * R / sqrt(n)`, and 1.546 does not vary with `n`. Given that, a renderer can *choose*
a radius that never overlaps. These tests hold the two halves that fact depends on:

* the constant is what `PHYLLOTAXIS_TIGHTEST` says it is, re-measured here rather than
  trusted, so a change to the placement that moved it cannot pass silently;
* the drawn nodes have a spiral **of their own**, so `n` in that formula is the number of
  dots and not the number of slots. Sharing one spiral with the shadows is what made the
  drawn nodes come out in contiguous runs, packed at five times their own density.
"""

from __future__ import annotations

import math
from pathlib import Path

from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import graph as G
from dunneflow.web.layout import (
    DISK_RADIUS,
    PHYLLOTAXIS_TIGHTEST,
    phyllotaxis,
    structural,
)

# Two packages that call each other, so each plate holds real nodes *and* shadows -- the
# arrangement the old single spiral got wrong. A fixture with no cross-plate call would
# have no shadows and would pass every claim below without asking the question (rule 64).
MOD_A = '''
"""Package alpha."""
import os


def one() -> str:
    return os.getenv("A", "")


def two() -> str:
    return one()


def three() -> str:
    return two()
'''

MOD_B = '''
"""Package beta."""
from alpha.mod import one, two


def four() -> str:
    return one()


def five() -> str:
    return two()
'''


def _tightest(points: list[tuple[float, float]]) -> float:
    return min(
        math.hypot(a[0] - b[0], a[1] - b[1])
        for i, a in enumerate(points)
        for b in points[i + 1:]
    )


def test_the_tightest_pair_is_the_constant_the_renderer_relies_on() -> None:
    """`PHYLLOTAXIS_TIGHTEST`, re-measured over four orders of magnitude.

    This is the whole basis of the separation guarantee: a plate of any size knows exactly
    how close its two closest dots are. If this constant is not a constant, a radius chosen
    from it stops being a guarantee and becomes a rule of thumb that fails on some plate
    nobody looked at.
    """
    for n in (6, 9, 12, 26, 58, 151, 475, 991, 4000):
        pts = [phyllotaxis(i, n) for i in range(n)]
        measured = _tightest(pts) * math.sqrt(n) / DISK_RADIUS
        assert abs(measured - PHYLLOTAXIS_TIGHTEST) < 0.002, (
            f"at n={n} the tightest pair is {measured:.4f}*R/sqrt(n), not "
            f"{PHYLLOTAXIS_TIGHTEST}; every node radius is chosen from this"
        )


def test_a_radius_chosen_from_the_constant_never_overlaps() -> None:
    """The guarantee itself, stated as the renderer will use it.

    `r = TIGHTEST * R / (2 * m * sqrt(n))` must leave every pair at least `m` diameters
    apart, at every plate size -- including the sizes where the old picture was solid.
    """
    for m in (1.1, 1.5, 2.0):
        for n in (6, 58, 475, 991):
            r = PHYLLOTAXIS_TIGHTEST * DISK_RADIUS / (2 * m * math.sqrt(n))
            pts = [phyllotaxis(i, n) for i in range(n)]
            gap = _tightest(pts)
            assert gap >= 2 * r, f"m={m} n={n}: {gap:.1f} < {2 * r:.1f}"
            # And not wastefully far: the whole point is that it is tight *and* safe.
            assert gap / (2 * r) < m * 1.01, (
                f"m={m} n={n}: {gap / (2 * r):.3f} diameters apart, asked for {m}"
            )


def _placed(tmp_path: Path) -> tuple[G.GraphModel, dict]:
    root = tmp_path / "prog"
    (root / "alpha").mkdir(parents=True)
    (root / "beta").mkdir(parents=True)
    (root / "alpha" / "mod.py").write_text(MOD_A, encoding="utf-8")
    (root / "beta" / "mod.py").write_text(MOD_B, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    model = G.build(store)
    pos = structural(model)
    store.close()
    return model, pos


def test_drawn_nodes_get_a_spiral_of_their_own(tmp_path: Path) -> None:
    """The placement change the guarantee depends on.

    A plate's drawn nodes must be spaced for *their own* number. Sharing a spiral with the
    shadows packed them at the density of all the placed points and, because the two kinds
    segregate by degree, left them in contiguous runs -- two blobs where there were six
    nodes.
    """
    model, pos = _placed(tmp_path)
    drawn: dict[str, list[tuple[float, float]]] = {}
    for n in model.nodes:
        x, y, _ = pos[(n.id, n.disk)]
        drawn.setdefault(n.disk, []).append((x, y))
    assert model.shadows, "the fixture must produce shadows or this asks nothing"

    for disk, pts in drawn.items():
        if len(pts) < 2:
            continue
        expected = PHYLLOTAXIS_TIGHTEST * DISK_RADIUS / math.sqrt(len(pts))
        assert abs(_tightest(pts) - expected) < 1.0, (
            f"{disk}: its {len(pts)} drawn nodes are spaced for some other number "
            f"— {_tightest(pts):.1f} against {expected:.1f}"
        )


def test_a_shadow_never_lands_on_a_drawn_node(tmp_path: Path) -> None:
    """Two spirals share a disk, so they must not share a point.

    `forcelayout.js` has a degenerate-overlap branch that has never fired, because from a
    phyllotaxis start no two slots coincide. Placing the shadows separately is a second
    spiral on the same disk, which is exactly the way that could stop being true.
    """
    model, pos = _placed(tmp_path)
    by_disk: dict[str, list[tuple[float, float, bool]]] = {}
    for n in model.nodes:
        x, y, _ = pos[(n.id, n.disk)]
        by_disk.setdefault(n.disk, []).append((x, y, False))
    for s in model.shadows:
        x, y, _ = pos[(s.node_id, s.disk)]
        by_disk.setdefault(s.disk, []).append((x, y, True))

    for disk, pts in by_disk.items():
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                if a[2] == b[2]:
                    continue
                assert math.hypot(a[0] - b[0], a[1] - b[1]) > 0.5, (
                    f"{disk}: a shadow and a drawn node are at the same point"
                )


def test_the_placement_is_the_same_on_every_run(tmp_path: Path) -> None:
    """The module's standing promise, and a set of plate ids nearly broke it.

    Iterating `set(drawn) | set(shades)` orders plates by the interpreter's hash seed, so
    the map was built in a different order run to run.
    """
    _, first = _placed(tmp_path / "a")
    _, second = _placed(tmp_path / "b")
    assert list(first.items()) == list(second.items()), \
        "the same graph must place every node identically, in the same order"
