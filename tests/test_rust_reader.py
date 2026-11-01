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


# ------------------------------------------------------------- the facts ------ #

SNIPPETS = {
    "lib.rs": '''//! The store.

use std::fs::{self, File as F};
use crate::net::*;

/// Keeps the orders.
pub struct Store {
    /// the handle
    pub path: String,
}

pub enum Color { Red = 1, Blue }

pub trait Saver {
    fn save(&self) -> bool { self.flush() }
    fn flush(&self) -> bool;
}

impl Store {
    /// Opens one.
    pub fn open(path: &str) -> Self {
        let _ = fs::read_to_string(path); // read it
        Store { path: path.to_owned() }
    }

    fn helper(&self) {}
}

impl std::fmt::Display for Store {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { write!(f, "{}", self.path) }
}

impl std::fmt::Debug for Store {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result { Ok(()) }
}

mod inner {
    pub fn deep() {
        fn nested() {}
        nested();
    }
}

#[tauri::command]
async fn fetch(url: String) {
    reqwest::get(&url);
    let kept = reqwest::get(&url);
    kept.await;
}

fn dispatch(x: Option<u8>) -> u8 {
    with_unlocked!(state, |s| { s.unlock(); helper_call(s) });
    match x {
        Some(1) => 1,
        Some(n) if n > 5 => n,
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn it_works() {}
}

#[test]
fn stray_test() {}
''',
    "build.rs": "fn main() { println!(\"cargo:rerun-if-changed=x\"); }\n",
    "bom.rs": "﻿#!/usr/bin/env run-cargo-script\nfn main() { std::env::var(\"HOME\"); }\n",
}


@pytest.fixture(scope="module")
def facts(tmp_path_factory):
    if PLUGIN is None or shutil.which("cargo") is None:
        pytest.skip("needs the Rust plugin and `cargo`")
    root = tmp_path_factory.mktemp("rustfacts")
    for name, text in SNIPPETS.items():
        (root / name).write_text(text, encoding="utf-8")
    files = sorted(root.rglob("*.rs"))
    PLUGIN.probe()
    PLUGIN.open(root, files)
    try:
        return {ff.path: ff for ff in PLUGIN.extract(files, root)}
    finally:
        PLUGIN.close()


def _routines(ff):
    return {r.qualname: r for r in ff.routines}


def test_a_trait_method_carries_its_trait_so_two_fmts_are_two_routines(facts):
    rs = _routines(facts["lib.rs"])
    assert "lib.Store.Display.fmt" in rs and "lib.Store.Debug.fmt" in rs
    assert "lib.Store.open" in rs and "lib.Store.helper" in rs
    assert rs["lib.Store.helper"].is_method and not rs["lib.Store.open"].is_method
    assert rs["lib.Store.open"].class_name == "Store"
    assert rs["lib.Saver.save"].class_name == "Saver", "a trait's default body is a routine"
    assert "lib.Saver.flush" not in rs, "a declaration with no body is not a routine"


def test_an_inline_module_and_a_nested_function_are_segments(facts):
    rs = _routines(facts["lib.rs"])
    assert "lib.inner.deep" in rs
    assert rs["lib.inner.deep.nested"].is_nested


def test_test_code_inside_a_file_is_left_out_and_counted(facts):
    ff = facts["lib.rs"]
    assert not any("it_works" in q or "stray_test" in q for q in _routines(ff))
    assert ff.tests_dropped == 2, "the `mod tests` and the stray `#[test]`, one each"


def test_every_routine_declares_what_it_returns(facts):
    """No `->` is `()`, never *undeclared* — Go's `MISSING_RETURN_TYPE` lesson (rule 98)."""
    rs = _routines(facts["lib.rs"])
    assert rs["lib.inner.deep"].returns == ""
    assert rs["lib.Store.open"].returns == "Self"
    assert rs["lib.Store.open"].docstring == "Opens one."
    assert rs["lib.Store.open"].visibility == "public"
    assert rs["lib.Store.helper"].visibility == "private"
    assert rs["lib.Store.Display.fmt"].visibility == "public", "a trait method is the trait's"
    assert rs["lib.fetch"].decorators == ["tauri.command"] and rs["lib.fetch"].is_async


def test_a_macro_s_arguments_are_code_and_its_name_keeps_its_bang(facts):
    calls = {c.callee_expr for c in facts["lib.rs"].calls}
    assert {"with_unlocked!", "s.unlock", "helper_call", "write!"} <= calls
    assert "Store" not in calls, "a struct literal runs no constructor and is not a call"


def test_a_discarded_future_is_unawaited_and_a_bound_one_is_not(facts):
    """`inert`: only a future whose value is thrown away never runs."""
    net = [(n.expr, n.line, n.awaited) for n in facts["lib.rs"].network]
    assert [a for _, _, a in net] == [False, True], net
    assert all(n.in_async_routine for n in facts["lib.rs"].network)


def test_structures_imports_and_comments(facts):
    ff = facts["lib.rs"]
    kinds = {s.name: s.kind.value for s in ff.structures}
    assert kinds == {"Store": "CLASS", "Color": "ENUM", "Saver": "INTERFACE"}
    color = next(s for s in ff.structures if s.name == "Color")
    assert [(f.name, f.default) for f in color.fields] == [("Red", "1"), ("Blue", None)]
    assert ff.doc == "The store."
    imports = {(i.module, i.name, i.alias) for i in ff.imports}
    assert ("std", "fs", "") in imports and ("std::fs", "File", "F") in imports
    assert ("crate", "net", "") in imports, "a glob imports its module"
    open_ = _routines(ff)["lib.Store.open"]
    assert [c.text for c in open_.comments] == ["read it"]


def test_a_match_is_a_decision_with_its_arms(facts):
    ff = facts["lib.rs"]
    m = next(p for p in ff.control if p.word == "match")
    arms = [(a.kind.value, a.header) for a in ff.control_arms if a.point_id == m.point_id]
    assert arms == [("case", "Some(1)"), ("case", "Some(n) if n > 5"), ("default", "")]


def test_a_build_script_is_not_a_way_into_the_program(facts):
    assert facts["build.rs"].entrypoints == []


def test_a_bom_and_a_shebang_move_no_offset(facts):
    """`syn` strips both and reports offsets into what is left; the reader strips them
    itself so a byte range is into the file the host read (rule 75's shape)."""
    ff = facts["bom.rs"]
    assert ff.errors == []
    [b] = ff.boundaries
    assert (b.kind.value, b.target, b.line) == ("ENV", "HOME", 2)
    assert [e.name for e in ff.entrypoints] == ["main"]


# -------------------------------------------------- through the whole walk ---- #

@needs_plugin
@needs_cargo
def test_a_declared_binary_runs_its_main_and_not_its_top_level(tmp_path):
    """`file_entry: main`. Bound to the module scope, DunneNote's three binaries reached
    nothing while their `main`s reached the program (`RuleSet.file_entry`)."""
    from dunneflow import walk
    from dunneflow.resolve import manifests
    from dunneflow.resolve.entrypoints import entrypoints_from_manifests
    from dunneflow.store import Store

    (tmp_path / "Cargo.toml").write_text('[package]\nname = "host"\n[[bin]]\nname = "host"\n')
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.rs").write_text("fn main() {\n    run();\n}\n\nfn run() {}\n")
    store = Store(tmp_path / "g.db")
    stats = walk.analyze_tree(tmp_path, store)
    _, found = manifests.find_package_root(tmp_path)
    readings = manifests.read_all(found, stats.manifests, relative_to=tmp_path)
    eps = entrypoints_from_manifests(readings, store)
    bound = store.query("SELECT qualname FROM routines WHERE id = ?", (eps[0].routine_id,))
    assert [r["qualname"] for r in bound] == ["src.main.main"]
    store.close()


@needs_plugin
@needs_cargo
def test_test_code_inside_files_reaches_the_report(tmp_path):
    from dunneflow import walk
    from dunneflow.store import Store

    (tmp_path / "lib.rs").write_text("pub fn a() {}\n#[cfg(test)]\nmod tests {}\n")
    store = Store(tmp_path / "g.db")
    stats = walk.analyze_tree(tmp_path, store)
    store.close()
    assert stats.tests_dropped == {"rust": 1}
    assert any(line.startswith("test code inside source files left out: 1 rust")
               for line in walk.walk_residue(stats)), walk.walk_residue(stats)


def test_file_entry_is_a_name_or_it_is_refused(tmp_path):
    from dunneflow.detectors import RulesMissing, _file_entry

    assert _file_entry("", "x", tmp_path) == "" and _file_entry("main", "x", tmp_path) == "main"
    with pytest.raises(RulesMissing):
        _file_entry("src/main.rs", "x", tmp_path)
