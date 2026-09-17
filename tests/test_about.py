"""What read this map, and whether anything in it was guessed.

The dialog states two things a reader handed a map is entitled to and could not previously
find anywhere: **nothing here was inferred**, and **nothing here was read by a model**. They
are a standing guarantee rather than a readout that happens to say nothing -- nothing on the
analysis path calls a model or touches a network -- so the tests here are about keeping the
guarantee honest rather than about rendering:

  - a claim on screen that no query can return is prose (rule 13), so the determinism half
    is checked against the source that has to stay deterministic;
  - **missing and blank are different answers**: a map written before this existed cannot
    say, and that is not the same claim as *nothing was inferred* (rule 30);
  - a map with no documents, no sidecar and no program version must still answer every row,
    each absence in its own words (design rule 21).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from dunneflow import revisions
from dunneflow.store import Store
from dunneflow.web import serve as serve_mod

SRC = Path(serve_mod.__file__).parent.parent

TINY = '''\
"""A program with something to count."""
import sqlite3


def open_it(path):
    return sqlite3.connect(path)
'''


def _live(tmp_path: Path, **meta: str) -> Any:
    """A served base over a one-file program, with whatever meta the test wants."""
    out = tmp_path / "prog"
    out.mkdir()
    rev = "2026-08-30T10:00:00Z"
    graph = revisions.db_path(out, revisions.GRAPH, rev)
    store = Store(graph)
    from dunneflow.extractors.python.extract import extract_file
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "m.py").write_text(TINY, encoding="utf-8")
    store.write_file_facts(extract_file(tree / "m.py", tree))
    store.set_meta("revision", rev)
    store.set_meta("program", "tinyprog")
    for k, v in meta.items():
        store.set_meta(k, v)
    store.conn.commit()
    store.close()
    lv = serve_mod._Live(out / "source.db", out)
    lv.open(graph)
    return lv


class _Cap:
    """Enough of a handler to call one route and keep what it answered."""

    def __init__(self, live: Any) -> None:
        self._live = live
        self.body: dict[str, Any] = {}

    def _json(self, body: dict[str, Any]) -> None:
        self.body = body


def _about(live: Any) -> dict[str, Any]:
    cap = _Cap(live)
    serve_mod._Handler._r_about(cap, {})       # type: ignore[arg-type]
    return cap.body


# ------------------------------------------------- the guarantee, kept honest --- #


def test_the_determinism_claim_is_checkable_rather_than_prose() -> None:
    """A claim on screen whose query returns nothing is prose (rule 13).

    The dialog says *nothing here was read by a model* and *nothing left this machine*.
    That has to be true of the code, not merely of the intention -- so nothing that reads
    source or prose, and nothing that resolves either, may reach for an HTTP client or an
    LLM SDK. `web/` is excluded on purpose: it *is* an HTTP server, and the claim is about
    what produced the facts rather than about what serves them.

    Tom, 2026-09-04: *"Inference should always be voluntary and secondary."* Voluntary
    means somebody turns it on; until somebody does, this is what says so.

    **`ingest/` joined the guard the day it was wired**, and that was the condition stated
    when it was written: it decides which reader a file goes to and holds the one that
    runs in this interpreter, so from the moment `walk.py` dispatches through it, it is on
    the path that produced every fact. `plugins/` is here for the same reason and is also
    why a plugin is discovered from `resource_root()/plugins/` and never from an
    entry-point group -- a guarantee printed on screen cannot survive arbitrary
    third-party code arriving on the ingest path.
    """
    banned = re.compile(
        r"^\s*(?:import|from)\s+(requests|httpx|urllib3|aiohttp|openai|anthropic|"
        r"google\.generativeai|cohere|mistralai|ollama)\b", re.M)
    looked = 0
    for area in ("extractors", "resolve", "canonical", "ingest", "plugins"):
        for mod in (SRC / area).rglob("*.py"):
            looked += 1
            found = banned.search(mod.read_text(encoding="utf-8"))
            assert not found, (
                f"{mod.relative_to(SRC)} imports {found.group(1)} -- the About dialog "
                "claims every fact here was read deterministically and locally, and that "
                "claim is now false"
            )
    assert looked > 10, f"only {looked} modules scanned; this guard is blind"


def test_a_fresh_map_says_nothing_was_inferred_and_no_model_read_it(
        tmp_path: Path) -> None:
    """The two rows the dialog exists for, on a map that records them."""
    live = _live(tmp_path, tool_version="0.1.0", inference="none", model="")
    try:
        d = _about(live)
    finally:
        live.close()
    # **Two spellings of nothing, one answer.** `inference` says `none` so the store reads
    # as prose under `dunneflow query`; `model` is blank because there is no word for the
    # model that did not run. The page must not have to know either, so the server decides.
    assert d["inference"] == {"recorded": True, "value": "none", "none": True}
    assert d["model"] == {"recorded": True, "value": "", "none": True}
    assert d["tool_version"]["value"] == "0.1.0"
    assert d["tool_version"]["none"] is False, "a real value was read as nothing"


def test_a_map_that_predates_the_question_says_so_rather_than_none(
        tmp_path: Path) -> None:
    """The distinction the whole guarantee rests on.

    *This map cannot say* and *nothing was inferred* look identical in a blank cell, and
    only one of them is a promise. A store written before these keys existed must report
    `recorded: false` so the dialog can render the difference -- rule 30, with a missing
    key and an empty one as the two things a label must not flatten.
    """
    live = _live(tmp_path)                     # no meta beyond revision and program
    try:
        d = _about(live)
    finally:
        live.close()
    for key in ("tool_version", "inference", "model", "analysis_args"):
        assert d[key] == {"recorded": False, "value": "", "none": False}, (
            f"{key} claims to know"
        )
        # **The distinction, stated as an assertion.** `none` must be false here: a map
        # that cannot say has not said nothing, and rendering the two the same way turns
        # a silence into a guarantee it never made.
        assert not d[key]["none"], f"{key} reads an unrecorded field as a promise"


def test_every_absence_answers_in_its_own_words(tmp_path: Path) -> None:
    """No documents, no sidecar, no version -- and every row still answers.

    Design rule 21: a blank must say why it is blank. Three different absences here, and
    the one that matters most is `documents`: `None` is *nobody scanned any* and `0` is
    *there are none*, which design rule 11 makes two different facts about a program.
    """
    live = _live(tmp_path)
    try:
        d = _about(live)
    finally:
        live.close()
    assert d["tree"] is None, "a tree name was invented with no sidecar to ask"
    assert d["counts"]["documents"] is None, (
        "an unscanned corpus reported as a count -- 0 documents and no scan are different"
    )
    assert d["counts"]["files"] == 1 and d["counts"]["routines"] >= 1
    assert d["program"] == "tinyprog"


def test_the_dialog_says_what_the_map_was_read_from(tmp_path: Path) -> None:
    """The mirror page's claim, as the count it comes from (rule 32).

    Two things at once, and the second is the one that will go wrong later: the block is
    what this **map** holds, never what this **build** can read — a version that reads
    TypeScript and was pointed at a Python tree must still say Python here, or the dialog
    describes the tool instead of the map (rule 24).
    """
    live = _live(tmp_path)
    try:
        d = _about(live)
    finally:
        live.close()
    assert d["languages"] == [{"lang": "python", "display": "Python", "files": 1}]


def test_the_dialog_spells_a_language_with_the_word_the_plugin_gave_it() -> None:
    """`files.lang` holds `python`; a sentence a reader reads says `Python`.

    The page owns neither spelling — the same argument that keeps `none` on the server
    (rule 51). A page that rendered the key would put a lowercase identifier in a dialog
    whose every other row is prose.
    """
    shell = (SRC / "web/static/shell.js").read_text(encoding="utf-8")
    body = shell.split('row("Read from"', 1)[1].split(");", 1)[0]
    assert "l.display" in body, "the dialog renders the stored key rather than the word"
    assert "records no language" in body, (
        "a map with no language recorded renders an empty row (design rule 21)"
    )


def test_the_dialog_renders_missing_and_recorded_differently() -> None:
    """The server's distinction is worthless if the page flattens it.

    `aboutSays` is the one place that decides, and it takes the *not recorded* sentence as
    an argument rather than falling through to the same empty string -- which is what
    would make a legacy map read as a guarantee it never made.
    """
    shell = (SRC / "web/static/shell.js").read_text(encoding="utf-8")
    body = shell.split("function aboutSays", 1)[1].split("\nfunction ", 1)[0]
    assert "recorded" in body, "aboutSays ignores whether the field was recorded at all"
    assert body.count("return") >= 2, "one return cannot render two different answers"
    # And it must read the server's decision rather than test for the word. Two fields
    # spell nothing differently in the store, and a page that knows one spelling renders
    # the other as a bare value -- which is how "Inferred facts: none" replaced the
    # sentence that was the whole point of the row.
    assert ".none" in body, "aboutSays decides for itself what counts as nothing"
    assert '"none"' not in body and "'none'" not in body, (
        "aboutSays tests for the literal word, which it does not own (rule 51)"
    )
    # And both callers must pass a sentence for the missing case.
    for field in ("d.inference", "d.model"):
        call = shell.split(f"aboutSays({field},", 1)
        assert len(call) == 2, f"{field} is not rendered through aboutSays"
        args = call[1].split(")}", 1)[0]
        assert args.count(",") >= 1, f"{field} has no sentence for the unrecorded case"


def test_the_dialog_claims_nothing_about_a_tree_it_has_not_looked_at() -> None:
    """Rule 13's family, in the one line of this dialog that was not a recorded fact.

    The footer read *"The tree it was read from **has** moved on since; this map has not."*
    Every other line here is something the map wrote down — the date, the leaf, the tool
    version, the two guarantees. That one was a statement about the world, made by a dialog
    that has not looked at the world since the analysis, and **opened straight after an
    analysis it is simply false** — which is where Tom reported it.

    What is true, and all that is true, is that nothing here has been checked against that
    tree since. So the sentence says *may have*.

    Asserted on the shape rather than on the wording: the claim is any assertion in the
    indicative about that tree having changed, and a rewrite that reintroduced it in other
    words would be the same defect.
    """
    shell = (SRC / "web/static/shell.js").read_text(encoding="utf-8")
    # Anchored on the sentence rather than on `about-foot`, which is also a class name in the
    # stylesheet above and so matches there first.
    opener = "A map is a reading of a program at a moment."
    assert shell.count(opener) == 1, "the footer sentence is no longer where this looks"
    foot = shell.split(opener, 1)[1].split("</span>", 1)[0]
    assert "may have moved on" in foot, (
        "the About footer no longer hedges a claim it cannot make"
    )
    for asserted in ("has moved on", "will have moved on", "is now out of date"):
        assert asserted not in foot, (
            f"the About footer states {asserted!r} about a tree it has not looked at since"
        )


def test_the_route_is_a_get_and_reads_nothing_it_can_change() -> None:
    """It is a read, like everything else under `web/` but the one analysis route."""
    handler = serve_mod._Handler
    assert handler.ROUTES.get("/api/about") == "_r_about"
    assert "_r_about" not in handler.POST_ROUTES.values()
    src = Path(serve_mod.__file__).read_text(encoding="utf-8")
    body = src.split("def _r_about", 1)[1].split("\n    def ", 1)[0]
    assert "set_meta" not in body, "the About route writes to the store it came to read"
    assert "with self._live.lock" in body, (
        "the base is read outside the lock a switch commits under"
    )


def test_analyze_records_what_read_the_map(tmp_path: Path) -> None:
    """The other end: `analyze` has to write what `/api/about` reads.

    Written from the store rather than asserted against a literal -- `_tool_version` reads
    the package, so a hard-coded expectation here would be the second answer that goes
    stale (rule 51).
    """
    from importlib import metadata

    from dunneflow.cli import build_parser, cmd_analyze
    tree = tmp_path / "src"
    tree.mkdir()
    (tree / "m.py").write_text(TINY, encoding="utf-8")
    out = tmp_path / "out"
    args = build_parser().parse_args(
        ["analyze", str(tree), "--name", "rec", "--output", str(out),
         "--no-docs", "--no-render", "--quiet"])
    assert cmd_analyze(args) == 0

    written = revisions.newest(out / "rec", revisions.GRAPH)
    assert written is not None, "the analysis wrote no graph at all"
    store = Store(written, writable=False)
    try:
        assert store.get_meta("tool_version") == metadata.version("dunneflow")
        assert store.get_meta("inference") == "none"
        assert store.get_meta("model") == ""
        # What the run was told, and only what *removed* something: a map with no
        # documents must be able to say it was asked to have none (design rule 1).
        assert "documentation not read" in (store.get_meta("analysis_args") or "")
    finally:
        store.close()


@pytest.mark.parametrize("flag,expected", [
    ("--include-tests", "tests included"),
    ("--no-source", "source bodies not kept"),
    ("--no-render", "map not written"),
])
def test_what_the_run_was_told_names_only_what_it_removed(
        flag: str, expected: str) -> None:
    """A phrase per flag, and nothing for a run that was told nothing.

    An empty string is the right answer for a default run: *"it was told"* with nothing
    after it is a row that says less than no row at all.
    """
    from dunneflow.cli import _args_said, build_parser
    plain = build_parser().parse_args(["analyze", "x"])
    assert _args_said(plain) == "", f"a default run claims {_args_said(plain)!r}"
    with_flag = build_parser().parse_args(["analyze", "x", flag])
    assert expected in _args_said(with_flag)
