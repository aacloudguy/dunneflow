"""Binding the words a program uses to the places its documentation defines them.

The feature was scoped as "infer what these words mean". Checking the source first
inverted it: nine of Mensores' eleven opaque terms are already defined by the project,
in a naming table and two glossary sections that DunneFlow could not see because it read
only code. So the job is **binding existing documentation to the code**, not generating
definitions -- and the terms nothing defines are the worklist, not a failure.

Four provenances, never blended. Two of them are free and are all this module produces:

* `DECLARED_CODE` -- a module docstring, parsed.
* `DECLARED_DOCS` -- a glossary heading or a definition table, parsed.

`CITED` and `INFERRED` come from the model pass, are stored separately, and are merged
in only at render time so that the free half can always be read alone.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..detectors.prose import is_ordinary
from ..docstore import DocStore
from ..schema import Provenance
from ..store import Store

WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
MIN_TERM_LENGTH = 3


@dataclass(slots=True)
class Sense:
    """One thing a document or a docstring says a term means."""

    definition: str
    provenance: Provenance
    source: str          # file
    line: int
    heading: str = ""
    form: str = ""


@dataclass(slots=True)
class Term:
    """A word this program uses as a name, and everything said about it."""

    term: str
    uses: int = 0
    where: list[str] = field(default_factory=list)   # module / class / command
    kinds: Counter[str] = field(default_factory=Counter)
    senses: list[Sense] = field(default_factory=list)

    def used_as(self) -> str:
        """Where the word is used, as counts rather than as 638 module names."""
        return ", ".join(
            f"{n:,} {kind}{'s' if n != 1 else ''}"
            for kind, n in self.kinds.most_common()
        )

    @property
    def defined(self) -> bool:
        return bool(self.senses)


@dataclass(slots=True)
class GlossaryReport:
    terms: list[Term] = field(default_factory=list)
    undefined: list[Term] = field(default_factory=list)
    definitions_seen: int = 0
    documents_seen: int = 0

    def coverage(self) -> tuple[int, int]:
        defined = sum(1 for t in self.terms if t.defined)
        return defined, len(self.terms)


def _candidate_terms(store: Store) -> dict[str, Term]:
    """Words the program uses as names, minus the ones any programmer already knows.

    Deliberately drawn from the names a person chose for a *thing* -- a package, a
    class, a command -- rather than from every identifier. A local variable is not
    vocabulary.
    """
    terms: dict[str, Term] = {}

    def note(word: str, kind: str, where: str) -> None:
        word = word.strip().strip("_")
        if len(word) < MIN_TERM_LENGTH or not word.isalpha() or is_ordinary(word):
            return
        t = terms.setdefault(word.lower(), Term(term=word))
        t.uses += 1
        t.kinds[kind] += 1
        if where not in t.where:
            t.where.append(where)

    for r in store.query("SELECT DISTINCT module FROM files WHERE module <> ''"):
        parts = str(r["module"]).split(".")
        for part in parts:
            note(part, "module", f"module {r['module']}")

    # Class names are deliberately NOT split into words. `AdmissibilityVerdict` is a
    # compound of two ordinary words and neither half is vocabulary; splitting every
    # class name produced `Pre`, `Not` and `Flight` as terms needing definitions. The
    # words a project coins appear as packages and as commands, which is where a person
    # has to name a thing rather than describe one.
    for r in store.query("SELECT DISTINCT name FROM entrypoints WHERE name <> ''"):
        for word in re.split(r"[^A-Za-z0-9]+", str(r["name"])):
            note(word, "way in", f"way in `{r['name']}`")

    for r in store.query("SELECT DISTINCT tbl FROM sql_ops WHERE tbl <> ''"):
        for word in re.split(r"[^A-Za-z0-9]+", str(r["tbl"])):
            note(word, "table", f"table {r['tbl']}")

    # A constant is the third place a person must name a thing rather than describe
    # one. `EMBEDDING_MODEL` and `MENSORES_DIRNAME` carry the program's configuration
    # vocabulary, and until constants were recorded none of it was here.
    for r in store.query("SELECT DISTINCT name FROM constants WHERE name <> ''"):
        for word in re.split(r"[^A-Za-z0-9]+", str(r["name"])):
            note(word, "constant", f"constant `{r['name']}`")

    return terms


def bind(store: Store, docs: DocStore | None) -> GlossaryReport:
    """Every candidate term, with whatever the program itself says it means."""
    terms = _candidate_terms(store)
    report = GlossaryReport()

    # DECLARED_CODE: a package's own docstring is the only place most programs say
    # what their words mean. `disceptator/__init__.py` opens "Interview engine".
    for r in store.query("SELECT path, module, doc FROM files WHERE doc <> ''"):
        module = str(r["module"])
        leaf = module.rsplit(".", 1)[-1].lower()
        target = terms.get(leaf)
        if target is None:
            continue
        doc = str(r["doc"]).strip()
        first = doc.split("\n\n", 1)[0].strip()
        target.senses.append(Sense(
            definition=first, provenance=Provenance.DECLARED_CODE,
            source=str(r["path"]), line=1, form="module docstring",
        ))

    if docs is not None:
        by_term: dict[str, list[Sense]] = defaultdict(list)
        rows = docs.query(
            "SELECT d.term, d.definition, d.line, d.form, d.heading, d.doc"
            "  FROM definitions d JOIN documents dc ON dc.path = d.doc"
            " WHERE dc.duplicate_of = ''"
        )
        report.definitions_seen = len(rows)
        for r in rows:
            by_term[str(r["term"]).strip().lower()].append(Sense(
                definition=str(r["definition"]), provenance=Provenance.DECLARED_DOCS,
                source=str(r["doc"]), line=int(r["line"]),
                heading=str(r["heading"]), form=str(r["form"]),
            ))
        for key, senses in by_term.items():
            target = terms.get(key)
            if target is not None:
                target.senses.extend(senses)
        report.documents_seen = docs.query(
            "SELECT COUNT(*) n FROM documents WHERE duplicate_of = ''"
        )[0]["n"]

    ordered = sorted(terms.values(), key=lambda t: (-t.uses, t.term.lower()))
    report.terms = ordered
    report.undefined = [t for t in ordered if not t.defined]
    return report
