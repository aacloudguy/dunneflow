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


class MapsRootGone(RuntimeError):
    """The reader chose a maps directory and it is not there right now.

    Its own class because it is the **one** state here that is neither an error in the
    program nor an answer it can act on: the pointer is intact, the choice still stands, and
    a disk is unplugged. Everything the sentence needs is in the message, because the two
    surfaces that catch it -- `serve`'s boot and the start page -- both just say it.
    """


def platform_output_root() -> Path:
    """Where a frozen application's maps go when the reader has never said otherwise.

    Apple's answer for an application's own data, and -- unlike `~/Documents` -- never swept
    into iCloud Drive. That matters here rather than being correctness for its own sake:
    `source.db` holds the private source of whatever was read, and a synced Documents folder
    would upload it, which is egress by accident out of a tool whose whole posture is
    deterministic and local (design rule 14).

    The two non-macOS branches are the conventional locations and are **untested** -- Windows
    is deliberately after this milestone and no Linux build is planned. They are here rather
    than absent because a wrong default is worse than an unexercised one, and a `KeyError`
    from an absent branch would be worse than both.

    Split out of `default_output_root` when the root became movable: this is the place that
    never moves, which is what makes it the right place to keep the note saying where the
    reader moved it to.
    """
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "DunneFlow"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / "DunneFlow"
    return home / ".local" / "share" / "DunneFlow"


def root_pointer() -> Path:
    """The file naming where the reader keeps their maps.

    **It cannot live in the maps directory**, which is the thing it locates, so it lives at
    the one address that never moves -- inside the platform default, whether or not any map
    is there. A few bytes left behind on the boot disk is the whole cost of being able to
    keep everything else off it.

    One line, an absolute path, no format. A key/value file would invite a second key, and
    the second key is where *"where are my maps"* stops having one answer (rule 51).
    """
    return platform_output_root() / "root"


def read_root_pointer() -> Path | None:
    """The chosen maps directory, or `None` if the reader has never chosen one.

    **Three states, never two**, and the third is why this raises rather than returning:

    * no pointer -- never chosen, and the platform default is the answer;
    * a pointer naming a directory that is there -- that directory;
    * a pointer naming one that is **not** -- `MapsRootGone`, because an external disk that
      is unplugged is the ordinary case for this feature and not an error in the choice.

    **The target is never created, and that is the sharpest line in this module.**
    `cmd_serve` calls `mkdir(parents=True)` on a root nobody named, which is right for the
    platform default and catastrophic here: `/Volumes` is an ordinary directory *on the boot
    disk*, so a pointer at `/Volumes/YourDisk/DunneFlow` with the drive unplugged would
    silently create that path on the very disk the reader moved their maps off, and then
    report no programs in it. A plausible value hiding the failure it was written for
    (rule 49), on the one disk this feature exists to keep clear.

    A pointer that cannot be read at all is treated as absent rather than fatal -- the
    reader can always choose again, and refusing to start over an unreadable byte would
    strand them with no way to fix it.
    """
    note = root_pointer()
    try:
        said = note.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not said:
        return None
    chosen = Path(said)
    if chosen.is_dir():
        return chosen
    # Named, and not there. The sentence has to name something that can act on it (rule 89),
    # and there are exactly two things: bring the disk back, or choose somewhere else.
    raise MapsRootGone(
        f"maps are kept in {chosen}, which is not there right now — reconnect that disk, "
        f"or choose somewhere else"
    )


def write_root_pointer(where: Path | None) -> None:
    """Remember where maps go, or forget and fall back to the platform default.

    `None` **removes** the pointer rather than writing the default into it. Writing the
    default would freeze today's answer into a file, so a reader who had never moved
    anything and a reader who moved back would be indistinguishable -- and the day the
    platform answer changes, the second one would keep the old one for ever (rule 30: the
    file records a *choice*, and "no choice" is not a path).

    **A checkout does not write it, and that is the same line `default_output_root` draws
    from the other side.** A checkout never *reads* the pointer -- `output/` is relative to
    the working directory somebody chose -- so writing one from a checkout is writing a
    setting nothing in that world consults, which is design rule 16's defect: a control that
    appears to work and changes nothing you can see. What it *does* change is the frozen
    application's idea of where its maps are, on the same machine.

    Found the hard way, immediately. A checkout's `serve` moved two maps into a scratchpad
    directory and stamped that path into `~/Library/Application Support/DunneFlow/root` --
    so the packaged application would have opened next, found a temporary directory that no
    longer existed, and told its reader their maps were on a disk that was gone. The two
    worlds share a home directory; they must not share this file.
    """
    if not frozen():
        return
    note = root_pointer()
    note.parent.mkdir(parents=True, exist_ok=True)
    if where is None:
        note.unlink(missing_ok=True)
        return
    note.write_text(f"{where}\n", encoding="utf-8")


def default_output_root() -> Path:
    """Where maps go when nobody said.

    Two answers to one question, keyed on the one honest fact that separates them: a
    checkout is run from a working directory somebody chose, and a double-clicked
    application has no working directory worth the name -- `Path("output")` there would
    resolve against `/` or against wherever the Finder happened to launch from.

    Where a frozen build's maps go by default, and why it is `Application Support` rather
    than `~/Documents`, is `platform_output_root`'s to say -- it moved there when this
    function stopped being the only answer. The cost of that location is that it is
    invisible in the Finder, which is why the start page states the root as a path and
    offers to reveal it.

    **A checkout never reads the pointer.** `output/` is relative to the working directory
    somebody chose by running the command there, and that *is* the answer in a checkout --
    a note left by the application would silently redirect a developer's `uv run dunneflow
    analyze` into their application data. The two worlds keep their own answer, which is
    what this function has always been for.

    Frozen, the reader may have moved their maps, so `read_root_pointer` decides -- and it
    **raises** rather than falling back when the chosen directory is not there. See its
    docstring: a fallback here would recreate the root on the boot disk.
    """
    if not frozen():
        return Path("output")
    return read_root_pointer() or platform_output_root()


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
