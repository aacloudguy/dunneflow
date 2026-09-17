"""Which definition a Python call expression meant.

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

**Moved here from `resolve/calls.py` unchanged in substance**, and what changed is what
it no longer does. It does not decide what a call touching a boundary means (rule 2, and
the driver's), it does not write to the store, and it does not count -- it answers one row
at a time with an `Edge` or a `NoEdge` and the driver does the rest. Three things are new:

* **It sees only Python.** The index is built over `routines WHERE lang = 'python'` and
  over the classes and imports of Python files, so a routine in another language cannot
  win a bare name here. On a single-language map that is the same index it always built.
* **`self` and `cls` come from the manifest.** `plugins/python/plugin.json` has declared
  `receiver_words` since the day it was written and nothing read it -- a declared value
  with no symptom when it is wrong (rule 35). It is read here.
* **The builtins come from `detectors/python.yaml`.** They were `dir(builtins)`, which is
  a fact about the machine doing the analysing rather than about Python, in a value that
  decides what a call means and that no fingerprint hashed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ...detectors import load_rules
from ...ingest import PLUGINS
from ...schema import Confidence
from ...store import Store
from ..contract import CallRow, Decision, Edge, NoEdge

LANG = "python"


def _receiver_words() -> frozenset[str]:
    """`self`, `cls` -- the words that mean *the thing this method was called on*.

    Off the manifest rather than spelled here, because the manifest already declares them
    and a second copy is a second answer (rule 51). A plugin that declares none gets none,
    which is the honest reading for a language that has no such word.
    """
    plugin = PLUGINS.get(LANG)
    return frozenset(plugin.manifest.receiver_words) if plugin is not None else frozenset()


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
    """Every Python definition in the map, indexed three ways.

    **Filtered to this language, and that is the one substantive change from v1.**
    `routines` carries `lang` (written by `ingest.stamp_lang`), so the filter is direct;
    `classes` and `imports` do not, so they join through `files`. Without it a TypeScript
    routine called `render` would compete for a Python bare call to `render()` and could
    win it outright -- rule 5's defect with a language boundary added to it.
    """
    ix = _Index(
        by_module_name=defaultdict(list), by_name=defaultdict(list),
        by_class_method=defaultdict(list),
    )
    for r in store.query(
        "SELECT id, name, module, class_name, file, is_nested FROM routines"
        " WHERE lang = ?", (LANG,)
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

    for c in store.query(
        "SELECT c.name, c.bases FROM classes c JOIN files f ON f.path = c.file"
        " WHERE f.lang = ?", (LANG,)
    ):
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
    for r in store.query(
        "SELECT i.file, i.module, i.name, i.alias, i.is_from FROM imports i"
        " JOIN files f ON f.path = i.file WHERE f.lang = ?", (LANG,)
    ):
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


def resolve(store: Store, lang: str, rows: Sequence[CallRow]) -> Iterator[Decision]:
    """One decision per row, in the order the rows were given.

    `lang` is accepted and not read: the signature is the seam's, and this resolver is
    registered for exactly one language. A resolver that served several would branch on
    it; pretending the parameter is not there would make the table's type a lie.
    """
    ix = _build_index(store)
    imports = _import_maps(store)
    builtins_ = load_rules(LANG).builtins
    receivers = _receiver_words()

    for row in rows:
        expr = row.callee_expr
        caller_id = row.caller_id
        caller_module, caller_class = ix.caller_info.get(caller_id, ("", None))
        caller_is_pkg = caller_module in ix.packages
        alias_map = imports.get(row.file, {})

        parts = expr.split(".")
        last = parts[-1]
        target: str | None = None
        conf = Confidence.INFERRED
        inherited = False
        suppressed = False

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
                        # routines happen to share the name. No rivals are counted --
                        # the import has already settled it.
                        yield NoEdge(candidates=0, suppressed=True)
                        continue
            if not target and last not in builtins_:
                target = _pick(ix.by_name.get(last, []), caller_id)
            elif not target:
                suppressed = True

        elif parts[0] in receivers and len(parts) == 2:
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
                        inherited = True
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
            yield Edge(target, conf, inherited=inherited)
        else:
            # An edge lost to ambiguity is not the same as a call that leaves the
            # program. Recording the candidate count makes a missing connection
            # visible instead of invisible -- which is the whole point when the
            # program under study may itself be broken.
            yield NoEdge(
                candidates=_candidates(ix.by_name.get(last, []), caller_id),
                suppressed=suppressed,
            )
