"""`writable=False` means the connection cannot write, not that we intend not to.

The family of failure here is a guard that reads correctly and enforces nothing.
`Store.writable` was assigned and never read again: it chose mkdir-versus-refuse and
refuse-versus-discard on staleness, and left an ordinary read-write sqlite handle
underneath every one of the fourteen sites that open a map to *read* it. So
`dunneflow query --sql "DELETE FROM routines"` emptied a table through a store whose own
name for itself was `writable=False`, and nothing anywhere said so.

These press the connection rather than the name (rule 37): a test that finds `mode=ro` in
the source has checked that a string appears, not that a write fails.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dunneflow.store import Store, read_only_uri

# ---- a map to read --- #


@pytest.fixture()
def graph(tmp_path: Path) -> Path:
    """One real graph, written by a writable store and then closed."""
    db = tmp_path / "graph.db"
    store = Store(db)
    store.conn.execute(
        "INSERT INTO routines (id, name, qualname, module, file, line_start, line_end, "
        "lang) VALUES ('r1', 'f', 'm.f', 'm', 'm.py', 1, 2, 'python')")
    store.conn.commit()
    store.close()
    return db


# ---- what a read may not do --- #


@pytest.mark.parametrize("sql", [
    "DELETE FROM routines",
    "UPDATE routines SET name = 'x'",
    "INSERT INTO routines (id, name, qualname, module, file, line_start, line_end, lang) "
    "VALUES ('r2', 'g', 'm.g', 'm', 'm.py', 3, 4, 'python')",
    "DROP TABLE routines",
    "CREATE TABLE sneaky (a)",
])
def test_a_read_only_store_refuses_every_write(graph: Path, sql: str) -> None:
    """Each of these worked through a `writable=False` store until 2026-09-17.

    Tolerable while a person was the one typing it; not once a language model composes
    the statement, which is what `dunneflow mcp` exists to let one do.
    """
    store = Store(graph, writable=False)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            store.query(sql)
        assert store.query("SELECT count(*) AS n FROM routines")[0]["n"] == 1, (
            "the row is gone, so the write was not refused -- it was refused *late*"
        )
    finally:
        store.close()


def test_the_refusal_reaches_a_write_the_classifier_reads_as_a_read(graph: Path) -> None:
    """`WITH x AS (...) DELETE FROM t` is legal SQLite and classifies as READ.

    `sql.parse` reads the leading verb and nothing else, so its direction for this
    statement is READ -- which is exactly why the connection has to be the defence and
    the classifier cannot be. Measured, not reasoned about: this is the one statement in
    the set that gets past a direction check and still writes.
    """
    store = Store(graph, writable=False)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            store.query("WITH x AS (SELECT 1) DELETE FROM routines")
    finally:
        store.close()


def test_a_read_only_store_still_reads_everything(graph: Path) -> None:
    """The point of the change is that nothing a reader does gets harder.

    A defence that costs the fourteen reading sites their answers would have been
    withdrawn within a day, so this is the half worth pinning.
    """
    store = Store(graph, writable=False)
    try:
        rows = store.query("SELECT id, name, lang FROM routines ORDER BY id")
        assert [tuple(r) for r in rows] == [("r1", "f", "python")]
        assert store.counts()["routines"] == 1
    finally:
        store.close()


def test_a_writable_store_still_writes(tmp_path: Path) -> None:
    """The branch has two arms and only one of them was changed. This is the other."""
    store = Store(tmp_path / "w.db")
    try:
        store.conn.execute(
            "INSERT INTO routines (id, name, qualname, module, file, line_start, "
            "line_end, lang) VALUES ('w1', 'f', 'm.f', 'm', 'm.py', 1, 2, 'python')")
        store.conn.commit()
        assert store.query("SELECT count(*) AS n FROM routines")[0]["n"] == 1
    finally:
        store.close()


# ---- the filename is inside a URI now, and a URI has a grammar --- #


@pytest.mark.parametrize("name,escaped", [
    ("plain", "plain"),
    ("has space", "has%20space"),
    ("has?query", "has%3Fquery"),
    ("has#fragment", "has%23fragment"),
    ("has%percent", "has%25percent"),
])
def test_a_path_is_escaped_into_the_uri_rather_than_pasted_into_it(
        name: str, escaped: str) -> None:
    """Rule 91, on that rule's own list: a filename in a URI is a narrower channel.

    `f"file:{path}?mode=ro"` is what four other sites in this codebase write by hand. A
    `?` in a directory name ends the path and begins the query string, so `mode=ro` is
    consumed as part of the *name* and the connection comes back writable -- against a
    database that does not exist and which SQLite would then create. The failure arrives
    through the fix for the failure.
    """
    uri = read_only_uri(Path("out") / name / "graph.db")
    assert uri == f"file:out/{escaped}/graph.db?mode=ro", uri
    assert uri.count("?") == 1, f"the path spent the query separator: {uri}"


def test_a_map_under_an_awkward_directory_name_still_opens_read_only(
        tmp_path: Path) -> None:
    """Pressed on a real file, because the escaping is only right if SQLite agrees.

    The round trip is what matters: quote it, hand it to SQLite, and get the same file
    back — with the write still refused.
    """
    awkward = tmp_path / "why? #1 100%"
    awkward.mkdir()
    db = awkward / "graph.db"
    Store(db).close()

    store = Store(db, writable=False)
    try:
        assert store.query("SELECT count(*) AS n FROM routines")[0]["n"] == 0
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            store.query("DELETE FROM routines")
    finally:
        store.close()


def test_a_missing_map_still_refuses_rather_than_being_created(tmp_path: Path) -> None:
    """`refuse_missing` is now the second guard and must still be the first to speak.

    `mode=ro` will not create a file either, so this could have been left to SQLite --
    and then the reader would meet `unable to open database file` instead of the sentence
    that says which path and why. The sentence is the point (rule 89).
    """
    absent = tmp_path / "nowhere" / "graph.db"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        Store(absent, writable=False)
    assert not absent.exists(), "opening it read-only brought the file into being"
