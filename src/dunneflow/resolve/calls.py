"""Turning call expressions into edges.

A call site knows only what it was spelled as -- `save`, `self.commit`,
`utils.load_config`. Making that an edge means deciding which definition it meant.

Python cannot always answer that: a name can be rebound, a method dispatched
dynamically, a module imported at runtime. So every edge carries how much to trust it:

    CERTAIN  -- the target was pinned by an import, the enclosing module, or the
                enclosing class. Wrong only if something rebinds the name at runtime.
    INFERRED -- exactly one routine in the whole program has that name, so it is
                very probably the target, but nothing proves it.

Anything with no match at all is marked external and dropped from the graph, which is
usually correct: it is a standard-library or third-party call, and those are recorded
as boundaries when they matter.
"""

from __future__ import annotations

import builtins
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..schema import Confidence
from ..store import Store

# A bare call to `list(...)` is the builtin, even in a program that happens to define
# a routine called `list`. Falling back to name matching here manufactured 261 false
# edges in the first real target, all of them to the same unlucky function.
_BUILTINS = frozenset(dir(builtins))


@dataclass(slots=True)
class ResolveStats:
    total: int = 0
    certain: int = 0
    inferred: int = 0
    external: int = 0
    suppressed: int = 0  # matches rejected as implausible rather than merely absent
    ambiguous: int = 0   # edges lost because several definitions shared the name
    inherited: int = 0   # edges recovered by following a base class

    @property
    def resolved(self) -> int:
        return self.certain + self.inferred

    def rate(self) -> float:
        return (self.resolved / self.total * 100) if self.total else 0.0


@dataclass(slots=True)
class _Index:
    by_module_name: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    by_name: dict[str, list[str]] = field(default_factory=dict)
    by_class_method: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    modules: set[str] = field(default_factory=set)
    packages: set[str] = field(default_factory=set)
    roots: set[str] = field(default_factory=set)
    bases_of: dict[str, list[str]] = field(default_factory=dict)
    caller_info: dict[str, tuple[str, str | None]] = field(default_factory=dict)


def _build_index(store: Store) -> _Index:
    ix = _Index(
        by_module_name=defaultdict(list), by_name=defaultdict(list),
        by_class_method=defaultdict(list),
    )
    for r in store.query(
        "SELECT id, name, module, class_name, file, is_nested FROM routines"
    ):
        rid, name, mod, cls = r["id"], r["name"], r["module"], r["class_name"]
        ix.caller_info[rid] = (mod, cls)
        if name == "<module>":
            continue
        ix.by_module_name[(mod, name)].append(rid)
        ix.by_name[name].append(rid)
        if cls:
            ix.by_class_method[(cls, name)].append(rid)
        ix.modules.add(mod)
        if mod:
            ix.roots.add(mod.split(".")[0])
        if Path(r["file"]).name == "__init__.py":
            ix.packages.add(mod)

    for c in store.query("SELECT name, bases FROM classes"):
        # Several classes can share a short name; the union of their bases is a
        # superset, which is the right bias here -- a wrong base only widens the
        # search, while a missing one loses the edge entirely.
        existing = ix.bases_of.setdefault(c["name"], [])
        for b in json.loads(c["bases"]):
            short = b.rsplit(".", 1)[-1]
            if short not in existing:
                existing.append(short)
    return ix


def _method_through_bases(ix: _Index, cls: str, method: str, caller_id: str,
                          depth: int = 0, seen: frozenset[str] = frozenset()) -> str | None:
    """Find a method on a class or anything it inherits from.

    A call to `self.thing()` where `thing` lives on a base class is extremely common,
    and without walking the inheritance chain it resolves to nothing -- silently
    dropping the edge rather than reporting it.
    """
    if depth > 6 or cls in seen:
        return None
    hit = _pick(ix.by_class_method.get((cls, method), []), caller_id)
    if hit:
        return hit
    for base in ix.bases_of.get(cls, []):
        found = _method_through_bases(ix, base, method, caller_id, depth + 1, seen | {cls})
        if found:
            return found
    return None


def _import_maps(store: Store) -> dict[str, dict[str, tuple[str, str, bool]]]:
    """alias -> (module, name, is_from), per file."""
    maps: dict[str, dict[str, tuple[str, str, bool]]] = defaultdict(dict)
    for r in store.query("SELECT file, module, name, alias, is_from FROM imports"):
        maps[r["file"]][r["alias"]] = (r["module"], r["name"], bool(r["is_from"]))
    return maps


def _absolute(mod: str, caller_module: str, caller_is_pkg: bool) -> str:
    """Resolve a relative import spelling to an absolute module path."""
    if not mod.startswith("."):
        return mod
    dots = len(mod) - len(mod.lstrip("."))
    rest = mod[dots:]
    parts = caller_module.split(".") if caller_module else []
    # Inside a package's __init__, one dot means the package itself.
    up = dots - 1 if caller_is_pkg else dots
    base = parts[: len(parts) - up] if up <= len(parts) else []
    return ".".join([*base, rest]) if rest else ".".join(base)


def _pick(ids: list[str], caller_id: str) -> str | None:
    """A unique match, ignoring self-recursion. Ambiguity resolves to nothing."""
    candidates = [i for i in ids if i != caller_id]
    return candidates[0] if len(candidates) == 1 else None


def _candidates(ids: list[str], caller_id: str) -> int:
    """How many definitions competed. More than one is why an edge went missing."""
    return len([i for i in ids if i != caller_id])


def resolve_calls(store: Store) -> ResolveStats:
    """Resolve every call site in the store, in place."""
    ix = _build_index(store)
    imports = _import_maps(store)
    stats = ResolveStats()
    updates: list[tuple[str | None, str, int, int, int]] = []

    rows = store.query(
        "SELECT rowid, file, caller_id, callee_expr, at_boundary FROM calls"
    )
    for row in rows:
        stats.total += 1
        rowid = row["rowid"]
        expr: str = row["callee_expr"]
        caller_id: str = row["caller_id"]
        caller_module, caller_class = ix.caller_info.get(caller_id, ("", None))
        caller_is_pkg = caller_module in ix.packages
        alias_map = imports.get(row["file"], {})

        parts = expr.split(".")
        last = parts[-1]
        target: str | None = None
        conf = Confidence.INFERRED

        # This call was already identified as touching the outside world -- a database
        # cursor, a file handle, a subprocess. `conn.execute(...)` is sqlite3, not a
        # local routine that happens to be called `execute`. Resolving it inward
        # invented 919 edges on the first real target and made an unrelated function
        # look like the most depended-upon code in the program.
        if row["at_boundary"]:
            stats.external += 1
            stats.suppressed += 1
            updates.append((None, Confidence.INFERRED.value, 1, 0, rowid))
            continue

        if len(parts) == 1:
            # Bare name: the enclosing module first, then whatever was imported.
            target = _pick(ix.by_module_name.get((caller_module, last), []), caller_id)
            if target:
                conf = Confidence.CERTAIN
            elif last in alias_map:
                mod, name, is_from = alias_map[last]
                if is_from:
                    abs_mod = _absolute(mod, caller_module, caller_is_pkg)
                    target = _pick(ix.by_module_name.get((abs_mod, name), []), caller_id)
                    if target:
                        conf = Confidence.CERTAIN
                    elif abs_mod and abs_mod.split(".")[0] not in ix.roots:
                        # Imported from outside this program: `from dataclasses import
                        # field` means `field(...)` is dataclasses', however many local
                        # routines happen to share the name.
                        stats.external += 1
                        stats.suppressed += 1
                        updates.append((None, Confidence.INFERRED.value, 1, 0, rowid))
                        continue
            if not target and last not in _BUILTINS:
                target = _pick(ix.by_name.get(last, []), caller_id)
            elif not target:
                stats.suppressed += 1

        elif parts[0] in {"self", "cls"} and len(parts) == 2:
            # A method on the enclosing class is as certain as Python gets, and one
            # inherited from a base is nearly so.
            if caller_class:
                target = _pick(ix.by_class_method.get((caller_class, last), []), caller_id)
                if target:
                    conf = Confidence.CERTAIN
                else:
                    target = _method_through_bases(ix, caller_class, last, caller_id)
                    if target:
                        conf = Confidence.CERTAIN
                        stats.inherited += 1
            if not target:
                target = _pick(ix.by_name.get(last, []), caller_id)

        else:
            prefix = ".".join(parts[:-1])
            head = parts[0]
            if prefix in ix.modules:
                target = _pick(ix.by_module_name.get((prefix, last), []), caller_id)
                if target:
                    conf = Confidence.CERTAIN
            if not target and head in alias_map:
                mod, name, is_from = alias_map[head]
                abs_mod = _absolute(mod, caller_module, caller_is_pkg)
                if is_from:
                    # `from pkg import mod` then `mod.fn`, or `from pkg import Cls`
                    # then `Cls.method`.
                    cand = f"{abs_mod}.{name}" if abs_mod else name
                    target = _pick(ix.by_module_name.get((cand, last), []), caller_id)
                    if target:
                        conf = Confidence.CERTAIN
                    else:
                        target = _pick(ix.by_class_method.get((name, last), []), caller_id)
                else:
                    joined = ".".join([abs_mod, *parts[1:-1]]) if len(parts) > 2 else abs_mod
                    target = _pick(ix.by_module_name.get((joined, last), []), caller_id)
                    if target:
                        conf = Confidence.CERTAIN
            if not target:
                # An attribute call on something local. Name uniqueness is all we have.
                target = _method_through_bases(ix, parts[-2], last, caller_id)
                if not target:
                    target = _pick(ix.by_name.get(last, []), caller_id)

        if target:
            if conf is Confidence.CERTAIN:
                stats.certain += 1
            else:
                stats.inferred += 1
            updates.append((target, conf.value, 0, 0, rowid))
        else:
            # An edge lost to ambiguity is not the same as a call that leaves the
            # program. Recording the candidate count makes a missing connection
            # visible instead of invisible -- which is the whole point when the
            # program under study may itself be broken.
            rival = _candidates(ix.by_name.get(last, []), caller_id)
            if rival > 1:
                stats.ambiguous += 1
            stats.external += 1
            updates.append((None, Confidence.INFERRED.value, 1, rival if rival > 1 else 0,
                            rowid))

    with store.batch():
        store.conn.executemany(
            "UPDATE calls SET callee_id = ?, confidence = ?, external = ?, ambiguous = ?"
            " WHERE rowid = ?",
            updates,
        )
    return stats
