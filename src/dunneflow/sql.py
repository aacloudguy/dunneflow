"""Reading the SQL a program contains.

Database access is the one boundary where the target is not a filename or a URL but a
statement, and that statement says far more than "touched the database": which tables,
in which direction, and -- for DDL -- the schema itself.

Parsing is deliberately lexical rather than a full SQL grammar. Programs build SQL by
interpolation, so a fair proportion of what is found is fragmentary by nature; a strict
parser would reject exactly the statements worth seeing. What follows recognises the
shapes that matter and says nothing about the rest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A quoted, bracketed, or bare identifier, optionally schema-qualified.
_IDENT = r'(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)'
_QUAL = rf"(?:{_IDENT}\s*\.\s*)?({_IDENT})"

_LEADING = re.compile(
    r"^\s*(?:--[^\n]*\n|/\*.*?\*/|\s)*"
    r"(WITH|SELECT|INSERT|REPLACE|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|"
    r"PRAGMA|BEGIN|COMMIT|ROLLBACK|VACUUM|ANALYZE|ATTACH|DETACH|SAVEPOINT|RELEASE)\b",
    re.IGNORECASE | re.DOTALL,
)

# Words that are never a table name, however the grammar happens to line up.
_KEYWORDS = frozenset({
    "set", "values", "from", "where", "select", "insert", "update", "delete", "into",
    "table", "index", "view", "as", "on", "and", "or", "not", "null", "default",
    "primary", "key", "unique", "check", "references", "conflict", "do", "nothing",
    "returning", "using", "join", "left", "right", "inner", "outer", "order", "group",
    "by", "limit", "offset", "having", "when", "then", "else", "end", "case",
})

# A leading verb is not enough: prose beginning "Update a field on the org-config"
# or "Create the shim directory" reads as SQL to any check that stops at the first
# word. Each verb must be corroborated by the structure that verb requires.
_STRUCTURE = {
    "SELECT":   re.compile(r"\bFROM\b|^\s*SELECT\s+(?:\d+|COUNT|MAX|MIN|SUM|EXISTS|\*)",
                           re.IGNORECASE),
    "WITH":     re.compile(r"\bAS\s*\(", re.IGNORECASE),
    "INSERT":   re.compile(r"\bINTO\b", re.IGNORECASE),
    "REPLACE":  re.compile(r"\bINTO\b", re.IGNORECASE),
    "UPDATE":   re.compile(r"\bSET\b", re.IGNORECASE),
    "DELETE":   re.compile(r"\bFROM\b", re.IGNORECASE),
    "CREATE":   re.compile(r"\b(TABLE|INDEX|VIEW|TRIGGER|VIRTUAL)\b", re.IGNORECASE),
    "ALTER":    re.compile(r"\bTABLE\b", re.IGNORECASE),
    "DROP":     re.compile(r"\b(TABLE|INDEX|VIEW|TRIGGER)\b", re.IGNORECASE),
    "TRUNCATE": re.compile(r"\bTABLE\b|^\s*TRUNCATE\s+\w+\s*;?\s*$", re.IGNORECASE),
    "ATTACH":   re.compile(r"\bDATABASE\b|\bAS\b", re.IGNORECASE),
    "DETACH":   re.compile(r"\bDATABASE\b|^\s*DETACH\s+\w+\s*;?\s*$", re.IGNORECASE),
    "PRAGMA":   re.compile(r"^\s*PRAGMA\s+[\w.]+\s*(=|\(|;|$)", re.IGNORECASE),
}

# Control statements carry no structure at all, so they are accepted only when the
# whole string is one -- which is what separates `ROLLBACK;` from "rollback the claim".
_CONTROL_ONLY = re.compile(
    r"^\s*(BEGIN|COMMIT|ROLLBACK|VACUUM|ANALYZE|SAVEPOINT|RELEASE)"
    r"(\s+(IMMEDIATE|DEFERRED|EXCLUSIVE|TRANSACTION|WORK|SAVEPOINT))*"
    r"(\s+[A-Za-z_][A-Za-z0-9_]*)?\s*;?\s*$",
    re.IGNORECASE,
)

# Parameter markers and the punctuation of an expression. Prose has none of these.
_SQL_TOKENS = re.compile(r"[=*(),;]|\?|%s|%\(|\$\d|:\w+\b")

_FROM_JOIN = re.compile(rf"\b(?:FROM|JOIN)\s+{_QUAL}", re.IGNORECASE)
_INTO = re.compile(rf"\b(?:INSERT|REPLACE)\s+(?:OR\s+\w+\s+)?INTO\s+{_QUAL}", re.IGNORECASE)
# `... ON CONFLICT DO UPDATE SET x = ?` is an upsert clause, not a second table.
_UPDATE = re.compile(
    rf"(?<!DO )\bUPDATE\s+(?:OR\s+(?:ROLLBACK|ABORT|REPLACE|FAIL|IGNORE)\s+)?{_QUAL}",
    re.IGNORECASE,
)
_DELETE = re.compile(rf"\bDELETE\s+FROM\s+{_QUAL}", re.IGNORECASE)
_CREATE_TABLE = re.compile(
    rf"\bCREATE\s+(?:(TEMP|TEMPORARY)\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?{_QUAL}",
    re.IGNORECASE,
)
_CREATE_INDEX = re.compile(
    rf"\bCREATE\s+(UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?{_QUAL}\s+ON\s+{_QUAL}\s*\(([^)]*)\)",
    re.IGNORECASE,
)
_CREATE_VIEW = re.compile(
    rf"\bCREATE\s+(?:TEMP\s+|TEMPORARY\s+)?VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?{_QUAL}",
    re.IGNORECASE,
)
_ALTER = re.compile(rf"\bALTER\s+TABLE\s+{_QUAL}", re.IGNORECASE)
_DROP = re.compile(rf"\bDROP\s+(?:TABLE|INDEX|VIEW)\s+(?:IF\s+EXISTS\s+)?{_QUAL}", re.IGNORECASE)

READ = "READ"
WRITE = "WRITE"
DDL = "DDL"
CONTROL = "CONTROL"

_OP_DIRECTION = {
    "SELECT": READ, "WITH": READ, "PRAGMA": READ,
    "INSERT": WRITE, "REPLACE": WRITE, "UPDATE": WRITE, "DELETE": WRITE, "TRUNCATE": WRITE,
    "CREATE": DDL, "ALTER": DDL, "DROP": DDL,
    "BEGIN": CONTROL, "COMMIT": CONTROL, "ROLLBACK": CONTROL, "SAVEPOINT": CONTROL,
    "RELEASE": CONTROL, "VACUUM": CONTROL, "ANALYZE": CONTROL, "ATTACH": CONTROL,
    "DETACH": CONTROL,
}


@dataclass(slots=True)
class Column:
    name: str
    type: str = ""
    constraints: str = ""


@dataclass(slots=True)
class TableDef:
    name: str
    columns: list[Column] = field(default_factory=list)
    temporary: bool = False


@dataclass(slots=True)
class IndexDef:
    name: str
    table: str
    columns: str
    unique: bool = False


@dataclass(slots=True)
class SqlOp:
    """One statement found in the source, and what it does to what."""

    operation: str
    direction: str
    tables: list[str] = field(default_factory=list)
    sql: str = ""


def _clean(ident: str) -> str:
    return ident.strip().strip('"`[]').strip()


def _is_table_name(ident: str) -> bool:
    """Reject grammar accidents: `SET`, `VALUES`, and placeholders are not tables."""
    name = _clean(ident)
    if not name or name in {"?", "*"}:
        return False
    if name.lower() in _KEYWORDS:
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", name))


def looks_like_sql(text: str) -> bool:
    """Whether a string is a statement rather than a sentence that begins like one.

    Most strings in a program are not SQL, and a surprising number of docstrings open
    with a word that is also a SQL verb. Requiring the structure each verb implies is
    what separates `UPDATE t SET x = ?` from "Update a field on the org-config".
    """
    if not text or len(text) < 6 or len(text) > 20000:
        return False
    # **A statement never ends with a full stop, and a sentence does.** The tests below
    # take a parenthesis or a comma as evidence of SQL, and prose has both: pdfcraft's MCP
    # tool descriptions, *"delete: true removes the pages from this document afterwards
    # (undoable)."*, read as `DELETE ... FROM this` and minted three tables the program
    # never had. Measured before it was decided: of every statement stored in the maps on
    # disk on 2026-11-01 -- Comitia, DunneFlow, DunneNote, gstack, ~1,900 -- none ends in
    # one.
    if text.rstrip().endswith("."):
        return False
    m = _LEADING.match(text)
    if not m:
        return False
    verb = m.group(1).upper()
    structure = _STRUCTURE.get(verb)
    if structure is None:
        return _CONTROL_ONLY.match(text) is not None
    hit = structure.search(text)
    if hit is None:
        return False
    # Structure alone still admits "Select the best candidate from the list". Real
    # statements carry a parameter marker, punctuation, or uppercase keywords;
    # an English sentence that happens to contain FROM carries none of the three.
    if _SQL_TOKENS.search(text):
        return True
    return m.group(1).isupper() and hit.group(0).isupper()


def parse(text: str) -> SqlOp | None:
    """Classify one statement and name the tables it concerns."""
    m = _LEADING.match(text)
    if not m:
        return None
    op = m.group(1).upper()

    # `WITH ... SELECT` and `CREATE TABLE` need the more specific verb.
    if op == "CREATE":
        if _CREATE_INDEX.search(text):
            op = "CREATE INDEX"
        elif _CREATE_TABLE.search(text):
            op = "CREATE TABLE"
        elif _CREATE_VIEW.search(text):
            op = "CREATE VIEW"

    direction = _OP_DIRECTION.get(op.split()[0], CONTROL)

    tables: list[str] = []
    for rx in (_INTO, _UPDATE, _DELETE, _ALTER, _DROP, _CREATE_TABLE, _CREATE_VIEW):
        for hit in rx.finditer(text):
            candidate = hit.groups()[-1]
            if _is_table_name(candidate):
                tables.append(_clean(candidate))
    for hit in _FROM_JOIN.finditer(text):
        if _is_table_name(hit.group(1)):
            tables.append(_clean(hit.group(1)))
    for hit in _CREATE_INDEX.finditer(text):
        if _is_table_name(hit.group(3)):
            tables.append(_clean(hit.group(3)))

    # An INSERT ... SELECT both writes and reads; the write is what matters.
    seen: set[str] = set()
    ordered: list[str] = []
    for t in tables:
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)

    # The statement is recorded whole. A half-quoted query cannot be checked against
    # the schema, which is the only reason to record it at all.
    return SqlOp(
        operation=op,
        direction=direction,
        tables=ordered,
        sql=" ".join(text.split()),
    )


def parse_table_def(text: str) -> TableDef | None:
    """Pull a table's columns out of its CREATE TABLE statement."""
    m = _CREATE_TABLE.search(text)
    if not m:
        return None
    name = _clean(m.group(2))
    body = _column_body(text, m.end())
    return TableDef(name=name, columns=_split_columns(body), temporary=bool(m.group(1)))


def parse_index_defs(text: str) -> list[IndexDef]:
    out = []
    for m in _CREATE_INDEX.finditer(text):
        out.append(IndexDef(
            name=_clean(m.group(2)), table=_clean(m.group(3)),
            columns=" ".join(m.group(4).split()), unique=bool(m.group(1)),
        ))
    return out


def _column_body(text: str, start: int) -> str:
    """The text between the parentheses that follow a CREATE TABLE name."""
    open_at = text.find("(", start)
    if open_at < 0:
        return ""
    depth = 0
    for i in range(open_at, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[open_at + 1 : i]
    return text[open_at + 1 :]


_TABLE_CONSTRAINT = re.compile(
    r"^\s*(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|CONSTRAINT)\b", re.IGNORECASE
)


def _split_columns(body: str) -> list[Column]:
    """Split a column list on top-level commas, then read name and type off each."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))

    cols: list[Column] = []
    for raw in parts:
        piece = " ".join(raw.split())
        if not piece or _TABLE_CONSTRAINT.match(piece):
            continue
        tokens = piece.split(" ", 1)
        name = _clean(tokens[0])
        if not name:
            continue
        rest = tokens[1] if len(tokens) > 1 else ""
        type_m = re.match(
            r"^([A-Za-z]+(?:\s*\([^)]*\))?)", rest.strip()
        )
        ctype = " ".join(type_m.group(1).split()) if type_m else ""
        constraints = rest[type_m.end():].strip() if type_m else rest.strip()
        cols.append(Column(name=name, type=ctype, constraints=constraints[:120]))
    return cols
