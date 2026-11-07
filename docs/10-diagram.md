# 10. Diagram

One compartment, drawn as a diagram.

![Diagram mode showing the render compartment: a dropdown reading "render — 14 boxes", the line "14 boxes over 91 routines · 23 flows within · 45 crossing to 10 other compartments (not drawn) · drawn in 7 ms · double-click a box to open it", a "show crossings" checkbox, "colour by: nothing", a "fit" button and "· what you picked is not in this compartment"; below, fourteen labelled boxes — snapshot.py, index.py and markdown.py at the top, eleven files and the Stamp class in a row, page.py at the foot — joined by arrows](images/10-diagram-compartment.jpg)

The stack draws all 2,692 nodes of this map at once. This draws fourteen boxes and answers
a different question: **what is this part shaped like, and what flows through it.**

## What a box is

A class, a file's loose functions, what one macro wrote, or a kind of boundary. The dropdown lists every
compartment with how many boxes it holds; pick one.

The line under it is the whole of what you are looking at, and every number in it earns
its place:

- **14 boxes over 91 routines** A fold, and what it folded.
- **23 flows within** Arrows drawn inside this compartment.
- **45 crossing to 10 other compartments (not drawn)** Arrows that leave. Counted always,
  drawn only when you ask, because drawn they connect everything to everything and nothing
  packs. **show crossings** turns them on.
- **entered from … ways in** How the outside world gets here, said only where it does:
  `web` is entered from 4, and `render` from none, so its line leaves the clause out.
- **drawn in 4 ms.**

**fit** frames the whole drawing.

**A dashed box is what a macro wrote**, one per macro per file, counted. `DECLARE_CYCLE_STAT` writes
a class of seven accessors for every stat, and a drawing of those is a drawing of nothing. Select it
and the inspector lists them all; open it and they are drawn. A way in is never folded into one:
`main` written by a macro is drawn as itself.

## Where your selection went

The diagram is one compartment, and whatever you have selected elsewhere may or may not be
in it. The line says which, in one of three ways:

- **nothing at all**, when nothing is selected.
- **`1` box selected**, with a **frame it** button beside it.
- **what you picked is not in this compartment** is the actual answer, and used to
  be given by saying nothing.

![The diagram's header, close up: "render — 14 boxes", the line "14 boxes over 91 routines · 23 flows within · 45 crossing to 10 other compartments (not drawn) · drawn in 7 ms · double-click a box to open it", and under it "show crossings", "colour by: nothing", "fit", then "· 1 box selected" and a "frame it" button](images/10-frame-it.png)

**frame it** moves the camera to your selection *and everything an arrow joins it to*, so
you land on the neighbourhood rather than on one box with no context. **fit** is untouched,
so the way back out is always one press.

Nothing frames itself. Picking a routine in the navigator marks the right boxes and leaves
the camera where it is. At that point, a list that moves the picture under you is how you lose the thing
you were looking at. Framing is offered, one click away, and never taken on your behalf.

> This is worth knowing because a correct selection can be invisible. Fitted to a narrow
> pane, a marked box can be a handful of pixels across, and *marked but too small to see*
> looks exactly like *not marked*. That is the reason the count is written out in words
> rather than left to the drawing to convey.

## Opening a box

Double-click one.

![The second level: "render — 14 boxes", "‹ out" and "markdown.py", then "13 routines · 27 flows within · 36 crossing to 21 other boxes (not drawn) · drawn in 4 ms" and "· you are inside what you picked"; the routines inside markdown.py drawn as boxes, render_all at the top fanning out to _flows, _routines, _data, _boundaries, _governance, _overview and _entrypoints, most of them writing to a FILE cylinder and calling _esc at the foot; the inspector on the right is headed render.markdown, render/markdown.py:42–626, ANALYSED · FILE · 13 folded, and lists HOLDS 13 with a code button beside each. The navigator is still filtered to the search "cmd_serve"](images/10-diagram-box-open.jpg)

Now the boxes are routines and the same sentence describes them; the breadcrumb above it
names the box you are inside, and with a selection made first the sentence adds whether
your pick is in here, so it is not a drawing you cannot place. **‹ out** goes back up.

The inspector follows you in. Opening a box selects it, and the box's own inspector lists
what it holds, each with a **code ▸** button that opens that routine's lines:

![The inspector for the opened box: render.markdown, render/markdown.py:42–626 with a "code ▸" button, the badges ANALYSED, FILE and "13 folded", "◇ Keep this" and "Collapse all", then "HOLDS 13" — _esc, render_all, _overview, _entrypoints, _unclaimed_marks, _count_commands, _tree_list, _flows, _flow_inventory, _routines, _data, _boundaries, _governance — each a signature cut short at its tail, with a code button and its line number on the same line; then IN 2, snapshot.py and cli, and OUT 18 beginning with page.py](images/10-box-inspector.png)

This second level is asked for on demand rather than built with the rest. A compartment is
one of 25 drawings that come out of one pass over the model; a box is one of 197. On this
map, fetching one takes a few milliseconds for a small file and about 15 ms for the largest
class in the program, `web.serve._Handler`, which holds 74 routines.

## Arrows open too

Every arrow is clickable, and it carries both its identity and its kind. A call and a
touch between the same two boxes are one arrow that can tell you which it is.

Clicking one opens the flow: **every call site, with the arguments as written, beside the
callee's declared parameters**. For an arrow into a boundary you get the SQL and the
network operations instead.

![An arrow opened inside entrypoints.py, in the "resolve — 40 boxes" compartment: the line says "12 routines · 11 flows within · 18 crossing to 8 other boxes (not drawn) · drawn in 2 ms", then "· 2 boxes selected" and a "frame it" button, and the arrow from _target_routine to exact is lit at both ends, entrypoints_from_manifests above them. The inspector is headed "_target_routine → exact", routine → routine, FLOW · CALL · 2 along it, and lists CALL SITES 2: exact at :102 passing module, and exact at :107 passing module[len(prefix) + 1:], each lined up against "→ name: str" and the declared signature exact(name: str) → str | None; then TOUCHES 0, "Nothing along this arrow touches a boundary, a table, a remote or a named file.", and under it the note that ends "92% of arguments on a resolved call bind; the rest say why they do not."](images/10-arrow-flow.jpg)

> **Aim for the middle of the arrow.** An arrow is a line two pixels wide, and a box is
> drawn over the ends of its own arrows, so a click close to either box picks the box. Click
> a stretch of the line well clear of both boxes. You know it worked when both ends light up,
> the note above the drawing says **2 boxes selected**, and the inspector is headed with the
> arrow itself, for example *\_target\_routine → exact*. Holding the pointer over a line first
> shows a card saying *Click to see what flows here.*, which confirms you are on it.

The arguments are the ones from the source, sliced out of the file's own bytes. These are never
re-printed from a parse tree, and never shortened. One argument on a real codebase is a
1,347-line frozen set, and it is stored whole.

An argument is lined up against a parameter only where the source settles it: a keyword
argument by name always; a positional one only when the callee is resolved, takes no
`*args`, and the receiver question is answerable. `self.f(x)` skips a parameter;
`obj.f(x)` cannot be told from `Cls.f(obj, x)` and so binds nothing. Across a real corpus
that is **92% of arguments on a resolved call**, and every one of the remaining 8% states
why it could not be bound — because a blank beside an argument would read as *no such
parameter*, which is a different and false claim.

## Nothing is bounded silently

Where a diagram leaves something out, it says what and how many. The complete listing sits
beside every bounded drawing, and that is not a courtesy: a node graph stops being
navigable with a screen reader somewhere past fifty nodes, so the listing is the accessible
path rather than a fallback.

---

Next: [11. Shape](11-shape.md)
