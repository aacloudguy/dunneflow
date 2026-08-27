"""Re-analysis must cost only what changed, and must forget what is gone."""

from __future__ import annotations

from pathlib import Path

from dunneflow.store import Store
from dunneflow.walk import analyze_tree


def _write(root: Path, name: str, body: str) -> None:
    (root / name).write_text(body, encoding="utf-8")


def test_unchanged_files_are_not_reparsed(tmp_path):
    root = tmp_path / "prog"
    root.mkdir()
    _write(root, "a.py", "def one():\n    pass\n")
    _write(root, "b.py", "def two():\n    pass\n")
    store = Store(tmp_path / "g.db")

    first = analyze_tree(root, store)
    assert first.parsed == 2 and first.cached == 0

    second = analyze_tree(root, store)
    assert second.parsed == 0 and second.cached == 2

    _write(root, "a.py", "def one():\n    return 1\n")
    third = analyze_tree(root, store)
    assert third.parsed == 1 and third.cached == 1
    store.close()


def test_deleted_files_are_forgotten(tmp_path):
    root = tmp_path / "prog"
    root.mkdir()
    _write(root, "a.py", "def one():\n    pass\n")
    _write(root, "b.py", "def two():\n    pass\n")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    assert store.counts()["routines"] == 2

    (root / "b.py").unlink()
    stats = analyze_tree(root, store)
    assert stats.removed == 1
    assert store.counts()["routines"] == 1
    assert not store.query("SELECT 1 FROM routines WHERE name = 'two'")
    store.close()


def test_reanalysis_is_deterministic(tmp_path):
    root = tmp_path / "prog"
    root.mkdir()
    _write(root, "a.py", "import os\ndef one(x: int) -> str:\n    return os.getenv('A', x)\n")

    def snapshot(db: Path) -> list:
        s = Store(db)
        rows = s.query(
            "SELECT qualname, line_start FROM routines ORDER BY qualname"
        ) + s.query("SELECT kind, target FROM boundaries ORDER BY kind, target")
        out = [tuple(r) for r in rows]
        s.close()
        return out

    s1 = Store(tmp_path / "g1.db")
    analyze_tree(root, s1)
    s1.close()
    s2 = Store(tmp_path / "g2.db")
    analyze_tree(root, s2)
    s2.close()
    assert snapshot(tmp_path / "g1.db") == snapshot(tmp_path / "g2.db")


def test_stale_schema_discards_the_graph(tmp_path: Path) -> None:
    """An upgraded DunneFlow must never read an older graph.

    `CREATE TABLE IF NOT EXISTS` will not widen an existing table, and the file cache
    keys on source content alone -- so without this, upgrading the tool yields a map
    that is silently the old shape and silently not re-parsed.
    """
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_text('"""Module prose."""\n\n\ndef alpha() -> None:\n    pass\n')

    db = tmp_path / "g.db"
    s1 = Store(db)
    analyze_tree(root, s1)
    assert not s1.rebuilt
    assert s1.counts()["routines"] >= 1
    s1.set_meta("extractor", "0:deadbeef")    # pretend an older tool wrote it
    s1.close()

    s2 = Store(db)
    assert s2.rebuilt, "a graph from another schema version was reused"
    assert s2.counts()["routines"] == 0, "stale facts survived the discard"

    stats = analyze_tree(root, s2)
    assert stats.parsed == 1 and stats.cached == 0, "the file cache survived a rebuild"
    rows = s2.query("SELECT doc FROM files")
    assert rows and rows[0][0] == "Module prose."
    s2.close()


def test_changed_detector_rules_discard_the_graph(tmp_path: Path) -> None:
    """`detectors/*.yaml` is the extension point, so it is the thing most often edited.

    Editing a rule changes what extraction produces while leaving every source file
    byte-identical -- so without a rules fingerprint in the cache key, the new rule
    silently never runs and the map keeps the old rule's answer.
    """
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_text("def alpha() -> None:\n    pass\n")
    db = tmp_path / "g.db"

    s1 = Store(db)
    analyze_tree(root, s1)
    stored = s1.get_meta("extractor")
    assert stored and ":" in stored, "the cache key does not carry a rules fingerprint"
    version, fingerprint = stored.split(":", 1)
    s1.set_meta("extractor", f"{version}:0000000000000000")   # pretend a rule changed
    s1.close()

    s2 = Store(db)
    assert s2.rebuilt, "a rule change did not invalidate the graph"
    stats = analyze_tree(root, s2)
    assert stats.parsed == 1 and stats.cached == 0
    s2.close()


def test_matching_schema_keeps_the_graph(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_text("def alpha() -> None:\n    pass\n")
    db = tmp_path / "g.db"
    s1 = Store(db)
    analyze_tree(root, s1)
    s1.close()

    s2 = Store(db)
    assert not s2.rebuilt
    stats = analyze_tree(root, s2)
    assert stats.cached == 1 and stats.parsed == 0
    s2.close()
