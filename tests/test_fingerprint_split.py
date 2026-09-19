"""Rule 12, per language: editing one reader must not discard another's facts.

`tests/test_incremental.py` holds the membership assertions — which file is in which key.
This holds the behaviour those keys exist to produce, which is a different question and
the one that can be true of a wrong list: a core key and a language key that both moved
would pass every membership test here and still drop the whole map.

Every stamp is moved by **monkeypatching the fingerprint**, never by editing a file on
disk. Editing `extractors/python/extract.py` to test this would discard every graph on the
machine, sealed snapshots included, which is the cost rule 12's own note warns about.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow import ingest, walk
from dunneflow import store as store_mod
from dunneflow.detectors import lang_fingerprint
from dunneflow.store import StaleGraphError, Store


def _tree(root: Path) -> None:
    (root / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / "n.py").write_text("def g():\n    return 2\n", encoding="utf-8")


def _read(db: Path, sql: str) -> list[tuple]:
    st = Store(db, writable=False)
    try:
        return [tuple(r) for r in st.conn.execute(sql)]
    finally:
        st.close()


def _analysed(tmp_path: Path) -> Path:
    tree = tmp_path / "tree"
    tree.mkdir()
    _tree(tree)
    db = tmp_path / "graph.db"
    st = Store(db)
    try:
        walk.analyze_tree(tree, st)
    finally:
        st.close()
    return db


# ------------------------------------------------------------------ the stamp --- #

def test_every_row_says_which_reader_produced_it(tmp_path):
    db = _analysed(tmp_path)
    rows = _read(db, "SELECT path, lang, extractor FROM files ORDER BY path")
    want = lang_fingerprint("python")
    assert [r[2] for r in rows] == [want, want]
    # A version **and** a hash: the version is what the reader says it is, the hash is
    # what it is. A label alone does not move when somebody edits the bundle (rule 30).
    # The version is read off the manifest rather than spelled here: a literal would fail
    # every time a reader is versioned, which is a test about nothing (rule 43).
    declared = ingest.PLUGINS["python"].manifest.version
    assert want.startswith(f"{declared}:") and len(want.split(":", 1)[1]) == 16


def test_the_core_stamp_and_the_language_stamp_are_different_questions():
    from dunneflow.detectors import core_fingerprint

    assert core_fingerprint() != lang_fingerprint("python")
    # The core key has no language in it at all, so it cannot move when one is edited.
    from dunneflow.detectors import core_extraction_inputs

    assert not any("extractors" in p.parts for p in core_extraction_inputs())


# --------------------------------------------------------------- the discard --- #

def test_a_changed_reader_re_reads_its_own_language_and_only_that(tmp_path, monkeypatch):
    """The whole of the chunk, as a behaviour.

    A second language cannot be analysed here — there is one reader — so the claim is
    made the other way round: the rows of a language whose stamp moved are dropped, and
    the map's core stamp, its meta and its other tables are not.
    """
    db = _analysed(tmp_path)
    before = _read(db, "SELECT COUNT(*) FROM routines")[0][0]
    assert before >= 2

    monkeypatch.setattr(store_mod, "lang_fingerprint",
                        lambda lang: "9.9.9:ffffffffffffffff")
    st = Store(db)
    try:
        assert st.reread == {"python": 2}, "the changed reader's files were not dropped"
        assert not st.rebuilt, "the whole graph was discarded for one reader's change"
        assert st.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
        assert st.get_meta("kind") == "graph", "meta went with the language's rows"
    finally:
        st.close()


def test_an_unchanged_reader_drops_nothing(tmp_path):
    db = _analysed(tmp_path)
    st = Store(db)
    try:
        assert st.reread == {}
        assert st.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 2
    finally:
        st.close()


def test_a_language_this_build_cannot_read_is_left_alone(tmp_path):
    """Refusing a map over a plugin somebody uninstalled would refuse it for ever.

    Its rows cannot be re-read and cannot be checked; the walk already says that language
    was not read this time, which is the fact somebody can act on (rule 89).

    *This said `typescript` until the TypeScript reader shipped*, at which point the
    row stopped being one this build cannot read and started being one it can — so
    the refusal fired, correctly, and the test was measuring the wrong thing. `go` is
    a language nothing here claims, which is what the case is about.
    """
    db = _analysed(tmp_path)
    st = Store(db)
    try:
        st.conn.execute(
            "INSERT INTO files(path, lang, module, content_hash, extractor)"
            " VALUES('a.go', 'go', 'a', 'h', '0.1.0:aaaaaaaaaaaaaaaa')")
        st.conn.commit()
    finally:
        st.close()
    assert Store(db, writable=False).stale_languages() == {}
    st = Store(db)
    try:
        assert st.reread == {}
        assert st.conn.execute(
            "SELECT COUNT(*) FROM files WHERE lang='go'").fetchone()[0] == 1
    finally:
        st.close()


# ---------------------------------------------------------------- the refusal --- #

def test_a_reader_refuses_a_language_it_did_not_produce(tmp_path, monkeypatch):
    """A read may refuse, but it may never repair (rule 20).

    And the sentence names the language, because *this map is stale* over a Python map
    whose forty TypeScript files are the problem sends somebody looking in the wrong
    place (rule 89).
    """
    db = _analysed(tmp_path)
    monkeypatch.setattr(store_mod, "lang_fingerprint",
                        lambda lang: "9.9.9:ffffffffffffffff")
    with pytest.raises(StaleGraphError) as exc:
        Store(db, writable=False)
    said = str(exc.value)
    assert "python" in said
    assert "only the language that changed" in said
    # It must not have repaired anything on the way past.
    monkeypatch.undo()
    assert _read(db, "SELECT COUNT(*) FROM files")[0][0] == 2


def test_a_map_written_before_the_column_existed_says_nothing_rather_than_stale(tmp_path):
    """Three states, never two (rule 63). A migrated store has no such column at all."""
    db = _analysed(tmp_path)
    st = Store(db)
    try:
        # The table as it was shaped before the column, rebuilt rather than dropped:
        # SQLite re-parses the stored CREATE statement for `DROP COLUMN`, and this one
        # carries the prose that explains the column.
        st.conn.executescript("""
            CREATE TABLE files_old (
                path TEXT PRIMARY KEY, lang TEXT NOT NULL, module TEXT NOT NULL,
                content_hash TEXT NOT NULL, doc TEXT NOT NULL DEFAULT '',
                errors TEXT NOT NULL DEFAULT '[]');
            INSERT INTO files_old
                SELECT path, lang, module, content_hash, doc, errors FROM files;
            DROP TABLE files;
            ALTER TABLE files_old RENAME TO files;
        """)
        st.conn.commit()
        assert st.language_stamps() == {}
        assert st.stale_languages() == {}
    finally:
        st.close()


# ----------------------------------------------------------------- the plugin --- #

def test_a_plugin_that_runs_here_must_say_where_its_reader_lives(tmp_path):
    """A reader whose bytes are in no key is rule 12 unenforced for every fact it makes."""
    manifest = tmp_path / "plugin.json"
    manifest.write_text(
        f'{{"lang": "x", "protocol": 1, "schema_version": {ingest.SCHEMA_VERSION},'
        f' "in_process": true, "fingerprint": ["plugin.json"],'
        f' "discovery": {{"suffixes": [".x"]}}}}', encoding="utf-8")
    with pytest.raises(ingest.PluginRefused) as exc:
        ingest.read_manifest(manifest)
    assert "where its reader lives" in str(exc.value)


def test_a_plugin_that_names_no_fingerprint_files_is_refused(tmp_path):
    manifest = tmp_path / "plugin.json"
    manifest.write_text(
        f'{{"lang": "x", "protocol": 1, "schema_version": {ingest.SCHEMA_VERSION},'
        f' "discovery": {{"suffixes": [".x"]}}}}', encoding="utf-8")
    with pytest.raises(ingest.PluginRefused) as exc:
        ingest.read_manifest(manifest)
    assert "cache key" in str(exc.value)


def test_the_manifests_claim_about_running_here_is_checked_against_the_code():
    """A manifest is a label; `_IN_PROCESS` is the identity (rule 30)."""
    src = Path(ingest.__file__).read_text(encoding="utf-8")
    assert "_IN_PROCESS" in src and "in_process !=" in src
    assert ingest.PLUGINS["python"].manifest.in_process is True
