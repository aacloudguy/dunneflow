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


# There was a `path` here, and in eight other renderers -- nine copies of the
# same four lines, each stripping the analysed root off a stored absolute path so a reader
# would not be shown one machine's directory layout. Paths are stored relative now, so
# every one of them had nothing left to strip.
#
# They were removed rather than left as harmless no-ops, because they were not harmless:
# `Path("mensores/cli.py").resolve()` resolves against the *working directory*, so run from
# anywhere inside the analysed tree the strip would succeed and silently prepend the
# intervening directories to every path on the page.


def _esc(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(str(text).split()).replace("|", "\\|")


def render_glossary(store: Store, docs: DocStore | None, out_dir: Path,
                    program: str, stamp: str) -> Path:
    report = bind(store, docs)
    defined, total = report.coverage()

    lines = [
        f"# {program} — Glossary\n",
        f"*Generated {stamp} by DunneFlow.*\n",
        "Every word this program uses as the name of a thing — a package, a command, a "
        "table — that is not ordinary programming vocabulary, together with whatever the "
        "program itself says it means. Nothing here is written by DunneFlow: each "
        "definition is quoted from a docstring or a document, and opens onto the line it "
        "was taken from.\n",
        f"**{defined:,} of {total:,} terms are defined somewhere.** The "
        f"{len(report.undefined):,} that are not are listed in full at the end"
        + (f", and {len(report.set_aside):,} more words were held back as fragments of "
           "compound names — those are listed too, because the judgement is a reader's "
           "to overturn.\n" if report.set_aside else ".\n"),
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
        lines.extend(_term_entry(term))

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

    lines.append("\n## Words held back\n")
    if not report.set_aside:
        lines.append("Every word this program uses as a name is above.\n")
    else:
        lines.append(
            f"{len(report.set_aside):,} words occur only *inside* a compound constant "
            "name — never as the whole name of anything, and nothing defines them. "
            "`_GLOSSARY_DEFINITION_MAX_LEN` is one name somebody chose, and splitting it "
            "yields its subject, its type and its unit; the units are what these are. "
            "They are held back rather than dropped, because the split cannot tell "
            "`MENSORES_MAX_LEN`'s first word from its last: if one of these is the "
            "program's own word, it is on this list and nowhere else.\n"
        )
        lines.append("| Word | Uses | First seen as |")
        lines.append("|---|---:|---|")
        for term in report.set_aside:
            where = term.where[0] if term.where else ""
            lines.append(f"| `{_esc(term.term)}` | {term.uses:,} | {_esc(where)} |")
        lines.append("")

    lines.extend(_scanned(report, docs))
    path = out_dir / "10-glossary.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _term_entry(term: Term) -> list[str]:
    lines = [f"\n### {term.term}\n"]
    # Counts, not 638 module names. The examples are for orientation; the complete
    # list of what uses a word is a query away and is not what this page is for.
    examples = ", ".join(w.split(" ", 1)[-1] for w in term.where[:3])
    lines.append(f"*Used {term.uses:,} time{'s' if term.uses != 1 else ''} — "
                 f"{term.used_as()}. For example: {_esc(examples)}.*\n")
    for sense in term.senses:
        where = f"{sense.source}:{sense.line}"
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
