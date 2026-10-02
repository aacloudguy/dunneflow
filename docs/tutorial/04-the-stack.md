# 4. The stack

Press **Graph** and you get the whole program at once: 2,690 things, arranged on 25 plates,
one plate per package or boundary kind. It is a stack of 2-dimensional knowledge graphs.
Call it a 2.5D graph.

![Graph mode with resolve.entrypoints.entrypoints_from_manifests selected, seen from the side as a tall column of grey nodes. The heads-up panel reads "60 fps · 2,690 nodes · 25 plates" and below it "on pkg:resolve, pkg:cli, pkg:store, ext:DATABASE · entrypoints_from_manifests · 9 nodes · 5 within · 3 crossing · 2,681 dimmed · focus: only what is lit answers", over the buttons undo, redo, you are here, focus (on), snap to fit, top-down, tilt, benchmark and clear. The spacing panel is folded to one line, "spacing 1.50× · spread 1.00 / 1.00 / 0.35 · plate width 1.00", and the plate list is folded to a rail on the right edge marked PLATES. A handful of lit nodes and the coloured edges between them run down the column; everything else is dimmed](images/04-the-stack.jpg)

## Why a stack and not a graph

A call graph of a real program drawn as a flat picture is a hairball. Everyone has seen one;
nobody has ever learned anything from one.

So DunneFlow gives the picture a third axis and puts each package on its own plate. You are
looking down through a stack of discs. What that buys is the one thing a hairball cannot
give you: **an edge that stays inside a plate and an edge that crosses between plates look
different**, and the second kind is what you actually care about when you are orienting.

## What the plate list tells you

Open the **Plates** panel and read it as a table of contents, largest first:

| | |
|---|---|
| `web` | 609 |
| `extractors` | 402 |
| `resolve` | 356 |
| `plugins` | 197 |
| `DATABASE` | 184 |
| `render` | 119 |

Two kinds of thing are in that list and they are deliberately not separated. `web`,
`extractors`, `resolve` are packages — code this program declares. `DATABASE`, `STDIO`,
`FILE`, `ARTEFACT` are boundary kinds — the outside world, given plates of its own.

That is the whole model in one list: **your code, and the things it touches, drawn on the
same picture at the same scale.** `DATABASE` being the fifth largest plate — bigger than
`render`, the package that writes every document the map produces — tells you more about
DunneFlow in one glance than any amount of reading would.

At the bottom: **2,690 drawn · 9 plates merged into `<small>`, holding 35**. Plates too sparse to be worth
their own disc are merged — five small packages into `<small>`, four small boundary kinds
into `<small outside>` — and the merge *says so*, with the count. You are never quietly
shown a partial picture.

## Focus

The selection from the last chapter is still live, and the HUD says what that costs:

> on pkg:resolve, pkg:cli, pkg:store, ext:DATABASE · `entrypoints_from_manifests` ·
> **9 nodes** · 5 within · 3 crossing · **2,681 dimmed** · focus: only what is lit answers

Nine nodes are lit, on four plates, and 2,681 are dimmed. Five of the lit edges stay inside
a plate; three cross to another.

**Dimmed, not hidden**, and the difference matters enough that DunneFlow has a rule about
it. A hidden node is gone and you cannot tell whether it was ever there; a dimmed one is
still in the picture, still in its place, still showing you how much of the program you are
*not* looking at. `2,681 dimmed` is a useful number. `9 nodes` on an empty screen is not.

That is the default, and it is a default rather than a law. When the dimmed thousands are
in the way of the few you are reading, the **Plates** panel has a control for it:
**unselected**, set to **hidden** instead of **dimmed**, and the stack draws only what is
lit.

![Graph mode with cli.cmd_serve selected and unselected nodes set to hidden. The stack is gone except for about a dozen lit nodes and the coloured edges between them, drawn on an empty canvas; the heads-up panel still reads "60 fps · 2,690 nodes · 25 plates". The trail reads "dunneflow › entrypoints_from_manifests › Shape › Graph › cmd_serve", and the inspector on the right shows cli.cmd_serve, cli.py:2033–2100, with IN 2 and OUT 14 call sites](images/04-hidden-unselected.jpg)

The heads-up panel still says 2,690 nodes. What is hidden is still counted; you have only
asked not to see it.

## The controls, and the one that surprised me

The HUD opens on sliders: **spacing**, three **spread** axes, **plate width**. They are
worth a minute because they are not decoration — a stack of 2,690 dots has a legibility
problem and these are how you solve it for the question you happen to be asking.

Two of the more interesting ones:

**nodes: by plate** — *"size says degree and how sparse the plate is"*. A node's size is
not just how connected it is; it is also how much room its plate has. The alternative,
**one size**, draws every plate at the *tightest* plate's size — never an average, so that
every other plate can afford it. It is the kind of choice that only shows up when you care
whether two dots can ever overlap. The X and Y axes are independent so you can create
renderings for reports if necessary, or make pretty pictures, and to keep the nodes from colliding.

**layout: by structure** — the default arrangement. The other is a force layout that
arranges each plate by what connects to what, and it is substantially better at what it
does; it is off by default because "better at what it does" and "the right default" are not
the same claim.

**follow: callers and callees** — what a selection drags into the light with it.

## Two drawings, one view

Top right of the centre pane there are two buttons, **Stack** and **Overview**. They are not
two modes — they are two drawings of the *same* view, which is why they sit inside Graph
rather than beside it. Promoting a layout to a mode would say the two answer different
questions, and they do not.

![Overview, the other drawing of the same view, with entrypoints_from_manifests still selected in the inspector. A header reads "24 packages · 86 connections between them · 7 external systems", then "Drawing the 45 heaviest connections — the spine. 41 lighter ones and all 36 boundary touches are not drawn: click any package to see every connection it has, at any weight.", then "Columns are hops from a way in. Depth reads left to right; a rank too deep for one column wraps rather than growing taller." The first column holds the four ways in, highlighted: web 352 routines, ingest 91, mcp 59, cli 47, each marked "way in". The second holds extractors 296, resolve 199, render 103, detectors 56, store 49, sourcedb 36 and anomalies 26; the third revisions 14, schema 11, runtime 10, sql 9, macapp 4, canonical 3 and lookup 2, and the edge of a fourth shows at the right. Grey connections fan out from the first column to the second](images/04-overview.jpg)

Overview is the stack flattened into packages, laid out left to right by how many hops each
is from a way in: **24 packages · 86 connections between them · 7 external systems**. It
draws the 45 heaviest connections and says, in the same breath, that 41 lighter ones and
all 36 boundary touches are not drawn — and how to see them. It is the picture to start
from on a program you have never seen; the stack is the one to come back to once you have
picked something.

---

Next: [5. Table and Code](05-table-and-code.md)
