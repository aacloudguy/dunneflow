"""Identity must survive editing, because the change view depends on it.

A routine is the same routine after code moves around it. If identity were derived
from file position, adding one import at the top of a file would retire every routine
in it and introduce identical replacements -- and a week of ordinary work would render
as thousands of false deletions. These tests exist to stop that regressing.

Identity answers "is this the same routine?"; `body_hash` answers "did it change?".
The two must stay independent.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.extractors.python.extract import extract_file

BASE = '''import os


def alpha(x: int) -> str:
    return str(x)


def beta() -> None:
    os.getenv("A")
'''

SHIFTED = "import sys\n" + BASE

EDITED = '''import os


def alpha(x: int) -> str:
    os.getenv("NEW_VAR")
    return str(x)


def beta() -> None:
    os.getenv("A")
'''


def _by_qualname(tmp_path: Path, name: str, source: str) -> dict:
    root = tmp_path / name
    root.mkdir()
    (root / "m.py").write_text(source, encoding="utf-8")
    facts = extract_file(root / "m.py", root)
    assert not facts.errors, facts.errors
    return {r.qualname: r for r in facts.routines}


def test_identity_survives_a_position_shift(tmp_path):
    a = _by_qualname(tmp_path, "a", BASE)
    b = _by_qualname(tmp_path, "b", SHIFTED)
    for qualname, routine in a.items():
        assert routine.id == b[qualname].id, f"{qualname} lost its identity when it moved"


def test_a_position_shift_does_not_look_like_a_change(tmp_path):
    a = _by_qualname(tmp_path, "a", BASE)
    b = _by_qualname(tmp_path, "b", SHIFTED)
    for qualname, routine in a.items():
        assert routine.body_hash == b[qualname].body_hash, (
            f"{qualname} appears edited but only moved"
        )
        assert routine.line_start != b[qualname].line_start  # it really did move


def test_identity_survives_a_real_edit(tmp_path):
    a = _by_qualname(tmp_path, "a", BASE)
    c = _by_qualname(tmp_path, "c", EDITED)
    assert a["m.alpha"].id == c["m.alpha"].id


def test_a_real_edit_is_visible_and_contained(tmp_path):
    a = _by_qualname(tmp_path, "a", BASE)
    c = _by_qualname(tmp_path, "c", EDITED)
    assert a["m.alpha"].body_hash != c["m.alpha"].body_hash
    assert a["m.beta"].body_hash == c["m.beta"].body_hash, (
        "an untouched routine must not look edited"
    )


def test_identity_does_not_depend_on_the_file_path(tmp_path):
    """The same module analysed from two checkouts must yield the same identities."""
    a = _by_qualname(tmp_path, "checkout_one", BASE)
    b = _by_qualname(tmp_path, "checkout_two", BASE)
    assert {q: r.id for q, r in a.items()} == {q: r.id for q, r in b.items()}


def test_duplicate_qualnames_keep_separate_identities(tmp_path):
    """A broken program must still document: colliding definitions do not merge."""
    dup = "def same() -> None:\n    pass\n\n\ndef same() -> int:\n    return 1\n"
    routines = _by_qualname(tmp_path, "dup", dup)
    # the dict collapses by qualname, so re-extract to count raw entries
    root = tmp_path / "dup2"
    root.mkdir()
    (root / "m.py").write_text(dup, encoding="utf-8")
    facts = extract_file(root / "m.py", root)
    same = [r for r in facts.routines if r.name == "same"]
    assert len(same) == 2
    assert same[0].id != same[1].id, "colliding definitions must keep distinct ids"
    assert routines  # sanity
