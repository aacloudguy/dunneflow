"""The glossary: what this program's words mean, and who says so.

Not a list of definitions a model wrote. A list of definitions **the project already
wrote**, bound to the code that uses the word, each opening onto the file and line it
came from. Nine of Mensores' eleven opaque terms were already defined in its own
documentation; the tool simply could not see them, because it read only source.

The terms nothing defines are the last section and the most useful one. That list is a
worklist, and it is also the exact input a model pass would be asked to read.
"""

from __future__ import annotations

from pathlib import Path

from ..docstore import DocStore
from ..resolve.glossary import GlossaryReport, Term, bind
from ..schema import Provenance
from ..store import Store

BADGE = {
    Provenance.DECLARED_CODE: "DECLARED · code",
    Provenance.DECLARED_DOCS: "DECLARED · docs",
    Provenance.CITED: "CITED",
    Provenance.INFERRED: "INFERRED",
}


def _rel(path: str, root: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return path


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split()).replace("|", "\\|")


def render_glossary(store: Store, docs: DocStore | None, out_dir: Path, root: Path,
                    program: str, stamp: str, docs_root: Path | None = None) -> Path:
    report = bind(store, docs)
    defined, total = report.coverage()
    doc_root = docs_root or root

    lines = [
        f"# {program} — Glossary\n",
        f"*Generated {stamp} by DunneFlow.*\n",
        "Every word this program uses as the name of a thing — a package, a command, a "
        "table — that is not ordinary programming vocabulary, together with whatever the "
        "program itself says it means. Nothing here is written by DunneFlow: each "
        "definition is quoted from a docstring or a document, and opens onto the line it "
        "was taken from.\n",
        f"**{defined:,} of {total:,} terms are defined somewhere.** The "
        f"{len(report.undefined):,} that are not are listed in full at the end.\n",
        "| Provenance | What it means | Cost |",
        "|---|---|---|",
        "| `DECLARED · code` | a module docstring, parsed | free |",
        "| `DECLARED · docs` | a glossary section or a definition table, parsed | free |",
        "| `CITED` | a model found it in prose and cited a line, and the citation was "
        "checked against that line | paid |",
        "| `INFERRED` | nothing states it; a guess, and it cannot prove itself | paid |",
        "",
    ]

    lines.append("\n## Defined terms\n")
    written = [t for t in report.terms if t.defined]
    if not written:
        lines.append("*Nothing in this program defines any of its own vocabulary.*\n")
    for term in written:
        lines.extend(_term_entry(term, doc_root))

    lines.append("\n## Terms nothing defines\n")
    if not report.undefined:
        lines.append("Every term this program names is defined somewhere in it.\n")
    else:
        lines.append(
            f"{len(report.undefined):,} words are used as names and explained nowhere in "
            "the code or the documentation. This is the worklist. It is also exactly "
            "what a model pass would be asked to read, and the reason to run one is to "
            "find a definition already written in prose that this scanner did not "
            "recognise — not to invent one.\n"
        )
        lines.append("| Term | Uses | First seen as |")
        lines.append("|---|---:|---|")
        for term in report.undefined:
            where = term.where[0] if term.where else ""
            lines.append(f"| `{_esc(term.term)}` | {term.uses:,} | {_esc(where)} |")
        lines.append("")

    lines.extend(_scanned(report, docs))
    path = out_dir / "10-glossary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _term_entry(term: Term, root: Path) -> list[str]:
    lines = [f"\n### {term.term}\n"]
    # Counts, not 638 module names. The examples are for orientation; the complete
    # list of what uses a word is a query away and is not what this page is for.
    examples = ", ".join(w.split(" ", 1)[-1] for w in term.where[:3])
    lines.append(f"*Used {term.uses:,} time{'s' if term.uses != 1 else ''} — "
                 f"{term.used_as()}. For example: {_esc(examples)}.*\n")
    for sense in term.senses:
        where = f"{_rel(sense.source, root)}:{sense.line}"
        lines.append(f"> {_esc(sense.definition)}\n")
        form = f", {sense.form}" if sense.form else ""
        heading = f" under “{_esc(sense.heading)}”" if sense.heading else ""
        lines.append(f"`{BADGE[sense.provenance]}` — {where}{heading}{form}\n")
    return lines


def _scanned(report: GlossaryReport, docs: DocStore | None) -> list[str]:
    lines = ["\n## What was read\n"]
    if docs is None:
        lines.append("No documentation was read. Every definition above comes from a "
                     "docstring in the source.\n")
        return lines
    c = docs.counts()
    lines.append(
        f"{c['documents']:,} documents, of which {c['duplicates']:,} are byte-identical "
        f"copies of another document and are counted once — agent worktrees and vendored "
        f"trees hold copies of a project's own writing, and counting a definition twice "
        f"makes a corpus look richer than it is.\n"
    )
    lines.append(
        f"{report.definitions_seen:,} definitions were found across "
        f"{report.documents_seen:,} distinct documents; the ones above are those whose "
        f"term is also a name in the code. A definition of a word the program never uses "
        f"is still recorded in `docs.db` and can be queried, but it is not part of this "
        f"program's vocabulary.\n"
    )
    return lines
