"""One file in, one `FileFacts` out — the entry point `ingest._IN_PROCESS` names.

Assembles the five phases and nothing else. Every decision lives in the module that owns it;
what is here is the order they run in and the one thing none of them can do alone, which is
say what the file could *not* be read as.

## Entrypoints are read off declarations, not only definitions

This is the one place the reader looks at something that is not a routine, and it is not an
inconsistency. `UFUNCTION(BlueprintCallable) void Fire(int);` in a header declares a way in
**from Blueprint**, and the body that implements it is usually in another file — so a rule
matching only routines would find a Blueprint-callable entrypoint exactly when its author
happened to write the body inline. `Entrypoint.routine_id` is `str | None` for this shape;
it is filled where the body is in this file and left empty where it is not, which is an
honest *we know this way in exists and not where it lands* rather than a way in nobody
records.

## `RESIDUE` is a deliverable

The list at the foot of this module is what this reader cannot see, and it is written to be
read by somebody deciding whether to trust a number. A reader whose limits are stated can be
believed about what it does say; one whose limits are not is a reader nobody can weigh
(rule 1, and design rule 1).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ...detectors import RuleSet, load_rules
from ...schema import (
    Entrypoint,
    EntrypointKind,
    FileFacts,
    Routine,
    entrypoint_id,
    hash_source,
    stored_path,
)
from . import calls as calls_mod
from . import control as control_mod
from . import literals as literals_mod
from . import names
from . import routines as routines_mod
from . import scopes as scopes_mod
from .ctx import Ctx
from .lexer import mask
from .preprocessor import scan
from .scopes import Scope
from .tokens import tokenize

LANG = "cpp"

# What this reader cannot see. Stated here because this is the file somebody opens to find
# out whether a number can be trusted.
RESIDUE = (
    "no types and no overload resolution — three overloads of one name are one written "
    "name, every call is external, and no `callee_id` is ever set",
    "no macro expansion — what a macro *generates* is invisible, including a "
    "framework's `GENERATED_BODY()`-style boilerplate and any scope a macro opens",
    "no `#include` following — a call into another header is external by construction",
    "no preprocessor evaluation beyond a literal `#if 0`; every other branch is read as "
    "live on both arms, and a name defined in two of them is kept as two identities",
    "a declaration with no body is not a routine, so a pure interface contributes none",
    "no template instantiation identity — every instantiation folds to one definition, and "
    "an explicit specialisation is indistinguishable from re-opening the primary template",
    "an STL algorithm is a call and not a loop, so a rate inside `std::transform` is not a "
    "control point where the same rate written as a range-`for` is",
    "`NetworkCall.timeout`, `.retries`, `.tls` and `.headers` are structurally always "
    "empty — C++ has no keyword arguments for them to be read from",
    "no trigraphs and no digraph normalisation (removed from the language in C++17)",
    "internal-linkage detection is a syntactic judgement, so a `static` helper in an "
    "unusual nesting can fail to be scoped to its file",
    "a construction is recognised only where the type is one the boundary rules name — "
    "`TYPE name(args);` is otherwise indistinguishable from a variable declaration",
)


def extract_file(path: Path, root: Path, src: str | None = None) -> FileFacts:
    """Read one C++ file.

    `src` is the already-normalised source when the host has it (`SOURCE_TEXT`), which is
    what keeps the hash this reader sees identical to the hash the host computed.
    """
    # Relative to the analysed root, POSIX-spelled, exactly as the Python reader does it —
    # rule 93, and the `ValueError` arm is recorded rather than swallowed because a quiet
    # fallback to an absolute path is the defect rule 60 was minted from, reintroduced with
    # no symptom.
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
        # A file whose nesting outruns the interpreter. Recorded as an unreadable file
        # rather than taking the whole run down: `ingest` must never fail on a broken
        # program, and a deeply nested generated header is a real thing.
        facts.errors.append(f"RecursionError: {exc}")
    return facts


def _read(facts: FileFacts, rel: str, text: str) -> None:
    masked = mask(text)
    pre = scan(masked)
    toks = tokenize(pre.code, masked)
    tree = scopes_mod.build(toks)
    ctx = Ctx(path=rel, module=facts.module, masked=masked, pre=pre, toks=toks, root=tree)

    # `load_rules` answers three ways and every one of them is deliberate: *declared*,
    # *declared none*, and *refused by name*. It is not wrapped, because a build shipping
    # no `detectors/cpp.yaml` is a packaging defect and an empty `RuleSet` in its place is
    # a reader that quietly finds no boundary, no way in and no CLI — rule 49 exactly, in
    # the one place it would look like a program that has none.
    rules = load_rules(LANG)

    rs, structures, classes, constants = routines_mod.read(ctx)
    facts.routines = rs
    facts.structures = structures
    facts.classes = classes
    facts.constants = constants
    facts.imports = list(pre.includes)
    facts.constants.extend(pre.defines)

    owners = {r_scope.open_tok: r for r_scope, r in _pair(ctx, rs)}

    site_list, boundaries = calls_mod.read(ctx, rules, owners)
    facts.calls = site_list
    facts.boundaries = boundaries

    points, arms = control_mod.read(ctx, owners)
    facts.control = points
    facts.control_arms = arms

    module_scope = literals_mod.module_routine(ctx)
    lits, dropped = literals_mod.read(ctx, owners, module_scope)
    facts.literals = lits
    facts.literals_dropped = dropped
    if literals_mod.module_scope_used(ctx, owners):
        facts.module_scope = module_scope

    facts.entrypoints = _entrypoints(ctx, rules, rs)


def _pair(ctx: Ctx, rs: list[Routine]) -> Iterator[tuple[Scope, Routine]]:
    """Match each routine back to the scope that produced it, in declaration order.

    `routines.read` walks the tree in the same order, so zipping the function scopes with
    the routines is exact rather than a lookup by name — which would collide on every
    overload set in the corpus.
    """
    fn_scopes = [s for s in scopes_mod.walk(ctx.root)
                 if s.kind is scopes_mod.ScopeKind.FUNCTION]
    return zip(fn_scopes, rs, strict=False)


def _entrypoints(ctx: Ctx, rules: RuleSet, rs: list[Routine]) -> list[Entrypoint]:
    """Ways in: `main` and its siblings, and anything a rule recognises by annotation.

    The annotation half reads **declarations as well as definitions** — see the module
    docstring. A declaration is a `;`-terminated run, so it never reaches the scope tree and
    has to be asked for here.
    """
    out: list[Entrypoint] = []
    by_qualname = {r.qualname: r for r in rs}

    for r in rs:
        if r.name in rules.entry_names and not r.is_method:
            out.append(Entrypoint(
                id=entrypoint_id(ctx.path, r.qualname, "main"),
                kind=EntrypointKind.MAIN,
                name=r.name,
                routine_id=r.id,
                module=ctx.module,
                evidence=f"{r.name}() at {ctx.path}:{r.line_start}",
                declared=False,
            ))

    for decorators, qualname, _line in _annotated(ctx):
        for rule in rules.entrypoints:
            if not any(rule.matches_decorator(d) for d in decorators):
                continue
            target = by_qualname.get(qualname)
            out.append(Entrypoint(
                id=entrypoint_id(ctx.path, qualname, rule.kind.value),
                kind=rule.kind,
                name=qualname.rsplit(".", 1)[-1],
                routine_id=target.id if target is not None else None,
                module=ctx.module,
                evidence=rule.evidence or ", ".join(decorators),
                target_expr=qualname,
                declared=True,
            ))
            break
    return out


def _annotated(ctx: Ctx) -> Iterator[tuple[list[str], str, int]]:
    """Every annotated declarator in the file — declared or defined — with its decorators.

    Declarations come from the `;`-terminated runs inside records and namespaces;
    definitions come from the scope tree. Both are yielded, and a definition that is also
    declared elsewhere in this file simply appears once per place it is written, which the
    caller deduplicates by qualname.
    """
    seen: set[str] = set()
    for scope in scopes_mod.walk(ctx.root):
        if scope.kind is scopes_mod.ScopeKind.FUNCTION:
            decs = routines_mod._decorators(scope.header)
            qual = names.join(scope.qual_prefix(), scope.name)
            if decs and qual not in seen:
                seen.add(qual)
                line = ctx.line(scope.header[0].start) if scope.header else 1
                yield decs, qual, line
            continue
        if scope.kind not in (scopes_mod.ScopeKind.FILE, scopes_mod.ScopeKind.RECORD,
                              scopes_mod.ScopeKind.NAMESPACE):
            continue
        for run in routines_mod._direct_statements(ctx, scope):
            span = scopes_mod.declarator_span(run)
            if span is None:
                continue
            decs = routines_mod._decorators(run)
            if not decs:
                continue
            qual = names.join(scope.qual_prefix(), span[2])
            if qual in seen:
                continue
            seen.add(qual)
            first = run[0]
            yield decs, qual, ctx.line(first.start)


def _module(rel: str) -> str:
    """A file's module name: its path without the suffix, dots for separators.

    A stored path is POSIX by rule 93, so this is the same answer on every platform — which
    is what lets a Windows build and a macOS build read each other's maps.
    """
    stem = rel.rsplit(".", 1)[0] if "." in rel.rsplit("/", 1)[-1] else rel
    return stem.replace("/", ".")

