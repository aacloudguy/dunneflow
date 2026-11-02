# DunneFlow — ground truth, and the gates that use it

`CLAUDE.md` carries the three verification gates as commands; this file carries **the
corpora they are run against, what each one is for, and the figure each is expected to
reproduce** — plus the two probes that are not tests: `tools/ordering.py` and
`tools/fingerprints.py`.

**Read this before quoting a figure, retaking one, or rebuilding the comparison pair.** A
row here states its conditions where they are load-bearing, and a measurement taken without
reproducing them is a different measurement under the same label (rule 24).

**Society is unpublished.** It is a 628-file Python application whose package is `mensores`,
and most figures in this repository were measured on it. Its snapshots sit beside this
repository as `../society-<date>` and are the maintainer's, so a contributor without them
cannot run this gate and should say so rather than report it passed. The four
Society clones are read-only and only two of them are the pair; getting that wrong cost a
whole analysis once, and the result looked perfectly healthy.

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

**All three run on Windows and on Linux as well, and the suite is expected to be green on all
three.** Two tests skip off their own platform, by name — the macOS and Linux maps roots, each
asserting its own layout — and nothing else is conditional. Everything else that is
platform-shaped is tested by **monkeypatching `sys.platform`** rather than by skipping, so the
Linux picker and the Windows stop rungs are exercised on whichever machine is running:
`tests/test_desktop.py` says why, and the two-of-four guard drift in `analysis.py` is what
happens when they are not.

`mypy` is worth running with `--platform darwin`, `--platform linux` and `--platform win32`
from any machine when anything under a `sys.platform` branch has moved: it checks the branches
this machine cannot execute, and it is the only gate that can — a Linux-only
`name is not defined` in `reveal_dir` was found exactly that way and no test on any platform
would have caught it.

And when anything under `runtime.py`, `packaging/`, `detectors/` or `extractors/` has
moved, **through the binary as well as beside it** — the tests prove the source tree and
not the artifact:

```bash
DUNNEFLOW_ARCH=host uv run pyinstaller packaging/dunneflow.spec --noconfirm
dist/DunneFlow.app/Contents/MacOS/dunneflow analyze <tree> --name x --output <tmp>   # macOS
dist/dunneflow/dunneflow analyze <tree> --name x --output <tmp>                      # Linux
./packaging/release-linux.sh verify        # does all of it, and compares the fingerprints
```

The one check that is not a ground-truth number, and it is **`tools/fingerprints.py`**:

```bash
uv run python tools/fingerprints.py dist/DunneFlow.app/Contents/MacOS/dunneflow
```

Every stamp the binary writes must equal the one this checkout computes, or the two builds
have stopped being able to read each other's maps (rule 12, and see `PACKAGING.md`). There
are **two kinds now** — the core key and one per language — so it reads a tree that holds
every language this build has a reader for, and **refuses when a registered language
contributed no rows**: a stamp that was never compared is not a stamp that agrees (rule 37).
It proves the property rather than a proxy for it, by having each build open the other's map
and letting `Store(writable=False)` speak.

All three `verify` steps run it and **none of them asks the question itself**. Both of the
two that did were calling `rules_fingerprint()`, which chunk 5 split in two; from then until
chunk 13 they raised `ImportError` — in the step written to defend rule 12, on no test path.
A Python question kept at a shell call site rots as the Python moves (rule 51), and a test
now asserts no release script spells one.

**And `tools/ordering.py` when anything under `render/` or `resolve/` has moved.** The map
may not depend on the order its rows happen to be in — `analyze_tree` collects facts through
`as_completed`, so every rowid varies run to run, and a query with no `ORDER BY` or one
ordering on a column with ties returns whatever the pool finished first (rule 66). It was
like that for a year:

```bash
uv run python tools/ordering.py output/mensores          # reverses every row, re-renders, diffs
uv run python tools/ordering.py output/mensores --api    # every GET route, asked twice
uv run python tools/ordering.py --survey                 # what no ORDER BY, and no key, defends
uv run python tools/ordering.py output/mensores-wide --api   # the comparison lane's own pair
```

**`output/mensores-wide` is the pair the comparison lane is measured against**, and it is
wide on purpose: Society's `main` at `09b9ef11` against the branch head at `03ebbd93`,
**384 Python files against 628**, where the `mensores` pair differs in three. It is what
takes `/api/changes` from three rows to 2,733, and its old side's tree is gone — a sealed
snapshot does not need one (rules 25 and 62). Rebuild it by cloning that repository at
`origin/main` into a scratchpad, analysing it with `--standards ../dunnecorp-standards`,
sealing, and analysing the branch head beside it.

**`--api` is the same argument one surface over, and it is what `web/` is measured by.**
The rendered map is the artifact that gets handed over; the dashboard is where a reader
actually stands, and it had the defect the map no longer had. It asks every route in
`_Handler.ROUTES` of two copies of one program with a **fresh `_Live` each**, because most
of the dashboard is cached and a third of it is filled before the first request arrives.
Three passes and not two: the straight copy is asked twice, so what differs between two
readings of *one* copy is named as noise rather than forgiven by a hand-kept list. A route
that was asked nothing, handed an empty parameter, or raised is **named and fails the run** —
each of those diffs perfectly clean (rule 37). `--survey` says where to look and decides
nothing; it is **rule 101** that says why the probe and not the survey is the authority.

Reversal rather than a second analysis, because two real runs shuffle *some* of the order
and catch *some* of the ties, differently each time. `tests/test_ordering.py` is the same
gate on a fixture; every file in it is a tie the Society map was actually unstable on —
including the three the *comparison* lane needs, which no corpus supplies at all.

**Half of what this gate covers, the reversal cannot see, and that is rule 105.** A
`sorted()` handed a set keeps the set's order for rows equal on the key, and that order is
the hash seed's rather than the rows' — so a route can be reversal-clean and still hand two
readers different pages. `--survey` counts that population beside the `ORDER BY` one and
decides nothing about either; what settles it is a **total** key, and in `web/changes.py`
that is `_settle`.

Then verify against real code, because unit tests on a toy program cannot catch a
resolution defect that only appears at scale:

```bash
uv run dunneflow analyze ../society-2026-08-29/src --name mensores
```

**Four trees, and only two of them are the pair.** `../society-2026-08-26` (e2e658b4,
625 files) and `../society-2026-08-29` (03ebbd93, 628 files) are the sister clones every
recorded temporal figure belongs to; `../mensores-overhaul` is a third copy of 626 files
and is neither end of it. This file named `mensores-overhaul` here for a year and it cost a
wasted analysis in the session that bumped `SCHEMA_VERSION` — the result looked perfectly
healthy, and the tell was the sidecar reporting *"1 read, 625 already held"* where the record
says twelve files differ.

`../society-2026-08-30` (7baa17bf, 628 files) is the checkpoint taken 2026-09-09, and it is
the newest Society there is: 6 commits past 03ebbd93, 43 files changed, and **3 source files**
of them. **`main` is not where Society lives** — it sits at 09b9ef11 from 2026-06-10 with 384
files under `src/`, and the work is on `feat/spec-lifecycle-and-evidence`. Cloning the default
branch gets a tree three months stale that analyses perfectly, which is why the branch is
named here.

**All four are read-only.** They are copies kept for documentation. Never write to any of
them. All output belongs in `output/`.

**None of the four is on the Linux machine, and neither is `../dunnecorp-standards`.** So the
ground truth above cannot be run there and no figure in this file was retaken on it. What a
Linux session can press instead is DunneFlow's own tree and `../dunnenote` — real code, not a
toy, and enough to exercise the binary end to end — and that is what the Linux figures in
**Packaging** were taken against. A session that needs the recorded numbers needs the trees:
clone them, or take the measurement on the Mac. Do not restate a Mensores figure measured
somewhere else as though it had been reproduced (rule 24).

Rebuilding the pair after a schema bump is two analyses and a seal, in this order — a
sealed snapshot is never re-analysed in place, by design (rules 25 and 62):

```bash
uv run dunneflow analyze ../society-2026-08-26/src --name mensores
uv run dunneflow revisions output/mensores --seal --label "Society at e2e658b4 - 2026-08-26"
uv run dunneflow analyze ../society-2026-08-29/src --name mensores \
    --standards ../dunnecorp-standards
```

**The third command carries `--standards` and the recipe said nothing about it for two days.**
`standards.db` is a document store like the corpus: a change to `detectors/docs/` or
`extractors/docs/` moves `doc_rules_fingerprint()` and stales it with everything else — and
`serve` **refuses to boot** on a stale one, before a page is served. Rebuilding the pair
without it leaves a map that analyses perfectly and cannot be opened. The directory is an
outside standard the reader names; if the one a map was built with is gone, the store can be
dropped and the conformance lane says so in its own words. Found 2026-09-08, the hard way.

**It lives at `../dunnecorp-standards/` now, and that is not a detail.** The store records
the root it was built from, and the first two were built from a session's scratchpad — so
`standards.db` recorded a path that no longer existed and the standard's provenance was
unreproducible twice. Not inside this repository, deliberately: DunneFlow's documentation
root is its package root, so a standards directory there would be read back as DunneFlow's
own prose and mint three naming rules this program never stated — rule 57's argument, one
directory over. `naming.md` is identical to the `CORP` fixture in `tests/test_standards.py`.

**A snapshot whose map was lost gets it back without an analysis.** `dunneflow render
<dir>` writes the map of every revision here that has a graph and no map, read-only, from
the stores already on disk — so it is not analysis and rules 25 and 62 never arise. It also
takes `--revision` to rewrite one. What it will not do is invent inputs: a `docs@` store is
resolved by name and never by newest, and a `standards.db` captured against another snapshot
is held out of the comparison with the naming page saying so.

**A superseded sealed snapshot is still dropped by hand**, and that is deliberate:
`sourcedb.py` owns no `DROP` and `test_source.py:171` asserts it against the source text. Each
rebuild leaves one behind — delete its `graph@…db` and `docs@…db`, then its rows in `paths`
and `revisions` in **both** sidecars. Blobs are shared by content and are left alone.

Ground truth for documentation: the pantheon table in
`.groma/milestones/v1.1-harness-ownership/NAMING.md` yields `groma`, `disceptator`,
`quaestor` and the rest with their Latin glosses; its three BINDING rules appear in the
**Vocabulary** lane, quoted whole; `.groma/PROJECT.md` and `docs/reference/glossary.md`
both define `mensor` from *mētior*. And the precision half, which matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about*
building a naming-standards importer, and must yield **zero** naming rules. If it yields
any, the detector is wrong, not the corpus.

Ground truth for code: the four executables declared in its
`pyproject.toml [project.scripts]` — `mensores`, `mensores-mcp`, `mensores-signator`,
`mensores-scriba` — must all appear in "Where to start" with plausible reach. If one
collapses to a reach of 1 or 2, a registration idiom is being missed.

## Go: two public trees, and what each reproduces (2026-11-01)

**Neither is Society, and neither is the pair.** They are what the Go reader was measured on,
in `../beads-main` and `../AppGraphs/rain-main`, both public projects copied to this machine,
and both **read-only** like every other corpus here. Analyse into a scratch output root.

```bash
uv run dunneflow analyze ../AppGraphs/rain-main --name rain --output <tmp> --no-render
uv run dunneflow analyze ../beads-main --name beads --output <tmp> --no-render
uv run dunneflow check   ../beads-main --name beads --output <tmp> --all --limit 300
```

At `go-reader` 2a9dedf, with Go 1.25.6:

| | rain | beads |
|---|---:|---:|
| Go files read (tests left out) | 147 (49) | 484 (386) |
| routines | 758 | 3,721 |
| Go edges supplied, every one matched to a routine by its first line | 3,615 | 7,449 |
| several declarations (interface calls) | 16 | 852 |
| of which drawn to linux/amd64 of several platform variants | 0 | 38 |
| outside / unknown, as the reader counts them | 2,661 / 628 | 17,907 / 4,570 |
| findings | 0 broken · 1 suspect · 3 informational | 0 broken · 13 suspect · 44 informational |

**Every SUSPECT left on both was read against the source.** On rain, `NO_TIMEOUT`: six
`http.Get` calls through Go's default client, which has none. On beads, `NO_TIMEOUT` again; ten
`SCHEMA_DRIFT`, every one a table its SQLite and Dolt backends create with different column
types, which is true; `/static/` leading nowhere, whose handler is `http.StripPrefix(...)`,
a value a library builds, which the finding's blind spot names; and one belonging to the
Python reader. Three earlier defects found the same way were this reader's and are fixed
(`LANGUAGES.md`, *A fifth reader*).

**The unknowns are two things, and both are stated rather than guessed.** A method on a type
from a dependency (cobra's `Cmd.Flags()`), because a package from outside the tree is an empty
stand-in and nothing is downloaded; and a function held in a package variable (rain's
`console.Yellow`). `BACKLOG.md` says what would turn the first into *outside*.

*Amended 2026-11-01, at `rust-reader` 651e930:* beads' `NO_TIMEOUT` reads **5 of 12**, not
all of them. Its seven `net.DialTimeout` calls carry their timeout as an argument, and
`go.yaml`'s `network.timed` now reads it; the five left are HTTP clients, whose timeout, if
any, is on the client — the finding's own blind spot. The table above is the figure at
2a9dedf and is not rewritten.

## Rust: DunneNote and pdfcraft, and what each reproduces (2026-11-01)

**Neither is Society, and neither is the pair.** `../DunneNote` is Tom's Tauri application —
Rust under a TypeScript front end, so its map is mixed — and `../pdfcraft` is a Rust
workspace of 35 packages. Both are **read-only**; analyse into a scratch output root.

```bash
uv run dunneflow analyze ../pdfcraft  --name pdfcraft  --output <tmp> --no-docs --no-render
uv run dunneflow analyze ../DunneNote --name dunnenote --output <tmp> --no-docs --no-render
uv run dunneflow check   ../pdfcraft  --name pdfcraft  --output <tmp> --all
```

At `rust-reader` 50ba0a1, Rust 1.98.1, on the Mac:

| | pdfcraft | DunneNote (Rust half) |
|---|---:|---:|
| `.rs` files read | 267, of which 17 test modules are then left out | 204, of which 2 test modules are left out |
| test files / inline test items left out | 85 / 658 | 97 / 159 |
| Rust edges supplied, every one matched to a routine by its first line | 17,240 | 5,113 |
| built one of the program's own types (`calls.constructs`) | 2,444 | 484 |
| several declarations — no edge | 16 | 70 |
| outside / unknown, as the reader counts them | 44,374 / 15,813 | 12,367 / 2,241 |
| dependencies read from the local cargo cache / spelt only | 60 / 16 | 40 / 5 |
| findings | 0 broken · 7 suspect · 4 informational | 0 broken · 4 suspect · 55 informational (whole map) |

**Every SUSPECT left on both was read against the source.** On pdfcraft:
- Six `LOST_EDGE`, each a real choice between two definitions: `self.get_object` and
  `self.trailer` in a trait default body with two impls; `self.doc.*` through a
  `&dyn Structure` with the same two; and `Self::from` with two `From` impls, chosen by the
  argument's type.
- One `NO_TIMEOUT`: `TcpStream::connect` with no connect timeout. The read timeout is set on
  the stream afterwards, which the blind spot names.

On DunneNote, four `LOST_EDGE` on `self.m()` through `pub` traits with several
implementations, which `BACKLOG.md`'s residues say why.

**Ten earlier findings, found the same way, were this tool's and are fixed.** On pdfcraft,
before 4a:
- three `LOST_EDGE` through a sealed trait's one default;
- one `LOST_EDGE` on three nested `fn walk`;
- a `NO_TIMEOUT` doubled by `.map_err`;
- three tables minted from MCP tool descriptions;
- a CRYPTO touch on a local `bool` called `rsa`.

On DunneNote, a `NO_TIMEOUT` on `connect_timeout`. Then 17 whole test-module files read as
production code, which was half pdfcraft's `DEAD_CODE` list. `LANGUAGES.md`, *A sixth
reader*, says what each taught.

**The unknowns are what a path cannot say, and every one says so.** A method on a value whose
type the source never writes down, a call through a closure or a function pointer, a
`macro_rules!` expansion: each carries `calls.reason` (*untyped*, *bound*, *unfollowed*)
rather than an edge guessed by name.

### The Tauri crossing on DunneNote (chunk 5, 2026-11-01)

At `rust-reader` 8881fc2, on the Mac, `analyze ../DunneNote` says
*commands by name: 179 sites send one (179 linked by name to a command); 167 commands,
167 registered*. Every figure was checked against the source:
- **Commands: 167.** The current app has 122 `#[tauri::command]` in
  `apps/desktop/src-tauri/src/lib.rs` and 122 names in its `generate_handler!`; legacy v0.1
  has 45 under `crates/app/src/ipc/commands/`. DunneNote's own comments say "113 commands"
  (`lib.rs:2416`) and "105" (`pl/client.ts`). **Both are stale**: grep finds 122 attributes
  and 122 registrations, and so does the map.
- **Sends: 179, all linked.**
  - 135 go from `apps/desktop` to `apps/desktop/src-tauri` and 44 from `legacy/v0.1` to its
    own crates.
  - None crosses between the two applications, though three names (`add_photo`,
    `get_blob_bytes`, `open_or_create_notebook`) are commands in both.
  - The carriers are `pl/client.ts:call` and `legacy/v0.1/src/lib/ipc.ts:call`.
- **Commands no client sends: 8, each grepped across the front end.**
  - Six appear nowhere.
  - `set_item_meta` appears only in `search-store.test.ts`.
  - `rebuild_search_index` appears only as a field of the health plan's object, never sent.
  - None is a missed link.
- **Findings:** no UNREGISTERED_COMMAND or UNKNOWN_COMMAND, which matches the above. Still
  0 broken and 4 suspect.
- **`08-network.md`** places the 135 in the `dunnenote` process and the 44 in `calnote`, by
  the registrar. That needed the reader to honour `[lib] name` (b932594), without which
  `main` reached nothing.

**Neither tree is on maclab or GIZA**, so these figures are the Mac's. The suite runs there,
and those machines prove the reader builds and reads; they do not retake these numbers
(rule 24).

## Java: spring-petclinic and traccar, and what each reproduces (2026-11-02)

**Neither is Society, and both are public.** Cloned at depth 1 into `../`, read-only, with
Tom's leave on 2026-11-01: `../spring-petclinic` at **500158f** (2026-09-29), Spring MVC and
Spring Data JPA, 30 program files and 20 tests; and `../traccar` at **f941c40**
(2026-11-01), a GPS tracking server on Netty, Guice, JAX-RS and JDBC, 1,059 program files
and 430 tests. Neither has its dependencies on this machine: there is no `~/.m2`, and the
Gradle cache holds 58 modules, none of theirs. `../Android/sources/android-37.0` (16,403
files) is the scale probe and is not a program.

```bash
uv run dunneflow analyze ../traccar          --name traccar   --output <tmp>
uv run dunneflow analyze ../spring-petclinic --name petclinic --output <tmp>
uv run dunneflow check   ../traccar          --name traccar   --output <tmp> --all --verbose
```

At `java-reader` 21810a9, JDK 21.0.5, on the Mac:

| | petclinic | traccar |
|---|---:|---:|
| `.java` files read / left out as tests | 25 / 20 (5 `package-info.java` skipped) | 1,059 / 430 |
| Java edges supplied, every one matched to a routine by its first line | 76 | 28,077 |
| built one of the program's own types (`calls.constructs`) | 5 | 539 |
| several declarations — no edge | 0 | 284 |
| outside / could not resolve | 63 / 109 | 7,970 / 16,220 |
| dispatched calls / the bodies they may reach | — | 749 / 2,180 |
| ways in | 21 (17 routes, `main`, 3 `@Bean`) | 106 |
| boundary touches | **0** (Spring Data, BACKLOG 45) | 277 (218 NETWORK, 2 DATABASE) |
| dependencies spelt, not on this machine | 17 | 62 |
| findings | 0 broken · 0 suspect · 1 informational | 0 broken · 23 suspect · 6 informational |

**Every SUSPECT left on traccar was read against the source.** Twenty-two `LOST_EDGE`, each
dispatch the rule correctly calls `dynamic` and the finding now says so: the abstract
`decode` with 271 implementations, `sendMessage` with two (`RedisBroadcastService`,
`MulticastBroadcastService`), `getDeviceSession` overridden in `BaseMediaProtocolDecoder`. One
`NO_TIMEOUT`, at `PositionForwarderWialon`'s `new DatagramSocket()`, which is right about
the Java site; the other seven remote calls it counts are traccar's Python tools.
`LOOPED_BOUNDARY` is a real alarm reply written on every pass of a record loop
(`ProgressProtocolDecoder:156`). `DEAD_CODE`'s six are test-only helpers, correctly listed.

**Thirty-seven earlier findings were this tool's, and are fixed** (`LANGUAGES.md`, *A seventh
reader*): five `LOST_EDGE` whose second definition was a sibling class's override, which
can never answer the receiver; twenty-four `DEAD_CODE` that were Guice's `@Provides`; three
that were called through a Netty-typed argument javac could not see; and, the one no finding
showed, about 2,000 edges javac had chosen among overloads it could not tell apart.

**UNREACHABLE is 2,946 of 4,296 with the dispatch arm, from 3,575 without.** 1,968 of the
remaining are under `protocol/`: traccar finds its protocols by scanning a package and has
Guice build them, which no static reading follows (`BACKLOG.md`'s residues).

**Society still reads 7 of 7** against `output/GOLDEN-v2.txt` at 21810a9, and the ordering
probe passes on traccar's map and its `--api`.

## The screenshot map — what `docs/` and `docs/tutorial/` were photographed against

**Every figure in the user guide and the tutorial is one this map reproduces**, so a retake
rebuilds it rather than rediscovering it. Taken 2026-10-02, on a map of a **clean clone** at
`2cdd872` analysed by release 8, the installed build of that commit, and photographed through
releases 8 and 9 (`0cd81cd`), which read the same maps — all five stamps agree. The shots of
the analyse dialog and the Settings page (`04-*`, `13-*`, `03-opening`, `15-refuse-relative`)
hold no figure these maps decide and were kept from the previous retake, against `5b737a0`.
The clone is required: the working
tree holds `CLAUDE.local.md` and `output/`, which the documentation scan would read as
DunneFlow's own corpus and print into the screenshots.

Three revisions, oldest first. The two sealed ones come from worktrees at the parent of a
named commit, so they can be rebuilt from history:

```bash
git worktree add ../dunneflow-before-parts   7665d66^    # 0804aa7
git worktree add ../dunneflow-before-windows 290c39b^    # 1017ef4
git clone . ../tour/DunneFlow && git -C ../tour/DunneFlow checkout 2cdd872

dunneflow analyze ../dunneflow-before-parts/src/dunneflow --name dunneflow --output ../tour/maps
dunneflow revisions ../tour/maps/dunneflow --seal --label "DunneFlow at 0804aa7 - before parts"
dunneflow analyze ../dunneflow-before-windows/src/dunneflow --name dunneflow --output ../tour/maps
dunneflow revisions ../tour/maps/dunneflow --seal --label "DunneFlow at 1017ef4 - before the Windows fix"
dunneflow analyze ../tour/DunneFlow/src/dunneflow --name dunneflow --output ../tour/maps \
    --standards ../dunnecorp-standards
```

The last analysis must reproduce **142 files · 53,988 lines · 1,552 routines · 3,315
internal calls · 526 boundary touches · 207 structures · 24 ways in**, findings 0 broken,
21 suspect and 18 informational, and 53 documents. Each figure moves with the source, so a
retake at another commit writes new figures rather than matching these. The tutorial's
chapter 8 compares *before the Windows fix* with the working revision; guide chapter 14
compares *before parts*.

The same root also holds `fastapi`, `djangoproject.com` and `OpenUSD`, analysed from
`../fastapi`, `../djangoproject.com` and `../OpenUSD`, so that the start page and the program
menu have neighbours. OpenUSD is the long run in guide chapter 4: long enough cold through
`serve` to photograph the steps and **Stop it**, at 80.5 s on this machine at `5b737a0`. The
quiet warning needs a run that goes quiet for longer than that one ever does, so
`04-progress-quiet.png` is kept from an earlier retake, taken when the same run took about
four minutes. Serve with `dunneflow serve ../tour/maps --port 8787 --no-open`.
How the captures were composed (window size, framing, the native menus that cannot be
photographed) is in the retake's record.
