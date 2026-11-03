"""How long a run will take, said before it starts, and the reader's choice about it.

Unreal's `Runtime`, 18,263 files, sat under the 20,000-file gate and started a 2 h 19 m
extraction without a word. The gate now decides on an estimate (`estimate`), asks a terminal
when the estimate is over `--warn-after`, and refuses anything else with `--any-size` named.

The estimate a run acts on comes from **this program's last run**, recorded in its sidecar,
so the end-to-end tests here plant a sidecar for a run that was slow -- the same file a real
run leaves -- rather than patching the rates: what is under test is that the gate reads it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from dunneflow import estimate, runstate
from dunneflow.cli import build_parser
from dunneflow.estimate import WARN_AFTER_MAX

#: The console script's own entry point, as `pyproject.toml` declares it.
CLI = [sys.executable, "-c", "import sys; from dunneflow.cli import main; sys.exit(main())"]


def test_the_defaults_price_each_language_at_its_own_rate() -> None:
    e = estimate.estimate({"cpp": 1000}, cpus=8)
    ex, after = estimate.RATES["cpp"]
    assert e.high_s == pytest.approx(1000 * (ex + after), rel=1e-3)
    assert e.low_s == e.high_s, "with no cache to skip from, the range has one end"
    assert "cpp" in e.basis and "8 CPUs" in e.basis


def test_twice_the_cpus_is_half_the_time_and_a_cache_lowers_only_the_low_end() -> None:
    eight = estimate.estimate({"cpp": 1000}, cpus=8)
    sixteen = estimate.estimate({"cpp": 1000}, cpus=16)
    assert sixteen.high_s == pytest.approx(eight.high_s / 2, rel=1e-3)
    cached = estimate.estimate({"cpp": 1000}, cpus=8, cached_possible=True)
    assert cached.high_s == eight.high_s and cached.low_s < cached.high_s


def test_a_language_with_no_measurement_is_named_not_hidden() -> None:
    e = estimate.estimate({"cobol": 10}, cpus=8)
    assert "no measurement for cobol" in e.basis


def test_the_last_run_of_this_program_is_what_the_next_one_is_priced_from() -> None:
    prior = {"state": "done", "parsed": 100, "files": {"cpp": 100},
             "timings": [["before the first step", 1000],
                         [estimate.EXTRACT_PHASE, 50_000], ["writing the map", 20_000]]}
    e = estimate.estimate({"cpp": 200}, prior=prior, cpus=8)
    # 0.5 s a file extracting, and the 21 s after it scaled by 200/100.
    assert e.high_s == pytest.approx(200 * 0.5 + 21 * 2, rel=1e-3)
    assert "last run" in e.basis


def test_a_cached_rerun_is_not_a_price_for_a_cold_one() -> None:
    """18,263 files extracted from cache in 40 s would price a cold run at 40 s."""
    prior = {"state": "done", "parsed": 3, "files": {"cpp": 18_263},
             "timings": [[estimate.EXTRACT_PHASE, 40_000]]}
    e = estimate.estimate({"cpp": 18_263}, prior=prior, cpus=8)
    assert "last run" not in e.basis


@pytest.mark.parametrize("secs, said", [
    (30, "under a minute"), (600, "10 min"), (3600, "1 h"), (8353, "2 h 20 min"),
    (7190, "2 h"),
])
def test_a_span_is_said_to_the_precision_it_has(secs: float, said: str) -> None:
    assert estimate._span(secs) == said


def test_the_warning_threshold_is_clamped_and_says_why(capsys) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["analyze", ".", "--warn-after", str(WARN_AFTER_MAX + 1)])
    assert "no run measured here" in capsys.readouterr().err


def _slow_last_run(out_dir: Path, files: int) -> None:
    """The sidecar a finished run leaves, for a run whose extraction was very slow."""
    out_dir.mkdir(parents=True, exist_ok=True)
    runstate.path_in(out_dir).write_text(json.dumps({
        "state": "done", "code": 0, "pid": 0, "beat": time.time(), "began": time.time(),
        "parsed": max(files, 20), "files": {"python": max(files, 20)},
        "timings": [[estimate.EXTRACT_PHASE, 3_600_000 * max(files, 20)]],
        "progress": {"state": "done"},
    }))


def test_a_long_run_with_no_terminal_is_refused_naming_the_flag(sample_tree: Path,
                                                                 tmp_path: Path) -> None:
    out = tmp_path / "out"
    _slow_last_run(out / "sample", 9)
    r = subprocess.run([*CLI, "analyze", str(sample_tree),
                        "--name", "sample", "--output", str(out)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert r.returncode == 2, r.stderr
    assert "estimated at" in r.stderr and "--any-size" in r.stderr
    assert not list((out / "sample").glob("graph@*.db")), "it started anyway"

    r = subprocess.run([*CLI, "analyze", str(sample_tree),
                        "--name", "sample", "--output", str(out), "--any-size", "--quiet"],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("answer, code", [(b"n\n", 2), (b"y\n", 0)])
def test_a_terminal_is_asked_and_the_answer_is_kept(sample_tree: Path, tmp_path: Path,
                                                    answer: bytes, code: int) -> None:
    if sys.platform == "win32":
        pytest.skip("a pseudo-terminal is POSIX's")
    import pty

    out = tmp_path / "out"
    _slow_last_run(out / "sample", 9)
    leader, follower = pty.openpty()
    proc = subprocess.Popen([*CLI, "analyze", str(sample_tree),
                             "--name", "sample", "--output", str(out), "--quiet"],
                            stdin=follower, stderr=follower, stdout=subprocess.DEVNULL)
    os.close(follower)
    said = b""
    try:
        while b"[y/N]" not in said:
            try:
                chunk = os.read(leader, 4096)
            except OSError:           # the child is gone and the terminal closed with it
                chunk = b""
            assert chunk, f"the child ended without asking: {said!r}"
            said += chunk
        os.write(leader, answer)
        assert proc.wait(timeout=300) == code
    finally:
        if proc.poll() is None:
            proc.kill()
        os.close(leader)
    assert b"estimated at" in said
    started = bool(list((out / "sample").glob("graph@*.db")))
    assert started == (code == 0)


# -- the dashboard: asked before it starts, and the child never asks again ------------- #


def test_the_dashboard_child_is_told_the_reader_has_been_asked(tmp_path: Path) -> None:
    """The child has no terminal; without `--any-size` its own gate refuses the run the
    reader just confirmed in the dialog."""
    from dunneflow.web import analysis

    assert "--any-size" in analysis.argv(tmp_path, "p", tmp_path, True)


def _handler(root: Path):
    from dunneflow.web import serve as serve_mod

    started: list[str] = []
    said: list[dict] = []

    class Live:
        out_root = root
        opened = False

        def start_analysis(self, name, **_kw):
            started.append(name)
            return True

        def analysis_progress(self):
            return {"state": "working"}

    h = serve_mod._Handler.__new__(serve_mod._Handler)
    h._live = Live()            # type: ignore[assignment]
    h._json = said.append       # type: ignore[assignment,method-assign]
    return h, started, said


def test_a_long_run_is_put_to_the_reader_and_starts_only_on_yes(sample_tree: Path,
                                                                tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    _slow_last_run(root / "sample", 9)
    h, started, said = _handler(root)
    q = {"path": [str(sample_tree)], "name": ["sample"]}

    h._p_analyze(q)
    assert not started, "it started before the reader was asked"
    k = said[-1]["confirm"]
    assert said[-1]["started"] is False and k["high_s"] > 600
    assert "last run" in k["basis"], "the dialog and the terminal priced it differently"

    h._p_analyze({**q, "any_size": ["1"]})
    assert started == ["sample"], "the reader said yes and nothing started"


def test_a_short_run_starts_without_asking_and_the_threshold_is_the_readers(
        sample_tree: Path, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    h, started, said = _handler(root)
    h._p_analyze({"path": [str(sample_tree)], "name": ["sample"]})
    assert started == ["sample"] and "confirm" not in said[-1]

    from dunneflow.web.serve import _warn_after

    assert _warn_after({"warn_after": ["0"]}) == 1
    assert _warn_after({"warn_after": ["99999"]}) == WARN_AFTER_MAX
    assert _warn_after({"warn_after": ["soon"]}) == 10
