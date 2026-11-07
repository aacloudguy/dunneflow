# 13. Settings

**⚙ Settings** in the top bar. Everything here is stored in your browser, per program, and
stays on your machine. Not all Settings are local: A view someone sends you keeps their
layout; this stays yours.

There are six sections. Every control in them is below.

![The Settings page, reached from "⚙ Settings" in the top bar: an APPEARANCE section with Theme (Light / System / Dark, System chosen) and Interface scale (88% / 100% / 113% / 125% / 150%, 100% chosen), and a COLOUR section headed "the two channels where colour carries a meaning", with the "Red and green" set selected — its chips gone, arrived, broken, suspect and info, its measured contrast of 5.34:1, "Clears the 4.5:1 minimum for body text", and its separation of ΔE 5, "Close — these two are hard to tell apart without the words beside them"](images/13-settings.jpg)

## Appearance

**Theme** — Light, System or Dark. System follows your OS. Both themes are designed, not
inverted.

**Interface scale** — 88%, 100%, 113%, 125% or 150%: one multiplier over everything — type,
column widths, row heights, icons, and the nodes in the graph. Every dimension in DunneFlow
is stored in `rem` for exactly this reason, so nothing is left behind when you move it.

## Colour

Colour separates one meaning from another in two places, and only two: **a difference,** meaning what only one version has, and **severity** in the anomaly worklist. Both spend red, which
is why both are set together. The accent and the external mark are single colours with
nothing to be confused with, so they are not part of a set.

Three sets are offered, each with a light and a dark variant:

| | Contrast | Separation |
|---|---|---|
| **Red and green** | 5.34:1 | ΔE 5 |
| **Blue and orange** | 4.86:1 | ΔE 43 |
| **Muted** | 4.84:1 | ΔE 10 |

- **Red and green** What the dashboard has always used. Familiar, and the weakest of the
  three when red and green cannot be told apart; the numbers say by how much.
- **Blue and orange** Built to stay separable when red and green do not: Okabe-Ito's
  vermillion and blue for a difference, a red-to-magenta-to-blue ramp for severity. Named
  for the colours rather than for the reader, because the colours are the fact and the rest
  is the claim underneath.
- **Muted** The same hues as the default, at lower chroma, for a reader who finds it loud.
  **Quieter is not safer** It is the same red and the same green, so it measures where
  they measure.

Each set states **two** numbers, and they answer different questions:

- **Contrast** Whether a colour can be *read*, taken as the worst case over every colour
  against both the surface and its own chip. 4.5:1 is the minimum for body text.
- **Separation** Whether two colours of one channel can be told *apart*, taken as the
  least of normal vision, deuteranopia and protanopia.

A set can pass the first and fail the second, which is exactly what *Red and green* does at
ΔE 5 against *Blue and orange*'s 43, and why both numbers are printed. Where two colours
are close, the page says so: *"these two are hard to tell apart without the words beside
them."* Every measurement is available behind a link on each set.

Colour is never the only carrier of meaning anywhere in DunneFlow. Confidence is line style.
A boundary kind is an icon plus a label. Severity carries a glyph.

## How a plate arranges what it holds

One choice, two answers, both built, and the page says which one your browser can run:
*"Your browser has WebGPU, so the solve runs on the graphics card."*

![The HOW A PLATE ARRANGES WHAT IT HOLDS section, headed "both built; use decides which survives": a paragraph saying it changes nothing about what the map says — "the same nodes, the same connections, the same plates — only where each one is drawn, so a selection, a search and the trail all survive the switch. Your browser has WebGPU, so the solve runs on the graphics card." Below it two choices, By structure (selected) — a sunflower spiral, busiest nearest the middle — and By connection — "328,531 crossings down to 27,291 on the busiest plate, 91.7% fewer"](images/13-plate-arrangement.png)

**By structure** A sunflower spiral, busiest nearest the middle. Even, instant, and the
same arrangement every time you open the map, which is what lets you remember where
something was. It knows nothing about which nodes are connected, so edges cross it at every
angle.

**By connection** Connected things pull together and everything pushes apart until the
plate settles. Measured: **328,531 edge crossings down to 27,291 on the busiest plate,
91.7% fewer.** Shadows pull for the plates they stand in for, so a plate is arranged by what
it reaches as well as by what it holds.

Neither changes what the map says. These are the same nodes, same connections, and the
same plates. Only where each one is drawn changes, so a selection, a search and the trail all survive the switch.

**The rest of the graph's controls are not here.** Spacing, the three spread axes, plate
width, node sizing and the order of the plates live on the graph's own HUD, where you can see what they
do while you move them. See [Graph](06-graph.md).

## What opens, and what shows

Twenty-four rows, and this is all of them.

| | |
|---|---|
| **Startup screen** — Cover / Package graph | Which one you land on. Both exist because the choice was a genuine tie; Usage below tracks which you open. |
| **Show the trail** | The strip recording where you have been. |
| **Steps the trail shows** — 6 / 12 / 25 | How many fit on the bar, not how many are kept: the history holds fifty either way and Back reaches all of them. |
| **A leading underscore in a name** — Counted as a violation / Allowed | Whether `_Handler` is a PascalCase class. See below. |
| **Routines a macro wrote** — Folded / Listed | One navigator row per macro, or every routine. See below. |
| **Cursor over the diagram** — Arrow / Crosshair / Hand | A diagram is a drawing you aim at, not a page of links. |
| **Flow arrow thickness** — 1× / 2× / 3× / 4× | How heavily an arrow between two boxes is drawn. It took Graphviz's default of 1. |
| **Menu order** — Ways in first / Explore first | First position in a menu is a real advantage, so it is yours to give. |
| **Routines listed per package** — 50 / 100 / 200 / 500 / All | See below. |
| **Navigator groups** — One at a time / All at once | See below. |
| **You are here** — Shown / Off · Reticule / No reticule · At the side / Over the node · colour | The arrow standing over every node you pick. See below. |
| **The graph's ground** — Follow the theme / Always dark | The stack's colours were all chosen against near-black. |
| **Show edges while moving** | Whether links stay drawn while the camera turns. |
| **Graph layout** — Stack / Overview | Two drawings of the same selection. |
| **Proportion bars on the cover** | The bar beside each count in *Where to start* and *What it touches*. |
| **Tags on their own line when a name is long** | On *Where to start*, when a name and its tags will not share a row. |
| **Wrap the evidence line** | The line under each name on the cover, wrapped or cut with an ellipsis. |
| **Ambient anomaly badges** | Whether anything carrying a finding is marked wherever it appears, with an amber `!` on the node, a tag beside the routine. |
| **Scroll change bands in place** | On the change worklist, each band keeps to 32rem and scrolls inside itself, or runs its full length. |
| **A navigator name too long for its row** — As it is / Cut it / Wrap it | Measured: on one routine list, 335 of 1,395 rows print their name straight over their counts. |
| **Fit the toolbar to the window** | The toolbar is one row that does not wrap, so on a narrow window it runs off the end. |
| **Version strip on one line** | The BASE strip wraps onto a second line, or scrolls. |
| **Keep the panes inside the window** | The panes yield, or run off with the toolbar. |
| **Fold a pane the window cannot fit** | Three panes need about 50rem side by side; below that, one folds. |
| **Hide inferred edges** | Show only what is pinned by import, module or class. |

### Routines a macro wrote

One macro can write thousands of routines. **Folded**, the default, gives the navigator one row per
macro per package, with a count, and a row that opens that macro on the Macros page. **Listed** gives
every routine. Under an open package, *list them* changes this too.

A search always finds them, a selected routine always has its row, and a way in is never folded.
The diagram keeps its one dashed box per macro either way, and opening the box lists what it holds.

### A leading underscore in a name

![The Settings row "A leading underscore in a name": "Whether _Handler is a PascalCase class. Strictly it is not — it does not begin with a capital — and it is also the commonest way a codebase marks something private. Counted as a violation is the strict reading; allowed reads the underscore as a privacy mark and judges the rest. Both naming pages follow this, and every claim it changed says so." Beside it the two buttons, Counted as a violation and Allowed, with Allowed chosen](images/13-leading-underscore.png)

A naming rule that says *classes are PascalCase* is broken, strictly, by every private class
in a Python program. **Counted as a violation**, the default, takes the rule at its word.
**Allowed** reads a leading underscore as a privacy mark and judges what follows it. On
DunneFlow's own map that moves its classes from **165 of 182** to **179 of 182**: the
three left are `ClassDef_`, `Exception_` and `Field_`, whose underscore is at the other end
and means something else.

It changes both naming pages, *Derived naming standard* and *Stated rules, checked*, and
each says which reading it is showing, so a count is never read without knowing which rule
produced it. The command line takes the same choice as `dunneflow naming
--allow-leading-underscore`.

## Usage

![The foot of the Usage counters, one row per view or choice with a bar and a count — Diagram:Colour:None, Naming:Underscore:Allowed and Naming:Underscore:Violation, each wrapped onto two lines inside its own column, then Doc:Lane:Map, Doc:Open and Algorithms — under which "Counted so a Setting that exists only because two options were tied can be retired on evidence rather than on opinion." Below it the ACCESSIBILITY — AND ITS LIMITS section: a node graph stops being screen-reader navigable past roughly fifty nodes; Mermaid's generated SVG can be themed but its focus order cannot be controlled; pan and pinch-zoom are gestures not everyone has; colour is never the only carrier of meaning](images/13-settings-usage-a11y.jpg)

A count of which views you actually open and which way you set the tied choices, headed *local only · never leaves this machine*.
It is here for one reason, stated on the page: several settings exist only because two
options were genuinely tied, and this is how the loser gets retired on evidence rather than
on opinion.

## Settings that are not on this page

Three things are remembered per program exactly like the rest, and set where you use them
rather than here, because each of them is a thing you change *while looking at what it
changes*.

**The graph's spacing, spreads, plate width, node sizing and the order of the plates** The HUD, and
[Graph](06-graph.md).

**Row density** Compact, Comfortable or Spacious, above the routine table.

**Which panes are open, and how wide** The rails and the drag handles.

### And the three comparison overlays

The **◆ changes** button in the code browser, above the routine table, and on the anomaly
worklist. Three separate switches, and they are separate because what each costs is
different. None of them is drawn at all when there is only one version because a switch that
governs nothing is worse than no switch.

| | What it costs |
|---|---|
| **The code overlay** | A per-file difference and up to a few hundred marked lines. The dearest to read, because it makes the *code* harder to read. |
| **The routine and table marks** | Free — drawn from an answer already held. |
| **The findings overlay** | The dearest to compute: thirteen detectors run against a graph this process has never opened. On a 628-file program, 1.3 to 4.1 seconds the first time, nothing afterwards. Fetched when you open the worklist, not at boot. |

Wanting the free ones while reading clean code is an ordinary thing to want, and one switch
could not express it.

## Clearing them

**There is no reset control.** Settings are kept in your browser's local storage under a key
per program, so clearing them today means clearing site data for the address the dashboard
is served on. Nothing else is lost by doing it: the map is on disk and every setting has a
default.

---

Next: [14. Comparing two versions](14-comparing-two-versions.md)
