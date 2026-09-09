"""What every page of a map says about itself, decided once.

**The defect this closes.** The cover stated which snapshot it described and when that
source was read; the other fourteen pages said only `Generated <now>`. A reader arriving
at `07-database.md` from a link — which is how most links arrive — had the whole problem
the cover had just solved, and no way to tell whether the page in front of them described
the tree as it stands or a snapshot sealed a fortnight ago.

It was not fixed in passing because it could not be: eight renderers each built the same
header line inline and `markdown._header` was a ninth copy, so correcting it meant
correcting it nine times and hoping the tenth renderer written after that remembered.
Rule 51 — a rule kept at a call site rots as callers are added; move it to where they all
pass.

**`Generated` is not `analysed`.** A map written by `analyze` carries one instant for
both, so a single line was true twice over by accident and nothing ever made the
difference visible. `dunneflow render` pulls them apart — documents written today about
source captured two weeks ago — and the old line then read as a claim about the wrong
fortnight. Three instants, and the page states all three.

**Its own module, and that placement is load-bearing.** `markdown.py` imports every one of
the eight renderers, so a header living there and imported back by them is a cycle. This
imports nothing but the store, which is also what lets `Stamp.of` ask the graph once for
facts fourteen pages share rather than threading them through fourteen signatures.

**Missing and blank are different answers.** A map written before `analyze` recorded a
revision keeps the exact line it always had rather than being handed an invented one
(rule 30) — a header that says `Snapshot: unknown` about a map that predates the concept
is a claim, and *not recorded* is a fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ..store import Store


def stamp_text(when: datetime | None = None) -> str:
    """The instant a document was written, as a reader reads it.

    Minutes, not seconds: this is prose about when a page was made, and a second's
    precision on it would invite a comparison nobody can use. The *revision* is where
    exactness lives, and it carries its own.
    """
    return (when or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")


@dataclass(frozen=True, slots=True)
class Stamp:
    """The three instants a page of a map stands on.

    `revision` and `analysed` are `""` when the graph does not record them, which is a
    real state — every map written before those keys existed — and not the same as a map
    whose revision is unknown.
    """

    generated: str
    revision: str
    analysed: str

    @classmethod
    def of(cls, store: Store, when: datetime | None = None) -> Stamp:
        """Read once, for the whole map.

        Asked of the store rather than carried down from `analyze`, because the graph is
        where both facts already live and a second copy travelling through fifteen
        signatures is a second answer waiting to disagree with the first.
        """
        return cls(
            generated=stamp_text(when),
            revision=store.get_meta("revision") or "",
            analysed=store.get_meta("analysed_at") or "",
        )

    @property
    def dated(self) -> bool:
        """Does this map know which snapshot it describes, or when it was read?"""
        return bool(self.revision or self.analysed)


def header(program: str, title: str, stamp: Stamp) -> str:
    """The heading and the one line under it, for every page of every map.

    The line is read by someone who arrived here from a link and does not know what they
    are looking at, so it is written as a sentence rather than as a table: a table of
    three dates under a heading reads as data about the program, and this is data about
    the *document*.
    """
    if not stamp.dated:
        # The line every map had before any of this was recorded, kept exactly. A map
        # written before the keys existed is fine (see `Store.finished`'s three states);
        # what it must not do is claim a snapshot it never had.
        return f"# {program} — {title}\n\n*Generated {stamp.generated} by DunneFlow.*\n\n"

    snapshot = (f"Snapshot `{stamp.revision}`" if stamp.revision
                else "Snapshot not recorded")
    read = (f"source read {stamp.analysed}" if stamp.analysed
            else "when that source was read is not recorded")
    return (f"# {program} — {title}\n\n"
            f"*{snapshot} — {read} — these documents written "
            f"{stamp.generated}, by DunneFlow.*\n\n")
