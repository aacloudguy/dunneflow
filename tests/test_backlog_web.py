"""Guards for the dashboard fixes made from the 2026-10-02 retake's BACKLOG items.

Source-reading guards in `test_web_controls.py`'s idiom, and over its helpers, so a span
means the same thing here as there: `_fn` by brace depth, `_code` with comment lines
removed, because a comment naming the fix is not the fix (rule 37).
"""

from __future__ import annotations

import re

from tests.test_web_controls import _code, _fn, _read


def test_the_boundaries_note_counts_the_kinds_it_lists():
    """BACKLOG 18(a): "the nine kinds" sat over a list of seven."""
    js = _code(_read("shell.js"))
    assert "nine kinds" not in js
    assert "${BOUNDARIES.length} kind" in js


def test_the_change_group_lists_every_band_its_badge_counts():
    """BACKLOG 18(e): the badge counted the structure bands and the group listed none."""
    js = _read("shell.js")
    count, listed = _code(_fn(js, "changeCount")), _code(_fn(js, "changeList"))
    for spec in ("CHANGE_FILE_BANDS", "CHANGE_STRUCT_BANDS"):
        assert spec in count and spec in listed, spec
    # And the one band listed but not counted says so in its own title.
    assert "not in the count" in listed


def test_both_document_counts_say_which_documents():
    """BACKLOG 18(d): 52 on the glossary and 53 on the stated page, a click apart."""
    js = _code(_read("shell.js"))
    assert "distinct document" in js
    assert re.search(r"byte-identical\s+copy of another", js)


def test_the_versions_are_asked_for_with_the_cover_not_after_it():
    """BACKLOG 18(f): `/api/revisions` queued behind everything else on a cold open."""
    boot = _code(_fn(_read("shell.js"), "boot"))
    asked, cover = boot.index("loadRevisions()"), boot.index("await loadCover()")
    assert asked < cover, "the versions are requested after the cover"
    assert "await loadRevisions()" not in boot, "a second, serial request was left behind"
