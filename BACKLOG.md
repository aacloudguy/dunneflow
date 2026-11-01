# Backlog

**What this tree knows it owes, in one place.** The fourteen chunks of v2's design plan are
all done, so nothing here is scheduled by the plan — every item is something a chunk found,
stated, and deliberately did not do. Until 2026-09-17 they lived scattered across the
development record's *What is next* and a dozen **Residue** sections, which meant the only
way to know what was outstanding was to read the whole record.

**Every item says where it came from, why it was not done, and what would settle it.** An
item with no *what would settle it* is a complaint rather than a task, and an item whose
*why not* is missing is one somebody will redo the argument for.

**This file is not the record.** The development record, kept outside this repository, says
what happened and when; this says what has not. When an item is done it leaves here and the record keeps it.

---

## Open

Nothing from before 2026-11-01: every older item was closed on 2026-10-02 or moved to the
residues below. These came out of the Go and Rust readers, and each says what would settle
it. (30,
Go on the build machines, was settled the same day: Go 1.25.6 on both, and the suite green
on each.)

**31. The tour maps and screenshots predate the Go and Rust readers.** DunneFlow's own tree
now holds the Go reader's seven `.go` files and the Rust reader's `.rs` files (its `vendor/`
is pruned), so a self-map reads `python · typescript · go · rust`, and the
figures the guide was photographed against (`python 131 · typescript 11`, chapters 1 and 4)
move. Not done because a retake is its own session with its own record. *Settled by* the next
retake, with `GROUND-TRUTH.md`'s screenshot-map figures rewritten from it.

**32. A dependency is an empty stand-in, so methods on its types are *unknown*, not
*outside*.** Measured: rain's 628 unknown calls are mostly cobra's `Cmd.Flags()` and
friends. Not done because reading a dependency means finding it, and the honest place is the
local module cache (`go env GOMODCACHE`, pinned by `go.sum`), read only where it is already
present, never fetched (design rule 14). *Settled by* a reader that consults the module cache
when it exists, with the unknown count retaken on rain and beads.

**33. Cobra's command tree is not drawn.** A group (`rain cc`) is correctly not a way in, but
the `AddCommand` calls that hang commands under it are not read as `cli_mounts`, so the CLI
tree is flat. Not done because it is a second fact kind for a reader one day old. *Settled by*
`AddCommand` read as a mount and resolved like Python's, and `cli: … (n in a tree)` above
zero on rain.

**34. Built readers are never pruned.** `runtime.reader_cache_root()` gains a directory per
stamp, platform and toolchain, and nothing removes the old ones: ten during the session that
built the Go reader, 3.4 to 3.6 MB each. Not done because nothing yet decides when a build is no
longer wanted. *Settled by* keeping the newest few per language, or the ones whose stamp a map
on this machine still holds.

**35. A table created twice in one file shows both sets of columns under each definition.**
`db_columns` is keyed on `(tbl, file)` and holds no line, so DunneNote's migrations — which
`CREATE TABLE` one table twice in one file as the schema moves — list the union of both
column sets beside each `CREATE`. Found by `tools/ordering.py` on 2026-11-01, as a tie the
Rust reader's SQL literals were the first to reach (rule 98); the tie is closed and the
attribution is not. *Settled by* a `line` on `db_columns`, written by `ingest/literals.py`,
and `render/database.py` asking for the columns of one statement.

**36. Only the Rust reader says where its calls stop.** `calls.frontier` and `calls.reason`
(schema 17) are filled by Rust alone, so *About this map* says *3,608 more whose reader does
not say* of DunneNote's TypeScript, and every Python, Go and C++ map says nothing. Not done
because each reader knows different things: TypeScript's checker names a far end's
declaration file, Go's names its package, Python's resolver knows the import it stopped at.
*Settled by* each reader sending `frontier`/`reason` on its unresolved calls (Python's
through `NoEdge`, which already carries both), with the unsaid count retaken per corpus.

**37. `--include-tests` does not bring back Rust's inline tests.** The walk leaves test
*files* out unless asked; the Rust reader leaves `#[cfg(test)]` items out always, because
nothing tells a reader the flag and the cache key does not carry it (rule 81). 159 items on
DunneNote. *Settled by* the flag reaching `open` and joining the per-language stamp, so a
run with it and a run without it cannot share a cached file. **Narrowed 2026-11-01
(3369fdc): this is inline items only now.** A whole file that a `#[cfg(test)] mod x;`
declares is named by the edge pass and left out by the host, which does know the flag, so
`--include-tests` reads those.

**38. Bare common method names are still in four rules files (rule 5).** `replace` was
taken out of `python.yaml`'s FILE rule on 2026-11-01 after it made 175 FILE boundaries in
Society, mostly strings. The same survey found more, each unmeasured:
- `kotlin.yaml`: `insert`, `update`, `delete`, `query` (DATABASE) and `exists` (FILE).
- `typescript.yaml`: `rm`, `remove`, `rename`, `mkdir`, `truncate`, `stat`, `access`,
  `exec`, `spawn`, `fork`, `subscribe`, `publish`, `aggregate`, `upsert`, `transaction`,
  `groupBy`.
- `python.yaml`: `glob`, `exists`, `stat`, the queue words, and the logging levels.

Not done because each needs its own measurement on a tree that uses it: taking one out
blind trades a false row for a missing one. *Settled by* diffing boundaries before and
after on Society, DunneNote and a Kotlin tree, and reading every lost row, as the 4d commit
did.

**39. A language whose `private` is not measured is not said to be.** `private_means:
surface` (Rust, Kotlin, C++) leaves the naming lane's LEAKAGE claim out for that language,
correctly, and nothing on the page says it was left out (design rule 1). pdfcraft's naming
report simply has no privacy line. *Settled by* `NamingMeasurement` carrying the languages
not measured, with the reason from the rules file, and the three surfaces (CLI, the
`naming.md` page, the Vocabulary lane) saying it.

---

**40. A command no client sends is not reported.** DunneNote has 8, and each was read
against the source (`GROUND-TRUTH.md`). That is dead code by another route, but it is not a
`DEAD_CODE` finding, because an `IPC_COMMAND` is a way in. Not built, because its blind spot is
large: a client in a language this build does not read, a test, or a second front end outside
the tree. *Settled by* Tom deciding whether an INFO finding with that blind spot is wanted.

**41. *About this map* says "Inferred facts: none" directly under "matched by name".** Design
rule 28's *inferred* is a provenance tier: a fact guessed by a model, of which there are
none. A link matched by name is `Confidence.INFERRED` in the sense Python's by-name edges
have always been. Read quickly, the two rows contradict each other. *Settled by* Tom
choosing between leaving it, adding a clause to the vow ("a call or command matched by name
is labelled where it is shown"), or rewording one of the rows.

**42. The second recursive arm's cost on a large map is unmeasured.** Every reach query now
also joins `ipc_links`. That table is empty on every map but DunneNote's, and a read-only
store walks in memory, so the cost is expected to be small. Nobody has timed it (rule 24).
*Settled by* timing `touches` and the cover on Unreal's Runtime part, before and after
f61514d.

## Stated residues — known, bounded, and not defects

These are not tasks. They are places where the honest answer is a limitation, recorded so
that nobody spends a session rediscovering them and filing them as bugs.

| | |
|---|---|
| **`node` is needed to verify the TypeScript stamp** | `tools/fingerprints.py` reads the stamp out of a map the binary *wrote*, which is what proves the stamp labels rows rather than merely being computable (rule 37). A machine without node gets a refusal naming it. Chunk 13. |
| **`GOLDEN-v1.txt` redefines two of its seven digests, and is history now** | `routines.body` and `calls.resolved` record values whose v1 statement was never written down and was not recovered by a bounded sweep (rule 24, chunk 0). It stopped mattering on 2026-09-19: rule 106 moved all five of the digests that *did* reproduce, so the live baseline is `output/GOLDEN-v2.txt`, `tools/golden.py` wrote both sides of that comparison, and it is **7 of 7** with no holdbacks. The v1 report is kept as a dated record and compares for five, all of which now move. |
| **`GOLDEN-v2.txt` was retaken on 2026-11-01, from main** | `calls.resolved` had moved on main at 58af95a (2026-10-02, `Foo()` binds to `Foo.__init__`, BACKLOG 14), which recorded the move and did not rewrite the report. The retake is from main at b2c4882 with `--standards`, and its graph is kept at `output/golden-v2-graph/`. The old report is `output/GOLDEN-v2-2026-09-19.txt`, unedited. |
| **A Python `Path` held in a name is not a FILE when it is replaced** | `tmp.replace(target)` is how Society writes 22 files atomically, and with `replace` gone from the bare methods (rule 5) those are not seen; `Path(p).replace(q)`, `pathlib.Path.replace` and `os.replace` are. What a name holds is a type, and Python's reader has none. |
| **A timeout set on the client is not read, in Go or Rust** | `network.timed` reads a timeout passed to the call (`net.DialTimeout`, `TcpStream::connect_timeout`). One set on the object — `http.Client{Timeout:}`, `net.Dialer{Timeout:}`, `stream.set_read_timeout(…)` — is not, which is NO_TIMEOUT's own blind spot, and the finding says so. beads reads 5 of 12 for that reason, and pdfcraft 1 of 1. |
| **A `pub` trait's dispatch stays ambiguous in Rust** | `self.m()` in a default body, `dyn T` and a bound type parameter resolve when `T` is sealed (no `pub`) and one definition answers. A `pub` trait with one implementor here does not, because another crate may write the override. DunneNote's four LOST_EDGE and pdfcraft's six are all this or a genuine choice between two impls. |
| **DunneCorp's routines are two conventions by role** | PascalCase 88 against camelCase 79 — React components against ordinary functions. A language split does not touch it, and it stays a reported gap because that is the true answer. Open question 6. |
| **DunneNote's modules stay a gap** | kebab 221, other 210. That tree really does spell module files three ways. Open question 6. |
| **Next.js route segments read as `other`** | `app.(admin).admin.customers.[id].page`. Route syntax is not an identifier and stripping it would be guessing at a spelling. Open question 6. |
| **Python's leading-underscore classes drag PascalCase to a `D`** | `_Base` and `Exception_`, 15 of DunneFlow's 164. Answered on 2026-10-02 as a Setting rather than a rule (*A leading underscore in a name*, and `naming --allow-leading-underscore`): strictly a violation, and allowed where the reader says so. `Exception_` and its kind stay exceptions either way. Open question 6. |
| **A Linux session cannot run the recorded ground truth** | None of the four Society clones nor `../dunnecorp-standards` is on that machine, so no figure in `CLAUDE.md` was retaken there. Do not restate a Mensores figure measured elsewhere as though it had been reproduced (rule 24). |
| **A program that serves browser JavaScript as a string has calls this map cannot see** | `gstack`'s `getCookiePickerHTML(): string` returns an HTML page holding four `fetch` calls, and `design/src/compare.ts` another. Those requests really are made — from the browser, by code this program wrote — and the map says nothing about them. Correctly: a string is not code, which is rule 9's argument one direction over, and reading one would mean parsing every template literal in every language. Stated so the NETWORK count is read as *what this program calls*, never *what this program causes*. 2026-09-18. |
| **`socket.emit` may be wrongly declared async** | `detectors/typescript.yaml` says `async: true`; `emit` is fire-and-forget in socket.io and `emitWithAck` is the awaitable one, so it is probably wrong beside `WebSocket` and `EventSource`, which were corrected. Left alone because **no map this tool has read holds a single `socket.emit`** and socket.io's types are in no corpus here, so there is nothing to check a change against. Asserting it from memory is what rule 24 forbids. 2026-09-18. |
| **Rule 105's survey is a floor, not the population** | `tools/ordering.py --survey` lists the five `sorted()` calls whose input is *written as* a set and which take a `key=`. Unorderedness propagates, so a dict built by iterating a set and then sorted over its `.items()` is the same defect and is invisible to it — `web/changes.py` held two of each, and only the two written as set algebra are in the count. Catching the rest means following the provenance of a value, which is a different instrument. The reversal probe cannot see any of them. 2026-09-18. |
| **A killed analysis can leave its pool behind** | Nine `ProcessPoolExecutor` workers from the original Unreal ingest were still alive 22 hours later, parented to init, idle at 5.5 MB each. Harmless where they are, and the 86-part re-read on 2026-09-20 added none — so it is an interrupted run's leak rather than an ordinary one's. Stated because a batch runner doing this nightly would accumulate them, and the batch-ingest design is the place that would have to care. 2026-09-20. |
| **The size guard counts files and nothing else** | `walk.TOO_BIG` is 20,000 *files*, which is the shape of the evidence — `Engine/Source/Runtime` is 18,191 and is the largest tree read end to end. A tree of 19,000 enormous files passes it and a tree of 25,000 tiny ones is refused, and neither is what the bound is really about: the thing that hurts is rows written, not files read. Bytes or an estimate of rows would be the honest key, and taking one needs a corpus spread wide enough to separate the two — which is a measurement, not an edit. Stated so the number is read as what it is. 2026-09-19. |
| **A part's documents are whatever is under its root, vendored prose included** | Unreal's 86 parts hold **12,886 documents, and 11,850 of them are `Engine.Source.ThirdParty`'s**: a part of 620 code files on 57,373 files of vendored library source, which the C++ reader skips by name for code. Every other part is in double or single figures. Tom's decision, 2026-10-02: vendored prose **is** documentation of the program, so it is read. Design rule 11 holds as written, and a reader's `skip_dirs` stays a statement about program source and never about prose. Measured with `analyze --timings` on 2026-09-20; formerly BACKLOG 9. |
| **A Go function defined per platform is drawn to its linux/amd64 definition** | Tom's decision, 2026-11-01. Each package is checked under linux/amd64, darwin/arm64 and windows/amd64; where they name different definitions the edge goes to the first, and its `how` counts the variants (38 on beads). The other platforms' versions read as uncalled. Ambiguous was the plan's answer and cost 16 false LOST_EDGE SUSPECT on beads. |
| **A Go call through a renamed standard-library import is not a boundary** | `import stdos "os"` then `stdos.Getenv` is not matched, because rules match the spelling written and a reader never expands an alias (rule 4). Rare, since `goimports` never renames. Stated in `detectors/go.yaml`. |
| **`f[MyType]()` records no call name in Go** | `x[y]` is a type argument or a subscript and only the checker can always tell; the reader answers *type* only where the index cannot be a value, so a call instantiated with a named type is left unnamed for rule matching. Its edge still comes from the checker. Stated in `extract.go:looksLikeType`. |
| **`plugin.json`'s `workers` is read and used by nothing** | Every manifest declares it and no reader is started more than once. Found writing the Go manifest; harmless, and a field nothing reads is rule 35's shape, so it is stated here rather than relied on. |
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
