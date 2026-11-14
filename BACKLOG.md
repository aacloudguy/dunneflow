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
residues below. These came out of the Go, Rust and Java readers, and each says what would settle
it. (30,
Go on the build machines, was settled the same day: Go 1.25.6 on both, and the suite green
on each. 31, the tour maps and screenshots, was settled by the retake of 2026-11-13 and 14:
`GROUND-TRUTH.md`'s screenshot map says what it was taken against.)

**32. A dependency is an empty stand-in, so methods on its types are *unknown*, not
*outside*.** Measured: rain's 628 unknown calls are mostly cobra's `Cmd.Flags()` and
friends. Not done because reading a dependency means finding it, and the honest place is the
local module cache (`go env GOMODCACHE`, pinned by `go.sum`), read only where it is already
present, never fetched (design rule 14). *Settled by* a reader that consults the module cache
when it exists, with the unknown count retaken on rain and beads.

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
Comitia, mostly strings. The same survey found more, each unmeasured:
- `kotlin.yaml`: `insert`, `update`, `delete`, `query` (DATABASE) and `exists` (FILE).
- `typescript.yaml`: `rm`, `remove`, `rename`, `mkdir`, `truncate`, `stat`, `access`,
  `exec`, `spawn`, `fork`, `subscribe`, `publish`, `aggregate`, `upsert`, `transaction`,
  `groupBy`.
- `python.yaml`: `glob`, `exists`, `stat`, the queue words, and the logging levels.

Not done because each needs its own measurement on a tree that uses it: taking one out
blind trades a false row for a missing one. *Settled by* diffing boundaries before and
after on Comitia, DunneNote and a Kotlin tree, and reading every lost row, as the 4d commit
did.

**42. The second recursive arm's cost on a large map is unmeasured.** Every reach query now
also joins `ipc_links`. That table is empty on every map but DunneNote's, and a read-only
store walks in memory, so the cost is expected to be small. Nobody has timed it (rule 24).
*Settled by* timing `touches` and the cover on Unreal's Runtime part, before and after
f61514d. *Part measured, 2026-11-02:* the dispatch arm (a third arm, `dispatch_links`) made a
**writable** store's recursive query sixteen times slower on traccar (`ways_in` 0.3 s →
4.8 s), because the query deduplicates on `(id, depth)` and fan-out multiplies the paths. A
writable store now walks in memory too, its cache stamped with `total_changes`, and the same
`ways_in` is 0.20 s; the in-memory walk itself is 27 ms over traccar's 105 ways in. Unreal is
still untimed.

---

**47. A Kotlin file in a Java tree is a missing class to javac.** A call from Java into
Kotlin is `untyped`, and a call from Kotlin into Java has no edge at all (the Kotlin reader
supplies none). anki-android is all Kotlin and no corpus here mixes them. *Settled by* a
mixed tree to measure, then deciding whether the Kotlin reader's declarations are handed to
javac as a classpath stub.
**Tom's decision, 2026-11-07: find a public mixed Java and Kotlin tree first**, measure it, and
decide the stubs from what it shows.

---

**49 to 64 came out of the documentation audit of 2026-11-14**, taken at `4f5d0f2`, the head
0.3.0 was released from. Every document and every comment outside the fingerprinted files was
read against the code; where they disagreed the prose was changed to say what the code does,
and what is left here is where the code is the half that is wrong or missing. Each says how
far it was checked: *read* means the lines were read and the defect follows from them,
*reproduced* means it was made to happen. The auditors' full lists are in the development
record under that date.

**49. The product describes itself as it was.** Sentences a reader meets on screen or in a
written map, each true when written. None was changed, because a string is product and tests
read them. *Settled by* rewording each and retaking any picture that shows it.
- **"stdlib parsing" and "with the standard library".** The start page's footer
  (`start.html`) and *About this map* (`aboutVow` in `shell.js`) say every fact was read with
  the standard library. That is the Python reader; the others are the TypeScript compiler,
  `go/types`, `syn`, javac and libclang. The guide's chapter 3 quotes the footer.
- **PARSE_ERROR's blind spot says "The file is not valid Python"** of a file in any language
  (`anomalies.py`), in the module the above-the-graph guard holds to naming none.
- **`11-naming.md` says "a standard of your own cannot yet be imported"** on a map made with
  `analyze --standards`, whose own *Checked* section is that comparison; and it tells the
  reader to run `dunneflow infer`, which is not a command (`render/naming.py`). It and the
  glossary's provenance table describe CITED and INFERRED tiers as though a model pass
  existed.
- **Settings descriptions quote one program's figures about whichever is open**: "4,734
  routines", "the same 105 findings … 93 suspect", "nine thousand nodes on fifty-two plates",
  "335 of 1,395 rows"; so do the plate-layout tooltip ("91.7% fewer crossings") and the arrow
  pane's foot ("92% of arguments on a resolved call bind").
- **The *Unfinished maps* row speaks of "a reset of this program"**; `resetSettings` exists
  and nothing calls it.
- **Smaller ones**: *Scroll change bands in place* names four headings where the page draws
  more; the table's footer waits for "a routines endpoint", which exists; LOOPED_BOUNDARY's
  title leaves out local IPC, which it reports; the Shape lane *match statements* holds
  `switch` and `when`; `08-network.md` says hops are "thick dashed arrows" and draws them
  solid; `13-mirror.md` says every count comes from the SQL printed, which covers three of
  its surfaces; the 409 sentence says the server "was started on an output root" after a
  close on one that was not; "is being analysed already, from a terminal" is said of a run
  another server started; the accessibility panel names Mermaid where Graphviz draws.
- **Help and refusals**: `render --include-tests` ("as `analyze` does") changes only
  dead-code wording; `--output`'s help gives the platform default where a packaged build
  uses the reader's chosen root; the sidecar's "run `dunneflow revisions --seal`" leaves out
  the directory; `tools/fingerprints.py --tree` says the probe "holds both languages";
  `ingest/codec.py`'s host-owned refusal says "the language" of `Entrypoint.declared`;
  `ingest/worker.py` says "the only answer to a handshake is `ready`" five lines under
  accepting `declined`; `plugins/typescript/build.mjs` says "run pnpm install" in a tree
  whose lockfile is npm's. The last three are fingerprinted (item 63).

**50. A written map's cover links ten of its sixteen pages.** *The rest of the map* in
`README.md` (`render/markdown.py`) lists 01 to 09 and 15; `10-glossary`, `11-naming`,
`12-traceability`, `13-mirror` and `14-constants` are reachable only by knowing their names.
Read. *Settled by* building the list from `PAGE_NAMES`, and a test that every page is linked.

**51. *Declared tables* counts no reads and no writes.** `DOC_DB_TABLES` in
`web/queries.py` compares `direction` with `'read'` and `'write'`; the store holds `READ` and
`WRITE` (`sql.py`), and every other query in that file spells them so. Read, not run on a
map. *Settled by* the two literals, and a test on a fixture with one of each.

**52. One server cache outlives the program it was built for.** `_Live.relaxed` holds the
macro report and the underscore-relaxed naming lanes under `(revision, lane)` and is in
neither `PROGRAM_CACHES` nor `COMPARISON_CACHES` (`web/serve.py`). Two programs with no
revision both key `""`, so a switch could serve the first one's report for the second, which
is the collision `switch_program` gives as its reason for clearing `findings`. Read, not
reproduced. *Settled by* adding it to `PROGRAM_CACHES` with a test that switches.

**53. Small defects in the dashboard, each read off `shell.js`.**
- The spacing slider is not saved on release: the `change` handler lists `gsize`, and the
  control has been `gspacing` since it was renamed.
- Sorting the table by *Changed* puts *explained differently* under *unchanged*:
  `CHANGE_WEIGHT` has no weight for it.
- Structure bands keep a fixed red and green when the reader turns "which is newer" round;
  routine bands follow `diffWords()`.
- `selectedLine` matches a file by suffix, which `followSelectionIntoCode` stopped doing
  because `cli/audit.py` also ends `/audit.py`.
- Usage bars are scaled against a pinned 68.
- `setGraphDetail` pushes onto `window.__lvl`, which nothing reads; `state.colourBy` and
  `g.coupled` are declared and unread; `.scale-group button` styles buttons that are gone.
- **A running analysis cannot be put aside.** The panel offers *Stop it* alone, and
  `analyze.js` still calls it dismissible. The guide's chapter 4 now says what happens.
- **A compared pair does not survive a restart of the server.** The base goes back to the
  newest version unless `--revision` is given; the page says what was being read. The
  guide's chapter 14 said it survived and now does not.
*Settled by* each in turn; the last two are decisions before they are edits.

**54. Diagram mode, five things read and one probed.** A crossing's weight is doubled,
because `web/graph.py` holds each cross-plate edge twice and `diagram.build` adds both (a
hand-built case turned 3 into 6; not confirmed on a map). `role_none` and `unlinked`
disagree where a way in enters an otherwise isolated box. The Mermaid export always carries
ports and the drawing omits them by default. `flow_of` leaves ways in out of a box's *in*
list. A `<module>`'s calls and touches are in no box and no count says so (design rule 1).
*Settled by* a fixture with ways in, which the test that promises agreement builds without.

**55. Two manifest providers misreport their own refusals.** Reproduced by calling them.
`swiftpm.read` reports `.executable(name: "tool")` as an entry *and* as "refused 1
.executable product whose name is not a string literal": the lookahead backtracks over the
space before the quote. `gradle.read` says nothing of a computed `mainClass` when a literal
one is also present, because it subtracts the literals from a count that never held them.
*Settled by* the two expressions and a fixture written the usual way.

**56. The `macros` tool cuts its answer without saying so.** Its description promises
"every definition" of a named macro; the body returns the first five with no total, takes a
negative `limit` as a slice from the end, and raises `ValueError` rather than a refusal on a
non-number (`mcp/tools.py`). `find` ignores `limit` when `file` is given. Read. *Settled by*
`_limit()` and a `more` count, as the other tools have.

**57. The Kotlin reader does not keep three terms `schema.py` states.** A control point's
id is minted from its **line** (`extractors/kotlin/control.py`), where the contract says
names and an ordinal and never a position, so every point below an inserted line changes
identity. `exits` is filled for every kind and may hold `throw`; an arm's header is written
as `"else"` and `"try"` where the contract says empty. And it records **one boundary per
matching rule** where `match_call` says the first wins (rule 40's shape), applies its own
literal floor with no ceiling, and its `RESIDUE`, "a deliverable", is read by nothing and
ends mid-sentence. Read. *Settled by* `control_point_id` and `match_call` in that reader,
measured on anki-android before and after. It moves Kotlin's stamp.

**58. What Rust's and TypeScript's edge passes have to say reaches nobody.** Both write
their notes to stderr and send no `notes` on `edges_done`, which Go and Java do and the host
reads (rule 38). So "N .rs file(s) are no crate's module and are read as crates of their
own" is never shown. Read. *Settled by* the key in both readers. It moves both stamps.

**59. ONE_WAY_TABLE reports a query's own names as tables.** Seven of the thirteen on
DunneFlow's own map are CTE names and SQLite's `json_each`, which the tutorial's chapter 9
shows as this tool's defect. Beside it: a statement assembled by concatenation yields no
`sql_ops` rows at all, which is why one such finding "went away" between two snapshots with
nothing fixed. Reproduced on the tour map. *Settled by* leaving out names a `WITH` binds in
the same statement and table-valued functions, and by recording that a statement was built
at run time rather than read.

**60. A named pipe is not LOCAL_IPC.** No rules file knows `mkfifo`, `CreateNamedPipe` or a
`\\.\pipe\` path; the 0.3.0 changelog said it was and has been corrected. *Settled by*
rules per language, measured on a tree that uses one.

**61. A program directory holds the path it was read from.** `analysis.json`
(`runstate.py`) records the command line and the absolute tree, in the directory `README.md`
calls built to be handed over. Both documents now say so. *Settled by* deciding whether a
hand-over strips it, relativises it, or is told to leave the file behind.

**62. Two stores opened to be read can be written to.** `SourceStore` and `DocStore` call
plain `sqlite3.connect` with `writable=False`, the hole `Store` closed with `?mode=ro`
(rule 20); and `changes._attach` writes its read-only URI by hand where
`store.read_only_uri` exists because `?`, `#` or `%` in a path breaks that spelling. Read.
*Settled by* opening all three through `read_only_uri`.

**63. Some fifty comments in fingerprinted files describe a tool that has moved on.**
`schema.py`, `sql.py`, `ingest/`, `detectors/`, `extractors/` and `plugins/` were read and
not edited, because their bytes are in every stored map's stamp and a corrected comment
would cost every user a re-analysis. Typical: `main.bundle.mjs` for `main.bundle.cjs`;
`rules_fingerprint()`, `_scan_sql` and `_extract_one_cpp`, none of which exists; "the other
three languages"; `cpp.yaml` and the C++ reader's headers describing the retired syntactic
reader; `go.yaml` saying Cobra's tree "is not drawn yet" seven lines above the key that
draws it; `python.yaml` calling `print` low-salience where its rule says normal. Beside
them, about twenty-five comments elsewhere that are true and sit on the wrong function. The
list, with the wording proposed for each, is in the development record. *Settled by*
applying it in the first release that moves the core stamp anyway; 57 and 58 are two.
Two belong with it and are behaviour: `extractors/docs/markdown.py` says unreadable
frontmatter "is recorded by the caller" and records nothing, and `_unclaimed_marks` counts
with one `LIKE` and prints another beside the figure (rule 13).

**64. `ARCHITECTURE.md` has no entry for two of the seven readers.** TypeScript, Go, Rust
and Java each have their paragraphs; C and C++ on libclang and Kotlin have none, the
pipeline drawing at the top shows two languages, and twenty-six routes `serve` answers are
named nowhere in it. Not written during the audit, which corrected and did not add. Beside
it, design rule 8 gives every node one of `ANALYZED`, `KNOWN_INTERFACE` and `OPAQUE`, and
only `OPAQUE` exists in `src/`. *Settled by* the two entries, and a decision on rule 8:
build the status, or say in the rule what was built.

## Stated residues — known, bounded, and not defects

These are not tasks. They are places where the honest answer is a limitation, recorded so
that nobody spends a session rediscovering them and filing them as bugs.

| | |
|---|---|
| **`node` is needed to verify the TypeScript stamp** | `tools/fingerprints.py` reads the stamp out of a map the binary *wrote*, which is what proves the stamp labels rows rather than merely being computable (rule 37). A machine without node gets a refusal naming it. Chunk 13. |
| **`GOLDEN-v1.txt` redefines two of its seven digests, and is history now** | `routines.body` and `calls.resolved` record values whose v1 statement was never written down and was not recovered by a bounded sweep (rule 24, chunk 0). It stopped mattering on 2026-09-19: rule 106 moved all five of the digests that *did* reproduce, so the live baseline is `output/GOLDEN-v2.txt`, `tools/golden.py` wrote both sides of that comparison, and it is **7 of 7** with no holdbacks. The v1 report is kept as a dated record and compares for five, all of which now move. |
| **`GOLDEN-v2.txt` was retaken on 2026-11-01, from main** | `calls.resolved` had moved on main at 58af95a (2026-10-02, `Foo()` binds to `Foo.__init__`, BACKLOG 14), which recorded the move and did not rewrite the report. The retake is from main at b2c4882 with `--standards`, and its graph is kept at `output/golden-v2-graph/`. The old report is `output/GOLDEN-v2-2026-09-19.txt`, unedited. |
| **`GOLDEN-v2.txt` was re-adopted on 2026-11-12, on release-0.3.0** | One digest of seven moved, `calls.resolved`: 56 INFERRED edges lost, none gained, none retargeted, 7,032 internal calls to 6,976. `GROUND-TRUTH.md` has the table and the reason. The report of 2026-11-01 is `output/GOLDEN-v2-2026-11-01.txt`, unedited. |
| **A Python method named like one of Python's own is untyped on a bare receiver** | `allocator.discard(x)` and `store.update(row)` were drawn INFERRED to the program's only `discard` and `update`, and were probably right; so was `rows.append(x)` to the only `append`, 893 times, and wrong every time. The name-uniqueness tier no longer argues from any of the 90 names in `python.yaml`'s `builtin_methods` (rule 5), and about 10 true edges of 56 went with the false ones in Comitia. `self.discard()`, a base class and an import still resolve them. What a name holds is a type, and Python's reader has none. |
| **A C name the tree defines in another file is still the library's as well** | `opendir(path)` in git is libc's on this machine and `compat/`'s on another, and both bodies are in the tree. The C++ reader withdraws a boundary only where clang has the body in the same translation unit (2026-11-12: this tool's own `send`, 13 calls, and a parameter named `bind`). Across files it keeps both the edge and the touch: 102 calls in git, 13 in tmux, 31 in nmap on the maps of 2026-11-03, nearly all compatibility shims, where the touch is the true half and the edge is the other platform's body drawn uncalled. Telling the two apart needs the build's configuration, which a tree without `compile_commands.json` does not give. |
| **A Python `Path` held in a name is not a FILE when it is replaced** | `tmp.replace(target)` is how Comitia writes 22 files atomically, and with `replace` gone from the bare methods (rule 5) those are not seen; `Path(p).replace(q)`, `pathlib.Path.replace` and `os.replace` are. What a name holds is a type, and Python's reader has none. |
| **A timeout set on the client is not read, in Go or Rust** | `network.timed` reads a timeout passed to the call (`net.DialTimeout`, `TcpStream::connect_timeout`). One set on the object — `http.Client{Timeout:}`, `net.Dialer{Timeout:}`, `stream.set_read_timeout(…)` — is not, which is NO_TIMEOUT's own blind spot, and the finding says so. beads reads 5 of 12 for that reason, and pdfcraft 1 of 1. |
| **A `pub` trait's dispatch stays ambiguous in Rust** | `self.m()` in a default body, `dyn T` and a bound type parameter resolve when `T` is sealed (no `pub`) and one definition answers. A `pub` trait with one implementor here does not, because another crate may write the override. DunneNote's four LOST_EDGE and pdfcraft's six are all this or a genuine choice between two impls. |
| **DunneCorp's routines are two conventions by role** | PascalCase 88 against camelCase 79 — React components against ordinary functions. A language split does not touch it, and it stays a reported gap because that is the true answer. Open question 6. |
| **DunneNote's modules stay a gap** | kebab 221, other 210. That tree really does spell module files three ways. Open question 6. |
| **Next.js route segments read as `other`** | `app.(admin).admin.customers.[id].page`. Route syntax is not an identifier and stripping it would be guessing at a spelling. Open question 6. |
| **Python's leading-underscore classes drag PascalCase to a `D`** | `_Base` and `Exception_`, 15 of DunneFlow's 164. Answered on 2026-10-02 as a Setting rather than a rule (*A leading underscore in a name*, and `naming --allow-leading-underscore`): strictly a violation, and allowed where the reader says so. `Exception_` and its kind stay exceptions either way. Open question 6. |
| **A Linux session cannot run the recorded ground truth** | None of the four Comitia clones nor `../dunnecorp-standards` is on that machine, so no figure in `CLAUDE.md` was retaken there. Do not restate a Lictores figure measured elsewhere as though it had been reproduced (rule 24). |
| **A program that serves browser JavaScript as a string has calls this map cannot see** | `gstack`'s `getCookiePickerHTML(): string` returns an HTML page holding four `fetch` calls, and `design/src/compare.ts` another. Those requests really are made — from the browser, by code this program wrote — and the map says nothing about them. Correctly: a string is not code, which is rule 9's argument one direction over, and reading one would mean parsing every template literal in every language. Stated so the NETWORK count is read as *what this program calls*, never *what this program causes*. 2026-09-18. |
| **`socket.emit` may be wrongly declared async** | `detectors/typescript.yaml` says `async: true`; `emit` is fire-and-forget in socket.io and `emitWithAck` is the awaitable one, so it is probably wrong beside `WebSocket` and `EventSource`, which were corrected. Left alone because **no map this tool has read holds a single `socket.emit`** and socket.io's types are in no corpus here, so there is nothing to check a change against. Asserting it from memory is what rule 24 forbids. 2026-09-18. |
| **Rule 105's survey is a floor, not the population** | `tools/ordering.py --survey` lists the five `sorted()` calls whose input is *written as* a set and which take a `key=`. Unorderedness propagates, so a dict built by iterating a set and then sorted over its `.items()` is the same defect and is invisible to it — `web/changes.py` held two of each, and only the two written as set algebra are in the count. Catching the rest means following the provenance of a value, which is a different instrument. The reversal probe cannot see any of them. 2026-09-18. |
| **A Java class built by reflection is unreachable** | traccar finds its protocols by scanning a package and has Guice build them, so no call reaches their constructors and 1,968 of its 2,946 unreachable routines were under `protocol/` on 2026-11-02. Since 2026-11-12 Netty's `channelRead` is a way in by inheritance and reach crosses its dispatch into every `decode`, so 1,172 of 4,296 are unreachable; what is left under `protocol/` is the constructors and what only they call. A static reading cannot follow a class name held in a string or a scan; UNREACHABLE says *possible* and its blind spot names library code, and this is the same honest limit. 2026-11-02. |
| **javac's pick among overloads under an unknown argument is refused** | Where an argument's type is a missing dependency's, javac still chooses one overload and says nothing; `Edges.java` refuses that choice when a rival overload exists, and the call is `untyped`. On traccar without Netty that is about 2,000 calls (`BufferUtil.indexOf(…, buf)`). Its jars on the machine (`Deps.java`) is what settles each one. DEAD_CODE spares a routine an untyped call may name. 2026-11-02. |
| **JAX-RS's client is NETWORK only with its jar on this machine** | `client.target(url).request().get()` is typed by the edge pass against `jakarta.ws.rs.client.SyncInvoker.get` (`java.yaml`, `Rules.typed`), which needs javac to load `jakarta.ws.rs-api`. traccar's jars are not on this machine, so its 18 such calls are still `untyped`; the behaviour is proved on a compiled jar in a fake repository (`tests/test_java_reader.py`). Tom's decision of 2026-11-07, as built on 2026-11-12 (BACKLOG 46). |
| **A supertype reached through `import a.b.*` is not read** | With a framework's jars missing, javac cannot type `extends JpaRepository<…>` and the edge pass reads the name the file wrote, through a single-type import or fully qualified. An on-demand import names a package, and choosing which package's `CrudRepository` was meant would be a guess, so such a class is said nothing about: no touch, no way in. A method with no `@Override` is not claimed as a framework's either, for the same reason. The jars on the machine settle both. 2026-11-12 (BACKLOG 45). |
| **Java's edge pass reads no annotation processor** | `-proc:none`, so a Lombok getter, a Dagger component or a MapStruct mapper is not there to resolve to; a call to one is `untyped`. Running a processor is running somebody's build. 2026-11-02. |
| **The JDK on the machine bounds the Java syntax read** | javac parses at its own `--release`, so a file using a feature newer than the installed JDK is a parse error, and two machines on two JDKs can read one tree differently. The reader's cache key carries the JDK's version (rule 81); the map's stamp does not, which is Go's stdlib residue in Java's terms. 2026-11-02. |
| **A Java overload's id is an ordinal, and order-dependent** | `pkg.C.helper` and `pkg.C.helper#2`, as Kotlin's and C++'s overloads are, so inserting an overload above another renumbers it. Putting the parameter types in the qualname would change how every name reads, on every surface, to fix a churn nobody has yet seen. 2026-11-02. |
| **A jar that arrives in the cache later changes no edge until a Java file does** | Supplied edges are replaced only when the language's reader runs, and a run where every file is a cache hit does not run it. So `untyped` stays `untyped` after a build fills `~/.m2` until something in the tree moves. Rust's cached crates have the same shape. 2026-11-02. |
| **A killed analysis can leave its pool behind** | Nine `ProcessPoolExecutor` workers from the original Unreal ingest were still alive 22 hours later, parented to init, idle at 5.5 MB each. Harmless where they are, and the 86-part re-read on 2026-09-20 added none — so it is an interrupted run's leak rather than an ordinary one's. Stated because a batch runner doing this nightly would accumulate them, and the batch-ingest design is the place that would have to care. 2026-09-20. |
| **An orphaned reader keeps computing** | A reader learns that its host has gone only when it next writes to the pipe, and Java's edge pass writes nothing until it is done. A killed analysis of the Android SDK left its JVM, parented to init, attributing for 30 minutes and more; it would have died at its first write. Harmless to the map, and it spoils any timing taken beside it, so `PERFORMANCE.md`'s Android row says to check `ps` first. Watching stdin for end-of-file on a thread would end it, and that is a change to every reader's loop, not one. 2026-11-02. |
| **The size guard counts files and nothing else** | `walk.TOO_BIG` is 20,000 *files*, which is the shape of the evidence — `Engine/Source/Runtime` is 18,191 and is the largest tree read end to end. A tree of 19,000 enormous files passes it and a tree of 25,000 tiny ones is refused, and neither is what the bound is really about: the thing that hurts is rows written, not files read. Bytes or an estimate of rows would be the honest key, and taking one needs a corpus spread wide enough to separate the two — which is a measurement, not an edit. Stated so the number is read as what it is. 2026-09-19. |
| **A part's documents are whatever is under its root, vendored prose included** | Unreal's 86 parts hold **12,886 documents, and 11,850 of them are `Engine.Source.ThirdParty`'s**: a part of 620 code files on 57,373 files of vendored library source, which the C++ reader skips by name for code. Every other part is in double or single figures. Tom's decision, 2026-10-02: vendored prose **is** documentation of the program, so it is read. Design rule 11 holds as written, and a reader's `skip_dirs` stays a statement about program source and never about prose. Measured with `analyze --timings` on 2026-09-20; formerly BACKLOG 9. |
| **A Go function defined per platform is drawn to its linux/amd64 definition** | Tom's decision, 2026-11-01. Each package is checked under linux/amd64, darwin/arm64 and windows/amd64; where they name different definitions the edge goes to the first, and its `how` counts the variants (38 on beads). The other platforms' versions read as uncalled. Ambiguous was the plan's answer and cost 16 false LOST_EDGE SUSPECT on beads. |
| **A Go call through a renamed standard-library import is not a boundary** | `import stdos "os"` then `stdos.Getenv` is not matched, because rules match the spelling written and a reader never expands an alias (rule 4). Rare, since `goimports` never renames. Stated in `detectors/go.yaml`. |
| **`f[MyType]()` records no call name in Go** | `x[y]` is a type argument or a subscript and only the checker can always tell; the reader answers *type* only where the index cannot be a value, so a call instantiated with a named type is left unnamed for rule matching. Its edge still comes from the checker. Stated in `extract.go:looksLikeType`. |
| **`plugin.json`'s `workers` is read and used by nothing** | Every manifest declares it and no reader is started more than once. Found writing the Go manifest; harmless, and a field nothing reads is rule 35's shape, so it is stated here rather than relied on. |
| **LOCAL_IPC is decided by an argument the source must write** | `net.Dial(network, a)` and `socket.socket(fam)` cannot be told from the network and stay NETWORK, with `blind spot:` in their evidence. So does `socket.socket(fileno=0)`, which takes its family from a descriptor (Comitia2's `s01sock.py speak`). A Go constant naming `"unix"` is a variable to a syntactic reader for the same reason. 2026-11-02. |
| **A signature names a type, not an act** | `net.Conn` and `net.Listener` are a Unix socket's as often as the network's, so a declared one is NETWORK and says *may be a Unix-domain socket*. A stub returning a type of its own (`ipc.Dial` returns `*Client`) declares nothing a rule can read, and a stub named for peer credentials (`PeerUID(*net.UnixConn)`) is LOCAL_IPC, not *peer credentials*, until a body calls `GetsockoptUcred`. 2026-11-02. |
| **Python's `bind`/`connect` are read only on a name bound in the same routine** | `on_receiver` follows `s = socket.socket(AF_UNIX)` and `with … as s` to `s.bind` within one routine. A socket held on `self` and used in another method, or returned and used by the caller, is the creation row alone, with no path. 2026-11-02. |
| **`PERFORMANCE.md` is v1's, except where it says otherwise** | Every figure above the v2 headings was measured on v1 and none has been reproduced in this tree. |
