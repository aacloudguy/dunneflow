"""What version a program says it is, and how honestly it says it.

The whole risk in this module is a **false claim**: reporting a version the program never
stated, or reporting a guess as though it were something read. Both look identical on
screen, and both are worse than the blank that "no version" honestly deserves.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.resolve import version as v
from dunneflow.schema import Provenance


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


# --------------------------------------------------------------------------- #
# Quoted
# --------------------------------------------------------------------------- #


def test_pyproject_version_is_read_with_the_file_that_proves_it(tmp_path):
    root = _tree(tmp_path, {
        "pyproject.toml": '[project]\nname = "thing"\nversion = "1.2.3"\n',
        "src/thing/__init__.py": "",
    })
    got = v.detect(root / "src", package_root=root, leaf="thing")
    assert got is not None
    assert got.value == "1.2.3"
    assert got.provenance is Provenance.DECLARED_CODE
    assert got.inferred is False


def test_a_src_layout_says_the_metadata_is_above_the_code(tmp_path):
    """`../pyproject.toml`, and a prefix strip cannot express it.

    Rule 61's companion. Packaging metadata sits one directory above a `src/` tree, so the
    honest relative path escapes the analysed root — and a `where` that quietly dropped the
    `..` would name a file that is not there.
    """
    root = _tree(tmp_path, {
        "pyproject.toml": '[project]\nversion = "9.9"\n',
        "src/thing/__init__.py": "",
    })
    got = v.detect(root / "src", package_root=root, leaf="thing")
    assert got is not None and got.where == "../pyproject.toml"


def test_a_module_scope_dunder_is_read_with_its_line(tmp_path):
    """The tier the constants table deliberately refuses to carry.

    `collect_module_names` filters dunders out on purpose — right for the glossary, and
    exactly why this reads the file itself. The filter must stay: a version is packaging
    metadata, which is precisely what that comment says it is.
    """
    root = _tree(tmp_path, {"thing/__init__.py": '"""Doc."""\n\n__version__ = "4.5.6"\n'})
    got = v.detect(root, leaf="thing")
    assert got is not None
    assert got.value == "4.5.6"
    assert got.provenance is Provenance.DECLARED_CODE
    assert got.where.endswith(":3"), got.where


def test_pyproject_outranks_a_dunder(tmp_path):
    """Order is trust. What a program is published as beats what a module says it is."""
    root = _tree(tmp_path, {
        "pyproject.toml": '[project]\nversion = "1.0.0"\n',
        "thing/__init__.py": '__version__ = "0.0.1-dev"\n',
    })
    got = v.detect(root, package_root=root, leaf="thing")
    assert got is not None and got.value == "1.0.0"


def test_a_computed_dunder_is_not_a_version(tmp_path):
    """Rule 1: precision over recall.

    `__version__ = _read_it()` is a call nobody here has evaluated. Printing the
    expression would be a claim about a value that does not exist until the program runs.
    """
    root = _tree(tmp_path, {"thing/__init__.py": "__version__ = _read_it()\n"})
    assert v.detect(root, leaf="thing") is None


def test_a_dunder_inside_a_function_is_not_the_modules_version(tmp_path):
    """Module scope only — the same boundary constants and comments already use."""
    root = _tree(tmp_path, {
        "thing/__init__.py": 'def f():\n    __version__ = "nope"\n    return __version__\n',
    })
    assert v.detect(root, leaf="thing") is None


# --------------------------------------------------------------------------- #
# Inferred — allowed, provided it says so
# --------------------------------------------------------------------------- #


def test_a_directory_name_can_supply_a_version_and_is_marked_as_a_guess(tmp_path):
    """Tom's rule: we may infer from a directory name or a date, provided we say we did."""
    root = _tree(tmp_path, {"thing/__init__.py": ""})
    got = v.detect(root, leaf="society-2026-08-26")
    assert got is not None
    assert got.value == "2026-08-26"
    assert got.provenance is Provenance.INFERRED
    assert got.inferred is True
    assert "directory name" in got.where


def test_a_guess_is_only_offered_when_nothing_was_stated(tmp_path):
    """The stated version wins, and the directory is not consulted at all."""
    root = _tree(tmp_path, {"pyproject.toml": '[project]\nversion = "2.0"\n'})
    got = v.detect(root, package_root=root, leaf="thing-1.2.3")
    assert got is not None
    assert got.value == "2.0" and got.provenance is Provenance.DECLARED_CODE


def test_a_directory_with_no_version_in_its_name_yields_nothing(tmp_path):
    """No version is a real answer, and the common one.

    Reaching for something rather than returning None is how a tool starts reporting the
    project's name, a hash, or today's date as a version.
    """
    root = _tree(tmp_path, {"thing/__init__.py": ""})
    assert v.detect(root, leaf="mensores") is None


def test_a_version_marker_must_sit_at_the_end_of_the_name():
    """Rule 5 in a directory name: a marker must sit at an edge, or everything matches.

    `v2-notes-about-1.2` has a version-shaped token in the middle of a name that is about
    something else, and `2026` alone is a year rather than a version.
    """
    assert v.from_directory_name("api-v2-scratch") is None
    assert v.from_directory_name("notes2026") is None
    assert v.from_directory_name("build2") is None
    # …and the shapes that genuinely are one.
    assert v.from_directory_name("app-1.2.3").value == "1.2.3"
    assert v.from_directory_name("app_2026-08-26").value == "2026-08-26"


def test_the_real_corpus_answers_are_the_ones_recorded():
    """Verified against the two trees this project is checked against, not invented.

    Society states no `version` in `[project]` and no module-scope `__version__` — checked
    by reading its `pyproject.toml`, not assumed — so both of its versions fall to the
    inferred tier and must say so. DunneFlow itself states one and must not.
    """
    here = Path(__file__).resolve().parent.parent
    got = v.detect(here / "src", package_root=here, leaf=here.name)
    assert got is not None
    assert got.provenance is Provenance.DECLARED_CODE, (
        "DunneFlow declares its own version in pyproject.toml; reporting it as a guess "
        "would understate a claim the source actually makes"
    )
