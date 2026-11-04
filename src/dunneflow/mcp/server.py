"""The method table, the lifecycle, and the loop — the one place that knows both sides.

`jsonrpc.py` below it knows messages and not MCP; `tools.py` beside it knows the map and
not the wire. This module is where a method name becomes a call, and it is deliberately
the only place either fact is written down.

**The loop may not raise.** A server that dies on one bad message takes the session with
it and leaves the client waiting on a pipe that will never answer — which looks exactly
like a hang and names nothing. So every handler runs inside a catch, and an unexpected
exception becomes an error object with `serve.why(exc)` in it. That sentence is the
dashboard's, used verbatim: `StaleGraphError` and `UnfinishedMapError` are whole sentences
written for a person, and prefixing them with a Python class name puts the wrong word
first (rule 91's neighbour).
"""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO

from ..runtime import tool_version
from . import Refused, jsonrpc, resources, tools
from .jsonrpc import Malformed, Request
from .session import Session

#: The protocol revisions this server knows, newest first. A client asking for one of
#: these is answered with **its own**; a client asking for anything else is answered with
#: the newest here, which is what the specification says to do and lets it decide whether
#: to go on. Never silently treated as the newest: the version a session runs under is a
#: fact both ends have to agree on out loud, and a server that echoes back whatever it was
#: sent has agreed to a protocol it has never heard of (rule 30).
SUPPORTED: tuple[str, ...] = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST = SUPPORTED[0]

SERVER_NAME = "dunneflow"


def _looks_like_a_notification(line: str) -> bool:
    """Did a refused line at least *claim* to be a notification?

    Asked only where the message could not be parsed into a request, which is the one
    place the question cannot be answered properly. A line that is not JSON gets a null-id
    error, as the specification says. A line that is JSON, is an object, carries a method
    beginning `notifications/` and carries no id is answered with **silence**, because
    replying to a notification is the one thing a server may never do and a refusal is not
    an excuse to do it.

    Deliberately narrow: anything it cannot read confidently gets the error, because a
    client that sent a real request and hears nothing has no way to find out why.
    """
    try:
        obj = json.loads(line)
    except ValueError:
        return False
    return (isinstance(obj, dict) and "id" not in obj
            and isinstance(obj.get("method"), str)
            and obj["method"].startswith("notifications/"))


class Server:
    """One stdio session.

    Constructed with its streams rather than reaching for `sys.*`, so a test can drive it
    over a pair of pipes — though the test that matters drives it as a **subprocess**,
    because the failure this transport is most exposed to is a stray write to stdout and
    no in-process test can see one.
    """

    #: Method name -> the attribute that answers it. A table rather than an if-ladder, on
    #: `_Handler`'s precedent one surface over: a method that exists is one line, and a
    #: method that does not is `METHOD_NOT_FOUND` by construction rather than by an `else`
    #: somebody has to remember to write.
    METHODS: dict[str, str] = {
        "initialize": "_initialize",
        "notifications/initialized": "_initialized",
        "ping": "_ping",
        "tools/list": "_tools_list",
        "tools/call": "_tools_call",
        "resources/list": "_resources_list",
        "resources/read": "_resources_read",
    }

    #: The methods answerable before `initialize` has been received, named as the
    #: **exceptions** so that a method added tomorrow needs the handshake by default and
    #: refuses visibly rather than answering out of a session that has not started. That
    #: is `GET_WITHOUT_BASE`'s shape, and it is the same argument (rule 49).
    #:
    #: `notifications/initialized` is on the list because it is **the message that ends
    #: the exception** -- gated behind the flag it sets, it was refused, the flag stayed
    #: false, and every later method was refused for ever. The refusal was even correct
    #: on its face: the session genuinely had not been initialised yet. Found by driving
    #: the server over a pipe and not by any unit test, because each handler was right on
    #: its own and only the order was wrong.
    BEFORE_INITIALIZE: frozenset[str] = frozenset(
        {"initialize", "notifications/initialized", "ping"})

    def __init__(self, stdin: TextIO, stdout: TextIO, session: Session | None = None,
                 log: Callable[[str], None] = lambda _msg: None) -> None:
        self._in = stdin
        self._out = stdout
        self._log = log
        self._ready = False
        self._version = LATEST
        self._session = session

    # ---- the loop --- #

    def serve(self) -> int:
        """Read until the input ends. Returns an exit code.

        EOF is the ordinary way an MCP session finishes: the client closes the pipe, and
        there is nothing to say about it. A client that vanishes mid-request is the same
        event one line earlier.
        """
        for line in self._in:
            if not line.strip():
                continue
            self._handle(line)
        self._log("input closed; the session is over")
        return 0

    def _handle(self, line: str) -> None:
        """One line, all the way to a written reply or to a deliberate silence."""
        try:
            request = jsonrpc.parse(line)
        except Malformed as exc:
            # A line that is not JSON has no id to answer under, and JSON-RPC's answer for
            # that is a null one. A *malformed object* usually does have one, and `parse`
            # carries it out — see `Malformed`. And a malformed **notification** is still a
            # notification: nothing may be written back at all.
            self._log(f"refused a message: {exc}")
            if exc.has_id or exc.request_id is not None:
                jsonrpc.write(self._out, jsonrpc.error(exc.request_id, exc.code, str(exc),
                                                       exc.data))
            elif not _looks_like_a_notification(line):
                jsonrpc.write(self._out, jsonrpc.error(None, exc.code, str(exc), exc.data))
            return

        try:
            payload = self._dispatch(request)
        except Malformed as exc:
            self._fail(request, exc.code, str(exc), exc.data)
            return
        except Exception as exc:  # noqa: BLE001 — the loop may not raise; see the docstring
            from ..web.serve import why
            self._log(f"{request.method} failed: {exc!r}")
            self._fail(request, jsonrpc.INTERNAL_ERROR, why(exc),
                       {"method": request.method, "exception": type(exc).__name__})
            return

        if request.is_notification:
            # JSON-RPC forbids replying to one, and a server that does sends the client a
            # response to a request it never made.
            return
        jsonrpc.write(self._out, jsonrpc.result(request.id, payload))

    def _fail(self, request: Request, code: int, message: str, data: Any = None) -> None:
        """An error reply, unless the thing that failed was a notification.

        A failed notification is logged and not answered. The alternative — answering it
        because something went wrong — breaks the same rule for the same message, and does
        it at the moment the client is least able to make sense of an extra frame.
        """
        if request.is_notification:
            self._log(f"{request.method} (a notification) failed: {message}")
            return
        jsonrpc.write(self._out, jsonrpc.error(request.id, code, message, data))

    def _dispatch(self, request: Request) -> Any:
        attribute = self.METHODS.get(request.method)
        if attribute is None:
            raise Malformed(jsonrpc.METHOD_NOT_FOUND,
                            f"this server has no method called {request.method!r}",
                            {"known": sorted(self.METHODS)})
        if not self._ready and request.method not in self.BEFORE_INITIALIZE:
            raise Malformed(
                jsonrpc.INVALID_REQUEST,
                f"{request.method} was asked before the session was initialised — send "
                f"initialize first",
                {"method": request.method})
        handler: Callable[[dict[str, Any]], Any] = getattr(self, attribute)
        return handler(request.params)

    # ---- the lifecycle --- #

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """The handshake. Agrees a protocol version and says what this server can do.

        The client's requested version is **logged**, because which one Claude Code
        actually sends is a fact about the world rather than about this code, and the
        cheapest way to learn it is to have the first real session write it down.
        """
        asked = params.get("protocolVersion")
        self._version = asked if asked in SUPPORTED else LATEST
        client = params.get("clientInfo", {})
        name = client.get("name", "an unnamed client") if isinstance(client, dict) else "?"
        self._log(f"{name} asked for protocol {asked!r}; answering {self._version!r}")
        return {
            "protocolVersion": self._version,
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {"subscribe": False, "listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": tool_version()},
        }

    def _initialized(self, _params: dict[str, Any]) -> None:
        """The client's notification that it is ready. Nothing is written back.

        The flag is `_ready` and not `_initialized`, which is what it was first called:
        the handler for this notification has that name, so the assignment replaced the
        method with `True` and the second session on one process answered
        `notifications/initialized` with a `TypeError`. An attribute and a method share
        one namespace, and neither the suite nor mypy said so.
        """
        self._ready = True
        self._log("initialised")
        return None

    def _ping(self, _params: dict[str, Any]) -> dict[str, Any]:
        """An empty result is the whole of the answer."""
        return {}

    # ---- tools --- #

    @property
    def session(self) -> Session:
        """The map this server is reading.

        Refused rather than built on demand. A server constructed without one is a
        programming error here, not a reader's mistake, and answering out of a session
        nobody opened is the shape rule 49 warns about.
        """
        if self._session is None:
            raise Malformed(jsonrpc.INTERNAL_ERROR,
                            "this server was started without a map to read")
        return self._session

    def _tools_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        """What this server can be asked to do.

        Straight off `tools.TOOLS`, so the list and the bodies are one table. A name here
        with nothing behind it is a control wired to nothing, which looks exactly like one
        that works (design rule 16), and a body nothing lists is unreachable — the suite
        asserts both directions because either alone passes while the feature is broken.
        """
        return {"tools": [tool.as_mcp() for tool in tools.TOOLS]}

    def _tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run one tool.

        **A refusal is a successful call carrying `isError`, not a JSON-RPC error**, and
        the difference is who the sentence is for. A JSON-RPC error is a fault in the
        *protocol* — a method that does not exist, a message that is not a message — and a
        client handles it. A stale map, an unfinished one, a rejected statement: those are
        answers to the question that was asked, and MCP puts them in front of the model,
        which is the only thing that can do anything about them.

        The sentence is `serve.why(exc)` verbatim, so `StaleGraphError` and
        `UnfinishedMapError` arrive as the whole sentences they were written as, with no
        Python class name in front (rule 91's neighbour).
        """
        from ..web.serve import why

        name = params.get("name")
        if not isinstance(name, str) or name not in tools.BY_NAME:
            raise Malformed(jsonrpc.INVALID_PARAMS,
                            f"this server has no tool called {name!r}",
                            {"known": [t.name for t in tools.TOOLS]})
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise Malformed(jsonrpc.INVALID_PARAMS, "arguments must be an object",
                            {"got": type(arguments).__name__})

        tool = tools.BY_NAME[name]
        try:
            payload = tool.body(self.session, arguments)
        except Refused as exc:
            # Already a sentence written for whoever asked; `why` would put a class name
            # in front of it, which is the one thing that sentence must not have.
            self._log(f"{name} refused: {exc}")
            return self._content(str(exc), is_error=True)
        except Exception as exc:  # noqa: BLE001 — every refusal is an answer; see above
            self._log(f"{name} failed: {exc!r}")
            return self._content(why(exc), is_error=True)
        return self._content(payload)

    def _content(self, payload: Any, *, is_error: bool = False) -> dict[str, Any]:
        """A tool result, as text.

        **Text only, and no `structuredContent`.** That field arrived in the 2025-06-18
        revision and this server negotiates down to 2024-11-05, so sending it would make
        the shape of an answer depend on which version the handshake settled — two answers
        to one question, decided by something the caller never sees. Indented JSON, because
        the reader is a model: the newlines live inside a JSON string in the message and
        the framing is untouched.
        """
        text = payload if isinstance(payload, str) else json.dumps(
            payload, indent=2, ensure_ascii=False, default=str)
        return {"content": [{"type": "text", "text": text}], "isError": is_error}

    # ---- resources --- #

    def _resources_list(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"resources": resources.listing(self.session)}

    def _resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """One resource by URI.

        A URI nobody serves is `INVALID_PARAMS` and not an empty `contents`: a resource
        that exists and holds nothing is a different fact from one that does not exist, and
        a client shown the first for the second stops looking (rule 30).
        """
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri:
            raise Malformed(jsonrpc.INVALID_PARAMS, "name a uri to read")
        try:
            return {"contents": resources.read(self.session, uri)}
        except KeyError as exc:
            raise Malformed(jsonrpc.INVALID_PARAMS, str(exc.args[0])) from exc


def serve(given: Path, revision: str | None = None,
          log: Callable[[str], None] = lambda _msg: None,
          allow_unfinished: bool = False) -> int:
    """Open the map and run one session on this process's own streams.

    **stdin is decoded here**, because `cli.speak_utf8` settles stdout and stderr and
    leaves stdin alone — every other command reads files and arguments, and this is the
    only one that reads the standard input at all. MCP's transport is UTF-8 by
    specification, so the locale does not get a vote.

    A stream a caller has replaced is left exactly as it is, which is `speak_utf8`'s own
    rule: this decides an encoding and may not decide who owns the stream.

    The session is built **before** the loop starts, so a map that cannot be opened is a
    refusal on the terminal with a non-zero exit rather than a server that handshakes
    cheerfully and then fails every call. That is `serve`'s own boot order.
    """
    with contextlib.suppress(AttributeError, OSError, ValueError):
        if (getattr(sys.stdin, "encoding", "") or "").lower().replace("-", "") != "utf8":
            sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

    session = Session(given, revision, log=log, allow_unfinished=allow_unfinished)
    try:
        return Server(sys.stdin, sys.stdout, session, log=log).serve()
    finally:
        session.close()
