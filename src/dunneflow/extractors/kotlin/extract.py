"""One Kotlin file in, one `FileFacts` out — what `ingest._IN_PROCESS` names.

## The package is the namespace, and the file is the identity

Kotlin states its own `package` at the top, so a qualname is what the author wrote rather
than something derived from where the file sits — which is the opposite of Python, where the
path *is* the module. The **file** is still in every id, because two files in one package can
each declare a top-level `fun render()` and both are real.

## `RESIDUE` is a deliverable

The list below is what this reader cannot see, written for somebody deciding whether to trust
a number. The third entry is the one to read first: in idiomatic Kotlin the functional
collection operators are the house style, so *a rate hidden in a `forEach` is invisible* costs
more here than the same sentence costs in C++.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ...detectors import RuleSet, load_rules
from ...schema import (
    Entrypoint,
    EntrypointKind,
    FileFacts,
    ImportRec,
    Routine,
    hash_source,
    make_id,
    stored_path,
)
from . import calls as calls_mod
from . import control as control_mod
from . import decls as decls_mod
from . import literals as literals_mod
from . import names
from . import scopes as scopes_mod
from .ctx import Ctx
from .lexer import mask
from .scopes import ScopeKind, annotations_of, walk
from .tokens import TokenKind, tokenize

LANG = "kotlin"

RESIDUE = (
    "no types and no resolution — an extension function is chosen by static receiver type "
    "and `apply`/`let`/`run`/`with` change what `this` means, so every call is external and "
    "no `callee_id` is ever set",
    "a constructor invocation is spelled exactly like a function call, so "
    "`CallSite.is_construction` is False for every Kotlin call",
    "**a collection operator is a call and not a loop** — a per-element rate inside "
    "`items.forEach { … }`, `map` or `filter` is not a control point, and in idiomatic "
    "Kotlin that is the house style rather than the exception",
    "a lambda is not a routine, so the calls inside one are attributed to the named "
    "function enclosing it and two lambdas in one function share a flat call list",
    "a declaration with no body is not a routine, so an `interface` member and an "
    "`abstract fun` contribute none — the implementations are ordinary functions and are",
    "an expression body's **extent** is found by a stated heuristic (`scopes._expression_end`) "
    "because Kotlin has no statement terminator; what it can get wrong is where a body ends, "
    "never whether the routine exists, its name or its parameters",
    "only `const val` is a constant — every other `val` is an immutable binding, including "
    "a local one, and admitting them would report the internal computation this tool exists "
    "not to report",
    "a `typealias` is not recorded, and neither is a delegated property's `by` provider",
)


def extract_file(path: Path, root: Path, src: str | None = None) -> FileFacts:
    outside = ""
    try:
        rel = stored_path(path.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = stored_path(path)
        outside = f"outside the analysed root {root}: stored absolute"

    try:
        text = src if src is not None else path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return FileFacts(path=rel, lang=LANG, module=_module(rel), content_hash="",
                         errors=[f"{type(exc).__name__}: {exc}"])

    facts = FileFacts(path=rel, lang=LANG, module=_module(rel),
                      content_hash=hash_source(text))
    if outside:
        facts.errors.append(outside)
    try:
        _read(facts, rel, text)
    except RecursionError as exc:
        facts.errors.append(f"RecursionError: {exc}")
    return facts


def _read(facts: FileFacts, rel: str, text: str) -> None:
    masked = mask(text)
    toks = tokenize(masked.code_only(), masked)
    package, imports = _package_and_imports(toks, masked)
    tree = scopes_mod.build(toks, masked)
    ctx = Ctx(path=rel, module=facts.module, package=package, masked=masked, toks=toks,
              root=tree)

    rules = load_rules(LANG)

    rs, structures, classes, constants = decls_mod.read(ctx)
    facts.routines = rs
    facts.structures = structures
    facts.classes = classes
    facts.constants = constants
    facts.imports = imports

    owners = {s.body_start: r for s, r in _pair(ctx, rs)}

    facts.calls, facts.boundaries = calls_mod.read(ctx, rules, owners)
    facts.control, facts.control_arms = control_mod.read(ctx, owners)

    module_scope = literals_mod.module_routine(ctx)
    facts.literals, facts.literals_dropped = literals_mod.read(ctx, owners, module_scope)
    if literals_mod.module_scope_used(ctx, owners):
        facts.module_scope = module_scope

    facts.entrypoints = _entrypoints(ctx, rules, rs)


def _pair(ctx: Ctx, rs: list[Routine]) -> Iterator[tuple[scopes_mod.Scope, Routine]]:
    fn_scopes = [s for s in walk(ctx.root) if s.kind is ScopeKind.FUNCTION]
    return zip(fn_scopes, rs, strict=False)


def _package_and_imports(toks: list, masked: object) -> tuple[str, list[ImportRec]]:
    """`package a.b.c` and every `import`, both as written.

    An `import x.y.Z as W` records the alias; nothing is resolved (clause 4), so what a rule
    matches is the prefix the author typed.
    """
    package = ""
    imports: list[ImportRec] = []
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t.kind is not TokenKind.IDENT:
            i += 1
            continue
        if t.text == "package" and not package:
            name, j = names.fold_declarator(toks, i + 1)
            package = name
            i = j
            continue
        if t.text == "import":
            name, j = names.fold_declarator(toks, i + 1)
            alias = ""
            star = j < n and toks[j].kind is TokenKind.PUNCT and toks[j].text == "*"
            if star:
                j += 1
            if j + 1 < n and toks[j].kind is TokenKind.IDENT and toks[j].text == "as":
                alias = toks[j + 1].text
                j += 2
            if name:
                imports.append(ImportRec(
                    module=name + (".*" if star else ""), name="", alias=alias,
                    is_from=False, line=masked.line_at(t.start)))  # type: ignore[attr-defined]
            i = max(j, i + 1)
            continue
        if t.text in ("fun", "class", "object", "interface"):
            break                    # past the header; nothing below declares a package
        i += 1
    return package, imports


def _entrypoints(ctx: Ctx, rules: RuleSet, rs: list[Routine]) -> list[Entrypoint]:
    """`main`, and anything a rule recognises by annotation.

    An annotated **type** counts as well as an annotated function: `@AndroidEntryPoint class
    DeckPicker : Activity` is how an Android application declares a way in, and the thing
    being registered is the class rather than any one method on it.
    """
    out: list[Entrypoint] = []
    for r in rs:
        if r.name in rules.entry_names and not r.is_method:
            out.append(Entrypoint(
                id=make_id(ctx.path, r.qualname, "main"),
                kind=EntrypointKind.MAIN, name=r.name, routine_id=r.id,
                module=ctx.module,
                evidence=f"{r.name}() at {ctx.path}:{r.line_start}", declared=False))

    by_qualname = {r.qualname: r for r in rs}
    for scope in walk(ctx.root):
        if scope.kind is ScopeKind.FILE:
            continue
        decs = annotations_of(scope.header)
        if not decs:
            continue
        qual = names.join(names.join(ctx.package, scope.qual_prefix()),
                          scope.name if scope.kind is ScopeKind.FUNCTION else "")
        for rule in rules.entrypoints:
            if not any(rule.matches_decorator(d) for d in decs):
                continue
            target = by_qualname.get(qual)
            out.append(Entrypoint(
                id=make_id(ctx.path, qual, rule.kind.value),
                kind=rule.kind, name=qual.rsplit(".", 1)[-1],
                routine_id=target.id if target is not None else None,
                module=ctx.module, evidence=rule.evidence or ", ".join(decs),
                target_expr=qual, declared=True))
            break
    return out


def _module(rel: str) -> str:
    """A file's module name: its path without the suffix, dots for separators.

    **The path and not the `package`**, deliberately. `module` is what the rest of the tool
    groups a file by and two files in one package are two modules; the package is in the
    *qualname*, which is where a reader looks for it. A stored path is POSIX (rule 93), so
    this is the same answer on every platform.
    """
    stem = rel.rsplit(".", 1)[0] if "." in rel.rsplit("/", 1)[-1] else rel
    return stem.replace("/", ".")
