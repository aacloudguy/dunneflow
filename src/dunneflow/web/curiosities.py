"""Curiosities: what came out furthest from the middle, for the whole program.

Design rule 15's fourth piece of furniture, and the last one to be built. The trail,
the threads and the shelf were the other three; this is the doorway panel:

> **Curiosities.** What came out furthest from the middle -- 264 comments on one
> routine, four closures deep, a table written twice as often as it is read. Not
> problems. Doorways.

`threads.py` already asks four of these questions of the package a reader is standing
on. This asks twelve of them of the whole program, which is a different panel: a thread
is *beside you*, a curiosity is *somewhere in here and worth the walk*.

Three disciplines, and the first is the one everything else follows from.

* **A curiosity is a measured extremum with its middle stated.** Every program has a
  most-commented routine, so a maximum on its own is a claim nobody can weigh. 1,126
  comments against a middle of 3 is a discovery; 3 levels of nesting against a middle
  of 2 is not, and this panel has to be able to say the second as plainly as the
  first. That is rule 14's lesson -- at enough measures something always comes out
  furthest -- in the one place in this product that goes looking for extremes on
  purpose. So every card carries the value, the median, the size of the population
  and the ratio between the first two, and the panel is **ordered by that ratio**.

* **A curiosity is a measurement, never a judgement.** A long routine, a wide
  parameter list and a lopsided table are all worth a look and none of them is a
  finding. `anomalies.py` is where a claim about what is *wrong* lives, and every one
  of its findings states a blind spot because it is making one. These make none, and
  must not read as though they did: there is no severity here, no colour that says
  broken, and nothing that implies the number ought to be smaller.

* **Every number comes out of the one statement that found it.** Design rule 13
  taken literally -- the query a card offers is not a query *about* the number, it is
  the query that returned it, and it runs verbatim through `dunneflow query`. Value,
  median, ties and population all come from one scan, so they cannot disagree.

**The list is fixed and complete.** Twelve measures, all of them, every time -- so
nothing here is bounded and rule 8 never arises. A family with nothing to measure (a
program that runs no SQL has no lopsided table) is *stated* with the rest, because
eleven cards and twelve cards are different claims and a reader has no way to tell a
missing measure from an absent one. Design rule 1.

**Which member is named when several tie is arbitrary but stable** -- the extremum is
broken on the grouping key, which for a routine is its id. That is deliberate: the
alternative is joining names into the scan to sort on them, which is what cost the
call-argument family 7.47 s against 54 ms (see `queries.py`). The card says how many
tie, so the one named is an example rather than a claim of uniqueness.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..store import Store
from . import queries, threads


@dataclass(frozen=True)
class Family:
    """One measure, its statement, and the prose that reports it.

    The prose lives beside the SQL rather than in the client for the same reason
    `threads.py` composes its `why` here: a sentence assembled from a number is prose
    the moment something prints it (rule 44's companion), and prose belongs where the
    number's meaning is known. The client lays it out; it does not word it.
    """

    key: str
    sql: str
    #: `{value}` is already formatted with separators. `one` is used when the value is
    #: exactly 1 -- rare, and real on a small program, and "1 comments" is the kind of
    #: thing that only ever gets noticed by the reader.
    head: str
    head_one: str
    #: Says what the middle is *of*, because the population is not "everything". Only
    #: routines that carry a comment have a comment count, so the middle is the middle
    #: of those and the sentence must say so or the number is a different claim.
    middle: str
    #: Appended only when something ties. `{others}` excludes the one named.
    tie: str
    #: The same sentence when exactly one other ties. `head_one`'s reason, one field
    #: down, and it was missed: `_card` pluralises the *noun* -- "1 other" / "3 others" --
    #: and every family's verb was written plural, so all ten cards said "1 other carry as
    #: many". `viewShape` records the same care one pane over ("1 decisions is the kind of
    #: thing only the reader ever notices, and this pane says five of them in a row").
    tie_one: str
    #: What the `whence` column means. Empty where the column is a phrase already.
    whence_label: str
    #: Which entry of `SUBJECTS` builds this family's subject.
    subject: str
    #: Whether `value` counts the very things following this card selects.
    #:
    #: True for a cohort that is measured by its own size, and it is a claim with teeth:
    #: a guard resolves the cohort and demands the two agree. The governance card said
    #: "121 routines carry one governance id" and opened 112, because an annotation's
    #: owner is a routine *or a structure* while the cohort query has always been scoped
    #: to routines. A wrong noun and a number a reader can catch out by clicking -- rule
    #: 32, and the only reason to write this down rather than fix the one query is that
    #: the next cohort family will make the same mistake silently.
    counts_its_cohort: bool = False


# What following a curiosity selects, routed from a table (design rule 16) so a family
# naming a kind nobody wrote a builder for is a **named error** rather than a card that
# renders, highlights, and goes nowhere. That is the exact defect this panel's own click
# handler used to have -- it switched on a `tag` string and fell through to table mode --
# and rule 30 has now been paid for often enough.
#
# Minted through `threads.py` and never here: there is one place in this product that
# says what a subject looks like, and the guard that checks every minted kind has a
# handler in the shell reads that module.
SUBJECTS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "node": lambda r: threads.node_subject(str(r["node"])),
    # A table is not a node and neither is a governance id, so following one selects the
    # code that touches or carries it. Both kinds are already resolved by
    # `threads.cohort()`; nothing new had to be taught to follow these.
    "table": lambda r: threads.cohort_subject("table", str(r["name"]), str(r["name"])),
    "governance": lambda r: threads.cohort_subject(
        "governance", str(r["name"]), str(r["name"])),
    # **`looped_table` and not `table`.** The card counts the loops over a table and the
    # cohort must open the routines that *loop* over it -- `table` would open every routine
    # that touches it at all, which is a figure counting one population and a destination
    # opening another (rule 32, and the reason the thread kind exists next door).
    "looped_table": lambda r: threads.cohort_subject(
        "looped_table", str(r["name"]), str(r["name"])),
}


# The twelve, in a fixed declaration order that is **not** the order they are shown in --
# the panel sorts by distance from the middle. Declared order still matters: it is what
# a reader of this file sees, and it is the tiebreak when two families are equally far
# out.
FAMILIES: tuple[Family, ...] = (
    Family(
        key="comments", sql=queries.CURIO_COMMENTS,
        head="{value} comments on one routine",
        head_one="1 comment on one routine",
        middle="the middle routine that carries any carries {middle}, "
               "of {population} that do",
        tie="{others} carry as many",
        tie_one="{others} carries as many",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="callers", sql=queries.CURIO_CALLERS,
        head="{value} callers of one routine",
        head_one="1 caller of one routine",
        middle="the middle called routine has {middle}, "
               "of {population} that are called at all",
        tie="{others} are called from as many places",
        tie_one="{others} is called from as many places",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="lines", sql=queries.CURIO_LINES,
        head="{value} lines in one routine",
        head_one="1 line in one routine",
        middle="the middle routine is {middle} lines, of {population}",
        tie="{others} are as long",
        tie_one="{others} is as long",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="params", sql=queries.CURIO_PARAMS,
        head="{value} parameters on one routine",
        head_one="1 parameter on one routine",
        middle="the middle routine that takes any takes {middle}, "
               "of {population} that do",
        tie="{others} take as many",
        tie_one="{others} takes as many",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="depth", sql=queries.CURIO_DEPTH,
        head="{value} levels of nesting in one closure",
        head_one="1 level of nesting in one closure",
        middle="the middle closure is {middle} deep, of {population}",
        tie="{others} are nested as deep",
        tie_one="{others} is nested as deep",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="boundaries", sql=queries.CURIO_BOUNDARIES,
        head="{value} boundaries reached from one routine",
        head_one="1 boundary reached from one routine",
        middle="the middle routine that reaches any reaches {middle}, "
               "of {population} that do",
        tie="{others} reach as many",
        tie_one="{others} reaches as many",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="argument", sql=queries.CURIO_ARGUMENT,
        head="{value} characters in one call argument",
        head_one="1 character in one call argument",
        middle="the middle argument is {middle} characters, of {population}",
        tie="{others} are as long",
        tie_one="{others} is as long",
        whence_label="written at", subject="node",
    ),
    Family(
        key="constant", sql=queries.CURIO_CONSTANT,
        head="{value} characters in one constant's value",
        head_one="1 character in one constant's value",
        middle="the middle constant is {middle} characters, of {population}",
        tie="{others} are as long",
        tie_one="{others} is as long",
        whence_label="declared at", subject="node",
    ),
    Family(
        key="table", sql=queries.CURIO_TABLE,
        head="{value}× out of balance: one table's reads against its writes",
        head_one="1× out of balance: one table's reads against its writes",
        middle="the middle table is {middle}× out, "
               "of {population} both read and written",
        tie="{others} are as far out",
        tie_one="{others} is as far out",
        whence_label="", subject="table",
    ),
    Family(
        key="governance", sql=queries.CURIO_GOVERNANCE,
        head="{value} routines carry one governance id",
        head_one="1 routine carries one governance id",
        middle="the middle id is carried by {middle}, of {population}",
        tie="{others} are carried by as many",
        tie_one="{others} is carried by as many",
        whence_label="cited as a", subject="governance", counts_its_cohort=True,
    ),
    # ── ALGORITHMS chunk 5 ────────────────────────────────────────────────────────
    Family(
        key="looped_table", sql=queries.CURIO_LOOPED_TABLE,
        head="{value} loops over one table",
        head_one="1 loop over one table",
        # The middle is over the tables something loops over, **not** over every table the
        # program has -- 12 and not 65. Said in the sentence rather than left to be assumed,
        # because the two answer different questions and only one of them is this card's
        # (rule 24).
        middle="the middle table that is looped over at all carries {middle}, "
               "of {population} that are",
        tie="{others} carry as many",
        tie_one="{others} carries as many",
        whence_label="first looped over at", subject="looped_table",
    ),
    Family(
        key="loop_places", sql=queries.CURIO_LOOP_PLACES,
        head="{value} places one loop reaches in a single pass",
        head_one="1 place one loop reaches in a single pass",
        middle="the middle loop that reaches anything reaches {middle}, "
               "of {population} that do",
        tie="{others} reach as many",
        tie_one="{others} reaches as many",
        whence_label="written at", subject="node",
    ),
)


def _num(v: float) -> str:
    """A number as it should be read.

    Ratios are real and counts are not, and printing `9.0 reads` or `1,126.0 comments`
    is the same defect in both directions. An integral float is an integer here.
    """
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}"
    return f"{int(v):,}"


def _measure(store: Store, fam: Family) -> dict[str, Any] | None:
    rows = store.query(fam.sql, {})
    return dict(rows[0]) if rows else None


def _card(fam: Family, row: dict[str, Any]) -> dict[str, Any] | None:
    """One card, or `None` when the row cannot honestly be turned into one.

    A card whose subject is empty is a card that goes nowhere, which is rule 30 and is
    worse than an absent card: it looks like a doorway and is a wall. Refusing it here
    and counting it as silent is the same choice `anomalies.py` makes about a finding
    it cannot construct.
    """
    build = SUBJECTS.get(fam.subject)
    if build is None:
        raise KeyError(
            f"curiosity family {fam.key!r} names subject kind {fam.subject!r}, "
            f"which nothing builds; known kinds are {sorted(SUBJECTS)}")

    value, middle = row["value"], row["middle"]
    if value is None or middle is None:
        return None
    ties, population = int(row["ties"] or 1), int(row["population"] or 0)

    if fam.subject == "node" and not str(row.get("node") or ""):
        return None
    subject = build(row)

    # A middle of zero is not a ratio, and a large number divided by nothing is not
    # "infinitely interesting" -- it is a question the arithmetic cannot answer. Said
    # rather than substituted for (rule 49): a plausible value here would hide exactly
    # the case the reader most needs told about. It sorts first, because a value with
    # no middle beneath it is as far from the middle as anything can be.
    ratio: float | None = (value / middle) if middle else None
    ratio_text = f"{_num(ratio)}× the middle" if ratio is not None \
        else "the middle is zero, so there is nothing to divide by"

    head = fam.head_one if value == 1 else fam.head.format(value=_num(value))
    others = ties - 1
    template = fam.tie_one if others == 1 else fam.tie
    tie = template.format(others=f"{others:,} other" + ("" if others == 1 else "s")) \
        if others > 0 else ""

    return {
        "key": fam.key,
        "head": head,
        # `<module>` is a real node -- the synthetic module scope that owns everything
        # no function does (rule 18) -- and on its own the name says nothing, so
        # `threads.label_of` shows it as the module it is. One renderer, both panels.
        "what": threads.label_of(row),
        "whenceLabel": fam.whence_label,
        "whence": str(row.get("whence") or ""),
        "middle": fam.middle.format(middle=_num(middle),
                                    population=f"{population:,}"),
        "tie": tie,
        "value": value,
        "middleValue": middle,
        "ties": ties,
        "population": population,
        "ratio": ratio,
        "ratioText": ratio_text,
        "subject": subject,
        "sql": fam.sql.strip(),
    }


def for_program(store: Store) -> dict[str, Any]:
    """Every measure, ranked by how far its extremum is from its middle.

    Answered whole. There is no bound and no threshold: a family that comes out barely
    above its middle is *the useful answer* for that measure, and dropping it would be
    a filter the reader cannot see (design rule 1) dressed up as tidiness.
    """
    cards: list[dict[str, Any]] = []
    silent: list[str] = []

    for fam in FAMILIES:
        row = _measure(store, fam)
        card = _card(fam, row) if row else None
        if card is None:
            silent.append(fam.key)
        else:
            cards.append(card)

    # Furthest from the middle first, and a family with no middle to divide by is as
    # far out as it is possible to be. The declaration order breaks a tie, so two
    # equally strange measures do not swap places between visits -- the same reason
    # `threads.KIND_ORDER` is fixed at the server.
    order = {fam.key: i for i, fam in enumerate(FAMILIES)}
    cards.sort(key=lambda c: (c["ratio"] is not None,
                              -(c["ratio"] or 0.0),
                              order[c["key"]]))

    return {
        "found": True,
        "curiosities": cards,
        "families": len(FAMILIES),
        # Named, not just counted. "one measure had nothing to report" is a fact a
        # reader can act on only if they know *which* -- a program with no SQL and a
        # program whose tables are perfectly balanced are different programs.
        "silent": silent,
    }
