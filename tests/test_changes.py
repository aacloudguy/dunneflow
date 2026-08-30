"""What differs between two versions of a program.

Every test here is a way the diff can be wrong while looking right. The expensive one
is the last: a comparison key containing a line number turns one inserted import into
thousands of false differences, and the view still renders perfectly.

**Every call names its ends.** `build(base=..., compared=...)` is written with keywords
throughout, because the two are not interchangeable and swapping them silently inverts
every band -- which is the exact defect this vocabulary was introduced to make
impossible. `base` is the version under the reader's eye; `compared` is the other one.
Neither is claimed to be older, so the bands say **where** a thing is and never what
befell it.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.extractors.python.extract import extract_file
from dunneflow.store import Store
from dunneflow.web import changes


def _graph(tmp_path: Path, name: str, source: str) -> Path:
    """A one-file program, extracted and stored, as a graph on disk."""
    tree = tmp_path / name
    tree.mkdir()
    src = tree / "m.py"
    src.write_text(source)
    db = tmp_path / f"{name}.db"
    store = Store(db)
    store.write_file_facts(extract_file(src, tree))
    store.conn.commit()
    store.close()
    return db


BEFORE = '''\
import os

def alpha():
    return os.getpid()

def beta():
    alpha()
'''


def test_a_routine_only_the_base_has_is_reported_against_the_base(tmp_path):
    grown = BEFORE + "\ndef gamma():\n    return 1\n"
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert [r["name"] for r in d["only_in_base"]] == ["gamma"]
    assert d["only_in_compared"] == []
    assert d["counts"]["behaves"] == 0, d["behaves"]
    assert d["identical"] is False


def test_a_routine_only_the_compared_has_is_reported_against_the_compared(tmp_path):
    shrunk = BEFORE.replace("def beta():\n    alpha()\n", "")
    d = changes.build(base=_graph(tmp_path, "b", shrunk),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert [r["name"] for r in d["only_in_compared"]] == ["beta"]
    assert d["only_in_base"] == []


def test_an_edit_that_changes_nothing_it_does_is_not_a_behaviour_change(tmp_path):
    """The largest band in ordinary work, and the one this tool exists not to report.

    `beta` gains a local and some arithmetic. Its body hash moves; what it *does* --
    what it calls, touches, takes and returns -- does not.
    """
    edited = BEFORE.replace("def beta():\n    alpha()\n",
                            "def beta():\n    n = 2 + 2\n    alpha()\n")
    d = changes.build(base=_graph(tmp_path, "b", edited),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert [r["name"] for r in d["edited_only"]] == ["beta"], d["edited_only"]
    assert d["counts"]["behaves"] == 0, d["behaves"]


def test_a_new_call_is_a_behaviour_change(tmp_path):
    calling_more = BEFORE.replace("def beta():\n    alpha()\n",
                                  "def beta():\n    alpha()\n    os.getcwd()\n")
    d = changes.build(base=_graph(tmp_path, "b", calling_more),
                      compared=_graph(tmp_path, "a", BEFORE))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "beta" in names, d["behaves"]
    assert "calls" in names["beta"]


def test_a_changed_signature_is_a_behaviour_change(tmp_path):
    signed = BEFORE.replace("def alpha():", "def alpha(flag: bool = False):")
    d = changes.build(base=_graph(tmp_path, "b", signed),
                      compared=_graph(tmp_path, "a", BEFORE))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "params" in names.get("alpha", []), d["behaves"]


def test_a_routine_that_arrived_is_not_also_counted_as_behaving_differently(tmp_path):
    """One act, one number. Rule 40 in a diff.

    A routine only one side has has all its calls on that side too, so a diff that does
    not restrict the fact comparison to routines present in *both* reports it twice --
    once for its presence and once as changed -- and the two counts never add up.
    """
    grown = BEFORE + "\ndef gamma():\n    alpha()\n"
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert [r["name"] for r in d["only_in_base"]] == ["gamma"]
    assert all(r["name"] != "gamma" for r in d["behaves"]), d["behaves"]


def test_inserting_a_line_above_everything_changes_nothing(tmp_path):
    """The defect that would render this whole view as noise.

    `calls`, `boundaries` and `sql_ops` all carry a line. Put one in the comparison key
    and a single added import moves every fact in the file, so an ordinary commit reads
    as the program having been rewritten. This is `make_id`'s own argument one level
    down, and the view looks completely normal while it happens.
    """
    shifted = "import sys\n" + BEFORE
    d = changes.build(base=_graph(tmp_path, "b", shifted),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert d["counts"]["behaves"] == 0, d["behaves"]
    assert d["only_in_base"] == [] and d["only_in_compared"] == [], (
        d["only_in_base"], d["only_in_compared"])


def test_the_module_scope_arrives_when_it_first_owns_something(tmp_path):
    """Stated because it is surprising, not because it is wrong.

    `<module>` is created lazily -- only when there is a module-level fact for it to own
    (rule 18/19) -- so a file whose first module-level *comment* is added gains a
    routine. That is true: the module scope now owns something it did not. It is also
    the one addition a reader will not recognise as one.

    **Kept exactly as it is, on Tom's decision** (2026-08-29): it is honest and it is
    rare. If it proves to be noise on a larger commit it gets fixed then and on
    evidence, which is why this test states the behaviour rather than asserting a
    preference about it.
    """
    commented = "# the first module-level comment\n" + BEFORE
    d = changes.build(base=_graph(tmp_path, "b", commented),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert [r["qualname"] for r in d["only_in_base"]] == ["m.<module>"], d["only_in_base"]
    assert all(r["name"] != "<module>" for r in d["behaves"])


def test_every_row_carries_the_id_the_dashboard_selects_by(tmp_path):
    """Rule 30: a worklist whose rows carry a label and no subject is forty dead controls."""
    grown = BEFORE + "\ndef gamma():\n    alpha()\n"
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", BEFORE))
    for band in ("only_in_base", "only_in_compared", "behaves", "edited_only"):
        for row in d[band]:
            assert row.get("id"), (band, row)


# --------------------------------------------------------------------------- #
# The losing direction.
#
# Every test above adds something, and all nine passed over a query that computed
# `B EXCEPT A` alone -- facts gained, never facts lost. On the corpus it was first run
# against it gave the right answer, because that change deleted almost nothing. These
# are the tests that had to exist for the defect to be visible at all.
# --------------------------------------------------------------------------- #


def test_a_call_that_stopped_happening_is_a_behaviour_change(tmp_path):
    hollowed = BEFORE.replace("def beta():\n    alpha()\n", "def beta():\n    pass\n")
    d = changes.build(base=_graph(tmp_path, "b", hollowed),
                      compared=_graph(tmp_path, "a", BEFORE))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "calls" in names.get("beta", []), d["behaves"]


def test_a_parameter_that_went_away_is_a_behaviour_change(tmp_path):
    signed = BEFORE.replace("def alpha():", "def alpha(flag: bool = False):")
    d = changes.build(base=_graph(tmp_path, "b", BEFORE),
                      compared=_graph(tmp_path, "a", signed))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "params" in names.get("alpha", []), d["behaves"]


def test_a_boundary_that_is_no_longer_touched_is_a_behaviour_change(tmp_path):
    touching = BEFORE.replace("def beta():\n    alpha()\n",
                              "def beta():\n    alpha()\n    open('/tmp/x').read()\n")
    d = changes.build(base=_graph(tmp_path, "b", BEFORE),
                      compared=_graph(tmp_path, "a", touching))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "beta" in names, d["behaves"]


def test_a_diff_can_ride_a_connection_that_already_holds_one_end(tmp_path):
    """The 36x, and the reason it is not a micro-optimisation.

    A second read-only handle to a database this process already has open in WAL mode
    cannot join the shared-memory WAL index — it has no write access to the `-shm` — and
    re-derives it on every query. One `calls` comparison on Mensores measured 8,855 ms
    with the dashboard holding the graph open and 137 ms attached onto the connection
    that already had it. Same query, same files, same page cache.

    The trap is that the slow path is only slow *while the tool is doing what it exists
    to do*. Measured standalone it is 242 ms, which is how it would have been recorded
    as fast and shipped — every measurement in this module before that one was taken
    with the server stopped.
    """
    import sqlite3

    compared = _graph(tmp_path, "a", BEFORE)
    base = _graph(tmp_path, "b", BEFORE + "\ndef gamma():\n    alpha()\n")

    standalone = changes.build(base=base, compared=compared)

    # **The connection is open on the base**, and that is the whole shape of the
    # optimisation: the base is the version the dashboard is serving, so it is the graph
    # this process already holds. A connection on the compared end is no use — it is the
    # one nothing has opened.
    #
    # Exactly as `Store` opens it: **no** `uri=True`, because that is the connection
    # this rides in the dashboard. With URI handling on, a `file:...?mode=ro` attach
    # quietly works here and fails in the server, where the URI is taken as a literal
    # filename — the guard would then pass against the defect it exists for (rule 37).
    conn = sqlite3.connect(base)
    conn.row_factory = sqlite3.Row
    try:
        ridden = changes.build(base=base, compared=compared, serving=conn)
        # Identical answers, or the fast path is a different measurement wearing the
        # same label (rule 24).
        assert ridden["counts"] == standalone["counts"]
        assert ([r["id"] for r in ridden["only_in_base"]]
                == [r["id"] for r in standalone["only_in_base"]])
        # And the connection is handed back as it was found: a left-behind alias makes
        # the *next* comparison fail, which is the kind of breakage that only shows up
        # on the second click.
        again = changes.build(base=base, compared=compared, serving=conn)
        assert again["counts"] == standalone["counts"]
    finally:
        conn.close()


def test_the_diff_contains_no_write_statement():
    """Rule 25's guarantee, kept rule 25's way.

    The pair is computed on the connection the dashboard already holds open, which
    cannot be read-only without spreading a 36x slowdown to every other query on it. So
    the read-only promise is not enforced by a flag but asserted here — because what it
    guards against is a future edit, not a present bug, and one of the two graphs is a
    snapshot somebody sealed precisely so it would stop changing.

    Over the module's **string literals**, via `ast`, with docstrings excluded. A grep
    would fire on the prose above the moment someone wrote `DROP` into a comment
    explaining why there is none, and a check that cries wolf is a check nobody reads
    (rule 43).
    """
    import ast

    from dunneflow.web import changes as mod

    tree = ast.parse(Path(mod.__file__).read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))

    WRITES = ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
              "REPLACE", "VACUUM", "REINDEX")
    seen = 0
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstrings:
            continue
        seen += 1
        upper = node.value.upper()
        for verb in WRITES:
            assert verb not in upper, f"{verb} in a string literal: {node.value[:70]!r}"
    # The check must have had something to look at, or it passes by finding nothing.
    assert seen > 5, f"only {seen} literals examined — the instrument is not looking"


# --------------------------------------------------------------------------- #
# Two versions, and no claim about which is older.
# --------------------------------------------------------------------------- #


def test_two_identical_versions_report_no_differences_rather_than_nothing(tmp_path):
    """"Identical" is an answer, and four empty bands are not the same claim.

    A reader who compares a tree with a copy of it has asked a real question and is
    entitled to a real answer. Empty bands read as a comparison that *failed* -- design
    rule 1 says a view must say what it is not showing, and "nothing here" and "nothing
    differs" are opposite claims (rule 35, one layer up).
    """
    d = changes.build(base=_graph(tmp_path, "b", BEFORE),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert d["identical"] is True
    assert d["only_in_base"] == [] and d["only_in_compared"] == []
    assert d["counts"]["behaves"] == 0 and d["counts"]["edited_only"] == 0


def test_a_single_difference_anywhere_is_enough_to_not_be_identical(tmp_path):
    """The half that makes the flag worth having.

    `identical` must fall to *any* band, including the presence tables nothing else
    counts. A constant added at module scope is the cheapest thing that is invisible to
    the four routine bands on a graph where the module scope already exists.
    """
    grown = BEFORE + "\nLIMIT = 5\n"
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", BEFORE))
    assert d["identical"] is False
    assert d["presence"]["constants"]["only_in_base"] == ["m.LIMIT"], d["presence"]


def test_no_band_or_count_is_named_for_a_point_in_time(tmp_path):
    """The vocabulary guard, and it is the point of the whole change.

    The store records when *we* read the bytes and nothing else, so a key called
    `before`, `after`, `earlier`, `later`, `added` or `removed` is this module claiming
    a chronology it cannot see. Every one of them was here, and the labels were correct
    only because the default pairing happened to make the base the newer capture.

    Asserted over the **keys the answer actually carries**, not over the source, because
    what a reader can be misled by is what reaches them (rule 13).
    """
    grown = BEFORE + "\ndef gamma():\n    return 1\n"
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", BEFORE))

    forbidden = {"before", "after", "earlier", "later", "added", "removed"}
    keys = set(d) | set(d["counts"])
    for table in d["presence"].values():
        keys |= set(table)
    # Over the **parts** of each name, not the whole name. `routines_after` is the same
    # claim as `after` and an exact-match test sails straight past it -- which is not a
    # hypothetical: it was the one mutation that survived the first version of this
    # guard, and it survived because the guard was weak rather than because the
    # mutation was (rule 59's companion).
    parts = {part for key in keys for part in key.split("_")}
    assert not (parts & forbidden), sorted(parts & forbidden)
    # And the ends it does name are the two it is allowed to name.
    assert {"only_in_base", "only_in_compared"} <= keys
