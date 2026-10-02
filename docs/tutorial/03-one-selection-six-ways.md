# 3. One selection, six ways

The cover is where you land. Everything after it is one idea: **you pick a thing, and the
whole screen is about that thing.**

There are six views — Graph, Table, Document, Code, Diagram, Shape — and they are not six
destinations. They are six readings of one selection. Pick a routine in any of them and
the other five are already showing it. You never navigate *to* a view; you change how you
are looking at what you already picked.

## Finding something to pick

The search box is in the top bar. Type into it and the entire navigator answers.

We will use `entrypoints_from_manifests`, which is the routine that turns what a
program's manifests declare — a `pyproject.toml`'s console scripts, for one — into the
ways in the cover ranks. It is a good specimen because it is a manageable size, it reaches
the database, and it is one of the routines that changed in the fix
[chapter 8](08-two-versions.md) is about, so it has a history worth asking about later.

![The navigator with "entrypoints_from_manifests" in the search box. ROUTINES reads "1 match "entrypoints_from_manifests", in 1 package" and shows resolve › resolve.entrypoints › entrypoints_from_manifests with 2← 6→, selected. Every other group answers too: WAYS IN "nothing matches", CHANGES "two versions — open to compare them", CODE "142 files — open one, or search names or source", PACKAGES "nothing matches", BOUNDARIES "nothing matches "entrypoints_from_manifests" — these are the 7 kinds this program touches; a target is in the source", DATABASE and STRUCTURES "nothing matches". The crumb reads dunneflow › resolve.entrypoints › entrypoints_from_manifests, with Stack and Overview beside it and the six views under it; the trail reads dunneflow › entrypoints_from_manifests, and the stack's panel says "on pkg:resolve, pkg:cli, pkg:store, ext:DATABASE · entrypoints_from_manifests · 9 nodes · 5 within · 3 crossing · 2,683 dimmed". The inspector on the right is headed resolve.entrypoints.entrypoints_from_manifests, resolve/entrypoints.py:252–302](images/03-selection-and-inspector.jpg)

Look at what the groups that found nothing do. They do not disappear, and they do not sit
there empty. Each one **says** that it found nothing, and BOUNDARIES goes further:

> nothing matches "entrypoints_from_manifests" — these are the 7 kinds this program touches; a target is in the source

That is the group explaining that you have searched it with the wrong kind of word. Its
rows are boundary *kinds* — the seven this program touches, DATABASE, FILE, NETWORK and so
on — so a routine name was never going to match one, and the thing you probably want is the
source search instead.

**No filter is ever silent** is the first of DunneFlow's design rules, and this is what it
buys. An empty list with no sentence reads as *nothing was found*; these read as *there is
nothing here to find, and here is why*. They are different facts and they look identical
if you let them.

## Picking it

Click the match. The screen fills in around it.

The crumb at the top reads `dunneflow › resolve.entrypoints › entrypoints_from_manifests`. The mode toggle appears
— Graph, Table, Document, Code, Diagram, Shape — and a **trail** bar appears under it,
recording where you have been. **← Back** and **Forward →** work from anywhere, which
matters because the person who needs Back is likely lost.

The inspector on the right is the part to read now.

## The inspector

![The inspector for entrypoints_from_manifests, close up. Headed resolve.entrypoints.entrypoints_from_manifests, resolve/entrypoints.py:252–302, tagged ANALYSED and ROUTINE, with Keep this and Collapse all buttons. IN 2: cmd_analyze from cli and entrypoints_from_packaging from resolve.entrypoints, both CERTAIN, and under them the quoted line "Bind, mint and record every way in the manifests declared." OUT 10 call sites: sorted EXTERNAL; _mint CERTAIN; entry.target.partition EXTERNAL; _target_routine, _import_prefixes and _target_file, all CERTAIN and in resolve.entrypoints; Entrypoint, "a class of this program", tagged CLASS; found.append EXTERNAL; add_entrypoint CERTAIN, in store; store.conn.commit "at the boundary", EXTERNAL. TOUCHES 1: DATABASE BOTH :301. SHAPE 4 begins below](images/03-inspector.png)

> **resolve.entrypoints.entrypoints_from_manifests**
> resolve/entrypoints.py:252–302
> ANALYSED · ROUTINE

**IN 2** — who calls it. `cmd_analyze` in `cli` and `entrypoints_from_packaging` beside it,
both marked **CERTAIN**. Under them is the routine's own first line, quoted from its
docstring: *"Bind, mint and record every way in the manifests declared."*

**OUT 10 call sites** — what it calls, counted per place it calls from. `_mint`,
`_target_routine`, `_import_prefixes` and `_target_file` are **CERTAIN** and live in the
same module; `add_entrypoint` is **CERTAIN** and lives in `store`. `sorted`,
`entry.target.partition`, `found.append` and `store.conn.commit` are **EXTERNAL**, meaning
they leave the program — and `store.conn.commit` carries **at the boundary**, because that
is the call that writes to the database. `Entrypoint` is neither: it is tagged **CLASS**,
*a class of this program*. The call builds `schema.Entrypoint`, one of this program's own
dataclasses, which has no constructor of its own to point at — so it is not an edge to a
routine, and it is not external either, because the thing it builds is defined in this
program.

**TOUCHES 1** — `DATABASE BOTH :301`. One place in this routine reaches out of the
program, and it is line 301.

**GOVERNANCE 5** — five lines lifted from the source's own comments, each with its line
number. The first:

> `:291` **The target, carried as a field.** `resolve/cli.py` and

This is the habit that runs through the whole tool: **a claim on screen carries its
evidence, and the evidence opens.** Not a summary of what the code means — the words its
author wrote, and the line they wrote them on.

**SHAPE 4** — `loop 2` · `guard 1` · `decision 1`, and a sentence:

> 0 things move inside them, and 5 calls go to this program's own code.

Then a button: **Draw its shape**.

## The sixth way

Press it.

![Shape mode for resolve.entrypoints.entrypoints_from_manifests. The header reads "resolve/entrypoints.py:252–302 · 51 lines · 2 loops · 1 decision · 1 refusal". The ribbon shows: line 272 LOOP sorted(readings, key=lambda r: (not r.at_root, r.where)), annotated "calls 5 routines of this program, and nothing moves at these lines"; nested inside it line 273 LOOP reading.entries, with the same annotation; a call to _mint at 274; line 275 GUARD ident in taken → continue, "a precondition: it skips the pass, and a refusal is read in the routine, not in a worklist"; line 278 DECISION entry.target_kind == TargetKind.MODULE_ATTR, "3 ways out of one decision, and none of them moves anything", whose if arm at 279 calls _target_routine and _import_prefixes, whose elif arm at 283 calls _target_file, and whose else at 286 is "nothing that moves"; a call to store.add_entrypoint at 300; and, outside both loops, line 301 DATABASE both](images/03-shape-of-the-ladder.jpg)

This is the same routine, read a sixth way — not what it is connected to, but **what it
does**.

> 51 lines · 2 loops · 1 decision · 1 refusal

And the ribbon underneath is the routine's own structure, nested as it is written. No
arrows, no boxes-and-lines diagram, no layout engine: structured code has no `goto` to
draw, so the drawing is an indented outline and nothing is lost.

Read it as prose and it says: *for each manifest, root first, and for each entry in it,
mint an identity and skip the ones already taken; then find what the entry names — a
routine, a file, or neither; record it; and when every entry is done, commit once.*

That last clause is the one a reader of the code could miss and the ribbon cannot. The
only thing in this routine that moves is the commit on line 301, and it sits **outside**
both loops — which is why the header names no *things that move*: it counts only what moves
inside the loops and decisions it lists, and here that is nothing. Each entry is handed to
`store.add_entrypoint` — this program's own code, so a call rather than a touch — and the
routine itself reaches the database once, after the last.

### The annotations are the feature

Every line carries a judgement, and the judgements are the reason this view exists:

- `LOOP reading.entries` — **calls 5 routines of this program, and nothing moves at these
  lines.** A loop that increments a counter is internal computation, and DunneFlow
  deliberately does not report it. A loop that reaches out of the program once per pass is
  a *rate*, and a rate is flow. This one is neither, and it says so in as many words: it is
  kept because it calls into the program, and it is marked as moving nothing so that you
  do not read it as a rate.
- `else` — **nothing that moves.** The arm is listed and then explicitly discounted. It is
  not hidden for being uninteresting; it is shown, with the reason it is uninteresting.
- `GUARD ident in taken → continue` — **a precondition: it skips the pass, and a refusal is
  read in the routine, not in a worklist.** DunneFlow counts it as a *refusal* rather than
  a branch.

**Nothing is dropped for failing the test.** Across DunneFlow's own source there are loops
that move something and loops that move nothing, and both are counted — because it is the
ones that move nothing that make the ones that move something worth believing.

## The point

You picked one routine in a search box. Without opening a file you now know where it lives,
who calls it, what it calls, which of those leave the program, what its author (Claude Code)
said about five specific lines, and what it actually does, step by step.

Six views, one selection. The other five are the next four chapters.

---

Next: [4. The stack](04-the-stack.md)
