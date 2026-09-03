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
| `RULES.md` | the 77 engineering rules **in full**, with the false result each came from | before working in the area a rule governs |
| `DESIGN-RULES.md` | the 27 dashboard design rules in full | before building or changing a view |
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
uv run dunneflow mirror   <path>                    # words the docs define that the code never uses
uv run dunneflow query    <path> --sql "..."        # ask the graph directly
uv run dunneflow migrate  <dir>                     # stored paths: absolute -> relative
uv run dunneflow serve    <dir> [--revision <rev>]  # the dashboard, on one version
```

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
- `docstore.py` — `docs.db`. **Parallel to the graph, never inside it.** A doc rescan
  never touches `graph.db`, code-only analysis stays cheap, and the corpus stays a
  separately handable artifact — many will hand over a charter and never a line of
  source. The join is one `ATTACH DATABASE` away.
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
- `web/vocabulary.py` — the two naming lanes served, and matched against one name. The
  membership test is `Convention.glob`, which is the same string the exceptions query is
  built from, so the claim and the population cannot drift (rule 41).
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
