# DunneFlow, read by DunneFlow

A walk through the tool, using the tool on itself.

The [reference guide](../README.md) answers *what does this control do*. This answers
*show me*. Every screenshot here is DunneFlow reading its own source, so every page you
see is a real page about a real program rather than a mock-up — and the figures are that
one session's, taken on a stated day. See [a note on the
numbers](#a-note-on-the-numbers) before you compare them with your own.

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
it at — [Run from source](../../README.md#run-from-source) in the project's README, which
is a `git clone` and `uv sync`.

Then, from the checkout:

```bash
uv run dunneflow analyze src/dunneflow --name dunneflow
uv run dunneflow serve output/dunneflow
```

Under a quarter of a minute. DunneFlow's own tree is in six languages now, and five of them
are read by that language's own toolchain — Node.js, Go, Rust, a JDK and clang. **If you
lack one**, DunneFlow will say so and decline to read those files: with no Node.js, say, add
`--without typescript` and the rest of the tour works, with the map saying it was told to
skip the eleven TypeScript files and your figures smaller than the ones printed here. See
[installing](../01-installing.md#which-languages-it-reads-and-the-one-thing-you-may-have-to-install).

Chapter 1 does this the other way, through the dialog rather than the terminal, and
explains what it is doing on the way.

## The chapters

| | |
|---|---|
| [1. Pointing it at itself](01-pointing-it-at-itself.md) | Reading a tree, and the refusal you meet first. |
| [2. The cover](02-the-cover.md) | What it found: where to start, what it touches, what looks wrong. |
| [3. One selection, six ways](03-one-selection-six-ways.md) | The three panes, the search that answers in every group, and a selection that travels. |
| [4. The stack](04-the-stack.md) | 4,410 things on 30 plates, and why the third axis is there. |
| [5. Table and Code](05-table-and-code.md) | Every routine as a row with what its author said; then the source as measured. |
| [6. Document](06-document.md) | Two lanes — the documents it writes, and the ones your program already had. |
| [7. Diagram](07-diagram.md) | One compartment, forty-six boxes, and **frame it**. |
| [8. Two versions](08-two-versions.md) | Held against each other — and the half a text diff cannot give you. |
| [9. What looks wrong](09-what-looks-wrong.md) | Thirty-eight findings, three buttons, and how to tell the program's mistakes from the tool's. |
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

**This is a recorded session, and it is dated.** Every figure quoted in these chapters came
off the screen or out of a terminal, and all of them come from **one map**: DunneFlow
reading its own source from a clean clone at `1ba37b3` on **13 November 2026**, by the
build of that same commit. The map holds three readings of DunneFlow — the clone itself,
read at 03:56:51 UTC, and two snapshots sealed from earlier commits and read seconds before
it: `1017ef4`, *before the Windows fix* (03:56:47), which is the one most chapters compare
against, and `0804aa7`, *before parts* (03:56:43). The screenshots were taken the next day,
by that source with five small repairs to the dashboard that taking them turned up; none of
them touches what the map holds. Yours will differ the moment the source does — that is the
fun of the tool, not a flaw in the tutorial — and where a number matters the chapter says
how to get it yourself, several of them handing you the exact query.

That day the tree was **181 files, 81,283 lines and 2,552 routines**, in **six
languages**: 128 Python files, 12 Rust, 11 each of C++, Java and TypeScript, and 8 Go —
everything that is not Python being a reader, the program that teaches DunneFlow one more
language, written in the language it reads. All six are read, so a figure that counts
routines or spellings counts all of them. How that map was built, command by command, is
recorded under *the screenshot map* in the repository's `GROUND-TRUTH.md`, so it can be
built again.

A control that is in a screenshot is in the product, and the reference guide is the half
of this that is not dated.

---

Back to [Using DunneFlow](../README.md).
