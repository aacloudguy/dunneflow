# 14. Comparing two versions

Read this once you are comfortable with a single version. Everything below sits on top of
the six views you already know.

## What this gives you that a text diff does not

`git diff` tells you which lines moved, and tells you better than anything else. It cannot
tell you **what moves changed**:

- a routine that is in one version and not the other
- a routine that writes to a table it does not write to over there
- a signature whose types differ
- a call that resolves in one version and not in the other
- an argument a caller passes that it did not pass before

That is the half a text diff cannot state, and it is one reason this exists. It also
works where a diff cannot: **two directories with no shared history at all** showing a vendor
drop against last quarter's vendor drop, a tree on a memory stick against the one you have.

## Getting a second version

A program directory holds one **working** snapshot, which each analysis replaces. To keep
two, you seal the first. Note that if you are using the application binary, you do not need
to type "uv run" in the examples below. Start with "dunneflow" and continue the rest of the lines.

The pictures in this chapter come from a map of DunneFlow itself, built that way: an older
checkout from before a fix for Windows, sealed, then today's tree.

```bash
# 1. analyse the older tree
uv run dunneflow analyze ~/code/dunneflow-before-windows/src/dunneflow --name dunneflow

# 2. seal it, with a name you will recognise
uv run dunneflow revisions output/dunneflow \
    --seal --label "DunneFlow at 1017ef4 - before the Windows fix"

# 3. analyse the newer tree into the same program
uv run dunneflow analyze ~/code/DunneFlow/src/dunneflow --name dunneflow
```

```
sealed 2026-10-02T19:59:47Z as FOR_COMPARISON — “DunneFlow at 1017ef4 - before the Windows fix”
the next `analyze` opens a fresh working revision beside it
```

Seal as many as you like. The map behind these pages holds a third, older still, from
before DunneFlow's analysis was split into parts. Check what a program holds at any time:

```bash
uv run dunneflow revisions output/dunneflow
```

```
revision               state            captured                files  label
2026-10-02T19:59:52Z   WORKING          2026-10-02T19:59:52Z      142
2026-10-02T19:59:47Z   FOR_COMPARISON   2026-10-02T19:59:47Z      141  DunneFlow at 1017ef4 - before the Windows fix
2026-10-02T19:59:41Z   FOR_COMPARISON   2026-10-02T19:59:41Z      141  DunneFlow at 0804aa7 - before parts
```

**Sealing is a command, not a button**, and the dashboard says so where you would look for
it. If you analyse into a program that already has a working snapshot, the dialog warns
you plainly: *"Analysing into it rewrites its working snapshot rather than adding a second
point in time — seal it first if you want to keep both."*

## Choosing the pair

With two or more comparable versions, the **version menu** appears in the top bar. One
control, and its options are the **pairs**:

```
reading DunneFlow
    DunneFlow · on its own
    DunneFlow ← dunneflow-before-windows · DunneFlow at 1017ef4 - before the Windows fix
    DunneFlow ← dunneflow-before-parts · DunneFlow at 0804aa7 - before parts
reading dunneflow-before-windows · DunneFlow at 1017ef4 - before the Windows fix
    dunneflow-before-windows · … · on its own
    dunneflow-before-windows · … ← DunneFlow
    dunneflow-before-windows · … ← dunneflow-before-parts · …
reading dunneflow-before-parts · DunneFlow at 0804aa7 - before parts
    …
```

Each option names both ends, because a closed menu shows only the option and not the group
it sits in: closed, it reads *DunneFlow ← dunneflow-bef…*. The list itself is drawn by your
operating system, which is why there is no picture of it here.

Both ends are real. The **reading** end decides what the whole screen shows, including
the cover, the routine list, the code browser, the glossary. The other end is what it is held
against. Your choice survives a page reload and a restart of the server, because it is the
server's state and not the browser's.

**A program with two versions opens comparing them**, rather than waiting to be asked.
The routine list marks itself and the code overlay draws on your first visit. The menu
names that pair, and **on its own** is the option that turns it off. Whichever you pick is
remembered.

## Which is newer?

**DunneFlow does not know, and does not pretend to.** The only instant it records is when
*it* read the bytes. A tree handed to you on a memory stick has no history at all and
that is precisely the case this view exists to serve.

So the bands are named by **where a thing is**, never by what happened to it, and the
interpretation is yours. The strip carries it as a button you can flip:

> BASE **DunneFlow** `0.2.0` compared with **dunneflow-before-windows** · DunneFlow at
> 1017ef4 - before the Windows fix `0.2.0` [ assuming the compared version is newer ]
> captured: compared first

Three things in that line:

- **The assumption**, as a button. Click it to flip. Where the two versions state numbers
  that can be ordered, it says so — *"the compared version is newer — from their
  versions"*. Where they cannot, as here (both are `0.2.0`), it says *"assuming the
  compared version is newer"*: a default rather than a reading. Hover it and the reason is
  given in full — *"Neither version says enough to compare, so this is the default
  assumption. It decides whether what only the base has reads as deleted or as added."*
  Once you have clicked it, it says so, and the versions no longer decide:

  ![The version strip for the before-parts pair: "BASE DunneFlow 0.2.0 compared with dunneflow-before-parts · DunneFlow at 0804aa7 - before parts 0.1.0", then the button "you chose: the compared version is older", then "captured: compared first"](images/14-assumption.png)
- **captured: compared first** Which of the two DunneFlow read first. A fact about the
  capture, not about the code, which is why it sits beside the assumption rather than
  deciding it.
- Changing the assumption costs no re-query. It only relabels; the facts underneath do not
  move.

## What differs

The **Changes** group in the navigator, or **The whole comparison** inside it.

![The "What differs" page for the before-parts pair: "base 2026-10-02T19:59:52Z · compared with 2026-10-02T19:59:41Z — DunneFlow at 0804aa7 - before parts · you chose: the compared version is older · compared in 3,988 ms on the connection already open here", then eight cards — 34 added, 3 deleted, 88 behave differently, 0 explained differently, 37 edited only, 1 module explained differently, 6 structures declaring differently, 1 structure explained differently — followed by "1,550 routines in the base, 1,519 in the compared. A rename reads as one of each — nothing in the source says the two are the same thing.", "207 structures in the base, 207 in the compared", and the start of the constants: +4, beginning cli.STEP_BEFORE and extractors.docs.markdown.IMAGE_ONLY, and ◈13, beginning extractors.cpp.extract.RESIDUE. The navigator's CHANGES group reads 133, with The whole comparison open and its bands listed beneath](images/14-what-differs.jpg)

### The bands

These are a partition, exclusive, so every routine that differs is in exactly one of them.

| | |
|---|---|
| **only in base** / **only in compared** | Presence, by identity. A routine is identified by its qualified name, never by its position, so it keeps its identity when anything above it moves. **A rename reads as one of each**, which is honest: nothing in the source says the two are the same thing. |
| **behave differently** | The same routine in both, and something it *does* differs — what it calls, what it touches, what it takes or returns. This is the band worth your time. |
| **edited only** | The body differs and nothing it does does. **The largest band in ordinary work and the least interesting**, and saying so is the point: a routine whose internal computation changed is exactly what DunneFlow exists not to report. |
| **explained only** | Nothing about the routine differs except the prose above it. It is a band of its own because a rewritten comment sits *outside* the routine's body and would otherwise be in no band at all — and a routine already in one of the bands above carries a tag instead of a second row. |

### The explanations

Beside the bands, never deciding one:

- **explained differently** A rewritten comment or docstring. Where the routine is
  already in a band it is a **tag on that row**; where it is not, it is the *explained
  only* band above. A leading comment sits *above* the `def` and so outside the routine's
  body, which means a rewritten comment would otherwise vanish from the comparison
  entirely.
- **modules explained differently** A rewritten module docstring. That belongs to a
  *file*, not to a routine, so it is its own lane and its rows carry a path.

Prose is compared **joined and collapsed**, not as written. On a real codebase 86% of
comment lines live in a run of two or more, so a re-wrap that changes no word reports 1,561
false differences as written and none once joined.

Docstrings are canonicalised slightly differently: paragraphs are **kept**. Merging them
would destroy the separation between a summary line and the rest, which is exactly the
change you would want reported.

Every card says what it counts, and the bands add up: of the 1,550 routines in this base,
34 are added, 88 behave differently, 37 are edited only, and 1,391 are unchanged — the
same sentence the ROUTINES group prints, which adds that the 3 deleted are *in
2026-10-02 19:59:41 only, so not listed here*. A list of the base cannot hold a routine the
base does not have.

### Below the bands

Ways in that appeared or vanished, named files, and constants with each listed by name, and
each clickable. Here, four constants arrived, `cli.STEP_BEFORE` among them, and thirteen
say something different, `schema.SCHEMA_VERSION` and `plugins.typescript.src.main.VERSION`
among them; the second list shows six and folds the other seven behind *7 more ▸*.

## Reading the difference in the views

With a pair set, the marks appear where you are already reading.

**The routine list and the table** mark each row with what the comparison found about it.
Free, drawn from an answer already held.

**The code browser** draws it over the source:

![The code browser on cli.py, against the before-the-Windows-fix version: "cli · 2,132 lines · 47 definitions · 213 marks", then "Against 2026-10-02 19:59:47: 71 lines added and 15 lines deleted. The deleted lines are shown where they belong, with their own numbers — they are not in the file you are reading." then "8 routines here the comparison has something to say about": build_parser "behaves differently — call_args", cmd_analyze "— call_args, calls, comments", cmd_impact and cmd_mirror "— boundaries, call_args, calls", cmd_naming "— call_args, docstring", cmd_touches "— boundaries, call_args, calls, comments", and two added, _gap and _settled](images/14-code-overlay.jpg)

The lines are the cheap half. The list under them is the half nothing else gives you:
*`cmd_naming` behaves differently — call_args, docstring*. That is two different claims
about one routine, and each is a fact you can go and look at.

Note what it says about deleted lines: they are *shown where they belong, with their own
numbers — they are not in the file you are reading*. You are reading one version, with the
other drawn over it, not a merged view of both.

**The stack** can colour by what changed, rather than by what things are — the **Colour by**
control in the graph legend, which offers `what changed` only when there is a comparison
to draw.

**The anomaly worklist** can say which findings the other version also has, and whose
count, severity or confidence moved. That one is the expensive overlay: on a 628-file program,
1.3 to 4.1 seconds the first time, because it means running thirteen detectors against a graph this process
has never opened.

## What is never done to your snapshots

The two graphs are joined read-only for the length of a query. **Neither snapshot is
copied, moved or rewritten to be compared**, and a sealed snapshot is never re-analysed in
place. That is what makes a sealed snapshot worth having: it is still readable after its
source tree is gone.

---

Next: [15. When it refuses](15-when-it-refuses.md)
