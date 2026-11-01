"""The Go reader: generated where it can be, pinned where it cannot, and asked through the host.

Three kinds of claim, and only the last needs Go on the machine:

- **What is generated is current.** `facts.go` and `tests/fixtures/ids/vectors.json` are
  regenerated from `schema.py` and compared, so a schema change that was not carried to the
  reader fails here rather than as a codec refusal on every Go file (`gen_facts_ts`'s lesson).
- **The second implementations agree with the first.** BLAKE2b, every id function and
  Python's `errors="replace"` decoding are written again in Go, and `go test` holds them
  to the vectors the host wrote.
- **The reader answers the host as the host asks.** Built, handshaken, opened and read
  through `OutOfProcessPlugin`, never by a script of this file's own (rule 48's shape: the
  path the product takes is the path that is proved).

Skipped for two named reasons only, each said in the skip: this build has no Go plugin,
or this machine has no `go`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.schema import hash_source

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gen_facts_go  # noqa: E402

PLUGIN = ingest.PLUGINS.get("go")
HERE = PLUGIN.manifest.root if PLUGIN is not None else None

needs_plugin = pytest.mark.skipif(PLUGIN is None, reason="this build ships no Go reader")
needs_go = pytest.mark.skipif(shutil.which("go") is None,
                              reason="no `go` on this machine, so the reader cannot be built")


# ---------------------------------------------------------- generated, no Go --- #

@needs_plugin
def test_the_reader_s_types_are_the_schema_s():
    assert HERE is not None
    assert (HERE / "facts.go").read_text(encoding="utf-8") == gen_facts_go.generate(), (
        "facts.go is not what schema.py generates: "
        "uv run python tools/gen_facts_go.py --write")


def test_the_id_vectors_are_the_host_s():
    assert gen_facts_go.VECTORS.read_text(encoding="utf-8") == gen_facts_go.vectors(), (
        "tests/fixtures/ids/vectors.json is not what the host computes: "
        "uv run python tools/gen_facts_go.py --write")


@needs_plugin
def test_every_source_file_is_in_the_fingerprint():
    """Rule 12. A `.go` file that is built and not hashed is a reader that can change
    without the map noticing. Named, never globbed, so this is what catches a new file."""
    assert PLUGIN is not None and HERE is not None
    built = {p.name for p in HERE.glob("*.go") if not p.name.endswith("_test.go")}
    named = set(PLUGIN.manifest.fingerprint)
    assert built <= named, f"built and not fingerprinted: {sorted(built - named)}"
    assert "go.mod" in named and "plugin.json" in named


@needs_plugin
def test_the_judgements_are_declared_and_not_defaulted():
    """Go has no async/await and the compiler refuses a real redefinition: both detectors
    are silent for Go **by declaration**, which `go.yaml` says in words (rule 98)."""
    from dunneflow.detectors import load_rules

    rules = load_rules("go")
    assert rules.unawaited_async == ""
    assert rules.redefinition == ""
    assert {"append", "len", "make", "new", "panic"} <= set(rules.builtins)


# -------------------------------------------------------------- with Go ------- #

@needs_plugin
@needs_go
def test_the_second_implementations_agree_with_the_first():
    out = subprocess.run(  # noqa: S603
        ["go", "test", "./..."], cwd=HERE, capture_output=True, text=True, timeout=600,
        check=False, env={**os.environ, "GOTOOLCHAIN": "local", "GOFLAGS": ""},
    )
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-3000:]


@needs_plugin
@needs_go
def test_go_vet_is_clean():
    out = subprocess.run(  # noqa: S603
        ["go", "vet", "./..."], cwd=HERE, capture_output=True, text=True, timeout=600,
        check=False, env={**os.environ, "GOTOOLCHAIN": "local", "GOFLAGS": ""},
    )
    assert out.returncode == 0, out.stderr[-3000:]


@pytest.fixture(scope="module")
def read(tmp_path_factory):
    """A small tree, read in one session through the host: CRLF and mixed bad bytes in
    one file, a parse error in another."""
    if PLUGIN is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    plugin = PLUGIN
    root = tmp_path_factory.mktemp("gotree")
    (root / "a.go").write_bytes(
        b"package main\r\n\r\nfunc main() {}\r\n// \xe2\x82A \xff \xed\xa0\x80 \xf0\x9f\x98\n")
    (root / "broken.go").write_bytes(b"package main\nfunc (\n")
    (root / "pkg").mkdir()
    (root / "pkg" / "run.go").write_bytes(b"package pkg\n\nfunc Run() {}\n")
    files = sorted(root.rglob("*.go"))
    plugin.probe()
    plugin.open(root, files)
    try:
        facts = {ff.path: ff for ff in plugin.extract(files, root)}
        edges = list(plugin.edges())
    finally:
        plugin.close()
    return root, facts, edges


def test_the_handshake_agrees_with_the_manifest(read):
    """`open` succeeding is the proof: `NdjsonWorker._handshake` refuses the language on any
    disagreement about lang, version, protocol, schema or capability (rule 30)."""
    _, facts, _ = read
    assert facts


def test_a_crlf_file_with_bad_bytes_hashes_as_the_host_hashes_it(read):
    """The echo check would have turned a disagreement into a synthesised failure."""
    root, facts, _ = read
    ff = facts["a.go"]
    assert ff.errors == []
    assert ff.content_hash == hash_source(
        (root / "a.go").read_text(encoding="utf-8", errors="replace"))


def test_a_file_that_will_not_parse_is_facts_with_errors(read):
    _, facts, _ = read
    ff = facts["broken.go"]
    assert ff.errors and "expected" in ff.errors[0]
    assert ff.content_hash, "a parse error is still a file whose bytes are known, so cached"


def test_paths_and_modules_are_spelled_as_every_reader_spells_them(read):
    _, facts, _ = read
    assert set(facts) == {"a.go", "broken.go", "pkg/run.go"}
    assert facts["pkg/run.go"].module == "pkg.run"
    assert all(ff.lang == "go" for ff in facts.values())
