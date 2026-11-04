"""A file's facts depend on more than its own bytes, so its own hash cannot decide the skip.

Rule 81. `analyze_tree` skipped a file whose own hash had not changed, which is right for a
reader that reads one file at a time and wrong for a compiler: `use.c`'s calls are whatever
`api.h`'s macro expands to. Edit the header and `use.c` kept its old facts, while the edge
pass -- replaced whole, from a fresh parse of everything -- described the new ones. The reader
had parsed `use.c` in that run and dropped the result.

Every test drives the real reader through the real walk (rule 48's shape).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dunneflow import ingest, walk
from dunneflow.ingest.contract import ToolchainMissing
from dunneflow.store import Store

PLUGIN = ingest.PLUGINS.get("cpp")


def _clang_missing() -> str:
    if PLUGIN is None:
        return "this build ships no C and C++ reader"
    try:
        PLUGIN.probe()
    except ToolchainMissing as exc:
        return f"no clang and libclang this reader accepts on this machine: {exc}"
    return ""


_WHY = _clang_missing()
pytestmark = pytest.mark.skipif(bool(_WHY), reason=_WHY or "-")


class Killed(BaseException):
    """What a `kill -9` looks like from inside: nothing after it runs. Not an `Exception`,
    so nothing on the way out can mistake it for a file that failed."""


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    root.mkdir()
    (root / "api.h").write_text("#define CALL() first_one()\nvoid first_one(void);\n"
                                "void second_one(void);\n")
    (root / "use.c").write_text('#include "api.h"\nvoid use(void) { CALL(); }\n')
    # The bodies are here so that an edge has somewhere to land. `stddef.h` is outside the tree.
    (root / "other.c").write_text('#include <stddef.h>\n#include "api.h"\n'
                                  "void first_one(void) {}\nvoid second_one(void) {}\n"
                                  "void other(void) { second_one(); }\n")
    return root


@pytest.fixture
def store(tmp_path: Path) -> Iterator[Store]:
    s = Store(tmp_path / "graph.db")
    yield s
    s.close()


def _read(root: Path, store: Store) -> walk.WalkStats:
    return walk.analyze_tree(root, store)


def _edge_names(store: Store) -> set[str]:
    return {str(r["name"]) for r in store.query(
        "SELECT name FROM supplied_edges WHERE lang = 'cpp' AND name != ''")}


# ------------------------------------------------------- what a change re-reads --- #

def test_a_header_edit_rereads_what_includes_it(tree: Path, store: Store) -> None:
    _read(tree, store)
    # The call is written by a macro, so what `use.c` calls is entirely the header's.
    (tree / "api.h").write_text("#define CALL() second_one()\nvoid first_one(void);\n"
                                "void second_one(void);\n")
    stats = _read(tree, store)
    assert stats.parsed == 3 and stats.cached == 0
    assert any("api.h" in n and "changed" in n for n in stats.reader_notes), stats.reader_notes
    assert "second_one" in _edge_names(store)


def test_the_facts_and_the_edges_describe_the_same_parse(tree: Path, store: Store) -> None:
    """The failure as a reader meets it: an edge whose call site the stored facts do not hold,
    because a header turned on a block of `use.c` and `use.c`'s bytes did not change."""
    (tree / "use.c").write_text('#include "api.h"\n#ifdef ON\n'
                                "void on(void) { second_one(); }\n#endif\n")
    _read(tree, store)
    (tree / "api.h").write_text("#define ON 1\nvoid first_one(void);\nvoid second_one(void);\n")
    _read(tree, store)
    held = {str(r["site_id"]) for r in store.query("SELECT site_id FROM supplied_edges")}
    sites = {str(r["site_id"]) for r in store.query("SELECT site_id FROM calls")}
    assert held and held <= sites, sorted(held - sites)
    assert store.query("SELECT 1 FROM routines WHERE name = 'on'")


def test_removing_a_header_rereads(tree: Path, store: Store) -> None:
    (tree / "gone.h").write_text("void gone(void);\n")
    (tree / "use.c").write_text('#include "api.h"\n#include "gone.h"\n'
                                "void use(void) { gone(); }\n")
    _read(tree, store)
    (tree / "gone.h").unlink()
    stats = _read(tree, store)
    assert stats.removed == 1 and stats.parsed == 3
    assert any("gone.h" in n and "removed" in n for n in stats.reader_notes), stats.reader_notes


def test_adding_the_header_a_file_could_not_find_rereads(tree: Path, store: Store) -> None:
    (tree / "use.c").write_text('#include "late.h"\nvoid use(void) { LATE(); }\n')
    _read(tree, store)
    (tree / "late.h").write_text("#define LATE() second_one()\nvoid second_one(void);\n")
    stats = _read(tree, store)
    assert stats.parsed == 4 and stats.cached == 0
    assert any("late.h" in n and "added" in n for n in stats.reader_notes), stats.reader_notes


def test_a_compilation_database_edit_rereads(tree: Path, store: Store) -> None:
    (tree / "use.c").write_text(
        '#include "api.h"\n#ifdef WANTED\nvoid wanted(void) { second_one(); }\n#endif\n')
    _read(tree, store)
    assert not store.query("SELECT 1 FROM routines WHERE name = 'wanted'")
    (tree / "compile_commands.json").write_text(json.dumps([{
        "directory": str(tree), "file": str(tree / "use.c"),
        "command": f"cc -DWANTED -c {tree / 'use.c'}"}]))
    stats = _read(tree, store)
    assert any("compile_commands.json" in n for n in stats.reader_notes), stats.reader_notes
    assert store.query("SELECT 1 FROM routines WHERE name = 'wanted'")


def test_a_header_the_walk_does_not_read_is_still_watched(tree: Path, store: Store) -> None:
    """A `.def` is included and is nobody's source file; a system header is the same case
    from outside the tree. Neither has a row in `files` to change."""
    (tree / "table.def").write_text("#define TABLE_CALL() first_one()\n")
    (tree / "use.c").write_text('#include "api.h"\n#include "table.def"\n'
                                "void use(void) { TABLE_CALL(); }\n")
    _read(tree, store)
    (tree / "table.def").write_text("#define TABLE_CALL() second_one()\n")
    stats = _read(tree, store)
    assert stats.parsed == 3, stats.reader_notes
    assert any("table.def" in n for n in stats.reader_notes), stats.reader_notes


# ------------------------------------------------------------- what it leaves --- #

def test_an_untouched_tree_opens_no_reader(tree: Path, store: Store,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    _read(tree, store)

    def refused(*_a: Any, **_k: Any) -> None:
        raise AssertionError("nothing changed, and the reader was opened anyway")

    assert PLUGIN is not None
    monkeypatch.setattr(PLUGIN, "open", refused)
    stats = _read(tree, store)
    assert stats.parsed == 0 and stats.cached == 3


def test_another_language_changing_leaves_this_reader_closed(
        tree: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    (tree / "tool.py").write_text("def tool():\n    return 1\n")
    _read(tree, store)
    (tree / "tool.py").write_text("def tool():\n    return 2\n")

    def refused(*_a: Any, **_k: Any) -> None:
        raise AssertionError("a Python edit opened the C reader")

    assert PLUGIN is not None
    monkeypatch.setattr(PLUGIN, "open", refused)
    stats = _read(tree, store)
    assert stats.parsed == 1 and stats.cached == 3


def test_a_reader_that_does_not_declare_it_still_skips_by_file(tmp_path: Path) -> None:
    root = tmp_path / "py"
    root.mkdir()
    (root / "a.py").write_text("def a():\n    return 1\n")
    (root / "b.py").write_text("def b():\n    return 1\n")
    s = Store(tmp_path / "py.db")
    try:
        walk.analyze_tree(root, s)
        (root / "a.py").write_text("def a():\n    return 2\n")
        stats = walk.analyze_tree(root, s)
        assert stats.parsed == 1 and stats.cached == 1
    finally:
        s.close()


# --------------------------------------------------------- a run that is killed --- #

def _kill_after_writes(monkeypatch: pytest.MonkeyPatch, store: Store, n: int) -> None:
    """Commit `n` files and die, as `settle_if_large` leaves a long run."""
    real = store.write_file_facts
    done = {"n": 0}

    def write(ff: Any, *a: Any, **k: Any) -> Any:
        if done["n"] >= n:
            store.conn.commit()
            raise Killed
        done["n"] += 1
        return real(ff, *a, **k)

    monkeypatch.setattr(store, "write_file_facts", write)


def test_a_whole_read_that_is_killed_is_taken_up_again(
        tree: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the marker every hash now matches, half the facts are old, and the next run
    finds nothing to do -- so this is the case the marker exists for (rule 80)."""
    _read(tree, store)
    (tree / "api.h").write_text("#define CALL() second_one()\nvoid first_one(void);\n"
                                "void second_one(void);\n")
    with monkeypatch.context() as m:
        _kill_after_writes(m, store, 1)
        with pytest.raises(Killed):
            _read(tree, store)
    stats = _read(tree, store)
    assert stats.parsed == 3, stats.reader_notes
    assert any("interrupted" in n for n in stats.reader_notes), stats.reader_notes


def test_a_cold_read_that_is_killed_only_reads_the_rest(
        tree: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Resume is worth 5 hours on Runtime's write side only when nothing changed, and nothing
    did: a file added to a run that never finished is not a change to anything finished."""
    with monkeypatch.context() as m:
        _kill_after_writes(m, store, 1)
        with pytest.raises(Killed):
            _read(tree, store)
    stats = _read(tree, store)
    assert stats.parsed == 2 and stats.cached == 1
    assert _edge_names(store)


def test_killed_between_the_files_and_the_edges_still_gets_its_edges(
        tree: Path, store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every file written, no edge asked for, and nothing left that looks like work."""
    assert PLUGIN is not None

    def killed() -> Iterator[Any]:
        raise Killed
        yield

    with monkeypatch.context() as m:
        m.setattr(PLUGIN, "edges", killed)
        with pytest.raises(Killed):
            _read(tree, store)
    assert store.query("SELECT count(*) AS n FROM files")[0]["n"] == 3
    assert not _edge_names(store)
    stats = _read(tree, store)
    assert stats.parsed == 0 and stats.cached == 3
    assert _edge_names(store)


def test_the_marker_does_not_outlive_a_finished_run(tree: Path, store: Store) -> None:
    _read(tree, store)
    assert not store.get_meta("reading:cpp")


def test_a_touched_outside_input_rereads_and_a_missing_one_is_a_change(
        tree: Path, store: Store) -> None:
    _read(tree, store)
    said = json.loads(store.get_meta("inputs:cpp") or "{}")
    assert said, "the reader named nothing it read beyond its own files"
    # The input of this kind that can be edited here: the database the reader looked for.
    db = [p for p in said if p.endswith("compile_commands.json")]
    assert db and said[db[0]] == [-1, -1]
    # A stat that differs is enough; a touched header is the same branch.
    other = next(p for p in said if not p.endswith("compile_commands.json"))
    said[other] = [1, 1]
    store.set_meta_now("inputs:cpp", json.dumps(said))
    stats = _read(tree, store)
    assert stats.parsed == 3, stats.reader_notes
    assert os.path.exists(other)


def test_resuming_past_the_window_does_not_deadlock(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader holds a bounded window of finished files. It dropped the unwanted ones once,
    when asked, so a wanted file more than a window ahead left the workers stopped with a full
    window and the main thread waiting for a file nobody would reach: forever, at no CPU.

    In a subprocess, because what this guards against is a read that never returns.
    """
    root = tmp_path / "many"
    root.mkdir()
    for i in range(100):
        (root / f"f{i:03}.c").write_text(f"void f{i}(void) {{}}\n")
    graph = tmp_path / "many.db"
    s = Store(graph)
    try:
        with monkeypatch.context() as m:
            _kill_after_writes(m, s, 90)
            with pytest.raises(Killed):
                walk.analyze_tree(root, s)
    finally:
        s.close()
    code = ("import sys; from pathlib import Path; from dunneflow import walk; "
            "from dunneflow.store import Store; s = Store(Path(sys.argv[2])); "
            "st = walk.analyze_tree(Path(sys.argv[1]), s); print(st.parsed, st.cached); s.close()")
    done = subprocess.run([sys.executable, "-c", code, str(root), str(graph)],
                          capture_output=True, text=True, timeout=120, check=True)
    assert done.stdout.split() == ["10", "90"], done.stdout
