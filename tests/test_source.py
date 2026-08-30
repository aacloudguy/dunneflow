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

    stats = capture({"gone/from/disk.py": h}, s, root=tmp_path)
    assert stats == {"stored": 0, "cached": 1, "missing": 0}
    assert s.text("gone/from/disk.py") == body


def test_capture_counts_an_unreadable_file_rather_than_raising(tmp_path: Path) -> None:
    """Ingest must never fail on a broken program -- but the shortfall is never silent."""
    s = _store(tmp_path)
    stats = capture({"does/not/exist.py": "deadbeef"}, s, root=tmp_path)
    assert stats["missing"] == 1
    assert stats["stored"] == 0


def test_capture_reads_and_stores_a_real_file(tmp_path: Path) -> None:
    f = tmp_path / "real.py"
    f.write_text("value = 42\n", encoding="utf-8")
    s = _store(tmp_path)
    # The key is relative and the root finds the bytes -- the two spellings a capture
    # legitimately holds at once, and the reason `capture` takes a root it never records.
    stats = capture({"real.py": hash_source(f.read_text(encoding="utf-8"))}, s,
                    root=tmp_path)
    assert stats["stored"] == 1
    assert s.text("real.py") == "value = 42\n"


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


# ---------------------------------------------------------------- revisions --- #

def _cap(s: SourceStore, path: str, body: str) -> str:
    h = hash_source(body)
    s.add_blob(body, h)
    s.map_path(path, h)
    s.commit()
    return h


def test_a_first_capture_opens_a_working_revision_with_an_instant(tmp_path: Path) -> None:
    """A snapshot has a name and a time. It used to have neither.

    The id and the state were one empty string, so there was nowhere to record when the
    bodies had been read, and re-analysing replaced the only snapshot there was.
    """
    s = _store(tmp_path)
    capture({"a.py": hash_source("x = 1\n")}, s, root=tmp_path)   # no such file: fine
    rows = s.revisions()
    assert len(rows) == 1
    assert rows[0]["state"] == sourcedb.STATE_WORKING
    assert rows[0]["stamped"] is True
    # Identity and instant agree for an ordinary capture; they only diverge on migration.
    assert rows[0]["revision"] == rows[0]["captured_at"] != ""


def test_sealing_moves_no_path_and_touches_no_body(tmp_path: Path) -> None:
    """The claim `seal()` makes about itself, asserted rather than described.

    Sealing is a change of state and nothing else -- which is the whole reason it is safe
    to do to a store whose job is to be the thing that survives.
    """
    s = _store(tmp_path)
    _cap(s, "/keep.py", "kept = True\n")
    before_paths = s.conn.execute("SELECT revision, path, hash FROM paths").fetchall()
    before_blobs = s.conn.execute("SELECT hash, body FROM blobs").fetchall()

    rev = s.seal(label="before the fresh pull")
    assert rev is not None

    after_paths = s.conn.execute("SELECT revision, path, hash FROM paths").fetchall()
    after_blobs = s.conn.execute("SELECT hash, body FROM blobs").fetchall()
    assert [tuple(r) for r in after_paths] == [tuple(r) for r in before_paths]
    assert [tuple(r) for r in after_blobs] == [tuple(r) for r in before_blobs]
    assert s.revisions()[0]["state"] == sourcedb.STATE_FOR_COMPARISON
    assert s.revisions()[0]["label"] == "before the fresh pull"


def test_a_sealed_snapshot_is_still_readable_before_the_next_analysis(
        tmp_path: Path) -> None:
    """The defect this was written from, found by asking what `seal` leaves behind.

    Sealing closes the working revision on purpose, so a read that resolved only to
    WORKING would answer "no source" for every file the sidecar holds -- and the window
    between sealing and the next analysis is exactly when someone opens the dashboard to
    see what they are about to replace.
    """
    s = _store(tmp_path)
    _cap(s, "/keep.py", "kept = True\n")
    s.seal()
    assert s.working_revision() is None          # nothing open to write into
    assert s.text("/keep.py") == "kept = True\n"  # ...and everything still readable
    assert list(sourcedb.iter_paths(s)) == ["/keep.py"]


def test_seal_then_capture_leaves_two_snapshots_that_disagree(tmp_path: Path) -> None:
    """The point of the whole exercise: a second point in time is now storable.

    Nothing reads it yet -- the time selector is the layer work. This asserts the store
    can hold the answer before anything is built to ask.
    """
    s = _store(tmp_path)
    _cap(s, "/f.py", "version = 1\n")
    old = s.seal(label="v1")
    new = s.open_working(at="2026-09-01T00:00:00Z")
    _cap_body = "version = 2\n"
    h = hash_source(_cap_body)
    s.add_blob(_cap_body, h)
    s.map_path("/f.py", h, revision=new)
    s.commit()

    assert old != new
    assert s.text("/f.py", revision=old) == "version = 1\n"
    assert s.text("/f.py", revision=new) == "version = 2\n"
    assert s.text("/f.py") == "version = 2\n"          # a read defaults to the working one
    assert {r["revision"] for r in s.revisions()} == {old, new}
    assert s.counts()["blobs"] == 2 and s.counts()["mapped"] == 2
    # Rule 32: the count that is printed as "files" is this revision's, not both revisions'.
    assert s.counts()["paths"] == 1


def test_a_read_only_open_reports_an_un_stamped_sidecar_and_never_stamps_it(
        tmp_path: Path) -> None:
    """Rule 20, in the store that must survive everything.

    A sidecar written before revisions existed holds its paths under the empty revision.
    Opening it to *read* must leave it exactly as it is and say what it found; only a
    writable open -- `analyze`, or `dunneflow revisions --seal` -- may migrate it.
    """
    db = tmp_path / "source.db"
    s = SourceStore(db)
    body = "legacy = True\n"
    h = hash_source(body)
    s.add_blob(body, h)
    s.conn.execute("INSERT INTO paths(revision, path, hash) VALUES('', '/old.py', ?)", (h,))
    s.conn.execute("DELETE FROM revisions")
    s.commit()
    s.close()

    ro = SourceStore(db, writable=False)
    rows = ro.revisions()
    assert [r["stamped"] for r in rows] == [False]
    assert rows[0]["revision"] == ""
    assert "before revisions were recorded" in rows[0]["note"]
    assert ro.text("/old.py") == body                     # readable, and unrepaired
    assert ro.conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 0
    with pytest.raises(PermissionError):
        ro.seal()
    # And the migration itself refuses, rather than being merely unreachable. `__init__`
    # returns before calling it on a read-only open, so this can never fire today -- which
    # is exactly why it is asserted: an unreachable guard that returns None quietly is one
    # a future caller trips without noticing. Rule 42.
    with pytest.raises(PermissionError):
        ro._stamp_legacy_paths()
    assert ro.conn.execute("SELECT COUNT(*) FROM revisions").fetchone()[0] == 0
    ro.close()

    # ...and a writable open migrates it, losing no path and inventing no instant.
    rw = SourceStore(db)
    rows = rw.revisions()
    assert [r["stamped"] for r in rows] == [True]
    assert rows[0]["state"] == sourcedb.STATE_WORKING
    assert rows[0]["revision"] != ""
    assert rows[0]["captured_at"] == ""            # not known here, and not invented
    assert rw.text("/old.py") == body


def test_a_stated_instant_fills_an_unknown_one_and_never_overwrites_a_recorded_one(
        tmp_path: Path) -> None:
    """Rule 13. Provenance may be supplied where there is none; it may not be rewritten."""
    s = _store(tmp_path)
    _cap(s, "/a.py", "a = 1\n")
    recorded = s.revisions()[0]["captured_at"]
    assert recorded
    s.seal(at="1999-01-01T00:00:00Z")
    assert s.revisions()[0]["captured_at"] == recorded   # the real one stands

    other = SourceStore(tmp_path / "two" / "source.db")
    h = hash_source("b = 1\n")
    other.add_blob("b = 1\n", h)
    other.conn.execute("INSERT INTO paths(revision, path, hash) VALUES('', '/b.py', ?)", (h,))
    other.conn.execute("DELETE FROM revisions")
    other.commit()
    other.close()
    again = SourceStore(tmp_path / "two" / "source.db")      # migrates: instant unknown
    assert again.revisions()[0]["captured_at"] == ""
    again.seal(at="2026-08-29 17:02 UTC")
    assert again.revisions()[0]["captured_at"] == "2026-08-29 17:02 UTC"


def test_seal_refuses_a_state_it_does_not_know(tmp_path: Path) -> None:
    """A state is a small closed set. An unknown one is a typo that would read as a fact."""
    s = _store(tmp_path)
    _cap(s, "/a.py", "a = 1\n")
    with pytest.raises(ValueError, match="not a revision state"):
        s.seal(state="ARCHIVED")


def test_sealing_twice_says_so_rather_than_sealing_nothing(tmp_path: Path) -> None:
    """"Already sealed" and "nothing here" are different answers, so they are said apart."""
    s = _store(tmp_path)
    _cap(s, "/a.py", "a = 1\n")
    s.seal()
    with pytest.raises(ValueError, match="already sealed"):
        s.seal()

    empty = SourceStore(tmp_path / "empty" / "source.db")
    assert empty.seal() is None
