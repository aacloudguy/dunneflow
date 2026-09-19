"""Python fact extraction.

Reads one source file and reports what moves through it: the routines, their typed
signatures, what they call, where they touch the outside world, the shapes they pass
around, and the comments that explain why.

Deliberately *not* reported: local variables, arithmetic, and anything else that stays
inside a routine. Those are the parts the reader was explicit about not wanting, and
leaving them out is most of what makes the output legible.

**Control flow is the one amendment, and it is narrow.** This line read "local variables,
arithmetic, control flow" until 2026-09-07, and the rule behind it has not changed: a loop
that increments a counter is still the internal computation nobody asked for. What is
recorded is a `ControlPoint` -- **a span, and nothing more**: no variable, no operator, no
value. What a loop *does* is reached by joining the tables that already exist, so a loop
holding a network call is `line BETWEEN line_start AND line_end` rather than a new fact.
A loop is a subject only where something moves inside it, and on Mensores that is 250 of
1,950. See `schema.ControlPoint`.

Uses the standard library only -- `ast` for structure, `tokenize` for comments. No
third-party parser, nothing to install, and it cannot fall behind the language.
"""

from __future__ import annotations

import ast
import io
import tokenize
from collections.abc import Sequence
from pathlib import Path

from ...detectors import RuleSet, load_rules, mine_annotations
from ...ingest.literals import in_bounds
from ...schema import (
    ArmKind,
    BoundaryHit,
    CallArg,
    CallSite,
    ClassDef_,
    CliApp,
    CliMount,
    Comment,
    Confidence,
    Constant,
    ControlArm,
    ControlKind,
    ControlPoint,
    DataStructure,
    Entrypoint,
    EntrypointKind,
    Field_,
    FileFacts,
    ImportRec,
    LiteralKind,
    NetworkCall,
    Param,
    Routine,
    StringLiteral,
    StructureKind,
    call_site_id,
    control_point_id,
    definition_id,
    entrypoint_id,
    hash_source,
    make_id,
    stored_path,
)

MODULE_SCOPE = "<module>"

_STRUCTURE_BASES = {
    "BaseModel": StructureKind.PYDANTIC,
    "TypedDict": StructureKind.TYPEDDICT,
    "NamedTuple": StructureKind.NAMEDTUPLE,
    "Enum": StructureKind.ENUM,
    "IntEnum": StructureKind.ENUM,
    "StrEnum": StructureKind.ENUM,
    "Flag": StructureKind.ENUM,
}


# How a guard clause leaves. Four ways out, and the difference between them is the whole
# reason `ControlPoint.exits` is recorded rather than read back off the header: `if not x:
# return` and `if not x: raise` are the same sentence and opposite facts. 3,937 of
# Mensores' 6,293 branches are one of these -- 62.6% of this program's decisions are
# refusals, which is the largest single shape in it.
_EXITS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def dotted_name(node: ast.AST) -> str:
    """Render an attribute/name chain as it reads in source: `a.b.c`.

    A call in the middle of the chain is folded to the thing being called, so
    `Path(p).read_text()` reads as `Path.read_text`. Without this, the extremely
    common habit of calling a method straight off a constructor would be invisible
    to every rule -- and reading a file that way is one of the most common boundary
    touches there is.

    Returns "" for anything with no name at its root (a subscript, a literal), because
    those cannot be matched against rules with any confidence.
    """
    parts: list[str] = []
    cur = node
    for _ in range(32):  # a chain deeper than this is pathological
        if isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        elif isinstance(cur, ast.Call):
            cur = cur.func
        else:
            break
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _literal(node: ast.AST | None) -> str | None:
    """Source text for a default or argument, recorded in full.

    Not abbreviated. This value reaches the store, so anything dropped here is lost
    for good rather than merely unshown, and a default argument cut off at eighty
    characters is no longer the default argument. Shortening for legibility is the
    renderer's business, and only where the full value is reachable beside it.
    """
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def _annotation(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return None


def collect_comments(src: str) -> dict[int, str]:
    """Every comment in the file, by line number.

    Tolerates files that do not tokenize cleanly -- a syntactically valid file can
    still upset the tokenizer, and losing comments is better than losing the file.

    `#:` is Sphinx's doc-comment marker, and its colon is syntax rather than text. Only
    the colon that *touches* the hash is: `#: Keychain service name` is a documented
    constant and its text begins at "Keychain", while `# :mod:`x`` is an ordinary comment
    whose text legitimately begins with a reStructuredText role. Stripping a leading
    colon wherever one appeared would have eaten that role -- the same shortening at
    ingest as the tag-stripper that ate `<role>` in rule 12, and the same discipline as
    rule 5: a marker only counts at an edge, so the test is position, not presence.

    1,698 of Mensores' comments carry the marker, across 117 files, and 323 constants
    took their WHY through it. Left alone they read as ": Keychain service name", and a
    blank `#:` line read as a bare colon.
    """
    out: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type != tokenize.COMMENT:
                continue
            text = tok.string.lstrip("#")
            if text.startswith(":"):
                text = text[1:]
            out[tok.start[0]] = text.strip()
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return out


class _Extractor(ast.NodeVisitor):
    """Walks one module, maintaining the scope stack so facts land on the right owner."""

    def __init__(self, path: str, module: str, src: str, rules: RuleSet,
                 docstrings: frozenset[int] = frozenset()) -> None:
        self.path = path
        self.module = module
        self.rules = rules
        self.comments = collect_comments(src)
        self.lines = src.splitlines()
        # Kept because an argument is recorded **as written** rather than re-rendered,
        # and `ast.unparse` is a re-rendering: it normalises spacing, drops line breaks,
        # and would put a different string on screen from the one a reader will go
        # looking for in the file.
        self.src = src
        # How many times this caller has already called this exact expression. The
        # discriminator in `call_site_id`, and the only one available that is not a
        # position.
        self._call_ordinal: dict[tuple[str, str], int] = {}
        # Documentation is never code. Code-shaped detectors must not read it -- a
        # docstring that opens "Insert candidate into capture_queue..." is a sentence
        # about a statement, not a statement.
        self._docstrings = docstrings

        self.routines: list[Routine] = []
        self.calls: list[CallSite] = []
        self.boundaries: list[BoundaryHit] = []
        self.structures: list[DataStructure] = []
        self.entrypoints: list[Entrypoint] = []
        self.imports: list[ImportRec] = []
        self.classes: list[ClassDef_] = []
        self.cli_apps: list[CliApp] = []
        self.cli_mounts: list[CliMount] = []
        # argparse builds its command table across two statements: a subparser is
        # created and named, then a handler is bound to it. Tracking the variable
        # between them is what connects "serve" to the function that implements it.
        self._argparse_var: dict[str, str] = {}
        self._argparse_ep: dict[str, Entrypoint] = {}
        self.network: list[NetworkCall] = []
        self._awaited: set[int] = set()
        self.constants: list[Constant] = []
        # Every string this file spells out, in the order it was read. The order is a
        # contract and not an accident: `ingest.literals` keeps one naming act per file
        # per line, so an interpolated string has to arrive before the plain parts it was
        # assembled from or `f"{root}/g.json"` loses to the bare `"/g.json"` inside it.
        self.literals: list[StringLiteral] = []
        self.literals_dropped = 0
        self._module_claimed = False
        # Module-level `name -> string`, or None where the name is not one value.
        self._module_strings: dict[str, str | None] = {}
        # A broken program may define one qualified name twice. Both keep an identity
        # of their own rather than merging, so the collision can be reported.
        self._seen_qualnames: dict[str, int] = {}

        self.control: list[ControlPoint] = []
        self.control_arms: list[ControlArm] = []
        # How many points of this exact writing this routine already holds -- the
        # discriminator in `control_point_id`, and the only one available that is not a
        # position. Two identical `for line in lines:` loops in one routine are two spans.
        self._control_ordinal: dict[tuple[str, str, str], int] = {}
        # Control nesting, which is **not** `Routine.is_nested` -- that counts enclosing
        # *functions*, and the two disagree on every closure. Reset per routine, because a
        # function defined inside a loop starts its own body at depth 0.
        self._depth = 0
        # `elif` is an `If` in the `orelse` of an `If`, so a ladder of seven arms arrives as
        # six nested nodes. The head records the whole ladder and puts its tails here; each
        # tail is then walked for its *contents* at the **same** depth, because an `elif` arm
        # is a sibling of the `if` arm and not a level below it. Keyed by `id()`, which is
        # safe only because the tree is alive for the whole walk.
        self._ladder_tails: set[int] = set()

        self._scope: list[Routine] = []
        self._class: list[str] = []
        self._class_bases: dict[str, list[str]] = {}
        self._module_routine: Routine | None = None
        self._has_main_guard = False
        self._main_guard_calls: list[str] = []

    # -- scope ------------------------------------------------------------- #

    def _identity(self, qualname: str) -> str:
        """A stable id for a qualified name in this file, disambiguating a real duplicate.

        The counter is per file because the identity is (`schema.definition_id`, rule 106):
        two files cannot reach the same ordinal for the same name, so nothing has to be
        counted across them.
        """
        n = self._seen_qualnames.get(qualname, 0)
        self._seen_qualnames[qualname] = n + 1
        return definition_id(self.path, qualname, n + 1)

    def module_scope(self) -> Routine:
        """The routine module-level code belongs to, **prepared and not claimed**.

        Module-level work matters: a `os.getenv` at import time is exactly the
        "fed inputs at startup" the reader cares about, and it belongs to something.

        Preparing it is separate from claiming it because **the module scope is a routine
        only where something belongs to it**, and that used to be true by accident rather
        than by rule: whichever fact asked first did the minting, so a file with nothing at
        module level got no such routine because nothing had asked. It stopped being true
        the moment a *string* asked -- `_literal` has to name an owner for every string it
        reports, and a string is not yet a fact. Measured: 65 of Society's 628 files gained
        a `<module>` routine owning nothing at all, a 1.3% inflation of every routine count
        in the map, decided by whether a string cleared a bound that exists to save wire.
        Rule 96.
        """
        if self._module_routine is None:
            self._module_routine = Routine(
                id=definition_id(self.path, f"{self.module}.{MODULE_SCOPE}"),
                name=MODULE_SCOPE,
                qualname=f"{self.module}.{MODULE_SCOPE}",
                module=self.module,
                file=self.path,
                line_start=1,
                line_end=len(self.lines) or 1,
                docstring="Module-level code: runs at import, before anything is called.",
                body_hash=hash_source("\n".join(self.lines)),
            )
        return self._module_routine

    def _owner(self) -> Routine:
        """Whichever routine encloses, claiming the module scope where none does.

        Every caller of this is recording a fact, so the claim is the record of it.
        `_literal` is the one thing that asks who owns something **without** knowing yet
        whether there is anything to own, and it asks `_owner_id` instead.
        """
        if self._scope:
            return self._scope[-1]
        scope = self.module_scope()
        if not self._module_claimed:
            self._module_claimed = True
            self.routines.append(scope)
        return scope

    def _owner_id(self) -> str:
        """Who a string belongs to, **without** deciding that it belongs to anybody.

        The id is derived from names and needs no row to exist (`make_id`), so it can be
        named before there is anything to hang on it. `ingest.literals.judge` claims the
        module scope if and when one of these strings turns out to be a fact.
        """
        return self._scope[-1].id if self._scope else self.module_scope().id

    # -- module-level names ------------------------------------------------- #

    def collect_module_strings(self, body: list[ast.stmt]) -> None:
        """Module-level names bound to a plain string, for resolving f-strings.

        `CREATE TABLE {_TABLE} (...)` in an f-string left the table unnamed, so
        Mensores' migration 0028 created `work_items` and the database map went on
        reading 40 tables at both points in time -- a table arrived and nothing said
        so. The value was never missing: rule 19 records `_TABLE = "work_items"` as a
        constant six lines above, in the same module.

        This is a **lexical binding in one file**, not a name match across the program,
        so rule 5 does not arise -- nothing here searches for `_TABLE` anywhere else.
        Precision is bought by refusing everything ambiguous:

        * a name bound more than once at module level resolves to nothing, because
          which binding reached the f-string is a question about control flow and this
          tool does not answer those (rule 10's argument, one scope down);
        * only a bare `Name` substitutes -- an attribute, call or subscript is a value
          this pass cannot claim to know;
        * only a plain string constant, and only where the placeholder carries no
          conversion and no format spec, because `{x:>10}` is not a substitution.

        Run as its own pass rather than folded into `collect_module_names`, which
        walks *after* the visitor and whose ordering claims comments depend on.
        """
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for attr in ("body", "orelse", "finalbody"):
                    self.collect_module_strings(getattr(stmt, attr, []) or [])
                for handler in getattr(stmt, "handlers", []) or []:
                    self.collect_module_strings(handler.body)
                continue
            value: ast.expr | None
            if isinstance(stmt, ast.Assign):
                targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                targets = [stmt.target.id]
                value = stmt.value
            else:
                continue
            text = (value.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str)
                    else None)
            for name in targets:
                # Seen before, however bound: the name is no longer one value.
                self._module_strings[name] = (
                    None if name in self._module_strings else text
                )

    def _interpolated(self, node: ast.FormattedValue) -> str | None:
        """The string a placeholder stands for, or None when we cannot say."""
        if node.conversion not in (-1, None) or node.format_spec is not None:
            return None
        if not isinstance(node.value, ast.Name):
            return None
        return self._module_strings.get(node.value.id)

    def collect_module_names(self, body: list[ast.stmt]) -> None:
        """Every value the module names at import, as a constant or as a type alias.

        `visit_Assign` caught only CLI app objects and `_class_fields` caught only
        class bodies, so module level produced nothing at all: `JTBD_OPENERS` was
        declared, read six times, and absent from the map. 3,072 of these on Mensores.

        Walked from the statement list rather than through the visitor, because module
        level is exactly "runs at import" and that is a property of position, not of a
        scope stack. A `try: import x except ImportError:` at module level runs; a
        function body does not, and is never descended into.
        """
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(stmt, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for attr in ("body", "orelse", "finalbody"):
                    self.collect_module_names(getattr(stmt, attr, []) or [])
                for handler in getattr(stmt, "handlers", []) or []:
                    self.collect_module_names(handler.body)
                continue
            annotation: str | None = None
            value: ast.expr | None = None
            if isinstance(stmt, ast.Assign):
                targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                targets = [stmt.target.id]
                annotation = _annotation(stmt.annotation)
                value = stmt.value
            else:
                continue
            if value is None:
                continue    # `X: int` declares a name and binds nothing
            for name in targets:
                # A dunder is packaging metadata, not something the program named.
                if name.startswith("__") and name.endswith("__"):
                    continue
                if self._record_type_alias(name, value, stmt):
                    continue
                self.constants.append(Constant(
                    name=name,
                    value=_literal(value) or "",
                    line=stmt.lineno,
                    type=annotation,
                    is_final=bool(annotation and annotation.split("[")[0].endswith("Final")),
                    comment=self._value_comment(stmt.lineno),
                    private=name.startswith("_"),
                ))

    def _record_type_alias(self, name: str, value: ast.expr, stmt: ast.stmt) -> bool:
        """`QueueState = Literal[...]` is an enumerated vocabulary, not a constant.

        `StructureKind.TYPE_ALIAS` was declared in the schema from the start and nothing
        produced one, because only a `class` statement became a structure. The admission
        rule lives in `detectors/python.yaml`: the subscript base or the called factory
        must be named there, or `X = SOME_DICT["key"]` reads as a type. A bare `X = Y`
        is not admitted at all -- it cannot be told from `DEFAULT = OTHER_DEFAULT`.
        """
        target = ""
        members: list[Field_] = []
        if isinstance(value, ast.Subscript):
            base = dotted_name(value.value)
            if not self.rules.is_type_expression(base):
                return False
            target = _literal(value) or ""
            if base.rsplit(".", 1)[-1] == "Literal":
                items = (value.slice.elts if isinstance(value.slice, ast.Tuple)
                         else [value.slice])
                members = [
                    Field_(name=_literal(item) or "", type=None)
                    for item in items
                ]
        elif isinstance(value, ast.Call) and self.rules.is_alias_factory(
            dotted_name(value.func)
        ):
            target = _literal(value) or ""
        else:
            return False

        self.structures.append(DataStructure(
            id=definition_id(self.path, f"{self.module}.{name}"),
            name=name,
            kind=StructureKind.TYPE_ALIAS,
            module=self.module,
            file=self.path,
            line=stmt.lineno,
            fields=members,
            docstring=self._value_comment(stmt.lineno),
            bases=[target] if target else [],
        ))
        return True

    def _value_comment(self, line: int) -> str | None:
        """The WHY beside a named value: the comment on its line, else the block above.

        Both are already owned by the module scope, and both are shown here too. A
        comment belongs against the thing it explains, and a constant is a thing.
        """
        inline = self.comments.get(line)
        if inline:
            return inline
        block = [c.text for c in self._leading_comments(line)]
        return " ".join(block) if block else None

    def claim_orphan_comments(self) -> None:
        """Give every comment nobody claimed to the module's import-time scope.

        Comments were collected per function: the block above a definition, and
        everything inside its line span. Anything else was dropped on the floor --
        **9,659 of Mensores' 18,208 comments, 53%** -- because the synthetic `<module>`
        routine is created on demand by `_owner()` and was never handed any.

        That is not a readability loss, it is a governance one. Comments are the only
        source of the WHY layer, and the unclaimed half carried 2,270 governance
        annotations across 438 distinct ids -- 76 of which appeared nowhere else in the
        graph, and 75 of those documented in the corpus. Real, traceable, and invisible.

        Two kinds are unclaimed, and both belong here for the same reason. A comment at
        module level explains code that runs at import. A comment inside a class body
        but outside every method (1,040 of them) explains code that *also* runs at
        import -- a class body is executed, not declared -- and `_owner()` already
        assigns boundaries, calls and SQL found there to this same routine. Putting
        comments anywhere else would invent a second ownership model for one fact type.

        Called once, after the walk, so "claimed" means claimed by anybody. A comment
        leading a nested definition is legitimately owned by both the inner routine and
        the enclosing one (187 such on Mensores); it is claimed either way and is not
        duplicated here.
        """
        claimed = {c.line for r in self.routines for c in r.comments}
        orphans = sorted(ln for ln in self.comments if ln not in claimed)
        if not orphans:
            return
        owner = self._owner()
        owner.comments.extend(
            Comment(text=self.comments[ln], line=ln, leading=False) for ln in orphans
        )
        for ln in orphans:
            owner.annotations.extend(mine_annotations(self.comments[ln], ln))

    def _body_hash(self, start: int, end: int) -> str:
        """Hash of a routine's own source lines.

        Separate from identity on purpose: this is how a change layer tells "the same
        routine, edited" from "a different routine".
        """
        return hash_source("\n".join(self.lines[start - 1 : end]))

    # -- comments ---------------------------------------------------------- #

    def _leading_comments(self, first_line: int) -> list[Comment]:
        """The contiguous comment block immediately above a definition."""
        out: list[Comment] = []
        line = first_line - 1
        while line > 0 and line in self.comments:
            out.append(Comment(text=self.comments[line], line=line, leading=True))
            line -= 1
        return list(reversed(out))

    def _inline_comments(self, start: int, end: int) -> list[Comment]:
        return [
            Comment(text=t, line=ln, leading=False)
            for ln, t in self.comments.items()
            if start <= ln <= end
        ]

    # -- definitions ------------------------------------------------------- #

    def _params(self, args: ast.arguments) -> list[Param]:
        """The parameters as written, markers included.

        `posonlyargs` was folded into `args` here and recorded as plain `positional`, so
        the `/` separating positional-only parameters was destroyed at ingest -- rule 8,
        in the smallest possible instance: a value shortened before it reaches the store
        is lost for good rather than merely unshown. Nothing had asked for it until the
        hover card began printing the invocation line, and a printed signature that is not
        the one in the file is exactly what rule 13 forbids.

        Neither Mensores nor DunneFlow uses `/` in any of 4,724 definitions between them,
        so this fixes nothing visible today. That is the argument for doing it now rather
        than against: the cost is three lines while nothing depends on the old shape, and
        the alternative is a renderer that is silently wrong on the first codebase that
        does use it. Defaults still pad from the right across both groups, which is how
        `def f(a, b=1, /, c=2)` binds.
        """
        out: list[Param] = []
        positional = list(args.posonlyargs) + list(args.args)
        n_posonly = len(args.posonlyargs)
        pad = len(positional) - len(args.defaults)
        for i, a in enumerate(positional):
            default = _literal(args.defaults[i - pad]) if i >= pad else None
            out.append(Param(a.arg, _annotation(a.annotation), default,
                             "positional_only" if i < n_posonly else "positional"))
        if args.vararg:
            out.append(Param(args.vararg.arg, _annotation(args.vararg.annotation), None, "vararg"))
        for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=False):
            out.append(Param(a.arg, _annotation(a.annotation), _literal(d), "keyword"))
        if args.kwarg:
            out.append(Param(args.kwarg.arg, _annotation(args.kwarg.annotation), None, "kwarg"))
        return out

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        cls = self._class[-1] if self._class else None
        # Nested functions must carry their enclosing scope. Seven distinct closures
        # each called `_close_ladybug`, one per factory function, are seven different
        # routines -- collapsing them to one qualname makes every call to any of them
        # ambiguous, and an ambiguous name resolves to nothing at all.
        enclosing = [r.name for r in self._scope]
        qual_parts = [self.module, *self._class, *enclosing, node.name]
        qualname = ".".join(qual_parts)
        decorators = [d for d in (dotted_name(_strip_call(x)) for x in node.decorator_list) if d]

        first_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        leading = self._leading_comments(first_line)
        end = node.end_lineno or node.lineno
        inline = self._inline_comments(node.lineno, end)
        doc = ast.get_docstring(node)

        annotations = []
        for c in leading + inline:
            annotations.extend(mine_annotations(c.text, c.line))
        if doc:
            annotations.extend(mine_annotations(doc, node.lineno))

        routine = Routine(
            id=self._identity(qualname),
            name=node.name,
            qualname=qualname,
            module=self.module,
            file=self.path,
            line_start=node.lineno,
            line_end=end,
            params=self._params(node.args),
            returns=_annotation(node.returns),
            decorators=decorators,
            docstring=doc,
            comments=leading + inline,
            annotations=annotations,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=cls is not None,
            class_name=cls,
            is_nested=bool(self._scope),
            visibility="private" if node.name.startswith("_") else "public",
            body_hash=self._body_hash(node.lineno, end),
        )
        self.routines.append(routine)
        self._detect_entrypoint(routine, decorators)

        self._scope.append(routine)
        # A function defined inside a loop starts its own body at depth 0: control nesting
        # belongs to a routine, and carrying the enclosing loop's depth into it would say a
        # closure's first `if` is three levels deep because of where it happens to be
        # declared. Saved and restored rather than zeroed, because the walk resumes in the
        # enclosing body afterwards.
        outer_depth, self._depth = self._depth, 0
        try:
            for child in node.body:
                self.visit(child)
        finally:
            self._depth = outer_depth
            self._scope.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [b for b in (dotted_name(x) for x in node.bases) if b]
        decorators = [d for d in (dotted_name(_strip_call(x)) for x in node.decorator_list) if d]

        kind: StructureKind | None = None
        if any(d.rsplit(".", 1)[-1] == "dataclass" for d in decorators):
            kind = StructureKind.DATACLASS
        else:
            for b in bases:
                last = b.rsplit(".", 1)[-1]
                if last in _STRUCTURE_BASES:
                    kind = _STRUCTURE_BASES[last]
                    break

        fields = self._class_fields(node)
        # A class with no declared fields and no data-shape base is behaviour, not a
        # structure. Recording it would bury the shapes that actually move.
        if kind is not None or fields:
            first_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
            doc = ast.get_docstring(node)
            annots = []
            for c in self._leading_comments(first_line):
                annots.extend(mine_annotations(c.text, c.line))
            if doc:
                annots.extend(mine_annotations(doc, node.lineno))
            self.structures.append(DataStructure(
                id=definition_id(self.path,
                                 ".".join([self.module, *self._class, node.name])),
                name=node.name,
                kind=kind or StructureKind.CLASS,
                module=self.module,
                file=self.path,
                line=node.lineno,
                fields=fields,
                docstring=doc,
                bases=bases,
                annotations=annots,
            ))

        self._class_bases[node.name] = bases
        self.classes.append(ClassDef_(
            name=node.name,
            qualname=".".join([self.module, *self._class, node.name]),
            module=self.module, file=self.path, line=node.lineno, bases=bases,
        ))
        self._class.append(node.name)
        for child in node.body:
            self.visit(child)
        self._class.pop()

    def _class_fields(self, node: ast.ClassDef) -> list[Field_]:
        out: list[Field_] = []
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                out.append(Field_(
                    name=stmt.target.id,
                    type=_annotation(stmt.annotation),
                    default=_literal(stmt.value),
                    comment=self.comments.get(stmt.lineno),
                ))
            elif isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and not t.id.startswith("__"):
                        out.append(Field_(
                            name=t.id,
                            type=None,
                            default=_literal(stmt.value),
                            comment=self.comments.get(stmt.lineno),
                        ))
        return out

    def visit_Assign(self, node: ast.Assign) -> None:
        """Catch `app = typer.Typer(...)`: the object a CLI is actually built on."""
        if isinstance(node.value, ast.Call):
            callee = dotted_name(node.value.func)
            if (
                callee.rsplit(".", 1)[-1] == "add_parser"
                and node.value.args
                and isinstance(node.value.args[0], ast.Constant)
                and isinstance(node.value.args[0].value, str)
            ):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self._argparse_var[t.id] = node.value.args[0].value
        if not self._scope and isinstance(node.value, ast.Call):
            factory = dotted_name(node.value.func)
            if self.rules.is_cli_factory(factory):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.cli_apps.append(CliApp(
                            id=make_id("cliapp", self.path, t.id),
                            var=t.id,
                            module=self.module,
                            file=self.path,
                            line=node.lineno,
                            title=_kwarg_str(node.value, "name") or _kwarg_str(node.value, "help")
                            or "",
                            factory=factory,
                        ))
        self.generic_visit(node)

    # -- imports ----------------------------------------------------------- #

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            self.imports.append(ImportRec(
                module=a.name, name=a.name, alias=a.asname or a.name,
                is_from=False, line=node.lineno,
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        if node.level:  # relative import; record the dots so the resolver can rebuild it
            mod = "." * node.level + mod
        for a in node.names:
            self.imports.append(ImportRec(
                module=mod, name=a.name, alias=a.asname or a.name,
                is_from=True, line=node.lineno,
            ))

    # -- the shape a routine takes ------------------------------------------ #
    #
    # A control point is **a span and nothing more**. Nothing here records a variable, an
    # operator or a value: what a loop *does* is reached later by joining `boundaries`,
    # `net_calls`, `sql_ops` and `calls`, every one of which already carries `routine_id`
    # and `line`. That is what keeps `CLAUDE.md`'s founding exclusion narrow -- control
    # flow is not reported as control flow, it is reported as a range that something moves
    # inside of.
    #
    # No control-flow graph and no dominator analysis, deliberately. Those exist to recover
    # structure a `goto` destroyed, and Python source never lost it -- `ast` hands the
    # nesting back exactly as written. Nassi and Shneiderman made the same observation in
    # 1972 and drew structured code as nested boxes with no arrows at all.

    @staticmethod
    def _lines_of(nodes: Sequence[ast.AST]) -> set[int]:
        """Every line these subtrees occupy, decorators and continuations included."""
        out: set[int] = set()
        for n in nodes:
            for sub in ast.walk(n):
                line = getattr(sub, "lineno", None)
                if line is None:
                    continue
                out.update(range(line, (getattr(sub, "end_lineno", None) or line) + 1))
        return out

    @classmethod
    def _once_span(cls, once: ast.AST | None,
                   repeats: Sequence[ast.AST]) -> tuple[int, int]:
        """The lines evaluated once before the first pass, and only where a line can say.

        The iterable's lines **minus** every line a repeated part of the same point also
        occupies, which is `ControlPoint.once_start`'s whole argument: a one-line
        comprehension writes its element and its iterable on the same line, and the
        subtraction empties the range there rather than guessing which of them a boundary
        on that line belongs to (rule 85, and rule 49 for why it empties rather than
        guesses).

        Contiguous by construction, so two ints hold it: a `for`'s body is strictly after
        its iterable and a comprehension's element strictly before it, so what is removed
        is always an end.
        """
        if once is None:
            return (0, 0)
        lines = cls._lines_of([once]) - cls._lines_of(repeats)
        return (min(lines), max(lines)) if lines else (0, 0)

    def _record_control(
        self, node: ast.AST, kind: ControlKind, *, arms: int = 1, exits: str = "",
        header: ast.AST | None = None, word: str = "",
        once: ast.AST | None = None, repeats: Sequence[ast.AST] = (),
    ) -> ControlPoint:
        """One point, then its contents one level deeper.

        The header is the **test or the iterable**, never the body: `for seal in
        spec.seals`, not the forty lines under it. Sliced by `_segment` on byte offsets
        (rule 75) and never `ast.unparse`d, for `call_args`' reason -- what is stored is
        what the reader will go looking for.

        `once` and `repeats` are the two halves of *what does this evaluate once*, and
        only a caller knows which node is which: a `for`'s iterable runs once and its test
        does not exist, a `while`'s test runs every pass and it has no iterable, and a
        comprehension repeats the element written to the left of its first generator.
        Passing both and subtracting here keeps that judgement out of four visitors
        (rule 51).

        Returns the point so the caller can hang its arms off it. Only a caller knows
        what its arms *are*: an `elif` chain has been flattened by then, a `try`'s arms
        are its handlers, and a loop has none unless it has an `else`.
        """
        once_start, once_end = self._once_span(once, repeats)
        start = int(getattr(node, "lineno", 0) or 0)
        # A node with no `end_lineno` collapses to its own first line rather than to 0: a
        # span of `start..0` is empty, and every range join over it would answer "nothing
        # moves in here" -- rule 49's fallback, a plausible value hiding the failure.
        end = int(getattr(node, "end_lineno", None) or start)
        routine_id = self._owner().id
        text = (self._segment(header) or "") if header is not None else ""
        key = (routine_id, kind.value, text)
        ordinal = self._control_ordinal.get(key, 0)
        self._control_ordinal[key] = ordinal + 1
        point = ControlPoint(
            point_id=control_point_id(routine_id, kind.value, text, ordinal),
            routine_id=routine_id,
            kind=kind,
            line_start=start,
            line_end=end,
            depth=self._depth + 1,
            header=text,
            arms=arms,
            exits=exits,
            word=word,
            once_start=once_start,
            once_end=once_end,
        )
        self.control.append(point)
        return point

    def _body_span(self, body: list[ast.stmt]) -> tuple[int, int] | None:
        """The lines one arm's statements occupy, decorators and all.

        Taken over `ast.walk` rather than off the first and last statement, because a
        `def` inside an arm reports the `def` line and its decorators sit above it -- a
        span starting at the `def` would put a decorated nested function's own decorator
        outside the arm that holds it.
        """
        lines = [n.lineno for s in body for n in ast.walk(s) if hasattr(n, "lineno")]
        if not lines:
            return None
        ends = [getattr(n, "end_lineno", None) or n.lineno
                for s in body for n in ast.walk(s) if hasattr(n, "lineno")]
        return min(lines), max(ends)

    def _record_arms(
        self, point: ControlPoint,
        arms: list[tuple[ArmKind, ast.AST | str | None, list[ast.stmt]]],
    ) -> None:
        """The ways through one point, **only where there is more than one.**

        A plain `if`, a `for` with no `else`, a guard: one way through, which is the
        point's own span, and a row repeating it would be a second answer to a settled
        question (rule 41).

        The header is either a node to slice or a string already assembled from slices --
        an `except` clause and a `case` pattern are written in two pieces (`except E as
        exc`, `case P if guard`) and there is no single node covering either.
        """
        if len(arms) < 2:
            return
        for idx, (kind, header, body) in enumerate(arms):
            span = self._body_span(body)
            if span is None:
                continue
            text = header if isinstance(header, str) else (
                (self._segment(header) or "") if header is not None else "")
            self.control_arms.append(ControlArm(
                point_id=point.point_id,
                routine_id=point.routine_id,
                idx=idx,
                kind=kind,
                line_start=span[0],
                line_end=span[1],
                header=text,
            ))

    def _descend(self, node: ast.AST, *, deeper: bool = True) -> None:
        """Walk a control point's children, one level down and back up again."""
        if deeper:
            self._depth += 1
        try:
            self.generic_visit(node)
        finally:
            if deeper:
                self._depth -= 1

    def _visit_loop(self, node: ast.For | ast.AsyncFor | ast.While) -> None:
        # A `while` has a test and a `for` has an iterable, and both are the answer to
        # "what is this looping over" -- the one thing a reader asks of a loop first.
        head = node.iter if isinstance(node, (ast.For, ast.AsyncFor)) else node.test
        # **A `while` evaluates nothing once, and that is why the word is recorded.** Its
        # test runs again on every pass, so `once` stays empty; a `for` runs its iterable
        # before the first pass and never again. The two are one `ControlKind` and the
        # header alone cannot tell them apart (rule 30).
        point = self._record_control(
            node, ControlKind.LOOP, header=head,
            word=("while" if isinstance(node, ast.While)
                  else "async for" if isinstance(node, ast.AsyncFor) else "for"),
            once=None if isinstance(node, ast.While) else head,
            repeats=[*node.body, *node.orelse],
        )
        # `for ... else` runs when the loop was never broken out of, which is a second
        # way through and the one most readers have to look up. 4 of Society's 976 loops
        # have one; a loop without an `else` records no arms at all, because its body is
        # its span. `arms` stays 1 either way -- what a loop is *over* is one thing, and
        # the ways out of it are the rows.
        word = ArmKind.WHILE if isinstance(node, ast.While) else ArmKind.FOR
        self._record_arms(point, [
            (word, head, node.body),
            (ArmKind.ELSE, None, node.orelse),
        ] if node.orelse else [])
        self._descend(node)

    visit_For = _visit_loop
    visit_AsyncFor = _visit_loop
    visit_While = _visit_loop

    def _visit_comprehension(self, node: ast.AST) -> None:
        """A comprehension is a loop that is an expression, and it is where the N+1 hides.

        Counted separately rather than folded into `LOOP` because a reader scanning for
        loops does not see one here, which is exactly why a boundary inside one is worth
        saying out loud: 39 of Mensores' comprehensions reach a boundary.
        """
        gens = getattr(node, "generators", [])
        # **Only the first generator's iterable runs once.** `[f(x) for x in a for y in b]`
        # evaluates `a` before anything and `b` once per item of `a`, so a later
        # generator's iterable repeats exactly as the element does. The element itself is
        # written to the *left* of the iterable, which is why the subtraction has to trim
        # both ends and why a one-line comprehension records nothing.
        repeats: list[ast.AST] = (
            [node.key, node.value] if isinstance(node, ast.DictComp)
            else [node.elt] if isinstance(node, (ast.ListComp, ast.SetComp,
                                                 ast.GeneratorExp))
            else []
        )
        for i, gen in enumerate(gens):
            repeats.extend(gen.ifs)
            if i:
                repeats.append(gen.iter)
        self._record_control(
            node, ControlKind.COMPREHENSION,
            header=gens[0].iter if gens else None,
            once=gens[0].iter if gens else None,
            repeats=repeats,
        )
        self._descend(node)

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_DictComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension

    def _ladder_arms(
        self, node: ast.If, tails: list[ast.If],
    ) -> list[tuple[ArmKind, ast.AST | str | None, list[ast.stmt]]]:
        """A flattened ladder's ways out, in the order they are written.

        The `if` arm carries the same test the point does -- from the same node, so the
        two cannot disagree (rule 13) -- because a ladder has to be readable from its
        arms alone.
        """
        arms: list[tuple[ArmKind, ast.AST | str | None, list[ast.stmt]]] = [
            (ArmKind.IF, node.test, node.body)]
        arms += [(ArmKind.ELIF, t.test, t.body) for t in tails]
        last = tails[-1] if tails else node
        if last.orelse:
            arms.append((ArmKind.ELSE, None, last.orelse))
        return arms

    def _ladder(self, node: ast.If) -> tuple[int, list[ast.If]]:
        """An `if`/`elif`/`else` chain flattened to its ways out.

        `arms` is what a reader counts: 2 for `if`/`else`, 4 for `if`/`elif`/`elif`/`else`,
        1 for a bare `if`. The tree says "2 arms" once per `elif` instead, because each is
        an `If` inside the previous one's `orelse` -- so a seven-way decision reads as six
        two-way ones, which is a picture of the syntax rather than of the decision.
        """
        arms, tails, cur = 1, [], node
        while len(cur.orelse) == 1 and isinstance(cur.orelse[0], ast.If):
            cur = cur.orelse[0]
            tails.append(cur)
            arms += 1
        if cur.orelse:
            arms += 1
        return arms, tails

    def _visit_decision(self, node: ast.If) -> None:
        if id(node) in self._ladder_tails:
            # An `elif` its own head already counted. Its contents still matter, and they
            # are at the head's depth -- an `elif` arm is a sibling of the `if` arm.
            self._ladder_tails.discard(id(node))
            self._descend(node, deeper=False)
            return
        arms, tails = self._ladder(node)
        # A **guard**: one arm, no `else`, and it leaves. Narrowed by how it ends rather
        # than by how it is written, because `if not x: return` and `if not x: raise` are
        # the same sentence and opposite facts -- so `exits` is recorded, never inferred.
        if (arms == 1 and len(node.body) <= 2
                and any(isinstance(s, _EXITS) for s in node.body)):
            last = node.body[-1]
            self._record_control(
                node, ControlKind.GUARD,
                exits=type(last).__name__.lower() if isinstance(last, _EXITS) else "",
                header=node.test, word="if",
            )
            self._descend(node)
            return
        self._ladder_tails.update(id(t) for t in tails)
        point = self._record_control(
            node, ControlKind.DECISION, arms=arms, header=node.test, word="if")
        self._record_arms(point, self._ladder_arms(node, tails))
        self._descend(node)

    def visit_Match(self, node: ast.Match) -> None:
        """`match` is a decision that already knows how many ways out it has.

        Mensores has **none** -- the population is zero and stays named rather than
        dropped (design rule 1), because a lane that silently vanishes cannot be told from
        one that looked and found nothing.
        """
        point = self._record_control(
            node, ControlKind.DECISION, arms=len(node.cases), header=node.subject,
            word="match")
        self._record_arms(point, [
            (ArmKind.CASE, self._case_header(c), c.body) for c in node.cases])
        self._descend(node)

    def _case_header(self, case: ast.match_case) -> str:
        """`case "retry" if seal.kind == "witness"` -- two slices, because it is two nodes.

        `ast.match_case` carries no position of its own, and a guard is a separate node
        from the pattern with the word `if` between them in the source and nowhere in the
        tree. Assembled from two as-written slices rather than `ast.unparse`d, which is
        the same trade `_segment` exists to refuse.
        """
        pattern = self._segment(case.pattern) or ""
        if case.guard is None:
            return pattern
        return f"{pattern} if {self._segment(case.guard) or ''}".strip()

    def visit_Try(self, node: ast.Try) -> None:
        """`try` is a decision about failure, and its arms are its handlers.

        No header: what a `try` is *about* is the block it guards, and quoting forty lines
        as a heading would be a header that is the body (rule 8's shape, one subject over).
        """
        point = self._record_control(node, ControlKind.HANDLER, arms=len(node.handlers),
                                    word="try")
        self._record_arms(point, self._try_arms(node))
        self._descend(node)

    def _try_arms(
        self, node: ast.Try | ast.TryStar,
    ) -> list[tuple[ArmKind, ast.AST | str | None, list[ast.stmt]]]:
        """A `try`'s ways through: the guarded body, each handler, `else`, `finally`.

        The body is an arm here where a loop's body is not, because a `try` genuinely has
        more than one way through it and the reader is asking which of them moves
        something -- 396 of Society's 1,531 handlers recover by moving something, and
        that question cannot be put to the `try` span, which contains both answers.
        """
        arms: list[tuple[ArmKind, ast.AST | str | None, list[ast.stmt]]] = [
            (ArmKind.TRY, None, node.body)]
        arms += [(ArmKind.EXCEPT, self._except_header(h), h.body) for h in node.handlers]
        if node.orelse:
            arms.append((ArmKind.ELSE, None, node.orelse))
        if node.finalbody:
            arms.append((ArmKind.FINALLY, None, node.finalbody))
        return arms

    def _except_header(self, handler: ast.ExceptHandler) -> str:
        """`except TimeoutError as exc` -- the caught type and the name it is bound to.

        Assembled from the type's own slice for `_case_header`'s reason: the bound name
        is an identifier on the `ExceptHandler` and not a node anywhere. A bare `except:`
        catches everything and has nothing to quote, so it says nothing.
        """
        if handler.type is None:
            return ""
        caught = self._segment(handler.type) or ""
        return f"{caught} as {handler.name}" if handler.name else caught

    def visit_TryStar(self, node: ast.TryStar) -> None:
        """`except*` groups, which are a `Try` in every way this fact cares about.

        Its own method rather than `visit_TryStar = visit_Try`: `TryStar` is a separate
        node type and the alias is a signature the checker is right to refuse. Mensores
        has none, and it is handled anyway because an extractor that silently walks past a
        language construct reports a smaller program (rule 15's shape).
        """
        point = self._record_control(node, ControlKind.HANDLER, arms=len(node.handlers),
                                    word="try")
        self._record_arms(point, self._try_arms(node))
        self._descend(node)

    # -- the things that move ---------------------------------------------- #

    def _segment(self, node: ast.AST) -> str | None:
        """The expression exactly as it is written in the file.

        Not `ast.unparse`, which is a re-rendering: it normalises spacing, canonicalises
        quotes and flattens a wrapped argument onto one line. What a caller passes is
        what the reader will go looking for in the source, so it is the source that is
        recorded -- whole, never shortened (rule 8).

        `col_offset` is a byte offset into the UTF-8 encoding of its line rather than a
        character index, so the slice is taken on the encoded bytes. On a line holding
        any non-ASCII character -- a name, a comment, a string -- a character slice is
        silently short, and produces a plausible expression that is not the one written.

        `ast.get_source_segment` does this correctly and re-splits the whole file on
        every call, which over 184k lines and 30k call sites is the file split a hundred
        thousand times. The lines are already here.
        """
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", None)
        col = getattr(node, "col_offset", None)
        end_col = getattr(node, "end_col_offset", None)
        if start is None or end is None or col is None or end_col is None:
            return None
        if start < 1 or end > len(self.lines) or end < start:
            return None
        if start == end:
            return self.lines[start - 1].encode()[col:end_col].decode(errors="replace")
        first = self.lines[start - 1].encode()[col:].decode(errors="replace")
        last = self.lines[end - 1].encode()[:end_col].decode(errors="replace")
        return "\n".join([first, *self.lines[start : end - 1], last])

    def _call_args(self, node: ast.Call) -> list[CallArg]:
        """Every argument of one call, in the order it is written.

        Positional and keyword arguments live in two lists on the node and may interleave
        in the source -- `f(*a, b=1, c)` is legal -- so the order is taken from where each
        one sits, not from which list it came out of. `idx` is that written ordinal,
        because it is the order the reader sees.

        A `*x` or `**x` is recorded and marked. What it passes is not one argument and
        cannot be bound to a parameter by position at all; dropping it would leave a call
        looking as though it passed less than it does.
        """
        pieces: list[tuple[tuple[int, int], str | None, bool, ast.AST]] = []
        for a in node.args:
            splat = isinstance(a, ast.Starred)
            pieces.append(((a.lineno, a.col_offset), None, splat, a))
        for kw in node.keywords:
            # `**x` arrives as a keyword whose `arg` is None. It is a splat, not a
            # keyword named nothing.
            pos = (kw.lineno, kw.col_offset)
            pieces.append((pos, kw.arg, kw.arg is None, kw.value if kw.arg else kw))
        pieces.sort(key=lambda t: t[0])

        out: list[CallArg] = []
        for i, (_, keyword, splat, expr_node) in enumerate(pieces):
            text = self._segment(expr_node)
            if text is None:
                continue
            out.append(CallArg(idx=i, expr=text, keyword=keyword, splat=splat))
        return out

    def _record_call(self, caller_id: str, expr: str, line: int, *,
                     at_boundary: bool = False,
                     args: list[CallArg] | None = None) -> None:
        """The one door onto `self.calls`, because identity is assigned here.

        Rule 51: every caller reaches it through the same door, or the next one added
        forgets the ordinal and two call sites share an id. The ordinal is per
        `(caller, expression)` and is what keeps two `emit()` calls in one routine apart
        without recording where either of them sits.
        """
        key = (caller_id, expr)
        ordinal = self._call_ordinal.get(key, 0)
        self._call_ordinal[key] = ordinal + 1
        self.calls.append(CallSite(
            caller_id=caller_id, callee_expr=expr, line=line,
            confidence=Confidence.INFERRED, at_boundary=at_boundary,
            site_id=call_site_id(caller_id, expr, ordinal),
            args=args or [],
        ))

    def visit_Call(self, node: ast.Call) -> None:
        owner = self._owner()
        self._maybe_registration(node)
        self._maybe_set_defaults(node)
        expr = dotted_name(node.func)
        if expr and self.rules.is_cli_mount(expr) and node.args:
            parent_var = expr.rsplit(".", 1)[0]
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                # argparse: `sub.add_parser("serve")` names a subcommand outright.
                # There is no application object to mount, so record the command.
                ep = Entrypoint(
                    id=entrypoint_id(self.path, arg0.value),
                    kind=EntrypointKind.CLI,
                    name=arg0.value,
                    routine_id=None,
                    module=self.module,
                    evidence=f"{expr}({arg0.value!r})",
                    group=parent_var,
                )
                self.entrypoints.append(ep)
                self._argparse_ep[arg0.value] = ep
            else:
                child = dotted_name(arg0) or _literal(arg0) or ""
                self.cli_mounts.append(CliMount(
                    parent_var=parent_var,
                    parent_module=self.module,
                    child_expr=child,
                    file=self.path,
                    line=node.lineno,
                    name=_kwarg_str(node, "name") or "",
                ))
        if expr:
            rule = self.rules.match_call(expr)
            self._record_call(owner.id, expr, node.lineno,
                              at_boundary=rule is not None, args=self._call_args(node))
            self._maybe_network(node, expr)
            if rule is not None:
                self.boundaries.append(BoundaryHit(
                    routine_id=owner.id,
                    kind=rule.kind,
                    direction=rule.direction,
                    target=self._target(node, rule.target_arg),
                    line=node.lineno,
                    evidence=expr,
                    salience=rule.salience,
                ))
        self.generic_visit(node)

    def _maybe_set_defaults(self, node: ast.Call) -> None:
        """Catch `p_serve.set_defaults(func=_cmd_serve)`.

        This is how argparse binds a subcommand to the function that implements it.
        The dispatch itself (`args.func(args)`) is invisible to static analysis, so
        without this the handlers look unreachable and the whole executable appears
        to do nothing.
        """
        expr = dotted_name(node.func)
        if not expr or expr.rsplit(".", 1)[-1] != "set_defaults":
            return
        handler = None
        for kw in node.keywords:
            if kw.arg in {"func", "handler", "callback"}:
                handler = dotted_name(kw.value)
                break
        if not handler:
            return
        # Record the dispatch as a real edge so reachability follows it. It carries no
        # arguments, and that is the honest answer rather than an omission: `args.func(
        # args)` is the call this stands for and it is nowhere in the source to read.
        self._record_call(self._owner().id, handler, node.lineno)
        name = self._argparse_var.get(expr.rsplit(".", 1)[0])
        ep = self._argparse_ep.get(name) if name else None
        if ep is not None and not ep.target_expr:
            ep.target_expr = handler
            ep.evidence = f"{ep.evidence} -> {handler}"

    def _maybe_registration(self, node: ast.Call) -> None:
        """Catch `app.command(name="docs")(_docs_cmd)`.

        Registering a command by calling the decorator directly is ordinary Python and
        common when the handler lives in another module. It is invisible to decorator
        matching, so a CLI built this way would otherwise look like it had no commands.
        """
        if not isinstance(node.func, ast.Call) or not node.args:
            return
        inner = node.func
        dec = dotted_name(inner.func)
        rule = self.rules.match_decorator(dec)
        if rule is None or "." not in dec:
            return
        target = dotted_name(node.args[0])
        if not target:
            return
        name = _kwarg_str(inner, "name") or target.rsplit(".", 1)[-1]
        self.entrypoints.append(Entrypoint(
            id=entrypoint_id(self.path, dec, name),
            kind=rule.kind,
            name=name,
            routine_id=None,
            module=self.module,
            evidence=f"{dec}(...)({target})",
            group=dec.rsplit(".", 1)[0],
            target_expr=target,
        ))

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """`async with httpx.AsyncClient(...) as c:` manages the client correctly.

        The constructor is deliberately not awaited -- the context manager awaits on
        entry and exit. Flagging it as an un-awaited async call reports correct code
        as a defect, which is worse than saying nothing.
        """
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                self._awaited.add(id(item.context_expr))
        self.generic_visit(node)

    def visit_Await(self, node: ast.Await) -> None:
        """Note which calls are actually awaited.

        An async client used without `await` blocks anyway (or worse, never runs), so
        "is this asynchronous?" is only answerable by looking at the call site.
        """
        if isinstance(node.value, ast.Call):
            self._awaited.add(id(node.value))
        self.generic_visit(node)

    def _maybe_network(self, node: ast.Call, expr: str) -> None:
        """Record a remote call with the detail an operator needs to troubleshoot it."""
        profile = self.rules.network_profile(expr)
        if profile is None:
            return
        protocol, lib_async = profile
        kw = self.rules.net_kwargs

        def kwarg(group: str) -> str:
            names = kw.get(group, frozenset())
            for k in node.keywords:
                if k.arg in names:
                    return _literal(k.value) or "set"
            return ""

        last = expr.rsplit(".", 1)[-1]
        verb = last.upper() if last in self.rules.net_verbs else ""
        if not verb:
            for k in node.keywords:
                if k.arg == "method" and isinstance(k.value, ast.Constant):
                    verb = str(k.value.value).upper()

        destination = ""
        port = kwarg("port")
        for k in node.keywords:
            if k.arg in {"url", "endpoint", "uri", "host", "address", "base_url"}:
                destination = _literal(k.value) or ""
        if not destination and node.args:
            first = node.args[0]
            # `create_connection((host, port))` carries both in one tuple.
            if isinstance(first, ast.Tuple) and len(first.elts) == 2:
                destination = _literal(first.elts[0]) or ""
                port = port or (_literal(first.elts[1]) or "")
            else:
                destination = _literal(first) or ""

        self.network.append(NetworkCall(
            routine_id=self._owner().id,
            expr=expr,
            protocol=protocol,
            line=node.lineno,
            verb=verb,
            destination=destination,
            port=port,
            is_async=lib_async,
            awaited=id(node) in self._awaited,
            in_async_routine=bool(self._scope and self._scope[-1].is_async),
            timeout=kwarg("timeout"),
            retries=kwarg("retries"),
            tls=kwarg("tls"),
            payload=kwarg("payload"),
            headers=kwarg("headers"),
            topic=kwarg("topic"),
            ack=kwarg("ack"),
        ))

    def visit_Constant(self, node: ast.Constant) -> None:
        """Every string literal is reported. What one *means* is not decided here.

        Looking only at call arguments would miss most of the schema: DDL is usually a
        module-level constant or an `executescript` block, far from any cursor.

        **A docstring is not one of these**, and that exclusion has to live here because
        only the reader can see it: rule 9, and a docstring opening "Insert candidate into
        capture_queue..." is a sentence about a statement rather than a statement. By the
        time `ingest/literals.py` has the string, nothing distinguishes the two.
        """
        if isinstance(node.value, str) and id(node) not in self._docstrings:
            self._literal(node.value, node.lineno, LiteralKind.PLAIN)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """An f-string, with its interpolations stood in for.

        `f"{root}/tabularium.db"` still names the file and `f"CREATE TABLE {t} (...)"`
        still names its table, so the text has to be assembled -- and assembling it needs
        the module's own constant table and the tree that holds it, which is why this half
        stays with the reader while the judgement does not. What leaves is marked
        `INTERPOLATED`, because `?` here is a placeholder this reader wrote and `?` in a
        string somebody typed is a glob (rule 30).
        """
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            elif isinstance(v, ast.FormattedValue):
                parts.append(self._interpolated(v) or "?")
            else:
                parts.append("?")
        self._literal("".join(parts), node.lineno, LiteralKind.INTERPOLATED)
        self.generic_visit(node)

    def _literal(self, text: str, line: int, kind: LiteralKind) -> None:
        """Report one string, or count it as dropped by the host's own bound.

        The bound is `ingest.literals`' and is applied here because this is where the wire
        is: what it genuinely saves is the **ceiling**, a vendored blob nobody should be
        lexically scanning for SQL. Its floor saves 1.6% of the payload and is set where it
        is so that no judgement the host might make can fall below it -- measured, and
        written down there rather than here. It is a *filter running where the host cannot
        see it*, so the count travels with the facts rather than being left to be inferred
        from a silence (design rule 1).
        """
        if not in_bounds(text):
            self.literals_dropped += 1
            return
        self.literals.append(StringLiteral(
            routine_id=self._owner_id(), line=line, text=text, kind=kind,
        ))

    def visit_Subscript(self, node: ast.Subscript) -> None:
        # os.environ["X"] is an environment read that never appears as a call.
        base = dotted_name(node.value)
        rule = self.rules.match_subscript(base) if base else None
        if rule is not None:
            # A string key is the variable's name; record it as such, the same way a
            # call argument is recorded, rather than as quoted source text.
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                target = key.value
            else:
                target = _literal(key) or "?"
            self.boundaries.append(BoundaryHit(
                routine_id=self._owner().id,
                kind=rule.kind,
                direction=rule.direction,
                target=target,
                line=node.lineno,
                evidence=f"{base}[...]",
                salience=rule.salience,
            ))
        self.generic_visit(node)

    def _target(self, node: ast.Call, arg_index: int | None) -> str:
        """What is being touched. A literal when it is knowable, the expression when not."""
        if arg_index is None or arg_index >= len(node.args):
            return ""
        arg = node.args[arg_index]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        return _literal(arg) or ""

    # -- ways in ------------------------------------------------------------ #

    def _detect_entrypoint(self, routine: Routine, decorators: list[str]) -> None:
        for dec in decorators:
            rule = self.rules.match_decorator(dec)
            if rule is not None:
                self.entrypoints.append(Entrypoint(
                    id=entrypoint_id(self.path, routine.qualname),
                    kind=rule.kind,
                    name=routine.name,
                    routine_id=routine.id,
                    module=self.module,
                    evidence=f"@{dec}",
                    group=dec.rsplit(".", 1)[0] if "." in dec else "",
                ))
                return
        # A request method on a server handler class is an inbound way in.
        if routine.is_method and routine.class_name:
            kind = self.rules.handler_kind(
                self._class_bases.get(routine.class_name, []), routine.name
            )
            if kind is not None:
                self.entrypoints.append(Entrypoint(
                    id=entrypoint_id(self.path, routine.qualname),
                    kind=kind,
                    name=f"{routine.class_name}.{routine.name}",
                    routine_id=routine.id,
                    module=self.module,
                    evidence=f"{routine.name} on {routine.class_name}",
                ))
                return

        # A conventionally-named routine at module top level is a way in.
        if (
            not routine.is_nested
            and not routine.is_method
            and routine.name in self.rules.entry_names
        ):
            self.entrypoints.append(Entrypoint(
                id=entrypoint_id(self.path, routine.qualname),
                kind=EntrypointKind.MAIN,
                name=routine.name,
                routine_id=routine.id,
                module=self.module,
                evidence=f"conventional name '{routine.name}' at module level",
            ))

    def visit_If(self, node: ast.If) -> None:
        if _is_main_guard(node.test):
            self._has_main_guard = True
            # Record what the guard actually calls. Assuming `main()` misses every
            # module whose entry function is called something else, and reports the
            # way in as leading nowhere.
            for stmt in ast.walk(node):
                if isinstance(stmt, ast.Call):
                    name = dotted_name(stmt.func)
                    if name and name not in _GUARD_NOISE:
                        self._main_guard_calls.append(name)
        # **Both, and this is the one visitor two features share.** The `__main__` test
        # above and the control point below answer different questions about the same
        # node, and `_visit_decision` owns the descent -- so `generic_visit` is *not*
        # called here as well, or every subtree under an `if` would be walked twice and
        # every call inside one recorded twice (rule 40: two detectors recording one act
        # is two numbers about one thing).
        self._visit_decision(node)


def _kwarg_str(call: ast.Call, key: str) -> str | None:
    """A string keyword argument's literal value, when it has one."""
    for kw in call.keywords:
        if kw.arg == key and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


# Calls a `__main__` guard makes incidentally, which never name the way in.
_GUARD_NOISE = frozenset({
    "print", "sys.exit", "exit", "json.dumps", "len", "str", "int", "SystemExit",
    "raise", "format", "sorted", "all", "any",
})


def _strip_call(node: ast.AST) -> ast.AST:
    """`@app.command()` and `@app.command` should look the same to a rule."""
    return node.func if isinstance(node, ast.Call) else node


def _is_main_guard(test: ast.AST) -> bool:
    if not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name):
        return False
    if test.left.id != "__name__":
        return False
    return any(
        isinstance(c, ast.Constant) and c.value == "__main__" for c in test.comparators
    )


def _docstring_nodes(tree: ast.Module) -> frozenset[int]:
    """Every string literal that serves as a docstring, by node identity."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                out.add(id(first.value))
    return frozenset(out)


def module_name(path: Path, root: Path) -> str:
    """Dotted module name from a path, the way an import would spell it."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = Path(path.name)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    # A src/ layout is packaging, not namespace.
    if parts and parts[0] == "src":
        parts.pop(0)
    return ".".join(parts) if parts else rel.stem


def extract_file(path: Path, root: Path, src: str | None = None) -> FileFacts:
    """Extract every fact from one Python file.

    A file that will not parse yields an empty result carrying the error, rather than
    aborting the run -- one bad file in six hundred should not cost the other 599.
    """
    if src is None:
        src = path.read_text(encoding="utf-8", errors="replace")
    # **Relative to the analysed root, and stored that way.** An absolute path is one
    # machine's directory layout: it leaks that layout to anyone the store is handed to,
    # it breaks when the tree is moved to free disk space, and it breaks outright when a
    # program directory is copied to another machine. Worse for this tool specifically,
    # two revisions read from two different trees give the same file two unrelated keys,
    # so nothing can pair a file across points in time -- which is the one question two
    # revisions exist to ask.
    #
    # Nothing needs the absolute form back. Bodies are read from `source.db` by content
    # hash, never by opening a path, and the only step that touches the disk is analysis,
    # which is handed the root as an argument. `module_name` below has computed the same
    # relative path since the day it was written; this line said `rel` and did not.
    outside = ""
    try:
        rel = stored_path(path.resolve().relative_to(root.resolve()))
    except ValueError:
        # Unreachable via `discover()`, which only yields files under `root`. Recorded
        # rather than swallowed: a fallback that quietly stores the absolute path again
        # would reintroduce the defect with no symptom, which is the shape this project
        # keeps paying for.
        rel = stored_path(path)
        outside = f"outside the analysed root {root}: stored absolute"
    module = module_name(path, root)
    facts = FileFacts(path=rel, lang="python", module=module, content_hash=hash_source(src))
    if outside:
        facts.errors.append(outside)

    try:
        tree = ast.parse(src, filename=str(path))
    except (SyntaxError, ValueError, RecursionError) as exc:
        facts.errors.append(f"parse failed: {exc}")
        return facts

    # The module docstring is kept whole. It is the only statement of what a module
    # is FOR that most codebases contain, and it is where domain vocabulary is defined.
    facts.doc = ast.get_docstring(tree) or ""

    ex = _Extractor(rel, module, src, load_rules("python"), _docstring_nodes(tree))
    # Before the walk: an f-string is resolved as it is visited, and a name bound
    # further down the module is still bound by the time the module runs.
    ex.collect_module_strings(tree.body)
    try:
        for stmt in tree.body:
            ex.visit(stmt)
    except RecursionError:
        facts.errors.append("extraction aborted: expression nesting too deep")

    ex.collect_module_names(tree.body)
    # After the walk, so "claimed" means claimed by any routine at all.
    ex.claim_orphan_comments()

    facts.routines = ex.routines
    facts.calls = ex.calls
    facts.boundaries = ex.boundaries
    facts.structures = ex.structures
    facts.entrypoints = ex.entrypoints
    facts.imports = ex.imports
    facts.classes = ex.classes
    facts.cli_apps = ex.cli_apps
    facts.cli_mounts = ex.cli_mounts
    facts.network = ex.network
    facts.constants = ex.constants
    # `sql`, `tables`, `indexes` and `artefacts` are deliberately not set here: they are
    # `ingest.literals.judge`'s to fill from these, for every language at once, and a
    # reader that filled them itself is refused there (rule 30).
    facts.literals = ex.literals
    facts.literals_dropped = ex.literals_dropped
    # Prepared, and claimed by the host only if one of those strings turns out to be a
    # fact. See `_Extractor.module_scope`.
    facts.module_scope = ex.module_scope()
    facts.control = ex.control
    facts.control_arms = ex.control_arms

    # A module that guards __main__ is startable in its own right.
    if ex._has_main_guard:
        target = next((r for r in ex.routines if r.name == "main" and not r.is_method), None)
        if target is None:
            # Fall back to whatever the guard actually calls, in the order written.
            by_name = {r.name: r for r in ex.routines if not r.is_method and not r.is_nested}
            for called in ex._main_guard_calls:
                candidate = by_name.get(called.rsplit(".", 1)[-1])
                if candidate is not None:
                    target = candidate
                    break
        facts.entrypoints.append(Entrypoint(
            id=entrypoint_id(rel, "__main__"),
            kind=EntrypointKind.MAIN,
            name=f"python -m {module}",
            routine_id=target.id if target else None,
            module=module,
            evidence='if __name__ == "__main__"',
        ))
    return facts
