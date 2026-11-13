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
    prog = _program(tmp_path, "lictores")
    assert where(prog) == (prog.resolve(), tmp_path.resolve())


def test_a_directory_holding_programs_is_a_root(tmp_path):
    _program(tmp_path, "lictores")
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
    _program(tmp_path, "lictores")
    _program(tmp_path, "dunneflow")
    said = no_map_here(tmp_path, tmp_path, None)
    assert "lictores" in said and "dunneflow" in said
    # The root itself is not one of the choices, however `program_dirs` reports it.
    # Split on the sentence's own words rather than on the first colon: the sentence opens
    # with a path, and on Windows that path starts `C:` -- so the first colon is the drive
    # letter's and the "listed programs" half came back holding the whole thing.
    assert tmp_path.name not in said.split("Under this root:", 1)[1]


def test_an_empty_root_names_the_command_instead(tmp_path):
    said = no_map_here(tmp_path, tmp_path, None)
    assert "dunneflow analyze" in said
    assert str(tmp_path) in said


def test_the_three_answers_are_three_different_sentences(tmp_path):
    """Design rule 21: collapsing any two would make *we did not look* read as *nothing there*."""
    _program(tmp_path, "lictores")
    said = {no_map_here(tmp_path, tmp_path, "2026-01-01T00:00:00Z"),
            no_map_here(tmp_path, tmp_path, None),
            no_map_here(tmp_path / "empty", tmp_path / "empty", None)}
    assert len(said) == 3


# --------------------------------------------------------------------------- #
# The field, and the guard that keeps it the only answer


def test_the_root_is_derived_once_when_nobody_says(tmp_path):
    prog = _program(tmp_path, "lictores")
    live = _Live(prog / "source.db", prog)
    try:
        assert live.out_root == tmp_path
    finally:
        live.close()


def test_a_root_given_outright_is_taken(tmp_path):
    """The case with no parent to take: a server opened on the root itself."""
    prog = _program(tmp_path, "lictores")
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


def test_nothing_spells_the_map_marker_for_itself():
    """`glob("graph*.db")` was written out three times, and a fourth was about to be.

    Twice in `program_dirs` and once re-implemented in `serve.where`, whose own docstring
    called it "the same question `analyze` asks" while asking it separately -- rule 51's
    exact shape, three copies of one rule waiting to disagree. `revisions.names_a_map` and
    `holds_a_map` are the one answer now, and the walk reads them rather than making a
    fourth.

    Parsed, never scanned. The pattern appears in the prose explaining it in at least four
    docstrings, and a check that reports its own explanation is rule 34 -- which this
    project has now paid for three times.
    """
    import dunneflow

    src = Path(dunneflow.__file__).parent
    owner = src / "revisions.py"
    offenders = []
    for mod in sorted(src.rglob("*.py")):
        if mod == owner:
            continue
        tree = ast.parse(mod.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in {"glob", "rglob"}:
                continue
            if not node.args:
                continue
            written = ast.unparse(node.args[0])
            # The literal and its f-string form, which is how the three copies were spelt.
            if "graph" in written.lower() and ".db" in written.lower():
                rel = mod.relative_to(src.parent)
                offenders.append(f"{rel}:{node.lineno}: {ast.unparse(node)}")
    assert not offenders, (
        "these spell the map marker for themselves instead of asking "
        "`revisions.holds_a_map` or `revisions.names_a_map`, which is how there came to "
        "be three answers to one question (rule 51):\n  " + "\n  ".join(offenders))


# --------------------------------------------------------------------------- #
# The one refusal that has no subject when nothing is open


def test_analysing_into_the_served_program_is_refused(tmp_path):
    _program(tmp_path, "lictores")
    tree = tmp_path.parent / "atree"
    tree.mkdir(exist_ok=True)
    v = analysis.check(str(tree), "lictores", tmp_path, tmp_path / "lictores")
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
    v = analysis.check(str(tree), "lictores", tmp_path, None)
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


# --------------------------------------------------------------------------- #
# A program directory is a key before it is a location


def _linked(tmp_path: Path) -> tuple[Path, Path]:
    """A maps root, and a symlink to it. Skips where the platform will not make one.

    Not a contrived shape: `/tmp` and `/var/folders` are both symlinks on macOS, so any
    tool whose maps root is a temporary directory is already standing on this -- which is
    exactly how `tools/ordering.py` met it.
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:      # Windows without the privilege
        pytest.skip(f"this platform will not make a symlink here: {exc}")
    return real, link


def test_a_root_reached_through_a_symlink_names_each_program_once(tmp_path):
    """The same directory reached two ways must compare equal, or a set cannot deduplicate.

    `_r_programs` unions `out_dir.resolve()` with this listing to mark which row is open.
    Unresolved, the two were unequal `Path` objects naming one directory: every program
    came back twice and the *unmarked* copy was this function's. Rule 60's argument about a
    stored path, one question over.
    """
    real, link = _linked(tmp_path)
    _program(real, "lictores")

    assert revisions.program_dirs(link) == revisions.program_dirs(real)
    # The union `_r_programs` actually makes, spelled here so the test fails on the defect
    # rather than on a proxy for it (rule 37).
    here = (link / "lictores").resolve()
    assert revisions.program_dirs(link) | {here} == {real / "lictores"}


def test_a_program_that_is_itself_a_symlink_stays_under_the_root_that_lists_it(tmp_path):
    """The root is canonicalised; a child is **not** followed, and that is deliberate.

    A map kept on another disk and linked into the maps root is still this root's program,
    and `resolve()` on the child would name it somewhere else entirely -- so the switch
    would refuse a program the list had just offered. Only the root moves.
    """
    real, link = _linked(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    _program(elsewhere, "lictores")
    (real / "lictores").symlink_to(elsewhere / "lictores", target_is_directory=True)

    assert revisions.program_dirs(link) == {real / "lictores"}


def test_the_root_is_never_one_of_its_own_programs_however_it_was_reached(tmp_path):
    """`programs_under` is the exclusion five callers were spelling for themselves.

    Against an unresolved root `d != out_root` is false for the very directory it excludes,
    so a root reached through a symlink listed *itself* as a program -- the second half of
    the same defect, and the reason the comparison now lives beside the resolution (rule 51).
    """
    real, link = _linked(tmp_path)
    revisions.db_path(real, revisions.GRAPH, "2026-01-01T00:00:00Z").touch()
    _program(real, "lictores")

    assert real in revisions.program_dirs(link), "the root holds a map and is one"
    assert revisions.programs_under(link) == [real / "lictores"]
    assert no_map_here(link, link, None).split("Under this root:", 1)[1].count("real") == 0
