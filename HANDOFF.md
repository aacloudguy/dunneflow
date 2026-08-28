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

- `/api/node` and `inspector.js` from the previous chunk are a parallel implementation of
  the shell's own `viewInspector()`. The shell's is the ratified design; the endpoint is
  the real data. They need reconciling in chunk 2, not two inspectors.

- The usage report screen's content.
- Layer selection UI — time slider, revision list, two-point comparison, or all three.
  That is the next conversation, not this one.

Settled: this is a **reading tool** you open to understand something — not a working
tool kept open while editing. Layers are how it stays true as the code moves.
