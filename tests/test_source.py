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


# --------------------------------------------------------------------------- #
# The tree a version was read from — the leaf, and only the leaf.
# --------------------------------------------------------------------------- #


def test_a_revision_records_the_leaf_of_the_tree_it_was_read_from(tmp_path):
    """Two versions of one program are two directories, so the leaf is what names them.

    Only the leaf. The path that led to it is one machine's layout and is deliberately
    recorded nowhere (rule 60); the leaf is a name somebody chose for the source, it
    travels with the map, and it survives a move.
    """
    s = SourceStore(tmp_path / "source.db")
    rev = s.open_working(tree="comitia-2026-08-26")
    s.commit()
    rows = {r["revision"]: r for r in s.revisions()}
    assert rows[rev]["tree"] == "comitia-2026-08-26"
    s.close()


def test_the_tree_is_never_a_path(tmp_path):
    """A separator here would mean a path had been stored under a column meaning a name.

    The store cannot police what it is handed, so this pins the *caller*: `cmd_analyze`
    passes `target.name`, and a change that passed `target` instead would put an absolute
    path into a map built to be handed over — silently, since it would look like a longer
    label.
    """
    import re
    src = Path("src/dunneflow/cli.py").read_text(encoding="utf-8")
    call = re.search(r"source\.open_working\((.*?)\)", src, re.S)
    assert call, "cmd_analyze no longer opens a working revision"
    assert "tree=tree_leaf" in call.group(1).replace(" ", ""), (
        f"the tree passed to open_working is {call.group(1)!r}, not the identifying leaf"
    )
    # And that leaf must be the **package root's**, not the analysed directory's.
    # `target.name` for a `src/` layout is the string `src`, which names every src-layout
    # program ever analysed and therefore identifies none of them. Invisible to every toy
    # fixture here, because none of them has a `src/` to be wrong about.
    assert "tree_leaf = pkg_root.name" in src, (
        "the recorded tree is no longer the package root's leaf -- for a src/ layout that "
        "records the string 'src' for every program"
    )


def test_an_older_sidecar_gains_the_column_and_loses_nothing(tmp_path):
    """`CREATE TABLE IF NOT EXISTS` does nothing to a table that already exists.

    This is the store that is never rebuilt (rule 25), so there is no re-analysis that
    would fix a missing column. The migration is **add only** — it must not touch a row,
    and a version captured before the column existed keeps an empty tree, which is the
    honest answer rather than a guessed one.
    """
    db = tmp_path / "source.db"
    s = SourceStore(db)
    rev = s.open_working(tree="original")
    s.commit()
    s.close()

    # Put the table back the way it looked before `tree` existed, rows and all.
    conn = sqlite3.connect(db)
    conn.executescript(
        "ALTER TABLE revisions RENAME TO revisions_old;"
        "CREATE TABLE revisions ("
        "  revision TEXT PRIMARY KEY, state TEXT NOT NULL, captured_at TEXT NOT NULL,"
        "  label TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '');"
        "INSERT INTO revisions SELECT revision, state, captured_at, label, note"
        "  FROM revisions_old;"
        "DROP TABLE revisions_old;"
    )
    conn.commit()
    conn.close()
    assert "tree" not in {
        r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(revisions)")
    }

    reopened = SourceStore(db)
    rows = {r["revision"]: r for r in reopened.revisions()}
    assert rev in rows, "the migration lost a row"
    assert rows[rev]["tree"] == "", (
        "a version captured before the column existed was given a tree it never had"
    )
    reopened.close()


def test_a_read_only_open_of_an_older_sidecar_still_lists_its_revisions(tmp_path):
    """The defect this was written from, and it reached the served JSON.

    A read may refuse but may never repair (rule 20), so a read-only open does not run
    the additive migration — and the dashboard opens the sidecar read-only every time it
    starts. Naming `tree` unconditionally made the SELECT raise, a blanket `except`
    turned that into "no rows", and a two-revision program was served as holding **no
    revisions at all**: state, label, capture instant and file counts all blank, with no
    error anywhere.

    That is rule 49 exactly — a fallback yielding a plausible value hides the failure it
    was written for — and it consumed the evidence on the way past. Asserted on the
    *values*, not on the row count, because an empty list and a list of empty rows were
    both available and only one of them is the defect.
    """
    db = tmp_path / "source.db"
    s = SourceStore(db)
    rev = s.open_working(tree="a-tree")
    s.seal(label="a label")
    s.commit()
    s.close()

    # Put the table back the way a sidecar written before `tree` existed holds it.
    conn = sqlite3.connect(db)
    conn.executescript(
        "ALTER TABLE revisions RENAME TO revisions_old;"
        "CREATE TABLE revisions ("
        "  revision TEXT PRIMARY KEY, state TEXT NOT NULL, captured_at TEXT NOT NULL,"
        "  label TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '');"
        "INSERT INTO revisions SELECT revision, state, captured_at, label, note"
        "  FROM revisions_old;"
        "DROP TABLE revisions_old;"
    )
    conn.commit()
    conn.close()

    reader = SourceStore(db, writable=False)
    rows = reader.revisions()
    assert [r["revision"] for r in rows] == [rev], "the reader lost the revision entirely"
    assert rows[0]["label"] == "a label", "the reader answered out of an empty hole"
    assert rows[0]["state"] == sourcedb.STATE_FOR_COMPARISON
    assert rows[0]["tree"] == "", "a column this sidecar never had was filled in anyway"
    # And it repaired nothing on the way past (rule 20).
    assert "tree" not in {
        r[1] for r in sqlite3.connect(db).execute("PRAGMA table_info(revisions)")
    }, "a read-only open added a column — a read may refuse, but never repair"
    reader.close()


# ------------------------------------------------ the document sidecar --- #

def test_the_two_sidecars_refuse_each_other(tmp_path: Path) -> None:
    """Rule 16, and the pair that makes it bite rather than merely apply.

    `SourceStore` and `DocSourceStore` have **identical schemas**, which is the point: a body
    is a body, and blobs, paths, revisions and the inflate cache all work the same on prose.
    It is also why the stamp is the only thing between them. A graph refuses by shape; these
    two can only refuse by name, and opening one as the other would not error -- it would
    succeed and claim the wrong corpus.
    """
    code, docs = tmp_path / "source.db", tmp_path / "docsource.db"
    SourceStore(code).close()
    sourcedb.DocSourceStore(docs).close()

    with pytest.raises(WrongStoreKind) as one:
        sourcedb.DocSourceStore(code)
    assert "not a document sidecar" in str(one.value)

    with pytest.raises(WrongStoreKind) as two:
        SourceStore(docs)
    assert "not a source sidecar" in str(two.value)

    # Each still opens as itself, or the guard has cost the thing it was protecting.
    SourceStore(code).close()
    sourcedb.DocSourceStore(docs).close()


def test_a_sidecar_that_adopts_a_revision_can_be_read_back(tmp_path: Path) -> None:
    """Bodies nothing can name are bodies with no reader.

    `open_working` mints an identity from the clock, which is right for `source.db` -- it is
    the authority the graph and the document store are named after. A second sidecar is not
    that authority, and the first build of this one showed what happens without a way to say
    so: `capture` wrote 2,064 path rows under the right revision and `revisions` stayed
    **empty**, so `resolve_revision(None)` fell through to `LEGACY_REVISION` and the analyze
    line read *"2,056 bodies for 0 paths"*. Every row was present. Nothing said the snapshot
    existed, and every read resolves through that.
    """
    path = tmp_path / "docsource.db"
    store = sourcedb.DocSourceStore(path)
    rev = store.adopt_revision("2026-01-01T00:00:00Z", tree="a-tree")
    store.add_blob("# Title\n\nbody\n", "hash-1")
    store.map_path("README.md", "hash-1", revision=rev)
    store.commit()
    assert store.counts()["paths"] == 1, (
        "the revision was adopted and the path count still resolves somewhere else"
    )
    store.close()

    back = sourcedb.DocSourceStore(path, writable=False)
    assert back.text("README.md") == "# Title\n\nbody\n", (
        "a reader told nothing cannot resolve to the adopted revision"
    )
    assert [r["revision"] for r in back.revisions()] == ["2026-01-01T00:00:00Z"]
    assert back.revisions()[0]["tree"] == "a-tree"
    back.close()


def test_adopting_the_same_revision_twice_reuses_it(tmp_path: Path) -> None:
    """Re-analysing one snapshot must not leave two half-filled ones behind.

    The property `open_working` has, for the reason it has it: `analyze` is run again after
    every edit. An empty `tree` is filled in, and a recorded one is **re-stamped** -- the
    half this asserted the wrong way round until renaming the checkout showed what it cost:
    `source.db` moved to the new leaf and `docsource.db` kept the old one, so one snapshot
    was recorded as read from two different trees.
    """
    store = sourcedb.DocSourceStore(tmp_path / "docsource.db")
    store.adopt_revision("2026-01-01T00:00:00Z")
    store.adopt_revision("2026-01-01T00:00:00Z", tree="named-later")
    store.commit()
    rows = store.revisions()
    assert len(rows) == 1, f"adopting twice left {len(rows)} revisions"
    assert rows[0]["tree"] == "named-later", "an empty tree was not filled in"

    # And the tree the reader has just analysed from wins over the one recorded before it.
    store.adopt_revision("2026-01-01T00:00:00Z", tree="renamed")
    store.commit()
    rows = store.revisions()
    assert len(rows) == 1, f"re-adopting left {len(rows)} revisions"
    assert rows[0]["tree"] == "renamed", "a recorded tree was not re-stamped"
    store.close()


def test_capture_fills_a_document_sidecar_from_the_doc_stores_hashes(tmp_path: Path) -> None:
    """The wiring `analyze` uses, end to end and without `analyze`.

    `capture()` needs a `dict[str, str]` and a root; `DocStore.known_hashes()` returns exactly
    that. So the document sidecar needed no new capture path, no change to the walk, and no
    body carried back out of the extraction subprocesses -- the bodies are re-read from disk
    by the same hashes the scan just recorded.
    """
    tree = tmp_path / "tree"
    (tree / "docs").mkdir(parents=True)
    (tree / "README.md").write_text("# Read me\n", encoding="utf-8")
    (tree / "docs" / "a.md").write_text("# A\n", encoding="utf-8")

    hashes = {
        "README.md": hash_source("# Read me\n"),
        "docs/a.md": hash_source("# A\n"),
    }
    store = sourcedb.DocSourceStore(tmp_path / "docsource.db")
    store.adopt_revision("2026-01-01T00:00:00Z")
    stats = capture(hashes, store, root=tree, revision="2026-01-01T00:00:00Z")
    assert stats == {"stored": 2, "cached": 0, "missing": 0}
    assert store.text("docs/a.md") == "# A\n"
    # And again: a body already held is never re-read.
    again = capture(hashes, store, root=tree, revision="2026-01-01T00:00:00Z")
    assert again["stored"] == 0 and again["cached"] == 2
    store.close()


def test_a_sidecar_is_stamped_the_moment_it_exists(tmp_path: Path) -> None:
    """A store created and closed with no write in between must still know what it is.

    `executescript` autocommits the schema; the three `set_meta` calls beside it do not, and
    `close()` closes without committing. So the file landed with all four tables and an
    **empty `meta`** -- no kind, no schema version, no `paths=relative` marker -- and rule 16
    was bypassed on it entirely: `_refuse_wrong_kind` cannot tell "no kind row" from "fresh
    database", so the wrong class opened it and **restamped** it.

    Found by building the second sidecar and asserting the two refuse each other. The pair is
    what made it visible: with one kind there was nothing to be mistaken for. Production never
    reached it, because `analyze` always follows with a `capture()` that commits -- the guard
    was intact everywhere it was exercised, which is the definition of the hazard.
    """
    path = tmp_path / "source.db"
    SourceStore(path).close()

    meta = dict(sqlite3.connect(path).execute("SELECT key, value FROM meta"))
    assert meta.get("kind") == "source", (
        f"a created-and-closed sidecar is unstamped ({meta!r}), so anything may open it"
    )
    assert meta.get(sourcedb.META_PATHS) == sourcedb.PATHS_RELATIVE, (
        "the paths marker did not survive either -- rule 60's marker is not inferred, so "
        "losing it means a migration cannot tell an unmigrated store from a migrated one"
    )

    # And the guard now bites on exactly that file.
    with pytest.raises(WrongStoreKind):
        sourcedb.DocSourceStore(path)


def test_analyze_lands_the_document_bodies_under_the_graphs_own_revision() -> None:
    """Two sidecars describing one analysis must name the same snapshot.

    Pinned on the *caller*, as `open_working`'s tree is above, because the store cannot
    police what it is handed. `source.db` is the authority on the revision id -- the graph
    and the document store are named after it -- so the document sidecar must **adopt** that
    id rather than mint one from its own clock.

    Without the adopt call the capture still writes every path row, under the right revision,
    and `revisions` stays empty; `resolve_revision(None)` then falls through to
    `LEGACY_REVISION` and no read resolves. On Lictores that read *"2,056 bodies for 0
    paths"* with all 2,064 rows present.
    """
    import re
    src = Path("src/dunneflow/cli.py").read_text(encoding="utf-8")
    adopt = re.search(r"docsource\.adopt_revision\((.*?)\)", src)
    assert adopt, (
        "analyze no longer adopts a revision for the document sidecar, so its bodies are "
        "stored under a snapshot the store has no row for and no reader can resolve"
    )
    assert "revision" in adopt.group(1), (
        f"the document sidecar is adopting {adopt.group(1)!r} rather than the graph's own "
        "revision, so the two sidecars describe different snapshots of one analysis"
    )
    # And it must be the same variable the graph and the document store are named from.
    assert "capture_source(doc_store.known_hashes(), docsource," in src.replace("\n", " ").replace(
        "                                           ", ""), (
        "the document capture is no longer driven by the document store's own hashes"
    )
