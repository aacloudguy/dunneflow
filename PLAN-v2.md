# DunneFlow v2 — polyglot ingest, plugin-shaped, API-first

## Context

DunneFlow reads Python and nothing else. Its own design says otherwise — `schema.py`
opens with *"Every extractor, whatever the language, emits exactly these types"* — and
that claim is half true in a way worth stating precisely, because it decides how much of
this is a rewrite and how much is a wiring job.

**What is already true.** `FileFacts` is a genuinely language-neutral contract.
`store.py` carries a `lang` column on `files`, `routines` and `structures`, `sourcedb.py`
on `paths`, and `Store.known_langs()` already feeds the source sidecar.
`detectors/<lang>.yaml` + `load_rules(lang)` is parameterised — a `typescript.yaml` would
load today. `sql.py`, `extractors/docs/`, `resolve/shape.py`, `anomalies.py`, `render/`
and almost all of `web/` read stored facts and never syntax: `shape.judge()` bands a
control point from line ranges alone, so a plugin that emits spans gets the whole
Algorithms feature free. The code browser draws numbered lines and underlines calls from
`calls.callee_id` — there is no syntax highlighter to teach. `canonical/__init__.py` is a
correct, documented, suffix-dispatched plugin seam, and **its docstring is already the
design statement for this work**: a suffix table, a dispatch table, and a named honest
answer when nobody claims the suffix.

**What is not.** *Nothing anywhere branches on `lang`.* Verified: across all of `src/`
there is not one `WHERE lang =` or `GROUP BY lang`. It is written, stored, selected and
shipped to the browser as a display string, and never read by a condition. So every
Python-specific rule in `resolve/` applies unconditionally to every row — that, and not
any individual hardcoded `.py`, is the structural problem. There is no extractor
registry: `walk.py:23` imports `extract_file` directly and `discover()`'s
`suffixes=frozenset({".py"})` at `walk.py:111` is never overridden by its only caller.
`resolve/calls.py:33` uses `dir(builtins)` of *DunneFlow's own interpreter* as an oracle,
so a TypeScript call to `map`, `filter`, `open`, `type` or `next` would be silently
dropped. And `schema.py:222`/`:478` default `lang="python"`, so a plugin that forgets to
set it silently claims Python.

The tool already names what it is missing, in the product: `resolve/mirror.py:221` — *"only
Python is extracted, so a word living in a shell script, a template, a front end or a
sibling program is absent from this graph and present in the product."* Closing that is
the outcome wanted: a version a new language joins by **registration** rather than by a
rewrite, keeping every analysis surface already built, and drivable by a coding agent
over MCP. v1 stays on disk, untouched and serving, throughout.

## Decisions taken

| | |
|---|---|
| **Where** | Sibling clone, fresh history, at `../DunneFlow-v2`. v1 is never edited. |
| **Parsers** | Out-of-process plugins over native toolchains. Python stays in-process on stdlib `ast`. |
| **API** | A hand-written stdlib MCP server over stdio. |
| **First language** | TypeScript, then React/TSX. |

Two were settled by measurement, and it is the same measurement twice. `tree-sitter`
ships **no macOS universal2 wheel** — `macosx_10_9_x86_64` and `macosx_11_0_arm64` only —
and neither does `pydantic-core`, which the official `mcp` SDK requires along with
starlette, uvicorn, httpx2, jsonschema and opentelemetry. DunneFlow's entire runtime
dependency list is `pyyaml`, it freezes to a universal2 bundle, and
`packaging/dunneflow.spec:230` already excludes PyYAML's C extension for exactly this
reason. Both candidates hit that wall, and unlike PyYAML neither has a pure-Python
fallback to hide behind.

---

## Amendments — 2026-09-17, after the plan was approved

A second design pass reported after approval. Everything below was **verified against the
code or the corpus by hand**, not taken on report, and each one changes what gets built.

**Four defects in v1, all confirmed.** They are not blockers, but three of them are things
v2 must get right on day one rather than inherit:

1. **`is_test_path` does not recognise a TypeScript test.** `Path("client.test.ts").stem`
   is `"client.test"`, which matches neither `startswith("test_")` nor `endswith("_test")`.
   Measured on DunneNote: **322 of 767 `.ts` files are `*.test.ts`/`*.spec.ts` — 42% of the
   corpus** — and every one would be admitted as program code, inflating routines,
   conventions and dead-code numbers. §1h's per-plugin test markers already cover it; the
   *size* is what is new.
2. **`BKIND_GLYPH` in `shell.js:4612` spells the key `CLOUD`; the enum value is
   `CLOUD_SDK`.** So every CLOUD_SDK boundary on screen already draws the neutral
   missing-glyph mark `◦`, and the `|| "◦"` fallback is what hid it — rule 49 in the
   product, live today. Fix it in chunk 1 and carry the fix back to v1.
3. **`resolve/flows.py:215` decides whether a way in is *declared* with
   `"[project.scripts]" in e.evidence`** — a substring test against a prose sentence that
   `web/waysin.py:120` renders verbatim. A `package.json` `bin` will never match, so every
   declared TypeScript executable would rank below a guessed `main`. `declared` must become
   a **field** on `Entrypoint`, set by the provider that read the manifest. That is rule 30
   exactly, and it is a **candidate for rule 97**.
4. **`writable=False` does not make the connection read-only.** `store.py:528` opens an
   ordinary `sqlite3.connect(self.path, …)`, and `Store.query:1180` passes SQL straight to
   `conn.execute`. `writable` chooses only refuse-vs-discard on staleness. So
   `dunneflow query --sql "DELETE FROM routines"` works today. Tolerable when a human types
   it; **not** tolerable when a language model composes it. §3's `query` tool therefore
   gets two defences, not one: a `Store(readonly=True)` opening
   `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` so a write fails in SQLite rather
   than in a guard someone can forget, **and** `sql.py` classification refusing any
   statement whose direction is not READ, by name. Belt and braces is justified exactly
   once, and this is the place.

**Open question 1 is answered: no `BROWSER` kind.** The consumption was measured —
`BoundaryKind` is read in only six places outside `schema.py`, two of them literals
(`render/network.py:106`, `web/code.py:313`) that would silently omit a new kind, and
`store.py` has no `CHECK` constraint, so there is no migration. Cheap in code — but
changing the enum changes the meaning of an extracted fact, which bumps `SCHEMA_VERSION`
and discards every stored map. And it is not needed: three things hide under "the
browser", and only one has no home. `fetch`/WebSocket are **the network by another name**;
`localStorage`/IndexedDB/cookies are **persistent named storage shared across an origin**,
which is what DATABASE means, with `target` carrying the `localStorage:` prefix so no
reader is misled. The third is the DOM — and the DOM is not the environment, it is the
program's own rendered output; 550 Svelte files' worth of `querySelector` would be ten
thousand rows drowning the panel they were added to (rule 1). The handful of DOM APIs that
genuinely are boundaries land on existing kinds, and **the residue is stated in words**:
DunneFlow does not report DOM access.

**Two new risks, both real:**

- **`make_id` must be byte-identical across the process boundary.** The plugin has to
  reproduce `blake2b(parts joined by \x00, digest_size=8)` in Node —
  `crypto.createHash('blake2b512', { outputLength: 8 })`. Two implementations of one hash
  is rule 51's warning, and it is unavoidable across a process boundary, so it gets a
  **shared fixture**: ten vectors generated by `schema.make_id`, asserted from both sides.
- **A TypeScript `module` has no dots, and `web/graph.py:132 root_package` elects a first
  dotted segment covering every file.** Spelling `module` as the path with `/` → `.` gives
  DunneNote three package plates for 767 files — coarse but not wrong, and the same answer
  analysing the parent directory would give. The better fix is a `FileFacts.package` filled
  from the nearest `package.json` `name`, which is rule 85's shape (an extractor can read a
  manifest; a resolver cannot). It touches `graph.py`, `packages.py` and `queries.py`, so
  it is **its own chunk with its own measurement** — plate count before and after — and is
  deliberately off the critical path.

**Ground truth, corrected.** DunneNote is **445 program `.ts` files**, not 767, once the
322 tests come out. And its Tauri seam gives the single best assertion available: **30
files import `@tauri-apps/api/core`, of which 29 are tests** — so exactly one program file,
`apps/desktop/src/lib/pl/client.ts`, and *the repo's own `client.test.ts` asserts that
single-seam property*. It is independently-verified ground truth, and it is two claims in
one: the seam only reads as a single seam if test exclusion works. `fetch` likewise appears
exactly once in non-test `.ts`.

**The React corpus may change** — see the note at the end of §5.

---

## 0. Seeding the tree

**Pre-flight, in v1, before anything is copied.** `git status` shows **22 modified
documentation files** (295 insertions, 292 deletions) uncommitted on `main`. Commit or
stash them first, so the seed is a named state.

Then copy v1's **tracked files** (274; `output/`, `dist/`, `build/` and the virtualenvs
are ignored and must not travel), `git init`, one first commit naming the v1 commit it
came from. **Local-only to begin with** — `aacloudguy/dunneflow` is private on GitHub and
creating a second repository is your call.

**Carried verbatim:** `RULES.md` with numbering **intact** — the numbers are addresses,
never reused, ~3,326 citations point at them, and v2 continues at rule 95.
`DESIGN-RULES.md` likewise. `PERFORMANCE.md` carries over with **every figure marked as
v1's**; a number measured on a different tree restated as this one's is rule 24.

**Rewritten day one:** `CLAUDE.md`'s Architecture and Commands, and in particular the
**"Adding a language"** section, which currently reads *"Write one extractor that emits
`FileFacts`. Nothing else changes"* — true for an in-process language and materially
incomplete for an out-of-process one. A fresh `BRIEFING.md` whose "what we are doing now"
is this plan; `HANDOFF.md` starts empty pointing at v1's as the prior record.

---

## 1. The architecture

The whole design is `canonical/__init__.py`'s shape repeated four times — ingest,
resolution, discovery, manifests — plus one thing a canonicaliser never needs: a plugin
whose reader is **out of process** must contribute to the cache key honestly and must
refuse by name when its toolchain is absent.

### Module layout

```
src/dunneflow/
  ingest/
    __init__.py      LANG_SUFFIX, PLUGINS, language_of(), plugin_for(), enabled()
    contract.py      IngestPlugin Protocol; ToolchainMissing, PluginRefused, ProtocolError
    manifest.py      PluginManifest — read and validate plugin.json
    codec.py         FileFacts <-> JSON, reflective over dataclasses.fields(), strict
    worker.py        NdjsonWorker: spawn, handshake, correlate, drain stderr, respawn once
    inprocess.py     wraps a Python callable, keeps today's ProcessPoolExecutor intact
    outofprocess.py  one or more NdjsonWorkers
    discovery.py     DiscoveryRules; suffix union; per-language test markers
    dotted.py        THE normalisation contract — docstring plus conformance fixtures
    literals.py      host-side scanning of reported string literals
  plugins/
    python/plugin.json
    typescript/{plugin.json, package.json, src/*.mts, main.bundle.mjs}
  resolve/
    __init__.py      RESOLVERS; the docstring defining CERTAIN/INFERRED per language
    contract.py      Resolver Protocol, ResolvedEdge
    calls.py         DRIVER ONLY: group by lang, hoist at_boundary, sum stats
    python/          today's calls.py, cli.py, version.py — verbatim
    typescript/      location -> routine_id for supplied edges
    manifests/       PROVIDERS table; pyproject, packagejson, cargo, swiftpm, gradle, gomod
```

**`plugins/` sits inside `src/dunneflow/`, not beside it**, and that is load-bearing
rather than tidy. `fingerprint_files` labels every input by its path relative to
`resource_root()`, and the spec puts the package under `dunneflow/` inside `_MEIPASS`
precisely so a binary's map and a checkout's map are the same map (rule 12). A plugins
directory outside the package cannot have that property.

### 1a. `lang` becomes a discriminator — do this first

- **Delete the two defaults** at `schema.py:222` and `:478`. Both fields already sit
  before every defaulted field, so this needs **zero field reordering**; mypy and the
  suite then name every construction site.
- **A plugin never sets `lang` on a nested record at all.** `FileFacts.lang` is the only
  place it travels; the codec stamps it onto every `Routine` and `DataStructure` on
  decode. A plugin cannot forget it and cannot disagree with itself. A plugin that *does*
  send it has its record refused — it is a host-derived field, and accepting it would be
  two answers to one question. `extract.py:1665` stops writing it per-routine too, and
  one `ingest.stamp_lang()` serves every plugin (rule 51).
- **The host verifies the claim**: `language_of(path) == facts.lang`, or the file is
  refused naming both (rule 30).
- **`load_rules(lang)` loses its default argument, and stops returning an empty
  `RuleSet` for a missing YAML.** For Python that branch never fires; for a new language
  it fires and every boundary silently disappears. The manifest declares
  `"rules": "typescript.yaml"` or `"rules": null` meaning *this language deliberately
  declares none*, and an undeclared language is **refused**.
- **The five hardcoded "only Python" claims become derived** from
  `SELECT DISTINCT lang FROM files`: `resolve/mirror.py:221`, `render/mirror.py:9` and
  `:115`, `cli.py:1080`, `render/traceability.py:312`. Cheapest proof the column works.
- Per-language counts surface in the summary, `--progress-json` and the corpus panel:
  `python 626 · typescript 412 · go 4,120 unclaimed · swift declined (no toolchain)`.
  A count must say what it counts (rule 32).

The mechanism for selecting per-language behaviour is then one function,
`ingest.language_of(path)`, feeding four tables of identical shape:

| Question | Table | Status |
|---|---|---|
| how does this language write an expression | `canonical.CANONICAL[lang]` | already correct |
| what are this language's rules | `detectors.load_rules(lang)` | already parameterised |
| how does this language resolve a call | `resolve.RESOLVERS[lang]` | **new** |
| what does this manifest declare | `resolve.manifests.PROVIDERS[filename]` | **new** |

### 1b. The registry

`ingest/__init__.py`, modelled line for line on `canonical/__init__.py`. **`LANG_SUFFIX`
moves here** and becomes *derived from the manifests* rather than declared — its current
comment, "here is the one place that consults it", stops being true the moment
`discover()` and the registry consult it, and rule 51 says move it to where all callers
pass. Two plugins claiming one suffix (`.js` is the plausible case) **refuses at import,
naming both**. Never first-wins.

**Discovery is `resource_root()/plugins/*/plugin.json`, read at import, and nothing
else.** No `pyproject.toml` entry-point group, for three reasons in descending weight:

1. **The frozen app has no site-packages to install into.** An entry-point group is live
   in a checkout and inert in the signed, notarised `.app` that is the shipped product.
   `runtime.py` exists as a whole module to stop exactly that split.
2. **Rule 12 cannot be satisfied.** `fingerprint_files` labels an input relative to
   `_PKG_ROOT` and falls back to `path.name` for anything outside
   (`detectors/__init__.py:447`). Two plugins each shipping `main.mjs` would hash under
   one label, and a wheel upgraded underneath you would move nothing.
3. **Ingest is a standing guarantee.** A test already asserts nothing under
   `extractors/`, `resolve/` or `canonical/` imports an HTTP client or an LLM SDK.
   Admitting arbitrary third-party code into ingest retires it.

No env-var override either: a second discovery path is a second place a plugin can enter
the fingerprint from.

### 1c. The wire protocol

**A static manifest *and* a runtime handshake — both, because rule 30: the manifest is a
label, the running process is the identity.** Any disagreement between the two on
protocol, schema version, lang, plugin version or capabilities refuses the language by
name, quoting both values.

`plugins/typescript/plugin.json` declares: lang, version, protocol, `schema_version`,
suffixes, its rules file, its toolchain (`command`, `probe`, `min_version`, and an
`install` sentence), its entry bundle, worker count, capabilities
(`supplies_edges`, `reports_literals`, `receiver_words`), discovery rules, and
`fingerprint` — **a list of named files, never a glob.** A glob over a missing directory
returns `[]`, and `fingerprint_files`' emptiness refusal would then blame the whole build
rather than the plugin; named files hit the second refusal, which is the sentence that
can act (rule 89).

**Two phases, and the phase boundary is the honest statement of what a TypeScript
plugin's unit of work is:**

```
→ {"t":"hello","protocol":1,"schema_version":9,"lang":"typescript","root":"/abs/tree"}
← {"t":"ready", ...version, toolchain, capabilities...}
→ {"t":"open","root":"/abs/tree","files":[ ...ALL 412... ],"hints":{"tsconfig":"..."}}
← {"t":"opened","files":412,"program_ms":3180,"diagnostics":[...]}
→ {"t":"extract","id":17,"path":"src/a.ts","hash":"9f3c…"}
← {"t":"facts","id":17,"hash":"9f3c…","facts":{ ...FileFacts... }}
→ {"t":"edges"}
← {"t":"edge","site_id":"…","caller_id":"…","target":{"file":"src/b.ts","line":88,"name":"save"},"how":"checker"}
← {"t":"edges_done","supplied":9014,"unresolved":221}
→ {"t":"close"}
```

`open` is given the **whole** file set so the type-checker is complete; `extract` is
asked only for the files whose content hash missed the cache. The incremental warm path
falls out of the design rather than being bolted on.

**Process-per-file is wrong, and the decisive reason is not startup cost.**
`ts.createProgram` plus checker construction is a per-*program* cost that dominates, and —
the real point — **the resolved-symbol information the plugin exists to provide only
exists inside a program.** A per-file process has no checker, so it is reduced to guessing
by name, which is the thing using the native toolchain is meant to stop.

**Parallelism.** `workers` is declared per plugin and defaults to 1 for TypeScript: each
worker needs its own program, and a program for a large monorepo is hundreds of megabytes.
The growth axis is **per-project, not per-file** — one worker per `tsconfig.json`, each
`open`ed with its own slice, which the protocol already expresses. Python keeps its
existing `ProcessPoolExecutor` untouched.

**Paths, not bodies** — the TS compiler host reads the disk itself, and must read files
the host never listed (`.d.ts`, type packages) to resolve imports. But the host's hash
travels with the request and the plugin **echoes back the hash of what it actually read**;
a mismatch means the file changed mid-run, and the facts are stored with an error rather
than filed under a hash they do not describe.

**Serialisation is a reflective codec** driven by `dataclasses.fields()` and
`get_type_hints` — not 25 hand-written pairs, for the reason `code_extraction_inputs()`'
own docstring gives: a hand-kept list drifts the moment someone adds a field. Fields equal
to their default are omitted, so 43,926 `CallArg`s do not each carry `"splat":false`.
Decoding is **strict**, each failure with its own answer: an unknown key is dropped *and
named in `FileFacts.errors`*; a missing required field refuses that record; an enum value
that is not a member refuses that record and quotes it — **never coerced, never
defaulted** (rule 49); a line that is not JSON refuses the language once, loudly, rather
than being skipped 600 times quietly.

And the drift is killed at source: `dunneflow ingest-schema --json` emits a descriptor of
`schema.py`, and the TypeScript plugin's types are **generated from it at build time**, so
a `SCHEMA_VERSION` bump breaks the plugin's build rather than its output.

**Failure policy matches the in-process one exactly.** A file that will not parse yields
`facts` with an error string and its content hash — which means it is cached and not
retried, existing Python behaviour, preserved deliberately. A plugin that *threw* on a
file yields `failed`, and **the host synthesises the `FileFacts`**: a plugin that has just
crashed on a file is not the right authority on what that file is. A worker that dies has
every outstanding id marked failed with the exit status and the last 4 KB of stderr, and
is respawned **once**; a second death refuses the language. stderr is drained on its own
thread into a ring buffer and **never parsed** — `_desktop_session`'s lesson in
`runtime.py` is the precedent: text a healthy process also writes cannot be a control
channel.

**Toolchain refusal** is probed once, at pre-flight, **before anything is opened** — the
placement `cli.py` already uses for `--standards`, so a refusal never abandons a
half-written map. The sentence names the language, the command, the minimum version, what
was found, **how many files will therefore not be read**, and both ways forward:

> typescript needs `node` ≥ 20.0.0 and nothing answers `node --version` on this machine.
> 412 files under `src/` claim `.ts`/`.tsx` and will not be read. Install it
> (`brew install node`, or nodejs.org), or run again with `--without typescript` — the map
> will then say those 412 files were declined.

Default is to **refuse the run**. `--without <lang>` is the only way past and it stamps
`meta.languages_declined`, so no later read can mistake a partial map for a whole one.

### 1d. The `dotted_name` contract — written down at last

`detectors/python.yaml`'s header already says rules match "the dotted form of a call
expression". That normalisation (`extract.py:91`) is the real, currently-undocumented
interface between any extractor and the rules, and a plugin that spells expressions
differently makes every YAML rule miss silently. It becomes `ingest/dotted.py`, whose
docstring *is* the contract:

1. source-order identifier chain, dot-joined: `a.b.c`
2. a call in the middle folds to its callee: `Path(p).read_text()` → `Path.read_text`
3. no name at the root → `""`, and `""` is **never** matched against a rule
4. **no resolution, no alias expansion** — rules match the written library prefix
   (rule 5), and a resolved name would silently stop matching
5. `a?.b!.c()` → `a.b.c` — nullability is not identity
6. `foo<T>()` → `foo`
7. `new Foo()` → `Foo`, plus a new `CallSite.is_construction`, so `new WebSocket(url)`
   and `WebSocket(url)` stay two facts (rule 30). False for Python.
8. the receiver word is written as written — `self.x`, `this.x` — and each language's
   resolver knows its own, declared in `capabilities.receiver_words`

Conformance: `tests/fixtures/dotted/cases.json`, run in-process against the Python
extractor and over the wire by `dunneflow ingest-conform <lang>`. **That fixture passing
is what makes the claim "a `typescript.yaml` loads with zero code change" true.**

### 1e. SQL, artefacts and network — scanned in the **host**

`FileFacts` gains a `literals: list[StringLiteral]` (routine, line, text whole and
untruncated per rule 8, kind). The plugin's job is to *find* string literals; the host
judges them, running today's `sql.py` and artefact matching in `ingest/literals.py`. The
Python extractor stops doing it inline and reports literals like everybody else.

Three reasons, and the first is the one that matters:

- **One answer to one question.** A plugin reimplementing `looks_like_sql` means the same
  string in a `.py` and a `.ts` file can be read two different ways — rule 51 in the fact
  contract, which is the most expensive place to have it.
- **`detectors/<lang>.yaml` stays the extension point.** Host-side scanning means a
  `typescript.yaml` edit moves `rules_fingerprint()` with no plugin rebuild.
- **It shrinks the plugin contract to one thing.** Once literals are host-side, the only
  rules-facing thing a plugin must get exactly right is `dotted_name` — one contract with
  one fixture instead of four.

What stays in the plugin is everything needing the AST: routines, call sites and argument
text, control points and arms, imports, structures, classes, boundary matches, and
`NetworkCall` (which needs kwargs, await-ness and the enclosing routine's asyncness —
none of which survive as a string). The plugin applies `_scan_sql`'s existing
`6 ≤ len ≤ 200_000` bound before sending, and **the count dropped by that bound is
reported** rather than silently filtered.

### 1f. Rule 12 — the fingerprint, split

| Key | Contents | Meaning |
|---|---|---|
| `meta.extractor` | `f"{SCHEMA_VERSION}:{fingerprint_files(core_extraction_inputs())}"` | the core: `detectors/*.yaml`, `detectors/__init__.py`, `ingest/*.py`, **`schema.py`** |
| `meta.extractor.<lang>` | `f"{plugin_version}:{fingerprint_files(manifest.fingerprint)}"` | one plugin's reader |
| `files.extractor` *(new column)* | the per-language stamp that read this row | what makes a partial discard possible |

`ingest/*.py` is in the core key and `canonical/` still is not — the test its docstring
already sets is *"what does this extraction actually read"*, and the codec, registry and
dispatcher all shape what a fact *is*, while a canonicaliser still cannot change one.
**`schema.py` joins the key**, which it is not in today; `SCHEMA_VERSION` is bumped by
hand and a forgotten bump is precisely rule 12's failure mode. It stays as the
human-readable generation marker and the protocol's declared version, and stops being
load-bearing.

**A plugin contributes version *and* file hash, and no toolchain.** A declared version
alone is a label (rule 30) that does not move when somebody edits the bundle during
development — exactly when it must. The named files are the **built bundle**, not the
source tree and never `node_modules`: `plugin.json` and `main.bundle.mjs`, identical in a
checkout and in `_MEIPASS`, so both builds stamp the same value at the same commit —
which is the property `runtime.py:37` exists to produce. **`node --version` is left out**
deliberately, because putting it in means every Node patch upgrade discards the TypeScript
half of every graph on the machine; it is a scope choice rather than a fallback, so rule
49 does not force it, and §5 says what would settle it.

**What happens when a stamp moves:** core differs → today's behaviour exactly, everything
dropped on write and refused on read. Core same, one language differs → `forget_file` over
that language's paths and re-extract, using no new destruction mechanism. **So editing the
TypeScript plugin does not discard the Python graph** — it costs a re-extraction of the
TypeScript half. `source.db` is untouched throughout (rule 25).

And the packaging lesson from rule 92: `packaging/dunneflow.spec:200` **enumerates**
`extractors/python` and `extractors/docs` by name. v2 bundles `plugins/` wholesale under
`dunneflow/plugins/`, and a test asserts every registered plugin's fingerprint files are
in `datas` — because a defence assembled from an enumeration does not survive a new
member.

### 1g. Per-language resolution

`resolve/calls.py` becomes a driver: join `calls` to `files` for `lang`, group, dispatch,
sum stats per language and in total. Two things **hoist into it** so a new resolver
inherits them rather than remembering them (rule 51): the `at_boundary` suppression
(`calls.py:166-176`, rule 2 — language-agnostic in principle, its evidence already coming
from `detectors/<lang>.yaml`), and the missing-target bookkeeping (`:246-256`) so there is
one place that writes `UPDATE calls SET callee_id` and a new resolver cannot invent a
fifth way to say "no edge".

**Python moves verbatim** to `resolve/python/`, gaining only a file-set filter. The gate
is a field-by-field golden diff over Society: every
`(rowid, callee_id, confidence, external, ambiguous)` tuple identical.

**One substantive Python change on the way past, and it must be measured rather than
assumed harmless.** `_BUILTINS = frozenset(dir(builtins))` introspects DunneFlow's own
interpreter. Dispatch fixes the cross-language half, but leaves a rule-12 hole even for
Python: the builtin set is a fact about the *analysing machine's* Python version
(`aiter`/`anext` arrived in 3.10, `ExceptionGroup` in 3.11), and it is an input to
extraction semantics that no fingerprint hashes. Move it into `detectors/python.yaml` as
declared data, where `rules_fingerprint()` already hashes it — and **record the diff on
Society**, never absorb it.

**TypeScript supplies edges rather than being re-guessed.** The checker already knows, so
`resolve/typescript/calls.py` is tiny: build `(file, line) → routine_id` from the routines
just stored and look each supplied edge up. **Targets are named by location, never by
id** — a plugin minting ids would be a second implementation of the identity function, in
the one place it is least recoverable. A supplied edge matching no stored routine is
**external**: the call certainly happens and we simply cannot see the other end, which is
rule 26 by construction rather than by luck. And a call site with **no** supplied edge is
left external, never guessed by name — that is the whole payoff of using the native
toolchain, and it is rule 1.

| | `CERTAIN` | `INFERRED` | external |
|---|---|---|---|
| **python** | import, enclosing module, or enclosing class | exactly one routine in the program has that name | unchanged |
| **typescript** | checker resolved the symbol to declarations all lying in one routine | **should essentially never occur** | resolved outside the program, or refused |

The TypeScript row is the opinionated part and it is right. Where the checker gives
several declarations — a merged overload set, an `any`-typed receiver, `obj[k]()` — the
honest answer is **external with the candidate count recorded in `ambiguous`**, exactly as
Python already does for a name collision. Not `INFERRED`: that is a claim that a
name-uniqueness argument was made, and for TypeScript none was made or needed. Marking a
TS edge `INFERRED` would blur precisely what rule 6 says never to blur. `ResolveStats`
gains `supplied: int` so the two provenances are countable side by side, and the
"Inferred facts: none" row at `GET /api/about` stays true.

### 1h. Discovery and manifests

`DiscoveryRules` per plugin: suffixes, skip dirs, test suffixes (matched at the **end** of
the filename), test stems (matched at an **edge**, preserving `is_test_path`'s hard-won
rule-5 precision — `_test_stage.py` is a pipeline stage, not a test), test dirs.

**Suffixes are a union. Skip dirs are *not*.** A TypeScript plugin adding `out` to a
global set would remove `out/` from the Python corpus too. So the walk prunes `dirnames`
only on the shared `SKIP_DIRS` — where every language genuinely agrees: `node_modules`,
`.git`, `target`, `Pods`, `DerivedData`, `vendor`, `obj`, `.gradle`, `.build`, `.turbo`,
all of which v1's *doc* skip set already has and its *code* set lacks — and a plugin's own
list applies at the **file** level, after `language_of(path)`. It costs a descent that
finds nothing, and it is the difference between a plugin contributing a filter and a
plugin shrinking somebody else's corpus.

**No filter is silent** (design rule 1). `WalkStats` gains four counters on the precedent
`nested` and `maps` already set: `skipped_dirs` (path and which rule pruned it),
`unclaimed` (suffix → count), `tests_excluded` (per language), `declined`
(lang → files and the refusal sentence). **`unclaimed` pays immediately**: point v2 at a
Go repo today and you get an empty map with no explanation; with it you get *"4,120 `.go`
files — no plugin claims `.go`"*.

**Manifest providers** replace the `pyproject.toml` walk-up at `cli.py:279-296`: walk up
for any file in `MANIFEST_FILES`. Two manifests at one level is the ordinary polyglot
repo, not an error — both are read, both contribute. Entrypoints and version are
**independent columns**: `go.mod` answers version and declares no entrypoint at all,
because Go's entrypoint is `func main` and belongs to the language plugin, and saying so
beats inventing one.

| Manifest | Entrypoints | Evidence sentence (verbatim, per provider) |
|---|---|---|
| `pyproject.toml` | `[project.scripts]`, `[project.gui-scripts]` | unchanged |
| `package.json` | **`bin` only** → CLI; `main`/`exports` → LIBRARY | `package.json "bin" dunneflow = ./cli.js` |
| `Cargo.toml` | `[[bin]]`, plus `src/main.rs` by convention | `Cargo.toml [[bin]] name = "x"` |
| `Package.swift` | `.executable` products | `Package.swift .executable(name: "x")` |
| `build.gradle.kts` | `application { mainClass.set("Foo") }`, **literal form only** | `build.gradle.kts application.mainClass = "Foo"` |
| `go.mod` | none | — (version and module only) |

Two precision calls worth stating now rather than discovering later. **`package.json`
`"scripts"` is not entrypoints** — it is a task runner, and admitting it would put
fourteen build commands in the ways-in panel beside real ones; `bin` is the contract with
whoever installs the program, `scripts` is a label (rule 30). And **`build.gradle.kts` is
a program, not a data file**, so only the literal `mainClass.set("Foo")` form is read and
anything computed is refused — which is `_from_dunder`'s reasoning verbatim
(`version.py:90`): reporting an expression as though it were the value would be a claim
about something nobody has evaluated.

The evidence string is rendered **verbatim** in the UI (`web/waysin.py:120` says so
explicitly), so it must come from the provider — a `package.json` entry claiming to come
from `pyproject.toml` is a visible falsehood.

**Two manifests declaring different versions** (a `package.json` at 2.0.0 beside a
`pyproject.toml` at 1.0.0): do not pick. Record both and say so on the cover. It is the
honest answer and also a signal — a tree with two disagreeing declared versions may be two
programs.

---

## 2. The TypeScript plugin

A pnpm package at `src/dunneflow/plugins/typescript/`, written in TypeScript, built by
esbuild into a **single `main.bundle.mjs` with the TypeScript compiler inlined**, and the
checkout runs the same bundle the app ships. That is what makes the fingerprint two named
files identical in a checkout and in `_MEIPASS`, and it means no `pnpm install` at
analysis time.

**Why the compiler API rather than a parser — measured on a real local corpus, not
asserted.** `../uigen/tsconfig.json` declares `paths: {"@/*": ["./src/*"]}` with
`moduleResolution: "bundler"`, and its source imports read `@/lib/prisma`. Any extractor
that is not the compiler has to reimplement TypeScript module resolution — path aliases,
`bundler` resolution, `exports` maps, extensionless imports — before it can say what a
single import refers to. The checker gives all of it, and gives symbol resolution on top.

### Fact mapping

| TS/React thing | Fact | Note |
|---|---|---|
| function, method, arrow assigned to a const | `Routine` | `qualname` carries the enclosing scope (rule 10); an anonymous default export needs a **stated** convention, not an invented name (rule 30) |
| React component | `Routine` | a component *is* a routine, not a new node kind |
| `fetch`, `axios.*`, `ky.*` | NETWORK + `NetworkCall` | straight into `typescript.yaml` |
| `process.env.X` | ENV | the analogue of `os.environ[...]`; `subscript` already exists as a match form |
| `node:fs`, `node:child_process` | FILE, PROCESS | |
| Prisma, `pg`, `better-sqlite3` | DATABASE | `uigen`'s server actions are the fixture |
| `@ai-sdk/*`, `@anthropic-ai/*`, `openai` | LLM_API | the kind already exists |
| `localStorage`, `IndexedDB`, `document`, `window` | **possibly a new `BROWSER` kind** | decide by counting, not by taste — see Open questions |
| Tauri `invoke("cmd")` | PROCESS (provisionally) | 6 files in DunneNote use it; it is an IPC call into a Rust backend |
| `interface`, `type X =`, `enum`, `class` | INTERFACE / TYPE_ALIAS / ENUM / CLASS | all already present |
| `package.json` `bin` | `Entrypoint` CLI | via the manifest provider |
| Next.js `app/**/route.ts`, Express handlers | HTTP_ROUTE | `uigen/src/app/api/chat/route.ts` |
| Next.js `page.tsx`, Vite/Svelte entry | MAIN | |
| `"use server"` actions | HTTP_ROUTE | it is called across the wire; that is what the kind means |
| `for`/`while`/`do`, `if`/`else`, `switch`, `try`/`catch`/`finally` | `ControlPoint` + `ControlArm` | `ArmKind` gains `catch`, `do`, `switch`. **It does not gain `elif`** — TS has no such word, and the enum's own docstring sets the rule: *"the word in the source, and nothing invented"*. Add values, never reuse |
| `.map` / `.filter` / `.forEach` chains | `COMPREHENSION` | a loop that is an expression — the judgement Python's comprehensions already get |

**The visible consequence of §1g worth predicting now:** design rule 5 draws CERTAIN
solid and INFERRED dashed. Because TypeScript edges come from the checker and ambiguity
resolves to *external* rather than to `INFERRED`, the TypeScript half of a mixed map will
read as an **entirely solid skeleton**. That is a true and useful difference between the
two languages, and the About page should say why rather than let it look like a rendering
bug.

### Out of scope for the first cut, deliberately

Rule 1 — precision beats recall; a detector whose first findings are limitations of the
tool must not ship.

- **JSX conditional rendering** (`{cond && <X/>}`, ternaries in JSX). It is a decision,
  but `shape.judge()`'s test is *does something move inside it*, and what moves is a
  rendered element, which this tool does not model. Recording them puts thousands of
  points on the worklist no reader can act on. Left out and **said out loud** on the
  Algorithms page rather than silently absent.
- **`useEffect` as a rate.** A `useEffect` containing a fetch genuinely is a rate in
  `shape.py`'s sense and is the most interesting thing React has to say — but it needs the
  dependency array read as part of the judgement to be worth anything, and that is a
  second feature. Deferred, and named in `BRIEFING.md` as open.
- **Type-level computation** (conditional and mapped types) — arithmetic, one level up.
- **`.svelte`, `.vue`, `.astro` single-file components.** DunneNote's `apps/desktop` holds
  **70 `.svelte` files carrying `<script lang="ts">`** with real imports and logic. They
  are part of the program and the TypeScript compiler cannot read them. They are reported
  **unclaimed by name and count**, which is the `unclaimed` counter earning its keep on
  the very first real corpus.

---

## 3. The MCP server

`dunneflow mcp` — a new subcommand. **Hand-written, stdlib only**: JSON-RPC 2.0,
newline-delimited over stdin/stdout, implementing `initialize`, the `initialized`
notification, `tools/list`, `tools/call`, `resources/list`, `resources/read` and `ping`,
with proper error objects.

The traps, each of which this codebase has already paid for once elsewhere: **stdout
carries protocol and nothing else** — every log line to stderr, which is exactly the
two-channel discipline `--progress-json` already proved across a process boundary; no
embedded newlines in a message; and MCP stdio is newline-delimited, **not** Content-Length
framed like LSP.

**Tools — small and sharp, aimed at an agent orienting in code it did not write**, not one
tool per endpoint:

| Tool | Answers |
|---|---|
| `analyze` | read a tree into a map. A long job: returns a **handle**, never a blocked call |
| `analysis_status` | poll that handle; relays the child's own NDJSON progress verbatim |
| `overview` | the cover: ways in, the biggest things, **which languages were read, which were declined, and what is unclaimed**, counts |
| `touches` / `impact` | what this routine reaches / what breaks if it changes |
| `routine` | one routine whole: signature, comments, boundaries, calls in and out, shape |
| `find` | names **and** text — the question the graph alone cannot answer |
| `glossary` | what the program's words mean, and who says so |
| `query` | raw SQL, the escape hatch |

Plus MCP **resources**: the graph schema DDL, so an agent can write its own SQL, and the
map's generated Markdown documents.

`analyze` reuses `runtime.self_argv()` — the one answer to "run this same build again" —
and `web/analysis.py`'s runner, which already solves the subprocess, the NDJSON protocol,
the two channels, and stop-by-process-group on POSIX and Windows alike. Its `check()`
pre-flight, which already returns three outcomes rather than two, becomes the tool's
refusal path unchanged.

**Read-only posture, stated.** Every store opened for serving is `writable=False`
(rule 20: a read may refuse but never repair). The server refuses an unfinished map and a
stale one, carrying `serve.why(exc)` **verbatim** — `StaleGraphError` and
`UnfinishedMapError` are whole sentences written to be read, and prefixing them with a
class name puts a Python word first. Rule 91 decides where the sentence rides: in the
JSON-RPC error's `message`, with machine-facing detail in `data`, never the reverse.

Registration is `claude mcp add dunneflow -- <path> mcp`, or a committed `.mcp.json`
(there is none today).

### The determinism guarantee must be re-earned, not inherited

Design rule 28 and `GET /api/about` make a standing promise — *"no model is used… the
extractors are stdlib `ast` and `tokenize`, the document scanner is hand-written, nothing
on the analysis path touches a network"* — backed by a test asserting that nothing under
`extractors/`, `resolve/` or `canonical/` imports an HTTP client or an LLM SDK. Tom's own
words are recorded beside it: *"Inference should always be voluntary and secondary."*

A Node subprocess running a bundled TypeScript compiler keeps every substantive part of
that promise: deterministic, local, no model, no network. But **the sentence stops being
true as written**, and the test stops covering the code that does the reading. So v2 owes
three things, and they are not optional:

1. The guarantee's wording changes to name what actually reads each language, per
   language, rather than saying "stdlib `ast` and `tokenize`" about a tool that now uses
   two readers.
2. The import test extends to `ingest/` and `plugins/` — **including the shipped JS
   bundle**, asserted to reach no network. A claim on screen that no test can return is
   prose (rule 13), and this is the one claim the tool's posture rests on.
3. `meta` records **which plugin read which language at which version**, so the About page
   can answer *what read this map* with something specific rather than something generic.
   `files.extractor` from §1f already carries it; About just has to ask.

**One flag on scope.** You picked MCP alone, not `--json` on the CLI and not a versioned
HTTP API, so this plan builds MCP alone. The tool bodies will live in one module returning
plain dictionaries rather than inline in the protocol layer — not scope creep, just the
shape that stops a second surface becoming a second assembly of the same steps (rule 51)
if you ever want one.

---

## 4. Build order — every chunk ends green and measured

| # | Chunk | Gate |
|---|---|---|
| 1 | **Clone and freeze.** Seed `../DunneFlow-v2`; analyse Society; dump every `files`/`routines` row and every `(rowid, callee_id, confidence, external, ambiguous)` tuple as **the golden** | 1,368 tests green, mypy and ruff clean on the untouched copy |
| 2 | **The `ingest/` seam, Python only.** Protocol types, `InProcessPlugin`, `plugins/python/plugin.json`, `LANG_SUFFIX` moves and becomes derived, `discover()` takes the union, `DiscoveryRules`, `WalkStats`' four counters, `SKIP_DIRS` extended | golden **unchanged** |
| 3 | **`lang` load-bearing.** Two defaults deleted, codec stamps, host verifies, `load_rules` loses its default and refuses an undeclared language, the five "only Python" claims derived | golden unchanged |
| 4 | **The MCP server** — over a still-Python-only v2, where it is immediately useful and the ingest churn cannot destabilise it | driven from Claude Code end to end |
| 5 | **Fingerprint split.** `core_extraction_inputs()` (+`schema.py`), per-plugin stamp, `files.extractor`, per-language discard and refusal, `migrate` updated | golden re-taken here by construction; editing a plugin discards only its files |
| 6 | **Resolver split.** `resolve/python/` verbatim; `RESOLVERS`; driver groups by lang; `at_boundary` and the no-edge bookkeeping hoist; `_BUILTINS` → `python.yaml` | Society's resolution tuples identical except the `_BUILTINS` move, whose diff is **measured and recorded** |
| 7 | **Codec and protocol, still one language.** `NdjsonWorker`, `ingest-schema`, `ingest-conform`. **Proved by running the Python extractor through a subprocess worker** — a `plugins/python-oop/` test double | byte-identical facts. *This is the chunk that de-risks everything: the protocol is validated against the one extractor whose output is known exactly* |
| 8 | **String-literal split.** `FileFacts.literals`, plugin-side bound, SQL and artefact scanning moved into `ingest/literals.py`. Done **before** TypeScript exists, so TypeScript never sees the old shape | golden unchanged — that is the proof the split is faithful |
| 9 | **TypeScript, extraction only.** The plugin, the esbuild bundle, `hello`/`open`/`extract`/`close`, `detectors/typescript.yaml`, dotted conformance green. No supplied edges yet — TS calls are external | DunneNote ground truth (below). A map with routines, boundaries and SQL and no internal TS edges is honest and shippable |
| 10 | **Supplied edges.** The `edges` frame, `resolve/typescript/calls.py`, confidence semantics per language documented | resolution rate measured on DunneNote |
| 11 | **TSX / React** — *done 2026-09-17.* A JSX element is a call; the 36 ways in a Next.js tree declares by file layout; boundaries matched on the package the checker resolved into; a hook's callback is a routine; the map states what it does not claim | DunneCorp ground truth met and printed; `.d.ts` excluded on 83 false BROKENs; 112 self-calls found and fixed |
| 12 | **Manifest providers.** `resolve/manifests/`, generalised `pkg_root`, per-provider evidence | DunneNote's `package.json` and uigen's read; no sentence says `pyproject.toml` about either |
| 13 | **Packaging.** Spec bundles `plugins/` wholesale; the fingerprint-equality gate extended to compare **per-language** stamps between binary and checkout | a frozen binary reads a TypeScript tree |
| 14 | **Docs.** Rewrite "Adding a language"; register `ingest/` and `plugins/` in the architecture list beside `canonical/`'s paragraph | — |

---

## 5. Verification

The three gates are binding and unchanged: `uv run pytest`, `uv run mypy .`,
`uv run ruff check .`. Then ground truth against real code, because unit tests on a toy
program cannot catch a resolution defect that only appears at scale.

**The Python regression guarantee — v2 must not make the Python answer worse.** Analyse
`../society-2026-08-29/src --standards ../dunnecorp-standards` with v1 and v2 and compare
through `dunneflow query --sql`: row counts for all 25 graph tables, the resolution stats
(certain / inferred / external / ambiguous / suppressed), the four `[project.scripts]`
executables still in "Where to start" with plausible reach (v1 answers
`1,381 · 423 · 292 · 112`), `naming.md` still byte-identical to the `CORP` fixture, the
research paper still yielding **zero** naming rules, and conformance still at
4 checked · 1 no population · 10 not checkable. **Any difference is explained, not
absorbed.**

**TypeScript ground truth — `../DunneNote`**, a pnpm workspace at version 0.9.0. The
accurate shape, checked rather than assumed:

**767 `.ts` on disk, 322 of them tests, so 445 program files.** Every figure below was
checked by hand:

> **Amendment, 2026-09-17, after chunk 9 read the tree.** Three of the figures in this
> section do not reproduce, and they are corrected here rather than edited above, because
> what was checked by hand is part of the record.
>
> * **758 files, not 767.** `apps/desktop/tests/visual/__screenshots__/` holds nine
>   *directories* named `cal-month.spec.ts`, `canvas.spec.ts` and so on, each full of PNGs,
>   and `find -name "*.ts"` matches a directory as happily as a file. The walk's arithmetic
>   closes exactly: **443 read + 315 left out as tests = 758**, with nothing
>   claimed-but-unread.
> * **Two program files import `@tauri-apps/api/core`, not one.** The second is
>   `legacy/v0.1/src/lib/ipc.ts` — a second copy of the program kept in the tree with its
>   own `tsconfig.json`. The property this corpus was chosen for is unharmed and is what
>   the map reports: 29 test files import that module and **none of them is in the map**,
>   which is the test exclusion working. *Exactly one* was true of a tree without the
>   legacy copy.
> * **`fetch` is called in no non-test `.ts` at all**, where this section says once. That
>   zero is what found the network matcher's defect: `startswith` made `fetch` match
>   `fetchImpl`, and the one row DunneNote reported was that.
> * **81 `.svelte` files, not 70** — unclaimed by name and count either way.
>
> Reproducing: `find` counts directories, so the file count is `p.is_file()` and not
> `find -name`.


| Area | Contents | What must be true |
|---|---|---|
| `apps/desktop` | 550 `.ts` (most of the tests), 70 `.svelte`, own `tsconfig.json` | routines and boundaries throughout |
| **the Tauri seam** | **30 files import `@tauri-apps/api/core`, and 29 are tests** | exactly **one** program file does — `apps/desktop/src/lib/pl/client.ts`. Two claims in one: the seam only reads as a single seam **if test exclusion works**, and *the repo's own `client.test.ts` asserts the property independently*. The best ground truth available here |
| `fetch` | once in all non-test `.ts` | one NETWORK OUT boundary with a `net_calls` row — a second one is a false positive |
| `packages/api-types` | 206 `.ts`, **no tsconfig of its own** | mostly INTERFACE and TYPE_ALIAS, and **zero boundaries** — a types package reporting a NETWORK boundary is the failure to look for |
| tests | 322 `*.test.ts`/`*.spec.ts` | **zero routines**. This is the precision gate, and v1's `is_test_path` fails it outright |
| `apps/host-http` | **Rust**, not TypeScript | absent, and **says so** — not read as text, not quietly missing |
| the 70 `.svelte` files | `<script lang="ts">`, real imports | reported **unclaimed by name and count**, with the set one click away (design rule 1) |
| 283 `.rs` files | | likewise unclaimed |

Also: the file count matches `find` minus the declared skips, and the skips are named.

**React/TSX ground truth — `../DunneCorp` (`dunne-web` 0.1.0), and it is your own tree.**
Verified: a Next.js App Router project, **76 `.tsx` + 60 `.ts`**, `33 page.tsx`,
`2 route.ts`, 22 `"use client"`, with `@prisma/client`, `next-auth`,
`@aws-sdk/client-dynamodb` + `lib-dynamodb`, `bcryptjs`, `stripe`, `resend` and `zod`. It
replaces uigen as the primary React corpus, and the reason is not size:

- it is the **only tree on this machine that exercises `CLOUD_SDK` and `CRYPTO`** in
  TypeScript — two `BoundaryKind` values that have never been asked of anything but
  Python, which is the real test of whether the vocabulary is language-shaped or
  Python-shaped
- **33 App Router pages** make the route-naming assertion worth making

What must be true:

- 33 HTTP_ROUTE entrypoints from the 33 `page.tsx`, **named by URL with route groups
  stripped** — `app/(marketing)/services/[slug]/page.tsx` → `/services/[slug]`. A `(…)`
  group appearing in any route name is a failure, and it is the first thing a Next.js
  reader checks. The 33 names get **printed and read**, not merely asserted.
- the 2 `route.ts` named by their exported HTTP verbs
- `@aws-sdk/client-dynamodb` → **CLOUD_SDK**; `bcryptjs` → **CRYPTO**; `stripe` and
  `resend` → NETWORK; Prisma → DATABASE with the **model** as target
- `process.env` reads → ENV IN with the variable name as target where the access is
  literal
- the 22 `"use client"` files yield components; `useEffect` callbacks yield nested
  routines whose qualname carries the component (rule 10)
- **precision:** `e2e/`, `tests/`, `.next/`, `*.d.ts` and `tsconfig.tsbuildinfo` produce
  nothing
- **stated holes:** `"use server"` actions are not claimed as entrypoints, and the map
  says so; `zod` schemas are not claimed as structures, and the map says so

`../uigen` stays as a **second opinion**, because it is the only TypeScript tree here that
exercises **LLM_API** (`@ai-sdk/anthropic`) and it independently proves path-alias
resolution through `@/lib/prisma`.

**Honest flag, revised.** 76 `.tsx` is a real corpus for correctness and still not a scale
corpus — DunneCorp is ~136 TypeScript files against Society's 628 Python. Correctness is
what chunk 11 is for, and it is well covered. If a *scale* number for React is wanted, say
so and we clone a large React repo before chunk 11 rather than after.

**Performance.** `PERFORMANCE.md` carries over marked as v1's and v2's budgets are
retaken. The number that matters most is taken at chunk 7: **the subprocess protocol's
overhead against in-process extraction, measured on the Python test double** — that is
what tells us whether out-of-process was the right call, on the one comparison where both
sides produce identical facts.

---

## 6. Open questions, flagged rather than assumed

1. **Does the browser need a new `BoundaryKind`?** `localStorage`, `IndexedDB`, `document`
   and `window` have no home in the existing ten. Adding one touches the legend, the plate
   grouping, the colour tokens and `web/graph.py`'s `ext:` plates. My inclination is
   `BROWSER` rather than stretching FILE — but settle it by counting hits on DunneNote and
   uigen first. A kind that turns out to be twelve hits is not worth a plate.
2. **Host-side literal scanning assumes the wire volume is tolerable.** Settle it by
   counting string literals of ≥6 characters in Society and in DunneNote and totalling
   their bytes. Under ~30 MB per cold run it is free; over ~150 MB, reconsider. Shipping
   `sql.py`'s regexes as data for the plugin to apply is rejected on sight — two regex
   engines, and `\b` and lookahead differ.
3. **Should a reader refuse the whole graph when only one language's stamp is stale?**
   Currently yes, on the grounds that edges can cross languages. Settle it with a test
   over the source — the technique `test_inference_withdrawn.py` already uses — asking
   whether any resolver, query or renderer reads a row belonging to a different language
   than the one it is resolving. If none does, scope reads by language instead: refusing a
   Python question because somebody edited the TypeScript plugin is the kind of friction
   that stops a tool being a habit.
4. **One worker per plugin, or one per `tsconfig.json`?** DunneNote has only two
   tsconfigs, so one worker is almost certainly right there. Settle it by timing
   `ts.createProgram` against total per-file visit time and measuring peak RSS per program
   on `apps/desktop`'s 550 files.
5. **Does `node --version` belong in the TypeScript stamp?** Left out. Settle it by
   running the conformance corpus under two Node majors and diffing the NDJSON byte for
   byte. Identical → it stays out and Node upgrades stop discarding the TypeScript half.
   Any difference → it goes in and the re-extract is simply paid.
6. **Do the naming, conformance and `--standards` lanes mean anything across languages?**
   A convention mined across a Python and a TypeScript corpus at once would report that
   the program has no convention. They probably need to be **per-language**, which changes
   `resolve/naming.py`'s denominators rather than adding a filter. Deferred until chunk 11,
   when there is a mixed corpus to measure on.
7. **Cross-language call edges.** DunneNote is TypeScript calling Rust through Tauri
   `invoke("cmd_name")` — a real edge across a language boundary and a genuinely new
   capability, but it needs a Rust plugin before it can be anything but a dangling name.
   Out of scope here; worth naming in `BRIEFING.md` as the reason a *second* plugin
   matters more than the first.

---

## Existing files that change most

`walk.py` (registry dispatch, discovery, the four new counters) · `schema.py` (`lang`
required, `literals`, `CallSite.is_construction`, `ArmKind` and `StructureKind` values) ·
`store.py` (`files.extractor`, per-language staleness) · `detectors/__init__.py`
(`core_extraction_inputs`, per-plugin stamp, `load_rules` refuses an undeclared language) ·
`resolve/calls.py` and `resolve/cli.py` (become drivers; the Python bodies move to
`resolve/python/`) · `resolve/entrypoints.py` and `resolve/version.py` (manifest
providers) · `resolve/naming.py` (`DOTTED`, the dunder and `self`/`cls` filters, case
expectations) · `canonical/__init__.py` (`LANG_SUFFIX` moves out) ·
`extractors/python/extract.py` (stops stamping `lang` per record; reports literals instead
of scanning them) · `cli.py` (`pkg_root` search, `--without <lang>`, `mcp`,
`ingest-schema`, `ingest-conform`) · `packaging/dunneflow.spec` (bundle `plugins/`
wholesale) · `web/cover.py` and `web/serve.py`'s `/api/about` (say what read each
language) · `render/mirror.py`, `resolve/mirror.py`, `render/traceability.py` (the
"only Python" claims become derived).

**New:** `ingest/` (nine modules) · `plugins/python/` · `plugins/typescript/` ·
`detectors/typescript.yaml` · `resolve/contract.py`, `resolve/python/`,
`resolve/typescript/`, `resolve/manifests/` · `mcp/` ·
`tests/fixtures/dotted/cases.json`.
