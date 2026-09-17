"""Vocabulary the documentation defines, and what the code does with it.

`12-traceability.md` asks what was built without a plan. This asks the mirror question
of the project's own words, and it is the harder half to render honestly, because the
interesting rows are the ones nothing was found for -- and an absence looks exactly the
same whether it is drift or a blind spot.

So the page leads with what it could not see, before any count is read: the admission
rule and everything it set aside, and which languages the graph was read from. Every
band states what would make placing a term there wrong, every term carries the
definition and the line it came from, and every claim ships the query behind it.

Nothing here is bounded. There are 119 admitted terms on Mensores and 94 set-aside ones;
all 213 are on the page.
"""

from __future__ import annotations

from pathlib import Path

from ..docstore import DocStore
from ..resolve import languages
from ..resolve.mirror import (
    ARTEFACT_NAMES_SQL,
    BANDS,
    BY_EXCLUSION,
    DEFINED_TERMS_SQL,
    EXCLUSIONS,
    MAX_TERM_WORDS,
    Mirror,
    MirroredTerm,
    measure,
    term_evidence_sql,
)
from ..store import Store
from .page import Stamp, header


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


def _slug(key: str) -> str:
    return key.lower().replace("_", "-")


def render_mirror(store: Store, docs: DocStore | None, out: Path,
                  program: str, stamp: Stamp) -> Path:
    """Write `13-mirror.md`, whether or not any documentation was read."""
    m = measure(store, docs)
    lines = [
        header(program, "words the documentation defines", stamp),
        "`12-traceability.md` asks what was built without a plan. This asks the same "
        "question of the project's vocabulary: **something took the trouble to define "
        "this word — does anything in the program answer to it?**\n",
    ]
    if not m.had_docs:
        return _write(out, lines + _no_documentation(m))

    lines += _what_it_could_not_see(m)
    lines += _what_was_joined(m)
    lines += _spectrum(m)
    lines += _bands(m)
    lines += _set_aside(m)
    lines += _reproducing(m)
    return _write(out, lines)


def _write(out: Path, lines: list[str]) -> Path:
    path = out / "13-mirror.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #


def _no_documentation(m: Mirror) -> list[str]:
    """Documentation is never a prerequisite, and its absence is never drift."""
    return [
        "## No documentation was read\n",
        "This run scanned source only (`--no-docs`, or a corpus with no documents in "
        "it). There is no set of defined words to mirror, so **there is no finding "
        "here** — not even an empty one. An absent corpus and a corpus that defines "
        "nothing look identical from inside the code, and this page will not "
        "pretend otherwise.\n",
        "Point `analyze` at a documentation root to get the join:\n",
        "```bash\ndunneflow analyze <path> --name <program> --docs <docs-root>\n```\n",
        f"The code half is already built: {m.artefacts_seen:,} references to "
        f"{m.artefact_names:,} named files, alongside every module, class, table and "
        "way in. It is waiting for something to compare against.\n",
    ]


def _what_it_could_not_see(m: Mirror) -> list[str]:
    """Said before any count, because every number below is a number about absence."""
    return [
        "## Read this first\n",
        "Every interesting row on this page is an **absence**, and an absence is the "
        "one finding that cannot prove itself. Three things limit what it means "
        "here.\n",
        languages.only(m.langs) + " *Absent from this program* is the strongest "
        "claim on this page, and it is weaker than *unused*.\n",
        f"**{m.excluded_total:,} of the {m.definitions_seen:,} definitions read are "
        "not words.** The definition extractor admits headings, test names and code "
        "fragments; run forwards that costs nothing, because a heading matches no code "
        "and is never seen. Run backwards it would fill this page with things Mensores "
        "was never asked to name. They are set aside by a rule stated below, counted, "
        "and listed whole — the rule is shape-based and cannot read meaning, so it "
        "keeps some phrases it should not and the Absent band shows them with their "
        "definitions beside them.\n",
        "**A word being used is not the definition being honoured.** This page proves "
        "that something in the program carries the word. Whether it still means what "
        "the document says it means is not a question two stores can answer.\n",
    ]


def _what_was_joined(m: Mirror) -> list[str]:
    return [
        "## What was joined\n",
        "| Input | Count |",
        "|---|---:|",
        f"| Documents scanned | {m.documents_scanned:,} |",
        f"| Definitions read from them | {m.definitions_seen:,} |",
        f"| Set aside as not a word | {m.excluded_total:,} |",
        f"| **Terms carried forward** | **{len(m.terms):,}** |",
        f"| Named files found in code | {m.artefact_names:,} |",
        f"| References to them | {m.artefacts_seen:,} |",
        "",
        "The named-file surface is here because of one word. `tabularium` is glossed "
        "in the pantheon table and appeared in the glossary nowhere, which read as a "
        "term the project had abandoned. It is in fact the name of the database the "
        "whole program writes to — a path assembled as "
        "`root / \".mensores\" / \"tabularium.db\"`, which is not a module, not a "
        "table and not a boundary target, because only the parts are literals. "
        "DunneFlow recorded no file the program names, so the first finding this "
        "report produced was a defect in the reader, not drift in the read.\n",
    ]


def _spectrum(m: Mirror) -> list[str]:
    groups = m.by_band()
    lines = [
        "## The spectrum\n",
        "A term is not used or unused. It has a standing, set by the strongest surface "
        "it appears on — being the name of a thing outranks being carried by a "
        "parameter, which outranks being said in a comment.\n",
        "| Standing | Terms | What it means |",
        "|---|---:|---|",
    ]
    for band in BANDS:
        n = len(groups[band.key])
        lines.append(
            f"| **[{band.label}](#{_slug(band.key)})** | {n:,} | {_esc(band.meaning)} |"
        )
    lines.append("")
    return lines


def _definition_cell(t: MirroredTerm) -> str:
    """Every definition of a term, with the file and line it was read from.

    Rule 13: a definition is a claim, and the route back to where it came from is the
    whole of its evidence. Terms are defined a handful of times at most, so this is
    listed in full rather than counted.
    """
    parts = []
    for d in t.definitions:
        where = f"`{_esc(d.doc)}`:{d.line}"
        parts.append(f"{_esc(d.definition)} — {where}")
    return "<br>".join(parts)


def _evidence_cell(t: MirroredTerm) -> str:
    """Where the program uses the word, as names rather than as a count.

    Bounded only where a name repeats: `mensores` is 623 modules and listing them is
    not a listing. The count is given with the surface, and `08-boundaries.md` and the
    module index already hold every one of them.
    """
    groups = t.by_surface()
    parts = []
    for surface, sightings in groups.items():
        names = sorted({s.name for s in sightings})
        detail = next((s.detail for s in sightings if s.detail), "")
        if len(names) <= 4:
            shown = " · ".join(f"`{_esc(n)}`" for n in names)
            parts.append(f"{surface}: {shown}" + (f" ({_esc(detail)})" if detail else ""))
        else:
            shown = " · ".join(f"`{_esc(n)}`" for n in names[:4])
            parts.append(
                f"{surface}: {shown} and {len(names) - 4:,} more"
            )
    return "<br>".join(parts) or "—"


def _bands(m: Mirror) -> list[str]:
    groups = m.by_band()
    lines: list[str] = ["## Every term, by standing\n"]
    for band in BANDS:
        terms = groups[band.key]
        lines += [
            f"### {band.label}\n",
            f'<a id="{_slug(band.key)}"></a>\n',
            f"{band.meaning} **{len(terms):,} term"
            f"{'s' if len(terms) != 1 else ''}.**\n",
            f"> **What would make a placement here wrong.** {band.spot(m.langs)}\n",
        ]
        if not terms:
            lines.append("Nothing in this band.\n")
            continue
        lines += [
            "| Term | Where the code uses it | What the documentation says |",
            "|---|---|---|",
        ]
        for t in terms:
            lines.append(
                f"| **{_esc(t.term)}** | {_evidence_cell(t)} "
                f"| {_definition_cell(t)} |"
            )
        lines.append("")
    return lines


def _set_aside(m: Mirror) -> list[str]:
    """What the admission rule removed, whole. No filter is ever silent."""
    lines = [
        "## What was set aside, and why\n",
        f"{m.excluded_total:,} of {m.definitions_seen:,} definitions were not carried "
        "forward as words. Each rule is stated with the evidence that motivated it, "
        "and everything it removed is listed — a filter that cannot be inspected is a "
        "filter that has to be trusted.\n",
        "These are filtered **here** and not at ingest on purpose. The glossary and "
        "naming lanes are verified against ground truth as the extractor stands; "
        "tightening it is a separate change with its own before-and-after, and this "
        "section is where the evidence for making it accumulates.\n",
    ]
    for rule in EXCLUSIONS:
        removed = m.excluded.get(rule.key, [])
        if not removed:
            continue
        lines += [
            f"### {rule.label} — {len(removed):,}\n",
            f"{rule.why}\n",
            *(f"- `{_esc(x)}`" for x in removed),
            "",
        ]
    unused = [r for r in EXCLUSIONS if not m.excluded.get(r.key)]
    if unused:
        lines += [
            "The remaining rules removed nothing from this corpus, and are listed so "
            "the whole admission rule can be read in one place: "
            + ", ".join(f"**{r.label}**" for r in unused) + ".\n",
        ]
    lines.append(
        f"The word cap is {MAX_TERM_WORDS}. It is a threshold, printed so it can be "
        "argued with: on this corpus every entry of four words or more is a sentence, "
        "and the two- and three-word entries include `Audit event`, `Decision graph` "
        "and `Society of Mensores`. A second corpus may move it.\n"
    )
    return lines


def _reproducing(m: Mirror) -> list[str]:
    """Rule 13. Every count above is re-runnable, and the queries are the proof."""
    example = next(
        (t.term for t in m.terms if t.term.lower() == "tabularium"),
        m.terms[0].term if m.terms else "tabularium",
    )
    return [
        "## Reproducing this\n",
        "Every count on this page comes from one of these. The definition side lives "
        "in `docs.db`, the code side in `graph.db`; `--docs` attaches the first to the "
        "second, which is what makes a claim spanning both checkable at all.\n",
        "**Every word the documentation defines:**\n",
        "```bash",
        'dunneflow query output/<program> --docs --sql "<the SQL below>"',
        "```\n",
        "```sql",
        DEFINED_TERMS_SQL,
        "```\n",
        "**Every file the program names, and how often:**\n",
        "```sql",
        ARTEFACT_NAMES_SQL,
        "```\n",
        f"**Where the code uses one term** (shown for `{_esc(example)}`; the same "
        "shape answers for any row above):\n",
        "```sql",
        term_evidence_sql(example),
        "```\n",
        "The Spoken band is the one surface no SQL above covers: it is a "
        "word-boundary search over comments and docstrings, run only for terms that "
        "nothing is named for, because a term already Named or Borne cannot be moved "
        "by a mention. Rule 9 holds in both directions — prose is read here and "
        "nowhere a code-shaped detector can see it.\n",
        "```sql",
        "SELECT 'comment' surface, text, routine_id FROM comments\n"
        " WHERE lower(text) LIKE '%<term>%'\n"
        "UNION ALL\n"
        "SELECT 'docstring', doc, path FROM files\n"
        " WHERE lower(doc) LIKE '%<term>%'",
        "```\n",
        "*(The LIKE is the pre-filter; the report confirms each hit with a "
        "word-boundary match, so `Gate` does not match `aggregate`.)*\n",
    ]


__all__ = ["render_mirror", "BY_EXCLUSION"]
