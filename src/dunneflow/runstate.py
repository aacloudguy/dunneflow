"""What an analysis is doing, written where anybody who opens the maps can find it.

`dunneflow analyze` told exactly one listener how far it had got: whoever was reading its
stdout. A run started from the dashboard had that listener; a run started from a terminal had
a scrolling line and nothing else, and the dashboard opened on the same root showed the
program as *"its analysis never finished — analyse it again"* while the analysis was two
hours into finishing it. Unreal's `Engine/Source/Runtime` is that run: 2 h 19 m of
extraction, then 40 minutes of anomaly detection that reported nothing at all.

So the run also writes **`analysis.json`** beside its graph, in the program's own output
directory -- the run-state sidecar `PLAN-BATCH-INGEST.md` proposes, and the only thing a
second process can read without being the run's parent. It holds:

- **who** -- the pid, so the dashboard can tell a live run from a dead one and stop it;
- **what it was told** -- the argv, the program, the revision and the graph it is writing;
- **where it is** -- the last `--progress-json` object, whole, in the shape `/api/analysis`
  already serves, so the panel that draws a dashboard-started run draws this one unchanged;
- **that it is still there** -- `beat`, refreshed by a thread every `BEAT_S` seconds.

**Alive is two questions, and either alone gets a real case wrong** (`analysis_running`'s
shape, one process over). *Is the pid alive* is false at once for a run that was killed, but
a pid is reused, and a stale sidecar naming a pid some other program now holds would read as
a run forever. *Is the heartbeat fresh* is immune to reuse, but is only false `STALE_S` after
a death. Both, then: a live pid **and** a beat within `STALE_S`.

**The file is never the authority on whether a map is finished.** That is the graph's
`complete` key (rule 80), and this file is deliberately not consulted for it: it is a report
about a process, and a process can die without saying so. What it adds is the third answer
the graph cannot give -- *not finished, and still being worked on*.

Written whole, through a temporary file and `os.replace`, so a reader never sees half of
one. On Windows a replace can be refused while another process has the file open; a write
that loses that race is dropped rather than retried, because the next beat is two seconds
away and a progress report is not worth blocking the run for.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

FILE = "analysis.json"

#: How often the heartbeat is refreshed while the run is alive, in seconds.
BEAT_S = 5.0
#: How old a heartbeat may be before the run it describes is taken to have gone. Twelve beats:
#: a run busy in one long SQLite statement still beats, because `sqlite3` releases the GIL
#: while it steps, but a machine swapping hard -- Runtime took free memory to 14 MB -- can
#: hold a thread off for a while, and calling a live run dead is the costlier mistake.
STALE_S = 60.0
#: How long a run's ending stays on show after its last heartbeat, in seconds, for a panel
#: that was following it. Two minutes: long enough for any poll to see it, short enough that
#: an ending nobody was watching does not outlive the reader's interest in it.
ENDED_S = 120.0
#: The least time between two progress writes. The heartbeat and the state changes are
#: written regardless; this bounds what a per-way-in tick costs on a 5,705-way-in render.
NOTE_S = 1.0


def path_in(out_dir: Path) -> Path:
    return out_dir / FILE


class RunState:
    """The writer: one per `analyze`, owned by the run and closed by it."""

    def __init__(self, out_dir: Path, *, program: str, revision: str, graph: Path,
                 argv: list[str], source: Path | None = None) -> None:
        self.path = path_in(out_dir)
        self._lock = threading.Lock()
        self._last_note = 0.0
        self._stop = threading.Event()
        self.body: dict[str, Any] = {
            "pid": os.getpid(),
            "program": program,
            "revision": revision,
            "graph": graph.name,
            "argv": list(argv),
            # Absolute, because the panel's *Analyse it again* fills the dialog with it and
            # the dialog refuses a relative path -- relative to a terminal's cwd it would be.
            "source": str(source) if source is not None else "",
            "began": time.time(),
            "beat": time.time(),
            "state": "working",
            "progress": {},
        }
        self._thread = threading.Thread(target=self._beat, name="dunneflow-runstate",
                                        daemon=True)

    def start(self) -> RunState:
        self._write()
        self._thread.start()
        return self

    def note(self, fields: dict[str, Any]) -> None:
        """The newest progress object. Written at most every `NOTE_S`, unless the step moved."""
        with self._lock:
            before = self.body["progress"]
            moved = (fields.get("step") != before.get("step")
                     or fields.get("state") != before.get("state")
                     or "residue" in fields)
            self.body["progress"] = dict(fields)
            now = time.monotonic()
            if not moved and now - self._last_note < NOTE_S:
                return
            self._last_note = now
        self._write()

    def finish(self, state: str, *, code: int) -> None:
        """The last word: `done`, `failed` or `stopped`, and the exit code it is leaving with."""
        self._stop.set()
        with self._lock:
            self.body["state"] = state
            self.body["code"] = code
            self.body["ended"] = time.time()
        self._write()

    def _beat(self) -> None:
        while not self._stop.wait(BEAT_S):
            self._write()

    def _write(self) -> None:
        with self._lock:
            self.body["beat"] = time.time()
            text = json.dumps(self.body, sort_keys=True)
        try:
            fd, tmp = tempfile.mkstemp(prefix=".analysis.", suffix=".json",
                                       dir=self.path.parent)
        except OSError:
            return
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, self.path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(tmp)


def alive(pid: int) -> bool:
    """Does a process with this id exist? Never signals it.

    **Not `os.kill(pid, 0)` on Windows**: there, any signal but the two console events is
    `TerminateProcess`, so the POSIX idiom for *are you there* would end the run it asks
    about. `OpenProcess` plus `GetExitCodeProcess` is the question without the act.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        query_limited = 0x1000
        still_active = 259
        handle = kernel32.OpenProcess(query_limited, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True           # it exists; it is somebody else's
    except OSError:
        return False
    return True


def read(out_dir: Path, *, now: float | None = None) -> dict[str, Any] | None:
    """The sidecar in `out_dir`, with `running` decided, or `None` when there is none.

    `running` is computed here and never stored: it is a judgement about the present, and a
    file can only record the past. A sidecar whose run has gone without saying so -- killed,
    or the machine slept through it -- reads `state: working, running: false`, which every
    surface words as *stopped while <step>*.
    """
    p = path_in(out_dir)
    try:
        body = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(body, dict):
        return None
    t = time.time() if now is None else now
    fresh = t - float(body.get("beat") or 0) <= STALE_S
    body["running"] = (body.get("state") == "working" and fresh
                       and alive(int(body.get("pid") or 0)))
    return body


def as_progress(body: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """The sidecar in `/api/analysis`'s shape, so the panel draws it as it draws its own run.

    `origin: "terminal"` says where it came from, because the panel's Stop has to reach it
    by pid rather than through a `Popen` this server never held.
    """
    t = time.time() if now is None else now
    prog = dict(body.get("progress") or {})
    raw = str(body.get("state") or "working")
    if raw == "working" and not body.get("running"):
        raw = "stopped"
        prog["reason"] = ("the analysis stopped without finishing, while "
                          f"{prog.get('step') or 'starting'} — analysing it again completes "
                          "it, and what it already read is cached")
    # The panel's own words: `stopped` has its own heading, because a run the reader ended
    # on purpose must not be reported back to them as one that broke.
    state = raw if raw in ("working", "done", "stopped") else "failed"
    out: dict[str, Any] = {
        "step": "", "done_steps": 0, "steps": 0, "detail": "",
        **prog,
        "state": state,
        "program": body.get("program", ""),
        "revision": body.get("revision", ""),
        "source": body.get("source", ""),
        "origin": "terminal",
        "pid": body.get("pid"),
        "began": body.get("began"),
        "running": bool(body.get("running")),
        "running_for": round(t - float(body.get("began") or t), 1),
        "silent_for": round(t - float(body.get("beat") or t), 1),
    }
    return out


def running_under(dirs: list[Path]) -> dict[str, Any] | None:
    """The newest live run in any of these program directories, or `None`."""
    live = [b for d in dirs if (b := read(d)) is not None and b["running"]]
    if not live:
        return None
    return max(live, key=lambda b: float(b.get("began") or 0))
