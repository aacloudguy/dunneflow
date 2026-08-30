"""The values the program names, and the comments explaining why they are those values.

A constant is configuration a person wrote down and gave a name: the model to call, the
token ceiling, the directory to write into, how many times to retry. It is exactly the
kind of thing a reader orienting in unfamiliar code needs and cannot get from a call
graph -- and DunneFlow recorded none of it. `visit_Assign` caught only CLI app objects,
class bodies became `Field_`, and module level became nothing at all, so `JTBD_OPENERS`
was declared, read six times, and absent from the map.

Two rules shape this page.

**The value is shown whole** -- rule 8. A ceiling cut off at eighty characters is no
longer the ceiling, and a reader who has to open the source to see the number they came
here for was not helped.

**The comment beside a constant is its WHY, and it leads.** A named value without its
reason is a number. `MENSORES_DIRNAME: Final[str] = ".mensores"` says what; the comment
above it says why it may not change. Those comments belong to the module scope too --
they are shown in both places, because a comment belongs against the thing it explains.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from ..store import Store


def _esc(text: str | None) -> str:
    """Table-safe and complete. Never truncates -- rule 8."""
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


CONSTANTS_SQL = """
SELECT module, name, value, type, is_final, comment, private, file, line
  FROM constants
 ORDER BY module, name
""".strip()

ALIASES_SQL = """
SELECT module, name, bases, line, file
  FROM structures
 WHERE kind = 'TYPE_ALIAS'
 ORDER BY module, name
""".strip()


def render_constants(store: Store, out: Path, root: Path, program: str,
                     stamp: str) -> Path:
    """Write `14-constants.md`. Nothing here is bounded."""
    rows = store.query(CONSTANTS_SQL)
    aliases = store.query(ALIASES_SQL)

    lines = [
        f"# {program} — named values\n",
        f"*Generated {stamp} by DunneFlow.*\n",
        "What the program configures, as it wrote it down: the values it names at "
        "module level, and the comments saying why they are those values. Values run "
        "at import, so a constant declared inside a module-level `try` or "
        "`if TYPE_CHECKING` is here and one declared inside a function is not.\n",
        "Every value is shown whole. A ceiling shortened for the table is no longer "
        "the ceiling, and the reader who came for the number would have to open the "
        "source anyway.\n",
    ]

    if not rows and not aliases:
        lines.append(
            "This program names no module-level values. That is unusual rather than "
            "impossible — a program whose configuration is all read at runtime from "
            "the environment or a file has nothing to declare here, and "
            "`05-boundaries.md` is where it will be.\n"
        )
        return _write(out, lines)

    lines += _summary(rows, aliases)
    lines += _aliases(aliases, root)
    lines += _constants(rows, root)
    lines += _reproducing()
    return _write(out, lines)


def _write(out: Path, lines: list[str]) -> Path:
    path = out / "14-constants.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _summary(rows: list, aliases: list) -> list[str]:
    public = sum(1 for r in rows if not int(r["private"]))
    final = sum(1 for r in rows if int(r["is_final"]))
    explained = sum(1 for r in rows if str(r["comment"]).strip())
    modules = len({str(r["module"]) for r in rows} | {str(a["module"]) for a in aliases})
    return [
        "## What there is\n",
        "| | Count |",
        "|---|---:|",
        f"| Named values | {len(rows):,} |",
        f"| …public | {public:,} |",
        f"| …declared `Final` | {final:,} |",
        f"| …carrying a comment that says why | {explained:,} |",
        f"| Type aliases | {len(aliases):,} |",
        f"| Modules declaring either | {modules:,} |",
        "",
    ]


def _aliases(aliases: list, root: Path | None) -> list[str]:
    """Type aliases lead, because a `Literal` alias is an enumerated vocabulary.

    `QueueState = Literal["pending", "adjudicating", "emitted", "rejected", "skipped"]`
    declares five states and the word `enum` appears nowhere. The members themselves
    are listed in `04-data.md`, which is where shapes live; this is the index.
    """
    if not aliases:
        return []
    lines = [
        "## Type aliases\n",
        "A name given to a type. Where the type is a `Literal`, the alias is an "
        "enumerated vocabulary declared without the word `enum` — the members are "
        "listed beside it in `04-data.md`, which is where shapes belong.\n",
        "| Alias | Is | Module | Source |",
        "|---|---|---|---|",
    ]
    for a in aliases:
        try:
            target = ", ".join(json.loads(str(a["bases"])))
        except (ValueError, TypeError):
            target = str(a["bases"])
        lines.append(
            f"| `{_esc(a['name'])}` | `{_esc(target)}` | `{_esc(a['module'])}` "
            f"| `{str(a['file'])}:{a['line']}` |"
        )
    lines.append("")
    return lines


def _constants(rows: list, root: Path | None) -> list[str]:
    """Every named value, grouped by the module that declares it.

    Grouped rather than ranked because a constant has no reach to rank by, and the
    module is how a reader will come looking: "what does the interview engine
    configure?" is the question this answers.
    """
    if not rows:
        return []
    by_module: dict[str, list] = defaultdict(list)
    for r in rows:
        by_module[str(r["module"])].append(r)

    lines = [
        "## Every named value\n",
        f"{len(rows):,} values across {len(by_module):,} modules, grouped by the "
        "module that declares them. A leading underscore means the module keeps it to "
        "itself.\n",
    ]
    for module in sorted(by_module):
        group = by_module[module]
        lines.append(f"### `{module}`\n")
        lines.append("| Name | Value | Type | Why |")
        lines.append("|---|---|---|---|")
        for r in group:
            name = str(r["name"])
            marks = []
            if int(r["is_final"]):
                marks.append("`Final`")
            if int(r["private"]):
                marks.append("private")
            suffix = f" — {' · '.join(marks)}" if marks else ""
            lines.append(
                f"| `{_esc(name)}`{suffix} | `{_esc(r['value'])}` "
                f"| `{_esc(r['type']) or '—'}` | {_esc(r['comment']) or '—'} |"
            )
        first = group[0]
        lines.append(f"\n`{str(first['file'])}`\n")
    return lines


def _reproducing() -> list[str]:
    """Rule 13. Every count above is re-runnable, and the query is the proof."""
    return [
        "## Reproducing this\n",
        "```bash",
        'dunneflow query output/<program> --sql "<the SQL below>"',
        "```\n",
        "**Every named value:**\n",
        "```sql",
        CONSTANTS_SQL,
        "```\n",
        "**Every type alias:**\n",
        "```sql",
        ALIASES_SQL,
        "```\n",
        "**The ones nobody explained** — a named value with no comment beside it is "
        "a number whose reason lives only in someone's head:\n",
        "```sql",
        "SELECT module, name, value FROM constants\n"
        " WHERE trim(comment) = ''\n"
        " ORDER BY module, name",
        "```\n",
    ]
