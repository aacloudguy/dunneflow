# 16. The command line

Everything the dashboard does, DunneFlow will also do from a terminal — and a few things
only the terminal does at all.

Every example below is `uv run dunneflow …` from a checkout. From the installed
application, the binary is:

| | |
|---|---|
| macOS | `/Applications/DunneFlow.app/Contents/MacOS/dunneflow` |
| Windows | `dunneflow-cli.exe`, beside `DunneFlow.exe` in the folder you unzipped |

**On Windows use `dunneflow-cli.exe` and not `DunneFlow.exe`.** They are the same program,
but the one you double-click is built without a console, so from a terminal it does the work
and prints nothing at all. The `-cli` one is the same build with its output attached.

## The two arguments almost everything takes

```bash
uv run dunneflow <command> <path> --name <program> [--output <dir>]
```

`<path>` is the source tree. `--name` is the program directory the map lives in — leave it
off and DunneFlow uses the directory's own name, which is why `touches src` looks for
`output/src`. `--output` says where maps go; with no `--output` from a checkout they go to
`output/`.

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
| `--jobs <n>` | parallel workers |
| `--no-render` | build the graph, write no Markdown |
| `--no-source` / `--no-doc-source` | do not keep the bodies of the code / the documents |
| `--quiet` | say nothing but failures |
| `--progress-json` | one JSON object per line on stdout instead of the summary |

It is incremental. Unchanged files are not re-parsed, so running it again after an edit
costs a fraction of the first run.

## Asking questions

**What does this reach?**

```bash
uv run dunneflow touches src --name dunneflow --routine cmd_serve
```

```
dunneflow.cli.cmd_serve  (dunneflow/cli.py:1420)
  reaches 112 routines
  DATABASE   SELECT * FROM entrypoints ORDER BY kind, name, …
  ENV        LOCALAPPDATA
  FILE       *.yaml, …
  NETWORK    f'{url}api/programs', socket.socket
  STDIO      msg
```

**What breaks if I change it?**

```bash
uv run dunneflow impact src --name dunneflow --routine _emit
```

```
dunneflow.cli._emit  (dunneflow/cli.py:59)
  19 routines depend on this, directly or transitively
  ways in affected (15):
    - analyze [CLI]
    - check [CLI]
    …
```

The second one is the question worth asking before you touch anything: not who calls it,
but **which ways into the program stop working**.

**What do its words mean, and who says so?**

```bash
uv run dunneflow glossary src --name dunneflow
```

```
44 of 153 terms are defined somewhere (29%)

calls  (13 uses)
  Turning call expressions into edges.
  [DECLARED_CODE] dunneflow/resolve/calls.py:1
```

Every definition carries where it came from and the line that proves it.

**What is its naming standard?**

```bash
uv run dunneflow naming src --name dunneflow
```

```
STATED — nothing in this program's documentation states a naming rule

MEASURED — counted against the code
  [C] 776/792  Routines are named in snake_case.  (16 exceptions)
  [B] 379/384  A routine marked private is called only from its own module.  (5 exceptions)
```

Two lanes, deliberately never mixed. **Stated** quotes rules somebody wrote. **Measured**
counts what the code actually does. A page of measured conventions holding 100% of the
time, headed "naming standard", would read as conformance to a rule nobody wrote.

**What does the documentation define that the code never uses?**

```bash
uv run dunneflow mirror src --name dunneflow
```

Four bands — Named, Borne, Spoken, Absent — where **Absent** (defined in documentation and
nowhere in the code at all) is the strongest signal of drift the two stores can produce
together.

**What looks wrong?**

```bash
uv run dunneflow check src --name dunneflow
```

```
[SUSPECT/PROBABLE] LOST_EDGE: `side` could not be connected: 4 definitions share the name
…
0 broken, 24 suspect, 15 informational
```

Exits non-zero **only on BROKEN**, so it can gate CI without failing your build over
things that merely look odd. `--all` includes informational findings, `--broken-only`
narrows to the ones that fail, `--verbose` prints each finding's detail and its blind spot.

**Ask the graph directly.**

```bash
uv run dunneflow query src --name dunneflow \
  --sql "select kind, count(*) n from boundaries group by kind order by n desc"
```

```
kind | n
DATABASE | 272
FILE | 144
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
revision               state            captured               files  label
2026-09-10T18:48:42Z   WORKING          2026-09-10T18:48:42Z      78
2026-09-10T18:48:30Z   FOR_COMPARISON   2026-09-10T18:48:30Z      73  DunneFlow at f795bc3 - 2026-09-08
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
was lost gets it back — it is not analysis, so the rule against re-analysing a sealed
snapshot never arises.

**Migrate stored paths** from absolute to relative, in place:

```bash
uv run dunneflow migrate output/dunneflow
```

## Serving

```bash
uv run dunneflow serve [dir] [--revision <rev>] [--port 8787] [--no-open]
```

`serve` takes a program directory, an output root, or **nothing at all** — and tells a
program from a root by asking whether the directory holds a map, never by its name.

With nothing open it serves [the start page](03-the-start-page.md). `--revision` chooses
which point in time opens as the base; it defaults to the newest, and you can change it
from the toolbar afterwards.

## Cleaning up

A superseded sealed snapshot is dropped **by hand**, deliberately — DunneFlow owns no
command that deletes a snapshot. Remove its `graph@….db` and `docs@….db`, then its rows in
`paths` and `revisions` in both sidecars. Bodies are shared by content and are left alone.

---

Back to [the index](README.md).
