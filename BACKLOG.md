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

Every item found while photographing the docs on 2026-10-02, and every older one, was closed
that day or moved to the residues below with the decision that put it there — except one,
found while the prose was being rewritten against the third retake.

### 29 · A Python routine that calls itself is never an edge to itself

**Found:** the tutorial's chapter 9, on the screenshot map (clone `5b737a0`, release 5).
`_pick` in `resolve/python/calls.py` drops the caller from every candidate list ("ignoring
self-recursion"), so a recursive call finds nothing in its own module and falls through to
the program-wide name index. On DunneFlow's own map that gives three wrong answers for one
fact: `extractors.cpp.literals._all` → `extractors.kotlin.literals._all` and
`web.shape._tally` → `walk._tally` are **bound** to a same-named routine in another module
(rule 1, rule 5); `extractors.cpp.calls._walk`, `resolve.shape.nesting.walk` and nine more are
LOST_EDGE, ambiguous between strangers; and the remaining ~35 recursive sites are counted
EXTERNAL, which is rule 26's false claim. The TypeScript reader binds recursion to itself.

**Why not done:** it changes resolution figures — internal calls, lost edges, reach and the
findings that read them — on every map, and the screenshot map's figures had just been
retaken. Fixing it now means rebuilding the tour maps and retaking the shots again.

**What would settle it:** a recursive call resolves to the caller (the in-module lookup finds
the caller itself and stops there), never falls through to the program-wide index, and is
neither EXTERNAL nor LOST. Whether a self-edge is drawn is a separate choice for `render/`.
The test is the six sites above on a synthetic tree, with a same-named function in a second
module as the decoy; the gates are the Society golden, `tools/ordering.py` and a re-release.

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
| **Python's leading-underscore classes drag PascalCase to a `D`** | `_Base` and `Exception_`, 15 of DunneFlow's 164. Answered on 2026-10-02 as a Setting rather than a rule (*A leading underscore in a name*, and `naming --allow-leading-underscore`): strictly a violation, and allowed where the reader says so. `Exception_` and its kind stay exceptions either way. Open question 6. |
| **A Linux session cannot run the recorded ground truth** | None of the four Society clones nor `../dunnecorp-standards` is on that machine, so no figure in `CLAUDE.md` was retaken there. Do not restate a Mensores figure measured elsewhere as though it had been reproduced (rule 24). |
| **A program that serves browser JavaScript as a string has calls this map cannot see** | `gstack`'s `getCookiePickerHTML(): string` returns an HTML page holding four `fetch` calls, and `design/src/compare.ts` another. Those requests really are made — from the browser, by code this program wrote — and the map says nothing about them. Correctly: a string is not code, which is rule 9's argument one direction over, and reading one would mean parsing every template literal in every language. Stated so the NETWORK count is read as *what this program calls*, never *what this program causes*. 2026-09-18. |
| **`socket.emit` may be wrongly declared async** | `detectors/typescript.yaml` says `async: true`; `emit` is fire-and-forget in socket.io and `emitWithAck` is the awaitable one, so it is probably wrong beside `WebSocket` and `EventSource`, which were corrected. Left alone because **no map this tool has read holds a single `socket.emit`** and socket.io's types are in no corpus here, so there is nothing to check a change against. Asserting it from memory is what rule 24 forbids. 2026-09-18. |
| **Rule 105's survey is a floor, not the population** | `tools/ordering.py --survey` lists the five `sorted()` calls whose input is *written as* a set and which take a `key=`. Unorderedness propagates, so a dict built by iterating a set and then sorted over its `.items()` is the same defect and is invisible to it — `web/changes.py` held two of each, and only the two written as set algebra are in the count. Catching the rest means following the provenance of a value, which is a different instrument. The reversal probe cannot see any of them. 2026-09-18. |
| **A killed analysis can leave its pool behind** | Nine `ProcessPoolExecutor` workers from the original Unreal ingest were still alive 22 hours later, parented to init, idle at 5.5 MB each. Harmless where they are, and the 86-part re-read on 2026-09-20 added none — so it is an interrupted run's leak rather than an ordinary one's. Stated because a batch runner doing this nightly would accumulate them, and the batch-ingest design is the place that would have to care. 2026-09-20. |
| **The size guard counts files and nothing else** | `walk.TOO_BIG` is 20,000 *files*, which is the shape of the evidence — `Engine/Source/Runtime` is 18,191 and is the largest tree read end to end. A tree of 19,000 enormous files passes it and a tree of 25,000 tiny ones is refused, and neither is what the bound is really about: the thing that hurts is rows written, not files read. Bytes or an estimate of rows would be the honest key, and taking one needs a corpus spread wide enough to separate the two — which is a measurement, not an edit. Stated so the number is read as what it is. 2026-09-19. |
| **A part's documents are whatever is under its root, vendored prose included** | Unreal's 86 parts hold **12,886 documents, and 11,850 of them are `Engine.Source.ThirdParty`'s**: a part of 620 code files on 57,373 files of vendored library source, which the C++ reader skips by name for code. Every other part is in double or single figures. Tom's decision, 2026-10-02: vendored prose **is** documentation of the program, so it is read. Design rule 11 holds as written, and a reader's `skip_dirs` stays a statement about program source and never about prose. Measured with `analyze --timings` on 2026-09-20; formerly BACKLOG 9. |
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
