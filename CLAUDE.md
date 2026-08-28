# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. Built for a reader who reads code but does not write it, and who thinks in
entrypoints, flows, routines, and boundaries.

**New here? Read `BRIEFING.md` first** — where the code lives, what is built, what we are
doing now, and which decisions are closed. This file is the rules; `HANDOFF.md` is the
chronological record.

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

The interactive map (`dunneflow serve`), measured on Mensores: 52 disks, largest 959,
**9,874 nodes drawn**, 13,935 edges in the model, plus 5,727 shadows that are *never*
drawn — they are placement devices only (rule 23). An earlier version of this table read
"14,991 drawn" by counting the shadows; that number was already wrong when shadows stopped
being drawn, and it overstated the picture by half.

| Measure | Budget | Measured 2026-08-27, Apple M1 / Chrome Metal |
|---|---|---|
| Payload build, server side | < 2 s | ~0.03 s |
| First paint in the browser | < 2 s | 0.1 s |
| Sustained fps, six-second orbit, dots | >= 55 median | **60 median, 60 worst — no frames dropped** |
| …spheres at full size (14×) | >= 55 median | **60 median, 60 worst — no frames dropped** |
| …spheres at 14× plus 4,253 edges | >= 55 median | **60 median, 60 worst — no frames dropped** |

The last two were taken 2026-08-27 in the second session, and the third one could not have
been taken before it: the orbit set the moving flag, which stripped the edges, so the
benchmark measured nodes only while printing an edge count beside the number (rule 24).
The edge run is eight plates selected — `disceptator`, `STDIO`, `quaestor`, `_internal`,
`storage`, `cli`, `governance`, `DATABASE` — giving 2,199 within-plate links and 2,054
crossings, with both layers confirmed present in the frame.

The sphere threshold (2.2×) was set by judgment and is now set by evidence: full size costs
nothing measurable, so the ceiling is a look rather than a budget.

60 is the vsync ceiling, so these rows state a floor, not a capacity: nothing was dropped
and the headroom above it is unmeasured. Read it as "never missed a frame", never as a
score. The benchmark says so in the readout for the same reason.

The frame rate is bought by two decisions and both are load-bearing. Everything drawn is
uploaded once as flat typed arrays — with per-object accessors, fifteen thousand nodes
means fifteen thousand function calls per attribute per update, and the budget is gone
before anything is drawn. And the `data` wrappers are built once rather than inside the
per-frame layer function, which would re-upload half a megabyte on every frame of a drag
and reintroduce the exact cost the typed arrays exist to avoid.

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

15. **A branch that consumes lines must offer them to every detector that wants them.**
    Building the traceability join surfaced the same defect three times in one file.
    The scanner skipped heading lines, `_table()` consumed table rows, and
    `_rule_unit()` swallowed the continuation lines of a wrapped bullet -- each one
    mining what *it* wanted and passing nothing on. So governance ids stated in a
    heading, in a roadmap table, or on the second line of a bullet were invisible:
    `ADR-0057` is named in `.groma/ROADMAP.md` and `Plan 44-01` in `ADR-0045`, and both
    were reported as work built without a plan. Fixing all three moved 30 ids out of
    that band and lifted code-to-docs traceability from 89% to 93%. Rule 9 says
    documentation is never code; this is its converse -- **prose is prose wherever it
    sits**, and a consuming branch is the easiest place in a parser to lose it.

16. **Never open a database as the wrong kind.** Pointing `--db` at `docs.db` opened it
    as a graph, failed the staleness check, and dropped every table in it — a
    destructive fallback wearing the costume of a version upgrade. Both stores now stamp
    their kind and refuse the other, before anything is allowed to drop anything.

17. **A program names its files, and those names are vocabulary.** `tabularium` is
    glossed in Mensores' pantheon and appeared in the glossary nowhere, which read as a
    word the project had abandoned. It is the name of the database the whole program
    writes to -- 52 references across 25 files. It was invisible because the path is
    assembled, `root / ".mensores" / "tabularium.db"`, so only the parts are literals:
    not a module, not a table, not a boundary target. 155 such names on Mensores and
    DunneFlow recorded none of them. `schema.Artefact` now does, admitted only by an
    extension listed in `detectors/*.yaml` -- rule 5 again, because a trailing dotted
    part is not an extension and without the list `1.2.3`, `utf-8` and `mensores.cli`
    all read as named files. `.org` was removed from that list on evidence: the only
    thing it ever matched was `host="freetsa.org"`.

18. **Every comment must land on something, and the module scope owns what no function
    does.** Comments were collected per function -- the block above a definition and
    everything inside its span -- so everything else fell on the floor: **9,659 of
    Mensores' 18,208 comments, 53%.** Whole files lost every comment they had. The
    synthetic `<module>` routine already owned module-level boundaries, calls and SQL;
    it was simply never handed any comments. A class body counts as module scope for
    the same reason it already does for every other fact type -- it runs at import.

    The cost was governance, not readability. Those comments carried 2,270 annotations
    across 438 ids, 76 of which the graph had never seen. Closing it took ids cited in
    code from 517 to 593, moved 47 plans out of *likely landed* into *traced*, and
    surfaced a marker kind (`DECISION`) that had never appeared at all. **Assert the
    total, not the cases**: the test counts comment tokens and demands none go
    unclaimed, because the defect was a whole category nobody had thought to name.

    Found the same way as rule 15 and for the same reason: a step that consumes what it
    wants and passes nothing on. Verifying it turned up rule 5 once more in
    `walk.is_test_path`, which matched `test_` as a *substring* -- so `_test_stage.py`,
    the real Test stage of the Groma pipeline, was dropped from the map entirely along
    with two others. A marker must sit at an edge of the name. A module about testing
    is not a test.

19. **A constant is a name, and a `Literal` alias is an enum.** Module level produced no
    facts at all: `visit_Assign` caught only CLI app objects and `_class_fields` caught
    only class bodies, so `JTBD_OPENERS` was declared, read six times, and absent from
    the map. 2,618 constants on Mensores carrying its configuration -- model names,
    token ceilings, directory names, the actual system prompts it sends -- and 1,030 of
    them carry a comment saying why. Module level means **runs at import**, taken from
    position rather than from a scope stack, which is the same boundary the module scope
    already uses for comments and boundaries.

    Among them hid 86 type aliases. `QueueState = Literal["pending", "adjudicating",
    "emitted", "rejected", "skipped"]` is an enumerated vocabulary declared without the
    word `enum`, and `StructureKind.TYPE_ALIAS` had existed in the schema from the start
    with nothing ever producing one. The admission rule is a constructor list in
    `detectors/*.yaml`, exactly as the artefact extension list is: `X = SOME_DICT["key"]`
    is also a Subscript. A bare `X = Y` is **not** admitted -- it cannot be told from
    `DEFAULT = OTHER_DEFAULT` without resolving `Y`, and rule 1 says precision first.

20. **A read may refuse, but it may never repair.** `Store.__init__` discarded a stale
    graph on *every* open. For `analyze` that is right -- it re-extracts in the same
    breath, and rule 12 says a graph answering the previous version of the tool is the
    one outcome this tool may not produce. But `touches`, `impact`, `query`, `glossary`,
    `naming` and `mirror` open the very same class, so upgrading DunneFlow and then
    asking it a question dropped every table and answered out of the hole. `(no rows)`
    is indistinguishable from a true empty result, so the failure was **silent, and it
    consumed the evidence on its way past**. A reader now refuses and names the fix;
    only `analyze` is allowed to drop anything.

    Two general points, both already stated elsewhere in a different costume. Rule 16
    was the same shape -- a destructive fallback wearing the uniform of a version
    upgrade -- and the lesson did not transfer because it was filed under *wrong kind*
    rather than under *destructive on a read path*. And the reasoning that licensed it
    ("derived data, rebuildable in seconds") was true of the caller it was written for
    and false of every other caller of the same constructor. **A justification that
    depends on the caller belongs at the call site, not in the constructor**; the
    decision (`_is_stale`) is now separate from the act of dropping.

    Found by dogfooding, which is the only reason it was found at all: no test covered
    a read against a stale store, because nobody thought of a reader as something that
    could destroy.

22. **A node is a billboard, not a disc.** A circle drawn in the plane of its own disk
    foreshortens into an ellipse the moment the stack is tilted, and an ellipse does not
    read as a ball -- it reads as a coin seen edge-on. A sphere has no orientation, so a
    picture of one must not either: the quad is held facing the camera, always. Invisible
    at dot sizes; the whole illusion the moment nodes are big enough to look at.

    Real geometry is not the answer. Instanced meshes and a lighting pass would cost
    fifteen thousand draws for a difference nobody can see, against a frame budget
    measured on a single instanced draw of flat circles. The sphere is a few lines of
    shader reconstructing a normal from the disc's own uv -- same layer, same call, same
    buffers. Depth writing stays **off**: two billboards at slightly different depths
    intersect along a straight line, which renders as a clean slice taken out of a ball.

    The shading silently did nothing at first, because the inject hook was named
    `fragmentColor:DECKGL_FILTER_COLOR` instead of `fs:DECKGL_FILTER_COLOR`. An
    unrecognised hook is not an error -- the shader compiles, the layer draws, the effect
    never happens. That is the same silent no-op as a string replacement that matches
    nothing, in a shader's clothing, and only looking closely at one node found it.

23. **A shadow is never drawn, and never an endpoint. The crossings are the point.**
    A shadow is a *placement device*: a proxy standing in on a plate so that plate's
    layout feels the pull of something living elsewhere. Drawing one puts a copy of a
    routine somewhere it is not, which is a lie about where code lives; ending an edge at
    one stops a real connection at a stand-in.

    The model stores every crossing twice, once per plate, each copy ending in a shadow --
    which is exactly what lets both plates lay out under the same forces. For drawing,
    those two halves are resolved back to their real ends and kept once. What comes out is
    the connection worth the screen: **this routine, on that plate, reaching that one over
    there**, drawn as a single line spanning Z. Within-plate links say what a package does
    among itself; crossings say how the program hangs together, and the two are counted
    separately because they answer different questions.

    A crossing is drawn when *both* ends are selected, so picking two plates shows exactly
    what passes between them. Its colour walks from the source plate's colour to the
    target's along its length, because a crossing passes visually through plates it has
    nothing to do with, and one flat colour there cannot be read -- the gradient says
    which end you are looking at without tracing the line back. Every disk therefore gets
    a distinct default colour, walked by the golden angle: a feature that only works once
    the reader has hand-coloured fifty-two plates is a feature nobody reaches.

    This was missing for a whole session and the stack looked fine without it, which is
    the warning. Plates full of dots are a plausible picture of nothing much.

24. **A measurement must measure the thing it names.** The orbit benchmark drove the
    camera every frame, which set the moving flag, which stripped the edges -- so it
    measured nodes only, while the readout printed `· 4,963 edges` beside the number
    because a selection existed. A claim about geometry that was never drawn. This is
    rule 13 in a renderer's clothing: the query must return what is printed beside it,
    and a benchmark's "query" is the frame it actually submitted. The override is scoped
    to the two link layers so the run isolates edge cost rather than also pulling in the
    collision-filtered labels -- measuring more than you name is the same defect
    inverted.

25. **The one store that is not derived must never be discarded.** Rule 12 says a cached
    fact is valid only if the source and the tool that read it are unchanged, so every
    store here is dropped when the extractor fingerprint moves. `source.db` is the
    exception and the reasoning inverts cleanly: it holds the file bodies themselves, no
    rule was applied to them, so no rule change can make them wrong. Dropping it would
    throw away the one artefact that cannot be rebuilt once the source tree has moved
    on -- which is precisely what the temporal layers exist to hold. It carries no
    staleness check at all, and a test asserts the module contains no `DROP TABLE`,
    because the defect this guards against is a future edit rather than a present bug.
    Rule 20 said a read may refuse but never repair; this says a *store* may be refused
    but never repaired away.

26. **External is not inferred.** Every call that did not resolve to a local routine is
    stored `INFERRED` -- 23,829 of Mensores' 30,209. But design rule 5 spends the dashed
    edge on *we are not sure this call exists*, and that is not the claim: we are certain
    the call happens and simply cannot see the other end. Drawing the two the same way
    blurs exactly what rule 6 says never to blur, so an external carries its own mark and
    no confidence shape at all. Found by noticing that a routine's inspector showed 22
    inferred calls and 22 external ones, and that the numbers were equal for a reason.

27. **A marker counts only where it touches.** `#:` is Sphinx's doc-comment marker and
    its colon is syntax; `# :mod:\`x\`` is an ordinary comment whose text legitimately
    begins with a reStructuredText role. Stripping only `#` left 1,698 comments reading
    `": Keychain service name"` and 323 constants carrying their WHY through a stray
    colon, while stripping any leading colon would have eaten the role -- the same
    shortening-at-ingest as the tag-stripper that ate `<role>`. The test is position, not
    presence, which is rule 5 stated once more: a marker must sit at an edge. Fixing it
    moved 1,698 to 62, and the 62 that remain are exactly the roles.

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
    graph and says so. **The reader is in that key too**, and for a while it was not:
    the rules were hashed and the extractor applying them was not, so artefacts, the
    comment fix and constants each changed what extraction *meant* while every cached
    file stayed byte-identical -- saved each time only by someone remembering to bump
    `SCHEMA_VERSION` by hand, which is precisely the half of the rule a hand forgets.
    `code_extraction_inputs()` and `doc_extraction_inputs()` name the files, per corpus,
    and a test asserts membership rather than re-deriving the list.

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

18. **The stack is an abstraction, not an object — so do not draw it.** The 2.5D model
    is a stack of disks, and the disks are the *idea* that groups nodes by height. Drawing
    the plates draws the scaffolding as though it were the content, and at fifteen
    thousand nodes it reads as a solid cylinder. Nodes are tiny dots — 1.4 to 3.6 pixels,
    degree moving the size across two pixels rather than twenty, because any radius that
    reads as a disc fuses the whole thing into a mass. Plates exist as a toggle, off.

19. **Edges are shown on demand, never by default.** All 13,277 at once do not describe a
    program, they erase it: everything else goes under a haze. Nothing but nodes is drawn
    until a disk or a node is selected, then only the edges the selection touches, and
    only once the camera has stopped. Selecting a node takes **one** hop — two hops is
    most of the program again. Unselected nodes dim rather than vanish, so a subset stays
    legible inside the shape it belongs to.

    The consequence is that **the filter is the interface**, not a refinement of it. The
    legend is therefore the main way in, and is built for it: fifty-one disks, clickable,
    three columns interleaved a fraction of a row apart so rows nest instead of sharing
    baselines — the whole index in a third of the height one column needs. It is HTML,
    not text in the scene, because a legend that spins away with the camera is not a
    legend.

20. **Frame the bounding cylinder at the tilt in force, and always offer a way back.** A
    bounding sphere is rotation-invariant and therefore safe at every angle by being
    wrong at nearly all of them — it reserves room for the worst case, so the subject
    sits small however it is turned. The stack is a cylinder and orbiting about Z leaves
    its footprint circular, so tilt is the only term that changes the silhouette and a
    snug fit is two terms. Projection is **orthographic**: under perspective the near
    plates magnify and the far ones shrink, rendering a stack of equal disks as a tapered
    cylinder — the exact shape the model exists not to be — and orthographic zoom maps
    world units to pixels exactly, so framing is arithmetic rather than a fudge that
    holds at one window size. A snap-to-fit control is not a convenience: nothing may
    strand the reader off-screen with no way back.

21. **A blank canvas must say why it is blank.** Hardware acceleration switched off in
    the browser gives no WebGL context, and the symptom is an empty page that looks
    exactly like a broken program. The failure names itself, gives the remedy, and keeps
    the raw driver string underneath as evidence. Diagnostics live *on the page* —
    canvas size, device pixel ratio, GL renderer, and where the geometry projects in
    screen space — because "drawn off-screen" and "not drawn" are indistinguishable by
    looking, and a developer cannot run a console in someone else's browser. A test
    pattern of three markers at known positions splits the question in two: if they draw
    and the graph does not, the fault is our geometry; if neither draws, nothing is
    reaching the screen at all.

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
