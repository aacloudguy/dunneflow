"""The map says what it deliberately does not claim.

`render/markdown.py:_unclaimed_marks`. A hole a reader can act on is stated; one that is
merely absent is a false claim of completeness — and this is design rule 13's shape, the
count beside the query that returns exactly it.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.anomalies import detect
from dunneflow.render import markdown as markdown_mod
from dunneflow.render.markdown import _unclaimed_marks, render_all
from dunneflow.schema import FileFacts, Routine, make_id
from dunneflow.store import Store

PATH = "app/actions/x.ts"


def _facts(lang: str, decorators: list[str]) -> FileFacts:
    return FileFacts(
        path=PATH, lang=lang, module="x", content_hash="h",
        routines=[
            Routine(id=make_id("r", name), name=name, qualname=f"x.{name}",
                    module="x", file=PATH, line_start=1 + i, line_end=2 + i,
                    lang=lang, decorators=list(decorators))
            for i, name in enumerate(("createThing", "deleteThing"))
        ],
    )


def _store(tmp_path: Path, decorators: list[str]) -> Store:
    store = Store(tmp_path / "graph.db")
    store.write_file_facts(_facts("typescript", decorators))
    return store


def test_a_mark_the_map_does_not_claim_is_counted_with_its_query(tmp_path):
    store = _store(tmp_path, ["use server"])
    try:
        out = "\n".join(_unclaimed_marks(store, "demo"))
    finally:
        store.close()
    assert "Not claimed as a way in" in out
    assert "**2 routines in 1 file**" in out
    assert "use server" in out
    # The query is printed so a reader can run it, and it is the query that returns the
    # number beside it.
    assert "dunneflow query" in out and "decorators LIKE '%use server%'" in out


def test_a_mark_the_map_does_claim_is_not_listed_as_a_hole(tmp_path):
    """`"use client"` is recorded and hides nothing: its exports are already routines."""
    store = _store(tmp_path, ["use client"])
    try:
        out = "\n".join(_unclaimed_marks(store, "demo"))
    finally:
        store.close()
    assert out == ""


def test_a_language_that_declares_no_directive_says_nothing(tmp_path):
    """Python declares none, so a Python map's chapter is exactly what it always was."""
    store = Store(tmp_path / "graph.db")
    store.write_file_facts(_facts("python", ["use server"]))
    try:
        assert _unclaimed_marks(store, "demo") == []
    finally:
        store.close()


# --------------------------------------------------------------- detected once --- #
#
# The overview's headline and the file it points at are one report, and until
# 2026-09-20 they were two.


def test_the_whole_map_is_written_from_one_detection(tmp_path, monkeypatch):
    """One judgement over one unchanged store, made once.

    `render_all` detected anomalies for `09-anomalies.md` and `_overview` detected them
    again for the *"🔴 N broken — see 09-anomalies.md"* line that sends the reader there,
    and `cli.py` detected them a third time for its own step. On `Engine/Binaries` --
    3,146 files, 71,306 routines -- `detect` is **306 s**, and the run spent 855.6 s
    writing the map and 306.4 s looking for anomalies: **94.8% of 1,226.6 s** deciding the
    same thing three times. Most of `BACKLOG.md` item 9's answer for a part of that size.

    Counted rather than timed. A test that asserted a duration would measure the machine
    it runs on; what is being claimed here is a number of calls, and that is the same
    everywhere.
    """
    calls = []
    real = markdown_mod.detect
    monkeypatch.setattr(markdown_mod, "detect",
                        lambda *a, **k: (calls.append(1), real(*a, **k))[1])

    store = Store(tmp_path / "graph.db")
    store.write_file_facts(FileFacts(
        path="app/thing.py", lang="python", module="thing", content_hash="a",
        routines=[Routine(id=make_id("r", "dup"), name="dup", qualname="thing.dup",
                          module="thing", file="app/thing.py", line_start=1, line_end=2,
                          lang="python"),
                  Routine(id=make_id("r", "dup2"), name="dup", qualname="thing.dup",
                          module="thing", file="app/thing.py", line_start=5, line_end=6,
                          lang="python")]))
    try:
        # Handed a report, it must not detect at all -- which is the case `cli.py` uses.
        render_all(store, tmp_path / "given", "demo", report=detect(store))
        assert calls == [], f"the map detected {len(calls)} times over a report it was given"

        # Handed none, exactly once for the whole map.
        render_all(store, tmp_path / "found", "demo")
        assert len(calls) == 1, f"the map detected {len(calls)} times, not once"
    finally:
        store.close()


def test_a_caller_with_no_report_still_gets_one(tmp_path):
    """`None` detects. A renderer that silently wrote no anomalies to save the work would
    be worse than a slow one (rule 49), and this function is called from places that have
    no report to hand."""
    store = Store(tmp_path / "graph.db")
    store.write_file_facts(FileFacts(path="a.py", lang="python", module="a",
                                     content_hash="h", routines=[]))
    try:
        out = tmp_path / "map"
        written = render_all(store, out, "demo")
        assert (out / "09-anomalies.md") in written
    finally:
        store.close()
