"""The tools, driven end to end against a map this test analysed itself.

`test_mcp.py` proves the transport. This proves what rides on it, and it does so over the
same pipe rather than by calling the bodies: a tool is only as good as the answer that
reaches the other end, and the shape of that answer is decided in three places — the body,
the content envelope, and the JSON encoder.

**The refusal tests are the point of the file.** A tool that says no is answering, and MCP
puts that answer in front of a model — so `isError` on a *successful* call, never a
JSON-RPC error, and the sentence with no Python class name in front of it. A protocol
fault is the other thing and stays a JSON-RPC error; both are asserted, because collapsing
them is easy and reads fine from either end alone.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from dunneflow.mcp import Refused, jsonrpc, resources, tools
from dunneflow.mcp.session import Session
from dunneflow.runtime import self_argv
from dunneflow.web import analysis

from .test_mcp import HELLO, READY, drive, driving


@pytest.fixture(scope="session")
def mapped(tmp_path_factory: Any, sample_tree: Path) -> Path:
    """An output root holding one real map, analysed by the tool itself.

    A hand-built store would be quicker and would not exercise the thing these tests are
    for: the tools answer out of `_Base`, which is built from a graph, its sidecars and
    its documents together. `analysis.argv` is how `serve` runs an analysis, so what runs
    here is exactly the tested command (rule 51).
    """
    root = tmp_path_factory.mktemp("maps")
    done = subprocess.run(analysis.argv(sample_tree, "sample", root, docs=False),
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stderr
    return root


def call(mapped: Path, name: str, arguments: dict[str, Any] | None = None,
         *, request_id: int = 9) -> dict[str, Any]:
    """One `tools/call`, through a real session, returning the reply."""
    return drive([HELLO, READY, {
        "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    }], mapped / "sample").by_id(request_id)


def payload(reply: dict[str, Any]) -> Any:
    """The JSON a successful tool answered with."""
    assert "error" not in reply, reply
    assert reply["result"]["isError"] is False, reply["result"]["content"][0]["text"]
    return json.loads(reply["result"]["content"][0]["text"])


def refusal(reply: dict[str, Any]) -> str:
    """The sentence a refusing tool answered with."""
    assert "error" not in reply, f"a refusal became a protocol error: {reply}"
    assert reply["result"]["isError"] is True, reply
    return str(reply["result"]["content"][0]["text"])


# ---- the table --- #


def test_every_tool_is_listed_with_a_schema_and_every_listed_tool_has_a_body(
        mapped: Path) -> None:
    """Both directions. Either alone passes while the feature is broken (design rule 16)."""
    listed = drive([HELLO, READY, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}],
                   mapped / "sample").by_id(2)["result"]["tools"]
    names = [t["name"] for t in listed]
    assert names == [t.name for t in tools.TOOLS], names
    assert set(tools.BY_NAME) == {t.name for t in tools.TOOLS}
    for entry in listed:
        assert entry["description"].strip(), f"{entry['name']} does not say what it does"
        schema = entry["inputSchema"]
        assert schema["type"] == "object"
        for required in schema["required"]:
            assert required in schema["properties"], (
                f"{entry['name']} requires {required!r} and never describes it"
            )
        for prop, spec in schema["properties"].items():
            assert spec.get("description", "").strip(), (
                f"{entry['name']}.{prop} has no description, and the description is the "
                "half a signature cannot carry"
            )


def test_an_unknown_tool_is_a_protocol_fault_rather_than_a_refusal(mapped: Path) -> None:
    """A tool that does not exist is not a tool saying no.

    The client asked for something this server never advertised, which is a fault in the
    call; a stale map or a rejected statement is an answer to a question that was asked
    properly. Collapsing the two sends the model a sentence to reason about where the
    client should have handled a fault.
    """
    reply = call(mapped, "nosuchtool")
    assert reply["error"]["code"] == jsonrpc.INVALID_PARAMS
    assert "nosuchtool" in reply["error"]["message"]


# ---- what the map says --- #


def test_the_overview_carries_the_counts_and_says_which_languages_were_read(
        mapped: Path) -> None:
    body = payload(call(mapped, "overview"))
    assert body["stats"]["files"] == 1
    assert body["stats"]["routines"] >= 1
    assert body["languages"] == {"python": 1}, body["languages"]
    assert body["entrypoints"], "the sample declares a console script and none is reported"


def test_touches_reports_what_a_routine_ends_up_touching(mapped: Path) -> None:
    """`load_config` reads an environment variable and a file. Both are boundaries."""
    body = payload(call(mapped, "touches", {"routine": "load_config"}))
    assert body["exact"] is True
    kinds = set(body["routines"][0]["boundary_kinds"])
    assert {"ENV", "FILE"} <= kinds, kinds


def test_impact_reports_the_ways_in_and_the_governance(mapped: Path) -> None:
    body = payload(call(mapped, "impact", {"routine": "load_config"}))
    one = body["routines"][0]
    assert one["dependents"] >= 1
    assert {w["name"] for w in one["ways_in"]} == {"sync"}, one["ways_in"]
    assert one["governance_kinds"] == ["PLAN", "DECISION", "AUDIT_LOCK"], (
        "the answer does not say which kinds it asked about (rule 41)"
    )


def test_a_routine_arrives_whole_with_its_shape(mapped: Path) -> None:
    body = payload(call(mapped, "routine", {"routine": "sync"}))
    assert body["found"] is True
    assert body["detail"]["found"] is not False
    assert body["shape"]["found"] is True
    assert body["shape"]["routine"]["name"] == "sync"


def test_find_answers_the_name_question_and_the_text_question_together(
        mapped: Path) -> None:
    """The text half is the one the graph cannot answer at all.

    `WHY` appears in a comment in the sample and in no routine name, so a search that
    found it has read the source rather than the graph.
    """
    body = payload(call(mapped, "find", {"q": "WHY"}))
    assert body["names"]["matched"] == 0
    assert body["text"]["total"] >= 1, body["text"]


def test_the_glossary_carries_its_capability_block(mapped: Path) -> None:
    """Whether a citation can be opened is a fact only the server has (design rule 13)."""
    body = payload(call(mapped, "glossary"))
    assert set(body["sidecars"]) == {"DECLARED_CODE", "DECLARED_DOCS"}
    for tier in body["sidecars"].values():
        assert "opens" in tier and "reason" in tier


# ---- the name search may not lose its caveat --- #


def test_an_inexact_match_says_so_and_says_how_many(mapped: Path) -> None:
    """Rule 49's shape, carried across a pipe.

    `sample.app` is a Typer object, not a routine, so nothing matches it exactly and
    `find_routine` falls back to a substring search. A tool that returned those rows
    without `exact: false` and the sentence would hand a model a plausible answer to a
    question it did not ask — which is the defect `Found` was minted from, arriving in a
    new surface.
    """
    body = payload(call(mapped, "touches", {"routine": "sample.app"}))
    assert body["exact"] is False
    assert body["said"], "the rows crossed without the sentence that says what they are"
    assert "no routine is named" in " ".join(body["said"])


def test_a_tool_asked_about_nothing_refuses_rather_than_choosing(mapped: Path) -> None:
    assert "required" in refusal(call(mapped, "touches", {}))
    assert "required" in refusal(call(mapped, "query", {"sql": "   "}))


# ---- the escape hatch, and its two gates --- #


def test_a_read_returns_rows_and_says_what_it_counted(mapped: Path) -> None:
    body = payload(call(mapped, "query",
                        {"sql": "SELECT name FROM routines ORDER BY name"}))
    assert body["operation"] == "SELECT"
    assert body["tables"] == ["routines"]
    assert body["rows"] == len(body["results"])
    assert body["truncated"] is False


def test_a_bounded_read_says_it_was_bounded(mapped: Path) -> None:
    """A count must say what it counts (rule 32), and a truncation must say it truncated."""
    body = payload(call(mapped, "query",
                        {"sql": "SELECT name FROM routines ORDER BY name", "limit": 1}))
    assert body["returned"] == 1
    assert body["rows"] > 1
    assert body["truncated"] is True


@pytest.mark.parametrize("sql,because", [
    ("DELETE FROM routines", "WRITE"),
    ("UPDATE routines SET name = 'x'", "WRITE"),
    ("DROP TABLE routines", "DDL"),
    ("CREATE TABLE sneaky (a)", "DDL"),
    ("ATTACH DATABASE '/tmp/x.db' AS z", "CONTROL"),
])
def test_a_statement_that_is_not_a_read_is_refused_by_name(
        mapped: Path, sql: str, because: str) -> None:
    """The classifier's half of the two gates.

    `ATTACH` is the one it exists for: `mode=ro` **allows** it, and a second call could
    then write to a database that is not the map. Everything else here the connection
    would refuse anyway — refusing it here is what makes the reason name the statement
    rather than the database.
    """
    said = refusal(call(mapped, "query", {"sql": sql}))
    assert because in said, said


def test_a_statement_that_cannot_be_classified_is_refused_rather_than_tried(
        mapped: Path) -> None:
    """Rule 49: a fallback that yields a plausible value hides the failure it was written
    for. `EXPLAIN SELECT 1` is harmless and is refused anyway, because *this looked safe*
    is not a direction."""
    assert "could not be classified" in refusal(
        call(mapped, "query", {"sql": "EXPLAIN SELECT 1"}))


def test_a_refusal_carries_no_python_class_name_in_front_of_it(mapped: Path) -> None:
    """`serve.why()` prefixes a class name because a bare `ValueError` says little.

    In front of *"this tool runs reads; that is DELETE (WRITE)"* it is exactly wrong — and
    the reader here is a model, which will repeat whatever it is given. `Refused` is the
    type that says the message is already a sentence.
    """
    said = refusal(call(mapped, "query", {"sql": "DELETE FROM routines"}))
    assert not said.startswith(("ValueError", "Refused", "Exception")), said
    assert said.startswith("this tool runs reads"), said


def test_the_connection_refuses_a_write_the_classifier_lets_through(mapped: Path) -> None:
    """The other gate, and the reason there are two.

    `WITH x AS (SELECT 1) DELETE FROM t` classifies as READ, because `sql.parse` reads the
    leading verb and nothing else. It gets past the classifier and is refused by SQLite,
    which is what makes belt and braces here a measurement rather than a habit.
    """
    said = refusal(call(mapped, "query",
                        {"sql": "WITH x AS (SELECT 1) DELETE FROM routines"}))
    assert "readonly" in said, said
    after = payload(call(mapped, "query", {"sql": "SELECT count(*) AS n FROM routines"}))
    assert after["results"][0]["n"] > 0, "the map was emptied by a tool that runs reads"


# ---- the other map, and the one that is not there --- #


def test_programs_lists_what_is_under_the_root_and_which_is_open(mapped: Path) -> None:
    body = payload(call(mapped, "programs"))
    assert [p["program"] for p in body["programs"]] == ["sample"]
    assert body["programs"][0]["open"] is True
    assert body["opened"] == "sample"


def test_open_with_nothing_named_refuses_rather_than_doing_nothing(mapped: Path) -> None:
    """A call that changes nothing and reports success is the worst of the three outcomes."""
    assert "name a program" in refusal(call(mapped, "open", {}))


def test_opening_a_program_that_is_not_there_names_what_is(mapped: Path) -> None:
    """A refusal has to name something the reader can act on, and a program name is not
    guessable (rule 89)."""
    said = refusal(call(mapped, "open", {"program": "nonesuch"}))
    assert "sample" in said, said


# ---- resources --- #


def test_the_schema_is_served_so_an_agent_can_write_its_own_sql(mapped: Path) -> None:
    """Without it the escape hatch is a door in the dark."""
    listed = drive([HELLO, READY,
                    {"jsonrpc": "2.0", "id": 3, "method": "resources/list"}],
                   mapped / "sample").by_id(3)["result"]["resources"]
    assert resources.SCHEMA_URI in {r["uri"] for r in listed}

    read = drive([HELLO, READY,
                  {"jsonrpc": "2.0", "id": 4, "method": "resources/read",
                   "params": {"uri": resources.SCHEMA_URI}}],
                 mapped / "sample").by_id(4)["result"]["contents"]
    assert "CREATE TABLE" in read[0]["text"]
    assert "routines" in read[0]["text"]


def test_a_generated_document_is_served_as_readable_prose(mapped: Path) -> None:
    """The rows carry graph node ids the dashboard selects with; none of that survives a
    pipe, so what crosses is the document."""
    uri = resources.DOCUMENT_PREFIX + "entrypoints"
    read = drive([HELLO, READY,
                  {"jsonrpc": "2.0", "id": 5, "method": "resources/read",
                   "params": {"uri": uri}}], mapped / "sample").by_id(5)["result"]
    text = read["contents"][0]["text"]
    assert text.startswith("# "), text[:80]
    assert "|" in text, "the sections rendered no table at all"
    assert "sample" in text


def test_a_uri_nobody_serves_is_refused_by_name(mapped: Path) -> None:
    """Never an empty `contents`: a resource that exists and holds nothing is a different
    fact from one that does not exist, and a client shown the first stops looking."""
    reply = drive([HELLO, READY,
                   {"jsonrpc": "2.0", "id": 6, "method": "resources/read",
                    "params": {"uri": "dunneflow://nope/nope"}}],
                  mapped / "sample").by_id(6)
    assert reply["error"]["code"] == jsonrpc.INVALID_PARAMS


# ---- boot --- #


def test_a_directory_holding_no_map_is_a_cold_root_rather_than_a_failure(
        tmp_path: Path) -> None:
    """Where a double-clicked application begins, and `serve`'s own test for it.

    `where()` returns `(given, given)` for a directory holding no map, which is what makes
    it a *root* — so this is not a mistake to refuse but the state `programs` and, later,
    `analyze` exist for. A server that refused it would refuse the one case an agent is
    most likely to start from.
    """
    empty = tmp_path / "fresh"
    empty.mkdir()
    listed = payload(drive([HELLO, READY, {
        "jsonrpc": "2.0", "id": 8, "method": "tools/call",
        "params": {"name": "programs", "arguments": {}}}], empty).by_id(8))
    assert listed["programs"] == [], listed


def test_a_tool_that_needs_a_map_says_so_and_names_what_to_do(tmp_path: Path) -> None:
    """`NothingOpen` carries no message of its own — the dashboard's sentence lives in its
    handler, so `why()` over one yields `NothingOpen: ` and nothing else. That is a refusal
    with no reason in it, which is the empty answer the gate exists to prevent (rule 49)."""
    empty = tmp_path / "fresh"
    empty.mkdir()
    said = refusal(drive([HELLO, READY, {
        "jsonrpc": "2.0", "id": 8, "method": "tools/call",
        "params": {"name": "overview", "arguments": {}}}], empty).by_id(8))
    assert "nothing is open" in said, said
    assert "programs" in said and "open" in said, (
        "the refusal names nothing that can act on it (rule 89)"
    )


def test_a_revision_that_is_not_there_is_refused_before_a_single_message(
        mapped: Path) -> None:
    """The boot refusal: a server that handshakes cheerfully and then fails every call
    gives an agent nothing to act on. A sentence on stderr, a non-zero exit, and **nothing
    at all on the protocol channel**."""
    done = subprocess.run(
        self_argv("mcp", str(mapped / "sample"), "--revision", "1999-01-01T00:00:00Z"),
        input="", capture_output=True, text=True, timeout=120)
    assert done.returncode == 2, done
    assert done.stdout == "", (
        f"it wrote to the protocol channel before refusing: {done.stdout!r}"
    )
    assert "1999-01-01" in done.stderr, done.stderr


# ---- the one thing here that writes --- #
#
# The stop *rungs* are `tests/test_analysis.py`'s and are not re-tested here: SIGTERM then
# SIGKILL to a group of the child's own, a console break then `taskkill /F /T` on Windows,
# and the eleven pool workers that hold stdout open if you signal the parent alone. This
# file owns the tool, not the machinery, and a test that raced a real child to assert a
# rung would be flaky about something already pinned deterministically next door.


def test_an_analysis_returns_a_handle_rather_than_blocking(tmp_path: Path) -> None:
    """A long job may not be a blocked call, and the map it makes must be openable after.

    The whole loop, over one pipe: a cold root, `analyze`, poll to `done`, `open` what was
    made, and read a fact out of it. The boundaries are the assertion that matters — a map
    that opens and holds nothing would pass every step before this one.
    """
    root = tmp_path / "maps"
    root.mkdir()
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "m.py").write_text(
        'import os\n\n\ndef f(p):\n    return os.environ["X"] + open(p).read()\n',
        encoding="utf-8")

    with driving(root) as session:
        started = session.tool("analyze", {"path": str(tree), "name": "tiny",
                                           "docs": False})
        assert started["started"] is True
        assert started["program"] == "tiny"

        for _ in range(120):
            state = session.tool("analysis_status")
            if state.get("state") in {"done", "failed", "stopped"}:
                break
            time.sleep(0.25)
        assert state["state"] == "done", state
        assert state["files"] == 1 and state["routines"] >= 1, state

        assert session.tool("open", {"program": "tiny"})["opened"] is True
        touched = session.tool("touches", {"routine": "f"})
        assert set(touched["routines"][0]["boundary_kinds"]) == {"ENV", "FILE"}


def test_a_second_analysis_is_refused_and_told_what_is_running(tmp_path: Path) -> None:
    """One slot, and the refusal names the job holding it (rule 89).

    A refusal that said only *"one is already running"* would be true and a dead end: the
    one thing the caller may want to do about it is stop that one.

    **In-process, and the first analysis is held rather than raced.** This drove the real
    server over the pipe and started a real analysis of a one-file tree, then asked for a
    second immediately -- so a first that finished first left nothing to refuse, and the
    test failed once inside a full suite and could not be reproduced. There is no way to
    hold a child open from the far side of a pipe, so the refusal is asked of the object
    that makes it: `Session.analyze`, with `start_analysis`'s `run` seam holding the slot
    until this test lets go. The wire is `test_mcp.py`'s subject and is not re-proved here.
    """
    root = tmp_path / "maps"
    root.mkdir()
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "m.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    session = Session(root)
    holding = threading.Event()
    let_go = threading.Event()

    def held(**_kw: Any) -> None:
        holding.set()
        let_go.wait(timeout=30)

    try:
        assert session.live.start_analysis("first", source=tree, out_root=root,
                                           docs=False, run=held) is True
        assert holding.wait(timeout=10), "the first analysis never started"

        with pytest.raises(Refused) as caught:
            session.analyze(str(tree), name="second", docs=False)
        said = str(caught.value)
        assert "already running" in said, said
        assert "first" in said, said
        assert "analysis_stop" in said, said
    finally:
        let_go.set()
        session.close()


def test_stopping_nothing_is_refused_rather_than_reported_as_a_stop(
        tmp_path: Path) -> None:
    """*Nothing was running* and *I stopped it* are different facts."""
    root = tmp_path / "maps"
    root.mkdir()
    with driving(root) as session:
        assert "no analysis is running" in session.refused("analysis_stop")


def test_analysing_a_relative_path_is_refused_by_the_same_check_the_dialog_asks(
        tmp_path: Path) -> None:
    """Every refusal here is `analysis.check`'s, so no two surfaces can disagree (rule 41)."""
    root = tmp_path / "maps"
    root.mkdir()
    with driving(root) as session:
        assert session.refused("analyze", {"path": "some/relative/tree"})


def test_analysing_into_the_program_being_read_is_refused(mapped: Path) -> None:
    """`Store._discard_if_stale` drops every table of a graph written by another build, and
    this server is holding that graph open — so an analysis aimed here can empty the map
    under a live reader.

    It is also what `serving_dir` exists for: `None` when nothing is open, never the output
    root standing in for a program, because the root's basename is a real name and would
    refuse the first analysis anybody ever asked for (rule 30).
    """
    with driving(mapped / "sample") as session:
        said = session.refused("analyze", {"path": str(mapped), "name": "sample"})
        assert said, "analysing over the open map was allowed"
