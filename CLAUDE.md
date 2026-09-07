# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. Built for a reader who reads code but does not write it, and who thinks in
entrypoints, flows, routines, and boundaries.

**New here? Read `BRIEFING.md` first** — where the code lives, what is built, what we are
doing now, and which decisions are closed. This file is the standing orders; `HANDOFF.md`
is the chronological record.

The rules moved out of this file when it outgrew what a session can carry, and the split is
by *how often you need it*, not by importance:

| File | What it holds | When to read it |
|---|---|---|
| `CLAUDE.md` | commands, verification gates, architecture, and the **index** of every rule | every session — it is loaded for you |
| `RULES.md` | the 81 engineering rules **in full**, with the false result each came from — numbered to 82, because 21 does not exist and the numbers are addresses | before working in the area a rule governs |
| `DESIGN-RULES.md` | the 29 dashboard design rules in full | before building or changing a view |
| `PERFORMANCE.md` | every measured figure, with its budget and its conditions | before quoting or retaking a number |
| `BRIEFING.md` | state: what is built, what is next, what is closed | at the start of a session |
| `HANDOFF.md` | the full chronological record, session by session | when you need why something is the way it is |

A rule is cited as a bare number — "rule 45", "design rule 19" — from code comments, tests
and both records; 768 such citations across `src/` and `tests/`. **The numbers are addresses.
Never reuse one, never renumber, never close a gap.**

## What this tool is for

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back out.
**What moves is the subject. Internal computation is not.**

Deliberately *not* reported: local variables, arithmetic, and private helpers that
neither touch a boundary nor sit on a path to one. Leaving those out is most of what
makes the output readable — do not "improve" the tool by adding them.

**Control flow was on that list until 2026-09-07, and the amendment is narrow.** A loop
or a decision is a subject **only where something moves inside it**: a loop that
increments a counter is still the internal computation nobody asked for, a loop that
issues one network call per item is a *rate*, and a rate is flow. What is recorded is a
span — routine, line range, depth, arms, and the header as written — and never a
variable, an operator or a value. See `resolve/shape.py`, which is the one place that
judgement is made.

The goal is **comprehension, not documentation**. Judge a change by whether it helps
someone orient in an unfamiliar codebase, not by how many pages it emits.

## Commands

```bash
uv run dunneflow analyze  <path> --name <program>   # extract, resolve, write the map
uv run dunneflow touches  <path> --routine <name>   # what does this reach?
uv run dunneflow impact   <path> --routine <name>   # what breaks if I change it?
uv run dunneflow glossary <path>                    # what its words mean, and who says so
uv run dunneflow naming   <path>                    # the naming standard as found: derived, and quoted
uv run dunneflow mirror   <path>                    # words the docs define that the code never uses
uv run dunneflow query    <path> --sql "..."        # ask the graph directly
uv run dunneflow migrate  <dir>                     # stored paths: absolute -> relative
uv run dunneflow serve    <dir> [--revision <rev>]  # the dashboard, on one version
uv run dunneflow analyze  <path> --standards <dir>  # measure it against somebody else's rules
```

`analyze --progress-json` reports one JSON object per line on stdout instead of the summary,
which is how `serve` runs it. See the `serve` section below.

**`serve` also *makes* a program.** The `<select>`'s last option, `+ Analyze a directory…`,
reads a source tree into a new directory under the output root and puts it in the list —
`POST /api/analyze`, `GET /api/analysis`, `web/analysis.py`. Four things about it:

* **A subprocess running `dunneflow analyze`, never an in-process call.** Every store this
  process opens is `writable=False` (rule 20), and an in-process analysis would make the
  serving process a writer to the tree it serves. It also keeps `walk.py`'s
  `ProcessPoolExecutor` out of a request thread, and makes what runs *exactly* the tested
  command rather than a second assembly of the same steps (rule 51).
* **Two channels, and `--progress-json` is why.** The child's **stdout** is one JSON object
  per line; its **stderr**, emptied by `--quiet`, is where a failure says why. Scraping
  prose written for a human would promote a sentence to a contract (rule 30). The step list
  is **computed for the run** — four flags remove work, so a fixed total is a bar a
  `--no-docs` run can never reach (rule 32) — and is printed as sent all the way to the
  screen. A failure's reason **leads with the child's last line** and keeps the rest as
  evidence: a traceback says the useful thing last, and this reader does not write code.
* **Its own slot, not the switch's.** `claim_analysis` beside `claim`. A switch replaces
  what is on screen; an analysis replaces nothing, so one slot would mean a ninety-second
  read of an unrelated tree locking the reader out of changing versions. That is also why
  the panel is dismissible rather than the base switch's blocking scrim — *the map on
  screen stays true for the whole run*, and it says so.
* **The served program is refused, and it is not caution.** `Store._discard_if_stale` drops
  every table of a graph written by another build, and this server is holding that graph
  open — so an analysis aimed here can empty the map under a live reader. Every other
  refusal has its own sentence too (`analysis.check`, one function for the dialog's live
  warning and the endpoint's answer, rule 41); analysing into a name that **already exists**
  is allowed and *says* it rewrites that program's working snapshot.

**A map records whether its own analysis finished, and every reader that vouches for one
checks.** `analyze` commits `complete = ""` as it opens the graph and `"yes"` as its last
act, and commits the **step** as it goes. This is not housekeeping: a killed `analyze` leaves
a graph that *opens perfectly and lies* — one stopped twelve seconds into Society reported
628 files, 4,786 routines and **`resolved_calls = 0`**, over a timestamp, a tool version and
the determinism guarantee. Reachable with no stop button anywhere: Ctrl-C, a sleeping laptop,
an OOM kill.

**Three states, never two** (`Store.finished`): missing means *written before this key
existed* and is fine, `""` means *started and never finished*, `"yes"` means finished.
Refusing on absence would refuse every map made before it. `UnfinishedMapError` is raised on
**read** paths only — `_Live.open`, `_open_store` and so `check`, and `serve`'s boot — with
`analyze` deliberately exempt, because opening one is how it recovers (34 s on Society, since
the extraction is content-hashed). `query` is the one reader that proceeds, and **warns**:
its contract is that you get the rows that are there. `unfinished_sentence` is the one place
those words live, and `serve.why()` strips the class name from the two exceptions written to
be read.

**An analysis can be stopped, and the slot asks the process rather than a flag.**
`POST /api/analyze/stop`. Three things make it work:

* `_Live.analysis_proc` holds the child. It was a local inside `analysis.run`, so nothing
  could stop a run at all — no route, no button, and a hung child held the slot until
  somebody killed the server.
* **`claim_analysis` asks `poll()`, not `state == "working"`** (rule 30). A watcher that dies
  without noting used to leave that label true for ever; the stale lock is now cleared rather
  than left for somebody to notice. This is the *"or locked"* half.
* **The child gets its own session and the signal goes to the group.** `analyze` runs a
  `ProcessPoolExecutor` whose workers inherit the pipes: signalling the parent alone left
  **eleven workers** holding stdout open, so `run`'s read loop never returned and the report
  said `working` over a child that had gone — the very jam, arriving through the fix for it.
* A stopped run is `state: "stopped"`, **not `failed`** — the reader did it on purpose, and a
  negative exit code is the child's own evidence rather than a flag set from outside (rule 13).

The slot records `began` and `moved`, and `moved` bumps **only when something changed** — a
timestamp refreshed by being polled would say a run was moving because it was being watched,
and *silent for 4 m* is the only thing separating a wedged child from a long step. The panel
**states the silence and acts on nothing**: resolution is legitimately quiet for tens of
seconds, so the judgement is the reader's. A refusal to start a second analysis carries the
running job and a **Stop it**, kept live while the dialog is open and clearing itself the
moment the run ends — the sentence promises that, so something has to keep it (rule 44). And
the page asks `/api/analysis` at boot, because a run outlives the page that started it.

**`serve` says what read the map, and whether anything in it was guessed.** The topbar's
`source directory` control — a readout until there was something true to put in it — opens
*About this map*: `GET /api/about`, and the two rows it exists for are

| Inferred facts | none — every fact here was read, not guessed |
| Read by a model | none — this analysis is deterministic and local |

**A standing guarantee, not a placeholder waiting for a model.** Nothing on the analysis
path calls a model or touches a network: the extractors are stdlib `ast` and `tokenize`, the
document scanner is hand-written, and `Provenance`'s two paid tiers (`CITED`, `INFERRED`) are
declared and unbuilt. Tom, 2026-09-04: *"Inference should always be voluntary and secondary."*
A test asserts nothing under `extractors/`, `resolve/` or `canonical/` imports an HTTP client
or an LLM SDK, because a claim on screen that no query can return is prose (rule 13).

**Missing and blank are different answers**, and flattening them would turn a silence into a
promise. Every field arrives as `{recorded, value, none}`: a map written before `analyze`
recorded any of this reports `recorded: false` and says *"not recorded — written before this
map could say"*. **`none` is the server's decision**, never a test for the word on the page —
`inference` stores `none` so `dunneflow query` over `meta` reads as prose and `model` stores
blank because there is no word for the model that did not run, and the page owns neither
spelling (rule 51).

*What is deliberately **not** offered is a "would a newer build read this differently?" row.*
For the map on screen it can only ever answer no: `Store` opened read-only calls
`_refuse_if_stale`, so a mismatched graph never becomes the base at all. What is stated is the
guarantee that produces. The honest *should I read this again?* signal is the date beside it
and the **tree leaf** it was read from — a leaf, never a path (rule 60).

`serve` also switches **program**, which is the same operation one axis over. The topbar's
first control lists every directory under the output root that holds a map —
`revisions.program_dirs()`, the same question `analyze` asks to keep a program's own output
out of its own corpus — and `POST /api/program` rebuilds against one of them. Two things
differ from a revision switch and both are in `_Live.switch_program`: the sidecars are
repointed, because `source.db` and `docsource.db` belong to the *program*; and **every**
cache is cleared, because `findings` is keyed on a graph's *basename* and `filepairs` on a
pair of revision strings, and two program directories collide on both. `PROGRAM_CACHES` is
stated separately from `COMPARISON_CACHES` rather than derived from it (rule 36). Nothing is
closed or repointed until the new base is built, so a stale program leaves the reader looking
at what they had, with the store's own sentence in the progress report (rule 20).

`serve --revision` chooses which point in time the server opens as the **base** -- the
version the cover, the routine list, the code browser, the glossary and the stack all
show. It defaults to the newest. The reader can switch it from the toolbar, and that
switch survives a page reload; this is how it survives a restart of the server, because
the base is the server's state and not the browser's.

`GET /api/graph` takes `?level=routine|module` and `?minDisk=<n>` — the stack's **level of
detail** and how few things a plate may hold before it is merged into `<small>`. An unknown
level is refused with a 400 rather than defaulted, because a silent fallback answers a
question nobody asked with a picture that looks exactly right; the threshold is clamped
instead, because the two are different mistakes. On screen it is the *Detail* control in
the legend, which states what the altitude costs: what is drawn, what it stands for, and
what the threshold merged.

`migrate` rewrites a program directory written before paths were relative (rule 60), **in
place** — 115,546 paths across five stores in 1.2 s on Mensores. In place rather than by
re-analysis, because a sealed snapshot exists to be readable after its source tree is
gone and rebuilding would orphan exactly those. A reader refuses an unmigrated store and
names this command; it never repairs one on the way past (rule 20).

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`).

The dashboard also searches the **text** of the source — `/api/search`, the Code group's
box. That is a different question from `touches`, `impact` and the glossary, which search
names and meanings: this finds a word inside a comment, inside a string literal, or on a
line that carries neither.

`analyze` is incremental: unchanged files are not re-parsed.

**Diagram mode has two levels too**, and the second is asked on demand rather than built
with the others: a compartment is fifty-three drawings from one pass over the model, and a
*box* is one of nine thousand. Measured on Mensores 2026-08-31:

| Measure | Budget | Measured |
|---|---|---|
| One compartment, drawn in the browser | < 500 ms | 93–179 ms |
| Opening a box — three grouped queries | < 200 ms | 15 ms (18 routines) · 170 ms (61) |
| `/api/fold`, a class of 61 methods | < 500 ms | 0.77 s cold, ~40 ms warm |

**ALGORITHMS is a page and a mode, and they are two questions.** The navigator's
*Algorithms* group opens `/api/algorithms` — five lanes over the whole program, each with
its denominator, held on the base. The mode toggle's **Shape** opens `/api/shape?node=` —
the selected routine's own outline, answered on demand. 105 ms and 0.2 ms; see
`PERFORMANCE.md`.

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then verify against real code, because unit tests on a toy program cannot catch a
resolution defect that only appears at scale:

```bash
uv run dunneflow analyze ../society-2026-08-29/src --name mensores
```

**Three trees, and only two of them are the pair.** `../society-2026-08-26` (e2e658b4,
625 files) and `../society-2026-08-29` (03ebbd93, 628 files) are the sister clones every
recorded temporal figure belongs to; `../mensores-overhaul` is a third copy of 626 files
and is neither end of it. This file named it here for a year and it cost a wasted analysis
in the session that bumped `SCHEMA_VERSION` — the result looked perfectly healthy, and the
tell was the sidecar reporting *"1 read, 625 already held"* where the record says twelve
files differ.

**All three are read-only.** They are copies kept for documentation. Never write to any of
them. All output belongs in `output/`.

Rebuilding the pair after a schema bump is two analyses and a seal, in this order — a
sealed snapshot is never re-analysed in place, by design (rules 25 and 62):

```bash
uv run dunneflow analyze ../society-2026-08-26/src --name mensores
uv run dunneflow revisions output/mensores --seal --label "Society at e2e658b4 - 2026-08-26"
uv run dunneflow analyze ../society-2026-08-29/src --name mensores
```

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

### Performance budgets — `PERFORMANCE.md`

Every measured figure lives there: analysis, the interactive map, the dashboard's panes,
the change worklist, search, and the documentation scan, each with the budget it was taken
against. **A cold row is the external volume and nothing else**, and a row states its
conditions where they are load-bearing — retaking one without reproducing those is a
different measurement under the same label (rule 24).

## Architecture

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

- `schema.py` — the fact contract. Every extractor, in any language, emits these types.
  A **call site has an identity** (`call_site_id`) and carries the arguments the caller
  wrote (`CallArg`), because two identical expressions in one routine are two calls and
  the arguments of one must not land on the other — 287 such pairs on Mensores. The id
  holds no position, like every other id here: an ordinal among identical expressions in
  the same caller, with the residue stated in the docstring rather than hidden.
- `store.py` — SQLite. **The spine, not an export format.** Nothing holds the whole
  program in memory; reachability is recursive SQL over indexed edges. This is the one
  decision that lets the tool survive growth — do not replace it with in-memory graphs.
- `extractors/python/` — stdlib `ast` + `tokenize` only. No third-party parser.
- `canonical/` — whether two writings are **the same expression**, one module per language.
  Beside the extractors rather than inside one, and that placement is load-bearing:
  `code_extraction_inputs()` globs `extractors/python/*.py` into the cache key, so a
  canonicaliser living there would discard every graph on the machine — sealed snapshots
  included — each time it was edited, for a module extraction never reads and that cannot
  change one fact. A language with no entry compares its expressions as written.
- `extractors/docs/` — Markdown, reStructuredText and plain text, scanned by hand for
  the same reason: no markdown library. Emits `DocFacts`.

  **A naming standard is usually a table, and `_table()` reads one.** The FORM lane was
  empty across all 2,064 of Mensores' documents — 5 rules, all VOCABULARY, none
  `checkable` — because `_table()` consumes a table whole and the loop `continue`s, so the
  prose rule detector is never offered its lines. `table_rule_columns()` decides which
  column names the thing and which gives its spelling, on the model of
  `term_columns`/`meaning_columns` beside it and with the rule that matters kept: **both
  halves are required, on different columns.** A column qualifies on its **header or its
  cells** — headers vary between organisations, and cells alone miss a column headed
  `Convention` whose contents are too terse to score. Measured over 5,230 tables: it fires
  on **one**, `harness/rules/style.md:30`, and mints its seven rows; the 100-row *Key
  Decisions* table and the pantheon glossary do not fire. A row whose scope names no
  identifier class is **kept, not dropped** (design rule 1) with `scope=""`, so it is a
  rule this tool has no population for rather than a rule that vanished.

  **That rule governs the extractor, and only the extractor.** Its output is a contract,
  hashed into the cache key by `doc_extraction_inputs()`, so a third party's reading of a
  document must never become a fact this tool asserts. A **renderer** produces pixels, is
  in no cache key, and no fact depends on it — which is why `markdown-it` is vendored in
  `web/vendor/` and why nothing under `extractors/` may import it. State the line rather
  than blur it, or the next reader will correctly call the library a violation.
- `standards.py` + `standards.db` — **somebody else's rules, admitted without being
  absorbed.** `--standards <dir>` reads an outside naming standard through the *same* walk
  as the corpus (so `discover_docs` refuses a nested checkout for it too, rule 57) into a
  store of its own. Its own **file**, never a column on `documents`: `docs.db` is read by
  the glossary, the mirror, traceability and Document mode's corpus lane, and a flag would
  make every one of those a place that must remember to filter — the seven-read-paths shape
  rule 51 was minted from. `docsource.db`'s argument, one subject over. Rule 57 gains three
  refusals a reader can trigger by naming a root — inside the output tree, inside the
  documentation root, inside the analysed tree — **each with its own sentence**, and all of
  them judged *before* anything is opened, so a refusal never abandons a half-written map.
- `resolve/conformance.py` — **reality against intent**, and the third naming question.
  `naming.py` counts and quotes nobody; `stated.py` quotes and counts nothing; this asks
  whether the program does what a rule says. **The population is never inferred from the
  scope word**, and that is the whole feature: all six of Mensores' `checkable` rules come
  from a harness standard and *none* is a question about `graph.db`. Checked against the
  graph, *"Files: kebab-case"* is **0 of 628** Python files — a catastrophic claim about a
  rule its own document scopes to `src/**/*.md`, three documents. So a **path-shaped scope
  requires a declared `paths:`** and is refused without one (rule 49: a plausible population
  is what hides the failure), while an **entity scope** names its own population and a glob
  narrows it. **Three verdicts, never two** — checked, no population here, not checkable —
  because collapsing any two lets *"we could not check"* read as *"it passes"*. Only case
  styles are tested, through `naming.case_style` so `kebab-case` means one thing (rule 51);
  a template like `NN-kebab-name` is quoted back and declared untestable rather than guessed
  at. It reuses `POPULATIONS` **and `DOTTED`**: taking the first without the second
  reproduced rule 51's own defect exactly, reporting `modules / snake_case` as **1 of 628**
  because a dotted path was read as one identifier.
- `resolve/shape.py` — **the amendment, and the one place it is judged.** `CLAUDE.md`'s
  founding exclusion read *"local variables, arithmetic, control flow"* until 2026-09-07,
  and the rule behind it has not changed: **a loop or a decision is a subject only where
  something *moves* inside it.** A loop that increments a counter is the internal
  computation nobody asked for; a loop that issues one call per item is a **rate**, and a
  rate is flow. A branch whose arms compute different numbers is arithmetic; one where an
  arm writes to a table and another does not is a decision about what leaves the program.
  That test lives here and nowhere else (rule 51) — the worklist, the ribbon and the panes
  all ask this module.

  **Nothing is dropped for failing it** (design rule 1). Three bands, never two: something
  moves · it only calls something of this program · nothing happens here that this map can
  see — and every point carries a `why`, including the ones that pass. It is the 1,222
  loops that move nothing that make the 261 credible.

  **The join is a range, never a relationship.** `boundaries`, `net_calls`, `sql_ops` and
  `calls` each already carry `routine_id` and `line`, so *inside* is
  `line BETWEEN line_start AND line_end` — the inverse of the lookup `web/search.py` does.
  A table joining a loop to a boundary would be a second copy of a fact those two already
  state between them (rule 40).

  **A place is one act; a row is one description of it.** An `INSERT` is a `DATABASE` row
  *and* a `SQL` row on one line, and 569 of Mensores' 991 SQL operations are such a pair —
  so counting rows said *two things move here* about one write, in the sentence that gives
  33 of the 261 rates their number. `places()` is the one place a count is taken; the rows
  stay as the descriptions, and a surface draws a place once, led by the row that says the
  most about it.

  **`in_loop`, and not `depth > 1`.** `depth` counts every enclosing control point, so a
  loop written inside an `if` has depth 2 and is nested in nothing. On Mensores the two
  answers are **104 and 10**, and the ten are the quadratic reaches into the outside world
  this feature exists to find. Filled by a stack sweep per routine, with `depth` breaking
  the one tie lines cannot — `[a for a in [b for b in c]]` is two comprehensions on one
  line.

  Measured over Mensores: 219 loops + 42 comprehensions reach a boundary · 467 only call ·
  1,222 move nothing · 78 of 2,213 decisions fork · 69 are ladders of three or more ·
  396 of 1,531 handlers recover by moving something · 3,931 guards · 0 `match`. 96 ms warm
  for all 9,625 points.
- `web/shape.py` — the same facts served twice, for two questions. **`/api/algorithms`** is
  the whole program in five lanes, held on the base and computed on the first ask; each
  lane states its **denominator** (*261 of 1,950*, never *261 loops*) and the page states
  the quiet bands above the list, because four lanes holding 804 of 9,625 points is a claim
  about the other 8,821. **`/api/shape?node=`** is one routine's outline, answered on demand
  and held on nothing (rule 45).

  **The ribbon is a nested outline and not a graph.** Nassi and Shneiderman drew structured
  code in 1972 as nested boxes with **no arrows at all**, because structured code has no
  `goto` to draw and Python source never lost the structure — so there is no control-flow
  graph, no dominator analysis, no layout pass and no library. Guards are drawn *here*, and
  only here: 3,931 refusals are a list of the program on a worklist and the truth about a
  routine in its own shape.

  **`shape` is the mode and `algorithms` is the page**, and the two words are kept apart on
  purpose: `selectFromNav` sets `state.view = state.mode`, so one word for both would make
  selecting a routine land on the worklist — `data-nav`'s defect, which cost a session.
- `docstore.py` — `docs.db`. **Parallel to the graph, never inside it.** A doc rescan
  never touches `graph.db`, code-only analysis stays cheap, and the corpus stays a
  separately handable artifact — many will hand over a charter and never a line of
  source. The join is one `ATTACH DATABASE` away.

  **It records what a document *says*, never what it is.** `DocSourceStore` in
  `sourcedb.py` holds the bodies in `docsource.db` — the same content-addressed blob store
  as `source.db` with a different `kind` stamp, in its own file for design rule 14's
  reason, and one per program holding every revision. 2,056 bodies for 2,064 paths, 38.7 MB
  of prose in 14.8 MB; the eight duplicates cost nothing. `--no-doc-source` beside
  `--no-source`, separately, because the two travel separately.
- **Document mode is two lanes sharing one pane**, and they are two subjects rather than two
  views of one thing: `documents.py` is prose this tool *generates* about the program,
  `corpus.py` is prose somebody *wrote*. One mount, one subtree cache and one `render()`
  branch serve both, so the cache key carries the lane — a subtree keyed on the other lane's
  page is handed back on a switch, and that looks exactly like a switch that did not work.
  The filter over the 2,064 documents **hides rows rather than rebuilding**: the query is
  deliberately out of the cache key, because rebuilding also destroys the `<input>` being
  typed into and takes the focus with it. A document is **rendered once when it is fetched**,
  never at paint time — parsing is the one cost a subtree cache cannot save. A relative link
  is **checked against the corpus before it is followed** (666 of them, and many point
  outside the scanned tree), and the refusal goes in `docNote`, never `navNote`: that is
  rendered only in the graph HUD, which nobody reading a document is looking at.
- `web/static/prose.js` — **the document renderer**, and the only third-party parser in the
  tool. Its own file because the boundary is `graph.js`'s: it turns text into markup and
  knows nothing about this page, and what it has to say leaves as **data attributes** —
  `data-line` on every block, `data-doclink`, `data-docanchor` — which the shell routes.
  Rendered through `md.parse()` to tokens and never `md.render()`, because the line map is
  the whole reason the library is here: **825 of 825 headings** verified findable in the DOM
  at exactly the line `docs.db` recorded, which is the chain design rule 13 rests on.
  `html: false` is the whole XSS answer; `linkify: false` because in 2,019 plans and research
  notes a great deal of text looks like a URL without being one. **An image is never
  fetched** — an `<img>` fires a request with no click and no consent, out of a tool whose
  posture is deterministic and local (design rule 14) — and a **relative link never keeps its
  href**, because `<a href="./rel.md">` navigates the dashboard away. Chosen from the corpus
  rather than in general: 3,522 external links, 666 relative, 16 anchors, 6 schemes nobody
  can follow, 5 images. **YAML frontmatter is blanked, never removed**: markdown-it parses it
  as a setext heading, 989 of 2,019 documents open with one, and *deleting* the lines would
  shift every `token.map` below by a constant — a page that renders perfectly with every
  number on it wrong. **An HTML comment is lifted out the same way and for a sharper reason:
  `html: false` does not hide one, it un-hides one.** With raw HTML refused, markdown-it
  disables the `html_block` rule *entirely*, so a comment is not a token to catch — it
  arrives as an ordinary paragraph and renders as body prose. 7,317 of them across 505
  documents. They are listed with their lines rather than dropped (design rule 1). Every
  block also carries `data-line-end`, because the lines anybody opens at are mostly **not**
  the first line of a block: a definition sits mid-paragraph, and reaching for the next block
  instead lands one paragraph past what was asked for.
- `web/documents.py` — **lane 2 of Document mode: the map's own eight documents**, and
  `corpus.py` below is lane 1. Close names for different subjects: this is prose the tool
  *generates* about the program, that is the prose somebody *wrote*. Every row carries the
  graph node id that produced it, selected in the same statement as its text — which is the
  whole reason this does not reuse `render/markdown.py`, because linking rendered prose back
  to nodes would mean matching names against the store and rule 5 says how that ends. So a
  row is an **ordinary selection**: the stack lights, the inspector fills, the trail records
  the hop, undo reaches it. A `Section` also declares `table_col` where its rows name a
  declared **table** rather than a node — `DOC_DB_TABLES` selects `NULL AS node` on purpose,
  and selecting a table means selecting the code that reads and writes it. Declared rather
  than inferred from a null id, because *"this row names a table"* and *"this row's node
  could not be resolved"* are different facts that look identical on the wire (rule 30).
  The location column is aliased `AS "where"`, **in quotes** — `where` is a SQL keyword, it
  was `where_` for as long as the family existed, and `Column("where", …)` therefore read
  `None` and rendered the cell blank in **every row of all eight documents**. A guard now
  prepares every statement and asserts each `Column` key is a column it returns.
- `web/corpus.py` — the corpus **served**: `/api/docs`, `/api/doc`, `/api/docsource`. Two
  stores answer together and either can be missing on its own, so there are **four**
  states and not two — never scanned, scanned but not captured, captured but not for the
  version on screen, and captured but not this path — each with its own sentence, because
  they look identical on a blank pane and the thing to do about each is different (design
  rule 21). `revision=None` is a **refusal** from here down, never "the newest": that `None`
  meeting the store's `None` served 2026-08-29's prose under 2026-08-26's headings, which
  is rule 70 one corpus over from where it was first paid for. A document is sent **whole
  and as one string**, unlike `/api/source`'s numbered lines, because a renderer needs
  block structure intact and takes its line numbers from `token.map`.

  `serving()` is the one decision *"can this sidecar serve the version on screen"*, and it
  answers for **both** corpora: its two sentences are arguments with document defaults, so
  `/api/source`, `/api/docsource` and the glossary's capability block share one reading of
  the question and differ only in wording (rule 51).
- **A glossary citation is a *capability* test, not a provenance test.** `senseOpens()` in
  the shell was `s.provenance === "DECLARED_CODE"` for as long as `source.db` was the only
  sidecar, so every documentation-derived definition rendered a dead end and design rule 13
  went unmet for the tier that quotes the program's own words. `/api/glossary` now carries a
  `sidecars` block — one entry per tier, `{opens, reason}` — computed from the live stores
  and the base's two revisions, so the question is *does the corpus this tier quotes have a
  sidecar this base can read*. Deliberately **not per path**: whether the corpus opens is
  what decides whether a button is drawn at all, and a sidecar that holds bodies but not
  *this* path is a fourth state stated by `_span` when the reader asks — pre-empting it
  would be a `held_paths` lookup per citation to grey out a button that already says what
  happened when it is pressed. The block rides on the route rather than in `bind_glossary`
  because the two have different lifetimes: the terms belong to the base, the sidecars to
  the process and to which version is on screen.

  **The two tiers are two routes**, `VIEWER_ROUTE` in the shell, for `_r_docsource`'s
  reason: a `corpus=` parameter with a default is right until somebody omits it. And the
  viewer offers a documentation citation a second reading — *Read it in the document →* —
  because the pane above it is the bytes **as measured**, Markdown syntax and all, which is
  what proves the citation and is not how that sentence was meant to be read. The hop holds
  its line until the paint that has a block to scroll to; `openDocumentAt` returns two
  awaits before there is one.
- `call_args` — what a caller passed, **as written**, hanging off `calls.site_id` rather
  than off a rowid: an argument has to stay attached to its call site across two versions
  of the same program. Sliced out of the file's own text on **byte** offsets (rule 75),
  never re-rendered by `ast.unparse`, and never shortened — one argument on Mensores is a
  1,347-line `frozenset` and is stored whole (rule 8). 43,926 arguments over 30,544 call
  sites. `forget_file` deletes them *through* `calls`, before emptying it.
- `detectors/*.yaml` — **the extension point.** Teaching the tool a new framework is a
  config edit here, not a code change. Prefer adding a rule over adding a branch.
- `resolve/` — call graph, CLI command trees, flows, naming conventions, glossary.
- `render/` — Markdown and Mermaid.
- `web/layout.py` — where things sit. `DISK_RADIUS` is now the width of the **widest**
  plate rather than of every plate; how wide each one is actually drawn is a *view*
  property owned by the renderer, like Z and the spreads, because `phyllotaxis` is radially
  uniform and scaling a plate's coordinates is exactly computing it at a smaller radius.
  Its old note — every disk one size, density carries the information — is rewritten as the
  reversal it is rather than left standing beside code that contradicts it.
- `web/graph.py` — the 2.5D model, at **two levels of detail**. `routine` is every thing
  the program declares; `module` folds each file into one node and each boundary kind into
  one, on a single plate below the code. 10,015 nodes and 52 plates become 578 and 38, and
  it is a second way to look at the same facts rather than a filter — nothing is dropped
  and every folded node states what it stands for. The fold happens **on the way in from
  the store**, never over `m.edges`, which holds each crossing twice by design (rule 23);
  `packages.py` wrote that warning down before anything needed it. `MIN_DISK` is per level
  and settable, because what a plate *holds* changes with the level.
- `web/diagram.py` — the compartment, at **two levels**, and **every arrow carries its
  identity and its kind**. A lane is `pair -> Counter[kind]` rather than `pair -> weight`,
  so a TOUCH and a CALL between the same two boxes are one arrow that can say which it is;
  the weight *is* the sum, by construction, so the two cannot disagree (rule 13). `dot()`
  writes `id=` on every edge as well as every node, which is what makes an arrow clickable
  at all. The separator is `=>` and no box id may contain one — asserted over the whole
  program, because the split is on the **first** occurrence and a box id that held one
  would name a box that does not exist. A box is a class, a file's loose
  functions, or a boundary kind; opening one returns a **`Compartment` of routines** — the
  same type, so `dot()` and `mermaid()` draw both and a fix to one is a fix to both. A fold
  is a subject in its own right, never one of the things it folds (rule 74).
- `/api/flow?from=&to=[&inside=]` — one arrow, opened: every call site with the arguments
  **as written** and the callee's declared parameters, or the SQL and network operations
  for an edge into a boundary. Answered on demand — rule 45 where it belongs, bounded by
  the reader opening one arrow rather than by the picture drawing a hundred. `inside` names
  the fold when the arrow is on the second level and is refused rather than guessed from
  the shape of an id (rule 30). Call sites are **listed, never grouped**: the aggregate is
  the number already on the arrow (rule 32), and never bounded (rule 8).
- **The binding line, and it is on the screen.** An argument is aligned to a parameter only
  where the source settles it — a keyword by name always, a position only when the callee
  is resolved, takes no `*args`, and the receiver question is answered (`self.f(x)` skips
  one; `obj.f(x)` cannot be told from `Cls.f(obj, x)` and so binds nothing). Measured over
  the corpus: **10,668 of 11,570 arguments on a resolved call bind, 92.2%**, and every
  refusal states its reason, because a blank beside an argument reads as *no such
  parameter* — a different and false claim.
- `web/curiosities.py` — **the doorway panel**: ten measured extrema over the whole
  program, each with **its middle stated**. Every program has a most-commented routine, so
  a maximum alone is a claim nobody can weigh — 1,126 comments against a middle of 3 is a
  discovery, 3 levels of nesting against a middle of 2 is not, and the panel says the
  second as plainly as the first. The list is fixed and complete, so rule 8's bound never
  arises; a measure with nothing to measure is *named* rather than dropped (design rule 1).
  Ordered by distance from the middle. **A curiosity is a measurement, never a judgement**:
  no severity, no blind spot, nothing implying a number ought to be smaller — that is what
  `anomalies.py` is for. One statement per family returns the value, the median, the ties
  and the population *together*, so the query a card offers is not a query about the number
  but the query that returned it (design rule 13), reproducible verbatim through
  `dunneflow query`. Subjects are minted in `threads.py` and nowhere else.
- `web/threads.py` — **adjacency by interest, not by edge.** Why a neighbour is worth a
  detour: shares a plan, the other end of a table you write, the most commented routine on
  your plate, named like ninety-eight others. Every thread carries a *subject* the router
  can act on, never a label (rule 30), and states its size so the reader can weigh it.
- `static/tokens.css` — every colour, and the three **colour sets**. A set covers the two
  channels where colour separates one meaning from another — a difference, and severity —
  and carries a light and a dark variant; `data-palette` on `:root` chooses one. In CSS
  rather than in a script because `cssPalette()` already reads the stack's colours off
  these tokens, so a second table would be a second answer. Each set states its contrast
  **and** its separation (rule 69). `--graph-unchanged`, `--graph-unclaimed` and
  `--graph-mixed` sit outside the sets on purpose: a set covers the *directions* of
  difference, and a ground — or "more than one direction" — is not one of them.
- `web/vocabulary.py` — the three naming lanes served, and matched against one name. The
  membership test is `Convention.glob`, which is the same string the exceptions query is
  built from, so the claim and the population cannot drift (rule 41).

  **Derived and stated are two pages, and the word *derived* is why.** A page of conventions
  holding 100% of the time, headed "Naming standard", reads as conformance to a rule somebody
  wrote — which DunneFlow has no evidence for and cannot yet import a standard to get any. So
  *Derived naming standard* counts what the code does, *Stated naming rules* quotes what
  somebody wrote, and they never share a screen a reader could take for a comparison. The
  Markdown report carries both under one title, *as found*, because a document is read top to
  bottom and its two sections announce themselves; a navigator row is read one word at a time.
  Flattening the two under one word would relabel a quotation as an inference, which is what
  the four provenance tiers exist to prevent.

  **The stated lane is read in one place**, `resolve/stated.py`, beside `resolve/naming.py`'s
  Form lane — the query, `StatedRule`, and the `checkable` sentence. It lived beside the
  renderer while the renderer was its only caller (rule 51). `checkable` means the rule *names
  both a class of identifier and a spelling*, so a check could be written; **no check is run**,
  and both surfaces print the one sentence that says so. `scope` and `pattern` were in the
  schema from the day the scanner was written and read by nothing until the stated page drew
  them — a rule that names a spelling and no identifier class is kept with an empty `scope`
  and says which half it is missing (design rule 1).

  **Three absences, three answers** (design rule 21). No documentation was read at all; some
  was read and there was none; documents were read and none of them states a naming rule. They
  arrive as the same empty list, so `read` travels beside the counts — flattening them turns
  *"we did not look"* into *"there is nothing there"*. And *"read it in the document"* is drawn
  only where `/api/stated`'s `corpus` block says `docsource.db` can serve the version on screen,
  which is the glossary's `sidecars` argument one page over: a capability, never a hope.
- `web/changes.py` — the **fact lane**: what a routine does differently, which routines and
  tables and constants each version has, **what a caller passes**, and **what explains it**. `call_args` is
  compared by joining through `calls.site_id` to reach an owner — and `site_id` itself is
  kept *out* of the key, because it carries an ordinal among identical expressions and
  inserting a third `emit()` would renumber every site after it. Arguments are canonicalised
  before being judged different, because they are stored as written (rules 8 and 75) and a
  re-wrapped message is not a change to what a routine does; **constants are not**, because
  `_literal` already unparses them on the way in. Two columns, two answers, and the
  difference is how each is filled rather than what it holds. **Comments are a third
  answer to the same question, and a band of their own.** A leading comment sits above the
  `def` and so outside that routine's `body_hash` — rewritten, it surfaced as `<module>` in
  *edited only* or as *"No differences found"*, depending only on whether the file had
  module-level code. `explained_only` holds what would otherwise be in no band and a routine
  already in one carries a `comments` tag instead, so the four bands stay a partition. They
  are compared **joined in line order and collapsed**, never as written: 86% of Mensores'
  18,731 comment lines live in a run of two or more, and a corpus-wide re-wrap that changes
  no word reports 1,561 false differences as written and none joined. Bounded to the files
  whose `content_hash` differs — 41 ms to 5.2 ms, same answer — which is why it costs
  `/api/changes` nothing measurable (451 → 448 ms).

  **A docstring is the same question from the other side, and it is a tag rather than a
  band.** A comment can sit *outside* a routine's `body_hash` and vanish; a docstring is
  inside the `def` and never does — it lands in *edited only*, the band whose whole claim is
  *internal computation, the one thing this tool exists not to report*. So what is corrected
  is the reason a row gives, not its absence: `docstring` rides beside `comments` and neither
  decides a band. The **canonical form differs from the comment lane's, and the difference is
  measured rather than preferred** — paragraphs are kept. Over Mensores' 3,769 docstrings,
  re-wrapping every one at three widths without altering a word reports 2,060 · 1,652 · 1,602
  as written and **none** under either canonical form; merging every docstring's paragraphs,
  which destroys the separation PEP 257 gives the summary line, is reported by a full
  collapse **not at all** and by the paragraph-preserving form for all 1,996. Same zero on
  the noise, 1,996 more on the signal — which is what chose it.

  **A module docstring is a third subject, and it is a file.** `files.doc` states what a
  module *is* — 619 of Mensores' 628 files — and belongs to no routine. `modules_explained`
  carries a path, because a row must be able to open something (rule 30) and the code
  browser's route already does. Both new lanes together are **+3 ms** (451 → 454, median of
  eight alternating builds on a warm disk), and `_changed_files` is one bound three lanes
  take rather than three copies waiting to disagree.
- `web/filediff.py` — the **text lane** of a comparison, beside `changes.py`'s fact lane.
  The file-level answer costs **no body reads at all**: the sidecar is content-addressed,
  so equal hashes are equal bytes and comparing two path maps *is* the file-level diff.
  That is what makes the expensive lane affordable — `difflib` runs only on a file the
  reader opened, and only where the hashes already say it differs. `autojunk=False`,
  measured rather than preferred (see the budget below).
- `web/search.py` — searching the **text**, which is the one question the graph cannot
  answer: `touches`, `impact` and the glossary search names and meanings, and none of them
  can find a word inside a comment or a string. **Files first** — 626 rows with a count on
  each, never bounded — and one file's lines only when someone opens it, because the margin
  is ten queries a file and a broad word touches 166. One compiled pattern serves both
  passes so the count on a row and the lines beneath it cannot disagree (rule 13). Where a
  hit sits is a line-range lookup, innermost span first; there is no name in the question,
  so rule 5 never arises and rule 10 decides which scope wins.
- `web/code.py` — the code browser. **Links are lookups, never name matches**: `calls`
  already carries `callee_id`, so a clickable name in the source is the resolver's own
  answer. What it does *not* carry is a column, so a call is underlined only where its
  expression occurs exactly once on its line and goes to the margin otherwise — inventing a
  column is inventing a position (rule 1).
- `sourcedb.py` — `WORKING` is a **state**, not an id; a revision is identified by when it
  was captured. `seal()` keeps the current snapshot under its own name so the next capture
  is a second one rather than a replacement. Nothing reads a second revision yet.
- `sql.py` — reads schemas out of the `CREATE TABLE` statements the code contains.

## Rules learned the hard way

These each came from a false result on real code. Keep them.

*There is no engineering rule 21, and nothing is missing.* The numbers are cited from code
comments, tests and `HANDOFF.md`, so they are addresses rather than an ordering and are
never reused or closed up. Every "design rule 21" in the codebase refers to the dashboard
rule of that number — a blank canvas must say why it is blank — which does exist.

**The index is below; the rules themselves are in `RULES.md`.** A title is the rule and is
enough to recognise that one applies — it is not enough to apply it. **Read the body before
working in the area it governs**, because every one of these was, at the time, the obvious
thing to do, and the title alone will let you agree with a rule and reimplement the defect
it was written from.

```
  1. Precision beats recall.
  2. A call that touches a boundary is never also an internal edge.
  3. Builtins never resolve to local routines.
  4. Names imported from outside the program stay outside it.
  5. Never match on a bare common method name.
  6. Mark confidence honestly.
  7. Registration is not always a decorator.
  8. Bound every diagram — and only a diagram.
  9. Documentation is never code.
 10. A nested function must carry its enclosing scope in its qualname.
 11. Follow base classes when resolving `self.x`.
 12. A fenced block is code, not prose — rule 9 in the mirror.
 13. A claim's query must return exactly what is printed beside it.
 14. With thousands of tests, agreement is expected.
 15. A branch that consumes lines must offer them to every detector that wants them.
 16. Never open a database as the wrong kind.
 17. A program names its files, and those names are vocabulary.
 18. Every comment must land on something, and the module scope owns what no function
     does.
 19. A constant is a name, and a `Literal` alias is an enum.
 20. A read may refuse, but it may never repair.
 22. A node is a billboard, not a disc.
 23. A shadow is never drawn, and never an endpoint. The crossings are the point.
 24. A measurement must measure the thing it names.
 25. The one store that is not derived must never be discarded.
 26. External is not inferred.
 27. A marker counts only where it touches.
 28. A `rem` inside `@media` is not the page's `rem`.
 29. A media query contributes no specificity, so equal selectors go to source order.
 30. A label is not an identity.
 31. A shadow is never an endpoint — when *reading* an edge as much as when drawing one.
 32. A count must say what it counts.
 33. A trail step must carry its subject, or the trail cannot take anyone back.
 34. Pinned data hides in prose, and that is the hiding place the guards missed.
 35. A `let X = []` that nothing assigns is an empty view with no symptom.
 36. A generic loop narrowed to a literal is how a feature disappears without a trace.
 37. A guard that checks a name appears has not checked that anything happens.
 38. An instrument that cannot see cannot report.
 39. A plausible diagnosis of a real symptom is still a guess, and this one named the
     wrong plane for two sessions.
 40. Two detectors recording one act is two numbers about one thing.
 41. A prose claim and a machine-readable population are two things, and only one of
     them can be asked a question.
 42. A guard that names the right case may still not catch it.
 43. A check that cries wolf has already failed, and it fails silently.
 44. A live control reading a field the server does not send renders nothing and throws
     nothing.
 45. Hidden is not absent, and the difference is the whole bill.
 46. An opening rule that names a position breaks exactly as an ordering one does.
 47. Dimming says what is not yours; it does not say which one is.
 48. A scripted click proves the handler; only a pointer proves the path to it.
 49. A fallback that yields a plausible value has hidden the failure it was written for.
 50. A scroller is the element that scrolls, not the one that declares `overflow`.
 51. A rule kept at a call site rots as callers are added; move it to where they all
     pass.
 52. A cache that takes a value has already done the work it exists to avoid.
 53. A layout bounded by arithmetic is right at one window size.
 54. A guard that names the wrong container has not guarded anything, and the container
     is usually the generated one.
 55. A bound must be on the work, not only on the answer.
 56. A file restored to disk is not a module restored to memory.
 57. Admitting a directory for its documents must not admit a copy of the program.
 58. A second read-only handle to a database this process already holds open is 36x
     slower, and it is only slow while the tool is doing its job.
 59. A mutation harness must prove its baseline is green, or every mutation reads as
     caught.
 60. A stored path is a key before it is a location, and an absolute one is a bad key.
 61. A second way into the store must obey the rule the first one was taught.
 62. A migration may re-stamp the fingerprint it satisfies, and only that one.
 63. A store's reader must read the columns that exist, not the ones this version of the
     code knows about.
 64. The leaf that identifies a tree is the package root's, not the analysed
     directory's.
 65. Name a set for where it is, not for what befell it.
 66. An order the tool cannot defend is not an order.
 67. A control's value is state, and the browser will supply one if you do not.
 68. A restore is a setter, and it must do what the setter does.
 69. Contrast says whether a colour can be *read*; it says nothing about whether two
     colours can be told *apart*.
 70. The version on screen decides which bytes, and the sidecar cannot know which that
     is.
 71. A class name is global, and a stylesheet gives no warning.
 72. A gesture's target is not what is under the pointer, and an instrument that cannot
     reproduce that reports its absence just as confidently.
 73. A picture must not move under a gesture, and identity is what survives when it
     does.
 74. A fold is not one of the things it folds.
 75. A column offset is a *byte* offset, and a character slice is silently short.
 76. An echo is not an act, and the engine cannot tell you which it is sending.
 77. A synthetic subject is minted on a condition, so it cannot carry a fact that does
     not share it.
 78. A pane brought up to date by the control that moved it is only as correct as the
     last person to add a control.
 79. A lifetime change is an access-pattern change.
 80. A job that can be interrupted must leave something that cannot be mistaken for
     a finished one.
 81. A key that decides whether to skip work must carry everything the work depends on.
 82. A long job is not a switch — a slot names what is being replaced, not what is
     running.
```

## Anomalies: the discipline

`anomalies.py` reports what looks wrong. It exists under one rule:

> **Every finding must state what would make it a false alarm.**

This is not politeness. On the first run against a live codebase, *six confident
findings in a row were defects in this tool*, not in the program being read. A
finding without its `blind_spot` is a guess wearing a uniform.

- **Severity** (BROKEN / SUSPECT / INFO) says what it would mean for the program.
- **Confidence** (CERTAIN / PROBABLE / POSSIBLE) says how sure the tool is.
- These are different questions. Never blur them.

Ingest must never fail on a broken program: unparseable files yield recorded errors,
colliding definitions keep separate identities, and an edge lost to ambiguity is
recorded as `LOST_EDGE` rather than silently omitted — a missing connection must be
visible, or a broken program documents as a smaller working one.

`dunneflow check` exits non-zero only on BROKEN, so it can gate CI.

**Before adding a detector**, verify a sample of its findings against real source. If
the first thing it reports is a limitation of DunneFlow, fix the limitation instead of
shipping the detector.

## Dashboard: design rules

A reading tool for someone orienting in code they did not write. Settled shape: a local
server (`dunneflow serve`), three panes — navigator, centre view, inspector — where the
centre pane is a mode toggle (graph / table / document) over one shared selection, not
three destinations. **Vanilla JS + deck.gl, served by `http.server`** — no framework, no
Node at runtime or build, deck.gl vendored into `web/vendor/`.

*Astro 5 + Tailwind 4 was ratified here and has been struck, on evidence.* It was chosen
before the graph became the defining requirement and before the ratified mockup turned
out to be vanilla with a hand-authored 832-line token stylesheet and no Tailwind at all.
The graph must be WebGL whichever stack wins, so Astro bought a build step and Tailwind
bought a rewrite of settled CSS, neither of which serves the thing the tool is for.

**The index is below; the rules themselves are in `DESIGN-RULES.md`.** Several exist only
as reasoning — what was tried, what it cost, and why the obvious alternative was rejected —
so read the body before building against one.

```
  1. No filter is ever silent.
  2. When two options are genuinely interchangeable, build both and make it a Setting.
  3. Everything dimensional is stored in `rem`, never `px`.
  4. Colour is the scarcest channel; spend it on one dimension at a time.
  5. Confidence is shape, not colour.
  6. Customisation is clamped, and says why.
  7. Accessibility limits are documented in the product, not apologised for.
  8. A program is never alone.
  9. The anomaly view is a worklist, not a report.
 10. Documentation is evidence, even though it is never code.
 11. Documentation and source are equal inputs; neither may be assumed present.
 12. A cached graph is valid only if the source AND the tool that read it are unchanged.
 13. Every reported meaning must carry its provenance, and the provenance must open.
 14. Deterministic by default; egress is scoped, never a switch.
 15. Build for the explorer, not only the navigator.
 16. A control that renders but is wired to nothing looks exactly like one that works.
 17. View state is local, and exported deliberately.
 18. The stack is an abstraction, not an object — so do not draw it.
 19. Edges are shown on demand, never by default.
 20. Frame the bounding cylinder at the tilt in force, and always offer a way back.
 21. A blank canvas must say why it is blank.
 22. Spread is three axes, and the fourth control is zoom.
 23. Hiding and collapsing are separate switches.
 24. A pane collapses to a rail, and the rail says which pane it is.
 25. The primary way in is a pane, not furniture.
 26. The list and the picture are one instrument, and it has to run both ways.
 27. A container's affordance drowns out the affordances inside it, because it wins on
     area.
 28. Inference is voluntary and secondary, and a map states whether any was used.
 29. A hidden control is not a dimmed one.
```

## Adding a language

Write one extractor that emits `FileFacts`. Nothing else changes — the resolver,
renderers, and orientation queries know nothing about any specific language. Swift is
the obvious next one.

## Shared library: dunnecorp-shared

This project consumes `github.com/aacloudguy/dunnecorp-shared`, DunneCorp's
shared library of code, Claude Code skills, governance templates, and CI
patterns.

**Before writing any new utility, helper, workflow, skill, or template, check
whether it already exists there.** The library exists specifically because the
same concepts were being rebuilt independently in each repository.

How to check, in order:

1. Read `catalog.json` in the shared library and match the task against the
   `use_when` field of each asset.
2. If an asset matches, use it. Add the dependency rather than reimplementing.
3. If something close but not exact exists, prefer extending it in the shared
   library (via a PR there) over writing a local variant here.
4. Only write something new here when nothing comparable exists, or when the
   need is genuinely specific to this project.

If the library is not checked out locally, read the catalog directly:

```bash
gh api repos/aacloudguy/dunnecorp-shared/contents/catalog.json \
  --jq '.content' | base64 -d
```

A local checkout exists at `../SharedCode`.

### Contributing back

If you build something here that is reusable, it belongs in the shared library.
Open a PR against `dunnecorp-shared` following its `CONTRIBUTING.md`: add the
asset, register it in `catalog.json` with a `use_when` trigger, and include the
required ADR/CMR record. Then depend on the new tag from here.

DunneFlow itself is a candidate for `packages/python/` once it settles.
