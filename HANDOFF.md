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
| **Interactive dashboard** | **designed 2026-08-27, not yet built** |
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

**Stack.** Astro 5 + Tailwind 4, matching `../wct-site`. Its brand tokens are
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

**5. The dashboard proper.** Astro 5 + Tailwind 4, the design ratified across this
session and mocked at the artifact URL in
`memory/project-dunneflow-dashboard-ui.md`. Port the mockup's decisions, not its code.

**6. Then, and only then, temporal layers.** Snapshots keyed by revision, the flow diff,
the scrubber. Identity is already position-independent, which was the prerequisite.

**7. Attestation**, on the layer storage — see "Attestation: promoting an inference"
above. Not before it; it needs the same content-addressed, revision-keyed store.

Deferred, recorded so they are not lost: a graph viewer that holds 10,000+ nodes (see
`../usdgraph`, NetworkX to OpenUSD); cross-process stitching; TypeScript extraction;
Swift extraction.

### Still open

- Layer storage builds on the same sidecar: content-addressing is version-control
  agnostic by construction, since it never asks where the bytes came from. Git,
  Perforce, Lore, a nightly cron, and a release tag are all the same problem.

- The usage report screen's content.
- Layer selection UI — time slider, revision list, two-point comparison, or all three.
  That is the next conversation, not this one.

Settled: this is a **reading tool** you open to understand something — not a working
tool kept open while editing. Layers are how it stays true as the code moves.
