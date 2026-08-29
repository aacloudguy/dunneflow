"""What moved between two points in time.

Every test here is a way the diff can be wrong while looking right. The expensive one
is the last: a comparison key containing a line number turns one inserted import into
thousands of false differences, and the view still renders perfectly.
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


def test_a_new_routine_is_added_and_nothing_else_moves(tmp_path):
    after = BEFORE + "\ndef gamma():\n    return 1\n"
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    assert [r["name"] for r in d["added"]] == ["gamma"]
    assert d["removed"] == []
    assert d["counts"]["behaves"] == 0, d["behaves"]


def test_a_deleted_routine_is_removed(tmp_path):
    after = BEFORE.replace("def beta():\n    alpha()\n", "")
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    assert [r["name"] for r in d["removed"]] == ["beta"]
    assert d["added"] == []


def test_an_edit_that_changes_nothing_it_does_is_not_a_behaviour_change(tmp_path):
    """The largest band in ordinary work, and the one this tool exists not to report.

    `beta` gains a local and some arithmetic. Its body hash moves; what it *does* --
    what it calls, touches, takes and returns -- does not.
    """
    after = BEFORE.replace("def beta():\n    alpha()\n",
                           "def beta():\n    n = 2 + 2\n    alpha()\n")
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    assert [r["name"] for r in d["edited_only"]] == ["beta"], d["edited_only"]
    assert d["counts"]["behaves"] == 0, d["behaves"]


def test_a_new_call_is_a_behaviour_change(tmp_path):
    after = BEFORE.replace("def beta():\n    alpha()\n",
                           "def beta():\n    alpha()\n    os.getcwd()\n")
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "beta" in names, d["behaves"]
    assert "calls" in names["beta"]


def test_a_changed_signature_is_a_behaviour_change(tmp_path):
    after = BEFORE.replace("def alpha():", "def alpha(flag: bool = False):")
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "params" in names.get("alpha", []), d["behaves"]


def test_a_routine_that_arrived_is_not_also_counted_as_behaving_differently(tmp_path):
    """One act, one number. Rule 40 in a diff.

    A new routine's calls are all "new", so a diff that does not restrict the fact
    comparison to routines present in *both* reports every addition twice -- once as
    added and once as changed -- and the two counts never add up to anything.
    """
    after = BEFORE + "\ndef gamma():\n    alpha()\n"
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    assert [r["name"] for r in d["added"]] == ["gamma"]
    assert all(r["name"] != "gamma" for r in d["behaves"]), d["behaves"]


def test_inserting_a_line_above_everything_changes_nothing(tmp_path):
    """The defect that would render this whole view as noise.

    `calls`, `boundaries` and `sql_ops` all carry a line. Put one in the comparison key
    and a single added import moves every fact in the file, so an ordinary commit reads
    as the program having been rewritten. This is `make_id`'s own argument one level
    down, and the view looks completely normal while it happens.
    """
    after = "import sys\n" + BEFORE
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    assert d["counts"]["behaves"] == 0, d["behaves"]
    assert d["added"] == [] and d["removed"] == [], (d["added"], d["removed"])


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
    after = "# the first module-level comment\n" + BEFORE
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    assert [r["qualname"] for r in d["added"]] == ["m.<module>"], d["added"]
    assert all(r["name"] != "<module>" for r in d["behaves"])


def test_every_row_carries_the_id_the_dashboard_selects_by(tmp_path):
    """Rule 30: a worklist whose rows carry a label and no subject is forty dead controls."""
    after = BEFORE + "\ndef gamma():\n    alpha()\n"
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    for band in ("added", "removed", "behaves", "edited_only"):
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
    after = BEFORE.replace("def beta():\n    alpha()\n", "def beta():\n    pass\n")
    d = changes.build(_graph(tmp_path, "a", BEFORE), _graph(tmp_path, "b", after))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "calls" in names.get("beta", []), d["behaves"]


def test_a_parameter_that_went_away_is_a_behaviour_change(tmp_path):
    before = BEFORE.replace("def alpha():", "def alpha(flag: bool = False):")
    d = changes.build(_graph(tmp_path, "a", before), _graph(tmp_path, "b", BEFORE))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "params" in names.get("alpha", []), d["behaves"]


def test_a_boundary_that_is_no_longer_touched_is_a_behaviour_change(tmp_path):
    before = BEFORE.replace("def beta():\n    alpha()\n",
                            "def beta():\n    alpha()\n    open('/tmp/x').read()\n")
    d = changes.build(_graph(tmp_path, "a", before), _graph(tmp_path, "b", BEFORE))
    names = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "beta" in names, d["behaves"]
