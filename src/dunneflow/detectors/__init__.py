"""Loading and matching of the declarative detector rules.

The rules themselves live in the YAML files beside this module. Keeping matching
here and rules there is what makes "teach it about a new framework" a config edit.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..runtime import resource_root
from ..schema import (
    Annotation,
    BoundaryKind,
    Confidence,
    Direction,
    EntrypointKind,
    stored_path,
)

# Through `resource_root()` rather than `Path(__file__)`, and the difference only shows
# frozen: `__file__` for a module imported out of a PyInstaller archive names a path that
# does not exist on disk, so `RULES_DIR.glob("*.yaml")` comes back empty and the
# fingerprint below hashes nothing at all. Settled once at import, because an application
# does not become a source checkout halfway through a run.
_PKG_ROOT = resource_root()
RULES_DIR = _PKG_ROOT / "detectors"


class RulesMissing(RuntimeError):
    """The files that decide what extraction *means* are not where this build looks.

    Never a reader's mistake and never recoverable in place: it says this copy of
    DunneFlow was assembled without the rules and the extractors it hashes, which is a
    build defect. Raised rather than defaulted, because the default is a hash of nothing
    and that is indistinguishable from a real answer (rule 49).
    """


# **The evidence separator.** A boundary's evidence is the call's dotted spelling, which
# `ingest/acts.py` folds chains by; a rule's `note` and an undecided rule's blind spot
# follow it after this, so the spelling is always the part before it.
EVIDENCE_NOTE = " — "


@dataclass(slots=True, frozen=True)
class ArgCondition:
    """`when_arg`: a rule that applies only for some values of one argument.

    `net.Dial("unix", p)` is a Unix socket and `net.Dial("tcp", a)` is the network, and the
    dotted name cannot tell them apart. The argument's *value* is a string literal's
    contents, and otherwise its source text, which is how a dotted constant such as
    `socket.AF_UNIX` is named. **Three answers, never two** (rule 49): a value in `in_`
    decides yes; any other literal, a `not_in` entry or an absent argument decides no; and
    anything else -- a variable, a call -- is *undecided*, which never matches and is said
    as the blind spot of whatever rule does.
    """

    index: int | None = None
    keyword: str = ""
    in_: frozenset[str] = frozenset()
    not_in: frozenset[str] = frozenset()
    # A keyword whose presence means the value comes from somewhere the source does not
    # say: `socket.socket(fileno=0)` takes its family from the descriptor.
    undecided_if_keyword: frozenset[str] = frozenset()

    def decide(self, positional: Sequence[tuple[str, bool]],
               keywords: dict[str, tuple[str, bool]]) -> bool | None:
        """`positional` and `keywords` hold `(value, is_literal)` for each argument."""
        value: tuple[str, bool] | None = None
        if self.keyword and self.keyword in keywords:
            value = keywords[self.keyword]
        elif self.index is not None and self.index < len(positional):
            value = positional[self.index]
        if value is None:
            if any(k in keywords for k in self.undecided_if_keyword):
                return None
            return False
        text, literal = value
        if text in self.in_:
            return True
        if literal or text in self.not_in:
            return False
        return None


@dataclass(slots=True, frozen=True)
class ReceiverMethod:
    """One `on_receiver` entry: a method called later on the name a matched call is bound
    to, and what touching it means."""

    direction: Direction
    target_arg: int | None = None


@dataclass(slots=True)
class BoundaryRule:
    kind: BoundaryKind
    direction: Direction
    salience: str = "normal"
    exact: frozenset[str] = field(default_factory=frozenset)
    prefix: tuple[str, ...] = ()
    method: frozenset[str] = field(default_factory=frozenset)
    subscript: frozenset[str] = field(default_factory=frozenset)
    contains: tuple[str, ...] = ()
    target_arg: int | None = None
    when_arg: ArgCondition | None = None
    # Said on whatever rule matches instead, when `when_arg` could not decide.
    undecided: str = ""
    # A fixed phrase appended to the evidence: `unix.GetsockoptUcred — peer credentials`.
    note: str = ""
    on_receiver: dict[str, ReceiverMethod] = field(default_factory=dict)

    def matches_call(self, dotted: str) -> bool:
        if not dotted:
            return False
        if dotted in self.exact:
            return True
        if self.prefix and dotted.startswith(self.prefix):
            return True
        if self.contains and any(c in dotted for c in self.contains):
            return True
        if self.method:
            last = dotted.rsplit(".", 1)[-1]
            # A bare name is a plain function call, not a method on something.
            if "." in dotted and last in self.method:
                return True
        return False


@dataclass(slots=True)
class EntrypointRule:
    kind: EntrypointKind
    decorator_method: frozenset[str]
    evidence: str = ""

    def matches_decorator(self, dotted: str) -> bool:
        if not dotted:
            return False
        return dotted.rsplit(".", 1)[-1] in self.decorator_method


@dataclass(slots=True)
class AnnotationRule:
    kind: str
    regex: re.Pattern[str]


@lru_cache(maxsize=1)
def load_annotation_rules() -> tuple[AnnotationRule, ...]:
    """Annotation patterns are language-independent -- comments are comments."""
    path = RULES_DIR / "annotations.yaml"
    if not path.exists():
        return ()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return tuple(
        AnnotationRule(kind=r["kind"], regex=re.compile(r["regex"]))
        for r in data.get("patterns", [])
    )


@dataclass(slots=True)
class DocumentIdentityRule:
    """An id composed from a document's own identity rather than read from its prose.

    Always INFERRED. The document does not state this in words; the rule assembles it
    from a naming convention, and a convention can be wrong, superseded, or simply not
    the one in force when the file was written.
    """

    kind: str
    fmt: str
    part: tuple[re.Pattern[str], ...]
    frontmatter: tuple[str, ...] = ()
    filename: re.Pattern[str] | None = None

    def _compose(self, parts: list[str]) -> str | None:
        """Every part must yield a number. Half an id is not an id."""
        if len(parts) != len(self.part):
            return None
        numbers: list[str] = []
        for raw, pattern in zip(parts, self.part, strict=True):
            m = pattern.search(raw or "")
            if not m:
                return None
            numbers.append(m.group(1) if m.groups() else m.group(0))
        try:
            return self.fmt.format(*numbers)
        except (IndexError, KeyError, ValueError):
            return None

    def from_frontmatter(self, meta: dict[str, str]) -> str | None:
        if not self.frontmatter or any(k not in meta for k in self.frontmatter):
            return None
        return self._compose([str(meta[k]) for k in self.frontmatter])

    def from_filename(self, basename: str) -> str | None:
        if self.filename is None:
            return None
        m = self.filename.match(basename)
        return self._compose(list(m.groups())) if m else None


def _part_patterns(spec: str | list[str], count: int) -> tuple[re.Pattern[str], ...]:
    """One pattern per part. A scalar applies to every part."""
    if isinstance(spec, str):
        return tuple(re.compile(spec) for _ in range(count))
    return tuple(re.compile(p) for p in spec)


@lru_cache(maxsize=1)
def load_document_identity_rules() -> tuple[DocumentIdentityRule, ...]:
    path = RULES_DIR / "annotations.yaml"
    if not path.exists():
        return ()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return tuple(
        DocumentIdentityRule(
            kind=r["kind"],
            fmt=r["format"],
            part=_part_patterns(r.get("part", r"(\d+)"),
                                len(r.get("frontmatter", [])) or 1),
            frontmatter=tuple(r.get("frontmatter", [])),
            filename=re.compile(r["filename"]) if r.get("filename") else None,
        )
        for r in data.get("document_identity", [])
    )


def identify_document(meta: dict[str, str], basename: str) -> list[Annotation]:
    """Ids a document states about itself without writing them out.

    Line 0, because there is no line to point at -- that absence is the honest signal
    that this was assembled rather than quoted, and the renderer says so in words.
    """
    out: list[Annotation] = []
    seen: set[tuple[str, str]] = set()
    for rule in load_document_identity_rules():
        for value, how in (
            (rule.from_frontmatter(meta), "frontmatter"),
            (rule.from_filename(basename), "filename"),
        ):
            if not value or (rule.kind, value) in seen:
                continue
            seen.add((rule.kind, value))
            out.append(Annotation(
                kind=rule.kind, value=value, line=0,
                text=f"composed from the document's {how}; not stated in its prose",
                confidence=Confidence.INFERRED,
            ))
    return out


@lru_cache(maxsize=1)
def _any_annotation_rule() -> re.Pattern[str]:
    """One regex that matches whatever any annotation rule would match.

    A cheap gate for scanning prose, where there are a million lines and nine patterns.
    It is *derived from the rules themselves* rather than hand-written: a hand-kept
    prefilter drifts the moment someone adds a rule, and a gate that silently hides a
    new rule is the same silent no-op that has cost this project three bugs already.
    """
    return re.compile("|".join(f"(?:{r.regex.pattern})" for r in load_annotation_rules()))


def has_annotation(text: str) -> bool:
    """Whether mining this text could possibly yield anything. Never a false negative."""
    return bool(_any_annotation_rule().search(text))


def mine_annotations(text: str, line: int) -> list[Annotation]:
    """Pull every structured marker out of one comment or docstring."""
    out: list[Annotation] = []
    seen: set[tuple[str, str]] = set()
    for rule in load_annotation_rules():
        for m in rule.regex.finditer(text):
            value = m.group(1) if m.groups() else m.group(0)
            key = (rule.kind, value)
            if key in seen:
                continue
            seen.add(key)
            # The whole comment, not an opening fragment: the warning is often in
            # the second sentence.
            out.append(Annotation(kind=rule.kind, value=value, line=line,
                                  text=" ".join(text.split())))
    return out


@dataclass(slots=True)
class RuleSet:
    boundaries: list[BoundaryRule]
    entrypoints: list[EntrypointRule]
    entry_names: frozenset[str]
    subscript_index: dict[str, BoundaryRule]
    cli_factories: frozenset[str] = field(default_factory=frozenset)
    cli_mounts: frozenset[str] = field(default_factory=frozenset)
    cli_launches: frozenset[str] = field(default_factory=frozenset)
    handler_bases: dict[str, str] = field(default_factory=dict)
    handler_methods: frozenset[str] = field(default_factory=frozenset)
    net_libraries: tuple[tuple[str, str, bool], ...] = ()
    net_verbs: frozenset[str] = field(default_factory=frozenset)
    net_kwargs: dict[str, frozenset[str]] = field(default_factory=dict)
    # extension (lowercased, no dot) -> artefact kind. See `artefacts` in the YAML.
    artefact_kinds: dict[str, str] = field(default_factory=dict)
    # Subscript bases and call factories that make an assignment a type alias.
    alias_constructors: frozenset[str] = field(default_factory=frozenset)
    alias_factories: frozenset[str] = field(default_factory=frozenset)
    # Names a bare call may mean without this program having defined them, so a bare call
    # is never resolved inward to a routine that happens to share one (rule 3). Declared
    # per language rather than read off this interpreter, because `dir(builtins)` is a
    # fact about the **analysing machine's** version and it is an input to what a call
    # means -- which put it outside every fingerprint. See `builtins` in the YAML.
    builtins: frozenset[str] = field(default_factory=frozenset)
    # **What it means to create an async call and throw the result away**, declared
    # because it is a fact about the language and not about the call. Python's coroutine
    # is *inert*: never awaited, it never runs, and the work simply does not happen --
    # which is a defect of the first order. A JavaScript promise *runs*: dropping it
    # loses the ordering and, without a `.catch`, the failure, but the request is made.
    #
    # One detector reads it, `anomalies.ASYNC_NOT_AWAITED`, and until 2026-09-18 that
    # detector said *"The coroutine is created and never run"* of every language. Put to
    # gstack it produced two BROKEN findings out of the command that gates CI on BROKEN,
    # and one of them was three lines under the comment *"No await; this is
    # fire-and-forget"* with a `.catch(() => {})` on the end of it. Correct code, called
    # broken, in Python's vocabulary, about a language with no coroutines in it (rule 98).
    #
    # **Empty means the detector does not fire for that language**, which is rule 49's
    # shape: a severity is a claim about what a discarded promise costs, and a language
    # nobody has declared this for is one nobody has answered that question about.
    # Defaulting to either answer would put a guess in the one command a CI job trusts.
    unawaited_async: str = ""
    # **What `visibility = 'private'` means in this language**, which the naming lane's
    # LEAKAGE claim depends on and which differs by language (rule 98, the fourth time).
    # *module*: a spelling convention that keeps a name inside its file (Python's `_x`,
    # TypeScript's `_x`/`#x`), so a call from another module is a leak. *package*: Go's
    # unexported name, visible to every file in its directory. *surface*: the schema's two
    # values fold a wider word into `private` -- Rust's `pub(crate)`, Kotlin's `internal`,
    # C++'s class member -- so a call from another file is correct code, and the claim is
    # not measured. pdfcraft reported 624 "leaks" under Python's reading, 440 of them
    # `pub(crate)` doing what it says. Empty means not measured; an unknown word is refused.
    private_means: str = ""
    # **What a second definition of one name means**, declared for the same reason and
    # found the same way — by running a correct new reader at an unchanged judgement
    # (rule 98, the third time).
    #
    # Python *shadows*: a second `def foo` replaces the first, the earlier one is
    # unreachable, and `NAME_COLLISION` is right to call that BROKEN. C++ *overloads*: a
    # second definition with a different parameter list is a **different routine**, which
    # is not a defect but the language's ordinary mechanism. Unreal's `Core` alone answers
    # `operator<<` 180 times, `operator=` 61, `FName::FName` 36 — and the first run of the
    # C++ reader produced **3,875 BROKEN** out of the command `dunneflow check` gates CI
    # with, every one of them a sentence in Python's vocabulary: *"Only the last one exists
    # at run time; every call resolves to it and the others are unreachable."*
    #
    # **Empty means the detector does not fire**, as above. A language nobody has answered
    # this for gets no claim made on its behalf.
    redefinition: str = ""
    # **What a file runs when a manifest says it is a program.** A `bin` in `package.json`
    # or a `[[bin]]` in `Cargo.toml` names a file, and for Python and TypeScript what runs
    # is that file's top level, so the way in is its module scope. A Rust file's top level
    # runs nothing at all: `fn main` does. Bound to the module scope, every Rust binary DunneNote
    # declares would reach nothing while its `main` reached the whole program — a claim
    # about somebody else's program that is not true, and a branch on the language in
    # `resolve/entrypoints.py` would be the host naming one (rule 98's remedy: declare it).
    #
    # **Empty means the module scope**, which is the answer every language had before this
    # key existed; a name means the routine of that name at the file's top level.
    file_entry: str = ""
    # **How this language calls a command by name across an IPC boundary**, or what a
    # name that is never a command looks like. `ipc` in the YAML; the reader's own keys
    # under it (`command_attrs`, `registrars`) are the reader's and are not read here.
    #
    # `ipc_clients` is the client side: a function a module exports that sends its first
    # argument as a command name -- `@tauri-apps/api/core`'s `invoke`. `resolve/ipc.py`
    # reads these for every language at once and names none of them.
    #
    # `ipc_foreign` is the server side: a prefix that marks a name answered by something
    # this tree does not hold -- Tauri's `plugin:dialog|open` is a plugin's command, and
    # calling it unknown would be the language working, reported as a defect (rule 98).
    #
    # Empty means this language neither sends nor answers commands by name.
    ipc_clients: tuple[tuple[str, str], ...] = ()
    ipc_foreign: tuple[str, ...] = ()

    def network_profile(self, dotted: str) -> tuple[str, bool] | None:
        """(protocol, is_async_library) for a call, by longest matching prefix.

        **A key with no dot in it matches exactly, and that is rule 5.** `requests.` and
        `httpx.AsyncClient` are namespace prefixes and `startswith` is what they mean;
        `fetch` is a bare name, and a prefix test makes it match `fetchImpl`,
        `fetchAll` and `fetchingState`. Python's own rules hid this for a year because
        every one of them contains a dot — TypeScript's `fetch`, `WebSocket` and
        `EventSource` do not, and DunneNote reported exactly one network call, which was
        `fetchImpl`: a parameter holding an implementation, not the global.

        The residue is stated: a call **through** a name that holds `fetch` is a network
        call and is no longer reported as one. Knowing that needs the far end of the name,
        which is resolution, and a plugin that supplies edges is where it comes back.
        """
        for prefix, protocol, is_async in self.net_libraries:
            if dotted == prefix or ("." in prefix and dotted.startswith(prefix)):
                return protocol, is_async
        return None

    def handler_kind(self, bases: list[str], method: str) -> EntrypointKind | None:
        """A request method on a server base class is an inbound way in."""
        if method not in self.handler_methods:
            return None
        for b in bases:
            kind = self.handler_bases.get(b.rsplit(".", 1)[-1])
            if kind:
                return EntrypointKind(kind)
        return None

    def is_cli_launch(self, dotted: str) -> bool:
        return bool(dotted) and "." in dotted and dotted.rsplit(".", 1)[-1] in self.cli_launches

    def is_cli_factory(self, dotted: str) -> bool:
        return bool(dotted) and dotted.rsplit(".", 1)[-1] in self.cli_factories

    def is_cli_mount(self, dotted: str) -> bool:
        return bool(dotted) and "." in dotted and dotted.rsplit(".", 1)[-1] in self.cli_mounts

    def match_call(self, dotted: str) -> BoundaryRule | None:
        """First matching rule wins, so order in the YAML is meaningful.

        High-salience rules are declared before low-salience ones for the same
        kind, which is why `.exists()` does not shadow `.write_text()`.

        A rule conditioned on an argument never matches here: there are no arguments to
        decide it by, and matching it unconditionally is the defect `when_arg` exists to
        remove. A reader with arguments asks `match_call_args`.
        """
        for rule in self.boundaries:
            if rule.when_arg is None and rule.matches_call(dotted):
                return rule
        return None

    def match_call_args(self, dotted: str, positional: Sequence[tuple[str, bool]],
                        keywords: dict[str, tuple[str, bool]]
                        ) -> tuple[BoundaryRule | None, str]:
        """`match_call`, deciding `when_arg` rules on the call's arguments.

        Returns the rule and the blind spot of every conditioned rule passed over because
        its argument could not be read: `net.Dial(network, a)` stays NETWORK, and says
        that a Unix socket there would read as NETWORK.
        """
        blind: list[str] = []
        for rule in self.boundaries:
            if not rule.matches_call(dotted):
                continue
            if rule.when_arg is not None:
                decided = rule.when_arg.decide(positional, keywords)
                if decided is None and rule.undecided:
                    blind.append(rule.undecided)
                if not decided:
                    continue
            return rule, "; ".join(blind)
        return None, "; ".join(blind)

    def is_type_expression(self, base: str) -> bool:
        """Does a subscript on this name produce a type?

        `Literal[...]` does; `SOME_DICT[...]` does not. Matched on the last segment so
        `typing.Literal` and a bare `Literal` are the same rule.
        """
        return bool(base) and base.rsplit(".", 1)[-1] in self.alias_constructors

    def is_alias_factory(self, dotted: str) -> bool:
        """`NewType(...)` and `TypeVar(...)` declare a type by calling something."""
        return bool(dotted) and dotted.rsplit(".", 1)[-1] in self.alias_factories

    def artefact_kind(self, ext: str) -> str | None:
        """The kind of file this extension names, or None if it names no file.

        An unknown extension is not an artefact. That is the whole precision defence:
        without it `"1.2.3"` and `"mensores.cli"` both read as named files.
        """
        return self.artefact_kinds.get(ext.lower())

    def match_subscript(self, dotted: str) -> BoundaryRule | None:
        return self.subscript_index.get(dotted)

    def match_decorator(self, dotted: str) -> EntrypointRule | None:
        for rule in self.entrypoints:
            if rule.matches_decorator(dotted):
                return rule
        return None


def _declared_rules(lang: str) -> str:
    """Which rules file this language says it has, refusing a language nobody reads.

    Asked of the plugin registry rather than of the directory listing, because *what this
    language declares* is the manifest's answer and `detectors/` holding a file of that
    name is a consequence. Imported inside the function: `ingest` reads every manifest at
    import and the extractor imports this module, so asking at call time keeps the two
    from having to be ordered.
    """
    from ..ingest import PLUGINS

    plugin = PLUGINS.get(lang)
    if plugin is None:
        raise RulesMissing(
            f"nothing in this build reads {lang!r}, so it has no extraction rules to "
            f"load. The readers here are {', '.join(sorted(PLUGINS))}; a language arrives "
            f"by registering a plugin, never by asking for its rules."
        )
    return plugin.manifest.rules


@lru_cache(maxsize=8)
def rules_document(lang: str) -> dict[str, Any]:
    """This language's rules file **as written**, for a reader that is another program.

    `load_rules` turns the same bytes into indexed dataclasses for use in this process. A
    reader on the far side of a pipe cannot be handed those, and must not carry its own
    copy of the file: a plugin with a baked-in rule set is a second answer that stops
    moving the moment somebody edits the YAML, and a language's rules file is in **that
    language's** stamp (`lang_extraction_inputs`) precisely so that an edit re-reads every
    file of it (rule 51). *This said "the core extraction key ... every language" until
    chunk 11 — true when written, and made false by chunk 5's own split.*

    So the document travels. **The declarations cross the wire and the matching is the
    reader's**, which is the seam `PLAN-v2.md` §1e draws: what needs the syntax tree stays
    with the reader, and a boundary match needs the tree to know what was called with what.
    What must never differ is the file, and there is one.

    Refusals are `load_rules`' and deliberately so — the same three answers, from the same
    two functions, so a language cannot be readable here and refused there.
    """
    declared = _declared_rules(lang)
    if not declared:
        return {}
    path = RULES_DIR / declared
    if not path.exists():
        raise RulesMissing(
            f"the {lang} plugin declares its extraction rules in {declared} and this "
            f"build has no such file at {path}. A language whose rules are missing reads "
            f"as a language with no boundaries, no ways in and no CLI at all, which is "
            f"indistinguishable from a program that has none."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _refuse_unread_keys(lang, data, path)
    return dict(data)


# Boundary-rule keys a reader must say it implements before its rules file may use them.
# Every reader ignores a key it does not know -- by design, the document is the host's --
# so a `when_arg` rule handed to a reader that never reads `when_arg` would match
# **unconditionally**, and `net.Dial("tcp", a)` would be LOCAL_IPC with no symptom
# (rule 49). The manifest's `rule_keys` is that reader's word that it reads them.
OPTIONAL_RULE_KEYS = ("when_arg", "undecided", "note", "target_field", "on_receiver")


def _refuse_unread_keys(lang: str, data: dict[str, Any], path: Path) -> None:
    from ..ingest import PLUGINS

    plugin = PLUGINS.get(lang)
    reads = set(plugin.manifest.rule_keys) if plugin is not None else set()
    for i, raw in enumerate(data.get("boundaries", []) or []):
        unread = sorted(k for k in OPTIONAL_RULE_KEYS if k in raw and k not in reads)
        if unread:
            raise RulesMissing(
                f"{path.name} rule {i + 1} ({raw.get('kind')}) uses {', '.join(unread)}, "
                f"and the {lang} reader does not say it reads "
                f"{'it' if len(unread) == 1 else 'them'} (`rule_keys` in its plugin.json). "
                f"A reader ignores a key it does not know, so the rule would match "
                f"unconditionally."
            )


def _arg_condition(raw: Any) -> ArgCondition | None:
    if not raw:
        return None
    return ArgCondition(
        index=raw.get("index"),
        keyword=str(raw.get("keyword", "")),
        in_=frozenset(str(x) for x in raw.get("in", [])),
        not_in=frozenset(str(x) for x in raw.get("not_in", [])),
        undecided_if_keyword=frozenset(str(x) for x in raw.get("undecided_if_keyword", [])),
    )


@lru_cache(maxsize=8)
def load_rules(lang: str) -> RuleSet:
    """Load and index the rules for one language. Cached; the files are static.

    **Three answers, never two**, and the middle one is the whole of this change. A
    language whose plugin declares a rules file gets it; a language whose plugin declares
    **none** gets an empty `RuleSet`, which is a decision somebody wrote down; and a
    language nobody ships, or one whose declared file is not there, is **refused**.

    It used to return an empty `RuleSet` for any missing YAML. For Python that branch
    never fired, so it read as harmless — and for a new language it fires on the first
    run and every boundary, every way in and every CLI mount silently disappears. The map
    comes back whole, plausible, and empty of the one thing the rules decide (rule 49).

    The default argument is gone for the same reason `discover`'s was: `lang` is the
    question, and a question with a default answer is a question nobody has to ask.
    """
    declared = _declared_rules(lang)
    if not declared:
        # Deliberately none. Different from *missing*, and the manifest is where that
        # difference is stated rather than inferred from an absent file (rule 30).
        return RuleSet([], [], frozenset(), {})
    path = RULES_DIR / declared
    if not path.exists():
        raise RulesMissing(
            f"the {lang} plugin declares its extraction rules in {declared} and this "
            f"build has no such file at {path}. A language whose rules are missing reads "
            f"as a language with no boundaries, no ways in and no CLI at all, which is "
            f"indistinguishable from a program that has none."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _refuse_unread_keys(lang, data, path)

    bounds: list[BoundaryRule] = []
    subs: dict[str, BoundaryRule] = {}
    for raw in data.get("boundaries", []):
        rule = BoundaryRule(
            kind=BoundaryKind(raw["kind"]),
            direction=Direction(raw.get("direction", "BOTH")),
            salience=raw.get("salience", "normal"),
            exact=frozenset(raw.get("exact", [])),
            prefix=tuple(raw.get("prefix", [])),
            method=frozenset(raw.get("method", [])),
            subscript=frozenset(raw.get("subscript", [])),
            contains=tuple(raw.get("contains", [])),
            target_arg=raw.get("target_arg"),
            when_arg=_arg_condition(raw.get("when_arg")),
            undecided=str(raw.get("undecided", "")),
            note=str(raw.get("note", "")),
            on_receiver={
                str(m): ReceiverMethod(
                    direction=Direction(spec.get("direction", raw.get("direction", "BOTH"))),
                    target_arg=spec.get("target_arg"))
                for m, spec in (raw.get("on_receiver") or {}).items()
            },
        )
        bounds.append(rule)
        for s in rule.subscript:
            subs[s] = rule

    eps = [
        EntrypointRule(
            kind=EntrypointKind(raw["kind"]),
            decorator_method=frozenset(raw.get("decorator_method", [])),
            evidence=raw.get("evidence", ""),
        )
        for raw in data.get("entrypoints", [])
    ]

    cli = data.get("cli", {}) or {}
    return RuleSet(
        boundaries=bounds,
        entrypoints=eps,
        entry_names=frozenset(data.get("entry_names", [])),
        subscript_index=subs,
        cli_factories=frozenset(cli.get("app_factories", [])),
        cli_mounts=frozenset(cli.get("mount_methods", [])),
        cli_launches=frozenset(cli.get("launch_methods", [])),
        handler_bases=dict(data.get("handler_bases", {}) or {}),
        handler_methods=frozenset(data.get("handler_methods", [])),
        net_libraries=tuple(
            sorted(
                (
                    (k, str(v.get("protocol", "?")), bool(v.get("async", False)))
                    for k, v in (data.get("network", {}) or {}).get("libraries", {}).items()
                ),
                key=lambda t: -len(t[0]),  # longest prefix wins
            )
        ),
        net_verbs=frozenset((data.get("network", {}) or {}).get("verbs", [])),
        net_kwargs={
            k: frozenset(v)
            for k, v in ((data.get("network", {}) or {}).get("kwargs", {}) or {}).items()
        },
        artefact_kinds={
            ext.lower().lstrip("."): kind
            for kind, exts in _artefact_extensions(data).items()
            for ext in exts
        },
        alias_constructors=frozenset(
            (data.get("type_aliases", {}) or {}).get("constructors", [])
        ),
        alias_factories=frozenset(
            (data.get("type_aliases", {}) or {}).get("factories", [])
        ),
        builtins=_builtins(data.get("builtins", []) or [], lang, path),
        unawaited_async=_unawaited_async(data.get("unawaited_async", ""), lang, path),
        private_means=_private_means(data.get("private_means", ""), lang, path),
        redefinition=_redefinition(data.get("redefinition", ""), lang, path),
        file_entry=_file_entry(data.get("file_entry", ""), lang, path),
        ipc_clients=_ipc_clients(data.get("ipc"), lang, path),
        ipc_foreign=_ipc_foreign(data.get("ipc"), lang, path),
    )


def _ipc_section(raw: Any, lang: str, path: Path) -> dict[str, Any]:
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise RulesMissing(
            f"the {lang} rules at {path} declare `ipc` as {raw!r}; it has to be a mapping "
            f"(clients, foreign_prefixes, command_attrs, registrars), or be left out"
        )
    return raw


def _ipc_clients(raw: Any, lang: str, path: Path) -> tuple[tuple[str, str], ...]:
    """`ipc.clients`: each a `{module, name}`, refused whole rather than half-read (rule 49)."""
    out: list[tuple[str, str]] = []
    for c in _ipc_section(raw, lang, path).get("clients", []) or []:
        if (not isinstance(c, dict) or not isinstance(c.get("module"), str)
                or not isinstance(c.get("name"), str) or not c["module"] or not c["name"]):
            raise RulesMissing(
                f"the {lang} rules at {path} declare an `ipc.clients` entry as {c!r}; each "
                f"has to be {{module: <what is imported from>, name: <the function>}}"
            )
        out.append((c["module"], c["name"]))
    return tuple(sorted(set(out)))


def _ipc_foreign(raw: Any, lang: str, path: Path) -> tuple[str, ...]:
    got = _ipc_section(raw, lang, path).get("foreign_prefixes", []) or []
    if not isinstance(got, list) or not all(isinstance(x, str) and x for x in got):
        raise RulesMissing(
            f"the {lang} rules at {path} declare `ipc.foreign_prefixes` as {got!r}; it has "
            f"to be a list of non-empty strings"
        )
    return tuple(sorted(set(got)))


_UNAWAITED = ("inert", "runs")
_PRIVATE_MEANS = ("module", "package", "surface")


def _private_means(raw: Any, lang: str, path: Path) -> str:
    """*module*, *package* or *surface*, or nothing -- refused rather than guessed (rule 49)."""
    if raw in ("", None):
        return ""
    if not isinstance(raw, str) or raw not in _PRIVATE_MEANS:
        raise RulesMissing(
            f"the {lang} rules at {path} declare `private_means` as {raw!r}; it has to be "
            f"one of {', '.join(_PRIVATE_MEANS)}, or be left out to say nobody has decided"
        )
    return raw
_REDEFINITION = ("shadows", "overloads")


def _unawaited_async(raw: Any, lang: str, path: Path) -> str:
    """*inert* or *runs*, or nothing at all -- and never a third word taken on trust.

    A misspelling would otherwise arrive as a severity nobody chose, in the one command a
    CI job exits non-zero on. Refused by name rather than defaulted (rule 49), and the
    empty string is a legitimate answer meaning *nobody has said*, which is why it is not
    in the tuple.
    """
    if raw in ("", None):
        return ""
    if not isinstance(raw, str) or raw not in _UNAWAITED:
        raise RulesMissing(
            f"the {lang} rules at {path} declare `unawaited_async` as {raw!r}; it has to "
            f"be one of {', '.join(_UNAWAITED)}, or be left out to say nobody has decided"
        )
    return raw


def _redefinition(raw: Any, lang: str, path: Path) -> str:
    """*shadows* or *overloads*, or nothing at all — `_unawaited_async`'s shape exactly.

    Two questions with the same structure get the same validator rather than one
    generalised one: each names its own key and its own words in the refusal, which is what
    makes the sentence something a plugin author can act on (rule 89).
    """
    if raw in ("", None):
        return ""
    if not isinstance(raw, str) or raw not in _REDEFINITION:
        raise RulesMissing(
            f"the {lang} rules at {path} declare `redefinition` as {raw!r}; it has to "
            f"be one of {', '.join(_REDEFINITION)}, or be left out to say nobody has decided"
        )
    return raw


def _file_entry(raw: Any, lang: str, path: Path) -> str:
    """A routine's name, or nothing. Refused rather than read if it is anything else,
    because a way in bound to a name nobody can define is a declared program that leads
    nowhere, said about every program in that language (rule 49)."""
    if raw in ("", None):
        return ""
    if not isinstance(raw, str) or not raw.isidentifier():
        raise RulesMissing(
            f"the {lang} rules at {path} declare `file_entry` as {raw!r}; it has to be the "
            f"name of a function, or be left out to mean the file's top level"
        )
    return raw


def _builtins(raw: Any, lang: str, path: Path) -> frozenset[str]:
    """The declared builtin names, refusing anything that is not one.

    **The refusal is the point, not the parsing.** `True` and `False` written unquoted in
    YAML are booleans, so a list that reads correctly, holds the right number of entries
    and passes every eye arrives holding two `bool`s -- and the two commonest words in the
    language quietly stop being suppressed, which is a handful of false edges and no
    symptom anywhere (rule 49). A comment in the YAML saying *quote them* is a comment; a
    name in the refusal is something somebody can act on (rule 89).
    """
    if not isinstance(raw, list):
        raise RulesMissing(
            f"the {lang} rules at {path} declare `builtins` as {type(raw).__name__} and "
            f"it has to be a list of names."
        )
    bad = [x for x in raw if not isinstance(x, str)]
    if bad:
        raise RulesMissing(
            f"the {lang} rules at {path} declare {len(bad)} builtin name(s) that are not "
            f"text: {bad!r}. Unquoted, `True` and `False` are YAML booleans — quote every "
            f"entry, or those names stop being suppressed and nothing says so."
        )
    return frozenset(raw)

def _artefact_extensions(data: dict[str, Any]) -> dict[str, list[str]]:
    """The `artefacts.extensions` block, or nothing if the language declares none."""
    block = data.get("artefacts") or {}
    exts = block.get("extensions") or {}
    return {str(k): list(v) for k, v in exts.items()}


def fingerprint_files(paths: Iterable[Path]) -> str:
    """Hash a set of files by name and content, order-independently.

    The name is hashed as well as the body so that renaming a rule file, or adding an
    empty one, still changes the answer.

    The label is the path relative to the package, not the bare filename: the code key
    holds two files called `__init__.py` -- the rule loader and the extractor package
    -- and a bare name cannot tell them apart.

    **Two refusals, and each is a way this returns a confident answer about nothing.**
    A hash of no files is `e3b0c44298fc1c14`, the sha256 of the empty string, which looks
    exactly like a fingerprint and compares equal to itself for ever -- so rule 12's whole
    guarantee, that a cached fact is valid only if the tool that read it is unchanged,
    would be enforced by a constant. The other is a file that is *named* and absent, which
    is what a frozen application does to `Path(__file__)`: the list is not empty, so an
    emptiness check alone passes it straight through to a `FileNotFoundError` raised from
    inside a hash, several frames from anything that can say what went wrong.

    Both are packaging failures rather than anything a reader can do, so they are loud
    rather than handled. `RulesMissing` exists so a test can name the case (rule 30 -- a
    class the guard can ask about, not a sentence it has to match).
    """
    wanted = sorted(set(paths))
    if not wanted:
        raise RulesMissing(
            "no extraction rules were found at all, so there is nothing to fingerprint. "
            f"This build is looking in {_PKG_ROOT} — in a packaged application that means "
            "the rule files and the extractors were not bundled as data.")
    missing = [p for p in wanted if not p.is_file()]
    if missing:
        named = ", ".join(str(p) for p in missing[:4])
        raise RulesMissing(
            f"{len(missing)} of {len(wanted)} extraction rule files are named and not "
            f"there: {named}{' …' if len(missing) > 4 else ''}. In a packaged application "
            "that means they were not bundled as data.")
    h = hashlib.sha256()
    for path in wanted:
        try:
            # **Through `stored_path`, and that is rule 12 rather than tidiness.** The
            # label goes into the hash, so spelling it the way the writing machine spells
            # a path would give one unchanged file two fingerprints -- and a map written
            # by the Windows build would be discarded by the macOS build as *written by a
            # different tool*, with the same commit on both. That is the refusal
            # `resource_root`'s layout exists to prevent, one platform over.
            label = stored_path(path.relative_to(_PKG_ROOT))
        except ValueError:      # a path from outside the package, as in tests
            label = path.name
        h.update(label.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


# The rules files that belong to no single language, and so to all of them.
# `annotations.yaml` mines governance markers out of comments and prose alike; a
# language's own rules file is named by that language's plugin and is hashed with it.
_SHARED_RULES = ("annotations.yaml",)


def core_extraction_inputs() -> list[Path]:
    """Every file that shapes code extraction **whatever language is being read**.

    This was `code_extraction_inputs()` and it held the Python reader and `python.yaml`,
    which was the whole truth while Python was the only reader. Split, because the thing
    rule 12 protects is *a cached fact against the tool that read it*, and editing the
    TypeScript plugin has nothing to say about a fact the Python reader produced. What is
    left here is what every reader passes through: the rule loader, the shared rules, the
    ingest seam that routes and stamps, and the fact contract itself.

    **`schema.py` joins the key, and `SCHEMA_VERSION` stops being load-bearing.** The
    version is bumped by hand and a forgotten bump is precisely rule 12's failure mode --
    a confident map answering the previous version of the tool. It stays as the
    human-readable generation marker, and the file that actually defines what a fact *is*
    is now hashed like everything else that decides that.

    **`ingest/*.py` is in and `canonical/` is still out**, on the test this list has always
    applied: what does extraction actually read. The registry decides which reader sees a
    file, the contract decides what a reader may say, and `stamp_lang` writes a field into
    every record -- all three shape what a fact is. A canonicaliser still cannot change a
    fact, only whether two facts compare equal, and it cost a sealed snapshot once to learn
    that (rules 25 and 62).

    Named separately from the hash so a test can assert *membership* rather than
    re-deriving the list, which is the same defence the annotation prefilter uses --
    a hand-kept list drifts the moment someone adds a file, and a key that silently
    omits one is the silent no-op this project has paid for repeatedly.
    """
    return [
        *(RULES_DIR / name for name in _SHARED_RULES),
        RULES_DIR / "__init__.py",      # the loader that decides what a rule means
        *(_PKG_ROOT / "ingest").glob("*.py"),  # who reads a file, and what it may say
        _PKG_ROOT / "schema.py",        # what a fact *is*
        _PKG_ROOT / "sql.py",           # what a string literal *means* -- rule 95
    ]


@lru_cache(maxsize=1)
def core_fingerprint() -> str:
    """A hash of everything that shapes code extraction in **every** language.

    `detectors/*.yaml` is the extension point -- teaching DunneFlow a framework is a
    config edit, not a code change. That makes it the thing most often edited and the
    thing most likely to leave a cached graph stale, because the file cache keys on
    source content and the source did not change. Editing a rule must invalidate the
    cache as surely as editing the schema does.

    Rule 12 says a cached fact is valid only if the source **and the tool that read
    it** are unchanged, and for a while only half of that was enforced. The rules were
    hashed; the extractor that applies them was not. Named artefacts, the comment fix
    and module-level constants each changed what extraction *means* while every cached
    file still answered the old rules, and each was saved only by someone remembering
    to bump `SCHEMA_VERSION` by hand. A forgotten bump is precisely rule 12's failure
    mode: a confident map answering the previous version of the tool. So the reader is
    in the key too, and the bump is no longer load-bearing.

    Scope is decided by asking what this extraction actually reads. `detectors/docs/`
    and `prose.py` are absent deliberately -- they shape the *other* corpus, and
    editing a prose rule must not discard the code graph. A **reader** is absent for the
    same argument one axis over: it shapes one language's facts, it is hashed into that
    language's stamp (`ingest.lang_fingerprint`), and a graph that differs only there
    loses that language's files rather than all of them.
    """
    return fingerprint_files(core_extraction_inputs())


def lang_extraction_inputs(lang: str) -> list[Path]:
    """Every file that shapes **one** language's extraction: its rules and its reader.

    Here rather than in `ingest` because this is the module that owns `RULES_DIR` and the
    hash, and because the two halves of the answer come from two places: the rules file the
    plugin declares, which lives beside this one, and the plugin's own files, which the
    plugin knows about. Asking the registry from here keeps one function that can be asked
    *what decides this language* (rule 51).
    """
    from ..ingest import plugin_fingerprint_files

    declared = _declared_rules(lang)
    rules = [RULES_DIR / declared] if declared else []
    return [*rules, *plugin_fingerprint_files(lang)]


@lru_cache(maxsize=8)
def lang_fingerprint(lang: str) -> str:
    """One reader's stamp: the version it declares and the bytes it is made of.

    **Cached, and that is a measured decision rather than a habit.** `write_file_facts`
    stamps every row, so an uncached answer re-reads and re-hashes the whole reader once
    per file -- 628 times over ten files on Society, for a value that cannot change while
    the process is running. `load_rules` and `resource_root` make the same assumption, in
    the same words: an application does not become a source checkout halfway through a
    run.

    **A declared version alone is a label** (rule 30) and it does not move when somebody
    edits the reader during development, which is exactly when it must. So the version is
    what a reader *says* it is and the hash is what it *is*, and the pair is what a file's
    facts are stamped with.
    """
    from ..ingest import PLUGINS

    plugin = PLUGINS.get(lang)
    if plugin is None:
        raise RulesMissing(
            f"nothing in this build reads {lang!r}, so there is no reader to fingerprint."
        )
    return f"{plugin.manifest.version}:{fingerprint_files(lang_extraction_inputs(lang))}"
