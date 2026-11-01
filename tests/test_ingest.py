"""The seam, wired: which reader owns a file, and what the walk left out.

`tests/test_comments.py` holds the other half of this — that the Python reader's own
`DiscoveryRules` still spells *test* exactly as `walk.is_test_path` did before it was
deleted. What is here is the part that could not be pressed while one language was wired:
a walk handed rules for readers this build does not ship, which is the only way to prove
the multi-language behaviour before a multi-language build exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow import ingest, walk
from dunneflow.ingest.contract import DiscoveryRules, PluginRefused

PY = DiscoveryRules(
    lang="python",
    suffixes=frozenset({".py"}),
    test_dirs=frozenset({"tests"}),
    test_stem_prefixes=("test_",),
)
TS = DiscoveryRules(
    lang="typescript",
    suffixes=frozenset({".ts"}),
    test_name_suffixes=(".test.ts", ".spec.ts"),
)


def _write(root: Path, rel: str, text: str = "x = 1\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# ------------------------------------------------------------------ the table --- #

def test_a_suffix_claimed_twice_refuses_naming_both():
    """Never first-wins. `.js` is the case that will actually arrive (rule 66)."""
    other = DiscoveryRules(lang="node", suffixes=frozenset({".ts"}))
    with pytest.raises(PluginRefused) as exc:
        ingest.suffix_owners([TS, other])
    said = str(exc.value)
    assert ".ts" in said and "typescript" in said and "node" in said


def test_the_registry_and_the_walk_read_one_table():
    """Rule 51: the walk asking a second time is how the two come to disagree."""
    assert ingest.suffix_owners(ingest.discovery()) == ingest.LANG_SUFFIX
    assert ingest.language_of("a/b/c.py") == "python"
    assert ingest.language_of("a/b/c.ts") == "typescript"
    # `None` is an answer and not a failure, and `.rb` is what it is about now that
    # `.ts` and `.go` have readers. What must never happen is the file being read anyway.
    assert ingest.language_of("a/b/c.rb") is None


# ------------------------------------------------------------------- the walk --- #

def test_a_typescript_test_is_left_out_and_python_would_have_admitted_it(tmp_path):
    """The 42% property, and the whole reason the rule moved per language.

    `Path("client.test.ts").stem` is `"client.test"`, which starts with neither `test_`
    nor ends with `_test` — so the rule this walk used to hold would have admitted every
    one of DunneNote's 322 test files as program code.
    """
    _write(tmp_path, "src/client.ts")
    _write(tmp_path, "src/client.test.ts")
    _write(tmp_path, "src/client.spec.ts")

    stats = walk.WalkStats()
    found = sorted(walk.discover(tmp_path, rules=[TS], stats=stats))

    assert [p.name for p in found] == ["client.ts"]
    assert stats.tests_excluded == {"typescript": 2}
    # And the old rule's answer, stated rather than assumed, because it is the claim.
    assert not PY.is_test(Path("src/client.test.ts"))


def test_a_readers_own_skip_list_does_not_shrink_another_readers_corpus(tmp_path):
    """The asymmetry: suffixes are a union, skip dirs are not.

    A TypeScript reader that declared `out` would take `out/` out of the **Python**
    corpus too if this walk pruned directories on a plugin's list. It prunes only on the
    set every language agrees about, and applies a plugin's own list to the file after
    the suffix has said who owns it.
    """
    ts_with_out = DiscoveryRules(lang="typescript", suffixes=frozenset({".ts"}),
                                 skip_dirs=frozenset({"out"}))
    _write(tmp_path, "out/generated.ts")
    _write(tmp_path, "out/kept.py")

    stats = walk.WalkStats()
    found = sorted(walk.discover(tmp_path, rules=[PY, ts_with_out], stats=stats))

    assert [p.name for p in found] == ["kept.py"]
    assert stats.lang_skipped == {"typescript": 1}


def test_a_suffix_nobody_claims_is_counted_and_a_document_is_not(tmp_path):
    """Design rule 1: an empty map must say why it is empty.

    A `.md` file is **read**, by the other walk in that module, so counting it as unread
    would be a false claim rather than a silent one (rule 13).
    """
    _write(tmp_path, "main.py")
    _write(tmp_path, "vendored.rb")
    _write(tmp_path, "schema.json")
    _write(tmp_path, "README.md", "# hello\n")

    stats = walk.WalkStats()
    found = sorted(walk.discover(tmp_path, rules=[PY], stats=stats))

    assert [p.name for p in found] == ["main.py"]
    assert stats.unclaimed == {".json": 1, ".rb": 1}
    said = " ".join(walk.walk_residue(stats))
    assert ".rb" in said and ".md" not in said


def test_a_pruned_directory_is_counted_by_name(tmp_path):
    _write(tmp_path, "keep.py")
    _write(tmp_path, "node_modules/pkg/index.py")
    _write(tmp_path, ".hidden/thing.py")

    stats = walk.WalkStats()
    found = sorted(walk.discover(tmp_path, rules=[PY], stats=stats))

    assert [p.name for p in found] == ["keep.py"]
    assert stats.pruned == {"node_modules": 1, ".hidden": 1}
    assert "node_modules" in " ".join(walk.walk_residue(stats))


def test_a_directory_holding_a_map_is_not_source(tmp_path):
    """Rule 92's test, on the walk that never had it.

    A program directory is this tool's own writing about somebody else's program. It
    never mattered while only Python was read — a map holds no `.py` — and it started
    mattering the moment the walk began saying what it had passed over.
    """
    _write(tmp_path, "keep.py")
    _write(tmp_path, "output/mensores/graph@2026-01-01T00-00-00Z.db", "not really sqlite")
    _write(tmp_path, "output/mensores/notes.py")

    stats = walk.WalkStats()
    found = sorted(walk.discover(tmp_path, rules=[PY], stats=stats))

    assert [p.name for p in found] == ["keep.py"]
    assert [Path(d).name for d in stats.maps] == ["mensores"]
    assert stats.unclaimed == {}
    assert "map" in " ".join(walk.walk_residue(stats))


def test_nothing_left_out_says_nothing(tmp_path):
    """A report that speaks when there is nothing to report is rule 43 in the summary."""
    _write(tmp_path, "only.py")
    stats = walk.WalkStats()
    list(walk.discover(tmp_path, rules=[PY], stats=stats))
    assert walk.walk_residue(stats) == []


def test_the_walk_defaults_to_every_reader_this_build_ships(tmp_path):
    _write(tmp_path, "a.py")
    _write(tmp_path, "b.ts")
    _write(tmp_path, "c.rb")
    # Both readers this build ships, and neither one by name. `c.rb` is the third
    # answer: a suffix nobody claims is left out and counted, never handed to
    # whichever reader happened to be nearest.
    assert [p.name for p in walk.discover(tmp_path)] == ["a.py", "b.ts"]


# -------------------------------------------------------------- the dispatch --- #

def test_extraction_goes_through_the_plugin(tmp_path, monkeypatch):
    """`analyze_tree` names no language, so a reader can be swapped underneath it."""
    from dunneflow.store import Store

    _write(tmp_path, "m.py", "def f():\n    return 1\n")
    seen: dict[str, object] = {}

    plugin = ingest.PLUGINS["python"]
    real_extract = plugin.extract

    def spy(work, root, progress=None, jobs=None):
        seen["work"] = sorted(p.name for p in work)
        seen["jobs"] = jobs
        return real_extract(work, root, progress, jobs)

    monkeypatch.setattr(plugin, "extract", spy)
    store = Store(tmp_path / "graph.db")
    try:
        stats = walk.analyze_tree(tmp_path, store, jobs=3)
    finally:
        store.close()

    assert seen["work"] == ["m.py"]
    # `--jobs` is the machine's owner speaking, and it has to reach the reader.
    assert seen["jobs"] == 3
    assert stats.parsed == 1


def test_a_file_the_reader_loses_is_counted_as_failed(tmp_path, monkeypatch):
    """A file whose worker died never arrives, so only the reader can say it existed."""
    from dunneflow.store import Store

    _write(tmp_path, "m.py")
    plugin = ingest.PLUGINS["python"]

    def nothing_came_back(work, root, progress=None, jobs=None):
        plugin.lost = len(work)
        return iter(())

    monkeypatch.setattr(plugin, "extract", nothing_came_back)
    store = Store(tmp_path / "graph.db")
    try:
        stats = walk.analyze_tree(tmp_path, store)
    finally:
        store.close()
    plugin.lost = 0

    assert stats.parsed == 0
    assert stats.failed == 1
