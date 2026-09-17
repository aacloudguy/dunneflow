"""What an agent can read rather than ask for: the schema, and the map's own documents.

A tool answers a question; a resource is a thing that sits there. The split matters for
exactly one of these and that one decides the module: **the graph's DDL**, because an agent
that can read the schema can write its own SQL, and every question this server has not
thought to provide a tool for becomes answerable through `query`. Without it the escape
hatch is a door in the dark.

The map's eight generated documents are the second: prose this tool wrote *about* the
program, which `web/documents.py` already builds for the dashboard's Document mode.
"""

from __future__ import annotations

from typing import Any

from ..store import SCHEMA_SQL
from ..web.documents import build as build_document
from ..web.documents import index as document_index
from .session import Session

SCHEMA_URI = "dunneflow://schema/graph.sql"
DOCUMENT_PREFIX = "dunneflow://document/"

SCHEMA_DESCRIPTION = (
    "The graph's tables and indexes, as `CREATE TABLE` statements — what the `query` tool "
    "runs against. Every fact DunneFlow stores about a program is in one of these."
)


def listing(session: Session) -> list[dict[str, Any]]:
    """Every resource this session can serve.

    The documents belong to the **open map**, so this is asked of the session rather than
    computed once: a program switch changes the list, and a cold start has none of them.
    The schema is always there, because it describes the shape rather than the contents —
    an agent with nothing open can still learn what it will be able to ask.
    """
    found: list[dict[str, Any]] = [{
        "uri": SCHEMA_URI,
        "name": "graph schema",
        "description": SCHEMA_DESCRIPTION,
        "mimeType": "application/sql",
    }]
    if not session.opened:
        return found
    for document in document_index():
        found.append({
            "uri": DOCUMENT_PREFIX + document["id"],
            "name": document.get("title", document["id"]),
            "description": document.get("blurb", ""),
            "mimeType": "text/markdown",
        })
    return found


def read(session: Session, uri: str) -> list[dict[str, Any]]:
    """One resource, as MCP's `contents` list.

    An unknown URI **raises** rather than returning an empty list. An empty `contents` is a
    resource that exists and holds nothing, which is a different fact from one that does
    not exist — and a client shown the first for the second stops looking (rule 30).
    """
    if uri == SCHEMA_URI:
        return [{"uri": uri, "mimeType": "application/sql", "text": SCHEMA_SQL}]

    if uri.startswith(DOCUMENT_PREFIX):
        doc_id = uri[len(DOCUMENT_PREFIX):]
        known = {d["id"] for d in document_index()}
        if doc_id not in known:
            raise KeyError(
                f"this map has no document called {doc_id!r} — it holds "
                f"{', '.join(sorted(known))}")
        built = build_document(session.store, doc_id)
        return [{"uri": uri, "mimeType": "text/markdown",
                 "text": _as_markdown(built)}]

    raise KeyError(f"nothing is served at {uri!r} — ask resources/list for what is")


def _as_markdown(document: dict[str, Any]) -> str:
    """A generated document as text, in the shape `web/documents.py` actually builds.

    A document holds sections; a section holds `columns` and `groups`; a group holds a
    title (empty where the section is ungrouped) and rows whose values live under `cells`.
    Read out of `build()` rather than assumed — the first version of this function invented
    a `section["title"]` and a `row[key]` that do not exist, and would have rendered every
    document as a row of empty headings with nothing under them. Nothing would have raised.

    Deliberately a rendering rather than the rows as JSON. Each row also carries the graph
    node that produced it, which is what lets the dashboard light the stack when one is
    clicked; none of that survives a pipe, and an agent that wants the node has `routine`
    and `query`. Putting both in one payload would double the size of a document to carry a
    second answer that is better asked for directly.
    """
    lines = [f"# {document.get('title', 'document')}"]
    if document.get("blurb"):
        lines += ["", str(document["blurb"])]

    for section in document.get("sections", []):
        columns = section.get("columns", [])
        labels = [str(c.get("label", c.get("key", ""))) for c in columns]
        keys = [str(c.get("key", "")) for c in columns]
        for group in section.get("groups", []):
            title = str(group.get("title") or "")
            if title:
                lines += ["", f"## {title}  ({group.get('count', 0):,})"]
            rows = group.get("rows", [])
            if not labels or not rows:
                lines += ["", "*nothing here*"]
                continue
            lines += ["", "| " + " | ".join(labels) + " |",
                      "|" + "|".join(["---"] * len(labels)) + "|"]
            for row in rows:
                cells = row.get("cells", {})
                lines.append("| " + " | ".join(_cell(cells.get(k)) for k in keys) + " |")
    return "\n".join(lines) + "\n"


def _cell(value: Any) -> str:
    """One value, safe inside a Markdown table row.

    A pipe would end the cell and a newline would end the row, and both are ordinary
    characters in a docstring or a SQL statement — which is most of what these documents
    are made of. Rule 91, in a table.
    """
    return str("" if value is None else value).replace("|", "\\|").replace("\n", " ")
