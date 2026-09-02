# DunneFlow — dashboard design rules

The dashboard's design rules, in full. `CLAUDE.md` carries the numbered index; this file
carries the reasoning, and several of these rules exist only as reasoning — what was tried,
what it cost, and why the obvious alternative was rejected.

**Read a rule's body before building against it.** Cited as "design rule N", which is a
different address space from the engineering rules in `RULES.md`: there is no engineering
rule 21, and every "design rule 21" in the codebase refers to the one below.


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

   **Shape is the channel that was going spare, and the diagram spends it on kind.** Five
   kinds, five silhouettes, in Mermaid's own vocabulary — a process box for a routine, a
   hexagon for a constant, a stadium for a boundary — which is what frees colour to go on
   saying *what changed*. Offered as a **set** rather than as a shape per kind, on exactly the
   argument rule 69 makes about colour sets: choosing them one at a time lets two kinds land
   on one outline, which is the channel saying nothing, and a sixth kind then arrives with no
   shape at all. Unlike a colour set there is nothing to measure — a shape has no contrast
   ratio and no separation — so the sets are offered because they read, not because they
   cleared a bar, and the Settings page says so rather than implying a rigour it does not
   have.

5. **Confidence is shape, not colour.** Solid edge = CERTAIN, dashed = INFERRED, plus a
   global "hide inferred" toggle so the defensible skeleton can be read alone. Severity
   and confidence stay separate channels, exactly as in `anomalies.py`.

6. **Customisation is clamped, and says why.** Settings may change colour and size within
   limits that keep text legible — 4.5:1 for body text, 3:1 for large text and chrome,
   computed live and shown beside the swatch. A refusal states its reason, the same way a
   finding states its blind spot.

   **Colour is offered as broad sets, not as a picker per token** — Tom's call, and his
   reason is that colour decisions are personal. A set covers the channels where colour
   separates one *meaning* from another and carries a light and a dark variant; the reader
   chooses between sets rather than mixing their own, so every combination that can be
   reached is one that has been measured. What each set states is its contrast **and** its
   separation (rule 69), because a set that clears the first bar and fails the second is
   the shipped palette's own history.

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

    **The dots stay tiny; what changes is how many there are.** Tom drove it and said the
    picture was hard to comprehend at 10,015 nodes and 14,254 edges, and the answer was
    neither bigger nodes nor fewer of them but a second **level of detail**: `module` folds
    each file into one node and each boundary kind into one, giving 578 and 1,505. This
    rule's own reasoning is what forces that — if a node cannot be made big enough to read
    without fusing the picture, the number of nodes is what is wrong. Both levels are
    served side by side and the reader chooses; nothing is dropped at either.

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

    **A fifth control joined them and it is not an axis: plate width, by what a plate
    holds.** The three axes widen every plate together; this says how much of that width
    each plate has earned, at `sqrt(n / n_largest)` on **real nodes** — a shadow is never
    drawn (rule 23), so the density a reader sees is nodes over area however many placement
    devices share the disc. It is a *strength* between the uniform stack (0) and area
    proportional to content (1), interpolated so that 0 comes home to exactly the
    arrangement the server placed, and it is **per level** for the same reason `MIN_DISK`
    is: Mensores spans 12.85x across its routine plates and 5.32x across its module ones,
    which is a different judgment about a different picture.

    Two things fall out that are worth keeping. **Where a proportional scale is anchored is
    a zoom, not a decision** — marks are drawn in pixels and fit frames whatever it is
    handed, so anchoring at the largest plate and at the smallest are the same picture at
    different zooms, and the first is chosen only because nothing then grows past the
    radius the server placed it at. Measured: the bounding cylinder is **999.8 x 3391.5 at
    both ends of the dial**, so design rule 20's framing is untouched. And **everything that
    sits on a plate's circle has to ask that plate how wide it is** — the nodes, the plate's
    own outline, and the you-are-here arrow standing on its rim were three expressions built
    from one constant, which is correct at one width and a lie at any other (rule 51).

    **The plate as a diagram, and the billboard question is settled at one angle only.**
    Rule 22 billboards a node because a sphere has *no orientation*, so a picture of one must
    not have one either. A labelled box is the opposite case — it has a top and a reading
    direction — so one held facing the camera has stopped lying on the plate it belongs to,
    and the boxes are built flat. Built flat and then **looked at**, which is what settled it:
    the tilt costs nothing a reader notices (a label loses 43% of its height at 35° and stays
    perfectly readable), and the **orbit** costs everything — text lying in the plate inherits
    the in-plane rotation, so looking straight down at a plate gives a page of names on a
    diagonal. So a box gives up its bearing and nothing else: turned about **Z alone**, it
    still lies flat, still foreshortens with the tilt, and its reading direction faces the
    reader at every orbit angle. At orbit zero it is identical to leaving it alone, which is
    the test that it takes nothing away.

    Sized in **pixels**, like the dots and the labels, which is what makes the overflow answer
    work: boxes are placed busiest-first and only where they do not overlap at the current
    zoom, everything else stays a dot (rule 19 — nothing leaves the picture), and the number
    still a dot is stated with the way to get more (design rule 1). Measured on Mensores at a
    1280×760 pane: `pkg:mcp` lights 360 and draws **102** boxes; the worst plate lights 1,319
    and draws 86, placed in **2.3 ms**.

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

27. **A container's affordance drowns out the affordances inside it, because it wins on
    area.** The compartment diagram carried `cursor: grab` on its canvas — *this surface is
    a thing you drag* — while each box carried `cursor: pointer`. Both were correct, both
    were live, and the canvas is **most of what a pointer is ever over**: the boxes' claim
    was visible only in the instant the pointer crossed one, and the drawing read as a
    picture to pan rather than as a set of things to click.

    The cost was not aesthetic and it was not a defect anything could detect. Every control
    was wired, the self-check passed, and clicking a box had always opened the inspector.
    What was missing is that **nobody found out it did.** Reported as comprehension rather
    than as a bug, after the cursor was changed: *"this change resolved a major confusion
    for me… now I understand how the diagrams work — click to view Inspector, and how the
    Inspector list works."* A feature nobody discovers and a feature that does not exist
    are the same feature.

    This is design rule 16 from the far side. That rule is about a control that renders and
    is wired to nothing; this is a control wired to everything, whose signal is masked by a
    louder one belonging to the thing it sits on. Both look exactly like working software,
    and the second is harder to find because it *is* working software.

    Two things follow. **Ask what the surface claims before asking what the target claims** —
    where a container and its children both spend one channel, the container is what a
    reader reads, and the child's use of it is a flicker. And a pan affordance is a poor
    trade against a click affordance in a drawing that is mostly clicking: panning is
    discovered by trying, clicking is not, so the channel belongs to the act the reader
    cannot guess at.

    *Found by Tom driving it, and only by that. It began as a complaint about a 1 px arrow
    being thin to aim at — which was true, and was the smaller half of the problem.*
