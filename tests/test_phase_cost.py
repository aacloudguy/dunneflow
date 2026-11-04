"""The anomaly phase and the map, made cheaper without changing what they say.

Unreal's Runtime spent 2,416 s looking for anomalies and 893 s writing the map. The largest
single cost was `_lost_edges` asking `calls` once per group of unpinned calls -- 1,465 times,
on a column with no index -- and it is now one ordered read. What is pinned here is that the
answer did not move: every group's call sites, in the order they were listed before.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.anomalies import Report, _lost_edges
from dunneflow.store import Store


def _store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "graph.db")
    c = s.conn
    c.executemany(
        "INSERT INTO routines(id, name, qualname, module, file, line_start, line_end, lang)"
        " VALUES(?, ?, ?, 'm', ?, 1, 99, 'python')",
        [("r1", "a", "m.a", "a.py"), ("r2", "b", "m.b", "b.py"), ("r3", "c", "m.c", "a.py")])
    rows = [
        # two groups, several files, and two calls on one line from two callers -- the tie
        # the old per-group order never broke
        ("a.py", "r1", "save", 10, 3), ("a.py", "r3", "save", 10, 3),
        ("b.py", "r2", "save", 4, 3), ("a.py", "r1", "load", 7, 2),
        ("b.py", "r2", "load", 2, 2), ("b.py", "r2", "self.go", 9, 2),
        # not lost: one rival, or a dotted receiver the detector leaves alone
        ("b.py", "r2", "fine", 3, 1), ("b.py", "r2", "obj.save", 5, 4),
    ]
    c.executemany(
        "INSERT INTO calls(file, caller_id, callee_expr, line, confidence, ambiguous)"
        " VALUES(?, ?, ?, ?, 'POSSIBLE', ?)", rows)
    c.commit()
    return s


def _per_group(store: Store, expr: str) -> list[tuple[str, int, str]]:
    """The query `_lost_edges` ran once per group until 2026-11-03."""
    return [(str(x["file"]), int(x["line"] or 0), str(x["caller"])) for x in store.query(
        "SELECT c.file, c.line, r.qualname AS caller FROM calls c"
        "  LEFT JOIN routines r ON r.id = c.caller_id"
        " WHERE c.ambiguous > 1 AND c.callee_expr = ?"
        " ORDER BY c.file, c.line, c.callee_expr", (expr,))]


def test_every_group_lists_the_call_sites_the_per_group_query_did(tmp_path: Path) -> None:
    store = _store(tmp_path)
    r = Report()
    _lost_edges(store, r)
    found = {a.subject: a for a in r.items}
    assert set(found) == {"save", "load", "self.go"}
    for expr, a in found.items():
        got = [(o.file, o.line, o.label.split(" → ")[0]) for o in a.occurrences]
        want = _per_group(store, expr)
        assert sorted(got) == sorted(want), expr
        # The order the old query defended -- file, then line -- is kept ...
        assert [(f, n) for f, n, _ in got] == [(f, n) for f, n, _ in want], expr
    # ... and the tie it left to the engine is now broken by the caller.
    assert [o.label for o in found["save"].occurrences[:2]] == [
        "m.a → save", "m.c → save"]


def test_the_streamed_flows_page_is_the_page_the_join_wrote(analyzed, tmp_path: Path) -> None:
    """Streamed to disk rather than joined in memory (1.14 GB on Unreal's Runtime), and
    byte for byte what `"\\n".join(lines)` produced, so no map's flows page moves."""
    from dunneflow.render import markdown
    from dunneflow.render.page import Stamp
    from dunneflow.resolve.flows import ways_in

    stamp = Stamp.of(analyzed, None)
    ranked = ways_in(analyzed)
    path = markdown._flows(analyzed, tmp_path, "sample", stamp, ranked=ranked)

    class Joined(list):
        def close(self) -> None:
            pass

    held = Joined()
    markdown._flows_into(held, analyzed, "sample", stamp, ranked, None)  # type: ignore[arg-type]
    # As text: both the join's `write_text` and the stream translate newlines on Windows.
    assert path.read_text(encoding="utf-8") == "\n".join(held)
    assert len(held) > 3, "the sample program drew no flows, so this compared nothing"


def _inventory_per_way_in(store: Store, roots: list[str]) -> list[tuple[str, str, str]]:
    """What `_flow_inventory` asked the graph for each way in until 2026-11-03."""
    import json

    reached = sorted(store.reachable_from_many(roots))
    ids = (json.dumps(reached),)
    rows = store.query(
        "SELECT id, qualname, module, file, line_start FROM routines"
        " WHERE id IN (SELECT value FROM json_each(?))"
        " ORDER BY module, qualname, file, line_start", ids)
    bounds: dict[str, list[str]] = {}
    for b in store.query(
            "SELECT routine_id, kind, direction, target FROM boundaries"
            " WHERE routine_id IN (SELECT value FROM json_each(?))"
            " ORDER BY kind, direction, target", ids):
        label = f"{b['kind']}{'→' if b['direction'] == 'OUT' else '←'}{b['target'] or '?'}"
        entries = bounds.setdefault(b["routine_id"], [])
        if label not in entries:
            entries.append(label)
    return [(r["qualname"], "; ".join(bounds.get(r["id"], [])) or "—",
             f"{r['file']}:{r['line_start']}") for r in rows]


def test_every_inventory_lists_what_the_per_way_in_queries_did(analyzed) -> None:
    """One read per render instead of two queries per way in (9,032 s of Runtime's
    render), and every way in's table is the table those queries produced, row for row."""
    from dunneflow.render.markdown import _esc, _flow_inventory, _Inventory
    from dunneflow.resolve.flows import ways_in

    index = _Inventory(analyzed)
    rooted = [d for d in ways_in(analyzed) if d["roots"]]
    assert rooted, "the sample program has no traced way in, so this compared nothing"
    compared = 0
    for d in rooted:
        want = [f"| `{_esc(q)}` | {_esc(t)} | {_esc(w)} |"
                for q, t, w in _inventory_per_way_in(analyzed, d["roots"])]
        text = _flow_inventory(analyzed, d, index)
        got = [x for x in text.split("\n") if x.startswith("| `")]
        assert got == want, d["name"]
        assert _flow_inventory(analyzed, d) == text, "a fresh index wrote a different table"
        compared += len(got)
    assert compared > 3



def test_a_batched_module_reads_the_routines_one_at_a_time_did(analyzed) -> None:
    """`routines` reads each child table once instead of three queries per routine, and
    every routine -- its parameters, comments and annotations, in their order -- is the
    one `routine(id)` reads alone."""
    modules = [r["module"] for r in analyzed.query(
        "SELECT DISTINCT module FROM routines ORDER BY module")]
    assert modules
    children = 0
    for m in [*modules, None]:
        batched = analyzed.routines(m)
        assert batched, m
        assert batched == [analyzed.routine(r.id) for r in batched], m
        children += sum(len(r.params) + len(r.comments) + len(r.annotations) for r in batched)
    assert children > 0, "no routine had a child row, so the grouping went unchecked"
