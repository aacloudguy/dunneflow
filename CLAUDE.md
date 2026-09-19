> **This is the v2 tree. Read `V2-START-HERE.md` first, then `PLAN-v2.md`.**
>
> This file below is still v1's and has not been rewritten. Where it describes the tool it
> is accurate; where it describes state, commands or architecture it describes v1. v1 itself
> is at `../DunneFlow`, untouched and still runnable.

# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. Built for a reader who reads code but does not write it, and who thinks in
entrypoints, flows, routines, and boundaries.

**New here? Read `BRIEFING.md` first** — where the code lives, what is built, what we are
doing now, and which decisions are closed. This file is the standing orders; `HANDOFF.md`
is the chronological record.

The rules moved out of this file when it outgrew what a session can carry, and the split is
by *how often you need it*, not by importance. **It has been done twice**: the rules and the
figures left on 2026-09-02, and the architecture, the surfaces, the packaging and the
ground truth left on 2026-09-18, when the file had grown back to within 2 KB of the size
that caused the first split. What is left here is what a session needs *before* it knows
what it is doing:

| File | What it holds | When to read it |
|---|---|---|
| `CLAUDE.md` | what the tool is for, the commands, the verification gates, and the **index** of every rule | every session — it is loaded for you |
| `RULES.md` | the 106 engineering rules **in full**, with the false result each came from — numbered to 107, because 21 does not exist and the numbers are addresses | before working in the area a rule governs |
| `DESIGN-RULES.md` | the 31 dashboard design rules in full | before building or changing a view |
| `ARCHITECTURE.md` | what each module owns, and what each surface answers — `serve`, `mcp`, `query`, and everything under them | before working in a module, or adding a route |
| `PACKAGING.md` | the spec, the three release scripts, signing, notarisation, and what a frozen build reads as a file | before touching `packaging/` or `runtime.py` |
| `GROUND-TRUTH.md` | the corpora, what each is for, the figure each reproduces, and the two probes that are not tests | before quoting a figure, retaking one, or rebuilding the pair |
| `LANGUAGES.md` | what it actually costs to teach this tool a new language | before writing a reader |
| `PERFORMANCE.md` | every measured figure, with its budget and its conditions | before quoting or retaking a number |
| `BRIEFING.md` | state: what is built, what is next, what is closed | at the start of a session |
| `BACKLOG.md` | what this tree owes, each with where it came from and what would settle it | when choosing what to do next |
| `HANDOFF.md` | the full chronological record, session by session | when you need why something is the way it is |

A rule is cited as a bare number — "rule 45", "design rule 19" — from code comments, tests
and both records; **3,326** such citations across `src/` and `tests/` as of 2026-09-15 —
2,489 to the engineering rules and 837 to the design ones, over 129 files. `RULES.md` carries
the command that counts them, because the first retake gave two different answers in two
shells — and the *second* retake, recorded the same day, did not reproduce against its own
commit either: it was taken partway through a session and the session kept writing. A figure
has to be taken last. **The numbers are
addresses. Never reuse one, never renumber, never close a gap.**

## House spelling — British in prose, and an identifier is an address

**Prose is British English.** Measured before it was decided rather than asserted: across
every `.md` in this repository, outside fenced blocks and inline code, the split was
**381 `-ise` to 35 `-ize`** — `analyse`, `colour`, `behaviour`, `normalise`,
`canonicalise`. The 35 were drift, quotations, or identifiers, and the convention was
already the one the project had been writing in for a year. Tom's own inclination is
American and he has said so; this is his delegation of the choice, not a claim about which
is correct.

**Three kinds of word, and only the first one moves.**

| | |
|---|---|
| **Prose** — comments, docstrings, documents, and **the strings a reader sees on screen** | British. A UI label is prose: the reader reads it, nobody imports it. |
| **Identifiers** — `dunneflow analyze`, `analyze.js`, `Analyze.OPTION`, `analyze_tree`, a CSS `color:` | **Never touched.** They are addresses, like the rule numbers: something types them, imports them or matches them, and a spelling change is a rename with no warning. |
| **Quotations** — Tom's words in `HANDOFF.md`, a sentence read out of somebody else's document, a library's own name | **Never touched, in either direction.** Evidence is quoted as written or it is not evidence. |

**The dated record is not rewritten.** `HANDOFF.md` says what was built and what it was
called at the time; `BRIEFING.md`'s "before that" entries are the same. Correcting a
spelling there would be editing the record to agree with the present, which is the one
thing a record may not do. Live surfaces — the product, the user guide, this file — are
brought into line instead.

*What this rule was minted from:* the program selector's last option read
**+ Analyze a directory…** and the dialog it opened was titled **Analyse a directory** —
two spellings of one control, a second apart, in the gesture that is the only way a
first-time reader gets a map at all. Rule 71's shape in the reader's language.

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
uv run dunneflow render   <dir> [--revision <rev>]  # a snapshot's map, from the graph it has
uv run dunneflow serve    [dir] [--revision <rev>]  # the dashboard; a program, a root, or neither
uv run dunneflow mcp      [dir] [--revision <rev>]  # the same map, answered to an agent over MCP
uv run dunneflow analyze  <path> --standards <dir>  # measure it against somebody else's rules
```

`analyze --progress-json` reports one JSON object per line on stdout instead of the summary,
which is how `serve` runs it. See **The surfaces** in `ARCHITECTURE.md`.

### What each command actually does — `ARCHITECTURE.md`

`serve`'s three ways of being started and the start page, `mcp`'s twelve tools and its three
modules, `query`'s two gates and the residue they leave, the analyse dialog and its stop
button, `migrate`, `render`, the diagram's two levels and the two ALGORITHMS surfaces: all
of it is in `ARCHITECTURE.md`, under **The surfaces**, with the module list underneath it.

### The frozen application — `PACKAGING.md`

Three platforms and one spec, `DUNNEFLOW_ARCH`, the universal2 interpreter, signing,
notarisation, the Dock presence, and the four questions `runtime.py` is the only place to
answer. Read it before touching `packaging/` or `runtime.py`.

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

**All three run on Windows and on Linux as well, and the suite is expected to be green on
all three.** Two tests skip off their own platform, by name; everything else that is
platform-shaped is tested by monkeypatching `sys.platform` rather than by skipping.

Four more gates are **conditional on what moved**, and each one exists because something got
through without it. `GROUND-TRUTH.md` carries what each is measured against and the figure
it must reproduce:

| When this moved | Run | Why |
|---|---|---|
| anything under a `sys.platform` branch | `uv run mypy . --platform darwin\|linux\|win32` | it is the only gate that can check the branches this machine cannot execute |
| `runtime.py`, `packaging/`, `detectors/`, `extractors/` | the frozen build, **and `tools/fingerprints.py` through it** | the tests prove the source tree, not the artifact — and two builds that cannot read each other's maps is rule 12 unenforced |
| `render/`, `resolve/` | `tools/ordering.py`, and `--api` for `web/` | the map may not depend on the order its rows happen to be in (rules 66 and 105) |
| anything at all, before it is called done | the real-code ground truth in `GROUND-TRUTH.md` | unit tests on a toy program cannot catch a resolution defect that only appears at scale |

**The four Society clones are read-only and only two of them are the pair.** Naming the
wrong one cost a whole analysis once and the result looked perfectly healthy —
`GROUND-TRUTH.md` says which is which, and never restate a figure measured on another
machine as though it had been reproduced (rule 24).

### Performance budgets — `PERFORMANCE.md`

Every measured figure lives there: analysis, the interactive map, the dashboard's panes,
the change worklist, search, and the documentation scan, each with the budget it was taken
against. **A cold row is the external volume and nothing else**, and a row states its
conditions where they are load-bearing — retaking one without reproducing those is a
different measurement under the same label (rule 24).

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
 83. An instrument's two coordinate systems can differ, and the one you can see is not
     the one you touch.
 84. A grid does not overflow, it grows a row.
 85. A span cannot tell what a loop is over from what it does.
 86. A guard can only see that a function was called, never what it returned.
 87. A derivation from the picture is only as available as the picture.
 88. A rebuild recipe must name every store the change invalidates, including the ones
     nothing else mentions.
 89. A refusal must name a command that can act on the thing it is refusing, and the
     sentence has to be readable off whatever decides that.
 90. An instrument's pointer lands on the window in front, not on the tab you addressed —
     and every other instruction still reaches the right one.
 91. A sentence written for a reader has to fit the channel it is put in, and a channel
     that is narrower than prose will not say so.
 92. A defence assembled from where this run writes does not survive the run being done
     from somewhere else.
 93. A stored path's separator belongs to the machine that wrote it, and that makes it a
     bad key.
 94. A boolean that says "the other one" stops being true when there are three.
 95. A cache key assembled from a directory does not cover what that directory imports.
 96. A record minted on demand exists because somebody asked, so a new question invents
     records.
 97. A bundled program does not carry the files it reads, and it answers anyway.
 98. A detector's population is whatever the map holds, so admitting a new kind of fact
     re-runs every detector against something it has never seen.
 99. A name is relative to the root that declared it, and a nested manifest's root is
     not the analysed tree's.
100. A judge that must pick one of several true answers picks by the order it was written
     in, and that order is the first language's preference.
101. A route is not a branch, and a probe that asks one query string per route says
     nothing about the others.
102. A list with no order comes back rearranged; a *sentence* about that order comes back
     wrong.
103. A path is not a key until it is canonical, and a set cannot deduplicate what does not
     compare equal.
104. A slot claimed before the thing that holds it exists is free for as long as it takes
     to create that thing.
105. An order taken over a set is the hash seed's, and a row-reversal probe cannot see it.
106. An identity assembled from names alone is only unique inside one language's
     naming.
107. A burst must end, and a transaction is not a bound.
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

**A severity is a claim about a language, so the language declares it.** `unawaited_async`
in each reader's own rules file says what it costs to start an async call and drop the
result: Python's coroutine is `inert` — never awaited, it never runs, which is BROKEN's own
definition — and a JavaScript promise `runs`, so what is lost is the ordering and, without
a `.catch`, the failure. `ASYNC_NOT_AWAITED` said *"The coroutine is created and never
run"* at BROKEN of **every** language until 2026-09-18, and produced two false BROKEN on
the first TypeScript tree it met: one on `new WebSocket(u)`, a **constructor**
`typescript.yaml` wrongly declared `async: true`, and one three lines under the comment
*"No await; this is fire-and-forget"* with a `.catch(() => {})` on the end. Rule 98.
`anomalies.py` reads the declaration off `files.lang` — per row, because a mixed map holds
both answers — and **names no language**, which the above-the-graph guard now asserts of it.
**Empty means the detector does not fire** and an unknown word is refused rather than
defaulted, because a severity nobody chose is worst in the one command a CI job trusts
(rule 49).

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
 30. A dimmed control still acts.
 31. A panel pinned to an edge grows away from it, so anything inside it that a program
     fills must be bounded.
```

## Adding a language — `LANGUAGES.md`

A reader is a plugin and never an import, and **nothing above the graph names a language**.
What that costs in practice — the six things to do, what a plugin gets for free and must not
reimplement, and the three things that will bite — is `LANGUAGES.md`. Read all of it before
writing a reader, and the third section twice.

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
