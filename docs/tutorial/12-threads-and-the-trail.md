# 12. Threads and the trail

Everything in the last eleven chapters was a door. This chapter is about what happens after
you have walked through six of them and can no longer remember why you were in the
basement.

## The trail

Every hop you make is recorded in a strip under the breadcrumb. Here is the one this
tutorial built while chapters 9 to 11 were being written, verbatim:

> TRAIL  dunneflow › Suspect › Glossary › Derived naming standard › Stated naming rules ›
> Stated rules, checked › Worth a look › cmd_analyze › Table › source.db › Kept
> — **← Back** · **Forward →** · **Clear**

Three things about it.

**It records what you selected, not what you clicked.** Every step carries its subject, so
Back does not merely undo a screen, it puts the thing back. That is why `cmd_analyze` and
`source.db` sit in the list beside pages like *Worth a look* — a routine, an artefact and
a view are all steps, because they are all answers to *what were you looking at*.

**A change of view is a step too.** `Table` is in that list between `cmd_analyze` and
`source.db`, because switching from Graph to Table while standing on the same routine is
something you may well want to undo.

**Forward exists.** Back then Forward is a free look around: nothing is lost by going back
two steps to check something.

## Threads to pull

Select a routine — `cmd_analyze` will do — and scroll the inspector past IN, OUT, TOUCHES
and GOVERNANCE.

![The inspector showing THREADS TO PULL 15, with the explanation "Not the call graph — reasons something nearby is worth a detour. Two routines that never call each other and both write one table are related, and no call graph can say that." Underneath, a lane headed THE OTHER END · 4 lists docsource.db "2 other routines name this file", pyproject.toml "2 other routines name this file", README.md "3 other routines name this file" and source.db "5 other routines name this file", each with a Keep this button. Below it a lane headed RUNS THE SAME SHAPE · 7 begins with "doc_store is not None — 1 other routine branches on this same test, as written" and "getattr(args, \"standards\", None) — 1 other routine branches on this same test, as written". The centre pane holds the routine table with cmd_analyze selected at row 41 of 925, and the trail above reads Stated naming rules › Stated rules, checked › Worth a look › cmd_analyze › Table](images/12-threads.jpg)

> **Not the call graph** — reasons something nearby is worth a detour. Two routines that
> never call each other and both write one table are related, and no call graph can say
> that.

Fifteen threads on this one routine, drawn from five kinds:

| | |
|---|---|
| **The other end** | you and somebody else touch the same file, table or boundary |
| **Runs the same shape** | you and somebody else make the same decision, or loop over the same table |
| **Named like these** | a naming convention you are an instance of |
| **Unusual nearby** | an outlier *in your package* |
| **Shares a plan** | the same ticket or decision id is written on both of you |

`cmd_analyze`'s first lane is four files — `source.db`, `README.md`, `pyproject.toml`,
`docsource.db` — each with the number of other routines that name it. Its second lane is
seven decisions: `not args.no_docs`, `doc_store is not None`, `getattr(args, "standards",
None)`. Somewhere else in the program, something branches on exactly the same test, and
knowing where is often the fastest way to understand what a flag actually does.

**Rarest first.** The lane says *Showing 5 of 7, rarest first*, and that ordering is the
feature: three routines is a detour, three hundred is a category. A thread shared with one
other routine is worth your afternoon; a thread shared with half the program is worth
nothing, and sorting by rarity keeps the first kind at the top.

**Every thread says how big it is** rather than being hidden for being small or large. And
each one states *why* in its own words — *"1 other routine branches on this same test, as
written"* — which includes the blind spot in four words: **as written**. `x == 1` and
`x==1` are two different threads here. The comparison is textual and the sentence says so.

### Nearby means nearby

The last lane on `cmd_analyze` is three outliers:

> `cmd_serve` — 35 comments, the most in `cli`
> `_emit` — called from 12 places, the most in `cli`
> `common` — nested 2 levels deep, the deepest closure in `cli`

*The most in `cli`*, not the most in the program. That is the difference between this
panel and [chapter 11](11-worth-a-look.md)'s: a curiosity is *somewhere in this program and
worth the walk*, a thread is *beside you*. The most-commented routine in the whole program
has 731; the most-commented one on this plate has 35, and when you are standing in `cli`
the second number is the useful one.

## Keeping something

Press **◇ Keep this** on the `source.db` thread, then follow it.

![The inspector for source.db, tagged ANALYSED and ARTEFACT with a filled "Kept" badge. IN 6 lists six routines that name the file, in cli, migrate and web.serve, each tagged INFERRED. OUT 0 reads "It calls nothing this map can see." TOUCHES 0 reads "It touches no boundary, table, remote or named file. Everything it does, it does in memory." GOVERNANCE 0 reads "No annotations and no comments. The code says what it does and nothing says why." THREADS TO PULL 0 reads "Nothing is beside this one — no shared plan, no shared table, nothing at the other end of anything it touches. That is an ordinary thing to be." The trail above reads dunneflow › cmd_analyze › source.db, followed by Back, Forward, Clear and a badge reading "1 kept"](images/12-trail-and-kept.jpg)

The trail gains a badge: **◆ 1 kept**. The navigator's EXPLORE group gains a row. And the
page behind it says what the shelf is for:

> Things you kept while you were looking at something else. The point of wandering is that
> you find what you were not looking for; this is where it goes so the detour does not cost
> you the thread you were on.

Every kept thing has a **Drop** beside it. The shelf is per program and it survives a
reload, so a half-finished investigation is still there tomorrow.

## The empty inspector is not empty

Look at what `source.db` itself reports. It is an artefact — a file this program names —
and almost every panel on it is zero. None of them is blank:

> **OUT 0** — It calls nothing this map can see.
>
> **TOUCHES 0** — It touches no boundary, table, remote or named file. Everything it does,
> it does in memory.
>
> **GOVERNANCE 0** — No annotations and no comments. The code says what it does and
> nothing says why.
>
> **THREADS TO PULL 0** — Nothing is beside this one — no shared plan, no shared table,
> nothing at the other end of anything it touches. That is an ordinary thing to be.

A blank pane and a pane that has looked and found nothing are indistinguishable on screen
and mean completely different things, so nothing here is ever left blank. The last one
even tells you not to read anything into it.

Note also the six rows under **IN**, every one tagged **INFERRED**. DunneFlow found six
routines that name the string `source.db`, and it will not pretend that naming a file is
the same as opening it. The tag is the tool declining to upgrade a guess.

---

Next: [13. The command line](13-the-command-line.md)
