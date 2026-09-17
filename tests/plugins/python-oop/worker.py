"""The Python extractor, on the far side of a pipe. A test double, and a real worker.

`PLAN-v2.md`'s chunk 7 calls this the thing that de-risks everything, and the reason is
that it is **the same extractor**: `extractors.python.extract.extract_file`, the function
the in-process reader calls, reached here through a subprocess and the NDJSON protocol. So
a difference between the two answers is the protocol and can be nothing else — where a
TypeScript plugin's first run would give a difference nobody has a baseline for.

**It lives in `tests/`, not in `src/dunneflow/plugins/`, and that is the registry's own
rule rather than squeamishness.** `ingest._load()` reads every `plugins/*/plugin.json` at
import and `suffix_owners` refuses two readers claiming one suffix, naming both. A double
shipped beside the real Python plugin would refuse the build at import; a double that
claimed some other suffix would not read the files the comparison is about. So it is built
by `read_manifest` and `OutOfProcessPlugin` directly — the public path, minus the registry.

**stdout carries protocol and nothing else.** Every diagnostic goes to stderr, which the
host drains and never parses. This file is also the worked example of what a plugin author
has to get right, which is why it is commented as one.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

# A plugin is started as a program, not imported, so it puts its own dependencies on the
# path. A real out-of-process plugin is a bundle with its own runtime and needs none of
# this; this one is Python reaching back into the package it is doubling for.
_SRC = Path(__file__).resolve().parents[3] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dunneflow.extractors.python.extract import extract_file  # noqa: E402
from dunneflow.ingest.codec import encode_facts  # noqa: E402
from dunneflow.schema import SCHEMA_VERSION  # noqa: E402

PROTOCOL = 1
LANG = "python"
VERSION = "1.0.0"

# Test hooks. A worker that cannot be made to misbehave on purpose leaves the host's
# failure paths — the ones that matter most and run least — proved by nothing.
#   DUNNEFLOW_OOP_DIE_ON   a path fragment; the worker exits hard when asked for it
#   DUNNEFLOW_OOP_GARBAGE  a path fragment; the worker writes prose on stdout for it
#   DUNNEFLOW_OOP_THROW    a path fragment; the worker answers `failed`
#   DUNNEFLOW_OOP_BADHASH  a path fragment; the worker echoes a hash that is not the one
#   DUNNEFLOW_OOP_CHATTER  anything truthy; the worker writes to stderr constantly
#   DUNNEFLOW_OOP_LIE      a field name; `ready` disagrees with the manifest about it
#   DUNNEFLOW_OOP_EXTRA    anything truthy; every routine carries a field this build lacks
#   DUNNEFLOW_OOP_WRONGID  anything truthy; every reply carries somebody else's id


def _hit(var: str, path: str) -> bool:
    want = os.environ.get(var, "")
    return bool(want) and want in path


def send(frame: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(frame, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def note(text: str) -> None:
    """The other channel. Evidence, and never a control signal."""
    sys.stderr.write(text + "\n")
    sys.stderr.flush()


def on_hello(frame: dict[str, Any]) -> dict[str, Any]:
    lie = os.environ.get("DUNNEFLOW_OOP_LIE", "")
    ready: dict[str, Any] = {
        "t": "ready",
        "lang": LANG,
        "version": VERSION,
        "protocol": PROTOCOL,
        "schema_version": SCHEMA_VERSION,
        "capabilities": {"supplies_edges": False, "reports_literals": False},
    }
    if lie in ready:
        # Rule 30 made testable: the manifest is a label and this process is the identity,
        # so the host must catch the two disagreeing about any of the four.
        ready[lie] = "something else" if isinstance(ready[lie], str) else 999
    return ready


# The analysed root, taken at `open` and held for the session. `extract` carries a path
# and a hash and no root, which is the protocol's shape rather than an economy: the root
# is a property of the session, and a reader that could be told a different one per file
# could file two files of one tree under two different module namings.
SESSION: dict[str, Any] = {}


def on_open(frame: dict[str, Any]) -> dict[str, Any]:
    """Python's reader answers one file without seeing the others, so this holds no files.

    Stated rather than left out, because *this is the difference* that decided the
    protocol's shape: a reader that resolves symbols cannot say it, and `open` exists for
    the ones that cannot. What it does keep is the root.
    """
    SESSION["root"] = Path(str(frame.get("root", ".")))
    note(f"opened {len(frame.get('files', []))} files")
    return {"t": "opened", "files": len(frame.get("files", [])), "program_ms": 0,
            "diagnostics": []}


def on_extract(frame: dict[str, Any]) -> dict[str, Any]:
    path = str(frame.get("path", ""))
    root = SESSION.get("root")

    if _hit("DUNNEFLOW_OOP_DIE_ON", path):
        note("dying on purpose")
        os._exit(9)
    if _hit("DUNNEFLOW_OOP_GARBAGE", path):
        # The one failure mode a plugin author actually produces: a stray print.
        sys.stdout.write("this is not a frame\n")
        sys.stdout.flush()
        return {"t": "facts", "hash": frame.get("hash"), "facts": {}}
    if _hit("DUNNEFLOW_OOP_THROW", path):
        return {"t": "failed", "reason": "asked to fail by DUNNEFLOW_OOP_THROW"}

    p = Path(path)
    try:
        facts = extract_file(p, root if root is not None else p.parent)
    except Exception:                       # noqa: BLE001 — reported, never raised
        # A reader that threw says so and lets the **host** write the record: a plugin
        # that has just crashed on a file is not the right authority on what that file is.
        return {"t": "failed", "reason": traceback.format_exc(limit=3).strip()}

    body = encode_facts(facts)
    if os.environ.get("DUNNEFLOW_OOP_EXTRA"):
        for r in body.get("routines", []):
            r["invented_by_a_newer_plugin"] = True
    echoed = frame.get("hash")
    if _hit("DUNNEFLOW_OOP_BADHASH", path):
        echoed = "0000000000000000"
    return {"t": "facts", "hash": echoed, "facts": body}


HANDLERS = {"hello": on_hello, "open": on_open, "extract": on_extract}


def main() -> int:
    if os.environ.get("DUNNEFLOW_OOP_CHATTER"):
        note("chatter: " + "x" * 8000)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            frame = json.loads(line)
        except ValueError:
            note(f"unreadable frame: {line[:120]}")
            continue
        kind = frame.get("t")
        ident = frame.get("id")
        if kind == "close":
            send({"t": "closed", "id": ident})
            return 0
        handler = HANDLERS.get(str(kind))
        if handler is None:
            send({"t": "error", "id": ident, "reason": f"unknown frame {kind!r}"})
            continue
        try:
            reply = handler(frame)
        except Exception:                   # noqa: BLE001 — reported, never raised
            send({"t": "error", "id": ident, "reason": traceback.format_exc(limit=3)})
            continue
        if os.environ.get("DUNNEFLOW_OOP_WRONGID"):
            # An answer to something else, arriving as this one. The host has to refuse it
            # rather than take it as a late reply.
            ident = (ident or 0) + 1000
        send({**reply, "id": ident})
        if os.environ.get("DUNNEFLOW_OOP_CHATTER"):
            note("still here")
    return 0


if __name__ == "__main__":
    sys.exit(main())
