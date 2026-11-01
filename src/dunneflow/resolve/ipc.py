"""A call that names a command in another process, and the way in that answers it.

PLAN-v2's question 7. DunneNote's front end is TypeScript and its back end is Rust, and the
only thing joining them is a **string**: `call('list_notes')` on one side, and on the other
a `#[tauri::command] fn list_notes` that a `generate_handler![…]` hands to Tauri's
dispatch. No reference crosses, so no resolver can draw it, and a map of the two halves
reads as two programs that never meet.

**This module names no language.** The client side is declared in a rules file
(`ipc.clients`: a function a module exports), the server side is facts a reader sent
(`EntrypointKind.IPC_COMMAND` and `ipc_registrations`), and a name that belongs to
neither is declared as a prefix (`ipc.foreign_prefixes`). What is decided here is only
which call sites *send* a name, and which command, if any, answers it.

**Which sites send a name.** Measured on DunneNote before it was written, because the
first plan looked for literals passed to `invoke` and would have found none:

- *the client itself*, called directly: `invoke('x')` in a file that imports it;
- *a carrier*: a routine that hands its own first parameter on, as the first argument of
  a call. DunneNote's `pl/client.ts` does exactly that, twice -- `tauriTransport(command)`
  calls `invoke(command)`, and `call(command)` calls `active(command)`, where `active` is
  a variable holding the transport. **The variable is why a carrier is judged by what it
  does with its parameter rather than by what it calls**: `active` resolves to nothing,
  and the 179 sites that matter go through it. A carrier must stand in a file that
  imports a declared client, or be reached from one along a CERTAIN edge, so a routine
  that merely forwards an argument somewhere unrelated is never one.

A site inside a carrier that forwards that carrier's own parameter is the carrier working,
not a send, and is left out -- otherwise every map with a client seam would report its seam
as a name nobody can read.

**What answers it.** A command whose name equals the literal, among those some registrar
names. **Two applications in one tree** -- DunneNote keeps `legacy/v0.1` beside
`apps/desktop`, each with its own `generate_handler!` -- are told apart by path: the
command whose registration shares the longest leading directory run with the site wins,
and a tie is recorded as `ambiguous` and linked to nothing (rule 1).

**Rule 2 holds, and it is the shape of the table.** The site is a boundary call into the
client library and stays one; `calls.callee_id` is never written here. `ipc_links` is a
second fact about the far end, `how = "by name"` and `INFERRED`, because a string equal to
a name is evidence and not a reference. It is replaced whole on every resolve.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ..detectors import load_rules
from ..schema import Confidence, EntrypointKind
from ..store import Store

HOW = "by name"

# The statuses a site can end in. Each is a different answer, and a count that folded any
# two of them together would be a number about two things (rule 32).
LINKED = "linked"
UNKNOWN = "unknown"            # a literal no command of the tree answers
UNREGISTERED = "unregistered"  # a command answers the name, and nothing registers it
AMBIGUOUS = "ambiguous"        # two applications answer it, equally near
DYNAMIC = "dynamic"            # the name is not written as a literal; nothing is guessed
FOREIGN = "foreign"            # a declared prefix: a plugin's command, not this tree's


@dataclass(slots=True)
class IpcStats:
    """What the linker found, for the summary line and for *About this map*.

    `recorded` separates *nothing sends a command* from *this map was never asked*: a
    tree whose languages declare no client gets `recorded = False` and says nothing.
    """

    recorded: bool = False
    clients: int = 0
    carriers: int = 0
    commands: int = 0
    registered: int = 0
    sites: int = 0
    status: dict[str, int] = field(default_factory=dict)

    def sentence(self) -> str:
        if not self.recorded or not (self.sites or self.commands):
            return ""
        s = self.status
        bits = [f"{s.get(LINKED, 0):,} linked by name to a command"]
        for key, said in ((UNKNOWN, "name no command"),
                          (UNREGISTERED, "name an unregistered command"),
                          (AMBIGUOUS, "are ambiguous between two applications"),
                          (DYNAMIC, "build the name at run time"),
                          (FOREIGN, "name a plugin's command")):
            if s.get(key):
                bits.append(f"{s[key]:,} {said}")
        return (f"commands by name: {self.sites:,} site{'' if self.sites == 1 else 's'} "
                f"send one ({', '.join(bits)}); {self.commands:,} command"
                f"{'' if self.commands == 1 else 's'}, {self.registered:,} registered")


def _literal(expr: str) -> str | None:
    """The string a call site spells out whole, or None where any of it is computed."""
    if len(expr) < 2 or expr[0] not in "'\"`" or expr[-1] != expr[0]:
        return None
    body = expr[1:-1]
    if expr[0] in body or "\\" in body or (expr[0] == "`" and "${" in body):
        return None
    return body


def _shared(a: str, b: str) -> int:
    """How many leading directories two stored paths share."""
    pa, pb = PurePosixPath(a).parent.parts, PurePosixPath(b).parent.parts
    n = 0
    for x, y in zip(pa, pb, strict=False):
        if x != y:
            break
        n += 1
    return n


def resolve_ipc(store: Store) -> IpcStats:
    """Derive `ipc_links` from the whole tree, replacing what was there."""
    stats = IpcStats()
    clients: set[tuple[str, str]] = set()
    foreign: set[str] = set()
    for row in store.query("SELECT DISTINCT lang FROM files ORDER BY lang"):
        rules = load_rules(row["lang"])
        clients.update(rules.ipc_clients)
        foreign.update(rules.ipc_foreign)

    with store.batch():
        store.conn.execute("DELETE FROM ipc_links")
    if not clients:
        return stats
    stats.recorded = True

    # --- the client, as each file that imports it spells it -------------------------- #
    spelt: dict[str, set[str]] = {}
    for imp in store.query("SELECT file, module, name, alias, is_from FROM imports"):
        for module, fn in clients:
            if imp["module"] != module:
                continue
            if imp["is_from"] and imp["name"] == fn:
                spelt.setdefault(imp["file"], set()).add(imp["alias"] or fn)
            elif not imp["is_from"] and imp["alias"]:
                spelt.setdefault(imp["file"], set()).add(f"{imp['alias']}.{fn}")
    stats.clients = len(spelt)

    # --- every call with its first argument ----------------------------------------- #
    sites = store.query(
        "SELECT c.site_id, c.file, c.line, c.caller_id, c.callee_expr, c.callee_id,"
        "       c.confidence, a.expr AS arg0"
        "  FROM calls c LEFT JOIN call_args a ON a.site_id = c.site_id AND a.idx = 0"
        " ORDER BY c.file, c.line, c.site_id"
    )
    first_param = {r["routine_id"]: r["name"] for r in store.query(
        "SELECT routine_id, name FROM params WHERE idx = 0")}

    def forwards(s: sqlite3.Row) -> bool:
        p = first_param.get(s["caller_id"])
        return p is not None and s["arg0"] == p

    direct = [s for s in sites if s["callee_expr"] in spelt.get(s["file"], ())]
    carriers: set[str] = {s["caller_id"] for s in sites
                          if s["file"] in spelt and forwards(s)}
    # Carried further only along CERTAIN edges: a routine that hands its first parameter
    # to a carrier is one, and nothing reached by a guess makes another (rule 6).
    while True:
        more = {s["caller_id"] for s in sites
                if s["callee_id"] in carriers and s["confidence"] == Confidence.CERTAIN.value
                and forwards(s) and s["caller_id"] not in carriers}
        if not more:
            break
        carriers |= more
    stats.carriers = len(carriers)

    sending = [s for s in direct if not (s["caller_id"] in carriers and forwards(s))]
    sending += [s for s in sites
                if s["callee_id"] in carriers and s["confidence"] == Confidence.CERTAIN.value
                and not (s["caller_id"] in carriers and forwards(s))]

    # --- the commands, and where each is registered --------------------------------- #
    regs: dict[str, list[str]] = {}
    for r in store.query("SELECT file, name FROM ipc_registrations ORDER BY file, line"):
        regs.setdefault(r["name"], []).append(r["file"])
    commands: dict[str, list[tuple[str, str | None, str]]] = {}
    for e in store.query(
        "SELECT e.id, e.name, e.routine_id, e.file FROM entrypoints e WHERE e.kind = ?"
        " ORDER BY e.name, e.file, e.id", (EntrypointKind.IPC_COMMAND.value,)
    ):
        commands.setdefault(e["name"], []).append((e["id"], e["routine_id"], e["file"]))
    stats.commands = sum(len(v) for v in commands.values())
    stats.registered = sum(len(v) for n, v in commands.items() if n in regs)

    def registration_of(name: str, cmd_file: str) -> str:
        """The registration nearest the command: the one that registers *this* one."""
        return max(regs[name], key=lambda f: (_shared(f, cmd_file), f))

    rows = []
    seen: set[str] = set()
    for s in sending:
        if s["site_id"] in seen:
            continue
        seen.add(s["site_id"])
        carrier = s["callee_id"] if s["callee_id"] in carriers else None
        name = _literal(s["arg0"] or "")
        ep_id: str | None = None
        routine: str | None = None
        if name is None:
            status = DYNAMIC
        elif any(name.startswith(p) for p in foreign):
            status = FOREIGN
        elif name not in commands:
            status = UNKNOWN
        elif name not in regs:
            status = UNREGISTERED
            ep_id, routine, _ = commands[name][0]
        else:
            scored = sorted(
                ((_shared(s["file"], registration_of(name, f)), i, r)
                 for i, r, f in commands[name]),
                key=lambda t: (-t[0], t[1]),
            )
            if len(scored) > 1 and scored[0][0] == scored[1][0]:
                status = AMBIGUOUS
            else:
                status = LINKED
                ep_id, routine = scored[0][1], scored[0][2]
        stats.status[status] = stats.status.get(status, 0) + 1
        rows.append((s["site_id"], s["caller_id"], s["file"], s["line"], name or "",
                     carrier, ep_id, routine, status, HOW if status == LINKED else "",
                     Confidence.INFERRED.value))
    stats.sites = len(rows)

    with store.batch():
        store.conn.executemany(
            "INSERT INTO ipc_links(site_id,caller_id,file,line,command,carrier_id,"
            "entrypoint_id,routine_id,status,how,confidence) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
    return stats
