"""Running an analysis from the server: the one thing this process asks for that is a write.

Every other line under `web/` is a read, and `_Live` opens every store `writable=False`
because rule 20 says serving may refuse but may never repair. So the analysis does not
happen here at all -- it happens in **a subprocess running `dunneflow analyze`**, and this
module is the pre-flight, the plumbing and the report.

Three reasons for the subprocess, and the first is the binding one:

* The serving process never becomes a writer to the tree it is serving. The posture is
  kept by construction rather than by care.
* `walk.py` runs a `ProcessPoolExecutor`. Starting one from inside a
  `ThreadingHTTPServer` request thread is fragile where a subprocess is not.
* What runs is **exactly** `dunneflow analyze`, not a second assembly of the same steps
  that can drift from the tested one (rule 51).

Two channels, kept apart on purpose. The child is given `--progress-json --quiet`, so its
**stdout** is one JSON object per line and its **stderr** carries only a real failure. A
progress report scraped out of prose written for a human would be a sentence promoted to a
contract (rule 30), and the day somebody rewords it the bar stops moving with no error
anywhere.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import revisions

# The tail of the child's stderr kept for a failure's reason. A traceback is a few dozen
# lines and a runaway is not, and the reason is rendered in a dialog -- so it is bounded,
# and **says so when it bites** (design rule 1: no filter is ever silent). Nothing else in
# this tool bounds a fact; this is not one, it is a subprocess's complaint.
REASON_LINES = 40


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the pre-flight says about a request, before anything has been started.

    Three outcomes rather than two, and the third is the point. A **refusal** is a thing
    that may not happen. A **note** is a thing that will happen and that the reader may
    not be expecting -- analysing into a name that already exists rewrites that program's
    working snapshot, which is a surprise and not an error.

    One function produces both, so the warning the dialog shows while somebody is typing
    and the answer the endpoint gives when they press the button cannot drift apart
    (rule 41).
    """

    refusal: str = ""
    note: str = ""

    @property
    def ok(self) -> bool:
        return not self.refusal


def check(path: str, name: str, out_root: Path, serving: Path) -> Verdict:
    """May this analysis run, and is there anything the reader should know first?

    The refusals are in the order somebody hits them, and **each has its own sentence**:
    "nothing happened" and "that would overwrite what you are reading" are different
    answers and a reader must never have to guess which one they got.
    """
    if not path.strip():
        return Verdict(refusal="no directory was named")
    source = Path(path.strip()).expanduser()
    if not source.is_absolute():
        return Verdict(refusal=f"{source} is a relative path — give the whole path, "
                               "because the server's directory is not yours")
    try:
        source = source.resolve()
    except OSError as exc:
        return Verdict(refusal=f"{source} could not be read: {exc}")
    if not source.exists():
        return Verdict(refusal=f"{source} does not exist")
    if not source.is_dir():
        return Verdict(refusal=f"{source} is a file, not a directory to analyse")

    root = out_root.resolve()
    # **Rule 57, one directory up.** Admitting a map's own output as a program to analyse
    # is the mistake that read 46 of 54 documents out of `output/` -- and here it would be
    # worse, because the thing analysed would be this tool's own generated prose about
    # some other program.
    if source == root or source.is_relative_to(root):
        return Verdict(refusal=f"{source} is inside the output root — that is where maps "
                               "are written, not a program to read")

    wanted = (name or source.name).strip()
    if not wanted:
        return Verdict(refusal="no name was given, and the directory has none to borrow")
    # A name **is a directory** under the output root, so it has to be one segment. Checked
    # rather than sanitised: silently turning `../etc` into `etc` would analyse a tree
    # nobody asked for under a name nobody typed (rule 30 -- a label becomes an identity
    # here, and only by being refused when it cannot be one).
    if wanted in {".", ".."} or any(c in wanted for c in "/\\") or wanted.startswith("."):
        return Verdict(refusal=f"{wanted} is not a name a directory can have — one plain "
                               "name, no separators and no leading dot")

    if wanted == serving.resolve().name:
        # **Not caution.** `Store._discard_if_stale` drops every table of a graph written
        # by another build of DunneFlow, and this server is holding that graph open. An
        # analysis aimed here can empty the map under a live reader.
        return Verdict(refusal=f"{wanted} is the program being read — its graph is open "
                               "here, and an analysis may discard and re-extract it. "
                               "Switch to another program first, or run this from a "
                               "terminal.")

    target = root / wanted
    if target.exists() and not target.is_dir():
        # Caught here rather than by the child, which reports it as a `FileExistsError`
        # traceback fourteen lines long -- true, and not a sentence the reader this tool
        # is for can act on.
        return Verdict(refusal=f"a file called {wanted} is already sitting where that "
                               "program's directory would go")
    if revisions.newest(target, revisions.GRAPH) is not None:
        # Allowed, and **said out loud**. `analyze` reuses the working revision, so this
        # replaces that snapshot rather than adding one beside it.
        return Verdict(note=f"There is already a program called {wanted}. Analysing into "
                            f"it rewrites its working snapshot rather than adding a second "
                            f"point in time — seal it first if you want to keep both.")
    return Verdict()


def argv(source: Path, name: str, out_root: Path, docs: bool) -> list[str]:
    """What the subprocess is told. Named apart from `run` so a test can read it.

    `-m dunneflow.cli` rather than `-m dunneflow`: the package has no `__main__`, and the
    module named here is the one that actually holds `main()`.

    `--quiet` **with** `--progress-json`, deliberately: it empties the prose channel so
    stderr holds a failure and nothing else, which is the whole of why there are two.
    """
    out = [sys.executable, "-m", "dunneflow.cli", "analyze", str(source),
           "--name", name, "--output", str(out_root), "--progress-json", "--quiet"]
    if not docs:
        out.append("--no-docs")
    return out


def run(source: Path, name: str, out_root: Path, docs: bool,
        note: Callable[..., None], *,
        popen: Any = subprocess.Popen) -> None:
    """Read `source` into `out_root/name`, reporting every step through `note`.

    Runs on its own thread. A failure is **reported, never raised** -- the reader asked
    for this and is watching a panel, and a run that ends by writing a traceback to a
    terminal nobody is looking at, leaving the panel saying "working" for ever, is the
    same defect as a spinner that never stops. `_Live.switch` carries the same rule one
    subject over.

    `popen` is an argument so a test can drive the failure paths without a real analysis.
    """
    cmd = argv(source, name, out_root, docs)
    tail: deque[str] = deque(maxlen=REASON_LINES)
    try:
        proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except OSError as exc:
        note(state="failed", program=name, reason=f"could not start the analysis: {exc}")
        return

    # Drained on its own thread. A child that writes more to stderr than the pipe holds
    # blocks in `write` while this thread blocks in `read` on the other pipe, and neither
    # ever moves -- an analysis that hangs for ever with no error and no progress.
    def drain() -> None:
        if proc.stderr is None:
            return
        for line in proc.stderr:
            tail.append(line.rstrip("\n"))

    drainer = threading.Thread(target=drain, name=f"dunneflow-analyze-err-{name}",
                               daemon=True)
    drainer.start()

    finished = False
    if proc.stdout is not None:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                fields = json.loads(line)
            except ValueError:
                # A line the contract does not cover is **skipped, not fatal**: the run
                # itself is fine and the bar simply does not move for it. Its own state
                # would be a failure invented by the watcher (rule 49).
                continue
            if not isinstance(fields, dict):
                continue
            fields["program"] = name
            note(**fields)
            finished = fields.get("state") == "done"

    code = proc.wait()
    drainer.join(timeout=2.0)
    if code != 0:
        note(state="failed", program=name, reason=_reason(tail, code))
        return
    if not finished:
        # Exit 0 with no `done` object means the contract was not met, and saying so is
        # better than reporting a success this never saw (rule 49).
        note(state="failed", program=name,
             reason="the analysis ended without saying it had finished")
        return
    # **Nothing is said here on success, and that is deliberate.** The child's own `done`
    # object has already been relayed and it carries the counts, the revision and the
    # graph it wrote. A second `done` from out here replaced all of that with a report
    # that knew none of it -- five of five steps, then zero of zero, and every number
    # gone. The last word belongs to the process that did the work (rule 51).


def _reason(tail: deque[str], code: int) -> str:
    """What went wrong, from the child's own mouth where it said anything.

    The bound is stated when it bites, because a truncated traceback that does not say it
    is truncated reads as the whole story (design rule 1).
    """
    lines = [line for line in tail if line.strip()]
    if not lines:
        return f"the analysis exited {code} without saying why"
    # **The last line first.** A traceback says the useful thing last -- `FileExistsError:
    # ... output/blocked` under fourteen lines of frames -- and the reader this tool is
    # written for reads code without writing it. Nothing is invented and nothing is
    # dropped: this is the child's own final line, promoted, with everything it said kept
    # underneath as the evidence for it.
    last = lines[-1].strip()
    if len(lines) == 1:
        return last
    head = f"(the last {REASON_LINES} lines it printed)\n" if len(lines) == REASON_LINES \
        else ""
    return f"{last}\n\n{head}" + "\n".join(lines)
