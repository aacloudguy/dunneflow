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
ticks below the selected row, which was highlighted but off screen. On the second retake
**Go to it** landed past the row as well (retake defect 42), at `resolve.languages` rather
than `resolve.entrypoints`, so the button shares the defect rather than being its remedy. The likely cause is a scroll taken before the tables above had laid out
(rule 73).

**What would settle it.** The opening scroll and **Go to it** become one call, run after
the tables above the row have laid out, with a test that the row is inside the scroller.

### 17 · Hiding then re-dimming unselected nodes loses the lit colouring

*Retake defect 26.*

With `binding_note` selected, setting Plates › unselected to *hidden* and then back to
*dimmed* drew the nine lit nodes grey, like the dimmed ones; only the links still showed
the selection. Rule 68's shape: a restore is a setter.

**What would settle it.** Going back to *dimmed* re-applies the lit colouring the way
selecting does, with a test over the engine's colour buffer.

### 19 · At 1,483 px with both panes open, the centre is too narrow for three of its views

*Retake defects 9, 11, 12 and 37.*

- **Graph:** the slider and plate panels cover the stack.
- **Table:** CONNECTIONS and CHANGED are off to the right, and the header clips to
  "CONNECTIO".
- **Algorithms:** the lane tabs run off the edge.

**What would settle it.** A judgement on the panes' default widths at a 1,440–1,500 px
window (design rule 53), measured, not guessed.

### 21 · The loading shell is blank and does not say why

*Retake defect 40.*

For about twenty seconds after the start page hands a program over, the shell shows its
three panes and nothing in them: the filter strip is hidden until the shell runs (defect 31's
fix), and nothing takes its place. A blank canvas must say why it is blank (design rule 21).

**What would settle it.** The shell says *reading the map…*, or what it is waiting for, until
the first pane has something to show, checked on a cold open from the external volume.

### 22 · The Informational tab moves the view without telling the navigator or the trail

*Retake defect 43.*

On the worklist, switching from Suspect to Informational inside the page heads it
*anomalies › Informational*, while the navigator keeps **Suspect** lit and the trail still
ends *Suspect*. The tab is a control that moves the pane without passing through the
selection, which is rule 78's shape and design rule 26's.

**What would settle it.** The tab goes through the same setter the navigator row does, with
a test that the navigator, the trail and the heading agree after either gesture.

### 23 · The trail names a boundary node by its raw id

*Seen during the 2026-10-02 retake.*

Selecting BOUNDARIES › NETWORK leaves a trail step reading *bnd:NETW…{url}api/programs'*,
an internal key, where every other step carries a label a reader would recognise.

**What would settle it.** `subjectLabel` names a boundary node by its kind and target, as
the inspector does.

### 27 · The trail bar loses steps off its left edge without counting them

*Found 2026-10-02 while rewriting the tutorial's chapter 12.*

The bar draws the last twelve steps, and *+N behind* counts what it did not draw. But the
twelve scroll sideways with the scrollbar hidden, so steps scrolled off the left are
neither visible nor counted. That is a filter that is silent (design rule 1).

**What would settle it.** Either the bar does not scroll, or *+N behind* counts what is out
of view, checked at 1,483 px with a trail longer than the bar.

### 28 · The CODE note can describe the file before last

*Retake, 2026-10-02.* With `cmd_serve` selected, the navigator's CODE note still read "357
lines, 37 clickable", which is `resolve/entrypoints.py`, the previous selection. The other
small defects first filed under this number were fixed on 2026-10-02.

**What would settle it.** The note names the file it counts and says nothing about a file
that is not the one selected, with the follow-into-code path not marking a subject as
followed before the file list has loaded.

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
