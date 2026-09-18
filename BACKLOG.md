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

### 2 · The analyse dialog cannot see what the walk left out

*From chunk 14, 2026-09-17.*

`_emit` writes to stderr and `dunneflow serve` runs the analysis `--quiet`, so
*unread: 4,120 `.go`*, *left out as tests: 315 typescript* and *declined by you* reach a
terminal and never the application. **Design rule 1 holds for the command line and not for
the surface this tool is actually for** — a reader who analyses from the dialog gets the
progress panel and the map, and no account of what was filtered out of it.

**Why not done.** Chunk 14 had already taken one feature detour (`--without`), and this
one needs a UI decision — where in the panel the residue goes, and whether it survives the
panel being dismissed — that is not a documentation chunk's to make silently.
`docs/04-your-first-map.md` states the gap in as many words.

**What would settle it.** A `residue` record on the `--progress-json` stream, and the panel
rendering it. The lines already exist and are already computed; nothing has to be measured
again.

### 3 · `web/` has the ordering defect the map no longer has

*From the ordering fix, 2026-09-17.*

The rendered map is now byte-identical under a full row reversal. **Six literal `SELECT`s
under `web/` still have no `ORDER BY` at all** — in `cover.py`, `related.py`, `serve.py`,
`shape.py` and `waysin.py` — plus an unknown number with a partial one. Everything shared
through `resolve/` was fixed and benefits both surfaces; these are `web/`'s own.

**Why not done.** Scope, stated in advance: the deliverable was the map, which is the
artifact that gets diffed and handed over. A pane whose rows come back in a different order
is a different symptom with no baseline to compare against.

**What would settle it.** `tools/ordering.py`'s argument, one surface over: a harness that
asks each route twice from two row orders and compares the JSON. The 23 API routes are the
population.

### 4 · The rendered map still varies with `--jobs` in one respect

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

### 5 · `resolve/traceability.py` asks Python's builtins of every corpus

*From chunk 14, 2026-09-17.*

`_builtins()` is `load_rules("python").builtins`, used to decide which symbols in a plan
are *distinctive* enough to count as landed. Asked of a TypeScript-only map it is a true
count of a question nobody asked — open question 6's shape one module over.

**Why not done.** Unmeasured. Nobody has run the traceability lane against a corpus with a
plan in it and no Python, so the size of the error is unknown and a fix would be a guess.
`tests/test_languages.py` pins the count of language literals under `resolve/` at one, so
it cannot grow quietly while this is open.

**What would settle it.** Measure it on a corpus that has both, then either split per
language as the naming lanes were, or state the blind spot on the page.

### 6 · `fetch` through a name

*From chunk 10, 2026-09-17.*

A boundary that a spelling rule cannot reach because the call goes through a local binding.
The mechanism exists — the TypeScript checker can say what a name holds — and chunk 11 used
it for package-resolved boundaries.

**Why not done.** **No population to measure against.** DunneNote calls `fetch` in no
program file at all, so the feature could not be given a ground truth. Scheduled for chunk
10, and the reason it did not close is stated rather than quiet.

**What would settle it.** A corpus that calls `fetch` through a name. Then the same shape
as chunk 11's package matching.

### 7 · Rule 95's general remedy

*From chunk 6, 2026-09-17.*

Rule 95 is *a cache key assembled from a directory does not cover what that directory
imports*. `sql.py` joined the core key, which shut the specific gap the rule was minted
from. **The general remedy — deriving the key from the import graph rather than from a
list of directories — is not built**, and a rule is never closed.

**What would settle it.** Either building it, or recording the measurement that says the
hand-kept list is sufficient and why.

### 8 · `test_a_second_analysis_is_refused_and_told_what_is_running` is flaky

*From chunk 14, 2026-09-17.*

Failed once inside a full-suite run; has passed every run since — six in isolation, three
at the previous commit, and several full suites. The likely mechanism is that it starts an
analysis of a one-file tree as a subprocess and asks for a second immediately, so a first
that finishes first leaves nothing to refuse.

**Why not done.** Reported as observed rather than diagnosed. Whether the chunk-14 diff can
influence that timing was not established, and *I did not cause it* is not a claim that
session could make.

**What would settle it.** Make the refusal not depend on wall-clock — a first analysis the
test can hold open, rather than one it races.

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
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
