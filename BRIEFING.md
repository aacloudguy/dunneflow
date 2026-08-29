# DunneFlow — briefing

**Read this first, then stop.** It is an index, not a fourth copy of the documentation.
It exists so a fresh context can be useful in a few minutes instead of an hour.

| Read | For |
|---|---|
| `CLAUDE.md` | The rules. 46 engineering rules and 26 dashboard design rules, each earned from a false result on real code. **Binding.** |
| `HANDOFF.md` | The chronological record — what was built when, what it cost, what broke. ~1,700 lines. Read *sections*, not the whole thing. |
| **this file** | Where things are, what is done, what we are doing now, what not to re-open. |
| Artifact `f993d319-d2b7-4217-9130-cdbba698d1bc` | The ratified dashboard design — a complete working UI, the source of truth for every view. Read it with the **Artifact tool**, not from a screenshot. |

---

## What the tool is

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. **What moves is the subject; internal computation is not.** Local variables,
arithmetic and control flow are deliberately absent — leaving them out is most of what
makes the output readable.

The reader is someone who **reads code but does not write it**, orienting in a codebase
they did not build. Judge every change by whether it helps them orient, not by how many
pages it emits.

## Where the code lives

```
source ──► extract ──► graph.db ──► resolve ──► render (Markdown + Mermaid)
docs   ──► extract ──► docs.db  ──────ATTACH──┘
                       source.db  (file bodies, content-addressed)
```

| Module | What it is |
|---|---|
| `schema.py` | The fact contract. Every extractor in any language emits these types. |
| `store.py` | SQLite. **The spine, not an export format.** Nothing holds the program in memory. |
| `docstore.py` | `docs.db` — parallel to the graph, never inside it. |
| `sourcedb.py` | `source.db` — file bodies. The one store that is never discarded (rule 25). |
| `extractors/python/` | stdlib `ast` + `tokenize` only. No third-party parser. |
| `extractors/docs/` | Markdown / rST / text, scanned by hand. No markdown library. |
| `detectors/*.yaml` | **The extension point.** Teach a framework here, not in code. |
| `resolve/` | Call graph, CLI trees, flows, naming, glossary, traceability, mirror. |
| `render/` | Markdown and Mermaid, complete — never abbreviated (rule 8). |
| `anomalies.py` | What looks wrong. Every finding states what would make it a false alarm. |
| `sql.py` | Reads schemas out of the `CREATE TABLE` statements the code contains. |

### `web/` — one application

The dashboard is **vanilla JS + deck.gl on stdlib `http.server`**. No Node, no framework,
no build step. deck.gl is vendored into `web/vendor/`.

| File | What it is |
|---|---|
| `serve.py` | the server — a route table, one handler per endpoint |
| `queries.py` | every dashboard query as **SQL text**, in one place |
| `cover.py` · `detail.py` · `documents.py` | the cover · the inspector and the hover card · document mode |
| `threads.py` | adjacency by *interest* — why a neighbour is worth a detour |
| `vocabulary.py` | the naming and glossary lanes, served and matched against one name |
| `graph.py` · `layout.py` | the 2.5D model, and where things sit |
| `packages.py` | the package overview — the other graph layout |
| `static/shell.js` | **the application**: state, routing, every view, the self-check |
| `static/graph.js` | **the engine**: payload to pixels, and nothing about this page |
| `static/settings.js` | the store — per program, versioned |
| `static/shading.js` | the sphere shading, one extension class per lighting |
| `static/tokens.css` | the tokens; **no colour is declared outside this file** |

> **The boundary that matters** is the container. The engine draws inside the element it is
> handed and touches no DOM outside it; what it has to say — selection, counts, fps,
> diagnostics, errors — leaves as events. The shell owns the selection, the settings, the
> search, the legend and the breadcrumb. Before chunk 2 both halves existed twice, and
> `index.html` loaded only one of them.

## Built, and not

Working and verified against Society of Mensores (623 files, 184k lines):

Python extraction · call resolution incl. inheritance and CLI registration idioms · CLI
command trees · flows · boundaries · data structures · database read/write matrix ·
network with timeouts and retries · messaging · anomalies with severity, confidence and
blind spots · Markdown + Mermaid · documentation ingest · glossary · naming standard ·
traceability across both stores · named artefacts · the mirror · comments (18,208 of
18,208) · constants and type aliases · stable identity · source sidecar.

**Dashboard:** one application — the ratified shell (cover, navigator, worklist, table,
document, glossary, naming, settings) with the 2.5D stack and the package overview as two
layouts inside graph mode, one inspector reading `/api/node`, and the graph following the
theme. The reading loop: the navigator is the routine list, hovering a node gives a card,
picking one lights its hop and fills the inspector, threads lead sideways, and ⌘Z takes any
of it back.

**Not built:** `dunneflow infer` (the model pass) · temporal layers · attestation · the
project profile · document mode's narrative view · packaging as a binary · any language
but Python.

**Built but not on screen:** `CURIOSITIES`. `threads.py` computes the outlier family per
package already — most commented, most called, deepest closure, most lopsided table — and
running that program-wide is most of design rule 15's doorway panel. It says honestly that it
is not computed yet.

## What we are doing now

**The navigator survives a long list — 2026-08-29.** See `HANDOFF.md` 5o. All three symptoms
Tom gave at the keyboard, and the question behind them: what does the pane offer someone who
arrives in the middle of 4,734 rows?

- **The notice reads before the list**, inside a sticky header, the same open or closed.
- **The pane is a header row over a scrolling body**, with the group headings sticky inside
  it — so the collapse control is always within reach of a wheel. Two grid rows rather than a
  second sticky element, because a sticky element under another has to know its height.
- **A jump strip** takes you to any group in one click and marks the group you are in,
  generated from the same ordered table the groups are. The menu order moved out of
  `render()`, where it was applied by shuffling DOM nodes the strip could not see.
- **The routine list is grouped by package** — 47 rows a person can read — and by the package
  the *stack* uses, so a heading names a plate. Packages too small for a plate of their own
  say so and select the merged one; rule 30 from the far side.
- **Three Settings, all counted** (design rule 2): how many groups stand open at once
  (default one), how many routines a package lists (50 / 100 / 200 / 500 / All — Tom's, and
  the reason is that `200 of 377` is a tease rather than a bound), and the menu order.
- **Rules 45 and 46**, and a fourth CSS default that looks like absence.

**Next, and named:**

1. **`CURIOSITIES`** — `threads.py` already measures the outlier family per package, and
   design rule 15's panel is that computation run over the whole program. It is the last
   thing on screen that says "not computed yet".
2. **The two vocabulary-lane precision defects**, still open and unchanged: a DASH_GLOSS
   mined out of a field-constraint table counts as a definition, and the undefined list's
   head is segments of SCREAMING_SNAKE constant names — `DDL` 57, `EXTRAS` 50, `REASON` 43 —
   burying the words that matter (`witness`, `posture`, `claim`, `probe`). Rule 1.
3. **Packaging as a binary**, which the briefing calls the product for a reason that has not
   changed: the tool reads private source.

**Open on the navigator, and deliberately left to use rather than to argument:** whether 47
closed packages is the right first screen, and whether the accordion should be the default.
Both are Settings and both are counted, which is what design rule 2 is for.

## What we were doing before that

**The glossary and naming pages are ported — 2026-08-28.** See `HANDOFF.md` 5n. They were the
last two screens admitting to being unported: both lanes were computed, tested and served, and
the two views were still the prototype's, written against a shape the server does not send. A
convention is followable by its `glob` (rule 41), a term shows however many senses anything
said about it, a citation opens from `/api/source`, and the lane sizes ride with the cover.
**Rule 44** came out of it: a live control reading a field the server does not send renders
`NaN` at zero width beside a claim that is true, and nothing throws.

**The pop-up and the threads are built — 2026-08-28.** See `HANDOFF.md` 5l–5m.

- **The pop-up is a card, painted in two stages.** `getTooltip` is gone; the engine emits a
  `hover` event and the shell draws. The first paint is free from the payload — name,
  qualified name, `file:line`, plate, `3← 5→` — and `/api/hover` fills in the lines, the
  comment count, what it touches grouped and named, the governance ids and one line of WHY
  with the label saying whether it came from a docstring, a leading comment or a quotation.
- **Threads to pull are computed, in four kinds**: governance kin, the other end of a
  boundary, outliers nearby, and vocabulary. Every one carries a **subject** the router acts
  on, ordered rarest-first, with the count beside it. What they replaced was six hand-written
  rows about one routine, every one of which went to the same empty page.
- **Following a neighbour is a Setting** (design rule 2): `replace` starts a fresh hop,
  `walk` keeps the path lit. Both built, ⌘Z drops the last hop, and the walked length is
  stated.
- **`/api/naming` and `/api/glossary` are served**, computed once at start. The graph uses
  them; the two pages were ported the same day — see above.

**Known and not fixed: the near-plane clipping.** Zooming far enough in clips the nodes
nearest the camera. It is deck.gl's default frustum, the diagnosis is in `graph.js`, and the
obvious remedy — a negative `near`, which is geometrically sound under an orthographic
projection — **breaks pan and zoom**. Do not retry it without a way to drive the controls.
Rule 39.

### And before that

**Chunk 2, "one application" — done 2026-08-28.** The two applications are one: the stack
mounts inside the shell, there is one state, one settings store, one inspector and one
self-check; the package overview is computed rather than hand-placed and sits beside the
stack as a *layout*; and the graph follows the theme. See `HANDOFF.md` 5d for what it cost
and what it found — including that the sphere shading had never actually run.

**Next: packaging.** A single double-clickable binary is the product, and not for
convenience: DunneFlow reads private source and `source.db` contains it, so a hosted model
would send an unfamiliar codebase to a server, and design rule 14 says egress is scoped and
never a switch. PyInstaller or py2app, opens at localhost, full SQLite underneath, no Node.
Signing decides the experience, and there is already an Apple Developer account.

Deferred deliberately: the layered "stack of architecture drawings" layout (`HANDOFF.md`
5b); temporal layers; attestation; `dunneflow infer`.

**Owed and now discharged:** the two "spheres" rows in the `CLAUDE.md` budget table were
retaken 2026-08-28 — 60 median, nothing dropped, on a 2652×1537 canvas framed with snap to
fit, shading confirmed by eye first. Both the canvas size and the framing are recorded this
time, because their absence is what made the original pair impossible to reproduce.

**Also done 2026-08-28 (`HANDOFF.md` 5g):** the side panes fold to a labelled rail, and
the inspector rails itself while nothing is selected. Found doing it: `panels` had been a
persisted, reset-by-name setting that **nothing read** since the chunk-2 merge. Design rule
24, and design rule 16 extended.

**Also done 2026-08-28 (`HANDOFF.md` 5f):** three independent spread axes (X and Y widen a
plate, Z is the gap between plates; all three together is what zoom already is), and
hide/collapse as separate switches so a selection of eight plates out of fifty-two stops
reading as eight plates down a tower of empty slots. Design rules 22 and 23. **Still owed
from that conversation: per-plate sphere scaling, and stack orientation** — laying the column
on its side, which is structural because `OrbitView` has no camera roll.

**Also done 2026-08-28 (`HANDOFF.md` 5e):** three layout and navigator defects found while
clearing that debt. A `rem` inside `@media` resolves against the browser's font size, not
the page's, so five breakpoints silently meant the wrong width; the narrow layout's
`display: none` lost to a later equal-specificity rule and never hid anything; and all four
navigator routes that set a subject carried no subject, so forty rows did the same nothing.
Rules 28, 29 and 30.

## Decided — do not re-open these

| Decision | Where it is recorded |
|---|---|
| The dashboard is the parent; the graph is a view inside it, **no iframe** | `HANDOFF.md` "Chunk 2, next" |
| `graph.js` is the engine, renamed not removed | same |
| Astro 5 + Tailwind 4 **struck**; vanilla + deck.gl, no Node | `CLAUDE.md` dashboard preamble |
| SQLite is the spine — never replaced with in-memory graphs | `CLAUDE.md` Architecture |
| `docs.db` stays parallel to `graph.db`, never inside it | same |
| **Both** a package graph and the 2.5D stack; the SVG is not the endpoint | `HANDOFF.md` "Opening screen", "Wanted later" |
| The graph follows the theme — both palettes, a Setting, usage retires the loser | `HANDOFF.md`; design rule 2 |
| One multiplier resizes everything, **graph nodes included** | design rule 3 |
| The legend is HTML, 51 disks in three interleaved columns, the main way in | design rule 19 |
| Edges on demand only, and only when still; **one** hop | design rule 19 |
| Confidence is shape, not colour; external is neither | design rule 5; rule 26 |
| Settings persist per program, versioned, discarded whole on mismatch | `settings.js` preamble |
| Route from a table; self-check derived from the DOM | design rule 16 |
| Egress is scoped, never a switch; nothing infers during `analyze` | design rule 14 |
| DunneFlow **never** talks to a VCS to fetch code | `HANDOFF.md` "Version control must stay pluggable" |
| A single binary is the product; sqlite-wasm is the *export* format | `HANDOFF.md` "Distribution" |
| **Nodes are billboarded circles, lit to read as spheres** — the technique, not an approximation | `HANDOFF.md` "why the nodes are flat circles" |
| Edges stay up while the camera turns; a Setting, default on | design rule 19, amended |
| The legend is a **pane with its own track**, never an overlay; open by default | design rule 25 |
| The **navigator is the routine list** — not a split centre pane, not a fourth mode | design rule 26 |
| Selecting never moves the camera; off-screen is *stated* with one click to frame it | design rule 26 |
| Clicking an already-selected node still clears it — undo makes it recoverable | rule 33 |
| The pop-up is a **hover card**; the clickable depth stays in the inspector | `HANDOFF.md` 5l |
| A thread carries a **subject**, never a label; the click routes from a table | rule 30; design rule 16 |
| Threads sort **rarest first** — three routines is a detour, three hundred is a category | `threads.py` |
| Following a neighbour: **both** replace and walk, a Setting, usage retires the loser | design rule 2 |
| The naming and glossary lanes are computed **at start**, not lazily; their bodies are fetched when their page opens, their sizes ride with the cover | `CLAUDE.md` budget; `HANDOFF.md` 5n |
| A citation is opened from `/api/source`, never pinned into the page | `HANDOFF.md` 5n |
| Plates a selection touches are drawn faintly and named, though plates stay off | design rule 26 |
| **Plate**, never disk or plane, in every word a reader sees | `HANDOFF.md` 5p; a guard |
| The you-are-here arrow is a billboard at the plate's rim, aimed by a screen angle | `HANDOFF.md` 5p; rule 22 |
| The way back restores the view the selection was *found* in, not a computed fit | `HANDOFF.md` 5p |
| The navigator is a fixed header over a scrolling body; group headings are sticky | rule 45's session; `HANDOFF.md` 5o |
| The routine list is grouped by package, and the package is the **plates'** package | `queries.py` `NAV_ROUTINES`; rule 30 |
| How many routines a package lists is the reader's, `All` included | `HANDOFF.md` 5o |
| A search opens what it matched only while the answer is small, and says when it did not | rule 45 |

## How to verify — all three, before saying anything is done

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then against real code, because unit tests on a toy program cannot catch a resolution
defect that only appears at scale:

```bash
uv run dunneflow analyze ../mensores-overhaul/src --name mensores
uv run dunneflow serve output/mensores
```

**`../mensores-overhaul` is read-only.** All output belongs in `output/`.

Ground truth is in `CLAUDE.md` — both halves. Positive: the four executables must all
appear in "Where to start" with plausible reach. Negative, and it matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about* naming
standards and must yield **zero** naming rules.

### The traps that cost this session

- **The automation tab gets no animation frames.** `ResizeObserver` never fires and `rAF`
  never ticks in it, so anything needing a rendered frame cannot be observed there — a
  confident, reproducible and entirely false finding came out of measuring through one.
  Static DOM facts (grid tracks, widths, classes) survive; everything else must be driven
  by a human in a real window. Rule 38.
- **A guard that checks a name appears has not checked anything happens.** Three guards
  written this session passed against their own defect first time. Run every new one against
  the defect it came from *and* against a half-working version. Rule 37.
- **A rule about drawing is usually also a rule about reading.** Rule 23 said a shadow is
  never an endpoint; the code that *drew* edges obeyed it and the code that *read* them did
  not, which silently deleted every cross-plate caller from the selection. Rule 31.
- **A guard that names the right case may still not catch it.** `selectionOnScreen()`
  documented itself as returning null when there is no viewport and guarded with `?.` —
  while deck.gl asserts *inside* `getViewports()`. The `?.` was what made it look guarded.
  Rule 42.
- **A check that cries wolf has already failed.** The runtime self-check reported four dead
  controls on every page load for two sessions and was wrong about all four. Rule 43.

Each of these looked like working code and passed every automated check.

- **The nodes are flat circles on purpose.** Billboarded circles lit to *simulate* spheres
  is the performance technique that lets the stack hold ten thousand nodes at full speed —
  it came out of prior research and is not an approximation of something better. The
  lighting is load-bearing: without it they render as coins, not balls. Do not "fix" this
  into real geometry.
- **A shader effect that does nothing is not an error.** Three separate causes did it here
  — an unrecognised inject hook, a GLSL name collision with deck.gl's own scope, and a
  shader never reassembled because deck.gl resolves one per extension *class*. Each
  compiles, each draws. Check by eye after touching the layer.
- **A backtick inside an HTML comment inside a template literal** closes the literal. The
  page comes up blank; nothing else fails. Two guards now catch it.
- **`render()` rewrites the centre pane on every keystroke.** Anything with state of its
  own — a canvas, a colour picker, a slider being dragged — must live outside it or be
  updated narrowly.
- **CSS has four defaults that look like absence and are not.** A `rem` inside `@media`
  silently means the *browser's* font size, not the page's. A media query adds no
  specificity, so its `display: none` loses to any equal selector declared later. A grid
  item is `min-height: auto`, so it refuses to shrink and hands its overflow to the
  document — the first three were live in one stylesheet at once and produced one symptom.
  And a **sticky child sticks to its scroller's padding box**, so a strip of padding there
  is a gap the content scrolls through *above* the header meant to be covering it.
- **`outerWidth`/`outerHeight` are device pixels; `inner*` are CSS pixels.** Mixing them
  made 88px of ordinary browser chrome read as 677px and sent a diagnosis chasing a docked
  panel that did not exist.
- **A check may only claim what its instrument can prove.** The DOM can show a control with
  no handler; it cannot show a handler no control reaches, because half the controls are
  conditional. That direction belongs in a test that reads the source.

### Three habits this project paid for

- **Look, don't only test.** Two defects in two sessions passed every scripted check and
  were obvious in one screenshot — a graph running at 60 fps under an opaque panel, and a
  filter strip announcing a slice over a view filtering nothing. Screenshot the UI.
- **Doubt the tool first.** On the first run against live code, *six confident findings in
  a row were defects in DunneFlow*, not in the program being read.
- **Assert your inputs.** Three bugs in one day came from a step that silently operated on
  the wrong input and reported success. A string replacement that matches nothing is the
  most expensive kind of edit.

## Shared library

This project consumes `github.com/aacloudguy/dunnecorp-shared` (local checkout
`../SharedCode`). **Check its `catalog.json` before writing any new utility, helper,
workflow, skill or template.** Read it freely; never write there without asking.
