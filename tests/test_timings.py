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

from pathlib import Path

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

    named = [line.strip().split("  ")[0] for line in prog.timings()]
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
    lines = prog.timings()
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
