"""Every control the page draws must be listened for by something.

Design rule 16, asserted at build time rather than only at runtime. Eight of eleven
left-hand menu items once rendered perfectly and silently showed the graph, because a
patch to add the missing branch matched nothing and reported success. The page carries a
`selfCheck()` that catches it in a browser; this catches it in `pytest`, which is where a
regression should be caught -- a self-check nobody opens the page to see is a self-check
that has already failed.

The lists are *derived from the files*, never written down here. A hand-kept list agrees
with a wrong implementation, which is the failure it was supposed to detect.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web" / "static"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _attrs(html: str, attr: str) -> set[str]:
    return set(re.findall(rf'{attr}="([^"]+)"', html))


def _action_table() -> set[str]:
    """The keys of `ACTIONS` in app.js.

    Read from the object literal rather than by executing anything: the point is to
    compare two files, and a parser that agreed with the code by running it would only
    prove the code agrees with itself.
    """
    js = _read("app.js")
    body = js.split("const ACTIONS = {", 1)[1].split("\n};", 1)[0]
    keys = set(re.findall(r"^\s{2}'?([a-zA-Z][\w-]*)'?:", body, re.M))
    assert keys, "found no actions -- the shape of ACTIONS changed and this test is blind"
    return keys


def _modes() -> set[str]:
    js = _read("app.js")
    line = re.search(r"const MODES = \[([^\]]+)\]", js)
    assert line, "MODES is no longer a literal array; this test cannot see it"
    return set(re.findall(r"'([^']+)'", line.group(1)))


def _panel_defaults() -> set[str]:
    settings = _read("settings.js")
    block = re.search(r"panels: \{([^}]+)\}", settings)
    assert block, "panels defaults are no longer a literal object"
    return set(re.findall(r"(\w+)\s*:", block.group(1)))


# ------------------------------------------------------------------ the checks --- #

def test_every_action_in_the_markup_has_a_handler() -> None:
    """The defect rule 16 is named for: a control that renders and does nothing."""
    drawn = _attrs(_read("index.html"), "data-act")
    handled = _action_table()
    assert drawn, "the page draws no actions at all -- something is very wrong"
    assert drawn <= handled, (
        f"controls wired to nothing: {sorted(drawn - handled)}. "
        f"A control that renders but does nothing looks exactly like one that works."
    )


def test_every_handler_is_reachable_from_the_markup() -> None:
    """The other direction, which is a smaller failure but still a lie.

    A handler no control can reach is dead code that reads as a working feature to anyone
    scanning the table for what the page can do.
    """
    drawn = _attrs(_read("index.html"), "data-act")
    handled = _action_table()
    assert handled <= drawn, f"actions no control reaches: {sorted(handled - drawn)}"


def test_every_mode_button_names_a_real_mode() -> None:
    drawn = _attrs(_read("index.html"), "data-mode")
    assert drawn == _modes(), (
        f"mode buttons and MODES disagree: markup {sorted(drawn)}, code {sorted(_modes())}"
    )


def test_every_mode_has_a_view_to_show() -> None:
    """A mode with no view of its own would fall back to whichever view is not hidden.

    That is the original defect exactly: eight menu items that showed the graph. Each
    mode owns a `data-view`, so an unbuilt one shows its own "not built" panel.
    """
    html = _read("index.html")
    assert _attrs(html, "data-view") == _modes()


def test_every_collapsible_panel_has_somewhere_to_remember_it() -> None:
    """A panel whose state is not in the defaults is a panel that forgets on reload."""
    drawn = _attrs(_read("index.html"), "data-panel")
    known = _panel_defaults()
    assert drawn <= known, f"panels with no stored default: {sorted(drawn - known)}"


def test_the_page_loads_every_script_it_depends_on() -> None:
    """A missing script is a blank page, and a blank page must never be a mystery."""
    html = _read("index.html")
    for name in ("settings.js", "shading.js", "inspector.js", "app.js"):
        assert f"/static/{name}" in html, f"{name} is never loaded"


def test_dimensions_are_stored_in_rem() -> None:
    """Design rule 3: one root scale must resize the whole surface together.

    A width in pixels is a width the multiplier cannot reach, and the layout then breaks
    for everyone who is not its author. Hairlines are the deliberate exception -- a 1px
    border is a device pixel by intent -- along with the single root font size that the
    multiplier acts *on*.
    """
    css = _read("style.css")
    offenders = []
    for line in css.splitlines():
        bare = line.split("/*", 1)[0]
        for hit in re.findall(r"(-?\d*\.?\d+)px", bare):
            if abs(float(hit)) <= 1:
                continue                      # hairline borders and outlines
            if "font-size" in bare and "html" in css[:css.index(line) + len(line)][-200:]:
                continue                      # the root scale itself
            offenders.append(line.strip())
    # The root scale is the one allowed pixel value, and it is named in a comment.
    offenders = [o for o in offenders if "the root scale" not in o]
    assert not offenders, f"pixel dimensions that the scale multiplier cannot reach: {offenders}"


def test_hidden_actually_hides() -> None:
    """`[hidden]` comes from the user-agent stylesheet, and any author `display` rule
    beats it — specificity never enters into it, author styles simply win.

    `.unbuilt { display: grid }` therefore cancelled `hidden` on the table and document
    views, and since all three views are absolutely positioned over one another, the last
    in the document painted on top of the canvas. The graph rendered at 60 fps underneath
    a panel saying "not built yet", and the mode buttons flipped every attribute
    correctly while nothing on screen changed.

    Asserted here because the override is one line that any later `display` rule can
    silently re-break, and the symptom is invisible to every check that reads the DOM.
    """
    css = _read("style.css")
    assert "[hidden] { display: none !important; }" in css, (
        "the [hidden] override is gone — any author `display` rule will now cancel the "
        "hidden attribute and views will stack on top of each other"
    )
