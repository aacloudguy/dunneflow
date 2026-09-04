# DunneFlow — rules learned the hard way

The engineering rules, in full. `CLAUDE.md` carries the numbered index; this file carries
the evidence, and the evidence is the point — each rule is the shortest true statement of
a false result that real code produced, and the body says what produced it.

**Read a rule's body before working in the area it governs.** The title alone will let you
agree with a rule and still reimplement the defect it was written from: every one of these
was, at the time, the obvious thing to do.

Cited as bare numbers — "rule 45" — from code comments, tests, `HANDOFF.md` and
`BRIEFING.md`; 768 such citations across `src/` and `tests/`. The numbers are therefore
**addresses**, never an ordering, and are never reused or closed up.


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
