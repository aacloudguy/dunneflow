# 13. The command line

Everything in this tutorial so far went through a browser. It does not have to.

The dashboard is a reader for a map; the map is a SQLite database in a directory, and the
same twelve commands that made it will answer questions about it without a server. This
chapter is the subset you will actually reach for, using the map you already have.

## Where a command looks

Start with the one thing that will confuse you once and never again:

```bash
uv run dunneflow touches output/dunneflow --routine cmd_analyze
```

```
no --output given; maps go to output
cli.cmd_analyze  (cli.py:256)
…
```

That first line is not an error, and it is worth reading properly. **The path you hand
these commands is a program name, not a directory.** DunneFlow takes its last segment —
`dunneflow` — and looks for a program of that name under the **maps root**, which is
`./output` from a checkout and a per-platform application directory when you are running
the packaged app. The line tells you which root it used.

Which means `dunneflow` and `some/nonsense/dunneflow` find the same map, and
`--output` is how you point somewhere else:

```bash
uv run dunneflow touches dunneflow --output output --routine cmd_analyze
```

## What does this reach?

Every transcript from here on leaves that first line out.

```bash
uv run dunneflow touches output/dunneflow --routine cmd_analyze
```

```
cli.cmd_analyze  (cli.py:256)
  reaches 287 routines
  CRYPTO     raw.encode('utf-8'), text.encode('utf-8')
  DATABASE   ANALYZE, DELETE FROM annotations WHERE owner_id IN (…), DELETE FROM call_args …
  ENV        LOCALAPPDATA, XDG_DATA_HOME
  FILE        , '\n'.join(lines), *.md, *.yaml, -, ., :
  STDIO      f'{program}: {c['routines']:,} routines · …', json.dumps(fields), msg
```

This is [chapter 3](03-one-selection-six-ways.md)'s inspector with no pixels. 287 routines
reachable, and every boundary any of them touches, grouped by kind and quoted **as
written** — the SQL is the SQL, the environment variables are the two it really reads.

## What breaks if I change it?

```bash
uv run dunneflow impact output/dunneflow --routine write_file_facts
```

```
store.Store.write_file_facts  (store.py:799)
  5 routines depend on this, directly or transitively
  ways in affected (3):
    - analyze [CLI]
    - main [MAIN]
    - python -m cli [MAIN]
```

`touches` runs the graph forwards; `impact` runs it backwards and then says which **ways
in** are behind you. Five routines depend on it, and all three of the program's command
line entrances are among them — which, for the routine that writes a file's facts into the
store, is exactly right and reassuring to see stated.

## The gate

```bash
uv run dunneflow check output/dunneflow
```

```
[SUSPECT/PROBABLE] LOST_EDGE: `side` could not be connected: 4 definitions share the name  web/changes.py
[SUSPECT/PROBABLE] NO_TIMEOUT: 2 of 3 remote calls set no timeout  web/serve.py:3419
…
0 broken, 25 suspect, 15 informational
```

Same forty findings as [chapter 9](09-what-looks-wrong.md), one line each. **It exits
non-zero only on BROKEN**, so it can gate a build without failing it every time the tool
is merely unsure. Here it exits `0` with forty findings printed.

## The vocabulary, without a browser

```bash
uv run dunneflow naming output/dunneflow
```

```
STATED — nothing in this program's documentation states a naming rule

MEASURED — counted against the code
  [B] 790/806  Routines are named in snake_case.  (16 exceptions)
  [B] 383/388  A routine marked private is called only from its own module.  (5 exceptions)
  …
  [A]   12/12  A routine beginning with `cmd` is registered as a way in.
```

Both lanes, and the empty one first. `glossary` prints the 44 defined terms with their
citations; `mirror` prints the third question, the one with no page in the dashboard —
**words the documents define that the code never uses.** On DunneFlow that is three, and
all three are sentences from a session journal that merely look like definitions, which
the command's own closing line invites you to discount:

> only Python is extracted: absent from this graph is not absent from the product.

## Which versions are in here

```bash
uv run dunneflow revisions output/dunneflow
```

```
revision               state            captured                files  label
2026-09-15T22:14:29Z   WORKING          2026-09-15T22:14:29Z       78
2026-09-15T22:14:26Z   FOR_COMPARISON   2026-09-15T22:14:26Z       78  DunneFlow at 875499c - before Linux
```

The pair from [chapter 8](08-two-versions.md), and the mechanism behind it in one table.
`WORKING` is a *state*, not a name: the next `analyze` rewrites that row. `--seal` is what
turns the working snapshot into a `FOR_COMPARISON` one with a label, so the analysis after
it opens a second point in time beside the first rather than replacing it.

## Asking the graph anything

The other eleven commands are questions somebody decided were worth a verb. `query` is the
escape hatch for every question nobody did:

```bash
uv run dunneflow query output/dunneflow \
    --sql "SELECT kind, COUNT(*) n FROM boundaries GROUP BY kind ORDER BY n DESC"
```

```
kind | n
DATABASE | 272
FILE | 142
STDIO | 56
PROCESS | 6
ENV | 5
CRYPTO | 3
NETWORK | 3
```

That is the cover's **WHAT IT TOUCHES** panel, in a terminal, to the row. Nothing on the
cover is computed anywhere the rest of the tool cannot reach.

This is the same door every **show the query** button in the dashboard opens onto
([chapter 11](11-worth-a-look.md)), and it is why those buttons are worth anything: the
statement on the card runs here unchanged, and returns what the card said.

Two things to know before you lean on it.

**It is read-only and it will tell you when a map is half-written.** Every other command
that reads a map refuses an unfinished one outright — an `analyze` killed part-way leaves a
graph that opens perfectly and lies, so a reader that vouches for a number will not read
one. (`analyze` itself is exempt, because re-opening one is how it recovers.) `query`
is the single exception: it proceeds and **warns**, because its whole contract is that you
get the rows that are there.

**The table names are the fact contract's.** `routines`, `calls`, `boundaries`, `files`,
`constants`, `comments`, `sql_ops` — one schema that every extractor in every language
emits into, which is why a query written against a Python program will run against
whatever DunneFlow learns to read next. [Chapter 9](09-what-looks-wrong.md) introduced you
to it by accident: the worklist's phantom tables were CTE names in statements exactly like
this one.

## The rest

| | |
|---|---|
| `analyze` | read a tree and write a map — [chapter 1](01-pointing-it-at-itself.md) |
| `serve` | the dashboard — everything from chapter 2 on |
| `render` | rewrite a snapshot's Markdown from the graph it already has, no re-analysis |
| `migrate` | rewrite a map written before stored paths were relative |

`render` is the one worth knowing about in advance. A sealed snapshot whose Markdown was
lost gets it back without being re-analysed — which matters precisely because a sealed
snapshot is never re-analysed in place, so re-running `analyze` is not an option and was
never meant to be.

The full reference for all twelve, every flag, is
[chapter 16 of the guide](../16-the-command-line.md).

---

That is the tour. Thirteen chapters, one program, and every number in them taken off the
screen or out of a terminal against DunneFlow reading its own source.

If you want the shortest possible proof that the tool works on something you have not been
shown: point it at a codebase you do not know, open the cover, and read *what it touches*
before you open a single file.

Back to [the contents](README.md) · [Using DunneFlow](../README.md).
