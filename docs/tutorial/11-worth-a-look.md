# 11. Worth a look

[Chapter 9](09-what-looks-wrong.md) was the pile of things that might be wrong. This is the
opposite pile, and it is the one that gets you into an unfamiliar program fastest.

Open **EXPLORE › Worth a look**.

![The doorway panel. A highlighted note reads "12 measurements of this program, each showing what came out furthest from the middle. None of them is a problem and none of them is a finding — there is no severity here and nothing that says a number ought to be smaller. Each says its value, the middle it is being read against, and how far apart the two are; the list is ordered by that distance, so the strangest is first and the ones barely above their middle sort last and say so. Pull one and see where it goes. Measured on the base alone. These are not compared across the two versions — what a card names is what the version on screen holds." Six cards follow in two columns: "2,382 characters in one call argument · 264.7× the middle · _r_diagram · written at web/serve.py:1600 · the middle argument is 9 characters, of 10,653"; "13,529 characters in one constant's value · 152.0× the middle · SCHEMA_SQL · declared at store.py:49"; "731 comments on one routine · 121.8× the middle · web.queries"; "79 callers of one routine · 79× the middle · query · declared at store.py:1180"; "449 lines in one routine · 24.9× the middle · cmd_analyze"; "25 boundaries reached from one routine · 12.5× the middle · write_file_facts". Each card carries "Follow this go", "How this was measured show the query" and a "Keep this" button](images/11-worth-a-look.jpg)

## Twelve maxima, each with its middle

> **12 measurements of this program, each showing what came out furthest from the middle.**
> None of them is a problem and none of them is a finding — there is no severity here and
> nothing that says a number ought to be smaller.

Every program has a most-commented routine. A maximum on its own is a claim nobody can
weigh, so every card states the **middle** it is being read against, and the list is
ordered by the distance between the two:

| | | |
|---|---|---|
| 2,382 characters in one call argument | `_r_diagram` | 264.7× the middle |
| 13,529 characters in one constant's value | `SCHEMA_SQL` | 152.0× |
| 731 comments on one routine | `web.queries` | 121.8× |
| 79 callers of one routine | `query` | 79× |
| 449 lines in one routine | `cmd_analyze` | 24.9× |
| 25 boundaries reached from one routine | `write_file_facts` | 12.5× |
| 38× out of balance: one table's reads against its writes | `boundaries` | 9.5× |
| 8 places one loop reaches in a single pass | `write_file_facts` | 8× |
| 5 loops over one table | `routines` | 5× |
| 9 parameters on one routine | `_record_control` | 4.5× |
| 2 routines carry one governance id | `AC-4` | 2× |
| 3 levels of nesting in one closure | `ms` | 1.5× |

Read the top and the bottom of that list together and you have the design in one glance.
*13,529 characters in a constant, against a middle of 89* is a discovery. *Three levels
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

- **`SCHEMA_SQL`, 13,529 characters**, is the entire database schema as one string. This
  is a program whose largest single value is a schema — which is what [chapter 2](02-the-cover.md)
  told you from a different direction when DATABASE came out at 272 of 487 boundary touches.
- **`web.queries`, 731 comments**, is a module that is almost entirely SQL with an
  explanation above each statement. The busiest commenting in the program is on the
  queries, not the code.
- **`query`, 79 callers**, against a middle of 1. One routine in `store.py` is how
  everything talks to SQLite. The store really is the spine.
- **`cmd_analyze`, 449 lines** — the command that does the work — and **`write_file_facts`,
  25 boundaries**, which is the routine that writes a file's facts into all of them.

None of that came from reading code. It came from twelve queries and a middle.

## The query that returned it

Click **show the query** on any card.

![The 731-comments card expanded. Below the card's numbers a SQL block reads: WITH m AS MATERIALIZED (SELECT c.routine_id AS k, COUNT(*) AS n FROM comments c GROUP BY c.routine_id), top AS (SELECT k, n FROM m ORDER BY n DESC, k LIMIT 1) SELECT r.id AS node, r.name AS name, r.qualname AS qualname, r.file || ':' || r.line_start AS whence, top.n AS value, (SELECT n FROM m ORDER BY n LIMIT 1 OFFSET (SELECT COUNT(*)/2 FROM m)) AS middle, (SELECT COUNT(*) FROM m WHERE m.n = top.n) AS ties, (SELECT COUNT(*) FROM m) AS population FROM top JOIN routines r ON r.id = top.k. Underneath, in small text: "Run it yourself: dunneflow query <this map> --sql "…" — the directory this dashboard is serving, not the source tree. Every number on this card comes out of that one statement: the value, the middle, how many tie with it, and how large a population it came out of. It is not a query about the number, it is the query that returned it."](images/11-show-the-query.jpg)

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
dc7f7b22bb28ddeb | <module> | web.queries.<module> | web/queries.py:1 | 731 | 6 | 1 | 352
```

731, middle 6, one holder, out of 352 routines that carry any comment at all. The card is
reproducible, and *this* is what [chapter 9](09-what-looks-wrong.md)'s note about module
scopes looks like from the other side: the thing with 731 comments is `web.queries.<module>`,
the top level of a file, which DunneFlow counts as a routine because code runs there.

Notice, while you are here, that the statement defines two CTEs called `m` and `top`. Those
are two of the eight things DunneFlow's own anomaly detector reported as tables read and
never written, two chapters ago. Same statement, both chapters.

## Not a judgement

A curiosity is a measurement. There is no severity, no confidence, no blind spot, and
nothing anywhere on the panel implying a number ought to be smaller. `cmd_analyze` being
449 lines is not a complaint; it is a door.

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
