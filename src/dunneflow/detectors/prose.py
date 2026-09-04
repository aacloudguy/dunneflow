"""Loading and matching of the prose detector rules.

The rules live in `detectors/docs/*.yaml`; only the matching lives here. That split is
what makes "teach it about another documentation habit" a config edit.

The subdirectory is deliberate. `rules_fingerprint()` globs `detectors/*.yaml` and does
not recurse, so editing a prose rule invalidates the document store without discarding
the code graph -- the two corpora are re-read independently, which is the whole reason
they are stored apart.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..schema import DocClass, RuleLane
from . import fingerprint_files

DOC_RULES_DIR = Path(__file__).parent / "docs"
_PKG_ROOT = Path(__file__).parent.parent


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
    scope_columns: re.Pattern[str]
    pattern_columns: re.Pattern[str]
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
        scope_columns=re.compile(str(data["scope_columns"])),
        pattern_columns=re.compile(str(data["pattern_columns"])),
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


def doc_extraction_inputs() -> list[Path]:
    """Every file that shapes document extraction. See `code_extraction_inputs`."""
    return [
        *DOC_RULES_DIR.glob("*.yaml"),              # the prose rules
        DOC_RULES_DIR.parent / "annotations.yaml",  # governs both corpora
        Path(__file__),                             # the loader and classifier
        *(_PKG_ROOT / "extractors" / "docs").rglob("*.py"),  # the reader itself
    ]


def doc_rules_fingerprint() -> str:
    """A hash of every rule file that shapes document extraction.

    Rule 12, applied to the other corpus: a cached fact is valid only if the source and
    the rule that read it are both unchanged.

    `annotations.yaml` is in here as well as the prose rules, and had to be added the
    hard way. It governs both corpora -- comments are comments and prose is prose, and
    the same governance markers are mined from each -- so editing it changed what a
    document means while leaving every document cached and answering the old rule. That
    is the same silent staleness the graph's own fingerprint exists to prevent, wearing
    the other corpus as a disguise. A rule file that shapes an extraction belongs in
    that extraction's fingerprint, and the only safe way to decide which is to ask what
    the extractor reads, not to keep a list by hand.

    The reader is in here too, for the same reason it is on the code side: rule 12 says
    a cached fact is valid only if the source **and the tool that read it** are
    unchanged, and hashing only the rules enforces half of that. Editing
    `extractors/docs/markdown.py` changes what a document means just as surely as
    editing `prose.yaml` does.
    """
    return fingerprint_files(doc_extraction_inputs())


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
    # **The same two questions a table cell is asked**, and asked by the same code. They
    # were written out here and again in `table_rule_columns` for about an hour, which is
    # rule 51 arriving before the second caller had finished being written: a sentence and
    # a cell must agree about what counts as a scope, or a rule mined from a table and the
    # same rule written in prose would carry different scopes.
    scope, pattern = rule_scope(text), rule_pattern(text)
    if scope or pattern:
        return RuleLane.FORM, scope, pattern
    return None


# The share of a column's non-empty cells that must carry the evidence before the column is
# taken to be playing that role. Half, and measured rather than chosen: the one real naming
# table in the corpus scores 86% on its scope column and 71% on its pattern column, and the
# nearest false positive scores nothing at all -- so the threshold is nowhere near either
# and moving it between 0.5 and 0.6 changes no result. A named constant because a bare 0.5
# in the middle of a loop is a number nobody can weigh.
COLUMN_EVIDENCE = 0.5

# Fewer rows than this and a majority means nothing: one row out of one is 100%.
MIN_RULE_TABLE_ROWS = 2


def rule_scope(text: str) -> str:
    """The class of identifier this text names, normalised, or `""`.

    `rule_lane`'s first half, lifted out so a table cell and a prose sentence are asked the
    same question by the same code. They were the same three lines twice for about an hour,
    which is rule 51 arriving before the second caller had finished being written.
    """
    m = load_prose_rules().identifier_classes.search(text)
    return m.group(1).lower() if m else ""


def rule_pattern(text: str) -> str:
    """The concrete spelling pattern this text shows, as written, or `""`."""
    for pat in load_prose_rules().pattern_tokens:
        hit = pat.search(text)
        if hit:
            return hit.group(0)
    return ""


def table_rule_columns(header: list[str],
                       rows: list[list[str]]) -> tuple[int, int] | None:
    """Which column names the thing and which gives its spelling, or neither.

    **A naming standard is usually a table**, and until this existed DunneFlow could not
    read one: `_table` consumes a table whole, so the prose rule detector is never offered
    its lines, and the corpus yielded **zero** FORM rules in consequence. The best standard
    in it is seven rows of `Type | Convention | Example`, every row a class of identifier
    and the spelling it must have -- exactly the pair the FORM lane wants.

    Modelled on `term_columns`/`meaning_columns` beside it, including the rule that matters:
    **both halves are required, on different columns.** `| Name | Port |` is not a glossary
    and `| Phase | Status |` is not a naming standard.

    A column qualifies on its **header or its cells**, and taking either is what makes this
    land. Headers vary between organisations -- Type/Convention, Element/Style, What/How --
    so matching headers alone is brittle; and cells alone miss the one real table here,
    whose `Convention` column scores 43% against regexes tuned for prose sentences. Together
    it fires on that table and on nothing else in 5,230.

    Returns `(scope_col, pattern_col)`, or `None` when either half is missing or both
    resolve to the same column -- which is a table saying one thing, not two.
    """
    if len(rows) < MIN_RULE_TABLE_ROWS:
        return None
    rules = load_prose_rules()
    width = max([len(r) for r in rows] + [len(header)])

    def cells(k: int) -> list[str]:
        return [r[k].strip() for r in rows if k < len(r) and r[k].strip()]

    def head(k: int) -> str:
        return header[k] if k < len(header) else ""

    def share(got: list[str], test: Callable[[str], str]) -> float:
        return sum(1 for c in got if test(c)) / len(got) if got else 0.0

    scope = pattern = None
    best_scope = best_pattern = -1.0
    for k in range(width):
        got = cells(k)
        s = share(got, rule_scope)
        p = share(got, rule_pattern)
        # The header is evidence, never proof: "Type" heads a great many tables that say
        # nothing about names, and it is the cells that decide whether this is one of them.
        # A header match admits a column whose cells are too terse to score; the cell
        # majority admits one whose header this list has never seen.
        if (rules.scope_columns.match(head(k)) or s >= COLUMN_EVIDENCE) and s > best_scope:
            scope, best_scope = k, s
        if (rules.pattern_columns.match(head(k)) or p >= COLUMN_EVIDENCE) and p > best_pattern:
            pattern, best_pattern = k, p

    if scope is None or pattern is None or scope == pattern:
        return None
    return scope, pattern


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
