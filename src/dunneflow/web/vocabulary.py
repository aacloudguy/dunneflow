"""The program's own words, as the dashboard serves them.

Three lanes, and design rule 13 says they do not prove themselves the same way. A
**quoted** definition, and a **stated** naming rule, prove themselves with a file and a
line the reader can open and read in context; a **measured** convention proves itself with
the query that counted it, reproducible via `dunneflow query`. Neither is worth anything
without that route back, so nothing here crosses the wire without it.

It was two lanes until the stated one was served. `11-naming.md` had carried it since the
scanner was written and the dashboard had never shown a line of it -- which is why the two
naming pages are titled differently and are two pages: *derived* is a load-bearing word
about a page that counts, and putting a rule somebody wrote on it would have made that word
false of half its contents.

`resolve/naming.py` and `resolve/glossary.py` do the work and are unchanged; this is
exposure. Both were built, tested and reachable only from the command line -- the shell's
glossary and naming pages have said "not computed yet" since they were written, honestly,
because no endpoint ever served them.

**Computed once, at start.** Measured on Mensores: the naming pass is 0.4 s and the
glossary pass 2.1 s, the latter because it reads a 176 MB document store. Two seconds is
tolerable on a page a reader deliberately opened and intolerable inside `/api/threads`,
which is asked on **every selection** -- the reading loop would stall on the first click of
every session. So both are paid for at boot, once, where the server is already building a
payload and a cover and says so as it goes.
"""

from __future__ import annotations

from typing import Any

from ..docstore import DocStore
from ..resolve import glossary as glossary_resolve
from ..resolve import languages
from ..resolve import naming as naming_resolve
from ..resolve.conformance import (
    CHECKED,
    NO_POPULATION,
    NOT_CHECKABLE,
    check_stated,
)
from ..resolve.stated import checkable_sentence, stated_rules
from ..store import Store
from . import threads


def measure_naming(store: Store, private_prefix: bool = False) -> dict[str, Any]:
    """The Form lane: what this program does about names, counted.

    Every convention travels with the query that produced it. Rule 13 is not decorative
    here -- three of the first twenty-seven conventions ever measured returned something
    other than the number printed beside them, and a query that disagrees with its claim is
    worse than no query, because it invites a reader to check and then misleads them.
    """
    m = naming_resolve.measure(store, private_prefix)
    return {
        # Whether a leading underscore was read as a privacy mark (the reader's Setting), so
        # the page can say which reading it is showing rather than leave two screens to
        # disagree silently.
        "private_prefix": private_prefix,
        "conventions": [
            {
                "kind": c.kind,
                "claim": c.claim,
                "population": c.population,
                # Which language this convention is about, `""` where the question had no
                # language axis: a map holding one language, or one of the two kinds that
                # are deliberately not split. Two spellings because they answer two
                # questions: `lang` is the stored key, which is what a page groups or
                # filters on, and `langName` is how the language is spelled in a sentence.
                # The page composes neither -- `languages.display` is the one place that
                # decides, because a map may hold a language whose reader is no longer
                # installed and inventing a capitalisation is a guess (rule 51).
                "lang": c.lang,
                "langName": languages.display(c.lang) if c.lang else "",
                "total": c.total,
                "holds": c.holds,
                "rating": c.rating(),
                "prevalence": round(c.prevalence, 4),
                # The population as a glob, so the inspector can ask whether a given name
                # is in it. Empty for a case convention, which is a property of every name
                # in its population rather than a subset of it -- a real absence.
                "glob": c.glob,
                # The same glob as a **subject**, minted here rather than in the page that
                # draws it. The convention row's *"Show all N in the graph"* button had
                # assembled `{"type": "cohort", "kind": "convention", ...}` in JavaScript
                # since it was written -- a second place deciding what a subject is, which
                # is exactly what the guard on `curiosities.py` refuses one module over and
                # could not see here. It went unnoticed while a subject was three fields
                # anybody could spell; it stopped being harmless when `noun` was added and
                # the hand-built copy silently lacked it.
                #
                # `None` for a case convention, which has no glob and therefore no
                # population to open (design rule 1: the absence is the answer, not a
                # subject naming everything).
                "subject": (threads.cohort_subject("convention", c.glob, c.glob)
                            if c.glob else None),
                "sql": c.sql,
                "note": c.note,
                # **The exceptions are the product.** The three non-exception `*Error`
                # classes on Mensores are frozen dataclasses carrying error information
                # that cannot be raised -- a real finding, verified against source, and the
                # most interesting thing the whole lane produced. Sending the claim without
                # them would be sending the boring half.
                "exceptions": [{"name": e.name, "where": e.where} for e in c.exceptions],
            }
            for c in m.conventions
        ],
        # A population with no dominant convention is a fact about the program, not a
        # blank. Design rule 1: what was looked at and found nothing is stated.
        "gaps": [{"population": g.population, "lang": g.lang,
                  "langName": languages.display(g.lang) if g.lang else "",
                  "total": g.total,
                  "spread": [[k, n] for k, n in g.spread]} for g in m.gaps],
        "thresholds": m.thresholds,
        # Said, never left out (design rule 1): a language whose privacy is not measured.
        "notMeasured": [{"lang": n.lang, "langName": languages.display(n.lang),
                         "what": n.what, "reason": n.reason} for n in m.not_measured],
    }


def stated_naming(docs: DocStore | None) -> dict[str, Any]:
    """The **stated** lane: the naming rules this project's documents actually contain.

    `measure_naming` above counts what the code does. This quotes what somebody wrote, and
    the two are never blended -- a derived convention holding 100% of the time and a rule a
    person set down are different claims, which is why they are two pages rather than two
    sections of one.

    **Nothing here is compared against anything**, and the page says so in its own first
    line. `checkable` records only that a rule names both a class of identifier and a
    spelling, so a check *could* be written; DunneFlow does not run one, and will not until
    a standards directory can be imported.

    **Three absences, and they are three different answers** (design rule 21). No store at
    all means the analysis never read documentation; a store with no rules means documents
    were read and none of them states a naming rule; and a rule count of zero over a
    document count of zero means the scan found nothing to read. Flattening them into one
    empty list would turn *"we did not look"* into *"there is nothing there"*, which is the
    claim this tool exists not to make. So the counts travel with the rules, whether or not
    there are any.

    Unbounded, like every list that is not a diagram (rule 8). The largest corpus measured
    here yields twelve; a stale self-analysis in `output/` yields 136, and the page renders
    all of them rather than the first few, because a stated rule nobody is shown is a rule
    that might as well not have been read.
    """
    rules = stated_rules(docs)
    counts = docs.counts() if docs is not None else {}
    return {
        # `read` is the flag that separates the first absence from the second two: it is
        # about the *analysis*, not about the corpus, and no count can stand in for it --
        # a program whose documentation is genuinely empty and one analysed with
        # `--no-docs` both report zero documents.
        "read": docs is not None,
        "rules": [
            {
                "doc": r.doc,
                "line": r.line,
                "lane": r.lane,
                "text": r.text,
                "heading": r.heading,
                "checkable": r.checkable,
                # The pair `checkable` is computed from, carried rather than summarised.
                # They have been in the schema since the scanner was written and read by
                # nothing; a reader deciding whether to trust a rule wants the halves that
                # made it checkable, not the verdict on its own.
                "scope": r.scope,
                "pattern": r.pattern,
                # One sentence, from the one place it lives. The Markdown report prints
                # the same string (rule 51) -- two surfaces spelling one fact two ways is
                # how a reader learns the tool does not know which it means.
                "note": checkable_sentence(r),
            }
            for r in rules
        ],
        # What was looked at, so an empty list can say why it is empty rather than merely
        # being empty. `duplicates` is the one filter in the query and design rule 1 says
        # it is never silent: byte-identical copies are folded, and the page states it.
        "documents_seen": int(counts.get("documents", 0)),
        "duplicates": int(counts.get("duplicates", 0)),
    }


def checked_naming(store: Store, docs: DocStore | None,
                   standards: DocStore | None, private_prefix: bool = False) -> dict[str, Any]:
    """The **comparison**: every stated rule, measured over the population it governs.

    A third page rather than a column on either of the two above, and that is Tom's
    separation kept rather than bent. `measure_naming` counts what the code does and quotes
    nobody; `stated_naming` quotes what somebody wrote and counts nothing; neither may show
    a number beside a quotation, because a derived convention holding 100% of the time and
    a rule a person set down are different claims. This page is *explicitly* the comparison
    and says so, which is the only way to put the two together honestly.

    **Three verdicts travel, never a boolean.** A rule that holds, a rule with no population
    in this map, and a rule whose spelling this tool cannot test are three facts, and the
    page must be unable to render any two of them alike -- otherwise *"we could not check"*
    reads as *"it passes"*, which is the claim this tool exists not to make.

    **`standards` may be `None` and that is the ordinary case** (design rule 11): no
    `--standards` directory was given. It is a different absence from a directory that was
    given and states no rule, so `imported` travels beside the rules rather than being
    inferred from an empty list.
    """
    checks = check_stated(store, docs, standards, private_prefix)
    counted = [c for c in checks if c.verdict == CHECKED]
    return {
        "private_prefix": private_prefix,
        # About the *analysis*, never the corpus -- the same distinction `stated_naming`'s
        # `read` draws, one store over. No count can stand in for either.
        "read": docs is not None,
        "imported": standards is not None,
        "checks": [
            {
                "doc": c.rule.doc,
                "line": c.rule.line,
                "text": c.rule.text,
                "heading": c.rule.heading,
                "scope": c.rule.scope,
                "pattern": c.rule.pattern,
                "source": c.source,
                "verdict": c.verdict,
                "reason": c.reason,
                # A rule measured once per language is one row per language, so the page
                # needs to tell them apart -- and `blindSpot` is what keeps the second row
                # a measurement rather than an accusation: a rule whose document names no
                # paths was measured against this language because the map holds it, not
                # because the rule claims it. `langName` is the prose spelling; see
                # `measure_naming` for why the page is never the one to compose it.
                "lang": c.lang,
                "langName": languages.display(c.lang) if c.lang else "",
                "blindSpot": c.blind_spot,
                "population": c.population,
                "scopedBy": c.scoped_by,
                "total": c.total,
                "holds": c.holds,
                "prevalence": round(c.prevalence, 4),
                "sql": c.sql,
                # Every exception, never a sample. The exceptions are the product: a rule
                # holding in 1,127 of 1,179 cases is mildly interesting, and the 52 classes
                # that break it are the finding (rule 8 bounds a diagram, not a list).
                "exceptions": [{"name": e.name, "where": e.where} for e in c.exceptions],
            }
            for c in checks
        ],
        # What the page needs to say what it is looking at before a reader counts rows.
        "summary": {
            "rules": len(checks),
            "checked": len(counted),
            "noPopulation": sum(1 for c in checks if c.verdict == NO_POPULATION),
            "notCheckable": sum(1 for c in checks if c.verdict == NOT_CHECKABLE),
            "exceptions": sum(len(c.exceptions) for c in counted),
        },
    }


def bind_glossary(store: Store, docs: DocStore | None) -> dict[str, Any]:
    """The Vocabulary lane: the program's words and who says what they mean.

    Documentation may be absent, and that is the normal case rather than the exception
    (design rule 11) -- five abandoned games taught that. A missing `docs.db` costs the
    DECLARED_DOCS tier and nothing else: the terms are still mined from the code, and the
    docstring definitions still stand.
    """
    report = glossary_resolve.bind(store, docs)
    defined, total = report.coverage()
    return {
        "terms": [
            {
                "term": t.term,
                "uses": t.uses,
                "used_as": t.used_as(),
                "defined": t.defined,
                "senses": [
                    {
                        "definition": s.definition,
                        # Never blended, never blurred (rule 6, and the glossary's own
                        # four tiers). A quotation from a docstring and a model's guess
                        # are different claims and the reader must be able to tell.
                        "provenance": str(s.provenance),
                        "source": s.source,
                        "line": s.line,
                        "heading": s.heading,
                        "form": s.form,
                    }
                    for s in t.senses
                ],
            }
            for t in report.terms
        ],
        "undefined": [{"term": t.term, "uses": t.uses, "used_as": t.used_as()}
                      for t in report.undefined],
        # Sent, never withheld. The page draws them in their own band with the reason, and
        # a reader can promote one back into the worklist -- `MENSORES_MAX_LEN` holds the
        # program's own word beside a modifier and a unit, and only a person can say which
        # is which. Promotion is the reader's, so it lives in their settings and not here
        # (design rule 17); this end sends the same list to everybody.
        "set_aside": [{"term": t.term, "uses": t.uses, "used_as": t.used_as()}
                      for t in report.set_aside],
        "definitions_seen": report.definitions_seen,
        "documents_seen": report.documents_seen,
        "coverage": [defined, total],
    }


# --------------------------------------------------------------------------- #
# Matching one name against the vocabulary
#
# What turns the two lanes into *threads*: given a routine, which conventions is
# it an instance of, and which of the program's own words does its name use.
# --------------------------------------------------------------------------- #

def _glob_matches(glob: str, name: str) -> bool:
    """SQLite's `GLOB`, for the two shapes this actually mints.

    Deliberately not a general glob implementation. `_affix_conventions` produces exactly
    `prefix<sep>*` and `*<sep>suffix` and nothing else, so handling those two exactly is
    both complete and checkable -- and a general matcher would be a second, subtly
    different reading of a pattern the store already interprets one way.
    """
    if not glob or "*" not in glob:
        return False
    if glob.startswith("*"):
        return name.endswith(glob[1:])
    if glob.endswith("*"):
        return name.startswith(glob[:-1])
    return False


def conventions_for(naming: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Every measured convention this name is an instance of.

    Only the affix conventions can answer, because only they name a *subset*: "routines are
    named in snake_case" is true of this routine and of four and a half thousand others,
    which is a fact about the program rather than a thread worth pulling.
    """
    out = []
    for c in naming.get("conventions", []):
        if not c.get("glob"):
            continue
        if _glob_matches(c["glob"], name):
            out.append(c)
    # The strongest claim first, then the biggest population: an `A` over 372 cases is a
    # better doorway than a `D` over 13, and the reader should not have to sort by eye.
    out.sort(key=lambda c: (c["rating"], -c["total"]))
    return out


def terms_in(glossary: dict[str, Any], name: str, module: str) -> list[dict[str, Any]]:
    """The program's own words that this routine's name uses.

    Matched on whole segments, never on substrings. Rule 5 in its most literal form: a
    term matched anywhere inside a name matches half the program -- `mensor` would claim
    every `dimensions`, and `groma` every `programatic` -- and rule 18 caught the same
    defect in the walk's test rule (`DiscoveryRules.is_test` now, `walk.is_test_path`
    then), where `test_` as a substring dropped `_test_stage.py` out of the map
    entirely. A word must sit at a segment boundary to count.
    """
    segs = {s.lower() for s in name.replace("-", "_").split("_") if s}
    segs |= {s.lower() for s in module.split(".") if s}
    if not segs:
        return []
    out = [t for t in glossary.get("terms", []) if t["term"].lower() in segs]
    # A defined word first: it is the one that can show the reader a definition with a file
    # and a line, which is the whole point of the tier (design rule 13). Then by how much
    # of the program uses it, because a word used twice is a coincidence and a word used
    # six hundred times is the vocabulary.
    out.sort(key=lambda t: (not t["defined"], -t["uses"]))
    return out
