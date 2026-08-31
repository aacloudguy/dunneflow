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

import math
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


def _css_code(css: str) -> str:
    """CSS with its comments removed, so a check reads rules and not prose.

    The JavaScript `_code()` blanks comment *lines* and deliberately goes no further: a
    general stripper there has to track template literals, and a first attempt ate their
    bodies -- which is where the code being checked lives. **CSS has neither template
    literals nor nested comments**, so the whole-block strip that is unsafe there is exact
    here, and it catches the case line-blanking cannot: a comment whose continuation lines
    are plain indented prose naming the selector it is saying was removed.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


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
    """Every `nav` kind the generated navigator can produce.

    Scanned over the **whole shell**, not over the `NAV_GROUPS` literal. A group that
    builds its rows with `body:` — the routine list, the code list, the change worklist —
    calls `navItemHtml` from a function declared far outside that block, so a scan bounded
    to the literal could not see `nav: "routine"` or `nav: "file"` at all. It had been
    blind to the navigator's three most-clicked row kinds since those groups were written,
    and passed the whole time by having nothing to compare.

    Rule 54 in the guard itself: naming the wrong container is not a narrower check, it is
    no check. `\b` still matters — `sevnav: "broken"` is a severity, not a nav kind, and
    without the boundary this reported three dead routes that were never routes.
    """
    # Comment lines removed first. This read the raw source, so a *comment* naming an
    # attribute counted as markup writing one -- and the prose explaining why the pane
    # track was renamed away from `data-nav` reported the renamed value as a live nav kind
    # with no route. Rule 43 in the instrument, and the third guard in this file to fail on
    # the sentence describing the very thing it checks; `_code` exists for exactly that and
    # this helper predates it.
    js = _code(_read("shell.js"))
    # Both spellings. A row built through `navItemHtml` carries `nav: "x"`; one written
    # straight into a template literal carries `data-nav="x"`, and the code list does
    # exactly that — so matching only the first left `file` unchecked as well.
    # Interpolated values (`data-nav="${...}"`) are skipped: they are not literals and
    # this instrument cannot say what they will be, which it should admit rather than
    # guess at.
    kinds = set(re.findall(r'\bnav:\s*"([^"]+)"', js))
    kinds |= {k for k in re.findall(r'data-nav="([^"]+)"', js) if "$" not in k}
    return kinds


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

    Five sliders, each stepping 0.05, are genuinely hard to land by hand, and the only way
    back used to be a reload or the whole-settings reset — which also throws away the disk
    order, the colours and the selection. So `sizereset` resets exactly the sliders.

    Three halves, and the third arrived with `plateSize`. Every slider on screen must be in
    the `SLIDERS` table, or the reset silently leaves one where it was and reports success
    for the rest. Every key must exist in `DEFAULTS`, because the reset reads its values
    from there rather than carrying numbers of its own. And the reset must go through the
    table's **accessors**: `plateSize` is a map keyed by level, so `state[k] =
    Settings.DEFAULTS[k]` restores it correctly and then hands the engine an object where
    it expects a number — the picture keeps the old widths while the slider moves home,
    which is one control with two answers and the visible one is the wrong one (rule 67).
    """
    js = _read("shell.js")

    table = re.search(r"const SLIDERS = \{(.*?)\n\};", js, re.S)
    assert table, "the SLIDERS table is gone; the reset cannot know what it resets"
    reset = set(re.findall(r"^  (\w+):", table.group(1), re.M))
    assert reset, "the SLIDERS table changed shape -- this test is blind"
    assert "Object.keys(SLIDERS)" in js, (
        "SLIDER_KEYS no longer derives from the table -- a hand-kept second list agrees "
        "with a wrong implementation, which is the failure it was written to detect"
    )

    # Every range input in the controls box, taken from the markup rather than a list.
    controls = js.split('id="panel-controls"', 1)[1].split("</div>`", 1)[0]
    ids = set(re.findall(r'<input id="(g\w+)" type="range"', controls))
    assert ids, "no range inputs found in the controls box -- this test is blind"
    ID_TO_KEY = {"gsize": "nodeSize", "gspreadx": "spreadX", "gspready": "spreadY",
                 "gspreadz": "spreadZ", "gwidth": "plateSize"}
    unknown = ids - set(ID_TO_KEY)
    assert not unknown, (
        f"sliders this test cannot name: {sorted(unknown)} — add them to ID_TO_KEY, and "
        "to SLIDERS, or the reset leaves them where they were"
    )
    sliders = {ID_TO_KEY[i] for i in ids}

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
    for call in ("sliderGet(k)", "sliderSet(k, sliderDef(k))", "sliderDef(k)"):
        assert call in js, (
            f"the reset no longer goes through {call} — a per-level slider read or "
            "written as a flat key hands the engine an object and moves the control home "
            "over a picture that did not change"
        )
    assert "Settings.DEFAULTS" in js, (
        "the reset has stopped reading Settings.DEFAULTS — a second copy of a default "
        "is a second thing to forget when one of them moves"
    )


def _fn(js: str, name: str) -> str:
    """One top-level `function name(...)`, from its keyword to its closing brace.

    **By brace depth, and there was briefly a second helper of this name that was not.** It
    ran to the next `function` at column 0, which is a different span: everything between
    two functions -- trailing prose, a hoisted constant, a comment naming the very thing a
    guard was checking for the absence of. That version had already been narrowed once, to
    make `\nasync function` count, because a guard reading "the fields `loadRoutines` reads"
    had been reading `loadAnomalies` as well and failing on a field the endpoint it names
    has no reason to send.

    Two helpers with one name is the same defect one level up (rule 51), and the later
    definition silently won for every caller of the earlier -- so a guard could be read,
    reviewed and mutation-tested against a helper other than the one written beside it.
    One of them, and it is the one that reads exactly what it claims: a check for what a
    function does *not* contain is only as good as the span it is taken over (rule 37).
    """
    start = js.index(f"function {name}(")
    # **Past the parameter list before counting braces.** A destructured parameter --
    # `setGraphDetail({ level, minDisk })`, `mount(container, raw, options = {})` -- opens
    # and closes a brace in the signature, so counting from the first `{` returns the
    # signature and nothing else. Four guards passed on that: an *absence* check over an
    # empty span is vacuously true, and a presence check fails loudly, which is the only
    # reason it was caught at all.
    depth = 0
    for j in range(js.index("(", start), len(js)):
        if js[j] == "(":
            depth += 1
        elif js[j] == ")":
            depth -= 1
            if depth == 0:
                break
    else:
        raise AssertionError(f"function {name} has no parameter list")

    i = js.index("{", j)
    depth = 0
    for k in range(i, len(js)):
        if js[k] == "{":
            depth += 1
        elif js[k] == "}":
            depth -= 1
            if depth == 0:
                return js[start:k + 1]
    raise AssertionError(f"function {name} never closes")


def test_a_plates_width_is_taken_from_what_is_drawn_on_it() -> None:
    """Sizing a plate by its content means its **real nodes**, never nodes plus shadows.

    A shadow is never drawn (rule 23) -- it is a placement device standing in for something
    living elsewhere -- so the density a reader actually sees is nodes over area however
    many of them share the disc. Mensores' `ext:<outside>` carries ten nodes and 378
    shadows: sized on the total it would be drawn six times too wide, equally plausibly,
    and the one thing a width is supposed to say would be false. Tom answered this before
    it was built -- *"shadows was just an idea due to the 3D aspect, not a requirement"* --
    and the arithmetic agrees with him for a reason worth keeping written down.

    The guard reads the ratio block rather than the whole file, because `shadows` appears
    legitimately a dozen times elsewhere in the engine.
    """
    js = _read("graph.js")
    block = js.split("const diskRatio = new Map();", 1)[1].split("\n\n", 1)[0]
    assert "k.nodes" in block, "the plate ratio no longer counts the plate's own nodes"
    assert "shadow" not in block.lower(), (
        "the plate ratio counts shadows -- a plate would be drawn wider than what is "
        "drawn on it, and a width that says nothing true is worse than every plate alike"
    )
    assert "Math.sqrt" in block, (
        "the ratio is no longer a square root, so a plate four times as full is four "
        "times as wide rather than twice -- area is the channel, not radius"
    )


def test_the_width_dial_is_reversible_and_comes_home_to_the_payload() -> None:
    """0 must be exactly the arrangement the server sent, not nearly it.

    Every scale in this engine is computed from an unscaled base for one reason: 2x then 2x
    again is 4x, and a slider dragged back has to come home. The width dial is the first one
    that is an *interpolation* rather than a multiplier, so the thing to check is the
    endpoints -- at 0 every plate is one width, at 1 every plate is its own ratio.

    Evaluated rather than matched. The expression is lifted out of the engine's own source
    and run, so a rewrite that is still correct passes and one that is merely differently
    shaped -- `ratio * strength`, which collapses the whole stack to a point at 0 -- fails.
    """
    js = _read("graph.js")
    m = re.search(r"d\.diskScale\.set\(id, (.+)\);", js)
    assert m, "the width factor is no longer set from one expression -- this test is blind"
    expr = m.group(1).strip()
    assert "strength" in expr and "ratio" in expr, f"unexpected factor: {expr!r}"

    def factor(ratio: float, strength: float) -> float:
        return float(eval(expr, {"__builtins__": {}},  # noqa: S307 -- the engine's own text
                          {"ratio": ratio, "strength": strength}))

    for ratio in (1.0, 0.5, 0.078):
        assert factor(ratio, 0.0) == pytest.approx(1.0), (
            f"at 0 a plate of ratio {ratio} is drawn at {factor(ratio, 0.0)} -- the dial "
            "does not come home to the arrangement the server placed"
        )
        assert factor(ratio, 1.0) == pytest.approx(ratio), (
            f"at 1 a plate of ratio {ratio} is drawn at {factor(ratio, 1.0)} -- its area "
            "no longer means what it holds"
        )
    assert factor(0.25, 0.5) == pytest.approx(0.625), "the dial is no longer linear"

    clamp = js.split("const strength =", 1)[1].split(";", 1)[0]
    assert "Math.max(0" in clamp and "Math.min(1" in clamp, (
        "the strength is unclamped -- a stored value from another build, or a control "
        "someone widens later, turns plates inside out rather than being refused"
    )


def test_everything_placed_on_a_plate_asks_that_plate_how_wide_it_is() -> None:
    """One radius described the whole stack until it did not.

    Three things sit on a plate's circle: the nodes, the plate's own outline, and the
    you-are-here arrow standing on its rim. They were three expressions built from one
    constant, which was right while every plate was the same width and is a lie the moment
    one is not -- an arrow on the largest plate's circle, for a node on a plate a tenth as
    wide, is still on the right bearing and no longer on the rim of anything (rule 51).

    So every place that multiplies by `spreadX` must also multiply by the plate's own
    factor, and that factor must come from the map `applyLayout` scaled the positions with
    -- not from a second walk over the disk counts, which is how two answers to one
    question get into one picture.
    """
    js = _read("graph.js")
    sites = [ln.strip() for ln in js.splitlines() if re.search(r"\* opts\.spreadX", ln)]
    assert len(sites) >= 3, f"expected the three placement sites, found {sites}"
    for line in sites:
        assert re.search(r"\* f\b", line), (
            f"placed without asking the plate how wide it is: {line!r} -- at one width "
            "this is correct and at any other it puts the thing somewhere it is not"
        )
    for fn in ("applyLayout", "rimPoint"):
        assert "diskScale.get(" in _fn(js, fn), (
            f"{fn} does not read diskScale, so its factor comes from somewhere else -- "
            "two answers to how wide a plate is drawn, in one frame"
        )


def test_the_width_dial_reaches_the_picture_and_not_only_the_setting() -> None:
    """A slider that writes state, persists, and repaints nothing looks exactly like one
    that works -- design rule 16, and the dial has four separate ways to be that.

    The engine must relay it to `applyLayout`; the plate outlines must be told their
    geometry changed or they keep the previous widths while the nodes move inside them; the
    mount must hand over the value the reader last chose; and a change of *altitude* must
    push that altitude's own value, because the dial is per level and `setPayload` does not
    know that. Miss the last and the slider moves to the right number over a picture drawn
    to the other one -- one control, two answers, and the visible one is wrong (rule 67).
    """
    engine = _read("graph.js")
    trigger = engine.split("if (partial.spreadX !== undefined", 1)[1].split("}", 1)[0]
    assert "partial.plateSize !== undefined" in trigger, (
        "setOptions does not relay plateSize to applyLayout -- the dial would move, "
        "persist, and leave the stack exactly as it was"
    )
    triggers = re.findall(r"updateTriggers: \{ getPolygon: \[([^\]]*)\]", engine)
    assert len(triggers) == 2, f"expected two plate layers, found {len(triggers)}"
    for t in triggers:
        assert "opts.plateSize" in t, (
            "a plate layer does not re-upload on a width change -- the outlines stay at "
            "the old widths while the nodes inside them move, which reads as a bug in the "
            "nodes"
        )

    shell = _read("shell.js")
    mount = shell.split("Graph.mount(", 1)[1].split("});", 1)[0]
    assert "plateSize: plateSizeNow()" in mount, (
        "the mount does not hand over the reader's width -- it would be restored into "
        "`state`, shown on the slider, and never drawn"
    )
    detail = _fn(shell, "setGraphDetail")
    swap = detail.split("Graph.setPayload(payload);", 1)
    assert len(swap) == 2, "setGraphDetail no longer swaps the payload -- this test is blind"
    assert "Graph.setOptions({ plateSize: plateSizeNow() })" in swap[1], (
        "a change of altitude does not push that altitude's width -- the dial is per "
        "level, so the new picture would be drawn to the old level's judgment"
    )


def test_the_width_readout_is_read_back_from_what_was_drawn() -> None:
    """Rule 13: the number printed beside a control must be produced by the thing it
    describes. The widths on screen come out of `diskScale` -- the very map the positions
    were scaled with -- so a clamp, the floor on an empty plate, or the interpolation
    itself cannot make the line a confident disagreement with the picture.

    Recomputing `sqrt(n / nmax)` in the shell would be a second answer built from the same
    inputs, which is how the routine list came to print an edge count under a heading about
    nodes (rule 32) and how the table footer and the table came apart (rule 13).
    """
    engine = _read("graph.js")
    widths = engine.split("plateWidths() {", 1)[1].split("\n  },", 1)[0]
    # **The values, not merely a mention.** A first version of this asked whether
    # `d.diskScale` appeared anywhere in the body and passed a mutation that read the
    # *ratios* for the numbers while still testing `diskScale.size` for emptiness -- the
    # guard true, the readout describing a stack nobody had drawn. Rule 59's companion: a
    # mutation that leaves any read of the thing standing has not removed it, and a guard
    # that accepts any read has not checked the one that matters.
    assert "d.diskScale.values()" in widths, (
        "plateWidths does not take its numbers from the map the positions were scaled "
        "with -- the line beside the slider would describe a stack that was not drawn"
    )
    assert "diskRatio" not in widths and "raw.disks" not in widths, (
        "plateWidths reads the payload's own ratios rather than what the dial made of "
        "them, so the readout would say the same thing at every strength"
    )
    assert "return null" in widths, (
        "plateWidths answers for an unprepared engine -- 'no stack yet' and 'every plate "
        "one width' are different claims and a reader cannot tell them apart"
    )

    shell = _read("shell.js")
    note = _fn(shell, "plateRangeNote")
    assert "Graph.plateWidths()" in note, (
        "the readout no longer asks the engine what it drew"
    )
    assert "Math.sqrt" not in note and ".nodes" not in note, (
        "the readout recomputes the widths from the plate counts -- a second answer to a "
        "question the engine has already answered, and the two will disagree"
    )
    assert "state.level" in note, (
        "the readout does not say which altitude it is speaking about -- the dial is per "
        "level, and a value that changes under the reader with nothing saying so reads as "
        "a control that reset itself"
    )
    assert "every plate one width" in note, (
        "a stack with the dial at zero says nothing about being at zero, so an unsized "
        "stack and a program whose packages are all the same size look identical"
    )


def test_the_width_control_does_not_borrow_a_word_this_product_owns() -> None:
    """`density` is already a setting here -- the table's row height -- and the dial that
    equalises plate density is *called* width for exactly that reason.

    One word for two ideas, in a tool whose whole subject is a program's vocabulary, is the
    disk/plate collision `settings.js` already carries a debt for. This one was caught
    before it shipped rather than after, and the guard is what keeps it caught.
    """
    shell = _read("shell.js")
    controls = shell.split('id="panel-controls"', 1)[1].split("</div>`", 1)[0]
    assert 'id="gwidth"' in controls, "the width slider is gone from the controls box"

    # Over what a reader can *see*, never over the whole span: the note explaining why the
    # word is not used is written in the markup beside the control, and a guard that trips
    # on the prose saying a word was avoided is rule 37 in its purest form.
    seen = set(re.findall(r'style="width:3\.2rem">([^<]+)<', controls))
    seen |= set(re.findall(r'aria-label="([^"]+)"', controls))
    seen.add(_fn(shell, "controlsSummary"))
    for text in seen:
        assert "density" not in text.lower(), (
            f"the graph's controls say {text!r} to the reader, and this product already "
            "spends the word `density` on the table's row height"
        )


def test_a_shape_set_covers_every_kind_a_box_can_be() -> None:
    """A kind with no outline is drawn as something else, silently.

    `silhouette` falls back to the rectangle for a kind it does not know, which is the right
    behaviour at runtime — a payload this build has not been taught is better drawn plainly
    than not drawn — and exactly the wrong thing to rely on. Two kinds sharing one outline is
    the channel saying nothing, which is the whole argument for offering shape as a **set**
    rather than as a picker per kind.

    Both directions. Every kind the payload can carry must have an outline; and every outline
    must be listed in the Settings key, or the reader meets a shape the page never explained.
    """
    engine = _read("graph.js")
    block = engine.split("const SILHOUETTE = {", 1)[1].split("\n};", 1)[0]
    shaped = set(re.findall(r"^  (\w+):", block, re.M))
    assert len(shaped) >= 5, f"the SILHOUETTE table changed shape: {sorted(shaped)}"

    # The kinds the *server* can emit, read from the payload builder rather than a list here.
    graph_py = (Path(__file__).resolve().parents[1]
                / "src/dunneflow/web/graph.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r'kind="([A-Z_]+)"', graph_py))
    assert emitted, "no node kinds found in graph.py -- this test is blind"
    assert emitted <= shaped, (
        f"kinds the payload emits with no outline of their own: {sorted(emitted - shaped)} "
        "— each falls back to the rectangle and becomes indistinguishable from a routine"
    )

    shell = _read("shell.js")
    keyed = set(re.findall(r'^  \["(\w+)",', shell.split("const SHAPE_KINDS = [", 1)[1]
                           .split("\n];", 1)[0], re.M))
    assert keyed == shaped, (
        f"the Settings key and the engine disagree about which kinds have a shape: "
        f"key-only {sorted(keyed - shaped)}, engine-only {sorted(shaped - keyed)} — "
        "a reader meets an outline the page never explained, or reads about one that is "
        "never drawn"
    )


def test_the_shape_key_draws_the_engines_own_outlines() -> None:
    """Rule 13: the picture beside a control must be produced by the thing it describes.

    A key that keeps its own copy of these shapes is a second answer to what a kind looks
    like, and the two part company on the day a shape moves — silently, because both halves
    go on rendering perfectly. So the page asks the engine, and the engine answers with the
    very points it hands to the layer.
    """
    shell = _read("shell.js")
    fn = _fn(shell, "shapeKeyHtml")
    assert "Graph.silhouettes(" in fn, (
        "the shape key no longer asks the engine for its outlines"
    )
    assert "polygon" in fn and "points=" in fn, "the key stopped drawing the outlines at all"
    for forbidden in ("SILHOUETTE", "Math.cos", "rect", "hexagon"):
        assert forbidden not in fn, (
            f"the shape key builds {forbidden!r} of its own — a second answer to what a "
            "kind looks like, which will disagree with the stack and say nothing when it does"
        )

    engine = _read("graph.js")
    api = engine.split("silhouettes: (set)", 1)
    assert len(api) == 2, "Graph.silhouettes is gone; the key has nothing to ask"
    assert "silhouette(k, set)" in api[1], (
        "Graph.silhouettes no longer routes through `silhouette`, so the key can be "
        "answered by something other than what draws the stack"
    )


def test_a_box_and_its_label_are_turned_by_one_number() -> None:
    """The outline and the text inside it are two layers drawing one object.

    They are turned about Z so the reading direction faces the reader — which was **found by
    looking**, not reasoned: built flat, the tilt turned out to cost nothing a reader
    notices, and the *orbit* turned every label by the orbit angle, so looking straight down
    at a plate gave a page of names set on a diagonal.

    Two numbers for one turn is how the box ends up at one angle and its name at another, and
    nothing would fail: both layers render, both are correct about themselves. So the angle
    comes from one function, in degrees for the text layer and radians for the outline,
    converted at the single call site that has both.
    """
    js = _read("graph.js")
    assert "function boxSpinDeg()" in js, "the turn is no longer stated in one place"

    build = _fn(js, "buildLayers")
    assert "const spinDeg = boxSpinDeg();" in build, "the layers no longer ask for the turn"
    assert re.search(r"const spin = \(spinDeg \* Math\.PI\) / 180;", build), (
        "the radian form is no longer derived from the degree form — two spellings of one "
        "angle is how the outline and its label come to disagree"
    )
    assert "getAngle: spinDeg" in build, "the text layer is not given the turn"
    assert "boxPolygon(b, unit, spin)" in build, "the outline is not given the turn"

    # It must also re-upload when the turn changes, or the boxes keep the previous angle
    # while the labels move -- the silent half of the same defect.
    for trigger in (r"getPolygon: \[unit, spin,", r"getAngle: \[spinDeg\]"):
        assert re.search(trigger, build), (
            f"no update trigger matching {trigger!r} — deck compares props shallowly, so "
            "the geometry would keep the angle it was first built at"
        )


def test_boxes_are_placed_in_screen_space_and_say_what_stayed_a_dot() -> None:
    """The overflow answer, and design rule 1 is the whole of it.

    A plate pick can light 926 nodes and a diagram of 926 boxes is not a diagram. Boxes are
    placed busiest-first and kept only where they do not touch one already placed; everything
    else stays a **dot**, so nothing leaves the picture (rule 19), and the number still a dot
    is stated with the way to get more (design rule 1, rule 32).

    Measured on Mensores at a 1280x760 pane: picking `pkg:mcp` lights 360 and draws 102
    boxes; the worst plate lights 1,319 and draws 86, in 2.3 ms.
    """
    engine = _read("graph.js")
    place = _fn(engine, "placeBoxes")
    assert "vp.project(" in place, "placement no longer happens in screen space"
    assert "d.degree[b] - d.degree[a]" in place, (
        "boxes are no longer placed busiest-first — the ordering is what makes the ones "
        "that survive a crowd the ones worth reading"
    )
    assert "g.members.size - placed.length" in place, (
        "the dotted count is no longer the remainder of what was lit, so the two numbers "
        "can disagree about one selection"
    )
    # **The catch branch itself, not any `return null` in the function.** A first version
    # asked whether the string appeared anywhere in `placeBoxes` and passed a mutation that
    # made the catch return an empty answer while a later `return null` stood untouched —
    # rule 59's companion, and the third time this session a guard has accepted any
    # occurrence when only one of them was the claim.
    catch = re.search(r"\}\s*catch\s*\{(.*?)\}", place, re.S)
    assert catch, "getViewports() is called unguarded; an optional chain does not catch a throw"
    assert re.search(r"return null;", catch.group(1)), (
        "placeBoxes answers for a viewport it does not have — rule 42: deck asserts inside "
        "getViewports() before its first frame, and 'cannot say' is not 'nothing fits'. "
        f"the catch returns: {catch.group(1).strip()!r}"
    )

    build = _fn(engine, "buildLayers")
    assert re.search(r"opts\.diagram && still", build), (
        "the placement runs while the camera is moving — a hundred rectangles re-solved "
        "per frame to draw a picture nobody is reading yet"
    )
    assert "g.boxCount = boxes ? boxes.placed.length : 0;" in build, (
        "the counts do not follow the placement, so turning the diagram off would leave "
        "the last numbers standing over a picture that no longer has boxes in it"
    )

    shell = _read("shell.js")
    # **And the mount has to hand both of them over.** Nothing asserted this until a
    # mutation deleted the line and every guard stayed green: the switch would be restored
    # into `state`, drawn checked in the controls box, and never reach the engine — design
    # rule 16's dead control, arriving through the restore path rather than the wiring.
    mount = shell.split("Graph.mount(", 1)[1].split("});", 1)[0]
    for handed in ("diagram: state.diagram", "nodeShapes: state.nodeShapes"):
        assert handed in mount, (
            f"the mount does not hand over {handed!r} — the setting would be persisted, "
            "restored, shown on its control and never drawn"
        )
    line = _fn(shell, "countLine")
    # The **condition**, not a mention: `(c.boxesDotted ? ... : "")` mutated to `(false ? ...`
    # leaves every use of the name standing inside a branch that can no longer run, which is
    # a dead control wearing a live variable (rule 59's companion once more).
    assert re.search(r"\(c\.boxesDotted\s*$", line, re.M), (
        "the overflow line is no longer guarded by the dotted count itself — a branch that "
        "cannot run still mentions every name in it"
    )
    assert "c.boxes || 0" in line, (
        "the count line does not state how many boxes were drawn — forty boxes over a "
        "selection of nine hundred looks exactly like a selection of forty"
    )
    assert "zoom in for more" in line, (
        "the line does not say how to get more boxes, and a reader cannot guess that the "
        "picture answers to the zoom"
    )


def test_the_box_cache_is_keyed_on_the_selection_and_cleared_by_whoever_moves_a_node() -> None:
    """Two ways for a cached placement to describe the wrong picture, and neither raises.

    Keyed on how *many* nodes are lit, two different routines with the same number of
    neighbours share a key and the second is drawn with the first one's boxes. And a key
    naming the spreads it happens to know about goes stale the day a fourth thing moves a
    node — so the invalidation lives with the code that does the moving instead (rule 51).
    """
    js = _read("graph.js")
    place = _fn(js, "placeBoxes")
    key = place.split("const key = [", 1)[1].split("].join", 1)[0]
    assert "g.picks.map(pickKey)" in key, (
        "the placement cache is not keyed on the selection itself — two selections of the "
        "same size would share an answer, and the second would be a confident picture of "
        "the first"
    )
    assert "g.members.size" not in key, (
        "the cache is keyed on the size of the selection, which is exactly the collision "
        "above wearing a number"
    )
    assert "opts.direction" in key, (
        "direction decides what a pick lights, so a cache blind to it answers the previous "
        "question"
    )
    for spread in ("opts.spreadX", "opts.plateSize"):
        assert spread not in key, (
            f"{spread} is back in the key — a key that lists the inputs it knows about is "
            "the shape that goes wrong when a fourth is added beside them; the layout "
            "clears the cache instead"
        )
    layout = _fn(js, "applyLayout")
    assert "g.boxCache = null" in layout, (
        "applyLayout moves every position and does not clear the placement built from them"
    )
    adopt = _fn(js, "adoptPayload")
    assert "g.boxCache = null" in adopt, (
        "a payload swap leaves a placement whose indices point into the previous payload"
    )


def test_the_frustum_reaches_past_the_stack_at_every_zoom() -> None:
    """Zooming all the way in used to lose a quarter of the stack, and the note on file
    blamed the wrong plane for two sessions.

    Measured by projecting every drawn node through deck's own view-projection and counting
    the ones whose clip-space z leaves [-1, 1]: nothing clips anywhere in the range except at
    `maxZoom` exactly, where **4,063 of 15,869** go past +1 — the *far* plane, at deck's
    default of 500. The near plane is never reached. It is a cliff at the top of the range
    rather than a gradual onset, which is how it was reported.

    Two halves. The far plane must be raised, from a named constant rather than a number
    written into the view. And `near` must **not** be made negative — that was the previous
    attempt, and it breaks pan and zoom outright, because deck's orbit controller implements
    both through `viewport.unproject()`. A guard is the only thing that stops a future reader
    reaching for the geometrically obvious fix a second time.
    """
    js = _read("graph.js")
    m = re.search(r"const FAR_PLANE = (\d+);", js)
    assert m, "FAR_PLANE is gone; the frustum is back to deck's default of 500"
    assert int(m.group(1)) >= 4000, (
        f"FAR_PLANE is {m.group(1)} — measured, the stack needs about 4,000 to clear "
        "maxZoom, and below that the far nodes are clipped at the top of the range"
    )
    view = re.search(r"new OrbitView\(\{([^}]*)\}\)", js)
    assert view, "the OrbitView construction changed shape -- this test is blind"
    assert "far: FAR_PLANE" in view.group(1), (
        f"the view does not take the raised far plane: {view.group(1).strip()!r}"
    )
    assert "orthographic: true" in view.group(1), (
        "the view is no longer orthographic — design rule 20, and every pixel-to-world "
        "conversion in this file assumes it"
    )
    assert not re.search(r"near:\s*-", view.group(1)), (
        "a negative near is back. It is geometrically sound under an orthographic "
        "projection and it breaks pan and zoom outright — both go through "
        "viewport.unproject(), rotate does not, so exactly the two controls that unproject "
        "stop while the one that does not carries on"
    )


def test_the_diagram_has_one_owner_and_every_control_goes_through_it() -> None:
    """Two controls reach the diagram: the switch on the graph, where a reader flips a way of
    looking while reading, and the toggle in Settings beside the shapes — which is where a
    reader who has just chosen a shape set is standing when they wonder why nothing changed.

    The second exists because the first could not be found. The reader's layout had the
    controls box collapsed, so the switch was 0×0 and the Shape page was a control that
    rendered and appeared to do nothing — design rule 16 with the wiring perfectly correct.

    Two doors onto one piece of state is fine. Two *implementations* of what the door does is
    rule 51, and the second one always forgets something: here it would be `used()`, which is
    how design rule 2 retires a loser on evidence.
    """
    js = _read("shell.js")
    assert "function setDiagram(" in js, "the diagram no longer has one owner"
    owner = _fn(js, "setDiagram")
    for required in ("state.diagram", "used(", "persist()", "Graph.setOptions"):
        assert required in owner, f"setDiagram does not {required} — a door that half-works"

    code = _code(js)
    assigns = [ln.strip() for ln in code.splitlines()
               if re.search(r"state\.diagram\s*=", ln)]
    assert len(assigns) == 1, (
        f"state.diagram is assigned in {len(assigns)} places: {assigns} — every control "
        "must go through setDiagram, or one of them forgets to count, persist or repaint"
    )
    assert 'if (t.id === "gdiagram") { setDiagram(' in js, (
        "the graph's switch no longer routes through the owner"
    )
    assert 'dgm.addEventListener("click", () => setDiagram(' in js, (
        "the Settings toggle no longer routes through the owner"
    )
    assert 'id="diagramToggle"' in js, (
        "the Settings toggle is gone — and it is the one a reader with the controls box "
        "collapsed can actually reach"
    )


def test_a_folded_box_names_the_mode_it_is_hiding() -> None:
    """This box collapses to a summary strip (design rule 25), and the strip has to name what
    is on inside it.

    With the box shut and the diagram on, a reader would have a stack of labelled boxes and
    nothing anywhere saying why — and the way it actually happened, the diagram *off* and no
    hint that a switch for it existed in there at all. Design rule 24 already says a strip
    reading only "controls" makes the reader open it to find out what it was; this is the
    same argument applied to what the strip must say.
    """
    js = _read("shell.js")
    summary = _fn(js, "controlsSummary")
    assert "state.diagram" in summary, (
        "the collapsed strip does not name the diagram, so a mode that changes every node "
        "on screen is invisible from outside the box that switches it"
    )
    assert re.search(r"state\.diagram \?", summary), (
        "the strip mentions the diagram unconditionally — it must say so when it is on, "
        "which is a different claim from listing a control that exists"
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

    # The step is built in `recordSelection` now rather than in `pushTrail` -- one recorder
    # for the one history -- so the literal is looked for where it is made, not where it
    # used to be. The claim is unchanged: a step without a subject takes nobody anywhere.
    step = re.search(r"const step = \{(.*?)\n  \};", _fn(js, "recordSelection"), re.S)
    assert step, "recordSelection no longer builds a step literal -- this test is blind"
    assert "subject" in step.group(1), (
        "a trail step records no subject, so clicking it cannot restore what you were "
        f"looking at: {step.group(1).strip()}"
    )
    assert "state.trail.push(step)" in js, "the step is not pushed onto the one history"
    # Both ways back must restore it: clicking a step, and the Back button. This counted two
    # copies of the same line, which was the right check while there were two handlers; they
    # go through one function now, so the check follows it -- that both *route* there, and
    # that it applies the subject. One place is the stronger version of the same claim.
    go = _fn(js, "goToTrailStep")
    assert "applySelectionStep(step.subject)" in go, (
        "the one way back no longer restores a step's subject, so every step takes you "
        "nowhere"
    )
    # Clicking a step still routes here directly; Back and Forward reach it through
    # `undoSelection` / `redoSelection`, which are the same two functions ⌘Z and the HUD's
    # buttons call. Three doors, one way back.
    seg = js.split("[data-trail]", 1)[1][:600]
    assert "goToTrailStep(" in seg, (
        "clicking a step does not go through the one way back, so the two can disagree "
        "about what returning to a step means"
    )
    for fn in ("undoSelection", "redoSelection"):
        assert "goToTrailStep(" in _fn(js, fn), (
            f"`{fn}` does not restore through `goToTrailStep`, so stepping and undoing "
            "would mean two different things"
        )
    # And the mode is not part of where you were: the three centre views are three ways of
    # looking at one selection, so Back from the table must not land you in the graph.
    assert "CENTRE_MODES.includes(step.view) && CENTRE_MODES.includes(state.view)" in go, (
        "a step replays the mode it was recorded in, so a reader pressing Back in the table "
        "is put in the graph -- which is where the step happened to be made, not where they "
        "were"
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

    assert "function recordSelection(" in js, "no selection history is recorded"
    assert js.count("recordSelection()") >= 3, (
        "the history is recorded on fewer paths than there are ways to select — the graph "
        "announcing a click and the list driving one must both reach it"
    )
    # The guard itself, not just the flag. The flag being declared and set proves nothing:
    # the recorder has to actually consult it, or every undo records itself as a new step
    # and the history can never move backwards.
    # The guard must stand between a restore and the *history*, which is what it is for.
    # It used to be pinned to the first statement of the function, and that is a position
    # rather than an invariant: `publishSelection()` is deliberately above it, because an
    # undo has genuinely changed where this window is looking and the window beside it is
    # entitled to follow -- while still not recording the replay as a new step.
    body = _code(_fn(js, "recordSelection"))
    assert "if (restoringSelection) return;" in body, (
        "recordSelection does not bail while a restore is in flight, so an undo records "
        "itself as a new step and the history never moves backwards"
    )
    assert body.index("if (restoringSelection) return;") < body.index("state.trail"), (
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

    # Everything the card's renderers read off the served object.
    #
    # **Every** renderer, not just the one this was written against. `hoverSigHtml` was
    # added as its own function and sat entirely outside this check's span for as long as
    # it took to notice -- so the card's most important line, the one thing on it that is
    # not a summary, was the one part nothing was vouching for. A check whose span does not
    # follow the code it names has stopped being a check (rule 37, in a test rather than in
    # a control).
    read: set[str] = set()
    for fn in ("hoverDetailHtml(card, needWhere)", "hoverSigHtml(card)", "hoverSkeleton(h)"):
        name = fn.split("(", 1)[0]
        assert f"function {fn} {{" in shell, f"{name} changed shape -- this test is blind"
        body = shell.split(f"function {fn} {{", 1)[1].split("\n}\n", 1)[0]
        read |= set(re.findall(r"\bcard\.(\w+)", body))
    assert read, "no renderer reads the served card at all -- this test is blind"

    # Everything `hover_card` puts on it. Only the dict literals it returns, so a key that
    # exists elsewhere in the module does not vouch for one the card never receives.
    served = set(re.findall(r'"(\w+)":', detail.split("def hover_card(", 1)[1]))
    assert served, "hover_card changed shape -- this test is blind"

    missing = sorted(read - served)
    assert not missing, (
        f"the pop-up renders fields the server never sends: {missing} -- each is a row "
        "that silently does not appear, indistinguishable from a node with nothing to say"
    )


def test_the_invocation_line_is_the_one_in_the_code() -> None:
    """What moves in and what comes back out -- the subject of the whole tool, and the one
    thing about a routine the card never said. Asked for at the keyboard.

    A signature is the kind of thing that must not have two answers, so the marker logic
    lives once, in `schema.signature_parts`, and the client colours what it is handed. The
    checks below are all one claim in different places: **the line printed is the line in
    the file**, which is rule 13 at the last surface it can still go wrong on.
    """
    shell = _read("shell.js")
    sig = _fn(shell, "hoverSigHtml")

    # It leads the fetched half. The measures and the touches *describe* the routine; this
    # one is the routine, and burying it under them answers a different question first.
    detail = _fn(shell, "hoverDetailHtml")
    at_sig = detail.index("hoverSigHtml(card)")
    for later in ('needWhere && card.file', 'card.kind === "ROUTINE"', "card.touches"):
        assert at_sig < detail.index(later), (
            f"the invocation line is pushed after `{later}`, so the card leads with a "
            f"summary of the routine rather than with the routine"
        )

    # The markers are rendered. Dropped, `def f(a, *, b)` prints as `f(a, b)` -- a different
    # function, and one that cannot be called the way the card implies.
    assert "p.marker" in sig and 'esc(p.marker)' in sig, (
        "the client drops the `*` and `/` pieces, so 998 of Mensores' 4,734 signatures "
        "print with a calling convention the code does not have"
    )

    # And it decides nothing about them. Two implementations of where a `*` belongs would
    # agree until the day one was edited (rule 36); the server sends the pieces in order and
    # this function's whole job is colour.
    for word in ('"keyword"', '"vararg"', '"kwarg"', '"positional'):
        assert word not in sig, (
            f"the card reasons about parameter kinds ({word}) -- that is a second opinion "
            f"on where a marker belongs, beside `schema.signature_parts`"
        )

    # `<module>` is DunneFlow's own name for module scope, not something anybody wrote.
    # `<module>()` is a call that cannot be made -- inventing an invocation to fill a row.
    assert 'card.name === "<module>"' in sig, (
        "a module-scope node renders an invocation line, which is a call nobody can make"
    )

    # One renderer, reached from Python and from the browser, so the Markdown documents and
    # the card cannot disagree about the same routine.
    schema = (WEB.parent / "schema.py").read_text(encoding="utf-8")
    assert "def signature_parts(" in schema, "the shared renderer is gone"
    body = schema.split("def signature(self)", 1)[1].split("\n    def ", 1)[0]
    assert "signature_parts(" in body, (
        "`Routine.signature()` no longer goes through the shared renderer, so the Markdown "
        "documents and the hover card are two opinions about one signature again"
    )


def test_every_scrim_sits_under_the_window_it_dims() -> None:
    """A scrim dims what is behind it and must be *behind* what it dims. One shared scrim
    cannot do that for two windows at different depths, and it did not: the detail window
    took `z-index: 88` to stay below the source viewer, the shared scrim sat at 90, and so
    the window rendered perfectly, greyed over, and turned every click on itself into
    "close" -- because the scrim was what the pointer hit.

    **No amount of driving would have caught it.** A synthetic `element.click()` invokes the
    handler on the element it names; it proves a control is wired and says nothing about
    whether a reader can reach it. Hit-testing is the half only a real pointer exercises,
    which is why this is asserted from the stylesheet rather than from the browser. Reported
    from a screenshot -- *look, don't only test*, once more.
    """
    css = _read("tokens.css")

    def z(selector: str) -> int:
        rule = css.split(f"{selector} {{", 1)[1].split("}", 1)[0]
        found = re.search(r"z-index:\s*(\d+)", rule)
        assert found, f"{selector} declares no z-index, so its layering is whatever order gives"
        return int(found.group(1))

    pairs = [(".detail-scrim", ".detailwin"), (".viewer-scrim", ".viewer")]
    for scrim, win in pairs:
        assert z(scrim) < z(win), (
            f"{scrim} is above {win}, so the window is dimmed by its own scrim and every "
            f"click on it lands on the scrim instead -- which reads as a window that closes "
            f"itself whenever it is touched"
        )
    # And the pairs do not interleave: a window must clear the scrim of everything below it,
    # or opening the upper one leaves the lower one's window poking through.
    assert z(".detailwin") < z(".viewer-scrim"), (
        "the source viewer's scrim no longer covers the detail window, so opening a citation "
        "from inside it leaves the window it came from undimmed on top"
    )
    # Each window has its own scrim: sharing one is what produced the inversion.
    shell = _read("shell.js")
    assert 'class="detail-scrim"' in _fn(shell, "detailShell"), (
        "the detail window uses the source viewer's scrim again, which cannot sit at two "
        "depths at once"
    )


def test_the_detached_window_is_the_same_application() -> None:
    """Asked for at the keyboard: a separate tab or pop-up window kept in bidirectional sync
    with the menu on the left. Wanted for the code viewer next, so it is built as a pattern.

    `?view=detail` boots the whole shell and hides everything but the panel. A second page
    with its own renderer would have been the **third** place this project draws one node,
    and the first two disagreed about parameter types for a year.
    """
    shell, css, html = _code(_read("shell.js")), _read("tokens.css"), _read("index.html")

    assert 'DETACHED_VIEW' in shell, "there is no detached mode"
    assert '"detail"' in shell and '"code"' in shell, (
        "the detached kinds are no longer named, so `?view=` accepts anything"
    )
    assert "document.body.classList.add(\"detached\")" in shell, (
        "detached mode never marks the document, so the stylesheet cannot lay it out"
    )
    # A second detached view was added, and it must not be a second page either. Its class
    # is its own rather than an exception carved out of `.detached`: that rule hides `.app`
    # outright, and the code view renders *inside* it, so sharing the class would be two
    # equal selectors arguing over one `display` and settled by source order (rule 29).
    assert 'classList.add("detached-code")' in shell, (
        "the detached code window does not mark the document"
    )
    assert '.detached .app' in css and 'body.detached-code .body' in css, (
        "the two detached views share one class, so one of them hides the pane it renders in"
    )
    assert 'code.html' not in shell and 'code.html' not in html, (
        "the detached code view is a second page, which is a second place a file is drawn"
    )
    # One page, one renderer: the detached view must not be served from a second file.
    assert "detail.html" not in shell and "detail.html" not in html, (
        "the detached view is a second page, which is a second place one node is rendered"
    )
    rule = css.split(".detached .detailwin {", 1)[1].split("}", 1)[0]
    assert "position: static" in rule and "height: 100vh" in rule, (
        "the detached panel is still a centred modal rather than the page it now is"
    )
    assert ".detached .app," in css and "display: none !important" in css, (
        "the shell is not hidden in the detached window, so it renders behind the panel"
    )


def test_two_windows_follow_each_other_without_looping() -> None:
    """Peers, not parent and child. A `postMessage` protocol through `window.opener` breaks
    the moment the reader closes the main window, reloads either one, or opens the detached
    view by pasting its URL -- all of which are ordinary. A `BroadcastChannel` is same-origin,
    needs no server, and does not care which window opened which.

    The loop guard is the whole subtlety: adopting a selection must not republish it, or two
    peers bounce one click between them for ever, which looks exactly like a hang and leaves
    neither window obviously at fault.
    """
    shell = _code(_read("shell.js"))
    assert "new BroadcastChannel(" in shell, "the two windows have no way to reach each other"
    # The guard line itself, not "the word appears somewhere below". `_fn` reads to the next
    # `function`, and what follows `publishSelection` is the message handler -- which
    # mentions `adopting` twice, so a containment check here vouched for the wrong code and
    # passed against its own mutation. That hazard is written in `_fn`'s own docstring.
    assert re.search(r"if \(!SYNC \|\| adopting \|\| !state\.selected\) return;", shell), (
        "publishing does not check the adopt flag, so a selection received from the other "
        "window is echoed straight back to it"
    )
    handler = shell.split('SYNC.addEventListener("message"', 1)[1].split("\n}\n", 1)[0]
    assert "adopting = true;" in handler and "adopting = false;" in handler, (
        "the adopt path never raises the flag, so the guard above it guards nothing"
    )
    assert "finally" in handler, (
        "the flag is cleared on the happy path only -- one failed adopt and this window "
        "stops publishing for the rest of the session, silently"
    )
    # Rule 26 with more drivers than anyone listed: the list must move to a selection it did
    # not make, whoever made it. Asserted on `selectFromNav` rather than on this handler,
    # because that is where it now happens *once* -- and because the alternative is one copy
    # per caller, which is how the table, the detail window and the arrow each got it wrong.
    sfn = _fn(shell, "selectFromNav")
    assert "buildNav();" in sfn and "revealSelectedRoutine();" in sfn, (
        "a selection made anywhere but the navigator leaves the navigator marking whatever "
        "was clicked last time -- a stale highlight, which is a confident wrong answer"
    )
    # It is published wherever a selection settles, not at one call site that will drift.
    assert "publishSelection();" in _fn(shell, "recordSelection"), (
        "the selection is published from somewhere other than the one place every path "
        "already funnels through"
    )


def test_popping_out_is_a_click_and_says_when_it_is_blocked() -> None:
    """A pop-up blocker reads a click as the reader asking and a keystroke as the page
    deciding for itself, so the control that survives is a button. And a blocked pop-up is
    the exact shape of a control that renders and does nothing -- so it says so, and names
    the URL the reader can open themselves."""
    shell = _code(_read("shell.js"))
    detach = _fn(shell, "detachDetail")
    assert "window.open(" in detach, "nothing opens a second window"
    assert "state.navNote" in detach and "blocked" in detach, (
        "a blocked pop-up leaves the reader with a button that did nothing and no reason"
    )
    assert "?view=detail" in detach, "the second window is not opened on the detached view"
    # Present is not reached. An early `return` after the counter left this line in the
    # source and out of the path, and a containment check passed against exactly that.
    after = detach.split('used("detail:detached");', 1)[1]
    closes = "state.detail = false;"
    assert closes in after and "return;" not in after.split(closes, 1)[0], (
        "the in-app window stays open behind the new one -- two copies of one view, the "
        "nearer of them stale"
    )
    # A button, and only in the window that is not already detached.
    assert 'data-detachdetail' in _read("shell.js"), "no control offers to pop out"
    shell_raw = _read("shell.js")
    head = shell_raw.split("function detailShell(", 1)[1].split("\n}\n", 1)[0]
    # Guarded on the *button*, not on the word. `DETACHED` also gates the sync badge below,
    # so "it appears in the header" stayed true with the button unconditionally rendered --
    # which is a detached window offering to detach itself.
    flat = " ".join(head.split())
    assert '${DETACHED ? "" : `<button class="linkbtn" data-detachdetail' in flat, (
        "the detached window still offers to detach itself"
    )
    assert re.search(r"\$\{DETACHED[\s\S]{0,400}?data-closedetail", head), (
        "the detached window still shows a Close button that closes a panel rather than the "
        "window the reader is actually looking at"
    )


def test_finding_a_node_by_id_is_a_lookup_and_not_a_scan() -> None:
    """`indexOfId` walked all 15,601 nodes on every call. Fine for the handful of lookups it
    was written for, and catastrophic for the caller that arrived later: table mode asks it
    once per row, so 4,734 rows against 15,601 nodes is **73.8 million comparisons** and the
    table took **2,418 ms** to build. Sorting by Connections asks twice per comparison.

    Reported as *lag that is not obvious* -- and it is not obvious, because a view that takes
    two and a half seconds to appear reads as a slow page rather than as a defect. Rule 45 in
    the engine rather than in a pane. Measured after: 46 ms.
    """
    engine = _code(_read("graph.js"))
    # An object method, not a `function` declaration, so `_fn` cannot reach it -- and a
    # helper that silently returned the whole file here would make every assertion below
    # true of something else.
    idx = engine.split("indexOfId(id) {", 1)[1].split("\n  },", 1)[0]
    assert "new Map()" in idx and "g.idIndex" in idx, (
        "indexOfId is a linear scan again, which is 73.8 million comparisons per table build"
    )
    scan = r"for \(let i = 0; i < raw\.id\.length; i\+\+\) \{\s*if \(raw\.id\[i\] === id"
    assert not re.search(scan, idx), (
        "the scan is still the thing that answers, whatever else was added beside it"
    )
    # A shadow must never win over the node it stands in for (rule 23, in an index).
    assert "!raw.shadow[i]" in idx, (
        "the index admits shadows, so a lookup can return a placement device instead of the "
        "routine it stands for"
    )
    # And it must not outlive the payload it describes.
    #
    # **Asserted on `adoptPayload`, and on both doors into it.** It used to be asserted on
    # `mount`, which was the whole story while `mount` was the only way a payload arrived.
    # The module level added a second -- `setPayload` -- and a guard naming one function
    # would have passed while a lookup answered about the altitude the reader had just left.
    adopt = _fn(engine, "adoptPayload")
    assert "g.idIndex = null;" in adopt, (
        "the index survives a new payload, so every lookup answers about the previous program"
    )
    for door in ("mount", "setPayload"):
        assert "adoptPayload(" in _fn(engine, door), (
            f"`{door}` takes a payload without going through `adoptPayload`, so half of what "
            "a payload decides is left describing the previous one"
        )


def test_a_column_can_actually_be_resized() -> None:
    """Under `table-layout: auto` a `width` on a `th` is a suggestion the browser weighs
    against its content, and against 4,734 long qualified names it loses every time: the drag
    handler set `width: 40rem` and the column stayed at 799px, before and after. The control
    was wired, the pointer capture worked, the rem arithmetic was right, and nothing happened
    -- design rule 16 with the dead end in the stylesheet, where no check on this page was
    looking.

    And the table's own width must be the sum of its columns. With `min-width: 100%` and no
    width the specified widths become mere *ratios* of the pane, so a column dragged to 40rem
    moved 218px to 257px and stopped.
    """
    css, shell = _read("tokens.css"), _read("shell.js")
    rule = css.split("table.grid {", 1)[1].split("}", 1)[0]
    assert "table-layout: fixed" in rule, (
        "the table lays out automatically again, so every column width is a suggestion the "
        "browser is free to ignore -- and with these names it always does"
    )
    assert "min-width: 100%" not in rule, (
        "the table is stretched to the pane, which turns each column's width into a ratio "
        "of it rather than the width it says"
    )
    # On the table element, not "somewhere in the file" -- the drag handler sums the same
    # columns, so a containment check stayed true with the table's own width removed.
    assert re.search(r'<table class="grid" style="width:\$\{TABLE_COLS\.reduce', shell), (
        "the table's width is no longer the sum of its columns, so a column cannot grow past "
        "the space the table already had"
    )
    # Fixed layout stops a cell growing to fit, so long content must wrap rather than clip.
    assert re.search(r"table\.grid td, table\.grid th \{ overflow-wrap: anywhere", css), (
        "cells neither grow nor wrap, so a qualified name is cut at the column edge -- a "
        "name that is not in the program"
    )
    # Design rule 17: widths persist per program. They were written to state and never saved.
    up = shell.split("const up = () => {", 1)[1].split("};", 1)[0]
    assert "persist();" in up, (
        "a dragged column width is never stored, so design rule 17's 'widths persist per "
        "program' describes something that does not happen"
    )


def test_the_table_keeps_its_header_and_its_subject_on_screen() -> None:
    """Reported at the keyboard: *scroll down just a bit and you can no longer see the column
    headers, so you can't resize them either.* And it took the subject strip with it, so the
    pane stopped saying what it was showing exactly when the reader had gone far enough to
    need telling.

    The sticky header was declared and could never have worked. `.tablewrap` carries
    `overflow: auto`, which makes it a scroll container, and a sticky child sticks to its
    nearest scrolling ancestor -- that one. Nothing bounded its height, so it grew to all
    339,229px of the table and never scrolled a pixel: the header was stuck to a box that
    does not move while the *pane* scrolled underneath. Position, offset, z-index and
    background were all correct and all inert.
    """
    css = _read("tokens.css")
    shell = _read("shell.js")

    assert 'class="tableview"' in _fn(shell, "viewTable"), "the table view has no frame to fill"
    view = css.split(".tableview {", 1)[1].split("}", 1)[0]
    assert "flex-direction: column" in view and "height: 100%" in view, (
        "the table view no longer fills the pane, so there is nothing for the body to "
        "scroll inside of"
    )
    wrap = css.split(".tablewrap {", 1)[1].split("}", 1)[0]
    assert "overflow: auto" in wrap and "flex: 1" in wrap, (
        "the table body is not the scroller, so the header sticks to a box that never moves"
    )
    # A flex child is `min-height: auto` and refuses to shrink below its content, which
    # hands the overflow back to the pane. Rule 29's companion, for the third time.
    assert "min-height: 0" in wrap, (
        "the body refuses to shrink below its 339,229px of rows, so it hands its overflow "
        "to the pane and scrolls the header away again"
    )
    assert ".viewmount:has(.tableview) { overflow: hidden; }" in css, (
        "the pane still scrolls too, and with two scrollers the outer one takes the wheel"
    )
    # Anchored to the start of a line: `table.grid td, table.grid th {` contains the same
    # substring, and splitting on it read the `overflow-wrap` rule instead -- a check
    # vouching for a rule three lines from the one it names.
    th = css.split("\ntable.grid th {", 1)[1].split("}", 1)[0]
    assert "position: sticky" in th and "top: 0" in th and "z-index" in th, (
        "the header is not pinned, or is pinned with no offset, or is painted under the rows"
    )
    assert "background:" in th, "a transparent sticky header has the rows scrolling through it"
    # One rule, once. An equal selector later in the file restating half of it is rule 29.
    assert css.count("\ntable.grid th {") == 1, (
        "the header rule is declared twice, and the later one wins on the properties it "
        "names -- which is how a `position: sticky` with no `top` cancelled a working one"
    )


def test_the_graph_is_never_framed_against_a_container_it_cannot_measure() -> None:
    """Reported at the keyboard: switching from the table to the graph showed nothing until
    snap-to-fit was clicked. *Nice fix, but the bug is real -- the graph should have been
    there.*

    Two causes, stacked. The mode toggle called `ensureGraph()` **before** `render()`, so the
    engine mounted while `#graphMount` was still hidden from the previous paint -- and a
    hidden container is 0x0. Then `fitView` read `clientWidth || window.innerWidth`, which
    turns "I cannot measure this" into a confident wrong number: the stack was framed for a
    1275px window and drawn into a 496px canvas, so it landed off screen.

    The fallback is the half worth keeping a check on. A substitution that yields a plausible
    measurement is worse than one that refuses, because nothing downstream can tell.
    """
    shell, engine = _code(_read("shell.js")), _code(_read("graph.js"))

    # Paint, then mount. `boot()` had this right and the mode toggle did not.
    toggle = shell.split('$$("#modes button").forEach', 1)[1].split("}));", 1)[0]
    assert toggle.index("render();") < toggle.index("ensureGraph();"), (
        "the mode toggle mounts the graph before painting it, so the engine measures a "
        "container that is still hidden and frames the stack for the whole window"
    )

    fit = _fn(engine, "fitView")
    assert "window.innerWidth" not in fit and "window.innerHeight" not in fit, (
        "a fit against an unlaid-out container substitutes the window for it, which is a "
        "wrong number rather than a refusal"
    )
    assert "g.fitOwed = true;" in fit and "return { ...g.viewState, rotationX };" in fit, (
        "a fit that cannot be computed is not deferred, so it is either guessed or lost"
    )
    # And the debt is paid the first moment it can be.
    rs = engine.split("resize() {", 1)[1].split("\n  },", 1)[0]
    assert "g.fitOwed" in rs and "fitView(g.prepared)" in rs, (
        "nothing performs the deferred fit, so the graph stays framed for a size it never had"
    )
    assert "onViewStateChange(" in rs, (
        "the deferred fit sets the camera behind the back of the one path that watches it, "
        "so the HUD and the way-back anchor never see it"
    )
    # Not an unconditional re-fit: switching away and back must keep the reader's camera.
    assert "if (g.fitOwed &&" in rs, (
        "every reveal re-frames the stack, which throws away the camera the reader set "
        "(design rule 26)"
    )


def test_the_navigator_follows_whoever_drove_the_selection() -> None:
    """Reported as a question, which is the worst kind of finding: *the left menu still shows
    `main`. Is that accurate or not? I can't tell.* It was not accurate. The breadcrumb read
    `_script_of` and the navigator still marked whatever had been clicked last time.

    `onGraphSelect` moved the list and `applySelectionStep` moved the list; `selectFromNav`
    did not, on the reasoning that a row the reader clicked is already under their eye. True
    of a navigator click and false of every caller it has since acquired -- a table row, a
    hop in the detail window, the arrow in the stack, the other browser window. **A stale
    highlight is worse than none**, because it is a confident wrong answer.
    """
    shell = _code(_read("shell.js"))
    sfn = _fn(shell, "selectFromNav")
    assert "buildNav();" in sfn and "revealSelectedRoutine();" in sfn, (
        "a selection made anywhere but the navigator leaves the navigator marking whatever "
        "was clicked last time"
    )
    # In one place, not one copy per caller -- which is how three of them got it wrong.
    for driver in ("onGraphSelect", "applySelectionStep"):
        assert "revealSelectedRoutine();" in _fn(shell, driver), (
            f"{driver} no longer moves the list, so one of the ways in stopped syncing"
        )
    handler = shell.split('SYNC.addEventListener("message"', 1)[1].split("\n}\n", 1)[0]
    assert "revealSelectedRoutine" not in handler, (
        "the sync handler keeps its own copy of the reveal, which is a second place this "
        "rule has to be remembered"
    )


def test_the_table_says_which_row_is_yours() -> None:
    """Reported at the keyboard: *I cannot tell what I am viewing in Table view.* It was in
    sync the whole time -- the row carried `aria-selected` and was tinted, 238,401px down a
    4,734-row list with the scroll at nought.

    Design rule 26 says an off-screen selection is **stated** and framing it is one click
    away. That was written for the graph and never applied to the pane that needs it more:
    the graph at least dims everything else, and a table gives every row equal weight.
    """
    shell = _read("shell.js")
    table = _code(_fn(shell, "viewTable"))
    # The exact class, not a prefix of it: `tablesubject-x` contains `tablesubject`.
    assert 'class="tablesubject"' in table, "the table never says what it is showing"
    assert "row ${(at + 1).toLocaleString()} of" in table, (
        "the strip names the selection without saying where it is, which is the number that "
        "tells a reader whether scrolling is worth it"
    )
    assert "data-tablego" in table, "there is no way to get to the row it names"
    # All three absences, told apart: a routine, a node that is not a routine, and nothing.
    assert "not a routine, so it has no row here" in table and "Nothing selected" in table, (
        "a selection this table cannot show is not distinguished from no selection at all"
    )
    # The rank comes from the list the rows are drawn from, or it can disagree with them.
    assert "const rows = sortedRoutines();" in table and "${rows.map(r =>" in table, (
        "the rank is computed from a different list than the rows, so the number and the "
        "picture can disagree (rule 13)"
    )


def test_the_table_moves_to_a_new_subject_and_not_to_a_repaint() -> None:
    """Two ways to get this wrong and both were live.

    `.tablewrap` carries `overflow: auto` and looks like the scroller. Nothing bounds its
    height, so it grows to all 339,229px of the table and the *pane* scrolls instead -- the
    reveal moved a `scrollTop` with nowhere to go, and its own check compared the row against
    a box extending far below the window, which made every row "in view" and reported
    success. A guard naming the right case and measuring the wrong box.

    And "reveal when the row is out of sight" is the wrong condition: scrolling away from
    your selection to read around it is ordinary, and it made the row out of sight, so the
    next repaint dragged the reader back. **An automatic move may not fight a deliberate
    one.** It moves once per subject.
    """
    shell = _code(_read("shell.js"))
    rev = _fn(shell, "revealSelectedRow")
    assert "scrollerFor(row)" in rev, (
        "the reveal assumes which element scrolls instead of asking, and the one that looks "
        "like the scroller is not"
    )
    assert '$(".tablewrap")' not in rev, "the reveal is back on the wrapper, which never scrolls"
    # The guard, not the variable. Removing the early return leaves the assignment below it
    # intact, so "the name appears" stayed true with the behaviour gone -- rule 37, again.
    assert "if (!force && state.selected === lastRevealedRow) return;" in rev, (
        "the reveal fires on every repaint, so a reader who scrolls away from their "
        "selection is dragged back to it by the next render"
    )
    sc = _fn(shell, "scrollerFor")
    assert "scrollHeight > n.clientHeight" in sc and "overflowY" in sc, (
        "the scroller is found by name or by class rather than by whether it scrolls"
    )
    # The place is kept across a rebuild, or the condition above could never be conditional.
    keeps = r'const mount = \$\("#viewMount"\);\s*const keep = mount \? mount\.scrollTop : 0;'
    assert re.search(keeps, shell), (
        "the table's scroll position is discarded on every render, so every repaint sends a "
        "4,734-row list back to row one"
    )


def test_the_detail_window_reads_the_one_selection() -> None:
    """It held a node id of its own, and the two states drifted the first time anything else
    moved the selection: the trail's Back stepped the app to the previous routine and left
    the window standing on the one after it. Two answers to "what am I looking at", in the
    one window built to show how things connect.

    So `state.detail` is **open or not**, never *which*. The window renders `SPECIMEN`, which
    is the same thing the inspector renders, and cannot disagree with it by construction.
    Found by driving it, not by any check.
    """
    shell = _read("shell.js")
    assert re.search(r"^  detail: false,", shell, re.M), (
        "the detail window holds a subject of its own again, which can drift from the "
        "selection the rest of the application is showing"
    )
    panel = _code(_fn(shell, "detailPanel"))
    assert "const s = SPECIMEN;" in panel, "the window no longer reads the one selection"
    # A word boundary, or `state.detailAll` matches -- which is not a subject at all but
    # per-node view state, already keyed by the selection and therefore unable to drift.
    assert not re.search(r"state\.detail(?![A-Za-z])",
                         panel.split("if (!state.detail) return", 1)[1]), (
        "the window consults its own state for something other than being open"
    )
    # Every way in and every hop is an ordinary selection, so the trail records the journey
    # once and undo already reaches every step of it.
    opener = _fn(shell, "openDetail")
    assert "selectFromNav({ nodes: [nodeId] })" in opener and "pushTrail(" in opener, (
        "opening the window does not go through the one selection route, so the stack and "
        "the trail do not follow the reader into it"
    )
    assert "hopDetail(hop.dataset.detail)" in shell and "function hopDetail" in shell, (
        "a hop inside the window takes a different path from opening it -- two sets of "
        "rules about what following a rabbit does to the trail"
    )


def test_a_control_rendered_twice_is_wired_twice() -> None:
    """The trail bar is now in two places -- the app header, and the detail window, which
    needs its own because the header sits behind that window's scrim. Its *steps* were wired
    with `$$` and worked in both; **Back** and **Clear** were wired with `$`, so only
    whichever copy came first in the DOM did anything.

    Two thirds of one bar working is not a state anybody looks for, and design rule 15 says
    the trail is what makes a detour free -- so the dead control was the one a lost reader
    reaches for first.
    """
    shell = _code(_read("shell.js"))
    for attr in ("trailback", "trailclear", "trail"):
        assert re.search(rf'\$\$\("\[data-{attr}\]"\)', shell), (
            f"[data-{attr}] is wired with the singular selector, so only the first of the "
            f"two trail bars on the page responds to it"
        )
        # `(?<!\$)` or this matches the tail of `$$("[data-x]")` and fails on the fix.
        assert not re.search(rf'(?<!\$)\$\("\[data-{attr}\]"\)', shell), (
            f"[data-{attr}] still has a singular wiring beside the plural one"
        )
    # And the window really does render a second one, or the check above guards nothing.
    assert "trailBar()" in _fn(shell, "detailShell"), (
        "the detail window no longer carries the trail, so the reader inside it has no "
        "breadcrumbs and no way back"
    )


def test_the_detail_window_never_drops_a_boundary_it_cannot_name() -> None:
    """`write_backup` has two FILE OUT boundaries whose target is not a literal in the
    source -- the path is assembled, which is rule 17's whole subject. Filtering rows with no
    value dropped both and printed *"It reaches nothing outside itself"*, which is not a
    weaker claim than the truth but a different and false one. Design rule 1, self-inflicted
    within the hour."""
    shell = _read("shell.js")
    panel = _code(_fn(shell, "detailPanel"))
    assert ".filter(x => x.v)" not in panel, (
        "boundaries with no readable target are filtered out, so a routine that touches the "
        "outside world can report that it touches nothing"
    )
    assert "dtouch-unnamed" in panel, (
        "an unnamed boundary is not distinguished from a named one, so a blank reads as a "
        "target rather than as a target we could not read"
    )
    # Rule 8: a bounded view states what it left out and opens the rest in place.
    col = _fn(shell, "detailFlowCol")
    assert "data-detailall" in col and "showing ${rows.length} of ${" in col, (
        "the flow columns are capped without saying so, which is a silent filter"
    )


def test_drilling_in_opens_on_what_the_pointer_is_over() -> None:
    """The card describes the node under the pointer, which is usually **not** the selected
    one. Opening on the selection would answer a question the reader did not ask, plausibly
    enough that they might not notice.

    And the card stays untouchable. Making it clickable is the recorded decision this key
    exists to avoid re-opening: the clickable depth is the inspector's and this window's, and
    a second interactive surface floating over the canvas is how the graph and the shell
    became two applications.
    """
    shell, css = _read("shell.js"), _read("tokens.css")
    key = re.search(r'if \(e\.key === "Enter" && [^)]*\) \{\s*e\.preventDefault\(\);\s*'
                    r'openDetail\((\w+)\);', shell)
    assert key, "no key opens the detail window from the pop-up"
    assert key.group(1) == "hoverAt", (
        f"the key opens on `{key.group(1)}` rather than on the node the pop-up is about"
    )
    card_rule = css.split(".hovercard {", 1)[1].split("}", 1)[0]
    assert "pointer-events: none" in card_rule, (
        "the pop-up became interactive -- a second clickable surface over the canvas, which "
        "is the decision the drill-in key was chosen to keep"
    )
    assert "hideHoverCard();" in _fn(shell, "openDetail"), (
        "the card is left standing while the window opens over it, describing a node the "
        "pointer has stopped being over"
    )


def test_the_inspector_prints_the_types_the_server_sends() -> None:
    """It read `p.annotation` and `p.default` against a query sending `type` and `dflt`, so
    **every parameter in the pane the whole design points at** rendered as a bare name --
    no type, no default -- from the day it was written. Nothing failed, and a missing type is
    indistinguishable from a routine that has none. Rule 44, found by reading the code beside
    something else."""
    shell = _read("shell.js")
    insp = _code(shell.split("/* ── the signature, demoted ── */", 1)[1]
                      .split("const lines =", 1)[0])
    assert "p.annotation" not in insp and "p.default" not in insp, (
        "the inspector reads parameter fields the server does not send, so every type and "
        "every default renders as nothing"
    )
    assert "esc(p.text)" in insp, (
        "the inspector composes its own parameter text instead of using the pieces "
        "`signature_parts` already rendered -- a second opinion about one signature"
    )
    detail_py = (WEB / "detail.py").read_text(encoding="utf-8")
    assert "signature_parts(" in detail_py.split("def _routine(", 1)[1].split("\ndef ", 1)[0], (
        "/api/node no longer sends signature pieces, so the inspector and the card are two "
        "renderings of two different shapes again"
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
    assert "placeHoverCard()" in fill, (
        "hoverFill does not re-place the card, so a card that grows past the bottom of "
        "the pane keeps the fetched half off screen"
    )
    # And it must place against the remembered anchor, not against something it invents:
    # the pointer event is long gone by the time the fetch lands. Now that two surfaces
    # share the card, the anchor is whatever that surface's placer needs -- a cursor
    # position from the picture, a row element from the list -- so the check follows it
    # into the one function that reads it.
    place = _fn(shell, "placeHoverCard")
    assert "hoverAnchor" in place and "host.place(el, hoverAnchor)" in place, (
        "the card is re-placed without the remembered anchor, so it cannot know where it "
        "belongs by the time the fetch lands"
    )
    assert "hoverAnchor == null" in place, (
        "nothing stops a placement running with no anchor, which puts the card at 0,0"
    )


def test_the_navigator_answers_with_a_card_and_not_a_native_tooltip() -> None:
    """Reported at the keyboard: *the names are all truncated, and hover text is too tiny to
    read.* That tiny text is the browser's own `title` tooltip -- unstyleable, delayed, and
    incapable of holding anything but one line of plain text.

    Both halves, because either alone passes while the feature is dead. The row must say it
    has a card *and* stop carrying a title, since a native tooltip renders on top of the
    thing that replaced it -- so a card that works perfectly still loses to the tiny text it
    was built to remove.
    """
    shell = _read("shell.js")
    html = _read("index.html")

    rows = shell.split("function routineList() {", 1)[1].split("\n}\n", 1)[0]
    assert 'card: true' in rows and 'qual: `${r.module}.${r.name}`' in rows, (
        "routine rows no longer declare a card, or no longer carry the qualified name it "
        "leads with"
    )
    assert "title:" not in rows, (
        "a routine row still sets a native title, which renders on top of the card and is "
        "the unreadable tooltip the card exists to replace"
    )
    dress = _fn(shell, "dressNavItems")
    assert "!el.dataset.card" in dress, (
        "dressNavItems still titles a row that has a card, so every carded row gets the "
        "native tooltip back -- with the leaf name in it, which is less than it had before"
    )

    # The element is at body level. Inside the navigator it is clipped by that pane's own
    # scroller for every row near an edge, which in a 4,734-row list is most of them.
    assert 'id="navCard"' in html, "the navigator's card element is not in the markup"
    before_app = html.split('id="navCard"', 1)[0]
    assert before_app.count("</div>\n</div>") >= 1 and 'id="navCard"' in html, (
        "the card is not emitted after the application shell closes"
    )
    css = _read("tokens.css")
    nav_rule = css.split(".navcard {", 1)[1].split("}", 1)[0]
    assert "position: fixed" in nav_rule, (
        "the navigator's card is not fixed to the window, so the pane it sits in clips it"
    )
    assert "max-width" in nav_rule, "the card is unbounded and can cover the whole window"


def test_one_card_serves_both_surfaces_and_only_one_shows() -> None:
    """The picture and the list ask the same question, so they share the markup, the fetch,
    the dwell and the cache -- two copies would agree until the day one of them was edited
    (rule 36), and the day after that only one would carry the signature.

    What they may not share is *two cards on screen*. Moving from a row straight into the
    stack switches surfaces, and the invariant is held in `showHoverCard` rather than left to
    emerge from two handlers firing in a lucky order.
    """
    shell = _read("shell.js")
    show = _fn(shell, "showHoverCard")
    assert "hideHoverCard();" in show, (
        "showing a card does not tear down the previous one, so the navigator's card can "
        "stand beside a stack that has moved on to another routine"
    )
    hide = _fn(shell, "hideHoverCard")
    assert "Object.values(HOVER_HOSTS)" in hide, (
        "hiding trusts `hoverHost` to still name the visible card, which it does not once "
        "the reader has crossed from one surface to the other"
    )
    # Routed from a table, so an unknown surface is a named error rather than a card that
    # appears somewhere nobody expected (design rule 16).
    assert 'console.error("DunneFlow: no hover host"' in show, (
        "an unknown hover surface falls through silently instead of naming itself"
    )
    for fn in ("hoverPlaceInCanvas", "hoverPlaceBesideNav"):
        assert f"{fn}(" in shell.split("const HOVER_HOSTS", 1)[1].split("};", 1)[0], (
            f"{fn} is defined but the hosts table does not use it"
        )


def test_a_card_is_offered_only_where_one_node_can_answer() -> None:
    """Rule 30's family. A card needs a single node the map can answer for: a package row and
    a boundary row select **plates**, and a way in resolves to many routines -- so a card over
    one of those is either blank or a confident description of the first of twenty-four.

    A table, so adding a kind later is an entry rather than a branch, and both directions are
    asserted: every kind offering a card must be a kind the navigator can route.
    """
    shell = _read("shell.js")
    kinds = set(re.findall(r"(\w+): \"", shell.split("const NAV_CARD_KINDS = {", 1)[1]
                                              .split("};", 1)[0]))
    assert kinds, "no navigator row offers a card at all"
    routes = set(re.findall(r"^  (\w+):", shell.split("const NAV_ROUTES = {", 1)[1]
                                              .split("\n};", 1)[0], re.M))
    assert kinds <= routes, (
        f"these offer a card and have no navigator route: {sorted(kinds - routes)}"
    )
    # The plate-selecting kinds must never be in it: `/api/hover` answers about nodes, and a
    # disk id is not one, so the card would fetch and render nothing.
    assert not (kinds & {"pkg", "b", "t"}), (
        "a card is offered on a row that selects a plate or a table, neither of which is a "
        "node -- the fetch returns `found: false` and the card stays a skeleton"
    )
    assert 'closest(".nav-item[data-card]")' in _fn(shell, "navCardRow"), (
        "the hover handler does not select on the card marker, so it opens for rows that "
        "declare no card"
    )


def test_the_navigator_card_lets_go_when_its_row_moves() -> None:
    """The card is anchored to a row, so anything that moves the row invalidates it. Left
    alone through a scroll it would sit level with whatever has slid into that place -- a
    confident answer about a routine nobody is pointing at, which is precisely the failure
    this surface exists to prevent (rule 47's argument, in a list rather than in the fog)."""
    shell = _read("shell.js")
    assert re.search(r'addEventListener\("scroll", \(\) => \{ if \(hoverHost === "nav"\) '
                     r'hideHoverCard\(\); \}, true\)', shell), (
        "nothing drops the navigator's card when the list scrolls under it"
    )
    assert re.search(r'addEventListener\("resize", \(\) => \{ if \(hoverHost === "nav"\)', shell), (
        "nothing drops the navigator's card when the window resizes under it"
    )
    # Keyboard readers get the card too: these rows are buttons and the list is tabbable.
    assert re.search(r'addEventListener\("focusin"', shell), (
        "the card appears only under a pointer, so a keyboard reader can see other people "
        "using a feature they cannot reach"
    )
    place = _fn(shell, "hoverPlaceBesideNav")
    assert "row.isConnected" in place, (
        "the card is placed against a row that may have been removed by a rebuild, which "
        "reads a stale rectangle and puts the card somewhere arbitrary"
    )
    assert "nb.right + gap" in place, (
        "the card is not anchored beside the pane, so it covers the list being read"
    )


def test_every_colour_token_a_stylesheet_reaches_for_actually_exists() -> None:
    """An undefined custom property is not an error. `var(--surface-2)` where the token is
    called `--sunken` resolves to nothing, the declaration is dropped, and the element paints
    transparent -- a panel that renders, looks deliberate, and is missing the one thing it
    asked for. Rule 44's family in a stylesheet: a live rule reading a name that is not there.

    Written after making exactly that mistake in this file, which is the only reason it is
    here rather than in a list of things that would be nice to check.

    Two legitimate shapes are known and allowed rather than special-cased away. A `var(--x,
    fallback)` is the documented escape hatch and `--nav-w` genuinely uses it: the value is
    set from script by `applyNavWidth()`, so it is absent until the pane is dragged. And a
    name composed in a template literal -- `var(--sev-${k})` -- cannot be resolved statically,
    so its *prefix* is checked against the tokens instead, which still catches a rename.
    """
    css = _read("tokens.css")
    defined = set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:", css, re.M))
    assert len(defined) > 30, "the token block has shrunk to almost nothing; check the split"

    problems = []
    for name in ("tokens.css", "shell.js", "graph.js", "index.html"):
        text = _read(name)
        # `var(--x)` and `var(--x)` only -- a comma means a fallback was supplied.
        for used in set(re.findall(r"var\((--[a-z0-9-]+)\)", text)):
            if used not in defined:
                problems.append(f"{name}: var({used}) is used and no token defines it")
        # Composed names: the literal part must at least be a real family.
        for stem in set(re.findall(r"var\((--[a-z0-9-]+)\$\{", text)):
            if not any(d.startswith(stem) for d in defined):
                problems.append(f"{name}: var({stem}...) names no token family")
    assert not problems, "\n".join(problems)


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

def _code(js: str) -> str:
    """JavaScript with its comment *lines* removed.

    Three guards this session failed on the prose explaining the very thing they check --
    a check for `p.annotation` tripping on the comment saying `p.annotation` was the bug,
    and twice more besides. A containment check is only as good as the span it is taken
    over (rule 37), and a comment is not code.

    Whole lines only, which is the conservative half of the job and the only half that is
    safe. A general comment stripper has to track string state, and a first attempt at one
    ate the bodies of the template literals -- which in this codebase is where the code
    being checked actually lives, so every check passed on an empty string.

    **And the continuation lines of a block, which is what this missed for four sessions.**
    The premise above -- "every doc-block line begins with `/*`, `*` or `*/` after its
    indent" -- is false of this codebase's own house style, which indents continuations as
    plain prose:

        /* The first line, which this did blank
           the second, which it did not */

    So a guard could trip on the sentence explaining the thing it checks, which is exactly
    the failure this function was written to prevent, arriving one line lower down. It has
    cost four sessions: three guards tripping on their own prose, and one selector check
    that missed the shape it was written from.

    The state machine starts a block **only** at a line whose first non-space characters
    are `/*`, which is what keeps it safe from the hazard above: a template literal holding
    the characters `/*` does not begin a line with them, and this never looks inside a
    line. Ending is any `*/` on the line, for the same reason -- conservative in the
    direction of blanking too little rather than too much.
    """
    out, in_block = [], False
    for line in js.split("\n"):
        if in_block:
            out.append("")
            if "*/" in line:
                in_block = False
            continue
        if re.match(r"\s*(/\*|\*/?|//)", line):
            out.append("")
            # A one-line `/* … */` closes itself; a `*` or `*/` continuation is already
            # inside a block this loop has either seen the start of or never will.
            if line.lstrip().startswith("/*") and "*/" not in line:
                in_block = True
            continue
        out.append(line)
    return "\n".join(out)


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
    assert "if (g.open && (g.rows.length < cap" in tree, (
        "rows are built for packages that are not drawn -- hidden is not absent, and it "
        "cost 341 ms a keystroke the first time"
    )
    assert "r.id === state.selected" in tree, (
        "the cap can hide the selected routine, and then the list shows no row for it at "
        "all -- no highlight, no scroll, indistinguishable from the sync being broken"
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
    assert "pickable: true" in layer, (
        "the arrow is inert -- an arrow that says `it is over there` and cannot take you "
        "there is half a control"
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


# ----------------------------------------------------------------------- focus --- #
#
# From Tom, with two screenshots: "Is that the right node? There are so many, and if I
# hover over the wrong one, I get the wrong information." Dimming answers what is *not*
# yours; it does not say which of the lit dots is the one you meant, and a dimmed node in
# front of or behind it looks much the same.


def test_clicking_the_arrow_goes_to_what_it_points_at() -> None:
    """An arrow that says "it is over there" and cannot take you there is half a control.

    Two things had to be right and both fail silently. The click must route by **layer**:
    two pickable layers report through one handler now, and an `info.index` from the pointer
    layer is an index into two dozen arrows — read as a node index it selects a different
    routine, plausibly and without complaint. And it must *set* the selection rather than
    toggle it: the node an arrow stands over is by definition already picked, and `replace`
    on an already-single pick is the deliberate toggle-off (rule 33), so the one control
    whose entire purpose is `go there` would have cleared the selection instead.
    """
    engine = _read("graph.js")
    click = engine.split("onClick: (info, event) => {", 1)[1].split("\n    },", 1)[0]
    assert "startsWith('pointers-')" in click, (
        "the click does not route by layer, so an arrow's index is read as a node's"
    )
    assert "g.picks = [{ kind: 'node', index: node.index }]" in click, (
        "the arrow toggles rather than selects -- on the single pick it points at, that is "
        "the toggle-off, so `go there` clears the selection (rule 33)"
    )
    assert "fitView(g.prepared)" in click, "the arrow selects without framing what it found"
    layer = engine.split("new IconLayer({", 1)[1].split("}));", 1)[0]
    assert "pickable: true" in layer, "the arrow cannot be clicked at all"


def test_the_arrow_reports_the_node_it_points_at() -> None:
    """It stands a plate's width from its subject. A card naming that subject is how the
    reader learns the two are connected — and what the click will do."""
    hover = _read("graph.js").split("onHover: (info) => {", 1)[1].split("\n    },", 1)[0]
    assert "startsWith('pointers-')" in hover and "i = info.object.index" in hover, (
        "hovering the arrow reports whichever node shares its index, which is a different "
        "routine and a confident one"
    )


def test_focus_lets_only_the_lit_answer_and_removes_nothing() -> None:
    """The half that is easy to get wrong is the *second* one.

    Rule 19 keeps the other nine thousand on screen deliberately: a subset is only legible
    inside the shape it belongs to. Focus is about what answers a question, not about what
    is drawn — the moment it became a draw filter it would be hiding context rule 19 refused
    to hide, and design rule 1 would demand a count for it.
    """
    engine = _read("graph.js")
    body = _fn(engine, "focusable")
    assert "!g.members.size) return true" in body, (
        "with nothing selected the lock locks everything, which is a mode nobody can click "
        "their way out of"
    )
    assert "g.members.has(realIndex(d, i))" in body, (
        "the lock tests the raw index, so a shadow of a lit node is treated as fog "
        "(rules 23 and 31)"
    )
    click = engine.split("onClick: (info, event) => {", 1)[1].split("\n    },", 1)[0]
    hover = engine.split("onHover: (info) => {", 1)[1].split("\n    },", 1)[0]
    assert "focusable(g.prepared" in click, "focus does not stop a click into the fog"
    assert "focusable(g.prepared" in hover, "focus does not stop a card about the fog"
    # And it must not reach the drawing.
    for fn in ("buildLayers", "paintNodes", "recomputeMembers", "buildSelectionGeometry"):
        assert "focusable(" not in _fn(engine, fn), (
            f"{fn} consults focus, so the lock has become a filter on the picture -- rule 19 "
            "keeps the rest of the program drawn, and design rule 1 would want a count"
        )


def test_the_reticule_is_a_fixed_size_billboard_drawn_last() -> None:
    """Its job is identification, so it is the same size at every zoom — a mark that shrank
    with the picture would stop working exactly when the picture got crowded — and it is
    drawn over everything, because a ring buried behind the mass it is identifying inside
    would be pointing at nothing."""
    engine = _read("graph.js")
    ret = engine.split("if (opts.reticuleShown) {", 1)[1].split("\n  }", 1)[0]
    # The *whole* expression, not a substring of it. Written as a containment check this
    # passed against its own defect: `RETICULE_SIZE * opts.scale * opts.nodeSize` contains
    # the string it was looking for. Rule 37, for the third time this session.
    assert re.search(r"getSize: RETICULE_SIZE \* opts\.scale,", ret), (
        "the reticule is not sized by the scale multiplier alone -- tied to the node size "
        "it shrinks to nothing at dot sizes, which is where it is needed most"
    )
    assert "billboard: true" in ret and "pickable: false" in ret, (
        "the reticule is not a screen-facing mark, or it steals clicks from its own node"
    )
    assert "getPosition: (o) => o.at" in ret, (
        "the reticule stands where the *arrow* stands rather than on the node, which at the "
        "rim placement is a plate's width from the thing it is meant to identify"
    )
    assert engine.index("id: `nodes${shadingId}`") < engine.index("id: `reticules-"), (
        "the reticule is built before the nodes, so it draws underneath them"
    )
    icon = _fn(engine, "reticuleIcon")
    assert re.search(r"const probe = x\.getImageData\(.*\)\.data;", icon), (
        "nothing checks the reticule texture has any pixels in it"
    )


def test_the_cursor_over_the_picture_is_a_reticule_you_can_aim_with() -> None:
    """deck.gl's default is a hand, and a hand cannot be aimed: it is opaque, it is drawn
    below and right of its own hotspot, and at dot sizes it covers the node being pointed
    at. Reported by Tom at the keyboard -- *the hand currently covers over the node I'm
    trying to highlight, so it disappears behind the cursor at small scales.*"""
    engine = _read("graph.js")

    # Defined is not passed. The whole defect was an absent prop, so a guard that found
    # the builder and stopped would pass against a version where deck.gl still draws a
    # hand -- rule 37, and this is the half that catches it.
    ctor = engine.split("g.deckgl = new Deck({", 1)[1].split("\n  });", 1)[0]
    assert re.search(r"getCursor: \(\{ isDragging \}\)", ctor), (
        "the Deck instance sets no cursor, so deck.gl's hand is what the reader aims with"
    )
    assert "CURSOR_RETICULE" in ctor and "'grabbing'" in ctor, (
        "the cursor is not the reticule, or dragging the camera no longer says it is a grab"
    )
    # Keyed on `isHovering` it would promise that a click will answer -- which is false
    # over a fogged node while focus is locked, since deck's picking pass knows nothing
    # about `focusable()`.
    #
    # Read off the *expression*, not off the constructor. Written against the whole block
    # this failed on the comment above `getCursor` explaining why `isHovering` is not used
    # -- a guard tripped by the prose describing the decision it is checking. Rule 37's
    # companion: a containment check is only as good as the span it is taken over.
    found = re.search(r"^ +getCursor: .*$", ctor, re.M)
    assert found, "the getCursor prop is no longer one line, so this reads nothing"
    expr = found.group(0)
    assert "isHovering" not in expr, (
        "the cursor changes over anything deck considers pickable, which under a focus "
        "lock promises an answer from nodes that will refuse one"
    )

    cur = _fn(engine, "reticuleCursor")

    # The hole in the middle is the entire feature: it is what stops the mark covering the
    # node. Assert the geometry, not the word -- a version with `inner = 0` draws a solid
    # plus and passes every check that only looks for ticks.
    gap = re.search(r"inner = (\d+), outer = (\d+)", cur)
    assert gap, "the cursor no longer names its inner and outer radii, so nothing here reads"
    inner, outer = int(gap.group(1)), int(gap.group(2))
    assert 0 < inner < outer, (
        f"the cursor's ticks reach the centre (inner={inner}, outer={outer}), so it covers "
        f"the node it is aiming at -- which is the defect it was written from"
    )
    assert re.search(r"\[m, m - outer, m, m - inner\]", cur), (
        "the ticks are not built from the gap outwards, so the geometry above proves nothing"
    )

    # Two marks that mean different things must not look alike. The selection reticule is a
    # ring *plus* ticks; this is the ticks alone.
    assert "circle" not in cur and "arc(" not in cur, (
        "the cursor draws a ring, so it is the selection reticule -- one mark saying both "
        "'you picked this' and 'you are pointing here'"
    )
    assert "ring(" in _fn(engine, "reticuleIcon"), (
        "the selection reticule no longer has its ring, so the two marks are now the same "
        "shape and the check above stopped meaning anything"
    )

    # The hotspot is the centre, or the mark sits below-right of what it points at, which
    # is the hand's defect wearing a new shape.
    assert re.search(r'\}"\) \$\{m\} \$\{m\}, crosshair`', cur), (
        "the hotspot is not the centre of the mark, or the `crosshair` fallback is gone"
    )
    # Built once. `_updateCursor` runs on every change of deck's cursor state.
    assert re.search(r"^const CURSOR_RETICULE = reticuleCursor\(\);", engine, re.M), (
        "the data URI is composed per call rather than once"
    )


def test_the_focus_lock_says_it_is_on() -> None:
    """Nothing is removed from the picture, so there is no count to state — but a reader
    whose hover has gone quiet over most of the screen is owed the reason, and the reason is
    a mode they turned on. Design rule 1 in the only form that fits."""
    js, engine = _read("shell.js"), _read("graph.js")
    assert "c.focusLocked ?" in _fn(js, "countLine"), (
        "the counts line never says the fog has stopped answering"
    )
    assert "focusLocked: opts.focusLocked && g.members.size > 0" in _fn(engine, "announceCounts"), (
        "the engine reports the lock as on when it is locking nothing, so the line claims a "
        "restriction that is not happening"
    )
    assert 'data-gact="focus"' in js and 'aria-pressed="${!!state.focusLocked}"' in js, (
        "the toggle does not carry its own state, so the reader cannot see which mode they "
        "are in"
    )
    assert 'used("focus:' in js, "the pair is not counted, so neither half can be retired"


def test_every_toggle_shows_that_it_is_on() -> None:
    """`focus` shipped with its label and its tooltip changing and nothing else, so the one
    control on the graph that has two *modes* looked exactly like the six beside it that
    have none — and a reader cannot be asked to read a tooltip to find out which mode they
    are in.

    Derived from the stylesheet rather than from a list: every selector in this shell that
    styles a pressed or selected state must actually change something a person can see, and
    "same surface, faint shadow" does not count on a pale theme where one shade sits against
    another. The accent is the one channel this page spends on *in force* (design rule 4),
    so a pressed control uses it.
    """
    css = re.sub(r"/\*.*?\*/", "", _read("tokens.css"), flags=re.S)
    # Every rule whose selector mentions a pressed/selected state, with its body.
    rules = re.findall(r"([^{}]*\[aria-(?:pressed|selected)=\"true\"\][^{}]*)\{([^}]*)\}", css)
    assert rules, "nothing styles a pressed state at all -- this test is blind"
    weak = []
    for selector, body in rules:
        # A rule may legitimately style only a *part* of a pressed control (the count inside
        # a selected row, the knob on a switch); those name a descendant or a pseudo.
        if "::" in selector or re.search(r'\[aria-\w+="true"\]\s+\S', selector):
            continue
        if ":hover" in selector:
            continue
        if "var(--accent)" not in body and "var(--accent-text)" not in body:
            weak.append(selector.strip())
    assert not weak, (
        "these pressed states do not use the accent, so being on looks like being off: "
        + "; ".join(weak)
    )


def test_the_row_you_are_on_is_unmissable() -> None:
    """The whole reading loop turns on being able to answer "which one am I on" without
    hunting for it, and arriving by wheel in a list of two hundred rows is the case that
    decides whether the mark is loud enough."""
    css = re.sub(r"/\*.*?\*/", "", _read("tokens.css"), flags=re.S)
    rule = re.search(r'\.nav-item\[aria-current="true"\]\s*\{([^}]*)\}', css)
    assert rule, "the current navigator row is not marked at all"
    assert "background: var(--accent)" in rule.group(1), (
        "the current row is tinted rather than filled -- at .78rem in a list of two hundred "
        "that is not a mark the eye lands on"
    )
    # And what sits inside the row has to come with it.
    assert re.search(r'\.nav-item\[aria-current="true"\] \.navsub', css), (
        "the row goes accent and its module path stays grey on it, which is less legible "
        "than the state it replaced"
    )


def test_the_undo_pair_both_say_what_they_do() -> None:
    """Undo read "undo" and redo read a bare glyph. An arrow is a puzzle for the one control
    a stranded reader is looking for — the same argument design rule 24 makes against an
    icon rail."""
    js = _read("shell.js")
    for act in ("undo", "redo"):
        m = re.search(rf'data-gact="{act}"[^>]*>([^<]*)</button>', js, re.S)
        assert m, f"the {act} button is gone"
        assert act in m.group(1), f"the {act} button is a glyph with no word on it"


def test_every_keyboard_badge_names_a_key_something_listens_for() -> None:
    """A control can promise in its *label* as well as in its wiring, and this page had
    three that did: `S` on the inspector's source button, `G` and `T` in the worklist. None
    of the three keys was handled anywhere.

    No check here could see it. The runtime self-check reads `data-*` attributes, and a
    keyboard shortcut has none — worse, the two worklist buttons had no attributes at all,
    which makes a control *invisible* to a check that enumerates attributes. Design rule 16
    one more level out: a printed promise is a control too.
    """
    js = _read("shell.js")
    body = re.sub(r"/\*.*?\*/|//[^\n]*|<!--.*?-->", "", js, flags=re.S)
    badges = set(re.findall(r'class="k">([A-Za-z])</span>', body))
    assert badges, "no keyboard badges at all -- this test is blind"
    # Bounded to the handler's own block. Unbounded it was "everything after the keydown
    # listener", which is most of the file -- so `"s"` matched a string somewhere else and
    # the guard passed against its own defect. The same over-capture `_fn` had.
    handler = js.split("document.addEventListener(\"keydown\"", 1)[1].split("\n});", 1)[0]
    assert "e.key" in handler, "the keydown handler changed shape -- this test is blind"
    missing = sorted(b for b in badges
                     if f'"{b.lower()}"' not in handler and f'"{b}"' not in handler)
    assert not missing, (
        f"these keys are printed on controls and handled nowhere: {missing} -- the label "
        "is a promise the page does not keep"
    )


def test_a_control_that_cannot_act_says_so_rather_than_looking_live() -> None:
    """The worklist's two jump buttons were live-looking, attribute-less and wired to
    nothing — the original design rule 16 defect, still on the page.

    They are not simply wireable, and that is the interesting half: a finding carries the
    *name* it found (`self._emit`), not a node id, and eleven routines share that name.
    `queries.py` wrote the answer down before anything needed it — inventing an id to make a
    row clickable is a link to nothing — so they are disabled with the reason, which is the
    same choice `undo` makes: a control that vanishes leaves no clue the feature exists.
    """
    js = _read("shell.js")
    jump = js.split('<div class="wl-jump">', 1)[1].split("</div>", 1)[0]
    buttons = re.findall(r"<button[^>]*>", jump)
    assert len(buttons) == 2, "the worklist jump pair changed shape -- this test is blind"
    for b in buttons:
        assert "disabled" in b, (
            "a worklist jump button looks live and is wired to nothing -- if it has been "
            "built, this guard should be replaced by one asserting it acts"
        )
        assert "title=" in b, "it is disabled and does not say why"


# ─────────────────────────────────────────────────────────────── the code browser --- #

def test_the_code_views_read_the_fields_the_server_sends() -> None:
    """Rule 44, applied to the newest pane before it can sit wrong for a session.

    A live control reading a field the server does not send renders nothing and throws
    nothing -- which is worse than an unported page, because it looks finished. Checked in
    one direction only: a view may leave a served field unread, but a view reading a field
    nothing sends is drawing a blank beside a claim that is perfectly true.
    """
    js = _read("shell.js")
    py = (STATIC.parent / "code.py").read_text(encoding="utf-8")

    served_file = _served_keys(py, "build_file")
    assert {"lines", "links", "marks", "defs", "unplaced", "placed"} <= served_file, (
        "build_file changed shape -- this test is blind"
    )
    read = set(re.findall(r"\bCODEFILE\.(\w+)", js))
    assert read, "nothing reads the file payload -- this test is blind"
    # `loading` and `file` are the client's own bookkeeping on the same object, set where
    # the fetch is issued so a pane can say "opening…" without a second variable to drift.
    assert read <= served_file | {"loading", "file"}, (
        f"the code views read fields the server does not send: {sorted(read - served_file)}"
    )

    served_list = _served_keys(py, "build_files")
    row = set(re.findall(r"\bf\.(\w+)", _fn(js, "fileRowsHtml")))
    assert row, "fileRowsHtml reads nothing off a file -- this test is blind"
    # `build_files` names the row's keys inside its loop, so they are in the same set.
    assert row <= served_list, (
        f"the file list reads fields the server does not send: {sorted(row - served_list)}"
    )


def test_every_clickable_name_in_the_source_carries_an_identity() -> None:
    """Rule 30: a label is not an identity, and a control that emits none cannot act.

    Forty navigator rows once did the same nothing because the route existed and had no
    subject to act on. A name in the source is the same shape of control: it renders, it is
    obviously clickable, and without the id it selects nothing while looking alive.
    """
    js = _code(_read("shell.js"))
    span = _fn(js, "codeLineHtml")
    assert "data-codelink=" in span, "a name in the source carries no identity"
    assert "s.id" in span, "the identity written is not the node id the server resolved"

    # ...and the route must *consume* one. Both halves, because either alone passes while
    # the feature is dead: an id nothing reads, or a reader with no id to read.
    route = js.split("const CODE_ROUTES = {", 1)[1].split("\n};", 1)[0]
    assert "codelink:" in route, "nothing routes a click on a name in the source"
    assert "dataset.codelink" in route, "the route does not read the identity it is given"
    assert "selectFromNav" in route, (
        "a name in the source does not make an ordinary selection, so the stack, the trail "
        "and undo do not follow it (rule 51)"
    )
    assert "console.error" in route, (
        "a link with no identity fails silently rather than by name"
    )
    # ...and the selection must settle **before** the step is filed. A trail step captures
    # `state.selected` as its subject, so pushing first files a step whose subject is null:
    # it renders, highlights and scrolls correctly and can take nobody back (rule 33).
    # Found by reading a real step, not by any check, and this is that check.
    body = route.split("codelink:", 1)[1]
    assert body.index("await selectFromNav") < body.index("pushTrail"), (
        "the trail step is filed before the selection settles, so it carries no subject"
    )


def test_the_code_pane_is_the_box_that_scrolls() -> None:
    """Rule 50: a scroller is the element that scrolls, not the one declaring `overflow`.

    `.tablewrap` carried `overflow: auto` and looked like the scroller; nothing bounded its
    height, so it grew to all 339,229px of the table and never scrolled a pixel while the
    pane scrolled underneath it. A sticky header stuck to a box that does not move, and a
    reveal moved a `scrollTop` with nowhere to go while its own check measured against a box
    extending far below the window -- so every row read as "in view" and it reported success.
    """
    css = _read("tokens.css")
    pane = css.split(".codescroll {", 1)[1].split("}", 1)[0]
    assert "overflow" in pane, ".codescroll does not scroll"
    # Bounded by what is left, not by arithmetic. `calc(100vh - 16rem)` was right at one
    # window height and wrong at every other: on a 589px window the chrome above came to
    # more than 16rem, the box overflowed its own scroller, and exactly one line of code was
    # on screen. A flex child is `min-height: auto` and refuses to shrink below its content,
    # so both halves are needed and either alone leaves it unbounded.
    assert "flex: 1" in pane and "min-height: 0" in pane, (
        ".codescroll declares overflow with nothing bounding its height, so it grows to the "
        "whole file and hands its overflow to the pane"
    )
    assert "100vh" not in pane, (
        ".codescroll bounds itself with a guess at how much chrome sits above it"
    )
    chain = css.split(".nav-scroll { display: flex", 1)
    assert len(chain) == 2, "the navigator's scroller is not a flex column, so nothing fills"
    assert "#codePaneMount { flex: 1; min-height: 0;" in css, (
        "the mount between the group and the scroller does not pass the height through, so "
        "the chain is broken at exactly one link and the pane collapses to its content"
    )
    body = css.split(".codeview-body {", 1)[1].split("}", 1)[0]
    assert "overflow: auto" in body and "min-height: 0" in body, (
        "the centre code view is a grid/flex child at min-height auto, so it refuses to "
        "shrink below its content and hands the overflow to the document"
    )
    # And the reveal must move the box that scrolls, paired with the row that lives in it.
    #
    # Read from `revealLine`, which is where the work moved when the search arrived and
    # needed to go to a line nothing had selected. The claim did not change; its address
    # did. `revealSelectedLine` is asserted to *delegate* rather than merely to exist, or a
    # second copy could drift from this one and both would pass.
    js = _code(_read("shell.js"))
    reveal = _fn(js, "revealLine")
    assert "#codeScroll" in reveal and "#viewMount" in reveal, (
        "the reveal knows only one of the two places the file is on screen"
    )
    assert "revealLine(" in _fn(js, "revealSelectedLine"), (
        "revealSelectedLine no longer reaches revealLine, so there are two reveals and only "
        "one of them is checked here"
    )
    # The comparison itself, not the word `continue` -- which appears in this function
    # twice for other reasons, so naming it vouched for a body that had stopped comparing.
    assert "r.top >= b.top" in reveal and "r.bottom <= b.bottom" in reveal, (
        "the reveal moves unconditionally, so it fights every deliberate click: design "
        "rule 26 says an automatic scroll may only act on a row that is out of sight"
    )


def test_the_file_filter_does_not_destroy_the_field_it_types_into() -> None:
    """The glossary filter's 412 ms defect in its other costume, and the caret was the tell.

    `buildNav()` replaces the navigator's `innerHTML`. The routine search box survives that
    only because it lives in the toolbar, outside the pane; this one is inside it, so
    calling `buildNav` on every keystroke would rebuild the input mid-word.
    """
    js = _code(_read("shell.js"))
    wire = _fn(js, "wireCodeFilterOnce")
    assert "refreshCodeFileList" in wire, "the filter does not refresh anything"
    assert "buildNav()" not in wire, (
        "typing in the file filter rebuilds the whole navigator, destroying the input the "
        "reader is typing into"
    )
    narrow = _fn(js, "refreshCodeFileList")
    assert "buildNav()" not in narrow and "render()" not in narrow, (
        "the narrow refresh is not narrow -- it rebuilds the pane it is meant to spare"
    )
    assert "codeFileRows" in narrow and "note-navCode" in narrow, (
        "the refresh does not update both the rows and the count beside them, so one of "
        "them describes the other's answer"
    )
    # **The half this guard did not have, and the defect it let stand for two sessions.**
    #
    # Not calling `buildNav` is not the same as not rebuilding the pane. `buildNav()` wraps
    # every group body in a `<div class="nav-items">`, so that class inside `#navCode`
    # matches the *wrapper* first -- and writing rows into it replaced the input, the caret
    # and all, on the first character typed. The old assertion required exactly the selector
    # that caused it. A class the generator emits around every body cannot distinguish the
    # wrapper from what the body puts inside it; an id can. Rule 37.
    assert '".nav-items"' not in narrow and "'.nav-items'" not in narrow, (
        "the refresh selects `.nav-items` inside the group, which is the wrapper buildNav "
        "puts around the whole body -- so it replaces the search box the reader is typing "
        "into. Name the list by id."
    )
    assert 'id="codeFileRows"' in _fn(js, "codeFileList"), (
        "the file rows have no id of their own, so nothing can be refreshed without "
        "replacing the box above them"
    )
    body = _fn(js, "codeFileList")
    box_at, rows_at = body.find("searchBoxHtml()"), body.find('id="codeFileRows"')
    assert 'id="codeQ"' in _fn(js, "searchBoxHtml"), "the box moved out of searchBoxHtml"
    assert 0 <= box_at < rows_at, (
        "the box is not rendered outside and above the rows, so refreshing the rows reaches it"
    )


def test_a_search_never_goes_through_render_or_buildnav() -> None:
    """Rule 45, by construction rather than by luck.

    Three times now the cost has been work proportional to the whole program on every
    character typed -- the glossary filter's 412 ms by calling `render()`, the routine list's
    483 ms by building rows nobody could see, and `buildNav()`'s 1,937 ms with a large file
    open. A search box is exactly where that defect lives, so the keystroke path is asserted
    to touch only its own two strips.

    `runSearch` may not repaint the pane either: it runs on the keystroke, before the answer
    is back.
    """
    js = _code(_read("shell.js"))
    for name in ("runSearch", "refreshCodeSearch", "loadSearchHits"):
        body = _fn(js, name)
        assert body, f"{name} is gone; this guard is blind"
        assert "render()" not in body, (
            f"{name} repaints the centre pane on a keystroke -- the glossary filter's 412 ms"
        )
        assert "buildNav()" not in body, (
            f"{name} rebuilds the navigator on a keystroke, destroying the box being typed in"
        )
    wire = _fn(js, "wireCodeFilterOnce")
    assert "runSearch(" in wire, "typing does not search the source at all"


def test_a_broad_search_opens_nothing_and_says_why() -> None:
    """Rule 45's better half: the bound is the better *answer*, and it must be stated.

    Both halves, because either alone passes while the feature misleads. Opening everything
    is the cost; opening nothing without saying so is a control that reads as broken.

    The server decides `broad` and the client obeys it, so the two are asserted together --
    a client that decided for itself would be a second definition of "narrowed down".
    """
    js = _code(_read("shell.js"))
    go = _fn(js, "runSearch")
    assert "d.broad" in go or "!d.broad" in go, (
        "the client does not consult the server's own judgment of whether the answer has "
        "narrowed, so there are two definitions of it"
    )
    assert "state.searchOpen[d.rows[0].path]" in go, (
        "nothing opens itself when the answer narrows, so a reader who has found the word "
        "must click again to see it"
    )
    assert "loadSearchHits" in go, (
        "a file is marked open without its hits being fetched -- it renders `opening...` and "
        "stays that way, which is a control that renders and does nothing"
    )
    note = _fn(js, "searchNote")
    assert "SEARCH.broad" in note, "the note does not distinguish the two cases at all"
    for phrase in ("too broad", "The first is open"):
        assert phrase in note, f"the note never says {phrase!r}"


def test_a_pattern_that_cannot_be_compiled_is_named_and_not_answered_with_nothing() -> None:
    """Rule 20's `(no rows)` argument, in a search box.

    "Nothing matches" and "that is not a pattern" are opposite claims. The server keeps them
    apart with `ok`; this asserts the page reads that field rather than the row count, which
    is the version that looks identical and tells the reader the wrong thing.
    """
    js = _code(_read("shell.js"))
    note = _fn(js, "searchNote")
    assert "SEARCH.ok" in note and "SEARCH.reason" in note, (
        "the note does not distinguish a refusal from an empty result"
    )
    lst = _fn(js, "searchList")
    assert "SEARCH.ok" in lst, "the list would draw rows for an answer the server refused"


def test_whole_word_and_a_regular_expression_do_not_both_apply() -> None:
    """Rule 46: two controls answering one question is how one is answered by accident.

    A regex writes its own word edges, so wrapping one in `\\b` changes what was typed --
    `a|b` becomes `\\ba` or `b\\b`. Three things have to agree: the request must not carry
    the flag, the switch must be disabled, and it must say why. A disabled control with no
    reason is indistinguishable from a broken one.
    """
    js = _code(_read("shell.js"))
    params = _fn(js, "searchParams")
    assert "!state.searchRegex" in params, (
        "whole word is sent alongside a regular expression, so the pattern is rewritten"
    )
    box = _fn(js, "searchBoxHtml")
    assert "state.searchRegex ?" in box, "the switch does not change with the regex flag"
    assert "disabled" in box, "the switch is never disabled"
    assert "writes its own" in box, "the switch is disabled without saying why"


def test_the_code_group_declares_which_of_its_two_shapes_it_is_in() -> None:
    """A flex chain written for one state and applied to both.

    With a file open the group fills what is left of the scroller so the pane grows with the
    window. In the list it must be as tall as its content and let the navigator scroll it.
    Unqualified, the second was squashed to 118px while 1,900px of results overflowed it and
    painted over the four groups below -- every row present, sized, correct, and unclickable.

    Both halves: the attribute must be written, and the stylesheet must key on it. Either
    alone is a rule that never applies or a value nothing reads.
    """
    js, css = _code(_read("shell.js")), _read("tokens.css")
    mark = _fn(js, "markCodeMode")
    assert "codemode" in mark and "state.codeFile" in mark, (
        "the group does not say which shape it is in, or does not derive it from the file"
    )
    assert "markCodeMode()" in _fn(js, "buildNav"), (
        "nothing sets it on a rebuild, so it is right once and stale after"
    )
    assert '[data-codemode="file"]' in css, (
        "the stylesheet does not key the fill-the-scroller chain on the file state, so it "
        "applies to the list too and squashes it"
    )
    assert "codemode" in _js_set("WIRED_ATTRS"), (
        "an attribute the shell writes is missing from the roster, so the self-check will "
        "report a dead control that is not one -- and a check that cries wolf is not read"
    )
    # And the pane must never be allowed to collapse to nothing: rule 53's flex twin.
    # Comments stripped first: the note above these declarations quotes `min-height: 0` to
    # explain what it is not, and a containment check over raw CSS reads its own explanation
    # as the defect. Three guards in this file have been caught by that.
    block = re.sub(r"/\*.*?\*/", "",
                   css.split('[data-codemode="file"] {', 1)[1].split("}", 1)[0], flags=re.S)
    assert "min-height: 0" not in block, (
        "the group may shrink to nothing, so on a short window the code pane measures 0px "
        "and an open file shows no lines at all"
    )
    assert re.search(r"min-height:\s*[\d.]+rem", block), (
        "the group has no floor, in rem -- design rule 3, and rule 53 for why a floor"
    )


def test_code_is_a_centre_mode_in_all_three_places() -> None:
    """A mode is a table entry, a button and a branch, and any one of them alone is dead.

    Design rule 16 twice over: a control with no branch falls through to something that
    looks deliberate, and a branch no control reaches is a view nobody can open.
    """
    js, html = _code(_read("shell.js")), _read("index.html")
    modes = js.split("const CENTRE_MODES = ", 1)[1].split(";", 1)[0]
    assert '"code"' in modes, "code is not a centre mode, so the mode strip hides for it"
    assert 'data-mode="code"' in html, "there is no button that switches to code"
    assert 'state.view === "code"' in js, "nothing paints the code view"
    assert "viewCode()" in js, "the code view is never called"


def test_the_code_view_reads_the_one_selection_and_keeps_no_second_copy() -> None:
    """Rule 51. The detail window held a node id of its own beside the selection, and the
    two drifted the first time anything else moved one of them -- the trail's Back stepped
    the app to the previous routine and left the window on the one after it.

    So the code panes hold *which file is open* and read the selection for where in it to
    look. `state.codeFile` is a pane's subject, not a second answer to "what am I looking
    at": a file is not a node, and nothing else in the application selects one.
    """
    js = _code(_read("shell.js"))
    where = _fn(js, "selectedLine")
    assert "SPECIMEN" in where, "the code view does not read the one selection"
    assert "SPECIMEN.where" in where, (
        "the line is not taken from the selection's own recorded position"
    )
    # No second node id anywhere in the code browser's own state.
    for name in ("codeSelected", "codeNode", "codeId"):
        assert name not in js, f"the code browser keeps its own `{name}` beside the selection"


def test_the_navigator_width_is_asked_of_the_window() -> None:
    """`NAV_MAX_REM = 44` was a judgment about one screen, and the code pane is what made it
    a problem: too narrow for source at any useful type size, and a third of a 4K display.

    Asked for at the keyboard -- *users may want that side to be much wider* -- so the cap is
    what is left after the inspector's track and a floor for the centre, recomputed as the
    window changes. Never a `rem` inside a media query: that resolves against the browser's
    font size and not the page's (rule 28).
    """
    js = _code(_read("shell.js"))
    assert "NAV_MAX_REM" not in js, "the cap is still a fixed number"
    cap = _fn(js, "navMaxRem")
    assert "innerWidth" in cap, "the cap does not ask the window how wide it is"
    assert "CENTRE_FLOOR_REM" in cap, (
        "the navigator may take the whole window, leaving the centre pane nothing"
    )
    assert "NAV_MIN_REM" in cap, (
        "on a narrow window the cap can fall below the minimum, clamping the pane to a "
        "width the reader never chose"
    )
    # Re-clamped on resize, or a width saved on a wide screen survives as a track wider
    # than the window it is now in, pushing the centre off the edge with no way back.
    assert 'addEventListener("resize"' in js and "applyNavWidth()" in js
    apply = _fn(js, "applyNavWidth")
    assert "navMaxRem()" in apply, "the stored width reaches the track unclamped"
    # Two widths, because the two panes hold different things -- and asserted inside the
    # function that chooses between them, not merely somewhere in the file. `codeWidth` is
    # a state key and `widthKey` a function name, so both survive a body that has stopped
    # choosing: a name where the claim is about a behaviour (rule 37).
    getter, setter = _fn(js, "navWidth"), _fn(js, "setNavWidth")
    assert "state.codeWidth" in getter and "state.navWidth" in getter, (
        "one width serves the routine list and the source, so the reader retunes it on "
        "every switch"
    )
    assert "state.codeWidth" in setter and "state.navWidth" in setter, (
        "the drag writes one width whichever pane is open, so widening the code pane "
        "narrows the routine list behind it"
    )
    assert "navCode" in _fn(js, "codeWidthInForce"), (
        "the width is chosen without asking which group is open"
    )



def _without_catch_blocks(js: str) -> str:
    """The source with every `catch (...) { ... }` body removed, braces matched.

    Needed because "there is an answer somewhere" and "there is an answer when the request
    works" are different claims, and only the second is the one that matters: a loader
    whose success path stops assigning still has its handler, and the pane then reads
    "…" for ever on a request that returned 200.
    """
    out: list[str] = []
    i = 0
    while True:
        m = re.compile(r"\bcatch\b[^{]*\{").search(js, i)
        if not m:
            out.append(js[i:])
            return "".join(out)
        out.append(js[i:m.start()])
        depth, j = 1, m.end()
        while j < len(js) and depth:
            if js[j] == "{":
                depth += 1
            elif js[j] == "}":
                depth -= 1
            j += 1
        i = j


def _catch_blocks(js: str) -> str:
    """Just the `catch (...) { ... }` bodies — the inverse of `_without_catch_blocks`."""
    out: list[str] = []
    i = 0
    while True:
        m = re.compile(r"\bcatch\b[^{]*\{").search(js, i)
        if not m:
            return "".join(out)
        depth, j = 1, m.end()
        while j < len(js) and depth:
            if js[j] == "{":
                depth += 1
            elif js[j] == "}":
                depth -= 1
            j += 1
        out.append(js[m.end(): j])
        i = j

def test_every_loading_placeholder_is_replaced_by_an_answer() -> None:
    """`{ loading: true }` that nothing ever overwrites renders "…" for ever.

    Rule 55's defect exactly: eighty-four files sat at `opening…` because the open state
    was computed in one place and the fetch lived in another, so a thing could be marked
    in flight without anything having put it in flight. On screen that is
    indistinguishable from a slow disk, which this project has plenty of — so nobody
    would report it for a long time.

    The claim is checked **inside the enclosing function**: the holder set to loading must
    also be set to something else there, and that function must have a `catch`, or a fetch
    that throws leaves the placeholder standing.

    Written first as "some other assignment must mention a failure shape", which reported
    `SEARCH` — a loader that handles failure perfectly by building the shape into a local
    and assigning that. A guard that fires on correct code is a guard nobody reads
    (rule 43), so it checks for the handler rather than for the shape of its result.
    """
    js = _read("shell.js")
    hits = list(re.finditer(r"^\s*([A-Z][A-Z_]+)\s*=\s*\{\s*loading:\s*true", js, re.M))
    assert hits, "no loading placeholders found -- this test is blind"

    for m in hits:
        name = m.group(1)
        # The rest of the enclosing top-level function: up to the next `}` in column 1.
        end = js.find("\n}\n", m.end())
        scope = js[m.start(): end if end > 0 else len(js)]
        others = [a for a in re.findall(rf"^\s*{name}\s*=\s*(.+)$", scope, re.M)
                  if "loading: true" not in a]
        assert others, (
            f"{name} is set to {{loading: true}} and never to anything else in the same "
            "function -- the view it feeds says '…' for as long as the page is open"
        )
        # And the answer must be on the **success** path, not only in the handler. Losing
        # the assignment that reads the response leaves the `catch` one standing, so a
        # request that succeeds is the one that renders "…" for ever -- which is the
        # harder failure to notice, because the network tab shows a 200.
        happy = _without_catch_blocks(scope)
        # The lookahead sits directly after `=`, never after a `\s*`: a greedy `\s*` will
        # happily match zero characters and then test the lookahead against a space, which
        # is not `{`, so the assertion passed against the loading line itself. This guard
        # was green against its own defect until that was fixed (rule 37).
        assert re.search(rf"^\s*{name}\s*=(?!\s*\{{\s*loading)", happy, re.M), (
            f"{name} is only ever answered inside a catch -- a request that SUCCEEDS "
            "leaves the placeholder standing"
        )
        # And the handler must answer as well as exist. A `catch` that logs and returns
        # leaves the placeholder standing exactly as no `catch` would, and reads on screen
        # as a slow disk rather than as a failure.
        handlers = re.findall(r"\bcatch\b[^{]*\{", scope)
        assert handlers, (
            f"{name} is set to {{loading: true}} in a function with no catch -- a fetch "
            "that throws leaves the placeholder standing"
        )
        # The handler must answer, and there are two correct idioms for that. `loadChanges`
        # assigns the holder in the try and again in the catch; the search assigns a local
        # in both and the holder after the whole try/catch. Either reaches an answer on a
        # failing request; a `catch` that logs and returns reaches neither, and on screen
        # that is a slow disk rather than a failure.
        in_catch = re.search(rf"\b{name}\s*=", _catch_blocks(scope))
        tail = scope[scope.rfind("catch"):] if "catch" in scope else ""
        after = re.search(rf"^\s*{name}\s*=(?!\s*\{{\s*loading)",
                          _without_catch_blocks(tail), re.M)
        assert in_catch or after, (
            f"{name} has a catch that never answers and nothing assigns it afterwards -- "
            "a failed request is indistinguishable from a slow one"
        )
        assert "catch" in scope, (
            f"{name} is set to {{loading: true}} in a function with no catch -- a fetch "
            "that throws leaves the placeholder standing and the pane reads as a slow disk"
        )


def test_every_control_the_shell_writes_is_read_somewhere() -> None:
    """A promise can be printed rather than wired.

    `test_every_static_control_is_listened_for` reads `index.html`, so it sees only the
    controls that ship in the markup. Most of this application's controls are written by
    JavaScript — every navigator row, every band header, every code link — and for those
    the only check was the *runtime* self-check, which cannot run in a test and reports
    from inside the page nobody has open.

    Three keyboard badges once named keys nothing listened for, and two of them sat on
    buttons with no attributes at all. This is that failure's build-time counterpart: an
    attribute the shell writes and never reads is a control that renders, looks
    deliberate, and does nothing.

    Read means read in any of the four ways this codebase actually uses, and finding all
    four took being wrong first: the guard named `codeback`, `codedetach`, `codeopen` and
    `triaged` as dead, and every one of them works. The three code ones are **keys of
    `CODE_ROUTES`**, dispatched through a selector built at runtime, so the literal
    `[data-codeback]` appears nowhere; `triaged` is read by the **stylesheet**
    (`.wl-item[data-triaged]`). That is rule 43 repeating precisely — the last check to
    report dead controls was wrong about all five, for the same reason.

    So: matched with `closest("[data-x]")`, taken off `dataset.x`, selected by the
    stylesheet, or a key in a routing table. All of them pass, so the invariant is stated
    rather than exempted — a list of exceptions grows until the guard catches nothing
    (rule 35's lesson).

    **What this does not prove**, stated because a check whose reach is unstated gets
    trusted past it: that the read is *reachable*. Deleting the `closest` line of a
    handler while leaving its `dataset.x` line standing keeps the attribute "read" by
    code that can no longer run, and this guard passes. It catches a control nothing was
    ever written for; it cannot catch one whose listener was hollowed out. That is the
    runtime self-check's job, and it is why both exist.
    """
    js = _read("shell.js")
    written = set(re.findall(r'data-([a-z][\w-]*)="', js))
    assert len(written) > 40, f"only {len(written)} found -- this test has gone blind"
    # The roster is removed before looking, because `WIRED_ATTRS` is a list of these very
    # names as strings: leaving it in makes every attribute vouch for itself, and the
    # guard passes for a control whose listener has been deleted. That is rule 43's shape
    # inverted -- not a check that cries wolf, a check that never can.
    js = re.sub(r"const WIRED_ATTRS = new Set\(\[.*?\]\)", "", js, flags=re.S)

    css = _read("tokens.css")
    unread = []
    for attr in sorted(written):
        camel = re.sub(r"-(\w)", lambda m: m.group(1).upper(), attr)
        read = (
            f"[data-{attr}]" in js                       # matched with `closest`
            or f"dataset.{camel}" in js                  # taken off the element
            or f"[data-{attr}]" in css                   # read by the stylesheet
            or re.search(rf"^\s*{camel}:\s", js, re.M)   # a key in a routing table
        )
        if not read:
            unread.append(attr)
    assert not unread, f"controls the shell writes and nothing reads: {unread}"


# ------------------------------------------------- the change worklist, on screen --- #
#
# Three guards, one per defect found by *looking* at the change worklist for the first
# time. Every one of them was invisible to the checks that already existed, and every one
# of them rendered perfectly while doing nothing — which is the failure this file is for.


def test_a_routed_control_is_found_by_its_route_and_not_by_its_class() -> None:
    """The delegated nav handler selects on `data-nav`, the attribute the routes are keyed on.

    It selected on `.nav-item` — a class — while `NAV_ROUTES` is looked up by `data-nav`.
    So a control could carry a real route and a real id and simply never be matched, which
    is what the change worklist's rows did: `class="wl-item" data-nav="chg" data-navid=…`,
    clicked by a pointer, nothing at all. Adding the class to one row made it work.

    Neither existing guard could see it. `test_every_generated_nav_item_has_a_route` asks
    whether a *kind* has a route — `chg` does — and the roster check passes because
    `data-nav` is genuinely wired, elsewhere. Reachability was the claim nobody made.

    So this asserts the shape that makes the defect impossible rather than detectable:
    narrowing the selector back to a class is rule 36 exactly — a generic match replaced by
    a literal, and a feature disappearing with no symptom.
    """
    js = _code(_read("shell.js"))
    m = re.search(r'const NAV_SELECTOR = "([^"]+)"', js)
    assert m, "NAV_SELECTOR is gone; this guard cannot see the handler's selector"
    assert m.group(1) == "[data-nav]", (
        f"the nav handler selects on {m.group(1)!r}. It must select on the attribute the "
        "route table is keyed on: a class is a second, silent condition on being routed."
    )

    # And the handler actually uses it, rather than declaring it beside a literal. Bounded
    # to the one listener that follows the declaration: taken any wider this reads the
    # pane-folding and code listeners too, and a check over the wrong span is no check
    # (rule 37).
    handler = js[js.index("const NAV_SELECTOR"):]
    handler = handler[:handler.index("\n});") + 4]
    assert "closest(NAV_SELECTOR)" in handler, "the handler no longer selects with NAV_SELECTOR"
    assert not re.search(r'closest\("\.[\w-]+"\)', handler), (
        "the nav handler is matching a class literal again"
    )
    # The self-check must scan the same population, or it goes on vouching for a subset.
    assert "querySelectorAll(NAV_SELECTOR)" in js, (
        "selfCheck no longer scans every routed control -- it scanned `.nav-item` while "
        "the worklist's rows carried routes it never looked at"
    )


def test_a_worklist_row_has_as_many_cells_as_its_grid_has_columns() -> None:
    """A row laid into a grid written for a different row loses whatever falls off the end.

    The change rows reused `.wl-item`, whose four columns begin with a `.wl-stripe`
    severity bar `.1875rem` wide. A change row has no severity and emitted two children, so
    the **routine name** was laid into the 3px stripe column and ellipsised out of
    existence, while the module path took the `1fr` and 786 pixels. Every row of every band
    showed a module and no name, measured as a title of `scrollWidth` 188 inside a box 3px
    wide, and confirmed by eye.

    Nothing static could have caught that, because the markup and the routes were both
    right — so this checks the one thing that was wrong: the row and its grid have to agree
    about how many cells there are.
    """
    js = _read("shell.js")
    css = _read("tokens.css")

    m = re.search(r"\.chg-item\s*\{[^}]*?grid-template-columns:\s*([^;]+);", css, re.S)
    assert m, ".chg-item no longer declares its columns; this guard is blind"
    # Count tracks, not commas: `minmax(0, max-content)` is one track containing a comma.
    tracks = re.sub(r"\([^()]*\)", "", m.group(1)).split()
    assert len(tracks) == 2, f".chg-item declares {len(tracks)} columns: {tracks}"

    # The cells the row template actually emits, taken from the template literal.
    row = js[js.index('<li><button class="chg-item"'):]
    row = row[:row.index("</button></li>")]
    cells = re.findall(r'<span class="chg-(title|meta)\b', row)
    assert len(cells) == len(tracks), (
        f"the change row emits {len(cells)} cells into {len(tracks)} columns: {cells}. "
        "A cell with no column falls into whatever track is left, which is how the name "
        "ended up three pixels wide."
    )
    # And the name must be the cell that can shrink, never one pinned to a fixed size: a
    # grid child is `min-width: auto` and refuses to go below its content, which is the
    # same default that held the navigator open at 700px inside a 446px box.
    #
    # Bounded to `.chg-title`'s own braces. Taken as "within 200 characters" this passed
    # against its own mutation, reading the `min-width: 0` on the `.chg-meta` rule three
    # lines below — a guard vouching for a neighbour, which is rule 37 in the check itself
    # and the reason every one of these was run against the defect it was written from.
    title = re.search(r"\.chg-title\s*\{([^}]*)\}", css)
    assert title, ".chg-title has no rule of its own; this guard is blind"
    assert re.search(r"min-width:\s*0\b", title.group(1)), (
        ".chg-title must be allowed to shrink below its content, or the row forces the "
        f"pane wider than it is. Declared: {title.group(1).strip()!r}"
    )


def test_opening_a_navigator_group_fetches_what_its_rows_need() -> None:
    """A group whose body needs data must fetch it, and both panes must learn the answer.

    The Changes group was a closed loop with no way in. `changeList()` builds the row that
    emits the `changes` route — and only once `CHANGES` is loaded; `CHANGES` was only ever
    loaded *by* that route. So the control that starts the comparison existed only after
    the comparison had started, and opening the group gave "Not compared yet." with nothing
    to click: eighty-seven routed controls on the page, none of them emitting `changes`.

    Its companion, and the reason both halves are asserted here: `loadChanges().then(render)`
    repainted the centre and not the navigator, so the comparison arrived, the worklist
    painted, and the group beside it went on saying "open to compare them" with a blank
    count. One question, two answers (rule 51).
    """
    js = _code(_read("shell.js"))

    # The group declares the work, beside the body that needs it (design rule 16).
    grp = js[js.index('{ id: "navChanges"'):]
    grp = grp[:grp.index("body:") + 40]
    assert re.search(r"onOpen:\s*\(\)\s*=>", grp), (
        "navChanges no longer declares onOpen -- opening it cannot fetch its own rows"
    )

    # And opening a group runs it. From the table, never a branch naming this one group.
    opener = _fn(js, "setGroupOpen")
    assert "onOpen" in opener, "setGroupOpen no longer runs a group's onOpen"
    assert "navChanges" not in opener, (
        "setGroupOpen names a specific group. Route from the table, or the next group "
        "needing a fetch is one nobody remembers to add here."
    )

    # Both panes are repainted, through one door so neither can be forgotten.
    refresh = _fn(js, "refreshChanges")
    assert "buildNav()" in refresh and "render()" in refresh, (
        "refreshChanges must repaint the navigator and the centre: render() alone left the "
        "Changes group saying 'open to compare them' beside a fully painted worklist"
    )
    # Nothing may go round it.
    assert "loadChanges().then(render)" not in js, (
        "a caller is loading the comparison and repainting only the centre again"
    )


def test_a_pane_track_attribute_is_never_also_a_route_attribute() -> None:
    """`data-nav` may mean one thing. It meant two, and only the second broke.

    `PANELS` writes each pane's fold state as `data-<attr>`, taken from a name of its own,
    and the navigator's was `nav` — so `.body` carried `data-nav="on"` as a grid-track
    state while every routed control carried `data-nav="chg"`, `"pkg"`, `"routine"` as a
    route. Two unrelated meanings under one name, invisible for as long as the click
    handler happened to select on `.nav-item`: matching on the attribute instead made
    `.body` the nearest routed ancestor of every stray click in the application, and the
    self-check reported `nav "on" has no route` on the first page load.

    Rule 47's companion — one channel carrying two meanings — a layer below where that rule
    found it. Caught by widening the self-check and then *looking at the console*, which is
    the only reason it was found at all.
    """
    js = _code(_read("shell.js"))
    body = js[js.index("const PANELS = {"):]
    body = body[:body.index("\n};")]
    track_attrs = set(re.findall(r'attr:\s*"([^"]+)"', body))
    assert track_attrs, "PANELS no longer declares its attributes; this guard is blind"

    routed = re.search(r'const NAV_SELECTOR = "\[data-([^\]"]+)\]"', js)
    assert routed, "NAV_SELECTOR is not an attribute selector; see the guard above"
    clash = track_attrs & {routed.group(1)}
    assert not clash, (
        f"a pane writes data-{clash.pop()} as fold state, and that is also the attribute "
        "routed controls are matched by. One name, two meanings: every click that misses a "
        "real control walks up to the pane and is routed as one."
    )


def test_every_persisted_key_is_a_setting_the_store_knows() -> None:
    """A key saved by the shell and unknown to the store is written and thrown away.

    `PERSISTED` in `shell.js` names what is written to storage; `DEFAULTS` in
    `settings.js` names what `loadSettings` will read back, and it merges **only keys it
    declares** — deliberately, so adding a setting never has to migrate an older blob. The
    two must therefore agree, and nothing checked that they did.

    The chosen pair of revisions went in `PERSISTED` and not in `DEFAULTS`. It saved
    perfectly on every change and came back as the default on every load, so the toolbar
    forgot which two points in time were being compared between one visit and the next.
    Nothing failed and nothing was logged; `localStorage` held the right answer the whole
    time and no one ever read it.

    Its neighbour above asks whether a *setting* is read by anything. This asks the other
    direction — whether something written is a setting at all — and neither implies the
    other: `panels` was declared and unread, these two were undeclared and eagerly read.
    """
    shell = _code(_read("shell.js"))
    block = shell.split("const PERSISTED = [", 1)[1].split("];", 1)[0]
    persisted = set(re.findall(r'"([^"]+)"', block))
    assert len(persisted) > 20, "PERSISTED changed shape -- this test is blind"

    defaults = _read("settings.js").split("const DEFAULTS = {", 1)[1].split("\n};", 1)[0]
    declared = set(re.findall(r"^\s{2}([a-zA-Z][\w]*):", defaults, re.M))
    assert len(declared) > 20, "DEFAULTS changed shape -- this test is blind"

    orphans = persisted - declared
    assert not orphans, (
        f"written to storage and unknown to the store: {sorted(orphans)}. "
        "loadSettings merges only keys DEFAULTS declares, so these are saved on every "
        "change and dropped on every load -- the reader's choice silently forgotten."
    )

    # **And the other direction, which this guard did not run for as long as it existed.**
    # `followMode` was declared, set by a live control that calls `persist()`, and named in
    # the reset dialog -- and never written, because `persist()` walks PERSISTED. So the
    # setting design rule 2 exists to retire on evidence came back on its default every
    # session, and the evidence was a coin toss. Both halves are the same defect and only
    # one of them was being caught, which is rule 37: a guard that names the right case in
    # one direction has not checked the other.
    lost = declared - persisted
    assert not lost, (
        f"declared as settings and never written: {sorted(lost)}. `persist()` writes "
        "PERSISTED and nothing else, so a control can set one of these, call persist, and "
        "watch it come back as the default on the next load -- the same silent forgetting "
        "as the orphans above, arriving from the other side."
    )


# --------------------------------------------- the pair of points in time, chosen --- #

def test_the_revision_control_is_built_from_the_store() -> None:
    """An option in the markup is a claim about a program the page has not read yet.

    The toolbar carried `<option>current</option>` hard-coded, on every map, whether or not
    the store had ever heard of such a revision — the same family as the pinned figures the
    prose guards were written for, in the chrome where it is least visible. It is filled
    from `/api/revisions` now, and the markup is empty.
    """
    html = _read("index.html")
    sel = html.split('id="rev"', 1)[1].split("</select>", 1)[0]
    assert "<option" not in sel, (
        "the revision control ships options written into the markup; they must come from "
        "/api/revisions, or the toolbar states a revision this program may not have"
    )
    js = _code(_read("shell.js"))
    assert 'rev.innerHTML' in js, "nothing fills the revision control"


def test_a_revision_reads_by_the_whole_instant_that_makes_it_unique() -> None:
    """Two options a reader cannot tell apart are worse than one long one.

    The revision id is when the snapshot was **captured**, not when the code is from. The
    two snapshots here hold a Society tree from 2026-08-26 and one from 2026-08-29, and
    both were captured on the same evening twenty-nine seconds apart — so abbreviated to
    the day both options read `2026-08-29`, and to the minute both read `2026-08-29 23:46`.
    Each shortening looked reasonable until it was on screen beside its neighbour.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "revWhen")
    ends = [int(m) for m in re.findall(r"iso\.slice\(\s*\d+\s*,\s*(\d+)\s*\)", fn)]
    assert ends, "revWhen no longer slices the instant; this guard is blind"
    assert max(ends) >= 19, (
        f"the revision label stops at character {max(ends)} of the instant. Two revisions "
        "captured in the same minute then read identically in the menu."
    )


def test_a_chosen_revision_that_is_gone_is_dropped_and_said_out_loud() -> None:
    """Re-analysing can retire a snapshot the reader had chosen.

    Honouring a stored id that no longer exists is impossible; honouring it *silently* by
    falling back to a different pair is worse than either, because the toolbar goes on
    naming the pair the reader picked while the worklist compares another one. Design
    rule 1, and rule 13 — the answer has to be the one the claim beside it names.
    """
    js = _code(_read("shell.js"))
    chosen = _fn(js, "chosenPair")
    assert "comparable" in chosen and "REVISIONS.some" in chosen, (
        "chosenPair no longer checks the stored ids against the revisions that exist"
    )
    # Both ends, named individually. Asked as "does the function mention the check" this
    # passed against its own mutation: dropping the guard from one end alone leaves the
    # other still using it, and the containment check cannot tell one end from two. Rule
    # 37 in a guard, which is where it keeps turning up.
    #
    # The ends were `from` and `to` until 2026-08-30, which named a direction in time the
    # store cannot see. They are `base` (the version being read) and `compared` (the one
    # it is held against), and neither is claimed to be older -- so this guard is updated
    # deliberately rather than loosened to match whatever the code now says.
    for end in ("base", "compared"):
        line = re.search(rf"^\s*{end}:\s*(.+)$", chosen, re.M)
        assert line, f"chosenPair no longer returns a {end!r} end"
        assert "live(" in line.group(1), (
            f"the {end!r} end is taken straight from storage. A revision retired by a "
            "re-analysis would be compared against silently, under a toolbar still naming it."
        )
    lost = _fn(js, "pairLost")
    assert "REVISIONS.some" in lost, "pairLost no longer checks anything"
    # And the boot path must actually say so rather than just computing it.
    assert re.search(r"pairLost\(\)", js), "nothing asks which chosen revisions are gone"
    boot = js[js.index("await loadRevisions();"):]
    boot = boot[:boot.index("buildNav();", boot.index("buildRevControls();"))]
    assert "state.revNote" in boot, (
        "a retired revision is dropped without telling the reader -- the toolbar would name "
        "one pair while the worklist compared another"
    )
    # And the sentence must reach a surface a reader is actually looking at. Its first
    # home was `state.navNote`, which is rendered in exactly one place: the graph HUD's
    # count line, absent until the graph is mounted. The revision was correctly dropped
    # and the explanation went nowhere -- a notice written and never shown, which is the
    # defect it exists to prevent. Assigned is not shown.
    assert "state.revNote" in _fn(js, "changeNote"), (
        "revNote is set and never rendered. The Changes group's note is where the pair "
        "lives; a note nothing paints is the silent filter design rule 1 forbids."
    )


# --------------------------------------------------------------------------- #
# The source-directory readout
# --------------------------------------------------------------------------- #

def test_the_source_directory_readout_is_not_overwritten_by_the_client() -> None:
    """Rule 44, and this one was introduced and then found by *looking*.

    `applySourcePath()` read `STATS.source_root` and each revision's `source_root` and
    wrote the result into `#srcPathV` with `innerHTML`. When the server stopped sending
    those fields — because a stored root is one machine's directory layout — the function
    went on running and wrote `""`: an empty box beside a label still reading SOURCE
    DIRECTORY, on every load. Nothing threw, no test failed, and the markup was correct
    the whole time.

    Both halves are asserted, because either alone passes while the box is blank: the
    static text must be *in* the markup, and nothing may write over it.
    """
    html, shell = _read("index.html"), _code(_read("shell.js"))
    assert 'id="srcPathV">not bound' in html, "the readout must state its state, not blank"
    assert "applySourcePath" not in shell
    assert "source_root" not in shell, "the client must not read a field nothing sends"
    for writer in ("#srcPathV", "srcPathV"):
        assert writer not in shell, f"{writer} is written by the client again"


def test_the_source_directory_is_a_readout_and_does_not_present_as_a_button() -> None:
    """Design rule 16: a control that renders but does nothing looks like one that works.

    Nothing binds a source tree yet — nothing at read time opens a file from disk — so
    this must not offer the affordances of a control. It was a `<button>` with
    `aria-expanded` and a pointer cursor, all three of which promise a press.
    """
    html, css = _read("index.html"), _read("tokens.css")
    block = html.split('id="srcPath"', 1)[1].split(">", 1)[0]
    assert "aria-expanded" not in block, "nothing expands; the attribute is a promise"
    assert '<div class="srcpath" id="srcPath"' in html, "a readout, not a button"

    # Read over the *rules*, never the whole file. The first version of this asserted the
    # bare selector was absent and failed on the comment saying it had been removed; the
    # second matched only a selector sitting immediately before its `{`, and so missed
    # `.srcpath[aria-expanded="true"] .srcpath-v { … }` — a descendant selector, which is
    # the exact shape that was there. Both are rule 37 in the check rather than the code:
    # run it against the defect, and against a version where only half the feature works.
    styles = _css_code(css)
    rule = styles.split(".srcpath {", 1)[1].split("}", 1)[0]
    assert "cursor: pointer" not in rule, "a pointer cursor promises a press"
    assert ".srcpath:hover" not in styles, "a hover lift promises a press"
    # Styles for states this element no longer has are how a dead control keeps looking
    # alive; they were removed with the button rather than left behind.
    assert '.srcpath[aria-expanded="true"]' not in styles
    assert ".srcpath-was" not in styles


# --------------------------------------------------------------------------- #
# Which version is newer: derived where the program says, assumed where it does not
# --------------------------------------------------------------------------- #

def test_the_polarity_is_three_states_and_auto_is_the_default() -> None:
    """`auto` is not a nicety, it is what makes the answer survive a change of pair.

    A boolean carries an explicit choice made about *one* pair silently onto the next,
    which is rule 51's failure with the reader's own decision as the thing that drifts.
    Both defaults must be `auto` — the store's and the running state's — or the two
    disagree on the first load and only one of them is visible.
    """
    settings = _read("settings.js")
    shell = _read("shell.js")
    assert re.search(r"^  comparedIsNewer: 'auto',", settings, re.M), (
        "the stored default is no longer `auto`; a pair change would keep a stale choice"
    )
    assert re.search(r'^  comparedIsNewer: "auto",', shell, re.M), (
        "the running state's default disagrees with the stored default"
    )


def test_the_default_is_read_from_the_versions_rather_than_guessed() -> None:
    """Tom's rule: infer only when nothing more obvious is available.

    Two versions that each state a version *are* more obvious than a blind default, so
    `auto` must actually consult them. A `diffWords` that ignores the derivation is the
    feature dead inside a live key — it renders, it is correct-looking, and it answers
    from a constant (rule 36's shape).
    """
    js = _code(_read("shell.js"))
    words = _fn(js, "diffWords")
    assert "comparedIsNewerFrom(" in words, (
        "diffWords no longer derives from the versions; `auto` would be a fixed guess"
    )
    # …and the derived answer must be the *value* `auto` resolves to, not merely a word
    # appearing near it. Asked as "does `derived` appear on the auto path" this guard
    # passed against its own mutation: replacing `: derived` with `: true` leaves the
    # `derived === null` test standing, so the name is still there and the value is
    # thrown away. Rule 59's companion — a mutation that leaves any read of the thing
    # standing has not removed it — so the null-test is struck out before looking.
    newer = re.search(r"const newer = [\s\S]*?;", words)
    assert newer, "diffWords no longer resolves a single `newer`"
    without_null_test = newer.group(0).replace("derived === null", "")
    assert "derived" in without_null_test, (
        "the `auto` path tests the derived answer and then discards it — the versions are "
        "consulted and the result is a constant"
    )


def test_a_date_and_a_release_number_are_never_ranked_against_each_other() -> None:
    """The kind is checked before the key, or the page ranks `1.2.3` against `2026-08-26`.

    The keys are integer tuples and would compare perfectly happily across kinds, which is
    exactly what makes this silent: a confident, wrong ordering with no symptom. The server
    sends the kind for this reason and the page must refuse on it.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "comparedIsNewerFrom")
    guard = re.search(r"if \(!bk \|\| !ck \|\| bk !== ck\) return null", fn)
    assert guard, "the kind check is gone; two kinds would be ranked by their raw keys"
    # The refusal must come before any comparison of the keys.
    assert guard.start() < fn.index("version_key"), (
        "the keys are compared before the kinds are checked"
    )


def test_an_equal_pair_ranks_neither_end() -> None:
    """Two identical versions say nothing about order, and saying nothing is the answer.

    Falling through to "the compared is newer" here would be the tool inventing a
    direction out of evidence that explicitly has none.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "comparedIsNewerFrom")
    tail = fn[fn.rindex("for ("):]
    assert "return null" in tail, (
        "an equal pair falls through to a direction; equal versions rank neither end"
    )


# ------------------------------------------------------- switching the base --- #
#
# Seven guards. The base is what the navigator counts, the inspector reports, the code
# browser reads and the stack draws; changing it is the server rebuilding all of that from
# another graph, which is seconds the reader has to be able to watch. Every failure here
# looks exactly like a working page.


def test_the_pair_control_offers_every_pair_and_no_dead_row() -> None:
    """The reading end used to be pinned, with a disabled row saying so.

    `— reading a past revision arrives next —` was honest and is now false, and a row that
    cannot be chosen sitting under a menu of rows that can is the shape design rule 16 was
    written from wearing an apology. Removing it *is* this chunk.

    Asserted as a nested walk over the same list, not as a count: what makes every pair
    reachable is that the options are built from `usable` inside a loop over `usable`, and
    a version of this that mapped one list and hard-coded the other end would produce the
    right number of options for two revisions and the wrong ones for three.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "buildRevControls")
    assert "disabled" not in fn, (
        "the pair control still ships a row that cannot be chosen; the reading end is "
        "settable now and the row that said otherwise is what this work removes"
    )
    outer = re.search(r"usable\.map\(\s*(\w+)\s*=>", fn)
    assert outer, "the options are no longer built from the list of usable revisions"
    b = outer.group(1)
    assert re.search(rf"usable\.filter\(\s*(\w+)\s*=>\s*\1\.revision\s*!==\s*{b}\.revision",
                     fn), (
        "the comparison ends are not walked against every reading end, so some pairs the "
        "program holds cannot be reached from the control at all"
    )


def test_the_pair_control_names_both_ends_on_every_option() -> None:
    """A closed `<select>` shows the selected option's text and never its group's.

    So an option reading only "on its own" would leave the one control that answers "which
    two points am I looking at" saying nothing until it was opened. The `<optgroup>` is a
    grouping aid; the option is the answer.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "buildRevControls")
    opts = re.findall(r"<option[^>]*>(.*?)</option>", fn, re.S)
    assert len(opts) >= 2, "the control no longer writes options; this guard is blind"
    for text in opts:
        assert text.count("pairName(") >= 1 or "on its own" in text, text
    paired = [t for t in opts if "←" in t]
    assert paired, "no option names a pair"
    for text in paired:
        assert text.count("pairName(") == 2, (
            "an option naming a pair names only one of its two ends: closed, the control "
            f"would not say what it is compared with -- {text.strip()}"
        )


def test_the_pair_control_shows_the_pair_that_is_actually_in_force() -> None:
    """Two ways this went wrong, and neither threw.

    It read `chosenPair().from` — a key `chosenPair()` has never returned; it returns
    `{base, compared}` — so the marker was the empty string on every build and the menu
    opened on the wrong row after every reload.

    And the `selected` attribute is not the last word: **Chrome restores a `<select>`'s
    value across a reload**, which outranks it. After a base switch the control showed the
    pair the reader had been on *before* the switch while the strip beside it named the new
    one — one control, two claims. The value is state, so it is assigned.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "buildRevControls")
    chosen = _fn(js, "chosenPair")
    keys = set(re.findall(r"^\s*(\w+):", chosen, re.M))
    read = set(re.findall(r"pair\.(\w+)", fn))
    assert read, "buildRevControls no longer reads the chosen pair at all"
    assert read <= keys, (
        f"buildRevControls reads {sorted(read - keys)} off chosenPair(), which returns "
        f"{sorted(keys)}. The control would silently mark nothing."
    )
    assert re.search(r"rev\.value\s*=", fn), (
        "the control's value is never assigned, so a browser restoring its pre-reload "
        "value outranks the markup and the control names a pair that is not in force"
    )


def test_moving_the_reading_end_asks_the_server_and_moving_the_other_does_not() -> None:
    """Two acts, two costs, and only one of them is a rebuild.

    The comparison end is a query the server already holds the stores for. The reading end
    is the payload, the file list, both vocabulary lanes and the cover, rebuilt from another
    graph. Sending both down one path would either spend ten seconds on a question that
    costs a query, or move a label and not the map — which is what the disabled row existed
    to admit.
    """
    js = _code(_read("shell.js"))
    handler = js.split('rev.addEventListener("change"', 1)
    assert len(handler) == 2, "nothing listens to the pair control"
    body = handler[1].split("\n  }\n", 1)[0]
    assert "switchBase(" in body, "choosing a different reading end asks the server nothing"
    assert "servingRevision()" in body, (
        "the handler decides what changed from stored state rather than from what the "
        "server says it is serving -- the two disagree exactly when it matters"
    )
    assert "refreshChanges()" in body, "moving only the comparison end no longer compares"


def test_a_switch_takes_the_new_base_up_only_when_the_server_has_one() -> None:
    """Reloading on anything short of `done` puts the reader in front of the old map
    wearing the new version's label — the two claims this whole chunk keeps in step.

    And a refusal is an answer. The server refuses by name — already the base, no graph for
    it, a switch already running — and swallowing that leaves an overlay spinning against a
    rebuild that was never started (rule 35: "working" and "it failed" are opposite claims).
    """
    js = _code(_read("shell.js"))
    poll = _fn(js, "pollBase")
    assert poll.count("location.reload") == 1, (
        f"{poll.count('location.reload')} reloads in the poll -- there is one moment the "
        "new base exists, and more than one route to it is more than one claim about when"
    )
    # The condition guarding it, found by walking back to the nearest `if (` rather than by
    # a regex spanning braces: the reload sits inside a `try`, and a pattern that cannot
    # cross a `}` matched nothing at all while reporting it as "no reload here" (rule 37 --
    # a guard that names the right case and measures the wrong span).
    before = poll[:poll.index("location.reload")]
    cond = before[before.rindex("if (") + 4:].split(")")[0]
    assert 'state === "done"' in cond, (
        f"the page reloads on `{cond.strip()}` -- anything but `done` means the server is "
        "still serving the version the reader was trying to leave"
    )
    start = _fn(js, "switchBase")
    assert "d.started" in start, "a refused switch is not distinguished from a started one"
    assert 'state: "failed"' in start, "a refusal leaves the overlay claiming to be working"
    # Every failure path puts the control back. A switch that did not happen leaving the
    # control naming the pair the reader chose is one control and one strip giving two
    # answers -- and the control is the one they will believe, because it is the one they
    # touched. Counted, not merely present: it was `render()` on two of the three paths and
    # the third would have been added without it.
    for fn_name in ("switchBase", "pollBase"):
        body = _fn(js, fn_name)
        fails = len(re.findall(r'state:\s*"failed"', body))
        assert fails == body.count("switchFailed()"), (
            f"{fn_name} reports {fails} failures and restores the control "
            f"{body.count('switchFailed()')} times -- a path that leaves it naming a pair "
            "that is not in force"
        )
    assert "buildRevControls()" in _fn(js, "switchFailed"), (
        "a failed switch does not rebuild the control from the pair actually in force"
    )
    assert 'method: "POST"' in start, (
        "the switch is asked for with a GET -- one a browser prefetch or a bookmark reload "
        "fires by itself"
    )


def test_the_rebuild_overlay_names_the_version_and_sits_over_its_own_scrim() -> None:
    """A blocking surface that does not say what it is waiting for is a frozen page.

    And rule 48: a scrim must sit under the thing it dims and over everything else, so one
    element cannot serve two windows at different depths. The detail window was rendered
    perfectly, greyed, and swallowed every click into "close" for exactly this.
    """
    js = _code(_read("shell.js"))
    panel = _fn(js, "rebuildPanel")
    assert "versionName(" in panel, "the overlay does not name the version being built"
    # `\b(?!s)`, not a containment check: `REBUILD.steps` *contains* `REBUILD.step`, so the
    # obvious spelling passed while the step name had been replaced by a literal and only
    # the count was still read. That is the same shape as `routines_after` containing
    # `after` -- twice now, the guard has been the weak half rather than the mutation
    # (rule 59), and both times only running the mutation found it.
    assert re.search(r"REBUILD\.step\b(?!s)", panel), (
        "the overlay does not say which step is running -- a blocking surface that names "
        "no work is a frozen page"
    )
    assert "REBUILD.reason" in panel, "a failed switch does not say why"
    assert "REBUILD.steps" in panel and "done_steps" in panel, (
        "the overlay does not report progress against the server's own step count"
    )

    css = _css_code(_read("tokens.css"))
    z = {name: int(m) for name, m in
         re.findall(r"\.(\w[\w-]*)\s*\{[^}]*z-index:\s*(\d+)", css)}
    for scrim, win in (("rebuild-scrim", "rebuild"),
                       ("detail-scrim", "detailwin"),
                       ("viewer-scrim", "srcviewer")):
        if scrim in z and win in z:
            assert z[scrim] < z[win], (
                f".{scrim} is above .{win}, so every click on the window lands on the scrim"
            )
    # Above every other **modal**, named rather than compared against the whole stylesheet:
    # `.skip-link` legitimately sits at 200 and is off-screen until focused, so "the highest
    # number anywhere" is a claim about the wrong set. What matters is that nothing a reader
    # can open lands in front of the switch -- a source viewer over it would be reading a
    # store that is about to close.
    for other in ("detailwin", "srcviewer", "detail-scrim", "viewer-scrim"):
        if other in z:
            assert z["rebuild"] > z[other], (
                f".{other} sits above the base switch's overlay, so it can be opened over "
                "a map that is being replaced"
            )


def test_the_served_version_decides_what_is_being_read() -> None:
    """One payload set is live, so `baseRev` is the server's answer and not a stored choice.

    Three things follow and each was a defect first. A stored base that disagrees with what
    is served is **said and never acted on** — ten uninvited seconds on every open is not a
    thing to do to someone. A version cannot be compared with itself, and a reader reaches
    that state by choosing `A ← B` and then having the server come back up on B. And the
    field is persisted *after* the switch lands, not when it is asked for: written when
    asked, it records an intention as a fact and a reader who reloads mid-rebuild has a
    stored base naming a version nothing is serving.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "reconcileBase")
    assert "servingRevision()" in fn, "the reconciliation does not ask what is being served"
    assert re.search(r"state\.baseRev\s*=\s*serving", fn), (
        "the served version does not decide `baseRev`, so the strip can name a version "
        "that is not the one on screen"
    )
    assert "switchBase(" not in fn, (
        "boot switches the base by itself -- ten seconds nobody asked for, on every open"
    )
    assert "revNote" in fn, "a disagreement about which version is being read is silent"
    assert re.search(r"comparedRev\s*===\s*state\.baseRev", fn), (
        "a version can be left compared with itself, which has nothing to say"
    )
    assert "persist()" in fn, (
        "the reconciled base is not stored, so its notice fires again on every reload -- "
        "a check that cries wolf"
    )

    handler = js.split('rev.addEventListener("change"', 1)[1].split("\n  }\n", 1)[0]
    switching = handler[handler.index("switchBase("):] if "switchBase(" in handler else ""
    before = handler[:handler.index("switchBase(")] if switching else handler
    assert "state.baseRev = wantBase" not in before, (
        "the handler stores a base before the switch has landed -- an intention recorded "
        "as a fact, and wrong for as long as the rebuild runs"
    )


def test_a_group_restored_open_fetches_what_its_rows_need() -> None:
    """`onOpen` fired from the toggle only, so it ran on the open and never on the restore.

    `navOpen` is persisted, so the second visit is the one that breaks: open the Changes
    group, reload, and it sits open under "two versions — open to compare them" with
    nothing to open — the note telling the reader to do what they have already done. Rule
    55's companion, with the *restore* as the half that sets the state and does none of the
    work.

    It has been there since the group was built and takes a reload to reach; a base switch
    reloads, so every switch out of an open Changes group landed on it.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "openGroupsFetchWhatTheyNeed")
    assert "NAV_GROUPS" in fn or "navGroupsInOrder()" in fn, (
        "the boot fetch names its own list of groups rather than reading the table -- "
        "rule 36, and a group added later would be missed in silence"
    )
    assert "groupOpen(" in fn, (
        "openness is read off `state.navOpen` directly. That map is empty on a fresh "
        "profile while the group still renders open, because `groupOpen()` also knows the "
        "table's default -- so this would fetch nothing for a group that says it has rows"
    )
    assert "onOpen" in fn, "the boot fetch does not call what a group declares it needs"
    boot = js[js.index("async function boot("):]
    assert "openGroupsFetchWhatTheyNeed()" in boot, "nothing calls it at boot"


# ------------------------------------------------------------- the colour sets --- #
#
# Colour decisions live in Settings and are personal — Tom's call, and his bound is the
# accessibility one. A set covers the two channels where colour separates one *meaning*
# from another, and they are the two that both spend red: the difference channel and
# severity. Every guard here is a way a set can look chosen and be unusable.

_PAL_ROLES = ("--diff-gone", "--diff-new", "--sev-broken", "--sev-suspect", "--sev-info")


def _blocks(css: str) -> dict[str, list[tuple[str, dict[str, str]]]]:
    """Every `:root…{…}` rule that mentions a palette, as (selector, tokens) per set."""
    out: dict[str, list[tuple[str, dict[str, str]]]] = {}
    for sel, body in re.findall(r"(:root\[[^{}]*?)\s*\{([^{}]*)\}",
                                _css_code(css)):
        sel = sel.strip()
        m = re.search(r'data-palette="([a-z]+)"', sel)
        if not m:
            continue
        toks = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{6})", body))
        out.setdefault(m.group(1), []).append((sel, toks))
    return out


def _base_tokens(css: str) -> dict[str, dict[str, str]]:
    """The default set: the light `:root` block, and the explicit dark one."""
    code = _css_code(css)
    light = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{6})",
                            code.split(":root {", 1)[1].split("}", 1)[0]))
    dark = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{6})",
                           code.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0]))
    return {"light": light, "dark": dark}


def _lum(hexv: str) -> float:
    def chan(c: int) -> float:
        x = c / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexv[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_every_colour_set_clears_the_contrast_bar_on_every_ground() -> None:
    """The guard the whole feature rests on.

    A set is offered as a choice, so every colour in it is drawn as text — on the surface,
    and on its own tinted chip. Both grounds are real and a set that clears one and fails
    the other is a set that is legible in half the places it appears.

    Computed from `tokens.css` itself rather than from a list here, so a hex edited to
    something prettier fails the build instead of reaching a reader. That is the whole
    difference between a stated bound and an enforced one.
    """
    css = _read("tokens.css")
    sets = _blocks(css)
    assert set(sets) >= {"safe", "muted"}, f"the palettes have gone: {sorted(sets)}"

    base = _base_tokens(css)
    grounds = {"light": base["light"]["--surface"], "dark": base["dark"]["--surface"]}

    # The default is one of the three and is measured with them: the bar it is held to is
    # the same bar, and a set exempt from its own guard is the set that drifts.
    everything: list[tuple[str, list[tuple[str, dict[str, str]]]]] = [
        ("default", []), *sets.items()]
    problems = []
    for name, blocks in everything:
        for theme, surface in grounds.items():
            if name == "default":
                toks = base[theme]
            else:
                picked = [t for sel, t in blocks
                          if (theme == "light") == ("data-theme" not in sel
                                                    and ":not(" not in sel)]
                assert picked, f"{name} has no {theme} block"
                toks = picked[0]
            for role in _PAL_ROLES:
                fg, bg = toks.get(role), toks.get(role + "-bg")
                assert fg and bg, f"{name}/{theme} is missing {role}"
                for ground, what in ((surface, "the surface"), (bg, "its own chip")):
                    r = _ratio(fg, ground)
                    if r < 4.5:
                        problems.append(
                            f"{name}/{theme} {role} {fg} on {what} {ground}: "
                            f"{r:.2f}:1, below the 4.5:1 minimum for body text")
    assert not problems, "\n".join(problems)


def test_every_set_declares_the_same_tokens_as_the_default() -> None:
    """A set missing one token silently inherits the default's, which is two palettes.

    And it is the worst kind of two: the reader picked *blue and orange* and got one green
    among them, with nothing on screen saying a colour came from somewhere else. Asserted
    against the base block rather than a list here, so a token added to the default has to
    be added to every set (rule 36 — from the table, never from memory).
    """
    css = _read("tokens.css")
    base = _base_tokens(css)["light"]
    want = {r for r in _PAL_ROLES} | {r + "-bg" for r in _PAL_ROLES}
    assert want <= set(base), f"the default is missing {sorted(want - set(base))}"
    for name, blocks in _blocks(css).items():
        for sel, toks in blocks:
            missing = want - set(toks)
            assert not missing, (
                f"the `{name}` set's `{sel}` block does not declare {sorted(missing)} — "
                "those tokens would silently fall back to the default's, so the reader "
                "would be looking at two palettes at once"
            )


def test_a_sets_dark_block_outranks_its_light_one_by_specificity() -> None:
    """Rule 29: a media query contributes no specificity, so equal selectors go to source
    order — and the fix is specificity, never order, or the next rule takes it back.

    The ladder has to be base < a set's light block < a set's dark blocks. Counted rather
    than asserted by eye, because the whole failure mode is that it *looks* right.
    """
    def spec(sel: str) -> int:
        return len(re.findall(r"\[[^\]]+\]", sel)) + len(re.findall(r":(?!not)[a-z-]+", sel))

    css = _css_code(_read("tokens.css"))
    base_light = spec(":root")
    for name, blocks in _blocks(_read("tokens.css")).items():
        light = [spec(s) for s, _ in blocks if "data-theme" not in s and ":not(" not in s]
        dark = [spec(s) for s, _ in blocks if "data-theme" in s or ":not(" in s]
        assert light and dark, f"{name} does not have both a light and a dark block"
        assert min(light) > base_light, (
            f"the `{name}` set's light block is no more specific than the base tokens; "
            "which wins would be decided by source order"
        )
        assert min(dark) > max(light), (
            f"the `{name}` set's dark block is not more specific than its light one, so "
            "in dark mode the light colours would win or lose on position alone"
        )
    assert "data-palette" in css


def test_the_difference_channel_is_actually_drawn() -> None:
    """A palette setting whose colours nothing spends is a swatch, not a control.

    `--diff-gone` and `--diff-new` were declared in all three token blocks from the day the
    comparison vocabulary landed, carried through `diffWords()` as a `tone` per side, and
    drawn by **nothing**. Design rule 16 in a stylesheet: it renders, it looks deliberate,
    and it changes no pixel.
    """
    css = _css_code(_read("tokens.css"))
    # The *tone classes themselves*, not a count of the token anywhere. Counting
    # occurrences passed on a mutation that pointed `.tone-gone` at `--text` and left the
    # token spent elsewhere -- the guard was measuring the wrong thing, which is rule 37's
    # own lesson pointed at a stylesheet.
    for cls, tok in ((".tone-gone", "--diff-gone"), (".tone-new", "--diff-new")):
        # The rule whose selector is *exactly* the class, not any rule mentioning it. A
        # looser match survived a mutation that pointed the bare class at `--text` while a
        # compound `.chgstat.tone-gone` kept the token: the colour would then hold in the
        # stat tiles and be lost in the band headings and the navigator's note. A partial
        # loss is the hardest kind to see, and it passed.
        rules = re.findall(r"(?:^|[},])\s*" + re.escape(cls) + r"\s*\{([^}]*)\}",
                           css, re.M)
        assert rules, f"{cls} is written by the views and no rule defines it on its own"
        assert any(f"var({tok})" in r for r in rules), (
            f"{cls} does not resolve to {tok} -- the difference channel would be declared, "
            "carried through the vocabulary as a word, and drawn in the ordinary text "
            "colour, which is where it started"
        )
    js = _code(_read("shell.js"))
    assert 'tone-" + ' in js or "tone-${" in js, "nothing writes a tone class"


def test_the_tone_follows_the_word_and_not_the_side() -> None:
    """Flipping the assumption swaps which set is called arrivals, and the colour must go
    with it. A page saying "added" in the colour of *gone* is worse than one with none.

    `diffWords()` decides both, so the only way they come apart is a view taking its tone
    from the band key rather than from the word. Asserted by requiring every tone the views
    write to be read off the same object the word is.
    """
    js = _code(_read("shell.js"))
    # Both sides, counted. One `tone: newer ?` left standing while the other was pinned to
    # a literal passed a containment check -- the same shape as `REBUILD.steps` matching
    # `REBUILD.step`, and the third time in two sessions the guard was the weak half.
    derived = len(re.findall(r"tone:\s*newer\s*\?", js))
    assert derived == 2, (
        f"{derived} of the two sides derive their tone from which version is newer. A side "
        "pinned to a literal keeps its colour while the words swap, so the page says "
        "'added' in the colour of gone"
    )
    bad = re.findall(r'tone-\$\{(?!.*?\.tone)([^}]*)\}', js)
    bad = [b for b in bad if "tone" not in b]
    assert not bad, (
        f"a tone is written from {bad} rather than from the word's own `.tone` — flip the "
        "assumption and the colours stay where they were while the words move"
    )


def test_the_colour_set_is_a_setting_that_something_reads() -> None:
    """Four halves, each of which passes alone while the setting is dead: declared,
    persisted, named in the reset, and acted on."""
    st = _read("settings.js")
    js = _code(_read("shell.js"))
    assert re.search(r"^\s*palette:\s*'default'", st, re.M), "palette is not a default"
    assert "palette: 'the colour set'" in st, (
        "the reset would clear the colour set and not mention it"
    )
    assert '"palette"' in js, "palette is not persisted"
    fn = _fn(js, "applyPalette")
    assert "data-palette" in fn and "state.palette" in fn, "applyPalette reads nothing"
    assert "removeAttribute" in fn, (
        "the default does not remove the stamp, so it needs a fourth copy of every token "
        "the base block already declares"
    )
    assert js.count("applyPalette()") >= 2, (
        "applyPalette is called fewer times than applyTheme — settings are adopted after "
        "the cover names the program, so a single call at the top of boot runs against "
        "defaults the reader may have overridden"
    )


def test_the_palette_route_is_not_the_palette_stamp() -> None:
    """One attribute meaning both a route and a piece of state is what `data-nav` cost.

    `data-palette` is the stamp on `:root`; the control is `data-palette-set`, exactly as
    `data-theme-set` sits beside `data-theme`. A handler matching the stamp would fire on
    the document element.
    """
    js = _read("shell.js")
    assert "[data-palette-set]" in js, "nothing listens for the colour-set control"
    assert not re.search(r'\[data-palette\](?!-)', js), (
        "something selects on `[data-palette]`, which is the stamp on the root element "
        "rather than a control"
    )
    assert '"palette-set"' in js, "the control is not in the wired roster"


def test_the_settings_page_measures_the_colours_it_is_showing() -> None:
    """Design rule 13: a claim carries the evidence, and the evidence must be the claim's.

    Every number beside a set is computed from the tokens the page resolves, not written
    into the markup — a hex typed beside a swatch is a claim nobody can check and the first
    thing to go stale. And the *separation* number is the one that matters here: contrast
    answers "can this be read", not "can these two be told apart", and red and green are
    both perfectly legible and, to a deuteranope, the same colour.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "paletteRow")
    assert "paletteColours(" in fn, "the row does not read the tokens it is showing"
    assert "contrast(" in fn and "separation(" in fn, (
        "the row states one of the two measurements and not the other"
    )
    assert not re.search(r"#[0-9a-f]{6}", fn), (
        "a colour is written into the Settings row; it must come from the stylesheet, or "
        "the page can state a colour it is not drawing"
    )
    read = _fn(js, "paletteColours")
    assert "getComputedStyle" in read and "data-palette" in read, (
        "the colours are not read back off the stylesheet"
    )
    # The *restore*, named by the variable that holds the previous value. Asking whether
    # `setAttribute` appears passed on a mutation that deleted the restore outright, since
    # the function also stamps the set it is about to measure.
    assert re.search(r"had\s*===\s*null.*?removeAttribute|removeAttribute.*?had\s*===\s*null",
                     read, re.S) and re.search(r'setAttribute\("data-palette",\s*had\)', read), (
        "the stamp is not put back after reading, so opening Settings would leave the page "
        "wearing whichever set was measured last"
    )
    sep = _fn(js, "separation")
    assert "Math.min" in sep, (
        "separation averages rather than taking the worst — a pair obvious to most readers "
        "and invisible to some is not a pair that works"
    )
    assert "deuteranopia" in sep and "protanopia" in sep


def test_the_dead_contrast_demo_is_gone() -> None:
    """Two colour pickers, a live WCAG ratio and a verdict — reading `state._fg` and
    `state._bg`, which were in no `DEFAULTS`, persisted nowhere, and read by nothing but
    their own preview chip. It rendered, it responded to every drag, and it changed no
    colour anywhere.

    Invisible to both guards that exist for this: the dead-setting one walks `DEFAULTS` and
    these keys were never in it, and the dead-control one asks whether an attribute is read,
    and these were `id`s rather than routes.
    """
    js = _code(_read("shell.js"))
    for dead in ("state._fg", "state._bg", "fgPick", "bgPick", "previewChip"):
        assert dead not in js, (
            f"`{dead}` is back — a Settings control that computes a correct answer and "
            "applies it to nothing"
        )


def test_a_palette_token_the_graph_reads_must_reach_the_graph() -> None:
    """The implication that can rot, asserted rather than remembered.

    `applyPalette()` deliberately does not repaint the stack: a set covers `--diff-*` and
    `--sev-*`, `cssPalette()` reads neither, and a push that changes nothing is waste. The
    moment the comparison arrives in the graph as `colorBy: "change"` it will read
    `--diff-*` — and then a set chosen in Settings would move every surface except the one
    the reader is looking at, silently.

    Derived from both sides, so chunk C cannot forget (rule 36).
    """
    js = _code(_read("shell.js"))
    owned = set()
    for _name, blocks in _blocks(_read("tokens.css")).items():
        for _sel, toks in blocks:
            owned |= set(toks)
    graph_reads = set(re.findall(r'hex\("(--[a-z0-9-]+)"\)', _fn(js, "cssPalette")))
    graph_reads |= set(re.findall(r'num\("(--[a-z0-9-]+)"\)', _fn(js, "cssPalette")))
    overlap = owned & graph_reads
    if overlap:
        assert "applyGraphPalette()" in _fn(js, "applyPalette"), (
            f"the graph now reads {sorted(overlap)}, which a colour set overrides — so "
            "applyPalette() must push the palette to the stack, or choosing a set moves "
            "every surface except the picture"
        )


# ═══ the comparison, laid over the code ═══════════════════════════════════════════════
#
# Six guards, and each is written from a way this fails while looking like it works. An
# overlay is the worst shape for that: a marked line looks exactly like a marked line
# whatever it is marking, and an unmarked one looks exactly like an unchanged one.


def test_the_overlay_is_drawn_from_one_answer_in_both_panes() -> None:
    """The navigator's pane and the centre's table show the same file, so they must not be
    able to disagree about which of its lines changed.

    Two copies of the marking logic would agree until the day either was edited alone,
    which is rule 51 exactly -- and the symptom would be one pane's marks, which nobody
    compares against the other's.
    """
    js = _code(_read("shell.js"))
    for fn in ("codeTable", "codeBody"):
        body = _fn(js, fn)
        assert "codeOverlay()" in body, (
            f"`{fn}` no longer reads `codeOverlay()` — if it marks lines from anything "
            "else, the two panes are two answers about one file"
        )


def test_the_built_subtree_is_keyed_on_the_overlay_as_well_as_the_file() -> None:
    """`codeCached` hands back a node built earlier when the key matches.

    The marked rows and the other version's inserted lines live *inside* that node, so a
    key naming only the file returns the page from before the diff arrived, from before
    the compared version moved, or from before the switch was thrown -- correct-looking,
    and about a different question. This is the cheap check that makes it safe not to
    repaint on every render (rule 52's companion).
    """
    key = _fn(_code(_read("shell.js")), "codeDomKey")
    assert "codeOverlay()" in key, (
        "codeDomKey() no longer consults the overlay, so a cached page outlives the "
        "difference it was drawn from"
    )
    assert "FILEDIFF.compared" in key, (
        "the key does not name which version the overlay is against, so moving the "
        "compared end hands back the previous pair's marks"
    )


def test_every_control_that_moves_the_overlay_repaints_it() -> None:
    """Three things change what is drawn over a file without changing which file it is:
    the switch, the assumption about which version is newer, and the pair itself.

    All three must go through `repaintCode()`. `render()` alone is not enough and the
    failure is silent -- the headings swap and the code keeps the previous colours, which
    is one page giving two answers (rule 51). Named as a list here because the list of
    callers is the thing that grows.
    """
    js = _code(_read("shell.js"))
    # Anchored on the **handler**, not on the name. `js.index("assumenewer")` finds the
    # markup that writes the attribute, which is a different place entirely and always
    # comes first — a guard reading the wrong span is rule 37 in the check itself.
    for anchor, why, wanted in [
        ("codeoverlay: () =>", "the change switch",
         # **Both paths, named.** The switch has two: turning it off repaints what is
         # already known, and turning it on has to fetch first and repaint after. A guard
         # asking only whether `repaintCode` appears in the handler stayed green over a
         # mutation that deleted the second — the off path kept the word (rule 59's
         # companion: when a mutation survives, ask whether the guard is weak first).
         ["repaintCode(); return;", ".then(repaintCode)"]),
        ('$$("[data-assumenewer]")', "the assumption about which version is newer",
         ["repaintCode()"]),
        ('rev.addEventListener("change"', "moving the pair",
         ["repaintCode"]),
    ]:
        assert anchor in js, f"{why}: the handler `{anchor}` is gone; this guard is blind"
        i = js.index(anchor)
        window = js[i:i + 1800]
        for want in wanted:
            assert want in window, (
                f"{why} does not repaint the code (`{want}` is gone) — the built subtree "
                "keeps what it had, so the control appears to do nothing to the lines"
            )


def test_a_line_from_the_other_version_is_never_given_this_file_s_numbering() -> None:
    """Rule 1 in the gutter: the inserted lines carry the *compared* version's numbers.

    Renumbering them into this file would invent a position for lines that have none
    here, and the result reads as ordinary source. `ghostRows` must take its number from
    the run's own `first`, never from a counter over this file's lines.
    """
    body = _fn(_code(_read("shell.js")), "ghostRows")
    assert "run.first" in body, (
        "a ghost row's number is no longer the compared version's own — it is claiming a "
        "position in a file it is not in"
    )
    assert "ghostn" in body, (
        "the borrowed number is no longer marked as borrowed, so two numbering systems "
        "share one gutter with nothing to tell them apart"
    )


def test_the_overlay_says_what_it_could_not_show() -> None:
    """Design rule 1, in the place with no visible symptom.

    Four things a reader cannot see by looking at marked lines: which version this is
    held against, how many lines went each way, that a routine the *other* version has
    could not be placed on these lines at all, and — worst — that this file did not
    change. An unmarked file under a running comparison and an unmarked file with no
    comparison look identical.
    """
    js = _code(_read("shell.js"))
    note = _fn(js, "overlayNote")
    assert "Byte for byte the same" in note, (
        "an unchanged file says nothing, so it cannot be told from a file nobody compared"
    )
    assert "Not showing the difference" in note, (
        "the overlay switched off says nothing, so an unmarked file reads as an unchanged "
        "one"
    )
    # Whitespace-normalised, because this sentence is written across lines in a template
    # literal and a guard that can only see it on one line is a guard the next reflow
    # breaks (rule 37 -- check that it catches, not that it mentions).
    fact = re.sub(r"\s+", " ", _fn(js, "factLaneHtml"))
    assert "listed rather than marked" in fact, (
        "a routine only the other version has is drawn without saying why it could not be "
        "placed — which is a line number from another file, silently"
    )


def test_the_switch_is_not_drawn_where_it_can_do_nothing() -> None:
    """Design rule 16: a control that renders and changes nothing looks exactly like one
    that works. With one version there is no overlay to suppress."""
    body = _fn(_code(_read("shell.js")), "overlaySwitchHtml")
    assert "comparing()" in body and "return \"\"" in body, (
        "the change switch is drawn without asking whether there is a comparison — a "
        "program with one version gets a control that can never do anything"
    )


def test_the_change_chip_does_not_land_inside_a_file_s_name() -> None:
    """`dressNavItems` rewrites every nav row after it is built, and that is the trap.

    It gathers a row's loose text nodes into a `.navlabel` and re-inserts it immediately
    before `.n` — so an element written between the file name and the count is *moved in
    front of the name*, and the row renders `mensores/scriba/ ○ _queue.py`: a glyph inside
    the path. The markup `fileRowsHtml` writes is correct; something else moves it.

    Nothing that reads markup can see this, which is why it is asserted as an ordering
    over the one function's source. Found by looking at the pane.
    """
    body = _fn(_code(_read("shell.js")), "fileRowsHtml")
    assert 'class="n"' in body and "filechg" in body, "this guard has lost its subject"
    assert body.index('class="n"') < body.index("filechg"), (
        "the change chip is written before the line count, so `dressNavItems` will insert "
        "the file name after it and the glyph will render inside the path"
    )


def test_a_file_row_s_change_classes_cannot_collide_with_another_component() -> None:
    """The collision this was written from, made general.

    `fileChip` first wrote `chg-same` / `chg-mod` / `chg-one`. `.chg-mod` already existed
    — it is the change worklist's *module* label, `font-size: .7rem; color: text-faint` —
    so every **modified** file in the list rendered smaller and greyer than the unchanged
    ones. The exact inverse of what a mark is for, in a stylesheet where a class is global
    and nothing warns you, and invisible to every check that reads markup or handlers.
    Found by looking at the pane.

    Two things are asserted, and the second is what makes this survive the next class
    added here. Every class the chip writes is prefixed, **and** every rule in the
    stylesheet that mentions one is scoped to `.codefile` — so a name that another
    component later takes cannot reach these rows, and one of these cannot reach another
    component's.
    """
    js = _code(_read("shell.js"))
    body = _fn(js, "fileChip")
    written = set(re.findall(r'cls:\s*[`" ]+([a-z-]+)', body))
    written |= set(re.findall(r'\bfilechg-[a-z]+', body))
    written = {c for c in written if c.startswith("filechg")} | {
        c for c in written if c.startswith("chg")}
    assert written, "fileChip writes no classes any more; this guard has lost its subject"
    for cls in written:
        assert cls.startswith("filechg-"), (
            f"`{cls}` is not prefixed for this row. A bare name is global: `chg-mod` was "
            "already the worklist's module label, and borrowing it restyled every "
            "modified file row"
        )

    css = _css_code(_read("tokens.css"))
    for cls in written:
        for rule in re.findall(rf"[^{{}}]*\.{re.escape(cls)}[^{{}}]*\{{", css):
            assert "codefile" in rule, (
                f"`{rule.strip().rstrip('{').strip()}` styles `{cls}` without scoping it "
                "to `.codefile` — the rule reaches anything else that ever takes the name"
            )


# --------------------------------------------------------------------------- #
# The comparison over the routines: the navigator's rows and the table's column.
#
# The same overlay the code browser draws over files and lines, drawn over the things the
# map is actually about. Every guard here was written from something that went wrong while
# building it or from a rule that had already been paid for once.
# --------------------------------------------------------------------------- #


def test_the_routine_change_cell_is_written_after_the_count() -> None:
    """`dressNavItems` moves what is written before `.n`, and it moved the file chip once.

    It gathers a row's loose text into a `.navlabel` and re-inserts that span **immediately
    before** the `.n` count -- so an element emitted between the label and the count comes
    out in front of the name. The file list learnt this the expensive way: the chip landed
    inside the directory and the row read `mensores/scriba/ ○ _queue.py`, a glyph inside a
    path (rule 71). Every check that reads markup or handlers passed, because what this
    function writes and what the reader sees are different questions.

    Asserted on position within the one renderer every navigator row goes through.
    """
    js = _code(_read("shell.js"))
    row = _fn(js, "navItemHtml")
    assert "i.chg" in row, "navItemHtml no longer writes a change cell; this guard is blind"
    count_at = row.index('<span class="n${')
    chg_at = row.index("i.chg")
    assert chg_at > count_at, (
        "the change cell is emitted before the `.n` count, so `dressNavItems` re-inserts "
        "the label in front of it and the glyph lands inside the module path"
    )


def test_every_routine_mark_class_is_prefixed_and_scoped() -> None:
    """A class name is global and a stylesheet gives no warning (rule 71).

    `chg-mod` was already the change worklist's *module* label -- faint and two sizes down
    -- so the file rows' first version made every modified file render quieter than the
    unchanged ones, the exact inverse of what a mark is for. Nothing threw.

    Both directions, so this survives the next class added here: every class the chip writes
    is prefixed `rtnchg`, and every rule in the stylesheet that mentions one is scoped to
    the element that carries it -- a nav row, a table cell, or the hover card.
    """
    js = _code(_read("shell.js"))
    body = _fn(js, "routineChip")
    # **Every class the function writes, not every class already prefixed.** The first
    # version of this collected `rtnchg[a-z-]*`, which can only ever find names that
    # already pass — so renaming one to `chg-behaves` left it green, which is the whole
    # defect. A guard that cannot see the mutation is a claim nobody has tested (rule 37).
    written: set[str] = set()
    for lit in re.findall(r'cls:\s*"([^"]*)"', body):
        written |= {c for c in lit.split() if not c.startswith("tone-")}
    assert written, "routineChip writes no classes any more; this guard has lost its subject"
    assert len(written) >= 4, f"only {sorted(written)} written; this guard is blind"
    for cls in written:
        assert cls == "rtnchg" or cls.startswith("rtnchg-"), (
            f"`{cls}` is not prefixed for these rows. A bare name is global, and that is "
            "how `chg-mod` restyled every modified file row"
        )

    css = _css_code(_read("tokens.css"))
    scopes = (".nav-item", "table.grid", ".hc-chg")
    for cls in written:
        for rule in re.findall(rf"[^{{}}]*\.{re.escape(cls)}\b[^{{}}]*\{{", css):
            assert any(s in rule for s in scopes), (
                f"`{rule.strip().rstrip('{').strip()}` styles `{cls}` without scoping it to "
                f"one of {scopes} — the rule reaches anything else that takes the name"
            )


def test_the_navigator_never_asks_for_the_comparison_itself() -> None:
    """The routine group is open by default, so asking there costs every session the wait.

    317 ms warm, and 13-28 s on the first comparison of a session against the external
    volume. The Code group's precedent -- whoever opens the group does the work -- is right
    for a group that is closed by default and wrong for the one that is not. So these rows
    are *drawn* from an answer something else fetched, and the group's note says which of
    the three states it is in rather than looking like a list that did not mark itself.
    """
    js = _code(_read("shell.js"))
    for fn in ("routineList", "routineChip", "routineChange", "routineChangeNote"):
        body = _fn(js, fn)
        for asker in ("ensureChanges", "loadChanges", "ensureTableOverlay", "refreshChanges"):
            assert asker not in body, (
                f"`{fn}` calls `{asker}`. The routine list opens by default, so that makes "
                "every session pay for a comparison nobody asked for"
            )
    nav = js[js.index('{ id: "navRoutines"'):]
    nav = nav[:nav.index('{ id: "navChanges"')]
    assert "onOpen" not in nav, (
        "the Routines group declares an `onOpen`, which is how the Code group fetches — "
        "and this one is open before the reader has done anything"
    )


def test_the_table_asks_for_the_comparison_before_it_paints() -> None:
    """Asking after the paint renders a note telling the reader to open the pane they are in.

    `viewTable()` reads `CHANGES` to decide what its note says. Called before the fetch is
    started it sees `null`, so the page said *"not compared yet — open the table and these
    rows will mark themselves"* to a reader sitting in the table, and left it there for the
    thirty seconds a cold comparison takes, because nothing re-renders in between. Rule 68:
    a note telling someone to do the thing they have already done.

    `loadChanges` sets its loading flag synchronously, so asking first makes the very first
    paint say "comparing…". Found by driving a base switch, not by any check.
    """
    js = _code(_read("shell.js"))
    branch = js[js.index('else if (state.view === "table")'):]
    branch = branch[:branch.index('else if (state.view === "doc")')]
    assert "ensureTableOverlay()" in branch, (
        "the table branch no longer asks for the comparison, so the marks appear only for "
        "a reader who opened the worklist first — the closed loop rule 55's companion names"
    )
    assert branch.index("ensureTableOverlay()") < branch.index("viewTable()"), (
        "the comparison is asked for after the paint, so the first paint states that "
        "nobody has asked for it — while the request is in flight"
    )
    assert ".then(" not in branch.split("ensureTableOverlay()")[0][-200:], (
        "a promise is chained onto the paint that starts the fetch"
    )


def test_the_routine_marks_take_their_tone_from_the_word_and_not_the_side() -> None:
    """The colour has to move with the word when the reader flips which version is newer.

    `diffWords()` decides both, so the only way they come apart is a mark taking its tone
    from the band key or from the side it is on. Written as a `w.<side>.tone` read, never as
    a literal -- and the check is over the *concatenated* form as well as the interpolated
    one, because `routineChip` builds its class with `+` and the existing guard on the
    template form cannot see that.
    """
    js = _code(_read("shell.js"))
    body = _fn(js, "routineChip")
    tones = re.findall(r'"[^"]*tone-"\s*\+\s*([\w.]+)', body)
    assert len(tones) == 2, (
        f"{len(tones)} of the two one-sided marks build a tone; expected the base's and the "
        "compared's. A mark pinned to a literal keeps its colour while the words swap"
    )
    for expr in tones:
        assert expr.endswith(".tone"), (
            f"a mark's tone comes from `{expr}` rather than from the word's own `.tone`"
        )
    literal = re.findall(r'cls:\s*"[^"]*tone-(gone|new)', body)
    assert not literal, (
        f"a mark hard-codes the tone {literal} — flip the assumption and it says 'added' "
        "in the colour of gone"
    )


def test_the_table_columns_and_their_widths_and_labels_are_one_list() -> None:
    """Three hand-kept lists of the same columns is two places to forget one (rule 36).

    A column in `TABLE_COLS` with no width contributes `undefined` to the table's own width
    and renders at whatever is left; a width with no column is a setting nothing spends. The
    heading is the third: a column with no label draws a blank button that still sorts.
    """
    js = _code(_read("shell.js"))
    st = _code(_read("settings.js"))

    m = re.search(r"const TABLE_COLS = \[(.*?)\]", js, re.S)
    assert m, "TABLE_COLS is no longer a list literal; this guard is blind"
    cols = set(re.findall(r'"(\w+)"', m.group(1)))
    assert len(cols) >= 4, f"only {len(cols)} columns; this guard is blind"

    m = re.search(r"const TABLE_LABELS = \{(.*?)\}", js, re.S)
    assert m, "TABLE_LABELS is no longer an object literal; this guard is blind"
    labels = set(re.findall(r"(\w+):", m.group(1)))

    # **Each file separately.** Unioned, a key present in one and missing from the other
    # still appears — and the two are two copies of one default: `settings.js` is what the
    # store hands a fresh reader and `shell.js` is the live state. A column missing from
    # either renders at `undefined` rem for exactly one of those two readers.
    widths = {}
    for name, src in (("shell.js", js), ("settings.js", st)):
        m = re.search(r"colWidths:\s*\{(.*?)\}", src, re.S)
        assert m, f"colWidths is no longer an object literal in {name}; this guard is blind"
        widths[name] = set(re.findall(r"(\w+):", m.group(1)))

    for name, keys in widths.items():
        assert cols == keys, (
            f"the columns {sorted(cols)} and the widths in {name} {sorted(keys)} disagree"
        )
    assert cols == labels, (
        f"the columns {sorted(cols)} and their labels {sorted(labels)} disagree"
    )


def test_every_change_band_the_server_sends_becomes_a_status() -> None:
    """A band added on the wire and forgotten in the client reads as *unchanged*.

    That is the worst outcome available here and it is silent: the routines in it get the
    same em dash and the same "unchanged between these two versions" as everything the
    comparison genuinely found nothing about. Rule 44's shape -- a view reading the fields a
    server sends -- pointed the other way, at the fields it must not ignore.

    The four presence and behaviour bands only. `counts`, `presence` and `identical` are
    about the comparison rather than about one routine, and nothing here should map them.
    """
    js = _code(_read("shell.js"))
    py = (Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"
          / "changes.py").read_text(encoding="utf-8")

    m = re.search(r"const CHANGE_BANDS = \{(.*?)\n\};", js, re.S)
    assert m, "CHANGE_BANDS is no longer an object literal; this guard is blind"
    mapped = set(re.findall(r"(\w+):", m.group(1)))

    ret = py[py.index("        return {"):]
    served = set(re.findall(r'^\s*"(\w+)": ', ret, re.M))
    bands = {k for k in served
             if k in {"only_in_base", "only_in_compared", "behaves", "edited_only"}}
    assert len(bands) == 4, f"changes.py sends {sorted(bands)}; this guard is blind"
    assert bands <= mapped, (
        f"the bands {sorted(bands - mapped)} reach no status, so every routine in them "
        "renders as unchanged"
    )
    assert mapped <= served, (
        f"{sorted(mapped - served)} is mapped and never sent"
    )


def test_a_routine_only_the_compared_version_has_is_counted_and_never_marked() -> None:
    """Both surfaces list the routines of the version on screen, so it has no row here.

    Marking one would need a row, and inventing a row would name a routine among what this
    version contains -- the same argument the code overlay makes about a line whose number
    belongs to another file (rule 1). So it is *stated*: counted, named as the other
    version's, and said to be absent from the list. Design rule 1's own case, and the state
    with no visible symptom.
    """
    js = _code(_read("shell.js"))
    counts = _fn(js, "routineChangeCounts")
    assert "only_in_compared" in counts, (
        "the count of routines only the compared version has is not taken from the band, "
        "so it cannot be stated — and it can never be counted from the rows"
    )
    note = _fn(js, "routineChangeNote")
    assert "only_compared" in note and "not listed here" in note, (
        "the note does not say that the compared version's own routines are absent from "
        "this list; an unstated absence is design rule 1's defect"
    )
    # The table says it in two places -- above the rows and in the footer, because 4,733
    # rows is further than a reader can see -- and **both come from one function**. Written
    # out twice they drifted at once: the note omitted a band with nothing in it and the
    # footer printed `0 deleted`, one answer stated two ways in one pane (rule 51).
    view = _fn(js, "viewTable")
    says = view.count("routineChangeNote()")
    assert says == 2, (
        f"the table states the comparison from {says} calls to `routineChangeNote()`; it "
        "needs one above the rows and one in the footer, and a second copy of the sentence "
        "is a second answer to what the comparison found"
    )


def test_the_change_column_sorts_what_changed_to_the_top() -> None:
    """A first click on a column sorts descending, so the weights have to run that way.

    Written as a rank where 0 was best, the first click on Changed opened on four thousand
    unchanged routines -- a control that looks like it did nothing. `fan` already sets the
    convention: bigger is more interesting.

    The order is the change worklist's, and it is a constant rather than derived from
    `diffBands()`. An earlier version derived it, which read as though it had been thought
    about and was a difference that cannot occur: both surfaces list the base's routines, so
    `only_in_compared` never owns a row and only one presence band is ever populated.
    """
    js = _code(_read("shell.js"))
    m = re.search(r"const CHANGE_WEIGHT = \{(.*?)\};", js, re.S)
    assert m, "CHANGE_WEIGHT is no longer an object literal; this guard is blind"
    w = {k: int(v) for k, v in re.findall(r"(\w+):\s*(\d+)", m.group(1))}
    assert set(w) >= {"behaves", "only_base", "edited", "same"}, f"weights are {w}"
    assert w["behaves"] > w["only_base"] > w["edited"] > w["same"] > 0, (
        f"the weights {w} do not run in the worklist's order, heaviest first"
    )
    body = _fn(js, "changeWeight")
    assert "diffBands" not in body, (
        "the sort order is derived from which version the reader assumes is newer. It "
        "cannot be: only one presence band ever owns a row in a list of the base's "
        "routines, so the assumption changes the words and never the order"
    )
    assert "|| 0" in body, "a routine with no status must weigh nothing, not `undefined`"


def test_the_routine_overlay_is_a_setting_that_something_reads() -> None:
    """Four halves, each of which passes alone while the switch is dead.

    Declared in the store, persisted, named in the reset dialog, and actually consulted.
    `panels` sat in `settings.js` for months -- persisted, versioned, named in the reset as
    "panel layout" -- with nothing anywhere reading it (design rule 16's second half).
    """
    st = _read("settings.js")
    js = _code(_read("shell.js"))
    assert re.search(r"^\s*tableOverlay:\s*true", st, re.M), (
        "tableOverlay is not a default, so `loadSettings` drops it on every load"
    )
    assert "tableOverlay: 'the change overlay" in st, (
        "the reset would clear the routine overlay without mentioning it"
    )
    # **Parsed out of `PERSISTED`, not looked for anywhere in the file.** A containment
    # check passed the mutation that deleted the key from the list, because the name is
    # also a quoted string in `OVERLAY_SWITCHES` — a guard that checks a name appears has
    # not checked that anything happens (rule 37).
    m = re.search(r"const PERSISTED = \[(.*?)\];", js, re.S)
    assert m, "PERSISTED is no longer a list literal; this guard is blind"
    persisted = set(re.findall(r'"(\w+)"', m.group(1)))
    assert len(persisted) > 20, f"PERSISTED holds {len(persisted)} keys; this guard is blind"
    assert "tableOverlay" in persisted, (
        "tableOverlay is not in PERSISTED, so the reader's choice is dropped on every load"
    )
    assert "state.tableOverlay" in _fn(js, "tableOverlayOn"), (
        "tableOverlayOn does not read the setting"
    )
    assert "comparing()" in _fn(js, "tableOverlayOn"), (
        "the switch governs the marks without asking whether there is a comparison at all, "
        "so it would draw for a program holding one version"
    )
    sw = _fn(js, "overlaySwitchHtml")
    assert "if (!comparing()) return" in sw, (
        "the switch is drawn where it cannot act — design rule 16's dead control with an "
        "excuse attached"
    )


def test_the_edited_glyph_is_not_the_separator_it_sits_beside() -> None:
    """A glyph that is also the punctuation around it is not a glyph.

    The `edited` mark was `\\u00b7`, and the note that states the counts separates them with
    `\\u00b7` too — so the line read "18 behave differently · · 15 edited only", two dots
    running together with nothing to say which was a word and which was punctuation. Found
    by reading the pane, not by any check.
    """
    js = _code(_read("shell.js"))
    body = _fn(js, "routineChip")
    m = re.search(r'rtnchg-edited[^}]*?glyph:\s*"([^"]+)"', body, re.S)
    assert m, "the edited mark no longer carries a glyph; this guard is blind"
    glyph = m.group(1).encode().decode("unicode_escape")

    note = _fn(js, "routineChangeNote")
    seps = set(re.findall(r"\}</b>\s*([^<{\s])", note)) | set(
        re.findall(r"`\s*([·|])\s*", note))
    assert glyph not in seps, (
        f"the edited glyph `{glyph}` is also the separator between the counts, so the note "
        "prints it twice in a row and neither reads as the other"
    )
    assert glyph in note, (
        "the note states a count for edited routines without their own glyph beside it, so "
        "the legend and the mark are two vocabularies"
    )


def test_the_routine_list_landing_repaints_both_things_that_read_it() -> None:
    """`ROUTINES` feeds two panes and only one of them was repainted when it arrived.

    A reader whose centre view was the table when the page opened got a table of nought
    rows under *"Reading the routine list…"* — permanently. The list had arrived, the
    navigator showed all 4,733 of them, and nothing ever asked the centre again. A message
    that is true at the instant it is written and never comes back is worse than a blank.

    Predates the change marks; found by driving those and confirmed against `HEAD` rather
    than assumed. Rule 35's family: the array is assigned, and a view that reads it is
    never repainted.

    **Every call site, not the first one in the file.** Written as `js.index(...)` this
    guarded whichever caller happened to be written earliest, and the module level's fold
    -- which loads the same list to colour a plate by what changed -- arrived above it and
    inherited a guard that was looking somewhere else. That is rule 55 in the test rather
    than in the code: a bound kept at one call site rots as callers are added.
    """
    js = _code(_read("shell.js"))
    sites = []
    at = js.find("loadRoutines().")
    while at != -1:
        sites.append(js[at:js.index("\n}", at)])
        at = js.find("loadRoutines().", at + 1)
    assert len(sites) >= 2, f"only {len(sites)} call sites -- this guard has gone blind"
    for call in sites:
        assert "buildNav()" in call, (
            "a caller of loadRoutines does not rebuild the navigator when the list lands"
        )
        assert "render()" in call, (
            "a caller of loadRoutines does not repaint the centre pane, so table mode holds "
            "nought rows under 'Reading the routine list…' for the rest of the session"
        )
    # Both halves, on the failure path too: a list that could not be read must leave both
    # panes stating that rather than one of them still waiting. Named by the branch that
    # has a failure path rather than by being the longest or the first -- rule 46, an
    # opening rule that names a position breaks the moment anything is added beside it.
    with_failure = [c for c in sites if ".catch(err" in c]
    assert len(with_failure) == 1, (
        f"{len(with_failure)} call sites handle a failed read; the guard cannot tell which"
    )
    boot = with_failure[0]
    assert boot.count("render()") >= 2 and boot.count("buildNav()") >= 2, (
        "only one of the two paths repaints both panes; the other leaves a pane waiting "
        "for something that has already failed"
    )


# --------------------------------------------------------------------------- #
# The comparison over the stack: `colorBy: 'change'`.
#
# The last of the temporal overlays. Colour carries one dimension at a time (design rule 4),
# so this one *takes the channel over* rather than tinting the changed nodes and leaving the
# rest on plate hue -- a red dot would otherwise mean either "deleted" or "the plate whose
# golden-angle hue landed on red". Every guard here was written from something that went
# wrong while building it.
# --------------------------------------------------------------------------- #


def _sim(hexv: str, kind: str) -> tuple[float, float, float]:
    """Viénot, Brettel & Mollon 1999, the same transform `simulate()` runs in the page."""
    dich = {"deuteranopia": ((1, 0, 0), (0.494207, 0, 1.24827), (0, 0, 1)),
            "protanopia":   ((0, 2.02344, -2.52581), (0, 1, 0), (0, 0, 1))}[kind]
    r2l = ((17.8824, 43.5161, 4.11935), (3.45565, 27.1554, 3.86714),
           (0.0299566, 0.184309, 1.46709))
    l2r = ((0.0809444479, -0.130504409, 0.116721066),
           (-0.0102485335, 0.0540193266, -0.113614708),
           (-0.000365296938, -0.00412161469, 0.693511405))

    def lin(c: int) -> float:
        x = c / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4

    def mul(m: tuple, v: tuple) -> tuple[float, float, float]:
        return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))

    v = tuple(lin(int(hexv[i:i + 2], 16)) * 255 for i in (1, 3, 5))
    out = mul(l2r, mul(dich, mul(r2l, v)))
    res = []
    for c in out:
        x = max(0.0, min(1.0, c / 255))
        y = (12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055) * 255
        res.append(float(max(0, min(255, round(y)))))
    return tuple(res)  # type: ignore[return-value]


def _lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        x = c / 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047)
    fy = f(0.2126 * r + 0.7152 * g + 0.0722 * b)
    fz = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _sep(a: str, b: str) -> float:
    """The **worst** of normal vision, deuteranopia and protanopia -- never an average."""
    def rgb(h: str) -> tuple[float, float, float]:
        return tuple(float(int(h[i:i + 2], 16)) for i in (1, 3, 5))  # type: ignore[return-value]

    def d(x: tuple[float, float, float], y: tuple[float, float, float]) -> float:
        la, lb = _lab(x), _lab(y)
        return math.dist(la, lb)
    return min(d(rgb(a), rgb(b)),
               d(_sim(a, "deuteranopia"), _sim(b, "deuteranopia")),
               d(_sim(a, "protanopia"), _sim(b, "protanopia")))


def _diff_triples() -> dict[str, tuple[str, str, str]]:
    """Every set and variant, as (gone, new, moved). Derived from the stylesheet."""
    css = _read("tokens.css")
    out: dict[str, tuple[str, str, str]] = {}
    base = _base_tokens(css)
    for variant, toks in base.items():
        out[f"default {variant}"] = (toks["--diff-gone"], toks["--diff-new"],
                                     toks["--diff-moved"])
    for name, blocks in _blocks(css).items():
        for sel, toks in blocks:
            if "--diff-moved" not in toks:
                continue
            # **Keyed by the selector, not by a guessed variant.** Written as
            # `"dark" if "dark" in sel else "light"` the `@media` block --
            # `:root[data-palette="muted"]:not([data-theme="light"])`, which contains no
            # "dark" at all -- was keyed as *light* and silently overwrote the real light
            # block. A mutation to the light colours then survived, because the guard was
            # measuring a different block under its name (rule 37).
            out[f"{name} {sel}"] = (toks["--diff-gone"], toks["--diff-new"],
                                    toks["--diff-moved"])
    return out


def test_every_colour_set_declares_the_third_difference() -> None:
    """A set that gains a difference and a set that misses one both fail here.

    The difference channel has three colours now -- arrived, went, and *behaves
    differently*, which is the half a text diff cannot state. A set that declares two of
    them leaves the third falling back to the base block, so a reader who chose `safe`
    would get its orange and blue with the default's violet: a set that is not the set.
    """
    css = _read("tokens.css")
    sets = _blocks(css)
    assert len(sets) >= 2, f"only {sorted(sets)} palette sets; this guard is blind"
    for _name, blocks in sets.items():
        for sel, toks in blocks:
            declared = {t for t in toks if t.startswith("--diff-")}
            assert declared >= {"--diff-gone", "--diff-new", "--diff-moved"}, (
                f"`{sel}` declares {sorted(declared)} — a set missing a difference colour "
                "falls back to the base block, so the reader gets half of two sets"
            )
    for variant, toks in _base_tokens(css).items():
        assert "--diff-moved" in toks, f"the base {variant} block has no --diff-moved"


def test_the_third_difference_is_never_the_least_separable_colour_shipped() -> None:
    """Rule 69: contrast says a colour can be read, separation says two can be told apart.

    The bar is **derived, not chosen**. A fixed one would fail colours already in use: the
    default set's own `gone`/`new` pair measures ΔE 9.5 on dark and 12.7 on light, which is
    rule 69's own conclusion that red and green cannot be rescued by tuning. So what is
    asserted is that the colour being *added* is never worse than the weakest thing already
    shipped — it may not become the new floor.
    """
    triples = _diff_triples()
    assert len(triples) >= 6, f"only {sorted(triples)}; this guard is blind"
    floor = min(_sep(g, n) for g, n, _ in triples.values())
    assert 5 < floor < 25, f"the shipped floor is ΔE {floor:.1f}; this guard is blind"
    for name, (gone, new, moved) in triples.items():
        for other, label in ((gone, "gone"), (new, "new")):
            got = _sep(moved, other)
            assert got >= floor, (
                f"{name}: `--diff-moved` is ΔE {got:.1f} from `--diff-{label}`, below the "
                f"ΔE {floor:.1f} floor already shipped — it would be the least separable "
                "pair in the product"
            )


def test_the_two_grounds_are_two_colours_and_both_can_be_seen() -> None:
    """"Nobody asked about this" and "we looked and found nothing" are opposite claims.

    More than half the stack is in the first state — it draws boundaries, constants,
    structures and artefacts, and the comparison's id-carrying bands are routines only. One
    tone for both would assert that the tool checked a boundary and found it unchanged,
    which it never did (design rule 1).

    Both must also clear **3:1 against the graph's own ground**, which is the bar the
    pointer's picker is clamped at. Below it a dot is not quiet, it is absent — and an
    invisible node is a silent filter.
    """
    css = _css_code(_read("tokens.css"))
    for label, block in (("light", css.split(":root {", 1)[1].split("\n}", 1)[0]),
                         ("dark", css.split(':root[data-theme="dark"] {', 1)[1]
                                     .split("\n}", 1)[0])):
        toks = dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{6})", block))
        for t in ("--graph-unchanged", "--graph-unclaimed", "--graph-ground", "--graph-dim"):
            assert t in toks, f"{label}: {t} is not declared"
        unch, uncl = toks["--graph-unchanged"], toks["--graph-unclaimed"]
        ground, dim = toks["--graph-ground"], toks["--graph-dim"]
        assert unch != uncl, (
            f"{label}: the two grounds are one colour, so 'not compared' and 'unchanged' "
            "are drawn as the same claim"
        )
        assert _sep(unch, uncl) >= 15, (
            f"{label}: the two grounds are ΔE {_sep(unch, uncl):.1f} apart — a reader "
            "cannot tell what was checked from what was not"
        )
        for t, v in (("unchanged", unch), ("unclaimed", uncl)):
            assert _ratio(v, ground) >= 3.0, (
                f"{label}: --graph-{t} is {_ratio(v, ground):.2f}:1 on the ground; below "
                "3:1 the node is invisible rather than quiet, which is a silent filter"
            )
        assert _sep(uncl, dim) >= 15, (
            f"{label}: 'not compared' is ΔE {_sep(uncl, dim):.1f} from `--graph-dim`, which "
            "means *not in your selection* — one grey saying two things"
        )


def test_the_stack_takes_its_tone_from_the_word_and_not_from_the_band() -> None:
    """A routine only the base has was *deleted* or *added* depending on the assumption.

    Written as `only_base: hex("--diff-gone")` the palette pinned a side to a colour, so
    flipping which version the reader takes to be newer swapped every word in the key and
    left the dots red — a picture saying "added" in the colour of gone, which rule 69's
    neighbour calls worse than no colour at all. Found by flipping it and reading the
    numbers back, not by any check.

    The palette is keyed by **tone** and the band-to-tone map comes from `diffWords()`.
    """
    js = _code(_read("shell.js"))
    palette = _fn(js, "cssPalette")
    block = palette[palette.index("change: {"):]
    block = block[:block.index("},")]
    for band in ("only_base", "only_compared"):
        assert band not in block, (
            f"`cssPalette` keys the stack's change palette by `{band}` — a side pinned to a "
            "colour cannot follow the word when the assumption flips"
        )
    assert "gone:" in block and "new:" in block and "moved:" in block, (
        "the change palette is no longer keyed by tone; this guard is blind"
    )
    tones = _fn(js, "changeTones")
    assert "diffWords()" in tones, (
        "the band-to-tone map is not derived from `diffWords()`, which is the one place the "
        "reader's assumption becomes a colour"
    )
    assert "w.base.tone" in tones and "w.compared.tone" in tones, (
        "a side's tone is written from something other than the word's own `.tone`"
    )


def test_flipping_the_assumption_repaints_the_stack_and_its_key() -> None:
    """The tone changes, and the nodes are inside a buffer as much as the code is in a cache.

    The handler already repainted the code for exactly this reason. It did not repaint the
    stack, so the key swapped its words while every dot kept the colour of the previous
    assumption — one control, two answers (rule 51), one layer out from where that lesson
    was learnt.
    """
    js = _code(_read("shell.js"))
    body = js[js.index('$$("[data-assumenewer]")'):]
    body = body[:body.index("}));")]
    for call in ("repaintCode()", "pushGraphChange()", "renderLegend()"):
        assert call in body, (
            f"flipping the assumption does not call `{call}`, so one surface keeps the "
            "colours of the assumption the reader has just left"
        )


def test_the_crossings_keep_their_plate_colour() -> None:
    """The decision the whole chunk rests on, and it is held by what `setOptions` omits.

    A crossing's colour walks from its source plate's hue to its target's (rule 23), because
    a line passing through plates it has nothing to do with cannot be read in one flat
    colour. That gradient is built in `buildSelectionGeometry`, and `setOptions` repaints
    the nodes without rebuilding it — which is what makes "the dots say what changed, the
    lines say which plate each end is on" free rather than a feature.
    """
    js = _code(_read("graph.js"))
    opts = js[js.index("setOptions(partial)"):]
    opts = opts[:opts.index("\n  },")]
    assert "paintNodes(" in opts, "setOptions no longer repaints the nodes; this is blind"

    # **The claim is about the guard around it, not about the call.** `setOptions` may
    # rebuild the selection geometry — it does, for a direction change — so what must hold
    # is that the *only* condition reaching it is that one. A first version asserted
    # `"diskColor(" in build`, which the mutation that replaced one of the two ends with a
    # flat colour walked straight past: the other end still said `diskColor`. A guard that
    # checks a name appears has not checked that anything happens (rule 37).
    # Split on the conditions themselves rather than matching a shape: every `if (` in this
    # function opens a block that runs to the next one, so the chunk a call sits in carries
    # its own guard. A regex over `if (…) {` looked more careful and matched nothing useful.
    chunks = opts.split("if (")
    assert len(chunks) >= 4, f"setOptions has {len(chunks) - 1} guards; this is blind"
    seen = 0
    for chunk in chunks[1:]:
        if "buildSelectionGeometry" not in chunk:
            continue
        seen += 1
        cond = chunk.split(") {", 1)[0]
        assert "direction" in cond, (
            f"`buildSelectionGeometry` runs under `{cond.strip()[:60]}` — a colorBy switch "
            "would recolour the crossings, and they are the one thing that still says "
            "which plate each end of a link is on"
        )
    assert seen == 1, (
        f"{seen} guarded paths reach `buildSelectionGeometry`; expected exactly the "
        "direction change"
    )

    build = _fn(js, "buildSelectionGeometry")
    ends = re.findall(r"const (c[ab]) = diskColor\(", build)
    assert set(ends) == {"ca", "cb"}, (
        f"the crossing gradient takes {sorted(set(ends))} from the plates — **both** ends "
        "must, or the line no longer says which end you are looking at. One end pinned to "
        "a flat colour is the defect this guard exists for"
    )


def test_the_change_key_counts_what_the_picture_draws() -> None:
    """A count must be named after the thing it measures (rule 32), and there are two
    populations here.

    `routineChangeCounts()` walks `ROUTINES` — 4,786 routines. The stack draws 10,015 nodes,
    more than half of which are not routines at all, and 5,855 shadows besides that are
    never drawn (rule 23). The key is about the picture, so it counts the picture.

    And it reads the payload **columnar**: `serve.py` transposes nodes into parallel arrays
    for the engine's typed buffers. Written as `for (const n of nodes)` this threw
    `nodes is not iterable` on the first paint and the key sat at "comparing…" for ever
    while the answer had long since arrived. Found by reading the console.
    """
    js = _code(_read("shell.js"))
    key = _fn(js, "changeKeyHtml")
    assert "routineChangeCounts" not in key, (
        "the key counts `ROUTINES`, which is not the population the stack draws"
    )
    assert "nodes.id" in key and "nodes.shadow" in key, (
        "the key does not read the payload's columnar arrays — `graphPayload.nodes` is an "
        "object of parallel arrays, not an array of nodes"
    )
    assert "shadow[i] === 1" in key or "shadow[i]" in key, (
        "shadows are counted, and they are never drawn"
    )
    assert "only_in_compared" in key, (
        "the routines only the compared version has are not stated — they have no node in "
        "this version, so no tally can find them and they must come from the band"
    )


def test_every_routine_the_stack_draws_carries_a_verdict() -> None:
    """An absent id means *unclaimed*, so a routine left out reads as never having been asked.

    `routineIndex()` holds only the ids that are in a band — 86 of them on Mensores — and
    `routineStatus` supplies `same` for a routine in none. Built by copying that index, the
    map left every unchanged routine absent and the key read *15 unchanged · 9,929 not
    compared* over a program with 4,700 unchanged routines. Both numbers wrong, nothing
    thrown.

    So the map is walked over the payload and the node's **kind** decides which ground it
    gets.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "changeByNodeId")
    assert "graphPayload" in fn, (
        "the map is not built from the payload, so it cannot know which nodes are routines"
    )
    assert 'kinds[i] !== "ROUTINE"' in fn or '"ROUTINE"' in fn, (
        "the map does not consult a node's kind, so it cannot tell a routine the comparison "
        "found nothing about from a boundary it was never asked about"
    )
    assert "routineStatus(" in fn, (
        "the map does not ask for a status per routine, so a routine in no band is absent "
        "— and an absent id is drawn as `unclaimed`, which is a different claim"
    )
    assert "shadow[i] === 1" in fn, "shadows are given a verdict, and they are never drawn"


def test_the_stack_asks_for_the_comparison_when_it_is_the_restored_mode() -> None:
    """`colorBy` is persisted, so a reader comes back into the mode — and nothing fetched.

    The mount hands the engine `changeByNodeId()`, which is `null` until something has
    asked. Nothing had, so the stack came up in change mode having requested nothing while
    the key said *comparing…* over a request that did not exist. Rule 55's companion: one
    truth about what is on, and whoever sets it does the work.
    """
    js = _code(_read("shell.js"))
    mount = _fn(js, "ensureGraph")
    assert "ensureGraphChange()" in mount, (
        "mounting the stack does not ask for the comparison, so a restored `change` mode "
        "colours nothing and says it is comparing"
    )
    assert "resolveColorBy()" in mount, (
        "a stored `change` on a program with one version is not resolved before the mode "
        "reaches the engine"
    )
    door = _fn(js, "ensureGraphChange")
    assert "ensureChanges()" in door, "the stack's door onto the comparison does not fetch"


def test_the_key_tells_not_asked_from_being_computed() -> None:
    """Three states, and collapsing any two states the wrong one (rule 35).

    Written as one `!CHANGES || CHANGES.loading` branch, the key said *comparing…* over a
    mode that had asked for nothing at all — for ever, and convincingly. The same trap
    `factLaneHtml` already carries a note about.
    """
    js = _code(_read("shell.js"))
    key = _fn(js, "changeKeyHtml")
    assert "if (!CHANGES) {" in key, (
        "the key does not distinguish 'nobody has asked' from 'it is being computed'"
    )
    assert "CHANGES.loading" in key, "the key has no computing state"
    assert key.index("if (!CHANGES) {") < key.index("CHANGES.loading"), (
        "the loading branch is tested first, so it swallows the not-asked case"
    )


def test_the_change_mode_is_offered_only_where_it_can_act() -> None:
    """A control whose only effect is to make the picture say nothing is a dead control.

    And the stored value is the other half: `colorBy` is persisted per program, so a reader
    who used the mode on a two-version program and opened a one-version one would arrive in
    a mode that can colour nothing. It falls back and **says so** — a silent fallback paints
    the stack one tone and reads as a broken picture (design rule 1, rule 66).
    """
    js = _code(_read("shell.js"))
    legend = _fn(js, "renderLegend")
    opt = legend[legend.index('id="gcolorby"'):]
    opt = opt[:opt.index("</select>")]
    assert '"change"' in opt, "the third option is gone; this guard is blind"
    assert "comparing()" in opt, (
        "the change option is drawn on a program with nothing to compare"
    )
    resolve = _fn(js, "resolveColorBy")
    assert "comparing()" in resolve and 'state.colorBy = "kind"' in resolve, (
        "a stored `change` with nothing to compare is not resolved back to a real mode"
    )
    assert "changeModeDropped = true" in resolve, "the fallback is silent"
    key = _fn(js, "changeKeyHtml")
    assert "changeModeDropped" in key, "nothing states that the mode was dropped"


def test_choosing_a_plate_colour_tells_the_selector_it_changed_the_mode() -> None:
    """One control, two claims, and the markup is the one that loses (rule 67).

    Picking a colour for a plate is a statement that colour should mean *plate*, so the
    branch forces `colorBy` to `disk` — and it returned without re-rendering, so the select
    went on displaying the mode the reader had just left. Harmless while there were two
    modes and `disk` was always the destination; with a third it is a control disagreeing
    with the state that owns it.
    """
    js = _code(_read("shell.js"))
    # **The second `.sw` test, not the first.** `js.index` found the row-click handler's
    # own guard (`ev.target.classList.contains("sw")`, which ignores a click on the
    # swatch) and asserted against a branch that was never the subject. A guard anchored
    # on the wrong span has not checked what it names (rule 37).
    branch = js[js.index('state.diskColors[row.dataset.disk] = t.value;'):]
    branch = branch[:branch.index("return;")]
    assert 'state.colorBy = "disk"' in branch, "the branch no longer forces the mode"
    assert "renderLegend()" in branch, (
        "forcing the mode does not re-render the control that displays it, so the selector "
        "keeps naming a mode the stack is no longer in"
    )
    assert "nodeChange: null" in branch, (
        "leaving change mode does not drop the map, so the engine holds data it no longer "
        "reads"
    )


def test_edited_and_unchanged_reach_one_tone_and_the_key_says_so() -> None:
    """The fold is a decision, and design rule 1 says a fold that is not stated is a filter.

    "The body changed and nothing it does did" is internal computation, which `CLAUDE.md`'s
    opening says this tool exists not to report — so on the stack it is drawn as unchanged.
    The table still lists it, and the key names the number that was folded in.
    """
    js = _code(_read("shell.js"))
    tones = _fn(js, "changeTones")
    assert 'edited: "quiet"' in tones and 'same: "quiet"' in tones, (
        "edited and unchanged no longer share a tone; if that is deliberate the key's "
        "sentence about the fold is now a lie"
    )
    key = _fn(js, "changeKeyHtml")
    assert "tally.edited + tally.same" in key, (
        "the unchanged count does not include the edited ones, so the folded rows are drawn "
        "in a colour no number accounts for"
    )
    assert "edited without" in key and "tally.edited.toLocaleString()" in key, (
        "the key does not say how many were folded into unchanged — an unstated fold is a "
        "silent filter"
    )


# --------------------------------------------------------------------------- #
# One history.
#
# `state.trail` was the visible record and `selHistory` the invisible one, and the split was
# never designed -- it accumulated. `onGraphSelect` recorded to the second and never the
# first, so the button labelled **Back** could not reverse a click in the stack, which is
# almost the only thing a reader does while exploring it. Reported at the keyboard as "I have
# to use Back too often, and it doesn't always do what I expect."
# --------------------------------------------------------------------------- #


def test_there_is_one_history() -> None:
    """Two stores is the defect, so the check is that the second one is gone.

    Not "the merge happened" — that is unfalsifiable — but that nothing writes a step
    anywhere except the one list, found by looking for pushes rather than by keeping a list
    of the places that used to have one.
    """
    js = _code(_read("shell.js"))
    assert "selHistory" not in js, (
        "a second selection history is back. Two stores means two answers to 'where have I "
        "been', and the visible control ends up blind to whichever acts the other one owns"
    )
    pushes = set(re.findall(r"(\w+(?:\.\w+)*)\.push\(step\)", js))
    assert pushes == {"state.trail"}, (
        f"steps are pushed onto {sorted(pushes) or 'nothing'} — there must be exactly one "
        "history, and it is `state.trail`"
    )
    # **A word boundary, not a substring.** `"let trailAt" in js` is also true of
    # `let trailAtX`, so renaming the cursor away walked straight past this (rule 37).
    assert re.search(r"\blet trailAt\b", js), (
        "the history has no cursor, so it can only be popped"
    )


def test_a_click_in_the_picture_is_a_step() -> None:
    """The defect this whole change is from, asserted at its source.

    `onGraphSelect` recorded to the selection history and never to the trail, so the visible
    Back button had no record of the commonest act there is. It goes through the one
    recorder now, and the step takes the name of what it landed on.
    """
    js = _code(_read("shell.js"))
    body = _fn(js, "onGraphSelect")
    assert "recordSelection(" in body, (
        "clicking a node in the stack records no step, so Back cannot reverse it — which is "
        "the report this change came from"
    )
    rec = _fn(js, "recordSelection")
    assert "labelFor(state.selected)" in rec, (
        "a step made by clicking takes no name from what it landed on, so the trail would "
        "read as a row of identical entries"
    )
    # A cleared selection is the step most worth having, and it must say what it is: the
    # fallback used to be `state.view`, so emptying the picture recorded a step called
    # "graph", which reads as a mode change.
    assert '"nothing selected"' in rec, (
        "a step recorded with nothing selected is not named, so the one step a reader most "
        "wants back is labelled after the view it happened in"
    )


def test_back_and_undo_are_the_same_thing() -> None:
    """Three doors onto one history: the trail's Back, ⌘Z, and the HUD's button.

    They were two mechanisms with different contents, and the reader could not tell which
    one a given control moved.
    """
    js = _code(_read("shell.js"))
    back = js.split("[data-trailback]", 1)[1][:200]
    assert "undoSelection" in back, "the trail's Back is not the undo everything else uses"
    fwd = js.split("[data-trailfwd]", 1)[1][:200]
    assert "redoSelection" in fwd, "the trail's Forward is not the redo everything else uses"
    keys = js[js.index('e.key.toLowerCase() === "z"'):][:300]
    assert "undoSelection()" in keys and "redoSelection()" in keys, (
        "the keyboard does not reach the same two functions"
    )
    for act in ("undo", "redo"):
        assert re.search(rf"^  {act}: \(\) => {act}Selection\(\)", js, re.M), (
            f"the HUD's {act} button does not reach {act}Selection"
        )


def test_looking_backwards_destroys_nothing() -> None:
    """Back popped and a step click truncated, so looking back destroyed the journey.

    A history has a cursor. The only thing that drops the forward branch is a **new** step,
    which is the recorder's own rule — going back and changing your mind is free, and that
    is the whole point of keeping the record.
    """
    js = _code(_read("shell.js"))
    for fn in ("undoSelection", "redoSelection"):
        body = _fn(js, fn)
        assert ".pop()" not in body and ".splice(" not in body, (
            f"`{fn}` shortens the history rather than moving the cursor"
        )
    step = js.split("[data-trail]", 1)[1][:400]
    assert "state.trail = state.trail.slice" not in step, (
        "clicking a step truncates the trail to it, so the forward branch is destroyed by "
        "looking at where you have been"
    )
    assert "trailAt = i" in step, "clicking a step does not move the cursor"
    # The one place that may drop it, and only on a new step.
    rec = _fn(js, "recordSelection")
    assert "state.trail = state.trail.slice(0, trailAt + 1)" in rec, (
        "a new step does not drop the forward branch, so redo would walk into a journey "
        "that no longer happened"
    )


def test_two_steps_with_one_name_are_two_steps() -> None:
    """`pushTrail` deduplicated on the *label*, and that is wrong once every click records.

    Two routines called `<module>` are two subjects with one name, and dropping the second
    as a repeat would silently lose a step Back is expected to reach. A label is not an
    identity (rule 30); `sameSelection` is the test the selection history already used.
    """
    js = _code(_read("shell.js"))
    rec = _fn(js, "recordSelection")
    assert "sameSelection(" in rec, (
        "the recorder no longer compares subjects, so two different routines sharing a name "
        "collapse into one step"
    )
    assert not re.search(r"\.label\s*===\s*", rec), (
        "the recorder deduplicates on the label — a name is not an identity, and two "
        "`<module>` routines are two steps"
    )
    assert "at.view === step.view" in rec, (
        "the view is not part of the comparison, so moving between the centre modes over "
        "one selection records nothing"
    )


def test_the_trail_bar_bounds_itself_and_says_what_it_left_out() -> None:
    """`trailCap` bounds the **bar**; `TRAIL_CAP` bounds the history.

    They were one number applied to the history, and merging made that fatal: every graph
    click is a step now, so a cap of twelve would flush the step the reader detoured *from*
    — destroying the one thing design rule 15 says the trail exists for.

    Both edges of the window are stated. Only what fell off the back was, at first, so
    stepping back through a long trail silently hid everything in front of the cursor
    (design rule 1: a filtered view says what it removed, and a window has two sides).
    """
    js = _code(_read("shell.js"))
    assert "const TRAIL_CAP" in js, "the history has no cap of its own"
    rec = _fn(js, "recordSelection")
    assert "TRAIL_CAP" in rec and "state.trailCap" not in rec, (
        "the recorder bounds the history by the number that governs the bar, so narrowing "
        "the bar would throw away the steps Back reaches"
    )
    cap = js.split("[data-trailcap]", 1)[1][:400]
    assert "splice" not in cap and "state.trail =" not in cap, (
        "changing how many steps are shown prunes the history — it is a view setting now"
    )
    bar = _fn(js, "trailBar")
    assert "state.trailCap" in bar, "the bar does not bound itself"
    # **What it renders, not what it names.** Asserting the words appear passed a bar with
    # the whole ahead-counter deleted, because `const ahead = …` still declared one — a
    # guard that checks a name appears has not checked that anything happens (rule 37).
    for side in ("behind", "ahead"):
        assert re.search(rf"\$\{{{side}\}} {side}</span>", bar), (
            f"the bar computes `{side}` and never draws it, so the window silently hides "
            "steps Back and Forward can still reach"
        )


def test_the_trail_steps_cannot_paint_over_the_controls_beside_them() -> None:
    """`min-width: 0` with no `overflow` lets a flex row's children spill outside their box.

    Six steps in a 509px lane painted straight over the "+7 ahead" counter and the Back
    button. **Every measurement said it was fine** — `getBoundingClientRect` reports the
    layout box, not the ink, and every child came back inside the bar and marked visible.
    Found by zooming in on it: what the DOM says and what the reader sees are different
    questions (rule 48's family).
    """
    css = _css_code(_read("tokens.css"))
    lane = re.search(r"\.trail \{([^}]*)\}", css)
    assert lane, ".trail no longer declares its own rule; this guard is blind"
    body = lane.group(1)
    assert "min-width: 0" in body, "the lane no longer shrinks, so it pushes the buttons off"
    assert "overflow-x" in body, (
        "the lane shrinks below its content and does not clip it, so the steps paint over "
        "the counter and the buttons beside them"
    )
    step = re.search(r"\.trailstep \{([^}]*)\}", css)
    assert step and "text-overflow: ellipsis" in step.group(1), (
        "a long qualified name is not ellipsised, so one step can fill the whole lane"
    )
    js = _code(_read("shell.js"))
    assert '$$(".trailstep.here")' in js, (
        "the cursor is scrolled into its lane with the singular selector — the bar is "
        "rendered twice, and that is exactly how its controls were once wired to one of them"
    )


# --------------------------------------------------------------------------- #
# The stack's second altitude.
#
# Two levels of one program: `routine` is every thing it declares, `module` folds each file
# into one node and each boundary kind into one. It is a second way to look at the same
# facts and not a filter, so nothing is dropped and every folded node says what it stands
# for. Every guard here was written from something that went wrong while building it.
# --------------------------------------------------------------------------- #


def test_a_payload_swap_rebuilds_everything_the_payload_decides() -> None:
    """The engine could `mount` and had no way to replace a payload, and `mount` returns
    early once mounted. A second setter doing nine tenths of what the first does is rule 68
    waiting to happen, so the payload-adoption half is one function and both doors call it.

    The tenth it would forget is the id index -- a lookup that answers confidently about the
    altitude the reader has just left.
    """
    engine = _code(_read("graph.js"))
    adopt = _fn(engine, "adoptPayload")
    for step in ("prepare(raw)", "diskPlates(raw)", "g.idIndex = null",
                 "applyLayout", "recomputeMembers", "buildSelectionGeometry",
                 "paintNodes", "fitView"):
        assert step in adopt, f"`adoptPayload` no longer does `{step}`"
    for door in ("mount", "setPayload"):
        assert "adoptPayload(" in _fn(engine, door), (
            f"`{door}` takes a payload without going through `adoptPayload`"
        )
    # A pick is an index into *one* payload, so the same number means a different routine in
    # the next one. `setPayload` must drop them; the shell re-resolves from ids.
    assert "adoptPayload(raw, [])" in _fn(engine, "setPayload"), (
        "a level switch carries the old payload's indices into the new one, so the "
        "selection lands on whatever happens to sit at those positions"
    )


def test_the_console_diagnostics_follow_the_payload() -> None:
    """Design rule 21 puts diagnostics where a developer can reach them, because "drawn
    off-screen" and "not drawn" are indistinguishable by looking.

    They were written once in `mount`, so after a change of level `window.__d` went on
    describing 15,870 routine-level rows while the engine drew 2,069 module-level ones. A
    diagnostic that lies is worse than none: it cost half an hour chasing a defect that was
    not there.
    """
    engine = _code(_read("graph.js"))
    assert "window.__d = g.prepared;" in _fn(engine, "adoptPayload"), (
        "`window.__d` is not refreshed when the payload changes, so it describes the "
        "altitude the reader has left"
    )
    # **One writer.** Asserted over the whole engine rather than over `mount`'s span,
    # because `mount` is the last function in the file and `_fn` therefore hands back
    # everything after it -- and because `window.__deck` contains `window.__d`, which is the
    # substring trap that made the first version of this line fail on code that was right.
    assert engine.count("window.__d = ") == 1, (
        f"`window.__d` is assigned {engine.count('window.__d = ')} times; two places writing "
        "one diagnostic means one of them goes stale, which is the defect this was written "
        "from"
    )


def test_the_shell_never_pushes_a_plate_order_the_engine_just_resolved() -> None:
    """**The defect that ate the whole feature, and it was silent in the page.**

    `adoptPayload` works out whether a saved plate order still describes this payload. The
    switch then pushed `plateOrder()` back in -- one truth in two places (rule 51) -- and on
    a fresh session there is no saved order at all, so it handed `setOptions` a `null` and
    `applyLayout` threw on it. Every switch, from the first one.

    Everything after the throw was skipped, so the selection never travelled and the note
    that would have said so was never written. The page looked like a page that works. The
    console had said so from the first attempt.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "setGraphDetail")
    assert "Graph.setPayload(payload)" in fn, "the switch no longer hands over the payload"
    assert "diskOrder: plateOrder()" not in fn, (
        "the switch pushes the shell's plate order back into an engine that has just "
        "resolved one -- `null` on a fresh session, and `applyLayout` throws on it"
    )
    assert "setPlateOrder(Graph.diskOrder())" in fn, (
        "the shell does not record the order the engine resolved, so a switch loses it"
    )


def test_the_two_per_level_settings_go_through_one_door() -> None:
    """`diskOrder` and `minDisk` are per level, and written inline at each call site that
    would be six places to keep one shape in step (rule 51 with six chances to get it
    wrong)."""
    js = _code(_read("shell.js"))
    for fn in ("plateOrder", "setPlateOrder", "minDiskNow", "setMinDiskNow"):
        assert f"function {fn}(" in js, f"`{fn}` is gone; the accessors have been inlined"
    # Nothing outside the accessors indexes the maps by hand.
    body = js.replace(_fn(js, "plateOrder"), "").replace(_fn(js, "setPlateOrder"), "")
    body = body.replace(_fn(js, "minDiskNow"), "").replace(_fn(js, "setMinDiskNow"), "")
    assert "state.diskOrder[" not in body and "state.minDisk[" not in body, (
        "a caller indexes a per-level setting directly instead of going through the "
        "accessor, which is how the two levels start disagreeing about one arrangement"
    )


def test_the_detail_control_states_what_the_altitude_costs() -> None:
    """Design rule 1: no filter is ever silent, and a picture that got seventeen times
    smaller without saying so reads as one. So the row states what is drawn, what it stands
    for, and what the `<small>` threshold merged -- because a shorter stack and a smaller
    program are indistinguishable by looking."""
    js = _code(_read("shell.js"))
    fn = _fn(js, "detailControlHtml")
    assert 'id="glevel"' in fn and 'id="gmindisk"' in fn, "the two controls are not both here"
    # **The exact assignments, not the substring.** `st.disks_merged` is a substring of
    # `st.disks_merged_nodes`, so a version that stopped reading the first and kept the
    # second passed a containment check while the row said "no plate merged" over 23 of
    # them. The same trap as `window.__d` inside `window.__deck`, one guard apart.
    for claim in ("Number(st.nodes || 0)", "Number(st.folded_from || 0)",
                  "Number(st.disks_merged || 0)", "Number(st.disks_merged_nodes || 0)",
                  "Number(st.min_disk || 1)"):
        assert claim in fn, f"the row no longer reads `{claim}` from the payload"
    assert "levelNote" in fn, (
        "the row does not say what the last switch did to the selection, so a reader whose "
        "routine became the file holding it has been moved without being told"
    )
    # And it is rendered, or it is a function nobody calls (rule 35's family).
    assert "detailControlHtml()" in _fn(js, "renderLegend"), (
        "the legend does not render the detail control"
    )


def test_the_level_control_and_the_threshold_are_wired_and_the_slider_waits() -> None:
    """`input` is every value a dragged slider passes through -- twenty requests for one
    decision, which is rule 45's shape in a control. The threshold commits on `change`;
    the number beside it follows the thumb immediately, because a control that shows
    nothing until it is released reads as one that is not working."""
    js = _code(_read("shell.js"))
    assert 'if (t.id === "glevel") { setGraphDetail({ level: t.value }); return; }' in js, (
        "the altitude control is not wired to the one function that changes altitude"
    )
    assert 'ev.target.id === "gmindisk"' in js, "the threshold never commits"
    # The commit is in the `change` listener and the live readout in the `input` one.
    after_input = js.split('mount.addEventListener("input"', 1)[1]
    live, _, committed = after_input.partition('mount.addEventListener("change"')
    assert 'setGraphDetail({ minDisk:' in committed, (
        "the threshold asks the server from the `input` handler, so a dragged slider "
        "fetches every value it passes through"
    )
    assert 'setGraphDetail({ minDisk:' not in live
    assert 't.id === "gmindisk"' in live, (
        "the number beside the slider does not follow the thumb, so the control looks dead "
        "until it is released"
    )


def test_a_selection_travels_between_altitudes_in_id_space() -> None:
    """An index means a different routine in the other payload, and an id does not survive
    either: `mod:mensores.cli.audit` is not a routine and no routine id is a module.

    So the translation is explicit and it reads the **routine-level** payload, the only one
    carrying a node's module and the plate it came from. `home ?? disk` is the plate
    *before* small ones were merged, which is what the server folds on -- so the two cannot
    drift apart over a threshold the reader moved.
    """
    js = _code(_read("shell.js"))
    fold = _fn(js, "foldedIdFor")
    assert "det.module" in fold and "mod:" in fold, "a module node is no longer addressed"
    assert "outside:" in fold, "an external node is no longer addressed"
    assert "det.home ||" in fold, (
        "the fold reads the drawn plate rather than the plate before `<small>` merged it, "
        "so moving the threshold silently re-homes what the reader had selected"
    )
    move = _fn(js, "translateIds")
    assert "shadow" in move, (
        "the downward translation admits shadows, which are never drawn (rule 23)"
    )
    fn = _fn(js, "setGraphDetail")
    assert "state.wanted =" in fn and "applyWanted()" in fn, (
        "the switch does not re-resolve the selection, so it is dropped with the payload"
    )
    # **Assigned once as a reset and then written**, not merely mentioned. Asserted this way
    # because a mutation that cleared it again after the branches left `levelNote =` in the
    # source and the note off the screen -- rule 37 in the shape it keeps taking: check that
    # the guard catches, not that it mentions.
    assert fn.count('levelNote = "";') == 1, (
        f"`levelNote` is cleared {fn.count(chr(39) + chr(39))} times in the switch; a second "
        "reset after the translation is a note that is written and never seen"
    )
    for phrase in ("nothing that was selected exists at this level",
                   "selected \u2192 the", "holding them"):
        assert phrase in fn, f"the switch cannot say `{phrase}`"
    assert fn.index('levelNote = "";') < fn.index("nothing that was selected"), (
        "the reset runs after the note is written, so the reader is never told"
    )


def test_a_module_takes_the_band_of_what_it_holds_with_same_as_the_ground() -> None:
    """Written the other way -- any two distinct bands make it mixed -- every changed file
    on Mensores reads `mixed` and the colour says nothing at all. With `same` as the ground,
    14 modules carry the whole comparison and 7 of them are genuinely mixed.

    Measured before it was built, which is why the rule is this way round.
    """
    js = _code(_read("shell.js"))
    fn = _fn(js, "changeByNodeId")
    assert 'graphPayload.level === "module"' in fn, "the fold no longer knows the altitude"
    assert 'b !== "same"' in fn, (
        "`same` competes with the other bands instead of being the ground, so a file with "
        "63 unchanged routines and one arrival reads as mixed"
    )
    assert '"mixed"' in fn, "there is no mixed band"
    assert 'st === "edited" ? "same" : st' in fn, (
        "`edited` is not folded into `same`, so a file edited without changing what it does "
        "reads as mixed against its own unchanged neighbours -- two bands, one tone"
    )
    # Three states, and the third is why it is `null`: "nobody has asked for the routine
    # list yet" is not "no module changed" (rule 35).
    assert "if (!ROUTINES.length) return null;" in fn, (
        "an empty routine list yields an empty map, which paints every module as *not "
        "compared*, confidently and for ever"
    )
    # And whoever needs it does the work of loading it (rule 55's companion).
    assert "loadRoutines()" in _fn(js, "ensureGraphChange"), (
        "the module level's fold needs the routine list and nothing asks for it"
    )


def test_mixed_is_not_directional_and_has_its_own_colour() -> None:
    """"More than one thing happened in this file" is the same claim whichever version the
    reader takes to be newer, so flipping the assumption must not move it -- unlike every
    band above it, whose tone comes from `diffWords()`.

    The colour is measured rather than picked. It sits with `--graph-unchanged` and
    `--graph-unclaimed` rather than in the colour sets, because a set covers the
    *directions* of difference and "more than one direction" is not one of them.
    """
    js = _code(_read("shell.js"))
    tones = _fn(js, "changeTones")
    assert 'mixed: "mixed"' in tones, "the mixed band reaches no tone"
    assert "w.base.tone" in tones and "w.compared.tone" in tones
    assert "mixed: w." not in tones, (
        "`mixed` is taken from `diffWords()`, so flipping which version is newer moves a "
        "claim that does not depend on it"
    )
    css = _css_code(_read("tokens.css"))
    assert css.count("--graph-mixed:") == 3, (
        f"--graph-mixed is declared {css.count('--graph-mixed:')} times, not once per theme "
        "block; a colour with no dark value borrows the light one"
    )
    assert ".legkey-dot.tone-mixed" in css, "the key's swatch has no colour"
    # It must reach the stack, through the same `hex(...)` read as every other tone -- the
    # shape the colour-set guard greps for.
    assert 'mixed:     hex("--graph-mixed")' in js, (
        "the mixed tone never reaches the engine, so seven nodes draw as `unclaimed`"
    )
    # And the engine carries its own fallback beside the other five, or a palette that has
    # not been pushed yet draws the band as nothing at all.
    engine = _code(_read("graph.js"))
    fallback = engine.split("change: {", 1)[1].split("},", 1)[0]
    assert "mixed:" in fallback, "the engine has no fallback colour for the mixed tone"


def test_the_change_key_names_what_it_counts_at_each_altitude() -> None:
    """Rule 32: the number must be named after the thing it measures. At module level the
    dots are files, so "53 arrived" would be a routine count printed over 4 nodes."""
    js = _code(_read("shell.js"))
    fn = _fn(js, "changeKeyHtml")
    assert 'graphPayload && graphPayload.level) === "module"' in fn, (
        "the key does not know which altitude it is describing"
    )
    assert 'at === "module"' in fn, "the key says the same words at both altitudes"
    assert "tally.mixed" in fn, "the mixed band is counted nowhere"
    # Walked from the drawn nodes, never read off the band lengths (rule 32).
    assert "shadow[i] === 1" in fn, (
        "shadows are counted, and they are never drawn -- so the key states a number no "
        "scrolling could find"
    )


def test_the_settings_version_moved_with_the_shape_that_changed() -> None:
    """`level` and `minDisk` are new keys and would merge safely on their own. `diskOrder`
    is the reason for the bump: it was one array and is now one per level, and a v3 blob
    merged into that shape hands `mount` a list of plate ids where it expects a map."""
    st = _read("settings.js")
    assert "const SETTINGS_VERSION = 4;" in st, (
        "the version did not move with the shape of `diskOrder`"
    )
    code = _code(st)
    assert "diskOrder: { routine: null, module: null }" in code
    assert "minDisk: { routine: null, module: null }" in code, (
        "the threshold is not per level, so a value chosen for one altitude is applied to "
        "the other, where it means something else"
    )
    js = _code(_read("shell.js"))
    persisted = js.split("const PERSISTED = [", 1)[1].split("];", 1)[0]
    for key in ("level", "minDisk"):
        assert f'"{key}"' in persisted, f"`{key}` is never written to storage"
