"""Which definition a Python call expression meant.

A call site knows only what it was spelled as -- `save`, `self.commit`,
`utils.load_config`. Making that an edge means deciding which definition it meant.

Python cannot always answer that: a name can be rebound, a method dispatched
dynamically, a module imported at runtime. So every edge carries how much to trust it:

    CERTAIN  -- the target was pinned by an import, the enclosing module, or the
                enclosing class. Wrong only if something rebinds the name at runtime.
    INFERRED -- exactly one routine in the whole program has that name, so it is
                very probably the target, but nothing proves it.
                **Never where the name is a method of Python's own types**
                (`python.yaml`'s `builtin_methods`): the program having one routine
                called `append` says nothing about what `rows.append(x)` calls.

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
    caller_qual: dict[str, str] = field(default_factory=dict)
    # A nested routine's id -> the qualname of the scope that encloses it. A closure is
    # reachable from that scope and from what it encloses, and from nowhere else.
    enclosing: dict[str, str] = field(default_factory=dict)
    # This program's classes, so that `Foo(...)` can find the thing it builds.
    class_by_module: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    class_by_name: dict[str, list[str]] = field(default_factory=dict)
    class_kind: dict[str, str] = field(default_factory=dict)
    class_short: dict[str, str] = field(default_factory=dict)
    init_of: dict[str, str] = field(default_factory=dict)


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
        by_class_method=defaultdict(list), class_by_module=defaultdict(list),
        class_by_name=defaultdict(list),
    )
    for r in store.query(
        "SELECT id, name, qualname, module, class_name, file, is_nested FROM routines"
        " WHERE lang = ?", (LANG,)
    ):
        rid, name, mod, cls = r["id"], r["name"], r["module"], r["class_name"]
        ix.caller_info[rid] = (mod, cls)
        ix.caller_qual[rid] = r["qualname"]
        if name == "<module>":
            continue
        ix.by_module_name[(mod, name)].append(rid)
        if r["is_nested"]:
            # **A closure is not a name the program can call** (BACKLOG 24, rule 10). It
            # stays in its module's index, filtered by `_visible` to the scope that
            # encloses it, and out of the program-wide one entirely: `render_maps`'s local
            # `say` matched `web.analysis.run.say` through it, an edge into another
            # module's closure that no execution could take.
            ix.enclosing[rid] = r["qualname"].rsplit(".", 1)[0]
        else:
            ix.by_name[name].append(rid)
        if name == "__init__" and cls:
            ix.init_of[r["qualname"].rsplit(".", 1)[0]] = rid
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

    # The classes again, for what a call to one builds. A dataclass, an enum or a named
    # tuple has a constructor its decorator or base writes, so it is never walked to a base
    # class's `__init__` -- `StructureKind` says which a class is.
    for c in store.query(
        "SELECT c.name, c.qualname, c.module, COALESCE(s.kind, 'CLASS') AS kind"
        "  FROM classes c JOIN files f ON f.path = c.file"
        "  LEFT JOIN structures s ON s.file = c.file AND s.name = c.name"
        "       AND s.module = c.module AND s.line = c.line"
        " WHERE f.lang = ? ORDER BY c.qualname, c.file", (LANG,)
    ):
        q = c["qualname"]
        if q in ix.class_short:
            continue
        ix.class_by_module[(c["module"], c["name"])].append(q)
        ix.class_by_name[c["name"]].append(q)
        ix.class_kind[q] = c["kind"]
        ix.class_short[q] = c["name"]
    return ix


def _visible(ix: _Index, ids: list[str], caller_id: str) -> list[str]:
    """`ids` less the closures the caller is not inside.

    A nested routine is reachable from the scope that encloses it and from anything that
    scope encloses -- a sibling closure calling it, or itself. From anywhere else in the
    module a bare call to its name is a call to something else, and matching it here would
    be a CERTAIN edge no execution could take.
    """
    if not ix.enclosing:
        return ids
    caller = ix.caller_qual.get(caller_id, "")
    out = []
    for i in ids:
        scope = ix.enclosing.get(i)
        if scope is None or caller == scope or caller.startswith(scope + "."):
            out.append(i)
    return out


def _in_module(ix: _Index, key: tuple[str, str], caller_id: str, *,
               bare: bool = False) -> str | None:
    """The one routine `key` -- (module, name) -- names that this caller can reach.

    `bare`: the call spelled the name alone, which in Python never reaches a method, so the
    module's methods are not candidates. A name spelled *with* a module path keeps them --
    `store.query(...)` on a local `store` finds `Store.query` that way, 180 of DunneFlow's
    own edges, and the first fix for BACKLOG 29 lost all of them by dropping methods there
    too. Only a caller that is not itself a method can find itself here.
    """
    ids = _visible(ix, ix.by_module_name.get(key, []), caller_id)
    if bare:
        ids = [i for i in ids if not _is_method(ix, i)]
    own = None if _is_method(ix, caller_id) else _itself(ids, caller_id)
    return own or _pick(ids, caller_id)


def _is_method(ix: _Index, rid: str) -> bool:
    """Defined in a class body, and so reachable by no bare or module-qualified name.

    The module index holds methods beside functions, so a bare `walk()` in a module that
    also defines `Tree.walk` had two candidates -- and when one was the caller, `_pick` chose
    the method: a function calling itself was recorded as calling a method nobody named
    (found with BACKLOG 29). A closure inside a method carries the class too and is not one.
    """
    return bool(ix.caller_info.get(rid, ("", None))[1]) and rid not in ix.enclosing


def _itself(ids: list[str], caller_id: str) -> str | None:
    """The caller, when the only routine a pinned lookup finds is the caller: recursion.

    **BACKLOG 29.** `_pick` drops the caller from every candidate list, which is right for a
    name matched across the program -- `self.repo.save()` inside `save` is someone else's
    `save` -- and wrong where the lookup is already pinned to the caller's own module or
    class. There, finding only yourself is the answer, and `_pick` made it no answer: the
    call fell through to the program-wide index and met strangers. On DunneFlow's own map
    that bound `cpp.literals._all` to `kotlin.literals._all`, left `cpp.calls._walk` LOST
    between two rivals, and counted ~35 more recursive sites EXTERNAL (rules 1, 5 and 26).
    A method spelling its own name bare is not itself: a bare lookup has already dropped
    methods, because a bare name never reaches one, and `_in_module` asks this only of a
    caller that is not a method.
    """
    return caller_id if ids == [caller_id] else None


def _constructor(ix: _Index, cls: str, conf: Confidence, caller_id: str) -> Decision:
    """What a call building `cls`, one of this program's classes, is a call to.

    Its own `__init__` first, then -- for a plain class only -- one it inherits from a base
    this program defines, which is rule 11 for constructors. Failing both, the class has no
    constructor routine here, and the honest answer is the class itself: not external,
    because it is in this program, and no edge, because there is no routine to point at
    (BACKLOG 14). It was EXTERNAL once per call site until 2026-10-02.
    """
    own = ix.init_of.get(cls)
    if own and own != caller_id:
        return Edge(own, conf)
    if ix.class_kind.get(cls) == "CLASS":
        for base in ix.bases_of.get(ix.class_short[cls], []):
            found = _method_through_bases(ix, base, "__init__", caller_id)
            if found:
                return Edge(found, conf, inherited=True)
    return NoEdge(constructs=cls)


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


def _one(ids: list[str]) -> str | None:
    """The single entry, or nothing. Two classes sharing a name are no answer."""
    return ids[0] if len(ids) == 1 else None


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
    # Names a call may be resolved by evidence but never by being the only routine so
    # called: `append`, `get`, `update` (rule 5; `python.yaml`'s `builtin_methods`).
    own_types_ = load_rules(LANG).builtin_methods
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

        if row.bound_locally:
            # A name this routine binds itself -- a parameter, an assignment. What it calls
            # is whatever value it holds, and matching the name against the program would
            # be guessing (BACKLOG 24, rule 1). No rivals are counted: the binding has
            # already settled that none of them is meant.
            yield NoEdge(candidates=0, suppressed=True, reason="bound")
            continue

        # One of this program's classes the call names, and how sure that is. Looked for
        # only where no routine answered, because a class and a routine never share a
        # module-level name and the routine lookups are the older, measured path.
        cls: str | None = None
        cls_conf = Confidence.CERTAIN

        if len(parts) == 1:
            # Bare name: the enclosing module first, then whatever was imported.
            target = _in_module(ix, (caller_module, last), caller_id, bare=True)
            if target:
                conf = Confidence.CERTAIN
            else:
                cls = _one(ix.class_by_module.get((caller_module, last), []))
            if not target and not cls and last in alias_map:
                mod, name, is_from = alias_map[last]
                if is_from:
                    abs_mod = _absolute(mod, caller_module, caller_is_pkg)
                    target = _in_module(ix, (abs_mod, name), caller_id, bare=True)
                    if target:
                        conf = Confidence.CERTAIN
                    else:
                        cls = _one(ix.class_by_module.get((abs_mod, name), []))
                    if not target and not cls and abs_mod \
                            and abs_mod.split(".")[0] not in ix.roots:
                        # Imported from outside this program: `from dataclasses import
                        # field` means `field(...)` is dataclasses', however many local
                        # routines happen to share the name. No rivals are counted --
                        # the import has already settled it.
                        yield NoEdge(candidates=0, suppressed=True, reason="outside",
                                     frontier=f"{abs_mod}.{name}")
                        continue
            if not target and not cls and last not in builtins_:
                target = _pick(ix.by_name.get(last, []), caller_id)
                if not target:
                    cls = _one(ix.class_by_name.get(last, []))
                    cls_conf = Confidence.INFERRED
            elif not target and not cls:
                suppressed = True

        elif parts[0] in receivers and len(parts) == 2:
            # A method on the enclosing class is as certain as Python gets, and one
            # inherited from a base is nearly so.
            if caller_class:
                own = ix.by_class_method.get((caller_class, last), [])
                target = _itself(own, caller_id) or _pick(own, caller_id)
                if target:
                    conf = Confidence.CERTAIN
                else:
                    target = _method_through_bases(ix, caller_class, last, caller_id)
                    if target:
                        conf = Confidence.CERTAIN
                        inherited = True
            if not target and last not in own_types_:
                target = _pick(ix.by_name.get(last, []), caller_id)
            elif not target:
                suppressed = True

        else:
            prefix = ".".join(parts[:-1])
            head = parts[0]
            # The module paths this spelling could be naming, for a class if no routine.
            homes = [prefix]
            if prefix in ix.modules:
                target = _in_module(ix, (prefix, last), caller_id)
                if target:
                    conf = Confidence.CERTAIN
            if not target and head in alias_map:
                mod, name, is_from = alias_map[head]
                abs_mod = _absolute(mod, caller_module, caller_is_pkg)
                if is_from:
                    # `from pkg import mod` then `mod.fn`, or `from pkg import Cls`
                    # then `Cls.method`.
                    cand = f"{abs_mod}.{name}" if abs_mod else name
                    homes.append(cand)
                    target = _in_module(ix, (cand, last), caller_id)
                    if target:
                        conf = Confidence.CERTAIN
                    else:
                        target = _pick(ix.by_class_method.get((name, last), []), caller_id)
                else:
                    joined = ".".join([abs_mod, *parts[1:-1]]) if len(parts) > 2 else abs_mod
                    homes.append(joined)
                    target = _in_module(ix, (joined, last), caller_id)
                    if target:
                        conf = Confidence.CERTAIN
            if not target:
                cls = next((c for c in (_one(ix.class_by_module.get((h, last), []))
                                        for h in homes) if c), None)
            if not target and not cls:
                # An attribute call on something local. Name uniqueness is all we have.
                target = _method_through_bases(ix, parts[-2], last, caller_id)
                if not target and last not in own_types_:
                    target = _pick(ix.by_name.get(last, []), caller_id)
                elif not target:
                    # `rows.append(x)`: the language has a method of that name, so the
                    # program having exactly one is no argument at all. Untyped, said.
                    suppressed = True

        if target:
            yield Edge(target, conf, inherited=inherited)
        elif cls:
            yield _constructor(ix, cls, cls_conf, caller_id)
        else:
            # **Where it stops, and why** (BACKLOG 36): a builtin and a module imported from
            # outside go outside, a call on a value whose type this resolver cannot see is
            # untyped, and a bare name nothing defines is a path it could not follow.
            frontier, reason = "", ""
            head = parts[0]
            if len(parts) == 1 and last in builtins_:
                frontier, reason = last, "outside"
            elif len(parts) > 1 and head in alias_map:
                mod, name, is_from = alias_map[head]
                abs_mod = _absolute(mod, caller_module, caller_is_pkg)
                home = f"{abs_mod}.{name}" if is_from and abs_mod else (abs_mod or name)
                if home and home.split(".")[0] not in ix.roots:
                    frontier, reason = ".".join([home, *parts[1:]]), "outside"
            if not reason:
                reason = "untyped" if len(parts) > 1 else "unfollowed"
            # An edge lost to ambiguity is not the same as a call that leaves the
            # program. Recording the candidate count makes a missing connection
            # visible instead of invisible -- which is the whole point when the
            # program under study may itself be broken.
            yield NoEdge(
                # A name ruled out on purpose had no rivals to count: the lone `append`
                # was never a candidate, and saying "1" would send a reader to look at it.
                candidates=0 if suppressed else _candidates(ix.by_name.get(last, []),
                                                            caller_id),
                suppressed=suppressed, frontier=frontier, reason=reason,
            )
