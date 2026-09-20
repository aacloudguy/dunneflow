# Batch ingest — reading a tree that takes days

**Design only. Nothing here is built, and nothing here is scheduled.** It is written now
because the evidence is fresh: `UnrealEngine-release` was read on 2026-09-19/20 as 85
separate analyses driven by a 86-line script, and everything that went wrong went wrong in
a way that a queue with a memory would have caught. Writing it down while the failures are
still legible is cheaper than rediscovering them.

## Context

**What was actually done.** `tools/ingest_parts.py` asks `walk.parts_under` for the cut and
runs `dunneflow analyze` once per part, in a `for` loop, printing a line each. That is the
whole of it: no state on disk, no resumption, no ordering, no way to see it from the
application, and no verification beyond a subprocess's exit code.

| | |
|---|---|
| the tree | **88,356 files**, 86 parts (it was 84 parts and 3,766 files uncovered until `--part-of`) |
| first pass | **327 minutes** |
| re-read after the C++ reader's stamp moved | **282 minutes**, 81 of 85 parts |
| the largest part | 18,191 files in **2,093 s** |
| the smallest parts | 11–15 files in **110–400 s each** — 50 such parts hold 1.5% of the tree and cost about a third of the wall clock |
| on disk | ~19 GB |

Ten hours of reading, in two sittings, from a loop with no memory. It worked. What it could
not do is survive being interrupted, tell anyone where it had got to, or answer *did that
actually work* afterwards — and each of those cost something real.

## The four failures, because the design is answerable to them

These are not hypotheticals. Each happened during that ingest and each is recorded in
`HANDOFF.md` under its date.

1. **A reader's stamp moved mid-run.** The tokenizer fix landed while the first pass was
   still going, so 81 of 85 parts became stale the moment they were written — rule 12
   working exactly as designed, against a run that had no idea the ground had shifted under
   it. Cost: 282 minutes. A queue knows the stamps it started with and can say *this job
   will be born stale* before spending twenty minutes on it.

2. **`0 failed` was true and useless.** The re-run driver passed `--output root.parent`
   where the first ingest passed `--output root`, so 81 maps were written correctly into the
   wrong directory. Every subprocess exited 0 and the driver reported success. The only
   thing that settled it was **asking the store the same question again afterwards** —
   which nothing in the driver did, and which a batch run must do as its last act.
   (`cli.part_argv` now makes the output root part of the one command spelling, so this
   particular mistake is no longer available. The lesson generalises: an exit code is a
   claim about a process, never about a map.)

3. **A part read 473 files nobody asked for and reported success.** `Engine.Binaries` was
   rooted inside a directory the C++ reader skips by name, so the rule that hid those files
   was no longer in any relative path. Closed on 2026-09-20 by `--part-of`
   (`BACKLOG.md` item 10, `walk.discover`). A wrong answer that fails loudly costs an hour;
   a wrong answer that succeeds goes into the map.

4. **Seven files were lost to one non-ASCII letter**, and the arithmetic only caught it
   because somebody checked each part against what the breakdown had claimed, by hand,
   afterwards. The run *did* say `failed 2` in its summary; what the **map** had was no
   `files` row, so the artifact could not answer *what was lost* once the terminal had
   scrolled.

Three of the four are invisible to a loop that reads exit codes, and the fourth was found
by a reconciliation nobody had asked for.

## What already exists and must not be rebuilt

The queue is genuinely small, because almost everything it needs is built and measured.
Rule 51 governs the whole of this: a batch runner that assembles its own version of any of
these is a second answer that can drift from the tested one.

| | |
|---|---|
| **the cut** | `walk.parts_under` — adaptive, one walk, and the same function the refusal prints |
| **the command** | `cli.part_argv` — one spelling, carrying `--part-of` and the output root |
| **the stream** | `--progress-json`, one object per line, now carrying `ms` |
| **resumption within a part** | `Store.known_hashes` — a re-run of a part re-reads only what changed |
| **commits as it goes** | `store.WAL_CAP_BYTES` (32 MB) — a part killed at 28 minutes keeps what it committed, which is what makes any of this finishable |
| **a half-written map is refused** | `UnfinishedMapError` and the `complete` meta (rule 80) |
| **staleness** | the five stamps — `Store(writable=False)` refuses a map whose reader has moved, **by name** |
| **not two at once** | `_Live.analysis_claimed` and its slot (rule 104: a slot claimed before the child exists) |
| **the pre-flight** | `web.analysis.Verdict` — refusals and notes, one function so the dialog and the endpoint cannot disagree |

So what is missing is **state, order, and an account** — not machinery for reading code.

## The design

### A run is a record, and a job is a row

The unit is a **run**: one tree, cut once, into N jobs. The cut belongs to the run and not
to each job, because `parts_under` is a 52-second answer on a tree this size and because a
cut re-taken halfway through is a different cut — a tree that gained a directory would
silently acquire a job nobody planned, and the arithmetic would stop closing.

A job carries: the part's path relative to the tree, its name, its expected file count from
the breakdown, its state, its wall time, the figures its analysis reported, and — the field
the Unreal run wanted and did not have — **the stamps that were in force when it was
written**.

States, and there are more than three because the interesting ones are not *running* and
*done*:

| | |
|---|---|
| `waiting` | cut, not started |
| `reading` | a child is alive |
| `read` | the child exited 0 **and** the store says `complete` |
| `stale` | written, but a stamp has moved since — it needs re-reading, and the run knows this without opening anything |
| `refused` | the pre-flight said no, with the sentence |
| `failed` | the child did not exit 0, with the tail of its stderr |
| `short` | it exited 0 and the map holds fewer files than the breakdown claimed — the state the seven lost files would have landed in |

`short` is the one that matters most and the one no exit code can produce. It is the
reconciliation of failure 4 and failure 2, made a state rather than an afternoon.

### Where the state lives

Beside the maps, in the maps root the run writes to — a sidecar next to the 86 program
directories, not in any of them. Three reasons: a run is about the root and not about any
one program; the root is what `dunneflow serve` already opens and lists; and a run
abandoned three days ago is then found by whoever opens the root, rather than by whoever
remembers which terminal it was in.

It is **not** in any graph. A graph is a map of a program and a queue is not a fact about
one, and putting it there would put it inside rule 12's blast radius for no benefit —
a run's own bookkeeping must survive a reader's stamp moving, which is precisely the
occasion it is most needed.

### What the application shows

Nothing new is needed on the wire. The dashboard already polls `/api/analysis` for one
running analysis and draws a panel from `state`, `step`, `done_steps`, `steps`, `detail`,
`residue`, `running_for` and `silent_for`. A run is that, plus *which job of how many*, plus
the table of jobs.

Two things it must get right, both learned here:

* **`ms` must never join the silence detector's list.** Every line now carries how long the
  run has taken, so a report that treated it as a change would say a run was progressing
  because it was being watched. `note_analysis` carries the comment.
* **A pane pinned to an edge grows away from it** (design rule 31), and 86 rows is longer
  than fourteen lines of residue, which already put a panel's head at −71px. A run's table
  is a scrolling region with a bounded height or it is a panel that cannot be stopped.

### Order

A run reads its jobs in an order, and the order has to be one the tool can defend
(rule 66). Largest first is the obvious one and is probably wrong: the 18,191-file part is
35 minutes during which nothing else finishes, and a reader watching would rather have
fifty small maps to open. Smallest first finishes more jobs sooner and leaves the risk at
the end. **This is a product question and not a correctness one**, exactly like
`BACKLOG.md` item 3's truncation, and the honest interim answer is the breakdown's own
order — which is already total and content-derived — with the choice stated rather than
implied.

### What it does at the end, and this is the part the loop did not have

A run's last act is to **ask the store the same questions again**:

* every job's map opens, and says `complete`;
* every job's file count equals what the breakdown claimed, or the job is `short` and says
  by how much;
* no job is stale against the stamps as they are *now* — which catches a reader that moved
  while the run was going, before anyone quotes a figure off it;
* the file counts sum to the breakdown's total, and `Breakdown.uncovered` is stated
  alongside rather than quietly dropped.

None of that is expensive — opening 85 maps read-only and asking each for two numbers took
seconds when it was done by hand. All of it was skipped, and the one time it was done it
found seven lost files and 473 unwanted ones.

## What has to be decided before it is built

Three things, none of which this note settles:

1. **Whether a run is a process or a service.** A `nohup`-able command that writes its state
   as it goes is small and survives a laptop sleeping; a long-lived server thread inside
   `dunneflow serve` gets the panel for free and dies when the window closes. The Unreal
   run took ten hours in two sittings, which argues for the first.
2. **What a queue of several trees means for the one-analysis-at-a-time slot.** Rule 104 was
   minted on that slot and it is currently a boolean plus a child; a queue is a third thing
   claiming it, and *"a boolean that says the other one stops being true when there are
   three"* is rule 94, already on the books.
3. **Whether `TOO_BIG` is still the right unit.** It counts files, and the stated residue
   says why that is the shape of the evidence rather than the right key: what hurts is rows
   written. A batch runner that schedules by size is the first thing that would want the
   honest key, and taking one needs a corpus spread wide enough to separate the two.

## What it is not

Not a scheduler, not a daemon, not a distributed anything, and **not a second way to
analyse a tree**. It runs `dunneflow analyze` and reads what that says. Every figure it
reports is one the analysis reported; every refusal it shows is one the pre-flight wrote.
The moment it computes something about a program itself, it has become a second assembly of
a tested thing and the day they disagree is already paid for.
