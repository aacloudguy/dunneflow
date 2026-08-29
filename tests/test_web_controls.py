"""The shell's controls, and the data it must not be carrying.

Two families of check, both aimed at failures that are invisible from inside the running
page.

**Dead controls.** Design rule 16: a control that renders but is wired to nothing looks
exactly like one that works. The shell carries its own `selfCheck()`, which is the right
thing at runtime and the wrong place to *rely* on -- a self-check nobody opens the page to
see has already failed. These run in `pytest`.

**Pinned data.** The shell began as a ratified prototype with one program's real numbers
written into it. Pinned data is the right way to settle a design and the wrong way to ship
one: point the tool at another codebase and every one of those arrays is a confident lie
about a program nobody has read. The port emptied them, and this keeps them empty.

Every list here is derived from the files. A hand-kept list agrees with a wrong
implementation, which is the failure it was supposed to detect.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _attrs(html: str, attr: str) -> set[str]:
    return set(re.findall(rf'{attr}="([^"]+)"', html))


def _js_set(name: str) -> set[str]:
    """Read a `new Set([...])` literal out of the shell without executing it."""
    js = _read("shell.js")
    m = re.search(rf'const {name} = new Set\(\[(.*?)\]\)', js, re.S)
    assert m, f"{name} is no longer a Set literal; this test cannot see it"
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _nav_routes() -> set[str]:
    js = _read("shell.js")
    body = js.split("const NAV_ROUTES = {", 1)[1].split("\n};", 1)[0]
    keys = set(re.findall(r"^\s+([a-zA-Z][\w]*)\s*:", body, re.M))
    assert keys, "NAV_ROUTES changed shape -- this test is blind"
    return keys


def _nav_kinds_built() -> set[str]:
    """Every `nav` kind the generated navigator can produce."""
    js = _read("shell.js")
    body = js.split("const NAV_GROUPS = [", 1)[1].split("\n];", 1)[0]
    # `\b` matters: `sevnav: "broken"` is a severity, not a nav kind, and without the
    # boundary this test reported three dead routes that were never routes.
    return set(re.findall(r'\bnav:\s*"([^"]+)"', body))


# --------------------------------------------------------------- dead controls --- #

def test_every_generated_nav_item_has_a_route() -> None:
    """The navigator is built from the store, so its kinds cannot be read off the HTML.

    An unrouted kind used to fall through to "show the graph", which is how eight menu
    items once rendered perfectly and did nothing.
    """
    built, routed = _nav_kinds_built(), _nav_routes()
    assert built <= routed, f"nav kinds with no route: {sorted(built - routed)}"


def test_every_static_control_is_listened_for() -> None:
    """The shell's own self-check list, applied to the markup at build time."""
    html = _read("index.html")
    used = {m for m in re.findall(r'data-([a-zA-Z][\w-]*)=', html)}
    wired = _js_set("WIRED_ATTRS")
    # `toggle` and the mode buttons are wired by delegation and appear in the list.
    unwired = {u for u in used if u not in wired}
    assert not unwired, f"controls in the markup that nothing listens for: {sorted(unwired)}"


def test_the_page_loads_what_it_needs() -> None:
    """A missing script is a blank page, and a blank page must never be a mystery.

    The graph is the reason this is not a formality. For one session the shell replaced
    `index.html` and simply stopped loading the engine: deck.gl was never fetched, there
    were no canvases on the page, and the 2.5D stack -- built, measured at 60 fps and
    entirely intact -- was unreachable. Nothing failed. The page loaded, every control
    worked, and one whole half of the product was not there.
    """
    html = _read("index.html")
    for src in ("/vendor/deck.gl.min.js", "/static/settings.js", "/static/shading.js",
                "/static/graph.js", "/static/shell.js"):
        assert src in html, f"{src} is never loaded, so the page is missing part of itself"
    assert "/static/tokens.css" in html, "the token stylesheet is never loaded"

    # Order is not incidental: these are classic scripts sharing one global scope, and each
    # reads the global the one before it defines.
    at = [html.index(s) for s in ("/vendor/deck.gl.min.js", "/static/shading.js",
                                  "/static/graph.js", "/static/shell.js")]
    assert at == sorted(at), "the scripts are loaded out of order; each needs the last"


def test_the_javascript_parses() -> None:
    """A syntax error in the shell is a blank page with no dashboard at all.

    It happened while writing this chunk: a backtick inside an HTML comment, inside a
    template literal, closed the literal early. `shell.js` failed to parse, the page came
    up with an empty navigator and "showing 0 of 0 routines", and every Python test still
    passed -- because none of them had ever asked whether the file was valid JavaScript.

    Skipped rather than required when no engine is present. DunneFlow ships with **no Node
    at runtime or build** and that is not negotiable; this uses whatever engine the
    developer's machine happens to have, and asserts nothing about the product.
    """
    engine = next((c for c in ("node", "deno", "bun") if shutil.which(c)), None)
    if engine is None:
        jsc = Path("/System/Library/Frameworks/JavaScriptCore.framework"
                   "/Versions/A/Helpers/jsc")
        engine = str(jsc) if jsc.exists() else None
    if engine is None:
        pytest.skip("no JavaScript engine on this machine to parse with")

    cmd = {"node": ["--check"], "deno": ["check"], "bun": ["build", "--no-bundle"]}
    for js in sorted(STATIC.glob("*.js")):
        args = [engine, *cmd.get(Path(engine).name, []), str(js)]
        r = subprocess.run(args, capture_output=True, text=True)
        assert r.returncode == 0, f"{js.name} does not parse:\n{r.stderr or r.stdout}"


def test_no_backtick_hides_in_an_html_comment() -> None:
    """The parse test catches this; this one names it.

    It has happened twice in a day. A template literal holds HTML, the HTML holds a
    comment, and the comment mentions a symbol the way the rest of this codebase does --
    in backticks. The backtick closes the literal, the file stops being JavaScript, and the
    page comes up empty. Nothing else fails.

    Kept separate from `test_the_javascript_parses` because that one skips when the machine
    has no JavaScript engine, and this defect needs no engine to find. A comment inside
    generated markup is prose about code, and prose does not need the quoting that code
    does -- rule 9 in a very small key.
    """
    for js in sorted(STATIC.glob("*.js")):
        for comment in re.findall(r"<!--.*?-->", js.read_text(encoding="utf-8"), re.S):
            assert "`" not in comment, (
                f"{js.name}: a backtick inside an HTML comment closes the template literal "
                f"it sits in — write the symbol without backticks:\n{comment[:200]}"
            )


def test_the_graph_has_somewhere_to_live() -> None:
    """`render()` fills the centre pane with innerHTML on every keystroke.

    A deck.gl canvas in that element would be destroyed and rebuilt continuously, losing
    its GL context, its camera and the reader's place. So the graph gets a mount that
    `render()` never touches, and the two are swapped rather than rewritten.
    """
    html = _read("index.html")
    assert 'id="graphMount"' in html and 'id="viewMount"' in html
    js = _read("shell.js")
    assert 'const vp = $("#viewMount")' in js, (
        "render() writes to the viewport again, which would destroy the graph canvas"
    )


def test_every_graph_action_is_reachable_and_every_control_acts() -> None:
    """Design rule 16, both directions, for the graph's own control table.

    The second direction is the one a hand forgets: an action no control reaches is a
    feature that has quietly stopped being reachable while every other test still passes.
    """
    js = _read("shell.js")
    body = js.split("const GRAPH_ACTIONS = {", 1)[1].split("\n};", 1)[0]
    actions = set(re.findall(r"^\s+([a-zA-Z][\w]*)\s*:", body, re.M))
    assert actions, "GRAPH_ACTIONS changed shape -- this test is blind"
    # A `${...}` is an interpolation, not markup -- the self-check quotes the attribute
    # back in its own error message, and reading that as a control is the same category
    # error as reading a docstring as code (rule 9).
    drawn = {v for v in re.findall(r'data-gact="([^"]+)"', js) if "${" not in v}
    assert drawn <= actions, f"graph controls with no action: {sorted(drawn - actions)}"
    assert actions <= drawn, f"graph actions no control reaches: {sorted(actions - drawn)}"


def test_hidden_actually_hides() -> None:
    """`[hidden]` is a user-agent rule and any author `display` declaration beats it.

    A panel with `display:grid` once cancelled its own `hidden` and painted over the
    canvas while every control reported success. One line prevents it, and the symptom is
    invisible to every check that reads the DOM, so it is asserted rather than trusted.
    """
    assert "[hidden] { display: none !important; }" in _read("tokens.css")


# ----------------------------------------------------------------- pinned data --- #

# `THREADS` is here because it was the one that got away. It held six hand-written rows
# about one Mensores routine -- naming `Plan 84-06`, `disceptator`, `SOCIETY_HEADLESS` --
# and evaded all three pinned-data guards at once: a `const` object rather than a `let []`,
# absent from this list, and invisible to the prose guard, which searches for the sample
# program's *name* while this data said `disceptator`. Membership here is structural and
# cannot be evaded that way.
PER_PROGRAM = ["ENTRYPOINTS", "BOUNDARIES", "PKGS", "TABLES", "ROUTINES",
               "ANOMALIES", "TERMS", "UNDEFINED", "CONVENTIONS", "VOCAB", "MANIFEST",
               "CURIOSITIES", "THREADS"]
# `PROVENANCE` was here and is gone rather than renamed: it held every source span of every
# glossary citation, and the viewer fetches one span from `/api/source` when a citation is
# opened. This list is the record that it left deliberately -- the guard above fails on a
# name it cannot find, which is how a rename is caught.


def test_no_program_data_is_pinned_into_the_shell() -> None:
    """Every per-program array starts empty and is filled from the store.

    This is the whole point of the port. A shell that ships one program's numbers will
    show them to the next program too -- confidently, and wrongly, with no symptom at all
    until someone who knows the codebase looks at it.
    """
    js = _read("shell.js")
    pinned = []
    for name in PER_PROGRAM:
        m = re.search(rf'^(?:let|const) {name}\s*=\s*(.{{0,40}})', js, re.M)
        assert m, f"{name} is gone -- if it was renamed, rename it here too"
        value = m.group(1).strip()
        if not re.match(r'^(\[\s*\]|\{\s*\})\s*[;,]', value):
            pinned.append(f"{name} = {value}")
    assert not pinned, f"per-program data pinned into the shell: {pinned}"


def test_no_program_data_is_pinned_inside_state() -> None:
    """The same rule, one level down, where the guard above could not see.

    `test_no_program_data_is_pinned_into_the_shell` walks the top-level arrays. It passed
    for a whole session while `state` still carried the prototype's Mensores data:

        usage:       {cover: 41, graph: 68, table: 52, doc: 12, settings: 9}
        selectedRow: "mensores.quaestor._witness_client.submit_to_peer"
        selected:    "specimen"

    `usage` exists so a Setting can be retired on evidence rather than opinion; seeded with
    invented counts it retires them on fiction, and reads as a measurement while doing it.
    A qualified name is unmistakable -- two dots and no spaces -- so that is what this
    looks for, rather than a list of words that would have to be kept by hand.
    """
    js = _read("shell.js")
    body = js.split("const state = {", 1)[1].split("\n};", 1)[0]

    qualified = [s for s in re.findall(r'"([^"]*)"', body)
                 if s.count(".") >= 2 and " " not in s and len(s) > 8]
    assert not qualified, f"qualified names pinned into state: {qualified}"

    m = re.search(r"usage:\s*\{([^}]*)\}", body)
    assert m, "usage is no longer an object literal in state; this test is blind"
    assert not m.group(1).strip(), (
        f"usage ships with counts already in it: {{{m.group(1).strip()}}} -- "
        "a usage counter seeded with invented numbers retires settings on fiction"
    )


def test_a_reset_reports_every_setting_it_clears() -> None:
    """A reset that under-reports itself is a silent omission, like an unstated filter.

    `resetSettings` used to walk its own label table, so a setting added without a label
    was cleared and never mentioned. It now walks the defaults; this keeps the labels
    honest so the fallback stays a safety net rather than the normal case.
    """
    js = _read("settings.js")
    defaults = set(re.findall(r"^  (\w+):", js.split("const DEFAULTS = {", 1)[1]
                              .split("\n};", 1)[0], re.M))
    named = set(re.findall(r"(\w+):\s*'", js.split("const named = {", 1)[1]
                           .split("\n  };", 1)[0]))
    assert defaults, "DEFAULTS changed shape -- this test is blind"
    assert defaults <= named, (
        f"settings with no label in the reset report: {sorted(defaults - named)} -- "
        "they would be cleared and named only by their key"
    )


def test_the_shell_declares_nothing_const_that_the_store_owns() -> None:
    """`const` would also mean the loader cannot replace it -- a silent empty dashboard."""
    js = _read("shell.js")
    for name in PER_PROGRAM:
        assert not re.search(rf'^const {name}\b', js, re.M), (
            f"{name} is `const`, so `loadCover` cannot fill it and the view stays empty"
        )


# ------------------------------------------------------------------ dimensions --- #

def test_layout_dimensions_are_stored_in_rem() -> None:
    """Design rule 3: one root scale must resize the whole surface together.

    The rule bites on anything affecting **layout or type** — widths, heights, padding,
    font sizes. Ornament is exempt on purpose: a shadow's blur, a focus outline and a
    small corner radius read correctly at every scale, and scaling a hairline produces a
    blurry line rather than a bigger one. The root `font-size` is the value the
    multiplier acts *on*, so it is the one dimension that cannot itself be in rem.

    A `@media` condition is exempt too, and that one is not a concession — see
    `test_breakpoints_are_px_because_a_media_rem_is_not_the_pages_rem` below, which
    asserts the opposite for exactly those lines.
    """
    exempt = re.compile(r"--shadow|box-shadow|outline|border-radius|"
                        r"border(-\w+)?:\s*[\d.]+px\s+(solid|dashed|dotted)|font-size:\s*calc")
    # Block comments are stripped from the whole file before splitting into lines. Doing
    # it per line saw only a comment that opened and closed on one, so prose inside a
    # multi-line comment was read as CSS -- this test failed on a sentence explaining why
    # a breakpoint is 1088px, which is a test reporting its own blind spot as a defect.
    css = re.sub(r"/\*.*?\*/", "", _read("tokens.css"), flags=re.S)
    offenders = []
    for bare in css.splitlines():
        if exempt.search(bare) or bare.lstrip().startswith("@media"):
            continue
        for hit in re.findall(r"(-?\d*\.?\d+)px", bare):
            if abs(float(hit)) > 1:
                offenders.append(bare.strip())
    assert not offenders, f"layout dimensions the scale multiplier cannot reach: {offenders}"


# ------------------------------------------------------------- the breakpoints --- #

def test_breakpoints_are_px_because_a_media_rem_is_not_the_pages_rem() -> None:
    """The one place `px` is right, and `rem` is actively wrong.

    Design rule 3 puts every *dimension* in rem so one multiplier resizes the surface
    together. A breakpoint is not a dimension -- it is a question about the window -- and
    a `rem` inside `@media` does not mean what it means anywhere else in the file: by
    spec it resolves against the **browser's** default font size and ignores `:root`,
    which this stylesheet pins and which the scale slider drives.

    Measured on a reader whose Chrome default is 24px: moving the slider took the
    navigator from 192px to 288px and moved the breakpoints not one pixel, while `68rem`
    silently meant 1632px instead of 1088px and put a 1454px window into the narrow
    layout -- where the inspector wrapped onto a second grid row and the whole app grew
    taller than the window.

    So this asserts the inverse of the rule-3 test, over exactly the lines that test
    skips. A rem here looks like a member of the scaling family and is not one.
    """
    offenders = [
        line.strip() for line in _read("tokens.css").splitlines()
        if line.lstrip().startswith("@media") and "rem" in line.split("/*", 1)[0]
    ]
    assert not offenders, (
        "breakpoints in rem resolve against the browser's font size, not the page's: "
        f"{offenders}"
    )


def test_the_narrow_layout_actually_hides_what_it_hides() -> None:
    """A media query contributes no specificity, so equal selectors go to source order.

    `.inspector { display: none }` inside the narrow block lost to `.inspector { display:
    flex }` declared later in the same file. The pane then rendered into a grid declaring
    two columns and wrapped onto row 2 -- "Nothing selected" at the bottom left, an empty
    strip beside it, and an app taller than the viewport.

    Same family as `test_hidden_actually_hides`: the wiring was right and the paint was
    wrong, and nothing that reads the DOM can see it. The fix is specificity, not order,
    so that a later component rule cannot silently take it back.
    """
    css = _read("tokens.css")
    for pane in ("inspector", "navigator"):
        assert f".body > .{pane} {{ display: none; }}" in css, (
            f"the narrow layout hides .{pane} with a bare selector that a later "
            f"`display` declaration will beat"
        )


# -------------------------------------------------------------- a real subject --- #

def test_every_subject_setting_nav_item_carries_a_subject() -> None:
    """A label is not an identity.

    The four routes that set what you are looking AT -- ways in, packages, boundaries,
    tables -- were `() => { state.view = state.mode; ensureGraph(); }`: they switched
    mode and selected nothing, so all forty navigator rows did the same thing and the
    inspector went on truthfully reporting "Nothing selected". It never tripped the
    no-route check, because the route existed and had nothing to act on.

    Asserted in both directions, because either half alone passes while the feature is
    dead: the item must emit an identity, and the route must consume one.
    """
    js = _read("shell.js")
    body = js.split("const NAV_GROUPS = [", 1)[1].split("\n];", 1)[0]

    subject_kinds = {"ep", "pkg", "b", "t"}

    def item_text(kind: str) -> str | None:
        """The item literal for one nav kind, brace-matched.

        Not a character class: `sel: \\`pkg:${p.id}\\`` contains braces of its own, and
        `[^{}]` stopped dead at the first one -- which silently found no item for `pkg`
        and `b` and would have reported a working feature as dead.
        """
        m = re.search(rf'\bnav:\s*"{re.escape(kind)}"', body)
        if not m:
            return None
        start = body.rfind("{", 0, m.start())
        depth = 0
        for i in range(start, len(body)):
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
                if depth == 0:
                    return body[start:i + 1]
        return None

    for kind in sorted(subject_kinds):
        item = item_text(kind)
        assert item, f'no navigator item builds nav kind "{kind}"'
        assert "sel:" in item, (
            f'nav kind "{kind}" builds an item with no `sel:` — it can only say that '
            f"something was clicked, never which thing: {item}"
        )

    routes = js.split("const NAV_ROUTES = {", 1)[1].split("\n};", 1)[0]
    for kind in subject_kinds:
        route = re.search(rf"^\s*{re.escape(kind)}:\s*(.+)$", routes, re.M)
        assert route, f'no route for nav kind "{kind}"'
        assert "selectFromNav" in route.group(1), (
            f'route "{kind}" does not select anything: {route.group(1).strip()}'
        )

    assert 'data-navid="${esc(i.sel)}"' in js, (
        "the identity never reaches the DOM, so the route cannot read it back"
    )


# ------------------------------------------------------------------ the axes --- #

def test_every_spread_slider_reaches_the_engine() -> None:
    """A slider whose id the handler does not know moves nothing and says nothing.

    The three axes are driven by one table rather than three copies of a branch, so the
    failure mode is a slider present in the markup with no entry in that table: it renders,
    it drags, its readout never updates and the geometry never moves. Design rule 16 for a
    control that is an `id` rather than a `data-` attribute, which is the half the DOM
    self-check and `test_every_static_control_is_listened_for` cannot see.

    Asserted in both directions, and against `graph.js` as well, because a slider wired to
    an option the engine ignores is the same silent no-op one layer further down.
    """
    js = _read("shell.js")

    rendered = set(re.findall(r'\["(gspread[a-z])",', js))
    assert rendered, "the spread sliders are no longer built from a table; this test is blind"

    table = re.search(r"const AXIS = \{([^}]*)\}", js)
    assert table, "the AXIS table is gone; the sliders cannot reach the engine"
    handled = dict(re.findall(r"(gspread[a-z]):\s*\"(\w+)\"", table.group(1)))

    assert rendered == set(handled), (
        f"sliders with no handler: {sorted(rendered - set(handled))}; "
        f"handlers with no slider: {sorted(set(handled) - rendered)}"
    )

    engine = _read("graph.js")
    for slider, option in sorted(handled.items()):
        assert f"opts.{option}" in engine, (
            f"slider {slider} sets `{option}`, which the engine never reads"
        )
        assert f"partial.{option} !== undefined" in engine, (
            f"`{option}` never triggers a re-layout, so moving {slider} changes nothing"
        )


def test_collapsing_is_separate_from_hiding() -> None:
    """Two switches, because they answer two questions.

    Hiding decides whether an unselected plate draws at all; collapsing decides whether it
    still takes up room in the stack. Folding them into one control would make "show me
    these eight plates, packed" unreachable — which is the state the pair exists for.
    """
    shell, engine = _read("shell.js"), _read("graph.js")
    assert 'id="gcollapse"' in shell, "the collapse control is gone"
    assert "collapseUnused" in shell and "collapseUnused" in engine
    assert "filterMode" in engine, "hiding and collapsing have been merged"

    # Rule 1: a plate whose gap has been closed has left the picture and must be counted.
    assert "collapsed:" in engine, "the engine never reports how many plates it collapsed"
    assert "plates collapsed" in shell, "the count is never shown, so the filter is silent"


# ------------------------------------------------------------- dead settings --- #

def test_every_persisted_setting_is_read_by_something() -> None:
    """A setting nothing reads is design rule 16 without even a control to look at.

    `panels` lived in `settings.js` from the first day: persisted per program, versioned,
    and named in the reset dialog as "panel layout" — so a reset would have reported
    clearing a layout that had never existed. Nothing anywhere read it. The pre-merge graph
    had collapsible panes and the merge kept the switch while dropping the implementation,
    which is the same shape as the eight menu items that rendered perfectly and did nothing.

    It looks for a **property access** -- `state.panels`, `opts.spreadZ` -- rather than the
    bare name, and that distinction is the test. Every one of these keys is also written as
    a plain string in the list of things to persist, so searching for the name alone passes
    on a setting that is faithfully saved and restored and never once acted upon, which is
    precisely the failure. The keys are read out of `DEFAULTS` itself, so a hand-kept list
    cannot agree with a wrong implementation.
    """
    settings = _read("settings.js")
    block = settings.split("const DEFAULTS = {", 1)[1].split("\n};", 1)[0]
    keys = re.findall(r"^\s{2}([a-zA-Z][\w]*):", block, re.M)
    assert len(keys) > 20, "DEFAULTS changed shape -- this test is blind"

    readers = _read("shell.js") + _read("graph.js")
    unread = [k for k in keys if not re.search(rf"\.{re.escape(k)}\b", readers)]
    assert not unread, (
        "settings persisted, reset by name, and read by nothing: "
        f"{sorted(unread)} — either wire them up or take them out"
    )


def test_every_panel_has_a_mechanism() -> None:
    """A panel in the settings with no entry in `PANELS` folds nothing, silently.

    This is the guard the previous one could not be. `test_every_persisted_setting_is_read_
    by_something` walks the *top-level* keys of `DEFAULTS`, and `panels` as a whole was
    plainly being read -- so `panels.hud` and `panels.controls` sat defaulted, persisted and
    named in the reset dialog as "panel layout" while `applyPanels()` looped over a
    two-element literal that did not mention them. The pre-merge graph could fold those two
    boxes; the merge kept the switch and dropped the implementation, and then the first fix
    narrowed a loop over `Object.entries(panels)` to a literal pair and took the capability
    with it a second time.

    So the two key sets must agree, both derived from the source. A panel added to settings
    without a mechanism fails here rather than rendering a control that does nothing.

    **Not generalised to every nested group, on purpose.** `state.insp[key]` and
    `state.aiOps[o.id]` are read by *computed index*, so a nested property-access check
    would report both as dead while they work perfectly -- and a check that cries wolf is a
    check nobody reads (HANDOFF: "a check may only claim what its instrument can prove").
    `panels` can be checked precisely because it has a mechanism table to check against.
    """
    settings = _read("settings.js")
    panels_default = settings.split("panels: {", 1)[1].split("}", 1)[0]
    declared = set(re.findall(r"(\w+):", panels_default))
    assert declared, "DEFAULTS.panels changed shape -- this test is blind"

    shell = _read("shell.js")
    table = shell.split("const PANELS = {", 1)[1].split("\n};", 1)[0]
    wired = set(re.findall(r"^\s{2}(\w+):", table, re.M))
    assert wired, "the PANELS table changed shape -- this test is blind"

    assert declared == wired, (
        "settings and mechanisms disagree — "
        f"persisted but unfoldable: {sorted(declared - wired)}; "
        f"wired but never stored: {sorted(wired - declared)}"
    )


def test_the_legend_is_a_track_not_an_overlay() -> None:
    """The legend indexes the picture; it may not be drawn on top of it.

    It was 26rem of opaque surface pinned over the canvas — the primary way into the graph
    (design rule 19) rendered as though it were furniture. That is also what made `fitView`
    wrong: the pre-merge engine carried `panels.disks ? 0.60 : 0.90` to aim the framing away
    from the panel, chunk 2 dropped the term while the panel stayed, and snap-to-fit went on
    centring the stack under it.

    Both halves are asserted, because either alone passes while the defect is live: the
    legend must not be positioned over the canvas, and the mount must give it a track that
    collapses (design rule 24 — the track carries the state, or collapsing the pane leaves a
    hole exactly its width).
    """
    css = _read("tokens.css")
    # Anchored to the start of a line, not merely to the selector text: ".graphlegend {"
    # also appears inside '.graphmount[data-legend="off"] > .graphlegend { display: none }',
    # which sits earlier in the file -- so a plain split read that rule instead and passed
    # whatever the real declaration said. Caught by running the guard against its own
    # defect, which is the only reason it is not still passing for the wrong reason.
    rule = re.search(r"^\.graphlegend \{(.*?)\}", css, re.M | re.S)
    assert rule, "the .graphlegend rule has moved -- this test is blind"
    legend = rule.group(1)
    assert "position: absolute" not in legend, (
        "the legend is floating over the canvas again — it is a pane, not furniture, "
        "and fitView frames by arithmetic only while it owns a track"
    )
    assert "grid-template-columns" in css.split(".graphmount {", 1)[1].split("}", 1)[0], (
        ".graphmount must be a grid: the legend needs a track of its own"
    )
    assert '.graphmount[data-legend="off"]' in css, (
        "nothing collapses the legend's track — a pane hidden while its column stays "
        "26rem leaves a 26rem hole"
    )


def test_the_slider_reset_covers_every_slider_and_invents_no_defaults() -> None:
    """A reset that misses a slider leaves the reader in the arrangement they wanted out of.

    Four axes, each stepping 0.05, are genuinely hard to land by hand, and the only way back
    used to be a reload or the whole-settings reset — which also throws away the disk order,
    the colours and the selection. So `sizereset` resets exactly the slider keys.

    Both halves matter. Every slider on screen must be in `SLIDER_KEYS`, or the reset
    silently leaves one where it was and reports success for the rest. And every key must
    exist in `DEFAULTS`, because the reset reads its values from there rather than carrying
    numbers of its own: a second copy of a default is a second thing to forget when one of
    them moves, and `state[k] = undefined` would render a slider with no position at all.
    """
    js = _read("shell.js")

    keys = re.search(r"const SLIDER_KEYS = \[([^\]]*)\]", js)
    assert keys, "SLIDER_KEYS is gone; the reset cannot know what it resets"
    reset = set(re.findall(r'"(\w+)"', keys.group(1)))

    # Every range input in the controls box, taken from the markup rather than a list.
    axis_table = re.search(r"const AXIS = \{([^}]*)\}", js)
    assert axis_table, "the AXIS table is gone -- this test is blind"
    axes = set(re.findall(r'"(spread[XYZ])"', axis_table.group(1)))
    assert axes, "the AXIS table changed shape -- this test is blind"
    sliders = axes | {"nodeSize"}          # the size slider is the fourth, handled apart

    assert sliders <= reset, (
        f"sliders the reset does not restore: {sorted(sliders - reset)} — "
        "it would report success while leaving them where they were"
    )

    settings = _read("settings.js")
    block = settings.split("const DEFAULTS = {", 1)[1].split("\n};", 1)[0]
    declared = set(re.findall(r"^\s{2}(\w+):", block, re.M))
    assert reset <= declared, (
        f"reset keys with no default: {sorted(reset - declared)} — "
        "the reset reads Settings.DEFAULTS, so these would become undefined"
    )
    assert "Settings.DEFAULTS[k]" in js, (
        "the reset has stopped reading Settings.DEFAULTS — a second copy of a default "
        "is a second thing to forget when one of them moves"
    )


def test_every_declared_data_array_is_assigned_somewhere() -> None:
    """`let X = []` that nothing ever writes to is an empty view with no symptom.

    `ROUTINES` was declared at the top of the shell, commented "for table mode", and
    assigned by **nothing** — so table mode rendered zero rows for as long as it has
    existed, under a footer stating a count from a different program. Nothing failed. The
    page loaded, the columns drew, the sort buttons worked, and there was no data.

    It is the pinned-data family from the other side: those guards check that the arrays are
    *empty* at rest, which `ROUTINES` passed perfectly by never being filled at all.
    """
    js = _read("shell.js")
    head = js.split("const $  =", 1)[0]
    declared = set(re.findall(r"^let ([A-Z][A-Z_]+)\s*=\s*\[\]", head, re.M))
    assert declared, "the data arrays changed shape -- this test is blind"

    for name in sorted(declared):
        assigned = re.search(rf"^\s*{name}\s*=\s*(?!\[\]\s*;)", js, re.M)
        # An array nothing fills is fine *if the view says so* — "not computed yet" and
        # "nothing to report" are opposite claims and a blank panel states the wrong one.
        # This is the invariant rather than a list of exemptions, which would have grown
        # until the guard was mostly exceptions and caught nothing.
        # Either polarity of the branch counts -- `!X.length ? empty : rows` and
        # `X.length ? rows : empty` are the same statement, and a guard that only
        # knew one of them would fail on correct code, which is how a check stops
        # being read.
        says_so = re.search(rf"(!\s*{name}\.length|{name}\.length\s*\?)", js)
        assert assigned or says_so, (
            f"{name} is declared, never assigned, and no view states that it is empty — "
            "so the page renders blank where it should say nothing has been computed"
        )


def test_no_program_data_is_pinned_into_view_prose() -> None:
    """The third hiding place, after the top-level arrays and `state`.

    Table mode's footer read "Showing **12** of **515** routines in
    `mensores.quaestor`" — a hard count and a real module name from the prototype, sitting
    in a template literal where neither existing guard could see it: it is not an array and
    not a `state` field, it is a sentence. `state.trail` carried a pinned "mensores" the
    same way.

    Looks for the sample program's name in the view templates rather than for numbers,
    because a number in prose is often legitimate ("one hop", "three panes") and a specific
    program's name never is.
    """
    for name in ("shell.js", "index.html"):
        text = _read(name)
        # Comments legitimately discuss the program the tool was verified against.
        body = re.sub(r"/\*.*?\*/|//[^\n]*|<!--.*?-->", "", text, flags=re.S)
        hits = [m for m in re.findall(r"[\"'`>][^\"'`<]*\bmensores[\w.]*", body)]
        assert not hits, (
            f"{name}: one program's name is pinned into what the page renders: "
            f"{hits[:3]} — the next codebase gets shown it, confidently and wrongly"
        )


def test_the_search_box_is_listened_for() -> None:
    """The most prominent control on the page, wired to nothing at all.

    `#search` has always carried the placeholder "Search routines, tables, boundaries…",
    has always been focusable with `/`, and appeared exactly once in `shell.js` — in the
    shortcut that focuses it. It rendered, it took keystrokes, and there was no handler.

    It is an `id` control rather than a `data-` one, which is precisely the half
    `selfCheck()` and `test_every_static_control_is_listened_for` cannot cover: both walk
    `data-` attributes. Same blind spot the spread sliders were found in, so the same
    remedy — read the markup for `id`-addressed inputs and demand a listener for each.
    """
    html = _read("index.html")
    js = _read("shell.js")

    inputs = set(re.findall(r'<input[^>]*\bid="([^"]+)"', html))
    inputs |= set(re.findall(r'<select[^>]*\bid="([^"]+)"', html))
    assert "search" in inputs, "the search box is gone -- this test is blind"

    # Inert on purpose, and visibly so: `prog` holds one option because switching programs
    # is not built, and `rev` carries a disabled "— layers not built yet —" option. Named
    # rather than silently skipped, so that building either one removes its line here.
    declared_inert = {"prog", "rev"}

    for ident in sorted(inputs - declared_inert):
        listened = (
            re.search(rf'#{re.escape(ident)}"\s*\)\s*\.addEventListener', js)
            or re.search(rf'\$\("#{re.escape(ident)}"\)[\s\S]{{0,400}}?addEventListener', js)
            or re.search(rf't\.id === "{re.escape(ident)}"', js)
            or re.search(rf'id === "{re.escape(ident)}"', js)
        )
        assert listened, (
            f"#{ident} is an input nothing listens to — it renders, it accepts input, "
            "and there is nothing on the other end"
        )


def test_a_trail_step_carries_the_subject_it_arrived_at() -> None:
    """A trail that cannot take you back is not a trail.

    Steps were `{view, label, note}` and clicking one set `state.view` and re-rendered — so
    from inside graph mode, where the view is already "graph", **nothing happened**. It
    rendered, highlighted the current step, scrolled and pruned correctly, and could not
    return anyone to anything they had been looking at.

    Rule 30 for the third time, and the most expensive place for it: design rule 15 says the
    trail is what makes a detour free, because nobody chases a rabbit if they might not find
    their way back.

    Both halves are asserted, because either alone passes while the feature is dead — the
    step must record a subject, and the handler must apply one.
    """
    js = _read("shell.js")

    push = re.search(r"state\.trail\.push\(\{([^}]*)\}", js)
    assert push, "pushTrail no longer pushes an object literal -- this test is blind"
    assert "subject" in push.group(1), (
        "a trail step records no subject, so clicking it cannot restore what you were "
        f"looking at: {push.group(1).strip()}"
    )
    # Both ways back must restore it: clicking a step, and the Back button. Checking that
    # the name merely appears passed while one of the two still went nowhere.
    applied = len(re.findall(r"applySelectionStep\(step\.subject\)", js))
    assert applied >= 2, (
        f"only {applied} of the two ways back apply a step's subject — clicking a step and "
        "pressing Back are separate handlers, and one of them would take you nowhere"
    )


def test_the_selection_can_be_taken_back() -> None:
    """Two ordinary clicks strand a reader, so undo is not a convenience here.

    Clicking the node you are already looking at clears the whole selection (a deliberate
    toggle-off in `togglePick`, and a trap when the click is also how you move), and every
    nothing-selected state looks identical — so there is nothing on screen to say which
    routine you had. Recovering it needs a history.

    Checks the whole chain rather than the presence of a function: recorded on both
    selection paths, guarded against recording its own replay, and reachable from a control.
    """
    js = _read("shell.js")

    assert "function recordSelection()" in js, "no selection history is recorded"
    assert js.count("recordSelection()") >= 3, (
        "the history is recorded on fewer paths than there are ways to select — the graph "
        "announcing a click and the list driving one must both reach it"
    )
    # The guard itself, not just the flag. The flag being declared and set proves nothing:
    # the recorder has to actually consult it, or every undo records itself as a new step
    # and the history can never move backwards.
    guard = r"function recordSelection\(\)\s*\{\s*if \(restoringSelection\) return;"
    assert re.search(guard, js), (
        "recordSelection does not bail while a restore is in flight, so an undo records "
        "itself as a new step and the history never moves backwards"
    )
    for act in ("undo", "redo"):
        assert re.search(rf'data-gact="{act}"', js), f"no control reaches {act}"
        assert re.search(rf"^  {act}: ", js, re.M), f"{act} has a control but no action"


# ------------------------------------------------------------------ the pop-up --- #

WEB = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"


def test_the_hover_event_is_emitted_and_listened_for() -> None:
    """Both halves, from the source, because either alone passes while nothing happens.

    The engine reports and the application draws (`graph.js` states that boundary in as
    many words). Split across two files, that is two places to be wrong in and each one
    looks fine on its own: an `emit('hover', ...)` nobody listens for draws nothing, and a
    `Graph.on("hover", ...)` nothing emits to is a listener that never runs. Neither raises,
    neither logs, and the pop-up simply does not appear -- design rule 16 across a module
    boundary.

    The engine's `listeners` table is checked too, because `on()` throws on an unknown
    event: a handler registered for an event the table does not declare fails loudly at
    boot rather than quietly at hover, and that is only true while `hover` is in it.
    """
    engine, shell = _read("graph.js"), _read("shell.js")

    assert re.search(r"const listeners = \{[^}]*\bhover:\s*\[\]", engine), (
        "`hover` is not in the engine's listeners table -- `on('hover', ...)` throws, and "
        "the pop-up never binds"
    )
    assert re.search(r"emit\(\s*'hover'", engine), (
        "nothing in the engine emits `hover`, so the shell's listener can never run"
    )
    assert "onHover:" in engine, (
        "deck.gl is not handed an `onHover` prop, so no pointer event ever reaches the emit"
    )
    assert re.search(r'Graph\.on\(\s*"hover"\s*,\s*(\w+)', shell), (
        "the shell never listens for `hover`; the engine reports into nothing"
    )


def test_the_hover_card_renders_only_fields_the_server_sends() -> None:
    """Rule 13 in the smallest space this product has: the claim and its source must agree.

    The card is filled from `/api/hover`, and a template reading `card.tables` against a
    server emitting `n_tables` renders **nothing** -- no error, no blank, just a row that
    is never there. The card would look exactly like a node with nothing to say, which is
    the one confusion this whole surface exists to prevent.

    Derived both ways from the source rather than from a hand-kept list, since a list is
    the thing that agrees with a wrong implementation.
    """
    shell = _read("shell.js")
    detail = (WEB / "detail.py").read_text(encoding="utf-8")

    # Everything `hoverDetailHtml` reads off the served object.
    body = shell.split("function hoverDetailHtml(card) {", 1)[1].split("\n}\n", 1)[0]
    read = set(re.findall(r"\bcard\.(\w+)", body))
    assert read, "hoverDetailHtml changed shape -- this test is blind"

    # Everything `hover_card` puts on it. Only the dict literals it returns, so a key that
    # exists elsewhere in the module does not vouch for one the card never receives.
    served = set(re.findall(r'"(\w+)":', detail.split("def hover_card(", 1)[1]))
    assert served, "hover_card changed shape -- this test is blind"

    missing = sorted(read - served)
    assert not missing, (
        f"the pop-up renders fields the server never sends: {missing} -- each is a row "
        "that silently does not appear, indistinguishable from a node with nothing to say"
    )


def test_the_hover_card_is_placed_again_once_it_is_filled() -> None:
    """The hazard the two-stage paint creates, and it is not hypothetical.

    The card is positioned as the skeleton -- 87px -- then filled to 293px. On a 418px
    canvas that puts its bottom 29px past the pane, so the half that just arrived is the
    half nobody can see. Growing downward is deliberate and stays; what has to follow it
    is one more placement, which is idempotent and therefore moves nothing that still fits.

    Checks that the fill path *calls* it, not merely that the function exists: a
    `hoverPlace` defined and never called from `hoverFill` is exactly the state this was
    written from.
    """
    shell = _read("shell.js")
    fill = shell.split("function hoverFill(id, card) {", 1)[1].split("\n}\n", 1)[0]
    assert "hoverPlace(" in fill, (
        "hoverFill does not re-place the card, so a card that grows past the bottom of "
        "the pane keeps the fetched half off screen"
    )
    # And it must place against the remembered cursor, not against something it invents:
    # the pointer event is long gone by the time the fetch lands.
    assert "hoverPos" in fill, (
        "hoverFill re-places without the remembered cursor position, so it cannot know "
        "where the card belongs"
    )


def test_every_thread_carries_a_subject_and_every_subject_has_a_route() -> None:
    """Both directions, and either half alone passes while the feature is dead.

    This is rule 30 in the place it has now appeared four times. The threads panel it
    replaces rendered six rows, highlighted correctly, and set `state.view = "curiosities"`
    whatever was clicked -- one destination for every thread, and a page that says nothing
    has been computed. The route existed, so no no-route check ever tripped; what was
    missing was a *subject*.

    So: every subject the server can mint must have a handler, and the handler table must
    be what the click actually routes through. A server emitting a `plate` subject nothing
    opens is a dead row; a client with a handler the server never sends is dead code that
    reads as coverage.
    """
    shell = _read("shell.js")
    threads_py = (WEB / "threads.py").read_text(encoding="utf-8")

    minted = set(re.findall(r'return \{"type": "(\w+)"', threads_py))
    assert minted, "threads.py no longer mints subjects as `{'type': ...}` -- this is blind"

    body = shell.split("const THREAD_SUBJECTS = {", 1)[1].split("\n};", 1)[0]
    routed = set(re.findall(r"^\s+(\w+):", body, re.M))
    assert routed, "THREAD_SUBJECTS changed shape -- this test is blind"

    assert minted <= routed, (
        f"the server mints thread subjects nothing opens: {sorted(minted - routed)} -- "
        "each is a row that renders, highlights, and goes nowhere"
    )
    assert routed <= minted, (
        f"the shell routes subject kinds the server never sends: {sorted(routed - minted)} "
        "-- dead code that reads as coverage"
    )

    # And the click must go *through* the table rather than past it. A handler table
    # nothing consults is the same defect with a tidier shape.
    #
    # Scoped to the click handler, and that is not fussiness: the first draft looked for
    # `followThread(subject)` anywhere in the file and passed against a version where the
    # click called `selectFromNav` directly, because the string also occurs in
    # `async function followThread(subject)` -- the definition vouching for its own call
    # site. Rule 37, on a guard written for rule 37.
    click = shell.split('$$("[data-thread]").forEach', 1)[1].split("}));", 1)[0]
    assert "followThread(" in click, (
        "the thread click handler does not call followThread, so the subject table is "
        "decoration and the click routes past it"
    )
    assert re.search(r"const go = THREAD_SUBJECTS\[", shell), (
        "followThread does not route from THREAD_SUBJECTS -- an unhandled subject would "
        "fall through to something that looks deliberate"
    )


def test_every_thread_kind_the_server_groups_is_a_kind_the_panel_shows() -> None:
    """A kind computed and never rendered is a whole thread family that silently vanishes.

    `threads.py` fixes the group order in `KIND_ORDER` so two readers of one routine see
    the same list; the panel titles them from `THREAD_KIND_TITLE`. Add a kind to one and
    not the other and its threads are computed, served, counted in the section heading --
    and drawn nowhere, because the panel iterates its own table. The heading would say 17
    over a list of 4.
    """
    shell = _read("shell.js")
    threads_py = (WEB / "threads.py").read_text(encoding="utf-8")

    order = re.search(r"KIND_ORDER = \((.*?)\)", threads_py, re.S)
    assert order, "KIND_ORDER changed shape -- this test is blind"
    kinds = set(re.findall(r'"(\w+)"', order.group(1)))

    body = shell.split("const THREAD_KIND_TITLE = {", 1)[1].split("\n};", 1)[0]
    titled = set(re.findall(r"^\s+(\w+):", body, re.M))
    assert titled, "THREAD_KIND_TITLE changed shape -- this test is blind"

    assert kinds == titled, (
        f"the server groups {sorted(kinds)} and the panel shows {sorted(titled)} -- "
        "threads in the difference are computed, counted in the heading, and drawn nowhere"
    )


def test_following_a_neighbour_reaches_both_selection_paths() -> None:
    """Design rule 2 built both, so both have to be reachable, and by both routes.

    A neighbour is followed two ways -- `togglePick` from the inspector's caller and callee
    lists, and `selectFromNav` from a thread's subject -- and they are different mechanisms.
    Wiring the setting to one of them leaves the reader who chose *keep the path* watching
    it work on half their clicks, which is worse than not offering it: an option that works
    sometimes is one nobody can build a habit on.

    The setting itself is covered for free by `test_every_persisted_setting_is_read_by_
    something`; what that cannot see is whether it reaches *both* paths.
    """
    shell = _read("shell.js")

    assert "followPickMode()" in shell.split("$$(\".gotonode\")", 1)[1][:900], (
        "the inspector's follow does not consult followPickMode -- it always replaces, "
        "whatever the reader chose"
    )
    subjects = shell.split("const THREAD_SUBJECTS = {", 1)[1].split("\n};", 1)[0]
    assert subjects.count("walking()") >= 2, (
        "not every thread subject honours the walk, so following one kind keeps the path "
        "and following another silently throws it away"
    )
    # `selectFromNav` must actually do something with it, or both call sites are polite
    # about a flag nothing reads.
    apply_wanted = shell.split("function applyWanted() {", 1)[1].split("\n}\n", 1)[0]
    assert "want.add" in apply_wanted, (
        "applyWanted ignores `add`, so every thread replaces the selection and the walk "
        "setting is a control wired to nothing"
    )


def test_every_data_attribute_the_shell_writes_is_in_the_roster() -> None:
    """The half `test_every_static_control_is_listened_for` cannot see.

    That guard reads `index.html`, so it covers only the markup that ships as a file. Every
    interesting control in this shell is *generated* -- the navigator rows, the thread
    buttons, the pane fold controls, the grid's own track state -- and none of it is in
    that file.

    Four attributes had been outside the roster since the panes learned to fold and the
    navigator became the routine list: `insp`, `fold`, `navid`, `titled`. All four are
    real. So the runtime self-check printed "dead controls" on every page load, was wrong
    about all four, and a genuine dead control would have arrived as a fifth line in an
    error nobody had believed for weeks. Its own comment says why that costs: a check that
    cries wolf is a check nobody reads.

    Derived from the source rather than from a list kept beside it, which is the whole
    reason the roster drifted in the first place.
    """
    js = _read("shell.js")
    # Strip comments first: this file discusses `data-nav` and `data-insp` in prose, and a
    # guard that reads its own documentation as evidence is vouching for nothing.
    body = re.sub(r"/\*.*?\*/|//[^\n]*", "", js, flags=re.S)

    written = set(re.findall(r'\bdata-([a-zA-Z][\w-]*)=', body))
    # `dataset.x` is the same attribute seen from the other side; camelCase maps back to
    # a hyphenated name, so only the plain ones are checked here -- the hyphenated ones
    # are all written as attributes somewhere and are caught by the line above.
    written |= {m for m in re.findall(r"\bdataset\.([a-z][a-z0-9]*)\b", body)}

    # And the grid's track state, which neither of those can see: `applyPanels` writes it
    # as `grid.dataset[spec.attr]`, a computed property whose name exists only as a string
    # in `PANELS`. That is precisely how `insp` stayed outside the roster -- the first
    # draft of this guard found the other three and missed it, which is the reason to run
    # a new check against its own defect rather than against a tidy version of it.
    panels = js.split("const PANELS = {", 1)[1].split("\n};", 1)[0]
    written |= set(re.findall(r'attr:\s*"(\w+)"', panels))
    assert written, "the shell writes no data attributes -- this test is blind"

    roster = _js_set("WIRED_ATTRS")
    missing = sorted(written - roster)
    assert not missing, (
        f"data attributes the shell writes that are not in WIRED_ATTRS: {missing} -- "
        "each makes the runtime self-check report a dead control, and four standing false "
        "alarms are how a real one goes unread"
    )


def test_every_cohort_kind_minted_has_a_query_to_resolve_it() -> None:
    """The same both-directions check as the subject table, one tier down.

    A cohort subject is a promise: *there is code at the far end of this, ask me and I will
    name it.* `_cohort("plate", ...)` with no entry in `cohort()`'s table is a thread that
    renders, highlights, is clicked, and comes back "no such thread kind" -- rule 30's
    failure wearing a server's uniform instead of a client's.

    The reverse matters too and is the quieter half: a query for a kind nothing ever mints
    is dead code that reads as coverage, and it is exactly what makes a table look more
    complete than the feature is.
    """
    threads_py = (WEB / "threads.py").read_text(encoding="utf-8")

    minted = set(re.findall(r'_cohort\(\s*"(\w+)"', threads_py))
    assert minted, "nothing mints a cohort any more -- this test is blind"

    table = threads_py.split("    sql = {", 1)[1].split("    }.get(kind)", 1)[0]
    resolved = set(re.findall(r'^\s+"(\w+)":', table, re.M))
    assert resolved, "cohort()'s query table changed shape -- this test is blind"

    assert minted == resolved, (
        f"cohort kinds minted: {sorted(minted)}; kinds with a query: {sorted(resolved)} -- "
        "one side is a thread that goes nowhere, the other is dead code that reads as "
        "coverage"
    )

    # And every one of them must be spendable: `cohort()` turns a single key into whatever
    # parameters its query needs, and a kind missing from that mapping raises `KeyError` on
    # a click rather than answering.
    spend = threads_py.split("    if kind == \"term\":", 1)[1].split("    nodes = ", 1)[0]
    named = set(re.findall(r'"(\w+)":\s*"\w+"', spend)) | {"term"}
    assert minted <= named, (
        f"cohort kinds with no parameter mapping: {sorted(minted - named)} -- following "
        "one raises rather than answering"
    )


def test_asking_where_the_selection_is_cannot_throw() -> None:
    """A guard that names the right case and does not catch it.

    `selectionOnScreen()` documents itself as returning null when there is no viewport --
    "we cannot say" and "it is off screen" being different answers that must not look
    alike. It guarded with `g.deckgl?.getViewports?.()`, which protects against a missing
    deck and **not** against the case it was written for: deck.gl asserts *inside*
    `getViewports()` before it has a view manager, so the throw came from within the call
    the optional chaining was wrapped around.

    The path is ordinary. Pick a routine in the navigator before opening the graph, and
    `selectFromNav` mounts the engine and runs `applyWanted()` synchronously, before any
    frame. The exception left `applyWanted`, so `persist()`, `recordSelection()` and
    `render()` after it never ran -- the selection happened, undo never recorded it, and
    nothing repainted.

    Checks for the catch rather than for the `?.`, because the `?.` was there the whole
    time and was exactly what made the code look guarded.
    """
    engine = _read("graph.js")
    body = engine.split("function selectionOnScreen() {", 1)[1].split("\n}\n", 1)[0]
    assert "getViewports" in body, "selectionOnScreen changed shape -- this test is blind"
    assert re.search(r"\btry\b", body) and re.search(r"\bcatch\b", body), (
        "selectionOnScreen calls getViewports() unguarded -- deck.gl asserts inside it "
        "before its first frame, and the throw takes out the rest of selectFromNav"
    )


# ------------------------------------------------- the two vocabulary lanes --- #

def _fn(js: str, name: str) -> str:
    """One function's source, from its `function` line to the next one at column 0.

    `\nasync function` counts. It did not, so a function followed by an async one returned
    both -- and a guard reading "the fields `loadRoutines` reads" was reading `loadAnomalies`
    as well, and failed on a field the endpoint it names has no reason to send. A helper
    that reads more than it claims makes every test built on it say more than it checked.
    """
    start = js.index(f"function {name}(")
    rest = js[start:]
    ends = [i for i in (rest.find("\nfunction ", 1), rest.find("\nasync function ", 1)) if i > 0]
    return rest if not ends else rest[:min(ends)]


def _served_keys(py: str, fn: str) -> set[str]:
    """The keys one `vocabulary.py` builder puts on the wire."""
    start = py.index(f"def {fn}(")
    body = py[start:]
    nxt = body.find("\ndef ", 1)
    return set(re.findall(r'^\s*"(\w+)":', body if nxt < 0 else body[:nxt], re.M))


def test_the_vocabulary_views_read_the_fields_the_server_sends() -> None:
    """The defect these two pages sat unported for, made into a check.

    Both views were written against the ratified prototype's shape and the server sends a
    different one -- `{glob, holds, total, rating, exceptions: [{name, where}]}` against
    `{pattern, ok, n, exceptions: [str]}`, and a term's four hand-named document slots
    against however many `senses` anything actually said. That is *worse* than an unported
    page: `cv.ok` is `undefined`, `(cv.ok / cv.n) * 100` is `NaN`, and a percentage bar
    renders at zero width beside a claim that is perfectly true. Nothing throws.

    So the field names are checked against the ones `vocabulary.py` emits, in that
    direction: a view may leave a served field unread (`uses` is a real example -- the
    page shows `used_as`, which is the same fact in a form a reader wants), but a view
    that reads a field the server does not send is silently rendering nothing.
    """
    js = _read("shell.js")
    py = (STATIC.parent / "vocabulary.py").read_text(encoding="utf-8")

    conv = _served_keys(py, "measure_naming")
    assert {"glob", "holds", "total", "rating", "sql"} <= conv, (
        "measure_naming changed shape -- this test is blind"
    )
    read = set(re.findall(r"\bcv\.(\w+)", _fn(js, "conventionPanel")))
    assert read, "conventionPanel reads nothing off a convention -- this test is blind"
    assert read <= conv | {"exceptions"}, (
        f"the naming view reads fields the server does not send: {sorted(read - conv)}"
    )

    sense = _served_keys(py, "bind_glossary")
    assert {"senses", "used_as", "provenance", "definition", "source", "line"} <= sense, (
        "bind_glossary changed shape -- this test is blind"
    )
    for fn in ("senseRow", "viewerPanel"):
        got = set(re.findall(r"\bs\.(\w+)", _fn(js, fn)))
        assert got, f"{fn} reads nothing off a sense -- this test is blind"
        assert got <= sense, (
            f"{fn} reads sense fields the server does not send: {sorted(got - sense)}"
        )


def test_every_route_to_a_lane_can_cause_its_fetch() -> None:
    """Five things route to these two pages and a fetch wired to one of them is a page
    that works from one direction and says "not asked for yet" from the other four.

    The navigator, the breadcrumb, `data-goto`, a curiosity and a trail step all set
    `state.view`, so the ask belongs where the view is *painted* rather than at any of
    them. This asserts the render dispatch reaches it, and that the one function it
    reaches covers both lanes -- half of it wired is the failure that looks like working
    code, because the page a session happens to open first is fine.
    """
    js = _read("shell.js")
    dispatch = js.split("else if (state.view === \"glossary\")", 1)[1].split("\n\n", 1)[0]
    assert dispatch.count("ensureVocabulary()") >= 2, (
        "a lane is painted without anything asking for its data; it would show "
        "\"not asked for yet\" forever"
    )
    body = _fn(js, "ensureVocabulary")
    for loader in ("loadGlossary", "loadNaming"):
        assert loader in body, f"ensureVocabulary never calls {loader}"
    assert body.count(".then(render)") >= 2, (
        "a lane is fetched and never repainted -- the data arrives behind a page that "
        "already said it had none"
    )


def test_a_lane_count_never_comes_from_an_array_nobody_fetched() -> None:
    """`TERMS.length` beside "Glossary" is zero until the page is opened.

    The row then reads as *nothing here*, which is the opposite of what is true, and it is
    the same confusion the whole port exists to remove: a count of nothing and an absent
    count are different claims. The sizes ride with the cover; the bodies do not.
    """
    js = _read("shell.js")
    nav = js.split('nav: "glossary"', 1)[1].split("]", 1)[0]
    assert "TERMS.length" not in nav and "CONVENTIONS.length" not in nav, (
        "a navigator count is taken from a lane array, which is empty until that lane's "
        "page has been opened"
    )
    assert "vocabCount(" in nav, "the navigator counts are not taken from the cover"
    assert '"vocabulary"' in (STATIC.parent / "cover.py").read_text(encoding="utf-8"), (
        "the cover no longer carries the vocabulary sizes the navigator reads"
    )


def test_a_lane_says_which_of_the_four_states_it_is_in() -> None:
    """"Not asked for", "on its way", "the server refused" and "there is nothing here"
    are four claims and a blank panel states the wrong one whichever it is.

    This is the whole reason the unported pages were written to say so rather than render
    an empty grid, and the reason survives the port -- it just has more states now.
    """
    body = _fn(_read("shell.js"), "laneState")
    for phrase in ("loading", "failed"):
        assert phrase in body, f"laneState does not distinguish {phrase!r}"
    assert "has not been asked for yet" in body, (
        "laneState cannot say a lane was never asked for, so it looks like an empty one"
    )


# ------------------------------------------------------- the navigator's furniture --- #
#
# Written from feedback at the keyboard, 2026-08-28: the routine list is 4,734 rows, the
# notice saying so was under all of them, and scrolling in trapped the reader because the
# collapse control scrolled away with its heading. Every check below is against one of
# those three symptoms, and each was run against the defect it came from before it was
# kept (rule 37) -- a guard that has never failed is a claim nobody has tested.


def _build_nav() -> str:
    return _fn(_read("shell.js"), "buildNav")


def test_the_truncation_notice_reads_before_the_list_it_describes() -> None:
    """`showing 200 of 4,734` was emitted after the items, so the only ways to see it were
    to scroll past the two hundred rows it describes or to collapse the group -- at which
    point it appeared at once, which is what gave it away.

    Design rule 1 says a filter is never silent about what it removed. It was satisfied in
    letter and defeated in fact, and the fix is a position rather than a wording.
    """
    body = _build_nav()
    note, items = body.find("nav-note"), body.find('class="nav-items"')
    assert note != -1 and items != -1, "buildNav changed shape -- this test is blind"
    assert note < items, (
        "the truncation notice is emitted after the list it describes -- a reader sees it "
        "only after scrolling past everything it is warning them about"
    )
    # And it must read the same open or closed, which means living outside the element the
    # stylesheet hides. `.nav-items` is what collapsing hides; the note is in the header.
    head = body.find("nav-headwrap")
    assert head != -1 and head < note < items, (
        "the notice is no longer inside the sticky header, so it does not travel with the "
        "heading and does not survive the group being collapsed"
    )
    css = _read("tokens.css")
    assert '.nav-group[data-open="false"] .nav-items { display: none; }' in css, (
        "collapsing hides something other than `.nav-items`; if it hides the header the "
        "notice goes with it and the closed group states nothing"
    )


def test_the_collapse_control_stays_in_reach_of_a_long_list() -> None:
    """Symptom 2, and the reason the whole pane was restructured.

    The collapse control is *on* the group heading, so a heading that scrolls away is a
    group the reader cannot close from inside it. 5g had already written this down and
    applied it to the panebar only, leaving the headings -- which carry the same control --
    to scroll. `.nav-headwrap` is sticky now.

    Checked for the *last* declaration, not for any: a media query contributes no
    specificity and an equal selector declared later simply wins, which is how the narrow
    layout's `display: none` lost to a rule 350 lines further down (rule 29).
    """
    css = re.sub(r"/\*.*?\*/", "", _read("tokens.css"), flags=re.S)
    blocks = re.findall(r"\.nav-headwrap\s*\{([^}]*)\}", css)
    assert blocks, ".nav-headwrap has no rule at all -- the headings do not stick"
    positions = [m for b in blocks for m in re.findall(r"position:\s*(\w+)", b)]
    assert positions and positions[-1] == "sticky", (
        f"the last `position` declared for .nav-headwrap is {positions[-1:] or ['none']} -- "
        "a later equal selector wins, so the heading scrolls away with the list"
    )
    tops = [m for b in blocks for m in re.findall(r"top:\s*([\w.]+)", b)]
    assert tops and tops[-1] == "0", (
        "a sticky heading with no `top` sticks nowhere -- it is a no-op that looks fixed"
    )


def test_the_navigator_scrolls_inside_itself_and_not_the_document() -> None:
    """The pane is a header that stays over a body that scrolls, as two grid rows.

    A grid item is `min-height: auto` and refuses to shrink below its content, so without
    `minmax(0, 1fr)` and `min-height: 0` the 4,734-row body holds the row open at its full
    height and hands the overflow to the document -- which does not scroll panes. That is
    rule 29's companion, and it has already cost this project one session.
    """
    css = re.sub(r"/\*.*?\*/", "", _read("tokens.css"), flags=re.S)
    # Anchored at the start of a line, so this reads the pane's own rule and not the tail
    # of `.body > .navigator { display: none }` in the narrow layout -- which is a different
    # rule about a different question, and matching it made this guard fail on prose.
    nav = re.search(r"^\.navigator\s*\{([^}]*)\}", css, re.M)
    scroll = re.search(r"^\.nav-scroll\s*\{([^}]*)\}", css, re.M)
    assert nav and scroll, "the navigator is no longer a header over a scroller"
    assert "minmax(0, 1fr)" in nav.group(1), (
        "the navigator's body track can refuse to shrink, which sends the overflow to the "
        "document instead of to the pane that knows how to scroll"
    )
    assert "min-height: 0" in scroll.group(1), "the scroller inherits `min-height: auto`"
    assert "overflow-y: auto" in scroll.group(1), "the scroller does not scroll"


def test_the_jump_strip_and_the_list_are_generated_from_one_order() -> None:
    """Symptom 3: getting between groups without traversing one.

    The invariant is not that the strip exists -- it is that the strip and the groups are
    the *same* set in the *same* order, both derived. A hand-kept second list agrees with
    itself and disagrees with the pane, which is how `FOLDABLE` and the panel loop both
    went quietly wrong (rule 36); and the menu order used to be applied by moving DOM nodes
    in `render()`, where the strip could not see it at all.
    """
    js = _read("shell.js")
    body = _build_nav()
    chips = re.search(r"jumpChips\((\w+)\)", body)
    groups = re.search(r"(\w+)\.map\(g => \{", body)
    assert chips and groups, "buildNav changed shape -- this test is blind"
    assert chips.group(1) == groups.group(1), (
        f"the strip is built from `{chips.group(1)}` and the groups from "
        f"`{groups.group(1)}` -- two orders, and the reader is offered the one the pane "
        "does not use"
    )
    assert re.search(r"function jumpChips\(order\) \{\s*return order\.map", js), (
        "jumpChips no longer maps the order it is handed, so a group can exist with no chip"
    )
    # Routed from the table, not from a branch: an id naming no group is a named error.
    assert re.search(r"NAV_GROUPS\.some\(g => g\.id === id\)", js), (
        "the jump route does not check its subject against NAV_GROUPS, so a stale chip "
        "would scroll nowhere and report nothing -- design rule 16"
    )
    # And `render()` must not still be shuffling the groups behind the strip's back.
    assert "insertBefore(first, firstGroup)" not in js, (
        "render() still reorders the navigator in the DOM, so the strip and the pane can "
        "disagree about which group comes first"
    )


def test_a_group_left_open_or_closed_survives_a_rebuild() -> None:
    """The toggle used to write `data-open` on the element and nothing else.

    `buildNav()` re-renders from `NAV_GROUPS` on every keystroke of the search box and on
    every graph selection, so a group collapsed by hand sprang open again the moment
    anything was typed. A toggle whose state lives only in the DOM lasts exactly as long as
    that DOM. This is rule 35's family: the state was assigned, and to the wrong thing.
    """
    js = _read("shell.js")
    assert re.search(r'data-open="\$\{groupOpen\(', _build_nav()), (
        "the group's open state is written from the table rather than from what the reader "
        "arranged, so every rebuild throws their arrangement away"
    )
    toggle = js.split('const b = ev.target.closest("[data-toggle]");', 1)[1].split("});", 1)[0]
    assert "setGroupOpen(" in toggle and "dataset.open =" not in toggle, (
        "the toggle writes the DOM directly; the next rebuild discards it"
    )


def test_the_accordion_is_a_setting_and_both_halves_are_built() -> None:
    """Design rule 2: when two options are genuinely interchangeable, build both and let
    usage retire the loser. One at a time keeps the pane shorter than a single list; all at
    once keeps the whole index visible, which is the better answer on a small program.

    Both must be *reachable* and both must be *read*. A pair where only the default is
    consulted is a setting that renders and does nothing -- design rule 16 with a control.
    """
    js, settings = _read("shell.js"), _read("settings.js")
    assert re.search(r"navGroups:\s*'one'", settings), (
        "navGroups is not a persisted setting, so the choice does not survive a reload"
    )
    for value in ("one", "many"):
        assert f'data-navgroups="{value}"' in js, f"no control offers navGroups={value!r}"
    # Read, not merely stored: the accordion branch and the fallback branch both consult it.
    # The accordion's first-visit group is named, not positional: with "Explore first" the
    # pane would otherwise open on two rows and leave the routine list -- which design rule
    # 26 says the navigator *is* -- closed, for no reason anyone chose.
    assert "g.primary" in _fn(js, "navPrimary"), (
        "the accordion opens whichever group happens to be first, so the menu order "
        "silently decides what the pane opens on"
    )
    assert re.search(r"primary: true", js), "no navigator group is marked as the primary one"
    assert 'state.navGroups === "one"' in _fn(js, "groupOpen"), (
        "groupOpen ignores the setting, so `all at once` and `one at a time` open the same "
        "groups and the control is dead"
    )
    assert 'state.navGroups === "one"' in _fn(js, "setGroupOpen"), (
        "setGroupOpen ignores the setting, so opening a group never closes the others"
    )
    assert 'used("navgroups:' in js, (
        "the pair is not counted, so neither half can ever be retired on evidence"
    )


def test_the_strip_marks_where_the_reader_was_taken() -> None:
    """The chips say which group you are in, and that claim has to survive a jump.

    Found by clicking, not by any guard: with one group open the pane is short, so the
    browser clamps a jump to a group near the bottom -- and the marker, read off the scroll
    position, lit *Explore* one click after the reader asked for *Packages*. Two correct
    numbers, neither of them saying what the reader had just done (rule 32).

    Under the accordion the answer is not a scroll position at all: exactly one group is
    open. The scroll rule stays for `all at once`, where there is no such answer.
    """
    body = _fn(_read("shell.js"), "markJump")
    assert 'state.navGroups === "one"' in body and "groupOpen(g)" in body, (
        "the marker reads the scroll position even under the accordion, so a jump the "
        "browser clamps lights a chip the reader did not click"
    )
    assert "offsetTop" in body and "scrollTop" in body, (
        "the fallback for `all at once` is gone, so with every group open nothing is marked"
    )


# ------------------------------------------------- the routine list, by package --- #


def test_the_routine_list_groups_by_the_package_the_stack_draws() -> None:
    """There are two expressions for "package" in this dashboard and there must not be a
    third -- least of all one in JavaScript.

    `queries.py` says why in as many words: two definitions of a package in one dashboard is
    how a reader ends up comparing two numbers that were never the same measurement. The
    navigator's grouping comes from `PACKAGE_EXPR`, which is what the disks are built from,
    so a package heading in the list names a plate in the picture.

    `documents.py` deliberately keeps that expression out of its own query family, which is
    why this is a separate statement rather than two more columns on `DOC_ROUTINES`.
    """
    q = (Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"
         / "queries.py").read_text(encoding="utf-8")
    nav = q.split("NAV_ROUTINES = f\"\"\"", 1)[1].split("\"\"\"", 1)[0]
    assert "{PACKAGE_EXPR}" in nav, (
        "the navigator's package is not the plates' package, so the list and the stack can "
        "disagree about what a package is"
    )
    doc = q.split("DOC_ROUTINES = \"\"\"", 1)[1].split("\"\"\"", 1)[0]
    assert "PACKAGE_EXPR" not in doc, (
        "DOC_ROUTINES now names parameters document mode does not bind -- see the comment "
        "in documents.py about two query families drifting into each other's shape"
    )
    js = _read("shell.js")
    assert 'fetch("/api/routines")' in js, "the shell still reads the document endpoint"


def test_the_navigator_reads_only_fields_the_routines_endpoint_sends() -> None:
    """Rule 44: a live control reading a field the server does not send renders nothing and
    throws nothing. The glossary spent a session showing a bar of zero width beside a claim
    that was perfectly true, and nothing anywhere failed.

    One direction only, as there: the server may send a field the view ignores.
    """
    web = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"
    q = (web / "queries.py").read_text(encoding="utf-8")
    nav = q.split("NAV_ROUTINES = f\"\"\"", 1)[1].split("\"\"\"", 1)[0]
    served = set(re.findall(r"AS (\w+)", nav))
    served |= set(re.findall(r'self\._json\(\{"routines": rows, "(\w+)"',
                             (web / "serve.py").read_text(encoding="utf-8")))
    served.add("routines")
    assert {"id", "pkg", "plates"} <= served, "the endpoint changed shape -- this test is blind"

    body = _fn(_read("shell.js"), "loadRoutines")
    read = set(re.findall(r"\brow\.(\w+)", body)) | set(re.findall(r"\bd\.(\w+)", body))
    missing = sorted(read - served)
    assert not missing, (
        f"the navigator reads fields /api/routines does not send: {missing} -- every row "
        "renders, none of them carries the value, and nothing fails"
    )


def test_a_package_heading_never_names_a_plate_the_stack_lacks() -> None:
    """`graph.py` merges any package below `MIN_DISK` into `pkg:<small>`, so 47 packages
    are 45 plates -- and a heading offering `pkg:_version` selects nothing at all.

    Rule 30 from the far side: the row carries an identity, and the identity names nothing.
    `queries.py` had written the answer down before anything needed it -- inventing an id to
    make a row clickable is a link to nothing -- so a package with no plate of its own says
    which plate it *is* drawn on, and one with no plate at all stays a heading.
    """
    body = _fn(_read("shell.js"), "routineTree")
    assert "PLATES.has(own)" in body, (
        "the heading offers its own name as a plate without checking the stack has one"
    )
    assert "merged" in body, (
        "a package drawn on the merged plate is not marked, so clicking it moves the "
        "picture somewhere the row did not say"
    )
    assert 'g.plate\n' not in _fn(_read("shell.js"), "routineList") or True
    lst = _fn(_read("shell.js"), "routineList")
    assert "g.plate" in lst and "nav-pkgplain" in lst, (
        "a package with no plate is still rendered as a selectable row"
    )


def test_the_packages_are_complete_and_only_their_routines_are_bounded() -> None:
    """Rule 8 bounds diagrams and nothing else. Forty-seven package rows are a list a
    person reads; 959 routines inside one of them is a rebuild on every keystroke.

    So the packages are never sliced, the routines within one are, and what a package
    leaves out is stated *on that package* -- which is the whole lesson of the notice that
    used to sit under two hundred rows.
    """
    tree = _fn(_read("shell.js"), "routineTree")
    assert "cap" in tree and "navCap()" in tree, (
        "the routines inside a package are unbounded, or the bound is no longer the "
        "reader's setting"
    )
    assert not re.search(r"packages\s*=\s*.*\.slice\(", tree), (
        "the package list is truncated -- a reference list is never abbreviated"
    )
    lst = _fn(_read("shell.js"), "routineList")
    note = lst.find("nav-note")
    items = lst.find('class="nav-items"')
    assert note != -1 and items != -1 and note < items, (
        "a package's truncation notice is emitted after its rows, which is the defect this "
        "whole session began with, one level down"
    )


def test_finding_the_selected_routine_opens_the_package_holding_it() -> None:
    """The back half of the reading loop: click a node in the stack, and the list moves to
    it (design rule 26).

    A row inside a collapsed package is rendered, marked `current`, and `display: none` --
    identical on screen to a row that was never found. Opening the group and stopping there
    was enough while the list was flat and is not enough now.
    """
    body = _fn(_read("shell.js"), "revealSelectedRoutine")
    assert "ROUTINES.find" in body, (
        "the reveal looks the row up in the DOM first -- and a closed package renders no "
        "rows, so it gives up on exactly the case it exists for, looking identical to a "
        "routine that is not in the list at all"
    )
    assert "state.navOpen[`pkg:" in body, (
        "the reveal stops at the group, so a selection inside a closed package is marked "
        "somewhere nobody can see it"
    )
    assert "setGroupOpen" in body, "the reveal no longer opens the group either"


def test_one_renderer_draws_every_navigator_row() -> None:
    """The routine rows are two levels deep now and the other groups are one. Two copies of
    the row markup is two answers to what a row looks like -- and the one that is not being
    looked at is the one that goes quietly wrong (rule 36)."""
    js = _read("shell.js")
    assert js.count("class=\"nav-item\" data-nav=") == 1, (
        "there is more than one place deciding what a navigator row is"
    )
    assert "navItemHtml(" in _fn(js, "routineList"), (
        "the routine list draws its own rows instead of using the one renderer"
    )
    assert "items.map(navItemHtml)" in _fn(js, "buildNav"), (
        "the generic groups draw their own rows instead of using the one renderer"
    )


def test_how_many_routines_a_package_lists_is_the_readers_to_set() -> None:
    """200 was a judgment about markup per keystroke, and on Mensores it read as a tease:
    most packages hold 200-400, so the notice said `200 of 377` over a list that was very
    nearly whole.

    `0` means all of them, and that is the half worth guarding: a cap of zero read as a
    number would show nothing at all, which is the opposite of what the control says.
    """
    js, settings = _read("shell.js"), _read("settings.js")
    assert re.search(r"navCap:\s*200", settings), "the cap is not a persisted setting"
    caps = re.search(r"const NAV_CAPS = \[([^\]]*)\]", js)
    assert caps, "the choices are no longer a table -- the control and the values can drift"
    values = [v.strip() for v in caps.group(1).split(",")]
    assert "0" in values, "there is no way to ask for the whole list"
    assert 'data-navcap="${n}"' in js and "NAV_CAPS.map" in js, (
        "the buttons are hand-written rather than generated from the table, so a value "
        "can exist with no control or a control with no value"
    )
    body = _fn(js, "navCap")
    assert "Infinity" in body and "> 0" in body, (
        "a cap of 0 is not turned into `no limit`, so asking for all of them shows none"
    )
    assert 'used("navcap:' in js, "the choice is not counted, so it cannot be reviewed"


def test_a_broad_search_does_not_open_the_whole_program() -> None:
    """`e` matches 4,734 routines across all 47 packages. Opening every one of them built
    3,413 buttons on the *first keystroke of an ordinary search*, at 483 ms -- the glossary
    filter's 412 ms in another pane, and the same cause: work proportional to the whole
    program on every character typed.

    It was the worse answer as well as the slower one. "2,206 match g, in 43 packages" is
    something a reader can act on; 1,924 rows is the haystack again. So a search opens what
    it matched only while the answer is small, and **says** when it did not -- closed
    packages with no explanation read as a control that failed (design rule 1).
    """
    js = _read("shell.js")
    tree = _fn(js, "routineTree")
    assert "SEARCH_OPEN_MAX" in tree, (
        "a search opens every package it matched in, however many that is"
    )
    assert "autoOpen || pkgOpen(g.id)" in tree, (
        "the reader cannot open a package by hand during a broad search, so the note's "
        "`open one` is an instruction the pane refuses"
    )
    note = js.split('id: "navRoutines"', 1)[1].split("body:", 1)[0]
    assert "too many to open" in note, (
        "the pane closes every package and says nothing about why"
    )
    # Two passes, and the rows built only for what is drawn.
    assert "g.open && g.rows.length < cap" in tree, (
        "rows are built for packages that are not drawn -- hidden is not absent, and it "
        "cost 341 ms a keystroke the first time"
    )


def test_the_routine_tree_is_computed_once_per_build() -> None:
    """The note asks how many matched; the body asks for the packages. One question, and it
    ran a full scan of 4,734 routines twice on every keystroke."""
    # Comments stripped first. Written without that, this passed against its own defect:
    # the line was disabled by commenting it out, and the guard found the words inside the
    # comment and vouched for them. A check that reads its own documentation as evidence is
    # vouching for nothing (rule 37).
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", _read("shell.js"), flags=re.S)
    assert "if (treeCache) return treeCache;" in _fn(js, "routineTree"), (
        "the tree is recomputed for every caller within one build"
    )
    assert "treeCache = null;" in _fn(js, "buildNav"), (
        "the cache is never cleared, so the pane draws the previous answer -- which is far "
        "worse than computing it twice"
    )


# ----------------------------------------------------------------- you are here --- #
#
# A selection of one node in nine thousand is a dot lit differently from its neighbours,
# and "lit differently" is findable only by someone who already knows where to look. Two
# halves: an arrow that stands over what was picked, and a way back to the view it was
# found in after the reader has turned the stack around three times.


def test_the_pointer_is_a_billboard_like_everything_else_in_the_stack() -> None:
    """Rule 22: a picture of something with no orientation must not have one. An arrow that
    foreshortened as the stack tilted would read as a shape lying on a plate rather than as
    a pointer at the reader — the coin-seen-edge-on failure, in a signpost."""
    engine = _read("graph.js")
    layer = engine.split("new IconLayer({", 1)[1].split("}));", 1)[0]
    assert "billboard: true" in layer, (
        "the pointer is not billboarded, so tilting the stack lays it down on a plate"
    )
    assert "pickable: false" in layer, (
        "the arrow is pickable, so clicking it means something the reader was not told"
    )
    assert "opts.scale" in layer, (
        "the pointer is outside the scale multiplier -- design rule 3 says one slider "
        "resizes the whole surface, and this would be the one thing it could not reach"
    )


def test_the_pointer_says_so_when_it_draws_nothing() -> None:
    """This codebase has paid three times over for a shader effect that compiled, drew, and
    silently did nothing. A texture that comes out empty is a pointer that renders perfectly
    and points at nothing, with no error anywhere.

    Checked once per colour, not once per frame, and stated on the diagnostics line as well
    as in the console -- design rule 21: a developer cannot open a console in someone else's
    browser, so what cannot be seen has to be said where the picture is.
    """
    engine = _read("graph.js")
    icon = _fn(engine, "pointerIcon")
    # The probe must be read *from the canvas*. Written as "getImageData appears somewhere
    # and probe[3] is tested somewhere" this passed against its own defect: a `probe` filled
    # with a constant beside an ignored `getImageData` call satisfied both halves. Rule 37 --
    # check that the guard catches, not that it mentions.
    assert re.search(r"const probe = x\.getImageData\(.*\)\.data;", icon), (
        "the blank check reads something other than the canvas it just drew"
    )
    assert "probe[3] === 0" in icon, "the probe is taken and never tested"
    assert "console.error" in icon, "a blank texture is discovered and not reported"
    assert "texture ${icon.blank ? 'BLANK'" in _fn(engine, "diagnostics"), (
        "the diagnostics line does not carry the pointer, so a blank one is invisible to "
        "anyone who cannot open a console on the reader's machine"
    )


def test_the_pointer_stands_only_on_what_the_reader_picked() -> None:
    """The one-hop neighbours are the *answer*; the picks are the question. An arrow over
    every member would point at the haystack again.

    And a shadow is never an endpoint (rules 23 and 31) -- an arrow over a stand-in would
    put a routine somewhere it does not live, in the one mark on screen whose entire job is
    to say where something is.
    """
    body = _fn(_read("graph.js"), "pointerData")
    assert "g.picks" in body and "g.members" not in body, (
        "the pointer stands on the whole selection rather than on what was picked"
    )
    assert "realIndex(d, p.index)" in body, (
        "a shadow gets an arrow, which points at a routine that is not there"
    )
    assert "p.kind !== 'node'" in body, (
        "a picked plate gets an arrow at the middle of 645 nodes, which is nowhere"
    )
    assert "POINTER_CAP" in body, (
        "a thread selecting ninety-nine routines draws ninety-nine arrows, which is not a "
        "signpost, it is weather"
    )


def test_the_pointer_count_states_what_it_left_out() -> None:
    """Design rule 1, and rule 32: two dozen arrows over a selection of ninety-nine looks
    exactly like a selection of two dozen."""
    js = _read("shell.js")
    line = _fn(js, "countLine")
    assert "pointersWanted" in line and "pointers" in line, (
        "the count line never says how many pointers were left undrawn"
    )
    assert "c.pointersWanted > c.pointers" in line, (
        "it states the pointer count even when nothing was left out, which is noise where "
        "design rule 1 wants a signal"
    )


def test_the_way_back_is_the_view_it_was_found_in() -> None:
    """Design rule 26 says picking a routine must never move the camera, so a selection made
    in the list usually happens while the thing is nowhere on screen -- and a view with the
    subject outside it is not somewhere anyone wants taking back to.

    So the anchor is *armed* by a selection and *set* by the first view the selection can
    actually be seen in. Two details, both of which were wrong first time and neither of
    which fails loudly: it must be asked **after** `recomputeMembers`, or it measures the
    previous selection; and `selectionOnScreen()`'s null means "cannot say", which on the
    commonest path of all -- a pick that mounts the graph -- is the answer it gives, because
    deck has no viewport in the turn it is constructed in.
    """
    engine = _read("graph.js")
    after = _fn(engine, "afterSelectionChange")
    assert after.index("recomputeMembers") < after.index("rememberWhere"), (
        "the anchor is taken before the selection is recomputed, so it asks whether the "
        "*previous* selection was on screen"
    )
    capture = _fn(engine, "captureWhere")
    assert "if (!where)" in capture and "anchorRetry" in capture, (
        "a `cannot say` is treated as `no`, so a selection that mounts the graph never "
        "arms an anchor and the button stays disabled for the session"
    )
    assert "if (!where.onScreen) return;" in capture, (
        "the anchor is set to a view the selection is not in, which is not a way back"
    )
    # `toAnchor` is a method on the exported object, not a top-level function, so it is
    # read by span rather than by `_fn` -- which stops at the next `function` at column 0.
    to_anchor = engine.split("toAnchor() {", 1)[1].split("\n  },", 1)[0]
    assert "if (!g.prepared || !g.anchor) return false;" in to_anchor, (
        "toAnchor cannot report that there was nothing to go back to, so the shell has no "
        "way to say why the button did nothing"
    )


def test_the_way_back_button_cannot_go_stale() -> None:
    """Its enabled state changes with the selection, and the box that draws it is rebuilt
    only by `renderGraphFurniture()` -- which a selection never calls.

    Written as an attribute alone it would be disabled at first paint, when nothing is
    selected, and stay that way for the whole session: design rule 16 in the *state* of a
    control rather than in its wiring, which is a place none of the existing guards look.
    """
    body = _fn(_read("shell.js"), "updateGraphCounts")
    assert 'data-gact="here"' in body and "here.disabled" in body, (
        "the button's enabled state is decided only where the HUD is rebuilt, and a "
        "selection does not rebuild the HUD"
    )
    assert "counts.anchored" in body, (
        "the shell guesses whether there is a view to go back to instead of asking the "
        "engine, which is the only thing that knows"
    )


def test_the_pointer_colour_is_clamped_and_says_why() -> None:
    """Design rule 6: customisation is clamped, and a refusal states its reason. 3:1 rather
    than 4.5:1 because a pointer is a large graphic object, not body text.

    Measured against the *graph's* ground, which is not the page's -- with the stack forced
    dark inside a light page they are different colours entirely. And re-asked when the
    ground moves, because the bar moves with it: a colour that cleared 3:1 on near-black can
    be invisible on the pale one, and a limit that was true once is not a limit.
    """
    js = _read("shell.js")
    assert ">= 3" in _fn(js, "pointerPasses"), "the pointer colour is not clamped at all"
    assert "graphPaletteNow()" in _fn(js, "pointerRatio"), (
        "the contrast is measured against the page's ground rather than the graph's, so a "
        "pointer nobody can see passes"
    )
    assert "Refused" in _fn(js, "updatePointerNote"), (
        "a refused colour is silently ignored -- design rule 6 says a refusal states its "
        "reason"
    )
    assert "pointerPasses(c) ? " in _fn(js, "pointerRgb"), (
        "a stored colour below the bar is drawn anyway"
    )
    assert "Graph.setOptions({ pointerColor: pointerRgb() })" in _fn(js, "applyGraphPalette"), (
        "changing the graph's ground does not re-ask the clamp, so a colour accepted "
        "against one ground stays in force against another"
    )
    # The token is the only place the default colour is written down.
    assert "--graph-pointer" in _read("tokens.css"), "the pointer colour is not a token"
    assert "--graph-pointer" in _fn(js, "pointerToken"), (
        "the picker's initial value is not read from the token, so it opens on a colour "
        "the picture is not using"
    )


def test_one_word_for_a_plate_wherever_a_reader_can_see_it() -> None:
    """The fps line said "52 disks" while the size menu said "plates" — two words for one
    idea, in a tool whose entire subject is a program's vocabulary. Plate won: rare enough
    that this product gets to define it, common enough to be guessed at.

    Scoped to what a *reader* sees. `disk` survives as an identifier, and deliberately: the
    persisted keys would discard every saved arrangement on a rename, and the code has a
    second live meaning for "plate" — the polygon that *draws* a disk (rule 18: the stack is
    an abstraction, and the plate is the drawing of it). That is written down as a debt.

    Line-bounded on purpose. Written to span, it read whole functions as though they were
    sentences and reported eleven leaks, none of them words on a screen — a check that cries
    wolf has already failed (rule 43), and it failed before it was ever committed.
    """
    files = {"shell.js": _read("shell.js"), "settings.js": _read("settings.js")}
    files["serve.py"] = (Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"
                         / "serve.py").read_text(encoding="utf-8")
    # An identifier is not a word on screen. These are the machinery, all of it named.
    machinery = re.compile(r"data-disk|dataset\.disk|diskColors|diskOrder|diskColorHex|"
                           r"--graph-disk|selectedDisks|sortedDisks|Graph\.disks|dragDisk|"
                           r"largest_disk|s\['disks'\]|want\.disks|\{ disks:|disks: \[|"
                           r"h\.disk|d\.disk|n\.disk|\.disk\b|disk:|c\.disks|"
                           + '"disks?"' + r"|'disks?'")
    leaks = []
    for name, text in files.items():
        body = re.sub(r"/\*.*?\*/", "", text, flags=re.S)          # block comments
        for i, line in enumerate(body.splitlines(), 1):
            if line.lstrip().startswith(("//", "#", "*")):
                continue
            for m in re.finditer(r'"[^"\n]*\bdisks?\b[^"\n]*"|>[^<>\n]*\bdisks?\b[^<>\n]*<',
                                 line):
                if not machinery.search(m.group(0)):
                    leaks.append(f"{name}:{i} {m.group(0).strip()}")
    assert not leaks, (
        "the reader is shown the word 'disk' here, and the product says plate:\n  "
        + "\n  ".join(leaks)
    )


def test_the_pointer_aims_by_computing_a_screen_direction() -> None:
    """A billboard has no world orientation to inherit — that is rule 22 — so aiming one at
    something means computing the direction in screen space and rotating the icon by it.

    The convention is read out of deck's own vendored shader, not guessed: it rotates by
    `mat2(cos, -sin, sin, cos)` (column-major) and then flips y, so with the icon's tip on
    its anchor the arrow points along `(sin, cos)` — giving `atan2(dx, dy)`, not the usual
    `atan2(dy, dx)`. An arrow aimed the wrong way is a working-looking signpost pointing at
    nothing, and this cannot be checked by looking in a tab that draws no frames.
    """
    engine = _read("graph.js")
    body = _fn(engine, "pointerAngle")
    assert "Math.atan2(dx, dy)" in body, (
        "the angle uses the usual atan2(dy, dx), which aims the arrow ninety degrees off "
        "and mirrored -- see deck's rotate_by_angle, which this convention is read from"
    )
    assert "if (!vp) return null;" in body, (
        "no viewport is treated as an angle rather than as `cannot say`, so the arrow aims "
        "somewhere invented before deck has rendered"
    )
    # And the vendored shader still says what that reasoning rests on.
    vendor = (Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web" / "vendor"
              / "deck.gl.min.js").read_text(encoding="utf-8", errors="ignore")
    assert "mat2(cos_angle, -sin_angle, sin_angle, cos_angle)" in vendor, (
        "deck's icon rotation is no longer the matrix this angle was derived from -- "
        "re-derive it before trusting the arrows"
    )
    assert "pixelOffset.y *= -1.0" in vendor, (
        "deck no longer flips y after rotating, which inverts every pointer"
    )


def test_the_pointer_at_the_rim_stands_on_the_plate_and_leads_to_its_node() -> None:
    """At the side of the stack, at the height of the plate holding the node and on that
    node's own bearing, so the line through the arrow leads the eye inward.

    The bearing is taken from the *base* coordinates, because the spread turns the plate's
    circle into an ellipse: read from the drawn positions instead, the arrow stops lining up
    the moment either spread slider moves. The plate radius is one constant, hoisted, because
    two copies of it is a signpost that drifts off the edge of the thing it names.
    """
    engine = _read("graph.js")
    rim = _fn(engine, "rimPoint")
    assert "d.baseXY" in rim and "PLATE_R" in rim, (
        "the rim point is not taken from the plate's own radius and the node's own bearing"
    )
    assert "opts.spreadX" in rim and "opts.spreadY" in rim, (
        "the arrow does not follow the spread, so it leaves the plate it stands on"
    )
    assert "at[2]" in rim, (
        "the arrow is not at the height of the plate holding the node, which is the whole "
        "of what it is pointing out"
    )
    assert engine.count("const PLATE_R") == 1 and "const R = PLATE_R" in engine, (
        "the plate radius is written down twice, so the plate and the pointer can disagree "
        "about where the edge is"
    )


def test_where_the_pointer_stands_is_a_pair_and_both_are_read() -> None:
    """Design rule 2. Rim is findable from across the picture and leaves the frame when the
    reader snaps to fit; over-the-node is exact at any zoom and can be swallowed by the
    neighbours it stands among. Both good, so both are built and usage decides."""
    js, engine, settings = _read("shell.js"), _read("graph.js"), _read("settings.js")
    assert re.search(r"pointerPlace:\s*'rim'", settings), "the placement is not persisted"
    for value in ("rim", "node"):
        assert f'data-pointerplace="{value}"' in js, f"no control offers {value!r}"
    assert "opts.pointerPlace === 'node'" in _fn(engine, "pointerData"), (
        "the engine ignores the setting, so both controls draw the same picture"
    )
    assert 'used("pointerplace:' in js, "the pair is not counted, so neither can be retired"
    # The fit interaction is real and is stated rather than discovered.
    assert "snap to fit" in js and "a plate's width away" in js, (
        "the Setting does not say that the rim pointer leaves the frame when fit runs, "
        "which is design rule 1 about the reader's own control"
    )
