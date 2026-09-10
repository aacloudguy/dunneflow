"""Where maps are kept, and moving the ones already there.

The frozen application writes to `~/Library/Application Support/DunneFlow`, on the boot
disk, and a reader with disk pressure needs them elsewhere. Two things are being guarded
here and only one of them is the feature:

* **the pointer never causes a directory to be created**, because `/Volumes` is an ordinary
  directory on the boot disk and a pointer at an unplugged drive would otherwise put a new
  empty maps root on exactly the disk the reader is clearing (rule 49);
* **a move that fails loses nothing**, because the alternative is a reader's maps split
  across two roots with nothing recording which half is where.
"""

from __future__ import annotations

import shutil
from collections import namedtuple
from pathlib import Path
from typing import Any

import pytest

from dunneflow import revisions, runtime
from dunneflow.extractors.python.extract import extract_file
from dunneflow.store import Store
from dunneflow.web import roots

_Usage = namedtuple("_Usage", "total used free")

ONE = '''\
"""A program small enough to analyse in a test."""


def go(path):
    """Do the thing."""
    return path
'''


def _make_program(root: Path, name: str) -> Path:
    out = root / name
    out.mkdir(parents=True)
    src = root / f"{name}_src"
    src.mkdir()
    (src / "one.py").write_text(ONE)
    rev = "2026-01-01T00:00:00Z"
    store = Store(revisions.db_path(out, revisions.GRAPH, rev))
    store.write_file_facts(extract_file(src / "one.py", src))
    store.set_meta("revision", rev)
    store.conn.commit()
    store.close()
    return out


# --------------------------------------------------------------- the pointer --- #


def test_the_three_states_of_the_pointer(tmp_path: Path, monkeypatch: Any) -> None:
    """Absent, resolving, and naming a disk that is not here — never two.

    The third is the ordinary case for this feature: an external drive gets unplugged, and
    that is not an error in the reader's choice. It is the one that has to be told apart,
    because the answer to it is *reconnect or choose again* and the answer to the first is
    *use the default*.
    """
    platform = tmp_path / "AppSupport"
    platform.mkdir()
    monkeypatch.setattr(runtime, "platform_output_root", lambda: platform)
    # The pointer is the frozen application's memory and only that world writes it.
    monkeypatch.setattr(runtime, "frozen", lambda: True)

    # Never chosen.
    assert runtime.read_root_pointer() is None

    # Chosen, and there.
    chosen = tmp_path / "OnTheBigDisk"
    chosen.mkdir()
    runtime.write_root_pointer(chosen)
    assert runtime.read_root_pointer() == chosen

    # Chosen, and the disk is gone. **Raises rather than falling back**, and the sentence
    # names both things a reader can do about it (rule 89).
    shutil.rmtree(chosen)
    with pytest.raises(runtime.MapsRootGone) as caught:
        runtime.read_root_pointer()
    assert str(chosen) in str(caught.value)
    assert "reconnect" in str(caught.value).lower()

    # Forgetting is removing the note, never writing today's default into it: a reader who
    # never chose and one who moved back must not become indistinguishable.
    runtime.write_root_pointer(None)
    assert runtime.read_root_pointer() is None
    assert not runtime.root_pointer().exists()


def test_a_missing_root_is_never_created(tmp_path: Path, monkeypatch: Any) -> None:
    """**The one that protects the boot disk.**

    `cmd_serve` calls `mkdir(parents=True)` on a root nobody named. `/Volumes` is an
    ordinary directory *on the boot disk*, so if `read_root_pointer` returned a path for a
    drive that is not mounted, that `mkdir` would create a new empty maps root on the very
    disk the reader moved their maps off — and then report no programs in it. A plausible
    value hiding the failure it was written for (rule 49), in the worst available place.

    So the contract is not merely "it raises": it is that **nothing is brought into being**
    on the way past.
    """
    platform = tmp_path / "AppSupport"
    platform.mkdir()
    monkeypatch.setattr(runtime, "platform_output_root", lambda: platform)
    monkeypatch.setattr(runtime, "frozen", lambda: True)

    absent = tmp_path / "Volumes" / "YourDisk" / "DunneFlow"
    runtime.write_root_pointer(absent)

    with pytest.raises(runtime.MapsRootGone):
        runtime.read_root_pointer()
    assert not absent.exists(), "the chosen root was created on the wrong disk"
    assert not absent.parent.exists(), "a parent of the chosen root was created"


def test_a_checkout_never_reads_the_pointer(tmp_path: Path, monkeypatch: Any) -> None:
    """`output/` is the answer in a checkout, and a note left by the app must not move it.

    Otherwise a developer's `uv run dunneflow analyze` would silently write into their
    application data because they once moved the *application's* maps.
    """
    platform = tmp_path / "AppSupport"
    platform.mkdir()
    monkeypatch.setattr(runtime, "platform_output_root", lambda: platform)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr(runtime, "frozen", lambda: True)
    runtime.write_root_pointer(elsewhere)

    monkeypatch.setattr(runtime, "frozen", lambda: False)
    assert runtime.default_output_root() == Path("output")

    monkeypatch.setattr(runtime, "frozen", lambda: True)
    assert runtime.default_output_root() == elsewhere


# ------------------------------------------------------------- the refusals --- #


def test_each_refusal_says_which_one_it_is(tmp_path: Path) -> None:
    """A reader must never have to guess which refusal they got (`analysis.check`'s rule)."""
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    seen = []

    for path, expect in [
        ("", "no directory was named"),
        ("relative/path", "relative path"),
        (str(tmp_path / "nope"), "does not exist"),
        (str(current), "already where maps are kept"),
        (str(current / "alpha"), "is inside"),
        (str(tmp_path), "contains"),
    ]:
        v = roots.check(path, current)
        assert not v.ok, f"{path!r} was allowed"
        assert expect in v.refusal, f"{path!r} said {v.refusal!r}"
        seen.append(v.refusal)

    a_file = tmp_path / "afile"
    a_file.write_text("x")
    v = roots.check(str(a_file), current)
    assert not v.ok and "not a directory" in v.refusal
    seen.append(v.refusal)

    assert len(set(seen)) == len(seen), f"two refusals share a sentence: {seen}"


def test_a_directory_that_already_holds_maps_is_a_note_and_not_a_refusal(
        tmp_path: Path) -> None:
    """Merging two roots is a legitimate thing to want, and a surprise is not an error.

    `analysis.check`'s distinction exactly: the reader must not find out from the program
    list that four programs they did not move are now sitting beside the ones they did.
    """
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    target = tmp_path / "other"
    _make_program(target, "beta")

    v = roots.check(str(target), current)
    assert v.ok, v.refusal
    assert "beta" in v.note and "already holds" in v.note


def test_a_root_that_cannot_be_written_is_refused_by_pressing_it(tmp_path: Path) -> None:
    """Pressed, never inferred from the mode bits.

    A read-only volume, an ACL and a directory owned by somebody else all read differently
    through `os.access`, and the only answer true on every one of them is what happened when
    we tried to write.
    """
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        v = roots.check(str(locked), current)
        assert not v.ok and "cannot be written to" in v.refusal
    finally:
        locked.chmod(0o700)


# ----------------------------------------------------------------- the move --- #


def test_a_move_carries_every_program_and_leaves_the_old_root_empty(
        tmp_path: Path) -> None:
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    _make_program(current, "beta")
    target = tmp_path / "elsewhere"
    target.mkdir()

    moved = roots.move(current, target)

    assert sorted(moved) == ["alpha", "beta"]
    assert sorted(d.name for d in revisions.program_dirs(target) if d != target) == [
        "alpha", "beta"]
    assert not list(revisions.program_dirs(current) - {current})
    # And the maps still open — a copy that lost a byte would still be a directory.
    for name in ("alpha", "beta"):
        graph = revisions.newest(target / name, revisions.GRAPH)
        assert graph is not None
        store = Store(graph, writable=False)
        assert store.get_meta("revision") == "2026-01-01T00:00:00Z"
        store.close()


def test_a_move_that_fails_half_way_leaves_every_original_where_it_was(
        tmp_path: Path, monkeypatch: Any) -> None:
    """**The property the whole three-pass shape exists for.**

    A per-program move would leave the reader's maps split across two roots after the first
    failure, with nothing recording which half is where — and a half-moved state is not one
    this tool could describe on the start page, because `program_dirs` would answer honestly
    about both roots and the reader would have to work the rest out themselves.

    So nothing is deleted until everything has landed, and a failure takes the partial
    copies with it on the way out. Both halves are asserted: the originals are intact **and**
    the new root is clean, because a partial copy left behind would be listed as a program —
    a map that opens and lies, which is what `complete` was added to the graph to prevent.
    """
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    _make_program(current, "beta")
    target = tmp_path / "elsewhere"
    target.mkdir()

    real = shutil.copytree
    calls = {"n": 0}

    def fail_on_the_second(src: Any, dst: Any, **kw: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("the disk filled up")
        return real(src, dst, **kw)

    monkeypatch.setattr(shutil, "copytree", fail_on_the_second)

    with pytest.raises(OSError, match="the disk filled up"):
        roots.move(current, target)

    assert calls["n"] == 2, "the move stopped before it reached the failure"
    assert sorted(d.name for d in revisions.program_dirs(current) if d != current) == [
        "alpha", "beta"], "an original was removed by a failed move"
    assert not list(target.iterdir()), f"a partial copy was left in {target}"


def test_a_move_refuses_rather_than_overwriting_a_map_already_there(
        tmp_path: Path) -> None:
    """Two roots merging is allowed; two programs of one name colliding is not.

    `check` says the destination already holds maps as a *note*, because merging is
    legitimate. A name collision inside that merge is different: one of the two would be
    destroyed, and which one is not something a reader chose.
    """
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    target = tmp_path / "elsewhere"
    _make_program(target, "alpha")

    with pytest.raises(FileExistsError, match="already there"):
        roots.move(current, target)

    # Untouched, both of them.
    assert (current / "alpha").is_dir()
    assert revisions.newest(target / "alpha", revisions.GRAPH) is not None


def test_room_is_checked_before_a_byte_is_copied(tmp_path: Path, monkeypatch: Any) -> None:
    """The reader's whole reason for moving is disk pressure.

    Discovering the shortfall half way through a 4 GB copy is the wrong time and the wrong
    place, so the refusal comes first and **carries the numbers** — `_mb`, never bytes,
    because 176,160,768 is not a size anybody reads (rule 32: say what the number is).
    """
    current = tmp_path / "maps"
    _make_program(current, "alpha")
    target = tmp_path / "tiny"
    target.mkdir()

    # One byte free. `disk_usage` returns a named tuple, so the stand-in is one too.
    monkeypatch.setattr(shutil, "disk_usage", lambda _p: _Usage(total=1, used=0, free=1))
    v = roots.will_fit(current, target)
    assert not v.ok
    assert "will not fit" in v.refusal
    assert "bytes" in v.refusal or "kB" in v.refusal or "MB" in v.refusal


def test_a_checkout_never_writes_the_pointer(tmp_path: Path, monkeypatch: Any) -> None:
    """**The two worlds share a home directory and must not share this file.**

    Found immediately and the hard way. A checkout's `serve` moved two maps into a
    scratchpad directory and stamped that path into the *real*
    `~/Library/Application Support/DunneFlow/root` — so the packaged application would have
    opened next, found a temporary directory that no longer existed, and told its reader
    their maps were on a disk that was gone. The tell was `test_frozen.py` failing with a
    path from another session.

    It is design rule 16 from both sides at once: writing a setting a checkout never reads
    is a control that appears to work and changes nothing here, while changing something
    real over in the other world.
    """
    platform = tmp_path / "AppSupport"
    platform.mkdir()
    monkeypatch.setattr(runtime, "platform_output_root", lambda: platform)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.setattr(runtime, "frozen", lambda: False)
    runtime.write_root_pointer(elsewhere)
    assert not runtime.root_pointer().exists(), (
        "a checkout wrote the frozen application's pointer — the packaged app on this "
        "machine would open somewhere the developer never meant to send it"
    )

    # And the frozen world still writes it, or the guard has taken the feature with it.
    monkeypatch.setattr(runtime, "frozen", lambda: True)
    runtime.write_root_pointer(elsewhere)
    assert runtime.read_root_pointer() == elsewhere
