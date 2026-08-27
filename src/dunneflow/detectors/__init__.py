"""Loading and matching of the declarative detector rules.

The rules themselves live in the YAML files beside this module. Keeping matching
here and rules there is what makes "teach it about a new framework" a config edit.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from ..schema import Annotation, BoundaryKind, Confidence, Direction, EntrypointKind

RULES_DIR = Path(__file__).parent


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

    def match_subscript(self, dotted: str) -> BoundaryRule | None:
        return self.subscript_index.get(dotted)

    def match_decorator(self, dotted: str) -> EntrypointRule | None:
        for rule in self.entrypoints:
            if rule.matches_decorator(dotted):
                return rule
        return None


@lru_cache(maxsize=8)
def load_rules(lang: str = "python") -> RuleSet:
    """Load and index the rules for one language. Cached; the files are static."""
    path = RULES_DIR / f"{lang}.yaml"
    if not path.exists():
        return RuleSet([], [], frozenset(), {})
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
    )

def rules_fingerprint() -> str:
    """A hash of every detector file that shapes extraction.

    `detectors/*.yaml` is the extension point -- teaching DunneFlow a framework is a
    config edit, not a code change. That makes it the thing most often edited and the
    thing most likely to leave a cached graph stale, because the file cache keys on
    source content and the source did not change. Editing a rule must invalidate the
    cache as surely as editing the schema does.
    """
    h = hashlib.sha256()
    for path in sorted(RULES_DIR.glob("*.yaml")):
        h.update(path.name.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()[:16]
