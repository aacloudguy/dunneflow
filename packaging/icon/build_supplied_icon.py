"""Condition a supplied drawing into DunneFlow's `.icns`, under the same canvas rules.

**This is a conditioner, not a generator**, and the distinction is the point.
`build_icon.py` beside it draws the hare as geometry so that a number can change and the
whole ladder re-render; this takes a picture somebody made and does the four things a
`.icns` needs doing to it -- square it, scale it, round it, ladder it. Nothing here can
improve the drawing, which is why the measurements it prints matter more than the files it
writes.

The canvas rules are `build_icon.py`'s, copied deliberately so the two candidates can be
compared at the same size without one of them having an advantage the other does not:
1024 square, corners at 22.4% of the side **drawn rather than masked** (nothing rounds a
`.icns` on the reader's behalf), and the art centred with a stated margin.

**What it prints is the thing to read.** `build_icon.py`'s docstring records that an
earlier candidate "failed at 32px for exactly the opposite reason: tan on mid-blue are
close in lightness, so the shape dissolved into the ground while the drawing itself was
fine." That is a claim about a *ratio*, so this measures the ratio rather than restating
the claim, and prints it beside the geometric icon's for the same ground.

Run it: `uv run --with pillow python packaging/icon/build_supplied_icon.py <source.jpg>`

**The icon the application ships** is `dunneflow.icns`, made from `rabbit-head.png` beside
it -- Tom's rabbit head at 800x528, which replaced a 266px crop of the same subject. Head-only
rather than the whole leaping animal, and that was settled by looking: it is the only framing
that still reads as a rabbit at 32px and at 16px, where the full-body drawing is a smudge.
Both the drawing and the `.icns` are committed, and regenerating from the one gives the other
byte for byte:

    uv run --with pillow python packaging/icon/build_supplied_icon.py packaging/icon/rabbit-head.png

**What the larger source bought**, measured: the upscale to a 1024px canvas fell from
**3.85x to 1.28x**, so 512 and 1024 stopped being soft. The fill contrast against the ground
is unchanged at 1.75:1 -- what carries the shape at small sizes is the dark outline, which is
heavier in this drawing, and the four-point star reads where the old fan of thin rays turned
to mush below 64px.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

SIZE = 1024
# `build_icon.py`'s number, and for its reason: macOS rounds its own icons at roughly
# 22.4% of the side, and a square `.icns` stays square on the reader's screen.
CORNER = round(0.224 * SIZE)

# How much of the canvas the drawing is allowed. Full width would put ink in the corner
# radius, where the rounding eats it -- so the art is inset and the inset is a number.
ART_WIDTH = 0.90

# The ladder macOS asks for. Each `.iconset` name is a contract: `icon_32x32@2x.png` is a
# 64-pixel file, and getting that wrong produces an `.icns` that builds and looks soft.
LADDER = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]


def luminance(rgb: tuple[int, ...]) -> float:
    """WCAG relative luminance -- the channel that survives when size takes the rest."""
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def ground(im: Image.Image) -> tuple[int, int, int]:
    """The most common colour, which for a flat-backed drawing is the ground.

    Taken rather than declared, because the point of a conditioner is that it has not been
    told what the drawing contains.
    """
    common = Counter(im.getdata()).most_common(1)[0][0]
    return (common[0], common[1], common[2])


def art_box(im: Image.Image, bg: tuple[int, int, int],
            tol: int = 26) -> tuple[int, int, int, int]:
    """The drawing's own bounds, so the frame is chosen and not inherited from the file.

    A JPEG of a flat background is never flat -- compression leaves every pixel a little
    different from its neighbours -- so this is a tolerance around the ground rather than
    an equality, and the tolerance is stated because it decides the answer.
    """
    px = im.load()
    w, h = im.size
    xs, ys = [], []
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if not all(abs(c[i] - bg[i]) < tol for i in range(3)):
                xs.append(x)
                ys.append(y)
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def rounded_mask(size: int, radius: int) -> Image.Image:
    """The corner, drawn at 4x and resampled, because a 16px corner aliases badly."""
    big = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        (0, 0, size * 4 - 1, size * 4 - 1), radius=radius * 4, fill=255)
    return big.resize((size, size), Image.LANCZOS)


def compose(source: Path) -> Image.Image:
    """The drawing on the icon canvas, **keeping whatever bleed the artist drew**.

    An edge the subject already runs off is a decision, not an accident, and centring
    undoes it: the rabbit is cut level at the neck because it is meant to run off the
    bottom, and centring floats that cut in the middle of the canvas with blue underneath,
    where it reads as a picture that failed to load rather than a head leaning out of its
    frame. So every edge the art meets in its *own* frame it meets in this one too, and
    only the edges it left a margin on get ground.

    Centring is still right for a drawing that sits inside its frame on all four sides,
    which is the case this started with -- so the rule is read off the source rather than
    switched on by a flag (rule 30: the drawing says which it is).
    """
    src = Image.open(source).convert("RGB")
    bg = ground(src)
    left, top, right, bottom = art_box(src, bg)
    art = src.crop((left, top, right, bottom))

    bleeds_l, bleeds_r = left == 0, right == src.width
    bleeds_t, bleeds_b = top == 0, bottom == src.height

    # Full width when it runs off both sides -- the corner radius takes the extremes, which
    # is what a bleed is for. Otherwise the stated inset, so nothing sits in the rounding.
    target_w = SIZE if (bleeds_l and bleeds_r) else round(SIZE * ART_WIDTH)
    target_h = round(art.height * target_w / art.width)
    art = art.resize((target_w, target_h), Image.LANCZOS)

    x = 0 if bleeds_l else (SIZE - target_w if bleeds_r else (SIZE - target_w) // 2)
    if bleeds_t and not bleeds_b:
        y = 0
    elif bleeds_b and not bleeds_t:
        y = SIZE - target_h
    else:
        y = (SIZE - target_h) // 2

    canvas = Image.new("RGB", (SIZE, SIZE), bg)
    canvas.paste(art, (x, y))

    out = canvas.convert("RGBA")
    out.putalpha(rounded_mask(SIZE, CORNER))
    return out


def report(source: Path) -> None:
    """What the drawing is made of, in the one channel that decides whether it reads."""
    src = Image.open(source).convert("RGB")
    bg = ground(src)
    left, top, right, bottom = art_box(src, bg)

    # The subject's own colour, taken as the commonest thing that is not the ground and
    # not near-white -- the highlights and the rays are not what has to carry the shape.
    px = src.load()
    subject: Counter[tuple[int, int, int]] = Counter()
    for y in range(top, bottom):
        for x in range(left, right):
            c = px[x, y]
            if all(abs(c[i] - bg[i]) < 26 for i in range(3)):
                continue
            if min(c) > 200:                      # white: the rays and the speed lines
                continue
            subject[(c[0] // 8 * 8, c[1] // 8 * 8, c[2] // 8 * 8)] += 1
    subj = subject.most_common(1)[0][0]

    print(f"source      {source.name}  {src.width}x{src.height}")
    print(f"art bounds  {right - left}x{bottom - top}  "
          f"(scaled {SIZE * ART_WIDTH / (right - left):.2f}x to reach {SIZE}px)")
    print(f"ground      #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}  L={luminance(bg):.3f}")
    print(f"subject     #{subj[0]:02x}{subj[1]:02x}{subj[2]:02x}  L={luminance(subj):.3f}")
    print(f"subject:ground contrast  {contrast(subj, bg):.2f}:1")
    print("  the geometric icon beside it is 4.74:1 on the same ground, and its own")
    print("  docstring records a candidate that failed at 32px for having less.")
    if src.width < SIZE:
        print(f"resolution  {src.width}px of source for a {SIZE}px icon — "
              f"upscaled {SIZE / src.width:.2f}x, so 512 and 1024 are soft by construction")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.exists():
        print(f"error: {source} does not exist")
        return 2

    report(source)
    master = compose(source)

    iconset = HERE / "supplied.iconset"
    iconset.mkdir(exist_ok=True)
    for name, px in LADDER:
        master.resize((px, px), Image.LANCZOS).save(iconset / name)
    # The ladder as flat files too, for looking at rather than for building with.
    for px in (16, 32, 64, 128, 256, 512, 1024):
        master.resize((px, px), Image.LANCZOS).save(HERE / f"supplied_{px}.png")

    icns = HERE / "dunneflow.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True)
    print(f"\nwrote {icns}  ({icns.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
