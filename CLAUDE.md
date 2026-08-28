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
| …spheres at full size (14×) | >= 55 median | **60 median, 59.7 worst — retaken 2026-08-28** |
| …spheres at 14× plus 4,253 edges | >= 55 median | **60 median, 59.9 worst — retaken 2026-08-28** |

**The two sphere rows were withdrawn and are now retaken, with the shading confirmed
running by eye before either was recorded.** They had been withdrawn rather than left
stale because the sphere shading was not executing when they were first taken: three
separate silent no-ops kept the fragment work from ever happening — an inject hook deck.gl
did not recognise, a GLSL local colliding with one of its own, and a shader that was never
reassembled because deck.gl resolves an extension's shader once per extension class. Every
one of them compiles and draws. Those runs measured flat discs while the readout printed
the word *spheres*, which is rule 24 exactly.

**Both retaken rows state their canvas and their framing, because the first pair did not
and that is what made them impossible to reproduce.** Canvas **2652×1537 device pixels**
(1326×768 CSS at dpr 2), framed with **snap to fit** at the tilt in force. Both matter and
neither is incidental: sphere shading is per-fragment work, so the same 14× nodes in a
1072×251 pane and in a full window are not the same measurement, and a stack that sits
small in the frame covers few fragments however large the canvas is. An early attempt this
session ran at 4.08M canvas pixels with the stack occupying a fraction of them — a bigger
number measuring the same little picture. Retaking without reproducing both is a different
measurement under the same label, exactly as with the plate selection below.

Read with the caveat that at 14× the nodes fuse into a solid mass and occlude the edges
they are drawn with: the frame is honest about cost and is not a picture anyone would read.
That is the case for independent X and Y spread, not against the measurement.

The dots row stands: nothing about it depended on the shading.

Kept because the *method* survives even though the numbers did not. The edge run could not
have been taken at all before the second session: the orbit set the moving flag, which
stripped the edges, so the benchmark measured nodes only while printing an edge count beside
the number (rule 24). Its selection is eight plates — `disceptator`, `STDIO`, `quaestor`,
`_internal`, `storage`, `cli`, `governance`, `DATABASE` — giving 2,199 within-plate links
and 2,054 crossings, with both layers confirmed present in the frame. Reproduce that
selection when retaking the row, or it is a different measurement wearing the same label.

A benchmark now refuses to start on a tab that is not visible. A hidden tab is given **no**
animation frames at all — not throttled, none — so a run started before switching away sits
at "benchmarking…" and then reports a figure averaged over the time nobody was looking.

The sphere threshold (2.2×) is **a judgment, and stays one.** It was briefly recorded as
set by evidence; that claim was withdrawn with the rows it rested on, because the evidence
was a run in which the shading did not execute and so showed only that flat discs are
cheap, which was never in doubt. The rows above are now retaken with the shading confirmed
running — and they still do not set the threshold. They say the shading is affordable at
full size in this framing, which is a different claim: where a *reader* wants a disc to
become a ball is a question about looking, not about cost. Setting it by evidence would
take a measurement of the fused-mass problem, and that measurement does not exist.

60 is the vsync ceiling, so these rows state a floor, not a capacity: nothing was dropped
and the headroom above it is unmeasured. Read it as "never missed a frame", never as a
score. The benchmark says so in the readout for the same reason.

The frame rate is bought by two decisions and both are load-bearing. Everything drawn is
uploaded once as flat typed arrays — with per-object accessors, fifteen thousand nodes
means fifteen thousand function calls per attribute per update, and the budget is gone
before anything is drawn. And the `data` wrappers are built once rather than inside the
per-frame layer function, which would re-upload half a megabyte on every frame of a drag
and reintroduce the exact cost the typed arrays exist to avoid.

Opening the dashboard (`dunneflow serve`) on an analysed program, 10.2 s to first serve,
of which the two vocabulary lanes are 2.5 s:

| Measure | Budget | Measured 2026-08-28 |
|---|---|---|
| `serve` start to first request | < 15 s | 10.2 s |
| …of which the naming pass | | 0.4 s |
| …of which the glossary pass | | 2.1 s |

The two lanes' **bodies** are fetched when their page is opened — 44 KB and 190 KB — while
their sizes ride with the cover, because the navigator states a count beside every other row
and a blank there reads as *nothing here*. Measured on the glossary, 1,207 words with 60
defined and 1,147 not:

| Measure | Budget | Measured 2026-08-28 |
|---|---|---|
| Full page render | < 100 ms | 51 ms |
| One keystroke in the term filter | < 30 ms | 9 ms |

The filter was **412 ms** per keystroke until it stopped calling `render()`, which rewrites
the centre pane, the inspector, the navigator and the trail and then puts the caret back in
the field it has just destroyed. The caret restoration was the tell.

Both lanes are paid for **at start rather than on first use**, and that is a decision
rather than an accident. A vocabulary thread is part of `/api/threads`, which is asked on
every selection, so a lazy first call would stall the reading loop on the first click of
every session — two seconds where the reader is entitled to think the click failed. Paid at
boot it is invisible, beside a payload build and a cover that were already being computed.

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
- `web/threads.py` — **adjacency by interest, not by edge.** Why a neighbour is worth a
  detour: shares a plan, the other end of a table you write, the most commented routine on
  your plate, named like ninety-eight others. Every thread carries a *subject* the router
  can act on, never a label (rule 30), and states its size so the reader can weigh it.
- `web/vocabulary.py` — the two naming lanes served, and matched against one name. The
  membership test is `Convention.glob`, which is the same string the exceptions query is
  built from, so the claim and the population cannot drift (rule 41).
- `sql.py` — reads schemas out of the `CREATE TABLE` statements the code contains.

## Rules learned the hard way

These each came from a false result on real code. Keep them.

*There is no engineering rule 21, and nothing is missing.* The numbers are cited from code
comments, tests and `HANDOFF.md`, so they are addresses rather than an ordering and are
never reused or closed up. Every "design rule 21" in the codebase refers to the dashboard
rule of that number — a blank canvas must say why it is blank — which does exist.

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

28. **A `rem` inside `@media` is not the page's `rem`.** Design rule 3 puts every
    dimension in rem so one multiplier resizes the surface together, and that is worth
    keeping — it works, and it is why the whole shell scales from one slider. But a
    breakpoint is not a dimension; it is a question about the *window*. By spec a relative
    unit in a media query resolves against the **browser's** default font size and ignores
    `:root`, which this stylesheet pins to 16px and which the scale slider drives. On a
    reader whose Chrome default is 24px, moving the slider took the navigator from 192px
    to 288px and moved the breakpoints not one pixel, while `68rem` silently meant 1632px
    instead of 1088px — so a 1454px window got the narrow layout. Five media queries were
    written this way. They are px now, at the widths the rem values were meant to express,
    and everything else stays rem. A unit that looks like a member of the scaling family
    and is not one is worse than an obvious exception.

29. **A media query contributes no specificity, so equal selectors go to source order.**
    `.inspector { display: none }` inside the narrow block lost to `.inspector { display:
    flex }` declared 350 lines later, so the narrow layout never hid what it said it hid:
    the pane rendered into a grid declaring two columns, wrapped onto row 2, and put
    "Nothing selected" at the bottom left with an empty strip beside it — while the app
    grew taller than the window and the whole document scrolled. **Fix it with specificity,
    not with order**, or the next component rule takes it back silently. This is the
    `[hidden]` defect exactly (rule: an author `display` beats a user-agent one), and the
    lesson did not transfer because it was filed under *user-agent rules* rather than under
    *a later `display` wins*.

    Its companion, found in the same layout: **a grid item defaults to `min-height: auto`
    and refuses to shrink below its content.** The navigator's 1,151px of content held the
    row open at 700px inside a 446px box. Every pane here scrolls inside itself, so that
    default hands the overflow to the document, which does not scroll panes, instead of to
    the pane, which does. `minmax(0, 1fr)` on the row and `min-height: 0` on the children.

30. **A label is not an identity.** The four navigator routes that set what you are looking
    AT — ways in, packages, boundaries, tables — were `() => { state.view = state.mode;
    ensureGraph(); }`. They switched mode and selected nothing, so **all forty rows did the
    same thing**, and the inspector went on truthfully reporting "Nothing selected" while
    every control worked. It never tripped the no-route check, because the route existed
    and simply had no subject; no identity had ever reached the DOM for it to act on. Design
    rule 16 one level below where the checks were looking, for the third time.

    The four are not one shape, and finding that out is what made the fix right rather than
    plausible: a package and a boundary kind are **plates** and select as themselves; a way
    in resolves to routines, and `ways_in()` had computed those roots all along while the
    cover threw them away; and a table is **neither** — `audit_events` is not a node at all,
    so selecting a table means selecting the code that reads and writes it. `queries.py`
    already said so in as many words — *inventing an id to make a row clickable would be a
    link to nothing* — which is the negative half of rule 17 and was written before anything
    needed it. Assert both directions: the item must emit an identity and the route must
    consume one, because either half alone passes while the feature is dead.

31. **A shadow is never an endpoint — when *reading* an edge as much as when drawing one.**
    Rule 23 says a shadow is a placement device, never drawn and never an end. `d.links`
    obeys it, resolving each stored edge back to its two real ends. `recomputeMembers` did
    not: it added `raw.edges.from/to` unresolved, so for a call that leaves the plate it put
    the **shadow** into the selection instead of the routine the shadow stands in for.

    Both halves then failed together and silently. The real neighbour was not a member, so
    it was never lit; and `buildSelectionGeometry` requires *both resolved ends* to be
    members, so the crossing was skipped — and crossings are exactly the edges that leave
    the plate. **Picking a routine drew its callers and callees only where they happened to
    sit on the same plate.** `console_script` has four callers and three callees and drew a
    single unconnected dot; `guarded_cwd` has eleven connections and drew seven. Nothing
    reported it, because a routine that genuinely has no neighbours looks identical.

    The lesson is not "resolve shadows" — rule 23 already said that, in as many words:
    *ending an edge at a stand-in stops a real connection at a stand-in*. It is that a rule
    about drawing was never applied to the code that **reads**, and the two are the same
    rule. Found by a reader saying a picture looked wrong, not by any check.

32. **A count must say what it counts.** The navigator listed `degree` — an edge count —
    beside each routine, in a pane where every other group's number counts *things*: 14 ways
    in, 8 packages, 52 disks. `guarded_cwd` printed **8**, drew **7** nodes, and had **3
    callers and 5 callees**. All three numbers were correct and no two of them agreed about
    what they were, so the reader reasonably read 8 as nodes and reported a missing one.

    Rule 13 in a list rather than in a claim: the number must be produced by, and named
    after, the thing it measures. It is `3← 5→` now, taken from the same `inbound`/`outbound`
    maps the selection itself uses, so the figure and the picture cannot disagree.

33. **A trail step must carry its subject, or the trail cannot take anyone back.** Steps were
    `{view, label, note}`; clicking one set `state.view` and re-rendered. From inside graph
    mode, where the view is *already* graph, that is a no-op — so the trail rendered,
    highlighted the current step, scrolled and pruned correctly, and could return nobody to
    anything. Rule 30 for the third time, and the most expensive place for it: design rule 15
    says the trail is what makes a detour free, because **nobody chases a rabbit if they
    might not find their way back**.

    Its companion, and the reason undo exists: two ordinary clicks strand a reader. Clicking
    the node you are already looking at clears the whole selection (a deliberate toggle-off
    in `togglePick`, and a trap when the click is *also* how you move), and every
    nothing-selected state looks identical, so nothing on screen says which routine you had.
    **The toggle is kept** — clearing by clicking is right, and `Esc` and the clear button do
    the same — because undo makes it recoverable, which is the cheaper fix and the better UI.

34. **Pinned data hides in prose, and that is the hiding place the guards missed.** Two
    guards kept the shell's top-level arrays empty and its `state` clean. Neither could see a
    *sentence*. Table mode's footer read "Showing **12** of **515** routines in
    `mensores.quaestor`"; the breadcrumb's three centre modes were fixed pairs — "packages ›
    system boundary", "quaestor › routines", "cli › interview" — shown on every screen for
    every program; document mode was a page of hand-written narrative about
    `mensores interview --extract`, formatted exactly as generated output with nothing
    marking it as a sample; the glossary asserted findings about specific `.groma` files; and
    a citation path called `.replace("mensores.", "mensores/")`, silently wrong elsewhere.

    Worst of them, and the one that says why this matters: **the egress consent surface**
    carried "4,568 routine names", "184,000 lines" and a manifest of "2,449" — one program's
    figures written into the one screen in the product where a wrong number is a consent the
    reader did not give (design rule 14).

    Guard on the *sample program's name*, not on numbers: a number in prose is often
    legitimate ("one hop", "three panes"), a specific program's name never is. And note what
    that still misses — the glossary named the program's **files** rather than the program.

35. **A `let X = []` that nothing assigns is an empty view with no symptom.** `ROUTINES` was
    declared, commented "for table mode", and written to by nothing, so table mode rendered
    zero rows for as long as it existed. It is the pinned-data family inverted: those guards
    assert the arrays are *empty*, which this passed perfectly by never being filled.

    The invariant is not "must be assigned" — an unbuilt feature legitimately has no data.
    It is **assigned, or the view says it is empty**, because "not computed yet" and "nothing
    to report" are opposite claims and a blank panel states the wrong one. Written as a list
    of exemptions first; that list reached five of ten arrays before it was obvious it would
    grow until the guard caught nothing. Finding the invariant is what made it a check rather
    than a ledger. It then found `CONVENTIONS`, `TERMS` and `MANIFEST` — and three variables
    read by nothing at all, which were deleted rather than exempted.

36. **A generic loop narrowed to a literal is how a feature disappears without a trace.**
    The pre-merge graph walked `Object.entries(panels)` and folded every panel. The rewrite
    wrote `[["navigator","nav"], ["inspector","insp"]]` — correct for the two it named, and
    it silently dropped `hud` and `controls`, which stayed defaulted, persisted, and listed
    in the reset dialog as "panel layout". Dead *inside a live key*, where the guard written
    for exactly this failure could not see them: it walks the top-level keys of `DEFAULTS`,
    and `panels` as a whole was plainly being read.

    Route from a table, walk the *settings* rather than a list of your own, and make an
    unknown key a named error. Then assert the two key sets agree, both derived. The same
    reasoning retires every hand-kept second list — `FOLDABLE` now derives from `PANELS`.

37. **A guard that checks a name appears has not checked that anything happens.** Three of
    this session's guards passed against their own defect on the first try. One split on
    `.graphlegend {` and read an *earlier* rule with the same selector, asserting against
    `display: none`. One accepted `step.subject` appearing anywhere, staying green while one
    of the two ways back was broken. One accepted the presence of `restoringSelection` while
    the line that consults it was gone.

    **Run every new guard against the defect it was written from, and against a version
    where only half the feature works.** A check that has never failed is a claim nobody has
    tested — the same argument as rule 13, applied to the tests themselves.

38. **An instrument that cannot see cannot report.** A browser-automation tab is given no
    animation frames, so `ResizeObserver` never fires and `requestAnimationFrame` never
    ticks. Measured through one, deck.gl's canvas appeared never to resize on a pane fold —
    a confident, reproducible, entirely false finding, and the fix for it was most of the
    way written before an observer attached by hand also failed to fire and gave it away.

    Static DOM facts survive a starved tab: layout runs without frames, so grid tracks,
    widths and classes are real. **Anything needing a rendered frame does not exist there.**
    Rule 24's family — a measurement must measure the thing it names — and the reason the
    benchmark already refuses to start on a hidden tab. When the instrument cannot prove it,
    describe the change and let someone with a real window look.

39. **Under an orthographic projection a negative `near` is geometrically sound and breaks
    the controls.** deck.gl's default frustum (`near 0.1, far 500`) clips the stack when the
    reader zooms in: `OrbitView` scales world units by `2 ** zoom / height` with the camera a
    fixed focal distance from the target, so the stack's *view-space* depth grows with zoom
    until its near half crosses the near plane. Nodes nearest the camera vanish and return on
    zooming out.

    An orthographic frustum is a box, not a pyramid, so a negative `near` looks like the
    obvious fix. **It kills pan and zoom outright** — deck.gl's orbit controller implements
    both through `viewport.unproject()`, while rotate is angle arithmetic that never
    unprojects, so exactly the two controls that unproject stop and the one that does not
    carries on. Losing pan and zoom is far worse than clipping at extreme zoom, so the
    default stands until there is a fix that keeps `near` positive — moving the camera back
    rather than the plane. Recorded because the diagnosis is right and the obvious remedy is
    not, and because it was shipped without being driven: **not being able to test a change
    is a reason to describe it, never a reason to ship it and ask.**

40. **Two detectors recording one act is two numbers about one thing.** The hover card
    read three tables *and* "DATABASE 20" — which is the same seventeen statements seen by
    the SQL reader and the boundary reader. Not an oddity of one routine: 991 of Mensores'
    1,316 DATABASE boundaries sit on a line with a `sql_ops` row, and **all twenty** NETWORK
    boundaries sit on a `net_calls` row. A summary that states the same act twice is rule 32
    in a smaller box — two correct numbers, neither of them saying what it counted.

    A boundary already named by a more specific record on the same line is not counted
    again. **Per line, not per routine**: 43 routines have a DATABASE boundary and no
    `sql_ops` at all — they open a connection and run nothing — and a coarser rule blanks
    their card. The one-line tolerance is a judgment and is written down as one; the
    detectors disagree by a line on multi-line statements, recording the call site and the
    statement start.

    Its companion, found in the same edit: **excluding the general record must not lose what
    only it recorded.** Ten of that routine's seventeen operations are `BEGIN` / `COMMIT` /
    `ROLLBACK` with no table of their own, and the first fix dropped them silently — the
    exact omission the anti-join was written to prevent, inverted. They have their own row,
    grouped by direction, because DDL is not transaction control.

41. **A prose claim and a machine-readable population are two things, and only one of them
    can be asked a question.** A measured naming convention carried `claim` (a sentence) and
    `sql` (which reproduces its *exceptions*). Neither can answer "is `witness_defer_cmd`
    one of these?" — which is what the inspector needs before it can say a routine shares a
    convention with ninety-eight others. Recovering the affix by parsing the sentence would
    be reading prose to get back something the code had already computed and thrown away.

    `Convention.glob` is that population, and it is **the same string the exceptions query
    is built from**, so the membership test and the evidence cannot drift. A test asserts
    the glob appears in the SQL — rule 13 applied to a second way of naming one set.
    Writing it exposed that `test_an_affix_glob_respects_the_separator` had **never run**:
    its fixture produces no affix convention at all, so its assertion sat behind
    `if predicates:` for as long as it had existed.

42. **A guard that names the right case may still not catch it.** `selectionOnScreen()`
    documents itself as returning null when there is no viewport — "we cannot say" and "it
    is off screen" being different answers — and guarded with
    `g.deckgl?.getViewports?.()`. deck.gl does not return a falsy viewport before it has
    one; it **asserts inside** `getViewports()`, so the optional chaining protected against
    a missing deck and not against the case the comment describes. The `?.` was what made
    the code look guarded.

    The path is ordinary: pick a routine in the navigator before opening the graph, and
    `selectFromNav` mounts the engine and calls `applyWanted()` synchronously, before any
    frame. The throw left `applyWanted`, so `persist()`, `recordSelection()` and `render()`
    never ran — the selection happened, undo did not record it, nothing repainted. Rule 37
    in the code rather than in the tests: **check that the guard catches, not that it
    mentions.**

43. **A check that cries wolf has already failed, and it fails silently.** The shell's
    runtime self-check printed "dead controls" on every page load and was wrong about every
    one of them: `insp`, `fold`, `navid`, `titled` and `legend` are real — grid track state
    the stylesheet reads, and parameters read off controls found by class — and had simply
    never joined `WIRED_ATTRS`. Its own comment says why that costs: *a check that cries
    wolf is a check nobody reads*, and a genuine dead control would have arrived as a sixth
    line in an error nobody had believed for weeks.

    `legend` is the one worth keeping. It is written on the graph mount, which does not
    exist until the reader opens the graph, so the check said four at boot and five
    afterwards — one page, two answers, neither of them the truth. **A check whose answer
    depends on when it runs needs a counterpart that does not run at all**, so the roster is
    now derived from the source, generated markup included; the existing guard reads
    `index.html`, and every one of these five is written by JavaScript.

44. **A live control reading a field the server does not send renders nothing and throws
    nothing.** The glossary and naming pages were the ratified prototype's, written against
    `{pattern, ok, n, exceptions: [str]}` while the server sends `{glob, holds, total,
    rating, exceptions: [{name, where}]}`. That is *worse* than an unported page: `cv.ok /
    cv.n` is `NaN`, the percentage bar renders at zero width beside a claim that is perfectly
    true, and nothing anywhere fails. Both pages were held back saying so, which was right,
    and neither existing guard had a name for the shape — a dead control renders and does
    nothing (rule 30), a dead setting is read by nothing (design rule 16), a dead variable is
    assigned by nothing (rule 35), and this one **works**, on data that is not there.

    The check reads the served key names out of the builder and the accessed names out of the
    view, and runs in one direction only. A view may leave a served field unread — the
    glossary sends `uses` and the page shows `used_as`, which is the same fact in the form a
    reader wants — but a view reading a field nothing sends is rendering a blank while looking
    finished. Its companion, found in the same edit and the same shape one layer down: a
    string the code composes is **prose the moment something prints it**, so `f"{noun}s"`
    stood as `classs ending in \`Error\`` for as long as no page displayed it.

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

    **And the same rule with no control at all: a setting nothing reads.** `panels` sat in
    `settings.js` from the first day -- persisted per program, versioned, and named in the
    reset dialog as "panel layout" -- while nothing anywhere read it, so a reset reported
    clearing a layout that had never existed. The pre-merge graph had collapsible panes and
    the merge kept the switch while dropping the implementation. A test now reads the keys
    out of `DEFAULTS` and demands each appear as a **property access** somewhere: every key
    is also a plain string in the list of things to persist, so searching for the bare name
    passes on a setting that is faithfully saved, restored, and never once acted upon --
    which is exactly the failure.

18. **The stack is an abstraction, not an object — so do not draw it.** The 2.5D model
    is a stack of disks, and the disks are the *idea* that groups nodes by height. Drawing
    the plates draws the scaffolding as though it were the content, and at fifteen
    thousand nodes it reads as a solid cylinder. Nodes are tiny dots — 1.4 to 3.6 pixels,
    degree moving the size across two pixels rather than twenty, because any radius that
    reads as a disc fuses the whole thing into a mass. Plates exist as a toggle, off.

19. **Edges are shown on demand, never by default.** All 13,277 at once do not describe a
    program, they erase it: everything else goes under a haze. Nothing but nodes is drawn
    until a disk or a node is selected, then only the edges the selection touches.
    Selecting a node takes **one** hop — two hops is most of the program again. Unselected
    nodes dim rather than vanish, so a subset stays legible inside the shape it belongs to.

    *"…and only once the camera has stopped" is struck, and is now a Setting defaulting to
    on.* That clause was a speed measure carried over from slower renderers, and it is not
    what this one needs: everything drawn is uploaded once as flat typed arrays, so a
    turning camera re-uploads nothing and the links cost the same moving as they do still.
    It also worked against the picture. **A rotation is how the connections between plates
    read as depth rather than as a flat tangle**, so stripping the edges during one hides
    precisely what the reader turned the view to see. Off is kept for a slower machine or a
    very large selection.

    The **on demand** half stands unchanged, and it is the half that carries the rule: what
    is drawn is still only what the selection touches.

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

22. **Spread is three axes, and the fourth control is zoom.** X and Y widen a plate, Z
    is the gap between plates, and they are independent because they answer different
    questions -- a plate too dense to read wants X and Y, a stack too tall to frame wants
    Z. Scaling all three by the same factor is *zoom*: under an orthographic projection
    uniform scaling and zoom are the same operation, so a "linked" slider would be a second
    way to do what the mouse wheel already does. Every scale is computed from an unscaled
    base copy of the payload's positions rather than applied in place -- 2x then 2x again
    is 4x, and a slider dragged back to 1 must come home.

    It is what makes large nodes usable at all. Billboarded spheres fuse into a solid mass
    once they are big enough to look at, and at 14x no amount of Z helps, because the
    crowding is *within* a plate. Widening is the answer, not shrinking the nodes.

23. **Hiding and collapsing are separate switches.** Hiding decides whether an unselected
    plate draws; collapsing decides whether it still takes up room. Wanting the second
    without the first is ordinary -- it is how eight plates out of fifty-two stop reading
    as eight plates scattered down a tower of empty slots. Merging them into one control
    makes "show me these eight, packed" unreachable.

    Two things follow. A collapsed plate is one *nothing is looking at*, so with no
    selection nothing collapses and the control quietly does nothing rather than emptying
    the stack -- the same reasoning as edges on demand. And which plates are unused is a
    function of the selection, so it is recomputed when the selection changes and not only
    when the control moves, or the stack keeps the shape of the previous selection while
    confidently showing the current one. The count is stated (rule 1): a shorter stack and
    a smaller program are indistinguishable by looking.

24. **A pane collapses to a rail, and the rail says which pane it is.** Three panes over
    one selection is the settled shape, but the inspector answers "what is this thing" and
    holds 22rem to say nothing when nothing is picked. So every pane folds, and folding
    leaves a rail behind: a pane that simply disappears is a silent filter, and the reader
    has no way to know the layout is a choice rather than the product. The label is rotated
    rather than reduced to an icon, because an icon rail is a puzzle.

    The grid **tracks** carry the state, not the panes -- collapsing a pane without
    collapsing its column leaves a hole exactly the width of the pane that is no longer
    there. The inspector rails itself while nothing is selected and returns when something
    is, but an explicit fold outranks that: auto may only ever *close*, or the reader's
    choice reopens underneath them. And opening the rail with nothing selected has to
    suspend the auto rule, or the pane reopens and instantly re-collapses, which reads as a
    broken button.

    Adding chrome to a pane broke something else, worth keeping: the Ways in / Explore
    reorder moved a group before `firstElementChild`, which swept it in front of the new
    fold button and put the collapse control a third of the way down the pane. **An
    ordering rule that names a position rather than an identity breaks the moment anything
    is added beside it.**

25. **The primary way in is a pane, not furniture.** The legend was 26rem of opaque surface
    pinned over the canvas it indexes — design rule 19 calls it the main way into the graph,
    and it was drawn as though it were decoration. It cost nothing in visible canvas to fix,
    because the pixels under it were never visible: what changes is that the pixels *beside*
    it are now honest, so snap-to-fit frames the stack in the space the stack actually has
    instead of centring it under the panel.

    That is the tell in general. `fitView` once carried `panels.disks ? 0.60 : 0.90` — a
    fudge factor kept in sync with a UI state by hand — and when the two applications merged
    the term was dropped while the panel stayed, so fit went on burying half the subject.
    **A framing correction for something floating over the picture means the thing floating
    should own a track.** With the legend as a grid column, `clientWidth` *is* the drawable
    width and the margin is plain arithmetic again, which is the same reason rule 20 chose
    orthographic over perspective.

    Two collapse idioms, because there are genuinely two shapes: a full-height side pane
    collapses its **track** and leaves a rotated rail (rule 24); an overlay box floating on
    the canvas collapses to a horizontal **ribbon** — its own header strip, still stating its
    summary, because a strip reading only "controls" is rule 24's icon rail lying down.

26. **The list and the picture are one instrument, and it has to run both ways.** Pick a
    routine on the left and the stack highlights it with everything that calls it and
    everything it calls; click a node in the stack and the list moves to it and marks it.
    Only one of those directions is a lookup. **Both of them is how a thread gets chased**,
    which design rule 15 says is what to build for, and either alone leaves the reader
    translating between two views by hand.

    Three things that are not optional once it runs both ways. The list must **not move the
    camera** — a list you can click through is useless if every click throws away where you
    were looking — so an off-screen selection is *stated* and framing it is one click away
    (rule 20's reasoning applied to selection rather than to the camera). The automatic
    scroll that follows the graph must not fight a deliberate click, so it only acts when
    the row is genuinely out of sight. And **plates are the missing answer**: rule 18 keeps
    all fifty-two undrawn, but the two or three a selection touches are the only thing on
    screen that can say *which plate am I looking at*, so they are drawn faintly and named
    on the HUD — the outlines say where, the names say what, and one without the other is
    half an answer.

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
