"""The naming lanes across a mixed corpus — `PLAN-v2.md`'s open question 6, answered.

A convention about **spelling** is a convention of one language. Mined across a Python and
a TypeScript corpus at once it is neither, and the number it produces is the most damaging
kind: large, plausible, and made of two answers that disagree.

Measured on DunneFlow's own tree, 107 Python files and 11 TypeScript, before any of this:

    [D] 1,014/1,114  Routines are named in snake_case.  (100 exceptions)

All 100 are TypeScript names spelled the way TypeScript spells names. Split, the same facts
are `982 of 998` and `116 of 116` — two conventions, both true, neither visible before.

Three properties are guarded here, and the third is the one that nearly went missing.

**A one-language map is untouched.** It has no language axis to state, so its report reads
exactly as it did — which is also what keeps every recorded Mensores figure reproducible.

**The split is per language and the languages are read off the map**, never guessed. That
is the distinction from `conformance.py`'s refusal of a path-shaped scope: nothing supplies
which *paths* a rule governs, and the map does supply which languages it holds.

**No row may be lost in the split.** Found the hard way: DunneFlow declares `dunneflow` in
`pyproject.toml`, which no reader claims and which therefore has no row in `files`. Scoped
by its own file that command belongs to no language and simply vanished — 15 commands where
the map holds 16, a denominator quietly shedding a row while every number on screen still
looked right (rule 32).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.docstore import DocStore
from dunneflow.resolve.conformance import CHECKED, check_stated
from dunneflow.resolve.naming import (
    POPULATIONS,
    measure,
    mine_case_conventions,
)
from dunneflow.store import Store
from dunneflow.walk import analyze_docs_tree, analyze_tree

LANG = "typescript"
PLUGIN = ingest.PLUGINS.get(LANG)

# Two reasons to skip and they are different facts, exactly as `test_typescript.py` has it:
# no plugin is a build assembled without its readers, no `node` is this machine's state.
pytestmark = [
    pytest.mark.skipif(PLUGIN is None, reason="this build ships no TypeScript reader"),
    pytest.mark.skipif(shutil.which("node") is None,
                       reason="node is not on this machine, and the reader is a node program"),
]

# Python that keeps Python's convention, comfortably past `MIN_POPULATION`.
PY_MODULE = '"""A module of well-named routines."""\n\n' + "\n\n".join(
    f"def load_{n}(a_value: int) -> int:\n    return a_value + {i}"
    for i, n in enumerate(
        ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota"]))

# TypeScript that keeps TypeScript's, including the one-token names that are the whole
# reason this could not be measured before (rule 100).
TS_MODULE = "\n\n".join(
    f"export function load{n}(someValue: number): number {{ return someValue + {i}; }}"
    for i, n in enumerate(
        ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta"])
) + "\n\nexport function main(): number { return 0; }\n"


def _mixed(root: Path) -> Store:
    """One tree, two languages, each spelling its own names its own way."""
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "load_things.py").write_text(PY_MODULE, encoding="utf-8")
    (src / "loaders.ts").write_text(TS_MODULE, encoding="utf-8")
    store = Store(root / "graph.db")
    analyze_tree(root, store)
    return store


def _python_only(root: Path) -> Store:
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "load_things.py").write_text(PY_MODULE, encoding="utf-8")
    store = Store(root / "graph.db")
    analyze_tree(root, store)
    return store


def _conventions(store: Store, kind: str, population_word: str) -> list:
    return [c for c in measure(store).conventions
            if c.kind == kind and population_word in c.population]


# -- the split itself --------------------------------------------------------- #


def test_a_mixed_map_states_one_spelling_convention_per_language(tmp_path: Path) -> None:
    """Two conventions where there was one rating, and both of them true."""
    store = _mixed(tmp_path)
    try:
        routines = _conventions(store, "CASE", "routines")
        by_lang = {c.lang: c for c in routines}
        assert set(by_lang) == {"python", "typescript"}, (
            f"expected a convention per language, got {[c.population for c in routines]}"
        )
        assert by_lang["python"].holds == by_lang["python"].total
        assert by_lang["typescript"].holds == by_lang["typescript"].total
        assert "snake_case" in by_lang["python"].claim
        assert "camelCase" in by_lang["typescript"].claim, (
            "the one-token names must count with their own population's majority, or "
            "TypeScript reports 72% and falls under the threshold as a false gap"
        )
        # The language is a *field*, not a word to be parsed back out of a sentence
        # (rule 30) -- and the sentence names it too, because a reader reads the sentence.
        assert by_lang["typescript"].population.startswith("TypeScript ")
    finally:
        store.close()


def test_a_one_language_map_states_no_language_at_all(tmp_path: Path) -> None:
    """Nothing to split on, so nothing is said — and every older figure still reproduces.

    This is not tidiness. A map holding one language has no language axis, and labelling
    its conventions *"Python routines"* would be asserting a distinction the map cannot
    draw — as well as moving every number recorded against every single-language corpus.
    """
    store = _python_only(tmp_path)
    try:
        m = measure(store)
        assert m.conventions, "nothing was measured; this test is blind"
        assert all(c.lang == "" for c in m.conventions), (
            f"a single-language map named a language: "
            f"{[c.population for c in m.conventions if c.lang]}"
        )
        assert all(g.lang == "" for g in m.gaps)
        assert any(c.claim.startswith("Routines are named") for c in m.conventions), (
            "the claim must read exactly as it did before any of this existed"
        )
    finally:
        store.close()


def test_the_split_loses_no_row_from_any_population(tmp_path: Path) -> None:
    """Every name counted once, under exactly one language.

    The guard for the defect that a split introduces and nothing else can see: a member
    whose language cannot be established drops out of every group and out of the totals
    with it. DunneFlow's own `dunneflow` command is declared in `pyproject.toml`, which is
    not source and has no row in `files`; scoped by its own file it belonged to no language
    and the report read *15 commands* over a map holding 16 (rule 32).
    """
    store = _mixed(tmp_path)
    try:
        whole, whole_gaps = mine_case_conventions(store, ())
        split, split_gaps = mine_case_conventions(store, ["python", "typescript"])

        def counted(conventions: list, gaps: list) -> dict[str, int]:
            """Every population's total, whichever side of the threshold it fell.

            Gaps as well as conventions, because splitting can move a population across
            `MIN_PREVALENCE` in either direction and a row that changed lanes has not gone
            anywhere. `population` carries the language's *display* name in front, so the
            key is what is left after it.
            """
            out: dict[str, int] = {}
            for item in [*conventions, *gaps]:
                key = item.population.split(" ", 1)[1] if item.lang else item.population
                out[key] = out.get(key, 0) + item.total
            return out

        unsplit = counted(whole, whole_gaps)
        pieces = counted(split, split_gaps)
        assert unsplit, "nothing was measured; this test is blind"
        for population, total in unsplit.items():
            assert pieces.get(population) == total, (
                f"{population}: {total} counted whole, {pieces.get(population)} counted "
                f"across the languages — the split lost or double-counted a row"
            )
    finally:
        store.close()


def test_every_split_claim_reproduces_its_own_exceptions(tmp_path: Path) -> None:
    """Rule 13, at the one place the language clause could break it.

    Each claim's query now carries a language predicate as well as a style one, and the
    two are assembled separately. A predicate that narrowed differently from the count
    would print a number over a query returning something else.
    """
    store = _mixed(tmp_path)
    try:
        for c in measure(store).conventions:
            rows = {str(r[0]) for r in store.query(c.sql)}
            assert rows == {e.name for e in c.exceptions}, (
                f"the query for {c.claim!r} returns {sorted(rows)} where the claim lists "
                f"{sorted(e.name for e in c.exceptions)}"
            )
    finally:
        store.close()


def test_only_the_spelling_lanes_carry_a_language(tmp_path: Path) -> None:
    """The decision, asserted so it cannot drift into place unnoticed.

    An affix is a *word a team chose* rather than a way of spelling one, and the privacy
    lane's population is `visibility = 'private'` — a Python spelling that no other reader
    here records at all (0 of DunneFlow's 122 TypeScript routines). Splitting either would
    assert an axis nothing has shown to matter, which is the thing this whole chunk is
    about not doing.
    """
    store = _mixed(tmp_path)
    try:
        for c in measure(store).conventions:
            if c.kind in ("AFFIX", "LEAKAGE"):
                assert c.lang == "", (
                    f"{c.kind} was split by language, which was decided against: {c.claim!r}"
                )
    finally:
        store.close()


def test_every_population_can_be_narrowed_to_a_language(tmp_path: Path) -> None:
    """Each language clause is SQL, and SQL that is never run is SQL that is wrong.

    Two of these queries had no `WHERE` at all, so appending `AND …` to them produced a
    syntax error rather than a narrower answer — and the whole suite passed, because no
    fixture had ever held two languages.
    """
    store = _mixed(tmp_path)
    try:
        for _label, (_table, list_sql, from_clause, lang_clause) in POPULATIONS.items():
            clause = lang_clause.format(lang="python")
            store.query(f"{list_sql} AND {clause}")
            store.query(f"SELECT 1 {from_clause} AND {clause}")
    finally:
        store.close()


# -- conformance -------------------------------------------------------------- #

UNSCOPED_RULES = """# House style

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Functions | snake_case | `load_thing` |
| Parameters | snake_case | `a_value` |
"""

PY_SCOPED_RULES = """---
paths: ['**/*.py']
---

# House style

## Naming Conventions

| Type | Convention | Example |
|---|---|---|
| Functions | snake_case | `load_thing` |
| Parameters | snake_case | `a_value` |
"""


def _docs(root: Path, text: str) -> DocStore:
    root.mkdir(parents=True, exist_ok=True)
    (root / "style.md").write_text(text, encoding="utf-8")
    store = DocStore(root / "docs.db")
    analyze_docs_tree(root, store, jobs=1)
    return store


def test_an_unscoped_rule_is_measured_once_per_language(tmp_path: Path) -> None:
    """The failure this module exists to prevent, arriving one door along.

    *"Functions: snake_case"* over a mixed map scores 91% on DunneFlow's own tree, and the
    100 names it condemns are TypeScript names obeying TypeScript. One number made of two
    answers is precisely the plausible population rule 49 is about — and the remedy is not
    a refusal, because the map *does* supply which languages it holds. Splitting reads a
    fact; widening guessed one.
    """
    store = _mixed(tmp_path / "p")
    docs = _docs(tmp_path / "p" / "d", UNSCOPED_RULES)
    try:
        checks = [c for c in check_stated(store, docs, None)
                  if c.rule.scope == "functions"]
        assert checks, "the table states a rule about functions, or this test is blind"
        assert {c.lang for c in checks} == {"python", "typescript"}, (
            f"expected one result per language, got {[(c.lang, c.population) for c in checks]}"
        )
        assert all(c.verdict == CHECKED for c in checks)
        assert all(c.blind_spot for c in checks), (
            "a rule measured against a language its document never names is a true count "
            "of a question nobody may have asked, and it has to say so"
        )
        python = next(c for c in checks if c.lang == "python")
        typescript = next(c for c in checks if c.lang == "typescript")
        assert python.holds == python.total, "the rule holds where it was plainly meant"
        assert typescript.holds < typescript.total, (
            "and fails where it was not — which is the fact that was hidden inside a 91%"
        )
    finally:
        docs.close()
        store.close()


def test_a_rule_its_document_scopes_to_one_language_is_not_split(tmp_path: Path) -> None:
    """The reader's own standard already closed the axis, so nothing announces one.

    `paths: ['**/*.py']` narrows the population to Python before any of this is asked.
    Pairing that answer with an empty TypeScript one — or labelling it at all — would be
    telling a reader about a distinction their standard had already made.
    """
    store = _mixed(tmp_path / "p")
    docs = _docs(tmp_path / "p" / "d", PY_SCOPED_RULES)
    try:
        checks = [c for c in check_stated(store, docs, None)
                  if c.rule.scope == "functions"]
        assert len(checks) == 1, (
            f"a scoped rule must stay one answer, got {[c.population for c in checks]}"
        )
        assert checks[0].lang == "" and not checks[0].blind_spot
        assert checks[0].verdict == CHECKED
        assert checks[0].holds == checks[0].total, (
            "scoped to Python, the rule holds — and the TypeScript names are out of it"
        )
    finally:
        docs.close()
        store.close()
