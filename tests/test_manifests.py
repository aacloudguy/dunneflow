"""Manifest providers: what a program declares about itself, and what it declines.

Chunk 12. Six providers, one per filename, and the two halves they answer are kept apart
on purpose: **entrypoints and version are independent columns**. `go.mod` declares a module
path and no version of the program; `Package.swift` declares executables and no version at
all; a `package.json` may declare a version and no way in. A reader that flattened the two
would have to invent one of them for half the manifests there are.

Two things every provider is held to, and both are measured here rather than asserted:

**The evidence is the provider's own, verbatim.** `web/waysin.py:120` renders it unparsed,
so a `package.json` entry claiming to come from `pyproject.toml` would be a visible
falsehood in the one string a reader is shown as-is. That is the `declared` field's whole
argument (rule 30) one step earlier.

**A refusal is said, not silent** (design rule 1). `"scripts"` is a task runner and not a
way in, and the four JavaScript corpora here hold **31 of them and not one `bin`** --
DunneNote 4, DunneCorp 16, uigen 8, Society 3. A reader looking at a manifest that plainly
lists sixteen somethings, and a panel holding none of them, is owed the sentence.

*`build.gradle.kts` is proved by this file and by nothing else.* There is no such file
anywhere on the machine this was written on, so unlike its five siblings it has no
population. Recorded here rather than left to be assumed from the fact that it shipped
(rule 24).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dunneflow.resolve import manifests
from dunneflow.resolve.entrypoints import (
    binding_note,
    collisions,
    entrypoints_from_manifests,
    record_manifests,
)
from dunneflow.schema import EntrypointKind, TargetKind
from dunneflow.store import Store
from dunneflow.walk import WalkStats, analyze_tree, discover


def _tree(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def _read(root: Path) -> list[manifests.ManifestReading]:
    """Every manifest the walk reaches, read -- the whole of what `analyze` does."""
    stats = WalkStats()
    list(discover(root, stats=stats))
    _, found = manifests.find_package_root(root)
    return manifests.read_all(found, stats.manifests, relative_to=root)


def _one(readings: list[manifests.ManifestReading], filename: str
         ) -> manifests.ManifestReading:
    return next(r for r in readings if r.filename == filename)


# ------------------------------------------------------------------ registry --- #

def test_the_filenames_are_derived_from_the_providers():
    """A hand-kept second list drifts the moment somebody adds a provider (rule 51).

    `walk.discover` matches on this set to decide what to collect, so a seventh provider
    whose name nobody added would be read by `find_package_root` and never by the walk --
    a manifest found at the root and invisible one directory down.
    """
    assert {p.filename for p in manifests.PROVIDERS} == manifests.MANIFEST_FILES
    assert len(manifests.PROVIDERS) == 6
    assert "pyproject.toml" in manifests.MANIFEST_FILES
    assert "package.json" in manifests.MANIFEST_FILES


def test_two_manifests_at_one_level_are_both_read(tmp_path):
    """The ordinary polyglot repository, not an error.

    DunneNote carries a `package.json` beside a `Cargo.toml` and both declare `0.9.0`.
    Stopping at the first would make the answer depend on which filename sorts earlier.
    """
    root = _tree(tmp_path, {
        "package.json": '{"name": "both", "version": "2.0.0"}',
        "pyproject.toml": '[project]\nname = "both"\nversion = "2.0.0"\n',
    })
    _, found = manifests.find_package_root(root)
    assert [p.name for p in found] == ["package.json", "pyproject.toml"]
    assert len(manifests.read_all(found, [], relative_to=root)) == 2


def test_the_package_root_is_found_above_a_src_layout(tmp_path):
    """The walk-up, generalised past `pyproject.toml`.

    It asked for that one name until chunk 12, which is an answer of *no* for every
    TypeScript, Rust, Go and Swift tree there is.
    """
    root = _tree(tmp_path, {"package.json": '{"name": "up"}', "src/a.ts": "export {};"})
    found_root, found = manifests.find_package_root(root / "src")
    assert found_root == root
    assert [p.name for p in found] == ["package.json"]


def test_a_tree_declaring_nothing_is_its_own_root(tmp_path):
    """A bare directory of source is a real state and not an error."""
    root = _tree(tmp_path, {"a.py": "x = 1\n"})
    found_root, found = manifests.find_package_root(root)
    assert found_root == root and found == []


def test_a_manifest_that_cannot_be_parsed_says_so_rather_than_vanishing(tmp_path):
    """Read and unparseable is a different fact from not there, and only one of them
    is about this program (rule 20 -- a read may refuse, but it may never repair)."""
    root = _tree(tmp_path, {"package.json": "{not json at all"})
    got = _one(_read(root), "package.json")
    assert got.declares_nothing
    assert got.notes == ("could not be parsed as JSON",)


# ------------------------------------------------------------------ providers --- #

def test_pyproject_reads_both_script_tables_and_each_names_itself(tmp_path):
    """**The marker used to lie**, and in the one string a reader is shown verbatim.

    `[project.gui-scripts]` was merged into the same dictionary as `[project.scripts]` and
    every entry was labelled `[project.scripts]`. Each table names itself now.
    """
    root = _tree(tmp_path, {"pyproject.toml": (
        '[project]\nname = "p"\nversion = "1.2.3"\n'
        '[project.scripts]\ncli = "p.cli:main"\n'
        '[project.gui-scripts]\ngui = "p.gui:main"\n')})
    got = _one(_read(root), "pyproject.toml")
    assert got.version is not None and got.version.value == "1.2.3"
    by_name = {e.name: e for e in got.entries}
    assert by_name["cli"].evidence == "pyproject.toml [project.scripts] cli = p.cli:main"
    assert by_name["gui"].evidence == (
        "pyproject.toml [project.gui-scripts] gui = p.gui:main")
    assert all(e.target_kind is TargetKind.MODULE_ATTR for e in got.entries)


def test_a_dynamic_version_is_a_declared_absence_and_earns_a_sentence(tmp_path):
    """Society's own case, and the reason it is not silent.

    `dynamic = ["version"]` says the version is computed at build time, by a tool this
    program will never run. Falling through to the directory-name guess is the right
    *answer* and the wrong *silence*: the reader then sees an INFERRED version with no
    hint that the program did state something about the question (design rule 21).
    """
    root = _tree(tmp_path, {
        "pyproject.toml": '[project]\nname = "p"\ndynamic = ["version"]\n'})
    got = _one(_read(root), "pyproject.toml")
    assert got.version is None
    assert any("dynamic" in n for n in got.notes)


def test_package_json_reads_bin_and_refuses_scripts(tmp_path):
    """`bin` is the contract with whoever installs the program; `scripts` is a label.

    Admitting `scripts` would put sixteen build commands in the ways-in panel beside real
    ones (rule 30). Measured across the corpora: 31 `scripts` entries, no `bin` at all.
    """
    root = _tree(tmp_path, {"package.json": (
        '{"name": "t", "version": "3.0.0", "bin": {"tcli": "./bin/t.js"},'
        ' "scripts": {"build": "x", "test": "y"}}')})
    got = _one(_read(root), "package.json")
    assert got.version is not None and got.version.value == "3.0.0"
    assert [(e.name, e.kind, e.target) for e in got.entries] == [
        ("tcli", EntrypointKind.CLI, "./bin/t.js")]
    assert got.entries[0].evidence == 'package.json "bin" tcli = ./bin/t.js'
    assert any('refused 2 "scripts"' in n for n in got.notes)


def test_a_string_bin_is_named_after_the_package(tmp_path):
    """npm's other spelling of one contract."""
    root = _tree(tmp_path, {"package.json": '{"name": "solo", "bin": "./cli.js"}'})
    got = _one(_read(root), "package.json")
    assert [(e.name, e.target) for e in got.entries] == [("solo", "./cli.js")]


def test_main_is_a_library_way_in(tmp_path):
    """`main` says how another program reaches into this one, which is a way in even
    though nobody types it. DunneNote's `packages/api-types` is the real case."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "lib", "main": "./src/index.ts"}'})
    got = _one(_read(root), "package.json")
    assert [(e.name, e.kind) for e in got.entries] == [("lib", EntrypointKind.LIBRARY)]


def test_a_conditional_exports_map_is_one_declaration_and_not_nineteen(tmp_path):
    """uigen's generated Prisma client, exactly.

    Nineteen subpaths across six runtime conditions is **one** package declaring one entry
    point in many dialects. Picking one condition would be this tool choosing a module
    system on the reader's behalf, and admitting all of them would bury the panel (rule 1).
    """
    root = _tree(tmp_path, {"package.json": (
        '{"name": "cond", "exports": {'
        '".": {"require": "./i.js", "import": "./i.mjs"},'
        '"./edge": "./edge.js"}}')})
    got = _one(_read(root), "package.json")
    assert got.entries == ()
    assert any('"exports" names more than one target' in n for n in got.notes)


def test_a_single_string_export_is_read(tmp_path):
    root = _tree(tmp_path, {"package.json": '{"name": "e", "exports": "./i.js"}'})
    got = _one(_read(root), "package.json")
    assert [(e.name, e.target) for e in got.entries] == [("e", "./i.js")]
    assert got.entries[0].evidence == 'package.json "exports" e = ./i.js'


def test_cargo_reads_an_explicit_bin(tmp_path):
    root = _tree(tmp_path, {"Cargo.toml": (
        '[package]\nname = "c"\nversion = "0.4.0"\n'
        '[[bin]]\nname = "chost"\npath = "src/main.rs"\n')})
    got = _one(_read(root), "Cargo.toml")
    assert got.version is not None and got.version.value == "0.4.0"
    assert [(e.name, e.target) for e in got.entries] == [("chost", "src/main.rs")]
    assert got.entries[0].evidence == 'Cargo.toml [[bin]] name = "chost"'


def test_cargo_reads_the_main_rs_convention_off_the_disk(tmp_path):
    """Cargo honours `src/main.rs` with no `[[bin]]` at all -- DunneNote's Tauri host.

    Asked of the **disk**, because a convention that names a file is only a way in when
    the file is there.
    """
    root = _tree(tmp_path, {"Cargo.toml": '[package]\nname = "conv"\n',
                            "src/main.rs": "fn main() {}\n"})
    got = _one(_read(root), "Cargo.toml")
    assert [(e.name, e.target) for e in got.entries] == [("conv", "src/main.rs")]
    assert "convention" in got.entries[0].evidence


def test_cargo_does_not_add_a_convention_beside_a_declared_bin(tmp_path):
    """A crate that lists its binaries has said what they are, and adding an unnamed
    extra from a file on disk would be this tool disagreeing with the manifest."""
    root = _tree(tmp_path, {
        "Cargo.toml": '[package]\nname = "c"\n[[bin]]\nname = "only"\n',
        "src/main.rs": "fn main() {}\n"})
    got = _one(_read(root), "Cargo.toml")
    assert [e.name for e in got.entries] == ["only"]


def test_a_cargo_workspace_declares_a_version_and_no_crate(tmp_path):
    """DunneNote's root. Reading only `[package]` would report that the tree states no
    version while a file in it plainly does."""
    root = _tree(tmp_path, {"Cargo.toml": (
        '[workspace]\nmembers = ["a"]\n[workspace.package]\nversion = "0.9.0"\n')})
    got = _one(_read(root), "Cargo.toml")
    assert got.version is not None and got.version.value == "0.9.0"
    assert any("workspace's" in n for n in got.notes)


def test_an_inherited_version_is_named_and_not_read(tmp_path):
    """`version.workspace = true` is a real declaration and not a version. Resolving it
    needs workspace membership, which this tool does not model -- so it says so."""
    root = _tree(tmp_path, {
        "Cargo.toml": '[package]\nname = "m"\nversion.workspace = true\n'})
    got = _one(_read(root), "Cargo.toml")
    assert got.version is None
    assert any("inherited from the workspace" in n for n in got.notes)


def test_go_mod_declares_a_module_and_no_version(tmp_path):
    """**The whole of this provider's precision.**

    `go 1.25.6` is a language and toolchain floor -- a number certainly in the file and
    certainly not the answer. Reporting it would be `_from_dunder`'s refusal in reverse.
    """
    root = _tree(tmp_path, {
        "go.mod": "module github.com/steveyegge/beads\n\ngo 1.25.6\n"})
    got = _one(_read(root), "go.mod")
    assert got.name == "github.com/steveyegge/beads"
    assert got.version is None
    assert got.entries == ()
    assert any("toolchain floor" in n for n in got.notes)


def test_a_go_module_path_major_suffix_is_a_declared_version(tmp_path):
    """Go's only way to say *this is major version 2*, and a reader can open the file."""
    root = _tree(tmp_path, {"go.mod": "module github.com/x/y/v2\n\ngo 1.23\n"})
    got = _one(_read(root), "go.mod")
    assert got.version is not None and got.version.value == "2"
    assert any("major only" in n for n in got.notes)


def test_a_module_path_that_merely_contains_a_v_is_not_a_version(tmp_path):
    """`github.com/v2ray/core` is not version 2 of anything -- a marker must sit at an
    edge of the name (rule 5)."""
    root = _tree(tmp_path, {"go.mod": "module github.com/v2ray/core\n"})
    assert _one(_read(root), "go.mod").version is None


def test_swiftpm_reads_executable_products_and_not_libraries(tmp_path):
    """Both Swift packages available here declare `.library` and no executable, so the
    corpus proves this reads *products* rather than package names."""
    root = _tree(tmp_path, {"Package.swift": (
        '// swift-tools-version:5.10\nimport PackageDescription\n'
        'let package = Package(\n  name: "Pkg",\n  products: [\n'
        '    .library(name: "Lib", targets: ["Lib"]),\n'
        '    .executable(name: "tool", targets: ["Tool"]),\n  ])\n')})
    got = _one(_read(root), "Package.swift")
    assert got.name == "Pkg"
    assert [(e.name, e.target_kind) for e in got.entries] == [("tool", TargetKind.NONE)]
    assert got.version is None


def test_a_swift_package_of_libraries_says_so(tmp_path):
    root = _tree(tmp_path, {"Package.swift": (
        'let package = Package(name: "L", products: [.library(name: "L", targets: [])])\n')})
    got = _one(_read(root), "Package.swift")
    assert got.entries == ()
    assert any("library products and no executable" in n for n in got.notes)


def test_a_computed_swift_product_name_is_refused_and_counted(tmp_path):
    """`Package.swift` is a program, and this tool does not run one -- the same rule
    `_from_dunder` refuses a computed `__version__` under (`version.py:90`)."""
    root = _tree(tmp_path, {"Package.swift": (
        'let n = "x"\nlet package = Package(products: [.executable(name: n, targets: [])])\n')})
    got = _one(_read(root), "Package.swift")
    assert got.entries == ()
    assert any("not a string literal" in n for n in got.notes)


@pytest.mark.parametrize("line", ['mainClass.set("com.x.App")', 'mainClass = "com.x.App"'])
def test_gradle_reads_both_literal_spellings(tmp_path, line):
    """**Fixtures only.** There is no `build.gradle.kts` anywhere on this machine, so
    this provider has no population and the record says so (rule 24)."""
    root = _tree(tmp_path, {"build.gradle.kts": f"application {{\n  {line}\n}}\n"})
    got = _one(_read(root), "build.gradle.kts")
    assert [(e.name, e.kind, e.target_kind) for e in got.entries] == [
        ("com.x.App", EntrypointKind.MAIN, TargetKind.NONE)]
    assert got.version is None


def test_a_computed_gradle_main_class_is_refused(tmp_path):
    root = _tree(tmp_path, {
        "build.gradle.kts": 'application {\n  mainClass.set(theApp)\n}\n'})
    got = _one(_read(root), "build.gradle.kts")
    assert got.entries == ()
    assert any("not a string literal" in n for n in got.notes)


# ------------------------------------------------------------------ the walk --- #

def test_manifests_are_collected_by_the_code_walk_and_share_its_prunes(tmp_path):
    """Declarations follow the corpus, off the listing `os.walk` already took (rule 92).

    A second traversal would be a second answer to *which directories are the program's*,
    and the two would disagree the first time somebody extended one of them.
    """
    root = _tree(tmp_path, {
        "package.json": '{"name": "top"}',
        "packages/inner/package.json": '{"name": "inner"}',
        "node_modules/dep/package.json": '{"name": "dep"}',
        ".next/package.json": '{"type": "commonjs"}',
        "build/package.json": '{"name": "out"}',
        "a.py": "x = 1\n",
    })
    stats = WalkStats()
    list(discover(root, stats=stats))
    got = sorted(str(p.relative_to(root)) for p in stats.manifests)
    assert got == ["package.json", "packages/inner/package.json"]


def test_a_manifest_inside_a_map_is_not_this_programs(tmp_path):
    """A directory holding a graph is somebody else's program (rule 92)."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "mine"}',
        "output/other/package.json": '{"name": "theirs"}',
        "output/other/graph@2026-01-01T00-00-00Z.db": "",
    })
    stats = WalkStats()
    list(discover(root, stats=stats))
    assert [p.name for p in stats.manifests] == ["package.json"]


def test_the_root_manifest_is_read_once_when_it_is_also_in_the_tree(tmp_path):
    """It appears in both lists, and reading it twice would declare its ways in twice --
    which `INSERT OR REPLACE` would hide and the version list would not."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "one", "version": "1.0.0", "bin": "./c.js"}'})
    readings = _read(root)
    assert len(readings) == 1 and readings[0].at_root


# ------------------------------------------------------------------ identity --- #

def test_a_root_declaration_keeps_the_bare_name_as_its_id(tmp_path):
    """What holds the golden. Society's four script ids are `make_id("script", name)` and
    every stored map since v1 agrees; Society's `src/` holds no nested manifest at all."""
    from dunneflow.schema import make_id
    root = _tree(tmp_path, {
        "pyproject.toml": '[project]\nname = "p"\n[project.scripts]\nx = "p:main"\n',
        "p.py": "def main():\n    pass\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = entrypoints_from_manifests(_read(root), store)
    assert [e.id for e in eps] == [make_id("script", "x")]
    store.close()


def test_a_member_declaration_carries_its_manifest_into_its_id(tmp_path):
    """Two members may each declare `serve`, and `INSERT OR REPLACE` would keep whichever
    was walked last -- a way in disappearing with no error anywhere (rule 35's shape)."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "root"}',
        "a/package.json": '{"name": "a", "bin": {"serve": "./s.js"}}',
        "b/package.json": '{"name": "b", "bin": {"serve": "./s.js"}}',
        "x.py": "y = 1\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = entrypoints_from_manifests(_read(root), store)
    assert len({e.id for e in eps}) == 2
    assert [e.name for e in eps] == ["serve", "serve"]
    store.close()


def test_two_declarations_of_one_identity_are_refused_and_named(tmp_path):
    """The first is kept and the second is said. A refusal a reader cannot see is the
    failure rule 49 is about."""
    root = _tree(tmp_path, {
        "pyproject.toml": '[project]\nname = "p"\n[project.scripts]\nx = "p:main"\n',
        "package.json": '{"name": "x", "bin": "./x.js"}',
        "p.py": "def main():\n    pass\n"})
    readings = _read(root)
    said = collisions(readings)
    assert len(said) == 1 and "`x` is already declared by" in said[0]


# ------------------------------------------------------------------ binding --- #

def test_a_declared_way_in_is_bound_to_the_module_scope_of_its_file(tmp_path):
    """A `bin` names a file, and what runs when the command is typed is that file's top
    level -- the same answer `_target_routine` gives an application object."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "p", "bin": {"run": "./cli.py"}}',
        "cli.py": "import os\nos.getcwd()\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = entrypoints_from_manifests(_read(root), store)
    assert eps[0].routine_id is not None
    assert eps[0].declared and eps[0].target_kind is TargetKind.FILE
    store.close()


def test_a_target_is_resolved_against_its_own_manifest(tmp_path):
    """`./src/index.ts` in `packages/api-types/package.json` is a file beside that
    manifest; joined to the root it would name a different file or none at all."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "root"}',
        "pkg/package.json": '{"name": "inner", "bin": {"go": "./run.py"}}',
        "pkg/run.py": "import os\nos.getcwd()\n",
        "run.py": "z = 1\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = [e for e in entrypoints_from_manifests(_read(root), store) if e.name == "go"]
    bound = store.query("SELECT file FROM routines WHERE id = ?", (eps[0].routine_id,))
    assert bound[0]["file"] == "pkg/run.py"
    store.close()


def test_a_declaration_in_a_language_this_build_cannot_read_is_a_known_limit(tmp_path):
    """DunneNote's three Rust binaries. Every one is a real front door of that
    application, and reporting them as *leads nowhere* would be chunk 11's 83 false
    BROKENs one surface over."""
    root = _tree(tmp_path, {
        "Cargo.toml": '[package]\nname = "host"\n[[bin]]\nname = "host"\n',
        "src/main.rs": "fn main() {}\n",
        "a.py": "x = 1\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = entrypoints_from_manifests(_read(root), store)
    note = binding_note(store, eps[0].id)
    assert eps[0].routine_id is None
    assert note.known_limit and "claims `.rs`" in note.sentence
    store.close()


def test_a_barrel_of_re_exports_is_read_and_declares_no_routine(tmp_path):
    """**Found by running it**, not by a test: this chunk's first pass reported
    `@dunnenote/api-types` as a SUSPECT *way in leads nowhere*, over 289 lines of
    `export type { X } from './X'`. The file is in the map, it was read, and it declares
    nothing because there is nothing to declare (design rule 21 -- the answers are four,
    and only one of them is a fault).
    """
    root = _tree(tmp_path, {
        "package.json": '{"name": "b", "main": "./index.py"}',
        "index.py": "from a import thing\n",
        "a.py": "thing = 1\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = entrypoints_from_manifests(_read(root), store)
    note = binding_note(store, eps[0].id)
    assert note.known_limit
    assert "declares no routine" in note.sentence
    store.close()


def test_a_declaration_naming_a_file_the_walk_never_found_is_a_fault(tmp_path):
    """The one of the five answers that **is** suspicious: a declaration gone stale."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "g", "bin": {"ghost": "./missing.py"}}',
        "a.py": "x = 1\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    eps = entrypoints_from_manifests(_read(root), store)
    note = binding_note(store, eps[0].id)
    assert not note.known_limit
    assert "not a file this map holds" in note.sentence
    store.close()


# ------------------------------------------------------------------ recorded --- #

def test_what_was_read_is_a_table_a_query_can_return(tmp_path):
    """The claim on the cover -- *this program declares two versions* -- must be one a
    reader can put a query behind (design rule 13)."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "n", "version": "2.0.0", "scripts": {"b": "x"}}',
        "pyproject.toml": '[project]\nname = "n"\nversion = "1.0.0"\n',
        "a.py": "x = 1\n"})
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    readings = _read(root)
    record_manifests(readings, store)
    rows = {r["path"]: r for r in store.query(
        "SELECT path, provider, version, ways_in, at_root, note FROM manifests")}
    assert rows["package.json"]["version"] == "2.0.0"
    assert rows["pyproject.toml"]["version"] == "1.0.0"
    assert all(r["at_root"] == 1 for r in rows.values())
    assert 'refused 1 "scripts"' in rows["package.json"]["note"]
    store.close()


def test_two_declared_versions_are_both_kept_and_neither_is_picked(tmp_path):
    """The honest answer, and also a signal: a tree stating two may be two programs."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "n", "version": "2.0.0"}',
        "pyproject.toml": '[project]\nname = "n"\nversion = "1.0.0"\n'})
    readings = _read(root)
    assert manifests.disagree(readings)
    assert [r.version.value for r in manifests.versions(readings) if r.version] == [
        "1.0.0", "2.0.0"]


def test_a_members_version_is_not_the_programs(tmp_path):
    """Promoting one would make the program's version depend on how deep somebody
    looked. It is kept in the member's own reading and named in the report."""
    root = _tree(tmp_path, {
        "package.json": '{"name": "top", "version": "1.0.0"}',
        "pkg/package.json": '{"name": "inner", "version": "9.9.9"}',
        "a.py": "x = 1\n"})
    readings = _read(root)
    assert [r.version.value for r in manifests.versions(readings) if r.version] == ["1.0.0"]
    assert _nested(readings).version is not None


def _nested(readings: list[manifests.ManifestReading]) -> manifests.ManifestReading:
    return next(r for r in readings if not r.at_root)


# ------------------------------------------------------------------ residue --- #

def test_one_line_per_kind_of_refusal_and_never_one_per_manifest(tmp_path):
    """`walk_residue`'s rule, and it was paid for here before it was copied: DunneNote's
    twenty manifests produce twenty-one notes and **eleven are the same sentence**. A
    report nobody reads to the end is design rule 1's letter without its point."""
    files = {"package.json": '{"name": "r"}'}
    for i in range(4):
        files[f"m{i}/Cargo.toml"] = '[package]\nname = "m"\nversion.workspace = true\n'
    files["a.py"] = "x = 1\n"
    said = manifests.residue(_read(_tree(tmp_path, files)))
    inherited = [s for s in said if "inherited from the workspace" in s]
    assert len(inherited) == 1
    assert "and 3 others" in inherited[0]


def test_a_run_that_read_nothing_says_that_rather_than_going_quiet(tmp_path):
    """*nothing declares a way in* and *nothing was looked at* are different facts."""
    assert manifests.summary([]).startswith("manifests 0:")


# ------------------------------------------------------------------ guards --- #

def test_nothing_decides_declared_by_looking_at_a_sentence_any_more():
    """**Rule 30, kept by reading the source**, because a second site is written by
    somebody who never read this file (`test_source.py:171`'s precedent).

    Seven places tested `"[project.scripts]" in evidence` or `LIKE '%[project.scripts]%'`
    to mean *this was declared in packaging*: `flows.py`, four in `resolve/cli.py`, two in
    `render/markdown.py`. Two of them went further and **parsed** the sentence back with
    `rsplit("= ", 1)` to recover a target that `target_expr` had been carrying all along.
    A `package.json` `bin` matches none of it.

    **Read as syntax and not as text** -- rule 34, and it was paid for the first time this
    guard ran. A line scan flagged `resolve/manifests/__init__.py`, whose *docstring*
    quotes the defect it exists to explain; every comment written about this rule contains
    every word a scan would look for. So the question asked is whether the marker survives
    anywhere as a **live string constant**, with docstrings dropped -- prose cannot answer
    that one wrongly.

    The provider still *writes* the sentence, and must: `tests/test_waysin.py` pins it
    byte for byte, and what changed is who reads it, not who says it.
    """
    import ast
    src = Path(__file__).resolve().parents[1] / "src" / "dunneflow"
    offenders = []
    for path in src.rglob("*.py"):
        if path.parts[-2:] == ("manifests", "pyproject.py"):
            continue                     # the one place that still writes the sentence
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef))
            and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and "[project.scripts]" in node.value
                    and id(node) not in docstrings):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


def test_a_reader_may_never_declare_a_way_in_itself():
    """`declared` and `target_kind` are read out of a **manifest**, which happens in this
    process after extraction. A plugin has not seen one, so a plugin that sends either is
    refused rather than believed -- `Routine.lang`'s defence, two records over."""
    from dunneflow.ingest.codec import _HOST_OWNED
    from dunneflow.schema import Entrypoint
    assert _HOST_OWNED[Entrypoint] == frozenset({"declared", "target_kind"})


def test_the_generated_reader_types_offer_neither_field():
    """What host-ownership means on the far side of the pipe: the fields are not in the
    interface, so a reader cannot set one by accident."""
    facts = (Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "plugins"
             / "typescript" / "src" / "facts.ts").read_text(encoding="utf-8")
    block = facts[facts.index("export interface Entrypoint {"):]
    block = block[:block.index("}")]
    assert "declared" not in block and "target_kind" not in block
