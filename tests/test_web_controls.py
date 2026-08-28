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
    """
    exempt = re.compile(r"--shadow|box-shadow|outline|border-radius|"
                        r"border(-\w+)?:\s*[\d.]+px\s+(solid|dashed|dotted)|font-size:\s*calc")
    offenders = []
    for line in _read("tokens.css").splitlines():
        bare = line.split("/*", 1)[0]
        if exempt.search(bare):
            continue
        for hit in re.findall(r"(-?\d*\.?\d+)px", bare):
            if abs(float(hit)) > 1:
                offenders.append(line.strip())
    assert not offenders, f"layout dimensions the scale multiplier cannot reach: {offenders}"
