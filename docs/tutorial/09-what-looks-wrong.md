# 9. What looks wrong

[Chapter 2](02-the-cover.md) read the cover's third panel and left it there:

> **WHAT LOOKS WRONG** — every finding states its blind spot
>
> Broken **0** · Suspect **19** · Informational **19**

Click **Suspect**.

![The anomalies worklist. Tabs across the top read Broken 0, Suspect 19, Info 19, followed by "19 left to triage" and a progress bar at 0/19, with Prev and Next buttons, the hint "or j/k" and a "changes" button. Above the list: "against 2026-11-13 03:56:47: +4 added · 15 unchanged ·" and a button reading "2 deleted — in 2026-11-13 03:56:47 only". The list on the left shows findings titled "`self._live.note` could not be connected: 2 definitions…" tagged LOST_EDGE 3× and marked with a plus, then `self._live.out_dir.resolve` and `self.conn.close` 3× each, "2 of 3 remote calls set no timeout" tagged NO_TIMEOUT 2×, and `self._base.docs.close`, `self._base.store.close`, `self._f.close` (another plus), `self._live.current.store.query`, `self._live.out_root.resolve` and `self._worker.stop` 1× each. The detail pane repeats the `self._live.note` title with the tags SUSPECT, confidence PROBABLE, LOST_EDGE and "3 occurrences", the file web/serve.py, the sentence "`self._live.note` is called 3 times, and 2 routines share that name. The call graph has no edge here, so anything downstream is missing from every flow that passes through it", and an indented blind spot. Below it, WHAT IS THIS? offers three buttons: "Not a bug — the blind spot applies" (1), "Real — acknowledged, leave it for now" (2), and "This is a DunneFlow defect, not the program's" (3). The inspector on the right shows entrypoints_from_manifests](images/09-the-worklist.jpg)

## It is a worklist, not a report

The difference is the counter at the top: **19 left to triage**, and a bar reading **0/19**.

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
| **3 occurrences** | how many places, each one openable |

Severity and confidence are the pair that most tools blur, and blurring them is why most
tools get ignored. *This would be catastrophic but probably is not happening* and *this is
definitely happening and barely matters* are not the same row.

Then the sentence, which says what it means rather than what it is:

> `self._live.note` is called 3 times, and 2 routines share that name. The call graph has
> no edge here, so anything downstream is missing from every flow that passes through it.

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

Click **Info 19**.

![The Info lane of the worklist: "19 left to triage", 0/19, and above the list "against 2026-11-13 03:56:47: +2 added · ◈ 6 claiming something different · 11 unchanged ·" and a button reading "1 deleted — in 2026-11-13 03:56:47 only". The list reads "4 routines have at least one…" (UNTYPED_PARAMETER 4×, marked with a diamond), "1 of 2,424 routines declare…" (MISSING_RETURN_TYPE 1×), "75 loops reach a database, a queue…" (LOOPED_BOUNDARY 75×, diamond), "None of the 3 remote calls declares a retry policy" (NO_RETRY 3×), "1,223 of 2,424 routines are not reachable fro…" (UNREACHABLE 1223×, diamond), "55 routines are never called and are not a way in" (DEAD_CODE 55×, diamond), then ONE_WAY_TABLE findings for json_each 27× (diamond), m 12× and top 12×. The detail pane shows "`json_each` is read but never written", tagged INFO, confidence POSSIBLE, ONE_WAY_TABLE, 27 occurrences, the line "`json_each`: 27 reads, 0 writes.", and the blind spot "The other half may live in another program, in tests, in a migration, or in SQL built by string interpolation that DunneFlow could not attribute to a table."](images/09-informational.jpg)

Thirteen of the nineteen say the same shape of thing: **a table is read and never written**,
or written and never read. Open them one at a time and seven of the thirteen — `json_each`,
`m`, `top`, `reach`, `back`, `looped`, `mv` — turn out not to be tables at all.

`json_each` is SQLite's own table-valued function. `m`, `top`, `looped` and `mv` are
common table expressions — the `WITH m AS …` blocks — inside `web/queries.py`. `reach` and
`back` are the recursive CTEs that walk the call graph in `store.py`. DunneFlow read `FROM m` and recorded a table read, because from where it
was standing that is exactly what `FROM m` looks like.

So: **press 3.** Seven findings, one detector, one defect. That is the button working as
designed, and the blind spot printed beside each of them already told you where to look —
*"SQL built by string interpolation that DunneFlow could not attribute to a table"* is one
sentence away from *"or a CTE"*.

It is also a nice demonstration of what self-analysis is for. `reach` is the query that
works out how far a way in reaches — the measure behind the 602 beside the `dunneflow`
command on the cover, on a map that is still being written; a finished one now walks the
same graph in memory. The tool is reporting on the machinery it used to report.

The other six are the opposite case. `sqlite_master` is a real table, genuinely read and
genuinely never written, and the finding is correct. `supplied_touches` and
`supplied_ways_in` are two tables this release added, written and — the finding says —
never read back; they carry a plus in the list, because the older snapshot has no such
finding. `doc_tables` and `doc_table_rows` are
two real tables in the documentation store that the documentation extractor fills and
nothing reads back — which is a true and mildly interesting thing to know about this
program. And `manifests` is written and never read back *on purpose*: the table exists so
that a person can put a query behind a sentence on the cover, and the reader it was built
for is you, at the command line, which no call graph can see. Same kind, same confidence,
several different answers; which is why they are offered one at a time rather than as a
count.

## A count that says what it counts

![The Info lane with the UNREACHABLE finding open: "1,223 of 2,424 routines are not reachable from any way in", tagged INFO, confidence POSSIBLE, UNREACHABLE, 1223 occurrences, with the sentence "These cannot run when the program is started by any entrypoint DunneFlow found. Reach followed every dispatched call into each body that may answer it." and the blind spot "An edge lost to ambiguity strands everything behind it, so LOST_EDGE findings inflate this number. Library code meant to be imported by other programs is also unreachable by design." In the list on the left, the row is marked with a diamond](images/09-unreachable.jpg)

> 1,223 of 2,424 routines are not reachable from any way in

The cover said **2,552 routines**. This says 2,424. Neither is wrong, and the difference is
the point of writing the denominator down.

```bash
uv run dunneflow query output/dunneflow \
    --sql "SELECT COUNT(*) total, SUM(name='<module>') modules, SUM(name!='<module>') named FROM routines"
```

```
no --output given; maps go to output
total | modules | named
2552 | 128 | 2424
```

(That first line is DunneFlow saying which maps root it resolved the name under —
[chapter 13](13-the-command-line.md) explains why the path you type is a program name.)

128 of the 2,552 are module scopes — the top level of a file, which DunneFlow treats
as a routine because code runs there and it has to belong to something. Asking whether a
module scope is *reachable from a way in* is not a question, so this measure counts the
2,424 named routines and says so in the title.

Read the blind spot before you read the number, though:

> An edge lost to ambiguity strands everything behind it, so LOST_EDGE findings inflate
> this number. Library code meant to be imported by other programs is also unreachable by
> design.

Eighteen of the nineteen Suspect findings are LOST_EDGE. They are upstream of this
one. The number is real and it is also inflated, and both halves are printed.

So is the other half of the blind spot. The dashboard's own routes are reached by looking
their names up in a table — a request for `/api/naming` finds `_r_naming` by name — and a
call graph cannot follow that. `do_GET`, which receives every request, is a way in; the
routes it hands them to are in this list.

## The ones that changed

Look at the line above the list:

> against 2026-11-13 03:56:47: **+2 added** · ◈ **6 claiming something different** · 11
> unchanged · 1 deleted — in 2026-11-13 03:56:47 only

The map holds more than one version ([chapter 8](08-two-versions.md)), so the findings are
held against each other too. Eleven of the nineteen say exactly what they said before. Two
are new — the two `supplied_` tables. One is gone: `reaches`, a CTE in `anomalies.py` that
the older snapshot read as a table and today's source no longer has. And six are the same
finding making a different claim, each marked with a diamond:

| | then | now |
|---|---|---|
| routines with an untyped parameter | 3 | 4 |
| loops that reach a database, a queue or the network on every pass | 54 | 75 |
| routines not reachable from any way in | 927 of 1,421 | 1,223 of 2,424 |
| routines never called that are not a way in | 49 | 55 |
| reads of `json_each` | 14 | 27 |
| reads of `reach` | 4 | 5 |

*The same finding making a different claim* is its own answer, and it is kept apart from
*added* for the reason chapter 8's bands are kept apart. A reader triaging this lane after
a release does not want nineteen findings; they want the eight that are not what they were.

The Suspect lane says the same kind of thing about itself: **+4 added · 15 unchanged · 2
deleted**. The two that went are `self.ancestors` and `self.masked.line_at`, both in
`extractors/cpp` — the Python C++ reader chapter 8 found deleted. The code went, and the
findings about it went with it, without anybody closing them.

## From the command line

```bash
uv run dunneflow check output/dunneflow
```

```
no --output given; maps go to output
[SUSPECT/PROBABLE] LOST_EDGE: `self._live.note` could not be connected: 2 definitions share the name  web/serve.py
[SUSPECT/PROBABLE] LOST_EDGE: `self._live.out_dir.resolve` could not be connected: 5 definitions share the name  web/serve.py
[SUSPECT/PROBABLE] LOST_EDGE: `self.conn.close` could not be connected: 8 definitions share the name  docstore.py
[SUSPECT/PROBABLE] NO_TIMEOUT: 2 of 3 remote calls set no timeout  web/serve.py:4025
…
0 broken, 19 suspect, 19 informational
```

`check` exits non-zero **only on BROKEN**, which is what makes it usable as a CI gate: a
build does not fail because a tool is unsure. Here it exits 0, and would exit 0 with all
thirty-eight findings still on the screen.

---

Next: [10. Words and names](10-words-and-names.md)
