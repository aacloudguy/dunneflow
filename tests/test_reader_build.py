"""A reader shipped as source, built once per version of its bytes on the machine reading.

Go's reader is the first of these: its checker needs the `go` toolchain at run time
anyway, so building with it costs nothing more than being able to run at all, and one
fingerprint serves every platform (rule 12). These tests press the build seam with a
stand-in compiler — this interpreter, copying a file — so that they run on all three
platforms whether or not Go is installed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from dunneflow import detectors
from dunneflow.ingest import read_manifest
from dunneflow.ingest.contract import PluginRefused
from dunneflow.ingest.outofprocess import built_reader, plugin_argv
from dunneflow.schema import SCHEMA_VERSION

# The stand-in compiler: writes a marker to `{output}` and counts its runs beside itself.
_COMPILER = (
    "import pathlib, sys\n"
    "here = pathlib.Path('.')\n"
    "n = here / 'runs'\n"
    "n.write_text(str(int(n.read_text()) + 1) if n.exists() else '1')\n"
    "pathlib.Path(sys.argv[1]).write_text('built')\n"
)


def _plugin(tmp_path: Path, build: list[str] | None = None, compiler: str = _COMPILER,
            ) -> Path:
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "compile.py").write_text(compiler, encoding="utf-8")
    (root / "plugin.json").write_text(json.dumps({
        "lang": "fake", "protocol": 1,
        "schema_version": SCHEMA_VERSION,
        "discovery": {"suffixes": [".fake"]},
        "toolchain": {"command": sys.executable, "probe": ["--version"]},
        "build": build if build is not None else [sys.executable, "compile.py", "{output}"],
        "fingerprint": ["compile.py"],
    }), encoding="utf-8")
    return root / "plugin.json"


@pytest.fixture
def cache(tmp_path, monkeypatch) -> Path:
    where = tmp_path / "cache"
    monkeypatch.setattr("dunneflow.ingest.outofprocess.reader_cache_root", lambda: where)
    monkeypatch.setattr(detectors, "lang_fingerprint", lambda _lang: "0.1.0:aaaaaaaaaaaaaaaa")
    return where


def test_a_built_reader_is_built_once_and_then_run_from_the_cache(tmp_path, cache):
    m = read_manifest(_plugin(tmp_path))
    first = built_reader(m)
    assert first.read_text() == "built"
    assert first.is_relative_to(cache)
    again = built_reader(m)
    assert again == first
    assert (m.root / "runs").read_text() == "1", "a warm run must not build again"


def test_the_argv_is_the_built_program_and_nothing_else(tmp_path, cache):
    m = read_manifest(_plugin(tmp_path))
    argv = plugin_argv(m)
    assert argv == [str(built_reader(m))]


def test_a_new_version_of_the_reader_is_a_new_build(tmp_path, cache, monkeypatch):
    """Rule 81: the key carries everything the work depends on, the reader's bytes first."""
    m = read_manifest(_plugin(tmp_path))
    first = built_reader(m)
    monkeypatch.setattr(detectors, "lang_fingerprint", lambda _lang: "0.1.0:bbbbbbbbbbbbbbbb")
    second = built_reader(m)
    assert second != first
    assert (m.root / "runs").read_text() == "2"


def test_a_build_that_fails_refuses_naming_the_command_and_the_way_forward(tmp_path, cache):
    """Rule 89: the refusal names a command that can act, and says whose fault it is."""
    m = read_manifest(_plugin(tmp_path, compiler="import sys\nsys.exit('no compiler today')\n"))
    with pytest.raises(PluginRefused) as exc:
        built_reader(m)
    said = str(exc.value)
    assert "compile.py" in said and "--without fake" in said
    assert "no compiler today" in said
    assert not any(p.is_file() for p in cache.rglob("fake*")), "no half-built reader is kept"


def test_a_build_that_names_no_output_is_refused_when_it_is_read(tmp_path):
    with pytest.raises(PluginRefused) as exc:
        read_manifest(_plugin(tmp_path, build=[sys.executable, "compile.py"]))
    assert "{output}" in str(exc.value)
