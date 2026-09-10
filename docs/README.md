# Using DunneFlow

DunneFlow maps what moves through a program: where it starts, what it runs, what it
touches, and why.

It is built for someone orienting in a codebase they did not write — someone who reads
code and does not necessarily write it. You point it at a directory of source, it reads
the code and the documentation beside it, and it gives you a map you can walk around in.

Nothing leaves your machine. No part of the analysis calls a model or opens a network
connection.

## Start here

If you have never run it, read these four in order. About twenty minutes, and at the end
you will have a map of a real codebase open in front of you.

| | |
|---|---|
| [1. Installing](01-installing.md) | The application, or the checkout. Where maps are kept, and how to move them. |
| [2. Getting the code](02-getting-the-code.md) | git, Perforce, Lore, a zip on a memory stick. DunneFlow never asks a version control system anything — you bring it a directory. |
| [3. The start page](03-the-start-page.md) | The page you land on when nothing is open. |
| [4. Your first map](04-your-first-map.md) | Reading a tree, watching it run, stopping it, and what you get. |

## The six views

The middle of the screen is one selection read six ways. They are not six destinations —
pick a routine in any of them and the other five are already showing it.

| | |
|---|---|
| [5. The shell](05-the-shell.md) | The three panes, the top bar, and how a selection travels. Read this before the five below. |
| [6. Graph](06-graph.md) | The whole program as a stack of plates. What is here, and what connects to what. |
| [7. Table](07-table.md) | Every routine as a row, sortable, with what its author said about it. |
| [8. Document](08-document.md) | Two lanes: the eight documents DunneFlow writes, and every document your program already carries. |
| [9. Code](09-code.md) | The source as it was measured, with every resolved call clickable. |
| [10. Diagram](10-diagram.md) | One compartment drawn as a diagram, and one box inside it. |
| [11. Shape](11-shape.md) | What one routine *does* — its loops, decisions and refusals, nested as written. |

## Working with it

| | |
|---|---|
| [12. Chasing rabbits](12-chasing-rabbits.md) | Threads to pull, Back, Forward, Clear, and ◇ Keep this. How to follow a thought without losing the one you were on. |
| [13. Settings](13-settings.md) | Every setting, what it does, and what it costs. |
| [14. Comparing two versions](14-comparing-two-versions.md) | Two points in time, held against each other — and the half a text diff cannot give you. |

## When something goes wrong

| | |
|---|---|
| [15. When it refuses](15-when-it-refuses.md) | Every refusal DunneFlow can give you, in plain words, and what to do about each. |
| [16. The command line](16-the-command-line.md) | All twelve commands, for when you want an answer without opening a browser. |

## Two promises the tool makes

These are worth knowing before you trust anything on the screen.

**Every finding states what would make it a false alarm.** An anomaly carries a severity
(what it would mean for your program), a confidence (how sure DunneFlow is), and a blind
spot (what would make it wrong). Those are three different questions and DunneFlow never
blurs them.

**Every reported meaning carries its provenance, and the provenance opens.** A quoted
definition proves itself with a file and a line you can click through to. A measured
claim ships the query that counted it. Nothing on screen is a number you have to take on
faith.
