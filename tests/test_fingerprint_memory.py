"""A fingerprint is remembered between processes, and only while its inputs are unchanged.

Opening a map hashed the tool's own readers in every process: 7.1 s of a 7.7 s read-only
open on a USB disk, 215 of the 286 reads being Rust's reader, and the dashboard's start
page took 8 s to list three programs. `remembered_fingerprint` keeps the answer keyed on
what the files' metadata says. These pin the two halves of rule 81 -- the answer is reused
when nothing changed, and is **not** when anything the hash depends on did -- and rule 12:
the remembered value is the same value, so no existing map's stamps move.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from dunneflow import detectors, runtime


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    where = tmp_path / "data"
    monkeypatch.setattr(runtime, "platform_output_root", lambda: where)
    return where


def _files(tmp_path: Path) -> list[Path]:
    a, b = tmp_path / "a.yaml", tmp_path / "b.py"
    a.write_text("rule: one\n")
    b.write_text("print('x')\n")
    return [a, b]


def test_the_remembered_value_is_the_computed_value(home: Path, tmp_path: Path) -> None:
    files = _files(tmp_path)
    assert detectors.remembered_fingerprint(files) == detectors.fingerprint_files(files)
    assert (home / detectors.FINGERPRINT_CACHE).is_file()


def test_unchanged_inputs_are_not_read_again(home, tmp_path, monkeypatch) -> None:
    files = _files(tmp_path)
    first = detectors.remembered_fingerprint(files)

    def refuse(_paths):
        raise AssertionError("the files were hashed again though nothing changed")

    monkeypatch.setattr(detectors, "fingerprint_files", refuse)
    assert detectors.remembered_fingerprint(files) == first


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no change time to see it")
def test_an_edit_that_hides_its_size_and_mtime_is_still_seen(home, tmp_path) -> None:
    """`touch -r` after an edit of the same length: size and mtime say nothing happened."""
    files = _files(tmp_path)
    before = detectors.remembered_fingerprint(files)
    st = files[0].stat()
    files[0].write_text("rule: two\n")                       # same length
    os.utime(files[0], ns=(st.st_atime_ns, st.st_mtime_ns))  # mtime put back
    assert files[0].stat().st_size == st.st_size
    after = detectors.remembered_fingerprint(files)
    assert after != before and after == detectors.fingerprint_files(files)


def test_a_missing_input_is_still_refused_loudly(home, tmp_path) -> None:
    files = _files(tmp_path)
    detectors.remembered_fingerprint(files)
    files[1].unlink()
    with pytest.raises(detectors.RulesMissing):
        detectors.remembered_fingerprint(files)


def test_an_unwritable_cache_is_not_a_failure(tmp_path, monkeypatch) -> None:
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("")
    monkeypatch.setattr(runtime, "platform_output_root", lambda: blocker / "under")
    files = _files(tmp_path)
    assert detectors.remembered_fingerprint(files) == detectors.fingerprint_files(files)
