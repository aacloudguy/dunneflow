"""Re-analysis must cost only what changed, and must forget what is gone."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dunneflow.docstore import DocStore
from dunneflow.store import StaleGraphError, Store
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
    (root / "a.py").write_text(
        '"""Module prose."""\n\n\ndef alpha() -> None:\n    pass\n', encoding="utf-8")

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
    (root / "a.py").write_text("def alpha() -> None:\n    pass\n", encoding="utf-8")
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
    (root / "a.py").write_text("def alpha() -> None:\n    pass\n", encoding="utf-8")
    db = tmp_path / "g.db"
    s1 = Store(db)
    analyze_tree(root, s1)
    s1.close()

    s2 = Store(db)
    assert not s2.rebuilt
    stats = analyze_tree(root, s2)
    assert stats.cached == 1 and stats.parsed == 0
    s2.close()


# --------------------------------------------------------------------------- #
# Rule 12, both halves: the source AND the tool that read it
# --------------------------------------------------------------------------- #


def test_the_reader_is_in_the_cache_key() -> None:
    """Rule 12 was enforced by hand, and a hand is exactly what forgets.

    The rules were hashed; the extractor that applies them was not. Named artefacts,
    the comment fix and module-level constants each changed what extraction *means*
    while every cached file stayed byte-identical, and each was saved only by someone
    remembering to bump `SCHEMA_VERSION`. A forgotten bump is a confident map
    answering the previous version of the tool.

    Membership is asserted rather than re-derived: a test that rebuilt the list would
    agree with a wrong list.
    """
    from dunneflow.detectors import core_extraction_inputs, lang_extraction_inputs
    from dunneflow.detectors.prose import doc_extraction_inputs

    # **Two keys now, and which half a file is in is the claim.** The reader and its own
    # rules stamp the language; the loader, the shared rules, the ingest seam and the fact
    # contract stamp every language at once. A file in the wrong half is either a plugin
    # edit that discards somebody else's graph, or a core edit that discards nothing.
    core = {p.name for p in core_extraction_inputs()}
    assert "annotations.yaml" in core, "the shared rules are not in the core cache key"
    assert "__init__.py" in core, "the rule loader is not in the core cache key"
    assert "schema.py" in core, "what a fact *is* is not in the core cache key"
    assert "contract.py" in core, "the ingest seam is not in the core cache key"

    python = {p.name for p in lang_extraction_inputs("python")}
    assert "extract.py" in python, "the Python reader is not in the Python cache key"
    assert "python.yaml" in python, "Python's own rules are not in its cache key"
    assert "plugin.json" in python, "the plugin's own manifest is not in its cache key"
    assert "extract.py" not in core and "python.yaml" not in core, (
        "one language's reader is in the key every language shares, so editing it would "
        "discard every other language's graph"
    )

    docs = {p.name for p in doc_extraction_inputs()}
    assert "markdown.py" in docs, "the document reader is not in the doc cache key"
    assert "prose.py" in docs and "annotations.yaml" in docs


def test_the_two_corpora_do_not_invalidate_each_other() -> None:
    """Editing a prose rule must not discard the code graph, and vice versa.

    The stores are separate so each corpus can be re-read on its own; a shared key
    would make a documentation edit cost a full re-parse of the source.
    """
    from dunneflow.detectors import core_extraction_inputs, lang_extraction_inputs
    from dunneflow.detectors.prose import doc_extraction_inputs

    code = {p.resolve() for p in (*core_extraction_inputs(),
                                  *lang_extraction_inputs("python"))}
    docs = {p.resolve() for p in doc_extraction_inputs()}

    assert not any(p.name == "markdown.py" for p in code), "docs reader leaked into the code key"
    assert not any(p.name == "prose.yaml" for p in code), "prose rules leaked into the code key"
    assert not any(p.name == "extract.py" for p in docs), "code reader leaked into the doc key"
    assert not any(p.name == "python.yaml" for p in docs), "code rules leaked into the doc key"

    # annotations.yaml governs both, deliberately -- comments are comments and prose
    # is prose, and the same governance markers are mined from each.
    shared = {p.name for p in code & docs}
    assert shared == {"annotations.yaml"}, f"unexpected overlap: {shared}"


def test_fingerprint_changes_when_any_input_changes(tmp_path: Path) -> None:
    """The hash must react to content and to naming, not just to the file set."""
    from dunneflow.detectors import fingerprint_files

    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("one", encoding="utf-8")
    b.write_text("two", encoding="utf-8")

    base = fingerprint_files([a, b])
    assert fingerprint_files([b, a]) == base, "the hash depends on argument order"

    a.write_text("one!", encoding="utf-8")
    assert fingerprint_files([a, b]) != base, "a content change did not change the hash"

    a.write_text("one", encoding="utf-8")
    c = tmp_path / "c.yaml"
    c.write_text("", encoding="utf-8")
    assert fingerprint_files([a, b, c]) != base, "an added empty file did not change the hash"


def test_a_reader_refuses_a_stale_graph_instead_of_emptying_it(tmp_path: Path) -> None:
    """Found by upgrading the tool and then running a read command.

    `Store.__init__` discarded a stale graph on *every* open. For `analyze` that is
    right -- it re-extracts in the same breath. For `query`, `touches` or `impact` it
    dropped every table and then answered out of the hole, and `(no rows)` is
    indistinguishable from a true empty result. A tool upgrade therefore turned every
    orientation command into a confident wrong answer, silently, once.

    A reader must refuse and say how to rebuild.
    """
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_text("def alpha() -> None:\n    pass\n", encoding="utf-8")
    db = tmp_path / "g.db"

    s1 = Store(db)
    analyze_tree(root, s1)
    before = s1.query("SELECT COUNT(*) FROM routines")[0][0]
    assert before, "nothing was stored, so the test proves nothing"
    version, _fp = str(s1.get_meta("extractor")).split(":", 1)
    s1.set_meta("extractor", f"{version}:0000000000000000")   # pretend the tool changed
    s1.close()

    with pytest.raises(StaleGraphError, match="dunneflow analyze"):
        Store(db, writable=False)

    # ...and the refusal must leave the graph exactly as it found it.
    s2 = Store(db)
    assert s2.rebuilt, "the writer should still rebuild a stale graph"
    s2.close()

    s3 = sqlite3.connect(db)
    kept = s3.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='routines'"
    ).fetchone()[0]
    s3.close()
    assert kept, "the writable open did not recreate the schema"


def test_a_reader_leaves_a_current_graph_untouched(tmp_path: Path) -> None:
    """A read must not write, not even the meta stamps a writable open refreshes."""
    root = tmp_path / "src"
    root.mkdir()
    (root / "a.py").write_text("def alpha() -> None:\n    pass\n", encoding="utf-8")
    db = tmp_path / "g.db"

    s1 = Store(db)
    analyze_tree(root, s1)
    s1.close()
    fingerprint = db.stat().st_mtime_ns, db.stat().st_size

    s2 = Store(db, writable=False)
    assert s2.query("SELECT COUNT(*) FROM routines")[0][0]
    assert not s2.rebuilt
    s2.close()

    assert (db.stat().st_mtime_ns, db.stat().st_size) == fingerprint, \
        "a read-only open modified the database"


def test_a_reader_refuses_a_stale_document_store(tmp_path: Path) -> None:
    """The same hole, the other corpus."""
    db = tmp_path / "docs.db"
    d1 = DocStore(db)
    version, _fp = str(d1.get_meta("extractor")).split(":", 1)
    d1.set_meta("extractor", f"{version}:0000000000000000")
    d1.close()

    with pytest.raises(StaleGraphError, match="dunneflow analyze"):
        DocStore(db, writable=False)


def test_the_cache_key_holds_only_what_extraction_reads() -> None:
    """The key's own rule, asserted where it can be broken by an ordinary edit.

    `lang_extraction_inputs("python")` globs `extractors/python/*.py`, which is the right
    default:
    rule 12 was earned by a key that hashed the rules and not the reader, and a glob cannot
    forget a file somebody adds. But the glob is a *mechanism* and "what extraction actually
    reads" is the *rule*, and a file dropped into that folder is in the key whether or not
    extraction has ever heard of it.

    That happened: a canonicaliser for the change comparison landed there and made both of
    Lictores' graphs read as stale — including a sealed snapshot, which exists precisely to
    outlive its source tree (rules 25 and 62) — for a module extraction never imports and
    that cannot alter a single fact. It lives in `canonical/` now.

    Over-invalidating is the safer direction and this test does not argue otherwise. It
    argues that the *reason* a file is in the key must be that extraction reads it.
    """
    import ast

    from dunneflow.detectors import core_extraction_inputs, lang_extraction_inputs

    for path in (*core_extraction_inputs(), *lang_extraction_inputs("python")):
        if path.suffix != ".py" or not path.stat().st_size:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        reachable = any(
            isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
            for n in ast.walk(tree)
        )
        assert reachable, (
            f"{path.name} is in the code cache key and declares nothing — if it is not read "
            "by extraction it does not belong there, and every edit to it discards every "
            "graph on the machine"
        )

    names = {p.name for p in (*core_extraction_inputs(),
                              *lang_extraction_inputs("python"))}
    assert "canonical.py" not in names, (
        "a canonicaliser is in the code extraction key. It cannot change a fact — only "
        "whether two facts compare equal — so editing one would discard every graph, sealed "
        "snapshots included, for nothing. It belongs in `canonical/`"
    )
