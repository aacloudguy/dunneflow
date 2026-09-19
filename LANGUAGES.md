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

**Go and Rust are the obvious next ones** — both ship a toolchain that can be asked, and
`resolve/manifests/` already reads `go.mod` and `Cargo.toml` for what a program declares
about itself, which is the half that does not need a reader at all.

