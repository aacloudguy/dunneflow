# 12. Chasing rabbits

Orienting in an unfamiliar codebase is not as simple as a search. You start with one question, notice
something odd on the way, follow it, notice something else, and twenty minutes later you
have learned five useful things and cannot remember what you were originally doing.

DunneFlow is built *for* that, rather than against it. Three things make wandering safe:
**threads** give you somewhere worth going, the **trail** brings you back, and **keeping**
means a detour gains you treasure.

## Threads to pull

At the bottom of the inspector, for whatever is selected.

![The Threads to pull panel for resolve.entrypoints.entrypoints_from_manifests, headed "THREADS TO PULL 5" and "Not the call graph — reasons something nearby is worth a detour. Two routines that never call each other and both write one table are related, and no call graph can say that." Below it two lanes: NAMED LIKE THESE 2 — manifests, "8 modules, 1 table — defined in __init__.py:1", and entrypoints, "3 constants, 1 module, 1 table — defined in entrypoints.py:1"; and UNUSUAL NEARBY 3 — _target_routine, "2 comments — the most in entrypoints", binding_note, "called from 4 places — the most in entrypoints", and exact, "nested 2 levels deep — the deepest closure in entrypoints". Each row has a "◇ Keep this" button](images/12-threads-to-pull.png)

This is **adjacency by interest, not by edge**. Two routines that never call each other and
both write to one table are coupled, and no call graph will ever tell you that.

| Lane | Why it is worth a detour |
|---|---|
| **The other end** | You write this table; here is who reads it. |
| **Runs the same shape** | You loop over this table; two other routines do too. They never call each other. |
| **Named like these** | Your name follows a convention ninety-eight other things follow — or, as often, your name is a word nothing in this program defines. |
| **Shares a plan** | The same ticket, plan or decision id. |
| **Unusual nearby** | The most commented routine on your plate. The one called from the most places. A value read three times as often as it is written. |

Every thread states **its own size**, so you can weigh it. *Called from 4 places — the most
in entrypoints* says both how many and against what, rather than looking like a general
truth. A lane with nothing in it is left out, which is why the panel above shows two lanes
of the five.

## Worth a look

The **Explore → Worth a look** panel is the same idea with no selection required. This indicates a
doorway when you do not yet know what to ask.

![The Worth a look panel: "12 measurements of this program, each showing what came out furthest from the middle", with "Measured on the base alone" beneath, then the first cards — "3,023 characters in one call argument", 377.9× the middle, _r_diagram, written at web/serve.py:1867, "the middle argument is 8 characters, of 16,049"; "17,585 characters in one constant's value", 308.5×, SCHEMA_SQL at store.py:52; "785 comments on one routine", 157×, web.queries; "89 callers of one routine", 89×, query at store.py:1641 — each with "Follow this go", "How this was measured show the query" and "◇ Keep this"](images/12-worth-a-look.jpg)

Twelve measured extrema, each with **its middle stated beside it**. Every program has a
most-commented routine, so a maximum on its own is a claim nobody can weigh. *3,023
characters in one call argument, 377.9× the middle* is a discovery. *3 levels of nesting
against a middle of 2* is not, and the panel says the second as plainly as the first.

**A curiosity is a measurement, never a judgement.** No severity, no blind spot, nothing
implying a number ought to be smaller. That is what the anomaly worklist is for, and these
are deliberately not that.

**show the query** gives you the SQL that produced the number. It is the query that
returned the whole card, middle and population included, not a query about the number
alone. Run it yourself with `dunneflow query`, one of the CLI-commands.

## The trail

Every selection you make is recorded, and the bar across the top of the centre pane is
your route.

![The trail bar: "TRAIL", a count of the steps behind it, then "Worth a look › entrypoints_from_manifests › _target_routine", the last highlighted, then "← Back", "Forward →" (greyed, with nothing ahead), "Clear" and "◆ 1 kept"](images/12-trail-bar.png)

**← Back** (`⌘Z`, or `Ctrl+Z` on Windows and Linux) and **Forward →** (`⇧⌘Z`,
`Ctrl+Shift+Z`) step along it. They work from anywhere because the person who needs Back is by
definition lost and should not have to find a particular pane first.

**Every step carries what it *is*, not just what it is called.** Two different things can
print the same name. On a real codebase, 531 routines share a module word and every
package has an `__init__` so a trail that stored labels would take you back to the wrong
one to deliver a wrong answer with great confidence.

**The bar is a window onto the history, not the history itself.** It shows a dozen steps;
Back reaches further. What falls off either end is stated, *+N behind* or *+N ahead*, because
a trail that silently forgets is worse than a short one: you would have no way to
know Back could still take you further.

**Forward is a real branch.** Step back three times and the steps ahead of you are still
there, drawn differently from the past, until you select something new.

**Clear** drops the trail back to where you are standing. It keeps that one step,
because Clear is for a trail grown too long to read and not for abandoning the thing on
screen. It does not drop what you have kept.

## ◇ Keep this

Anywhere you see **◇ Keep this,** including the inspector, a thread, a curiosity, a search hit, or a
row on the Algorithms page, that thing lands on a shelf.

![The kept shelf, reached from the "◆ 1 kept" badge: "Things you kept while you were looking at something else. The point of wandering is that you find what you were not looking for; this is where it goes so the detour does not cost you the thread you were on." One kept routine, binding_note, with a Drop button. The trail reads "… Worth a look › _target_routine › kept things" with "◆ 1 kept", and the inspector still shows resolve.entrypoints._target_routine, the routine the reader was on](images/12-kept-shelf.jpg)

The count sits in the trail bar as **◆ 1 kept** and opens the shelf. Every row **opens**
when you click it and goes back to the thing itself, not to a note about it. **Drop** removes
one.

This is the whole point of the feature, and it was once broken in exactly the way that
matters: a kept thing that shows you a row and cannot take you back to it is a bookmark to
nowhere.

### Kept things have different lifetimes, and the shelf says so

- **A routine, a constant, a structure** survives anything above it moving. It is
  identified by its qualified name, not its position, so inserting fifty lines above it
  changes nothing.
- **A word your program states** A ticket id, a table name, a naming pattern. This survives
  re-analysis entirely and means the same thing at both ends of a comparison. Nothing in
  the map minted it. Its row also recounts itself: *how many routines this stands for
  now*, not how many it stood for when you kept it.
- **A line, or a loop at a line**, is only true of the version it was kept in. If you
  switch to a different version the row says so: *kept at 2026-10-02T21:37:11Z, so this
  version may have moved line 92*.
- **A box in a diagram** belongs to the drawing it was drawn in, and is valid at the
  altitude you drew it at. The row says that too.

## A worked detour

1. You are reading `docstore.DocStore.mark_duplicates` because you want to know how
   DunneFlow decides two documents are copies of one another.
2. Its inspector shows **Threads to pull → The other end: `documents` — you write and read
   it · of 20 others, 16 read it and 3 write it and 1 declare it.** You had no idea twenty
   other things touched that table.
3. You follow it. Selecting the table selects every routine that reads or writes it, and
   one of the three other writers is a routine you have never heard of.
4. That is interesting but it is not what you came for. **◇ Keep this** on it.
5. **← Back**, twice. You are on `mark_duplicates` again, on the line you left.
6. When you are done, **◆ 1 kept** takes you straight to it.

The detour cost you nothing, and we hope it was full of value.

---

Next: [13. Settings](13-settings.md)
