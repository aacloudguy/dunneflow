"""Whose builtin names are struck out of the landing evidence, and on what authority.

`_builtins()` was `load_rules("python").builtins` and was asked of every corpus. That is a
true statement about Python put to a map with no Python in it: on DunneNote — 442 TypeScript
files, no Python, 391 graded ids — it struck `hex`, `round` and `set` out of the evidence
for being words in a language nobody had read. Open question 6's shape one module over, and
the same remedy: the map supplies which languages it holds, so the question is scoped by
them rather than the answer widened.

**Measured before it was changed, and the headline is that it moved nothing.** Removing the
exclusion outright changes no verdict on any of the four corpora — Lictores 1,463 ids,
DunneNote 391, DunneFlow 28, DunneCorp 0. A name must be unique in the program *and* collide
with a builtin *and* be the symbol tipping an id past `STRONG_LANDED_SYMBOLS` before anybody
sees it. So this is a correctness fix with a measured effect of nil today, and the reason to
make it is rule 98: the words it struck — `id`, `set`, `type`, `next`, `open`, `filter` —
are ordinary TypeScript names that happen to be Python's, and what is nil on these corpora
is not nil on the next one.

**A language that declares no builtins contributes no exclusions**, and that is the residue
rather than a gap to fill by guessing. Writing a TypeScript list into `detectors/` would be
this tool asserting a fact about a language it reads rather than one it was told.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.detectors import load_rules
from dunneflow.docstore import DocStore
from dunneflow.render.page import Stamp
from dunneflow.render.traceability import _builtin_sentence, render_traceability
from dunneflow.resolve.traceability import _builtins, measure
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree, analyze_tree

LANG = "typescript"
PLUGIN = ingest.PLUGINS.get(LANG)

# Two reasons to skip and they are different facts: no plugin is a build assembled without
# its readers, no `node` is this machine's state.
pytestmark = [
    pytest.mark.skipif(PLUGIN is None, reason="this build ships no TypeScript reader"),
    pytest.mark.skipif(shutil.which("node") is None,
                       reason="node is not on this machine, and the reader is a node program"),
]

STAMP = Stamp(generated="2026-01-01 00:00 UTC", revision="", analysed="")

# **Every one of these names is a Python builtin**, and every one is an ordinary thing to
# call a TypeScript function. That is the whole case: `hex`, `round` and `set` are what the
# unscoped exclusion actually struck out of DunneNote.
TS_MODULE = """\
export function hex(n: number): string { return n.toString(16); }

export function round(n: number): number { return Math.trunc(n + 0.5); }

export function id(thing: string): string { return thing; }

export function formatLedgerWitness(rows: string[]): string { return rows.join(","); }
"""

PY_MODULE = '''\
"""A module that names one thing after a builtin, as Python programs do."""


def hex_of(value: int) -> str:
    return format(value, "x")


def reconcile_witness_ledger(rows: list) -> int:
    return len(rows)
'''

DOC = """# Plan 31-01 — the hex encoder

Implements `hex`, `round` and `id`, plus `formatLedgerWitness`.
"""


def _store(root: Path, *, python: bool, typescript: bool) -> Store:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    if python:
        (src / "things.py").write_text(PY_MODULE, encoding="utf-8")
    if typescript:
        (src / "things.ts").write_text(TS_MODULE, encoding="utf-8")
    store = Store(root / "graph.db")
    analyze_tree(root, store)
    return store


# -- which list is applied ----------------------------------------------------- #


def test_a_map_with_no_python_excludes_no_python_builtin(tmp_path):
    """The defect, stated as the thing it got wrong.

    `hex`, `round` and `id` are declared here in TypeScript and nowhere else. Asked of this
    map, Python's builtin list has no standing at all — there is no Python in it.
    """
    store = _store(tmp_path, python=False, typescript=True)
    try:
        assert _builtins(store) == frozenset(), (
            "a TypeScript-only map borrowed another language's builtins")
    finally:
        store.close()


def test_a_python_map_still_excludes_pythons(tmp_path):
    """The behaviour that must not change, because rule 3 is why any of this exists.

    Asserted against `detectors/python.yaml` rather than a literal list, so the claim and
    the declaration cannot drift (rule 51).
    """
    store = _store(tmp_path, python=True, typescript=False)
    try:
        assert _builtins(store) == frozenset(load_rules("python").builtins)
    finally:
        store.close()


def test_a_mixed_map_applies_every_language_it_holds(tmp_path):
    """A union, and deliberately not a per-symbol test.

    The exclusion does not ask *is this symbol a builtin* — a program may perfectly well
    define its own `hex`. It asks *would a document naming this word be naming your symbol
    or using the word*, and that is a question about the language the prose is written
    **about**. Somebody describing a Python-and-TypeScript program writes `list`
    generically whichever half they mean.
    """
    store = _store(tmp_path, python=True, typescript=True)
    try:
        got = _builtins(store)
        assert got >= frozenset(load_rules("python").builtins), (
            "a map that holds Python stopped excluding Python's builtins")
        assert "hex" in got, "the Python half's list stopped reaching the map"
    finally:
        store.close()


def test_the_languages_a_map_holds_decide_and_nothing_else(tmp_path):
    """Rule 32: the population supplies the axis.

    Pinned as a *difference* between two maps of the same shape, because an assertion
    about one of them would pass just as well if the answer were hardcoded.
    """
    ts = _store(tmp_path / "ts", python=False, typescript=True)
    py = _store(tmp_path / "py", python=True, typescript=False)
    try:
        assert _builtins(ts) != _builtins(py), (
            "two maps of different languages were given one answer")
    finally:
        ts.close()
        py.close()


# -- what the page says about it ----------------------------------------------- #


def _measured(root: Path, *, python: bool, typescript: bool):
    store = _store(root, python=python, typescript=typescript)
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "plan-31-01.md").write_text(DOC, encoding="utf-8")
    doc_store = DocStore(root / "docs.db")
    analyze_docs_tree(docs_dir, doc_store, jobs=1)
    doc_store.mark_duplicates()
    return store, doc_store, measure(store, doc_store)


def test_the_report_names_the_languages_whose_builtins_were_used(tmp_path):
    """Rule 13: the sentence comes off the field the exclusion was built from.

    It read "**Python's** builtin names are excluded" as a constant, which described the
    code and not the map — and on a TypeScript corpus it named a language that corpus has
    no file of, to explain striking out three of its names.
    """
    store, docs, result = _measured(tmp_path, python=True, typescript=False)
    try:
        assert result.builtin_languages == ["python"]
        assert "Python's" in _builtin_sentence(result)
    finally:
        store.close()
        docs.close()


def test_a_map_that_excluded_nothing_says_so_rather_than_saying_nothing(tmp_path):
    """Design rule 21: the empty case is an answer, not a missing clause.

    *No builtins were excluded* is a thing a reader weighing this evidence needs told —
    and it needs its reason, or it reads as an omission rather than as the true state.
    """
    store, docs, result = _measured(tmp_path, python=False, typescript=True)
    try:
        assert result.builtin_languages == []
        assert result.languages == ["typescript"]
        said = _builtin_sentence(result)
        assert "No builtin names were excluded" in said, said
        assert "TypeScript" in said, "the sentence does not say which language it holds"
        assert "Python" not in said, (
            "a TypeScript-only map still names Python in its own method section")
    finally:
        store.close()
        docs.close()


def test_the_sentence_reaches_the_written_report(tmp_path):
    """Rule 44's shape from the other end: a field nothing renders says nothing."""
    store, docs, _ = _measured(tmp_path, python=False, typescript=True)
    try:
        out = tmp_path / "map"
        out.mkdir()
        written = render_traceability(store, docs, out, "demo", STAMP)
        text = Path(written).read_text(encoding="utf-8")
        assert "No builtin names were excluded" in text
    finally:
        store.close()
        docs.close()


def test_a_typescript_name_that_is_a_python_builtin_can_be_evidence(tmp_path):
    """The whole point, measured on the thing the reader actually reads.

    `hex`, `round` and `id` are unique in this program and declared in TypeScript. Struck
    out, `PLAN-31-1` had one distinctive symbol to its name; kept, it has four.
    """
    store, docs, result = _measured(tmp_path, python=False, typescript=True)
    try:
        plan = next((t for t in result.ids if t.id == "PLAN-31-1"), None)
        assert plan is not None, [t.id for t in result.ids]
        assert "hex" in plan.landed, plan.landed
        assert "round" in plan.landed, plan.landed
    finally:
        store.close()
        docs.close()
