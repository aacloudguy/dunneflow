"""The map may not depend on the order the rows happen to be in.

**It did, for a year.** Two analyses of Society by the same build, minutes apart, wrote
different documents — 1,488 lines of `06-governance.md`, 656 of `12-traceability.md` — and
every difference was *order* and never content. `analyze_tree` collects facts through
`as_completed`, so which file is written first varies per run and so does every rowid; a
query with no `ORDER BY`, or one ordering on a column with ties, then returns rows in
whatever order the pool happened to finish in. Rule 66: an order the tool cannot defend is
not an order, and these were undefended ties rather than wrong answers.

Nobody noticed, including every session that diffed two maps by hand. The gate that found
it was looking at something else.

**Reversing the rows rather than analysing twice**, for the reason `tools/ordering.py`
gives at length: two real runs shuffle *some* of the order and catch *some* of the ties,
differently each time, which is why `07-database.md` came out stable in one pair and
unstable in the next. Reversal is the worst case and is the same every time, so a map that
survives it survives any order — and a test that finds nothing has actually checked
something (rule 37).

**Sorting the pool's output would not have been a fix**, which is worth stating because it
is what anybody reaches for first. It would keep the parallelism, since results are
accumulated before they are written. It still leaves the defect, because analysis is
**incremental**: a re-analysed file's rows are deleted and appended at the end, so rowid
order tracks the edit history of the tree rather than anything about the program.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

from dunneflow.render.markdown import render_all
from dunneflow.resolve.calls import resolve_calls
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

ROOT = Path(__file__).resolve().parents[1]
# A fixed instant: the cover states when the documents were written, so two
# renders a millisecond apart would differ there and nowhere else. The
# command-line probe normalises that line; here it can simply be pinned.
_WHEN = datetime(2026, 1, 1, tzinfo=UTC)


def _tool():
    path = ROOT / "tools" / "ordering.py"
    spec = importlib.util.spec_from_file_location("_ordering", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


order = _tool()


# **Every file here is a tie somebody actually shipped.** A fixture of distinct names
# proves nothing: the whole defect is what happens when two rows are equal on the column
# the order was taken over, so each of these is one of the ties the Society map was found
# to be unstable on, reduced to the smallest program that still has it.
TIES = {
    # Two ways in with the same kind and the same name, in different modules. Society has
    # exactly this, and `README.md` listed the pair in a different order every run.
    "alpha/__main__.py": (
        "import sqlite3\n\n\n"
        "def main() -> None:\n"
        "    # PLAN: AC-1 the first arm\n"
        "    con = sqlite3.connect('a.db')\n"
        "    con.execute('CREATE TABLE ledger (id TEXT)')\n"
        "    con.execute('CREATE INDEX idx_shared ON ledger (id)')\n"
        "    con.execute('SELECT * FROM ledger')\n\n\n"
        "if __name__ == '__main__':\n    main()\n"
    ),
    "beta/__main__.py": (
        "import sqlite3\n\n\n"
        "def main() -> None:\n"
        "    # PLAN: AC-1 the second arm\n"
        "    con = sqlite3.connect('b.db')\n"
        # **The same index, on the same table, in a second file.** `ORDER BY name` over
        # `db_indexes` was the first site found — `idx_audit_agent` is created in two of
        # Society's migrations, both on `audit`. Two files creating one table is the
        # migration idiom, and it is what puts two rows in the bucket the renderer groups
        # by; an index of the same name on a *different* table lands in a bucket of its
        # own and the tie never arises, which is how the first version of this fixture
        # passed with the defect reintroduced (rule 59).
        "    con.execute('CREATE TABLE ledger (id TEXT, note TEXT)')\n"
        "    con.execute('CREATE INDEX idx_shared ON ledger (id)')\n"
        "    con.execute('SELECT * FROM ledger')\n\n\n"
        "if __name__ == '__main__':\n    main()\n"
    ),
    # One routine name in two modules, one annotation value in two places, and two tables
    # touched exactly as often as each other.
    "alpha/work.py": (
        "import os\n\n\n"
        "def _cache() -> str:\n"
        "    # AUDIT: LOCK-7\n"
        "    return os.getenv('ALPHA_HOME', '')\n"
    ),
    "beta/work.py": (
        "import os\n\n\n"
        "def _cache() -> str:\n"
        "    # AUDIT: LOCK-7\n"
        "    return os.getenv('BETA_HOME', '')\n"
    ),
}


def _program(tmp_path: Path) -> Path:
    root = tmp_path / "prog"
    for rel, body in TIES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def _render(root: Path, db: Path, out: Path, *, flip: bool) -> Path:
    store = Store(db)
    analyze_tree(root, store)
    resolve_calls(store)
    store.conn.commit()
    store.close()
    if flip:
        order.reverse_rows(db)
    store = Store(db, writable=False)
    try:
        render_all(store, out, "prog", when=_WHEN)
    finally:
        store.close()
    return out



def test_the_map_is_the_same_whatever_order_the_rows_are_in(tmp_path):
    """The gate. Byte-identical, not "the counts match" — a total can hold while the
    contents swap, which is exactly what was happening."""
    root = _program(tmp_path)
    straight = _render(root, tmp_path / "a.db", tmp_path / "a", flip=False)
    flipped = _render(root, tmp_path / "b.db", tmp_path / "b", flip=True)

    left = {p.name: p.read_text(encoding="utf-8") for p in straight.glob("*.md")}
    right = {p.name: p.read_text(encoding="utf-8") for p in flipped.glob("*.md")}
    assert set(left) == set(right), "the two renders wrote different documents"
    differing = sorted(n for n in left if left[n] != right[n])
    assert not differing, (
        "these documents depend on the order rows are stored in, which is the order the "
        f"process pool happened to finish files in (rule 66): {', '.join(differing)}")


def test_the_probe_actually_reverses_something(tmp_path):
    """Rule 37, aimed at the instrument — and it caught a real one.

    `tools/ordering.py` globbed `*.db`, then `graph@*.db`, then `docs@*.db`; the first
    already matches the other two, so every graph was reversed and then reversed **back**.
    The probe ran, rendered twice, diffed, and reported *every document is byte-identical*
    over a store it had not touched. An instrument that cannot see cannot report (rule 38),
    and it reported anyway.
    """
    root = _program(tmp_path)
    db = tmp_path / "c.db"
    store = Store(db)
    analyze_tree(root, store)
    store.conn.commit()
    # **By rowid, explicitly.** `SELECT path FROM files` can be answered straight out of
    # an index on `path`, which hands back sorted rows whatever the physical order is —
    # so the obvious spelling of this assertion passes over a store nothing has touched,
    # which is the very failure it was written to catch, one layer down.
    before = [r[0] for r in store.conn.execute("SELECT path FROM files ORDER BY rowid")]
    store.close()

    moved = order.reverse_rows(db)
    assert moved > 1, "nothing was reversed at all"

    store = Store(db, writable=False)
    try:
        after = [r[0] for r in store.conn.execute("SELECT path FROM files ORDER BY rowid")]
    finally:
        store.close()
    assert after == list(reversed(before)), "the rows did not actually move"
    assert sorted(after) == sorted(before), "reversing changed the content, not the order"


def test_meta_is_left_alone(tmp_path):
    """The map's identity is read by key and never by order.

    Rewriting it is the one edit in this probe that could change what the store *means* —
    the schema version, both fingerprints, and whether the analysis finished.
    """
    root = _program(tmp_path)
    db = tmp_path / "d.db"
    store = Store(db)
    analyze_tree(root, store)
    store.conn.commit()
    before = dict(store.conn.execute("SELECT key, value FROM meta"))
    store.close()

    order.reverse_rows(db)
    store = Store(db, writable=False)
    try:
        assert dict(store.conn.execute("SELECT key, value FROM meta")) == before
    finally:
        store.close()
