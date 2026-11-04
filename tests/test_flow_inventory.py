"""The flows page's inventory is the reader's choice, and its stated cost is its size.

Unreal's `Runtime` wrote a 1.14 GB `02-flows.md`: 5,705 inventories of 11.3 M rows, every
routine each way in reaches. Tom's ruling (2026-11-03): `full` stays the default, and a
costly output is the reader's choice with the cost in front of them. So there are three
inventories -- `full`, `omitted` (only what each diagram leaves out, which is rule 8 read
literally) and `count` -- and the page says which was written and what the others would
have taken. Rule 13 is the test that matters here: a size printed beside a choice is the
number of bytes that choice puts on the page.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from dunneflow import runstate
from dunneflow.render import markdown
from dunneflow.render.markdown import (
    COUNT,
    FULL,
    INVENTORY_MODES,
    OMITTED,
    InventoryCost,
    human_bytes,
    inventory_costs,
    render_all,
)
from dunneflow.resolve.flows import trace_flow, ways_in
from dunneflow.store import Store
from dunneflow.web import analysis

BLOCK = re.compile(r"<details><summary>.*?</details>\n", re.S)


@pytest.fixture
def small_diagrams(monkeypatch: pytest.MonkeyPatch) -> None:
    """Diagrams of one routine, so every way in that reaches more has something left out."""
    def capped(*a: Any, **k: Any) -> Any:
        k["max_nodes"] = 1
        return trace_flow(*a, **k)
    monkeypatch.setattr(markdown, "trace_flow", capped)


def _render(store: Store, out: Path, mode: str) -> tuple[str, InventoryCost]:
    seen: list[InventoryCost] = []

    def choose(cost: InventoryCost) -> str:
        seen.append(cost)
        return mode

    render_all(store, out, "sample", choose=choose)
    return (out / "02-flows.md").read_text(encoding="utf-8"), seen[0]


@pytest.mark.usefixtures("small_diagrams")
@pytest.mark.parametrize("mode", INVENTORY_MODES)
def test_the_stated_cost_is_the_bytes_the_page_holds(
        analyzed: Store, tmp_path: Path, mode: str) -> None:
    page, cost = _render(analyzed, tmp_path / mode, mode)
    blocks = BLOCK.findall(page)
    assert blocks, "the sample drew no flows, so this compared nothing"
    assert sum(len(b.encode("utf-8")) for b in blocks) == cost.bytes[mode]
    # And the page says it, in the words the README uses.
    assert f"`--flow-inventory {mode}`, {human_bytes(cost.bytes[mode])}" in page
    for other in INVENTORY_MODES:
        if other != mode:
            assert cost.words(other) in page


@pytest.mark.usefixtures("small_diagrams")
def test_each_mode_lists_what_it_says(analyzed: Store, tmp_path: Path) -> None:
    full, _ = _render(analyzed, tmp_path / "f", FULL)
    omitted, _ = _render(analyzed, tmp_path / "o", OMITTED)
    count, _ = _render(analyzed, tmp_path / "c", COUNT)

    def rows(page: str) -> int:
        return sum(1 for line in page.splitlines() if line.startswith("| `"))

    assert rows(full) > rows(omitted) > 0, "omitted must list less, and something"
    assert rows(count) == 0, "count lists nothing"
    assert "counted, not listed" in count and "--flow-inventory full" in count
    assert "leaves out" in omitted
    # The caption under a capped diagram promises what the list below it holds (rule 13).
    assert "listed in full below" in full and "listed in full below" not in omitted


def test_omitted_lists_exactly_what_the_diagram_drew_not(analyzed: Store) -> None:
    index = markdown._Inventory(analyzed)
    d = next(x for x in ways_in(analyzed) if x["roots"])
    flow = trace_flow(analyzed, d["roots"][0], d["name"], d["kind"], max_nodes=2)
    reached = set(analyzed.reachable_from_many(d["roots"]))
    drawn = {n.routine_id for n in flow.nodes}

    block = markdown._flow_inventory(analyzed, d, index, OMITTED, flow)

    assert block.count("\n| `") == len(index.rows(reached - drawn))


def test_the_choice_is_asked_with_the_costs_and_an_unknown_one_is_refused(
        analyzed: Store, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no flows inventory called 'some'"):
        render_all(analyzed, tmp_path / "x", "sample", choose=lambda _c: "some")
    cost = inventory_costs(analyzed, ways_in(analyzed))
    assert cost.bytes[FULL] >= cost.bytes[OMITTED]
    assert cost.bytes[COUNT] > 0


def test_the_readme_says_which_inventory_was_written(analyzed: Store, tmp_path: Path) -> None:
    render_all(analyzed, tmp_path / "m", "sample", inventory=COUNT)
    readme = (tmp_path / "m" / "README.md").read_text(encoding="utf-8")
    assert "its inventories list how many each reaches, not which" in readme


def test_human_bytes_reads_as_a_file_manager_does() -> None:
    assert human_bytes(412) == "412 bytes"
    assert human_bytes(830_400) == "830 KB"
    assert human_bytes(1_140_000_000) == "1.14 GB"


# --------------------------------------------------------------------------- #
# The dialog


def test_the_child_is_told_the_dialogs_choice(tmp_path: Path) -> None:
    cmd = analysis.argv(tmp_path, "n", tmp_path, docs=True, inventory=OMITTED)
    assert cmd[cmd.index("--flow-inventory") + 1] == OMITTED
    assert "--flow-inventory" not in analysis.argv(tmp_path, "n", tmp_path, docs=True)


def test_the_last_runs_sizes_are_read_only_from_a_finished_run(tmp_path: Path) -> None:
    out = tmp_path / "prog"
    out.mkdir()
    assert analysis.inventory_for(out) is None
    sizes = {FULL: 9_000, OMITTED: 300, COUNT: 40}
    runstate.path_in(out).write_text(
        '{"state": "done", "inventory_bytes": ' + str(sizes).replace("'", '"') + "}",
        encoding="utf-8")
    assert analysis.inventory_for(out) == sizes
    runstate.path_in(out).write_text('{"state": "working", "inventory_bytes": {"full": 1}}',
                                     encoding="utf-8")
    assert analysis.inventory_for(out) is None


# --------------------------------------------------------------------------- #
# The terminal


def test_the_flag_wins_and_unchosen_large_says_the_costs_and_writes_full(
        monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from dunneflow import cli

    cost = InventoryCost({FULL: 2_000_000, OMITTED: 50_000, COUNT: 900})
    seen: dict[str, int] = {}
    told = cli.build_parser().parse_args(["render", "x", "--flow-inventory", "count"])
    assert cli._inventory_chooser(told, seen)(cost) == COUNT
    assert seen == cost.bytes, "the sizes must reach the run's sidecar"

    monkeypatch.setattr(cli, "INVENTORY_ASK_ABOVE", 1_000_000)
    monkeypatch.setattr(cli, "_interactive", lambda _a: False)
    unsaid = cli.build_parser().parse_args(["render", "x"])
    assert cli._inventory_chooser(unsaid, {})(cost) == FULL
    said = capsys.readouterr().err
    assert "2 MB" in said and "50 KB" in said and "--flow-inventory" in said

    monkeypatch.setattr(cli, "_interactive", lambda _a: True)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO("o\n"))
    assert cli._inventory_chooser(unsaid, {})(cost) == OMITTED
