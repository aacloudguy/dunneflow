"""A routine search says how it found what it found, or it is answering about something else.

**The defect, found 2026-09-09 while retaking the ground truth.**
`dunneflow touches output/lictores --routine lictores.cli.app` answered about
**`lictores.cli.apply.apply`** and reported a reach of 1. `app` is a Typer object rather
than a routine, so nothing could match it exactly; `find_routine` then fell back to
`qualname LIKE '%needle%'` and returned the first plausible thing it found -- silently.

That is rule 49 (a fallback that yields a plausible value has hidden the failure it was
written for) wrapped around rule 5 (never match on a bare common name), in the one command
a reader would use to check an executable's reach. The map itself was never wrong: the
four executables list 1,381 / 423 / 292 / 112 routines in `02-flows.md`.

The fallback is kept, because a half-remembered name is a real way to arrive. What it may
not do is wear an exact match's clothes. Three answers, never two: an exact match, nothing
named that at all, and *nothing exact but N whose qualname contains it* -- said out loud,
above the rows, with the count (rule 32).

The sample program is the defect's own shape by luck: `app = typer.Typer(name="sample")`
sits at module scope in `sample.py`, so `sample.app` is a name the program really uses and
really is not a routine.

Every assertion below was run against the unfixed `find_routine` first (rule 37): the
three that matter fail there, and they fail by *passing silently*, which is the defect.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.lookup import find_routine, search_said
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

TWO_RESOLVERS = '''
def resolve(name):
    """One of two routines sharing a name, which is the ordinary case."""
    return name
'''


def test_an_exact_qualname_answers_with_nothing_added(analyzed: Store) -> None:
    """The common case must not grow a caveat. A note on every answer is no note."""
    found = find_routine(analyzed, "sample.main")

    assert found.exact, "a qualname the program declares is an exact match"
    assert [m["qualname"] for m in found.matches] == ["sample.main"]
    assert search_said("sample.main", found, len(found.matches)) == [], (
        "an exact, unbounded answer says nothing about how it was found"
    )


def test_a_bare_name_is_still_an_exact_match(analyzed: Store) -> None:
    """`name = ?` is deliberate and stays. `main` is how a reader asks about `main`."""
    found = find_routine(analyzed, "main")

    assert found.exact
    assert [m["qualname"] for m in found.matches] == ["sample.main"]


def test_a_name_that_is_not_a_routine_names_the_module_instead(analyzed: Store) -> None:
    """The defect, and its true answer.

    `sample.app` is a Typer object at module scope. The old code answered about
    `sample.save_widget` or whatever sorted first; there is nothing to answer with here,
    and the honest reply is the one fact the map does hold -- that `sample` is a module it
    read, and nothing in it is named `app`.
    """
    found = find_routine(analyzed, "sample.app")

    assert not found.exact, "nothing is named this, and the search must say so"
    assert found.matches == [], "and nothing in this program's names even contains it"
    assert found.module == "sample"
    assert found.module_file == "sample.py"
    assert found.module_routines > 0, (
        "the count is the next question and this module answers it"
    )

    said = "\n".join(search_said("sample.app", found, 0))
    assert "no routine is named 'sample.app'" in said
    assert "sample is a module here" in said
    assert "sample.py" in said, "and it names the file, so the reader can go and look"
    assert "nothing in it is named 'app'" in said


def test_a_module_that_declares_no_routines_says_that_rather_than_a_count(
        tmp_path: Path) -> None:
    """`lictores/cli/__init__.py` is the real one: a package that builds a Typer app.

    **This is why the module test asks `files` and not `routines`.** A package module
    declares nothing of its own, so `routines.module` reports it as unknown -- which would
    have said "not a module here" about a file the analysis had read.
    """
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("app = object()\n", encoding="utf-8")
    (tmp_path / "pkg" / "work.py").write_text(TWO_RESOLVERS, encoding="utf-8")

    store = Store(tmp_path / "graph.db")
    analyze_tree(tmp_path, store)

    found = find_routine(store, "pkg.app")
    assert found.module == "pkg", "read from `files`, which recorded the __init__"
    assert found.module_routines == 0
    said = "\n".join(search_said("pkg.app", found, 0))
    assert "declares no routines at all" in said, (
        "'declares 0 routines' would be arithmetic; this is the reason nothing matched"
    )
    store.close()


def test_a_name_search_says_it_is_a_name_search(analyzed: Store) -> None:
    """The fallback kept, and labelled. Two routines' names contain `widget`."""
    found = find_routine(analyzed, "widget")

    assert not found.exact
    assert found.total == 2, "save_widget and read_widgets"
    assert {m["name"] for m in found.matches} == {"save_widget", "read_widgets"}

    said = "\n".join(search_said("widget", found, len(found.matches)))
    assert "no routine is named 'widget'" in said
    assert "2 routine names contain it" in said
    assert "a name search, not the routine you asked for" in said
    assert "showing" not in said, "nothing was held back, so nothing is claimed to be"


def test_a_bounded_name_search_says_how_many_it_held_back(analyzed: Store) -> None:
    """`--limit` deciding the answer in silence is the same defect one level down."""
    found = find_routine(analyzed, "widget")

    said = "\n".join(search_said("widget", found, 1))
    assert "2 routine names contain it, showing 1" in said


def test_a_bounded_exact_answer_says_how_many_share_the_name(tmp_path: Path) -> None:
    """Eight routines are named `resolve` on Comitia, and `--limit 2` showed two.

    An exact match needs no caveat about *how* it was found; it does need one about how
    much of it is on screen (rule 32).
    """
    for name in ("one", "two", "three"):
        (tmp_path / f"{name}.py").write_text(TWO_RESOLVERS, encoding="utf-8")

    store = Store(tmp_path / "graph.db")
    analyze_tree(tmp_path, store)

    found = find_routine(store, "resolve")
    assert found.exact
    assert found.total == 3, "counted, never `len(rows)` -- the LIMIT decided that"

    assert search_said("resolve", found, 3) == [], "all three shown, nothing to say"
    assert search_said("resolve", found, 2) == [
        "3 routines are named 'resolve'; showing 2."
    ]
    store.close()


def test_a_needle_matching_nothing_at_all_is_unchanged(analyzed: Store) -> None:
    """Three answers, never two -- and this is the third, which was always right."""
    found = find_routine(analyzed, "zzzznope")

    assert not found.exact
    assert found.matches == []
    assert found.module == "", "nothing here is a module either"
