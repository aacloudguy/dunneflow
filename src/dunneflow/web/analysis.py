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

import contextlib
import json
import os
import signal
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import revisions
from ..runtime import self_argv

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


def check(path: str, name: str, out_root: Path, serving: Path | None) -> Verdict:
    """May this analysis run, and is there anything the reader should know first?

    The refusals are in the order somebody hits them, and **each has its own sentence**:
    "nothing happened" and "that would overwrite what you are reading" are different
    answers and a reader must never have to guess which one they got.

    `serving` is `None` when nothing is open, which is the state a packaged application
    starts in. Exactly one refusal depends on it -- *that is the program being read* -- and
    with nothing being read it is not a refusal, it is a fact that has no subject. Passed as
    `None` rather than as some stand-in path, because a stand-in would have to be a
    directory name, and a name that accidentally matched would refuse the first analysis a
    reader ever asks for (rule 30).
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

    if serving is not None and wanted == serving.resolve().name:
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

    **How to run this same DunneFlow again is `runtime.self_argv`'s question, not this
    one.** It used to be spelled out here as `[sys.executable, "-m", "dunneflow.cli", ...]`,
    which is right in a checkout and meaningless in a packaged application: `-m` names a
    module to an interpreter, and there is no interpreter to name it to. That would have
    left **+ Analyze a directory...** -- the only way a first-time reader gets a map at all
    -- failing on the one build where it is the only way in.

    `--quiet` **with** `--progress-json`, deliberately: it empties the prose channel so
    stderr holds a failure and nothing else, which is the whole of why there are two.
    """
    out = [*self_argv("analyze", str(source)),
           "--name", name, "--output", str(out_root), "--progress-json", "--quiet"]
    if not docs:
        out.append("--no-docs")
    return out


# **What a stopped child's own exit code is, on each platform.** POSIX reports a death by
# signal as a negative return code; Windows has no such thing, and a process broken out of
# its wait reports `STATUS_CONTROL_C_EXIT` instead -- which is the same kind of fact, made
# by the child rather than set from outside (rule 13). Held in both spellings because the
# raw status reaches Python unsigned and the same value signed is what a C reader expects.
CONTROL_C_EXIT = 0xC000013A
_WINDOWS_STOPPED = frozenset({CONTROL_C_EXIT, CONTROL_C_EXIT - (1 << 32)})


def own_group() -> dict[str, Any]:
    """How a child is put in a group of its own, so stopping it can reach what it starts.

    One idea and two spellings, and neither is optional: `analyze` runs a
    `ProcessPoolExecutor` whose workers inherit the pipes, so a stop that reaches only the
    parent leaves them holding stdout open and `run`'s read loop never returns.

    Named and returned rather than written inline at the `Popen`, because the group this
    makes is the thing `_interrupt_group` and `_kill_group` address -- three places that
    have to agree about one decision (rule 51). `start_new_session` is **silently ignored**
    on Windows, so the wrong one there is not an error; it is a stop that does nothing.
    """
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _interrupt_group(proc: Any) -> bool:
    """Ask the child **and everything it started** to stop, and let it close what it holds.

    `analyze` holds three SQLite connections and a process pool, so the first rung is always
    the polite one. On POSIX that is `SIGTERM` to the process group, falling back to the
    child alone for a `Popen` that has no group to speak of -- a test double, or a platform
    without one.

    On Windows it is a **console break** to the group, which is the same instrument under
    another name: it reaches every process in the group, the child raises
    `KeyboardInterrupt` and unwinds, and its exit code says so afterwards. Measured on a
    pool of eight workers -- 8 descendants before, **0** after, exit `0xC000013A`. Plain
    `terminate()`, which is what a `Popen` does with `SIGTERM` there, left **all nine
    processes alive**, and the reader's panel said `working` over a child that had gone:
    the exact jam the POSIX side of this function was written to prevent, reproduced whole
    on the other platform.

    Returns whether the ask was *delivered*. It can honestly fail on Windows, where a break
    needs a console and a double-clicked application has none. That is a rung skipped rather
    than a refusal -- `_kill_group` needs no console.

    **`SystemError` is in the guard because that is the class this actually raises**, and it
    was found by pressing the packaged application rather than by reading the documentation
    (rule 48). With no console, `GenerateConsoleCtrlEvent` fails with `WinError 6`, and
    CPython's `os.kill` returns a value with that error still set -- so what reaches the
    caller is not the `OSError` every line of this function was written to expect but
    `SystemError: <built-in function kill> returned a result with an exception set`. Uncaught,
    it left `_p_stop_analysis` with a dead handler thread: **the connection closed without a
    response**, the reader's Stop button reported a network failure, and the analysis was
    killed anyway by nothing at all. A guard that names the wrong class has not guarded
    anything (rule 42), and the wrong class here was the plausible one.
    """
    if sys.platform == "win32":
        try:
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
            return True
        except (OSError, SystemError, AttributeError, TypeError, ValueError):
            return False
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        return True
    except (OSError, AttributeError, TypeError):
        try:
            proc.send_signal(signal.SIGTERM)
            return True
        except (OSError, AttributeError, TypeError):
            return False


def _kill_group(proc: Any) -> bool:
    """Take the child **and everything it started** down, whatever they are doing.

    The second rung. On Windows it is a different instrument rather than a harder signal:
    there is no `SIGKILL`, and `terminate()` reaches one process. `taskkill /F /T` walks the
    tree and ships with Windows; measured, it takes the same pool of eight from 8
    descendants to 0.

    **It costs the child's evidence**, and `note_forced` is what pays for that. A tree taken
    down this way exits 1, which is exactly what an analysis that genuinely broke exits with,
    so the exit code alone cannot tell the two apart -- and the polite rung is the one a
    packaged Windows build cannot use. `stop` therefore records that this rung ran; see
    `note_forced` for why that is not the flag rule 13 refuses, for why it is written before
    the kill rather than after it, and for the one instant of residue it leaves. On POSIX
    both rungs leave a negative code, the child speaks for itself, and none of this applies.
    """
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
            return True
        except (OSError, SystemError, subprocess.TimeoutExpired, ValueError):
            return False
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        return True
    except (OSError, AttributeError, TypeError):
        try:
            proc.send_signal(signal.SIGKILL)
            return True
        except (OSError, AttributeError, TypeError):
            return False


# Where "this process took that child down" is recorded: **on the child's own handle**, and
# never in a module global. The two functions that care already share the `Popen` -- `stop`
# sets it, `run` reads it -- and a global would be one fact about whichever analysis ran last.
FORCED = "dunneflow_forced"


def note_forced(proc: Any, forced: bool = True) -> None:
    """Record that this process is killing the child outright, because nothing else will.

    **The narrow exception to rule 13, and the bound on it is what makes it payable.** That
    rule says a stop must be told from a failure by the child's *own* evidence, never by a
    flag this process set when it asked -- because the ask and the outcome can disagree. On
    POSIX that costs nothing: both rungs leave a negative exit code and the child speaks for
    itself either way.

    Windows has one rung that can speak and one that cannot. A console break leaves
    `STATUS_CONTROL_C_EXIT`; `taskkill /F` leaves **1**, which is what a broken analysis
    leaves. And the polite rung is exactly the one a *packaged* build cannot use, because a
    windowed binary is given no console -- so on the surface most readers actually have, every
    deliberate stop was reported as *"the analysis exited 1 without saying why"*. A control
    that reports the opposite of what the reader just did is worse than the rule it was
    keeping.

    So this is not quite the flag rule 13 refuses, and the difference is that it is
    **withdrawn when the kill fails** -- `stop` clears it on a `_kill_group` that could not
    deliver, so what survives is a record of what happened rather than of what was asked for.

    **It is taken before the kill and not after, and that ordering was measured.** Written
    afterwards it lost a race it cannot win: `taskkill` returns only once the child is
    already gone, so `run`'s read loop unblocks, reaches `proc.wait()` and reports -- all
    while `stop` is still inside `subprocess.run`. Every stop on the packaged build went on
    reading *"the analysis exited 1 without saying why"* with this note set a moment too
    late. The window the early write opens is harmless in the other direction: `run` only
    reads this once the child is dead, and the child only dies from a kill that worked.

    The residue is stated rather than hidden: a child that broke of its own accord in the
    same instant it was force-killed is reported as stopped. That is one instant, against
    every stop on a packaged Windows build.
    """
    # A `Popen` double a test supplied with `__slots__`, or anything else that will not take
    # an attribute, is left alone. Nothing here is worth failing a stop over.
    with contextlib.suppress(AttributeError):
        setattr(proc, FORCED, forced)


def was_forced(proc: Any) -> bool:
    """Did this process take that child down? See `note_forced` for why this exists."""
    return bool(getattr(proc, FORCED, False))


def was_stopped(code: int) -> bool:
    """Does this exit code say the child was stopped, rather than that it broke?

    **The child's own evidence, on whichever platform it ran** -- never a flag this process
    set when it asked, which could disagree with what actually happened (rule 13). POSIX
    spells it as a negative return code; Windows spells it `STATUS_CONTROL_C_EXIT`. One
    function, so the two spellings cannot be read in one place and forgotten in another.
    """
    if sys.platform == "win32":
        return code in _WINDOWS_STOPPED
    return code < 0


def stop(proc: Any, *, grace: float = 3.0) -> str:
    """End a running analysis, and say how it ended.

    The polite rung first, because `analyze` holds three SQLite connections and a process
    pool and a clean exit closes them; the forceful one only if it will not go. **To the
    whole group either way** -- see `_interrupt_group`, which is where the interesting part
    is, and `own_group`, which is what makes a group there is to address.

    The forceful rung is tried even where the polite one could not be delivered, which is
    Windows' case and costs POSIX nothing: there, an ask that cannot be delivered is a child
    already out of reach, so the second rung fails the same way and the answer is the same
    sentence.

    The map it was writing is left marked unfinished by its own hand: the marker is
    committed as the run starts, so there is nothing for this to write and nothing here
    that could (rule 20 -- this process never writes to a map).

    Returns what actually happened, because *asked to stop* and *had to be killed* are
    different facts about the child and only one of them is tidy.
    """
    if proc is None or proc.poll() is not None:
        return "it had already ended"
    if _interrupt_group(proc):
        try:
            proc.wait(timeout=grace)
            return "stopped"
        except subprocess.TimeoutExpired:
            pass
    # **Before the kill, and withdrawn if it cannot be delivered.** `taskkill` returns after
    # the child is already gone, so a note taken afterwards is read too late -- see
    # `note_forced`, where the race and the reason it only runs one way are written down.
    note_forced(proc)
    if not _kill_group(proc):
        note_forced(proc, False)
        return "it could not be signalled"
    try:
        proc.wait(timeout=grace)
        return "killed — it did not stop when asked"
    except subprocess.TimeoutExpired:
        return "it would not stop, even when killed"


def run(source: Path, name: str, out_root: Path, docs: bool,
        note: Callable[..., None], *,
        popen: Any = subprocess.Popen,
        on_start: Callable[[Any], None] | None = None) -> None:
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
        # **Its own group**, so stopping it can reach the pool workers it will start.
        # Without this the parent dies and its workers keep the pipes open -- see
        # `own_group`, which is the one place the platform's spelling of that is decided.
        #
        # **And the pipe is read as UTF-8, named rather than left to the locale.** `text=True`
        # alone decodes with `locale.getpreferredencoding()`, which is `cp1252` on a Windows
        # machine in most of the world -- while the child, whose every output file is UTF-8,
        # writes UTF-8. The `--progress-json` contract carries a path, a program name and a
        # failure's own words, any of which can be non-ASCII; with the locale in the middle
        # a step name arrives mojibake and a path outside cp1252 ends the run with a decode
        # error in the watcher rather than a failure in the work.
        proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                     encoding="utf-8", errors="replace", **own_group())
    except OSError as exc:
        note(state="failed", program=name, reason=f"could not start the analysis: {exc}")
        return
    # **Handed out before anything is read**, so the child is reachable for the whole of
    # its life rather than only once this function returns. It was a local here, which
    # meant nothing on the server could stop a run at all -- no route, no button, and a
    # hung child holding the slot until somebody killed the server.
    if on_start is not None:
        on_start(proc)

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
        # **A run somebody stopped is not a run that broke**, and the panel says a different
        # thing about each. A stopped child says so in its own exit code -- so the
        # distinction is in the code itself and does not need a flag set from outside that
        # could disagree with what actually happened (rule 13). Which code that is differs
        # by platform and is `was_stopped`'s to know, not this line's.
        if was_stopped(code) or was_forced(proc):
            how = ("signal " + str(-code) if code < 0
                   else "a console break" if was_stopped(code)
                   else "being killed, having not stopped when asked")
            note(state="stopped", program=name,
                 reason=f"stopped on {how}. What it had written is left marked "
                        f"unfinished — analysing {name} again completes it.")
            return
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
