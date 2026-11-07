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


# ------------------------------------------------------------- the facts ------ #

SNIPPETS = {
    "shop.go": '''package shop

import (
\t"database/sql"
\tstdos "os"
)

// Store keeps the orders.
type Store struct {
\tdb   *sql.DB // the handle
\tBase
}

// Save writes one order.
func (s *Store) Save(id string) error {
\t_, err := s.db.ExecContext(nil, "INSERT INTO orders VALUES (?)", id)
\treturn err
}

func (s Store) load() string { return stdos.Getenv("SHOP") }

func init() {}

func init() {}
''',
    "run.go": '''package main

import (
\t"fmt"
\t"net/http"
\t"os"
)

type Color string

const (
\tRed  Color = "red"
\tBlue Color = "blue"
)

const limit = 3

func main() {
\thandle := func(w http.ResponseWriter, r *http.Request) {
\t\tfmt.Println("handled")
\t}
\t_ = handle
\tgo func() {
\t\tos.Remove("/tmp/x")
\t}()
\tfor i := 0; i < limit; i++ {
\t\tresp, err := http.Get("https://example.com/items")
\t\tif err != nil {
\t\t\tpanic(err)
\t\t}
\t\t_ = resp
\t}
\tswitch os.Args[1] {
\tcase "a", "b":
\t\tfmt.Println("ab")
\tdefault:
\t}
\tselect {}
}
''',
    "serve.go": '''package main

import (
\t"net/http"

\t"github.com/spf13/cobra"
)

func items(w http.ResponseWriter, r *http.Request) {}

var serveCmd = &cobra.Command{
\tUse:   "serve [flags]",
\tShort: "run the server",
\tRunE: func(cmd *cobra.Command, args []string) error {
\t\tmux := http.NewServeMux()
\t\tmux.HandleFunc("GET /items", items)
\t\tmux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {})
\t\tmux.HandleFunc("/ready", func(w http.ResponseWriter, r *http.Request) {})
\t\tcache.Get("key", 1)
\t\treturn http.ListenAndServe(":8080", mux)
\t},
}
''',
    "dial.go": '''package dial

import (
	"net"
	"time"
)

func both(budget time.Duration) {
	net.DialTimeout("tcp", "h:1", budget)
	net.Dial("tcp", "h:2")
}
''',
    "lib.go": '''package lib

func main() {}

func stub()
''',
}


@pytest.fixture(scope="module")
def go_facts(tmp_path_factory):
    if PLUGIN is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    plugin = PLUGIN
    root = tmp_path_factory.mktemp("gofacts")
    paths = []
    for name, source in SNIPPETS.items():
        (root / name).write_text(source, encoding="utf-8")
        paths.append(root / name)
    plugin.probe()
    plugin.open(root, paths)
    try:
        return {ff.path: ff for ff in plugin.extract(paths, root)}
    finally:
        plugin.close()


def test_a_method_belongs_to_its_type_whether_its_receiver_is_a_pointer_or_not(go_facts):
    by = {r.name: r for r in go_facts["shop.go"].routines}
    assert by["Save"].qualname == "shop.Store.Save" and by["Save"].class_name == "Store"
    assert by["load"].qualname == "shop.Store.load" and by["load"].is_method
    assert by["Save"].visibility == "public" and by["load"].visibility == "private"
    assert by["Save"].docstring == "Save writes one order."
    assert [(p.name, p.type) for p in by["Save"].params] == [("id", "string")]


def test_two_init_functions_are_two_routines_with_two_identities(go_facts):
    """Go allows any number of `init` per file; the ordinal keeps them apart (rule 106)."""
    from dunneflow.schema import definition_id

    inits = [r for r in go_facts["shop.go"].routines if r.name == "init"]
    assert [r.id for r in inits] == [definition_id("shop.go", "shop.init", 1),
                                     definition_id("shop.go", "shop.init", 2)]


def test_a_boundary_is_matched_on_the_spelling_the_file_writes(go_facts):
    """Rule 4: `stdos.Getenv` is not `os.Getenv`, and the residue is stated in go.yaml."""
    hits = {(b.kind, b.evidence, b.target) for b in go_facts["shop.go"].boundaries}
    assert ("DATABASE", "s.db.ExecContext", "nil") in hits
    assert not any(b.evidence == "stdos.Getenv" for b in go_facts["shop.go"].boundaries)
    calls = {c.callee_expr: c for c in go_facts["shop.go"].calls}
    assert calls["s.db.ExecContext"].at_boundary, "rule 2: a boundary call is never an edge"


def test_an_import_alias_is_recorded_only_where_it_is_written(go_facts):
    imports = {(i.module, i.alias) for i in go_facts["shop.go"].imports}
    assert imports == {("database/sql", ""), ("os", "stdos")}


def test_a_struct_is_a_class_and_its_embedded_type_is_its_base(go_facts):
    store = next(s for s in go_facts["shop.go"].structures if s.name == "Store")
    assert store.kind == "CLASS" and store.bases == ["Base"]
    assert [(f.name, f.type) for f in store.fields] == [("db", "*sql.DB"), ("Base", "Base")]
    assert store.docstring == "Store keeps the orders."


def test_a_named_type_with_constants_of_it_is_an_enum(go_facts):
    """Rule 19: a set of named values of one type is an enumeration."""
    color = next(s for s in go_facts["run.go"].structures if s.name == "Color")
    assert color.kind == "ENUM"
    assert [(f.name, f.default) for f in color.fields] == [("Red", '"red"'), ("Blue", '"blue"')]


def test_a_func_literal_bound_to_a_name_is_a_routine_and_an_anonymous_one_is_not(go_facts):
    names = {r.qualname: r for r in go_facts["run.go"].routines}
    assert "run.main.handle" in names and names["run.main.handle"].is_nested
    # `go func() { os.Remove(...) }()` is anonymous: what it does belongs to `main`.
    remove = next(c for c in go_facts["run.go"].calls if c.callee_expr == "os.Remove")
    assert remove.caller_id == names["run.main"].id


def test_main_is_a_way_in_only_in_package_main(go_facts):
    eps = [e for e in go_facts["run.go"].entrypoints]
    assert [(e.kind, e.name) for e in eps] == [("MAIN", "main")]
    assert go_facts["lib.go"].entrypoints == [], "a `main` in package lib is ordinary"


def test_a_function_with_no_body_is_not_a_routine(go_facts):
    assert [r.name for r in go_facts["lib.go"].routines] == ["main"]


def test_control_is_recorded_as_spans_in_go_s_own_words(go_facts):
    points = [(p.kind, p.word, p.header, p.exits) for p in go_facts["run.go"].control]
    assert ("LOOP", "for", "i := 0; i < limit; i++", "") in points
    assert ("GUARD", "if", "err != nil", "panic") in points
    assert ("DECISION", "switch", "os.Args[1]", "") in points
    assert ("DECISION", "select", "", "") in points
    arms = {(a.kind, a.header) for a in go_facts["run.go"].control_arms}
    assert ("case", '"a", "b"') in arms and ("default", "") in arms


def test_a_network_call_carries_its_verb_and_destination(go_facts):
    (call,) = go_facts["run.go"].network
    assert (call.expr, call.protocol, call.verb, call.destination) == (
        "http.Get", "HTTP", "GET", "https://example.com/items")
    assert not call.is_async, "a Go call blocks its goroutine; go.yaml says why"


def test_a_call_named_for_its_timeout_sets_one(go_facts):
    """`network.timed`: `net.DialTimeout` was a NO_TIMEOUT on the one call that cannot be
    made without one. `net.Dial` sets none, and says so."""
    got = [(n.expr, n.timeout) for n in go_facts["dial.go"].network]
    assert got == [("net.DialTimeout", "set"), ("net.Dial", "")], got


def test_strings_are_reported_for_the_host_to_judge(go_facts):
    texts = {lit.text for lit in go_facts["run.go"].literals}
    assert {"handled", "/tmp/x", "https://example.com/items"} <= texts
    shop = {lit.text for lit in go_facts["shop.go"].literals}
    assert "INSERT INTO orders VALUES (?)" in shop
    assert "database/sql" not in shop, "an import path is not a string the program uses"


def test_every_comment_lands_on_something(go_facts):
    """Rule 18, and rule 40: a field's trailing comment is the field's, never twice."""
    ff = go_facts["shop.go"]
    every = [c.text for r in ff.routines for c in r.comments]
    every += [c.text for c in (ff.module_scope.comments if ff.module_scope else [])]
    assert "the handle" not in every
    store = next(s for s in ff.structures if s.name == "Store")
    assert store.fields[0].comment == "the handle"


def test_a_handler_registered_by_a_call_is_a_way_in(go_facts):
    eps = {e.name: e for e in go_facts["serve.go"].entrypoints}
    assert {"GET /items", "/health", "/ready", "serve"} <= set(eps)
    assert "key" not in eps, "a string that is not a route registers nothing (rule 5)"
    by_id = {r.id: r for r in go_facts["serve.go"].routines}
    assert by_id[eps["GET /items"].routine_id].qualname == "serve.items"


def test_an_inline_handler_is_a_routine_named_by_the_word_that_registered_it(go_facts):
    """Rule 30: the word written there, and an ordinal so two are not one name twice."""
    eps = {e.name: e for e in go_facts["serve.go"].entrypoints}
    by_id = {r.id: r for r in go_facts["serve.go"].routines}
    assert by_id[eps["serve"].routine_id].qualname == "serve.RunE"
    assert by_id[eps["/health"].routine_id].qualname == "serve.RunE.HandleFunc"
    assert by_id[eps["/ready"].routine_id].qualname == "serve.RunE.HandleFunc#2"
    assert all(e.kind == "HTTP_ROUTE" for n, e in eps.items() if n.startswith(("/", "GET")))
    assert eps["serve"].kind == "CLI"


def test_a_way_in_has_no_position_in_its_identity(go_facts):
    """`schema.make_id`: a line number would retire the id whenever anything moved."""
    from dunneflow.schema import entrypoint_id

    eps = {e.name: e for e in go_facts["serve.go"].entrypoints}
    assert eps["/health"].id == entrypoint_id("serve.go", "http_route", "/health")


def test_a_function_with_no_results_declares_that_it_returns_nothing(go_facts):
    """Rule 98: `None` is *undeclared*, which no Go function is. Read as `None`,
    `MISSING_RETURN_TYPE` counted 183 of rain's 715 routines, and every one returned
    nothing by declaration."""
    by = {r.name: r for r in go_facts["shop.go"].routines}
    assert by["init"].returns == ""
    assert by["Save"].returns == "error"


# ------------------------------------------------------------- the edges ------ #

MODULE = {
    "go.mod": "module example.com/app\n\ngo 1.22\n",
    "main.go": '''package main

import (
\t"fmt"

\t"example.com/app/store"
\t"github.com/acme/thing"
)

type Base struct{}

func (Base) Hello() {}

type Child struct{ Base }

type Speaker interface{ Speak() }

type Dog struct{}

func (Dog) Speak() {}

type Cat struct{}

func (Cat) Speak() {}

func countdown(n int) {
\tif n > 0 {
\t\tcountdown(n - 1)
\t}
}

func main() {
\thelper()
\tstore.Save("x")
\tvar c Child
\tc.Hello()
\tvar s Speaker = Dog{}
\ts.Speak()
\tlater := func() { helper() }
\tlater()
\tcountdown(3)
\tplatform()
\tfmt.Println(len("x"))
\tthing.Do()
}
''',
    "helper.go": "package main\n\nfunc helper() {}\n",
    "platform_linux.go": "package main\n\nfunc platform() {}\n",
    "platform_darwin.go": "package main\n\nfunc platform() {}\n",
    "platform_windows.go": "package main\n\nfunc platform() {}\n",
    "store/store.go": "package store\n\n// Save keeps one.\nfunc Save(id string) {}\n",
}


@pytest.fixture(scope="module")
def go_edges(tmp_path_factory):
    if PLUGIN is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    plugin = PLUGIN
    root = tmp_path_factory.mktemp("gomod")
    for name, source in MODULE.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(source, encoding="utf-8")
    paths = sorted(root.rglob("*.go"))

    def once():
        plugin.probe()
        plugin.open(root, paths)
        try:
            facts = {ff.path: ff for ff in plugin.extract(paths, root)}
            edges = list(plugin.edges())
            return facts, edges, plugin.edges_outside, plugin.edges_unknown
        finally:
            plugin.close()

    first = once()
    return first, once()


def _by_callee(go_edges):
    (facts, edges, _, _), _ = go_edges
    site = {c.site_id: c for ff in facts.values() for c in ff.calls}
    return {site[e.site_id].callee_expr: e for e in edges}


def test_a_call_is_supplied_as_a_location_the_host_turns_into_an_id(go_edges):
    by = _by_callee(go_edges)
    assert (by["helper"].file, by["helper"].line, by["helper"].name) == ("helper.go", 3, "helper")
    assert (by["store.Save"].file, by["store.Save"].line) == ("store/store.go", 4), (
        "the line is the function's own, never its doc comment's")


def test_a_promoted_method_and_a_named_closure_resolve(go_edges):
    by = _by_callee(go_edges)
    # Through a variable: `Child{}.Hello()` has a literal at its root, so clause 3 records
    # no call there and there is no site to resolve.
    assert by["c.Hello"].name == "Hello" and by["c.Hello"].line == 12
    assert by["later"].name == "later", "a function literal bound to a name is a routine"


def test_a_routine_that_calls_itself_is_an_edge_to_itself(go_edges):
    """BACKLOG 29's shape, in Go."""
    by = _by_callee(go_edges)
    assert (by["countdown"].name, by["countdown"].line) == ("countdown", 26)


def test_an_interface_call_is_ambiguous_and_never_guessed(go_edges):
    """Rule 1: two types implement `Speaker`, and the edge names neither."""
    by = _by_callee(go_edges)
    assert by["s.Speak"].file == "" and by["s.Speak"].candidates == 2
    # BACKLOG 43: and it names both bodies, so every walk can follow them as *may run*.
    assert by["s.Speak"].reason == "dynamic"
    assert sorted(a.name for a in by["s.Speak"].answers) == ["Speak", "Speak"]
    assert len({(a.file, a.line) for a in by["s.Speak"].answers}) == 2


def test_a_function_defined_per_platform_is_drawn_to_the_reference_target(go_edges):
    """Tom's decision of 2026-11-01: linux/amd64's definition, with the variants counted."""
    by = _by_callee(go_edges)
    assert by["platform"].file == "platform_linux.go"
    assert "3 platform variants" in by["platform"].how


def test_the_standard_library_a_dependency_and_a_builtin_are_outside(go_edges):
    (_, _, outside, _), _ = go_edges
    by = _by_callee(go_edges)
    # BACKLOG 36: each is sent, with no target, saying where it stops and why.
    assert by["len"].file == "" and (by["len"].reason, by["len"].frontier) == ("outside", "len")
    assert by["thing.Do"].file == "" and by["thing.Do"].reason == "outside"
    assert by["thing.Do"].frontier.endswith(".Do")
    assert outside >= 2
    # `fmt.Println` is a STDIO boundary, so it never reaches the edge pass (rule 2).
    assert "fmt.Println" not in by


def test_the_edges_are_the_same_answer_twice(go_edges):
    """Rule 66: the order and the content are the reader's own, never a map iteration's."""
    (_, edges1, o1, u1), (_, edges2, o2, u2) = go_edges
    assert edges1 == edges2 and (o1, u1) == (o2, u2)


def test_a_cobra_tree_is_drawn_from_add_command_across_the_files_of_a_package(tmp_path):
    """BACKLOG 33: `AddCommand` hangs a command under a group, and the group and the command
    are usually in sibling files of one package, which no import connects."""
    if PLUGIN is None or shutil.which("go") is None:
        pytest.skip("needs the Go plugin and `go`")
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.resolve.cli import command_tree, resolve_cli
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    root = tmp_path / "t"
    (root / "cmd").mkdir(parents=True)
    (root / "go.mod").write_text("module example.com/t\n\ngo 1.22\n", encoding="utf-8")
    (root / "cmd" / "root.go").write_text(
        'package cmd\n\nimport "github.com/spf13/cobra"\n\n'
        'var Root = &cobra.Command{Use: "t"}\n\n'
        'var cc = &cobra.Command{Use: "cc"}\n\n'
        'func init() {\n\tRoot.AddCommand(cc)\n}\n', encoding="utf-8")
    (root / "cmd" / "list.go").write_text(
        'package cmd\n\nimport "github.com/spf13/cobra"\n\n'
        'var ccList = &cobra.Command{Use: "list", Run: func(c *cobra.Command, a []string) {}}\n\n'
        'func init() {\n\tcc.AddCommand(ccList)\n}\n', encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    stats = resolve_cli(store)
    assert (stats.mounts_resolved, stats.mounts_total) == (2, 2)
    (app,) = store.query("SELECT id FROM cli_apps WHERE var = 'Root'")
    tree = command_tree(store, app["id"])
    store.close()
    assert tree is not None
    (cc,) = tree["children"]
    (lst,) = cc["children"]
    assert [c["name"] for c in lst["commands"]] == ["list"]
