"""Every comment reaches the store, and lands on something.

Comments were collected per function -- the block above a definition, and everything
inside its line span. Everything else was dropped: **9,659 of Mensores' 18,208 comments,
53%**, because the synthetic `<module>` routine is created on demand and was never
handed any. Whole files lost every comment they had, the `*_extras_schemas.py` modules
worst of all, which are almost entirely module-level commentary.

The cost was not readability. Comments are the only source of the WHY layer and of the
governance annotations, and the unclaimed half carried 2,270 of them across 438 distinct
ids -- 76 the graph had never seen, 75 of those documented in the corpus. Closing it
moved 47 plans out of "a document is about it, but no comment cites it" into "the code
says it landed", and lifted ids cited in code from 517 to 593.

The test that matters is the total: **no comment token may go unclaimed.** Counting the
tokens rather than asserting on named cases is deliberate -- the defect was a whole
category nobody had thought to name, and only a total catches the next one.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import pytest

from dunneflow.extractors.python.extract import (
    MODULE_SCOPE,
    collect_comments,
    extract_file,
)

# Every place a comment can sit. Before the fix only the two inside `worker` survived.
PROGRAM = '''
"""Module docstring. Not a comment, and never mined as one."""

# A file-header comment, above every definition. Plan 01-01 governs this module.
# It continues onto a second line, which is also a comment.

import os

# A comment above a module-level constant. ADR-0042 decided this value.
LIMIT = 10

TABLE = "widgets"   # an inline comment on a module-level statement


class Holder:
    """A class whose body carries commentary of its own."""

    # A comment inside the class body, above a field. ISS-777 tracks it.
    size: int = 0

    def worker(self) -> None:
        # A comment leading nothing, inside a method. Plan 02-02.
        value = os.environ["X"]
        return value   # an inline comment inside a method


# A trailing comment at the very end of the file. ADR-0099.
'''


@pytest.fixture(scope="module")
def facts(tmp_path_factory):
    root = tmp_path_factory.mktemp("commented")
    (root / "prog.py").write_text(PROGRAM, encoding="utf-8")
    return extract_file(root / "prog.py", root), PROGRAM


def _claimed(ff) -> set[int]:
    return {c.line for r in ff.routines for c in r.comments}


# --------------------------------------------------------------------------- #
# The total. This is the assertion the defect would have failed.
# --------------------------------------------------------------------------- #


def test_no_comment_token_goes_unclaimed(facts):
    ff, src = facts
    every = set(collect_comments(src))
    assert every, "the fixture must contain comments for this to mean anything"
    assert _claimed(ff) == every, (
        f"unclaimed comment lines: {sorted(every - _claimed(ff))}"
    )


def test_the_count_is_measured_on_tokens_not_on_hashes(facts):
    """A `#` inside a string is not a comment.

    The first measurement of this defect was inflated by prompt strings whose lines
    begin with `#`. `collect_comments` tokenizes, so this stays honest.
    """
    _, src = facts
    tokenized = {
        t.start[0]
        for t in tokenize.generate_tokens(io.StringIO(src).readline)
        if t.type == tokenize.COMMENT
    }
    assert set(collect_comments(src)) == tokenized


# --------------------------------------------------------------------------- #
# Where the previously-lost ones land
# --------------------------------------------------------------------------- #


def _module_routine(ff):
    return next(r for r in ff.routines if r.name == MODULE_SCOPE)


@pytest.mark.parametrize(
    "fragment",
    [
        "A file-header comment",
        "It continues onto a second line",
        "above a module-level constant",
        "an inline comment on a module-level statement",
        "inside the class body",
        "trailing comment at the very end",
    ],
)
def test_a_comment_outside_every_function_belongs_to_the_module_scope(facts, fragment):
    """A class body runs at import, which is what the module scope already means.

    `_owner()` assigns boundaries, calls and SQL found in a class body to this same
    routine. Putting comments anywhere else would invent a second ownership model for
    one fact type.
    """
    ff, _ = facts
    texts = " | ".join(c.text for c in _module_routine(ff).comments)
    assert fragment in texts


def test_a_comment_inside_a_function_still_belongs_to_that_function(facts):
    """The fix must not move what already worked."""
    ff, _ = facts
    worker = next(r for r in ff.routines if r.name == "worker")
    texts = " | ".join(c.text for c in worker.comments)
    assert "A comment leading nothing" in texts
    assert "an inline comment inside a method" in texts
    assert "A file-header comment" not in texts


def test_the_module_scope_is_created_for_comments_alone(tmp_path):
    """A file with nothing but commentary must still keep it.

    This is the case that lost whole files: `_role_prompts.py` had 35 comments and
    stored none, because nothing in it ever asked `_owner()` for an owner.
    """
    (tmp_path / "only.py").write_text(
        "# Nothing here but a comment. Plan 03-03.\nX = 1\n", encoding="utf-8"
    )
    ff = extract_file(tmp_path / "only.py", tmp_path)
    assert [c.text for c in _module_routine(ff).comments] == [
        "Nothing here but a comment. Plan 03-03."
    ]


def test_a_file_with_no_comments_grows_no_module_routine(tmp_path):
    """The scope is created on demand, not for every file in the tree."""
    (tmp_path / "bare.py").write_text("X = 1\n", encoding="utf-8")
    ff = extract_file(tmp_path / "bare.py", tmp_path)
    assert [r for r in ff.routines if r.name == MODULE_SCOPE] == []


# --------------------------------------------------------------------------- #
# Governance: the reason this mattered
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "identifier", ["Plan 01-01", "ADR-0042", "ISS-777", "ADR-0099"]
)
def test_a_governance_id_stated_outside_a_function_is_mined(facts, identifier):
    """2,270 annotations across 438 ids were invisible for exactly this reason."""
    ff, _ = facts
    values = {a.value for r in ff.routines for a in r.annotations}
    assert identifier in values


def test_a_comment_is_not_mined_twice(facts):
    """Orphans are claimed after the walk, so nothing already owned is re-read.

    The triple, not the pair: one marker legitimately matches two detectors, because
    `ADR-0042` satisfies both the ADR rule and the general TICKET rule. That is known
    and deliberate -- 574 such rows on Mensores -- and the traceability report
    deduplicates on exactly the triple its shipped query selects. Asserting on
    `(value, line)` alone fails on that and says nothing about this fix.
    """
    ff, _ = facts
    seen: dict[tuple[str, str, int], int] = {}
    for routine in ff.routines:
        for a in routine.annotations:
            key = (a.kind, a.value, a.line)
            seen[key] = seen.get(key, 0) + 1
    repeated = {k: v for k, v in seen.items() if v > 1}
    assert not repeated, f"mined more than once: {repeated}"


def test_the_module_docstring_is_not_read_as_a_comment(facts):
    """Rule 9 holds in both directions. A docstring is a sentence, not a comment."""
    ff, _ = facts
    texts = " | ".join(c.text for r in ff.routines for c in r.comments)
    assert "Module docstring" not in texts
    assert "A class whose body carries" not in texts


def test_incremental_re_extraction_is_stable(tmp_path):
    """Extracting the same file twice must give the same comments, not double them."""
    (tmp_path / "p.py").write_text(PROGRAM, encoding="utf-8")
    first = extract_file(tmp_path / "p.py", tmp_path)
    second = extract_file(tmp_path / "p.py", tmp_path)
    assert _claimed(first) == _claimed(second)
    assert (
        sum(len(r.comments) for r in first.routines)
        == sum(len(r.comments) for r in second.routines)
    )


def test_identity_of_the_module_scope_does_not_move(tmp_path):
    """The module scope is keyed by module name, never by position.

    Adding a comment at the top of a file must not retire the module routine and
    introduce an identical replacement -- the same rule `tests/test_identity.py`
    guards for every other routine, and the prerequisite for temporal layers.
    """
    p: Path = tmp_path / "q.py"
    p.write_text("# one. Plan 04-04\nX = 1\n", encoding="utf-8")
    before = _module_routine(extract_file(p, tmp_path)).id
    p.write_text("# added above\n# one. Plan 04-04\nX = 1\n", encoding="utf-8")
    assert _module_routine(extract_file(p, tmp_path)).id == before


# --------------------------------------------------------------------------- #
# A module about testing is not a test
# --------------------------------------------------------------------------- #


def _python_rules():
    """How the Python reader spells *this is a test*, straight off its manifest."""
    from dunneflow import ingest

    return ingest.PLUGINS["python"].manifest.discovery


@pytest.mark.parametrize(
    "name",
    ["test_thing.py", "thing_test.py", "conftest.py"],
)
def test_a_real_test_is_still_excluded(name):
    assert _python_rules().is_test(Path(name))


@pytest.mark.parametrize(
    "name",
    ["_test_stage.py", "_test_extras_schemas.py", "latest_run.py", "contest.py"],
)
def test_a_module_that_merely_contains_the_word_is_not(name):
    """Rule 5 in the walk.

    `_test_stage.py` is the real Test stage of the Groma pipeline (Plan 30-02), and
    the substring match dropped it and two others from the map entirely -- routines,
    boundaries, comments and all. Found while checking why 30 comments were still
    missing after the module-scope fix; the answer was that their files were never
    read.

    Asked of the **Python plugin's** rules now rather than of `walk.is_test_path`, which
    is gone: the rule is per language because a test is spelled per language, and this
    file is what says the move carried Python's spelling across whole.
    """
    assert not _python_rules().is_test(Path(name))


def test_a_tests_directory_is_still_excluded():
    assert _python_rules().is_test(Path("tests/helpers/thing.py"))


# --------------------------------------------------------------- doc markers --- #

def test_sphinx_doc_comment_marker_is_stripped_but_an_rst_role_is_not():
    """`#:` is syntax; `# :mod:` is text. The difference is whether it touches the hash.

    Both shapes are live in Mensores -- 1,698 comments carry the marker and some of the
    rest open with a reStructuredText role. A stripper that took any leading colon would
    read `:mod:` as a marker and shorten a value at ingest, which is rule 12's `<role>`
    lesson and rule 5's "a marker must sit at an edge".
    """
    from dunneflow.extractors.python.extract import collect_comments

    src = (
        "#: Keychain service name. Matches the operator's item.\n"
        "# :mod:`mensores._internal._sanitize`. The previous definition is gone.\n"
        "#:\n"
        "#\n"
        "### banner ###\n"
        "x = 1\n"
    )
    got = collect_comments(src)
    assert got[1] == "Keychain service name. Matches the operator's item."
    assert got[2] == ":mod:`mensores._internal._sanitize`. The previous definition is gone."
    assert got[3] == ""          # a bare `#:` is an empty line, not a colon
    assert got[4] == ""
    assert got[5] == "banner ###"
