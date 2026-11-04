"""A fragment (`.inl`, `.ipp`) is read through the file that includes it (chunk 5b, slice G).

Unreal keeps the bodies of `UKismetMathLibrary`'s inline functions in
`KismetMathLibrary.inl`, which `KismetMathLibrary.h` includes at its end. Read alone the
fragment has no `UKismetMathLibrary` in front of it: clang cannot name a single routine in
it, and 528 of Runtime's Blueprint ways in had no body to bind to. So a fragment is parsed
as part of a file that includes it, and only what is expanded in the fragment is kept --
the routines keep the fragment's own path, and their names come from the includer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.schema import FileFacts, SuppliedEdge
from tests.test_cpp_reader import _WHY, PLUGIN, needs_clang

pytestmark = needs_clang

# The shape of KismetMathLibrary: a class in the header, its bodies in the fragment, and
# the fragment included at the end.
CLASS_H = """\
#pragma once
namespace ue {
int helper(int x);
class Maths {
public:
    static int add(int a, int b);
    int twice(int a) const;
};
}
#include "maths.inl"
"""
CLASS_INL = """\
namespace ue {
inline int Maths::add(int a, int b) { return helper(a) + b; }
inline int Maths::twice(int a) const { return add(a, a); }
}
"""


def _read(root: Path, files: list[Path], *, edges: bool = False
          ) -> tuple[dict[str, FileFacts], list[str], list[SuppliedEdge]]:
    if _WHY:
        pytest.skip(_WHY)
    assert PLUGIN is not None
    PLUGIN.open(root, files)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(files, root)}
        got = list(PLUGIN.edges()) if edges else []
        return facts, list(PLUGIN.edge_notes) + list(PLUGIN.edges_said), got
    finally:
        PLUGIN.close()


def _tree(root: Path, files: dict[str, str]) -> list[Path]:
    """Exactly these files. No `.cpp` is added: a fragment's suffix is what says the tree is
    C++, and a `.cpp` beside every case would hide that it does not."""
    out = []
    for name, body in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        out.append(p)
    return sorted(out)


def _names(ff: FileFacts) -> set[str]:
    return {r.qualname for r in ff.routines}


def test_a_fragments_bodies_are_named_by_the_class_its_includer_declares(tmp_path: Path) -> None:
    files = _tree(tmp_path, {"maths.h": CLASS_H, "maths.inl": CLASS_INL})
    facts, notes, got = _read(tmp_path, files, edges=True)

    frag = facts["maths.inl"]
    assert _names(frag) == {"ue.Maths.add", "ue.Maths.twice"}, frag.routines
    assert all(r.file == "maths.inl" for r in frag.routines), "a routine moved to its includer"
    assert not frag.errors
    assert _names(facts["maths.h"]) == set(), "the includer took the fragment's routines"
    # And its calls resolve: `twice` calls `add`, which only the header declares.
    twice = next(r for r in frag.routines if r.name == "twice")
    add = next(r for r in frag.routines if r.name == "add")
    site = {c.site_id for c in frag.calls if c.caller_id == twice.id}
    target = ("maths.inl", add.line_start, "add")
    assert any(e.site_id in site and (e.file, e.line, e.name) == target for e in got), got
    assert any("1 fragments (.inl, .ipp) were read through" in n for n in notes), notes


def test_alone_it_was_unnamed_which_is_the_defect(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The baseline the first test is against: the same fragment with no includer read."""
    files = _tree(tmp_path, {"maths.inl": CLASS_INL})
    facts, notes, _ = _read(tmp_path, files, edges=True)
    assert _names(facts["maths.inl"]) != {"ue.Maths.add", "ue.Maths.twice"}
    assert any("1 were read alone" in n for n in notes) and "  maths.inl" in notes, notes


def test_the_includer_s_namespace_around_the_include_is_the_fragment_s(tmp_path: Path) -> None:
    files = _tree(tmp_path, {
        "wrap.h": 'namespace outer {\n#include "wrap.inl"\n}\n',
        "wrap.inl": "inline int inside() { return 1; }\n",
    })
    facts, _, _ = _read(tmp_path, files)
    assert _names(facts["wrap.inl"]) == {"outer.inside"}


TWO_INCLUDERS = {
    # Path order would choose `a_other.h`; the header of the fragment's own stem wins.
    "a_other.h": 'namespace two {\n#include "shared.inl"\n}\n',
    "shared.h": 'namespace one {\n#include "shared.inl"\n}\n',
    "shared.inl": "inline int g() { return 1; }\n",
}


@pytest.mark.parametrize("reverse", [False, True], ids=["sorted", "reversed"])
def test_two_includers_the_canonical_one_is_chosen_in_any_order(
        tmp_path: Path, reverse: bool) -> None:
    files = _tree(tmp_path, TWO_INCLUDERS)
    facts, _, _ = _read(tmp_path, files[::-1] if reverse else files)
    assert _names(facts["shared.inl"]) == {"one.g"}


def test_without_a_same_stem_header_path_order_decides(tmp_path: Path) -> None:
    files = _tree(tmp_path, {
        "b.h": 'namespace bee {\n#include "frag.inl"\n}\n',
        "a.h": 'namespace ay {\n#include "frag.inl"\n}\n',
        "frag.inl": "inline int g() { return 1; }\n",
    })
    facts, _, _ = _read(tmp_path, files[::-1])
    assert _names(facts["frag.inl"]) == {"ay.g"}


def test_an_includer_that_guards_it_out_is_passed_over(tmp_path: Path) -> None:
    """`clang_getFile` answers for any file on disk; the inclusion is what has to be asked."""
    files = _tree(tmp_path, {
        "guarded.h": 'namespace off {\n#if 0\n#include "guarded.inl"\n#endif\n}\n',
        "z_live.h": 'namespace on {\n#include "guarded.inl"\n}\n',
        "guarded.inl": "inline int g() { return 1; }\n",
    })
    facts, _, _ = _read(tmp_path, files)
    assert _names(facts["guarded.inl"]) == {"on.g"}


def test_an_orphan_fragment_is_read_alone_and_named_in_the_notes(tmp_path: Path) -> None:
    files = _tree(tmp_path, {"lonely.inl": "inline int g() { return 1; }\n"})
    facts, notes, _ = _read(tmp_path, files, edges=True)
    assert _names(facts["lonely.inl"]) == {"g"}
    assert "  lonely.inl" in notes, notes


def test_a_header_only_cpp_tree_is_read_as_cpp(tmp_path: Path) -> None:
    """Unreal's `Engine/Classes/Kismet` is 25 headers and no source: read as C, all 25 lost
    `<type_traits>` and the map had no routine at all. A header only C++ writes says the
    tree is C++, as a `.cpp` does."""
    files = _tree(tmp_path, {"lib.hpp": "namespace lib {\ninline int one() { return 1; }\n}\n",
                             "plain.h": "namespace lib {\ninline int two() { return 2; }\n}\n"})
    facts, _, _ = _read(tmp_path, files)
    assert _names(facts["lib.hpp"]) == {"lib.one"}
    assert _names(facts["plain.h"]) == {"lib.two"}, "a .h beside a .hpp was read as C"
