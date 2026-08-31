# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. Built for a reader who reads code but does not write it, and who thinks in
entrypoints, flows, routines, and boundaries.

**New here? Read `BRIEFING.md` first** — where the code lives, what is built, what we are
doing now, and which decisions are closed. This file is the rules; `HANDOFF.md` is the
chronological record.

## What this tool is for

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back out.
**What moves is the subject. Internal computation is not.**

Deliberately *not* reported: local variables, arithmetic, control flow, and private
helpers that neither touch a boundary nor sit on a path to one. Leaving those out is
most of what makes the output readable — do not "improve" the tool by adding them.

The goal is **comprehension, not documentation**. Judge a change by whether it helps
someone orient in an unfamiliar codebase, not by how many pages it emits.

## Commands

```bash
uv run dunneflow analyze  <path> --name <program>   # extract, resolve, write the map
uv run dunneflow touches  <path> --routine <name>   # what does this reach?
uv run dunneflow impact   <path> --routine <name>   # what breaks if I change it?
uv run dunneflow glossary <path>                    # what its words mean, and who says so
uv run dunneflow naming   <path>                    # the naming standard, stated and measured
uv run dunneflow mirror   <path>                    # words the docs define that the code never uses
uv run dunneflow query    <path> --sql "..."        # ask the graph directly
uv run dunneflow migrate  <dir>                     # stored paths: absolute -> relative
uv run dunneflow serve    <dir> [--revision <rev>]  # the dashboard, on one version
```

`serve --revision` chooses which point in time the server opens as the **base** -- the
version the cover, the routine list, the code browser, the glossary and the stack all
show. It defaults to the newest. The reader can switch it from the toolbar, and that
switch survives a page reload; this is how it survives a restart of the server, because
the base is the server's state and not the browser's.

`GET /api/graph` takes `?level=routine|module` and `?minDisk=<n>` — the stack's **level of
detail** and how few things a plate may hold before it is merged into `<small>`. An unknown
level is refused with a 400 rather than defaulted, because a silent fallback answers a
question nobody asked with a picture that looks exactly right; the threshold is clamped
instead, because the two are different mistakes. On screen it is the *Detail* control in
the legend, which states what the altitude costs: what is drawn, what it stands for, and
what the threshold merged.

`migrate` rewrites a program directory written before paths were relative (rule 60), **in
place** — 115,546 paths across five stores in 1.2 s on Mensores. In place rather than by
re-analysis, because a sealed snapshot exists to be readable after its source tree is
gone and rebuilding would orphan exactly those. A reader refuses an unmigrated store and
names this command; it never repairs one on the way past (rule 20).

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`).

The dashboard also searches the **text** of the source — `/api/search`, the Code group's
box. That is a different question from `touches`, `impact` and the glossary, which search
names and meanings: this finds a word inside a comment, inside a string literal, or on a
line that carries neither.

`analyze` is incremental: unchanged files are not re-parsed.

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then verify against real code, because unit tests on a toy program cannot catch a
resolution defect that only appears at scale:

```bash
uv run dunneflow analyze ../mensores-overhaul/src --name mensores
```

**`../mensores-overhaul` is read-only.** It is a copy kept for documentation. Never
write to it. All output belongs in `output/`.

Ground truth for documentation: the pantheon table in
`.groma/milestones/v1.1-harness-ownership/NAMING.md` yields `groma`, `disceptator`,
`quaestor` and the rest with their Latin glosses; its three BINDING rules appear in the
**Vocabulary** lane, quoted whole; `.groma/PROJECT.md` and `docs/reference/glossary.md`
both define `mensor` from *mētior*. And the precision half, which matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about*
building a naming-standards importer, and must yield **zero** naming rules. If it yields
any, the detector is wrong, not the corpus.

Ground truth for code: the four executables declared in its
`pyproject.toml [project.scripts]` — `mensores`, `mensores-mcp`, `mensores-signator`,
`mensores-scriba` — must all appear in "Where to start" with plausible reach. If one
collapses to a reach of 1 or 2, a registration idiom is being missed.

### Performance budget (measured on mensores: 623 files, 184k lines)

| Measure | Budget |
|---|---|
| Cold full analysis | < 90 s |
| Warm re-analysis, nothing changed | < 5 s |
| Orientation query (touches / impact) | < 1 s |
| Peak memory | < 1 GB, flat as file count grows |

The interactive map (`dunneflow serve`), measured on Mensores: 52 disks, largest 959,
**9,874 nodes drawn**, 13,935 edges in the model, plus 5,727 shadows that are *never*
drawn — they are placement devices only (rule 23). An earlier version of this table read
"14,991 drawn" by counting the shadows; that number was already wrong when shadows stopped
being drawn, and it overstated the picture by half.

| Measure | Budget | Measured 2026-08-27, Apple M1 / Chrome Metal |
|---|---|---|
| Payload build, server side | < 2 s | ~0.03 s |
| First paint in the browser | < 2 s | 0.1 s |
| Sustained fps, six-second orbit, dots | >= 55 median | **60 median, 60 worst — no frames dropped** |
| …spheres at full size (14×) | >= 55 median | **60 median, 59.7 worst — retaken 2026-08-28** |
| …spheres at 14× plus 4,253 edges | >= 55 median | **60 median, 59.9 worst — retaken 2026-08-28** |

The second **level of detail**, measured 2026-08-31 on the same corpus. A module payload is
578 nodes and 1,505 connections against 10,015 and 14,254, and 0.53 MB against 4.89 MB:

| Measure | Budget | Measured 2026-08-31 |
|---|---|---|
| Module payload build, server side | < 2 s | 0.09 s |
| …a threshold nobody has asked for yet | < 2 s | 0.10 s round trip |
| …the same again, cached on the base | < 50 ms | 10 ms |
| First paint at module level | < 2 s | **not measured — see below** |

**The build is cheap and it is held per level *and per threshold*, on `_Base`**, so a base
switch throws all of it away for free. The routine payload is still built at boot, so the
10.2 s start does not move; a level nobody climbs to costs nothing at all.

**First paint at module level is absent rather than estimated, and so is the frame rate.**
Rule 38: a browser-automation tab is given no animation frames — the HUD reads **0 fps** in
one — so anything needing a rendered frame does not exist there. The counts, the controls,
the selection that travels between altitudes, the change key and the colour buffer were all
driven and checked in that tab; the picture wants a real window. There is no reason to
expect it slower than the routine level, which is the point: it is a seventeenth of the
nodes and a seventh of the edges. That is a prediction, not a measurement, and it is
written here as one.

**The two sphere rows were withdrawn and are now retaken, with the shading confirmed
running by eye before either was recorded.** They had been withdrawn rather than left
stale because the sphere shading was not executing when they were first taken: three
separate silent no-ops kept the fragment work from ever happening — an inject hook deck.gl
did not recognise, a GLSL local colliding with one of its own, and a shader that was never
reassembled because deck.gl resolves an extension's shader once per extension class. Every
one of them compiles and draws. Those runs measured flat discs while the readout printed
the word *spheres*, which is rule 24 exactly.

**Both retaken rows state their canvas and their framing, because the first pair did not
and that is what made them impossible to reproduce.** Canvas **2652×1537 device pixels**
(1326×768 CSS at dpr 2), framed with **snap to fit** at the tilt in force. Both matter and
neither is incidental: sphere shading is per-fragment work, so the same 14× nodes in a
1072×251 pane and in a full window are not the same measurement, and a stack that sits
small in the frame covers few fragments however large the canvas is. An early attempt this
session ran at 4.08M canvas pixels with the stack occupying a fraction of them — a bigger
number measuring the same little picture. Retaking without reproducing both is a different
measurement under the same label, exactly as with the plate selection below.

Read with the caveat that at 14× the nodes fuse into a solid mass and occlude the edges
they are drawn with: the frame is honest about cost and is not a picture anyone would read.
That is the case for independent X and Y spread, not against the measurement.

The dots row stands: nothing about it depended on the shading.

Kept because the *method* survives even though the numbers did not. The edge run could not
have been taken at all before the second session: the orbit set the moving flag, which
stripped the edges, so the benchmark measured nodes only while printing an edge count beside
the number (rule 24). Its selection is eight plates — `disceptator`, `STDIO`, `quaestor`,
`_internal`, `storage`, `cli`, `governance`, `DATABASE` — giving 2,199 within-plate links
and 2,054 crossings, with both layers confirmed present in the frame. Reproduce that
selection when retaking the row, or it is a different measurement wearing the same label.

A benchmark now refuses to start on a tab that is not visible. A hidden tab is given **no**
animation frames at all — not throttled, none — so a run started before switching away sits
at "benchmarking…" and then reports a figure averaged over the time nobody was looking.

The sphere threshold (2.2×) is **a judgment, and stays one.** It was briefly recorded as
set by evidence; that claim was withdrawn with the rows it rested on, because the evidence
was a run in which the shading did not execute and so showed only that flat discs are
cheap, which was never in doubt. The rows above are now retaken with the shading confirmed
running — and they still do not set the threshold. They say the shading is affordable at
full size in this framing, which is a different claim: where a *reader* wants a disc to
become a ball is a question about looking, not about cost. Setting it by evidence would
take a measurement of the fused-mass problem, and that measurement does not exist.

60 is the vsync ceiling, so these rows state a floor, not a capacity: nothing was dropped
and the headroom above it is unmeasured. Read it as "never missed a frame", never as a
score. The benchmark says so in the readout for the same reason.

The frame rate is bought by two decisions and both are load-bearing. Everything drawn is
uploaded once as flat typed arrays — with per-object accessors, fifteen thousand nodes
means fifteen thousand function calls per attribute per update, and the budget is gone
before anything is drawn. And the `data` wrappers are built once rather than inside the
per-frame layer function, which would re-upload half a megabyte on every frame of a drag
and reintroduce the exact cost the typed arrays exist to avoid.

Opening the dashboard (`dunneflow serve`) on an analysed program, 10.2 s to first serve,
of which the two vocabulary lanes are 2.5 s:

| Measure | Budget | Measured 2026-08-28 |
|---|---|---|
| `serve` start to first request | < 15 s | 10.2 s |
| …of which the naming pass | | 0.4 s |
| …of which the glossary pass | | 2.1 s |

**Switching the base pays that start again**, because one payload set is live at a time.
Measured 2026-08-30 on Mensores' two revisions, six steps reported by name as they run:

| Measure | Budget | Measured 2026-08-30 |
|---|---|---|
| Switch to a version whose stores are warm | < 15 s | 1.2 s · 2.1 s · 3.0 s |
| …the same, cold on the external volume | < 60 s | **35 s** |

**The cold figure is the disk and nothing else** — the other revision's 148 MB document
store and 31 MB graph, never touched this session. It is the same caveat the change
worklist's cold row carries, and it is why the overlay names the step it is on rather than
showing a bar alone: a reader waiting thirty-five seconds is owed *the glossary* rather
than a claim that something is happening.

Two things make the wait cost other requests nothing. The new base is built **outside** the
lock and committed inside it, so only the commit blocks a reader; and the progress lives
behind its own lock, because a poll that queued behind the rebuild would report nothing
until there was nothing left to report.

The two lanes' **bodies** are fetched when their page is opened — 44 KB and 190 KB — while
their sizes ride with the cover, because the navigator states a count beside every other row
and a blank there reads as *nothing here*. Measured on the glossary, 1,207 words with 60
defined and 1,147 not:

| Measure | Budget | Measured 2026-08-28 |
|---|---|---|
| Full page render | < 100 ms | 51 ms |
| One keystroke in the term filter | < 30 ms | 9 ms |

The filter was **412 ms** per keystroke until it stopped calling `render()`, which rewrites
the centre pane, the inspector, the navigator and the trail and then puts the caret back in
the field it has just destroyed. The caret restoration was the tell.

Table mode, all 4,734 routines with no bound (rule 8: a reference list is never bounded):

| Measure | Budget | Measured 2026-08-29 |
|---|---|---|
| Build the whole table | < 100 ms | 46 ms |
| Sort by Connections | < 100 ms | 18 ms |

It was **2,418 ms**, and `Graph.connections` was the whole of it: `indexOfId` walked all
15,601 nodes on every call, so 4,734 rows cost **73.8 million comparisons** — and sorting
asked twice per comparison. Fine for the handful of lookups it was written for and
catastrophic for the caller that arrived later, which is rule 45 in the engine rather than
in a pane. A map built once with the payload is the whole fix. Reported as *lag that is not
obvious*, and that is exactly right: two and a half seconds reads as a slow page, not as a
defect.

The code browser, measured on Mensores' largest file (`mensores/mcp/_server.py`, 5,838
lines, 1.37 MB of markup) and on `mensores/cli/audit.py` (4,820 lines):

| Measure | Budget | Measured 2026-08-29 |
|---|---|---|
| `/api/files`, 626 files | < 200 ms | 23 ms warm, 550 ms cold |
| `/api/file`, largest file | < 100 ms | 53–59 ms |
| Open a file in the pane | < 100 ms | 12–42 ms |
| `buildNav()` with that file open | < 100 ms | 22–56 ms |
| Repaint on a selection | < 100 ms | 30–37 ms |

`buildNav()` was **1,937 ms** and `render()` **1,358 ms**, both on every selection and every
keystroke — worse than the 2,418 ms table defect that earned rule 45, and found by looking
rather than by any test, because a slow page reads as a slow page. The cost was *parsing*:
both rewrite an `innerHTML`, and with a large file open that re-parsed 5,838 lines of markup
per click. The subtree is now built once per file and re-attached, and the centre pane is not
repainted at all when only the selection moved — the highlight is two class changes, 1 ms.

Two things that looked like fixes and were not. `codeCached(slot, codeTable())` evaluates its
argument before the call, so the cache rebuilt the 1.37 MB string on every hit and threw it
away; it takes a builder function now. And re-attaching the built node still costs a full
layout, so `render()` went from 155 ms to 1,370 — the only way not to pay a layout is not to
detach, which is what the paint key is for.

Search inside source, measured on the same corpus — 626 files, 184,722 lines, 7.8 MB of
text held as 3.1 MB of zlib blobs:

| Measure | Budget | Measured 2026-08-29 |
|---|---|---|
| `/api/search`, whole corpus, warm | < 100 ms | 38–102 ms |
| …the same, first search of a session | < 500 ms | **250 ms – 2.2 s, and it is the disk** |
| …as a regular expression | < 150 ms | 87–96 ms |
| One file's hits with their margin | < 200 ms | 95 ms (`_server.py`) · 172–189 ms (268 hits) |
| Paint the 166-file answer | < 100 ms | 16–21 ms |
| Paint 268 hits of one file | < 200 ms | 158 ms |
| The file-name lane, per keystroke | < 30 ms | 3.3 ms |

**The cold row is a disk read and nothing else**, and it is stated as a range because that
is what it is: 250 ms, 780 ms and 2,224 ms on three runs of the same query, varying only by
how much of `source.db` the operating system still had. Warm it is 38–102 ms. The bodies are
held in a bounded inflate cache — 64 MB, keyed by content hash, stated in `sourcedb.py`
rather than pretended away — so a program larger than the bound re-inflates its overflow and
the answer reports how many bodies it read. That is the same external-volume caveat this
file already carries, and it is not a regression.

**Rule 45 does not land on the search.** Scanning all 184,722 lines is 30 ms; the whole
program is 7.8 MB of text and reading it is cheap. It lands entirely on the *answer* —
133,454 hits for `e` is the haystack again — which is why the answer is 626 file rows and
the lines come one file at a time. An index would have been the wrong instinct twice over:
FTS5 is token-based, so it could not find `_emit` inside `self._emit` or a substring of a
string literal, and there was nothing to make faster.

**What is not measured, and why it is absent rather than estimated.** Keystroke-to-answer
wall time, which is the number a reader actually feels. It was measured at 1.4–2.5 s through
a browser-automation tab and thrown away: that tab gets no animation frames, `setTimeout`
is throttled in it, and the same query the tab took 1,965 ms to poll for answered `curl` in
86 ms. Rule 38 — an instrument that cannot see cannot report. The server times above are
taken inside the server with `perf_counter` and stand; the paint times are synchronous
deltas around a DOM write with a forced layout and stand; the round trip between them wants
a real window.

Two things looked like the cost and were not. Per-row `overflow-x` on 268 hit rows makes 268
scroll containers, which is the shape that cost `codeTable` 1,358 ms — and it is 158 ms with
them and 165 ms without, so it is the markup, not the containers. And the whole-word and
regex passes are the same compiled-pattern loop as the literal one, so they cost what the
literal costs plus what the pattern costs, not a second scan.

The first code view of a session costs about a second if the first thing painted is a
five-thousand-line file; painting a small one first makes every subsequent file 12–42 ms.
That is warm-up rather than proportional work — the same file is 40 ms when it is not first —
and it is not attributed further than that.

Both lanes are paid for **at start rather than on first use**, and that is a decision
rather than an accident. A vocabulary thread is part of `/api/threads`, which is asked on
every selection, so a lazy first call would stall the reading loop on the first click of
every session — two seconds where the reader is entitled to think the click failed. Paid at
boot it is invisible, beside a payload build and a cover that were already being computed.

The comparison over the code, on the same pair (628 files against 625):

| Measure | Budget | Measured 2026-08-30 |
|---|---|---|
| `/api/filechanges`, the whole pairing | < 500 ms | 37 ms, and 325 ms cold — it is the disk |
| …the same, cached | < 50 ms | 1 ms |
| One file's lines, the worst in the corpus | < 200 ms | 42 ms (`_server.py`, 5,903 v 5,838) |
| …a file that did not change | < 50 ms | 0.1 ms — answered from the hashes |
| …an ordinary modified file | < 100 ms | 1 ms (`_queue.py`) |

**No body is read to pair 628 files.** `paths(revision, path) -> hash` with one blob per
unique body means an unchanged file holds the *same hash* at both revisions, so two indexed
queries answer "which twelve of these 628 are worth reading". The cold row is the external
volume and nothing else, the same caveat every other cold row here carries.

**`autojunk=False`, and it is measured.** `SequenceMatcher`'s heuristic calls a line
appearing in more than 1% of a sequence longer than 200 lines junk — which in source is
every blank line, every bare `)` and every `return`, so it aligns worst exactly where source
is most repetitive. Across the twelve modified files it is 10 ms with the heuristic and 59 ms
without; and with it, `cli/scribe.py` reports **60 removed lines rather than 57** and
`_migrations.py` 15 rather than 13. Three false removals in one file is not worth 49 ms. Its
guard asserts the *answer* over a 480-line fixture, not the flag — the string `autojunk=False`
is in that module's docstring too, so a grep for it passes over a mutation of the call.

Nothing here is cached per file. The worst file is 42 ms and every body it reads is already
in the sidecar's inflate cache from having been opened; holding the compared version's text
for every file a reader visits would be a second copy of the program in memory to save that.

The change worklist, comparing two revisions of Mensores (4,733 routines against 4,786):

| Measure | Budget | Measured 2026-08-29 |
|---|---|---|
| `/api/changes`, warm | < 500 ms | 317 ms |
| …first comparison of a session | < 5 s | **13 s – 28 s, and it is the disk** |
| …the same, cached | < 50 ms | 1 ms |

**The cold row is the external volume**, reading a 31 MB graph the server has never
touched: 13.1 s, then 2.5 s, then 317 ms on three runs of the same comparison. It was
**84 s** until the diff stopped opening a second read-only handle to a database the
dashboard already holds open — see rule 58, and note that measured standalone it was
242 ms the whole time.

Documentation (2,041 documents on Mensores, 44 MB):

**These were 2,381 and 310 definitions, and the difference is not a change to Society.**
335 of those documents were two stale agent worktrees under `.claude/worktrees/`, holding
a May-era copy of the project's own governance documents under the old `.paul` name. See
rule 57. The duplicate detector caught 303 and every consumer filters `duplicate_of`, so
most recorded numbers were protected; the 32 that had drifted from their originals were
no longer identical, escaped it, and put ten definitions — `mensor`, `mensores` and
`Society of Mensores` among them — into the glossary from a directory that is not the
project.

| Measure | Budget | Measured |
|---|---|---|
| Cold documentation scan | < 20 s | ~18 s |
| Warm re-scan, nothing changed | < 2 s | 0.9 s |

The warm gate is `(mtime, size)`, falling through to the content hash whenever either
differs. Hashing 44 MB off the external volume costs eighteen seconds whether anything
changed or not, which turns re-analysis back into an event. Blind spot: a document
rewritten to exactly its old length with its modification time preserved is missed;
`--recheck-docs` hashes everything.

The machine's source volume is a slow external disk; cold reads cost far more than
warm ones. That is expected and is not a regression.

## Architecture

```
source ──► extract ──► graph.db (SQLite) ──► resolve ──► render
           per file,    the one source                   Markdown + Mermaid
           parallel,     of truth                        ▲
           hash-cached                                   │
docs   ──► extract ──► docs.db  (SQLite) ──────────ATTACH┘
           per file,    a parallel store, never
           parallel,    the same one
           stat-gated
```

- `schema.py` — the fact contract. Every extractor, in any language, emits these types.
- `store.py` — SQLite. **The spine, not an export format.** Nothing holds the whole
  program in memory; reachability is recursive SQL over indexed edges. This is the one
  decision that lets the tool survive growth — do not replace it with in-memory graphs.
- `extractors/python/` — stdlib `ast` + `tokenize` only. No third-party parser.
- `extractors/docs/` — Markdown, reStructuredText and plain text, scanned by hand for
  the same reason: no markdown library. Emits `DocFacts`.
- `docstore.py` — `docs.db`. **Parallel to the graph, never inside it.** A doc rescan
  never touches `graph.db`, code-only analysis stays cheap, and the corpus stays a
  separately handable artifact — many will hand over a charter and never a line of
  source. The join is one `ATTACH DATABASE` away.
- `detectors/*.yaml` — **the extension point.** Teaching the tool a new framework is a
  config edit here, not a code change. Prefer adding a rule over adding a branch.
- `resolve/` — call graph, CLI command trees, flows, naming conventions, glossary.
- `render/` — Markdown and Mermaid.
- `web/layout.py` — where things sit. `DISK_RADIUS` is now the width of the **widest**
  plate rather than of every plate; how wide each one is actually drawn is a *view*
  property owned by the renderer, like Z and the spreads, because `phyllotaxis` is radially
  uniform and scaling a plate's coordinates is exactly computing it at a smaller radius.
  Its old note — every disk one size, density carries the information — is rewritten as the
  reversal it is rather than left standing beside code that contradicts it.
- `web/graph.py` — the 2.5D model, at **two levels of detail**. `routine` is every thing
  the program declares; `module` folds each file into one node and each boundary kind into
  one, on a single plate below the code. 10,015 nodes and 52 plates become 578 and 38, and
  it is a second way to look at the same facts rather than a filter — nothing is dropped
  and every folded node states what it stands for. The fold happens **on the way in from
  the store**, never over `m.edges`, which holds each crossing twice by design (rule 23);
  `packages.py` wrote that warning down before anything needed it. `MIN_DISK` is per level
  and settable, because what a plate *holds* changes with the level.
- `web/threads.py` — **adjacency by interest, not by edge.** Why a neighbour is worth a
  detour: shares a plan, the other end of a table you write, the most commented routine on
  your plate, named like ninety-eight others. Every thread carries a *subject* the router
  can act on, never a label (rule 30), and states its size so the reader can weigh it.
- `static/tokens.css` — every colour, and the three **colour sets**. A set covers the two
  channels where colour separates one meaning from another — a difference, and severity —
  and carries a light and a dark variant; `data-palette` on `:root` chooses one. In CSS
  rather than in a script because `cssPalette()` already reads the stack's colours off
  these tokens, so a second table would be a second answer. Each set states its contrast
  **and** its separation (rule 69). `--graph-unchanged`, `--graph-unclaimed` and
  `--graph-mixed` sit outside the sets on purpose: a set covers the *directions* of
  difference, and a ground — or "more than one direction" — is not one of them.
- `web/vocabulary.py` — the two naming lanes served, and matched against one name. The
  membership test is `Convention.glob`, which is the same string the exceptions query is
  built from, so the claim and the population cannot drift (rule 41).
- `web/filediff.py` — the **text lane** of a comparison, beside `changes.py`'s fact lane.
  The file-level answer costs **no body reads at all**: the sidecar is content-addressed,
  so equal hashes are equal bytes and comparing two path maps *is* the file-level diff.
  That is what makes the expensive lane affordable — `difflib` runs only on a file the
  reader opened, and only where the hashes already say it differs. `autojunk=False`,
  measured rather than preferred (see the budget below).
- `web/search.py` — searching the **text**, which is the one question the graph cannot
  answer: `touches`, `impact` and the glossary search names and meanings, and none of them
  can find a word inside a comment or a string. **Files first** — 626 rows with a count on
  each, never bounded — and one file's lines only when someone opens it, because the margin
  is ten queries a file and a broad word touches 166. One compiled pattern serves both
  passes so the count on a row and the lines beneath it cannot disagree (rule 13). Where a
  hit sits is a line-range lookup, innermost span first; there is no name in the question,
  so rule 5 never arises and rule 10 decides which scope wins.
- `web/code.py` — the code browser. **Links are lookups, never name matches**: `calls`
  already carries `callee_id`, so a clickable name in the source is the resolver's own
  answer. What it does *not* carry is a column, so a call is underlined only where its
  expression occurs exactly once on its line and goes to the margin otherwise — inventing a
  column is inventing a position (rule 1).
- `sourcedb.py` — `WORKING` is a **state**, not an id; a revision is identified by when it
  was captured. `seal()` keeps the current snapshot under its own name so the next capture
  is a second one rather than a replacement. Nothing reads a second revision yet.
- `sql.py` — reads schemas out of the `CREATE TABLE` statements the code contains.

## Rules learned the hard way

These each came from a false result on real code. Keep them.

*There is no engineering rule 21, and nothing is missing.* The numbers are cited from code
comments, tests and `HANDOFF.md`, so they are addresses rather than an ordering and are
never reused or closed up. Every "design rule 21" in the codebase refers to the dashboard
rule of that number — a blank canvas must say why it is blank — which does exist.

1. **Precision beats recall.** A false edge tells the reader something is connected
   when it is not — worse than a missing edge. Every match must be defensible.
2. **A call that touches a boundary is never also an internal edge.** `conn.execute()`
   is sqlite3, not a local routine named `execute`. Ignoring this invented 919 edges.
3. **Builtins never resolve to local routines.** A program defining `list` does not
   make every `list(...)` call a call to it. This invented 261 edges.
4. **Names imported from outside the program stay outside it.** `from dataclasses
   import field` means `field(...)` is theirs.
5. **Never match on a bare common method name.** `create`, `poll`, `get`, `execute`
   are everywhere. Match on a qualified path (`.messages.create`) or a library prefix.
6. **Mark confidence honestly.** `CERTAIN` when pinned by import, module, or class;
   `INFERRED` when resolved by unique name. Never blur them.
7. **Registration is not always a decorator.** Commands are also registered by direct
   call (`app.command(name="x")(fn)`), by argparse `set_defaults(func=...)`, and by
   subclassing (`do_POST`). Each of these was invisible until handled, and each made a
   whole executable look like it did nothing.
8. **Bound every diagram — and only a diagram.** A picture of 4,500 routines is not
   a picture. Abbreviation is allowed *only* where the complete content sits beside
   it: every bounded diagram is followed by a full listing of what it left out.
   Reference lists are never bounded. There is no mandate to save space.
   **Never truncate at ingest** — a value shortened before it reaches the store is
   lost for good rather than merely unshown. `_literal`, comment text, and SQL
   statements are all recorded whole.
9. **Documentation is never code.** Docstrings are excluded from code-shaped
   detectors. `"""Update a field on the org-config"""` is a sentence about a
   statement, not a statement — 248 phantom SQL statements came from reading them.
   Comments are different: they never reach a parser at all. They are tokenized
   separately and attached as metadata, and they are the only source of the
   governance layer. **Never strip comments to "help" a parser** — they are not in
   its way, and removing them would cost the WHY that the whole tool exists to show.
10. **A nested function must carry its enclosing scope in its qualname.** Seven
    closures called `_close_ladybug`, one per factory, are seven routines. Collapsing
    them made every call to any of them ambiguous, and ambiguity loses the edge.
11. **Follow base classes when resolving `self.x`.** Inherited methods are ordinary;
    not following them dropped 113 real edges.

12. **A fenced block is code, not prose — rule 9 in the mirror.** Rule 9 keeps
    docstrings out of code-shaped detectors because a sentence about a statement is not
    a statement. The same argument runs backwards: an example inside a fence is a
    statement, not a sentence, and mining a definition out of one is the same defect
    wearing the opposite uniform. Nothing prose-shaped is ever read from inside a fence.
    The same care applies to markup: `<role>` in `mensores-<role>` is a placeholder, and
    a tag-stripper that eats it has shortened a value at ingest.

13. **A claim's query must return exactly what is printed beside it.** Every measured
    convention ships the SQL that produced it. Three of the first twenty-seven returned
    something else — a glob matched `iso_utc_now` as a routine beginning with `is`, and
    a house-prefix count had its numerator over multi-segment names and its denominator
    over all of them. A query that disagrees with the number beside it is worse than no
    query: it invites a reader to check, and then misleads them. A test asserts the
    agreement on every convention.

14. **With thousands of tests, agreement is expected.** Affix conventions are mined by
    trying every affix against every property, which is thousands of comparisons. At
    that many, "a class ending in `Provenance` is a dataclass, 7 of 7" happens by
    itself — two classes in five are dataclasses anyway. Precision, sample size and
    lift all passed it; only a coincidence test corrected for the number of tries
    separates it from `*Error`, 372 of 375. Rule 5 in a statistical key.

15. **A branch that consumes lines must offer them to every detector that wants them.**
    Building the traceability join surfaced the same defect three times in one file.
    The scanner skipped heading lines, `_table()` consumed table rows, and
    `_rule_unit()` swallowed the continuation lines of a wrapped bullet -- each one
    mining what *it* wanted and passing nothing on. So governance ids stated in a
    heading, in a roadmap table, or on the second line of a bullet were invisible:
    `ADR-0057` is named in `.groma/ROADMAP.md` and `Plan 44-01` in `ADR-0045`, and both
    were reported as work built without a plan. Fixing all three moved 30 ids out of
    that band and lifted code-to-docs traceability from 89% to 93%. Rule 9 says
    documentation is never code; this is its converse -- **prose is prose wherever it
    sits**, and a consuming branch is the easiest place in a parser to lose it.

16. **Never open a database as the wrong kind.** Pointing `--db` at `docs.db` opened it
    as a graph, failed the staleness check, and dropped every table in it — a
    destructive fallback wearing the costume of a version upgrade. Both stores now stamp
    their kind and refuse the other, before anything is allowed to drop anything.

17. **A program names its files, and those names are vocabulary.** `tabularium` is
    glossed in Mensores' pantheon and appeared in the glossary nowhere, which read as a
    word the project had abandoned. It is the name of the database the whole program
    writes to -- 52 references across 25 files. It was invisible because the path is
    assembled, `root / ".mensores" / "tabularium.db"`, so only the parts are literals:
    not a module, not a table, not a boundary target. 155 such names on Mensores and
    DunneFlow recorded none of them. `schema.Artefact` now does, admitted only by an
    extension listed in `detectors/*.yaml` -- rule 5 again, because a trailing dotted
    part is not an extension and without the list `1.2.3`, `utf-8` and `mensores.cli`
    all read as named files. `.org` was removed from that list on evidence: the only
    thing it ever matched was `host="freetsa.org"`.

18. **Every comment must land on something, and the module scope owns what no function
    does.** Comments were collected per function -- the block above a definition and
    everything inside its span -- so everything else fell on the floor: **9,659 of
    Mensores' 18,208 comments, 53%.** Whole files lost every comment they had. The
    synthetic `<module>` routine already owned module-level boundaries, calls and SQL;
    it was simply never handed any comments. A class body counts as module scope for
    the same reason it already does for every other fact type -- it runs at import.

    The cost was governance, not readability. Those comments carried 2,270 annotations
    across 438 ids, 76 of which the graph had never seen. Closing it took ids cited in
    code from 517 to 593, moved 47 plans out of *likely landed* into *traced*, and
    surfaced a marker kind (`DECISION`) that had never appeared at all. **Assert the
    total, not the cases**: the test counts comment tokens and demands none go
    unclaimed, because the defect was a whole category nobody had thought to name.

    Found the same way as rule 15 and for the same reason: a step that consumes what it
    wants and passes nothing on. Verifying it turned up rule 5 once more in
    `walk.is_test_path`, which matched `test_` as a *substring* -- so `_test_stage.py`,
    the real Test stage of the Groma pipeline, was dropped from the map entirely along
    with two others. A marker must sit at an edge of the name. A module about testing
    is not a test.

19. **A constant is a name, and a `Literal` alias is an enum.** Module level produced no
    facts at all: `visit_Assign` caught only CLI app objects and `_class_fields` caught
    only class bodies, so `JTBD_OPENERS` was declared, read six times, and absent from
    the map. 2,618 constants on Mensores carrying its configuration -- model names,
    token ceilings, directory names, the actual system prompts it sends -- and 1,030 of
    them carry a comment saying why. Module level means **runs at import**, taken from
    position rather than from a scope stack, which is the same boundary the module scope
    already uses for comments and boundaries.

    Among them hid 86 type aliases. `QueueState = Literal["pending", "adjudicating",
    "emitted", "rejected", "skipped"]` is an enumerated vocabulary declared without the
    word `enum`, and `StructureKind.TYPE_ALIAS` had existed in the schema from the start
    with nothing ever producing one. The admission rule is a constructor list in
    `detectors/*.yaml`, exactly as the artefact extension list is: `X = SOME_DICT["key"]`
    is also a Subscript. A bare `X = Y` is **not** admitted -- it cannot be told from
    `DEFAULT = OTHER_DEFAULT` without resolving `Y`, and rule 1 says precision first.

20. **A read may refuse, but it may never repair.** `Store.__init__` discarded a stale
    graph on *every* open. For `analyze` that is right -- it re-extracts in the same
    breath, and rule 12 says a graph answering the previous version of the tool is the
    one outcome this tool may not produce. But `touches`, `impact`, `query`, `glossary`,
    `naming` and `mirror` open the very same class, so upgrading DunneFlow and then
    asking it a question dropped every table and answered out of the hole. `(no rows)`
    is indistinguishable from a true empty result, so the failure was **silent, and it
    consumed the evidence on its way past**. A reader now refuses and names the fix;
    only `analyze` is allowed to drop anything.

    Two general points, both already stated elsewhere in a different costume. Rule 16
    was the same shape -- a destructive fallback wearing the uniform of a version
    upgrade -- and the lesson did not transfer because it was filed under *wrong kind*
    rather than under *destructive on a read path*. And the reasoning that licensed it
    ("derived data, rebuildable in seconds") was true of the caller it was written for
    and false of every other caller of the same constructor. **A justification that
    depends on the caller belongs at the call site, not in the constructor**; the
    decision (`_is_stale`) is now separate from the act of dropping.

    Found by dogfooding, which is the only reason it was found at all: no test covered
    a read against a stale store, because nobody thought of a reader as something that
    could destroy.

22. **A node is a billboard, not a disc.** A circle drawn in the plane of its own disk
    foreshortens into an ellipse the moment the stack is tilted, and an ellipse does not
    read as a ball -- it reads as a coin seen edge-on. A sphere has no orientation, so a
    picture of one must not either: the quad is held facing the camera, always. Invisible
    at dot sizes; the whole illusion the moment nodes are big enough to look at.

    Real geometry is not the answer. Instanced meshes and a lighting pass would cost
    fifteen thousand draws for a difference nobody can see, against a frame budget
    measured on a single instanced draw of flat circles. The sphere is a few lines of
    shader reconstructing a normal from the disc's own uv -- same layer, same call, same
    buffers. Depth writing stays **off**: two billboards at slightly different depths
    intersect along a straight line, which renders as a clean slice taken out of a ball.

    The shading silently did nothing at first, because the inject hook was named
    `fragmentColor:DECKGL_FILTER_COLOR` instead of `fs:DECKGL_FILTER_COLOR`. An
    unrecognised hook is not an error -- the shader compiles, the layer draws, the effect
    never happens. That is the same silent no-op as a string replacement that matches
    nothing, in a shader's clothing, and only looking closely at one node found it.

23. **A shadow is never drawn, and never an endpoint. The crossings are the point.**
    A shadow is a *placement device*: a proxy standing in on a plate so that plate's
    layout feels the pull of something living elsewhere. Drawing one puts a copy of a
    routine somewhere it is not, which is a lie about where code lives; ending an edge at
    one stops a real connection at a stand-in.

    The model stores every crossing twice, once per plate, each copy ending in a shadow --
    which is exactly what lets both plates lay out under the same forces. For drawing,
    those two halves are resolved back to their real ends and kept once. What comes out is
    the connection worth the screen: **this routine, on that plate, reaching that one over
    there**, drawn as a single line spanning Z. Within-plate links say what a package does
    among itself; crossings say how the program hangs together, and the two are counted
    separately because they answer different questions.

    A crossing is drawn when *both* ends are selected, so picking two plates shows exactly
    what passes between them. Its colour walks from the source plate's colour to the
    target's along its length, because a crossing passes visually through plates it has
    nothing to do with, and one flat colour there cannot be read -- the gradient says
    which end you are looking at without tracing the line back. Every disk therefore gets
    a distinct default colour, walked by the golden angle: a feature that only works once
    the reader has hand-coloured fifty-two plates is a feature nobody reaches.

    This was missing for a whole session and the stack looked fine without it, which is
    the warning. Plates full of dots are a plausible picture of nothing much.

24. **A measurement must measure the thing it names.** The orbit benchmark drove the
    camera every frame, which set the moving flag, which stripped the edges -- so it
    measured nodes only, while the readout printed `· 4,963 edges` beside the number
    because a selection existed. A claim about geometry that was never drawn. This is
    rule 13 in a renderer's clothing: the query must return what is printed beside it,
    and a benchmark's "query" is the frame it actually submitted. The override is scoped
    to the two link layers so the run isolates edge cost rather than also pulling in the
    collision-filtered labels -- measuring more than you name is the same defect
    inverted.

25. **The one store that is not derived must never be discarded.** Rule 12 says a cached
    fact is valid only if the source and the tool that read it are unchanged, so every
    store here is dropped when the extractor fingerprint moves. `source.db` is the
    exception and the reasoning inverts cleanly: it holds the file bodies themselves, no
    rule was applied to them, so no rule change can make them wrong. Dropping it would
    throw away the one artefact that cannot be rebuilt once the source tree has moved
    on -- which is precisely what the temporal layers exist to hold. It carries no
    staleness check at all, and a test asserts the module contains no `DROP TABLE`,
    because the defect this guards against is a future edit rather than a present bug.
    Rule 20 said a read may refuse but never repair; this says a *store* may be refused
    but never repaired away.

26. **External is not inferred.** Every call that did not resolve to a local routine is
    stored `INFERRED` -- 23,829 of Mensores' 30,209. But design rule 5 spends the dashed
    edge on *we are not sure this call exists*, and that is not the claim: we are certain
    the call happens and simply cannot see the other end. Drawing the two the same way
    blurs exactly what rule 6 says never to blur, so an external carries its own mark and
    no confidence shape at all. Found by noticing that a routine's inspector showed 22
    inferred calls and 22 external ones, and that the numbers were equal for a reason.

27. **A marker counts only where it touches.** `#:` is Sphinx's doc-comment marker and
    its colon is syntax; `# :mod:\`x\`` is an ordinary comment whose text legitimately
    begins with a reStructuredText role. Stripping only `#` left 1,698 comments reading
    `": Keychain service name"` and 323 constants carrying their WHY through a stray
    colon, while stripping any leading colon would have eaten the role -- the same
    shortening-at-ingest as the tag-stripper that ate `<role>`. The test is position, not
    presence, which is rule 5 stated once more: a marker must sit at an edge. Fixing it
    moved 1,698 to 62, and the 62 that remain are exactly the roles.

28. **A `rem` inside `@media` is not the page's `rem`.** Design rule 3 puts every
    dimension in rem so one multiplier resizes the surface together, and that is worth
    keeping — it works, and it is why the whole shell scales from one slider. But a
    breakpoint is not a dimension; it is a question about the *window*. By spec a relative
    unit in a media query resolves against the **browser's** default font size and ignores
    `:root`, which this stylesheet pins to 16px and which the scale slider drives. On a
    reader whose Chrome default is 24px, moving the slider took the navigator from 192px
    to 288px and moved the breakpoints not one pixel, while `68rem` silently meant 1632px
    instead of 1088px — so a 1454px window got the narrow layout. Five media queries were
    written this way. They are px now, at the widths the rem values were meant to express,
    and everything else stays rem. A unit that looks like a member of the scaling family
    and is not one is worse than an obvious exception.

29. **A media query contributes no specificity, so equal selectors go to source order.**
    `.inspector { display: none }` inside the narrow block lost to `.inspector { display:
    flex }` declared 350 lines later, so the narrow layout never hid what it said it hid:
    the pane rendered into a grid declaring two columns, wrapped onto row 2, and put
    "Nothing selected" at the bottom left with an empty strip beside it — while the app
    grew taller than the window and the whole document scrolled. **Fix it with specificity,
    not with order**, or the next component rule takes it back silently. This is the
    `[hidden]` defect exactly (rule: an author `display` beats a user-agent one), and the
    lesson did not transfer because it was filed under *user-agent rules* rather than under
    *a later `display` wins*.

    Its companion, found in the same layout: **a grid item defaults to `min-height: auto`
    and refuses to shrink below its content.** The navigator's 1,151px of content held the
    row open at 700px inside a 446px box. Every pane here scrolls inside itself, so that
    default hands the overflow to the document, which does not scroll panes, instead of to
    the pane, which does. `minmax(0, 1fr)` on the row and `min-height: 0` on the children.

30. **A label is not an identity.** The four navigator routes that set what you are looking
    AT — ways in, packages, boundaries, tables — were `() => { state.view = state.mode;
    ensureGraph(); }`. They switched mode and selected nothing, so **all forty rows did the
    same thing**, and the inspector went on truthfully reporting "Nothing selected" while
    every control worked. It never tripped the no-route check, because the route existed
    and simply had no subject; no identity had ever reached the DOM for it to act on. Design
    rule 16 one level below where the checks were looking, for the third time.

    The four are not one shape, and finding that out is what made the fix right rather than
    plausible: a package and a boundary kind are **plates** and select as themselves; a way
    in resolves to routines, and `ways_in()` had computed those roots all along while the
    cover threw them away; and a table is **neither** — `audit_events` is not a node at all,
    so selecting a table means selecting the code that reads and writes it. `queries.py`
    already said so in as many words — *inventing an id to make a row clickable would be a
    link to nothing* — which is the negative half of rule 17 and was written before anything
    needed it. Assert both directions: the item must emit an identity and the route must
    consume one, because either half alone passes while the feature is dead.

31. **A shadow is never an endpoint — when *reading* an edge as much as when drawing one.**
    Rule 23 says a shadow is a placement device, never drawn and never an end. `d.links`
    obeys it, resolving each stored edge back to its two real ends. `recomputeMembers` did
    not: it added `raw.edges.from/to` unresolved, so for a call that leaves the plate it put
    the **shadow** into the selection instead of the routine the shadow stands in for.

    Both halves then failed together and silently. The real neighbour was not a member, so
    it was never lit; and `buildSelectionGeometry` requires *both resolved ends* to be
    members, so the crossing was skipped — and crossings are exactly the edges that leave
    the plate. **Picking a routine drew its callers and callees only where they happened to
    sit on the same plate.** `console_script` has four callers and three callees and drew a
    single unconnected dot; `guarded_cwd` has eleven connections and drew seven. Nothing
    reported it, because a routine that genuinely has no neighbours looks identical.

    The lesson is not "resolve shadows" — rule 23 already said that, in as many words:
    *ending an edge at a stand-in stops a real connection at a stand-in*. It is that a rule
    about drawing was never applied to the code that **reads**, and the two are the same
    rule. Found by a reader saying a picture looked wrong, not by any check.

32. **A count must say what it counts.** The navigator listed `degree` — an edge count —
    beside each routine, in a pane where every other group's number counts *things*: 14 ways
    in, 8 packages, 52 disks. `guarded_cwd` printed **8**, drew **7** nodes, and had **3
    callers and 5 callees**. All three numbers were correct and no two of them agreed about
    what they were, so the reader reasonably read 8 as nodes and reported a missing one.

    Rule 13 in a list rather than in a claim: the number must be produced by, and named
    after, the thing it measures. It is `3← 5→` now, taken from the same `inbound`/`outbound`
    maps the selection itself uses, so the figure and the picture cannot disagree.

33. **A trail step must carry its subject, or the trail cannot take anyone back.** Steps were
    `{view, label, note}`; clicking one set `state.view` and re-rendered. From inside graph
    mode, where the view is *already* graph, that is a no-op — so the trail rendered,
    highlighted the current step, scrolled and pruned correctly, and could return nobody to
    anything. Rule 30 for the third time, and the most expensive place for it: design rule 15
    says the trail is what makes a detour free, because **nobody chases a rabbit if they
    might not find their way back**.

    Its companion, and the reason undo exists: two ordinary clicks strand a reader. Clicking
    the node you are already looking at clears the whole selection (a deliberate toggle-off
    in `togglePick`, and a trap when the click is *also* how you move), and every
    nothing-selected state looks identical, so nothing on screen says which routine you had.
    **The toggle is kept** — clearing by clicking is right, and `Esc` and the clear button do
    the same — because undo makes it recoverable, which is the cheaper fix and the better UI.

34. **Pinned data hides in prose, and that is the hiding place the guards missed.** Two
    guards kept the shell's top-level arrays empty and its `state` clean. Neither could see a
    *sentence*. Table mode's footer read "Showing **12** of **515** routines in
    `mensores.quaestor`"; the breadcrumb's three centre modes were fixed pairs — "packages ›
    system boundary", "quaestor › routines", "cli › interview" — shown on every screen for
    every program; document mode was a page of hand-written narrative about
    `mensores interview --extract`, formatted exactly as generated output with nothing
    marking it as a sample; the glossary asserted findings about specific `.groma` files; and
    a citation path called `.replace("mensores.", "mensores/")`, silently wrong elsewhere.

    Worst of them, and the one that says why this matters: **the egress consent surface**
    carried "4,568 routine names", "184,000 lines" and a manifest of "2,449" — one program's
    figures written into the one screen in the product where a wrong number is a consent the
    reader did not give (design rule 14).

    Guard on the *sample program's name*, not on numbers: a number in prose is often
    legitimate ("one hop", "three panes"), a specific program's name never is. And note what
    that still misses — the glossary named the program's **files** rather than the program.

35. **A `let X = []` that nothing assigns is an empty view with no symptom.** `ROUTINES` was
    declared, commented "for table mode", and written to by nothing, so table mode rendered
    zero rows for as long as it existed. It is the pinned-data family inverted: those guards
    assert the arrays are *empty*, which this passed perfectly by never being filled.

    The invariant is not "must be assigned" — an unbuilt feature legitimately has no data.
    It is **assigned, or the view says it is empty**, because "not computed yet" and "nothing
    to report" are opposite claims and a blank panel states the wrong one. Written as a list
    of exemptions first; that list reached five of ten arrays before it was obvious it would
    grow until the guard caught nothing. Finding the invariant is what made it a check rather
    than a ledger. It then found `CONVENTIONS`, `TERMS` and `MANIFEST` — and three variables
    read by nothing at all, which were deleted rather than exempted.

36. **A generic loop narrowed to a literal is how a feature disappears without a trace.**
    The pre-merge graph walked `Object.entries(panels)` and folded every panel. The rewrite
    wrote `[["navigator","nav"], ["inspector","insp"]]` — correct for the two it named, and
    it silently dropped `hud` and `controls`, which stayed defaulted, persisted, and listed
    in the reset dialog as "panel layout". Dead *inside a live key*, where the guard written
    for exactly this failure could not see them: it walks the top-level keys of `DEFAULTS`,
    and `panels` as a whole was plainly being read.

    Route from a table, walk the *settings* rather than a list of your own, and make an
    unknown key a named error. Then assert the two key sets agree, both derived. The same
    reasoning retires every hand-kept second list — `FOLDABLE` now derives from `PANELS`.

37. **A guard that checks a name appears has not checked that anything happens.** Three of
    this session's guards passed against their own defect on the first try. One split on
    `.graphlegend {` and read an *earlier* rule with the same selector, asserting against
    `display: none`. One accepted `step.subject` appearing anywhere, staying green while one
    of the two ways back was broken. One accepted the presence of `restoringSelection` while
    the line that consults it was gone.

    **Run every new guard against the defect it was written from, and against a version
    where only half the feature works.** A check that has never failed is a claim nobody has
    tested — the same argument as rule 13, applied to the tests themselves.

38. **An instrument that cannot see cannot report.** A browser-automation tab is given no
    animation frames, so `ResizeObserver` never fires and `requestAnimationFrame` never
    ticks. Measured through one, deck.gl's canvas appeared never to resize on a pane fold —
    a confident, reproducible, entirely false finding, and the fix for it was most of the
    way written before an observer attached by hand also failed to fire and gave it away.

    Static DOM facts survive a starved tab: layout runs without frames, so grid tracks,
    widths and classes are real. **Anything needing a rendered frame does not exist there.**
    Rule 24's family — a measurement must measure the thing it names — and the reason the
    benchmark already refuses to start on a hidden tab. When the instrument cannot prove it,
    describe the change and let someone with a real window look.

39. **A plausible diagnosis of a real symptom is still a guess, and this one named the
    wrong plane for two sessions.** Zooming all the way in lost a quarter of the stack. The
    explanation on file was the **near** plane — `OrbitView` scales world units by
    `2 ** zoom` about a target the camera sits a fixed distance from, so the stack's near
    half was said to cross `near 0.1`. It reasons well and it is wrong.

    Measured, by projecting every drawn node through deck's own view-projection and counting
    the ones whose clip-space z leaves `[-1, 1]`: **nothing clips anywhere in the range
    except at `maxZoom` exactly, where 4,063 of 15,869 go past +1** — the **far** plane, at
    deck's default of 500. The near plane is never reached at any zoom this view allows. A
    cliff at the top of the range rather than a gradual onset, which is exactly how a reader
    reported it: *"when I zoom in, the clipping cuts in"*.

    So `far` is raised to 5,000 and `near` is untouched. It costs nothing, and both things
    that could have made it cost something were measured: the on-screen scale is identical to
    the pixel (24,574.8 px per 100 world units at `maxZoom` either way), and `unproject`
    round-trips to zero error. 5,000 rather than more, because it clears `maxZoom` with the
    furthest node at clip-space −0.43, while 50,000 puts the whole stack past −0.94 and
    spends depth precision on nothing.

    **The warning that produced this rule stands, and is why the fix took two sessions to
    find.** An orthographic frustum is a box, not a pyramid, so a negative `near` is
    geometrically meaningful and looks like the obvious fix. **It kills pan and zoom
    outright** — deck.gl's orbit controller implements both through `viewport.unproject()`,
    while rotate is angle arithmetic that never unprojects, so exactly the two controls that
    unproject stop and the one that does not carries on. A guard now refuses a negative
    `near`, because the geometrically obvious wrong answer is the one a reader reaches for.

    Two general points. **A symptom explained but never measured is an open question wearing
    an answer** — this one was closed with a count rather than an argument, and the count
    took one pass over 15,869 nodes and no rendered frame at all. And it stayed open because
    it was filed as *tolerable at extreme zoom*: it stopped being tolerable the moment a
    feature told the reader to zoom in for more, so **a defect's severity is a property of
    what has been built since**, not of when it was found.

40. **Two detectors recording one act is two numbers about one thing.** The hover card
    read three tables *and* "DATABASE 20" — which is the same seventeen statements seen by
    the SQL reader and the boundary reader. Not an oddity of one routine: 991 of Mensores'
    1,316 DATABASE boundaries sit on a line with a `sql_ops` row, and **all twenty** NETWORK
    boundaries sit on a `net_calls` row. A summary that states the same act twice is rule 32
    in a smaller box — two correct numbers, neither of them saying what it counted.

    A boundary already named by a more specific record on the same line is not counted
    again. **Per line, not per routine**: 43 routines have a DATABASE boundary and no
    `sql_ops` at all — they open a connection and run nothing — and a coarser rule blanks
    their card. The one-line tolerance is a judgment and is written down as one; the
    detectors disagree by a line on multi-line statements, recording the call site and the
    statement start.

    Its companion, found in the same edit: **excluding the general record must not lose what
    only it recorded.** Ten of that routine's seventeen operations are `BEGIN` / `COMMIT` /
    `ROLLBACK` with no table of their own, and the first fix dropped them silently — the
    exact omission the anti-join was written to prevent, inverted. They have their own row,
    grouped by direction, because DDL is not transaction control.

41. **A prose claim and a machine-readable population are two things, and only one of them
    can be asked a question.** A measured naming convention carried `claim` (a sentence) and
    `sql` (which reproduces its *exceptions*). Neither can answer "is `witness_defer_cmd`
    one of these?" — which is what the inspector needs before it can say a routine shares a
    convention with ninety-eight others. Recovering the affix by parsing the sentence would
    be reading prose to get back something the code had already computed and thrown away.

    `Convention.glob` is that population, and it is **the same string the exceptions query
    is built from**, so the membership test and the evidence cannot drift. A test asserts
    the glob appears in the SQL — rule 13 applied to a second way of naming one set.
    Writing it exposed that `test_an_affix_glob_respects_the_separator` had **never run**:
    its fixture produces no affix convention at all, so its assertion sat behind
    `if predicates:` for as long as it had existed.

42. **A guard that names the right case may still not catch it.** `selectionOnScreen()`
    documents itself as returning null when there is no viewport — "we cannot say" and "it
    is off screen" being different answers — and guarded with
    `g.deckgl?.getViewports?.()`. deck.gl does not return a falsy viewport before it has
    one; it **asserts inside** `getViewports()`, so the optional chaining protected against
    a missing deck and not against the case the comment describes. The `?.` was what made
    the code look guarded.

    The path is ordinary: pick a routine in the navigator before opening the graph, and
    `selectFromNav` mounts the engine and calls `applyWanted()` synchronously, before any
    frame. The throw left `applyWanted`, so `persist()`, `recordSelection()` and `render()`
    never ran — the selection happened, undo did not record it, nothing repainted. Rule 37
    in the code rather than in the tests: **check that the guard catches, not that it
    mentions.**

43. **A check that cries wolf has already failed, and it fails silently.** The shell's
    runtime self-check printed "dead controls" on every page load and was wrong about every
    one of them: `insp`, `fold`, `navid`, `titled` and `legend` are real — grid track state
    the stylesheet reads, and parameters read off controls found by class — and had simply
    never joined `WIRED_ATTRS`. Its own comment says why that costs: *a check that cries
    wolf is a check nobody reads*, and a genuine dead control would have arrived as a sixth
    line in an error nobody had believed for weeks.

    `legend` is the one worth keeping. It is written on the graph mount, which does not
    exist until the reader opens the graph, so the check said four at boot and five
    afterwards — one page, two answers, neither of them the truth. **A check whose answer
    depends on when it runs needs a counterpart that does not run at all**, so the roster is
    now derived from the source, generated markup included; the existing guard reads
    `index.html`, and every one of these five is written by JavaScript.

44. **A live control reading a field the server does not send renders nothing and throws
    nothing.** The glossary and naming pages were the ratified prototype's, written against
    `{pattern, ok, n, exceptions: [str]}` while the server sends `{glob, holds, total,
    rating, exceptions: [{name, where}]}`. That is *worse* than an unported page: `cv.ok /
    cv.n` is `NaN`, the percentage bar renders at zero width beside a claim that is perfectly
    true, and nothing anywhere fails. Both pages were held back saying so, which was right,
    and neither existing guard had a name for the shape — a dead control renders and does
    nothing (rule 30), a dead setting is read by nothing (design rule 16), a dead variable is
    assigned by nothing (rule 35), and this one **works**, on data that is not there.

    The check reads the served key names out of the builder and the accessed names out of the
    view, and runs in one direction only. A view may leave a served field unread — the
    glossary sends `uses` and the page shows `used_as`, which is the same fact in the form a
    reader wants — but a view reading a field nothing sends is rendering a blank while looking
    finished. Its companion, found in the same edit and the same shape one layer down: a
    string the code composes is **prose the moment something prints it**, so `f"{noun}s"`
    stood as `classs ending in \`Error\`` for as long as no page displayed it.

45. **Hidden is not absent, and the difference is the whole bill.** The routine list
    grouped 4,734 routines into 47 packages and built every package's rows whether it was
    open or not -- closed ones being `display: none`. That is 3,413 buttons on every
    keystroke where the flat list cost 200, at **341 ms per character typed**. Its
    companion in the same pane: a search opened every package it matched in, and `e`
    matches all 4,734 routines across all 47 packages -- **483 ms on the first keystroke of
    an ordinary search**.

    Both are the glossary filter's 412 ms again (see the budget table), and the cause is the
    same one in a third costume: **work proportional to the whole program on every character
    typed**. The filter got there by calling `render()`; this got there by building markup
    nobody could see, and then by opening everything a broad query touched.

    The second was the worse *answer* as well as the slower one, which is the part worth
    keeping. "2,206 match `g`, in 43 packages" is something a reader can act on; 1,924 rows
    is the haystack again. A bound on how much a search opens by itself is not a performance
    concession, it is the better reply to a question that has not narrowed anything down
    yet. It must say so, though: closed packages with no explanation read as a control that
    failed -- design rule 1 with nothing removed but everything hidden.

46. **An opening rule that names a position breaks exactly as an ordering one does.** Rule
    24's companion was recorded as *an ordering rule that names a position rather than an
    identity breaks the moment anything is added beside it*, and it was written one function
    away from where the accordion decided which group to open: `order[0]`. So with the menu
    order set to "Ways in first" the navigator opened on six entrypoints and left the
    routine list -- which design rule 26 says the navigator *is* -- closed. The menu order
    decides what sits at the **top**; it was never asked what should be **open**, and two
    questions sharing an answer is how one of them gets answered by accident. The group is
    named (`primary`) now.

    Found by looking at the pane, not by any of the six guards written that hour.

47. **Dimming says what is not yours; it does not say which one is.** Design rule 19 dims
    the other nine thousand rather than hiding them, and that is right -- a subset is only
    legible inside the shape it belongs to. But a reader looking for *one* routine among
    9,874 dots then has to read their answer off a colour difference, with a dimmed node in
    front of or behind the lit one looking much the same at two pixels across. Worse, the
    picture answers questions about whichever dot the cursor lands on: hovering a neighbour
    by a pixel produces a confident card about a routine nobody asked about, and it is
    indistinguishable from a card about the one they did.

    So identification is its own channel -- a reticule on what was picked, fixed in screen
    size because a mark that shrinks with the picture stops working exactly when the picture
    gets crowded -- and *what may answer* is separated from *what is drawn*. Locked, only
    the lit set replies to a hover or a click; the fog stays on screen, because rule 19's
    reason for drawing it has not changed. **The moment that separation collapses the
    feature is a filter on the picture**, and then rule 19 forbids it and design rule 1
    wants a count for it. Exploring wants the opposite of all this, so it is a switch and it
    sits where the reading happens rather than in Settings.

    Its companion, and the sharper lesson: **two pickable layers reporting through one
    handler is an index that means two things.** `info.index` from the pointer layer is an
    index into two dozen arrows; read as a node index it selects a different routine,
    plausibly and in silence. Route by layer, which is design rule 16 one level below where
    it is usually applied -- and note that the arrow's click had to *set* the selection
    rather than toggle it, because the node an arrow stands over is already picked and
    `replace` on a single pick is the deliberate toggle-off (rule 33). The one control whose
    entire purpose is *go there* would have cleared the selection instead.

48. **A scripted click proves the handler; only a pointer proves the path to it.**
    `element.click()` invokes the listener on the element it names, whatever is drawn on top
    of it. So a session that drove the detail window through `.click()` — opening it,
    hopping, going back, closing — verified every control on it and could not see that
    **the scrim was painted over the whole window**: `.viewer-scrim` at z-index 90 above a
    window at 88. It rendered greyed, and every click on it landed on the scrim and closed
    it. Reported from a screenshot within minutes.

    Two things follow. Hit-testing is a separate claim from wiring, and `elementFromPoint`
    is how a script makes it — `el.contains(document.elementFromPoint(cx, cy))` is one line
    and would have caught this at once. And **a scrim belongs to one window**: two windows at
    different depths cannot share one, because a scrim must be under what it dims and over
    everything else, and one element cannot be both. They are declared as pairs now.

    This is the `[hidden]` defect and the `table-layout` defect in the same family: three
    times now, a control has been correctly wired to a stylesheet that could not carry it,
    and every check that reads markup or handlers passed. What the DOM says and what the
    reader can reach are different questions.

49. **A fallback that yields a plausible value has hidden the failure it was written for.**
    `fitView` read `g.container?.clientWidth || window.innerWidth`. Mounted while its pane
    was still hidden — a hidden container is 0×0 — it framed the stack for a 1275px window
    and drew it into a 496px canvas, so the graph came up empty and stayed empty until the
    reader found snap-to-fit. Nothing failed, nothing logged, and the number was entirely
    reasonable; it was simply about a different box.

    A fit against something not laid out is not computable, so it is **deferred** rather
    than guessed: the view state is returned untouched and the debt is paid on the first
    reveal that has a size. Deferring is what makes it recoverable; substituting is what
    made it invisible.

    Its companion, found the same hour and the reason the fallback ever ran: `ensureGraph()`
    was called **before** `render()` on the mode toggle, so the engine measured a container
    the next line was about to un-hide. `boot()` had the order right. **Paint, then measure**
    — an order that is correct at one call site is not a property of the code.

50. **A scroller is the element that scrolls, not the one that declares `overflow`.**
    `.tablewrap` carries `overflow: auto` and looks like the scroller. Nothing bounded its
    height, so it grew to all 339,229px of the table and never scrolled a pixel while the
    *pane* scrolled underneath it. Two features were written against it and both failed
    silently in the same way.

    The sticky header — position, offset, z-index and background all correct — stuck to a
    box that does not move, so it scrolled away and took the resize handles and the subject
    strip with it. And the reveal moved a `scrollTop` with nowhere to go, while its own check
    compared the row against a box extending far below the window, which made every row "in
    view" and reported success. **A guard naming the right case and measuring the wrong box.**

    Ask, do not assume: walk up until something genuinely overflows. And if a box is meant to
    be the scroller, bound its height so it is one — the wrapper is a fixed header over a
    scrolling body now, which is the shape the navigator was already given for the same
    reason.

51. **A rule kept at a call site rots as callers are added; move it to where they all pass.**
    `selectFromNav` did not move the routine list to its selection, on the reasoning that a
    row the reader clicked is already under their eye. True of its one caller, and false of
    every caller it acquired since — a table row, a hop in the detail window, the arrow at
    the plate's rim, the other browser window. All four left the navigator marking whatever
    had been clicked last time, and **a stale highlight is worse than none**: it is a
    confident wrong answer. It was reported as a question — *is that accurate? I can't tell*
    — which is the most expensive way to find anything.

    Its companion, the same shape in state rather than in behaviour: the detail window held
    a node id **of its own** beside the selection, and the two drifted the first time
    anything else moved one of them — the trail's Back stepped the app to the previous
    routine and left the window on the one after it. Two answers to "what am I looking at",
    in the window built to show how things connect. It holds *open or not* now and reads the
    one selection, so it cannot disagree by construction.

    Both are the same instruction. One truth, one place that owns it, and every caller
    reaching it through the same door — because the list of callers is the thing that grows.

52. **A cache that takes a value has already done the work it exists to avoid.** The code
    browser rebuilds a file's markup once and re-attaches the node, because `buildNav()` and
    `render()` both rewrite an `innerHTML` and both run on every selection — 1,937 ms and
    1,358 ms per click with a 5,838-line file open. The cache was written as
    `codeCached(slot, codeTable())`, and JavaScript evaluates arguments before the call: the
    1.37 MB string was built on every hit and discarded. It takes a thunk now.

    Its companion, and the more useful half: **re-attaching a large subtree is not cheap
    either.** Moving 17,500 elements back into the document forces a style recalc and a
    layout over all of them — `render()` measured *worse* after the cache than before it,
    155 ms to 1,370. A node kept in the document costs nothing, so the pane is simply not
    repainted when only the selection moved, and the highlight is two class changes. The
    check on that is the DOM, not a flag: a flag saying *already painted* is true of a pane
    another view has since overwritten, which is rule 42 in a repaint.

    Both were invisible to every test, and both were found by driving the thing.

53. **A layout bounded by arithmetic is right at one window size.** The code pane declared
    `max-height: calc(100vh - 16rem)`, where 16rem stood for the chrome above it. On a 589px
    window that chrome came to 185px, the box overflowed its own scroller, and **one line of
    code was on screen** — while every check on the page passed, because the box did declare
    `overflow` and did have a height. Rule 49's shape in a stylesheet: a plausible value
    standing where a measurement belongs, and no symptom beyond a picture nobody had looked
    at.

    The remedy is the one rule 29's companion already gives. A flex child is `min-height:
    auto` and refuses to shrink below its content, so the chain has to say `flex: 1;
    min-height: 0` at *every* link between the scroller and the box — and a single missing
    link collapses the pane to its content with nothing anywhere to indicate which one.

    Not fixed, and reported rather than changed because it is a design decision that is not
    mine: the navigator's nine group headings cost **306px** whether or not their groups are
    open, so on a short window any open group — the routine list as much as the code — gets
    about 200px. That is pre-existing and affects every group equally.

54. **A guard that names the wrong container has not guarded anything, and the container
    is usually the generated one.** The Code group's file filter destroyed the box it was
    typed into, on every keystroke, for as long as it had existed: `buildNav()` wraps every
    group's body in a `<div class="nav-items">`, so `group.querySelector(".nav-items")`
    inside `#navCode` returns the **wrapper** and writing rows into it replaced the whole
    body, input and caret and all. Filtering 626 files has never worked past one character.

    The guard for exactly this passed the whole time. It asserted the refresh does not
    *call* `buildNav` — true, and beside the point, because it rebuilt the pane without
    going through it. Rule 37 said check that a guard catches rather than that it mentions;
    this is the same instruction pointed at a **selector**, and the general form is worth
    keeping: *a class the generator emits around every item cannot distinguish the wrapper
    from what the item puts inside it.* An id can. The same session found the same shape one
    layer out — a flex chain written for one of a component's two states and applied to
    both, which squashed the other to 118px and let 1,900px of content overflow it visibly
    and paint over the four panels below. Every row present, sized, correct and unclickable;
    `elementFromPoint` said `.nav-head` for all thirteen on screen. Neither was visible to
    any test, and both were found by driving the thing.

55. **A bound must be on the work, not only on the answer.** Rule 45's auto-open is free
    where it was written: the routine list opens packages whose rows are already in memory,
    so the only cost is markup. Carried into the search unchanged it marked 84 files open,
    and a file there is a **request** — ten queries for its margin. Eighty-four of them
    behind one keystroke is the very defect the rule exists to prevent, arriving by a route
    its own precedent did not cover. One file opens now, the top one, and only once the
    answer has narrowed.

    Its companion, and how it was caught: the 84 rendered `opening…` for ever, because
    *nothing fetched them*. The open state was computed in one place (`return !SEARCH.broad`)
    and the fetch lived in another, so a file could be open without anything having opened
    it. **One truth about what is open, and whoever sets it does the work** — rule 51 again,
    and the version that looks identical on screen right up until it does not.

56. **A file restored to disk is not a module restored to memory.** A mutation harness
    wrote `revisions.py`, ran the tests, and wrote the original back in a `finally`. The
    file was byte-identical to HEAD afterwards — `git status` clean, `grep` showing
    `replace(":", "-")` — and the next analysis wrote
    `graph@2026-08-29T23~43~25Z.db`. Python revalidates a `.pyc` on the source's
    **(mtime, size)**, and a one-character-for-one-character mutation changes neither
    when the restore lands in the same clock second, so the interpreter kept running the
    mutant out of `__pycache__` while every way of inspecting the source said it was
    fine.

    Two things follow, and the second is the general one. A harness that edits source
    must invalidate the bytecode it caused to be written, not merely put the text back.
    And **the size-preserving mutation is the dangerous one** — every mutation in this
    session that changed a line's length invalidated the cache by accident and hid the
    defect, so the harness looked correct for as long as it was only used carelessly.

    This is rule 43 in the instrument for the third time in two sessions: the first two
    read pytest's output instead of its exit code and reported every mutation as
    surviving. Here the harness reported honestly and **corrupted the next command
    instead**. An instrument that modifies the thing it measures has to put it back at
    the level the next reader looks at, and for Python that level is not the file.

57. **Admitting a directory for its documents must not admit a copy of the program.**
    `.claude` and `.groma` are kept in the document walk deliberately — that is where a
    project files its charter, its decisions and its naming standard, and skipping every
    dotted directory is right for code and hides the vocabulary. Nothing scoped that
    admission below the top level, so two stale agent worktrees under
    `.claude/worktrees/` put **335 of Mensores' 2,381 documents** — 14% of the corpus —
    into the map: a complete second copy of the project's governance documents from May,
    under the old `.paul` name, from before the rename this file's ground truth rests on.

    The tool defended itself better than it had any right to. The copy detector caught
    303 of the 335 and every consumer filters `duplicate_of = ''`, so the glossary, the
    naming lanes, traceability and the mirror were all largely protected. **The 32 that
    leaked are the ones that had drifted from their originals** and so were no longer
    byte-identical — which is the general shape: a near-duplicate defeats an
    exact-duplicate test precisely when it has become interesting.

    The marker is read off the disk and is never a question asked of a VCS: a worktree
    carries a `.git` *file*, a clone a `.git` *directory*. `os.walk` has already listed
    the directory, so the test costs no `stat` at all. The root's own marker is never
    consulted, because the corpus is itself a checkout and that is the point.

    Found by pointing DunneFlow at two points in time for the first time. Neither number
    was wrong on its own; the *difference* between them was 340 removed documents that
    Society had never removed, and a phantom is only obvious once something makes it move.

58. **A second read-only handle to a database this process already holds open is 36x
    slower, and it is only slow while the tool is doing its job.** The change diff
    attached both graphs with `mode=ro`, for the best reason there is: rule 20 says a
    read may refuse but may never repair, and one of the two is a snapshot somebody
    sealed. One `calls` comparison on Mensores measured **8,855 ms with the dashboard
    running and 242 ms with it stopped** — same query, same files, same page cache. A
    read-only connection has no write access to the `-shm`, so it cannot join the
    shared-memory WAL index the open handle maintains and re-derives it per query.

    The trap is the shape of the measurement, not the number. Every timing taken of this
    module before that one was taken with the server stopped, where it is 242 ms and
    perfectly healthy — so it would have been recorded as fast, shipped, and been 87
    seconds behind the reader's first click. **A component measured in isolation has not
    been measured in the state it runs in**, and for a server the state it runs in is
    "holding its own files open". Rule 24's family: the benchmark must submit the frame
    the product actually draws.

    The fix is to attach the *other* graph onto the connection that already has one —
    137 ms — which is what `Store(shared=True)` was already for. And the read-only
    guarantee is then kept the way rule 25 keeps `sourcedb`'s: by a test asserting the
    module contains no write statement, over its **string literals via `ast`** rather
    than by grep, because the prose explaining why there are no writes contains the word
    `DROP` and a check that cries wolf is a check nobody reads (rule 43).

    Two smaller things fell out of it, both silent. `PRAGMA query_only` buys the
    guarantee back and buys the slowdown with it, so it is not an escape. And a
    **relative path inside a `file:` URI is not that path** — `file:output/mensores/…`
    reports "unable to open database", naming the file it could not open and never
    saying why.

59. **A mutation harness must prove its baseline is green, or every mutation reads as
    caught.** A run scored **7/7** while one guard was already failing on an unrelated
    attribute: the suite was red before any mutation, so each one "went red" and the
    single mutation that genuinely survived was invisible inside the perfect score. The
    honest score was 6/7. A harness that only knows *red after* cannot tell a mutation it
    killed from a suite that was already dead.

    Rule 43 in the instrument for the fourth time in two sessions, and the four are worth
    listing together because no two look alike: two read pytest's **output** instead of
    its exit code and reported everything as surviving; one restored a file of identical
    size within the same second and left the mutant running out of `__pycache__` (rule
    56); this one measured against a red baseline. Every one of them was a check about
    checks, and every one reported confidently.

    Its companion, from the same run: **a mutation that leaves any read of the thing
    standing has not removed it.** Deleting a handler's `closest("[data-x]")` while its
    `dataset.x` line remains keeps the attribute "read" by code that can no longer run —
    so the guard passes, correctly, on a claim narrower than the one being tested. When a
    mutation survives, ask whether the guard is weak or the *mutation* was, before
    changing either.

60. **A stored path is a key before it is a location, and an absolute one is a bad key.**
    Every path in all three stores was absolute -- 55,434 rows in one graph alone. Three
    of the costs are about a program directory being a thing somebody can *hand over*: it
    publishes one machine's directory layout to whoever receives it, it is wrong the
    moment a tree is moved to free disk space, and it is wrong on every other machine a
    copy reaches.

    The fourth is the one that mattered here. Two revisions read from two different trees
    give the same file **two unrelated keys**, so nothing can pair a file with itself
    across two points in time -- which is the one question two revisions exist to ask.
    Joined as stored, Mensores' pair read **0 identical, 628 added, 625 removed**. The
    truth is 613 identical, 12 modified, 3 added, 0 removed, and it costs one query and
    **zero body reads**, because the sidecar is content-addressed: a hash comparison *is*
    the file-level diff.

    The origin was one line, and it had been announcing itself: `rel = str(path)`, with
    `module_name(path, root)` computing the genuine relative form on the very next line.
    Nothing needed the absolute form back -- bodies are fetched by content hash, never by
    opening a path, and the only step that touches the disk is analysis, which is handed
    the root as an argument. So the root is **used and never recorded**, and the reader
    binds one only when something actually opens a file.

    Two things fell out that say the shape was right. The strip already existed **ten
    times** -- nine identical `_rel()` clones across the renderers plus `_short()` in the
    code browser -- so storing the relative form was a net deletion; and those clones were
    not the harmless no-ops they looked like, because `Path("a/b.py").resolve()` resolves
    against the *working directory*, so run from inside the analysed tree they would have
    silently prepended the intervening directories to every path on the page. And a move
    became free: **0 cache hits and 628 files pruned** under the old key, 628 cached and
    nothing pruned under the new one, for a move that changed no byte.

61. **A second way into the store must obey the rule the first one was taught.**
    `entrypoints_from_packaging` reads `[project.scripts]` and writes rows directly; it
    never goes through the extractor. So making the extractor's paths relative moved
    54,746 rows and left **four** absolute -- in the one place `CLAUDE.md`'s own ground
    truth lives, the four declared executables. Nothing failed. 54,746 of 54,750 moving
    looks exactly like success, and every unit test passed, because the sample program has
    no `pyproject.toml` and nothing exercised that writer at all.

    Found by scanning **every column of every table in every store** for the analysed root
    rather than by checking the columns the change had touched. That is the difference
    between a check that confirms what you did and one that can tell you what you missed;
    the same scan is what proved the only absolute strings left anywhere are paths quoted
    inside Society's own handoff documents, which are content and stay whole (rule 8).

    Its companion, and the reason it is a rule about *one meaning per column*: those rows
    land in `COALESCE(r.file, e.file)`, the same payload column as a routine's file. A
    `src/` layout puts `pyproject.toml` one directory *above* the code, so the honest
    answer is `../pyproject.toml` -- and the migration needed the same transform, not a
    prefix strip, which cannot express `..`. A first version stripped only, and left those
    four rows absolute in every graph while reporting a five-figure success.

62. **A migration may re-stamp the fingerprint it satisfies, and only that one.**
    Making paths relative meant editing the extractors, which moves `rules_fingerprint()`,
    which makes every existing store stale -- so a correctly migrated graph is one no
    reader will open. The migration therefore re-stamps `meta.extractor` too, and that is
    defensible **only because it performs exactly the transformation the new fingerprint
    stands for**: no rule about what counts as a call, a boundary or a constant moved,
    only the spelling of a column.

    Left general that is a licence to vouch for changes it did not make, so it is **gated
    on the stored fingerprint being one specific prior value**, named as a constant. Any
    other is stale for reasons this migration cannot speak to and is refused, naming
    re-analysis instead. The marker for *have the paths been converted* is its own meta
    key rather than the schema version, because bumping that **discards** the graph -- and
    the whole reason to migrate in place is that a sealed snapshot is kept precisely so it
    can be read after its source tree is gone. Rebuilding would orphan exactly those.

    Two smaller things it settles. A reader must name **which** fix applies: telling
    someone to re-analyse a snapshot whose tree no longer exists is telling them to do the
    impossible. And *"the paths are relative"* is **stated in a marker, never inferred
    from the rows** -- an empty store holds no absolute path to find, and "nothing to see"
    is not the same claim as "already converted".

63. **A store's reader must read the columns that exist, not the ones this version of the
    code knows about.** Rule 20 says a read may refuse but may never repair, so a
    read-only open never runs an additive migration -- and the dashboard opens `source.db`
    read-only every time it starts. Adding a column and naming it unconditionally in the
    reader's SELECT made that SELECT raise, a pre-existing blanket `except sqlite3.Error`
    turned the raise into `rows = []`, and a two-revision program was **served as holding
    no revisions at all**: state, label, capture instant and file counts blank, with no
    error anywhere.

    Rule 49 in a schema: a fallback yielding a plausible value hides the failure it was
    written for, and this one consumed the evidence on the way past. The reader asks
    `PRAGMA table_info` and selects what is there; a column the file does not have reads
    as empty, which is the honest answer -- *captured before we recorded this* rather than
    *we recorded nothing*. This bites hardest on the one store that is never rebuilt (rule
    25), because there is no re-analysis that would repair it.

    Found by reading the served JSON and noticing four fields had gone empty since the
    previous request. **No test compares two runs of a server**, and every unit test opened
    the store for writing, where the migration always ran.

64. **The leaf that identifies a tree is the package root's, not the analysed
    directory's.** Two versions of one program are two directories, so the directory's
    name is what a reader recognises them by -- an instant only says when we read the
    bytes. But `target.name` for a `src/` layout is the string `src`, which names every
    src-layout program ever analysed and therefore identifies none of them.

    The right leaf is the one the upward walk for `pyproject.toml` already finds, so the
    fix hoists that walk above the sidecar open and retires a duplicate of it. **Invisible
    to every fixture in the suite**, because none of them has a `src/` to be wrong about,
    and correct on the first real run only by accident of where the fixtures put things --
    which is the same shape as rule 61: the sample program had no `pyproject.toml`, so
    nothing exercised the writer at all.

65. **Name a set for where it is, not for what befell it.** The change worklist reported
    `added` and `removed` -- both of which are claims about *time*, from a store whose only
    instant is when it read the bytes. They were correct only because the default pairing
    happened to make the base the newer capture; analysing an older copy inverted the whole
    view, confidently, with no symptom.

    The bands are `only_in_base` and `only_in_compared` now, which is a fact about set
    membership, and *added* / *deleted* are an interpretation the **reader** owns, stated
    on a strip that is always on screen. Two things fall out and both are load-bearing.
    Flipping the interpretation costs **zero queries**, because nothing was baked in. And
    the tool stops asserting something it cannot see, which is the whole of design rule 1
    applied to a vocabulary rather than to a filter.

    Its guard is worth copying: assert over the **keys the answer carries**, not over the
    source, because what misleads a reader is what reaches them. And assert over the
    *parts* of each name -- the first version tested whole keys, and `routines_after`
    contains the forbidden word rather than equalling it, so the one mutation that survived
    did so because the guard was weak rather than because the mutation was (rule 59).

66. **An order the tool cannot defend is not an order.** Which of two versions is newer is
    often knowable -- a program states a version, and comparing two of them beats any
    default. Three things make that a false claim if they are skipped, and none of them has
    a symptom.

    **`1.10.0` sorts below `1.2.0` as a string**, so the comparison is over integer tuples
    and is computed where it can be tested rather than in a template. **A date and a
    release number are both orderable and are not orderable against each other** -- the
    keys compare perfectly happily, so the *kind* travels with the key and the caller
    refuses across kinds. And two versions that are **equal**, or one carrying a
    prerelease suffix, rank *nothing*: `1.0.0-rc1` precedes `1.0.0` under semver and
    follows it under other conventions in the wild, so choosing would state an order
    nobody can defend. Rule 1 three times over, in a place where every wrong answer looks
    exactly like a right one.

    Its companion, about the *setting* rather than the ordering: an answer that is
    sometimes derived and sometimes chosen is **three states, never a boolean**. `auto`
    must re-derive when the subject changes, or an explicit choice made about one pair is
    carried silently onto the next -- rule 51 with the reader's own decision as the thing
    that drifts. And each state must say which it is: derived, chosen, or assumed for want
    of anything to read. A colour a reader cannot account for is worse than no colour.

67. **A control's value is state, and the browser will supply one if you do not.**
    A `<select>` rebuilt by script has its pre-reload value **restored by the browser**,
    and that restoration outranks the `selected` attribute the code wrote. So after a base
    switch the pair control named the pair the reader had been on *before* the switch,
    while the strip beside it correctly named the new one -- one control, two claims, and
    the markup was the one that lost. Every source-reading check passes: the attribute is
    written, on the right option, for the right reason.

    Assign the value from state rather than defending against the restoration. A control
    that derives its value from state has nothing left for a restoration to disagree with.
    This is rule 48's lesson in a form `elementFromPoint` cannot reach -- what the DOM says
    and what the browser has since done to it are different questions -- and like rule 48
    it was found only by driving the thing.

    Its companion, and why it could hide as long as it did: `chosenPair()` returns
    `{base, compared}` and the control read `.from`, a key it has never carried. Undefined
    is not an error, so the marker was the empty string on **every** build and the menu
    opened on the wrong row after every reload. Rule 44 one step further in -- not a field
    the *server* does not send, but a field this file does not send itself.

68. **A restore is a setter, and it must do what the setter does.**
    Rule 55's companion says *one truth about what is open, and whoever sets it does the
    work*. `setGroupOpen` did the work; the boot that restores `navOpen` from storage did
    not. So a reader who left the Changes group open reloaded into a group sitting open
    under *"two versions -- open to compare them"* with nothing to open: a note telling
    them to do the thing they had already done. It had been there since the group was
    built and takes a reload to reach, so it was invisible -- until a base switch, which
    reloads, so every switch out of an open group landed on it.

    The fix routes from the table (rule 36), so a group that declares an `onOpen` is
    covered without anyone remembering. And it went wrong once on the way, which is the
    part worth keeping: written as `state.navOpen[g.id]` it fetched nothing on a fresh
    profile, because openness has **two** expressions -- what the reader arranged, and the
    table's own default for a group they have arranged nothing about -- and `groupOpen()`
    is the one place that knows both. Rule 51 inside the fix for rule 51.

69. **Contrast says whether a colour can be *read*; it says nothing about whether two
    colours can be told *apart*.** Design rule 6 clamps customisation at a contrast ratio
    and that is right and insufficient: it is a claim about one colour against its ground,
    and a channel that separates two meanings is making a claim about a *pair*.

    The dashboard's own palette passed the first bar and failed the second for its whole
    life. `--sev-broken` `#b91c1c` and `--sev-suspect` `#92400e` are 6.47:1 and 7.09:1 on
    white — comfortably legible, and **to a deuteranope the same colour**: simulated, they
    are ΔE 5.3 apart, the worst number in the product. The difference pair was little
    better at 12.7. Every check that existed passed, because every check asked the
    answerable question rather than the useful one.

    So a set states both: contrast against each ground it is drawn on, and **separation**
    as the worst CIE Lab ΔE across normal vision, deuteranopia and protanopia (Viénot,
    Brettel & Mollon 1999). The worst, never an average — a pair obvious to most readers
    and invisible to some is not a pair that works, and averaging is the arithmetic form of
    not caring.

    Two things the arithmetic settled that guessing would not have. **Red and green cannot
    be rescued by tuning**: every chroma and every lightness inside that hue family measures
    between 4 and 14, so only changing the hues changes the answer. And **a difference in
    lightness survives colour blindness where a difference in hue does not** — so forcing
    both colours of a pair to the same contrast ratio throws away the one axis that always
    works. The shipped dark pair is separable partly because it sits at 6.06:1 and 9.63:1,
    which nobody intended.

    **A channel has a capacity, and this one is now full** — found 2026-08-31, adding a
    sixth meaning to the difference channel. Sweeping every hue at every saturation and
    lightness, against every colour in all three sets plus the two grounds, in all three
    vision models: nothing clears a useful bar in **both** themes. The light theme is the
    binding constraint — red, orange, green, blue, violet, purple and two greys are already
    spent, and what is left is yellow, which cannot hold 3:1 on a light ground.

    Two things follow. The colour chosen for `mixed` is the best available rather than a
    good one (worst ΔE 29.8 light, 45.3 dark), and it is stated as such. And **a seventh
    meaning cannot be added by colour at all** — the next one wants a different channel,
    which is what design rules 4 and 5 have been saying since before there was a reason to
    listen. Knowing a channel is full is worth as much as knowing a pair is separable.

70. **The version on screen decides which bytes, and the sidecar cannot know which that
    is.** There is one `source.db` per program holding every revision, and its own default
    is the newest snapshot -- which is the right answer only while the newest is also the
    version being read. It stopped being that the day a reader could switch the base, and
    six readers went on asking the store rather than the base: the code browser, the file
    list, the search, `/api/source`, the inspector's definition and the cover's line count.

    Serving Mensores' older graph returned `_queue.py` at **674 lines with the 595-line
    version's marks laid over it** -- every link past the first divergence underlining the
    wrong characters, a margin describing lines that had moved under it, and a footer
    naming the revision the *bytes* came from while the facts came from another. Nothing
    raised. The page looked exactly like a page that works, which is what a file always
    looks like.

    Rule 51 in the shape that rule was written for: a default that was correct while there
    was one version and one graph, and wrong for every caller acquired since. The base
    names the revision and every reader is handed it; a sidecar that does not hold that
    revision is `None` and a **stated absence**, never the newest bytes substituted for the
    ones asked for (rule 49 -- the plausible value is what hides the failure).

    Found by pointing the tool at its own two revisions and comparing what came back, not
    by any test: every unit test opened one revision, where the default is right.

71. **A class name is global, and a stylesheet gives no warning.** The code browser's file
    rows were marked `chg-same` / `chg-mod` / `chg-one`. `.chg-mod` already existed -- it is
    the change worklist's *module* label, `font-size: .7rem; color: text-faint` -- so every
    **modified** file rendered smaller and greyer than the unchanged ones, which is the exact
    inverse of what a mark is for. Every check passed: the markup is right, the handler is
    right, the class is written, and nothing anywhere is dead.

    Its companion, found in the same row and the same way: **markup another function
    rewrites is not the markup that renders.** `dressNavItems` gathers a row's loose text
    nodes into a `.navlabel` and re-inserts it immediately before `.n` -- so an element
    written between the file name and the count is moved *in front of the name*, and the row
    read `mensores/scriba/ ○ _queue.py`, a glyph inside a path.

    Both are the same instruction one level below where the checks look: what this function
    writes and what the reader sees are different questions, because a stylesheet and a
    later pass both get a say. The classes are prefixed and every rule that styles one is
    scoped to `.codefile`, asserted in both directions so a name taken later cannot reach
    these rows. Found by looking at the pane, which is now the fourth consecutive session
    that has paid for itself.

## Anomalies: the discipline

`anomalies.py` reports what looks wrong. It exists under one rule:

> **Every finding must state what would make it a false alarm.**

This is not politeness. On the first run against a live codebase, *six confident
findings in a row were defects in this tool*, not in the program being read. A
finding without its `blind_spot` is a guess wearing a uniform.

- **Severity** (BROKEN / SUSPECT / INFO) says what it would mean for the program.
- **Confidence** (CERTAIN / PROBABLE / POSSIBLE) says how sure the tool is.
- These are different questions. Never blur them.

Ingest must never fail on a broken program: unparseable files yield recorded errors,
colliding definitions keep separate identities, and an edge lost to ambiguity is
recorded as `LOST_EDGE` rather than silently omitted — a missing connection must be
visible, or a broken program documents as a smaller working one.

`dunneflow check` exits non-zero only on BROKEN, so it can gate CI.

**Before adding a detector**, verify a sample of its findings against real source. If
the first thing it reports is a limitation of DunneFlow, fix the limitation instead of
shipping the detector.

## Dashboard: design rules

A reading tool for someone orienting in code they did not write. Settled shape: a local
server (`dunneflow serve`), three panes — navigator, centre view, inspector — where the
centre pane is a mode toggle (graph / table / document) over one shared selection, not
three destinations. **Vanilla JS + deck.gl, served by `http.server`** — no framework, no
Node at runtime or build, deck.gl vendored into `web/vendor/`.

*Astro 5 + Tailwind 4 was ratified here and has been struck, on evidence.* It was chosen
before the graph became the defining requirement and before the ratified mockup turned
out to be vanilla with a hand-authored 832-line token stylesheet and no Tailwind at all.
The graph must be WebGL whichever stack wins, so Astro bought a build step and Tailwind
bought a rewrite of settled CSS, neither of which serves the thing the tool is for.

1. **No filter is ever silent.** A filtered view states what it removed, in counts, with
   the hidden set one click away. Same discipline as `LOST_EDGE` and rule 8 above: a
   missing thing must be visible, or the reader mistakes a slice for the whole. Knowing
   what you are *not* looking at is the state-awareness problem the whole UI turns on.

2. **When two options are genuinely interchangeable, build both and make it a Setting.**
   Real use decides; the loser can be retired later on evidence, which is why usage is
   counted locally. This is not licence to defer every decision — it applies only when
   both choices are actually good.

3. **Everything dimensional is stored in `rem`, never `px`.** One root scale multiplier
   must resize the whole surface together — type, column widths, row heights, padding,
   icons, graph nodes. A width stored in pixels is a width the multiplier cannot reach,
   and the layout then breaks for everyone who is not its author.

4. **Colour is the scarcest channel; spend it on one dimension at a time.** Nine boundary
   kinds are not nine distinguishable colours, and the temporal layers still need added /
   removed / modified. Kind is icon plus label; colour follows an explicit "colour by"
   selector.

   **Shape is the channel that was going spare, and the diagram spends it on kind.** Five
   kinds, five silhouettes, in Mermaid's own vocabulary — a process box for a routine, a
   hexagon for a constant, a stadium for a boundary — which is what frees colour to go on
   saying *what changed*. Offered as a **set** rather than as a shape per kind, on exactly the
   argument rule 69 makes about colour sets: choosing them one at a time lets two kinds land
   on one outline, which is the channel saying nothing, and a sixth kind then arrives with no
   shape at all. Unlike a colour set there is nothing to measure — a shape has no contrast
   ratio and no separation — so the sets are offered because they read, not because they
   cleared a bar, and the Settings page says so rather than implying a rigour it does not
   have.

5. **Confidence is shape, not colour.** Solid edge = CERTAIN, dashed = INFERRED, plus a
   global "hide inferred" toggle so the defensible skeleton can be read alone. Severity
   and confidence stay separate channels, exactly as in `anomalies.py`.

6. **Customisation is clamped, and says why.** Settings may change colour and size within
   limits that keep text legible — 4.5:1 for body text, 3:1 for large text and chrome,
   computed live and shown beside the swatch. A refusal states its reason, the same way a
   finding states its blind spot.

   **Colour is offered as broad sets, not as a picker per token** — Tom's call, and his
   reason is that colour decisions are personal. A set covers the channels where colour
   separates one *meaning* from another and carries a light and a dark variant; the reader
   chooses between sets rather than mixing their own, so every combination that can be
   reached is one that has been measured. What each set states is its contrast **and** its
   separation (rule 69), because a set that clears the first bar and fails the second is
   the shipped palette's own history.

7. **Accessibility limits are documented in the product, not apologised for.** A node
   graph stops being meaningfully screen-reader navigable past roughly fifty nodes; the
   complete table beside it is the accessible path, not a fallback. Mermaid's generated
   SVG can be themed but its focus order cannot be controlled. Pan and zoom need keyboard
   equivalents. These live on a visible Accessibility page.

8. **A program is never alone.** Calling one program "one program" is a convenience, not a
   fact. Every node carries a source status: `ANALYZED` (we have the source),
   `KNOWN_INTERFACE` (we see the call leave and know protocol, verb, destination, port,
   timeout, retries, payload — SAP, Oracle, a REST endpoint), or `OPAQUE` (something
   leaves and we cannot say to what). Externals are first-class nodes at the boundary,
   badged as outside our control. `net_calls` already records this. Pointing DunneFlow at
   an external's source flips it to `ANALYZED` in place — cross-program stitching is not a
   new UI, only a fuller one.

9. **The anomaly view is a worklist, not a report.** Observed, not assumed: the first
   move on opening the dashboard was to jump to SUSPECT and start clearing findings one
   by one — BROKEN would have come first, and a red table would have been clicked before
   either. Red and amber are read as a call to action. So findings are traversable
   (`j`/`k`, next/prev), carry triage state, and show progress. Triage has three
   outcomes, and the third is load-bearing: *the blind spot applies*, *real and
   acknowledged*, and *this is a DunneFlow defect*. The third is a different pile,
   because a detector whose findings are repeatedly dismissed that way is the detector
   to fix — the rule under "Before adding a detector" applied after the fact.

10. **Documentation is evidence, even though it is never code.** Rule 9 keeps docstrings
    out of *code-shaped* detectors, because a sentence about a statement is not a
    statement. It does not mean prose is worthless -- for a glossary, being prose is the
    qualification. A program's vocabulary is almost never defined in its code: Mensores
    states its entire Latin naming scheme in `NAMING.md` and defines `mensor` in
    `PROJECT.md`, and DunneFlow saw neither. Look for the definition before generating
    one, and prefer a quotation with a file and line over anything a model writes.

11. **Documentation and source are equal inputs; neither may be assumed present.**
    `analyze` reads both, and each is a check on the other. But documentation is often
    absent, partial, or wrong -- porting five abandoned games taught that the badly
    documented case is the normal one -- so every reverse-engineering path must keep
    working with no documentation at all. Never make a doc-derived fact a prerequisite
    for a code-derived one.

12. **A cached graph is valid only if the source AND the tool that read it are
    unchanged.** The file cache keys on source content, so editing `detectors/*.yaml` --
    the extension point, and therefore the thing edited most -- left every cached fact
    answering the old rule while the new rule silently never ran. The cache key is now
    `SCHEMA_VERSION` plus a hash of every detector file, and a mismatch discards the
    graph and says so. **The reader is in that key too**, and for a while it was not:
    the rules were hashed and the extractor applying them was not, so artefacts, the
    comment fix and constants each changed what extraction *meant* while every cached
    file stayed byte-identical -- saved each time only by someone remembering to bump
    `SCHEMA_VERSION` by hand, which is precisely the half of the rule a hand forgets.
    `code_extraction_inputs()` and `doc_extraction_inputs()` name the files, per corpus,
    and a test asserts membership rather than re-deriving the list.

13. **Every reported meaning must carry its provenance, and the provenance must open.**
    A definition or a naming rule is a claim, and a claim without its source is an
    assertion wearing a uniform -- the same failure `blind_spot` exists to prevent on the
    anomaly side. Each tier proves itself differently: a **quoted** definition proves
    itself with a file and line the reader can click through to and read in context,
    highlighted, in the surrounding source; a **measured** claim proves itself with the
    query that counted it, reproducible via `dunneflow query`; an **inferred** one cannot
    prove itself at all and must say so. Never render a definition without the route back
    to where it came from.

14. **Deterministic by default; egress is scoped, never a switch.** Everything DunneFlow
    reports is read from local files by local code, and the product is complete that way.
    Anything needing a model lives on its own page -- never buried in Settings, never run
    during `analyze`, never on a schedule -- and is off until turned on. Consent is
    per-corpus, because the surfaces differ: many will send documentation and never
    source. The postures are Off / Documentation / Documentation + identifiers /
    Everything / Local endpoint, each operation declares which it needs, and one it does
    not have stays disabled with the reason shown. Before any run, show the exact file
    manifest that would leave the machine.

15. **Build for the explorer, not only the navigator.** Orientation \u2014 "where do I
    start, what is the shape" \u2014 is the first need, not the lasting one. The way this
    gets used is: see something, get curious, notice something beside it, pull the
    thread, get distracted, learn something never intended. That mode wants different
    furniture, and it is furniture, not decoration:

    - **A trail.** A visible record of the journey, not the hierarchy \u2014 clickable,
      steppable, branchable. Nobody chases a rabbit if they might not find their way
      back; the trail is what makes the detour free.
    - **Threads to pull.** Beside the call graph, the *reasons* a neighbour is worth a
      detour: shares a plan, the other end of an emit, the most commented routine in the
      program. Adjacency by interest, not only by edge.
    - **Somewhere to put what you found.** You go looking for one thing and find
      another; it needs a shelf, or the detour costs you the thread you were on.
    - **Curiosities.** What came out furthest from the middle \u2014 264 comments on one
      routine, four closures deep, a table written twice as often as it is read. Not
      problems. Doorways.

    Judge a feature by whether it makes pulling the next thread easy and rewarding.

16. **A control that renders but is wired to nothing looks exactly like one that
    works.** Eight of eleven left-hand menu items silently showed the graph instead of
    their own page, because a patch to add the missing branch matched nothing and
    reported success. Two defences, both cheap: route from a *table*, so an unhandled
    case logs an error rather than falling through to a default that looks deliberate;
    and run a startup self-check that names any control nothing listens for, with its
    list derived from the source rather than hand-kept so it cannot drift. When editing
    by string replacement, assert the pattern matched -- a silent no-op is the most
    expensive kind of edit.

    **And the same rule with no control at all: a setting nothing reads.** `panels` sat in
    `settings.js` from the first day -- persisted per program, versioned, and named in the
    reset dialog as "panel layout" -- while nothing anywhere read it, so a reset reported
    clearing a layout that had never existed. The pre-merge graph had collapsible panes and
    the merge kept the switch while dropping the implementation. A test now reads the keys
    out of `DEFAULTS` and demands each appear as a **property access** somewhere: every key
    is also a plain string in the list of things to persist, so searching for the bare name
    passes on a setting that is faithfully saved, restored, and never once acted upon --
    which is exactly the failure.

18. **The stack is an abstraction, not an object — so do not draw it.** The 2.5D model
    is a stack of disks, and the disks are the *idea* that groups nodes by height. Drawing
    the plates draws the scaffolding as though it were the content, and at fifteen
    thousand nodes it reads as a solid cylinder. Nodes are tiny dots — 1.4 to 3.6 pixels,
    degree moving the size across two pixels rather than twenty, because any radius that
    reads as a disc fuses the whole thing into a mass. Plates exist as a toggle, off.

    **The dots stay tiny; what changes is how many there are.** Tom drove it and said the
    picture was hard to comprehend at 10,015 nodes and 14,254 edges, and the answer was
    neither bigger nodes nor fewer of them but a second **level of detail**: `module` folds
    each file into one node and each boundary kind into one, giving 578 and 1,505. This
    rule's own reasoning is what forces that — if a node cannot be made big enough to read
    without fusing the picture, the number of nodes is what is wrong. Both levels are
    served side by side and the reader chooses; nothing is dropped at either.

19. **Edges are shown on demand, never by default.** All 13,277 at once do not describe a
    program, they erase it: everything else goes under a haze. Nothing but nodes is drawn
    until a disk or a node is selected, then only the edges the selection touches.
    Selecting a node takes **one** hop — two hops is most of the program again. Unselected
    nodes dim rather than vanish, so a subset stays legible inside the shape it belongs to.

    *"…and only once the camera has stopped" is struck, and is now a Setting defaulting to
    on.* That clause was a speed measure carried over from slower renderers, and it is not
    what this one needs: everything drawn is uploaded once as flat typed arrays, so a
    turning camera re-uploads nothing and the links cost the same moving as they do still.
    It also worked against the picture. **A rotation is how the connections between plates
    read as depth rather than as a flat tangle**, so stripping the edges during one hides
    precisely what the reader turned the view to see. Off is kept for a slower machine or a
    very large selection.

    The **on demand** half stands unchanged, and it is the half that carries the rule: what
    is drawn is still only what the selection touches.

    The consequence is that **the filter is the interface**, not a refinement of it. The
    legend is therefore the main way in, and is built for it: fifty-one disks, clickable,
    three columns interleaved a fraction of a row apart so rows nest instead of sharing
    baselines — the whole index in a third of the height one column needs. It is HTML,
    not text in the scene, because a legend that spins away with the camera is not a
    legend.

20. **Frame the bounding cylinder at the tilt in force, and always offer a way back.** A
    bounding sphere is rotation-invariant and therefore safe at every angle by being
    wrong at nearly all of them — it reserves room for the worst case, so the subject
    sits small however it is turned. The stack is a cylinder and orbiting about Z leaves
    its footprint circular, so tilt is the only term that changes the silhouette and a
    snug fit is two terms. Projection is **orthographic**: under perspective the near
    plates magnify and the far ones shrink, rendering a stack of equal disks as a tapered
    cylinder — the exact shape the model exists not to be — and orthographic zoom maps
    world units to pixels exactly, so framing is arithmetic rather than a fudge that
    holds at one window size. A snap-to-fit control is not a convenience: nothing may
    strand the reader off-screen with no way back.

21. **A blank canvas must say why it is blank.** Hardware acceleration switched off in
    the browser gives no WebGL context, and the symptom is an empty page that looks
    exactly like a broken program. The failure names itself, gives the remedy, and keeps
    the raw driver string underneath as evidence. Diagnostics live *on the page* —
    canvas size, device pixel ratio, GL renderer, and where the geometry projects in
    screen space — because "drawn off-screen" and "not drawn" are indistinguishable by
    looking, and a developer cannot run a console in someone else's browser. A test
    pattern of three markers at known positions splits the question in two: if they draw
    and the graph does not, the fault is our geometry; if neither draws, nothing is
    reaching the screen at all.

22. **Spread is three axes, and the fourth control is zoom.** X and Y widen a plate, Z
    is the gap between plates, and they are independent because they answer different
    questions -- a plate too dense to read wants X and Y, a stack too tall to frame wants
    Z. Scaling all three by the same factor is *zoom*: under an orthographic projection
    uniform scaling and zoom are the same operation, so a "linked" slider would be a second
    way to do what the mouse wheel already does. Every scale is computed from an unscaled
    base copy of the payload's positions rather than applied in place -- 2x then 2x again
    is 4x, and a slider dragged back to 1 must come home.

    It is what makes large nodes usable at all. Billboarded spheres fuse into a solid mass
    once they are big enough to look at, and at 14x no amount of Z helps, because the
    crowding is *within* a plate. Widening is the answer, not shrinking the nodes.

    **A fifth control joined them and it is not an axis: plate width, by what a plate
    holds.** The three axes widen every plate together; this says how much of that width
    each plate has earned, at `sqrt(n / n_largest)` on **real nodes** — a shadow is never
    drawn (rule 23), so the density a reader sees is nodes over area however many placement
    devices share the disc. It is a *strength* between the uniform stack (0) and area
    proportional to content (1), interpolated so that 0 comes home to exactly the
    arrangement the server placed, and it is **per level** for the same reason `MIN_DISK`
    is: Mensores spans 12.85x across its routine plates and 5.32x across its module ones,
    which is a different judgment about a different picture.

    Two things fall out that are worth keeping. **Where a proportional scale is anchored is
    a zoom, not a decision** — marks are drawn in pixels and fit frames whatever it is
    handed, so anchoring at the largest plate and at the smallest are the same picture at
    different zooms, and the first is chosen only because nothing then grows past the
    radius the server placed it at. Measured: the bounding cylinder is **999.8 x 3391.5 at
    both ends of the dial**, so design rule 20's framing is untouched. And **everything that
    sits on a plate's circle has to ask that plate how wide it is** — the nodes, the plate's
    own outline, and the you-are-here arrow standing on its rim were three expressions built
    from one constant, which is correct at one width and a lie at any other (rule 51).

    **The plate as a diagram, and the billboard question is settled at one angle only.**
    Rule 22 billboards a node because a sphere has *no orientation*, so a picture of one must
    not have one either. A labelled box is the opposite case — it has a top and a reading
    direction — so one held facing the camera has stopped lying on the plate it belongs to,
    and the boxes are built flat. Built flat and then **looked at**, which is what settled it:
    the tilt costs nothing a reader notices (a label loses 43% of its height at 35° and stays
    perfectly readable), and the **orbit** costs everything — text lying in the plate inherits
    the in-plane rotation, so looking straight down at a plate gives a page of names on a
    diagonal. So a box gives up its bearing and nothing else: turned about **Z alone**, it
    still lies flat, still foreshortens with the tilt, and its reading direction faces the
    reader at every orbit angle. At orbit zero it is identical to leaving it alone, which is
    the test that it takes nothing away.

    Sized in **pixels**, like the dots and the labels, which is what makes the overflow answer
    work: boxes are placed busiest-first and only where they do not overlap at the current
    zoom, everything else stays a dot (rule 19 — nothing leaves the picture), and the number
    still a dot is stated with the way to get more (design rule 1). Measured on Mensores at a
    1280×760 pane: `pkg:mcp` lights 360 and draws **102** boxes; the worst plate lights 1,319
    and draws 86, placed in **2.3 ms**.

23. **Hiding and collapsing are separate switches.** Hiding decides whether an unselected
    plate draws; collapsing decides whether it still takes up room. Wanting the second
    without the first is ordinary -- it is how eight plates out of fifty-two stop reading
    as eight plates scattered down a tower of empty slots. Merging them into one control
    makes "show me these eight, packed" unreachable.

    Two things follow. A collapsed plate is one *nothing is looking at*, so with no
    selection nothing collapses and the control quietly does nothing rather than emptying
    the stack -- the same reasoning as edges on demand. And which plates are unused is a
    function of the selection, so it is recomputed when the selection changes and not only
    when the control moves, or the stack keeps the shape of the previous selection while
    confidently showing the current one. The count is stated (rule 1): a shorter stack and
    a smaller program are indistinguishable by looking.

24. **A pane collapses to a rail, and the rail says which pane it is.** Three panes over
    one selection is the settled shape, but the inspector answers "what is this thing" and
    holds 22rem to say nothing when nothing is picked. So every pane folds, and folding
    leaves a rail behind: a pane that simply disappears is a silent filter, and the reader
    has no way to know the layout is a choice rather than the product. The label is rotated
    rather than reduced to an icon, because an icon rail is a puzzle.

    The grid **tracks** carry the state, not the panes -- collapsing a pane without
    collapsing its column leaves a hole exactly the width of the pane that is no longer
    there. The inspector rails itself while nothing is selected and returns when something
    is, but an explicit fold outranks that: auto may only ever *close*, or the reader's
    choice reopens underneath them. And opening the rail with nothing selected has to
    suspend the auto rule, or the pane reopens and instantly re-collapses, which reads as a
    broken button.

    Adding chrome to a pane broke something else, worth keeping: the Ways in / Explore
    reorder moved a group before `firstElementChild`, which swept it in front of the new
    fold button and put the collapse control a third of the way down the pane. **An
    ordering rule that names a position rather than an identity breaks the moment anything
    is added beside it.**

25. **The primary way in is a pane, not furniture.** The legend was 26rem of opaque surface
    pinned over the canvas it indexes — design rule 19 calls it the main way into the graph,
    and it was drawn as though it were decoration. It cost nothing in visible canvas to fix,
    because the pixels under it were never visible: what changes is that the pixels *beside*
    it are now honest, so snap-to-fit frames the stack in the space the stack actually has
    instead of centring it under the panel.

    That is the tell in general. `fitView` once carried `panels.disks ? 0.60 : 0.90` — a
    fudge factor kept in sync with a UI state by hand — and when the two applications merged
    the term was dropped while the panel stayed, so fit went on burying half the subject.
    **A framing correction for something floating over the picture means the thing floating
    should own a track.** With the legend as a grid column, `clientWidth` *is* the drawable
    width and the margin is plain arithmetic again, which is the same reason rule 20 chose
    orthographic over perspective.

    Two collapse idioms, because there are genuinely two shapes: a full-height side pane
    collapses its **track** and leaves a rotated rail (rule 24); an overlay box floating on
    the canvas collapses to a horizontal **ribbon** — its own header strip, still stating its
    summary, because a strip reading only "controls" is rule 24's icon rail lying down.

26. **The list and the picture are one instrument, and it has to run both ways.** Pick a
    routine on the left and the stack highlights it with everything that calls it and
    everything it calls; click a node in the stack and the list moves to it and marks it.
    Only one of those directions is a lookup. **Both of them is how a thread gets chased**,
    which design rule 15 says is what to build for, and either alone leaves the reader
    translating between two views by hand.

    Three things that are not optional once it runs both ways. The list must **not move the
    camera** — a list you can click through is useless if every click throws away where you
    were looking — so an off-screen selection is *stated* and framing it is one click away
    (rule 20's reasoning applied to selection rather than to the camera). The automatic
    scroll that follows the graph must not fight a deliberate click, so it only acts when
    the row is genuinely out of sight. And **plates are the missing answer**: rule 18 keeps
    all fifty-two undrawn, but the two or three a selection touches are the only thing on
    screen that can say *which plate am I looking at*, so they are drawn faintly and named
    on the HUD — the outlines say where, the names say what, and one without the other is
    half an answer.

17. **View state is local, and exported deliberately.** Column widths, density, chosen
   columns, saved filters, and expansion state persist per program, keyed by stable
   identity so they survive switching revisions. They travel only when someone exports
   them, and a recipient always keeps their own scale multiplier.

## Adding a language

Write one extractor that emits `FileFacts`. Nothing else changes — the resolver,
renderers, and orientation queries know nothing about any specific language. Swift is
the obvious next one.

## Shared library: dunnecorp-shared

This project consumes `github.com/aacloudguy/dunnecorp-shared`, DunneCorp's
shared library of code, Claude Code skills, governance templates, and CI
patterns.

**Before writing any new utility, helper, workflow, skill, or template, check
whether it already exists there.** The library exists specifically because the
same concepts were being rebuilt independently in each repository.

How to check, in order:

1. Read `catalog.json` in the shared library and match the task against the
   `use_when` field of each asset.
2. If an asset matches, use it. Add the dependency rather than reimplementing.
3. If something close but not exact exists, prefer extending it in the shared
   library (via a PR there) over writing a local variant here.
4. Only write something new here when nothing comparable exists, or when the
   need is genuinely specific to this project.

If the library is not checked out locally, read the catalog directly:

```bash
gh api repos/aacloudguy/dunnecorp-shared/contents/catalog.json \
  --jq '.content' | base64 -d
```

A local checkout exists at `../SharedCode`.

### Contributing back

If you build something here that is reusable, it belongs in the shared library.
Open a PR against `dunnecorp-shared` following its `CONTRIBUTING.md`: add the
asset, register it in `catalog.json` with a `use_when` trigger, and include the
required ADR/CMR record. Then depend on the new tag from here.

DunneFlow itself is a candidate for `packages/python/` once it settles.
