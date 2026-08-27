"""The fact contract.

Every extractor, whatever the language, emits exactly these types. The resolver,
renderer, and narrator know nothing about Python or TypeScript -- only about this.
Adding a language means writing one extractor that speaks this vocabulary.

The vocabulary is deliberately the user's own: a program has ENTRYPOINTS, it runs
ROUTINES, those routines call each other (EDGES), they touch the outside world at
BOUNDARIES, and they move DATA STRUCTURES around. What does not move is not modelled.

Documentation has its own contract at the foot of this file -- `DocFacts` and its parts.
It is a parallel input, not a subordinate one, and it is stored separately for the same
reason it is contracted separately: a program is often documented badly or not at all,
and nothing read from code may ever depend on prose being present.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

# Bump whenever the stored shape or the meaning of an extracted fact changes.
# A mismatch discards the graph and re-extracts: graph.db is derived data, and a
# stale map that answers confidently is worse than no map at all.
SCHEMA_VERSION = 2


# --------------------------------------------------------------------------- #
# Boundaries: the only places a program touches anything outside itself.
# --------------------------------------------------------------------------- #


class BoundaryKind(StrEnum):
    """Where a program pulls from or pushes to its environment."""

    ENV = "ENV"
    FILE = "FILE"
    PROCESS = "PROCESS"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    QUEUE = "QUEUE"
    STDIO = "STDIO"
    CLOUD_SDK = "CLOUD_SDK"
    LLM_API = "LLM_API"
    CRYPTO = "CRYPTO"


class Direction(StrEnum):
    """Which way the thing moves."""

    IN = "IN"
    OUT = "OUT"
    BOTH = "BOTH"


class EntrypointKind(StrEnum):
    """How a program gets started, or woken up."""

    CLI = "CLI"
    MAIN = "MAIN"
    MCP_TOOL = "MCP_TOOL"
    HTTP_ROUTE = "HTTP_ROUTE"
    QUEUE_CONSUMER = "QUEUE_CONSUMER"
    SCHEDULED = "SCHEDULED"
    SIGNAL = "SIGNAL"
    LIBRARY = "LIBRARY"


class Confidence(StrEnum):
    """How much to trust an edge.

    CERTAIN -- the call target was resolved unambiguously.
    INFERRED -- resolved by name across modules; probably right, not provably.
    """

    CERTAIN = "CERTAIN"
    INFERRED = "INFERRED"


class StructureKind(StrEnum):
    DATACLASS = "DATACLASS"
    PYDANTIC = "PYDANTIC"
    TYPEDDICT = "TYPEDDICT"
    NAMEDTUPLE = "NAMEDTUPLE"
    ENUM = "ENUM"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    TYPE_ALIAS = "TYPE_ALIAS"


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Param:
    """One parameter of a routine. Types are what moves in."""

    name: str
    type: str | None = None
    default: str | None = None
    kind: Literal["positional", "keyword", "vararg", "kwarg"] = "positional"


@dataclass(frozen=True, slots=True)
class Field_:
    """One field of a data structure."""

    name: str
    type: str | None = None
    default: str | None = None
    comment: str | None = None


@dataclass(slots=True)
class Comment:
    """A comment attached to a routine.

    Comments are first-class because they carry WHY, which the code itself never does.
    `leading` distinguishes the block above a definition (usually intent) from inline
    remarks (usually caveats).
    """

    text: str
    line: int
    leading: bool = False


@dataclass(slots=True)
class Annotation:
    """A structured marker mined out of a comment or docstring.

    Governance IDs, audit locks, warnings -- the things that are load-bearing prose.
    """

    kind: str
    value: str
    line: int
    text: str = ""


@dataclass(slots=True)
class Routine:
    """A function, method, or subroutine: a place where things pass through."""

    id: str
    name: str
    qualname: str
    module: str
    file: str
    line_start: int
    line_end: int
    lang: str = "python"
    params: list[Param] = field(default_factory=list)
    returns: str | None = None
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    comments: list[Comment] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    is_async: bool = False
    is_method: bool = False
    class_name: str | None = None
    is_nested: bool = False
    visibility: Literal["public", "private"] = "public"
    body_hash: str = ""  # changes when the routine's source changes; identity does not

    def signature(self) -> str:
        """Render the signature the way it would be read, not the way it was written."""
        parts = []
        for p in self.params:
            prefix = {"vararg": "*", "kwarg": "**"}.get(p.kind, "")
            s = f"{prefix}{p.name}"
            if p.type:
                s += f": {p.type}"
            if p.default is not None:
                s += f" = {p.default}"
            parts.append(s)
        sig = f"{self.name}({', '.join(parts)})"
        if self.returns:
            sig += f" -> {self.returns}"
        return sig


@dataclass(slots=True)
class CallSite:
    """One routine calling another. Resolution happens later, in the resolver."""

    caller_id: str
    callee_expr: str
    line: int
    callee_id: str | None = None
    confidence: Confidence = Confidence.INFERRED
    external: bool = False
    at_boundary: bool = False  # already identified as a call OUT of the program


@dataclass(slots=True)
class BoundaryHit:
    """A routine touching the outside world."""

    routine_id: str
    kind: BoundaryKind
    direction: Direction
    target: str
    line: int
    evidence: str = ""
    salience: str = "normal"  # high | normal | low -- lets noise be filtered, not lost


@dataclass(slots=True)
class DataStructure:
    """A named shape that moves between routines."""

    id: str
    name: str
    kind: StructureKind
    module: str
    file: str
    line: int
    lang: str = "python"
    fields: list[Field_] = field(default_factory=list)
    docstring: str | None = None
    bases: list[str] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)


@dataclass(slots=True)
class ClassDef_:
    """Every class and what it derives from.

    Recorded for all classes, not just data-shaped ones, because a method call on
    `self` is often defined on a base. Without the inheritance chain those calls
    resolve to nothing and the graph quietly loses the edge.
    """

    name: str
    qualname: str
    module: str
    file: str
    line: int
    bases: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NetworkCall:
    """One remote call, with the detail needed to reason about it operationally.

    A local call is characterised by its types. A remote call needs more: what
    protocol, to where, on what port, does it block, how long before it gives up, and
    does it retry. Those are the fields you otherwise reconstruct from a packet
    capture.
    """

    routine_id: str
    expr: str
    protocol: str
    line: int
    verb: str = ""
    destination: str = ""
    port: str = ""
    is_async: bool = False       # the library call itself is asynchronous
    awaited: bool = False        # and it is actually awaited here
    in_async_routine: bool = False
    timeout: str = ""
    retries: str = ""
    tls: str = ""
    payload: str = ""
    headers: str = ""
    topic: str = ""      # messaging: the queue, topic, subject, or routing key
    ack: str = ""        # messaging: acknowledgement / durability setting

    def blocking(self) -> bool:
        """Whether this call stops the caller until the far end answers."""
        return not (self.is_async and self.awaited)


@dataclass(slots=True)
class SqlStatement:
    """One SQL statement found in the source, and the routine that holds it."""

    routine_id: str
    operation: str
    direction: str          # READ | WRITE | DDL | CONTROL
    tables: list[str]
    sql: str
    line: int


@dataclass(slots=True)
class TableSchema:
    """A table the program itself creates. The schema, from the code that defines it."""

    name: str
    file: str
    line: int
    columns: list[tuple[str, str, str]] = field(default_factory=list)
    temporary: bool = False


@dataclass(slots=True)
class IndexSchema:
    name: str
    table: str
    columns: str
    file: str
    line: int
    unique: bool = False


@dataclass(slots=True)
class CliApp:
    """A command-line application object, e.g. `app = typer.Typer()`.

    Modelled because a real CLI is rarely one function. It is an object that commands
    attach to and that other such objects mount onto, and that tree is the shape of
    the program's front door.
    """

    id: str
    var: str
    module: str
    file: str
    line: int
    title: str = ""
    factory: str = ""


@dataclass(slots=True)
class CliMount:
    """One CLI application mounted onto another, e.g. `app.add_typer(check_app)`."""

    parent_var: str
    parent_module: str
    child_expr: str
    file: str
    line: int
    name: str = ""


@dataclass(slots=True)
class Entrypoint:
    """A way in."""

    id: str
    kind: EntrypointKind
    name: str
    routine_id: str | None = None
    module: str = ""
    evidence: str = ""
    group: str = ""       # the CLI app object this command attaches to, if any
    parent_id: str | None = None  # the app this belongs to, once resolved
    target_expr: str = ""  # routine named by expression, when not resolvable in-file


@dataclass(slots=True)
class ImportRec:
    """An import, kept only so call names can be resolved to their module."""

    module: str
    name: str
    alias: str
    is_from: bool
    line: int


@dataclass(slots=True)
class FileFacts:
    """Everything one source file yields. The unit of extraction and of caching."""

    path: str
    lang: str
    module: str
    content_hash: str
    # The module's own docstring. Prose about what this module IS -- the only place
    # most programs say what their vocabulary means. Excluded from code-shaped
    # detectors (rule 9) precisely because it is a sentence, which is what makes it
    # the right source for a glossary.
    doc: str = ""
    routines: list[Routine] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)
    boundaries: list[BoundaryHit] = field(default_factory=list)
    structures: list[DataStructure] = field(default_factory=list)
    entrypoints: list[Entrypoint] = field(default_factory=list)
    imports: list[ImportRec] = field(default_factory=list)
    cli_apps: list[CliApp] = field(default_factory=list)
    cli_mounts: list[CliMount] = field(default_factory=list)
    sql: list[SqlStatement] = field(default_factory=list)
    network: list[NetworkCall] = field(default_factory=list)
    classes: list[ClassDef_] = field(default_factory=list)
    tables: list[TableSchema] = field(default_factory=list)
    indexes: list[IndexSchema] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Documentation: the other half of the input.
#
# Documentation is a parallel and equal input, not a side channel -- and it is often
# absent, partial, or wrong, so nothing code-derived may ever depend on it. These types
# are to prose what FileFacts is to source, and they are stored in their own database
# for the same reason: a doc rescan must not touch the code graph.
# --------------------------------------------------------------------------- #

# Bump whenever the stored shape or the meaning of an extracted doc fact changes.
# Separate from SCHEMA_VERSION so a prose rule change does not discard the code graph.
DOC_SCHEMA_VERSION = 5


class DocFormat(StrEnum):
    MARKDOWN = "MARKDOWN"
    RST = "RST"
    TEXT = "TEXT"
    ADOC = "ADOC"


class DocClass(StrEnum):
    """What kind of document this is, decided deterministically.

    Load-bearing rather than decorative: a research paper *about* naming standards is
    not a naming standard, and only the classification tells them apart.
    """

    README = "README"
    GLOSSARY = "GLOSSARY"
    NAMING_STANDARD = "NAMING_STANDARD"
    DECISION = "DECISION"          # ADR and the like
    PLAN = "PLAN"
    ROADMAP = "ROADMAP"
    CHANGELOG = "CHANGELOG"
    GUIDE = "GUIDE"
    REFERENCE = "REFERENCE"
    RESEARCH = "RESEARCH"
    SPEC = "SPEC"
    ISSUE = "ISSUE"
    CONTRIBUTING = "CONTRIBUTING"
    TOOLING = "TOOLING"            # agent instructions, skills, harness config
    OTHER = "OTHER"


class DefForm(StrEnum):
    """The shape a definition was written in. Kept because it is evidence."""

    TABLE_ROW = "TABLE_ROW"
    BOLD_LEAD = "BOLD_LEAD"
    DEF_LIST = "DEF_LIST"
    HEADING_PARA = "HEADING_PARA"
    DASH_GLOSS = "DASH_GLOSS"


class RuleLane(StrEnum):
    """The two kinds of naming rule. They are both true and they read differently.

    FORM -- where the underscore goes, which case, what suffix. Mechanical, countable,
    usually checkable against the graph. Wants a table.

    VOCABULARY -- what a name may be drawn from or must mean: Latin only, always the
    binomial, a route name carries its functionality. Semantic, usually not mechanically
    checkable. Wants a paragraph, quoted whole.
    """

    FORM = "FORM"
    VOCABULARY = "VOCABULARY"


class Provenance(StrEnum):
    """Where a stated meaning came from. Never blended, never blurred.

    DECLARED_CODE -- a module docstring, parsed. Free.
    DECLARED_DOCS -- a glossary heading or a definition table, parsed. Free.
    CITED         -- a model found it in prose and cited file:line, and the citation
                     was verified against the file. Paid, and checkable.
    INFERRED      -- nothing states it; a guess. Paid, and not checkable.
    """

    DECLARED_CODE = "DECLARED_CODE"
    DECLARED_DOCS = "DECLARED_DOCS"
    CITED = "CITED"
    INFERRED = "INFERRED"


class DocRefKind(StrEnum):
    CODE = "CODE"    # a backticked identifier: `resolve_calls`, `mensores custos`
    PATH = "PATH"    # a path-shaped token: src/dunneflow/store.py
    URL = "URL"


@dataclass(slots=True)
class Heading:
    """One heading, and the trail of headings above it."""

    level: int
    text: str
    line: int
    path: str = ""    # "Naming rules > The pantheon"


@dataclass(slots=True)
class DocDefinition:
    """A term and what a document says it means. Kept whole, never summarised."""

    term: str
    definition: str
    line: int
    form: DefForm
    heading: str = ""
    source_line: str = ""


@dataclass(slots=True)
class DocRule:
    """A naming rule a document states, quoted verbatim."""

    text: str
    line: int
    lane: RuleLane
    scope: str = ""       # the identifier class it governs, when it names one
    pattern: str = ""     # snake_case, *_cmd, corpname_, a regex -- when it shows one
    heading: str = ""
    checkable: bool = False


@dataclass(slots=True)
class DocRef:
    """A reference out of prose and into the program."""

    kind: DocRefKind
    value: str
    line: int


@dataclass(slots=True)
class DocTable:
    """A table, header and every row, whole.

    The "pantheon" table pairs each component with its Latin name, its gloss, its
    historical accuracy and its trademark risk. Keeping only the gloss would throw away
    four columns that are the reason the table was written.
    """

    line: int
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    heading: str = ""


@dataclass(slots=True)
class DocFacts:
    """Everything one document yields. The unit of extraction and of caching."""

    path: str
    fmt: DocFormat
    content_hash: str
    title: str = ""
    doc_class: DocClass = DocClass.OTHER
    size: int = 0
    words: int = 0
    frontmatter: dict[str, str] = field(default_factory=dict)
    headings: list[Heading] = field(default_factory=list)
    definitions: list[DocDefinition] = field(default_factory=list)
    rules: list[DocRule] = field(default_factory=list)
    refs: list[DocRef] = field(default_factory=list)
    tables: list[DocTable] = field(default_factory=list)
    annotations: list[Annotation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Identity
# --------------------------------------------------------------------------- #


def make_id(*parts: str) -> str:
    """A stable id, derived from a thing's name and nothing else.

    Emphatically **not** from its file position. An id that includes a line number
    changes whenever anything above it moves, so adding a single import at the top of
    a file would retire every routine in that file and introduce identical
    replacements. Across a week of real work that renders a change view as thousands
    of false deletions and additions -- which is to say, as noise.

    Identity answers "is this the same routine?". Whether its contents changed is a
    separate question, answered by `Routine.body_hash`. Keeping the two apart is what
    makes a temporal view possible at all.

    A rename still reads as a removal plus an addition. That is honest: nothing in the
    source says the two are the same thing.
    """
    raw = "\x00".join(parts)
    return hashlib.blake2b(raw.encode("utf-8"), digest_size=8).hexdigest()


def hash_source(text: str) -> str:
    """Content hash of a source file, used to skip re-parsing unchanged files."""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
