"""Governance ids, joined across the two stores: what was built, and what was planned.

Both halves are already ingested. Code annotations mined from comments and docstrings
live in `graph.db.annotations`; the same ids mined from prose live in
`docs.db.doc_annotations`. Joining them needs no model -- it is one `ATTACH DATABASE`
and a normalisation rule -- and it answers the question neither store answers alone:
**what was built without a plan, and what was planned without being built?**

Two things make this harder than an intersection, and both are the point.

**An id is not present or absent; it has a standing.** Being the subject of a document
of its own is not the same as being name-dropped in someone else's paragraph, and one
code annotation is not the same as forty. So the report grades rather than partitions:
seven states along a spectrum from *both ends meet* to *nothing meets*, each carrying
the evidence that placed it there so a reader can move it.

**"Planned and never built" is not observable.** A plan can land perfectly and simply
never be cited in a comment; DunneFlow would see the same absence either way. What can
be observed is weaker and honest: whether the code symbols a plan names actually exist
in the program. `CL-68`'s documents name `AnthropicPMActor` and `CompositeProbingStrategy`
and both exist, which is real evidence the work landed unannotated. That signal has to
be filtered hard, because rule 5 applies to it exactly: a plan that names `check`,
`apply` and `error` has named nothing. Only symbols that are *unique in the program*
count, and the surviving names are printed so the reader can weigh them.

Nothing here needs a model, and nothing here is a verdict.
"""

from __future__ import annotations

import builtins
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cache

from ..docstore import DocStore
from ..schema import Confidence
from ..store import Store

# An id is a marker with a number in it. `WARNING`, `TODO` and `Audit-locked` are
# markers too, but they name a category rather than a unit of work and cannot be
# traced to anything. Deriving the set this way rather than listing kinds by hand
# means a new rule in `detectors/annotations.yaml` is included without a code edit
# -- and cannot drift out of step with it.
IS_ID = re.compile(r"^[A-Za-z]+[\s\-_.]?\d")

# Splits `Plan 01-04` / `ADR-0001` / `G11` into a prefix and its numbered segments.
_SPLIT = re.compile(r"^([A-Za-z]+)[\s\-_.]*(.*)$")
_SEGMENT = re.compile(r"^0*(\d+)([A-Za-z]*)$")

# Anything id-shaped inside a title or heading, so a document can be asked which ids
# it is *about*. Deliberately loose: it is filtered immediately against ids actually
# mined from the corpus, so a false catch here matches nothing and costs nothing.
_ID_IN_TEXT = re.compile(r"\b[A-Za-z]{1,10}[\s\-_.]?\d[\w\-.]*")

# A backticked span is a code reference only if it could be an identifier. The corpus
# holds shell lines, YAML fragments and prose in backticks too.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,}$")

# Rule 3, in a new place. A program that happens to define one thing called `list` does
# not make every document naming `list` evidence of that thing. `ADR-59`'s entire claim
# to having landed was the word `list`, and it was the only such case on Mensores --
# which is why the exclusion is this narrow and not a guessed stopword list.
#
# **This interpreter's builtins, and so Python's alone** -- deliberately left as it is
# rather than derived from what the map holds, because deriving it would be a claim and
# not a fix: there is no list of TypeScript's or Go's builtins here to exclude, and a
# sentence saying *the builtins of every language read are excluded* would be false the
# first time a second language arrived. The page says which language's these are; the
# list itself moves when `_BUILTINS` moves into `python.yaml` with its twin in
# `resolve/calls.py`, which is the resolver chunk's work and not this one's.
_BUILTINS = frozenset(dir(builtins))

# How many distinctive symbols a plan must name, and have exist, before its work is
# called likely rather than possible. Printed in the report so it can be argued with.
STRONG_LANDED_SYMBOLS = 3


# Called once per annotation row -- 48,706 times on Mensores for about 1,300 distinct
# values. The cache is what keeps that a rounding error rather than three seconds.
@cache
def normalise(value: str) -> str:
    """`ADR-0001`, `ADR 1` and `adr_1` are one id. `Plan 01-04` is not `PLAN-01`.

    Case, separator and zero-padding are dropped; the number of segments is not, which
    is what keeps a two-part plan id distinct from a one-part ticket that shares its
    prefix. A trailing letter is part of the segment -- `Plan 87-02c` is not `Plan 87-02`.
    """
    m = _SPLIT.match(value.strip().upper())
    if not m:
        return value.strip().upper()
    prefix, rest = m.group(1), m.group(2)
    segments: list[str] = []
    for part in (p for p in re.split(r"[\s\-_.]+", rest) if p):
        seg = _SEGMENT.match(part)
        segments.append(f"{int(seg.group(1))}{seg.group(2)}" if seg else part)
    return "-".join([prefix, *segments]) if segments else prefix


# --------------------------------------------------------------------------- #
# The states, in order from both ends meeting to neither
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class State:
    """One band of the spectrum, and what would make placing an id here wrong."""

    key: str
    label: str
    meaning: str
    blind_spot: str


STATES: tuple[State, ...] = (
    State(
        "TRACED",
        "Traced",
        "A document is about it, and the code cites it. Both ends meet.",
        "A document can be about an id without governing the code that cites it; the "
        "join proves they share a name, not that either honours the other.",
    ),
    State(
        "THINLY_TRACED",
        "Thinly traced",
        "The code cites it and prose mentions it, but nothing is written about it. "
        "The plan may be a line inside someone else's document.",
        "A document whose title and headings never name the id it is about reads as a "
        "mention here. Heading style, not absence of a plan, may be what was measured.",
    ),
    State(
        "UNDOCUMENTED_WORK",
        "Undocumented work",
        "The code cites it and the corpus does not contain it at all. Work done "
        "against a plan this scan cannot see.",
        "The plan may live outside the scanned corpus -- another repository, an issue "
        "tracker, a wiki -- so absence here is absence from `--docs`, nothing wider. "
        "It may also have a document that never writes its own id in prose: "
        "`68-03-PLAN.md` declares itself in YAML frontmatter as `phase: 68-...` and "
        "`plan: 03`, and the string `Plan 68-03` appears nowhere in the corpus. The "
        "id is read from prose, so a convention that states it only in frontmatter or "
        "a filename is invisible here.",
    ),
    State(
        "LIKELY_LANDED",
        "Likely landed, never annotated",
        "A document is about it, no comment cites it, but several code symbols it "
        "names by hand exist in the program.",
        "A symbol can exist because something else created it. This is evidence of "
        "arrival, never proof of it, and it says nothing about correctness.",
    ),
    State(
        "POSSIBLY_LANDED",
        "Possibly landed, never annotated",
        "The same, on one or two symbols. Enough to look, not enough to believe.",
        "One or two matches is close to what coincidence supplies on its own; the "
        "matched names are printed because they are the whole of the evidence.",
    ),
    State(
        "NO_TRACE_IN_CODE",
        "No trace in code",
        "A document is about it, no comment cites it, and none of the symbols it "
        "names exist. The strongest available reading of planned and not built.",
        "A plan that names no code at all lands here for want of a signal rather than "
        "for want of an implementation; the symbol count beside it says which.",
    ),
    State(
        "PASSING_REFERENCE",
        "Passing reference",
        "Mentioned in prose, never written about, never cited in code. Usually a "
        "pointer at something outside this program.",
        "An id whose own document was not scanned -- or was scanned and titled "
        "differently -- looks like a passing reference to it.",
    ),
)

STATE_ORDER: dict[str, int] = {s.key: i for i, s in enumerate(STATES)}
BY_KEY: dict[str, State] = {s.key: s for s in STATES}


# --------------------------------------------------------------------------- #
# What was found
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class CodeSite:
    """One place in the source that cites an id."""

    owner: str
    owner_kind: str
    file: str
    line: int
    text: str


@dataclass(slots=True)
class DocSite:
    """One place in the corpus that names an id.

    `stated` is False when the id was composed from the document's frontmatter or
    filename rather than written in its prose. Such a document is real and the id is
    probably right, but nothing in it says so in words, and the two are never merged.
    """

    doc: str
    line: int
    title: str
    doc_class: str
    text: str
    stated: bool = True


@dataclass(slots=True)
class TracedId:
    """One governance id and everything both stores say about it."""

    id: str
    forms: list[str] = field(default_factory=list)      # every raw spelling seen
    kinds: list[str] = field(default_factory=list)      # PLAN, ADR, ...
    code: list[CodeSite] = field(default_factory=list)
    subjects: list[DocSite] = field(default_factory=list)   # documents about it
    mentions: list[DocSite] = field(default_factory=list)   # documents citing it
    landed: list[str] = field(default_factory=list)     # distinctive symbols that exist
    named: int = 0                                      # symbols it named at all
    family_in_docs: bool = False   # does the corpus know this prefix at all?

    @property
    def state(self) -> str:
        if self.code:
            if self.subjects:
                return "TRACED"
            return "THINLY_TRACED" if self.mentions else "UNDOCUMENTED_WORK"
        if self.subjects:
            if len(self.landed) >= STRONG_LANDED_SYMBOLS:
                return "LIKELY_LANDED"
            return "POSSIBLY_LANDED" if self.landed else "NO_TRACE_IN_CODE"
        return "PASSING_REFERENCE"

    @property
    def prefix(self) -> str:
        return self.id.split("-", 1)[0]

    def documents(self) -> list[DocSite]:
        return [*self.subjects, *self.mentions]

    @property
    def stated_anywhere(self) -> bool:
        """Does any document write this id out, as opposed to implying it?"""
        return any(site.stated for site in self.documents())

    @property
    def by_inference_only(self) -> bool:
        """Known to the documentation, but only because a convention was applied.

        The load-bearing case: `Plan 68-03` has a plan document, an audit and a
        summary, and the string appears nowhere in the corpus. Without the convention
        it reads as work built against no plan; with it, and unmarked, it would read
        as though someone had written the plan down. Neither is true.
        """
        docs = self.documents()
        return bool(docs) and not any(site.stated for site in docs)


@dataclass(slots=True)
class Traceability:
    """The whole join, plus what it could not see."""

    ids: list[TracedId] = field(default_factory=list)
    had_docs: bool = True
    documents_scanned: int = 0
    duplicates_ignored: int = 0
    code_annotations: int = 0
    doc_annotations: int = 0
    unique_symbols: int = 0
    total_symbols: int = 0
    doc_prefixes: list[str] = field(default_factory=list)
    inferred_annotations: int = 0
    merged_forms: list[tuple[str, list[str]]] = field(default_factory=list)

    def by_state(self) -> dict[str, list[TracedId]]:
        out: dict[str, list[TracedId]] = {s.key: [] for s in STATES}
        for t in self.ids:
            out[t.state].append(t)
        for group in out.values():
            group.sort(key=lambda t: (t.prefix, _sortable(t.id)))
        return out

    def counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.by_state().items()}

    def in_code(self) -> int:
        return sum(1 for t in self.ids if t.code)

    def by_inference_only(self) -> list[TracedId]:
        """Ids whose entire documentary standing rests on a naming convention."""
        return sorted(
            (t for t in self.ids if t.by_inference_only),
            key=lambda t: (t.prefix, _sortable(t.id)),
        )

    def traced(self) -> int:
        return sum(1 for t in self.ids if t.code and (t.subjects or t.mentions))


def _sortable(identifier: str) -> tuple[object, ...]:
    """Sort `ADR-9` before `ADR-10`, which a plain string sort will not."""
    return tuple(
        int(p) if p.isdigit() else p for p in re.split(r"[-]", identifier)
    )


# --------------------------------------------------------------------------- #
# Measuring
# --------------------------------------------------------------------------- #

# Every claim in the rendered report is reproducible through `dunneflow query --docs`,
# which attaches the document store as `docs`. Kept as text, for the same reason the
# naming lane keeps its queries as text: a number a reader cannot re-derive is an
# assertion, and one whose query returns something else is worse than no query at all.
CODE_IDS_SQL = (
    "SELECT DISTINCT value, owner_id, line FROM annotations "
    "WHERE value GLOB '*[0-9]*'"
)
DOC_IDS_SQL = (
    "SELECT DISTINCT a.value, a.doc, a.line FROM docs.doc_annotations a "
    "JOIN docs.documents d ON d.path = a.doc "
    "WHERE d.duplicate_of = '' AND a.value GLOB '*[0-9]*'"
)


def _symbol_population(store: Store) -> Counter[str]:
    """How many distinct things in the program answer to each name.

    A name that means one thing is evidence; a name that means twenty-two is rule 5's
    trap. `__init__` names 217 routines in Mensores and could never distinguish a plan.

    Counted over *identities*, not rows. A dataclass is recorded as both a structure
    and a class -- 570 names on Mensores sit in both tables -- and summing rows would
    give every one of them a population of two, disqualifying as evidence exactly the
    distinctive type names a plan document is most likely to cite.
    """
    identities: defaultdict[str, set[str]] = defaultdict(set)
    for sql, keyed_by_module in (
        ("SELECT name, module FROM routines WHERE name NOT GLOB '<*>'", True),
        ("SELECT name, module FROM structures", True),
        ("SELECT name, module FROM classes", True),
        ("SELECT name, file FROM db_tables", False),
    ):
        for row in store.query(sql):
            name, where = row[0], row[1]
            if name:
                identities[name].add(f"{where}" if keyed_by_module else f"table:{where}")
    return Counter({name: len(where) for name, where in identities.items()})


def measure(store: Store, docs: DocStore | None) -> Traceability:
    """Join both stores on normalised governance ids and grade every one."""
    result = Traceability(had_docs=docs is not None)
    found: dict[str, TracedId] = {}

    def entry(raw: str, kind: str) -> TracedId:
        key = normalise(raw)
        t = found.get(key)
        if t is None:
            t = found[key] = TracedId(id=key)
        if raw not in t.forms:
            t.forms.append(raw)
        if kind not in t.kinds:
            t.kinds.append(kind)
        return t

    # --- the code half ---------------------------------------------------- #
    # One marker can be caught by two detectors -- `ADR-0057` matches both the ADR rule
    # and the general TICKET rule, and `ISS-014` matches both ISSUE and TICKET. The
    # extractor rightly records both readings, but they are one citation in one place,
    # and counting them twice would say a plan is cited four times when it is cited
    # twice. Deduplicated on where it is, with every reading kept in `kinds`.
    # Keyed on exactly what CODE_IDS_SQL selects, so the count printed in the report
    # and the query printed beside it cannot disagree -- rule 13.
    seen_code: set[tuple[str, str, int]] = set()
    for row in store.query(
        """SELECT a.kind, a.value, a.line, a.text, a.owner_kind, a.owner_id,
                  COALESCE(r.qualname, s.name, '') AS owner,
                  COALESCE(r.file, s.file, '')     AS file
             FROM annotations a
             LEFT JOIN routines   r ON a.owner_id = r.id
             LEFT JOIN structures s ON a.owner_id = s.id
            ORDER BY a.kind, a.value"""
    ):
        if not IS_ID.match(row["value"]):
            continue
        t = entry(row["value"], row["kind"])
        where = (row["value"], row["owner_id"], row["line"])
        if where in seen_code:
            continue
        seen_code.add(where)
        result.code_annotations += 1
        t.code.append(
            CodeSite(
                owner=row["owner"], owner_kind=row["owner_kind"],
                file=row["file"], line=row["line"], text=row["text"],
            )
        )

    if docs is None:
        result.ids = list(found.values())
        return result

    # --- the documentation half ------------------------------------------- #
    # Worktree copies of the project's own research are content-addressed and already
    # marked. Counting them would inflate every mention count by the number of agents
    # that happened to be running.
    live: dict[str, tuple[str, str]] = {}
    for row in docs.query(
        "SELECT path, title, doc_class FROM documents WHERE duplicate_of = ''"
    ):
        live[row["path"]] = (row["title"] or "", row["doc_class"])
    result.documents_scanned = len(live)
    result.duplicates_ignored = len(
        docs.query("SELECT 1 FROM documents WHERE duplicate_of <> ''")
    )

    # A document is *about* an id when its title or one of its top two heading levels
    # names it. Deeper headings are structure inside a document, not its subject.
    about: dict[str, set[str]] = defaultdict(set)
    for path, (title, _class) in live.items():
        for hit in _ID_IN_TEXT.findall(title):
            about[path].add(normalise(hit))
    for row in docs.query("SELECT doc, text FROM headings WHERE level <= 2"):
        if row["doc"] in live:
            for hit in _ID_IN_TEXT.findall(row["text"] or ""):
                about[row["doc"]].add(normalise(hit))

    seen_docs: set[tuple[str, str, int]] = set()   # as DOC_IDS_SQL selects
    placed: set[tuple[str, str]] = set()          # (id, document) already recorded
    for row in docs.query(
        "SELECT doc, kind, value, line, text, confidence FROM doc_annotations"
        " ORDER BY value"
    ):
        doc = row["doc"]
        if doc not in live or not IS_ID.match(row["value"]):
            continue
        t = entry(row["value"], row["kind"])
        where = (row["value"], doc, row["line"])
        if where in seen_docs:
            continue
        seen_docs.add(where)
        result.doc_annotations += 1
        stated = row["confidence"] != Confidence.INFERRED
        if not stated:
            result.inferred_annotations += 1
        title, doc_class = live[doc]
        site = DocSite(doc=doc, line=row["line"], title=title,
                       doc_class=doc_class, text=row["text"], stated=stated)
        # A document that only implies its id is still *about* it -- that is the whole
        # point of composing one -- but the implication travels with the evidence, and
        # the report never shows it as something a person wrote down.
        bucket = (
            t.subjects if (not stated or t.id in about.get(doc, ())) else t.mentions
        )
        # A set rather than a scan of the bucket: `AC-1` is named in 385 documents and
        # cited 24,096 times, and re-scanning its list per row is quadratic.
        if (t.id, doc) not in placed:
            placed.add((t.id, doc))
            bucket.append(site)

    # --- did the unannotated ones land? ------------------------------------ #
    pop = _symbol_population(store)
    unique = {name for name, n in pop.items()
              if n == 1 and name not in _BUILTINS}
    result.total_symbols, result.unique_symbols = len(pop), len(unique)

    # Only documents that are the subject of an *unannotated* id can contribute
    # evidence, which is a few hundred of the corpus rather than all of it. Filtering
    # first turns 142,672 identifier tests into a few thousand.
    wanted: set[str] = {
        site.doc
        for t in found.values()
        if not t.code
        for site in t.subjects
    }
    named_by_doc: dict[str, set[str]] = defaultdict(set)
    if wanted:
        for row in docs.query("SELECT doc, value FROM doc_refs WHERE kind = 'CODE'"):
            if row["doc"] in wanted and _IDENTIFIER.match(row["value"]):
                named_by_doc[row["doc"]].add(row["value"])

    for t in found.values():
        if t.code or not t.subjects:
            continue
        named: set[str] = set()
        for site in t.subjects:
            named |= named_by_doc.get(site.doc, set())
        t.named = len(named)
        t.landed = sorted(named & unique)

    # A prefix the documentation has never once used is not a governance vocabulary
    # this corpus tracks. `DRAFT-05` is a finding code the EARS validator emits and
    # `AR-7` an assessor role named in a docstring; both are real, both are cited in
    # code, and neither will ever have a plan. Rule 5 again -- the general TICKET rule
    # catches any domain vocabulary shaped like an id. Recorded rather than filtered,
    # because the distinction is the reader's to draw and dropping it silently would
    # be the worse error.
    known = {t.prefix for t in found.values() if t.subjects or t.mentions}
    result.doc_prefixes = sorted(known)
    for t in found.values():
        t.family_in_docs = t.prefix in known

    result.merged_forms = sorted(
        (t.id, sorted(t.forms)) for t in found.values() if len(t.forms) > 1
    )
    result.ids = list(found.values())
    return result
