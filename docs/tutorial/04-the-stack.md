# 4. The stack

Press **Graph** and you get the whole program at once: 1,773 things, arranged on 22 plates,
one plate per package or boundary kind. It is a stack of 2-dimensional knowledge graphs. 
Call it a 2.5D graph.

![Graph mode with web.serve._reveal_linux selected. The HUD reads "60 fps · 1,773 nodes · 22 plates" and below it "on pkg:web, ext:<small outside> · _reveal_linux · 4 nodes · 2 within · 2 crossing · 1,769 dimmed · focus: only what it is answers". Controls for spacing 1.50×, spread 1.00/1.00/0.35 and plate width 1.00 are open, with nodes sized "by plate" and layout "by structure". On the right the plate list runs web 592, resolve 236, DATABASE 170, extractors 117, render 116, detectors 62, STDIO 54, schema 53, cli 45, sourcedb 45, store 39, anomalies 38, sql 35, FILE 28, ARTEFACT 27, docstore 26, migrate 23, revisions 18, small outside 14, small 13, walk 13, runtime 9. Below it "1,773 drawn · 7 plates merged into <small>, holding 27"](images/04-the-stack.jpg)

## Why a stack and not a graph

A call graph of a real program drawn as a flat picture is a hairball. Everyone has seen one;
nobody has ever learned anything from one.

So DunneFlow gives the picture a third axis and puts each package on its own plate. You are
looking down through a stack of discs. What that buys is the one thing a hairball cannot
give you: **an edge that stays inside a plate and an edge that crosses between plates look
different**, and the second kind is what you actually care about when you are orienting.

## What the plate list tells you

Read it as a table of contents, largest first:

| | |
|---|---|
| `web` | 592 |
| `resolve` | 236 |
| `DATABASE` | 170 |
| `extractors` | 117 |
| `render` | 116 |

Two kinds of thing are in that list and they are deliberately not separated. `web`,
`resolve`, `extractors` are packages — code this program declares. `DATABASE`, `STDIO`,
`FILE`, `ARTEFACT` are boundary kinds — the outside world, given plates of its own.

That is the whole model in one list: **your code, and the things it touches, drawn on the
same picture at the same scale.** `DATABASE` being the third largest plate tells you more
about DunneFlow in one glance than any amount of reading would.

At the bottom: **7 plates merged into `<small>`, holding 27**. Plates too sparse to be worth
their own disc are merged — and the merge *says so*, with the count. You are never quietly
shown a partial picture.

## Focus

The selection from the last chapter is still live, and the HUD says what that costs:

> on pkg:web, ext:`<small outside>` · `_reveal_linux` · **4 nodes** · 2 within · 2 crossing ·
> **1,769 dimmed** · focus: only what it is answers

Four nodes are lit and 1,769 are dimmed. Two of the lit edges stay inside `web`; two cross
to another plate.

**Dimmed, not hidden**, and the difference matters enough that DunneFlow has a rule about
it. A hidden node is gone and you cannot tell whether it was ever there; a dimmed one is
still in the picture, still in its place, still showing you how much of the program you are
*not* looking at. `1,769 dimmed` is a useful number. `4 nodes` on an empty screen is not.

## The controls, and the one that surprised me

The HUD opens on sliders: **spacing**, three **spread** axes, **plate width**. They are
worth a minute because they are not decoration — a stack of 1,773 dots has a legibility
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

Top left there are two buttons, **Stack** and **Overview**. They are not two modes — they
are two drawings of the *same* view, which is why they sit inside Graph rather than beside
it. Promoting a layout to a mode would say the two answer different questions, and they do
not.

---

Next: [5. Table and Code](05-table-and-code.md)
