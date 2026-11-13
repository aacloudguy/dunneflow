"""Ways in: what each one *is*, and what a command tree does when you open it.

Tom, reading Lictores' cover: *"they don't make sense in the way that code does… Are these
packages, modules, or applications? What is `lictores`, `lictores-mcp`, `run`?"*

They are none of those three as a class. A way in is **how the outside world starts this
program** — a name you can type, a request that arrives, a module you can run — and the
fourteen on that cover are four *declared* executables read out of packaging, one HTTP route,
and nine *guesses* from a name or a `__main__` guard. The cover drew all fourteen as a name,
a kind tag and a bar, and threw the evidence away before the wire.

Two properties matter here.

**Declared and guessed must be separable by a query, not only by eye** — a row that cannot
say which it is is the reason five rows called `main` were unreadable.

**A tree is not one of the things it holds** (rule 74). `lictores` names `lictores.cli:app`,
which is a Typer object with no definition site, and expands to 107 commands across 44 files.
Clicking it selected all 107 and landed on whichever a query returned first. Which of the two
a way in is arrives as a declared field, because "this is a tree" and "this happens to start
several routines" look identical on the wire (rule 30).
"""

from __future__ import annotations

import pytest

from dunneflow.resolve.calls import resolve_calls
from dunneflow.resolve.cli import resolve_cli
from dunneflow.store import Store
from dunneflow.walk import analyze_tree
from dunneflow.web import waysin

APP = '''
"""A program with a real command tree and a guessed way in."""
import typer

app = typer.Typer()
tools_app = typer.Typer()
app.add_typer(tools_app, name="tools")


@app.command()
def build(target: str) -> int:
    return len(target)


@tools_app.command()
def clean() -> int:
    return 0


@tools_app.command()
def verify() -> int:
    return 1


def run() -> int:
    """A conventional name at module level. Nothing declares this a way in."""
    return build("x")
'''

PYPROJECT = """
[project]
name = "demo"
version = "0.1.0"
[project.scripts]
demo = "demo.main:app"
"""


@pytest.fixture(scope="module")
def tree(tmp_path_factory):
    root = tmp_path_factory.mktemp("waysin")
    (root / "demo").mkdir()
    (root / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (root / "demo" / "main.py").write_text(APP, encoding="utf-8")
    (root / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")

    db = tmp_path_factory.mktemp("waysingraph") / "graph.db"
    store = Store(db)
    analyze_tree(root, store)
    from dunneflow.resolve.entrypoints import entrypoints_from_packaging
    entrypoints_from_packaging(root, store)
    resolve_calls(store)
    resolve_cli(store)
    store.optimize()
    yield store
    store.close()


def _by_name(rows: list[dict], name: str) -> dict:
    got = [r for r in rows if r["name"] == name]
    assert got, f"no way in called {name!r}; got {[r['name'] for r in rows]}"
    return got[0]


# -- what a way in is --------------------------------------------------------- #


def test_every_way_in_says_whether_it_was_declared_or_guessed(tree: Store) -> None:
    """The word is the row's whole answer to "what, exactly?"."""
    rows = waysin.listing(tree)
    assert rows, "no ways in at all"
    for r in rows:
        assert isinstance(r["declared"], bool)
        assert r["evidence"], f"{r['name']} carries no evidence for being a way in"


def test_a_console_script_is_declared_and_a_conventional_name_is_not(tree: Store) -> None:
    """`demo` is read out of packaging; `run` is recognised by its name and nothing more."""
    rows = waysin.listing(tree)
    assert _by_name(rows, "demo")["declared"] is True
    assert "[project.scripts]" in _by_name(rows, "demo")["evidence"]
    guessed = _by_name(rows, "run")
    assert guessed["declared"] is False
    assert "conventional name" in guessed["evidence"]


def test_the_evidence_is_carried_verbatim_and_never_parsed(tree: Store) -> None:
    """It is this tool's own sentence, and it *is* the answer (rule 30).

    Tidying `pyproject.toml [project.scripts] demo = demo.main:app` into fields would promote
    a sentence written to be read into a contract, for a column nobody asked for.
    """
    row = _by_name(waysin.listing(tree), "demo")
    assert row["evidence"] == "pyproject.toml [project.scripts] demo = demo.main:app"


# -- a tree is not one of the things it holds --------------------------------- #


def test_a_command_tree_says_so_rather_than_being_counted(tree: Store) -> None:
    """Rule 30: `app` is declared, never inferred from `len(nodes) > 1`."""
    rows = waysin.listing(tree)
    assert _by_name(rows, "demo")["app"] is True
    assert _by_name(rows, "run")["app"] is False


def test_a_single_routine_way_in_carries_its_definition_site(tree: Store) -> None:
    row = _by_name(waysin.listing(tree), "run")
    assert row["where"] and row["where"]["file"].endswith("main.py")
    assert row["where"]["line"] > 0


def test_an_application_object_has_no_definition_site_and_says_what_it_spans(
        tree: Store) -> None:
    """`demo` names a Typer object. It has no `def`, so no file may be invented (rule 1).

    What it has instead is a size: the routines it starts and the files they are in, which is
    what the row prints where a single-routine way in prints a path.
    """
    row = _by_name(waysin.listing(tree), "demo")
    assert row["starts"] >= 3, "the command tree did not expand"
    assert row["files"] >= 1


def test_opening_an_application_returns_its_tree(tree: Store) -> None:
    """The pane behind the click: the sub-applications, and the commands hung directly on it.

    This is what clicking `lictores` could not do. It selected 107 routines at once and the
    centre opened whichever the query returned first — `lictores.cli.examples.list_cmd` from
    one query and `lictores/cli/_root.py` from another. Arbitrary, and unexplained.
    """
    d = waysin.describe(tree, "demo")
    assert d["found"] is True and d["app"] is True
    assert [c["name"] for c in d["commands"]] == ["build"]
    assert [g["name"] for g in d["groups"]] == ["tools"]
    assert d["groups"][0]["commands"] == 2, "a group must count what it holds"
    assert d["groups"][0]["file"], "a group with no file cannot be opened"


def test_every_command_carries_the_node_that_makes_it_a_selection(tree: Store) -> None:
    """A row that names a routine has to *be* the ordinary selection, or the pane is a list.

    Rule 30 from the other side: without the node id these rows differ only by the text they
    print, which is the defect the four subject-setting nav routes were fixed for.
    """
    d = waysin.describe(tree, "demo")
    for c in d["commands"]:
        assert c["node"], f"command {c['name']} carries no identity"
        assert c["file"], f"command {c['name']} cannot be opened"


def test_a_group_accounts_for_what_the_tree_starts(tree: Store) -> None:
    """Design rule 1: told "starts N" and shown one command, the reader is owed the rest.

    `unlisted` counts routines named by neither the entry, a listed command, nor a listed
    group. Counting a group by its *direct* children read `telemetry 0` on Lictores for a
    group holding nine commands one mount further down, so groups are counted with
    `app_command_routines` — the same function `ways_in` counts the whole tree with (rule 13).
    """
    d = waysin.describe(tree, "demo")
    assert d["unlisted"] == 0, "the tree does not account for what it starts"


def test_the_front_door_is_not_reported_as_a_limitation(tree: Store) -> None:
    """Where execution begins is its own answer, never a leftover.

    Keeping the executable out of its own command list (rule 74) left its entry routine
    named by nothing, so `unlisted` counted it — and the pane's sentence for `unlisted` calls
    it *a registration idiom DunneFlow followed far enough to count and not far enough to
    name*. That is a limitation confessed where there is none (rule 32), about the single
    most interesting routine in the tree. `lictores-mcp` has two.
    """
    d = waysin.describe(tree, "demo")
    assert "entry" in d
    named = {c["node"] for c in d["commands"]} | {c["node"] for c in d["entry"]}
    assert d["name"] not in [c["name"] for c in d["commands"]], \
        "the application lists itself as one of its own commands"
    for c in d["entry"]:
        assert c["node"] in named and c["file"]


def test_a_single_routine_way_in_lists_the_one_thing_it_runs(tree: Store) -> None:
    d = waysin.describe(tree, "run")
    assert d["app"] is False and d["groups"] == []
    assert len(d["commands"]) == 1 and d["commands"][0]["node"]


def test_a_name_that_matches_nothing_is_refused_rather_than_emptied(tree: Store) -> None:
    """An empty tree reads as an application with no commands — a different, false claim."""
    d = waysin.describe(tree, "no-such-way-in")
    assert d["found"] is False and d["reason"]
    assert "commands" not in d, "a refusal that carries an empty tree is not a refusal"


# -- chasing into a sub-application ------------------------------------------- #


def test_a_sub_application_can_be_opened(tree: Store) -> None:
    """A row that states a number nobody can open is a dead end in a pane built to be followed."""
    top = waysin.describe(tree, "demo")
    child = top["groups"][0]["child_id"]
    sub = waysin.describe(tree, "demo", child)
    assert sub["found"] is True
    assert sub["inside"] and sub["inside"]["name"] == "tools"
    assert sorted(c["name"] for c in sub["commands"]) == ["clean", "verify"]


def test_every_count_is_recomputed_for_the_sub_application(tree: Store) -> None:
    """Rule 24: a measurement must measure the thing it names.

    Carried down unchanged, `starts`, `files` and `reach` read 107, 44 and 1,381 on Lictores
    under a heading naming a group of 34 — three numbers each true of something the reader is
    not looking at.
    """
    top = waysin.describe(tree, "demo")
    child = top["groups"][0]["child_id"]
    sub = waysin.describe(tree, "demo", child)
    assert sub["starts"] < top["starts"], "the sub-application reports the whole tree's size"
    assert sub["starts"] == 2
    assert sub["unlisted"] == 0, "the remainder is measured against the wrong population"


def test_an_id_that_is_not_mounted_under_this_way_in_is_refused(tree: Store) -> None:
    """The id arrives from the page, and a parameter is not a permission.

    Taken as given it would render any application object in the store under any way in's
    heading — a pane correct in every respect except that it is about something else. Refused
    with a sentence rather than falling back to the root, because a fallback that yields a
    plausible value hides the failure it was written for (rule 49).
    """
    bad = waysin.describe(tree, "demo", "not-a-real-app-id")
    assert bad["found"] is False and "sub-application" in bad["reason"]
