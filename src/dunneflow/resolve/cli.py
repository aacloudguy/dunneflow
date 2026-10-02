"""Resolving the command tree.

A console script names an object, not a function: `mensores = "mensores.cli:app"`. That
object is a Typer application, usually re-exported through a package `__init__`, with
commands attached by decorator and whole sub-applications mounted onto it.

Following that chain is what turns "one executable" into the readable answer to
"what can I actually tell this thing to do?" -- which is the first question anyone
asks of an unfamiliar program.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from ..detectors import load_rules
from ..store import Store
from . import languages
from .python.calls import _absolute


@dataclass(slots=True)
class CliStats:
    apps: int = 0
    mounts_resolved: int = 0
    mounts_total: int = 0
    commands_found: int = 0
    commands_attached: int = 0
    scripts_linked: int = 0
    launches_linked: int = 0


class _AppResolver:
    """Finds the CLI application object a (module, variable) pair refers to."""

    def __init__(self, store: Store) -> None:
        self.by_modvar: dict[tuple[str, str], str] = {}
        for r in store.query("SELECT id, module, var FROM cli_apps"):
            self.by_modvar[(r["module"], r["var"])] = r["id"]

        self.module_file: dict[str, str] = {}
        self.packages: set[str] = set()
        for r in store.query("SELECT path, module FROM files"):
            self.module_file.setdefault(r["module"], r["path"])
            if Path(r["path"]).name == "__init__.py":
                self.packages.add(r["module"])

        self.imports: dict[str, dict[str, tuple[str, str, bool]]] = defaultdict(dict)
        for r in store.query("SELECT file, module, name, alias, is_from FROM imports"):
            self.imports[r["file"]][r["alias"]] = (r["module"], r["name"], bool(r["is_from"]))

    def resolve(self, module: str, var: str, file: str | None = None,
                depth: int = 0) -> str | None:
        """Follow re-exports until the definition is found, or give up."""
        if depth > 6:
            return None
        direct = self.by_modvar.get((module, var))
        if direct:
            return direct
        path = file or self.module_file.get(module)
        if not path:
            return None
        entry = self.imports.get(path, {}).get(var)
        if not entry:
            return None
        mod, name, is_from = entry
        if not is_from:
            return None
        abs_mod = _absolute(mod, module, module in self.packages)
        return self.resolve(abs_mod, name, None, depth + 1)


def resolve_cli(store: Store) -> CliStats:
    """Link console scripts to apps, apps to their sub-apps, and commands to apps."""
    r = _AppResolver(store)
    stats = CliStats(apps=len(r.by_modvar))

    # Sub-applications mounted onto a parent.
    mount_updates: list[tuple[str | None, str | None, int]] = []
    for m in store.query(
        "SELECT rowid, file, parent_var, parent_module, child_expr FROM cli_mounts"
    ):
        stats.mounts_total += 1
        child = m["child_expr"]
        if not child:
            continue
        parent = r.resolve(m["parent_module"], m["parent_var"], m["file"])
        # `app.add_typer(pkg.sub_app)` as well as the plain `app.add_typer(sub_app)`.
        var = child.rsplit(".", 1)[-1]
        found = r.resolve(m["parent_module"], var, m["file"])
        if found:
            stats.mounts_resolved += 1
        mount_updates.append((found, parent, m["rowid"]))

    # Commands attach to whichever app object their decorator named.
    ep_updates: list[tuple[str, str]] = []
    for e in store.query(
        "SELECT id, module, grp, file FROM entrypoints WHERE grp != '' AND parent_id IS NULL"
    ):
        found = r.resolve(e["module"], e["grp"], e["file"])
        if found:
            ep_updates.append((found, e["id"]))
            stats.commands_attached += 1

    # Commands registered by direct call name their handler by expression.
    routine_updates: list[tuple[str, str]] = []
    for e in store.query(
        "SELECT id, module, file, target_expr FROM entrypoints"
        " WHERE target_expr != '' AND routine_id IS NULL"
    ):
        rid = _resolve_routine(store, r, e["module"], e["file"], e["target_expr"])
        if rid:
            routine_updates.append((rid, e["id"]))

    # A way in that launches an app object commands everything attached to it.
    # `def main(): mcp.run()` is a one-line function and a whole server at once.
    #
    # **The launch methods of every language the map holds**, not Python's. This read
    # `load_rules("python")` while Python was the only reader, which was the whole truth
    # at the time and is the shape that makes a second language's CLI silently vanish --
    # the entrypoints are there, the calls are there, and nothing joins them. Off the
    # graph rather than off the plugins this build ships, because the claim is about the
    # map (rule 24).
    launch: frozenset[str] = frozenset()
    for held in languages.read(store):
        launch |= load_rules(held).cli_launches
    if launch:
        marks = " OR ".join(["c.callee_expr LIKE ?"] * len(launch))
        params = tuple(f"%.{m}" for m in sorted(launch))
        # Resolve against the *routine's* module and file, not the entrypoint's: a
        # script declared in pyproject.toml records pyproject.toml as its file, and
        # that file has no imports to resolve the app object through.
        for e in store.query(
            f"""SELECT DISTINCT e.id, rt.module AS module, rt.file AS file, c.callee_expr
                  FROM entrypoints e
                  JOIN routines rt ON rt.id = e.routine_id
                  JOIN calls c ON c.caller_id = e.routine_id
                 WHERE e.parent_id IS NULL AND e.grp = '' AND ({marks})""",
            params,
        ):
            var = e["callee_expr"].rsplit(".", 1)[0]
            found = r.resolve(e["module"], var, e["file"])
            if found:
                ep_updates.append((found, e["id"]))
                stats.launches_linked += 1

    # Console scripts name the root app of the tree.
    #
    # **Two fields, where this used to be a LIKE and a `rsplit`.** It selected on
    # `evidence LIKE '%[project.scripts]%'` and then recovered the target with
    # `evidence.rsplit("= ", 1)[-1]` -- parsing a sentence written for a person to get
    # back a value that was in hand when the sentence was built, out of the one string
    # `web/waysin.py` renders verbatim (rule 30). `declared` says which rows these are
    # and `target_expr` carries `mensores.cli:app` as itself.
    #
    # `target_expr <> ''` is not redundant with `declared`: a Cargo `[[bin]]` and a
    # `package.json` `bin` are declared too, and neither names a Python app object.
    for e in store.query(
        "SELECT id, module, target_expr FROM entrypoints"
        " WHERE declared = 1 AND target_expr <> ''"
    ):
        target = str(e["target_expr"]).strip()
        mod, _, attr = target.partition(":")
        found = r.resolve(mod, attr or "app")
        if found:
            ep_updates.append((found, e["id"]))
            stats.scripts_linked += 1

    with store.batch():
        store.conn.executemany(
            "UPDATE cli_mounts SET child_id = ?, parent_id = ? WHERE rowid = ?",
            mount_updates,
        )
        store.conn.executemany(
            "UPDATE entrypoints SET parent_id = ? WHERE id = ?", ep_updates
        )
        store.conn.executemany(
            "UPDATE entrypoints SET routine_id = ? WHERE id = ?", routine_updates
        )

    # Report the state, not the delta. These counters were incremented only for rows
    # this run happened to change, so a warm re-analysis -- where every command was
    # already attached -- announced "0 commands" over a map holding 149 of them.
    # A statistic that reads as a collapsed command tree is worse than none.
    # Attached is not found, and the two must be counted over the *same* population or
    # the pair is worse than either alone. A command reaches an app object only when
    # there is one, and argparse builds its parser inside a function -- so
    # `p = ArgumentParser()` is never a module-level app and its subcommands have no
    # parent to hang from. They are extracted correctly and rendered correctly; only
    # this counter could not see them, and it read "0 commands" over a CLI holding
    # eight. That is the same collapsed-tree misreading the note above was written to
    # prevent, and it cost this session its first finding, which was wrong.
    #
    # Console-script declarations are excluded from both: `mensores = "...:app"` is the
    # executable, not one of its commands, and counting it inflates the total by one
    # per entry point.
    counted = (
        "FROM entrypoints"
        " WHERE kind = 'CLI' AND declared = 0"
    )
    row = store.query(
        f"SELECT COUNT(*), SUM(parent_id IS NOT NULL) {counted}"
    )[0]
    stats.commands_found = row[0]
    stats.commands_attached = row[1] or 0
    stats.scripts_linked = store.query(
        "SELECT COUNT(*) FROM entrypoints"
        " WHERE parent_id IS NOT NULL AND declared = 1"
    )[0][0]
    return stats


def _resolve_routine(store: Store, r: _AppResolver, module: str, file: str,
                     expr: str) -> str | None:
    """Find the routine an expression names: local first, then whatever was imported."""
    name = expr.rsplit(".", 1)[-1]
    # **A qualified target is matched on the whole name, and never on its last segment.**
    #
    # The fallback at the foot of this function takes a bare name that is unique in the
    # map, which is a fair bet in a Python program of five thousand routines and an
    # accident in a C++ one of 262,879. Unreal's `Runtime` proved it: 55 of 4,369 bound
    # ways in landed on the wrong routine, `UAISense_Blueprint.OnUpdate` on the only
    # `OnUpdate` in the map — in `VirtualTextureScalability.cpp`, a file with nothing to do
    # with it. Rule 5, at a scale that had never been put to it (rule 98).
    #
    # So a target that names a scope is resolved by that name or not at all. Tried before
    # the module lookup because it is the stronger claim: an exact qualname is the thing
    # itself, where a module-and-name pair is two halves that happen to agree.
    if "." in expr:
        exact = store.query(
            "SELECT id FROM routines WHERE qualname = ? LIMIT 2", (expr,))
        if len(exact) == 1:
            return str(exact[0]["id"])
        # **And nothing else, for a qualified target.** The two fallbacks below both match
        # on the last segment — map-wide, and within one module — and both are the same
        # bare-name bet one scope apart. Unreal showed each of them wrong in turn: first 55
        # ways in landing on an unrelated file, then 14 landing on a *different class in
        # the same header*, where a pure-virtual `ITypedElementObjectInterface.GetObject`
        # took the body of `TTypedElement.GetObject` beside it. A wrapper with the same
        # method name is the commonest thing in that file, not a coincidence worth trading
        # on. An import may still place it, so that path is tried; otherwise unbound, and
        # `declared` keeps the honest half — this way in exists, and this map cannot say
        # where it lands.
        return _by_import(store, r, module, file, expr, name)
    row = store.query(
        "SELECT id FROM routines WHERE module = ? AND name = ? LIMIT 1", (module, name)
    )
    if row:
        return str(row[0]["id"])
    found = _by_import(store, r, module, file, expr, name)
    if found:
        return found
    row = store.query("SELECT id FROM routines WHERE name = ? LIMIT 2", (name,))
    return str(row[0]["id"]) if len(row) == 1 else None


def _by_import(store: Store, r: _AppResolver, module: str, file: str,
               expr: str, name: str) -> str | None:
    """Whatever the file imported under the target's first segment, if anything.

    One function because both branches above need it and neither may have its own copy
    (rule 51). A language with no import table — which is every language whose reader does
    not fill one — gets `None` here, which is the right answer rather than an empty one.
    """
    entry = r.imports.get(file, {}).get(expr.split(".")[0])
    if not entry:
        return None
    mod, iname, is_from = entry
    abs_mod = _absolute(mod, module, module in r.packages)
    lookup = abs_mod if is_from and iname == expr.split(".")[0] else f"{abs_mod}.{iname}"
    for candidate in (lookup, abs_mod):
        row = store.query(
            "SELECT id FROM routines WHERE module = ? AND name = ? LIMIT 1",
            (candidate, name))
        if row:
            return str(row[0]["id"])
    return None


#: How many commands a node of the command-tree diagram draws; the rest are *+N more*, and
#: the complete tree is listed beneath it. Here, beside the reach it is chosen by.
DRAWN_COMMANDS = 6


def command_tree(store: Store, app_id: str, depth: int = 0,
                 seen: set[str] | None = None) -> dict:
    """The tree under one CLI application: its commands and its mounted sub-apps."""
    seen = seen if seen is not None else set()
    if app_id in seen or depth > 8:
        return {}
    seen.add(app_id)

    row = store.query("SELECT * FROM cli_apps WHERE id = ?", (app_id,))
    if not row:
        return {}
    app = row[0]

    commands = []
    callback = None
    for c in store.query(
        "SELECT name, routine_id, module, evidence FROM entrypoints WHERE parent_id = ?"
        " AND declared = 0 ORDER BY name, module, routine_id",
        (app_id,),
    ):
        item = {"name": c["name"], "routine_id": c["routine_id"], "module": c["module"]}
        # `@app.callback` is the application's own preamble, not one of its commands.
        if c["evidence"].endswith(".callback"):
            callback = item
        else:
            commands.append(item)

    # **Which commands the diagram draws is decided by reach** where it cannot draw them
    # all (BACKLOG 3): the six that lead to most of the program, then by name. Measured only
    # where there is a choice to make, because each is a walk of the call graph.
    if len(commands) > DRAWN_COMMANDS:
        for item in commands:
            rid = item["routine_id"]
            item["reach"] = len(store.reachable_from(rid)) if rid else 0

    children = []
    for m in store.query(
        # **Ordered, and it was not** (rule 66). A mount had no order at all, so the
        # sub-applications came back in rowid order — which is the order the process pool
        # happened to finish files in, and so a different order every run. It is not
        # cosmetic either: `command_tree_diagram` draws the first six commands of each
        # node and counts the rest as *+N more*, so an undefended order decides **which
        # commands appear in the picture**.
        "SELECT child_id, name FROM cli_mounts"
        " WHERE parent_id = ? AND child_id IS NOT NULL AND child_id != ?"
        " ORDER BY name, child_id",
        (app_id, app_id),
    ):
        sub = command_tree(store, m["child_id"], depth + 1, seen)
        if sub:
            sub["mounted_as"] = m["name"]
            children.append(sub)

    return {
        "id": app_id, "var": app["var"], "module": app["module"],
        "title": app["title"], "commands": commands, "callback": callback,
        "children": children,
    }
