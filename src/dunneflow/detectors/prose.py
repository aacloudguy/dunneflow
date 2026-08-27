"""Loading and matching of the prose detector rules.

The rules live in `detectors/docs/*.yaml`; only the matching lives here. That split is
what makes "teach it about another documentation habit" a config edit.

The subdirectory is deliberate. `rules_fingerprint()` globs `detectors/*.yaml` and does
not recurse, so editing a prose rule invalidates the document store without discarding
the code graph -- the two corpora are re-read independently, which is the whole reason
they are stored apart.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..schema import DocClass, RuleLane

DOC_RULES_DIR = Path(__file__).parent / "docs"


def _alternation(words: list[str]) -> re.Pattern[str]:
    """One word-bounded alternation, longest first so `env var` beats `var`."""
    parts = sorted((re.escape(w) for w in words), key=len, reverse=True)
    return re.compile(r"(?i)\b(" + "|".join(parts) + r")\b")


@dataclass(slots=True)
class ProseRules:
    exact_stems: dict[str, DocClass]
    frontmatter_kind: dict[str, DocClass]
    path_segments: dict[str, DocClass]
    stem_contains: dict[str, DocClass]
    heading_class: tuple[tuple[DocClass, re.Pattern[str]], ...]
    definition_headings: re.Pattern[str]
    naming_headings: re.Pattern[str]
    term_columns: re.Pattern[str]
    meaning_columns: re.Pattern[str]
    modals: re.Pattern[str]
    excluded_headings: re.Pattern[str]
    rule_bearing_classes: frozenset[DocClass]
    ordinary_words: frozenset[str]
    identifier_classes: re.Pattern[str]
    pattern_tokens: tuple[re.Pattern[str], ...]
    naming_domain_words: re.Pattern[str]


def _classes(raw: dict[str, str] | None) -> dict[str, DocClass]:
    out: dict[str, DocClass] = {}
    for key, value in (raw or {}).items():
        try:
            out[str(key).lower()] = DocClass(value)
        except ValueError:
            # An unknown class name in the rules file is a typo, and a typo that
            # silently classifies nothing is exactly the failure this project keeps
            # paying for. Say so rather than dropping it.
            raise ValueError(f"prose rules: unknown document class {value!r} for {key!r}") from None
    return out


@lru_cache(maxsize=1)
def load_prose_rules() -> ProseRules:
    data: dict[str, Any] = {}
    for path in sorted(DOC_RULES_DIR.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        data.update(loaded)
    if not data:
        raise FileNotFoundError(f"no prose rules found in {DOC_RULES_DIR}")

    heading_class = tuple(
        (DocClass(k), re.compile(v))
        for k, v in (data.get("heading_class") or {}).items()
    )
    return ProseRules(
        exact_stems=_classes(data.get("exact_stems")),      
        frontmatter_kind=_classes(data.get("frontmatter_kind")),
        path_segments=_classes(data.get("path_segments")),  
        stem_contains=_classes(data.get("stem_contains")),  
        heading_class=heading_class,
        definition_headings=re.compile(str(data["definition_headings"])),
        naming_headings=re.compile(str(data["naming_headings"])),
        term_columns=re.compile(str(data["term_columns"])),
        meaning_columns=re.compile(str(data["meaning_columns"])),
        modals=re.compile(str(data["modals"])),
        excluded_headings=re.compile(str(data["excluded_headings"])),
        ordinary_words=frozenset(
            w.strip().lower()
            for line in data.get("ordinary_words", [])
            for w in str(line).split(",")
            if w.strip()
        ),
        rule_bearing_classes=frozenset(
            DocClass(c) for c in data["rule_bearing_classes"]
        ),
        identifier_classes=_alternation(list(data["identifier_classes"])),
        pattern_tokens=tuple(re.compile(p) for p in data["pattern_tokens"]),
        naming_domain_words=re.compile(str(data["naming_domain_words"])),
    )


def doc_rules_fingerprint() -> str:
    """A hash of every prose rule file, for the document store's staleness check.

    Rule 12, applied to the other corpus: a cached fact is valid only if the source and
    the rule that read it are both unchanged.
    """
    h = hashlib.sha256()
    for path in sorted(DOC_RULES_DIR.glob("*.yaml")):
        h.update(path.name.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #


def classify(path: Path, kind: str, headings: list[str]) -> DocClass:
    """What kind of document this is.

    Precedence is evidence-ordered, and each tier is there because of a real document:

    * `NAMING.md` filed under `milestones/` is a naming standard, not a plan -- so an
      unambiguous filename outranks the drawer it was filed in.
    * `conventions-naming-and-documentation.md` carries `kind: research` and is a paper
      *about* naming standards -- so the author's own word outranks a filename substring.
    * `0020-org-glossary-cli-etl.md` under `adrs/` is a decision about a glossary
      feature, not a glossary -- so the drawer outranks a filename substring too.
    """
    rules = load_prose_rules()
    stem = path.stem.lower()

    found = rules.exact_stems.get(stem)
    if found:
        return found

    found = rules.frontmatter_kind.get(kind.strip().lower()) if kind else None
    if found:
        return found

    for part in path.parts:
        found = rules.path_segments.get(part.lower())
        if found:
            return found

    for needle, cls in rules.stem_contains.items():
        if needle in stem:
            return cls

    for cls, pattern in rules.heading_class:
        if any(pattern.search(h) for h in headings):
            return cls

    return DocClass.OTHER


# --------------------------------------------------------------------------- #
# Naming rules: the two lanes
# --------------------------------------------------------------------------- #


def is_normative(text: str) -> bool:
    """Does this sentence tell you to do something, rather than describe something?"""
    return bool(load_prose_rules().modals.search(text))


def rule_lane(text: str) -> tuple[RuleLane, str, str] | None:
    """Which lane a stated rule belongs to, with the evidence that put it there.

    Returns (lane, scope, pattern). FORM when the sentence names a class of identifier
    or shows a concrete spelling pattern -- those can be pointed at rows in the graph
    and belong in a table. VOCABULARY otherwise: a rule about what a name may be drawn
    from is a paragraph, and flattening it into a cell loses it.

    Returns None when neither lane applies; the caller decides whether the sentence is
    admissible as VOCABULARY on the strength of its section instead.
    """
    rules = load_prose_rules()

    scope = ""
    m = rules.identifier_classes.search(text)
    if m:
        scope = m.group(1).lower()

    pattern = ""
    for pat in rules.pattern_tokens:
        hit = pat.search(text)
        if hit:
            pattern = hit.group(0)
            break

    if scope or pattern:
        return RuleLane.FORM, scope, pattern
    return None


def is_ordinary(word: str) -> bool:
    """Is this a word a working programmer already has?

    A glossary is for the words a reader cannot look up. `handler` is not one of them;
    `disceptator` is.
    """
    return word.strip().lower() in load_prose_rules().ordinary_words


def may_state_rules(doc_class: DocClass) -> bool:
    """Is this the kind of document that states rules, rather than discusses them?

    A paper *about* naming standards is not a naming standard, and only the
    classification tells them apart -- its headings read identically.
    """
    return doc_class in load_prose_rules().rule_bearing_classes


def reports_rather_than_rules(heading: str) -> bool:
    """Is this section reporting a finding rather than stating a rule?

    A naming-standards document is not made only of rules. NAMING.md carries a
    trademark status section, a registry availability table and a runner-up list, and
    every one of them is normative in voice -- "Action before any filing", "prefix
    `mensores-<role>` if it ever ships standalone". None of them is a rule anyone
    follows when naming a function, and admitting them would put four findings into a
    standard that has three rules.
    """
    return bool(load_prose_rules().excluded_headings.search(heading))


def about_naming(text: str) -> bool:
    """Is this sentence about names at all?

    The guard that keeps a naming-standard document's trademark and domain-registration
    sections out of the standard. They are normative -- "a registered attorney runs full
    clearance before any filing" -- and they are not naming rules.
    """
    return bool(load_prose_rules().naming_domain_words.search(text))
