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
    kind: str          # 'class' | 'file' | 'touch' | 'port' | 'wayin'
    holds: int = 0     # how many routines are folded into it -- 0 for a touch or a port
    # The node ids this box stands for, so a click on the drawing reaches the selection the
    # rest of the dashboard shares. A box that cannot name what it holds is a shape (rule
    # 30), and the fold is only honest if the reader can get back through it (design rule 1).
    members: list[str] = field(default_factory=list)
    # What those members are called, in the same order. Carried rather than looked up later
    # because the fold is the only place that knows both -- a second pass to recover a name
    # for an id would be a second answer to what a box holds (rule 13).
    labels: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


# One lane of flow: for each pair of boxes, the weight **per kind**. Not a plain
# `Counter[(src, dst)]`, which is what it was: that keeps the weight and drops the kind, so
# a call and a database touch between the same two boxes are one arrow with one number and
# nothing anywhere can say which it is. Held as one structure rather than as a weight beside
# a kind map, because two structures over one fact drift (rule 13) -- the weight *is* the
# sum of the kinds, by construction.
Flow = dict[tuple[str, str], Counter[str]]


def add_flow(lane: Flow, src: str, dst: str, kind: str, weight: int) -> None:
    """The one door onto a lane, so a caller cannot record a weight without its kind."""
    lane.setdefault((src, dst), Counter())[kind] += weight


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
    # **The ways in that enter this compartment**, and the flow from each into the boxes it
    # starts. Their own list and their own lane rather than boxes and `inside`, because
    # every count on the panel says what it counts (rule 32): "24 boxes over 237 routines"
    # is about the program's own code, and a way in is the world outside reaching into it.
    # Folding them in would have grown that number by one and changed what it meant.
    entries: list[Box] = field(default_factory=list)
    entered: Flow = field(default_factory=dict)
    inside: Flow = field(default_factory=dict)
    out: Flow = field(default_factory=dict)
    into: Flow = field(default_factory=dict)

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
            # How many ways in reach this compartment, and how many boxes they reach
            # between them. `entered` is the *drawable* population; `ENTRY_ARROWS` bounds
            # what is drawn and `entry_hidden` says by how much, because a bound nobody
            # states is a picture that quietly stops being complete (rule 8).
            "entries": len(self.entries),
            "entered": len(self.entered),
            "entry_hidden": max(0, len(self.entered) - self.entry_drawn_count()),
            # Stated rather than hidden: a box with no flow at all is a real thing about the
            # program -- a file nothing here calls and which calls nothing here -- and it is
            # also exactly what made the first attempt at this a ribbon.
            "unlinked": len(drawn - linked),
        }

    def entry_arrows(self) -> list[tuple[str, str]]:
        """The entry arrows that are drawn, bounded per way in and stated in `stats`.

        Bounded **per entry box**, not over the compartment: one way in fanning out to 39
        boxes must not push another way in's single arrow out of the picture. Sorted so the
        same compartment yields the same source on every run -- `layout.py` requires that of
        positions for spatial memory and a drawing a reader has learnt the shape of has the
        same claim.
        """
        by_entry: dict[str, list[tuple[str, str]]] = {}
        for pair in sorted(self.entered):
            by_entry.setdefault(pair[0], []).append(pair)
        out: list[tuple[str, str]] = []
        for src in sorted(by_entry):
            out.extend(by_entry[src][:ENTRY_ARROWS])
        return out

    def entry_drawn_count(self) -> int:
        return len(self.entry_arrows())


# **The arrow bound, and it is one compartment's number.** Drawn unbounded, `mensores`
# alone -- which enters 39 of `pkg:cli`'s boxes, nearly every file in the package -- takes
# that compartment from 734x650pt at 1.1:1 to **3647x428pt at 8.5:1**: the horizontal strip
# this module's docstring records Mermaid producing, arriving through a different door.
# Bounded at eight it is 1017x674 at 1.5:1, and *no other compartment reaches the bound at
# all* -- the next largest fan-out in 53 is three. So this is a bound on the one picture
# that needs it (rule 8: bound a diagram, and only a diagram); opening the box lists every
# routine the way in starts here, unbounded, because that is an answer and not a picture.
ENTRY_ARROWS = 8


def _clip(text: str) -> str:
    """A label short enough to draw, with the ellipsis a reader can see."""
    text = (text or "").strip()
    return text if len(text) <= LABEL_MAX else text[: LABEL_MAX - 1] + "…"


def _box_id(disk: str, kind: str, key: str) -> str:
    return f"{disk}|{kind}|{key}"


def build(model: GraphModel,
          ways: dict[str, list[str]] | None = None) -> dict[str, Compartment]:
    """Fold the whole model into one compartment per plate, in a single pass.

    Built from `model.nodes` and `model.edges` rather than by a second walk over the store,
    so the diagram describes exactly what the stack describes. **Shadows are not consulted**:
    a shadow is a placement device and never an endpoint (rule 23), and `model.edges` already
    carries each crossing twice, once per plate -- which is why every crossing here is keyed
    by the *plate* of its far end rather than counted, or it would be counted twice.

    `ways` maps a routine id to the ways in that start it, and is the **only** thing here
    that did not come out of the model. It arrives as an argument rather than being looked
    up, because this module takes a model and never a store: `waysin.listing()` is where
    that question is asked, and asking it twice is how two answers begin (rule 51). `None`
    means nobody asked for entries, which is a different thing from a program with none --
    a compartment then has an empty `entries` list either way, and the panel says which.
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
        box.labels.append(n.label)
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
            add_flow(comp(da).inside, a, b, e.kind, e.weight)
        else:
            add_flow(comp(da).out, a, port(da, db).id, e.kind, e.weight)
            add_flow(comp(db).into, port(db, da).id, b, e.kind, e.weight)

    # ── the ways in, and the boxes each one enters ──────────────────────────────────
    #
    # **A way in is not one of the things it starts** (rule 74). It gets its own box, holding
    # the routines it starts *in this compartment* -- so opening it uses the second level
    # already built for a class or a file, and the reader lands on an ordinary selection.
    #
    # `holds` counts what it starts **here** and not its whole reach: `mensores` reaches
    # 1,381 routines and starts 106 of them in `pkg:cli`, and a box on `pkg:cli` labelled
    # 1,381 would be a number about somewhere else (rule 24).
    if ways:
        entry_boxes: dict[tuple[str, str], Box] = {}
        for node_id, names in ways.items():
            bid_here = box_of.get(node_id)
            disk = disk_of.get(node_id)
            if not bid_here or disk is None:
                continue
            for name in names:
                key = (disk, name)
                entry = entry_boxes.get(key)
                if entry is None:
                    entry = Box(_box_id(disk, "wayin", name), _clip(name), "wayin",
                                detail={"wayin": name})
                    entry_boxes[key] = entry
                    comp(disk).entries.append(entry)
                entry.holds += 1
                entry.members.append(node_id)
                entry.labels.append(name)
                # Weight is how many of this box's routines this way in starts, which is what
                # makes one arrow heavier than another rather than every arrow being 1.
                add_flow(comp(disk).entered, entry.id, bid_here, "ENTRY", 1)

    for c in comps.values():
        c.boxes.sort(key=lambda x: (x.kind, x.label.lower(), x.id))
        c.ports.sort(key=lambda x: (x.label.lower(), x.id))
        c.entries.sort(key=lambda x: (x.label.lower(), x.id))
    return comps


# ── the two emitters ────────────────────────────────────────────────────────────────

# Graphviz needs an identifier per node, and a box id carries dots, colons and slashes.
# Numbered on the *sorted* box list so the same compartment yields the same source on every
# run and every machine -- `layout.py` requires that of positions for spatial memory, and a
# diagram a reader has learned the shape of has exactly the same claim.
def _ids(c: Compartment) -> dict[str, str]:
    return {b.id: f"n{i}" for i, b in enumerate([*c.boxes, *c.ports, *c.entries])}


def _quote(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# The separator between the two ends of an edge id. `=>` rather than something prettier
# because it must not occur in a box id, and a box id is `plate|kind|key` where the key is
# a module path, a class name, a boundary kind, or another box id -- none of which can
# contain it. The client splits on the **first** occurrence; a guard asserts no box id
# holds one, because if one ever did the split would name a box that does not exist and
# the panel would answer confidently about nothing (rule 30).
EDGE_SEP = "=>"


def edge_id(src: str, dst: str) -> str:
    """The identity of one edge, so a click on an arrow reaches the flow behind it."""
    return f"{src}{EDGE_SEP}{dst}"


def split_edge(eid: str) -> tuple[str, str] | None:
    """The two ends of an edge id, or `None` if it is not one. Never a guess."""
    src, sep, dst = eid.partition(EDGE_SEP)
    return (src, dst) if sep and src and dst else None


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
        elif b.kind == "routine":
            # The second level. A routine says what it is called and nothing else: it
            # holds only itself, so "1 functions" would be a count of the box rather
            # than a fact about the program (rule 32). What it takes and what it gives
            # back is the hover card's invocation line, one glance away.
            out.append(f'  {n} [id="{_quote(b.id)}", label="{_quote(b.label)}", '
                       f'shape=box, style=rounded];')
        else:
            # What it touches: a cylinder, which is the shape a diagram has always spent on
            # a store, and the bottom of the flow.
            out.append(f'  {n} [id="{_quote(b.id)}", label="{_quote(b.label)}", '
                       f'shape=cylinder, style=""];')
    # **Drawn by default, unlike a port, and the difference is measured rather than felt.**
    # Rule 19 turned ports off because they are median 13 and max 41 per compartment against
    # a median of 10 boxes -- they outnumber the subject and they connect what `pack` needs
    # disconnected. Ways in are **max 3 per compartment and absent from 46 of 53**. Same
    # rule, opposite answer, because it is a different population; the numbers are here so
    # the next reader can check that rather than take it.
    #
    # A **note** silhouette, never a colour: colour on this page is already spent on
    # difference and severity (design rule 4), and a shape is what tells a reader that the
    # thing outside the program is a different kind of thing (design rule 5's neighbour).
    for b in c.entries:
        out.append(f'  {ids[b.id]} [id="{_quote(b.id)}", label="{_quote(b.label)}", '
                   f'shape=note, style="", fontsize=9];')
    for src, dst in c.entry_arrows():
        out.append(f'  {ids[src]} -> {ids[dst]} '
                   f'[style=bold, id="{_quote(edge_id(src, dst))}"];')
    if ports:
        for b in c.ports:
            out.append(f'  {ids[b.id]} [id="{_quote(b.id)}", label="{_quote(b.label)}", '
                       f'shape=ellipse, style=dashed];')
    # `id=` on every edge, for the same reason it is on every node: Graphviz writes it into
    # the `<g id="...">` of the arrow, so a click routes back to a thing this program knows
    # about. Without it an edge carries Graphviz's own auto id and nothing can be asked
    # about it -- which is what "an edge has no answer at all" meant.
    for src, dst in sorted(c.inside):
        out.append(f'  {ids[src]} -> {ids[dst]} [id="{_quote(edge_id(src, dst))}"];')
    if ports:
        # A crossing is dashed, because it does not end where it appears to: the far end is
        # a port standing for a whole compartment, not the routine that was called.
        for src, dst in sorted(list(c.out) + list(c.into)):
            out.append(f'  {ids[src]} -> {ids[dst]} '
                       f'[style=dashed, id="{_quote(edge_id(src, dst))}"];')
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
        elif b.kind == "routine":
            out.append(f'  {n}["{lab}"]')
        else:
            out.append(f'  {n}["{lab}{held}"]')
    # The same entries `dot()` draws, from the same model and under the same bound, so the
    # picture and the source a reader copies out cannot describe different graphs.
    for b in c.entries:
        lab = b.label.replace('"', "'")
        out.append(f'  {ids[b.id]}[/"{lab}"/]')
    for src, dst in c.entry_arrows():
        out.append(f"  {ids[src]} ==> {ids[dst]}")
    for b in c.ports:
        out.append(f'  {ids[b.id]}(["{b.label}"])')
    for src, dst in sorted(c.inside):
        out.append(f"  {ids[src]} --> {ids[dst]}")
    for src, dst in sorted(list(c.out) + list(c.into)):
        out.append(f"  {ids[src]} -.-> {ids[dst]}")
    return "\n".join(out)


# ── asking a compartment about one box ──────────────────────────────────────────────

def find_box(comps: dict[str, Compartment], box_id: str) -> tuple[Compartment, Box] | None:
    """The compartment a box belongs to, and the box, or `None` for neither.

    A box id begins with its plate, so the compartment is read off the id rather than
    searched for -- fifty-three compartments times a hundred boxes is a scan nobody
    needs to do to answer a click. A port is findable too: it is a real thing in the
    drawing, and refusing to look one up here would push that distinction into every
    caller (rule 51).
    """
    c = comps.get(box_id.partition("|")[0])
    if c is None:
        return None
    for b in (*c.boxes, *c.ports, *c.entries):
        if b.id == box_id:
            return c, b
    return None


def flow_of(c: Compartment, box_id: str) -> dict[str, list[dict[str, Any]]]:
    """What reaches a box, and what it reaches -- named, counted, and kept apart.

    Both halves are read off the counters the compartment already built, never
    recomputed from the model: the diagram's picture and the inspector's answer are
    then the same arithmetic, so a reader who counts the arrows and reads the number
    cannot find them disagreeing (rule 13).

    `inside` and the two crossing counters are merged here on purpose and marked with
    `crosses`. The picture keeps them apart because they answer different questions
    about the *drawing* -- what does this do among itself, what does it hang off. The
    inspector's question is the reader's: **what talks to this thing**, and an answer
    that splits one routine's neighbours by whether they happened to be drawn on the
    same plate would be an answer about the layout.
    """
    label: dict[str, str] = {b.id: b.label for b in (*c.boxes, *c.ports)}
    kind: dict[str, str] = {b.id: b.kind for b in (*c.boxes, *c.ports)}

    def rows(pairs: list[tuple[tuple[str, str], Counter[str]]], mine: int, theirs: int,
             crosses: bool) -> list[dict[str, Any]]:
        out = []
        for pair, kinds in pairs:
            if pair[mine] != box_id:
                continue
            other = pair[theirs]
            out.append({
                "id": other,
                "label": label.get(other, other),
                "box_kind": kind.get(other, ""),
                "weight": sum(kinds.values()),
                # What sort of flow it is, heaviest first. Dropped for the whole life of
                # this pane, so a database touch and a call read identically.
                "kinds": [k for k, _ in kinds.most_common()],
                # The edge as the drawing names it, so a row here and an arrow there are
                # the same control (rule 30). Both directions, because a row is `other`
                # and the edge is always (source, target).
                "edge": (edge_id(other, box_id) if mine == 1 else edge_id(box_id, other)),
                # A crossing does not end where it appears to: the far end is a port
                # standing for a whole compartment, not the thing that was called
                # (rule 23's argument, one level up). Marked rather than hidden.
                "crosses": crosses,
            })
        return sorted(out, key=lambda r: (-r["weight"], r["label"].lower()))

    inside = list(c.inside.items())
    return {
        "in": rows(inside, 1, 0, False) + rows(list(c.into.items()), 1, 0, True),
        "out": rows(inside, 0, 1, False) + rows(list(c.out.items()), 0, 1, True),
    }


def edge_flow(c: Compartment, src: str, dst: str) -> tuple[list[str], int] | None:
    """The kinds carried by one arrow and its weight, or `None` if there is no such arrow.

    All three lanes are asked, because a reader clicking an arrow does not know or care
    which lane the drawing filed it in -- `inside`, `out` and `into` are a fact about the
    *picture* (rule 23's within-plate links and crossings), not about the edge. `None`
    rather than an empty answer: "there is no arrow between these two" and "the arrow
    carries nothing" are different claims, and an empty panel states the second.
    """
    for lane in (c.inside, c.out, c.into, c.entered):
        kinds = lane.get((src, dst))
        if kinds:
            return [k for k, _ in kinds.most_common()], sum(kinds.values())
    return None


def edge_payload(c: Compartment) -> dict[str, dict[str, Any]]:
    """Every arrow the drawing carries, by the id `dot()` wrote on it.

    So a hover over an arrow costs no request at all -- the kinds and the weight are what a
    card would say, they are already computed here, and asking the server for them would be
    a fetch per arrow for a fact that rode in with the picture. Same reasoning that made the
    box card `fetches: false`.

    Crossings are marked, because an arrow that ends at a port does not end where it appears
    to (rule 23) and a card that did not say so would be describing a connection to a place
    rather than to a thing.
    """
    ports = {b.id for b in c.ports}
    entries = {b.id for b in c.entries}
    out: dict[str, dict[str, Any]] = {}
    for lane in (c.inside, c.out, c.into, c.entered):
        for (src, dst), kinds in lane.items():
            out[edge_id(src, dst)] = {
                "from": src, "to": dst,
                "kinds": [k for k, _ in kinds.most_common()],
                "weight": sum(kinds.values()),
                "crosses": src in ports or dst in ports,
                # **An entry arrow is not a call**, and it is marked here so nothing
                # downstream has to work that out from a box kind. It says *this is how
                # these routines get started*; there is no call site to open, because the
                # caller is the operating system.
                "entry": src in entries,
            }
    return out


def box_payload(b: Box) -> dict[str, Any]:
    """A box as the wire carries it -- the shape the drawing's `by_id` map already uses."""
    return {"id": b.id, "label": b.label, "kind": b.kind, "holds": b.holds,
            "members": list(b.members), "labels": list(b.labels), **b.detail}


# ── the second level: one box, opened ───────────────────────────────────────────────

def build_inside(box_id: str, box: Box, members: list[dict[str, Any]],
                 inner: list[dict[str, Any]], out: list[dict[str, Any]],
                 into: list[dict[str, Any]], touches: list[dict[str, Any]],
                 box_of: dict[str, str], label_of: dict[str, str]) -> Compartment:
    """A fold's own routines as a compartment, so the same drawing code renders it.

    **Not a new picture, a second altitude of the one there is.** A `Compartment` is
    "boxes, and the flow among them"; at the first level a box is a class and at the
    second it is a routine. `dot()` and `mermaid()` take a `Compartment` and neither
    knows or needs to know which level it came from -- so a shape, a colour or a fix
    applied to one is applied to both, and the two cannot drift into being two views
    (rule 51, and design rule 2's reasoning about one instrument).

    **The data bounds it and no rule has to.** A class holds a median of 4 to 6 routines
    across Mensores' 623 files, and exactly one module exceeds a hundred. That is a
    diagram either way; the count is stated regardless, because a picture that is
    complete and a picture that was cut look the same (design rule 1).

    A crossing ends at a **port** named for the box on the other side rather than for the
    routine, exactly as the first level does -- one routine calling forty elsewhere is the
    whole program again (rule 19), and a port is a place to click.
    """
    c = Compartment(id=box_id, name=box.label)
    seen: dict[str, Box] = {}

    for m in members:
        mid = str(m["id"])
        b = Box(mid, _clip(str(m["name"])), "routine", holds=1,
                members=[mid], labels=[str(m["name"])],
                detail={"qualname": m.get("qualname"), "line": m.get("line_start"),
                        "is_async": m.get("is_async"), "returns": m.get("returns")})
        seen[mid] = b
        c.boxes.append(b)

    # What the routines touch, folded per kind exactly as the first level folds it: a
    # cylinder is the bottom of the flow, and twelve separate SELECTs against one table
    # is a picture of a query log rather than of a program.
    for t in touches:
        what = str(t.get("kind") or "")
        tid = _box_id(box_id, "touch", what)
        tb = seen.get(tid)
        if tb is None:
            tb = Box(tid, _clip(what), "touch", detail={"what": what})
            seen[tid] = tb
            c.boxes.append(tb)
        src = seen.get(str(t.get("routine_id") or ""))
        if src is not None:
            add_flow(c.inside, src.id, tid, "TOUCH", int(t.get("weight") or 1))

    for e in inner:
        a, b2 = seen.get(str(e["src"])), seen.get(str(e["dst"]))
        if a is not None and b2 is not None:
            add_flow(c.inside, a.id, b2.id, "CALL", int(e["weight"]))

    ports: dict[str, Box] = {}

    def port(other_id: str) -> Box | None:
        """The box on the far side, as a place. `None` when we cannot name one.

        A callee this compartment cannot place -- an external, or something merged away --
        gets no port at all rather than one labelled with a raw id. Rule 30: a control
        that carries no identity resolves to nothing, and a port is a control.
        """
        far = box_of.get(other_id)
        if not far:
            return None
        if far not in ports:
            p = Box(_box_id(box_id, "port", far), _clip(label_of.get(far, far)),
                    "port", detail={"box": far})
            ports[far] = p
            c.ports.append(p)
        return ports[far]

    for e in out:
        mine, far = seen.get(str(e["mine"])), port(str(e["other"]))
        if mine is not None and far is not None:
            add_flow(c.out, mine.id, far.id, "CALL", int(e["weight"]))
    for e in into:
        mine, far = seen.get(str(e["mine"])), port(str(e["other"]))
        if mine is not None and far is not None:
            add_flow(c.into, far.id, mine.id, "CALL", int(e["weight"]))

    c.boxes.sort(key=lambda x: (x.kind, int(x.detail.get("line") or 0), x.label.lower()))
    c.ports.sort(key=lambda x: (x.label.lower(), x.id))
    return c


def box_index(comps: dict[str, Compartment]) -> tuple[dict[str, str], dict[str, str]]:
    """Which box each node lives in, and what each box is called.

    Built from the compartments rather than from a second walk over the store, so the
    second level places a crossing in exactly the box the first level drew it in. Two
    passes over ten thousand members, held on the base beside the compartments.
    """
    box_of: dict[str, str] = {}
    label_of: dict[str, str] = {}
    for c in comps.values():
        for b in c.boxes:
            label_of[b.id] = b.label
            for m in b.members:
                box_of[m] = b.id
    return box_of, label_of
