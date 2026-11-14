"""Document mode: the map's own prose, built from the store rather than from markdown.

`render/markdown.py` writes the same material to sixteen files, and this does **not** reuse
them. The reason is the one thing document mode exists to do: clicking a routine in the
text must select that routine in the graph, and a markdown file has already thrown away
the identity needed to do it. Linking rendered prose back to nodes would mean matching
names against the store -- and rule 5 says exactly how that ends, with 4,734 routines of
which a great many are called `main`, `run` or `_state`. Every one would light up every
other.

So each row carries the node id that produced it, selected in the same query. Selection is
exact by construction rather than by resemblance, which is the difference between a link
and a guess.

**Table-driven, deliberately** (design rule 16). A document is a `Document` in `DOCUMENTS`,
a section is a `Section` with its SQL, and adding one is an entry rather than a branch.
Nothing here interprets a row: the SQL says what to ask, this says how it is grouped and
which column is the identity, and the client says how it looks.

The id scheme is the graph's, not a second one. `bnd:KIND:target`, `art:name`,
`const:module.name`, and the store's own hash for a routine or a structure -- because a
document that minted its own ids would link to nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..store import Store
from . import queries


@dataclass(frozen=True)
class Column:
    """One column of a section's table.

    `kind` is a hint about presentation, never about meaning: `code` is monospaced, `why`
    is the comment or docstring that says why the thing exists, `where` is a file and line
    that the source view can open. The client may style them; it may not drop them.
    """

    key: str
    label: str
    kind: str = "text"


@dataclass(frozen=True)
class Section:
    """A grouped table within a document."""

    query: str
    columns: tuple[Column, ...]
    # The column holding the graph node id. A row whose id is null is still shown -- it is
    # a fact about the program either way -- but it is not clickable, and the client says
    # so rather than offering a link that goes nowhere.
    node_col: str = "node"
    # The column to group rows under as headings. None means one flat table.
    group_col: str | None = None
    # The column holding a **table name**, for a section whose rows are not nodes.
    #
    # `DOC_DB_TABLES` selects `NULL AS node` on purpose -- a declared table is not a node
    # in the graph, and inventing an id to make a row clickable would be a link to nothing.
    # But selecting a table is a real act with a route of its own: it means selecting the
    # code that reads and writes it, which `TABLE_ROUTINES` answers and the navigator has
    # done since it had a Database group. Without this the whole 43-row section renders
    # inert, and an inert row is indistinguishable from a row whose id was lost.
    #
    # Declared here rather than inferred by the client from a null id, because "this row
    # names a table" and "this row's node could not be resolved" are different facts that
    # look identical on the wire (rule 30).
    table_col: str | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    blurb: str
    sections: tuple[Section, ...]


# --------------------------------------------------------------------------- #
# The map's own documents.
#
# Ordered broadly as the rendered set is (named values sit beside the data here
# rather than fourteenth, and flows and governance have no document here),
# because that order is an argument: where to
# start, then what it sets in motion, then what does the work, then what it
# holds, then what it touches, then why it is that way.
# --------------------------------------------------------------------------- #

DOCUMENTS: tuple[Document, ...] = (
    Document(
        id="entrypoints",
        title="Where to start",
        blurb="Ways in, ranked by how much of the program each one commands. "
              "The top of this list is the largest thing the program does.",
        sections=(
            Section(
                query=queries.DOC_ENTRYPOINTS,
                group_col="kind",
                columns=(
                    Column("name", "Way in", "code"),
                    Column("routine", "Runs", "code"),
                    Column("evidence", "How it is registered"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="routines",
        title="Routines",
        blurb="Every routine, with what goes in and what comes out. WHY is the comment "
              "or docstring attached to it — the part the code itself cannot tell you.",
        sections=(
            Section(
                query=queries.DOC_ROUTINES,
                group_col="module",
                columns=(
                    Column("name", "Routine", "code"),
                    Column("signature", "Signature", "code"),
                    Column("why", "WHY", "why"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="data",
        title="Data structures",
        blurb="What the program holds: classes, dataclasses, enums and type aliases, "
              "with their fields.",
        sections=(
            Section(
                query=queries.DOC_STRUCTURES,
                group_col="module",
                columns=(
                    Column("name", "Structure", "code"),
                    Column("kind", "Kind"),
                    Column("fields", "Fields", "code"),
                    Column("why", "WHY", "why"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="constants",
        title="Named values",
        blurb="The configuration the program carries in its own source — model names, "
              "ceilings, directory names, prompts. A constant is a name, and the comment "
              "beside it is often the only place the reason is written down.",
        sections=(
            Section(
                query=queries.DOC_CONSTANTS,
                group_col="module",
                columns=(
                    Column("name", "Name", "code"),
                    Column("value", "Value", "code"),
                    Column("why", "WHY", "why"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="boundaries",
        title="Boundaries",
        blurb="Everywhere the program touches the world outside itself, grouped by the "
              "kind of thing it touches. Each row keeps the evidence that admitted it.",
        sections=(
            Section(
                query=queries.DOC_BOUNDARIES,
                group_col="kind",
                columns=(
                    Column("target", "Target", "code"),
                    Column("direction", "Direction"),
                    Column("routine", "From", "code"),
                    Column("evidence", "Evidence"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="database",
        title="Database",
        blurb="The tables the program declares, and which routines read or write each "
              "one. A table written far more often than it is read is worth a look.",
        sections=(
            Section(
                query=queries.DOC_DB_TABLES,
                table_col="name",
                columns=(
                    Column("name", "Table", "code"),
                    Column("columns", "Columns", "code"),
                    Column("reads", "Reads"),
                    Column("writes", "Writes"),
                    Column("where", "Declared at", "where"),
                ),
            ),
            Section(
                query=queries.DOC_DB_OPS,
                group_col="tbl",
                columns=(
                    Column("operation", "Operation"),
                    Column("direction", "Direction"),
                    Column("routine", "From", "code"),
                    Column("sql", "Statement", "code"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="network",
        title="Network",
        blurb="What leaves the machine, with the full record: protocol, verb, "
              "destination, port, timeout, retries. A timeout nobody set is a fact "
              "about the program, so it is shown as unset rather than omitted.",
        sections=(
            Section(
                query=queries.DOC_NET,
                group_col="protocol",
                columns=(
                    Column("destination", "Destination", "code"),
                    Column("verb", "Verb"),
                    Column("routine", "From", "code"),
                    Column("timeout", "Timeout"),
                    Column("retries", "Retries"),
                    Column("where", "Where", "where"),
                ),
            ),
        ),
    ),
    Document(
        id="artefacts",
        title="Files the program names",
        blurb="Names the authors chose, which is different from files the code opens. "
              "A database whose path is assembled from parts, rather than written "
              "whole, is named here and reaches no other detector.",
        sections=(
            Section(
                query=queries.DOC_ARTEFACTS,
                group_col="ext",
                columns=(
                    Column("name", "Name", "code"),
                    Column("kind", "Kind"),
                    Column("mentions", "Mentions"),
                    Column("namers", "Named by"),
                ),
            ),
        ),
    ),
)

BY_ID = {d.id: d for d in DOCUMENTS}


# --------------------------------------------------------------------------- #
# Building one
# --------------------------------------------------------------------------- #

def index() -> list[dict[str, str]]:
    """What document mode can show. Not a count -- the counts cost a query each."""
    return [{"id": d.id, "title": d.title, "blurb": d.blurb} for d in DOCUMENTS]


def build(store: Store, doc_id: str) -> dict[str, Any]:
    """One document, whole.

    **Whole** is deliberate. Rule 8 bounds diagrams and nothing else: a reference list is
    never abbreviated, and this is a reference list. 4,734 routines is a large page, and a
    large page a reader can search is worth more than a small one that quietly stopped.
    The client may page it for the browser's sake; it may not decide the content.
    """
    doc = BY_ID.get(doc_id)
    if doc is None:
        return {"found": False, "id": doc_id,
                "reason": "no such document in this map"}

    out_sections: list[dict[str, Any]] = []
    for spec in doc.sections:
        # Grouping here is by module, kind, table, protocol or extension -- values the rows
        # already carry.
        # None of these need the package expression the *node* queries splice in, and
        # binding parameters a statement does not name is how two query families drift
        # into depending on each other's shape.
        rows = [dict(r) for r in store.query(spec.query, spec.params)]
        groups: list[dict[str, Any]] = []
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = str(row.get(spec.group_col) or "") if spec.group_col else ""
            g = seen.get(key)
            if g is None:
                g = {"title": key, "rows": []}
                seen[key] = g
                groups.append(g)
            g["rows"].append({
                "node": row.get(spec.node_col),
                # Present only where the section declares one, so a client can tell "this
                # row selects a table" from "this row selects nothing" without reading the
                # shape of a null.
                **({"table": row.get(spec.table_col)} if spec.table_col else {}),
                "cells": {c.key: row.get(c.key) for c in spec.columns},
            })
        for g in groups:
            g["count"] = len(g["rows"])
        out_sections.append({
            "columns": [{"key": c.key, "label": c.label, "kind": c.kind}
                        for c in spec.columns],
            "grouped": spec.group_col is not None,
            # What a row in this section selects, stated rather than sniffed: "node" is a
            # graph node, "table" is a declared table and selects the code that touches it.
            "selects": "table" if spec.table_col else "node",
            "groups": groups,
            "rows": sum(len(g["rows"]) for g in groups),
        })

    return {
        "found": True,
        "id": doc.id,
        "title": doc.title,
        "blurb": doc.blurb,
        "sections": out_sections,
        "rows": sum(s["rows"] for s in out_sections),
    }
