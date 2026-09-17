# 2. The cover

The map opens on the cover. It is the answer to *what is this program*, in three panels,
before you have asked anything specific.

![The DunneFlow dashboard showing the dunneflow map. The heading reads "dunneflow — 78 files · 34,291 lines · 925 routines · analysed 2026-09-15 22:14 UTC". WHERE TO START ranks main at 393, serve at 111, run at 8, _Handler.do_GET at 3 and _Handler.do_POST at 2, each with a bar. WHAT IT TOUCHES totals 487: DATABASE 272, FILE 142, STDIO 56, PROCESS 6, ENV 5, CRYPTO 3, NETWORK 3. WHAT LOOKS WRONG shows Broken 0, Suspect 25, Informational 15. The navigator on the left lists WAYS IN 5 and ROUTINES 925 across 19 packages](images/02-the-cover.jpg)

## The heading

> **dunneflow** 78 files · 34,291 lines · 925 routines · analysed 2026-09-15 22:14 UTC

The date is not decoration, it's a label. A map is a reading of a tree at a moment, and it
keeps saying which moment for as long as it exists. Later, when the source has moved on, 
this line is how you know what you are looking at.

## Where to start

> ranked by how much of the program each one commands

Five ways in, and `main` commands 393 of the 925 routines. `serve` commands 111. Then the
drop is steep: 8, 3, 2.

That shape is the useful part. It says DunneFlow is a command-line program with one large
front door and a web server hanging off the side of it — which is true, and which you now
know without having opened a file. DunneFlow is about the flow of information, in this
case it is the flow of information into the program.

Each entry says how it was found. `main` carries **MAIN** and **GUESSED**: the tag is the
kind of way in, and *guessed* is DunneFlow telling you it inferred this from a conventional
name at module level rather than reading a declaration that said so. The tool is
persistently willing to tell you how confident it is, and this is the first place you see
it.

Notice that code editors do not guess, but that DunneFlow will do so. DunneFlow is not
the same kind of tool that exists already, it is intended to be different. It follows the
rabbits wherever they may lead, and sometimes guessing can help make the intellectual
leap needed to connect two concepts that have no obvious link. That sort of connection
can help to create that insight moment and forms a foundation on which to build lasting knowledge.

**Two of the five are HTTP routes** — `_Handler.do_GET` and `_Handler.do_POST`. They
command 3 and 2 routines respectively, which is a good demonstration of what "commands"
means: those two dispatch to sixty-odd routes, but they *reach* almost nothing directly.
Reach is measured, not asserted.

## What it touches

> 487

This is the panel that says what kind of program you have, and it is the one to read first
on a codebase you have never before seen. If the application was written by an AI, it is
possible that no one has ever seen the source code.

| | | |
|---|---|---|
| DATABASE | 272 | It is mostly a database program. |
| FILE | 142 | It reads and writes a lot of files. |
| STDIO | 56 | It talks to a terminal. |
| PROCESS | 6 | It starts other programs — six places. |
| ENV | 5 | It reads five things from the environment. |
| CRYPTO | 3 | Hashing, here; it is how the caches are keyed. |
| NETWORK | 3 | Three. For a tool with a web dashboard. |

That last row is the interesting one and it is worth dwelling on, because it is the 
reason for this panel. **Three network touches, in a program that serves a
dashboard.** Click it and you get all three:

| | |
|---|---|
| `_free_port` | `serve.py:3419` and `:3425` — binding a socket to find a port that is free |
| `already_serving` | `serve.py:3400` — asking `api/programs` whether a server is already up |

All three are localhost, and there is no fourth. DunneFlow's claim that nothing leaves your
machine is not a promise in a README here; it is a number on the cover of its own map, with
the three rows under it. If a model were being called, or a package index consulted, or a
crash reported home, this row would say so — and it is the shortest row on the panel.

## What looks wrong

> every finding states its blind spot

| | |
|---|---|
| Broken | 0 |
| Suspect | 25 |
| Informational | 15 |

And underneath, the sentence that governs the entire feature:

> Severity says what it would mean for the program. Confidence says how sure DunneFlow is.
> They are different questions.

Blurring those two is the standard failure of many tools that report problems, and it is
why most of them get ignored. *This is probably fine but would be catastrophic* and *this
is definitely happening and barely matters* are not the same row, and DunneFlow will not
let them be.

Every finding also carries a **blind spot** — what would make it a false alarm. That rule
exists because on the first run against a live codebase, six confident findings in a row
turned out to be defects in DunneFlow rather than in the program it was reading. Yes, those
problems were fixed, so anything that is wrong with DunneFlow now is a new problem.

## The navigator

Down the left: **WAYS IN 5**, **ROUTINES 925 in 19 packages**, and below them CHANGES,
CODE, EXPLORE, PACKAGES, BOUNDARIES, DATABASE, STRUCTURES, VOCABULARY, ALGORITHMS,
ANOMALIES.

The package list is ranked by size — `web` 337, `resolve` 125, `render` 100, `extractors`
89 — and the tail is folded into `·small`: `macapp` 4, `canonical` 3, `standards` 2. Folded,
and **still listed**, with their counts. Nothing is dropped for being small; it is just
moved out of the way of the things that are not.

## The strip above it

> BASE **DunneFlow 0.1.0** compared with **DunneFlow-before-Linux** · DunneFlow at 875499c
> — before Linux

This map holds two readings of DunneFlow: the current source, and a snapshot taken from the
commit before Linux support landed. That is [chapter 8](08-two-versions.md)'s subject and you can
ignore it for now — but it is worth knowing it is there, because several panels behave
differently once a comparison exists, and they will tell you so rather than changing
quietly.

---

Next: [3. One selection, six ways](03-one-selection-six-ways.md)
