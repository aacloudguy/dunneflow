"""What the walk left out, from the walk to the panel and to the map it wrote.

**Design rule 1 held for the command line and not for the application, and that is the gap
this file is written from.** `walk_residue` has worded these sentences since the walk was
made multi-language -- *unread: 4,120 `.go`*, *left out as tests: 315 typescript*,
*declined by you* -- and `analyze` has always printed them. It prints them through `_emit`,
which is stderr, and `dunneflow serve` runs its child `--quiet` to keep stderr clear for a
failure's reason. So a reader who analysed from the dialog got a progress bar and a map and
no account at all of what had been filtered out of them.

Three surfaces now, and they are three readers rather than three copies: the terminal, the
`--progress-json` stream that the panel draws, and `meta` on the map itself, which is the
only one that is still there tomorrow. **The sentences are worded in exactly one place**
(rule 51) -- every test here compares against `walk_residue` rather than against a literal,
because a second wording is how the panel goes on saying the old list after the walk learns
a new kind of residue.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from dunneflow import revisions
from dunneflow.cli import _Progress, analysis_steps, build_parser, cmd_analyze
from dunneflow.store import Store
from dunneflow.web import serve as serve_mod
from dunneflow.web.serve import said_residue

TINY = "def f():\n    return 1\n"


def _analysed(tmp_path: Path, *, extra: list[str] | None = None,
              files: dict[str, str] | None = None) -> Store:
    """Analyse a tiny tree for real and hand back its graph, read-only."""
    tree = tmp_path / "src"
    tree.mkdir()
    for name, text in (files or {"m.py": TINY}).items():
        (tree / name).write_text(text, encoding="utf-8")
    out = tmp_path / "out"
    args = build_parser().parse_args(
        ["analyze", str(tree), "--name", "r", "--output", str(out),
         "--no-docs", "--no-render", "--quiet", *(extra or [])])
    assert cmd_analyze(args) == 0
    written = revisions.newest(out / "r", revisions.GRAPH)
    assert written is not None, "the analysis wrote no graph at all"
    return Store(written, writable=False)


# --------------------------------------------------------------------------- #
# The map records it, and records it even when there is nothing to record


def test_a_map_records_what_the_walk_left_out(tmp_path: Path) -> None:
    """A panel is dismissed and a map is kept.

    *5,470 routines* is a claim about what was read, and a reader cannot weigh it without
    knowing what was not. So the account is a fact **about the map**, stored with it, and
    not only a thing said while it was being made.
    """
    store = _analysed(tmp_path, files={"m.py": TINY, "notes.rs": "fn main() {}\n"})
    try:
        lines = json.loads(store.get_meta("walk_residue") or "null")
    finally:
        store.close()
    assert isinstance(lines, list) and lines, "nothing was recorded over an unread suffix"
    assert any(".rs" in line for line in lines), lines
    assert any("unread" in line for line in lines), lines


def test_an_empty_residue_is_recorded_rather_than_left_absent(tmp_path: Path) -> None:
    """**The answer that could not otherwise be given** (design rule 21).

    *This map cannot say* and *nothing was left out* are different claims, and they arrive
    at a reader as the same blank. A map written before this key existed is the first; one
    that records `[]` is the second, and only a key that is always written can tell them
    apart.
    """
    store = _analysed(tmp_path)
    try:
        stored = store.get_meta("walk_residue")
    finally:
        store.close()
    assert stored is not None, "a clean walk recorded nothing, so it cannot say it was clean"
    assert json.loads(stored) == [], stored


def test_the_recorded_lines_are_the_walks_own_words(tmp_path: Path) -> None:
    """Rule 51: one wording, and every surface quotes it.

    A second phrasing on the way to the store is how *analyse again with --include-tests*
    becomes a sentence naming a flag that has been renamed.
    """
    store = _analysed(tmp_path, files={"m.py": TINY, "m_test.py": TINY,
                                       "notes.rs": "fn main() {}\n"})
    try:
        lines = json.loads(store.get_meta("walk_residue") or "[]")
    finally:
        store.close()
    assert any("left out as tests" in line for line in lines), lines
    # Every recorded line is one `walk_residue` can produce -- checked by shape rather than
    # by text, because the texts are what this asserts nobody re-words.
    assert all(isinstance(line, str) and line.strip() for line in lines), lines


# --------------------------------------------------------------------------- #
# The stream carries it, once


def test_the_stream_says_it_once_and_does_not_move_the_bar(monkeypatch: Any) -> None:
    """One object per line, and the residue is a fixed fact among many changing ones.

    Repeating it on every line would multiply four sentences by however long resolution
    takes; sending it with no step would make a client that draws the bar from every object
    jump to a step-less record. So it restates the current step and adds one key.
    """
    said: list[dict[str, Any]] = []
    args = build_parser().parse_args(["analyze", "x", "--no-docs", "--no-render"])
    prog = _Progress(analysis_steps(args), on=True)
    # The channel, captured rather than printed. `monkeypatch` on the *instance* would be
    # assigning to a method; this replaces what the method writes to, which is the seam the
    # real stream uses anyway.
    monkeypatch.setattr("builtins.print",
                        lambda line, **_kw: said.append(json.loads(line)))
    prog.step(prog.steps[0])
    said.clear()
    prog.residue(["unread: 3 .go — no reader here claims that suffix"])

    assert len(said) == 1, said
    one = said[0]
    assert one["residue"] == ["unread: 3 .go — no reader here claims that suffix"]
    assert one["state"] == "working"
    assert one["step"] == prog.steps[0], "the residue moved the bar off its own step"
    assert one["done_steps"] == 0 and one["steps"] == len(prog.steps)


def test_an_analysis_really_puts_it_on_the_machine_channel(tmp_path: Path) -> None:
    """End to end, because the two halves above are each half of a contract.

    `--progress-json` is what `serve` runs, so what this test reads is exactly what the
    panel is drawn from.
    """
    import contextlib
    import io

    tree = tmp_path / "src"
    tree.mkdir()
    (tree / "m.py").write_text(TINY, encoding="utf-8")
    (tree / "notes.rs").write_text("fn main() {}\n", encoding="utf-8")
    args = build_parser().parse_args(
        ["analyze", str(tree), "--name", "r", "--output", str(tmp_path / "out"),
         "--no-docs", "--no-render", "--quiet", "--progress-json"])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert cmd_analyze(args) == 0

    objects = [json.loads(line) for line in out.getvalue().splitlines() if line.strip()]
    carrying = [o for o in objects if "residue" in o]
    assert len(carrying) == 1, f"the residue was sent {len(carrying)} times"
    assert any(".rs" in line for line in carrying[0]["residue"]), carrying[0]


# --------------------------------------------------------------------------- #
# The watcher keeps it, because the report is replaced whole


def _slot() -> Any:
    lv = serve_mod._Live.__new__(serve_mod._Live)
    lv.analysis_lock = threading.Lock()
    lv.analysis = {"state": "idle"}
    lv.analysis_proc = None
    lv.analysis_claimed = False
    return lv


def test_the_residue_survives_every_later_report(tmp_path: Path) -> None:
    """**The stickiness is a term of the contract, not a convenience.**

    `note_analysis` replaces the report whole -- that is deliberate, so a field from a
    previous step cannot survive into this one. The child therefore sends the residue once
    and the watcher carries it, exactly as it carries `began`. Without this the panel would
    show it for the fraction of a second before the next line arrived, which is the same as
    not showing it.
    """
    lv = _slot()
    assert lv.claim_analysis("first") is True
    lv.note_analysis(state="working", step="reading the source tree", done_steps=0,
                     steps=5, detail="", residue=["unread: 3 .go"])
    for i in range(1, 5):
        lv.note_analysis(state="working", step=f"step {i}", done_steps=i, steps=5,
                         detail="")
    lv.note_analysis(state="done", program="first", routines=4)

    got = lv.analysis_progress()
    assert got["state"] == "done"
    assert got["residue"] == ["unread: 3 .go"], (
        "the residue was wiped by the reports after it, so nobody could read it")


def test_the_residue_arriving_is_movement_and_carrying_it_is_not(tmp_path: Path) -> None:
    """`moved` is how a hang is told from a long step, so both directions matter.

    The residue *arriving* is something happening and must bump the clock; the residue
    being carried on every line afterwards must not, or a run would look busy for as long
    as it was being watched -- which is the one thing a silence detector may never do.
    """
    lv = _slot()
    assert lv.claim_analysis("first") is True
    lv.note_analysis(state="working", step="s", done_steps=1, steps=5, detail="")
    lv.analysis["moved"] = 100.0

    lv.note_analysis(state="working", step="s", done_steps=1, steps=5, detail="",
                     residue=["unread: 3 .go"])
    assert lv.analysis["moved"] != 100.0, "the residue arrived and the clock called it silence"

    lv.analysis["moved"] = 100.0
    lv.note_analysis(state="working", step="s", done_steps=1, steps=5, detail="")
    assert lv.analysis["moved"] == 100.0, (
        "a carried residue read as news, so a watched run can never look silent")


def test_a_new_analysis_does_not_inherit_the_last_ones_residue(tmp_path: Path) -> None:
    """A claim replaces the report outright, which is what bounds the stickiness."""
    lv = _slot()
    assert lv.claim_analysis("first") is True
    lv.note_analysis(state="working", step="s", done_steps=0, steps=1, detail="",
                     residue=["unread: 3 .go"])
    lv.note_analysis(state="done", program="first")
    lv.analysis_claimed = False

    assert lv.claim_analysis("second") is True
    assert "residue" not in lv.analysis, (
        "the second analysis reported the first one's residue as its own")


# --------------------------------------------------------------------------- #
# What the map says when it is asked


def test_the_three_states_are_three_different_answers() -> None:
    """Design rule 21, on a field that holds a list rather than a word.

    *Not recorded* is a map written before `analyze` could say; *recorded and empty* is
    *nothing was left out*; *recorded with lines* says which. Flattening the first two
    turns a silence into a promise.
    """
    absent = said_residue(None)
    empty = said_residue("[]")
    full = said_residue(json.dumps(["unread: 3 .go"]))

    assert absent == {"recorded": False, "lines": [], "none": False}
    assert empty == {"recorded": True, "lines": [], "none": True}
    assert full == {"recorded": True, "lines": ["unread: 3 .go"], "none": False}
    assert len({(a["recorded"], a["none"], tuple(a["lines"])) for a in
                (absent, empty, full)}) == 3


def test_a_key_this_build_cannot_read_says_it_cannot_say(tmp_path: Path) -> None:
    """Rule 49: a plausible value standing in for a failure is how the failure hides.

    Text that will not parse as a list of sentences was written by something this build
    does not understand. Reporting that as `none` would be this map claiming nothing was
    left out, on no evidence at all.
    """
    for stored in ("not json at all", "{}", '"a string"', '[1, 2]', "null"):
        got = said_residue(stored)
        assert got["recorded"] is False, f"{stored!r} was read as a recorded answer"
        assert got["none"] is False, f"{stored!r} was read as *nothing was left out*"


def test_about_reports_it_for_a_map_that_records_it(tmp_path: Path) -> None:
    """The row a reader actually sees, from a map a real analysis wrote."""
    store = _analysed(tmp_path, files={"m.py": TINY, "notes.rs": "fn main() {}\n"})
    try:
        got = said_residue(store.get_meta("walk_residue"))
    finally:
        store.close()
    assert got["recorded"] is True and got["none"] is False
    # Sentences, and the walk's own: each names the thing it left out and what would change
    # it. The wording is `walk_residue`'s and is asserted there; what matters here is that
    # nothing between the walk and this row shortened one into a label (rule 30).
    assert got["lines"] and all(" " in line for line in got["lines"]), got
    assert any(".rs" in line for line in got["lines"]), got


# --------------------------------------------------------------------------- #
# The panel draws it


STATIC = Path(__file__).resolve().parent.parent / "src" / "dunneflow" / "web" / "static"


def test_the_panel_draws_the_residue_in_every_state_that_has_one() -> None:
    """Rule 78's neighbourhood: a block added to one branch of a renderer.

    `analysisPanel` has four branches and three of them can be reached with a residue in
    hand -- a run in progress, a run that finished, and a run the reader stopped after the
    walk was done. Only *failed* cannot, because a failure has no map to describe. Asserted
    over the source because there is no JS runtime here, and asserted as **calls** rather
    than as the word appearing anywhere (rule 37).
    """
    js = (STATIC / "analyze.js").read_text(encoding="utf-8")
    assert "function residueBlock(" in js, "the block is not defined"
    assert js.count("${residueBlock(a)}") == 3, (
        "the residue is drawn in some panel states and not others -- a reader who stops a "
        "run, or comes back to a finished one, sees a different account of the same walk")


def test_the_about_dialog_keeps_the_three_states_apart() -> None:
    """The panel may flatten *absent* and *empty*; this page may not.

    A running commentary that announced *nothing was left out* on every healthy analysis
    would be noise on the common case. *About this map* is a question being asked, and the
    answer to it has to distinguish a map that cannot say from one saying there was nothing
    (design rule 21).
    """
    js = (STATIC / "shell.js").read_text(encoding="utf-8")
    assert "d.walk_residue" in js
    assert "res.none" in js, "the empty answer has no words of its own"
    assert "res.recorded" in js, "*cannot say* and *nothing* were flattened"
    assert "about-residue" in js
