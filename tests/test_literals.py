"""The string-literal split: the reader finds them, the host says what they mean.

Every claim here was true of v1 by accident, in the way `test_languages.py`'s were: one
language, so one scanner could not disagree with a second one, and `_owner()`'s laziness
could not be disturbed by a question nobody was asking. Each test below is the point where
the accident stops being one — and the sharpest of them, `the module scope is claimed only
by a string that turned out to be a fact`, pins a defect this split created and measured:
**65 of Society's 628 files** gained a `<module>` routine owning nothing at all.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from dunneflow import walk
from dunneflow.extractors.python import extract as pyextract
from dunneflow.extractors.python.extract import extract_file
from dunneflow.ingest import literals
from dunneflow.ingest.contract import PluginRefused, stamp_lang
from dunneflow.ingest.literals import judge
from dunneflow.schema import Artefact, FileFacts, LiteralKind, SqlStatement, StringLiteral


def _read(tmp_path: Path, source: str) -> FileFacts:
    (tmp_path / "m.py").write_text(source, encoding="utf-8")
    return stamp_lang(extract_file(tmp_path / "m.py", tmp_path))


def _judged(tmp_path: Path, source: str) -> FileFacts:
    return judge(_read(tmp_path, source))


def _facts(**kw: object) -> FileFacts:
    return FileFacts(path="m.py", lang="python", module="m", content_hash="h", **kw)  # type: ignore[arg-type]


# ---------------------------------------------------------------- the split --- #

def test_the_reader_reports_strings_and_judges_none_of_them(tmp_path):
    """The whole of the split, in the one assertion that says it happened."""
    facts = _read(tmp_path, 'DDL = "CREATE TABLE widgets (id TEXT)"\n'
                            'DB = "tabularium.db"\n')
    assert [lit.text for lit in facts.literals] == [
        "CREATE TABLE widgets (id TEXT)", "tabularium.db",
    ]
    assert facts.sql == [] and facts.artefacts == []
    assert facts.tables == [] and facts.indexes == []


def test_the_host_judges_what_the_reader_reported(tmp_path):
    facts = _judged(tmp_path, 'DDL = "CREATE TABLE widgets (id TEXT)"\n'
                              'DB = "tabularium.db"\n')
    assert [op.operation for op in facts.sql] == ["CREATE TABLE"]
    assert [t.name for t in facts.tables] == ["widgets"]
    assert [a.name for a in facts.artefacts] == ["tabularium.db"]


def test_nothing_under_extractors_decides_what_a_string_means():
    """The guard that keeps the split a split rather than a move (rule 51).

    Read off the source text because the thing being refused is a *second* scanner, and a
    second scanner is exactly what no test of behaviour can see: it would agree with this
    one until the day the two drifted.
    """
    source = inspect.getsource(pyextract)
    for word in ("looks_like_sql", "parse_table_def", "parse_index_defs", "artefact_kind"):
        assert word not in source, (
            f"{word} is back in the Python reader; what a string means is "
            f"`ingest/literals.py`'s answer for every language at once"
        )


def test_a_reader_that_judged_its_own_strings_is_refused():
    """Two answers to one question, and only ever noticed when they differ (rule 30)."""
    with pytest.raises(PluginRefused) as exc:
        judge(_facts(artefacts=[Artefact(name="a.db", stem="a", ext="db", kind="DATABASE",
                                         routine_id="r", line=1, literal="a.db")]))
    assert "artefacts" in str(exc.value)


def test_a_reader_that_declared_no_strings_and_sent_some_is_refused():
    lit = StringLiteral(routine_id="r", line=1, text="SELECT 1 FROM t")
    with pytest.raises(PluginRefused) as exc:
        judge(_facts(literals=[lit]), reports_literals=False)
    assert "reports_literals" in str(exc.value)


def test_a_language_that_reports_no_strings_contributes_no_sql_and_says_so():
    """A real answer and not an empty one (design rule 1)."""
    facts = judge(_facts(), reports_literals=False)
    assert facts.sql == [] and facts.artefacts == []

    stats = walk.WalkStats(no_literals=["kotlin"])
    said = " ".join(walk.walk_residue(stats))
    assert "kotlin" in said and "no SQL" in said


# ----------------------------------------------------------------- the bound --- #

def test_a_string_too_short_to_be_anything_never_leaves_the_reader(tmp_path):
    facts = _read(tmp_path, 'A = "w"\nB = "ab"\nC = "abc"\n')
    assert [lit.text for lit in facts.literals] == ["abc"]
    assert facts.literals_dropped == 2


def test_the_bound_is_the_union_of_what_either_judgement_can_accept():
    """Six is SQL's own and is applied in `_sql`; three is the shortest a file can be named.

    Taking six for both would be a bound written for one question quietly deciding another
    (rule 49). On Society it happens to cost nothing — the shortest artefact literal there
    is seven characters — which is not the same claim as *it cannot cost anything*.
    """
    assert literals.LITERAL_MIN == 3
    assert not literals.in_bounds("ab")
    assert literals.in_bounds("a.db")
    assert not literals.in_bounds("x" * (literals.LITERAL_MAX + 1))


def test_a_string_dropped_by_the_bound_is_counted_and_said(tmp_path):
    """A filter running where the host cannot look inside is the silent one (design rule 1)."""
    facts = _read(tmp_path, 'A = "w"\n')
    assert facts.literals_dropped == 1

    stats = walk.WalkStats(literals_dropped={"python": 4_022})
    said = " ".join(walk.walk_residue(stats))
    assert "4,022 python" in said and "3–200,000" in said


def test_a_whole_schema_block_is_reported_and_stored_whole(tmp_path):
    """Rule 8: a DDL statement cut off at eighty characters is no longer the schema."""
    ddl = "CREATE TABLE widgets (\n" + "".join(
        f"    col_{i:03d} TEXT NOT NULL,\n" for i in range(200)
    ) + "    id TEXT PRIMARY KEY\n)"
    facts = _judged(tmp_path, f'DDL = """{ddl}"""\n')
    assert len(ddl) > 5_000
    assert facts.literals[0].text == ddl
    assert [c[0] for c in facts.tables[0].columns][:2] == ["col_000", "col_001"]


# ------------------------------------------------------------ what was written --- #

def test_an_interpolated_stem_names_nothing_a_reader_could_look_up(tmp_path):
    facts = _judged(tmp_path, 'import os\nP = f"{os.sep}{name}.db"\n')
    assert [a.name for a in facts.artefacts] == []


def test_a_question_mark_somebody_typed_is_a_glob_and_not_a_placeholder(tmp_path):
    """`LiteralKind`'s whole job, and until it existed the glob lost (rule 30).

    Measured before it was taken: the artefact rows of Society are byte-identical either
    way, so this reading costs the golden nothing and gains the case it was written for.
    """
    facts = _judged(tmp_path, 'PATTERN = "chaos_?.py"\n')
    assert [(a.name, a.is_pattern) for a in facts.artefacts] == [("chaos_?.py", True)]


def test_an_interpolated_string_still_names_its_table_and_its_file(tmp_path):
    """The half that stays with the reader: assembling the text needs the tree."""
    facts = _judged(tmp_path, '_TABLE = "work_items"\n'
                              'ROOT = "/var"\n'
                              'DDL = f"CREATE TABLE {_TABLE} (id TEXT PRIMARY KEY)"\n'
                              'P = f"{ROOT}/tabularium.db"\n')
    assert [t.name for t in facts.tables] == ["work_items"]
    assert [a.name for a in facts.artefacts] == ["tabularium.db"]
    assert facts.literals[2].kind is LiteralKind.INTERPOLATED


def test_an_interpolated_string_is_reported_before_the_parts_it_was_built_from(tmp_path):
    """The order is a contract: one naming act per line keeps the fuller literal."""
    facts = _judged(tmp_path, 'P = f"{root}/tabularium.db"\n')
    assert facts.literals[0].kind is LiteralKind.INTERPOLATED
    assert [a.literal for a in facts.artefacts] == ["?/tabularium.db"]


def test_a_docstring_is_never_reported_as_a_string_to_judge(tmp_path):
    """Rule 9, and it stays with the reader because only the reader can see it."""
    facts = _judged(tmp_path, '"""Insert candidate into capture_queue for later."""\n'
                              'def f():\n'
                              '    """Select the widget from widgets by id."""\n')
    assert facts.literals == []
    assert facts.sql == []


# ------------------------------------------------------------- the module scope --- #

def test_the_module_scope_is_claimed_only_by_a_string_that_turned_out_to_be_a_fact(tmp_path):
    """The defect this split created, pinned at its measured size.

    `_owner()` minted the synthetic `<module>` routine for whichever fact asked first, so a
    file with nothing at module level got none — by accident, because nothing had asked. A
    *string* has to name an owner before anybody knows whether it is a fact, so asking there
    minted **65 of Society's 628 files** a routine owning nothing: a 1.3% inflation of every
    routine count in the map, decided by whether a string cleared a bound that exists to
    save wire (rule 96).
    """
    prose = _judged(tmp_path, 'GREETING = "hello there, reader"\n')
    assert prose.literals, "the string was reported"
    assert [r.name for r in prose.routines] == []
    assert prose.module_scope is not None, "prepared, and left unclaimed"

    fact = _judged(tmp_path, 'DB = "tabularium.db"\n')
    assert [r.name for r in fact.routines] == ["<module>"]
    assert fact.artefacts[0].routine_id == fact.module_scope.id


def test_the_prepared_module_scope_carries_the_language_whether_claimed_or_not(tmp_path):
    """It is a record inside these facts, and `stamp_lang` is the one place `lang` is written."""
    facts = _judged(tmp_path, 'GREETING = "hello there, reader"\n')
    assert facts.module_scope is not None and facts.module_scope.lang == "python"


def test_a_routine_that_owns_the_string_is_claimed_the_way_it_always_was(tmp_path):
    facts = _judged(tmp_path, 'def f():\n    return "SELECT id FROM widgets"\n')
    assert [r.name for r in facts.routines] == ["f"]
    assert facts.sql[0].routine_id == facts.routines[0].id


def test_the_claim_is_not_repeated_when_a_file_has_both_kinds_of_fact(tmp_path):
    facts = _judged(tmp_path, 'import os\n'
                              'HOME = os.environ["HOME"]\n'
                              'DB = "tabularium.db"\n')
    names = [r.name for r in facts.routines]
    assert names == ["<module>"], names


# ----------------------------------------------------------------- the walk --- #

def test_the_walk_judges_what_a_reader_brought_back(tmp_path):
    """The one place both kinds of reader pass through (rule 51)."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text('DDL = "CREATE TABLE widgets (id TEXT)"\n'
                              'A = "w"\n', encoding="utf-8")
    from dunneflow.store import Store
    store = Store(tmp_path / "g.db")
    stats = walk.analyze_tree(src, store)
    assert stats.parsed == 1
    assert store.conn.execute("SELECT count(*) FROM db_tables").fetchone()[0] == 1
    assert stats.literals_dropped == {"python": 1}
    assert stats.no_literals == []
    store.close()


def test_the_stored_sql_and_artefacts_are_the_hosts(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text('DB = "tabularium.db"\n'
                              'Q = "SELECT id FROM widgets"\n', encoding="utf-8")
    from dunneflow.store import Store
    store = Store(tmp_path / "g.db")
    walk.analyze_tree(src, store)
    assert store.conn.execute("SELECT count(*) FROM artefacts").fetchone()[0] == 1
    assert store.conn.execute("SELECT count(*) FROM sql_ops").fetchone()[0] == 1
    assert store.conn.execute("SELECT count(*) FROM routines").fetchone()[0] == 1
    store.close()


def test_one_statement_is_recorded_once_however_often_the_line_is_visited(tmp_path):
    """The dedupe that was a field on the extractor and is now per judgement."""
    facts = _judged(tmp_path, 'Q = "SELECT id FROM widgets"\n'
                              'R = "SELECT id FROM widgets"\n')
    assert len(facts.sql) == 2, "two lines are two statements"
    same_line = _facts(literals=[
        StringLiteral(routine_id="r", line=4, text="SELECT id FROM widgets"),
        StringLiteral(routine_id="r", line=4, text="SELECT id FROM widgets"),
    ])
    assert len(judge(same_line).sql) == 1


def test_a_statement_the_host_produced_names_the_routine_the_reader_stood_in(tmp_path):
    """The host cannot recompute it: a line number is all that is left of where anything was."""
    facts = _judged(tmp_path, 'def f():\n'
                              '    return "SELECT id FROM widgets"\n'
                              'def g():\n'
                              '    return "SELECT id FROM gadgets"\n')
    by_id = {r.id: r.name for r in facts.routines}
    assert [by_id[op.routine_id] for op in facts.sql] == ["f", "g"]
    assert isinstance(facts.sql[0], SqlStatement)
