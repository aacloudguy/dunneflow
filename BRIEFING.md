# DunneFlow — briefing

**Read this first, then stop.** It is an index, not a fourth copy of the documentation.
It exists so a fresh context can be useful in a few minutes instead of an hour.

| Read | For |
|---|---|
| `CLAUDE.md` | The rules. 88 engineering rules — numbered to 89, since 21 does not exist — and 30 dashboard design rules, each earned from a false result on real code. **Binding.** |
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
                       source.db     (file bodies, content-addressed)
                       docsource.db  (document bodies, the same store, its own kind)
```

| Module | What it is |
|---|---|
| `schema.py` | The fact contract. Every extractor in any language emits these types. |
| `store.py` | SQLite. **The spine, not an export format.** Nothing holds the program in memory. |
| `docstore.py` | `docs.db` — parallel to the graph, never inside it. |
| `sourcedb.py` | `source.db` — file bodies. The one store that is never discarded (rule 25). And `DocSourceStore`: the same class with a different `kind`, writing `docsource.db`. |
| `migrate.py` | Stored paths absolute → relative, in place. The prior state it can speak for, named (rules 60–62). |
| `extractors/python/` | stdlib `ast` + `tokenize` only. No third-party parser. |
| `extractors/docs/` | Markdown / rST / text, scanned by hand. No markdown library. |
| `detectors/*.yaml` | **The extension point.** Teach a framework here, not in code. |
| `canonical/` | Whether two writings are the same expression, per language. **Beside** the extractors, never inside one — see the cache-key note in `CLAUDE.md`. |
| `resolve/` | Call graph, CLI trees, flows, naming, glossary, traceability, mirror. `naming.py` is the **derived** lane, `stated.py` the **quoted** one — read in one place, by three readers. |
| `resolve/shape.py` | **The amendment, judged once.** What moves inside a loop or a decision, by a range join, and whether that makes it a subject. Nothing is dropped for failing it. |
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
| `cover.py` · `detail.py` | the cover · the inspector and the hover card |
| `threads.py` | adjacency by *interest* — why a neighbour is worth a detour |
| `curiosities.py` | the doorway panel — ten measured extrema, each with **its middle** |
| `vocabulary.py` | the three naming lanes served — derived, **stated**, glossary — and matched against one name |
| `graph.py` · `layout.py` | the 2.5D model at two levels of detail, and where things sit |
| `packages.py` | the package overview — the other graph layout |
| `code.py` | the code browser — a file, its clickable names and what each line *is* |
| `documents.py` | the map's **own** eight documents — lane 2, every row a selection |
| `static/prose.js` | the document renderer — markdown to markup, `data-line` on every block |
| `corpus.py` | the program's **own** documents served — the list, one document, one span. Lane 1; `documents.py` is lane 2 |
| `shape.py` | ALGORITHMS: the five lanes with their denominators (`/api/algorithms`), and one routine's outline (`/api/shape`) |
| `search.py` | searching the **text** — files first, then one file's lines with their margin |
| `static/shell.js` | **the application**: state, routing, every view, the self-check |
| `static/graph.js` | **the engine**: payload to pixels, and nothing about this page |
| `static/forcelayout.js` | the second plate layout — Fruchterman–Reingold on the GPU, 91.7% fewer crossings; shadows pull for the plates they stand in for |
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
document, glossary, **both naming lanes**, settings) with the 2.5D stack and the package overview as two
layouts inside graph mode and **two levels of detail inside the stack**, one inspector
reading `/api/node`, and the graph following the theme. The reading loop: the navigator is the routine list grouped by package, hovering a
node gives a card, picking one lights its hop and fills the inspector, threads lead sideways,
and ⌘Z takes any of it back. **Finding and keeping your place**: an arrow at the plate's rim
aimed at what you picked and clickable to go there, a reticule on it, a *focus* lock so only
the lit set answers a hover or a click, and *you are here* to restore the view you found it
in.

**ALGORITHMS — built 2026-09-06/07, chunks 1 to 4 of 6.** Tom's, and the one place this
tool's founding exclusion is amended: *"algorithms are FLOW, that's our namesake"*. A
`ControlPoint` is **a span and nothing more** — routine, line range, depth, arms, and the
header as written — and a `ControlArm` is the same one level in, so a decision can be asked
*which way out writes*. What a loop **does** is a range join over the tables that already
carry `routine_id` and `line`.

The judgement is one sentence in one module: **a loop or a decision is a subject only where
something moves inside it.** The navigator's **Algorithms** group lists what passes, in five
lanes with their denominators — 250 rates of 1,950 loops, 78 forks and 69 ladders of 2,213
decisions, 396 recoveries of 1,531 handlers, and 0 `match`, which is a named row rather than
an absent lane. The mode toggle's **Shape** draws one routine's whole outline, guards
included, nested as it is written — Nassi and Shneiderman's drawing, which is nested boxes
and no arrows at all.

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
packaging as a binary · any language but Python. **Document mode is complete** — chunks 1, 2,
3, both lanes of 4, and **chunk 5 as of 2026-09-04**. The pane reads the map's eight documents
and the program's own 2,064, and a glossary citation into the corpus **opens**: `senseOpens()`
is a capability test rather than a provenance test, the viewer serves the span out of
`docsource.db`, and its foot hops into the document itself at the block holding the line.
Design rule 13 is met for both tiers.

*The number that was carried for two sessions was wrong.* The plan and this file both said
*"235 documentation-derived definitions render a dead end"*. **235 is `definitions_seen`** —
every definition the scan mined — and only **32 of them bind to a term the code uses as an
identifier** and become citations; the other 203 define words this program never names and
belong to the *mirror*. So chunk 5 fixed **32 citations across 22 terms in 10 documents**:
60 citation buttons on the glossary page before, **92 after** (60 code, 32 docs). *Retaken
2026-09-08: **91** (60 code, 31 docs). The one that went was the constraint gloss on the word*
definition*, refused by the rule at the top of this file — a citation lost by a definition
ceasing to be one, which is the fix working rather than the feature regressing.*

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

**A bug-fix pass and one feature, 2026-09-08. Eight commits, nothing half-written.** 1,229
tests, mypy clean over **121** source files, ruff clean, `check` 0 broken, working tree clean,
no servers running. *Every figure on this line is retaken rather than incremented (rule 24) —
the count this file carried was 1,213 against a real 1,216 before a line of today's work, so
adding to it would have carried the drift forward.*
`output/mensores` holds the pair rebuilt under the new documentation rule:
`2026-09-08T13:39:50Z` (628 files, Society at 08-29) working, `2026-09-07T15:32:31Z` (625,
at 08-26) sealed.

**Four defects were outstanding, and the record had two of them by half.**

| | |
|---|---|
| `navIds` split every row's ids on a space | filed as latent, and it was — but the fix is a row that *says* it carries several, not a separator no name can contain |
| `holds` had no default, so the fold pane's section started closed | **three** keys were in that position, not one: `holds`, `stands` and `calls`, each the answer its pane exists to give |
| a constraint was being read as a definition | `1 ≤ len ≤ 5000 chars`, glossing the word *definition* on the glossary page |
| the undefined list's head was fragments of constant names | 889 of 1,154, with `witness` and `posture` and `claim` buried under `DDL`, `EXTRAS`, `BYTES` |

**The two shell defects came with the guard that found the other two.**
`test_every_inspector_section_declares_its_default` reads the `sec("…")` keys out of the
shell and requires each to be named in the settings — written because a note about one
section had stood for six days while two more joined it silently.

**A constraint is not a definition, and the judgement is on the opening.** A gloss that
*begins* with a bound, a bare type, a regex or a placeholder value states a shape; a
sentence that reaches a number partway through is prose. Measured over all 240 definitions
Society yields: **5 refused**, every one a field constraint, and the three definitions that
quote a bound mid-sentence kept. The rule is in `detectors/docs/prose.yaml` and refused in
`_add_def`, the one place every definition of every form passes.

*The section rule was measured and deliberately left standing.* A heading that merely
mentions the glossary still admits definitions — 29 of these came from
`"AC-19: Performance budget for glossary tools"`. Requiring the word to head its phrase
drops **77 of 240** and takes 60 defined terms to 58. Tom's call, on the numbers: refuse the
constraint alone.

**A word is not a fragment of somebody else's constant name.** Three conditions: never the
whole name of anything, only ever inside a constant's name, and **nothing defines it** —
which is why 889 words leave the worklist and no defined term goes with them. Measured after
the constraint fix: **59 of 324 defined (18%)** against 60 of 1,214 (5%), **265 undefined**
headed by `DDL`, `witness`, `posture`, `claim`, `probe`, and **890 held back**.

**Held back, listed, and every one offered back** — Tom: *"offer a chance to promote them
back to the list manually… a term might appear such as MENSORES_MAX_LEN, where the MAX and
LEN are modifiers but MENSORES has real meaning."* The report lists all 890 with the reason,
the command says how many and where, and the dashboard draws a **Held back** band where each
word says *a word*; persisted per program beside `triage`, with *hold back* on the way out.
The worklist and the band are one split read from its two ends.

**Looked at, and the looking found the fifth commit.** In three CSS columns a button
labelled *"it is a word"* wrapped onto three lines and made every row a different height —
890 of them. No test could have said so. Verified at the **pointer**, which is the half a
scripted click cannot reach: promoting `EXTRAS` moved it from 890 held to 266 undefined and
wrote `{extras: true}` into `dunneflow:mensores:v6`; *hold back* undid both. Eight views
walked, no console error, self-check reporting every control wired.

### The stale-text pass, and it found two sentences arguing with their own pages

Tom scheduled it as the third pass, and the figures were the smaller half. Retaken rather
than carried (rule 24): rule citations **2,775 → 2,832** over 107 files, definitions mined
**235 → 230**, glossary citation buttons **92 → 91** — the lost one being the constraint gloss
on the word *definition*, which is the fix working rather than the feature regressing.
`PERFORMANCE.md`'s 999 ms row is deliberately **not** retaken and says why: its 1,214 terms
are now drawn in three lists rather than two and the population is exactly unchanged.

**The larger half was two claims about a capability, written as fixed prose.** The glossary
page said *"Documents are scanned but not stored… cannot be opened here"* — true until
2026-09-04, false since, and still printed above 31 documentation citations that open. The
stated-rules lane said *"DunneFlow does not yet run one"* — careful when it was written, false
since `conformance.py` began running exactly those on 2026-09-06. Both now read the thing they
describe: the first from the same `SIDECARS` block the buttons are drawn from, the second by
naming the lane that answers instead of claiming the answer. Neither was catchable by a test
that did not know the sentence existed, which is why both are now guarded by name.

*The shape worth keeping:* a sentence stating what the tool **can** do is a claim, and rule 13
applies to it exactly as to a number — it has to be readable off the thing that decides it.
Both of these were prose beside a control that already disagreed with them.

### What the rebuild cost, and it is worth knowing before the next one

The documentation rule moved `doc_rules_fingerprint()`, so the pair had to be rebuilt — two
analyses and a seal, exactly as this file says. **What this file does not say is that
`standards.db` is a document store too.** It went stale with the rest, and `serve` refuses to
boot on it: *"written by a different version of DunneFlow"*, before a single page is served.
The recipe is now three commands and the third is `--standards`, which is written into the
Commands section above.

*Candidate rule, for Tom to mint or refuse:* **a rebuild recipe must name every store the
change invalidates, including the ones nothing else mentions.** Rule 12 says a cached fact is
only as good as the tool that read it; this is the other end of it — the recipe that repairs
the staleness has to be as complete as the fingerprint that detects it.

~~**One thing is left undone and it needs a hand.**~~ *Closed 2026-09-08 — Tom ran it.*
Dropping the superseded sealed snapshot is a manual pass by design (`sourcedb.py` owns no
`DROP`, and `test_source.py:171` asserts it): the two `.db` files went first, and the
**sidecar rows** needed the one command this entry carried. Verified — both sidecars now hold
exactly the two live snapshots, `2026-09-08T13:39:50Z` (628 paths) and `2026-09-07T15:32:31Z`
(625), and `2026-09-07T14:55:40Z` is gone from `paths` and `revisions` in each.

### The plates, ordered by what they link to (2026-09-08)

Tom's request: the force layout improves *verticality* using the shadow nodes — can the same
mechanism minimise vertical **distance** and choose the plate order? **Not that mechanism,
but yes the idea.** Plates as springs on a line, relaxed and ranked, is `forcelayout.js` one
dimension over and gives **-11.3%**; searching the *permutation* directly — weighted minimum
linear arrangement — gives **-82.8%**. Same evidence, different solver, and `plateorder.py`
says so rather than letting the next reader assume one mechanism does both.

| how far a crossing travels | by size | by what they link to |
|---|---|---|
| the plate next door | 190 (3.7%) | **1,724 (33.8%)** |
| **21 or more plates** | **3,738 (73.3%)** | **121 (2.4%)** |

Mean crossing height **30.78 → 5.31** plates over 5,101 crossings; module level -74.1%. **And
the picture says it without the numbers**: the stack stops being a funnel and becomes a
*spindle*, the hubs pulled to the middle where everything can reach them and the leaves sent
to both ends.

**Both variants are built and `by size` is still the default** — Tom's two calls. Interleaved
puts `ext:DATABASE` beside `storage`; grouped holds packages above externals and keeps 31.5%.
The control says **"by what they link to"** and never *"by connection"*, which the
plate-layout button already means about something else (rule 71). `/api/plateorder`, on demand
and held on the base: 1.50 s cold, 10 ms warm, keyed on level, threshold and grouping (rule
81).

**The control it joined did not order plates**, and that had to be fixed first. `sortMode` was
read only in `sortedDisks()`, called only from `renderLegend()`, and the handler never handed
the engine an order — so *by name* and *by kind* renumbered a legend and left every plate
where it was. Invisible because the default very nearly agrees with `defaultOrder`; the two
disagreed even at boot. `applyOrder()` is the missing half, called from the one handler rather
than each branch (rule 78), and fixing it repaired the other two modes as a side effect.

*Three instrument failures on the way, and the lesson is one line:* **when a result looks like
the code is broken, check the instrument first — twice out of three times it was.** A
mis-dispatched `change` where the handler listens on `input`; a cached `<select>` reference
that `renderLegend` had already replaced; and rule 83's pointer factor, **1.0 in this window
against 1.5581 in the last**, so it is a property of the window and must be re-measured every
session.

### The looking pass, which answered two questions and asked three

**A kept fold and a kept flow both open from the shelf**, verified at the pointer in
`pkg:standards`. The fold returns to Diagram mode and its compartment, outlines the box, lits
its routines and files a trail step; the flow fills the inspector with the arrow itself —
`class → file`, *1 along it*, the call site with its argument bound — and lights both ends.
Opened from a *different* compartment, `PIN_ROUTES.flow`'s stated limitation holds exactly as
written: nothing lights, the inspector opens on the arrow, and nothing false is said.

**The hover card's shadow sentence is dead code, and rules 23 and 31 are what killed it.**
*Withdrawn 2026-09-08 on Tom's call — this is the finding as it stood.*
*"A stand-in. This routine lives on X — the copy you are pointing at is a placement device"*
was drawn when `h.shadow` was true, which is `raw2.shadow[i]` at the **picked** index. A shadow
is given radius 0 and alpha 0, so it is never drawn and never picked — **1,989 picks over 562
distinct nodes returned not one**, against 5,855 shadows in the payload — and the only other
path in, the rim arrow, builds every mark as `realIndex(...)` under a comment citing those
same two rules. The reticule over the top is `pickable: false`, so there is no third path.
Design rule 16 from the far side: the branch rendered for nobody *because the rule it describes
was applied correctly everywhere else*. **Withdrawn**, along with the payload field — the
*resolution* stays, since that is what makes rules 23 and 31 true from that handler. A guard
asserts the two facts that closed it **before** the consequence, so a level that ever draws a
shadow fails at the fact rather than at the deletion.

*The instrument could not have shown this either way, and that is worth knowing.* deck.gl's
own `pickObject` answers correctly at every one of those points; what fails is the extension's
synthetic `mousemove`, which never becomes the `pointermove` mjolnir listens for. **The hover
card cannot be verified at the pointer with this instrument at all** — which is what
`e60c050` was really recording. Rule 72.

**And the thing nobody scheduled: 335 of 1,395 navigator rows print their name over their
counts** — 24%, worst case 101 px of overprint where a 62 px box holds 170 px of text.
`_schema_validator` runs straight through its own `1← 1→`. **Rule 53**: the remedy in the
stylesheet is two shrink classes chosen from the **character count alone**, and the budget is
not a property of the name — `.navsub` takes up to 11rem, so the room left swings from ~200 px
to ~68 px on how long the *module path* is. 65 of 84 `xlong` rows still overlap and so do 103
rows carrying no class at all. `selfCheck` only inspects `[data-fit]` elements and a
`.navlabel` has none, so it reports every control wired.

**Tom's call, taken the same day: let the module path yield its width first.** `.navsub` was
`flex: none` at up to 11rem — a fixed cost the name had to fit around — and is now `flex: 0 1
auto` with a 4rem floor, keeping the ellipsis it already had. It is the one field in the row
already built to lose its head, so nothing that was not already designed to be shortened gets
shortened. Measured as a controlled pair, one declaration toggled on one page:
**335 rows / 101 px → 266 / 49 px** at the declared 21rem; 1,037 → 951 at 16rem; and
**almost nothing at 12rem**, where the name alone is wider than the row.

**A fifth better, and still open.** The remainder needs a decision about the *name* — wrap,
truncate, or let the row grow (rule 84) — and each is rejected by one of the two comments over
`.navlabel`. `navWidth` was widened from 14.5 to 21 with the note *"a qualified name is the
thing it has to be able to show"*, and 266 rows still say it cannot.

*And a band nobody had looked at:* `@media (max-width: 1088px)` drops the navigator to
**12rem**, where 1,289 of 1,346 rows overprint and this fix buys four of them. **Check
`innerWidth` against 1088 before trusting any navigator figure** — two of this session's own
numbers were taken either side of it and read as a fourfold regression that was not there
(rule 24).

### And the maps in `output/`, three of which refused and were sent to the wrong command

The scheduled item read *"two maps cannot be opened, both refusing exactly as designed and
both one command away."* **Three refused, and the command was not one away.**

`Store._refuse_if_stale` exists to name *which* of two fixes applies, and its reasoning is
right: a graph written before paths went relative needs `migrate`, which rewrites in place
and keeps a sealed snapshot whose source tree may be long gone. But it tested
`paths_are_relative` — *when* the store was written — where the migration tests
`_require_previous`, which admits **one** fingerprint on the claim that making paths relative
is the only thing that changed. Two facts, one test. Every store older than that single
version was told to migrate, and the migration refused it in turn: rule 49's shape in prose.

`migration_speaks_for` is now in `migrate.py` beside the gate, and both refusals ask it —
the graph on `PREVIOUS_CODE_EXTRACTOR`, the document store on `PREVIOUS_DOC_EXTRACTOR`, the
compared value the only difference (rule 51). It tests the fingerprint and **not** the
recorded root: that root is read per revision from a graph which may not be the store being
refused, and it is reachable only past this gate — so a store admitted here and refused there
is told the truth twice rather than plausibly once. The old guard built its legacy store
*with* the gated fingerprint and still passes; the new one stamps an older fingerprint and
asserts `migrate_program` would in fact have refused it (rule 13).

**`dunneflow` and `beads` were then re-analysed and both open** — 71 files and 849 routines,
14 files and 239. `beads` is a **Go** program with 30 Python files, so it was always a probe
rather than a subject; a probe that lists in the selector and refuses is still worth one
command.

**The fourth is a decision, and it is open.** `output/mensores@2026-08-29T19-43-39Z` is an
old-style directory whose *name* is a revision stamp from before the revision layout, and its
`source_root` is `mensores-overhaul` — the third tree `CLAUDE.md` warns is neither end of the
pair, and which cost a wasted analysis once already. Re-analysing it would re-read exactly
that tree into a directory named after a layout that is gone. **Drop it, or leave it listed
and refusing?** Tom's call; nothing is broken either way, and the refusal now names a command
that would work.

### Before that: the plates, coupled and framed (2026-09-07/08)

Four commits that were built and never recorded here; `CLAUDE.md` and `PERFORMANCE.md`
carry them in full and the commit messages carry the reasoning.

**A second layout, and `layout.py` had named it in its own docstring since the day it was
written.** Fruchterman–Reingold per plate, seeded from the spiral, in a WebGPU compute
shader with a web-worker fallback: **89 ms against 9.7 s**, and 328,531 edge crossings down
to 27,291 on the busiest plate. A toggle on the panel that arranges plates, so design rule 2
holds: both layouts are built and the reader chooses.

**Then Tom asked why the links between plates are not vertical**, and the answer was that a
shadow took part in its plate's forces and nothing pulled back. Coupling every slot that
stands for one entity toward their common middle doubled the upright crossings; **one
coordinate frame for the whole stack** took them to 3,878 of 5,101 and co-located every one
of the 4,050 entities to a spread of exactly zero. It costs the within-plate reduction —
about 90% down to 75–83% — and Tom took that trade on the numbers.

**A plate is no longer centred on the stack axis**, which three things assumed, so the
plate's circle is now reported by the layout and read by the outline, the rim arrow and the
framing alike (rule 51).

### Before that: the review worklist, closed (2026-09-07)

Six findings, and F1 is the one a reader was being lied to by: `_r_about` took the sidecar
inside the lock and queried it after the block closed, so `/api/about` and `/api/revisions`
— fired back to back at boot — shared one SQLite connection. 2 of 60 concurrent reads came
back wrong and the topbar printed *"no sidecar here to ask"* over a map whose sidecar holds
the name. Rule 49 exactly. The guard that watches for it looks at where a store is *used*
rather than where it is read, because an alias carried past the `with` was invisible to the
one that already existed.

The other five: the node-shape orphans withdrawn with the view that drew them, a second
serialiser of a model with one serialiser, the structure bands given the denominator they
were already computing, two measurements that now explain themselves, and four unreferenced
functions. `detectors/__init__.py` was left alone deliberately — deleting one dead predicate
there changes `rules_fingerprint()` and discards every graph on the machine.

### Before that: ALGORITHMS chunk 6, and the pause it ended on

**Paused 2026-09-07 after ALGORITHMS chunk 6. Nothing is half-written.** Five commits,
1,187 tests, mypy clean over 120 source files, ruff clean, `check` 0 broken, working tree
clean, no servers running. `output/mensores` holds exactly the pair at `SCHEMA_VERSION` 9:
`2026-09-07T15:32:31Z` (628 files, Society at 08-29) working, `2026-09-07T14:55:40Z` (625,
at 08-26) sealed.

**ALGORITHMS is complete, and chunk 6 corrected the feature's own headline on the way.**

**The detector, as recorded, reported its own blind spot.** `LOOPED_BOUNDARY` read as
`net_calls` inside a loop fires twice on Society, and both are `wait_until_serving` —
`while True:` poll loops with a deadline, which is the blind spot the record itself names.
Two of two findings would have been false. Measuring it before building it is what
`CLAUDE.md` asks for, and it is what turned this into a different session.

**An iterable is not a body, and 11 of the 261 rates were not rates.** `for row in
conn.execute(q).fetchall():` runs one query, not one per row — but it is written on a line
inside the loop's own span, so `line BETWEEN line_start AND line_end` read it as a rate and
said *once per pass* about it. `ControlPoint` now records the lines a loop evaluates once,
and it is **the iterable's lines minus every line a repeated part also occupies**: the
iterable's span alone reclassifies 45 loops and 34 of them wrongly, because a one-line
comprehension writes its element and its iterable on the same line.

| | Was | Is |
|---|---|---|
| loops + comprehensions reaching a boundary | 219 + 42 = 261 | 211 + 39 = **250** |
| bands over 1,950 loops | 261 · 467 · 1,222 | **250 · 470 · 1,230** |
| significant of 9,625 points | 797 | **786** |
| rates at depth > 1, and inside another loop | 104 and 10 | **98 and 9** |
| the four lanes' rows | 804 *and* 803, in different files | **793** |

**Three surfaces were saying it and one of them was already right.** Checking the four SQL
statements against the resolver over all 64 tables found two disagreements, and the SQL won
both: `shape.enclosing` — chunk 5's *"and vice versa"* half — still counted a loop's own
iterable, so a table's pane said *"reached from inside 1 loop"* about a query the loop is
written over. Also fixed: the ribbon gated its `why` sentence on `significant`, so the 11
corrected loops lost the explanation they most needed.

**`LOOPED_BOUNDARY` is in, at 35 of 74.** The other 39 say how many passes they make and
are named in the detail rather than dropped — 29 over a collection this program declares,
4 over a literal at the loop, 6 on a `while`. INFO/PROBABLE, never SUSPECT, with four
measured blind spots including the one it cannot see past: a local SQLite file is not a
network.

**Every outstanding rule candidate is minted.** Tom: *"Accept and mint all outstanding
rules."* That session left **86 engineering rules numbered to 87** — 21 still does not
exist — and **30 design rules**. *(88 and 89 joined them on 2026-09-08; the live count is
in the table at the top of this file.)* There were six, not the three I first reported: sweeping
the record for *every* unminted candidate rather than the ones I had in hand found three
more, two of them standing since 2026-09-06.

| | |
|---|---|
| **83** | an instrument's two coordinate systems can differ, and the one you can see is not the one you touch — raised 2026-09-06, measured 2026-09-07, and it had cost four sessions |
| **84** | a grid does not overflow, it grows a row |
| **85** | a span cannot tell what a loop is over from what it does — this session's, and the one with reach: anything derived by containment inherits it, which `shape.enclosing` proved while the fix was being verified |
| **86** | a guard can only see that a function was called, never what it returned — the `minDisk=null` defect, which no source check could have caught |
| **87** | a derivation from the picture is only as available as the picture — rule 13's own cost, and the trap you fall into while obeying it |
| **design 30** | a dimmed control still acts — Tom's sentence, and design rule 29's companion |

86 and 87 were checked against rules 37, 42, 44 and 13 before a number was taken, on the
2026-09-05 precedent: a rule that restates an existing one would spend an address on
nothing.

**The stale snapshots are gone, by hand, and the tool still cannot do it.** There were
five, not four — a rebuild adds one each time. `dunneflow revisions --drop` was built and
proved, then reverted: `test_source.py:171` asserts against the source text that
`sourcedb.py` owns no `DROP`, on the grounds that *a store whose whole job is to be the
thing that survives has no business owning one*. Tom's call was to honour the guard and
drop by hand this once, so **the next accumulation needs the same manual pass**. Bodies
were left alone, which is the store's own behaviour rather than a shortcut.

### Before that: chunk 5, the links back

**Paused 2026-09-07 after ALGORITHMS chunk 5. Nothing is half-written.** 1,177 tests, mypy
clean over 120 source files, ruff clean, working tree clean, no servers running. `output/`
is unchanged — this session wrote no maps.

**ALGORITHMS is complete but for chunk 6.** Chunk 5 is the *"and vice versa"* half Tom
named when he asked for the feature, and it is in: a table and a boundary each say what
loops over them and open the list, a routine's pane carries its Shape, two threads lead to
code that runs the same shape, a loop can be **kept**, and two curiosities measure it.

**A table is a subject now, and that was a defect rather than a feature.** Selecting one
fetched the routines that touch it and *threw the table away*, so the crumb named a table
and the inspector answered about whichever routine sorted first. `web/table.py` on
`plate.py`'s model, and `state.dbtable` — never `state.table`, because `state.mode ===
"table"` is the centre pane's routine table.

**Two things Tom found by looking that no test would have.** *Shape locked on to the last
routine viewed* — the bag was keyed from the day it was written and no renderer read the
key, and `ensureShape` was invited from one branch, so the new inspector section was wired
to nothing (design rule 16). Both fixed the way the 2026-09-03 session settled: the
reconcile runs from `render()`, every early return empties the bag, and both renderers read
the key.

**What is left: chunk 6**, the detector. `LOOPED_BOUNDARY` in `anomalies.py` — a remote
call inside a loop, INFO or SUSPECT and never BROKEN, with the two blind spots that make it
honest: *the iterable may hold one item, and nothing static can count it*, and *a retry loop
is this shape on purpose*.

**Still waiting on Tom's eye**, and now more than before: the **instrument cannot show the
inspector at all**. The capture is a fixed 784 px of a 1,200 px viewport, `resize_window`
does not move the page viewport, and the pane sits at x=848 whatever is collapsed. Every
layout claim about the table pane this session was **measured in the DOM, not seen**. Also
open: the worklist's and ribbon's row layouts, and whether *"a grid does not overflow, it
grows a row"* and *"an instrument's two coordinate systems can differ"* are rules or notes.

### Before that: chunks 2 to 4, and four sealed snapshots the schema bump left behind

**Paused 2026-09-07 after four commits. Nothing is half-written.** 1,145 tests, mypy clean
over 117 source files, ruff clean, working tree clean, `check` 0 broken on
`output/mensores`, no servers running. ALGORITHMS chunks 2 to 4 are built; 5 and 6 are not
started.

**`output/mensores` changed, and in two ways worth knowing.** The pair is rebuilt and
resealed at `SCHEMA_VERSION` 8 — `2026-09-06T21:37:35Z` is Society at 08-26 (625 files),
the working `2026-09-07T00:01:16Z` is 08-29 (628). And the **four older sealed snapshots
are now stale**: two at schema 6, one at 6, one at 7, all of them 08-26 under the same
label. They open as a refusal with the store's own sentence, which is correct behaviour
(rule 20 — a read may refuse, it may never repair) and is also clutter accumulated by four
rebuild dances. Whether to drop them is Tom's call: a sealed snapshot exists to outlive its
source tree, so nothing here deletes one on its own.

| Commit | What |
|---|---|
| `9bf688d` | **chunk 4** — the ribbon, and a place is not two things because it was written down twice |
| `22667dc` | **chunk 3** — the worklist, and a row that names its own step |
| `4bdc0e8` | **chunk 2** — the join, the judgement, and the arm that carries them |

**The feature, in one sentence Tom can check:** the navigator's **Algorithms** group lists
the loops and decisions this program is worth reading — 261 rates, 78 forks, 69 ladders,
396 recoveries, 0 `match` — and the mode toggle's **Shape** draws any routine's whole
outline, guards included, nested as it is written.

**The judgement lives in one place** (`resolve/shape.py`, rule 51): *a loop or a decision
is a subject only where something moves inside it.* Nothing is dropped for failing it —
three bands, a `why` on every point, and the quiet numbers stated on the page, because it
is the 1,222 loops that move nothing that make the 261 credible.

**The arms were the missing fact.** A point says a decision has four ways out; only an arm
says which one writes. `control_arms`, 4,125 of them over 9,625 points, recorded only where
a point has more than one way through it — and they are the *bodies*, so a boundary reached
from inside a test belongs to the decision and to neither arm.

**Three figures were corrected, all in the same direction — the plan reasoned, the store
measured.**

| Was | Is | Why |
|---|---|---|
| 80 forks | **78** | the plan's script counted each `elif` tail as a ladder of its own; then places, not rows |
| 10 nested, from `depth` | **10, from containment** | `depth` counts every enclosing `if` — the two answers are 104 and 10 |
| 742 handlers touching | **750** | the plan measured two spans; the store measures the `try` |

**A place is one act; a row is one description of it.** An `INSERT` is a `DATABASE` row and
a `SQL` row on one line — 569 of Mensores' 991 SQL operations are such a pair — so counting
rows said *two things move here* about one write, in the sentence that gives 33 of the 261
rates their number. `places()` is the one place a count is taken now.

**Two defects found by looking, not by testing.** One pointer click on a worklist row filed
**two trail steps** — the dispatcher's step landing on the subject being left, which on a
page of its own is nothing, so nothing could deduplicate it (rule 33's fourth variant). And
the ribbon's line numbers stepped right with the indentation, under a comment of mine
saying that is exactly what they must not do.

**What is next: chunks 5 and 6.** Chunk 5 is the links back — a table's pane saying
*"written from inside 3 loops"*, threads for *other loops over this table*, a `PIN_ROUTES`
kind so a loop can be kept, two curiosities. That is the *"and vice versa"* half of what
Tom asked for. Chunk 6 is `LOOPED_BOUNDARY` in `anomalies.py`, with the blind spot that
makes it honest.

**Waiting on Tom's eye:** the worklist's row layout and the ribbon's, both of which are
design calls; and whether *"a grid does not overflow, it grows a row"* and *"an
instrument's two coordinate systems can differ"* are rules or notes. The second is now
measured rather than suspected — clicks are in the screenshot's frame, `zoom` regions are
in the page's, and the pair differs by the device pixel ratio.

### Before that: the trail names its own hops, and a grid that grew a row (2026-09-07)

**Paused 2026-09-07 after two commits. Nothing is half-written.** 1,103 tests, mypy clean over
113 source files, ruff clean, working tree clean, `check` 0 broken on `output/mensores`, no
servers running. `output/` is unchanged — this session wrote no maps.

| Commit | What |
|---|---|
| `3df8730` | **a trail step takes the name of the move that files it** — seven callers, and the open entry describing it was wrong |
| `a7ea9ba` | **a search hit's keep button gets a cell** — the looking debt from 2026-09-06, paid, and the columns were wrong |

**The open entry was wrong, and measuring is what said so.** It read *"clicking a change row
files two trail steps"*. No path files two, and **the change row is not among the affected
paths at all** — it sets its subject synchronously, so the dispatcher's step lands correctly;
verified by clicking one. What is real is quieter: opening the kept cohort `AC-4`, which opens
112 routines, filed a step called **`resolve_cli_invocation`** — one arbitrary member — and
wrote *"a plan or decision id"* onto the `kept things` step the reader was **leaving**. A
sentence about one subject printed under another, in the surface built so a detour does not
cost you your thread.

**A caller about to move now names the step the move will file, and never files one of its
own.** `selectFromNav(want, name)` and `followThread(subject, name)` carry `{label, note}` to
the one recorder, so there is one step, named when it is made. Both orders lost before: filed
*before* the move a step carries the subject being left and donates only its note; filed
*after* it lands on the step the move already made and is dropped whole. The note-adoption
branch is **deleted** rather than kept — it put the note on the right step and about the wrong
thing. `NAV_NAMES_ITSELF` declares the one navigator route that fetches before it selects
(rule 30), because the dispatcher names a step *after* calling a route.

*A seventh caller was found by sweep rather than by the entry:* the glossary term row mints
the same cohort a thread does, and `mensores` opens 628 modules — one of them standing in for
the word is rule 74 in the trail.

**Seen on all six affected paths and the three that were already right.** `AC-4` reads `AC-4`
from a panel and from the shelf, a glossary term reads `quaestor — 45 modules, 1 constant`, a
table row is named for the table, and a routine, package and change row each still file
exactly one step. Back and Forward still walk it.

**The looking debt is paid and the columns were wrong.** `.srch-hit` declared five columns for
five children — and `.srch-in` spans `2 / -1`, so it fills the rest of its row and anything
after it starts a new one. The keep button added in the previous session flowed onto a **third**
row into the 3.2 rem line-number column: **51 × 54, "Keep this" wrapped onto two lines**, under
a 17 px line of code, on every one of 126 hits — 101–108 px of pane each. Now 78 × 22 on the
code's own line, rows 45–53 px. Nothing reported it and nothing could, so the new guard asserts
the *rule* — after a child that spans to the last column, every later child is placed by hand —
and matches the button by its `pinBtn(` call, because a child a source scan cannot see is the
one that gets forgotten when columns are counted. **The placement is Tom's to change.**

*Minted 2026-09-07 on Tom's call:* **rule 84 — a grid does not overflow, it grows a row.**

### Before that: "keep this" on everything (2026-09-06)

| Commit | What |
|---|---|
| `c53d0a0` | **"keep this" on everything** — a thread, a curiosity, a search hit and a convention, over two id spaces kept apart |
| `85e000a` | **design rule 29 minted** — a hidden control is not a dimmed one |

A thread, a curiosity, a search hit and a naming convention can each be kept now; before this
every one of `pinBtn`'s five call sites was an inspector pane, so the four things a reader
actually wanders into could be *followed* and not *kept*. **Tom chose the shape first: two
routes, not one reconciled table.**

**What a cohort is** — the question that decided the shape, answered from `threads.py` rather
than by reasoning: *a set of routines that share a value, named by that value, resolved on
demand and never shipped.* Its `key` is always a value string — a plan id, a table name, a
glob, a glossary word — never an id this map minted. That is exactly why the two spaces stay
apart: a `fold` id belongs to the drawing and is valid only at the altitude it was drawn at, a
cohort key is something the *program* says and survives re-analysis. And `kind` already means
different things in the two, so one table would be one word carrying two meanings — rule 47's
companion, paid for once by `data-nav`.

**A thread whose subject is already a node is kept as a node**, translated into the map space,
so keeping a routine from a curiosity and from its own pane is one pin rather than two rows
naming one thing. Verified on screen.

**A kept cohort never prints a remembered count.** `cohort_subject` gained a `noun` that counts
nothing; the number is asked for when the shelf paints. On screen: *counting…*, then *"a plan
or decision id · opens 112 routines"* — the same 112 the corpus measurement gives for `AC-4`.
The count is deliberately **not** reused by the open, because that would be the shelf opening a
cohort past `THREAD_SUBJECTS`.

**A line is the first kept subject that moves**, so it records the revision it was kept at and
says the line may have moved — only when the versions differ.

*Found while building it:* the conventions page had been minting a cohort subject in JavaScript
since it was written, invisible to the guard that refuses exactly that one module over. Harmless
until `noun` existed; the subject comes from `vocabulary.py` now.

*Two the tests could not have caught.* **`visibility: hidden` is not dimming, it is disabling** —
a real pointer click landed inside the keep button's own rectangle and hit the row, because a
hidden element is not hit-tested and is out of the tab order, so `:focus-within` can never
rescue it. And a label centred in the middle of its own row, which then exposed
`.pinrow .linkbtn { margin-left: auto }` matching the label as well as *Drop* (rule 71).

*Not seen:* the search hit row's **column alignment** — its structure and subject were read from
the DOM, the columns were not looked at, and the renderer wedged twice before the retry limit.
Said rather than claimed. *Looked at 2026-09-07, and they were wrong: the keep button was on a
third row in the line-number column. See the top of this file.*

**Before that, paused 2026-09-06 between features.** `output/` holds what it held at the start
plus `mensores/standards.db`, which is that session's own feature and belongs there.

**Six commits, and the thread running through five of them is one idea Tom stated once:**
*"We're a rabbit-chasing application — it should work. If a panel lists 7 things, clicking
on that panel should lead to a screen that lists all 7 things in detail, no matter what
they are."*

| Commit | What |
|---|---|
| `9000550` | **the looking debt is paid** — five surfaces seen, and the instrument had two coordinate systems differing by exactly the dpr |
| `22e82ff` | **standards 4 then 3** — import an outside standard, and measure the program against it |
| `deb97c8` | **the cover's bars become a Setting**, and the name gets the column |
| `392d1e1` | **two more cover Settings** — tags to their own line, and the evidence line wraps |
| `e54df9b` | **a figure that counts things opens those things** — the comparison's nine tiles |
| `3cfce1b` | **the worklist's jump buttons act** — a finding opens what it found |

**Two items came off the open list, and both were recorded as harder than they were.**
Standards step 3 was *"compare against the graph"*, which measurement showed would make the
tool confidently wrong. The worklist's jump buttons were *"blocked on precision, not
effort"*, when every detector already had the ids in hand and was throwing them away. In
both cases the record was written from reasoning and the correction came from measuring.

**What is open** after that session: *"keep this" on everything* — **closed 2026-09-06, see the
top of this file** — the three filed defects (a change row files two trail steps, `holds`
missing from `insp`'s defaults, `navIds` splitting on a space), `m.<module>` as a language
feature, and per-plate sphere scaling with stack orientation.

*The two-trail-steps defect is now measured rather than filed from one surface.* Opening a kept
cohort files the subject **and** one arbitrary member of it; the untouched `[data-thread]` path
does the same, so it belongs to the selection path and not to any one lane, exactly as recorded.

**Two mistakes worth carrying forward.**

*`git checkout <file>` is not an undo.* Proving a guard non-vacuous, a cleanup line read
`git checkout src/dunneflow/anomalies.py || cp /tmp/a.bak …` — a backup that never existed,
after a command that cannot fail. It reverted ~200 lines of uncommitted work. The lesson is
the fallback rather than the checkout: `||` after a command that always succeeds is a
comment, not a safety net, and the VCS is no undo for work it has never seen. **Take the
backup first and restore from that.**

*A stale readout that looked like a false claim was self-inflicted.* The topbar read *"no
sidecar here to ask"* while `/api/about` answered fine — from re-analysing the map underneath
a running server and then driving `state` by hand. On a clean boot it is correct. Verified
before reporting, and it dissolved.

**Design rule 29 was minted on Tom's call: *a hidden control is not a dimmed one.*** The counts
are now **81 engineering rules numbered to 82** — 21 still does not exist — and **29 design
rules**. `visibility: hidden` and `display: none` take an element out of hit-testing **and** the
tab order, so a rule revealing it on `:hover` or `:focus-within` can never be reached by the
route that would rescue it — every way in is closed by the one declaration meant to make the
control quiet, and nothing reports it. In `DESIGN-RULES.md` in full, indexed in `CLAUDE.md`.

**One candidate is still open** for Tom to mint or refuse: *an instrument's two coordinate
systems can differ, and the one you can see is not the one you touch.*

### Before the pause: a plate is a subject (2026-09-05)

Tom's, and pre-existing. `pkg` routed to `selectFromNav({ disks })`, which sets no subject —
so the crumb read *"nothing selected"*, the table showed all 4,786 rows, and the inspector
offered *"Pick … a package from the navigator"*, naming the gesture that had just failed.

**What it decided is what selecting a package is.** Not a nominated member — that is what
`detail.fold` exists to undo, and a plate holding 926 would make it twenty times over. So
`state.plate` is a fourth subject, `web/plate.py` answers, and the pane is routed on the kind
above the first line that reads a routine's shape. Five plate kinds; `answers` is **declared**
by the server, because a package with no callers and a plate outside the program both arrive
as `[]` and mean opposite things — for one draft the external plates got the package queries
and `ext:STDIO` reported *0 in, 0 out, 0 touches*, which on screen says nothing in Mensores
writes to standard output.

**Three things measurement changed and no source check could have seen.** A ways-in query of
my own (`WHERE parent_id IS NULL`) dropped all 32 MCP tools and two of the four executables
`CLAUDE.md` names as ground truth — `waysin.listing()` is the one answer (rule 51). Members
read off the drawn payload marked *0 of 4,786 rows* in Table mode, which never mounts the
graph. And `&minDisk=${minDiskNow()}` spelled an unset threshold `null`, got a 400, and sent
every click to *"Not in this map"*.

2.4–9.7 ms for a package plate, a flat ~15 ms beyond the boundary line, in `PERFORMANCE.md`.
**Never seen** — measured entirely through the DOM.

### Before that: `<module>` is answered as what it is (2026-09-05)

Two false statements, not one. The three-way *"way in, dead code, or a call DunneFlow cannot
see"* hint fires on all 487 module nodes, every one of which has **0 callers and 0
entrypoints** — nothing can call module scope, because module scope is what runs *instead* of
being called, and the true sentence was already on the page underneath it. And `def
<module>():` — a copyable declaration of a routine nobody wrote, which `hoverSigHtml` already
refuses one surface over and which was not in the filed entry.

Not a separate pane: Out, Touches and Governance are all correct for module scope.

### Before that: a read never brings a database into being (2026-09-05)

Caused and then found. A one-line probe opened `output/mensores/graph.db` read-only — a path
that does not exist there — and `sqlite3.connect` **created** it. The failed query was not the
harm; the 0-byte file was, because `revisions.py` reads a bare `graph.db` as that program's one
legacy revision. Rule 20 from the side nobody expects: the read repaired nothing, it wrote.

Rule 51 with the count as the argument — **seven** read paths each carried their own
`if not path.exists()`, every one correct, and the caller that forgot was none of them.

### Before that: Document mode is about the selection (2026-09-05)

**Tom's screenshot was the bug report**, and it was two defects. `state.docPath` held whatever
was last opened and nothing connected it to the selection, while the mode toggle claims *"five
ways of reading one selection"*. And `.docnav` is `position: sticky` inside a `flex-wrap` box:
right while it is a side column, and at a 24px root its bases (12 + 26 + 1.2 rem ≈ 941px)
exceed the centre pane, so it wraps to a full-width row and pins itself over the prose.

**The obvious relation does not exist and is written down so nobody mines it again**:
`doc_refs`' 37,150 PATH entries are *document* paths, and a source file matches **zero**; its
CODE entries are CLI flags. What exists is the governance join — and **naming an id is not
being related**: a routine carries a median of 2 ids named by a median of **281** documents,
14% of the corpus. The **intersection** is selective, median **4**. So the pane ranks rather
than filters, states both numbers, and answers in 6.8 ms per selection rather than the 4.7 s
`traceability.measure()` takes for the whole program.

On Tom's call an open document **stays open** and says which it is — related, it names the
shared ids; unrelated, it says so and how you got there. 59% of routines carry no id at all
and get a sentence, not an empty list.

The contents fix is a **container query**: `@media` answers about the viewport and its `rem` is
not the page's (rule 28), `@container` answers about the pane and its `rem` is. Measured
sticky at 43.8rem, static and stacked at 35.0rem.

*And one I caused:* the doc chrome repaints only when `docDomKey()` changes, so the related
block froze on "Looking for…" seven milliseconds before the answer landed. The key carries it
now.

### Before that: ways in are nodes on the Diagram (2026-09-05)

Tom's option (iii), taken up an hour after being deferred. A way in is a **box on every
compartment it enters**, with bold arrows into what it starts, and the ordinary arrows carry on
inward from there — `pkg:signator` reads as `mensores-signator` → `__main__.py`,
`WitnessHandler.do_POST` → `WitnessHandler`, `serve` → `_server.py`, and down through
`_keygen`, `_custody`, `_signing`.

**Drawn by default, unlike a port, and the difference is measured.** Rule 19 turned ports off
because they are median 13 and max 41 per compartment against a median of 10 boxes. Ways in
are **max 3 and absent from 46 of 53**. Same rule, opposite answer, because it is a different
population; both numbers are in the docstring. Told apart by a **note silhouette**, never
colour (design rule 4).

**The arrow bound is one compartment's number.** `mensores` enters **39 of `pkg:cli`'s boxes**;
unbounded that compartment goes from 734×650pt at 1.1:1 to **3647×428pt at 8.5:1**, and
bounded at eight it is 1017×674 at 1.5:1. **No other compartment reaches the bound** — the next
largest fan-out in 53 is three. Bounded *per way in*, or one fan-out would push another's single
arrow out of the picture; the panel says *"entered from 1 way in, reaching 43 boxes — 8 arrows
drawn"* and opening the box lists all 106 (rule 8, design rule 1).

`entries` and `entered` are their **own list and lane**, so every count the panel already
printed is unchanged and a compartment with no way in emits a byte-identical drawing (rule 32).
Clicking a way-in box opens the way-in pane, so (ii) and (iii) are one path. An **entry arrow
refuses to open as a flow** and says why: the caller is the operating system, so there is no
call site to list.

### Before that: ways in say what they are, and an application opens as one (2026-09-05)

**Tom's question was the bug report.** *"They don't make sense in the way that code does… what
is `mensores`, `mensores-mcp`, `run`?"* A way in is **how the outside world starts this
program**; Mensores' fourteen are four *declared* executables from `pyproject.toml`, one HTTP
route, and nine *guesses* from a conventional name or a `__main__` guard — and the cover drew
all fourteen as a name, a kind tag and a bar. `ways_in()` computed the evidence and `cover.py`
threw it away before the wire. Five rows are called `main`.

**The row now says which**, with the evidence verbatim and unparsed (rule 30) and where it
lives — or, for a command tree, what it *spans*, because `mensores.cli:app` is a Typer object
with no definition site and inventing one would mean picking one of 44 files (rule 1). Neither
badge is coloured: green already means *here is a route* on that page (design rule 4).

**And clicking an application opens the application.** `web/waysin.py` + `/api/wayin` answer
with the tree — where execution begins, the 22 sub-applications with what each holds, and the
commands hung directly on it, every row carrying the node id that makes it an ordinary
selection. A sub-application opens too, with **every count recomputed for it** (rule 24), and
its id verified to be mounted under this way in rather than trusted (rule 49). Driven end to
end with a real pointer: cover → pane → `quaestor` → `accept_cmd` → `mensores/cli/audit.py`.

*Three found while building it, all in the record:* the application listed **itself** as one of
its own commands (rule 74); keeping it out then made the program's own front door read as a
limitation of the tool (rule 32); and a group counted by direct children read `telemetry 0` for
a group holding commands one mount down (rule 13).

***And one that was mine.*** `selectionSnapshot` and `sameSelection` were two hand-kept lists of
the same fields, and `wayIn` went into one — so a step carrying its subject perfectly was
deduplicated away, which is rule 33's symptom with nothing missing. `SUBJECT_KEYS` is the one
list now, and the guard asserting the two agree **immediately caught a second field**.

*Two things not proven, and said rather than claimed:* the **pointer path** for the
sub-application button — three real clicks reported success and delivered no event, the harness
having stopped mid-session (rule 48; the cover row and command row were pointer-proven before
it stopped) — and a **one-off boot failure** from a stale `localStorage` blob that cleared on
reset and did not reproduce. Both are in `HANDOFF.md`.

*A mistake worth knowing:* `git checkout <file>` to undo a one-line probe reverted the whole
day's work in that file. Recovered from a scratchpad copy plus nine re-applied edits. Revert
the probe, not the file.

### Before that: a root elected by no vote, and a package row that selects nothing (2026-09-05)

**Tom opened the throwaway `nodocs` map and found it broken. He was right, and it was two
things.** Mine: the map was `analyze src/dunneflow`, and the prescribed shape is the *parent*
(`analyze .../src`, whose child is the package). The tool's: it then failed twice.

**1. `root_package` could not fail.** It elected the modal first dotted segment. Analyse a
directory that already *is* a package and no segment is the root, so the biggest subpackage
wins — `web`, 20 of 63 files — and `package_expr` sent everything else down its `ELSE` branch
as `<external>`. **750 of 752 routines drawn as somebody else's code**, on the largest plate
in the picture. The tell is not marginal: a real root covers **628/628** and **63/63**, a wrong
one **20/63** and **19/61**, so no threshold is invented — a root accounts for every file or
there is none, and `""` is a real answer meaning *the tree itself is the root*.

*And the right test was already in the file.* `COVER_ROOT` asks the same question by grouping,
counted **16 heads** and answered *no root* — same process, same store — while `root_package`
elected `web`. `<external>` is `<outside the root>` now: it fired **0 of 4,786** times on
Mensores and only ever when the root was wrong (rules 26 and 30).

**2. `COVER_PACKAGES` was a second decomposition.** Second dotted segment, no root; its own
comment claimed it matched the disks and `PACKAGE_SIZES` called the difference a hazard a
hundred lines below — both standing for two months. The navigator selects **by plate id**, so
a row with no plate selects nothing and the pane says *"Nothing to show."* **1 dead row of 46
on Mensores**, 36 of 48 on the broken map. One expression, three callers (rule 51).

Both are serve-time, so every map is fixed with no re-analysis; `output/dunneflow` had the same
wrong root. 1,007 tests, and the three that matter fail without the fix — verified by stashing
the *source* and keeping the tests, since stashing both proves nothing.

### Before that: the stated naming lane, on screen at last (2026-09-05)

**`doc_rules` has held naming rules somebody wrote since the document scanner existed, and the
dashboard had never shown one of them.** `11-naming.md` quoted them from the day the column was
added; `/api/naming` served the derived lane and nothing else. This is standards **step 2**, and
it is exposure rather than comparison.

Measured before it was built, which is what shaped it: `output/mensores` states **12** rules
(7 FORM, 5 VOCABULARY) out of 2,064 documents; `output/dunneflow` states **0** out of 9. Both
cases were already on disk, so the good one and the blank one were each looked at.

**Two pages, and Tom chose which.** The obvious move was one page retitled *"Naming standard, as
found"* to match the Markdown report. Tom took the other option — keep *Derived naming standard*
and add a second row — because *derived* is load-bearing, and a rule somebody wrote on that page
would have made the word false of half its contents while leaving it standing. Stated sits above
derived: what was written comes before what was done. Each page names the other and says in the
same sentence that **nothing compares them**.

**One reading, three readers.** `resolve/stated.py`, beside `resolve/naming.py`'s Form lane,
takes the query, `StatedRule` and the `checkable` sentence out of `render/naming.py`. The
report's output is byte-identical across the move. **`scope` and `pattern` are drawn for the
first time** — in the schema since the scanner was written and read by nothing — which is what
makes *"Step names: snake_case"* legible as the one rule here that names a spelling and no
identifier class, kept rather than dropped (design rule 1).

**Three absences, three answers**, all driven on real maps: `--no-docs`, nine documents that
state nothing, and a scan that found none. `read` travels beside the counts because no count can
stand in for it. *(`output/beads` was a fourth candidate and refused to open — unmigrated
absolute paths, rule 60's refusal naming `dunneflow migrate`, not repaired on the way past.)*

**The hop is a capability test, not a hope.** `/api/stated` carries a `corpus` block for the
reason `/api/glossary` carries `sidecars`, and where it says no the reason is printed rather than
the button dropped. Driven with a real pointer: `NAMING.md:17` opened the document scrolled to
the *Latin-only* block with `docflash` on it, rendered as prose.

**And the thing only looking caught.** The first drawing gave **CHECKABLE the accent green** the
glossary spends on a DECLARED tier — on screen it read as pass/fail, which is not the claim: a
Latin-only rule is not a worse rule, it is one no query can decide. Green already means *here is
a route* on that page. Both badges are neutral now (design rule 4).

*Worth keeping:* the **old-style** `output/dunneflow/docs.db` yields **136** stated rules and all
136 come out of DunneFlow's own generated `11-naming.md` files — rule 57's hazard, closed by
`b92dec0`, preserved in a stale artefact. The current revision yields 0. It is why the page
renders an unbounded list grouped by document rather than assuming twelve.

*The harness trap, re-measured because it is not stable between tabs:* this tab took **clicks at
viewport × 0.395** and **captured at viewport × 0.79**, cropped to the top-left quadrant.
Calibrate with labelled markers at known viewport coordinates *and* a click listener reading back
`clientX/clientY` — that is the only method that settles both scales at once. Viewport 1,920×991
at a **16px root**, so rule 38's debt is reduced again and **not paid**. Two smaller ones: a
collapsed pane's own fold button has zero size, so the way back is the **rail** and a scripted
click on the fold is a silent no-op; and `state.view` is not persisted for any page, so a reload
landing on the cover is design rule 17 rather than a regression.

### Before that: a stopped analysis, and the map it leaves behind (2026-09-04)

Tom asked what happens when a background analysis hangs, crashes, or gets in the way of the
next one — *"the user disagrees, or asks to override."* Four things were checked against the
running code. Three were defects. **The fourth was worse than the question.**

**A killed `analyze` left a map that opens and lies.** Measured by stopping one twelve
seconds into the Society tree: 628 files, 4,786 routines, 4,070 boundary touches — and
`resolved_calls = 0`, a program that calls nothing — carrying a timestamp, a tool version and
chunk 2's determinism guarantee, listed by `program_dirs` and opened by the switch without a
word. **Reachable with no stop button anywhere**: Ctrl-C, a sleeping laptop, an OOM kill. So
the marker was the prerequisite, not an extra: cancelling without it would have turned a rare
accident into a button.

`analyze` now commits `complete = ""` on the way in, the **step** as it goes, and `"yes"` on
the way out. Three states and not two — missing means *predates the key* and is fine, which
matters because every map made before today lacks it. Verified against a real `kill -9`:
`complete = ''`, `step = 'reading the documents'`. **Re-analysing recovers it in 34 s**,
because the extraction is content-hashed, so *Analyse it again* is a fix rather than advice.

**Three defects that existed and are fixed:**

1. **Nothing could stop a run.** The `Popen` was a local inside `analysis.run` — no route, no
   button, and a hung child held the slot until somebody killed the server.
2. **The slot trusted a label.** `state == "working"` is true for ever if the watcher dies
   without noting. It asks `poll()` now, and clears the stale lock (rule 30). That is the
   *"or locked"* half of the question.
3. **A reload orphaned the run.** Nothing asked `/api/analysis` at boot, so the panel vanished
   while the run continued and the next attempt was refused by a sentence naming a job with
   nothing on screen to point at. The refusal was also a dead end — it now carries the running
   job and a **Stop it**.

**And the jam came back through the fix for it, which is the finding worth keeping.**
`analyze` runs a `ProcessPoolExecutor` and its workers inherit the pipes. `terminate()` on the
parent killed the parent and left **eleven workers** alive holding stdout open, so `run`'s
read loop never returned and the report said `working` over a child that had gone —
`state: working` beside `running: false`, the exact label-outlives-fact shape this chunk
exists to remove. The child gets its own session now and the signal goes to the **group**.
Found by looking at `ps`, not by a test.

**The silence is stated and acted on by nothing.** `moved` bumps only when something actually
changed — a timestamp refreshed by being polled would say a run was moving because it was
being watched — and the panel says *"Nothing new for 48 s. Some steps are quiet for a while…
so this may be working. It may also be stuck."* Resolution is legitimately silent for tens of
seconds, so the judgement is the reader's, not the server's.

***Minted as rule 80** on Tom's call:* **a job that can be interrupted must leave something
that cannot be mistaken for a finished one.** In `RULES.md` in full, indexed in `CLAUDE.md`,
cited six times across `store.py`, `cli.py` and the tests. *(The stated rule count was already
stale by one when 79 was minted; it now reads 79 rules **numbered to 80**, since 21 does not
exist and the numbers are addresses.)*

***`query` warns rather than refusing** — closed by Tom, not open:* *"I like the fact that
query returns but warns, that seems correct behavior for that feature."* It is the one reader
that opens an unfinished map, because its whole contract is that you get the rows that are
there; the other five refuse.

**Driven in a browser**, all four cases: the panel came back after a mid-run reload with its
elapsed time correctly reconstructed; the refusal named the running job and its Stop worked;
the selector reads *"coldrun2 — never finished being read"*; and the switch to it is refused
with the store's own sentence over an **Analyse it again** that opens the dialog name-filled —
after clearing the switch scrim, which would otherwise have sat at z-96 over a dialog at 92.

### Before that: "About this map" — what read it, and whether anything was guessed (2026-09-04)

**Tom asked for the model an analysis used. There is none, and checking that first turned the
feature from a placeholder into a guarantee.** Nothing on the analysis path calls a model or
touches a network: stdlib `ast` and `tokenize`, a hand-written document scanner, and
`Provenance`'s two paid tiers declared and unbuilt. On being told: *"Perfect, keep it that way
as much as possible! Inference should always be voluntary and secondary."*

So the two rows read *none — every fact here was read, not guessed* and *none — this analysis
is deterministic and local*, and a test asserts nothing under `extractors/`, `resolve/` or
`canonical/` imports an HTTP client or an LLM SDK — a claim on screen that no query can return
is prose (rule 13).

**Missing and blank are different answers**, and that distinction is the whole thing. Every
field arrives as `{recorded, value, none}`; `output/dunneflow`, analysed before these keys
existed, renders *"not recorded — written before this map could say"* in italic, visibly
apart from the guarantee. Both cases were looked at on real maps.

**`none` is the server's decision.** `inference` stores the word `none` so `dunneflow query`
over `meta` reads as prose; `model` stores blank, because there is no word for the model that
did not run. The page owned one spelling for an hour and rendered *"Inferred facts: none"* —
a bare word where the sentence was the point — which is rule 51 caught on screen.

**The row that was planned and struck.** *"Would a newer build read this differently?"* can
only ever answer no for the map on screen: `Store` opened read-only calls `_refuse_if_stale`,
so a mismatched graph never becomes the base. What is stated is the guarantee that produces.
The honest *read it again?* signal is the date and the **tree leaf** — a leaf, never a path
(rule 60).

**The topbar's `source directory` readout is the doorway**, and four guards flipped with it
rather than being deleted. It was a `<div>` with no pointer and no hover *because nothing
bound a tree*; its own markup set the condition — *"it becomes interactive when something
needs to open a file from disk"* — and this met it. So: it is a `<button>`, it carries the
affordances it used to have to refuse, and **the clip came back with the binding**, which is
what its own guard's failure message asked for in as many words. Each guard now protects the
new decision, in the same rule read the other way round.

*Candidate design rule, for Tom to mint or refuse:* **inference is voluntary and secondary, and
a map states whether any was used.** One step over from design rule 14, which scopes *egress*;
this scopes whether a fact was *guessed*.

*A second harness trap, and it cost another false start:* **click coordinates and screenshot
coordinates are not the same scale, and neither is stable between tabs.** One tab took clicks
at viewport×0.62 and captured at viewport×0.62; the next took clicks at viewport×0.62 and
captured at viewport×1.25 — a *crop* of a magnified render, not a downscale. Calibrate with
markers at known viewport coordinates before trusting either. Clicks below about viewport
y=48 never reached the page at all, so **the topbar cannot be clicked in this harness**; the
button was proven from the real keyboard instead, which is the better proof for a control
that has to be reachable without a pointer.

### Before that: "+ Analyze a directory…" works (2026-09-04)

**The dashboard can now make a program, not only choose one.** The `<select>`'s last option
opens a dialog, the server reads a source tree in a subprocess, a panel reports each step,
and the new program appears in the list with an *Open it* that is the program switch already
built. It is the second half of the selector entry, and it closes it.

**Four decisions, and the first is the one everything else follows from.** It runs
`dunneflow analyze` as a **subprocess**: every store this process holds is `writable=False`
by rule 20, and an in-process analysis would make the serving process a writer to the tree
it serves. It also keeps `walk.py`'s `ProcessPoolExecutor` out of a request thread, and makes
what runs *exactly* the tested command (rule 51).

**It is not the switch overlay, and that is the shape of the whole feature.** A base switch
blocks the page because every count underneath belongs to the version being replaced. This
reads some *other* tree into some *other* directory, so nothing on screen becomes untrue and
nothing is taken away — a dismissible panel, and a **second slot** on `_Live` beside the
build one, or a ninety-second read of an unrelated program would lock the reader out of
changing versions for no reason anybody could state.

**`--progress-json` is a contract, not a scrape.** stdout is one JSON object per line;
stderr, emptied by `--quiet`, is where a failure says why. The step list is **computed for
the run** — `--no-docs` makes it five and not seven — because a bar drawn against a total
this run can never reach is a run that looks like it died at step five (rule 32). Verified on
the real corpus: 63 lines, one total, 628 files and 2,064 documents, empty stderr.

**Eight refusals, each with its own sentence**, from one `analysis.check` that both the
dialog's live warning and the endpoint's answer go through (rule 41). The sharpest is the
**served program**, and it is not caution: `Store._discard_if_stale` drops every table of a
graph written by another build, and this server is holding that graph open. Analysing into a
name that already exists is *allowed* and says it rewrites that program's working snapshot —
Tom's call.

**Two defects found by looking rather than by testing**, which is the whole argument for
rule 38:

1. **A disabled `.linkbtn` did not look disabled.** The class sets an explicit background and
   colour, which overrides everything the browser does to say a control cannot act — design
   rule 16's defect arriving through a stylesheet. The rule existed under `.trailbar` and has
   moved beside `.linkbtn` itself, where both callers pass (rule 51).
2. **A failed analysis handed the reader a fourteen-line traceback with the useful line
   last.** The reason now **leads with the child's last line** and keeps the rest as evidence.
   And the case that produced it — a file sitting where the program directory would go — is
   a pre-flight sentence now, not a `FileExistsError`.

**Looked at in a browser, with a real pointer.** `elementFromPoint` confirms every control is
reachable rather than merely wired (rule 48); 75 characters typed into the path field
survived 75 repaints with the caret held; and `/` does not leak to the topbar search, which
matters because every path on this machine starts with one. The full loop was driven from a
real click: analysed, appeared in the selector, opened, served. **Still the automation tab
though** — 1,259×523 at a 16px root, and screenshots crop at 784×326, so the surfaces were
seen by parking the dialog inside the frame. Rule 38's debt is *reduced*, not paid.

*A coordinate trap worth knowing:* the `computer` tool's coordinates are **screenshot space**,
not viewport space. A click asked for at (626, 186) landed at (1005, 298) — the 1.606× ratio
of 1,259 to 784. That is the "clicks did not land where `getBoundingClientRect` said" note
from chunk 5, explained: multiply viewport coordinates by `784 / innerWidth`. It cost one
false bug report before it was checked.

*Candidate engineering rule, for Tom to mint or refuse:* **a long job is not a switch — a slot
names what is being replaced, not what is running.** Not minted.

**Chunk 2 is planned and not built:** *"About this map"* — what read this directory, shown so
a reader can decide to read it again. See "What is next" below.

---

**Before all three — the earlier pause of 2026-09-04, five features back.** 951 tests, mypy clean,
ruff clean, console clean, working tree clean, `check` reports 0 broken. Five things landed
that day, each whole and committed on its own:

| Commit | What |
|---|---|
| `94858d5` | Document mode **chunk 5** — a glossary citation into the corpus opens; **rule 79** minted |
| `3ce4c4a` | the naming standard says it was **derived**, not required |
| `427bace` | a naming standard written as a **table** is read — corpus FORM rules 0 → 7 |
| `b92dec0` | the mode toggle **dims** instead of vanishing; a program's own output leaves its corpus |
| `36a6439` | the **program selector** works |

**Next, and Tom has asked for it in this order:** *"+ Analyze a directory…"* — running an
analysis from the server, with progress, failure, and a new program appearing in the
selector. It is deliberately **not** in the `<select>` yet, because a third option that does
nothing is the defect the selector just fixed. No plan written; the approved plan file
`~/.claude/plans/async-hugging-whistle.md` holds the selector's, now built.

*Document mode is finished — chunk 5's approved plan was at
`~/.claude/plans/polymorphic-finding-swan.md`, superseded on the day by two decisions: the
viewer keeps its raw span **and** gains a hop into the prose reader, and rule 79 was minted.*

**Two servers were running at the pause and are stopped now**: `serve output/mensores` and
`serve output/dunneflow`. Both directories are current — the pair was rebuilt after the table
detector bumped the documentation fingerprint, and `output/dunneflow` was re-analysed after
the corpus fix. `output/beads` is stale by design and is what the selector's failure path was
tested against; `output/mensores@2026-08-29T19-43-39Z` and two `2026-08-31…` revisions inside
`output/mensores` are orphans, named in the record and left for Tom to delete or keep.

**Three things are waiting on Tom, one of them now closed, and none blocks anything:**

1. ~~**A candidate engineering rule, not minted.**~~ *Minted 2026-09-04 as **rule 79** —
   a lifetime change is an access-pattern change — on Tom's call. In `RULES.md` in full,
   indexed in `CLAUDE.md`.*
2. **A real window is owed a look.** Every figure in three sessions was taken at a 537–1,285px
   centre pane and a **16px root font**, in a browser context that reports 1,267×539, refuses
   `resize_window`, and crops its screenshots. His Chrome is **24px on a 4K screen**, where
   rows are taller and the pane proportionally narrower. Rule 38, still open, and the
   sticky-overlap defect in lane 2 was caught only because it happened to fall in the visible
   crop. The column weights in lane 2 (`DOC_COL_WEIGHT`) and lane 1's list row are the two
   places most likely to want adjusting.
3. **The extractor records 3–4 headings that are inside fenced code blocks** — examples of
   headings, not headings. 3 or 4 of 29,980, found by the renderer disagreeing with the map.
   Rule 12 is holding; this is the residue. Not fixed: correcting it changes `docs.db`'s
   contract, busts every cached graph, and rewrites 29,980 rows for four of them. Named here
   rather than filed, because it may never be worth doing.

**Next: whatever Tom picks.** Document mode is done and the open list below owns the rest.
The two nearest things are both his eye rather than my keyboard: the three surfaces never seen
in a real window (rule 38's debt, and chunk 5 added a fourth — the viewer's foot is 56rem wide
and never appeared in a capture), and the `<module>` inspector routing that he found on the
way past the Code-pane defect.

**Both lanes work.** Lane 2 is the map's own eight documents, every row an ordinary
selection. Lane 1 is the program's own 2,064 — a list grouped by class, a filter, a reader
with the document's headings beside it, and all three link kinds routed.

*Earlier the same day:* chunk B of the shortening work, rule 78, and three rounds of looking at
the code view — the greenbar, the margin fold, three broken buttons, and the rail/centre split.

*The paragraphs below are that day's earlier work, kept because the reasoning is recent and
load-bearing; the current task is the one named above.*

### Before that: the program selector works (2026-09-04)

The topbar's first control has never worked — three options and no change handler in the
ratified artifact, one served option in every shipped build, and no endpoint to fill it. It
switches programs now: `/api/programs` lists every directory under the output root holding a
map, `POST /api/program` rebuilds against one.

**It is the revision switch one axis over, and the reload is what made it small.** A program
switch cannot keep the selection, the trail or the revision; the reload discards them and
`loadSettings(program)` restores the arrived-at program's own settings, which have been keyed
per program all along. `serve` needed no CLI change — the siblings come from
`revisions.program_dirs()`, written that morning for the docs-corpus fix.

**Two things are not a mirror image.** The sidecars are repointed, because `source.db` and
`docsource.db` belong to the program. And **every** cache is cleared, because `findings` is
keyed on a graph's *basename* and `filepairs` on a pair of revision strings — two program
directories collide on both, without needing a coincidence. `PROGRAM_CACHES` is written out
rather than derived from `COMPARISON_CACHES` (rule 36 in both directions).

Verified on the real output root: `mensores` → `dunneflow` moves cover, navigator, graph and
glossary; the sidecars follow; settings stay apart. **And a switch to the genuinely stale
`beads` failed with the store's own sentence and left `dunneflow` still being served** — the
mode that would otherwise take the dashboard down. **9 mutations, all CAUGHT**, after two
survivors that were both my own guards failing to reach the code.

### Before that: a naming standard written as a table is read at last (2026-09-04)

**The FORM lane was empty across 2,064 documents**, and the reason was one shape: `_table()`
consumes a table whole and the loop `continue`s, so the prose rule detector is never offered
its lines. A naming standard is usually a table. `harness/rules/style.md:30` states seven
conventions as `Type | Convention | Example` — every row a class of identifier and the
spelling it must have — and DunneFlow could not read one of them. **`checkable` had therefore
never once been true**, and the whole point of that field is to be a comparison's input.

`table_rule_columns()` decides which column names the thing and which gives its spelling, on
the model of `term_columns`/`meaning_columns` beside it and keeping the rule that matters:
**both halves, on different columns.** A column qualifies on its **header or its cells** —
headers vary between organisations, and cells alone miss a column headed `Convention` whose
contents are too terse to score.

**Measured over the whole corpus before a line was written: 5,230 tables, one fires.** It
mints 7 rules, 6 of them checkable. The 100-row *Key Decisions* table does not fire; nor does
the pantheon, which is a glossary in a naming standard under a naming heading and is the most
dangerous near-miss there is. Corpus-wide FORM rules: **0 → 7**. VOCABULARY unchanged at 5.

**Two things the plan got wrong and measuring caught.** The two table-cell regexes added for
`CAPS_UNDERSCORES` and `colon separator` earn **nothing** on this corpus — the column is
headed `Convention`, which the header list matches, so it yields all seven rules with them
removed. What they earn is the *cell* path, which is what has to carry a standard written by
somebody who does not work here; the comment now says that instead of overclaiming. And the
seven new rules would have had **seven dead links**: the handbook links each stated rule to
`[the rule in full](#slug)` and only the Vocabulary section ever emitted a heading to slug,
so a FORM rule pointed at nothing. That is the `where_` defect's shape and it is why **Form**
now has a *Stated* half above its *Measured* half.

**And a sentence that had never been printed said something false the first time it was.**
`checkable` had no true branch in practice, so *"Mechanically checkable."* went out beside
"Type attributes: colon separator" — for which this tool has no population and no check. It
now says what is true: a check *could* be written, and DunneFlow does not run one.

**10 mutations, all CAUGHT** — after a first pass where 5 survived, every one of them a
fixture missing *both* column halves rather than one, so a mutation dropping either still
passed. Rule 37, in the guards written for it.

### Before that: Document mode, chunk 5 — a citation into the corpus opens (2026-09-04)

Design rule 13's last unmet half. **`senseOpens()` is a capability test rather than a
provenance test** — `s.provenance === "DECLARED_CODE"` was true of the tool until chunk 1 gave
the document corpus a sidecar, and stopped being true the moment it landed. `/api/glossary`
now carries a `sidecars` block, `{opens, reason}` per tier, computed from the live stores and
the base's two revisions, because whether a corpus can be read is a fact about the *directory
and the base* that the page has no other way to learn.

**Both halves of the reading are offered.** The viewer shows the span out of `docsource.db` —
the bytes **as measured**, Markdown syntax and all, which is what proves the citation — and
its foot offers *Read it in the document →*, which closes the viewer, opens lane 1 and scrolls
to the block holding the line. Verified live: `mensores` → `.groma/PROJECT.md:474` → the
paragraph spanning 474–475 flashed, **55,810px into 459 blocks**. That is chunk 4's
`data-line-end` innermost-containing lookup doing the thing it was named for.

**The refusal is per corpus and was verified on a real asymmetric base.** `output/mensores`
holds source bodies for both revisions and document bodies only for the newer, so serving the
2026-08-26 base gives code citations that open and documentation citations that do not, with
the version reason stated — and `/api/docsource` refuses rather than serving newer prose under
older headings (rule 70). On that base the 32 documentation rows render as plain text with no
button at all: no control that resolves to nothing.

**Reading the sentence out loud is what caught the defect.** The server's four reasons are not
one part of speech, and embedding a clause in `because there is …` produced *"because there is
this sidecar holds nothing for the version on screen"*. Every test passed. A dash takes both,
the wording stays the server's, and the guard that the shell carries none of the three
sentences tripped on the comment explaining the fix — the sixth time a guard in that file has
failed on its own prose.

**17 mutations, all CAUGHT.** 928 tests. Every measured figure is in `PERFORMANCE.md`; the one
worth carrying is that a documentation citation costs **999 ms** and a code citation costs
**999 ms**, which is the glossary's own repaint and not either route.

### Before that: Document mode, chunk 4 lane 1 — the program's documents, read (2026-09-03)

The last piece. 2,064 documents mined for 29,980 headings and readable nowhere now have a
list, a filter, a reader and a side nav.

**Two lanes sharing a pane — two subjects, not two views of one thing.** One mount, one
subtree cache, one `render()` branch, so the cache key carries the lane: a subtree keyed on
the other lane's page is handed back on a switch, which looks exactly like a switch that did
not work. **The filter hides rows rather than rebuilding** — 2,064 rows per keystroke is the
cost, and rebuilding also destroys the `<input>` being typed into. The reader wraps to one
column by **flex-wrap rather than a breakpoint**, because this depends on the *centre pane* and
`@media` can only ask about the *window*.

**The screenshot found what nothing else could.** `html: false` does not hide an HTML comment
— **it un-hides one**: markdown-it disables the `html_block` rule entirely, so a comment
arrives as an ordinary paragraph and renders as body prose. **7,317 of them across 505 of
2,019 documents.** The first fix, written against `html_block` tokens, counted zero — there
are none. They are lifted out before parsing, replaced by their own newlines, and listed with
their lines rather than dropped.

**And a heading that was not one found what chunk 5 will need.** One of 1,566 stopped matching
after the comment strip: `## Discoveries` **inside a code fence**, recorded by the extractor as
a real heading (3–4 such in 29,980). What it exposed is that blocks carried only their *start*
line — and the lines anybody opens at are mostly not the first line of anything. **A definition
sits mid-paragraph, which is exactly what chunk 5 opens against.** Every block now carries
`data-line-end` and the lookup takes the innermost containing block. Zero unreachable headings.

**Three of my own guards survived their mutations, all the same way**: each checked that a
*name appeared* rather than that anything happened. Rule 37, three times, in a chunk whose own
defects are rule 37's shape.

**23 mutations, all CAUGHT** on the second pass. The list is 56 ms to paint and 5 ms to
repaint; the filter over 2,064 rows is 2 ms; the 1.32 MB worst case is 668 ms to open.

### Before that: Document mode, chunk 3 — the renderer (2026-09-03)

`prose.js` and the vendored `markdown-it`. **Its own file, and the boundary is `graph.js`'s**:
it turns text into markup and knows nothing about this page, and what it has to say leaves as
data attributes the shell routes.

**The line CLAUDE.md draws is enforced now rather than stated.** `VERSIONS.json` has claimed
*"a test asserts it"* since the library was vendored and there was no such test — rule 43's
shape, the same as `shorten()`'s docstring promising a `selfCheck`. Nothing under
`extractors/` may mention the library: its output is a contract hashed into the cache key,
and a renderer is in no cache key at all.

**The property it was chosen for, verified rather than assumed**: every heading `docs.db`
recorded found in the rendered DOM at exactly its own line — **825 of 825** across 60
documents, 782 of 782 across another 41. That is the chain design rule 13 rests on.

**Every link and image decision came from the corpus**: 3,516 https · 6 http · 666 relative ·
16 anchors · 6 unfollowable schemes · 5 images. External links stay links in a new tab;
relative links and anchors **lose their href entirely**; `graph:` and friends render as text.
**An image is never fetched** — that is egress rather than navigation, no click and no
consent (design rule 14). Swept over 230 documents and 4.0 MB: zero errors, zero hrefs that
could navigate away, zero `<img>`, zero `<script>`.

**Frontmatter is half the corpus and the obvious fix was the trap.** 989 of 2,019 documents
open with YAML that markdown-it renders as a setext heading. *Cutting* those lines shifts
every `token.map` below by a constant — a page that renders perfectly with every line number
on it wrong. They are **blanked** instead: no arithmetic, none to get wrong.

**Two process findings.** A guard passed on the *comment* explaining it — dropping
`noreferrer` survived a mutation because the paragraph saying why it was there was still in
the searched text, which is `_code()`'s own recorded defect reproduced within an hour of
reading it. And a mutation harness killed by a timeout **leaves the tree mutated**, which
`git checkout` cannot undo for a new untracked file: commit before mutating.

**22 mutations, all CAUGHT.** The library is 29 ms lazily; 1.32 MB parses and renders in
40–72 ms.

### Before that: Document mode, chunk 4 lane 2 — the narrative view delivered (2026-09-03)

**The ratified design's own sentence, built at last**: *"the same selection, as a document,
scrolled to the routine you have selected."* `documents.py` has carried a graph node id on
every row since it was written precisely so this could exist, so a row is an **ordinary
selection** — the stack lights, the inspector fills, the navigator marks and reveals, the
trail records the hop, undo reaches it. Driven and read back off the page, not asserted.

**The `where_` bug is fixed and it was worse than it sounded.** All eight `DOC_*` statements
aliased their location column `AS where_` — `where` is a SQL keyword — while `documents.py`
keyed it `Column("where", …)`, so the **"Where" cell of every row of all eight documents**
rendered blank. Now `AS "where"`, and every statement in the family is prepared against the
real schema with each `Column` key asserted to be one it returns. 0 blank cells on Mensores.

**The first draft cost 9,568 ms per `render()`** — the code browser's own defect at six times
the size, written by someone who had just read the comment about it. And **two of three
fixes did nothing** (rule 39): 566 tables against one was 2,049 ms against 2,103; 4,786
`<button>` cells against spans was inside the noise. What worked was not repainting, plus
`content-visibility: auto` per group (**61 ms against 3,205**) and `table-layout: fixed`
(1,769 against 2,389). First paint is now **631 ms** on the largest document and repaints
are 19–94 ms.

**Two defects found by looking and by clicking.** The group name and the column headers were
both sticky at `top: 0` inside one container, so the name covered **every column label** the
moment a group reached the top of the pane — nothing threw, and only a screenshot showed it.
And the **trail note never landed in three routes**, one of them a year old: `codelink`,
`docrow` and `doctable` all push a note after `selectFromNav` has already recorded the step,
and the dedupe threw it away whole. A deduped step now adopts a note the standing one lacks.

**21 mutations, all CAUGHT.** The rule-38 debt stands and grew: every figure was taken at a
537px centre pane and a 16px root font in a window that refuses to resize and crops its
screenshots at 784px. **A real window is still owed a look.**

### Before that: Document mode, chunk 2 — the corpus served (2026-09-03)

Every figure the plan predicted came back exactly: **2,064 documents** (2,019 Markdown, 45
text), 29,980 headings, 235 definitions, 8 duplicates, all openable, and the class breakdown
to the row — PLAN 1601 · OTHER 286 · DECISION 92 · RESEARCH 33 · TOOLING 12 · README 9 ·
REFERENCE 8 · ROADMAP 6 · SPEC 6 · NAMING_STANDARD 5 · GLOSSARY 3 · ISSUE 2 · CONTRIBUTING 1.
The list is 546 KB of JSON at **18 ms warm**; the worst case, `.groma/ISSUES.md` at 1.33 MB
and 18,299 lines, is **6–7 ms warm**. Both whole, neither paged.

**The document store is held on `_Base` now, and the 148 MB per-switch leak its old close was
written against has moved rather than gone** — the swap closes it, `_Live.close()` closes it,
and so does the failure path of `open()`. Three closes where there was one, all three guarded,
one of them exercised by asking the outgoing connection a question after the switch.

**Two defects, and neither could have been found by a test.**

*A 000 and a stack trace on the first request.* `DocStore` had no `shared` parameter at all,
because it had only ever been opened, read and closed on one thread. Held on the base and read
from a request thread, sqlite refuses it **by name, from inside the request, and only on the
routes that touch it**. Every unit test passed, because a unit test calls the builder on the
thread that opened the store. Its guard starts a real `threading.Thread`.

*And rule 70, one corpus over from where it was first paid for.* `_sidecar_revision` returns
`None` for *this sidecar cannot serve the version on screen*; every store reads `revision=None`
as *the current one*. Two meanings, one spelling, and the newer won: Mensores' 08-26 base
listed all 2,041 of its documents as openable and served the **08-29** prose under them, every
heading's line landing wherever the text had since moved. The source sidecar never showed it
because it holds both snapshots — the older base is the first version anything here has ever
had no bodies for. `serving()` is the fix: `revision=None` is a refusal with a sentence, never
a fallback. `_span`, which `/api/source` shares, had the identical hole.

**Fifteen mutations, all CAUGHT.** Four absences, four sentences — never scanned, not
captured, not for this version, not this path — because they look identical on a blank pane
and the thing to do about each is different.

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

*Chunk 2 is done — it is the entry above.*

*Still queued behind the plan:* the flow panel's real worst case — `session.add_turn` at
`_extraction_state.py:742`, 3,323 bytes over 53 lines, on a *resolved* call, so its arrow can
be opened. One outlier and not a class: the next largest resolved call argument in the corpus
is 923 bytes.

**A server is running on 8787**, on the **08-29** base. Bring one
back with `uv run dunneflow serve output/mensores --port 8787 --no-open`, and add
`--revision 2026-08-31T22:53:15Z` to open the older one — which is the base with **no document
bodies**, and is worth keeping in mind: it is the only version anything here has ever had none
for, and it is what turned up the rule-70 defect. `output/mensores` also holds `docsource.db`
(17 MB on disk). `pkill -f "dunneflow serve"` ends it. Note that `--port` yields to any free
port if the asked-for one is taken, so a second server started over a stale one lands
somewhere else and says so on its last line.

**The debt is unchanged and it is rule 38's.** Everything in chunk B was measured at 1396px in
a browser context that reports `outerWidth: 0`, refuses to resize, and whose **screenshots did
not track the live DOM** — the region under a freshly measured element kept rendering the pane
beside it. Every number above is a measurement and every guard is a guard; what none of them is
is a look. Three things now wait on a real window: the constants surface, the blank-graph fix,
and this.

### Before that: Document mode, chunk 1 of 6 — a body sidecar for documents (2026-09-03)

**Paused mid-feature. The approved plan is at `~/.claude/plans/polymorphic-finding-swan.md`;
read it before resuming.**

**Document mode was never "browse documentation", and that is what makes the question
interesting.** The ratified `viewDoc()` is a hand-written sample of narrative prose *about the
current selection*. Half of it arrived as Code mode; the other half — the selection read as a
document, scrolled to the routine you picked — has been buildable since `documents.py` started
putting a graph node id on every row, and simply had no view. Meanwhile the **name** promises
something real and entirely unmet: nothing in DunneFlow could read a program's documentation.
2,064 documents mined for 29,980 headings and 235 definitions, and **zero** of them readable.

Tom's direction, and it shaped the plan: *"I don't want to abandon the old code, I want to
resolve it."* The narrative view's two claims each get a home and the eight generated
documents get the reader they never had — nothing is deleted for being unfinished.

**Chunk 1 is built and committed.** `sourcedb.py` was already a generic blob store; the only
thing hard-coded to code was the `kind` stamp, so `DocSourceStore` is that class with a
different one, in its own file because design rule 14 turns on documentation and source being
separately handable. **`capture()` needed no change at all** — `DocStore.known_hashes()`
returns exactly the map it wants — so there is no new capture path and no change to `walk.py`.
Measured: **2,056 bodies for 2,064 paths, 38.7 MB of prose in 14.8 MB**, against a predicted
14.87.

**Two defects found in the building.** `adopt_revision` exists because the first build had
none: `open_working` mints an id from the clock, which is right for the store that *is* the
authority, and a second sidecar is not — without it the capture wrote 2,064 path rows and left
`revisions` **empty**, so nothing could resolve them (*"2,056 bodies for 0 paths"*). And **rule
16 had a hole**: `set_meta` does not commit and `close()` does not either, so a sidecar created
and closed landed with an empty `meta` — no kind — and the wrong class then opened and
**restamped** it. Production never reached it because `analyze` always commits afterwards,
which is the hazard exactly: *the guard was intact everywhere it was exercised*. It took a
second kind to be mistaken for before anyone could see it.

**`markdown-it 14.3.1` is vendored and recorded**, with the line that matters written beside
it: `CLAUDE.md`'s *"no markdown library"* governs the **extractor**, whose output is a contract
hashed into the cache key. A renderer is in no cache key and no fact depends on it, and nothing
under `extractors/` may import it. Both properties it was chosen for are verified in the
browser — `token.map` on every block, and `html: false` rendering a `<script>` as text.

*Open and not yet handled:* relative links (`./rel.md`, `#anchor`) render as **live hrefs** and
would navigate the dashboard. Chunk 3 must route them.

**Next was chunk 2, and it is built** — see the entry at the top of this section.

### Before that: one file, two panes, and one button for both (2026-09-03)

**Reported as a question about whether the tool was telling the truth**, which is the form the
useful ones take: *"Once again, I'm told there is no file open... The list of files is on the
left side, and I had clicked on one of them, so it must have been open, right? What was
supposed to happen when I clicked on those buttons?"*

`‹ files` in the rail and `files ›` in the centre were **the same control** — both
`data-codeback`, both `openCodeFile("")` — and `state.codeFile` is **one value serving two
panes**, with `codeList()` deciding list-or-file purely by it. So a button reading *show me
the list* closed the file everywhere. The reader was right and the pane was wrong.

The centre's copy was the worse of the two: `viewCode()` has **no file list at all**, so its
whole effect was to remove what the reader was looking at and print *"Open the Code group in
the navigator and pick one"* — a control that empties a pane it cannot refill. It is gone.

**And it was mine to have surfaced, which is worth recording as a shape.** `openCodeFile` had
never called `render()` until earlier the same day; before that the rail's button looked
pane-scoped *by accident*, because the centre kept its already-painted chrome until something
else repainted it. The state was global the whole time. **A fix that makes an inconsistency
visible gets reported as the fix's fault, and is not.**

Two questions, two fields now: `codeRailList` is where the **rail** is, `codeFile` is what is
**open**. Tom's own argument for code in the rail is quoted a few lines above `codeList` —
*"I want to be able to see code and graph at the same time"* — and a rail that must empty the
centre to show its list is that undone, as it had been since Code became a fourth centre mode.

*Four mutations CAUGHT and one control case correctly **not** caught*: a `data-codeback` in
the rail must not trip the guard, because that is where the button belongs. A guard firing on
both would assert the opposite of the fix.

### Before that: three broken buttons on the Code panel (2026-09-03)

**Reported in one line each, all three real, and no two of them the same bug.**

**`margin 35` did nothing** — the fold built an hour earlier and tested at the keyboard before
it shipped. `wire()` runs at the end of *every* `render()` and calls `addEventListener` with a
fresh closure; for a control in `#viewMount` or `#inspector` that is harmless, because those
are rewritten each render. **The code chrome is the one surface that is not** — it repaints
only when `codeDomKey()` moves, so a 1.37 MB subtree is not re-attached on every keystroke.
The button survives and the listeners pile up. Measured: five renders after a paint, **one
click ran the handler six times**. An even number, so nothing happens; one, three or five all
work, which is why it passed its own test and my own look at it. `CODE_ROUTES` is the answer
and its comment already said so — **a route cannot accumulate** — and the guard is now about
the whole surface rather than the two buttons.

**`files ›` fired every time and the reader was watching the wrong pane.** `state.codeFile`
went to `""` and the navigator's list came back; `loadCodeFile("")` returns at its first line
and `openCodeFile` never called `render()`, so the centre kept the file, its title and its
footer. Rule 77's companion one route over: **a route correct for the caller it was written
for is wrong for the caller it has just acquired** — `openCodeFile` was the navigator's, and
`Code` became a centre mode after it.

**Back then Forward did not restore the file.** `selectionSnapshot()` records where the
*drawing* is and not where the *code* is, so a file open — which changes no selection — filed
a step that `sameSelection` deduplicated away. The comment beside `diagramId` says this about
itself in those words; the lesson was written one view over and never carried across.
`codeFile` is in all three places now — recorded, compared and restored — because a field in
one or two of them is worse than none.

**What they have in common is worth more than any of them.** Every one was a control whose
*state* was right and whose *pane* was not, and none was visible to a check: the listener was
attached, the route ran, the step was filed. The tell in all three was a reader clicking and
watching — rule 38's debt, paid by Tom for the third session running.

### Before that: the code view, looked at (2026-09-03)

**Four things in one screenshot, at Tom's own keyboard and his own window.** Three were real
and one was a question that answered itself.

**The greenbar was a row breaking twice.** `rows.join("\n")` is the reflex, and inside a
`<pre>` it is not whitespace between tags — it is content. `white-space: pre` renders it as a
line break and the row span is already `display: block`, so every row was followed by an empty
one: **1,703 rows in 58,932px, 34.6px a row against a 17.28px line-height.** Now 29,520px.
**Three surfaces had it** — the centre's table, the navigator's pane, the glossary's citation
viewer — and only one was reported; the others were found by looking at the remaining `<pre>`
builders. `srcPane` keeps its newline and that is the rule rather than an exception: its rows
are not wrapped in a block. **A row breaks once**, and the guard asserts both directions.

**The indent was not an indent** — it is the margin column, and a fixed 12rem reserve fails
from both ends at once: **92.4% of rows carry no mark** and pay it in full, while **37.7% of
the marks that exist are clipped** by it. (A comment records it was already narrowed once from
15rem, which treated the symptom; the mark widths run median 185px to **max 1,263**, so no one
width can serve both.) Three ways out were measured and put to Tom. **His call: fold it** —
248px down to **76px**, and at his 24px root that is 258px of code back. Folded, a marked line
still says so with a glyph carrying the whole mark on its title (rule 45, design rule 1), and
a file with **no** marks renders no mark elements at all.

**The line numbers were asked about and left alone.** `3.5rem`, right-aligned, four digits —
exactly the reason Tom guessed, on a 1,703-line file.

**The grey area is provenance**, and it folds now per his standing rule. *That fold was itself
a dead control in its first draft*, which is worth more than the fold: `render()` repaints the
code chrome only when `codeDomKey()` moves, so flipping the state and calling `render()` set
the field and changed nothing on screen — design rule 16 with every part working, in a control
added to satisfy a rule about controls.

*Two guards went blind rather than green on the way*, which is the only reason they were
survivable — one matching a class attribute that gained a second token, one `_fn_body` unable
to see an `async function`. And one self-inflicted `SyntaxError`: two `const bare` in one
scope, caught by `test_the_javascript_parses` on the next run.

### Before that: no pane assumes what it was showing is still true (2026-09-03)

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

### The next pass, as scheduled

Tom, 2026-09-08, on the four defects: *"add the other items for the next pass after this
one."* This is that list, and it is drawn from the entries below rather than kept beside
them — the entries are still where an item is closed, and this is only the order.

1. **Three things have never been *looked* at.** *Two are answered 2026-09-08 — see the top
   of this file.* The **kept fold** and **kept flow** both open from the shelf, verified at
   the pointer, and the stated cross-compartment limitation is honest. The **hover card's
   shadow sentence** turns out to be **dead code**: a shadow is drawn at radius 0 and alpha 0
   and both paths into `onHover` resolve through `realIndex`, so `h.shadow` can never be
   true — 1,989 picks over 562 distinct nodes returned not one shadow. *Withdrawing it is
   Tom's call, below.* Still open: the **worklist's and the ribbon's row layouts**, which are
   design calls waiting on Tom's eye — and the navigator's rows have joined them with a
   number (below). The instrument reaches all of them, and rule 83 is now measured rather than
   described: pointer space and capture space are both 784 px wide and differ by **exactly
   2×**, so `pointer = viewport / 1.5581` and `viewport = screenshot × 0.779`. **A body pan
   breaks hovering while it lasts** — pan to find a target, un-pan to touch it.
2. ~~**Two maps in `output/` cannot be opened**, both refusing exactly as designed and both
   one command away.~~ *Closed 2026-09-08, and it was wrong on both counts — see the top of
   this file. There were **three**, not two, and the command each was sent to would have
   refused it: `_refuse_if_stale` branched on absolute paths where the migration branches on
   a fingerprint. Three of the four now open; the fourth is a decision below rather than a
   defect.*
3. ~~**The superseded snapshot's sidecar rows.**~~ *Closed 2026-09-08 — Tom ran the command,
   and it is verified at the top of this file.*
4. **The rebuild-recipe rule**, to mint or refuse: *a rebuild recipe must name every store
   the change invalidates.* `standards.db` is a document store, went stale with the corpus,
   and stopped `serve` from booting at all.
5. **Three found while looking. Tom answered two the same day.** The **dead shadow branch**
   is *withdrawn*, with a guard that asserts the two facts closing it before it asserts the
   consequence. The **navigator rows** got Tom's mechanism — the module path yields its width
   first — which is **335 → 266 rows and 101 px → 49 px at the declared 21rem**, a fifth
   better and *not closed*: the remainder needs a decision about the **name** (wrap, truncate,
   or let the row grow, rule 84), and each is rejected by one of the two comments over
   `.navlabel`. **Still open.** Two pluralisations, *"1 boxes"* and *"1 call sites"*, need
   nobody and are not done.
6. Then the standing backlog below, none of it scheduled.

### What is next, and it is open

Nothing in the anomaly worklist's chunk 5 is outstanding, the argument gap is closed, and
the two small things filed as known are done. *(That is the worklist's chunk 5, written here
2026-09-01 and unrelated to Document mode's chunk 5, which landed 2026-09-04 and is at the top
of this file. Two features numbered their chunks from one; the sentence was unambiguous until
the second one existed.)*

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
- ~~**A program selector**~~ *— built 2026-09-04.* ~~**"+ Analyze a directory…"**~~ *— built
  2026-09-04 too, and the option is in the `<select>` now that it does something. See the top
  of this file. The original entry:* Tom, 2026-09-04: *"What is
  missing is a way to switch between the two — that used to exist… I definitely want to add
  the Analyze a directory part next. That's what I'm looking for at the moment."* The
  ratified artifact `f993d319` has the selector — three options, `mensores — 623 files`,
  `dunneflow — 23 files`, `+ Analyze a directory…` — and **no change handler even there**.
  The port carried the markup and emptied the options with every other pinned array; unlike
  the others it never got the endpoint that fills it. What exists to build on: `_Live.open()`
  already rebuilds a whole base atomically against a different graph and refuses without
  leaving a broken one behind, which is the revision switch — a program switch is the same
  operation pointed at a different directory. What has to be decided: `serve` takes a
  program directory today and would take the root while still accepting either; a program
  switch cannot keep the selection, the trail or the revision, all of which belong to the old
  program; and the list must say what it found *and* what it cannot open, because
  `output/` here holds four candidates of which two are stale or old-style.
- ~~**"About this map": what read this directory, and whether anything was inferred.**~~
  *Built 2026-09-04 — see the top of this file. The entry as it was filed:* Tom asked that an
  analysis record **what model was used**, in an *"About this directory"* dialog, so a reader
  might analyse again when a better one exists.

  **No model is used**, and that was checked before it was planned: the extractors are
  stdlib `ast` and `tokenize`, the document scanner is hand-written, and there is no LLM call
  and no network egress anywhere on the analysis path. `Provenance` declares four tiers and
  only the two free ones are built — `CITED` and `INFERRED` are designed and unbuilt.

  Tom, on being told: *"Perfect, keep it that way as much as possible! Inference should
  always be voluntary and secondary."* So the row is **a standing guarantee, not a
  placeholder** — *nothing in this map was inferred, and nothing was read by a model* — and
  the model field exists so that a reader who ever turns inference on **voluntarily** can see
  which facts it paid for.

  **And the live re-analysis trigger already exists and is surfaced nowhere.** Every store
  records `extractor = f"{SCHEMA_VERSION}:{rules_fingerprint()}"`, and `_is_stale` compares
  it against this build's — today only to refuse. That comparison *is* "would a newer
  DunneFlow read this differently?", which is the question Tom wants answered; it has never
  had a reader. The plan is at `~/.claude/plans/wondrous-crunching-ocean.md`.

  *Candidate design rule, for Tom to mint or refuse:* **inference is voluntary and secondary,
  and a map states whether any was used.** One step over from design rule 14, which scopes
  *egress*; this scopes whether a fact was *guessed*.

- ~~**Five surfaces have never been *looked* at in a real window.**~~ *Discharged
  2026-09-06 — all five seen, and the obstacle was never the surfaces. See the top of this
  file and `HANDOFF.md` under that date. The instrument was misread for four sessions: the
  automation tab's **screenshot** covers `inner ÷ dpr` — the top-left quarter — while its
  **click** frame covers the whole viewport, so the two differ by exactly the device pixel
  ratio. The pointer could always reach the inspector at x=985; only sight stopped halfway.
  A click computed as `784 / innerWidth` lands on the element (verified against a capturing
  `pointerdown` listener), and `transform: translate(-x,-y)` on the app root pans the capture
  window over the real page at full fidelity. `resize_window` does not refuse — it reports
  success and changes nothing.*
- ~~**Ways in as nodes on the Diagram**~~ — *built 2026-09-05, an hour after being deferred.
  Drawn by default on a measurement (ports max 41 per compartment, ways in max 3), arrows
  bounded at 8 per way in with the bound stated, and clicking one opens the way-in pane. An
  entry arrow refuses to open as a flow and says why: the caller is the operating system.*
- ~~**A package row does not make a selection.**~~ *Built 2026-09-05 — see the top of this
  file. A plate is a fourth subject beside `flow`, `fold` and `selected`, answered by
  `web/plate.py` and drawn by `viewInspectorPlate` on the `viewInspectorConstant` precedent.
  It decided what selecting a package **is**: not a nominated member (rules 30 and 74), and
  **mark-and-state rather than a filter** — the fold's settled shape one level up, so the
  rows are marked, the count says how many, and the table stays the whole program. Three
  pre-existing gaps went with it: the table marked on `state.selected` alone, the crumb read
  `state.selected` alone, and the package row lost its own `aria-current` to the rebuild its
  own click triggers.*

- ~~**`<module>` is answered in a routine-shaped inspector.**~~ *Built 2026-09-05 — see the
  top of this file. It was **two** false statements rather than one: the three-way "way in,
  dead code, or a call DunneFlow cannot see" hint, false of all 487 module nodes (0 callers,
  0 entrypoints, measured); and `def <module>():`, a copyable declaration of a routine
  nobody wrote, which `hoverSigHtml` already refuses one surface over. Not a separate pane —
  Out, Touches and Governance are all correct for module scope, and copying them would be
  rule 51's own defect.*

- ~~**Clicking a change row files two trail steps**~~ *— closed 2026-09-07, and* **corrected**
  *rather than merely struck. No path files two, and the change row is not among the affected
  paths at all: it sets its subject synchronously, so the dispatcher's step lands correctly.
  What was real is that seven callers named a step* around *an async move and lost what they
  were saying — the label replaced by one arbitrary member of the selection, the note written
  onto the step being left. The half the entry got right is that it belonged to the selection
  path. See the top of this file. Filed from reasoning in 2026-09-02, and both descriptions of
  it were wrong until it was measured.*
- **A kept fold and a kept flow have never been opened on screen.** The shelf routes three
  kinds and the node kind is verified; the other two need a compartment drawn. The kind and
  the route are guarded against each other at the source, in both directions, which is why
  that guard exists rather than a click — but it is a shape check and not a look.
- ~~**Every surface that offers "keep this" is an inspector pane.**~~ *Built 2026-09-06 — see
  the top of this file. Four surfaces gained it, not three: the naming convention row mints the
  same cohort a thread does. **Two routes, Tom's call**, because `PIN_ROUTES` is keyed on `kind`
  ∈ {node, fold, flow, plate, line} and `THREAD_SUBJECTS` on `type` ∈ {node, cohort} — one word
  meaning two things in one table is rule 47's companion. A thread's node subject is translated
  into the map space so the two doors mint one pin; a cohort's note is a `noun` that counts
  nothing and its size is asked for live; a kept **line** records the revision it was kept at.
  The search hit was in the plan on evidence: `goToCode(path, line)` already existed, which is
  the third item in two days recorded as blocked and found not to be.*
- ~~**`holds` is not in `insp`'s defaults.**~~ *Fixed 2026-09-08, and it was **three** keys
  rather than one — `holds` (a fold's contents and a plate's), `stands` (what a merged plate
  stands for) and `calls` (the call sites behind an arrow). Each is the answer its pane
  exists to give rather than a caveat on one it already had, which is the test `loops` and
  `shape` were named under, so all three open. The entry stood for six days as a note about
  one section while two more joined it in silence, which is what a guard is for:
  `test_every_inspector_section_declares_its_default` reads the `sec("…")` keys out of the
  shell and requires each to be named in the settings.*
- ~~**`navIds` splits `data-navid` on a space.**~~ *Fixed 2026-09-08, and the fix is not the
  one the entry implied. A separator no name can contain — a control character — gives up the
  one thing the space was chosen for, an attribute a person can read when something goes
  wrong. Instead the **row declares** whether it holds several: `data-navmulti`, written by
  the single producer that joins any (the ways-in rows, whose ids are digests), and a single
  id comes back whole whatever characters it holds.*
- ~~**The blank-graph fix (rule 49) is reasoned and guarded, never *seen*.**~~ *Seen
  2026-09-06. The premise was false: the graph **does** mount in the automation tab —
  `canvas MISSING` was a read taken while the pane still said "reading the stack…". Four
  seconds later there is a canvas, 10,015 nodes and 53 plates, and WebGL was available all
  along. `Snap to fit` pressed with the pointer framed the selection to the real 621×333
  canvas.*
- **A known-standards directory, to compare reality against intent.** Tom, 2026-09-04:
  *"I am interested in creating a known standards directory as a baseline against which to
  compare what is really found. The goal is to show reality, not the plan."* The wording
  change of that date is the honest stopgap, not the feature. What was found while surveying
  it, all measured on Mensores:

  - **Ingest exists and is narrow.** `_maybe_rule()` mines `doc_rules` during the ordinary
    docs scan — `lane`, `scope`, `pattern`, `checkable` all in the schema already. Gated to
    six rule-bearing classes on evidence (a research paper *about* naming standards yielded
    ten confident false FORM rules). There is **no import gesture**: `--docs` takes one root
    and replaces the default, so an outside standards directory cannot be added to a scan.
  - **Yield: 5 rules, from 1 of 29 rule-bearing documents.** All VOCABULARY, all
    `checkable = 0`. **Zero FORM rules across the whole corpus**, so the checkable machinery
    has never had an input.
  - **Nothing compares.** `checkable` is read by one thing: a sentence in the report saying
    whether it is checkable. `scope` and `pattern` are stored and consumed by nothing.
  - **The best standard in the corpus is a table, and the detector cannot see it.**
    `harness/rules/style.md:30`, heading "Naming Conventions", header
    `Type | Convention | Example`, **seven rows** — Files kebab-case, Commands
    `paul:kebab-case`, Step names snake_case, Bash variables CAPS_UNDERSCORES, Type
    attributes colon separator, Phase directories `NN-kebab-name`, Plan files
    `NN-NN-PLAN.md`. Every row is a `scope` and a `pattern`, which is exactly the pair the
    FORM lane needs. The table **is fully captured** in `doc_tables`/`doc_table_rows`; the
    rule detector returns on `text.startswith("|")` at `markdown.py:468` and never sees it.
    A table is how most enterprises write a naming standard.
  - **The scoping mechanism is already in the store and read by nothing.**
    `harness/rules/style.md` carries frontmatter `paths: ['src/**/*.md']`, and **62 documents
    in this corpus carry a `paths`, `area` or `applies_to` key** — captured in
    `documents.frontmatter`. That is the "only some parts are relevant" half, present and
    unused. `Society-Specs/01-naming-standards.md` is Society's own spec asking for exactly
    this: *"a naming standard directory that contains multiple documents, each of which
    identifies one or more subsystems."*

  Order, cheapest and highest-value first: ~~**(1)** read a table as rules~~ — *built
  2026-09-04, see the record: 0 FORM rules became 7, and one table of 5,230 fires*;
  ~~**(2)** serve the stated lane to the dashboard~~ — *built 2026-09-05, and it is two pages
  rather than one section: see the top of this file. `scope` and `pattern` reach a screen for
  the first time, and the three ways a program can state nothing each got their own sentence*;
  ~~**(3)** compare a checkable rule against the graph~~ and ~~**(4)** `--standards <dir>`~~ —
  *both built 2026-09-06, and **in that reversed order, on evidence**. Step 3 as written would
  have made the tool confidently wrong: none of the six checkable rules is a question about
  `graph.db`, and checked against it "Files: kebab-case" scores 0 of 628 Python files for a
  rule its own document scopes to three markdown files. The population is now never inferred
  from the scope word. See the top of this file.*

  *Also corrected here: this list said **62 documents carry a `paths`, `area` or
  `applies_to` key**. By key rather than by substring it is `paths` **5**, `applies_to` **4**,
  `area` **8** — and only `harness/rules/style.md` carries both a scope and any rules.*
- **`m.<module>` as a language feature, with research owed on prior art** — how other tools
  present a construct the *language* put there rather than an author. Decided 2026-08-30:
  not filtered and not bare, but a curiosity carrying its own explanation, scoped to the
  language that produced it rather than special-cased in the diff.
- ~~**The worklist's two jump buttons are half done.**~~ *Built 2026-09-06. It was less
  blocked than recorded: every detector already selected rows identifying its occurrences and
  threw the identity away, keeping the names as prose in `detail` — rule 41. `Anomaly` now
  carries `occurrences` (each naming a route `NAV_ROUTES` already has, so nothing translates)
  and `unenumerated` for a finding that can list nothing. All 107 of Mensores' findings
  enumerate; `LOST_EDGE` opens its **call sites**, because the callee not resolving is the
  finding and opening a rival would be rule 5's guess dressed as a destination.*
- **Per-plate sphere scaling, and stack orientation** — carried in `HANDOFF`'s list and
  missing from this one until the 2026-09-02 audit. The second is structural: `OrbitView`
  has no camera roll.
- ~~**The two vocabulary-lane precision defects.**~~ *Both fixed 2026-09-08 — see the top of
  this file. A DASH_GLOSS mined out of a constraint table is no longer counted as a
  definition (5 refused of 240, all constraints), and the undefined list's head is words
  again rather than the tails of SCREAMING_SNAKE constant names (1,154 → 265, with 890 held
  back, listed, and each one offered back to the worklist by hand).*
- The filed small things: the rendered markdown is not revision-named, `--revision` on
  `analyze` (it exists on `serve` only), the navigator's search box pinned-when-open
  (decided 2026-08-30, never built), packaging as a binary.

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
