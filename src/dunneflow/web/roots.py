"""Choosing where maps are kept, and moving the ones that are already there.

The application writes to `~/Library/Application Support/DunneFlow`, which is the right
place for an application's own data and is on the boot disk. Maps are not small -- one
Society snapshot is 168 MB, and `source.db` and `docsource.db` grow with every revision
captured -- so a reader with disk pressure needs them somewhere else, and until this module
existed there was no way to say so short of a terminal.

**Two operations, and they are separable on purpose.** Pointing says *maps live here now*;
moving carries the existing ones across. The dialog offers both together because a reader
who points without moving watches their program list empty itself, which is alarming and
looks like data loss -- but the move is a checkbox and not a precondition, because a reader
whose old disk is full may have no way to read the old maps at all and still wants the new
location. Design rule 2: when two readings are both real, build both.

**Everything here is checked before anything is done.** `check` returns the same `Verdict`
`analysis.check` does, so the warning under the field while somebody is typing and the
refusal when they press the button are one function's answer and cannot drift (rule 41).

**The move is copy-verify-delete, never a rename.** `os.rename` across filesystems fails,
and the whole point is that the destination is a different disk; `shutil.move` would fall
back to a copy that is not verified. More importantly, nothing is deleted until *every*
program has landed: a move that fails half way leaves the reader's maps split across two
roots with no record of which is which, and that is worse than not having moved at all.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from .. import revisions
from .analysis import Verdict

# What a map directory is allowed to cost before the reader is told the number. Not a limit
# -- a **note**, on `analysis.check`'s precedent: a surprise is not an error, and a reader
# moving 4 GB onto a nearly full disk should be told rather than stopped, because only they
# know what else is going there. Refusal is reserved for *it will not fit*.
HEADROOM = 1.05


def _size(path: Path) -> int:
    """Bytes under `path`, following nothing. Symlinks are counted as links, not targets.

    A map directory holds databases and generated Markdown and nothing else, so there is
    normally no link in it at all -- but a reader's output root is a directory they own, and
    following a link out of it would measure something that is not being moved.
    """
    total = 0
    for p in path.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        try:
            total += p.stat().st_size
        except OSError:
            # A file that vanished between the walk and the stat is not a measurement
            # failure worth refusing over -- it is a file that is no longer there to move.
            continue
    return total


def check(path: str, current: Path) -> Verdict:
    """May maps be kept here, and is there anything the reader should know first?

    The refusals are in the order somebody hits them and **each has its own sentence**,
    because *that is where they already are* and *that is inside the maps directory* are
    different answers and a reader must never have to guess which one they got
    (`analysis.check`'s discipline, one subject over).
    """
    if not path.strip():
        return Verdict(refusal="no directory was named")
    chosen = Path(path.strip()).expanduser()
    if not chosen.is_absolute():
        return Verdict(refusal=f"{chosen} is a relative path — give the whole path, "
                               "because the server's directory is not yours")
    try:
        chosen = chosen.resolve()
    except OSError as exc:
        return Verdict(refusal=f"{chosen} could not be read: {exc}")

    # **Not created here, and that is the rule this whole feature turns on.** `/Volumes` is
    # an ordinary directory on the boot disk, so `mkdir(parents=True)` on a path naming an
    # unplugged drive silently makes a new empty maps root on exactly the disk the reader is
    # trying to clear -- and then reports no programs in it (rule 49). A directory the
    # reader means to use is one they can point at.
    if not chosen.exists():
        return Verdict(refusal=f"{chosen} does not exist — make it first, or pick a "
                               "directory that is already there. If it is on another disk, "
                               "check that disk is connected.")
    if not chosen.is_dir():
        return Verdict(refusal=f"{chosen} is a file, not a directory")

    here = current.resolve()
    if chosen == here:
        return Verdict(refusal=f"{chosen} is already where maps are kept")
    # **Both directions, and neither is theoretical.** A root inside the current root would
    # be walked by `program_dirs` as one of its own programs; the current root inside the
    # new one would make every existing map a program of the new root the moment it moved.
    if chosen.is_relative_to(here):
        return Verdict(refusal=f"{chosen} is inside {here}, which is where maps are kept "
                               "now — pick a directory outside it")
    if here.is_relative_to(chosen):
        return Verdict(refusal=f"{chosen} contains {here}, where maps are kept now — "
                               "pick a directory that does not")

    probe = chosen / ".dunneflow-write-test"
    try:
        probe.touch()
        probe.unlink()
    except OSError as exc:
        # **Pressed, not inferred from the mode bits.** A read-only volume, an ACL and a
        # directory owned by somebody else all read differently through `os.access`, and the
        # only answer that is true on every one of them is what happened when we tried.
        return Verdict(refusal=f"{chosen} cannot be written to: {exc}")

    holds = [d.name for d in revisions.program_dirs(chosen) if d != chosen]
    if holds:
        # Allowed and **said out loud**. Two roots merging is a legitimate thing to want,
        # and a reader who did not expect it must not find out from the program list.
        return Verdict(note=f"{chosen} already holds "
                            f"{len(holds)} program{'s' if len(holds) != 1 else ''} "
                            f"({', '.join(sorted(holds)[:4])}"
                            f"{'…' if len(holds) > 4 else ''}). They will be listed "
                            "alongside anything moved there.")
    return Verdict()


def will_fit(source_root: Path, target: Path) -> Verdict:
    """Is there room, and how much is being asked for? Asked **before** a byte is copied.

    Its own function rather than part of `check`, because it answers a question about a
    *move* and `check` answers one about a *directory*: pointing without moving needs no
    room at all, and a reader who unticked the box must not be refused for space they are
    not going to use (rule 32's neighbourhood -- say what the number is about).

    The whole reason this feature exists is disk pressure, so discovering the shortfall
    half way through a copy is the wrong time and the wrong place to discover it.
    """
    want = _size(source_root)
    try:
        free = shutil.disk_usage(target).free
    except OSError as exc:
        return Verdict(refusal=f"how much room is on {target} could not be read: {exc}")
    if free < want * HEADROOM:
        return Verdict(refusal=f"{_mb(want)} of maps will not fit in {_mb(free)} free on "
                               f"{target} — free some space there, or move fewer programs "
                               "by deleting the ones you no longer want first")
    return Verdict(note=f"{_mb(want)} will be copied, then removed from the old location.")


def _mb(n: int) -> str:
    """Bytes in the unit a reader thinks in. Never bytes: 176,160,768 is not a size."""
    for unit, scale in (("GB", 1 << 30), ("MB", 1 << 20), ("kB", 1 << 10)):
        if n >= scale:
            return f"{n / scale:.1f} {unit}"
    return f"{n} bytes"


def move(source_root: Path, target: Path,
         step: Callable[[str, int, int], None] | None = None) -> list[str]:
    """Carry every program from `source_root` to `target`. Returns the names moved.

    **Copy everything, verify everything, then delete.** Three passes rather than a move
    per program, and the ordering is the whole guarantee: a failure at any point leaves
    every original exactly where it was, and takes the partial copies with it on the way
    out. A per-program move would leave a reader's maps split across two roots after the
    first failure, with nothing recording which half is where -- and the half-moved state
    is not one this tool could describe on the start page, because `program_dirs` would
    answer honestly about both roots and the reader would have to work out the rest.

    Raises rather than reporting, unlike an analysis: this runs in the request that asked
    for it, so the exception is the answer. `analysis.run` reports because its work outlives
    the request that started it, which is a different shape (rule 82).
    """
    programs = sorted(d for d in revisions.program_dirs(source_root) if d != source_root)
    landed: list[Path] = []
    try:
        for i, d in enumerate(programs):
            if step is not None:
                step(f"copying {d.name}", i, len(programs))
            dest = target / d.name
            if dest.exists():
                raise FileExistsError(
                    f"{dest} is already there — this would overwrite a map that is "
                    f"already in the new location. Nothing has been moved."
                )
            # `copytree` rather than `shutil.move`: move degrades to a copy across
            # filesystems and reports success without the originals having been read back,
            # and across filesystems is the only case this feature has.
            shutil.copytree(d, dest, symlinks=True)
            landed.append(dest)
        # Verified before a single original is removed. Sizes rather than hashes: a map
        # directory is hundreds of megabytes and re-reading it all to hash would double the
        # cost of the move for a guarantee `copytree` failing loudly already gives. What
        # this catches is a copy that silently ran short -- a full disk between the
        # headroom check and the last file.
        for d, dest in zip(programs, landed, strict=True):
            if _size(dest) != _size(d):
                raise OSError(f"{dest} did not copy completely. Nothing has been removed.")
    except Exception:
        # **The originals are untouched, so the only thing to undo is what we made.** A
        # partial copy left in the new root would be listed as a program by
        # `program_dirs` -- a half-written map that opens and lies, which is the thing
        # `complete` was added to the graph to prevent, arriving by a different route.
        for dest in landed:
            shutil.rmtree(dest, ignore_errors=True)
        raise
    for i, d in enumerate(programs):
        if step is not None:
            step(f"removing {d.name} from the old location", len(programs) + i,
                 len(programs) * 2)
        shutil.rmtree(d)
    return [d.name for d in programs]
