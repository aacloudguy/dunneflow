"""Inference is withdrawn, and withdrawn is not the same as deleted.

**Tom, 2026-09-09:** *"The infer parts can be disabled as features and the links can be
removed (but the code left in place and marked for use in the next version). Be sure to
remove all mentions of the feature from any other controls or documentation, but don't
destroy any code that may already exist for it."*

So there are **two** things to hold, and each fails silently without the other:

* nothing on screen may offer it — it was a control that renders and is wired to nothing
  (design rule 16), and worse than that, `data-airun="go"` set `state.aiDone = true` and
  reported *"Pass complete"* having done nothing at all;
* nothing may have been thrown away — the next version starts from what is here, and a
  withdrawal that quietly became a deletion is not recoverable from a constant.

`shell.js` carries a `selfCheck()` that catches the first at runtime, which is the right
thing in a browser and the wrong thing to rely on: a self-check nobody opens the page to
see has already failed. These run in `pytest`, over the source.

What is deliberately **not** checked here, because none of it is the feature: *edge
confidence* `INFERRED` and the *hide inferred edges* toggle (design rule 5), the *version
tier* `INFERRED`, `Provenance`'s four tiers, and *About this map*'s two rows — those say
no fact was inferred and no model read it, which this withdrawal makes more true.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_web_controls import _code

STATIC = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web" / "static"
ROOT = Path(__file__).resolve().parents[1]

# How far above a marker a guard may sit. The reachability points are one-line entries
# inside a spread or a template branch, so the constant is within a few lines of each;
# a bound is what makes this a check rather than a search of the whole file.
GUARD_WINDOW = 8

# Every way the running page could reach the withdrawn feature, and the file it is in.
# Named one by one rather than found by a pattern: a pattern would silently stop matching
# the day someone writes a seventh door in a shape it does not know.
DOORS = [
    ('nav: "inference"', "the navigator row"),
    ("inference: () => { state.view", "the route"),
    ('inference: [{ label: "inference"', "the breadcrumb"),
    ('state.view === "inference"', "the dispatch"),
    ('data-goto="inference"', "the Settings link"),
    ('inference: "the inference settings"', "the off-mode label"),
]

# The feature itself. Present, whole, and reachable by flipping one constant.
KEPT = [
    ("function viewInference()", "the page"),
    ("const AI_OPS = [", "the operations and their costs"),
    ("const POSTURES = [", "the egress postures"),
    ("function posture()", "which posture is in force"),
    ("function chosenOps()", "what has been selected"),
    ('data-airun="go"', "the run button"),
    ("state.aiOps[cb.dataset.aiop]", "the operation checkboxes"),
    ("state.egress = b.dataset.egress", "the posture buttons"),
]


def _read(name: str) -> str:
    """The file with its comment *lines* blanked, which is not optional here.

    The first run of this guard failed on the block comment above `INFERENCE_SHIPPED` --
    the prose explaining the withdrawal names `data-goto="inference"`, so the check read
    its own explanation as a live door. That is rule 43 arriving through the one place
    this project has already paid for it five times, which is why `_code` exists and why
    it is imported rather than written again here (rule 51): a second stripper is a second
    answer, and this one would have been the naive version that ate the template literals.

    Line count is preserved, so the window below still measures lines of code.
    """
    return _code((STATIC / name).read_text(encoding="utf-8"))


def test_the_feature_is_off_and_one_constant_says_so() -> None:
    """One place decides (rule 51). Two would be two answers waiting to disagree."""
    shell = _read("shell.js")
    assert shell.count("const INFERENCE_SHIPPED") == 1, \
        "a second declaration is a second answer"
    assert re.search(r"const INFERENCE_SHIPPED = false;", shell), \
        "the feature is withdrawn; this constant is what says so"


@pytest.mark.parametrize(("marker", "what"), DOORS, ids=[d[1] for d in DOORS])
def test_every_door_into_the_page_is_behind_the_constant(marker: str, what: str) -> None:
    """A door left unguarded is the whole defect: one row still offering the feature.

    Checked over the source rather than the DOM because most of these are conditional —
    the Settings link only exists on the Settings view — so a live page can only ever
    prove that a door is *absent right now*, which is a true statement about that moment
    and a false one about the product.
    """
    lines = _read("shell.js").splitlines()
    hits = [i for i, line in enumerate(lines) if marker in line]
    assert hits, f"{what} is gone entirely — this was a withdrawal, not a deletion"

    for i in hits:
        window = "\n".join(lines[max(0, i - GUARD_WINDOW):i + 1])
        assert "INFERENCE_SHIPPED" in window, (
            f"{what} ({marker!r}, line {i + 1}) is not behind INFERENCE_SHIPPED, "
            "so the withdrawn feature is still offered"
        )


@pytest.mark.parametrize(("marker", "what"), KEPT, ids=[k[1] for k in KEPT])
def test_the_feature_itself_is_kept_whole(marker: str, what: str) -> None:
    """The other half, and the one a constant cannot restore.

    Turning the feature back on must be one line. It stops being one line the moment
    somebody tidies away a handler nothing appears to call.
    """
    assert marker in _read("shell.js"), (
        f"{what} has been removed. Inference is withdrawn, not deleted — the next version "
        "starts from this code (Tom, 2026-09-09)"
    )


def test_neither_withdrawn_setting_is_still_a_setting() -> None:
    """`nodeShapes`' precedent, and it is about the reset dialog rather than storage.

    `resetSettings` walks `DEFAULTS`, so a key left there makes a reset report clearing
    *"egress posture"* — naming a setting the reader was never offered and could not have
    changed. A default is a promise that something can be different.
    """
    settings, shell = _read("settings.js"), _read("shell.js")

    defaults = settings.split("const DEFAULTS = {", 1)[1].split("\n};", 1)[0]
    declared = set(re.findall(r"^\s{2}([a-zA-Z][\w]*):", defaults, re.M))
    assert "egress" not in declared and "aiOps" not in declared, \
        "a withdrawn feature's keys must not be defaults the reset dialog can name"

    persisted = shell.split("const PERSISTED = [", 1)[1].split("];", 1)[0]
    assert '"egress"' not in persisted and '"aiOps"' not in persisted, \
        "persisting a value nothing can change writes a key only ever restored to itself"


def test_the_state_the_page_needs_is_still_there() -> None:
    """Kept where they are, so restoring the feature restores its state with it."""
    shell = _read("shell.js")
    for key in ("egress:", "aiOps:", "aiConfirm:", "aiDone:", "showManifest:"):
        assert key in shell, f"state.{key.rstrip(':')} is what the kept page reads"


def test_no_command_offers_an_inference_pass() -> None:
    """There is no `dunneflow infer`, and the CLI must not grow one by accident.

    Stated here rather than assumed: the whole withdrawal rests on the analysis path
    calling no model, and a subcommand appearing would be the loudest possible
    contradiction of *About this map*'s standing guarantee.
    """
    cli = (ROOT / "src" / "dunneflow" / "cli.py").read_text(encoding="utf-8")
    assert 'add_parser("infer"' not in cli
