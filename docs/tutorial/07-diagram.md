# 7. Diagram

The stack draws all 2,692 nodes. This draws forty boxes, and answers a different question:
**what is this one part shaped like, and what flows through it.**

![Diagram mode with the resolve compartment chosen. A dropdown reads "resolve — 40 boxes" and the line beside it reads "40 boxes over 178 routines · 17 flows within · 80 crossing to 11 other compartments (not drawn) · 9 with no flow either way · drawn in 25 ms · double-click a box to open it", with a "show crossings" checkbox. Below are "colour by" set to "nothing", a "fit" button, and the text "· 1 box selected" with a "frame it" button. Forty small labelled boxes are scattered over the pane, most of them joined to nothing; in the middle, entrypoints.py with 12 functions is drawn bold, with arrows to manifests.py and languages.py, and conformance.py, stated.py, mirror.py, naming.py, traceability.py, cli.py and others also point into languages.py](images/07-diagram-compartment.jpg)

## The line under the dropdown

Every number in it earns its place, and together they are a complete description of what
you are looking at:

| | |
|---|---|
| **40 boxes over 178 routines** | a fold, and what it folded |
| **17 flows within** | arrows drawn inside this compartment |
| **80 crossing to 11 other compartments (not drawn)** | arrows that leave |
| **9 with no flow either way** | boxes here that connect to nothing |
| **drawn in 25 ms** | |

The crossings are **counted always and drawn only when you ask**. Turn them on and the
picture connects everything to everything and stops packing; leave them off and the count
still tells you they are there. What is not allowed is for them to be silently absent.

And `9 with no flow either way` is the sort of row most tools would drop. A box that
connects to nothing is not an error, but it is *interesting*, and you would never find it
by looking.

One clause is missing, and that is information too. A compartment the outside world comes
straight into says so — `web`'s line includes *entered from 4 ways in*. Nothing enters
`resolve` from outside the program; it is reached only from code that was itself reached
first, so its line leaves the clause out rather than printing a zero.

## Your selection, and where it went

The head says one of exactly three things:

- nothing, when nothing is selected;
- **`1` box selected**, with a **frame it** button;
- *what you picked is not in this compartment.*

That third one used to be conveyed by saying nothing at all, which is indistinguishable
from a control that is broken.

We still have `entrypoints_from_manifests` selected from chapter 3, and it lives in
`entrypoints.py`, which is in `resolve`. So: **1 box selected**. The box is marked — but
fitted to this pane, a marked box is a few pixels across, and *marked but too small to see*
looks exactly like *not marked*. Hence the sentence. The count is written out in words
because the drawing cannot be trusted to convey it at this size.

## frame it

Press it.

![The same compartment after pressing frame it. The camera has zoomed in on entrypoints.py, drawn bold with 12 functions, among the boxes an arrow joins it to: flows.py with 8 functions above it, pointing in; manifests.py with 8 functions and languages.py with 6 functions below it, both pointed at. Around them, some cut off by the edge of the pane, are version.py, conformance.py, stated.py, Band, mirror.py, ManifestReading, Report and GlossaryReport](images/07-diagram-framed.jpg)

The camera moved to the selection **and everything an arrow joins it to** — so you land on
a neighbourhood rather than on one box with no context. `entrypoints.py` is bold in the
middle; `flows.py` calls into it, and it calls out to `manifests.py`, where the files a
program declares itself in are read, and to `languages.py`, which says which languages the
map holds.

That is a fair one-glance summary of where the program's ways in are worked out, and it
took one click from a search box.

**Nothing frames itself.** Selecting a routine elsewhere marks the right boxes and leaves
the camera exactly where it was. Framing is offered, one click away, and never taken on
your behalf — the same rule the table follows with its **Go to it** button. And **fit** is
untouched, so the way back out is always one press.

## colour by

The diagram spends no colour until you ask it to. **colour by** offers one reading,
**what it does**, and it sorts every box by the direction its flow runs:

![The resolve compartment with colour by set to "what it does". A legend reads "emits only 3 · receives only 11 · both 17 · neither 9" and, beside it, "counts flow that leaves this compartment, which is not drawn — turn on show crossings to see it". The boxes are tinted to match: entrypoints.py, flows.py, conformance.py, languages.py, manifests.py, _AppResolver and most of the files are the rose of "both"; Term, Mirror, TracedId, Report, ResolveStats and other small classes are the blue of "receives only"; Point, cargo.py and one of the two calls.py boxes are the amber of "emits only"; and gomod.py, RuleCheck, Resolver, ProgramVersion, ManifestReading, packagejson.py and a few others are left untinted](images/07-colour-by.jpg)

The four numbers add up to the forty in the line above, so no box is coloured without being
counted. And the legend states what the reading costs: a box can be amber, *emits only*,
with no arrow leaving it on screen, because what it emits goes out of the compartment and
the crossings are not drawn. Without that sentence, an amber box with no arrow would look
like a bug.

So turn on **show crossings**:

![The same compartment with show crossings ticked. The line now reads "40 boxes over 178 routines · 17 flows within · 80 crossing to 11 other compartments · 9 with no flow either way · drawn in 24 ms", without "(not drawn)", and the legend has lost its warning. Dashed ellipses for the other compartments have joined the drawing — render, web, mcp, cli, anomalies, detectors, store and schema, with ARTEFACT, FILE and DATABASE for the boundaries — and dashed arrows run from nearly every box to them, so the whole compartment is fitted into a wide, shallow band, a dense mesh too small to read at this size](images/07-crossings.jpg)

Now the line drops *(not drawn)*, the legend drops its warning, and the picture shows you
why the crossings are off by default: it connects everything to everything and stops
reading as a shape. The other compartments come in as **dashed ellipses** — places the
flow goes, not boxes in this one.

## Opening a box

Double-click `entrypoints.py` and the boxes become the routines inside it, described by the
same sentence — including which box you are inside, so it is never a drawing you cannot
place. **‹ out** goes back up.

![The second level. Beside "resolve — 40 boxes" are a "‹ out" button and the title entrypoints.py, then "12 routines · 11 flows within · 18 crossing to 8 other boxes (not drawn) · drawn in 2 ms", show crossings unticked, colour by "nothing", and "· you are inside what you picked". entrypoints_from_packaging sits at the top and points down into entrypoints_from_manifests, which has solid arrows to _import_prefixes, _target_routine, _target_file, a DATABASE cylinder and _mint; _target_routine points down to exact; collisions points into _mint; binding_note, on the right, points to _resolved and _declaration and has no arrow coming in; record_manifests stands alone. The inspector is headed resolve.entrypoints, resolve/entrypoints.py:38–356, with a code button, ANALYSED, FILE and "12 folded", and lists HOLDS 12, each routine on one line with its code button and line number, from _import_prefixes at :38 to record_manifests at :350. The trail ends "Document › Diagram › entrypoints.py"](images/07-box-open.jpg)

Your selection is inside this box, and the head says so in as many words: **you are inside
what you picked**. The one box selected a moment ago is now the frame around everything
you see.

The two routines the comparison found added are both here — `_import_prefixes`, which
`entrypoints_from_manifests` now calls, and `exact` under `_target_routine` — and so is the
one that explains the shape of the whole box. `binding_note`, on the right, has no arrow
coming in, yet it is called from four other files — `cli.py`, `anomalies.py`, `flows.py`
and `markdown.py`. Those calls are among the *18 crossing*: counted in the line, and drawn
as dashed arrows from above as soon as you tick **show crossings**. It is where an unbound
way in gets its sentence, and everything that prints one asks it.

This second level is asked for on demand rather than built with the rest, and the reason is
arithmetic: a compartment is one of 25 drawings that come out of one pass over the model;
a box is one of 197.

## Arrows open too

Every arrow is clickable, and it carries both its identity and its kind — a call and a
touch between the same two boxes are **one arrow that can tell you which it is**, rather
than two arrows or one ambiguous one.

Click the one from `_target_routine` down to `exact`, and you get the flow:

![The arrow from _target_routine to exact selected inside entrypoints.py. Both ends are drawn bold and the head reads "· 2 boxes selected". The inspector is headed "_target_routine → exact", "routine → routine", with the badges FLOW, CALL and "2 along it". CALL SITES 2 lists two calls, each marked CERTAIN with a code button: exact at :102, in resolve.entrypoints._target_routine, passing "module", and exact at :107 passing "module[len(prefix) + 1:]", each lined up against "→ name: str" and the declared signature "exact(name: str) → str | None". TOUCHES 0 says "Nothing along this arrow touches a boundary, a table, a remote or a named file." A closing paragraph begins "Every expression here is what the caller wrote. Nothing is inferred" and ends "92% of arguments on a resolved call bind; the rest say why they do not."](images/07-arrow-flow.jpg)

Every call site, with **the arguments as written**, beside the callee's declared
parameters. Not re-printed from a parse tree — sliced out of the file's own bytes, and
never shortened. Here there are two: `_target_routine` asks `exact` about the name as the
console script wrote it and, if that finds nothing, about the same name with an import
prefix taken off the front — one for each directory the manifest climbed through.

An argument is lined up against a parameter only where the source settles it. Where it
cannot be, the row says why, because a blank beside an argument would read as *no such
parameter* — a different claim, and a false one.

> **Aim for the middle of the arrow.** An arrow is a line two pixels wide, and a box is
> drawn over the ends of its own arrows, so a click close to either box picks the box. Click
> a stretch of the line well clear of both boxes. You know it worked when both ends light up,
> the note above the drawing says **2 boxes selected**, and the inspector is headed with the
> arrow itself — here *\_target\_routine → exact*. Holding the pointer over a line first
> shows a card saying *Click to see what flows here.*, which confirms you are on it.

---

Next: [8. Two versions](08-two-versions.md)
