"""What was built without a plan, and what was planned without being built.

The join itself is cheap. What this page has to get right is the register: a governance
id is not traced or untraced, it has a standing, and a report that partitions 1,270 ids
into two piles would be lying about six of the seven things it found.

So the spectrum leads, every band states what would make placing an id there wrong, and
every id is listed with the evidence that placed it -- the documents that are about it,
the symbols it names that exist. A reader who disagrees with a placement can see exactly
what to disagree with, which is the whole design.

Nothing here is bounded. The code sites behind each id are already listed whole in
`06-governance.md` and are pointed at rather than reprinted; everything else is here.
"""

from __future__ import annotations

from pathlib import Path

from ..docstore import DocStore
from ..resolve.traceability import (
    CODE_IDS_SQL,
    DOC_IDS_SQL,
    STATES,
    STRONG_LANDED_SYMBOLS,
    Traceability,
    TracedId,
    measure,
)
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


def _slug(key: str) -> str:
    return key.lower().replace("_", "-")


def _docs_cell(t: TracedId) -> str:
    """The documents that are *about* an id, in full.

    Subject documents are few by construction -- something has to name the id in a
    title or a top-level heading -- so listing them costs nothing and is the single
    most useful cell on the page. Mentions are the unbounded set (`CP-1` is named in
    553 documents) and are given as a count with the query that lists them.
    """
    if not t.subjects:
        return "—"
    return "<br>".join(
        f"`{_esc(s.doc)}`" + ("" if s.stated else " *(inferred)*")
        for s in t.subjects
    )


def render_traceability(
    store: Store,
    docs: DocStore | None,
    out: Path,
    program: str,
    stamp: str,
) -> Path:
    """Write `12-traceability.md`. Returns the path."""
    t = measure(store, docs)
    lines = [
        f"# {program} — Traceability\n\n*Generated {stamp} by DunneFlow.*\n",
        "Governance ids appear in two places: in comments and docstrings beside the "
        "code that implements them, and in the prose that planned them. Joining the "
        "two answers the question neither answers alone — **what was built without a "
        "plan, and what was planned without being built?**\n",
        "It needs no model. The join is a normalisation rule and an `ATTACH DATABASE`, "
        "and every number below ships the query that produced it.\n",
    ]

    if not t.had_docs:
        lines += _no_documentation(t)
        return _write(out, lines)

    lines += _what_was_joined(t)
    lines += _inference(t)
    lines += _spectrum(t)
    lines += _headlines(t)
    lines += _method(t)
    lines += _bands(t)
    lines += _reproducing(t)
    return _write(out, lines)


def _write(out: Path, lines: list[str]) -> Path:
    path = out / "12-traceability.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #


def _no_documentation(t: Traceability) -> list[str]:
    """Documentation is never a prerequisite, and its absence is never drift.

    Reporting "517 ids built without a plan" when no corpus was read would be a
    fabricated finding, so the count is stated as what it is: a code-side inventory.
    """
    n = len(t.ids)
    return [
        "## No documentation was read\n",
        "This run scanned source only (`--no-docs`, or a corpus with no documents in "
        "it), so there is no second half to join against. **Nothing here is a finding "
        f"about drift.** The {n:,} governance id{'s' if n != 1 else ''} below "
        f"{'were' if n != 1 else 'was'} found in code and have not been looked for "
        "anywhere else.\n",
        "Point `analyze` at a documentation root to get the join:\n",
        "```bash\ndunneflow analyze <path> --name <program> --docs <docs-root>\n```\n",
        "| Id | Kinds | Code sites |",
        "|---|---|---:|",
        *(
            f"| `{_esc(x.id)}` | {_esc(', '.join(x.kinds))} | {len(x.code):,} |"
            for x in sorted(t.ids, key=lambda i: (i.prefix, i.id))
        ),
        "",
    ]


def _what_was_joined(t: Traceability) -> list[str]:
    lines = [
        "## What was joined\n",
        "| Input | Count |",
        "|---|---:|",
        f"| Documents scanned | {t.documents_scanned:,} |",
        f"| Copies of another document, counted once | {t.duplicates_ignored:,} |",
        f"| Governance ids cited in code | {t.code_annotations:,} |",
        f"| Governance ids named in prose | {t.doc_annotations:,} |",
        f"| **Distinct ids after normalising** | **{len(t.ids):,}** |",
        "",
    ]
    if t.merged_forms:
        lines += [
            f"Normalising separator and zero-padding merged "
            f"{len(t.merged_forms):,} id{'s' if len(t.merged_forms) != 1 else ''} that "
            "the corpus spells more than one way. Every spelling seen is kept:\n",
            "| Id | Spellings found |",
            "|---|---|",
            *(
                f"| `{_esc(k)}` | {' · '.join(f'`{_esc(f)}`' for f in forms)} |"
                for k, forms in t.merged_forms
            ),
            "",
        ]
    else:
        lines.append(
            "No id is spelled more than one way in this corpus, so normalising "
            "changed nothing here. It still runs: `ADR-0001` and `ADR 1` are one id "
            "in a corpus that writes both.\n"
        )
    return lines


def _inference(t: Traceability) -> list[str]:
    """What was composed rather than quoted, said before any count below is read.

    Rule 6, and rule 13's spirit. A quoted id proves itself with a line a reader can
    open; a composed one cannot prove itself at all, and must say so.
    """
    only = t.by_inference_only()
    if not t.inferred_annotations:
        return [
            "## Nothing here was inferred\n",
            "Every id below was read as written, from a line you can open. No "
            "`document_identity` rule in `detectors/annotations.yaml` matched anything "
            "in this corpus, so nothing was composed from a filename or from "
            "frontmatter.\n",
        ]
    return [
        "## What was read, and what was inferred\n",
        "Most ids here were **read as written** \u2014 the string is on a line and you "
        "can go and look at it. Some were **composed** from a document's own identity "
        "instead: `68-03-PLAN.md` declares itself as `phase: 68-front-door-extraction` "
        "and `plan: 03` in YAML frontmatter, and the string `Plan 68-03` appears "
        "nowhere in the corpus. Without composing it, the document is invisible and "
        "its work reads as unplanned. With it, unmarked, it would read as though "
        "someone had written the plan down. Neither is true, so the two never merge.\n",
        "| | Count |",
        "|---|---:|",
        f"| Ids written out somewhere in the corpus "
        f"| {sum(1 for x in t.ids if x.stated_anywhere):,} |",
        f"| Mentions composed from frontmatter or a filename "
        f"| {t.inferred_annotations:,} |",
        f"| **Ids whose entire documentary standing is composed** | **{len(only):,}** |",
        "",
        "The last row is the one to be sceptical of, and it is listed whole so the "
        "rest of the page can be read without it. These ids are marked *(inferred)* "
        "wherever they appear below.\n",
        "| Id | Composed from | Cited in code |",
        "|---|---|---:|",
        *(
            f"| `{_esc(x.id)}` "
            f"| {'<br>'.join(f'`{_esc(Path(s.doc).name)}`' for s in x.documents())} "
            f"| {len(x.code):,} |"
            for x in only
        ),
        "",
        "The convention that produced them is a rule in "
        "`detectors/annotations.yaml`, not a judgement in code \u2014 a project that "
        "names its plans differently edits a config file rather than this tool. It is "
        "an inference either way: a convention can be wrong, superseded, or simply not "
        "the one in force when a given file was written.\n",
    ]


def _spectrum(t: Traceability) -> list[str]:
    counts = t.counts()
    total = sum(counts.values()) or 1
    lines = [
        "## The spectrum\n",
        "An id is not traced or untraced. It has a standing, set by two things that "
        "can be observed: whether any document is *about* it — names it in a title or "
        "a top-level heading, rather than mentioning it in passing — and whether the "
        "code cites it.\n",
        "| Standing | Ids | Share | What it means |",
        "|---|---:|---:|---|",
    ]
    for s in STATES:
        n = counts[s.key]
        lines.append(
            f"| [{s.label}](#{_slug(s.key)}) | {n:,} | {n / total:.0%} | {s.meaning} |"
        )
    lines.append(f"| **Total** | **{total:,}** | | |")
    lines.append("")
    return lines


def _headlines(t: Traceability) -> list[str]:
    counts = t.counts()
    in_code = t.in_code()
    traced = t.traced()
    planned = counts["LIKELY_LANDED"] + counts["POSSIBLY_LANDED"] + counts["NO_TRACE_IN_CODE"]
    # **A share of nothing is not zero percent, it is not a number** -- and `analyze`
    # crashed here rather than saying so. A program that cites no governance id in any
    # comment is not exotic: it is every program that has not adopted this discipline, which
    # is most of them. Found by pointing the tool at a four-file fixture, which is the first
    # thing it has ever been given that had none; Mensores has 593 and could never reach it.
    #
    # Stated as an absence rather than filled with a plausible 0% (rule 49): "no ids are
    # cited in code" and "none of the ids cited in code are documented" are opposite
    # findings, and a bare 0% claims the second.
    # The division sits **inside** the guarded branch rather than behind a placeholder
    # computed above it. A `share = ... if in_code else "—"` was written first and its
    # fallback was read by nothing -- the empty branch below does not mention it -- so a
    # mutation putting `0%` back in that limb changed no output and survived. Rule 35 in
    # three lines of my own: not a weak guard and not a weak mutation, a dead value.
    built = (f"{in_code:,} ids are cited in code. {traced:,} of them "
             f"({traced / in_code:.0%}) are findable in the documentation; "
             f"**{counts['UNDOCUMENTED_WORK']:,} are not there at all**. That is the list "
             "worth reading first, and it is short enough to read."
             if in_code else
             "**No governance ids are cited in code at all.** Nothing here was built "
             "without a plan, because nothing here names a plan — which is a fact about "
             "this program's conventions rather than about its work.")
    return [
        "## The two findings\n",
        "**What was built without a plan.** " + built + "\n",
        "**What was planned without landing.** "
        f"{planned:,} ids are the subject of a document and are cited by no comment "
        "anywhere in the code. They are *not* all unbuilt — that is the part this tool "
        "cannot see. A plan can land perfectly and simply never be mentioned in a "
        "comment, and the absence looks identical. What can be measured is whether the "
        "code symbols each document names actually exist: "
        f"{counts['LIKELY_LANDED']:,} name several that do, "
        f"{counts['POSSIBLY_LANDED']:,} name one or two, and "
        f"{counts['NO_TRACE_IN_CODE']:,} name none.\n",
        f"The remaining {counts['PASSING_REFERENCE']:,} ids are named in prose, never "
        "written about, and never cited in code — mostly pointers at work that lives "
        "somewhere other than this program.\n",
    ]


def _method(t: Traceability) -> list[str]:
    return [
        "## How an id was placed\n",
        "Three rules, all deterministic, all arguable — which is why they are printed "
        "rather than described.\n",
        "**An id is a marker with a number in it.** `WARNING`, `TODO` and "
        "`Audit-locked` are markers too, but they name a category rather than a unit "
        "of work and cannot be traced to anything. Deriving the set this way rather "
        "than listing kinds by hand means a new rule in `detectors/annotations.yaml` "
        "is included here without a code edit, and cannot fall out of step with it.\n",
        "**A document is *about* an id when its title or one of its top two heading "
        "levels names it.** Deeper headings are structure inside a document, not its "
        "subject. This is the rule most likely to misplace something, and it "
        "misplaces in a known direction: a project that titles its plans by prose "
        "rather than by id will show as thinly traced throughout.\n",
        "**A symbol counts as evidence only if it is unique in the program.** Of "
        f"{t.total_symbols:,} names this program defines, {t.unique_symbols:,} "
        "identify exactly one routine, structure or table; the rest — `__init__`, "
        "`check`, `to_dict` — could never distinguish one plan from another, and are "
        "not counted. Python builtins are excluded on top of that: one id's entire "
        "claim to having landed was the word `list`.\n",
        "| Threshold | Value |",
        "|---|---:|",
        f"| Distinctive symbols for *likely* rather than *possibly* landed "
        f"| {STRONG_LANDED_SYMBOLS} |",
        f"| Symbol names in the program | {t.total_symbols:,} |",
        f"| Of those, unique enough to count as evidence | {t.unique_symbols:,} |",
        "",
        "### What none of this can see\n",
        "| Band | What would make a placement here wrong |",
        "|---|---|",
        *(f"| {s.label} | {s.blind_spot} |" for s in STATES),
        "",
        "And three that apply to every row: an id is matched on its normalised text, "
        "so two systems using one prefix would merge; the join proves a shared name, "
        "never that the code honours the plan; and a document outside the scanned "
        "corpus is invisible rather than absent.\n",
    ]


def _bands(t: Traceability) -> list[str]:
    """Every id, in its band, with its evidence. Nothing is elided."""
    grouped = t.by_state()
    lines: list[str] = ["## Every id\n"]
    lines.append(
        "Complete. Code sites are counted here and listed in full in "
        "`06-governance.md`, which is where they belong; nothing else is abbreviated. "
        "Where an id is named in more documents than are shown, it is because only "
        "the documents *about* it are listed — the mention count says how many others "
        "there are, and the query at the foot of this page lists them.\n"
    )
    for s in STATES:
        band = grouped[s.key]
        lines.append(f"### {s.label} ({len(band):,}) {{#{_slug(s.key)}}}\n")
        lines.append(f"{s.meaning}\n")
        lines.append(f"*Would be wrong if:* {s.blind_spot}\n")
        if not band:
            lines.append("*None.*\n")
            continue
        lines += _band_table(s.key, band)
    return lines


def _band_table(
    key: str, band: list[TracedId]
) -> list[str]:
    landed_band = key in ("LIKELY_LANDED", "POSSIBLY_LANDED", "NO_TRACE_IN_CODE")
    lines: list[str] = []
    if key == "UNDOCUMENTED_WORK":
        lines.append(_undocumented_note(band))
        lines.append(
            "| Id | Vocabulary | Cited from | Code sites | Where it is cited |"
        )
        lines.append("|---|---|---|---:|---|")
        for x in band:
            where = "<br>".join(
                f"`{_esc(c.owner)}` — `{_esc(c.file)}:{c.line}`"
                for c in x.code
            )
            family = (
                f"`{x.prefix}-*` is used in the documentation"
                if x.family_in_docs
                else f"**`{x.prefix}-*` appears nowhere in it**"
            )
            files = {c.file for c in x.code}
            routines = {c.owner for c in x.code}
            spread = (
                f"{len(routines)} routine{'s' if len(routines) != 1 else ''}, "
                f"{len(files)} file{'s' if len(files) != 1 else ''}"
            )
            lines.append(
                f"| `{_esc(x.id)}` | {family} | {spread} "
                f"| {len(x.code):,} | {where or '—'} |"
            )
    elif landed_band:
        lines.append(
            "| Id | Documents about it | Symbols named | Distinctive, and present |"
        )
        lines.append("|---|---|---:|---|")
        for x in band:
            ev = " · ".join(f"`{_esc(n)}`" for n in x.landed) or "—"
            lines.append(
                f"| `{_esc(x.id)}` | {_docs_cell(x)} | {x.named:,} | {ev} |"
            )
    else:
        lines.append("| Id | Kinds | Code sites | Documents about it | Also named in |")
        lines.append("|---|---|---:|---|---:|")
        for x in band:
            mentions = f"{len(x.mentions):,} more" if x.mentions else "—"
            lines.append(
                f"| `{_esc(x.id)}` | {_esc(', '.join(x.kinds))} | {len(x.code):,} "
                f"| {_docs_cell(x)} | {mentions} |"
            )
    lines.append("")
    return lines


def _undocumented_note(band: list[TracedId]) -> str:
    """Two facts that separate a missing plan from a vocabulary that never had one.

    Not a filter. The general TICKET rule catches anything shaped like an id, so this
    band mixes genuine untracked work with domain vocabularies -- `DRAFT-05` is a
    finding code the EARS validator emits, `AR-7` an assessor role named in a
    docstring. Both are real and neither will ever have a plan. Which is which is the
    reader's call, so the evidence is printed rather than acted on.
    """
    unknown = [x for x in band if not x.family_in_docs]
    narrow = [x for x in band if len({c.owner for c in x.code}) == 1]
    parts = [
        "Two columns are here to be judged rather than trusted. **Vocabulary** says "
        "whether the documentation uses this id's prefix anywhere at all: "
        f"{len(unknown):,} of these {len(band):,} ids belong to a family the corpus "
        "has never once written down, which usually means it was never governance — "
        "an emitted finding code, a role name, a layer number. **Cited from** says how "
        f"far the id spreads; {len(narrow):,} are cited from a single routine, which "
        "is the shape of a code table rather than of work done against a plan.",
        "Neither is applied as a filter. An id that fails both can still be real "
        "untracked work, and an id that passes both can still be a lookup table.",
    ]
    return "\n\n".join(parts) + "\n"


def _reproducing(t: Traceability) -> list[str]:
    return [
        "## Reproducing these numbers\n",
        "A claim whose query returns something else is worse than a claim with no "
        "query, so these are the ones this page was built from. `--docs` attaches the "
        "document store as `docs`.\n",
        "The governance ids this program's code cites:\n",
        f"```bash\ndunneflow query <path> --sql \"{CODE_IDS_SQL}\"\n```\n",
        "The governance ids its documentation names, copies excluded:\n",
        f"```bash\ndunneflow query <path> --docs --sql \\\n  \"{DOC_IDS_SQL}\"\n```\n",
        "Every document naming one id — the mention lists this page counts rather "
        "than prints:\n",
        "```bash\ndunneflow query <path> --docs --sql \\\n"
        "  \"SELECT a.doc, a.line, a.text FROM docs.doc_annotations a\n"
        "     JOIN docs.documents d ON d.path = a.doc\n"
        "    WHERE d.duplicate_of = '' AND a.value = 'ADR-0001'\"\n```\n",
        f"Read against {t.documents_scanned:,} documents and "
        f"{t.code_annotations:,} code annotations.\n",
    ]
