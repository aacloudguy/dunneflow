"""A compartment as a diagram: what is in it, and what the flow between those things is.

**A different level of detail from the stack, not a decoration on it.** The stack draws
every thing the program declares -- ten thousand dots, which is what ten thousand things
can be drawn as. A diagram draws a *compartment*: its classes, its files of loose
functions, what it touches, and the flow between them. Tom's words for why:

    DunneFlow is about FLOW - how information moves between segments of a program.
    Knuth: "data structures + algorithms = programs". I would like these diagrams to
    show the algorithms and flow as best we can.

So a box is a **class** -- a data structure and the algorithms bound to it -- or a **file's
loose functions**, which are the algorithms bound to nothing but each other. That grain was
chosen against a measurement rather than a preference. A box per class *and per loose
function* is 432 boxes on Mensores' `quaestor`, because the program is function-oriented and
42 classes hold only 89 of its 531 routines; gathering each file's loose functions into one
box gives **median 14 boxes, p90 57, max 107**, with one compartment over a hundred. Nothing
is dropped -- the functions are one level in, exactly where a class's methods are, and the
second level is bounded without a rule bounding it: median 4 to 6, and one module in 623
files exceeds a hundred.

## Two emitters, one model

`dot()` is what gets **drawn**. `mermaid()` is what a reader can **copy out** into any other
tool. They are built from the same `Compartment`, in one pass, so a diagram and its
exported source cannot disagree about what is in it (rule 13) -- which is the whole reason
the second one is not a separate walk over the store.

**Graphviz draws and Mermaid does not**, and that is a measured decision rather than a
preference. Mermaid's dagre puts every node with no inbound edge on rank 0 side by side and
lays disconnected components out in a row, and roughly half of a compartment's boxes have no
*within*-compartment edge at all -- they only reach outward. On Mensores that is
`pkg:cli` at **11991x514 pixels, 23:1, in 2.5 s**. dagre has no component-packing,
aspect-ratio or width option to fix it; its whole surface is `rankdir`, `align`, `nodesep`,
`edgesep`, `ranksep`, `ranker`, `acyclicer` and the margins. Graphviz's `pack=true` packs
components instead of rowing them: the same graph is **782x744, 1.1:1, in 83 ms**.

`pack=true` is passed **alone**. It was first tried beside `ratio=compress, size="14,10"`
and appeared to do almost nothing, because `size` merely *scales* a finished drawing and
`ratio` fights the packing -- a probe that changes two things at once measures neither.

## Ports, and why a crossing is drawn as one

A compartment's flow is mostly *outward*: `quaestor` has 83 edges among its own boxes and
221 leaving. Drawing every far end would be the whole program again (rule 19's warning), so
a crossing ends at a **port** -- one node per compartment on the other side, named for it.
That is Tom's *"any links to other classes or routines in other sections of the program
would be edges to other plates"*, and it is what makes the flip-book navigable: a port is a
place to click.

A port is drawn differently from a box because it is **not a thing in this compartment**;
it stands for somewhere else, and a reader who cannot tell those apart is reading a lie
about where code lives (rule 23's argument, one level up).

## Shadows: proposed, measured, and dropped

Tom proposed the stack's own device -- let a crossing end at a **shadow** of the actual
far-side class or file, greyed, so a compartment is self-contained and needs no navigation
to be understood. It is the better *model*: a port says only *which compartment*, a shadow
names the thing, and 79% of shadows would be degree-1 leaves, which layout engines handle
far better than a port's hubs.

**It was built as a probe, measured, and dropped on his call** -- *"stick with what works,
drop the shadow idea"* -- and the measurement is kept because it is the reason, and because
the idea is good enough that someone will think of it again:

```
                no crossings     ports         shadows      nodes: boxes / +ports / +shadows
pkg:mcp            1.26:1        7.69:1        9.52:1              8 / +29 / +67
pkg:governance     1.13:1        2.47:1        4.58:1             40 / +25 / +80
pkg:quaestor       1.98:1        3.43:1        6.64:1             83 / +41 / +175
```

Both put a single enormous row across the picture and swamp the compartment they are
supposed to be about. That is **rule 19 exactly**, one level up from the stack: all the
edges at once do not describe a program, they erase it. So crossings are off by default and
counted, and the shape that is left -- 1.1:1 to 2:1 -- is a diagram a reader can read.

Ports stay as an opt-in switch because they are what makes the flip-book work -- a port is
a place to click, and clicking one moves the reader to that compartment. Shadows have no
such second job: they were only ever a better way to draw the same crossings, and the
crossings are not what this view is for.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from .graph import GraphModel

# A box's label, and a hard bound on it. A class or a file name is short -- routines,
# constants, structures and artefacts run a median of 13 to 18 characters -- but a
# *boundary* carries the expression it touches, a median of 50 and up to 1,388 characters of
# embedded Python. Rule 8 forbids shortening at **ingest**; this is display, the store keeps
# the value whole, and the inspector gives it whole one click away.
LABEL_MAX = 30

# Which kinds become a box of their own rather than folding into a class or a file. A
# boundary and an artefact are what the compartment *touches*, so they are the bottom of the
# flow and belong in the picture; a constant is a name pinned to a value and belongs to
# whatever reads it.
TOUCH_KINDS = ("BOUNDARY", "ARTEFACT")


@dataclass
class Box:
    """One node of a compartment diagram, and what it stands for."""

    id: str
    label: str
    kind: str          # 'class' | 'file' | 'touch' | 'port'
    holds: int = 0     # how many routines are folded into it -- 0 for a touch or a port
    # The node ids this box stands for, so a click on the drawing reaches the selection the
    # rest of the dashboard shares. A box that cannot name what it holds is a shape (rule
    # 30), and the fold is only honest if the reader can get back through it (design rule 1).
    members: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class Compartment:
    """A compartment, its boxes, and the flow among them.

    `inside` is flow between two boxes here. `out` and `into` are flow that crosses the
    compartment's edge, ending at a port. They are kept apart because they answer different
    questions -- *what does this do among itself* and *what does it hang off* -- and merging
    them is how a picture stops being able to say either (rule 23's own reasoning about
    within-plate links and crossings).
    """

    id: str
    name: str
    boxes: list[Box] = field(default_factory=list)
    ports: list[Box] = field(default_factory=list)
    inside: Counter[tuple[str, str]] = field(default_factory=Counter)
    out: Counter[tuple[str, str]] = field(default_factory=Counter)
    into: Counter[tuple[str, str]] = field(default_factory=Counter)

    @property
    def stats(self) -> dict[str, int]:
        drawn = {b.id for b in self.boxes}
        linked = {x for e in self.inside for x in e}
        linked |= {a for a, _ in self.out} | {b for _, b in self.into}
        return {
            "boxes": len(self.boxes),
            "ports": len(self.ports),
            "routines": sum(b.holds for b in self.boxes),
            "inside": len(self.inside),
            "crossing": len(self.out) + len(self.into),
            # Stated rather than hidden: a box with no flow at all is a real thing about the
            # program -- a file nothing here calls and which calls nothing here -- and it is
            # also exactly what made the first attempt at this a ribbon.
            "unlinked": len(drawn - linked),
        }


def _clip(text: str) -> str:
    """A label short enough to draw, with the ellipsis a reader can see."""
    text = (text or "").strip()
    return text if len(text) <= LABEL_MAX else text[: LABEL_MAX - 1] + "…"


def _box_id(disk: str, kind: str, key: str) -> str:
    return f"{disk}|{kind}|{key}"


def build(model: GraphModel) -> dict[str, Compartment]:
    """Fold the whole model into one compartment per plate, in a single pass.

    Built from `model.nodes` and `model.edges` rather than by a second walk over the store,
    so the diagram describes exactly what the stack describes. **Shadows are not consulted**:
    a shadow is a placement device and never an endpoint (rule 23), and `model.edges` already
    carries each crossing twice, once per plate -- which is why every crossing here is keyed
    by the *plate* of its far end rather than counted, or it would be counted twice.
    """
    box_of: dict[str, str] = {}
    comps: dict[str, Compartment] = {}
    seen: dict[str, Box] = {}

    def comp(disk: str) -> Compartment:
        if disk not in comps:
            comps[disk] = Compartment(id=disk, name=disk.partition(":")[2] or disk)
        return comps[disk]

    for n in model.nodes:
        d = n.detail or {}
        if n.kind == "ROUTINE":
            # `<module>` is the synthetic scope that owns what no function does. It is a
            # real node in the stack and it is not a thing a reader looks for in a diagram,
            # so its routines fold into their file like any other loose function.
            if n.label == "<module>":
                continue
            mod, cls = d.get("module"), d.get("class_name")
            if cls:
                bid = _box_id(n.disk, "class", f"{mod}.{cls}")
                box = seen.get(bid) or Box(bid, _clip(cls), "class",
                                           detail={"module": mod, "class_name": cls})
            else:
                bid = _box_id(n.disk, "file", str(mod))
                leaf = (mod or "?").rsplit(".", 1)[-1] + ".py"
                box = seen.get(bid) or Box(bid, _clip(leaf), "file", detail={"module": mod})
        elif n.kind in TOUCH_KINDS:
            what = d.get("bkind") or d.get("akind") or n.kind
            bid = _box_id(n.disk, "touch", str(what))
            box = seen.get(bid) or Box(bid, _clip(str(what)), "touch",
                                       detail={"what": what, "direction": d.get("direction")})
        else:
            continue
        if bid not in seen:
            seen[bid] = box
            comp(n.disk).boxes.append(box)
        box.holds += 1
        box.members.append(n.id)
        box_of[n.id] = bid

    disk_of = {n.id: n.disk for n in model.nodes}
    ports: dict[tuple[str, str], Box] = {}

    def port(here: str, there: str) -> Box:
        key = (here, there)
        if key not in ports:
            b = Box(_box_id(here, "port", there), _clip(there.partition(":")[2] or there),
                    "port", detail={"plate": there})
            ports[key] = b
            comp(here).ports.append(b)
        return ports[key]

    for e in model.edges:
        a, b = box_of.get(e.src), box_of.get(e.dst)
        if not a or not b or a == b:
            continue
        da, db = disk_of.get(e.src), disk_of.get(e.dst)
        if da is None or db is None:
            continue
        if da == db:
            comp(da).inside[(a, b)] += e.weight
        else:
            comp(da).out[(a, port(da, db).id)] += e.weight
            comp(db).into[(port(db, da).id, b)] += e.weight

    for c in comps.values():
        c.boxes.sort(key=lambda x: (x.kind, x.label.lower(), x.id))
        c.ports.sort(key=lambda x: (x.label.lower(), x.id))
    return comps


# ── the two emitters ────────────────────────────────────────────────────────────────

# Graphviz needs an identifier per node, and a box id carries dots, colons and slashes.
# Numbered on the *sorted* box list so the same compartment yields the same source on every
# run and every machine -- `layout.py` requires that of positions for spatial memory, and a
# diagram a reader has learned the shape of has exactly the same claim.
def _ids(c: Compartment) -> dict[str, str]:
    return {b.id: f"n{i}" for i, b in enumerate(c.boxes + c.ports)}


def _quote(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def dot(c: Compartment, *, rankdir: str = "TB", ports: bool = False) -> str:
    """The compartment as Graphviz DOT -- the source that is actually drawn.

    `pack=true` and nothing else. See this module's docstring: `size` scales a finished
    drawing and `ratio` fights the packing, so the two attributes that look like they help
    are the two that hid the fix.

    **Ports are off by default, and that is design rule 19 arriving here on its own.** Drawn,
    they do two things to the picture and both are bad. They *connect what was disconnected*,
    so `pack` has nothing left to pack and the compartment goes back to being wide -- 107
    boxes and 26 ports is 4871x1331 against 1746x1098 for the boxes alone. And in a small
    compartment they **outnumber the subject**: `pkg:mcp` is 8 boxes and 29 ports, which is
    not a diagram of mcp, it is a diagram of everywhere mcp touches. Rule 19 already decided
    this shape for the stack -- all the edges at once do not describe a program, they erase
    it -- and the count is always stated so the reader knows what they are not looking at.

    `id=` on every node is the box id, unescaped, which is what makes the rendered SVG
    clickable: Graphviz writes it into the `<g id="...">` of each node, so the browser can
    route a click back to a thing this program knows about rather than to a shape. Rule 30 --
    a control that carries no identity resolves to nothing.
    """
    ids = _ids(c)
    out = [
        "digraph compartment {",
        f'  graph [rankdir={rankdir}, pack=true, packmode="node", '
        f'bgcolor="transparent", fontname="Helvetica"];',
        '  node [shape=box, style=rounded, fontname="Helvetica", fontsize=10,'
        'margin="0.10,0.05", height=0.3];',
        '  edge [arrowsize=0.6, color="#5f6b7a"];',
    ]
    for b in c.boxes:
        n = ids[b.id]
        held = f"\\n{b.holds} {'methods' if b.kind == 'class' else 'functions'}"
        if b.kind == "class":
            out.append(f'  {n} [id="{_quote(b.id)}", label="{_quote(b.label)}{held}", '
                       f'shape=box, style="rounded,bold"];')
        elif b.kind == "file":
            out.append(f'  {n} [id="{_quote(b.id)}", label="{_quote(b.label)}{held}"];')
        else:
            # What it touches: a cylinder, which is the shape a diagram has always spent on
            # a store, and the bottom of the flow.
            out.append(f'  {n} [id="{_quote(b.id)}", label="{_quote(b.label)}", '
                       f'shape=cylinder, style=""];')
    if ports:
        for b in c.ports:
            out.append(f'  {ids[b.id]} [id="{_quote(b.id)}", label="{_quote(b.label)}", '
                       f'shape=ellipse, style=dashed];')
    for src, dst in sorted(c.inside):
        out.append(f"  {ids[src]} -> {ids[dst]};")
    if ports:
        # A crossing is dashed, because it does not end where it appears to: the far end is
        # a port standing for a whole compartment, not the routine that was called.
        for src, dst in sorted(list(c.out) + list(c.into)):
            out.append(f"  {ids[src]} -> {ids[dst]} [style=dashed];")
    out.append("}")
    return "\n".join(out)


def mermaid(c: Compartment) -> str:
    """The same compartment as Mermaid source, for a reader to copy elsewhere.

    **This is not what gets drawn** -- see the module docstring for the measurement that
    decided it. It is emitted from the same `Compartment` as `dot()` so the two cannot
    describe different graphs, which is the only reason offering both is safe.

    A Mermaid id may not begin with a digit and may not carry a dot, so the same `n0, n1`
    numbering is used; the readable name is in the label where a reader wants it.
    """
    ids = _ids(c)
    out = [f"%% {c.name} — {c.stats['boxes']} boxes, {c.stats['routines']} routines",
           "flowchart TD"]
    for b in c.boxes:
        n, lab = ids[b.id], b.label.replace('"', "'")
        held = f"<br>{b.holds} {'methods' if b.kind == 'class' else 'functions'}"
        if b.kind == "touch":
            out.append(f'  {n}[("{lab}")]')
        else:
            out.append(f'  {n}["{lab}{held}"]')
    for b in c.ports:
        out.append(f'  {ids[b.id]}(["{b.label}"])')
    for src, dst in sorted(c.inside):
        out.append(f"  {ids[src]} --> {ids[dst]}")
    for src, dst in sorted(list(c.out) + list(c.into)):
        out.append(f"  {ids[src]} -.-> {ids[dst]}")
    return "\n".join(out)
