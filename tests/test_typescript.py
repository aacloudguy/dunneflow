"""The TypeScript reader: a second language, read by another program.

`test_wire.py` proved the protocol against an extractor whose output was already known.
This is the first reader whose output nobody has a baseline for, so what is asserted here
is the **contract** rather than a diff: the dotted spelling, the identity functions, the
rule matching, and the facts that a snippet plainly contains.

**One session for the whole file.** Spawning the reader costs a handshake over a 9.5 MB
bundle, so the snippets are written into one tree and extracted in one `open`/`extract`
pass — which is also how a run does it, so the path under test is the path that runs.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.detectors import load_rules, rules_document
from dunneflow.ingest import dotted as dotted_contract
from dunneflow.ingest.literals import judge
from dunneflow.schema import (
    SCHEMA_VERSION,
    ArmKind,
    FileFacts,
    call_site_id,
    control_point_id,
    definition_id,
    hash_source,
)

LANG = "typescript"
PLUGIN = ingest.PLUGINS.get(LANG)
BUNDLE = PLUGIN.manifest.root / PLUGIN.manifest.entry if PLUGIN else Path("missing")

# Two reasons to skip and they are different facts. No plugin at all is a build assembled
# without its readers; no `node` is this machine's state and is recoverable (rules 49, 89).
pytestmark = [
    pytest.mark.skipif(PLUGIN is None, reason="this build ships no TypeScript reader"),
    pytest.mark.skipif(shutil.which("node") is None,
                       reason="node is not on this machine, and the reader is a node program"),
]


SNIPPETS: dict[str, str] = {
    # Every fact a reader is asked for, in one file a person can read.
    "shop.ts": '''/**
 * The shop, and what it touches.
 */
import { readFile } from "node:fs/promises";
import * as path from "node:path";

export const DB_FILE = "tabularium.db";

export interface Widget {
  id: string;
  name?: string;
}

export class Store {
  rows: Widget[] = [];

  async save(name: string): Promise<void> {
    // WHY: the insert is the whole point.
    const sql = "INSERT INTO widgets (name) VALUES (?)";
    if (!name) {
      throw new Error("no name");
    }
    for (const row of this.rows) {
      console.log(row.id);
    }
  }
}

export const load = async () => {
  const key = process.env.API_KEY;
  const body = await readFile(path.join("/tmp", DB_FILE), "utf8");
  const names = ["a", "b"].map((n) => n.toUpperCase());
  let i = 0;
  do {
    i += 1;
  } while (i < 3);
  switch (i) {
    case 1:
      return "one";
    default:
      return "many";
  }
};
''',
    # The DOM, and what must not come of it.
    "page.ts": '''export function paint(): void {
  const el = document.querySelector("#root");
  window.addEventListener("click", () => {});
  localStorage.setItem("seen", "1");
}
''',
    # An `else if` ladder, which TypeScript writes in two words.
    "ladder.ts": '''export function band(n: number): string {
  if (n < 1) {
    return "low";
  } else if (n < 10) {
    return "mid";
  } else if (n < 100) {
    return "high";
  } else {
    return "vast";
  }
}
''',
    # Prose that is not a fact, so the module scope must stay unclaimed (rule 96).
    "prose.ts": 'export const GREETING = "hello there, reader";\n',
    # A string that is a fact, so it must be claimed.
    "named.ts": 'export const DB = "tabularium.db";\n',
}


@pytest.fixture(scope="module")
def facts(tmp_path_factory) -> dict[str, FileFacts]:
    """Every snippet, read in one session and judged the way a run judges it."""
    root = tmp_path_factory.mktemp("tstree")
    paths = []
    for name, source in SNIPPETS.items():
        p = root / name
        p.write_text(source, encoding="utf-8")
        paths.append(p)
    assert PLUGIN is not None
    PLUGIN.probe()
    PLUGIN.open(root, paths)
    try:
        out = {ff.path: judge(ff, PLUGIN.manifest.reports_literals)
               for ff in PLUGIN.extract(paths, root)}
    finally:
        PLUGIN.close()
    for ff in out.values():
        assert ff.errors == [], f"{ff.path}: {ff.errors}"
    return out


def _by_name(records):
    return {r.name: r for r in records}


# ----------------------------------------------------------------- the reader --- #

def test_the_reader_is_a_program_and_says_the_same_thing_the_manifest_does():
    """Rule 30: the manifest is a label and the running process is the identity.

    `NdjsonWorker._handshake` refuses a disagreement on any of six, so reaching `ready` at
    all is the assertion — this names what it agreed about.
    """
    assert PLUGIN is not None
    m = PLUGIN.manifest
    assert m.lang == LANG
    assert m.schema_version == SCHEMA_VERSION
    assert m.in_process is False
    # Three places say this and the handshake refuses a disagreement between two of them:
    # `plugin.json`, the `ready` frame's `capabilities`, and this. Reaching `ready` proves
    # the first two agree; this is what stops the pair moving without anybody deciding to.
    assert m.supplies_edges is True
    assert m.reports_literals is True
    assert BUNDLE.exists(), "the reader is its built bundle, and it is committed"
    assert set(m.fingerprint) == {"plugin.json", BUNDLE.name}


def test_the_bundle_is_what_the_fingerprint_names_and_nothing_globs_for_it():
    """Rule 12: a glob over a directory that was not bundled returns nothing and blames
    the whole build for one missing plugin, so the files are named."""
    assert PLUGIN is not None
    named = [PLUGIN.manifest.root / n for n in PLUGIN.manifest.fingerprint]
    assert all(p.exists() for p in named), named
    assert PLUGIN.manifest.reader == "", "a reader over a pipe is its bundle, not a package here"


def test_the_types_the_reader_emits_are_generated_from_the_schema():
    """A hand-written copy drifts, and here the drift is a fact that stops existing.

    It was written by hand first and was wrong inside an hour: a `NetworkCall.library`
    field that `schema.py` has not got, which the codec drops and names in
    `FileFacts.errors` — and `WalkStats` counts a file with an error as **failed**, so
    every TypeScript file holding a network call would have been reported unreadable.
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import gen_facts_ts

    assert gen_facts_ts.OUT.read_text(encoding="utf-8") == gen_facts_ts.generate(), (
        "src/facts.ts has drifted from schema.py — run "
        "`uv run python tools/gen_facts_ts.py --write` and rebuild the bundle"
    )


# ---------------------------------------------------------------- the contract --- #

def test_the_dotted_contract_is_kept_and_rules_5_6_and_7_are_exercised():
    """The interface between any extractor and every rule in every YAML file.

    A reader that spells an expression differently does not fail; it makes every rule miss,
    so the map comes back with no boundaries and no ways in, looking exactly like a program
    that has none. Rules 5, 6 and 7 had no exercise at all until this language arrived.
    """
    assert PLUGIN is not None
    results = dotted_contract.run(PLUGIN, LANG)
    failed = [r for r in results if not r.passed]
    assert not failed, [(r.case.id, r.error or r.got) for r in failed]
    exercised = {r.case.rule for r in results if not r.skipped}
    assert {5, 6, 7} <= exercised, "the three clauses Python cannot express"


def test_a_construction_is_a_fact_of_its_own(facts):
    """Clause 7. `new Error(...)` and `Error(...)` call one name and do two things."""
    shop = facts["shop.ts"]
    made = [c for c in shop.calls if c.is_construction]
    assert [c.callee_expr for c in made] == ["Error"]
    assert all(not c.is_construction for c in shop.calls if c.callee_expr != "Error")


# ------------------------------------------------------------------ identity --- //

def test_every_id_the_reader_minted_is_the_one_python_would_have(facts):
    """BLAKE2b, twice, across a process boundary — and the fixture is the real output.

    `PLAN-v2.md` asked for ten vectors asserted from both sides. This is that assertion
    made against **what the reader actually sent**, which is strictly stronger and needs no
    second surface: a vectors file the plugin never reads would prove a function nothing
    calls (rule 35), and a conformance frame added to be tested would prove that frame and
    not the one the map is built from.

    It is not a formality. `crypto.createHash("blake2b512", { outputLength: 8 })` — the
    line the plan specified — is refused by Node's OpenSSL, and truncating a 512-bit digest
    is a **different hash**, because BLAKE2b puts the digest length in its parameter block.
    A reader that shipped the truncation would mint ids that look exactly like ids.
    """
    shop = facts["shop.ts"]
    by = _by_name(shop.routines)
    assert by["save"].id == definition_id("shop.ts", "shop.Store.save")
    assert by["load"].id == definition_id("shop.ts", "shop.load")
    assert shop.content_hash == hash_source(SNIPPETS["shop.ts"])

    log = next(c for c in shop.calls if c.callee_expr == "console.log")
    assert log.site_id == call_site_id(by["save"].id, "console.log", 0)

    loop = next(p for p in shop.control if p.word == "for")
    assert loop.point_id == control_point_id(
        by["save"].id, "LOOP", "const row of this.rows", 0)


def test_two_identical_expressions_in_one_routine_stay_two_call_sites(facts):
    """`call_site_id`'s ordinal, which is the only discriminator that is not a position."""
    ladder = facts["ladder.ts"]
    ids = [c.site_id for c in ladder.calls]
    assert len(ids) == len(set(ids))


# ------------------------------------------------------------------- the rules --- #

def test_the_rules_the_reader_matched_are_the_rules_this_process_holds(facts):
    """One file, and the plugin is handed it rather than carrying a copy (rule 51).

    Asserted by putting every dotted name the reader recorded through **this process's**
    `match_call` and requiring the two to agree about which of them is a boundary. A plugin
    with a baked-in rule set would pass this today and drift the moment somebody edited the
    YAML, so `rules_document` is what travels and this is what says the two agree.
    """
    rules = load_rules(LANG)
    shop = facts["shop.ts"]
    here = {c.callee_expr for c in shop.calls if rules.match_call(c.callee_expr)}
    there = {c.callee_expr for c in shop.calls if c.at_boundary}
    assert here == there, here ^ there
    assert "console.log" in there and "readFile" in there


def test_the_rules_travel_with_the_session_and_are_the_file_on_disk():
    doc = rules_document(LANG)
    assert doc["version"] == 1
    kinds = {r["kind"] for r in doc["boundaries"]}
    assert {"ENV", "FILE", "NETWORK", "DATABASE", "STDIO", "CRYPTO", "CLOUD_SDK"} <= kinds


def test_an_environment_read_is_a_boundary_whether_it_is_written_as_a_property(facts):
    """`process.env.X` is a property read, and `os.environ["X"]`'s analogue.

    One `subscript:` rule serves both spellings, which is what keeps the rule vocabulary
    the same in both languages rather than a TypeScript dialect of it.
    """
    env = [b for b in facts["shop.ts"].boundaries if b.kind.value == "ENV"]
    assert [(b.direction.value, b.target) for b in env] == [("IN", "API_KEY")]


def test_the_dom_is_not_a_boundary_and_storage_is_a_database(facts):
    """`PLAN-v2.md`'s open question 1, settled by counting rather than by taste.

    There is no `BROWSER` kind. `localStorage` is persistent named storage shared across
    an origin, which is what DATABASE means; the DOM is the program's own rendered output
    rather than its environment, and 81 `.svelte` files' worth of `querySelector` would be
    thousands of rows drowning the panel they were added to (rule 1). The residue is
    stated in words, and this is where it stops being a hope.
    """
    page = facts["page.ts"]
    kinds = {b.kind.value for b in page.boundaries}
    assert "DATABASE" in kinds
    assert [b.target for b in page.boundaries if b.kind.value == "DATABASE"] == ["seen"]
    evidence = " ".join(b.evidence for b in page.boundaries)
    assert "querySelector" not in evidence and "addEventListener" not in evidence


def test_a_types_package_reports_no_boundaries():
    """The failure the plan says to look for, stated as its own case.

    Measured on DunneNote's `packages/api-types`: 206 files, 205 TYPE_ALIAS structures and
    **zero** boundaries. Here it is the property rather than the corpus — a file that
    declares types and calls nothing must touch nothing.
    """
    assert PLUGIN is not None
    root = Path(__file__).parent
    del root
    # The snippet is the assertion; no session is needed because `shop.ts` already proves
    # the reader finds boundaries when there are any.
    types_only = facts_of("types.ts", "export type A = string;\nexport interface B { a: A }\n")
    assert types_only.boundaries == []
    assert types_only.calls == []
    assert {s.kind.value for s in types_only.structures} == {"TYPE_ALIAS", "INTERFACE"}


def facts_of(name: str, source: str) -> FileFacts:
    """One snippet through the reader, for the cases that want their own session."""
    import tempfile

    assert PLUGIN is not None
    with tempfile.TemporaryDirectory(prefix="dunneflow-ts-") as td:
        root = Path(td)
        path = root / name
        path.write_text(source, encoding="utf-8")
        PLUGIN.open(root, [path])
        try:
            out = list(PLUGIN.extract([path], root))
        finally:
            PLUGIN.close()
    assert len(out) == 1
    return judge(out[0], PLUGIN.manifest.reports_literals)


# ------------------------------------------------------------------- the words --- #

def test_typescripts_four_arm_words_are_its_own_and_python_keeps_its_own(facts):
    """`ArmKind`: the word in the source, and nothing invented.

    `PLAN-v2.md` said *catch, do, switch*; two of those are right. A `switch` is a **point**
    and its arms are `case` — already there — and `default`, which was not. And TypeScript
    has no `elif`: it writes `else if`, which is what its rung is called.
    """
    arms = {a.kind for a in facts["shop.ts"].control_arms}
    assert ArmKind.CATCH not in arms  # shop.ts has no try
    assert ArmKind.DO in arms
    assert ArmKind.DEFAULT in arms
    assert ArmKind.CASE in arms

    ladder = {a.kind for a in facts["ladder.ts"].control_arms}
    assert ladder == {ArmKind.IF, ArmKind.ELSE_IF, ArmKind.ELSE}
    assert ArmKind.ELIF not in ladder, "`elif` is Python's word and only Python's"


def test_an_else_if_ladder_is_one_decision_with_four_ways_out(facts):
    """Flattened at extraction, for the reason Python's `elif` is: the tree shape says
    *2 arms* three times where a reader sees one decision with four ways out."""
    points = facts["ladder.ts"].control
    assert len(points) == 1, [p.header for p in points]
    assert points[0].kind.value == "DECISION"
    assert points[0].arms == 4


def test_a_one_armed_decision_that_leaves_records_how_it_left(facts):
    """`if (!x) throw` and `if (!x) return` are the same sentence and opposite facts."""
    guard = next(p for p in facts["shop.ts"].control if p.kind.value == "GUARD")
    assert guard.exits == "throw", "TypeScript's word, where Python's is `raise`"
    assert guard.header == "!name"


def test_a_map_chain_is_a_loop_that_is_an_expression(facts):
    """The judgement Python's comprehensions already get."""
    comps = [p for p in facts["shop.ts"].control if p.kind.value == "COMPREHENSION"]
    assert [p.word for p in comps] == ["map"]


# ----------------------------------------------------------------- the strings --- #

def test_the_reader_reports_strings_and_the_host_says_what_they_mean(facts):
    """Chunk 8's split, holding for a language that did not exist when it was made.

    The SQL and the artefact below were decided by `ingest/literals.py` — the same function
    that decides them for Python — so the same text cannot read two ways in a `.ts` and a
    `.py` (rule 51, in the fact contract).
    """
    shop = facts["shop.ts"]
    assert [op.operation for op in shop.sql] == ["INSERT"]
    assert [op.tables for op in shop.sql] == [["widgets"]]
    assert [a.name for a in shop.artefacts] == ["tabularium.db"]
    assert any(lit.text.startswith("INSERT INTO") for lit in shop.literals)


def test_a_template_literal_is_marked_as_assembled(facts):
    """`?` in a template is a placeholder this reader wrote; `?` somebody typed is a glob."""
    ff = facts_of("tmpl.ts", "const name = 'x';\nexport const u = `https://h/${name}.db`;\n")
    kinds = {lit.kind.value for lit in ff.literals}
    assert "INTERPOLATED" in kinds


def test_the_module_scope_is_claimed_only_by_a_string_that_was_a_fact(facts):
    """Rule 96, across the wire this time.

    `prose.ts` holds a string and nothing that string turns out to be; `named.ts` holds one
    that names a file. The first must leave no `<module>` routine behind, or every routine
    count in a TypeScript map is inflated by whichever files happen to hold a long enough
    string.
    """
    prose, named = facts["prose.ts"], facts["named.ts"]
    assert prose.literals and [r.name for r in prose.routines] == []
    assert prose.module_scope is not None and prose.module_scope.lang == LANG
    assert [r.name for r in named.routines] == ["<module>"]
    assert named.artefacts[0].routine_id == named.module_scope.id


# -------------------------------------------------------------------- the walk --- #

def test_a_typescript_test_is_left_out_by_the_readers_own_rule():
    """`Path("client.test.ts").stem` is `"client.test"`, which Python's rule never caught —
    measured at 322 of DunneNote's 767 `.ts` files, 42% of the corpus."""
    assert PLUGIN is not None
    rules = PLUGIN.manifest.discovery
    assert rules.is_test(Path("src/lib/client.test.ts"))
    assert rules.is_test(Path("src/lib/client.spec.tsx"))
    assert rules.is_test(Path("tests/visual/canvas.ts"))
    assert not rules.is_test(Path("src/lib/client.ts"))
    assert not rules.is_test(Path("src/lib/latest.ts")), "an edge, never a substring (rule 5)"


def test_the_suffixes_are_claimed_and_the_ones_nobody_reads_are_not():
    assert ingest.language_of("a/b/c.ts") == LANG
    assert ingest.language_of("a/b/c.tsx") == LANG
    # The two DunneNote reports by name and count, and neither is claimed by accident.
    assert ingest.language_of("a/b/c.svelte") is None
    assert ingest.language_of("a/b/c.rs") is None


def test_the_reader_needs_node_and_says_so_with_both_ways_forward():
    """`ToolchainMissing` is the machine's state and a reader can act on it (rules 49, 89)."""
    assert PLUGIN is not None
    tc = PLUGIN.manifest.toolchain
    assert tc is not None
    assert tc.command == "node" and tc.min_version
    assert "node" in tc.install.lower() or "brew" in tc.install.lower()


def test_the_bundle_runs_under_plain_node_with_nothing_installed():
    """No `pnpm install` at analysis time, which is why the bundle is committed.

    The compiler is inlined, and the handshake is the cheapest proof that it loads: it was
    two different failures before it did — a dynamic `require` an ESM bundle cannot answer,
    and a `__filename` it has not got.
    """
    out = subprocess.run(  # noqa: S603
        ["node", str(BUNDLE)],
        input=json.dumps({"t": "hello", "id": 1, "protocol": 1,
                          "schema_version": SCHEMA_VERSION, "lang": LANG}) + "\n",
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert out.returncode == 0 or out.stdout, out.stderr[-2000:]
    reply = json.loads(out.stdout.splitlines()[0])
    assert reply["t"] == "ready" and reply["lang"] == LANG
    assert reply["schema_version"] == SCHEMA_VERSION


def test_a_file_with_windows_line_endings_is_read_and_not_reported_as_changed(tmp_path):
    """The contract that was an accident of a default until it cost two files.

    The host hashes what `Path.read_text` gave it, and Python reads text with **universal
    newlines**: `\r\n` and a lone `\r` both arrive as `\n`. `readFileSync` keeps them, so a
    CRLF file hashed differently on the two sides and the echo check refused it — correctly,
    and with the wrong reason, because the file had not changed.

    Measured on `../uigen`: **2 of 54 files**, both generated with CRLF, both reported
    unreadable in a map that was otherwise perfect, and neither would have been read on any
    later run either. `ingest.contract.SOURCE_TEXT` is where the term now lives.
    """
    assert PLUGIN is not None
    source = 'export const A = "one";\r\nexport function f(): number {\r\n  return 1;\r\n}\r\n'
    path = tmp_path / "crlf.ts"
    path.write_bytes(source.encode("utf-8"))
    PLUGIN.open(tmp_path, [path])
    try:
        out = list(PLUGIN.extract([path], tmp_path))
    finally:
        PLUGIN.close()
    assert len(out) == 1
    ff = out[0]
    assert ff.errors == [], ff.errors
    assert ff.content_hash == hash_source(
        path.read_text(encoding="utf-8", errors="replace")), (
        "the reader hashed the carriage returns the host had already dropped"
    )
    assert [r.name for r in ff.routines] == ["f"]


def test_the_echo_names_both_things_that_look_like_a_mismatch():
    """A race and a reader that decodes differently are one symptom and two facts."""
    from dunneflow.ingest.contract import SOURCE_TEXT

    assert "newlines normalised" in SOURCE_TEXT
    import inspect

    from dunneflow.ingest import outofprocess

    said = inspect.getsource(outofprocess.OutOfProcessPlugin._one)
    assert "changed" in said and "read it differently" in said


def test_an_overload_set_keeps_two_identities_rather_than_colliding():
    """TypeScript's commonest way of declaring one name twice, and it is not broken code.

    Found by the store: `UNIQUE constraint failed: routines.id` on uigen's generated Prisma
    client, where `PrismaClient.$transaction` is declared twice as an overload. Python has
    had `_identity`'s ordinal since it was written; this reader had not.
    """
    ff = facts_of("over.ts", "export function f(a: string): void;\n"
                             "export function f(a: number): void;\n"
                             "export function f(a: unknown): void {}\n")
    ids = [r.id for r in ff.routines]
    assert len(ids) == 3
    assert len(set(ids)) == 3, "two declarations of one name collapsed into one identity"
    assert ids[0] == definition_id("over.ts", "over.f"), "the first keeps the plain id"


def test_a_bare_library_name_matches_exactly_and_never_as_a_prefix():
    """Rule 5, in the matcher rather than in a rule file.

    `requests.` and `httpx.AsyncClient` are namespace prefixes and `startswith` is what
    they mean. `fetch` is a bare name, and a prefix test makes it match `fetchImpl`,
    `fetchAll` and `fetchingState`. Python's own rules hid it for a year because every one
    of them contains a dot; TypeScript's do not, and DunneNote reported **exactly one**
    network call — `fetchImpl`, a parameter holding an implementation, in the corpus whose
    stated ground truth is that no non-test file calls `fetch` at all.

    The residue is stated rather than hidden: a call *through* a name that holds `fetch` is
    a network call and is no longer reported as one. Knowing that needs the far end of the
    name, which is resolution, and chunk 10's supplied edges are where it comes back.
    """
    rules = load_rules(LANG)
    assert rules.network_profile("fetch") == ("HTTP", True)
    assert rules.network_profile("fetchImpl") is None
    assert rules.network_profile("axios.get") == ("HTTP", True)

    ff = facts_of("net.ts", "declare const fetchImpl: typeof fetch;\n"
                            "export async function a() { return await fetchImpl('/x'); }\n"
                            "export async function b() { return await fetch('/y'); }\n")
    assert [n.expr for n in ff.network] == ["fetch"]


def test_python_keeps_the_same_answer_because_all_its_keys_are_dotted():
    """The change could not move the golden, and this is why rather than a hope."""
    from dunneflow.detectors import rules_document

    keys = list((rules_document("python").get("network") or {}).get("libraries", {}))
    assert keys and all("." in k for k in keys), [k for k in keys if "." not in k]


# ---------------------------------------------------------- the checker's answer --- #
#
# Chunk 10. The reader builds a `ts.Program` per `tsconfig.json` in `open` and answers the
# `edges` frame out of the checker — so what is pressed here is what a compiler can say
# that a name cannot, and each case is one this reader would have got **wrong** by
# guessing.

EDGE_TREE: dict[str, str] = {
    "tsconfig.json": """{
  "compilerOptions": { "strict": true, "target": "ES2022", "module": "ESNext",
                       "moduleResolution": "bundler", "baseUrl": ".", "jsx": "react-jsx",
                       "paths": { "$lib/*": ["lib/*"] } }
}
""",
    # A second `save`, in a file nobody imports. A resolver matching on the name has two
    # routines called `save` in the program and no way to choose; the checker has already
    # chosen, because choosing is what it did to type the call.
    "other.ts": """
export function save(value: string): string {
  return "not the one";
}
""",
    "lib/store.ts": """
export function save(value: string): string {
  return value;
}

export function resync(a: string, b: string): string {
  return a + b;
}

export class Hierarchy {
  selectNode(id: string): string {
    return id;
  }
}

export function pick(a: string): string;
export function pick(a: number): number;
export function pick(a: string | number): string | number {
  return a;
}
""",
    "lib/widgets.tsx": """
export function Panel({ heading }: { heading: string }) {
  return <section>{heading}</section>;
}

export function Star() {
  return <b>*</b>;
}
""",
    "caller.ts": """
import { save, resync as resyncState, Hierarchy, pick } from "$lib/store";

const store = new Hierarchy();

export function viaImport(): string {
  return save("x");
}

export function viaAlias(): string {
  return resyncState("a", "b");
}

export function viaReceiver(): string {
  return store.selectNode("n");
}

export function viaOverload(): number {
  return pick(1);
}

export function viaAny(bag: any): unknown {
  return bag.whatever();
}

export function viaLibrary(): number {
  return Math.max(1, 2);
}
""",
    # Chunk 11. A component element is a call, an intrinsic one is the page, and the two
    # are told apart by React's own rule rather than by what anything resolves to.
    "page.tsx": """
import { Panel } from "$lib/widgets";
import * as icons from "$lib/widgets";

export function Card({ title }: { title: string }) {
  return <p className="lead">{title}</p>;
}

export function Page({ wide }: { wide: boolean }) {
  const rest = { id: "x" };
  return (
    <div className="page">
      <Card title="Hello" />
      <Panel heading={"Two"} wide {...rest}>
        <span>body</span>
      </Panel>
      <icons.Star />
      <my-widget />
    </div>
  );
}
""",
}


@pytest.fixture(scope="module")
def edges(tmp_path_factory):
    """One session over a small tree with a `tsconfig.json`, opened and asked for edges.

    A real `tsconfig.json` because the grouping and its `paths` map are half the feature:
    `$lib/store` resolves only through it, and a reader that ignored the project would
    report every call through it external with nothing saying why (rule 49).
    """
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    root = tmp_path_factory.mktemp("tsedges")
    paths = []
    for name, source in EDGE_TREE.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")
        if name.endswith((".ts", ".tsx")):
            paths.append(p)
    PLUGIN.probe()
    PLUGIN.open(root, paths)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(paths, root)}
        supplied = list(PLUGIN.edges())
        outside, unknown = PLUGIN.edges_outside, PLUGIN.edges_unknown
    finally:
        PLUGIN.close()
    for ff in facts.values():
        assert ff.errors == [], f"{ff.path}: {ff.errors}"
    return facts, supplied, outside, unknown


def _edge_for(facts, supplied, caller: str, expr: str, path: str = "caller.ts"):
    """The supplied edge for one call, found by the identity the reader minted."""
    ff = facts[path]
    sites = [c for c in ff.calls
             if c.callee_expr == expr
             and any(r.name == caller and r.id == c.caller_id for r in ff.routines)]
    assert len(sites) == 1, f"{caller} -> {expr}: {len(sites)} call sites"
    by_site = {e.site_id: e for e in supplied}
    return by_site.get(sites[0].site_id)


def test_an_import_beats_another_routine_of_the_same_name(edges):
    """The case a name could not get right, in a tree that holds the name twice.

    `other.ts` exports a `save` as well, and nothing imports it. A resolver matching on the
    name has two candidates and no way to choose; the checker has already chosen, because
    choosing is what it did to type the call.
    """
    facts, supplied, _, _ = edges
    edge = _edge_for(facts, supplied, "viaImport", "save")
    assert edge is not None
    assert edge.file == "lib/store.ts"
    assert edge.name == "save"
    target = [r for r in facts["lib/store.ts"].routines if r.name == "save"][0]
    assert edge.line == target.line_start, "the line the extractor recorded, not a second one"


def test_an_alias_is_followed_to_what_it_was_bound_to(edges):
    """`import { resync as resyncState }`. Nothing in the tree is *called* `resyncState`,
    so a name match finds nothing at all and the edge is simply lost."""
    facts, supplied, _, _ = edges
    edge = _edge_for(facts, supplied, "viaAlias", "resyncState")
    assert edge is not None
    assert (edge.file, edge.name) == ("lib/store.ts", "resync")


def test_a_method_through_a_typed_receiver_reaches_its_class(edges):
    """`store.selectNode(...)` where `store: Hierarchy`. The receiver's type is the whole
    answer, and it is the one thing a reader without a checker cannot have."""
    facts, supplied, _, _ = edges
    edge = _edge_for(facts, supplied, "viaReceiver", "store.selectNode")
    assert edge is not None
    assert (edge.file, edge.name) == ("lib/store.ts", "selectNode")


def test_an_overload_set_resolves_to_the_signature_the_call_fits(edges):
    """Three declarations of one name, and the checker picks by the arguments.

    Chunk 9 gave each overload an identity of its own (`UNIQUE(routines.id)` found that);
    this is what makes those identities reachable rather than merely distinct.
    """
    facts, supplied, _, _ = edges
    edge = _edge_for(facts, supplied, "viaOverload", "pick")
    assert edge is not None
    assert edge.name == "pick"
    assert edge.how == "signature"


def test_a_call_through_an_any_is_left_alone_and_a_library_call_is_named_outside(edges):
    """The two kinds of *no*, and they are two numbers (design rule 21).

    `bag.whatever()` on an `any` is *the checker could not say*. `Math.max` is *it said,
    and the answer is not in this map* — external, and the map is right about it. A reader
    that flattened them would make a healthy program that leans on its platform read
    exactly like a reader that had stopped resolving.
    """
    facts, supplied, outside, unknown = edges
    assert _edge_for(facts, supplied, "viaAny", "bag.whatever") is None
    assert _edge_for(facts, supplied, "viaLibrary", "Math.max") is None
    assert outside >= 1, "Math.max resolves into lib.es5.d.ts"
    assert unknown >= 1, "a call on an `any` resolves to nothing at all"


def test_the_standard_library_travels_in_the_bundle(edges):
    """Without it the compiler builds a program with no `Array` and **answers anyway**.

    That is rule 49 in its purest form: edges still come out, so nothing looks wrong, while
    every value typed through the platform is `any`. Measured on DunneNote at 1,935 edges
    either way and 2,587 calls moving from *could not resolve* to *resolves to a library*.
    The observable consequence is this: `Math.max` has to land in `outside`, which can only
    happen if `lib.es5.d.ts` was there to resolve it.
    """
    _, _, outside, _ = edges
    assert outside >= 1


def test_the_project_is_what_makes_a_path_alias_resolve(edges):
    """`$lib/store` is `tsconfig.json`'s `paths`, and nothing else in the world knows it.

    It is why there is a program per `tsconfig.json` rather than one for the tree: one
    options object holds one `paths` map, and a monorepo's copies disagree.
    """
    facts, supplied, _, _ = edges
    assert _edge_for(facts, supplied, "viaImport", "save") is not None


def test_the_bundle_is_the_source_it_was_built_from():
    """Rule 37, and the gap this chunk had to close before it could edit either.

    Everything that tested the bundle tested that it **exists**, that the fingerprint names
    it, and that `node main.bundle.cjs` answers `hello` — and all three pass over a bundle
    built from last month's source. This chunk is the first to edit `src/` after the bundle
    was committed, so it is the first time that could cost a whole feature sitting in a file
    nothing runs.

    Skipped where `node_modules` is absent, because rebuilding needs esbuild — the same
    shape as the `node` skip above, and named rather than silent.
    """
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    root = PLUGIN.manifest.root
    if not (root / "node_modules" / "esbuild").exists():
        pytest.skip("esbuild is not installed here — `pnpm install` in the plugin first")
    with tempfile.TemporaryDirectory(prefix="dunneflow-bundle-") as tmp:
        out = Path(tmp) / "rebuilt.cjs"
        done = subprocess.run(
            ["node", str(root / "build.mjs")],
            cwd=root, capture_output=True, text=True, check=False,
            env={**os.environ, "DUNNEFLOW_BUNDLE_OUT": str(out)},
        )
        assert done.returncode == 0, done.stderr
        assert out.read_bytes() == BUNDLE.read_bytes(), (
            "main.bundle.cjs is not what src/ builds — run `node build.mjs` and commit it"
        )


def test_a_warm_run_keeps_the_edges_it_did_not_re_read(tmp_path):
    """The whole storage argument, end to end.

    Supplied edges are a **whole-program** answer, so they are replaced whole whenever
    their reader is opened and left alone when it is not. A run that reads no file of a
    language changes none of its edges, and they are still true because nothing of that
    language changed. Per-file caching would be the alternative and it goes stale silently:
    the checker's answer for `a.ts` is built out of `b.ts`, so a `b.ts` that moved a
    function would leave `a.ts`' stored line pointing at whatever drifted into it.
    """
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    from dunneflow.resolve.calls import resolve_calls
    from dunneflow.store import Store
    from dunneflow.walk import analyze_tree

    root = tmp_path / "tree"
    root.mkdir()
    (root / "lib.ts").write_text("export function save(v: string): string { return v; }\n")
    (root / "app.ts").write_text(
        'import { save } from "./lib";\nexport function go(): string { return save("x"); }\n'
    )
    store = Store(tmp_path / "graph.db")
    try:
        cold = analyze_tree(root, store)
        assert cold.parsed == 2
        assert cold.supplied_edges["typescript"] >= 1
        first = resolve_calls(store)
        assert first.supplied >= 1
        held = store.counts()["supplied_edges"]

        warm = analyze_tree(root, store)
        assert (warm.parsed, warm.cached) == (0, 2)
        assert "typescript" not in warm.supplied_edges, "the reader was never opened"
        assert store.counts()["supplied_edges"] == held, "and its answer was left alone"
        second = resolve_calls(store)
        assert second.supplied == first.supplied
    finally:
        store.close()


# --------------------------------------------------------- JSX: an element is a call --- #
#
# Chunk 11. In a React program the component tree *is* the flow, and chunk 9 left it
# unread: a page rendering eleven components looked like a routine that called one
# function. What is asserted here is the judgement — which tags are calls — and that the
# checker answers a tag exactly as it answers a callee.


def _calls_of(facts, path: str, caller: str) -> list:
    ff = facts[path]
    owner = next(r for r in ff.routines if r.name == caller)
    return [c for c in ff.calls if c.caller_id == owner.id]


def test_a_component_element_is_a_call_and_an_intrinsic_one_is_not(edges):
    """`<Card/>` is a call; `<div>`, `<span>` and `<my-widget/>` are the page.

    React's own rule, and it is about spelling rather than about types: a bare lowercase
    tag is passed through as a *string*, so it names no routine anybody could go to. A
    hyphenated tag is a custom element and is a string too. Getting this wrong in either
    direction is visible immediately — every `<div>` in a corpus as a call site, or every
    component missing.
    """
    facts, _, _, _ = edges
    spelled = [c.callee_expr for c in _calls_of(facts, "page.tsx", "Page")]
    assert sorted(spelled) == ["Card", "Panel", "icons.Star"]


def test_a_props_are_the_arguments_a_component_was_handed(edges):
    """What a caller passed, which is what `call_args` is for — keyword by construction.

    A boolean shorthand carries no value, and `true` is React's transform rather than the
    program's word for it (rule 30), so the keyword is recorded and the expression is
    empty. A spread is `splat`, the field `...args` already uses.
    """
    facts, _, _, _ = edges
    panel = next(c for c in _calls_of(facts, "page.tsx", "Page") if c.callee_expr == "Panel")
    assert [(a.idx, a.keyword, a.expr, bool(a.splat)) for a in panel.args] == [
        (0, "heading", '"Two"', False),
        (1, "wide", "", False),
        (2, None, "rest", True),
    ]
    # The children are not arguments: `<span>body</span>` is rendered output, and storing
    # it as argument 3 would put the page's body in a column headed *what was passed*.
    assert len(panel.args) == 3


def test_the_checker_names_the_component_a_tag_reaches(edges):
    """A tag is resolved by the question that resolves a callee, not by its name."""
    facts, supplied, _, _ = edges
    local = _edge_for(facts, supplied, "Page", "Card", path="page.tsx")
    assert local is not None
    assert (local.file, local.name) == ("page.tsx", "Card")

    imported = _edge_for(facts, supplied, "Page", "Panel", path="page.tsx")
    assert imported is not None
    assert (imported.file, imported.name) == ("lib/widgets.tsx", "Panel")


def test_a_dotted_tag_is_one_name_and_reaches_what_it_names(edges):
    """`<icons.Star/>` through a namespace import — clause 1 of the dotted contract, in a
    tag, and the alias followed to what it was bound to."""
    facts, supplied, _, _ = edges
    edge = _edge_for(facts, supplied, "Page", "icons.Star", path="page.tsx")
    assert edge is not None
    assert edge.name == "Star"


def test_a_tag_is_never_offered_to_a_boundary_rule(edges):
    """A component called `Command` or `Image` must not match a `method:` list (rule 5).

    The tag goes nowhere near `matchCall`, so this holds by construction rather than by
    the rules happening not to contain a component's name today.
    """
    facts, _, _, _ = edges
    assert facts["page.tsx"].boundaries == []
    assert all(c.at_boundary is not True
               for c in _calls_of(facts, "page.tsx", "Page"))


# ------------------------------------------------- ways in a framework declares --- #
#
# Chunk 11b. A Next.js page declares nothing in the file: `app/(marketing)/services/
# [slug]/page.tsx` serves `/services/[slug]` because of where it is. The names are
# `detectors/typescript.yaml`'s `routes:` section and the derivation is `routes.ts`.

ROUTE_TREE: dict[str, str] = {
    "tsconfig.json": """{
  "compilerOptions": { "strict": true, "target": "ES2022", "module": "ESNext",
                       "moduleResolution": "bundler", "jsx": "react-jsx" }
}
""",
    # A group vanishes; a dynamic segment is kept exactly as written.
    "app/(marketing)/page.tsx": """
export default function HomePage() {
  return <main>home</main>;
}
""",
    "app/(marketing)/services/[slug]/page.tsx": """
export default async function ServiceDetailPage() {
  return <article>one</article>;
}
""",
    # `export default X;` names a component declared above it.
    "app/admin/page.tsx": """
function AdminPage() {
  return <section>admin</section>;
}

export default AdminPage;
""",
    # A handler declares one way in per verb, and `PUT` is not exported so it is not one.
    "app/api/ticket/route.ts": """
export async function GET(): Promise<string> {
  return "read";
}

export async function POST(): Promise<string> {
  return "write";
}

async function PUT(): Promise<string> {
  return "unexported";
}
""",
    # next-auth's own spelling: the verbs are bound by destructuring a library's object,
    # so nothing in the file declares a function at all.
    "app/api/auth/[...nextauth]/route.ts": """
const handlers = { GET: async () => "g", POST: async () => "p" };
export const { GET, POST } = handlers;
""",
    # Around a route rather than a route: nothing is served at its URL.
    "app/(marketing)/layout.tsx": """
export default function MarketingLayout() {
  return <div>shell</div>;
}
""",
    # Outside every declared root: a component, and not a way in.
    "components/card.tsx": """
export default function Card() {
  return <p>card</p>;
}
""",
}


@pytest.fixture(scope="module")
def routes(tmp_path_factory):
    """One session over a Next.js-shaped tree, extracted the way a run extracts."""
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    root = tmp_path_factory.mktemp("tsroutes")
    paths = []
    for name, source in ROUTE_TREE.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")
        if name.endswith((".ts", ".tsx")):
            paths.append(p)
    PLUGIN.probe()
    PLUGIN.open(root, paths)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(paths, root)}
    finally:
        PLUGIN.close()
    for ff in facts.values():
        assert ff.errors == [], f"{ff.path}: {ff.errors}"
    return facts


def _ways(facts) -> dict[str, list]:
    return {path: ff.entrypoints for path, ff in facts.items() if ff.entrypoints}


def test_a_page_is_named_by_its_url_with_the_route_groups_gone(routes):
    """`(marketing)` shares a layout and is not a URL segment.

    A `(…)` surviving into a route name is a name no reader can type into a browser, and
    it is the first thing anybody who writes Next.js checks.
    """
    named = sorted(ep.name for eps in _ways(routes).values() for ep in eps)
    assert named == [
        "/",
        "/admin",
        "/services/[slug]",
        "GET /api/auth/[...nextauth]",
        "GET /api/ticket",
        "POST /api/auth/[...nextauth]",
        "POST /api/ticket",
    ]
    assert not any("(" in n for n in named), named


def test_a_dynamic_segment_keeps_the_programs_own_word_for_it(routes):
    """`[slug]` and `[...nextauth]`, never `:slug` — translating is inventing (rule 30)."""
    named = {ep.name for eps in _ways(routes).values() for ep in eps}
    assert "/services/[slug]" in named
    assert "GET /api/auth/[...nextauth]" in named


def test_a_page_lands_on_the_component_it_default_exports(routes):
    """Both spellings: the modifier on the declaration, and `export default X;`."""
    by_name = {ep.name: ep for eps in _ways(routes).values() for ep in eps}
    home = by_name["/"]
    page = next(r for r in routes["app/(marketing)/page.tsx"].routines
                if r.name == "HomePage")
    assert home.routine_id == page.id
    assert home.kind.value == "HTTP_ROUTE"

    admin = by_name["/admin"]
    declared = next(r for r in routes["app/admin/page.tsx"].routines
                    if r.name == "AdminPage")
    assert admin.routine_id == declared.id


def test_a_handler_declares_one_way_in_per_verb_it_exports(routes):
    """One `route.ts` serving GET and POST is two ways in; an unexported `PUT` is none."""
    eps = _ways(routes)["app/api/ticket/route.ts"]
    assert [ep.name for ep in eps] == ["GET /api/ticket", "POST /api/ticket"]
    assert all(ep.routine_id is not None for ep in eps)


def test_a_verb_bound_by_destructuring_is_still_a_way_in(routes):
    """`export const { GET, POST } = handlers;` — next-auth's own spelling.

    A scan for exported *functions* finds nothing here and reports a route file serving no
    method. The routine is `None` and that is the true answer: the thing that serves the
    request was supplied by a dependency, and `ENTRYPOINT_NO_TARGET` says so.
    """
    eps = _ways(routes)["app/api/auth/[...nextauth]/route.ts"]
    assert [ep.name for ep in eps] == [
        "GET /api/auth/[...nextauth]", "POST /api/auth/[...nextauth]",
    ]
    assert all(ep.routine_id is None for ep in eps)


def test_what_sits_around_a_route_is_not_one_and_nor_is_a_component(routes):
    """`layout.tsx` is a framework hook; `components/card.tsx` is outside every root."""
    claimed = set(_ways(routes))
    assert "app/(marketing)/layout.tsx" not in claimed
    assert "components/card.tsx" not in claimed


def test_a_declaration_file_is_not_program_source():
    """A `.d.ts` declares and never implements — the reader's own rule, not the walk's.

    Measured on uigen, which vendors a generated Prisma client as `src/generated/prisma/
    *.d.ts`: read as program source it contributed 422 routines with no bodies and **83
    BROKEN anomalies**, every one an overload set in a library's declarations reported as
    a name collision in somebody's program — and `dunneflow check` exits non-zero on
    BROKEN. What it costs is stated too: DunneCorp's `types/next-auth.d.ts` is 3 genuine
    interfaces and they go with it.
    """
    rules = {r.lang: r for r in ingest.discovery()}["typescript"]
    assert ".d.ts" in rules.skip_names
    assert ".ts" in rules.suffixes, "and it is still a file this reader claims"


def test_the_route_names_are_the_yaml_s_and_the_derivation_is_the_readers():
    """Teaching this tool SvelteKit is an edit to the YAML, not to the plugin."""
    doc = rules_document("typescript")
    rule = doc["routes"][0]
    assert rule["kind"] == "HTTP_ROUTE"
    assert "app" in rule["roots"] and "src/app" in rule["roots"]
    assert "page.tsx" in rule["pages"] and "route.ts" in rule["handlers"]
    assert rule["strip_groups"] is True


# ------------------------------------------ the boundary a name cannot reach --- #
#
# Chunk 11c. The `boundaries` rules match the dotted *spelling* of an expression, which is
# a guess about what somebody called a local variable. These match the package the checker
# resolved the call into, which is what the compiler worked out to type it.

PACKAGE_TREE: dict[str, str] = {
    "tsconfig.json": """{
  "compilerOptions": { "strict": true, "target": "ES2022", "module": "ESNext",
                       "moduleResolution": "bundler" }
}
""",
    # A stand-in for a dependency, laid out the way one is: inside `node_modules`, with the
    # package's name in the path, which is the only thing `packageOf` reads.
    "node_modules/resend/index.d.ts": """
export declare class Resend {
  constructor(key: string);
  emails: { send(opts: { to: string }): Promise<void> };
}
""",
    "node_modules/resend/package.json": '{"name":"resend","types":"index.d.ts"}\n',
    "node_modules/@types/bcrypt/index.d.ts": """
export declare function hash(plain: string, rounds: number): Promise<string>;
""",
    "node_modules/@types/bcrypt/package.json": '{"name":"@types/bcrypt"}\n',
    "node_modules/bcrypt/package.json": '{"name":"bcrypt","types":"../@types/bcrypt/index.d.ts"}\n',
    "send.ts": """
import { Resend } from "resend";
import { hash } from "bcrypt";

export async function notify(to: string): Promise<void> {
  const resend = new Resend("k");
  await resend.emails.send({ to });
}

export async function secret(plain: string): Promise<string> {
  return hash(plain, 12);
}
""",
}


@pytest.fixture(scope="module")
def packages(tmp_path_factory):
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    root = tmp_path_factory.mktemp("tspkgs")
    paths = []
    for name, source in PACKAGE_TREE.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")
        # Only the program's own file is handed over; `node_modules` is the dependency and
        # the walk never offers one.
        if name == "send.ts":
            paths.append(p)
    PLUGIN.probe()
    PLUGIN.open(root, paths)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(paths, root)}
    finally:
        PLUGIN.close()
    return facts


def test_a_local_const_holding_a_client_is_still_a_boundary(packages):
    """`const resend = new Resend(k); resend.emails.send(…)`.

    No rule could match that by name without matching the *variable*, which is rule 5 and
    is why every Python rule in `detectors/*.yaml` contains a dot. The checker resolved it
    to type the call, and the package it landed in is the answer.
    """
    hits = [b for b in packages["send.ts"].boundaries if b.evidence == "resend.emails.send"]
    assert len(hits) == 1
    hit = hits[0]
    assert (hit.kind.value, hit.direction.value) == ("NETWORK", "OUT")
    # The thing touched is the dependency; the expression is already the evidence.
    assert hit.target == "resend"


def test_a_package_that_ships_its_types_apart_is_the_same_dependency(packages):
    """`bcrypt.hash` resolves into `@types/bcrypt`, and they are one dependency.

    Measured on uigen, where `@types/bcrypt` is the only spelling `bcrypt` ever has.
    """
    hits = [b for b in packages["send.ts"].boundaries if b.evidence == "hash"]
    assert [(h.kind.value, h.target) for h in hits] == [("CRYPTO", "bcrypt")]


def test_one_call_is_one_boundary_however_it_was_matched(packages):
    """Rule 40: two lanes claiming one act would be two numbers about one thing."""
    lines = [b.line for b in packages["send.ts"].boundaries]
    assert len(lines) == len(set(lines)), packages["send.ts"].boundaries


def test_the_package_table_is_the_yamls_and_names_what_it_measured():
    """The entries that are *absent* matter as much: `zod` is 169 calls in DunneCorp and is
    validation, `@types/node` is 159 in DunneNote and would collapse every file, process
    and console boundary into one target called `node`."""
    table = rules_document("typescript")["packages"]
    assert table["stripe"]["kind"] == "NETWORK"
    assert table["@aws-sdk/"]["kind"] == "CLOUD_SDK"
    # `.prisma` is not a typo: a generated client's types live in `node_modules/.prisma`.
    assert table[".prisma"]["target"] == "receiver_tail"
    for absent in ("zod", "@types/node", "react", "next", "svelte", "prosemirror-model"):
        assert absent not in table, absent


def test_an_unknown_target_strategy_is_refused_rather_than_defaulted(tmp_path):
    """Rule 49, in the file whose whole point is that somebody can edit it.

    Driven through the reader itself, because the refusal is the plugin's: a misspelt
    strategy that quietly fell back would leave every row it governs naming the wrong
    thing with nothing to say so.
    """
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    doc = dict(rules_document("typescript"))
    doc["packages"] = {"resend": {"kind": "NETWORK", "target": "the-wrong-word"}}
    out = subprocess.run(
        ["node", str(BUNDLE)],
        input=json.dumps({"t": "open", "id": 1, "root": str(tmp_path),
                          "files": [], "rules": doc}) + "\n",
        capture_output=True, text=True, timeout=120,
    )
    assert "the-wrong-word" in (out.stdout + out.stderr)
    assert "receiver_tail" in (out.stdout + out.stderr), "and it names the ones that work"


# ------------------------------------- React: the callback, and the file's own word --- #
#
# Chunk 11d and 11e. A hook's callback is where a React component does the things this
# tool records; a directive prologue is a word written above the thing it marks.

REACT_TREE: dict[str, str] = {
    "tsconfig.json": """{
  "compilerOptions": { "strict": true, "target": "ES2022", "module": "ESNext",
                       "moduleResolution": "bundler", "jsx": "react-jsx" }
}
""",
    "panel.tsx": """
"use client";

import { useEffect, useCallback, useState } from "react";

export function Panel({ id }: { id: string }) {
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    console.log("opened", id);
  }, [id]);

  useEffect(() => {
    console.error("second effect");
  }, []);

  const save = useCallback(() => {
    console.warn("saving", id);
  }, [id]);

  return <button onClick={save}>{seen}</button>;
}
""",
    "actions.ts": """
"use server";

export async function createThing(name: string): Promise<string> {
  return name;
}

export async function deleteThing(id: string): Promise<void> {
  console.log(id);
}
""",
}


@pytest.fixture(scope="module")
def react(tmp_path_factory):
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    root = tmp_path_factory.mktemp("tsreact")
    paths = []
    for name, source in REACT_TREE.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(source, encoding="utf-8")
        if name.endswith((".ts", ".tsx")):
            paths.append(p)
    PLUGIN.probe()
    PLUGIN.open(root, paths)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(paths, root)}
    finally:
        PLUGIN.close()
    for ff in facts.values():
        assert ff.errors == [], f"{ff.path}: {ff.errors}"
    return facts


def test_an_effect_is_a_routine_nested_in_the_component(react):
    """What an effect touches is filed under the effect, not under the component that
    merely declares it (rule 10)."""
    names = {r.qualname for r in react["panel.tsx"].routines}
    assert "panel.Panel.useEffect" in names
    effect = next(r for r in react["panel.tsx"].routines
                  if r.qualname == "panel.Panel.useEffect")
    assert effect.is_nested is True
    owned = [b for b in react["panel.tsx"].boundaries if b.routine_id == effect.id]
    assert [b.evidence for b in owned] == ["console.log"]


def test_a_second_effect_is_a_second_name_and_not_a_collision(react):
    """Found by running this on uigen: two effects in one component were two routines with
    one qualname, and `NAME_COLLISION` reported a **BROKEN** defect in a program that has
    none — out of a command that gates CI on BROKEN. A name the program chose twice is a
    collision and is the finding; a name this reader applies by convention is expected to
    repeat and carries the ordinal that says which one it is."""
    names = sorted(r.qualname for r in react["panel.tsx"].routines
                   if r.name.startswith("useEffect"))
    assert names == ["panel.Panel.useEffect", "panel.Panel.useEffect#2"]
    ids = {r.id for r in react["panel.tsx"].routines}
    assert len(ids) == len(react["panel.tsx"].routines)


def test_a_hook_bound_to_a_name_takes_that_name(react):
    """`const save = useCallback(() => {…})` is **save** — the word the file uses, and the
    only way that arrow becomes a routine at all (`variableStatement` looks for a function
    and finds a call)."""
    saves = [r for r in react["panel.tsx"].routines if r.name == "save"]
    assert len(saves) == 1
    assert saves[0].qualname == "panel.Panel.save"


def test_a_directive_marks_every_routine_in_its_file(react):
    """A file-level `"use server"` marks all of its exports — that is what it means — so a
    reader asking which routines are server actions has to find them all."""
    assert all("use server" in (r.decorators or [])
               for r in react["actions.ts"].routines), react["actions.ts"].routines
    assert all("use client" in (r.decorators or [])
               for r in react["panel.tsx"].routines)


def test_the_words_and_the_sentence_are_the_languages_and_not_the_renderers():
    """`render/markdown.py` prints the count and the query; what a mark *means* comes from
    `detectors/<lang>.yaml`, so a sentence about React is not written into a
    language-agnostic renderer where no language could edit it (rule 51)."""
    declared = rules_document("typescript")["directives"]
    assert declared["use server"]["claimed"] is False
    assert "across the wire" in declared["use server"]["says"]
    # `use client` is recorded and *is* claimed — it hides nothing, so it is not listed
    # under what the map does not claim.
    assert declared["use client"].get("claimed", True) is True
    assert "use strict" not in declared


def test_both_passes_find_one_tree_whatever_the_separator():
    """The extractor and the compiler share one parse, and that rests on one cache key.

    `main.ts` resolves a file to `C:\\…\\a.ts`; the compiler asks the host for `C:/…/a.ts`.
    Keyed as each side spelt it, `Session.sourceFile` missed on Windows, quietly parsed the
    file a second time, and handed the extractor a tree the checker had never bound — so
    every TypeScript file failed with "Cannot read properties of undefined (reading
    'members')" on Windows and nowhere else. Found on GIZA on 2026-10-01; a macOS or Linux
    run cannot see it, because there both spellings are the same string.

    So it is held over the source rather than by behaviour: every read and write of the
    shared cache goes through `cacheKey`, and `cacheKey` folds the platform separator.
    """
    program = (Path(ingest.__file__).parent.parent / "plugins" / "typescript" / "src"
               / "program.ts").read_text(encoding="utf-8")
    import re
    touches = re.findall(r"\b(?:byPath|cache)\.(?:get|set|has|delete)\(([^,)]*)", program)
    assert touches, "the shared cache is no longer reached the way this test reads it"
    unkeyed = [arg for arg in touches if not arg.strip().startswith("cacheKey(")]
    assert not unkeyed, f"the shared cache is reached by a raw path: {unkeyed}"
    body = program[program.index("export function cacheKey"):]
    body = body[:body.index("\n}")]
    assert "split(sep)" in body, "cacheKey no longer folds the platform separator"


# ------------------------------------------------- fetch through a name (BACKLOG 4) --- #

FETCH_TREE: dict[str, str] = {
    "tsconfig.json": """{
  "compilerOptions": { "strict": true, "target": "ES2022", "module": "ESNext",
                       "moduleResolution": "bundler", "lib": ["ES2022", "DOM"] }
}
""",
    "net.ts": """
const f = fetch;
const g = window.fetch;
const h = fetch.bind(globalThis);
let reassigned = fetch;

function fetchLike(u: string): string { return u; }
const mine = fetchLike;

export async function direct() { return fetch("/direct"); }
export async function viaConst() { return f("/f"); }
export async function viaWindow() { return g("/g"); }
export async function viaBind() { return h("/h"); }
export async function viaLet() { return reassigned("/let"); }
export async function injected(fetchImpl: typeof fetch) { return fetchImpl("/injected"); }
export function ours() { return mine("/ours"); }
""",
}


@pytest.fixture(scope="module")
def fetched(tmp_path_factory):
    """A synthetic tree, because no real one calls `fetch` through a name (BACKLOG 4)."""
    if PLUGIN is None:
        pytest.skip("no typescript plugin in this build")
    root = tmp_path_factory.mktemp("tsfetch")
    paths = []
    for name, source in FETCH_TREE.items():
        p = root / name
        p.write_text(source, encoding="utf-8")
        if name.endswith(".ts"):
            paths.append(p)
    PLUGIN.probe()
    PLUGIN.open(root, paths)
    try:
        facts = {ff.path: ff for ff in PLUGIN.extract(paths, root)}
    finally:
        PLUGIN.close()
    return facts["net.ts"]


def test_the_global_fetch_held_in_a_const_is_a_network_call(fetched):
    """`const f = fetch`, `window.fetch` and a `.bind` of it: the request is made."""
    network = {n.expr for n in fetched.network}
    boundaries = {b.evidence for b in fetched.boundaries if b.kind.value == "NETWORK"}
    for expr in ("fetch", "f", "g", "h"):
        assert expr in network, (expr, network)
        assert expr in boundaries, (expr, boundaries)
    destinations = {n.expr: n.destination for n in fetched.network}
    assert destinations["f"] == "/f"


def test_a_name_that_only_might_hold_fetch_is_not_one(fetched):
    """By value, never by type: a parameter typed `typeof fetch` holds whatever it was
    handed (DunneNote's `fetchImpl`), a `let` can be rebound, and a const holding this
    program's own function is this program's code (rule 5)."""
    named = {n.expr for n in fetched.network} | {b.evidence for b in fetched.boundaries}
    for expr in ("fetchImpl", "reassigned", "mine"):
        assert expr not in named, expr
