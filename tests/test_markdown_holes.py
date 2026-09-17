"""The map says what it deliberately does not claim.

`render/markdown.py:_unclaimed_marks`. A hole a reader can act on is stated; one that is
merely absent is a false claim of completeness — and this is design rule 13's shape, the
count beside the query that returns exactly it.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.render.markdown import _unclaimed_marks
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
