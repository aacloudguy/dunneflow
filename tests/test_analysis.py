"""Running an analysis from the server: the one thing the dashboard does that is a write.

Every other route under `web/` reads a store this process opened `writable=False`, because
rule 20 says serving may refuse but may never repair. This one starts `dunneflow analyze`
in a **subprocess**, so that posture is kept by construction rather than by care.

Each test here is a way it can go wrong while looking right:

  - a refusal that does not say which refusal it is, so the reader guesses;
  - a name that leaves the output root, or one that lands on the graph this server is
    holding open -- which `Store._discard_if_stale` would then empty under a live reader;
  - an analysis taking the slot a *switch* uses, so reading another tree locks the reader
    out of changing versions for ninety seconds;
  - a child that dies and a panel that says "working" for ever;
  - a GET that starts one, which is rule 20's shape with a filesystem behind it.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from dunneflow import revisions
from dunneflow.cli import (
    ALL_STEPS,
    analysis_steps,
    build_parser,
    cmd_check,
    cmd_query,
)
from dunneflow.store import StaleGraphError, Store, UnfinishedMapError
from dunneflow.web import analysis
from dunneflow.web import serve as serve_mod

SERVE_PY = Path(serve_mod.__file__)

TINY = '''\
"""A program small enough to read in a test."""
import sqlite3


def open_it(path):
    return sqlite3.connect(path)
'''


@pytest.fixture()
def world(tmp_path: Path) -> Any:
    """An output root holding one served program, and a source tree beside it."""
    root = tmp_path / "output"
    serving = root / "served"
    serving.mkdir(parents=True)
    rev = "2026-08-30T10:00:00Z"
    store = Store(revisions.db_path(serving, revisions.GRAPH, rev))
    store.set_meta("revision", rev)
    store.conn.commit()
    store.close()

    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "m.py").write_text(TINY)
    return root, serving, tree


# ------------------------------------------------- every refusal, by its own name --- #


def test_each_refusal_says_which_one_it_is(world: Any) -> None:
    """Seven ways to be told no, and seven different sentences.

    "Nothing happened" and "that would overwrite what you are reading" are different
    answers, and a reader who has to guess which they got will guess wrong about the one
    that matters. The assertion is on the *words* rather than on a boolean, because a
    boolean is what a reader cannot act on.
    """
    root, serving, tree = world
    cases = {
        "": "no directory was named",
        "relative/path": "relative path",
        str(tree / "nope"): "does not exist",
        str(tree / "m.py"): "is a file",
        str(root): "inside the output root",
    }
    seen = []
    for path, expected in cases.items():
        v = analysis.check(path, "", root, serving)
        assert not v.ok, f"{path!r} was allowed"
        assert expected in v.refusal, f"{path!r} said {v.refusal!r}"
        seen.append(v.refusal)

    bad_name = analysis.check(str(tree), "../escape", root, serving)
    assert not bad_name.ok and "not a name a directory can have" in bad_name.refusal
    seen.append(bad_name.refusal)

    served = analysis.check(str(tree), "served", root, serving)
    assert not served.ok and "the program being read" in served.refusal
    seen.append(served.refusal)

    assert len(set(seen)) == len(seen), f"two refusals share a sentence: {seen}"


def test_the_served_program_is_refused_because_its_graph_is_open_here(world: Any) -> None:
    """Not caution, and the sentence has to carry the reason.

    `Store._discard_if_stale` drops every table of a graph written by another build of
    DunneFlow, and this server is holding that graph open. An analysis aimed at the served
    directory can therefore empty the map under a live reader -- so the refusal names what
    would happen, not merely that it may not.
    """
    root, serving, tree = world
    v = analysis.check(str(tree), "served", root, serving)
    assert not v.ok
    assert "discard" in v.refusal and "re-extract" in v.refusal, v.refusal
    # **The sentence has to stay true of the code it describes.** If `_discard_if_stale`
    # ever stops dropping tables, this refusal is telling the reader something that is no
    # longer so -- and a refusal nobody can justify is one somebody will remove.
    store_src = Path(sys.modules[Store.__module__].__file__ or "").read_text()
    dropper = store_src.split("def _discard_if_stale", 1)
    assert len(dropper) == 2, "_discard_if_stale is gone; this refusal has lost its reason"
    assert "DROP TABLE" in dropper[1].split("\n    def ", 1)[0], (
        "_discard_if_stale no longer drops tables, so the refusal's reason is stale"
    )


def test_a_name_that_already_exists_is_allowed_and_says_what_it_will_do(
        world: Any) -> None:
    """A note, not a refusal -- and the difference is the whole of Tom's call here.

    `analyze` reuses the working revision, so analysing into an existing directory
    **replaces** that snapshot rather than adding one beside it. That is a surprise, not
    an error, and design rule 1 says a thing that will happen is stated rather than
    silently done.
    """
    root, serving, tree = world
    other = root / "other"
    other.mkdir()
    rev = "2026-08-30T11:00:00Z"
    store = Store(revisions.db_path(other, revisions.GRAPH, rev))
    store.close()

    v = analysis.check(str(tree), "other", root, serving)
    assert v.ok, f"an existing name was refused: {v.refusal}"
    assert "rewrites its working snapshot" in v.note, v.note

    fresh = analysis.check(str(tree), "brandnew", root, serving)
    assert fresh.ok and not fresh.note, (
        f"a name nothing holds carries a warning: {fresh.note!r}"
    )


def test_a_file_where_the_directory_would_go_is_refused_before_the_child_sees_it(
        world: Any) -> None:
    """A pre-flight sentence instead of a fourteen-line traceback.

    Found by driving it: `output/blocked` as an ordinary file got through `check`, and the
    child reported `FileExistsError` under thirteen frames of `runpy`. True, and not a
    thing the reader this tool is written for can act on.
    """
    root, serving, tree = world
    (root / "blocked").write_text("")
    v = analysis.check(str(tree), "blocked", root, serving)
    assert not v.ok
    assert "already sitting where that program's directory would go" in v.refusal


def test_a_reason_leads_with_the_childs_last_line(world: Any) -> None:
    """A traceback says the useful thing last, and the panel shows the top first.

    Nothing invented and nothing dropped: the child's own final line is promoted, and
    everything it said stays underneath as the evidence for it.
    """
    root, _serving, _tree = world
    seen: list[dict[str, Any]] = []

    class Loud:
        stdout = iter(())
        stderr = iter(["Traceback (most recent call last):\n",
                       "  File \"x.py\", line 1, in <module>\n",
                       "FileExistsError: [Errno 17] File exists: 'output/blocked'\n"])

        def wait(self) -> int:
            return 1

    analysis.run(Path("/x"), "n", root, docs=False,
                 note=lambda **f: seen.append(f), popen=lambda *a, **k: Loud())
    reason = seen[-1]["reason"]
    assert reason.startswith("FileExistsError: [Errno 17]"), reason
    assert "Traceback (most recent call last):" in reason, (
        "the evidence for the promoted line was dropped"
    )


def test_a_blank_name_borrows_the_directorys_own(world: Any) -> None:
    """The placeholder the dialog shows is the rule the server actually applies."""
    root, _serving_dir, tree = world
    assert analysis.check(str(tree), "", root, root / "served").ok

    # Serving a program named after the tree's own leaf: a blank name must resolve to that
    # leaf and hit the served-program refusal. If it did not resolve, this would be allowed
    # and the analysis would land on the graph this server is holding open.
    clash = analysis.check(str(tree), "", root, root / tree.name)
    assert not clash.ok, "a blank name did not resolve to the directory's leaf"
    assert "the program being read" in clash.refusal, clash.refusal


# --------------------------------------------------------- what the child is told --- #


def test_the_child_is_run_with_both_channels_separated(world: Any) -> None:
    """`--progress-json --quiet`, and the reason is that there are two channels.

    stdout is the machine channel and stderr is where a failure says why. `--quiet` empties
    the prose so the second holds a real failure and nothing else; without it a reason is
    forty lines of ordinary progress with the traceback somewhere inside.
    """
    root, _serving, tree = world
    cmd = analysis.argv(tree, "n", root, docs=True)
    assert cmd[:3] == [sys.executable, "-m", "dunneflow.cli"], cmd[:3]
    assert "analyze" in cmd and "--progress-json" in cmd and "--quiet" in cmd
    assert "--no-docs" not in cmd
    assert "--no-docs" in analysis.argv(tree, "n", root, docs=False)


def test_the_step_count_is_what_this_run_will_actually_do() -> None:
    """A total the run cannot reach is a bar that stops at five of seven.

    Four flags remove work, so the list is computed for the run rather than declared once
    (rule 32). This is the guard on that: every flag that skips a step has to shorten it.
    """
    def ns(**kw: Any) -> Any:
        base = dict(no_docs=False, no_doc_source=False, no_source=False, no_render=False)
        base.update(kw)
        return type("A", (), base)()

    full = analysis_steps(ns())
    assert len(full) == 7, full
    assert len(analysis_steps(ns(no_docs=True))) == 5
    assert len(analysis_steps(ns(no_doc_source=True))) == 6
    assert len(analysis_steps(ns(no_source=True))) == 6
    assert len(analysis_steps(ns(no_render=True))) == 6
    assert set(full) <= ALL_STEPS, "a step was minted outside the declared set"


def test_the_machine_channel_is_parseable_and_ends_by_saying_it_finished(
        world: Any, tmp_path: Path) -> None:
    """The whole contract, over a real analysis of a real (tiny) tree.

    Every line an object, every step named from the declared list, the count constant
    across the run, and a final `done` carrying what was read. A run that ends without
    that last object is reported as a failure by `run` below, and this is what makes that
    a real outcome rather than a defensive branch.
    """
    root, _serving, tree = world
    out = subprocess.run(analysis.argv(tree, "made", root, docs=False),
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr
    lines = [json.loads(x) for x in out.stdout.splitlines() if x.strip()]
    assert lines, f"nothing on the machine channel; stderr was {out.stderr!r}"
    assert all(isinstance(x, dict) for x in lines)
    # One total for the whole run. A count that moves is a bar that jumps backwards, and
    # it is what a step list assembled per-phase rather than up front would produce.
    assert len({x["steps"] for x in lines}) == 1, (
        f"the total moved mid-run: {sorted({x['steps'] for x in lines})}"
    )
    # And it is the total for *these* flags -- `--no-docs`, so five.
    assert lines[0]["steps"] == 5, lines[0]
    named = {x["step"] for x in lines if x["step"]}
    assert named <= ALL_STEPS, f"a step nobody declared: {named - ALL_STEPS}"
    assert lines[-1]["state"] == "done", lines[-1]
    assert lines[-1]["files"] == 1 and lines[-1]["routines"] >= 1, lines[-1]
    assert revisions.newest(root / "made", revisions.GRAPH) is not None


# ------------------------------------------------------------- reported, not raised --- #


def test_a_child_that_fails_is_reported_with_its_own_words(world: Any) -> None:
    """A failure is a report, never an exception into a thread nobody is reading.

    The reader asked for this and is watching a panel; a run that ends by writing a
    traceback to a terminal, leaving the panel saying "working" for ever, is the same
    defect as a spinner that never stops. `_Live.switch` carries the rule one subject over.
    """
    root, _serving, _tree = world
    seen: list[dict[str, Any]] = []
    analysis.run(Path("/definitely/not/here"), "nope", root, docs=False,
                 note=lambda **f: seen.append(f))
    assert seen, "a failed analysis reported nothing at all"
    assert seen[-1]["state"] == "failed"
    assert "does not exist" in seen[-1]["reason"], seen[-1]["reason"]


def test_a_child_that_exits_clean_without_finishing_is_a_failure(world: Any) -> None:
    """Exit 0 and no `done` object means the contract was not met.

    Reporting a success this never saw would be rule 49 exactly: a plausible value that
    has hidden the failure the code was written for.
    """
    root, _serving, _tree = world
    seen: list[dict[str, Any]] = []

    class Quiet:
        stdout = iter(())
        stderr = iter(())

        def wait(self) -> int:
            return 0

    analysis.run(Path("/x"), "n", root, docs=False,
                 note=lambda **f: seen.append(f), popen=lambda *a, **k: Quiet())
    assert seen[-1]["state"] == "failed"
    assert "without saying it had finished" in seen[-1]["reason"]


def test_the_last_word_belongs_to_the_process_that_did_the_work(world: Any) -> None:
    """`run` adds no `done` of its own, and this is why.

    It used to append one, which replaced the child's -- five of five steps, then zero of
    zero, and every count gone. The report a reader ends up looking at has to be the one
    that knows what happened (rule 51).
    """
    root, _serving, _tree = world
    seen: list[dict[str, Any]] = []

    class Fake:
        stdout = iter([json.dumps({"state": "working", "step": "reading the source tree",
                                   "done_steps": 0, "steps": 2}) + "\n",
                       "not json at all\n",
                       json.dumps({"state": "done", "done_steps": 2, "steps": 2,
                                   "routines": 41}) + "\n"])
        stderr = iter(())

        def wait(self) -> int:
            return 0

    analysis.run(Path("/x"), "n", root, docs=False,
                 note=lambda **f: seen.append(f), popen=lambda *a, **k: Fake())
    assert seen[-1] == {"state": "done", "done_steps": 2, "steps": 2, "routines": 41,
                        "program": "n"}, seen[-1]
    assert len(seen) == 2, f"the unparseable line was not skipped: {seen}"


# ------------------------------------------------------------------- the two slots --- #


def test_an_analysis_does_not_take_the_slot_a_switch_uses() -> None:
    """The whole reason the panel is not the switch overlay.

    One slot would mean a ninety-second read of an unrelated tree locking the reader out
    of changing versions -- for work that replaces nothing on screen. Both directions,
    because a superset expression would satisfy one of them and not the other (rule 36).
    """
    lv = serve_mod._Live.__new__(serve_mod._Live)
    import threading
    lv.build_lock = threading.Lock()
    lv.build = {"state": "idle"}
    lv.analysis_lock = threading.Lock()
    lv.analysis = {"state": "idle"}
    lv.analysis_proc = None

    lv.analysis_proc = _Alive()
    assert lv.claim_analysis("a") is False, "a live analysis did not hold its own slot"
    assert lv.claim("some-revision") is True, (
        "an analysis blocked a version switch -- they are one slot"
    )
    assert lv.progress()["revision"] == "some-revision"


class _Alive:
    """A child that has not exited. `poll()` returning None is the whole contract."""

    def poll(self) -> None:
        return None


class _Gone:
    """A child that has. This is what a stale lock looks like from the outside."""

    def poll(self) -> int:
        return 0


def test_one_analysis_at_a_time_while_one_is_actually_running() -> None:
    """Two reading into one output root can collide on a directory, and the panel shows one.

    Asserted against a **live process**, because that is now what holds the slot -- the
    report's own word does not, and the test below is why.
    """
    lv = serve_mod._Live.__new__(serve_mod._Live)
    import threading
    lv.analysis_lock = threading.Lock()
    lv.analysis = {"state": "idle"}
    lv.analysis_proc = _Alive()
    assert lv.claim_analysis("b") is False, "two analyses claimed the same slot"


def test_a_report_that_outlived_its_process_is_a_stale_lock_and_is_cleared() -> None:
    """**The jam Tom asked about, and the reason the slot asks the child.**

    `state == "working"` is a label, and a label outlives the thing it names: a watcher
    that dies without noting leaves it true for ever, and nothing short of restarting the
    server could then start another analysis. Rule 30, in the one place a reader cannot
    argue with it -- they can see nothing is running and still be refused.

    So the claim asks the process. A report still saying `working` over a child that has
    gone is cleared here rather than left for somebody to notice.
    """
    lv = serve_mod._Live.__new__(serve_mod._Live)
    import threading
    lv.analysis_lock = threading.Lock()
    lv.analysis_proc = _Gone()
    lv.analysis = {"state": "working", "program": "wedged", "step": "the glossary",
                   "began": 1.0, "moved": 1.0}

    assert lv.analysis_running() is False, "an exited child is reported as running"
    assert lv.claim_analysis("next") is True, (
        "a report that outlived its process held the slot -- the reader is locked out of "
        "a feature by a label, with nothing running to point at"
    )
    assert lv.analysis_proc is None, "the dead child was kept after its slot was reused"
    assert lv.analysis["program"] == "next"


def test_stopping_when_nothing_runs_says_so_rather_than_pretending() -> None:
    """`started: false` and a reason, like every other refusal on this server."""
    lv = serve_mod._Live.__new__(serve_mod._Live)
    import threading
    lv.analysis_lock = threading.Lock()
    lv.analysis = {"state": "idle"}
    lv.analysis_proc = _Gone()
    assert lv.stop_analysis() == (False, "no analysis is running")


def test_the_analysis_report_is_replaced_whole_except_its_clock() -> None:
    """`note`'s rule, one slot over: a half-updated report is a state a reader can see.

    **Two fields are carried on purpose and everything else is replaced**, which is a
    narrower claim than this test used to make and the narrower one is the true one.
    `began` has to survive or the panel cannot say how long a run has been going; `moved`
    has to survive *an unchanged report* or a silence detector that is refreshed by being
    watched would never report silence at all. Everything the child actually said is
    replaced whole.
    """
    lv = serve_mod._Live.__new__(serve_mod._Live)
    import threading
    lv.analysis_lock = threading.Lock()
    lv.analysis_proc = None
    lv.analysis = {"state": "working", "program": "a", "step": "the glossary",
                   "began": 100.0, "moved": 100.0}
    lv.note_analysis(state="done", program="a")
    got = lv.analysis_progress()
    assert "step" not in got, "a field from the previous report survived into this one"
    assert got["state"] == "done" and got["program"] == "a"
    assert got["began"] == 100.0, "the run forgot when it started"


def test_a_report_that_says_nothing_new_does_not_reset_the_silence() -> None:
    """The whole of how a hang becomes visible.

    A `moved` bumped on every identical report would say a run was moving because somebody
    was watching it -- and *silent for 4 minutes* is the only thing that separates a wedged
    child from a long step. Resolution on the Society tree is legitimately quiet for tens of
    seconds, which is why this is stated to the reader rather than acted on by the server.
    """
    lv = serve_mod._Live.__new__(serve_mod._Live)
    import threading
    lv.analysis_lock = threading.Lock()
    lv.analysis_proc = None
    lv.analysis = {"state": "working", "program": "a", "step": "resolving",
                   "done_steps": 3, "detail": "", "began": 100.0, "moved": 100.0}

    lv.note_analysis(state="working", program="a", step="resolving", done_steps=3,
                     detail="")
    assert lv.analysis["moved"] == 100.0, (
        "an identical report moved the clock -- the silence resets itself and a hang can "
        "never be seen"
    )
    lv.note_analysis(state="working", program="a", step="the cover", done_steps=4,
                     detail="")
    assert lv.analysis["moved"] > 100.0, "a real step change did not move the clock"


# ------------------------------------------------------------------ no GET does it --- #


def _handler_source() -> ast.ClassDef:
    tree = ast.parse(SERVE_PY.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "_Handler":
            return node
    raise AssertionError("_Handler is gone; this guard is blind")


def test_no_get_route_starts_an_analysis() -> None:
    """Rule 20 with a filesystem behind it.

    A GET that swaps the map is one a prefetch, a bookmark reload or a link preview fires
    by itself. A GET that reads a source tree into a new directory is the same thing and
    worse. `test_no_get_route_can_swap_the_base` is this test's older sibling; both read
    the route tables rather than trusting a naming convention.
    """
    handler = _handler_source()
    tables: dict[str, set[str]] = {}
    for node in handler.body:
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id in ("ROUTES", "POST_ROUTES")
                and isinstance(node.value, ast.Dict)):
            tables[node.target.id] = {
                v.value for v in node.value.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            }
    assert tables.get("ROUTES") and tables.get("POST_ROUTES"), "a route table is missing"
    assert "_p_analyze" in tables["POST_ROUTES"], "nothing starts an analysis at all"
    assert "_p_analyze" not in tables["ROUTES"], (
        "a GET starts an analysis -- a prefetch would read a tree off this disk"
    )
    # And the handler itself must be the only thing that starts the thread.
    src = SERVE_PY.read_text()
    body = src.split("def _r_analysis", 1)[1].split("\n    def ", 1)[0]
    assert "Thread(" not in body, "the read route starts work; it is meant to report it"


def test_the_pre_flight_is_one_function_for_the_field_and_the_button() -> None:
    """The warning under the field and the refusal at the button are the same sentence.

    Two readings of "may this run" would agree on the day they were written and drift on
    every day after (rule 41). Both routes call `analysis.check`, and this reads that off
    the source rather than hoping.
    """
    src = SERVE_PY.read_text()
    for route in ("_r_analysis", "_p_analyze"):
        body = src.split(f"def {route}", 1)[1].split("\n    def ", 1)[0]
        assert "analysis.check(" in body, (
            f"{route} decides for itself whether an analysis may run"
        )


# ------------------------------------------- a run that never finished writing --- #
#
# The finding that reframed this whole chunk. A killed `analyze` leaves a graph that **opens
# perfectly and lies**: one stopped twelve seconds into the Society tree reported 628 files,
# 4,786 routines and `resolved_calls = 0` -- a program that calls nothing -- over a
# timestamp, a tool version and chunk 2's determinism guarantee. Reachable with no stop
# button anywhere: Ctrl-C, a laptop that slept, an OOM kill, a full disk.


def _graph_with(out: Path, **meta: str) -> Path:
    """A graph in `out` carrying exactly the meta a test wants, and nothing else.

    Writes **into the directory it is given**, so a caller that then asks
    `revisions.newest(out, ...)` finds it. It made a `prog/` subdirectory once and the base
    test looked in the parent, which is a fixture bug that reads on screen as the feature
    not working.
    """
    out.mkdir(parents=True, exist_ok=True)
    rev = "2026-08-30T10:00:00Z"
    graph = revisions.db_path(out, revisions.GRAPH, rev)
    store = Store(graph)
    store.set_meta("revision", rev)
    for k, v in meta.items():
        store.set_meta(k, v)
    store.conn.commit()
    store.close()
    return graph


def test_the_three_states_of_finished_are_kept_apart(tmp_path: Path) -> None:
    """Missing, blank and `yes` -- and only the middle one is broken.

    Refusing on absence would refuse **every map made before this key existed**, none of
    which is broken. It is the same missing-versus-blank distinction `/api/about` keeps for
    `inference` and `model`, one store over, and it is the reason the marker is written on
    the way *in* rather than inferred from the absence of one on the way out.
    """
    predates = Store(_graph_with(tmp_path / "a"), writable=False)
    started = Store(_graph_with(tmp_path / "b", complete=""), writable=False)
    done = Store(_graph_with(tmp_path / "c", complete="yes"), writable=False)
    try:
        assert predates.finished() is None
        predates.refuse_if_unfinished("a")          # must not raise
        assert done.finished() == "yes"
        done.refuse_if_unfinished("c")              # must not raise
        assert started.finished() == ""
        with pytest.raises(UnfinishedMapError):
            started.refuse_if_unfinished("b")
    finally:
        for s in (predates, started, done):
            s.close()


def test_the_refusal_names_the_step_it_stopped_at(tmp_path: Path) -> None:
    """*Stopped* and *stopped while reading the documents* are different amounts of help.

    And it says no more than it knows: claiming *"nothing resolved its calls"* would be true
    of the one case that was measured and false of a run stopped after resolution (rule 13).
    """
    store = Store(_graph_with(tmp_path, complete="", step="reading the documents"),
                  writable=False)
    try:
        with pytest.raises(UnfinishedMapError) as caught:
            store.refuse_if_unfinished("half")
    finally:
        store.close()
    said = str(caught.value)
    assert "half was never finished" in said
    assert "while reading the documents" in said
    assert "part of a program, not a program" in said
    assert "Analysing it again completes it" in said, (
        "the refusal names no way out -- the reader is told no and left there"
    )


def test_the_marker_survives_a_real_kill(tmp_path: Path) -> None:
    """**The whole thing rests on a commit, so the commit is what is tested.**

    `Store.set_meta` does not commit; an uncommitted marker is lost by exactly the `kill -9`
    it exists for, and the graph then reads as one that predates the question -- which is
    the ambiguity above, arriving through the back door. Asserted by killing a real child
    rather than by reading the source for a `commit()`, because rule 37 is that a guard
    naming the right thing may still not catch it.
    """
    tree = tmp_path / "src"
    tree.mkdir()
    # Enough files that the run cannot finish before it is killed.
    for i in range(400):
        (tree / f"m{i}.py").write_text(
            f'"""Module {i}."""\nimport sqlite3\n\n\ndef f{i}(p):\n    return sqlite3.connect(p)\n')
    out = tmp_path / "out"
    proc = subprocess.Popen(analysis.argv(tree, "killed", out, docs=False),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Wait for the first progress line, so the graph certainly exists, then kill hardest.
    assert proc.stdout is not None
    assert proc.stdout.readline(), "the child said nothing before it was killed"
    proc.kill()
    proc.wait(timeout=30)

    graph = revisions.newest(out / "killed", revisions.GRAPH)
    assert graph is not None, "the killed run left no graph; this test proves nothing"
    store = Store(graph, writable=False)
    try:
        assert store.finished() == "", (
            "a killed run left no completion marker -- its map is indistinguishable from "
            "one written before the key existed, and every reader will vouch for it"
        )
        with pytest.raises(UnfinishedMapError):
            store.refuse_if_unfinished("killed")
    finally:
        store.close()


def test_a_finished_run_clears_the_marker(tmp_path: Path) -> None:
    """The other half, or the marker is a permanent accusation."""
    tree = tmp_path / "src"
    tree.mkdir()
    (tree / "m.py").write_text(TINY)
    out = tmp_path / "out"
    done = subprocess.run(analysis.argv(tree, "whole", out, docs=False),
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    graph = revisions.newest(out / "whole", revisions.GRAPH)
    assert graph is not None
    store = Store(graph, writable=False)
    try:
        assert store.finished() == "yes"
        store.refuse_if_unfinished("whole")         # must not raise
    finally:
        store.close()


def test_the_base_refuses_to_open_an_unfinished_map(tmp_path: Path) -> None:
    """`_Live.open` is where a map becomes the thing every pane answers out of.

    Refused before anything is built and before anything is swapped -- so a reader who picks
    one in the selector keeps the map they had, which is `open()`'s own rule (20) and what
    the stale-graph refusal already does.
    """
    out = tmp_path / "prog"
    out.mkdir()
    _graph_with(out, complete="", step="resolving calls and command trees")
    lv = serve_mod._Live(out / "source.db", out)
    try:
        with pytest.raises(UnfinishedMapError) as caught:
            lv.open(revisions.newest(out, revisions.GRAPH))     # type: ignore[arg-type]
    finally:
        lv.close()
    assert "resolving calls and command trees" in str(caught.value)


def test_the_reader_facing_refusals_lose_the_class_name() -> None:
    """A Python word in front of a sentence written for someone who does not write Python.

    `type(exc).__name__` earns its place before an `OSError`, which says little alone. In
    front of these two it is noise, and it lands first -- where the reader looks.
    """
    assert serve_mod.why(UnfinishedMapError("half was never finished: ...")) == (
        "half was never finished: ..."
    )
    assert serve_mod.why(StaleGraphError("written by an older DunneFlow")) == (
        "written by an older DunneFlow"
    )
    # And anything else keeps it, because "connection refused" alone names nothing.
    assert serve_mod.why(OSError("connection refused")) == "OSError: connection refused"


def test_check_refuses_an_unfinished_map_rather_than_reporting_it_green(
        tmp_path: Path) -> None:
    """**The most expensive of the four readers, because it is the one that gates CI.**

    `dunneflow check` exits non-zero only on BROKEN. A half-written map has had most of its
    detectors run over a third of a program, so it reports `0 broken` and passes -- a green
    build over a map that was never finished being written. Every command sharing
    `_open_store` refuses for the same reason: they all present their answer as a fact about
    a program.
    """
    out = tmp_path / "out"
    _graph_with(out / "half", complete="", step="reading the documents")
    args = build_parser().parse_args(
        ["check", str(tmp_path / "anything"), "--name", "half", "--output", str(out)])
    assert cmd_check(args) == 2, "check passed a map that was never finished"


def test_query_reads_an_unfinished_map_and_says_so(tmp_path: Path, capsys: Any) -> None:
    """The one exemption, and it is loud.

    `query`'s whole contract is that you get the rows that are there, so refusing would
    take away the only tool that can look at what a stopped run did manage to write. It
    warns instead -- an escape hatch that quietly hands over a half-written map is not an
    escape hatch, it is a trap.
    """
    out = tmp_path / "out"
    _graph_with(out / "half", complete="", step="reading the documents")
    args = build_parser().parse_args(
        ["query", str(tmp_path / "anything"), "--name", "half", "--output", str(out),
         "--sql", "SELECT 1 AS n"])
    assert cmd_query(args) == 0, "query refused; it is the reader that must not"
    said = capsys.readouterr()
    assert "warning:" in said.err and "never finished" in said.err, (
        "query read a half-written map without saying so"
    )


def test_stopping_reaches_the_workers_the_child_started(tmp_path: Path) -> None:
    """**The jam this chunk is about, arriving through the fix for it.**

    `analyze` runs a `ProcessPoolExecutor` and its workers inherit the pipes. Signalling the
    parent alone killed the parent and left eleven workers alive holding stdout open, so
    `run`'s read loop never returned and the report said `working` for ever over a child
    that had gone -- `state: working` beside `running: false`, which is the exact
    label-outlives-the-fact shape this chunk exists to remove.

    Asserted end to end on a real analysis, because nothing smaller reproduces it: the
    defect lives in process groups, not in this codebase's logic.
    """
    tree = tmp_path / "src"
    tree.mkdir()
    for i in range(400):
        (tree / f"m{i}.py").write_text(
            f'"""Module {i}."""\nimport sqlite3\n\n\ndef f{i}(p):\n    return sqlite3.connect(p)\n')
    out = tmp_path / "out"

    seen: list[dict[str, Any]] = []
    holder: dict[str, Any] = {}
    thread = threading.Thread(
        target=analysis.run,
        kwargs={"source": tree, "name": "grp", "out_root": out, "docs": False,
                "note": lambda **f: seen.append(f),
                "on_start": lambda p: holder.setdefault("proc", p)},
        daemon=True)
    thread.start()

    for _ in range(200):                          # wait for the pool to be busy
        if seen and holder.get("proc"):
            break
        time.sleep(0.05)
    assert holder.get("proc"), "the child never started; this test proves nothing"

    assert analysis.stop(holder["proc"]) in ("stopped", "killed — it did not stop when asked")
    # **The point.** `run` must return -- which it only does once every writer of the
    # stdout pipe is gone, workers included.
    thread.join(timeout=30)
    assert not thread.is_alive(), (
        "the reader thread never returned -- the pool's workers are still holding stdout "
        "open, so the panel will say `working` over a child that has gone"
    )
    assert seen[-1]["state"] == "stopped", (
        f"a stopped run did not report itself stopped: {seen[-1]}"
    )
