"""Reading a document the way a reader reads it.

Stdlib only, no markdown library -- the same discipline the Python extractor keeps with
`ast` and `tokenize`. A document is scanned twice: once for structure (where the code
fences are, where the headings are), then once for meaning. Structure first is what lets
the second pass know that a line inside a fence is code and must yield nothing.

**The mirror of rule 9.** Rule 9 keeps docstrings out of code-shaped detectors, because a
sentence about a statement is not a statement. The same argument runs the other way: a
fenced block is a statement, not a sentence, and mining a definition out of an example is
the same defect wearing the opposite uniform.

Every shape recognised here is corroborated by its context. A table becomes definitions
only when its header pairs a term column with a meaning column; a bold lead-in becomes a
definition only inside a glossary section; a sentence becomes a naming rule only when it
is normative, in a naming section, and lands in one of the two lanes. Rule 1: a false
definition tells the reader a word means something it does not.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import yaml

from ...detectors import has_annotation, mine_annotations
from ...detectors.prose import (
    about_naming,
    classify,
    is_normative,
    load_prose_rules,
    may_state_rules,
    reports_rather_than_rules,
    rule_lane,
)
from ...schema import (
    DefForm,
    DocDefinition,
    DocFacts,
    DocFormat,
    DocRef,
    DocRefKind,
    DocRule,
    DocTable,
    Heading,
    RuleLane,
    hash_source,
)

# -- structure -------------------------------------------------------------- #

FENCE = re.compile(r"^\s{0,3}(?P<f>`{3,}|~{3,})")
ATX = re.compile(r"^(?P<h>#{1,6})\s+(?P<t>.*?)\s*#*\s*$")
SETEXT = re.compile(r"^\s{0,3}(=+|-{2,})\s*$")
TABLE_SEP = re.compile(r"^\s*\|?[\s:]*-{2,}[\s:]*(\|[\s:]*-{2,}[\s:]*)*\|?\s*$")
LIST_ITEM = re.compile(r"^(?P<indent>\s*)(?:[-*+]|\d+[.)])\s+(?P<t>.*)$")

# -- definition shapes ------------------------------------------------------- #

BOLD_DEF = re.compile(
    r"^\s*(?:[-*+]\s+|\d+[.)]\s+)?\*\*(?P<term>[^*\n]{1,80})\*\*\s*"
    r"(?:\*\([^)]*\)\*\s*)?(?P<sep>[—–:-])\s+(?P<def>\S.*)$"
)
BOLD_ALONE = re.compile(r"^\s*\*\*(?P<term>[^*\n]{1,80})\*\*\s*(?:\*\([^)]*\)\*)?\s*$")
CODE_GLOSS = re.compile(
    r"^\s*(?:[-*+]\s+)?`(?P<term>[^`\n]{1,60})`\s*(?P<sep>[—–:-])\s+(?P<def>\S.*)$"
)
DT = re.compile(r"<dt>(?P<t>.*?)</dt>", re.I | re.S)
DD = re.compile(r"<dd>(?P<t>.*?)</dd>", re.I | re.S)

# -- references -------------------------------------------------------------- #

URL = re.compile(r"https?://[^\s)>\]\"']+")
BACKTICK = re.compile(r"`([^`\n]{1,120})`")
PATHLIKE = re.compile(
    r"\b[\w][\w./-]*\.(?:py|pyi|ts|tsx|js|jsx|md|rst|ya?ml|toml|json|sql|sh|rs|go|java|swift|c|h|cpp)\b"
)
# Only real HTML tags are markup. `<role>` in `mensores-<role>` is a placeholder in
# prose, and stripping it shortens a value before it reaches the store -- the one loss
# rule 8 calls unrecoverable. The tag names are the ones documentation actually uses.
_HTML_TAGS = (
    "dl|dt|dd|em|strong|b|i|u|code|pre|br|p|span|div|a|ul|ol|li|table|thead|tbody|tr|td|th"
    "|h[1-6]|img|sup|sub|blockquote|hr|details|summary|kbd|small|figure|figcaption|section"
)
TAG = re.compile(rf"</?(?:{_HTML_TAGS})(?:\s[^>]*)?/?>", re.I)
STATUS_MARK = re.compile(r"\s*[✅✓⚠️❌✗].*$")

MIN_RULE_CHARS = 20

# How a format finds its headings. Everything else about reading a document -- what a
# definition looks like, what makes a sentence a rule -- is format-independent.
HeadingsFn = Callable[[list[str], int, list[bool]], list[Heading]]


def _text(raw: str) -> str:
    """Readable text from a fragment of markup. Nothing is shortened, only unwrapped."""
    return " ".join(TAG.sub(" ", raw).split())


def _clean_term(cell: str) -> str:
    """The term a cell names.

    When a cell bolds part of itself, the bold part is the term: `**signator** /
    signatores` names `signator`, and `**disceptator** ✓ LOCKED` names `disceptator`.
    """
    bold = re.search(r"\*\*([^*]+)\*\*", cell)
    term = bold.group(1) if bold else cell
    term = STATUS_MARK.sub("", TAG.sub("", term)).replace("`", "")
    return " ".join(term.strip(" *_.:—–-").split())


def _is_term_shaped(term: str) -> bool:
    """A term is a name, not a sentence.

    Guards the second term-ish column of a wide table: `Harness (the PAUL fork:
    /paul-*, .groma/, groma.json)` is a description of a component, not a word anyone
    looks up.
    """
    if not term or len(term) > 60:
        return False
    if len(term.split()) > 5:
        return False
    return not term.endswith(".")


def _split_frontmatter(text: str) -> tuple[dict[str, str], int, list[str]]:
    """YAML frontmatter, the line it ends on, and the body lines.

    A document with unreadable frontmatter is still a document: the error is recorded
    by the caller and the body is read regardless. Ingest never fails on bad input.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() not in {"---", "+++"}:
        return {}, 0, lines
    fence = lines[0].strip()
    for i in range(1, min(len(lines), 400)):
        if lines[i].strip() == fence:
            raw = "\n".join(lines[1:i])
            meta: dict[str, str] = {}
            try:
                loaded = yaml.safe_load(raw)
            except Exception:
                loaded = None
            if isinstance(loaded, dict):
                for k, v in loaded.items():
                    meta[str(k)] = v if isinstance(v, str) else str(v)
            return meta, i + 1, lines
    return {}, 0, lines


def _fence_mask(lines: list[str], start: int) -> list[bool]:
    """True where a line is inside a fenced code block, fences included."""
    mask = [False] * len(lines)
    fence: str | None = None
    for i in range(start, len(lines)):
        m = FENCE.match(lines[i])
        if fence is None:
            if m:
                fence = m.group("f")[0]
                mask[i] = True
            continue
        mask[i] = True
        if m and m.group("f")[0] == fence:
            fence = None
    return mask


def _headings(lines: list[str], start: int, mask: list[bool]) -> list[Heading]:
    """Every heading, with the trail of headings above it."""
    out: list[Heading] = []
    stack: list[tuple[int, str]] = []
    for i in range(start, len(lines)):
        if mask[i]:
            continue
        line = lines[i]
        level = 0
        text = ""
        m = ATX.match(line)
        if m:
            level, text = len(m.group("h")), m.group("t").strip()
        elif (
            SETEXT.match(line)
            and i > start
            and lines[i - 1].strip()
            and not lines[i - 1].startswith(("#", "|", ">"))
            and not LIST_ITEM.match(lines[i - 1])
        ):
            level = 1 if line.strip().startswith("=") else 2
            text = lines[i - 1].strip()
        if not level or not text:
            continue
        while stack and stack[-1][0] >= level:
            stack.pop()
        trail = " > ".join(t for _, t in stack)
        out.append(Heading(level=level, text=_text(text), line=i + 1, path=trail))
        stack.append((level, _text(text)))
    return out


class _Scanner:
    """One document, scanned once for meaning after being scanned once for structure."""

    def __init__(self, path: str, rel: Path, text: str, fmt: DocFormat,
                 headings_fn: HeadingsFn | None = None) -> None:
        self.rules = load_prose_rules()
        self.facts = DocFacts(path=path, fmt=fmt, content_hash=hash_source(text))
        self.facts.size = len(text.encode("utf-8", errors="replace"))
        self.facts.words = len(text.split())

        meta, body_start, lines = _split_frontmatter(text)
        self.facts.frontmatter = meta
        self.lines = lines
        self.start = body_start
        self.mask = _fence_mask(lines, body_start)
        self.facts.headings = (headings_fn or _headings)(lines, body_start, self.mask)

        heads = [h.text for h in self.facts.headings]
        self.facts.doc_class = classify(rel, meta.get("kind", ""), heads)
        self.facts.title = meta.get("title", "") or (
            next((h.text for h in self.facts.headings if h.level == 1), "") or rel.stem
        )

        # Section state, recomputed at each heading. A level-1 heading is the title of
        # the document, not a section within it: NAMING.md is titled "... rebrand
        # vocabulary", and letting that title stand as a section made every heading in
        # the file a glossary section and turned its three naming rules into three
        # definitions. Document-level signals belong to classification, which already
        # reads the title.
        self.stack: list[tuple[int, str]] = []
        self.heading = ""
        self.trail = ""
        self.in_defs = False
        self.in_naming = False
        # A term-shaped heading in a glossary section may be defined by the paragraph
        # under it -- but only if nothing better defines it first.
        self.reporting = False
        self.pending: tuple[str, int, list[str]] | None = None
        self.subsection_defs = 0

    # -- emission ------------------------------------------------------------ #

    def _add_def(self, term: str, definition: str, line: int, form: DefForm, src: str) -> None:
        term = _clean_term(term)
        definition = _text(definition)
        if not _is_term_shaped(term) or len(definition) < 3:
            return
        self.subsection_defs += 1
        self.facts.definitions.append(
            DocDefinition(
                term=term, definition=definition, line=line, form=form,
                heading=self.heading, source_line=src.strip(),
            )
        )

    def _flush_pending(self) -> None:
        if self.pending and not self.subsection_defs:
            term, line, para = self.pending
            self._add_def(term, " ".join(para), line, DefForm.HEADING_PARA, term)
        self.pending = None

    # -- passes -------------------------------------------------------------- #

    def run(self) -> DocFacts:
        head_at = {h.line: h for h in self.facts.headings}
        i = self.start
        n = len(self.lines)
        while i < n:
            line = self.lines[i]
            lineno = i + 1

            if self.mask[i]:
                i += 1
                continue

            head = head_at.get(lineno)
            if head is not None:
                self._flush_pending()
                self.subsection_defs = 0
                while self.stack and self.stack[-1][0] >= head.level:
                    self.stack.pop()
                self.stack.append((head.level, head.text))
                self.heading = head.text
                self.trail = " > ".join(t for lvl, t in self.stack if lvl >= 2)
                trail = self.trail
                self.in_defs = bool(trail and self.rules.definition_headings.search(trail))
                self.in_naming = bool(trail and self.rules.naming_headings.search(trail))
                self.reporting = bool(self.trail and reports_rather_than_rules(self.trail))
                if self.in_defs and _is_term_shaped(head.text):
                    self.pending = (head.text, head.line, [])
                # A heading is prose too, and it is where a plan document states which
                # plan it is. Skipping it made the most canonical governance document
                # of all -- one titled by its id and never repeating it in the body --
                # contribute nothing to the traceability join. 58 real ids on Mensores
                # were invisible for this reason. The detector is unchanged; only the
                # lines it is offered are.
                if has_annotation(head.text):
                    self.facts.annotations.extend(
                        mine_annotations(head.text, head.line)
                    )
                i += 1
                continue

            self._refs(line, lineno)
            if has_annotation(line):
                self.facts.annotations.extend(mine_annotations(line, lineno))

            # A table is self-corroborating and needs no section.
            if "|" in line and i + 1 < n and TABLE_SEP.match(self.lines[i + 1]):
                i = self._table(i)
                continue

            if "<dl" in line.lower():
                i = self._deflist(i)
                continue

            if not line.strip():
                if self.pending and self.pending[2]:
                    self._flush_pending()
                i += 1
                continue

            if self.pending is not None and not self.mask[i]:
                self.pending[2].append(_text(line))

            self._definition(line, lineno)
            i = self._rule_unit(i)
        self._flush_pending()
        return self.facts

    # -- shapes -------------------------------------------------------------- #

    def _refs(self, line: str, lineno: int) -> None:
        for m in URL.finditer(line):
            self.facts.refs.append(DocRef(DocRefKind.URL, m.group(0), lineno))
        for m in BACKTICK.finditer(line):
            value = m.group(1).strip()
            if not value:
                continue
            kind = DocRefKind.PATH if PATHLIKE.fullmatch(value) else DocRefKind.CODE
            self.facts.refs.append(DocRef(kind, value, lineno))
        for m in PATHLIKE.finditer(line):
            self.facts.refs.append(DocRef(DocRefKind.PATH, m.group(0), lineno))

    def _table(self, i: int) -> int:
        """One pipe table, header and every row, whole."""
        header = [c.strip() for c in self.lines[i].strip().strip("|").split("|")]
        rows: list[list[str]] = []
        j = i + 2
        while j < len(self.lines) and "|" in self.lines[j] and self.lines[j].strip():
            if self.mask[j]:
                break
            rows.append([c.strip() for c in self.lines[j].strip().strip("|").split("|")])
            j += 1

        table = DocTable(line=i + 1, header=header, rows=rows, heading=self.heading)
        self.facts.tables.append(table)

        term_cols = [k for k, c in enumerate(header) if self.rules.term_columns.match(c)]
        mean_cols = [k for k, c in enumerate(header) if self.rules.meaning_columns.match(c)]
        # Both halves required. `| Name | Port |` is not a glossary.
        if term_cols and mean_cols:
            mean = mean_cols[0]
            for r, row in enumerate(rows):
                if mean >= len(row):
                    continue
                for t in term_cols:
                    if t < len(row) and t != mean:
                        # Every term-ish column is emitted. A table may name a thing
                        # twice -- "Harness" and `groma` -- and which of the two the
                        # code actually uses is decided later, at binding, not here.
                        self._add_def(row[t], row[mean], i + 3 + r,
                                      DefForm.TABLE_ROW, " | ".join(row))
        for offset, line in enumerate(self.lines[i:j]):
            for m in BACKTICK.finditer(line):
                self.facts.refs.append(DocRef(DocRefKind.CODE, m.group(1).strip(), i + 1))
            # A roadmap is a table, and a plan index is a table. Consuming table rows
            # without offering them to the annotation detector made every governance id
            # stated only in a table invisible to the traceability join -- `ADR-0057` is
            # named in `.groma/ROADMAP.md` and was reported as undocumented work.
            # Rule 12 in the other direction: a row is prose, and prose is where ids live.
            if has_annotation(line):
                self.facts.annotations.extend(mine_annotations(line, i + 1 + offset))
        return j

    def _deflist(self, i: int) -> int:
        """An HTML definition list, as `docs/reference/glossary.md` actually writes them."""
        j = i
        while j < len(self.lines) and "</dl>" not in self.lines[j].lower():
            j += 1
        block = "\n".join(self.lines[i : min(j + 1, len(self.lines))])
        terms = [(m.group("t"), block[: m.start()].count("\n")) for m in DT.finditer(block)]
        defs = [m.group("t") for m in DD.finditer(block)]
        for (term, offset), definition in zip(terms, defs, strict=False):
            self._add_def(term, definition, i + 1 + offset, DefForm.DEF_LIST, _text(term))
        return j + 1

    def _definition(self, line: str, lineno: int) -> None:
        """Prose definition shapes, admitted only where a glossary is being written."""
        if not (self.in_defs or self.facts.doc_class.value == "GLOSSARY"):
            return
        m = BOLD_DEF.match(line)
        if m:
            self._add_def(m.group("term"), m.group("def"), lineno, DefForm.BOLD_LEAD, line)
            return
        m = CODE_GLOSS.match(line)
        if m:
            self._add_def(m.group("term"), m.group("def"), lineno, DefForm.DASH_GLOSS, line)
            return
        m = BOLD_ALONE.match(line)
        if m:
            # `**mensor** *(noun)*` on its own line: the definition is what follows.
            para: list[str] = []
            k = lineno
            while k < len(self.lines) and self.lines[k].strip() and not self.mask[k]:
                para.append(_text(self.lines[k]))
                k += 1
            if para:
                self._add_def(m.group("term"), " ".join(para), lineno,
                              DefForm.BOLD_LEAD, line)

    def _rule_unit(self, i: int) -> int:
        """One prose unit -- a list item or a paragraph -- weighed as a stated rule."""
        line = self.lines[i]
        m = LIST_ITEM.match(line)
        j = i + 1
        if m:
            text = m.group("t")
            while j < len(self.lines) and self.lines[j].strip() and not self.mask[j]:
                if LIST_ITEM.match(self.lines[j]) or ATX.match(self.lines[j]):
                    break
                text += " " + self.lines[j].strip()
                j += 1
            is_item = True
        else:
            text = line.strip()
            while j < len(self.lines) and self.lines[j].strip() and not self.mask[j]:
                if LIST_ITEM.match(self.lines[j]) or ATX.match(self.lines[j]):
                    break
                text += " " + self.lines[j].strip()
                j += 1
            is_item = False

        # The unit's continuation lines never pass through the main loop, so anything
        # stated on the second line of a wrapped bullet was invisible to the annotation
        # detector. `ADR-0045` authored "at Plan 44-01 APPLY" on line 4 of a bullet
        # beginning on line 2, and the plan read as undocumented work in consequence.
        # Third instance of one defect: a branch that consumes lines without offering
        # them to every detector that wants them.
        for k in range(i + 1, j):
            if not self.mask[k] and has_annotation(self.lines[k]):
                self.facts.annotations.extend(
                    mine_annotations(self.lines[k], k + 1)
                )

        self._maybe_rule(_text(text), i + 1, is_item)
        return max(j, i + 1)

    def _maybe_rule(self, text: str, lineno: int, is_item: bool) -> None:
        """Three conditions, all required: right section, normative voice, a lane."""
        if len(text) < MIN_RULE_CHARS or text.startswith("|"):
            return
        if not may_state_rules(self.facts.doc_class):
            return
        in_standard = self.facts.doc_class.value == "NAMING_STANDARD"
        if not (self.in_naming or in_standard):
            return
        if self.reporting:
            return
        if not is_normative(text):
            return
        # Inside a naming section, shape is enough. Across the rest of a naming-standards
        # document, the sentence must at least be about naming -- otherwise a page of
        # trademark findings enters the standard on the strength of the word "classes".
        if not self.in_naming and not about_naming(text):
            return

        lane = rule_lane(text)
        if lane is not None:
            kind, scope, pattern = lane
            # Outside a naming section, a FORM rule must be checkable -- it must name
            # both a class of identifier and a spelling pattern. `docs/contributing/
            # conventions/naming.md` is titled "Naming standards (imported, not
            # prescribed)" and states no convention at all; its sentence "PDF is not
            # imported. If a standards directory contains a `.pdf`, the import is
            # refused and names the offending file" is product behaviour, and it
            # entered the standard on the strength of the word "directory".
            if not self.in_naming and not (scope and pattern):
                return
            self.facts.rules.append(
                DocRule(text=text, line=lineno, lane=kind, scope=scope, pattern=pattern,
                        heading=self.heading, checkable=bool(scope and pattern))
            )
            return

        # No identifier class and no spelling pattern. It is a vocabulary rule if it
        # is one of a list of rules under a naming heading, or if it is about naming
        # at all -- which is what keeps a naming document's trademark and domain
        # sections out of its naming standard.
        if (is_item and self.in_naming) or about_naming(text):
            self.facts.rules.append(
                DocRule(text=text, line=lineno, lane=RuleLane.VOCABULARY,
                        heading=self.heading, checkable=False)
            )


def scan_markdown(path: str, rel: Path, text: str, fmt: DocFormat = DocFormat.MARKDOWN) -> DocFacts:
    return _Scanner(path, rel, text, fmt).run()


def scan_with(path: str, rel: Path, text: str, fmt: DocFormat,
              headings_fn: HeadingsFn | None) -> DocFacts:
    """The same reading, for a format that marks its headings differently."""
    return _Scanner(path, rel, text, fmt, headings_fn).run()
