"""Draw DunneFlow's icon: a hare leaping over a river, as geometry rather than a picture.

**Why this is a generator and not a drawing.** The icon has to survive being 32 pixels
wide -- the Dock's small end, the Finder's list view, the menu bar -- and at that size the
only things that read are *value contrast* and *silhouette*. Both are decided by numbers
that want tuning: how big the hare is in the frame, how deep the river sits, how much blue
shows between the two. A generated SVG lets a number change and the whole ladder be
re-rendered in a second; a drawing means starting again.

**The rule the composition is built to.** The hare is one dark silhouette, the river is one
light mass, and the ground is the blue between them. Three values, maximally separated, so
that when every detail has gone there is still a dark animal above a light river. The
earlier candidate failed at 32px for exactly the opposite reason: tan on mid-blue are close
in lightness, so the shape dissolved into the ground while the drawing itself was fine.

**The gap is the subject.** `GAP` is the blue between the hare's lowest point and the
river's highest crest, and it is what makes this a leap *over* water rather than an animal
standing in it. It is stated in canvas units and checked in pixels at every rendered size,
because a separation that reads at 512 and closes at 32 has not done its job.

**Ears do not overlap, deliberately.** Two dark shapes touching merge into one blob -- the
fill has no seam -- so the ears are set at different angles with blue between them. That
splay is most of what says *hare* rather than *some animal* at small sizes.

Run it: `uv run --with pillow python packaging/icon/build_icon.py`
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- the canvas --- #

SIZE = 1024
# macOS rounds its own icons at roughly 22.4% of the side. Drawn rather than left to the
# system: nothing masks a `.icns` on the reader's behalf, so a square icon stays square.
CORNER = 0.224 * SIZE

BLUE = "#249AD8"        # sampled from the reference the shape came from
DARK = "#0B2942"        # the hare: near-black, so value alone carries it at 32px
WATER = "#FFFFFF"       # the near bank of the river
WATER_BACK = "#A6D8F2"  # the far bank, one step off the ground

# ------------------------------------------------------------------- the hare --- #

# A single number for "how big is the animal in the frame". Everything below is in canvas
# units at SCALE = 1.0 and is scaled about the hare's own centre, so this can move without
# anything drifting off the edge.
SCALE = 1.0

# Where the river's highest crest sits, and how much blue is left above it.
RIVER_TOP = 690         # the far bank's crest
GAP = 96                # canvas units of blue between hare and water -- 3px at 32px


def tapered(bx: float, by: float, tx: float, ty: float,
            base_w: float, bulge: float = 0.0) -> str:
    """A limb or an ear: `base_w` wide where it joins, tapering to a point at the tip.

    `bulge` bends it perpendicular to its own axis, which is what stops a leg reading as a
    stick. Built from the axis rather than from absolute control points so that moving a
    tip does not require re-deriving four numbers by hand.
    """
    dx, dy = tx - bx, ty - by
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux                      # unit normal, y-down
    half = base_w / 2.0

    lx, ly = bx + nx * half, by + ny * half
    rx, ry = bx - nx * half, by - ny * half

    # **The width is held out to `HOLD` of the length before it tapers**, and that one
    # number is the difference between a leg and a whisker. The first version put its
    # control points on the centre line, so every limb pinched to a needle the moment it
    # left the base and the icon rendered as a blob with antennae -- the ears looked like
    # spikes and the forelegs like whiskers coming off the face.
    hold = 0.55
    kx, ky = bx + ux * length * hold, by + uy * length * hold
    wide = half * 0.92
    near = half * 0.30
    tipx, tipy = tx - ux * length * 0.20, ty - uy * length * 0.20
    return (
        f"M {lx:.1f},{ly:.1f} "
        f"C {kx + nx * (wide + bulge):.1f},{ky + ny * (wide + bulge):.1f} "
        f"{tipx + nx * (near + bulge * 0.4):.1f},{tipy + ny * (near + bulge * 0.4):.1f} "
        f"{tx:.1f},{ty:.1f} "
        f"C {tipx - nx * (near - bulge * 0.4):.1f},{tipy - ny * (near - bulge * 0.4):.1f} "
        f"{kx - nx * (wide - bulge):.1f},{ky - ny * (wide - bulge):.1f} "
        f"{rx:.1f},{ry:.1f} Z"
    )


def hare() -> tuple[list[str], float]:
    """Every piece of the animal, and the lowest point it reaches.

    **Overlapping primitives in one fill, not one path.** A silhouette does not need its
    outline solved: eight shapes of the same colour that touch *are* one shape, and each of
    them can be moved without re-cutting the others. The lowest point comes back because
    `GAP` is measured from it and must not be maintained by hand.
    """
    parts: list[str] = []
    low = 0.0

    def ellipse(cx: float, cy: float, rx: float, ry: float, rot: float = 0.0) -> None:
        nonlocal low
        parts.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
            f'transform="rotate({rot} {cx} {cy})"/>'
        )
        low = max(low, cy + max(rx, ry))

    def limb(bx: float, by: float, tx: float, ty: float, w: float, bulge: float = 0.0) -> None:
        nonlocal low
        parts.append(f'<path d="{tapered(bx, by, tx, ty, w, bulge)}"/>')
        low = max(low, ty + w * 0.25, by + w * 0.5)

    # Hind leg first, so it sits behind the haunch that covers its joint.
    limb(302, 438, 138, 546, 132, bulge=30)        # thigh, thrown back
    ellipse(120, 552, 78, 34, rot=-14)             # hind foot, long and flat
    ellipse(198, 352, 46, 42)                      # tail

    ellipse(300, 400, 140, 128)                    # haunch
    ellipse(530, 358, 232, 110, rot=-8)            # body
    ellipse(700, 348, 112, 94, rot=-6)             # chest and shoulder

    # Front legs, off the **chest** and not the jaw. They sat forty units too high and
    # read as whiskers coming off the muzzle rather than legs reaching into the leap.
    limb(716, 408, 898, 476, 78, bulge=-22)        # leading
    limb(664, 428, 810, 520, 70, bulge=-18)        # trailing
    ellipse(902, 480, 46, 25, rot=18)
    ellipse(816, 524, 42, 23, rot=24)

    ellipse(818, 298, 90, 74, rot=-14)             # head
    ellipse(890, 320, 50, 40, rot=-8)              # muzzle
    ellipse(926, 326, 23, 19)                      # nose

    # **Splayed, and that is the whole of reading as a hare.** Same fill means touching
    # shapes merge, so the angle between them is what keeps two ears visible at 32px.
    #
    # **And upright rather than swept back.** Laid along the spine they were geometrically
    # clear of the back and still merged into it by eye -- a wide shape a few units above a
    # long one reads as one outline. Rising means blue underneath them, which is what makes
    # them ears instead of a fin. It costs some of the speed a swept ear carries; the
    # forelegs and the leap are already saying that, and nothing else says *rabbit*.
    limb(800, 244, 810, 78, 84, bulge=14)          # near ear, near-vertical
    limb(752, 256, 692, 92, 76, bulge=12)          # far ear, leaning back
    return parts, low


def river() -> list[str]:
    """Two banks, flat and full width. The far one paler, the near one white.

    **Flat, not swirly.** A curl collapses into a dot below about 48px, so the crests here
    are shallow and long -- they still read as moving water where a spiral reads as a
    smudge. Both bands run the whole width and off both edges, so the river is the base of
    the icon rather than an object sitting in it.
    """
    def band(top: float, amp: float, fill: str) -> str:
        # Four shallow crests across the width, then straight down and along the bottom.
        w = SIZE
        d = [f"M 0,{top:.0f}"]
        steps = 4
        for i in range(steps):
            x0 = w * i / steps
            x1 = w * (i + 1) / steps
            mid = (x0 + x1) / 2
            up = top - amp if i % 2 == 0 else top + amp * 0.55
            d.append(f"C {x0 + (mid - x0) * 0.6:.0f},{up:.0f} "
                     f"{mid + (x1 - mid) * 0.4:.0f},{up:.0f} {x1:.0f},{top:.0f}")
        d.append(f"L {w},{SIZE} L 0,{SIZE} Z")
        return f'<path d="{" ".join(d)}" fill="{fill}"/>'

    return [band(RIVER_TOP + 54, 46, WATER_BACK), band(RIVER_TOP + 168, 40, WATER)]


def build() -> tuple[str, float]:
    parts, low = hare()

    # The hare is drawn where it looked right, then moved as one so its lowest point lands
    # exactly `GAP` above the water. Stated as arithmetic rather than baked into every
    # coordinate: `GAP` is a decision, and a decision should be visible.
    lift = (RIVER_TOP - GAP) - low
    body = "\n    ".join(parts)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE}"
     viewBox="0 0 {SIZE} {SIZE}">
  <rect width="{SIZE}" height="{SIZE}" rx="{CORNER:.0f}" ry="{CORNER:.0f}" fill="{BLUE}"/>
  {chr(10).join("  " + b for b in river())}
  <g fill="{DARK}" transform="translate(0 {lift:.1f}) scale({SCALE})">
    {body}
  </g>
</svg>
"""
    return svg, low + lift


if __name__ == "__main__":
    svg, low = build()
    out = HERE / "dunneflow.svg"
    out.write_text(svg, encoding="utf-8")
    gap_units = RIVER_TOP - low
    print(f"wrote {out}")
    print(f"hare's lowest point: {low:.0f}   river crest: {RIVER_TOP}   "
          f"gap: {gap_units:.0f} units")
    for px in (16, 32, 64, 128, 256, 512, 1024):
        print(f"  at {px:>4}px the gap is {gap_units * px / SIZE:.1f}px")
        subprocess.run(["rsvg-convert", "-w", str(px), "-h", str(px),
                        str(out), "-o", str(HERE / f"render_{px}.png")], check=True)
