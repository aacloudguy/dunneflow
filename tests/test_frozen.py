"""What a packaged DunneFlow has to get right, tested without packaging one.

Every question here has two answers -- one for a source checkout and one for a frozen
application -- and only the first is ever exercised by running the tests. So the second
world is put on by monkeypatching `sys.frozen` and `sys._MEIPASS`, which is exactly what
PyInstaller sets and nothing else does.

The guards at the foot are the ones that matter longest. A build defect here does not
raise: it produces a confident wrong answer -- a fingerprint of nothing, a page of 404s,
a subprocess that never starts -- and the next person to add a data path will add it the
way every one of these was written, with `Path(__file__)`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from dunneflow import runtime
from dunneflow.cli import _out_root, build_parser
from dunneflow.detectors import (
    RulesMissing,
    code_extraction_inputs,
    fingerprint_files,
    rules_fingerprint,
)
from dunneflow.detectors.prose import doc_extraction_inputs, doc_rules_fingerprint
from dunneflow.web.analysis import argv

SRC = Path(runtime.__file__).parent

# The sha256 of nothing, shortened the way `fingerprint_files` shortens. This is what the
# function used to return for an empty input, and it is the whole reason for the refusal:
# it looks exactly like a fingerprint and compares equal to itself for ever, so rule 12's
# guarantee would have been enforced by a constant.
HASH_OF_NOTHING = "e3b0c44298fc1c14"


@pytest.fixture
def as_frozen(monkeypatch, tmp_path):
    """Put the module under test in the world PyInstaller makes.

    `_MEIPASS` is the unpacked bundle, and the spec places this package's data under
    `dunneflow/` inside it -- so the fixture builds that directory rather than pointing at
    the bare temporary path, because the layout is the thing being asserted about.
    """
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    (tmp_path / "dunneflow").mkdir()
    return tmp_path


# --------------------------------------------------------------------------- #
# The fingerprint, which is the blocker that would have failed silently


def test_a_fingerprint_of_nothing_is_refused():
    with pytest.raises(RulesMissing) as exc:
        fingerprint_files([])
    # The sentence has to name where this build looked, because the answer to it is a
    # change to a spec file and nothing else (rule 89).
    assert str(SRC) in str(exc.value)


def test_a_named_and_absent_input_is_refused(tmp_path):
    """The frozen failure is this one, not the empty list.

    `doc_extraction_inputs()` returns `Path(__file__)` unconditionally, so frozen the list
    is never empty -- it holds a path that is not a file. An emptiness check alone passes
    that straight through to a `FileNotFoundError` raised from inside a hash.
    """
    here = tmp_path / "real.yaml"
    here.write_text("a: 1")
    with pytest.raises(RulesMissing) as exc:
        fingerprint_files([here, tmp_path / "gone.yaml"])
    assert "gone.yaml" in str(exc.value)
    assert "1 of 2" in str(exc.value)


def test_a_directory_is_not_a_rule_file(tmp_path):
    """`is_file()` rather than `exists()`, and the difference is a real mistake.

    A `datas` entry that names a directory where a file was meant unpacks as a directory,
    which exists -- and then `read_bytes()` raises `IsADirectoryError` from inside the
    hash, one frame further on than the `FileNotFoundError` above.
    """
    (tmp_path / "docs").mkdir()
    with pytest.raises(RulesMissing):
        fingerprint_files([tmp_path / "docs"])


def test_neither_fingerprint_is_the_hash_of_nothing():
    assert rules_fingerprint() != HASH_OF_NOTHING
    assert doc_rules_fingerprint() != HASH_OF_NOTHING
    assert rules_fingerprint() != doc_rules_fingerprint()


@pytest.mark.parametrize("inputs", [code_extraction_inputs, doc_extraction_inputs],
                         ids=["code", "docs"])
def test_every_extraction_input_is_a_file_that_exists(inputs):
    """The membership assertion the two `*_inputs` functions were split out for.

    A missing entry is now loud rather than silent, so this is no longer the only thing
    standing between a bad bundle and a hash of nothing -- but it is the one that says
    *which* file, at the moment somebody moves one.
    """
    found = inputs()
    assert found, f"{inputs.__name__} found nothing"
    absent = [p for p in found if not p.is_file()]
    assert not absent, f"{inputs.__name__} names files that are not there: {absent}"


def test_the_two_keys_do_not_share_a_reader():
    """Editing a prose rule must not discard the code graph, and the reverse.

    Stated in `rules_fingerprint`'s docstring as the reason `detectors/docs/` and
    `prose.py` are absent from the code key. Asserted here because both lists now come
    from `resource_root()`, and a resource root is exactly the sort of change that makes
    two globs start overlapping.
    """
    code = {p.relative_to(SRC) for p in code_extraction_inputs()}
    docs = {p.relative_to(SRC) for p in doc_extraction_inputs()}
    # By relative path and never by name: both keys hold a file called `__init__.py`, and
    # they are two different files. That is `fingerprint_files`' own labelling argument,
    # and comparing names here would report an overlap that does not exist.
    assert code & docs == {Path("detectors/annotations.yaml")}


# --------------------------------------------------------------------------- #
# The two worlds


def test_this_is_not_a_frozen_build():
    assert runtime.frozen() is False
    assert runtime.resource_root() == SRC


def test_the_bundle_keeps_the_package_as_its_last_segment(as_frozen):
    """`fingerprint_files` labels each input relative to this root.

    So a bundle laid out with `dunneflow/` under `_MEIPASS` yields the labels the checkout
    yields -- `detectors/python.yaml`, not `python.yaml` -- and the two builds agree on a
    fingerprint at the same commit. Laid out any other way they would refuse each other's
    maps under rule 12, which is the opposite of what that rule is for.
    """
    assert runtime.frozen() is True
    assert runtime.resource_root() == as_frozen / "dunneflow"
    assert runtime.resource_root().name == SRC.name


def test_self_argv_names_a_module_only_where_there_is_an_interpreter(as_frozen):
    """`-m dunneflow.cli` is meaningless to a frozen binary; it *is* DunneFlow."""
    assert runtime.self_argv("analyze", "/tmp/x") == [sys.executable, "analyze", "/tmp/x"]


def test_self_argv_from_a_checkout():
    assert runtime.self_argv("analyze") == [sys.executable, "-m", "dunneflow.cli", "analyze"]


def test_the_analysis_subprocess_runs_this_same_build(as_frozen, tmp_path):
    """Blocker 3, at the surface it would have broken.

    **+ Analyze a directory...** is the only way a first-time reader gets a map at all,
    and it is the one build where it is the only way in.
    """
    cmd = argv(tmp_path, "x", tmp_path, docs=True)
    assert "-m" not in cmd
    assert cmd[0] == sys.executable
    assert cmd[1] == "analyze"
    assert "--progress-json" in cmd and "--quiet" in cmd


def test_the_output_root_from_a_checkout():
    assert runtime.default_output_root() == Path("output")


@pytest.mark.skipif(sys.platform != "darwin", reason="the other two branches are untested")
def test_the_output_root_of_an_application(as_frozen):
    """Application Support, never Documents -- and that is not tidiness.

    `source.db` holds the private source of whatever was read, and `~/Documents` is swept
    into iCloud Drive on a signed-in Mac. That would be egress by accident, out of a tool
    whose posture is deterministic and local (design rule 14).
    """
    root = runtime.default_output_root()
    assert root == Path.home() / "Library" / "Application Support" / "DunneFlow"
    assert root.is_absolute()
    assert "Documents" not in root.parts


# --------------------------------------------------------------------------- #
# The guards


def _module_sources():
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_only_runtime_finds_this_package_by_its_own_file():
    """`Path(__file__)` means *my files* in four places, and frozen it is wrong in all of them.

    A module imported out of a PyInstaller archive has a `__file__` naming a path that
    does not exist, so a glob under it comes back empty and a read of it raises. The four
    that mattered were the two rule directories, the two extractor trees they reach, and
    `web/`'s `static` and `vendor` -- a server that starts perfectly and serves 404s.

    The next one will be added by somebody who has not read any of that, which is what
    this is for. `runtime.py` is the one exemption because answering this question is what
    it is (rule 51).
    """
    offenders = []
    for path in _module_sources():
        if path.name == "runtime.py":
            continue
        # Parsed, never scanned. The first spelling of this guard read the file line by
        # line and reported **its own explanation of the rule** as a violation -- rule 34,
        # which is about exactly this: the thing being looked for hides in the prose about
        # it. An AST holds code and nothing else.
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Name) and node.id == "__file__":
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, (
        "these derive a location from `__file__` rather than `runtime.resource_root()`, "
        "which is empty in a packaged application:\n  " + "\n  ".join(offenders))


def test_freeze_support_is_the_first_thing_main_does():
    """Blocker 2, asserted structurally rather than by running sixteen servers.

    macOS spawns, so every pool worker re-executes this program. In a checkout that
    re-executes the interpreter; in a frozen application it re-executes *the application*.
    Nothing in the parent raises, so `walk.py`'s serial fallback never sees it -- the
    parent is fine and the children are the program.

    A guard can only see that a call is written, never that it ran (rule 86). What it
    *can* see is that nothing is written in front of it, which is the whole requirement.
    """
    tree = ast.parse((SRC / "cli.py").read_text(encoding="utf-8"))
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    body = [n for n in main.body if not isinstance(n, ast.Expr)
            or not isinstance(n.value, ast.Constant)]      # past the docstring
    first = body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call), \
        f"main() begins with {ast.dump(first)[:60]}, not a call"
    assert ast.unparse(first.value.func) == "multiprocessing.freeze_support"


def test_nothing_on_the_analysis_path_spells_out_the_interpreter():
    """One place decides how to run this build again, and it is `runtime.self_argv`.

    `sys.executable` beside a hand-written `-m` is the shape blocker 3 had. It is right in
    a checkout, which is why it survived: it fails only where it is the only way in.
    """
    offenders = []
    for path in _module_sources():
        if path.name == "runtime.py":
            continue
        # An AST, for the reason one guard up: written out as prose, `sys.executable`
        # beside a `-m` is a description of the defect and not the defect.
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Attribute) and node.attr == "executable"
                    and isinstance(node.value, ast.Name) and node.value.id == "sys"):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, (
        "these build a command for this program by hand; `runtime.self_argv` is the one "
        "place that knows how:\n  " + "\n  ".join(offenders))


# --------------------------------------------------------------------------- #
# The default that moved


def test_the_output_root_says_so_when_nobody_chose_it(capsys):
    """Two answers to one question, and the fallback names the one it took.

    `--output` defaulted to the literal `output`, relative to whatever working directory
    the command was run from. That is right for a checkout and meaningless for a
    double-clicked application. A default that quietly moves between the two is the sort of
    silence that costs a session hunting for a map that was written somewhere else.
    """
    args = build_parser().parse_args(["analyze", "src"])
    assert args.output is None, "the default is resolved at use, not by argparse"
    assert _out_root(args) == runtime.default_output_root()
    said = capsys.readouterr().err
    assert "no --output given" in said
    assert str(runtime.default_output_root()) in said


def test_a_chosen_output_root_is_taken_in_silence(capsys):
    args = build_parser().parse_args(["analyze", "src", "--output", "/tmp/somewhere"])
    assert _out_root(args) == Path("/tmp/somewhere")
    assert capsys.readouterr().err == ""
