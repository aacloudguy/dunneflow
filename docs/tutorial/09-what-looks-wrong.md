# 9. What looks wrong

[Chapter 2](02-the-cover.md) read the cover's third panel and left it there:

> **WHAT LOOKS WRONG** — every finding states its blind spot
>
> Broken **0** · Suspect **25** · Informational **15**

Click **Suspect**.

![The anomalies worklist. Tabs across the top read Broken 0, Suspect 25, Info 15, followed by "25 left to triage" and a progress bar at 0/25, with Prev and Next buttons and the hint "or j/k" on the right. A list on the left shows findings titled "`side` could not be connected: 4 definitions share the name" tagged LOST_EDGE 8×, then `ms`, `self._live.progress`, `note`, `progress`, `port`, `_pick`, `step`. The detail pane on the right repeats the `side` title with the tags SUSPECT, confidence PROBABLE, LOST_EDGE and "8 occurrences", the sentence "`side` is called 8 times, and 4 routines share that name. The call graph has no edge here, so anything downstream is missing from every flow that passes through it", and an indented blind spot. Below it, WHAT IS THIS? offers three buttons: "Not a bug — the blind spot applies" (1), "Real — acknowledged, leave it for now" (2), and "This is a DunneFlow defect, not the program's" (3)](images/09-the-worklist.jpg)

## It is a worklist, not a report

The difference is the counter at the top: **25 left to triage**, and a bar reading **0/25**.

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
| **8 occurrences** | how many places, each one openable |

Severity and confidence are the pair that most tools blur, and blurring them is why most
tools get ignored. *This would be catastrophic but probably is not happening* and *this is
definitely happening and barely matters* are not the same row.

Then the sentence, which says what it means rather than what it is:

> `side` is called 8 times, and 4 routines share that name. The call graph has no edge
> here, so anything downstream is missing from every flow that passes through it.

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

Click **Info 15**.

![The Info lane of the worklist. The list reads "47 loops reach a database, a queue or the network on every pass" (LOOPED_BOUNDARY 47×), "None of the 3 remote calls declares a retry policy" (NO_RETRY 3×), "459 of 863 routines are not reachable from any way in" (UNREACHABLE 459×, marked with a diamond), "19 routines are never called and are not a way in" (DEAD_CODE 19×), then a run of ONE_WAY_TABLE findings for json_each, m, top, reach, sqlite_master, back and doc_table_rows. The detail pane shows "`json_each` is read but never written", tagged INFO, confidence POSSIBLE, ONE_WAY_TABLE, 14 occurrences, with the blind spot "The other half may live in another program, in tests, in a migration, or in SQL built by string interpolation that DunneFlow could not attribute to a table." The summary line above reads "against 2026-09-15 22:14:26: 1 claiming something different · 14 unchanged"](images/09-informational.jpg)

Eleven of the fifteen say the same shape of thing: **a table is read and never written**,
or written and never read. Open them one at a time and eight of the eleven — `json_each`,
`m`, `top`, `reach`, `back`, `looped`, `mv`, `reaches` — turn out not to be tables at all.

`json_each` is SQLite's own table-valued function. `m`, `top`, `looped` and `mv` are
common table expressions — the `WITH m AS …` blocks — inside `web/queries.py`. `reach` and
`back` are the recursive CTEs that walk the call graph in `store.py`. DunneFlow read
`FROM m` and recorded a table read, because from where it was standing that is exactly
what `FROM m` looks like.

So: **press 3.** Eight findings, one detector, one defect. That is the button working as
designed, and the blind spot printed beside each of them already told you where to look —
*"SQL built by string interpolation that DunneFlow could not attribute to a table"* is one
sentence away from *"or a CTE"*.

It is also a nice demonstration of what self-analysis is for. `reach` is the query behind
the number on the cover that says `main` commands 393 routines. The tool is reporting on
the machinery it used to report.

The other three are the opposite case. `sqlite_master` is a real table, genuinely read and
genuinely never written, and the finding is correct. `doc_tables` and `doc_table_rows` are
two real tables in `docs.db` that the documentation extractor fills and nothing reads back
— which is a true and mildly interesting thing to know about this program. Same kind, same
confidence, three different answers; which is why they are offered one at a time rather
than as a count.

## A count that says what it counts

> 459 of 863 routines are not reachable from any way in

The cover said **925 routines**. This says 863. Neither is wrong, and the difference is
the point of writing the denominator down.

```bash
uv run dunneflow query output/dunneflow \
    --sql "SELECT COUNT(*) total, SUM(name='<module>') modules, SUM(name!='<module>') named FROM routines"
```

```
no --output given; maps go to output
total | modules | named
925 | 62 | 863
```

(That first line is DunneFlow saying which maps root it resolved the name under —
[chapter 13](13-the-command-line.md) explains why the path you type is a program name.)

Sixty-two of the 925 are module scopes — the top level of a file, which DunneFlow treats
as a routine because code runs there and it has to belong to something. Asking whether a
module scope is *reachable from a way in* is not a question, so this measure counts the
863 named routines and says so in the title.

Read the blind spot before you read the number, though:

> An edge lost to ambiguity strands everything behind it, so LOST_EDGE findings inflate
> this number. Library code meant to be imported by other programs is also unreachable by
> design.

Twenty-three of the twenty-five Suspect findings are LOST_EDGE. They are upstream of this
one. The number is real and it is also inflated, and both halves are printed.

## The one that changed

Look at the line above the list:

> against 2026-09-15 22:14:26: ◆ **1 claiming something different** · 14 unchanged

The map holds two versions ([chapter 8](08-two-versions.md)), so the findings are held
against each other too. Fourteen of the fifteen say exactly what they said before. One
does not, and it is the unreachable count: **456 in the older snapshot, 459 in this one.**

Three more. Chapter 8 found exactly three routines added for Linux — `_desktop_session`,
`_picker_order` and `_reveal_linux` — and all three are in this finding's list of 459.
Nothing here was told about Linux either.

## From the command line

```bash
uv run dunneflow check output/dunneflow
```

```
[SUSPECT/PROBABLE] LOST_EDGE: `side` could not be connected: 4 definitions share the name  web/changes.py
…
0 broken, 25 suspect, 15 informational
```

`check` exits non-zero **only on BROKEN**, which is what makes it usable as a CI gate: a
build does not fail because a tool is unsure. Here it exits 0, and would exit 0 with all
forty findings still on the screen.

---

Next: [10. Words and names](10-words-and-names.md)
