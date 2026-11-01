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


# ------------------------------------------------------------- the edges ------ #

WORKSPACE = {
    "Cargo.toml": '[workspace]\nmembers = ["core", "app"]\n',
    "core/Cargo.toml": '[package]\nname = "my-core"\n',
    "core/src/lib.rs": '''pub mod typed;
pub mod util;
pub use util::helper as reexported;

pub fn top() {
    util::helper();
    top();
}
''',
    "core/src/util.rs": '''pub fn helper() {
    plat();
}

#[cfg(target_os = "linux")]
fn plat() {}

#[cfg(target_os = "macos")]
fn plat() {}

pub struct S;

impl S {
    pub fn new() -> S {
        S
    }

    fn m(&self) {
        self.n();
    }

    fn n(&self) {}
}

pub trait T {
    fn t(&self);

    fn twice(&self) {
        self.t();
    }
}

impl T for S {
    fn t(&self) {}
}

pub struct S2;

impl T for S2 {
    fn t(&self) {}
}

pub fn dynamic(x: &dyn T) {
    x.t();
    x.len();
}

pub enum E {
    A(u8),
    B,
}

pub struct P(u8, u8);

pub fn build() {
    let _ = E::A(1);
    let _ = P(1, 2);
    let _ = Some(1);
}
''',
    "core/src/typed.rs": '''use crate::util::T;

pub struct Conn;

impl Conn {
    pub fn open() -> Result<Conn, ()> {
        Ok(Conn)
    }

    pub fn exec(&self) {}
}

pub struct Db {
    pub conn: Conn,
}

impl Db {
    pub fn conn(&self) -> &Conn {
        &self.conn
    }

    fn go(&self) {
        self.conn.exec();
        self.conn().exec();
    }
}

pub fn typed(db: &Db, tx: &rusqlite::Transaction, shared: std::sync::Arc<Db>, t: &dyn T) {
    db.conn.exec();
    tx.exec();
    shared.conn().exec();
    let c = Conn::open().unwrap();
    c.exec();
    let d = Conn::open()?;
    d.exec();
    t.t();
    t.missing();
    for row in rows {
        row.exec();
    }
}

fn secret() -> Option<u8> {
    None
}

pub fn shadow() {
    let Some(secret) = secret() else {
        return;
    };
    let _ = secret;
}

mod one {
    pub struct Tok;

    impl Tok {
        pub fn only_one(&self) {}
    }
}

mod two {
    pub struct Tok;

    impl Tok {
        pub fn new() -> Tok {
            Tok
        }
    }

    pub fn mk() {
        let t = Tok::new();
        t.only_one();
    }
}
''',
    "app/Cargo.toml": '[package]\nname = "app"\n',
    "app/src/main.rs": '''use my_core::util::S;

mod key;

fn main() {
    my_core::top();
    my_core::reexported();
    S::new();
    key::Store::open();
    let helper = |x: u8| x;
    helper(1);
    serde_json::to_string(&1);
    with!(my_core::top());
}
''',
    "app/src/key/mod.rs": '''#[cfg(target_os = "macos")]
mod mac;
#[cfg(target_os = "linux")]
mod lin;

#[cfg(target_os = "macos")]
pub use mac::MacStore as Store;
#[cfg(target_os = "linux")]
pub use lin::LinStore as Store;
''',
    "app/src/key/mac.rs": "pub struct MacStore;\n\nimpl MacStore {\n    pub fn open() {}\n}\n",
    "app/src/key/lin.rs": "pub struct LinStore;\n\nimpl LinStore {\n    pub fn open() {}\n}\n",
}


@pytest.fixture(scope="module")
def edges(tmp_path_factory):
    if PLUGIN is None or shutil.which("cargo") is None:
        pytest.skip("needs the Rust plugin and `cargo`")
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    root = tmp_path_factory.mktemp("rustws")
    for rel, text in WORKSPACE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    store = Store(tmp_path_factory.mktemp("db") / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)    # as `cmd_analyze` does: the walk stores, resolution follows
    rows = store.query(
        "SELECT r.qualname AS caller, c.callee_expr AS expr, t.qualname AS callee,"
        " c.ambiguous AS ambiguous, c.external AS external, c.constructs AS constructs"
        " FROM calls c JOIN routines r ON r.id = c.caller_id"
        " LEFT JOIN routines t ON t.id = c.callee_id")
    got = {(r["caller"].rsplit(".", 1)[-1], r["expr"]): (r["callee"], r["ambiguous"])
           for r in rows}
    for r in store.query("SELECT callee_expr, constructs FROM calls WHERE constructs != ''"):
        got[("constructs", r["callee_expr"])] = (r["constructs"], 0)
    store.close()
    return got


@pytest.mark.parametrize("caller, expr, callee", [
    ("top", "util.helper", "core.src.util.helper"),                 # a child module
    ("top", "top", "core.src.lib.top"),                             # recursion: an edge to itself
    ("main", "my_core.top", "core.src.lib.top"),                    # another workspace crate
    ("main", "my_core.reexported", "core.src.util.helper"),         # a renamed re-export
    ("main", "S.new", "core.src.util.S.new"),                       # a `use`d type's method
    ("main", "key.Store.open", "app.src.key.lin.LinStore.open"),    # the reference target's module
    ("helper", "plat", "core.src.util.plat"),                       # the reference target's fn
    ("m", "self.n", "core.src.util.S.n"),                           # `self` in an impl
])
def test_a_path_names_one_definition(edges, caller, expr, callee):
    assert edges[(caller, expr)][0] == callee, edges[(caller, expr)]


def test_a_call_inside_a_macro_argument_resolves(edges):
    """DunneNote's `with_unlocked!(…)` wraps the dispatch calls: they are still calls."""
    tops = [k for k in edges if k == ("main", "my_core.top")]
    assert tops and edges[tops[0]][0] == "core.src.lib.top"


def test_what_needs_a_type_is_never_guessed(edges):
    """Rule 1. A trait call with two impls, `self` in a trait's default body, and a method
    on a value of unknown type get no edge; the first two say how many could answer."""
    assert edges[("dynamic", "x.t")][0] is None
    assert edges[("dynamic", "x.len")][0] is None
    callee, ambiguous = edges[("twice", "self.t")]
    assert callee is None and ambiguous


def test_a_closure_shadows_a_function_of_the_same_name(edges):
    """`let helper = |x| x; helper(1)` calls the closure, never `util::helper`."""
    assert edges[("main", "helper")][0] is None


def test_a_dependency_s_path_goes_outside(edges):
    assert edges[("main", "serde_json.to_string")][0] is None


def test_a_variant_or_a_tuple_struct_builds_the_program_s_own_type(edges):
    """`E::A(1)` and `P(1, 2)` run no routine and build one of this program's types; they
    are constructions (`calls.constructs`), not calls to nothing. `Some(1)` is std's."""
    assert edges[("constructs", "E.A")][0] == "core.src.util.E"
    assert edges[("constructs", "P")][0] == "core.src.util.P"
    assert ("constructs", "Some") not in edges


def test_a_receiver_s_declared_type_names_its_method(edges):
    """`types.rs`: a field's type, a parameter's (through `&` and `Arc`), a constructor's
    declared return, `?` and `.unwrap()` on it, and a method's declared return."""
    for caller in ("go", "typed"):
        exec_calls = {k: v for k, v in edges.items() if k[0] == caller and k[1].endswith(".exec")}
        assert exec_calls, caller
    assert edges[("go", "self.conn.exec")][0] == "core.src.typed.Conn.exec"
    assert edges[("go", "self.conn.exec")][0] == "core.src.typed.Conn.exec"
    assert edges[("typed", "db.conn.exec")][0] == "core.src.typed.Conn.exec"
    assert edges[("typed", "shared.conn.exec")][0] == "core.src.typed.Conn.exec"
    assert edges[("typed", "c.exec")][0] == "core.src.typed.Conn.exec"
    assert edges[("typed", "d.exec")][0] == "core.src.typed.Conn.exec"


def test_what_the_declared_type_cannot_say_is_still_not_guessed(edges):
    """A dependency's type is outside; `dyn T` with two implementors is ambiguous; an
    iterator's item has no hint and `exec` is a name this program defines, so unknown."""
    assert edges[("typed", "tx.exec")][0] is None
    callee, ambiguous = edges[("typed", "t.t")]
    assert callee is None and ambiguous
    assert edges[("typed", "row.exec")][0] is None


def test_two_types_of_one_name_in_two_modules_are_two_types(edges):
    """DunneNote's search crate has a `struct Tok` and an `enum Tok`. Keyed on the name, the
    two pooled their methods, and `t.only_one()` on `two::Tok` resolved to `one::Tok`'s."""
    assert edges[("mk", "Tok.new")][0] == "core.src.typed.two.Tok.new"
    assert edges[("mk", "t.only_one")][0] is None


@pytest.fixture(scope="module")
def frontier_store(tmp_path_factory):
    if PLUGIN is None or shutil.which("cargo") is None:
        pytest.skip("needs the Rust plugin and `cargo`")
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    root = tmp_path_factory.mktemp("rustfront")
    for rel, text in WORKSPACE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    store = Store(tmp_path_factory.mktemp("db") / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    yield store
    store.close()


def test_every_call_with_no_edge_says_where_it_stops_and_why(frontier_store):
    """Schema 17: `calls.frontier` and `calls.reason`, from the reader that knows."""
    rows = {r["callee_expr"]: (r["frontier"], r["reason"]) for r in frontier_store.query(
        "SELECT callee_expr, frontier, reason FROM calls WHERE callee_id IS NULL"
        " AND constructs = '' AND at_boundary = 0")}
    assert rows["serde_json.to_string"] == ("serde_json::to_string", "outside")
    assert rows["tx.exec"] == ("rusqlite::Transaction::exec", "outside")
    assert rows["Some"] == ("std::Some", "outside")
    assert rows["with!"][1] == "outside"
    assert rows["row.exec"] == ("", "untyped")
    assert rows["helper"] == ("", "bound")
    assert rows["t.t"][1] == "dynamic"
    # Every call with no edge was said something about: Rust's reader leaves none unsaid.
    unsaid = frontier_store.query(
        "SELECT COUNT(*) AS n FROM calls c JOIN files f ON f.path = c.file"
        " WHERE f.lang = 'rust' AND c.callee_id IS NULL AND c.constructs = ''"
        " AND c.at_boundary = 0 AND c.reason = ''")
    assert unsaid[0]["n"] == 0


def test_touches_groups_the_frontier_by_crate_and_by_reason(frontier_store):
    from dunneflow.cli import frontier_lines

    [main] = frontier_store.query("SELECT id FROM routines WHERE qualname = 'app.src.main.main'")
    front = frontier_store.frontier_reached(main["id"])
    assert dict(front["outside"])["serde_json"] == 1
    assert dict(front["unresolved"])["bound"] == 1
    lines = frontier_lines(front)
    assert lines[0].startswith("leaves the program by ") and "serde_json 1" in lines[0]
    assert lines[1].startswith("no edge, and why: ")


def test_impact_names_the_calls_it_might_be_receiving(frontier_store):
    """`row.exec()` on an iterator's item could be `Conn::exec`: a reason to look, never a
    dependent (rule 1)."""
    assert dict(frontier_store.unresolved_named("exec")) == {"untyped": 1}
    assert frontier_store.unresolved_named("ex_c") == [], "`_` is not a wildcard here"


def test_a_let_shadows_only_the_calls_written_after_it(edges):
    """`let Some(secret) = secret() else { … }` calls the function `secret`; the name it
    binds exists only once the statement is done. Found in DunneNote's `host-http` `main`."""
    assert edges[("shadow", "secret")][0] == "core.src.typed.secret"
