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

PER_PROGRAM = ["ENTRYPOINTS", "BOUNDARIES", "PKGS", "TABLES", "ROUTINES",
               "ANOMALIES", "TERMS", "CONVENTIONS", "MANIFEST", "CURIOSITIES",
               "PROVENANCE"]


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
