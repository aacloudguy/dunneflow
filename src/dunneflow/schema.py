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
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePath
from typing import Literal

# Bump whenever the stored shape or the meaning of an extracted fact changes.
# A mismatch discards the graph and re-extracts: graph.db is derived data, and a
# stale map that answers confidently is worse than no map at all.
#
# **It stopped being load-bearing on 2026-09-17 and it is still here.** This file is in
# the core extraction key now, so a change to what a fact *is* moves the fingerprint
# whether or not anybody remembers this line -- which is rule 12's own failure mode, a
# forgotten bump leaving a confident map answering the previous version of the tool. What
# the number still does is two things a hash cannot: it is the generation a person reads
# off `meta`, and it is what a plugin declares it was written against, so a reader whose
# facts no longer fit is refused by name rather than by a hash nobody can interpret.
#
# 10: `files.extractor` -- which reader produced each row, per language.
# 11: `FileFacts.literals` -- a reader reports the strings, the host judges them.
# 12: `CallSite.is_construction`, and four `ArmKind` words TypeScript writes.
# 13: `SuppliedEdge` -- a reader whose toolchain resolves names says where a call goes.
# 14: `Entrypoint.declared` and `target_kind` -- a way in read out of a manifest,
#     said as fields rather than as a sentence somebody has to parse back.
# 15: identity carries the file. A routine, a structure and a way in are keyed on the file
#     they are written in as well as on their name (`definition_id`, rule 106). No column
#     moved and no field was added: what changed is what every id in a map is made of, so
#     every map written by 14 is discarded rather than read.
# 16: `CallSite.bound_locally`, and `calls.constructs`. A bare call to a name the routine
#     binds itself is not a call to whatever else in the program shares the name, and a
#     call that builds one of this program's own classes is not external (BACKLOG 24, 14).
SCHEMA_VERSION = 16


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


class TargetKind(StrEnum):
    """How to find the thing a **declared** way in names -- said, never inferred.

    `mensores.cli:app`, `./cli.js` and `src/main.rs` are three shapes of string and a
    fourth that looks like any of them is one guess away: `Path("mensores.cli:app").suffix`
    is `.cli:app`, which a reader looking for a language would report as a suffix nobody
    claims. The provider that read the manifest knows which kind it read, so it says
    (rule 30) -- and it is stored, because `render/markdown.py` and `anomalies.py` ask the
    question long after the provider has gone.

    `NONE` is a real answer rather than a failure. A Swift `.executable` product names a
    *target* and a Gradle `mainClass` names a class on a classpath; neither is a file this
    map holds or a module it can look up, and building a path out of either would be a
    claim about something nobody has evaluated.

    It is meaningful only where `Entrypoint.declared` is true. A way in recognised in code
    was not named by a target at all, and carries `NONE` because there is nothing to say.
    """

    MODULE_ATTR = "MODULE_ATTR"
    FILE = "FILE"
    NONE = "NONE"


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
    # `positional_only` is what sits before a `/`; `keyword` is what sits after a `*`.
    # Both markers are structure, not decoration -- a signature printed without them
    # is not the one in the file (rule 8 at ingest, rule 13 at the screen).
    kind: Literal["positional_only", "positional", "vararg",
                  "keyword", "kwarg"] = "positional"


def signature_parts(
    params: Sequence[tuple[str, str | None, str | None, str]],
) -> list[dict[str, str]]:
    """The parameter list as ordered pieces, **markers included**.

    One implementation, because there are two callers and a signature is the kind of thing
    that must not have two answers. `Routine.signature()` renders the line for the Markdown
    documents; the hover card needs the same sequence with the name and the type still told
    apart so it can colour them. Splitting one string back into its parts on the far side
    would be a second parser of something the first one already knew.

    The markers are the whole reason this is not a `join`. `def f(a, *, b)` and `def f(a, b)`
    are different functions -- the first cannot be called `f(1, 2)` -- and `signature()`
    rendered them identically for as long as it existed, because it handled the `*args` and
    `**kwargs` *prefixes* and never the bare separators between groups. A printed signature
    that is not the one in the file is rule 13 at the screen, and it is worse here than a
    missing signature would be: it is specific, plausible and wrong.

    `/` closes a run of positional-only parameters; `*` opens the keyword-only ones, and only
    when no `*args` has already opened them -- `def f(*a, b)` needs no separator because
    `*a` is one.
    """
    out: list[dict[str, str]] = []
    seen_star = False
    for i, (name, type_, default, kind) in enumerate(params):
        if kind == "keyword" and not seen_star:
            out.append({"text": "*", "marker": "*"})
            seen_star = True
        if kind == "vararg":
            seen_star = True

        prefix = {"vararg": "*", "kwarg": "**"}.get(kind, "")
        text = f"{prefix}{name}"
        if type_:
            text += f": {type_}"
        if default is not None:
            text += f" = {default}"
        piece = {"text": text, "name": f"{prefix}{name}"}
        if type_:
            piece["type"] = type_
        if default is not None:
            piece["default"] = default
        out.append(piece)

        # After the last of a run, never after each one.
        if kind == "positional_only" and (
            i + 1 == len(params) or params[i + 1][3] != "positional_only"
        ):
            out.append({"text": "/", "marker": "/"})
    return out


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
    """A structured marker mined out of a comment, a docstring, or prose.

    Governance IDs, audit locks, warnings -- the things that are load-bearing prose.

    `confidence` is CERTAIN when the marker was read as written: the string is on the
    line, and a reader can go and see it. It is INFERRED when the marker was composed
    from a naming convention rather than quoted -- a plan document that declares itself
    only as `phase:` and `plan:` in frontmatter never writes "Plan 68-03" anywhere, so
    the id is assembled and is a claim about a convention, not a quotation. Rule 6:
    never blur the two.
    """

    kind: str
    value: str
    line: int
    text: str = ""
    confidence: Confidence = Confidence.CERTAIN


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
    # **The host's answer, never the reader's** — blank until it is stamped, and never
    # `"python"`. It defaulted to `"python"` for as long as Python was the only reader
    # there was, which is a fact about a record that nothing in the record decided: a
    # plugin that forgot to say would have had every routine it emitted claim to be
    # Python, and the map would have been wrong in the one column nothing reads twice.
    # `FileFacts.lang` is the only place a language travels, `ingest.stamp_lang` is the
    # one place it is written onto the records below it (rule 51), and a record that
    # arrives carrying one of its own is refused rather than believed — two answers to
    # one question is how the two come to disagree.
    lang: str = ""
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
        rendered = ", ".join(part["text"] for part in signature_parts(
            [(p.name, p.type, p.default, p.kind) for p in self.params]))
        sig = f"{self.name}({rendered})"
        if self.returns:
            sig += f" -> {self.returns}"
        return sig


@dataclass(slots=True)
class CallArg:
    """One argument of one call, as the caller wrote it.

    The expression and nothing more. We do not record what it evaluates to, what type
    it is, or which parameter it lands on -- those are three different claims and only
    the first is visible in the source. Binding an argument to a declared parameter is
    the reader's question and is answered where the two are shown together, only where
    the alignment is unambiguous (rule 1: a false binding is worse than none).

    `idx` is the ordinal in the call **as written**, positional and keyword together,
    because that is the order a reader sees. `keyword` is set for `k=v` and nothing
    else. `splat` marks `*x` and `**x`, where what is passed is not one argument at all
    and no binding by position is possible.
    """

    idx: int
    expr: str
    keyword: str | None = None
    splat: bool = False


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
    # Identity of this one call, so two identical expressions on one line stay two
    # call sites and the arguments of each hang off the right one. Derived by
    # `call_site_id` -- from names and an ordinal, never from a position (`make_id`).
    site_id: str = ""
    args: list[CallArg] = field(default_factory=list)
    # **`new Foo()` is `Foo` and is not `Foo()`** -- `ingest/dotted.py` clause 7. The two
    # spellings call the same name and do two different things, and a map that flattened
    # them would say a routine calls `WebSocket` without saying it opens one (rule 30).
    # Declared here rather than earlier because a field nothing sets is a field nothing
    # can be trusted to set (rule 35): it arrived with the TypeScript reader that fills
    # it, and it is False for Python, which has no such syntax.
    is_construction: bool = False
    # **A bare call to a name this routine binds itself** -- a parameter, an assignment,
    # a loop or `with` target. `say = emit or (lambda _: None)` then `say(...)` calls
    # whatever `emit` held, and a resolver that matched it by name to the one routine in
    # the program called `say` drew an edge into another module's closure (BACKLOG 24,
    # rule 1). The reader knows the binding and the resolver does not, so the reader says.
    bound_locally: bool = False


@dataclass(slots=True)
class SuppliedEdge:
    """Where a call goes, according to a reader whose toolchain already knows.

    **The one fact in this file that is not about one file**, and that is why it is not a
    field on `FileFacts`. A type checker's answer for `a.ts` is built out of `b.ts`, so an
    edge filed under its caller would go stale the moment `b.ts` moved a function and
    `a.ts` did not change -- the line it names would then point at whatever had drifted
    into that position, and nothing would be re-read to notice. So supplied edges are a
    whole-program answer, asked once per session and **replaced whole**; a run that reads
    no file of a language changes none of its edges, and they are still true because
    nothing of that language changed.

    **A target is named by location and never by id** (`PLAN-v2.md` §1g). A plugin minting
    ids would be a second implementation of `make_id`, in the one place a disagreement is
    least recoverable: two ids that look exactly like ids and match nothing. The host looks
    the location up among the routines it stored, and a location that matches none is an
    **external** call -- the call certainly happens and this map cannot see the other end,
    which is rule 26 by construction rather than by luck.

    `candidates` is the honest answer where the checker gave several declarations -- a
    merged overload set, an `any`-typed receiver, `obj[k]()`. It is **no edge**, with the
    count recorded exactly as Python already records a name collision, and it is never
    `INFERRED`: that word is a claim that a name-uniqueness argument was made, and for a
    checker none was made or needed (rule 6).

    `how` is which question the checker answered -- `signature` for
    `getResolvedSignature`, `symbol` for a lone declaration behind a symbol. Evidence for
    a reader, never a condition: the host does the same thing with either.
    """

    site_id: str
    caller_id: str
    # The **target's** stored path, relative and POSIX (rule 93). Empty where there is no
    # target, which is what a row carrying only `candidates` is.
    file: str = ""
    line: int = 0
    # What the target is called. The host checks it against the routine it matched rather
    # than trusting the line alone: a line that has drifted lands on some routine, and a
    # silently wrong edge is worse than a missing one (rule 1).
    name: str = ""
    how: str = ""
    candidates: int = 0


class ControlKind(StrEnum):
    """The four shapes a routine's body takes, and nothing else.

    No `IfExp`, no boolean operator, no `assert`: those are expressions, and an
    expression that chooses between two numbers is the arithmetic this tool exists not
    to report. `GUARD` is a `DECISION` narrowed by how it *ends* rather than by how it
    is written, because that is what makes it a different thing to read -- 3,937 of
    Mensores' 6,293 branches are refusals, and a refusal is a precondition stated in
    code.
    """

    LOOP = "LOOP"                    # for / async for / while
    COMPREHENSION = "COMPREHENSION"  # list, set, dict, generator -- a loop that is an expression
    DECISION = "DECISION"            # if / elif ladder / match
    GUARD = "GUARD"                  # a one-armed decision that leaves: return/raise/continue/break
    HANDLER = "HANDLER"              # try -- a decision about failure


class ArmKind(StrEnum):
    """The word in the source, and nothing invented.

    Nine words for Python, because Python has nine ways to open one arm of something.
    `ELSE` appears once and means three different things -- after a `for`, after a `try`,
    after an `if` -- and it is the *point's* kind that says which, exactly as it is for the
    reader looking at the line. Naming them `LOOP_ELSE`, `TRY_ELSE` and `ELSE` would put
    a distinction in the data that the source does not make (rule 30's neighbour).

    **Four more for TypeScript, and the rule is what chose them rather than a list.**
    `PLAN-v2.md` said *catch, do, switch*; two of those are right and the third is not,
    which is what reading the rule above rather than the plan's summary gets you. A
    `switch` is a **point**, and its arms are `case` -- which is already here -- and
    `default`, which was not. And TypeScript has no `elif`: it writes `else if`, two words,
    which is exactly what its arm is called. Python's ladder is one word and TypeScript's
    is two, and flattening either onto the other would be inventing a word for a reader to
    find in a file that does not contain it.

    A value is **added and never reused**: `EXCEPT` is Python's word and `CATCH` is
    TypeScript's, and spelling one language's arm with the other's word is the same defect
    as renaming it.
    """

    IF = "if"
    ELIF = "elif"
    ELSE = "else"
    ELSE_IF = "else if"     # TypeScript's ladder; `elif` is Python's word and only Python's
    CASE = "case"
    DEFAULT = "default"     # the last arm of a `switch`
    TRY = "try"
    EXCEPT = "except"
    CATCH = "catch"         # TypeScript's word for Python's `except`
    FINALLY = "finally"
    FOR = "for"      # also `async for` -- the arm is the body, and `async` is not a way out
    WHILE = "while"
    DO = "do"               # `do { ... } while (x)` -- the body is entered before the test


@dataclass(slots=True)
class ControlPoint:
    """A loop or a decision inside one routine: **a line range, and nothing more.**

    This is the one fact that amends `CLAUDE.md`'s founding exclusion, and the shape of
    it is what keeps that amendment narrow. Control flow is not reported *as* control
    flow; a control point is a **span**, and everything about what it does is reached by
    joining the tables that already exist -- `boundaries`, `net_calls`, `sql_ops` and
    `calls` each carry `routine_id` and `line`. So a loop holding a network call is not
    a new relationship, it is `line BETWEEN line_start AND line_end`. Nothing here
    records a variable, an operator, or a value.

    That is also why there is no control-flow graph and no dominator analysis. Those
    exist to recover structure that a `goto` destroyed, and Python source never lost it:
    `ast` hands back the nesting exactly as written. Nassi and Shneiderman made the same
    observation in 1972 and drew structured code as nested boxes with no arrows at all.

    `depth` is control nesting, which is **not** `Routine.is_nested` -- that one counts
    enclosing *functions*, and the two disagree on every closure.

    `arms` is the branch count: an `elif` ladder flattened to the number of ways out
    (2 for a plain if/else, 4 for `if/elif/elif/else`), a `match`'s case count, a `try`'s
    handler count, and 1 for a loop. Flattened at extraction because an `elif` is an
    `If` in the `orelse` of an `If`, so the tree shape says "2 arms" seven times where a
    reader sees one decision with seven ways out.
    """

    # Identity of this one point, so an arm can name the point it belongs to and a
    # reader can keep a loop (rule 30: a label is not an identity). Derived by
    # `control_point_id` from names and an ordinal, never from a position, for
    # `call_site_id`'s reason -- a span whose id held its own line number would be a
    # different loop after every import added above it.
    point_id: str
    routine_id: str
    kind: ControlKind
    line_start: int
    line_end: int
    depth: int
    # As written, sliced from the file's own bytes on **byte** offsets (rule 75) and
    # never re-rendered by `ast.unparse` -- for `call_args`' reason. `for seal in
    # spec.seals`, `if not spec.seals`, `except TimeoutError`. Never shortened here;
    # what a surface does about a long one is the surface's decision (rule 8).
    header: str = ""
    arms: int = 1
    # How a GUARD leaves: return | raise | continue | break. Empty for every other kind.
    # Recorded rather than inferred from the header, because "if not x: return" and
    # "if not x: raise" are the same sentence and opposite facts.
    exits: str = ""
    # **The word that opens the point, as the source wrote it**: `for`, `async for`,
    # `while`, `if`, `try`, `match`, and `""` for a comprehension, which opens with a
    # bracket. `exits`' own argument one kind over: `for x in y` and `while y` are both
    # `ControlKind.LOOP` and opposite facts about whether the header runs again, and a
    # header of `True` is `while True` to a reader and a guess to a matcher (rule 30).
    word: str = ""
    # **The lines this point evaluates once, before the first pass.** A `for`'s iterable
    # and a comprehension's first generator; 0/0 for a `while`, whose test re-runs, and
    # for every decision, guard and handler, which repeat nothing.
    #
    # It is the iterable's span **minus every line a repeated part of this point also
    # occupies**, and the subtraction is the whole fact. The iterable's span alone
    # reclassifies 45 of Society's loops and 34 of them wrongly, because
    # `[fetch(x) for x in ids]` writes its element and its iterable on one line and a line
    # cannot choose between them. Subtracting leaves the range empty there -- nothing is
    # excluded, which is the answer that cannot be wrong (rule 49: a plausible fallback is
    # what hides the failure). Contiguous by construction: a `for`'s body is strictly
    # after its iterable and a comprehension's element strictly before it, so the
    # subtraction only ever trims an end.
    #
    # Why it is a fact and not something the resolver works out (rule 85): `line BETWEEN
    # line_start AND line_end` reads the iterable as part of the body, so `for row in query():`
    # reported one query as a query per pass -- 11 of Society's 261 rates, in the sentence
    # that is the feature's headline. Four statements in `web/queries.py` ask the same
    # range question in SQL and cannot import the resolver, so the answer has to be a
    # column they can read (rule 51).
    once_start: int = 0
    once_end: int = 0


@dataclass(slots=True)
class ControlArm:
    """One way out of a decision: **another span, belonging to a point.**

    A `ControlPoint` says *there is a decision here and it has four ways out*. It cannot
    say **which** way out writes to a table, and that is the whole question -- a branch
    whose arms compute different numbers is the arithmetic this tool excludes, while a
    branch where one arm writes to a table and the other does not is a decision about
    what leaves the program. Measured over Society: 78 of its 2,213 decisions differ in
    what moves between their arms, and 396 of its 1,531 handlers recover by moving
    something. Neither number can be asked of the point alone.

    So an arm is the same kind of fact as a point, one level in: a routine, a line range,
    and the words as written. No variable, no value, no control-flow graph.

    **The arms do not cover the point.** They are the *bodies*: an `elif`'s own test line
    belongs to no arm, and a boundary reached from inside a test -- `if fetch_row():` --
    is a fact about the decision rather than about either way out of it. Attributing it
    to the arm above it would be a position mistaken for a meaning (rule 1).

    `kind` is the **word in the source**: `if`, `elif`, `else`, `case`, `try`, `except`,
    `finally`. The point's own kind is what disambiguates the three `else`s Python has --
    a `for`'s (no `break`), a `try`'s (no exception), and a decision's -- because that is
    the distinction the *reader* makes, standing at the line.

    **Recorded only where a point has more than one way through it.** A plain `if` with
    no `else`, a `for` with no `else`, a `GUARD` -- each has one arm, which is its own
    span, and a row saying so again would be a second answer to a settled question
    (rule 41). Society records 2,269 arms over 1,689 points, against 9,625 points in all.

    The `if` arm's header is the point's header, by construction and from the same node,
    so the two cannot disagree (rule 13). It is written on both because a ladder has to
    be readable from its arms alone -- `if` / `elif` / `else`, each with its own test --
    and an arm with no header where every sibling has one reads as a missing fact.
    """

    point_id: str
    routine_id: str
    # Position among this point's arms, in source order: 0 is the `if` body, the `try`
    # body, the first `case`. An ordinal within one point, which is what `idx` means
    # everywhere else here (`CallArg`, `Field_`) -- never a line.
    idx: int
    kind: ArmKind
    line_start: int
    line_end: int
    # The clause as written, sliced on byte offsets (rule 75): `elif seal.kind ==
    # "witness"`, `except TimeoutError as exc`, `case "retry"`. Empty for `else`,
    # `finally` and a `try` body, which have no test to quote -- the word is the header,
    # and it is already in `kind`.
    header: str = ""


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
    # Blank until the host stamps it, exactly as `Routine.lang` is. See there.
    lang: str = ""
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
    # **Was this read out of a manifest, or recognised in code?** A field, because it was
    # a substring test -- `"[project.scripts]" in e.evidence` at `flows.py:259` -- against
    # a sentence `web/waysin.py:120` renders verbatim. It is the primary sort key of the
    # way-in list, so a `package.json` `bin`, which can never match that string, would
    # have ranked below a guessed name for ever (rule 30).
    #
    # **Host-owned** (`ingest.codec._HOST_OWNED`): a reader may never send it. A manifest
    # is read by `resolve/manifests`, in this process, after extraction -- a plugin has
    # not seen one and has nothing to say about the question.
    declared: bool = False
    # What kind of thing `target_expr` names, where this was declared. See
    # `TargetKind`: a module-and-attribute, a file, or a name this tool cannot
    # turn into a place to open. Host-owned for `declared`'s reason.
    target_kind: TargetKind = TargetKind.NONE


@dataclass(slots=True)
class Constant:
    """A value the program names at module level, and the comment explaining why.

    Added because `JTBD_OPENERS` is declared in `_prompts.py`, read six times, and the
    map could not say it existed: `visit_Assign` caught only CLI app objects, class
    bodies became `Field_`, and module level became nothing. A constant is a name a
    person chose for a value -- the same argument that made `Artefact` a fact type --
    and 2,489 of them on Mensores carry the program's configuration: model names, token
    ceilings, directory names, retry limits.

    Module level means *runs at import*, so a constant inside a module-level `try` or
    `if TYPE_CHECKING` counts, and one inside a function does not. That is the same
    boundary the module scope already uses for comments and for boundaries.

    `value` is the assigned expression whole, never shortened -- rule 8. A ceiling cut
    off at eighty characters is no longer the ceiling.
    """

    name: str
    value: str                    # the assigned expression, as written
    line: int
    type: str | None = None       # the declared annotation, where there is one
    is_final: bool = False        # `Final[...]`, which says it is not meant to be rebound
    comment: str | None = None    # the WHY, from the comment beside or above it
    private: bool = False         # leading underscore: internal to the module


class LiteralKind(StrEnum):
    """Whether the text is what the file says, or what the file would assemble.

    Two facts that look identical once they are a string, and telling them apart is the
    whole reason this field exists. `"chaos_?.py"` is a glob a person wrote; the `?` in
    `f"{stem}.py"`'s reported text is the placeholder the reader left where a value goes.
    A judgement that cannot tell them apart has to treat every `?` as one or the other,
    and both readings are wrong half the time (rule 30).
    """

    PLAIN = "PLAIN"
    INTERPOLATED = "INTERPOLATED"


@dataclass(slots=True)
class StringLiteral:
    """A string the source spells out, reported so the **host** can judge what it means.

    The one fact a reader is asked for and told not to interpret. What a string *is* --
    a SQL statement, the name of a file, or prose that happens to contain a dot -- is one
    question with one answer, and a plugin that answered it for its own language would
    make the same text read two ways in a `.py` and a `.ts` (rule 51, in the fact
    contract, which is the most expensive place to have it). So `ingest/literals.py`
    decides, for every language at once, and `detectors/<lang>.yaml` stays the extension
    point: adding an extension is a YAML edit and never a plugin rebuild.

    `text` is the string **whole and as the reader resolved it** (rule 8): a 200 KB
    schema block is stored entire, because a DDL statement cut off at eighty characters
    is no longer the schema. An interpolated string arrives with its interpolations
    already stood in for -- that needs the syntax tree and so is the reader's -- and
    `kind` says so, because the placeholder is otherwise indistinguishable from a
    character somebody typed.

    `routine_id` is the routine the string sits in, decided where the reader was standing
    when it saw it. The host cannot recompute it: by the time facts arrive, a line number
    is all that is left of where anything was.
    """

    routine_id: str
    line: int
    text: str
    kind: LiteralKind = LiteralKind.PLAIN


@dataclass(slots=True)
class Artefact:
    """A file the program names: a database, a config, a script, a document.

    Added because `tabularium.db` -- the single most-referenced name in Mensores, 50
    quoted occurrences -- appeared nowhere in the map. It is built as
    `repo_root / ".mensores" / "tabularium.db"`, so it is not a module, not a table,
    and not a boundary target: the path is assembled from parts and only the parts
    are literals. A program names its artefacts as deliberately as it names its
    packages, and the words it chooses are part of its vocabulary. 101 distinct ones
    in Mensores, and DunneFlow could see none of them.

    One row per reference site, never deduplicated at ingest, so "how often is this
    named, and by whom" is answerable and rule 8 holds.
    """

    name: str            # basename as written -- "tabularium.db"
    stem: str            # basename minus its final extension -- "tabularium"
    ext: str             # lowercased, no dot -- "db"
    kind: str            # DATABASE | CONFIG | SCRIPT | DOCUMENT | DATA | ARCHIVE
    routine_id: str
    line: int
    literal: str         # the whole literal as written, never shortened (rule 8)
    is_pattern: bool = False   # `chaos_*.py` names a set, not a file


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
    artefacts: list[Artefact] = field(default_factory=list)
    constants: list[Constant] = field(default_factory=list)
    control: list[ControlPoint] = field(default_factory=list)
    control_arms: list[ControlArm] = field(default_factory=list)
    # Every string this file spells out, for the host to judge. `sql`, `tables`, `indexes`
    # and `artefacts` above are **filled from these, by the host**, and a reader that sends
    # literals must not also send those (`ingest.literals.judge` refuses it): two answers to
    # one question, and only ever noticed when they differ.
    literals: list[StringLiteral] = field(default_factory=list)
    # The routine module-level code belongs to, **prepared and not claimed**. A file's
    # module scope is a routine only where something belongs to it, and a reader cannot
    # know that about a string: what a string *means* is `ingest.literals.judge`'s answer,
    # and this is what lets it claim the scope after it has one. Where the reader has
    # already recorded module-level work -- a call, a constant, a comment -- the same
    # routine is in `routines` and this is the same object; where it has not, this is a
    # row nobody has claimed and it stays out of the map.
    module_scope: Routine | None = None
    # Strings the reader did not send because they fall outside `ingest.literals`' bound.
    # A count and not a list, because the thing to know is whether the number is zero; a
    # filter nobody can see is design rule 1's subject, and this one runs in a process the
    # host cannot look inside.
    literals_dropped: int = 0
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
DOC_SCHEMA_VERSION = 6


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


def stored_path(rel: Path | str) -> str:
    """One relative path, spelled the way every store keeps it: with forward slashes.

    **Rule 93, and it is rule 60 one platform over.** That rule made a stored path
    relative because an absolute one is a bad key -- it names one machine's directory
    layout, so two revisions read from two trees give one file two unrelated keys and
    nothing can pair it across time. A path spelled with the *separator of the machine
    that wrote it* is a bad key for exactly the same reason: `web\\serve.py` and
    `web/serve.py` are the same file and two different keys, so a map written on Windows
    and a map written on macOS cannot be compared, and neither can read the other's.

    It is not only the pairing. A stored path is read back as a **POSIX** path all over this
    tool, by code that was right when there was only one platform: `conformance` matches a
    rule's `paths:` glob against it and splits it with `PurePosixPath`, `threads` takes its
    last segment, and the shell draws a leaf with `split("/")` -- each of which silently
    yields the whole path, or nothing, when the separator is a backslash. The conformance
    lane is the sharpest: `files / kebab-case` measured **0 of 78** against a population it
    had quietly failed to find, which is rule 49's shape in the surface built to refuse it.

    So the separator is decided **here**, once, and every writer of a `path` or `file`
    column passes through it (rule 51). It was six spellings of `str(p.relative_to(root))`
    and `os.path.relpath(...)` in six modules, every one of them correct on the machine it
    was written on.

    `PurePath` is the platform's own parser and that is deliberate: on Windows it splits on
    both separators, and on POSIX it splits on neither -- where a backslash is an ordinary
    character in a filename and must survive as one. Nothing here re-spells a path the
    running platform would not.
    """
    return PurePath(rel).as_posix()


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


def definition_id(file: str, qualname: str, ordinal: int = 1) -> str:
    """Identity of one definition -- a routine or a data structure.

    **The file is in it, and that is rule 106.** A qualified name is only unique inside one
    language's way of naming things, and two languages in one directory do not share one.
    `probe.py` and `probe.ts` are both module `probe`, both declare `main`, and `probe.main`
    was one id in two languages -- so a tree holding them could not be analysed at all:

        sqlite3.IntegrityError: UNIQUE constraint failed: routines.id

    The discriminator is the **file** and not the language, because the language does not
    close it: `probe.ts` and `probe.tsx` are one module in *one* reader, and a `lang` part
    would leave that collision exactly where it was. A file is the smaller claim and the true
    one -- a definition is written down somewhere, once.

    It is not a position (`make_id`). A file is where a definition *lives*, which survives
    everything moving inside it; a line is where it happens to sit today, which does not.
    Moving a routine between files reads as a removal and an addition, which is the same
    honesty a rename gets and for the same reason: nothing in the source says the two are
    the same thing.

    `ordinal` tells apart real duplicates -- an overload set, a name declared twice -- and is
    the same discriminator, and the same stated residue, as `call_site_id`'s. It counts from
    1, and 1 is spelled by leaving the part off, so the first declaration of a name keeps the
    plain two-part id.
    """
    return make_id(file, qualname) if ordinal == 1 else make_id(file, qualname, f"#{ordinal}")


def entrypoint_id(file: str, *parts: str) -> str:
    """Identity of one way in: the file that declares it, and whatever names it there.

    `definition_id`'s argument, one table over, and the parts after the file are each
    reader's own because a way in is not spelled one way -- a decorator and a name, a route
    and a verb, a routine's qualname, a conventional `main`. What is shared is the namespace
    and the file, which is what stops two readers of one directory minting one id (rule 106).

    Three of the four readers already carried the file and Python did not; it was safe only
    because no other reader minted an `ep` from a module name, which is a fact about today's
    set of readers rather than about ids. `resolve/entrypoints.py` mints `make_id("script",
    ...)` and is deliberately **not** here: those come from a manifest's declaration rather
    than from reading a file, and that function says so.
    """
    return make_id("ep", file, *parts)


def call_site_id(caller_id: str, callee_expr: str, ordinal: int) -> str:
    """Identity of one call site -- position-free, like every other id here.

    Two identical expressions in one routine are two call sites and have to stay two,
    or the arguments of one land on the other. The only discriminator available that is
    not a position is an **ordinal among identical expressions in the same caller**:
    `make_id` is explicit that a line number would retire every fact below an inserted
    import.

    The residue is stated rather than hidden. Adding a *third* `emit()` between the
    first two re-numbers the ones after it, so those sites read as changed when nothing
    about them did. That is a narrower loss than a line number, which moves everything
    below anything, and it is bounded by how often one routine calls one name twice.
    """
    return make_id("site", caller_id, callee_expr, str(ordinal))


def control_point_id(routine_id: str, kind: str, header: str, ordinal: int) -> str:
    """Identity of one control point -- position-free, like every other id here.

    A routine may hold two identical loops: `for line in lines:` twice is two spans, and
    an arm of one must never hang off the other. The discriminator is `call_site_id`'s,
    for `call_site_id`'s reason -- an **ordinal among identical writings in the same
    routine**, because a line number retires every fact below an inserted import.

    A `try` has no header, so a routine's handlers are told apart by the ordinal alone.
    The residue is the same one and is stated rather than hidden: inserting a third
    `try` between the first two renumbers the ones after it, and those points read as
    changed when nothing about them did.
    """
    return make_id("control", routine_id, kind, header, str(ordinal))


def hash_source(text: str) -> str:
    """Content hash of a source file, used to skip re-parsing unchanged files."""
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
