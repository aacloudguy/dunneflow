# 10. Diagram

One compartment, drawn as a diagram.

![Diagram mode showing the render compartment: a dropdown reading "render — 14 boxes", the line "14 boxes over 88 routines · 23 flows within · 42 crossing to 8 other compartments (not drawn) · drawn in 3 ms · double-click a box to open it", a "show crossings" checkbox, a "fit" button, and fourteen labelled boxes joined by arrows](images/10-diagram-compartment.jpg)

The stack draws every one of ten thousand things. This draws forty boxes and answers a
different question: **what is this part shaped like, and what flows through it.**

## What a box is

A class, a file's loose functions, or a kind of boundary. The dropdown lists every
compartment with how many boxes it holds; pick one.

The line under it is the whole of what you are looking at, and every number in it earns
its place:

- **14 boxes over 88 routines** — a fold, and what it folded.
- **23 flows within** — arrows drawn inside this compartment.
- **42 crossing to 8 other compartments (not drawn)** — arrows that leave. Counted always,
  drawn only when you ask, because drawn they connect everything to everything and nothing
  packs. **show crossings** turns them on.
- **entered from 1 way in** — how the outside world gets here.
- **drawn in 3 ms.**

**fit** frames the whole drawing.

## Opening a box

Double-click one.

![The second level: "‹ out markdown.py" and "12 routines · 25 flows within · 32 crossing to 19 other boxes (not drawn) · drawn in 3 ms", with the routines inside markdown.py drawn as boxes joined by arrows, and the inspector on the right listing HOLDS 12 with a code button beside each](images/10-diagram-box-open.jpg)

Now the boxes are routines and the same sentence describes them — including *which box
you are inside*, so it is not a drawing you cannot place. **‹ out** goes back up.

This second level is asked for on demand rather than built with the rest. A compartment is
fifty-odd drawings from one pass over the model; a box is one of thousands. Opening one
takes about 15 ms for a small class and 170 ms for a large one.

## Arrows open too

Every arrow is clickable, and it carries both its identity and its kind — a call and a
touch between the same two boxes are one arrow that can tell you which it is.

Clicking one opens the flow: **every call site, with the arguments as written, beside the
callee's declared parameters**. For an arrow into a boundary you get the SQL and the
network operations instead.

The arguments are the ones from the source, sliced out of the file's own bytes — never
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
