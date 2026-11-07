"""A command sent by name from one language and answered in another (`resolve/ipc.py`).

The fixture is DunneNote's shape in miniature, because DunneNote is where the first plan
would have found nothing: the front end never calls `invoke` with a literal. It calls a
seam, `call('name')`, which hands its parameter to a transport held in a **variable**, and
only the transport calls `invoke`. And two applications sit in one tree, `apps/app` and
`legacy`, each registering a command of the same name.

Needs both readers, so it needs `node` and `cargo`, and says so in the skip.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.anomalies import SUSPECT, detect
from dunneflow.resolve.calls import resolve_calls
from dunneflow.resolve.ipc import _literal
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

pytestmark = pytest.mark.skipif(
    ingest.PLUGINS.get("typescript") is None or ingest.PLUGINS.get("rust") is None
    or shutil.which("node") is None or shutil.which("cargo") is None,
    reason="needs the TypeScript and Rust readers, `node` and `cargo`",
)

TREE = {
    "apps/app/src/client.ts": """\
import { invoke } from '@tauri-apps/api/core';

export const transport = (command: string, args?: object): Promise<unknown> =>
  invoke(command, args);

let active = transport;

export function call(command: string, args?: object): Promise<unknown> {
  return active(command, args);
}
""",
    "apps/app/src/store.ts": """\
import { call } from './client';

export async function load(): Promise<void> {
  await call('list_notes');
  await call('missing_cmd', { a: 1 });
  await call('plugin:dialog|open');
  await call('forgotten');
  const name = 'list_notes';
  await call(name);
  await call('shared');
}
""",
    "apps/app/src/direct.ts": """\
import { invoke } from '@tauri-apps/api/core';

export function ping(): Promise<unknown> {
  return invoke('ping');
}
""",
    "apps/app/src-tauri/src/lib.rs": """\
#[tauri::command]
pub fn list_notes() {}

#[tauri::command]
pub fn ping() {}

#[tauri::command]
pub fn shared() {}

#[tauri::command]
pub fn forgotten() {}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![list_notes, ping, shared])
        .run(tauri::generate_context!());
}
""",
    "legacy/src-tauri/src/lib.rs": """\
#[tauri::command]
pub fn shared() {}

pub fn run() {
    tauri::Builder::default().invoke_handler(tauri::generate_handler![shared]);
}
""",
    "neither/src/tie.ts": """\
import { call } from '../../apps/app/src/client';

export function tie(): void {
  call('shared');
}
""",
}


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    root: Path = tmp_path_factory.mktemp("ipc")
    for rel, text in TREE.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    s = Store(root / "g.db")
    analyze_tree(root, s)
    s.stats = resolve_calls(s)
    yield s
    s.close()


def _links(store):
    return {(r["file"], r["line"]): (r["command"], r["status"], r["entrypoint_file"])
            for r in store.query(
                "SELECT l.file, l.line, l.command, l.status, e.file AS entrypoint_file"
                "  FROM ipc_links l LEFT JOIN entrypoints e ON e.id = l.entrypoint_id")}


def test_every_send_is_found_through_the_seam_and_judged(store):
    assert _links(store) == {
        ("apps/app/src/store.ts", 4): ("list_notes", "linked", "apps/app/src-tauri/src/lib.rs"),
        ("apps/app/src/store.ts", 5): ("missing_cmd", "unknown", None),
        ("apps/app/src/store.ts", 6): ("plugin:dialog|open", "foreign", None),
        ("apps/app/src/store.ts", 7): ("forgotten", "unregistered",
                                       "apps/app/src-tauri/src/lib.rs"),
        ("apps/app/src/store.ts", 9): ("", "dynamic", None),
        # Two applications register `shared`; the nearer one answers.
        ("apps/app/src/store.ts", 10): ("shared", "linked", "apps/app/src-tauri/src/lib.rs"),
        ("apps/app/src/direct.ts", 4): ("ping", "linked", "apps/app/src-tauri/src/lib.rs"),
        # Equally far from both: linked to neither (rule 1).
        ("neither/src/tie.ts", 4): ("shared", "ambiguous", None),
    }


def test_the_seam_s_own_forwarding_is_not_a_send(store):
    """`invoke(command)` inside the transport is the carrier working, not a name."""
    carriers = {r["qualname"] for r in store.query(
        "SELECT qualname FROM routines WHERE id IN (SELECT carrier_id FROM ipc_links)")}
    assert carriers == {"apps.app.src.client.call"}
    assert not store.query("SELECT 1 FROM ipc_links WHERE file = 'apps/app/src/client.ts'")


def test_the_link_is_never_a_call_edge(store):
    """Rule 2: the site keeps the edge it had, and the command gains no caller in `calls`."""
    cmd_ids = [r["routine_id"] for r in store.query(
        "SELECT routine_id FROM entrypoints WHERE kind = 'IPC_COMMAND'")]
    assert cmd_ids
    marks = ",".join("?" * len(cmd_ids))
    assert not store.query(f"SELECT 1 FROM calls WHERE callee_id IN ({marks})", tuple(cmd_ids))
    assert {r["confidence"] for r in store.query("SELECT confidence FROM ipc_links")} == {
        "INFERRED"}


def test_the_resolve_says_what_it_found(store):
    said = store.stats.ipc.sentence()
    assert said.startswith("commands by name: 8 sites send one (3 linked by name to a command")
    assert "1 name no command" in said and "1 build the name at run time" in said


def test_an_unregistered_command_and_an_unknown_name_are_suspect(store):
    found = {(a.kind, a.subject): a for a in detect(store).items
             if a.kind in ("UNREGISTERED_COMMAND", "UNKNOWN_COMMAND")}
    assert set(found) == {("UNREGISTERED_COMMAND", "forgotten"),
                          ("UNKNOWN_COMMAND", "missing_cmd")}
    assert {a.severity for a in found.values()} == {SUSPECT}
    assert all(a.blind_spot for a in found.values())


def test_a_command_is_a_way_in_so_it_is_not_dead(store):
    dead = next((a for a in detect(store).items if a.kind == "DEAD_CODE"), None)
    names = {o.label for o in dead.occurrences} if dead else set()
    assert not names & {"apps.app.src-tauri.src.lib.list_notes",
                        "apps.app.src-tauri.src.lib.forgotten"}


@pytest.mark.parametrize("expr, name", [
    ("'list_notes'", "list_notes"), ('"a_b"', "a_b"), ("`plain`", "plain"),
    ("`x_${n}`", None), ("name", None), ("'it\\'s'", None), ("''", ""), ("'", None),
])
def test_only_a_name_written_whole_is_a_name(expr, name):
    assert _literal(expr) == name


def _id(store, qualname):
    return store.query("SELECT id FROM routines WHERE qualname = ?", (qualname,))[0]["id"]


def test_a_reach_crosses_into_the_command_and_back_out_of_it(store):
    """`touches` goes on into the command; `impact` comes back to the sender (5c)."""
    load = _id(store, "apps.app.src.store.load")
    cmd = _id(store, "apps.app.src-tauri.src.lib.list_notes")
    assert cmd in store.reachable_from(load)
    assert cmd in store.reachable_from_many([load])
    assert load in store.callers_of(cmd)
    sent = {(x["command"], x["status"]) for x in store.ipc_sent(store.reachable_from(load))}
    assert ("list_notes", "linked") in sent and ("missing_cmd", "unknown") in sent
    [got] = [x for x in store.ipc_received([cmd]) if x["command"] == "list_notes"]
    assert (got["sender"], got["how"]) == ("apps.app.src.store.load", "by name")


def test_an_unlinked_send_is_not_crossed(store):
    """`forgotten` is a command, and the send names it -- but nothing registers it, so
    nothing can answer, and the walk does not pretend it does."""
    load = _id(store, "apps.app.src.store.load")
    forgotten = _id(store, "apps.app.src-tauri.src.lib.forgotten")
    assert forgotten not in store.reachable_from(load)


def test_the_cli_says_the_crossing_was_by_name():
    from dunneflow.cli import ipc_sent_lines
    rows = [
        {"status": "linked", "command": "a", "command_qualname": "x.a"},
        {"status": "unknown", "command": "b", "command_qualname": None},
        {"status": "dynamic", "command": "", "command_qualname": None},
    ]
    assert ipc_sent_lines(rows) == [
        "crosses into another process by name at 1 site, to 1 command (matched by name): x.a",
        "sends a command by name and links nothing: 1 built at run time · "
        "1 no command answers (b)",
    ]


def test_a_store_that_cannot_change_walks_the_same_crossing(store):
    """A read-only store walks in memory (`_reach_graph`), and must cross as the query does."""
    ro = Store(store.path, writable=False)
    try:
        load = _id(ro, "apps.app.src.store.load")
        cmd = _id(ro, "apps.app.src-tauri.src.lib.list_notes")
        assert ro._reach_graph() is not None
        assert cmd in ro.reachable_from(load)
        assert cmd in ro.reachable_from_many([load])
        assert [x["command"] for x in ro.ipc_received([cmd])] == ["list_notes"]
    finally:
        ro.close()


def test_the_network_page_names_the_far_end_and_draws_one_dotted_arrow(store, tmp_path):
    """5d: a crossing is a dotted arrow per client and process, never a box per command."""
    from dunneflow.render.network import render_network
    from dunneflow.render.page import Stamp

    page = render_network(store, tmp_path, "ipc", Stamp(generated="x", revision="", analysed=""))
    text = page.read_text(encoding="utf-8")
    assert "## Commands called by name" in text and "INFERRED" in text
    assert "| a client in apps/app | `(not started by this program)` | 3 | 3 |" in text
    assert text.count("-.->|by name ×3|") == 1  # the tie links nothing, so one client
    assert text.count("answers commands by name") == 1


def test_the_inspector_lists_a_crossing_apart_from_the_calls(store):
    from dunneflow.web.detail import describe

    cmd = _id(store, "apps.app.src-tauri.src.lib.list_notes")
    d = describe(store, cmd, None)
    assert d["in"]["callers"] == []
    assert [(r["qualname"], r["how"]) for r in d["in"]["by_name"]] == [
        ("apps.app.src.store.load", "by name")]
    sends = describe(store, _id(store, "apps.app.src.store.load"), None)["out"]["by_name"]
    assert [r["status"] for r in sends] == [
        "linked", "unknown", "foreign", "unregistered", "dynamic", "linked"]


def test_about_counts_the_crossings(store):
    got = store.ipc_of_map()
    assert got == {"sites": 8, "status": {"ambiguous": 1, "dynamic": 1, "foreign": 1,
                                         "linked": 3, "unknown": 1, "unregistered": 1},
                   "commands": 5, "registered": 4, "named": 3, "how": "by name"}


def test_a_process_zone_does_not_cross(store):
    load = _id(store, "apps.app.src.store.load")
    cmd = _id(store, "apps.app.src-tauri.src.lib.list_notes")
    assert cmd in store.reachable_from_many([load])
    assert cmd not in store.reachable_from_many([load], cross=False)


def test_a_registered_command_no_client_sends_is_reported_as_dead_code_is(store):
    """BACKLOG 40, Tom 2026-11-07: dead code by another route, at DEAD_CODE's severity.
    `shared` is answered twice and one send is ambiguous between them, so neither is unsent;
    `forgotten` is unregistered, and that is its own finding (rule 40). Every other command
    in the fixture is sent."""
    found = [a for a in detect(store).items if a.kind == "UNSENT_COMMAND"]
    assert found == [], [a.detail for a in found]


def test_an_unsent_command_is_one_finding_for_the_program(tmp_path):
    from dunneflow.anomalies import INFO, POSSIBLE

    tree = tmp_path / "apps" / "app"
    (tree / "src").mkdir(parents=True)
    (tree / "src-tauri" / "src").mkdir(parents=True)
    (tree / "src" / "main.ts").write_text(
        "import { invoke } from '@tauri-apps/api/core';\n"
        "export const a = () => invoke('ping');\n", encoding="utf-8")
    (tree / "src-tauri" / "src" / "lib.rs").write_text(
        "#[tauri::command]\npub fn ping() {}\n\n#[tauri::command]\npub fn unused() {}\n\n"
        "#[tauri::command]\npub fn also_unused() {}\n\n"
        "pub fn run() {\n    tauri::Builder::default()\n"
        "        .invoke_handler(tauri::generate_handler![ping, unused, also_unused]);\n}\n",
        encoding="utf-8")
    (tree / "src-tauri" / "Cargo.toml").write_text(
        '[package]\nname = "app"\nversion = "0.1.0"\n', encoding="utf-8")
    s = Store(tmp_path / "g.db")
    analyze_tree(tmp_path, s)
    s.stats = resolve_calls(s)
    found = [a for a in detect(s).items if a.kind == "UNSENT_COMMAND"]
    s.close()
    assert len(found) == 1
    a = found[0]
    assert (a.severity, a.confidence, a.count) == (INFO, POSSIBLE, 2)
    assert a.detail == "also_unused; unused"
    assert [o.label for o in a.occurrences] == ["also_unused", "unused"]
