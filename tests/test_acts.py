"""One act, one row (`ingest/acts.py`) and rule 5 in `python.yaml`'s FILE rule.

Both through the ordinary walk, because the collapse is applied where every reader's
facts pass and nowhere else (rule 51): what is tested is exactly what runs.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

PY = '''import os
import sqlite3
from datetime import datetime
from pathlib import Path


def stamp(text):
    when = datetime.now().isoformat().replace(":", "-")
    return text.replace(" ", "_") + when


def move(p, q):
    Path(p).replace(q)
    os.replace(p, q)


def one(conn):
    return conn.execute("SELECT a FROM t").fetchone()


def two(conn):
    cur = conn.execute("SELECT a FROM t")
    return cur.fetchall()
'''

GO = '''package main

import "net/http"

func main() {
	http.Get("https://example.com").Body.Close()
}
'''


def _boundaries(store: Store) -> list[tuple[str, str, int]]:
    return sorted((str(r["kind"]), str(r["evidence"]), int(r["line"]))
                  for r in store.query("SELECT kind, evidence, line FROM boundaries"))


@pytest.fixture
def python_map(tmp_path: Path) -> Store:
    root = tmp_path / "p"
    root.mkdir()
    (root / "m.py").write_text(PY, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    return store


def test_a_string_s_replace_is_not_a_file(python_map: Store) -> None:
    """Rule 5. `replace` as a bare method made 175 FILE boundaries in Comitia, most of them
    a timestamp or a piece of text being edited."""
    files = [e for k, e, _ in _boundaries(python_map) if k == "FILE"]
    assert files == ["Path.replace", "os.replace"], files


def test_a_chain_on_a_call_is_that_call(python_map: Store) -> None:
    """Rule 40. `conn.execute(q).fetchone()` is one DATABASE touch on its line; the same two
    calls written over two lines are two, which is what a reader of the source counts."""
    db = [(e, line) for k, e, line in _boundaries(python_map) if k == "DATABASE"]
    one = [e for e, line in db if line == 18]
    assert one == ["conn.execute"], db
    two = sorted(e for e, line in db if line in (22, 23))
    assert two == ["conn.execute", "cur.fetchall"], db


def test_a_go_chain_on_a_remote_call_is_one_remote_call(tmp_path: Path) -> None:
    """`http.Get(u).Body.Close()` is spelt `http.Get.Body.Close`, and the `http.Get` network
    prefix matched it a second time."""
    if ingest.PLUGINS.get("go") is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    root = tmp_path / "g"
    root.mkdir()
    (root / "go.mod").write_text("module example.com/g\n\ngo 1.22\n", encoding="utf-8")
    (root / "main.go").write_text(GO, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    net = [str(r["expr"]) for r in store.query("SELECT expr FROM net_calls")]
    assert net == ["http.Get"], net
    store.close()
