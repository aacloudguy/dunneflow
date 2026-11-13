"""The naming standard as **stated**: rules quoted out of the project's own documents.

The counterpart to `naming.py`, whose first line says it is *the Form lane* and means it --
everything there is measured over `graph.db` and nothing there was written by a person.
Everything here was. A stated rule is a **quotation**, and it proves itself the way a
quotation does: with a document, a line, and the heading it sat under.

**Two lanes travel in this one list, and they are not two shapes.** `lane` is `FORM` where
a rule names how a name is *spelled* and `VOCABULARY` where it names what a name may be
drawn from or must mean. Both come out of `doc_rules`, both are quoted whole, and the only
thing that differs is what a reader can do with one -- which is what `checkable` records.
Splitting them into two queries would be two readings of one table, and the day the
extractor mints a third lane only one of them would learn about it.

**This module exists because there are three readers.** `render/naming.py` wrote the query,
the dashboard needs the same rows, and the tests need to be able to say the two agree. A
query kept beside one caller is right until the second one arrives (rule 51) -- and the
`checkable` *sentence* below is the sharper half of that, because two surfaces spelling one
fact two ways is how a reader learns that the tool does not know which it means.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..docstore import DocStore


@dataclass(slots=True)
class StatedRule:
    """One naming rule a document states.

    `scope` and `pattern` are the two halves `checkable` is computed from -- the class of
    identifier and the spelling it must take -- and they are carried rather than dropped
    because a reader deciding whether to trust a rule wants to see the pair that made it
    checkable, not the verdict alone.
    """

    doc: str
    text: str
    line: int
    lane: str
    heading: str
    checkable: bool
    scope: str
    pattern: str


# **A duplicate document is excluded, and that is a filter with a reason.** `documents`
# marks a byte-identical copy with the path it duplicates, and a naming rule quoted twice
# out of two copies of one file is one rule that would be counted as two. Design rule 1
# says no filter is silent: `_scanned_section` prints how many copies were folded, and the
# dashboard's stated page says the same thing in its own words.
_SQL = (
    "SELECT r.doc, r.text, r.line, r.lane, r.heading, r.checkable, r.scope, r.pattern"
    "  FROM doc_rules r JOIN documents d ON d.path = r.doc"
    " WHERE d.duplicate_of = ''"
    " ORDER BY r.lane, r.doc, r.line"
)


def stated_rules(docs: DocStore | None) -> list[StatedRule]:
    """Every naming rule this program's documents state, in lane then document order.

    `None` is the ordinary case rather than an error (design rule 11): a program analysed
    with `--no-docs` states nothing, and that is a fact about the analysis rather than
    about the program. The empty list it returns is told apart from *"documents were read
    and none of them states a rule"* by the caller, which knows whether a store was opened.
    """
    if docs is None:
        return []
    return [
        StatedRule(
            doc=str(r["doc"]), text=str(r["text"]), line=int(r["line"]),
            lane=str(r["lane"]), heading=str(r["heading"]),
            checkable=bool(r["checkable"]),
            scope=str(r["scope"] or ""), pattern=str(r["pattern"] or ""),
        )
        for r in docs.query(_SQL)
    ]


def checkable_sentence(rule: StatedRule) -> str:
    """What `checkable` actually means, said once and without over-claiming.

    **This sentence had never been printed.** No rule in any corpus carried
    `checkable = 1` until tables were read, so its true branch was written, shipped and
    never seen. The first thing it said, on its first outing, was *"Mechanically
    checkable."* beside **"Type attributes: colon separator"** -- for which DunneFlow has
    no population and no check, and will not have one until a standards directory can be
    imported and compared.

    The field is right and the sentence was wrong. `checkable` means the rule *names both
    a class of identifier and a spelling*, which is what makes a check writable; it has
    never meant that one is run.

    **And then one was**, on 2026-09-06: `resolve/conformance.py` measures a checkable rule
    against the population its own document declares -- 4 of Comitia's 12 are checked, and
    the rest report no population rather than passing quietly. So the sentence changed again
    on 2026-09-08, because *"DunneFlow does not yet run one"* had gone from careful to false
    while the surface that prints it went on printing it. A sentence about a capability has
    to be read against the capability, which is the same lesson the glossary page's citation
    note paid for on the same day.

    It lives here rather than beside either surface because there are now three of them --
    the Markdown report, the dashboard's stated page, and the tests that hold them to each
    other. A claim spelled two ways is two claims (rule 51).
    """
    if rule.checkable:
        return ("Names a class of identifier and a spelling, so a check can be written "
                "for it. Whether one was run is the checked lane's answer: it measures "
                "the rules whose population this map holds, and says why not for the rest.")
    return "No query can decide this one."
