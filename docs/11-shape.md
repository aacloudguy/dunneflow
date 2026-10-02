# 11. Shape

Every other view answers what a routine is *connected to*. This one answers what it
**does**.

![Shape mode for docstore.DocStore.mark_duplicates: the header reads "docstore.py:422–459 · 38 lines · 3 loops · 1 decision · 1 refusal · 4 things that move", and below it a nested outline — at 440 a LOOP over a SELECT that moves nothing inside it, with its DATABASE row and a SQL documents link; at 447 LOOP groups.values(), "something moves inside this loop, 2 of them, once per pass"; inside it GUARD len(paths) < 2 → continue, LOOP paths, and DECISION p != canonical, "every way out of it moves the same things", holding a DATABASE UPDATE documents SET duplicate_of = ? WHERE path = ?. The inspector on the right shows IN 2, OUT 11 and TOUCHES 7](images/11-shape-ribbon.jpg)

## Why this exists at all

DunneFlow's founding rule is that **what moves is the subject and internal computation is
not**. Local variables, arithmetic and private helpers that touch nothing are deliberately
left out, and leaving them out is most of what makes the rest readable. There are many existing
tools to examine source code, follow live code values as the program executes, and debug
live applications with the values of variables available for inspection. DunneFlow has none
of these features. DunneFlow is entirely about connections and flow, and a different way of
looking at applications.

Control flow was on that list until it was amended, and the amendment is narrow:

> A loop or a decision is a subject **only where something moves inside it.**

A loop that increments a counter is the internal computation nobody asked for. A loop that
issues one network call per item is a **rate**, and a rate is flow. A branch whose arms
compute different numbers is arithmetic; one where an arm writes to a table and another
does not is a decision about what leaves the program.

## Reading the ribbon

It is a nested outline, and there are **no arrows** deliberately. Structured code has no
`goto` to draw, so there is no control-flow graph here, no layout pass and no library.
Boxes nested as the code is nested is the whole drawing.

Each line carries its line number, the kind, the header **as written**, and a note saying
what DunneFlow judged about it:

| | |
|---|---|
| `LOOP` | with its iterable as written, and *"something moves inside this loop, 2 of them, once per pass"* |
| `DECISION` | with its test as written, and whether every way out of it moves the same things |
| `GUARD` | a refusal — *"a precondition: it skips the pass, and a refusal is read in the routine, not in a worklist"* — and how it leaves (`→ continue`) |
| `HANDLER` | a `try`, and whether anything moves while recovering |
| `DATABASE` / `FILE` / `STDIO` … | something actually leaving the program, with the operation |
| `→ name` | a call, clickable |

**Nothing is dropped for being quiet.** A loop that moves nothing is still drawn, and says
*"nothing that moves happens inside it"*. It is the loops that move nothing that make the
ones that do credible.

Anything that names a table is a link: click it and you select the table, which selects
everything that reads and writes it.

## The Algorithms page

The mode toggle's **Shape** is one routine. The navigator's **Algorithms** group is the
same facts over the whole program, in five lanes.

![The Algorithms page on its first lane: tabs, wrapped onto two rows, reading "A boundary, once per pass 113", "Decisions about what leaves 11", "Three or more ways out 56", "Something moves while recovering 6" and "match statements 0", then "113 of 1,808 loops and comprehensions", an explanation, the quiet bands, and a list of loops — mark_duplicates at docstore.py:451, _from_dunder at resolve/version.py:84, _discard_stale_languages at store.py:866, cmd_touches at cli.py:1307 — each naming the loop it sits inside, what moves inside it, and a "◇ Keep this" button. The navigator's ALGORITHMS group reads 186 and "4,363 loops and decisions were measured — 998 loops move nothing and 1,283 branches are refusals"](images/11-algorithms-page.jpg)

| Lane | What is in it |
|---|---|
| **A boundary, once per pass** | Loops that reach out of the program every time round. One call per item, one write per row — the rate. |
| **Decisions about what leaves** | Branches whose arms differ in what they move, not in what they compute. |
| **Three or more ways out** | Ladders. |
| **Something moves while recovering** | Handlers that do more than swallow. |
| **`match` statements** | Counted whether or not there are any. |

Two things about this page:

**Every lane states its denominator.** *113 of 1,808 loops and comprehensions* — never
*113 loops*, which would be a number you could not weigh.

**The quiet bands are stated above the list**, and that is the honest half:

> Measured and not listed here: 998 loops that move nothing, 697 that call something of
> this program and move nothing themselves, 1,026 decisions whose arms move alike, 39
> handlers that guard something and recover quietly, and 1,283 refusals — a guard is read
> in the routine it stands at the top of, never in a list of its own.

Four lanes holding 186 points, out of 4,363 loops and decisions measured, is a claim about
the 4,177 that are not in them, and this is where that claim is made. (The fifth lane,
`match` statements, holds none in this program, and its tab says *0*.)

## What it cannot see

Two things worth knowing, both stated on screen where they apply.

**A decision is compared by its header as written.** `x == 1` and `x==1` are two different
values here. That is a blind spot rather than a bug. DunneFlow records what the source
says, and normalising it would be inventing an equivalence the source does not state.

**A span cannot tell what a loop is over from what it does.** What is recorded is the
loop's iterable or its test, never the word that opened it. This means a loop is labelled `LOOP`
and not `for`, because `for` would be a guess and `while True` would sometimes be a false
one.

---

Next: [12. Chasing rabbits](12-chasing-rabbits.md)
