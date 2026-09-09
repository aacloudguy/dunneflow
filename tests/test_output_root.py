"""The output root as a thing the server owns, rather than one it works out four times.

`serve` has always been handed a *program* directory and derived the root as its parent.
That is right for as long as there is a program directory, and a packaged application
starts with neither one nor a working directory to resolve a relative default against.

Four routes did that derivation for themselves -- the program list, the program switch,
the analysis, and the dialog's live pre-flight. Four copies of one derivation is where
rule 51 says the drift starts, and here it is also the thing that cannot survive having
nothing open.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dunneflow import revisions
from dunneflow.web import analysis
from dunneflow.web import serve as serve_mod
from dunneflow.web.serve import _Live, no_map_here, where

SERVE_PY = Path(serve_mod.__file__)


def _program(root: Path, name: str, revision: str = "2026-01-01T00:00:00Z") -> Path:
    """A directory that looks like a program to `program_dirs`, without an analysis.

    Only the *filename* decides, which is what `where()` reads too -- so an empty file of
    the right name is the whole fixture. Anything more would be testing the store.
    """
    d = root / name
    d.mkdir(parents=True)
    revisions.db_path(d, revisions.GRAPH, revision).touch()
    return d


# --------------------------------------------------------------------------- #
# Which of the two was handed over


def test_a_directory_holding_a_map_is_a_program(tmp_path):
    prog = _program(tmp_path, "mensores")
    assert where(prog) == (prog.resolve(), tmp_path.resolve())


def test_a_directory_holding_programs_is_a_root(tmp_path):
    _program(tmp_path, "mensores")
    _program(tmp_path, "dunneflow")
    assert where(tmp_path) == (tmp_path.resolve(), tmp_path.resolve())


def test_a_root_is_recognised_by_what_it_holds_and_never_by_its_name(tmp_path):
    """`program_dirs`' own bargain, one caller over.

    `output/` is a fine name for a directory of hand-written prose, and a directory called
    anything at all is a program if it holds a map. Deciding by name would turn a label
    into an identity (rule 30).
    """
    named = _program(tmp_path, "output")
    assert where(named)[0] == named.resolve()          # a program, despite the name
    plain = tmp_path / "notes"
    plain.mkdir()
    assert where(plain) == (plain.resolve(), plain.resolve())   # a root, despite the name


def test_a_legacy_bare_graph_is_still_a_program(tmp_path):
    """A directory written before revisions had names holds `graph.db` and no `@`."""
    d = tmp_path / "old"
    d.mkdir()
    (d / "graph.db").touch()
    assert where(d) == (d.resolve(), tmp_path.resolve())


# --------------------------------------------------------------------------- #
# Why there is nothing to serve -- three answers, never one


def test_a_named_version_that_is_not_here_says_so(tmp_path):
    said = no_map_here(tmp_path, tmp_path, "2026-01-01T00:00:00Z")
    assert "2026-01-01T00:00:00Z" in said
    assert "analyze" not in said, "the reader named a version; the command is not the fix"


def test_a_root_with_programs_names_them(tmp_path):
    """Rule 89: the reader's next move is a program name they cannot guess."""
    _program(tmp_path, "mensores")
    _program(tmp_path, "dunneflow")
    said = no_map_here(tmp_path, tmp_path, None)
    assert "mensores" in said and "dunneflow" in said
    # The root itself is not one of the choices, however `program_dirs` reports it.
    assert tmp_path.name not in said.split(":", 1)[1]


def test_an_empty_root_names_the_command_instead(tmp_path):
    said = no_map_here(tmp_path, tmp_path, None)
    assert "dunneflow analyze" in said
    assert str(tmp_path) in said


def test_the_three_answers_are_three_different_sentences(tmp_path):
    """Design rule 21: collapsing any two would make *we did not look* read as *nothing there*."""
    _program(tmp_path, "mensores")
    said = {no_map_here(tmp_path, tmp_path, "2026-01-01T00:00:00Z"),
            no_map_here(tmp_path, tmp_path, None),
            no_map_here(tmp_path / "empty", tmp_path / "empty", None)}
    assert len(said) == 3


# --------------------------------------------------------------------------- #
# The field, and the guard that keeps it the only answer


def test_the_root_is_derived_once_when_nobody_says(tmp_path):
    prog = _program(tmp_path, "mensores")
    live = _Live(prog / "source.db", prog)
    try:
        assert live.out_root == tmp_path
    finally:
        live.close()


def test_a_root_given_outright_is_taken(tmp_path):
    """The case with no parent to take: a server opened on the root itself."""
    prog = _program(tmp_path, "mensores")
    live = _Live(prog / "source.db", prog, tmp_path)
    try:
        assert live.out_root == tmp_path
    finally:
        live.close()


def test_no_route_works_the_output_root_out_for_itself():
    """`out_dir.parent` was the spelling in four places; the field is the only one now.

    A guard over the source because the four were identical, correct, and independently
    added -- which is exactly how the fifth arrives.
    """
    tree = ast.parse(SERVE_PY.read_text(encoding="utf-8"))
    # The one place that is allowed to derive it: the constructor's own default, which is
    # what makes the field the single answer rather than a fifth copy of the question.
    exempt = {n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Assign)
              and any(ast.unparse(t) == "self.out_root" for t in n.targets)}
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr != "parent":
            continue
        if node.lineno in exempt:
            continue
        written = ast.unparse(node)
        if "out_dir" in written and "out_root" not in written:
            offenders.append(f"{SERVE_PY.name}:{node.lineno}: {written}")
    assert not offenders, (
        "these derive the output root rather than reading `_Live.out_root`, which is the "
        "one thing a server with nothing open still knows:\n  " + "\n  ".join(offenders))


# --------------------------------------------------------------------------- #
# The one refusal that has no subject when nothing is open


def test_analysing_into_the_served_program_is_refused(tmp_path):
    _program(tmp_path, "mensores")
    tree = tmp_path.parent / "atree"
    tree.mkdir(exist_ok=True)
    v = analysis.check(str(tree), "mensores", tmp_path, tmp_path / "mensores")
    assert not v.ok
    assert "being read" in v.refusal


def test_with_nothing_open_that_refusal_has_no_subject(tmp_path):
    """`serving=None` is the state a packaged application starts in.

    Exactly one refusal depends on it, and with nothing being read it is not a refusal --
    it is a fact with no subject. A stand-in path would have to be a directory *name*, and
    a name that happened to match would refuse the first analysis a reader ever asks for.
    """
    tree = tmp_path.parent / "atree"
    tree.mkdir(exist_ok=True)
    v = analysis.check(str(tree), "mensores", tmp_path, None)
    assert v.ok, v.refusal


@pytest.mark.parametrize("name", ["..", "with/slash", ".hidden"])
def test_the_other_refusals_are_untouched_by_that(tmp_path, name):
    tree = tmp_path.parent / "atree"
    tree.mkdir(exist_ok=True)
    assert not analysis.check(str(tree), name, tmp_path, None).ok


def test_an_unnamed_analysis_still_borrows_the_directory_leaf(tmp_path):
    """Not a refusal, and worth pinning while the signature is being changed.

    `check` reads `name or source.name`, so an empty name is the ordinary case rather than
    a missing one -- the refusal is for a directory that has no leaf to lend, which is the
    filesystem root. The first spelling of the test above asserted the opposite and was
    wrong about the code rather than about the code being wrong.
    """
    tree = tmp_path.parent / "atree"
    tree.mkdir(exist_ok=True)
    assert analysis.check(str(tree), "", tmp_path, None).ok
