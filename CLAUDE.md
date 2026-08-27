# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. Built for a reader who reads code but does not write it, and who thinks in
entrypoints, flows, routines, and boundaries.

## What this tool is for

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back out.
**What moves is the subject. Internal computation is not.**

Deliberately *not* reported: local variables, arithmetic, control flow, and private
helpers that neither touch a boundary nor sit on a path to one. Leaving those out is
most of what makes the output readable — do not "improve" the tool by adding them.

The goal is **comprehension, not documentation**. Judge a change by whether it helps
someone orient in an unfamiliar codebase, not by how many pages it emits.

## Commands

```bash
uv run dunneflow analyze  <path> --name <program>   # extract, resolve, write the map
uv run dunneflow touches  <path> --routine <name>   # what does this reach?
uv run dunneflow impact   <path> --routine <name>   # what breaks if I change it?
uv run dunneflow glossary <path>                    # what its words mean, and who says so
uv run dunneflow naming   <path>                    # the naming standard, stated and measured
uv run dunneflow query    <path> --sql "..."        # ask the graph directly
```

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`).

`analyze` is incremental: unchanged files are not re-parsed.

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then verify against real code, because unit tests on a toy program cannot catch a
resolution defect that only appears at scale:

```bash
uv run dunneflow analyze ../mensores-overhaul/src --name mensores
```

**`../mensores-overhaul` is read-only.** It is a copy kept for documentation. Never
write to it. All output belongs in `output/`.

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

### Performance budget (measured on mensores: 623 files, 184k lines)

| Measure | Budget |
|---|---|
| Cold full analysis | < 90 s |
| Warm re-analysis, nothing changed | < 5 s |
| Orientation query (touches / impact) | < 1 s |
| Peak memory | < 1 GB, flat as file count grows |

Documentation (2,381 documents, 44 MB):

| Measure | Budget | Measured |
|---|---|---|
| Cold documentation scan | < 20 s | ~18 s |
| Warm re-scan, nothing changed | < 2 s | 0.9 s |

The warm gate is `(mtime, size)`, falling through to the content hash whenever either
differs. Hashing 44 MB off the external volume costs eighteen seconds whether anything
changed or not, which turns re-analysis back into an event. Blind spot: a document
rewritten to exactly its old length with its modification time preserved is missed;
`--recheck-docs` hashes everything.

The machine's source volume is a slow external disk; cold reads cost far more than
warm ones. That is expected and is not a regression.

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
- `store.py` — SQLite. **The spine, not an export format.** Nothing holds the whole
  program in memory; reachability is recursive SQL over indexed edges. This is the one
  decision that lets the tool survive growth — do not replace it with in-memory graphs.
- `extractors/python/` — stdlib `ast` + `tokenize` only. No third-party parser.
- `extractors/docs/` — Markdown, reStructuredText and plain text, scanned by hand for
  the same reason: no markdown library. Emits `DocFacts`.
- `docstore.py` — `docs.db`. **Parallel to the graph, never inside it.** A doc rescan
  never touches `graph.db`, code-only analysis stays cheap, and the corpus stays a
  separately handable artifact — many will hand over a charter and never a line of
  source. The join is one `ATTACH DATABASE` away.
- `detectors/*.yaml` — **the extension point.** Teaching the tool a new framework is a
  config edit here, not a code change. Prefer adding a rule over adding a branch.
- `resolve/` — call graph, CLI command trees, flows, naming conventions, glossary.
- `render/` — Markdown and Mermaid.
- `sql.py` — reads schemas out of the `CREATE TABLE` statements the code contains.

## Rules learned the hard way

These each came from a false result on real code. Keep them.

1. **Precision beats recall.** A false edge tells the reader something is connected
   when it is not — worse than a missing edge. Every match must be defensible.
2. **A call that touches a boundary is never also an internal edge.** `conn.execute()`
   is sqlite3, not a local routine named `execute`. Ignoring this invented 919 edges.
3. **Builtins never resolve to local routines.** A program defining `list` does not
   make every `list(...)` call a call to it. This invented 261 edges.
4. **Names imported from outside the program stay outside it.** `from dataclasses
   import field` means `field(...)` is theirs.
5. **Never match on a bare common method name.** `create`, `poll`, `get`, `execute`
   are everywhere. Match on a qualified path (`.messages.create`) or a library prefix.
6. **Mark confidence honestly.** `CERTAIN` when pinned by import, module, or class;
   `INFERRED` when resolved by unique name. Never blur them.
7. **Registration is not always a decorator.** Commands are also registered by direct
   call (`app.command(name="x")(fn)`), by argparse `set_defaults(func=...)`, and by
   subclassing (`do_POST`). Each of these was invisible until handled, and each made a
   whole executable look like it did nothing.
8. **Bound every diagram — and only a diagram.** A picture of 4,500 routines is not
   a picture. Abbreviation is allowed *only* where the complete content sits beside
   it: every bounded diagram is followed by a full listing of what it left out.
   Reference lists are never bounded. There is no mandate to save space.
   **Never truncate at ingest** — a value shortened before it reaches the store is
   lost for good rather than merely unshown. `_literal`, comment text, and SQL
   statements are all recorded whole.
9. **Documentation is never code.** Docstrings are excluded from code-shaped
   detectors. `"""Update a field on the org-config"""` is a sentence about a
   statement, not a statement — 248 phantom SQL statements came from reading them.
   Comments are different: they never reach a parser at all. They are tokenized
   separately and attached as metadata, and they are the only source of the
   governance layer. **Never strip comments to "help" a parser** — they are not in
   its way, and removing them would cost the WHY that the whole tool exists to show.
10. **A nested function must carry its enclosing scope in its qualname.** Seven
    closures called `_close_ladybug`, one per factory, are seven routines. Collapsing
    them made every call to any of them ambiguous, and ambiguity loses the edge.
11. **Follow base classes when resolving `self.x`.** Inherited methods are ordinary;
    not following them dropped 113 real edges.

12. **A fenced block is code, not prose — rule 9 in the mirror.** Rule 9 keeps
    docstrings out of code-shaped detectors because a sentence about a statement is not
    a statement. The same argument runs backwards: an example inside a fence is a
    statement, not a sentence, and mining a definition out of one is the same defect
    wearing the opposite uniform. Nothing prose-shaped is ever read from inside a fence.
    The same care applies to markup: `<role>` in `mensores-<role>` is a placeholder, and
    a tag-stripper that eats it has shortened a value at ingest.

13. **A claim's query must return exactly what is printed beside it.** Every measured
    convention ships the SQL that produced it. Three of the first twenty-seven returned
    something else — a glob matched `iso_utc_now` as a routine beginning with `is`, and
    a house-prefix count had its numerator over multi-segment names and its denominator
    over all of them. A query that disagrees with the number beside it is worse than no
    query: it invites a reader to check, and then misleads them. A test asserts the
    agreement on every convention.

14. **With thousands of tests, agreement is expected.** Affix conventions are mined by
    trying every affix against every property, which is thousands of comparisons. At
    that many, "a class ending in `Provenance` is a dataclass, 7 of 7" happens by
    itself — two classes in five are dataclasses anyway. Precision, sample size and
    lift all passed it; only a coincidence test corrected for the number of tries
    separates it from `*Error`, 372 of 375. Rule 5 in a statistical key.

15. **Never open a database as the wrong kind.** Pointing `--db` at `docs.db` opened it
    as a graph, failed the staleness check, and dropped every table in it — a
    destructive fallback wearing the costume of a version upgrade. Both stores now stamp
    their kind and refuse the other, before anything is allowed to drop anything.

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
three destinations. Astro 5 + Tailwind 4, built assets shipped inside the package so
`uv run` needs no Node.

1. **No filter is ever silent.** A filtered view states what it removed, in counts, with
   the hidden set one click away. Same discipline as `LOST_EDGE` and rule 8 above: a
   missing thing must be visible, or the reader mistakes a slice for the whole. Knowing
   what you are *not* looking at is the state-awareness problem the whole UI turns on.

2. **When two options are genuinely interchangeable, build both and make it a Setting.**
   Real use decides; the loser can be retired later on evidence, which is why usage is
   counted locally. This is not licence to defer every decision — it applies only when
   both choices are actually good.

3. **Everything dimensional is stored in `rem`, never `px`.** One root scale multiplier
   must resize the whole surface together — type, column widths, row heights, padding,
   icons, graph nodes. A width stored in pixels is a width the multiplier cannot reach,
   and the layout then breaks for everyone who is not its author.

4. **Colour is the scarcest channel; spend it on one dimension at a time.** Nine boundary
   kinds are not nine distinguishable colours, and the temporal layers still need added /
   removed / modified. Kind is icon plus label; colour follows an explicit "colour by"
   selector.

5. **Confidence is shape, not colour.** Solid edge = CERTAIN, dashed = INFERRED, plus a
   global "hide inferred" toggle so the defensible skeleton can be read alone. Severity
   and confidence stay separate channels, exactly as in `anomalies.py`.

6. **Customisation is clamped, and says why.** Settings may change colour and size within
   limits that keep text legible — 4.5:1 for body text, 3:1 for large text and chrome,
   computed live and shown beside the swatch. A refusal states its reason, the same way a
   finding states its blind spot.

7. **Accessibility limits are documented in the product, not apologised for.** A node
   graph stops being meaningfully screen-reader navigable past roughly fifty nodes; the
   complete table beside it is the accessible path, not a fallback. Mermaid's generated
   SVG can be themed but its focus order cannot be controlled. Pan and zoom need keyboard
   equivalents. These live on a visible Accessibility page.

8. **A program is never alone.** Calling one program "one program" is a convenience, not a
   fact. Every node carries a source status: `ANALYZED` (we have the source),
   `KNOWN_INTERFACE` (we see the call leave and know protocol, verb, destination, port,
   timeout, retries, payload — SAP, Oracle, a REST endpoint), or `OPAQUE` (something
   leaves and we cannot say to what). Externals are first-class nodes at the boundary,
   badged as outside our control. `net_calls` already records this. Pointing DunneFlow at
   an external's source flips it to `ANALYZED` in place — cross-program stitching is not a
   new UI, only a fuller one.

9. **The anomaly view is a worklist, not a report.** Observed, not assumed: the first
   move on opening the dashboard was to jump to SUSPECT and start clearing findings one
   by one — BROKEN would have come first, and a red table would have been clicked before
   either. Red and amber are read as a call to action. So findings are traversable
   (`j`/`k`, next/prev), carry triage state, and show progress. Triage has three
   outcomes, and the third is load-bearing: *the blind spot applies*, *real and
   acknowledged*, and *this is a DunneFlow defect*. The third is a different pile,
   because a detector whose findings are repeatedly dismissed that way is the detector
   to fix — the rule under "Before adding a detector" applied after the fact.

10. **Documentation is evidence, even though it is never code.** Rule 9 keeps docstrings
    out of *code-shaped* detectors, because a sentence about a statement is not a
    statement. It does not mean prose is worthless -- for a glossary, being prose is the
    qualification. A program's vocabulary is almost never defined in its code: Mensores
    states its entire Latin naming scheme in `NAMING.md` and defines `mensor` in
    `PROJECT.md`, and DunneFlow saw neither. Look for the definition before generating
    one, and prefer a quotation with a file and line over anything a model writes.

11. **Documentation and source are equal inputs; neither may be assumed present.**
    `analyze` reads both, and each is a check on the other. But documentation is often
    absent, partial, or wrong -- porting five abandoned games taught that the badly
    documented case is the normal one -- so every reverse-engineering path must keep
    working with no documentation at all. Never make a doc-derived fact a prerequisite
    for a code-derived one.

12. **A cached graph is valid only if the source AND the tool that read it are
    unchanged.** The file cache keys on source content, so editing `detectors/*.yaml` --
    the extension point, and therefore the thing edited most -- left every cached fact
    answering the old rule while the new rule silently never ran. The cache key is now
    `SCHEMA_VERSION` plus a hash of every detector file, and a mismatch discards the
    graph and says so.

13. **Every reported meaning must carry its provenance, and the provenance must open.**
    A definition or a naming rule is a claim, and a claim without its source is an
    assertion wearing a uniform -- the same failure `blind_spot` exists to prevent on the
    anomaly side. Each tier proves itself differently: a **quoted** definition proves
    itself with a file and line the reader can click through to and read in context,
    highlighted, in the surrounding source; a **measured** claim proves itself with the
    query that counted it, reproducible via `dunneflow query`; an **inferred** one cannot
    prove itself at all and must say so. Never render a definition without the route back
    to where it came from.

14. **Deterministic by default; egress is scoped, never a switch.** Everything DunneFlow
    reports is read from local files by local code, and the product is complete that way.
    Anything needing a model lives on its own page -- never buried in Settings, never run
    during `analyze`, never on a schedule -- and is off until turned on. Consent is
    per-corpus, because the surfaces differ: many will send documentation and never
    source. The postures are Off / Documentation / Documentation + identifiers /
    Everything / Local endpoint, each operation declares which it needs, and one it does
    not have stays disabled with the reason shown. Before any run, show the exact file
    manifest that would leave the machine.

15. **Build for the explorer, not only the navigator.** Orientation \u2014 "where do I
    start, what is the shape" \u2014 is the first need, not the lasting one. The way this
    gets used is: see something, get curious, notice something beside it, pull the
    thread, get distracted, learn something never intended. That mode wants different
    furniture, and it is furniture, not decoration:

    - **A trail.** A visible record of the journey, not the hierarchy \u2014 clickable,
      steppable, branchable. Nobody chases a rabbit if they might not find their way
      back; the trail is what makes the detour free.
    - **Threads to pull.** Beside the call graph, the *reasons* a neighbour is worth a
      detour: shares a plan, the other end of an emit, the most commented routine in the
      program. Adjacency by interest, not only by edge.
    - **Somewhere to put what you found.** You go looking for one thing and find
      another; it needs a shelf, or the detour costs you the thread you were on.
    - **Curiosities.** What came out furthest from the middle \u2014 264 comments on one
      routine, four closures deep, a table written twice as often as it is read. Not
      problems. Doorways.

    Judge a feature by whether it makes pulling the next thread easy and rewarding.

16. **A control that renders but is wired to nothing looks exactly like one that
    works.** Eight of eleven left-hand menu items silently showed the graph instead of
    their own page, because a patch to add the missing branch matched nothing and
    reported success. Two defences, both cheap: route from a *table*, so an unhandled
    case logs an error rather than falling through to a default that looks deliberate;
    and run a startup self-check that names any control nothing listens for, with its
    list derived from the source rather than hand-kept so it cannot drift. When editing
    by string replacement, assert the pattern matched -- a silent no-op is the most
    expensive kind of edit.

17. **View state is local, and exported deliberately.** Column widths, density, chosen
   columns, saved filters, and expansion state persist per program, keyed by stable
   identity so they survive switching revisions. They travel only when someone exports
   them, and a recipient always keeps their own scale multiplier.

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
