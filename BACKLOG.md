# Backlog

**What this tree knows it owes, in one place.** The fourteen chunks of v2's design plan are
all done, so nothing here is scheduled by the plan — every item is something a chunk found,
stated, and deliberately did not do. Until 2026-09-17 they lived scattered across the
development record's *What is next* and a dozen **Residue** sections, which meant the only
way to know what was outstanding was to read the whole record.

**Every item says where it came from, why it was not done, and what would settle it.** An
item with no *what would settle it* is a complaint rather than a task, and an item whose
*why not* is missing is one somebody will redo the argument for.

**This file is not the record.** The development record, kept outside this repository, says
what happened and when; this says what has not. When an item is done it leaves here and the record keeps it.

---

## Open

### 1 · The tutorial's 21 screenshots

*From chunk 14, 2026-09-17.*

`docs/tutorial/` carries the figures of one session — DunneFlow reading itself at
`1e76c51` on 15 September 2026 — against a tree that has gone from **78 files and 925
routines to 118 and 1,283**. Chapter 10 was rewritten because it changed *shape* rather
than size (fifteen naming conventions where its screenshot shows seven, most naming a
language); the other twelve chapters carry that afternoon's numbers.

**Why not done.** Tom's call. The captures are hand-composed 1483×812 images and the
session could not drive a browser, and a chapter cannot be half-retaken — the images are
the evidence. `docs/tutorial/README.md` now says plainly what the reader is looking at,
which is the honest interim state rather than a silent one.

**And one more figure went stale on 2026-09-18.** The `CLAUDE.md` split added four `.md`
files at the root, so `docs/tutorial/06-document.md`'s *"26 documents carrying 29
definitions and 45 governance ids"* — DunneFlow's own count of its own corpus — is now
wrong by construction. Same remedy, same session.

**The capture path, probed 2026-10-02, and it works.** What was missing was never the
window size. It was whether the automation tab was the **active, highlighted tab** of a
window in front. In the background the page reported `outerWidth` 0 and
`visibilityState: hidden`, ignored `resize_window`, and its screenshot covered only the
top-left of the viewport, which is the clipping the 2026-09-15 session hit. With Tom sizing
the window first and highlighting the tab, the same page reported `visible` at 1,920×919
CSS, the screenshot held all four edges, and clicks landed where they were aimed (two
probes, both within a pixel). **And once the tab is active, `resize_window` works too**,
in device pixels: on Tom's display (`devicePixelRatio` 2, 89 CSS px of browser chrome),
`resize_window(2966, 1802)` gave a viewport of exactly **1,483×812**, the old images' framing.

**What the recipe has to carry.** At that size the screenshot frame is 1,482×812, so one
capture at `scale: 1` is already 1:1 with the old images. Anything wider is scaled down to
1,568 across, and there four quadrant `zoom` calls stitched with Pillow give the viewport at
twice the resolution (3,136×1,500 from a 1,920×919 window), seamlessly. A `zoom` region is
checked against the viewport in CSS pixels after scaling, so its bottom edge has to stop one
pixel short. The pointer is drawn into the capture, so it is parked off the subject before
every shot. Headless Chrome also gives a full frame with WebGL2 on Metal, but it photographs
a page as loaded and nothing more, so it is the fallback rather than the route.

**And the map is gone.** Neither `output/dunneflow` nor the sealed `875499c` snapshot
survives, so chapters 1–7 cannot be retaken against the afternoon they describe. Both
commits are still in the history, so the pair can be rebuilt from worktrees. Chapter 8's
story, *what did the Linux work change*, is exactly `875499c` → `1e76c51`; held against
`HEAD` instead, the same pair would be fifty-eight commits and a second language. Which pair
the chapter tells is Tom's call.

**What would settle it.** A session doing prose and images together: a fresh self-analysis,
the 21 shots re-composed with Tom's window and tab set up as above, and every figure and
alt-text transcription rewritten against them.

### 3 · The rendered map still varies with `--jobs` in one respect

*From the ordering fix, 2026-09-17.*

Not a defect and stated so it is not rediscovered as one: `trace_flow` is breadth-first and
`max_nodes` truncates it, so **which** routines a flow diagram draws is decided by the
order the walk reaches them. That order is now total and content-derived (`ORDER BY
caller_id, callee_id`), so it is identical run to run and build to build — but it is not
the order a reader would choose, and the same is true of the six commands
`command_tree_diagram` draws per node.

**What would settle it.** Deciding what a *good* truncation is — widest reach? shallowest?
alphabetical? — which is a product question rather than a correctness one. Until then the
answer is reproducible and arbitrary, which is rule 66's floor and not its ceiling.

### 4 · `fetch` through a name

*From chunk 10, 2026-09-17. Searched for a corpus 2026-09-18.*

A boundary that a spelling rule cannot reach because the call goes through a local
binding. The mechanism exists — the TypeScript checker can say what a name holds — and
chunk 11 used it for package-resolved boundaries.

**Why not done. Still no population, and now that is measured rather than assumed.** Tom's
call was to search the Developer directory for open-source trees that might supply one.
Every `.ts`/`.tsx`/`.js`/`.jsx`/`.mjs` file in it outside `node_modules`, builds and
virtualenvs was scanned for `fetch` bound to a name — `const x = fetch`, `= window.fetch`,
`typeof fetch`, `fetch.bind(`, `fetchFn`/`fetchImpl`/`fetchClient`, `this.fetch =`. **One
hit in the whole tree**, `gstack-main/browse/test/security-sidepanel-dom.test.ts:92`:
`const origFetch = window.fetch;` — in a test file, which `DiscoveryRules.is_test` excludes
from program source by design.

Of the thirteen JavaScript projects there, exactly two call `fetch` at all in program code:
DunneNote once, and `gstack-main` **35 times across 21 files** — every one of them spelled
`fetch`. So the shape is real in principle and is not in this corpus of corpora, and
guessing at it would be building a feature against no ground truth (rule 24).

**What would settle it.** A corpus that calls `fetch` through a name. `gstack-main` is
now analysed as `gstack` and is the corpus to re-test against if one is ever found — it is
the only tree to hand with a real `fetch` population, and the tool scores **29 of 29** on
it with no false positives, so the direct case needs nothing.

### 12 · An `analyze` with no `--part-of` still climbs without a ceiling

*From rule 108, 2026-09-20.*

`--part-of` bounds the climb for a part. A plain `analyze <some/subdirectory>` has no tree
to be bounded by and still walks its ancestors to `/`, looking for any of six filenames, and
takes the document root and the tree's name from wherever it lands.

**Why not done.** Nothing in those arguments says where to stop, and every candidate
stopping condition is a guess: the git root is a guess (a tree need not be under one, and a
monorepo's root is not a program), the first directory holding no manifest is a guess, and a
depth limit is the worst of the three. Inventing one would be a rule with no evidence behind
it, which is what rule 24 is about.

**What would settle it.** Either a measurement that says how far real trees' package roots
actually sit above their source — which the corpora here could answer — or the honest
alternative, which is to **say what it did**: a run that took its documentation root from
four levels up should print that, and today it prints nothing at all. The second is small and
is design rule 1's shape.

### 8 · A map of 262,879 routines takes 27.6 minutes to open

*From the Unreal ingest, 2026-09-20.*

`/api/program` on `Engine.Source.Runtime` reports `done` after **1,659,334 ms**, most of it in
*the 2.5D model and its payload*. Every route then answers 200 and the cover is right — it
works, at a speed that makes it unusable. Design rule 45's bargain is that the bound on this
work is *a reader opening one thing*; at 18,191 files that bound is no longer a bound.

**The instrument exists now** (2026-09-20). `web.serve._Clock` times all six steps and
sub-times the five things step 1 conflates — reading the graph into a model, laying it out,
transposing it into the payload, and the root package — and `serve` prints each as it ends.
`/api/base` carries the table as `spent`.

**And the first reading of it contradicts the sentence above.** On `Engine.Plugins.AI` —
331 files, so not this part — the six steps came out **2.3 s · 0.5 s · 0.0 s · 48.4 s ·
2.2 s · 0.8 s** of 54.0 s: *the naming standard, stated and derived* is 90% of it and *the
2.5D model and its payload* is under a second. That is one part and not the one this item is
about, so it settles nothing here; it is recorded because it is the first evidence of any
kind, and because it points somewhere other than where the last progress line does. Rule 39
exactly.

**Why not done.** `Engine.Source.Runtime` has not been opened with the instrument. It is a
~28-minute measurement and the machine has been reading Unreal all session.

**What would settle it.** Opening that part with the six timings, and separately timing the
first `/api/graph` — `json.dumps` of the whole payload runs per request, uncached, and is
**not** inside the 1,659,334 ms, so whatever it costs at 262,879 routines is a second figure
nobody has taken. Then deciding whether the answer is a bound on the payload, a lazier
build, or a refusal that says a map this large opens in the documents and not in the graph.

### 9 · The documents of a part are not bounded the way its code is

*From the Unreal ingest, 2026-09-20. Reshaped the same day — the original item was "a part of
fifteen files costs two hundred seconds", and the two causes it was looking for were found.*

`analyze --timings` prints what every phase cost, and `--progress-json` carries `ms`. With
it, the original item split into two answered halves and one that is left:

* **Answered — the document root was outside the tree.** **Rule 108**, now item 11: the
  document walk read every project on the machine, about 205 s a part over 85 parts, which
  is most of a 327-minute run.
* **Answered — one judgement made three times.** `detect` ran for `09-anomalies.md`, again
  inside `_overview` for the headline that points at it, and a third time for `analyze`'s own
  step. On `Engine/Binaries` writing the map was **855.6 s** and the anomalies **306.4 s** —
  **94.8% of a 1,226.6 s run**. `render_all` takes the report now.
* **Left, and the whole-tree re-read on 2026-09-20 measured how much of it there is.** A
  part's *documents* are still whatever is physically under its root, where its *code* is
  what a reader admits. Across all 86 parts the tree now holds **12,886 documents — and
  11,850 of them are `Engine.Source.ThirdParty`'s**, a part of 620 code files sitting on
  57,373 files of vendored library source. Every other part in Unreal is in double or
  single figures. So this is not a general property of parts; it is one directory, and the
  question is whether vendored third-party prose is documentation of the program.

**Why not done.** Because it is not obviously wrong. Those documents really are in that
directory, and design rule 11 says documentation and source are equal inputs — a reader's
`skip_dirs` is a statement about what is *program source*, and nothing has ever said it is a
statement about prose. Applying one reader's skip list to documents would also be a
per-language rule applied to a thing that has no language.

**What would settle it.** Deciding what a part's documentation *is*. The measurement that
was wanted has been taken and it narrows the question rather than answering it: 92% of the
tree's documents are under one directory that the C++ reader skips by name for code. Until
somebody decides whether that is evidence about Unreal, the number is what it is and is now
visible, which it was not.

### 5 · Rule 95's general remedy

*From chunk 6, 2026-09-17.*

Rule 95 is *a cache key assembled from a directory does not cover what that directory
imports*. `sql.py` joined the core key, which shut the specific gap the rule was minted
from. **The general remedy — deriving the key from the import graph rather than from a
list of directories — is not built**, and a rule is never closed.

**What would settle it.** Either building it, or recording the measurement that says the
hand-kept list is sufficient and why.

---

### 13 · `/api/table?name=annotations` follows the order its rows are stored in

*From the ordering gate run for the Windows fixes, 2026-10-01.*

`tools/ordering.py --api` on a fresh map of DunneFlow's own `src` reports one route that is
not the same under a full row reversal. Two of the `annotations` table's SQL operations,
`CREATE TABLE` and `CREATE INDEX`, swap places, and nothing else moves. It is the same at
`a877bd3`, before that session's changes, so it was not introduced there. The document
probe is clean on the same map.

The two rows almost certainly share every sort key `_r_table` orders by, so the tie falls
to storage order (rule 66). Each answer is true, but the order is not one the tool can
defend.

**What would settle it.** Add a final, total tie-break to the query behind `_r_table`'s
operations, such as the operation's file, line and kind. Then show the reversal probe clean
on that route.

### 14 · A dataclass in this program is called EXTERNAL, once per call site

*Found photographing the tutorial, 2026-10-02 (retake defect 5).*

`resolve.entrypoints.binding_note` lists `BindingNote` as EXTERNAL six times in OUT 13.
`BindingNote` is a dataclass in the same module. A call to a class with no `__init__` of
its own resolves to no routine, so it falls through to external, which is not where it
lives. OUT also counts call sites rather than callees and does not say so (rule 32).

**Why not done.** Resolving a constructor to its structure changes `calls.resolved`, which
moves the Society golden. It is a resolver change with a re-baseline, not a fix to make in
a documentation pass.

**What would settle it.** A call to a class this map holds resolves to that structure, with
a confidence. The inspector either says "sites" or groups by callee. Society is
re-baselined, and the move in `calls.resolved` is explained.

### 15 · The graph can arrive framed for a size it no longer has

*Retake defect 8.*

Coming from Shape to Graph with a selection held, the stack drew as a thin row of dots
behind the panels until **snap to fit** was pressed. `fitView` defers a fit when the
container measures 0×0, but a fit taken at a transitional, non-zero size is kept.

**What would settle it.** The engine keeps a fit nobody has moved since as a fit across
container resizes, as the diagram now does (`dgmFitWhole`). It is reproduced first by
measuring the container at mount.

### 16 · Document opens scrolled past the selection

*Retake defect 14.*

Selecting a routine and switching to Document opened the Routines document about 25 wheel
ticks below the selected row, which was highlighted but off screen. **Go to it** lands
correctly. The likely cause is a scroll taken before the tables above had laid out
(rule 73).

**What would settle it.** The opening scroll is the same call **Go to it** makes, run after
layout.

### 17 · Hiding then re-dimming unselected nodes loses the lit colouring

*Retake defect 26.*

With `binding_note` selected, setting Plates › unselected to *hidden* and then back to
*dimmed* drew the nine lit nodes grey, like the dimmed ones; only the links still showed
the selection. Rule 68's shape: a restore is a setter.

**What would settle it.** Going back to *dimmed* re-applies the lit colouring the way
selecting does, with a test over the engine's colour buffer.

### 18 · Counts beside each other that do not say what they count

*Retake defects 6, 7, 10, 23, 32 and 39, each with its screenshot in the record.*

- **BOUNDARIES:** the search note says "the nine kinds" while the group lists seven.
- **SHAPE:** the inspector says "1 thing moves inside them" when its one boundary is
  outside both loops.
- **Overview:** the system-boundaries column (NETWORK 2, DATABASE 204) disagrees with the
  cover (3, 287).
- **Documents:** the glossary says "52 documents" and the stated-rules page "53".
- **Changes:** the CHANGES group's 49 does not equal its parts.
- **Cold open:** `/api/revisions` waits behind the page's other requests on a cold open.

Each may be two true numbers about two populations. Rule 32 asks that each say which.

**What would settle it.** Each pair is checked against its query, and is either reworded
to name its population or fixed.

### 19 · At 1,483 px with both panes open, the centre is too narrow for three of its views

*Retake defects 9, 11, 12 and 37.*

- **Graph:** the slider and plate panels cover the stack.
- **Table:** CONNECTIONS and CHANGED are off to the right, and the header clips to
  "CONNECTIO".
- **Algorithms:** the lane tabs run off the edge.

**What would settle it.** A judgement on the panes' default widths at a 1,440–1,500 px
window (design rule 53), measured, not guessed.

---

## Stated residues — known, bounded, and not defects

These are not tasks. They are places where the honest answer is a limitation, recorded so
that nobody spends a session rediscovering them and filing them as bugs.

| | |
|---|---|
| **`node` is needed to verify the TypeScript stamp** | `tools/fingerprints.py` reads the stamp out of a map the binary *wrote*, which is what proves the stamp labels rows rather than merely being computable (rule 37). A machine without node gets a refusal naming it. Chunk 13. |
| **`GOLDEN-v1.txt` redefines two of its seven digests, and is history now** | `routines.body` and `calls.resolved` record values whose v1 statement was never written down and was not recovered by a bounded sweep (rule 24, chunk 0). It stopped mattering on 2026-09-19: rule 106 moved all five of the digests that *did* reproduce, so the live baseline is `output/GOLDEN-v2.txt`, `tools/golden.py` wrote both sides of that comparison, and it is **7 of 7** with no holdbacks. The v1 report is kept as a dated record and compares for five, all of which now move. |
| **DunneCorp's routines are two conventions by role** | PascalCase 88 against camelCase 79 — React components against ordinary functions. A language split does not touch it, and it stays a reported gap because that is the true answer. Open question 6. |
| **DunneNote's modules stay a gap** | kebab 221, other 210. That tree really does spell module files three ways. Open question 6. |
| **Next.js route segments read as `other`** | `app.(admin).admin.customers.[id].page`. Route syntax is not an identifier and stripping it would be guessing at a spelling. Open question 6. |
| **Python's leading-underscore classes drag PascalCase to a `D`** | `_Base` and `Exception_`, 15 of DunneFlow's 164. A pre-existing question about what PascalCase means with an affixed underscore; not a language question, and left alone deliberately rather than folded into a chunk about something else. Open question 6. |
| **A Linux session cannot run the recorded ground truth** | None of the four Society clones nor `../dunnecorp-standards` is on that machine, so no figure in `CLAUDE.md` was retaken there. Do not restate a Mensores figure measured elsewhere as though it had been reproduced (rule 24). |
| **A program that serves browser JavaScript as a string has calls this map cannot see** | `gstack`'s `getCookiePickerHTML(): string` returns an HTML page holding four `fetch` calls, and `design/src/compare.ts` another. Those requests really are made — from the browser, by code this program wrote — and the map says nothing about them. Correctly: a string is not code, which is rule 9's argument one direction over, and reading one would mean parsing every template literal in every language. Stated so the NETWORK count is read as *what this program calls*, never *what this program causes*. 2026-09-18. |
| **`socket.emit` may be wrongly declared async** | `detectors/typescript.yaml` says `async: true`; `emit` is fire-and-forget in socket.io and `emitWithAck` is the awaitable one, so it is probably wrong beside `WebSocket` and `EventSource`, which were corrected. Left alone because **no map this tool has read holds a single `socket.emit`** and socket.io's types are in no corpus here, so there is nothing to check a change against. Asserting it from memory is what rule 24 forbids. 2026-09-18. |
| **Rule 105's survey is a floor, not the population** | `tools/ordering.py --survey` lists the five `sorted()` calls whose input is *written as* a set and which take a `key=`. Unorderedness propagates, so a dict built by iterating a set and then sorted over its `.items()` is the same defect and is invisible to it — `web/changes.py` held two of each, and only the two written as set algebra are in the count. Catching the rest means following the provenance of a value, which is a different instrument. The reversal probe cannot see any of them. 2026-09-18. |
| **A killed analysis can leave its pool behind** | Nine `ProcessPoolExecutor` workers from the original Unreal ingest were still alive 22 hours later, parented to init, idle at 5.5 MB each. Harmless where they are, and the 86-part re-read on 2026-09-20 added none — so it is an interrupted run's leak rather than an ordinary one's. Stated because a batch runner doing this nightly would accumulate them, and the batch-ingest design is the place that would have to care. 2026-09-20. |
| **The size guard counts files and nothing else** | `walk.TOO_BIG` is 20,000 *files*, which is the shape of the evidence — `Engine/Source/Runtime` is 18,191 and is the largest tree read end to end. A tree of 19,000 enormous files passes it and a tree of 25,000 tiny ones is refused, and neither is what the bound is really about: the thing that hurts is rows written, not files read. Bytes or an estimate of rows would be the honest key, and taking one needs a corpus spread wide enough to separate the two — which is a measurement, not an edit. Stated so the number is read as what it is. 2026-09-19. |
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
