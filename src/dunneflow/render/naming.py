"""The naming standard: what the project says, and what the code does.

Two lanes, because there are two kinds of naming rule and rendering them the same way
makes each read worse.

**Form** -- where the underscore goes, which case, what suffix. Mechanical, countable,
checkable against the graph. It wants a table, and every table carries the query that
produced it and every exception it found.

**Vocabulary** -- what a name may be drawn from or must mean: Latin only, always the
binomial, a route name carries its functionality. Semantic, usually not mechanically
checkable. It wants a paragraph, quoted whole, with the file and line it came from.

Above both sits the one page a new developer would actually be handed. Every line on it
carries its provenance and points down into the section that proves it -- rule 8:
abbreviate only where the complete content sits beside it.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..docstore import DocStore
from ..resolve import languages
from ..resolve.conformance import (
    CHECKED,
    NO_POPULATION,
    NOT_CHECKABLE,
    check_stated,
)
from ..resolve.naming import (
    Convention,
    NamingMeasurement,
    measure,
)
from ..resolve.stated import StatedRule, checkable_sentence, stated_rules
from ..store import Store
from .page import Stamp, header

HANDBOOK_LINES = 12


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


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


def _first_sentence(text: str, limit: int = 160) -> str:
    """The opening of a rule, for the one-page summary.

    Abbreviation is allowed here and only here, because the rule is quoted whole a few
    hundred lines below and linked from this very line. A summary page that runs to
    three screens is not a summary page.
    """
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    stop = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(" — "))
    return (cut[: stop + 1] if stop > 60 else cut.rsplit(" ", 1)[0]) + " …"


def _pct(holds: int, total: int) -> str:
    """Never round a near-miss up to a clean number.

    99.97% shown as 100% is the difference between "no exceptions" and "one exception",
    and the exception is the part worth reading.
    """
    if not total:
        return "—"
    if holds == total:
        return "100%"
    value = 100.0 * holds / total
    return f"{value:.2f}%" if value > 99.9 else f"{value:.1f}%"


def render_naming(store: Store, docs: DocStore | None, out_dir: Path,
                  program: str, stamp: Stamp,
                  standards: DocStore | None = None,
                  standards_note: str = "") -> Path:
    m = measure(store)
    stated = stated_rules(docs)
    lines: list[str] = [
        # **"as found", not "derived"**, and the difference is the Vocabulary lane. This
        # document carries two lanes and only one of them is derived: Form is counted off
        # the code, Vocabulary is *quoted* from the project's own documents. Titling the
        # whole thing "derived" would relabel a quotation as an inference, which is the one
        # thing the four provenance tiers exist to prevent. "As found" is true of both --
        # found in the code, found in the documents -- and claims of neither that anybody
        # required it. The dashboard's page *is* measured-only, and is titled "Derived
        # naming standard" for that reason.
        header(program, "Naming standard, as found", stamp),
        "**Nothing here was required of this program.** This is the standard the code and "
        "its documents were found to keep, not one anybody imposed and not one DunneFlow "
        "checked them against — a standard of your own cannot yet be imported, so nothing "
        "on this page is a comparison. A convention holding every time means the code is "
        "consistent; it does not mean the code is right.\n",
        "Two kinds of rule live here and they are kept apart. **Form** is how a name is "
        "spelled — case, underscores, prefixes and suffixes — and it is **derived**, "
        "counted off the code itself. **Vocabulary** is what a name may be drawn from or "
        "must mean, and it is **quoted** from documentation, because no query can check "
        "it. Derived and quoted are different claims and are never blended.\n",
        "Nothing on this page is guessed. A `STATED` line is a quotation with a file and "
        "a line. A `MEASURED` line is a count with the query that produced it and every "
        "exception it found. If a model has been run, its contributions appear as "
        "`CITED` or `INFERRED` and never as either of these.\n",
    ]

    lines.append("## The standard, in one page\n")
    lines.append(
        "The short version, for someone joining. Every line says where it came from and "
        "links to the evidence below.\n"
    )
    if not stated and not m.conventions:
        lines.append("*Nothing stated, and nothing measurable. See “What was scanned”.*\n")
    n = 0
    for rule in stated:
        n += 1
        src = f"{rule.doc}:{rule.line}"
        lines.append(f"{n}. {_esc(_first_sentence(rule.text))}  \n"
                     f"    `STATED · {rule.lane.lower()} · {src}` "
                     f"→ [the rule in full](#{_slug(src)})\n")
    for conv in m.conventions[:HANDBOOK_LINES]:
        n += 1
        exc = f" · {len(conv.exceptions)} exception{'s' if len(conv.exceptions) != 1 else ''}" \
            if conv.exceptions else ""
        lines.append(f"{n}. {_esc(conv.claim)}  \n"
                     f"    `MEASURED · {conv.holds:,}/{conv.total:,} · "
                     f"{_pct(conv.holds, conv.total)}{exc}` "
                     f"→ [evidence](#{_slug(conv.claim)})\n")
    if len(m.conventions) > HANDBOOK_LINES:
        lines.append(
            f"\n{len(m.conventions) - HANDBOOK_LINES} further measured conventions are "
            f"listed in full under **Form**; none is omitted.\n"
        )

    lines.extend(_form_section(m, stated))
    lines.extend(_vocabulary_section(stated))
    lines.extend(_checked_section(store, docs, standards, standards_note))
    lines.extend(_gaps_section(m))
    lines.extend(_scanned_section(m, docs, stated))

    path = out_dir / "11-naming.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# `StatedRule`, the query behind it and the `checkable` sentence all used to live here,
# because this was the only reader. The dashboard is the second and the tests are the
# third, so they moved to `resolve/stated.py` where all three pass (rule 51). Nothing about
# them changed in the move except that `scope` and `pattern` now travel too -- this file
# does not print them, and the page that does would otherwise have queried the table itself.


def _stated_form(stated: list[StatedRule]) -> list[str]:
    """The Form lane's *stated* half: rules a document gives, not counts off the code.

    **Its own block because every one of these needs an anchor to land on.** The handbook
    at the top of this page links each stated rule to `[the rule in full](#slug)`, and only
    the Vocabulary section ever emitted a heading to slug — so the day a FORM rule first
    existed, that link went nowhere. Seven dead links, from a change that never touched this
    file. It is the `where_` defect's shape: a link correct in every respect except that
    nothing is at the other end of it.

    Stated and measured sit under one heading on purpose. This section is *Form*, and both
    halves answer the same question about spelling — one from a document, one from the code.
    Comparing them is not built; putting them beside each other is the beginning of it.

    **No root, deliberately.** `_form_section` is handed the *source* root and these rules
    come out of *documents*, which live above it — the mix-up this file records paying for
    once already, where every citation printed as an absolute path halfway across the disk.
    A path is not needed here, so the parameter that could be the wrong one is not taken.
    """
    form = [r for r in stated if r.lane == "FORM"]
    if not form:
        return []
    lines = [f"\n### Stated — {len(form)} rule{'s' if len(form) != 1 else ''} "
             "a document gives\n",
             "Quoted from the project's own documentation rather than counted. What "
             "happened when each was measured against the population its own document "
             "says it governs is in **Checked** below.\n"]
    for r in form:
        src = f"{r.doc}:{r.line}"
        lines.append(f"\n#### {src}\n")
        lines.append(f"> {_esc(r.text)}\n")
        heading = _esc(r.heading) or "—"
        where = f"*Stated under “{heading}”.*"
        lines.append(f"{where} {checkable_sentence(r)}\n")
    return lines


def _form_section(m: NamingMeasurement, stated: list[StatedRule],
) -> list[str]:
    lines = ["\n## Form — derived from the code\n",
             "**Not a standard anyone wrote: a standard the code was found to keep.** "
             "How names are spelled, counted over the code itself. Each convention "
             "carries the population it was counted over, the query that reproduces it, "
             "and every exception — never a sample. The exceptions are the point: a "
             "convention holding in 372 of 375 cases is mildly interesting, and the "
             "three that break it are the finding.\n"]
    lines.extend(_stated_form(stated))
    if not m.conventions:
        lines.append("\n### Measured — nothing reaches the thresholds\n")
        lines.append("*No convention in this program reaches the thresholds below.*\n")
        return lines

    lines.append(f"\n### Measured — {len(m.conventions)} convention"
                 f"{'s' if len(m.conventions) != 1 else ''} counted off the code\n")
    lines.append("| Convention | Population | Holds | Rate | Exceptions |")
    lines.append("|---|---|---:|---:|---:|")
    for c in m.conventions:
        lines.append(
            f"| [{_esc(c.claim)}](#{_slug(c.claim)}) | {_esc(c.population)} | "
            f"{c.holds:,}/{c.total:,} | {_pct(c.holds, c.total)} | {len(c.exceptions):,} |"
        )
    lines.append("")

    for c in m.conventions:
        lines.extend(_convention_detail(c))
    return lines


def _convention_detail(c: Convention) -> list[str]:
    lines = [f"\n### {c.claim}\n",
             f"Holds in **{c.holds:,} of {c.total:,}** {c.population} "
             f"({_pct(c.holds, c.total)}).\n"]
    if c.note:
        lines.append(f"{c.note}\n")
    lines.append("Reproduce with `dunneflow query <path> --sql \"...\"`:\n")
    lines.append(f"```sql\n{c.sql}\n```\n")
    if not c.exceptions:
        lines.append("No exceptions.\n")
        return lines
    plural = "exception" if len(c.exceptions) == 1 else "exceptions"
    lines.append(f"**The {len(c.exceptions):,} {plural}**, in full:\n")
    lines.append("| Name | Where |")
    lines.append("|---|---|")
    for e in c.exceptions:
        lines.append(f"| `{_esc(e.name)}` | {_esc(e.where)} |")
    lines.append("")
    return lines


def _vocabulary_section(stated: list[StatedRule]) -> list[str]:
    vocab = [r for r in stated if r.lane == "VOCABULARY"]
    lines = ["\n## Vocabulary — quoted, not derived\n",
             "**The one lane on this page somebody actually wrote.** "
             "What a name may be drawn from, or must mean. Quoted whole from the "
             "project's own documentation, because compressing a rule of this kind into "
             "a table cell loses it. Most of these cannot be checked by any query, and "
             "each one says so rather than being quietly left out.\n"]
    if not vocab:
        lines.append(
            "*No documentation in this program states a vocabulary rule.* That is a "
            "finding, not an absence of one: the conventions under **Form** are what the "
            "code does, and nothing records what it was supposed to do. A model pass "
            "(`dunneflow infer`) can read prose that states rules in a shape this "
            "scanner does not recognise.\n"
        )
        return lines
    for r in vocab:
        src = f"{r.doc}:{r.line}"
        lines.append(f"\n#### {src}\n")
        lines.append(f"> {_esc(r.text)}\n")
        heading = _esc(r.heading) or "—"
        lines.append(f"*Stated under “{heading}”.* {checkable_sentence(r)}\n")
    return lines


def _checked_section(store: Store, docs: DocStore | None,
                     standards: DocStore | None,
                     standards_note: str = "") -> list[str]:
    """Reality against intent: each stated rule over the population it governs.

    **The one section on this page that is a comparison**, and it says so in its first line.
    Everything above either counts without quoting or quotes without counting, deliberately;
    putting a number beside a quotation is safe only where the reader is told that is what
    is happening.

    Three verdicts get three sub-headings rather than one table with a column, because a
    table sorts and a reader skimming a sorted column will read *"not checkable"* as a
    milder *"fails"*. They are not the same kind of thing at all.
    """
    checks = check_stated(store, docs, standards)
    if not checks:
        return [f"\n## Checked — the stated rules, measured\n\n{standards_note}\n"] \
            if standards_note else []
    lines = ["\n## Checked — the stated rules, measured\n",
             *([standards_note + "\n"] if standards_note else []),
             "**The comparison, and the only section here that is one.** Each rule above, "
             "measured over the population its own document says it governs — never over "
             "whatever this tool happens to hold. A rule scoped at documentation is not "
             "checked against the code, and a rule this map cannot answer says so rather "
             "than passing quietly.\n"]

    for verdict, title, blurb in (
        (CHECKED, "Checked",
         "Measured. Every exception is listed, because the exceptions are the product."),
        (NO_POPULATION, "Nothing here to check",
         "Well formed, and this map holds nothing it governs. A fact about the map."),
        (NOT_CHECKABLE, "Not checkable by this tool",
         "DunneFlow tests case styles. A template or a separator is quoted back rather "
         "than guessed at — a guess would read exactly like a measurement."),
    ):
        rows = [c for c in checks if c.verdict == verdict]
        if not rows:
            continue
        lines.append(f"\n### {title} — {len(rows)}\n")
        lines.append(f"{blurb}\n")
        for c in rows:
            name = (f"{c.rule.scope} · {c.rule.pattern}"
                    if c.rule.scope and c.rule.pattern
                    else (c.rule.scope or c.rule.pattern or c.rule.heading or "a stated rule"))
            # The language belongs in the heading, not only in the sentence beneath it. One
            # rule measured across two languages is two results, and two `#### functions ·
            # snake_case` headings a screen apart read as the page saying the same thing
            # twice rather than as the two answers it has.
            if c.lang:
                name = f"{name} — {languages.display(c.lang)}"
            lines.append(f"\n#### {_esc(name)}\n")
            lines.append(f"> {_esc(c.rule.text)}\n")
            lines.append(f"*From {_esc(c.rule.doc)}:{c.rule.line} — {_esc(c.source)}.*\n")
            if c.blind_spot:
                lines.append(f"*What would make this a false alarm: {_esc(c.blind_spot)}.*\n")
            if c.verdict != CHECKED:
                lines.append(f"{_esc(c.reason)}.\n")
                continue
            scoped = (f", scoped by `{_esc(c.scoped_by)}` as its own document declares"
                      if c.scoped_by else "")
            lines.append(f"Holds in **{c.holds:,} of {c.total:,}** {_esc(c.population)}"
                         f"{scoped} ({_pct(c.holds, c.total)}).\n")
            if not c.exceptions:
                lines.append("No exceptions.\n")
                continue
            plural = "exception" if len(c.exceptions) == 1 else "exceptions"
            lines.append(f"**The {len(c.exceptions):,} {plural}**, in full:\n")
            lines.append("| Name | Where |")
            lines.append("|---|---|")
            for e in c.exceptions:
                lines.append(f"| `{_esc(e.name)}` | {_esc(e.where)} |")
            lines.append("")
    return lines


def _gaps_section(m: NamingMeasurement) -> list[str]:
    lines = ["\n## Gaps — where there is no convention\n"]
    if not m.gaps:
        lines.append("Every population large enough to measure has a dominant "
                     "convention.\n")
    else:
        lines.append("Populations with no dominant convention. Nothing is being hidden "
                     "here — these are counted and reported precisely because a reader "
                     "who sees only the conventions would take the silence for "
                     "consistency.\n")
        lines.append("| Population | Counted | How it splits |")
        lines.append("|---|---:|---|")
        for g in m.gaps:
            spread = ", ".join(f"{style} {count:,}" for style, count in g.spread)
            lines.append(f"| {_esc(g.population)} | {g.total:,} | {_esc(spread)} |")
        lines.append("")
    return lines


def _scanned_section(m: NamingMeasurement, docs: DocStore | None,
                     stated: list[StatedRule]) -> list[str]:
    lines = ["\n## What was scanned, and where the lines were drawn\n"]
    if docs is not None:
        c = docs.counts()
        lines.append(
            f"{c['documents']:,} documents were read, of which {c['duplicates']:,} are "
            f"byte-identical copies of another and are counted once. "
            f"{len(stated)} stated naming rule"
            f"{'s' if len(stated) != 1 else ''} survived.\n"
        )
    else:
        lines.append("No documentation was read, so nothing here is stated — only "
                     "measured.\n")
    lines.append("A measured convention is reported only above these thresholds. They "
                 "are printed so they can be disagreed with:\n")
    lines.append("| Threshold | Value |")
    lines.append("|---|---:|")
    for name, value in m.thresholds.items():
        shown = f"{value:.0%}" if value < 1 else f"{value:g}"
        lines.append(f"| {name} | {shown} |")
    lines.append(
        "\nAffix conventions carry one further test: the count has to be unlikely "
        "enough that coincidence does not explain it, corrected for the number of "
        "affixes tried. Without it, “a class ending in `Provenance` is a dataclass, 7 "
        "of 7” passes every other check and means nothing, because two classes in five "
        "are dataclasses anyway.\n"
    )
    return lines
