# 13. The command line

Everything in this tutorial so far went through a browser. It does not have to.

The dashboard is a reader for a map; the map is a SQLite database in a directory, and the
same command that made it will answer questions about it without a server. `dunneflow` has
fifteen subcommands. This chapter is the subset you will actually reach for, using the map
you already have.

## Where a command looks

Start with the one thing that will confuse you once and never again:

```bash
uv run dunneflow touches output/dunneflow --routine cmd_analyze
```

```
no --output given; maps go to output
cli.cmd_analyze  (cli.py:576)
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
cli.cmd_analyze  (cli.py:576)
  reaches 411 routines
  CRYPTO     hashlib.sha256, raw.encode('utf-8'), text.encode('utf-8')
  DATABASE   
            WITH RECURSIVE reach(id, depth) AS (
            …
            SELECT DISTINCT id FROM reach WHERE id IS NOT NULL
            , ANALYZE, DELETE FROM annotations WHERE owner_id IN (…), DELETE FROM call_args …
  ENV        LOCALAPPDATA, XDG_DATA_HOME
  FILE        , ', '\n'.join(lines), '\n'.join(lines) + '\n', *.md, *.yaml, -, :
  PROCESS    self.argv
  STDIO      f"{program}: {c['routines']:,} routines · …", f'docs:  {…}', f'graph: {db_path}', …
```

This is [chapter 3](03-one-selection-six-ways.md)'s inspector with no pixels. 411 routines
reachable, and every boundary any of them touches, grouped by kind and quoted **as
written** — the SQL is the SQL, line breaks and all, which is why the first DATABASE entry
is a recursive query spread over several lines: `reach`, the walk over the call graph
[chapter 9](09-what-looks-wrong.md) met as a table nobody writes. The environment
variables are the two it really reads, and the STDIO line begins with the f-string that
printed [chapter 1](01-pointing-it-at-itself.md)'s summary line.

## What breaks if I change it?

```bash
uv run dunneflow impact output/dunneflow --routine write_file_facts
```

```
store.Store.write_file_facts  (store.py:1128)
  5 routines depend on this, directly or transitively
  ways in affected (4):
    - analyze [CLI]
    - dunneflow [CLI]
    - main [MAIN]
    - python -m cli [MAIN]
```

`touches` runs the graph forwards; `impact` runs it backwards and then says which **ways
in** are behind you. Five routines depend on it, and four ways in — every one of them a way
in from the command line: the `dunneflow` console script its `pyproject.toml` declares, the
`analyze` subcommand, `main`, and `python -m`. For the routine that writes a file's facts
into the store, that is exactly right and reassuring to see stated.

## The gate

```bash
uv run dunneflow check output/dunneflow
```

```
[SUSPECT/PROBABLE] LOST_EDGE: `_literal` could not be connected: 2 definitions share the name  extractors/python/extract.py
[SUSPECT/PROBABLE] LOST_EDGE: `_scan` could not be connected: 2 definitions share the name  extractors/cpp/control.py
…
[SUSPECT/PROBABLE] NO_TIMEOUT: 2 of 3 remote calls set no timeout  web/serve.py:3764
…
0 broken, 26 suspect, 18 informational
```

Same forty-four findings as [chapter 9](09-what-looks-wrong.md): the 26 suspect ones a line
each, and the 18 informational ones counted in the last line — `--all` prints those too.
**It exits non-zero only on BROKEN**, so it can gate a build without failing it every time
the tool is merely unsure. Here it exits `0` with 26 findings printed.

## The vocabulary, without a browser

```bash
uv run dunneflow naming output/dunneflow
```

```
STATED — nothing in this program's documentation states a naming rule

MEASURED — counted against the code
  [B] 1,231/1,247  Python routines are named in snake_case.  (16 exceptions)
  [B] 611/621  A routine marked private is called only from its own module.  (10 exceptions)
  …
  [D] 165/182  Python classes are named in PascalCase.  (17 exceptions)
  …
  [A] 11/11  TypeScript modules begin with `plugins`.
  ... 1 more; all of them in 11-naming.md
```

Both lanes, and the empty one first. The last line names the file in the map's own
Markdown that holds all sixteen conventions with every exception, because a terminal is not
the place for them.

**`--allow-leading-underscore`** is the Setting from [chapter 10](10-words-and-names.md), as
a flag. Every convention it applies to says so in its own line, and the class count moves:

```bash
uv run dunneflow naming output/dunneflow --allow-leading-underscore
```

```
  [B] 179/182  Python classes are named in PascalCase (a leading underscore allowed).  (3 exceptions)
  [B] 154/157  Python data structures are named in PascalCase (a leading underscore allowed).  (3 exceptions)
```

`glossary` prints the defined terms with their citations, and opens with the count:

```
82 of 223 terms are defined somewhere (37%)
```

`mirror` prints the third question, the one with no page in the dashboard — **words the
documents define that the code never uses**:

```
2 definitions read, 2 set aside as not a word, 0 terms carried forward
  Named       0   Something in the program is called this: …
  Borne       0   A routine, a parameter or a field carries the word, but nothing is called it. …
  Spoken      0   The word appears only in comments and docstrings. …
  Absent      0   Defined in documentation, and nowhere in the code at all. …

only Python and TypeScript are extracted: absent from this graph is not absent from the product.
```

On DunneFlow the two definitions are headings out of this tutorial that merely look like
definitions, both are set aside, and every row reads 0 — and the closing line would invite
you to discount even one that survived.

## Which versions are in here

```bash
uv run dunneflow revisions output/dunneflow
```

```
revision               state            captured                files  label
2026-10-02T19:59:52Z   WORKING          2026-10-02T19:59:52Z      142
2026-10-02T19:59:47Z   FOR_COMPARISON   2026-10-02T19:59:47Z      141  DunneFlow at 1017ef4 - before the Windows fix
2026-10-02T19:59:41Z   FOR_COMPARISON   2026-10-02T19:59:41Z      141  DunneFlow at 0804aa7 - before parts
```

The versions from [chapter 8](08-two-versions.md), and the mechanism behind them in one
table.
`WORKING` is a *state*, not a name: the next `analyze` rewrites that row. `--seal` is what
turns the working snapshot into a `FOR_COMPARISON` one with a label, so the analysis after
it opens a second point in time beside the first rather than replacing it.

## Asking the graph anything

The other subcommands are questions somebody decided were worth a verb. `query` is the
escape hatch for every question nobody did:

```bash
uv run dunneflow query output/dunneflow \
    --sql "SELECT kind, COUNT(*) n FROM boundaries GROUP BY kind ORDER BY n DESC"
```

```
kind | n
DATABASE | 290
FILE | 154
STDIO | 62
PROCESS | 9
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
| `mcp` | the same map, answered to an agent over MCP instead of a browser |
| `ingest-schema`, `ingest-conform` | for somebody teaching DunneFlow a new language: what a reader must emit, and whether it spells a call the way the rules match |

`render` is the one worth knowing about in advance. A sealed snapshot whose Markdown was
lost gets it back without being re-analysed — which matters precisely because a sealed
snapshot is never re-analysed in place, so re-running `analyze` is not an option and was
never meant to be.

The full reference for every subcommand and every flag is
[chapter 16 of the guide](../16-the-command-line.md).

---

That is the tour. Thirteen chapters, one program, and every number in them taken off the
screen or out of a terminal against DunneFlow reading its own source.

If you want the shortest possible proof that the tool works on something you have not been
shown: point it at a codebase you do not know, open the cover, and read *what it touches*
before you open a single file.

Back to [the contents](README.md) · [Using DunneFlow](../README.md).
