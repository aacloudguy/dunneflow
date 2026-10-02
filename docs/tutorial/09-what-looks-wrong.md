# 9. What looks wrong

[Chapter 2](02-the-cover.md) read the cover's third panel and left it there:

> **WHAT LOOKS WRONG** — every finding states its blind spot
>
> Broken **0** · Suspect **26** · Informational **18**

Click **Suspect**.

![The anomalies worklist. Tabs across the top read Broken 0, Suspect 26, Info 18, followed by "26 left to triage" and a progress bar at 0/26, with Prev and Next buttons, the hint "or j/k" and a "changes" button. Above the list: "against 2026-10-02 19:59:47: +1 added · 25 unchanged". The list on the left shows findings titled "`_literal` could not be connected: 2 definitions…" tagged LOST_EDGE 16×, then `_scan`, `self.ancestors` and `self.masked.line_at` 4× each, `self._live.out_dir.resolve` and `self.conn.close` 3× each, `_walk` 2× marked with a plus, `self._awaited.add` and `walk` 2× each, and "2 of 3 remote calls set no…" tagged NO_TIMEOUT. The detail pane repeats the `_literal` title with the tags SUSPECT, confidence PROBABLE, LOST_EDGE and "16 occurrences", the file extractors/python/extract.py, the sentence "`_literal` is called 16 times, and 2 routines share that name. The call graph has no edge here, so anything downstream is missing from every flow that passes through it", and an indented blind spot. Below it, WHAT IS THIS? offers three buttons: "Not a bug — the blind spot applies" (1), "Real — acknowledged, leave it for now" (2), and "This is a DunneFlow defect, not the program's" (3). The inspector on the right still shows the arrow _target_routine → exact from chapter 7](images/09-the-worklist.jpg)

## It is a worklist, not a report

The difference is the counter at the top: **26 left to triage**, and a bar reading **0/26**.

A report is something you read. A worklist is something you get to the end of. Every
finding has three buttons under it and one keystroke each, `↓ Next` and `j`/`k` move you
through them, and the bar fills as you decide. At the end the number is zero because *you*
made it zero, not because the tool stopped saying anything.

## What a finding is made of

Take the first one apart. It carries four separate claims and they are deliberately never
merged:

| | |
|---|---|
| **SUSPECT** | the severity — what it would mean for the program |
| **confidence PROBABLE** | how sure DunneFlow is that it is seeing what it thinks |
| **LOST_EDGE** | the kind — the family of thing it is |
| **16 occurrences** | how many places, each one openable |

Severity and confidence are the pair that most tools blur, and blurring them is why most
tools get ignored. *This would be catastrophic but probably is not happening* and *this is
definitely happening and barely matters* are not the same row.

Then the sentence, which says what it means rather than what it is:

> `_literal` is called 16 times, and 2 routines share that name. The call graph has no
> edge here, so anything downstream is missing from every flow that passes through it.

And then the part that governs the whole feature:

> blind spot — *If the receiver is a third-party object, or the method is supplied by a
> mixin or set dynamically, no local definition was ever intended and nothing is wrong.*

**Every finding states what would make it a false alarm.** Not as politeness — as the
thing that makes the other three claims usable. A finding without its blind spot is a
guess wearing a uniform, and you cannot triage a guess.

## The third button

> 1. Not a bug — the blind spot applies
> 2. Real — acknowledged, leave it for now
> 3. **This is a DunneFlow defect, not the program's**

Most tools have the first two. The third is unusual enough that the panel explains itself
underneath:

> **Why the third button exists.** On the first run against a live codebase, six confident
> findings in a row were defects in DunneFlow rather than in the program it was reading. A
> finding dismissed this way is not just cleared — it is evidence that a detector needs
> fixing, which is a different pile from "the blind spot applies here".

You are about to need it.

## The informational lane

Click **Info 18**.

![The Info lane of the worklist: "18 left to triage", 0/18, and above the list "against 2026-10-02 19:59:47: ◈ 2 claiming something different · 16 unchanged". The list reads "3 routines have at least one…" (UNTYPED_PARAMETER 3×), "1 of 1,442 routines declare no retur…" (MISSING_RETURN_TYPE 1×), "55 loops reach a database, a queue…" (LOOPED_BOUNDARY 55×, marked with a diamond), "None of the 3 remote calls declares a retry policy" (NO_RETRY 3×), "930 of 1,442 routines are not reachable from…" (UNREACHABLE 930×, marked with a diamond), "58 routines are never called and are not a way in" (DEAD_CODE 58×), then ONE_WAY_TABLE findings for json_each 14×, m 12×, top 12× and reach 4×. The detail pane shows "`json_each` is read but never written", tagged INFO, confidence POSSIBLE, ONE_WAY_TABLE, 14 occurrences, the line "`json_each`: 14 reads, 0 writes.", and the blind spot "The other half may live in another program, in tests, in a migration, or in SQL built by string interpolation that DunneFlow could not attribute to a table."](images/09-informational.jpg)

Twelve of the eighteen say the same shape of thing: **a table is read and never written**,
or written and never read. Open them one at a time and eight of the twelve — `json_each`,
`m`, `top`, `reach`, `back`, `looped`, `mv`, `reaches` — turn out not to be tables at all.

`json_each` is SQLite's own table-valued function. `m`, `top`, `looped` and `mv` are
common table expressions — the `WITH m AS …` blocks — inside `web/queries.py`. `reach` and
`back` are the recursive CTEs that walk the call graph in `store.py`, and `reaches` is one
in `anomalies.py`. DunneFlow read `FROM m` and recorded a table read, because from where it
was standing that is exactly what `FROM m` looks like.

So: **press 3.** Eight findings, one detector, one defect. That is the button working as
designed, and the blind spot printed beside each of them already told you where to look —
*"SQL built by string interpolation that DunneFlow could not attribute to a table"* is one
sentence away from *"or a CTE"*.

It is also a nice demonstration of what self-analysis is for. `reach` is the query that
works out how far a way in reaches — the measure behind the 488 beside the `dunneflow`
command on the cover, on a map that is still being written; a finished one now walks the
same graph in memory. The tool is reporting on the machinery it used to report.

The other four are the opposite case. `sqlite_master` is a real table, genuinely read and
genuinely never written, and the finding is correct. `doc_tables` and `doc_table_rows` are
two real tables in the documentation store that the documentation extractor fills and
nothing reads back — which is a true and mildly interesting thing to know about this
program. And `manifests` is written and never read back *on purpose*: the table exists so
that a person can put a query behind a sentence on the cover, and the reader it was built
for is you, at the command line, which no call graph can see. Same kind, same confidence,
four different answers; which is why they are offered one at a time rather than as a
count.

## A count that says what it counts

![The Info lane with the UNREACHABLE finding open: "930 of 1,442 routines are not reachable from any way in", tagged INFO, confidence POSSIBLE, UNREACHABLE, 930 occurrences, with the sentence "These cannot run when the program is started by any entrypoint DunneFlow found." and the blind spot "An edge lost to ambiguity strands everything behind it, so LOST_EDGE findings inflate this number. Library code meant to be imported by other programs is also unreachable by design." In the list on the left, the row is marked with a diamond](images/09-unreachable.jpg)

> 930 of 1,442 routines are not reachable from any way in

The cover said **1,550 routines**. This says 1,442. Neither is wrong, and the difference is
the point of writing the denominator down.

```bash
uv run dunneflow query output/dunneflow \
    --sql "SELECT COUNT(*) total, SUM(name='<module>') modules, SUM(name!='<module>') named FROM routines"
```

```
no --output given; maps go to output
total | modules | named
1550 | 108 | 1442
```

(That first line is DunneFlow saying which maps root it resolved the name under —
[chapter 13](13-the-command-line.md) explains why the path you type is a program name.)

108 of the 1,550 are module scopes — the top level of a file, which DunneFlow treats
as a routine because code runs there and it has to belong to something. Asking whether a
module scope is *reachable from a way in* is not a question, so this measure counts the
1,442 named routines and says so in the title.

Read the blind spot before you read the number, though:

> An edge lost to ambiguity strands everything behind it, so LOST_EDGE findings inflate
> this number. Library code meant to be imported by other programs is also unreachable by
> design.

Twenty-five of the twenty-six Suspect findings are LOST_EDGE. They are upstream of this
one. The number is real and it is also inflated, and both halves are printed.

So is the other half of the blind spot. The dashboard's own routes are reached by looking
their names up in a table — a request for `/api/naming` finds `_r_naming` by name — and a
call graph cannot follow that. `do_GET`, which receives every request, is a way in; the
routes it hands them to are in this list.

## The two that changed

Look at the line above the list:

> against 2026-10-02 19:59:47: ◈ **2 claiming something different** · 16 unchanged

The map holds more than one version ([chapter 8](08-two-versions.md)), so the findings are
held against each other too. Sixteen of the eighteen say exactly what they said before.
Two do not. One loop more reaches a database on every pass — **54 in the older snapshot,
55 in this one** — and the unreachable count moved: **921 of 1,421 then, 930 of 1,442
now.**

Nine more, and the finding can say exactly which. Chapter 8 found twenty-two named routines
added, and ten of them are in this finding's list: `cacheKey` and `isGlobalFetch`, in the
TypeScript reader, which runs as a program of its own; `_held`, called from the diagram's
drawing code; `_relaxed` and `_relaxed_lane`, called from the two naming routes — reached,
like every route, through that table; and `_locally_bound`, `_visible`, `_in_module`,
`_one` and `_constructor`, in the Python reader and its call resolver, which the analysis
loads as a plugin by name rather than importing. The one it lost is `_plural`, which was
unreachable before and is gone now — lifted into `words.py`, where its successor is called
from the command line. The other twelve are reached from a way in. Nothing here was told
which was which.

(The Suspect lane has one of these too, marked **+**: `_walk` *could not be connected*.
The C++ and Kotlin readers each have a `_walk` that calls itself, and the older snapshot
bound each of those calls to the *other* language's `_walk` — a confident edge, and a wrong
one. This version will not guess between two routines of the same name, and records the
call as lost instead. A lost edge is on this list where you can see it; a wrong one was
nowhere. The right answer, a function calling itself, is one the tool should have found,
and the finding is what tells you to look.)

## From the command line

```bash
uv run dunneflow check output/dunneflow
```

```
no --output given; maps go to output
[SUSPECT/PROBABLE] LOST_EDGE: `_literal` could not be connected: 2 definitions share the name  extractors/python/extract.py
[SUSPECT/PROBABLE] LOST_EDGE: `_scan` could not be connected: 2 definitions share the name  extractors/cpp/control.py
…
[SUSPECT/PROBABLE] NO_TIMEOUT: 2 of 3 remote calls set no timeout  web/serve.py:3764
…
0 broken, 26 suspect, 18 informational
```

`check` exits non-zero **only on BROKEN**, which is what makes it usable as a CI gate: a
build does not fail because a tool is unsure. Here it exits 0, and would exit 0 with all
forty-four findings still on the screen.

---

Next: [10. Words and names](10-words-and-names.md)
