"""*What breaks if I change it?* — the two halves that only ever existed as print code.

`Store.callers_of` answers the first half and has always been a method anybody can call.
The other two thirds of the answer — which ways in are disturbed, and what somebody has
already signed off on around them — were written inline in `cmd_impact` and were reachable
only by running the command and reading its output. So nothing tested them, and
`dunneflow mcp` would have had to write the statements a second time to ask the same
question (rule 51).

They are `resolve/flows.py`'s now, and these are their first tests.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from dunneflow.resolve import flows
from dunneflow.resolve.flows import (
    GOVERNANCE_KINDS,
    governance_over,
    ways_in_affected,
)
from dunneflow.store import Store


@pytest.fixture()
def ids(analyzed: Store) -> dict[str, str]:
    """The two routines the sample program's own shape makes useful here."""
    out = {}
    for name in ("load_config", "sync"):
        rows = analyzed.query("SELECT id FROM routines WHERE name = ?", (name,))
        assert rows, f"the sample no longer declares {name}"
        out[name] = rows[0]["id"]
    return out


# ---- the ways in a change disturbs --- #


def test_the_ways_in_reached_by_a_change_are_named(analyzed: Store,
                                                   ids: dict[str, str]) -> None:
    """`load_config` is called by `sync`, and `sync` is a declared CLI command.

    That chain is the whole feature: a reader changing a helper wants to be told which
    *ways in* they have disturbed, not which functions. The sample is the shape by luck --
    `@app.command()` over `sync`, and `sync` is the only caller.
    """
    callers = analyzed.callers_of(ids["load_config"])
    assert ids["sync"] in callers, "the sample's own call chain has changed"

    ways = ways_in_affected(analyzed, callers)
    assert {(w["name"], w["kind"]) for w in ways} == {("sync", "CLI")}, ways


def test_a_routine_nothing_calls_disturbs_no_way_in(analyzed: Store) -> None:
    """The empty answer is an answer, and it must not be an error.

    `IN ()` is not valid SQL, so the guard is in the function rather than at each caller --
    which is the whole reason this moved (rule 51). `cmd_impact` had it as an `if callers:`
    wrapped around both statements, and the MCP tool would have needed its own copy.
    """
    assert ways_in_affected(analyzed, []) == []
    assert governance_over(analyzed, []) == []


# ---- what somebody already decided --- #


def test_governance_recorded_against_a_routine_is_reported(analyzed: Store,
                                                           ids: dict[str, str]) -> None:
    """The sample's `# WHY: … Plan 01-02.` is mined as a PLAN annotation on `load_config`.

    Asked of the routine that carries it rather than of its callers, because that is the
    distinction the command makes and gets right: the annotation belongs to the thing
    annotated, and *implicated* means it sits on something in the blast radius.
    """
    assert governance_over(analyzed, [ids["load_config"]]) == ["Plan 01-02"]
    assert governance_over(analyzed, [ids["sync"]]) == [], (
        "an annotation on a callee is being reported against its caller"
    )


def test_the_governance_kinds_are_stated_once_rather_than_written_into_the_query(
) -> None:
    """A prose claim and the population it describes have to come from one place (rule 41).

    `cmd_impact` printed *"governance implicated"* over a statement whose
    `kind IN ('PLAN','DECISION','AUDIT_LOCK')` was a literal inside the SQL string. A
    surface that wants to say *which* kinds it asked about had no way to find out, and a
    fourth kind added to the schema would have been silently outside the answer.
    """
    assert GOVERNANCE_KINDS == ("PLAN", "DECISION", "AUDIT_LOCK")
    body = inspect.getsource(governance_over)
    for kind in GOVERNANCE_KINDS:
        assert f"'{kind}'" not in body and f'"{kind}"' not in body, (
            f"{kind} is written into the statement as well as declared, so the two can "
            "drift apart"
        )


def test_the_command_asks_these_rather_than_carrying_its_own_statements() -> None:
    """The point of the move, pinned: `cli.py` must hold no copy of either query.

    A guard over the source rather than over behaviour, because the failure being
    prevented is a *second* correct implementation -- which behaves identically until one
    of them is changed.
    """
    cli = (Path(flows.__file__).parent.parent / "cli.py").read_text(encoding="utf-8")
    impact = cli.split("def cmd_impact", 1)[1].split("\ndef ", 1)[0]
    assert "ways_in_affected(" in impact and "governance_over(" in impact, (
        "cmd_impact no longer asks the shared functions"
    )
    for fragment in ("FROM entrypoints WHERE routine_id IN", "FROM annotations WHERE owner_id IN"):
        assert fragment not in cli, (
            f"cli.py still writes {fragment!r} itself, so there are two answers to one "
            "question again"
        )
