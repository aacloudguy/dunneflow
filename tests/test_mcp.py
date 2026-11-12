"""The MCP transport, driven over a real pipe — because nothing else can see it.

**Every test here spawns `dunneflow mcp` as a subprocess.** That is rule 91's lesson
applied before it can be paid for again: a handler called directly is correct in a frame
that has no stdout, and the failures this transport is actually exposed to all live in the
bytes. A stray `print` anywhere in the reachable code puts a line on the protocol channel
that is not a message; a `json.dumps(..., indent=2)` turns one message into several and
breaks the framing for good; an encoding left to the locale turns every em dash into a
`UnicodeEncodeError` raised from inside the writer. None of the three is visible to a test
that calls `Server._handle` and reads the return value. `tests/test_cold_start.py` binds a
real port for the same reason.

The lifecycle test is here because the defect it pins was found this way and no other way:
`notifications/initialized` was gated behind the flag it sets, so it was refused, the flag
stayed false, and every subsequent method was refused for ever — with a refusal that was
perfectly correct on its face.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from dunneflow.mcp import jsonrpc, server
from dunneflow.runtime import self_argv

HELLO = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": server.LATEST,
                    "clientInfo": {"name": "the suite", "version": "0"}}}
READY = {"jsonrpc": "2.0", "method": "notifications/initialized"}


class Session:
    """What one run of the server said, split by channel."""

    def __init__(self, replies: list[dict[str, Any]], out: str, err: str) -> None:
        self.replies = replies
        self.out = out
        self.err = err

    def by_id(self, request_id: Any) -> dict[str, Any]:
        for reply in self.replies:
            if reply.get("id") == request_id:
                return reply
        raise AssertionError(f"nothing answered id {request_id!r}: {self.replies}")


def drive(messages: list[Any], where: Path | None = None) -> Session:
    """Feed these lines to a real `dunneflow mcp` and read both channels back.

    A raw string is sent as written, so a test can post something that is not JSON at all.
    """
    lines = "".join(
        (m if isinstance(m, str) else json.dumps(m)) + "\n" for m in messages)
    argv = self_argv("mcp", *( [str(where)] if where else [] ))
    # UTF-8 both ways, said rather than inherited: `text=True` alone decodes with the
    # console's code page on Windows, and the em dash test then reads its own reader's
    # mojibake as the server's fault.
    done = subprocess.run(argv, input=lines, capture_output=True, encoding="utf-8",
                          timeout=120)
    assert done.returncode == 0, f"the server exited {done.returncode}: {done.stderr}"

    replies = []
    for n, line in enumerate(done.stdout.splitlines(), 1):
        if not line.strip():
            continue
        try:
            replies.append(json.loads(line))
        except ValueError as exc:  # noqa: PERF203 — the message is the point
            raise AssertionError(
                f"stdout line {n} is not a JSON-RPC message, so something wrote to the "
                f"protocol channel: {line!r} ({exc})") from exc
    return Session(replies, done.stdout, done.stderr)


class Driving:
    """A session held open across several calls, for the tools that share state.

    `drive` spawns a process per run, which is right for everything whose answer depends
    only on the message. It is wrong for `analyze`, `analysis_status` and `analysis_stop`,
    whose whole subject is one slot on one `_Live` — asked down three separate pipes they
    would each get a fresh server and every answer would be *nothing is running*, which is
    a test that passes while the feature does not exist.
    """

    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self._proc = proc
        self._next = 0

    def send(self, message: dict[str, Any]) -> None:
        assert self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(message) + "\n")
        self._proc.stdin.flush()

    def read(self) -> dict[str, Any]:
        assert self._proc.stdout is not None
        line = self._proc.stdout.readline()
        assert line, "the server closed its output with a reply outstanding"
        try:
            return dict(json.loads(line))
        except ValueError as exc:
            raise AssertionError(
                f"a line on the protocol channel is not a message: {line!r}") from exc

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next += 1
        self.send({"jsonrpc": "2.0", "id": self._next, "method": method,
                   "params": params or {}})
        reply = self.read()
        assert reply["id"] == self._next, f"replies arrived out of order: {reply}"
        return reply

    def tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        """One tool call that must succeed, decoded."""
        reply = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        assert "error" not in reply, reply
        result = reply["result"]
        assert result["isError"] is False, result["content"][0]["text"]
        return json.loads(result["content"][0]["text"])

    def refused(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """One tool call that must refuse, as the sentence it refused with."""
        reply = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        assert "error" not in reply, f"a refusal became a protocol error: {reply}"
        assert reply["result"]["isError"] is True, reply
        return str(reply["result"]["content"][0]["text"])


@contextlib.contextmanager
def driving(where: Path) -> Iterator[Driving]:
    """A handshaken session on `where`, closed and checked on the way out."""
    proc = subprocess.Popen(self_argv("mcp", str(where)), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            bufsize=1)
    session = Driving(proc)
    try:
        session.request("initialize", {"protocolVersion": server.LATEST})
        session.send(READY)
        yield session
    finally:
        assert proc.stdin is not None
        proc.stdin.close()
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:  # pragma: no cover - only on a wedged server
            proc.kill()
            raise
    assert proc.returncode == 0, f"the server exited {proc.returncode}"


@pytest.fixture()
def mapped(tmp_path: Path) -> Path:
    """An output root with nothing in it. The transport does not need a map to answer."""
    root = tmp_path / "maps"
    root.mkdir()
    return root


# ---- the channel --- #


def test_stdout_carries_protocol_and_nothing_else(mapped: Path) -> None:
    """`drive` asserts it line by line; this states the claim in its own right.

    The prose the command has to say -- which directory it opened, what the client asked
    for -- must be on stderr, and this is what says it is somewhere rather than nowhere.
    """
    session = drive([HELLO, READY, {"jsonrpc": "2.0", "id": 2, "method": "ping"}], mapped)
    assert len(session.replies) == 2, session.replies
    assert all("jsonrpc" in r for r in session.replies)
    assert str(mapped) in session.err, (
        "the server never said which directory it opened, on either channel"
    )


def test_every_reply_is_one_line(mapped: Path) -> None:
    """The framing *is* the newline, so a message containing one is two messages.

    `json.dumps` cannot emit a bare newline -- until somebody passes `indent`, which reads
    as a tidy-up and silently ends the session's ability to be parsed.
    """
    session = drive([HELLO, READY, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}],
                    mapped)
    assert len(session.out.rstrip("\n").split("\n")) == len(session.replies)


def test_a_sentence_with_an_em_dash_survives_the_wire(mapped: Path) -> None:
    """Rule 91, pressed rather than assumed.

    The refusal below is written with an em dash, as every sentence in this project is.
    It reaches the client or it does not, and only the wire knows -- an
    `expected str` assertion inside the process would pass over a stream that then raises
    `UnicodeEncodeError` on write, several frames from anything that could explain it.
    """
    session = drive([{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}], mapped)
    message = session.by_id(1)["error"]["message"]
    assert "—" in message, f"the em dash did not survive: {message!r}"


# ---- the lifecycle --- #


def test_the_handshake_agrees_a_version_and_names_the_server(mapped: Path) -> None:
    session = drive([HELLO], mapped)
    result = session.by_id(1)["result"]
    assert result["protocolVersion"] == server.LATEST
    assert result["serverInfo"]["name"] == server.SERVER_NAME
    assert result["serverInfo"]["version"], "the server does not say which build it is"


@pytest.mark.parametrize("asked,answered", [
    (server.LATEST, server.LATEST),
    ("2024-11-05", "2024-11-05"),          # an older revision we know: its own back
    ("2099-01-01", server.LATEST),         # one we do not: ours, for the client to judge
    (None, server.LATEST),                 # none offered at all
])
def test_the_protocol_version_is_negotiated_rather_than_echoed(
        mapped: Path, asked: str | None, answered: str) -> None:
    """A server that echoes whatever it was sent has agreed to a protocol it never heard of.

    The specification's own answer for an unsupported version is to reply with one we do
    support and let the client decide whether to go on — which is three outcomes collapsed
    into two only if you forget that the client gets a vote (rule 30).
    """
    hello = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {} if asked is None else {"protocolVersion": asked}}
    assert drive([hello], mapped).by_id(1)["result"]["protocolVersion"] == answered


def test_the_notification_that_ends_the_handshake_is_not_gated_behind_it(
        mapped: Path) -> None:
    """The defect this file was written to catch, and it is a whole-session failure.

    `notifications/initialized` sets the flag that opens the rest of the table. Behind
    that flag it was refused — correctly, on its face, because the session really had not
    been initialised — and the session could then never be initialised at all. Every
    handler was right; only the order was wrong, which is why no unit test saw it.
    """
    session = drive([HELLO, READY, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}],
                    mapped)
    assert "error" not in session.by_id(2), (
        "the session never became ready, so everything after the handshake is refused"
    )
    assert "tools" in session.by_id(2)["result"]


def test_a_method_asked_before_the_handshake_is_refused_by_name(mapped: Path) -> None:
    """Refusing is the point; refusing *visibly* is the rest of it (rule 49)."""
    reply = drive([{"jsonrpc": "2.0", "id": 7, "method": "tools/list"}], mapped).by_id(7)
    assert reply["error"]["code"] == jsonrpc.INVALID_REQUEST
    assert "initialize" in reply["error"]["message"]


def test_a_notification_is_never_answered(mapped: Path) -> None:
    """JSON-RPC forbids it, and a client receiving one has a reply to a request it never
    made — which, for a client tracking outstanding ids, is an id it cannot account for."""
    session = drive([HELLO, READY, READY], mapped)
    assert [r["id"] for r in session.replies] == [1], session.replies


def test_a_notification_that_fails_is_logged_rather_than_answered(mapped: Path) -> None:
    """The rule holds hardest in the case where something has already gone wrong."""
    session = drive([{"jsonrpc": "2.0", "method": "notifications/nonesuch"}], mapped)
    assert session.replies == [], session.replies
    assert "nonesuch" in session.err, "it failed silently on both channels"


# ---- refusals --- #


def test_a_line_that_is_not_json_is_refused_under_a_null_id(mapped: Path) -> None:
    """There is no id to answer under, so JSON-RPC's answer is `null` — the one case."""
    session = drive(["this is not json"], mapped)
    assert session.replies[0]["id"] is None
    assert session.replies[0]["error"]["code"] == jsonrpc.PARSE_ERROR


def test_a_refusal_answers_under_the_id_the_client_sent(mapped: Path) -> None:
    """A detectable id is answered under, never under null.

    JSON-RPC reserves the null id for the case where the id could not be *detected* — a
    line that is not JSON. Every other refusal here happens on an object whose `id` is
    sitting in plain view, and answering those under null costs the client the one thing
    it needs to match a reply to a call. A request it cannot account for reads as one that
    was never answered, which is a hang rather than a refusal.
    """
    session = drive([{"jsonrpc": "1.0", "id": "abc", "method": "ping"}], mapped)
    assert session.replies[0]["id"] == "abc", session.replies


def test_a_malformed_notification_is_still_a_notification(mapped: Path) -> None:
    """The one rule a refusal is not an excuse to break.

    A message carrying no id and a `notifications/` method is a notification even when the
    rest of it is wrong, so it gets silence — and a client tracking outstanding ids is not
    handed a reply to a request it never made at the moment it is least able to place one.
    """
    session = drive([{"jsonrpc": "1.0", "method": "notifications/initialized"}], mapped)
    assert session.replies == [], session.replies
    assert "refused" in session.err, "it was dropped without a word on either channel"


@pytest.mark.parametrize("message,code", [
    ({"jsonrpc": "2.0", "id": 1, "method": "nosuchthing"}, jsonrpc.METHOD_NOT_FOUND),
    ({"jsonrpc": "1.0", "id": 1, "method": "ping"}, jsonrpc.INVALID_REQUEST),
    ({"id": 1, "method": "ping"}, jsonrpc.INVALID_REQUEST),
    ({"jsonrpc": "2.0", "id": 1}, jsonrpc.INVALID_REQUEST),
    ({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1, 2]},
     jsonrpc.INVALID_PARAMS),
])
def test_each_malformed_message_gets_the_code_that_describes_it(
        mapped: Path, message: dict[str, Any], code: int) -> None:
    """One generic code for every refusal tells a client the wrong thing about its message.

    Positional `params` is the one worth naming: it is legal JSON-RPC, is used nowhere in
    MCP, and read as *no arguments at all* would be a call that looks like it worked
    (rule 49).
    """
    assert drive([message], mapped).by_id(1)["error"]["code"] == code


def test_the_session_survives_every_refusal_and_keeps_answering(mapped: Path) -> None:
    """A server that dies on one bad message leaves the client on a pipe that never
    answers, which looks exactly like a hang and names nothing."""
    session = drive([
        "{{{ not json",
        {"jsonrpc": "2.0", "id": 1, "method": "nosuchthing"},
        HELLO, READY,
        {"jsonrpc": "2.0", "id": 2, "method": "ping"},
    ], mapped)
    assert "error" not in session.by_id(2), "the session did not survive the bad messages"


# ---- the table and the handlers are two halves of one contract --- #


def test_every_method_in_the_table_has_a_handler_and_every_handler_is_in_the_table(
) -> None:
    """Both directions, because either alone passes while the feature is broken.

    A name in the table with nothing behind it raises `AttributeError` inside the loop and
    is reported as an internal error to the client. A handler that nothing routes to is
    dead code that reads as a working feature (design rule 16, rule 44).
    """
    table = server.Server.METHODS
    for method, attribute in table.items():
        assert callable(getattr(server.Server, attribute, None)), (
            f"{method} routes to {attribute!r}, which is not a method"
        )
    # Written out rather than derived, and that is the guard. `Server` has other private
    # methods -- `_handle`, `_dispatch`, `_fail`, `_content` -- and no convention tells a
    # handler from a helper, so anything derived would either miss one or admit all of
    # them. A list that has to be edited when a method is added is the cost of noticing
    # when one is added and routed to nothing.
    handlers = {"_initialize", "_initialized", "_ping", "_tools_list", "_tools_call",
                "_resources_list", "_resources_read"}
    assert set(table.values()) == handlers, (
        f"routed but not expected: {set(table.values()) - handlers}; "
        f"expected but not routed: {handlers - set(table.values())}"
    )


def test_the_handshake_exceptions_are_all_real_methods() -> None:
    """A name in the exception list that is not in the table exempts nothing, silently."""
    unknown = server.Server.BEFORE_INITIALIZE - set(server.Server.METHODS)
    assert not unknown, f"these are exempted from a handshake they never reach: {unknown}"


def test_the_handshake_says_whose_words_the_answers_are() -> None:
    """Every tool quotes the program that was read, and the reader is a model: a comment
    that addresses it is a fact about that program. Said in `initialize`, which is the one
    place the protocol gives a server to say something before any tool is called."""
    said = drive([HELLO]).by_id(HELLO["id"])["result"]["instructions"]
    assert "verbatim" in said and "never an instruction" in said
