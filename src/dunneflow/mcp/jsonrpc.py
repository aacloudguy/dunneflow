"""JSON-RPC 2.0 over newline-delimited stdio — the frame, and nothing above it.

This module knows about messages. It knows nothing about DunneFlow, about MCP's method
names, or about what any of them mean, which is `server.py`'s business and `tools.py`'s.
The split is `prose.js`' boundary: a thing that turns bytes into structure has no opinion
about the structure's subject.

**Newline-delimited, not Content-Length framed.** MCP's stdio transport is one JSON object
per line; LSP's is a header block with a byte count. They are close enough to look alike in
a summary and are not interchangeable, and a server that guesses wrong produces a client
that hangs with nothing on either channel.

**stdout carries protocol and nothing else.** That is the same two-channel discipline
`--progress-json` already proved across a process boundary, and here it is stricter: a
progress reader skips a line it cannot parse, and an MCP client is entitled to fail the
session. One stray `print` anywhere in the reachable code is the whole failure mode, and
nothing but the wire can see it — which is why `tests/test_mcp.py` reads every line back
and parses it rather than testing handlers directly (rule 91).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TextIO

VERSION = "2.0"

# The five codes JSON-RPC 2.0 defines. Named rather than written at the raise site, because
# a code is what a client switches on and a typo in one is a different error arriving.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class Malformed(Exception):
    """A message this layer refuses, carrying the code the reply must use.

    `message` is the sentence a person reads; `data` is for the machine. Rule 91 decides
    which way round: a channel that takes a sentence and a channel that takes detail are
    two channels, and putting the sentence in `data` hides it from every client that shows
    only `message`.

    **And it carries the id when the id could be read**, which is not a detail. JSON-RPC
    says a reply must use a null id only where the id could not be *detected* — a line
    that is not JSON at all. Every other refusal here happens on an object whose `id` is
    sitting right there, and answering those under null too costs the client the one thing
    it needs to match a reply to a call: a request it can never account for reads as a
    request that was never answered, which is a hang rather than a refusal.
    """

    def __init__(self, code: int, message: str, data: Any = None, *,
                 request_id: Any = None, has_id: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
        self.request_id = request_id
        self.has_id = has_id


@dataclass(frozen=True, slots=True)
class Request:
    """One incoming call, or one notification.

    **A notification is not a request with a missing id**, and the difference decides
    whether anything may be written back: JSON-RPC forbids a reply to a notification, and
    a server that answers `notifications/initialized` sends a client a response to a
    request it never made. `id` is `None` for one — and because `None` is also a *legal*
    id in JSON-RPC, `has_id` carries the fact rather than being inferred from the value
    (rule 30).
    """

    method: str
    params: dict[str, Any]
    id: Any
    has_id: bool

    @property
    def is_notification(self) -> bool:
        return not self.has_id


def parse(line: str) -> Request:
    """One line into one request, or `Malformed` saying which rule it broke.

    Every refusal names the code a reply must carry, because the caller answering this is
    several frames from the reason by then and a generic `-32600` for a parse failure is a
    client being told the wrong thing about its own message.
    """
    try:
        obj = json.loads(line)
    except ValueError as exc:
        raise Malformed(PARSE_ERROR, "that line is not JSON", str(exc)) from exc

    if not isinstance(obj, dict):
        raise Malformed(INVALID_REQUEST, "a message must be a JSON object",
                        {"got": type(obj).__name__})

    # Read the id **first**, and carry it into every refusal below. From here on the id is
    # detectable, so a null reply would be a choice rather than a necessity.
    carry: dict[str, Any] = {"request_id": obj.get("id"), "has_id": "id" in obj}

    if obj.get("jsonrpc") != VERSION:
        raise Malformed(INVALID_REQUEST, f"every message must declare jsonrpc {VERSION}",
                        {"jsonrpc": obj.get("jsonrpc")}, **carry)

    method = obj.get("method")
    if not isinstance(method, str) or not method:
        raise Malformed(INVALID_REQUEST, "a message must name a method",
                        {"method": method}, **carry)

    params = obj.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        # Positional params are legal JSON-RPC and are not used anywhere in MCP. Refused
        # by name rather than coerced: a list quietly read as no arguments at all is a
        # call that looks like it worked (rule 49).
        raise Malformed(INVALID_PARAMS, "params must be an object, not a list",
                        {"got": type(params).__name__}, **carry)

    return Request(method=method, params=params, id=obj.get("id"), has_id="id" in obj)


def result(request_id: Any, payload: Any) -> dict[str, Any]:
    """A successful reply."""
    return {"jsonrpc": VERSION, "id": request_id, "result": payload}


def error(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    """A failed reply. `data` is omitted rather than sent as null when there is none."""
    body: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        body["data"] = data
    return {"jsonrpc": VERSION, "id": request_id, "error": body}


def write(stream: TextIO, message: dict[str, Any]) -> None:
    """One message, one line, flushed.

    `ensure_ascii=False` because this project writes em dashes in every sentence it means
    a person to read, and the transport is UTF-8 by specification. The escaped form would
    also arrive intact; what it would not do is survive being looked at during debugging,
    and a refusal nobody can read is the failure rule 91 is about.

    The assertion is not defensive padding. `json.dumps` escapes a newline inside a string
    and cannot emit a bare one — *unless* somebody passes `indent`, which is the one edit
    that turns every message into several and breaks the framing for good. It costs a
    scan of a line that was just built and it fails here rather than at the far end.
    """
    line = json.dumps(message, ensure_ascii=False)
    assert "\n" not in line, "a message may not contain a newline; the framing is the line"
    stream.write(line + "\n")
    stream.flush()
