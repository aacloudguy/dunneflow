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

