"""Switching which version the whole map is showing.

The base is what the navigator counts, the inspector reports, the code browser reads and
the stack draws. One payload set is live at a time, so changing it means the **server**
opening another graph and rebuilding the payload, the file list, both vocabulary lanes and
the cover from it -- measured between 2.8 s warm and 35 s with the other revision's stores
cold on an external volume.

Every test here is a way that can go wrong while looking right:

  - a part of the base rebuilt and another left behind, so the cover names one version and
    the stack draws another;
  - a cached comparison surviving a switch, answering about a pair that no longer applies;
  - a failed switch leaving no base at all, or a half-built one;
  - a read swapping the base, which is rule 20's shape -- a request that came to look and
    changed what it found;
  - the outgoing store closed while a request is still using it, which is what the lock
    discipline exists to prevent and is invisible until it is a crash under load.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from dunneflow import revisions
from dunneflow.extractors.python.extract import extract_file
from dunneflow.store import Store
from dunneflow.web import serve as serve_mod

SERVE_PY = Path(serve_mod.__file__)

ONE = '''\
"""A program with one of everything the base is built from."""
import sqlite3


def open_it(path):
    """Open the database."""
    conn = sqlite3.connect(path)      # why: the boundary the cover counts
    return conn


def use_it(path):
    return open_it(path)
'''

TWO = ONE + '''

def also(path):
    """Only the second version has this one."""
    return use_it(path)
'''


def _program(tmp_path: Path) -> tuple[Path, str, str]:
    """A program directory with two revisions, as `analyze` would leave it."""
    out = tmp_path / "prog"
    out.mkdir()
    revs = []
    for i, source in enumerate((ONE, TWO)):
        tree = tmp_path / f"tree{i}"
        tree.mkdir()
        (tree / "m.py").write_text(source)
        rev = f"2026-08-30T10:0{i}:00Z"
        store = Store(revisions.db_path(out, revisions.GRAPH, rev))
        store.write_file_facts(extract_file(tree / "m.py", tree))
        store.set_meta("revision", rev)
        store.conn.commit()
        store.close()
        revs.append(rev)
    return out, revs[0], revs[1]


@pytest.fixture()
def live(tmp_path: Path) -> Any:
    out, first, second = _program(tmp_path)
    lv = serve_mod._Live(out / "source.db", out)
    lv.open(revisions.db_path(out, revisions.GRAPH, first))
    try:
        yield lv, out, first, second
    finally:
        lv.close()


# ------------------------------------------------------ everything, or nothing --- #


def test_a_switch_rebuilds_every_part_of_the_base(live: Any) -> None:
    """A base is eight things, and seven of them rebuilt is a map that contradicts itself.

    The field list is read off `_Base` rather than written here, so a part added later is
    covered without anyone remembering -- rule 36, which was earned by a loop over a
    settings table narrowed to two literals that silently dropped two panels.

    Asserted by *identity*, not by value: two versions of a tiny program can produce equal
    dicts, and `==` would pass on a part that was never touched. `is` cannot.
    """
    lv, out, _first, second = live
    fields = set(serve_mod._Base.__dataclass_fields__)
    assert len(fields) >= 8, f"only {fields} -- this guard has gone blind"

    # Read off the construction, because that is where a part gets left behind, and because
    # identity cannot see it for the one field that is a `str`: Python interns short
    # strings, so two independently computed root packages are the same object and an
    # `is` check passes on a value that was never recomputed.
    src = ast.parse(inspect.getsource(serve_mod._Live.open).strip())
    made = [n for n in ast.walk(src)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "_Base"]
    assert len(made) == 1, "`open()` no longer builds exactly one `_Base`; guard is blind"
    named = {kw.arg for kw in made[0].keywords}
    assert named == fields, f"a switch does not rebuild {sorted(fields - named)}"
    carried = [kw.arg for kw in made[0].keywords
               if "self.current" in ast.unparse(kw.value)]
    assert not carried, (
        f"a switch carries {carried} over from the previous base. The cover would name one "
        "version while the stack drew another."
    )

    # And the same claim exercised, for every part that is a container and so can be told
    # apart by identity. A guard read only off the source passes on code that is right and
    # data that is not.
    containers = [f for f in fields
                  if isinstance(getattr(lv.current, f), (dict, list))]
    before = {f: getattr(lv.current, f) for f in containers}
    lv.open(revisions.db_path(out, revisions.GRAPH, second))
    kept = [f for f in containers if getattr(lv.current, f) is before[f]]
    assert not kept, f"a switch left {kept} pointing at the previous version's object"


def test_a_switch_clears_every_cached_comparison(live: Any) -> None:
    """A diff is keyed on a pair, and one end of it has just moved.

    Not a stale copy of this answer -- an answer to a different question. Kept, it would be
    rendered under the new pair's heading with the old pair's figures, which is precisely
    the failure `refreshChanges` drops its own result to avoid.
    """
    lv, out, first, second = live
    caches = serve_mod._Live.COMPARISON_CACHES
    assert len(caches) >= 2, "fewer comparison caches than there are -- guard is blind"
    for name in caches:
        getattr(lv, name)[("a.db", "b.db")] = {"available": True}
    lv.open(revisions.db_path(out, revisions.GRAPH, second))
    for name in caches:
        assert getattr(lv, name) == {}, (
            f"`{name}` computed against the previous base survived it"
        )
    assert lv.current.graph_db.name.endswith(revisions.as_filename(second) + ".db")
    assert first != second


def test_a_switch_keeps_what_is_keyed_on_one_version_rather_than_on_a_pair(
    live: Any,
) -> None:
    """The other half of the rule above, and the expensive half.

    `findings` holds what thirteen detectors concluded about **one graph file**, which a
    switch does not change: the file is the same file. Cleared with the pair caches it
    would look tidy and make every switch pay 4.1 s to learn what it already knew -- and
    `filepairs` has carried this same reasoning since it was written, because there is one
    `source.db` per program and it is never rebuilt (rule 25).
    """
    lv, out, _first, second = live
    lv.findings["some-graph.db"] = [{"ident": "x"}]
    lv.filepairs[("a", "b")] = {"files": []}
    lv.open(revisions.db_path(out, revisions.GRAPH, second))
    assert lv.findings, "a switch threw away findings keyed on a graph it did not move"
    assert lv.filepairs, "a switch threw away the sidecar pairing"
    assert "findings" not in serve_mod._Live.COMPARISON_CACHES
    assert "filepairs" not in serve_mod._Live.COMPARISON_CACHES


def test_a_failed_switch_leaves_the_previous_base_serving(live: Any, tmp_path: Path) -> None:
    """A switch may refuse; it may never leave a broken base behind.

    Rule 20's shape applied to a swap. `Store` refuses a graph written by an older
    DunneFlow rather than repairing it, and `revisions.known` lists such a graph as
    comparable regardless -- so a reader can genuinely ask for one. The map they had must
    still be there afterwards, and still answering.
    """
    lv, _out, _first, _second = live
    was = lv.current
    missing = tmp_path / "graph@nothing-here.db"
    with pytest.raises(Exception):                        # noqa: B017 -- any failure
        lv.open(missing)
    assert lv.current is was, "a failed switch replaced the base it could not build"
    rows = lv.current.store.query("SELECT COUNT(*) AS n FROM routines", {})
    assert rows[0]["n"] > 0, "the base survived the failed switch but stopped answering"


def test_a_switch_that_fails_reports_rather_than_raising_into_a_thread(live: Any,
                                                                      tmp_path: Path) -> None:
    """`switch()` runs on a thread nobody is reading. A traceback there is a silent hang.

    The reader asked for a switch and is watching a progress report; a rebuild that ends by
    writing to stderr and leaving the report saying "working" for ever is a spinner that
    never stops (rule 35 -- "not computed yet" and "nothing to report" are opposite claims,
    and so are "working" and "it failed").
    """
    lv, _out, _first, _second = live
    lv.claim("nope")
    lv.switch(tmp_path / "graph@nope.db", "nope")
    p = lv.progress()
    assert p["state"] == "failed", f"a failed switch reported {p['state']}"
    assert p["reason"], "a failure with no reason is a blank pane where a sentence belongs"
    assert p["revision"] == "nope"


def test_two_switches_at_once_start_one_rebuild(live: Any) -> None:
    """Test and set in one hold of the lock, or two requests both spend ten seconds.

    And the loser must be *told*. Answering it as though its own switch were the one now
    running is design rule 1's failure in the one place a reader cannot check by looking:
    both requests would then watch the same progress and one of them would be watching
    something it did not ask for.
    """
    lv, _out, _first, _second = live
    assert lv.claim("a") is True
    assert lv.claim("b") is False, "two switches were allowed to start together"
    assert lv.progress()["revision"] == "a", "the second claim overwrote the first's report"


def test_the_progress_report_is_replaced_whole(live: Any) -> None:
    """A half-updated report is a state the reader can be shown.

    "the glossary" beside a step count from the previous step is two numbers about one
    thing (rule 32), and it costs one dict to make impossible.
    """
    lv, _out, _first, _second = live
    lv.note(state="working", step="the glossary", done_steps=4)
    lv.note(state="done")
    assert lv.progress() == {"state": "done"}, (
        "a later report inherited fields from an earlier one"
    )


# ------------------------------------------------------------ only a POST swaps --- #


def _handler_source() -> ast.ClassDef:
    tree = ast.parse(SERVE_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "_Handler":
            return node
    raise AssertionError("_Handler is gone; this guard is blind")


def test_no_get_route_can_swap_the_base() -> None:
    """Every other route here is a read, and a GET that replaces the map is one a browser
    prefetch, a bookmark reload or a link preview fires by itself.

    Read off the two tables and the handlers they name, rather than off the route strings:
    `/api/base` is legitimately in **both** tables -- the GET reports the base and the
    progress, the POST changes it -- so a guard comparing paths would have to allow it and
    would then be allowing the thing it is for. What matters is that no handler reachable
    from `ROUTES` calls `switch`, `claim` or `open` on the live base.
    """
    cls = _handler_source()
    tables = {}
    for node in cls.body:
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id in ("ROUTES", "POST_ROUTES") and node.value is not None):
            tables[node.target.id] = {
                v.value for v in node.value.values              # type: ignore[attr-defined]
                if isinstance(v, ast.Constant)
            }
    assert tables.get("POST_ROUTES"), "there is no POST table; the switch is a read again"
    assert tables.get("ROUTES"), "the GET table is gone; this guard is blind"

    mutating = {"switch", "claim"}
    for node in cls.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in tables["ROUTES"]:
            continue
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
                assert call.func.attr not in mutating, (
                    f"the GET handler {node.name} calls {call.func.attr}() -- a read that "
                    "repairs, which is rule 20 exactly"
                )


def test_the_document_store_is_closed_once_its_lane_is_built() -> None:
    """A switch that leaks the document store leaks 148 MB per switch.

    `serve()` closed it when it was the only caller. `open()` is called on every switch
    now, and a reader moving between two versions is a thing this chunk exists to make
    ordinary — so the one-off leak became a per-switch one. Only the glossary lane holds
    anything from it, and the lane is a plain dict by the time this returns.
    """
    src = inspect.getsource(serve_mod._Live.open)
    assert "_docs_for(" in src, "the glossary no longer reads the version's own documents"
    assert "docs.close()" in src, (
        "the document store opened for the glossary is never closed -- 148 MB per switch"
    )
    tree = ast.parse(src.strip())
    closed_in_finally = any(
        "docs.close()" in ast.unparse(h)
        for n in ast.walk(tree) if isinstance(n, ast.Try) for h in n.finalbody
    )
    assert closed_in_finally, (
        "the close is not in a `finally`, so a glossary pass that raises leaks the store "
        "and the switch that failed costs more than the one that worked"
    )


def test_a_refusal_carries_no_progress_because_nothing_is_running() -> None:
    """Three fields about three different things under one answer.

    A refusal used to merge the live progress report, so declining a switch to a version
    with no graph replied `started: false` beside `state: "done"` and the **previous**
    switch's revision. Rule 13: the answer beside a claim has to be about that claim. A
    refusal is about the request, and there is no progress to report because nothing has
    started.
    """
    src = inspect.getsource(serve_mod._Handler._started)
    assert "progress()" in src, "the started answer carries no progress at all"
    guarded = src.split("if ok:", 1)
    assert len(guarded) == 2, (
        "the progress is not conditional on anything having started -- a refusal would "
        "carry the previous switch's report"
    )
    assert "progress()" not in guarded[0], (
        "the progress is merged before the `started` test, so a refusal carries it"
    )


def test_the_post_dispatch_fails_by_name(live: Any) -> None:
    """A chain ends in a fallback and a fallback that looks deliberate is worse than a
    404. Design rule 16: an unknown path fails loudly, and the POST table is its own."""
    src = SERVE_PY.read_text()
    assert "def do_POST" in src, "nothing takes a POST; the base cannot be switched"
    body = src.split("def do_POST", 1)[1].split("\n    def ", 1)[0]
    assert "POST_ROUTES" in body, "do_POST does not route from the table"
    assert "send_error(404" in body, (
        "an unrouted POST does not fail by name -- design rule 16's whole argument"
    )


# ------------------------------------------------- the lock the switch rests on --- #


def test_every_route_reads_the_base_under_the_lock() -> None:
    """The invariant that makes closing the outgoing store safe.

    `open()` closes the previous connection at the moment it commits, which is only sound
    because no request can be holding it: every use of `current` happens inside
    `with self._live.lock`. A route that took the base out from under the lock and used it
    afterwards would be reading a connection the switch had already closed -- a crash that
    appears only when a reader switches while something else is in flight, which is exactly
    the case no test would think to write.

    Read with `ast`, not by grep: the prose in this file says `self._live.current` several
    times while explaining why, and a check that cries wolf is a check nobody reads
    (rule 43).
    """
    cls = _handler_source()
    outside = []
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        guarded: list[tuple[int, int]] = []
        for node in ast.walk(fn):
            if isinstance(node, ast.With):
                for item in node.items:
                    txt = ast.unparse(item.context_expr)
                    if txt.endswith("_live.lock"):
                        last = max((getattr(n, "lineno", node.lineno)
                                    for n in ast.walk(node)), default=node.lineno)
                        guarded.append((node.lineno, last))
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Attribute) and node.attr == "current"):
                continue
            if not ast.unparse(node).endswith("_live.current"):
                continue
            if not any(lo <= node.lineno <= hi for lo, hi in guarded):
                outside.append(f"{fn.name}:{node.lineno}")
    assert not outside, (
        f"the base is read outside the lock at {outside}. A switch commits and closes the "
        "outgoing store under that lock; a read outside it can hold a closed connection."
    )


def test_the_progress_never_waits_on_the_lock_the_rebuild_commits_under() -> None:
    """A poll that queued behind the rebuild would report nothing until there was nothing
    left to report -- which is the whole reason there are two locks."""
    src = inspect.getsource(serve_mod._Handler._r_base)
    assert "_live.progress()" in src, "the progress route does not report progress"
    body = src.split("_live.progress()", 1)[0]
    assert body.count("with self._live.lock") <= 1, (
        "the progress route takes the main lock more than once; the second would wait "
        "behind a ten-second rebuild"
    )
    assert "self.build_lock" in inspect.getsource(serve_mod._Live.progress), (
        "progress() does not use its own lock"
    )


def test_a_reader_can_ask_while_a_switch_is_running(live: Any) -> None:
    """The claim above, exercised rather than read off the source.

    `open()` builds outside the lock and commits inside it, so the ten seconds cost other
    requests nothing. Built from a real thread because the failure -- holding the lock for
    the build -- passes every source-reading check.
    """
    lv, out, _first, second = live
    free: list[bool] = []

    def watching(name: str, i: int, n: int) -> None:
        # Asked from inside the build itself, which is the only place the question means
        # anything. A separate thread would race the build of a tiny program and pass by
        # finishing first -- a guard that never runs against the case it names (rule 37).
        got = lv.lock.acquire(blocking=False)
        free.append(got)
        if got:
            lv.lock.release()

    lv.open(revisions.db_path(out, revisions.GRAPH, second), watching)
    assert free, "no step was reported; this guard never ran"
    assert all(free), (
        f"the lock was held for {free.count(False)} of {len(free)} build steps -- every "
        "other request would queue behind the whole rebuild"
    )


# ------------------------------------------------------------ opening a version --- #


def test_serve_opens_the_revision_it_was_asked_for() -> None:
    """`--revision` is where "which version does this server open" honestly lives.

    Without it a reader's chosen base cannot survive a restart of `serve` -- only a page
    reload -- and the alternative, a server reading the browser's stored settings, does not
    exist.
    """
    src = inspect.getsource(serve_mod.serve)
    assert "revisions.resolve(" in src, (
        "serve() no longer resolves a named revision; --revision would be a flag that "
        "renders and does nothing"
    )
    assert "revision" in inspect.signature(serve_mod.serve).parameters


def test_the_boot_and_a_switch_go_through_one_door() -> None:
    """Two builders would be two ways to produce one thing.

    The day they disagree, the map after a switch is not the map `serve` would have shown
    for that version -- and nothing on screen would say which of the two you were looking
    at (rule 51).
    """
    src = inspect.getsource(serve_mod.serve)
    assert "live.open(" in src, "serve() builds the base some other way than `open()`"
    for builder in ("columnar(", "build_files(", "measure_naming(", "bind_glossary(",
                    "build_cover("):
        assert builder not in src, (
            f"serve() calls {builder} itself -- a second way to build a base, beside the "
            "one a switch uses"
        )


def test_the_steps_are_named_once_and_counted_from_that_list(live: Any) -> None:
    """"Step 4 of 6" needs the 6 up front, and a hand-counted 6 beside a six-branch
    function is two numbers about one thing (rule 32).

    **Exercised, not read.** The first version of this collected `_step(N)` calls with
    `ast` and a mutation survived it: wrapping one in `if False:` leaves the call standing
    in the source, so a guard asking whether the call *appears* passed while the step was
    never reported. That is rule 59's companion pointed at the guard rather than at the
    mutation -- and the fix is not a cleverer read of the source, because reachability is
    not a thing a source read can answer. Run it and record what came out.
    """
    lv, out, _first, second = live
    assert len(serve_mod.BUILD_STEPS) >= 5
    seen: list[tuple[str, int, int]] = []
    lv.open(revisions.db_path(out, revisions.GRAPH, second),
            lambda name, i, n: seen.append((name, i, n)))

    assert [i for _n, i, _t in seen] == list(range(len(serve_mod.BUILD_STEPS))), (
        f"the steps reported were {[i for _n, i, _t in seen]} but there are "
        f"{len(serve_mod.BUILD_STEPS)} named -- the reader watches a count that skips"
    )
    assert [n for n, _i, _t in seen] == list(serve_mod.BUILD_STEPS), (
        "a step was reported under a name that is not its own"
    )
    assert {t for _n, _i, t in seen} == {len(serve_mod.BUILD_STEPS)}, (
        "the total a step reports is not the number of steps there are"
    )
