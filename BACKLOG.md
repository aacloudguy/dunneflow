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
| **The golden redefines two of its seven digests** | `routines.body` and `calls.resolved` record values whose statement was never written down and was not recovered by a bounded sweep. `tools/golden.py` redefines them explicitly and compares graph to graph. *We did not find it* is not *it is not there* (rule 24). Chunk 0. |
| **DunneCorp's routines are two conventions by role** | PascalCase 88 against camelCase 79 — React components against ordinary functions. A language split does not touch it, and it stays a reported gap because that is the true answer. Open question 6. |
| **DunneNote's modules stay a gap** | kebab 221, other 210. That tree really does spell module files three ways. Open question 6. |
| **Next.js route segments read as `other`** | `app.(admin).admin.customers.[id].page`. Route syntax is not an identifier and stripping it would be guessing at a spelling. Open question 6. |
| **Python's leading-underscore classes drag PascalCase to a `D`** | `_Base` and `Exception_`, 15 of DunneFlow's 164. A pre-existing question about what PascalCase means with an affixed underscore; not a language question, and left alone deliberately rather than folded into a chunk about something else. Open question 6. |
| **A Linux session cannot run the recorded ground truth** | None of the four Society clones nor `../dunnecorp-standards` is on that machine, so no figure in `CLAUDE.md` was retaken there. Do not restate a Mensores figure measured elsewhere as though it had been reproduced (rule 24). |
| **A program that serves browser JavaScript as a string has calls this map cannot see** | `gstack`'s `getCookiePickerHTML(): string` returns an HTML page holding four `fetch` calls, and `design/src/compare.ts` another. Those requests really are made — from the browser, by code this program wrote — and the map says nothing about them. Correctly: a string is not code, which is rule 9's argument one direction over, and reading one would mean parsing every template literal in every language. Stated so the NETWORK count is read as *what this program calls*, never *what this program causes*. 2026-09-18. |
| **`socket.emit` may be wrongly declared async** | `detectors/typescript.yaml` says `async: true`; `emit` is fire-and-forget in socket.io and `emitWithAck` is the awaitable one, so it is probably wrong beside `WebSocket` and `EventSource`, which were corrected. Left alone because **no map this tool has read holds a single `socket.emit`** and socket.io's types are in no corpus here, so there is nothing to check a change against. Asserting it from memory is what rule 24 forbids. 2026-09-18. |
| **Rule 105's survey is a floor, not the population** | `tools/ordering.py --survey` lists the five `sorted()` calls whose input is *written as* a set and which take a `key=`. Unorderedness propagates, so a dict built by iterating a set and then sorted over its `.items()` is the same defect and is invisible to it — `web/changes.py` held two of each, and only the two written as set algebra are in the count. Catching the rest means following the provenance of a value, which is a different instrument. The reversal probe cannot see any of them. 2026-09-18. |
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
