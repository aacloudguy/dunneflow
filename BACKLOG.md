# Backlog

**What this tree knows it owes, in one place.** `PLAN-v2.md`'s fourteen chunks are all
done, so nothing here is scheduled by the plan — every item is something a chunk found,
stated, and deliberately did not do. Until 2026-09-17 they lived scattered across
`V2-START-HERE.md`'s *What is next* and a dozen `HANDOFF.md` **Residue** sections, which
meant the only way to know what was outstanding was to read the whole record.

**Every item says where it came from, why it was not done, and what would settle it.** An
item with no *what would settle it* is a complaint rather than a task, and an item whose
*why not* is missing is one somebody will redo the argument for.

**This file is not the record.** `HANDOFF.md` says what happened and when; this says what
has not. When an item is done it leaves here and the record keeps it.

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

**What would settle it.** A session that can screenshot, doing prose and images together:
a fresh self-analysis, the 21 shots re-composed to the same framing, and every figure and
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

### 11 · 84 maps hold another program's documents, and call their tree `Developer`

*From the Unreal ingest, 2026-09-20. **This is the one to pick up next** — it is the only
open item that leaves maps on disk holding facts the tool would not have gathered.*

**Rule 108**, found by the phase timings built for item 9. `find_package_root` climbed four
levels above the tree into the Developer directory, which holds a stray `package.json`, so
the document root of every Unreal part was *every project on this machine*.

| | |
|---|---:|
| documents in each part's map | **15,497** |
| of those, from programs that are not Unreal | **2,607** |
| the tree each map says it is of | **`Developer`** |
| what the document walk cost a part | roughly **205 s**, over 85 parts |

A document is evidence (design rule 11), so each part's **glossary, naming standard, mirror
and traceability** was measured over a corpus that is partly somebody else's vocabulary, and
`tree_leaf` — rule 64's identifying leaf — is the name of a directory that is nobody's
program.

**What is fixed and what is not.** `analyze --part-of <tree>` is the ceiling, and the two
parts re-read this session are correct: `Engine.Source.ThirdParty` holds 11,850 documents,
all of them inside itself, in a 15 MB store against 107 MB. **The other 84 parts still hold
the foreign corpus.**

**Why not done.** It is 84 analyses, and they are cheap only in the sense that the code is
cached — the document phase is the whole of the cost and it is the phase being re-taken.
Worth doing in one pass with whatever item 8 decides, rather than twice.

**What would settle it.** Re-reading the 84 with `--part-of`, then asking each map the two
questions afterwards: that it holds no document outside the tree, and that it names its own
tree. `PLAN-BATCH-INGEST.md` is written around exactly that reconciliation.

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
* **Left.** A part's *documents* are still whatever is physically under its root, where its
  *code* is what a reader admits. `Engine/Source/ThirdParty` is 620 files of code and
  **57,373 files on disk**, and with the ceiling in place it still holds **11,850 documents**
  and spends **71.9% of a 241 s run** on them.

**Why not done.** Because it is not obviously wrong. Those documents really are in that
directory, and design rule 11 says documentation and source are equal inputs — a reader's
`skip_dirs` is a statement about what is *program source*, and nothing has ever said it is a
statement about prose. Applying one reader's skip list to documents would also be a
per-language rule applied to a thing that has no language.

**What would settle it.** Deciding what a part's documentation *is*, with a measurement
behind it: how much of a corpus's prose sits under a directory some reader skips, across the
corpora here. Until then the number is what it is and is now visible, which it was not.

### 5 · Rule 95's general remedy

*From chunk 6, 2026-09-17.*

Rule 95 is *a cache key assembled from a directory does not cover what that directory
imports*. `sql.py` joined the core key, which shut the specific gap the rule was minted
from. **The general remedy — deriving the key from the import graph rather than from a
list of directories — is not built**, and a rule is never closed.

**What would settle it.** Either building it, or recording the measurement that says the
hand-kept list is sufficient and why.

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
| **The size guard counts files and nothing else** | `walk.TOO_BIG` is 20,000 *files*, which is the shape of the evidence — `Engine/Source/Runtime` is 18,191 and is the largest tree read end to end. A tree of 19,000 enormous files passes it and a tree of 25,000 tiny ones is refused, and neither is what the bound is really about: the thing that hurts is rows written, not files read. Bytes or an estimate of rows would be the honest key, and taking one needs a corpus spread wide enough to separate the two — which is a measurement, not an edit. Stated so the number is read as what it is. 2026-09-19. |
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
