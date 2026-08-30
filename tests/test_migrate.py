"""Paths are stored relative, and the migration that made the existing ones relative.

The defect these were written from: every path in all three stores was absolute. That
leaks one machine's directory layout to anyone the stores are handed to, breaks when a
tree is moved, breaks when a program directory is copied to another machine, and -- worst
for this tool -- gives the same file two unrelated keys across two revisions read from two
different trees, so nothing could pair a file with itself across two points in time.

Every guard here was run against that defect **and** against a half-working version, per
rule 37: a check that has never failed is a claim nobody has tested.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from dunneflow import migrate, revisions
from dunneflow.schema import hash_source
from dunneflow.sourcedb import SourceStore, capture
from dunneflow.store import StaleGraphError, Store
from dunneflow.walk import analyze_tree

PROG = '''"""A tiny program."""
import os


def go(path: str) -> str:
    return os.path.join(path, "x")
'''


def _tree(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pkg").mkdir(exist_ok=True)
    (root / "pkg" / "mod.py").write_text(PROG, encoding="utf-8")
    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    return root


# --------------------------------------------------------------------------- #
# Nothing absolute survives analysis
# --------------------------------------------------------------------------- #


def _absolute_paths(db: Path, exempt: dict[str, str]) -> dict[str, int]:
    """Every path column in one store that still holds an absolute value.

    **Derived from the schema, never a hand-kept list.** A list of twenty columns drifts
    the moment a table is added, and a key that silently omits one is the silent no-op
    this project keeps paying for (rule 36). Assert the total, not the cases (rule 18).
    """
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        out: dict[str, int] = {}
        for tbl, col in migrate.path_columns(conn, exempt):
            n = conn.execute(
                f'SELECT COUNT(*) FROM "{tbl}" WHERE "{col}" LIKE ?', ("/%",)
            ).fetchone()[0]
            if n:
                out[f"{tbl}.{col}"] = int(n)
        return out
    finally:
        conn.close()


def test_no_path_column_holds_an_absolute_path_after_analysis(tmp_path: Path) -> None:
    """The whole point, asserted over every column the schema declares."""
    root = _tree(tmp_path / "tree")
    db = tmp_path / "graph.db"
    store = Store(db)
    analyze_tree(root, store)
    store.close()
    assert _absolute_paths(db, migrate.GRAPH_EXEMPT) == {}


def test_every_path_column_is_either_migrated_or_exempt_with_a_reason(
        tmp_path: Path) -> None:
    """An unknown column called `path` is a question, not a default (rule 36).

    `headings.path` holds a trail of parent headings, not a filesystem path, and a
    migration that rewrote every column called `path` would have been reading a name as a
    meaning (rule 5). This fails when a table is added whose path column nobody classified,
    which is the only way the migration can silently leave something absolute.
    """
    from dunneflow.docstore import DocStore

    store = Store(tmp_path / "graph.db")
    docs = DocStore(tmp_path / "docs.db")
    for conn, exempt in ((store.conn, migrate.GRAPH_EXEMPT),
                         (docs.conn, migrate.DOCS_EXEMPT)):
        declared = set()
        for tbl in [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%'")]:
            for col in [r[1] for r in conn.execute(f'PRAGMA table_info("{tbl}")')]:
                if col in ("file", "path"):
                    declared.add(f"{tbl}.{col}")
        handled = {f"{t}.{c}" for t, c in migrate.path_columns(conn, exempt)} | set(exempt)
        assert declared == handled, f"unclassified path column(s): {declared - handled}"
    store.close()
    docs.close()


# --------------------------------------------------------------------------- #
# A moved tree is a cache hit
# --------------------------------------------------------------------------- #


def test_moving_the_tree_is_a_cache_hit_and_prunes_nothing(tmp_path: Path) -> None:
    """Tom's second reason, asserted rather than described.

    Keyed on the absolute path this was `parsed 628, removed 628` on the real corpus --
    a full re-parse and a churned graph for a move that changed no byte. Measured both
    ways before this guard was written: 0 cache hits then, 628 now.
    """
    a = _tree(tmp_path / "a")
    b = _tree(tmp_path / "b")          # the same bytes at a different absolute path
    db = tmp_path / "graph.db"

    store = Store(db)
    first = analyze_tree(a, store)
    assert first.parsed == first.found > 0 and first.cached == 0

    second = analyze_tree(b, store)
    assert second.cached == second.found == first.found
    assert second.parsed == 0
    assert second.removed == 0, "a move must not read as every file being deleted"
    store.close()


# --------------------------------------------------------------------------- #
# Two revisions, two trees, one file
# --------------------------------------------------------------------------- #


def test_two_revisions_read_from_two_trees_pair_by_path(tmp_path: Path) -> None:
    """The question two revisions exist to ask, and the one the old key could not answer.

    Absolute keys made this 0 identical / everything added / everything removed, because
    `<A>/pkg/mod.py` and `<B>/pkg/mod.py` are different strings. The assertion is that the
    *unchanged* file pairs and the *changed* one is seen to have changed.
    """
    a, b = _tree(tmp_path / "old"), _tree(tmp_path / "new")
    (b / "pkg" / "mod.py").write_text(PROG + "\n\ndef extra() -> None:\n    pass\n",
                                      encoding="utf-8")
    src = SourceStore(tmp_path / "source.db")

    graph_a = Store(tmp_path / "a.db")
    analyze_tree(a, graph_a)
    rev_a = src.open_working()
    capture(graph_a.known_hashes(), src, root=a, revision=rev_a)
    src.seal()

    graph_b = Store(tmp_path / "b.db")
    analyze_tree(b, graph_b)
    rev_b = src.open_working()
    capture(graph_b.known_hashes(), src, root=b, revision=rev_b)

    rows = dict(src.conn.execute(
        "SELECT p.path, COUNT(DISTINCT p.hash) FROM paths p"
        " WHERE p.revision IN (?, ?) GROUP BY p.path", (rev_a, rev_b)).fetchall())
    assert "pkg/__init__.py" in rows and "pkg/mod.py" in rows
    assert rows["pkg/__init__.py"] == 1, "an unchanged file is one body at one path"
    assert rows["pkg/mod.py"] == 2, "an edited file is two bodies at the same path"
    graph_a.close()
    graph_b.close()


# --------------------------------------------------------------------------- #
# The migration
# --------------------------------------------------------------------------- #


def _make_legacy(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    """A program directory exactly as one written before paths went relative.

    Built by analysing normally and then putting it *back*: paths re-absolutised, the root
    recorded, the marker removed and the old fingerprint stamped. Faithful rather than
    hand-written, so the guard runs against the shape the real stores actually had.
    """
    root = _tree(tmp_path / "tree")
    out = tmp_path / "out"
    out.mkdir()
    # The sidecar names the revision and the graph is named after it, in that order --
    # exactly as `cmd_analyze` does. Taking the id from anywhere else gives a sidecar and
    # a graph that disagree about which snapshot they are, which is not a state `analyze`
    # can produce and not one worth writing a guard against.
    src = SourceStore(out / "source.db")
    rev = src.open_working()
    db = revisions.db_path(out, revisions.GRAPH, rev)

    store = Store(db)
    store.set_meta("revision", rev)
    analyze_tree(root, store)
    capture(store.known_hashes(), src, root=root, revision=rev)
    store.close()
    src.close()

    conn = sqlite3.connect(db)
    for tbl, col in migrate.path_columns(conn, migrate.GRAPH_EXEMPT):
        conn.execute(f'UPDATE "{tbl}" SET "{col}" = ? || "{col}"', (str(root) + "/",))
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('source_root',?)",
                 (str(root),))
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('extractor',?)",
                 (migrate.PREVIOUS_CODE_EXTRACTOR,))
    conn.execute("DELETE FROM meta WHERE key = ?", (migrate.META_PATHS,))
    conn.commit()
    conn.close()

    sconn = sqlite3.connect(out / "source.db")
    sconn.execute('UPDATE paths SET path = ? || path', (str(root) + "/",))
    sconn.execute("DELETE FROM meta WHERE key = ?", (migrate.META_PATHS,))
    sconn.commit()
    sconn.close()
    return out, db, root, rev


def test_a_reader_refuses_an_unmigrated_store_names_the_fix_and_repairs_nothing(
        tmp_path: Path) -> None:
    """Rule 20, and the half that is easy to forget: it must not repair on the way past.

    Two different fixes exist and naming the wrong one is expensive -- a sealed snapshot
    whose tree is gone cannot be re-analysed, so a reader told to `analyze` is a reader
    told to do the impossible.
    """
    out, db, _, _rev = _make_legacy(tmp_path)
    before = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = before.execute("SELECT COUNT(*) FROM routines").fetchone()[0]
    before.close()
    assert rows > 0

    with pytest.raises(StaleGraphError) as exc:
        Store(db, writable=False)
    assert "migrate" in str(exc.value), "the refusal must name the fix that applies"
    assert "analyze" not in str(exc.value), "re-analysis is the wrong fix for this one"

    after = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    assert after.execute("SELECT COUNT(*) FROM routines").fetchone()[0] == rows
    after.close()


def test_the_migration_makes_every_path_relative_and_keeps_the_facts(
        tmp_path: Path) -> None:
    out, db, root, _rev = _make_legacy(tmp_path)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    facts = conn.execute("SELECT COUNT(*) FROM routines").fetchone()[0]
    conn.close()
    assert _absolute_paths(db, migrate.GRAPH_EXEMPT), "the fixture must start absolute"

    report = migrate.migrate_program(out)
    assert report.total > 0

    assert _absolute_paths(db, migrate.GRAPH_EXEMPT) == {}
    assert _absolute_paths(out / "source.db", migrate.SOURCE_EXEMPT) == {}

    reopened = Store(db, writable=False)          # re-stamped, so a reader may open it
    assert reopened.query("SELECT COUNT(*) AS n FROM routines", ())[0]["n"] == facts
    # The key is *absent*, not blank. A blank value is still a row saying "we looked and
    # the answer is nothing", which is a different claim from "this is not recorded".
    assert reopened.query(
        "SELECT COUNT(*) AS n FROM meta WHERE key = 'source_root'", ())[0]["n"] == 0
    reopened.close()


def test_migrating_twice_is_a_no_op_rather_than_a_second_strip(tmp_path: Path) -> None:
    """The failure this prevents: a second pass treating `pkg/mod.py` as absolute again.

    Run against a half-working version that reported success without setting the marker,
    where the second pass silently rewrote relative paths a second time.
    """
    out, db, _, _rev = _make_legacy(tmp_path)
    migrate.migrate_program(out)
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    paths = sorted(r[0] for r in conn.execute("SELECT path FROM files"))
    conn.close()

    again = migrate.migrate_program(out)
    assert all(s.already for s in again.stores)
    assert again.total == 0

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    assert sorted(r[0] for r in conn.execute("SELECT path FROM files")) == paths
    conn.close()


def test_the_migration_refuses_a_fingerprint_it_cannot_speak_for(tmp_path: Path) -> None:
    """It re-stamps `extractor`, so it must only ever do that for one prior state.

    A store written by some other version is stale for reasons this migration knows
    nothing about; re-stamping it would vouch for changes it did not make.
    """
    out, db, _, _rev = _make_legacy(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('extractor','9:deadbeef')")
    conn.commit()
    conn.close()

    with pytest.raises(migrate.MigrationRefused) as exc:
        migrate.migrate_program(out)
    assert "9:deadbeef" in str(exc.value)
    assert "analyze" in str(exc.value), "it must name the fix that does apply"


def test_a_revision_with_no_graph_beside_it_is_refused_and_named(tmp_path: Path) -> None:
    """Never guessed. The sidecar records no root of its own, and a longest common prefix
    would be a plausible root and plausibly wrong -- rule 20 refuses rather than repairs.
    """
    out, db, _, rev = _make_legacy(tmp_path)
    shutil.move(str(db), str(tmp_path / "elsewhere.db"))

    with pytest.raises(migrate.MigrationRefused) as exc:
        migrate.migrate_program(out)
    assert rev in str(exc.value), "it must name which revision it cannot place"


def test_a_path_above_the_analysed_tree_becomes_a_dotdot_rather_than_staying_absolute(
        tmp_path: Path) -> None:
    """The four rows a first version of this migration silently left behind.

    `pyproject.toml` sits above `src/`, so a prefix strip cannot reach it and 54,746 of
    54,750 rows moving looks exactly like success. Counted apart from the rest, because a
    `..` path is worth an operator seeing (rule 32).
    """
    out, db, root, _rev = _make_legacy(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO entrypoints(id,kind,name,file) VALUES('x','CLI','x',?)",
                 (str(root.parent / "pyproject.toml"),))
    conn.commit()
    conn.close()

    report = migrate.migrate_program(out)
    graph = next(s for s in report.stores if s.path == db)
    assert graph.above, "a path above the tree must be reported separately"

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    got = conn.execute("SELECT file FROM entrypoints WHERE id = 'x'").fetchone()[0]
    conn.close()
    assert got == "../pyproject.toml"
    assert _absolute_paths(db, migrate.GRAPH_EXEMPT) == {}


def test_the_marker_is_stated_rather_than_guessed_from_an_empty_store(
        tmp_path: Path) -> None:
    """"Nothing to see" is not the same claim as "already relative".

    An empty legacy store holds no absolute path to find, so a migration inferring its
    state from the rows would call it done and leave the next writer's paths absolute.
    """
    conn = sqlite3.connect(tmp_path / "empty.db")
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.commit()
    assert migrate.paths_are_relative(conn) is False
    conn.execute("INSERT INTO meta(key,value) VALUES(?,?)",
                 (migrate.META_PATHS, migrate.PATHS_RELATIVE))
    conn.commit()
    assert migrate.paths_are_relative(conn) is True
    conn.close()


def test_a_fresh_analysis_states_the_marker_in_all_three_stores(tmp_path: Path) -> None:
    """Or every store this tool writes today is one a reader refuses tomorrow."""
    from dunneflow.docstore import DocStore

    store = Store(tmp_path / "graph.db")
    docs = DocStore(tmp_path / "docs.db")
    src = SourceStore(tmp_path / "source.db")
    for s in (store, docs, src):
        assert migrate.paths_are_relative(s.conn) is True
        s.close()


def test_capture_keys_relative_and_reads_absolute(tmp_path: Path) -> None:
    """The two spellings a capture legitimately holds at once, and which goes where."""
    root = _tree(tmp_path / "tree")
    src = SourceStore(tmp_path / "source.db")
    body = (root / "pkg" / "mod.py").read_text(encoding="utf-8")
    stats = capture({"pkg/mod.py": hash_source(body)}, src, root=root)
    assert stats["stored"] == 1
    assert src.text("pkg/mod.py") == body
    assert [r[0] for r in src.conn.execute("SELECT path FROM paths")] == ["pkg/mod.py"]
    src.close()


def test_packaging_metadata_above_a_src_layout_is_written_as_a_dotdot(
        tmp_path: Path) -> None:
    """The leak the whole-store scan caught, and the one no unit test covered.

    `entrypoints_from_packaging` is a second way into the store that never goes through
    the extractor, so making the extractor's paths relative left these four rows absolute
    — in the one place `CLAUDE.md`'s ground truth lives. Nothing failed: 54,746 of 54,750
    rows moved, which looks exactly like success.

    A `src/` layout is required for the guard to mean anything: with `pyproject.toml`
    beside the code the answer is plain `pyproject.toml` and a version that never learnt
    `..` passes.
    """
    from dunneflow.resolve.entrypoints import entrypoints_from_packaging

    pkg = tmp_path / "proj"
    src_root = _tree(pkg / "src")
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "p"\nversion = "0"\n'
        '[project.scripts]\ngo = "pkg.mod:go"\n', encoding="utf-8")

    db = tmp_path / "graph.db"
    store = Store(db)
    analyze_tree(src_root, store)
    entrypoints_from_packaging(pkg, store, relative_to=src_root)
    store.close()

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    where = [r[0] for r in conn.execute(
        "SELECT file FROM entrypoints WHERE evidence LIKE '%project.scripts%'")]
    conn.close()
    assert where == ["../pyproject.toml"]
    assert _absolute_paths(db, migrate.GRAPH_EXEMPT) == {}


def test_the_cover_counts_lines_in_the_revision_it_is_reading(tmp_path: Path) -> None:
    """A pre-existing defect, found by serving a copied program directory and looking.

    `_lines` asked for `WHERE p.revision = ''` — the legacy revision, from before a
    snapshot had a name — so from the day revisions landed the cover reported **0 lines**
    for every program analysed since. Mensores is 186,786. Nothing failed and nothing was
    empty: a zero on the first screen reads as "this program has no source", which is a
    claim and a wrong one.

    The guard needs a *named* revision to mean anything: against the legacy empty-string
    revision the old query is right, and a fixture that used one would pass either way.
    """
    from dunneflow.web.cover import _lines

    root = _tree(tmp_path / "tree")
    store = Store(tmp_path / "graph.db")
    analyze_tree(root, store)
    src = SourceStore(tmp_path / "source.db")
    rev = src.open_working()
    assert rev, "the fixture must use a named revision, not the legacy one"
    capture(store.known_hashes(), src, root=root, revision=rev)

    held = src.conn.execute(
        "SELECT SUM(b.lines) FROM paths p JOIN blobs b ON b.hash = p.hash"
        " WHERE p.revision = ?", (rev,)).fetchone()[0]
    assert held > 0
    assert _lines(src, None) == held
    store.close()
    src.close()
