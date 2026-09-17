"""Loading and matching of the declarative detector rules.

The rules themselves live in the YAML files beside this module. Keeping matching
here and rules there is what makes "teach it about a new framework" a config edit.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
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

    def network_profile(self, dotted: str) -> tuple[str, bool] | None:
        """(protocol, is_async_library) for a call, by longest matching prefix."""
        for prefix, protocol, is_async in self.net_libraries:
            if dotted.startswith(prefix):
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
        """
        for rule in self.boundaries:
            if rule.matches_call(dotted):
                return rule
        return None

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
    )

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
