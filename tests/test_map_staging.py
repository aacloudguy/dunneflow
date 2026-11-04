"""Rule 109: a folder of pages is an artefact, finished only once renamed into place.

A render of Unreal's `Runtime` crashed in `02-flows.md` and left `map@<rev>/` holding
`README.md` and `01-entrypoints.md`. The graph was correctly marked unfinished; the folder
had the finished map's name, a cover page vouching for it, and thirteen pages missing --
and `revisions.known_maps` counted it, so `dunneflow render`, the one command that could
repair it, answered *every revision already has a map*.

And the Setting that came with it, "Unfinished maps: refuse / open with a warning", which
governs every reader that refuses an unfinished graph: the dashboard's open and switch, and
the orientation commands (Tom, 2026-11-03: strictness is the reader's choice).
"""

from __future__ import annotations

import json
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from dunneflow import revisions
from dunneflow.cli import build_parser, cmd_check
from dunneflow.render import markdown
from dunneflow.render.index import render_index
from dunneflow.render.snapshot import mapless, render_maps, render_snapshot
from dunneflow.store import Store, UnfinishedMapError
from dunneflow.web.serve import _Handler, _Live, _unfinished_choice, where
from tests.test_cold_start import _get, _make_program, _post
from tests.test_snapshot_render import REV_A, _graph


class _Died(RuntimeError):
    """What a page raises when the test wants the render to stop there."""


def _die_in_routines(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise _Died("the disk filled")
    monkeypatch.setattr(markdown, "_routines", boom)


# --------------------------------------------------------------------------- #
# The folder


def test_a_render_that_dies_leaves_a_folder_nothing_counts_as_a_map(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    _die_in_routines(monkeypatch)

    with pytest.raises(_Died):
        render_snapshot(out_dir, REV_A)

    final = revisions.map_dir(out_dir, REV_A)
    staged = revisions.staging_dir(final)
    assert not final.exists(), "a render that died left a folder with the finished name"
    assert staged.is_dir(), "the pages it did write must stay, under a name nothing reads"
    assert (staged / "README.md").exists() and (staged / "02-flows.md").exists()
    assert revisions.known_maps(out_dir) == {}, "a half-written folder was counted as a map"
    assert revisions.unfinished_maps(out_dir) == {REV_A: staged}
    assert mapless(out_dir) == [REV_A], "render must offer the revision again"

    note = (staged / revisions.UNFINISHED_NOTE).read_text(encoding="utf-8")
    assert "page 4 of 15, `03-routines.md`" in note, note
    assert f"--revision {REV_A}" in note, "the note must name the command that repairs it"


def test_render_repairs_it_and_the_note_does_not_survive(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    _die_in_routines(monkeypatch)
    with pytest.raises(_Died):
        render_snapshot(out_dir, REV_A)
    monkeypatch.undo()

    done = render_maps(out_dir)

    final = revisions.map_dir(out_dir, REV_A)
    assert [r.revision for r in done if r.map_dir] == [REV_A]
    assert not revisions.staging_dir(final).exists()
    assert not (final / revisions.UNFINISHED_NOTE).exists()
    assert all(f.parent == final and f.exists() for f in done[0].files), \
        "the paths handed back must be the finished folder's, not the staging one's"


def test_a_rewrite_that_dies_keeps_the_old_map_and_one_that_finishes_drops_stale_pages(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In place, a dying rewrite would leave new pages over old ones and call it a map."""
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    assert not render_snapshot(out_dir, REV_A).refusal
    final = revisions.map_dir(out_dir, REV_A)
    before = (final / "03-routines.md").read_bytes()
    (final / "stale.md").write_text("a page no render writes any more\n", encoding="utf-8")

    _die_in_routines(monkeypatch)
    with pytest.raises(_Died):
        render_snapshot(out_dir, REV_A)
    assert (final / "03-routines.md").read_bytes() == before, \
        "a rewrite that died touched the finished map"
    monkeypatch.undo()

    assert not render_snapshot(out_dir, REV_A).refusal
    assert not (final / "stale.md").exists(), "a page from an earlier render survived"
    assert not revisions.staging_dir(final).exists()


def test_the_note_names_every_page_render_all_writes(tmp_path: Path) -> None:
    """`PAGE_NAMES` is positional; a page added to the list and not to it misnames the stop."""
    out_dir = tmp_path / "prog"
    graph = _graph(out_dir, REV_A, tmp_path)
    totals: set[int] = set()
    store = Store(graph, writable=False)
    try:
        markdown.render_all(store, revisions.map_dir(out_dir, REV_A), "fixture",
                            tick=lambda _d, n, what: totals.add(n) if what == "document"
                            else None)
    finally:
        store.close()
    assert totals == {len(markdown.PAGE_NAMES)}


def test_the_listing_links_an_unfinished_folder_to_its_note_never_its_pages(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out_dir = tmp_path / "prog"
    _graph(out_dir, REV_A, tmp_path)
    _die_in_routines(monkeypatch)
    with pytest.raises(_Died):
        render_snapshot(out_dir, REV_A)

    text = render_index(out_dir, "fixture").read_text(encoding="utf-8")
    staged = revisions.staging_dir(revisions.map_dir(out_dir, REV_A)).name
    assert "*never finished*" in text
    assert f"]({staged}/{revisions.UNFINISHED_NOTE})" in text
    assert f"]({staged}/README.md)" not in text, "the half-written cover was linked as a map"


# --------------------------------------------------------------------------- #
# The Setting: the CLI


def test_check_reads_an_unfinished_map_only_when_told_and_says_so(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "out"
    _graph(out / "half", REV_A, tmp_path, finished=False)
    argv = ["check", str(tmp_path / "anything"), "--name", "half", "--output", str(out)]

    assert cmd_check(build_parser().parse_args(argv)) == 2
    refused = capsys.readouterr().err
    assert "--allow-unfinished" in refused, "the refusal must name the Setting that opens it"

    assert cmd_check(build_parser().parse_args([*argv, "--allow-unfinished"])) == 0
    said = capsys.readouterr().err
    assert "warning:" in said and "never finished" in said and "resolving calls" in said


@pytest.mark.parametrize("command", ["touches", "impact", "check", "glossary", "naming",
                                     "mirror", "serve", "mcp"])
def test_every_reader_that_refuses_takes_the_flag(command: str) -> None:
    extra = {"touches": ["x", "--routine", "r"], "impact": ["x", "--routine", "r"],
             "serve": [], "mcp": []}.get(command, ["x"])
    args = build_parser().parse_args([command, *extra, "--allow-unfinished"])
    assert args.allow_unfinished is True


# --------------------------------------------------------------------------- #
# The Setting: the server


def test_the_base_opens_an_unfinished_map_with_its_sentence_when_allowed(
        tmp_path: Path) -> None:
    out_dir = tmp_path / "prog"
    graph = _graph(out_dir, REV_A, tmp_path, finished=False)
    lv = _Live(out_dir / "source.db", out_dir, allow_unfinished=True)
    try:
        lv.open(graph)
        assert "never finished" in lv.current.unfinished
        assert "resolving calls" in lv.current.unfinished, "the banner must name the step"
    finally:
        lv.close()


def test_a_request_that_says_refuse_wins_over_the_servers_default(tmp_path: Path) -> None:
    out_dir = tmp_path / "prog"
    graph = _graph(out_dir, REV_A, tmp_path, finished=False)
    lv = _Live(out_dir / "source.db", out_dir, allow_unfinished=True)
    try:
        with pytest.raises(UnfinishedMapError):
            lv.open(graph, allow_unfinished=False)
    finally:
        lv.close()


def test_a_finished_map_carries_no_warning(tmp_path: Path) -> None:
    out_dir = tmp_path / "prog"
    graph = _graph(out_dir, REV_A, tmp_path)
    lv = _Live(out_dir / "source.db", out_dir, allow_unfinished=True)
    try:
        lv.open(graph)
        assert lv.current.unfinished == ""
    finally:
        lv.close()


def test_the_choice_has_three_states_and_guesses_none() -> None:
    assert _unfinished_choice({"unfinished": ["open"]}) is True
    assert _unfinished_choice({"unfinished": ["refuse"]}) is False
    assert _unfinished_choice({}) is None
    assert _unfinished_choice({"unfinished": ["yes"]}) is None


def _wait(base: str) -> dict[str, Any]:
    for _ in range(200):
        _status, body = _get(base + "/api/base")
        d = json.loads(body)
        if d.get("state") in ("done", "failed"):
            return d
        time.sleep(0.05)
    raise AssertionError("the open never ended")


@pytest.mark.parametrize("choice", ["refuse", "open"])
def test_the_page_sends_the_setting_and_about_carries_the_warning(
        tmp_path: Path, choice: str) -> None:
    root = tmp_path / "maps"
    root.mkdir()
    half = _make_program(root, "half")
    graph = revisions.newest(half, revisions.GRAPH)
    assert graph is not None
    store = Store(graph)
    store.set_meta("complete", "")
    store.set_meta("step", "reading the documents")
    store.conn.commit()
    store.close()

    out_dir, out_root = where(root)
    live = _Live(out_dir / "source.db", out_dir, out_root)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Handler, live=live))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        status, body = _post(base + f"/api/program?name=half&unfinished={choice}")
        assert status == 200 and json.loads(body)["started"], body
        ended = _wait(base)
        if choice == "refuse":
            assert ended["state"] == "failed" and ended.get("unfinished") is True, ended
            return
        assert ended["state"] == "done", ended
        _status, about = _get(base + "/api/about")
        said = json.loads(about)["unfinished"]
        assert "never finished" in said and "reading the documents" in said
    finally:
        httpd.shutdown()
        httpd.server_close()
        live.close()

