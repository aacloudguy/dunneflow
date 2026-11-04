"""A reader on the far side of a pipe: spawn it, agree with it, and correlate.

This module knows about **frames**. It knows nothing about `FileFacts`, about extraction,
or about what any frame means — that is `outofprocess.py`'s business. The split is
`mcp/jsonrpc.py`'s, one protocol over: a thing that turns bytes into structure has no
opinion about the structure's subject.

**Newline-delimited JSON, one object per line.** The same framing the MCP server speaks,
chosen for the same reason: it needs no length header, it can be read by a person with
`cat`, and a plugin in any language can write it with its standard library alone.

**stdout carries protocol and nothing else, and stderr is never parsed.** One stray
`print` in a plugin is the entire failure mode, so a line that is not JSON refuses the
language **once, loudly**, rather than being skipped six hundred times quietly. And the
other channel is drained into a ring buffer and read only when something has already gone
wrong: `runtime._desktop_session` is the precedent — text a healthy process also writes
cannot be a control channel, and treating it as one is how a working plugin reads as a
broken one.

**Every request carries an `id` and every reply must echo it**, including `hello`, `open`
and `close` which `PLAN-v2.md`'s sketch shows without one. Uniform, because the
alternative is a reader that special-cases three frames, and the first plugin to reply to
`open` while a file request is outstanding would be answered as though it had replied to
the file.

**A worker that dies is respawned once and the file it died on is not retried.** Retrying
is how one poison file refuses a whole language: the fresh worker meets the same file and
dies again, and the second death is the refusal. So the file is reported failed, the
worker comes back, and the run continues — a **second** death, on some other file, is what
says the reader itself cannot be trusted.

**One reply, or many.** `request` is one frame and one answer; `stream` is one frame and a
run of answers ending in a named terminator. `edges` is the second kind, because a
compilation's answer is tens of thousands of edges and a single JSON line holding all of
them is a payload with no bound (rule 8's argument, on the wire). The id discipline does
not relax for it: **every** frame in the run carries the request's id, including the
terminator, so a stray reply to something else cannot arrive in the middle of a stream and
be read as part of it.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import threading
from collections import deque
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from ..detectors import rules_document
from ..schema import SCHEMA_VERSION
from .contract import PluginManifest, PluginRefused, ProtocolError, ToolchainMissing

# How much of the other channel to keep. Enough to carry a stack trace's tail, which is
# the part that says what happened, and bounded because a plugin in a loop can write
# megabytes a second and the host must not be the thing that runs out of memory.
STDERR_KEEP = 4096

# The protocol generation this module speaks. `ingest.PROTOCOL` is the same number; it is
# imported rather than re-declared where the two would otherwise drift, and stated here so
# the frame-writer's own claim is readable beside the frames.
PROTOCOL = 1


class WorkerDied(RuntimeError):
    """The process went away mid-conversation, and this is what it left behind."""


class NdjsonWorker:
    """One plugin process, from spawn to close.

    Not reusable across languages and not shared: a worker holds whatever `open` gave it,
    which for a type-checking reader is an entire compilation.
    """

    def __init__(self, argv: Sequence[str], manifest: PluginManifest,
                 cwd: Path | None = None) -> None:
        self.argv = list(argv)
        self.manifest = manifest
        self.cwd = cwd
        self.proc: subprocess.Popen[str] | None = None
        self.ready: dict[str, Any] = {}
        self.deaths = 0
        self._next_id = 0
        self._stderr: deque[str] = deque()
        self._stderr_bytes = 0
        self._drain: threading.Thread | None = None
        self._lock = threading.Lock()
        # What `open` was given, so a respawned worker can be put back in the state the
        # dead one was in. A reader that resolves symbols over a subset of the compilation
        # answers wrongly rather than partially, so this is not optional bookkeeping.
        self._opened: tuple[Path, list[str]] | None = None

    # ------------------------------------------------------------------ life --- #

    def start(self) -> None:
        """Spawn and shake hands. Raises `PluginRefused` if the two disagree."""
        try:
            self.proc = subprocess.Popen(  # noqa: S603 — argv is built, never a shell
                self.argv,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(self.cwd) if self.cwd else None,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
            )
        except OSError as exc:
            raise PluginRefused(
                f"the {self.manifest.lang} plugin could not be started: {exc}. The command "
                f"was {' '.join(self.argv)}."
            ) from exc
        self._drain = threading.Thread(target=self._drain_stderr, daemon=True)
        self._drain.start()
        self._handshake()

    def stop(self) -> None:
        """Say goodbye, then make sure. Safe to call twice, as the contract requires."""
        proc = self.proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                # Through the live handle, and `self.proc` is cleared only afterwards: a
                # `stop` that disowned the process first would send its goodbye into a
                # `None` and kill every worker the hard way, which looks exactly like a
                # plugin that will not shut down cleanly.
                self._write({"t": "close", "id": self._id()})
                proc.wait(timeout=5)
        except (OSError, ValueError, WorkerDied, subprocess.TimeoutExpired, ProtocolError):
            pass
        finally:
            self.proc = None
            if proc.poll() is None:
                proc.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=5)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    with contextlib.suppress(OSError):
                        stream.close()

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    # ------------------------------------------------------------- the wire ---- #

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _write(self, frame: dict[str, Any]) -> None:
        proc = self.proc
        if proc is None or proc.stdin is None:
            raise WorkerDied("the worker is not running")
        try:
            proc.stdin.write(json.dumps(frame, separators=(",", ":")) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError) as exc:
            raise WorkerDied(str(exc)) from exc

    def _read(self) -> dict[str, Any]:
        proc = self.proc
        if proc is None or proc.stdout is None:
            raise WorkerDied("the worker is not running")
        line = proc.stdout.readline()
        if line == "":
            raise WorkerDied(f"exit status {proc.wait()}")
        try:
            frame = json.loads(line)
        except ValueError as exc:
            # Loudly and once. A reader that skips this has a channel carrying something
            # other than protocol and no way to know how long that has been true.
            raise ProtocolError(
                f"the {self.manifest.lang} plugin wrote a line on stdout that is not this "
                f"protocol: {line[:200]!r}. stdout carries frames and nothing else — a "
                f"stray print in a plugin arrives here, and every fact already taken from "
                f"this channel is suspect. ({exc})"
            ) from exc
        if not isinstance(frame, dict) or "t" not in frame:
            raise ProtocolError(
                f"the {self.manifest.lang} plugin sent {line[:200]!r}, which is JSON but "
                f"not a frame: every frame is an object with a `t`."
            )
        return frame

    def request(self, frame: dict[str, Any]) -> dict[str, Any]:
        """Send one frame and return its reply, matched by id.

        Raises `WorkerDied` if the process went away; respawning is the caller's decision,
        because only the caller knows whether the request that killed it should be retried
        (it should not) and what to tell the host about the work it was carrying.
        """
        with self._lock:
            ident = self._id()
            self._write({**frame, "id": ident})
            reply = self._read()
            got = reply.get("id")
            if got != ident:
                raise ProtocolError(
                    f"the {self.manifest.lang} plugin answered request {ident} with a "
                    f"frame carrying id {got!r}. Replies are matched by id, so one that "
                    f"does not match is not a late answer, it is an answer to something "
                    f"else arriving as this one."
                )
            if reply["t"] == "error":
                raise ProtocolError(
                    f"the {self.manifest.lang} plugin refused {frame['t']!r}: "
                    f"{reply.get('reason', '(no reason given)')}"
                )
            return reply

    def stream(self, frame: dict[str, Any], done: str) -> Iterator[dict[str, Any]]:
        """Send one frame and read every answer until the one named `done`.

        The terminator is yielded last rather than swallowed, so a caller can read the
        plugin's own tally off it and check it against what actually arrived — a count a
        plugin sends is a claim, and a claim checked against nothing is rule 37.

        **The id is checked on every frame of the run**, not only on the first. A stream is
        exactly where a misdirected reply would be absorbed silently: it arrives in the
        middle of a run of legitimate frames and looks like one of them.

        Under the same lock `request` takes, because a stream and a request interleaved on
        one pipe is two conversations sharing a channel. The lock is held for the whole
        run, so a caller that abandons the iterator half way leaves the pipe with unread
        frames on it — which is why the one caller drains it.
        """
        with self._lock:
            ident = self._id()
            self._write({**frame, "id": ident})
            while True:
                reply = self._read()
                got = reply.get("id")
                if got != ident:
                    raise ProtocolError(
                        f"the {self.manifest.lang} plugin answered request {ident} with a "
                        f"frame carrying id {got!r}, part way through a {frame['t']!r} "
                        f"stream. A frame that does not match is not a late answer, it is "
                        f"an answer to something else arriving as this one."
                    )
                if reply["t"] == "error":
                    raise ProtocolError(
                        f"the {self.manifest.lang} plugin refused {frame['t']!r}: "
                        f"{reply.get('reason', '(no reason given)')}"
                    )
                yield reply
                if reply["t"] == done:
                    return

    # -------------------------------------------------------------- stderr ----- #

    def _drain_stderr(self) -> None:
        proc = self.proc
        if proc is None or proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                self._stderr.append(line)
                self._stderr_bytes += len(line)
                while self._stderr_bytes > STDERR_KEEP and len(self._stderr) > 1:
                    self._stderr_bytes -= len(self._stderr.popleft())
        except (OSError, ValueError):
            pass

    def stderr_tail(self) -> str:
        """What the plugin said on the other channel. Evidence, never a control signal."""
        return "".join(self._stderr).strip()

    # ----------------------------------------------------------- handshake ----- #

    def _handshake(self) -> None:
        """Ask the running process the questions the manifest already answered.

        **Both, and that is rule 30**: the manifest is a label a file makes and the running
        process is the identity. They cannot disagree for a reader in this interpreter,
        which is the whole difference between the two kinds of plugin — so for this kind,
        a disagreement is checked and refuses the language quoting both values.
        """
        m = self.manifest
        try:
            reply = self.request({
                "t": "hello", "protocol": PROTOCOL,
                "schema_version": SCHEMA_VERSION, "lang": m.lang,
            })
        except WorkerDied as exc:
            raise PluginRefused(
                f"the {m.lang} plugin died during the handshake ({exc}). It wrote:\n"
                f"{self.stderr_tail() or '(nothing on stderr)'}"
            ) from exc
        if reply["t"] == "declined":
            # The reader started and cannot read: a library its toolchain needs is not on
            # this machine (`Toolchain.asks_reader`). The machine's state, not a defect.
            tc = m.toolchain
            raise ToolchainMissing(
                f"{m.lang} needs more than `{tc.command if tc else m.lang}` answering: the "
                f"reader started and declined, saying: {reply.get('reason') or '(no reason)'}. "
                f"Install it" + (f" ({tc.install})" if tc and tc.install else "")
                + f", or run again with `--without {m.lang}` and the map will say those files "
                f"were declined."
            )
        if reply["t"] != "ready":
            raise ProtocolError(
                f"the {m.lang} plugin answered `hello` with {reply['t']!r}; the only "
                f"answer to a handshake is `ready`."
            )
        self.ready = reply

        for field, declared in (("lang", m.lang), ("protocol", PROTOCOL),
                                ("schema_version", SCHEMA_VERSION),
                                ("version", m.version)):
            said = reply.get(field)
            if said != declared:
                raise PluginRefused(
                    f"the {m.lang} plugin at {m.root} disagrees with itself about "
                    f"{field}: its manifest says {declared!r} and the running process says "
                    f"{said!r}. A manifest is a label and the process is the identity, so "
                    f"a plugin that cannot say one thing about itself is one whose facts "
                    f"nobody can vouch for."
                )

        # The capabilities, asked the same way and for the same reason. They were declared
        # on both sides and compared on neither until `reports_literals` started deciding
        # whether the host judges this language's strings at all — a manifest saying yes
        # over a process saying no is then a map with no SQL and no named files in it, and
        # nothing anywhere that says why.
        caps = reply.get("capabilities") or {}
        for field, declared in (("supplies_edges", m.supplies_edges),
                                ("supplies_bindings", m.supplies_bindings),
                                ("reports_literals", m.reports_literals)):
            said = bool(caps.get(field, False))
            if said != declared:
                raise PluginRefused(
                    f"the {m.lang} plugin at {m.root} disagrees with itself about "
                    f"{field}: its manifest says {declared!r} and the running process says "
                    f"{said!r}. A capability decides what the host does with what comes "
                    f"back, so the two must be one answer."
                )

    # -------------------------------------------------------------- session ---- #

    def _open_frame(self, root: Path, files: Sequence[str]) -> dict[str, Any]:
        """The `open` frame, built in **one place** (rule 51).

        `respawn` spelled this out a second time and left the rules off, so a worker that
        died once read the rest of the run with no boundary rules at all — no boundaries,
        no SQL, no network, and nothing anywhere saying why. The plugin's own warning for
        that case is written and would have gone to stderr, which the host never parses
        (rule 35: a second spelling of a frame is an empty view with no symptom).

        **The rules travel with the session**, because a reader that is another program
        cannot import `detectors/` and must not carry its own copy: a baked-in rule set
        stops moving the moment somebody edits the YAML, and that file is in the core
        extraction key exactly so an edit re-reads every language (rule 51). Sent as
        written — `detectors.rules_document` — so there is one file and not a second
        rendering of it. A reader that wants none ignores the key.
        """
        return {"t": "open", "root": str(root), "files": list(files),
                "rules": rules_document(self.manifest.lang)}

    def open(self, root: Path, files: Sequence[str]) -> dict[str, Any]:
        """Hand over **every** file of this language, changed or not.

        A reader that resolves symbols over a subset of the compilation answers wrongly
        rather than partially, which is why this takes the whole set and `extract` takes
        only what missed the cache.
        """
        self._opened = (root, list(files))
        return self.request(self._open_frame(root, files))

    def respawn(self) -> None:
        """Bring a dead worker back, in the state the dead one was in.

        Counted. The **second** death is what says the reader cannot be trusted; the first
        is a crash, and a crash on one file is a fact about that file.
        """
        self.deaths += 1
        self.stop()
        self._stderr.clear()
        self._stderr_bytes = 0
        self.start()
        if self._opened is not None:
            root, files = self._opened
            self.request(self._open_frame(root, files))
