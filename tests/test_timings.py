"""Where the time went, on both of the surfaces that had no answer.

Two instruments and one reason for them. `analyze` has timed extraction, resolution and
rendering for a year and nothing else, and `/api/program` has reported which step it was on
and never what a step cost. That was survivable until Unreal: a part of **fifteen files
costing 110-400 s** and a map opening in **27.6 minutes**, with nothing to say where either
went (`BACKLOG.md` items 8 and 9). The evidence for the second was the last step label sent
before `done`, which is not evidence at all -- it is the plausible diagnosis of a real
symptom that rule 39 is named for.

**Nothing here times anything.** A test that asserts a phase took under N seconds measures
the machine it runs on (`test_size_guard.py` makes the same argument about commits). What is
asserted is that every phase is *accounted for*: that the rows name the phases that ran, that
a step contains its own parts rather than reporting their crumbs, and that the arithmetic
closes against the total. A figure nobody can check is a figure, and a figure that does not
add up is a defect.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dunneflow import usage
from dunneflow.cli import (
    STEP_ANOMALIES,
    STEP_BEFORE,
    STEP_EXTRACT,
    _Progress,
    analysis_steps,
    build_parser,
    cmd_analyze,
)
from dunneflow.web.serve import _Clock

# ------------------------------------------------------- the analysis's phases --- #

def _analyse(tmp_path: Path, *extra: str) -> _Progress:
    """Analyse a tiny tree for real and hand back the reporter that timed it."""
    tree = tmp_path / "src"
    tree.mkdir()
    (tree / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    args = build_parser().parse_args(
        ["analyze", str(tree), "--name", "t", "--output", str(tmp_path / "out"),
         "--quiet", *extra])
    assert cmd_analyze(args) == 0
    # The reporter the run actually used is not handed back, so this rebuilds the claim
    # the table makes rather than the table itself; the end-to-end assertion is below.
    return _Progress(analysis_steps(args), on=False)


def _table(prog: _Progress) -> list[str]:
    """The phase rows and the total, without the lines about the machine under them."""
    lines = prog.timings()
    end = next(i for i, ln in enumerate(lines) if ln.strip().startswith("the whole run"))
    return lines[:end + 1]


def test_every_phase_of_a_run_is_named_in_the_table(tmp_path: Path) -> None:
    """Including the ones that cost nothing, and including the one with no step.

    A phase absent from a table is indistinguishable from a phase that was instant, and
    only one of those is news (design rule 21). The unnamed region **before** the first
    step is the one this was written for: the size guard's walk, the manifest walk-up, the
    standards refusals and three store opens all happen there, and on a part of fifteen
    files that is where a run's time can go.
    """
    # `_Progress` asserts its labels against `ALL_STEPS`, so the table is exercised
    # through the real ones.
    prog = _Progress((STEP_EXTRACT, STEP_ANOMALIES), on=False)
    prog.step(STEP_EXTRACT)
    prog.step(STEP_ANOMALIES)

    named = [line.strip().split("  ")[0] for line in _table(prog)]
    assert STEP_BEFORE in named, "the region before the first step is a phase and was untimed"
    assert STEP_EXTRACT in named and STEP_ANOMALIES in named
    assert named[-1] == "the whole run"


def test_the_last_phase_is_in_the_table_although_nothing_closed_it(tmp_path: Path) -> None:
    """The prose path never calls `done`, and the last phase is the anomalies.

    `done` is reached only with `--progress-json`; a terminal gets a summary instead. So a
    table built from what has been banked is a table with its last row missing, and the
    missing row is a real phase of every run there is (rule 32).
    """
    prog = _Progress((STEP_EXTRACT, STEP_ANOMALIES), on=False)
    prog.step(STEP_EXTRACT)
    prog.step(STEP_ANOMALIES)
    assert STEP_ANOMALIES in " ".join(prog.timings())


def test_a_step_this_run_is_not_taking_is_not_a_phase(tmp_path: Path) -> None:
    """`analysis_steps` decides what a run does, and the table follows it.

    `--no-docs` removes two steps, and a table that listed them at 0.0s would be claiming
    the documents were read instantly rather than not at all -- design rule 1 inverted,
    which is rule 13.
    """
    prog = _Progress((STEP_EXTRACT, STEP_ANOMALIES), on=False)
    prog.step(STEP_EXTRACT)
    prog.step("reading the documents")       # in ALL_STEPS, not in this run
    prog.step(STEP_ANOMALIES)
    assert "reading the documents" not in " ".join(prog.timings())


def test_the_phases_add_up_to_the_run(tmp_path: Path) -> None:
    """The one arithmetic claim, and it is the one that makes the rest readable.

    Percentages that do not sum are a table nobody can reason from. Asserted on the
    numbers rather than on the printed line, because the printed line rounds.
    """
    prog = _Progress((STEP_EXTRACT, STEP_ANOMALIES), on=False)
    prog.step(STEP_EXTRACT)
    prog.step(STEP_ANOMALIES)
    lines = _table(prog)
    assert len(lines) == 4, lines                       # before + two steps + the total
    # Against the numbers, not the printed line: the line rounds to a tenth of a second
    # and every phase of this run is far inside that.
    assert sum(t for _, t in prog.spent) <= prog.ms()


def test_the_machine_channel_carries_how_long_it_has_taken(tmp_path: Path, capsys) -> None:
    """`serve` runs its child `--quiet`, so prose timings reached nobody who used the app.

    Three `perf_counter` spans were printed to a stderr the dashboard does not read, which
    is design rule 1's shape one channel over: the application could say how far a run had
    got and never how long it had been going.
    """
    prog = _Progress((STEP_EXTRACT,), on=True)
    prog.step(STEP_EXTRACT)
    prog.detail(1, 2)
    prog.done(program="t")
    import json
    lines = [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert lines, "the machine channel said nothing at all"
    assert all("ms" in ln for ln in lines), [ln for ln in lines if "ms" not in ln]
    assert all(isinstance(ln["ms"], int) for ln in lines)


def test_the_flag_is_what_prints_it(tmp_path: Path, capsys) -> None:
    """An instrument, not part of what a run says. End to end, through `cmd_analyze`."""
    _analyse(tmp_path, "--no-docs", "--no-render")
    assert "where the time went" not in capsys.readouterr().err

    (tmp_path / "again").mkdir()
    _analyse(tmp_path / "again", "--no-docs", "--no-render", "--timings")
    said = capsys.readouterr().err
    assert "where the time went" in said
    assert STEP_BEFORE in said and STEP_EXTRACT in said


# ------------------------------------------- what a run cost the machine --- #

def test_every_phase_has_its_cpu_beside_its_time() -> None:
    """Runtime read in 10,363 s once and 30,660 s another time, and the log could not say
    whether the reader worked or waited. CPU beside wall clock is that difference."""
    prog = _Progress((STEP_EXTRACT, STEP_ANOMALIES), on=False)
    prog.step(STEP_EXTRACT)
    sum(i * i for i in range(200_000))                      # some CPU, in this phase
    prog.step(STEP_ANOMALIES)
    cpus = prog.cpu_phases()
    assert len(cpus) == len(prog.phases())
    if sys.platform != "win32":
        assert all(c is not None and c >= 0 for c in cpus), cpus
        assert cpus[1] is not None and cpus[1] > 0
        assert all("CPUs" in ln for ln in _table(prog)), _table(prog)


def test_a_platform_that_cannot_count_the_readers_says_so(monkeypatch) -> None:
    """Windows has no `RUSAGE_CHILDREN`, and a figure for this process alone would read as
    the run's: so no CPU column at all, and a line saying why (rule 49)."""
    monkeypatch.setattr(sys, "platform", "win32")
    prog = _Progress((STEP_EXTRACT,), on=False)
    prog.step(STEP_EXTRACT)
    said = prog.timings()
    assert not any("CPUs" in ln for ln in said), said
    assert any("not measured for the readers" in ln for ln in said), said
    assert any("peak memory: not measured" in ln for ln in said), said
    r = prog.resources()
    assert r["cpu_s"] == [None, None] and r["peak_bytes"] is None


def test_the_table_says_what_the_machine_was_doing() -> None:
    prog = _Progress((STEP_EXTRACT,), on=False)
    prog.step(STEP_EXTRACT)
    said = " ".join(prog.timings())
    assert "the machine at the start:" in said and "the machine at the end:" in said
    if sys.platform != "win32":
        assert "peak memory:" in said and "MB this process" in said


def test_the_sidecar_keeps_what_the_run_cost_the_machine(tmp_path: Path) -> None:
    _analyse(tmp_path, "--no-docs", "--no-render")
    side = json.loads(next((tmp_path / "out").rglob("analysis.json")).read_text())
    r = side["resources"]
    assert len(r["cpu_s"]) == len(side["timings"])
    assert set(r) >= {"machine_start", "machine_end", "peak_bytes", "peak_child_bytes"}


def test_swap_is_read_off_what_macos_prints(monkeypatch) -> None:
    import subprocess

    class Done:
        stdout = "total = 3072.00M  used = 1840.69M  free = 1231.31M  (encrypted)\n"

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Done())
    assert usage._swap() == (round(1840.69 * (1 << 20)), 3072 * (1 << 20))


def test_swap_is_read_off_proc_meminfo(monkeypatch, tmp_path: Path) -> None:
    import builtins
    info = tmp_path / "meminfo"
    info.write_text("MemTotal: 8000 kB\nSwapTotal:  2048 kB\nSwapFree:  512 kB\n",
                    encoding="ascii")
    real = builtins.open
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(builtins, "open",
                        lambda p, *a, **k: real(info if p == "/proc/meminfo" else p, *a, **k))
    assert usage._swap() == (1536 * 1024, 2048 * 1024)


def test_swap_that_cannot_be_read_is_absent_not_zero(monkeypatch) -> None:
    import subprocess

    def fails(*a, **k):
        raise subprocess.CalledProcessError(1, "sysctl")

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(subprocess, "run", fails)
    assert "swap_used" not in usage.machine()


# --------------------------------------------------- the dashboard's six steps --- #

def test_a_step_contains_its_parts_rather_than_their_crumbs() -> None:
    """The defect this class shipped with for the length of one boot, and the reason for
    two cursors.

    Written with one cursor, `the 2.5D model and its payload` reported **0.0s** on a boot
    where it had just taken every one of the four laps printed above it: the step's delta
    was measured from the last lap rather than from the last step, so its own row was the
    crumbs its parts had left. Arithmetically true, and it says the opposite of what
    happened -- which is the shape of rule 49 in a report.
    """
    c = _Clock()
    c.phase("first")
    c.lap("· part one")
    c.lap("· part two")
    c.phase("second")

    spent = dict(c.spent)
    assert spent["second"] >= spent["· part one"] + spent["· part two"], c.spent


def test_a_clock_says_cumulative_and_banks_deltas() -> None:
    """`ms()` is what every existing caller means by it and what the client draws.

    A client that misses a line still has a true cumulative figure; a stream of deltas
    does not survive one being dropped.
    """
    c = _Clock()
    c.phase("first")
    first = c.ms()
    c.phase("second")
    assert c.ms() >= first
    assert [n for n, _ in c.spent] == ["first", "second"]
