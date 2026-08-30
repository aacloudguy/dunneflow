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
  the machinery sitting beside it.

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
prior art first; `CURIOSITIES`; the worklist's two jump buttons; the two vocabulary-lane
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

**Next: the graph as `colorBy: 'change'`** — and it still wants Tom's decision on the
colour channel before it is built. Read `6g`.

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

**The graph as `colorBy: 'change'` is what remains, and the colour-channel question below
is still owed to Tom before it is built.**

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

*Unchanged from before, and none of it blocked by the above:* the rendered markdown is not
revision-named, so a second analysis overwrites the first's map; `--revision` on `analyze`
is still unimplemented (and is now a smaller question than it was — a version is read from
the program, so what `--revision` would add is a reader's *declaration* where the program
says nothing); the navigator's search box pinned-when-open / icon-when-closed (decided
2026-08-30, not built); `m.<module>` as a language feature, with research owed on prior art
first; `CURIOSITIES`; the worklist's two jump buttons; the two vocabulary-lane precision
defects; per-plate sphere scaling and stack orientation; packaging as a binary. One question
never answered: **what is an occurrence for LOST_EDGE** — the 142 callers, or the rival
definitions? 93 of Mensores' 106 findings are LOST_EDGE, so it decides the feature. And the
blank-graph fix (rule 49) is still reasoned and guarded rather than seen.

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
