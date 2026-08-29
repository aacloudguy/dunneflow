"""Where a revision's databases live, and which one a reader opens.

The failure this guards against is rule 20's, one layer out: a reader that resolves to
a fixed `graph.db` answers "no graph — run analyze first" for a program that has been
analysed several times, which is a confident wrong answer about a store that is right
there. And its mirror, which is worse: a reader that silently opened the *oldest*
revision would answer every question correctly about the wrong point in time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow import revisions

R1 = "2026-08-26T09:14:02Z"
R2 = "2026-08-29T23:11:46Z"


def _touch(p: Path) -> Path:
    p.write_bytes(b"")
    return p


def test_a_filename_survives_the_round_trip():
    """The colons are a portability trap; the date's own dashes are not separators."""
    p = revisions.db_path(Path("/out"), revisions.GRAPH, R2)
    assert p.name == "graph@2026-08-29T23-11-46Z.db"
    assert revisions.revision_of(p) == R2


def test_filenames_sort_into_chronological_order():
    """`-` for `:` is order-preserving, which is the only reason `newest` may sort names.

    The half-working version replaces the colon with something above `T` in ASCII, and
    every listing silently reverses within the same day.
    """
    names = [revisions.db_path(Path("/o"), revisions.GRAPH, r).name for r in (R1, R2)]
    assert sorted(names, reverse=True)[0] == revisions.db_path(
        Path("/o"), revisions.GRAPH, R2).name


def test_newest_picks_the_latest_revision(tmp_path):
    _touch(revisions.db_path(tmp_path, revisions.GRAPH, R1))
    want = _touch(revisions.db_path(tmp_path, revisions.GRAPH, R2))
    assert revisions.newest(tmp_path, revisions.GRAPH) == want


def test_a_legacy_bare_graph_is_still_read(tmp_path):
    """A directory written before this layout is read as the one revision it is.

    Rule 20: a read may refuse but may never repair. Renaming someone's `graph.db` into
    the new shape behind them is the destructive-fallback-in-a-uniform this project has
    already paid for twice (rules 16 and 20).
    """
    legacy = _touch(tmp_path / "graph.db")
    assert revisions.newest(tmp_path, revisions.GRAPH) == legacy
    assert legacy.exists(), "the legacy file must not be moved or rewritten"
    assert revisions.revision_of(legacy) is None, "it claims no revision, and says so"


def test_a_revision_outranks_the_legacy_name(tmp_path):
    """Both present: the analysed revision wins, and the old file is left alone."""
    _touch(tmp_path / "graph.db")
    want = _touch(revisions.db_path(tmp_path, revisions.GRAPH, R2))
    assert revisions.newest(tmp_path, revisions.GRAPH) == want
    assert (tmp_path / "graph.db").exists()


def test_nothing_there_is_not_an_empty_store(tmp_path):
    """None, so the caller can say "no such program" rather than answer out of a hole."""
    assert revisions.newest(tmp_path, revisions.GRAPH) is None


def test_resolve_names_one_revision(tmp_path):
    a = _touch(revisions.db_path(tmp_path, revisions.GRAPH, R1))
    _touch(revisions.db_path(tmp_path, revisions.GRAPH, R2))
    assert revisions.resolve(tmp_path, revisions.GRAPH, R1) == a
    assert revisions.resolve(tmp_path, revisions.GRAPH, "2020-01-01T00:00:00Z") is None


def test_the_graph_and_the_documents_do_not_collide(tmp_path):
    """One directory holds both, per revision, and `newest` must not cross the streams."""
    g = _touch(revisions.db_path(tmp_path, revisions.GRAPH, R2))
    d = _touch(revisions.db_path(tmp_path, revisions.DOCS, R2))
    assert revisions.newest(tmp_path, revisions.GRAPH) == g
    assert revisions.newest(tmp_path, revisions.DOCS) == d


@pytest.mark.parametrize("stem", [revisions.GRAPH, revisions.DOCS])
def test_a_stamp_is_a_usable_revision(stem):
    """What `--no-source` mints must round-trip like one the sidecar handed out."""
    rev = revisions.stamp()
    assert revisions.revision_of(revisions.db_path(Path("/o"), stem, rev)) == rev
