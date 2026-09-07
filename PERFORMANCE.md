# DunneFlow — the measured budgets

Every performance figure this project has taken, with the budget it was taken against and
the conditions it was taken under. `CLAUDE.md` carries the three verification gates; this
file carries what "fast enough" means and what it was measured on.

Two things to read here before quoting any row. **A cold row is the external volume and
nothing else** — the source tree lives on a slow external disk, cold reads cost far more
than warm ones, and several rows are stated as ranges because the same query on the same
files varies by a factor of forty. And **a row states its conditions where they are
load-bearing** — canvas size, framing, and plate selection for the frame-rate rows —
because retaking one without reproducing those is a different measurement under the same
label (rule 24).

An absent row is absent rather than estimated. Rule 38: a browser-automation tab is given
no animation frames, so anything needing a rendered frame does not exist there.

## Performance budget (measured on mensores: 623 files, 184k lines)

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

**One plate, opened** — `/api/plate`, measured 2026-09-05 on Mensores at routine level:
53 plates over 15,870 drawn things, the largest holding 991.

| Measure | Budget | Measured 2026-09-05 |
|---|---|---|
| One package plate, answered | < 200 ms | **2.4–9.7 ms** (49 to 959 nodes) |
| One plate beyond the boundary line | < 200 ms | **14.8–15.3 ms** |
| The payload it reads, warm store | < 2 s | **1.31 s** |
| …the same on the first open of a cold store | — | **10.0 s** — the external volume |

**The two bands cost differently and the reason is in the query, not the size.** A package
asks `FOLD_CALLS_IN`/`OUT` over its own member ids, so it scales with what it holds — 2.4 ms
for `pkg:mensor`'s 12 nodes, 9.7 ms for `pkg:quaestor`'s 926. A plate *outside* the program
cannot: a boundary node's id is `bnd:<kind>:<target>`, which those queries do not match at
all, so it scans `BOUNDARY_EDGES` and `ARTEFACT_EDGES` whole and lands at a flat ~15 ms
whatever it holds. `ext:STDIO` with 991 nodes and `ext:NETWORK` with 9 cost the same.

**The 1.31 s payload row is not `_r_graph`'s ~120 ms and must not be quoted as it.** That
figure was taken on a smaller program; this is `build_payload` on a 100 MB graph. It is
paid once per `(level, minDisk)` and cached on `_Base`, and a plate asked for at an
undrawn altitude pays it — which is the right way round, since the reader who asks about a
plate is about to look at it. The cold row is the external volume and nothing else.

**What is absent: the pane rendered.** The plate inspector was driven and measured entirely
through the DOM — the crumb, the trail, the sections, the member marks, all read back from
a live page — and **never seen in a real window**. Rule 38, and rule 48 besides: every
click here was a dispatched `MouseEvent`, which proves the handler and not the path to it.
The automation tab captures 784 px of a 1,259 px viewport, so the inspector at x=1012 is
outside every screenshot taken of it. This adds to the standing debt rather than paying it.

*Rule 83, minted later, corrects half of that sentence.* Sight stops at 784 px of 1,259; the
**pointer never did** — the capture path divides by `devicePixelRatio` and the input path
does not, so the two frames differ by exactly the dpr and a click computed with
`784 / innerWidth` reaches anything in the viewport. Left standing as written, with the
correction beside it, because it is what these figures were taken under.

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

The doorway panel — ten measured extrema over the whole program, held on the base and
computed on the first ask:

| Measure | Budget | Measured 2026-09-01 |
|---|---|---|
| `/api/curiosities`, warm | < 500 ms | **0.5–0.7 ms**, held on `_Base` |
| …the first ask of a session | < 5 s | 0.2 s – 1.7 s, and it is the disk |
| …the ten queries themselves, warm | < 500 ms | 106 ms |

Not paid at boot, unlike the two vocabulary lanes, and the difference is the bargain: a
thread is asked on every selection, so a lazy first call there would stall the reading
loop; this is a page a session either opens or never does (rule 45).

**One family was 7.47 s and is 54 ms**, and the fix is the shape every one of them now
uses. Written the obvious way, the call-argument CTE joined 43,926 rows to `calls` and
`routines` — and did it four times over, once per reference to the CTE. Materialising only
the key and the measure, and resolving the winner's name once for the one row that won,
is the whole difference. `MATERIALIZED` is stated rather than hoped for.

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

| Measure | Budget | Measured 2026-09-01 |
|---|---|---|
| `/api/changes`, warm | < 500 ms | **480 ms — and that is 20 ms of headroom** |
| …the same before the arguments and constants landed | | 266 ms |
| …with the comment lane added | | **no measurable change: 451 → 448 ms, median of four** |
| …with the docstring and module lanes added | | **+3 ms: 451 → 454, median of eight alternating** |
| …first comparison of a session | < 5 s | **1.4 s – 23 s, and it is the disk** |
| …the same, cached | < 50 ms | 0.7 ms |

**The warm row has almost nothing left and is recorded as such.** Comparing what a caller
passes and what a constant holds costs **+214 ms**, nearly all of it one scan of the largest
table in the store — 43,926 arguments a side, joined to `calls` to reach an owner. Measured
like for like: six builds in one process against a warm disk, the same corpus, this commit
and the one before it (270 → 493, then 266 → 480 once the scan stopped building a
`sqlite3.Row` per row and took SQLite's own tuples, which is 202 ms against 165).

Three formulations were measured and the fastest was **rejected**: a `group_concat` digest
per caller is 164 ms against 188 for two scans diffed in Python and 364 for `EXCEPT` both
ways, but SQLite does not specify the order an aggregate concatenates in, so two identical
argument sets laid out differently in two files would digest differently and report a
difference that is not there. Rule 1, for 24 ms.

**The cold row is the external volume**, reading a 31 MB graph the server has never
touched: 13.1 s, then 2.5 s, then 317 ms on three runs of the same comparison in 2026-08-29,
and 23.4 s / 1.2 s / 0.5 s on three server restarts a session later. It swings by a factor
of forty on the same query and the same files, which is why it is stated as a range. It was
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

**Document mode, lane 1** — the program's own 2,064 documents, measured 2026-09-03:

| Measure | Budget | Measured 2026-09-03 |
|---|---|---|
| The list: 2,064 rows in 13 class groups, first paint | < 200 ms | 56 ms |
| …repaint, and the filter over all 2,064 | < 50 ms | 5 ms · 2 ms |
| Open a document (fetch + render + paint), ordinary | < 500 ms | 279 ms (`glossary.md`) |
| …the worst case, 1.32 MB | < 1 s | 668 ms (`.groma/ISSUES.md`) |
| Paint one already-fetched document | < 100 ms | 4 ms · 66 ms (worst case) |
| Repaint on any other change | < 50 ms | 2 ms |

**The filter hides rows rather than rebuilding the list**, and there are two reasons rather
than one. 2,064 rows rebuilt per keystroke is the cost; rebuilding also destroys the
`<input>` being typed into, taking the focus and the caret with it — which reads as a box
that stops working after one letter. So the query is deliberately *not* in the cache key, and
2 ms is what a narrow write over 2,064 rows costs.

**A document is rendered once, when it is fetched, never at paint time.** Parsing is the one
cost a subtree cache cannot save — the cache holds a node and the parse happens before there
is one — so the 40–72 ms of markdown parsing is paid on the fetch and every repaint after it
is 2 ms.

**The document renderer** (`prose.js` + `markdown-it`), measured 2026-09-03 on Mensores.
It is cheap, and the interesting thing about it is that it is cheap:

| Measure | Budget | Measured 2026-09-03 |
|---|---|---|
| Fetch and configure the library, lazily | < 500 ms | 29 ms |
| Parse and render `.groma/ISSUES.md` (1.32 MB) | < 500 ms | 40–72 ms |
| 230 documents, 4.0 MB of prose, with their fetches | — | 927 ms |

The library is **125 KB fetched on first use**, not at boot — most sessions never open a
document, and two concurrent callers produce one script tag and one instance.

**The chain design rule 13 depends on was verified rather than assumed.** Every heading
`docs.db` recorded must be findable in the rendered DOM at exactly its own line, or a
citation opens a document *near* where it was read from. Measured over a spread of the
corpus: **825 of 825 headings across 60 documents**, and 782 of 782 across a second sample
of 41 — including 27 documents carrying YAML frontmatter, which is the case most able to
break it silently.

**Document mode, lane 2** — the map's own eight documents, measured 2026-09-03 on
Mensores. The pane's whole cost is **layout**, and the numbers say so plainly: on
`routines`, 4,786 rows over 566 groups, building the markup is **73 ms**, parsing it into a
detached node **329 ms**, and laying it out **2.0 s**.

| Measure | Budget | Measured 2026-09-03 |
|---|---|---|
| `/api/document`, the largest (`routines`, 4,786 rows, 2.07 MB) | < 200 ms | 47 ms |
| First paint, `routines` | < 1 s | 631 ms |
| First paint, `boundaries` (4,070) · `constants` (2,638) | < 1 s | 360 ms · 317 ms |
| First paint, the five smaller documents | < 200 ms | 23–174 ms |
| Repaint on a selection, any document | < 100 ms | 19–94 ms |

**The first draft cost 9,568 ms per `render()`** — on a function that runs on every
selection, every keystroke and every message from the other window. It rewrote the chrome
around the document each time, which detaches the built subtree, and **re-attaching pays
the layout again**. That is the code browser's 1,358 ms defect at six times the size, and
the fix is the same one: repaint only when the document changes, and write the highlight
and the subject line narrowly.

**Two plausible fixes did nothing, and that is worth recording** (rule 39). **566 separate
tables against one**, with the group headings as rows inside it: 2,049 ms against 2,103.
**4,786 `<button>` cells against spans**: 2,103 against 2,003, inside the noise. Neither
structure is where the cost lives.

What worked was two lines of CSS. `content-visibility: auto` on each group is **61 ms
against 3,205** — the browser lays out the groups the reader can see and skips the other
550 — and `table-layout: fixed` is **1,769 ms against 2,389**, 25%, which is why this grid
now lays out like every other one. The remaining time is twenty thousand cells of real
text and there is nothing in it to find.

Conditions: 1,267×539 with the centre pane at 537px, root font 16px. **The pane width is
load-bearing here** — a narrow centre wraps every cell and makes each row 70px tall, so a
wider window lays out fewer pixels for the same rows, not more.

**Serving the corpus** — the document list and one document, measured 2026-09-03 on
Mensores' 2,064 documents, 38.7 MB of prose held in a 17 MB sidecar:

| Measure | Budget | Measured 2026-09-03 |
|---|---|---|
| `/api/docs`, all 2,064 rows | < 200 ms | 18 ms warm, 1.7–2.3 s cold |
| `/api/doc`, an ordinary document | < 100 ms | 0.8–2.5 ms (`docs/reference/glossary.md`) |
| `/api/doc`, the worst case | < 200 ms | 6–7 ms warm, 0.86 s cold |

The worst case is `.groma/ISSUES.md` — 1.33 MB, 18,299 lines, 327 headings, 191,549 words —
which is comparable to the largest *code* file and is sent whole (rules 8 and 55). The list
is 546 KB of JSON and is also whole: 2,064 rows with a heading count and a definition count
on each, never paged.

What makes both affordable is that the bodies are **not** in `docs.db`. The list is three
grouped counts over a store the server already holds open, and 38.7 MB of prose stays in the
sidecar until somebody opens a document. **The cold row is the external volume**, as every
cold row in this file is: 1.7 s and 2.3 s on two first reads, 18 ms on every one after.

**Switching program** — measured 2026-09-04 on an output root holding four programs:

| Measure | Budget | Measured 2026-09-04 |
|---|---|---|
| `/api/programs` | < 50 ms | **1.0–1.2 ms** warm, 1.0 s cold |
| `/api/cover`, beside it | — | 0.54–0.72 ms |
| a switch, `mensores` → `dunneflow` | < 30 s | **5.0 s** server-side, then a reload |

**The cold second is the external volume**, as every cold row here is: four directory
listings and a `glob` apiece on a disk that has not been touched. It is paid once, at boot,
by a fetch that is deliberately **not awaited** — the control is already correct with the
served program on it, and the siblings arrive when they arrive.

The file count is carried **only for the program being served**, and that is why the route is
1 ms rather than seconds: the served program's count is already in the base's cover, and every
other program's would cost a 27 MB graph open apiece to learn. A count nobody can afford is
worse than no count (rule 32 — a count must say what it counts, and this one says which
program it is about by being the only one there).

**Reading a naming standard out of a table** — measured 2026-09-04 over the 2,024 Markdown
documents of the corpus, which hold **5,230 tables** between them:

| Measure | Budget | Measured 2026-09-04 |
|---|---|---|
| full document scan, with the table rule detector | — | 5.75 s |
| the same scan, detector stubbed out | — | 5.74 s |
| **what the detector costs** | < 5% | **+4 ms, +0.1%** |

Median of three sweeps each, alternating, in one process against bodies already in memory —
which is the point of the conditions: this isolates the *detector* from the disk, and the
disk is what the 5.7 s is. The detector runs once per table and does two regex passes per
column over cells it has already been handed by `_table`, so there was no reason to expect a
cost and there is not one. It is recorded because a per-table pass over 5,230 tables is
exactly the shape of thing that turns out to cost something, and a number nobody took is a
number somebody will guess at later.

**A glossary citation into the corpus** — chunk 5, measured 2026-09-04 on the same base:

| Measure | Budget | Measured 2026-09-04 |
|---|---|---|
| `/api/docsource`, a 15-line span | < 50 ms | **0.56–0.65 ms**, five reads |
| `/api/source`, the same shape | < 50 ms | 0.60–0.61 ms |
| `/api/glossary`, now carrying `sidecars` | < 50 ms | **1.53–1.57 ms** |
| a documentation citation, opened in the page | < 1.5 s | **999 ms** |
| a **code** citation, opened in the page | < 1.5 s | **999 ms** |

The last two rows are the measurement, and they are a pair on purpose: **a documentation
citation costs exactly what a code one does**, which is the claim chunk 5 has to be able to
make. The 999 ms is neither route — both answer in under a millisecond — it is the glossary
page repainting its 1,214 terms on the `render()` that follows the fetch. Pre-existing,
identical for both tiers, and not chunk 5's; naming it here stops the next person retaking
this row and reporting it as a cost of the corpus (rule 24).

Conditions, because they are load-bearing: taken in the automation tab at a **1,264×523
viewport and a 16px root font**, on a warm sidecar, with the glossary page already painted.
The `sidecars` block adds a shallow copy of a five-key dict and two `serving()` calls to a
payload that is otherwise built once at boot — which is why the route stays at its old figure.

**ALGORITHMS: the judgement, the lanes and one ribbon** — **retaken 2026-09-07** after
chunk 6, on `output/mensores` at 628 files, 9,625 control points and 4,125 arms. Median of
five, warm, in one process.

`judge` walks a second list per point now — `Point.repeated`, which is `moves` minus what
the loop is over — and **it costs nothing measurable**: 105 ms, the figure it already had.
What moved is the payload, because the rates lane lost the 11 loops whose query runs once.

*The first retake read 176 ms and 273 ms and was thrown away.* It was taken in the minute
after a full analysis, on a machine still writing 31 MB of graph to an external volume;
three settled rounds of seven then agreed on 105 and 115 to within 2 ms. A measurement must
measure the thing it names (rule 24), and that one was measuring the disk.

| Measure | Budget | Measured 2026-09-07 |
|---|---|---|
| `shape.measure` — every point judged | < 500 ms | **105 ms** |
| `/api/algorithms` — the five lanes built | < 500 ms | **115 ms** |
| its payload, 793 rows | — | 682 KB |
| `/api/shape` — one routine's ribbon (10 points) | < 200 ms | **0.2 ms** |
| the widest ribbon in the program (51 points) | < 200 ms | **0.5 ms** |

The two figures are two bargains, and the difference between them is the whole shape of
this feature. The lanes are the **whole program** — four statements and arithmetic over
what they returned — so they are held on the base and paid once, on the first ask, exactly
as the curiosities are (rule 45). A ribbon is **one routine**, bounded by the reader
opening it, so it is answered on demand and held on nothing: at half a millisecond,
remembering it would cost more than making it (rule 52).

A cold first ask is the external volume rather than the work — 534 ms against 105 ms warm,
which is this machine's disk and not this feature (rule 24), so no cold row is claimed.

**ALGORITHMS chunk 5: the links back** — measured 2026-09-07 on the same map, warm, median
of five in one process.

| Measure | Budget | Measured 2026-09-07 |
|---|---|---|
| `shape.enclosing`, the median of 166 boundary targets | < 200 ms | **0.4 ms** |
| …the same at the 90th percentile | < 200 ms | **0.5 ms** |
| …the worst in the program (`bnd:FILE:`, 672 spans) | < 500 ms | **37 ms** |
| a boundary's whole pane, worst case | < 500 ms | **43 ms** |
| a table's pane (`audit_events`, 106 operations) | < 200 ms | **9.3 ms** |
| `/api/curiosities`, now twelve families | < 500 ms | **140 ms** (was 106 ms at ten) |

`enclosing` is `outline` per routine and the bound is the routines that touch the thing,
so the spread is what the corpus is rather than what the code is: one target of 166 costs
more than 20 ms. **The `EXISTS` is the bound on the work and not on the answer** (rule 55)
— 524 routines touch the unnamed `FILE` boundary and 389 hold a point around it, and
skipping the other 135 took the worst case from 297 ms to 197 ms cold and 36 ms warm.

*A cold row is the external volume and nothing else.* The worst target reads 187 ms on the
first ask in a process and 36 ms on every one after, and a genuinely cold page cache took
it to 1.0 s — the disk, not the feature, so no cold row is claimed here either.

The machine's source volume is a slow external disk; cold reads cost far more than
warm ones. That is expected and is not a regression.
