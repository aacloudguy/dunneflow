# 3. One selection, six ways

The cover is where you land. Everything after it is one idea: **you pick a thing, and the
whole screen is about that thing.**

There are six views — Graph, Table, Document, Code, Diagram, Shape — and they are not six
destinations. They are six readings of one selection. Pick a routine in any of them and
the other five are already showing it. You never navigate *to* a view; you change how you
are looking at what you already picked.

## Finding something to pick

The search box is in the top bar. Type into it and the entire navigator answers.

We will use `_reveal_linux`, which is the routine that opens a directory in a Linux file
manager. It is a good specimen because it is small, it touches the outside world, and it
is one of the three routines that did not exist a week ago when this tutorial was written.

![The navigator with "_reveal_linux" in the search box. ROUTINES reads "1 match \_reveal_linux, in 1 package" and shows web › web.serve › \_reveal\_linux with 1← 2→. Every other group answers too: WAYS IN "nothing matches \_reveal_linux", PACKAGES "nothing matches", BOUNDARIES "nothing matches \_reveal_linux — these are the nine kinds; a target is in the source", STRUCTURES "nothing matches", DATABASE "nothing matches"](images/03-selection-and-inspector.jpg)

Look at what the groups that found nothing do. They do not disappear, and they do not sit
there empty. Each one **says** that it found nothing, and BOUNDARIES goes further:

> nothing matches "_reveal_linux" — these are the nine kinds; a target is in the source

That is the group explaining that you have searched it with the wrong kind of word. There
are nine boundary *kinds* — DATABASE, FILE, NETWORK and so on — so a routine name was never
going to match one, and the thing you probably want is the source search instead.

**No filter is ever silent** is the first of DunneFlow's design rules, and this is what it
buys. An empty list with no sentence reads as *nothing was found*; these read as *there is
nothing here to find, and here is why*. They are different facts and they look identical
if you let them.

## Picking it

Click the match. The screen fills in around it.

The crumb at the top reads `dunneflow › web.serve › _reveal_linux`. The mode toggle appears
— Graph, Table, Document, Code, Diagram, Shape — and a **trail** bar appears under it,
recording where you have been. **← Back** and **Forward →** work from anywhere, which
matters because the person who needs Back is likely lost.

The inspector on the right is the part to read now.

## The inspector

> **web.serve._reveal_linux**
> web/serve.py:3732–3773
> ANALYZED · ROUTINE

**IN 1** — who calls it. `reveal_dir`, marked **CERTAIN**, with its own first line quoted
underneath: *"Show one directory on a Linux desktop, by the two means a desktop offers."*

**OUT 5** — what it calls. `_desktop_session` is **CERTAIN** and inside this program;
`target.as_uri`, `str`, `subprocess.run` and `str` are **EXTERNAL**, meaning they leave the
program. `subprocess.run` carries **at the boundary**, because that is the call that starts
another process.

**TOUCHES 1** — `PROCESS argv BOTH :3761`. One place in this routine reaches out of the
program, and it is line 3761.

**GOVERNANCE 3** — three quotes lifted from the source's own comments, each with its line:

> `:3751` `as_uri` percent-encodes, which the bus requires and a space in a directory name
> would…

This is the habit that runs through the whole tool: **a claim on screen carries its
evidence, and the evidence opens.** Not a summary of what the code means — the words its
author wrote, and the line they wrote them on.

**SHAPE 4** — `guard 2` · `loop 1` · `handler 1`, and a sentence:

> 1 thing moves inside them, and 1 call goes to this program's own code.

Then a button: **Draw its shape**.

## The sixth way

Press it.

![Shape mode for web.serve._reveal_linux. The header reads "web/serve.py:3732–3773 · 42 lines · 1 loop · 2 refusals · 1 handler · 1 thing that moves". The ribbon shows: line 3749 GUARD not _desktop_session() → return, annotated "a precondition: it returns, and a refusal is read in the routine, not in a worklist"; line 3759 LOOP rungs, annotated "something moves inside this loop, once per pass"; nested inside it line 3760 HANDLER "it guards something that moves, and its handlers move nothing", a try at 3761 containing PROCESS argv, except FileNotFoundError at 3764 "nothing that moves" and except (OSError, subprocess.TimeoutExpired) at 3767 "nothing that moves"; and line 3769 GUARD done.returncode == 0 → return](images/03-shape-of-the-ladder.jpg)

This is the same routine, read a sixth way — not what it is connected to, but **what it
does**.

> 42 lines · 1 loop · 2 refusals · 1 handler · 1 thing that moves

And the ribbon underneath is the routine's own structure, nested as it is written. No
arrows, no boxes-and-lines diagram, no layout engine: structured code has no `goto` to
draw, so the drawing is an indented outline and nothing is lost.

Read it as prose and it says: *check there is a screen; then for each rung in turn, try to
run it, and give up quietly on either of two failures; then refuse unless it worked.*

That is the ladder [chapter 1](01-pointing-it-at-itself.md) mentioned in passing, and here
it is measured rather than described.

### The annotations are the feature

Every line carries a judgement, and the judgements are the reason this view exists:

- `LOOP rungs` — **something moves inside this loop, once per pass.** That is what makes
  this loop worth reporting. A loop that increments a counter is internal computation and
  DunneFlow deliberately does not report it; a loop that reaches out of the program once
  per iteration is a *rate*, and a rate is flow.
- `except FileNotFoundError` — **nothing that moves.** The handler is listed and then
  explicitly discounted. It is not hidden for being uninteresting; it is shown, with the
  reason it is uninteresting.
- `GUARD … → return` — **a precondition: it returns, and a refusal is read in the routine,
  not in a worklist.** Two guards, and DunneFlow counts them as *refusals* rather than
  branches.

**Nothing is dropped for failing the test.** Across DunneFlow's own source there are loops
that move something and loops that move nothing, and both are counted — because it is the
ones that move nothing that make the ones that move something worth believing.

## The point

You picked one routine in a search box. Without opening a file you now know where it lives,
who calls it, what it calls, which of those leave the program, what its author (Claude Code)
said about three specific lines, and what it actually does, step by step.

Six views, one selection. The other five are the next four chapters.

---

Next: [4. The stack](04-the-stack.md)
