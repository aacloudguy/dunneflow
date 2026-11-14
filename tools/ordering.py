"""Does anything this tool shows depend on the order the rows happen to be in?

**Two surfaces, one question, and one `reverse_rows`.** The map is the first and was the
whole of this file until 2026-09-18; the dashboard is the second. They are in one file
because the reversal is the instrument and there may only be one of it (rule 51) — and
because `tools/` is deliberately not a package and not on `sys.path`, so a sibling script
could only reach `reverse_rows` by loading this one by path. A third mode, `--survey`,
lists the statements no `ORDER BY` defends, so the population is a reproducible count
rather than a number in a commit message (rule 13).

    uv run python tools/ordering.py output/lictores            # the map
    uv run python tools/ordering.py output/lictores --api      # every GET route, twice
    uv run python tools/ordering.py --survey                   # what to look at

## The map

It did, for a year, and nobody noticed — including every session that diffed two maps by
hand. **Two analyses of Comitia by the same build, minutes apart, differ**: 1,488 lines in
`06-governance.md`, 656 in `12-traceability.md`, and every difference is *order* and never
content. `analyze_tree` collects facts through `as_completed`, so which file is written
first varies per run and so does every rowid; a query with no `ORDER BY`, or one ordering
on a column with ties, then returns rows in whatever order the pool happened to finish in.
Rule 66: an order the tool cannot defend is not an order, and these are undefended ties
rather than wrong answers.

**This probes it by reversing the rows rather than by analysing twice**, and that is the
whole reason it is a usable gate. Two real runs shuffle *some* of the order and catch
*some* of the ties, differently each time — `07-database.md` came out stable in one pair
and unstable in the next, which is what a coin looks like. Reversing every table is the
worst case and is the same every time, so a map that survives it survives any order at all,
and a run that reports nothing has actually checked something (rule 37).

**Reversing is safe, and that was established rather than assumed.** Nothing in either
store declares an `INTEGER PRIMARY KEY`, so no rowid is anybody's key: every identity here
is a `make_id` string, deliberately (`resolve/contract.py` says why). The two places a rowid
is held at all are `resolve/cli.py` and `resolve/calls.py`, each of which reads and updates
inside a single pass. So the
content after a reversal is identical by construction and only the physical order moves.

**Why reversal rather than a stable pool** — which is the fix somebody reaches for first.
Sorting the pool's output would keep the parallelism, since the results are accumulated
before they are written. It still would not be a fix: analysis is **incremental**, so a
re-analysed file's rows are deleted and appended at the end, and rowid order tracks the
edit history of the tree rather than anything about the program. Only a total order on
every rendered list is stable under that, which is what rule 66 asks for anyway.

## The dashboard

`web/` was deliberately out of scope when the map was fixed: the deliverable was the
artifact that gets diffed and handed over, and a pane whose rows come back in a different
order is a different symptom with no baseline to compare against. `--api` is that baseline.
It asks **every route in `_Handler.ROUTES`** of two copies of one program, one of them
reversed, and diffs the JSON — the same argument one surface over, with three differences
that the map does not have:

* **A route takes parameters, and both sides must be asked the same question.** They are
  chosen once, from the *straight* copy, by an ordered query. Chosen per copy they would
  differ, and the probe would be comparing two answers to two questions.
* **Most of the dashboard is cached, and a third of it before the first request arrives.**
  So each copy gets a **fresh `_Live`**, which is the only thing that resets both layers —
  the four dicts `PROGRAM_CACHES` names and the `_Base` fields built inside `open()`.
  Asking twice on one `_Live` compares an object with itself and reports nothing (rule 37).
* **A route with no parameter is refused by name, never skipped.** Eight of them answer
  `{"found": false}` to an empty query, which diffs clean while checking nothing — rule 49
  in an instrument.

## The survey

`--survey` is the third mode and it decides nothing; it says where to look. The first
survey of `web/` reported *six literal `SELECT`s with no `ORDER BY`* and was wrong in both
directions: `ast.literal_eval` fails on an f-string, so every query built with an
`IN ({marks})` placeholder — which is most of the interesting ones — was invisible to it,
and it **excluded `LIMIT 1`**, which is exactly backwards, because a `LIMIT` with no order
does not reorder a list, it picks a different answer. It also over-counted, exempting
nothing. So this joins an f-string's literal parts, treats `LIMIT` as the sharpest finding
there is, and exempts on two grounds only — an aggregate with no `GROUP BY`, and a lookup
whose `WHERE` equates **a whole declared key**. The keys are read out of the three
`SCHEMA_SQL` constants rather than guessed at from the shape of a column name (rule 51):
`id = ?` is exempt because `routines.id` is a primary key, and would not be if it were not.

    uv run python tools/ordering.py output/lictores
    uv run python tools/ordering.py output/lictores --show 06-governance.md
    uv run python tools/ordering.py output/lictores --api
    uv run python tools/ordering.py --survey
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from dunneflow import revisions
from dunneflow.docstore import DOC_SCHEMA_SQL
from dunneflow.runtime import self_argv
from dunneflow.sourcedb import SCHEMA_SQL as SOURCE_SCHEMA_SQL
from dunneflow.store import SCHEMA_SQL as GRAPH_SCHEMA_SQL

# The one line that is *meant* to differ between two renders of one snapshot. The snapshot
# instant and the source-read instant are facts about the analysis and are identical in
# both copies; only *when these documents were written* is a fact about the render, and the
# cover states three instants on purpose (see `render/`). Normalised rather than dropped, so
# a document that differs **only** here still reads as a document that differed nowhere.
WRITTEN = re.compile(r"written \d{4}-\d\d-\d\d \d\d:\d\d UTC")


def reverse_rows(db: Path) -> int:
    """Flip the physical order of every table, keeping every row exactly as it was.

    `meta` is left alone: it is the map's identity — the schema version, the two
    fingerprints, whether the analysis finished — read by key and never by order, and
    rewriting it would be the one edit here that could change what the store *means*.
    """
    conn = sqlite3.connect(db)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        moved = 0
        for t in names:
            if t == "meta":
                continue
            conn.execute(f'CREATE TEMP TABLE _flip AS SELECT * FROM "{t}" ORDER BY rowid DESC')
            conn.execute(f'DELETE FROM "{t}"')
            conn.execute(f'INSERT INTO "{t}" SELECT * FROM _flip')
            conn.execute("DROP TABLE _flip")
            moved += 1
        conn.commit()
        return moved
    finally:
        conn.close()


def render(program: Path) -> Path:
    """Write this program's map from the graph it already has, and return the map dir."""
    for old in program.glob("map@*"):
        shutil.rmtree(old)
    done = subprocess.run([*self_argv(), "render", str(program)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        said = (done.stderr or done.stdout or "").strip().splitlines()
        raise SystemExit(f"could not render {program}:\n  "
                         + (said[-1] if said else "it said nothing"))
    made = sorted(program.glob("map@*"))
    if not made:
        raise SystemExit(f"{program} rendered nothing, so there is nothing to compare")
    return made[0]


def _lines(path: Path) -> list[str]:
    return [WRITTEN.sub("written <when>", line)
            for line in path.read_text(encoding="utf-8").splitlines()]


def compare(a: Path, b: Path) -> dict[str, list[str]]:
    """Per document, the unified diff of the two renders, or nothing at all."""
    out: dict[str, list[str]] = {}
    names = sorted({p.name for p in a.glob("*.md")} | {p.name for p in b.glob("*.md")})
    for name in names:
        left = _lines(a / name) if (a / name).exists() else []
        right = _lines(b / name) if (b / name).exists() else []
        d = [ln for ln in difflib.unified_diff(left, right, lineterm="", n=1)
             if ln[:1] in "+-" and ln[:3] not in ("---", "+++")]
        if d:
            out[name] = d
    return out


def probe(program: Path, keep: Path | None = None) -> dict[str, list[str]]:
    """Render this program twice — as it is, and with every row reversed.

    Both copies are rendered, rather than one being compared against the map `analyze`
    already wrote. The map on disk was written by a different command at a different
    instant, and comparing against it would fold *did the renderer change* into *does the
    order matter* — two questions, one answer, and no way to tell which one moved.
    """
    with tempfile.TemporaryDirectory(prefix="dunneflow-order-") as tmp:
        where = Path(keep) if keep else Path(tmp)
        where.mkdir(parents=True, exist_ok=True)
        straight, flipped = where / "straight", where / "flipped"
        for d in (straight, flipped):
            if d.exists():
                shutil.rmtree(d)
            shutil.copytree(program, d)
        # **One glob, and it has to be one.** This was three — `*.db`, then `graph@*.db`,
        # then `docs@*.db` — and the first already matches the other two, so every graph
        # was reversed and then reversed back. The probe ran, rendered twice, diffed, and
        # reported *every document is byte-identical* over a store it had not changed:
        # rule 37 in the instrument, which is the one place it costs most (rule 38).
        for db in sorted(flipped.glob("*.db")):
            reverse_rows(db)
        return compare(render(straight), render(flipped))


def _programs(where: Path) -> Iterable[Path]:
    """Every analysed program under `where`, or `where` itself if it is one."""
    if revisions.holds_a_map(where):
        return [where]
    return revisions.programs_under(where)


# ======================================================================================
# The survey — which statements no `ORDER BY` defends.
# ======================================================================================

WEB = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"
# **The whole package, and `--at` does not move it.** The `ORDER BY` survey defaults to
# `web/` because that is where the statements are and it reads one directory; rule 105's
# question is about `sorted()` and is asked of every module there is, recursively. One
# command reading two extents is worth naming rather than leaving to be discovered.
PKG = WEB.parent

# An aggregate over a whole population returns one row, and one row has no order. `GROUP
# BY` is what turns it back into a list, which is why the exemption names it.
AGGREGATES = ("COUNT(", "SUM(", "MAX(", "MIN(", "AVG(", "TOTAL(", "GROUP_CONCAT(")

# What a computed part of an f-string is rendered as. Not blanked and not dropped: a
# reader of this report has to be able to see that something was substituted there, and
# `IN ({})` says so where `IN ()` looks like a statement somebody wrote wrong.
HOLE = "{}"

_TABLE_BLOCK = re.compile(r"CREATE TABLE(?: IF NOT EXISTS)? (\w+)\s*\((.*?)\n\);", re.S)
_UNIQUE_INDEX = re.compile(
    r"CREATE UNIQUE INDEX(?: IF NOT EXISTS)? \w+\s+ON\s+(\w+)\s*\(([^)]*)\)", re.S)
_INLINE_KEY = re.compile(r"^\s*(\w+)\s+\w+[^,]*?\b(?:PRIMARY KEY|UNIQUE)\b", re.M)
_TABLE_KEY = re.compile(r"^\s*(?:PRIMARY KEY|UNIQUE)\s*\(([^)]*)\)", re.M)
_NAMES_A_TABLE = re.compile(r"(?:FROM|JOIN)\s+(?:\{\}\.)?([A-Za-z_]\w*)", re.I)
# **What counts as equating a column to one value.** This read `= ?` alone to begin with,
# and `web/` binds by name at least as often: `WHERE path = :p` and `WHERE id = :id` both
# came back as findings — a key lookup reported as a list, by an instrument that could not
# see the placeholder in front of it (rule 38). A quoted literal is here for the same
# reason and not as a convenience: `WHERE key = 'layout_fingerprint'` selects one row of
# `meta` exactly as a bound parameter would, and what makes it one row is the key, not how
# the value arrived. A column equated to *another column* is a join condition and is
# deliberately not matched.
_EQUATED = re.compile(r"(?:\w+\.)?(\w+)\s*=\s*(?:\?\d*|[:@$]\w+|'[^']*'|\d+)")


@dataclass(frozen=True)
class Site:
    """One statement, and why it is or is not a finding."""

    file: str
    line: int
    verdict: str
    finding: bool
    sql: str


def _without_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))


def declared_keys() -> dict[str, set[frozenset[str]]]:
    """Every whole key each table declares, read out of the schemas themselves.

    The exemption this feeds is *a lookup by a unique key*, and the temptation is to spell
    it `id = ?` — which is a guess about a column name dressed up as a rule. `routines.id`
    is exempt because `routines` declares it a primary key; a column called `id` in a table
    that does not would not be, and neither spelling has to be maintained here (rule 51).

    A key is a **set** because `params` declares `PRIMARY KEY (routine_id, idx)`: equating
    one half of it selects a list, and only equating both selects a row.
    """
    keys: dict[str, set[frozenset[str]]] = {}
    for schema in (GRAPH_SCHEMA_SQL, DOC_SCHEMA_SQL, SOURCE_SCHEMA_SQL):
        clean = _without_comments(schema)
        for table, body in _TABLE_BLOCK.findall(clean):
            here = keys.setdefault(table.lower(), set())
            for col in _INLINE_KEY.findall(body):
                here.add(frozenset({col.lower()}))
            for cols in _TABLE_KEY.findall(body):
                here.add(frozenset(c.strip().lower() for c in cols.split(",") if c.strip()))
        for table, cols in _UNIQUE_INDEX.findall(clean):
            keys.setdefault(table.lower(), set()).add(
                frozenset(c.strip().lower() for c in cols.split(",") if c.strip()))
    return keys


def sql_text(node: ast.AST) -> str:
    """The SQL a node spells, with every computed part rendered as `{}`.

    **Joining an f-string's literal parts is the half the first survey did not have.**
    `ast.literal_eval` raises on a `JoinedStr` and that survey skipped whatever it raised
    on, so every query built with an `IN ({marks})` placeholder — which is most of the ones
    worth looking at — was invisible to the instrument written to find them (rule 38).
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else ""
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value if isinstance(part, ast.Constant) and isinstance(part.value, str)
            else HOLE
            for part in node.values)
    return ""


def _flat(sql: str) -> str:
    return " ".join(sql.split()).upper()


def _is_select(flat: str) -> bool:
    """A statement that returns rows, and not prose that mentions one."""
    return flat.startswith("SELECT ") or (flat.startswith("WITH ") and " SELECT " in flat)


def _one_row_by_key(flat: str, keys: dict[str, set[frozenset[str]]]) -> str:
    """The key this statement equates in full, or `""` if it equates none.

    Every table the statement names is asked, because the equated columns are not
    attributed to a table here — a join that equates a whole key of *either* side is still
    reaching for one row of it, and the blind spot is stated rather than papered over: a
    statement joining two tables and equating one's key selects one row of that table and
    however many of the other. Such a statement is exempt here and should not be; there
    are none in `web/`, and if one arrives the probe is what will say so.
    """
    equated = {c.lower() for c in _EQUATED.findall(flat.lower())}
    if not equated:
        return ""
    for table in {t.lower() for t in _NAMES_A_TABLE.findall(flat)}:
        for key in keys.get(table, ()):
            if key <= equated:
                return f"{table}({', '.join(sorted(key))})"
    return ""


def classify(sql: str, keys: dict[str, set[frozenset[str]]]) -> tuple[str, bool]:
    """Why this statement is a finding, or which exemption clears it."""
    flat = _flat(sql)
    if "ORDER BY" in flat:
        return "ordered", False
    # **The sharpest form, and the one the first survey exempted.** A `LIMIT` with no order
    # does not shuffle a list a reader can still read; it picks a different answer and
    # throws the others away, with nothing on the screen saying a choice was made.
    if "LIMIT" in flat:
        return "LIMIT with no ORDER BY", True
    if any(agg in flat for agg in AGGREGATES) and "GROUP BY" not in flat:
        return "one row: an aggregate with no GROUP BY", False
    by_key = _one_row_by_key(flat, keys)
    if by_key:
        return f"one row: a lookup by {by_key}", False
    return "no ORDER BY", True


def survey(where: Path) -> list[Site]:
    """Every statement in every module under `where`, classified.

    Exemptions are **returned, not filtered** — design rule 1, in an instrument. A survey
    that prints only its findings cannot be checked against the tree it read, and the two
    numbers that matter most about this one are how many statements it saw at all and how
    many it let through.
    """
    keys = declared_keys()
    out: list[Site] = []
    for path in sorted(where.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # A `JoinedStr` holds `Constant` children, and `ast.walk` reaches both — so the
        # literal parts of every f-string would be counted a second time, each of them a
        # fragment with no `ORDER BY` in it. Only the outermost node is the statement.
        inside = {id(part) for node in ast.walk(tree) if isinstance(node, ast.JoinedStr)
                  for part in ast.walk(node) if part is not node}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant | ast.JoinedStr) or id(node) in inside:
                continue
            sql = sql_text(node)
            if not _is_select(_flat(sql)):
                continue
            verdict, finding = classify(sql, keys)
            out.append(Site(path.name, node.lineno, verdict, finding, " ".join(sql.split())))
    return out


def report_survey(sites: list[Site], where: Path, width: int = 200) -> None:
    """The findings, then what was exempted and on what grounds, then the denominator."""
    findings = [s for s in sites if s.finding]
    for s in sorted(findings, key=lambda s: (s.file, s.line)):
        print(f"   {s.file + ':' + str(s.line):<18} {s.verdict:<22} {s.sql[:width]}")
    print(f"\n   {len(findings)} findings in {len({s.file for s in findings})} files")
    for verdict in sorted({s.verdict for s in sites}):
        n = sum(1 for s in sites if s.verdict == verdict)
        mark = "!!" if any(s.finding for s in sites if s.verdict == verdict) else "  "
        print(f"   {mark} {n:>4}  {verdict}")
    print(f"\n   {len(sites)} statements read, in {len(sorted(where.glob('*.py')))} modules")


# **The second population, and the reversal cannot see any of it (rule 105).** `sorted()`
# is stable, so rows equal on the key keep the order they arrived in — and when what
# arrived is a **set**, a `dict.keys()` intersection or a set comprehension, that order is
# CPython's hash order and so the hash seed's. Reversing every row in the store moves it not
# at all: measured over 20 seeds against `web/changes.py`'s unfixed structure sort, two rows
# tied on `(module, name)` came back one way 12 times and the other way 8, with the route
# reported clean on every one of them.
#
# So this is listed beside the `ORDER BY` survey rather than probed, and like that one it
# **decides nothing**. A `sorted(a_set)` with no `key=` is total by definition and is
# counted and not shown; a `key=` is where a non-total one can hide, and whether it is total
# is a question about that key that only a reader can answer.
#
# It reads the source rather than the behaviour for the same reason the other survey does,
# and it is a **floor rather than the population**: unorderedness propagates, so a dict built
# by iterating a set and then sorted over its `.items()` is the same defect and is invisible
# here. `web/changes.py` held two of each.
_UNORDERED_CALLS = {"set", "frozenset"}


@dataclass(frozen=True)
class SetSort:
    """One `sorted()` handed something that has no order of its own."""

    file: str
    line: int
    keyed: bool
    source: str


def set_sorts(where: Path) -> list[SetSort]:
    """Every `sorted()` in `where` whose input is a set, by the shape of the expression."""
    out: list[SetSort] = []
    for path in sorted(where.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "sorted" and node.args):
                continue
            arg, kind = node.args[0], ""
            if isinstance(arg, ast.BinOp) and isinstance(
                    arg.op, ast.BitAnd | ast.BitOr | ast.Sub):
                kind = "set algebra"
            elif isinstance(arg, ast.SetComp | ast.Set):
                kind = "a set literal"
            elif (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name)
                  and arg.func.id in _UNORDERED_CALLS):
                kind = f"{arg.func.id}()"
            if kind:
                rel = path.relative_to(where.parent) if where.parent in path.parents else path
                out.append(SetSort(str(rel), node.lineno,
                                   any(k.arg == "key" for k in node.keywords), kind))
    return out


def report_set_sorts(sites: list[SetSort]) -> None:
    """The keyed ones, then the denominator. The unkeyed are counted and not listed."""
    keyed = [s for s in sites if s.keyed]
    for s in sorted(keyed, key=lambda s: (s.file, s.line)):
        print(f"   {s.file + ':' + str(s.line):<44} over {s.source}")
    print(f"\n   {len(keyed)} of {len(sites)} take a `key=`, which is where a key that does "
          "not separate every member can hide")
    print(f"   {len(sites) - len(keyed)} take none, and sorting a set by its own values "
          "is total by definition")


# ======================================================================================
# The dashboard — every route, asked twice.
# ======================================================================================

# The four entries in `ROUTES` that do not answer JSON: two spellings of the shell, the
# start page, and a 204 with no body at all. Named rather than detected, so a fifth one
# has to be added here on purpose.
NOT_JSON = frozenset({"/", "/index.html", "/start", "/favicon.ico"})

# **The one key that is a measurement rather than an answer**, and the sibling of `WRITTEN`
# one surface over. `/api/search`, `/api/changes`, `/api/filechanges` and
# `/api/anomalychanges` each report how long they took, so each of them differs between
# any two readings of one copy — and the probe holds a noisy route *out* of its findings,
# so leaving it would take four routes out of the gate for ever and report the run green
# (rule 37).
#
# Normalised by name and by nothing else. The three-pass noise floor below is what makes
# that safe: it is still measured rather than assumed, so a second volatile key arriving
# tomorrow shows up as noise and fails the gate instead of being quietly forgiven.
MEASURED = re.compile(r'"ms": -?\d+(?:\.\d+)?')

# The separator `diagram.dot` writes into an edge id, and the reason the split below is on
# the **first** occurrence: no box id may contain one, which `web/diagram.py` asserts over
# the whole program.
ARROW = "=>"


class _Cap:
    """Enough of a handler to call one route and keep what it answered.

    The shape `tests/test_stated.py` and `tests/test_about.py` already use. A route touches
    exactly two things on `self` — `_live` and one of the two ways out — so a socket is not
    needed to ask one, and asking over HTTP would put a server, a port and a thread between
    the question and the answer for no gain.

    `send_error` is here because two routes reach for it: `/api/graph` and `/api/plateorder`
    refuse an unknown `level` with a 400 rather than defaulting it. A cap without one turns
    that refusal into an `AttributeError` and the probe into an instrument that cannot ask
    about a third of the query strings a reader can type.

    **And `__getattr__` hands back the handler's own helper, bound to this cap.** A route
    is not only `self._live` and one way out: `_r_diagram`, `_r_fold` and `_r_inside` all
    call `self._compartments()`, and `_r_anomalies` calls `self._findings()`. Each reads
    `self._live` and nothing else, so the real one is the right one to run — writing a
    second `_compartments` here would be a second answer to a question the server already
    answers, which is the thing this whole file exists to look for (rule 51). What is
    replaced is the two ways out and nothing else.
    """

    def __init__(self, live: Any) -> None:
        self._live = live
        self.body: dict[str, Any] = {}

    def _json(self, body: dict[str, Any]) -> None:
        self.body = body

    def send_error(self, code: int, message: str | None = None,
                   explain: str | None = None) -> None:
        self.body = {"refused": code, "message": message, "explain": explain}

    def __getattr__(self, name: str) -> Any:
        from dunneflow.web.serve import _Handler

        held = getattr(_Handler, name, None)
        if not callable(held):
            raise AttributeError(name)
        return partial(held, self)


def ask(live: Any, route: str, query: dict[str, list[str]]) -> dict[str, Any]:
    """One route, asked of one base. What it answered, or what it raised.

    A raise is **kept rather than caught away**. If a route raises the same way on both
    copies that is not a difference and not this probe's business; if it raises on one copy
    only, the order decided whether the dashboard worked, which is the worst finding there
    is and the one a `try` that returned `{}` would report as *no difference*.
    """
    from dunneflow.web.serve import _Handler

    cap = _Cap(live)
    try:
        getattr(_Handler, _Handler.ROUTES[route])(cap, query)
    except Exception as exc:  # noqa: BLE001 - see the docstring
        return {"raised": f"{type(exc).__name__}: {exc}"}
    return cap.body


def _first(live: Any, sql: str) -> str:
    """The first value an ordered statement returns, or `""`.

    Every caller spells its own `ORDER BY`, and that is the point rather than an oversight:
    a probe that picked its parameters out of an unordered query would choose them by the
    very thing it is measuring, and the two copies would be asked different questions.
    """
    with live.lock:
        rows = list(live.current.store.query(sql, ()))
    return str(rows[0][0]) if rows else ""


def _all(live: Any, sql: str) -> list[str]:
    """Every first value an ordered statement returns. `_first`'s argument, plural."""
    with live.lock:
        return [str(r[0]) for r in live.current.store.query(sql, ())]


def choose(live: Any) -> dict[str, list[dict[str, list[str]]]]:
    """What to ask each route, decided once against the straight copy.

    **Once, and against one copy.** The parameters are part of the question, so deriving
    them per copy would ask the flipped base about its own first row and the straight base
    about its own — two questions, one comparison, and an answer that means nothing.

    A route may be asked more than once, because several of them answer a different *shape*
    depending on what they are given: `/api/search` with a path returns lines and without
    one returns files, `/api/diagram` with an id returns a drawing and without one the
    index, and `/api/filechanges` with a path is the line diff and without it the summary.
    Asking only the cheap form would leave the expensive one unprobed while reporting a
    clean run.
    """
    # **The busiest routine, not the first by id.** A tie needs two rows to tie, so the
    # routine a probe learns most from is the one with the most of them — and `ORDER BY id`
    # picks a hash, which on a real program is as likely as not to be something with one
    # call in it. Deterministic either way; this one is also informative.
    routine = _first(live, "SELECT caller_id FROM calls WHERE caller_id <> ''"
                           " GROUP BY caller_id ORDER BY COUNT(*) DESC, caller_id")
    # **The busiest file, not the first one.** `alpha/__init__.py` sorts first and is
    # empty, so `/api/file` and `/api/search` were asked about a file with nothing in it
    # and came back identical for the best of reasons — a parameter that selects nothing
    # is the same failure as no parameter at all, one level in (rule 37).
    path = _first(live, "SELECT file FROM routines WHERE file <> '' GROUP BY file"
                        " ORDER BY COUNT(*) DESC, file")
    # **A second file, chosen to hold the most imports**, because the busiest file by
    # routines is rarely the one with two names imported on one line — and a per-file list
    # ordered on the line alone ties exactly there. Two asks on one route, on
    # `/api/search`'s precedent: a route with two shapes is two questions.
    imported = _first(live, "SELECT file FROM imports WHERE file <> '' GROUP BY file"
                            " ORDER BY COUNT(*) DESC, file") or path
    # A table this program **touches**, if it declares none. `web/table.py` answers for
    # both on purpose — "12 of Comitia's 65 tables are read and never declared" — so a
    # probe that only ever asked about a declared one would leave the commoner half unasked.
    table = (_first(live, "SELECT name FROM db_tables ORDER BY name")
             or _first(live, "SELECT tbl FROM sql_ops WHERE tbl <> '' ORDER BY tbl"))
    # Never `<module>`: it is a routine name in every map, it sorts before every real one,
    # and a search for it finds a line in no file. A term has to be a word somebody wrote.
    term = _first(live, "SELECT name FROM routines WHERE length(name) > 5 "
                        "AND name NOT LIKE '<%' ORDER BY name")

    plan: dict[str, list[dict[str, list[str]]]] = {
        "/api/graph": [{}, {"level": ["module"]}],
        "/api/plateorder": [{}, {"grouped": ["1"]}],
        "/api/diagram": [{}],
        "/api/node": [{"id": [routine]}],
        "/api/hover": [{"id": [routine]}],
        "/api/shape": [{"node": [routine]}],
        "/api/threads": [{"id": [routine]}],
        "/api/reldocs": [{"node": [routine]}],
        "/api/file": [{"path": [path]}, {"path": [imported]}],
        "/api/source": [{"path": [path]}],
        "/api/search": [{"q": [term]}, {"q": [term], "path": [path]}],
        "/api/table": [{"name": [table]}],
    }

    # A plate, a box and an arrow are not in the store as ids -- they are made by the model
    # the payload is built from -- so they are read off the straight copy's own answers,
    # sorted. Sorted rather than first-served for the reason `_first` spells out.
    payload = ask(live, "/api/graph", {})
    disks = sorted(str(d.get("id", "")) for d in payload.get("disks", []) if d.get("id"))
    if disks:
        plan["/api/plate"] = [{"id": [disks[0]]}]

    index = ask(live, "/api/diagram", {})
    comps = sorted(str(c["id"]) for c in index.get("compartments", []) if c.get("id"))
    if comps:
        plan["/api/diagram"].append({"id": [comps[0]]})
        drawn = ask(live, "/api/diagram", {"id": [comps[0]]})
        boxes = sorted(str(b) for b in drawn.get("by_id", {}))
        if boxes:
            plan["/api/fold"] = [{"id": [boxes[0]]}]
            plan["/api/inside"] = [{"id": [boxes[0]]}]
        edges = sorted(str(e) for e in drawn.get("edges", {}) if ARROW in str(e))
        if edges:
            src, dst = edges[0].split(ARROW, 1)
            plan["/api/flow"] = [{"from": [src], "to": [dst]}]

    # **A thread's kind and key are on its `subject`, not on the thread**, and only a
    # `cohort` subject has them at all — the others are already a node and are selected as
    # themselves, which is what `_r_thread` says in so many words. Read off the thread it
    # asked the wrong object and every value came back `None`, so `/api/thread` was asked
    # `kind=boundary&key=` and answered *"a thread needs both"*, identically, twice.
    #
    # Every routine, not the first one: a cohort thread fires rarely by design — the table
    # thread on 8 routines of Comitia's 4,823 — so asking one routine is how a lane that
    # exists goes unprobed.
    subjects: set[tuple[str, str]] = set()
    for rid in _all(live, "SELECT id FROM routines ORDER BY id"):
        for th in ask(live, "/api/threads", {"id": [rid]}).get("threads", []):
            s = th.get("subject") or {}
            if s.get("type") == "cohort" and s.get("kind") and s.get("key"):
                subjects.add((str(s["kind"]), str(s["key"])))
    if subjects:
        kind, key = sorted(subjects)[0]
        plan["/api/thread"] = [{"kind": [kind], "key": [key]}]

    docs = ask(live, "/api/docs", {})
    paths = sorted(str(d.get("path", "")) for d in docs.get("documents", []) if d.get("path"))
    if paths:
        plan["/api/doc"] = [{"path": [paths[0]]}]
        plan["/api/docsource"] = [{"path": [paths[0]]}]

    mine = ask(live, "/api/documents", {})
    sections = sorted(str(s.get("id", "")) for s in mine.get("documents", []) if s.get("id"))
    if sections:
        plan["/api/document"] = [{"id": [sections[0]]}]

    ways = ask(live, "/api/cover", {})
    names = sorted(str(w.get("name", "")) for w in ways.get("entrypoints", []) if w.get("name"))
    if names:
        plan["/api/wayin"] = [{"name": [names[0]]}]
        # **The second shape of the route, and it is the one that reaches `_mount_name`.**
        # Without `inside` the pane describes the way in; with it, the sub-application
        # mounted on it — which is where the name a tree is mounted under is asked for, and
        # that was a `LIMIT 1` with no order. Asking only the first shape left the branch
        # the survey called *certain* unprobed, with the route reported clean: a route is
        # not a branch, and a probe that asks one query string per route says nothing about
        # the others (rule 37).
        for name in names:
            opened = ask(live, "/api/wayin", {"name": [name]})
            groups = sorted(str(g.get("child_id", "")) for g in opened.get("groups", [])
                            if g.get("child_id"))
            if groups:
                plan["/api/wayin"] = [{"name": [name]},
                                      {"name": [name], "inside": [groups[0]]}]
                break

    # The comparison lane needs two revisions and short-circuits on one, so it is asked
    # only where there is a pair -- and the pair is named rather than defaulted, because
    # `_pick`'s default is *the next comparable one*, which is a fact about the listing.
    revs = sorted(str(r.get("revision", ""))
                  for r in ask(live, "/api/revisions", {}).get("revisions", [])
                  if r.get("revision"))
    if len(revs) > 1:
        plan["/api/changes"] = [{"base": [revs[-1]], "compared": [revs[0]]}]
        plan["/api/anomalychanges"] = [{"base": [revs[-1]], "compared": [revs[0]]}]
        plan["/api/filechanges"] = [{"compared": [revs[0]]},
                                    {"compared": [revs[0]], "path": [path]}]
    return plan


def ask_all(program: Path, plan: dict[str, list[dict[str, list[str]]]]) -> dict[str, str]:
    """Every JSON route of this copy, asked, as `route?query -> JSON`.

    **A fresh `_Live` per copy, and that is the whole of why this works.** Most of the
    dashboard is cached and about a third of it is filled before the first request arrives
    -- `cover`, `files`, `naming`, `stated`, `checked` and `glossary` are built inside
    `open()`. Asking one base twice would compare those objects with themselves and report
    a clean run over a store nobody had questioned twice (rule 37).

    A route in `ROUTES` with nothing in the plan and no parameters is asked with an empty
    query, which is what a reader asking it would send. A route that *needs* one and has
    none is **refused by name** in `main`, never skipped: eight of them answer
    `{"found": false}` to an empty query, and a probe that accepted that would be diffing
    two identical refusals and calling the route clean (rule 49).
    """
    from dunneflow.web.serve import _Handler, _Live

    graph = revisions.newest(program, revisions.GRAPH)
    if graph is None:
        raise SystemExit(f"{program} holds no graph, so there is nothing to serve")
    live = _Live(program / "source.db", program)
    live.open(graph)
    try:
        out: dict[str, str] = {}
        for route in sorted(_Handler.ROUTES):
            if route in NOT_JSON:
                continue
            for query in plan.get(route, [{}]):
                key = route + ("?" + urlencode(query, doseq=True) if query else "")
                said = json.dumps(ask(live, route, query), indent=1, sort_keys=False)
                # **Where this copy lives is not a fact about the map.** The two copies are
                # two directories by construction, and `/api/programs`, `/api/about` and
                # `/api/base` all report the root they were opened from — so without this
                # the probe reports its own scaffolding as a finding, every run, on every
                # program. The program before its root, because one contains the other.
                # Masked as the text holds it, which is JSON: a Windows root arrives with
                # each separator doubled (`C:\\Users`), so the raw `str()` never matched
                # there, and the probe reported the two copies' homes as an ordering defect.
                for path, mask in ((program, "<program>"), (program.parent, "<root>")):
                    said = said.replace(json.dumps(str(path))[1:-1], mask)
                out[key] = MEASURED.sub('"ms": <measured>', said)
        return out
    finally:
        live.close()


def _diff(left: dict[str, str], right: dict[str, str]) -> dict[str, list[str]]:
    """Per route, the unified diff of the two answers, or nothing at all."""
    out: dict[str, list[str]] = {}
    for key in sorted(set(left) | set(right)):
        d = [ln for ln in difflib.unified_diff(
            left.get(key, "").splitlines(), right.get(key, "").splitlines(),
            lineterm="", n=1)
            if ln[:1] in "+-" and ln[:3] not in ("---", "+++")]
        if d:
            out[key] = d
    return out


def unasked(answers: dict[str, str]) -> list[str]:
    """Routes that answered nothing, and so were never actually probed.

    **Two shapes, and both of them diff clean.** Eight routes reply
    `{"found": false, "reason": "no id asked for"}` to an empty query, so a plan that
    forgot one compares two identical refusals and reports the route sound. And a route
    that *raises* — because the plan handed it something it cannot use, or because the cap
    is missing a helper it calls — raises the same way on both copies and compares equal
    too. Both are rule 37 in the instrument: a green run over a question nobody asked.

    So neither is allowed to pass silently. They are named, and they fail the run.
    """
    out = []
    for key, body in answers.items():
        try:
            answered = json.loads(body)
        except json.JSONDecodeError:  # pragma: no cover - `_json` produced it
            continue
        if not isinstance(answered, dict):
            continue
        if "raised" in answered:
            out.append(f"{key} [{answered['raised']}]")
        elif "?" not in key and answered.get("found") is False:
            out.append(key)
        elif "=&" in key or key.endswith("="):
            # **A parameter that came back empty is no parameter**, and it is the harder
            # one to see: the route is in the plan, the query string is there, and the
            # answer is a refusal that is identical on both copies. It happened twice --
            # `/api/table?name=` on a program that declares no table, and a `path` that
            # sorted first and was an empty `__init__.py`.
            out.append(f"{key} [nothing was chosen for a parameter]")
    return sorted(out)


def api_probe(program: Path, keep: Path | None = None) -> tuple[
        dict[str, list[str]], dict[str, list[str]], list[str]]:
    """Ask every route of this program three times: twice straight, once reversed.

    **Three passes and not two, because an instrument has to know its own noise floor.**
    Some of what a route answers is a fact about the run rather than about the map, and the
    alternative to measuring that is a hand-kept list of keys to forgive — which is a list
    somebody has to be right about, once, for ever, and which forgives a real finding the
    day a volatile key grows a real one underneath it.

    So the straight copy is asked twice. What differs between those two answers is **noise**
    and is named as such; what differs under the reversal and *not* between them is a
    finding. A route that does both is reported as noise, because nothing can be concluded
    about it until the noise is gone — and saying so is the honest answer, where picking one
    of the two would be a guess (rule 49).
    """
    with tempfile.TemporaryDirectory(prefix="dunneflow-api-order-") as tmp:
        where = Path(keep) if keep else Path(tmp)
        where.mkdir(parents=True, exist_ok=True)
        # **Deliberately *not* resolved, and that is a change from how this was written.**
        # `/tmp` and `/var/folders` are both symlinks on macOS, so a temporary directory
        # is a symlinked maps root for free — which is the one shape `_r_programs` used to
        # get wrong, unioning a *resolved* `out_dir` with an unresolved listing and so
        # naming every program twice. This probe met that on its first run and reported it
        # as an ordering finding, and resolved its own paths to get past it. The defect is
        # closed in `revisions.program_dirs`, so the workaround comes out and the shape it
        # was hiding from becomes coverage: a probe that canonicalises its own root can
        # never see that class of defect return (rule 43).
        # **A root of its own each, and the leaf named the same in both.** Side by side
        # under one root they are two *programs*, so `/api/programs` lists the other copy
        # and `_r_programs` reports a difference the reader could never see — the probe's
        # own scaffolding, read back as a finding. One program per root is the shape a
        # reader actually has.
        straight, flipped = where / "straight" / program.name, where / "flipped" / program.name
        for d in (straight, flipped):
            if d.parent.exists():
                shutil.rmtree(d.parent)
            shutil.copytree(program, d)
        # One glob, for `probe`'s reason exactly: `*.db` already matches `graph@*.db` and
        # `docs@*.db`, and reversing through all three reverses every graph back.
        for db in sorted(flipped.glob("*.db")):
            reverse_rows(db)

        graph = revisions.newest(straight, revisions.GRAPH)
        if graph is None:
            raise SystemExit(f"{program} holds no graph, so there is nothing to serve")
        from dunneflow.web.serve import _Live
        live = _Live(straight / "source.db", straight)
        live.open(graph)
        try:
            plan = choose(live)
        finally:
            live.close()

        first = ask_all(straight, plan)
        again = ask_all(straight, plan)
        flip = ask_all(flipped, plan)

        noise = _diff(first, again)
        found = {k: v for k, v in _diff(first, flip).items() if k not in noise}
        return found, noise, unasked(first)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ordering",
        description="Does anything this tool shows depend on the order its rows are in?")
    p.add_argument("program", type=Path, nargs="?", default=None,
                   help="an analysed program directory, or a maps root")
    p.add_argument("--api", action="store_true",
                   help="probe the dashboard's routes instead of the rendered map")
    p.add_argument("--survey", action="store_true",
                   help="list the statements no ORDER BY defends, and what was exempted")
    p.add_argument("--at", type=Path, default=WEB,
                   help="what --survey reads (default src/dunneflow/web)")
    p.add_argument("--show", default="", metavar="DOC",
                   help="print the actual differing lines for one document")
    p.add_argument("--lines", type=int, default=20,
                   help="how many differing lines to print with --show (default 20)")
    p.add_argument("--keep", type=Path, default=None,
                   help="keep both renders here instead of in a temporary directory")
    args = p.parse_args(argv)

    if args.survey:
        at = args.at.resolve()
        if not at.is_dir():
            print(f"!! {at} is not a directory", file=sys.stderr)
            return 1
        print(f"== {at}")
        report_survey(survey(at), at)
        # The second population, in the same breath, because they are two ways for one
        # claim to be false and a reader looking at either wants to know about the other.
        print(f"\n== `sorted()` over something with no order, under {PKG}")
        report_set_sorts(set_sorts(PKG))
        return 0

    if args.program is None:
        p.error("a program directory is needed, unless you asked for --survey")

    where = args.program.resolve()
    if not where.is_dir():
        print(f"!! {where} is not a directory", file=sys.stderr)
        return 1

    bad = 0
    for program in _programs(where):
        print(f"\n== {program.name}")
        noise: dict[str, list[str]] = {}
        if args.api:
            found, noise, vacuous = api_probe(program, keep=args.keep)
            clean = "every route answers the same thing under a full row reversal"
            if vacuous:
                bad += 1
                print("   !! asked nothing and answered `found: false`, so these were "
                      "not checked at all: " + ", ".join(vacuous))
        else:
            found = probe(program, keep=args.keep)
            clean = "every document is byte-identical under a full row reversal"

        if found:
            bad += 1
            for name, d in found.items():
                print(f"   {name:<44} {len(d):>6} differing lines")
        elif not noise:
            print(f"   {clean}")
        # Noise is printed whether or not anything was found, and never folded into the
        # findings. A route whose answer moves between two runs of the *same* copy is
        # saying something about this run and nothing about row order, and a reader who
        # cannot see which is which cannot act on either (design rule 1).
        for name, d in noise.items():
            print(f"   ~~ {name:<41} {len(d):>6} lines differ between two straight runs")
        if args.show:
            for name, d in {**found, **noise}.items():
                if name == args.show:
                    print(f"\n-- {name}")
                    for line in d[:args.lines]:
                        print(f"   {line}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
