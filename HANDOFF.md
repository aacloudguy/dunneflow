# DunneFlow — state and open questions

Written 2026-08-27. Engineering rules live in `CLAUDE.md`; this is where things stand
and what needs deciding.

## Where it stands

Working, verified against Society of Mensores (623 files, 184k lines):

| Capability | State |
|---|---|
| Python extraction (`ast` + `tokenize`, stdlib only) | done |
| Module docstrings captured whole (`files.doc`) | done |
| Schema-version invalidation: a stale graph is discarded, not reused | done |
| Call resolution, incl. inheritance and CLI registration idioms | done |
| CLI command trees (Typer, Click, argparse, MCP, HTTP handlers) | done |
| Flows, boundaries, data structures | done |
| Database: schemas from `CREATE TABLE`, read/write matrix | done |
| Network: protocol, verb, sync/async, timeout, retries, port, payload | done |
| Messaging: brokers, producers/consumers, ack, kept separate from RPC | done |
| Anomaly detection with severity, confidence, and blind spots | done |
| Markdown + Mermaid rendering, complete (no omissions) | done |
| **Documentation ingest** — `DocFacts`, `docs.db`, markdown/rst/text reader | **done** |
| **Glossary** — terms bound to the documentation that defines them | **done** |
| **Naming standard** — two lanes: stated Vocabulary, measured Form | **done** |
| **Traceability** — governance ids joined across both stores, seven bands | **done** |
| **Named artefacts** — files the program names (`tabularium.db`) | **done** |
| **The mirror** — defined words the code does not use, four bands | **done** |
| **Comments** — every one reaches the store, 18,208 of 18,208 | **done** |
| **Named values** — 2,618 constants and 86 type aliases | **done** |
| Stable identity across edits (prerequisite for layers) | done |
| **Interactive dashboard — the 2.5D graph** | built 2026-08-27, 60 fps at every measured load |
| **Interactive dashboard — shell, cover, navigator, worklist** | **built 2026-08-28, reading from the store** |
| **The graph mounted inside the shell** | **next: chunk 2** |
| **Temporal layers / snapshots / flow diff** | **not started — after the static view** |
| TypeScript extraction (`ts-morph` sidecar) | not started |
| LLM narration | not started |
| Cross-process stitching: outbound call → the handler that serves it | not started |

Commands: `dunneflow analyze | touches | impact | check | glossary | naming | mirror | query`.
Gates: 227 tests, mypy clean, ruff clean. Cold run 4.1s of code plus ~17s of documentation, against budgets of 90s and 20s; warm 2.7s total.

## Verify it still works

```bash
uv run pytest && uv run mypy . && uv run ruff check .
uv run dunneflow analyze ../mensores-overhaul/src --name mensores
```

All four executables (`mensores`, `mensores-mcp`, `mensores-signator`,
`mensores-scriba`) must appear in "Where to start" with plausible reach. A reach of 1
or 2 means a registration idiom is being missed.

For documentation, the ground truth is in `CLAUDE.md` — and its most important half is
negative: `.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper
*about* naming standards and must yield **zero** naming rules.

`../mensores-overhaul` is read-only. Output goes only to `output/`.

## Layers: the temporal model

The dashboard is a **reading tool**, but code moves. The agreed model is a static view
of the program as it is, with change rendered as **peelable layers** over it — onion
skin, where the top layer is current and peeling back shows what changed and when.
Static view first, get it right, then layers.

**One decision was made early because it cannot be retrofitted: identity is now
derived from a routine's qualified name alone, never from its file position.** An id
containing a line number changes whenever anything above it moves, so a single added
import would retire every routine in that file and introduce identical replacements.
Across 611 commits in thirty days — Mensores' actual recent rate — that renders a change
view as thousands of false deletions. `Routine.body_hash` answers "did it change?"
separately from "is it the same routine?". `tests/test_identity.py` guards this; do not
weaken it.

What still needs building, when the time comes:

- **Snapshots.** The store currently holds one state and overwrites it. Layers need the
  graph keyed by a revision, with a diff computed between any two.
- **A flow diff, not a text diff.** The interesting change is not "these lines moved"
  but *what moves changed*: a new way in, a routine that now writes to a table it
  didn't, a signature whose types changed, a flow that reroutes, a boundary that
  appears, a new anomaly. That is the part worth looking at, and it is what DunneFlow
  can say that `git diff` cannot.
- **Node states** in the UI: unchanged, added, removed, modified — with modified
  distinguishing "edited" from "behaves differently".

### Version control must stay pluggable

DunneFlow should **never talk to a version control system to fetch code.** It analyses
whatever tree it is pointed at and records a revision label supplied from outside
(`--revision`, auto-detected from git when present, or a timestamp). Layers are then
snapshots keyed by that label.

This matters because git is not the only target: Epic's **Lore** is intended to be
supported later, and Perforce, a nightly cron, or a release tag must work identically.
Keeping the VCS at arm's length makes all of them the same problem. Anything that
shells out to `git` inside the extractor or resolver is a design error.

Mensores is under git (1,034 commits) and its commit messages carry the same governance
vocabulary the comments do — `Plan 87-02c`, `ISS-293`. A layer can therefore be
*labelled by the plan it belongs to*, which joins the temporal view to the governance
view already built.

## The dashboard: decided 2026-08-27

Design rules live in `CLAUDE.md` under "Dashboard: design rules". This records what was
chosen and what is still open.

**Shape.** Local server (`dunneflow serve output/<program>`) querying `graph.db` live —
not a self-contained file, because 26 MB of SQLite inlined breaks the store-as-spine
decision. Keep every dashboard query as SQL text in one module so the same strings can
later run client-side against `sqlite-wasm` over HTTP range requests; that is the path to
a static, mailable deployment without rewriting the query layer.

Three panes: navigator | centre view | inspector. The centre pane is a mode toggle —
graph, table, document — over one shared selection. Breadcrumb above it, expand-in-place
in the graph, never a drill-down that replaces the view. Hover = signature and one-line
WHY; click = select; double-click or Enter = descend. Keyboard equivalents throughout.

**Stack.** ~~Astro 5 + Tailwind 4~~ — **struck 2026-08-27**, see `CLAUDE.md`. Built as
vanilla JS + deck.gl on `http.server`. The colour reasoning below still stands and the
ratified token stylesheet is still the one to port; only the framework changed.

*Superseded:* Astro 5 + Tailwind 4, matching `../wct-site`. Its brand tokens are
light-mode-shaped, so the app uses semantic tokens (`--surface`, `--surface-raised`,
`--border`, `--text`, `--text-muted`, `--accent`, `--focus`) filled per theme. Teal
carries interaction in both themes; amber carries attention. Dark mode is new work —
wct-site has none.

**Opening screen.** Both the cover (ways in ranked by reach, boundary summary, anomaly
counts) and a package-level graph (~30 nodes for mensores, genuinely drawable), chosen by
Setting. Real use decides which survives.

**Inspector is flow-first, not signature-first.** IN (how it is reached) → OUT (what it
calls, with confidence) → TOUCHES → GOVERNANCE, with comments placed against the thing
they explain rather than pooled in a block, and source one click down. WHAT and WHY
interleaved; HOW reachable. Signature demoted into the params view.

**Anomalies** are ambient — badged on affected nodes wherever they appear — but off by
default, as a Setting. 93 suspect findings on mensores is a lot of badges, and rule 1
says a false signal costs more than a missing one.

**Usage counting.** Local, in the view-state store, feeding a usage report screen. Its
only purpose is to retire Settings on evidence rather than on opinion.

**Source storage — decided.** A content-addressed sidecar, `output/<program>/source.db`,
keyed by the `content_hash` already in `files`. The map then shows what was actually
measured and survives the source tree moving or being deleted, while `graph.db` stays
purely the fact store. `--no-source` becomes a file not written, and mailing a map
without the code becomes a file not attached — a per-recipient decision, not a
per-analysis one. Each unique file body is stored once no matter how many revisions
reference it, so the sidecar grows only by what genuinely changed; that is what makes
temporal layers storable at Mensores' rate of 611 commits in thirty days.

### Observed in use — 2026-08-27 mockup session

The first action on opening the dashboard was not the cover and not the graph: it was
**Anomalies → Suspect, intending to clear findings one at a time**. BROKEN would have
been first had any existed, and a red badge on a database table would have outranked
both. Red and amber are read as a call to action, not as decoration. The anomaly view is
therefore a worklist with triage state and progress, not a report — see the design rules
in `CLAUDE.md`. The cover's "what looks wrong" panel and the left rail's severity counts
are doorways into it.

Also observed: the colour picker was unusable because the settings view re-rendered on
every `input` event, destroying the native picker mid-drag. Live controls update in
place; only committed changes re-render.

### Wanted later

- **A graph viewer that holds 10,000+ nodes.** The hand-placed SVG package graph is
  adequate for orientation and will not scale. The reference is `../usdgraph` —
  NetworkX → OpenUSD, for 3D graph rendering with per-node styling and multi-edges.
  Not a priority; recorded so the SVG view is not mistaken for the endpoint.

### Glossary and naming standard — decided 2026-08-27

Three tiers, visually distinct, never blended:

- **DECLARED** — quoted from the source. 44 package-root docstrings carry real definitions
  (`disceptator` — "Interview engine"; `groma` — "the Mensores engine skeleton … the
  surveyor's instrument"). DunneFlow was reading and discarding these; `files.doc` now
  keeps them whole. This is the tier that does most of the work.
- **MEASURED** — counted, never guessed. `*_cmd` → registered command: 97/99 (98.0%);
  leading underscore → private: 4,293/4,293 once dunders are excluded; `*Error` →
  subclasses an exception: 372/375. **The exceptions are the product.** The three
  non-exception `*Error` classes are frozen dataclasses carrying error information that
  cannot be raised — verified against source, a real finding rather than a tool artefact.
- **INFERRED** — a language model's guess, run only on demand, always carrying the blind
  spot "nothing in the source states this".

Rule 9 stands unchanged and gains a carve-out: docstrings stay out of *code-shaped*
detectors, because a sentence about a statement is not a statement. The glossary is the
one feature where being prose is the qualification. `tests/test_glossary.py` guards both
halves — the docstring is captured whole, and it still never reaches the SQL or boundary
detectors.

**Egress is opt-in, priced, and double-confirmed.** A "One-time AI pass" panel in
Settings lists what a run would cover with a per-operation cost estimate; the first click
arms it and shows the total, the second runs it. Nothing infers during `analyze`, and
nothing runs on a schedule.

### The glossary's real job — found by testing the assumption

The feature was scoped as "infer what these words mean." Checking the source first
inverted it. Mensores already contains a fully authored naming standard:
`.groma/milestones/v1.1-harness-ownership/NAMING.md`, a table headed "The pantheon"
that maps every component to its Latin name with etymology and a historical-accuracy
rating -- `quaestor` = "the accounts magistrate who inquires into & audits the records
(root *quaerere*)"; `disceptator` = "one who argues out a contested point"; `groma` =
"the surveyor's instrument that lays out the lines". `.groma/PROJECT.md` carries its own
`## Glossary` section defining `mensor` from *mētior*, to measure.

**9 of the 11 opaque terms are already defined by the project.** Only `oscal` (a NIST
acronym) and `testkit` (an English compound) are undefined anywhere, and neither is a
coinage. The knowledge existed; DunneFlow could not see it because it read only source.

So the glossary's job is **binding existing documentation to the code**, not generating
definitions. Four provenances, never blended:

| Provenance | Source | Cost |
|---|---|---|
| `DECLARED · code` | module docstring, parsed | free |
| `DECLARED · docs` | a structured glossary heading or naming table, parsed | free |
| `CITED` | a model found it in prose documentation and cited file:line -- checkable | paid |
| `INFERRED` | nothing explains it; a guess -- not checkable | paid |

`CITED` is the tier that matters for other projects. Most codebases have charters,
READMEs and design write-ups rather than a `## Glossary` heading, and a model reading
prose and returning **quotations with citations** is doing extraction, not invention --
the result can be checked against the line it names. Mensores carries 2,449 prose
documents totalling 44 MB (~10.1M tokens); reading all of them costs $10-30, so the pass
triages by term co-occurrence first and reads only candidates (~34 documents, ~$1.20).

A classifier for "is this term explained or only named?" was built and **discarded**: it
scored `oscal` and `procurator` as explained when their glosses describe the module and
never touch the word. That distinction is semantic and a regex cannot make it. What
survived is one precise detector -- **a docstring that defines a term using the term**
(`dispensator -- the Mensores Dispensator`) -- narrowed to opaque words only, because
`feedback -- agent-feedback loop` is circular and harmless. One finding, correct.

### Documentation as a first-class input — decided 2026-08-27

Documentation is a parallel and equal input to `analyze`, not a side channel. **Every
reverse-engineering path stays**: documentation is often absent, partial, or wrong, and
the badly documented codebase is the normal case, not the exception.

The strongest deterministic link between the two is the governance vocabulary, which
both sides already carry. Measured on Mensores after normalising separators and
zero-padding (`ADR-0001` == `ADR 1`):

| | |
|---|---:|
| Governance ids in code annotations | 530 |
| Governance ids in prose documents | 930 |
| **Traceable in both** | **434 (82% of code ids)** |
| Code only — annotated work with no plan document | 96 |
| Docs only — planned or specified, never annotated in code | 496 |

That join needs no model. It is the shape of a drift report: what was built without a
plan, and what was planned without being built.

Also minable deterministically from 2,449 documents: 28 with a Glossary/Terminology/
Naming heading, 1,614 containing tables, 6,861 bold-term definition lines, 23,911
backticked code references.

**Storage: a parallel `docs.db`,** not the code graph. A doc rescan never touches
`graph.db`, code-only analysis stays cheap, and -- the reason that settled it -- the doc
corpus becomes a separately-handable artifact, the same logic as the source sidecar. The
join is one `ATTACH DATABASE` away, so keeping them apart costs nothing.

**Egress is scoped, not switched.** Postures: Off (default) / Documentation /
Documentation + identifiers / Everything / Local endpoint. Consent is per-corpus because
the surfaces genuinely differ -- many organisations will send a charter and never a line
of source. Each operation declares what it needs and stays disabled without it, and the
exact file manifest is shown before any run. Measured on Mensores, a definition-shaped
triage selects 57 of 2,449 documents (977 KB, ~225k tokens, ~$0.68) against $30.18 to
read the corpus whole.

**Provenance is the feature, not a footnote.** Every definition opens into a source
viewer showing the real file with the cited lines highlighted in context, switchable
between a term's several sources. Measured claims cite the SQL that counted them; all six
naming conventions were re-run against `graph.db` and reproduce exactly. An inferred
entry can prove nothing and says so.

**Not yet built.** This round established feasibility and cleared two blockers. The
extractor itself -- `DocFacts`, a markdown/rst reader, `documents` / `definitions` /
`doc_refs` tables, and doc discovery in `walk` -- is the next chunk.

### Two defects found and fixed while building this

1. **A stale graph was silently reused.** `CREATE TABLE IF NOT EXISTS` will not widen an
   existing table, and the file cache keys on source content alone — so an upgraded
   DunneFlow read an older graph in the old shape and re-parsed nothing to reveal it.
   `SCHEMA_VERSION` is now checked on open; a mismatch discards the graph and says so.
   The graph is derived data, rebuildable in 2.3s; a stale map that answers confidently
   is the one outcome this tool may not have.
2. **Phantom governance tickets.** The TICKET rule was `\b([A-Z]{2,10}-\d+)\b`, which is
   rule 5's failure in a new place: it matched every standard and cipher a program
   names. `SHA-256`, `UTF-8`, `ISO-8601`, `RFC-3161` and `IEEE-29148` accounted for 121
   phantom annotations across 10 distinct values. Found by joining code annotations
   against the same ids in documentation -- neither source would have revealed it alone.
   Fixed in `detectors/annotations.yaml` with an evidence-led denylist, not in code.
   4,834 annotations to 4,713; every real id kept.

3. **A rule edit did not invalidate the cache.** Fixing the above changed nothing,
   because the file cache keys on source content and no source file had changed. The
   cache key is now `SCHEMA_VERSION` plus a hash of every `detectors/*.yaml`, so editing
   the extension point invalidates the graph the way editing the schema does.

4. **A warm run under-reported the command tree.** `commands_attached` counted rows
   changed this run rather than state, so a cached re-analysis announced `0 commands`
   over a map holding 149. The map was intact throughout — the statistic was the defect.
   Both figures now read 149 cold and warm.

### Lessons from the 2026-08-27 session

Three separate bugs, one root cause: **a step that silently operates on the wrong input
and reports success.** Worth naming as a class, because it recurred three times in a day.

1. A `str.replace` patch targeted `else if (kind === "cover")` when the source said
   `if (kind === "cover")`. It matched nothing, reported success, and eight of eleven
   menu items silently showed the graph. Some patches that session asserted their
   pattern matched; this one did not.
2. A cached graph was reused across a schema change, then across a detector-rule
   change. Both produced a confident map answering the previous version's rules.
3. The local UI test server read the file once at import, so a re-test ran against the
   previous build and reported two working fixes as still broken.

The defence is the same in all three: **assert that the input is what you think it is,
and fail loudly when it is not.** Applied as: assert every string replacement matched;
key the graph cache on `SCHEMA_VERSION` + a hash of `detectors/*.yaml`; re-read on every
request in the test harness; route from a table so an unhandled case logs rather than
falling through to a default that looks deliberate; and a startup self-check that names
any control nothing listens for.

**Verify against real code, and doubt the tool first.** Four claims were wrong before
they were checked: a "degraded map" that was a race in my own reading; 275 underscore
"violations" that were `__init__` dunders; "6 of 80" boundary-touching constructors that
were 21; and an explained/vague term classifier that scored `oscal` and `procurator`
backwards and was discarded rather than shipped at 60%. The rule under "Anomalies" --
verify a sample before shipping a detector -- earned itself repeatedly.

**Programmatic checks do not replace looking.** Two defects passed every scripted test
and were obvious on screen: a long name breaking mid-token into "do_PO / ST", and trail
steps reading "Overviewcover" because the label was read from the whole button. The
breadcrumb lied on every screen for hours because no check asserted that it *changed*.

### Feature request: the project profile — a trend, not a grade (2026-08-27)

Requested after a survey of what the industry actually has. Recorded here rather than
built; it waits behind the documentation extractor and the dashboard.

**What the survey found.** There is no single standard for grading a project. There are
five separable families: a quality *vocabulary* (ISO/IEC 25010, eight characteristics,
which does not grade); *automated code measures* (ISO/IEC 5055:2021, counts of structural
weaknesses, needing CWE-level analysis DunneFlow does not do); *commercial ratings*
(SonarQube/SQALE, A–E over a technical-debt ratio); *repo and security scorecards*
(OpenSSF Scorecard, 18 checks each 0–10, risk-weighted, `-1` for "cannot evaluate"); and
*maturity rubrics* (Apereo OSS, 40+ criteria to Emerging / Established / Mature).

Two findings shaped the request. The percentage scale is the one shape the field tried
and abandoned for quality — the Maintainability Index (0–100) is the only widely-shipped
one and is also the most discredited, for opaque root cause and unjustifiable thresholds.
What survived is a letter or a 0–10 **per dimension**. And every credible scorecard ships
a disclaimer in this project's own voice: OpenSSF states that "a low score is not a
definitive indication that the project is at risk", and scores `-1` rather than folding
an unevaluable check into the average. That is `blind_spot` and `LOST_EDGE` under other
names.

**What was decided.** Build the five dimensions DunneFlow can evidence from facts it
already holds, and **promise nothing beyond a direction of travel**. Not "this project is
good"; not "this project is better than that one". Only: *is this one moving the right
way?*

| Dimension | Evidence already in the store |
|---|---|
| Naming compliance | the Form lane — population, prevalence, complete exception list |
| Documentation binding | glossary coverage of opaque terms; governance ids tracing to a document |
| Boundary hygiene | `net_calls` already holds timeout, retries, TLS per remote call |
| Structural integrity | call-resolution rate, `LOST_EDGE` count, unreachable routines, orphan ways in |
| Anomaly load | BROKEN / SUSPECT per thousand routines |

Deliberately **not** included, and to be printed as NOT ASSESSED rather than left as a
hole that reads as a pass: security compliance (ISO 5055 / SAST / CVE territory — point
at OpenSSF Scorecard, never reimplement it), internal code quality (complexity and
duplication are internal computation, which this tool exists not to report), delivery
performance (DORA needs telemetry we cannot see), and repo practice (file-presence checks
— cheap, but shallow enough to mislead).

**Requirements.**

1. **A time series, not a snapshot.** Every dimension is stored per revision and read as a
   trend. This is the same snapshot machinery temporal layers need, so the profile should
   be built *on* that, not beside it — a second store keyed by revision would be the
   mistake.
2. **A regression is highlighted.** A scan whose ranking falls against the previous one
   raises a visible alert, in the same register as a BROKEN finding: the reader should not
   have to go looking for the bad news. A rise is shown, not alerted.
3. **A graph on the metrics page.** Improvement over time, or the opposite, must be
   visible as a shape rather than read out of a table. The table stays beside it, complete
   — rule 8.
4. **No composite.** Five dimensions stay five. One number cannot state its blind spot,
   and collapsing them hides the exceptions, which are the product.
5. **Percentages only where the percentage is a real ratio.** 97 of 99 is 98% and means
   something. A synthesised "quality: 82%" means nothing and cannot say what would make it
   wrong.

Cheap if it stays a profile: five of the six come from work already in flight. Expensive
and dishonest the moment it has to yield one number for a slide.

### Built 2026-08-27: documentation, glossary, naming standard

`analyze` now reads prose as well as source. 2,381 documents, 310 definitions, 5 stated
rules, 1,230 distinct governance ids; ~18 s cold, 0.9 s warm. `10-glossary.md` and
`11-naming.md` are written every run.

**The naming standard has two lanes**, because there are two kinds of rule and rendering
them alike makes both read worse. **Form** — case, underscores, affixes — is counted
against the code: 27 conventions on Mensores, each with the query that produced it and
every exception listed. **Vocabulary** — *Latin only*, *always the binomial* — is quoted
whole from documentation, with the file and line, and says plainly when no query can
check it. Above both sits the one page a new developer would be handed, every line
badged and linked down into its evidence.

Two ground-truth numbers from the earlier session reproduced exactly and independently:
`*Error` subclasses an exception in **372 of 375** cases, and `*_cmd` is registered as a
command in **97 of 99**. Mensores states no Form rule anywhere, so that lane is entirely
measured — which is the honest answer, and the reason the measured miner had to exist.

What it cost, all of it found by looking rather than by testing:

* A research paper headed "Naming-Standards Importer Design" yielded ten confident
  naming rules. Fixed by classifying the document, not the section — three tiers of
  precedence, tested both ways.
* A document titled "… rebrand vocabulary" made every section in it a glossary, turning
  its three naming rules into three definitions. A level-1 heading is a title, not a
  section.
* 335 documents inside agent worktrees were copies of the project's own research.
  Content-addressed, marked as duplicates, counted once, and listed.
* `--db output/mensores/docs.db` opened the document store as a graph and dropped every
  table in it. Both stores now refuse the other kind.
* Three of the first twenty-seven measured conventions shipped a query that returned
  something other than the exceptions printed beside it.
* An affix miner that found "a class ending in `Provenance` is a dataclass, 7 of 7" —
  true, meaningless, and now filtered by a coincidence test.

Still open on this half, in the order they are likely to matter:

* **Known recall gaps, deliberately accepted.** Precision was bought with recall, and
  these are the receipts. A rule stated outside a naming section of a naming-standard
  document is lost — `NAMING.md`'s "**Do NOT field both `quaestor` (audit) and
  `quaesitor` (interview)**" sits under "System-level cautions" and does not survive.
  An ADR that decides a convention is lost too, because `DECISION` is not a rule-bearing
  class. Both are exactly what `naming-cite` exists to recover, and both are worth
  re-checking after the model pass runs: if it returns them, the deterministic scanner
  could reasonably be widened.
* **A term defined but never used.** `tabularium` is glossed in the pantheon and appears
  nowhere in the code as a module, command or table, so it is not in the glossary at
  all. The mirror of the traceability report — *vocabulary the documentation defines
  that the program does not use* — is one query away and is probably a real finding
  about drift. Not built.
* **`docs/contributing/conventions/naming.md` classifies as `NAMING_STANDARD`** and is
  not one: it is titled "Naming standards (imported, not prescribed)" and describes a
  feature of Mensores itself. Harmless today, because it now yields nothing, but it is
  the case that will break first if the Form-lane admission rules are loosened.
* **`docs.db` re-reads the whole corpus when the *vocabulary* list in `prose.yaml`
  changes**, because that file is inside the extraction fingerprint. Correct but
  conservative; splitting resolver config from extraction config would fix it and has
  not been worth 18 seconds yet.

### Built 2026-08-27: the traceability report

`12-traceability.md`, written every run. Governance ids normalised for separator and
zero-padding, joined across `annotations` and `doc_annotations` via `ATTACH`. No model.

**Seven bands, not two lists.** An id is not traced or untraced; it has a standing, set
by whether any document is *about* it — names it in a title or a top-two-level heading
— and whether the code cites it. Traced (298) · thinly traced (190) · undocumented work
(29) · likely landed (94) · possibly landed (45) · no trace in code (31) · passing
reference (748). Every band states what would make a placement in it wrong, and every id
is listed with the evidence that placed it, so a reader can move it.

**"Planned and never built" is not observable, and the page says so.** A plan can land
and never be cited in a comment; the absence looks identical. What *is* observable is
whether the code symbols a plan's document names actually exist — and that signal needed
hard filtering, because rule 5 applies to it exactly. Only symbols unique in the program
count (3,378 of 3,757 names), Python builtins are excluded on top (`ADR-59`'s entire
claim to having landed was the word `list`), and the surviving names are printed as the
whole of the evidence. Population is counted over identities, not rows: 570 names sit in
both `structures` and `classes`, and summing rows would have disqualified exactly the
distinctive type names a plan is most likely to cite.

**Three extractor recall gaps, one defect.** See rule 15 in `CLAUDE.md`. Headings, table
rows and the continuation lines of wrapped bullets were each consumed by a branch that
mined what it wanted and passed nothing on. `ADR-0057` is named in `.groma/ROADMAP.md`
and `Plan 44-01` in `ADR-0045`; both were reported as built-without-a-plan until fixed.
Undocumented work fell 59 → 29 and traceability rose 89% → 93%. `DOC_SCHEMA_VERSION`
2 → 5 across the three, because the fingerprint covers prose YAML and not extractor code
— rule 12's gap, worth closing properly.

**Counting.** 574 annotation rows are one marker caught by two detectors (`ISS-014`
matches ISSUE and TICKET both). Deduplicated on exactly the triple the shipped query
selects, so the printed count and the query beside it cannot disagree — rule 13, now
asserted by a test across the `ATTACH`.

**`dunneflow query --docs`** attaches the document store as `docs`, which is what makes
a cross-store claim reproducible at all.

Still open on this half:

* ~~**An id stated only in frontmatter or a filename is invisible.**~~ Done, as a
  `document_identity` rule in `detectors/annotations.yaml` — a config edit, not a code
  change. Every id it composes is marked `INFERRED` and is never merged with one read
  as written: the report has a "What was read, and what was inferred" section, marks
  composed evidence *(inferred)* wherever it appears, and lists whole the 33 ids whose
  entire documentary standing rests on the convention. Undocumented work 29 → 14, and
  code-to-docs traceability 93% → 97%.

  Two things this cost, both worth keeping. The corpus writes `plan:` two ways —
  `plan: "1"` and `plan: "06-02"` — and one pattern across both parts read `06-02` as
  `06` and composed `Plan 06-06`, an id that exists nowhere. Patterns are now
  positional, one per part. And `annotations.yaml` was not in the document store's
  fingerprint, so editing it left every document cached and answering the old rule —
  rule 12 wearing the other corpus as a disguise. It is in `doc_rules_fingerprint()`
  now.
* ~~**The mirror query.**~~ Done. Tom's instinct was right and the reason was worse
  than suspected: the `.db` suffix was not defeating a term matcher, there was no
  filename surface at all. `tabularium.db` is the most-named thing in Mensores and every
  one of its 155 named files was invisible. Doubting the tool first turned a one-query
  report into a new fact type.
* **The band boundary at three symbols** is a threshold, printed so it can be argued
  with, and not yet argued with against a second corpus.

### Built 2026-08-27: named artefacts, and the mirror query

`13-mirror.md` and `dunneflow mirror`, written every run. The traceability report's
mirror: **vocabulary the documentation defines, and what the code does with it.** No
model.

**The premise was wrong, and checking it first is what made the feature.** `tabularium`
was recorded as probable drift. It is not drift and the `.db` suffix was not defeating a
term matcher -- there was no filename surface at all. `tabularium.db` is the most-named
thing in Mensores, 52 references across 25 files, and it was invisible because the path
is assembled: `root / ".mensores" / "tabularium.db"` is not a module, not a table and
not a boundary target, because only the parts are literals. 155 such names in that
source and DunneFlow recorded none. Tom's generalisation was the right one -- databases,
scripts and programs are all named with defined words, and the extension is the tell.

So `schema.Artefact` came first: name, stem, extension, kind, and one row per reference
site so "how often, and by whom" is answerable. `SCHEMA_VERSION` 2 -> 3. Admission is an
extension list in `detectors/python.yaml`, which is the whole precision defence (rule 5):
without it `1.2.3`, `utf-8` and `mensores.cli` all read as named files. `.org` was
removed from that list on evidence -- the only thing it ever matched was
`host="freetsa.org"`. 350 references to 155 names on Mensores, and `tabularium` moves
from Absent to **Named**.

**Four bands, not two lists**, the same register as the traceability report. Named (51:
a package, class, table, way in or named file answers to it) · Borne (6: a routine,
param or field carries it) · Spoken (25: only comments and docstrings say it) · Absent
(37). Each states what would make a placement in it wrong. Matching is on identity, not
containment -- `Gate` does not match `aggregate` -- but compounds are split into the
words a person joined, so `disceptator_handle` carries `disceptator` exactly as
`bootstrap-config.json` carries `config`.

**The admission rule is the report.** Run forwards, the join to code filtered the
definition extractor's over-reach for free: a heading matches no code and is never seen.
Run backwards there is no filter, and 94 of Mensores' 245 definitions are not words --
38 code-shaped, 23 test names, 19 numbered headings, 14 sentences. Reporting them as
vocabulary Mensores ignores would be a finding about DunneFlow in a finding's uniform.
They are set aside **in the report, not at ingest**, by a rule stated on the page,
counted, and listed whole: the glossary and naming lanes are verified as they stand, and
tightening the extractor is a separate change with its own before-and-after. This
section is where the evidence for making it accumulates.

Ground truth reproduced: four executables at 1,366 / 421 / 265 / 111 reach; the research
paper still yields zero naming rules. 141 tests, mypy and ruff clean, `check` exits 0.
The mirror costs 0.37s.

### Two blind spots found while verifying the Absent band, neither fixed

Sampling Absent against real source -- the rule under "Anomalies" -- put four terms in it
that Mensores does use. Both causes are in DunneFlow, both are out of the mirror's scope,
and both change numbers in already-verified reports, so they are recorded rather than
quietly fixed. The Absent band's blind spot names them on the page, so it never asserts
drift where the tool is blind.

1. **A comment outside every function is not recorded at all.** Comments are collected
   per function; the `<module>` routine is created lazily and never receives any. On
   Mensores that is **9,887 of 18,208 comment tokens, 54%**, and 99 of 465 files with
   comments have none stored -- the `*_extras_schemas.py` modules, which are almost
   entirely module-level commentary, lose everything. Measured with `tokenize` rather
   than by grepping for `#`, because a `#` inside a prompt string is not a comment and
   the first count was inflated by them.

   The cost is not readability, it is governance: those comments carry **2,270
   annotations across 438 distinct ids**, of which **76 appear nowhere else in the graph
   and 75 of those are documented in the corpus**. They are real, traceable, and
   currently invisible. This is the layer CLAUDE.md says the tool exists to show, so it
   is probably the next thing to fix -- and it will move `06-governance.md` and every
   band in `12-traceability.md`, including the 97% headline.

2. **A module-level constant is not a recorded name.** `visit_Assign` catches only CLI
   app objects; class-level assignments become `Field_` and module-level ones become
   nothing. `JTBD_OPENERS` is declared in `_prompts.py` and read six times, and reads as
   Absent. A constant is a name a person chose, which is the same argument that made
   artefacts a fact type.

Also seen and left alone: `TechDebt` is a Neo4j node label inside a Cypher string, so it
is a name in a query language DunneFlow does not parse. Correctly Absent, honestly
reported.

### Built 2026-08-27: the comment gap, closed

Recorded as the next thing to do while building the mirror, and done. **Every comment in
every analysed file now reaches the store: 18,208 of 18,208, verified against `tokenize`
rather than against a grep for `#`.** Before, 8,549 were claimed and 9,659 -- 53% -- were
not.

**The mechanism.** Comments were collected per function: the block above a definition,
and everything inside its line span. The synthetic `<module>` routine is created on
demand by `_owner()` and was never handed any, so a comment outside every function was
simply dropped. Whole files lost everything they had -- the `*_extras_schemas.py`
modules are almost entirely module-level commentary. `claim_orphan_comments()` runs once
after the walk, so "claimed" means claimed by anybody: a comment leading a nested
definition is legitimately owned by both the inner and enclosing routine (187 of them)
and is not duplicated. `SCHEMA_VERSION` 3 -> 4, because extractor code is not in the
detector fingerprint -- rule 12's known gap, still worth closing properly.

Class bodies count as module scope. That is not a compromise: a class body runs at
import, and `_owner()` already assigns boundaries, calls and SQL found there to the same
routine. Anywhere else would have invented a second ownership model for one fact type.

**What it was worth**, all of it in the governance layer:

| | Before | After |
|---|---:|---:|
| Comments stored | 8,736 | 18,384 |
| Annotations | 4,713 | 6,944 |
| Distinct governance ids in code | 520 | 596 |
| Ids cited in code (traceability) | 517 | 593 |
| Traced -- both ends meet | 424 | **471** |
| Thinly traced | 79 | 107 |
| Likely landed, never annotated | 157 | **116** |
| Planned without landing | 258 | **211** |
| Marker kinds found | 7 | 8 (`DECISION` appeared) |

The direction is what matters: 47 plans moved *out* of "a document is about it but no
comment cites it" and into "the code says it landed". That band was over-reporting
speculation, and the evidence to settle it was sitting in comments nobody read.
Code-to-docs traceability held at 97% across a 15% larger population, so the new ids are
as traceable as the old. Anomalies went 93 -> 94 suspect; the one addition is a real
`LOST_EDGE` in newly-visible code, sitting beside the identical finding for its sibling
stage.

**One more defect, found by refusing to accept 30.** After the fix, 30 comments were
still missing. They were in three files the walk never read: `is_test_path` matched
`test_` as a **substring**, so `_test_stage.py` -- the real Test stage of the Groma
pipeline, Plan 30-02 -- along with `_test_extras_schemas.py` and
`_test_acceptance_extras_schemas.py` were dropped from the map entirely, routines,
boundaries and all. Rule 5 in a place nobody had looked. A marker must sit at an edge of
the name; a module *about* testing is not a test. 623 files -> 626, and the missing
count is now zero.

**Still open on this half.** A module-level constant is still not a recorded name --
`JTBD_OPENERS` is declared and read six times and reaches only Spoken, on a comment.
Same shape of gap as named artefacts, much smaller, and the mirror's Absent band names
it as a live blind spot.

### Built 2026-08-27: module-level constants, and the type aliases hiding in them

The last of the three blind spots the mirror's Absent band named. `14-constants.md`,
written every run: **2,618 named values and 86 type aliases**, none of them previously
recorded. `SCHEMA_VERSION` 4 -> 5.

**The gap.** `visit_Assign` caught only CLI app objects, `_class_fields` caught only
class bodies, and module level produced nothing at all -- so `JTBD_OPENERS` was declared
in `_prompts.py`, read six times, and absent from the map. Module level is taken from
**position**, not from a scope stack: it means *runs at import*, so a constant inside a
module-level `try` or `if TYPE_CHECKING` counts (13 of them) and one inside a function
does not. That is the same boundary the module scope already uses for comments and
boundaries, which is the argument for it.

**What the page is for.** A constant is configuration a person wrote down and named: the
model to call, the token ceiling, the directory to write into, the actual system prompts
the program sends to an LLM. 1,030 of the 2,618 carry a comment saying *why* they are
that value, and the comment leads -- a named value without its reason is a number. 1,689
are `Final`. Values are printed whole (rule 8): a ceiling cut to eighty characters is no
longer the ceiling, and a reader who has to open the source for the number they came for
was not helped.

**86 type aliases were hiding among them, and `StructureKind.TYPE_ALIAS` had existed
from the start with nothing ever producing one.** `QueueState = Literal["pending",
"adjudicating", "emitted", "rejected", "skipped"]` is an enumerated vocabulary declared
without the word `enum`; 67 of the 86 are `Literal`. They are `DataStructure`s, so
`04-data.md` renders them for free -- as *members*, after the first attempt put them in a
Field / Type / Default / Note table with three columns of em-dashes, which was found by
looking rather than by testing.

The admission rule is a constructor list in `detectors/python.yaml`, exactly as the
artefact extension list is, because `X = SOME_DICT["key"]` is also a Subscript. A bare
`X = Y` is deliberately **not** admitted -- it cannot be told from `DEFAULT =
OTHER_DEFAULT` without resolving `Y`, and it is recorded as a constant instead, which is
true either way. The rule ignores case, which turned out to matter: it found three
`_TOKEN_CLASS = Literal[...]` aliases that a CapWords-based measurement had missed.

**In the mirror.** `constant` is now a naming surface, and `JTBD_OPENERS` moved from
Spoken to **Named**. Named 51 -> 57, Absent 33 -> 32. The Absent band's blind spot is
down to one item, honestly stated: only Python is extracted.

**One matching change came with it, measured before it shipped.** `TOOL_STATUS_RAN`
carries `tool status`, and whole-name-plus-single-words missed it: a term matching the
*front* of a compound matched nothing. Names are now indexed under every contiguous
word-run. Simulated first: it moves exactly one term on its own evidence and six in
total, every one verified against source, and no false placement. Splitting a name
someone wrote is still identity and not containment -- `aggregate` yields one key and
never `gate` -- so rule 5 holds, and a test asserts it.

**Still open.** The Absent band now has one blind spot, not three: only Python is
extracted, so a word living in a shell script, a template, a front end or a sibling
program is absent from this graph and present in the product. That is a language
question, not a defect.

### Attestation: promoting an inference, and why it is not canon (2026-08-27)

Agreed in principle, recorded rather than built. It waits behind temporal layers,
because it needs the same storage they do.

**Where it comes from.** DunneWrite's note ingest asks the fiction author to certify
whether an inferred fact is true; if so it is promoted to canon, otherwise it stays
marked as the model's guess. The question was whether that model transfers to source
code, "since it is or isn't real, not the same as fiction".

**It transfers, but not the vocabulary.** In fiction the author *is* the ground truth:
certification does not discover a fact, it creates one, which is why "canon" is the
right word there. In code there is a fact of the matter independent of any reader --
`Plan 68-03` either did or did not govern that file -- so a person confirming it is not
authoring, they are **witnessing**. Calling that canon would quietly borrow the fiction
author's authority for someone who does not have it.

What makes the mechanism worth having anyway is not whether truth exists but **who can
see it**. DunneFlow's `Plan 68-03` inference is unfalsifiable *by DunneFlow*: the
evidence lives in a convention someone holds in their head, or in a tracker outside
`--docs`. A person who knows the project can falsify it in seconds. Their judgement adds
information the tool cannot derive, which is exactly the condition that makes
certification worth building rather than decorative.

**Three changes from the DunneWrite model.**

1. **An attestation is a claim, so it carries provenance.** Rule 13 applies to people
   too. The tier is *attested*, beside quoted and measured -- who, when, and on what
   basis, because "I wrote this plan" and "it looks right to me" are different evidence.
   A quoted definition proves itself with a line; an attestation proves itself with a
   person, and must name them.

2. **An attestation goes stale; canon does not.** Fiction canon is decided and stays
   decided. Code moves. An attestation must be keyed to the *evidence* it was made
   about, so that renaming the file, changing the convention, or the plan document
   finally appearing invalidates it rather than silently carrying an old judgement
   forward. That is content-addressing again, and it is the same storage question
   temporal layers answer -- which is the whole reason this waits for them. A second
   store keyed by revision would be the same mistake the project profile records.

3. **The third pile is the valuable one.** The anomaly worklist already has the right
   shape: *the blind spot applies* / *real and acknowledged* / *this is a DunneFlow
   defect*. Attestation must feed the same loop rather than growing a parallel system.
   Rejecting `Plan 06-06` is not a fact about one id -- it is a fact about the
   `document_identity` rule in `detectors/annotations.yaml` that composed it. An
   inference rejected repeatedly means the convention is wrong, and the rule is the
   thing to fix. Certification that only decorates individual rows throws away its own
   best signal.

**One invariant.** Promotion must never overwrite the inference. Record "inferred, then
attested by <person> on <date>" with both visible. In fiction the guess can be discarded
once canon exists; here, if the attestation turns out wrong, you need to see what it was
resting on.

**Scope when it is built.** Not only composed ids. Every INFERRED thing DunneFlow
reports is a candidate: `Confidence.INFERRED` call edges, the *likely landed* and
*possibly landed* traceability bands, and whatever `dunneflow infer` returns. One
mechanism, one worklist, one triage vocabulary.

### Next, in order

**1. ~~The documentation extractor.~~ ~~The glossary and naming-standard renderers.~~
Done — see above.**

**2. ~~The traceability report.~~ Done — see "Built 2026-08-27: the traceability report" above.**

**3. ~~The mirror query.~~ Done — see "Built 2026-08-27: named artefacts, and the
mirror query" above.** The premise was wrong and checking it first was the whole value:
`tabularium` is not drift, it is the most-named file in the program, and DunneFlow could
see no file a program names. `schema.Artefact` and `13-mirror.md` came out of it.

**3a. ~~The comment gap.~~ ~~Module-level constants.~~ Both done — see the two
sections above.** 53% of comments never reached the store and now all do, taking ids
cited in code from 517 to 593 and moving 47 plans out of the speculative bands.
Constants and type aliases followed, closing the last recoverable blind spot the mirror
named. What remains on that band is a language question, not a defect: only Python is
extracted.

**3b. ~~Close rule 12 properly.~~ Done — and it uncovered a worse one.** The extractor
is now in the cache key for both corpora: `code_extraction_inputs()` in
`detectors/__init__.py` and `doc_extraction_inputs()` in `detectors/prose.py` name the
files, and `fingerprint_files()` hashes them by package-relative path and content. The
two lists are deliberately disjoint apart from `annotations.yaml`, so a prose edit never
discards the code graph; a test asserts membership *and* the disjointness, because a
test that re-derived the list would agree with a wrong list. The `SCHEMA_VERSION` bump
is no longer load-bearing.

Changing the fingerprint is what exposed **rule 20**: every read command opened `Store`,
which discarded a stale graph unconditionally, so the first `dunneflow query` after the
change dropped all 4,734 mensores routines and answered `(no rows)` — a silent wrong
answer that consumed its own evidence. `Store` and `DocStore` now take
`writable=False`; a reader raises `StaleGraphError` naming the fix, and only `analyze`
may drop. Three tests cover it, including that a read-only open does not alter the file
at all. See rule 20 in `CLAUDE.md`.

Also fixed: the `cli:` summary line counted only commands attached to an app object, so
it read `0 apps, 0 commands` over DunneFlow's own eight-command CLI — argparse builds
its parser inside a function, so there is no module-level app to hang them from. **The
commands themselves were never lost**; only the counter was blind, which cost this
session its first finding. Both counters are now taken over the same population
(CLI-kind entrypoints, excluding console-script declarations) and the line reads
`116 commands (111 in a tree)` on mensores — the 5 unattached are exactly signator's
argparse subcommands.

**4. The one-time model pass — `dunneflow infer`.** Postures (Off / Documentation /
Documentation + identifiers / Everything / Local endpoint), stored per corpus; a file
manifest shown before anything leaves; two-step arm-then-confirm; `CITED` results
verified against the line they name and *reported* when they do not verify. Its worklist
already exists: `10-glossary.md` ends with the 191 terms nothing defines, and
`11-naming.md` says plainly that Mensores states no Form rule anywhere. The Form lane
needs no model at all — counting is what a database is for.

**5. The dashboard. Chunk 1 built 2026-08-27 — the 2.5D graph.** `dunneflow serve
output/<program>`: stdlib `http.server`, vanilla JS, deck.gl 9.3.10 vendored into
`web/vendor/`. No Node at build or runtime. **Astro 5 + Tailwind 4 was struck** — see
`CLAUDE.md`, dashboard preamble, for why.

The model is Tom's, from usdgraph, and it is the valuable part: a stack of 2D disks
"like ice rinks". Within a disk an ordinary graph; an edge leaving it puts a **shadow**
there, taking part in that disk's forces normally, with the real node on its own disk and
a **transposition** joining them across Z. Disks shuffle like cards. It is the answer to
density — usdgraph's own continuation prompt records the failure it fixes, an HR graph
"too dense to be useful" even filtered to ~700 employees. Decomposition, not filtering,
and nothing is discarded.

Disks: one per top-level package, plus one per boundary kind for external systems. On
Mensores that is 51 disks, largest 959, 9,719 real nodes plus 5,272 shadows = 14,991
drawn, 13,277 edges. Payload builds in ~30 ms and is sent columnar.

What real use corrected, all now in `CLAUDE.md` as dashboard rules 18–21: the plates must
not be drawn at all (the stack is an abstraction), edges only on demand for a selection
and only when still, the fit is a bounding *cylinder* at the tilt in force under an
orthographic projection, and a blank canvas must say why it is blank.

**Chunk 1's gate is met.** Measured on the M1 with Chrome's Metal renderer: **60 fps
median, 60 worst, no frames dropped** across the six-second orbit at 14,991 drawn nodes,
loading in 0.1 s. The plan's threshold was 55 median, so deck.gl stays and the three.js
fallback is not needed. 60 is the vsync ceiling, so that is a floor with unmeasured
headroom, not a capacity — the readout now says so rather than letting a ceiling read as
a score.

**Phase 2 built 2026-08-27.** The working session: selection is a set of picks (shift
adds, alt removes, esc clears), disks multi-select and drag-to-reorder with Z owned by the
client, per-disk colour, sort by size/name/kind/manual, dim-or-hide with the excluded
count always stated, collapsible panels, node size from dots to billboarded spheres,
search across every metadata field the payload carries, and settings persisted per program
and versioned with a reset that says what it cleared. Named artefacts became nodes on
their own plate (155, 329 edges) -- searching `tabularium` returned nothing and that was a
gap in the map, not the search. Edge width is driven by weight end to end, which is the
whole preparation for flow replay.

**The crossings, and what a shadow is for.** A shadow is a placement device only: it is
never drawn and never an edge endpoint. The model stores each crossing twice, once per
plate, each copy ending in a shadow -- that is what lets both plates lay out under the
same forces -- and for drawing the two halves are resolved back to their real ends and
kept once. The result spans Z as a single line, coloured walking from one plate's colour
to the other's, drawn when both ends are selected. Within-plate and crossing links are
counted separately. On Mensores: 8,969 links, of which 4,963 cross. See rule 23.

**Still open after phase 2:** two measurements need real hardware -- fps with spheres at
full size, and fps with a large multi-disk selection drawing thousands of edges. The
sphere threshold (2.2x) is set by judgment and should be set by the first of those. Layout
is still `structural` only; ForceAtlas2 in a worker, posted back and stored, is not built.
Node selection
is fiddly at overview zoom — the likely fix is a disk-focus mode that flies to a plate and
drops to top-down, which belongs to chunk 2. Layout is still `structural` only:
ForceAtlas2 in a worker, posted back and stored in a `layout` table, is not built.

Chunks 2–9 (shadows/shuffling UI, the three-pane shell, inspector, table and document
modes, anomaly worklist, glossary pages, exploration layer, settings) are unchanged.

**5a. Built 2026-08-27 (second session): the shell, the inspector, and the source
sidecar.** The graph stopped being the page and became a mode inside it.

*The shell.* Three panes over one shared selection -- navigator | centre | inspector --
as a CSS grid under a header carrying the program name, the mode toggle and a breadcrumb.
The centre is a toggle, never three destinations: graph, table and document all show
whatever is selected, so switching never costs the reader their place. Table and document
are **declared and explicitly unbuilt** rather than silently showing the graph, which is
the failure design rule 16 was written from.

Three things rode along because they were cheapest now and structural later:

- **Routing from a table.** The click handler ended `const tilt = act === 'top' ? 90 :
  act === 'tilt' ? 35 : state.viewState.rotationX` -- so *any* unrecognised `data-act`
  snapped the camera and looked entirely deliberate. `ACTIONS` and `MODES` are tables; an
  unknown action is a named error.
- **A startup self-check**, deriving its list from the DOM so markup and handlers cannot
  drift. Plus `tests/test_web_controls.py`, which asserts the same agreement in `pytest`
  -- a self-check nobody opens the page to see is one that has already failed. It runs
  both directions: a control with no handler, *and* a handler no control reaches.
- **The `px` to `rem` conversion**, design rule 3. The test caught three 2px borders
  written in the same session -- the confidence-shape markers, which are exactly the
  thing that must scale with everything else.

*The inspector.* `/api/node?id=`, flow-first in the settled order: IN (callers, and any
entrypoint registered on it) → OUT (with `external`, `at_boundary` and `ambiguous` all
distinguished) → TOUCHES (boundaries, SQL with direction, the full network record,
artefacts) → GOVERNANCE (annotations, then the comments placed against the line they
explain) → source. The signature is demoted into a params view. Every list states what it
is not showing and opens in place. All five node kinds answer -- routine, structure,
constant, boundary, artefact -- and each answers with what it actually has rather than
posing as a routine with fields missing.

*The source sidecar.* `output/<program>/source.db`, content-addressed on the
`content_hash` already in `files`, `--no-source` to skip it. On Mensores: 626 bodies,
7.8 MB of source in 2.6 MB. Driven by the hashes the graph just recorded rather than by a
second walk, so a re-analysis with nothing changed reads **zero** bytes of source --
confirmed in the same run that discarded the graph for an extractor change, which is
rule 25 demonstrated rather than asserted.

*Found while building, all fixed:*

- The orbit benchmark could never draw edges (rule 24) -- so one of the two outstanding
  measurements was not merely unmeasured but unmeasurable, and the readout printed an
  edge count for geometry it had not drawn.
- `ThreadingHTTPServer` plus one sqlite connection: a lock is not enough, because sqlite
  refuses a connection used off its creating thread whatever the caller does about
  ordering. Both stores take `shared=True` now, and the lock is what then makes it safe.
- Externals were drawn as INFERRED (rule 26).
- The Sphinx `#:` marker leaked into 1,698 comments and 323 constants (rule 27).

*The two fps measurements are taken.* Both at 60 median and 60 worst, nothing dropped:
spheres at full size (14×), and spheres at 14× with 4,253 edges drawn (2,199 within, 2,054
crossing, eight plates selected). **The sphere threshold is now set by evidence rather
than judgment** -- full size costs nothing measurable, so 2.2× is a look, not a budget.
The budget table in `CLAUDE.md` also had two stale figures: it claimed 14,991 drawn by
counting shadows, which stopped being drawn when rule 23 landed. It is 9,874.

*One defect found by taking the measurement.* The bench line reported `selGeom.count` and
omitted `interCount` -- 2,199 printed against 4,253 actually submitted. Rule 24 surviving
in the half of the line the first fix had not touched, which is worth noticing: fixing the
cause of a mis-stated measurement is not the same as fixing every place it was mis-stated.

*And one found by Tom looking at it.* `[hidden]` is a user-agent rule, and any author
`display` declaration beats it outright -- specificity is not involved. `.unbuilt {
display: grid }` therefore cancelled `hidden` on the table and document views; all three
views are absolutely positioned over one another, so the document panel painted on top of
the canvas. The graph was rendering at 60 fps underneath it the whole time, and the mode
buttons flipped `hidden` and `aria-selected` correctly while nothing on screen changed.

This is design rule 16 one layer below where every existing check was looking. `selfCheck()`
compares markup to handlers and passed; `test_web_controls.py` compares the same two files
and passed; reading `v.hidden` back agreed with itself and proved nothing. **The wiring was
right and the paint was wrong.** Two guards added: `verifyOneViewShowing()` asks
`offsetParent`, which is null only when something is genuinely not laid out, and a test
asserts the `[hidden]` override is still in the stylesheet, since it is one line any later
`display` rule can silently re-break.

The general lesson, and it is the one already written down as *look, don't only test*: this
session verified the DOM, the routing, the endpoints and all five node kinds, declared the
shell working, and never once took a screenshot. One screenshot would have shown it
immediately.

Also not done: `source.db` is written but the inspector's "open the whole file" is the
only route into it, and the graph does not yet offer a way to reach a node's source
without going through the inspector.

**5c. Built 2026-08-28: the ratified shell, reading from the store.** The dashboard was
built *first*, as a claude.ai artifact, and it is not a mockup -- it is a complete working
UI with Mensores' real numbers pinned into it. Measured: **832 lines** of token stylesheet,
**1,639 lines** of behaviour, **292 lines** of `const` arrays, and **zero `fetch` calls**.
The design and the interaction were done; only the data binding was missing.

*The artifact is the source of truth for the design* and is recorded under Still open
below, because it took a screenshot and a search to find it again.

What the port did: moved the stylesheet and behaviour into `web/static/` (vanilla already,
no framework, no build step), emptied every pinned array, and served them. `/api/cover`
answers in one request; `/api/anomalies` is separate because the findings are large and
most sessions read the counts without opening the list.

Live on Mensores: 626 files, 184,722 lines, 4,734 routines, analysed stamp, 14 ways in
ranked by reach, 9 boundary kinds each with its commonest target, 94 suspect and 12
informational findings with their blind spots. The line count is summed from `source.db`
-- the sidecar earning its keep the day after it was built -- and says nothing at all when
there is no sidecar rather than guessing from file sizes.

**Emptied and honest rather than emptied and blank:** glossary, naming and curiosities all
say they are not computed yet. "Nothing unusual here" and "nobody has looked yet" are
opposite claims, and an empty grid reads as the first one. `PROVENANCE` alone was 52 KB of
Mensores' glossary.

*Two defects found by looking, both invisible to anything that reads the DOM:*

- `viewInspector()` threw on a null specimen -- the prototype pinned one routine as its
  permanent subject and could never reach "nothing selected". The exception took the rest
  of `render()` with it, so the filter strip went on announcing **"showing 187 of 4,568
  routines"** over a view filtering nothing. An *announced* filter that is not happening is
  worse than a silent one, because the reader adjusts for a slice they are not being shown.
  Each section now renders inside its own boundary and says on the page when it cannot.
- The `[hidden]` override was lost with the old stylesheet. Carried forward, because the
  failure it prevents reports success everywhere.

*The guard this port exists for* is in `test_web_controls.py`: no per-program array may be
non-empty, and none may be `const` -- a `const` the loader cannot fill is an empty
dashboard with no symptom at all.

**Chunk 2, next: mount the graph inside the shell.**

The architecture question was settled by discussion and the answer is *not* what it looked
like. The graph does **not** need to be the parent and there is no iframe: WebGL has no
requirement to be the top-level document, deck.gl mounts into any div, and the only real
constraints are a sized container at init and a resize nudge on reveal -- both already hit
and fixed. An iframe would cut the single shared selection in half and turn "click a
routine in the text, see it in the graph" into a postMessage protocol, which is the one
interaction the whole design is built around.

So: the dashboard is the parent, the graph is a view inside it. `graph.js` is the engine,
renamed rather than removed; its shell concerns need separating from its rendering.

**The graph follows the theme.** Decided against my recommendation, on evidence: Tom has
talked to people who genuinely prefer a light graph. Design rule 2 settles it -- build
both, make it a Setting, count usage locally, retire the loser on evidence. The work is
real: `KIND_COLOR`, the golden-angle per-disk hues, edge, dim and plate colours are all
chosen against near-black, and `shading.js` assumes a dark background for its sphere
highlight. A light stack needs its own palette derivation, not the same numbers on a pale
background.

**Distribution: a single binary is the product.** Not for convenience -- because DunneFlow
reads private source and `source.db` contains it, so a hosted model sends an unfamiliar
codebase to a server, and dashboard rule 14 says egress is scoped and never a switch.
PyInstaller/py2app, double-click, opens at localhost, full SQLite underneath, no Node.
`pywebview` would give a real app window using the OS webview if wanted, still no Node.

The static sqlite-wasm build is **not** scrapped, it is reclassified: it is the *export*
format for handing one map to a colleague, which is what the handoff always called it
("mailable"). It cannot be double-clicked from disk either -- browsers block `file://`
range requests -- so it needs a host to work at all. Keeping every dashboard query as SQL
text in `queries.py` is what keeps that path open.

Signing is what decides the non-technical experience: unsigned, macOS says the developer
cannot be verified and the user stops. **Tom has an Apple Developer account already**, so
macOS is available whenever wanted. Windows is deferred to the last minute.

**5d. Built 2026-08-28: chunk 2, one application.** The graph and the dashboard were two
complete applications that had never been joined -- each with its own state, settings, mode
toggle, search, inspector, self-check and `boot()`. `index.html` loaded only one of them, so
deck.gl was never fetched, there were no canvases on the page, and the 2.5D stack was
unreachable while every control on the page worked perfectly.

*What was done.* `graph.js` is the engine and nothing else: it draws inside the element it
is handed, and counts, fps, selection, diagnostics and errors leave as events. The canvas
lives in a mount `render()` never touches, since `render()` fills the centre pane with
innerHTML on every keystroke. `settings.js` became the whole application's store at version
2 -- before this the graph persisted its arrangement and the shell persisted nothing, so a
theme chosen deliberately was gone on reload while a disk order nobody remembered setting
survived. One inspector: the ratified layout fed by `/api/node`; `inspector.js` and
`style.css` deleted, both already orphaned. The package overview is real -- `web/packages.py`,
`/api/packages` -- computed rather than hand-placed, and it is a *layout* inside graph mode
beside the stack, never a fourth mode. The graph follows the theme, reading its palette from
`tokens.css` so there is one place a colour is written down.

*The find that matters: the sphere shading has never run.* Three silent no-ops, stacked.
Rule 22 records the first -- an inject hook deck.gl did not recognise. Behind it were a GLSL
local colliding with one of deck.gl's own, and a shader that was never reassembled, because
deck.gl resolves an extension's shader once per extension *class* and matches layers by id
(and the layer first renders below the sphere threshold, with no extension at all). None of
the three is an error: each compiles, each draws, each skips the effect. **The two "spheres"
rows in the budget table are therefore withdrawn** -- they measured flat discs while printing
the word spheres, which is rule 24 -- along with the claim that the 2.2x threshold was set by
evidence. They want retaking now the fragment work actually runs.

*Three pinned Mensores values left the shell*, invisible to the guard written to catch
exactly them: it walked the top-level arrays and never looked inside `state`, where `usage`
was seeded with invented counts and two routine paths were hard-coded.

*Found by looking, every one of them:* a backtick inside an HTML comment closing a template
literal (twice -- the page came up empty and every Python test passed); the counts event
rebuilding the HUD and so destroying a slider mid-drag; `.tb-select` reused on a white panel,
where it is white-on-white by design; long qualified names breaking mid-token, the `do_PO /
ST` defect in a new pane; and all three shading no-ops.

*Still open from this chunk.*

- **The fps rows want retaking** on a visible, focused window at full size, reproducing the
  eight-plate selection named in `CLAUDE.md` or it is a different measurement under the same
  label. It could not be done in this session: the automation tab is not visible, and a
  hidden tab is given **no** animation frames at all. The benchmark now refuses rather than
  hanging, and says why.
- `47` packages is the truth and the ratified design's `24` is stale -- 42 have eight or more
  routines, 5 have fewer (11 routines, folded into `<small>`), and 42 + `<small>` + 9 boundary
  kinds is exactly the 52 disks. That question in *Still open* is answered.
- Document mode's narrative view, the exploration layer, and the usage report screen are
  still as they were.

*Added after the chunk, on Tom's correction: edges stay up while the camera turns.*
Hiding them during motion was a speed measure borrowed from slower renderers and this one
does not need it -- the geometry is uploaded once as flat typed arrays, so a turning camera
re-uploads nothing and the links cost the same moving as they do still. It also worked
against the picture: **a rotation is how connections between plates resolve into depth
rather than a flat tangle**, so stripping the edges during one hid exactly what the reader
turned the view to see. Now a Setting, *Show edges while moving*, default on; off kept for a
slower machine or a very large selection. Design rule 19's "…and only once the camera has
stopped" is struck; its **on demand** half is untouched and is the half that carries the
rule. The benchmark still forces edges on regardless, because a run must measure the frame
it names.

### Do not re-open: why the nodes are flat circles

Recorded because it looks like a shortcut and is not, and because a future session reading
"fake spheres" in the code could easily try to "fix" it into real geometry.

**Billboarded circles are the technique, not an approximation of one.** They came out of
Tom's research on another product, where drawing spheres as circles that always face the
screen sped up rendering enough to put *massive* numbers of nodes on screen at full speed.
The custom lighting is what simulates the sphere, and it has to hold up while the reader
rotates the model in space -- which is the whole point, since rotation is how relationships
between nodes are read. A fixed light in view space is therefore correct: the highlight
stays put as the view turns.

The corollary is the one that cost this session: **the lighting is load-bearing, not
decoration.** Without it the technique renders flat discs, and a flat disc read at a glance
is a coin, not a ball. It is worth checking by eye after any change near the layer.

### The sphere shading: three silent no-ops, stacked

Worth its own heading because each one alone is subtle and all three have the same shape --
*it compiles, it draws, the effect never happens* -- and because scripted checks caught none
of them.

1. **The inject hook was named wrong** (`fragmentColor:DECKGL_FILTER_COLOR` rather than
   `fs:…`). Already recorded as rule 22. An unrecognised hook is not an error.
2. **A GLSL name collision.** The block is injected into deck.gl's own fragment shader, so
   `vec3 normal = …` landed in a scope that already had one. Every local is now prefixed
   `df`.
3. **The shader was never reassembled.** deck.gl resolves an extension's shader once per
   extension *class*, so a second instance carrying different values silently reuses the
   first assembly. `shading.js` now builds **one class per lighting**, cached by it -- two
   for the life of a page. Established by experiment: an identical body in a freshly
   declared class shades, and in a shared class it does not.

Related and separate: a layer's shader is built once with its model, and deck.gl matches an
incoming layer to the drawn one **by id**. The nodes layer first renders below the sphere
threshold with no extension at all, so it kept its plain shader forever. The id now carries
the shading signature.

All three were found by looking closely at one node. Nothing else has ever detected any of
them.

### A check may only claim what its instrument can prove

The runtime self-check reported `clear` as "reached by no control" while sitting on the
Settings view. True of that moment, false about the product: half these controls are
conditional -- `clear` appears only with a selection, and the whole HUD only in graph mode.

**The DOM can prove a control has no action. It cannot prove an action has no control.**
That second direction moved to `test_web_controls.py`, which reads every `data-gact` in the
source whether it is on screen or not. A check that cries wolf is a check nobody reads, and
this project's checks are load-bearing.

Same shape as rule 24 (a measurement must measure the thing it names) and as rule 13 (a
claim's query must return what is printed beside it), arriving in a third costume.

### Guards added this session, and the defect each was written from

| Guard | Written from |
|---|---|
| `test_the_javascript_parses` | a backtick in an HTML comment closed a template literal; the page came up empty and every Python test passed |
| `test_no_backtick_hides_in_an_html_comment` | the same defect, twice in one day; needs no JavaScript engine, so it runs everywhere |
| `test_the_page_loads_what_it_needs` | the shell replaced `index.html` and stopped loading the engine entirely |
| `test_the_graph_has_somewhere_to_live` | `render()` would destroy the canvas if it ever wrote to the viewport again |
| `test_every_graph_action_is_reachable_and_every_control_acts` | design rule 16, both directions, from the source |
| `test_no_program_data_is_pinned_inside_state` | three pinned Mensores values the existing guard could not see |
| `test_a_reset_reports_every_setting_it_clears` | a reset that walked its label table under-reported itself |

**5e. Built 2026-08-28: the layout, the navigator, and the two rows finally taken.**

Started as "clear the owed fps rows" and turned into three defects, because the rows could
not be taken honestly until the canvas was the size a reader actually has.

*What Tom saw.* A default panel stuck at the bottom left reading "Nothing selected", text
scrolling off the bottom, a strip along the bottom right, and picking something from
**Ways in** no longer clearing it. Three separate causes, none of them what either of us
guessed first -- my own first diagnosis, DevTools docked to the window, was wrong, and so
was the second, `min-height: 40rem`, which turned out to be a consequence rather than a
cause.

*The chain.* `@media (max-width: 68rem)` meant **1632px** rather than 1088px, because a
relative unit in a media query resolves against the browser's default font size -- 24px on
that machine -- and ignores the `:root` this stylesheet pins. So a 1454px window got the
narrow layout. The narrow layout's `.inspector { display: none }` then lost to
`.inspector { display: flex }` declared 350 lines later, since a media query contributes no
specificity and equal specificity goes to source order -- so the pane rendered into a grid
declaring two columns and wrapped onto row 2. Two rows of panes needed 640px, `min-height:
40rem` held the app there against a 500px viewport, and the document scrolled. Rules 28 and
29.

Measured rather than argued: the scale slider took the navigator from 192px to 288px and
moved the breakpoints not one pixel. **The rem in those media queries was never part of the
scaling system** -- it looked like a member of the family and was not one. Five queries were
written that way; all five are px now, and every real dimension stays rem. The rule-3 test
grew an exemption for `@media` lines and a second test asserting the inverse over exactly
those lines, so the pair cannot drift.

Its companion, in the same layout: a grid item defaults to `min-height: auto` and refuses to
shrink below its content, so the navigator's 1,151px held the row open at 700px inside a
446px box. `minmax(0, 1fr)` on the row, `min-height: 0` on the children.

*The one that mattered.* All four navigator routes that set a subject -- `ep`, `pkg`, `b`,
`t` -- were `() => { state.view = state.mode; ensureGraph(); }`. They switched mode and
selected nothing, so **forty rows all did the same thing** and the inspector went on
truthfully reporting "Nothing selected". No identity had ever reached the DOM: the item
objects were `{nav, label, n}`. It never tripped the no-route check, because the route
existed. Rule 30.

The four turned out not to be one shape, which is what made the fix right rather than
plausible. A package and a boundary kind are plates and select as themselves. A way in
resolves to routines, and `ways_in()` had been computing those roots all along while
`cover.py` dropped them -- `mensores` has 104, `mensores-mcp` 38. A table is **neither**:
`audit_events` is not a node at all, so selecting a table means selecting the code that
reads and writes it, which is a new `TABLE_ROUTINES` query and `/api/table`. `queries.py`
had already written the reason down before anything needed it -- *inventing an id to make a
row clickable would be a link to nothing*.

Selection is now held in **id space** in the shell and resolved to drawn indices only when
the engine is mounted, so picking a way in works while the centre pane is showing a table or
a document, and the stack adopts it when it next appears. What cannot be drawn is counted
and stated on the HUD (design rule 1) rather than going quietly missing.

*The rows, taken.* Both at **60 median, nothing dropped** -- 59.7 worst without edges, 59.9
worst with 4,253 -- on a **2652×1537** canvas framed with **snap to fit**, shading confirmed
by eye on a single node before either was recorded. Both facts are now in the table, because
their absence is what made the first pair impossible to reproduce: an early attempt this
session ran at 4.08M canvas pixels with the stack sitting small inside them, which is a
bigger number measuring the same little picture. The 2.2× sphere threshold stays **a
judgment** -- these rows say the shading is affordable, not where a reader wants a disc to
become a ball.

*Also learned.* `outerWidth/Height` are device pixels while `inner*` are CSS pixels, which
is what made a normal 88px of browser chrome read as 677px and sent the first diagnosis to a
docked panel that did not exist.

*Not done, and named:* hiding the inspector on a narrow window is a silent filter, which
design rule 1 says it may not be -- it should say what it removed. The legend panel covers
most of the graph at moderate widths. And at 14× the nodes fuse into a solid mass and
occlude their own edges, which is the case for independent X and Y spread (5b) rather than
against the measurement.

**5f. Built 2026-08-28: three spread axes, and collapsing the gaps.**

Tom's, from looking at the 14x benchmark frame and seeing a solid cylinder: at large node
sizes the spheres fuse, and no amount of Z spacing helps because the crowding is *within*
a plate.

*Three axes.* `applyLayout()` is the single place positions are computed, which is what
made this cheap -- it already scaled Z by one `spread` and never touched X or Y, which
arrived from the server's phyllotaxis. Now all three, independent. Every scale is computed
from an unscaled **base copy** of the payload positions rather than applied in place, so
the operation is idempotent and a slider dragged back to 1 comes home -- verified: fit zoom
returns to exactly -2.63. There is deliberately **no linked slider**: under an orthographic
projection uniform scaling of all three axes *is* zoom, so it would be a second mouse
wheel. Design rule 22.

*Hide and collapse, separately.* Hiding already existed as `filterMode` and stops
unselected plates drawing; what it could not do is close the gap they leave, so a selection
of eight plates out of fifty-two read as eight plates scattered down a tower of empty slots.
Collapsing repacks the stack over the plates still in play. The two are independent because
"show me these eight, packed" needs both and is unreachable if they are one control.
Design rule 23.

Two consequences that had to be got right rather than assumed. Which plates are unused is a
function of the *selection*, so it is recomputed in `afterSelectionChange` and not only when
the control moves -- otherwise the stack keeps the shape of the previous selection while
confidently showing the current one. And a collapsed plate's nodes are parked on the slot
their neighbour takes rather than left at the old height, because they are still crossing
endpoints and one left behind drags an edge to a place nothing is.

Measured on Mensores: eight plates selected collapses 44 of 52, three plates collapses 49,
and the count line says so (design rule 1) -- a shorter stack and a smaller program are
indistinguishable by looking. At 8x with X and Y at 3.5 the spheres are individually
separated and readable, 3,578 nodes at 60 fps, which is the state the whole change exists
for.

*Settings went to version 3*, so the single `spread` is discarded rather than silently
reinterpreted as one of three.

*Two guards, both verified to fail on their own defect.* The spread sliders are driven by
one table rather than three copies of a branch, so the failure mode is a slider with no
entry in it: it renders, it drags, its readout never updates, nothing moves. The test walks
both directions and follows each option into `graph.js` to check the engine both reads it
and re-lays out on it -- a slider wired to an option the engine ignores is the same silent
no-op one layer down. These are `id` controls rather than `data-` ones, which is exactly the
half `selfCheck()` and `test_every_static_control_is_listened_for` cannot see.

*Still open from this chunk.* Per-plate sphere scaling and stack orientation -- laying the
column on its side -- are the two Tom asked for that are not built. Orientation is the
structural one: deck.gl's `OrbitView` orbits a fixed axis and offers no camera roll, so
laying the stack down means making the stack axis a different world axis, which changes what
`fit`, `top-down` and `tilt` each mean and changes the silhouette `fitView` computes
(design rule 20 frames a bounding cylinder, and its axis moves). It wants its own step.

Also seen and not fixed: **the legend covers most of the graph** at ordinary widths -- it is
an opaque panel over the canvas, and at 1279px it left the stack a corner to draw in. It
collapses to a "Plates" button, but it opens by default over the thing it indexes.

**5g. Built 2026-08-28: the panes fold, and a setting that had never done anything.**

Tom's, on seeing the inspector holding 22rem to say "Nothing selected": rail it when there
is nothing to show, pop it out when there is. He added that the panes used to be
collapsible and that it should still be in the code somewhere.

*It was, and it was dead.* `settings.js` carried `panels: { hud, disks, settings, inspector }`
from the first day -- persisted per program, versioned, and named in the reset dialog as
"panel layout" -- and **nothing anywhere read it**. Not a dead control: a dead *setting*,
which a reset would have cheerfully reported clearing. The pre-merge graph had collapsible
panels and the merge kept the switch while dropping the implementation, exactly as it kept
two inspectors and two boot paths. Design rule 16 with no control to look at.

*What was built.* Both side panes fold to a 1.75rem rail carrying a rotated label -- a pane
that simply vanishes is a silent filter, and the rail is what makes the layout legibly a
choice. The **grid tracks** carry the state, not the panes, because collapsing a pane
without its column leaves a hole the width of the pane that is no longer there. The
inspector rails itself while nothing is selected and returns when something is; an explicit
fold outranks that, and clicking the rail with nothing selected suspends the auto rule --
without which the pane reopens and instantly re-collapses, which reads as a broken button.
Verified through all six transitions plus that edge case.

*Found while building, and worth keeping.* Adding a fold button to the navigator moved it a
third of the way down the pane. `render()` reorders Ways in / Explore with
`insertBefore(first, parentNode.firstElementChild)` -- which assumed the first element child
*was* a group, and swept the chosen one in front of the new chrome. It targets the first
`.nav-group` now. **An ordering rule that names a position rather than an identity breaks
the moment anything is added beside it**, which is the same shape as rule 15 and rule 18
and cost nothing to fix only because a screenshot showed it immediately.

The panebar is `position: sticky` for a plainer reason: the navigator scrolls 1,151px of
its own content, and a collapse control that scrolls away is one the reader cannot reach
from the bottom of the list.

*The guard is the valuable part.* A test now reads every key out of `DEFAULTS` and demands
each appear as a **property access** in the shell or the engine. Searching for the bare name
is not enough and the first draft of the test proved it: every key is also a plain string in
the list of things to persist, so the weak version passed on a setting that is faithfully
saved, restored, and never once acted upon. Verified against both shapes -- a brand-new dead
key, and `panels` unwired while left in the persist list.

*Still owed from that conversation:* per-plate sphere scaling, and stack orientation. Also
still true: **the legend covers a third of the graph** when open. It has its own collapse
("Plates"), so the pieces are all there now -- what is missing is a decision about what it
should do by default, and a horizontal stack will want that width.

**5h. Built 2026-08-28: the legend becomes a pane, and the panes fold again.**

Started as "the legend covers the graph, fix its default" and the default turned out not to
be the question. The legend was a 26rem opaque overlay pinned over the canvas it indexes --
the primary way in (design rule 19) drawn as furniture -- and `legendOpen` was a bare module
`let`, so the reader's answer could never survive a reload and the *default* was the only
answer there was. It is `panels.legend` now, with its own grid track and a rail.

*What it cost in canvas: nothing.* At 1454px with both panes open the graph pane was 870px
of which 416 sat under the legend -- 454 visible. As a track it is 454 **honest**. What
changes is `fitView`, which had carried `panels.disks ? 0.60 : 0.90` in the pre-merge engine
and lost the term in the chunk-2 merge while the panel stayed, so snap-to-fit went on
centring the stack under the legend. Design rule 25.

*The fold capability was not deleted, it was narrowed.* `applyPanels()` walked
`Object.entries(panels)` before the merge; the 5g rewrite wrote a two-element literal, which
left `panels.hud` and `panels.controls` dead **inside a live key** -- somewhere the guard
written for that exact failure could not see, because it walks the top-level keys of
`DEFAULTS`. Both HUD boxes ribbon again, each strip stating its own summary. Rule 36.

**5i. Built 2026-08-28: pick a routine, see what calls it and what it calls.**

Tom's, and the thing the tool is for. Investigating it found the interaction was mostly
*wiring*: `/api/document?id=routines` already returned all 4,734 routines with their graph
node ids, `/api/node` already answered callers and callees, `recomputeMembers()` already
pulled in one hop, and `selectFromNav()` already did the whole forward path. Four defects
stood between those pieces and the feature.

`ROUTINES` was declared and assigned by nothing, so table mode had always rendered zero rows
(rule 35). Table rows carried a qualname rather than an id (rule 30 again). The topbar
search -- "Search routines, tables, boundaries…", focusable with `/` -- **listened to
nothing**, an `id` control and therefore invisible to both the DOM self-check and
`test_every_static_control_is_listened_for`. And nothing moved the list when the graph
changed.

The navigator is the list now (Tom's call: the ratified three-pane shape, not a split centre
pane), draggable, with the camera deliberately not moving on selection and an off-screen
selection stated with one click to frame it. Design rule 26.

*Then the picture was wrong, and the reason was rule 23 read backwards.* `recomputeMembers`
added raw edge endpoints unresolved, so a call leaving the plate put the **shadow** into the
selection. The real neighbour was never lit and the crossing was skipped -- so picking a
routine drew its callers and callees *only where they sat on the same plate*.
`console_script` has four callers and three callees and drew one dot. Rule 31, and the rule
it breaks had already written the sentence: ending an edge at a stand-in stops a real
connection at a stand-in.

*Found in the same pass, from Tom looking rather than from any check:* the navigator's
number was `degree`, an edge count, in a pane where every other number counts things (rule
32); the module was clipped with `direction: rtl`, which renders
`mensores._internal._cwd_guard` as "...ores_internal_cwd_guard", a string not in the program
anywhere; and `dressNavItems()` overwrote each row's title with the leaf name, losing the
only thing a hover was worth doing for.

**5j. Built 2026-08-28: undo, and a trail that can take you back.**

A stranded session. Clicking the node you are already looking at clears the whole selection
-- a deliberate toggle-off in `togglePick`, and a trap when the click is also how you move --
and every nothing-selected state looks identical, so nothing on screen says which routine you
had. The trail could not help: steps recorded `{view, label, note}` and clicking one set
`state.view`, which from inside graph mode is a no-op. **It rendered, highlighted, scrolled
and pruned correctly and could return nobody to anything.** Rule 33.

Steps carry their subject now, and there is a linear selection history -- ↶/↷ on the HUD
first in the row, ⌘Z / ⇧⌘Z from anywhere, recorded on both selection paths, seeded at boot so
the first click has somewhere to come back to, and guarded so an undo does not record itself.

**The click-to-deselect stays**, on Tom's call and it is the right one: clearing by clicking
is reasonable, `Esc` and the button do the same, and undo makes it recoverable. The cheaper
fix was the better UI.

**5k. What the guards found once they existed.** Four guards written from the four defects
above then turned up six more of the same families, all pre-existing and none of them
reported by anything: the breadcrumb's three centre modes were fixed Mensores pairs shown on
every screen; document mode was a page of hand-written narrative formatted as generated
output; the **egress consent surface** carried one program's file counts (design rule 14 --
the one screen where a wrong number is a consent nobody gave); the glossary asserted findings
about specific `.groma` files; a citation path hard-coded one package prefix; and three
variables were read by nothing at all. Rule 34.

*Three of those guards passed against their own defect on the first attempt* -- one read an
earlier CSS rule with the same selector, one accepted a name appearing anywhere while half
the feature was broken, one accepted a flag being declared while the line consulting it was
gone. Rule 37 exists because of that, and every guard here has now been run against its own
defect **and** against a half-working version.

*Two things could not be verified by this session at all.* The automation tab is given no
animation frames, so `ResizeObserver` never fires and `rAF` never ticks -- a confident,
reproducible and entirely false "the canvas never resizes" finding came out of it, withdrawn
when an observer attached by hand also failed to fire (rule 38). And the near-plane clipping
Tom noticed is diagnosed but not fixed: the obvious remedy, a negative `near` under the
orthographic projection, **breaks pan and zoom**, and was shipped without being driven (rule
39). It is reverted, documented in `graph.js`, and waits for a fix that keeps `near` positive.

**5l. Built 2026-08-28: the pop-up, and threads that lead somewhere.**

Tom's, and stated as a goal rather than a feature: *dramatically expand what each pop-up
says, so a reader can delve deeply in a few clicks, see adjacent nodes, follow threads
wherever they lead, and always find the way back.* Three answers settled the shape — the
pop-up is a rich hover card with the clickable depth staying in the inspector (one
implementation of one pane); all four thread kinds get computed; and following a neighbour
builds **both** behaviours with a Setting deciding, per design rule 2.

*The pop-up.* `getTooltip` was three lines and could never be more: deck.gl's tooltip
returns finished HTML synchronously, so it can only say what the payload already holds and
cannot be filled in two stages. It is a `hover` **event** now — the engine reports what the
picture knows, the shell draws — and the card is painted twice. The first paint is free
(name, qualified name, `file:line`, plate, `3← 5→`, all from the engine's own maps); the
second is `/api/hover`, a compact card carrying lines, comment count, what it touches
grouped and named, its governance ids and one line of WHY. Not in the payload, deliberately:
fifteen thousand node entries already cross the wire and carrying all of that would charge
every node for the handful anybody hovers.

**The fan counts come from the engine and only from the engine.** A second count taken from
`calls` would be over a different population — externals resolve to no node — so the card and
the picture would disagree, both correct, about things neither of them named. Rule 32, and
the fix is not to take the count twice.

*Which left one number still not adding up, and it was the last thing found.* The card said
`3← 5→` while the inspector's **Out** heading said **8**, on the same screen about the same
routine. Both right: eight calls leave `guarded_cwd`, five reach a routine this map holds and
three leave the program, so the graph can only draw five. The fix is not a third count — it
is to state the **externals**, which is the one quantity neither number was carrying and is
not a re-count of anything (an external resolves to no node and is in neither of the engine's
maps). The card reads `45 lines · 6 comments · 3 external` now and 5 + 3 = 8, so the two
headings are one arithmetic instead of two claims. Design rule 8 says an external is
first-class anyway.

*Two things looking found that no check would have.* The card is positioned as the 87px
skeleton and then filled to 293px: on a 418px canvas that put its bottom 29px past the pane,
so the half that had just arrived was the half nobody could see. It is placed again after
the fill — idempotent, so a card that still fits does not move, which is the whole point of
growing downward. And at 26rem it covered **84%** of the canvas on an ordinary 1276px
window, answering the question by hiding its subject; it is bounded by half the picture now.

*The double count, and it was general.* The card first read three tables **and** "DATABASE
20" — which is the same seventeen statements seen by two detectors. Measured across the
program: 991 of 1,316 DATABASE boundaries sit on a line with a `sql_ops` row, and **all
twenty** NETWORK boundaries sit on a `net_calls` row. A boundary already named by a more
specific record on the same line is not counted again — per *line*, not per routine,
because 43 routines have a DATABASE boundary and no `sql_ops` at all and a coarser rule
would blank their card. The transaction statements that then had no row of their own got
one, because dropping ten of seventeen operations silently is the omission the anti-join was
supposed to prevent.

*Threads, computed.* `threads.py` and `/api/threads`, three kinds: **governance kin** (who
else carries this plan), **the other end of a boundary** — the kind that finds code with no
call edge to you at all — and **outliers nearby**, scoped to the package you are standing on.
Every thread carries a **subject** the router can act on, and the click routes from a table
so an unhandled kind is a named error. Ordered by **rarity ascending** in every kind, which
is the opposite of the obvious: a thing shared with three routines is work you can hold in
your head, a thing shared with three hundred is a category. The count travels so the reader
can disagree.

*What it replaced was fiction pointing at a blank page.* `THREADS` was six hand-written rows
about one Mensores routine — `Plan 84-06`, `disceptator`, `SOCIETY_HEADLESS` — and **every
one of them set `state.view = "curiosities"`**, a page that says nothing has been computed.
It rendered, it highlighted, it took nobody anywhere. Rule 30 for the fourth time, and rule
34: it escaped all three pinned-data guards at once, being a `const` object rather than a
`let []`, absent from `PER_PROGRAM`, and invisible to the prose guard, which looks for the
sample program's *name* while this data said `disceptator`.

*Following, both ways.* `followMode` is `replace` or `walk`. Walk needed **no new selection
machinery** — `togglePick` has taken a mode since the multi-pick work and `walk` is `add`,
after which `recomputeMembers` keeps each hop and `buildSelectionGeometry` draws the edges
between consecutive ones because both ends are already members. It reaches both follow paths
through one predicate, so the reader who chose it gets it whichever way they followed. The
walked path states its length and says `⌘Z drops the last`. Verified by driving it: 1 → 2 →
3 hops, undo to 2, redo to 3, switch to replace and back to 1.

*Found on the way, and pre-existing.* The runtime self-check had been printing **"dead
controls"** on every page load since the panes learned to fold, and was wrong about all of
them: `insp`, `fold`, `navid`, `titled` and `legend` are real — CSS track state and handler
parameters — and had simply never been added to `WIRED_ATTRS`. Its own comment says why that
costs: *a check that cries wolf is a check nobody reads*, and a genuine dead control would
have arrived as a sixth line in an error nobody had believed for weeks. `legend` is the one
worth the sentence: it is written on the graph mount, which does not exist until the reader
opens the graph, so the check said four at boot and five afterwards — one page, two answers,
neither of them the truth. There is a source-derived guard now, because the existing one
reads `index.html` and every one of these is written by JavaScript.

*Six guards, each run against its own defect **and** a half-working version.* One of them
failed that discipline on the first try and had to be fixed: it looked for
`followThread(subject)` anywhere in the file and passed against a version where the click
called `selectFromNav` directly — because the string also occurs in
`async function followThread(subject)`, the definition vouching for its own call site. That
is rule 37 applied to a guard written for rule 37. A second was widened after missing `insp`,
which `applyPanels` writes as `grid.dataset[spec.attr]` — a computed property no regex over
attribute literals can see, so the panel table is read too.

*Not verifiable here, and stated as such.* deck.gl's picking pass **does** run in a
browser-automation tab — `pickObject` returns a real node from the `nodes` layer, and the
whole chain was driven end to end from a genuine pick. What could not be exercised is the
pointer event that normally calls `onHover`, which is deck.gl's own plumbing and the same
mechanism `onClick` already uses in production. Rule 38: the instrument proved what it could
and the rest wants a real window.

**5m. Built 2026-08-28: vocabulary threads, and the two lanes finally served.**

The fourth thread kind, and it needed one structural change first. A measured naming
convention carried `claim` — a sentence — and `sql`, which reproduces its *exceptions*.
Neither can answer *is this routine one of these?*, which is what the inspector needs before
it can say a routine shares a convention with ninety-eight others. `Convention.glob` is that
population now, and it is the **same string the exceptions query is built from**, so the
membership test and the evidence cannot drift. Rule 41.

Writing the guard for it found that `test_an_affix_glob_respects_the_separator` had **never
run**: the fixture it uses produces no affix convention at all — five `is_*` routines out of
nine do not survive the coincidence correction, which is rule 14 working — so its assertion
had sat behind `if predicates:` for its whole life. There is a second fixture now, shaped to
produce one: eight `check_*` routines that all return a boolean against twenty-seven that do
not, which is high precision over a *low* base rate. Both terms are needed; seven of seven
against a background where a third of routines have the property anyway is the `Provenance`
coincidence rule 14 rejects.

*The two lanes are served.* `naming.measure()` and `glossary.bind()` were built, tested, and
reachable only from the command line — the shell's glossary and naming pages have said "not
computed yet" since they were written, honestly, because nothing ever served them.
`/api/naming` and `/api/glossary` do now, computed **once at start**: measured at 0.4 s and
2.1 s, against a boot that was already 7.7 s, and the reason it is not lazy is where they are
used. A vocabulary thread is part of `/api/threads`, asked on **every selection**, so a lazy
first call would stall the reading loop on the first click of every session.

*What it produces.* Picking `witness_defer_cmd` shows four vocabulary threads: the convention
`*_cmd` ("registered as a way in — 97 of 99 (C); 98 others named this way"), `mensores`
defined in `__init__.py:1`, and two words the program uses heavily and **defines nowhere** —
`witness`, across 19 constants, 8 way ins, 6 tables and a module. That last is the mirror's
finding arriving where a reader is actually looking rather than on a page they have to think
to open.

*Following one is exact.* The claim says 97 of 99 and following it selects **99** — the
cohort query uses `GLOB` with the convention's own glob, so the population you land in is
the population the number was measured over. Drawn: 986 nodes, 253 within-plate links and
1,109 crossings over 34 plates, at 60 fps. Terms match on **whole segments, never
substrings** — rule 5's most literal form, and the same defect rule 18 found in
`walk.is_test_path`: `mensor` returns nine routines, all of them in `mensores.mensor.*` or
named `write_mensor`, and none of the nine routines whose names contain `dimension`.

*The glossary and naming pages are still not ported*, and now say so accurately: the data is
served and the graph already uses it; what is missing is those two views, which were written
against the prototype's shape and would render the real data wrongly rather than not at all.
That is a different statement from "nothing has been computed" and the two must not look
alike.

*Two things found while driving it.* The runtime self-check had been red since 5g (rule 43).
And `selectionOnScreen()` guarded `getViewports()` with `?.` while deck.gl asserts *inside*
the call — so picking a routine before opening the graph threw out of `applyWanted()` and
took `persist()`, `recordSelection()` and `render()` with it. The selection happened, undo
never recorded it, nothing repainted. Rule 42.

*Three more guards, each run against its own defect and a half-working version*, plus one
that catches a dead query for a kind nothing mints — the quieter half of the both-directions
check, and the one that makes a table look more complete than the feature is.

**5n. Built 2026-08-28: the glossary and naming pages, ported to the data behind them.**

The last two screens that admitted to being unported. Both lanes have been computed, tested
and served since 5m; the two *views* were still the ratified prototype's, written against a
shape the server does not send, and they said so rather than rendering the real data wrongly.
That was the right holding position and not a place to stay — "this page is not ported" and
"this program has no conventions" are opposite claims and a reader cannot tell them apart.

*What made it a port rather than a rename*, in both directions:

| prototype | served |
|---|---|
| `{pattern, ok, n, exceptions: [str]}` | `{glob, holds, total, kind, rating, prevalence, sql, note, exceptions: [{name, where}]}` |
| `{term, declared, module, opaque, circular, docs, project}` | `{term, uses, used_as, defined, senses: [{definition, provenance, source, line, heading, form}]}` |

`glob` is what makes a convention **followable**: it is the same string the exceptions query
is built from (rule 41), so the cohort you land in is the population the number was measured
over. Driven: the naming page's *Show all 99 in the graph* on `*_cmd` selects exactly 99, and
the trail records `*_cmd` so the detour is free. `rating` leads and the percentage is gone,
because `naming.py` says why in as many words — *a percentage implies a precision this does
not have*. And an exception carries where it lives, so the three `*Error` classes that are
not exceptions are a place to go rather than three names.

The glossary's four hand-named document slots became however many `senses` anything actually
said. That is not a convenience: the prototype **knew in advance which three documents would
define a word**, and design rule 11 says documentation is often absent and every path has to
work with none at all. Grouping by evidence rather than by an expected document is what makes
the page work on a program with no `.groma` at all.

*Two things the prototype had that are deliberately not here.* `INFERRED_SAMPLE` was two
paragraphs of Mensores prose about `oscal` and `testkit` — rule 34, and it went with the
port. And `circular`, "the gloss repeats the word instead of explaining it", was a hand-set
flag on one pinned term; computing it honestly flags **63 of 96 senses**, including *"Society
of Mensores — spec-and-test-driven development with deterministic governance"*, which
explains perfectly well. That is rule 1 and rule 14 together — a detector whose first sample
against real data is mostly wrong is not shipped, it is dropped.

*`PROVENANCE` is gone rather than renamed.* It held every source span of every citation, 52
KB pinned for one program. The viewer fetches one span from `/api/source` when a citation is
opened — the same bargain the hover card makes. What it exposed is a real limitation, now
**stated on the page instead of hidden behind a button that opens nothing**: `source.db`
holds the 626 files the graph was built from, and the document corpus is scanned but not
stored, so a docstring opens in context and a definition quoted from a Markdown file names
its file and line and stops. The viewer's foot also carried a hard-coded analysis date, which
is rule 34 in a form the prose guard cannot see — it looks for the program's *name*.

*The navigator counted from an array nobody had fetched.* `TERMS.length` beside "Glossary" is
zero until the page is opened, so the row read as *nothing here* — the exact confusion the
port exists to remove. The two lanes' **sizes** ride with the cover now (`cover.py` takes a
`vocabulary` block, and `serve()` computes the lanes before the cover so it can); the bodies,
234 KB between them, are fetched when their page is opened.

*And the fetch is asked from `render()`, not from a click.* Five things route to these pages —
the navigator, the breadcrumb, `data-goto`, a curiosity and a trail step. A loader wired to
one of them is a page that works from one direction and says "not asked for yet" forever from
the other four, which is design rule 16's family with no control to look at.

*Found by driving it: the filter could not be typed into.* 412 ms per keystroke. The handler
called `render()` — which rewrites the centre pane, the inspector, the navigator and the
trail — and then put the caret back in the field it had just destroyed. **The caret
restoration was the tell**: a workaround for having used the wrong instrument. It refills
three elements now: 51 ms for the page, 9 ms per keystroke, and the count line states what
the filter removed (design rule 1). Two things came out of measuring it — 1,214 `data-thread`
attributes each carrying a JSON subject, and 1,214 listeners rebuilt on every keystroke. A
word **is** its own identity, so the undefined list carries `data-term` and one delegated
handler builds the cohort. That is rule 30 read the right way round: the control must carry an
identity, and constructing the subject from it belongs in the route, where the table is.

*One server-side defect, invisible until something printed the string.* `_affix_conventions`
takes both `noun` and `plural` — "class" and "classes" — and built the population with
`f"{noun}s"`, so every class affix convention read **classs ending in `Error`**. `plural` was
passed and used in one place and ignored in the other, for as long as the naming page had
been unported.

Its guard is the more interesting half. Written against the existing affix fixture it
**passed against its own defect**, because that fixture produces routine conventions only and
`f"{noun}s"` is correct for "routine". A second fixture, eight `*Error` classes against
twenty-seven that are neither, makes the case reachable. Rule 41's finding for the second
time in two sessions: *a test whose fixture cannot produce the case has never run.*

*Four guards, each run against its own defect and against every half-working version I could
express* — eleven mutations, all caught. The load-bearing one is
`test_the_vocabulary_views_read_the_fields_the_server_sends`, and it is a shape the existing
guards had no name for. A dead control renders and does nothing (rule 30); a dead setting is
read by nothing (design rule 16); a dead variable is assigned by nothing (rule 35). This is a
**live** control reading a field that does not exist: `cv.ok / cv.n` is `NaN`, the bar renders
at zero width beside a claim that is perfectly true, and nothing throws. Rule 44. The check
reads the served key names out of `vocabulary.py` and the accessed names out of the two view
functions, in that direction — a view may leave a served field unread (`uses` is a real
example; the page shows `used_as`, the same fact in the form a reader wants), but a view
reading a field the server does not send is rendering nothing while looking finished.

*Two findings the port made visible, neither fixed, both for the vocabulary lane rather than
for the dashboard.* They are recorded because they were unreachable while the page said
"not computed yet", which is most of the argument for having ported it:

- **A constraint is not a definition.** `DEFINITION` is one of the 60 terms the glossary calls
  defined, and its gloss is `1 ≤ len ≤ 5000 chars`, a DASH_GLOSS mined out of a field table in
  `22-03-PLAN.md:410`. It is used once, as one constant. Rule 12's family: prose-shaped is not
  the same as prose.
- **The undefined list is mostly not words.** Its head is `DDL` 57, `EXTRAS` 50, `REASON` 43,
  `KEYS` 40, `BYTES` 39, `CHARS` 37 — the tails of SCREAMING_SNAKE constant names, not words
  the program leans on and never explains. The genuinely interesting ones are in there —
  `witness` (19 constants, 8 way ins, 6 tables, a module), `posture`, `claim`, `probe` — and
  are buried among segments. Precision beats recall (rule 1), and this is the mirror's finding
  arriving with its recall turned up too far.
- Also seen, and a corpus fact rather than a defect: `mensores` carries the *same* definition
  twice, from `.groma/PROJECT.md:474` and from a `.claude/worktrees/…/.paul/PROJECT.md:302`
  copy of it. The scan reads worktrees.

*What the instrument could not prove.* The pages are HTML and CSS with no canvas and no
animation frame, so the automation tab is a fair witness for them (rule 38 bites on rendered
frames, not on layout) — geometry, overflow, column counts and every interaction were driven
here, and the console is clean. What it cannot say is whether they *read* well at Tom's own
24px browser default on a 4K screen, which is where the last two layout defects came from.

**5b. Planned, not scheduled: the layered layout — a stack of architecture drawings.**
Tom's, stated 2026-08-27. Keep everything that exists and add a second way of drawing a
plate: instead of a spring layout, lay the disk out the way Mermaid lays out an
architecture diagram of that one module — layered top-to-bottom, ordinary edges, nodes as
rectangles or as the pseudo-spheres, which of the two does not matter. Crossings between
plates stay exactly as they are now. The result reads as a stack of architecture drawings
rather than a stack of constellations, so the disks must also **spread along X and Y
independently**, not only along Z.

Four consequences worth fixing in place before anything is built on top of them:

- **It is a layout, not a mode.** The centre pane's modes are graph / table / document.
  Layered sits *inside* graph mode beside `structural` and `force`, which is what
  `layout.py` already anticipates and what design rule 2 asks for — force answers "what
  clusters", layered answers "what flows into what", both are good, so both get built and
  usage retires the loser.
- **Disk placement must become an origin, not a height.** `disk_heights()` returns Z
  alone and the renderer stacks on Z alone. X and Y spread means `disk_origins()`
  returning `(x, y, z)`, with three independent spread multipliers in settings. Cheap
  now, a rewrite of every position path later.
- **Layered edges are routed, not straight.** A Sugiyama drawing puts bends in its edges;
  `LineLayer` draws segments. Within-plate links under this layout want `PathLayer` with
  computed waypoints. The crossings keep `LineLayer` — they genuinely are straight lines
  through Z.
- **The size problem does not go away, it moves.** The largest plate holds 959 nodes.
  Mermaid itself is unreadable well below that, and a layered drawing of 959 nodes is a
  very tall picture rather than a dense one. Layered will need its own answer to bounding
  — rule 8's, most likely: draw a bounded thing only where the complete listing sits
  beside it.

Not scheduled. Recorded so the shell, the settings schema and the layout module leave
room for it rather than being retrofitted.

**6. Then, and only then, temporal layers.** Snapshots keyed by revision, the flow diff,
the scrubber. Identity is already position-independent, which was the prerequisite.

**7. Attestation**, on the layer storage — see "Attestation: promoting an inference"
above. Not before it; it needs the same content-addressed, revision-keyed store.

Deferred, recorded so they are not lost: a graph viewer that holds 10,000+ nodes (see
`../usdgraph`, NetworkX to OpenUSD); cross-process stitching; TypeScript extraction;
Swift extraction.

### Navigator: scrolling feedback from Tom, 2026-08-28 — not yet fixed

Given at the end of the session with two screenshots, and recorded whole because the
diagnosis is half-written already.

**1. The truncation notice is at the bottom of the list it describes.** *Routines* shows
`showing 200 of 4,734 — narrow the search, or open the table for all 4,734`, and the only
ways to see it are to scroll past two hundred rows or to collapse the group — at which point
it appears immediately, which is what makes it obviously wrong. Design rule 1 is satisfied in
letter and defeated in fact: the view *does* state what it removed, somewhere nobody reads.
**It belongs at the head of the group, and it must read the same open or closed.**

**2. Scrolling into Routines traps the reader.** Two hundred rows with no `ROUTINES ▶`
control in reach, so *Explore*, *Packages*, *Boundaries*, *Tables* and *Vocabulary* — every
menu below it — cost a scroll through the whole list to get back to. This is exactly the
finding 5g wrote down and then applied to only one element: *the navigator scrolls 1,151px of
its own content, and a collapse control that scrolls away is one the reader cannot reach from
the bottom of the list.* The panebar was made `position: sticky` for that reason; **the group
headings inside it were not**, and they carry the same control.

**3. Tom navigates by scroll wheel, heavily**, and says so — "it may not be best UI practice
for me to move the way I do". It is not the reader's job to move differently. The navigator
wants furniture that suits a wheel: sticky group headings, and buttons that get you between
groups without traversing one.

Not started. It is a navigator problem, not a vocabulary one, and it is bigger than the two
symptoms — the question is what the pane offers someone who arrives in the middle of a long
list, which is the ordinary case at 4,734 routines.

**5o. Built 2026-08-29: the navigator that survives a long list.** The three symptoms
Tom gave at the keyboard, and the question behind them -- what does the pane offer someone
who arrives in the middle of 4,734 rows?

**The furniture.** The truncation notice is above the list it describes, inside a sticky
header, and reads the same open or closed. The pane is a grid: a header row that never
scrolls over a body that does, with `.nav-headwrap` sticky inside it -- two grid rows
rather than a second sticky element, because a sticky element under another has to know
its height and that height moves with the scale multiplier. A jump strip in the panebar
takes the reader to any group in one click and marks the group they are in, generated from
the same ordered table the groups are; the menu order moved out of `render()`, where it was
applied by shuffling DOM nodes the strip could not see. How many groups stand open at once
is a Setting, defaulting to one at a time.

**The list.** Grouped by package -- 47 rows a person can read instead of 200 arbitrary ones
out of 4,734 -- and by the package the *stack* uses, so a heading names a plate. Not every
package has one: `graph.py` merges anything below `MIN_DISK`, so `/api/routines` sends the
plates it actually has and a merged package says so on its row. How many routines a package
lists is the reader's: 50 / 100 / 200 / 500 / All. That came from Tom, and the reason is
worth keeping -- 200 was a judgment about markup per keystroke, and on a program whose
packages hold 200-400 the notice read `200 of 377`, which is a tease rather than a bound.

**What it cost, found by measuring.** Closed packages were still building their rows --
3,413 buttons a keystroke against the flat list's 200, at 341 ms. A search opened every
package it matched in, and `e` matches all 4,734 routines in all 47 packages: 483 ms on the
first keystroke of an ordinary search. Both are the glossary filter's 412 ms again, and the
second was the worse answer as well as the slower one. Now: 12.4 ms median, 22.2 ms worst
over three runs of a six-keystroke search.

**What it found on the way.** Four defects nothing had reported. The accordion opened
whichever group sat first, so "Ways in first" left the routine list closed -- an *opening*
rule that names a position breaks exactly as an ordering one does. A sticky child sticks to
the padding box, so the scroller's top padding was a strip the list scrolled through above
the heading meant to cover it. The jump strip's marker lit *Explore* one click after the
reader asked for *Packages*, because with one group open the pane is short and the browser
clamps the jump -- two correct numbers, neither saying what the reader had just done. And
`_fn` in the guard file stopped at `\nfunction` and swallowed the `async function` after
it, so a guard naming one function was reading two.

Fifteen guards, each run against the defect it came from and against a half-working
version. One passed against its own defect first time: the line had been disabled by
commenting it out and the guard found the words inside the comment. Rule 37, twice in one
session, which is the argument for the practice rather than against it.

**Still owed on the navigator**: nothing named. Whether 47 closed packages is the right
first screen, and whether the accordion should be the default, are both questions for use
rather than for argument -- which is why both are Settings and both are counted.

**5p. Built 2026-08-29: you are here.** Tom, on getting lost in a large stack: *I move the
graph around and look at it from various points of view. I might click away, hover over
other nodes, explore, and chase rabbits. I haven't actually decided to leave though.*

**An arrow over what was picked.** A billboard, for rule 22's reason -- a picture of
something with no orientation must not have one, and an arrow foreshortened by the tilt
reads as a shape lying on a plate. Over the *picks*, never the one-hop neighbours: the
neighbours are the answer, the picks are the question. Shaded from the same direction the
spheres are lit, baked into the texture rather than a shader, because there are two dozen of
these and fifteen thousand nodes, and `mask: true` would have thrown the shading away. Its
colour is a Setting clamped at 3:1 against the *graph's* ground, re-asked when the ground
moves; a refusal says why (design rule 6). Capped at 24 with the count stating what it left
out, because a thread can select ninety-nine and ninety-nine arrows is weather.

**A way back to the view it was found in.** Not `snap to fit`, which frames the selection --
this restores the reader's own framing. Armed by a selection and *set* by the first view the
selection can actually be seen in, because design rule 26 says picking never moves the camera
and a view without the subject in it is not somewhere to be taken back to.

Both halves of that were wrong first and neither failed loudly: it must be asked after
`recomputeMembers` or it measures the previous selection, and `selectionOnScreen()`'s null
means *cannot say* -- which on the commonest path of all, a pick that mounts the graph, is
the answer it gives. Rule 42's distinction acted on rather than documented. The button's
enabled state is written where the counts are and not where the HUD is rebuilt, since a
selection never rebuilds the HUD: design rule 16 in the *state* of a control.

**Moved to the rim, 2026-08-29, on Tom's direction**: *put it at the side of the cylinder,
pointing at the plane that holds the node, at the x or y coordinate that leads the eye to
it.* The arrow now stands on the plate's own circle at the height of the plate holding the
node and on that node's bearing, aimed inward. Rim point, origin and node are collinear
because plates are circles centred on the axis and the spread stretches node and plate by
the same pair of factors -- so the bearing is taken from the *base* coordinates, or the arrow
drifts off the plate the moment either spread slider moves.

Aiming a billboard means computing a *screen* direction, and the convention was read out of
deck's vendored shader rather than guessed at, because an arrow aimed the wrong way is a
working-looking signpost pointing at nothing and this session had no frames to check it in.
`rotate_by_angle` is `mat2(cos, -sin, sin, cos)` -- column-major, so `(x cos + y sin, -x sin
+ y cos)` -- followed by a y flip; with the icon's tip on its anchor that makes the arrow
point along `(sin, cos)`, hence **`atan2(dx, dy)`**, not the usual `atan2(dy, dx)`. A guard
asserts both halves of the shader still say that.

Both placements are kept as a design-rule-2 pair, defaulting to the rim. **The rim placement
leaves the frame when the reader snaps to fit**, because fit frames the *selection* and the
rim is a plate's width away from it; that is stated in the Setting rather than left to be
discovered, and it is the reason over-the-node stays built.

**Deliberately not built, and a candidate Setting**: re-recording the anchor while the
selection stays visible, so "back" means the *last* good view rather than the first. It is a
real second answer and might be the better one; design rule 2 asks for use behind a pair
before building both, and this does not have it yet.

**And one word for a plate.** The fps line said "52 disks" while the size menu said "plates".
Plate won -- rare enough that the product defines it, common enough to be guessed at. Scoped
to what a reader sees; `disk` stays an identifier and **that is a debt, not a decision**:
renaming the persisted keys discards every saved arrangement without a version bump, and the
code has a second live meaning for "plate" (the polygon that draws a disk -- `showPlates`,
`diskPlates`, `plateFill`), so renaming half the pair leaves the collision it was meant to
remove. A guard keeps the reader-facing half honest.

**Plate, and not plane or planum -- decided 2026-08-29.** *plane* is unbounded by
definition where these are bounded, and it is already taken in this very codebase for the
near and far frustum planes (rule 39 is an essay about one), so a renderer reader's mind goes
to the wrong object. *planum* is the Latin flourish, ruled out with the rest of it. *plate*
is bounded, physical, stacks, and has a plural nobody has to be taught -- and it leaves
*disk* to mean what it means everywhere else in computing, which is the whole reason the
question came up.

**On the Latin, since it was asked and then declined**: the word is **tabula** (pl.
*tabulae*) -- a flat board,
and also a picture, and also a register. Recognisable through *tabula rasa* without being an
English word, so DunneFlow could define it in its own glossary the way Mensores defines
`mensor`. *lamina* is more exact for a thin plate in a stack and collides with the temporal
*layers*; *discus* is simply the etymon of "disk"; *orbis* reads as "orb", and the nodes are
already spheres. Not adopted: a reading tool for someone orienting in code they did not
write should not open by teaching them a word.

**5q. Built 2026-08-29: focus.** Tom, with two screenshots of `assert_manifest_fidelity`
lit among 9,871 dimmed nodes: *Is that the right node? There are so many, and if I hover
over the wrong one, I get the wrong information. That's nice for exploring, but not for
targeted research.*

Three things, and they are one feature.

**The arrow is clickable.** It selects the node it points at and frames it. Two ways to get
that wrong, both silent: the click must route by **layer**, because `info.index` from the
pointer layer is an index into two dozen arrows and reads as a different routine entirely;
and it must *set* the selection rather than toggle it, because the node an arrow stands over
is already picked and `replace` on a single pick is the deliberate toggle-off (rule 33) --
the one control whose purpose is *go there* would have cleared the selection. Hovering the
arrow reports the node it points at, which is how a reader learns the two are connected.

**A reticule** -- a ring with four ticks, fixed in screen size, drawn over everything, on
each picked node. Dimming answers *what is not mine*; this answers *which one is mine*.

**Focus, a switch on the HUD.** Locked, only the lit set answers a hover or a click. The fog
stays drawn, because rule 19's reason for drawing it has not changed -- what changed is what
may answer, and keeping those separate is the whole discipline of it (rule 47). With nothing
selected everything answers, or the lock would be a mode nobody could click out of. Default
**on**, which is a judgment: the behaviour it replaces is the one Tom reported as wrong for
research, and the toggle is one click away with its state on its face.

Consequence worth knowing: clicking the arrow frames the selection, and the rim pointer is a
plate's width away from it, so the arrow leaves the view on its way to doing its job. The
reticule is what stays.

Eight guards, each run against its own defect. One passed against its own defect first time
-- `"RETICULE_SIZE * opts.scale" in ret` is still true of
`RETICULE_SIZE * opts.scale * opts.nodeSize` -- and is fixed. That is rule 37 for the third
time in one session, always the same shape: a containment check is not a check.

**5r. Built 2026-08-29: state you can see, and the cap that hid the selection.** Feedback
at the keyboard, and one item of it was a defect wearing a UI complaint's clothes.

**"The left menu isn't jumping — bidirectional sync?"** It was, and then it silently was not.
Pick `verify_timestamp` in the picture -- rank 400 in a package of 531 -- and the inspector
filled, the package opened, and the list rendered **no row at all**: nothing marked, nothing
scrolled. The per-package cap had dropped it. Identical on screen to the sync being broken,
which is exactly what it was reported as. **The cap never hides what is selected** now; the
row lands last among those shown, which is its right place, and the note counts it
(`showing 201 of 531`). The bidirectional loop itself was never broken -- it failed only on
the routines it is most needed for, which is the shape this project keeps paying for.

**A toggle that is on must look it.** `focus` shipped with its label and its tooltip changing
and nothing else, so the one control on the graph with two *modes* looked exactly like the
six beside it that have none. Every pressed state on the page now fills with the accent --
the same channel the navigator's current row and the legend's selected plate already use for
*in force*, spent once (design rule 4). The guard is **derived from the stylesheet**, not from
a list, and it immediately found a seventh control nobody had looked at: the source viewer's
tabs.

**The navigator's current row** was a soft tint with a 3px bar. It is a filled accent bar with
white text now, its module path and fan counts carried with it -- a row that goes accent while
its own contents stay grey is less legible than the state it replaced. And **redo** has a word
on it: an arrow is a puzzle for one of the two controls a stranded reader is looking for.

**Asked and already true**: the reticule follows every left-menu row that resolves to nodes --
a routine (1 reticule), a way in (24 of 104), a table (24 of 57). A **package** gets none, and
that is rule 47's own argument: a plate is not a place, and a mark in the middle of 645 nodes
says nothing about where any of them is. The plate's version of the same answer already
exists -- it is drawn faintly and named on the HUD (design rule 26).

**Not verified, and it needs a real window**: what the arrow looks like. The automation tab
draws no frames at all -- canvas 300x150, `frames 0` -- so its shape, size and shading are
for someone with a real window to judge -- and so is deck's *picking*, so the arrow's click
and the focus lock are reasoned and guarded but not driven. Rule 38, and rule 39's lesson:
not being able to test a change is a reason to describe it, never a reason to ship it and
ask.

**5s. Code viewing, as it stands — taken stock of 2026-08-29.** Asked at the end of the
session, and answered by looking rather than by recalling.

`source.db` is content-addressed by the `content_hash` already in `files`, so each unique
body is stored once however many paths or revisions point at it, and compressed: Mensores'
626 files are 7.8 MB of text in **3.1 MB on disk**. Two ways in, both live and both verified:
`/api/node` carries a `source` block of the definition ±3 lines with `focus` marking the
definition's own span (the inspector's *Show source* pane), and `/api/source?path&first&last`
serves any span or a whole file (the glossary's citation viewer, a modal with a tab per
sense). Both say on the page that this is the source **as measured when the map was built**,
which is the whole point of content-addressing it. Three absences are told apart rather than
blurred -- no sidecar, a sidecar without this file, and a node with no file at all.

**Not built**: a file browser (source is reachable through a routine or a citation, never by
opening a file); search inside source; syntax highlighting; and document mode's narrative
view, which the ratified design specifies as serif prose read from `source.db` and scrolled
to the selection -- a different thing from the eight structured documents behind
`/api/document`, and both are wanted. The document corpus itself is scanned but not stored,
so a docstring opens in context and a Markdown definition names its line and stops.

**Three printed promises the page was not keeping**, found by taking that stock and by
nothing else. The inspector's source button has advertised an `S` badge since it was written
and nothing ever listened for the key; it works now. The worklist's two jump buttons -- *Go
to the first occurrence in the graph*, *Show all N occurrences as a table* -- were
live-looking buttons with **no attributes, no handler and a keyboard badge each**: the
original design rule 16 defect, still on the page, and invisible to the runtime self-check
for a reason worth keeping. **That check enumerates `data-*` attributes, so a control with
none is one it cannot see at all.**

They are not simply wireable, and that is the half that decided the fix. A finding carries
the *name* it found -- `self._emit` -- and not a node id; eleven routines share that name,
and resolving it is rule 5 exactly. `queries.py` had written the answer before anything
needed it: inventing an id to make a row clickable is a link to nothing. So both are
disabled with the reason on them, the choice `undo` already makes. **Building them is a
server change** -- `anomalies.py` carrying the node ids it already knows -- and it is the
obvious next thing in the worklist, which design rule 9 says is a worklist and not a report.

**5t. Built 2026-08-29 (second session): the pop-up learned to be read, and four panes
stopped lying.** Everything here came from Tom at the keyboard, most of it from screenshots,
and the through-line is that **six defects were controls wired perfectly to a stylesheet or
a layout that could not carry them**. Every automated check on the page passed for all six.

**The cursor.** deck.gl's hand is opaque and drawn below-right of its own hotspot, so at dot
sizes it covers the node being aimed at. A reticule with four ticks and a hole in the middle,
hotspot dead centre — deliberately not the selection reticule, which is a ring *plus* ticks,
because the two are on screen together in the ordinary case. White over a dark halo rather
than the accent: design rule 4 spends colour on one dimension and the accent already means
*in force*. Not keyed on `isHovering`, which would promise an answer from a fogged node under
a focus lock. An honest exception to design rule 3 recorded as one — a cursor's size is the
OS's.

**The navigator's pop-up.** The tiny text was the native `title` attribute. It is the graph's
card now — same markup, fetch, dwell and cache, one component with two hosts — anchored
*beside* the pane rather than following the cursor, because in a list the row is the subject's
position. Fixed to the window at body level, since the navigator is a scroller that would clip
it. The `title` came off the rows, which is half the fix: a native tooltip renders on top.

**The invocation line**, and the defect it uncovered. `Routine.signature()` handled the
`*args` and `**kwargs` prefixes and never the bare separators between groups, so
`def f(a, *, b)` rendered as `f(a, b)` — a different function. **998 of Mensores' 4,734
routines**, and `render/markdown.py` uses the same function, so `03-routines.md` had been
printing them wrong since it existed; it now carries 192 signatures with a bare `*`.
Underneath it, rule 8 at its smallest: `_params` folded `posonlyargs` into `args`, destroying
the `/` at ingest. Neither codebase here uses `/` in 4,724 definitions, which is the argument
for fixing it while nothing depends on the old shape. One renderer, `schema.signature_parts`,
reached from Python for the documents and over the wire for the card.

**The detail window.** `Enter` over a card opens a destination: callers left, the routine and
its invocation line between, callees right, what it touches beneath, threads leading away.
Not a second set of facts — the same `/api/node` and `/api/threads` — and not a second state:
every hop is an ordinary `selectFromNav`, so the stack lights up underneath, the trail records
the journey once, and undo reaches every step. The card stays `pointer-events: none`; the key
is what keeps that decision.

**Detached, and the pattern for the code viewer.** `?view=detail` boots the same application
and hides everything but the panel — not a second page, which would have been the third place
this project draws one node. The two windows are **peers over a `BroadcastChannel`**, not
parent and child: a `window.opener` protocol breaks when the reader closes the main window,
reloads either, or opens the view by pasting its URL. Each publishes where it is looking and
adopts where the other is, and adopting never republishes.

**Table mode, three reports and three unrelated causes.** 2,418 ms to 46 (rule 45, and the
budget table). A resize the browser was ignoring (`table-layout: auto`, where a `th` width is
a suggestion it weighs against content and always loses). And a pane that was in sync with no
way to tell — the selected row sat 238,401px down with the scroll at nought, so it now states
`row 3,633 of 4,734` with a *Go to it*, and moves once per subject rather than once per
repaint.

**The header that could never have stuck**, and the scroller that never scrolled: rule 50.

**The graph that came up blank**, and the fallback that hid it: rule 49.

**Back kept the mode rather than the subject.** A step records the view it was made in, so a
reader in the table pressing Back landed in the graph. Changed rather than documented,
because the centre pane's settled rule already decides it: three modes are three ways of
looking at one selection, so the mode is not part of where you were. Still restored for
somewhere genuinely elsewhere — the glossary, the worklist, settings.

**Rule 44's original, still live in the pane the whole design points at.** The inspector's
demoted signature read `p.annotation` and `p.default` against a query sending `type` and
`dflt`, so **every parameter had rendered as a bare name, no type and no default, since it
was written**. Found by reading the code beside something else, not by any check.

*What it cost in checks.* Sixty-odd mutations across the session; **twelve guards passed
against their own defect first time**, every one a containment check taken over too wide a
span or against a name rather than a behaviour. Three failed on the *comment explaining the
defect they check*, which is what `_code()` is for — and its first version stripped string
bodies too, which in this codebase is where the checked code lives, so every check passed
against an empty string. `_fn`'s own docstring warns it reads past its subject, and it did
that again here.

*Not verified, and it needs a real window.* The blank-graph fix. The automation tab never
mounts the graph at all — `canvas MISSING`, `frames 0` — so that diagnosis is from the code
and the arithmetic. Rule 38.

**Next: the code browser**, and Society will be pulled fresh first, which makes the temporal
question concrete rather than hypothetical for the first time. What exists today: `source.db`
holds 626 files content-addressed, `/api/source?path&first&last` serves any span, and every
routine carries `file`, `line_start`, `line_end` — so a browser with clickable names in both
directions is the detached-window pattern again. What does **not** exist: any second point in
time. `source.db` holds one snapshot, so the time selector and the diff screen are the layer
work, not a feature of the browser. Build the browser against today's snapshot first; the
layers then add a selector to a working view rather than inventing both at once.

### Still open

- Layer storage builds on the same sidecar: content-addressing is version-control
  agnostic by construction, since it never asks where the bytes came from. Git,
  Perforce, Lore, a nightly cron, and a release tag are all the same problem.

- **The ratified design lives in a claude.ai artifact**, and finding it again cost a
  screenshot and a search:
  `https://claude.ai/code/artifact/f993d319-d2b7-4217-9130-cdbba698d1bc`
  It is the complete design -- cover, graph, table, doc, worklist, glossary, naming,
  exploration, source viewer, settings, trail, curiosities, inference postures -- with
  Mensores' data pinned in. Read it with the Artifact tool rather than working from a
  screenshot. Views not yet ported are still specified there.

- **Navigator bounds are a judgment, not a measurement.** Top 6 ways in, top 8 packages,
  top 8 tables; the complete lists are on the cover and in the views, so rule 8 holds, but
  the cuts have not been reviewed in use.

- **Packages reads 47 where the ratified design says 24.** `COVER_PACKAGES` counts every
  second-level package including very small ones. Either a floor is wanted or 47 is simply
  the truth and the design's number was from an older extraction. Not yet checked.

- **Document mode's backend is built and not wired to a view.** Eight documents, every row
  carrying the graph's own node id: entrypoints 175, routines 4,734, data 665, constants
  2,618, boundaries 3,950, database 1,042, network 32, artefacts 155. `/api/documents` and
  `/api/document` serve them. What the ratified design calls Document mode is a different
  thing -- narrative prose, serif, the current selection read as text and scrolled to the
  selected routine, reading from `source.db`. Both are wanted; they are not the same view.

- ~~`/api/node` and `inspector.js` are a parallel implementation of the shell's own
  `viewInspector()`.~~ **Closed in chunk 2.** There is one inspector, the ratified layout
  reading the real endpoint, and `inspector.js` is gone from `static/`.

- ~~**The glossary and naming views are not ported to the data now behind them.**~~
  **Closed 2026-08-28 -- see 5n.** Both pages read the served shape; a convention is
  followable by its `glob` and proves itself with its query, a term shows however many senses
  anything said about it, and a citation opens the surrounding source from `/api/source`.
  What is *not* closed and belongs to the vocabulary lane rather than to the dashboard: a
  DASH_GLOSS mined out of a constraint table is being counted as a definition, and the
  undefined list's head is segments of SCREAMING_SNAKE constant names rather than words.

- **`CURIOSITIES` is the same job at program scope.** `threads.py` already measures the
  outlier family per package -- most commented, most called, deepest closure, most lopsided
  table -- and design rule 15's curiosities panel is that computation run over the whole
  program rather than one plate. It says honestly that it is not computed yet; it now has
  the machinery sitting beside it. *Built 2026-09-01 — and at program scope it turned out to
  want its own module and its own queries, because what a card must carry beside the number
  is the **middle** it is being read against. See "Curiosities: the doorway panel".*

- The usage report screen's content. `followMode`, `graphLayout`, `graphTheme` and
  `menuOrder` are all design-rule-2 pairs counting usage now, and none of them can be
  retired on evidence until something shows the counts.
- Layer selection UI — time slider, revision list, two-point comparison, or all three.
  That is the next conversation, not this one.

Settled: this is a **reading tool** you open to understand something — not a working
tool kept open while editing. Layers are how it stays true as the code moves.

**5u. Built 2026-08-29 (third session): the code browser, and a snapshot that has a name.**
Planned with Tom at the keyboard and built in four chunks. Every decision below is his;
what follows each is what building it found.

*The decisions.* The code viewer runs in **three** places — the left pane, a fourth centre
mode "in greater detail with columns", and a detached window — because inside one window the
left pane is the only place code can sit while the stack holds the centre. The Code group is
**stacked**: a file list that collapses once a file is picked, and that file's lines beneath
it. **No syntax colour**: things that are already database objects are clickable and that is
enough. **Search inside source is its own loop.** And **prepare for versions now**: WORKING
as a state, a timestamp on every snapshot, another state naming what is being compared.

**The revision spine.** `source.db` held its paths under the empty string and had nowhere to
record when the bodies were read, so the id and the state were one thing and a re-analysis
replaced the only snapshot there was — the bodies surviving, because blobs are never pruned,
and nothing left that could name them. A `revisions` table now says which snapshot the next
capture writes into. Two columns that look like one and the difference is the point:
`revision` is the identity and is always known, `captured_at` is a claim about the *source*.
For an ordinary capture they are the same instant; for a sidecar migrated from before this
existed they are not, because nothing in the store knows when its bodies were measured — so
`captured_at` is left empty rather than filled with a plausible lie, and `dunneflow revisions
--seal --at` states it from the graph's own `analysed_at`, which the CLI legitimately holds
both halves of. Mensores is sealed as `2026-08-29T19:43:39Z`, captured 2026-08-29 17:02 UTC,
626 files.

Three things found writing it. **Reading and writing are different questions**: a read that
resolved only to WORKING would answer "no source" for every file between a seal and the next
analysis, which is precisely when someone opens the dashboard to see what they are about to
replace. **Rule 20 in the store that must survive everything**: a writable open migrates an
un-stamped sidecar and a read-only open reports it as un-stamped and changes nothing —
verified on the real sidecar, byte-identical after listing. And **rule 37**: five guards run
against their own defect, one missed, because the mutation removed a redundant inner check
while `__init__`'s early return did the real protecting.

**A file, and what the map knows about every line of it.** Nearly every fact table carries a
`file` *and* a `line`. Links are inline spans carrying the node id they select, and there is
no name matching anywhere in them — `calls.callee_id` is the resolver's own answer, so rule 5
never arises. What the resolver does *not* record is a **column**, so a call is underlined
only where its expression occurs exactly once on that line; guessing a column is inventing a
position, and both counts ride with the payload.

**The margin was wrong when first read, and reading it is the only reason I know.** It
printed `int` on its own line labelled *leaves the program*. `calls.external` covers three
different things — 11,256 builtins, 3,943 boundary touches, 8,630 calls into someone else's
code — and only the third earns a mark. A builtin is not rule 26's case, and `len(x)` is
internal computation, which this tool exists not to report; a boundary touch already has a
boundary row and often a `sql_ops` row on the same line, so marking it here states one act a
third time (rule 40, in the same function as the test written for it); and the first segment
must be a name the file imported, or `out.append` and `payload.get` read as libraries. 1,642
marks on `audit.py` became 1,054.

**Four defects found by driving the thing, and none of them visible to any test.**

`buildNav()` cost **1,937 ms** and `render()` **1,358 ms**, both on every selection and every
keystroke with a 5,838-line file open — worse than the 2,418 ms table defect that earned rule
45, and a slow page reads as a slow page rather than as a defect. Two things that looked like
fixes and were not: `codeCached(slot, codeTable())` evaluates its argument before the call, so
the cache rebuilt 1.37 MB on every hit and threw it away; and re-attaching the built node
still forces a layout over 17,500 elements, which made `render()` *worse* than before the
cache, 155 ms to 1,370. The only way not to pay a layout is not to detach. **Rule 52.**

The pane bounded itself with `calc(100vh - 16rem)`, where 16rem stood for the chrome above
it. On a 589px window that chrome came to 185px, the box overflowed its own scroller, and
**one line of code was on screen** — while every check passed, because the box did declare
`overflow` and did have a height. **Rule 53**, and rule 49's shape in a stylesheet.

The mark column was 15rem and left-aligned. 1,054 marks over 4,820 lines means four rows in
five carry nothing, so most of the pane was a blank column holding the code out past the
middle of the window. 12rem, right-aligned against the code.

And **my own route filed its trail step before awaiting the selection**, so the step carried
`subject: null` — rule 33's defect in a new route, caught by reading a real step rather than
by the guard I had just written for it. `openDetail` had the order right and this did not.

*What it cost in checks.* Thirty-odd mutations across the three chunks. Five missed on the
first pass and every one was a name where the claim was about a behaviour, or a fixture
smaller than the defect: the bounded-list guard ran against a one-file program, so a `[:2]`
that would hide 624 of 626 changed nothing; rule 40's companion had no boundary the other
detectors had not also seen; and the module-scope guard passed because `<module>` never
appears in ordinary source, so the placement rule protected it by coincidence and the filter
could have been deleted freely. The persisted-settings guard caught `state[widthKey()]` for
exactly the reason it exists — a dynamic lookup is how a setting slips past a search for its
name — so both widths are read as named properties now.

*Verified in a real window.* Links reachable by `elementFromPoint` (rule 48), the file header
stays while the code scrolls to line 1,189 (rule 50), columns aligned to a single x, the
self-check reporting every control wired, and the console otherwise clean.

*Not fixed, and reported instead because it is Tom's design and not mine.* The navigator's
nine group headings cost **306px** whether their groups are open or closed, so on a short
window any open group — the routine list as much as the code — gets about 200px. Measured at
589px tall; the automation window could not be resized to check a realistic height (rule 38).

**Next: search inside source**, named as its own loop when this was planned, and **the layer
selection UI** — the storage is ready and there is now a sealed snapshot to compare against
as soon as Society is pulled fresh.

**5v. Built 2026-08-29 (fourth session): search inside the source.** The shape is Tom's,
decided at the keyboard before anything was written: **files first, expand to lines**; **one
box, two lanes** in the Code group; literal and case-insensitive by default with case,
whole-word and regex switches; and **the full margin on a hit** — the routine it sits in, its
marks, its clickable names.

*The measurement came before the design and changed the conversation.* Scanning all 184,722
lines of Mensores case-insensitively is **20–30 ms**, and a regex is 87. Rule 45 has never
been about the search: the whole program is 7.8 MB of text and reading it is cheap. It is
entirely about the **answer** — `e` matches 133,454 lines in all 626 files, and that is the
haystack again. So the cheap pass returns 626 rows at worst and the expensive half, ten
queries for a file's margin, is built only for a file someone opened. FTS5 was the obvious
reach and is wrong twice over: token-based, so it cannot find `_emit` inside `self._emit` or
a substring of a string literal, and there was nothing to make faster.

One compiled pattern serves both passes, because the count on a file row and the lines
beneath it are one claim and `str.lower()` against `re.IGNORECASE` is the easiest way to make
them disagree (rule 13). Whole word is `\b` around an escaped needle rather than a second
path; a regex turns it **off** rather than composing with it, because `a|b` wrapped in `\b`
is not the question that was asked (rule 46). A pattern that will not compile is named, never
answered with no rows — rule 20's `(no rows)` argument in a search box. Where a hit sits is a
line-range lookup, innermost span first: no name is in the question, so rule 5 never arises,
and rule 10 is why the factory is not the answer for a line inside its closure.

`SourceStore` grew a bounded inflate cache keyed by content hash — a body at fifty paths
inflates once — and `text`, `lines` and `path_lines` share it rather than materialising the
same megabyte three times. **The bound is stated at 64 MB rather than pretended away**: text
is the one thing here you cannot answer about without reading it, so the honest answer is a
ceiling that says what it is.

**Four defects found by driving it, three of them pre-existing and none visible to any test.**

*The file filter has never worked past one character.* `buildNav()` wraps every group body in
a `<div class="nav-items">`, so that class inside `#navCode` matches the **wrapper** — and the
narrow refresh wrote rows into it, replacing the box and the caret. The guard written for
exactly this asserted the refresh does not *call* `buildNav`: true, and beside the point.
**Rule 54.**

*The results painted over the four groups below them.* The flex chain that makes the Code
group fill the scroller was written for the file-open state and applied to both, so the list
was squashed to 118px while 1,900px of results overflowed it visibly. Every row present,
sized and correct, and `elementFromPoint` said `.nav-head` for all thirteen on screen. Rule
48, found by hit-testing and by nothing else.

*The code pane measured 0px on a short window.* The nine group headings cost ~306px open or
closed, so on a 536px window the group's share went negative — the file open, its lines in
the DOM, none on screen. The box above it made an existing squeeze worse rather than causing
it. A floor in rem, and the navigator scrolls. Rule 53's flex twin.

*And one of mine.* Auto-opening every file while the answer was small marked 84 open that
nothing fetched, so all 84 rendered `opening…` for ever — and 84 files is 84 requests.
**Rule 55**: a bound must be on the work, not only on the answer, and one truth about what is
open with whoever sets it doing the work.

*Contrast, measured rather than assumed.* The match highlight was `--accent-soft`, which is
what a hovered link fills with and is **1.20:1 against the pane** — for the one mark whose
whole job is to be found, a rumour rather than a highlight. Full accent now, 4.87:1 light and
9.01:1 dark. The pressed switch was 4.05:1 and reads `--text`.

*What it cost in checks.* Twelve mutations on the server and twelve on the client, each the
defect its guard was written from, all twenty-four caught. **Both mutation harnesses lied
before either did** — the first misread `pytest -x`'s truncated tail, the second grepped for
a summary line `-q` does not print here, and both reported everything as surviving. Rule 43
in the instrument, twice in one session; they read the exit code now.

*Reported rather than changed, because it is Tom's design.* The search box scrolls away with
the list — the group's own note is sticky and carries the whole answer, but the input and its
three switches are ordinary content in a group that is 1,900px tall on a broad search. Making
them sticky would cost ~64px of always-visible navigator, which is the vertical budget already
flagged at the last pause. And a hypothesis worth recording because it was reasonable and
wrong: per-row `overflow-x` on 268 hit rows makes 268 scroll containers, the shape that cost
`codeTable` 1,358 ms — and it is 158 ms with them and 165 ms without.

**Next: the layer selection UI.** The storage is ready, Mensores is sealed as
`2026-08-29T19:43:39Z`, and nothing else stands between the spine and a second point in time
on screen.

**Paused here, and the second point now exists.** Tom, at the pause: *society has been
updated and pushed so there is a new version to pull when ready.* So the layer work is no
longer a feature to be built against one snapshot and imagined — pull, re-run `analyze`, and
there are two.

Three things checked at the pause rather than assumed, because the whole next session rests
on them and getting them wrong destroys the thing being compared:

* **The sealed bodies survive the pull.** `source.db` is content-addressed and
  `prune_missing` deliberately leaves blobs alone, so the 626 bodies of
  `2026-08-29T19:43:39Z` are safe once the tree moves on. Its label reads *"before Society is
  pulled fresh"*; it was sealed for this.
* **A second `analyze` opens a second revision beside the sealed one.** Verified on a copy of
  the real sidecar: `open_working()` on a store whose only revision is `FOR_COMPARISON`
  created `2026-08-29T22:27:21Z` as `WORKING`, left the sealed row untouched, and the sealed
  snapshot still answered `text()`. That is `sourcedb.py`'s whole reason for existing and it
  now has a test-by-driving behind it.
* **The pull is not DunneFlow's to make.** *Version control must stay pluggable* — the tool
  never talks to a VCS, and a snapshot is identified by when it was captured rather than by a
  commit. Someone runs `git pull`, then `analyze`.

And a correction from the session, because it changes what the next one can do: I reported in
the plan that `../mensores-overhaul` was *not on this volume*. It is, and always was — the
check was run from a drifted working directory. Nothing was verified against a toy program as
a result; every measurement in 5v is against the real 626-file corpus.


**5w. Built 2026-08-29 (fifth session): two points in time, and the change worklist's
engine.** Tom's decisions, taken before anything was written: the layer work leads with a
**change worklist** rather than an onion skin — what changed, as a list, with the picture
following; the search box becomes a **design-rule-2 pair** (sticky or scrolling, a
Setting, usage retires the loser); a program directory holds **one graph and one document
store per revision**, joined by `ATTACH`; and the f-string table fix ships **with** the
worklist rather than after it.

*The corpus first, and it is the reason the rest of the session happened.* Society was
pulled into two clean sister clones — `../society-2026-08-26` at `e2e658b4` and
`../society-2026-08-29` at `03ebbd93`, 27 commits apart — leaving `../mensores-overhaul`
frozen and never written to. `main` was checked and is stale since June and does not
contain the frozen commit, so the update is the feature branch.

**Point A′ reproduces point A exactly**: 30,209 calls, 3,950 boundary touches, 175 ways
in, all identical to the figures already recorded. The only difference is 4,733 routines
against 4,734, which is `mensores/_version.py` — generated by vcs-versioning, gitignored,
and present only in the working tree.

**A working tree and a clean clone are never a fair pair, and the first diff proved it
loudly.** 340 documents read as removed, and Society had removed none of them.

*Rule 57 came out of that.* 335 of point A's 2,381 documents were two stale agent
worktrees under `.claude/worktrees/`, holding a complete second copy of the project's
governance documents from May, under the old `.paul` name. `.claude` is admitted to the
document walk deliberately and for good reason; nothing scoped that admission below the
top level. The tool defended itself better than expected — the copy detector caught 303
and every consumer filters `duplicate_of` — but **the 32 that had drifted from their
originals were no longer byte-identical and escaped it**, putting ten definitions into
the glossary, `mensor`, `mensores` and `Society of Mensores` among them, from a directory
that is not the project. The marker is read off the disk (`os.walk` has already listed
it, so the test costs no `stat`) and is never a question asked of a VCS. Mensores'
corpus is 2,041 documents and 235 definitions; the budget table is corrected.

*Rule 56 came out of the session's own instrument, for the third time in two sessions.*
A mutation harness restored `revisions.py` in a `finally`, `git status` was clean, `grep`
showed the right line — and the next analysis wrote `graph@2026-08-29T23~43~25Z.db`.
Python revalidates a `.pyc` on the source's **(mtime, size)**, and a
one-character-for-one-character mutation changes neither when the restore lands in the
same second. **The size-preserving mutation is the dangerous one**: every other mutation
this session invalidated the cache by accident and hid the defect. The harness purges
`__pycache__` now.

**An f-string still names its table.** Migration 0028 creates `work_items` as
`f"CREATE TABLE {_TABLE} (...)"`, so the name interpolated to a placeholder and the
database map read 40 tables before the migration and 40 after — a table arrived and
nothing said so. The value was never missing: rule 19 records `_TABLE = "work_items"` as
a constant six lines above. Substituting is a **lexical binding in one file**, so rule 5
never arises — and it matters that it is scoped that way, because `_TABLE` names three
different tables in three migrations. Everything ambiguous is refused: a name bound more
than once, an attribute or a call, a placeholder carrying a conversion or a format spec,
a binding inside a function. Verified against the whole population rather than a sample:
**three interpolated `CREATE TABLE` statements in 628 files, all three now named**
(`work_items`, `session_claims`, `session_claims_v27`), nothing lost, and routines, calls
and boundaries byte-identical. Five artefacts came with it, each rule 17's own case —
`_PLUGIN_FILENAME = f"{_PLUGIN_MODULE_NAME}.py"`.

**The revision layout.** `revisions.py` owns the naming: `graph@<revision>.db` and
`docs@<revision>.db` beside one `source.db`. The colon becomes a dash — order-preserving,
so ISO stamps still sort chronologically as filenames — and **the identity lives inside
the file** as `meta.revision`, because a name is not an identity (rule 30) and a renamed
graph must still be able to say what it is. A legacy bare `graph.db` is **read** as the
one revision it is and never rewritten into the new shape: rule 20 again, and the same
destructive-fallback-in-a-uniform as rules 16 and 20. Readers resolve the newest
revision; a reader still resolving a fixed `graph.db` would answer "no graph — run
analyze first" about a store sitting right there.

`output/mensores` now holds both points, and sealing works end to end:

    2026-08-29T23:46:53Z   WORKING          628
    2026-08-29T23:46:24Z   FOR_COMPARISON   625   Society at e2e658b4 - 2026-08-26

**The diff engine, and the defect that measurement found.** `web/changes.py` builds four
bands over two `ATTACH`ed graphs, read-only with `mode=ro` — a diff is the most purely
read-only thing this tool does and must not leave a journal beside a sealed snapshot. No
comparison key contains a position, which is `make_id`'s argument one level down: put a
line in the key and one inserted import moves every fact in the file.

It measured **27 seconds**, and that number is the only reason the SQL got re-read.
SQLite's compound operators are **left-associative**, so

    SELECT a EXCEPT SELECT b UNION ALL SELECT b EXCEPT SELECT a

parses as `((A EXCEPT B) UNION ALL B) EXCEPT A`, which reduces to `B EXCEPT A` — **facts
gained, never facts lost.** A routine that stopped calling something would never have
appeared in the band at all. Nine guards passed over it, because every one of them added
something: rule 37 in my own tests, an hour after writing it into a comment. Three tests
for the losing direction now exist, and the fix **changed no number on this corpus** —
2,166 insertions against 80 deletions, nothing removed — which is exactly why it would
have shipped.

The 27 seconds was not the query. Cold it is 13 s, then 2.5 s, then **317 ms**: the
external volume, the same caveat this file already carries for the first search of a
session.

*What the pair actually says*, and it is a good first case:

| | |
|---|---|
| routines | 4,733 → 4,786 |
| added | **53** — 12 in `_work_item_registry`, 10 in `scriba._daemon`, 8 in `_orchestrator_claim_status` |
| removed | **0** |
| behaves differently | **18** — calls 17, boundaries 3, sql_ops 1, params 1 |
| edited, behaves the same | **15** |
| documents | +23, 5 modified, 0 removed |
| tables | **+1 `work_items`** · ways in +3 · constants +23 |

**Four of the eighteen have an unchanged body, and they are the feature's whole
argument.** `scriba._daemon.process_one` and three chaos drills stopped resolving
`queue.claim`. `StateIntentQueue.claim` is untouched and still there; what happened is
that `_work_item_registry.py` arrived carrying a **second** routine named `claim`, so the
call has two candidates and the resolver declines to guess (rule 5, `ambiguous=2`).
Adding a module cost four existing routines an edge, none of them edited, and `git diff`
shows a new file and says nothing about any of the four.

*Reported rather than decided.* `<module>` is created lazily, so adding a file's first
module-level comment makes `m.<module>` appear as an **added routine**. That is true —
the module scope now owns something — and it is the one addition a reader will not
recognise as one. Stated in a test rather than suppressed.

*Also owed:* the rendered markdown (`01-entrypoints.md` …) is not revision-named, so a
second analysis overwrites the first's map. The dashboard reads the databases, so nothing
is broken. And `--revision`, which `HANDOFF.md` records as the intended design ("a label
supplied from outside"), is still not implemented — both revisions here are stamped with
their capture time and carry the meaning in their label.

**Next: the worklist on screen.** The engine is built, guarded and measured; what is
missing is `/api/changes`, the navigator's Changes group, and the centre view — and the
pair selector, which now has two real revisions to choose between.


**5x. Built 2026-08-29 (fifth session, second half): the change worklist on screen.**

`/api/revisions` lists every point in time the program directory holds — state, capture
instant, label, and **whether a graph exists to read it with**, because a revision whose
bodies are held and whose graph was never written cannot be compared and saying so is the
difference between an empty answer and an honest one. `/api/changes` compares a pair,
defaulting to the two newest, and names both ends in its answer.

**Rule 58, and it is the session's best find.** The diff attached both graphs with
`mode=ro`, for the best reason there is: rule 20 says a read may refuse but never repair,
and one of the two is a snapshot somebody sealed. A read-only connection has no write
access to the `-shm`, so it cannot join the shared-memory WAL index the dashboard's own
handle maintains and re-derives it on every query. One `calls` comparison:

| | |
|---|---|
| `mode=ro`, dashboard running | **8,855 ms** |
| `mode=ro`, dashboard stopped | 242 ms |
| attached onto the connection that already had it | **137 ms** |

Same query, same files, same page cache. The trap is not the number, it is that **every
timing of this module before that one was taken with the server stopped**, where it is
242 ms and perfectly healthy. It would have been recorded as fast, shipped, and been 84
seconds behind the reader's first click. `Store(shared=True)` already existed for exactly
this. `PRAGMA query_only` buys the guarantee back and buys the slowdown with it, so the
guarantee is kept rule 25's way instead: a test asserting the module contains no write
statement, over its **string literals via `ast`** rather than by grep, because the prose
explaining why there are none contains the word `DROP`.

End to end: 317 ms warm, 13–28 s on the first comparison of a session, 1 ms cached. The
cold figure is the external volume reading a 31 MB graph the server has never touched —
13.1 s, 2.5 s, 317 ms across three runs — and is the caveat this file already carries for
the first search of a session.

**Rule 59, from the harness.** A mutation run scored **7/7** while one guard was already
failing on an unrelated attribute: the suite was red before any mutation, so every
mutation "went red" and the single genuine survivor was invisible inside the perfect
score. The honest number was 6/7. That is rule 43 in the instrument for the fourth time in
two sessions, and no two of the four look alike — two read pytest's output instead of its
exit code, one left the mutant running out of `__pycache__` (rule 56), this one measured
against a red baseline.

**The view.** A `Changes` navigator group — absent entirely from a program with one
revision, because a group that is always empty is a control that always fails — and a
centre worklist. Four bands in the order they are worth reading: what arrived, what went,
what behaves differently, and last and largest, **what was edited without changing
anything it does**. That band is listed rather than dropped, because leaving it out
entirely is a silent filter (design rule 1) — and it is last because a routine whose
internal computation changed is precisely what this tool exists not to report.

Every row carries the node id, so clicking one is the same `selectFromNav` every other row
makes: the stack lights its hop, the inspector fills, the trail records it and undo takes
it back, none of which this view had to build (rule 30 from the useful side).

**Three guards widened, each after being wrong first.**

* `_nav_kinds_built()` scanned only inside the `NAV_GROUPS` literal, so rows built by a
  group's `body:` function — the routine list, the code list — were invisible to it. It
  had never checked the navigator's most-clicked row kinds and passed the whole time by
  having nothing to compare. Rule 54 in the guard itself.
* A new loading-placeholder guard (rule 55's shape: `{loading: true}` that nothing
  overwrites renders "…" for ever) fired on `SEARCH`, which handles failure perfectly by
  building the shape into a local and assigning that. It checks for the handler now rather
  than for the shape of its result — a guard that fires on correct code is one nobody
  reads (rule 43). Its first version also passed against its own defect, because a greedy
  `\s*` before a negative lookahead lets the lookahead be tested against a space.
* A new written-control guard — the build-time counterpart to the runtime self-check,
  which cannot run in a test — named **four working controls dead**. `codeback`,
  `codedetach` and `codeopen` are keys of `CODE_ROUTES`, dispatched through a selector
  built at runtime so the literal never appears; `triaged` is read by the **stylesheet**.
  Rule 43 repeating exactly. It knows all four ways this codebase reads a control now, and
  states plainly what it cannot prove: that the read is *reachable*.

It found one real thing: `data-col` on the table header, written, rostered as wired, and
read by nothing at all. Removed rather than exempted.

**Not seen, and that is the gap.** Every claim above about the worklist is static —
guards, mutations, and the endpoints driven with `curl`. **Nobody has looked at it.** Rule
38: the automation tab gets no animation frames, and the three habits this project paid
for lead with *look, don't only test*. The layout, the band accordion, whether the four
figures read as figures, and whether a row is reachable by pointer rather than by
`element.click()` (rule 48) all want a real window.

**Owed, unchanged:** the rendered markdown is not revision-named, so the second analysis
overwrites the first's map; `--revision` is still unimplemented, so both revisions here are
stamped with their capture time and carry their meaning in a label.

### Two decisions taken 2026-08-30, before any of it was built

Both are Tom's, both were questions this file had been carrying, and both are recorded
here rather than acted on immediately because the session's first job is to *look* at
the change worklist.

**1. The navigator's search box is pinned, and collapses to an icon.** The question at
the last pause was whether to make it sticky, and the objection was the vertical budget:
~64 px of always-visible navigator, in a pane where nine group headings already cost
306 px open or closed. The answer resolves the trade rather than paying it. **Open, the
box is sticky and takes the real estate it needs** — input, its three switches, and the
answer line, all held in view while the list under it scrolls. **Closed, it is an icon on
the toolbar**, costing nothing. So the reader pays for the box only while they are using
it, and the state that costs 64 px is one they chose.

That is the same shape as design rule 24 — a pane folds and leaves a rail — with one
deliberate difference worth writing down, because rule 24 says in as many words that *an
icon rail is a puzzle*. It says that about a **pane**, whose identity a reader cannot
guess from a glyph; a search box is one of the few controls whose icon is genuinely read,
and it collapses to a *toolbar*, which is where a reader already looks for one. If it
turns out to be a puzzle in use, the remedy is a labelled control rather than an
un-pinning, because scrolling away was the defect being fixed.

It also settles what the collapsed state must not do: **a search with an answer on screen
may not collapse into silence.** Rule 1 — a filter that says nothing about what it removed
is a filter the reader mistakes for the whole. The icon has to carry that the search is
live, and the answer line has to survive the fold.

**2. `m.<module>` is a language feature, and is reported as one.** The question was
whether the synthetic module routine appearing — because a file gained its first
module-level comment — should be reported as an added routine, or suppressed as noise.
Neither. **It is a fact about Python**, and the tool's reader reads code without writing
it, so the thing that serves them is not a hidden row and not a bare one: it is the row
*with its explanation attached*.

Three consequences, and the third is the reason to decide it now rather than when it
irritates someone:

- It is **not noise**, so it is not filtered. A file acquiring module-level behaviour it
  did not have is a real change, and design rule 1 forbids removing it quietly.
- It is **a curiosity**, in design rule 15's sense — a doorway rather than a problem. A
  reader who has never written Python does not know that a module body runs at import,
  and this is the row that teaches them. It carries extra documentation, not a badge.
- It is **language-scoped**, and must be built that way. Every extractor emits the same
  `FileFacts`, and the resolver knows nothing about any language; a rule that says *this
  particular appearance means something specific about how this language loads code*
  belongs beside the extractor that produced it, tagged with its language, so the next
  extractor either supplies its own or supplies none. **Do not special-case Python in the
  diff.** Swift's answer will not be Python's, and a hard-coded one here is a false claim
  about every language added later.

**Research owed before building it:** how other tools present a construct that exists in
the graph because the language put it there rather than because an author wrote it. That
is a real question with prior art — it is the same problem as a synthesized default
constructor, an implicit `main`, a generated accessor — and the answer decides whether
this is one row with a note or a small family of them.

**5y. Built 2026-08-30: the change worklist, looked at for the first time.** 5x said it
plainly — *nobody has looked at it* — and every claim in it was guards, mutations and
`curl`. Looking found six things in an hour. **None of them was visible to any check, and
four of them meant the feature did not work at all.**

*What was wrong.*

1. **The worklist could not be reached.** A closed loop: `changeList()` builds the row
   that emits the `changes` route, and only once `CHANGES` is loaded; `CHANGES` was only
   ever loaded *by* that route. The control that starts the comparison existed only after
   the comparison had started. Opening the Changes group gave "Not compared yet." with
   nothing to click — eighty-seven routed controls on the page, none emitting `changes`.
   The group declares `onOpen` now, run by `setGroupOpen` from the table rather than from
   a branch naming it. Rule 55's companion by a route its own precedent did not cover.

2. **Once compared, the navigator never learnt.** `loadChanges().then(render)` — and
   `render()` repaints the centre, inspector, trail and filters, never the navigator. So
   the comparison arrived, the worklist painted in full, and the group beside it went on
   saying "two points in time — open to compare them" with a blank count. One question,
   two answers, drifting on the first click (rule 51). `refreshChanges()` is the one door
   both callers use.

3. **Every routine name was three pixels wide.** The rows reused `.wl-item`, whose grid is
   `.1875rem 1fr auto auto` — four columns written for the **anomaly** worklist, the first
   of them a `.wl-stripe` severity bar. A change row has no severity and emitted two
   children, so the *name* was laid into the 3px stripe column and `text-overflow:
   ellipsis` erased it, while the module path took the `1fr` and 786 pixels. Measured: a
   title of `scrollWidth` 188 inside a box 3px wide, on all 86 rows of all four bands.
   Rules 44 and 48's family — wired correctly to a stylesheet that could not carry it.

4. **Clicking a row did nothing.** Rows carried `class="wl-item" data-nav="chg"
   data-navid=…` while the delegated handler selected `.nav-item` — a **class**, when
   `NAV_ROUTES` is keyed on `data-nav`. Adding the class to one row live made it work
   exactly as 5x describes. The handler selects on the attribute now, which makes the
   defect unreachable rather than merely detectable.

5. **"Ways in +3" printed raw node ids** — three sixteen-character hashes where Tables
   printed `work_items`. `PRESENCE` keyed entrypoints on `id` (correctly: `name` is not
   unique there) and *printed the key*. Key and label are separate columns now.

6. **The trail step was the whole row** — "claim_status_cmd mensores.cli.scribe
   boundariescallssql_ops" — because `pushTrail` falls back to the button's text with no
   `.navlabel` present. There is one on the name.

*And one the fix itself created, which is the most useful thing here.* Broadening the
click handler from `.nav-item` to `[data-nav]` immediately reported `nav "on" has no
route` on the first page load. `PANELS` writes each pane's fold state as `data-<attr>`
from a name of its own, and the navigator's was **`nav`** — so `.body` carried
`data-nav="on"` as grid-track state while every routed control carried `data-nav="chg"`,
`"pkg"`, `"routine"` as a route. **One attribute, two unrelated meanings**, harmless only
for as long as the handler happened to match a class instead; on the attribute, `.body`
became the nearest routed ancestor of every stray click in the application. Rule 47's
companion — one channel meaning two things — a layer below where that rule found it. The
track is `data-navtrack`, and a test keeps the two sets disjoint.

Found by widening a check and then **reading the console**, which no test does.

*The one judgment, and it is now a Setting.* `.wl-list` capped a band at `32rem`, so the
Added band — 53 rows, the largest and the first thing anyone wants — was a 512px scroller
nested inside the page's own 401px one. Rule 8 decides the default: a reference list is
never bounded and there is no mandate to save space, so bands run their full length and
the page is the only scroller. **`bandScroll` turns the caps back on** for a reader who
would rather compare the four bands than read one through — design rule 2, counted, and
retired later on evidence. Measured both ways: capped, the Added band is 512px of a
1,505px list inside a 2,018px page; uncapped it is 1,507px inside 3,015px and nothing
scrolls in place.

*What the guards cost.* Three written, then a fourth for the collision, and **run against
the defects they were written from**: 8 of 8 mutations killed after one was fixed. The
survivor was mine — a containment check taken over "200 characters after `.chg-title`",
which passed against its own mutation by reading the `min-width: 0` on the `.chg-meta`
rule three lines below. A guard vouching for its neighbour, rule 37 inside a check written
*because of* rule 37. And `_nav_kinds_built()` then failed on the **comment explaining the
collision**: it read raw source, so prose naming an attribute counted as markup writing
one. That is the third guard in this file to trip on the sentence describing the thing it
checks; `_code()` exists for exactly that and this helper predated it.

*What could not be driven, and how it was verified instead.* The extension's click
dispatch died mid-session — pointer *moves* reached the page and `click` events did not,
in two tabs, with `elementFromPoint` still answering. So rule 48's two halves were taken
separately and are reported as two claims: **reachability** by `elementFromPoint` at each
control's centre (chip, "the whole comparison" row, a worklist row, the new toggle — all
four reachable), and **wiring** by `element.click()`. That is weaker than one pointer
doing both, and it is said here rather than glossed. The rest was looked at: names now
render at 196–228px and nothing is clipped, the group reads `71` and its note, the fold
still collapses the track to a rail and back, and the self-check prints *every control is
wired*.

*Owed, unchanged:* the rendered markdown is not revision-named; `--revision` is still
unimplemented. **Next: the pair selector** — two revisions exist and `/api/changes` is
still hard-wired to the newest two.

**5z. Built 2026-08-30: choosing which two points in time.** Tom's design, settled at the
keyboard before anything was written, and it started with him asking what the toolbar's
revision control was *for*.

*The two decisions.* **A pair has a reading end.** `revB` is the point being read — cover,
routine list, code browser, glossary and stack all show that one — and `revA` is the other
end of the comparison. So "what am I looking at" keeps one answer while a comparison runs,
which it could not if every view tried to show two points at once. The alternative, every
view learning to diff, is a much larger idea and would change what those views *are*.
And **pair first, then the switch**: the selector is client-side, because `/api/changes`
already took `from` and `to`; making the reading end actually switch is the server work
and is next.

*One control, not two.* It was briefly two selects, one per end, and driving it settled the
question: a `<select>` is as wide as its longest option, and these are filled with a label
and an instant apiece, so the pair came to **448px of a 1,278px window** and pushed the
search box and the whole right-hand group off the screen. They did not overflow, they
displaced everything beside them. One control whose *options are the pairs* — `current · on
its own`, `current ← Society at e2e658b4 · 2026-08-29 23:46:24` — is narrower, reads as the
answer to "which two am I looking at", and is what Tom asked for in the first place.

*What looking found, and none of it was visible from the code.*

- **Both revisions read `2026-08-29`.** The id is when the snapshot was **captured**, not
  when the code is from: these hold a Society tree from the 26th and one from the 29th, and
  both were captured on the evening of the 29th **twenty-nine seconds apart**. Abbreviated
  to the day the two menu entries were identical; shortened to the minute they were still
  identical, `2026-08-29 23:46`. Each shortening looked reasonable until it sat beside its
  neighbour. The whole instant is shown, and the *label* is where "which point in time is
  this" actually lives.
- **The chosen pair never survived a reload.** `revA`/`revB` went into `PERSISTED` and not
  into `DEFAULTS`, and `loadSettings` merges only keys `DEFAULTS` declares — so the choice
  was written to storage on every change and dropped on every load. `localStorage` held the
  right answer the whole time and nothing ever read it.
- **The guard written for that immediately found three more.** `searchCase`, `searchWord`
  and `searchRegex` have the identical defect and have had it since the search was built:
  `shell.js` says in a comment that they are persisted, and they are not. The invariant is
  **`PERSISTED` ⊆ `DEFAULTS`**, and nothing had ever checked the two lists agreed.
- **The notice about a dropped revision went to a surface nobody had opened.** A stored
  revision that no longer exists is dropped and said out loud — except `state.navNote` is
  rendered in exactly one place, the graph HUD's count line, which does not exist until the
  reader mounts the graph. Correct drop, invisible explanation: the defect it was written to
  prevent, wearing the other uniform. It is the Changes group's note now.
- **And that notice then cleared itself at random.** Three of `changeNote`'s four returns
  prepended it and the success path did not, so it survived every state except a working
  comparison — which looked like deliberate behaviour and was an accident. It is cleared
  where the reader answers it, in the control's own handler.
- **`data-rev` was a marker nothing read.** The control is found by its id. Removed rather
  than exempted, the same call `data-col` got.

*The source directory shows both trees*, which was Tom's own observation and is backed by a
fact: the two revisions genuinely have different roots, `society-2026-08-26/src` and
`society-2026-08-29/src`. One path shown while two points are in play names one end and
implies it is both. `/api/revisions` carries `source_root` per revision now, read from each
graph's own `meta` — and the served one is answered from the connection already open, because
a second read-only handle to a database this process holds open is rule 58's 36x and this
route is asked at boot.

*Not built, and it is Tom's ask.* Selecting a version *from* the source-directory control.
A path is a label, not a key: analyse the same tree twice and both revisions carry the same
one, and a menu with two identical rows selects nothing in particular. It can be done backed
by the revision id — which is exactly the key-and-label separation the presence lines needed
— but it wants a decision about what two identical rows should look like.

*Guards.* Four new, plus the `PERSISTED ⊆ DEFAULTS` one, each run against the defect it was
written from: **7 of 7** after one was strengthened. The survivor was mine again — "does
`chosenPair` mention the check" passed when the check was dropped from one of its two ends,
because a containment test cannot tell one end from two. That is rule 37 inside a guard for
the second session running.

*Verified by driving it.* The chosen pair is what is requested
(`/api/changes?from=2026-08-29T23%3A46%3A24Z`, not the default); "on its own" issues **no**
request and clears the group; the choice survives a reload; a planted retired revision is
dropped, explained, and the explanation clears when answered; the toolbar fits its window
again with the search box and the right-hand group on screen; and the self-check prints
*every control is wired*.

**Next: the reading end.** `serve()` opens one graph at boot and builds the payload, the
628-file code list, both vocabulary lanes and the cover from it — the whole of the measured
10.2 s start. Switching the point in time the screen displays means paying that per switch
or holding two sets live, and that is the decision the next chunk opens with.

### The next chunk's framing, from Tom at the 2026-08-30 pause

> *"We need to be able to compare to an older or newer version, by analysis. This isn't
> just taking github as the source of truth, it is our own analysis so it works with any
> version control or just an old source code copy that was never properly documented."*

This sharpens *Version control must stay pluggable* above rather than repeating it. That
section says DunneFlow must never shell out to a VCS to fetch code, and names Lore,
Perforce and a nightly cron as the reason. Tom's case is stronger and is the one to build
for: **no version control at all.** A directory of source somebody hands you, with no
history, no documentation and no way to ask where it came from — and the question is how
it differs from what is running now. That is his own experience and it is the case the
comparison has to serve, because it is the case where nothing else can answer.

Two consequences, and the first is concrete enough to break something today.

**Capture order is not code chronology, and the pair is currently ordered by capture.**
`revisions.known()` sorts by *filename*, which encodes the instant the snapshot was taken,
newest first; `_r_changes` then takes `graphs[0]` as the later end and `graphs[1]` as the
earlier one. Analyse an old copy this afternoon and its capture instant is the newest one
in the directory, so it becomes the *later* end — and the worklist reports the old code's
absences as **added** and its presences as **removed**, the whole comparison inverted,
confidently, with no symptom. This is read from the code and the ordering is certain; the
run that demonstrates it has not been done, and it is the first thing to do next.

It is also today's finding one level up. The revision id is when the snapshot was
*captured*, not when the code is from — the two revisions here were captured twenty-nine
seconds apart and hold trees three days apart — so **which end is earlier is a fact about
the source, and nothing in the store records it.** `--revision` is where a reader supplies
it and is still unimplemented; a label ("Society at e2e658b4 - 2026-08-26") carries it
today only as prose.

**And "older or newer" means the reading end can be either.** The settled model is that a
pair has a reading end and the map shows it; nothing in that says the reading end is the
later one. Reading an old copy and comparing it forward to the current tree is the same
feature pointed the other way, and it is the shape Tom's case actually wants: *this is what
we were handed — what has happened since?*

**6a. Built 2026-08-30: stored paths are relative, and the root is not recorded.** Tom's
ask, arriving in the middle of a conversation about the reading end and displacing it —
correctly, because it turned out to be underneath the layer work rather than beside it.

*His three reasons.* An absolute path leaks information about a system; users move files
to manage disk space; and copying a directory from one system to another breaks
everything. All three are about a program directory being a thing somebody can **hand
over**, which is what this tool produces.

*The fourth, found by surveying before proposing, and the one that mattered here.* Two
revisions read from two different trees give the same file two unrelated keys. Joined as
stored, Mensores' pair read **0 identical, 0 modified, 628 added, 625 removed**. Stripped,
it is **613 identical, 12 modified, 3 added, 0 removed** — one query, zero body reads,
because the sidecar is content-addressed and a hash comparison *is* the file-level diff.
The one question two revisions exist to ask could not be asked.

*A fifth, in the store nobody can rebuild.* The tree a revision was read from was recorded
**only** in `graph.meta.source_root` and `docs.meta.docs_root` — the two stores that get
discarded on a fingerprint change — while the bodies live in the one that never is (rule
25). One schema bump from unrecoverable, for exactly the sealed snapshots sealing exists
to protect.

*The origin was one line, and it had been announcing itself for as long as it existed:*

```python
rel = str(path)                     # named `rel`, holding the absolute path
module = module_name(path, root)    # the next line already computes the relative form
```

`FileFacts.path` flows through one choke point, `store.write_file_facts()`, into eighteen
tables. `extractors/docs/__init__.py` had the identical shape — `rel` computed, `str(path)`
stored.

*Three things made it cheaper than it looked, and all three were checked rather than
assumed.* **Identity is safe**: `make_id` derives from module and qualname and
`module_name` was already root-relative, so a move changes no id and this is a
representation change, not a re-interpretation. **Nothing at read time opens a stored
path**: bodies come from `source.db` by content hash. And **the strip already existed ten
times** — nine identical `_rel()` clones plus `_short()` — so storing the relative form
was a *net deletion*. Those clones were not the harmless no-ops they looked like:
`Path("a/b.py").resolve()` resolves against the working directory, so run from inside the
analysed tree they would have silently prepended the intervening directories to every path
on every page.

*Tom's two decisions.* **Migrate in place** — a sealed snapshot is kept precisely so it
can be read after its tree is gone, and re-analysis would orphan exactly those. And
**record nothing**, his reasoning being that only the repo-named directory is stable while
the rest carry dates or version suffixes and are ephemeral, so compelling the reader to
name one is expected. Asked whether to build a binding now or defer it, he chose defer:
nothing opens a file from disk, so nothing needs one.

*What it cost and what it bought.* `dunneflow migrate` rewrote **115,546 paths across five
stores in 1.2 s**. A move became free — **0 cache hits and 628 files pruned** under the old
key, **628 cached and nothing pruned** under the new one, measured both ways rather than
argued. And the acceptance test that no unit test can give: `output/mensores` copied to a
path that has never existed on this machine and served from there — cover, routine list,
code browser, search, citations, both revisions and the change worklist, no root bound and
none needed.

*Rules 60, 61 and 62.* **61 is the one to read.** `entrypoints_from_packaging` reads
`[project.scripts]` and writes rows directly, never through the extractor — so making the
extractor relative moved 54,746 rows and left **four** absolute, in the one place
`CLAUDE.md`'s own ground truth lives. 54,746 of 54,750 looks exactly like success, and no
unit test covered it because the sample program has no `pyproject.toml`. Found by scanning
**every column of every table in every store** for the analysed root rather than the
columns the change had touched. The same scan proved the only absolute strings left
anywhere are paths quoted inside Society's own handoff documents, which are content and
stay whole (rule 8). Its companion: those rows land in `COALESCE(r.file, e.file)`, the same
column as a routine's file, and a `src/` layout puts `pyproject.toml` *above* the code — so
the answer is `../pyproject.toml`, and the migration needed `relpath`, not a prefix strip
that cannot express `..`. The first version stripped only, and reported a five-figure
success over four rows it had missed.

**62** is the delicate one and is written down as such: editing the extractors moves
`rules_fingerprint()`, so a correctly migrated graph is one no reader will open. The
migration re-stamps `meta.extractor` — defensible **only** because it performs exactly the
transformation the new fingerprint stands for, and gated on one specific named prior value
so it never becomes a general licence. The *paths are relative* marker is its own meta key
rather than the schema version, because bumping that discards the graph, which is the
outcome migrating in place exists to avoid.

*Two defects found by looking, neither caused by this work.*

- **The cover has reported `0 lines` for every program since revisions landed.** `_lines`
  asked `WHERE p.revision = ''` — the legacy revision, from before a snapshot had a name.
  Mensores is 186,786. Nothing failed and nothing was empty: a zero on the first screen
  reads as "this program has no source", which is a claim and a wrong one. Found by serving
  a copied program directory and reading the cover.
- **The `source directory` control was filled by nothing and listened to by nothing.** It
  is a **readout** now — `not bound — none needed here` — and becomes the binding when
  something genuinely opens a file from disk. A `<div>`, with no `aria-expanded` to toggle
  and no pointer cursor, because a control that looks pressable and changes nothing is
  design rule 16's defect.

*And one I introduced, which is the most useful thing here.* Removing the served root left
`applySourcePath()` reading `STATS.source_root` and writing `""` into that readout on every
load — **rule 44 exactly**, an empty box beside a label still reading SOURCE DIRECTORY,
nothing thrown. I had cleared it as safe on a `grep` of `shell.js` that returned nothing.

**`grep` had silently decided the 412 KB file was binary.** `file` calls it UTF-8 text;
without `-a`, `grep` answered "no matches" for `srcPath`, `getElementById` and
`source_root`, all three of which are in it. Rule 43 in the instrument for the fifth time
in three sessions, and the cheapest one yet to have avoided — the fix is `grep -a` and
treating "no matches" in a large file as a claim to check. Caught by driving the page and
looking at the toolbar, which is the habit that has now paid for itself in three
consecutive sessions.

*Guards.* A new `tests/test_migrate.py` — fifteen — plus two on the readout. Run against
the defects they were written from and against half-working versions, with the baseline
proved green first (rule 59): **9/9** and then **5/5** mutations killed. Two of the readout
guards had to be fixed before they caught anything: one tripped on the prose explaining the
defect (`_code()` blanks comment *lines*, and a `/* */` block with plain indented
continuation is invisible to it — the fourth time in this file), and one matched a selector
only where it sat immediately before its `{`, so it missed
`.srcpath[aria-expanded="true"] .srcpath-v { … }`, which is the exact shape that was there.
CSS now has its own `_css_code()`: with no template literals and no nested comments, the
whole-block strip that is unsafe in JavaScript is exact there.

*Owed, unchanged:* the rendered markdown is not revision-named; `--revision` is still
unimplemented. **Next:** the ordering — `--revision`, an explicit direction control, and
capture order stated *as* capture order — then the reading end, then the code viewer's diff
view, whose file-level half the pairing above has already made free.

### Paused 2026-08-30, after the path work

`output/mensores` is migrated and verified; working tree clean; all three gates green.

**The next chunk is the ordering, and it is a wrong answer on screen today.** Tom settled
its shape this session, in answer to "who says which of two trees is older":

> *"I agree with 3 — Both. If the reader doesn't declare, we do our best and say that, and
> allow them to choose otherwise for a future run if they don't like the results. Sometimes
> the code will be so poorly documented that the user just can't tell which is older or
> newer — that's ok. The difference is the important part, and we can call that out on
> every screen."*

So: the reader may declare, the tool defaults to what it can actually see, and it never
claims more than that. Concretely, and in the order they unblock each other.

1. **Demonstrate the inversion.** Read from the code and still not run:
   `revisions.known()` sorts by *filename* — the instant the snapshot was captured, newest
   first — and `_r_changes` takes `graphs[0]` as the later end. Analyse an old copy this
   afternoon and it becomes the *later* revision, so the worklist reports the old code's
   absences as **added** and its presences as **removed**, inverted, confidently, with no
   symptom. Analyse `../society-2026-08-26/src` into a scratch copy of a program directory
   that already holds the 29th and read `/api/changes`.

2. **`--revision` on `analyze`.** Still unimplemented, and it is where a reader declares
   which point in time a tree *is* — as opposed to when it was captured, which is all the
   store records. The two Mensores revisions were captured twenty-nine seconds apart and
   hold trees three days apart, which is the whole argument in one line.

3. **State capture order as capture order.** The menu must say "captured first", never
   "earlier": one is a fact this store holds and the other is an inference it cannot make.
   Design rule 1 — a claim the tool cannot support is a filter on the truth.

4. **A direction control on the pair.** The pair becomes `A → B` with reversing as a
   control rather than a re-analysis. This is the same control the reading end needs, which
   is why it comes before it rather than after.

**Then the reading end**, unchanged and still opening with its cost decision: `serve()`
builds the payload, the 628-file code list, both vocabulary lanes and the cover from one
graph opened at boot — the measured 10.2 s — so switching the displayed revision means
paying that per switch or holding two sets live.

**Then the code viewer's diff view.** Tom asked for it this session and said it can wait.
It is **two lanes and only one of them is faked**:

| Lane | What it diffs | How |
|---|---|---|
| **Source** | the bodies, line by line | genuine `difflib` — `source.db` holds both revisions' bodies whole |
| **Facts** | routines, calls, boundaries, SQL, params | `changes.py`, already built |

The second is the one nothing else can give you — `changes.py` says so in its own preamble,
and the four routines that stopped resolving `queue.claim` without being edited are
invisible to a text diff. The **file-level** half is now free: 613 identical, 12 modified,
3 added, 0 removed from one query with zero body reads, which also says which twelve files
are worth the expensive lane.

**One question of Tom's is open and was never answered.** *"The difference is the important
part, and we can call that out on every screen"* — I asked what shape that takes (a
persistent strip in the toolbar naming both ends and the direction, visible in the glossary
and code browser as much as the worklist; or something lighter that appears only where a
number could be misread) and the conversation moved to absolute paths before he answered.
**Ask before building it.**

**One earlier ask is now reshaped rather than owed.** *Selecting a version from the
source-directory control* was on the list; that control is a **readout** now and a path is
not a key, so the ask should be put back to Tom rather than built as originally stated.

*Still owed, unchanged:* the rendered markdown is not revision-named, so a second analysis
overwrites the first's map; the navigator's search box pinned-when-open / icon-when-closed
(decided 2026-08-30, not built); `m.<module>` as a language feature, with research owed on
prior art first; the worklist's two jump buttons; the two vocabulary-lane
precision defects; per-plate sphere scaling and stack orientation; packaging as a binary.
One question never answered: **what is an occurrence for LOST_EDGE** — the 142 callers, or
the rival definitions? 93 of Mensores' 106 findings are LOST_EDGE, so it decides the
feature. And the blank-graph fix (rule 49) is still reasoned and guarded rather than seen.

*One practical note.* The pre-flight backup of the un-migrated stores was written to this
session's scratchpad, which is ephemeral and will be gone. That is acceptable and is said
rather than hidden: the migration is verified, idempotent, and re-derivable — both source
trees still exist, so the worst case is a re-analysis rather than a loss. `source.db`'s
bodies were never at risk; `prune_missing` leaves blobs alone and the migration only
rewrote the `paths` mapping.

**6b. Built 2026-08-30: base and compared — two directories, and no claim about which is
older.** Tom's decision, and it replaces the question the previous pause was going to
answer rather than answering it.

> *"I don't want to show the pair as 'captured first' or 'written first'. We just have a
> 'base version' and a 'compared version', and that second version might be higher or
> lower, doesn't matter. It might even be identical, and we'll report that there are no
> differences found."*

The four-step ordering plan is **superseded**. Step 3 — "state capture order as capture
order" — is gone and better than gone: it was an honest label on a claim the tool should
never have been making. There is no *earlier* end and no *later* end. There is the
version the map is showing and the version it is held against.

*What the vocabulary was, and what it is.* Not `earlier`/`later` — those never reached a
reader. Four overlapping layers: `build(before, after)` with SQL aliases `A`/`B`; the wire's
`from`/`to` and `routines_before`/`routines_after`; the bands `added`/`removed`; and the
client's `state.revB` (reading end) and `state.revA`. All of it is now `base` and
`compared`, and the presence bands are **`only_in_base` and `only_in_compared`** — named
for *where a thing is*, which is a fact, rather than for what befell it, which is not.

*The correction that mattered, and it inverted my first reading.* `state.revB` was already
the base concept, so `changes.build`'s 36x serving-connection ride (rule 58) **already rode
the base** and needed no re-pointing. But it also means today's `added` band was
*"in base, not in compared"* — which under the settled default polarity is **deleted**. The
labels were correct only because the default pairing happened to make the base the newer
capture. That accident is exactly what this removes.

*Added and deleted are an interpretation, and the store does not hold one.* The polarity is
`state.comparedIsNewer`, default true — Tom's default, and the case the feature exists for:
*here is the copy somebody handed me, what has happened since?* `diffWords()` turns it into
the two words the whole page uses, so no view can label one set two ways (rule 51). **Driven
and measured: flipping it costs zero fetches** — 53 deleted becomes 53 added, in the
navigator and the centre pane together, with no query. That is the whole payoff of naming
the sets by side.

*The strip.* Its own `.app` grid row, because it is about the whole screen — the navigator's
counts, the inspector's figures and the code browser's lines all belong to the base, and a
band inside `.centre` would be a claim about the middle only. Not the toolbar: that is a
single-line flex row whose width caps exist because two unbounded selects once made a
1,278px window carry a 2,068px toolbar. **Always present**, including on a one-version
program, where it reads *"on its own, nothing compared"* — Tom's call, and the right one: an
absence must never be the thing that tells a reader they are not comparing.

It carries four claims of different kinds, and keeping them apart is the point: which two
versions (a fact), what each asserts about its own version and at which tier (design rule
13), the reader's assumption (stated as one, and clickable), and **what we can actually see
about capture order, as a plain observation beside the assumption and never as a correction
to it.** We may infer, so long as we say we did.

*Version detection, in tiers.* `pyproject.toml [project] version` reusing the entrypoint
reader's parse — `os.path.relpath`, so a `src/` layout honestly says `../pyproject.toml`
(rule 61); then a module-scope `__version__` with its file and line; then a guess off the
directory leaf, marked `INFERRED` and rendered faint and italic so it cannot pass for
something read. `__version__` is read by `resolve/version.py` directly rather than out of
the constants table, **routing around the deliberate dunder filter rather than removing
it** — that filter is right for the glossary, and its own comment says why.

Verified against the corpus rather than assumed: Society's `[project]` genuinely has **no**
`version` key and no module-scope `__version__` — read, not guessed — so both its versions
fall to the inferred tier, and DunneFlow's own tree correctly yields `0.1.0` from
`../pyproject.toml` at the declared tier.

*The leaf of the tree, recorded — and documented.* `revisions.tree`, an additive column,
add-only (rule 25 means this store is never rebuilt, so there is no re-analysis that would
repair a missing column). Two versions of one program are two directories, so the leaf is
what a reader recognises them by. Distinct from `label`, which is what a person called a
snapshot at `seal` time: one meaning per column, so `seal --label` cannot overwrite where
the code came from. `README.md` gains **"What a program directory contains about your
machine"**, because a thing built to be handed over must say what it carries.

*Two defects found by running it on real code, neither visible to any test.*

- **A read-only open of an older sidecar reported a two-revision program as holding no
  revisions at all.** A read may refuse but never repair (rule 20), so a read-only open
  does not run the additive migration — and the dashboard opens the sidecar read-only every
  time it starts. Naming `tree` unconditionally made the SELECT raise, a pre-existing
  blanket `except sqlite3.Error` turned that into `rows = []`, and state, label, capture
  instant and file counts all came back blank with **no error anywhere**. Rule 49 exactly: a
  fallback yielding a plausible value hides the failure it was written for, and it consumed
  the evidence on its way past. `revisions()` now reads the columns the sidecar has. Found
  by reading the served JSON and noticing four fields had gone empty since the previous
  request — no test compares two runs of a server.
- **The recorded tree was `src`.** `target.name` for a `src/` layout is the string `src`,
  which names every src-layout program ever analysed and therefore identifies none of them.
  The leaf that identifies a tree is the **package root's**, found by the same upward walk
  `pkg_root` already did — hoisted above the sidecar open, which also retired a duplicate
  walk. **Invisible to every fixture in the suite, because none of them has a `src/` to be
  wrong about**; visible on the first real run.

*Guards.* `test_version.py` (11), plus tests for the tree column, the read-only path, and
the vocabulary itself — `test_no_band_or_count_is_named_for_a_point_in_time`, asserted over
the **keys the answer carries** rather than over the source, because what misleads a reader
is what reaches them. Run against the defects they were written from with the baseline
proved green first (rule 59): **5/5 mutations killed**. One survived the first attempt —
renaming `routines_base` to `routines_after` — and the guard was the weak half, not the
mutation: it tested exact key names, and `routines_after` *contains* the forbidden word
rather than equalling it. It tests the parts of each name now.

*Verified on the corpus.* Same totals under the new key names — 53 / 0 / 18 / 15, 4,786
routines base against 4,733 compared, `work_items` as the new table — with
`rode_serving_connection: true`, so the rule 58 fast path still fires. Swapping the ends
explicitly inverts the two presence bands and correctly reports `rode: false`, because the
base is then not the served graph. A fresh analysis of `../society-2026-08-26/src`
reproduces the recorded ground truth exactly: **30,209 calls, 3,950 boundary touches, 175
ways in**, in 74 s. The runtime self-check prints *every control is wired*.

*Driven in a real window*, which is where all of this was checked: the strip on one version
and on two, `elementFromPoint` on the assumption control (rule 48 — wiring and reachability
are different claims), the flip with `fetch` counted, and the console read.

**The flagged consequence, and it is on screen.** With the default pairing and the default
polarity, Mensores' 53 genuinely-new routines render as **deleted**. That is the assumption
doing its job visibly rather than a defect — and the strip says both *"assuming the compared
version is the newer one"* and *"captured: compared first"*, so the reader has what they need
to flip it. **But there is now a better default available and it is Tom's call, not mine:**
when both versions carry a version — even an inferred one — comparing them is "a more
obvious version available" in his own words, and the default could be derived from that and
said to be derived. He set the default explicitly, so it stands until he moves it.

**Not built, and it is the seam this stops at: switching the base.** Tom chose *rebuild
every switch* (one payload set live, always). `serve()` builds the payload, the 628-file
code list, both vocabulary lanes and the cover from one graph opened at boot, and `_Handler`
holds the payload from construction — so a base switch is a server-lifecycle change (swap
the store under the lock, rebuild the payload in place, invalidate the diff cache) plus a
client progress state and its guards. `revB` was never settable from the UI, so this is new
capability rather than a rewiring. Everything else in the chunk stands without it: the
default base is the served graph, and `_r_changes` now defaults from `self._live.graph_db`
rather than `graphs[0]` so the map and the comparison cannot disagree about which version is
on screen.

*The scratch corpus used for this was removed* — 250 MB, and Tom manages disk. Rebuild:
`analyze ../society-2026-08-26/src --name verifycheck`, `revisions output/verifycheck --seal
--label "handed over, undocumented"`, `analyze ../society-2026-08-29/src --name verifycheck`.
It is the only program directory whose revisions carry a `tree`; `output/mensores` predates
the column and honestly reports empty for both.

**6c. Built 2026-08-30: the default is read from the versions, not guessed.** Tom's call,
taken on the evidence of 6b's flagged consequence — with a fixed default, Mensores' 53
genuinely-new routines rendered as *deleted* on first open.

His own rule decided it: *"we may infer a version from a directory name or date, but have
to say that we did. It would only be used when no other, more obvious version is
available."* Two versions that each state a version **are** more obvious than a blind
default, so they decide — and the strip says which of the two happened.

*Three states, and the third is the point.* `comparedIsNewer` is `'auto' | 'yes' | 'no'`,
not a boolean. `auto` re-derives when the reader moves to a different pair; an explicit
choice made about *one* pair would otherwise be carried silently onto another, which is
rule 51 with the reader's own decision as the thing that drifts. Design rule 24's shape —
an automatic rule may decide, and an explicit choice outranks it. The control cycles
auto → newer → older → auto, and **the label always states the state in full**:

```
the compared version is older — from their versions (inferred)
you chose: the compared version is newer
assuming the compared version is newer — no versions to compare     ← dashed border
```

*The comparison is the server's, and that is not fussiness.* `/api/revisions` carries
`version_kind` and `version_key` per version; the page only compares two keys of one kind.
Two reasons, both of which a template would get wrong. **`1.10.0` sorts below `1.2.0` as a
string** — the oldest version-sorting bug there is. And **a date and a release number are
both orderable and are not orderable against each other**: the keys are integer tuples and
would compare perfectly happily, so ranking `1.2.3` against `2026-08-26` is a confident
wrong answer with no symptom. The kind travels with the key so the page can refuse.

*Two refusals, both rule 1.* A prerelease suffix makes a version un-orderable — `1.0.0-rc1`
precedes `1.0.0` under semver's own rules and follows it under other conventions in the
wild, so picking one would state an order the tool cannot defend. And two **equal**
versions rank neither end rather than falling through to a direction.

*Driven on the real corpus.* `society-2026-08-26` against `society-2026-08-29`, both
versions inferred from their directory leaves: the strip reads *"the compared version is
older — from their versions (inferred)"* and the worklist opens on **53 added** with no
click. Cycled through all three states and back, each stating itself in full; the choice
survives a reload, which is the defect that bit `revA`/`revB` and the three search switches.
On `output/mensores`, whose versions predate the column, it falls back and says so with a
dashed border and *"no versions to compare"*.

*One wording defect found by driving it.* In the assumed state the button offered *"Click
for: the compared version is newer"* — which was already the direction in force, so the
control read as a no-op. From `auto` what the next click changes is the **basis**, not the
direction, and it says that now.

*Guards.* Four new ones, mutation-tested at **6/6 over a proved-green baseline** — after
the first run scored 5/6. The survivor is worth keeping: replacing `: derived` with
`: true` leaves the `derived === null` test standing, so a guard asking "does `derived`
appear on the auto path" passed while the value was thrown away. It strikes the null-test
out before looking now. **That is the second time in this session a guard was the weak half
rather than the mutation** — the first was `routines_after` containing `after` rather than
equalling it — and both were found only by running the mutation.

**6d. Built 2026-08-30: switching the base.** The reading end is settable. `buildRevControls`'
trailing disabled row — `— reading a past revision arrives next —` — is gone, and removing it
was the work.

*One owner for everything a version decides.* `_Live` held `store`, `graph_db`, `root`,
`cover`, `files`, `naming` and `glossary` as separate attributes and the payload lived on
`_Handler`, arriving as a constructor argument from a local in `serve()`. Eight places to
keep in step across a swap. They are a frozen `_Base` now, swapped in **one binding** under
the lock, so a request sees the old version entirely or the new one entirely — never a cover
from one and a payload from the other. It is also what the guard reads: *a switch rebuilt
everything* derives its field list from `__dataclass_fields__` rather than restating it
(rule 36).

*Built outside the lock, committed inside it.* Nothing touches the live base until the last
three statements, so the rebuild costs other requests nothing and a failure costs them
nothing at all: the new store is private to the building thread until it is committed, and
on any exception it is closed and the reader keeps the map they had. That is rule 20 applied
to a swap — a switch may refuse, it may never leave a broken base behind. **Exercised rather
than read**: the lock is asked for from inside each build step, because a separate thread
would race the build of a fixture program and pass by finishing first (rule 37).

*One door.* `_Live.open(graph_db, step)` is the boot **and** the switch. A second builder
would be two ways to produce one thing, and the day they disagree the map after a switch is
not the map `serve` would have shown for that version. A guard asserts `serve()` calls none
of the five builders itself.

*A POST, and that is not ceremony.* Every other route here is a read, and a GET that
replaces the map is one a browser prefetch, a bookmark reload or a link preview fires by
itself — this codebase spends rule 20 on a *read* that repaired. `do_POST` routes from its
own table for the same reason `do_GET` does (design rule 16). The guard is over the two
tables and the handlers they name rather than over the paths, because `/api/base` is
legitimately in **both** — the GET reports the base and the progress, the POST changes it —
so a guard comparing paths would have to allow the very thing it is for.

*Progress behind its own lock*, never `live.lock`: the whole point is answering **while** the
big work runs. Six steps, named by the server and printed as sent, because a client-side list
of what building a base involves is a second answer and would count to the wrong total the
day a step is added (rule 32).

*`serve --revision`*, which is where "which version does this server open" honestly lives.
Without it a reader's chosen base survives a reload and not a restart, and the alternative —
a server reading the browser's stored settings — does not exist.

*The client: the options are the pairs, and all of them are real.* Grouped by reading end,
each option naming **both** ends even though its group names one of them — a closed
`<select>` shows the option's text and never its group's, so an option reading only "on its
own" would leave the one control that answers *which two points am I looking at* saying
nothing until it was opened. `revLabel()` is retired with the world it was written for: it
prefixed the served revision with **current**, which was honest while the base was pinned and
is falsest exactly where it matters — in `Society at e2e658b4 ← current`, naming the end that
would stop being current if the reader chose that row.

*On `done`, the page reloads*, and that is Tom's call and the right one. Every module-level
array here is base-derived — routines, plates, files, cover, conventions, terms, anomalies,
packages, the graph payload, the code pane's cache, the search results — and a hand-kept
invalidation list is the defect rule 36 was written from. Settings are keyed per program, so
the theme, scale, panel layout, disk colours, column widths, chosen pair and polarity all
survive; what is lost was about the old base anyway. **On `failed`, it does not reload** and
the overlay states the reason.

*The overlay is blocking, over the whole application*, and Tom chose that too. Every count in
the navigator, every figure in the inspector, every line in the code pane and every dot in
the stack belongs to the version being replaced, so a click during those seconds buys a
confident answer about a map on its way out. It says so, because a reader who cannot use the
page is entitled to know the page underneath is still real and still the old one. Its own
scrim, at the top pair (rule 48), checked with `elementFromPoint`.

*Six defects found by driving, and not one of them by a test.*

- **Chrome restores a `<select>`'s value across a reload, and that outranks the `selected`
  attribute the code writes.** After a switch the control named the pair the reader had been
  on *before* it while the strip named the new one — one control, two claims. **Rule 67.**
- **`buildRevControls` read `chosenPair().from`**, a key it has never carried, so the marker
  was the empty string on every build and the menu opened on the wrong row after every
  reload. Rule 44 one step further in: not a field the server does not send, but one this
  file does not send itself. Same rule 67.
- **A group restored open at boot never fired its `onOpen`.** Open Changes, reload, and it
  sits open under *"two versions — open to compare them"* with nothing to open. Present since
  the group was built and reachable only by reloading — and a base switch reloads. **Rule
  68**, and the fix went wrong once on the way: written as `state.navOpen[g.id]` it fetched
  nothing on a fresh profile, because `groupOpen()` is the one place that knows openness'
  *two* expressions. Rule 51 inside the fix for rule 51.
- **A version left compared with itself.** Choose `A ← B`, then have the server come back up
  on B — reachable without doing anything wrong. Said and dropped, rather than spending a
  fetch to be told.
- **The stored base recorded an intention as a fact.** Written when the switch was *asked
  for*, it named a version nothing was serving for as long as the rebuild ran. `switchBase`
  carries the intent; `reconcileBase` records the outcome, once there is one.
- **A failed switch left the control naming the pair that failed**, while the strip went on
  naming the real base. `buildRevControls()` puts it back — from `state`, which was
  deliberately never written, so the pair in force is what it rebuilds to by construction.

*And one found by reading the served JSON*, which is the second time this session that has
been the only way: **a refusal carried the previous switch's progress**, so declining a
switch to a version with no graph replied `started: false` beside `state: "done"` and another
revision's name. Three fields about three different things under one answer (rule 13).

*The elapsed clock is the client's, deliberately.* The server stamps its elapsed when a
**step** changes, so between steps it stands still — and a cold step takes seconds. A reader
watching a frozen `0.0 s` reads a stalled process. The client measures how long they have
been waiting, which is the number they care about and cannot be stale.

*Guards.* Fourteen server (`tests/test_base_switch.py`) and eight client, mutation-tested
over proved-green baselines (rule 59) at **12/12** and **20/20**. Two survivors on the first
run, and **both times the guard was the weak half, not the mutation** — which is now the
fourth and fifth occurrence in two sessions:

- `if False: _step(5)` survived an `ast` guard collecting `_step(N)` calls, because the call
  still *appears*. Reachability is not a thing a source read can answer; the guard runs
  `open()` with a recording callback now.
- `"REBUILD.step" in panel` passed on `REBUILD.steps`. That is `routines_after` containing
  `after` for the third time. It is `\b(?!s)` now.

*Verified on the corpus.* `output/mensores`, both revisions, driven in a real window.
Switched both ways; the cover, file list, routine list, glossary, naming lane and stack all
move together — 628 / 4,786 / 10,015 nodes against 625 / 4,733 / 9,873 — and the older base
reproduces the recorded ground truth exactly: **175 ways in, 3,950 boundary touches**, with
all four declared executables in *Where to start* at 1,366 / 421 / 265 / 111. The worklist
inverts across the switch, 53 added becoming 53 deleted with no re-query, and
`rode_serving_connection` stays `true` — rule 58's fast path survives the thing it was never
tested against, because `changes.build` rides whichever end is the base. `--revision` opens
the older one at boot and refuses an unknown one by name. A switch to a version with no graph
leaves the old base serving and answering. The console is clean and the self-check prints
*every control is wired* on every load.

*The measurement, honestly.* **1.2 s, 2.1 s and 3.0 s warm; 35 s with the other revision's
stores cold on the external volume.** Same caveat as the change worklist's cold row, and it
is why the overlay names its step: a reader waiting thirty-five seconds is owed *the
glossary* rather than a bar.

**6e. Built 2026-08-30: colour sets in Settings (chunk B).** Tom's call, in his words:
*"Color decisions should reside in Settings — they tend to be personal. Offer a light and
dark mode set, and permit customization within the a11y bounds. It can be broad sets, does
not have to permit individual color settings."*

*Scope, settled with him.* A set covers **difference and severity** — the two channels where
colour separates one meaning from another, and the two that both spend red. A reader who
cannot separate red from green cannot separate red from amber either, so a safe diff pair
beside a red/amber worklist would fix half a problem. Accent and external are single colours
with no partner to be confused with and keep following the theme. Three sets: **Red and
green** (what shipped), **Blue and orange**, **Muted**.

*Two things were wrong before any of it was built, and the second is worse.*

**The difference channel was defined and never spent.** `--diff-gone` and `--diff-new` sat
in all three token blocks from the day the comparison vocabulary landed, `diffWords()`
carried a `tone` per side, and the only thing that drew with either was `.rebuild-why`,
added the day before. A palette setting alone would have been a swatch that changed nothing
— design rule 16 wearing a colour picker — so the channel is now spent: the worklist's stat
tiles, its band headings, the navigator's bands and its note, and the presence lines' `+`
and `−`.

**The Settings "Colour" panel was a live-looking demo.** Two colour pickers, a live WCAG
ratio, a pass/fail verdict — and `state._fg` / `state._bg` were in no `DEFAULTS`, persisted
nowhere, and read by nothing but their own preview chip. It rendered, responded to every
drag, computed a correct ratio and applied it to nothing, since the ratified prototype.
Invisible to *both* guards written for this family: the dead-setting one walks `DEFAULTS`
and these keys were never in it, and the dead-control one asks whether an attribute is read,
and these were `id`s. A control wired to itself.

*The sets are CSS; JavaScript stamps `data-palette`.* `tokens.css` opens by saying no
component declares a colour outside that block, and it is load-bearing — `cssPalette()`
reads the stack's colours through `getComputedStyle` so there is one place a colour is
written down. A palette table in a script would be the second. **Overrides only**: the dark
values are already written twice, so three sets written whole would be six copies nobody
could keep in step; each set declares what differs and `default` declares nothing and stamps
nothing. The ladder is **specificity, never source order** (rule 29) — base `:root` (0,1,0)
< a set's light block (0,2,0) < its dark blocks (0,3,0) — and a guard counts it rather than
trusting it.

*The route is `data-palette-set`, never `data-palette`.* One attribute meaning both a route
and a piece of state is what `data-nav` cost a session; `data-theme-set` already sits beside
`data-theme` for the same reason, and a guard keeps them disjoint.

**Rule 69 came out of the arithmetic, and it is the find.** Contrast says whether a colour
can be *read* and nothing about whether two can be told *apart* — and the shipped palette
passed the first bar and failed the second for its whole life. `--sev-broken` and
`--sev-suspect` are 6.47:1 and 7.09:1 on white and, simulated for deuteranopia, **ΔE 5.3
apart**: the same colour. The difference pair was 12.7. Every check that existed passed,
because they all asked the answerable question rather than the useful one.

So a set states both, computed in the page from the tokens it is actually drawing (rule 13 —
a hex typed beside a swatch is a claim nobody can check). `separation()` implements Viénot,
Brettel & Mollon 1999 and takes the **worst** of normal vision, deuteranopia and protanopia,
never an average: a pair obvious to most readers and invisible to some is not a pair that
works. Measured:

```
                      contrast (worst)   separation (worst)
  Red and green            5.34:1              ΔE  5     ← broken against suspect
  Blue and orange          4.86:1              ΔE 43
  Muted                    4.84:1              ΔE 10
```

*Two things the arithmetic settled that guessing would not have.* **Red and green cannot be
rescued by tuning** — every chroma and every lightness inside that hue family measures
between 4 and 14, which is why `muted` is a *quieter* option and not a safer one and says so
beside its own numbers. And **a difference in lightness survives colour blindness where a
difference in hue does not**, so forcing both colours of a pair to the same contrast ratio
throws away the one axis that always works; the shipped dark pair is separable partly
because it sits at 6.06:1 and 9.63:1, which nobody intended. `muted`'s dark variant keeps
that spread deliberately.

*How the values were arrived at.* Not chosen and checked — a hue and a saturation were
chosen and the **lightness walked** until the colour cleared 5.5:1 against the ground it is
actually drawn on (5.5 rather than AA's 4.5, because the shipped set sits near 6.5 and a bar
met exactly is a bar failed by the next edit). `safe` starts from Okabe-Ito: as published,
its vermillion is 3.87:1 on white and fails outright, so it moves along its own hue until it
passes. Severity there cannot be red/amber/blue — that is the pair the set exists to replace
— so it is a red → magenta → blue ramp, keeping a warm-to-cool ordering.

*Guards.* Nine, mutation-tested at **13/13** over a proved-green baseline (rule 59) — after a
first run at 8/13. **Three of the five survivors were the guard being weak**, which is now
the sixth, seventh and eighth time in three sessions:

- counting `var(--diff-gone)` anywhere passed on a mutation that pointed the bare
  `.tone-gone` at `--text` while a compound `.chgstat.tone-gone` kept it — a *partial* loss,
  the hardest kind to see. It anchors to the bare class now;
- `tone: newer ?` appearing passed with one of the two sides pinned to a literal. It counts
  both;
- `setAttribute` appearing passed on a mutation that deleted the *restore* outright, because
  the same function stamps the set it is about to measure. It names the saved variable now.

*Driven in a real window*, which is where the rest of it was checked: every set in light and
in dark against a live 53/0/18/15 comparison; the polarity flipped through all three states
with `fetch` counted at **zero** and the colours following the words (`53 deleted` red →
`53 added` green → back); the set switched from Settings with the worklist, the navigator's
note and the anomaly badges all moving together; `elementFromPoint` on the chooser; and the
console read — clean, self-check green.

*One false finding I nearly reported.* `elementFromPoint` said the first chooser row landed
on the trail bar, and the geometry says the two panes do not overlap at all: my check asked
whether the row was inside the **window** when the question is whether it is inside the
**scroller**. Rule 50 exactly — a guard naming the right case and measuring the wrong box —
in the driving rather than in the code.

**6f. Built 2026-08-30: the comparison over the code (chunk C, the code browser).** The
first of the overlays, and the one the pairing work had already made nearly free.

*What it is.* Two lanes, and only one of them is ordinary. The **text lane** marks the
lines of the open file that the compared version does not have, and draws the lines it has
and this one does not where they belong, in their own numbering. The **fact lane** beside
it says which routines in this file *behave differently* — which is the half a text diff
cannot state at all, and the whole reason the tool exists. And the file list marks every
one of 628 files as same, different, or on one side only.

*The file-level answer costs no body reads.* `source.db` is content-addressed —
`paths(revision, path) -> hash`, one blob per unique body — so an unchanged file holds the
**same hash** at both revisions and comparing two path maps *is* the file-level diff. Two
indexed queries over 628 rows each, 37 ms warm and 1 ms cached, and it is what makes the
expensive lane affordable: `difflib` runs only on a file the reader opened, and only where
the hashes already say it differs. Twelve of Mensores' 628.

**The prerequisite was a defect, and it is rule 70.** The code browser did not read the
version the map was showing. There is one sidecar per program holding every revision and
its own default is the *newest* snapshot — right only while the newest is also the version
being read, which stopped being true the day the base became switchable. Serving Mensores'
older graph returned `_queue.py` at **674 lines with the 595-line version's marks over
it**: every link past the first divergence underlining the wrong characters, and a footer
naming the revision the bytes came from while the margin came from another. Nothing raised.

Six readers had the same shape — the code browser, the file list, the search,
`/api/source`, the inspector's definition and the cover's line count — and the fix is rule
51's: the **base** names the revision, `_Base.source_revision`, and every reader is handed
it rather than asking a store that cannot know what the reader is looking at. A sidecar
that does not hold that revision answers `None` and a stated absence, never the newest
bytes substituted for the ones asked for. Verified through a live base switch: 595 lines,
625 files, one revision id on every payload.

Found by pointing DunneFlow at its own two revisions and reading what came back. No test
covered it because every unit test opens one revision, where the default is right.

*Decisions worth keeping.*

- **The base end is the server's, not a parameter.** Every other pair here is two
  arguments; this one is drawn over the bytes on screen, and those are the base's. A caller
  free to name a base the browser is not showing could put one version's marks on another's
  lines, which is the defect above wearing a query string — so the parameter does not exist
  rather than being validated.
- **Nothing is elided.** A run of four hundred inserted lines is four hundred rows (rule
  8). The reader can switch the overlay off, which is a different thing from being handed a
  summary of it.
- **A `replace` is a deletion and an insertion, never a third kind.** Two rewritten lines
  are not "one changed line" in any way this can defend — their contents may share nothing
  — and pairing them would invent an identity.
- **The tone comes from `diffWords()`**, so flipping which version is assumed newer swaps
  the marks' colours with the words. Driven, with `fetch` counted at **zero**.
- **A routine only the *other* version has is listed, never marked.** Its line number
  belongs to the other version, and drawing it in this file's margin would put it at a line
  that means something else here (rule 1 — the same argument `code.py` makes about a call
  whose column it cannot honestly give). It says so on the page.
- **`autojunk=False`, measured.** 10 ms with difflib's junk heuristic and 59 ms without,
  and with it `scribe.py` reports 60 removed lines rather than 57. Its guard asserts the
  *answer* over a 480-line fixture, because the string is in that module's docstring too
  and a grep for it passes over a mutation of the call.

*Rule 71, and it is two defects with one shape.* The file rows were marked `chg-same` /
`chg-mod` / `chg-one`, and `.chg-mod` already existed — the worklist's *module* label,
faint and two sizes down — so every **modified** file rendered smaller and greyer than the
unchanged ones. And `dressNavItems` re-inserts a row's gathered text immediately before
`.n`, so the chip written between the name and the count came out *in front of the name*:
`mensores/scriba/ ○ _queue.py`, a glyph inside a path. Both are what this function writes
against what the reader sees, and every check that reads markup or handlers passed both.
Found by looking at the pane — the fourth consecutive session that has paid for itself.

*One more find, in the guards rather than in the code.* `_code()` blanks comment *lines*
and could not see the continuation lines of a block comment, because this codebase indents
them as plain prose. `HANDOFF` records that costing four sessions — three guards tripping
on their own explanation and one selector check missing the shape it was written from — and
it tripped again here on the sentence explaining the tone rule. It is a small state machine
now, starting a block only at a line whose first characters are `/*`, which is what keeps
it safe from the template literals a general stripper once ate. No other guard was resting
on prose.

*Guards.* Eighteen in a new `tests/test_filediff.py` plus seven on the shell, mutation-tested
at **17/17** over a proved-green baseline (rule 59) — after a first run at 11/13 with four
anchors that matched nothing. **Both survivors were the guard being weak**, which is now the
ninth and tenth time in four sessions, and one of them was the *headline* defect: the file
guard asked for the newest revision, where a `build_file` that dropped the revision entirely
answers identically. It asks for the older one now. The other could not tell a pure insert's
`i1` from its `i2` — only a `replace` has a range wide enough to be wrong about — and a third,
found on the re-run, counted `repaintCode` anywhere in a handler that has two paths and needs
both.

*Driven in a real window*, which is where rule 71 and the fact lane's closed loop were found:
both directions of the pair, a live base switch, the switch on and off, the assumption flipped
through all three states with fetches counted at zero, `elementFromPoint` on the controls, and
the console read — clean, self-check green.

*One false finding I nearly reported.* A control measured 0×0 and `elementFromPoint` said the
topbar, which reads as a covered control. It was inside a **closed** accordion group — and I
had checked "open" by asking whether `#codeQ` existed, which is rule 45's own lesson pointed
at my instrument: hidden is not absent.

**6g. Built 2026-08-30: the comparison over the routines (chunk C, tables and the list).**
The second overlay, and the one that needed no server at all.

*What it is.* Every routine in table mode and in the navigator's routine list carries what
the comparison says about it: **arrived**, **went**, **behaves differently**, **edited and
behaving the same**, or **unchanged**. `/api/changes` already returns all four bands with
the node id on every row -- a worklist whose rows cannot be acted on is a dead control with
a count beside it (rule 30) -- so the whole chunk is a `Map` hung on the answer and a glyph.

Three decisions of Tom's settled the shape before any of it was written.

- **Routines only.** The change worklist already *is* the comparison. The **anomaly**
  worklist is a separate piece and is blocked on a question rather than on work: a finding
  carries no id (`state.triage` is keyed by the array index), so "new since the compared
  version" would have to pair findings on `kind` plus `subject` -- and 93 of Mensores' 106
  are `LOST_EDGE`, while `DEAD_CODE` carries no subject at all. A false *new* is rule 1's
  defect with a colour on it.
- **Two switches, not one.** `codeOverlay` fetches a difference per file and can mark four
  hundred lines; `tableOverlay` reads an answer already held. Wanting the cheap marks in the
  list while reading clean code is ordinary, and one control cannot say it.
- **The navigator never pays.** Its routine group is open by default, so asking there would
  cost every session 13-28 s against the cold volume. It *draws* the marks and never fetches
  them, and its note says which of three states it is in -- not compared, comparing, or the
  counts -- because an unmarked list and a list of things that did not change are identical
  to look at and only one of them is a claim (design rule 1).

*Decisions worth keeping.*

- **A routine only the *compared* version has is counted and never marked.** Both surfaces
  list the routines of the version on screen, so it has no row -- and inventing one would
  name a routine among what this version contains. It is stated instead: *"53 added -- in
  2026-08-29 23:46:53 only, so not listed here"*. Serving the other end of the pair is the
  case that exercises it, and it is the whole design-rule-1 point of the chunk.
- **The counts are taken by walking the rows that are drawn**, never from the band lengths
  (rule 32). The bands are the server's answer about two graphs; a count read off them could
  name routines no amount of scrolling would find. `only_compared` is the one exception and
  says so.
- **The tone follows the word.** Flipping which version the reader assumes is newer swaps
  the glyph, the colour and the sentence together, driven through all three states with
  `fetch` counted at **zero**.
- **The sort is a constant, and an earlier version pretended otherwise.** It was derived
  from `diffBands()` so the order would flip with the assumption -- a difference that cannot
  occur, because only one presence band ever owns a row here. Deriving it read as though it
  had been thought about, which is worse than a constant.

*Four defects found by looking, and none of them by any check.*

1. **The `edited` glyph was `·`, and so is the separator between the counts.** The note read
   "18 behave differently · · 15 edited only" -- two dots running together, one a word and
   one punctuation, with nothing to tell them apart. It is `≈` now, which says the thing
   anyway: the text moved and the behaviour did not. *A mark that is also the punctuation
   around it is not a mark* -- rule 32's family, and not worth a number of its own.
2. **The table asked for the comparison after painting**, so `viewTable()` read `CHANGES`
   while it was still null and rendered *"not compared yet — open the table and these rows
   will mark themselves"* **to a reader sitting in the table**, for the thirty seconds a cold
   comparison takes. Rule 68 exactly: a note telling someone to do the thing they have
   already done. `loadChanges` sets its loading flag synchronously, so asking first makes the
   first paint say "comparing…". The navigator had the same lag one pane over, because its
   note is built by `buildNav()` rather than by `render()`.
3. **The footer stated the same answer a second way** and the two drifted immediately: the
   note omits a band with nothing in it and the footer printed `0 deleted`. One answer, twice,
   differently, four thousand rows apart. Both call one function now (rule 51). It is repeated
   at the bottom deliberately -- 4,733 rows is further than a reader can see, and a count they
   have to scroll back for is a count they do not have.
4. **`ROUTINES` feeds two panes and only one was repainted when it arrived.** A reader whose
   centre view was the table when the list landed got nought rows under *"Reading the routine
   list…"*, permanently -- the navigator showing all 4,733 of them beside it. `loadRoutines()
   .then(buildNav)` and no `render()`. **Predates this chunk**, and stated carefully: the empty
   state was observed directly, and that `HEAD` shares it is read from the code rather than
   reproduced, because the attempt to reproduce it there measured the cover instead of the
   table. Rule 35's family -- the array is assigned, and a view that reads it is never asked
   again.

*One infinite loop caught before it ran.* `ensureTableOverlay().then(render)` inside
`render()`'s own table branch: `ensureChanges()` resolves immediately once `CHANGES` is held,
so every paint would have scheduled the next. It already repaints itself when the answer
lands, which is the only repaint wanted.

*Guards.* Twelve new ones in `tests/test_web_controls.py`, mutation-tested at **20/20** over
a proved-green baseline (rule 59) -- after a first run at 14/17 with **all three survivors
the guard being weak**, the eleventh, twelfth and thirteenth time in four sessions. They are
worth listing, because none of the three looked weak:

- the prefix guard collected `rtnchg[a-z-]*` and so could only ever find names that already
  passed -- renaming one to `chg-behaves` left it green, which is the entire defect it exists
  for;
- the column guard unioned the widths across `shell.js` and `settings.js`, so a key deleted
  from one still appeared;
- "is persisted" was a containment check for `"tableOverlay"` anywhere in the file, and the
  name is also a quoted key in `OVERLAY_SWITCHES`. Rule 37, verbatim: a guard that checks a
  name appears has not checked that anything happens. It parses `PERSISTED` now.

*Driven in a real window*: both ends of the pair, a live base switch, the switch on and off,
the assumption through all three states with fetches counted, `elementFromPoint` on the switch
and on a mark, the hover card carrying the mark's sentence, and the console read -- clean,
self-check green. Ground truth held both ways: 18 + 53 + 15 + 4,700 = 4,786 from the newer
base, and 18 + 15 + 4,700 = 4,733 with the 53 stated-and-not-listed from the older one.

### Paused 2026-08-30, after the code browser's overlay

Working tree clean; all three gates green; `output/mensores` untouched and still serving
both revisions.

**The first overlay is on screen, and the thing it needed first was a defect.** The code
browser now draws the difference from the compared version over the file it is showing —
lines the other version does not have, lines it has and this one does not, and beside them
the routines that *behave* differently, which is the half a text diff cannot state. The
file list marks all 628 files, for no body reads at all.

Underneath it, **rule 70**: every reader of the sidecar asked the *store* which bytes to
give rather than the base, so the newest snapshot's text was served under whatever version's
map was on screen. 674 lines with a 595-line file's marks on them, and nothing raised.

**Rule 71** came out of driving it: a class name is global and a stylesheet gives no
warning, and markup another function rewrites is not the markup that renders.

**Next: tables and the worklist**, then the graph as `colorBy: 'change'` — and that one
still wants Tom's decision on the colour channel before it is built. Read `6f`.

**6i. Built 2026-08-30: one history.** Tom's decision, from the report in the section
below: *"I have to use Back too often, and it doesn't always do what I expect."*

*What was wrong.* Two histories, and the split was never designed — it accumulated.
`state.trail` was the visible record and `selHistory` the invisible ⌘Z one, and
`onGraphSelect` recorded to the second and never the first. So the button labelled **Back**
had no record of clicking a node in the stack, which is almost the only thing a reader does
while exploring it. Rule 51 (two places each holding their own answer to one question)
crossed with rule 30 (the visible control's subject was not what the reader took it to be).

*Why it was cheap.* They had already half-merged. A trail step has carried its **subject**
since rule 33; `goToTrailStep` already restored through `applySelectionStep`, which is the
function undo used; and **neither list was ever persisted**, so there was one shape, one
restore path and nothing to migrate. `selHistory` and `selAt` are gone, `state.trail` is the
history, and `trailAt` is the cursor.

*Decisions worth keeping.*

- **One recorder.** `recordSelection(label, note, view)` is the only place a step is made;
  `pushTrail` keeps its signature and delegates. Its two invariants stay exactly where they
  were and are still asserted: `publishSelection()` **first**, above the bail, so an undo
  still tells the sibling window where this one moved; and the `restoringSelection` bail
  **before any write to the history**, or stepping back would record the step it just
  returned to.
- **Dedup by subject, never by label.** `pushTrail` compared labels, which was fine while
  steps were named by hand and wrong the moment every click makes one: two routines called
  `<module>` are two subjects with one name. Confirmed by driving it — the trail shows two
  `<module>` steps side by side, which the old rule would have collapsed.
- **Looking backwards destroys nothing.** Back popped and a step click truncated. Both are
  cursor moves now, and the only thing that drops the forward branch is a *new* step. So the
  bar gained a **Forward**, the `here` mark follows the cursor, and the steps ahead of it
  render faint and italic rather than being hidden — a history with a cursor knows the
  journey did not end where you are standing.
- **The cap split in two, and that is what makes one history workable.** `state.trailCap`
  bounded the *history*, and merging made that fatal: every graph click is a step now, so
  twelve would flush the step the reader detoured *from*. `TRAIL_CAP` (50) is the history;
  `trailCap` is how many the bar shows; and `[data-trailcap]` no longer prunes anything.
  Measured on Mensores: bar showing 6, `+3 behind · 6 shown · +7 ahead` = **16**, the exact
  history length, with Back reaching all of it.

*Three defects found by driving, and the third is the one worth reading.*

1. **A step for a cleared selection was labelled `graph`.** `labelFor(null)` is null, so the
   fallback was `state.view` — and the step a reader most wants back (clicking the node you
   are on is the toggle-off that empties everything) was named after the view it happened in.
2. **The bar stated what fell off the back and not the front.** Stepping back through a long
   trail silently hid everything ahead of the cursor. A window has two edges and design rule
   1 applies to both.
3. **The steps painted over the controls beside them, and every measurement said otherwise.**
   `.trail` carries `min-width: 0` so the buttons are never pushed off, and had no
   `overflow` — so six steps in a 509 px lane drew straight over the "+7 ahead" counter and
   the Back button. `getBoundingClientRect` reported all seven children inside the bar and
   marked visible, because it reports the **layout box and not the ink**. Found by zooming
   in on the bar after the numbers had already said it was fine. Rule 48's family: what the
   DOM says and what the reader sees are different questions.

*What this closes, and what it does not.* Tom's second complaint — *"accidentally changing
the filter by clicking on and off nodes"* — is the same problem, and rule 33 kept that
toggle on the grounds that *undo makes it recoverable*. Driven: clicking the node you are
already on empties the picture, and **one Back restores it**, through a visible control. That
promise is now true. Whether the toggle should still exist is a separate question and wants
Tom's eye before anything else is done to it.

*Guards.* Seven new, and two rewritten rather than protected — `test_the_selection_can_be_
taken_back` asserted an ordering against `selHistory`, which no longer exists. Mutation-tested
at **20/20** over a proved-green baseline (rule 59), after 18/20 with **both survivors the
guard being weak** — the seventeenth and eighteenth time in five sessions:

- `"let trailAt" in js` is also true of `let trailAtX`, so renaming the cursor away walked
  past it. It is a word-boundary match now.
- the bar's two counters were asserted by looking for the words `behind` and `ahead`, which
  a bar with the whole ahead-counter deleted still contains, because `const ahead = …`
  declares one. It asserts the rendered output now.

### Paused 2026-08-30, after one history

Working tree clean; all three gates green; `output/mensores` untouched and still serving both
revisions.

**Chunk C is complete and has been looked at.** All three overlays are on screen — the code
browser, the routine views, and the stack — and Tom drove the stack and approved it: *"the
colors are a reasonable differentiating factor, and the edges do seem to make sense"*, *"an
absolute delight to work with so far"*.

**The exploration work is two-thirds done.** Of the three problems that came out of driving
it (see "Looked at, at the keyboard" below), two are closed by `6i`: Back is one history with
the ⌘Z one, and the toggle-off that empties the picture is recoverable through a visible
control. **The third is next, and Tom named it at the pause: density.**

### Next: density

*"A graph with this many nodes and edges is hard to comprehend."* 10,015 nodes, 14,254 edges.
Everything needed to start is already written down and nothing is blocked.

- **The two feature requests** are recorded whole, in Tom's own words, with what is already
  decided and what is not: "Two feature requests, recorded 2026-08-30" below. **Size a plate
  by its density** — and note it *reverses* `layout.py`'s written decision that every disk is
  drawn the same size, so that comment must be rewritten rather than left to contradict the
  code; there is no per-plate size in the model today, `spreadX`/`spreadY` being global. And
  **draw a plate as a readable diagram** rather than a field of dots.
- **The bar is Tom's and it is an acceptance test, not an aspiration**: *"they must be easy to
  read or we have failed."* A diagram that is drawn and cannot be read is withdrawn, not
  shipped with a caveat.
- **Rule 18 is the constraint that shapes it.** Nodes are 1.4–3.6 px because anything larger
  fuses 10,015 of them into a mass, and rule 22 records that at 14× they occlude the edges
  they are drawn with. A node carrying readable text is an order of magnitude bigger, so the
  first design question is *what is the reader looking at when they turn it on* — one plate, a
  selection — before any renderer.
- **The projection question is already answered** and agrees with Tom's instinct: design rule
  20 chose orthographic, because under perspective a stack of equal disks renders as a tapered
  cylinder. Whether to billboard a *labelled* rectangle the way rule 22 billboards a dot is
  open, and Tom said so — a sphere has no orientation and a labelled box does.
- **The third of the three problems is also a filtering question**, in Tom's framing: *"it may
  take some additional work to get the view filtering improved for exploring."* Worth deciding
  whether density is answered by drawing less, drawing bigger, or drawing differently, before
  building any of the three.

**Also still open, unblocked and unstarted:** the anomaly worklist overlay, which needs one
question answered first — what makes two findings in two versions the same finding. A finding
carries no id and 93 of Mensores' 106 are `LOST_EDGE`, so pairing them would invent an
identity (rule 1).

## The change worklist sees a rewritten comment — 2026-09-01

The last gap in `changes.FACTS`, and the premise on file was wrong in a way worth keeping.
It was written down as *a rewritten explanation above unchanged code is invisible*. It is
not invisible; it is **three different wrong answers**, and only one of them is silence.

### What the tool said before, verified case by case

`line_start` is the `def` line, so a comment block leading a definition sits above it and
outside that routine's `body_hash`. Each row below was constructed and run, and the
mechanism confirmed in the store rather than argued:

| a rewritten comment… | what the page said |
|---|---|
| **leading**, in a file with module-level code (487 of Mensores' 628) | `<module>` in *edited only* — the file rather than the routine, filed under "internal computation, which this tool exists not to report" |
| **leading**, in a file with none (141 of 628) | **"No differences found."** A stated false claim, not an omission |
| **inline**, any file | *edited only* on the right routine, and a pure re-wrap says the same thing |

The `comments` table already attaches a leading comment to the routine it leads —
`alpha` owns it and `<module>` owns none — so asking that table instead of a body hash
**names the right subject for free**. That is what makes this a read-side change with no
re-analysis behind it.

### What it adds on the real corpus, stated plainly: no new rows

```
20 routines have differing comments · all 20 were already in a band
10 in `behaves`, 10 in `edited only` · 0 reclassified · 0 rows added
```

Recorded as it is rather than as it was hoped. Mensores' two versions are three days apart
in active development, so every comment change there rides along with a code change; the
value on that corpus is the `comments` tag on twenty rows, and the three wrong answers above
are what the band is actually for. A documentation-tidying commit is the case it catches,
and this pair does not contain one.

### The canonical form, decided by measurement rather than taste

86% of Mensores' 18,731 comment lines live in a contiguous run of two or more, so
re-wrapping is the ordinary edit and not an exotic one. Re-wrapping every run at three
widths without altering one word:

```
compared as written (set of text + leading)   1,561 · 1,186 · 1,231 routines falsely reported
joined in line order, whitespace collapsed        0 ·     0 ·     0
```

1,561 of the 1,870 routines that own a comment. Comparing as written is not a stricter
reading, it is unusable, and rule 1 decides it.

**The experiment was wrong twice before it was right, both times in my favour.** `textwrap`
splits a long identifier mid-word by default, which is a corruption rather than a re-wrap;
and the first renumbering let a lengthened run overrun the next one's start, merging two
runs. Both showed the joined form failing at 518 when it does not fail at all. Each is now
asserted against inside the experiment — an instrument that alters what it measures reports
on itself (rule 24, in a measurement of prose).

`_constants_moved` predicted this: *"whoever adds `comments` here next will have to ask this
same question a third time, and the answer will depend on how that column is filled rather
than on what it holds."* It does. A constant arrives through `ast.unparse` and is already
canonical; an argument is a byte slice and needs the `canonical/` seam; a comment is **one
row per physical line**, stripped of its marker and nothing else, so the pass it needs is
not about a language at all — it is about where somebody pressed return. That is why it is
done in `changes.py` rather than behind the language seam: joining lines and collapsing
whitespace is prose handling, and prose is prose in every language.

### The bound, which is what made it free

```
41.0 ms   every comment in the program, both sides
 5.2 ms   bounded to the fifteen files whose bytes differ
          — the same twenty routines either way
```

A comment is text in a file, so a file both versions hold with the same content hash cannot
hold a comment that moved. That is `filediff`'s own argument, and it needs no sidecar here
because `files.content_hash` is already in the graph. A routine that moved between files
needs no special case: whichever file lost it and whichever gained it both differ in bytes
by having done so.

Measured like for like in one process against a warm disk, this commit and the one before
it — a git worktree at HEAD, so the working tree was never touched while the numbers were
taken:

```
/api/changes warm   451 ms before  ->  448 ms after   (median of four)
                    every existing band unchanged: 53 / 0 / 20 / 13
```

Inside the noise. The 20 ms of headroom recorded last session is still there.

### The band, which was Tom's call

A **fifth band**, and a **tag** on the rows already in another one.

Not `behaves`: that band promises something the routine *does* has moved, and a rewritten
comment moves nothing it does — the mistake the argument canonicaliser was written to avoid,
one fact type over. Not `edited only` alone: that band says the change was internal
computation, which is what this tool exists **not** to report, and a rewritten WHY is the
layer it exists to show. So `explained_only` holds exactly what would otherwise be in *no*
band, the four bands stay a partition by subtraction, and a routine already in one carries
`comments` among its `moved` kinds instead — one row, one claim (rule 32).

`changeCount()` takes `explained_only` into the headline and still leaves `edited_only` out,
and that line is this tool's whole subject in one expression.

**The glyph is the channel, because the colour channel is full.** Rule 69 measured it:
three directions and a ground, with nothing left that clears a useful bar in both themes. So
`explained` shares `--diff-moved` with `behaves` — *still here, and different* is exactly
what that colour means — and the pilcrow separates them. On the stack, where a node is a dot
and there is no glyph, the two are one colour, and the legend is the only surface that can
admit it, so it does (design rule 1).

### What driving it found

A four-file program with the four cases built into it, analysed twice and served.
`worker_key` reads *explained differently*, `sweep` reads *behaves differently — boundaries,
call_args*, `claim` reads *edited only* with a `comments` tag, and the re-wrapped block on
`claim` produced nothing at all.

And one defect that no check could have: **the table cell's tooltip said "edited, and
nothing it does changed" on a row whose worklist tag said `comments`.** `behaves` has always
named its kinds in that tooltip; `edited` had nothing to name until this landed, and then
had exactly one thing and went on not saying it. Two surfaces answering one question
differently (rule 51), and the tooltip is the one the cursor is already on. Found by
hovering the column. Seventh consecutive session in which looking at the pane paid for
itself.

**Absent rather than estimated:** the graph legend's new row. The key only renders over a
mounted stack and a browser-automation tab gets no animation frames, so `Graph.mounted()` is
false there and every tally is zero (rule 38). It is asserted and mutation-tested, not seen.

### A crash found by dogfooding, and it was nothing to do with this

`analyze` raised `ZeroDivisionError` on the four-file fixture. `render/traceability.py`
divides the ids findable in documentation by the ids cited in code, and a program whose
comments name no governance id makes that denominator zero — which is not an exotic corpus,
it is every program that has not adopted the discipline. Mensores cites 593 and could never
reach it; this was the first thing the tool had ever been given with none.

Stated as an absence rather than filled with a plausible 0% (rule 49): *"no ids are cited in
code"* and *"none of the ids cited in code are documented"* are opposite findings, and a
bare 0% asserts the second.

### The guards

**20/20 mutations caught over a baseline proved green first** (rule 59). Six survived the
first pass, and the split is the useful part — two were weak mutations, three were weak
guards, and one was neither:

- **weak mutations.** Folding comments into `moved` after `behaves` had already been
  computed changes nothing; and mutating one of the two symmetric halves of the changed-file
  `UNION` leaves the other half finding the file anyway.
- **weak guards.** The fact-lane check accepted `"explained"` appearing anywhere, which
  stays true of `explained: []` — the band drawn as empty, rule 35's own shape. The legend
  check looked for its explanation within 400 characters either side, and `_code()` does not
  strip a comment opened inside a template expression, so it was reading the note explaining
  the decision and calling it the note on the screen (rule 43, again). And the re-wrap
  fixture could not reach the case the collapse pass exists for: each stored line is already
  stripped, so joining one-space-per-break is a canonical form by itself — what needs
  collapsing is whitespace *inside* a line, two spaces after a full stop, which 112 of
  Mensores' 6,076 runs carry.
- **neither.** Putting a plausible `0%` back into the traceability fix changed no output,
  because the placeholder it lived in was read by nothing: the empty branch does not mention
  it. A dead value in three lines of my own, and the mutation is what found it (rule 35).

`ORDER BY line` gets a **source** guard rather than a fixture, for `group_concat`'s reason:
drop it and SQLite still returns rows in rowid order, which for a file inserted in one pass
*is* line order — so every test goes on passing while the query has stopped promising
anything.

And one existing guard had to be inverted rather than extended.
`test_every_change_band_the_server_sends_becomes_a_status` listed the four band names and
asserted it had found four, so `explained_only` — sent by the server, mapped by the client —
passed straight through the guard whose entire subject is bands the client forgets. It reads
the served keys out of `build`'s return with `ast` now and excludes three that are not bands,
because an inclusion list can only check what somebody remembered to add to it. That is the
second session running in which a blindness check keyed to the design had to be re-keyed to
the instrument.

```
758 tests · mypy clean · ruff clean · 20/20 mutations caught
```

### Left out, and honestly

**A docstring is not a comment here.** `changes.py` compares the `comments` table, and a
rewritten docstring — which is also WHY, and which rule 9 keeps out of code-shaped detectors
for a different reason — is not in it. `routines.docstring` is in the store and is not
compared by anything. It is the same shape as this work and was not in the scope Tom took.

## A presence line says what it left out, and one idea stops having two colours — 2026-09-01

Two small things, both filed as known and neither a bug. Tom took them together and they
turned out to share a shape: each was a surface saying less than the map already knew.

### The bound without the companion

`Constants +23` printed six names and stopped. The count was right, so nothing looked
wrong — a reader simply had no way to know that six was not twenty-three, and there was no
full listing anywhere in the product. Rule 8 allows abbreviation **only** where the
complete content sits beside it; design rule 1 says a filtered view states what it removed
with the hidden set one click away. This had the bound and neither companion.

**The server was never the problem.** `changes.build` sends every name, in order, whole —
1 table, 3 ways in, 2 named files, 23 constants and 7 that moved on Mensores' pair. The
whole defect was `names.slice(0, 6)` in the renderer.

```
Tables      −1   1 name,  no control  — six is already the whole of it
Ways in     −3   3 names, no control
Named files −2   2 names, no control
Constants  −23   6 names + "17 more ▸"  ·  ◈7  6 names + "1 more ▸"
```

Open, the group names the **whole** set rather than the remainder: two lists a reader has
to join by hand is the same defect one step on, and it is why the way back says *fewer*
rather than *hide these*. The control is drawn whichever way the group is open, because
"showing six of 23" and "showing all 23" are both answers and a button that appears only
while something is hidden makes the unfolded state look like the only state there was.

**The key is the band, never the sign, and that is the judgment worth keeping.** `+` and
`−` swap when the reader changes which version they take to be newer; the twenty-three
names do not move. Keyed on "the plus group" an unfold comes back attached to a different
set — rule 65 in a control, and rule 30 one layer in: a sign is not an identity. Driven
both ways, and it holds: `+23` green with 23 names open becomes `−23` red with the same 23
still open, and the `◈7` beside it is untouched either way.

Not persisted, for `anoOnlyThere`'s reason: this is where the reader is, not what they
arranged, and that is the line `PERSISTED` is drawn on.

### What driving it found, which no test could have

Twenty-three names separated by a single space, several of them 76 characters long and
wrapping mid-name, is a wall of monospace with nothing saying where one ends. **The bound
had been hiding a legibility problem as much as it had been hiding names** — at six it
reads as a list, and it only stops working at the size the unfold makes reachable. Each
name is a chip now.

Inline rather than `inline-block`, and that is the part worth writing down: a chip that
cannot break is a 76-character box that overflows a narrow pane, which is a worse answer
than the wall. An inline background breaks across lines with its text.

Sixth consecutive session in which looking at the pane paid for itself.

### One idea, two colours

*Behaves differently* drew in `--text-muted` on the routine lane while the stack, the graph
legend and the findings' mark drew the same idea in `--diff-moved`. Tom's call: unify.

The old argument is in the stylesheet and is **rewritten as the reversal it is** rather
than left standing beside code that contradicts it. It ran: `behaves` has no *direction*,
and design rule 4 spends colour on one dimension at a time. `--diff-moved` is the answer to
it — it exists precisely because *still here, doing something different* is a direction of
difference rather than an absence of one, and it is measured for separation from the other
two in all three sets and both themes (rule 69).

Eight surfaces, and finding them all is most of the work:

```
routineChip          navigator rows, table cells and the hover card   moved
factLaneHtml         the code browser's fact lane                     moved
viewChanges          the page's third figure, and its band heading    moved
changeList           the navigator group's band heading               moved
changeNote           the note above that group                        moved
routineChangeNote    the routine lane's own note                      moved
anomalyChangeNote    the findings' note                               moved
changeTones · changeKeyHtml   the stack and its legend         already moved
```

`edited` stays out, and that is the channel being **full** rather than an oversight: it is
a fourth thing where rule 69 measured room for three directions and a ground.

**Two near-misses came out of it, and both are the same family.**

The fact lane spelled it `tone-mod` — a *fourth* spelling of the third direction, with a
`.factdot.tone-mod` rule of its own painting it the muted text colour one class name away
from the `.tone-moved` everything else used. Nothing was dead: the class was written, the
rule existed, the colour rendered. Rule 71 with the stylesheet cooperating. It is also the
one surface no search for `tone-moved` could ever have found, because the renderer spells
the class itself and what travels is a bare `"mod"` — and it is the one mutation that
survived the first pass.

And `.hc-chg` sets the muted colour on the very element the tone class lands on, so it
**ties** with the unscoped `.tone-moved` and wins on source order. The hover card would
have gone on saying *behaves differently* in grey while the row that opened it said it in
violet, with the markup, the class and the handler all correct. Rule 29, and it was caught
by working the specificity out by hand rather than by anything that ran. Proved in the
browser afterwards by deleting the rule live: `rgb(90, 102, 117)` without it,
`rgb(109, 40, 217)` with.

### The guards

**21/21 mutations caught over a baseline proved green first** (rule 59), and two of the
three new guards had to be repointed after a mutation survived or a guard failed for the
wrong reason:

- `test_the_difference_channel_is_spelled_one_way` asserts both directions — every tone the
  stylesheet carries is one the shell writes and back again, and every tone rule paints from
  `--diff-*` or a named ground. It could **not** see `tone-mod` come back, because that name
  never appears in the shell: the tone travels as a bare string to a renderer that spells
  the class. The surface-by-surface guard is what catches it, and the general lesson is that
  a search for a class name cannot see a class that is computed.
- `test_behaving_differently_is_drawn_in_the_channel_on_every_surface` anchors the three
  notes on their **count expression**, not on the words beside it: two of the three
  sentences wrap across a line, so a search for the prose finds nothing and the guard would
  pass by having no subject.

**And one existing guard's blindness check had to be rewritten rather than lowered.**
`test_every_routine_mark_class_is_prefixed_and_scoped` asserted four distinct `rtnchg-`
names existed "or this guard is blind". Moving `behaves` into the channel left three, and
the obvious fix — lower the floor to 3 — is how a blindness check erodes to nothing over a
few sessions. It counts what the **regex found** now (five `cls:` literals, one per state),
which is a fact about the instrument rather than about the design it is pointed at.

```
747 tests · mypy clean · ruff clean · 21/21 mutations caught
```

### Absent rather than estimated

**A picture of the four figures side by side.** The automation tab's screenshot viewport
captures roughly the left half of a 1258 px page whatever the window is, so the violet
figure is off the frame — the same limitation the anomaly rows hit last session. What was
driven there is everything static: the classes, the computed colours on every surface
(`rgb(109, 40, 217)` = `--diff-moved` on the table cell, the page figure, the band heading,
the presence line, the fact dot and the hover card), the unfold both ways with
`elementFromPoint` proving it reachable, and the assumption flip carrying the open set with
it. Rule 38: the picture wants a real window.

## The change worklist sees what a call passes, and what a constant is — 2026-09-01

Two gaps that had been written down as open long enough to look like scenery. `FACTS`
compared `calls` without their arguments, and `constants` sat in `PRESENCE` compared by
name — so `f(db_path=None)` becoming `f(policy_path=…/standards-policy.json)` and
`EXPECTED_SCHEMA_VERSION` going from 27 to 28 both read as **no change at all**.

### Measured before it was proposed, and one of the findings was noise

```
arguments   53 callers differ as written · 14 routines in both · 13 after canonicalising
            2 genuinely new to `behaves` (18 -> 20) · 11 already caught by another fact
constants    7 values differ, of 2,615 present in both versions
```

The thirteen were checked against real source, one by one, and every one is genuine:
`db_path=None` → `policy_path=project_dir / ".mensores" / "standards-policy.json"` in two
places, a `frozenset` admitting `'work_items'`, `system/com.society.mensores-scriba` becoming
`system/{_scribe_label()}`, and a refusal message rewritten.

**The fourteenth was the interesting one.** `claim_break_glass_cmd` passes a `typer.echo`
message that was re-wrapped across two lines with not one character of its content changed.
Arguments are stored **as written** — chunk 3's deliberate choice, so a reader can find the
string in the file (rules 8 and 75) — so comparing what was written put it in *behaves
differently*, the band that promises what a routine **does** moved, sitting beside one that
says *edited only, and nothing it does changed*. Rule 1 in the place it does most damage,
and the discipline that caught it is the one already written down: verify a sample against
real source before shipping a detector.

### The canonical form, and where it is allowed to live

Tom's call: canonicalise **at read time, behind a language seam**. So `changes.py` learns
that a canonical form *exists* and never how one is made — an `import ast` there would work
perfectly, on Python, for ever, and quietly break "adding a language changes one extractor".

Two passes, the shape `filediff.py` already uses where equal hashes decide which twelve of
628 files `difflib` reads:

```
one scan a side, compared as written    165 ms   ->  53 candidates
canonicalising only what that flagged    17 ms   over 1,188 arguments
canonicalising both corpora outright    556 ms   for the same answer
```

**Constants are deliberately *not* canonicalised, and that asymmetry is the finding.** A
constant's value reaches the store through `_literal`, which is `ast.unparse` — so both
spellings of `{'a':1,  'b':2}` are already the same string before anything compares them. A
canonical pass was written for them, measured at 384 ms over 374,529 characters a side,
found unable to change any answer, and **removed**. An argument is the opposite case because
`_segment` slices it out of the file on purpose. Two columns, two answers, and the difference
is how each is filled rather than what it holds. Written down in both places, because the
symmetry is inviting and wrong.

### Where the canonicalisers live, and why it is not where they started

They went into `extractors/python/canonical.py`, and both of Mensores' graphs immediately
read as **stale** — `code_extraction_inputs()` globs `extractors/python/*.py` into the cache
key. That is the right default (rule 12 was earned by a key that hashed the rules and not the
reader, and a glob cannot forget a file somebody adds), but the glob is a *mechanism* and the
key's own docstring states the *rule*: **scope is decided by asking what this extraction
actually reads.** Extraction never imports a canonicaliser, and no edit to one can change a
single fact — only whether two facts are judged equal.

Left there it would have discarded every graph on the machine on every edit, sealed snapshots
included, which exist precisely to outlive their source tree (rules 25 and 62). Tom took the
move. `canonical/` sits beside `extractors/`, the fingerprint returned to its stored value
(`0721d30af999205b`), both graphs became readable again, and **no re-analysis was needed** —
which the plan had claimed for the wrong reason and then very nearly got wrong.

Adding a language now touches two places, and they are two concerns rather than one split in
half: `extractors/<lang>/` reads facts, `canonical/<lang>.py` says when two expressions are
the same. A language may have the first and not the second, and then it compares as written.

`LANG_SUFFIX` came along with it — it had been sitting in `walk.py` **declared and read by
nothing at all** since it was written (rule 35, in a constant that looked like a decision).
It is in `canonical/` now, where it is the one thing that consults it.

### The judgment worth recording: `site_id` is not in the key

`call_args` has no owner, so it reaches one by joining `calls` through `site_id`. `site_id`
itself is kept **out** of the comparison: it embeds an ordinal among identical expressions in
a caller, so inserting a third `emit()` renumbers the ones after it and every argument of
every renumbered site would read as changed — the module docstring's own rule about positions
arriving by a side door.

What it costs is the mirror of what `FACTS["calls"]` already costs and is stated rather than
discovered later: this is set comparison, so deleting one of two *identical* calls carrying
*identical* arguments reads as no change. Measured honestly — on this pair both keys give the
same fourteen routines, so **the corpus does not separate them** and the choice rests on the
argument.

### The budget, which now has almost nothing left

```
/api/changes warm   266 ms before  ->  480 ms after, against a < 500 ms budget
first of a session  1.4 s - 23 s, and it swings by forty on the same query
cached              0.7 ms
```

Recorded as 20 ms of headroom rather than as comfortably inside. Three formulations were
measured and **the fastest was rejected**: a `group_concat` digest per caller is 164 ms
against 188 for two scans diffed in Python, but SQLite does not specify the order an
aggregate concatenates in, so two identical argument sets laid out differently in two files
would digest differently and report a difference that is not there. Rule 1, for 24 ms. The
scan takes SQLite's own tuples on a cursor of its own rather than building a `sqlite3.Row`
per row — 202 ms against 165 — and it is set on the *cursor* because `conn` may be the
connection the whole dashboard shares.

And the baseline was measured in a **git worktree at HEAD**, not by stashing, so the working
tree was never touched while the numbers were taken.

### What driving it found

`Constants +23 ◈7` followed by six names, **none of which had moved** — three claims and one
list, with nothing saying which names belonged to which number. Rule 32, and it read
perfectly plausibly. Each count carries its own names now.

### The guards

Mutation-tested **18/18** over a baseline proved green first (rule 59). Four survived first
passes; three were the guard and one was the mutation, which is worth separating:

- the `site_id` guard could not see its own mutation. Its fixture inserted a call, which is a
  real change either way; the case that separates the two keys is a **reorder** — two calls
  to one name swapped, every argument where it was, both ordinals different;
- the constants guard compared values only, so dropping `type` and `is_final` from the key was
  invisible;
- the presence-line guard checked that `names.slice(0, 6)` *appeared*, so a mutation that kept
  the groups and appended a second list at the end left it green. It counts now;
- and one **mutation** was the weak one: canonicalising splats changes no answer, because
  `canonical` returns them unchanged through its own fallback. The branch is an optimisation
  and a statement of intent, and the code now says so rather than implying a guard covers it.

Two guards had to be rewritten rather than repointed. `test_the_diff_asks_for_a_canonical_
form_and_never_makes_one` fired **on its own docstring** — the prose explaining why constants
need no canonical pass cannot say so without naming `ast.unparse` — which is exactly the shape
`test_the_diff_contains_no_write_statement` already had to solve for `DROP`. It walks the AST
now and reads code, never prose (rule 43). And a new guard asserts the cache key holds only
what extraction reads, so the placement decision above is checked rather than remembered.

    744 tests · mypy clean · ruff clean · 18/18 mutations caught

### Left out, and one thing to look at

**Comments**, on Tom's scoping call. `changes.FACTS` does not compare them, so a rewritten
explanation above unchanged code is invisible — and 18,208 comments are the governance layer
and the only source of WHY. It wants its own thought: a reflowed comment is the re-wrap
problem again, larger, and prose has no `ast.unparse` to appeal to.

**Pre-existing and now more visible:** a presence line names at most six of its members and
there is no full listing anywhere — `Constants +23` shows six. Rule 8 allows abbreviation
only where the complete content sits beside it. Adding a third count made the bound easier to
notice; it did not create it.

## The overlay on the findings, and the key it had to be built on — 2026-09-01

Chunk 5c. It opened by reproducing a defect rather than by building anything, and the
reproduction is what made the rest of it obvious.

### The defect, reproduced end to end before a line was changed

`state.triage` was keyed by the finding's **array index** while both declarations of it
said `finding id ->` — `shell.js:362` and `settings.js:330`. Five sites subscripted it:
the count, the row, the three buttons, the click handler and the number keys. Every one
correct on its own, and all five wrong together, because `/api/anomalies` serves findings
`sorted()` by severity, confidence and **count**.

Reproduced over Mensores' pair rather than argued:

    base 22:53:57 -> 107 findings     base 22:53:15 -> 106
    2 of 106 positions hold a different finding, and they are the last two

    index 104   base 22:53:57  `siq__rebuild_87_02h` is written but never read back
                base 22:53:15  `tags` is written but never read back

The one finding that exists in one version and not the other — `siq__rebuild_87_02h`, and
it is exactly the unpaired one 5b measured — shunts every later index by one. Then the
persistence half, in the browser: file a decision against it, switch the base, and
`localStorage` restores `{"104": "ack"}`, which now reads as an acknowledgement of `tags`.
The finding actually acknowledged is not even in that version. **Nothing on screen, nothing
in the console.**

Two more of the same family in one function. `loadAnomalies()` dropped `ident`,
`ident_parts` **and** `subject` on the way in, while `shell.js` read `cur.a.subject` in the
sentence explaining why the two jump buttons are disabled — always `undefined`, falling
back to `"a name"`, for as long as the buttons have existed. Rule 44 one step further in
than usual: not a field the *server* does not send, but a field this file does not send
itself. The server has sent all three since 5a.

### One door in each direction, asserted as an absence

`triageOf(a)` and `setTriage(a, v)` are now the only two places `state.triage` is
subscripted anywhere. The guard is over the **whole file**, not over the five sites that
existed: a sixth hand-written one is the failure this shape exists to prevent, and a check
written over the five would pass on it (rule 74's shape, rule 51's reason). Both take the
finding rather than its identity, so a caller cannot reach for the wrong key holding half
of one.

### `SETTINGS_VERSION` 5, and the first bump that carries forward

An index-keyed blob read as ident-keyed is a **wrong** answer, not an absent one, so it may
not merge. Every bump before this one discarded the whole blob, which is right when a blob
cannot be read at all — here exactly one key of sixty-six is unreadable and the shelf, the
plate colours and the panel layout are as good as they were. Tom's call: bump, carry
forward, drop exactly `triage`.

`CARRY_FORWARD` is keyed by the version being **left**, so it is a statement about one
specific blob rather than a licence to vouch for any older one — the gate `migrate.py` puts
on re-stamping a fingerprint (rule 62), in client storage. Two things fell out:

- **The old blob is left where it is.** Deleting it would be a read path destroying the
  evidence it read (rule 20), and the trade is asymmetric: a few kilobytes against every
  arrangement a reader has made, gone the moment they run an older build. `v1` through `v3`
  are still sitting in this machine's storage, which is the cheaper mistake.
- **The load says what it dropped**, on the surface that lost it rather than as a banner,
  and once — a second load has a v5 blob and does not nag.

Driven: v5 written with 67 keys, every arrangement intact, `triage` empty, v4 untouched.

### The overlay

`/api/anomalychanges` on screen, default on, fetched when the worklist is opened — the
bargain `codeOverlay` and `tableOverlay` already strike, and the dearest of the three,
because the compared end is thirteen detectors over a graph nothing here has opened.

Two calls Tom took before it was built. **Findings only the compared version has are
counted in the head with the set one unfold away**, not given rows — so the list, `j`/`k`
and "left to triage" go on counting one thing (rule 32), which is the exception
`changeCounts` already makes for `only_compared` routines. And they carry no triage
buttons: a decision about a version you are not reading is not a decision.

**The `moved` mark already had a colour and nobody had spent it.** `--diff-moved` is violet
in all three sets and both themes, with its separation measured and stated in the Settings
table (rule 69), and `.tone-moved` is what the graph legend already spells the same idea
with. *Still here, claiming something different* is a **direction** of difference, not an
absence of one — so it goes in the channel, and the two surfaces cannot part company about
what violet means. Every class is prefixed `anochg-` and scoped to `.wl-item`, because
rule 71 has been paid for twice already.

    base 22:53:57   1 only_in_base ·  0 only_in_compared · 4 moved · 0 ms held
    base 22:53:15   0 only_in_base ·  1 only_in_compared · 4 moved, and the word inverts

The inversion is exact and it is the check that these are set membership rather than a
claim about time: `siq__rebuild_87_02h` is a counted-but-unlisted "1 added" from one end
and a green `+` row from the other, and the word is "added" both times, because it follows
the **word** and never the side.

### What driving it found, and no test could have

**A count that named the wrong set.** The note counted all 106 findings while the tabs, the
progress bar and "left to triage" beside it were per severity — so the Suspect tab read
`◈ 4 claiming something different · 1 added` with **not one marked row on it**: all five
banded findings on this pair are INFO. Two correct numbers, neither saying what it counted,
which is rule 32 exactly and the same shape that stopped `degree` being printed beside a
routine. Everything in that note is scoped to the tab now, the compared-only count and the
unfolded set included.

**One fact rendered twice, side by side.** The carried-forward note read *"triage decisions
— they were filed against a position in the list, not a finding: they were filed against a
position in this list rather than against a finding"*, because `settings.js` carried a
reason and `shell.js` wrote one too. The store names **what** was dropped; the view says
**why it mattered here**. Rule 40 in prose.

Both were found by looking at the pane, which is now the fifth consecutive session that has
paid for itself.

### The guards

Mutation-tested **20/20** over a baseline proved green first (rule 59). Three survived
first passes and every one was the guard:

- a check for `SETTINGS_VERSION - 1` in `carryForward` passed over `CARRY_FORWARD[4]`,
  because the *storage key* one line below still said it — rule 54's shape, the right name
  read over the wrong span. It asserts both occurrences and no literal index now;
- the tone check inspected only the concatenation form, so hardcoding `tone-gone` left the
  loop nothing to iterate and it passed on empty — rule 59's companion, a mutation that
  removes the thing being read. It refuses a literal outright now;
- and one that cried wolf on its own first run: `"removeItem" not in code` fired on
  `resetSettings`, which deletes the key and is **right** to — that is the reader asking
  out loud. Scoped to the two read paths (rule 43).

One existing guard was rewritten rather than repointed. `test_the_settings_version_moved_
with_the_shape_that_changed` asserted the literal `const SETTINGS_VERSION = 4;`, so the v5
bump failed it for nothing — an assertion about *when it was written* rather than about what
it protects, which is rule 46's family. It asserts `>= 4` now, and what a *bump* needs is
asserted next door.

    731 tests · mypy clean · ruff clean · 20/20 mutations caught

### Not measured, and absent rather than estimated

**A picture of it.** The automation tab's viewport is fixed at 1262x556 whatever the window
is set to, and this app puts ~320px of chrome above the list, so the marked rows do not fit
in a frame. Every static fact was driven and checked there — the classes, the computed
colours (`rgb(109, 40, 217)`, which is `--diff-moved`), the titles with both numbers in
them, the counts per tab, the switch both ways, and `elementFromPoint` on the unfold and the
switch to prove they are reachable rather than merely wired (rule 48). Rule 38: the picture
wants a real window.

### Still wanting Tom's eye

Carried over unchanged and blocking nothing: the flow panel's **1 px arrow stroke**, thin to
aim at though the same flow is reachable from a row in the pane; and a **1,347-line
`frozenset` argument** in this corpus that wraps rather than elides, because rule 8 allows
abbreviation only beside the full value.

New, and small: the routine lane draws *behaves differently* in `--text-muted` while the
graph legend and now the findings draw the same idea in `--diff-moved`. Two answers to one
question (rule 51). Not changed here because it is a change to a shipped surface on a
judgment that is Tom's, not mine.

## A finding says what makes it that finding — 2026-08-31

Chunks 5a and 5b. The anomaly worklist overlay had been blocked since 2026-08-30 on one
question rather than on effort, and the question turned out to be measurable.

### The question, answered with a count rather than an argument

*What makes two findings in two versions the same finding.* A finding carried no identity
at all, `state.triage` was keyed by an array index, and 93 of Mensores' 106 findings are
`LOST_EDGE` — so any loose pairing would have invented one, which is rule 1's defect with
a colour on it.

Measured over the real pair before putting anything to Tom, which is what turned a design
judgment into a decision:

    base 106 findings · compared 107
      kind+subject       106 distinct keys in each · 0 collisions
                         106 of 106 paired · 1 genuinely new · 4 with a moved count
      kind+subject+file  loses pairs — `file` is MIN(file), an arbitrary tiebreak
      kind+title         loses 4 and 5 — the title carries the counts

And the old sub-question — *what is an occurrence for `LOST_EDGE`, the 142 callers or the
rival definitions* — dissolved rather than being answered. The detector already groups by
`callee_expr`, so the finding is one per expression; the callers are its `count` and the
rivals are in its title. Both are what it *reports*, and both move while it stays the same
finding. It was never an identity question.

### Tom's decision, and the reason that shaped the build

He took **an explicit identity per detector** over the cheaper uniform key, and his reason
is the whole shape of 5a: *"to later on permit different languages such as Kotlin or C++
… keep the input possibilities wide enough."*

Detectors are query-driven over the store, so a Kotlin or C++ extractor's facts already
run through the thirteen that exist — and a second language brings detectors of its own. A
**central** rule inferring identity from `subject` would have to go on being right about
every one of them. Declared beside the detector, adding one is a self-contained job.

Two constraints follow, and both are stated in `Anomaly`'s docstring rather than left to
be rediscovered: no position in a key, and the parts come from the **fact contract**
(`qualname`, `callee_expr`, `tbl`, `module`) rather than from any language's syntax.

### 5a — the identity

`ident_parts` has **no default**, so a detector that does not answer the question cannot
construct a finding: the type checker named all 17 sites itself the moment the field
landed, which is the strongest form the guard can take. `ident` is a property over the
parts — `make_id("finding", kind, *parts)`, the namespacing `make_id("ep", …)` and
`make_id("site", …)` already use — never stored beside them, because a second copy of an
answer is a second thing to keep in step (rule 51). The parts are kept because the pairing
is a *claim* and they are how a reader sees why it was made (design rule 13).

Three shapes, and naming them was most of the work. **Grouped** detectors key on their
GROUP BY column, unique by construction. **Per-site** ones key on what names them.
**Whole-program** ones declare `()`, and that empty tuple is a statement — one of these
per program — where before it was an empty `subject` that fell out of a default argument
and claimed nothing.

`Report.add` breaks a genuine tie with an **ordinal among identical keys**, the residue
`_identity()` and `call_site_id` already carry. It never merges and it never invents a
key; it only breaks a tie in one.

    Mensores, both ends   106 findings / 106 ids · 107 / 107 · zero ordinals needed
    DunneFlow read by itself   21 findings / 21 ids

### 5b — the pairing

`web/anomalychanges.py` takes two lists of rows and pairs them, so it can be read and
tested without a graph on disk. Bands named for **where a finding is** (rule 65):
`only_in_base`, `only_in_compared`, `moved` — and the compared end of a moved finding is
`in_compared`, never `was`, which would be the whole of rule 65 in one word.

**What is compared is what a finding claims**: `count`, `severity`, `confidence`. Not
`title` or `detail`, which are renderings of exactly those — comparing both would report
one change twice and call it two (rule 40). Not `blind_spot`, which is a sentence about
*this tool*: when it changes, DunneFlow changed, and a mark there would say the program
moved when it did not.

Driven against the real pair, both ways round, and it inverts exactly — which is the
check that these are set membership and not a claim about time:

    base 22:53:57   1 only_in_base · 0 only_in_compared · 4 moved
    base 22:53:15   0 only_in_base · 1 only_in_compared · 4 moved, counts reversed
    the one unpaired finding is real: an eighth ONE_WAY_TABLE, `siq__rebuild_87_02h`

### The cost is inherent, and it is the disk

Every other comparison here joins two graphs on one connection, because facts are rows.
Findings are not rows — they are what thirteen detectors *conclude* — so the compared
version's findings mean running the detectors over its graph. Rule 58 does not land: its
36× is a second handle to a file this process already holds open, and the compared graph
is not that file.

    /api/anomalies, served graph      62 ms per request → 0.9 ms held
    first pairing, 31 MB graph cold   1.3 s – 4.1 s, and it is mostly the disk
    pairing once both ends are held   0 ms

So the findings are held per **graph**, not per pair, and a base switch does not clear
them: the file is the same file. `COMPARISON_CACHES` names the caches a switch *does*
clear, and a second guard asserts `findings` and `filepairs` are not among them — cleared
for tidiness they would make every switch pay those seconds again to learn what it knew.

The same cache fixes something that was already there: `/api/anomalies` ran all thirteen
detectors on **every** request, inside the lock, for an answer that cannot change while
the served file does not.

### A graph that cannot be read is stated, never emptied

Rules 49 and 63, and driven end to end rather than trusted to a guard: a program directory
holding one readable graph and one genuinely stale one. The comparison answers
`available: false`, names the file, the reason and `dunneflow migrate` (rule 62 — a reader
must name *which* fix applies), sends **no bands at all**, and the base's own findings go
on answering. An empty list there would have read as *this version had nothing wrong with
it*, which is a different and false claim.

### The guards, and what the first passes found

Mutation-tested **10/10** and **11/11** over baselines proved green first (rule 59). Four
survived first passes and **every one was the guard**, for the fourteenth, fifteenth,
sixteenth and seventeenth time in five sessions:

- a check reading the word `file` passed straight over `MIN(file) f` reaching the site as
  `row["f"]`. It compares *expressions* now, never names;
- the fixtures had one module, so a key of the bare name was indistinguishable from
  `(module, name)`. Two modules redefining one name is the smallest program that can see
  the difference;
- **the ordinal that exists to disambiguate was hiding weak keys from the uniqueness
  test** — two findings that should have had different keys got different ids anyway, told
  apart by their order. The corpus guard now asserts no declared key needs tie-breaking at
  all, which is the stronger claim;
- nothing asserted that a pair whose findings only *moved* is not `identical`.

Two general rules fell out and are worth keeping. **A key carries every loop the finding
is emitted inside**: `_parse_failures` loops files then errors, and keyed on the path alone
every error after the first vanishes into the tie-breaker — the merge this design exists to
prevent, wearing the costume of the mechanism written to prevent it. Unreachable in Python,
which stops at the first syntax error, and reachable the day a compiler that reports many is
read; so the guard is structural, because the fixtures cannot see it. And **a finding that
counts a set is not identified by a member of it** — rule 32 in an identity.

    710 tests after 5a · 723 after 5b · mypy clean · ruff clean

### Paused 2026-08-31, with 5a and 5b in

Both committed, tree clean. **Next: 5c, the overlay on screen**, and it opens by
reproducing a live defect rather than by building anything. `state.triage` is keyed by the
finding's **array index** while both of its declarations say `finding id ->` —
`shell.js:362` and `settings.js:330`. Triage is persisted, findings are served `sorted()`
by severity, confidence and **count**, and a base switch reloads the page: so a count that
moves, a detector that is added, or a switch lands every saved decision on a different
finding, silently. `SETTINGS_VERSION` must bump — an index-keyed blob read as ident-keyed
is a wrong answer, not an absent one.

Tom's call on the overlay, taken at the pause before 5b: **default on, fetched when the
worklist is opened**, matching `codeOverlay` and `tableOverlay`, which pay on a deliberate
navigation. The first open of a session may wait and says *comparing with …* while it does.

Found in passing and unfixed: `loadAnomalies()` drops `f.subject` from its map while
`shell.js:3752` reads `cur.a.subject` — always `undefined`, falling back to `"a name"`, in
the text explaining why the two jump buttons are disabled. Rule 44 again.

**Still wanting Tom's eye, carried over unchanged and blocking nothing:** the flow panel's
arrow stroke is **1 px**, thin to aim at, though the same flow is reachable from a row in
the pane, which is a button; and a **1,347-line `frozenset` argument** in this corpus wraps
rather than elides, because rule 8 allows abbreviation only where the complete value sits
beside it.

## An edge says what flows, and the echo that had been eating the subject — 2026-08-31

Chunk 4 of the approved plan, and the one Tom asked for in the same breath as the
arguments: *"If I click on an edge in the diagram, I would like to see what data is
flowing there (Flow)."*

### The arrow is a thing now

`Compartment`'s three lanes were `Counter[(src, dst)] -> weight`, which computes the kind
on the way in and drops it on the way out — so a TOUCH and a CALL between the same two
boxes were one arrow with one number and nothing could say which. A lane is
`pair -> Counter[kind]` now, and **the weight is the sum, by construction**, so the number
on the arrow and the kinds behind it cannot disagree (rule 13).

`dot()` writes `id=` on every edge as well as every node. The id is the two box ids with
`=>` between them, split on the **first** occurrence — exact only while no box id can hold
one, which is asserted over every box in the program rather than assumed. A box id that
held one would name a box that does not exist, and the panel would answer about it
confidently.

`/api/flow?from=&to=[&inside=]` answers on demand. `inside` names the fold when the arrow
is on the second level and is **refused rather than inferred from the shape of an id**
(rule 30): the same pair of ids can name an arrow on either level.

    a CALL edge, 14 sites   OrchestratorClaimStore -> _orchestrator_claim_store.py   1 ms warm
    a TOUCH edge, weight 12  _orchestrator_claim_status.py -> DATABASE               2 ms
    the whole payload        119 arrows keyed by id, riding with the drawing         0 requests to hover

### What an argument may be said to land on, and 92.2% of them do

The precision line is the whole of this chunk. An argument is recorded as written; it is
aligned to a declared parameter **only where the source settles it**:

- a **keyword** binds by name, always — the source names its parameter;
- a **positional** binds by index only when the callee is resolved, declares no `*args`,
  and the receiver question is answered;
- a **splat** binds to nothing ever, and a positional *after* a splat is unbindable too —
  `f(*xs, b)` puts `b` at an index nobody can compute, and the easy version of this rule
  carries on one place out and produces a specific, plausible, wrong answer.

The receiver question is the interesting one. `self.render(x)` passes `x` to the *second*
parameter and that is certain. `obj.render(x)` and `Cls.render(obj, x)` are the same
routine written two ways and nothing in the expression says which, so nothing is claimed.

**Measured before deciding whether that refusal was too cautious**, over every resolved
call site rather than over the four edges I had open:

    10,668 of 11,570 arguments bound   92.2%
       426  a dotted call to a method -- the receiver question
       348  the callee takes *args
       113  no parameter of that name or index
        15  a splat

So the refusal costs 3.7% and the `self.` fast path does the work. A sharper rule using
arity to settle the receiver would buy at most those 426 and add reasoning; not worth it,
and rule 1 says the refusal is the right default anyway. **The pane states the reason on
every refusal**, because a blank beside an argument reads as *no such parameter*, which is
a different and false claim.

### The defect this uncovered, which was not this chunk's

Driving it with the graph mounted, the arrow was clicked, `state.flow` was set — and two
lines later it was gone and the inspector was describing `emit_hard_policy_changed`.

`applyWanted` hands the stack a selection the app has already decided, and
`Graph.setSelection` announces it **synchronously**, so `onGraphSelect` ran inside its own
caller's turn and re-subjected to `sel.node`: the last node of whatever was just installed,
one arbitrary member of it. **That is rule 74 exactly, arriving through the engine instead
of through the caller** — and it filed a second trail step under that member's name on the
way past.

**The fold has had it since the day it was built.** Instrumented on the live page, a box
click set `state.fold` and the echo replaced it with a method of that class, every time.
It was invisible because in Diagram mode with the stack never mounted `applyWanted` returns
at `Graph.mounted()` and nothing echoes at all — so the feature is correct exactly as long
as nobody opens the graph, which is how it passed a session of verification and Tom's own
use. Rule 76, and rule 38's companion: an instrument that never reaches a state cannot
report on it.

The bail is a flag raised for the duration of the one call that re-enters, in a `finally`
— a throw inside the engine would otherwise leave the shell deaf to every later selection.
`state.picks` stays outside it, because the engine is the authority on what is *picked*.

### Two smaller things, both found by driving

**A port carries `plate`, not `what`.** Inside a box a boundary is a `touch` box whose
`what` is the kind; *between* compartments the boundaries live on their own plate, so the
arrow ends at a port standing for `ext:DATABASE`. Reading only the first spelling returned
an edge into the database with five unfiltered boundaries and **no SQL at all** — a panel
that looked like an answer and named none of the twelve statements the arrow was drawn
for. With it fixed, the same edge reads two SELECTs with their tables and two DATABASE
boundaries that no SQL row names — and rule 40's one-line tolerance is visibly right
there: the connection opens at :94 and :110, the statements run at :99 and :115, so both
are kept as separate acts.

**`elementFromPoint` answers `null` outside the viewport**, which is not the same as
"nothing there". A probe that did not check cost one confusing round.

### What was verified, and what was not

Driven with a real pointer sequence at coordinates taken from each arrow's own path:

    17 arrows drawn, 17 with an id, 17 reachable by elementFromPoint
    the click routes to selectFlow; fold and selected are null; SPECIMEN.kind is FLOW
    14 call sites rendered, 14 `code >` buttons, 10 bound argument rows
    the trail step reads "OrchestratorClaimStore -> _orchestrator_claim_store.py"
    the hover card fires 0 requests
    the pane scrolls inside itself; the document does not (rule 29 holds)

**Not verified: what it looks like.** The automation tab's screenshot viewport is narrower
than the page's CSS viewport, so the inspector is off the captured frame while being
plainly on the page at x=910, 352x437. Rule 38 — the picture wants a real window and Tom's
eye. Two things worth his judgment: the arrow stroke is **1px**, which is thin to aim at
(the same flow is reachable from a row in the pane, which is a button), and a 1,347-line
`frozenset` argument exists in this corpus and will wrap rather than elide, because rule 8
allows abbreviation only where the complete value sits beside it.

### Guards

`tests/test_diagram.py` gains six behavioural checks over the real fold and ten over the
binding rule; `tests/test_web_controls.py` gains four. Mutation-tested **19/19** and
**5/5** over baselines proved green first (rule 59).

**Four survived the first pass and every one was the guard.** Three were the same
weakness — a containment check the mutation left the token in place for: `"loadFlow(" in
setter` passes on `if (false) loadFlow(flow)`, and `"unbound_because" in view` passes on
`false && c.unbound_because`. The fourth is the one worth keeping: an ordering guard that
compared two chosen literals survived a mutation that simply *added* an earlier call, and
its "fix" — comparing the first mention of each name — measured where the two functions are
**defined** rather than where they are called, and survived the same mutation again. It is
structural now, in both directions: the arrow is asked about *only* in the branch the box
question missed. Rule 46's shape, in a test, twice.

A fifth mutation did not apply at all, and that is a check too: the pattern had drifted from
the file, so it was reporting nothing while looking like a pass.

Gates: 698 tests, mypy clean, ruff clean.

## The arguments, as written — 2026-08-31

Chunk 3 of the approved plan, and the one Tom chose over approximating a call from the
callee's declaration: **record what the caller actually passes.**

`schema.CallArg` is `{idx, expr, keyword, splat}` and `CallSite` gains `args` and a
`site_id`. The store gains a `call_args` table hanging off that id, and `SCHEMA_VERSION`
goes to 6, which invalidates every cached fact by itself (rule 12).

**As written, not re-rendered, and that is the whole of the decision.** `ast.unparse` was
sitting right there in `_literal` and would have been one line. It gives back an
expression that is equivalent and not identical: `d["k"]` comes back as `d['k']`, a
wrapped list comes back on one line, and a reader who goes looking in the file for the
string the panel showed them does not find it. So the expression is sliced out of the
file's own text. Measured on the corpus: **43,926 arguments across 30,544 call sites**,
14,222 of them keywords and 49 splats.

### The column offset is a byte offset, and 235 arguments prove it

`ast`'s `col_offset` is an offset into the **UTF-8 encoding** of its line, not a character
index. On `emit("naïve ✓", timeout=5.0)` a character slice returns `)` for the second
argument — a perfectly plausible expression, and not the one that is there.

Measured over the real tree rather than argued: **235 of 44,344 single-line arguments
would differ**, and they are the interesting ones —

    f"must be a positive int ≤ {_TTL_MAX_SECONDS} (1 day)"     char slice keeps the comma
    f"  [red]•[/red] [{kind}] {msg}"                            char slice keeps the paren
    f"Society 5-layer reconstruction — {framework} {version}"   char slice keeps the comma

Every one of them a message with a symbol in it, which is exactly what a reader opens a
flow panel to read. Rule 75.

`ast.get_source_segment` gets this right and re-splits the whole file on every call, which
over 184k lines and 30k call sites is the file split a hundred thousand times. The lines
are already in the extractor.

### Two identical expressions on one line, and 287 of them are real

`site_id` exists so the arguments of one call do not land on another. The old key
available — `(caller_id, callee_expr, line)` — is ambiguous for **287 call sites on
Mensores**, so this is not a theoretical case: `emit(x); emit(y)` is ordinary code and
merging the two loses one of the two argument lists.

**No position in the id**, per `make_id`, which is explicit that a line number would
retire every fact below an inserted import. The only discriminator left is an ordinal
among identical expressions in the same caller, and **the residue is written down rather
than hidden**: adding a *third* `emit()` between the first two re-numbers the ones after
it, so those sites read as changed when nothing about them did. That is narrower than a
line number, which moves everything below anything, and it is bounded by how often one
routine calls one name twice. 30,544 sites, 30,544 distinct ids, none blank.

### One door, and a second one deleted

Two places appended a `CallSite`, so identity is assigned in neither of them — it is
assigned in `_record_call`, which both go through. Rule 51: the list of callers is the
thing that grows, and the next one added forgets the ordinal.

`Store.set_call_target` was deleted on the way past. **Nothing called it** — the resolver
updates by `rowid` — and it keyed on `(caller_id, callee_expr, line)`, which is the key
`site_id` exists because it is ambiguous. A dead second door onto the table that would
have been wrong the moment anyone opened it.

The argument purge had one ordering to get right: `call_args` has no `file` column, so
`forget_file` has to delete through `calls` **before** emptying it, or the rows sit in the
store for ever attached to a site that no longer exists. 0 orphans on the corpus.

### What is honestly absent

- **The change worklist does not see an argument change yet.** `changes.FACTS` compares
  `calls` on `(callee_id, callee_expr, external, at_boundary)`; a call whose arguments
  were rewritten and whose target was not reads as unchanged. That is a real gap and it
  is left open rather than closed quietly, because adding a column there moves the
  recorded worklist figures and is a decision about what "behaves differently" means.
- **One argument is 91,224 characters over 1,347 lines** — a `frozenset` literal in
  `quaestor/_envelope.py`. Kept whole, because rule 8 says a value shortened at ingest is
  lost for good. It is a constraint on chunk 4's panel rather than on the store: the
  complete content has to sit beside any abbreviation of it, never instead of it.

### The corpus, rebuilt — and the tree this file named wrongly

A `SCHEMA_VERSION` bump makes both stored revisions refuse to open (rule 20), so both were
rebuilt on Tom's call. **`CLAUDE.md` and `BRIEFING.md` both name `../mensores-overhaul` as
the tree to verify against, and it is not either end of the temporal pair** — the pair is
`../society-2026-08-26` (625 files) and `../society-2026-08-29` (628), pulled as sister
clones and recorded as such 1,400 lines up this file. `mensores-overhaul` is a third tree
of 626 files. Analysing it produced a perfectly healthy revision that was not the one every
recorded temporal figure belongs to, and the tell was the sidecar: *"1 read, 625 already
held"*, one file different where the record says twelve.

Rebuilt, both ends reproduce their recorded figures exactly:

    625 files · 4,733 routines · 175 ways in · 3,950 boundary touches   FOR_COMPARISON
    628 files · 4,786 routines · 178 ways in · 4,070 boundary touches   WORKING

Ground truth holds at both ends: the four executables resolved with their command trees,
five STATED naming rules all from `NAMING.md`, `mensor` glossed from *mētior*, and **zero**
naming rules from `conventions-naming-and-documentation.md`, which is the half that
matters. Cold analysis 32 s against a 90 s budget. The worklist reads 53 only-in-base,
18 behaving differently, 15 edited only, over 4,786 against 4,733.

### The boot figure is withdrawn for this session rather than reported

`serve` on the rebuilt stores was timed four times on identical work: **57.2 s, 16.1 s,
50.0 s and 135.3 s**, at around 3% CPU throughout. Reading the three stores with `cat`
takes 11.5 s for 135 MB — about 12 MB/s — so the volume is certainly part of it, and
priming the page cache produced the *slowest* run of the four, so the volume is not all of
it either. An eight-fold spread on one measurement is not a measurement (rule 24), and
picking the good number would be worse than posting none.

What can be said soundly: nothing at boot reads the new table, the graph is *smaller* than
the one that recorded 10.2 s (28.0 MB against 31.4 MB), and the request timings taken
against the running server are all inside budget — cover 1 ms, `/api/graph` 33 ms,
`/api/changes` 4.5 ms cached, `/api/filechanges` 0.6 ms, search 45 ms warm. The 12 s first
search and the 40 s first comparison are the external-volume caveat this file already
carries in five places.

### Guards

`tests/test_call_args.py`, twelve of them, mutation-tested **7/7 over the extractor and
4/4 over the store**, on a baseline proved green before any mutation ran (rule 59) and with
`__pycache__` cleared around every restore (rule 56). Each was written from a defect and
run against it: a character slice, a single-line-only segment, `ast.unparse` in place of
the source, an ordinal frozen at zero, splats dropped, `**x` read as a keyword named
nothing, a synthetic dispatch bypassing the one door, the purge never reaching `call_args`,
a blank `site_id`, arguments never written, and `keyword`/`expr` swapped on the way in.

One of the twelve passed for the wrong reason first time and is worth keeping: the
"identity survives an edit above it" guard extracted the two versions as `a.py` and `b.py`,
which are two *modules* and so two callers, so the ids differed for a reason that had
nothing to do with the claim. It edits one file now.

Gates: **679** tests, mypy clean, ruff clean. *That figure was first written here as 703 and was never measured* -- `pytest -q` prints dots and the count was asserted beside them. Rule 13 in this file rather than in the product: a number printed beside a claim has to be the one the thing produced.

**Next: chunk 4** — `dot()` writes `id=` on every edge, `Compartment` keeps the edge *kind*
beside the weight (dropped today, so a TOUCH and a CALL are indistinguishable), and
`/api/flow?from=&to=` answers on demand with every call site, its arguments, the callee's
declared parameters, and the `data-gotocode` button on each — Tom's *"ultimately where it
all goes"*.

## A box answers about itself, and the click that never arrived — 2026-08-31

Tom drove the approved Diagram mode and reported three things over two rounds. All three
were defects, and the last of them had already survived two rounds of verification because
of *how* it was being verified.

> *"I click a node, and the Inspector does not change to reflect that specific node… If I
> click on an edge in the diagram, I would like to see what data is flowing there (Flow)…
> It would be nice to have this sync'd with Code as well."*

### 1. A box is a fold, and the inspector was answering about a member of it

`selectFromNav({nodes: box.members})` sets `state.selected = members[0]`. So clicking the
box labelled **`KernelDecl`, 61 methods** filled the inspector with
`KernelDecl._profile_name_or_none`, lines 335–337 — a true answer about something nobody
clicked (rule 32). The previous session recorded that "the inspector did fill", which was
true and beside the point.

**The stack has never made that mistake.** `onGraphSelect` sets `state.selected = null` when
a *plate* is picked, because a plate is not a node. What was missing was an answer, not
honesty about the lack of one.

`/api/fold` answers in the **same skeleton every other specimen uses**, so it renders
through the pane that already exists: 61 members with their invocation lines, 8 neighbours,
what it touches, its governance ids, and the span of the whole class. Set-scoped queries by
`json_each` on a JSON array — one bound parameter, constant SQL text, no per-call
concatenation, and a fold larger than SQLite's parameter limit is not a different code path.

`_module` had been sending a `holds` key since the day it was built and nothing rendered it,
so the section this adds serves both.

### 2. Two things it was hiding, and one it was not

- **The pane rendered and railed itself.** The auto-rail read `state.selected`, which a fold
  leaves null, so the whole answer was painted into a column **zero pixels wide**. That is
  Tom's *"nothing is visible"* arriving from the other end.
- **The trail filed every box click as "nothing selected"**, for the same reason.
- **The inspector's SQL rows have never shown their table, and the network rows never their
  destination.** `ROUTINE_SQL_OPS` sends `tbl`/`sql`; the pane read `q.table || q.statement`.
  `ROUTINE_NET_CALLS` sends `destination`; the pane read `nc.target || nc.host`. Both render
  as the empty string, so a SQL row was an operation and a line number with nothing between
  them. Rule 44, unrelated to any of this, live since the day it was written.

### 3. The navigator did not follow, and could not

> *"If I click on the menu on the left, the Diagram shows that routine… However, if I click
> inside the Diagram, neither of the other two syncs to it at all."*

Half right on the build he had: the inspector did follow. The navigator marks
`state.selected === r.id` and reveals the same field, so a fold marked nothing and moved
nothing — design rule 26's back half, dead. It marks **every member** now (61 rows), opens
the package and scrolls to the first. Marking all of them is the honest answer rather than
an unfortunate one; Tom raised it as a worry and the alternative is electing a member, which
is the defect this replaces.

### 4. The pointer capture — the one that beat two rounds of verification

> *"I did a hard refresh, but double click still does not open a new diagram or box, and
> click does not change the Inspector view that I can detect."*

`dgmGestures` called `setPointerCapture` on **every press** inside the canvas. A captured
pointer retargets the compatibility mouse events with it, so `click` and `dblclick` arrived
naming `#dgmCanvas` rather than the box: `ev.target.closest("g.node")` was null and every
handler in the view returned having done nothing. **The handlers were correct the whole time
and were being handed the wrong element.**

**Why it survived.** Every check I ran dispatched an event directly at the element it named,
which never touches the pointer path at all — rule 48, and the previous session filed the
same symptom under *"the feedback was in a railed pane"*, which was also true and was not
this. My one real-pointer click passed because `setPointerCapture` **throws** for a
pointerId the automation never made active: the capture silently never took for the
instrument and did for a real mouse. An instrument that cannot reproduce a defect reports
its absence just as confidently as its presence.

Reproduced in the end **without a pointer at all** — a retargeted click *is* a click whose
target is the canvas carrying the coordinates of the press, and that can be dispatched.

Capture is taken on the first move past a 3px slop instead; a drag swallows the click it
ends in, so panning no longer selects what it set off from; and `diagramBoxAt()` asks
`elementFromPoint` what is under the pointer rather than trusting `ev.target`.

### 5. And the drawing moved 139 pixels between the two clicks

The SVG was `width: 100%` with `preserveAspectRatio`, so the **browser** fitted it and
re-fitted on every resize. The first click un-rails the inspector, which narrows the centre
column, which moved the whole drawing out from under the cursor — so the second click landed
on a different box and no gesture could be built on `dblclick`. Once per session, on the
first double-click a reader tries.

Fit is our own transform now against an SVG carrying its own pixel size, deferred rather
than guessed when the pane has no size yet (rule 49). Measured at **0 px** of movement when
the inspector opens. Opening a box is a second click on the same **box id** within 500 ms,
because identity survives a reflow and a position does not.

### 6. The second level, and the way to the code

A box opens into its own routines. `build_inside` returns a **`Compartment`** — the same
type the first level uses — so `dot()` and `mermaid()` draw it unchanged and a fix to one is
a fix to both. `mensores.governance/_authorization.py` opens to 18 routines, 3 boundary
cylinders, 36 flows within, 0 unlinked, in **15 ms**; `KernelDecl` to 61 routines in 93 ms.
Ports there name the far *box* rather than the far plate.

`gotoCodeBtn` / `data-gotocode` is the one way to the code — the location line, every member
of a fold, and every call site when the flow panel lands. `data-box`, **not** `data-fold`:
that attribute has collapsed a pane since design rule 24, so the obvious spelling would have
railed the inspector on every neighbour row (rule 71), caught on the way in.

### 7. Three acts in this view were unreversible

Switching compartment, opening a box, backing out. None changes a *selection*, so every step
they filed deduplicated against the one before it and Back skipped straight past —
pre-existing for the compartment picker. A step's subject carries where the drawing is now.

### What it cost, and what earned itself

**Rule 36's guard paid for itself again**: adding two fields to `_Base` failed
`test_a_switch_rebuilds_every_part_of_the_base` immediately, because a base switch would
have carried the old version's box index into the new base and placed this version's
crossings in the last version's boxes. Nothing else would have noticed.

**The diagram had no behavioural test at all.** A mutation emptying the compartment cache
passed every source-reading guard in the suite — the code was all still there and every
drawing was blank. `tests/test_diagram.py` folds the sample tree, opens its largest box, and
asserts the two levels agree about what they hold.

**A live check read a mutant.** Mid-session, the page reported `state.fold` set while
`inspectorSubject()` returned null — the browser had fetched `shell.js` while the mutation
harness was rewriting it. Rule 56's family: an instrument that modifies the thing it
measures. Do not drive the browser while it runs.

Guards mutation-tested at **46/46** over a proved-green baseline, after 20/20, 30/35, 38/38,
43/46 and 45/46. **Every survivor across all of them was the guard rather than the
mutation** — a step keeping `diagramId:` while dropping `state.diagramId`, a picker
computing the right constant and comparing against the wrong one, a port keeping its lookup
and losing its refusal, a flag set nowhere, one of two early returns, and a slice taken on a
comment `_code()` had already stripped so it ran to the end of the file. That is the
twenty-fourth through thirtieth time in this record.

**Tom, after the last fix: _"Fixed! I love this, thank you!"_**

## Looked at, at the keyboard — Tom, 2026-08-31, on the diagram

Two sentences, and both were defects rather than misreadings.

> *"'tick diagram in the controls box on the right' does not map to anything that I see. My
> Settings for Shapes is set to By Kind, but all nodes are simply dots, as before. When I
> zoom in, the clipping cuts in and nodes disappear."*

### 1. The switch was inside a box he had collapsed

`panels.controls: false` in his stored layout, so `#gdiagram` measured **0×0** and the box
was a 29-pixel strip reading *"size 1.0× · spread 1.00 / 1.00 / 0.35 · plate width 1.00"*.
The switch was wired perfectly and unreachable, which is design rule 16 arriving through a
*layout* rather than through the wiring — nothing in the roster or the self-check can see it,
because there is nothing wrong with the control.

Worse, and this is the part worth keeping: **he went to Settings › Shape, set it to By Kind,
and nothing happened.** That page was a control that rendered and appeared to do nothing,
because the thing it configures is switched on somewhere else entirely. A settings panel for
a mode you cannot turn on from it is the same defect one layer out.

Three fixes:

- **The switch is in the Shape panel too**, which is where a reader who has just chosen a
  shape set is standing when they wonder why nothing changed. `setDiagram()` owns the state
  and both controls go through it — two doors, one implementation, because the second
  implementation always forgets something (here `used()`, which is how design rule 2 retires
  a loser).
- **The collapsed strip names the mode when it is on.** Design rule 25 lets this box fold to
  its summary; design rule 24 already says a strip that makes you open it to find out what it
  was has failed. **A mode inside a box that folds has to be named on the strip it folds
  into** — otherwise the diagram is on, every node on screen is a labelled box, and nothing
  says why.
- The Shape panel says in as many words that the shapes appear when the diagram is on.

### 2. The clipping, and rule 39 named the wrong plane for two sessions

The note on file said the **near** plane: the stack's near half crossing `near 0.1` as zoom
pulls it toward the camera. It reasons well, it was never measured, and it is wrong.

Measured by projecting every drawn node through deck's own view-projection and counting the
ones whose clip-space z leaves `[-1, 1]`:

```
far = 500 (deck's default)      zoom −9 … 7 → 0 clipped      zoom 8 → 4,063 of 15,869
far = 5,000                     zoom −9 … 8 → 0 clipped
```

It is the **far** plane, at `maxZoom` exactly — a cliff at the top of the range rather than a
gradual onset, which is precisely how it was reported. The near plane is never reached at any
zoom this view allows.

`far` is 5,000 now and `near` is untouched. Both things that could have made it cost
something were measured: the on-screen scale is identical to the pixel (24,574.8 px per 100
world units at `maxZoom` either way), and `unproject` round-trips to **zero** error — which is
the check that matters, because the previous attempt at this was a negative `near`, and that
breaks pan and zoom by making the unprojection nonsense. A guard refuses a negative `near`
now, because the geometrically obvious wrong answer is the one a reader reaches for.

**Two general points, and rule 39 is rewritten around them.** A symptom explained but never
measured is an open question wearing an answer; this one was closed with a count over 15,869
nodes and no rendered frame at all, which was available for the whole two sessions it stood.
And it stayed open because it was filed as *tolerable at extreme zoom* — it stopped being
tolerable the moment a feature told the reader to **zoom in for more**, so a defect's severity
is a property of what has been built since, not of when it was found.

### Verified

`far: 5000` on the live view with **zero clipped at every zoom including `maxZoom`**, where it
was 4,063. The Settings toggle found, pressed, persisted and pressed back. Six key rows and
three shape sets rendering. Guards mutation-tested at **10/10** over a proved-green baseline.

Still unseen: the pixels. Rule 38 is unchanged.

## Paused 2026-08-31, with Diagram mode approved

Tom, after the three fixes below: **_"Diagrams look great, love it!"_**

Working tree clean; all three gates green; both mutation suites at 100%; `output/mensores`
untouched and serving on 8899.

**What stands:** the stack at two altitudes with plate widths by content; the comparison over
the code, the routines and the stack; and **Diagram mode** — a compartment drawn by Graphviz
as a real diagram, with Mermaid emitted beside it for export.

**Next, in the order they were left:**

1. **The second level** — opening a box into its own routines. The data bounds it without a
   rule: median 4 to 6, and one module in 623 files exceeds a hundred.
2. **The Mermaid export** Tom deferred — *"a Mermaid drawing of what is rendered, a complete
   set, or per selected plate."* `diagram.mermaid()` already emits it and `/api/diagram`
   already serves it on every compartment; nothing surfaces it yet.
3. **The anomaly worklist overlay**, still blocked on one question — what makes two findings
   in two versions the same finding. A finding carries no id and 93 of Mensores' 106 are
   `LOST_EDGE`, so pairing them would invent an identity (rule 1).

**Withdrawn and not to be rebuilt without reading why:** boxes drawn on the stack at
phyllotaxis positions (a sunflower is not a diagram), and shadows for cross-compartment
edges (the better model, the worse picture — measured, and dropped on Tom's call).

## Looked at, at the keyboard — Tom, 2026-08-31, on Diagram mode

*"Nice progress!"* — and three things, all real.

### 1. Unreadable zoomed in, then crisp when the inspector opened

`will-change: transform` on the pan wrapper. It promotes the element to its own compositor
layer, which is rasterised **once at the scale it had** and then scaled as a bitmap — so
zooming in enlarged a picture of the text rather than redrawing it, and any unrelated
re-layout (opening the inspector) rasterised the layer again and made it crisp. Reported
precisely as it behaves, including the accidental cure.

The property is a performance hint and it is the wrong one here: a **pan** wants the layer,
a **zoom** wants the vector, and the zoom is what a reader does in order to read. Removed.

### 2. No hover card

The stack has one; this had none. It is a fourth entry in `HOVER_HOSTS` (rule 36 — the table
was already there), with one difference that is worth its own flag: **it asks the server for
nothing.** A box is a *fold* — a class and its methods, a file and its functions — so there
is no node id to ask about, and everything a card would say is already in the payload the
drawing came from. `fetches: false` is what stops `showHoverCard` starting a request for an
id the server has never heard of, which would have been a 404 per hover and a card that
filled itself with an error. The card names what a box holds, up to six, and says how many
it left out (rule 8).

### 3. Clicking did nothing visible, and Back could not undo it

The click **did** reach the shared selection and the inspector **did** fill — from the first
version, and I verified it. Tom had the inspector railed, so he saw nothing at all happen.
Design rule 24 lets a reader fold any pane, which makes *"the feedback is in another pane"*
the same as no feedback. The clicked box is marked on the drawing now, two class changes and
never a repaint.

And nothing pushed a trail step, so Back could not reverse the commonest act in the view —
rule 33, and design rule 15's whole argument. Both directions now work: click marks and
selects, Back clears, Forward restores.

**The mark was then correct code reading the wrong source.** `selectedIds()` translates the
*graph engine's* picks, so it answers `{nodes: [], disks: []}` for a session that has never
opened the stack — which is every session that goes straight to Diagram mode. The selection
was real, the inspector had it, and nothing lit. `state.selected` is what the inspector reads
and does not depend on a renderer being mounted (rule 51). Found by driving it, not by any
check.

### Guards

Mutation-tested at **10/10** over a proved-green baseline, after 7/10 — **all three survivors
the guard being weak, and all three the same shape**: a check that accepts *any* occurrence
of a name has not checked the one that matters. One tripped on the comment explaining the
line it was testing; one accepted a second CSS rule mentioning the class after the rule that
draws it was renamed away; one sliced from the port branch, which pushes a trail step of its
own, so removing the box's passed. That is the twenty-first through twenty-third time in this
record, and the fourth in this session.

## Diagram mode — built 2026-08-31

Tom: *"Keep Mermaid as emitted source, but switch to Graphviz for drawing… Add this as
another kind of Graph, not just an option inside Graph. It's a different point of view, like
Table, Document, or Code."*

A fifth centre mode. `web/diagram.py` folds the model into one **compartment** per plate --
a box per class, a box per file's loose functions, a box per boundary kind -- and emits it
twice from one pass: **DOT**, which Graphviz draws, and **Mermaid**, which a reader copies
elsewhere. One model, two emitters, so the picture and the export cannot describe different
graphs (rule 13).

```
53 compartments · boxes median 10, p90 54, max 107 · /api/diagram in 140 ms
pkg:mcp        8 boxes over 134 routines   1.26:1   drawn in  40 ms
pkg:governance 40 boxes over 202 routines  1.13:1   drawn in  31 ms
pkg:quaestor   83 boxes over 487 routines  1.98:1   drawn in  49 ms
```

Graphviz 15.1.0 as `@hpcc-js/wasm` 2.35.0 -- one UMD script tag, 822 KB, the wasm embedded
so there is no second fetch and no bundler, exactly the shape of the deck.gl vendoring.
Loaded **lazily**: most sessions never open this mode, and 822 KB at boot would slow the
screen everyone sees for the one many never do.

### What it does

- **A picker**, and the compartment the current selection sits on when there is one -- five
  modes are five ways of looking at one selection, so arriving here from a selected routine
  lands on its compartment rather than on a default nobody chose.
- **Pan and zoom on a transform**, not a viewBox: the SVG is laid out once and only the
  wrapper moves, so a drag costs a compositor transform and never a re-layout.
- **A box click reaches the shared selection** -- `selectFromNav` with the routines it holds,
  so the inspector fills and the stack lights. A fold that cannot be got back through is a
  filter, and a box that cannot name what it stands for is a shape (rule 30).
- **A port click flips the book** to that compartment, which is the navigation Tom asked for.
- Counts always stated: boxes, the routines they stand for, flows within, crossings, how
  many compartments those reach, and how many boxes have no flow either way.

### Crossings are off by default, and that is rule 19 arriving one level up

Drawn, they do two things and both are bad: they connect what was disconnected so `pack` has
nothing left to pack, and on a small compartment they **outnumber the subject** -- `pkg:mcp`
is 8 boxes to 29 ports. Measured, with Tom's shadow proposal beside it:

```
                no crossings     ports         shadows      nodes: boxes / +ports / +shadows
pkg:mcp            1.26:1        7.69:1        9.52:1              8 / +29 / +67
pkg:governance     1.13:1        2.47:1        4.58:1             40 / +25 / +80
pkg:quaestor       1.98:1        3.43:1        6.64:1             83 / +41 / +175
```

**Tom's shadows are the better model and the worse picture, drawn all at once.** A port says
only which compartment; a shadow names the actual far-side class or file, and 79% of them
would be degree-1 leaves, which layout engines handle far better than a port's hubs. But
either way a single enormous row crosses the picture and swamps the compartment it is about.

**Dropped on his call** -- *"stick with what works, drop the shadow idea"* -- with the
measurement kept as the reason, because the idea is good enough that someone will have it
again. Ports remain as an opt-in switch, because a port has a second job a shadow does not:
it is a **place to click**, and clicking one moves the reader to that compartment. That is
the flip-book, and it is the only navigation between compartments other than the picker.

### One bug worth the name

`boxes` was both a count and a map in the payload -- `**c.stats` carries a box *count*, and
the box map overwrote it, so the page would have read a count off an object. One key meaning
two things is rule 32 in a payload, and it is invisible because both halves are real. It is
`by_id` now, and a guard asserts the map is never keyed `boxes` again.

### Verified

Driven: the mode button, the mount swapping with the graph's, the picker, the crossings
toggle changing the fetch and the picture (8 nodes to 37), a **port click flipping to
`pkg:storage`**, a **box click filling the inspector** with
`mensores.storage._graph_backend.BackendCapabilityError`, the counts, and **no console
errors**. The compartment index is 140 ms; a compartment is 31–76 ms to fetch and draw.

Still to build: **the second level** -- opening a box into its own routines, bounded at 4 to 6
median and 106 at the very worst -- and the **Mermaid export** Tom deferred (*"a Mermaid
drawing of what is rendered, a complete set, or per selected plate"*). The source is already
emitted and served on every compartment; nothing surfaces it yet. Shadows are not on this
list: see above.

## The ribbon, diagnosed and fixed — 2026-08-31

Tom: *"Give up the plate image - let's render what's real and not force it to comply to a
predetermined concept. Is there a better method available for rendering?"*

### The mechanism, measured

The width was never about node count. dagre reserves a horizontal slot **per rank for every
edge crossing that rank**, so long-span edges push neighbours apart:

```
                rows  widest row   median gap between neighbours in a row
weight>=1        21        5 nodes      419 px   (max 1,317)
weight>=5        13        9 nodes      517 px   (max 2,431)
weight>=50        5       14 nodes      178 px   (max   421)
```

Five to fourteen nodes in a row, spread over eight thousand pixels. And the research
confirms the missing lever: **dagre has no component-packing, aspect-ratio or width option
at all** — its entire documented surface is `rankdir`, `align`, `nodesep`, `edgesep`,
`ranksep`, `ranker`, `acyclicer`, `marginx/y`. Graphviz and ELK both have one.

### The fix: Graphviz `dot` with `pack=true`

`@hpcc-js/wasm` 2.35.0, one UMD script tag, 822 KB, **Graphviz 15.1.0** (the research said
16.0.0; the build actually reports 15.1.0), loads in 888 ms, and all seven engines are
compiled in — `dot`, `neato`, `fdp`, `circo`, `twopi`, `osage`, `patchwork`.

```
                      Mermaid / dagre          Graphviz dot, pack=true
pkg:quaestor    15544x1993   7.8:1  3.9 s      1746x1098   1.6:1   62 ms
pkg:cli         11991x 514  23.3:1  2.5 s       782x 744   1.1:1   83 ms
```

**A 37:1 ribbon becomes a 1.1:1 square, thirty times faster.** All 83 boxes are drawn: the
connected flow in the middle, the isolated boxes packed into tidy rows above and below.

**The first attempt at this failed and the failure was mine.** `pack=true` was tested
alongside `ratio=compress, size="14,10"` and the aspect barely moved — because `size` merely
*scales* the finished drawing (1008 px is 14 inches at 72 dpi) and `ratio` fought the pack.
`pack=true` **alone** is the whole fix. A probe that changes two things at once measures
neither.

Other engines on the same input, for the record: `neato` and `fdp` give 1:1 but are
force-directed (hairball risk at scale), `osage` 3.7:1, and `pack` plus `ratio=1.6`
overshoots to 0.6:1.

### What else the research settled

- **Mermaid v11 *can* swap dagre for ELK** — `@mermaid-js/layout-elk`, `layout: elk` in the
  frontmatter — and ELK's defaults are already `separateConnectedComponents: true` and
  `aspectRatio: 1.6`. But mermaid exposes **none** of those options in its config schema, so
  the defaults are all you get; the build is **ESM-only** (no UMD), 1.64 MB; it covers
  flowcharts and state diagrams only; and `maxEdges` defaults to 500, which a whole-program
  view exceeds. Cheap to try, not worth building on.
- **Above about twenty nodes, a matrix beats a node-link diagram on nearly every task except
  path-finding** — Ghoniem, Fekete & Castagliola 2005, replicated at scale since. The
  software form is the Dependency Structure Matrix (Sangal et al., OOPSLA 2005; the basis of
  Lattix, Structure101, NDepend). **An isolate costs one empty row in a matrix and a slot in
  a 23:1 ribbon**, which is precisely this data's problem.
- **Hierarchical edge bundling** (Holten 2006) is the literature's answer for the
  *between*-compartment layer: it bundles adjacency along the containment tree and makes
  implicit parent-to-parent relations visible, which is this tool's subject exactly.
- **Motif simplification** (Dunne & Shneiderman, CHI 2013) is the named answer to "half my
  boxes have no within-compartment edge": collapse the fan into one glyph and state the
  count. That is rule 8 arriving from the literature.

### A correction to my own prediction, caught by testing

From a longest-path count I predicted the between-compartment graph would lay out tall and
narrow — 17 ranks, at most 10 per rank. It *does* rank deeply (21 rows, widest row 5) and
still came out **4.6:1**, for the same edge-slot reason. I was one step from reporting the
prediction as a result.

And a second: a render I recorded as a **failure** (10x10 SVG) was my own regex requiring
`viewBox="0 0 …"` against an actual `viewBox="-35 0 …"`. The render was fine. Rule 24's
family, twice in one session, in the instrument rather than the product.

## The compartment diagram — designed with Tom, and measured before building, 2026-08-31

Tom's design, in his words: *"each set of classes, procedures, and functions be graphed as
Mermaid diagrams that showed the flow within a grouped set such as mensores.quaestor, and
that would be one plate… we might have a summary diagram for each plate that is shown until
you select that plate, and then you go into a Mermaid detail view that allows you pan and
zoom around that plate only… with controls to easily follow links to other plates - sort of
flip-book effect… It's not the same level of detail as the node stack, and that's ok."*

Compartmentalisation, and the stack becomes an **index** into the diagrams rather than the
place the reading happens.

### Settled

- **A new centre mode**, a peer of Table / Document / Code — not a toggle inside Graph.
- **One box per class, plus one box per file's loose functions.** The first form he chose
  was a box per class *and per loose function*; the table I had given him showed classes
  (≤71) and modules (≤83) and he reasonably read those as the box count. They are not:
  Mensores is function-oriented, and quaestor's 42 classes hold only 89 of its 531
  routines, so a box per loose function is **432 boxes**. Gathering a file's loose functions
  into one box restores his ≤100 premise exactly — median **14**, p90 57, max 107, with one
  plate over 100.
- **Real Mermaid, vendored** — 11.17.2, 3.5 MB, fetched with his go-ahead.

### Measured, and the second level is the happy surprise

```
level 1, a package     median  14 boxes   p90  57   max 107
level 2, opening one   median   4-6       p90  14   max 106  (one module in 623 files)
```

The drill-down is bounded at every level *without a rule to bound it*, because the code is
already compartmented. That is what makes the design work and it was not obvious before
counting.

### Three things established by testing rather than by reasoning

- **`deck.BitmapLayer` is in the vendored build and constructs.** A bitmap on a quad in the
  plate's own XY plane at the plate's Z is the diagram lying flat — Tom's "rendered
  orthogonally" exactly, and undistorted under this projection apart from the tilt.
- **An SVG carrying `<foreignObject>` will not rasterise into a canvas.** Plain `<text>`
  gave 623 ink pixels; the `foreignObject` version never decoded at all, in the same tab, so
  it is the markup and not the environment. Mermaid uses `foreignObject` for labels by
  default, so it **must** be initialised `htmlLabels: false` or every plate image is
  silently blank. Recorded in `vendor/VERSIONS.json` where the next reader will meet it.
- **Mermaid renders these, and the small ones are excellent.** `pkg:mcp` at 8 boxes is a
  proper diagram — routed edges, arrowheads, labels reading *"4 methods"* and *"3
  functions"*.

### And the finding that stops the build: the diagrams are ribbons

```
                boxes  ports  isolated   svg size      aspect   render
pkg:quaestor       83     41        27   15544×1993     7.8:1    3.9 s
pkg:storage        90     32        27   17433×1296    13.5:1    2.6 s
pkg:cli            57     35         5   11991× 514    23.3:1    2.5 s
pkg:disceptator   107     26        35   16453×1296    12.7:1    3.3 s
```

**It is not a Mermaid failure, it is the shape of the data.** Half of each package's boxes
have no within-package edge at all — quaestor has 83 internal edges against 221 outbound —
and `flowchart TD` puts everything with no inbound edge on rank 0, side by side. The
verification that this is real rather than a folding bug: the drawn model and the store's own
`calls` rows agree to the edge, on every plate.

Adding Tom's cross-plate links as **ports** was the obvious fix and it is not one. It
improved connectivity (quaestor 41 isolated → 27) and left the aspect ratio no better,
because a package's call graph is inherently **wide and shallow**: two to four ranks, dozens
of boxes per rank.

Two consequences, and both are for Tom:

- **A 23:1 ribbon cannot be a plate image.** A plate wants something near square.
- **2.5–3.9 s per plate** means the stack of 53 costs minutes to build, so the summaries want
  caching on disk rather than rendering per session — if they are kept at all.

Nothing further is built. The next decision is his: whether the plate summary survives in
some other form, whether the diagram accepts being a wide thing you pan (which is how a real
Mermaid diagram of this size is normally read), or whether the level-1 grain moves again.

## Withdrawn — Tom, 2026-08-31, on the plate diagram

> *"Diagram mode is unreadable, and inconsistent… My original concept for this was a valid
> Mermaid diagram laying on its side — create the Mermaid diagram first, then render it
> orthogonally, and stack them up… This is just nodes that are boxes, that's totally
> different. Mermaid diagrams have completely different layouts than graph plates, they use
> a different layout algorithm."*

**He is right, and the acceptance test he set before it was built is the one that applies:**
*"they must be easy to read or we have failed"*, with the instruction to withdraw rather
than ship with a caveat. Withdrawn.

### What I built, and why it was never going to work

A labelled box for everything the selection lit, **at the position the plate layout had
already given each node** — and that layout is `phyllotaxis`, a sunflower. `layout.py`'s own
docstring said so all along: *"That ordering is the only structure this layout imposes."*
Boxes at sunflower positions are not a diagram. Nothing is ranked by what calls what, so
every edge crosses every other and a reader gets a field of names rather than a picture of a
flow.

**A diagram's readability comes from its layout algorithm, not from the outline of its
nodes**, and I spent the chunk on the outlines. The shape sets, the box text, the pixel
sizing, the placement and its overflow rule are all correct components of the right view;
none of them was the thing that mattered.

The question I put to him — *what becomes a box* — was the wrong question, and it was wrong
in a way worth naming. It took the existing picture as given and asked which nodes to
decorate. The record's own words for the request were *"draw a plate as a diagram, not as a
field of dots"*, and the operative word is **draw**, not *decorate*.

### Two smaller failures, both real

- **The glyphs render scrambled** — `selected_backend` came out as `s/lec-uh-cc-e·u`. The
  rasterised preview could not have caught this and its caveat predicted it in as many
  words: it draws the geometry deck was handed, not deck's own text. `sizeUnits: 'common'`
  on a non-billboarded `TextLayer` is the first thing to suspect in the rebuild.
- **Some lit nodes stayed dots beside boxes at a selection of eight**, where everything
  should have fitted — the placement's overflow answer arriving where there was no crowd to
  answer for.

### What is kept, and what the rebuild needs

The two controls are gone and everything else stays: `setDiagram` survives so there is one
door to reopen rather than two to rebuild, and a guard asserts the **absence of a door**
until `layout.py` has a layered layout. The engine's `diagram` option defaults off and a
guard holds it there.

The rebuild is a **second layout beside `structural()`, not a replacement** — design rule 2's
own shape, and for its reason: the sunflower is right for ten thousand dots and wrong for
eighty boxes, and the reverse. Ranks assigned by call direction, ordering within a rank
chosen to reduce crossings, then coordinates; computed where the rest of the layout is
computed, deterministically and with no random number generator, which that file already
requires.

`layout.py` now records this at `structural()` so the next reader does not repeat it.

## The inspector could not be collapsed while it was empty — fixed 2026-08-31

> *"When Inspector shows 'Nothing selected.', there is no method to collapse the panel. You
> must find something that will display there before the collapse button will appear."*

Its fold control lived in the header of a **populated** specimen, so the two states that
return early — *"Nothing selected"* and *"Not in this map"* — rendered without one. Design
rule 24 says every pane folds and folding leaves a rail, and the pane that most needs it is
precisely the one with nothing to say: the inspector holds 22rem to report that it is empty,
which is the whole reason it rails itself in the first place.

It is painted at the **paint site** now, before the content, so no branch of any renderer can
drop it again — structurally outside every `return` the content has (rule 36).

**And the first fix was wrong in a way rule 48 does not catch.** Moved out of the header it
carried `style="float:right"`, and the inspector is a flex column: **a flex item ignores
`float`**, so the button stretched to the full 351px and read as a bar across the top of the
pane. `elementFromPoint` said it was reachable, and it was — hit-testing says a control is
under the cursor and says nothing about it being the width of the pane. `align-self` on a
`.pane > .panefold` rule, and it measures 16×16 where it should.

Guards mutation-tested at **6/6** over a proved-green baseline.

## The plate as a diagram — built 2026-08-31

**`6l`.** The second recorded feature request, and the one carrying an acceptance test:
*"The goal of the Mermaid diagrams is to aid in understanding, so they must be easy to read
or we have failed."* Three questions went to Tom; he answered one, asked to clarify, and
then settled the other two.

### What Tom decided

- **Boxes for whatever is lit.** No new idea to learn: picking a plate already lights every
  node on it and picking a routine lights it and its one hop, so "the lit set" is the
  reading loop drawn as a diagram rather than as dots. Median 3 boxes from a routine (p99
  16), 6 to 991 from a plate.
- **Shape carries kind — and is selectable in Settings.** His words: *"Shape can carry kind,
  but should be selectable in Settings, that's my only request."* Offered as **sets**, the
  way the colours are: *By kind*, *All rectangles*, *All rounded*.
- **Box what fits, dot the rest, state the number.** Placed busiest-first and only where they
  do not overlap at the current zoom; zooming in turns more dots into boxes.

### Two things the data settled before any of that was asked

- **Names are box-sized; boundary targets are not.** Routines, constants, structures and
  artefacts run a median of 13 to 18 characters with a 99th percentile of 37. Boundaries are
  70% over 30 characters, median 50, **max 1,388** — a whole embedded Python program —
  because a boundary's label is the *expression it touches* rather than a name.
- **That decision then changed once shape started carrying kind.** The first version led a
  boundary box with its kind (`DATABASE`, `STDIO`), which was right while colour was the only
  thing saying what a node is. It is wrong now: the stadium outline already says *boundary*,
  so the box would spend its one line repeating the shape while dropping the only thing shape
  cannot carry. It says what it touches, prefixed by the direction, elided at 28 characters
  with the card holding it whole — rule 8 forbids truncating at *ingest*, and a bounded
  diagram beside the complete content is what it explicitly allows.

### The billboard question, answered at one angle and only one

This is the *"To be determined…"* Tom left open, and it was left open on purpose: rule 22
billboards a node because a sphere **has no orientation**, and a labelled box does — it has a
top and a reading direction — so one held facing the camera has stopped lying on the plate it
belongs to. His instruction was to build it flat and find out whether there was a problem at
all. There is, and **it is not where either of us expected**:

- **The tilt costs nothing.** At 35° a label loses 43% of its height and stays perfectly
  readable. Foreshortening was the thing the question was about and it turns out not to matter.
- **The orbit costs everything.** Text lying in the plate inherits the in-plane rotation, so
  turning the stack 20° turns every label 20°, and looking *straight down* at a plate — the
  one view where a plate is an undistorted diagram — gives a page of names set on a diagonal.
  Top-down was **worse than tilted**, which is the opposite of what the reasoning predicted.

So a box gives up its bearing and nothing else: **turned about Z alone**. It still lies flat,
still foreshortens with the tilt, still reads as something *on* a plate, and its reading
direction faces the reader at every orbit angle. At orbit zero it is identical to leaving it
alone, which is the test that it takes nothing away. The other two axes stay exactly where
flat put them.

### What it looks like, and how that was seen at all

Rule 38 stands: the automation tab gets **zero animation frames** — measured, 0 in a second,
and resizing the window to 1600×1000 changed nothing — so deck's canvas never leaves its
300×150 default and the renderer draws nothing to screenshot.

So the geometry was **rasterised** instead: `draw()` builds its layers synchronously, so the
boxes, their outlines, their colours and their text are all in `props` without a frame ever
happening, and a 2D canvas can draw them through deck's own viewport. Every number came from
the layer's own accessors — `getPolygon`, `getLineColor`, `getAngle` — so it is the renderer's
geometry and not a second copy of it. **It is a picture of what would be drawn, not a
screenshot of the renderer**, and it is recorded as one.

That harness got it wrong twice and both are worth keeping:

- **It built its viewport without `orthographic: true`**, which is deck's default of
  *perspective* — a different projection from the one design rule 20 chose. Every number it
  had produced was about another picture: box counts, the overlap check, the lot. Rule 24 in
  my own instrument. Caught by measuring pixels-per-world against `2 ** zoom` and finding 39
  where 132 was owed.
- **It drew the labels mirrored**, because canvas Y runs down and the plate's Y runs up. The
  first screenshot was a page of backwards text — the harness lying about the renderer rather
  than the renderer being wrong.

And one risk was closed by reading rather than by looking: deck's `getAngle` sign convention
for non-billboard text. `rotate_by_angle` in the vendored bundle is a column-major *clockwise*
matrix followed by `pixelOffset.y *= -1.0`, which is net **counter-clockwise in the world XY
plane** — the same convention the harness used, so the pictures are faithful on the one point
the whole fix turns on. That is rule 22's own history taken seriously: three times the sphere
shading compiled, drew, and silently did nothing.

### Measured on Mensores

```
pkg:mcp, 360 lit          496x361  → 21 boxes    900x600  →  55
                         1280x760  → 102 boxes  1920x1080 → 157
pkg:quaestor, 1,319 lit  1280x760  →  86 boxes, 1,233 still dots, placed in 2.3 ms
```

The dots and the boxes sum to the lit set exactly, at every size, and the count line says so:
*"102 boxed · 258 still dots — zoom in for more"*. Zero overlapping pairs among the placed
boxes, checked by re-projecting them off the layer deck was handed.

### What is verified, and what is not

Driven: both shape sets and the six outlines they produce, the switch, the placement at four
window sizes, the sum against the lit set, the overlap check, the cost, the count line, the
cross-plate crossings drawn beside the boxes (`sel-edges` and `inter-edges` both present with
`boxes-kind` and `box-labels`), and the settings surviving a reload.

**Not verified: the renderer's own pixels.** Everything above is the geometry deck was given,
drawn by a second rasteriser. The one thing that cannot be checked this way is whether deck's
TextLayer puts the glyphs where the harness put them — the convention is read out of the
shader and matches, but reading a shader is not seeing it. **This wants Tom's eye more than
either of the last two chunks did**, because it is the first one whose whole point is what it
looks like.

**The weakest thing in the picture is not the boxes.** With 360 lit and 149 within-plate
links, the edges are a hairball behind them. That is the existing edge rendering rather than
anything this chunk added, and it is the next thing to look at if the diagram is kept.

Guards mutation-tested at **23/23** over a proved-green baseline, after a run at 20/23 —
**all three survivors the guard being weak**, which is the eighteenth through twentieth time
in this record. Two were the same shape twice: a check asking whether a name appeared
*anywhere* in a function, passing a mutation that left a second occurrence standing (rule 59's
companion). The third was a genuine gap — nothing asserted the mount hands `diagram` and
`nodeShapes` to the engine at all, so deleting that line left every guard green while the
switch would have been persisted, restored, drawn checked, and never reached the renderer.

**No new numbered rule.** The billboard finding belongs to rule 22 and is recorded there; the
shape-as-a-set argument belongs to design rule 4 and is recorded there; everything else is
rule 24, rule 59's companion, and design rule 1 in new costumes.

### Paused 2026-08-31, after the diagram

Working tree clean; all three gates green; both mutation suites at 100% (24/24 for the plate
widths, 23/23 here); `output/mensores` untouched.

**Three chunks now rest on a picture nobody with a real window has looked at**: the second
altitude, the plate widths, and this. `dunneflow serve output/mensores`, then the *diagram*
switch in the controls box beside *plates*, and Settings › Shape for the outlines.

**Still open and unstarted:** the anomaly worklist overlay, blocked on one question — what
makes two findings in two versions the same finding.

## Sizing a plate by what it holds — built 2026-08-31

**`6k`.** The first of the two recorded feature requests, and the smaller one. Three
questions went to Tom before any code and he took all three recommendations.

```
routine   largest ext:STDIO 991 · smallest ext:<small outside> 6   → 12.85x on radius
module    largest pkg:_internal 85 · smallest 3                    →  5.32x on radius
```

### Three things settled before writing anything

- **It belongs in the client, not `layout.py`.** `phyllotaxis` is radially uniform, so
  scaling a plate's placed coordinates by a factor is *exactly* computing it at a smaller
  radius — which makes plate width a view property like Z and the spreads, reversible from
  the unscaled base the engine already keeps, live with no round trip, and correct at both
  altitudes from payloads already in hand. `layout.py`'s note is rewritten as the reversal
  it is; a guard written in the last session for exactly this moment reversed with it.
- **The anchor is arithmetic, not a decision.** Nodes are `radiusUnits: 'pixels'` and
  `fitView` frames whatever it is handed, so anchoring at the largest plate and at the
  smallest are the same picture at different zooms — under an orthographic projection
  uniform scaling *is* zoom (design rule 22). Largest is chosen only so nothing grows past
  the radius the server placed it at. **Measured: the bounding cylinder is 999.8 x 3391.5
  at both ends of the dial**, so design rule 20's framing never moves.
- **Tom's "nodes, not nodes + shadows" answer is right, and now there is a reason.** A
  shadow is never drawn (rule 23), so the density a reader *sees* is real nodes over area
  however many placement devices share the disc — `ext:<outside>` carries ten nodes and 378
  shadows and has to read as ten. Sizing on the total would draw it six times too wide,
  equally plausibly.

### What Tom decided

- **Full on by default (1.00)**, with the uniform stack one drag away. At fit zoom the
  smallest routine plate is ~56 px radius holding nine nodes, so nothing clumps.
- **In the HUD controls box, with the spreads**, because it multiplies them and answers the
  neighbouring question — they widen every plate together, this says how much of that width
  each plate has earned. Live, no fetch, per level under the hood.
- **One scale for the whole stack**, code and externals alike. The consequence is that the
  widest plate on Mensores is `ext:STDIO`, 991 stdout strings, sitting below the code in the
  band that already reads *the program, then what it touches*. Honest, and design rule 8
  says externals are first-class.

### Called width, not density — and that is the find worth keeping

`density` is **already a setting in this product**: the table's row height. One word for two
ideas, in a tool whose entire subject is a program's vocabulary, is the `disk`/`plate`
collision `settings.js` still carries a debt for. Caught before it shipped rather than
after, and there is a guard now — over what a reader can *see* (the label, the aria-label,
the collapsed ribbon), never over the span, because the note explaining why the word is
avoided is written beside the control and a guard tripping on that is rule 37 in its purest
form.

### Everything on a plate's circle asks that plate how wide it is

Three things sit on it and they were three expressions built from one constant: the nodes,
the plate's own outline, and the you-are-here arrow standing on its rim. Correct while every
plate was one width and a lie the moment one is not — an arrow on the largest plate's circle,
for a node on a plate a tenth as wide, is still on the right bearing and no longer on the rim
of anything. Rule 51: one number described the whole stack until it did not.

### `followMode` has never survived a reload, and no guard could see it

Found while mutation-testing. `followMode` is declared in `DEFAULTS`, set by a live control
that calls `persist()`, and named in the reset dialog — and it was **not in `PERSISTED`**,
which is the only list `persist()` walks. So design rule 2's "build both and let real use
retire the loser" has been retiring on a coin toss per session.

`test_every_persisted_key_is_a_setting_the_store_knows` was written for exactly this failure
and ran **one direction only** — written and unknown, never declared and unwritten. Both
halves are the same defect. Rule 37 again: a guard that names the right case in one direction
has not checked the other.

### What is verified, driven in Chrome

- The widths reaching the engine are `sqrt(n / nmax)` to the last digit: min **0.09529814**
  against an expected **0.09529814**.
- **The dial comes home.** At 0 every factor is exactly 1 and the worst node is 3e-5 world
  units from the payload's own coordinate on a 2000-unit stack — Float32 rounding, not
  compounding. At 0.5 the minimum is 0.5476, which is the interpolation exactly.
- **Per level, and it travels.** With routine on 0.40 and module on 1.00, each altitude is
  drawn to its own value on arrival and the store holds `{routine: 0.4, module: 1}`.
- **The reset names what it cleared** — *"back to defaults: plateSize"* — and restores that
  level.
- Every plate's drawn nodes sit inside that plate's own scaled radius, and each outline is
  that plate's own circle at `PLATE_R x factor` to the tenth of a unit.
- The row is laid out below *stack*, sized like its siblings, and `elementFromPoint` returns
  the slider itself (rule 48 — wiring and reachability are different claims).
- Clean load, self-check green, **no console errors** — the one place the last session's
  half-hour defect had been shouting.

**What it looks like is not verified.** The HUD reads **0 fps** and deck.gl's canvas is
stuck at its default 300x150, because `ResizeObserver` never fires in a browser-automation
tab: rule 38, and it is the same absence the second altitude was paused on. The picture
wants Tom's eye.

Guards mutation-tested at **24/24** over a proved-green baseline, after a run at 22/24 — one
survivor was the guard being weak (it asked whether `d.diskScale` appeared *anywhere* in
`plateWidths` and passed a mutation that read the ratios for the numbers while still testing
`diskScale.size` for emptiness — rule 59's companion: a mutation that leaves any read of the
thing standing has not removed it, and a guard that accepts any read has not checked the one
that matters). The other was a stale mutation, not a weak guard.

### Two things found in the guards themselves

- **Two `_fn` helpers with one name**, and the later definition silently won for every caller
  of the earlier — so a guard could be written, reviewed and mutation-tested against a helper
  other than the one beside it. Rule 51 one level up. One of them now, the brace-depth version,
  because a check for what a function does *not* contain is only as good as the span it is
  taken over.
- **And that one was wrong for a destructured parameter.** `setGraphDetail({ level, minDisk })`
  opens and closes a brace in its *signature*, so counting from the first `{` returned the
  signature and nothing else. Four existing guards caught it — because a presence check over an
  empty span fails loudly, where an absence check would have passed vacuously and for ever.

**No new numbered rule.** Every finding here is an existing rule in a new costume: 51 for the
one constant that described the whole stack, 37 for the guard run in one direction, 59's
companion for the guard that accepted any read, and the vocabulary collision is the `disk` /
`plate` debt arriving a second time.

### Paused 2026-08-31, after plate sizing

Working tree clean; all three gates green; `output/mensores` untouched.

**Next: chunk 3, the plate as a diagram** — flat first, no billboards until there is a problem
to see (Tom's call), on one plate or a selection, at the altitude that makes it a readable
number of boxes. His bar stands: *"they must be easy to read or we have failed."* Withdrawn
rather than shipped with a caveat if it does not clear it.

**Still owed: Tom's eye on both this and the second altitude.** Two chunks now rest on a
picture nobody with a real window has looked at.

**Still open and unstarted:** the anomaly worklist overlay, blocked on one question — what
makes two findings in two versions the same finding.

## The second altitude — built 2026-08-31

**`6j`.** Tom's density complaint, answered. Three questions were put to him before any code
and all three answers are load-bearing.

> *"level-of-detail sounds right to me as well, let's build that. Remember, keep what we
> have, this is another way to view the same information."*

```
routines   10,015 nodes · 14,254 edges · 52 plates · largest plate 926
modules       578 nodes ·  1,505 edges · 38 plates · largest plate  85
```

The argument for it was already in this file, written for request B: *if a plate cannot be
read at a useful number of nodes, the number of nodes is wrong rather than the projection.*
Neither recorded feature request changes the number of things on screen; this does, by
seventeen times, and it is what makes both of them worth building afterwards.

### What Tom decided

- **Level of detail first**, before plate sizing and before the diagram renderer, because
  it changes what those two are for.
- **Externals fold by kind.** 1,920 of the 10,015 are boundary targets with no module — 991
  individual stdout strings, 408 SQL statements — and left alone they are 77% of the module
  picture and answer nothing the altitude asks. They become nine nodes on one plate below
  the code, `ext:<outside>`. One word rather than "touches", because artefacts land there
  too and naming a file is not touching one (rule 17).
- **`MIN_DISK` becomes a Setting**, per level (design rule 2). What a plate *holds* changes
  with the level: 8 folds 21 of Mensores' 45 packages away at module level, 3 folds 7.
  Defaults 8 and 3, the reader owns the value, and the count of what it merged is stated.
- **A module takes the change band of what it holds, and `mixed` says so.**

And two answers for the work that follows, recorded so they survive: plate sizing is on
**nodes**, not nodes + shadows — *"shadows was just an idea due to the 3D aspect, not a
requirement"* — and the diagram is built **flat first**: *"billboard is my proactive
approach to what might be a problem... let's build it without billboards first and
determine if there is a problem to solve at all."*

### The shape, and the one thing that must not be done

A module-level `GraphModel` is an ordinary `GraphModel`, which is why this is small:
`structural()`, `phyllotaxis`, `disk_heights`, `columnar()` and every line of the renderer
work on it unchanged. The fold happens **on the way in from the store**, in `_add_edges`,
where every call, touch and naming is seen exactly once. Never over `m.edges`: the 2.5D
model holds each crossing twice by design (rule 23), so aggregating the drawn model would
double every weight silently and plausibly. `packages.py` wrote that warning down before
anything needed it.

`mod:` and `outside:` join `const:`, `bnd:` and `art:` — the id is what tells the inspector
what it has been handed — and `detail.py` answers for both. A module card lists what the
file declares in full (rule 8) and names its neighbours as **modules**: 85 names a reader
can act on where the 1,400 calls under them are the haystack again (rule 45).

### `same` is the ground, and that was measured before it was built

A module holding one arrival and forty unchanged routines is a module something arrived in,
not a mixed one. Counted the other way — any two distinct bands make it mixed — **every
changed file on Mensores reads `mixed` and the tone says nothing at all.** With `same` as
the ground:

```
568 modules:  552 unchanged · 7 mixed · 4 with something deleted · 3 behave differently
              …and 12 not compared, which is the outside plate and two files declaring
              no routine at all
```

Fourteen files carry the whole comparison. That is the case for the altitude in one line.

### The colour channel is full, and that is the session's second find

`mixed` needed a sixth colour, and the sweep says the difference channel has no room left.
Every hue at every saturation and lightness, against every colour in all three sets plus
the two grounds, in normal vision, deuteranopia and protanopia: **nothing clears a useful
bar in both themes.** Light is the binding constraint — red, orange, green, blue, violet,
purple and two greys are spent, and what remains is yellow, which cannot hold 3:1 on a
light ground.

So the pair shipped is the best available rather than a good one, and it says so: worst
**ΔE 29.8 light and 45.3 dark** within the channel, against the shipped red/green pair's
12.7 and 9.5. It sits with `--graph-unchanged` and `--graph-unclaimed` rather than in the
sets, on the argument those two already make: a set covers the *directions* of difference,
and "more than one direction" is not one of them. **Rule 69 gains the general point** — a
seventh meaning cannot be added by colour at all, and the next one wants another channel.

`MODULE` needed a kind colour too, measured the same way: worst ΔE 42.7 light and 51.7 dark
against the other five. Its nearest neighbour anywhere is `--graph-mixed` at ΔE 20.8, and
the two are never on screen together because `colorBy` spends the channel on one dimension
at a time (design rule 4).

### Two things found that were already there

- **A small *external* plate has been merging onto `pkg:<small>`, a package plate, since
  the day `<small>` existed.** On Mensores that is the four QUEUE targets, the unnamed QUEUE
  touch and the one LLM_API endpoint, drawn among the code that reaches them and badged as
  ours — design rule 8's exact claim, inverted. Nothing could see it, because a merged plate
  is *supposed* to hold things from elsewhere; it surfaced only because making the threshold
  settable made it reachable at any size. Each band merges into its own plate now, and the
  two carry different names or the legend says one word for two plates (rule 32). Mensores'
  routine level is 53 plates rather than 52 as a result.
- **The module card and the module node disagreed about `holds`** — three fixed keys against
  a count of what is there, so a file declaring only routines read "0 constants" in one
  place and nothing in the other. Rule 13 between a card and a node, caught by the guard
  written to compare them.

### Three defects found by driving it, and the first one is the lesson

- **The switch pushed the shell's plate order back into an engine that had just resolved
  one.** One truth in two places (rule 51) — and on a fresh session there is no saved order
  at all, so it handed `setOptions` a `null` and `applyLayout` threw. **Every switch, from
  the first.** Everything after the throw was skipped, so the selection never travelled and
  the note that would have said so was never written. The page looked exactly like a page
  that works.

  **The console had said so from the first attempt and I did not read it.** Half an hour
  went on a defect that was announcing itself in the one place nothing else looks. That is
  the same finding the `data-nav` collision produced ("found by reading the console, which
  no test does") and it did not transfer.

- **`window.__d` and `window.__graph` were written once in `mount`**, so after a switch they
  described 15,870 routine-level rows while the engine drew 2,069 module-level ones. Design
  rule 21 puts diagnostics where a developer can reach them; one that lies is worse than
  none, and this one sent me looking in the wrong place for most of that half hour. They
  follow the payload now, asserted as **one writer** rather than as present in a function.

- **`ensureGraphChange` loads the routine list for the module fold and repainted only
  itself**, leaving the other reader saying *"reading the routine list…"* over an answer that
  had arrived. Rule 55 in the guard as well as the code: the check written for that exact
  defect sliced from the **first** `loadRoutines()` in the file, so a caller added above it
  inherited a guard looking somewhere else. It walks every call site now.

### What is verified, and what is not

Driven in a real Chrome window: both levels served and consistent, the control, the
threshold slider (25 plates at 8, 38 at 3, 47 at 1, each stating what it merged), the
selection travelling in both directions over three shapes — a plate, one routine, and a way
in resolving to 107 routines which became *"the 44 nodes holding them"* — the change key
summing to 578 at module level and unchanged at routine level, and every band reaching the
colour buffer with its own value including `mixed` at `#00007a`.

**What it looks like is not verified.** The HUD reads **0 fps** in that tab: rule 38, a
browser-automation tab is given no animation frames, so nothing needing a rendered frame
exists there. The picture wants Tom's eye, and the frame rate at module level is written in
`CLAUDE.md` as an absence rather than a guess.

Guards mutation-tested at **49/49** over a proved-green baseline, after runs at 22/24 and
47/49 — **every survivor the guard being weak**, which is now the fourteenth through
seventeenth time in this record. Two of them were the same substring trap one guard apart:
`st.disks_merged` inside `st.disks_merged_nodes`, as `window.__d` sits inside
`window.__deck`.

### Paused 2026-08-31, after the second altitude

Working tree clean; all three gates green; `output/mensores` untouched and still serving
both revisions. Three commits: the model and the server, the client, and the record.

**Tom has not looked at it yet, and that is the one thing owed.** Everything checkable
without a rendered frame is checked — the counts at both altitudes, the control, the
threshold, the selection travelling in both directions over three shapes, the change key
summing to the drawn total, and every band reaching the colour buffer with its own value.
The HUD reads **0 fps** in a browser-automation tab (rule 38), so the picture itself has
been described and not seen. A `dunneflow serve output/mensores` and the *Detail* selector
in the legend is the whole of what wants an eye.

**Read the verdict as a worklist when it comes**, as the last one was: *"the stack is
legible enough to say what changed and not yet legible enough to explore"* is the sentence
this chunk was built to answer, and whether it did is not something I can tell from here.

### Next

**Chunk 2: size a plate by its density**, and it is unblocked and re-shaped by this. `r =
DISK_RADIUS * sqrt(n / n_ref)` on **nodes** (Tom's answer), a Setting, with `layout.py`'s
`DISK_RADIUS` comment rewritten as the reversal it is rather than left standing to
contradict the code. Two things this session changes about it:

- **The range is not 31×.** That note assumed a smallest plate of 1; `MIN_DISK` puts the
  floor at 9, so it is 110× on count and **10.5× on radius** — awkward but not the specks
  the note feared, and it may need no clamp at all, only a check that design rule 20's
  framing still holds.
- **It is now a question about two pictures, not one.** At module level the largest plate
  holds 85 and the smallest 1, which is a different range and a different judgment. The
  Setting is per level or it is wrong at one of them — the same argument `MIN_DISK` just
  had.

**Chunk 3: the plate as a diagram**, flat first, on one plate or a selection, at the
altitude that makes it a readable number of boxes. Tom's bar stands: *"they must be easy to
read or we have failed."* Withdrawn rather than shipped with a caveat if it does not clear
it.

**Still open and unstarted:** the anomaly worklist overlay, blocked on one question — what
makes two findings in two versions the same finding. A finding carries no id and 93 of
Mensores' 106 are `LOST_EDGE`, so pairing them would invent an identity (rule 1).

## Looked at, at the keyboard — Tom, 2026-08-30, after the stack's change colours

The pixels `6h` said it owed a real window. Read as a verdict *and* as a worklist.

**What works.** *"The colors are a reasonable differentiating factor, and the edges do seem
to make sense."* That closes the item `6h` left open: the palette, the tones and the
crossings were driven as data and are now confirmed as a picture. *"An absolute delight to
work with so far"*, and the chunk is approved.

**What does not, and it is one sentence with three problems in it.** *"A graph with this
many nodes and edges is hard to comprehend… It may take some additional work to get the
view filtering improved for exploring, especially when manipulating the filtered stack and
trying to understand it without accidentally changing the filter by clicking on and off
nodes, which changes the focus. I have to use Back too often, and it doesn't always do what
I expect."*

### 1. Back is two histories, and the visible one is blind to the commonest act

> **Fixed 2026-08-30, see `6i` — one history.** What follows is the diagnosis as it stood,
> kept because the reasoning about the cap is what shaped the fix: the trail bar bounds
> itself now and the history does not.

**Read from the code rather than reproduced, and it is structural rather than behavioural.**
`onGraphSelect` (`shell.js:8298`) calls `recordSelection()` — the ⌘Z selection history — and
**never `pushTrail`**. So clicking a node in the picture leaves no trail step at all.

The visible **← Back** button (`shell.js:5893`) pops `state.trail`, and `pushTrail` is called
from fifteen places: mode toggles, layout changes, navigator rows, glossary terms, threads,
the inspector, the detail window, the other browser window. **Not from a click in the stack.**

So there are two answers to *where have I been*:

| the act | recorded in `selHistory` (⌘Z) | recorded in `state.trail` (← Back) |
|---|---|---|
| click a node in the picture | yes | **no** |
| click a row in the navigator | yes | yes |
| change mode or layout | no | yes |

A reader exploring the stack does almost nothing but click nodes, so the button labelled
Back is precisely the control that cannot reverse what they just did — while ⌘Z, which can,
is invisible. That is rule 51's shape (two places each holding their own answer to one
question) crossed with rule 30's (the visible control's subject is not what the reader takes
it to be). It matches the report exactly and it was never designed; it accumulated.

**Do not simply make `onGraphSelect` call `pushTrail`.** Every graph click would become a
trail step, and the trail is capped at `state.trailCap` (12 by default) — chasing a thread
across a plate would flush every earlier step, so the feature design rule 15 says makes a
detour free would lose the thing the reader detoured *from*. The question to answer first is
whether the trail and the selection history should be **one** history with one visible
control, or stay two with the second one named and reachable. That is a design decision and
it is Tom's.

### 2. Clicking to look changes the filter

> **Half-answered 2026-08-30 by `6i`.** Rule 33 kept the toggle on the grounds that undo
> makes it recoverable; that is now true through a visible control, and driven: clicking the
> node you are on empties the picture and **one Back restores it**. Whether the toggle
> should still exist is a separate question and wants Tom's eye.

*"…without accidentally changing the filter by clicking on and off nodes, which changes the
focus."*

This is `togglePick`'s deliberate toggle-off meeting the fact that a click is also how you
*move*. Rule 33's companion records the trade already: clicking the node you are looking at
clears the whole selection, the toggle is kept because clearing by clicking is right, and
*undo makes it recoverable* — which is exactly the recovery that finding 1 says is behind an
invisible key. The two problems are one problem.

With edges on demand (design rule 19) the selection **is** the filter, so a stray click does
not merely deselect: it empties the picture. Worth considering: a separate *inspect* gesture
that answers "what is this" without moving the selection, or making the selection sticky
until something explicitly clears it. Neither is decided.

### 3. The picture is too dense to comprehend, and that is not new

*"A graph with this many nodes and edges is hard to comprehend."* 10,015 nodes and 14,254
edges. Rule 18 already says the plates are not drawn and the dots are 1.4–3.6 px precisely
because anything larger fuses; rule 22 records that at 14× they occlude the edges they are
drawn with. **This is the observation the two recorded feature requests exist to answer** —
sizing a plate by its density, and drawing a plate as a readable diagram — and it is the
reason Tom's bar for the second one is *"they must be easy to read or we have failed"*.

So the three are one line of work rather than three: **the stack is legible enough to say
what changed and not yet legible enough to explore.**

### Paused 2026-08-30, after the stack's change colours

Working tree clean; all three gates green; `output/mensores` untouched and still serving
both revisions.

**The overlays are complete.** Code, routines, and now the stack. Colour by *what changed*
takes the channel over, the crossings keep their plate gradient, and the key states all five
bands — including the two a reader could not otherwise account for: the 15 edited routines
folded into unchanged, and the 5,229 nodes the comparison was never asked about.

Six defects found by driving and one by a guard catching an edit that had been silently
lost. The measurement that was expected to block the chunk did not: a third difference
colour clears rule 69 comfortably in every set, and the finding is that the *shipped*
red/green pair is the weakest thing in the product at ΔE 9.5.

**The real window has now happened**, and the verdict is in the section above: the colours
and the edges work, the chunk is approved, and the picture is *hard to comprehend at this
density*. Three things came out of it, and they are one line of work — see "Looked at, at
the keyboard". The sharpest was that **← Back could not reverse a click in the stack**: graph
selections went to the ⌘Z history and never to the trail. **Fixed 2026-08-30 — see `6i`,
one history.** Read `6h`.

### The colour channel, decided 2026-08-30 — the graph as `colorBy: 'change'`

Asked and answered at the keyboard, and both halves are Tom's.

**Change takes the channel over.** A third value in the existing "colour by" selector
beside *what it is* and *which plate*, so turning it on colours every node by its change
status and plate hue steps aside while it is on. Design rule 4 stays literal, which is how
`paintNodes` already reads: either kind or disk, never both, with selection carried by
dimming so it never competes.

The option refused, and why it is worth writing down: **tinting only the changed nodes**
and leaving the other 9,788 on plate colour. It reads well — 86 changed out of 9,874 — and
it puts two meanings in one channel, so a red dot would mean either *deleted* or *the plate
whose golden-angle hue landed on red*. That is precisely the ambiguity rule 4 exists to
prevent, and the fact that it looks fine on Mensores is not evidence, because Mensores'
changed set is small.

**Crossings keep their plate gradient.** Rule 23 walks a crossing's colour from its source
plate's hue to its target's, because a line passing through plates it has nothing to do with
cannot be read in one flat colour. Nodes and links are already separate buffers, so the dots
can say *what changed* while the lines go on saying *which plate each end is on* — and
"this deleted routine on `cli` was calling into `storage`" stays a readable sentence. An
edge's colour is its own channel; the alternative was strictly one dimension everywhere at
the cost of no longer being able to tell which end of a line you are looking at.

*Three things this chunk will have to handle, none of them decided by the above.*

- **Three states, not two.** Arrived and went have a direction; *behaves differently* has
  none, and *edited only* and *unchanged* have neither. `signOf` must not be reached for a
  fourth answer — the same trap `factLaneHtml` already documented.
- **`applyPalette()` must start pushing to the stack.** It deliberately does not today,
  because `cssPalette()` reads no token a colour set overrides, so a push would be a repaint
  that changes nothing. The moment the graph reads `--diff-*` that stops being true, and
  `test_a_palette_token_the_graph_reads_must_reach_the_graph` is already written to fail
  when it does — the implication is derived from both sides so it cannot be forgotten
  (rule 36).
- **There is no plate outline to fall back on.** Rule 18 keeps the plates undrawn and design
  rule 26 draws faintly only the two or three a *selection* touches, so with nothing selected
  plate colour is the only answer to "where am I". Colouring by change removes it. Whether
  that wants the plates drawn while this mode is on is a question for when it is on screen,
  not before.

**6h. Built 2026-08-30: the comparison over the stack (chunk C, `colorBy: 'change'`).**
The last of the temporal overlays, and the one that needed a decision before it needed work.

*What it is.* A third value in the stack's "colour by" selector, beside *what it is* and
*which plate*. Every node is drawn by what the comparison says about it, with a key under
the legend stating each band and its count.

*Four decisions, and the first two are Tom's.*

- **Change takes the channel over.** Plate hue steps aside while it is on. Tinting only the
  changed nodes was refused: two meanings in one channel means a red dot could be *deleted*
  or *the plate whose golden-angle hue landed on red* (design rule 4).
- **Crossings keep their plate gradient** (rule 23) — and it costs nothing, because
  `setOptions` repaints the nodes and never rebuilds the selection geometry, which is where
  that gradient lives. The dots say what changed; the lines go on saying which plate each
  end is on.
- **Three colours and a ground.** *Edited only* folds into unchanged **on principle**: "the
  body changed and nothing it does did" is internal computation, which `CLAUDE.md`'s opening
  says this tool exists not to report. The fold is stated in the key, never hidden.
- **"Not compared" is its own tone.** The stack draws boundaries, constants, structures and
  artefacts, and `changes.py`'s id-carrying bands are routines only (`PRESENCE` compares the
  rest by name and returns no ids). On Mensores that is **5,229 of 10,015 drawn nodes** with
  no claim either way, and "nobody asked" must not look like "we looked and found nothing".

*The measurement that was expected to be the risk, and was not.* A third difference colour
has to be separable from both existing ones under normal vision, deuteranopia and
protanopia. A grid search found candidates at ΔE 66–151; violet serves every set, and in
`safe` — whose `--diff-new` is already blue — it separates by **lightness**, which is rule
69's own lesson. **The finding is the opposite one**: the *existing* pairs are the weak link.

```
  --diff-gone vs --diff-new, worst of three vision models
  default (red/green)   light 12.7 · dark  9.5      ← the weakest thing shipped
  safe (blue/orange)    light 82.2 · dark 106.8
  muted                 light 14.0 · dark 12.8
```

So the guard's bar is **derived, not chosen**: the new colour may never become the least
separable pair in the product. A fixed bar would have failed colours already in use, which
is rule 69's conclusion that red and green cannot be rescued by tuning.

*Six defects found by driving, none by any check.*

1. **`nodes is not iterable`** on the first paint. `serve.py` transposes the payload into
   parallel arrays for the engine's typed buffers, so `graphPayload.nodes` is an object of
   columns and not an array of nodes. The key sat at *comparing…* for ever while the answer
   had long since arrived. Found by reading the console.
2. **The palette pinned a side to a colour.** Written as `only_base: hex("--diff-gone")`,
   flipping which version the reader assumes is newer swapped every word in the key and left
   the dots red — a picture saying "added" in the colour of gone. The palette is keyed by
   **tone** now and the band-to-tone map comes from `diffWords()`, so the two cannot come
   apart. Found by flipping it and reading the numbers back.
3. **The flip repainted the code and not the stack.** The handler already knew to repaint
   the code for exactly this reason; the stack is the same argument one layer out.
4. **A restored mode never asked for its data.** `colorBy` is persisted, so a reader comes
   back into `change` — and the mount hands the engine a map that is `null` until something
   has fetched. Nothing had. Rule 55's companion again: whoever sets the state does the work.
5. **Every unchanged routine read as *not compared*.** The map was copied out of
   `routineIndex()`, which holds only the 86 ids that are *in a band*; `routineStatus`
   supplies `same` for the rest, and an absent id is drawn as `unclaimed`. The key read
   *15 unchanged · 9,929 not compared* over a program with 4,700 unchanged routines — two
   wrong numbers, nothing thrown. It walks the payload and consults each node's **kind** now.
6. **The plate swatch left the selector stale.** Picking a colour for a plate forces
   `colorBy` to `disk` and returned without re-rendering, so the control went on naming the
   mode the reader had just left (rule 67). Predicted while planning, and confirmed by
   driving it.

*One caught by a guard rather than by looking, and it is the better story.* The three-state
fix — "nobody has asked", "it is being computed", an answer — was written and then **lost**:
the script carrying it asserted on a later anchor, aborted before writing, and only the
second half was re-applied. Nothing on screen said so. `test_the_key_tells_not_asked_from_
being_computed` failed on the next run and named it exactly. A guard written from a defect
caught the same defect re-entering by an entirely different route.

*One false alarm I nearly reported.* The one-version fallback appeared not to state itself.
It states itself perfectly; my seeded `localStorage` key used the wrong `SETTINGS_VERSION`,
so the stored mode never applied and there was nothing to fall back from. Checked before
reporting.

*Guards.* Thirteen new ones, mutation-tested at **23/23** over a proved-green baseline
(rule 59) — after 19/22 and then 21/23, and **all three survivors were the guard being
weak**, which is now the fourteenth, fifteenth and sixteenth time in five sessions:

- the crossings guard asserted `"diskColor(" in build`, which a mutation replacing *one* of
  the gradient's two ends walked straight past, because the other end still said it;
- `_diff_triples()` keyed blocks as `"dark" if "dark" in sel else "light"`, and the `@media`
  selector `:root[data-palette="muted"]:not([data-theme="light"])` contains no "dark" — so
  it was keyed *light* and silently overwrote the real light block, and a mutation to the
  light colours survived because the guard was measuring a different block under its name;
- the swatch guard anchored on `js.index('t.classList.contains("sw")')`, which finds the
  row-click handler's own guard first and asserted against a branch that was never the
  subject.

*What was verified, and what was not.* The data and the palette resolution were driven end
to end: the map covers all 4,786 routines (53 · 18 · 15 · 4,700), the key's five bands sum
to **10,015** — the drawn-node count exactly — the tones follow the words through all three
assumption states, all three colour sets reach the stack with the measured values, the
one-version fallback drops the mode and says so, and the console is clean with the
self-check green. **The rendered pixels were not seen.** The automation tab reports 0 fps
and is given no animation frames (rule 38), so what the stack actually looks like in these
colours is described here and has not been looked at. That is the one thing this chunk
owes a real window.

### Paused 2026-08-30, after the routine marks

Working tree clean; all three gates green; `output/mensores` untouched and still serving
both revisions.

**The second overlay is on screen and it cost no server work.** Table mode and the routine
list say what the comparison found about every routine, from an answer the page already
holds -- and say, where it applies, that the compared version's own routines are counted
and cannot be listed here.

Four defects found by looking, one of them older than this chunk: a glyph that was also its
own punctuation, a pane that told the reader to open the pane they were in, a count stated
twice and differently in one view, and a table left empty for ever by a list that had
arrived. No new numbered rule -- every one of them is an existing rule in a new costume,
which is what the numbering is for.

**Next: the graph as `colorBy: 'change'`, and it is unblocked** — the colour channel was
decided at the keyboard after this pause; see the section above. Read `6g`.

### Paused 2026-08-30, after the colour sets

Working tree clean; all three gates green; `output/mensores` untouched.

**Colour is a Setting, and the sets are measured rather than asserted.** Three of them, each
with a light and a dark variant, covering the two channels where colour separates one
meaning from another. The difference channel is finally spent, so the setting changes
something. **Rule 69** is the find: contrast says whether a colour can be read and nothing
about whether two can be told apart, and the shipped palette had been failing that second
bar since the day it was written — `broken` and `suspect` are the same colour to a
deuteranope, at ΔE 5.3.

Read `6e`.


### Paused 2026-08-30, after switching the base



Working tree clean; all three gates green; `output/mensores` untouched and still serving
both revisions.

**The base is settable and the seam is closed.** A comparison is two directions now, not
one: the reader picks which version the whole map shows and which it is held against, the
server rebuilds, and the worklist's interpretation follows without a re-query. Everything
that was prepared for it held — `_r_changes` defaulting its base from the served graph, and
`changes.build` riding the serving connection on whichever end is the base (rule 58).

Read `6d` for what was built and what driving it found. Two rules came out of it, **67**
and **68**, and both are about a state that was set somewhere the code was not looking: a
value the *browser* wrote back over the markup, and a restore that set a flag without doing
the work the setter does.

### Paused 2026-08-30, after base and compared

Working tree clean; all three gates green; `output/mensores` untouched and still serving
both revisions.

**The vocabulary is settled and the ordering problem is gone rather than solved.** There is
no earlier end and no later end — there is the **base** (what the map shows) and the
**compared** (what it is held against), and *added* / *deleted* is an interpretation the
reader owns, derived from the two versions where they say enough and assumed where they do
not. The four-step ordering plan from the previous pause is superseded; step 3 in
particular ("state capture order as capture order") is gone, and that is an improvement —
it was an honest label on a claim the tool should never have been making.

## Two feature requests, recorded 2026-08-30 (Tom, at the keyboard)

Recorded, not planned. Neither is scheduled and neither has been costed; they are written
down here so they survive the session with their reasoning intact.

### A. Size a plate by its density — a Setting

**Tom's ask, in his words:** *"A plate with just a few nodes will have a small radius
because all the nodes will fit easily. A plate with many nodes will have a much larger
radius so all the nodes can comfortably spread out."*

**It reverses a decision that is written down, and that is the first thing to know.**
`layout.py` states the opposite in as many words, at `DISK_RADIUS`:

> Disks are drawn the same size regardless of how much they hold, so a plate with 900
> nodes and one with 30 read as the same kind of object; density then carries the
> information rather than area.

Tom's request is that **area** carry it instead. That is a legitimate reversal — the
existing note is a judgment, not a measurement, and it has never been tested against a
reader — but it must be made as a reversal, with `layout.py`'s comment rewritten rather
than left standing to contradict the code. Half of every defect in this file's record is a
rule that stayed in place after the thing it described had moved.

*What does not exist today, despite the ask assuming it does.* There is **no per-plate
size** of any kind. `DISK_RADIUS` (1000, server, for placement) and `PLATE_R` (1060,
client, for the outline) are single constants, and `spreadX` / `spreadY` are **global**
multipliers applied to every plate equally — that is what rule 22's three axes are. So this
is a new dimension in the model, not a Setting over an existing one. A disk record already
carries `nodes`, `shadows` and `edges` (`graph.py:269`), which is everything needed to size
it, so the payload needs no new query.

*The arithmetic is already half-written.* `phyllotaxis` places points with `sqrt` spacing
precisely so **area per point stays constant** within a disk. Extending that across disks
is the same identity one level up: `r = DISK_RADIUS * sqrt(n / n_ref)` makes area
proportional to count and node density equal on every plate, which is exactly what the ask
describes.

*Three things to settle when it is built, none of them decided here.*

- **The range is 31x and that is not usable raw.** Mensores' largest plate holds 991 and
  its smallest holds 1, so `sqrt` gives a radius range of about thirty-one to one — the
  small plates become specks, and a plate nobody can see is a plate that is not in the
  picture (design rule 1). It wants a floor, a clamp, or a gentler exponent, and whichever
  it is should be stated as the judgment it is.
- **Does the shadow count count?** A plate's shadows are placement devices and are never
  drawn (rule 23), but they *do* take room in the layout. Sizing on `nodes` and sizing on
  `nodes + shadows` are different pictures and only one of them is about what the reader
  can see.
- **Framing still works, and should be checked rather than assumed.** Design rule 20 frames
  the bounding **cylinder** at the tilt in force, on the reasoning that orbiting about Z
  leaves the footprint circular. Variable radii keep it circular — the stack becomes a
  stepped vase rather than a cylinder — so the fit is the *largest* radius and the
  arithmetic survives. Worth confirming with a measurement, because "should still work" is
  how rule 49 got written.

### B. Draw a plate as a diagram, not as a field of dots

**Tom's ask, in his words:** *"render each plate not as the existing plates with round
nodes, but rather as Mermaid diagrams with rectangular or circular nodes (Setting), each
with text on them just like a normal diagram. The fun part is when diagrams link between
plates."* The reading furniture carries over unchanged: *"the same concepts — greyed out or
transparent nodes that are not in focus, hover panels with more details (same as
existing)."*

*Where the rendering question already has an answer.* Tom: *"I am thinking that perspective
view is appropriate — angled, orthogonal. Not true perspective, the simpler version."*
**That is the projection already in force**, and for his reason: design rule 20 chose
orthographic because under perspective the near plates magnify and the far ones shrink,
rendering a stack of equal disks as a tapered cylinder — the exact shape the model exists
not to be. So nothing changes there, and the instinct and the existing decision agree.

*Where it is genuinely undecided, and Tom says so.* Whether to billboard the rectangles the
way rule 22 billboards the node quads: *"we might also try the same trick as our circles —
tilt the rectangles up so they face the screen. That might make it hard to read the
connections between them, though, so I'm not at all sure. To be determined…"*

The tension he names is real and rule 22 says why. A sphere **has no orientation**, so a
picture of one must not either, and the billboard is free. A labelled rectangle *does* have
an orientation — it has a top, and a reading direction — and a lozenge floating at an angle
to the plate it belongs to is a box that has stopped being on the plate. Held flat it
foreshortens into the same coin-on-edge rule 22 rejects, and text on it foreshortens with
it. There is no third option that is obviously right, which is why this is `To be
determined` and should stay that way until something is on screen.

***The bar it has to clear, and Tom set it:*** *"The goal of the Mermaid diagrams is to aid
in understanding, so they must be easy to read or we have failed."* That is the acceptance
test, and it is stated before any renderer exists on purpose. A diagram that is
technically drawn and cannot be read has not half-succeeded — by this bar it has failed,
and it should be withdrawn rather than shipped with a caveat. It is `CLAUDE.md`'s own
opening applied to a view: judge the change by whether it helps someone orient, not by
whether it emits a picture.

Two consequences follow immediately. **Legibility outranks completeness here**, which is
the one place in this tool that is true — rule 8 bounds a *diagram* precisely because a
picture of 4,500 routines is not a picture, and the complete list sits beside it. And it
settles the billboarding question empirically rather than by argument: whichever of the
two can be read wins, and if neither can at a useful number of nodes, the answer is that
the number of nodes is wrong rather than that the projection is.

*The constraint that shapes the whole thing.* Rule 18 keeps nodes at **1.4 to 3.6 pixels**,
and the reason is measured rather than aesthetic: any radius that reads as a disc fuses
9,874 of them into a solid mass, and rule 22's own note records that at 14x they occlude
the edges they are drawn with. A rectangle carrying readable text is an order of magnitude
larger than that. **So this cannot be the whole stack at once**, and pretending otherwise
is the same picture-of-nothing rule 8 forbids in a diagram. It is a view of *one plate*, or
of a selection, and "the fun part" — the links between diagrams — is then a question about
two or three plates rather than fifty-two. Deciding what the reader is looking at when they
turn it on is the first design question, before any renderer.

*What already exists to build on.* A collision-filtered `TextLayer` is in the engine
(`graph.js:1026`, `pickLabels`), so labelled nodes are not new ground — what is new is a
node that *is* its label rather than a dot with one beside it.

## Curiosities: the doorway panel — built 2026-09-01

Design rule 15 asks for four pieces of furniture for the explorer. Three were built — the
trail, the threads, the shelf. This is the fourth, and the panel had been on screen since
the port saying, honestly, that nothing had been computed.

### What it is

**A curiosity is a measured extremum with its middle stated.** That is the whole design and
everything else follows from it. Every program has a most-commented routine, so a maximum
alone is a claim nobody can weigh; 1,126 comments against a middle of 3 is a discovery and
3 levels of nesting against a middle of 2 is not, and the panel has to be able to say the
second as plainly as the first. Rule 14's lesson — at enough measures something always
comes out furthest — in the one place in this product that goes looking for extremes on
purpose.

Ten measures, all of them, every time. **The list is fixed and complete, so rule 8's bound
never arises**, and a family with nothing to measure is *named* rather than dropped:
nine cards and ten cards are different claims (design rule 1). Ordered by the ratio between
value and middle, so the strangest is first and the near-ordinary ones sort last and say so.

**A curiosity is a measurement, never a judgement.** No severity, no blind spot, nothing
implying a number ought to be smaller — `anomalies.py` is where a claim about what is
*wrong* lives, and it states a blind spot because it makes one. These make none.

Tom settled the shape (one card per measure, all ten, ranked by distance from the middle)
and the line-count family, with the reason recorded: external coding standards are written
about package and routine size, so displaying a large line count is a measurement and
implies no judgement.

### Measured on Mensores, and every number checked against real source

| Measure | Extremum | Middle | Ratio |
|---|---|---|---|
| characters in one call argument | 91,224 (`frozenset`, `quaestor/_envelope.py:67`) | 10 | 9,122× |
| comments on one routine | 1,126 (`quaestor._envelope`, module scope) | 3 | 375× |
| characters in one constant's value | 8,586 (`GOVERNED_GATES`) | 34 | 253× |
| callers of one routine | 82 (`make_operational_event`) | 1 | 82× |
| lines in one routine | 617 (`make_operational_event`) | 15 | 41× |
| routines carrying one governance id | 112 (`AC-4`) | 4 | 28× |
| boundaries reached from one routine | 27 (`cli.audit.backup_cmd`) | 2 | 13.5× |
| parameters on one routine | 19 (`SQLiteClient.write_spec_amendment`) | 2 | 9.5× |
| a table's read/write lopsidedness | 9× (`spec_seals`) | 2× | 4.5× |
| nesting depth of a closure | 3, and 24 others as deep | 2 | 1.5× |

Not taken from the store on trust. The `frozenset` at line 67 really does span 1,350 lines;
`make_operational_event` really is 1637–2253, which is 617; `write_spec_amendment` really
takes 19 parameters. **And each card's own SQL was copied out of the served JSON and run
through `dunneflow query`** — all ten returned exactly what the card printed, which is
design rule 13 checked from the reader's side rather than asserted from ours.

The inspector shows `In 92` for `make_operational_event` against the card's 82, and the two
agree: 92 call sites, 82 distinct callers. The card says *callers* (rule 32).

### One statement per family, and it produces every number on the card

Value, median, ties and population come out of **one scan**, so they cannot disagree, and
the statement a card offers is not a query *about* the number — it is the query that
returned it. Reproducible verbatim.

**One of them was 7.47 s.** Written the obvious way, the call-argument CTE joined 43,926
rows to `calls` and `routines` — and did it four times over, once per reference to the CTE.
Materialising only the key and the measure, and resolving the winner's name once for the
one row that won, is **54 ms**. `MATERIALIZED` is stated rather than hoped for. All ten are
106 ms warm; the route is held on `_Base` and answers in 0.5 ms after the first ask.

Not paid at boot, unlike the two vocabulary lanes, and the difference is the bargain: a
thread is asked on every selection so a lazy first call there would stall the reading loop;
this is a page a session either opens or never does (rule 45).

### Two defects, both found by driving

**Mine.** The governance card said **"121 routines carry one governance id" and opened
112**. An annotation's owner is a routine *or a structure*; the measure counted every owner
and called them routines, while `GOVERNANCE_ROUTINES` — which resolves the cohort — has
always been scoped to routines. Rule 32 twice over: a wrong noun, and a number a reader
catches out the moment they click it. The measure is now over exactly the set the subject
opens, and the guard is written against a `counts_its_cohort` flag rather than against this
family, so the next cohort measured by its own size is covered without anyone remembering.

**Not mine, and it had been unreachable.** **Rule 76's flag was at one of three call sites.**
`Graph.mount` is handed `picks: state.picks` and finishes by calling `announceSelection()`
for exactly the same reason `setSelection` does, and it was never flagged;
`applySelectionStep` raises `restoringSelection`, which only ever suppressed
`recordSelection`, so a Back ran the whole handler under `sel.node` and was corrected on the
next line — right by ordering rather than by design.

This panel is **the first surface in the product that can follow a subject with the stack
never mounted**, which is why nothing had reached the mount case before. It showed up on the
first cold run: a card naming `backup_cmd` opened the inspector on
`mensores.transport._envelope.<module>` and filed two trail steps under its name. One
predicate now covers all three sites and a guard asserts there is no fourth — the failure to
guard against is a *new* way to hand the engine a selection, which would look exactly like
working code. Rule 76 is amended accordingly.

The panel's own click handler was rule 30 alive in the file, and is gone rather than fixed:
each card carried a `tag` string and the handler switched on it with an `else` falling
through to table mode. It had never fired because `CURIOSITIES` was never filled; filling it
is what would have lit it up. Cards now carry a **subject** and go through the tested
`data-thread` / `THREAD_SUBJECTS` path, which also gives them the trail step for free.

### Smaller things it turned up

- **The navigator count never appeared.** `render()` does not rebuild the pane, so the
  number landed and the row went on saying nothing until something unrelated rebuilt it.
  Rule 55's companion: whoever sets the state does the work of showing it.
- **The provenance key was a bare index**, and two panes number their cards from zero.
  Opening the naming page's third query would have opened this pane's third card too.
  `provKey(pane, i)` is the one owner of the key shape; a prefix written at the attribute
  and again at the comparison is two decisions about one key.
- **`laneState` takes its bag as a parameter** now. Three panes fetch on demand and each
  keeps its own flag; what must not be duplicated is the four states and how each reads.

### Verification

```
25 mutations caught over a baseline proved green first
five survived a first pass:
  two guards read the flag named in their own comment (rule 37, for the fourth and fifth
    time — `_code` exists precisely for this, and neither guard used it)
  one fixture could not produce a zero middle, so the branch was tested where it can be
    reached — through `_card` with a constructed row — rather than pretended at
  one guard did not exist (the four lane states)
  one was too loose (the silent note, dropped from the page with cards while the other
    return still mentioned it)
```

The fixture had to be corrected twice before it could tell the governance defect from its
fix: a comment on a class body is filed under module scope (rule 18), which is a *routine*,
so the id had to go in the class's **docstring** to produce a structure owner at all. Until
then the guard passed against the reverted defect — a check that has never failed is a claim
nobody has tested.

**Absent rather than estimated: a picture of the whole panel.** The automation tab's capture
is fixed at 784×353 whatever the window is resized to, so one card fits and the other nine
do not (rule 38). What was driven there: all ten cards, all twenty buttons reachable by
`elementFromPoint`, every node card followed and checked against the inspector, both cohort
cards resolved (the governance one selecting exactly the 112 it claims), the provenance
block opened and confirmed not to open the naming page's, Back returning to all ten cards,
and three cold-mount cycles for the echo fix.

783 tests, mypy clean, ruff clean.

## Still open, in the order agreed

**1. Switching the base — done 2026-08-30, see `6d`.** What follows was the plan and is kept
because two of its five bullets turned out differently. The `_Handler`-holds-the-payload
shape is gone rather than worked around — the payload lives in `_Base` with everything else
a version decides — and the selection-survival worry resolved into something smaller than
expected: `state.selected` is not persisted, `describe()` already answers `found: false` with
a reason, and the inspector already renders it. What the reload could not carry is the
*knowledge that a switch happened*, so that is a one-shot in `sessionStorage`, read into the
strip's note.

<details><summary>the plan as it stood</summary>

**1. Switching the base — next, and as proposed.** Tom chose *rebuild every switch*: one
payload set live, always. The shape of the work:

- `serve()` builds the payload, the 628-file code list, both vocabulary lanes and the cover
  from **one graph opened at boot**, and `_Handler` receives that payload at construction.
  So a base switch is a server-lifecycle change: swap `live.store` under `live.lock`,
  rebuild the payload **in place** (the handler holds it by reference), rebuild
  `live.files`, `live.naming`, `live.glossary`, `live.cover` and `live.root`, and clear
  `live.changes` — every cached diff is keyed on a pair that no longer applies.
- A **new endpoint** to ask for it, and a client **progress state**. The measured cost is
  10.2 s of which the glossary is 2.1 s; design rule 1 and rule 35 both say the reader must
  see "rebuilding for <version>…" rather than a page that appears to have frozen.
- **`baseRev` was never settable from the UI** — `buildRevControls` sets only the compared
  end, and its trailing disabled row says so in as many words. That row is the thing this
  work removes.
- Two things already prepared for it: `_r_changes` defaults its base from
  `self._live.graph_db` rather than `graphs[0]`, so the map and the comparison cannot
  disagree about which version is on screen; and `changes.build` rides the serving
  connection on whichever end is the base, so the 36x (rule 58) survives the switch.
- Watch for: a rebuild that leaves `state.selected` pointing at a node id the new base does
  not have. Ids are position-independent (`make_id`), so most survive — but a routine only
  the old base had does not, and "selected something that is not there" must be a stated
  outcome rather than a blank inspector.

</details>

**2. The diff palette (chunk B) — done 2026-08-30, see `6e`, and it grew.** The plan was a
Setting and an a11y clamp beside the existing `pointerPasses`. What it became, on Tom's
instruction, is three colour **sets** covering difference *and* severity — and the reason it
grew is rule 69: generalising the contrast clamp would have shipped a red/green pair that
clears every contrast bar and is one colour to a deuteranope. `pointerPasses` was **not**
generalised in the end, and that is the part worth keeping: it clamps a *free picker* at 3:1
against the graph's own ground, while a set is a fixed choice validated at build time by a
test. Two different questions, and one clamp answering both would have made the pointer's
bar speak for colours nobody can pick.

**3. The overlays (chunk C) — the code browser and the routines are done, 2026-08-30, see
`6f` and `6g`.** What follows was the plan, and it held: the file-level pairing was free
(613 identical, 12 modified, 3 added, 0 removed, zero body reads) and it is what says which
twelve files are worth `difflib`. What the plan did not know is that the code browser was
reading the *wrong version's bytes* — see rule 70 — so the chunk began with a fix rather
than with an overlay.

The routines followed and needed no server at all. **"The worklist" turned out to be two
questions, and Tom took the first**: the change worklist already *is* the comparison, so
this was table mode and the navigator's routine list. The **anomaly** worklist is a
separate piece and is blocked on a question rather than on effort — *what makes two
findings in two versions the same finding* — because a finding carries no id and 93 of
Mensores' 106 are `LOST_EDGE`. Answer that before building it; a false *new* is rule 1's
defect with a colour on it.

**The graph is done too — 2026-08-30, see `6h`.** The colour-channel question was answered
at the keyboard (see "The colour channel, decided 2026-08-30" below) and built the same day.
**Chunk C is complete**: the code browser, the routine views and the stack all draw the
comparison. What is left of the overlays is the **anomaly worklist**, and it is blocked on a
question rather than on effort — what makes two findings in two versions the same finding.

<details><summary>the plan as it stood</summary>

**3. The overlays (chunk C) — next.** Code browser first — nearly free, because
`SourceStore.text(path, revision=…)` and `hash_of(path, revision=…)` already take a
revision and the file-level pairing is one query with zero body reads (613 identical, 12
modified, 3 added, 0 removed), which also says which twelve files are worth `difflib`.
Then tables and the worklist. Then the graph as `colorBy: 'change'` — **put the
colour-channel decision to Tom before building that one**; design rule 4 says colour
carries one dimension at a time, so a comparison should *take over* the channel rather than
paint red and green over fifty-two plate hues.

*What `6e` hands this chunk.* The difference channel is a real colour now, chosen by the
reader as one of three sets, so anything an overlay draws in `--diff-gone` / `--diff-new`
gets that choice for free and needs no palette of its own — which is the whole reason the
sets are CSS rather than a table in a script. Two things follow. The **tone must come from
`diffWords()`**, never from the band key or the side: `.tone-gone` / `.tone-new` are the
classes, and a guard asserts both sides derive their tone from which version is newer.
And when the graph starts reading `--diff-*`, **`applyPalette()` must push the palette to
the stack** — it deliberately does not today, because `cssPalette()` reads no token a set
overrides and a repaint that changes nothing is waste.
`test_a_palette_token_the_graph_reads_must_reach_the_graph` derives that implication from
both sides and will fail the moment it becomes true, so it cannot be forgotten (rule 36).

</details>

*Two feature requests recorded 2026-08-30 — **both built 2026-08-31**, and the text below
is kept because one of them changed name on the way.* **Sizing a plate by its density** is
done, and shipped as *plate width* rather than density: see "Sizing a plate by what it
holds". **Drawing a plate as a diagram** is done too — withdrawn once, then built: see
"Withdrawn — Tom, 2026-08-31, on the plate diagram" and "The plate as a diagram". Their
original framing, with what was decided and what was not, is under "Two feature requests,
recorded 2026-08-30" above.

### The open list lives in `BRIEFING.md`, and only there

**Read it under "What is next, and it is open". Do not keep a second copy here.**

This paragraph *was* that second copy, and it drifted twice in two days — which is the whole
argument for the rule. On 2026-09-02 an audit found it carrying "what is an occurrence for
`LOST_EDGE`" as an unanswered question that had dissolved two days earlier, and carrying both
2026-08-30 feature requests as unscheduled when both were built; `BRIEFING`'s copy meanwhile
was missing per-plate sphere scaling and stack orientation, which only this one had. **Then
it drifted again inside the very session that fixed it** — the class docstring was closed and
this list went on saying it was open, while the trail-duplication found the same afternoon
reached `BRIEFING` and never reached here.

Rule 51, and the shape that rule is about: one truth, one place that owns it, and every
reader arriving through the same door. Two lists kept level by hand are two answers waiting
to disagree, and **a standing list is read as current by definition** — an item that has
stopped being true costs more than one that was never added.

`BRIEFING` owns it because that is the file a session is told to read first. What belongs
here is what this file is for: the record of *how* each item was closed, under its own dated
heading.

**Struck 2026-09-02: "what is an occurrence for `LOST_EDGE`" was not an unanswered
question.** It stood here as *one question never answered* — the 142 callers or the rival
definitions, deciding the feature because 93 of Mensores' 106 findings are that kind. It
**dissolved** on 2026-08-31 rather than being answered: the detector already groups by
`callee_expr`, so a finding is one per expression, the callers are its `count` and the
rivals are in its `title`. Both are what it *reports*, and both move while it stays the same
finding. The anomaly worklist it was said to block was built the same day — `5a` and `5b`,
`anomalychanges.py`, `/api/anomalychanges`. It is recorded here rather than deleted because
the entry misled every session for two days, and **a standing list is read as current by
definition**: an item that has stopped being true costs more than one that was never added.

And the blank-graph fix (rule 49) is still reasoned and guarded rather than seen — rule 38,
it wants a real window.

*Practical note.* The two-version corpus used to verify this work was **removed** — 250 MB,
and Tom manages disk. Rebuild it with:

```bash
uv run dunneflow analyze ../society-2026-08-26/src --name verifycheck
uv run dunneflow revisions output/verifycheck --seal --label "handed over, undocumented"
uv run dunneflow analyze ../society-2026-08-29/src --name verifycheck
```

It is the only program directory whose revisions carry a `tree` and a version;
`output/mensores` predates both columns and honestly reports empty, which is what makes it
the useful test of the *fallback* path.

---

## The docstring lanes — built 2026-09-01

The last item on the open list, and it was two subjects rather than one.
`routines.docstring` had been in the store from the beginning and compared by nothing; so
had `files.doc`, and they cannot share a row.

### What was wrong, verified on the pair rather than argued

A docstring lives *inside* the `def`, so it is inside `body_hash` — which is the opposite
of the comment case and makes this a different defect. A rewritten comment could vanish
outright; a rewritten docstring never does. It is reported, in **`edited only`**, whose
tooltip reads *"edited, and nothing it does changed"* and whose section on the page calls
it *internal computation — what this tool exists not to report*.

On Mensores' pair (628 files against 625), two routines have a differing docstring:

| routine | band before | what actually moved |
|---|---|---|
| `_migrations._production_audit_db_path` | `edited only` | a `.. deprecated::` notice and the entire reasoning |
| `_queue.StateIntentQueue.ensure_schema` | `behaves` | docstring, invisible beside `calls` + `call_args` |

Neither was missing. Both were filed under a reason that is false about them.

### The canonical question, a fourth time

`_constants_moved` predicted this would come round and said the answer would depend on how
the column is filled. It does, and it lands somewhere new:

| surface | how it reaches the store | canonical form |
|---|---|---|
| constant | `ast.unparse` | none needed — already canonical |
| call argument | a byte slice of the file (rules 8, 75) | ask `canonical/`, per language |
| comment | one row per *physical line*, marker stripped | join everything, collapse |
| **docstring** | one string via `inspect.cleandoc` — **blank lines intact** | **collapse within a paragraph, keep the breaks** |

Two experiments over the real 3,769 docstrings, and only the second chooses:

```
re-wrapped at 72 / 79 / 88,   as written     2,060 · 1,652 · 1,602 falsely reported
not one word altered          collapsed          0 ·     0 ·     0
                              by paragraph       0 ·     0 ·     0

every paragraph merged        collapsed          0 reported     <- blind
(1,996 affected)              by paragraph   1,996 reported
```

Merging paragraphs changes no word and destroys the separation PEP 257 gives the summary
line. A full collapse cannot see it; the paragraph-preserving form catches all of it and
costs nothing on the noise. Same zero, 1,996 more signal.

One fixture went wrong on the way and it is worth keeping: a blank line padded to *less*
than the docstring's common margin is removed by `cleandoc` before anything compares it, so
the first version of the trailing-whitespace test was testing an empty string against an
empty string. Eight spaces inside a four-space margin, not three. Found by mutation.

### The module lane — Tom's call, and rule 77

`files.doc` states what a module *is*, and belongs to no routine. The cheap implementation
is `<module>`, and the numbers are the whole argument against it:

```
files with a module docstring   619
files with a <module> routine   487      <- minted only where a file runs something at import
                                141      files that say what they are and would report nothing
```

For those 141, a rewritten module docstring moves no body hash, no fact and no row, and the
page states **"No differences found."** That is the comment lane's worst answer standing
again. Caught by counting before it shipped, not by a false result, which is why it is
written up as a design decision.

`modules_explained` rows carry a **path**; the route opens the file. `CHANGE_FILE_BANDS` is
a table beside `CHANGE_BANDS` rather than an exemption inside it, so the guard asking
whether every band the server sends reaches something that draws it keeps working.

### Two live defects found on the way, neither in this work

**`changeNote()` had been wrong since the comment lane landed.** It decided "no differences
found" from `only_in_base + only_in_compared + behaves + edited_only`, so a pair whose one
difference is a rewritten comment — or a table that appeared, or a constant whose value
moved — said *no differences found* in the group a reader lands in first while the page
below listed the change. The same false claim the explained band was built to remove,
surviving in the other of the two surfaces (rule 51). It asks `CHANGES.identical` now,
which the server computes once over every band and every presence line.

**The file route did nothing visible, and only clicking it said so.** `openCodeFile` opens
the pane and leaves the centre alone — right inside the navigator's Code group, where the
list is already under the reader's eye, and wrong from a worklist page: state set, file
loaded, not a pixel moved. `chgfile` is a second route rather than a flag on the first,
because the two callers genuinely want different things. Rule 77's companion.

And a third, smaller: **"1 modules explained differently"**, which is `classs ending in
\`Error\`` again — a string the code composes is prose the moment something prints it. Both
forms are written out in the table rather than derived, because English is not a rule.

### Cost

```
_changed_files       1.9 ms   (15 of 628 files)
_comments_moved      8.2 ms
_docstrings_moved    3.2 ms   ...and 22.3 ms unbounded, over all 628
_module_docs_moved   2.2 ms
```

`/api/changes` whole build, HEAD against this, **alternating in one process on a warm disk**
so disk state cancels — the first attempt was taken cold and gave a −54 ms median, which is
noise wearing a sign:

```
HEAD  449 451 449 453 452 456 463 449   median 451
new   454 454 457 455 456 453 452 454   median 454      +3 ms
```

The 19 ms the bound saves is almost exactly the 20 ms of headroom that budget row has. So
the bound now has a guard of its own — **no answer can catch it being removed**, because
every prose lane returns the same rows bounded or not, and the comment lane's own test says
as much in its docstring. It is guarded in both directions: `_changed_files` reading the
changed-file query, and every lane taking it rather than building its own.

### Mutation

```
18/18 caught over a baseline proved green first (rule 59)
```

Three passes. Five survived the first: three genuinely unguarded surfaces (the edited
tooltip, the file row's route, `changeNote`), one weak fixture (the margin problem above),
and two weak *mutations* — the `behaves` promotion wrote to `moved` after `behaves` had
already been computed, and the bound mutation matched twice because both lanes share it,
which is the point. One survived the second, and it was my own guard: it summed two counts
of overlapping substrings, so either printing site could drop the singular and still clear
the bar. Rule 59's companion twice in one session.

### What was driven, and what is absent

Driven on Mensores' real pair: both docstring tags, the edited tooltip's sentence, the stat
tiles, `routineChip`. Driven on a purpose-built two-revision program: the module band, its
heading and hint, the row reachable by `elementFromPoint` and clicked through a real pointer
event (rule 48) to the code view, the trail step it files, the navigator group joining the
same accordion as the routine bands, and the singular.

**Absent rather than estimated: a picture of the band.** The automation tab's capture is
fixed at 784×349 whatever the window size (rule 38), so anything below the fold cannot be
photographed. The stat tile's violet is visible in the one capture that fits.

### The corpus used and removed

`output/tinydocs`, 1 MB, built to exercise the module lane end to end and deleted after.
`queue.py` runs nothing at import, so it has no `<module>` routine and is the 141-of-628
case; `audit.py` does, and carries the routine-docstring change. Rebuild with:

```bash
mkdir -p /tmp/tinyv1/tiny /tmp/tinyv2/tiny
# v1/queue.py    """Queue state, and the one place it is written."""     + push(), drain()
# v2/queue.py    """Queue state. Every writer goes through `push`; nothing else may."""
# v1/audit.py    """Audit trail."""  + ROOT = os.environ.get(...)  + record() -> """Write one event to the trail."""
# v2/audit.py    ...record() -> """Write one event to the trail, and never anywhere else."""
uv run dunneflow analyze /tmp/tinyv1 --name tinydocs
uv run dunneflow revisions output/tinydocs --seal --label "before the rewrite"
uv run dunneflow analyze /tmp/tinyv2 --name tinydocs
uv run dunneflow serve output/tinydocs
```

It reports 1 module explained differently, 2 edited only (`tiny.audit.record` tagged
`docstring`, and `tiny.audit.<module>` because that file's bytes changed), and nothing else.

### Still open after this

The list is at the foot of this file and has not grown. One thing this work *names* that was
not named before: **a class docstring is compared by nothing**, and it is blocked on the
same question rule 77 is about — `structures` has no presence band at all, so a class that
appeared or vanished is unreported too, and there is no row to tag. Zero differ on Mensores'
pair. Decide the subject before building the lane.

## The record split into files that can be carried — 2026-09-02

**`CLAUDE.md` had grown to 162,893 bytes, past the 150,000 a session can load.** It is
loaded in full at the start of every session, so past that limit it is not merely large —
it is *truncated*, silently, and the part that falls off is whatever sits at the end. That
is rule 49's shape in a document: a plausible value where a measurement belongs, with no
symptom. Nothing was reporting it.

**What it was made of, measured before anything was moved:**

```
  91,418  Rules learned the hard way          76 engineering rules
  26,517  Dashboard: design rules             26 design rules
  23,544  Verification                        of which ~21,000 is measured budget tables
  14,174  Architecture
   3,220  Commands
   1,181  Anomalies: the discipline
   ~2,800 everything else
```

Two thirds of the file is 102 rules, and the rules are cited as **bare numbers** — "rule
45", "design rule 19" — **768 times across `src/` and `tests/`**. So nothing could be
deleted, renumbered, or closed up: the numbers are addresses, which this file already said
in as many words about rule 21's gap.

### What was decided, and by whom

Tom took all three, and the shape is his: **split by how often you need it, not by
importance.**

- **The rule bodies move; the titles stay.** `RULES.md` and `DESIGN-RULES.md` hold all 102
  in full. `CLAUDE.md` keeps a numbered index of the **bold title of each**, which is the
  rule itself — the body is its evidence. ~7 KB inline against 118 KB.
- **`BRIEFING.md`'s history chain goes.** 82,004 of its 121,705 bytes were `### Before
  that:` sections, each a summary of a session `HANDOFF.md` already records in fuller form.
  Verified before cutting rather than assumed — the relative-paths session, for one, is at
  `6a`. Replaced by a 26-row table of date, subject, and **what to search for**.
- **The measured budgets move to `PERFORMANCE.md`.** `CLAUDE.md` keeps the three gates and
  the ground-truth corpus rules — the things that must run before anything is called done.

### The result

```
CLAUDE.md    162,893 -> 34,583     (79% smaller, and the whole of it now loads)
BRIEFING.md  122,578 -> 46,056     (62% smaller)
RULES.md               92,158      76 rules, verbatim
DESIGN-RULES.md        27,029      26 rules, verbatim
PERFORMANCE.md         22,154      13 tables, verbatim
HANDOFF.md   443,524 unchanged     the archive is the archive
```

### How it was proved lossless, which is the part worth keeping

**Not by reading the diff.** A 3,194-line deletion is not reviewable by eye, and "it looks
right" is exactly the claim this project does not accept.

1. **The split reconstructs the original byte for byte.** `CLAUDE.md` was cut into eight
   segments by line boundary and the concatenation compared to the original — `True` before
   a single file was written. A first attempt returned `False` by one byte, on a trailing
   newline, and that one byte is the reason the check exists.
2. **Every substantive line of the original was searched for across the whole new set.**
   1,974 lines of 12 characters or more; **1,972 found verbatim**. The two misses are the
   two lines deliberately rewritten — the intro sentence, and a heading promoted from `###`
   to `##`. Naming both up front is what makes the number readable.
3. **Rule numbers were enumerated, not counted.** 1–77 with **21 correctly absent**, and
   1–26 for the design rules. A count of 76 would have passed while a rule was silently
   duplicated and another dropped.
4. **Every pointer in the new `BRIEFING.md` table was resolved against `HANDOFF.md` before
   the cut.** 33 anchors, 0 unresolved. A pointer table nobody checked is rule 30 in a
   document — a label that opens nothing.
5. **The cut region was scanned for forward-looking language** — `still owed`, `not built`,
   `blocked`, `deferred` — because a summary being redundant does not make every line in it
   redundant. 25 hits, and **two were genuinely open and lived nowhere else in `BRIEFING`**:
   the blank-graph fix (rule 49), reasoned and guarded but never *seen* because the
   automation tab never mounts the graph; and `m.<module>` as a language feature, with
   research owed on prior art. Both are in `HANDOFF`'s standing list, so nothing was lost —
   but both are now restored to `BRIEFING`'s open list, where a reader will meet them.

### The split changes nothing about what the tool reads, and that was measured too

The worry was real: the rule titles now appear **twice** — once in the index, once in the
body — so the glossary or the naming lanes could double-count them. Analysed both trees in
isolation, same source, same four-versus-seven markdown files:

```
before, 4 documents:  10 definitions, 0 stated rules, 25 governance ids
after,  7 documents:  10 definitions, 0 stated rules, 25 governance ids
```

Identical. The index sits inside a fence, and **rule 12 says nothing prose-shaped is ever
read from inside one** — so the mechanism that keeps an example from becoming a definition
is the same one that keeps an index from becoming a second copy. That was a happy accident
of formatting when the index was written, and it is recorded here as a decision now: the
index stays fenced.

798 tests, mypy clean, ruff clean, before and after. Self-analysis reads 54 documents, 0
failed. Both the original and the pruned set are backed up to
`/Volumes/YourBackup/DunneFlow/2026-09-02T075559/`, the originals at the top level and
the result under `after/`.

### What this does not fix

`HANDOFF.md` is 443,524 bytes and was left alone deliberately — it is the archive, it is
read on demand rather than loaded, and truncating an archive to save a file that is not
loaded would be the wrong trade. It will want splitting by era eventually; nothing depends
on that yet.

And the standing risk of the whole exercise is worth stating plainly: **a rule in a file
nobody opens is a rule nobody follows.** The index is the mitigation — a title in every
session's context is enough to recognise that a rule applies — but it is a mitigation, not
a proof, and the instruction to read the body before working in an area a rule governs is
written at the top of `RULES.md`, at the head of the index, and in the routing table in
`CLAUDE.md`. If a future session applies a rule shallowly from its title alone, that is the
failure mode to look for first.

## The standing open list, audited entry by entry — 2026-09-02

Nothing was scheduled, so the standing list is what a session navigates by. Audited rather
than read out, and it had drifted both ways.

**Struck, because it was resolved and still listed.** *"What is an occurrence for
`LOST_EDGE`"* stood as **one question never answered**, said to decide a whole feature
because 93 of Mensores' 106 findings are that kind. It **dissolved** on 2026-08-31 rather
than being answered — the detector already groups by `callee_expr`, so a finding is one per
expression, the callers are its `count` and the rivals are in its `title`; both are what it
*reports* and both move while it stays the same finding. The anomaly worklist it was said to
block was built the same day (`5a`, `5b`, `anomalychanges.py`, `/api/anomalychanges`). It had
told every session for two days that the largest feature was blocked on an answer nobody
owed.

Both 2026-08-30 feature requests were marked *not scheduled* and both were **built
2026-08-31** — sizing a plate by its density, which shipped under the name *plate width*, and
the plate diagram, withdrawn once and then built.

**Two half-truths about the worklist's jump buttons, separated.** The design rule 16 defect
is *fixed*: they were live-looking buttons with no attributes and no handler, and each now
states why it does not act. Making them **act** is still open and is blocked on precision
rather than effort — a finding carries the **name** it found, not the node, so resolving
`subject` would guess between every routine sharing that name (rule 5).

And the rule 44 defect inside that explanation is fixed too, which `4650` recorded as *"found
in passing and unfixed"*. Verified live rather than by reading the map: `/api/anomalies`
sends `subject`, `loadAnomalies()` carries it across, and **23 of 26 findings on DunneFlow's
own graph have a non-empty one**.

**Added to `BRIEFING`, which was missing them:** per-plate sphere scaling, and stack
orientation — the second structural, because `OrbitView` has no camera roll.

### And it drifted again the same day, which is the finding that outlasts the audit

The list was corrected in both files, and then closing the class docstring updated one copy
and not the other, while the trail duplication found that afternoon reached `BRIEFING` and
never reached here. Two lists levelled by hand are two answers waiting to disagree — rule 51,
in the documents rather than in the code.

So `BRIEFING.md` **owns** the open list now and this file points at it. What belongs here is
what this file is for: the record of *how* each item was closed, under its own dated heading.

## Structures, compared at last — built 2026-09-02

**The last prose surface, and it turned out to be three lanes rather than one.** A class
docstring was compared by nothing. So was the *presence* of a class, and so was what one
declares — `structures` had no band of any kind, which is why the docstring was left out in
the first place: there was no row for it to be a tag on.

### The subject question, settled by measuring the wrong answer first

`BRIEFING` said this wanted deciding before any code, and it did. The tempting answer is the
diagram box: rule 74 already says **a box is a class**, `state.fold` is already a subject,
and `/api/fold` already describes one. Measured before taking it:

```
structures in base                       671
  ...that any routine names as its class 192   <- would have a box
  ...with no method at all               479   <- no box exists, and none can

  by kind:  DATACLASS  480 total, 159 with a box
            TYPE_ALIAS  88 total,   0        <- every one
            CLASS       49 total,  32
            ENUM        42 total,   0        <- every one
            TYPEDDICT    8 total,   0        <- every one
            NAMEDTUPLE   4 total,   1

  and of the 8 structures that actually move on the pair, 4 have no methods
```

A box is built from **routine** nodes, so it exists only where a class has methods. Routing
these rows through it would have been right about the majority and silently wrong about the
rest — **rule 77**, third time, and caught by counting rather than by a false result.

**And nothing had to be minted.** `describe()` already resolves a `structures.id` and answers
with a STRUCTURE specimen — verified live on a TYPE_ALIAS with no methods before a line was
written. So a structure is a subject exactly as a routine is, and these rows carry an **id**
where the four presence lines carry only a name. Not an inconsistency: rule 30 applied
honestly rather than uniformly — emit an identity where one exists, a name where none does.
`db_tables` has no id because a table is not a node; a structure is.

### What it reports, on Mensores' pair

```
structures_only_in_base       7     <- reported by nothing before today
structures_only_in_compared   1
structures_declared           1     <- IntentOp: bases and fields moved
structures_explained          0     <- and 0 is the true answer, see below
```

Tom took **Structures** for the name (the store's own word — the table, the enum and the
cover all already say it; "Classes" would be wrong for the 138 aliases and enums), and took
the *declares differently* lane on top of what he had asked for, so nothing about a structure
is left uncompared.

### The defect this shipped with for an hour, and how it was caught

`structures_explained` came back **5** against a raw ground truth of **0**. Every one of the
five was already a presence row: `_moved_prose` compares the **union** of the two id sets, so
a structure that exists on one side only reads as *described differently* — its docstring is
here and absent there. Two lanes recording one act, which is **rule 40**.

It was caught only because the number disagreed with a ground truth taken before the code
existed. The routine lane guards it at the call site (`& both`), the module lane inside its
own helper — **three lanes, one rule, and this was the third time it had to be applied**, in
a module whose own comments explain the rule twice.

### A surviving mutation that was the guard's fault, not the mutation's

`test_reordering_two_fields_is_not_a_declaration_change` pins that `idx` is excluded — a
position, and no key in this module carries one. Keying the field comparison on `idx`
instead of `name` **survived it**. The fixture was `a: int = 0` and `b: int = 0`: swap two
fields that differ only in name and *either* key gives the same set, so there was nothing
for the mutation to change. The fields differ in **type** as well now, and the mutation is
caught. Rule 59's companion — when a mutation survives, ask whether the guard is weak before
changing either.

One more of the same family, in a test I wrote and then had to withdraw: the first version
of that test swapped fields that also *gained a default*, so it asserted a change while its
name promised none. A test whose name and assertion disagree is worse than no test.

### Cost, measured like for like

**+13.3 ms**, median of four alternating builds of HEAD and this in one process against a
warm disk (321.2 → 334.5). That fits the 20 ms of headroom `/api/changes` had, and it is the
whole of the budget story: the four lanes are 6.5 ms of query between them once warm, and
the 182 ms a first run shows is the external volume, the same caveat every cold row carries.

The fact lanes are **unbounded** while the docstring lane is bounded to `_changed_files` with
the other two prose lanes. That split is deliberate rather than accidental: a presence lane is
an indexed set difference over 671 rows, and a structure whose whole file was removed must
still be reported.

### Verified by driving it, not only by tests

809 tests (11 new), mypy clean, ruff clean. Three mutations run against a baseline proved
green first: the missing intersection, `idx` as a key, and a dead docstring lane — all three
caught, one only after the fixture was strengthened.

On the real Mensores pair in Chrome: the three bands render with their counts, the navigator
note reads *"7 structures only in the base · 1 structure only in the compared · 1 structure
declaring differently"* with the singulars right, the declaring row carries `TYPE_ALIAS`,
`bases` and `fields` as tags, and the stat tiles say **structures, not routines** (rule 32).
The row was confirmed reachable with `elementFromPoint` (rule 48) and then clicked through a
**real pointer sequence dispatched at whatever was on top** — which was a child `kind-tag`,
so the bubble path is proven too. The inspector answered `ClaimVerdict · ANALYZED ·
STRUCTURE`: the structure itself, not one of its members (rule 74). Console clean, "every
control is wired".

**Absent rather than estimated:** a photograph of the bands. The automation capture is fixed
at 784×349 whatever the window (rule 38), so the worklist below the fold cannot be
photographed and coordinate-clicking is unreliable there — which is exactly why the click was
dispatched at coordinates read from the page rather than aimed at a screenshot.

### Found in passing and not fixed — it is not this work's

**Clicking a change row files two trail steps.** Verified pre-existing and not introduced
here: a **routine** row does it too (`drill_exactly_once_after_recovery` twice from one real
pointer click), so structures behave exactly as routines do. It is rule 76's family — an echo
arriving as an act — and rule 76's own amendment describes this symptom in as many words for
the doorway panel. Left alone deliberately: it affects the existing lane equally, and fixing
it is a change to the selection path rather than to this feature.

### Still open after this

The list at the foot of this file, minus the class docstring, which this closes. Nothing new
is blocked. The trail duplication above joins it.

## The cursor over a diagram — built 2026-09-02, and it was never about the arrow

**Opened as the first item on the open list: "the flow panel's arrow stroke is 1 px, which
is thin to aim at."** That was true and was the smaller half. Tom drove it and said so
immediately: *"The problem isn't so much the arrow size as the cursor pointer. We're back to
the hand icon here… I think the reticule or arrow would be better in this context."*

### What was actually wrong

Two things, and neither was a bug anything could detect.

**`.dgm-pan g.node { cursor: pointer }`** — the web's *this is a link* hand — on a drawing
you **aim** at. Its hotspot is a fingertip whose exact pixel is a guess, and the glyph is
broad enough to cover the thing being aimed at, which is worst on precisely the thin target
that opened the item.

**`.dgm-pan g.edge path { stroke: var(--graph-edge) }`** with no `stroke-width` at all — so
an arrow took Graphviz's default of 1. A 1 nobody chose, which is why it never read as a
decision.

Both are design rule 2: genuinely interchangeable, so both are built and it is a Setting.
`diagramCursor` is arrow / crosshair / hand, defaulting to **arrow** — Tom's choice — and
`diagramEdgeWidth` is 1–4, clamped 1–8 at the one door the value comes through, because
`localStorage` is editable and a 400-unit stroke is a solid rectangle with no way back.

Thickness is in **user units**, not rem, and that is not a lapse from design rule 3: the
drawing carries its own pixel size and `dgmFit()` scales it with a transform, so a stroke
here scales with the picture the way every other mark in it does. A rem would scale it with
the *chrome*, and zooming in would thin the line against the boxes beside it.

### The fix that was wrong, and the report that corrected it

The first version styled only `g.node` and `g.edge` — what is *pickable* — and left
`.dgm-canvas { cursor: grab }` alone. Tom: *"the cursor is still Hand most of the time, it
only switches to arrow when near the link."* The canvas is most of what a pointer is ever
over, so styling only the targets changed almost nothing.

It is **two** variables now rather than one, and they stay a pair on purpose: `hand` has
genuinely different conventional glyphs for the two, an **open** hand for a surface that
pans and a **pointing** hand for a thing that is clickable. Keeping both is what makes the
`Hand` option honestly *what it was before* rather than an approximation of it. Measured on
the page: arrow → `default`/`default`, crosshair → `crosshair`/`crosshair`, hand →
`grab`/`pointer`.

### `:active` was the wrong moment, and rule 72 already said so

`.dgm-canvas:active { cursor: grabbing }` fires on **any** press, so the closed hand flashed
on every click of a box that never became a pan. That is rule 72's own lesson wearing a
cursor — a drag needs the feedback and a click does not — and the moment that tells them
apart already existed: `dragging`, set past the 3 px slop, which is where the pointer
capture is taken and for the same reason. A class is added there and removed on pointerup.

### What it turned out to be worth, and it is design rule 27

The change was proposed as an aiming fix. What it did was explain the feature:

> *"This change resolved a major confusion for me, too. Now I understand how the diagrams
> work — click to view Inspector, and how the Inspector list works."*

`cursor: grab` on the canvas is a claim — *this surface is a thing you drag* — and it wins on
**area**, because the canvas is nearly all of the pane. The boxes' own `cursor: pointer` was
visible only in the instant the pointer crossed one, so the drawing read as a picture to pan
rather than as a set of things to click. Every control was wired, the self-check passed, and
clicking a box had always opened the inspector. **Nobody found out that it did.**

That is **design rule 27**, and it is design rule 16 from the far side: not a control wired
to nothing, but a control wired to everything whose signal is drowned by a louder one
belonging to the thing it sits on. Both look exactly like working software, and the second
is harder to find because it *is* working software.

### One thing added that was not asked for

**Arrows highlight on hover**, widening by 1.5 as well as taking the accent — because a
1-unit line highlighted at 1 unit is a colour change a reader must already be looking at to
notice. The reason is a consequence of the change itself: the hand was the only thing on the
page saying an arrow could be clicked at all, so removing it left the arrows with no
affordance whatever. Arrows also take the cursor setting now, which they never did. Two CSS
rules if it should go.

### Verified

809 tests, mypy clean, ruff clean. Driven in Chrome on the real Mensores pair: the controls
render, pressing one moves the CSS custom property and the `aria-pressed` with it, **the
choice survives a reload** (rule 68 — where `followMode` was silently lost), the computed
cursor was read off `#dgmCanvas` and off a box for all three settings, `grabbing` confirmed
on the drag class, and the self-check still reports *every control is wired*. Both
`dgmcursor` and `dgmedge` are in `WIRED_ATTRS`, so a rename fails by name.

## The topbar search does what it says — built 2026-09-02

**Reported as a question, which is how the useful ones arrive:** *"Interesting that I can't
find `frozenset` by searching for it. Nothing appears."* Then, better: *"What does search DO,
exactly? Is it a filter, a focus, or a highlighter?"*

### The answer, and why it was the wrong one

A **filter**, on one list. `matchingRoutines()` walked `ROUTINES` and matched a
case-insensitive substring of `name` or `module`. `state.routineQ` is read in five places
and all five are the Routines group. It is not a focus — it never moves the selection, the
graph or the centre view — and not a highlighter: it marks no occurrence anywhere.

The box says **"Search routines, tables, boundaries…"**. Measured against real names from the
graph before anything was changed:

```
envelope     (a routine word)   Routines  52 match     Database —      Boundaries —
audit_blobs  (a REAL table)     Routines   4 match     Database —      Boundaries —
VIRTUAL_ENV  (a REAL boundary)  Routines  nothing      Database —      Boundaries —
```

`audit_blobs` is the worst row: it *looks* like it worked, having matched four routine names
by substring, while the Database group holding that very table said nothing. A control that
names three things and does one is design rule 16's dead control with two thirds of it alive.

And `frozenset` was two failures stacked. The name search says "nothing matches", which a
reader reasonably reads as *this word is not in this program* — while the source search finds
it **408 times in 136 files**. Two searches with different verbs, and nothing on screen
saying the second exists.

### What it does now — Tom's call, "make it do what it says"

One predicate, `navMatch`, handed to every named group, so a group added later is filtered by
having been born (rule 36). Every list filters **before** it slices: searching a bounded list
would answer about the first eight of forty-three, which is the haystack again and silently.

`structures` now rides with `/api/routines` — 671 rows against 4,786, a seventh of the weight
on a request already made at boot — and there is a **Structures group**, which the search had
nowhere to put before. Its rows carry a `structures.id` and route through `chg`, because
`describe()` already resolves one.

```
audit_blobs   Database   1 match · audit_blobs 5
HookEvent     Structures 1 match · HookEvent DATACLASS
DATABASE      Boundaries 1 match · DATABASE 1371
quaestor      Routines 531 match · Structures 127 match — showing 8
```

### Two defects found in the doing, and one of them was mine

**Rule 44, committed inside the fix for rule 44.** The first draft filtered boundaries on
`b.target` — a field the cover has never sent; it sends `common`. Nothing failed, and the
filter silently matched on the kind alone. Caught only by typing a real boundary name.

**Design rule 1, four times.** `navPkgs`, `navBounds`, `navTables` and `navWaysIn` had no
`note` at all, so a search matching nothing in them left a heading and a total above an empty
body — indistinguishable from a group nobody had opened. `navFilterNote` is shared now.

**And one formulation, not three.** The shared note derived `match`/`matches` from the count
while the Routines note has always said `match` and the new Structures note said a third
thing. All three are now the one sentence — the same reason `modband` writes `stat` and
`stat1` out in full rather than appending an `s` by arithmetic.

### What it deliberately still cannot do, and says so

A boundary **target** is not findable here. The cover carries nine kinds and one commonest
target each; the program has **1,741** distinct targets, most of them expressions rather than
names (`text.encode('utf-8')`, `+00:00`). This group lists kinds, so it filters kinds — and
when nothing matches it says *"these are the nine kinds; a target is in the source"*, because
"nothing matches" alone is the false conclusion this whole change was about.

### Verified

809 tests, mypy clean, ruff clean. The guard
`test_the_navigator_reads_only_fields_the_routines_endpoint_sends` had to be fixed to see
this at all: it derived what the endpoint sends from a regex capturing only the **second**
key of the `_json` literal, so inserting a list between the first and last silently dropped
`plates` from what it believed was served. It reads both statements and the payload's keys
with `ast` now, and it was run against its own defect — reading a field nothing sends fails
by name.

Driven in Chrome on the real Mensores pair, with a real table, a real boundary kind, a real
structure, a package and a way in. Console clean.

### The topbar's three flags — built 2026-09-02, same session

*"Does that mean I can use regex in the Search box?"* — and the honest answer was **yes, in
the other one**. The Code box has taken a full pattern since it was built, behind `.*`, with
`Aa` and `|ab|` beside it; the topbar was `.toLowerCase().includes(q)`. Two boxes that look
alike and behave differently, which is the complaint that produced this whole line of work,
one layer along. Tom's call: give the topbar the same three.

**Kept as their own keys** (`navCase` / `navWord` / `navRegex`) rather than shared with the
Code box's, because the two answer different questions and hunting a name literally while
grepping the source by pattern is an ordinary thing to be doing. One switch governing both
would make that unreachable.

**Compiled once per keystroke, never once per row.** `items()` and `note()` are called for
every group and the predicate for every row — 5,560 names on Mensores — so a `RegExp` built
inside `navMatch` would compile the pattern five and a half thousand times per character.
`navMatcher()` caches on the query **and** the three flags, so a new query misses by itself
and there is no reset for anyone to forget (rule 51). That the lists are in memory is what
makes this affordable at all: rule 45 bites on the 186,786 lines of source, which is why
*that* box had to earn its toggles.

**A broken pattern is an answer, not an absence.** `[unclosed` says *"that is not a regular
expression: …"* in every group, which is the sentence the Code box already used. Reporting it
as "nothing matches" would claim the program lacks what was asked for — the exact false
conclusion this work began with.

**`matchingRoutines()` had to be rewritten to go through the matcher**, and that is the part
worth keeping: it carried its own lowercased `includes`, which is what the matcher does by
default, so it would have gone on quietly working while `.*` reached every group but the one
a reader uses most (rule 51 again).

Two smaller things. `navQuery()` now returns an object, so the boundaries note's `q && !hit`
was always truthy and appended its sentence to the resting state — caught by reading, and it
is `!m.all && m.ok && !hit` now. And whole-word goes disabled under regex on both surfaces,
so the shared handler repaints the topbar as well as the pane.

Verified in Chrome: three flags at boot with the right pressed state; `_VALID_[A-Z_]+` → 5
routines, `^emit` → 30 routines and 3 structures, `[unclosed` → the stated reason; `Aa` off
matches `HOOKEVENT` → `HookEvent` and on does not; `|ab|` disabled while `.*` is on and
enabled after; and **the flags survive a reload and still match** (rule 68). Console clean,
809 tests, mypy and ruff clean.

### Paused 2026-09-02, after the search work

809 tests, mypy clean, ruff clean, working tree clean. Nothing is half-done. Seven commits:
the record split into carryable files, the open list audited, structures compared, one open
list with an owner, the diagram cursor and design rule 27, the topbar search doing what it
says, and the topbar taking a regular expression.

**A server is running** on `http://127.0.0.1:8787/` against `output/mensores`, the two-revision
pair. Nothing depends on it; `pkill -f "dunneflow serve"` ends it.

**Where the list stands.** Item 1 of *waiting on Tom's eye* is closed. Item 2 is closed
differently from how it was written and the entry has been corrected: the 1,347-line
`frozenset` is **not reachable from the flow panel at all** — `external`, `at_boundary = 0`,
a builtin, so no arrow is drawn for it — and the same expression is in the store twice, as
91,224 bytes over 1,348 lines in `call_args` (as written, rule 75) and as **6,924 bytes on one
line** in `constants` (unparsed by `_literal`). The readability risk is therefore a
6,924-character line in the constants surface, which nobody had noticed, and not a wrapped
argument in the flow panel.

**Next, and it is where we stopped.** The real worst case for the flow panel is
`session.add_turn` at `_extraction_state.py:742` — 3,323 bytes over 53 lines, on a resolved
call, so its arrow can actually be opened. Then the constants surface. Neither is started.

**Found and deliberately not fixed, twice.** Clicking a change row files **two** trail steps,
for a routine as much as for a structure — verified pre-existing, rule 76's family, and the
fix belongs to the selection path rather than to any lane. And boundary **targets** (1,741 of
them) are not searchable from the topbar by design; the note names the source search instead.

## The constants surface, and the shortening rule it needs — built 2026-09-02

**Where the last session stopped**, and measuring first moved the target twice.

### What the measurement changed before anything was built

The pause note named a **6,924-character single line** in the constants surface as the
readability problem. It is the *second* largest. `GOVERNED_GATES` in
`_internal/_governed_gates.py` is **8,586 characters** and nobody had noticed it.

And it is a class rather than an outlier. Of 2,638 named values, **739 (28%) exceed one
card line, 301 exceed 300 characters, and 23 (0.9%) exceed a whole card** — which is
exactly the "rare cases" Tom guessed at, quantified. Every one of them is a **single
line**: `_literal` is `ast.unparse`, so not one value in the table carries a newline.

The flow panel, which the note put first, is one outlier and not a class: over every
resolved non-external call, `session.add_turn` is 3,323 bytes and the next is 923. That is
why the two were swapped — 178 rows against 1, and the shape of the constants problem is
uniform.

### The defect nobody had seen, and it was not the line length

Selecting a constant rendered the **routine-shaped inspector**, which answered three
questions a constant cannot be asked:

```
In  0       Nothing in this map calls it. That is either a way in, dead code, or a call
            DunneFlow cannot see — a dynamic dispatch, or a language it does not read.
Out 0       It calls nothing this map can see.
Touches 0   It touches no boundary, table, remote or named file. Everything it does, it
            does in memory.
```

A constant is not a routine. It cannot be a way in or dead code, it calls nothing by
construction, and it does nothing in memory. Three *plausible* sentences, each inviting the
reader to conclude the analysis had failed on a thing it had read perfectly — and the 8,586
characters it had read were the one thing absent. Rule 30's shape one level up: not a label
standing in for an identity, but a **kind standing in for another kind**.

`viewInspectorConstant` is routed on kind beside `FOLD` and `FLOW`, above the first line
that reads a routine's shape, which is exactly why those two routes are already there.

### Tom's three decisions

| Question | His answer |
|---|---|
| How to reach the 0.9% that overflow a card | Card stays bounded and non-interactive; **clicking opens the value in the inspector** |
| Which end of a string to keep | **Head and leaf, middle elided** — one rule, all kinds |
| What a moved constant shows | **A mark only**; the name becomes clickable and opens with both values |

The first was put to him because `.hovercard` is `pointer-events: none` by a recorded
decision — it follows the cursor, so any hit area would put a surface between the reader
and the node they are pointing at — and a scroll box needs the pointer. **Measurement made
the choice easy and it is worth keeping:** the longest qualname in the corpus is 107
characters, two lines on a card. *Names never need a scroll box.* The scroll box is only
ever for a value, so the card's decision survives untouched and the inspector is where the
23 land.

### What was built

**The card is bounded and says by how much.** `-webkit-line-clamp: 3` was a silent filter
(design rule 1) inside the surface whose whole job is to answer *what is this*: it cut
8,586 characters to about 240 and looked exactly like a constant whose value is 240
characters long. It is `CARD_VALUE_CHARS` in the script now, with
`cutWords()` — the sentence `cut()` already used, factored out so a pane and a card cannot
word it two ways.

**Characters, not lines, and the difference is a claim.** No value in `constants` carries a
newline, so the wrapping on screen is the card's and not the program's; *"94 more lines"*
would report a fact about this pane as a fact about the source (rule 32).

**What reads a constant is stated as unanswerable.** The store has no table pairing a
routine with a constant it mentions — `calls` is about calls — so "nothing uses it" is a
claim nothing here can make. `LOST_EDGE`'s discipline in a pane: a missing relation must be
visible, or a program documents as a smaller one that works.

**A moved constant is reachable, and opens showing both values.** Every presence row was a
bare `<code>`: the line said `Constants ◈7`, named seven constants, and not one could be
opened — design rule 16's dead control wearing a label. `PRESENCE` carries a **route and a
subject** beside its key and label, and they come from the server: building `const:` + a
printed name in the browser is rule 30 with the arrow reversed. **Ways in carry none and
stay text** — their route wants the routines they start, `ways_in()` computes those, and
this table cannot reach them; inventing an id to make the row clickable would be a link to
nothing, which is the sentence `queries.py` wrote down before anything needed it.

The row says **which of value, type and finality moved**, because two of them can change
while the value does not — `X: Final[int] = 1` → `X: int = 1` prints the same `1` on both
sides, and two identical strings under a heading claiming they differ is rule 13 in a pane.

### `shorten()`, and the two things that made it right

Head and leaf, middle elided, **whole segments, never mid-token**. Cutting between joints
leaves a string that exists in the program with a piece visibly removed; cutting through one
leaves `...ores_internal_cwd_guard`, which is the `direction: rtl` defect `.navsub` already
carried a note about.

**The leaf is protected where only one token can break.**
`disceptator._anthropic_architect` came out as `disceptator._an…opic_architect` — the
package kept whole, and the navigator *already prints it as the group heading*, while the
one part separating this row from its neighbours was cut in half. The head takes the damage
now: `disc…ator._anthropic_architect`.

**The program root is dropped first, and the server measures it.** All 566 modules begin
`mensores.`, so keeping the head spends nine characters saying what every row says — and,
for a three-segment module, elides the *package* to afford them. `COVER_ROOT` answers the
question `COVER_PACKAGES` had a comment saying it could not ("without knowing the program
root"). A client that derived it from whatever list was loaded would shorten one name two
ways on two surfaces (rule 24).

**742 of 1,019 navigator rows now show whole**, against essentially none before —
`moduleTail` always prefixed an ellipsis. The CSS backstop fired **0 times**, measured on
the page.

### Four defects found in the doing, three of them mine

**Rule 51, in the settings.** `state.insp` was declared in **both** `shell.js` and
`settings.js`, and only `settings.js` wins — `adoptSettings` overwrites every persisted key.
Two new sections were added to the copy that does not win, the page was opened, and both
rendered `data-open="undefined"` with the value box measuring `clientHeight: 0`. Nothing
failed and nothing was logged. The shell's copy is now `{ ...DEFAULTS.insp }` — spread, not
shared, because a shared object would write a toggle back into the defaults and a reset
would restore what the reader had just changed.

**The root lookup stripped nothing.** The first version asked "which segment names a
package" and `mensores` **is** a package — the modules directly under it belong to one — so
it matched at position 0 every time. `PKG_IDS.size` was 46 and correct, the function ran,
and 1,019 rows still read `mensores.….\_advance_gate`. Found by reading them.

**`_constants_moved` built its rows by hand and gave them no route**, so 23 of the 30
constant rows were clickable and the **7 that mattered** were not — the one band whose whole
claim is *this is not constant any more* was the one a reader could not open. The route
comes from `PRESENCE` now rather than being spelled a second time.

**A floor guaranteed the overflow it looked like it prevented.** `Math.max(4, budget -
head.length)` added four characters to a head already wider than the field. Caught by
asserting the budget across **every width from 8 to 40** rather than at the two the fields
actually use — which is the range rule 53 is about.

### Verified

818 tests, mypy clean, ruff clean. The two new guards were each **run against the defect
they were written for** (rule 59): removing `nav` from the moved rows fails
`test_every_presence_row_can_be_acted_on_or_says_it_cannot`.

Driven in Chrome on the real Mensores pair: `GOVERNED_GATES` whole and scrolling
(`scrollHeight` 2382 against `clientHeight` 446), a 36-character constant with **no mark and
no ellipsis**, `EXPECTED_SCHEMA_VERSION` opening from the presence line to **28 beside 27**
labelled by revision, 15 presence rows as buttons and the 3 ways in as text. Console clean,
self-check green.

**One thing the automation could not do, and rule 38 says so plainly.** The browser context
reports `outerWidth: 0` and will not resize, so everything above was measured at a 900px
viewport where the narrow layout sets `#inspector { display: none }` — the pane was forced
visible with an injected stylesheet to measure it, and the clicks were scripted. A scripted
click proves the handler and not the path to it (rule 48). **A look at a real window is
owed**, and it is the same debt the blank-graph fix has been carrying.

### Still open

Chunk B — the remaining twelve `text-overflow: ellipsis` sites, which all still cut the
tail — is planned and not started: `.chg-mod`, `.gotonode`, `.wl-title`, `.trailstep`,
`.rank-name code`, `.callhead code`, `.srcpath-v`. With them, the `selfCheck` assertion that
the CSS backstop never fires.

**Noted and not fixed:** `holds`, the fold pane's section, is not in `insp`'s defaults, so it
starts closed whatever it wanted and "Collapse all" cannot see it until someone has opened it
once. Its default is a decision about that pane, not this one.

**A residue, stated:** the `chg` route reads ids through `navIds`, which splits on a space. A
*named file* is the one subject here whose name can contain one. Mensores has 0, and a
constant's `module.name` cannot hold one at all, so the corpus does not exercise it; the fix
belongs to `navIds`.

## Two dead controls, reported at the keyboard — fixed 2026-09-02

Both arrived the way the useful ones do: as an account of what the reader tried, not as a
diagnosis. Both were **design rule 16 with every part working**, and both were rule 30
underneath — an item that carried no identity, or a route that could not consume one.

### "On its own" was offered, selected, handled — and undone twice

*"In the header, I have selected society-2026-08-29 on its own. However, the next line down
still shows BASE then compared with society-2026-08-26. How can this be cleared so I view
just one version, no diff?"*

**It could not be.** And everything about the option was already right: it exists in the
control, it is selected, the handler sets the field, drops `FILEPAIR`/`FILEDIFF`, clears
`CHANGES`, and carries a comment saying *"On its own is a real answer and must not spend
seconds fetching a comparison nobody asked for."* Measured before anything was changed:

```
state.comparedRev  ""            the handler did its job
CHANGES            null          the handler did its job
comparedRevInForce 2026-08-31T22:53:15Z   ← invented
comparing()        true
```

**First, `comparedRevInForce()` could not tell two answers apart.** *Nothing chosen yet* and
*chosen: on its own* were both `""`, so the fallback — which exists so a first visit marks
its file list without anyone opening the worklist — filled the choice back in. **Rule 49**:
a fallback that yields a plausible value has hidden the failure it was written for.

`comparedRev` has three states now. `ALONE` is a **named state, not an id**, the way
`sourcedb.py` makes `WORKING` one; it cannot collide with a revision, because those are
instants. `pairLost` skips it, or the next reload greets the choice with *"the revision you
were comparing (alone) is no longer here"* and silently resets it — **rule 43**, crying wolf
about a thing that never existed.

**And that fixed nothing the reader could see, which is the half worth recording.**
`versionStrip()` derived the compared end **again**, with its own copy of the same fallback:

```js
const compared = REVISIONS.find(r => r.revision === (CHANGES && CHANGES.compared))
              || usable.find(r => r.revision !== (base && base.revision));
```

and its "on its own" branch tested `usable.length < 2` — whether the **program** has a second
version — so on a two-revision pair it could not fire at all. The state went right,
`comparing()` went false, and the strip three lines away went on naming a pair. **Rule 51**:
one question, one place that answers it.

The strip now says **which kind of none** it is. A program with one version *cannot* be
compared; a reader who chose "on its own" *chose* not to be. Reporting both as "nothing
compared" shows a state the reader can change as a limit of the program (design rule 1).

### The shelf could drop a thing and never open it

*"Using the Kept feature of Trail, I see my Kept item, but there is no way to select it and
therefore view it. I can Drop it, but nothing else."*

A pin was `{label, note}`. **Neither is an identity**, so the shelf could render a row and
drop a row — dropping needs only the row's position — and could never open one. Rule 30 in
the one surface built for the thing rule 30 is about: the shelf exists so a detour does not
cost you the thread you were on, and it could not take you back.

**The three kinds are not one shape, and finding that out is what made the fix right rather
than plausible** — the same discovery rule 30 records about the four navigator routes. A
routine, a constant and a structure are **nodes**. A fold is a **box**, whose id belongs to
the drawing and means nothing to `/api/node`. An arrow is a **flow**, and it needs the
compartment it was drawn in. `.gotonode` already routes two id spaces by which attribute is
present, and its comment says why: reading one as the other resolves plausibly and silently
to the wrong thing. `PIN_ROUTES` is a table, so a kind nobody wired logs an error rather than
falling through to a default that looks deliberate.

**Pins were keyed by label.** `some(p => p.label === label)` collides every `__init__` in the
program and 531 routines sharing a module word — keeping one showed the other as kept, and
dropping one dropped the other. Keyed on the subject now.

**A pin kept before subjects existed has none.** It stays plain text and says why, rather
than being routed somewhere plausible. The shelf is the last place to guess.

### Verified

823 tests, mypy clean, ruff clean, self-check green, console clean. Driven in Chrome on the
real pair: the strip reads *"VERSION society-2026-08-29 — on its own, nothing compared"*,
change marks go 1 → 0, it toggles back, and it survives a reload with the control showing
the right option and no note (rule 68). Keeping a constant and a routine records both
subjects; clicking a shelf row's label selects it, `SPECIMEN.id` matching and kind
`CONSTANT`. **Tom confirmed both at the keyboard.**

**Seven guards, each run against the defect it names**, including the pin pairing in *both*
directions — a kind nothing routes and a route nothing keeps each fail.

Two of them were blind first, and the second is the one worth keeping:

- One tripped on the **comment quoting the code it checks** — the sixth time in this file,
  so `_fn_body` strips comments now. `_code()`'s own docstring already said five was enough
  to call it a habit rather than an occasion.
- The other reported **MISSED when the guard was fine and the *mutation* was wrong**:
  `replace("if (!comparing())", ..., 1)` hit the first of **eight** occurrences in the file,
  in a different function entirely. Rule 59 from the other side — a harness that does not
  prove it changed what it names reports a false result *about the guard*, and the obvious
  reading of that result is to weaken a check that was already right.

**Not exercised on screen:** the fold and flow pin kinds, which need a compartment drawn.
The pairing is guarded at the source in both directions, which is why that guard exists
rather than a click.

## Chunk B: every field fits its own box — built 2026-09-03

The record's plan was *"the remaining twelve `text-overflow: ellipsis` sites all still cut
the tail; they move onto `shorten()`, and with them the `selfCheck` assertion that the CSS
backstop never fires."* Measuring first changed three of those twelve, changed the
mechanism, and found the assertion had been **promised in a comment for a session without
existing**.

### The assertion `shorten()` already claimed to have

`shorten()`'s docstring ended *"`selfCheck` asserts the backstop never fires."* It did not.
`selfCheck` checked three things and none of them was a width. A sentence promising a guard
reads exactly like a guard, and the next person to lean on it has no way to tell — rule 37
in the documents rather than in a check.

It could not have been written earlier, and that is the interesting half. Against a
**constant** budget the assertion is rule 43: a constant is wrong at every width it was not
measured at, so the check would report a narrow window as a defect and be switched off. It
became writable the moment the budgets stopped being arithmetic.

### A constant is arithmetic wearing a measurement's clothes

`MODULE_BUDGET_NAV = 30` is honest because `.navsub` is `max-width: 11rem` — every one of
its 1,175 rows is the same box, at any window and any root font size. **None of the seven
fields left over is like that.** They are flex children with `min-width: 0`, so each one's
width is what is left after a badge, a count and a line number have taken theirs, and it
differs *per row inside one window*: `.rank-name code` is 156px on one row of the cover and
112px on the row below it, because the `kind-tag` beside it is a different width.

So `fitFields` takes each budget off the box the text is actually in. Reads batched before
writes, candidates measured on a **canvas** rather than in the DOM — `shorten()` is
monotonic in its budget, verified over module names, qualnames, paths and command lines with
**0 non-monotonic steps**, so the widest budget that fits is a bisection of about seven
`measureText` calls and not one layout between them. **4 ms over 120 fields; 4.5 ms over the
navigator's 1,175**, which is why it runs at the end of every `render()` and does not wait
for a frame. Waiting would cost more than it saves: a frame painted before the pass is a
frame of the untruncated string, on every keystroke.

### What measuring struck from the list

Three of the twelve came off, and each for its own reason.

**`.wl-title` is prose and `shorten()` would have destroyed it.** All 107 of Mensores'
findings contain a space and 80 contain a dot, so the middle-elide reads a title as a dotted
name: the head becomes ``self`` and the leaf becomes the whole predicate, and the *subject*
is elided out of the middle of a sentence. Prose is cut at its tail, where a sentence carries
least and a qualified name carries most.

But the field was in far worse shape than the list said. **94 of 94 rows clipped** — a 172px
box against a median title of 73 characters needing about 420. Every reader saw the first
thirty characters of every finding and none of them ever saw the predicate, on the surface
Tom clears. Tom's call: **two lines, then a mark, with the whole title on the hover**.
`-webkit-line-clamp` was struck from the constants card for being a *silent* filter and this
is the same mechanism without that fault — the clamp draws its own ellipsis and `prose` hangs
the full text on the hover, so the mark says something went and the hover says what.
92 of the 94 carry that hover; the two that fit in two lines carry none.

**`.srcpath-v` is a dead field.** `#srcPathV` is written by nothing in the whole tree — the
entirety of it is the 28-character literal in `index.html`, which fits with room to spare. Its
`overflow`, `text-overflow` and `max-width` were sizing a string that cannot arrive: the same
dead-CSS fault as the three rules struck beside it when the button went (rules 44 and 48).

**`.callhead code` was a contradiction, not a budget.** The expression is rendered through
`breakable()`, which marks every joint with a `<wbr>` so a name breaks on a dot instead of
mid-token — and `white-space: nowrap` here forbade breaking at all, so every one of those
marks was inert. `.callin code` and `.calldecl code` render the same strings through the same
function and wrap correctly: measured, **98 and 88 characters with no overflow**, against this
one clipping 1 row in 6 at 29 characters. One idea, two answers, and the wrong one was the odd
rule out (rule 13). It wraps now and needs no fitting at all.

### Four defects in the fitter itself, every one found on screen

*None of these was found by review, and three of them had a comment beside them asserting the
opposite.*

**It measured the pane mid-transition.** `.body` carries `transition: all`, so collapsing the
inspector animates the grid's columns. `render()` is synchronous: it writes the attribute and
the pass measures while the columns are still on their way, reading the width the pane is
*leaving*. Every field fitted itself perfectly to a layout that had already gone, and the tell
was three fields still overflowing after a pass that reported cutting nothing. A
`ResizeObserver` on the panes answers it for every cause at once — a pane toggled, a rail
dragged, a window resized, a reader changing their browser's font size, which reports no event
at all (rule 51).

**It measured a box its own last write had shrunk.** `.rank-name code` is a flex item with an
`auto` basis, so shortening its text shrinks the box to the shortened text and the next pass
measures what the last one left. It ratchets and can never grow back: driven across four
container widths from 300px to released, the box read **81px at every one of them** and the
string never changed. The first version of this pass carried a comment claiming the loop was
impossible; it was measured happening an hour later. Phase 1 now writes the whole string into
every field before phase 2 reads a single width — free, because all three phases are one
synchronous task and the layout flushes once however many fields there are.

**It measured the border box.** `getBoundingClientRect().width` includes padding and border and
text sits in neither, so every field was handed its own padding twice. `.trailstep` has `.3rem`
a side and was the one field of eight still spilling after a pass that reported fitting it:
**201px of text written into 192px of room**, by arithmetic that thought it had 201.
Subtracted from the rect rather than read off `clientWidth`, which is 0 on an inline element
and would collapse every such field to a single mark.

**It compared two floats for exact fit.** A fitted field is usually sized *to* its own content,
so the space available and the space needed are computed from the same text and come out
**exactly equal** — a strict `<=` is a coin flip on the last bit, and `mensores` lost it:
53.3px of text in 53.3px of room, declared too long, cut to `men…res`. Eight characters to
seven. `FIT_SLACK` is one constant used by the fitter **and** by `selfCheck`, so the two cannot
disagree about what fits (rule 13).

### And two layouts that were wearing a shortening rule's clothes

**The trail squeezed its steps instead of scrolling them.** `.trail` is `overflow-x: auto` and
`render()` scrolls the current step into view, so scrolling is what the bar was built to do —
but its items were left shrinkable, and a flex item that can shrink does, before its container
ever overflows. Three steps in a 404px bar were squeezed to fit and clipped. It looked like a
shortening rule for as long as the stylesheet was doing the cutting; `fitFields` is what named
it, by reporting `mensores` as `men…res`. A shortening that saves one character is not a
shortening, and the box was the thing that was wrong.

**A caller row cannot hold a name and a module on one line.** Splitting `.gotonode` into two
boxes fixed the *tail* — 7 of 11 rows had been overflowing 242px, with
`mensores.chaos.chaos_scriba_kill` and `mensores.chaos.chaos_broker_kill` both reading
`mensores.chaos.cha…`, two different modules drawn as one string — and could not fix the
*room*. On a 344px pane every side-by-side split measured as a trade: protect the name and
`mensores.disceptator._architect_dispatch` reduces to `dis…tch`; floor the module at 6rem and
the name goes to `resolve_a…_dispatch`. Neither field is worth having in those states.
**Tom's call, put to him with the three measured against each other: stack them**, which is
the shape the navigator has always used for this pair. Both whole, at 36px a row instead of 18.
All 11 rows now show their name and their module entire.

### A label is not the text on screen

A fitted field's text is a shortened one, so a trail step built from it records `stor…items`
as the place you were — rule 33 and rule 30 in the surface built to take a reader back. Every
label reader goes through `labelOf` now: `data-label`, then the unshortened `data-full`, then
the text, rebuilt from the children so a control *containing* a fitted field reads as it would
have read unfitted. Five call sites, one accessor (rule 51).

`.trailstep`'s title carried `note || label`, which was right while the label was always
wholly on screen. Once it can be elided, a step *with* a note had the whole of it nowhere —
its text cut and its hover talking about something else. It carries both.

### The band tables say what kind of string each column holds

`modules_explained` is why. Its meta column is a **path** where every other band's is a dotted
module, and its label is a **module** where every other band's is a leaf name — exactly
inverted. A kind guessed from the shape of the markup would drop a program root off a path,
find none, and look entirely deliberate. `labelFit` and `metaFit` are declared per band and
there is no default behind them: a band that forgets writes `data-fit=""` and the fitter
answers with a named error (design rule 16).

### Verified

**835 tests** (12 new), mypy clean, ruff clean, self-check green, console clean. Driven in
Chrome against the real pair at 1396px: **zero fitted fields overflow** on the cover, the
navigator, the change list, the worklist, the inspector and the flow panel; ten passes back to
back drift **not one character**; a field put through four container widths shortens and grows
back; 4 ms a pass.

**Twelve guards, each run against the defect it names, all twelve CAUGHT.** The mutation
harness proves its baseline green first (rule 59).

*One existing guard earned its keep.* Four of the explanations above were first written as
HTML comments **inside template literals**, where a backtick closes the literal and the page
comes up empty — the defect `test_no_backtick_hides_in_an_html_comment` was written for, on its
third occurrence. They were moved to JS comments above their functions, which they should have
been anyway: inside a `.map()` body each one shipped once per row.

### Not done, and why

`.navsub` keeps its constant. `max-width: 11rem` makes every row of it the same box at every
window and every root size, so 30 is honest there, and 1,175 fields through the fitter on every
keystroke is a real cost for no gain. The boundary is stated in `shorten()`'s docstring: a
**fixed rem width takes a constant, a flex-derived one is fitted**.

The fold's member rows keep the backstop deliberately. A member row carries an invocation line
— `_profile_name_or_none(self) → str | None` — which is not a jointed name, so the middle-elide
would cut it to `_profile…→ str` and throw away the parameters, which are the reason to have
opened the class. A signature's identity is at its head, like prose, so the tail cut is already
the right end. `selfCheck` does not watch it, because nothing there claims it fits.

**Still owed: a real window.** Everything above was measured at 1396px in a browser context
that reports `outerWidth: 0`, refuses to resize, and whose screenshots did not track the live
DOM — rule 38, the same debt the blank-graph fix carries. The numbers are measurements and the
guards are guards; what none of them is, is a look.


## No pane assumes what it was showing is still true — 2026-09-03

Reported at the keyboard, mid-rabbit: *"Found myself at `disceptator._extraction_state
<module>` ... When I change the center panel to Code, that panel shows
`mensores/_internal/_governed_gates.py` which is not what I expect to see. Is this accurate,
and I am seeing what I should, or is the center panel off?"*

**The panel was off.** `/api/node` gave `mensores/disceptator/_extraction_state.py` for that
node all along. What was on screen was `state.codeFile` — which is **persisted** — so it was
the file the constants session left open two days earlier, from a package the reader had never
opened, rendered with a title and a path and nothing to say it was stale. The store was right,
the selection was right, and the walk was right.

### One caller, and it was the wrong one

`followSelectionIntoCode()` opens with `if (!codeOnScreen()) return;` — correct, there is
nothing to walk when the pane is not up. It was invited from **exactly one place**, the end of
`loadSpecimen`. So selecting a routine while Code sat behind another mode returned at that
guard and left no trace, and the mode switch never asked again. The condition has two halves —
*the selection changed* and *the pane became visible* — and only the first was served.

### Tom's rule, which is larger than the defect

*"EVERY mode switch should re-verify where it should be ... Users can move around using nearly
any panel — left, center, or Inspector. Every possible venue that can change the point of view
should be considered, so no control should ever expect that it 'knows' what it was showing
before is still true."*

**This file already said so, in one branch.** The table's:

> *"Here rather than on the mode toggle because there are five ways into table mode — the
> toggle, `Enter` on a hovered navigator row, two crumb routes and the code browser's hand-off
> — and a call at each is exactly the list rule 51 says grows. Every one of them arrives here."*

The audit found three panes on each side of that lesson. Reconciling inside `render()`:
**table** (`ensureTableOverlay` + `revealSelectedRow`), **glossary/naming**
(`ensureVocabulary`), **curiosities** (`ensureCuriosities`). Relying on every call site to
remember: **code** (1 site, and the wrong one), **stack** (4 sites), **diagram** (7 sites).

So all three moved into `render()`, where every route arrives.

### And the four graph call sites were mis-ordered as well as incomplete

Every one of them sat **before** its own `render()`:

```js
if (state.graphLayout === "stack") ensureGraph();
render();
```

so each was mounting into the *previous* view's layout — the exact defect recorded on the mode
toggle as *"the graph should have been there"*, fixed there in 2026-08 and left standing at the
other three. A hidden container is 0x0 and `fitView` framed the stack for the whole window.
Arriving in `render()` they are ordered right by construction, for every route including the
ones nobody has written yet. The guard that watched the toggle now watches `render()`, which is
a stronger statement: it speaks for every route rather than for one handler.

### What it cost to make the reconcile safe

`render()` runs on every keystroke, so a reconcile must be **silent when there is nothing to
do**. Two of the three needed work for that.

**`ensureDiagram` claimed its lock before asking whether it had anything to do.** It ran to the
bottom on every call, found both content guards satisfied, and still finished with
`renderDiagram()` — which rewrites `#diagramMount`, the mount that exists precisely so
`render()` does not touch it, and takes the laid-out SVG and the reader's pan and zoom with it.
It compares the drawing it has against the drawing that is wanted first now. Verified: the
`<svg>` node is the same object after five renders, transform unchanged.

**The code walk had to stop fighting the reader.** An unconditional walk puts the pane back on
the next repaint, so a reader who opens a second file to compare it with the first could not
keep it for one paint — an automatic move fighting a deliberate one, which `revealSelectedRow`
and the trail scroller are both careful about. `codeFollowedFor` records *which subject* the
pane has been walked for, not *whether* it has been walked: a flag would be cleared by every
selection and set by every walk, and the deliberate open undone immediately. `openCodeFile`
marks the subject serviced, so the reader may go anywhere inside one selection and is still
followed the moment they pick something new.

`ensureGraph` needed nothing — *"cheap to call from anywhere that might land in graph mode; it
decides for itself"* was already true and already written down.

### Verified

839 tests (4 new), mypy clean, ruff clean, self-check green, console clean. Driven in Chrome on
the real pair, Tom's sequence exactly: land on `<module>` from graph mode with
`_governed_gates.py` persisted, switch the centre to Code — **`_extraction_state.py`**, the file
the node lives in. Then the two things a render-time reconcile could have broken: a file opened
by hand **held its ground across three repaints**, and picking a new routine **followed again**.
Seven centre-mode switches in a row, every one showing the selection's own file.

**Five guards, each run against the defect it names, all CAUGHT** — and one was blind first and
found by mutation: it asserted `codeFollowedFor` was *named* in the walk and passed with the
early return deleted, which is rule 37 again (naming a thing is not using it).

*`_fn_body` could not see an `async function`* and reported `ensureDiagram` as "no longer a
function declaration" — a message that reads as the code having moved rather than the helper
being blind, and whose obvious response is to weaken a guard that was pointing at the right
thing. Both ends of the slice take `async` now.

### Checked and not a regression

The stack's backing store is 300×150 against a 245×293 stage in the automation tab. Measured
against `HEAD` with the change stashed: **identical**, so it is the recorded rule-38 context and
not this. It is the same context that reports `canvas MISSING, frames 0`.

### It is rule 78

Tom's call, put to him because the numbers are permanent addresses in this project's
constitution and 768 citations point at them. **Rule 78: a pane brought up to date by the
control that moved it is only as correct as the last person to add a control.**

Its own address rather than a note under rule 51, and the distinction is the reason it earned
one: rule 51 is about a *rule* rotting across call sites, where this is about **state going
stale in silence**. Nothing throws, nothing logs, and the pane looks entirely deliberate —
which is why this arrived as a question about whether the tool was telling the truth rather
than as a bug report.

The body carries the three things that make it usable rather than agreeable: the reconcile
must be **silent when there is nothing to do**, because `render()` runs on every keystroke;
an **automatic move must not fight a deliberate one**, or the rule turns a pane into a cage;
and the guard's condition had **two halves with an event on only one**, which is the shape to
look for. Cited from four places in `shell.js` and from the guards.

Enumerated after adding it rather than counted: **1–78 with 21 absent, 77 rules, and the
index in `CLAUDE.md` and the bodies in `RULES.md` agree exactly** — no index without a body,
no body without an index. `BRIEFING.md`'s file-size table is left as taken and now says so:
its counts and byte sizes are of 2026-09-02, and rewriting one column without retaking the
other is a different measurement under the same label (rule 24).

### Left open

**`<module>` is answered in a routine-shaped inspector.** It draws *"Nothing in this map calls
it. That is either a way in, dead code, or a call DunneFlow cannot see"* — three plausible
sentences, none of them the true one, which the routine list already carries as its own `why`:
*"Module-level code: runs at import, before anything is called."* Same shape as the constants
defect: a pane answering a question this kind cannot be asked. `viewInspectorConstant` is the
precedent — route on kind. Not built; Tom found it on the way past this one.


## The code view, looked at — 2026-09-03

Four things in one screenshot, at Tom's own keyboard and his own window. **Three were real
and one was a question that answered itself.**

### The greenbar: a row was breaking twice

*"Every line has a blank between it, like old IBM greenbar printouts. Kind of takes me back
40 years, but that's not a good thing."*

`rows.join("\n")` — the reflex, the thing every other list builder in this file does, and the
thing that makes generated markup readable in devtools. Inside a `<pre>` it is not whitespace
between tags, it is **content**: `white-space: pre` renders it as a line break, and the row
span is `display: block` and has already broken the line. So every row was followed by an
empty one. **1,703 rows in 58,932px — 34.6px a row against a 17.28px line-height**, and
29,000px of scrolling carrying nothing. Now 29,520px.

**Three surfaces had it and only one was reported.** The centre's code table, the navigator's
code pane, and the glossary's citation viewer; the second and third were found by going to
look at the other `<pre>` builders once the first was understood. `srcPane` keeps its newline
and that is the rule rather than an exception to it — its rows are *not* wrapped in a block,
so there the newline is the only thing breaking the line. What has to hold is that **a row
breaks once**, never that a separator has one spelling, and the guard asserts both directions.

### The indent was not an indent

*"The indent is also large, so you have to scroll over to see the text. If that's real, ok,
but otherwise it needs to be removed."*

It is not real: it is the margin column, a fixed 12rem reserve where marks are drawn. Measured
on the file he was looking at, it fails **from both directions at once**:

| | |
|---|---|
| rows carrying no mark, paying the whole indent | **1,573 of 1,703 — 92.4%** |
| marks that exist and are clipped by that same 12rem | **49 of 130 — 37.7%** |
| mark widths | min 85px · median 185 · p90 341 · **max 1,263** |

A comment in `tokens.css` records that it was already narrowed once from 15rem to 12rem for
the first of those reasons. That treated the symptom: no single width serves both, because
the long tail means "wide enough for the marks" is 1,263px and "narrow enough for the code"
is zero.

Three ways out were measured against each other and put to Tom: fold it, move marks to the
end of the line, or size the reserve to the file's own widest mark. **His call: fold it.**
Code starts at 248px with the margin shown and **76px folded** — 172px back at a 16px root,
258px at his 24px.

**Folded, a marked line still says so.** A glyph from `MARK_GLYPH` — the same table the
navigator's pane reads — sits where the column was, carrying the whole mark on its title
(`markTitle`, the same function, so one answer serves two surfaces). Dropping it would make
the fold a silent filter over the one thing the margin exists to report (design rule 1, rule
45). Both forms are in the markup and a stylesheet chooses, so folding repaints nothing.

**And a file with nothing to mark renders no mark elements at all**, whichever way the fold
is set — the toggle is a preference between two jobs, this is a fact about the file. The first
attempt at that was a `.nomarks` CSS rule, and it **lost on specificity** to the fold's own
`:root[data-code-marks="off"] .codetable .cglyph` — (0,3,0) against (0,4,0) — so the column
stayed 20px wide on a file that could never fill it. Answered in the builder instead: not
rendering a thing cannot lose a cascade it is not in.

### The line numbers: asked and answered, nothing changed

*"There's a bit of space before the line numbers, I'm guessing that's to permit large numbers
— again, if that's the case, leave it."*

That is exactly what it is. `.cnum` is `3.5rem`, right-aligned, which holds four digits and
the file is 1,703 lines. Left alone.

### The grey area: provenance, and now a fold

It is the line that says these bytes came from the content-addressed sidecar **as measured**
at a recorded instant, not as the tree stands now — the same claim the inspector's source view
makes, and design rule 13's provenance. It is 46px of a pane whose whole job is the lines
above it, **22.6% of the body on a short window**, and it says the same sentence on every
file. So it folds, per Tom's standing rule that anything that can collapse should.

A fold rather than a hide: the bar stays and says what it is, so there is something on screen
to open (rule 45, design rule 23).

**That fold was itself a dead control in its first draft**, which is worth more than the fold
is. `render()`'s code branch repaints its chrome only when `codeDomKey()` moves — file,
availability, overlay — because rebuilding it re-attaches the table, measured at 1,358 ms on
`_server.py`. The footer is chrome. So flipping the state, persisting it and calling
`render()` set the field and **changed nothing on screen**: design rule 16 with every part
working, in a control added to satisfy a rule about controls. Putting `codeProv` in the key
would fix it and buy a full re-attach for a one-line toggle, so the handler writes the two
attributes itself — the narrow update this file already records for the file filter.

### Verified

842 tests (3 new), mypy clean, ruff clean, console clean. Driven in Chrome: row pitch 17.3px
against a 17.28px line-height on the centre and 16.8 against 16.8 in the navigator's pane;
the margin folds to 76px and back to 248 and survives a reload folded (rule 68); an unmarked
file renders **zero** mark spans, starts its code at 56px and draws no toggle; the glyph
carries `import: import — __future__.annotations` on its title.

**Eleven mutations across three guards, all CAUGHT**, including the counter-case that
`srcPane` must *keep* its newline — without it the rule reads as "never a newline" and the
next person deletes the one that is load-bearing.

*Two guards went blind rather than green on the way, which is the only reason they were
survivable.* One matched `<pre class="codetable"` including the closing quote and threw when
the class gained a conditional second token; the other was `_fn_body` failing on
`async function`. A guard that cannot find its subject must say so — one that quietly finds
nothing passes every mutation of itself (rule 37).

*And one self-inflicted defect worth recording*: the first pass added `const bare` at the top
of the builder while an older `const bare` still stood near the `return`, which is a
`SyntaxError` and took the whole page down. `test_the_javascript_parses` caught it on the next
run. Two declarations of one name in one scope is what a large, careful, multi-step edit does
when it is applied in pieces.
