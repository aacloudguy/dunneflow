# 11. Worth a look

[Chapter 9](09-what-looks-wrong.md) was the pile of things that might be wrong. This is the
opposite pile, and it is the one that gets you into an unfamiliar program fastest.

Open **EXPLORE › Worth a look**.

![The doorway panel. A highlighted note reads "12 measurements of this program, each showing what came out furthest from the middle. None of them is a problem and none of them is a finding — there is no severity here and nothing that says a number ought to be smaller. Each says its value, the middle it is being read against, and how far apart the two are; the list is ordered by that distance, so the strangest is first and the ones barely above their middle sort last and say so. Pull one and see where it goes. Measured on the base alone. These are not compared across the two versions — what a card names is what the version on screen holds." Cards follow in two columns: "3,023 characters in one call argument · 377.9× the middle · _r_diagram · written at web/serve.py:1867 · the middle argument is 8 characters, of 16,033"; "17,585 characters in one constant's value · 308.5× the middle · SCHEMA_SQL · declared at store.py:52 · the middle constant is 57 characters, of 604"; "782 comments on one routine · 156.4× the middle · web.queries · declared at web/queries.py:1 · the middle routine that carries any carries 5, of 522 that do"; "89 callers of one routine · 89× the middle · query · declared at store.py:1641 · the middle called routine has 1, of 1,182 that are called at all"; and, cut off at the foot, "631 lines in one routine · 37.1× the middle" and "25 boundaries reached from one routine". Each card carries "Follow this go", "How this was measured show the query" and a "Keep this" button](images/11-worth-a-look.jpg)

## Twelve maxima, each with its middle

> **12 measurements of this program, each showing what came out furthest from the middle.**
> None of them is a problem and none of them is a finding — there is no severity here and
> nothing that says a number ought to be smaller.

Every program has a most-commented routine. A maximum on its own is a claim nobody can
weigh, so every card states the **middle** it is being read against, and the list is
ordered by the distance between the two:

| | | |
|---|---|---|
| 3,023 characters in one call argument | `_r_diagram` | 377.9× the middle |
| 17,585 characters in one constant's value | `SCHEMA_SQL` | 308.5× |
| 782 comments on one routine | `web.queries` | 156.4× |
| 89 callers of one routine | `query` | 89× |
| 631 lines in one routine | `cmd_analyze` | 37.1× |
| 25 boundaries reached from one routine | `write_file_facts` | 25× |
| 11 loops over one table | `routines` | 11× |
| 40× out of balance: one table's reads against its writes | `boundaries` | 10× |
| 8 places one loop reaches in a single pass | `write_file_facts` | 8× |
| 9 parameters on one routine | `render_all` | 4.5× |
| 2 routines carry one governance id | `AC-4` | 2× |
| 3 levels of nesting in one closure | `libOf` | 1.5× |

Scroll to the foot of the panel and the last cards are there too, saying exactly as much
about themselves as the first:

![The last six cards of the doorway panel. "11 loops over one table" ends with "the middle table that is looped over at all carries 1, of 18 that are"; beside it, boundaries, "1 written, 40 read", "the middle table is 4× out, of 36 both read and written". Then "8 places one loop reaches in a single pass · 8× the middle · write_file_facts · written at store.py:1138 · the middle loop that reaches anything reaches 1, of 113 that do"; "9 parameters on one routine · 4.5× the middle · render_all · declared at render/markdown.py:77 · the middle routine that takes any takes 2, of 1,396 that do · 2 others take as many"; "2 routines carry one governance id · 2× the middle · AC-4 · cited as a ticket · the middle id is carried by 1, of 22 · 5 others are carried by as many"; and "3 levels of nesting in one closure · 1.5× the middle · libOf · declared at plugins/typescript/src/program.ts:191 · the middle closure is 2 deep, of 52 · 9 others are nested as deep"](images/11-last-cards.jpg)

Read the top and the bottom of that list together and you have the design in one glance.
*17,585 characters in a constant, against a middle of 57* is a discovery. *Three levels
of nesting, against a middle of two* is not — and the last card says so as plainly as the
first does, rather than being dropped for being boring. It even says how much company it
has: **9 others are nested as deep**.

Nothing is left out for having nothing to report. A measure with no population — a program
that runs no SQL has no lopsided table — is named with the rest, because eleven cards and
twelve cards are different claims and you have no way to tell a missing measure from an
absent one.

## What these twelve say about DunneFlow

Do not skip past the specimens. Taken together they are a portrait, and every one of them
is true of the program you have been reading about for ten chapters:

- **`SCHEMA_SQL`, 17,585 characters**, is the entire database schema as one string. This
  is a program whose largest single value is a schema — which is what [chapter 2](02-the-cover.md)
  told you from a different direction when DATABASE came out at 290 of 526 boundary touches.
- **`web.queries`, 782 comments**, is a module that is almost entirely SQL with an
  explanation above each statement. The busiest commenting in the program is on the
  queries, not the code.
- **`query`, 89 callers**, against a middle of 1. One routine in `store.py` is how
  everything talks to SQLite. The store really is the spine.
- **`cmd_analyze`, 631 lines** — the command that does the work — and **`write_file_facts`,
  25 boundaries**, which is the routine that writes a file's facts into all of them. It
  turns up twice, because one of its loops is also the one that reaches 8 places in a
  single pass.
- **`routines`, looped over 11 times**, the first of them at `resolve/entrypoints.py:92` —
  inside `_target_routine`, a few lines from the routine this tutorial has been following.
- **`libOf`, 3 levels deep**, is TypeScript. The deepest closure in the program is in the
  reader that taught it a second language.

None of that came from reading code. It came from twelve queries and a middle.

## The query that returned it

Click **show the query** on any card.

![The 782-comments card expanded to the full width of the panel. Below the card's numbers a SQL block reads: WITH m AS MATERIALIZED (SELECT c.routine_id AS k, COUNT(*) AS n FROM comments c GROUP BY c.routine_id), top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1) SELECT r.id AS node, r.name AS name, r.qualname AS qualname, r.file || ':' || r.line_start AS whence, top.n AS value, (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle, (SELECT COUNT(*) FROM m WHERE m.n = top.n) AS ties, (SELECT COUNT(*) FROM m) AS population FROM top JOIN routines r ON r.id = top.k. Underneath, in small text: "Run it yourself: dunneflow query <this map> --sql "…" — the directory this dashboard is serving, not the source tree. Every number on this card comes out of that one statement: the value, the middle, how many tie with it, and how large a population it came out of. It is not a query about the number, it is the query that returned it." The cards for 89 callers of one routine and 631 lines in one routine continue below it](images/11-show-the-query.jpg)

> It is not a query *about* the number, it is the query that returned it.

That sentence is the whole discipline. Value, middle, ties and population all come out of
one scan, so they cannot disagree with each other — and the statement on screen is the one
that ran. Copy it:

```bash
uv run dunneflow query output/dunneflow --sql "WITH m AS MATERIALIZED (
    SELECT c.routine_id AS k, COUNT(*) AS n FROM comments c GROUP BY c.routine_id),
top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1)
SELECT r.id AS node, r.name AS name, r.qualname AS qualname,
       r.file || ':' || r.line_start AS whence, top.n AS value,
       (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle,
       (SELECT COUNT(*) FROM m WHERE m.n = top.n)                             AS ties,
       (SELECT COUNT(*) FROM m)                                               AS population
FROM top JOIN routines r ON r.id = top.k"
```

```
no --output given; maps go to output
node | name | qualname | whence | value | middle | ties | population
4b39b1f5bda86280 | <module> | web.queries.<module> | web/queries.py:1 | 782 | 5 | 1 | 522
```

782, middle 5, one holder, out of 522 routines that carry any comment at all. The card is
reproducible, and *this* is what [chapter 9](09-what-looks-wrong.md)'s note about module
scopes looks like from the other side: the thing with 782 comments is `web.queries.<module>`,
the top level of a file, which DunneFlow counts as a routine because code runs there.

Notice, while you are here, that the statement defines two CTEs called `m` and `top`. Those
are two of the names DunneFlow's own anomaly detector reported as tables read and never
written, two chapters ago. Same statement, both chapters.

## Not a judgement

A curiosity is a measurement. There is no severity, no confidence, no blind spot, and
nothing anywhere on the panel implying a number ought to be smaller. `cmd_analyze` being
631 lines is not a complaint; it is a door.

That line is held deliberately, because the moment a doorway panel starts hinting, you
have to argue with it instead of walking through it. The pile that *is* allowed to say
something is wrong is [chapter 9](09-what-looks-wrong.md)'s, and it has to state its blind
spot to do so.

One more line in the note, easy to miss:

> Measured on the base alone. These are not compared across the two versions — what a card
> names is what the version on screen holds.

## Two ways out of a card

Each card offers **Follow this go**, which selects the thing it names — the whole panel is
a set of doors, and the rest of the application is already showing whatever you walk
through.

And **◇ Keep this**, which is the subject of the next chapter.

---

Next: [12. Threads and the trail](12-threads-and-the-trail.md)
