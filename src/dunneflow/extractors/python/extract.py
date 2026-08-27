"""Python fact extraction.

Reads one source file and reports what moves through it: the routines, their typed
signatures, what they call, where they touch the outside world, the shapes they pass
around, and the comments that explain why.

Deliberately *not* reported: local variables, arithmetic, control flow, and anything
else that stays inside a routine. Those are the parts the reader was explicit about
not wanting, and leaving them out is most of what makes the output legible.

Uses the standard library only -- `ast` for structure, `tokenize` for comments. No
third-party parser, nothing to install, and it cannot fall behind the language.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

from ... import sql as sqlmod
from ...detectors import RuleSet, load_rules, mine_annotations
from ...schema import (
    Artefact,
    BoundaryHit,
    CallSite,
    ClassDef_,
    CliApp,
    CliMount,
    Comment,
    Confidence,
    Constant,
    DataStructure,
    Entrypoint,
    EntrypointKind,
    Field_,
    FileFacts,
    ImportRec,
    IndexSchema,
    NetworkCall,
    Param,
    Routine,
    SqlStatement,
    StructureKind,
    TableSchema,
    hash_source,
    make_id,
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


# A file basename, as a person would write one. Deliberately narrow: no spaces, no
# quoting, no shell metacharacters beyond the glob forms, and an extension of at most
# eight characters. Anything else is prose that happens to contain a dot.
_ARTEFACT_NAME = re.compile(r"^[A-Za-z0-9_*?\[\]][A-Za-z0-9_.*?\[\]-]*\.[A-Za-z0-9]{1,8}$")


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
    """
    out: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                out[tok.start[0]] = tok.string.lstrip("#").strip()
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
        self.sql: list[SqlStatement] = []
        self.network: list[NetworkCall] = []
        self._awaited: set[int] = set()
        self.tables: list[TableSchema] = []
        self.indexes: list[IndexSchema] = []
        self.artefacts: list[Artefact] = []
        self.constants: list[Constant] = []
        # An f-string is visited whole and then descended into, so `f"{root}/g.json"`
        # would name `g.json` twice -- once with the fuller literal, once from the
        # bare constant part. The same file named on the same line is one naming act;
        # the f-string is seen first and so keeps the more informative literal.
        self._artefact_seen: set[tuple[str, int]] = set()
        self._sql_seen: set[tuple[str, int]] = set()
        # A broken program may define one qualified name twice. Both keep an identity
        # of their own rather than merging, so the collision can be reported.
        self._seen_qualnames: dict[str, int] = {}

        self._scope: list[Routine] = []
        self._class: list[str] = []
        self._class_bases: dict[str, list[str]] = {}
        self._module_routine: Routine | None = None
        self._has_main_guard = False
        self._main_guard_calls: list[str] = []

    # -- scope ------------------------------------------------------------- #

    def _identity(self, qualname: str) -> str:
        """A stable id for a qualified name, disambiguating any real duplicate."""
        n = self._seen_qualnames.get(qualname, 0)
        self._seen_qualnames[qualname] = n + 1
        return make_id(qualname) if n == 0 else make_id(qualname, f"#{n + 1}")

    def _owner(self) -> Routine:
        """Whichever routine currently encloses. Module level gets a synthetic one.

        Module-level work matters: a `os.getenv` at import time is exactly the
        "fed inputs at startup" the reader cares about, and it belongs to something.
        """
        if self._scope:
            return self._scope[-1]
        if self._module_routine is None:
            self._module_routine = Routine(
                id=make_id(f"{self.module}.{MODULE_SCOPE}"),
                name=MODULE_SCOPE,
                qualname=f"{self.module}.{MODULE_SCOPE}",
                module=self.module,
                file=self.path,
                line_start=1,
                line_end=len(self.lines) or 1,
                docstring="Module-level code: runs at import, before anything is called.",
                body_hash=hash_source("\n".join(self.lines)),
            )
            self.routines.append(self._module_routine)
        return self._module_routine

    # -- module-level names ------------------------------------------------- #

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
            id=make_id(f"{self.module}.{name}"),
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
        out: list[Param] = []
        positional = list(args.posonlyargs) + list(args.args)
        pad = len(positional) - len(args.defaults)
        for i, a in enumerate(positional):
            default = _literal(args.defaults[i - pad]) if i >= pad else None
            out.append(Param(a.arg, _annotation(a.annotation), default, "positional"))
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
        for child in node.body:
            self.visit(child)
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
                id=make_id(".".join([self.module, *self._class, node.name])),
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
                            id=make_id("cliapp", f"{self.module}.{t.id}"),
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

    # -- the things that move ---------------------------------------------- #

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
                    id=make_id("ep", f"{self.module}:{arg0.value}"),
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
            self.calls.append(CallSite(
                caller_id=owner.id, callee_expr=expr, line=node.lineno,
                confidence=Confidence.INFERRED, at_boundary=rule is not None,
            ))
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
        # Record the dispatch as a real edge so reachability follows it.
        self.calls.append(CallSite(
            caller_id=self._owner().id, callee_expr=handler, line=node.lineno,
            confidence=Confidence.INFERRED,
        ))
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
            id=make_id("ep", f"{self.module}:{dec}:{name}"),
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
        """Every string literal is a candidate statement.

        Looking only at call arguments would miss most of the schema: DDL is usually a
        module-level constant or an `executescript` block, far from any cursor.
        """
        if isinstance(node.value, str) and id(node) not in self._docstrings:
            self._scan_sql(node.value, node.lineno)
            self._scan_artefact(node.value, node.lineno)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """An f-string with interpolation still names its tables."""
        parts = [
            v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "?"
            for v in node.values
        ]
        joined = "".join(parts)
        self._scan_sql(joined, node.lineno)
        # `f"{root}/tabularium.db"` still names the file; `f"{name}.db"` does not, and
        # is rejected below because the stem itself came back as the `?` placeholder.
        self._scan_artefact(joined, node.lineno)
        self.generic_visit(node)

    def _scan_artefact(self, text: str, line: int) -> None:
        """A string literal that names a file the program uses.

        Precision is bought entirely by the extension list in `detectors/*.yaml`
        (rule 5): a trailing dotted part is not a file extension, or `"1.2.3"`,
        `"utf-8"` and `"mensores.cli"` would all read as named files. Everything
        else here is a guard against reading prose as a path.

        The literal is recorded whole (rule 8). The basename is what gets matched,
        because `.mensores/tabularium.db` and `tabularium.db` name the same file.
        """
        raw = text.strip()
        if not raw or len(raw) > 512 or any(ch.isspace() for ch in raw):
            return
        if "://" in raw:            # a URL is a network boundary, not a local artefact
            return
        base = raw.replace("\\", "/").rsplit("/", 1)[-1]
        if "." not in base[1:]:     # leading dot is a hidden file, not an extension
            return
        stem, _, ext = base.rpartition(".")
        kind = self.rules.artefact_kind(ext)
        if kind is None or not stem:
            return
        # `?` is the placeholder an f-string leaves where a value was interpolated.
        # A stem that is only a placeholder names nothing a reader could look up.
        if "?" in stem or not any(ch.isalnum() for ch in stem):
            return
        if not _ARTEFACT_NAME.match(base):
            return
        if (base, line) in self._artefact_seen:
            return
        self._artefact_seen.add((base, line))
        self.artefacts.append(Artefact(
            name=base, stem=stem, ext=ext.lower(), kind=kind,
            routine_id=self._owner().id, line=line, literal=text,
            is_pattern=any(ch in base for ch in "*?[") ,
        ))

    def _scan_sql(self, text: str, line: int) -> None:
        if len(text) < 6 or len(text) > 200_000:
            return
        # `executescript` blocks hold a whole schema; each statement counts separately.
        chunks = text.split(";") if text.count(";") else [text]
        for chunk in chunks[:200]:
            if not sqlmod.looks_like_sql(chunk):
                continue
            op = sqlmod.parse(chunk)
            if op is None:
                continue
            key = (op.sql[:80], line)
            if key in self._sql_seen:
                continue
            self._sql_seen.add(key)
            self.sql.append(SqlStatement(
                routine_id=self._owner().id, operation=op.operation,
                direction=op.direction, tables=op.tables, sql=op.sql, line=line,
            ))
            if op.operation == "CREATE TABLE":
                td = sqlmod.parse_table_def(chunk)
                if td and td.name:
                    self.tables.append(TableSchema(
                        name=td.name, file=self.path, line=line, temporary=td.temporary,
                        columns=[(c.name, c.type, c.constraints) for c in td.columns],
                    ))
            elif op.operation == "CREATE INDEX":
                for ix in sqlmod.parse_index_defs(chunk):
                    self.indexes.append(IndexSchema(
                        name=ix.name, table=ix.table, columns=ix.columns,
                        file=self.path, line=line, unique=ix.unique,
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
                    id=make_id("ep", routine.qualname),
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
                    id=make_id("ep", routine.qualname),
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
                id=make_id("ep", routine.qualname),
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
        self.generic_visit(node)


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
    rel = str(path)
    module = module_name(path, root)
    facts = FileFacts(path=rel, lang="python", module=module, content_hash=hash_source(src))

    try:
        tree = ast.parse(src, filename=str(path))
    except (SyntaxError, ValueError, RecursionError) as exc:
        facts.errors.append(f"parse failed: {exc}")
        return facts

    # The module docstring is kept whole. It is the only statement of what a module
    # is FOR that most codebases contain, and it is where domain vocabulary is defined.
    facts.doc = ast.get_docstring(tree) or ""

    ex = _Extractor(rel, module, src, load_rules("python"), _docstring_nodes(tree))
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
    facts.sql = ex.sql
    facts.network = ex.network
    facts.tables = ex.tables
    facts.indexes = ex.indexes
    facts.artefacts = ex.artefacts
    facts.constants = ex.constants

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
            id=make_id("ep", f"{module}:__main__"),
            kind=EntrypointKind.MAIN,
            name=f"python -m {module}",
            routine_id=target.id if target else None,
            module=module,
            evidence='if __name__ == "__main__"',
        ))
    return facts
