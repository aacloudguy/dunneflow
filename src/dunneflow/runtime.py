"""What this build of DunneFlow is, and where it lives.

One place, because every question here has two answers -- one for a source checkout and
one for a frozen application -- and a second copy of that branch is rule 51's own defect
waiting to happen. Four modules asked `Path(__file__)` where they meant *my files*, and
frozen every one of them is wrong in a different way.

Named `runtime` rather than `paths` deliberately. A *path* in this codebase is a stored
key, relative to the tree a store was read from (rule 60); nothing in here is one of
those. These are questions about the running program.

**Frozen is asked, never cached.** `frozen()` and `resource_root()` read `sys` on every
call rather than settling at import, so a test can put this module in the other world
without a build. What the callers do with the answer is theirs -- `detectors` settles its
directories at import, because a frozen app does not become a source checkout halfway
through a run.
"""

from __future__ import annotations

import os
import sys
from importlib import metadata
from pathlib import Path


def frozen() -> bool:
    """Is this a packaged application rather than a source checkout?

    `sys.frozen` is set by PyInstaller and by py2app alike, and by nothing else. Asked
    through `getattr` because it does not exist at all in a normal interpreter -- and a
    `hasattr` guard elsewhere would be a second spelling of this one question.
    """
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """The directory holding this package's files, wherever they are today.

    In a checkout that is `src/dunneflow/`. Frozen, PyInstaller unpacks the bundle to
    `sys._MEIPASS` and the spec places this package's data under `dunneflow/` inside it,
    so the answer is `<_MEIPASS>/dunneflow` -- **the same last segment either way.**

    That is not tidiness. `fingerprint_files` labels each input by its path *relative to
    this root*, so a bundle laid out this way yields exactly the fingerprint the source
    tree yields for the same commit. A map written by the binary is then readable by the
    checkout and back; laid out any other way the two builds would refuse each other's
    maps under rule 12, which is the opposite of what that rule is for.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if frozen() and meipass:
        return Path(meipass) / "dunneflow"
    return Path(__file__).parent


def default_output_root() -> Path:
    """Where maps go when nobody said.

    Two answers to one question, keyed on the one honest fact that separates them: a
    checkout is run from a working directory somebody chose, and a double-clicked
    application has no working directory worth the name -- `Path("output")` there would
    resolve against `/` or against wherever the Finder happened to launch from.

    `~/Library/Application Support/DunneFlow` is Apple's answer for an application's own
    data and, unlike `~/Documents`, is never swept into iCloud Drive. That matters here
    rather than being correctness for its own sake: `source.db` holds the private source
    of whatever was read, and a synced Documents folder would upload it -- egress by
    accident, out of a tool whose whole posture is deterministic and local (design rule
    14). The cost is that it is invisible in the Finder, which is why the start page
    states the root as a path and offers to reveal it.

    The two non-macOS branches are the conventional locations and are **untested** --
    Windows is deliberately after this milestone and no Linux build is planned. They are
    here rather than absent because a wrong default is worse than an unexercised one, and
    a `KeyError` from an absent branch would be worse than both.
    """
    if not frozen():
        return Path("output")
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "DunneFlow"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / "DunneFlow"
    return home / ".local" / "share" / "DunneFlow"


def self_argv(*args: str) -> list[str]:
    """The command that runs *this* DunneFlow again, with `args` after it.

    The server runs an analysis as a subprocess rather than in-process -- rule 20, and so
    that what runs is exactly the tested command rather than a second assembly of the same
    steps. That only works if the subprocess is this same build.

    `-m dunneflow.cli` means nothing to a frozen binary: `sys.executable` *is* DunneFlow
    there, and it takes its subcommand straight. Without this branch **+ Analyze a
    directory...** -- the only way a first-time reader gets a map at all -- would fail with
    an interpreter's complaint about a module.
    """
    if frozen():
        return [sys.executable, *args]
    return [sys.executable, "-m", "dunneflow.cli", *args]


def tool_version() -> str:
    """Which DunneFlow read this map. From the package metadata, never a literal beside it.

    A literal is a second answer to a question `pyproject.toml` already answers, and it is
    the copy that goes stale (rule 51). An editable install with no metadata is a real
    state and says so rather than claiming a version it cannot know.

    **Frozen, this keeps working rather than gaining a branch.** The spec calls
    PyInstaller's `copy_metadata('dunneflow')`, so the dist-info travels in the bundle and
    `metadata.version` answers there exactly as it does here. The alternative -- stamping a
    version into a file at build time -- would be the literal this docstring refuses, one
    build system further away.
    """
    try:
        return metadata.version("dunneflow")
    except metadata.PackageNotFoundError:
        return ""
