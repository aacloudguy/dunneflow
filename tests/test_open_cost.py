"""Opening a large map reads its biggest tables in table order (BACKLOG 8).

Unreal's Runtime part, 262,879 routines in a 766 MB graph, took 27.6 minutes to open, and
the whole of it was one access path: `ROUTINE_NODES` walked the routines through their
primary-key index, so every row was a random seek into the table, on an external volume.
The same rows read in table order and sorted in memory took 7.7 s; the index walk was killed
unfinished at 15 m 46 s. `CALL_EDGES` grouped 947,786 calls the same way.

The plan is what is pinned, because the cost only shows at a size no test can build.
"""

from __future__ import annotations

import pytest

from dunneflow.web import queries
from dunneflow.web.graph import pkg_params


@pytest.mark.parametrize("name", ["ROUTINE_NODES", "STRUCTURE_NODES", "CALL_EDGES"])
def test_the_model_reads_its_big_tables_in_table_order(analyzed, name):
    sql = getattr(queries, name)
    plan = [str(r[-1]) for r in analyzed.conn.execute(
        "EXPLAIN QUERY PLAN " + sql, pkg_params("") if ":" in sql else ())]
    walked = [p for p in plan if p.startswith("SCAN") and "USING" in p]
    assert not walked, f"{name} walks an index row by row: {plan}"


def test_reach_walked_in_memory_is_the_reach_the_query_finds(analyzed, monkeypatch):
    """BACKLOG 8's second step: the cover's reach, walked in memory on a read-only store,
    must be the set the recursive query returns, for every routine and for a set of them.

    Both kinds of store walk in memory since 2026-11-02 (a writable one keyed by what it
    has written), so the query is reached by taking the graph away from one of them: the
    query is still the path every walk without a graph takes, and the two must agree."""
    from dunneflow.store import Store

    ids = [r["id"] for r in analyzed.query("SELECT id FROM routines ORDER BY id")]
    reader = Store(analyzed.path, writable=False)
    monkeypatch.setattr(analyzed, "_reach_graph", lambda cross=True: None)
    try:
        assert reader._reach_graph() is not None and analyzed._reach_graph() is None
        for rid in ids:
            assert set(reader.reachable_from(rid)) == set(analyzed.reachable_from(rid)), rid
            assert set(reader.reachable_from(rid, 1)) == set(analyzed.reachable_from(rid, 1))
        assert reader.reachable_from_many(ids[:5]) == analyzed.reachable_from_many(ids[:5])
        assert reader.reachable_from_many(["not-a-routine"]) == set()
        assert reader.boundaries_reached_many(ids) == analyzed.boundaries_reached_many(ids)
        for rid in ids[:20]:
            assert (reader.boundaries_reached_many([rid])
                    == analyzed.boundaries_reached_many([rid])), rid
    finally:
        reader.close()


def test_a_writable_store_s_graph_is_the_graph_it_has_now(analyzed):
    """The cache a writable store keeps is stamped with `total_changes`, so a row it writes
    is in the next walk: a graph taken before `resolve_calls` finished must never answer
    after it (the reason a writable store kept the query until 2026-11-02)."""
    rows = [r["id"] for r in analyzed.query("SELECT id FROM routines ORDER BY id")]
    a = rows[0]
    before = set(analyzed.reachable_from(a))
    b = next(x for x in rows if x not in before)  # a routine the walk cannot reach yet
    assert analyzed._reach_graph() is not None
    analyzed.conn.execute(
        "INSERT INTO dispatch_links(site_id, caller_id, routine_id) VALUES('probe', ?, ?)",
        (a, b))
    try:
        assert b in set(analyzed.reachable_from(a))
        assert b in analyzed.reachable_from_many([a])
    finally:
        analyzed.conn.execute("DELETE FROM dispatch_links WHERE site_id = 'probe'")
    assert set(analyzed.reachable_from(a)) == before


def test_a_finished_map_carries_its_counts_and_a_reader_uses_them(sample_tree, tmp_path):
    """Every `COUNT(*)` reads its whole table, and the cover paid 86 s for them at each open
    of a large map (BACKLOG 8). The analysis that finishes a map records them once."""
    import json

    from dunneflow import cli
    from dunneflow.store import Store

    assert cli.main(["analyze", str(sample_tree), "--name", "sample", "--output",
                     str(tmp_path), "--quiet", "--no-docs"]) == 0
    graph = next((tmp_path / "sample").glob("graph@*.db"))
    reader = Store(graph, writable=False)
    try:
        stored = json.loads(reader.get_meta("counts") or "{}")
        assert stored and reader.counts() == stored
    finally:
        reader.close()
    writer = Store(graph)
    try:
        assert writer.counts() == stored, "the recorded counts are not the counted ones"
    finally:
        writer.close()
