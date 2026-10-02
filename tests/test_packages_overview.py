"""The overview's external boxes count what the cover counts (BACKLOG 18).

A box read NETWORK 2 where the cover read 3, and DATABASE 204 against 287: the box summed
`COUNT(DISTINCT target)` per package across the packages it drew, and the cover counted
every touch. Two true numbers about two populations, with nothing on screen to say which.
The box now carries the cover's count of touches and, beside it and named, the distinct
targets over the whole program.
"""

from __future__ import annotations

from dunneflow.web import cover, packages


def test_a_boundary_box_carries_the_covers_count_and_its_distinct_targets(analyzed):
    built = packages.build(analyzed)
    on_cover = {b["kind"]: b["n"] for b in cover.build(analyzed, None, "sample")["boundaries"]}
    distinct = {str(r["kind"]): int(r["n"]) for r in analyzed.query(
        "SELECT kind, COUNT(DISTINCT target) AS n FROM boundaries"
        " WHERE target <> '' GROUP BY kind")}
    assert built["externals"], "the sample program touches nothing outside itself"
    for box in built["externals"]:
        assert box["hits"] == on_cover[box["kind"]], box
        assert box["targets"] == distinct.get(box["kind"], 0), box
