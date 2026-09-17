# DunneFlow, read by DunneFlow

A walk through the tool, using the tool on itself.

The [reference guide](../README.md) answers *what does this control do*. This answers
*show me*. Every screenshot here is DunneFlow reading its own source — 78 files, 925
routines — so every number on every page is one you can reproduce by pointing your own
copy at the checkout.

DunneFlow is not a code editor or code browser. It looks at application source code
in a different way. We take apart that source code and watch how information *flows*
through it. We create diagrams and tables and lists and let you hunt rabbits.

See something interesting? Chase after it. Click Keep and the treasure is yours until you
decide you are done with it.

**You do not need to read the code.** Nothing here asks you to. Where a chapter points at
a routine it is because the *feature* is easier to see with a specimen under it, and the
specimen is described in words. However, if you do decide that reading the code would
be helpful in understanding, there are a few places where we provide that service.

## Before you start

You need DunneFlow [installed](../01-installing.md) and a checkout of its source to point
it at — the [checkout section](../01-installing.md#the-checkout) of that chapter, which is
a `git clone` and `uv sync`.

Then, from the checkout:

```bash
uv run dunneflow analyze src/dunneflow --name dunneflow
uv run dunneflow serve output/dunneflow
```

This should not take long, about twelve seconds. Chapter 1 does this the other way,
through the dialog rather than the terminal, and explains what it is doing on the way.

## The chapters

| | |
|---|---|
| [1. Pointing it at itself](01-pointing-it-at-itself.md) | Reading a tree, and the refusal you meet first. |
| [2. The cover](02-the-cover.md) | What it found: where to start, what it touches, what looks wrong. |
| [3. One selection, six ways](03-one-selection-six-ways.md) | The three panes, the search that answers in every group, and a selection that travels. |
| [4. The stack](04-the-stack.md) | 1,773 things on 22 plates, and why the third axis is there. |
| [5. Table and Code](05-table-and-code.md) | Every routine as a row with what its author said; then the source as measured. |
| [6. Document](06-document.md) | Two lanes — the documents it writes, and the ones your program already had. |
| [7. Diagram](07-diagram.md) | One compartment, thirty-one boxes, and **frame it**. |
| [8. Two versions](08-two-versions.md) | Held against each other — and the half a text diff cannot give you. |
| [9. What looks wrong](09-what-looks-wrong.md) | Forty findings, three buttons, and the four this tool got wrong about itself. |
| [10. Words and names](10-words-and-names.md) | What its words mean, how its names are spelled, and whether anybody wrote that down. |
| [11. Worth a look](11-worth-a-look.md) | Twelve measurements, each with its middle, and the query that returned it. |
| [12. Threads and the trail](12-threads-and-the-trail.md) | Following a thought without losing the one you were on. |
| [13. The command line](13-the-command-line.md) | The same questions, with no browser. |

Thirteen chapters, about ninety minutes. Chapter 8 is the one to read if you only read one:
it is the tool answering a question nobody told it the answer to.

Chapters 1 to 8 are the tour of the views; 9 to 13 are the four surfaces that sit beside
them. They show what looks wrong, what the words mean, what is unusual, and what is worth a detour.
You can also ask the same questions from a terminal. Every chapter stands on its own, so if
you came here for one of those, start there.

The [reference guide](../README.md) is the other half: this shows you a feature working on
a real program, that one tells you what every control does.

## A note on the numbers

Every figure quoted in these chapters came off the screen or out of a terminal, and all of
them come from **one map**: DunneFlow reading its own source at `1e76c51`, held against a
snapshot of `875499c`. Yours will differ the moment the source does. That is the fun of
the tool, not a flaw in the tutorial. Dive into your own investigation and enjoy the
ride. Where a number matters, the chapter says how to
get it yourself, and several of them hand you the exact query.

---

Back to [Using DunneFlow](../README.md).
