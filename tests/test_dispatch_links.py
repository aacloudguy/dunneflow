"""The dispatch arm: a call the reader marked `dynamic` reaches every body that may answer it.

Tom's decision, 2026-11-02, after traccar read 3,575 of 4,296 routines as reachable from no
way in: Netty calls one abstract `decode`, 271 decoders answer it, and a `dynamic` call had
no edge for a walk to follow. So the bodies are linked (`dispatch_links`) and every walk
crosses them, **never as an edge** (rule 2) and always said as *may run*.

On `tests/fixtures/java_edges`, through the host's own analysis, so what is tested is what
runs (rule 51). Skipped without a JDK, by name.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.ingest.contract import ToolchainMissing
from dunneflow.ingest.outofprocess import probe_toolchain

EDGES = Path(__file__).parent / "fixtures" / "java_edges"


def _why() -> str:
    plugin = ingest.PLUGINS.get("java")
    if plugin is None:
        return "this build ships no Java reader"
    try:
        probe_toolchain(plugin.manifest)
    except ToolchainMissing as exc:
        return f"no JDK this reader accepts on this machine: {exc}"
    return ""


pytestmark = pytest.mark.skipif(bool(_why()), reason=_why() or "-")


@pytest.fixture(scope="module")
def db(tmp_path_factory) -> Path:
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    path = tmp_path_factory.mktemp("dispatch") / "g.db"
    store = Store(path)
    analyze_tree(EDGES, store)
    stats = resolve_calls(store)
    assert stats.dispatch is not None and stats.dispatch.sites.get("java", 0) >= 3
    store.close()
    return path


def _ids(store, *quals: str) -> list[str]:
    out = []
    for q in quals:
        (row,) = store.query("SELECT id FROM routines WHERE qualname = ?", (q,))
        out.append(row["id"])
    return out


@pytest.fixture
def store(db):
    from dunneflow.store import Store

    s = Store(db)
    yield s
    s.close()


def test_an_abstract_step_is_inside_the_reach_of_the_method_that_calls_it(store):
    tick, step = _ids(store, "org.lib.Base.tick", "org.app.Main.step")
    assert step in store.reachable_from(tick)


def test_an_interface_call_reaches_every_body_that_may_answer_it(store):
    run, sq, ci = _ids(store, "org.app.Main.run", "org.lib.Square.area", "org.lib.Circle.area")
    reach = set(store.reachable_from(run))
    assert {sq, ci} <= reach
    assert {sq, ci} <= store.reachable_from_many([run])


def test_a_body_dispatch_may_reach_counts_its_dispatcher_as_a_dependent(store):
    run, ci = _ids(store, "org.app.Main.run", "org.lib.Circle.area")
    assert run in store.callers_of(ci)
    into = store.dispatched_into([ci])
    assert [(x["callee_expr"], x["how"]) for x in into] == [("s.area", "by dispatch")]


def test_a_dispatch_link_is_never_a_call_edge(store):
    """Rule 2: the call stays an unresolved `dynamic` call, and only the walk crosses it."""
    (row,) = store.query(
        "SELECT callee_id, reason, ambiguous FROM calls WHERE callee_expr = 's.area'")
    assert (row["callee_id"], row["reason"], row["ambiguous"]) == (None, "dynamic", 2)
    linked = store.query("SELECT COUNT(*) n FROM dispatch_links d JOIN calls c"
                         " ON c.site_id = d.site_id WHERE c.callee_id IS NOT NULL")
    assert linked[0]["n"] == 0


def test_a_store_that_cannot_change_walks_the_same_arm(db, store):
    from dunneflow.store import Store

    run, = _ids(store, "org.app.Main.run")
    ro = Store(db, writable=False)
    try:
        assert sorted(ro.reachable_from(run)) == sorted(store.reachable_from(run))
    finally:
        ro.close()


def test_a_process_zone_still_crosses_dispatch(store):
    """`cross=False` stops at a process boundary, and dispatch never leaves the process."""
    run, sq = _ids(store, "org.app.Main.run", "org.lib.Square.area")
    assert sq in store.reachable_from_many([run], cross=False)


def test_the_cli_says_the_reach_went_on_by_dispatch(db):
    from dunneflow.cli import dispatched_lines
    from dunneflow.store import Store

    s = Store(db, writable=False)
    try:
        run, = _ids(s, "org.app.Main.run")
        lines = dispatched_lines(s.dispatched(s.reachable_from(run)))
    finally:
        s.close()
    assert lines and "by dispatch" in lines[0] and "may run" in lines[0]
    assert "s.area" in lines[0] and "r.run" in lines[0]


def test_unreachable_says_it_followed_dispatch_and_strands_less(db, tmp_path):
    import shutil

    from dunneflow.anomalies import detect
    from dunneflow.store import Store

    copy = tmp_path / "copy.db"
    shutil.copyfile(db, copy)  # the arm is removed below, from a copy and never the shared map
    s = Store(copy)
    try:
        before = s.query("SELECT COUNT(*) n FROM dispatch_links")[0]["n"]
        found = {a.kind: a for a in detect(s).items}
        with_arm = found["UNREACHABLE"].count if "UNREACHABLE" in found else 0
        said = found["UNREACHABLE"].detail if "UNREACHABLE" in found else ""
        s.conn.execute("DELETE FROM dispatch_links")
        found = {a.kind: a for a in detect(s).items}
        without = found["UNREACHABLE"].count if "UNREACHABLE" in found else 0
    finally:
        s.close()
    assert before > 0 and with_arm < without
    assert not said or "followed every dispatched call" in said


def test_about_counts_the_dispatched_calls(store):
    said = store.dispatch_of_map()
    assert said is not None and said["how"] == "by dispatch"
    assert said["calls"] >= 3 and said["bodies"] >= 4


def test_the_resolve_says_what_it_linked(tmp_path):
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    store = Store(tmp_path / "g.db")
    analyze_tree(EDGES, store)
    out = io.StringIO()
    with redirect_stdout(out):
        stats = resolve_calls(store)
    store.close()
    assert stats.dispatch is not None
    assert stats.dispatch.sentence().startswith("java dispatch: ")
    assert stats.dispatch.missed.get("java", 0) == 0, "every body named lands on its routine"
