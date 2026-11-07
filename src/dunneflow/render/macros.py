"""`15-macros.md`: what the program's macros do, and what the map could not see of them.

Nothing here is bounded, because the reader who comes for one macro in the long tail has
nowhere else to go, and it is one row per definition rather than per use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..resolve.macros import macro_report
from ..store import Store
from ..words import are, plural
from .page import Stamp, header


def _esc(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _where(d: dict[str, Any]) -> str:
    if d["file"]:
        return f"{d['file']}:{d['line']}"
    return {"command_line": "the build's command line", "builtin": "the compiler",
            "unknown": "not known to this reader"}.get(d["origin"], d["origin"])


def _table(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["| Macro | Defined | Uses | Wrote | Reaches | Touches |",
             "|---|---|---:|---:|---|---|"]
    for d in rows:
        reach = [f"{d['in_tree']:,} here" if d["in_tree"] else "",
                 f"{d['leaving']:,} outside" if d["leaving"] else "",
                 f"{d['indirect']:,} through a value" if d["indirect"] else ""]
        wrote = d["routines_written"] + d["structures_named"]
        lines.append(
            f"| `{_esc(d['name'])}` | {_esc(_where(d))} | {d['uses']:,} | "
            f"{wrote:,} | {', '.join(x for x in reach if x)} | {', '.join(d['kinds'])} |")
    lines.append("")
    return lines


def render_macros(store: Store, out: Path, program: str, stamp: Stamp) -> Path:
    report = macro_report(store)
    s = report["summary"]
    defs = report["definitions"]
    lines = [
        header(program, "Macros", stamp),
        "What the program's macros do where they are used. A macro is not a way in and is "
        "not a call anybody wrote: it is text a compiler replaced, so this page is about what "
        "that text turned out to be, and most of it is unremarkable.\n",
    ]
    read, named = report["expansion"]["read"], report["expansion"]["named"]
    if not read and not named:
        lines.append("No language in this map has macros this tool reads, so this page has "
                     "nothing to say about this program, and that is not a finding.\n")
        return _write(out, lines)

    lines.append(f"**{s['uses']:,} uses of {plural(len(defs), 'definition')}.** "
                 f"Of {plural(s['routines'], 'routine')}, **{s['routines_written']:,} "
                 f"{are(s['routines_written'])} written by macros**, and "
                 f"{s['routines_named']:,} more have a name a macro gave them over a body "
                 f"somebody wrote. {plural(s['boundaries'], 'boundary', 'boundaries')} "
                 f"{are(s['boundaries'])} reached through a macro or a body one wrote.\n")

    lines += _unseen(report, read, named)

    shadows = [d for d in defs if d["shadows"]]
    if shadows:
        lines += ["## Named like a boundary, and going somewhere else\n",
                  "The name says one thing and the expansion another, so these are not "
                  "recorded as boundaries.\n"]
        lines += _table(shadows)

    reaching = [d for d in defs if d["boundaries"]]
    if reaching:
        lines += ["## What leaves the program through a macro\n",
                  "`09-anomalies.md` reports those this program or its build defined. Most "
                  "are an ordinary wrapper; these are here so that you can see them.\n"]
        lines += _table(reaching)
    rest = [d for d in defs if not d["boundaries"]]
    calling = [d for d in rest if d["in_tree"] or d["leaving"] or d["indirect"]]
    if calling:
        lines += ["## What makes calls\n"]
        lines += _table(calling)
    writing = [d for d in rest if d not in calling and (d["routines_written"]
                                                        or d["structures_named"])]
    if writing:
        lines += ["## What writes routines and structures\n",
                  "Folded to one row each in `03-routines.md`, where the routines would "
                  "otherwise be most of the page.\n"]
        lines += _table(writing)
    quiet = [d for d in rest if d not in calling and d not in writing]
    if quiet:
        lines += ["## The rest\n",
                  "Constants, string wrappers and annotations: no call under them and "
                  "nothing written.\n"]
        lines += _table(quiet)
    return _write(out, lines)


def _unseen(report: dict[str, Any], read: list[str], named: list[str]) -> list[str]:
    s, u = report["summary"], report["unread"]
    lines = ["## What this page cannot see\n"]
    if read:
        lines.append(f"- **{', '.join(read)}**: the toolchain expands every macro, so what is "
                     "below is what it expanded to, **in the one configuration read**.")
        lines.append("- **One hop.** A macro inside a macro's body is credited to the one "
                     "written at the line, and the definition is where to look further.")
        lines.append("- **Boundaries are the names the rules list.** A call to anything else "
                     "is under *Reaches*, and it is not called a boundary.")
    if named:
        lines.append(f"- **{', '.join(named)}**: this reader sees a use and **does not read "
                     "what it does**. Nothing is reported through these macros, which does "
                     "not mean there is nothing to report.")
    if u["lines"]:
        lines.append(f"- **{u['lines']:,} lines not read** in `#if` arms this configuration "
                     f"does not take, across {plural(len(u['arms']), 'file')}.")
    if u["files_missing_headers"]:
        lines.append(f"- **{plural(u['files_missing_headers'], 'file')} with a header not "
                     "found.** Macros from a missing header are **not read, rather than "
                     "absent**, and a call under them may be missing here.")
    if s["opaque_asm"]:
        lines.append(f"- **{plural(s['opaque_asm'], 'inline assembly statement')}**, which "
                     "this map cannot read into.")
    if s["directive_uses"]:
        lines.append(f"- {plural(s['directive_uses'], 'use')} in a directive (`#if ID(1)`) "
                     "decide what is read and run nothing, so they are not counted above.")
    lines.append("")
    if u["headers"]:
        lines += ["| Header not found | Files |", "|---|---:|"]
        lines += [f"| `{_esc(h['header'])}` | {h['files']:,} |" for h in u["headers"]]
        lines.append("")
    if u["arms"]:
        lines += ["| File with arms not read | Lines |", "|---|---:|"]
        lines += [f"| {_esc(a['file'])} | {a['lines']:,} |" for a in u["arms"]]
        lines.append("")
    return lines


def _write(out: Path, lines: list[str]) -> Path:
    path = out / "15-macros.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
