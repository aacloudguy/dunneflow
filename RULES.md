# DunneFlow — rules learned the hard way

The engineering rules, in full. `CLAUDE.md` carries the numbered index; this file carries
the evidence, and the evidence is the point — each rule is the shortest true statement of
a false result that real code produced, and the body says what produced it.

**Read a rule's body before working in the area it governs.** The title alone will let you
agree with a rule and still reimplement the defect it was written from: every one of these
was, at the time, the obvious thing to do.

Cited as bare numbers — "rule 45" — from code comments, tests and the development
record; **3,326** such citations across `src/` and `tests/`, 2,489 of them to these
rules and 837 to the design ones, over 129 files — retaken 2026-09-15 *after* the session
that last wrote it down, which had moved it by three while writing. That is the third time
this figure has failed to reproduce against its own commit, and the reason the command is
written down. The numbers are therefore
**addresses**, never an ordering, and are never reused or closed up.

*That figure was 768 and is retaken rather than carried.* It was measured on 2026-09-02 at
the split, when there were 102 rules, and sessions of code have been written since — an
old count restated as a live one is rule 24's defect in a sentence about rules.

**And the retake before this one did not reproduce either, which is the same defect one turn
later.** The figures written above on 2026-09-15 were 3,241 · 2,422 · 819 · 128; run against
that very commit they come back **3,297 · 2,463 · 834 · 128**. Nothing is wrong with the
command — it was taken partway through a session and more code was written after it, so what
was recorded was a true measurement of a tree that no longer existed by the time the sentence
holding it was committed. A figure has to be taken *last*, not merely reproduced twice.

**The method, because the first retake was wrong twice.** Counted as occurrences of `rule N`
or `rules N`, case-insensitive, **excluding `__pycache__`** — the first run through an
interactive shell returned 105 files and the same command through `bash` returned 204, the
difference being compiled bytecode that had been silently filtered by the shell rather than
by the query. A count that changes with the shell it is run in is not a measurement (rule
24), so the exclusion is stated and the figure was reproduced twice before being written:

```bash
grep -rhoiE "\brules? [0-9]+"        --exclude-dir=__pycache__ src tests | wc -l   # 3,326
grep -rhoiE "\bdesign rules? [0-9]+" --exclude-dir=__pycache__ src tests | wc -l   #   837
grep -rliE "\brules? [0-9]+"         --exclude-dir=__pycache__ src tests | wc -l   #   129
```


These each came from a false result on real code. Keep them.

*There is no engineering rule 21, and nothing is missing.* The numbers are cited from code
comments, tests and the development record, so they are addresses rather than an ordering and are
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

39. **A plausible diagnosis of a real symptom is still a guess, and this one named the
    wrong plane for two sessions.** Zooming all the way in lost a quarter of the stack. The
    explanation on file was the **near** plane — `OrbitView` scales world units by
    `2 ** zoom` about a target the camera sits a fixed distance from, so the stack's near
    half was said to cross `near 0.1`. It reasons well and it is wrong.

    Measured, by projecting every drawn node through deck's own view-projection and counting
    the ones whose clip-space z leaves `[-1, 1]`: **nothing clips anywhere in the range
    except at `maxZoom` exactly, where 4,063 of 15,869 go past +1** — the **far** plane, at
    deck's default of 500. The near plane is never reached at any zoom this view allows. A
    cliff at the top of the range rather than a gradual onset, which is exactly how a reader
    reported it: *"when I zoom in, the clipping cuts in"*.

    So `far` is raised to 5,000 and `near` is untouched. It costs nothing, and both things
    that could have made it cost something were measured: the on-screen scale is identical to
    the pixel (24,574.8 px per 100 world units at `maxZoom` either way), and `unproject`
    round-trips to zero error. 5,000 rather than more, because it clears `maxZoom` with the
    furthest node at clip-space −0.43, while 50,000 puts the whole stack past −0.94 and
    spends depth precision on nothing.

    **The warning that produced this rule stands, and is why the fix took two sessions to
    find.** An orthographic frustum is a box, not a pyramid, so a negative `near` is
    geometrically meaningful and looks like the obvious fix. **It kills pan and zoom
    outright** — deck.gl's orbit controller implements both through `viewport.unproject()`,
    while rotate is angle arithmetic that never unprojects, so exactly the two controls that
    unproject stop and the one that does not carries on. A guard now refuses a negative
    `near`, because the geometrically obvious wrong answer is the one a reader reaches for.

    Two general points. **A symptom explained but never measured is an open question wearing
    an answer** — this one was closed with a count rather than an argument, and the count
    took one pass over 15,869 nodes and no rendered frame at all. And it stayed open because
    it was filed as *tolerable at extreme zoom*: it stopped being tolerable the moment a
    feature told the reader to zoom in for more, so **a defect's severity is a property of
    what has been built since**, not of when it was found.

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

45. **Hidden is not absent, and the difference is the whole bill.** The routine list
    grouped 4,734 routines into 47 packages and built every package's rows whether it was
    open or not -- closed ones being `display: none`. That is 3,413 buttons on every
    keystroke where the flat list cost 200, at **341 ms per character typed**. Its
    companion in the same pane: a search opened every package it matched in, and `e`
    matches all 4,734 routines across all 47 packages -- **483 ms on the first keystroke of
    an ordinary search**.

    Both are the glossary filter's 412 ms again (see the budget table), and the cause is the
    same one in a third costume: **work proportional to the whole program on every character
    typed**. The filter got there by calling `render()`; this got there by building markup
    nobody could see, and then by opening everything a broad query touched.

    The second was the worse *answer* as well as the slower one, which is the part worth
    keeping. "2,206 match `g`, in 43 packages" is something a reader can act on; 1,924 rows
    is the haystack again. A bound on how much a search opens by itself is not a performance
    concession, it is the better reply to a question that has not narrowed anything down
    yet. It must say so, though: closed packages with no explanation read as a control that
    failed -- design rule 1 with nothing removed but everything hidden.

46. **An opening rule that names a position breaks exactly as an ordering one does.** Rule
    24's companion was recorded as *an ordering rule that names a position rather than an
    identity breaks the moment anything is added beside it*, and it was written one function
    away from where the accordion decided which group to open: `order[0]`. So with the menu
    order set to "Ways in first" the navigator opened on six entrypoints and left the
    routine list -- which design rule 26 says the navigator *is* -- closed. The menu order
    decides what sits at the **top**; it was never asked what should be **open**, and two
    questions sharing an answer is how one of them gets answered by accident. The group is
    named (`primary`) now.

    Found by looking at the pane, not by any of the six guards written that hour.

47. **Dimming says what is not yours; it does not say which one is.** Design rule 19 dims
    the other nine thousand rather than hiding them, and that is right -- a subset is only
    legible inside the shape it belongs to. But a reader looking for *one* routine among
    9,874 dots then has to read their answer off a colour difference, with a dimmed node in
    front of or behind the lit one looking much the same at two pixels across. Worse, the
    picture answers questions about whichever dot the cursor lands on: hovering a neighbour
    by a pixel produces a confident card about a routine nobody asked about, and it is
    indistinguishable from a card about the one they did.

    So identification is its own channel -- a reticule on what was picked, fixed in screen
    size because a mark that shrinks with the picture stops working exactly when the picture
    gets crowded -- and *what may answer* is separated from *what is drawn*. Locked, only
    the lit set replies to a hover or a click; the fog stays on screen, because rule 19's
    reason for drawing it has not changed. **The moment that separation collapses the
    feature is a filter on the picture**, and then rule 19 forbids it and design rule 1
    wants a count for it. Exploring wants the opposite of all this, so it is a switch and it
    sits where the reading happens rather than in Settings.

    Its companion, and the sharper lesson: **two pickable layers reporting through one
    handler is an index that means two things.** `info.index` from the pointer layer is an
    index into two dozen arrows; read as a node index it selects a different routine,
    plausibly and in silence. Route by layer, which is design rule 16 one level below where
    it is usually applied -- and note that the arrow's click had to *set* the selection
    rather than toggle it, because the node an arrow stands over is already picked and
    `replace` on a single pick is the deliberate toggle-off (rule 33). The one control whose
    entire purpose is *go there* would have cleared the selection instead.

48. **A scripted click proves the handler; only a pointer proves the path to it.**
    `element.click()` invokes the listener on the element it names, whatever is drawn on top
    of it. So a session that drove the detail window through `.click()` — opening it,
    hopping, going back, closing — verified every control on it and could not see that
    **the scrim was painted over the whole window**: `.viewer-scrim` at z-index 90 above a
    window at 88. It rendered greyed, and every click on it landed on the scrim and closed
    it. Reported from a screenshot within minutes.

    Two things follow. Hit-testing is a separate claim from wiring, and `elementFromPoint`
    is how a script makes it — `el.contains(document.elementFromPoint(cx, cy))` is one line
    and would have caught this at once. And **a scrim belongs to one window**: two windows at
    different depths cannot share one, because a scrim must be under what it dims and over
    everything else, and one element cannot be both. They are declared as pairs now.

    This is the `[hidden]` defect and the `table-layout` defect in the same family: three
    times now, a control has been correctly wired to a stylesheet that could not carry it,
    and every check that reads markup or handlers passed. What the DOM says and what the
    reader can reach are different questions.

49. **A fallback that yields a plausible value has hidden the failure it was written for.**
    `fitView` read `g.container?.clientWidth || window.innerWidth`. Mounted while its pane
    was still hidden — a hidden container is 0×0 — it framed the stack for a 1275px window
    and drew it into a 496px canvas, so the graph came up empty and stayed empty until the
    reader found snap-to-fit. Nothing failed, nothing logged, and the number was entirely
    reasonable; it was simply about a different box.

    A fit against something not laid out is not computable, so it is **deferred** rather
    than guessed: the view state is returned untouched and the debt is paid on the first
    reveal that has a size. Deferring is what makes it recoverable; substituting is what
    made it invisible.

    Its companion, found the same hour and the reason the fallback ever ran: `ensureGraph()`
    was called **before** `render()` on the mode toggle, so the engine measured a container
    the next line was about to un-hide. `boot()` had the order right. **Paint, then measure**
    — an order that is correct at one call site is not a property of the code.

50. **A scroller is the element that scrolls, not the one that declares `overflow`.**
    `.tablewrap` carries `overflow: auto` and looks like the scroller. Nothing bounded its
    height, so it grew to all 339,229px of the table and never scrolled a pixel while the
    *pane* scrolled underneath it. Two features were written against it and both failed
    silently in the same way.

    The sticky header — position, offset, z-index and background all correct — stuck to a
    box that does not move, so it scrolled away and took the resize handles and the subject
    strip with it. And the reveal moved a `scrollTop` with nowhere to go, while its own check
    compared the row against a box extending far below the window, which made every row "in
    view" and reported success. **A guard naming the right case and measuring the wrong box.**

    Ask, do not assume: walk up until something genuinely overflows. And if a box is meant to
    be the scroller, bound its height so it is one — the wrapper is a fixed header over a
    scrolling body now, which is the shape the navigator was already given for the same
    reason.

51. **A rule kept at a call site rots as callers are added; move it to where they all pass.**
    `selectFromNav` did not move the routine list to its selection, on the reasoning that a
    row the reader clicked is already under their eye. True of its one caller, and false of
    every caller it acquired since — a table row, a hop in the detail window, the arrow at
    the plate's rim, the other browser window. All four left the navigator marking whatever
    had been clicked last time, and **a stale highlight is worse than none**: it is a
    confident wrong answer. It was reported as a question — *is that accurate? I can't tell*
    — which is the most expensive way to find anything.

    Its companion, the same shape in state rather than in behaviour: the detail window held
    a node id **of its own** beside the selection, and the two drifted the first time
    anything else moved one of them — the trail's Back stepped the app to the previous
    routine and left the window on the one after it. Two answers to "what am I looking at",
    in the window built to show how things connect. It holds *open or not* now and reads the
    one selection, so it cannot disagree by construction.

    Both are the same instruction. One truth, one place that owns it, and every caller
    reaching it through the same door — because the list of callers is the thing that grows.

52. **A cache that takes a value has already done the work it exists to avoid.** The code
    browser rebuilds a file's markup once and re-attaches the node, because `buildNav()` and
    `render()` both rewrite an `innerHTML` and both run on every selection — 1,937 ms and
    1,358 ms per click with a 5,838-line file open. The cache was written as
    `codeCached(slot, codeTable())`, and JavaScript evaluates arguments before the call: the
    1.37 MB string was built on every hit and discarded. It takes a thunk now.

    Its companion, and the more useful half: **re-attaching a large subtree is not cheap
    either.** Moving 17,500 elements back into the document forces a style recalc and a
    layout over all of them — `render()` measured *worse* after the cache than before it,
    155 ms to 1,370. A node kept in the document costs nothing, so the pane is simply not
    repainted when only the selection moved, and the highlight is two class changes. The
    check on that is the DOM, not a flag: a flag saying *already painted* is true of a pane
    another view has since overwritten, which is rule 42 in a repaint.

    Both were invisible to every test, and both were found by driving the thing.

53. **A layout bounded by arithmetic is right at one window size.** The code pane declared
    `max-height: calc(100vh - 16rem)`, where 16rem stood for the chrome above it. On a 589px
    window that chrome came to 185px, the box overflowed its own scroller, and **one line of
    code was on screen** — while every check on the page passed, because the box did declare
    `overflow` and did have a height. Rule 49's shape in a stylesheet: a plausible value
    standing where a measurement belongs, and no symptom beyond a picture nobody had looked
    at.

    The remedy is the one rule 29's companion already gives. A flex child is `min-height:
    auto` and refuses to shrink below its content, so the chain has to say `flex: 1;
    min-height: 0` at *every* link between the scroller and the box — and a single missing
    link collapses the pane to its content with nothing anywhere to indicate which one.

    Not fixed, and reported rather than changed because it is a design decision that is not
    mine: the navigator's nine group headings cost **306px** whether or not their groups are
    open, so on a short window any open group — the routine list as much as the code — gets
    about 200px. That is pre-existing and affects every group equally.

54. **A guard that names the wrong container has not guarded anything, and the container
    is usually the generated one.** The Code group's file filter destroyed the box it was
    typed into, on every keystroke, for as long as it had existed: `buildNav()` wraps every
    group's body in a `<div class="nav-items">`, so `group.querySelector(".nav-items")`
    inside `#navCode` returns the **wrapper** and writing rows into it replaced the whole
    body, input and caret and all. Filtering 626 files has never worked past one character.

    The guard for exactly this passed the whole time. It asserted the refresh does not
    *call* `buildNav` — true, and beside the point, because it rebuilt the pane without
    going through it. Rule 37 said check that a guard catches rather than that it mentions;
    this is the same instruction pointed at a **selector**, and the general form is worth
    keeping: *a class the generator emits around every item cannot distinguish the wrapper
    from what the item puts inside it.* An id can. The same session found the same shape one
    layer out — a flex chain written for one of a component's two states and applied to
    both, which squashed the other to 118px and let 1,900px of content overflow it visibly
    and paint over the four panels below. Every row present, sized, correct and unclickable;
    `elementFromPoint` said `.nav-head` for all thirteen on screen. Neither was visible to
    any test, and both were found by driving the thing.

55. **A bound must be on the work, not only on the answer.** Rule 45's auto-open is free
    where it was written: the routine list opens packages whose rows are already in memory,
    so the only cost is markup. Carried into the search unchanged it marked 84 files open,
    and a file there is a **request** — ten queries for its margin. Eighty-four of them
    behind one keystroke is the very defect the rule exists to prevent, arriving by a route
    its own precedent did not cover. One file opens now, the top one, and only once the
    answer has narrowed.

    Its companion, and how it was caught: the 84 rendered `opening…` for ever, because
    *nothing fetched them*. The open state was computed in one place (`return !SEARCH.broad`)
    and the fetch lived in another, so a file could be open without anything having opened
    it. **One truth about what is open, and whoever sets it does the work** — rule 51 again,
    and the version that looks identical on screen right up until it does not.

56. **A file restored to disk is not a module restored to memory.** A mutation harness
    wrote `revisions.py`, ran the tests, and wrote the original back in a `finally`. The
    file was byte-identical to HEAD afterwards — `git status` clean, `grep` showing
    `replace(":", "-")` — and the next analysis wrote
    `graph@2026-08-29T23~43~25Z.db`. Python revalidates a `.pyc` on the source's
    **(mtime, size)**, and a one-character-for-one-character mutation changes neither
    when the restore lands in the same clock second, so the interpreter kept running the
    mutant out of `__pycache__` while every way of inspecting the source said it was
    fine.

    Two things follow, and the second is the general one. A harness that edits source
    must invalidate the bytecode it caused to be written, not merely put the text back.
    And **the size-preserving mutation is the dangerous one** — every mutation in this
    session that changed a line's length invalidated the cache by accident and hid the
    defect, so the harness looked correct for as long as it was only used carelessly.

    This is rule 43 in the instrument for the third time in two sessions: the first two
    read pytest's output instead of its exit code and reported every mutation as
    surviving. Here the harness reported honestly and **corrupted the next command
    instead**. An instrument that modifies the thing it measures has to put it back at
    the level the next reader looks at, and for Python that level is not the file.

    **And the next reader is not always the next command.** A live check against the running
    dashboard reported `state.fold` set while `inspectorSubject()` returned null — an
    impossible pair, and the explanation was that the browser had fetched `shell.js` while
    this harness was part-way through rewriting it. The served file is a level the harness
    also has to put back, and a browser reads it on its own schedule. Do not drive the
    product while the harness runs; a mutant answering a question you asked of the real
    thing is a false finding with no tell at all.

57. **Admitting a directory for its documents must not admit a copy of the program.**
    `.claude` and `.groma` are kept in the document walk deliberately — that is where a
    project files its charter, its decisions and its naming standard, and skipping every
    dotted directory is right for code and hides the vocabulary. Nothing scoped that
    admission below the top level, so two stale agent worktrees under
    `.claude/worktrees/` put **335 of Mensores' 2,381 documents** — 14% of the corpus —
    into the map: a complete second copy of the project's governance documents from May,
    under the old `.paul` name, from before the rename this file's ground truth rests on.

    The tool defended itself better than it had any right to. The copy detector caught
    303 of the 335 and every consumer filters `duplicate_of = ''`, so the glossary, the
    naming lanes, traceability and the mirror were all largely protected. **The 32 that
    leaked are the ones that had drifted from their originals** and so were no longer
    byte-identical — which is the general shape: a near-duplicate defeats an
    exact-duplicate test precisely when it has become interesting.

    The marker is read off the disk and is never a question asked of a VCS: a worktree
    carries a `.git` *file*, a clone a `.git` *directory*. `os.walk` has already listed
    the directory, so the test costs no `stat` at all. The root's own marker is never
    consulted, because the corpus is itself a checkout and that is the point.

    Found by pointing DunneFlow at two points in time for the first time. Neither number
    was wrong on its own; the *difference* between them was 340 removed documents that
    Society had never removed, and a phantom is only obvious once something makes it move.

58. **A second read-only handle to a database this process already holds open is 36x
    slower, and it is only slow while the tool is doing its job.** The change diff
    attached both graphs with `mode=ro`, for the best reason there is: rule 20 says a
    read may refuse but may never repair, and one of the two is a snapshot somebody
    sealed. One `calls` comparison on Mensores measured **8,855 ms with the dashboard
    running and 242 ms with it stopped** — same query, same files, same page cache. A
    read-only connection has no write access to the `-shm`, so it cannot join the
    shared-memory WAL index the open handle maintains and re-derives it per query.

    The trap is the shape of the measurement, not the number. Every timing taken of this
    module before that one was taken with the server stopped, where it is 242 ms and
    perfectly healthy — so it would have been recorded as fast, shipped, and been 87
    seconds behind the reader's first click. **A component measured in isolation has not
    been measured in the state it runs in**, and for a server the state it runs in is
    "holding its own files open". Rule 24's family: the benchmark must submit the frame
    the product actually draws.

    The fix is to attach the *other* graph onto the connection that already has one —
    137 ms — which is what `Store(shared=True)` was already for. And the read-only
    guarantee is then kept the way rule 25 keeps `sourcedb`'s: by a test asserting the
    module contains no write statement, over its **string literals via `ast`** rather
    than by grep, because the prose explaining why there are no writes contains the word
    `DROP` and a check that cries wolf is a check nobody reads (rule 43).

    Two smaller things fell out of it, both silent. `PRAGMA query_only` buys the
    guarantee back and buys the slowdown with it, so it is not an escape. And a
    **relative path inside a `file:` URI is not that path** — `file:output/mensores/…`
    reports "unable to open database", naming the file it could not open and never
    saying why.

59. **A mutation harness must prove its baseline is green, or every mutation reads as
    caught.** A run scored **7/7** while one guard was already failing on an unrelated
    attribute: the suite was red before any mutation, so each one "went red" and the
    single mutation that genuinely survived was invisible inside the perfect score. The
    honest score was 6/7. A harness that only knows *red after* cannot tell a mutation it
    killed from a suite that was already dead.

    Rule 43 in the instrument for the fourth time in two sessions, and the four are worth
    listing together because no two look alike: two read pytest's **output** instead of
    its exit code and reported everything as surviving; one restored a file of identical
    size within the same second and left the mutant running out of `__pycache__` (rule
    56); this one measured against a red baseline. Every one of them was a check about
    checks, and every one reported confidently.

    Its companion, from the same run: **a mutation that leaves any read of the thing
    standing has not removed it.** Deleting a handler's `closest("[data-x]")` while its
    `dataset.x` line remains keeps the attribute "read" by code that can no longer run —
    so the guard passes, correctly, on a claim narrower than the one being tested. When a
    mutation survives, ask whether the guard is weak or the *mutation* was, before
    changing either.

60. **A stored path is a key before it is a location, and an absolute one is a bad key.**
    Every path in all three stores was absolute -- 55,434 rows in one graph alone. Three
    of the costs are about a program directory being a thing somebody can *hand over*: it
    publishes one machine's directory layout to whoever receives it, it is wrong the
    moment a tree is moved to free disk space, and it is wrong on every other machine a
    copy reaches.

    The fourth is the one that mattered here. Two revisions read from two different trees
    give the same file **two unrelated keys**, so nothing can pair a file with itself
    across two points in time -- which is the one question two revisions exist to ask.
    Joined as stored, Mensores' pair read **0 identical, 628 added, 625 removed**. The
    truth is 613 identical, 12 modified, 3 added, 0 removed, and it costs one query and
    **zero body reads**, because the sidecar is content-addressed: a hash comparison *is*
    the file-level diff.

    The origin was one line, and it had been announcing itself: `rel = str(path)`, with
    `module_name(path, root)` computing the genuine relative form on the very next line.
    Nothing needed the absolute form back -- bodies are fetched by content hash, never by
    opening a path, and the only step that touches the disk is analysis, which is handed
    the root as an argument. So the root is **used and never recorded**, and the reader
    binds one only when something actually opens a file.

    Two things fell out that say the shape was right. The strip already existed **ten
    times** -- nine identical `_rel()` clones across the renderers plus `_short()` in the
    code browser -- so storing the relative form was a net deletion; and those clones were
    not the harmless no-ops they looked like, because `Path("a/b.py").resolve()` resolves
    against the *working directory*, so run from inside the analysed tree they would have
    silently prepended the intervening directories to every path on the page. And a move
    became free: **0 cache hits and 628 files pruned** under the old key, 628 cached and
    nothing pruned under the new one, for a move that changed no byte.

61. **A second way into the store must obey the rule the first one was taught.**
    `entrypoints_from_packaging` reads `[project.scripts]` and writes rows directly; it
    never goes through the extractor. So making the extractor's paths relative moved
    54,746 rows and left **four** absolute -- in the one place `CLAUDE.md`'s own ground
    truth lives, the four declared executables. Nothing failed. 54,746 of 54,750 moving
    looks exactly like success, and every unit test passed, because the sample program has
    no `pyproject.toml` and nothing exercised that writer at all.

    Found by scanning **every column of every table in every store** for the analysed root
    rather than by checking the columns the change had touched. That is the difference
    between a check that confirms what you did and one that can tell you what you missed;
    the same scan is what proved the only absolute strings left anywhere are paths quoted
    inside Society's own handoff documents, which are content and stay whole (rule 8).

    Its companion, and the reason it is a rule about *one meaning per column*: those rows
    land in `COALESCE(r.file, e.file)`, the same payload column as a routine's file. A
    `src/` layout puts `pyproject.toml` one directory *above* the code, so the honest
    answer is `../pyproject.toml` -- and the migration needed the same transform, not a
    prefix strip, which cannot express `..`. A first version stripped only, and left those
    four rows absolute in every graph while reporting a five-figure success.

62. **A migration may re-stamp the fingerprint it satisfies, and only that one.**
    Making paths relative meant editing the extractors, which moves `rules_fingerprint()`,
    which makes every existing store stale -- so a correctly migrated graph is one no
    reader will open. The migration therefore re-stamps `meta.extractor` too, and that is
    defensible **only because it performs exactly the transformation the new fingerprint
    stands for**: no rule about what counts as a call, a boundary or a constant moved,
    only the spelling of a column.

    Left general that is a licence to vouch for changes it did not make, so it is **gated
    on the stored fingerprint being one specific prior value**, named as a constant. Any
    other is stale for reasons this migration cannot speak to and is refused, naming
    re-analysis instead. The marker for *have the paths been converted* is its own meta
    key rather than the schema version, because bumping that **discards** the graph -- and
    the whole reason to migrate in place is that a sealed snapshot is kept precisely so it
    can be read after its source tree is gone. Rebuilding would orphan exactly those.

    Two smaller things it settles. A reader must name **which** fix applies: telling
    someone to re-analyse a snapshot whose tree no longer exists is telling them to do the
    impossible. And *"the paths are relative"* is **stated in a marker, never inferred
    from the rows** -- an empty store holds no absolute path to find, and "nothing to see"
    is not the same claim as "already converted".

63. **A store's reader must read the columns that exist, not the ones this version of the
    code knows about.** Rule 20 says a read may refuse but may never repair, so a
    read-only open never runs an additive migration -- and the dashboard opens `source.db`
    read-only every time it starts. Adding a column and naming it unconditionally in the
    reader's SELECT made that SELECT raise, a pre-existing blanket `except sqlite3.Error`
    turned the raise into `rows = []`, and a two-revision program was **served as holding
    no revisions at all**: state, label, capture instant and file counts blank, with no
    error anywhere.

    Rule 49 in a schema: a fallback yielding a plausible value hides the failure it was
    written for, and this one consumed the evidence on the way past. The reader asks
    `PRAGMA table_info` and selects what is there; a column the file does not have reads
    as empty, which is the honest answer -- *captured before we recorded this* rather than
    *we recorded nothing*. This bites hardest on the one store that is never rebuilt (rule
    25), because there is no re-analysis that would repair it.

    Found by reading the served JSON and noticing four fields had gone empty since the
    previous request. **No test compares two runs of a server**, and every unit test opened
    the store for writing, where the migration always ran.

64. **The leaf that identifies a tree is the package root's, not the analysed
    directory's.** Two versions of one program are two directories, so the directory's
    name is what a reader recognises them by -- an instant only says when we read the
    bytes. But `target.name` for a `src/` layout is the string `src`, which names every
    src-layout program ever analysed and therefore identifies none of them.

    The right leaf is the one the upward walk for `pyproject.toml` already finds, so the
    fix hoists that walk above the sidecar open and retires a duplicate of it. **Invisible
    to every fixture in the suite**, because none of them has a `src/` to be wrong about,
    and correct on the first real run only by accident of where the fixtures put things --
    which is the same shape as rule 61: the sample program had no `pyproject.toml`, so
    nothing exercised the writer at all.

65. **Name a set for where it is, not for what befell it.** The change worklist reported
    `added` and `removed` -- both of which are claims about *time*, from a store whose only
    instant is when it read the bytes. They were correct only because the default pairing
    happened to make the base the newer capture; analysing an older copy inverted the whole
    view, confidently, with no symptom.

    The bands are `only_in_base` and `only_in_compared` now, which is a fact about set
    membership, and *added* / *deleted* are an interpretation the **reader** owns, stated
    on a strip that is always on screen. Two things fall out and both are load-bearing.
    Flipping the interpretation costs **zero queries**, because nothing was baked in. And
    the tool stops asserting something it cannot see, which is the whole of design rule 1
    applied to a vocabulary rather than to a filter.

    Its guard is worth copying: assert over the **keys the answer carries**, not over the
    source, because what misleads a reader is what reaches them. And assert over the
    *parts* of each name -- the first version tested whole keys, and `routines_after`
    contains the forbidden word rather than equalling it, so the one mutation that survived
    did so because the guard was weak rather than because the mutation was (rule 59).

66. **An order the tool cannot defend is not an order.** Which of two versions is newer is
    often knowable -- a program states a version, and comparing two of them beats any
    default. Three things make that a false claim if they are skipped, and none of them has
    a symptom.

    **`1.10.0` sorts below `1.2.0` as a string**, so the comparison is over integer tuples
    and is computed where it can be tested rather than in a template. **A date and a
    release number are both orderable and are not orderable against each other** -- the
    keys compare perfectly happily, so the *kind* travels with the key and the caller
    refuses across kinds. And two versions that are **equal**, or one carrying a
    prerelease suffix, rank *nothing*: `1.0.0-rc1` precedes `1.0.0` under semver and
    follows it under other conventions in the wild, so choosing would state an order
    nobody can defend. Rule 1 three times over, in a place where every wrong answer looks
    exactly like a right one.

    Its companion, about the *setting* rather than the ordering: an answer that is
    sometimes derived and sometimes chosen is **three states, never a boolean**. `auto`
    must re-derive when the subject changes, or an explicit choice made about one pair is
    carried silently onto the next -- rule 51 with the reader's own decision as the thing
    that drifts. And each state must say which it is: derived, chosen, or assumed for want
    of anything to read. A colour a reader cannot account for is worse than no colour.

67. **A control's value is state, and the browser will supply one if you do not.**
    A `<select>` rebuilt by script has its pre-reload value **restored by the browser**,
    and that restoration outranks the `selected` attribute the code wrote. So after a base
    switch the pair control named the pair the reader had been on *before* the switch,
    while the strip beside it correctly named the new one -- one control, two claims, and
    the markup was the one that lost. Every source-reading check passes: the attribute is
    written, on the right option, for the right reason.

    Assign the value from state rather than defending against the restoration. A control
    that derives its value from state has nothing left for a restoration to disagree with.
    This is rule 48's lesson in a form `elementFromPoint` cannot reach -- what the DOM says
    and what the browser has since done to it are different questions -- and like rule 48
    it was found only by driving the thing.

    Its companion, and why it could hide as long as it did: `chosenPair()` returns
    `{base, compared}` and the control read `.from`, a key it has never carried. Undefined
    is not an error, so the marker was the empty string on **every** build and the menu
    opened on the wrong row after every reload. Rule 44 one step further in -- not a field
    the *server* does not send, but a field this file does not send itself.

68. **A restore is a setter, and it must do what the setter does.**
    Rule 55's companion says *one truth about what is open, and whoever sets it does the
    work*. `setGroupOpen` did the work; the boot that restores `navOpen` from storage did
    not. So a reader who left the Changes group open reloaded into a group sitting open
    under *"two versions -- open to compare them"* with nothing to open: a note telling
    them to do the thing they had already done. It had been there since the group was
    built and takes a reload to reach, so it was invisible -- until a base switch, which
    reloads, so every switch out of an open group landed on it.

    The fix routes from the table (rule 36), so a group that declares an `onOpen` is
    covered without anyone remembering. And it went wrong once on the way, which is the
    part worth keeping: written as `state.navOpen[g.id]` it fetched nothing on a fresh
    profile, because openness has **two** expressions -- what the reader arranged, and the
    table's own default for a group they have arranged nothing about -- and `groupOpen()`
    is the one place that knows both. Rule 51 inside the fix for rule 51.

69. **Contrast says whether a colour can be *read*; it says nothing about whether two
    colours can be told *apart*.** Design rule 6 clamps customisation at a contrast ratio
    and that is right and insufficient: it is a claim about one colour against its ground,
    and a channel that separates two meanings is making a claim about a *pair*.

    The dashboard's own palette passed the first bar and failed the second for its whole
    life. `--sev-broken` `#b91c1c` and `--sev-suspect` `#92400e` are 6.47:1 and 7.09:1 on
    white — comfortably legible, and **to a deuteranope the same colour**: simulated, they
    are ΔE 5.3 apart, the worst number in the product. The difference pair was little
    better at 12.7. Every check that existed passed, because every check asked the
    answerable question rather than the useful one.

    So a set states both: contrast against each ground it is drawn on, and **separation**
    as the worst CIE Lab ΔE across normal vision, deuteranopia and protanopia (Viénot,
    Brettel & Mollon 1999). The worst, never an average — a pair obvious to most readers
    and invisible to some is not a pair that works, and averaging is the arithmetic form of
    not caring.

    Two things the arithmetic settled that guessing would not have. **Red and green cannot
    be rescued by tuning**: every chroma and every lightness inside that hue family measures
    between 4 and 14, so only changing the hues changes the answer. And **a difference in
    lightness survives colour blindness where a difference in hue does not** — so forcing
    both colours of a pair to the same contrast ratio throws away the one axis that always
    works. The shipped dark pair is separable partly because it sits at 6.06:1 and 9.63:1,
    which nobody intended.

    **A channel has a capacity, and this one is now full** — found 2026-08-31, adding a
    sixth meaning to the difference channel. Sweeping every hue at every saturation and
    lightness, against every colour in all three sets plus the two grounds, in all three
    vision models: nothing clears a useful bar in **both** themes. The light theme is the
    binding constraint — red, orange, green, blue, violet, purple and two greys are already
    spent, and what is left is yellow, which cannot hold 3:1 on a light ground.

    Two things follow. The colour chosen for `mixed` is the best available rather than a
    good one (worst ΔE 29.8 light, 45.3 dark), and it is stated as such. And **a seventh
    meaning cannot be added by colour at all** — the next one wants a different channel,
    which is what design rules 4 and 5 have been saying since before there was a reason to
    listen. Knowing a channel is full is worth as much as knowing a pair is separable.

70. **The version on screen decides which bytes, and the sidecar cannot know which that
    is.** There is one `source.db` per program holding every revision, and its own default
    is the newest snapshot -- which is the right answer only while the newest is also the
    version being read. It stopped being that the day a reader could switch the base, and
    six readers went on asking the store rather than the base: the code browser, the file
    list, the search, `/api/source`, the inspector's definition and the cover's line count.

    Serving Mensores' older graph returned `_queue.py` at **674 lines with the 595-line
    version's marks laid over it** -- every link past the first divergence underlining the
    wrong characters, a margin describing lines that had moved under it, and a footer
    naming the revision the *bytes* came from while the facts came from another. Nothing
    raised. The page looked exactly like a page that works, which is what a file always
    looks like.

    Rule 51 in the shape that rule was written for: a default that was correct while there
    was one version and one graph, and wrong for every caller acquired since. The base
    names the revision and every reader is handed it; a sidecar that does not hold that
    revision is `None` and a **stated absence**, never the newest bytes substituted for the
    ones asked for (rule 49 -- the plausible value is what hides the failure).

    Found by pointing the tool at its own two revisions and comparing what came back, not
    by any test: every unit test opened one revision, where the default is right.

71. **A class name is global, and a stylesheet gives no warning.** The code browser's file
    rows were marked `chg-same` / `chg-mod` / `chg-one`. `.chg-mod` already existed -- it is
    the change worklist's *module* label, `font-size: .7rem; color: text-faint` -- so every
    **modified** file rendered smaller and greyer than the unchanged ones, which is the exact
    inverse of what a mark is for. Every check passed: the markup is right, the handler is
    right, the class is written, and nothing anywhere is dead.

    Its companion, found in the same row and the same way: **markup another function
    rewrites is not the markup that renders.** `dressNavItems` gathers a row's loose text
    nodes into a `.navlabel` and re-inserts it immediately before `.n` -- so an element
    written between the file name and the count is moved *in front of the name*, and the row
    read `mensores/scriba/ ○ _queue.py`, a glyph inside a path.

    Both are the same instruction one level below where the checks look: what this function
    writes and what the reader sees are different questions, because a stylesheet and a
    later pass both get a say. The classes are prefixed and every rule that styles one is
    scoped to `.codefile`, asserted in both directions so a name taken later cannot reach
    these rows. Found by looking at the pane, which is now the fourth consecutive session
    that has paid for itself.

72. **A gesture's target is not what is under the pointer, and an instrument that cannot
    reproduce that reports its absence just as confidently.** The compartment diagram
    captured the pointer on **every** press inside its canvas, to pan. A captured pointer
    retargets the compatibility mouse events with it, so `click` and `dblclick` arrived
    naming the canvas rather than the box: `ev.target.closest("g.node")` was null and every
    handler in the view returned having done nothing. Clicking a box did nothing, opening
    one did nothing, and **nothing failed** — the handlers were correct the whole time and
    were being handed the wrong element.

    Rule 48 said a scripted click proves the handler and only a pointer proves the path to
    it. This is the sharper half of that, and it is why the defect survived two sessions and
    two rounds of verification: the automation's own click **could not reproduce it**.
    `setPointerCapture` throws `NotFoundError` for a pointerId that is not active, and the
    injected pointer's never was — so the capture silently never took for the instrument and
    took every time for a real mouse. Both sessions reported the feature working.

    Two things follow, and the second is the general one. **Capture on the first move past a
    slop, never on the press**: a drag needs it and a click does not, and taking it early
    costs every click in the view. And when the instrument and the product disagree about
    something as basic as which element was clicked, **reproduce the failure rather than the
    gesture** — a retargeted click *is* a click whose target is the container carrying the
    coordinates of the press, and that can be dispatched. The fix is then verified against
    the defect (rule 37) rather than against a simulation of the act.

    Its companion, and cheap: read the element with `elementFromPoint(ev.clientX,
    ev.clientY)` when `ev.target` yields nothing, so the next thing to capture a pointer
    cannot break it again. That is the same tool rule 48 names for proving a control is
    reachable, used to *be* reachable.

73. **A picture must not move under a gesture, and identity is what survives when it
    does.** The diagram's SVG was `width: 100%` with `preserveAspectRatio`, so the *browser*
    fitted it — and re-fitted it on every container resize. The first click on a box
    un-rails the inspector, which narrows the centre column, which moved the whole drawing
    **139 pixels** out from under the reader's cursor. Their second click landed on a
    different box, so `dblclick` never fired: once per session, on the first double-click
    anyone tries.

    Two fixes and they are different in kind. The **cause** is that framing was the
    browser's job; it is our own transform now against a drawing that carries its own pixel
    size, which is what design rule 20 already requires of the stack — framing is arithmetic,
    and there is always a way back. Deferred rather than guessed when the pane has no size
    yet (rule 49). And the **gesture** is keyed on the box id rather than on the element or
    the position, because a reflow changes every position and no identity.

    The general form is worth more than either: **a layout change is a legitimate response
    to the first half of a gesture, and it invalidates the second half.** Anywhere a click
    opens, rails, or resizes something, the next click in the sequence is landing somewhere
    the reader did not aim.

74. **A fold is not one of the things it folds.** A diagram box is a class and its methods,
    or a file and its loose functions. Clicking one handed `selectFromNav` the members and
    let it elect `members[0]`, so a box labelled `KernelDecl` holding sixty-one methods
    filled the inspector with `KernelDecl._profile_name_or_none` — a perfectly true answer
    about something nobody clicked. Reported as *"the Inspector does not change to reflect
    that specific node"*, which is exactly what it was.

    **The stack has never made this mistake**: picking a *plate* clears the selection,
    because a plate is not a node. So what was missing was an answer rather than honesty
    about the lack of one, and the answer is that a fold is a **subject** in its own right —
    same skeleton as every other specimen, so the pane that exists renders it, with `holds`
    listing what it stands for, never bounded (rule 8).

    Two consequences that are the same rule one layer out. Every reader of "what is
    selected" has to know there are two kinds — the auto-rail read `state.selected`, so the
    complete answer was painted into a column **zero pixels wide**, and the trail filed every
    box click as *"nothing selected"*. And every *writer* has to go through one owner, or
    the fold outlives its selection at whichever of the four call sites was forgotten
    (rule 51). Assert the writers as an **absence** over the whole file: the failure is a new
    hand-written site, not a change to an existing one.

75. **A column offset is a *byte* offset, and a character slice is silently short.**
    `ast`'s `col_offset` and `end_col_offset` index the **UTF-8 encoding** of their line,
    not its characters. Slicing the line as a string is right on every ASCII line and
    wrong by one position per multi-byte character on every other, and what comes back is
    not an error: it is a plausible expression carrying a stray `,` or `)`.

    Measured on the real tree rather than argued: **235 of 44,344 single-line call
    arguments would differ**, and they are the interesting ones —
    `f"must be a positive int ≤ {_TTL_MAX_SECONDS} (1 day)"`,
    `f"  [red]•[/red] [{kind}] {msg}"`, `f"Society 5-layer reconstruction — {framework}"`.
    Every one a message with a symbol in it, which is exactly what a reader opens a flow
    panel to read. 613 of Mensores' 628 files hold a non-ASCII character somewhere.

    Rule 27 in a different alphabet — there a marker had to sit at an *edge* of a name;
    here an offset has to be measured in the units it was written in. And rule 8 at
    ingest: the value that reaches the store is the value for good, so a slice that is
    two characters adrift is not "close", it is a different expression.

    `ast.get_source_segment` is correct and re-splits the whole file on every call, which
    over 184k lines and 30k call sites is the file split a hundred thousand times. Slice
    the lines the extractor is already holding, on their encoded bytes.

    Its companion, from the same edit: **`ast.unparse` is a re-rendering, not the
    source.** It returns something equivalent and not identical — `d["k"]` comes back as
    `d['k']`, a wrapped argument comes back on one line — and a reader who goes looking in
    the file for the string the product showed them does not find it. Recording what a
    caller passes means recording what the caller *wrote*.

76. **An echo is not an act, and the engine cannot tell you which it is sending.**
    `applyWanted` hands the stack a selection the app has already decided, and
    `Graph.setSelection` announces it **synchronously** -- so `onGraphSelect` ran inside its
    own caller's turn and re-subjected to `sel.node`, which is the *last node of whatever
    was just installed*. One arbitrary member of it.

    That is rule 74 exactly, arriving through the engine instead of through the caller: a
    box click set `state.fold` and the echo replaced it with a method of that class two
    lines later; opening an arrow set `state.flow` and the echo replaced it with a routine.
    The pane then answered truthfully about something nobody clicked, and filed a second
    trail step under that member's name on the way past.

    **It had been live since the fold was built, and it was verified twice.** In Diagram
    mode with the stack never mounted, `applyWanted` returns at `Graph.mounted()` and
    nothing echoes at all -- so the feature is correct exactly as long as nobody opens the
    graph. Found by driving with the graph up, which no test had reason to do. Rule 38's
    companion: an instrument that never reaches a state cannot report on it.

    The fix is a flag raised for the duration of the one call that re-enters, in a
    `finally` -- a throw inside the engine would otherwise leave the shell deaf to every
    later selection. `state.picks` stays outside the bail, because the engine is the
    authority on what is *picked*; everything else in that handler is "what to do about a
    new selection", and the caller that installed this one does all of it itself.

    The general form, and it is the third costume rule 51 has worn: **a notification you
    caused is not a notification you received.** Anywhere something announces changes it is
    also given, the receiver has to be able to tell the two apart, and nothing in the
    message says which it is.

    **Amended 2026-09-01: the flag was put at the site the defect was found at, and there
    were three.** `Graph.mount` is handed `picks: state.picks` and finishes by calling
    `announceSelection()` for exactly the same reason `setSelection` does, and it was not
    flagged; `applySelectionStep` raises `restoringSelection`, which only ever suppressed
    `recordSelection`, so a Back ran the whole handler under `sel.node` and was corrected
    on the next line — right by ordering rather than by design.

    Both were unreachable until the doorway panel, which is the first surface in the
    product that can follow a subject with the stack **never mounted**. It showed the mount
    case immediately: a card naming `backup_cmd` opened the inspector on
    `mensores.transport._envelope.<module>`, an unrelated node, and filed two trail steps
    under its name. One predicate now covers all three sites and a guard asserts there is no
    fourth — because the failure to guard against is a *new* way to hand the engine a
    selection, which would look exactly like working code.

    So the rule has a second half: **a guard against an echo must cover every place that
    causes one, not the place the defect was found.** Rule 51 with a flag as the thing
    kept at one call site.

77. **A synthetic subject is minted on a condition, so it cannot carry a fact that does not
    share it.** `<module>` is this tool's stand-in for a file's own scope, and it owns the
    module-level comments, boundaries, calls and constants — everything that *runs at
    import*. A module docstring runs nothing, and hanging it on `<module>` was the obvious
    implementation: one join, no new row shape, and the comment lane's own precedent for
    naming the right subject for free.

    It covers **487 of Mensores' 628 files** while **619** of them state what the module is.
    `<module>` exists only where a file has module-level work, so for the other 141 there is
    no such routine — no `body_hash` moves, no fact moves, and a rewritten module docstring
    is reported by nothing at all while the page states **"No differences found."** That is
    the comment lane's worst answer standing again, in the one sentence a module writes
    about itself, and it would have shipped looking like a working feature: 487 of 628 is
    not a symptom.

    The subject is the **file**, and the row carries a path the code browser can open (rule
    30). Rule 74's family — a fold is not one of the things it folds — pointed at a
    *synthetic*: `<module>` stands for what a file does, which is not what a file says it is.

    Two things worth keeping. **Caught by counting rather than by a false result**, which is
    the only reason it is written here as a design decision instead of as a defect: the tell
    was 619 against 487, and both numbers are one query. And the cheap answer's failure mode
    is the dangerous one — it is right about the majority, wrong in silence about the rest,
    and the rest are exactly the files with nothing else going on in them.

    Its companion, found by *clicking* the row the decision produced: **a route correct for
    the caller it was written for is wrong for the caller it has just acquired.** `file`
    opens the code pane and deliberately leaves the centre alone, which is right inside the
    navigator's Code group where the list is under the reader's eye, and from a worklist page
    it sets the state, loads the file, and moves not one pixel. Rule 51 in the shape rule 51
    is about, and invisible to every test: the state was correct the whole time.

78. **A pane brought up to date by the control that moved it is only as correct as the last
    person to add a control.** Reported at the keyboard, mid-rabbit: *"When I change the
    center panel to Code, that panel shows `mensores/_internal/_governed_gates.py` which is
    not what I expect to see. Is this accurate, or is the center panel off?"*

    It was off. `/api/node` gave `mensores/disceptator/_extraction_state.py` for that node
    all along. What was on screen was `state.codeFile`, which is **persisted** — the file a
    session two days earlier had left open, in a package the reader had never opened, drawn
    with a title and a path and nothing whatever to say it was stale. A wrong answer wearing
    a correct answer's clothes; the reader had no way to tell, which is why it arrived as a
    question about the tool's honesty rather than as a bug report.

    Nothing was broken. The store was right, the selection was right, and
    `followSelectionIntoCode()` was right — it opens `if (!codeOnScreen()) return`, which is
    correct, because there is nothing to walk when the pane is not up. **The guard's
    condition has two halves — *the selection changed* and *the pane became visible* — and
    only the first of them had an event.** The walk was invited from exactly one place, the
    end of `loadSpecimen`. Selecting while Code sat behind another mode returned at the guard
    and left no trace, and the mode switch never asked again.

    Tom's rule is larger than the defect and is the rule here: *"Every possible venue that
    can change the point of view should be considered, so no control should ever expect that
    it 'knows' what it was showing before is still true."* A reader moves the point of view
    from the navigator, the centre, the inspector, the trail, the shelf, the crumbs, a hovered
    row, a diagram box, a search hit and a second window.

    **So a pane reconciles where every route arrives, not where each route remembers** — in
    `render()`. This is rule 51's family and it is worth its own address because rule 51 is
    about a *rule* rotting across call sites, where this is about *state going stale in
    silence*: nothing throws, nothing logs, and the pane looks deliberate. The audit that
    followed the report found three panes on each side of the lesson. Reconciling in
    `render()`: the table, the vocabulary lanes, the doorway panel. Relying on every call
    site: the code pane (one site, and the wrong one), the stack (four), the diagram (seven).

    **The four stack calls were mis-ordered as well as incomplete**, which is what makes the
    count the point rather than an aside. Every one of them sat *before* its own `render()`,
    so each was mounting into the previous view's layout — the defect recorded as *"the graph
    should have been there"*, found once on the mode toggle, fixed there, and left standing
    at the other three because the report named one handler. A guard was written for it and
    watched that handler. It watches `render()` now, which speaks for every route including
    the ones nobody has written.

    **The price is that a reconcile must be silent when it has nothing to do**, because
    `render()` runs on every keystroke, and two of the three were not. `ensureDiagram` claimed
    its lock before asking, ran to the bottom, and finished by rewriting `#diagramMount` — the
    mount that exists *specifically* so `render()` will not touch it — taking the laid-out SVG
    and the reader's pan and zoom with it. Make the reconcile cheap and quiet, or it becomes
    the thing that destroys the reader's place on every character they type.

    **And an automatic move must not fight a deliberate one**, which is what stops this rule
    turning a pane into a cage. The walk records **which subject** the pane was walked for,
    never merely *that* it was: a flag would be cleared by every selection and set by every
    walk, so a reader opening a second file to compare against the first could not keep it on
    screen for one paint. Marking the subject serviced lets them go anywhere inside one
    selection, and still follows them the moment they pick something new.

79. **A lifetime change is an access-pattern change.** Chunk 2 of Document mode moved
    `DocStore` from a handle opened and closed inside `_docs_for()` onto `_Base`, so a
    document list could be served from a store that was still open. Nothing about the store
    changed — not its schema, not its file, not one line of `docstore.py` — and every unit
    test passed, because a unit test opens a store and reads it on the thread that opened it.

    The server does not. A held store is opened on the thread that builds the base and read
    from a **request** thread, and sqlite refuses that connection **by name**:
    *"SQLite objects created in a thread can only be used in that same thread."* It failed on
    the routes that touch documents and nowhere else, which is the worst shape a failure can
    have — the map, the stack, the code browser and the glossary all kept working, so the
    thing that looked broken was Document mode rather than the decision that broke it.

    The rule the number is for: **who reads a thing is part of what it is.** Widening a
    lifetime — a handle held across requests, a cache promoted from local to module scope, a
    connection moved onto a long-lived object — changes nothing about the object and
    everything about the contract it is under, and the tests that cover the object are
    exactly the ones that cannot see it. `shared=True` is the fix here; noticing that a
    lifetime change needs a fix at all is the rule.

    Every other store this server holds was already opened `shared`, which is the tell: the
    correct posture was one line away and written down three times over, and the change that
    needed it did not look like a change to a store at all. So the guard is not a unit test —
    it starts a thread, reads the held store from it, and fails with sqlite's own sentence
    (`test_a_held_document_store_can_be_read_from_a_request_thread`).

80. **A job that can be interrupted must leave something that cannot be mistaken for a
    finished one.** Stopping `analyze` twelve seconds into the Society tree left a graph that
    opened perfectly and reported 628 files, 4,786 routines, 4,070 boundary touches — and
    `resolved_calls = 0`, because it died before `resolve_calls`. A program that calls
    nothing. It carried `analysed_at`, `tool_version` and `inference = none`, so the cover
    dated it, the selector offered it, the switch opened it and *About this map* vouched for
    its determinism. Every part of the tool agreed it was a map of a program, and the only
    thing wrong with it was everything.

    **The interruption is not the rare case.** This was reachable before any stop button
    existed: Ctrl-C in a terminal, a laptop that slept, an OOM kill, a full disk. The rule
    was earned while *adding* a cancel button, and the button was not what earned it — it
    only made a standing accident easy to reach.

    The rule the number is for: **a partial result is not a small result.** Work that writes
    as it goes will be stopped somewhere, and the half it finished is often the half that
    looks complete — 628 files really were read. What makes it a lie is the half that was
    not, and nothing in the artefact says which half that is. So the *writer* records that it
    has started and records again that it finished, and every reader that presents the
    artefact as whole refuses one that never said so.

    Three states, never two. `complete` missing means *written before this key existed* and
    is fine; `""` means *started and never finished*; `"yes"` means finished. Refusing on
    absence alone would refuse every artefact made before the rule, none of which is broken
    — the same missing-versus-blank distinction `/api/about` keeps for `inference` and
    `model`, one store over.

    **The marker must be durable at the moment of the interruption, or it is not a marker.**
    `Store.set_meta` does not commit; an uncommitted `complete = ""` is lost by exactly the
    `kill -9` it exists for, and the graph then reads as one that predates the key. That is
    the failure this rule prevents, arriving through the back door of the fix for it. Hence
    `set_meta_now`, and a test that kills a real child rather than reading the source for a
    `commit()` (rule 37).

    **Refuse on read, never on write.** `UnfinishedMapError` is raised by `_Live.open`, by
    `_open_store` and so by `check`, and by `serve`'s boot. `analyze` is deliberately exempt,
    because opening an unfinished map is exactly how it finishes one — 34 s against a 90 s
    cold run, since the extraction is content-hashed. Rule 20's shape: a read may refuse but
    may never repair, and the thing that *can* repair must not be locked out. `query` is the
    one reader that proceeds, and warns: its whole contract is that you get the rows that are
    there, and an escape hatch that quietly hands over a half-written artefact is not an
    escape hatch.

    **And the refusal has to name the way out.** *"Never finished"* is a dead end; *"analysing
    it again completes it — the extraction is cached, so it takes seconds"* is a fix the
    reader can press. A rule that only ever says no teaches people to work around it.

81. **A key that decides whether to skip work must carry everything the work depends on.**
    Document mode's related-documents block painted *"Looking for documents related to
    `<module>`…"*, the answer arrived **seven milliseconds later**, `render()` ran, and the
    sentence never changed. Nothing was broken anywhere in the chain: the endpoint answered,
    `RELDOCS` held the right object with `loading: false`, and calling `relDocsBlock()` by
    hand in the console returned the correct markup. The screen was simply never told.

    The doc pane repaints only when `docDomKey()` changes — a bargain worth 9.5 s per
    `render()` on a function that runs on every keystroke, so the bargain is right. The new
    block lived in that chrome and **its state was not in the key**, so the pane was told
    nothing had changed and believed it.

    **This is not rule 78.** That rule is about a pane nobody asked to update: the guard had
    two halves and only one had an event. Here every route asked, the state was correct, and
    the *paint* was skipped. Same silence, opposite cause — and the two are worth separate
    addresses because the fix is in different places: rule 78 moves the reconcile into
    `render()`, and this one puts the field in the key.

    **It happened twice in one session, in two unrelated caches, which is what makes it a
    rule rather than an oversight.** `selectionSnapshot()` writes a trail step's subject and
    `sameSelection()` decides whether two steps are the same one; they were two hand-kept
    lists of the same fields, `wayIn` went into the first and not the second, and drilling
    into a sub-application filed a step labelled `mensores ▸ quaestor` that was correct in
    every respect and deduplicated away. The comments on `diagramId`, `diagramBox` and
    `codeFile` each record paying that once — **in the snapshot**, where the lesson never
    reached the half that forgets.

    So: name the fields once and derive both sides from the list. `SUBJECT_KEYS` is that
    list, and the guard asserting the snapshot and the comparator agree **caught a second
    field the moment it was written** — `wayInsideName`, which is deliberately excluded
    because it is a *label* and the trail gave up deduplicating on labels for rule 30's
    reason. A rule that finds its next instance while you are still writing it is the shape
    worth an address.

    The failure mode is the worst kind to find by eye: **no error, no log, no missing
    element** — a stale sentence that was true when it was painted. Test it by changing the
    thing the key does not carry and asserting the screen moved, never by asserting the
    state is right; the state was always right.

82. **A long job is not a switch — a slot names what is being replaced, not what is
    running.** `serve` had one lock for *"something is rebuilding the base"*, and reading a
    new source tree wanted a lock too. Sharing it was the obvious move and would have meant a
    ninety-second analysis of an unrelated directory locking the reader out of changing
    version for reasons nobody could state on screen.

    The two are not the same act. **A base switch replaces what is on screen**, so every count
    underneath belongs to the version being replaced and blocking the page is honest: the map
    is about to stop being true. **An analysis of some other tree replaces nothing** — the map
    on screen stays true for the whole run — so it gets a dismissible panel and a second slot,
    `claim_analysis` beside `claim`.

    The test is not *how long does it take* or *how much does it cost*. It is **what does the
    reader lose while it runs**: name the thing being replaced, and if the answer is "nothing
    on this screen", it is not a switch however long it takes and however much machinery it
    shares. A slot exists to protect what is being replaced, not to serialise work.

    **And a slot must ask the process, not a flag** (rule 30). `claim_analysis` refused on
    `state == "working"`, which a watcher dying without noting leaves true for ever — a reader
    seeing nothing running and still being refused. It asks `poll()` now and clears the stale
    lock rather than leaving it for somebody to notice.

83. **An instrument's two coordinate systems can differ, and the one you can see is not
    the one you touch.** Rule 38 says an instrument that cannot see cannot report; rule 48
    says only a pointer proves the path to a handler. Neither says the instrument may be
    *self-inconsistent* — that its picture and its pointer answer in different units, so a
    coordinate read off a **correct** screenshot lands at twice its intended place with no
    error anywhere.

    Measured on a 1259×551 viewport at `devicePixelRatio` 2:

    | | CSS → frame factor | what the frame covers |
    |---|---|---|
    | **screenshot** | 784 / 629.5 = **1.2454** | CSS 0..629.5 × 0..275.5 — `inner ÷ dpr` |
    | **click** | 784 / 1259 = **0.6227** | CSS 0..1259 × 0..551 — the whole viewport |

    **The ratio between them is 2.000 — the dpr.** The capture path divides the viewport by
    `devicePixelRatio` and the input path does not, so the pixels you can see and the
    coordinates you must click are two different spaces in one tool.

    Neither factor was reasoned; both were planted and read. Five fixed bars at CSS x = 0,
    400, 780, 1000 and 1245: only the first two appear, and the 400 bar lands at image
    x ≈ 500, giving 1.2454. Then a click at frame (400, 200), caught by a capturing
    `pointerdown` listener, reported `clientX/Y = (642, 321)` — 1.605, which is 1259/784.
    Two instruments, two numbers, and the quotient is the dpr.

    **The cost of not knowing it was four sessions.** Each read the pair as two unrelated
    limitations — a capture that stops halfway across, and clicks that miss — and worked
    around both with `.click()`, which proves the handler and not the path. The pointer was
    never blocked: everything in the viewport has always been clickable, including the
    inspector at x=985. Only *sight* stopped at the halfway line.

    So **measure each direction separately before trusting either**, and never derive one
    from the other. Two mappings that look like one are two. `resize_window` belongs to the
    same family from the other end (rule 37): `resize_window(2400, 1700)` returns
    *"Successfully resized window … to 2400x1700 pixels"* and `innerWidth` stays 1259 — the
    call reported that it was made, not that it did anything.

84. **A grid does not overflow, it grows a row.** `.srch-hit` declared **five columns for
    five children** and the comment above it said so. The arithmetic was already false:
    `.srch-in` carries `grid-column: 2 / -1`, so it fills the rest of whatever row it lands
    on and **anything emitted after it starts a new one**. The keep button — the fifth
    child, added to this row in the very session that filed the debt to look at it — flowed
    onto a **third** row, into the 3.2 rem line-number column.

    Measured in a real window, `emit` over 2,403 lines in 298 files with one file open at
    126 hits:

    | | before | after |
    |---|---|---|
    | keep button | 51 × 54, *"Keep this"* wrapped to two lines | 78 × 22, one line |
    | where | row 3, column 1, under the line number | row 1, column 4, beside the marks |
    | row height | 101–108 px for one 17 px line of code | 45–53 px |

    **Nothing reported it and nothing could.** The row rendered, the button worked, and a
    control on a row of its own looks exactly like a control somebody deliberately put on a
    row of its own — design rule 16's shape, from the layout rather than from the wiring.
    CSS grid never overflows and never complains; it creates implicit rows in silence, so a
    column count written in a comment is a claim nothing checks.

    The remedy is a rule and not a number: **after a child that spans to the last column,
    every later child is placed by hand.** `grid-row: 1; grid-column: 4`, explicit, because
    auto-flow is what put it on a third row — and explicit placement of that one child is
    also what lets `.srch-in` keep its `2 / -1` and land on row 2 as written.

    The guard therefore asserts the rule rather than any symptom, and matches the button by
    its **`pinBtn(` call** rather than by a class in the markup: a child a source scan cannot
    see is exactly the child that gets forgotten when the columns are counted, and that is
    how this happened. Proved non-vacuous by reverting the placement against a real file
    backup, not against `git checkout`.

    Rule 53's neighbour, one property over. That one is a layout right at a single window
    size; this one is a layout right until a child is added, with the arithmetic that decides
    it living in two files.

85. **A span cannot tell what a loop is over from what it does.** `for row in
    conn.execute(q).fetchall():` runs **one** query, before the first pass. It is written on
    a line inside the loop's own span, so `line BETWEEN line_start AND line_end` reads it as
    a query *per* pass — and said so, about **11 of Society's 261 rates**, in the sentence
    that is the feature's headline: *"something moves inside this loop, once per pass"*
    about something that happens once.

    Not found by a test. `tests/test_shape.py` had no fixture routine with a move in its
    iterable, so every assertion passed; it was found by measuring chunk 6's detector against
    real source before building it, which is what the anomaly discipline already demands of
    a detector and turns out to be worth demanding of the fact underneath one.

    A span is a **range**, and a range says where something is written, never what evaluates
    it. So the answer has to be a fact the extractor records — `ControlPoint.once_start` and
    `once_end`, the lines a loop evaluates once — because nothing downstream can work it out
    from the span it was handed.

    **And the obvious form of that fact is wrong.** The iterable's line span alone
    reclassifies 45 loops and **34 of them wrongly**, because `[fetch(x) for x in ids]`
    writes its element and its iterable on the same line and a line cannot choose between
    them: comprehensions reaching a boundary would have read 42 → 5 rather than 42 → 39. It
    is the iterable's lines **minus every line a repeated part of the same point also
    occupies**, which leaves the range empty exactly where a line cannot say — the answer
    that cannot be wrong (rule 49). Contiguous by construction, so two ints hold it.

    **Anything derived by containment inherits this**, and the proof arrived while the fix
    was being verified: `shape.enclosing` — a reader standing at a table asking what loops
    over it — still counted a loop's own iterable, so a table's pane said *"reached from
    inside 1 loop"* about a query the loop is written over. Two of 64 tables, found by
    checking all of them against the four SQL statements rather than the one table that had
    been looked at.

    Beside it, and for rule 30's reason: **`word` is recorded, not inferred from the
    header.** `for x in y` and `while y` are one `ControlKind` and opposite facts about
    whether the header runs again, and a header of `True` is `while True` to a reader and a
    guess to a matcher.

86. **A guard can only see that a function was called, never what it returned.**
    `graphUrl` built `&minDisk=${minDiskNow()}`, and `minDiskNow()` returns `null` for *let
    the server choose*. Template interpolation spelled that as the four characters `null`,
    the server refused an unknown threshold with a 400 rather than defaulting it — correctly,
    and by design — and **every package click landed on *"Not in this map"***.

    The guard over that line asserted the builder consulted `minDiskNow()`. It did. There is
    no source check that could have caught this: the call is present, the name is right, the
    argument is spelled correctly, and the defect is entirely in a value that does not exist
    until the function runs.

    **Checked against rules 37, 42 and 44 before a number was taken**, because it is close to
    all three and none of them is it. Rule 37 is a guard that checks a *name appears* — this
    one went a rung further and confirmed the call. Rule 42 is a guard that names the right
    case and is defeated by how the callee fails. Rule 44 is a *live control* reading a field
    the server never sends, which shows up as a rendered nothing; this shows up as a correct
    request for a value that cannot exist.

    The remedy is not a better guard, because a static one cannot reach. It is to remove the
    hole: `levelQuery` is now one builder that **omits** the parameter when the threshold is
    unset, so the unrepresentable value has nowhere to be spelled. Where a source check must
    stand in, assert the *shape of the call site* — that the optional parameter is built
    conditionally — never that the function was consulted.

87. **A derivation from the picture is only as available as the picture.** A package's
    members were read from the drawn graph payload, on an argument that is correct and is
    rule 13's own: read the members from the thing on screen and they cannot disagree with
    the thing on screen.

    The argument was right and its premise was false half the time. **Table mode never mounts
    the graph**, so a package click there marked *0 of 4,786 rows* beside a pane correctly
    reporting **469** — two numbers about one package, on one screen, and the one derived
    from the picture was the wrong one.

    So rule 13 has a cost, and this is it: satisfying *"the claim and the picture agree"* by
    deriving the claim **from** the picture makes the claim exactly as conditional as the
    render. Every mode that does not draw is a mode where the derivation silently returns
    nothing, and nothing looks like zero.

    `plate.py` computes members from the same payload on the **server**, which keeps rule 13
    — one reading, one source — and moves it to the side that always has it. The test is
    *when is this input absent?* If the answer is "in some mode", the derivation belongs
    where the input is unconditional, not where it happens to be convenient.

88. **A rebuild recipe must name every store the change invalidates, including the ones
    nothing else mentions.** Rule 12 says a cached fact is only as good as the tool that
    read it. This is the other end of it: the recipe that *repairs* the staleness has to be
    as complete as the fingerprint that detects it.

    A documentation rule moved `doc_rules_fingerprint()`, so the pair had to be rebuilt —
    two analyses and a seal, exactly as `CLAUDE.md` said. What `CLAUDE.md` did not say is
    that **`standards.db` is a document store too**. It went stale with the corpus, and
    `serve` refuses to boot on a stale one: *"written by a different version of DunneFlow"*,
    before a single page is served. The rebuild ran clean, the map analysed perfectly, and
    the dashboard could not be opened.

    The trap is that the invalidated store was the one the recipe had no reason to mention.
    `--standards <dir>` is an *optional* flag naming an *outside* standard, so it reads as
    something the rebuild does not concern — and it is hashed into exactly the fingerprint
    the change moved. A store admitted through a different door is invalidated through the
    same one.

    So the test when a fingerprint moves is not *"which stores does this recipe usually
    rebuild"* but **"which stores carry this fingerprint"** — and every one of them belongs
    in the recipe, whether or not it is part of the normal flow. `CLAUDE.md`'s rebuild is
    three commands now, and the third carries `--standards`.

89. **A refusal must name a command that can act on the thing it is refusing, and the
    sentence has to be readable off whatever decides that.** Rule 13 for a remedy rather
    than for a number.

    `Store._refuse_if_stale` exists to name *which* of two fixes applies, and its reasoning
    was right: a graph written before paths went relative needs `migrate`, which rewrites in
    place and keeps a sealed snapshot whose source tree may be long gone, so telling that
    reader to re-analyse asks them to rebuild from a tree they do not have. But it decided
    from `paths_are_relative` — *when* the store was written — while the migration decides
    from `_require_previous`, which admits exactly **one** fingerprint on the claim that
    making paths relative is the only thing that changed.

    Two facts, one test. Every store older than that single version was told to run
    `dunneflow migrate`, and the migration refused it in turn. **Three of the four program
    directories in this project's own `output/` were in that state**, and it cost nothing
    at all until somebody kept an old map — at which point the reader is handed a command,
    runs it, is refused by it, and has no third thing to try.

    This is rule 49 one step on. Rule 49 is a *fallback* yielding a plausible value; this is
    a *refusal* yielding a plausible remedy, and it is worse in one way: a refusal is the
    surface a reader trusts most, because it is the one that just admitted something was
    wrong.

    The remedy is rule 51's: ask the module that owns the gate. `migration_speaks_for` lives
    beside `_require_previous`, and both refusals call it — the graph on
    `PREVIOUS_CODE_EXTRACTOR`, the document store on `PREVIOUS_DOC_EXTRACTOR`, the compared
    value being the only thing that differs. The two sentences were already copies of each
    other, which is where this kind of thing goes unnoticed twice.

90. **An instrument's pointer lands on the window in front, not on the tab you addressed —
    and every other instruction still reaches the right one.** Rule 83's family, one layer
    out: that rule is about two coordinate systems, this is about two *windows*.

    The whole of an automated browser session can be correct — the right tab id, the right
    URL, JavaScript evaluating in the right document, screenshots returning the right page —
    while the pointer goes somewhere else entirely. A screenshot is captured *from the tab*;
    a click is delivered *to the screen*. So the one instrument that proves what a reader
    can reach is the one instrument that silently stops addressing the page, and it does it
    without a single error: the tool reports `Clicked at (300, 250)` either way (rule 76 — an
    echo is not an act).

    **What it looks like from inside is a moving floor.** This session recorded, in the
    development record, that clicks below a vertical threshold were not
    arriving: pointer y=45 landed and y=40 did not, and after a reload y=88 stopped landing
    on a page where y=109 had worked twenty minutes before. That is a coherent, plausible,
    entirely fictional diagnosis — a pointer floor that happened to sit just above the
    toolbar, explaining exactly the control that could not be pressed. It was written down
    as fact and it was wrong. There is no floor. The window had gone behind another one, and
    `document.visibilityState` said `hidden` the moment anybody asked.

    So: **`document.visibilityState` before the first click, and again after anything that
    could raise another window** — a reload, a new tab, a dialog, a wait long enough for the
    reader to touch their own machine. It is one call and it is the difference between
    measuring the product and measuring the furniture.

    Two consequences worth carrying. A click delivered to the screen while the tab is hidden
    lands *somewhere* — possibly on the reader's own window, on their own session — so a
    blind retry is not free. And the mapping between pointer space and viewport space is not
    a constant to carry between sessions: measure it from a `pointerdown` probe each time
    (this session `viewport = pointer x 1.5667`, the one before it 1.7111), and re-measure a
    control's box after **every** press, because a setting that changes the layout moves the
    next control — pressing the version strip to two lines moved its own toggle 8px and the
    next click landed on the row behind it.

91. **A sentence written for a reader has to fit the channel it is put in, and a channel
    that is narrower than prose will not say so.** The refusal was correct, complete, and
    aimed at exactly the right person; it never arrived, because it was written into an HTTP
    status line.

    `send_error(409, "…")`'s second argument is the *reason phrase* — `HTTP/1.0 409 <here>` —
    and `http.server` encodes that line as **latin-1**. Every other string in this codebase
    is UTF-8 and this project writes em dashes everywhere, so the first em dash raised
    `UnicodeEncodeError` from **inside the error handler**. There is no error path out of an
    error path: the exception went to the socket-server's own logger and the connection
    closed with nothing on it at all. `curl` reports exit 52, *empty reply from server* — a
    symptom that names neither the route, the code, nor the sentence.

    That is worse than the failure the refusal was written to prevent. A route answering an
    empty payload at least answers; this looks like a server that crashed, on a page that had
    just been asked a perfectly ordinary question.

    **The remedy is one argument along**, not shorter prose: `send_error(code, message,
    explain)` puts `explain` in the *body*, which is encoded UTF-8 and is where a sentence
    belongs. The status line takes `nothing is open` and nothing more.

    The general shape is worth more than the instance, because every one of these looks like
    an ordinary string until it is not. A channel narrower than the text you are putting
    through it: an HTTP reason phrase (latin-1), a filename (no `/`, and no `:` on some
    volumes), a SQL identifier, a shell argument, an HTTP **header** value, a `data-`
    attribute a splitter will divide, an environment variable. Each is a place where a
    sentence composed for a human meets a protocol that predates it, and **none of them
    validates on the way in** — the failure is at the far end, in a frame that cannot explain
    itself.

    **No test that calls a handler directly can see any of it**, which is the other half of
    why this stood. The gate had honest unit coverage; the defect lives in the encoding of a
    line that only exists when there is a socket. So `tests/test_cold_start.py` binds a real
    port, and one of its assertions is simply that the em dash comes back —
    `assert "—" in body`. A sentence that cannot be delivered is not a sentence, and the only
    instrument that knows the difference is the wire.

92. **A defence assembled from where this run writes does not survive the run being done
    from somewhere else.** The exclusion was content-tested, argued from a measured failure
    and correct — and it evaporated the moment the output root moved out of the tree being
    read, which is precisely what installing the application does.

    Rule 57's own defect had already been paid for once: pointing DunneFlow at itself read
    46 of 54 documents out of `output/`, its own generated reports about a *different*
    program, and all 942 naming rules it then claimed came from them. The fix was
    `exclude = {out_dir} | revisions.program_dirs(out_dir.parent)` — every directory under
    the output root holding a `graph*.db`, recognised by content and never by the name
    `output`, which is right on both counts. `program_dirs` even stated its own bound
    honestly: one level down and no deeper, because a recursive search would *"cost every
    project a walk to protect against a layout nobody uses."*

    **That layout is what an installed application does.** From a checkout the output root
    is `./output`, inside the tree being read, so the set enumerates exactly the maps in the
    way and the defence holds. Frozen, `default_output_root()` is
    `~/Library/Application Support/DunneFlow`, so the same expression enumerates a directory
    in the reader's Library with no bearing on the tree at all — and a checkout's own
    `output/`, full of maps, went straight back into the corpus.

    Measured on DunneFlow's own map as the signed binary built it, 2026-09-10: **122 of 147
    documents** came out of `output/`, **122 of 122** stated naming rules were mined from
    them — every rule the map claimed was about Mensores — 655 of 680 definitions likewise,
    and the document store was **289 MB** against a 6 MB graph, 13,449 tables and 161,047
    table rows of somebody else's generated report.

    **The remedy is to ask the question of the thing being read, not of the thing being
    written.** `discover_docs` is already walking every directory of the documentation root
    and already prunes a nested checkout off `os.walk`'s own listing at no `stat` cost
    (rule 57); a map's spine is in `filenames` for the same price. `exclude` stays for the
    one thing a marker cannot answer — this run's `out_dir`, which is created before the
    documents are scanned and holds no graph until after — and the two are now two
    mechanisms with two stated reasons rather than one doing both jobs badly.

    **1,402 green tests said nothing about any of it**, and the reason is worth more than
    the fix. `tests/test_map_index.py` drives the whole of `cmd_analyze` and asserts this
    exact property — with `out = tmp_path/"out"` beside `tree = tmp_path/"src"`. Every test
    in the suite put the output root inside the analysed tree, because that is what a
    developer's arrangement looks like, so the suite proved the one shape where the defect
    cannot appear. It is rule 24's family at the level of a fixture: **a test that only ever
    constructs the developer's own arrangement has not measured the product.**

    The family this belongs to is any defence derived from the process rather than from the
    subject — a path relative to the cwd, an exclusion built from the destination, a limit
    taken from the machine doing the work. Each is correct where it was written and each
    stops being correct when the same code runs somewhere else, silently, because the
    expression still evaluates and still returns something plausible (rule 49).

93. **A stored path's separator belongs to the machine that wrote it, and that makes it a
    bad key.** Rule 60's sequel, one platform over, and the same failure: it made paths
    relative because an absolute one names one machine's directory layout, and left them
    spelled in one machine's *alphabet*. Run on Windows, `str(p.relative_to(root))` stores
    `web\\serve.py` where the same commit on macOS stores `web/serve.py` — one file, two
    unrelated keys, so the pair cannot be compared and neither build can read the other's
    map. Six modules minted a path and every one of them was correct where it was written:
    the two extractors, `entrypoints`, `version`, `walk`'s two cache keys, and
    `fingerprint_files`.

    **The costs were not theoretical and none of them looked like a path problem.** The
    conformance lane reported `files / kebab-case` as **NO_POPULATION** over 78 files it had
    quietly failed to find, because a rule's `paths:` glob is POSIX and `fnmatch` does not
    know that `web\\serve.py` is under `web/` — rule 49's shape in the surface built to
    refuse it. `PurePosixPath(p).stem` returned `web\\serve` for the same reason. The
    document corpus listed its own paths back differently from the set it had just scanned.
    And in the shell, `String(path).split("/").slice(-2)` — the leaf a reader is shown rather
    than a path (rule 60 again) — returned the whole path, so every "leaf" on every pane was
    the full thing.

    The sharpest one is `fingerprint_files`, because it inverts rule 12. The label goes into
    the hash, so the Windows build and the macOS build compute **different fingerprints from
    identical bytes** — and each would discard the other's map as *written by a different
    tool*. That is precisely the refusal `resource_root()`'s layout was shaped to prevent,
    arriving through the one thing that layout does not control. Measured after the fix: both
    stamp `9:d6179cee25581502`, and each opens the other's map.

    **The remedy is the shape rule 51 always prescribes**: one function, `schema.stored_path`,
    beside `make_id` and `call_site_id` because a stored path *is* an identity, and every
    writer passes through it. `PurePath` is deliberately the platform's own parser — on
    Windows it splits on both separators, and on POSIX it splits on neither, where a
    backslash is an ordinary character in a filename and has to survive as one. Nothing
    re-spells a path the running platform would not.

    What makes the whole family hard to see is that **the reading side was already right**.
    `conformance` reached for `PurePosixPath`, the shell split on `/`, `migrate` matched
    `LIKE '/%'`: every consumer had decided a stored path was POSIX, correctly, and said so
    in code. Only the writers had never been asked, because for as long as there was one
    platform the question had one answer.

94. **A boolean that says "the other one" stops being true when there are three.** A
    two-valued test of a set that later grows does not raise, does not warn, and does not
    read as wrong: it keeps answering, and one of its two answers has quietly become a
    third platform's. Both instances here are in `packaging/dunneflow.spec`, and neither was
    a mistake on the day it was written.

    `BUNDLE` — the macOS `.app` — was guarded by `if not _WINDOWS`, which was an exact
    statement of the truth while there were two platforms. Built on Linux it would have
    produced a directory with an `Info.plist` in it that nothing on the machine can launch,
    and **PyInstaller would have reported success**: there is no step in a spec that checks
    what a bundle is for. The same file's `ICON` read `"dunneflow.ico" if win32 else
    "dunneflow.icns"` over a guard that raises when the named file is missing, so a Linux
    build would have refused to start over the absence of a macOS icon container it would
    then never have used — rule 49 pointing the wrong way, failing on a file that is not an
    input.

    **The tell is that the negation is doing two jobs.** `not _WINDOWS` is being read as
    *"the platform this branch is for"* while it is written as *"not the platform the other
    branch is for"*, and the two are the same sentence only in a closed world of two. So the
    remedy is to name every member, once: `_MACOS`, `_WINDOWS`, `_LINUX`, each an assertion
    about itself, and every branch guarded by the one it is actually about. A fourth platform
    then arrives as an unhandled case rather than as somebody else's `else`.

    **It generalises past platforms**, which is why it is a rule and not a note in the spec.
    Any `if not X` over an enumeration — two revision kinds, two provenance tiers, two lanes —
    is a claim that the enumeration is closed, made in a place that will not be looked at
    when it opens. Rule 30's *"three verdicts, never two"* and design rule 21's *"three
    absences, three answers"* are the same argument arriving from the other side: those say
    what collapsing states costs a reader, and this says what it costs the next branch.

    Caught by neither gate and by no test: `mypy --platform linux` type-checks a `BUNDLE`
    call perfectly, and the suite proves the source tree rather than the artifact. It was
    found by reading the spec before building with it, and pinned afterwards —
    `tests/test_frozen.py` now reads the guard *and its definition*, because asserting on a
    name alone would pass a `_MACOS` redefined to mean anything (rule 37).

95. **A cache key assembled from a directory does not cover what that directory imports.**
    `rules_fingerprint()` is rule 12's enforcement: a cached fact is valid only if the
    source *and the tool that read it* are unchanged, so `code_extraction_inputs()` names
    the rules, the loader, and the reader —
    `(_PKG_ROOT / "extractors" / "python").rglob("*.py")`. That glob is an exact statement
    of *where the reader lives* and it is not a statement of *what the reader reads*, and
    those stopped being the same thing the first time a module outside that tree shaped a
    stored fact.

    **The whole of the reader's reach is three imports, and two of them are outside the
    key.** `extractors/python/extract.py` reaches out of its own tree for exactly
    `detectors` (in the key, and the reason the key exists), `schema`, and `sql`.
    `sql.parse` classifies every SQL statement the extractor finds in the program being
    read — its direction, its operation, and the tables it names — so `sql.py` shapes all
    1,055 of Society's `sql_ops` rows, all 43 `db_tables` and all 73 `db_indexes`. Edit one
    entry in its `_OP_DIRECTION` table and every cached graph on the machine keeps its old
    answer, reports it as current, and is *not* discarded, because the fingerprint it is
    checked against did not move. That is rule 12's failure mode reached through rule 12's
    own defence.

    **It is silent in the direction that matters.** A key that moves when it should not
    costs a re-extraction and announces itself; a key that fails to move when it should
    costs nothing, says nothing, and leaves two graphs on one machine disagreeing about
    what a program does with its database. Nobody looks, because the cache is working
    exactly as designed.

    `schema.py` is the second gap and was already known — v2's design plan (§1f) puts it in the
    key — but it was named for a different reason, that `SCHEMA_VERSION` is bumped by hand
    and a forgotten bump is the same failure. `sql.py` was named by nobody, and the
    difference is instructive: the module whose *absence* from a list is hardest to notice
    is the one no document ever had a reason to mention.

    **The remedy is not a longer list.** A hand-kept list drifts the moment somebody adds a
    file — `code_extraction_inputs`' own docstring says so, which is why it globs at all.
    What the key needs is the reader's *imports*, resolved: the tree, plus every module
    inside this package that the tree reaches. Until that exists the honest form is the
    glob plus the named few, and the test that asserts membership must assert the named few
    too, or it proves only that the glob still globs (rule 37).

    *Not to be confused with `canonical/`, which is outside the key deliberately and
    correctly.* Its docstring sets the right test — **what does this extraction actually
    read** — and a canonicaliser is not read by extraction at all: it decides whether two
    stored expressions are the same expression, afterwards, and cannot change one fact.
    `sql.py` fails that test, which is how it was found. The test was never wrong; nobody
    had applied it to this module.

    *The `sql.py` instance was shut on 2026-09-17 by v2's chunk 6*, which put it in
    `core_extraction_inputs()` — core rather than Python's, because judging a string
    literal is the host's job by design. **The rule stands unchanged**: what was fixed is
    one named module, by the interim form this body already describes, and the key still
    knows where the reader lives rather than what it reads. The next module to reach out
    of `extractors/python/` will be in no key either, and nothing will say so.

96. **A record minted on demand exists because somebody asked, so a new question invents
    records.**
    `_Extractor._owner()` returns the routine that encloses, and at module level it *mints*
    a synthetic `<module>` routine and appends it. So the rule the map actually held —
    **the module scope is a routine only where something belongs to it** — was true by
    accident rather than by statement: whichever fact asked first did the minting, and a
    file with nothing at module level got none because nothing had asked.

    Chunk 8 asked a new question. A string literal has to name its owner *before* anybody
    knows whether it is a fact — what a string means is the host's answer now, and the
    reader reports it either way — so `_owner()` was called for every module-level string
    in the corpus. **65 of Society's 628 files gained a `<module>` routine owning nothing
    at all**: no SQL operation, no artefact, no call, no comment. A 1.3% inflation of every
    routine count, every dead-code number and every naming population in the map, and the
    thing deciding it was `LITERAL_MIN` — a bound whose entire purpose is to save bytes on
    a pipe.

    **It was invisible to every check except identity.** The change touches no routine, so
    nothing about it suggested reading the routine table; the tests were green; the map
    opened and looked right. It was caught by `routines.id` and `routines.body` moving in
    the golden — which is why that gate is a digest of the sorted ids and not a count
    (a total can hold while its contents swap), and why it is run on a change that has no
    business moving it.

    **The remedy is to separate preparing from claiming, and to state the rule the accident
    was keeping.** `module_scope()` builds the row and appends nothing; `_owner()` claims
    it, as every fact-recording caller always did; `_owner_id()` names it without claiming,
    because `make_id` is derived from names and needs no row to exist. The host claims it
    if and only if one of those strings turned out to be a fact — `ingest.literals`, the
    one place that knows.

    **The general shape, which is what makes this a rule rather than a fix.** Lazy
    construction ties a record's *existence* to the set of questions the code happens to
    ask. That is stable only while the questions are, and a seam exists to let new askers
    arrive — a second language, a second surface, a host that wants a fact the reader used
    to keep to itself. Ask *who owns this* without deciding *that this is owned*, or the
    answer creates the owner.

97. **A bundled program does not carry the files it reads, and it answers anyway.**
    The TypeScript plugin is a pnpm package bundled by esbuild into one committed
    `main.bundle.cjs` with the compiler inlined — which is the right shape and is what
    makes rule 12's per-language stamp a claim about bytes somebody can point at. Bundling
    moved every line of TypeScript's *code* into the file. It moved none of `lib.es5.d.ts`,
    `lib.dom.d.ts` or the other ninety-seven `lib*.d.ts` files the compiler opens **by
    path** at run time, off `__dirname` — which after bundling is the plugin's own
    directory, where no such file exists and none ever will.

    **The compiler does not refuse.** It builds a program with no `Array`, no `Promise`, no
    `Map`, no DOM; every value typed through one of them becomes `any`; and it answers
    every question it is asked. Measured on `../DunneNote`, 5,119 call sites, with the
    libraries and without: **1,935 edges against 1,931**. Four. The map is the same map. A
    check on the number of edges — which is the number the chunk existed to produce — would
    have passed.

    What moved was the **account**: 2,868 calls resolved to somewhere outside the map and
    187 could not be resolved at all, against 472 and 2,587 without. So the run's own
    sentence went from *the reader could not name the far end of half this program's calls*
    to *those calls go to `Math`, `JSON`, `Set` and the DOM — external, and right*. The
    first reads as a reader that mostly does not work and the second as a program that uses
    its platform, and only one of them is true.

    **It was found by splitting a residue into its two reasons, not by a test.** Chunk 10
    reported one number for *could not name the far end*, and 2,587 of 5,119 was too large
    to leave alone; separating *the checker said, and the answer is not here* from *the
    checker could not say* is what made the missing library visible at all. Design rule 21
    paying for itself one process away from where it was written.

    The remedy is `src/libs.ts` and `build.mjs`' `tsLibs` plugin: the ninety-nine files are
    read at bundle time and carried as data, 3.0 MB, and the compiler host serves them from
    memory under a sentinel path that is on no disk. A build with no `node_modules` refuses
    rather than bundling an empty map, and `Session.open` says so in its diagnostics if one
    ever arrives — because the one thing this defect proves is that nothing else would.

    **The general shape.** A dependency that reads *code* is carried by bundling it. A
    dependency that reads *files* — a grammar, a schema, a locale table, a standard library
    — is not, and the failure is silent by construction: the code that would have reported
    a missing file is the code that was written to work without it. Ask of anything
    inlined: what does it open, and where does it think it is?

98. **A detector's population is whatever the map holds, so admitting a new kind of fact
    re-runs every detector against something it has never seen.**
    `anomalies._entrypoint_problems` had been correct for a year. Its rule — *a way in
    with no routine and no parent leads nowhere* — was exactly right while the only
    declared ways in were Python console scripts, because one of those that reached no
    routine really was a broken `[project.scripts]` entry.

    Chunk 12 taught the tool to read a `package.json` `bin`, a Cargo `[[bin]]` and a
    SwiftPM `.executable`, and the same detector, unchanged, began reporting DunneNote's
    `dunnenote-host` as *leads nowhere*. It is the front door of that application. What
    leads nowhere is DunneFlow: there is no Rust reader, so the binary's `src/main.rs` is
    in no map. The finding was about this tool and was filed against somebody else's
    program — which is `anomalies.py`'s founding discipline, *six confident findings in a
    row were defects in this tool*, arriving through a feature rather than through a
    detector.

    **It happened twice in two chunks.** Chunk 11 admitted `.d.ts` files as program source
    and `MISSING_BODY` turned uigen's vendored Prisma client into **83 BROKEN** out of a
    command that gates CI on BROKEN. Same shape, different detector: a population widened
    in one place, a judgement written against the old one somewhere else.

    And it was not finished by the first fix. Suppressing the unreadable languages left
    `@dunnenote/api-types` still reported, over 289 lines of `export type { X } from './X'`
    — a file that is in the map, was read, and declares no routine because there is
    nothing to declare. **Five answers, and only one of them is a fault**
    (`resolve/entrypoints.binding_note`): the declaration names no file at all; no reader
    claims the suffix; the language is one this map holds none of; the file is read and
    declares nothing; the file is not there. Only the last is worth a reader's attention.

    The remedy is not a longer suppression list. It is to ask, of every feature that
    widens what a map can hold: **which existing judgement now has a population it was
    never shown?** `dunneflow check` gates CI on BROKEN, so the cost of getting that wrong
    is somebody else's build.

99. **A name is relative to the root that declared it, and a nested manifest's root is not
    the analysed tree's.**
    `../beads-main/integrations/beads-mcp/pyproject.toml` declares
    `beads-mcp = "beads_mcp.server:main"`. That module is real, it is in the tree, and it
    is stored as `integrations.beads-mcp.src.beads_mcp.server`, because a module name in
    this map is derived from the directory somebody pointed `analyze` at. An exact match
    answers *no*, and the map then says a real front door leads nowhere.

    This is rule 64's family — *the leaf that identifies a tree is the package root's, not
    the analysed directory's* — one level down and one direction over. There, one root was
    the wrong root; here there are **several**, one per manifest, and the analysed tree is
    none of them.

    The fix is bounded rather than clever: the exact name first, then a **dotted-suffix**
    match, taken only when exactly one routine has it. That is not rule 5's forbidden bare
    name — `beads_mcp.server` is a dotted path matched at a segment edge — and the
    uniqueness test is `_resolve_routine`'s own remedy sitting beside it. Two copies of a
    package in one monorepo leave the declaration unbound **and saying so**, which is the
    right answer rather than a coin toss.

100. **A judge that must pick one of several true answers picks by the order it was
     written in, and that order is the first language's preference.**
     `case_style` answers *which spelling convention does this name follow* with one
     string, and for a one-token name several answers are true at once: `widget` is
     snake_case, camelCase **and** kebab-case, and `DDL` is SCREAMING_SNAKE and PascalCase.
     Its own docstring said the ambiguity was real and that a one-word name is *"counted
     with the majority"*. It was not. It was counted with whichever of five `if`s came
     first, and that order was written when Python was the only language this tool could
     read — so the tie went to Python's preference in every corpus, for ever, and nothing
     recorded that a choice was being made at all.

     What it cost, measured on corpora that were sitting in `output/` the whole time:

     * **DunneNote's routines** read *camelCase, 1,151 of 1,348* with **197 exceptions**.
       146 of those are single lowercase words obeying the convention perfectly. The
       figure is 1,297.
     * **DunneNote's parameters** were reported as a **gap** — *no dominant convention* —
       in a program where 515 of 519 are camelCase. 335 one-word names had been counted
       as snake_case, which is not a smaller number than 182: it is a different answer.
     * **DunneFlow's own commands** read *snake_case, 14 of 16*, naming `ingest-conform`
       and `ingest-schema` as the exceptions. They are the two names that settle what the
       convention is; the answer is kebab-case, 16 of 16.

     **A predicate written beside such a judge inherits its blind spot silently.**
     `STYLE_PREDICATE["kebab-case"]` required a dash, which is right for the question
     *"is this name kebab-case rather than one of the others"* and wrong for *"is this
     name kebab-case"*. It returned 14 rows to prove a claim of 16 of 16 — rule 13
     broken by a predicate nobody had ever been able to run, because until a corpus spelled
     its names that way no population had ever resolved to kebab.

     The remedy is not a better tie-break. It is to stop returning one answer where several
     are true: `styles_of` returns **the set**, `resolve_styles` lets the population's own
     unambiguous names decide which of them its author meant, and where a population offers
     no unambiguous name at all the fallback order is **named in the source and stated on
     the claim** — so the tool can say *the count is right and the name of the convention
     is mine*.

     This is rule 98 arriving through a function rather than through a detector: admitting
     a new language re-ran a judgement against a population it had never been shown. The
     tell is different, though, and worth carrying: rule 98's defect appeared the moment a
     new fact arrived. **This one was already wrong on a single-language TypeScript map
     and had been for two chunks**, because nobody had asked the old question of the new
     corpus. A judge with a hidden preference does not announce itself when the second
     language arrives; it announces itself when somebody finally reads its output.

101. **A route is not a branch, and a probe that asks one query string per route says
     nothing about the others.**
     `tools/ordering.py --api` asks every route of two copies of one program, one with
     every row reversed, and reported `/api/wayin` identical — over a `_mount_name` that
     returns `ledger` in one row order and `books` in the other, which `BACKLOG.md` had
     already called the certain one of nine. Both statements were true. The route has two
     shapes: without `inside` it describes the way in, and only **with** it does it ask
     what name a sub-application is mounted under. The probe only ever sent the first.

     This is rule 37 at the next level down. That rule is about a guard that checks a name
     appears without checking anything happens; this is about an instrument that exercises
     a *door* and reports on the *rooms*. The coverage a route-level probe gives is
     coverage of route-level answers, and the arithmetic is unforgiving: 43 routes against
     however many query strings a reader can type.

     Three remedies, and all three were needed. A route with more than one shape is asked
     **more than once** — `/api/search` with and without a path, `/api/diagram` with and
     without an id, `/api/wayin` with and without `inside`. A parameter that came back
     **empty** is a gap in the plan and is named, because `/api/table?name=` is a refusal
     that is identical on both copies and diffs perfectly clean. And a route that **raised**
     is named too, for the same reason: it raises the same way twice.

     What is left is stated rather than claimed away: the fixture reaches what it reaches,
     and `web/queries.py` says in as many words which of its orders a probe could make
     move and which are defence in depth.

102. **A list with no order comes back rearranged; a *sentence* about that order comes
     back wrong.**
     `anomalies.py` reported *"`twin` is defined 2 times in `alpha.work` (lines 23,18).
     The later definition shadows the earlier."* The lines came from `GROUP_CONCAT`, which
     has no defined order, and the sentence beside them is a claim **about** the order. So
     this is not the usual cost of an undefended order — a reader shrugging at a list that
     moved — it is a finding that names the wrong definition as the live one, in the
     detector whose whole discipline is that every finding states what would make it a
     false alarm.

     Rule 66 says an order the tool cannot defend is not an order. This says what the bill
     is when the order is load-bearing in prose: the same defect, one severity higher, and
     invisible to a reader who has no second row order to compare against.

     The fix is not `GROUP_CONCAT(x ORDER BY y)`, which needs SQLite 3.44 and would make
     the sentence depend on a version. It is to build the sentence from **the rows the
     finding already opens** — `_at_lines(members)` over `_routine_rows`' own order — so
     the claim and the occurrences beneath it are the same rows in the same order
     (rule 13), and there is one place where that order is decided.

103. **A path is not a key until it is canonical, and a set cannot deduplicate what does
     not compare equal.**
     `_r_programs` builds the toolbar's program list by unioning the directory being
     served — `out_dir.resolve()`, resolved since the day it was written — with
     `revisions.program_dirs(out_root)`, which resolved nothing. Under a maps root reached
     through a symlink those are two unequal `Path` objects naming one directory, so the
     open program appeared **twice** in the `<select>`, and the copy that was not marked as
     the one being read was the one the listing supplied. Measured: `['alpha', 'alpha',
     'beta']`.

     `/tmp` and `/var/folders` are both symlinks on macOS, so this is not an exotic shape —
     it is what any caller whose maps root is a temporary directory is already standing on,
     and `tools/ordering.py` met it on its first run and worked around it by resolving its
     own paths.

     Rule 60 is the same argument about an absolute path and rule 93 about a separator, and
     this completes the family: **the writer of a key decides nothing about it; the
     comparison does.** A path can be relative, POSIX-separated and still name one directory
     two ways. What makes the three one rule is that in every case the value is right, the
     directory is right, and only the *equality* is wrong — which is invisible until two
     spellings meet in one set.

     The fix is the same shape as the other two: one place canonicalises, and it is the
     place that answers the question rather than any of the places that ask it (rule 51).
     `program_dirs` resolves its root before it lists; the **root is canonicalised and the
     children are not**, deliberately, because `resolve()` on a child that is itself a
     symlink would name a program somewhere outside the root that is listing it. And the
     five callers that excluded the root with `if d != out_root` moved to `programs_under`,
     because an exclusion compared against an unresolved root is false for exactly the
     directory it excludes — the same defect, wearing the other face.

     **The workaround came out with the defect.** The probe that found this resolved its own
     temporary directory to get past it; a probe that canonicalises its own root can never
     see this class of defect return (rule 43), so it now runs on the symlinked root it is
     handed.

104. **A slot claimed before the thing that holds it exists is free for as long as it takes
     to create that thing.**
     `_Live.analysis_running` asked `analysis_proc.poll()` and nothing else — deliberately,
     and for a good reason: `state == "working"` is a label and a label outlives the thing
     it names, so a watcher that died without noting would hold the slot for the life of the
     server (rule 30). The answer to that was to ask the child. The child does not exist
     yet.

     Between `claim_analysis` returning `True` and `on_start` handing the process over there
     is a thread start and a `Popen`, and through that window a second claim succeeded.
     Measured in three lines and no timing at all: two `claim_analysis` calls in a row both
     return `True`. What follows is worse than a duplicated report. The loser overwrites the
     report; then *its* `on_start` overwrites `analysis_proc`, so the first child is
     unreachable — `analysis_stop` cannot signal it, nothing will ever poll it — and it goes
     on writing into the same output root as the run that displaced it. One slot, two
     analyses, one of them invisible.

     **Neither question alone is enough, and that is rule 36 arriving from the other end.**
     *Is the slot claimed* is the only thing true from the instant somebody takes it; *has
     the child exited* is the only thing that clears a claim whose watcher died. The
     conjunction is not a superset of either.

     What makes the claim safe to trust is **what releases it**: not a caller saying it is
     finished, but the watching thread *ending*, in a `finally` it cannot skip. That is the
     distinction rule 30 actually draws — a label is set by somebody describing the work, a
     claim is given back by the work stopping — and it is why the release had to move into
     the one function that also takes the claim and starts the thread. It was two functions
     doing all three, in `web/serve.py` and in `mcp/session.py`, so whatever either did
     about a claim that never became a child it had to do twice (rule 51).

     Found while making a flaky test deterministic. The test's stated hypothesis was that
     the first analysis simply finished before the second was asked for; that is possible
     and was never established, and this window is a second mechanism that was there all
     along and reachable by both surfaces.

105. **An order taken over a set is the hash seed's, and a row-reversal probe cannot see
     it.**
     `tools/ordering.py` reverses every row of every table and asks whether the answer
     changed. That is the worst case for row order and it is the same every time, which is
     what makes it a usable gate — and it says nothing whatever about a list whose order
     was never row order in the first place.

     Four of `web/changes.py`'s lists are sorted in Python over a **set**: `both =
     here_d.keys() & there_d.keys()`, and the two subtractions beside it. `sorted` is
     stable, so rows equal on the key keep the order they arrived in, and the order they
     arrived in is CPython's set iteration — which for strings is decided by
     `PYTHONHASHSEED` and is therefore different in every process. Measured over 20 seeds
     against the unfixed sort: two structures tied on `(module, name)` came back one way
     **12 times and the other way 8**, while the reversal probe reported the route clean on
     every one of them.

     So a route can be reversal-clean and still hand two readers different pages, and a
     third reader a third page after a restart. That is rule 66's own failure — an order the
     tool cannot defend — arriving through a door the instrument built for rule 66 does not
     open.

     **The fix is not a better probe.** A total key is what removes the dependence on the
     input's order altogether, whatever that order was: `_settle` closes on the row's `id`,
     so there is no equal pair left for stability to decide. The probe stays exactly as
     useful as it was for the half it can see, and the half it cannot see is stated in a
     test that presses the property rather than the instrument.

     The same shape is waiting anywhere a `sorted()` is handed a `set`, a `dict.keys()`
     intersection or a `frozenset` and given a key that does not separate every member —
     and none of it is visible to a probe that shuffles storage.

106. **An identity assembled from names alone is only unique inside one language's
     naming.**
     A tree holding `probe.py` and `probe.ts` side by side could not be analysed at all:

         sqlite3.IntegrityError: UNIQUE constraint failed: routines.id

     Every reader derives a module name from the path with the suffix dropped, so both
     files were module `probe`, both declared `main`, and `make_id("probe.main")` is one id
     in two languages. The store is the only thing that noticed, and what it could say was
     that a constraint failed.

     **It is older than the language that found it.** Python and TypeScript had both been
     here since chunk 9; no corpus happened to put two same-stemmed files of different
     languages in one directory, because DunneNote and DunneCorp are TypeScript-shaped and
     Society is Python. It surfaced while building the C++ reader's probe tree, and the C++
     reader was immune by accident of a different fix — it puts the file in every identity,
     because a C++ routine is a body and a body is in exactly one file. The remedy was
     already written, in one of the four readers, for another reason.

     **The discriminator is the file and not the language**, and the difference is the whole
     of the rule. A `lang` part looks like the direct answer and closes only the case that
     was reported: `probe.ts` and `probe.tsx` are one module in **one** reader, and would
     collide exactly as before. A file is the smaller claim and the true one — a definition
     is written down somewhere, once — so `schema.definition_id` is `(file, qualname[,
     ordinal])` and `entrypoint_id` carries the file too.

     **A file is not a position** (`make_id`). Where a definition lives survives everything
     moving inside it; the line it sits on does not. Moving a routine between files reads as
     a removal and an addition, which is what a rename already gets and for the same reason:
     nothing in the source says the two are the same thing. What is in the id is the path
     *inside the analysed tree*, never the one on this machine, or two checkouts of one
     program would pair with nothing (rule 60).

     **The cost was the point, and it was taken deliberately.** `make_id` is what every
     stored map on every machine is keyed on, so this discards all of them, sealed snapshots
     included (rules 25 and 62). What made it checkable is that a digest cannot tell a
     re-keying from a change of facts — every digest is taken *over* the thing that moved.
     `tools/golden.py --rekeyed` projects each table onto its facts and none of its ids, and
     against the preserved v1 graph all six projections are byte-identical while all five
     identity digests move. That pair of results is the evidence, and neither half says it
     alone.

     **And it moved a detector that had never been shown this population** (rule 98, the
     fifth time). `NAME_COLLISION` and `REDEFINITION` group by qualname across every
     language whose rules say a later definition shadows an earlier one — which was
     unobservable while a tree like this could not be analysed. The first map ever made of
     one reported `probe.main is defined 2 times` at BROKEN, out of the command a CI job
     exits non-zero on, about two routines in two files in two languages. Both detectors
     group by language now, which is what the comment above `_shadowing_langs` had said the
     scope was since the day it was written.

107. **A burst must end, and a transaction is not a bound.**
     `analyze_tree` wrapped a language's entire write loop in one transaction — *"one
     transaction per reader; per-file commits dominate otherwise"* — and that sentence was
     measured, correct, and silent about the case it could not cover. **SQLite cannot
     checkpoint a write-ahead log while a write transaction is open.** So the log grows for
     as long as the burst does, and the moment it outgrows `cache_size` every index insert
     starts reading pages back out of it. That is not a slowdown, it is a different cost
     curve, and it arrives without a symptom until it is already unusable.

     Analysing the whole of `UnrealEngine-release` — 84,159 C++ files in one transaction —
     the log reached **734 MB** and the process **0.1% CPU**, down from 98%, after 1 h 45 m.
     Sampled there: `sqlite3BtreeIndexMoveto` → `sqlite3PagerGet` → `sqlite3WalReadFrame`,
     with `sqlite3PcacheFetchStress` spilling dirty pages continuously.

     **The same work, bounded and not**, on `Engine/Source/Runtime` — 18,191 files, the
     largest tree this tool had read end to end:

         bounded     700 s, log held at 136 MB, 62 drains
         unbounded   stopped at 29 minutes, log 533 MB, still going

     **And the second column of that table is worth more than the first.** At the ten-minute
     mark the bounded run had **committed 17,664 of 18,191 files** and the unbounded one had
     committed **none** — one transaction means a run killed at 28 minutes has nothing
     whatever to show for it, and the file cache cannot resume what was never written. The
     bound did not only make it faster; it made it *interruptible*, which is the property
     rule 80 is about and which no amount of speed substitutes for.

     It costs nothing where it is not needed — 3,169 files, 12.9 s bounded against 13.0 s —
     so the old sentence stays true and is now true of a bounded thing.

     **The general shape.** Any accumulator with no ceiling is a bound nobody set: a
     transaction, a batch, a buffer, a list a loop appends to. "One per X" is a *grouping*
     and reads like a limit, and the two are only the same while X is small. The question to
     ask of one is not *how many groups* but *how large can a group get*, and the answer has
     to come from the thing that has to hold it — here, `cache_size`, two lines further up
     the same file.

108. **A walk up the tree does not know when it has left it, and it answers anyway.**
     `find_package_root` climbs from the analysed directory through its ancestors looking
     for any of six manifest filenames, and stops at the first that matches. Rule 64 is why
     it climbs at all — `.../society-2026-08-26/src` really does belong to the
     `pyproject.toml` one level up, and the leaf that identifies a tree is the package
     root's and not the analysed directory's. What it had no answer for is **where to
     stop**, and `(target, *target.parents)` ends at `/`.

     Found by analysing one part of Unreal with the phase timings that had just been built
     for `BACKLOG.md` item 9. `Engine/Source/ThirdParty` is 620 files of code; the run took
     **265 s**, of which **205 s — 77.5% — was documents**. The climb had gone **four levels
     above the tree** into the Developer directory, which is not a project and is not
     anybody's program, and which happens to hold a stray `package.json`. So `pkg_root` was
     the whole of that directory, and `analyze_docs_tree` read **every project on the
     machine**.

     **What it put on disk.** Every one of the 85 Unreal part maps holds the same
     **15,497 documents, 2,607 of them from programs that are not Unreal** — `AgentUX`,
     `beads-main`, `knowledge-catalog-main`, `usdview`. A document is evidence (design rule
     11), so the glossary, the naming standard, the mirror and traceability were each
     measured over a corpus that was partly somebody else's vocabulary, in 85 maps, none of
     which said anything was wrong. At roughly 205 s a part over 85 parts that is most of a
     327-minute run, and a 107 MB document store per part of which the great majority is the
     same foreign corpus copied 85 times.

     **And it took rule 64's own subject with it.** `tree_leaf = pkg_root.name` is the leaf
     that identifies a tree, and every one of those maps records its tree as
     **`Developer`** -- the name of the directory that holds every project on this machine.
     Rule 64 exists because `.../society-2026-08-26/src` identifies itself as `src`, which
     names every src-layout program ever analysed and so identifies none of them; the
     remedy was to ask the package root instead, and here the package root was four levels
     outside the program. A rule that fixes an identity by delegating it inherits whatever
     the delegate gets wrong.

     `analyze --part-of <tree>` is the ceiling: a part of a tree cannot belong to a package
     above that tree, which is what being a part *means*. Where the ceiling is reached and
     nothing has declared anything, the part is its own package root — the same answer a
     bare directory of source already gets, arrived at honestly rather than by carrying on
     until something unrelated matched (rule 49).

     **The general shape, and it is rule 107's one subject over.** An accumulator with no
     ceiling is a bound nobody set; a **search** with no ceiling is a stopping condition
     nobody set, and it is worse in one specific way — an unbounded accumulator eventually
     becomes slow, and an unbounded search *succeeds*. It returns a confident answer of
     exactly the right type, and every consumer downstream treats it as the answer to the
     question they asked. The question to ask of a climb is not *what am I looking for* but
     *what would it mean to have gone too far*, and if there is no answer to the second then
     the first has no bound on how wrong it can be. The unbounded climb is still there for
     an `analyze` with no `--part-of`, because nothing in those arguments says where to
     stop and inventing a stopping condition would be a rule with no evidence behind it —
     stated in `BACKLOG.md` rather than guessed at.

109. **A folder of pages is an artefact too, and it is finished only once it has been renamed
     into place.** Rule 80 taught the graph to say it was unfinished, and it did: the render
     of Unreal's `Engine/Source/Runtime` crashed in `02-flows.md` on SQLite's parameter limit,
     and the graph beside it was correctly marked `complete = ""`. The **map** was not
     marked at all. `render_all` wrote straight into `map@<rev>/`, so the crash left a folder
     with the finished map's name, a cover page vouching for it, `01-entrypoints.md`, and
     thirteen pages missing — and `revisions.known_maps` counted that folder as a map. So
     `mapless` did not offer the revision, and `dunneflow render`, the one command that could
     have written it again, answered *every revision in this directory already has a map*.

     **The marker cannot be inside the thing it marks.** A page the map writes to say "not
     finished yet" is a page the map has to remember to delete, and a reader opening the
     folder sees thirteen pages before they see one note. The name is the one fact a listing
     reads without opening anything, so the name is where the state goes: pages are written
     into `map@<rev>.unfinished/`, which nothing counts, and become `map@<rev>/` in one
     `os.replace` after the last page. A rewrite stages too, because rewriting in place and
     dying leaves new pages over old ones — two maps' halves under one name. The folder still
     carries `UNFINISHED.md`, rewritten before every page, so a person who opens it is told
     which page it stopped on and the command that writes it again (rule 89).

     **And skipping it by name had a trap of its own.** `revision_of` takes `Path.stem`,
     which reads `.unfinished` as a suffix and strips it — so the staging folder claims
     exactly the revision of the finished one, and a listing keyed by revision would have let
     whichever sorted last win. The suffix is removed deliberately before the revision is
     read, and the two sets are kept apart.

     **Whether an unfinished map may be read at all is the reader's choice** — Tom,
     2026-11-03: strictness is a Setting. *Unfinished maps: refuse / open with a warning*,
     default refuse, governs every reader that refused one: the dashboard's open and switch
     (`unfinished=` on the request, one key for the machine because a refused program
     cannot be opened to change its own setting), `serve` and `mcp` (`--allow-unfinished`),
     and the orientation commands through `_open_store`. Opened anyway, the same sentence
     the refusal would have said is printed as a warning — above the view, in the version
     strip, naming the step it stopped in. The map folder is not governed by it: a
     half-written folder is never linked as a map, only its note is.

     **The general shape.** A completion marker protects the artefact it is written into and
     nothing else. Anything a run produces in more than one write — a folder, a set of
     files, an export — is a second artefact with the same failure, and it needs either its
     own marker or an atomic step into the name readers look for.
