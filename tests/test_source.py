"""The source sidecar: content addressing, and the two ways it must refuse to destroy."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dunneflow import sourcedb
from dunneflow.schema import hash_source
from dunneflow.sourcedb import SourceStore, WrongStoreKind, capture


def _store(tmp_path: Path) -> SourceStore:
    return SourceStore(tmp_path / "source.db")


# --------------------------------------------------------------- addressing --- #

def test_identical_bodies_are_stored_once(tmp_path: Path) -> None:
    """The property the whole design rests on: one blob, however many paths."""
    body = "def f():\n    return 1\n"
    h = hash_source(body)
    s = _store(tmp_path)
    s.add_blob(body, h)
    s.map_path("/a/one.py", h, lang="python")
    s.add_blob(body, h)
    s.map_path("/b/two.py", h, lang="python")
    s.commit()

    c = s.counts()
    assert c["blobs"] == 1
    assert c["paths"] == 2
    assert s.text("/a/one.py") == body
    assert s.text("/b/two.py") == body


def test_add_blob_reports_whether_it_was_new(tmp_path: Path) -> None:
    body = "x = 1\n"
    h = hash_source(body)
    s = _store(tmp_path)
    assert s.add_blob(body, h) is True
    assert s.add_blob(body, h) is False


def test_body_round_trips_whole(tmp_path: Path) -> None:
    """Rule 8: nothing is shortened on the way in. Unicode, blank lines and all."""
    body = "# måler\n\n\nx = '→'\nlast = 2\n"
    h = hash_source(body)
    s = _store(tmp_path)
    s.add_blob(body, h)
    s.map_path("/p.py", h)
    s.commit()
    assert s.text("/p.py") == body


def test_missing_path_answers_none_not_empty(tmp_path: Path) -> None:
    """A map with no sidecar has no source; that is not the same as an empty file."""
    s = _store(tmp_path)
    assert s.text("/nothing.py") is None
    assert s.lines("/nothing.py", 1, 5) == []


def test_lines_are_one_based_and_clamped(tmp_path: Path) -> None:
    body = "a\nb\nc\n"
    h = hash_source(body)
    s = _store(tmp_path)
    s.add_blob(body, h)
    s.map_path("/p.py", h)
    assert s.lines("/p.py", 1, 2) == [(1, "a"), (2, "b")]
    assert s.lines("/p.py", 0, 99)[0] == (1, "a")
    assert s.lines("/p.py", 2, 2) == [(2, "b")]


# ------------------------------------------------------------------ capture --- #

def test_capture_never_reads_a_body_it_already_holds(tmp_path: Path) -> None:
    """The warm path. The file is not even on disk, and it still counts as cached.

    This is the whole reason capture is driven by the graph's hashes rather than by a
    second walk of the tree: a re-analysis with nothing changed must read no source.
    """
    body = "held = True\n"
    h = hash_source(body)
    s = _store(tmp_path)
    s.add_blob(body, h)
    s.commit()

    stats = capture({"/gone/from/disk.py": h}, s)
    assert stats == {"stored": 0, "cached": 1, "missing": 0}
    assert s.text("/gone/from/disk.py") == body


def test_capture_counts_an_unreadable_file_rather_than_raising(tmp_path: Path) -> None:
    """Ingest must never fail on a broken program -- but the shortfall is never silent."""
    s = _store(tmp_path)
    stats = capture({"/does/not/exist.py": "deadbeef"}, s)
    assert stats["missing"] == 1
    assert stats["stored"] == 0


def test_capture_reads_and_stores_a_real_file(tmp_path: Path) -> None:
    f = tmp_path / "real.py"
    f.write_text("value = 42\n", encoding="utf-8")
    s = _store(tmp_path)
    stats = capture({str(f): hash_source(f.read_text(encoding="utf-8"))}, s)
    assert stats["stored"] == 1
    assert s.text(str(f)) == "value = 42\n"


def test_prune_forgets_paths_but_keeps_bodies(tmp_path: Path) -> None:
    """A body no live path points at is still what an earlier revision was read from.

    Pruning blobs would make the sidecar current-state only, which is precisely what it
    must not be -- the temporal layers are the reason it exists.
    """
    body = "old = 1\n"
    h = hash_source(body)
    s = _store(tmp_path)
    s.add_blob(body, h)
    s.map_path("/deleted.py", h)
    s.commit()

    assert s.prune_missing([]) == 1
    assert s.counts()["paths"] == 0
    assert s.counts()["blobs"] == 1
    assert s.has_blob(h) is True


# ------------------------------------------------------------------ refusal --- #

def test_refuses_to_open_a_graph_as_a_source_sidecar(tmp_path: Path) -> None:
    """Rule 16, in the third store. The mistake cost a document store once."""
    other = tmp_path / "graph.db"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO meta VALUES ('kind', 'graph')")
    conn.commit()
    conn.close()

    with pytest.raises(WrongStoreKind) as exc:
        SourceStore(other)
    assert "not a source sidecar" in str(exc.value)


def test_a_reopen_keeps_everything(tmp_path: Path) -> None:
    """Rule 12 in reverse: a tool upgrade must not cost the sidecar its history.

    Every other store here is derived from the detector rules and must be discarded when
    they change. These are the file bodies -- no rule was applied to them, so no rule
    change can make them wrong, and dropping them would throw away the one artefact that
    cannot be rebuilt once the source tree has moved on.
    """
    body = "kept = True\n"
    h = hash_source(body)
    s = _store(tmp_path)
    s.add_blob(body, h)
    s.map_path("/kept.py", h)
    s.commit()
    s.close()

    again = SourceStore(tmp_path / "source.db")
    assert again.text("/kept.py") == body
    assert again.counts()["blobs"] == 1


def test_the_sidecar_has_no_way_to_drop_anything() -> None:
    """Asserted against the source, because the defect this guards is a future edit.

    Rule 20 was written after a read path quietly dropped every table it was asked about.
    The lesson did not transfer the first time because it was filed under the wrong
    heading, so here it is stated as a property of the file rather than of a code path: a
    store whose whole job is to be the thing that survives has no business owning a DROP.
    """
    text = Path(sourcedb.__file__).read_text(encoding="utf-8")
    lowered = text.lower()
    assert "drop table" not in lowered
    assert "delete from blobs" not in lowered
