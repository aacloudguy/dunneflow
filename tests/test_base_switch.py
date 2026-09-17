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
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from dunneflow import revisions
from dunneflow.docstore import DocStore
from dunneflow.extractors.docs import extract_doc
from dunneflow.extractors.python.extract import extract_file
from dunneflow.sourcedb import DocSourceStore, SourceStore
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
    """A program directory with two revisions, as `analyze` would leave it.

    **With its documents**, because the base holds a `DocStore` now and a fixture with no
    `docs.db` would let every guard about that handle pass on a `None` — which is rule
    37's shape, a guard that cannot see the thing it is guarding. One document per
    revision is enough: what is being tested is the handle's lifetime, not the corpus.
    """
    out = tmp_path / "prog"
    out.mkdir()
    revs = []
    for i, source in enumerate((ONE, TWO)):
        tree = tmp_path / f"tree{i}"
        tree.mkdir()
        (tree / "m.py").write_text(source, encoding="utf-8")
        (tree / "README.md").write_text(
            f"# Revision {i}\n\nWhat this version is for.\n", encoding="utf-8")
        rev = f"2026-08-30T10:0{i}:00Z"
        store = Store(revisions.db_path(out, revisions.GRAPH, rev))
        store.write_file_facts(extract_file(tree / "m.py", tree))
        store.set_meta("revision", rev)
        store.conn.commit()
        store.close()
        docs = DocStore(revisions.db_path(out, revisions.DOCS, rev))
        docs.set_meta("revision", rev)
        docs.write_doc_facts(extract_doc(tree / "README.md", tree))
        docs.conn.commit()
        docs.close()
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
    tree = ast.parse(SERVE_PY.read_text(encoding="utf-8"))
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


def test_the_document_store_is_closed_by_the_switch_that_replaces_it() -> None:
    """A switch that leaks the document store leaks 148 MB per switch.

    **The leak is the same one; the close has moved.** It used to happen in a `finally`
    the moment the glossary lane was built, because `open()` runs on every switch and a
    handle held past it accumulated one store per version the reader visited. A document
    list cannot be served from a store that is already shut, so the handle is now a field
    of `_Base` and the *swap* closes the outgoing one — the lifetime is a version's
    instead of a statement's, and the leak is answered rather than avoided.

    Which makes this guard about three closes rather than one, because there are now three
    ways for the store to outlive the version that owns it: a build that raises after
    opening it, a swap that forgets the outgoing base, and a server that shuts down.
    """
    src = inspect.getsource(serve_mod._Live.open)
    assert "_docs_for(" in src, "the glossary no longer reads the version's own documents"

    tree = ast.parse(src.strip())
    # A build that raises after `_docs_for` returns must close what it opened. In the
    # handler, not a `finally`: the success path deliberately keeps it.
    closed_on_failure = any(
        "docs.close()" in ast.unparse(h)
        for n in ast.walk(tree) if isinstance(n, ast.Try) for h in n.handlers
    )
    assert closed_on_failure, (
        "a build that fails after opening the document store never closes it — the switch "
        "that did not happen costs more than the one that did"
    )
    assert "docs=docs" in ast.unparse(tree).replace(" ", ""), (
        "`open()` no longer hands the document store to the base, so nothing owns it"
    )

    swap = inspect.getsource(serve_mod._Live.open)
    assert "outgoing.docs" in swap, (
        "the swap closes the outgoing graph store and not its document store — the "
        "per-switch leak, moved rather than fixed"
    )
    assert "docs.close()" in inspect.getsource(serve_mod._Live.close), (
        "shutting the server down leaves the current version's document store open"
    )


def test_a_switch_closes_the_outgoing_document_store(live: Any) -> None:
    """The same claim exercised, because reading it off the source is not seeing it happen.

    A closed sqlite connection refuses the next query by name, so the outgoing handle is
    asked one question after the switch. Rule 37: a guard that checks a close *appears*
    has not checked that anything was closed.
    """
    import sqlite3

    lv, out, _first, second = live
    outgoing = lv.current.docs
    assert outgoing is not None, "the fixture's program has no documents; guard is blind"
    lv.open(revisions.db_path(out, revisions.GRAPH, second))
    assert lv.current.docs is not outgoing, "the switch carried the old document store over"
    with pytest.raises(sqlite3.ProgrammingError):
        outgoing.query("SELECT COUNT(*) n FROM documents")


def test_a_refusal_carries_no_progress_because_nothing_is_running() -> None:
    """Three fields about three different things under one answer.

    A refusal used to merge the live progress report, so declining a switch to a version
    with no graph replied `started: false` beside `state: "done"` and the **previous**
    switch's revision. Rule 13: the answer beside a claim has to be about that claim. A
    refusal is about the request, and there is no progress to report because nothing has
    started.

    **On the merge, not on a spelling.** This asked for the literal `progress()` until the
    slot became the caller's -- `(progress or self._live.progress)()`, so an analysis can
    report its own -- and then failed saying the route carried no progress at all, which
    was true of no version of the code. The invariant is that the *merge* happens under
    `if ok:`, whichever slot is being read; naming the merge is what makes this survive a
    third caller (rule 43: a check that cries wolf has already failed).
    """
    src = inspect.getsource(serve_mod._Handler._started)
    assert "body.update(" in src, "the started answer carries no progress at all"
    guarded = src.split("if ok:", 1)
    assert len(guarded) == 2, (
        "the progress is not conditional on anything having started -- a refusal would "
        "carry the previous switch's report"
    )
    assert "body.update(" not in guarded[0], (
        "the progress is merged before the `started` test, so a refusal carries it"
    )


def test_the_post_dispatch_fails_by_name(live: Any) -> None:
    """A chain ends in a fallback and a fallback that looks deliberate is worse than a
    404. Design rule 16: an unknown path fails loudly, and the POST table is its own."""
    src = SERVE_PY.read_text(encoding="utf-8")
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


# The stores `_Live` holds open across requests, every one of them `shared=True` -- which
# is `check_same_thread=False` and, in `sourcedb.py`'s own words, "a lock owed by the
# caller". The base is not in here: it has its own guard above, which watches `current`.
SHARED_SIDECARS = ("source", "docsource", "standards")


def _lock_spans(fn: ast.FunctionDef) -> list[tuple[int, int]]:
    """The line ranges of every `with self._live.lock` in one handler."""
    spans = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            if ast.unparse(item.context_expr).endswith("_live.lock"):
                last = max((getattr(n, "lineno", node.lineno) for n in ast.walk(node)),
                           default=node.lineno)
                spans.append((node.lineno, last))
    return spans


def test_no_route_queries_a_shared_sidecar_outside_the_lock() -> None:
    """The guard above watches the *attribute*; this one watches the *use*.

    `_r_about` took `sidecar = self._live.source` inside the lock and called
    `sidecar.revisions()` after the block closed. Both guards were blind to it: the one
    above only looks at `current`, and it looks at where a store is *read* rather than
    where it is *used*, so an alias carried past the `with` is invisible to it.

    What that cost was a false sentence rather than a crash, which is why nothing noticed.
    `ThreadingHTTPServer` ran `/api/about` and `/api/revisions` -- which the shell fires
    back to back at boot -- over one connection at once; `revisions()` came back wrong, no
    row matched the served revision, and the topbar printed *"no sidecar here to ask"* over
    a map whose sidecar holds the tree name. A plausible answer that consumed its own
    evidence (rule 49), and the one sentence on that control that must never be guessed.

    Passing a store *into* something is not a use: `_r_source` and `_r_docsource` hand
    `self._live.source` to `_span`, which takes the lock itself. Only a call **on** the
    store is counted, which is the line between the defect and its two innocent neighbours.
    """
    cls = _handler_source()
    outside = []
    for fn in cls.body:
        if not isinstance(fn, ast.FunctionDef):
            continue

        guarded = _lock_spans(fn)

        # Locals bound from one of those stores, so an alias is followed rather than
        # trusted -- the whole hiding place the defect used.
        aliases: dict[str, str] = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target, value = node.targets[0], ast.unparse(node.value)
                if isinstance(target, ast.Name) and any(
                        value.endswith(f"_live.{s}") for s in SHARED_SIDECARS):
                    aliases[target.id] = value

        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            owner = node.func.value
            named = (aliases.get(owner.id) if isinstance(owner, ast.Name)
                     else ast.unparse(owner) if any(
                         ast.unparse(owner).endswith(f"_live.{s}")
                         for s in SHARED_SIDECARS) else None)
            if named and not any(lo <= node.lineno <= hi for lo, hi in guarded):
                outside.append(f"{fn.name}:{node.lineno} {named}.{node.func.attr}()")

    assert not outside, (
        f"a shared sidecar is queried outside the lock at {outside}. Every one of these "
        "stores is opened `shared=True`, so two requests can reach one sqlite connection "
        "at once -- and the answer comes back wrong rather than raising."
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


# --------------------------------------------------------------------------- #
# Switching program
#
# The same shape as a revision switch and a wider blast radius. The ratified
# design had this control with three options and no change handler even there;
# the port carried the markup and never built the endpoint. What follows is the
# part that is not a mirror image: the caches, and the sidecars.
# --------------------------------------------------------------------------- #

@pytest.fixture()
def two_programs(tmp_path: Path) -> Any:
    """Two program directories under one root, as `--output` leaves them.

    **Their newest graphs share a basename on purpose.** `findings` is keyed on
    `graph_db.name`, so this is the collision the cache list exists for, and a fixture
    that gave them different revisions would let a broken fix pass.
    """
    root = tmp_path / "output"
    made = []
    for name in ("alpha", "beta"):
        out = root / name
        out.mkdir(parents=True)
        tree = tmp_path / f"src-{name}"
        tree.mkdir()
        (tree / "m.py").write_text(ONE if name == "alpha" else TWO, encoding="utf-8")
        (tree / "README.md").write_text(f"# {name}\n\nProse for {name}.\n", encoding="utf-8")
        rev = "2026-08-30T10:00:00Z"                      # the same, deliberately
        store = Store(revisions.db_path(out, revisions.GRAPH, rev))
        store.write_file_facts(extract_file(tree / "m.py", tree))
        store.set_meta("revision", rev)
        store.conn.commit()
        store.close()
        docs = DocStore(revisions.db_path(out, revisions.DOCS, rev))
        docs.set_meta("revision", rev)
        docs.write_doc_facts(extract_doc(tree / "README.md", tree))
        docs.conn.commit()
        docs.close()
        made.append(out)
    lv = serve_mod._Live(made[0] / "source.db", made[0])
    lv.open(revisions.db_path(made[0], revisions.GRAPH, "2026-08-30T10:00:00Z"))
    try:
        yield lv, root, made[0], made[1]
    finally:
        lv.close()


def test_a_program_switch_clears_every_cache(two_programs: Any) -> None:
    """Not a superset of the revision switch's list — a different question.

    `findings` and `filepairs` survive a revision switch deliberately, both because they
    are keyed on one thing rather than on a pair. Neither key is safe across programs:
    `findings` is keyed on `graph_db.name`, a **basename** two directories share, and
    `filepairs` on revision strings that two unrevisioned directories both render `("",
    "")`. Serving one program's anomalies for another is what this prevents.
    """
    lv, _root, _alpha, beta = two_programs
    for cache in serve_mod._Live.PROGRAM_CACHES:
        getattr(lv, cache)["poisoned"] = ["from the program we are leaving"]
    lv.switch_program(beta, "beta")
    assert lv.progress()["state"] == "done", lv.progress()
    for cache in serve_mod._Live.PROGRAM_CACHES:
        assert not getattr(lv, cache), (
            f"`{cache}` survived a program switch — its keys are shared between programs, "
            "so the next read serves the program you just left"
        )


def test_the_two_cache_lists_are_stated_separately(two_programs: Any) -> None:
    """One is not a slice of the other, and a reader must see both answers.

    Rule 36 cuts both ways: a generic loop narrowed to a literal loses a feature silently,
    and a second switch reusing the first switch's literal keeps a stale cache just as
    silently. The two that differ are named here so a third switch cannot quietly adopt
    the wrong list.
    """
    kept = set(serve_mod._Live.PROGRAM_CACHES) - set(serve_mod._Live.COMPARISON_CACHES)
    assert kept == {"findings", "filepairs"}, (
        f"the lists no longer differ by exactly the per-graph caches: {kept}"
    )


def test_a_program_switch_repoints_the_sidecars(two_programs: Any) -> None:
    """A program's bodies are that program's, and they are not part of `_Base`.

    They live on `_Live` because a *revision* switch does not change them. A program
    switch does, and forgetting it would serve one program's source under another's map —
    the same class of mistake as rule 70, one axis over.
    """
    lv, _root, alpha, beta = two_programs
    assert lv.out_dir == alpha
    lv.switch_program(beta, "beta")
    assert lv.out_dir == beta, "the output directory did not follow the switch"
    assert lv.current.store.path.parent == beta, "the base was built from the old directory"


def test_a_failed_program_switch_leaves_the_old_one_serving(
        two_programs: Any, tmp_path: Path) -> None:
    """The important failure, because the alternative takes the dashboard down.

    Nothing is closed or repointed until `open()` has returned a base built from the new
    directory, so a stale program, a missing graph or a schema bump leaves the reader
    looking at what they had — with the reason in the progress report (rule 20).
    """
    lv, _root, alpha, _beta = two_programs
    empty = tmp_path / "output" / "gamma"
    empty.mkdir(parents=True)
    before = lv.current
    lv.switch_program(empty, "gamma")
    report = lv.progress()
    assert report["state"] == "failed", report
    assert "gamma" in report.get("reason", ""), report
    assert lv.current is before, "a failed switch replaced the base it could not build"
    assert lv.out_dir == alpha, "a failed switch left the output directory pointing away"
    # The store the reader is still looking at must be usable, not a closed handle.
    assert lv.current.store.query("SELECT 1 AS n")[0]["n"] == 1


def test_a_switch_that_fails_inside_the_build_puts_the_program_back(
        two_programs: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The other failure, and the one that reaches further into the method.

    A directory with **no graph at all** is refused before anything is repointed, so it
    never exercises the restore — the first version of this pair tested only that, and a
    mutation deleting the whole `self.out_dir, ... = was` line passed. This one has a graph
    that cannot be opened, so the build fails *after* the fields have been moved and the
    restore is the only thing that puts them back (rule 37: the guard has to reach the code).
    """
    lv, _root, alpha, _beta = two_programs
    broken = tmp_path / "output" / "delta"
    broken.mkdir(parents=True)
    # A file where a graph should be, which is what a truncated copy or an interrupted
    # analyse leaves behind. **With a real sidecar beside it**, so the switch genuinely
    # opens a handle before it fails — without one there is nothing to leak and the guard
    # below would pass against code that leaks every time.
    # `as_filename`'s spelling, with the colons replaced, because that is the only name
    # `analyze` can have left here -- and the colons are illegal in a Windows filename, so a
    # fixture carrying them tests the harness rather than the switch (rule 24).
    (broken / "graph@2026-08-30T10-00-00Z.db").write_text(
        "not a database at all", encoding="utf-8")
    SourceStore(broken / "source.db").close()

    opened: list[Any] = []
    real = serve_mod._Live._open_source

    def capture(path: Path) -> Any:
        got = real(path)
        if got is not None:
            opened.append(got)
        return got

    monkeypatch.setattr(serve_mod._Live, "_open_source", staticmethod(capture))
    before, before_source = lv.current, lv.source
    lv.switch_program(broken, "delta")
    assert lv.progress()["state"] == "failed", lv.progress()
    assert lv.current is before, "a failed build replaced the base"
    assert lv.out_dir == alpha, (
        "the output directory stayed pointed at the program that could not be opened, so "
        "every revision and sidecar lookup now answers for a map nobody is serving"
    )
    assert lv.source is before_source, "the sidecar was left repointed by a failed switch"
    assert lv.current.store.query("SELECT 1 AS n")[0]["n"] == 1
    # **And the handle it opened and abandoned is closed.** The field being put back is
    # only half of it: a sidecar opened for a program nobody ends up serving is a file
    # descriptor on a store with no reader, and one per failed switch. Captured through the
    # opener because the store itself is a local inside `switch_program` and there is no
    # other way to reach it.
    assert opened, "no sidecar was opened, so this guard proves nothing about closing one"
    with pytest.raises(sqlite3.ProgrammingError):
        opened[-1].conn.execute("SELECT 1")


def test_the_program_routes_refuse_by_name() -> None:
    """Four refusals, as `_p_base` has four. "Nothing happened" is not an answer."""
    src = inspect.getsource(serve_mod._Handler._p_program)
    for reason in ("no program was named", "beside this one",
                   "already the program being read", "already running"):
        assert reason in src, f"the switch cannot say “{reason}”"
    # **A name is looked up, never joined onto a path.** `output/../../etc` must address
    # nothing; the list of siblings is the authority on what may be switched to (rule 30).
    assert "candidates.get(asked)" in src, (
        "the asked-for name is turned into a directory by construction rather than by "
        "lookup, so a name carrying a separator addresses a directory outside the root"
    )


def test_switching_program_is_a_post_like_switching_version() -> None:
    """A GET that swaps the whole map is one a prefetch fires by itself.

    The **tables**, not a string somewhere in the class: the first version of this guard
    looked for `_p_program` anywhere among the handler's string constants, which the POST
    table's own value satisfies whatever path it is filed under — so renaming the route to
    `/api/programx` passed it. Rule 37, one line long.
    """
    assert serve_mod._Handler.POST_ROUTES.get("/api/program") == "_p_program", (
        "the program switch is not reachable as a POST at the path the client asks for"
    )
    assert "/api/program" not in serve_mod._Handler.ROUTES, (
        "the program switch is reachable by GET, so a browser prefetch can swap the map"
    )
    assert serve_mod._Handler.ROUTES.get("/api/programs") == "_r_programs", (
        "the list is not a GET"
    )


def test_a_close_clears_every_cache(two_programs: Any) -> None:
    """A close is a program switch whose destination is *no program*, so the same list goes.

    **Poisoned first, and that is not decoration.** The obvious spelling of this test — open
    something, close it, assert the caches are empty — passes over a `close_program` that
    clears nothing at all, because nothing in that sequence ever *fills* a cache: `findings`
    is only populated when somebody asks for anomalies. A check that cannot fail has already
    failed, and it fails silently (rule 43). Caught by mutating `close_program` and watching
    the first version of this stay green.

    The keys are the reason, and they are `switch_program`'s: `findings` is keyed on
    `graph_db.name`, a basename two program directories share, and `filepairs` on `("", "")`
    for any pair of unrevisioned ones. After a close the next thing opened may be any program
    under the root, so every key that does not name one is unsafe.
    """
    lv, _root, alpha, _beta = two_programs
    lv.switch_program(alpha, "alpha")
    assert lv.progress()["state"] == "done", lv.progress()
    for cache in serve_mod._Live.PROGRAM_CACHES:
        getattr(lv, cache)["poisoned"] = ["from the program we are putting down"]

    lv.close_program()

    assert lv.opened is False
    for cache in serve_mod._Live.PROGRAM_CACHES:
        assert not getattr(lv, cache), (
            f"`{cache}` survived a close — its keys are shared between programs, so the "
            "next program opened is served what the one you closed left behind"
        )


def test_a_close_leaves_no_sidecar_open_and_returns_out_dir_to_the_root(
        two_programs: Any) -> None:
    """All **three** sidecars, and the third is the one that keeps getting missed.

    `standards` joined `source` and `docsource` when `--standards` arrived; it was added to
    `switch_program`'s `was` tuple and to the swap, and to neither of its two closes — so
    every program switch leaked a `standards.db` handle, invisibly, because a leaked
    read-only SQLite handle costs nothing a reader can see. The sidecars are a set of three
    and anything enumerating two of them has fallen behind (rule 36).
    """
    lv, root, alpha, _beta = two_programs
    # **The fixture's programs have no sidecars, and a leak cannot show through a `None`.**
    # All three are built here so `switch_program` has three real handles to hand over --
    # without them this test passes over any close at all, which is the failure mode the
    # comment below is about, one level further out.
    SourceStore(alpha / "source.db").close()
    DocSourceStore(alpha / "docsource.db").close()
    DocStore(alpha / serve_mod.STANDARDS_DB).close()

    lv.switch_program(alpha, "alpha")
    assert lv.progress()["state"] == "done", lv.progress()

    # **Held before the close, because the field going `None` is not the handle shutting.**
    # The first version of this asserted only `lv.standards is None` and passed happily over
    # a `close_program` that dropped the reference without closing it -- which is precisely
    # the leak being guarded against, since a leaked read-only SQLite handle has no symptom
    # (rule 43: a check that cannot fail has already failed). What is asserted is that the
    # connection refuses to work afterwards.
    held = [s for s in (lv.source, lv.docsource, lv.standards) if s is not None]
    assert len(held) == 3, f"the fixture opened {len(held)} sidecars, not three"

    lv.close_program()

    assert (lv.source, lv.docsource, lv.standards) == (None, None, None)
    for store in held:
        with pytest.raises(sqlite3.ProgrammingError):
            store.conn.execute("SELECT 1")
    # `where()` returns `(root, root)` for a directory holding no map, and `serve()` tests
    # that equality to decide it is cold. A close that left `out_dir` in the program
    # directory would leave a base-shaped hole rather than the start state.
    assert lv.out_dir == lv.out_root == root


def test_a_program_switch_closes_all_three_of_the_outgoing_sidecars(
        two_programs: Any) -> None:
    """The leak this was written from, and it had been there since `--standards` landed.

    `switch_program` captures `was = (out_dir, source, docsource, standards)` — four — and
    then closed `(was[1], was[2])`. Three sidecars in, two out, so **every program switch
    left one `standards.db` handle open**, on both the success path and the failure path.
    It had no symptom: a leaked read-only SQLite handle costs nothing a reader can see until
    a session has done it a few hundred times, and nothing counts them.

    Found by writing `close_program` beside it. That is rule 36's warning arriving as it
    usually does — not as a loop narrowed to a literal, but as a list that stopped agreeing
    with the tuple above it — and the fix is `was[1:]`, which cannot fall behind again.

    Asserted on the **connections**, never on the fields: `switch_program` repoints those to
    the incoming program either way, so a field check passes over the leak (rule 43).
    """
    lv, _root, alpha, beta = two_programs
    for out in (alpha, beta):
        SourceStore(out / "source.db").close()
        DocSourceStore(out / "docsource.db").close()
        DocStore(out / serve_mod.STANDARDS_DB).close()

    lv.switch_program(alpha, "alpha")
    assert lv.progress()["state"] == "done", lv.progress()
    outgoing = [s for s in (lv.source, lv.docsource, lv.standards) if s is not None]
    assert len(outgoing) == 3, f"alpha opened {len(outgoing)} sidecars, not three"

    lv.switch_program(beta, "beta")
    assert lv.progress()["state"] == "done", lv.progress()

    # Every one of alpha's handles is shut, and beta's three are live in their place.
    for store in outgoing:
        with pytest.raises(sqlite3.ProgrammingError):
            store.conn.execute("SELECT 1")
    assert len([s for s in (lv.source, lv.docsource, lv.standards) if s is not None]) == 3
