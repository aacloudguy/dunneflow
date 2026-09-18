# v2 — start here

This tree is **DunneFlow v2**: the same tool, being reshaped so that ingest is modular and
multi-language. v1 lives at `../DunneFlow`, is untouched, and still runs — use it whenever
you need a working map while this one is mid-change.

**`CLAUDE.md`, `BRIEFING.md` and `HANDOFF.md` in this tree are still v1's** and have not
been rewritten yet. Where they describe the tool they are accurate; where they describe
*state* they are v1's state, not this one's. This file and `PLAN-v2.md` are the v2 state.

## Read in this order

| File | For |
|---|---|
| `PLAN-v2.md` | the whole design: the plugin protocol, the registry, the fingerprint split, the TypeScript plugin, the MCP server, the 14 chunks and the gate on each |
| `CLAUDE.md` | the standing orders — **binding**, and the rules index |
| `RULES.md` · `DESIGN-RULES.md` | carried over **verbatim, numbering intact**. The numbers are addresses: never reused, never renumbered, never closed up. **v2 continues at engineering rule 105, and design rule 32** — 95 is the fingerprint's blind spot, 96 the record minted on demand, 97 the bundled program that does not carry the files it reads, 98 the detector handed a population it was never shown, 99 the name that is relative to the root that declared it, 100 the judge that picks one of several true answers by the order it was written in (all six 2026-09-17), 101 the route that is not a branch and 102 the sentence about an order that has none (both 2026-09-18), 103 the path that is not a key until it is canonical and 104 the slot claimed before the thing that holds it exists (both 2026-09-18), and **design rule 31**, the panel pinned to an edge that grows away from it. A rule is never closed; 95's `sql.py` gap was shut by chunk 6 and the general remedy it names is not built. |
| `BACKLOG.md` | **what this tree owes** — nine open items and eight stated residues, each with where it came from, why it was not done, and what would settle it. Nothing in it is scheduled by the plan; all fourteen chunks are done. |
| `PERFORMANCE.md` | v1's figures. **Every one of them was measured on v1** and none has been reproduced here — do not restate one as though it had been (rule 24). |

## The four decisions, already taken

* **Where** — sibling clone, fresh history. v1 is never edited.
* **Parsers** — out-of-process plugins over native toolchains. Python stays in-process on
  stdlib `ast`. Chosen on a measurement: `tree-sitter` ships no macOS universal2 wheel, and
  neither does `pydantic-core`, which the official `mcp` SDK needs. This tool freezes to a
  universal2 bundle and its entire runtime dependency list is `pyyaml`.
* **API** — a hand-written stdlib MCP server over stdio, for the same reason.
* **First language** — TypeScript (against `../DunneNote`), then React/TSX (against
  `../DunneCorp`).

## What is done

* **Chunk 0.** Tree seeded from v1's *working tree* at `4f2796c` — v1 had 22 documentation
  files edited and uncommitted, and copying HEAD would have dropped them. Gates green on the
  untouched clone: ruff, mypy, **1,451 passed · 1 skipped** (the skip is `test_frozen.py:207`,
  the Linux maps-root layout, correct on macOS). Note that is 1,452 tests where `CLAUDE.md`
  still says 1,447.
* **The golden baseline** — `output/GOLDEN-v1.txt`, with the graph it came from beside it in
  `output/mensores-v1/`. Society (`../society-2026-08-29/src`, 628 files) read by **v1's**
  code with `--standards ../dunnecorp-standards`.
* **The `ingest/` seam** — contract, registry, in-process wrapper, `plugins/python/plugin.json`.
* **The gate is runnable** — `tools/golden.py`, and the section below says what it reproduces.
* **A read means a read.** `Store(writable=False)` opens `?mode=ro`, so the fourteen sites
  that open a map to read it can no longer write to one. Nothing on the analysis path
  changed, so the golden is untouched.
* **`walk.py` is wired to it** — `discover()` takes the suffix union off the manifests and
  a plugin's own skip and test rules, `analyze_tree` groups by language and dispatches, and
  `is_test_path` is gone in favour of `DiscoveryRules.is_test`. The walk says what it left
  out: unread suffixes, tests, pruned directories. **Gate run and green: 7 of 7 digests
  identical against the v1 graph**, every row count and distribution byte-identical, the
  four executables still at 1,381 · 423 · 292 · 112 and conformance still 4 · 1 · 10.
  **1,540 passed · 1 skipped**, mypy clean over 157 files, ruff clean.
* **`lang` is load-bearing** — the two `"python"` defaults on `Routine` and
  `DataStructure` are gone, `ingest.stamp_lang` is the one place a language is written onto
  a record and refuses a record that brings its own, the host verifies what a reader
  claimed against what it was handed, `load_rules` lost its default and now answers
  *declared* · *declared none* · *refused* instead of returning an empty rule set for a
  missing file, and four of the five hardcoded "only Python is extracted" claims are read
  off `SELECT DISTINCT lang FROM files`. A run says `read: python 628` on all three
  channels, the About dialog included. **1,562 passed · 1 skipped**, mypy clean over 159
  files, ruff clean, golden unmoved.
* **Rule 12 is split.** Three keys instead of one: `meta.extractor` for what every reader
  passes through (now including `schema.py` and `ingest/*.py`), and `files.extractor` per
  row for the reader that produced it — a version and a hash of its rules and its bytes.
  Editing one language's reader costs that language a re-read and costs the others
  nothing; a read of a map whose reader has moved is refused **by name**. Pressed end to
  end, and through the frozen binary: both builds compute the same two stamps and open
  each other's maps. `SCHEMA_VERSION` is **10** and no longer load-bearing. **1,575 passed
  · 1 skipped**, mypy clean over 160 files, ruff clean, golden unmoved.
* **The codec and the wire.** A reader on the far side of a pipe now works and is proved
  against the one extractor whose output is known exactly: `tests/plugins/python-oop/` runs
  **the Python extractor itself** through a subprocess, and Society comes back with **0 of
  628 files differing** and **7 of 7 golden digests identical** — against the v1 graph and
  against the in-process v2 one. `ingest/codec.py` is reflective over `dataclasses.fields()`
  and strict four ways; `ingest/worker.py` spawns, shakes hands, correlates on an id, drains
  stderr without ever parsing it, and respawns once without retrying the file that killed
  it. `ingest/dotted.py` writes down the normalisation contract that every rule in every
  detectors YAML has always been matched against, with `dunneflow ingest-conform` to check a
  reader keeps it and `dunneflow ingest-schema` to generate a plugin's types from. **The
  transport is free** — 0.022 ms a round trip, 0.3% of the run — and the codec is 98% of the
  1.48× overhead, so pipelining would buy nothing. **1,647 passed · 1 skipped**, mypy clean
  over 171 files, ruff clean.
* **The resolver is split.** `resolve/python/` holds Python's name rules, `RESOLVERS`
  says who answers for which language, and the driver in `resolve/calls.py` groups by
  `files.lang`. Two things hoisted into it so a new resolver inherits them: the
  `at_boundary` suppression (rule 2), so a boundary row never reaches a resolver at all,
  and the missing-target bookkeeping, so **one place** writes `UPDATE calls SET callee_id`
  where v1 had three. A resolver returns `Edge` or `NoEdge` and does no arithmetic. A
  language with **no** resolver has every call left external and is **named** with its
  count — which is what chunk 9 needs, since TypeScript extraction lands a chunk before
  its supplied edges do. `_BUILTINS` is `detectors/python.yaml` now, the measured union
  over CPython 3.9–3.13, so a map no longer depends on the analysing machine's version;
  on Society **no call site spells any of the seven names that differ**, and the digest is
  unmoved. `sql.py` joined the core key, which shuts the gap rule 95 was minted from. **1,588 passed · 1 skipped**,
  mypy clean over 164 files, ruff clean, **7 of 7 digests identical**.
* **TypeScript, extraction only.** A pnpm package bundled by esbuild into one committed
  `main.bundle.cjs` with the compiler inlined, speaking chunk 7's protocol. **DunneNote:
  443 program files read, 0 failed**, 315 left out as tests, 1,518 routines, 708
  structures; `packages/api-types` reports **zero** boundaries over 206 files, and the 283
  `.rs` and 81 `.svelte` files are named and counted. Python unmoved — **7 of 7 digests**,
  4,823 routines. The frozen binary reads a TypeScript tree and stamps the same two
  fingerprints. `SCHEMA_VERSION` is **12**. **1,699 passed · 1 skipped**, mypy clean over
  175 files, ruff clean.

  Six defects, four of them found by things written to find them: the plan's
  `crypto.createHash("blake2b512", {outputLength: 8})` is refused by Node **and** is the
  wrong hash (BLAKE2b puts the length in its parameter block), so BLAKE2b is implemented
  from RFC 7693; `localStorage.setItem` produced two rows for one act (rule 40); a `.map`
  on an unnamed receiver stopped being a loop; and `fetch` prefix-matched `fetchImpl`
  (rule 5 — Python's own rules hid it because every one of them contains a dot). The other
  two came from running it on real trees: a TypeScript **overload set** is one name
  declared three times, and **Python reads text with universal newlines and Node does
  not**, so every CRLF file hashed differently on the two sides and was refused as
  *changed while it was being read*. That is a term of the protocol now,
  `ingest.contract.SOURCE_TEXT`.

  Three things keep the reader honest: the rules **travel** in the `open` frame rather
  than being baked in; `src/facts.ts` is **generated** from `schema.py` and a test compares;
  and `ingest-conform typescript` is 12 of 12 with the dotted contract's clauses 5, 6 and 7
  exercised for the first time.
* **The string-literal split.** `FileFacts.literals`; the Python reader stops deciding
  what a string *means* and reports the strings; `ingest/literals.py` runs the SQL and
  artefact scanning for every language at once, so `detectors/<lang>.yaml` stays an
  extension point a plugin never has to be rebuilt for. **7 of 7 digests identical** and
  the four tables the split moves — `artefacts` 364, `sql_ops` 1,055, `db_tables` 43,
  `db_indexes` 73 — byte-identical to v1 row for row; 0 of 628 files differ over the wire;
  the frozen binary agrees and stamps the same fingerprints. It **invented 65 routines**
  before it was right: `_owner()` mints the module scope on demand, so asking who owns a
  *string* — which happens before anybody knows whether it is a fact — minted it for every
  file with a module-level string. Preparing the scope is separate from claiming it now.
  `LiteralKind` tells a glob from an interpolation placeholder, `reports_literals` stops
  being a field nobody reads, and the bound's floor is **3 rather than 6**, measured:
  six is SQL's own and would put a four-character filename outside the map to save 1.6% of
  the payload. `SCHEMA_VERSION` is **11**. **1,670 passed · 1 skipped**, mypy clean over
  173 files, ruff clean.
* **`dunneflow mcp`** — the whole of `PLAN-v2.md` §3, brought forward and shipped. Twelve
  tools, two resources, one base at a time with `programs`/`open` as the topbar's controls,
  and `analyze`/`analysis_status`/`analysis_stop` for making a map rather than reading one.
  `.mcp.json` is committed, so a session started in this tree finds it. **1,529 passed ·
  1 skipped**, mypy clean over 156 files, ruff clean; the golden has not moved.

* **Supplied edges.** The TypeScript checker names the far end of a call and the host turns
  the location into an id — `edges`/`edge`/`edges_done`, a `ts.Program` per `tsconfig.json`
  built in `open`, and `resolve/typescript/calls.py`. DunneNote goes from **0 internal edges
  to 1,935**, 38% internal, every one of them supplied rather than guessed and **0 ambiguous**;
  twelve were read against the source by hand, including an import alias that collides with a
  local name and a method reached through a typed receiver — two cases a name could not get
  right. Python unmoved (**7 of 7 digests**) and extraction unmoved: all of chunk 9's figures
  reproduce exactly. `SCHEMA_VERSION` is **13**. **1,727 passed · 1 skipped**, mypy clean over
  178 files, ruff clean; the frozen binary and the checkout stamp the same two fingerprints
  and open each other's maps.

  **Rule 97 is the defect of the chunk**: the bundled compiler was shipping without its own
  `lib*.d.ts`, which esbuild cannot carry because the compiler opens them **by path**. It
  does not refuse — it builds a program with no `Array` and no DOM and answers anyway, four
  edges short, and what it loses is not the map but the *account*: 2,587 calls move from *the
  reader could not say* to *these go to `Math` and the DOM*. Found by splitting one residue
  into its two reasons (design rule 21), not by a test.

  Four more: `ResolveStats.external` had stopped counting external calls in the chunk 6 split,
  so Society's recorded *4,063 external* was the `at_boundary` count and the true figure is
  **24,103**; `respawn` re-opened a worker without its rules; the `opened` frame's
  `diagnostics` and `program_ms` had been discarded since chunk 7; and nothing checked that
  the committed bundle was the committed source (rule 37), which this chunk closed before it
  edited either.

* **TSX and React.** A JSX element whose tag names a value is a call — the props are its
  keyword arguments and the checker names the far end — so a React program's component tree
  is in the map at last. **DunneCorp: 173 component elements**, and the arithmetic closes
  (215 capitalised tags by grep, minus 42 that are type names in generic positions);
  **36 ways in** where a Next.js tree declares them by where its files sit, all 33 route
  names printed and read with no `(group)` surviving into one; **boundaries the spelling
  rules cannot reach**, matched on the package the checker resolved a call into, which is
  NETWORK 0 → 12, CLOUD_SDK 1 → 4 and 130 DATABASE rows that name the Prisma model instead
  of a fragment of an argument; a hook's callback is a routine nested in its component; and
  the map **states what it does not claim** — 27 routines in 8 files marked `use server`,
  with the query that returns exactly 27.

  Three defects, and two were not on any list. A **`.d.ts` is not program source**: uigen
  vendors a generated Prisma client as one, and read as code it contributed 422 bodyless
  routines and **83 BROKEN anomalies** out of a command that gates CI on BROKEN.
  **112 of DunneCorp's 403 internal edges were a routine calling itself** — `const [x, setX]
  = useState()` is the commonest line in React, and the checker's declaration for `setX` is
  a binding inside the component; four declaration shapes and one stopping condition in the
  climb, measured one at a time, and the twelve self-calls left across three corpora are all
  genuine recursion. And **chunk 11d shipped a false BROKEN itself** before the qualname
  carried the ordinal that tells two effects apart.

  Python unmoved (**7 of 7 digests**), the frozen binary reads DunneCorp to the figure and
  both builds open each other's maps. **1,753 passed · 1 skipped**, mypy clean over 179
  files, ruff clean. `SCHEMA_VERSION` stays **13**; the TypeScript reader is **1.1.0**.

* **Manifest providers.** `resolve/manifests/`, six providers one per filename, and the
  `pyproject.toml` walk-up generalised to any of them. **Discovery is the whole tree** —
  Tom's criterion, *any module that has inputs and/or outputs is included, because that is
  flow* — collected off the listing `walk.discover` already took, so `SKIP_DIRS`, dotted
  directories and maps are pruned once (rule 92). **DunneNote goes from no version and no
  way in to 0.9.0 with two witnesses and four ways in**; DunneCorp and uigen record 0.1.0
  where they recorded nothing. `"scripts"` is never a way in and 31 across four corpora are
  declined by name. `Entrypoint.declared` is a **field** at last, which is the last of the
  four confirmed v1 defects: it was `"[project.scripts]" in e.evidence`, and two sites went
  further and parsed the sentence back for a target `target_expr` already held.
  `SCHEMA_VERSION` is **14**. **1,798 passed · 1 skipped**, mypy clean over 188 files, ruff
  clean, **7 of 7 golden digests identical**, and both builds stamp
  `14:c6cd0c4e1d15e9e3` and `1.1.0:92eb0d173e9807a7`.

  **Rule 98 is the defect of the chunk, and it is chunk 11's twice over.** A detector
  unchanged for a year began calling DunneNote's `dunnenote-host` *leads nowhere* — the
  front door of that application, in a language this build has no reader for. Admitting a
  new kind of fact re-runs every judgement against a population it has never seen, exactly
  as `.d.ts` turned uigen's Prisma client into 83 BROKEN. The remedy is
  `binding_note`'s **five answers, of which one is a fault**. Rule 99 came from beads-main,
  a corpus no chunk had read: a nested manifest's module name is relative to *its* root and
  not the analysed tree's. Three more were found by running it — `ways_in` dropped every
  unbound declaration, `_flows` then crashed on `roots[0]`, and the zone map counted one.

* **Open question 6 — the naming lanes across a mixed corpus.** Answered on DunneFlow's own
  tree, 107 Python files and 11 TypeScript. Yes, the spelling lanes need splitting:
  *"routines are named in snake_case, **1,014 of 1,114**"*, a D with 100 exceptions, is two
  conventions — **982 of 998** and **116 of 116** — and every one of the 100 was a
  TypeScript name spelled the way TypeScript spells names. CASE, the gaps and HOUSE_PREFIX
  carry a language now; AFFIX and LEAKAGE deliberately do not, because an affix is a word a
  team chose rather than a way of spelling one and the privacy population is
  `visibility = 'private'`, which the TypeScript reader never records (0 of 122).
  Conformance splits an unscoped stated rule the same way, each result carrying a
  **blind spot** — the distinction from its path-scope refusal is that nothing supplies
  which *paths* a rule governs and **the map does supply which languages it holds**.
  A standard declaring `paths: ['**/*.py']` has closed the axis itself and is never
  labelled. A map holding one language is untouched throughout.

  **But the premise was narrower than the defect, and that is the finding.** Splitting alone
  would have replaced a false `D` with a false *gap*: the shared spelling judge returned
  **one** answer where a one-token name has several true ones — `widget` is snake_case,
  camelCase and kebab-case — and settled the tie by the order five `if`s were written in,
  which is Python's (**rule 100**). It was **already wrong on a single-language TypeScript
  map** and had been since chunk 9: DunneNote's routines read 1,151 of 1,348 where the
  figure is **1,297**, and its parameters were reported as having no convention at all where
  **515 of 519** are camelCase. Two more: a dotted name was judged by substituting `.` for
  `_`, which is why **387 of DunneNote's 389** unreadable module names contain a dash; and
  the kebab predicate required a dash, so it returned 14 rows to prove a claim of 16 of 16
  and no corpus had ever been able to run it (rule 13).

  Three found by running it: two population queries had no `WHERE` at all, so the language
  clause was a syntax error and the whole suite passed because no fixture held two
  languages; the split **lost a row** — `dunneflow` is declared in `pyproject.toml`, which
  has no row in `files`, so it belonged to no language and the report read *15 commands*
  over a map holding 16 (rule 32); and `dotted` was read off a label that now carries a
  language in front of it. Nothing invalidates a stored map — `resolve/` is in no
  fingerprint and `SCHEMA_VERSION` stays **14**. Mensores byte-identical in all eight
  populations, **7 of 7 golden digests**, verified in the dashboard as well as the CLI.
  **1,813 passed · 1 skipped**, mypy clean over 189 files, ruff clean.

* **Chunk 13 — packaging, and the gate that had been broken for eight chunks.** The spec
  already bundled `plugins/` from the manifests, so the half that was left was the
  fingerprint-equality gate — and it turned out to be a repair before it was an extension.
  Chunk 5 split `rules_fingerprint()` in two; both scripts that asked the question asked it
  by writing `from dunneflow.detectors import rules_fingerprint` into a here-doc and a `-c`
  argument, so the rename did not touch them and **`release-linux.sh verify` and
  `release.ps1` have been raising `ImportError` ever since** — in the step written to defend
  rule 12, on no test path. macOS had no fingerprint check at all, on the platform whose
  builds are signed, notarised and handed to somebody. And both probe trees were Python to
  the last file, so **no script had ever compared a TypeScript stamp**: they would have
  passed on a build whose TypeScript maps the checkout refuses (rule 37, in the step whose
  own comment quotes rule 37).

  `tools/fingerprints.py` is the one place the question is asked, and the three scripts run
  it. It **opens each build's map with the other build** rather than diffing two hex strings
  — what a colleague meets is `Store(writable=False)` raising, and those sentences already
  name the language and say re-analysing costs only that language. No language is named in
  it (rule 92): the list is `ingest.PLUGINS`. **A language that contributed no rows is a
  refusal**, with three answers and not two (design rule 21) — the tree holds none, the
  reader could not run, or it ran and disagrees, the middle one quoting the toolchain
  sentence out of the plugin's own manifest.

  Pressed in all four ways it can fail, against a copy of the real build with one bundled
  file perturbed — including chunk 5's partial discard made visible: core and python
  unmoved, typescript at `1.1.0:af854a44b61588eb` against `1.1.0:92eb0d173e9807a7`, and only
  that reader's rows refused. The two tests that matter read the *scripts*, because none
  ever had: no release script names a Python symbol at all, and every one of the three runs
  the gate. Both halves fail at the previous commit.

  **7.8 s** for the gate, 14.0 s for the build. Binary and checkout agree on
  `14:c6cd0c4e1d15e9e3`, `1.0.0:cd8f8435300e2ec5` and `1.1.0:92eb0d173e9807a7`, which are
  chunk 12's hand-taken figures reproduced by the script that now takes them. The frozen
  binary reads three trees to the recorded figure: DunneNote 1,518 routines · 708
  structures · 1,867 internal calls · 4 ways in at 0.9.0, DunneCorp **36 ways in** and
  **291 internal calls** (chunk 11's 403 less the 112 self-calls it fixed), Society **7 of 7
  golden digests**. **1,830 passed · 1 skipped**, mypy clean over 191 files, ruff clean.

  **A second defect in the same file, hidden by a filesystem.** `require_universal` — which
  gates `sign`, `notarize`, `dmg` and `install` — looked for the executable at
  `${APP_NAME%.app}`, which is `DunneFlow`, where the spec builds `dunneflow`. It has worked
  for a year because APFS is case-insensitive *by default*; formatted case-sensitive, every
  step after `build` refuses a good bundle saying there is no executable. `BIN` is the one
  spelling now, pinned against `EXE(name=…)`.

  **One recorded figure was one out, and it is chunk 11's doing.** `PLAN-v2.md`'s chunk 9
  amendment records DunneNote as *443 read + 315 tests = 758*; it is **442** today, in both
  builds alike, so it is not a packaging fact. `legacy/v0.1/src/vite-env.d.ts` is the file,
  and chunk 11's `skip_names` moved it — the rule that took uigen's Prisma client and its 83
  false BROKEN out of the map. Three categories where the line was written knowing two, and
  the arithmetic still closes: 442 + 315 + 1. Corrected in place there.

* **Chunk 14 — the documentation, and the flag two refusals had been promising.** The last
  chunk in the plan. **"Adding a language" said the same four lines for a year** — *write
  one extractor that emits `FileFacts`; nothing else changes* — and that was a claim about a
  tool nobody had asked. It is now the six things to do, what a plugin gets free and must
  not reimplement, and three things that will bite, each of the three a rule this tree paid
  for. `ingest/`, `plugins/<lang>/` and a corrected `canonical/` joined the architecture
  list; `detectors/*.yaml` and `resolve/` gained the per-language halves they had grown.

  **The promise at the top of it is asserted rather than claimed.** *Nothing above the graph
  names a language*: two renderers and forty-odd dashboard modules hold **not one string
  constant** spelling a language, and neither does `walk.py`, which used to open with `from
  .extractors.python.extract import extract_file`. Held by `tests/test_languages.py`, off
  `PLUGINS` rather than a list of names, reading **constants** and not the text (rules 34
  and 43). Under `resolve/`, `RESOLVERS` and a language's own package name one
  legitimately and **`traceability.py` does not** — it asks Python's builtins of every
  corpus, which is open question 6's shape one module over, unmeasured, and pinned at one so
  it cannot grow quietly.

  **`--without <lang>` is wired, and it is why the chunk was more than documentation.**
  Writing the chapter about refusals found that `ingest/outofprocess.py` had been telling a
  reader with no Node to *"run again with `--without typescript`"* since chunk 9 — and the
  flag did not exist. `declined` was a parameter on three functions that **no caller had
  ever passed**: rule 35 in an argument, and rule 89 broken by the sentence written to keep
  it. Tom's call was to wire it. `ingest.decline()` is the one place a name is judged, with
  two refusals — an unknown language, and declining them all — and `declined` filters
  **last** in `discover`, because taken off `rules` a declined language's files would be
  tallied as *no reader here claims `.ts`*, said by a build that has one (design rule 21).
  Measured: **107 read, 11 declined** on DunneFlow's own tree, 118 accounted for, and 0.8 s
  against 3.7 s because Node is never started. The map records it on `analysis_args`.

  **The user guide gained the subject it had no word for.** *Two languages* appeared nowhere
  in 4,009 lines of documentation; three chapters now carry it. Writing them found a second
  gap, **stated rather than fixed**: `_emit` writes to stderr and `serve` runs the analysis
  `--quiet`, so **the walk's residue never reaches the dialog** — design rule 1 holds for
  the command line and not for the surface the tool is actually for. A chunk of its own.

  **The tutorial is dated rather than re-taken**, Tom's call: the 21 screenshots are
  hand-composed captures from 15 September and this session could not drive a browser. Its
  front page already cited the commit; what it also said was *"every number on every page is
  one you can reproduce"*, which had stopped being true. **Chapter 10 is rewritten** because
  it changed *shape* — fifteen conventions where the screenshot shows seven — and the
  interesting part is what the split replaced: measured across both languages at once,
  *"routines are named in snake_case"* is **1,014 of 1,114**, a `D` whose hundred exceptions
  are all TypeScript names spelled the way TypeScript spells names.

  **The core key moved**, `14:c6cd0c4e1d15e9e3` → **`14:d273f41c746d39d2`**, because
  `ingest/__init__.py` is in it. Correct and conservative — `decline()` cannot change a
  fact, and over-invalidating is rule 12's safe direction — and it costs one re-analysis.
  **7 of 7 golden digests identical**, so nothing moved with it, and chunk 13's gate caught
  the move on the next run with both builds agreeing at the new value. **1,840 passed · 1
  skipped**, mypy clean over 191 files, ruff clean.

## The gate everything is measured against

`output/GOLDEN-v1.txt` holds row counts, distributions, and **seven identity digests** —
sorted `routines.id`, `structures.id`, `entrypoints.id`, `calls.site_id`,
`control.point_id`, plus body hashes and resolved-call tuples.

`make_id` is derived from names and never from positions, so **while `extractors/python/`
is unchanged, every one of those digests must stay byte-identical.** Not "the counts should
match" — a total can hold while its contents swap.

**The script is `tools/golden.py`**, written 2026-09-17, because the one this file used to
point at — "recorded in `HANDOFF.md`'s v2 entries" — was never written, so the gate could be
read and not run. It regenerates the report byte-for-byte apart from two digests:
`routines.body` and `calls.resolved` record a value whose statement was not recorded and was
not recovered by a **bounded** sweep — column permutations up to three wide over ten
candidate columns, six orderings, ten field-and-row separators and three renderings of
NULL. Bounded, not exhaustive: the search space is larger than that and was abandoned
rather than finished, which is worth saying plainly because "we could not find it" and
"it is not there" are different claims. So both are **redefined in that file** and are
compared graph to graph rather than against the report.
The other five reproduce exactly, which is what says the serialisation there is the
original's and not a second convention that happens to be self-consistent.

```bash
uv run python tools/golden.py output/mensores-v1/graph@*.db --against output/GOLDEN-v1.txt
uv run python tools/golden.py <v1.db> <v2.db>    # the gate: all seven, both sides computed here
```

Two of the baseline's figures reproduce numbers written in `CLAUDE.md` exactly — 43,926 call
arguments over 30,544 call sites, and 9,625 control points — which is what says the baseline
is faithful rather than merely plausible.

## What is next

**The MCP server was brought forward** on 2026-09-17, from `PLAN-v2.md`'s chunk 4 to the
front, and the walk was wired behind it the same day — so the ordering that remains is the
plan's own, and chunks 5 through 9 were taken in it. Tom's call on the front-loading, and his reasoning is recorded: the existing
tool is usable as-is, so v1 defects found along the way are rolled into whichever feature
chunk owns them rather than scheduled as work of their own.

**All fourteen chunks in `PLAN-v2.md` are done, and so is the run-to-run instability
below.** What this tree still owes is in **`BACKLOG.md`** — eight open items and eight
stated residues, each with where it came from, why it was not done, and what would settle
it. It is there rather than here so that there is one place to read it, and this file does
not carry a copy that drifts.

The largest of them, in one line each: the tutorial's **21 screenshots** are a dated
session and want a re-capture; the **analyse dialog cannot see the walk's residue**, so
design rule 1 holds for the command line and not for the application; and the **comparison
lane is probed against a pair differing in three source files**, which is a real result
from a small population.

**`web/`'s own ordering defect is closed** (2026-09-18). All 43 GET routes answer the same
thing under a full row reversal, on Society across two revisions, on DunneFlow's own mixed
tree and on a fixture built out of ties — `tools/ordering.py --api`, beside the map probe
and a `--survey` that counts what no `ORDER BY` defends (50 findings before, 36 after). Two
of the three biggest defects were queries that *had* an `ORDER BY`, on a column with ties,
and two were not in `web/` at all; of the nine sites the backlog named, one was real. The
worst was `anomalies.py` reporting *"(lines 23,18). The later definition shadows the
earlier"* — **rule 102**, a sentence about an order built on `GROUP_CONCAT`, which has
none. **Rule 101** is the miss that probe made first: a route is not a branch, and it
reported `/api/wayin` clean over the one site the backlog had called certain.

**The fifth v1 defect is closed** — the one chunk 8's gate found and left alone. The
rendered map depended on the order its rows happened to be in, so two analyses of Society by
the same build wrote different documents; nineteen undefended ties across nine modules
(rule 66), and the two largest were queries with no `ORDER BY` **at all**, one of which
decided which routines a flow diagram draws. Measured: every document byte-identical under a
full row reversal, and two real analyses now differing in **nothing**. `tools/ordering.py`
is the probe and `tests/test_ordering.py` is the gate; **7 of 7 golden digests** say no
stored fact moved, and no stamp moved, so no stored map is invalidated.

**All four confirmed v1 defects are closed.** `BKIND_GLYPH` went in `679d772`;
`writable=False` now opens `?mode=ro` and genuinely refuses a write, which is what the MCP
`query` tool needed; and `is_test_path` is gone, replaced by `DiscoveryRules.is_test` per
language, so `client.test.ts` is a test rather than 42% of a corpus read as program code.
And the fourth went with chunk 12: `flows.py:259`'s substring test for *declared* is a
field on `Entrypoint`, set by the provider that read the manifest — which is the first
point a `package.json` `bin` exists to outrank a guessed `main`. Two sites nearby were
doing worse than testing that sentence: they **parsed** it back with `rsplit("= ", 1)` for
a target `target_expr` had been carrying all along.

**Three backlog items are closed** (2026-09-18) and two rules came out of them. `/api/programs`
listed every program twice under a symlinked maps root — `program_dirs` resolves its root now,
and **rule 103** is the family rule 60 and 93 belong to: a path is not a key until it is
canonical, and a set cannot deduplicate what does not compare equal. Making the flaky MCP slot
test deterministic found **rule 104**: `analysis_running` asked the child and nothing else, so
between a claim and its `Popen` a second analysis claimed the same slot, overwrote the report
and left the first child unreachable and still writing. And **the walk's residue reaches the
application at last** — *unread: 4,120 `.go`*, *left out as tests* — on the `--progress-json`
stream, carried across the whole-report replacement, and recorded on the map so *About this
map* can say it after the panel is gone, in three answers rather than two. **Design rule 31**
is the panel measured while doing it: fixed to the bottom, it grows upward, and fourteen lines
of residue put its head and its Stop button at **-71px**.

## Three things not to re-open

* **The rule numbers.** Addresses, not an ordering. v2 continues at 103.
* **No `BROWSER` boundary kind.** Settled on measurement — `BoundaryKind` is read in only six
  places outside `schema.py`, but changing the enum changes the meaning of a fact and
  discards every stored map; and it is not needed. `fetch`/WebSocket are the network under
  another name, `localStorage`/IndexedDB/cookies are persistent named storage shared across
  an origin, and the DOM is the program's own output rather than its environment. The
  residue is stated in words instead.
* **The seed came from the working tree, not HEAD.** Deliberate, and recorded in `e6da9b5`.
