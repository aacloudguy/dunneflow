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
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

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


def test_identity_does_not_depend_on_where_the_tree_is(tmp_path):
    """The same module analysed from two checkouts must yield the same identities.

    **This is not in tension with rule 106**, and the distinction is the whole reason the
    path a definition carries is `stored_path`'s and not the one on this machine. What is in
    an id is where the file sits *inside the analysed tree*, which is a fact about the
    program; where the tree sits is a fact about a laptop, and two checkouts of one program
    must pair across it or nothing can be compared to anything (rule 60).
    """
    a = _by_qualname(tmp_path, "checkout_one", BASE)
    b = _by_qualname(tmp_path, "checkout_two", BASE)
    assert {q: r.id for q, r in a.items()} == {q: r.id for q, r in b.items()}


def test_identity_does_depend_on_where_the_file_is_in_the_tree(tmp_path):
    """Rule 106's own half, stated so the test above cannot be read as denying it.

    One file, one module name, two directories — and two identities, because a definition is
    keyed on the file it is written in. Without it `probe.py` and `probe.ts` are one routine.
    """
    one = tmp_path / "one"
    (one / "pkg").mkdir(parents=True)
    (one / "m.py").write_text(BASE, encoding="utf-8")
    (one / "pkg" / "m.py").write_text(BASE, encoding="utf-8")
    top = {r.qualname: r for r in extract_file(one / "m.py", one).routines}
    nested = {r.qualname: r for r in extract_file(one / "pkg" / "m.py", one).routines}
    assert top["m.alpha"].id != nested["pkg.m.alpha"].id


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


# ------------------------------------------------------------------- rule 106 --- #

def test_two_languages_in_one_directory_do_not_collide_on_an_id(tmp_path):
    """The tree that could not be analysed at all, analysed — rule 106.

    `tests/fixtures/polyglot/` holds `probe.py`, `probe.ts`, `probe.cpp` and `probe.kt`.
    Every reader derives a module name from the path with the suffix dropped, so all four
    are module `probe` and three of them declare `probe.main`. Keyed on the name alone that
    is one id in three languages, and the store said so:

        sqlite3.IntegrityError: UNIQUE constraint failed: routines.id

    The stems were forced apart for a day and are back, because a fixture that avoids the
    defect proves nothing about it. What is asserted is not *the ids differ* — a hash of
    different inputs differs by construction — but that **the analysis completes and every
    definition in it survives as itself**, which is what the collision took away.
    """
    root = Path(__file__).parent / "fixtures" / "polyglot"
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)

    rows = list(store.query("SELECT id, qualname, lang FROM routines"))
    assert len({r["id"] for r in rows}) == len(rows), "two definitions share one identity"

    mains = sorted(r["lang"] for r in rows if r["qualname"] == "probe.main")
    assert mains == ["kotlin", "python", "typescript"], (
        "one module name, one routine name, three languages — all three must be here"
    )
    settings = list(store.query("SELECT id FROM structures WHERE name = 'Setting'"))
    assert len({r["id"] for r in settings}) == len(settings) == 3
    store.close()
