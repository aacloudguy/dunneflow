"""A run is visible to whoever opens the maps, not only to whoever started it.

Unreal's `Engine/Source/Runtime`, analysed from a terminal: 2 h 19 m of extraction, then
forty minutes of anomaly detection that reported nothing, and a dashboard opened on the same
root that called the program *"never finished — analyse it again"* the whole time. These
pin the three things that fixed it: every phase reports a count; the run writes
`analysis.json` beside its graph; and the dashboard reads that file -- to show the run, to
refuse a second one into the same directory, and to stop it.

**Alive is asked of a real child**, started and killed here, because a sidecar's whole job
is to describe a process that may already be gone, and a test that only constructs the
file would prove the parser and nothing about the process (rule 37).
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from dunneflow import runstate
from dunneflow.anomalies import DETECTORS, detect
from dunneflow.web import analysis
from dunneflow.web import serve as serve_mod

CHILD = r"""
import os, sys, time
from pathlib import Path
from dunneflow import runstate
d = Path(sys.argv[1])
r = runstate.RunState(d, program=d.name, revision="r1", graph=d / "graph@r1.db",
                      argv=["analyze", "x"]).start()
r.note({"state": "working", "step": "looking for anomalies", "done_steps": 6,
        "steps": 8, "detail": "detector 4/15", "ms": 1})
print("ready", os.getpid(), flush=True)
time.sleep(120)
"""


def _child(program_dir: Path) -> tuple[subprocess.Popen[str], int]:
    """The process, and the pid the run itself holds. They are two pids on Windows, where a
    venv's `python.exe` is a launcher that starts the real interpreter."""
    program_dir.mkdir(parents=True, exist_ok=True)
    kw: dict = {"start_new_session": True}
    if sys.platform == "win32":
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = subprocess.Popen([sys.executable, "-c", CHILD, str(program_dir)],
                            stdout=subprocess.PIPE, text=True, **kw)
    assert proc.stdout is not None
    word, pid = proc.stdout.readline().split()
    assert word == "ready"
    return proc, int(pid)


def _kill(proc: subprocess.Popen[str], pid: int) -> None:
    if proc.poll() is None:
        if sys.platform == "win32":
            os.kill(pid, signal.SIGTERM)  # TerminateProcess; the launcher then exits by itself
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    proc.wait(timeout=10)


def test_a_live_run_reads_as_running_and_a_killed_one_as_stopped(tmp_path: Path) -> None:
    d = tmp_path / "prog"
    proc, pid = _child(d)
    try:
        body = runstate.read(d)
        assert body is not None and body["running"], body
        shown = runstate.as_progress(body)
        assert shown["state"] == "working" and shown["origin"] == "terminal"
        assert shown["detail"] == "detector 4/15"
        assert shown["pid"] == pid
    finally:
        _kill(proc, pid)
    body = runstate.read(d)
    assert body is not None
    assert body["state"] == "working", "a killed run cannot have written its last word"
    assert not body["running"], "a dead pid read as a live run"
    shown = runstate.as_progress(body)
    assert shown["state"] == "stopped"
    assert "looking for anomalies" in shown["reason"], (
        "the sentence must say where it stopped, or it cannot say what to do about it")


def test_a_stale_heartbeat_is_not_a_live_run_even_with_a_live_pid(tmp_path: Path) -> None:
    """A pid is reused; the heartbeat is what a reused pid cannot fake."""
    r = runstate.RunState(tmp_path, program="p", revision="r", graph=tmp_path / "g.db",
                          argv=[]).start()
    try:
        later = time.time() + runstate.STALE_S + 5
        body = runstate.read(tmp_path, now=later)
        assert body is not None and not body["running"]
        assert runstate.read(tmp_path)["running"]  # type: ignore[index]
    finally:
        r.finish("done", code=0)


def test_the_last_word_is_the_state_it_left_in(tmp_path: Path) -> None:
    r = runstate.RunState(tmp_path, program="p", revision="r", graph=tmp_path / "g.db",
                          argv=[]).start()
    r.finish("failed", code=2)
    body = runstate.read(tmp_path)
    assert body is not None and body["state"] == "failed" and body["code"] == 2
    assert not body["running"]
    assert runstate.as_progress(body)["state"] == "failed"


def test_progress_is_throttled_but_a_new_step_is_never_dropped(tmp_path: Path) -> None:
    r = runstate.RunState(tmp_path, program="p", revision="r", graph=tmp_path / "g.db",
                          argv=[]).start()
    try:
        r.note({"state": "working", "step": "a", "detail": "1/9"})
        r.note({"state": "working", "step": "a", "detail": "2/9"})   # inside NOTE_S
        on_disk = json.loads(runstate.path_in(tmp_path).read_text())
        assert on_disk["progress"]["detail"] == "1/9"
        r.note({"state": "working", "step": "b", "detail": ""})     # a step moved
        on_disk = json.loads(runstate.path_in(tmp_path).read_text())
        assert on_disk["progress"]["step"] == "b"
    finally:
        r.finish("done", code=0)


def test_every_detector_is_a_tick(analyzed) -> None:
    seen: list[tuple[int, int, str]] = []
    detect(analyzed, tick=lambda i, n, what: seen.append((i, n, what)))
    total = len(DETECTORS) + 1
    assert [i for i, _, _ in seen] == list(range(total + 1))
    assert all(n == total for _, n, _ in seen)


def test_every_document_is_a_tick_and_the_flows_page_counts_its_ways_in(analyzed, tmp_path):
    from dunneflow.render.markdown import render_all

    seen: list[tuple[int, int, str]] = []
    files = render_all(analyzed, tmp_path / "map", "sample",
                       tick=lambda i, n, what: seen.append((i, n, what)))
    pages = [(i, n) for i, n, what in seen if what == "document"]
    assert pages[0] == (0, pages[0][1]) and pages[-1] == (pages[0][1], pages[0][1])
    assert len(files) <= pages[0][1]
    assert any(what.startswith("02-flows.md") for _, _, what in seen), (
        "the flows page is the slow one, and it said nothing about its ways in")


def test_analyze_leaves_a_sidecar_that_says_it_finished(sample_tree: Path, tmp_path: Path):
    from dunneflow.cli import build_parser, cmd_analyze

    out = tmp_path / "out"
    args = build_parser().parse_args(
        ["analyze", str(sample_tree), "--name", "sample", "--output", str(out), "--quiet"])
    assert cmd_analyze(args) == 0
    body = runstate.read(out / "sample")
    assert body is not None, "analyze wrote no sidecar"
    assert body["state"] == "done" and body["code"] == 0 and not body["running"]
    assert body["progress"]["state"] == "done", "the last progress object is not the end"
    assert body["source"] == str(sample_tree.resolve()), (
        "Analyse it again fills the dialog with this, and the dialog takes absolute paths")


def _live(root: Path) -> serve_mod._Live:
    lv = serve_mod._Live.__new__(serve_mod._Live)
    lv.out_root = root
    lv.terminal_dir = None
    lv.analysis_lock = threading.Lock()
    lv.analysis = {"state": "idle"}
    lv.analysis_claimed = False
    lv.analysis_proc = None
    return lv


def _graph(d: Path) -> None:
    """Enough for `programs_under` to count the directory as a program."""
    from dunneflow.store import Store

    Store(d / "graph@r1.db").close()


def test_the_dashboard_shows_a_terminal_run_refuses_a_second_and_stops_it(tmp_path: Path,
                                                                         monkeypatch):
    root = tmp_path / "root"
    d = root / "prog"
    proc, pid = _child(d)
    _graph(d)
    try:
        lv = _live(root)
        shown = lv.analysis_progress()
        assert shown["origin"] == "terminal" and shown["running"], shown
        assert shown["program"] == "prog"

        src = tmp_path / "src"
        src.mkdir()
        v = analysis.check(str(src), "prog", root, None)
        assert not v.ok and "from a terminal" in v.refusal

        # **Polled while the stop is in progress**, as the panel does every 600 ms. The
        # first version reported the ending once, a poll during the stop's grace period took
        # it, and the panel was left on "asking the server…" (found in the browser).
        polls: list[dict] = []

        def poll() -> None:
            for _ in range(30):
                polls.append(lv.analysis_progress())
                time.sleep(0.2)

        poller = threading.Thread(target=poll)
        poller.start()
        stopped, said = lv.stop_analysis()
        assert stopped, said
        proc.wait(timeout=15)
        poller.join()
        # The ending stays on show for every poll after it, not for one of them ...
        for _ in range(3):
            after = lv.analysis_progress()
            assert after["origin"] == "terminal" and after["state"] == "stopped", after
            assert not after["running"]
        # ... until the window is over, when the server's own idle report is back.
        body = runstate.read(d)
        assert body is not None
        monkeypatch.setattr(time, "time", lambda: float(body["beat"]) + runstate.ENDED_S + 1)
        assert lv.analysis_progress().get("origin") is None
    finally:
        _kill(proc, pid)


@pytest.mark.skipif(sys.platform == "win32", reason="process groups are POSIX's")
def test_a_stop_never_signals_the_group_the_server_is_in() -> None:
    """A terminal job and the server can share a group -- a script that starts both with `&`.

    Signalling that group would stop the dashboard with the analysis."""
    class Ours:
        pid = os.getpid()
        own_group = False

    assert analysis._group_of(Ours()) is None
