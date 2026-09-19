# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches,
and why.

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back
out. **What moves is the subject. Internal computation is not.**

DunneFlow reads a source tree and the documentation beside it and gives you a map you can
walk around in — entrypoints, flows, routines, boundaries, database use, network and
messaging, governance, a glossary, a naming standard, and a list of anomalies. It is built
for someone orienting in a codebase they did not write.

Deliberately *not* reported: local variables, arithmetic, and private helpers that neither
touch a boundary nor sit on a path to one. Leaving those out is most of what makes the
output readable.

Control flow is reported only where something **moves** inside it: a loop that increments a
counter is the internal computation nobody asked for, a loop that issues one network call
per item is a *rate*, and a rate is flow.

The goal is **comprehension, not documentation**.

**New here? [Read the guide.](docs/README.md)** It starts at installing and ends at holding
two versions of a program against each other.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run dunneflow serve
```

That opens the start page in a browser, which is where you make your first map.

There is also a double-clickable application that does the same thing with no Python to
install, on all three platforms: **macOS**, signed and notarised, built for Apple silicon
and Intel and asking the system for no permissions at all; **Windows**, as a zip holding
`DunneFlow.exe` and a `dunneflow-cli.exe` beside it for the command line; and **Linux**, as
a tarball that installs into `~/.local` — binary, menu entry and icons — without needing
root. See [docs/01-installing.md](docs/01-installing.md).

## The dashboard

`dunneflow serve` is the main way in. Three panes — navigator, centre, inspector — and the
centre is **one selection read six ways**, not six destinations:

| | |
|---|---|
| [Graph](docs/06-graph.md) | the whole program as a stack of plates |
| [Table](docs/07-table.md) | every routine as a sortable row |
| [Document](docs/08-document.md) | the eight documents DunneFlow writes, and every document your program carries |
| [Code](docs/09-code.md) | the source as measured, with every resolved call clickable |
| [Diagram](docs/10-diagram.md) | one compartment, drawn |
| [Shape](docs/11-shape.md) | what one routine *does* — its loops, decisions and refusals |

Around them: a [trail with Back, Forward and a shelf](docs/12-chasing-rabbits.md) so a
detour costs you nothing, and a [comparison](docs/14-comparing-two-versions.md) between two
points in time that says what a text diff cannot — which routines *behave* differently, not
which of their lines moved.

Vanilla JavaScript and deck.gl over `http.server`. No framework, no Node at runtime or
build.

## Command line

```bash
uv run dunneflow analyze   <path> --name <program>   # extract, resolve, write the map
uv run dunneflow serve     [dir]                     # the dashboard
uv run dunneflow touches   <path> --routine <name>   # what does this reach?
uv run dunneflow impact    <path> --routine <name>   # what breaks if I change it?
uv run dunneflow check     <path>                    # anomalies; non-zero exit on BROKEN
uv run dunneflow glossary  <path>                    # what its words mean, and who says so
uv run dunneflow naming    <path>                    # the naming standard: derived, and quoted
uv run dunneflow mirror    <path>                    # words the docs define that the code never uses
uv run dunneflow query     <path> --sql "..."        # ask the graph directly
uv run dunneflow revisions <dir> [--seal]            # what snapshots this holds; keep the current one
uv run dunneflow render    <dir>                     # a snapshot's Markdown, from the graph it has
uv run dunneflow migrate   <dir>                     # stored paths: absolute -> relative
```

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`), and `--standards <dir>` admits somebody
else's naming standard without absorbing it. It is incremental: unchanged files are not
re-parsed.

Point it at itself for a worked example:

```bash
uv run dunneflow analyze src --name dunneflow
```

Full reference: [docs/16-the-command-line.md](docs/16-the-command-line.md).

## What a program directory contains about your machine

A program directory is built to be **handed over** — copied to a colleague, kept after
the source tree has moved on, read on a machine that has never held the code. So what it
records about where it came from is a deliberate, short list.

**Not recorded:** the path to the analysed tree. Every stored path is relative, and the
root is never written down — it is one machine's directory layout, it is wrong the moment
anything moves, and it is wrong on every machine a copy reaches. Nothing at read time
needs it: file bodies are held by content hash, never fetched by opening a path.

**Recorded:** the **leaf** of the directory each version was read from — `society-2026-08-26`,
not the path that led to it. Two versions of one program are two directories, so the leaf
is what a reader recognises them by; a capture instant only says when we read the bytes.

**Recorded:** the version the program **states about itself**, if it states one — from
`pyproject.toml [project] version`, or a module-scope `__version__`, each with the file
that proves it. Where the source says nothing, a version may be guessed from the
directory's own name (`app-1.2.3`, `society-2026-08-26`) and is then marked as inferred
wherever it appears. DunneFlow never asks a version control system anything.

## How it works

```
source ──► extract ──► graph.db (SQLite) ──► resolve ──► render
           per file,    the one source                   Markdown + Mermaid
           parallel,     of truth                        ▲
           hash-cached                                   │
docs   ──► extract ──► docs.db  (SQLite) ──────────ATTACH┘
           per file,    a parallel store, never
           parallel,    the same one
           stat-gated
```

SQLite is the spine, not an export format — nothing holds the whole program in memory,
and reachability is recursive SQL over indexed edges.

**Four languages, and each is read by whatever understands it best.** Python is stdlib
`ast` and `tokenize`. TypeScript is read by TypeScript's own compiler, out of process, so a
name it resolves is one *it* resolved. C++ and Kotlin are read syntactically, in process,
for two different reasons: most large C++ trees cannot tell a compiler how they are built
without being built first, and asking Kotlin's compiler would put a Java runtime inside a
bundle whose whole dependency list is `pyyaml`. So a C++ or Kotlin map states what a program
touches and does not claim to know where a call goes — and says so with a count rather than
leaving it to be noticed. Documents are scanned by hand. No third-party parser in any of it.

Teaching the tool a new framework is normally a config edit in `detectors/*.yaml`,
not a code change.

## Two disciplines

**Every finding states what would make it a false alarm.** Anomalies carry a severity
(what it would mean for the program), a confidence (how sure the tool is), and a blind
spot. They are different questions and are never blurred.

**Every reported meaning carries its provenance.** A quoted definition proves itself
with a file and line; a measured claim ships the SQL that counted it; an inferred one
cannot prove itself and must say so.

Nothing on the analysis path calls a model or opens a network connection, and a test fails
if anything under `extractors/`, `resolve/` or `canonical/` starts importing an HTTP client
or a model SDK. That is a standing guarantee rather than a current state of affairs.

## Development

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Unit tests on a toy program cannot catch a resolution defect that only appears at
scale, so changes are also verified against a real codebase before being called done.

Engineering rules — the ones learned the hard way, each from a false result on real
code — are indexed in [`CLAUDE.md`](CLAUDE.md) and written out in [`RULES.md`](RULES.md);
the dashboard's are in [`DESIGN-RULES.md`](DESIGN-RULES.md). Current state is in
[`BRIEFING.md`](BRIEFING.md), the full record in [`HANDOFF.md`](HANDOFF.md), and every
measured figure with the budget it was taken against is in
[`PERFORMANCE.md`](PERFORMANCE.md).

## Status

Working and verified at scale, with the dashboard and comparison built. **All three
platforms run it**, each with the full suite, the dashboard and a packaged build green:
macOS signed, notarised and shipping; Windows and Linux built and run at the keyboard.
Every build stamps the same extractor fingerprint, so a map made on one opens on the other
two.

Two platform differences are documented rather than fixed, because neither is DunneFlow's
to fix: on **Windows** a folder chooser asked for by a background process opens behind the
browser, and the Windows build is unsigned, so SmartScreen warns once. On **Linux** the
folder picker needs zenity or kdialog installed, and says so by name if neither is.

*This paragraph ended "TypeScript extraction and cross-process stitching come next" until
2026-09-18, by which point TypeScript had shipped and C++ had joined it.* What is actually
next is in `BACKLOG.md`, which is the one place it is written down.
