# 6. Graph

The whole program at once, as a stack of plates. Also known as 2.5D, or two and a half dimensional.

![Graph mode with nothing selected: the stack of coloured dots, a wide plate of teal, blue and grey at the top narrowing to a thin column above a smaller purple plate at the bottom; the HUD on the left reading "60 fps · 4,410 nodes · 30 plates — nothing selected — all links hidden; pick two plates to see what crosses between them, or click a node" above the undo, redo, you are here, focus, snap to fit, top-down, tilt and benchmark buttons; the sliders folded to one line, "spacing 1.50× · spread 1.00 / 1.00 / 0.35 · plate width 1.00"; the Plates panel folded to a rail labelled PLATES; and the inspector on the right reading "Nothing selected."](images/06-graph-stack.jpg)

## What you are looking at

**A plate is a package**, or a kind of boundary or grouping. Everything the program declares sits on
the plate it belongs to, and the plates are stacked so you can see the whole program's
shape without anything overlapping anything else.

**A node is one thing the program declares** A routine, a constant, a structure. It is
drawn as a dot rather than a labelled box because at fifteen thousand of them a labelled
box is not a picture, it renders as a wall.

The legend on the right, **Plates**, lists every plate with what it holds. Click one to
select it; drag to reorder. Its **⇥** sends it to a rail at the edge, which is the
quickest way to give the stack the room. When the middle pane is too narrow for both, as it
is in the picture above with the navigator and the inspector open, the panel starts on its
rail by itself; click the rail to bring it back.

**Some nodes are shadows and are never drawn.** When a routine on one plate calls a
routine on another, the model puts a placeholder for the far end on *this* plate, so the
crossing can be expressed as a force within each plate. You never see them. They are what
lets both ends of a call pull on each other's layout.

## Making sense of it

Nothing is lit until you pick something. With nothing selected all links are hidden. Two
hops from any routine is most of the program again, and a picture of most of the program
is a picture of nothing.

Pick a node and the rest dims:

![Graph mode with cmd_serve selected: everything except its neighbourhood is dimmed to grey, its links drawn between the few lit nodes, and the HUD says "60 fps · 4,410 nodes · 30 plates — on pkg:cli, pkg:runtime, pkg:web, ext:FILE · cmd_serve · 9 nodes · 4 within · 7 crossing · 4,401 dimmed · focus: only what is lit answers". An amber pointer stands over the selection, the navigator shows its one match for "cmd_serve", and the inspector on the right shows cli.cmd_serve, IN 2 and OUT 14 call sites.](images/06-graph-selected.jpg)

The HUD states exactly what it did: how many nodes are lit, how many are dimmed, and
whether the dimmed ones still answer a hover. **Dimming says what is not yours; it does
not say which one is yours** so there is also a pointer standing over your selection,
and a ring with four ticks around it. Both can be turned off.

## The controls

**Along the top of the HUD:**

| | |
|---|---|
| **undo** / **redo** | step back and forward through selections |
| **you are here** | go back to the view you found the current selection in |
| **focus** | whether the dimmed thousands answer a hover, or only what is lit |
| **snap to fit** | frame the selection, or everything when nothing is selected |
| **top-down** / **tilt** | two camera angles |
| **benchmark** | measure the frame rate on your machine |
| **clear** | drop the selection — it appears once there is one |

**The sliders** are three independent axes plus two. They fold away under the buttons to
a single line that still states every value — *spacing 1.50× · spread 1.00 / 1.00 / 0.35 ·
plate width 1.00* — so a folded panel never hides what is in force.

- **spacing** How much clear space a node keeps, as a multiple of its own diameter.
  Smaller means bigger dots. You set the room, and the radius follows from it. This is
  what guarantees that no two nodes ever touch.
- **across** and **deep** widen a plate in X and Y. This is what separates nodes that
  fuse into a mass at large sizes.
- **stack** is the gap *between* plates.
- **width** is how much a plate's width says about how much it holds. At `0` every plate
  is drawn the same width whether it holds hundreds of things or six. At `1` the area is
  proportional to the contents, so the footprint means *how much is here*.

**nodes** Whether a node's size says how sparse its plate is, or only how connected it
is. Both readings are good, so both are built.

**layout** How a plate arranges what it holds.

- **by structure** is a sunflower spiral ordered by how connected each node is. Even,
  instant, and blind to which nodes are connected — so links cross it at every angle.
- **by connection** runs a force solve until connected things sit near each other, with
  the shadows pulling for the plates they stand in for. On a large program's busiest
  plate that takes 328,531 edge crossings down to 27,291 — **91.7% fewer**, the figure the
  button's own tooltip gives.

  It costs about **89 ms with a GPU and 9.7 seconds without one**, paid when you ask for
  it. The page says which of the two actually drew it.

**follow** Which connections a picked node pulls in: `callers and callees`, `callers
only`, or `callees only`. Standing on a routine and asking *callers only* is the fastest
way to see who depends on you and nothing else.

**plates** Draw the plate discs themselves. Off by default: at fifteen thousand nodes a
full set of discs reads as a solid cylinder, and the stack is an abstraction rather than an
object. The two or three plates your selection actually touches are drawn faintly anyway,
because otherwise nothing on screen answers *which plate am I looking at*.

**reset sliders** Puts the five back where they started.

## Under the legend

These sit at the foot of the Plates panel, and fold away with it: if you have folded Plates
to its rail to make room for the stack, click the **PLATES** rail to get them back.

**Detail** The altitude. `every routine` draws everything the program declares. `one node
per file` folds each file into one node and each boundary kind into one. It is a second way
of looking at the same facts and not a filter: nothing is dropped, and every folded node
says what it stands for.

**smallest plate** How few things a plate may hold before it is merged into `<small>`.
The line under it always states what that merged: *"4,410 drawn · 7 plates merged into
`<small>`, holding 25."*

**Colour by** What colour means: `what it is`, `which plate`, or `what changed`. The last
appears only while two versions are being compared.

**unselected** Whether everything you did not pick is `dimmed` or `hidden`. Dimmed keeps
the shape of the program around your selection; hidden gives you the neighbourhood alone.

**following** What clicking a neighbour does. **replaces** gives you one hop from wherever
you land, which is the cleanest picture. **keeps the path** keeps every node you followed
picked, so a few clicks build a visible route through the program.

**collapse gaps** Close the hole a plate nothing is looking at leaves behind, rather than
flying past an empty height.

**The sort menu** at the top of the Plates panel, beside its count — it has no label on
screen; a screen reader announces it as *Sort plates*. Six orders. `by size` is the default; `by name` and `by kind` are what
they sound like; `as arranged` is whatever order you dragged the legend into. The
interesting two are **by what they link to** and **by what they link to, grouped**, which
search for an order putting plates near the ones they cross to. On a 53-plate program the
first took the average crossing from 30.78 plates of travel down to 5.31 — **83% shorter** —
with a third of all crossings landing on the plate next door. The grouped variant holds
packages above externals and keeps about a third of that saving. Neither is ever claimed to
be optimal, only better by a stated amount than the order it started from.

## The Overview layout

The **Stack** / **Overview** toggle beside the mode buttons is two drawings of one
selection, not a seventh mode. The stack holds every node and answers *what is in
here*. The overview holds one box per package — 27 of them for DunneFlow — and answers *what
is this shaped like*.

---

Next: [7. Table](07-table.md)
