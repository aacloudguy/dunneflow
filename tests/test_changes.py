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
    assert ([r["label"] for r in d["presence"]["constants"]["only_in_base"]]
            == ["m.LIMIT"]), d["presence"]
    # And the row can be opened. A presence row that names a constant and cannot reach it
    # is design rule 16 with a label on it, which is what every one of these used to be.
    assert (d["presence"]["constants"]["only_in_base"][0]["id"]
            == "const:m.LIMIT"), d["presence"]


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


# ── what a caller passes, and what a constant holds ────────────────────────────────────
#
# Two gaps that were open long enough to be written down as open. `FACTS` compares `calls`
# without their arguments, and `constants` sat in `PRESENCE` compared by name — so
# `f(db_path=None)` becoming `f(policy_path=…)` and `EXPECTED_SCHEMA_VERSION` going from 27
# to 28 both read as no change at all.


ARG_BEFORE = '''\
def sink(a, b=None):
    return a

def caller():
    sink(1, b=None)
'''


def test_an_argument_that_changed_is_a_behaviour_change(tmp_path):
    """The gap itself. The call resolves to the same routine at the same site; only what it
    hands over is different, and what moves is the whole subject of this tool."""
    after = ARG_BEFORE.replace("sink(1, b=None)", "sink(1, b=2)")
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", ARG_BEFORE))
    rows = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "caller" in rows, f"an argument that changed is not a behaviour change: {rows}"
    assert "call_args" in rows["caller"], rows["caller"]
    # And it is reported *once*. `calls` did not move -- same callee, same expression -- so a
    # second kind here would be one difference counted twice (rule 40).
    assert rows["caller"] == ["call_args"], rows["caller"]


def test_a_keyword_that_changed_is_a_behaviour_change(tmp_path):
    """`db_path=None` -> `policy_path=…` on Mensores' pair: the name it was passed under is
    as much a part of what moves as the value."""
    after = ARG_BEFORE.replace("def sink(a, b=None)", "def sink(a, c=None)") \
                      .replace("sink(1, b=None)", "sink(1, c=None)")
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", ARG_BEFORE))
    assert "call_args" in {r["name"]: r["moved"] for r in d["behaves"]}["caller"]


def test_an_argument_rewrapped_and_not_changed_is_not_a_behaviour_change(tmp_path):
    """**The reason there is a canonicalising pass at all**, and it is a real finding.

    Mensores' `claim_break_glass_cmd` passes a `typer.echo` message that was re-wrapped
    across two lines without one character of its content changing. Arguments are stored as
    written and never re-rendered (rules 8 and 75) — right for a reader who wants to find the
    string in the file, and wrong for a comparison, which asks whether these are the same
    expression.

    Without the second pass this routine lands in *behaves differently*, the band that
    promises what a routine **does** moved, sitting beside one that says *edited only, and
    nothing it does changed*. Rule 1: a false difference is worse than a missing one.
    """
    before = 'def sink(m):\n    return m\n\ndef caller():\n    sink("one two three")\n'
    after = ('def sink(m):\n    return m\n\ndef caller():\n'
             '    sink(\n        "one "\n        "two "\n        "three"\n    )\n')
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", before))
    moved = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "caller" not in moved, (
        f"a re-wrapped literal is reported as behaving differently: {moved}"
    )
    # It is not silently dropped either -- the body did change, so it belongs to the band
    # that exists to say exactly that.
    assert "caller" in {r["name"] for r in d["edited_only"]}, d["edited_only"]


def test_a_splat_argument_is_compared_as_written(tmp_path):
    """`**kwargs` is a call-site form, not an expression, and does not parse alone.

    All 49 of Mensores' unparseable arguments are splats. They compare as written, which is
    correct rather than a fallback — and it has to go on working, because a canonicaliser
    that threw here would take the whole comparison with it.
    """
    before = 'def sink(**kw):\n    return kw\n\ndef caller(**kwargs):\n    sink(**kwargs)\n'
    after = before.replace("sink(**kwargs)", "sink(**dict(kwargs))")
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", before))
    assert "call_args" in {r["name"]: r["moved"] for r in d["behaves"]}["caller"]


def test_a_constant_whose_value_moved_is_reported(tmp_path):
    """`EXPECTED_SCHEMA_VERSION` 27 -> 28 read as no change for as long as constants were
    compared by name. A constant is a name *and* a value, and the value is what it says."""
    before = "EXPECTED_SCHEMA_VERSION = 27\nOTHER = 'x'\n"
    after = "EXPECTED_SCHEMA_VERSION = 28\nOTHER = 'x'\n"
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", before))
    c = d["presence"]["constants"]
    assert [r["label"].split(".")[-1] for r in c["moved"]] == ["EXPECTED_SCHEMA_VERSION"], c
    # **Both values ride with the row**, which is the whole claim of this band: the thing
    # is not constant any more, and a name alone cannot say so.
    assert [r["base"] for r in c["moved"]] == ["28"], c["moved"]
    assert [r["compared"] for r in c["moved"]] == ["27"], c["moved"]
    # And which of the three moved, because a row showing two identical values under a
    # heading that says they differ is rule 13 in a pane.
    assert [r["moved"] for r in c["moved"]] == [["value"]], c["moved"]
    # Present in both, so it is in neither presence band. A constant in one band and the
    # other would be one difference reported twice (rule 40).
    assert c["only_in_base"] == [] and c["only_in_compared"] == [], c
    assert d["identical"] is False


def test_a_constant_whose_type_or_finality_moved_has_also_moved(tmp_path):
    """Three things say what a named value *is*, and the value is only one of them.

    `X: int = 1` becoming `X: str = "1"` is a change to what the program says it holds, and
    a constant that stopped being `Final` is a constant something may now reassign. Both are
    what moves; neither shows up in the value alone.

    Written because a first version of this compared the value only, and the fixture that
    was supposed to guard the key could not see it: a mutation dropping `type` and
    `is_final` survived, and the mutation was fine — the guard was the weak one (rule 59).
    """
    for before, after, what in (
        ("from typing import Final\nX: int = 1\n",
         "from typing import Final\nX: str = 1\n", "type"),
        ("from typing import Final\nX: Final[int] = 1\n",
         "from typing import Final\nX: int = 1\n", "finality"),
    ):
        d = changes.build(base=_graph(tmp_path, f"b_{what}", after),
                          compared=_graph(tmp_path, f"a_{what}", before))
        rows = d["presence"]["constants"]["moved"]
        moved = [r["label"].split(".")[-1] for r in rows]
        assert moved == ["X"], f"a constant whose {what} moved is not reported: {moved}"
        # The row says *which* of the three moved, and it names the one this case
        # changed. Matched exactly rather than by substring: "fina" is inside "final"
        # and inside nothing else here, so a substring test passes on a row that names
        # only the value and would not notice (rule 59's companion).
        term = {"type": "type", "finality": "final"}[what]
        assert term in rows[0]["moved"], (what, rows[0]["moved"])


def test_a_constant_rewritten_and_not_changed_has_not_moved(tmp_path):
    """A re-spaced constant has not moved — and **the diff does nothing to earn this.**

    The property is the extractor's: `constants.value` reaches the store through `_literal`,
    which is `ast.unparse`, so both spellings are already the same string before anything
    compares them. An end-to-end guard rather than a guard on `_constants_moved`, and it is
    written that way on purpose — a canonical pass was added here, measured at 384 ms over
    374,529 characters a side, found unable to change any answer, and removed.

    Which is why this test's docstring says where the property lives. Without that, the next
    reader sees arguments canonicalised and constants not, assumes an oversight, and puts the
    dead pass back. The regression that would actually break this is in `extract.py` — if a
    constant were ever recorded by source slice, the way an argument deliberately is.
    """
    d = changes.build(base=_graph(tmp_path, "b", "OPS = {'a':1,  'b':2}\n"),
                      compared=_graph(tmp_path, "a", "OPS = {'a': 1, 'b': 2}\n"))
    assert d["presence"]["constants"]["moved"] == [], d["presence"]["constants"]


def test_only_constants_carry_a_moved_band_and_the_others_carry_it_empty(tmp_path):
    """A table, a way in and a file the program names are **names**: each either is there or
    is not, so "still here, saying something else" cannot be true of one.

    Empty rather than absent, so the renderer reads one shape and a missing key can never be
    mistaken for a band with nothing in it (rule 13).
    """
    d = changes.build(base=_graph(tmp_path, "b", "A = 1\n"),
                      compared=_graph(tmp_path, "a", "A = 2\n"))
    for table, v in d["presence"].items():
        assert "moved" in v, f"`{table}` has no `moved` key at all"
        if table != "constants":
            assert v["moved"] == [], f"`{table}` claims a value moved: {v['moved']}"


def test_no_comparison_key_here_carries_a_position(tmp_path):
    """The module's own rule, extended to the two new comparisons.

    An argument's `line` and a constant's `line` are both in the store and neither is asked
    about; nor is the file either sits in. And `site_id` is deliberately out of the argument
    key — it embeds an ordinal among identical expressions in a caller, so inserting a third
    `emit()` would renumber the ones after it and every argument of every renumbered site
    would read as changed. Not a line number, but a position all the same.
    """
    body = 'def s(x):\n    return x\n\ndef caller():\n    s(1)\n    s(2)\n'
    shoved = "import os\nimport sys\n\n" + body
    d = changes.build(base=_graph(tmp_path, "b", shoved),
                      compared=_graph(tmp_path, "a", body))
    moved = {r["name"]: r["moved"] for r in d["behaves"]}
    assert "call_args" not in moved.get("caller", []), (
        f"pushing everything down two lines moved an argument: {moved}"
    )
    assert d["presence"]["constants"]["moved"] == []

    # **The case that actually separates `site_id` in from `site_id` out**, and the first
    # version of this test could not see it: swapping two calls to the same name leaves every
    # argument exactly where it was and gives both sites a different ordinal. With `site_id`
    # in the key that is two changed sites and nothing changed; without it, nothing at all.
    #
    # Nothing here reports *order* — `calls` is a set, and so is this — so "the same calls
    # with the same arguments" is the whole of what the tool can see, and saying they moved
    # would be a difference it cannot defend.
    swapped = body.replace("    s(1)\n    s(2)\n", "    s(2)\n    s(1)\n")
    assert swapped != body, "the fixture did not actually swap anything"
    d2 = changes.build(base=_graph(tmp_path, "d", swapped),
                       compared=_graph(tmp_path, "c", body))
    moved2 = {r["name"]: r["moved"] for r in d2["behaves"]}
    assert "call_args" not in moved2.get("caller", []), (
        f"reordering two calls to one name moved their arguments: {moved2} -- the ordinal "
        "in `site_id` has reached the comparison key, and inserting a call to a name a "
        "routine already calls now rewrites every site after it"
    )

    # And an inserted call *is* reported, so the guard above is not passing by reporting
    # nothing at all.
    grown = body.replace("    s(1)\n", "    s(0)\n    s(1)\n")
    d3 = changes.build(base=_graph(tmp_path, "f", grown),
                       compared=_graph(tmp_path, "e", body))
    assert "call_args" in {r["name"]: r["moved"] for r in d3["behaves"]}.get("caller", []), (
        "a call passing a value nothing passed before is not reported"
    )


def test_the_diff_asks_for_a_canonical_form_and_never_makes_one():
    """`changes.py` knows that two writings can be the same expression, and nothing else.

    CLAUDE.md's promise is that adding a language means writing one extractor: the resolver,
    the renderers and the orientation queries know nothing about any language. An `import ast`
    here would break that quietly — it would work perfectly, on Python, for ever.
    """
    import ast as _ast

    from dunneflow.web import changes as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "from ..canonical import canonical" in src, (
        "the diff no longer asks for a canonical form — it either compares expressions as "
        "written, or it has started making one itself"
    )

    # **Over the code, never over the prose**, and this guard fired on its own docstring
    # before it did this: `_constants_moved` explains at length why a constant needs no
    # canonical pass, and cannot do that without naming `ast.unparse`. Exactly the shape
    # `test_the_diff_contains_no_write_statement` above already had to solve for `DROP` --
    # a check that cries wolf is a check nobody reads (rule 43).
    tree = _ast.parse(src)
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.Import, _ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            assert "ast" not in names, (
                "changes.py imports a parser — it has learned what a language is, and the "
                "next language will have to teach it a second time"
            )
        if isinstance(node, _ast.Attribute) and isinstance(node.value, _ast.Name):
            assert node.value.id != "ast", (
                f"changes.py calls `ast.{node.attr}` — the canonical form is the extractor's "
                "answer to give, not this module's to compute"
            )


def test_only_the_python_canonicaliser_knows_how_to_canonicalise():
    """The seam, asserted from the other end: one place makes a canonical form, per language.

    And it lives **beside** the extractors rather than inside one, which is not cosmetic:
    `code_extraction_inputs()` globs `extractors/python/*.py` into the cache key, so a
    canonicaliser there would discard every graph on the machine — sealed snapshots included
    — every time it was edited, for a change that cannot alter one fact.
    """
    from dunneflow.canonical import CANONICAL, LANG_SUFFIX, canonical

    # **The direction that can actually be wrong.** A language may have an extractor and no
    # canonicaliser -- it then compares as written, which is honest. What cannot be right is
    # a canonicaliser filed under a language no suffix produces: `canonical` looks it up
    # through `LANG_SUFFIX`, so nothing could ever reach it (rule 35, in a table).
    assert set(CANONICAL) <= set(LANG_SUFFIX.values()), (
        f"canonicalisers no suffix can reach: {sorted(set(CANONICAL) - set(LANG_SUFFIX.values()))}"
    )
    # A suffix nobody claims compares as written -- an answer, not a failure (rule 49).
    assert canonical('d["k"]', "a/b.py") == "d['k']"
    assert canonical('d["k"]', "a/b.kt") == 'd["k"]', (
        "an unknown language was canonicalised by somebody else's rules"
    )
    assert canonical("**kwargs", "a/b.py") == "**kwargs", (
        "a splat is not an expression, and must survive being handed to a parser"
    )
    assert canonical("not python at all (((", "a/b.py") == "not python at all (((", (
        "an expression that cannot be parsed must come back unchanged, never substituted"
    )


# --------------------------------------------------------------------------- #
# The WHY, which is the one layer the code itself never carries.
#
# A comment block leading a definition sits *above* the `def`, so it is outside that
# routine's `line_start` and outside its `body_hash`. Before this band existed a rewritten
# leading comment produced one of two wrong answers, and both are asserted below because
# they are different failures: in a file with module-level work it surfaced as `<module>`
# in *edited only* -- the file rather than the routine, filed under "internal computation",
# the one thing this tool says it exists not to report -- and in a file with none it
# surfaced not at all, with the page stating **"No differences found"**.
# --------------------------------------------------------------------------- #

# Module-level *work*, which is what creates the `<module>` routine whose body hash is the
# whole file. 487 of Mensores' 628 files are like this and 141 are not, so both are fixtures.
WITH_MODULE = '''\
import os

ROOT = os.environ.get("MENSORES_ROOT", "/srv")

# Intent: the pid identifies this process to the scheduler.
def alpha():
    # Caveat: getpid is per-process, not per-thread.
    return os.getpid()
'''

BARE = '''\
# Intent: the pid identifies this process to the scheduler.
def alpha():
    return 1
'''

OLD_WHY = "# Intent: the pid identifies this process to the scheduler."
NEW_WHY = "# Intent: the pid is the lease key; two workers must never share one."


def _named(rows):
    return [r["name"] for r in rows]


def test_a_rewritten_leading_comment_names_the_routine_it_leads(tmp_path):
    """The routine, not the file — and the fix is free because the store already knows.

    `<module>`'s body hash is the whole file, so the change was *reported*; it was reported
    against the wrong subject. The `comments` table attaches a leading comment to the
    routine it leads, so asking that table instead of a body hash names `alpha`.
    """
    d = changes.build(base=_graph(tmp_path, "b", WITH_MODULE.replace(OLD_WHY, NEW_WHY)),
                      compared=_graph(tmp_path, "a", WITH_MODULE))
    assert _named(d["explained_only"]) == ["alpha"], d["explained_only"]
    assert d["counts"]["behaves"] == 0, (
        "a rewritten comment is in the band that promises something the routine DOES moved"
    )
    assert "alpha" not in _named(d["edited_only"]), (
        "the routine whose intent was rewritten is filed under internal computation"
    )


def test_a_rewritten_leading_comment_is_not_no_differences_found(tmp_path):
    """The sharper half: in a file with no module-level work, nothing surfaced at all.

    Not an omission — the page states "No differences found. Every routine, call, boundary,
    table, way in and constant the map can see is the same in both", which is a confident
    false claim over a version whose intent had been rewritten. `identical` is what says it,
    so `identical` is what this asserts.
    """
    d = changes.build(base=_graph(tmp_path, "b", BARE.replace(OLD_WHY, NEW_WHY)),
                      compared=_graph(tmp_path, "a", BARE))
    assert d["identical"] is False, "the page would state that nothing differs"
    assert _named(d["explained_only"]) == ["alpha"], d["explained_only"]
    assert d["counts"]["edited_only"] == 0, (
        "nothing here was edited in a way that changed a body hash — this file has no "
        "<module> routine at all, which is why the change used to vanish"
    )


def test_the_same_words_re_wrapped_are_not_a_different_explanation(tmp_path):
    """Rule 1, in prose, and the corpus was made to say how much it matters.

    86% of Mensores' 18,731 comment lines live in a run of two or more, so re-wrapping is
    the ordinary edit rather than an exotic one. Re-wrapped at three widths without altering
    one word, comparing as written reports 1,561 · 1,186 · 1,231 of the 1,870 routines that
    own a comment; joined in line order and collapsed reports **none**.
    """
    reflowed = WITH_MODULE.replace(
        OLD_WHY, "# Intent: the pid identifies this process\n# to the scheduler.")
    d = changes.build(base=_graph(tmp_path, "b", reflowed),
                      compared=_graph(tmp_path, "a", WITH_MODULE))
    assert d["explained_only"] == [], (
        "a comment re-wrapped over two lines reads as a different explanation"
    )

    # **And the case the collapse pass actually exists for**, which the wrap above does not
    # reach: each stored line is already stripped, so joining one-space-per-break is a
    # canonical form all by itself. What is not is whitespace *inside* a line -- two spaces
    # after a full stop, which 112 of Mensores' 6,076 comment runs carry -- because a wrap
    # that breaks at exactly that point turns two spaces into one. Without the second pass
    # this is a false difference, and the first version of this test could not see it.
    spaced = WITH_MODULE.replace(
        OLD_WHY, "# Intent: the pid is the lease key.  Two workers must never share one.")
    spaced_wrapped = WITH_MODULE.replace(
        OLD_WHY, "# Intent: the pid is the lease key.\n# Two workers must never share one.")
    d2 = changes.build(base=_graph(tmp_path, "d", spaced_wrapped),
                       compared=_graph(tmp_path, "c", spaced))
    assert d2["explained_only"] == [], (
        "the same sentence, re-wrapped where it had two spaces, reads as a different "
        "explanation — the collapse pass is what this asserts and it is not running"
    )
    # The file's bytes did change, so `<module>` is legitimately edited. That is the honest
    # answer and is not what this test is about; what it is about is that `alpha` is clean.
    assert "alpha" not in _named(d["edited_only"]) + _named(d["explained_only"])


def test_the_comments_are_read_in_the_order_they_are_written(tmp_path):
    """A source guard, because the defect it prevents cannot be reproduced by a fixture.

    Drop the `ORDER BY` and SQLite still returns rows in rowid order, which for a file
    inserted in one pass *is* line order -- so every test here goes on passing while the
    query has stopped promising anything. The same objection that kept `group_concat` out of
    `_arguments_moved`: an order SQLite does not specify is one that holds until it does not.

    The line number **orders** and never keys, which is the module docstring's own
    distinction. Inserting a line above a comment block moves every number in it and changes
    no order.
    """
    from dunneflow.web.changes import COMMENTS_IN

    assert "ORDER BY" in COMMENTS_IN and "c.line" in COMMENTS_IN.split("ORDER BY")[1], (
        "the comments are read in whatever order the engine returns them, so joining them "
        "is a set with extra steps and a re-wrap reads as a rewrite"
    )
    # And the line is *not* in what is compared -- only in what orders it.
    assert "c.line" not in COMMENTS_IN.split("ORDER BY")[0], (
        "a line number reached the comparison itself, which makes one inserted import a "
        "difference in every comment below it"
    )


def test_an_inline_comment_that_moved_tags_the_row_it_already_had(tmp_path):
    """A tag, never a second row (rule 32: one row, one claim).

    An inline comment is inside the body, so the routine is already in `edited only`. What
    the tag adds is *which* part of that edit a reader might care about — and `explained
    only` must stay empty, or one routine would be counted in two bands.
    """
    rewritten = WITH_MODULE.replace(
        "# Caveat: getpid is per-process, not per-thread.",
        "# Caveat: this is the lease key and must outlive the thread.")
    d = changes.build(base=_graph(tmp_path, "b", rewritten),
                      compared=_graph(tmp_path, "a", WITH_MODULE))
    alpha = [r for r in d["edited_only"] if r["name"] == "alpha"]
    assert alpha, f"alpha is not in `edited only`: {_named(d['edited_only'])}"
    assert alpha[0]["moved"] == ["comments"], alpha[0]["moved"]
    assert _named(d["explained_only"]) == [], (
        "a routine already in a band was given a second row rather than a tag"
    )


def test_an_inline_comment_re_wrapped_leaves_no_tag(tmp_path):
    """The other direction of the same claim, and the one a weak guard would miss.

    The body hash moves either way, so `alpha` is in `edited only` whatever happens here.
    What must not happen is the tag: it would say the explanation moved when not one word
    of it did, which is the false difference rule 1 is about.
    """
    reflowed = WITH_MODULE.replace(
        "    # Caveat: getpid is per-process, not per-thread.",
        "    # Caveat: getpid is per-process,\n    # not per-thread.")
    d = changes.build(base=_graph(tmp_path, "b", reflowed),
                      compared=_graph(tmp_path, "a", WITH_MODULE))
    alpha = [r for r in d["edited_only"] if r["name"] == "alpha"]
    assert alpha, "alpha's body hash did not move, so this fixture tests nothing"
    assert alpha[0]["moved"] == [], (
        "a re-wrapped comment was tagged as a changed explanation"
    )


def test_the_five_bands_are_a_partition(tmp_path):
    """No routine in two bands, with all five populated at once.

    The four were a partition by construction and the fifth has to be subtracted from all of
    them to stay one. Asserted over a fixture that fills every band, because a partition
    that holds when two bands are empty has not been tested.
    """
    before = WITH_MODULE + '''
def beta():
    return alpha()

# Intent: unchanged throughout.
def gamma():
    return 2

def delta():
    return 3
'''
    after = (before
             .replace(OLD_WHY, NEW_WHY)                        # explained: alpha
             .replace("def beta():\n    return alpha()",
                      "def beta():\n    return os.getpid()")   # behaves: beta
             .replace("def delta():\n    return 3",
                      "def delta():\n    n = 1 + 1\n    return 3")  # edited: delta
             + "\ndef epsilon():\n    return 4\n")             # only in base
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", before))
    bands = {
        "only_in_base": d["only_in_base"], "only_in_compared": d["only_in_compared"],
        "behaves": d["behaves"], "edited_only": d["edited_only"],
        "explained_only": d["explained_only"],
    }
    filled = [k for k, v in bands.items() if v]
    assert set(filled) >= {"only_in_base", "behaves", "edited_only", "explained_only"}, (
        f"this fixture does not fill the bands it claims to: {filled}"
    )
    seen: dict[str, str] = {}
    for band, rows in bands.items():
        for r in rows:
            assert r["id"] not in seen, (
                f"{r['name']} is in both `{seen[r['id']]}` and `{band}`"
            )
            seen[r["id"]] = band


def test_a_comment_in_a_file_whose_bytes_did_not_change_is_not_looked_for(tmp_path):
    """The bound that makes this affordable, asserted as an *answer* rather than as a flag.

    A comment is text in a file, so a file both versions hold with the same content hash
    cannot hold a comment that moved — the same argument `filediff` makes when it decides
    which twelve of 628 files are worth reading, and `files.content_hash` is already in the
    graph. 41 ms over every comment in Mensores, 5.2 ms over the fifteen files that differ,
    and the same twenty routines either way.

    Two files, one changed: the answer must name the routine in the changed one and must not
    be disturbed by the other, whose bytes are identical and whose comments therefore are.
    """
    def two_files(tmp, name, one, two):
        tree = tmp / name
        tree.mkdir()
        (tree / "one.py").write_text(one)
        (tree / "two.py").write_text(two)
        db = tmp / f"{name}.db"
        store = Store(db)
        for f in sorted(tree.glob("*.py")):
            store.write_file_facts(extract_file(f, tree))
        store.conn.commit()
        store.close()
        return db

    steady = BARE.replace("alpha", "steady")
    d = changes.build(
        base=two_files(tmp_path, "b", BARE.replace(OLD_WHY, NEW_WHY), steady),
        compared=two_files(tmp_path, "a", BARE, steady))
    assert _named(d["explained_only"]) == ["alpha"], d["explained_only"]


def test_a_routine_that_moved_files_is_still_compared(tmp_path):
    """The bound's one interesting edge, and it needs no special case.

    Whichever file lost the routine and whichever gained it both differ in bytes by having
    done so, so both are in the changed set and both sides of the comparison see it.
    """
    def two_files(tmp, name, one, two):
        tree = tmp / name
        tree.mkdir()
        (tree / "one.py").write_text(one)
        (tree / "two.py").write_text(two)
        db = tmp / f"{name}.db"
        store = Store(db)
        for f in sorted(tree.glob("*.py")):
            store.write_file_facts(extract_file(f, tree))
        store.conn.commit()
        store.close()
        return db

    # `alpha` keeps its qualname -- and therefore its id -- by moving with its module name
    # unchanged is impossible, so this asserts the weaker, true thing: the move is reported
    # and nothing is silently dropped.
    d = changes.build(base=two_files(tmp_path, "b", "", BARE),
                      compared=two_files(tmp_path, "a", BARE, ""))
    moved = _named(d["only_in_base"]) + _named(d["only_in_compared"])
    assert "alpha" in moved, (
        "a routine that moved between files vanished from the comparison entirely"
    )


# --------------------------------------------------------------------------- #
# What a routine says about itself, and what a module says it is.
#
# The docstring lane, beside the comment lane and answering the same question from the
# other side. Its fixtures are separate because the shape it tests is the opposite one: a
# comment can be *outside* a routine's body hash and vanish; a docstring is always inside
# it and never vanishes, so every test here is about the band being wrong rather than
# missing -- except the module ones, where it does vanish and for a different reason.
# --------------------------------------------------------------------------- #

DOC_OLD = '"""The path a production door would resolve from the current directory."""'
DOC_NEW = '"""The path a production door would resolve right now."""'

DOCUMENTED = f"""\
def alpha():
    {DOC_OLD}
    return 1
"""

MODULE_DOC_OLD = '"""Queue state, and the one place it is written."""'
MODULE_DOC_NEW = '"""Queue state. Every writer goes through `push`; nothing else may."""'

# A file that runs **nothing** at import, so it has no `<module>` routine at all. This is
# the 141-of-628 case, and it is the one where a rewritten module docstring changes no row.
MODULE_BARE = f"""\
{MODULE_DOC_OLD}


def alpha():
    return 1
"""

# ...and one that does, so it has a `<module>` routine whose body hash is the whole file.
MODULE_WITH_WORK = f"""\
{MODULE_DOC_OLD}

import os

ROOT = os.environ.get("MENSORES_ROOT", "/srv")


def alpha():
    return 1
"""


def _tagged(d, tag):
    """Every routine carrying one `moved` tag, in whichever band it landed in."""
    return sorted(r["name"] for band in ("behaves", "edited_only", "explained_only")
                  for r in d[band] if tag in (r.get("moved") or []))


def test_a_rewritten_docstring_tags_the_row_it_already_had(tmp_path):
    """The whole shape of this lane in one assertion, and it is not the comment lane's.

    A docstring lives *inside* the `def`, so `body_hash` moves with it and the routine is
    already in `edited only` -- the band whose claim is *the body differs and nothing it
    does does*, described in this tool's own words as internal computation and the one thing
    it exists not to report. Nothing was missing; the reason given was wrong.

    So the tag, and **the band must not move**. A rewritten docstring did not move anything
    the routine does, and promoting it to `behaves` would be the comment lane's mistake with
    the sign flipped (rule 32: one row, one claim).
    """
    d = changes.build(base=_graph(tmp_path, "b", DOCUMENTED.replace(DOC_OLD, DOC_NEW)),
                      compared=_graph(tmp_path, "a", DOCUMENTED))
    assert _tagged(d, "docstring") == ["alpha"], d["edited_only"]
    assert _named(d["edited_only"]) == ["alpha"], (
        "a rewritten docstring is a body change, and the band that says so is right"
    )
    assert d["counts"]["behaves"] == 0, (
        "a docstring is not something the routine does"
    )
    assert d["counts"]["explained_only"] == 0, (
        "explained_only holds what would be in no band; this row has one"
    )


def test_a_docstring_removed_outright_is_a_difference(tmp_path):
    """One side has one and the other does not, which the set comparison must catch.

    The query asks only for routines that *have* a docstring -- carrying an empty string per
    routine to state its absence would be the same answer at a cost -- so this is the case
    that says the default on the missing side is doing its job.
    """
    stripped = DOCUMENTED.replace("    " + DOC_OLD + "\n", "")
    d = changes.build(base=_graph(tmp_path, "b", stripped),
                      compared=_graph(tmp_path, "a", DOCUMENTED))
    assert _tagged(d, "docstring") == ["alpha"], d


def test_the_same_docstring_re_wrapped_is_not_a_different_explanation(tmp_path):
    """Rule 1 in prose again, and the corpus was made to say how much it matters.

    Re-wrapping every one of Mensores' 3,769 docstrings at three widths without altering a
    word -- 52% of them are multi-line with a blank-line break, so this is the ordinary edit
    -- reports 2,060 · 1,652 · 1,602 routines as written and **none** canonically.
    """
    wrapped = DOCUMENTED.replace(
        DOC_OLD,
        '"""The path a production door\n    would resolve from the current directory."""')
    d = changes.build(base=_graph(tmp_path, "b", wrapped),
                      compared=_graph(tmp_path, "a", DOCUMENTED))
    assert _tagged(d, "docstring") == [], (
        "the same words at a different width are not a different explanation"
    )


def test_merging_a_docstrings_paragraphs_is_a_difference(tmp_path):
    """The measurement that chose the canonical form, and the half a full collapse loses.

    `_comments_moved` collapses every run of whitespace, which is right for a comment: it
    reaches the store as one row per physical line with no paragraph structure left to keep.
    A docstring reaches it through `inspect.cleandoc` with its blank lines intact, so the
    structure is there -- and PEP 257 gives the summary line its meaning by separating it.

    Measured on Mensores: merging every docstring's paragraphs without changing one word
    affects 1,996 of them, and a full collapse reports **none** of it. Both forms are silent
    on the re-wrap above, so this is the only experiment that separates them.
    """
    two = DOCUMENTED.replace(
        DOC_OLD, '"""Resolve a path.\n\n    From the current directory, which is the bug.\n    """')
    one = DOCUMENTED.replace(
        DOC_OLD, '"""Resolve a path.\n    From the current directory, which is the bug.\n    """')
    d = changes.build(base=_graph(tmp_path, "b", one),
                      compared=_graph(tmp_path, "a", two))
    assert _tagged(d, "docstring") == ["alpha"], (
        "a summary line that stopped being a summary line is a change to how it reads, "
        "and a full whitespace collapse cannot see it"
    )

    # **A blank line with spaces on it is still a blank line**, and this is the half a
    # `\n\n` would miss. Editors disagree about trimming, so the two versions of one file
    # routinely differ there and nowhere else -- and a paragraph break that stops counting
    # as one turns a re-wrap back into 1,996 false differences. Found by mutation.
    # Eight spaces, not three. `ast.get_docstring` is `inspect.cleandoc`, which strips the
    # docstring's common margin -- four here -- so a blank line padded to *less* than the
    # margin comes out genuinely empty and this fixture would be testing nothing. Padded
    # past it, the blank line reaches the store as `"    "`, which is what an editor that
    # indents blank lines to their block actually produces.
    padded = two.replace(
        '"""Resolve a path.\n\n    From', '"""Resolve a path.\n        \n    From')
    assert padded != two, "the padded fixture is the same string; this assertion is blind"
    d = changes.build(base=_graph(tmp_path, "d", padded),
                      compared=_graph(tmp_path, "c", two))
    assert _tagged(d, "docstring") == [], (
        "trailing spaces on an otherwise blank line are not a change to what a routine says"
    )


def test_a_rewritten_module_docstring_is_not_no_differences_found(tmp_path):
    """The case with no routine to report against, and it is 141 of Mensores' 628 files.

    `<module>` is minted only where a file has module-level work. In a file that runs
    nothing at import there is no such routine, no body hash moves, no fact moves -- and the
    page states "No differences found", which is a confident false claim over a file whose
    one statement of what it *is* has been rewritten. `identical` is what says it, so
    `identical` is what this asserts.
    """
    d = changes.build(base=_graph(tmp_path, "b",
                                  MODULE_BARE.replace(MODULE_DOC_OLD, MODULE_DOC_NEW)),
                      compared=_graph(tmp_path, "a", MODULE_BARE))
    assert d["identical"] is False, "the page would state that nothing differs"
    assert [r["path"] for r in d["modules_explained"]] == ["m.py"], d["modules_explained"]
    assert d["counts"]["modules_explained"] == 1
    assert d["counts"]["edited_only"] == 0, (
        "nothing here was edited in a way that changed a body hash -- this file has no "
        "<module> routine at all, which is why the change vanished"
    )


def test_a_module_docstring_is_a_file_and_never_a_routine(tmp_path):
    """Rule 74's shape: a module is not one of its routines, so it is not filed as one.

    In a file that *does* run something at import there is a `<module>` routine whose body
    hash is the whole file, so this change is also reported there -- honestly, because the
    file's bytes did change. What must not happen is the module docstring being *counted*
    as a routine, or the row that carries it naming something the reader cannot open.
    """
    d = changes.build(base=_graph(tmp_path, "b",
                                  MODULE_WITH_WORK.replace(MODULE_DOC_OLD, MODULE_DOC_NEW)),
                      compared=_graph(tmp_path, "a", MODULE_WITH_WORK))
    rows = d["modules_explained"]
    assert [r["path"] for r in rows] == ["m.py"], rows
    assert all("path" in r and "module" in r and "id" not in r for r in rows), (
        "a file row carrying a node id would put a path where a routine is expected"
    )
    assert _tagged(d, "docstring") == [], (
        "the module docstring is not any routine's docstring, not even <module>'s"
    )
    assert d["counts"]["routines_base"] == d["counts"]["routines_compared"], (
        "no routine was created or destroyed by rewriting a module docstring"
    )


def test_a_module_docstring_re_wrapped_is_not_a_difference(tmp_path):
    """The same canonical form as the routine lane, because it is the same kind of prose."""
    wrapped = MODULE_BARE.replace(
        MODULE_DOC_OLD, '"""Queue state, and the one\nplace it is written."""')
    d = changes.build(base=_graph(tmp_path, "b", wrapped),
                      compared=_graph(tmp_path, "a", MODULE_BARE))
    assert d["modules_explained"] == [], d["modules_explained"]


def test_a_docstring_in_a_file_whose_bytes_did_not_change_is_not_looked_for(tmp_path):
    """The bound, asserted as an *answer* rather than as a flag, and shared with two lanes.

    A docstring is text in a file, so equal content hashes are equal docstrings -- the same
    argument the comment lane makes, and the reason `_changed_files` is one function three
    lanes call rather than three copies waiting to disagree (rule 51). Measured on Mensores:
    22.3 ms over all 628 files, 3.2 ms over the fifteen that differ, same answer.
    """
    def two_files(tmp, name, one, two):
        tree = tmp / name
        tree.mkdir()
        (tree / "one.py").write_text(one)
        (tree / "two.py").write_text(two)
        db = tmp / f"{name}.db"
        store = Store(db)
        for f in sorted(tree.glob("*.py")):
            store.write_file_facts(extract_file(f, tree))
        store.conn.commit()
        store.close()
        return db

    steady = DOCUMENTED.replace("alpha", "steady")
    d = changes.build(
        base=two_files(tmp_path, "b", DOCUMENTED.replace(DOC_OLD, DOC_NEW), steady),
        compared=two_files(tmp_path, "a", DOCUMENTED, steady))
    assert _tagged(d, "docstring") == ["alpha"], d


def test_the_two_explanation_tags_are_kept_apart(tmp_path):
    """A comment and a docstring are two things, and one tag for both would say neither.

    A comment is what somebody wrote *around* a routine; a docstring is what the routine
    says about *itself*. They are rewritten independently and a reader clearing a worklist
    wants to know which -- rule 32, in a tag.
    """
    with_both = '''\
# Intent: the pid identifies this process to the scheduler.
def alpha():
    """Return the identifier."""
    return 1
'''
    both_moved = (with_both.replace(OLD_WHY, NEW_WHY)
                           .replace('"""Return the identifier."""',
                                    '"""Return the lease key. Two workers must not share one."""'))
    d = changes.build(base=_graph(tmp_path, "b", both_moved),
                      compared=_graph(tmp_path, "a", with_both))
    row = next(r for band in ("behaves", "edited_only", "explained_only")
               for r in d[band] if r["name"] == "alpha")
    assert row["moved"] == ["comments", "docstring"], row

    only_doc = with_both.replace('"""Return the identifier."""',
                                 '"""Return the lease key."""')
    d = changes.build(base=_graph(tmp_path, "d", only_doc),
                      compared=_graph(tmp_path, "c", with_both))
    row = next(r for band in ("behaves", "edited_only", "explained_only")
               for r in d[band] if r["name"] == "alpha")
    assert row["moved"] == ["docstring"], (
        "the comment did not move, and a tag that appears anyway is a false difference"
    )


def test_the_prose_bound_is_the_files_that_differ_and_every_lane_takes_it() -> None:
    """The bound is a **cost** decision, so no answer can catch it being removed.

    Every prose lane returns the same rows bounded or unbounded -- a file whose bytes are
    identical holds identical prose, which is the whole argument -- so the tests that assert
    the answer pass either way and the comment lane's own said so in as many words. That was
    affordable when it was 41 ms against 5.2; the docstring lane is 22.3 ms against 3.2, and
    `/api/changes` measured 480 ms against a 500 ms budget. Nineteen milliseconds is
    **almost exactly the headroom**, so the bound stops being a nicety and starts being the
    thing that keeps the row in budget.

    Two ways to lose it and both are checked, because a guard for one passes cleanly against
    the other (rule 37): the bound itself widening, and a lane going round it.
    """
    import ast as _ast

    src = (Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web"
           / "changes.py").read_text(encoding="utf-8")
    tree = _ast.parse(src)
    fn = {n.name: n for n in _ast.walk(tree) if isinstance(n, _ast.FunctionDef)}

    # It reads the changed-file query and nothing wider. Asserted over the *call* rather
    # than over the string, because the string is quoted in the prose above it (rule 43).
    called = {c.func.id for c in _ast.walk(fn["_changed_files"])
              if isinstance(c, _ast.Call) and isinstance(c.func, _ast.Name)}
    assert "CHANGED_FILES" not in called
    assert any(isinstance(n, _ast.Name) and n.id == "CHANGED_FILES"
               for n in _ast.walk(fn["_changed_files"])), (
        "_changed_files no longer reads CHANGED_FILES, so the bound is whatever it now asks"
    )

    # And every prose lane takes it. Named as an absence over the whole module: what has to
    # be caught is a *new* lane written with its own bound, which would look like working
    # code and quietly cost the budget row (rule 74's guard shape).
    for lane in ("_comments_moved", "_moved_prose", "_module_docs_moved"):
        names = {n.id for n in _ast.walk(fn[lane])
                 if isinstance(n, _ast.Name)}
        assert "_changed_files" in names, (
            f"{lane} does not take the shared bound; two answers to which files are worth "
            "reading is rule 51, and one of them is 19 ms of a 20 ms headroom"
        )
        assert "CHANGED_FILES" not in names, (
            f"{lane} builds its own bound instead of taking the one place that owns it"
        )


def test_the_bound_names_the_files_that_differ_and_no_others(tmp_path):
    """The bound's own answer, over two files where one changed. Rule 13, on a bound."""
    def two_files(tmp, name, one, two):
        tree = tmp / name
        tree.mkdir()
        (tree / "one.py").write_text(one)
        (tree / "two.py").write_text(two)
        db = tmp / f"{name}.db"
        store = Store(db)
        for f in sorted(tree.glob("*.py")):
            store.write_file_facts(extract_file(f, tree))
        store.conn.commit()
        store.close()
        return db

    steady = DOCUMENTED.replace("alpha", "steady")
    base = two_files(tmp_path, "b", DOCUMENTED.replace(DOC_OLD, DOC_NEW), steady)
    compared = two_files(tmp_path, "a", DOCUMENTED, steady)
    conn = changes._attach(compared, base)
    try:
        assert changes._changed_files(conn, "compared", "base") == ["one.py"], (
            "the bound names a file whose bytes are identical, so every prose lane reads "
            "the whole program to get the answer it already had"
        )
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Structures: the third subject, added 2026-09-02. Compared by nothing before that
# -- not presence, not what they declare, not what they say about themselves. On
# Mensores' pair it hid eight structures that appear or vanish.
# --------------------------------------------------------------------------- #

STRUCTS = '''\
from dataclasses import dataclass
from typing import Literal


@dataclass
class Claim:
    """What somebody asserted."""

    who: str
    weight: int = 1


Status = Literal["open", "shut"]
'''


def test_a_structure_only_the_base_has_is_reported(tmp_path):
    grown = STRUCTS + '\n\n@dataclass\nclass Extra:\n    """Late arrival."""\n\n    n: int\n'
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", STRUCTS))
    assert [r["name"] for r in d["structures_only_in_base"]] == ["Extra"]
    assert d["structures_only_in_compared"] == []
    assert d["counts"]["structures_only_in_base"] == 1
    assert d["identical"] is False


def test_a_structure_only_the_compared_has_is_reported(tmp_path):
    shrunk = STRUCTS.replace('Status = Literal["open", "shut"]\n', "")
    d = changes.build(base=_graph(tmp_path, "b", shrunk),
                      compared=_graph(tmp_path, "a", STRUCTS))
    assert [r["name"] for r in d["structures_only_in_compared"]] == ["Status"]
    assert d["structures_only_in_base"] == []


def test_a_type_alias_is_reported_though_it_can_never_have_a_method(tmp_path):
    """The row a diagram box could not have carried, and the reason the subject is the
    structure itself.

    A box is built from routine nodes (rule 74), so it exists only where a class has
    methods -- 192 of Mensores' 671 structures, and **no** TYPE_ALIAS, ENUM or TYPEDDICT
    ever. Four of the eight rows that actually move on that pair have no methods. Routing
    these through `state.fold` would have been right about the majority and silently wrong
    about the rest, which is rule 77.
    """
    grown = STRUCTS + '\nOutcome = Literal["kept", "lost"]\n'
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", STRUCTS))
    row = next(r for r in d["structures_only_in_base"] if r["name"] == "Outcome")
    assert row["kind"] == "TYPE_ALIAS"
    # And it carries an id, because `describe()` resolves one -- a row that cannot be
    # acted on is design rule 16's dead control with a count beside it (rule 30).
    assert row["id"]


def test_a_field_that_arrived_is_a_declaration_change(tmp_path):
    moved = STRUCTS.replace("    weight: int = 1\n",
                            "    weight: int = 1\n    note: str = ''\n")
    d = changes.build(base=_graph(tmp_path, "b", moved),
                      compared=_graph(tmp_path, "a", STRUCTS))
    row = next(r for r in d["structures_declared"] if r["name"] == "Claim")
    assert "fields" in row["moved"]
    assert d["structures_only_in_base"] == []


def test_a_field_whose_type_moved_is_a_declaration_change(tmp_path):
    moved = STRUCTS.replace("    weight: int = 1", "    weight: float = 1")
    d = changes.build(base=_graph(tmp_path, "b", moved),
                      compared=_graph(tmp_path, "a", STRUCTS))
    assert [r["name"] for r in d["structures_declared"]] == ["Claim"]
    assert d["structures_declared"][0]["moved"] == ["fields"]


PAIR = '''\
from dataclasses import dataclass


@dataclass
class Pair:
    """Two of a kind."""

    a: int = 0
    b: str = ""
'''


def test_reordering_two_fields_is_not_a_declaration_change(tmp_path):
    """`idx` is a **position**, and no key in this module carries one.

    Swapping two fields renumbers every one after them, which is `site_id`'s residue in a
    second costume -- and it changes nothing about what the structure holds.

    The fixture is a **pure** swap: same names, same types, same defaults, different order.
    An earlier version of this test swapped fields that also gained a default, so it
    asserted a change while its name promised none -- a test whose name and assertion
    disagree is worse than no test (rule 13, pointed at the suite).

    **The two fields differ in type as well as in name, and that is what gives the test
    teeth.** With `a: int` and `b: int` a swap is invisible to *either* key, so keying the
    comparison on `idx` instead of `name` survived this guard -- a mutation that lived
    because the fixture could not tell the two apart, which is rule 59's companion: when a
    mutation survives, ask whether the guard is weak before changing either.
    """
    swapped = PAIR.replace('    a: int = 0\n    b: str = ""\n',
                           '    b: str = ""\n    a: int = 0\n')
    assert swapped != PAIR, "the fixture did not actually swap; this guard is blind"
    d = changes.build(base=_graph(tmp_path, "b", swapped),
                      compared=_graph(tmp_path, "a", PAIR))
    assert d["structures_declared"] == [], d["structures_declared"]
    assert d["identical"] is True


def test_a_rewritten_structure_docstring_is_its_own_band(tmp_path):
    """A structure has no `body_hash`, so this can be in **no other band**.

    That is the one place it differs from a routine, whose docstring sits inside the `def`
    and so lands in `edited only` with a tag correcting the reason. Without this band a
    rewritten class docstring is reported by nothing and the page says "No differences
    found" -- the comment lane's worst answer, one subject over (rule 77).
    """
    reworded = STRUCTS.replace('"""What somebody asserted."""',
                               '"""What somebody asserted, and who stands behind it."""')
    d = changes.build(base=_graph(tmp_path, "b", reworded),
                      compared=_graph(tmp_path, "a", STRUCTS))
    assert [r["name"] for r in d["structures_explained"]] == ["Claim"]
    assert d["structures_declared"] == []
    assert d["identical"] is False


def test_a_structure_docstring_rewrapped_and_not_changed_is_no_difference(tmp_path):
    """The canonical form, asked of the third prose lane exactly as of the other two."""
    rewrapped = STRUCTS.replace('"""What somebody asserted."""',
                                '"""What somebody\n    asserted."""')
    d = changes.build(base=_graph(tmp_path, "b", rewrapped),
                      compared=_graph(tmp_path, "a", STRUCTS))
    assert d["structures_explained"] == []


def test_a_structure_on_one_side_only_is_not_also_explained_differently(tmp_path):
    """Rule 40, and it is the defect this lane actually shipped with for an hour.

    `_moved_prose` compares the **union** of the two id sets, so a structure that exists on
    one side only reads as described differently -- its docstring is here and absent there.
    Every one of those is already a presence row, and reporting it twice is two lanes
    recording one act.

    Measured on Mensores' pair when it was wrong: **5 rows, all five of them presence rows
    and not one a rewritten docstring**, against a raw ground truth of zero. The routine
    lane guards it at the same place (`& both`) and the module lane inside its own helper --
    three lanes, one rule, and this was the third time it had to be applied.
    """
    grown = STRUCTS + '\n\n@dataclass\nclass Extra:\n    """Late arrival."""\n\n    n: int\n'
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", STRUCTS))
    assert [r["name"] for r in d["structures_only_in_base"]] == ["Extra"]
    assert d["structures_explained"] == [], (
        "a structure only one side has carries its docstring with it; saying so twice is "
        "rule 40"
    )


def test_the_three_structure_lanes_are_a_partition(tmp_path):
    """No structure may appear in two of them, or one difference is reported twice."""
    both = STRUCTS + '\n\n@dataclass\nclass Extra:\n    """Late."""\n\n    n: int\n'
    other = STRUCTS.replace('"""What somebody asserted."""', '"""Asserted by whom."""') \
                   .replace("    weight: int = 1", "    weight: float = 1")
    d = changes.build(base=_graph(tmp_path, "b", both),
                      compared=_graph(tmp_path, "a", other))
    seen = {}
    for lane in ("structures_only_in_base", "structures_only_in_compared",
                 "structures_declared", "structures_explained"):
        for r in d[lane]:
            assert r["id"] not in seen, (
                f"{r['name']} is in both {seen.get(r['id'])} and {lane}"
            )
            seen[r["id"]] = lane
    assert seen, "the fixture produced no structure rows; this guard is blind"


def test_a_structure_that_did_not_move_is_reported_by_no_lane(tmp_path):
    d = changes.build(base=_graph(tmp_path, "b", STRUCTS),
                      compared=_graph(tmp_path, "a", STRUCTS))
    for lane in ("structures_only_in_base", "structures_only_in_compared",
                 "structures_declared", "structures_explained"):
        assert d[lane] == [], lane
    assert d["identical"] is True


def test_every_presence_row_can_be_acted_on_or_says_it_cannot(tmp_path):
    """A row that names something and cannot open it is design rule 16 with a label on it.

    Every band here is a list of things a reader wants to look at, and for a long time all
    of them rendered as bare text. The fix is only half done if a *band* is missed, and one
    was: `_constants_moved` built its rows by hand with a label and an id and **no route**,
    so 23 of the 30 constant rows were clickable and the seven whose value had moved -- the
    band whose entire claim is *this is not constant any more* -- were not. Nothing failed;
    the rows simply rendered as text, exactly as every row used to.

    So this asserts the **shape over every band of every kind**, rather than over the two
    that were written first. `entrypoints` is the one kind that legitimately carries no
    subject: its route wants the routines a way in starts, and this table cannot reach them.
    Declared, not inferred -- an empty `nav` is a claim that there is nothing to open, and
    it has to be as deliberate as a route is.
    """
    grown = BEFORE + "\nLIMIT = 5\n"
    d = changes.build(base=_graph(tmp_path, "b", grown),
                      compared=_graph(tmp_path, "a", BEFORE))

    routable = {k for k, p in changes.PRESENCE.items() if p.nav}
    assert routable, "no presence kind declares a route; this guard is blind"

    for kind, bands in d["presence"].items():
        for band, rows in bands.items():
            for r in rows:
                assert set(r) >= {"label", "id", "nav"}, (
                    f"{kind}.{band} row is not the presence row shape: {r}")
                if kind in routable:
                    assert r["nav"] and r["id"], (
                        f"{kind}.{band} names {r['label']!r} and cannot be opened")
                else:
                    assert not r["nav"], (
                        f"{kind}.{band} claims a route it has no subject for: {r}")


def test_a_moved_constant_is_reachable(tmp_path):
    """The band Tom asked for, checked as a whole row rather than as a name.

    `EXPECTED_SCHEMA_VERSION` moved says less than 27 → 28, and both of those say nothing
    at all if the row cannot be opened to see them in context.
    """
    before = "X: int = 1\n"
    after = "X: int = 2\n"
    d = changes.build(base=_graph(tmp_path, "b", after),
                      compared=_graph(tmp_path, "a", before))
    moved = d["presence"]["constants"]["moved"]
    assert len(moved) == 1, moved
    row = moved[0]
    assert row["id"] == "const:m.X" and row["nav"], row
    assert (row["base"], row["compared"]) == ("2", "1"), row
    assert row["moved"] == ["value"], row
