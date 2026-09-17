"""What the comparison says about each finding.

The last surface the comparison did not reach, and the one that was blocked on a
question rather than on effort: **what makes two findings in two versions the same
finding.** A finding carried no identity at all, and 93 of Mensores' 106 are
`LOST_EDGE`, so pairing them on anything loose would have invented one -- rule 1's
defect with a colour on it. `anomalies.py` answers that now: every detector declares
what identifies its finding, and this module does nothing but pair on it.

**Two versions, and no claim about which is older.** The `base` is the version the whole
map is showing and the `compared` is the one it is held against, exactly as in
`changes.py`. The bands are named for **where a finding is**, never for what befell it
(rule 65) -- *added* and *deleted* are an interpretation the reader owns, made on the
strip that states their own assumption, and flipping it costs nothing here because
nothing here is baked in.

**What is compared, and what is deliberately not.** A finding's `count`, `severity` and
`confidence`: the three things it *claims*. Not its `title` or its `detail`, which are
renderings of exactly those -- a title embeds the count, so comparing both would report
one change twice and call it two (rule 40). Not its `blind_spot`, which is a sentence
about this tool rather than about the program: when it changes, DunneFlow changed, and
saying so here would put a mark on a finding the program did not move.

**No SQL, and no `ATTACH`.** Every other comparison in this dashboard joins two graphs on
one connection, because facts are rows. Findings are not rows: they are what thirteen
query-driven detectors *conclude*, so the only way to have the compared version's
findings is to run the detectors over the compared version's graph. That is the whole
cost of this view, and it is why the caller holds them per **graph** rather than per
pair: the findings of a graph are a property of that file. Measured on Mensores' pair --
107 findings against 106 -- the first request is **1.3 s to 4.1 s**, nearly all of it
running the detectors over a 31 MB graph this process had never opened, and the spread is
the disk rather than the work. Pairing the two ends once both are held is **0 ms**. The
pairing was never the cost; having the second version's findings at all is.

Rule 58 does not land here, and it is worth saying why rather than leaving it to be
rediscovered. Its 36x is a second read-only handle to a database *this process already
holds open*; the compared graph is not that file, and where the base **is** the served
graph the caller hands its own store in rather than opening a second one.
"""

from __future__ import annotations

from typing import Any

# The three things a finding claims about the program. Everything else it carries is
# either a rendering of these (`title`, `detail`) or a statement about DunneFlow
# (`blind_spot`), and neither is a difference between two versions of the program.
CLAIMS: tuple[str, ...] = ("count", "severity", "confidence")


def build(base: list[dict[str, Any]],
          compared: list[dict[str, Any]]) -> dict[str, Any]:
    """Pair two versions' findings on the identity each detector declared.

    Takes the rows themselves rather than a store, so the pairing can be read and tested
    without a graph on disk -- which is the half of this that carries the design rule,
    and the half that must not be able to disagree with itself.

    Every row carries the `ident` the worklist files a triage decision under, because a
    band whose rows cannot be matched to what is on screen is a count with nothing behind
    it (rule 30).
    """
    by_base = {row["ident"]: row for row in base}
    by_compared = {row["ident"]: row for row in compared}

    only_base = [row for row in base if row["ident"] not in by_compared]
    only_compared = [row for row in compared if row["ident"] not in by_base]

    moved: list[dict[str, Any]] = []
    for ident, row in by_base.items():
        other = by_compared.get(ident)
        if other is None:
            continue
        differs = [c for c in CLAIMS if row.get(c) != other.get(c)]
        if differs:
            moved.append({
                **row,
                "moved": differs,
                # Named for the side it is on, never for a point in time. `was` would be
                # the whole of rule 65 in one word: this module cannot see which version
                # is older, and a key that says otherwise is a claim it cannot defend.
                "in_compared": {c: other.get(c) for c in CLAIMS},
            })

    # A finding in both, claiming the same three things, is unchanged -- and it is left
    # to be derived rather than sent, exactly as `changes.py` leaves an unchanged routine
    # out of its bands. Sending it would be a second, longer way to say what the absence
    # of a band already says, and two answers to one question drift (rule 51).
    return {
        "counts": {
            "only_in_base": len(only_base),
            "only_in_compared": len(only_compared),
            "moved": len(moved),
            "findings_base": len(base),
            "findings_compared": len(compared),
        },
        # `identical` is a real answer and is stated as one: two versions whose findings
        # agree in every particular is what a reader gets for comparing a tree with a
        # copy of itself, and three empty bands read as a comparison that failed rather
        # than as one that succeeded and found nothing (design rule 1).
        "identical": not (only_base or only_compared or moved),
        "only_in_base": only_base,
        "only_in_compared": only_compared,
        "moved": moved,
    }
