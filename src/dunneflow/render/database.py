"""The database view.

Written for someone who wants the schema and the traffic against it: what tables the
program creates, what columns and indexes they have, and — in both directions — which
routines read them and which write them.

The schema comes from the code that creates it. Every `CREATE TABLE` in the source is
authoritative in a way that a hand-maintained data dictionary never is, and version
suffixes on table names make the migration history visible for free.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..store import Store


def _esc(text: str | None) -> str:
    """Table-safe, and complete. Never truncates -- see render/markdown.py."""
    if not text:
        return ""
    return " ".join(str(text).split()).replace("|", "\\|")


# There was a `path` here, and in eight other renderers -- nine copies of the
# same four lines, each stripping the analysed root off a stored absolute path so a reader
# would not be shown one machine's directory layout. Paths are stored relative now, so
# every one of them had nothing left to strip.
#
# They were removed rather than left as harmless no-ops, because they were not harmless:
# `Path("mensores/cli.py").resolve()` resolves against the *working directory*, so run from
# anywhere inside the analysed tree the strip would succeed and silently prepend the
# intervening directories to every path on the page.


def render_database(store: Store, out: Path, root: Path, program: str, stamp: str) -> Path | None:
    counts = store.query(
        "SELECT (SELECT COUNT(DISTINCT name) FROM db_tables) t,"
        "       (SELECT COUNT(*) FROM db_indexes) i,"
        "       (SELECT COUNT(*) FROM sql_ops) s"
    )[0]
    if not counts["s"]:
        return None

    lines = [f"# {program} — Database\n\n*Generated {stamp} by DunneFlow.*\n"]
    lines.append(
        "Schemas taken from the code that creates them, and every statement the program "
        "issues against them, in both directions.\n"
    )
    lines.append("| Measure | Count |\n|---|---:|")
    lines.append(f"| Tables created | {counts['t']:,} |")
    lines.append(f"| Indexes created | {counts['i']:,} |")
    lines.append(f"| SQL statements | {counts['s']:,} |")
    lines.append("")

    # -- traffic ------------------------------------------------------------ #
    lines.append("## Access by table\n")
    lines.append(
        "`READ` is `SELECT`; `WRITE` is `INSERT`/`UPDATE`/`DELETE`; `DDL` creates or "
        "alters. A table with writes but no reads — or the reverse — is usually worth "
        "a second look.\n"
    )
    lines.append(
        "| Table | Reads | Writes | DDL | Routines | Created here |\n"
        "|---|---:|---:|---:|---:|---|"
    )
    created = {r["name"] for r in store.query("SELECT DISTINCT name FROM db_tables")}
    rows = store.query(
        "SELECT tbl, SUM(direction='READ') r, SUM(direction='WRITE') w,"
        " SUM(direction='DDL') d, COUNT(DISTINCT routine_id) n"
        " FROM sql_ops WHERE tbl != '' GROUP BY tbl ORDER BY (r+w+d) DESC"
    )
    for r in rows:
        mark = "yes" if r["tbl"] in created else "—"
        lines.append(
            f"| `{_esc(r['tbl'])}` | {r['r']} | {r['w']} | {r['d']} | {r['n']} | {mark} |"
        )
    lines.append("")

    external = [r["tbl"] for r in rows if r["tbl"] not in created]
    if external:
        lines.append(
            f"> **{len(external)} tables are used but never created by this program**, so "
            f"their schema is defined elsewhere: "
            f"{', '.join('`' + t + '`' for t in external)}.\n"
        )

    # -- schema ------------------------------------------------------------- #
    lines.append("## Schema\n")
    tables = store.query("SELECT * FROM db_tables ORDER BY name, file")
    by_name: dict[str, list] = defaultdict(list)
    for t in tables:
        by_name[t["name"]].append(t)

    idx_by_table: dict[str, list] = defaultdict(list)
    for i in store.query("SELECT * FROM db_indexes ORDER BY name"):
        idx_by_table[i["tbl"]].append(i)

    for name in sorted(by_name):
        defs = by_name[name]
        lines.append(f"### `{name}`\n")
        if len(defs) > 1:
            lines.append(
                f"*Created in {len(defs)} places — the definitions below are each "
                f"occurrence.*\n"
            )
        for t in defs:
            cols = store.query(
                "SELECT * FROM db_columns WHERE tbl = ? AND file = ? ORDER BY idx",
                (name, t["file"]),
            )
            where = f"{t['file']}:{t['line']}"
            if cols:
                lines.append("| Column | Type | Constraints |\n|---|---|---|")
                for c in cols:
                    lines.append(
                        f"| `{_esc(c['name'])}` | `{_esc(c['type']) or '—'}` "
                        f"| {_esc(c['constraints']) or '—'} |"
                    )
            lines.append(f"\n`{where}`{' · TEMPORARY' if t['temporary'] else ''}\n")

        if idx_by_table.get(name):
            lines.append("**Indexes**\n")
            lines.append("| Index | Columns | Unique | Where |\n|---|---|---|---|")
            for i in idx_by_table[name]:
                lines.append(
                    f"| `{_esc(i['name'])}` | `{_esc(i['columns'])}` "
                    f"| {'yes' if i['uniq'] else '—'} "
                    f"| {_esc(i['file'] + ':' + str(i['line']))} |"
                )
            lines.append("")

    orphan_idx = [
        i for tbl, items in idx_by_table.items() if tbl not in by_name for i in items
    ]
    if orphan_idx:
        lines.append("### Indexes on tables created elsewhere\n")
        lines.append("| Index | Table | Columns | Unique |\n|---|---|---|---|")
        for i in orphan_idx:
            lines.append(
                f"| `{_esc(i['name'])}` | `{_esc(i['tbl'])}` "
                f"| `{_esc(i['columns'])}` | {'yes' if i['uniq'] else '—'} |"
            )
        lines.append("")

    # -- who touches what --------------------------------------------------- #
    lines.append("## Who reads and who writes\n")
    for direction, title in (("WRITE", "Writes"), ("READ", "Reads"), ("DDL", "Schema changes")):
        hits = store.query(
            "SELECT s.tbl, s.operation, s.sql, s.line, r.qualname, r.file"
            "  FROM sql_ops s JOIN routines r ON s.routine_id = r.id"
            " WHERE s.direction = ? AND s.tbl != ''"
            " ORDER BY s.tbl, r.qualname",
            (direction,),
        )
        if not hits:
            continue
        lines.append(f"### {title} ({len(hits):,})\n")
        lines.append("<details><summary>Show all</summary>\n")
        lines.append("| Table | Routine | Statement | Where |\n|---|---|---|---|")
        for h in hits:
            where = f"{h['file']}:{h['line']}"
            lines.append(
                f"| `{_esc(h['tbl'])}` | `{_esc(h['qualname'])}` "
                f"| `{_esc(h['sql'])}` | {_esc(where)} |"
            )
        lines.append("\n</details>\n")

    path = out / "07-database.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
