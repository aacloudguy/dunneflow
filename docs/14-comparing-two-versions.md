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
sealed 2026-11-13T03:56:47Z as FOR_COMPARISON — “DunneFlow at 1017ef4 - before the Windows fix”
the next `analyze` opens a fresh working revision beside it
```

Seal as many as you like. The map behind these pages holds a third, older still, from
before DunneFlow's analysis was split into parts. Check what a program holds at any time:

```bash
uv run dunneflow revisions output/dunneflow
```

```
revision               state            captured                files  label
2026-11-13T03:56:51Z   WORKING          2026-11-13T03:56:51Z      181
2026-11-13T03:56:47Z   FOR_COMPARISON   2026-11-13T03:56:47Z      141  DunneFlow at 1017ef4 - before the Windows fix
2026-11-13T03:56:43Z   FOR_COMPARISON   2026-11-13T03:56:43Z      141  DunneFlow at 0804aa7 - before parts
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

**DunneFlow reads it where the two programs say, and does not pretend to where they do
not.** The only instant it records is when *it* read the bytes, and that is a fact about
the capture. A tree handed to you on a memory stick has no history at all and that is
precisely the case this view exists to serve. What a program can state is its own version,
and where both ends state one and the two can be ordered, that is what decides.

So the bands are named by **where a thing is**, never by what happened to it, and the
interpretation laid over them says where it came from. The strip carries it:

> BASE **DunneFlow** `0.3.0` compared with **dunneflow-before-windows** · DunneFlow at
> 1017ef4 - before the Windows fix `0.2.0` [ the compared version is older — from their
> versions ] captured: compared first

Three things in that line:

- **The direction, and its basis**, as a button. Where the two versions state numbers
  that can be ordered, as here (`0.3.0` against `0.2.0`), it says so — *"the compared
  version is older — from their versions"*: a reading rather than a default. Hover it and
  the reason is given in full — *"Read from the two versions each program states about
  itself. It decides whether what only the base has reads as deleted or as added."* Where
  they cannot be ordered — one end states none, or both state the same one — it says
  *"assuming the compared version is newer"*, and the hover says that *"Neither version
  says enough to compare, so this is the default assumption."* Clicking the button puts
  your own choice in place of either, it then begins *"you chose:"*, and a third click
  hands the decision back to the versions. The other pair in this map reads the same way,
  `0.3.0` against `0.1.0`:

  ![The version strip for the before-parts pair: "BASE DunneFlow 0.3.0 compared with dunneflow-before-parts · DunneFlow at 0804aa7 - before parts 0.1.0", then the button "the compared version is older — from their versions", then "captured: compared first"](images/14-assumption.png)
- **captured: compared first** Which of the two DunneFlow read first. A fact about the
  capture, not about the code, which is why it sits beside the direction rather than
  deciding it.
- Changing the direction costs no re-query. It only relabels; the facts underneath do not
  move.

## What differs

The **Changes** group in the navigator, or **The whole comparison** inside it.

![The "What differs" page for the before-parts pair: "base 2026-11-13T03:56:51Z · compared with 2026-11-13T03:56:43Z — DunneFlow at 0804aa7 - before parts · the compared version is older — from their versions · compared in 521 ms on the connection already open here", then ten cards — 1,158 added, 125 deleted, 238 behave differently, 2 explained differently, 186 edited only, 41 modules explained differently, 318 structures only in the base, 10 structures only in the compared, 29 structures declaring differently, 9 structures explained differently — followed by "2,552 routines in the base, 1,519 in the compared. A rename reads as one of each — nothing in the source says the two are the same thing." and "515 structures in the base, 207 in the compared", where the picture ends. The navigator's CHANGES group reads 1,930, with The whole comparison open and its bands listed beneath](images/14-what-differs.jpg)

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

Every card says what it counts, and the bands add up: of the 2,552 routines in this base,
1,158 are added, 238 behave differently, 2 are explained differently, 186 are edited only,
and 968 are unchanged — the same sentence the ROUTINES group prints, which adds that the
125 deleted are *in 2026-11-13 03:56:43 only, so not listed here*. A list of the base cannot hold a routine the
base does not have.

### Below the bands

Tables and ways in that appeared or vanished, named files, and constants with each listed
by name, and each clickable. Here, 329 constants arrived, `cli.STEP_BEFORE` among them, 41
are gone, and forty say something different, `schema.SCHEMA_VERSION` and
`plugins.typescript.src.main.VERSION` among them; each list shows six and folds the rest
behind a count, so the last of the three ends *34 more ▸*.

## Reading the difference in the views

With a pair set, the marks appear where you are already reading.

**The routine list and the table** mark each row with what the comparison found about it.
Free, drawn from an answer already held.

**The code browser** draws it over the source:

![The code browser on cli.py, against the before-the-Windows-fix version: "cli · 2,559 lines · 65 definitions · 257 marks", then "Against 2026-11-13 03:56:47: 559 lines added and 76 lines deleted. The deleted lines are shown where they belong, with their own numbers — they are not in the file you are reading." then "42 routines here the comparison has something to say about", the first twenty of them in the picture: __init__ "behaves differently — calls, comments", detail "— call_args, params, docstring", build_parser "— call_args, calls, comments", cmd_analyze "— boundaries, call_args, calls, comments, docstring", cmd_naming "— boundaries, call_args, calls, docstring", cmd_serve "— call_args", cmd_touches "— boundaries, call_args, calls, comments" and eleven more that behave differently, then two added, cpu_phases and phases](images/14-code-overlay.jpg)

The lines are the cheap half. The list under them is the half nothing else gives you:
*`cmd_naming` behaves differently — boundaries, call_args, calls, docstring*. That is four
different claims about one routine, and each is a fact you can go and look at.

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
