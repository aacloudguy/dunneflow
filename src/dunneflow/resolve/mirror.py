"""The traceability report's mirror: vocabulary the documentation defines that the
program does not use.

`12-traceability.md` asks what was built without a plan. This asks the same question of
words: **the project took the trouble to define this term -- does anything answer to
it?** A term defined and never used is either drift (the thing was renamed, or never
built) or a word the documentation needs and the code does not. Both are worth seeing,
and neither is visible from either store alone.

Two things had to be got right before the query was worth running, and both were found
by checking the first finding rather than reporting it.

**`tabularium` was not drift.** It is glossed in Mensores' pantheon table and appeared
in the glossary nowhere, which read as a term the program had abandoned. It is in fact
the most-named artefact in the program -- `tabularium.db`, 52 references across 25
files -- and DunneFlow could not see it because it recorded no file the program names.
A path assembled as `root / ".mensores" / "tabularium.db"` is not a module, not a
table, and not a boundary target: only the parts are literals. `schema.Artefact` exists
because of this one word, and the answer to "is this term used?" is now a fifth surface.

**A term is not used or unused; it has a standing.** `tabularium` names a database.
`term_name` is a parameter and nothing else. `SARIF` appears only in a sentence about a
format the program does not emit. `Frozenset discipline` appears nowhere at all. Four
bands, each stating what would make a placement in it wrong -- the same register as the
traceability report, for the same reason.

**And the admission rule is the report.** Run forwards, the join to code filtered the
definition extractor's over-reach for free: a heading admitted as a term simply matched
nothing and was never seen. Run backwards there is no such filter, and 87 of Mensores'
213 definitions are not terms -- test names, code fragments, numbered headings,
sentences. Reporting them as vocabulary the program ignores would be a finding about
DunneFlow wearing a finding about Mensores. So they are excluded here, by a rule stated
on the page, counted, and listed whole (rule 8): the reader can see exactly what was
set aside and argue with the line.

The exclusions are filtered in this report rather than at ingest deliberately. The
glossary and naming lanes are verified against ground truth as they stand; tightening
the definition extractor is a separate change with its own before-and-after, and this
report is where the evidence for making it accumulates.

Nothing here needs a model.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..docstore import DocStore
from ..store import Store
from . import languages

# --------------------------------------------------------------------------- #
# Admission: what counts as a term at all
# --------------------------------------------------------------------------- #

# A term is at most this many words. `Society of Mensores` is vocabulary; `Files likely
# modified` is a heading that the definition extractor read as one. Three is where the
# corpus separates -- every 4-or-more-word entry on Mensores is a sentence, and the
# 2-and-3-word entries include `Audit event`, `Decision graph` and `Reader tier`, all of
# which the program genuinely does or does not use.
MAX_TERM_WORDS = 3

# Anything a person would read as code rather than as a name.
_CODE_SHAPED = re.compile(r"[()\[\]{}<>/\\]|->|::|\s=\s")

# A numbered or quoted section heading: `1.1 Term identity model`, `§ 7.1 — Definition`,
# `"Touched" Definition`, `(A) Designated-repo model`, `A3. GLOSSARY.md conventions`.
# The appendix form (`A1.`, `A2.`) is a letter and a number, which is also the shape of
# a real term -- `G7`, `CC2.1` -- so it is admitted only with the trailing dot and a
# following word, which no term has.
_HEADING_SHAPED = re.compile(r"^[\d§\"'(\[]|^\d+\.|^[A-Z]\d*\.\s+\S")

# A definition whose term is a declaration: `class _AbAssignment`. The extractor read
# the whole line; the name is the second word and the first is syntax.
_DECLARATION = re.compile(r"^(class|def|async|import|from|return|struct|interface)\s",
                          re.IGNORECASE)

# Punctuation that only appears mid-sentence. A term does not carry a comma.
_SENTENCE_PUNCT = re.compile(r"[,;:!?]|\s[—–-]\s")


@dataclass(frozen=True, slots=True)
class Exclusion:
    """One reason a defined term is not treated as vocabulary, and its cost."""

    key: str
    label: str
    why: str


EXCLUSIONS: tuple[Exclusion, ...] = (
    Exclusion(
        "TEST_NAME", "A test name",
        "`test_adr_0012_has_carve_out_criteria_section` is an assertion the corpus "
        "makes about itself, not a word the program is asked to answer to.",
    ),
    Exclusion(
        "CODE_SHAPED", "Code, not a word",
        "`read_all() -> dict` and `src/app/cli/_root.py (lines 110-115)` are "
        "spans of code the definition extractor read as terms. Rule 12 in the mirror: "
        "a signature is a statement, not a name.",
    ),
    Exclusion(
        "HEADING_SHAPED", "A numbered or quoted heading",
        "`1.1 Term identity model` and `§ 7.1 — Definition` are positions in a "
        "document. The heading is real; the term is the document's structure.",
    ),
    Exclusion(
        "SENTENCE", "A phrase, not a term",
        f"More than {MAX_TERM_WORDS} words, or carrying sentence punctuation. "
        "`Files likely modified` and `Auto-fixed — the nomenclature-census net-new` "
        "describe something; they do not name it.",
    ),
    Exclusion(
        "TOO_SHORT", "Too short to match on",
        "Fewer than three characters. Rule 5: `CC` and `G7` would match everywhere "
        "and mean nothing.",
    ),
)

BY_EXCLUSION: dict[str, Exclusion] = {e.key: e for e in EXCLUSIONS}

MIN_TERM_LENGTH = 3

# Splits a compound name into the words a person joined to make it: `audit_event`,
# `auditEvent` and `audit-event` all yield `audit` and `event`. Splitting is not
# substring matching -- `aggregate` has no boundary in it and stays one word.
_WORDS = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def name_keys(name: str) -> set[str]:
    """Every word-run a compound name contains, as identity keys.

    `TOOL_STATUS_RAN` is three words a person joined, and the program uses `tool
    status` as surely as it uses `tool`. Whole name and single words alone missed that:
    a term matching the *front* of a compound matched nothing.

    Contiguous runs only, and still identity rather than containment -- `aggregate` has
    no word boundary in it and yields one key, never `gate`. Measured before it was
    added: on Mensores it moves exactly one term, `tool_status`, onto three constants
    that genuinely name it, and produces no false placement at all.
    """
    parts = [p for p in _WORDS.split(name) if p]
    keys = {key_of(name)}
    for size in range(1, len(parts) + 1):
        for i in range(len(parts) - size + 1):
            keys.add(key_of("".join(parts[i : i + size])))
    return {k for k in keys if len(k) >= MIN_TERM_LENGTH}


def admit(term: str) -> str | None:
    """None if the term is vocabulary; otherwise the key of the rule that rejected it.

    Deliberately conservative in one direction only: a rejected term is listed whole on
    the page with the rule that rejected it, so an over-eager rule costs a reader one
    glance rather than a silent omission.
    """
    t = term.strip()
    if len(t.replace(" ", "")) < MIN_TERM_LENGTH:
        return "TOO_SHORT"
    if t.lower().startswith("test_"):
        return "TEST_NAME"
    if _CODE_SHAPED.search(t) or _DECLARATION.match(t):
        return "CODE_SHAPED"
    if _HEADING_SHAPED.match(t):
        return "HEADING_SHAPED"
    if _SENTENCE_PUNCT.search(t) or len(t.split()) > MAX_TERM_WORDS:
        return "SENTENCE"
    return None


# --------------------------------------------------------------------------- #
# The bands, from the program answering to a word to never having heard it
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Band:
    """One standing a defined term can have in the code, and its blind spot."""

    key: str
    label: str
    meaning: str
    # May carry `{languages}`, which is filled in by `spot()` from what the map actually
    # holds. A blind spot that names a language is a claim about the map rather than
    # about the band, and it was written as a constant while there was only ever one
    # answer to it.
    blind_spot: str

    def spot(self, langs: Sequence[str]) -> str:
        """The blind spot, with what was actually read filled in.

        `replace` rather than `format`, deliberately: every other band's text is prose
        full of backticks and punctuation, and a stray brace in one of them would turn a
        sentence into an exception on a page nobody was editing.
        """
        return self.blind_spot.replace("{languages}", languages.named(langs) or "nothing")


BANDS: tuple[Band, ...] = (
    Band(
        "NAMED",
        "Named",
        "Something in the program is called this: a package, a class, a table, a way "
        "in, a constant, or a file the program names. The word is load-bearing.",
        "A name can survive the thing it named. `witness.db` proves the word is "
        "written down, not that the definition beside it is still what the code "
        "means by it.",
    ),
    Band(
        "BORNE",
        "Borne",
        "A routine, a parameter or a field carries the word, but nothing is called it. "
        "The program uses the term without naming a thing after it.",
        "A parameter name is a local choice. `term_name` may be borrowing an ordinary "
        "English compound rather than honouring the definition, and this band cannot "
        "tell the two apart.",
    ),
    Band(
        "SPOKEN",
        "Spoken",
        "The word appears only in comments and docstrings. The program talks about it; "
        "nothing is named for it.",
        "Prose about a word is often prose about *not* doing it — `SARIF` may appear "
        "only in a note explaining that the program emits something else. The band "
        "says the word was said, never that it was meant.",
    ),
    Band(
        "ABSENT",
        "Absent",
        "Defined in documentation, and nowhere in the code at all. The strongest "
        "signal of drift the two stores can produce together.",
        "One blind spot still puts words here that the program does use: this map was "
        "read from {languages} alone, so a word living in a shell script, a template, a "
        "front end or a sibling program is absent from this graph and present in the "
        "product. Two "
        "others have been closed, and both moved terms out of this band -- comments "
        "outside every function were not recorded at all, 53% of them, and a "
        "module-level constant was not a recorded name, so `JTBD_OPENERS` read as "
        "abandoned while the program declared it and read it six times. *Absent from "
        "this graph* is the claim. Absent is not.",
    ),
)

# A `plural()` and its `_PLURALS` table lived here, because adding an "s" gave "23 classs"
# and "3 way ins" -- both of which a reader reads as a defect in the tool before they read
# the number. It went with `surface_summary()`, its only caller. **Bring both back together
# if a surface is ever counted in prose again**: the two exceptions are the whole content,
# and re-deriving them from a defect on screen is the expensive way to learn them twice.


BAND_ORDER: dict[str, int] = {b.key: i for i, b in enumerate(BANDS)}
BY_BAND: dict[str, Band] = {b.key: b for b in BANDS}

# Which surfaces put a term in which band. The band is decided by the strongest
# surface a term appears on, so a word that is both a class and a comment is Named.
NAMING_SURFACES = ("module", "class", "table", "way in", "artefact", "constant")
BEARING_SURFACES = ("routine", "param", "field")
SPEAKING_SURFACES = ("comment", "docstring")


# --------------------------------------------------------------------------- #
# What was found
# --------------------------------------------------------------------------- #


def key_of(text: str) -> str:
    """The identity two names share when they name the same thing.

    `Audit event`, `AuditEvent` and `audit_event` are one word; `auditor` is not.
    Deliberately an exact identity rather than a substring test -- rule 5 -- because
    `Gate` as a substring matches `aggregate`, `delegate` and `mitigated`.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _prose_pattern(term: str) -> re.Pattern[str]:
    """A word-boundary match for a term in prose, tolerant of how it is joined.

    `audit event`, `audit-event` and `AuditEvent` are all the term being spoken; the
    letters either side of it are not.
    """
    words = [re.escape(w) for w in re.split(r"[^A-Za-z0-9]+", term) if w]
    if not words:
        return re.compile(r"(?!)")
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\s_.\-]?".join(words) + r"(?![A-Za-z0-9])",
                      re.IGNORECASE)


@dataclass(slots=True)
class Sighting:
    """One place the program uses a word, and what kind of use it is."""

    surface: str      # module | class | table | way in | artefact | routine | ...
    name: str         # the code name that matched, as written
    where: str        # file, module, or another locating string
    detail: str = ""  # how many times, when the surface is counted rather than named


@dataclass(slots=True)
class Definition:
    """One thing a document says a term means."""

    definition: str
    doc: str
    line: int
    form: str
    heading: str = ""


@dataclass(slots=True)
class MirroredTerm:
    """A word the documentation defines, and everything the code does with it."""

    term: str
    definitions: list[Definition] = field(default_factory=list)
    sightings: list[Sighting] = field(default_factory=list)

    @property
    def band(self) -> str:
        surfaces = {s.surface for s in self.sightings}
        if surfaces & set(NAMING_SURFACES):
            return "NAMED"
        if surfaces & set(BEARING_SURFACES):
            return "BORNE"
        if surfaces & set(SPEAKING_SURFACES):
            return "SPOKEN"
        return "ABSENT"

    def by_surface(self) -> dict[str, list[Sighting]]:
        out: dict[str, list[Sighting]] = defaultdict(list)
        for s in self.sightings:
            out[s.surface].append(s)
        return dict(out)

    # A `surface_summary()` stood here -- *"1,204 constants, 3 ways in"* -- and nothing
    # called it. `render/mirror.py` asks `by_surface()` the same question and answers it
    # differently on purpose: it names the surface, shows up to four of the words, and says
    # how many more. That is a listing with a count in it, not a count; the renderer needs
    # the names, and this returned only the tally. It went with `plural()`, its one caller,
    # which is why "23 classes" is no longer spelled anywhere -- there is nothing left that
    # counts a surface without naming what it found.


@dataclass(slots=True)
class Mirror:
    """The whole mirror, plus everything it set aside and why."""

    terms: list[MirroredTerm] = field(default_factory=list)
    excluded: dict[str, list[str]] = field(default_factory=dict)
    # What the graph was read from, on the report rather than asked of a store again:
    # every page that explains an absence has to name the languages it could see, and a
    # renderer holds no store to ask (rule 87, in the small).
    langs: list[str] = field(default_factory=list)
    had_docs: bool = True
    definitions_seen: int = 0
    documents_scanned: int = 0
    artefacts_seen: int = 0
    artefact_names: int = 0

    def by_band(self) -> dict[str, list[MirroredTerm]]:
        out: dict[str, list[MirroredTerm]] = {b.key: [] for b in BANDS}
        for t in self.terms:
            out[t.band].append(t)
        for group in out.values():
            group.sort(key=lambda t: t.term.lower())
        return out

    @property
    def excluded_total(self) -> int:
        return sum(len(v) for v in self.excluded.values())


# --------------------------------------------------------------------------- #
# The queries, shipped so every count on the page can be re-run (rule 13)
# --------------------------------------------------------------------------- #

DEFINED_TERMS_SQL = """
SELECT DISTINCT d.term, d.definition, d.doc, d.line, d.form, d.heading
  FROM definitions d
  JOIN documents dc ON dc.path = d.doc
 WHERE dc.duplicate_of = ''
 ORDER BY d.term, d.doc, d.line, d.form, d.heading
""".strip()

ARTEFACT_NAMES_SQL = """
SELECT stem, name, kind, COUNT(*) refs, COUNT(DISTINCT file) files
  FROM artefacts
 GROUP BY stem, name, kind
 ORDER BY refs DESC, stem, name, kind
""".strip()


def term_evidence_sql(term: str) -> str:
    """The query that lists every code name matching one term.

    Printed beside the term so a reader can re-run it. Rule 13: a query that returns
    something other than what is printed beside it is worse than no query at all.
    """
    k = key_of(term)
    return (
        "SELECT 'module' surface, module name, path FROM files\n"
        f" WHERE replace(replace(lower(module),'_',''),'.','') LIKE '%{k}%'\n"
        "UNION ALL\n"
        "SELECT 'class', name, file FROM classes\n"
        f" WHERE replace(lower(name),'_','') = '{k}'\n"
        "UNION ALL\n"
        "SELECT 'artefact', name, file FROM artefacts\n"
        f" WHERE replace(replace(lower(stem),'_',''),'-','') = '{k}'"
    )


# --------------------------------------------------------------------------- #
# The join
# --------------------------------------------------------------------------- #


def _index_code(store: Store) -> dict[str, list[Sighting]]:
    """Every word the program uses as a name, keyed by identity.

    Five naming surfaces and three bearing ones. The artefact surface is the one this
    report was built for: without it `tabularium` reads as a word Mensores defined and
    abandoned, when it is the name of the database the whole program writes to.
    """
    index: dict[str, list[Sighting]] = defaultdict(list)

    seen: set[tuple[str, str, str, str]] = set()

    def note(word: str, surface: str, name: str, where: str, detail: str = "") -> None:
        k = key_of(word)
        if len(k) < MIN_TERM_LENGTH:
            return
        # A one-word stem is indexed as the whole stem and as its only word, and a
        # module part can equal its module. The same code name sighted twice on the
        # same surface is one sighting; two files naming `tabularium.db` are two.
        if (k, surface, name, where) in seen:
            return
        seen.add((k, surface, name, where))
        index[k].append(Sighting(surface=surface, name=name, where=where, detail=detail))

    def note_words(word: str, surface: str, name: str, where: str) -> None:
        """A compound name, indexed under every word-run a person joined to make it.

        `disceptator_handle` carries `disceptator` as surely as `bootstrap-config.json`
        carries `config`, and `TOOL_STATUS_RAN` carries `tool status`. Splitting a name
        someone wrote is not substring matching: `aggregate` has no boundary in it and
        yields only itself, never `gate`, which is what keeps rule 5 intact.
        """
        for key in name_keys(word):
            note(key, surface, name, where)

    # -- named ------------------------------------------------------------- #
    for r in store.query(
            "SELECT DISTINCT module, path FROM files WHERE module <> ''"
            " ORDER BY module, path"):
        module = str(r["module"])
        note(module, "module", module, str(r["path"]))
        for part in module.split("."):
            note(part, "module", module, str(r["path"]))

    for table in ("classes", "structures"):
        for r in store.query(
                f"SELECT DISTINCT name, file FROM {table} WHERE name <> ''"
                " ORDER BY name, file"):
            note_words(str(r["name"]), "class", str(r["name"]), str(r["file"]))

    for r in store.query(
            "SELECT DISTINCT name, file FROM db_tables WHERE name <> ''"
            " ORDER BY name, file"):
        note(str(r["name"]), "table", str(r["name"]), str(r["file"]))
    for r in store.query("SELECT DISTINCT tbl FROM sql_ops WHERE tbl <> '' ORDER BY tbl"):
        note(str(r["tbl"]), "table", str(r["tbl"]), "read or written")

    for r in store.query(
            "SELECT DISTINCT name, module FROM entrypoints WHERE name <> ''"
            " ORDER BY name, module"):
        name = str(r["name"])
        note(name, "way in", name, str(r["module"]))
        for word in re.split(r"[^A-Za-z0-9]+", name):
            note(word, "way in", name, str(r["module"]))

    # A constant is a name a person chose for a value, and each word of it: the
    # program answers to `JTBD_OPENERS` and to `JTBD`. This surface exists because
    # `JTBD_OPENERS` was declared, read six times, and read as vocabulary the project
    # had abandoned.
    for r in store.query(
        "SELECT DISTINCT name, module FROM constants WHERE name <> ''"
        " ORDER BY name, module"
    ):
        name = str(r["name"])
        note_words(name, "constant", name, str(r["module"]))

    # A named file, and each word of its stem: `bootstrap-config.json` is named for
    # `bootstrap` and for `config` as surely as it is for the compound.
    for r in store.query(ARTEFACT_NAMES_SQL):
        stem, name = str(r["stem"]), str(r["name"])
        refs, files = int(r["refs"]), int(r["files"])
        detail = (f"{refs:,} reference{'s' if refs != 1 else ''}"
                  f" in {files:,} file{'s' if files != 1 else ''}")
        note(stem, "artefact", name, str(r["kind"]), detail)
        for word in re.split(r"[^A-Za-z0-9]+", stem):
            note(word, "artefact", name, str(r["kind"]), detail)

    # -- borne -------------------------------------------------------------- #

    for r in store.query(
        "SELECT DISTINCT name, module FROM routines WHERE name <> '' AND name NOT LIKE '<%'"
        " ORDER BY name, module"
    ):
        note_words(str(r["name"]), "routine", str(r["name"]), str(r["module"]))
    for r in store.query("SELECT DISTINCT name FROM params WHERE name <> '' ORDER BY name"):
        note_words(str(r["name"]), "param", str(r["name"]), "a parameter")
    for r in store.query("SELECT DISTINCT name FROM fields WHERE name <> '' ORDER BY name"):
        note_words(str(r["name"]), "field", str(r["name"]), "a field")

    return dict(index)


def _prose_corpus(store: Store) -> list[tuple[str, str, str]]:
    """(surface, text, where) for everything the program says in words.

    Comments and docstrings both, and kept apart from every code-shaped surface --
    rule 9 in both directions. A word spoken in a comment is not a word the program is
    named for, and this is the only band that reads prose.
    """
    out: list[tuple[str, str, str]] = []
    for r in store.query(
            "SELECT text, routine_id FROM comments WHERE text <> ''"
            " ORDER BY routine_id, line, text"):
        out.append(("comment", str(r["text"]), str(r["routine_id"])))
    for r in store.query("SELECT doc, path FROM files WHERE doc <> '' ORDER BY path"):
        out.append(("docstring", str(r["doc"]), str(r["path"])))
    for r in store.query(
        "SELECT docstring, qualname FROM routines WHERE docstring IS NOT NULL"
        " AND docstring <> '' ORDER BY qualname, docstring"
    ):
        out.append(("docstring", str(r["docstring"]), str(r["qualname"])))
    for r in store.query(
        "SELECT docstring, name FROM structures WHERE docstring IS NOT NULL"
        " AND docstring <> '' ORDER BY name, docstring"
    ):
        out.append(("docstring", str(r["docstring"]), str(r["name"])))
    return out


def measure(store: Store, docs: DocStore | None) -> Mirror:
    """Every term the documentation defines, and what the code does with it."""
    report = Mirror(had_docs=docs is not None, langs=languages.read(store))

    counts = store.query(
        "SELECT COUNT(*) refs, COUNT(DISTINCT name) names FROM artefacts"
    )[0]
    report.artefacts_seen = int(counts["refs"])
    report.artefact_names = int(counts["names"])

    if docs is None:
        return report

    rows = docs.query(DEFINED_TERMS_SQL)
    report.definitions_seen = len(rows)
    report.documents_scanned = docs.query(
        "SELECT COUNT(*) n FROM documents WHERE duplicate_of = ''"
    )[0]["n"]

    excluded: dict[str, list[str]] = defaultdict(list)
    admitted: dict[str, MirroredTerm] = {}
    seen_exclusions: set[tuple[str, str]] = set()

    for r in rows:
        term = str(r["term"]).strip()
        reason = admit(term)
        if reason is not None:
            if (reason, term.lower()) not in seen_exclusions:
                seen_exclusions.add((reason, term.lower()))
                excluded[reason].append(term)
            continue
        entry = admitted.setdefault(term.lower(), MirroredTerm(term=term))
        entry.definitions.append(Definition(
            definition=str(r["definition"]), doc=str(r["doc"]), line=int(r["line"]),
            form=str(r["form"]), heading=str(r["heading"]),
        ))

    report.excluded = {k: sorted(v, key=str.lower) for k, v in excluded.items()}

    index = _index_code(store)
    for entry in admitted.values():
        entry.sightings.extend(index.get(key_of(entry.term), []))

    # Prose is scanned only for terms nothing is named for. It is the expensive surface
    # -- 13,430 spans -- and a term already Named or Borne cannot be moved by it.
    unplaced = [e for e in admitted.values() if not e.sightings]
    if unplaced:
        patterns = [(e, _prose_pattern(e.term)) for e in unplaced]
        for surface, text, where in _prose_corpus(store):
            lowered = text.lower()
            for entry, pattern in patterns:
                if entry.term.split()[0].lower() not in lowered:
                    continue
                if pattern.search(text):
                    entry.sightings.append(
                        Sighting(surface=surface, name=entry.term, where=where)
                    )

    report.terms = sorted(admitted.values(), key=lambda t: t.term.lower())
    return report
