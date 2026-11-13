"""Values the program names at module level, and the type aliases hiding among them.

`visit_Assign` caught only CLI app objects, `_class_fields` caught only class bodies,
and module level produced nothing at all -- so `JTBD_OPENERS` was declared in
`_prompts.py`, read six times, and absent from the map. 2,618 constants and 86 type
aliases on Lictores, none of them previously recorded.

Two things here can go wrong quietly, and both have tests.

**The type-alias rule is a precision rule.** `QueueState = Literal[...]` is an
enumerated vocabulary; `NOT_AN_ALIAS = SOME_DICT["key"]` is a subscript that happens to
look like one. The constructor list in `detectors/python.yaml` is the whole defence, the
same way the artefact extension list is. A bare `X = Y` is deliberately not admitted --
it cannot be told from `DEFAULT = OTHER_DEFAULT` without resolving `Y`.

**Module level means runs at import.** A constant inside a module-level `try` counts;
one inside a function does not. That is the same boundary the module scope already uses
for comments and boundaries, and getting it from position rather than from a scope stack
is what makes it unambiguous.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.extractors.python.extract import extract_file
from dunneflow.schema import Constant, DataStructure, StructureKind

PROGRAM = '''
"""A module that names values."""
from typing import Any, Callable, Final, Literal, Mapping, NewType

# The Roman records office. Plan 30-02 says this may not move.
LICTORES_DIRNAME: Final[str] = ".lictores"

JTBD_OPENERS: list[str] = ["What problem?", "For whom?"]

LIMIT = 10   # how many at once

_PRIVATE_SEED = 3

TOOL_STATUS_RAN: Final[str] = "ran"
TOOL_STATUS_FAILED: Final[str] = "tool_failed"

# -- type aliases, which are not constants ---------------------------------- #
QueueState = Literal["pending", "adjudicating", "emitted"]
AuditSink = Callable[[Mapping[str, Any]], None]
UserId = NewType("UserId", int)

# -- things that must NOT be read as type aliases --------------------------- #
NOT_AN_ALIAS = SOME_DICT["key"]
AMBIGUOUS = OtherName

__version__ = "1.0"
__all__ = ["LICTORES_DIRNAME"]

try:
    OPTIONAL_BACKEND = "neo4j"
except ImportError:
    OPTIONAL_BACKEND = "sqlite"


def routine() -> None:
    INSIDE_A_FUNCTION = 1
    return INSIDE_A_FUNCTION


class Holder:
    IN_A_CLASS_BODY = 2
'''


@pytest.fixture(scope="module")
def facts(tmp_path_factory):
    root = tmp_path_factory.mktemp("constants")
    (root / "prog.py").write_text(PROGRAM, encoding="utf-8")
    return extract_file(root / "prog.py", root)


def _by_name(facts) -> dict[str, Constant]:
    return {c.name: c for c in facts.constants}


def _aliases(facts) -> dict[str, DataStructure]:
    return {
        s.name: s for s in facts.structures if s.kind is StructureKind.TYPE_ALIAS
    }


# --------------------------------------------------------------------------- #
# What a constant is
# --------------------------------------------------------------------------- #


def test_the_constant_that_motivated_this_is_recorded(facts):
    """`JTBD_OPENERS` was declared, read six times, and invisible."""
    k = _by_name(facts)["JTBD_OPENERS"]
    assert k.value == "['What problem?', 'For whom?']"
    assert k.type == "list[str]"


def test_the_value_is_recorded_whole(facts):
    """Rule 8. A ceiling cut off at eighty characters is no longer the ceiling."""
    assert _by_name(facts)["LICTORES_DIRNAME"].value == "'.lictores'"


def test_final_is_recorded_because_it_says_do_not_rebind(facts):
    by = _by_name(facts)
    assert by["LICTORES_DIRNAME"].is_final
    assert not by["LIMIT"].is_final


def test_a_leading_comment_becomes_the_why(facts):
    why = _by_name(facts)["LICTORES_DIRNAME"].comment
    assert why is not None
    assert "Plan 30-02" in why


def test_an_inline_comment_becomes_the_why(facts):
    assert _by_name(facts)["LIMIT"].comment == "how many at once"


def test_a_leading_underscore_is_recorded_as_private(facts):
    by = _by_name(facts)
    assert by["_PRIVATE_SEED"].private
    assert not by["LIMIT"].private


# --------------------------------------------------------------------------- #
# Module level means runs at import
# --------------------------------------------------------------------------- #


def test_a_constant_in_a_module_level_try_still_runs_at_import(facts):
    assert "OPTIONAL_BACKEND" in _by_name(facts)


@pytest.mark.parametrize("name", ["INSIDE_A_FUNCTION", "IN_A_CLASS_BODY"])
def test_a_name_bound_inside_a_scope_is_not_a_module_constant(facts, name):
    """A function body does not run at import, and a class body is a structure."""
    assert name not in _by_name(facts)


@pytest.mark.parametrize("name", ["__version__", "__all__"])
def test_a_dunder_is_packaging_metadata_not_vocabulary(facts, name):
    assert name not in _by_name(facts)


def test_a_bare_annotation_binds_nothing(tmp_path):
    (tmp_path / "d.py").write_text("X: int\nY: int = 1\n", encoding="utf-8")
    names = {c.name for c in extract_file(tmp_path / "d.py", tmp_path).constants}
    assert names == {"Y"}


# --------------------------------------------------------------------------- #
# Type aliases: the precision rule
# --------------------------------------------------------------------------- #


def test_a_literal_alias_is_an_enumerated_vocabulary(facts):
    """`StructureKind.TYPE_ALIAS` existed from the start and nothing produced one."""
    alias = _aliases(facts)["QueueState"]
    assert alias.bases == ["Literal['pending', 'adjudicating', 'emitted']"]
    assert [f.name for f in alias.fields] == [
        "'pending'", "'adjudicating'", "'emitted'"
    ]


def test_a_callable_alias_records_its_target_and_has_no_members(facts):
    alias = _aliases(facts)["AuditSink"]
    assert alias.bases == ["Callable[[Mapping[str, Any]], None]"]
    assert alias.fields == []


def test_a_factory_call_declares_a_type(facts):
    assert _aliases(facts)["UserId"].bases == ["NewType('UserId', int)"]


@pytest.mark.parametrize("name", ["NOT_AN_ALIAS", "AMBIGUOUS"])
def test_what_must_not_be_read_as_a_type(facts, name):
    """Rule 1. `SOME_DICT["key"]` is a subscript; `X = Y` cannot be told from a value.

    Both are recorded as constants instead, which is true either way.
    """
    assert name not in _aliases(facts)
    assert name in _by_name(facts)


def test_an_alias_is_never_also_a_constant(facts):
    """One assignment, one fact. A name in both places would be counted twice."""
    assert not (set(_aliases(facts)) & set(_by_name(facts)))


def test_the_constructor_list_is_the_defence():
    """The rule lives in `detectors/python.yaml`, not in a branch."""
    from dunneflow.detectors import load_rules

    rules = load_rules("python")
    assert rules.is_type_expression("Literal")
    assert rules.is_type_expression("typing.Literal")
    assert not rules.is_type_expression("SOME_DICT")
    assert rules.is_alias_factory("NewType")
    assert not rules.is_alias_factory("compute")


# --------------------------------------------------------------------------- #
# The mirror, which is why this exists
# --------------------------------------------------------------------------- #


def test_a_constant_makes_a_documented_word_named(tmp_path):
    """The blind spot this closed: a term reached only Spoken, on a comment."""
    from dunneflow.docstore import DocStore
    from dunneflow.resolve.mirror import measure
    from dunneflow.store import Store
    from dunneflow.walk import analyze_docs_tree, analyze_tree

    root: Path = tmp_path / "prog"
    root.mkdir()
    (root / "p.py").write_text(
        'JTBD_OPENERS: list[str] = ["a"]\nSOLUS = 1\n', encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "glossary.md").write_text(
        "# Glossary\n\n- **JTBD_OPENERS** — the opening questions.\n"
        "- **solus** — alone, and used nowhere.\n",
        encoding="utf-8",
    )
    store = Store(tmp_path / "graph.db")
    analyze_tree(root, store)
    doc_store = DocStore(tmp_path / "docs.db")
    analyze_docs_tree(docs, doc_store, jobs=1)
    doc_store.mark_duplicates()

    bands = {t.term: t.band for t in measure(store, doc_store).terms}
    assert bands["JTBD_OPENERS"] == "NAMED"
    assert bands["solus"] == "NAMED"    # `SOLUS` names it, case-insensitively
    store.close()
    doc_store.close()


def test_a_word_run_matches_a_compound_but_a_substring_does_not():
    """`TOOL_STATUS_RAN` carries `tool status`; `aggregate` does not carry `gate`.

    Measured before it was added: on Lictores this moves exactly one term into a
    stronger band on its own, and every term it moves was verified against source.
    """
    from dunneflow.resolve.mirror import name_keys

    assert "toolstatus" in name_keys("TOOL_STATUS_RAN")
    assert "tool" in name_keys("TOOL_STATUS_RAN")
    assert name_keys("aggregate") == {"aggregate"}
    assert "gate" not in name_keys("aggregate")


# `test_surfaces_are_pluralised_as_english` was here, over `mirror.plural`. Both are gone:
# `plural`'s only caller was `surface_summary`, which nothing ever called, and keeping a
# function alive in `src/` so a test can assert on it makes the test the reason the code
# exists. `mirror.py` carries the two exceptions -- "classes", "ways in" -- in a comment
# where the pair stood, so whoever counts a surface in prose next does not rediscover them
# from "23 classs" on a screen.
