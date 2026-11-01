"""The Rust reader: generated where it can be, pinned where it cannot, and asked through the host.

`test_go_reader.py`'s three kinds of claim, and only the last needs cargo on the machine:

- **What is generated is current.** `src/facts.rs` and the fingerprint list are regenerated
  from `schema.py` and from the tree, and compared.
- **The second implementations agree with the first.** BLAKE2b, every id function and the
  decoding are written again in Rust, and `cargo test` holds them to the vectors the host
  wrote (`tests/fixtures/ids/vectors.json`, which `gen_facts_go.py` keeps).
- **The reader answers the host as the host asks.** Built by the host's own `build` seam,
  handshaken, opened and read through `OutOfProcessPlugin` (rule 48's shape).

Skipped for two named reasons only, each said in the skip: this build has no Rust plugin,
or this machine has no `cargo`.
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

import gen_facts_rs  # noqa: E402

PLUGIN = ingest.PLUGINS.get("rust")
HERE = PLUGIN.manifest.root if PLUGIN is not None else None

needs_plugin = pytest.mark.skipif(PLUGIN is None, reason="this build ships no Rust reader")
needs_cargo = pytest.mark.skipif(shutil.which("cargo") is None,
                                 reason="no `cargo` on this machine, so the reader cannot be built")


# ------------------------------------------------------- generated, no cargo --- #

@needs_plugin
def test_the_reader_s_types_are_the_schema_s():
    assert HERE is not None
    assert (HERE / "src" / "facts.rs").read_text(encoding="utf-8") == gen_facts_rs.generate(), (
        "src/facts.rs is not what schema.py generates: "
        "uv run python tools/gen_facts_rs.py --write")


@needs_plugin
def test_every_file_the_reader_is_built_from_is_in_the_fingerprint():
    """Rule 12, over a vendored tree. Named, never globbed — so this is the glob, and it
    is what catches a file added to `src/` or a crate re-vendored without `--write`."""
    assert PLUGIN is not None and HERE is not None
    named = list(PLUGIN.manifest.fingerprint)
    assert named == gen_facts_rs.fingerprint(), (
        "plugin.json's fingerprint is not the files on disk: "
        "uv run python tools/gen_facts_rs.py --write")
    for fixed in ("plugin.json", "Cargo.toml", "Cargo.lock", ".cargo/config.toml"):
        assert fixed in named
    assert not any(n.startswith("target/") for n in named), "a build's output is not a source"


@needs_plugin
def test_the_build_writes_nothing_inside_the_package_and_fetches_nothing():
    """`{workdir}` keeps cargo's `target/` out of a signed bundle, and `--offline --locked`
    with the vendored source keeps reading Rust from ever being egress (design rule 14)."""
    assert PLUGIN is not None
    m = PLUGIN.manifest
    assert "{workdir}" in m.build and m.product
    assert {"--offline", "--locked"} <= set(m.build)
    assert "vendored-sources" in (m.root / ".cargo" / "config.toml").read_text(encoding="utf-8")


@needs_plugin
def test_the_judgements_are_declared_and_not_defaulted():
    """A Rust future is inert until polled, which is Python's answer; rustc refuses a real
    redefinition, so that detector is silent by declaration (rule 98)."""
    from dunneflow.detectors import load_rules

    rules = load_rules("rust")
    assert rules.unawaited_async == "inert"
    assert rules.redefinition == ""
    assert {"drop", "format!", "vec!"} <= set(rules.builtins)


# ------------------------------------------------------------ with cargo ------- #

@needs_plugin
@needs_cargo
def test_the_second_implementations_agree_with_the_first(tmp_path):
    out = subprocess.run(  # noqa: S603
        ["cargo", "test", "--offline", "--locked", "--quiet", "--target-dir", str(tmp_path)],
        cwd=HERE, capture_output=True, text=True, timeout=600, check=False,
        env={k: v for k, v in os.environ.items() if k not in ("RUSTFLAGS", "CARGO_TARGET_DIR")},
    )
    assert out.returncode == 0, out.stdout[-3000:] + out.stderr[-3000:]


@pytest.fixture(scope="module")
def read(tmp_path_factory):
    """A small tree, read in one session through the host: CRLF and mixed bad bytes in
    one file, a parse error in another."""
    if PLUGIN is None or shutil.which("cargo") is None:
        pytest.skip("needs the Rust plugin and `cargo`")
    plugin = PLUGIN
    root = tmp_path_factory.mktemp("rusttree")
    (root / "main.rs").write_bytes(
        b"fn main() {}\r\n\r\n// \xe2\x82A \xff \xed\xa0\x80 \xf0\x9f\x98\n")
    (root / "broken.rs").write_bytes(b"fn main( {\n")
    (root / "src" / "net").mkdir(parents=True)
    (root / "src" / "net" / "mod.rs").write_bytes(b"pub fn run() {}\n")
    files = sorted(root.rglob("*.rs"))
    plugin.probe()
    plugin.open(root, files)
    try:
        facts = {ff.path: ff for ff in plugin.extract(files, root)}
        edges = list(plugin.edges())
    finally:
        plugin.close()
    return root, facts, edges


def test_the_handshake_agrees_with_the_manifest(read):
    """`open` succeeding is the proof: the handshake refuses the language on any
    disagreement about lang, version, protocol, schema or capability (rule 30)."""
    _, facts, _ = read
    assert facts


def test_a_crlf_file_with_bad_bytes_hashes_as_the_host_hashes_it(read):
    root, facts, _ = read
    ff = facts["main.rs"]
    assert ff.errors == []
    assert ff.content_hash == hash_source(
        (root / "main.rs").read_text(encoding="utf-8", errors="replace"))


def test_a_file_that_will_not_parse_is_facts_with_errors(read):
    _, facts, _ = read
    ff = facts["broken.rs"]
    assert ff.errors and ff.errors[0].startswith("1:")
    assert ff.content_hash, "a parse error is still a file whose bytes are known, so cached"


def test_paths_and_modules_are_spelled_as_every_reader_spells_them(read):
    _, facts, _ = read
    assert set(facts) == {"main.rs", "broken.rs", "src/net/mod.rs"}
    assert facts["src/net/mod.rs"].module == "src.net.mod"
    assert all(ff.lang == "rust" for ff in facts.values())
