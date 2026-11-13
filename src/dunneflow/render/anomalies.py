"""The anomaly report.

Ordered by what it means for the program, then by how sure the tool is. Every entry
carries its blind spot, because a finding you cannot check is not a finding.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..anomalies import BROKEN, INFO, SUSPECT, Report
from .page import Stamp, header

_BADGE = {BROKEN: "🔴 BROKEN", SUSPECT: "🟠 SUSPECT", INFO: "🔵 INFO"}

_MEANING = {
    BROKEN: "The program cannot be correct as written. Each of these is a defect "
            "unless the blind spot applies.",
    SUSPECT: "Probably wrong, or a latent operational hazard. Worth reading before "
             "changing anything nearby.",
    INFO: "Worth knowing. Not necessarily wrong.",
}


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
# `Path("lictores/cli.py").resolve()` resolves against the *working directory*, so run from
# anywhere inside the analysed tree the strip would succeed and silently prepend the
# intervening directories to every path on the page.


def render_anomalies(report: Report, out: Path, program: str,
                     stamp: Stamp) -> Path:
    counts = report.counts()
    lines = [header(program, "Anomalies", stamp)]
    lines.append(
        "What looks wrong, and how confident the tool is about each one.\n\n"
        "**Severity** says what it would mean for the program. **Confidence** says how "
        "sure DunneFlow is. They are different questions. Every entry carries a "
        "**blind spot** — the thing that would make it a false alarm — because in the "
        "first run against a live codebase, six confident findings in a row turned out "
        "to be defects in this tool rather than in the program it was reading. Check "
        "the blind spot before acting on any of these.\n"
    )

    lines.append("| Severity | Count | Meaning |\n|---|---:|---|")
    for sev in (BROKEN, SUSPECT, INFO):
        lines.append(f"| {_BADGE[sev]} | {counts.get(sev, 0)} | {_MEANING[sev]} |")
    lines.append("")

    by_kind: dict[str, int] = defaultdict(int)
    for a in report.items:
        by_kind[a.kind] += 1
    if by_kind:
        lines.append("| Kind | Findings |\n|---|---:|")
        for kind, n in sorted(by_kind.items(), key=lambda kv: -kv[1]):
            lines.append(f"| `{kind}` | {n} |")
        lines.append("")

    if not report.items:
        lines.append("No anomalies found.\n")
        path = out / "09-anomalies.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    current = None
    for a in report.sorted():
        if a.severity != current:
            current = a.severity
            lines.append(f"\n## {_BADGE[a.severity]} ({counts.get(a.severity, 0)})\n")
            lines.append(f"*{_MEANING[a.severity]}*\n")
        if a.file and a.line:
            where = f"{a.file}:{a.line}"
        elif a.file:
            where = a.file
        else:
            where = ""
        lines.append(f"### {a.title}\n")
        meta = [f"`{a.kind}`", f"confidence **{a.confidence}**"]
        if a.count > 1:
            meta.append(f"{a.count:,} occurrences")
        if where:
            meta.append(f"`{where}`")
        lines.append(" · ".join(meta) + "\n")
        lines.append(f"{_esc(a.detail)}\n")
        lines.append(f"> **Blind spot.** {_esc(a.blind_spot)}\n")

    path = out / "09-anomalies.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
