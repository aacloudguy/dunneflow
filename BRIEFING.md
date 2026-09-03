# DunneFlow — briefing

**Read this first, then stop.** It is an index, not a fourth copy of the documentation.
It exists so a fresh context can be useful in a few minutes instead of an hour.

| Read | For |
|---|---|
| `CLAUDE.md` | The rules. 77 engineering rules and 27 dashboard design rules, each earned from a false result on real code. **Binding.** |
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
| `migrate.py` | Stored paths absolute → relative, in place. The prior state it can speak for, named (rules 60–62). |
| `extractors/python/` | stdlib `ast` + `tokenize` only. No third-party parser. |
| `extractors/docs/` | Markdown / rST / text, scanned by hand. No markdown library. |
| `detectors/*.yaml` | **The extension point.** Teach a framework here, not in code. |
| `canonical/` | Whether two writings are the same expression, per language. **Beside** the extractors, never inside one — see the cache-key note in `CLAUDE.md`. |
| `resolve/` | Call graph, CLI trees, flows, naming, glossary, traceability, mirror. |
| `render/` | Markdown and Mermaid, complete — never abbreviated (rule 8). |
| `anomalies.py` | What looks wrong. Every finding states what would make it a false alarm. |
| `sql.py` | Reads schemas out of the `CREATE TABLE` statements the code contains. |

### `web/` — one application

The dashboard is **vanilla JS + deck.gl on stdlib `http.server`**. No Node, no framework,
no build step. deck.gl is vendored into `web/vendor/`.

| File | What it is |
|---|---|
| `serve.py` | the server — two route tables (GET reads, the one POST switches the base), and `_Base`: everything one version decides, swapped whole |
| `queries.py` | every dashboard query as **SQL text**, in one place |
| `cover.py` · `detail.py` · `documents.py` | the cover · the inspector and the hover card · document mode |
| `threads.py` | adjacency by *interest* — why a neighbour is worth a detour |
| `curiosities.py` | the doorway panel — ten measured extrema, each with **its middle** |
| `vocabulary.py` | the naming and glossary lanes, served and matched against one name |
| `graph.py` · `layout.py` | the 2.5D model at two levels of detail, and where things sit |
| `packages.py` | the package overview — the other graph layout |
| `code.py` | the code browser — a file, its clickable names and what each line *is* |
| `search.py` | searching the **text** — files first, then one file's lines with their margin |
| `static/shell.js` | **the application**: state, routing, every view, the self-check |
| `static/graph.js` | **the engine**: payload to pixels, and nothing about this page |
| `static/settings.js` | the store — per program, versioned |
| `static/shading.js` | the sphere shading, one extension class per lighting |
| `static/tokens.css` | the tokens and the three colour sets; **no colour is declared outside this file** |

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
layouts inside graph mode and **two levels of detail inside the stack**, one inspector
reading `/api/node`, and the graph following the theme. The reading loop: the navigator is the routine list grouped by package, hovering a
node gives a card, picking one lights its hop and fills the inspector, threads lead sideways,
and ⌘Z takes any of it back. **Finding and keeping your place**: an arrow at the plate's rim
aimed at what you picked and clickable to go there, a reticule on it, a *focus* lock so only
the lit set answers a hover or a click, and *you are here* to restore the view you found it
in.

**Reading one node:** hovering a routine in the picture *or in the navigator* gives a card,
painted in two stages, leading with the **invocation line** — the name, its arguments with
their types, and what comes back. `Enter` over a card opens a **detail window**: callers left,
the routine between, callees right, what it touches, threads leading away; every name is a
hop, and every hop is an ordinary selection so the stack, the navigator, the trail and undo
all follow. `?view=detail` puts that window in a **second tab or window**, two peers in
bidirectional sync over a `BroadcastChannel`.

**Code viewing — built 2026-08-29.** `source.db` is a content-addressed, compressed sidecar
(626 files, 7.8 MB of text in 3.1 MB). The inspector opens a definition ±3 lines from
`/api/node` and the glossary's citation viewer opens any span from `/api/source`; both say
the source is *as measured*, not as the tree stands now.

**The code browser** runs in three places over one `CODEFILE`: the **navigator's Code
group**, stacked as a file list that collapses once a file is picked with that file's lines
beneath it — so code and the stack are readable at once inside one window; **`Code` as a
fourth centre mode**, the same file with room for the margin to say what a line *is* rather
than stand for it; and **`?view=code`**, a peer over the same `BroadcastChannel` the detail
window uses. Clicking a name is an ordinary `selectFromNav`, and selecting anything anywhere
walks the code to the file it lives in. **No syntax colour, deliberately** — design rule 4.

Links are lookups, never name matches: `calls.callee_id` is the resolver's own answer. What
it does not carry is a *column*, so a call is underlined only where its expression occurs
exactly once on its line, and the counts of what was and was not placed ride with the payload.

**Search inside the source — built 2026-08-29.** The Code group's box asks two questions at
once: what matches a **path**, filtered instantly over rows already in the page, and what
matches the **text**, fetched. Files first — "782 lines in 166 files", 626 rows at worst and
never bounded — and the top one opens itself once the answer has narrowed, saying so when it
has not. A hit carries what the map knows about it: the routine it sits in (a line-range
lookup, innermost first), its margin, and its clickable names, all of them `code.py`'s own
answers narrowed to the matching lines. Literal and case-insensitive by default, with case,
whole-word and regex switches; a regex turns whole word off and says why.

Scanning all 184,722 lines is 20–30 ms, so rule 45 lands on the *answer* rather than on the
search. FTS5 was rejected on evidence: token-based, so it cannot find `_emit` inside
`self._emit`.

Still not built: syntax highlighting (a design-rule-2 pair if ever wanted, done server-side
with stdlib `tokenize`).

**The temporal overlays are complete.** The code browser, the routine views and the stack
were layered 2026-08-30; the **anomaly worklist joined them 2026-09-01**, once a finding
carried an identity to be paired on.

**Not built:** `dunneflow infer` (the model pass) · attestation · the project profile ·
document mode's narrative view · packaging as a binary · any language but Python.

**The revision spine is in, and both ends of a pair are readable.** `WORKING` is a *state*
rather than an id, and a revision is identified by when it was captured; `seal()` keeps the
current snapshot under its own name so the next `analyze` opens a second one beside it rather
than replacing it. `dunneflow revisions <dir>` lists them and `--seal` keeps one.

**A comparison is two directories**: the **base** is what the whole map shows and the
**compared** is what it is held against, neither claimed to be older — *added* / *deleted* is
an interpretation the reader owns, derived from the two versions where they say enough. Both
ends are settable from the toolbar; changing the base makes the server rebuild everything
from that graph (1.2–3.0 s warm, 35 s cold), and `serve --revision` chooses it at boot.

**The doorway panel is on screen — built 2026-09-01.** Design rule 15's fourth piece of
furniture, and the last of the four. `curiosities.py` measures ten extrema over the whole
program and every card states **the middle it is being read against**, because every
program has a most-commented routine and a maximum alone is a claim nobody can weigh.

## What we are doing now

**Paused 2026-09-03, after chunk B and the pane-reconcile rule it uncovered.**
839 tests, mypy clean, ruff clean, self-check green, console clean, working tree clean.

*The shortening work is complete.* The remaining twelve `text-overflow: ellipsis` sites were
measured before being changed, and measuring struck three of them, changed the mechanism from
a constant budget to one taken off the box at render time, and found that `shorten()`'s
docstring had been **promising a `selfCheck` assertion for a session without it existing**.
That assertion is real now, and it could not have been written against constants (rule 43).

**Four defects in the fitter, every one found on screen and three of them with a comment
beside them asserting the opposite** — a pane measured mid-transition, a box shrunk by the
pass's own previous write, the border box measured instead of the content box, and two floats
compared for exact equality. And two *layouts* that had been wearing a shortening rule's
clothes: the trail squeezing its steps rather than scrolling them, and a caller row that
cannot hold a name and a module on one line at all.

**Two of Tom's calls, both put to him with the alternatives measured against each other.**
A worklist title is **two lines then a mark**, with the whole of it on the hover — it had been
one clipped line, *94 of 94 rows*, showing the first thirty characters of every finding and
never the predicate. A caller row **stacks** its module under its name — side by side, every
split measured as a trade rather than a fix, and all 11 rows now show both entire where 7 of
11 used to overflow.

**Next, and it is the item that has been waiting behind this one:** the flow panel's real
worst case — `session.add_turn` at `_extraction_state.py:742`, 3,323 bytes over 53 lines, on a
*resolved* call, so its arrow can be opened. One outlier and not a class: the next largest
resolved call argument in the corpus is 923 bytes.

**A server is running** on `http://127.0.0.1:8787/` against `output/mensores`, the
two-revision pair. Nothing depends on it; `pkill -f "dunneflow serve"` ends it. Note that
`--port` yields to any free port if the asked-for one is taken, so a second server started
over a stale one lands somewhere else and says so on its last line.

**The debt is unchanged and it is rule 38's.** Everything in chunk B was measured at 1396px in
a browser context that reports `outerWidth: 0`, refuses to resize, and whose **screenshots did
not track the live DOM** — the region under a freshly measured element kept rendering the pane
beside it. Every number above is a measurement and every guard is a guard; what none of them is
is a look. Three things now wait on a real window: the constants surface, the blank-graph fix,
and this.

### The latest: no pane assumes what it was showing is still true (2026-09-03)

**Found by Tom mid-rabbit, and it relocated the defect twice.** *"When I change the center
panel to Code, that panel shows `mensores/_internal/_governed_gates.py` which is not what I
expect to see."* It was not: `/api/node` gave `mensores/disceptator/_extraction_state.py` for
that node all along. What was on screen was `state.codeFile`, which is **persisted** — the
file a session two days earlier left open, from a package the reader had never touched, drawn
with a title and a path and nothing to say it was stale.

`followSelectionIntoCode()` is guarded on the pane being on screen, which is right, and was
invited from **exactly one place**. The condition has two halves — the selection changed, and
the pane became visible — and only the first was ever served.

**Tom's rule is larger than the defect, and this file already contained it in one branch.**
*"Every possible venue that can change the point of view should be considered, so no control
should ever expect that it 'knows' what it was showing before is still true."* The table's own
comment has said exactly that since it was written: *"there are five ways into table mode ...
a call at each is exactly the list rule 51 says grows. Every one of them arrives here."*

The audit found three panes on each side of that lesson. **Reconciling inside `render()`:**
table, glossary/naming, curiosities. **Relying on every call site to remember:** the code pane
(1 site, and the wrong one), the stack (4), the diagram (7). All three moved.

**The four stack calls were mis-ordered as well as incomplete** — every one sat *before* its
own `render()`, so each was mounting into the previous view's layout. That is the defect
recorded as *"the graph should have been there"*, fixed on the mode toggle in 2026-08 and left
standing at the other three. In `render()` they are ordered right by construction, for routes
nobody has written yet.

**The price of a render-time reconcile is that it must be silent when there is nothing to do**,
because `render()` runs on every keystroke. `ensureDiagram` claimed its lock before asking, and
finished by rewriting the mount that exists so `render()` will not touch it — taking the
laid-out SVG and the reader's pan with it. And the code walk had to stop fighting a deliberate
file open: `codeFollowedFor` records **which subject** the pane was walked for, never merely
that it was, so a reader may open anything they like inside one selection and is still followed
the moment they pick something new.

*One guard was blind first and found by mutation*: it asserted `codeFollowedFor` was **named**
in the walk and passed with the early return deleted. Rule 37, again.

### Before that: every field fits its own box (2026-09-03)

**A constant is arithmetic wearing a measurement's clothes.** `MODULE_BUDGET_NAV = 30` is
honest because `.navsub` is `max-width: 11rem` — all 1,175 rows are the same box at any window
and any root size. None of the seven fields left over is like that: they are flex children
whose width is what a badge, a count and a line number leave them, and it differs *per row
inside one window*. `.rank-name code` is 156px on one cover row and 112px on the next, because
the `kind-tag` beside it is a different width. Rule 53, with rule 24 underneath it.

So `fitFields` measures the box each string is in. Reads batched before writes; candidates
measured on a **canvas**, never in the DOM, because `shorten()` is monotonic in its budget
(0 non-monotonic steps over module names, qualnames, paths and command lines) and the widest
budget that fits is therefore a seven-call bisection with no layout in the middle. **4 ms over
120 fields, 4.5 ms over 1,175** — so it runs at the end of every `render()` rather than waiting
for a frame, because a frame painted before the pass is a frame of the untruncated string.

*Three fields came off the list by being measured.* `.wl-title` is **prose** — every one of
the 107 findings contains a space and 80 contain a dot, so the middle-elide would decide the
head was ``self``, the leaf was the whole predicate, and elide the subject out of a sentence.
`.srcpath-v` is a **dead field**: `#srcPathV` is written by nothing and holds a 28-character
literal that fits. `.callhead code` was a **contradiction** — `breakable()` marks its joints
with `<wbr>` and `white-space: nowrap` made every mark inert, while its two siblings render the
same strings through the same function and carry 98 and 88 characters with no overflow (rule 13).

*A label is not the text on screen.* Every label reader goes through `labelOf` — `data-label`,
then the unshortened `data-full`, then the text — or a trail step records `stor…items` as the
place you were, which is rule 33 and rule 30 in the one surface built to take a reader back.

*The band tables now say what kind of string each column holds*, with **no default behind
them**: `modules_explained` prints a path where every other band prints a module and a module
where every other band prints a leaf name, exactly inverted, so a kind guessed from the markup
would strip a program root off a path, find none, and look deliberate.

**Twelve guards, each run against the defect it names, all twelve CAUGHT.** One existing guard
earned its keep on the way: four explanations were first written as HTML comments *inside
template literals*, where a backtick closes the literal and the page comes up empty — the third
occurrence of the defect `test_no_backtick_hides_in_an_html_comment` was written for. They
belonged above their functions anyway; inside a `.map()` body each shipped once per row.

### Before that: two dead controls, reported at the keyboard (2026-09-02)

**"On its own" could not be chosen.** The option existed, was selected, and the handler was
correct — it even carried a comment saying *"On its own is a real answer"*. Two things put
the comparison back. `comparedRevInForce()` could not tell *nothing chosen yet* from
*chosen: on its own* (both `""`), so the fallback that marks a first visit's file list
invented the pair back — **rule 49**. And fixing that changed nothing on screen, because
`versionStrip()` derived the compared end **again** with its own copy of that fallback, and
its "on its own" branch tested whether the *program* had a second version rather than whether
a comparison was running — **rule 51**. `comparedRev` has three states now, with `ALONE` a
named state rather than an id.

**The shelf could drop a thing and never open it.** A pin was `{label, note}` — neither is an
identity, so dropping worked (it needs only the row's position) and opening was impossible,
in the one surface built so a detour does not cost you your thread. The subject is carried
now, and **the three kinds are not one shape**: a node, a box whose id belongs to the drawing,
and a flow that needs its compartment. Pins were also keyed by *label*, which collides every
`__init__` in the program.

*Seven guards, each run against the defect it names. Two were blind first — one tripped on
the comment quoting the code it checks (the sixth time in that file), and one reported MISSED
when the **mutation** was wrong rather than the guard: `replace(…, 1)` hit the first of eight
occurrences, in another function. Rule 59 from the other side.*

### Before that: the constants surface (2026-09-02)

**Measuring first moved the target twice.** The record named a 6,924-character line as the
problem; `GOVERNED_GATES` is **8,586** and nobody had noticed it. And it is a class, not an
outlier: **739 of 2,638 constants exceed one card line, 301 exceed 300 characters, 23 (0.9%)
exceed a whole card** — Tom's "rare cases", quantified. Every value is a single line, because
`_literal` is `ast.unparse`.

**And the real defect was not the line length.** A constant rendered in the *routine-shaped*
inspector, which answered three questions a constant cannot be asked — nothing calls it *"a
way in, dead code, or a call DunneFlow cannot see"*, it calls nothing, *"everything it does,
it does in memory"* — while the 8,586 characters it had read were absent. Three plausible
sentences inviting the reader to conclude the analysis had failed. `viewInspectorConstant` is
routed on kind now, beside `FOLD` and `FLOW`.

**The value is whole in the one box that scrolls**, which is what lets the card bound itself
at 240 characters and say so: rule 8 allows abbreviation only where the complete content sits
beside it, and that pane is where *beside it* lives. The card's `-webkit-line-clamp: 3` was a
silent filter inside the surface whose whole job is to answer *what is this*. It counts
**characters, not lines** — no value carries a newline, so "94 more lines" would report the
pane as the program (rule 32).

**Tom's three calls.** The card stays non-interactive and a click opens the value — put to
him because `.hovercard` is `pointer-events: none` by a recorded decision, and settled by
measurement: the longest qualname is 107 characters, so *names never need a scroll box*.
**Head and leaf, middle elided**, one rule for all kinds. And a moved constant shows **a mark
only**, with the name clickable and opening on both values.

**Every presence row was a bare `<code>`** — `Constants ◈7` named seven constants and not one
could be opened. They carry a route and a subject from the server now; ways in carry none and
stay text, because their route wants the routines they start and that table cannot reach them.
`EXPECTED_SCHEMA_VERSION` opens to **28 beside 27**, labelled by revision.

**`shorten()` replaces `moduleTail`**, and the program root is dropped first — all 566 modules
begin `mensores.`, so keeping the head spends nine characters saying what every row says and,
for a three-segment module, elides the *package* to afford them. `COVER_ROOT` answers the
question `COVER_PACKAGES` had a comment saying it could not. **742 of 1,019 navigator rows now
show whole**; the CSS backstop fired **0 times**.

*Four defects found in the doing, three of them mine — `state.insp` declared in two files with
only one winning, a root lookup that stripped nothing because `mensores` is itself a package,
moved rows built with no route, and a floor that guaranteed the overflow it prevented. All
four in `HANDOFF.md` under this session's heading.*

### Before that: the topbar search does what it says (2026-09-02)

**Reported as a question:** *"I can't find `frozenset` by searching for it. Nothing appears."*
Then the better one — *"What does search DO, exactly? Is it a filter, a focus, or a
highlighter?"*

**A filter, on one list.** It matched a substring of a routine's name or module and nothing
else, while the box said *"Search routines, tables, boundaries…"*. `audit_blobs` — a real
table — matched **4 routines** by substring while the Database group holding that table said
nothing, which is the worst kind of pass: it looks like it worked. `VIRTUAL_ENV`, a real
boundary, said *nothing matches*. And `frozenset` is in the source **408 times in 136 files**,
found by the *other* search, which nothing on screen mentioned.

**Now every named group filters**, through one predicate handed to each (rule 36), and each
filters **before** it slices — searching a bounded list would answer about the first eight of
forty-three. `structures` rides with `/api/routines` (671 rows against 4,786) and there is a
**Structures group**, which the search had nowhere to put before.

*Two defects found in the doing.* **Rule 44 committed inside the fix for rule 44** — the first
draft filtered on `b.target`, a field the cover has never sent. And four groups had no note at
all, so a search matching nothing left a heading above an empty body (design rule 1).

*What it still cannot do, and says so:* a boundary **target** is not findable — 1,741 of them,
mostly expressions, against nine kinds in memory. The note names the source search instead.

**And it takes a regular expression now.** *"Does that mean I can use regex in the Search
box?"* — yes, but in the *other* one: the Code box has taken a pattern since it was built and
the topbar was a substring test. Tom's call, give the topbar the same three flags. `Aa`,
`|ab|`, `.*`, with their own keys so a literal name hunt and a pattern grep can be in force at
once. Compiled **once per keystroke** and cached on the query plus the flags — 5,560 names
means a per-row compile would be 5,560 of them per character. A pattern that will not compile
**says why** rather than reading as *nothing matches*, which is the false conclusion this
whole thread began with.

### Before that: the cursor over a diagram (2026-09-02)

**Opened as "the arrow stroke is 1 px, thin to aim at" and that was the smaller half.** Tom
drove it: the `cursor: pointer` hand is the web's *this is a link* glyph, wrong for a drawing
you **aim** at — its hotspot is a guess and it covers what you are aiming at. Both the cursor
and the stroke are Settings now (design rule 2): arrow / crosshair / hand, defaulting to
**arrow**, and 1–4× on the stroke, which had no width set at all and so took Graphviz's
default of 1.

**The first fix was wrong and the report corrected it.** It styled only what was *pickable*
and left `.dgm-canvas { cursor: grab }` alone — *"still Hand most of the time, it only
switches to arrow when near the link."* The canvas is most of what a pointer is ever over.

**And then it turned out not to be an aiming fix at all:** *"This change resolved a major
confusion for me… now I understand how the diagrams work — click to view Inspector."* The
canvas's `grab` was a claim that the surface pans, and it **wins on area**; the boxes' own
`pointer` was visible only in the instant the pointer crossed one, so the drawing read as a
picture to pan rather than a set of things to click. Every control was wired and the
self-check passed the whole time — nobody found out clicking a box opened the inspector.
That is **design rule 27**, and it is design rule 16 from the far side.

*Also fixed on the way: `:active` was the wrong moment for the grabbing hand — it fires on
any press, so it flashed on every click of a box. It is on the real `dragging` flag now, past
the slop, which is rule 72's own lesson in a cursor.*

### Before that: structures, compared at last (2026-09-02)

**The last prose surface, and it was three lanes rather than one.** A class docstring was
compared by nothing — and so was the *presence* of a class, which is why the docstring had
been left out: there was no row for it to be a tag on. On Mensores' pair that hid **8
structures that appear or vanish**, reported nowhere, on a page free to say *no differences
found*.

**The subject question was settled by measuring the wrong answer first.** Rule 74 says a
diagram box *is* a class, so routing through `state.fold` looks obvious. A box is built from
**routine** nodes, so it exists only where a class has methods: 192 of 671, with **every**
TYPE_ALIAS, ENUM and TYPEDDICT having none and never able to — and 4 of the 8 rows that
actually move have no methods. Rule 77, a third time, caught by counting. Nothing had to be
minted instead: `describe()` already resolves a `structures.id`, verified live on a
methodless TYPE_ALIAS before a line was written, so these rows carry an **id** where the four
presence lines carry only a name — rule 30 applied honestly rather than uniformly.

Tom took **Structures** for the name (the store's own word; "Classes" would be wrong for the
138 aliases and enums) and added the *declares differently* lane on top of what he asked for,
so nothing about a structure is left uncompared: `7 · 1 · 1 · 0` on the pair.

**A defect shipped and caught within the hour, and it is rule 40.** `structures_explained`
returned 5 against a ground truth of 0 — every one already a presence row, because
`_moved_prose` compares the **union** of the id sets and a structure on one side only carries
its docstring with it. Two lanes recording one act. Caught only because the number disagreed
with a measurement taken before the code existed; the routine and module lanes each guard it
in a different place, so this was the third application of one rule.

**A surviving mutation that was the guard's fault.** Keying fields on `idx` rather than
`name` survived the reorder test, because the fixture's two fields differed only in name —
swap them and *either* key gives the same set. They differ in type now and it is caught. Rule
59's companion: ask whether the guard is weak before changing either.

**+13.3 ms**, median of four alternating builds of HEAD and this in one process on a warm
disk — inside the 20 ms `/api/changes` had left. Driven in Chrome on the real pair: bands,
counts, singulars, tags and stat tiles all correct, the row reachable by `elementFromPoint`
and clicked through a **real pointer sequence** landing on a child element, and the inspector
answering `ClaimVerdict · ANALYZED · STRUCTURE` — the structure, not one of its members.

*Found in passing and left alone: clicking a change row files **two** trail steps. Verified
pre-existing — a routine row does it too — so it is rule 76's family and not this work's.*

### Before that: the record split into files that can be carried (2026-09-02)

`CLAUDE.md` had reached 162,893 bytes, past the 150,000 a session loads — so it was being
**truncated silently**, and the part falling off the end was whatever sat there. Two thirds
of it was 102 rules, cited as bare numbers 768 times across `src/` and `tests/`, so nothing
could be deleted or renumbered. The bodies moved and the titles stayed:

**Figures as measured at the split, 2026-09-02, and left as taken.** Every count and byte
size below is of that day — the rules have been added to since, and rewriting one column
without retaking the other is a different measurement under the same label (rule 24). The
live counts are at the head of this file.

| File | Was | Now | Holds |
|---|---|---|---|
| `CLAUDE.md` | 162,893 | **34,583** | commands, gates, architecture, the **index** of all 102 rules |
| `BRIEFING.md` | 122,578 | **46,056** | state; the `Before that:` chain became a 26-row pointer table |
| `RULES.md` | — | 92,158 | the 76 engineering rules, verbatim |
| `DESIGN-RULES.md` | — | 27,029 | the 26 design rules, verbatim |
| `PERFORMANCE.md` | — | 22,154 | every measured figure, verbatim |
| `HANDOFF.md` | 443,524 | unchanged | the archive, read on demand rather than loaded |

Proved lossless by construction rather than by reading a 3,194-line diff: the split
**reconstructs the original byte for byte**; 1,972 of 1,974 substantive lines were found
verbatim in the new set, the two misses being the two deliberately rewritten; rule numbers
were **enumerated**, 1–77 with 21 correctly absent; all 33 pointer anchors resolved before
the cut; and the cut region was scanned for open items, which found **two that lived nowhere
else in this file** — the blank-graph fix and the `m.<module>` research — now restored to
the open list below. Analysing both trees gave identical doc figures, so the duplicated
titles cost nothing: the index is fenced, and rule 12 keeps prose out of a fence.

**Read `RULES.md` before working in an area a rule governs.** A title is enough to recognise
that a rule applies and not enough to apply it — that is the one risk this split carries.

### Before that: what a routine says about itself, and what a module says it is (2026-09-01)


**The last item on the open list, and it turned out to be two.** `routines.docstring` was in
the store and compared by nothing; so was `files.doc`, and they need different subjects.

**The routine lane corrects a reason, not an absence — which is what makes it unlike the
comment lane.** A leading comment sits above the `def` and so outside `body_hash`, which is
why rewriting one could vanish entirely. A docstring is *inside* the `def`, so it is always
inside `body_hash` and always reported — filed under **edited only**, the band this tool
describes in its own words as *internal computation, what it exists not to report*. On
Mensores' pair `_production_audit_db_path` had a deprecation notice and its whole reasoning
rewritten and sat exactly there. So `docstring` is a **tag** beside `comments`, and it can
never be a band: `explained_only` holds what would be in no band, and nothing reaches it by
this route.

**The canonical question, asked a fourth time and answered differently — by measurement.**
`_constants_moved` predicted this would come round and said the answer would depend on how
the column is filled. It does. A comment reaches the store as one row per *physical line*
with no paragraph structure left to keep, so the comment lane joins the lot and collapses.
A docstring arrives as one string through `inspect.cleandoc`, **blank lines intact**, so the
structure is there to keep. Two experiments over the real 3,769:

```
re-wrapped at 72 / 79 / 88,      as written    2,060 · 1,652 · 1,602 falsely reported
not one word altered             collapsed         0 ·     0 ·     0
                                 by paragraph      0 ·     0 ·     0

every paragraph merged,          collapsed         0 reported   ← blind
1,996 affected                   by paragraph  1,996 reported
```

Both forms are silent on the noise, so the re-wrap does not choose between them. Merging
paragraphs does: it changes no word and destroys the separation PEP 257 gives the summary
line, and a full collapse cannot see it. Same zero on the noise, 1,996 more on the signal.

**The module lane is a new subject, and it is Tom's call.** `files.doc` states what a module
*is* — 619 of 628 files. The cheap implementation is to hang it on `<module>`, and it covers
**487 of 628** while missing 141 *silently*: `<module>` exists only where a file runs
something at import, so in a file that runs nothing, a rewritten module docstring moves no
body hash, no fact and no row, and the page states **"No differences found."** That is
**rule 77**, and it was caught by counting rather than by a false result — 619 against 487,
one query each. `modules_explained` rows carry a **path**, and the route opens the file.

**Two live defects found on the way, neither of them in this work.**

*The navigator's note had been wrong since the comment lane landed.* `changeNote()` decided
"no differences found" from `only_in_base + only_in_compared + behaves + edited_only` — so a
pair whose one difference is a rewritten comment, a table that appeared, or a constant whose
value moved said **no differences found** in the group a reader lands in first, while the
page below listed it. The same false claim the explained band was built to remove, surviving
in the other of the two surfaces (rule 51). `identical` is the server's own answer and is now
what is asked.

*And the file route did nothing visible.* Found by clicking the row, not by any test:
`openCodeFile` opens the pane and leaves the centre alone, which is right inside the Code
group and wrong from a worklist page — state set, file loaded, not a pixel moved. Rule 77's
companion, and rule 51 in the shape that rule is about.

```
18/18 mutations caught over a baseline proved green first
three passes: five survived the first (three unguarded surfaces, one weak fixture, and two
weak mutations — the `behaves` one wrote to `moved` after `behaves` was computed); one
survived the second, and it was my own guard summing two overlapping substring counts so
either site could drop the plural and still clear the bar
```

**+3 ms, and it is measured like for like**: 451 → 454, median of eight alternating builds
of HEAD and this in one process against a warm disk. The two lanes are 3.2 ms and 2.2 ms in
isolation, and the shared bound takes the docstring lane from 22.3 ms over all 628 files to
3.2 over the fifteen that differ — 19 ms, which is almost exactly the 20 ms of headroom that
row has. That bound now has a guard of its own, because no *answer* can catch it being
removed: every prose lane returns the same rows bounded or not.

**Absent rather than estimated: a picture of the band.** The automation tab's capture is
fixed at 784×349 whatever the window (rule 38), so the worklist below the fold cannot be
photographed. What *was* driven: both docstring tags on the real Mensores pair, the edited
tooltip, the band and its stat tile, the row reachable by `elementFromPoint` and clicked
through a real pointer event to the file, the navigator group joining the same accordion,
and the singular. The stat tile's violet is visible in the one capture that fits.

### Two things waiting on Tom's eye, and neither is a bug

1. ~~**The flow panel's arrow stroke is 1 px**, which is thin to aim at.~~ *Closed
   2026-09-02, and it was never really about the arrow — see the top of this file. The
   stroke is a Setting now, and the **cursor** turned out to be the larger half: `grab` on
   the canvas was claiming the whole pane pans, which drowned out the boxes saying they are
   clickable. That earned **design rule 27**.*
2. ~~**A 1,347-line `frozenset` argument exists in this corpus**~~ *Closed 2026-09-02, and
   the constants half of it is built. The entry had already been corrected once: the
   `frozenset` is **not reachable from the flow panel at all** — external, `at_boundary = 0`,
   a builtin, so no arrow is drawn — and the same expression sits in the store twice, as
   91,224 bytes in `call_args` and as **6,924 on one line** in `constants`. The constants
   surface now shows a value whole in a box that scrolls, and the card bounds itself and says
   by how much. Its real worst case turned out to be `GOVERNED_GATES` at **8,586**, which
   nobody had named. The `call_args` side keeps its recorded* wrapped, not elided *decision.*

*There was a third — the routine lane drawing* behaves differently *in `--text-muted` while
the legend and the findings drew the same idea in `--diff-moved`. Put to Tom on 2026-09-01
and unified on `--diff-moved`; see the top of this file.*

### What is next, and it is open

Nothing in chunk 5 is outstanding, the argument gap is closed, and the two small things
filed as known are done.

1. ~~**`CURIOSITIES` has never been put on screen.**~~ *Built 2026-09-01.*
2. ~~**A rewritten docstring is not compared either.**~~ *Built 2026-09-01, and it was two
   lanes rather than one — see the top of this file.*

**This file owns the open list. There is no second copy.** `HANDOFF.md` used to keep one at
its foot and the two drifted twice in two days — an audit on 2026-09-02 found each carrying
something the other had closed, and then the same session closed the class docstring in one
copy and not the other. Rule 51 in the documents: one truth, one place that owns it. Record
*how* an item was closed in `HANDOFF` under its own dated heading; record *whether* it is
open here.

Audited entry by entry on 2026-09-02, none of it scheduled:

*Struck in that audit:* **"what is an occurrence for `LOST_EDGE`"** had stood as a question
for Tom that decided a whole feature. It **dissolved** on 2026-08-31 rather than being
answered — the detector groups by `callee_expr`, so a finding is one per expression, the
callers are its count and the rivals are in its title — and the anomaly worklist it was said
to block was built the same day. It had been telling every session since that the largest
feature was blocked on an answer nobody owed.

- ~~**A class docstring is still compared by nothing.**~~ *Built 2026-09-02, and it was
  three lanes rather than one — presence, declaration and docstring. See the top of this
  file.*
- ~~**Chunk B of the shortening work: twelve fields still cut the tail.**~~ *Built
  2026-09-03, and measuring first struck three of the twelve and changed the mechanism — see
  the top of this file. The budgets are **measured at render time**, not constants; the
  `selfCheck` assertion exists and is honest; `.wl-title` is prose and refuses the
  middle-elide; `.srcpath-v` was a dead field; `.callhead code` wraps. `.navsub` keeps its
  constant and the boundary is stated. `.argrow` keeps its* wrapped, not elided *decision;
  `.leg .nm` is left alone.*
- **Three surfaces have never been *looked* at in a real window** — the constants surface,
  the blank-graph fix (rule 49), and now chunk B. Not three items: one debt, rule 38's, and
  it grew this session rather than shrinking. The automation tab reports `outerWidth: 0`,
  refuses `resize_window`, and its **screenshots did not track the live DOM** — the region
  under a freshly measured element kept rendering the pane beside it, so even a zoom on
  correct coordinates showed the wrong thing. Measurement through the DOM still works and is
  what every figure in this session rests on.
- **`<module>` is answered in a routine-shaped inspector.** It draws *"Nothing in this map
  calls it — that is either a way in, dead code, or a call DunneFlow cannot see"*: three
  plausible sentences and none of them the true one, which the routine list already carries as
  its own `why` — *"Module-level code: runs at import, before anything is called."* The same
  shape as the constants defect, and `viewInspectorConstant` is the precedent: route on kind.
  Found by Tom on the way past the Code-pane defect, 2026-09-03.
- **Clicking a change row files two trail steps**, for a structure and for a routine alike.
  Found 2026-09-02 and verified pre-existing rather than introduced. Rule 76's family — an
  echo arriving as an act — and the fix is to the selection path, not to any one lane.
- **A kept fold and a kept flow have never been opened on screen.** The shelf routes three
  kinds and the node kind is verified; the other two need a compartment drawn. The kind and
  the route are guarded against each other at the source, in both directions, which is why
  that guard exists rather than a click — but it is a shape check and not a look.
- **Every surface that offers "keep this" is an inspector pane.** A curiosity, a thread and
  a search hit are all things a reader would want on the shelf and none of them can be kept.
  Not a defect, and the obvious next question now that a pin carries a subject.
- **`holds` is not in `insp`'s defaults**, so the fold pane's section starts closed whatever
  it wanted and "Collapse all" cannot see it until someone has opened it once. Found
  2026-09-02 while adding two sections beside it; not fixed, because its default is a
  decision about that pane. One line in `settings.js` either way.
- **`navIds` splits `data-navid` on a space**, so a presence row for a *named file* whose
  name contains one would resolve to two ids that name nothing. Mensores has 0 and a
  constant's `module.name` cannot hold one, so nothing exercises it; the fix belongs to
  `navIds` rather than to any caller.
- **The blank-graph fix (rule 49) is reasoned and guarded, never *seen*.** The automation
  tab never mounts the graph — `canvas MISSING`, `frames 0` — so rule 38 applies and it
  wants a real window before anyone calls it verified.
- **`m.<module>` as a language feature, with research owed on prior art** — how other tools
  present a construct the *language* put there rather than an author. Decided 2026-08-30:
  not filtered and not bare, but a curiosity carrying its own explanation, scoped to the
  language that produced it rather than special-cased in the diff.
- **The worklist's two jump buttons are half done.** The design rule 16 defect is fixed —
  they no longer look live while doing nothing, and each states why it does not act. Making
  them *act* is blocked on precision, not effort: a finding carries the **name** it found,
  not the node, so resolving it would guess between every routine sharing that name (rule 5).
- **Per-plate sphere scaling, and stack orientation** — carried in `HANDOFF`'s list and
  missing from this one until the 2026-09-02 audit. The second is structural: `OrbitView`
  has no camera roll.
- The filed small things: the rendered markdown is not revision-named, `--revision` on
  `analyze` (it exists on `serve` only), the navigator's search box pinned-when-open
  (decided 2026-08-30, never built), the two vocabulary-lane precision defects, packaging as
  a binary.

### Before this, in order — the full record is `HANDOFF.md`

Each session below was summarised here and is recorded **in full** in `HANDOFF.md`, with
what it cost, what it found, and what was rejected on the way. The anchor is what to search
for; chunk labels (`5v`, `6a`) and dated headings are stable, line numbers are not.

| When | What was built | Search `HANDOFF.md` for |
|---|---|---|
| 2026-09-01 | Curiosities: the doorway panel, each extremum stating its middle | `Curiosities: the doorway panel` |
| 2026-09-01 | The change worklist sees a rewritten comment | `sees a rewritten comment` |
| 2026-09-01 | A presence line says what it left out; one idea stops having two colours | `A presence line says what it left out` |
| 2026-09-01 | What a call passes, and what a constant is | `what a call passes` |
| 2026-09-01 | The overlay on the findings, and the key it had to be built on | `The overlay on the findings` |
| 2026-08-31 | A finding says what makes it that finding — the identity question, answered | `what makes it that finding` |
| 2026-08-31 | An edge says what flows, and the echo that had been eating the subject | `An edge says what flows` |
| 2026-08-31 | The call-site arguments, as written | `The arguments, as written` |
| 2026-08-31 | Diagram mode, reading both ways; the box that answers about itself | `Diagram mode — built` · `A box answers about itself` |
| 2026-08-31 | The plate diagram — withdrawn, then built | `Withdrawn — Tom, 2026-08-31` · `The plate as a diagram` |
| 2026-08-31 | Sizing a plate by what it holds | `Sizing a plate by what it holds` |
| 2026-08-31 | The second altitude — the module level of detail | `The second altitude` |
| 2026-08-30 | One history — the trail and undo unified | `6i.` |
| 2026-08-30 | The comparison over the routines: tables and the list (chunk C) | `6g.` |
| 2026-08-30 | The comparison over the code: the code browser (chunk C) | `6f.` |
| 2026-08-30 | Colour sets in Settings (chunk B) | `6e.` |
| 2026-08-30 | Switching the base | `6d.` |
| 2026-08-30 | The default read from the versions, not guessed | `6c.` |
| 2026-08-30 | Base and compared — two directories, no claim about which is newer | `6b.` |
| 2026-08-30 | Stored paths are relative, and the root is not recorded | `6a.` |
| 2026-08-30 | The change worklist, looked at for the first time; choosing two points in time | `5y.` · `5z.` |
| 2026-08-29 | Two points in time, and the change worklist | `5w.` · `5x.` |
| 2026-08-29 | Search inside the source | `5v.` |
| 2026-08-29 | The code browser, and a snapshot that has a name | `5u.` |
| 2026-08-29 | Four panes, and the pop-up that learned to be read | `5t.` |
| 2026-08-28/29 | The navigator that survives a long list; you-are-here; focus | `5o.` · `5p.` · `5q.` · `5r.` |

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
| Clicking the arrow selects that node alone and frames it — it **sets**, never toggles | rule 47; rule 33 |
| Focus separates *what may answer* from *what is drawn*; the fog stays on screen | rule 47; design rule 19 |
| The navigator is a fixed header over a scrolling body; group headings are sticky | rule 45's session; `HANDOFF.md` 5o |
| The routine list is grouped by package, and the package is the **plates'** package | `queries.py` `NAV_ROUTINES`; rule 30 |
| How many routines a package lists is the reader's, `All` included | `HANDOFF.md` 5o |
| A search opens what it matched only while the answer is small, and says when it did not | rule 45 |
| The centre pane's **mode is not part of where you were** — Back restores the subject and leaves you in the mode you are reading in | `HANDOFF.md` 5t; `CENTRE_MODES` |
| The pop-up stays `pointer-events: none`; drilling in is a **key**, never a click on the card | rule 48; `HANDOFF.md` 5l |
| The detail window holds **open or not**, never *which* — it reads the one selection | rule 51 |
| Two windows are **peers over a `BroadcastChannel`**, never opener and child | `HANDOFF.md` 5t |
| A detached view is the **same application** under `?view=detail`, never a second page | `HANDOFF.md` 5t |
| One renderer for a signature, `schema.signature_parts`, for the documents and the card alike | rule 13; `HANDOFF.md` 5t |
| A clickable name in source is `calls.callee_id`, **never** a name match; no column means no inline span | rule 1; rule 5; `code.py` |
| **No syntax colour** in the code browser — kind is the dimension colour is spent on | design rule 4; `HANDOFF.md` 5u |
| The code browser runs in three places over **one** `CODEFILE`; a file is not a node and selects nothing | rule 51; rule 30 |
| `WORKING` is a **state**; a revision is identified by when it was captured | rule 20; `sourcedb.py` |
| A read defaults to the newest revision, never only to WORKING — sealing must not blind the dashboard | `sourcedb.py` `current_revision` |
| The navigator's width cap is what the window can spare; the Code group keeps its own width | rule 28; `HANDOFF.md` 5u |
| One box, two lanes: file names filtered here, source text asked of the server | `HANDOFF.md` 5v |
| Files first, then lines — a flat hit list is the haystack again | rule 45; `HANDOFF.md` 5v |
| One compiled pattern for the count and for the lines beneath it | rule 13; `search.py` |
| A regex turns whole word **off**; a bad pattern is named, never answered with no rows | rule 46; rule 20 |
| Where a hit sits is a line range, innermost span first — never a name match | rule 5; rule 10 |
| No index: FTS5 is token-based and cannot find `_emit` inside `self._emit` | `search.py` |
| The inflate cache is **bounded and says so** — 64 MB, keyed by content hash | `sourcedb.py` |
| A program dir holds `graph@<rev>.db` and `docs@<rev>.db` per revision, beside one `source.db` | `revisions.py`; `HANDOFF.md` 5w |
| The filename is a convenience; the identity is `meta.revision` **inside** the file | rule 30; `revisions.py` |
| A legacy bare `graph.db` is **read**, never rewritten into the new shape | rule 20; `revisions.py` |
| The layer work leads with a **change worklist**, and the picture follows the list | Tom, 2026-08-29; design rule 9 |
| No comparison key contains a **position** — one inserted import would move every fact | `make_id`; `changes.py` |
| A routine that arrived is not also counted as behaving differently | rule 40; `changes.py` |
| The search box is a **design-rule-2 pair**: sticky or scrolling, a Setting | Tom, 2026-08-29 |
| Stored paths are **relative to the tree that was read**; the root is used and never recorded | Tom, 2026-08-30; rule 60 |
| Legacy stores are migrated **in place**, never rebuilt — rebuilding orphans a snapshot whose tree is gone | Tom, 2026-08-30; rule 62 |
| A binding is **deferred** until something opens a file from disk; the control says `not bound` | Tom, 2026-08-30; design rule 16 |
| A call site has an **identity**, and it holds no position — an ordinal among identical expressions in one caller | Tom, 2026-08-31; `call_site_id`; `make_id` |
| An argument is recorded **as the caller wrote it**, never `ast.unparse`, never shortened | Tom, 2026-08-31; rule 8; rule 75 |
| The temporal pair is the **two society clones**; `mensores-overhaul` is a third tree | 2026-08-31; "How to verify" |
| An arrow is a **subject**, like a box and a node; the three are exclusive by construction | rule 74; rule 76 |
| An argument binds to a parameter **only where the source settles it**, and says why not | Tom, 2026-08-31; rule 1 |
| Call sites are listed, never grouped and never bounded — the aggregate is on the arrow | rule 32; rule 8 |
| The engine's **echo** of a selection it was handed is not a new act by the reader | rule 76 |
| A rewritten comment is a **fifth band**, never a sixth fact kind — `behaves` promises what a routine *does* | Tom, 2026-09-01; rule 32 |
| `explained_only` holds only what would be in **no** band; a routine already in one gets a tag | rule 32 |
| Comments are compared **joined in line order and collapsed**, never as written | rule 1; measured |
| The comment scan is bounded by **files whose bytes differ** — equal hash, equal comments | `filediff`'s argument |
| The headline count takes `explained_only` and still leaves `edited_only` out | this tool's subject |
| *Behaves differently* is **in the difference channel**, on every surface that draws it | Tom, 2026-09-01; rule 51; rule 69 |
| `edited` stays **out** of that channel — the channel holds three directions and a ground | rule 69 |
| A presence group's unfold is keyed on the **band**, never on the sign that swaps with the assumption | rule 65; rule 30 |
| A presence line names six and puts the **whole** set one click away, never the remainder | rule 8; design rule 1 |

## How to verify — all three, before saying anything is done

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then against real code, because unit tests on a toy program cannot catch a resolution
defect that only appears at scale:

```bash
uv run dunneflow analyze ../society-2026-08-29/src --name mensores
uv run dunneflow serve output/mensores
```

**The pair is the two society clones, not `../mensores-overhaul`.** That is a third copy
of 626 files and is neither end of the comparison; this file and `CLAUDE.md` both named it
here and it cost a wasted analysis. All three trees are read-only; all output belongs in
`output/`. Rebuilding the pair after a schema bump is in `CLAUDE.md` — two analyses and a
seal, in that order, because a sealed snapshot is never re-analysed in place.

**Do not re-analyse into `output/mensores` while verifying two versions.** It holds the two
revisions everything temporal is checked against — `2026-08-31T22:53:57Z` (WORKING, 628
files, from `../society-2026-08-29`) and `2026-08-31T22:53:15Z` (FOR_COMPARISON, *Society at
e2e658b4 — 2026-08-26*, 625 files, from `../society-2026-08-26`) — and a third would change the setup the recorded figures belong to. It is enough on
its own to verify a base switch, both directions, with no scratch corpus.

Ground truth is in `CLAUDE.md` — both halves. Positive: the four executables must all
appear in "Where to start" with plausible reach, **and they must still be there after a base
switch**, which is the cheapest check that a switch rebuilt everything rather than most
things. On the older revision that is 175 ways in and 3,950 boundary touches, with
`mensores` / `mensores-mcp` / `mensores-scriba` / `mensores-signator` at 1,366 / 421 / 265 /
111. Negative, and it matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about* naming
standards and must yield **zero** naming rules.

### The traps that cost this session

- **The automation tab gets no animation frames.** `ResizeObserver` never fires and `rAF`
  never ticks in it, so anything needing a rendered frame cannot be observed there — a
  confident, reproducible and entirely false finding came out of measuring through one.
  Static DOM facts (grid tracks, widths, classes) survive; everything else must be driven
  by a human in a real window. Rule 38.
- **`grep` can silently answer "no matches" about a file it has decided is binary.**
  `shell.js` is 412 KB of UTF-8 and `file` calls it text, but `grep` without `-a` returned
  *nothing* for `srcPath`, `getElementById` and `source_root` — all three of which are in
  it. Acting on that false negative, a live control reading a field the server no longer
  sent was declared safe; it rendered an empty box on every load (rule 44). **Use `grep -a`
  on the client sources**, and treat "no matches" in a large file as a claim to check
  rather than an answer. Rule 43 in the instrument, and the cheapest one yet to avoid.
- **A `/* */` block whose continuation lines are plain indented prose is invisible to
  `_code()`.** It blanks comment *lines* — those starting `/*`, `*` or `//` — and this
  codebase uses both that style and bare indented continuation. A new guard tripped on the
  paragraph explaining the defect it was written from, which is the fourth time in this
  file. Write client comments in the `*`-prefixed style. CSS has its own `_css_code()`:
  with no template literals and no nested comments, the whole-block strip that is unsafe
  in JavaScript is exact there.
- **The browser writes to your controls.** Chrome restores a `<select>`'s value across a
  reload, outranking the `selected` attribute the code wrote — so a control can name a state
  the page is not in while every source-reading check passes. Rule 67: assign the value from
  state. More generally, `elementFromPoint` answers *can the reader reach it*; nothing in a
  test answers *what has the browser since done to it*, and only driving does.
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

- **A scripted click proves the handler, not the path to it.** `element.click()` fires the
  listener whatever is painted on top. A whole session's driving verified every control on
  the detail window and could not see that its scrim was over it. Use `elementFromPoint`.
  Rule 48.
- **A class the generator emits around every item cannot name one item.** `buildNav()` wraps
  every group body in `.nav-items`, so `querySelector(".nav-items")` inside a group returns
  the **wrapper** — and the file filter had been replacing the box it was typed into on every
  keystroke since it was written, with a guard for exactly that passing throughout. Rule 54.
- **A component with two shapes needs two sets of rules, and must say which it is in.** One
  flex chain served both and squashed the list state to 118px while 1,900px overflowed it and
  painted over the panels below. Every row present, sized, correct and unclickable.
- **Your mutation harness is a check too.** Both of this session's reported every mutation as
  surviving, because they read pytest's output rather than its exit code. Rule 43.
- **Three times now: a control correctly wired to a stylesheet that could not carry it.**
  `[hidden]` beaten by a later `display`, a `th` width ignored under `table-layout: auto`,
  a sticky header bound to a box that never scrolls. Markup and handlers both check out.
- **A blindness check keyed to the design erodes; key it to the instrument.** A guard
  asserted four distinct `rtnchg-` class names existed "or this guard is blind". Moving one
  of them into the difference channel left three, and the obvious fix -- lower the floor to
  3 -- is how such a check reaches zero over a few sessions without anyone deciding to
  weaken it. It counts what the regex *found* now (one `cls:` literal per state), which is a
  fact about the instrument rather than about the design it is pointed at.
- **A guard that passes first time has not been tested.** Twelve did this session. Every one
  was a containment check over too wide a span, or against a name where the claim was about
  a behaviour. Run every new guard against its own defect *and* a half-working version.
- **A comment explaining a defect will trip the check for it.** Three did; `_code()` strips
  comment lines. Its first version stripped string bodies too — which in this codebase is
  where the checked code lives — so every check passed against an empty string.
- **A promise can be printed rather than wired.** Three keyboard badges — `S`, `G`, `T` —
  named keys nothing listened for, and two of them sat on buttons with *no attributes at
  all*. The runtime self-check enumerates `data-*`, so a control carrying none is one it
  cannot see. Design rule 16 one level further out than any check here was looking.
- **A search for a class name cannot see a class that is computed.** The fact lane spelled
  the third difference `tone-mod` -- a fourth spelling of one idea, with a rule of its own
  painting it grey a class name away from the `.tone-moved` everything else used. No search
  for `tone-moved` could find it, because the renderer writes `tone-${tone}` itself and what
  travels from the caller is a bare `"mod"`. The guard that checks the tone *vocabulary*
  passed throughout; only a guard naming the surface caught it, and it was the one mutation
  to survive a first pass.
- **An equal-specificity class rule loses to a later one, and a colour is the quietest place
  for that.** `.hc-chg` sets a colour on the very element a `.tone-*` class lands on, so the
  two tie and source order decides -- the hover card would have said *behaves differently*
  in grey while the row that opened it said it in violet, with the markup, the class and the
  handler all correct. Found by working the specificity out by hand, not by anything that
  ran. Rule 29, which was filed under media queries and is not about media queries.
- **A guard that reads past its subject vouches for the wrong thing.** `_fn` stopped at
  `\nfunction` and swallowed the `async function` after it; a badge check took "everything
  after the keydown listener" as the handler. Both passed against their own defects.

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
