# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches,
and why.

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back
out. **What moves is the subject. Internal computation is not.**

DunneFlow reads a source tree and a documentation corpus and writes a Markdown map —
entrypoints, flows, routines, boundaries, database use, network and messaging,
governance, a glossary, a naming standard, and a list of anomalies. It is built for
someone orienting in a codebase they did not write.

Deliberately *not* reported: local variables, arithmetic, control flow, and private
helpers that neither touch a boundary nor sit on a path to one. Leaving those out is
most of what makes the output readable.

The goal is **comprehension, not documentation**.

## Install

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Use

```bash
uv run dunneflow analyze  <path> --name <program>   # extract, resolve, write the map
uv run dunneflow touches  <path> --routine <name>   # what does this reach?
uv run dunneflow impact   <path> --routine <name>   # what breaks if I change it?
uv run dunneflow check    <path>                    # anomalies; non-zero exit on BROKEN
uv run dunneflow glossary <path>                    # what its words mean, and who says so
uv run dunneflow naming   <path>                    # the naming standard, stated and measured
uv run dunneflow query    <path> --sql "..."        # ask the graph directly
```

`query` takes `--docs` to attach the document store as `docs`, which is what makes the
cross-store claims in the traceability report reproducible.

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`). It is incremental: unchanged files
are not re-parsed. Output lands in `output/<program>/` and is not checked in —
regenerate it rather than committing it.

Point it at itself for a worked example:

```bash
uv run dunneflow analyze src --name dunneflow
```

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
and reachability is recursive SQL over indexed edges. Python extraction uses stdlib
`ast` and `tokenize` only; documents are scanned by hand. No third-party parser.

Teaching the tool a new framework is normally a config edit in `detectors/*.yaml`,
not a code change.

## Two disciplines

**Every finding states what would make it a false alarm.** Anomalies carry a severity
(what it would mean for the program), a confidence (how sure the tool is), and a blind
spot. They are different questions and are never blurred.

**Every reported meaning carries its provenance.** A quoted definition proves itself
with a file and line; a measured claim ships the SQL that counted it; an inferred one
cannot prove itself and must say so.

## Development

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Unit tests on a toy program cannot catch a resolution defect that only appears at
scale, so changes are also verified against a real codebase before being called done.

Engineering rules — the ones learned the hard way, each from a false result on real
code — are in [`CLAUDE.md`](CLAUDE.md). Current state and open questions are in
[`HANDOFF.md`](HANDOFF.md).

## Status

Working and verified at scale. The interactive dashboard is designed but not yet
built; temporal layers, TypeScript extraction, and cross-process stitching come after
it. See `HANDOFF.md`.
