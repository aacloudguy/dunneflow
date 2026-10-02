"""Which routines a flow diagram keeps when it cannot draw them all (BACKLOG 3).

Shallowest first, then widest reach, then id (Tom, 2026-10-02). The cut used to fall
wherever the breadth-first walk had got to: reproducible, and arbitrary.
"""

from __future__ import annotations

from dunneflow.render.mermaid import command_tree_diagram
from dunneflow.resolve.calls import resolve_calls
from dunneflow.resolve.flows import trace_flow
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

PROGRAM = (
    "def leaf_one():\n    return 1\n\n"
    "def leaf_two():\n    return 2\n\n"
    "def leaf_three():\n    return 3\n\n"
    + "".join(f"def n{i}():\n    return 0\n\n" for i in range(6)) +
    "def zz_wide():\n    leaf_one()\n    leaf_two()\n    leaf_three()\n\n"
    "def main():\n" + "".join(f"    n{i}()\n" for i in range(6)) + "    zz_wide()\n"
)


def test_the_cut_keeps_the_routine_that_leads_furthest(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "m.py").write_text(PROGRAM, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    try:
        analyze_tree(src, store)
        resolve_calls(store)
        main = store.query("SELECT id FROM routines WHERE name = 'main'")[0]["id"]
        siblings = [r["id"] for r in store.query(
            "SELECT id FROM routines WHERE name LIKE 'n_' OR name = 'zz_wide'")]
        wide = store.query("SELECT id FROM routines WHERE name = 'zz_wide'")[0]["id"]
        # The test has teeth only if the old order -- by id -- would have cut it.
        assert min(siblings) != wide, "rename the siblings: id order alone keeps zz_wide"
        flow = trace_flow(store, main, "main", max_nodes=2)
        names = {n.name for n in flow.nodes}
        assert flow.truncated
        assert names == {"main", "zz_wide"}, names
    finally:
        store.close()


def test_the_command_tree_draws_the_widest_reaching_commands():
    commands = [{"name": f"c{i}", "routine_id": None, "module": "m", "reach": i}
                for i in range(9)]
    drawn = command_tree_diagram({"var": "app", "commands": commands, "children": []},
                                 max_commands=3)
    assert all(f'"c{i}"' in drawn for i in (6, 7, 8)), drawn
    assert '"c0"' not in drawn and "+6 more" in drawn
