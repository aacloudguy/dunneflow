"""The resolver seam: who is asked, what they are never asked, and who writes.

`tests/test_resolve.py` holds the Python answers — that `self.thing()` reaches a base
class, that a builtin never resolves inward, that ambiguity is recorded rather than
guessed. Those are unchanged and stay there. What is here is the part that could not be
pressed while there was one resolver: dispatch, the two hoists, and the honest answer for
a language this build cannot resolve.

The second language is a **fake registered into `RESOLVERS`**, for `test_ingest.py`'s
reason: the multi-language behaviour has to be provable before a multi-language build
exists, or it is written on the strength of reading it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from dunneflow.detectors import load_rules
from dunneflow.resolve import calls as driver
from dunneflow.resolve.contract import CallRow, Edge, NoEdge
from dunneflow.schema import Confidence
from dunneflow.store import Store

SRC = Path(__file__).resolve().parents[1] / "src" / "dunneflow"


# ------------------------------------------------------------------ a map ------ #

def _map(tmp_path: Path, rows: list[tuple[str, str, str, str, int]]) -> Store:
    """A graph with just enough in it to resolve: files, one routine each, and calls.

    `rows` is `(lang, file, caller_id, callee_expr, at_boundary)`. Written straight into
    the store rather than extracted, because what is under test is the driver and a
    TypeScript file cannot be extracted by this build at all.
    """
    store = Store(tmp_path / "graph.db")
    seen: set[str] = set()
    for lang, file, caller, expr, boundary in rows:
        if file not in seen:
            seen.add(file)
            store.conn.execute(
                "INSERT INTO files(path, lang, module, content_hash) VALUES (?,?,?,?)",
                (file, lang, file.rsplit(".", 1)[0], "h"),
            )
            store.conn.execute(
                "INSERT INTO routines(id, name, qualname, module, file, line_start,"
                " line_end, lang) VALUES (?,?,?,?,?,1,9,?)",
                (caller, caller, caller, file.rsplit(".", 1)[0], file, lang),
            )
        store.conn.execute(
            "INSERT INTO calls(file, caller_id, callee_expr, line, confidence,"
            " at_boundary, site_id) VALUES (?,?,?,1,?,?,?)",
            (file, caller, expr, Confidence.INFERRED.value, boundary,
             f"{caller}:{expr}:{boundary}"),
        )
    store.conn.commit()
    return store


@pytest.fixture
def two_languages(tmp_path: Path):
    store = _map(tmp_path, [
        ("python", "a.py", "a:f", "helper", 0),
        ("python", "a.py", "a:f", "conn.execute", 1),
        ("typescript", "b.ts", "b:g", "load", 0),
        ("typescript", "b.ts", "b:g", "fetch", 1),
    ])
    yield store
    store.close()


# ------------------------------------------------------------------ dispatch --- #

def test_a_resolver_is_asked_only_about_its_own_language(two_languages, monkeypatch):
    """The whole point of the chunk: Python's name rules never see a TypeScript call."""
    handed: dict[str, list[str]] = {}

    def fake(store, lang, rows):
        handed[lang] = [r.callee_expr for r in rows]
        return [NoEdge() for _ in rows]

    def fake_py(store, lang, rows):
        handed[lang] = [r.callee_expr for r in rows]
        return [Edge("a:f", Confidence.CERTAIN) for _ in rows]

    monkeypatch.setitem(driver.RESOLVERS, "typescript", fake)
    monkeypatch.setitem(driver.RESOLVERS, "python", fake_py)
    driver.resolve_calls(two_languages)

    assert handed == {"python": ["helper"], "typescript": ["load"]}


def test_a_boundary_call_never_reaches_a_resolver(two_languages, monkeypatch):
    """Rule 2, hoisted. `conn.execute(...)` is sqlite3, and no resolver gets a vote.

    It was decided inside Python's resolver, which was the whole truth with one resolver
    and is a rule every new one would have had to remember — and forgetting it is 919
    invented edges, not a smaller map.
    """
    seen: list[str] = []

    def fake(store, lang, rows):
        seen.extend(r.callee_expr for r in rows)
        return [NoEdge() for _ in rows]

    monkeypatch.setitem(driver.RESOLVERS, "typescript", fake)
    monkeypatch.setitem(driver.RESOLVERS, "python", fake)
    driver.resolve_calls(two_languages)

    assert "conn.execute" not in seen
    assert "fetch" not in seen
    assert sorted(seen) == ["helper", "load"]

    # And what the map now says about them: external, suppressed, no candidates.
    rows = two_languages.query(
        "SELECT callee_expr, callee_id, external, ambiguous FROM calls"
        " WHERE at_boundary = 1"
    )
    assert len(rows) == 2
    for r in rows:
        assert r["callee_id"] is None
        assert r["external"] == 1
        assert r["ambiguous"] == 0


def test_a_language_with_no_resolver_is_external_and_named(two_languages, monkeypatch):
    """Three answers, never two. TypeScript extraction lands a chunk before its edges do.

    A map with routines, boundaries and no internal TypeScript edges is honest and
    shippable — as long as it says so. Silence reads exactly like a program that calls
    nothing.
    """
    monkeypatch.delitem(driver.RESOLVERS, "typescript", raising=False)
    stats = driver.resolve_calls(two_languages)

    assert stats.unresolved_langs == {"typescript": 1}
    assert stats.langs["typescript"].certain == 0
    assert stats.langs["typescript"].inferred == 0
    # Both TypeScript calls external: the boundary one by rule 2, the other for want of
    # anything that can see the far end (rule 26).
    assert stats.langs["typescript"].external == 2
    assert two_languages.query(
        "SELECT COUNT(*) n FROM calls c JOIN files f ON f.path = c.file"
        " WHERE f.lang = 'typescript' AND c.callee_id IS NOT NULL"
    )[0]["n"] == 0


def test_the_per_language_figures_add_up_to_the_published_one(two_languages, monkeypatch):
    """Rule 13: the number printed and the numbers behind it cannot disagree."""
    monkeypatch.setitem(
        driver.RESOLVERS, "typescript",
        lambda store, lang, rows: [Edge("b:g", Confidence.INFERRED) for _ in rows],
    )
    stats = driver.resolve_calls(two_languages)

    assert stats.total == 4
    assert sum(p.total for p in stats.langs.values()) == stats.total
    for field in ("certain", "inferred", "external", "suppressed", "ambiguous",
                  "inherited"):
        assert getattr(stats, field) == sum(
            getattr(p, field) for p in stats.langs.values()
        ), field


def test_a_resolver_answering_the_wrong_number_of_rows_is_refused(two_languages,
                                                                 monkeypatch):
    """Decisions pair with rows by position, so a short answer misplaces them all."""
    monkeypatch.setitem(driver.RESOLVERS, "typescript",
                        lambda store, lang, rows: [])
    with pytest.raises(ValueError, match="answered 0"):
        driver.resolve_calls(two_languages)


# ------------------------------------------------------------------ one writer - #

def test_only_the_driver_writes_a_callee_id():
    """One place spells `UPDATE calls SET callee_id`, asserted over the source.

    `test_source.py:171` sets the precedent: a rule about where an act may happen is kept
    by reading the code, because a second site is written by somebody who never read this
    file. v1 had three, each getting `external`, `suppressed` and `ambiguous` right on its
    own.
    """
    writers = [
        p for p in (SRC / "resolve").rglob("*.py")
        if re.search(r"UPDATE\s+calls\s+SET\s+callee_id", p.read_text(encoding="utf-8"))
    ]
    assert [p.name for p in writers] == ["calls.py"]
    assert writers[0].parent.name == "resolve"


def test_no_resolver_reads_this_interpreters_builtins():
    """The builtin set is a fact about the analysing machine, and it decided edges.

    **Read as syntax and not as text** — rule 34, and it was paid for here: the two
    modules that stopped doing this each explain *why* in a comment, and every comment
    contains every word a scan would look for. So the question asked is whether anything
    under `resolve/` still **imports** the module, which no amount of prose can answer
    wrongly.
    """
    offenders = []
    for path in (SRC / "resolve").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {node.module or ""}
            else:
                continue
            if "builtins" in names:
                offenders.append(path.name)
    assert offenders == []


# ------------------------------------------------------------------ declared --- #

def test_the_builtins_are_declared_and_hold_the_version_delta():
    """Measured across CPython 3.9–3.13, so the answer stops varying by machine.

    The seven names are the ones that actually differ over that range — which is to say
    exactly what the analysing machine used to decide. `True` and `False` are in the list
    because they are quoted in the YAML: unquoted they are booleans, and a set that looks
    right silently stops suppressing two of the commonest words in the language.
    """
    declared = load_rules("python").builtins
    assert len(declared) == 159
    assert all(isinstance(x, str) for x in declared)
    assert {"aiter", "anext", "EncodingWarning", "ExceptionGroup", "BaseExceptionGroup",
            "PythonFinalizationError", "_IncompleteInputError"} <= declared
    assert {"True", "False", "None"} <= declared


def test_the_receiver_words_come_from_the_manifest():
    """`self` and `cls` were declared in `plugin.json` and read by nothing (rule 35)."""
    from dunneflow.ingest import PLUGINS
    from dunneflow.resolve.python.calls import _receiver_words

    assert _receiver_words() == frozenset({"self", "cls"})
    assert _receiver_words() == frozenset(PLUGINS["python"].manifest.receiver_words)
    text = (SRC / "resolve" / "python" / "calls.py").read_text(encoding="utf-8")
    assert '{"self", "cls"}' not in text


def test_sql_is_in_the_core_key():
    """Rule 95. `sql.py` shapes every `sql_ops` row and was in no cache key at all.

    Core rather than Python's, because judging a string literal is the **host's** job by
    design: a plugin reimplementing `looks_like_sql` means the same string in a `.py` and
    a `.ts` file can be read two different ways.
    """
    from dunneflow.detectors import core_extraction_inputs, lang_extraction_inputs

    assert "sql.py" in {p.name for p in core_extraction_inputs()}
    assert "sql.py" not in {p.name for p in lang_extraction_inputs("python")}


# ------------------------------------------------------------------ the index -- #

def test_a_bare_name_never_resolves_across_a_language(tmp_path):
    """The file-set filter, and the reason it is not housekeeping.

    A TypeScript routine called `render` competing for a Python bare `render()` is rule 5's
    defect with a language boundary added to it — and on a single-language map the filter
    changes nothing, which is why the golden cannot move.
    """
    store = _map(tmp_path, [
        ("python", "a.py", "a:caller", "render", 0),
        ("typescript", "b.ts", "b:render", "noop", 0),
    ])
    # Give the TypeScript side a routine that would win the name outright.
    store.conn.execute(
        "UPDATE routines SET name = 'render' WHERE id = 'b:render'")
    store.conn.commit()
    try:
        driver.resolve_calls(store)
        row = store.query(
            "SELECT callee_id, external FROM calls WHERE callee_expr = 'render'")[0]
        assert row["callee_id"] is None
        assert row["external"] == 1
    finally:
        store.close()


def test_a_call_whose_file_is_not_in_the_map_is_refused(tmp_path):
    """Skipping it would leave a call resolved by nobody, with no symptom anywhere."""
    store = _map(tmp_path, [("python", "a.py", "a:f", "helper", 0)])
    store.conn.execute("DELETE FROM files WHERE path = 'a.py'")
    store.conn.commit()
    try:
        with pytest.raises(ValueError, match="belongs to no file"):
            driver.resolve_calls(store)
    finally:
        store.close()


def test_a_call_row_carries_no_rowid(tmp_path):
    """A resolver has no use for one that is not a second way to write (rule 20).

    `site_id` joined it for chunk 10 and is the opposite case, which is why the set is
    spelled out rather than loosened: a rowid is a **position in one database** and a
    `site_id` is this call's **identity**, minted from the caller, the expression and an
    ordinal. A supplied edge names a call site by that identity, so a resolver without it
    would have to match on file and line — a second identity function for call sites, in
    the one place the two could disagree unnoticed (rule 30).
    """
    assert not hasattr(CallRow("a.py", "a:f", "x"), "rowid")
    assert set(CallRow.__slots__) == {"file", "caller_id", "callee_expr", "site_id"}
