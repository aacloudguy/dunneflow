# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches,
and why.

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back
out. **What moves is the subject. Internal computation is not.**

DunneFlow reads a source tree and the documentation beside it and gives you a map you can
walk around in — entrypoints, flows, routines, boundaries, database use, network and
messaging, governance, a glossary, a naming standard, and a list of anomalies. It is built
for someone orienting in a codebase they did not write, and it answers the same map to an
AI agent over MCP.

Deliberately *not* reported: local variables, arithmetic, and private helpers that neither
touch a boundary nor sit on a path to one. Leaving those out is most of what makes the
output readable.

Control flow is reported only where something **moves** inside it: a loop that increments a
counter is the internal computation nobody asked for, a loop that issues one network call
per item is a *rate*, and a rate is flow.

The goal is **comprehension, not documentation**.

**New here? [Read the guide.](docs/README.md)** It starts at installing and ends at holding
two versions of a program against each other.

## Download

**[The latest release](https://github.com/aacloudguy/dunneflow/releases/latest)** has a
double-clickable application for each platform. There is no Python to install; it opens your
browser on the start page, which is where you make your first map.

| | | First run |
|---|---|---|
| **macOS** | `DunneFlow-<version>.dmg` — Apple silicon and Intel | Signed and notarised: drag it to Applications and open it. It asks the system for no permissions. |
| **Windows** | `DunneFlow-<version>-windows-x64.zip` | **Unsigned**, so SmartScreen warns once: **More info → Run anyway**. `DunneFlow.exe` is what you double-click; `dunneflow-cli.exe` beside it is the command line. |
| **Linux** | `DunneFlow-<version>-linux-x86_64.tar.gz` | `tar -xzf` it, then `./dunneflow/install.sh`. Installs into `~/.local` with a menu entry and icons; nothing needs root. |

Each release carries a `SHA256SUMS` file. **Reading TypeScript needs Node.js 20 or newer**, and
**reading Go needs Go 1.22 or newer**, **reading Rust needs Rust 1.79 or newer**, and
**reading Java needs a JDK 17 or newer**, on the machine, because each is read by its own
toolchain; the other three languages need nothing. Without one, DunneFlow reads everything else
and says, in the run and in the map, which files it could not read and what to install;
`--without typescript`, `--without go`, `--without rust` or `--without java` makes the same
choice deliberately.

Details for each platform, including where maps are kept and how to move them, are in
[docs/01-installing.md](docs/01-installing.md).

## Run from source

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run dunneflow serve
```

## What it reads

Seven languages, each read by whatever understands it best. No language is a special case:
a reader is a plugin, and nothing above the graph names one ([`LANGUAGES.md`](LANGUAGES.md)
says what the fifth and sixth cost).

| | Files | Read by | Recognises | Calls inside the program |
|---|---|---|---|---|
| **Python** | `.py` | stdlib `ast`, in process | decorated CLI commands, HTTP routes, queue consumers, scheduled jobs, MCP listeners | resolved |
| **TypeScript** | `.ts` `.tsx` `.mts` `.cts`, JSX | TypeScript's own compiler, out of process | Next.js App Router pages and route handlers, React hook callbacks, Prisma and Supabase, `fetch` / WebSocket / EventSource / socket.io | resolved — by the compiler, not guessed |
| **C and C++** | `.c` `.cpp` `.cc` `.cxx` `.h` `.hpp` `.inl` … | clang's own parser (libclang), out of process, built on your machine | `main`; Unreal `UFUNCTION`s that are Blueprint-callable, replicated or `Exec`; `UE_LOG`; file, process and environment calls | resolved — by clang, where a file's includes can be found; every other call says why it was not |
| **Kotlin** | `.kt` `.kts` | syntactically, in process | Android and Hilt entry points, Jetpack `@Composable`, Retrofit, scheduled work | not resolved, and counted |
| **Go** | `.go` | Go's own type checker (`go/types`), out of process | `main`, `net/http` and router handlers registered by a call, cobra commands | resolved — by the checker, not guessed |
| **Rust** | `.rs` | `syn`, out of process, built on your machine and never fetching | each Cargo binary's `fn main`; `std::net`, `reqwest`/`ureq`, `rusqlite`, the OS keychain, the crypto crates | resolved by path — only where a path, or a type the source writes down, names one definition; every other call says where it stops and why |
| **Java** | `.java` | javac, out of process, built on your machine and never fetching | `main`; Spring MVC and JAX-RS routes; `@Scheduled`, listeners, Guice and Spring `@Provides`/`@Bean`; JDBC, Netty, `java.net`, `java.nio.file`, the JCA | resolved — by javac, not guessed; a call several bodies may answer is followed into all of them, *by dispatch*, and never drawn as an edge |

**Kotlin is read without a compiler**, because asking Kotlin's compiler would put a Java
runtime inside a bundle whose whole dependency list is `pyyaml`. So a Kotlin map states what
a program touches and every routine, loop and guard in it, but does not claim to know where
a call goes. The run says so with a count rather than leaving you to notice.

**C and C++ need no build first.** A `compile_commands.json` is used if there is one.
Otherwise include paths are inferred from the tree and a file is read on past an include
that cannot be found, and the map counts what that left out.

Documents beside the code (Markdown, reStructuredText, AsciiDoc and plain text) and the code's own docstrings and comments are
read too, as evidence and never as code: a glossary term quotes the file and line that defines
it. Teaching the tool a new framework is normally a config edit in `detectors/*.yaml`, not a
code change.

**Very large trees are read in parts.** Above 20,000 files `analyze` stops and offers the
tree cut into readable parts (`--parts`), each read with `--part-of` so its tests and skips
are judged from the whole tree. Unreal Engine was read this way: 88,356 files in 86 parts.

## The dashboard

`dunneflow serve` is the main way in. Three panes (navigator, centre, inspector), and the
centre is **one selection read six ways**, not six destinations:

| | |
|---|---|
| [Graph](docs/06-graph.md) | the whole program as a stack of plates |
| [Table](docs/07-table.md) | every routine as a sortable row |
| [Document](docs/08-document.md) | the eight documents DunneFlow writes, and every document your program carries |
| [Code](docs/09-code.md) | the source as measured, with every resolved call clickable |
| [Diagram](docs/10-diagram.md) | one compartment, drawn |
| [Shape](docs/11-shape.md) | what one routine *does*: its loops, decisions and refusals |

Around them: a [trail with Back, Forward and a shelf](docs/12-chasing-rabbits.md) so a
detour costs you nothing, and a [comparison](docs/14-comparing-two-versions.md) between two
points in time that says what a text diff cannot: which routines *behave* differently, not
which of their lines moved.

The dashboard is vanilla JavaScript and deck.gl over `http.server`: no framework, and no Node
to serve or build it.

## For agents

`dunneflow mcp` answers the same map to an agent over the Model Context Protocol, on stdio,
with no dependency beyond the standard library.

```bash
claude mcp add dunneflow -- uv run dunneflow mcp output
```

This repository carries a `.mcp.json` that does the same, so a Claude Code session started
here already has it.

| Tool | Answers |
|---|---|
| `overview` · `programs` · `open` | what maps there are, and one program's cover |
| `routine` | one routine whole: signature, callers, callees, boundaries, source and shape |
| `touches` · `impact` | what a routine reaches; what breaks if it changes |
| `find` | names and source text together, comments and strings included |
| `glossary` | what the program's words mean, with the file and line that says so |
| `query` | read-only SQL against the graph |
| `analyze` · `analysis_status` · `analysis_stop` | make a map in the background, watch it, stop it |

Two resources come with it: the graph's schema (`dunneflow://schema/graph.sql`) and every
document by id. **The server cannot change a map**: every store is opened read-only, and
`query` refuses anything that is not a read, `ATTACH` included.

## Command line

```bash
uv run dunneflow analyze   <path> --name <program>   # extract, resolve, write the map
uv run dunneflow serve     [dir]                     # the dashboard
uv run dunneflow mcp       [dir]                     # the map, answered to an agent
uv run dunneflow touches   <path> --routine <name>   # what does this reach?
uv run dunneflow impact    <path> --routine <name>   # what breaks if I change it?
uv run dunneflow check     <path>                    # anomalies; non-zero exit on BROKEN
uv run dunneflow glossary  <path>                    # what its words mean, and who says so
uv run dunneflow naming    <path>                    # the naming standard: derived, and quoted
uv run dunneflow mirror    <path>                    # words the docs define that the code never uses
uv run dunneflow query     <path> --sql "..."        # ask the graph directly
uv run dunneflow revisions <dir> [--seal]            # what snapshots this holds; keep the current one
uv run dunneflow render    <dir>                     # a snapshot's Markdown, from the graph it has
```

From the application, drop `uv run`: the binary is `dunneflow` (on Windows,
`dunneflow-cli.exe`).

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`), and `--standards <dir>` admits somebody
else's naming standard without absorbing it. `--without <lang>` declines a language and says
so in the map, and `--include-tests` keeps what is normally left out as tests. It is
incremental: unchanged files are not re-parsed.

Point it at itself for a worked example:

```bash
uv run dunneflow analyze src --name dunneflow
```

Full reference: [docs/16-the-command-line.md](docs/16-the-command-line.md). `migrate`
upgrades maps made by older versions; `ingest-schema` and `ingest-conform` are for writing a
language reader and are described in [`LANGUAGES.md`](LANGUAGES.md).

## What a program directory contains about your machine

A program directory is built to be **handed over**: copied to a colleague, kept after
the source tree has moved on, read on a machine that has never held the code. So what it
records about where it came from is a deliberate, short list.

**Not recorded:** the path to the analysed tree. Every stored path is relative, and the
root is never written down. It is one machine's directory layout, it is wrong the moment
anything moves, and it is wrong on every machine a copy reaches. Nothing at read time
needs it: file bodies are held by content hash, never fetched by opening a path.

**Recorded:** the **leaf** of the directory each version was read from (`society-2026-08-26`,
not the path that led to it). Two versions of one program are two directories, so the leaf
is what a reader recognises them by; a capture instant only says when we read the bytes.

**Recorded:** the version the program **states about itself**, if it states one: from
`pyproject.toml [project] version`, or a module-scope `__version__`, each with the file
that proves it. Where the source says nothing, a version may be guessed from the
directory's own name (`app-1.2.3`, `society-2026-08-26`) and is then marked as inferred
wherever it appears. DunneFlow never asks a version control system anything.

**Recorded, unless you say not to:** the source itself, in `source.db`, so the Code view
works after the tree has gone. `--no-source` and `--no-doc-source` leave it out.

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

SQLite is the spine, not an export format: nothing holds the whole program in memory,
and reachability is recursive SQL over indexed edges. A reader in another language speaks
a small JSON protocol over a pipe, and its output is checked against the same contract the
in-process Python reader keeps. Each reader's rules and bytes are part of the cache key for
its own files, so changing one language's reader costs that language a re-read and the others
nothing.

## Two disciplines

**Every finding states what would make it a false alarm.** Anomalies carry a severity
(what it would mean for the program), a confidence (how sure the tool is), and a blind
spot. They are different questions and are never blurred. A severity is a claim about a
language, so each language declares its own: a dropped coroutine never runs in Python, but a
dropped promise in TypeScript still does.

**Every reported meaning carries its provenance.** A quoted definition proves itself
with a file and line; a measured claim ships the SQL that counted it; an inferred one
cannot prove itself and must say so.

Nothing on the analysis path calls a model or opens a network connection, and a test fails
if anything under `extractors/`, `resolve/` or `canonical/` starts importing an HTTP client
or a model SDK. That is a standing guarantee rather than a current state of affairs.

## Known limits

Stated here rather than left to be found:

- **Kotlin calls are not resolved** inside the program; every one is external, and the map
  says how many.
- **A C or C++ tree that has not been configured loses what its build would generate**:
  `config.h`, `*.generated.h`. Unreal's `Runtime` read 10,923 of 18,259 files past a missing
  include. The calls clang could not then resolve are counted, each with its reason.
- **A large C++ tree takes hours, and one header edit re-reads all of it.** A file's facts
  depend on what it includes. Unreal's `Runtime` (18,263 files) took 2 h 20 m to 3 h on an
  8 GB Apple M1, so `analyze` states an estimate and asks first.
- **A very large single map is slow to open.** 262,879 routines (one part of Unreal) takes
  about 4.6 minutes in the dashboard, down from 27.6. Reading in parts keeps each map to a
  size that opens quickly.
- **A call the source does not spell is not seen**: JavaScript served as a string, or `fetch`
  handed in as a parameter. (A `const` holding the global `fetch` is followed.) A NETWORK
  count means *what this program calls*, not everything it causes.
- **A subdirectory analysed on its own**, without `--part-of`, looks upward for its package
  root and documentation, and can settle further up than you meant. The run says where it
  settled and how many levels up, so it is never a surprise.

The full list, each with where it came from and why it stands, is the stated residues in
[`BACKLOG.md`](BACKLOG.md).

## Development

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Unit tests on a toy program cannot catch a resolution defect that only appears at
scale, so changes are also verified against real codebases before being called done.
Releases are built by `packaging/release.sh` (macOS), `packaging/release.ps1` (Windows) and
`packaging/release-linux.sh` (Linux), described in [`PACKAGING.md`](PACKAGING.md).

Engineering rules (the ones learned the hard way, each from a false result on real
code) are indexed in [`CLAUDE.md`](CLAUDE.md) and written out in [`RULES.md`](RULES.md);
the dashboard's are in [`DESIGN-RULES.md`](DESIGN-RULES.md). What each module owns is in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Status

**0.2.0**, the second line of DunneFlow. It is the same tool as 0.1.0, rebuilt so that
reading is modular. It adds TypeScript, C++ and Kotlin beside Python, the MCP server, and
reading very large trees in parts. It is verified at scale: its own source, a 628-file Python
application read identically by both lines, a TypeScript monorepo, and Unreal Engine.

All three platforms run it. macOS is signed and notarised; Windows and Linux are built and run
at the keyboard and are unsigned. Every build stamps the same reader fingerprints, so a map
made on one opens on the other two. Two platform differences are documented rather than fixed,
because neither is DunneFlow's to fix: on **Windows** a folder chooser asked for by a
background process opens behind the browser, and on **Linux** the folder picker needs zenity
or kdialog installed, and says so by name if neither is.

The 0.1.0 line is kept on the [`v1`](https://github.com/aacloudguy/dunneflow/tree/v1) branch
and the `v1-final` tag. What is open is [`BACKLOG.md`](BACKLOG.md), and how to work on the
tool is [`CLAUDE.md`](CLAUDE.md). The figures in [`PERFORMANCE.md`](PERFORMANCE.md) were
measured on 0.1.0 unless marked otherwise.

## Licence

DunneFlow is released under the [MIT licence](LICENSE), © 2026 Dunne, Corp. It carries
deck.gl, Mermaid and markdown-it (MIT), @hpcc-js/wasm and the TypeScript compiler
(Apache-2.0), and Graphviz (EPL-1.0), each under its own licence; the packaged applications
add CPython, PyYAML and OpenSSL. [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) lists them
all, and every licence text is in [`licenses/`](licenses/).
