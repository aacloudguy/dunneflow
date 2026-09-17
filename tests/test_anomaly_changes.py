"""What the comparison says about each finding.

Every test here is a way the pairing can be wrong while looking right. Findings are the
one thing in this dashboard that is *computed* rather than stored, so the failure mode is
not a bad join -- it is a confident band on a finding that is not the one it names.

**Every call names its ends.** `build(base=..., compared=...)`, as in `test_changes.py`
and for the same reason: the two are not interchangeable and swapping them silently
inverts every band, which is the exact defect the vocabulary exists to prevent.
"""

from __future__ import annotations

import inspect
from typing import Any

from dunneflow.web import anomalychanges
from dunneflow.web import serve as serve_mod


def _f(ident: str, *, kind: str = "LOST_EDGE", count: int = 1,
       severity: str = "SUSPECT", confidence: str = "PROBABLE",
       **rest: Any) -> dict[str, Any]:
    """One finding as it reaches the wire, which is what the pairing works on."""
    return {
        "ident": ident, "ident_parts": [ident], "kind": kind, "count": count,
        "severity": severity, "confidence": confidence,
        "title": f"{ident} ({count})", "detail": "d", "blind_spot": "b",
        "subject": ident, "file": "m.py", "line": 1, **rest,
    }


def test_a_finding_in_both_versions_is_one_finding():
    """The whole point. Measured on Mensores: 106 of 106 paired, one genuinely new."""
    built = anomalychanges.build(base=[_f("a"), _f("b")], compared=[_f("a"), _f("b")])
    assert built["identical"]
    assert built["counts"]["only_in_base"] == 0
    assert built["counts"]["only_in_compared"] == 0
    assert built["counts"]["moved"] == 0


def test_the_bands_say_where_a_finding_is_and_never_what_befell_it():
    """Rule 65, asserted over the **keys the answer carries**, not over the source.

    What misleads a reader is what reaches them. `added` and `removed` are claims about
    time, and nothing here can see time: the only instant this tool records is when the
    bytes were read. The reader owns that interpretation and makes it on the strip.

    Asserted over the *parts* of each key rather than over whole keys, because
    `findings_base` contains a forbidden word rather than equalling one -- the mistake
    that let exactly this guard pass while being weak, on the routine bands (rule 59).
    """
    built = anomalychanges.build(base=[_f("a")], compared=[_f("b")])
    forbidden = {"added", "removed", "deleted", "new", "gone", "before", "after",
                 "old", "newer", "older", "was", "since"}
    keys = list(built) + list(built["counts"])
    for row in built["moved"]:
        keys += list(row)
    for key in keys:
        parts = set(key.replace("-", "_").split("_"))
        assert not (parts & forbidden), f"`{key}` names a point in time"


def test_a_finding_only_one_version_has_lands_in_that_version_s_band():
    built = anomalychanges.build(base=[_f("a"), _f("b")], compared=[_f("b"), _f("c")])
    assert [r["ident"] for r in built["only_in_base"]] == ["a"]
    assert [r["ident"] for r in built["only_in_compared"]] == ["c"]
    assert not built["identical"]


def test_swapping_the_ends_inverts_the_answer_exactly():
    """Set membership, not a claim about time -- so it must invert and nothing more.

    Driven against the real pair as well: base 22:53:57 reports 1 only_in_base and 0
    only_in_compared, and the same two graphs the other way round report 0 and 1.
    """
    a, b = [_f("a"), _f("b")], [_f("b"), _f("c")]
    one = anomalychanges.build(base=a, compared=b)
    other = anomalychanges.build(base=b, compared=a)
    assert [r["ident"] for r in one["only_in_base"]] == \
           [r["ident"] for r in other["only_in_compared"]]
    assert [r["ident"] for r in one["only_in_compared"]] == \
           [r["ident"] for r in other["only_in_base"]]
    assert one["counts"]["moved"] == other["counts"]["moved"]


def test_a_finding_that_still_stands_but_claims_something_else_says_which():
    """`moved` is the band a text diff of the report could not produce.

    A `LOST_EDGE` called twelve times and then nineteen is the same finding about the
    same expression, and the number is the whole of what changed. Naming *which* claim
    moved is what stops the reader having to diff two titles by eye.
    """
    built = anomalychanges.build(
        base=[_f("a", count=12)],
        compared=[_f("a", count=19, severity="INFO")],
    )
    assert built["counts"]["moved"] == 1
    # And `identical` has to see it. Two versions where four findings changed what they
    # claim are not two versions that agree -- the bands being empty is not the question,
    # and a comparison that says "nothing to report" here is worse than a slow one.
    assert not built["identical"]
    row = built["moved"][0]
    assert row["ident"] == "a"
    assert sorted(row["moved"]) == ["count", "severity"]
    # The row is the base's -- the version on screen -- with the other end beside it.
    assert row["count"] == 12
    assert row["in_compared"] == {"count": 19, "severity": "INFO",
                                  "confidence": "PROBABLE"}


def test_a_rendering_of_a_claim_is_not_a_second_claim():
    """`title` and `detail` restate the count; `blind_spot` describes DunneFlow.

    Comparing the renderings as well would report one change twice and call it two (rule
    40), and comparing the blind spot would put a mark on a finding when *this tool*
    changed -- a difference the program did not make.
    """
    built = anomalychanges.build(
        base=[_f("a", title="one way", detail="x", blind_spot="b")],
        compared=[_f("a", title="another", detail="y", blind_spot="rewritten")],
    )
    assert built["identical"], built["moved"]


def test_every_row_carries_the_identity_the_worklist_files_triage_under():
    """Rule 30: a band whose rows cannot be matched to the screen is a dead count."""
    built = anomalychanges.build(
        base=[_f("a"), _f("b", count=2)],
        compared=[_f("b", count=3), _f("c")],
    )
    for band in ("only_in_base", "only_in_compared", "moved"):
        for row in built[band]:
            assert row.get("ident"), f"{band} carries a row with no identity"


def test_a_finding_that_did_not_change_is_derived_rather_than_sent():
    """One answer, one place. Sending `same` would be a second, longer way to say what
    the absence of a band already says, and two answers to one question drift (rule 51).
    """
    built = anomalychanges.build(base=[_f("a")], compared=[_f("a")])
    assert "same" not in built
    assert built["counts"]["findings_base"] == 1
    assert built["counts"]["findings_compared"] == 1


def test_the_claims_compared_are_stated_once_and_the_answer_uses_that_list():
    """Rule 36: route from the table, so a fourth claim cannot be half-added.

    `CLAIMS` is what `moved` reports and what `in_compared` carries, and both are built
    from it -- so a claim added to the tuple appears on both sides or neither.
    """
    built = anomalychanges.build(
        base=[_f("a", count=1, severity="INFO", confidence="CERTAIN")],
        compared=[_f("a", count=2, severity="SUSPECT", confidence="POSSIBLE")],
    )
    row = built["moved"][0]
    assert sorted(row["moved"]) == sorted(anomalychanges.CLAIMS)
    assert set(row["in_compared"]) == set(anomalychanges.CLAIMS)


# --------------------------------------------------------------------------- #
# The route. Guarded off its own source, the way every other route here is: what
# matters is the choreography around the pairing, not the pairing it delegates.
# --------------------------------------------------------------------------- #

def _route(name: str) -> str:
    return inspect.getsource(getattr(serve_mod._Handler, name))


def test_both_comparisons_choose_the_same_two_versions():
    """One pair, or the reader is holding two comparisons and told about one.

    `/api/changes` and `/api/anomalychanges` answer about the same two versions or the
    worklist marks a pair the change view is not showing -- rule 51, where the rule kept
    at one call site rots as callers are added. Asserted by comparing the *code* that
    picks them, because two functions that agree today and are edited separately are
    exactly how they come to disagree.
    """
    def picking(src: str) -> list[str]:
        keep = [ln.strip() for ln in src.splitlines()
                if "_pick(" in ln or "revisions.known(" in ln
                or "graphs[1]" in ln or "base == compared" in ln]
        return [ln for ln in keep if ln]

    mine, theirs = picking(_route("_r_anomalychanges")), picking(_route("_r_changes"))
    assert mine, "the anomaly route no longer picks two versions -- guard is blind"
    assert mine == theirs, (
        "the two comparisons no longer choose the same pair:\n"
        f"  anomalies: {mine}\n  changes:   {theirs}"
    )


def test_a_graph_that_cannot_be_read_is_stated_and_never_emptied():
    """Rules 49 and 63: the plausible value is what hides the failure.

    `Store` refuses a stale or wrong-kind graph rather than repairing it (rules 16, 20),
    and a reader can genuinely ask for one -- `revisions.known` lists it. Answered with
    an empty list, "this version's graph is one this DunneFlow will not read" and "this
    version had nothing wrong with it" render identically, and only one of them is true.
    """
    finder = _route("_findings")
    assert "return None, str(exc)" in finder, (
        "`_findings` no longer returns a reason when it cannot read a graph"
    )
    assert "StaleGraphError" in finder and "ValueError" in finder, (
        "`_findings` does not catch the refusals `Store` actually raises"
    )

    route = _route("_r_anomalychanges")
    guard = route.split("if base_rows is None or compared_rows is None:", 1)
    assert len(guard) == 2, "the route no longer checks whether it could read both ends"
    branch = guard[1].split("return", 1)[0]
    assert '"available": False' in branch and "reason" in branch, (
        "a graph that could not be read is answered without saying so"
    )


def test_the_findings_of_one_graph_are_held_against_that_graph():
    """Keyed by the file, so the base and the compared end share one cache.

    A reader switching back and forth pays for each graph once. Keyed by the *pair* it
    would pay again for a version it had already read, which is the 4.1 s that makes this
    view expensive at all.
    """
    finder = _route("_findings")
    assert "graph_db.name" in finder, "the findings cache is not keyed by the graph file"
    assert "self._live.findings" in finder
