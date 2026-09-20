# 16. The command line

Everything the dashboard does, DunneFlow will also do from a terminal, and there are
a few things only the terminal does at all.

CLI tools are useful for automation. It is possible to script operations with DunneFlow
and then use the output in batch operations. It can be used to compare large collections
of applications for example, seeking common issues from a very large corpus of source
code, whether they are versions over time or just an Enterprise repository.

Every example below is `uv run dunneflow …` from a checkout. If you have the application
binary, do not run the `uv run` portion, start with `dunneflow` 
From the installed application, the binary is:

| | |
|---|---|
| macOS | `/Applications/DunneFlow.app/Contents/MacOS/dunneflow` |
| Windows | `dunneflow-cli.exe`, beside `DunneFlow.exe` in the folder you unzipped |
| Linux | `~/.local/bin/dunneflow` once installed — or `dunneflow/dunneflow` in the folder you unpacked |

**On Windows use `dunneflow-cli.exe` and not `DunneFlow.exe`.** They are the same program,
but the one you double-click is built without a console, so from a terminal it does the work
and prints nothing at all. The `-cli` one is the same build with its output attached.

**Linux needs no such pair.** There is one executable and it prints, because a Linux program
is not built for a console or against one, it simply has whatever it was started with.
`./dunneflow/install.sh` puts that name on your `PATH` via `~/.local/bin`.

## The two arguments almost everything takes

```bash
uv run dunneflow <command> <path> --name <program> [--output <dir>]
```

`<path>` is the source tree. `--name` is the program directory the map lives in. Leave it
off and DunneFlow uses the directory's own name, which is why `touches src` looks for
`output/src`. `--output` says where maps go; with no `--output` from a checkout they go to
`output/`, and the command says so on the way past.

Two more that almost everything takes and no example below uses: **`--db`** names a graph
file directly, skipping the program lookup entirely, and **`--limit`** caps how many rows a
report prints.

## Making a map

```bash
uv run dunneflow analyze <path> --name <program>
```

| Flag | |
|---|---|
| `--docs <path>` | where the documentation is (defaults to the package root) |
| `--no-docs` | skip documentation entirely |
| `--recheck-docs` | re-read documents even where nothing has changed |
| `--standards <dir>` | admit somebody else's naming standard, into its own store. Repeatable. |
| `--include-tests` | include test files |
| `--without <lang>` | do not read that language, and say so. Repeatable, refused for a language this build has no reader for, and refused if it would decline them all. For a machine that lacks a language's toolchain — see [installing](01-installing.md#which-languages-it-reads-and-the-one-thing-you-may-have-to-install) |
| `--part-of <tree>` | this is a part of `<tree>`, so judge what to skip and what is a test from there. A directory read on its own is judged by a path that no longer contains the component that hid something — see [when it refuses](15-when-it-refuses.md) |
| `--jobs <n>` | parallel workers |
| `--timings` | print what each phase of the run cost |
| `--no-render` | build the graph, write no Markdown |
| `--no-source` / `--no-doc-source` | do not keep the bodies of the code / the documents |
| `--quiet` | say nothing but failures |
| `--progress-json` | one JSON object per line on stdout instead of the summary |

It is incremental. Unchanged files are not re-parsed, so running it again after an edit
costs a fraction of the first run.

## Asking questions

**What does this reach?**

```bash
uv run dunneflow touches src/dunneflow --name dunneflow --routine cmd_serve
```

```
cli.cmd_serve  (cli.py:1482)
  reaches 118 routines
  DATABASE   SELECT * FROM entrypoints ORDER BY kind, name, …
  ENV        LOCALAPPDATA, XDG_DATA_HOME
  FILE        , *.yaml, -, ., :, …
  NETWORK    f'{url}api/programs', socket.socket
  PROCESS    ['taskkill', '/F', '/T', '/PID', str(proc.pid)]
  STDIO      msg
```

**What breaks if I change it?**

```bash
uv run dunneflow impact src/dunneflow --name dunneflow --routine _emit
```

```
cli._emit  (cli.py:60)
  19 routines depend on this, directly or transitively
  ways in affected (14):
    - analyze [CLI]
    - check [CLI]
    …
```

The second one is the question worth asking before you touch anything: not who calls it,
but **which ways into the program stop working**.

**What do its words mean, and who says so?**

```bash
uv run dunneflow glossary src/dunneflow --name dunneflow
```

```
44 of 155 terms are defined somewhere (28%)

calls  (13 uses)
  Turning call expressions into edges.
  [DECLARED_CODE] resolve/calls.py:1
```

Every definition carries where it came from and the line that proves it.

**What is its naming standard?**

```bash
uv run dunneflow naming src/dunneflow --name dunneflow
```

```
STATED — nothing in this program's documentation states a naming rule

MEASURED — counted against the code
  [B] 790/806  Routines are named in snake_case.  (16 exceptions)
  [B] 383/388  A routine marked private is called only from its own module.  (5 exceptions)
```

**Stated** quotes rules somebody wrote.
**Measured** counts what the code actually does.

**What does the documentation define that the code never uses?**

```bash
uv run dunneflow mirror src/dunneflow --name dunneflow
```

Four bands — Named, Borne, Spoken, Absent — where **Absent** is the strongest
signal of drift the two stores can produce together.

**What looks wrong?**

```bash
uv run dunneflow check src/dunneflow --name dunneflow
```

```
[SUSPECT/PROBABLE] LOST_EDGE: `side` could not be connected: 4 definitions share the name
…
0 broken, 25 suspect, 15 informational
```

Exits non-zero **only on BROKEN**, so it can gate CI without failing your build over
things that merely look odd. `--all` includes informational findings, `--broken-only`
narrows to the ones that fail, `--verbose` prints each finding's detail and its blind spot.

**Ask the graph directly.**

```bash
uv run dunneflow query src/dunneflow --name dunneflow \
  --sql "select kind, count(*) n from boundaries group by kind order by n desc"
```

```
kind | n
DATABASE | 272
FILE | 142
STDIO | 56
```

`--docs` attaches the document store as `docs`, which is what makes the cross-store claims
in the traceability report reproducible. Every query the dashboard offers you under *show
the query* runs here verbatim.

## Managing snapshots

**What does this program hold?**

```bash
uv run dunneflow revisions output/dunneflow
```

```
revision               state            captured                files  label
2026-09-15T22:14:29Z   WORKING          2026-09-15T22:14:29Z       78
2026-09-15T22:14:26Z   FOR_COMPARISON   2026-09-15T22:14:26Z       78  DunneFlow at 875499c - before Linux
```

**Keep the current one**, so the next analysis lands beside it rather than on it:

```bash
uv run dunneflow revisions output/dunneflow --seal --label "a name you will recognise"
```

**Rewrite a map's Markdown** without re-analysing anything:

```bash
uv run dunneflow render output/dunneflow [--revision <rev>]
```

Read-only, from the stores already on disk. This is how a sealed snapshot whose Markdown
was lost gets it back. It is not analysis, so the rule against re-analysing a sealed
snapshot never arises.

**Migrate stored paths** from absolute to relative, in place:

```bash
uv run dunneflow migrate output/dunneflow
```

## Serving

```bash
uv run dunneflow serve [dir] [--revision <rev>] [--port 8787] [--no-open]
```

`serve` takes a program directory, an output root, or **nothing at all** and tells a
program from a root by asking whether the directory holds a map, never by its name.

With nothing open it serves [the start page](03-the-start-page.md). `--revision` chooses
which point in time opens as the base; it defaults to the newest, and you can change it
from the toolbar afterwards.

## Answering an agent

```bash
uv run dunneflow mcp [dir] [--revision <rev>]
```

The same map, answered to a program instead of to you. `mcp` speaks
[MCP](https://modelcontextprotocol.io) on its standard input and output, so a coding agent
can ask the questions the dashboard answers — and make a map of a tree it has just been
pointed at.

It takes the same argument `serve` does, and asks the same question of it: a program
directory or an output root, decided by whether the directory holds a map rather than by
what it is called.

**Twelve tools.** `overview` is the cover and is where to start. `touches`, `impact` and
`routine` are one routine's three questions. `find` searches names and the text of the
source together. `glossary` is what the program's words mean and who says so. `query` runs
SQL against the graph — reads only, and the schema is offered as a resource so an agent can
write its own. `programs` and `open` are the topbar's two controls. `analyze`,
`analysis_status` and `analysis_stop` read a new tree into a map, report on it, and end it.

**It cannot change a map.** Every store it opens is read-only, which since 2026-09-17 means
the SQLite connection itself refuses a write rather than merely intending not to. `query`
refuses anything that is not a read by name, before the connection gets the chance.

Registering it with Claude Code:

```bash
claude mcp add dunneflow -- uv run dunneflow mcp output
```

This repository carries a `.mcp.json` doing the same thing, so a session started here finds
it without being told.

## Cleaning up

A superseded sealed snapshot is dropped **by hand**, deliberately. DunneFlow owns no
command that deletes a snapshot. Remove its `graph@….db` and `docs@….db`, then its rows in
`paths` and `revisions` in both sidecars. Bodies are shared by content and are left alone.

---

Back to [the index](README.md).
