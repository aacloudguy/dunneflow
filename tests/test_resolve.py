"""What the resolver must and must not connect.

The must-nots matter as much as the musts: a false edge tells the reader something is
connected when it is not, which is worse than an edge simply being absent.
"""

from __future__ import annotations

from pathlib import Path

from dunneflow.resolve.calls import resolve_calls
from dunneflow.resolve.cli import resolve_cli
from dunneflow.schema import Confidence
from dunneflow.store import Store
from dunneflow.walk import analyze_tree


def _edges(store):
    return store.query(
        "SELECT c.callee_expr, r1.name AS caller, r2.name AS callee, c.confidence"
        "  FROM calls c JOIN routines r1 ON c.caller_id = r1.id"
        "  JOIN routines r2 ON c.callee_id = r2.id"
    )


def test_same_module_call_is_certain(analyzed):
    edge = [e for e in _edges(analyzed) if e["caller"] == "sync" and e["callee"] == "load_config"]
    assert edge and edge[0]["confidence"] == Confidence.CERTAIN.value


def test_builtin_never_resolves_to_a_local_routine(analyzed):
    """`list(...)` is the builtin even where a routine happens to be named `list`."""
    assert not analyzed.query(
        "SELECT 1 FROM calls WHERE callee_expr IN ('list','set','dict','print','len')"
        " AND callee_id IS NOT NULL"
    )


def test_boundary_call_is_not_also_an_internal_edge(analyzed):
    """`conn.execute(...)` is sqlite3, not a local routine that shares the name."""
    assert not analyzed.query(
        "SELECT 1 FROM calls WHERE at_boundary = 1 AND callee_id IS NOT NULL"
    )


def test_packaging_entrypoint_is_found(analyzed):
    rows = analyzed.query(
        "SELECT name, parent_id FROM entrypoints WHERE evidence LIKE '%project.scripts%'"
    )
    assert [r["name"] for r in rows] == ["sample"]


def test_console_script_links_to_its_app_object(analyzed):
    """`sample = "sample:app"` names a Typer object, not a function."""
    row = analyzed.query(
        "SELECT parent_id FROM entrypoints WHERE name = 'sample'"
    )[0]
    assert row["parent_id"] is not None


def test_commands_attach_to_their_app(analyzed):
    names = {
        r["name"]
        for r in analyzed.query("SELECT name FROM entrypoints WHERE grp != ''")
    }
    assert {"sync", "purge"} <= names


def test_mounted_subapp_is_resolved(analyzed):
    rows = analyzed.query("SELECT child_id FROM cli_mounts")
    assert rows and all(r["child_id"] for r in rows)


def test_reachability_follows_the_flow(analyzed):
    sync = analyzed.query("SELECT id FROM routines WHERE name = 'sync'")[0]["id"]
    reached = set(analyzed.reachable_from(sync))
    names = {
        r["name"]
        for r in analyzed.query(
            f"SELECT name FROM routines WHERE id IN ({','.join('?' * len(reached))})",
            tuple(reached),
        )
    }
    assert {"load_config", "fetch_remote", "run_tool"} <= names


def test_impact_is_reachability_reversed(analyzed):
    load = analyzed.query("SELECT id FROM routines WHERE name = 'load_config'")[0]["id"]
    callers = set(analyzed.callers_of(load))
    sync = analyzed.query("SELECT id FROM routines WHERE name = 'sync'")[0]["id"]
    assert sync in callers


def test_boundaries_reached_transitively(analyzed):
    sync = analyzed.query("SELECT id FROM routines WHERE name = 'sync'")[0]["id"]
    kinds = {b.kind.value for b in analyzed.boundaries_reached(sync)}
    # sync itself touches nothing; everything here comes from what it calls.
    assert {"ENV", "FILE", "NETWORK", "PROCESS"} <= kinds


def test_cli_stats_report_state_not_delta(tmp_path: Path) -> None:
    """A warm re-analysis must not announce a command tree it still holds.

    The counters were incremented per row changed, so a second run -- where every
    command was already attached -- reported zero commands over an intact map.
    """
    root = tmp_path / "prog"
    root.mkdir()
    (root / "main.py").write_text(
        "import typer\n"
        "app = typer.Typer()\n"
        "\n"
        "@app.command()\n"
        "def alpha() -> None:\n"
        "    pass\n"
        "\n"
        "@app.command()\n"
        "def beta() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    db = tmp_path / "g.db"

    store = Store(db)
    analyze_tree(root, store)
    cold = resolve_cli(store)
    store.close()

    store = Store(db)
    warm_stats = analyze_tree(root, store)
    warm = resolve_cli(store)
    store.close()

    assert warm_stats.cached >= 1, "the run under test was not a warm one"
    assert cold.commands_attached > 0, "no commands were attached on the cold run"
    assert warm.commands_attached == cold.commands_attached, (
        "a warm run under-reported the command tree"
    )


def test_argparse_commands_are_counted_even_with_no_app_object(tmp_path):
    """The summary line must not read as a collapsed command tree.

    `commands_attached` counts entrypoints hanging off an app object. argparse builds
    its parser inside a function, so there is no module-level app and no parent to
    hang from -- and the line therefore announced "0 commands" over a CLI holding
    eight of them. The commands were extracted correctly the whole time; only the
    statistic was blind, which is the harder kind of wrong to notice.
    """
    root = tmp_path / "src"
    root.mkdir()
    (root / "tool.py").write_text(
        "import argparse\n"
        "\n"
        "def cmd_go(args):\n"
        "    pass\n"
        "\n"
        "def build():\n"
        "    p = argparse.ArgumentParser()\n"
        "    sub = p.add_subparsers()\n"
        "    g = sub.add_parser('go')\n"
        "    g.set_defaults(func=cmd_go)\n"
        "    return p\n",
        encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    stats = resolve_cli(store)

    assert stats.apps == 0, "argparse builds its parser in a function; there is no app"
    assert stats.commands_found == 1, "the argparse subcommand was not counted"
    assert stats.commands_attached == 0, "it has no app object to attach to"

    names = [r["name"] for r in store.query(
        "SELECT name FROM entrypoints WHERE kind = 'CLI'"
    )]
    assert "go" in names, "the subcommand itself was lost, not merely uncounted"
