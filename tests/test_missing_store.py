"""A reader refuses a path that is not there, and never brings one into being.

**The defect, and it was done rather than imagined.** `sqlite3.connect` creates. A
one-line probe opened `output/lictores/graph.db` with `writable=False` -- a path that does
not exist in that directory, because lictores keeps only `graph@<revision>.db` -- and
sqlite made one: a 0-byte file, in the output tree, invisible to `git status` because
`output/` is untracked. The query that followed raised `no such table: files`, so nothing
answered wrongly *that* time; what remained was the file.

**The file is the harm.** `revisions.py` reads a bare `graph.db` as "a directory written
before this layout existed" -- the one legacy revision of that program. So a *read* had
given lictores a fifth revision holding nothing at all, and every listing, every `newest`
and every `program_dirs` would have gone on believing it. Rule 20 from the side nobody
expects: the read repaired nothing, it wrote.

**And it is rule 51, which is why the fix is where it is.** Seven read paths each carried
their own `if not path.exists()` -- `cli._open_store`, `_Live._docs_for`, `_open_source`,
`_open_docsource`, and the version-listing branch of `_r_revisions`. Every one was
correct. The guard held for exactly as long as somebody remembered to write it, and the
caller that did not remember was not any of them. Moved to where they all pass.

Every guard below was run against the unfixed constructors first (rule 37): each of the
three refusal tests fails there, and `test_a_writer_still_creates_its_own_file` passes
there, which is the pair that says the fix is a refusal and not a wall.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dunneflow import revisions
from dunneflow.docstore import DocStore
from dunneflow.sourcedb import DocSourceStore, SourceStore
from dunneflow.store import Store
from dunneflow.web import serve as serve_mod


def test_a_read_of_a_missing_graph_refuses_and_leaves_nothing_behind(
        tmp_path: Path) -> None:
    """The refusal is the smaller half. Not creating the file is the point.

    Asserted in that order deliberately: an implementation that raised *after* connecting
    would satisfy the first assertion and leave the phantom revision behind exactly as
    before, which is the whole defect wearing an error message.
    """
    missing = tmp_path / "graph.db"

    with pytest.raises(FileNotFoundError) as exc:
        Store(missing, writable=False)

    assert not missing.exists(), (
        "a read created the file it was refusing to read -- the defect itself"
    )
    said = str(exc.value)
    assert str(missing) in said, "the refusal must name the path that is not there"
    assert "code graph" in said, "and say what it declined to open there"


def test_a_leftover_file_is_read_as_a_program_and_a_revision(tmp_path: Path) -> None:
    """**Why the file matters**, proved against `revisions` and not against the guard.

    This test is true with the fix and without it, on purpose: it is a fact about
    `revisions.py`, which is the thing that turns a stray file into a wrong answer.
    `program_dirs` recognises a *map* -- `graph.db` or `graph@<revision>.db` -- and a bare
    name is read as the one legacy revision of a directory written before the layout
    existed. Neither reader opens the file, so neither can tell that this one holds
    nothing.

    Written this way after the first version of it was worthless. It asserted the same two
    facts *after* a `pytest.raises`, so against the unfixed constructors it failed on the
    raise and never reached them -- a test that appeared to prove the consequence and had
    never once executed the lines that do. Rule 37 on the guard written for rule 51.
    """
    out = tmp_path / "output" / "someprogram"
    out.mkdir(parents=True)

    assert revisions.program_dirs(tmp_path / "output") == frozenset(), (
        "a directory with no map is not a program directory -- the baseline"
    )
    assert revisions.newest(out, revisions.GRAPH) is None

    (out / "graph.db").touch()          # exactly what the unfixed read left behind

    assert revisions.program_dirs(tmp_path / "output") == frozenset({out}), (
        "a 0-byte file promoted a directory holding no map into a program"
    )
    assert revisions.newest(out, revisions.GRAPH) == out / "graph.db", (
        "and it is offered as the newest revision, holding nothing at all"
    )
    assert revisions.revision_of(out / "graph.db") is None, (
        "as a legacy revision, which is the shape that cannot be told from a real one"
    )


def test_the_refusal_leaves_no_phantom_revision(tmp_path: Path) -> None:
    """And the guard, against the consequence the test above established.

    Both assertions are reached only when the refusal happens, which is why the fact they
    rest on is proved separately: this one says the read created nothing, that one says
    what it would have cost if it had.
    """
    out = tmp_path / "output" / "someprogram"
    out.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        Store(out / "graph.db", writable=False)

    assert revisions.program_dirs(tmp_path / "output") == frozenset(), (
        "a refused read invented a program directory"
    )
    assert revisions.newest(out, revisions.GRAPH) is None, (
        "a refused read invented a revision"
    )


@pytest.mark.parametrize(
    ("cls", "filename", "what"),
    [
        (Store, "graph.db", "code graph"),
        (DocStore, "docs.db", "document corpus"),
        (SourceStore, "source.db", "source sidecar"),
        (DocSourceStore, "docsource.db", "document sidecar"),
    ],
)
def test_every_store_obeys_the_rule_the_first_one_was_taught(
        tmp_path: Path, cls: type, filename: str, what: str) -> None:
    """Rule 61, asserted over all four rather than argued for in a comment.

    `DocSourceStore` is in the list even though it inherits `SourceStore`'s constructor:
    what is being checked is that it refuses *as itself*, since its whole existence is
    rule 16's point that the stamp is the difference.
    """
    missing = tmp_path / filename

    with pytest.raises(FileNotFoundError) as exc:
        cls(missing, writable=False)

    assert not missing.exists(), f"{cls.__name__} created the file it refused to read"
    assert what in str(exc.value), (
        f"{cls.__name__} must say what it declined to open, not just that it declined"
    )


def test_a_writer_still_creates_its_own_file(tmp_path: Path) -> None:
    """A guard that stopped a writer would be rule 43's defect, not rule 20's fix.

    Creating the database is the entire job of a writer, and `analyze` opening a program
    for the first time is the commonest thing this tool does. Asserted rather than assumed
    because the guard sits three lines from the `mkdir` that exists to serve exactly this.
    """
    fresh = tmp_path / "nested" / "graph.db"
    store = Store(fresh, writable=True)
    try:
        assert fresh.exists(), "a writer must create the file it was pointed at"
        assert store.get_meta("kind") == "graph"
    finally:
        store.close()


def test_an_absent_sidecar_is_still_a_state_and_not_an_error(tmp_path: Path) -> None:
    """`serve` says *"absent is a real state, never an error"*, and it still is.

    `FileNotFoundError` was chosen over an exception of ours precisely so this stayed
    true: it is an `OSError`, which is what these two already catch. Asserted through
    `_Live`'s own methods rather than through the exception type, because what must not
    change is the answer the server gives -- not the route it takes to it.
    """
    assert serve_mod._Live._open_source(tmp_path / "source.db") is None
    assert serve_mod._Live._open_docsource(tmp_path / "docsource.db") is None


def test_an_existing_but_empty_file_is_a_different_failure_and_is_left_alone(
        tmp_path: Path) -> None:
    """The boundary of this fix, stated so the next reader does not assume it is wider.

    A file that **exists** and holds no tables is not what this guard is about, and it is
    deliberately not caught here: `_is_stale` reads it as *"no meta table yet: a fresh
    database"*, which is right for the writer that is about to fill it. Such a file
    raises `no such table` on the first query rather than answering nothing -- a poor
    sentence and not a wrong answer, and a separate decision from this one.

    Recorded as a test because the difference is invisible: both cases produce a 0-byte
    file, and only one of them was produced by a read.
    """
    empty = tmp_path / "graph.db"
    empty.touch()

    store = Store(empty, writable=False)
    try:
        with pytest.raises(sqlite3.OperationalError):
            store.query("SELECT COUNT(*) FROM files")
    finally:
        store.close()
