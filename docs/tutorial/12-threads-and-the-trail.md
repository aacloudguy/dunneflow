# 12. Threads and the trail

Everything in the last eleven chapters was a door. This chapter is about what happens after
you have walked through six of them and can no longer remember why you were in the
basement.

## The trail

Every hop you make is recorded in a strip under the breadcrumb. By the end of this
chapter, the steps this tutorial has taken since [chapter 7](07-diagram.md) read, in order:

> Diagram › entrypoints.py › inside entrypoints.py › _target_routine → exact › Suspect ›
> Informational › Glossary › Derived naming standard › Stated naming rules ›
> Stated rules, checked › Worth a look › entrypoints_from_manifests › _target_routine

That is thirteen steps, and twelve is what the bar draws by default — the last twelve,
scrolled sideways so that the one you are on is in view:

![The trail strip. It reads TRAIL, a count of the steps behind, then Worth a look › entrypoints_from_manifests › _target_routine, the last one highlighted, followed by buttons reading ← Back, Forward → (greyed out), Clear, and a filled badge reading ◆ 1 kept](images/12-trail-bar.png)

**+N behind** counts the older steps you cannot see: the ones beyond the twelve it draws,
from the chapters before 7, and the ones scrolled out of view to the left, which in a
narrow centre pane is most of them. Your number depends on every hop you have made, so it
will not match anyone else's. Back still reaches every one of them; the count is there so
that nothing falls off the left-hand end without saying so.

Three things about it.

**It records what you selected, not what you clicked.** Every step carries its subject, so
Back does not merely undo a screen, it puts the thing back. That is why
`_target_routine → exact` sits in the list beside pages like *Worth a look* — a routine, an
arrow, a box and a page are all steps, because they are all answers to *what were you
looking at*.

**A change of view is a step too.** `Diagram` is in that list, because switching from Graph
to Diagram while standing on the same routine is something you may well want to undo.

**Forward exists.** Back then Forward is a free look around: nothing is lost by going back
two steps to check something.

## Threads to pull

Select `entrypoints_from_manifests` again — the routine chapters 3 to 7 followed — and
scroll the inspector past IN, OUT, TOUCHES and GOVERNANCE.

![The inspector's THREADS TO PULL section, counted 5, with the explanation "Not the call graph — reasons something nearby is worth a detour. Two routines that never call each other and both write one table are related, and no call graph can say that." A lane headed NAMED LIKE THESE · 2 lists manifests "8 modules, 1 table — defined in __init__.py:1" and entrypoints "3 constants, 1 module, 1 table — defined in entrypoints.py:1". A lane headed UNUSUAL NEARBY · 3 lists _target_routine "2 comments — the most in entrypoints", binding_note "called from 4 places — the most in entrypoints" and exact "nested 2 levels deep — the deepest closure in entrypoints". Every row has a Keep this button](images/12-threads.png)

> **Not the call graph** — reasons something nearby is worth a detour. Two routines that
> never call each other and both write one table are related, and no call graph can say
> that.

Five threads on this one routine, in two lanes. There are five kinds a thread can be, and a
lane appears only where there is something in it:

| | |
|---|---|
| **The other end** | you and somebody else touch the same file, table or boundary |
| **Runs the same shape** | you and somebody else make the same decision, or loop over the same table |
| **Named like these** | a word or a naming convention you are an instance of |
| **Unusual nearby** | an outlier *in your package* |
| **Shares a plan** | the same ticket or decision id is written on both of you |

`entrypoints_from_manifests`'s first lane is two words its own names are made of:
`manifests`, which eight modules and a table are named for, and `entrypoints`, which names
three constants, a module and a table. Both are words the glossary in
[chapter 10](10-words-and-names.md) found defined, and the thread says where.

A busier routine has busier lanes. Select `cmd_analyze` — the **go** on chapter 11's
631-lines card — and it has fifteen threads in four lanes. **The other end** is three
files, `docsource.db`, `README.md` and `source.db`, each with the number of other routines
that name it. **Runs the same shape** is eight decisions: `not args.no_docs`,
`doc_store is not None`, `getattr(args, "standards", None)` and five more. Somewhere else in
the program, something branches on exactly the same test, and knowing where is often the
fastest way to understand what a flag actually does.

**Rarest first.** That lane says *Showing 5 of 8, rarest first*, and the ordering is the
feature: three routines is a detour, three hundred is a category. A thread shared with one
other routine is worth your afternoon; a thread shared with half the program is worth
nothing, and sorting by rarity keeps the first kind at the top.

**Every thread says how big it is** rather than being hidden for being small or large. And
each one states *why* in its own words — *"1 other routine branches on this same test, as
written"* — which includes the blind spot in two words: **as written**. `x == 1` and
`x==1` are two different threads here. The comparison is textual and the sentence says so.

### Nearby means nearby

The last lane on `entrypoints_from_manifests` is three outliers:

> `_target_routine` — 2 comments, the most in `entrypoints`
> `binding_note` — called from 4 places, the most in `entrypoints`
> `exact` — nested 2 levels deep, the deepest closure in `entrypoints`

*The most in `entrypoints`*, not the most in the program. That is the difference between
this panel and [chapter 11](11-worth-a-look.md)'s: a curiosity is *somewhere in this
program and worth the walk*, a thread is *beside you*. The most-commented routine in the
whole program has 785 comments; the most-commented one in this module has 2, and when you
are standing in `entrypoints` the second number is the useful one.

## Keeping something

Press **◇ Keep this** on the `binding_note` thread. Then click `_target_routine`, the thread
above it, and follow that one instead.

![The dashboard on the Diagram view of the resolve compartment, "40 boxes over 178 routines", with _target_routine selected and entrypoints.py — the box that holds it — outlined. The trail reads "Worth a look › entrypoints_from_manifests › _target_routine", after its count of the steps behind, followed by Back, Forward, Clear and a filled badge reading "◆ 1 kept". The inspector shows resolve.entrypoints._target_routine at resolve/entrypoints.py:69–117, tagged ANALYSED and ROUTINE. IN 1 lists entrypoints_from_manifests, CERTAIN, under the docstring "Find the routine a `module:attr` console-script target names." OUT 7 call sites lists exact (CERTAIN), module.startswith (EXTERNAL), exact (CERTAIN), len (EXTERNAL), query in store (CERTAIN), len (EXTERNAL) and str (EXTERNAL). TOUCHES 1 reads SELECT routines READ :112. SHAPE 6 shows guard 3, loop 2, decision 1 and "1 thing moves inside them, and 2 calls go to this program's own code."](images/12-trail-and-kept.jpg)

You are on `_target_routine` now, and `binding_note` is not lost. The trail gains a badge,
**◆ 1 kept**, and the navigator's EXPLORE group gains a row, **Kept · 1**. Click either and
the page behind it says what the shelf is for:

> Things you kept while you were looking at something else. The point of wandering is that
> you find what you were not looking for; this is where it goes so the detour does not cost
> you the thread you were on.

`binding_note` is on it, with a **Drop** beside it. The shelf is per program and it survives
a reload, so a half-finished investigation is still there tomorrow.

## The empty inspector is not empty

Go back to `cmd_analyze` and follow its **The other end** thread to `source.db`. It is an
artefact — a file this program names, not a routine — and almost every panel on it is zero.
None of them is blank:

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

Note also the seven rows under **IN**, each named for the routine that names the file —
`cmd_analyze`, `cmd_revisions` and `cmd_render` in `cli`, `__init__` in `mcp.session`,
`migrate_program` in `migrate`, and `switch_program` and `serve` in `web.serve` — every
one tagged **INFERRED**. DunneFlow
found seven routines that name the string `source.db`, and it will not pretend that naming
a file is the same as opening it. The tag is the tool declining to upgrade a guess.

---

Next: [13. The command line](13-the-command-line.md)
