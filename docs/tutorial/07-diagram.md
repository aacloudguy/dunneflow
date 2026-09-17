# 7. Diagram

The stack draws all 1,773 things. This draws thirty-one, and answers a different question:
**what is this one part shaped like, and what flows through it.**

![Diagram mode with the web compartment selected. A dropdown reads "web — 31 boxes" and the line beneath it reads "31 boxes over 315 routines · 46 flows within · 59 crossing to 14 other compartments (not drawn) · 2 with no flow either way · entered from 4 ways in · drawn in 21 ms · double-click a box to open it". Below are a "show crossings" checkbox, a "fit" button, and the text "· 1 box selected" with a "frame it" button. Thirty-one small labelled boxes are joined by arrows, with serve.py highlighted](images/07-diagram-compartment.jpg)

## The line under the dropdown

Every number in it earns its place, and together they are a complete description of what
you are looking at:

| | |
|---|---|
| **31 boxes over 315 routines** | a fold, and what it folded |
| **46 flows within** | arrows drawn inside this compartment |
| **59 crossing to 14 other compartments (not drawn)** | arrows that leave |
| **2 with no flow either way** | boxes here that connect to nothing |
| **entered from 4 ways in** | how the outside world gets in |
| **drawn in 21 ms** | |

The crossings are **counted always and drawn only when you ask**. Turn them on and the
picture connects everything to everything and stops packing; leave them off and the count
still tells you they are there. What is not allowed is for them to be silently absent.

And `2 with no flow either way` is the sort of row most tools would drop. A box that
connects to nothing is not an error, but it is *interesting*, and you would never find it
by looking.

## Your selection, and where it went

The head says one of exactly three things:

- nothing, when nothing is selected;
- **`1` box selected**, with a **frame it** button;
- *what you picked is not in this compartment.*

That third one used to be conveyed by saying nothing at all, which is indistinguishable
from a control that is broken.

We still have `_reveal_linux` selected from chapter 3, and it lives in `serve.py`, which is
in `web`. So: **1 box selected**. The box is marked — but fitted to this pane, a marked box
is a few pixels across, and *marked but too small to see* looks exactly like *not marked*.
Hence the sentence. The count is written out in words because the drawing cannot be trusted
to convey it at this size.

## frame it

Press it.

![The same compartment after pressing frame it. The camera has zoomed to serve.py, drawn bold with 20 functions, surrounded by the boxes an arrow joins it to: _Handler with 74 methods, _Live with 26 methods, serve, cover.py with 4 functions, packages.py with 5 functions, corpus.py with 6 functions, layout.py with 3 functions, graph.py with 10 functions, documents.py and search](images/07-diagram-framed.jpg)

The camera moved to the selection **and everything an arrow joins it to** — so you land on
a neighbourhood rather than on one box with no context. `serve.py` is bold in the middle;
around it are `_Handler` (74 methods), `_Live` (26 methods), `graph.py`, `layout.py`,
`corpus.py`, `documents.py`, `packages.py`, `cover.py`, `search`.

That picture is a decent one-glance summary of how the dashboard is put together, and it
took one click from a search box.

**Nothing frames itself.** Selecting a routine elsewhere marks the right boxes and leaves
the camera exactly where it was. Framing is offered, one click away, and never taken on
your behalf — the same rule the table follows with its **Go to it** button. And **fit** is
untouched, so the way back out is always one press.

## Opening a box

Double-click one and the boxes become the routines inside it, described by the same
sentence — including which box you are inside, so it is never a drawing you cannot place.
**‹ out** goes back up.

This second level is asked for on demand rather than built with the rest, and the reason is
arithmetic: a compartment is fifty-odd drawings from one pass over the model; a box is one
of thousands.

## Arrows open too

Every arrow is clickable, and it carries both its identity and its kind — a call and a
touch between the same two boxes are **one arrow that can tell you which it is**, rather
than two arrows or one ambiguous one.

Click one and you get the flow: every call site, with **the arguments as written**, beside
the callee's declared parameters. Not re-printed from a parse tree — sliced out of the
file's own bytes, and never shortened.

An argument is lined up against a parameter only where the source settles it. Where it
cannot be, the row says why, because a blank beside an argument would read as *no such
parameter* — a different claim, and a false one.

---

Next: [8. Two versions](08-two-versions.md)
