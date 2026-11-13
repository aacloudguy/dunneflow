"""The map may not depend on the order the rows happen to be in.

**It did, for a year.** Two analyses of Comitia by the same build, minutes apart, wrote
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
from typing import Any

from dunneflow import revisions
from dunneflow.docstore import DocStore
from dunneflow.extractors.docs import extract_doc
from dunneflow.render.markdown import render_all
from dunneflow.resolve.calls import resolve_calls
from dunneflow.resolve.cli import resolve_cli
from dunneflow.resolve.entrypoints import entrypoints_from_packaging
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import serve as serve_mod

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
# the order was taken over, so each of these is one of the ties the Comitia map was found
# to be unstable on, reduced to the smallest program that still has it.
TIES = {
    # Two ways in with the same kind and the same name, in different modules. Comitia has
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
        # Comitia's migrations, both on `audit`. Two files creating one table is the
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


# ====================================================================================== #
# The dashboard.
#
# `web/` was deliberately out of scope when the map was fixed: the deliverable was the
# artifact that gets diffed and handed over. These are the same claim one surface over, and
# `tools/ordering.py --api` is the instrument — asking every route of two copies of one
# program, one of them reversed, with a **fresh `_Live`** per copy because most of the
# dashboard is cached and a third of it is filled before the first request arrives.
#
# What it found on DunneFlow's own tree, none of it visible to the survey and two of the
# three not even in `web/`: `resolve/shape.py` deduplicated the moving things at a line
# before it ordered them, so *which* of two things on one line led it was row order;
# `web/shape.py`'s five worklist lanes all ended `(file, line_start)`, which ties on two
# comprehensions written on one line; and ten of `web/queries.py`'s node and edge queries
# had no `ORDER BY` at all, so the picture itself came back arranged differently.
# ====================================================================================== #

# One tie per line, and every one of them a shape this tool actually reads.
PAIR_ONE = {
    "alpha/__init__.py": "",
    "alpha/__main__.py": '''\
"""The way in."""
import sqlite3
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(name="alpha")
inner = typer.Typer(name="inner")
# **One sub-application mounted under two names.** `_mount_name` takes the first row a
# `LIMIT 1` with no `ORDER BY` returns, so which name the pane prints was row order.
app.add_typer(inner, name="ledger")
app.add_typer(inner, name="books")


@inner.command()
def post(path: str) -> None:
    """A command of the sub-application, so it is a mounted tree rather than an unused
    object -- which is what makes `describe()` ask what name it is mounted under."""
    main(path)


@app.command()
def main(path: str) -> None:
    """Do the thing."""
    conn = sqlite3.connect(path)
    # Two SQL operations on one line, so `_grouped` has two rows to lead with.
    conn.execute("INSERT INTO ledger (id)"); conn.execute("INSERT INTO audit (id)")
    # Two calls on one line: `ROUTINE_CALLEES` ordered on the line alone.
    describe(measure(conn))


def measure(conn):
    """Count what is there."""
    return conn.execute("SELECT id FROM ledger").fetchall()


def audit(conn):
    """A second routine touching the same table, so `TABLE_ROUTINES` returns a list."""
    return conn.execute("SELECT id FROM ledger WHERE id > 0").fetchall()


def sweep(conn):
    """A third caller, so the edge list has something to shuffle."""
    audit(conn)
    measure(conn)
    describe([])


def describe(rows):
    """Say what it is."""
    # **Two comprehensions on one line, each reaching a boundary.** Both are therefore in
    # the `rates` lane with the same number of places, so the lane's key ties on
    # (file, line_start) — which is the real shape found at `tools/ordering.py:169`.
    # Two that move nothing is not the same fixture: neither enters a lane, and the
    # mutation goes uncaught (rule 59).
    return sorted({p.name for p in Path("i").glob("*.md")} | {q.stem for q in Path("o").glob("*")})
''',
    "alpha/work.py": '''\
"""A second module, so a name can be in two."""
import os
# Two names on one line is two `imports` rows on one line, which is what the code
# browser's per-file lists tie on.
from os import environ, getenv


def _cache():
    # AUDIT: LOCK-7
    return getenv("ALPHA_HOME") or environ.get("HOME") or os.getcwd()


def main():
    """A second `main`, which is the commonest tie in any tree."""
    return _cache()


def twin():
    """Declared twice in one module, so two ids share one qualname."""
    return _cache()


def twin():  # noqa: F811 - deliberate, see the docstring above
    """The second declaration. Colliding definitions keep separate identities."""
    return os.getcwd()
''',
    # **The comparison lane's own ties, and they have to be in the *changed* set.**
    # `alpha/work.py`'s two `twin`s tie on (module, qualname) in the map, and for as long
    # as they were identical in both revisions they reached no changed list at all -- so
    # `/api/changes` answered three lists of one row each and the gate passed over a lane
    # that had never been asked a question it could get wrong (rule 37). These move.
    "alpha/shapes.py": '''\
"""Shapes, and the tie `ORDER BY s.module, s.name` cannot break.

A nested class is keyed on the path that reaches it -- `make_id(module.Outer.Config)` --
but its `name` column is the bare `Config` and its `module` is the file. So two classes of
one module each holding a `Config` are two ids with one (module, name), which is the
structure lane's tie and is one of the commonest shapes in Python: `class Meta` in Django,
`class Config` in Pydantic, `class Params` in anything with a settings object.
"""
from dataclasses import dataclass


@dataclass
class Ledger:
    """Where the rows go."""

    id: str

    @dataclass
    class Config:
        """The first of the pair."""

        depth: int = 1


@dataclass
class Audit:
    """What was done to them."""

    id: str

    @dataclass
    class Config:
        """The second, and identical to the first in both the columns the order is
        taken over."""

        depth: int = 1
''',
    # A declared way in, so the command tree has a name of its own. Without it the tree
    # and the `main` in `work.py` are both called `main`, `describe()` matches on the name
    # the row prints, and the sub-application is unreachable through the route.
    "pyproject.toml": '''\
[project]
name = "alpha"
version = "0.1.0"
[project.scripts]
alpha = "alpha.__main__:app"
''',
    "README.md": '''\
# Alpha

What this is for. See PLAN-01 and AC-19.

- `ledger`: where the rows go.
''',
}

# The second revision, so the comparison lane has a pair rather than a short circuit.
#
# **Each edit here exists to put a tie in one of `changes.py`'s ordered lists**, because a
# pair that differs only in distinct names proves what a fixture of distinct names always
# proves: nothing. `_cache` changes so there is a `behaves` row at all; both `twin`s change
# so two of them tie on (module, qualname); `spare` arrives twice so `only_in_base` ties on
# the same key; and both `Config`s gain a field so the structure lanes tie on
# (module, name). Comitia's pair supplies none of these -- see `_pair`.
PAIR_TWO = {
    **PAIR_ONE,
    "alpha/work.py": PAIR_ONE["alpha/work.py"].replace(
        "    return getenv(\"ALPHA_HOME\") or environ.get(\"HOME\") or os.getcwd()",
        "    return getenv(\"ALPHA_HOME\") or os.getcwd()",
    ).replace(
        '    """Declared twice in one module, so two ids share one qualname."""\n'
        "    return _cache()",
        '    """Declared twice in one module, so two ids share one qualname."""\n'
        "    return _cache() or os.sep",
    ).replace(
        '    """The second declaration. Colliding definitions keep separate identities."""\n'
        "    return os.getcwd()",
        '    """The second declaration. Colliding definitions keep separate identities."""\n'
        "    return os.getcwd() or os.sep",
    ) + '''

def extra():
    """Only the second version has this one."""
    return _cache()


def spare():
    """Twice again, and only in this revision -- so both land in `only_in_base`, which is
    the same (module, qualname) order one list over."""
    return _cache()


def spare():  # noqa: F811 - deliberate, as `twin` is
    """The second one."""
    return os.getcwd()
''',
    "alpha/shapes.py": PAIR_ONE["alpha/shapes.py"].replace(
        "        depth: int = 1", "        depth: int = 1\n        width: int = 0"),
}


def _revision(out: Path, tree: Path, files: dict[str, str], rev: str) -> None:
    """One point in time of one program, as `analyze` would leave it."""
    for rel, body in files.items():
        path = tree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    store = Store(revisions.db_path(out, revisions.GRAPH, rev))
    analyze_tree(tree, store)
    entrypoints_from_packaging(tree, store)
    resolve_calls(store)
    resolve_cli(store)
    store.set_meta("revision", rev)
    # Three states and never two: a graph with no `complete` key at all is one written
    # before the key existed and opens fine, but a base built here should say it finished
    # rather than lean on that.
    store.set_meta("complete", "yes")
    store.conn.commit()
    store.close()

    docs = DocStore(revisions.db_path(out, revisions.DOCS, rev))
    docs.set_meta("revision", rev)
    for md in sorted(tree.rglob("*.md")):
        docs.write_doc_facts(extract_doc(md, tree))
    docs.conn.commit()
    docs.close()


def _pair(tmp_path: Path) -> Path:
    """A program directory with two revisions, which the comparison lane needs.

    `/api/changes`, `/api/anomalychanges` and `/api/filechanges` short-circuit on a program
    holding one version — they answer *"this program has one version"* and answer it
    identically whatever the rows are doing. A one-revision fixture would leave three
    routes reported clean without either of them having been asked a question (rule 37).
    """
    out = tmp_path / "prog"
    out.mkdir()
    for i, files in enumerate((PAIR_ONE, PAIR_TWO)):
        tree = tmp_path / f"tree{i}"
        tree.mkdir()
        _revision(out, tree, files, f"2026-08-30T10:0{i}:00Z")
    return out


# **The routes that answer a fact about the run rather than about the map.** Named, and the
# list is of *exceptions*, so a route that starts moving between two readings of one copy
# has to be added here on purpose rather than quietly dropping out of the gate — which is
# what would happen if noise were simply tolerated, because the probe holds a noisy route
# out of its findings (`GET_WITHOUT_BASE`'s own argument, one file over).
KNOWN_NOISE: frozenset[str] = frozenset()


def test_the_dashboard_answers_the_same_whatever_order_the_rows_are_in(tmp_path: Path) -> None:
    """Every route, asked of two copies of one program, one of them reversed.

    Not "the counts match": the whole JSON, because a list that comes back rearranged has
    the same length and says something different — which is exactly what `/api/graph` was
    doing, arranging the picture itself differently for the same program.
    """
    found, noise, vacuous = order.api_probe(_pair(tmp_path))

    assert not vacuous, (
        "these routes were asked nothing, or raised, so nothing about them was checked "
        "and the run is green for no reason (rule 37): " + ", ".join(vacuous))
    assert set(noise) <= KNOWN_NOISE, (
        "these routes differ between two readings of the *same* copy, so the probe cannot "
        "say anything about row order for them: " + ", ".join(sorted(set(noise) - KNOWN_NOISE)))
    assert not found, (
        "these routes depend on the order rows are stored in, which is the order the "
        "process pool happened to finish files in (rule 66): " + ", ".join(sorted(found)))


# The three lanes the fixture plants a tie in, as `(key in the answer, the column that
# names the row)`. Named rather than discovered, so a lane that stops holding its tie is a
# failure here and not a quiet loss of coverage.
TIED_LANES = (("only_in_base", "qualname", "line_start"),
              ("edited_only", "qualname", "line_start"),
              ("structures_declared", "name", "line"))


def _changes(out: Path) -> dict[str, Any]:
    """`/api/changes` over the fixture pair, asked as the probe asks it."""
    graph = revisions.newest(out, revisions.GRAPH)
    assert graph is not None, "the fixture wrote no graph"
    live = serve_mod._Live(out / "source.db", out)
    live.open(graph)
    try:
        plan = order.choose(live)
        assert "/api/changes" in plan, "the fixture pair does not reach the comparison lane"
        return order.ask(live, "/api/changes", plan["/api/changes"][0])
    finally:
        live.close()


def test_the_comparison_lane_is_asked_a_question_it_could_get_wrong(tmp_path: Path) -> None:
    """Rule 37, aimed at the fixture above — and the whole reason this file grew.

    The comparison lane came back clean under a full row reversal for as long as anyone
    had asked it, and on 2026-09-18 that was measured rather than believed: Comitia's pair
    differs in three source files, so `BACKLOG.md` item 2 said the population was thin. A
    pair built from Comitia's `main` against its branch head — **384 files against 628**,
    2,733 rows in `only_in_base` alone — came back clean too, and then held **no tie at
    all**: not one of the five maps to hand declares one name twice in one module, over
    9,972 routines. Neither did this fixture, whose comparison lane answered three lists of
    **one row each**.

    So the lane was clean because it had never been asked a question it could get wrong,
    which is not the same claim and is the one worth gating. These are the ties.
    """
    ans = _changes(_pair(tmp_path))
    for lane, names, _ in TIED_LANES:
        rows = ans.get(lane) or []
        keys = [(r.get("module"), r.get(names)) for r in rows]
        tied = {k for k in keys if keys.count(k) > 1}
        assert tied, (
            f"`{lane}` holds no two rows with one (module, {names}), so the order it is "
            "served in cannot be wrong and the gate over it checks nothing (rule 37)")


def test_two_rows_of_one_name_are_told_apart_by_where_they_are(tmp_path: Path) -> None:
    """A tie is settled by source order and closed by the id, in every lane at once.

    **The row-reversal probe cannot see half of this, and that is the finding.** Four of
    these lists are sorted in Python over a **set** — `both = here_d.keys() & there_d.keys()`
    and the two subtractions beside it — and `sorted` is stable, so rows equal on the key
    keep the order the set iterated in. That order is the hash seed's, not the rows', so
    reversing every table in the store changes nothing about it: measured over 20 seeds
    against the unfixed sort, the two `Config` rows came back one way 12 times and the
    other way 8, while the reversal probe reported the route clean every time. Rule 105.

    So this states the property directly rather than through the instrument: whatever a
    lane holds, it is served in `_settle`'s order, and `_settle` separates rows that
    `(module, name)` cannot.
    """
    from dunneflow.web.changes import _settle

    ans = _changes(_pair(tmp_path))
    for lane, names, line in TIED_LANES:
        rows = ans.get(lane) or []
        by_id = {str(r["id"]): dict(r) for r in rows}
        keys = [_settle(by_id, str(r["id"]), names, line) for r in rows]
        assert len(set(keys)) == len(keys), (
            f"`{lane}` holds two rows the order cannot tell apart, so which comes first is "
            f"whatever wrote first (rule 66): {keys}")
        assert keys == sorted(keys), (
            f"`{lane}` is not served in the order `_settle` gives, so the two are two "
            f"answers rather than one (rule 51): {keys}")


def test_every_route_the_server_answers_is_in_the_population(tmp_path: Path) -> None:
    """The probe walks `ROUTES`, so a route added tomorrow is asked without being listed.

    What can still go wrong is the **exemption** list growing, and that is why it is spelled
    out here rather than described. `NOT_JSON` is the four entries that do not answer JSON —
    two spellings of the shell, the start page, and a 204 with no body — and a fifth name
    added to it would take a route out of the gate with nothing saying so.
    """
    from dunneflow.web.serve import _Handler

    assert frozenset({"/", "/index.html", "/start", "/favicon.ico"}) == order.NOT_JSON
    assert set(_Handler.ROUTES) >= order.NOT_JSON

    out = _pair(tmp_path)
    plan = {}
    graph = revisions.newest(out, revisions.GRAPH)
    assert graph is not None, "the fixture wrote no graph"
    live = serve_mod._Live(out / "source.db", out)
    live.open(graph)
    try:
        plan = order.choose(live)
    finally:
        live.close()
    assert set(plan) <= set(_Handler.ROUTES), (
        "the plan names routes this server does not answer: "
        + ", ".join(sorted(set(plan) - set(_Handler.ROUTES))))
