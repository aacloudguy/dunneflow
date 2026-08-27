from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dunneflow.resolve.calls import resolve_calls  # noqa: E402
from dunneflow.resolve.cli import resolve_cli  # noqa: E402
from dunneflow.resolve.entrypoints import entrypoints_from_packaging  # noqa: E402
from dunneflow.store import Store  # noqa: E402
from dunneflow.walk import analyze_tree  # noqa: E402

SAMPLE = '''
"""A tiny program with one of everything worth finding."""
import os
import sqlite3
import subprocess
from pathlib import Path

import typer
import requests

app = typer.Typer(name="sample")
admin_app = typer.Typer(name="admin")
app.add_typer(admin_app, name="admin")

SCHEMA = """
CREATE TABLE IF NOT EXISTS widgets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    qty INTEGER DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_widgets_name ON widgets(name);
"""


def load_config(path: str) -> dict:
    # WHY: fails closed when the key is absent. Plan 01-02.
    token = os.environ["API_TOKEN"]
    return {"token": token, "body": Path(path).read_text()}


def save_widget(conn: sqlite3.Connection, name: str, qty: int = 0) -> None:
    conn.execute("INSERT INTO widgets (id, name, qty) VALUES (?, ?, ?)", (name, name, qty))


def read_widgets(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT id, name FROM widgets WHERE qty > 0").fetchall()


def fetch_remote(url: str) -> str:
    return requests.post(url, json={"a": 1}, timeout=5.0).text


def run_tool(name: str) -> int:
    return subprocess.run([name], check=False).returncode


@app.command()
def sync(path: str) -> None:
    """Sync everything."""
    cfg = load_config(path)
    fetch_remote(cfg["token"])
    run_tool("git")


@admin_app.command()
def purge() -> None:
    pass


def main() -> None:
    app()


if __name__ == "__main__":
    main()
'''

PYPROJECT = """
[project]
name = "sample"
version = "0.1.0"
[project.scripts]
sample = "sample:app"
"""


@pytest.fixture(scope="session")
def sample_tree(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("sample_program")
    (root / "sample.py").write_text(SAMPLE, encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return root


@pytest.fixture(scope="session")
def analyzed(sample_tree: Path, tmp_path_factory):
    db = tmp_path_factory.mktemp("graph") / "graph.db"
    store = Store(db)
    analyze_tree(sample_tree, store)
    entrypoints_from_packaging(sample_tree, store)
    resolve_calls(store)
    resolve_cli(store)
    store.optimize()
    yield store
    store.close()
