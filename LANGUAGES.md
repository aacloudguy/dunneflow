# DunneFlow — adding a language

`CLAUDE.md` carries the architecture index; this file carries **what it actually costs to
teach this tool a new language** — the six things to do, what a plugin gets for free and
must not reimplement, and the three things that will bite.

**Read all of it before writing a reader, and the third section twice.** This chapter said
the same four lines for a year — *write one extractor that emits `FileFacts`; nothing else
changes* — and that was a claim about a tool nobody had asked. What is here now is what was
actually done, twice.

## Adding a language

*This section said "write one extractor that emits `FileFacts`; nothing else changes" for a
year, and it was a claim about a tool that had never been asked.* Asked, in v2, it turned
out to be **nearly** true and to leave out everything about how the reader gets there. What
follows is what was actually done twice.

**A reader is a plugin and never an import.** It declares itself in
`plugins/<lang>/plugin.json` and the registry finds it. **Nothing above the graph names a
language** — two renderers and forty-odd dashboard modules, and not one string constant
spelling `python`; `walk.py` dispatches without naming anybody, where it used to open with
`from .extractors.python.extract import extract_file`, which is the whole of what *only
Python is extracted* ever meant. `tests/test_languages.py` asserts it, off `PLUGINS` rather
than a list of names, and reads **constants** rather than the text, because a docstring
giving *python 628 · typescript 412* as an example is not a violation of the rule it is
describing (rules 34 and 43).

Under `resolve/` exactly two places name one legitimately — `RESOLVERS`, which is the
dispatch table, and a language's own package — and **nothing else may at all**. It was one
more until 2026-09-18: `traceability.py` asked Python's builtins of every corpus, including
one with no Python in it, and the test pinned that at **one** so it could not grow while it
went unmeasured. Measured, it was scoped to `languages.read(store)`, the literal went with
it, and the guard failed saying so — which is how a residue held at a number gets closed
rather than forgotten. The assertion is zero now.

**The measurement is worth carrying, because the honest headline is that it moved nothing.**
Removing the exclusion outright changes no verdict on any of four corpora — Mensores 1,463
graded ids, DunneNote 391, DunneFlow 28, DunneCorp 0. The case for the fix is rule 98: on a
TypeScript-only map the words it struck were `hex`, `round` and `set`, and the ones waiting
in a larger tree are `id`, `set`, `type`, `format`, `next`, `open`, `filter`, `map`. A
**union over the languages the map holds**, never a per-symbol test — the question is not
*is this symbol a builtin* but *would a document naming this word be naming your symbol*,
which is about the language the prose is written about. A language declaring no builtins
contributes none, and the page says which languages' were used, off the field the exclusion
was built from rather than as a constant reading "Python's" (rule 13).

The two kinds of reader differ in one field:

| | |
|---|---|
| `in_process: true` | runs in this interpreter, `reader:` names a package in this tree. Python. |
| `in_process: false` | runs behind a pipe, `entry:` names one built file, `toolchain:` says what has to be on the machine. TypeScript. |

**Which it is, is a decision and not a preference.** `tree-sitter` ships no macOS
universal2 wheel and neither does `pydantic-core`; this tool freezes to a universal2 bundle
whose entire runtime dependency list is `pyyaml`. So a language whose only good parser is a
native extension is read **out of process**, by the toolchain that language already has, and
the frozen application stays one file. Measured before it was settled: **the transport is
free** — 0.022 ms a round trip, 0.3% of a run — and the codec is 98% of the 1.48× overhead
an out-of-process reader costs, so pipelining would buy nothing.

### The six things to do

1. **Generate your fact types, never transcribe them.**
   `dunneflow ingest-schema --json` emits a descriptor of `schema.py`; write the small
   generator that turns it into your language's types, and have a **test regenerate and
   compare**, because a generator nobody runs is a transcription with extra steps.
   TypeScript's is `tools/gen_facts_ts.py` (Python, so the test needs no toolchain), and the
   hand-written version it replaced was wrong within an hour: it filled a
   `NetworkCall.library` field `schema.py` has not got, the codec dropped it into
   `FileFacts.errors`, and `WalkStats` counts that as a **failed file** — so every
   TypeScript file with a network call in it would have been reported as unreadable.
2. **Speak the protocol**: `hello` · `open` · `extract` · `edges` · `close`, NDJSON over
   stdin and stdout, correlated on an id. **stdout carries protocol and nothing else**; every
   sentence goes to stderr, which the host drains and never parses.
3. **Keep the dotted contract.** `ingest/dotted.py` writes down the normalisation every rule
   in every `detectors/*.yaml` has always been matched against, and
   **`dunneflow ingest-conform <lang>`** checks your reader keeps it. Run it. TypeScript's
   twelve clauses are the first time clauses 5, 6 and 7 were ever exercised.
4. **Write `detectors/<lang>.yaml`** and name it in the manifest. Boundaries, frameworks,
   and whatever else that language spells its own way. Prefer a rule to a branch.
5. **Declare `discovery:`** — suffixes, skip dirs, skip names, and the **three shapes of
   test name**. Do not generalise them into one list: `test_a.py` is a stem prefix and
   `a.test.ts` is a whole-name suffix, and a shared rule gets both wrong in opposite
   directions. Python's rule applied to TypeScript admitted **322 of DunneNote's 767 files**,
   42% of the corpus, as program code.
6. **Declare `fingerprint:`** — the files your reader's stamp is computed from, named and
   never globbed. For a bundled reader that is the built artifact, not its source tree.

### What you get for free, and what you must not reimplement

**String literals are scanned in the host.** A reader reports the strings it found
(`FileFacts.literals`) and stops deciding what a string *means*; `ingest/literals.py` does
the SQL and artefact scanning for every language at once. So `detectors/<lang>.yaml` stays
an extension point a plugin never has to be rebuilt for, and one string cannot be read two
ways in a `.py` and a `.ts` (rule 51, in the fact contract, which is the most expensive
place to have it).

**Edges are optional and are supplied, not guessed.** `supplies_edges: false` is a complete
answer: every call is left external and the run says so with a count. If your language has a
checker that knows the far end, say so and send `edges` — the host turns a location into an
id, and nothing about that passes through a name.

**So are bindings, for a way in marked on a declaration.** Unreal's `UFUNCTION` sits on a
declaration in a header and its body is in a `.cpp`, or is `<Name>_Implementation`, or is
generated and in no C++ at all. A reader whose checker knows declarations by identity
declares `supplies_bindings: true` and sends a `binding` frame per such way in during the
`edges` stream (`schema.SuppliedBinding`): where its body is, or `why` it has none, and the
`edges_done` frame's `bindings` is the count. A way in it sent a binding for is never
then bound by name, because a name cannot tell overloads apart. The C++ reader is the only
one that sends them; what decides `_Implementation` is the Unreal preset in `cpp.yaml`, not
the reader.

**And a binding may name several bodies.** A marked pure virtual has none of its own, so its
binding carries `answers`, shaped as a dispatched call's: the overriders, any of which may be
what runs. They reach `entrypoint_roots`, `entrypoints.routine_id` stays NULL, and `why` stays
as the sentence saying *any of these*. What a walk starts from is their union.

**And uses, for a routine named as a value.** A C callback is handed to `event_set` or stored
in a table's `.exec` and never called by name, so without this every one of them is dead code
(714 of tmux's routines). `supplies_uses: true` and a `use` frame per routine named and not
called (`schema.SuppliedUse`, counted by `edges_done.uses`), and `DEAD_CODE` leaves them out.
A use is never made an edge: what calls a stored callback is somebody else's business.

**A reader whose facts depend on other files says so, or its map goes stale without a word.**
A C file's calls are whatever its headers expand to, so the file's own hash cannot decide
whether it is read. `facts_span_files: true` makes any change to that language's files
re-read all of them, and `edges_done.inputs` names what the reader read beyond its own files
-- a system header, a `.def`, a build file, a file it looked for and did not find -- whose
stats are compared on the next run. Rule 81. Every reader that supplies edges also gets the
`reading:<lang>` marker for nothing: a run killed before its edge pass still owes one.

**A reason is worded in your language.** `untyped`, `bound` and the rest are the reader's
words, and what each means is the language's: Rust's `untyped` is a receiver whose type is not
written down, C's is a call clang could not resolve. Say it under `frontier_words` in your
rules file; a reason you leave out is given the plain wording in `detectors.FRONTIER_WORDS`.

**Nothing else is yours.** The resolver's boundary suppression, the missing-target
bookkeeping, `stamp_lang`, the fingerprint, the walk's arithmetic and every surface above
the graph are the host's. If you find yourself writing one of them, that is the signal the
seam is in the wrong place.

### Three things that will bite

* **Text.** Python reads with universal newlines and most languages' runtimes do not, so a
  CRLF file hashes differently on the two sides and comes back *changed while it was being
  read*. `ingest.contract.SOURCE_TEXT` is the term; honour it.
* **A bundled reader does not carry the files it opens by path** (rule 97). It will not
  refuse — it will answer, with less. Split the residue into its reasons and look at the
  small one.
* **Admitting a new kind of fact re-runs every detector against a population it has never
  seen** (rule 98). A reader that is correct can still turn an unchanged detector into a
  liar: a `.d.ts` read as code gave uigen 83 BROKEN out of the command that gates CI, and
  C++ gave Unreal's `Runtime/Core` **3,875** out of the same command — every one of them
  `NAME_COLLISION` saying *"only the last one exists at run time"* about a language whose
  ordinary mechanism is overloading. Run `dunneflow check` on a real tree before believing
  the map.

## A third reader, and what it cost that the chapter above did not predict

*Written after C++, which is the first language this tool is not itself written in. Nothing
above was wrong; these are the four things it did not say.*

**A judgement you have to correct is a key in somebody's rules file, not a branch.** Two of
them exist now and they are the same shape: `unawaited_async` says what a dropped async call
costs, `redefinition` says what a second definition of one name means. Both are declared by
the language, read per row off `files.lang`, and both take **empty to mean the detector does
not fire** — a severity nobody chose is worst in the command a CI job trusts (rule 49). When
a detector is wrong about your language, add the third key rather than the first `if`.

**The probe tree is not this repository any more, and adding a language means adding a file
to it.** `tools/fingerprints.py` read `src/dunneflow` because it held real source in every
language this build reads — which was true exactly while those were the languages DunneFlow
is *written in*. It is `tests/fixtures/polyglot/` now, one file per registered language, and
`test_the_default_probe_tree_holds_every_language_this_build_reads` fails until yours is
there. That test is not an obstacle; it is the thing standing between you and a stamp
compared against an empty map (rule 37).

**The packaging spec finds in-process readers now, and did not before.** It named
`extractors/python` literally, two lines under a comment arguing rule 92 about the rules
directory. A new in-process reader would have had its manifest ship, its rules ship, the
registry load it — and its own bytes missing from the bundle, so `lang_fingerprint` hashed
nothing and the application met its first file of that language in somebody else's hands.

**Decide what belongs in a routine's identity before you write the reader, not after.** The
C++ reader was designed to leave the file out of an id for externally-linked names, so that
a header's declaration and a `.cpp`'s definition would land on one routine. There is no such
pair — *a declaration with no body is not a routine* — so the file belongs in the identity,
as a module does for Python. Left out it is wrong rather than merely unnecessary, and Unreal
proved it inside one module: 221 qualnames with a body in two files, and
`UNIQUE constraint failed: routines.id`.

**And a reader does not decide this at all any more — `schema.definition_id` does** (rule
106, 2026-09-19). A definition is `(file, qualname[, ordinal])` and a way in is
`entrypoint_id(file, …)`, in one function each, for every reader including the one on the
far side of a pipe: `plugins/typescript/src/ids.ts` mirrors both, and that mirror is pinned
from both sides by `tests/test_typescript.py`. Do not mint an id any other way.

The paragraph above was the right instinct arrived at one reader at a time, and the reason
it had to become a rule is that **a qualified name is only unique inside one language's
naming**. `probe.py` and `probe.ts` in one directory are both module `probe`, both declare
`main`, and for as long as an id was the name alone that tree could not be analysed at all.
The C++ reader was immune by accident; the two readers that had been here a chunk longer
were not, and no corpus had happened to show it.

## A fourth reader, and what the third one got wrong about it

*Written after Kotlin, which took a day where C++ took a session.* The chapter above is
right; what it does not say is **how much of the cost is the language rather than the seam**.

**The seam costs almost nothing now, and that is measurable.** Kotlin needed: a manifest, a
rules file, one entry in `_IN_PROCESS`, one file in the probe tree, and one name in the
plugin-set assertion. Nothing in `packaging/`, nothing in `walk.py`, nothing above the graph,
and no new key in the detector grammar. Every one of those five is in the list above, and the
list is now complete rather than hopeful.

**What varies by two orders of magnitude is the reader.** C++ needed a line-continuation
splice, a preprocessor, a most-vexing-parse refusal and a header/implementation rule; Kotlin
needed none of them and is about half the size. The two things Kotlin needed that C++ did not
are worth naming because they generalise: a language with **expression bodies** cannot be read
by looking for braces, and a language whose **house style is lambdas** cannot be read by
treating a brace as a scope. Ask both questions of the next language before writing anything.

**`redefinition` is the second judgement to be declared rather than branched on**, after
`unawaited_async`, and Kotlin needed it on day one — it overloads, like C++ and unlike Python.
That it was already there is the point: the first language to hit a wrong judgement pays for
the key, and the second one just fills it in. When a detector is wrong about your language,
look for the key before you write the `if`.

**And a residue can be larger in one language than in another for the same reason.** *A
collection operator is a call and not a loop* is true of C++ and Kotlin alike, and it costs
far more in Kotlin, where `forEach` is the idiom rather than the exception. State the residue
in the language's own terms, not in the tool's.

**Go and Rust are the obvious next ones** — both ship a toolchain that can be asked, and
`resolve/manifests/` already reads `go.mod` and `Cargo.toml` for what a program declares
about itself, which is the half that does not need a reader at all.

## A fifth reader, and the seam it found that four had not

*Written after Go, 2026-11-01, the first reader since TypeScript to run on the far side of a
pipe and the first to supply edges after it.* Kotlin said the seam cost almost nothing. For a
second **checker-backed** reader that was not yet true, and what it cost is worth knowing
before the next one.

**Three things in the seam had only ever been asked by one reader, and each was quietly
TypeScript's.** The supplied-edge lookup hardcoded `"typescript"` in both of its queries,
so a second reader's edges would have been written to `supplied_edges` and read by nothing
(rule 35); it is `resolve/supplied.py` now and reads its `lang`. `plugin_argv` could start
`[command, entry]` and nothing else. And **`probe_toolchain` had never been called outside a
test**, so a missing `node` reached the walk as an uncaught refusal from a worker that could
not start and took the whole analysis with it. A second reader of the same kind is what
finds the places the first one was assumed (rule 92's shape, one layer up).

**A reader may be shipped as source and built where it runs.** `plugin.json`'s `build` is
the argv of a build, with `{output}` for where the program goes; the host builds it once per
stamp, platform and toolchain, and starts what it built. Choose it when the toolchain has to
be present at run time anyway, as Go's does to read the standard library. It keeps one
`fingerprint` for every platform, where one binary per platform would give each its own
stamp and make every map unreadable on every other machine (rule 12).

**The second implementations are pinned from both sides, by a fixture the host writes.**
BLAKE2b, every id function, and Python's `errors="replace"` decoding had to be written again
in Go. `tools/gen_facts_go.py` writes `tests/fixtures/ids/vectors.json` from `schema.py` and
from Python's own decoder, `go test` asserts it, and a test regenerates it without Go. The
decoding is the one that would have bitten: Go's own conveniences replace an ill-formed
sequence once per byte or once per run, and Python replaces it once per *maximal subpart*,
so a file with stray bytes would have hashed differently on the two sides and been reported
as *changed while it was being read*. A tampered vector was seen to fail before any was
believed (rule 59).

**A judgement can be about the targets as well as the language.** Go defines a function once
per platform as an ordinary thing, and a reader that checked only the host's `GOOS` would
draw a different map on each machine (rule 66). So every package is checked under a fixed
set of three targets and the answers are joined per call site. The plan said a site the
targets disagree about is ambiguous; beads showed what that costs: 16 `LOST_EDGE` SUSPECT
findings saying *anything downstream is missing* about Go that was correct, and every flow
through them cut. Tom's decision on 2026-11-01 was the **reference target**, linux/amd64:
the edge goes to its definition, the edge's `how` counts the variants, and the residue
(the other platforms' versions drawn uncalled) is stated in the user guide. Ask the next
language what it does per platform before choosing.

**And rule 98 found three defects in a day, every one of them this reader's.**
`MISSING_RETURN_TYPE` read 183 of rain's 715 routines as undeclared, because a Go function
with no results was sent as `None`, which means *undeclared*, and no Go function is. A cobra
command with no handler is a group, and as a way in it *led nowhere*, four times. And
`os.Exit` was a PROCESS boundary, which was 714 of beads' 5,891 touches. Each was fixed in the
reader or in `go.yaml`, and each was found the way this chapter says: `dunneflow check` on a
real tree, with every finding read against the source before it was believed.


## A sixth reader, and four declarations every language now makes

*Written after Rust, 2026-11-01. Out of process on `syn` 2.0.119, and the first reader
whose edges come from a path resolver rather than a type checker.* Go's seam carried it
with three additions, and its first real trees found more in the **host** than in the
reader, which is the part worth reading before the next one.

**The build seam grew three words.** `{workdir}` is a scratch directory the host owns, for a
toolchain that writes beside what it builds; `product` names the file a build leaves there,
for a toolchain that will not be told where to put it; and `build_env` holds a build's
environment, which is where Go's four variables went. `syn`, `proc-macro2`, `quote` and
`unicode-ident` are vendored under `plugins/rust/vendor/` and built with
`cargo build --offline --locked`: nothing is fetched, ever. **Two of those crates carry a
`build.rs`, and it runs when the reader is built** — say so to anyone asked to trust it.

**A path resolver is not a checker, and the difference is the rule.** An edge is CERTAIN
only where a path names exactly one definition: a `use`, a module, a receiver whose type the
source writes down (a field, a parameter, a constructor's declared return). Everything else
stops, and **says where and why** (`calls.frontier`, `calls.reason`: *outside*, *untyped*,
*dynamic*, *bound*, *unfollowed*), and a stop at a dependency is confirmed against that
dependency's source in the local cargo cache — read, never fetched (design rule 14). Two
judgements are this reader's own and were each a LOST_EDGE on pdfcraft before they were made:
- **a sealed trait's one answer is an edge.** `self.m()` in a default body, `dyn T`, or a
  type parameter bound by `T`, where `T` is written without `pub` and exactly one definition
  answers. A `pub` trait stays ambiguous, because another crate may write the override.
- **a function a body declares is that body's.** Three `fn walk`, each nested in a different
  function, were one module-level name with three definitions.

**Test code can be a file that only another file names.** `#[cfg(test)] mod tests;` makes
`tests.rs` test code, and `tests.rs` cannot know it; the per-file pass cannot read its parent
without breaking its own cache key (rule 95). Only the edge pass sees the whole tree, so
`edges_done` carries **`test_only`**, and the walk leaves those files out as it leaves out a
test file. The set is held in `meta` (`test_modules:<lang>`) with each file's hash, so an
unchanged test module is a cache hit and is never parsed again. On pdfcraft that was 17 files
and half its DEAD_CODE list. Any reader with a declaration-driven test idiom answers here.

**Every rules file now answers two more questions, and the next reader must too.**
- **`network.timed`**: a call that cannot be made without a timeout, and the index of the
  argument that carries it. Python names its timeout with a keyword; Rust and Go cannot, so
  `TcpStream::connect_timeout` and `net.DialTimeout` were NO_TIMEOUT on the one call named
  for its timeout — DunneNote's once, beads' seven times.
- **`private_means`**: *module*, *package* or *surface* — what `visibility = 'private'` means
  in this language, which the naming lane's LEAKAGE claim depends on. Rust records
  `pub(crate)` as private; under Python's reading pdfcraft "leaked" 624 times. An unknown
  word is refused and an empty one is not measured.

**And rule 98 found the host's defects this time, not only the reader's.** A new language
brings a new population to old judgements, and Rust's idioms reached three that had been
wrong all along:
- **A chain on a call was a second act.** The dotted contract folds `f(x).g()` into `f.g`
  (clause 2), so a rule that matched `f` matched `f.g` again. `ingest/acts.one_act` drops the
  extension, per routine, line and kind: 257 doubled DATABASE rows in Society, and Go's
  `http.Get(u).Body.Close()` was two network calls. Rust is cleaner still: a method's
  receiver is a value, so the reader matches a method site by `method:` rules alone, which is
  how `rsa.then(…)` on a `bool` stopped being CRYPTO.
- **`replace` was a FILE method** — rule 5's own example, 175 times in Society.
- **A sentence ending in a full stop was SQL** when it began with `delete` and had a bracket
  in it, and pdfcraft's MCP tool descriptions minted three tables.

**A language can now say how it calls another one by name, and the next reader should
ask whether it does.** `ipc` in a rules file has two sides (`resolve/ipc.py`, `ARCHITECTURE.md`):
- **the server side, which is the reader's:** an attribute that makes a function a command
  (`command_attrs`) and a macro whose path arguments register it (`registrars`). The reader
  emits `EntrypointKind.IPC_COMMAND` and `IpcRegistration` and judges neither.
- **the client side, which is the host's:** `clients`, a `{module, name}` that sends its first
  argument as a command name. The host finds the sends; a plugin reads nothing.

`foreign_prefixes` names commands answered outside the tree. Only Tauri is declared.
Electron's `ipcRenderer.invoke` looks like the same shape and has not been tried, and the
judgement that one would fit belongs to a real tree, not to this paragraph.

Each was found the way this chapter keeps saying: `dunneflow check` on two real trees
(DunneNote and pdfcraft), every finding read against the source, and the survivors fixed
where they live rather than where they showed.


## A seventh reader, and what a checker's answer still needs from the host

*Written after Java, 2026-11-02.* Out of process on javac's public tree API
(`com.sun.source`, `javax.lang.model`), with no internals and no `--add-exports`; shipped as
source and built where it runs, as Go's and Rust's are. Its first two real trees (petclinic
and traccar) found more to fix in the host's judgements than in the reader, and the reader's
own two defects were both a checker answering more confidently than it had the right to.

**The build seam grew one word, `run`.** A JVM reader's product is a jar, which no platform
will execute, so `run` is the argv that starts what the build wrote: the toolchain's command
first and `{reader}` for the file (`["-Xss16m", "-XX:+UseSerialGC", "-jar", "{reader}"]`).
The cached file is then `<lang>.reader` and is never marked executable. And because the seam
runs one command, **the build is a Java program**: `java Build.java {output}`, through the
JDK's single-file launcher, compiles `src/` with the system compiler and writes a
reproducible jar itself. No Maven, no Gradle, nothing fetched; a JRE is refused by name.

**Decide identity by the language's nearest neighbour, not by the last reader.** The
qualname is the **package's**, as Kotlin's is (`org.traccar.model.Event.setDeviceId`),
because that is how a Java author addresses a method; the module and the id carry the file,
as every reader's do (rule 106). A constructor is spelt with its class's name, as C++ does; an
anonymous class takes javac's `$n`, counted within its method; an enum constant's body is
named by the constant. A method with no body is a field of its interface, not a routine.

**javac writes things nobody wrote, and every one has to be refused by hand.** An enum
constant arrives as a field whose initialiser is a `new` javac made, so a reader that walked
it recorded `Colour` as a construction at every constant. A record's accessors and
canonical constructor, an enum's `values()` and a class's default constructor are members
the source never declared (`Elements.getOrigin`); a call to an implicit constructor points at
the class it builds (`SuppliedEdge.constructs`) rather than at a routine that does not exist.

**A checker resolves with what it has, and with a missing dependency that is a guess.**
javac given an argument whose type it cannot see still chooses one overload, silently:
`width(m.part())` went to `width(int)` with nothing to rule out `width(String)`. Refusing
that choice where a rival overload exists withdrew about 2,000 of traccar's edges into
`untyped` (Netty is not on this machine). The second defect was the same shape over
dispatch: an override counts only where it can answer **this receiver** — `Event`'s
`setDeviceId()` is `Message`'s whatever `Command`, a sibling, does with its own — which
supplied 1,241 more edges and took ambiguous calls from 1,582 to 293.

**Dispatch is the language working, so the host learned to say so.** Tom's rule (2026-11-01):
an edge is CERTAIN where nothing else can answer — static, private, final, a constructor, a
final class or record, `super.m()`, or nothing in the tree overriding it — and otherwise the
call is `dynamic` with the answering bodies counted. Three host judgements followed from
traccar, each read off `calls.reason` and never off a language's name:
- **LOST_EDGE** stands for a `dynamic` call and says it is *dispatched to one of N
  implementations*, not that N definitions share a name (Python's sentence).
- **DEAD_CODE** spares a routine whose name an untyped call uses, and says how many.
- **Every walk crosses dispatch** (`dispatch_links`, `resolve/dispatch.py`): the reader sends
  the location of every body that may answer (`SuppliedEdge.answers`), the host links them,
  and reach, `touches`, `impact`, MCP and UNREACHABLE follow them, said as *may run* and never
  drawn as an edge. traccar's unreachable count fell from 3,575 to 2,946; most of the rest is
  classes it builds by reflection.

**The frontier can be read from this machine's caches.** `Deps.java` reads what a tree
declares as its build tool would, without running it — Maven's effective POM (parents,
properties, imported BOMs), Gradle's literal, map and catalog coordinates with `$name` filled,
the Spring Boot plugin's BOM — mediates nearest-first through cached POMs, and puts the jars
it finds on the edge pass's own classpath, so `untyped` becomes `outside` with the library's
own name. Neither corpus's jars were on this machine; the behaviour is proved on a fake
repository with real compiled jars. A coordinate a script computes (traccar's
`jacksonVersion`) is listed as not found, never guessed.

**A checker built for one project's compilation will not hold a big one, and the bound
has to be on the work.** The Android SDK's 16,344 files kept javac collecting garbage for 97
minutes and then out of a 2 GB heap, with no edges; the reader's own account of that failure
reached only stderr until `edges_done.notes` carried it to the map. Over 2,000 files the
tree is now attributed **in batches of whole directories**, in path order (rules 66 and 105):
- **What crosses a batch is a name, never javac's identity.** Each compilation's elements
  die with it, so every batch writes its overriders into an index keyed by string
  (`binary.Owner#name(erased params)`), and the dispatch rule is decided once, over the whole
  tree's index, after javac is gone. A batch-local index called `x.hello()` CERTAIN while
  another batch's `C.hello` could answer it (rule 1).
- **The rest of the tree is a source path held in memory, read once, with every body
  blanked**: interior made spaces, line breaks kept, so every position is the file's own.
  Two things were measured first. A real `-sourcepath` was read off the external volume one
  file at a time in every compilation, four hours at 3 % CPU. And javac attributes a class
  it loads off the source path as fully as one it was handed (102 of traccar's files
  attributed 915 others). A blank starts at the brace and never at the node, or `static {`
  loses its keyword and the class stops parsing.
- **The stop is heap after collection, summed over the heap pools and judged against the
  whole heap**, at 85 %. One pool judged against its own maximum is a different question,
  and it stopped the first batched run in under a second. A batch that fills is split in
  half; a single directory that still fills is given up, its calls are left unresolved, and
  any call that could dispatch into it is `unfollowed` rather than CERTAIN (rule 49).
- **javac's errors are counted in a batch's own files**, with `-Xmaxerrs` lifted: "100
  errors" was javac's cap, not traccar's count.

The batches cost no internals. `JavacTaskImpl.analyze(classes)` would attribute only what is
named, but it is `com.sun.tools.javac`, which this reader does not use. Blanking the bodies
is how the public `JavacTask` is made to do the same.

**Ask the next reader the two Kotlin questions and two more.** Java has expression-bodied
lambdas and a stream house style, so `.forEach(x -> …)` is a COMPREHENSION span where the
function is written in place. The third question is Java's: **what does your checker do when
it cannot see a type?** If the answer is *it picks*, that pick is a guess, and the map may
not draw it. The fourth is clang's as much as anyone's: **what does your checker do with a
tree ten times your corpus?** Measure it on a scale probe before the first real tree does it
for you, and if it must be split, decide what crosses the split by name.

## An eighth reader, and what a whole-program parser costs the host

C and C++ on libclang took four seams the other readers did not need.

- **`facts_span_files`.** A C++ file's facts depend on what it includes, so its own hash is not a
  key for them (rule 81). A reader that declares this has all its files read after any change,
  and reports what else it read as `edges_done.inputs`, down to system headers. The cost is
  transfer and writes only, because this reader parses every file whenever it is opened anyway.
- **`reading:<lang>`.** A marker set before a language is read and cleared after its edge pass, so
  a run killed in between is recognised (rule 80). Without it, every edge-supplying reader could
  leave a map with no edges that the next run saw nothing wrong with.
- **`supplies_bindings`.** A way in marked on a declaration is bound by the reader. A USR is the
  right key and not a sufficient one: a header read alone may not know a type its `.cpp` does, and
  then the two have different USRs. So the qualified name and the parameter types as written answer
  where no USR does, if there is one such definition and one declaration asking. Argument count
  stands in only where one side has no types to compare; where both write types and they differ, it
  is not asked, because it would hand a marked overload the body of a sibling that is not marked.
- **A framework's code generator is data.** Which marker means which body is in the preset's
  `bodies` in `cpp.yaml`, not in the reader.

**What bit, and would bite again.** Findings in a language you are not working on still need
reading: OpenUSD's 89 BROKEN were noted as "all Python" for two days, and 87 were false. A generated
header (`pxr/pxr.h`, `*.generated.h`) is missing from any unconfigured tree, so 4,622 of OpenUSD's
5,104 C++ files and 10,923 of Runtime's 18,259 read on past a missing include. And any data-sized
`IN (?,…)` overflows at this scale, which is why they became `json_each`.

**A parser that recovers can lose things without saying so.** A reader that takes a parser's word
for what exists inherits every silent recovery it has. clang read `void U::F(X* p)` as a variable
and skipped the body, with no error on the file, and a body wholly inside a macro has no `{` where
one was looked for. Neither was visible in a count. Both came out only by reading each "leads
nowhere" against the source and asking why, and "no definition by a text search" had been recorded
as an answer on the way. Ask the source before the map.

**A fifth declaration: `macro_expansion`.** `read` where the toolchain expands macros and the calls
under one are facts (C and C++), `named` where a use can be seen and what it does cannot (Rust's
`syn`), `none` where the language has none or the reader does not look. Empty means nobody chose and
the macro detectors do not fire; any other word is refused. A reader that says `read` fills
`macro_defs`, `macro_sites`, `Routine.name_by` and `body_by`, and declares `supplies_macro_callees`
with a `macro_callee` frame per callee per line, whose `hits` the host records as boundaries. A
reader that says `named` fills the first two and the map says what it could not see. Where a macro
is defined is `unknown` unless the reader knows: `outside` would be a claim that it is not this
tree's, and a Rust macro may be another file's.

**A macro's whole expansion maps to one offset**, which is what makes every join between clang and
the tokens fragile here. A call starting inside a macro's span may be written in its arguments or
made by its body, and the test is whether the token scan would name a call at that offset. A
member call starts at its receiver and not its name, so testing the name's token called
`checkf(Key.IsValid())` hidden. And `clang_getSpellingLocation` returns the file location for a
macro's token, so it cannot detect what a macro wrote; rule 110 has the rest.

