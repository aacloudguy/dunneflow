"""How every reader must spell a call expression — the contract, written down at last.

`detectors/python.yaml`'s header has said since it was written that rules match *"the
dotted form of a call expression"*. That normalisation lives in
`extractors/python/extract.py:dotted_name`, and it is **the real interface between any
extractor and the rules**: every `exact`, `prefix`, `method` and `contains` in every YAML
file is matched against its output. A plugin that spells expressions differently does not
fail — it makes every rule miss, so the map comes back with no boundaries, no ways in and
no CLI, looking exactly like a program that has none.

Until this file, that interface was undocumented, unversioned and known only to the one
extractor that implemented it.

**The function itself does not live here, and cannot.** It takes an `ast.AST`; a
TypeScript reader has a TypeScript AST on the far side of a pipe and nothing to hand it.
What is shared is the **contract and its fixtures** — `tests/fixtures/dotted/cases.json`,
run against whichever reader claims a language, in this process or over the wire, through
that reader's *ordinary* `extract` (rule 51: what is tested is exactly what runs).

## The contract

1. **A source-order identifier chain, dot-joined.** `a.b.c()` → `a.b.c`.
2. **A call in the middle folds to its callee.** `Path(p).read_text()` →
   `Path.read_text`. Without this, the extremely common habit of calling a method straight
   off a constructor is invisible to every rule — and reading a file that way is one of
   the commonest boundary touches there is. It folds repeatedly: `a.b(1).c(2).d()` →
   `a.b.c.d`.
3. **No name at the root gives `""`, and `""` is never matched against a rule.** A
   subscript, a literal, a call on something anonymous. *Anywhere* in the chain, not only
   at its root: `reg.handlers['x'].run()` is `""`, because the chain cannot be named
   without deciding what `handlers['x']` is, and deciding that is resolution.
4. **No resolution and no alias expansion.** `import numpy as np` then `np.array(...)` is
   `np.array` and never `numpy.array`. The rules match the **written** library prefix
   (rule 5), so a reader that helpfully resolved the name would silently stop matching
   every rule written against the spelling people actually use.
5. **Nullability is not identity.** `a?.b!.c()` → `a.b.c`.
6. **Type arguments are not part of the name.** `foo<T>()` → `foo`.
7. **`new Foo()` → `Foo`, and the construction is recorded separately.** `new
   WebSocket(url)` and `WebSocket(url)` are two facts and must not become one (rule 30).
   **This clause is not implemented.** It needs a `CallSite.is_construction`, which is a
   schema change for a language that does not exist yet — a field nothing sets is a field
   nothing can be trusted to set (rule 35). Chunk 9 adds it with the reader that fills it.
8. **The receiver word is written as written.** `self.x`, `this.x`. Each language declares
   its own in `receiver_words`, and its resolver reads it from there.

Rules 5, 6 and 7 have nothing to say about Python, and the runner **names them as
unexercised** rather than counting them passed (design rule 1): a conformance report that
says *8 of 8* about a language with no syntax for three of them is a report that means
nothing.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..runtime import resource_root
from .contract import IngestPlugin

# Beside the tests rather than beside this module, because it is a fixture and the suite is
# what mostly runs it. **Through `resource_root()` and never `Path(__file__)`**: a module
# imported out of a PyInstaller archive has a `__file__` naming a path that does not exist,
# so the spelled-out form is right in a checkout and quietly wrong in the application —
# which is the whole of why `runtime.py` is a module. A frozen build ships no tests, and
# `load()` says so rather than reporting that nothing failed (rule 49).
CASES = resource_root().parents[1] / "tests" / "fixtures" / "dotted" / "cases.json"


class FixtureMissing(RuntimeError):
    """The conformance cases are not on this machine.

    Raised rather than answered with an empty run, because *no cases* and *every case
    passed* are the same exit code and opposite facts. A frozen build ships no tests, and
    telling somebody their plugin conforms on the strength of nothing is worse than saying
    the fixture is not here.
    """


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    rule: int
    expect: str
    why: str = ""
    # One snippet per language. A language with no snippet is not a failure — it is a rule
    # that language has no syntax for, and the report says so.
    source: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class Result:
    case: Case
    got: list[str] = field(default_factory=list)
    skipped: bool = False
    error: str = ""

    @property
    def passed(self) -> bool:
        if self.skipped:
            return True
        if self.error:
            return False
        # `expect: ""` is rule 3 — the chain has no name, so the extractor records no call
        # at all. Asking for the absence is the only way to state it.
        return not self.got if self.expect_nothing else self.case.expect in self.got

    @property
    def expect_nothing(self) -> bool:
        return self.case.expect == ""


def load(path: Path | None = None) -> list[Case]:
    where = path or CASES
    if not where.exists():
        raise FixtureMissing(
            f"the dotted-name conformance cases are not at {where}. They live in the "
            f"source tree beside the tests, so a frozen build has no copy — run "
            f"`dunneflow ingest-conform` from a checkout."
        )
    raw = json.loads(where.read_text(encoding="utf-8"))
    return [
        Case(id=str(c["id"]), rule=int(c["rule"]), expect=str(c["expect"]),
             why=str(c.get("why", "")), source=dict(c.get("source", {})))
        for c in raw["cases"]
    ]


def run(plugin: IngestPlugin, lang: str, cases: Sequence[Case] | None = None) -> list[Result]:
    """Put every case through this reader's **ordinary** extract, and report.

    Each snippet becomes a real file of the language's suffix in a temporary tree, and the
    reader is opened on it and asked for it exactly as a run would. No conformance frame,
    no back door: a protocol surface that exists only to be tested proves that surface and
    not the one the map is built from.
    """
    cases = cases or load()
    suffix = sorted(plugin.manifest.discovery.suffixes)[0]
    out: list[Result] = []
    with tempfile.TemporaryDirectory(prefix="dunneflow-conform-") as td:
        root = Path(td)
        wanted: list[tuple[Case, Path]] = []
        for case in cases:
            snippet = case.source.get(lang)
            if snippet is None:
                out.append(Result(case=case, skipped=True))
                continue
            path = root / f"{case.id}{suffix}"
            path.write_text(snippet, encoding="utf-8")
            wanted.append((case, path))

        if wanted:
            paths = [p for _, p in wanted]
            plugin.open(root, paths)
            try:
                facts = {f.path: f for f in plugin.extract(paths, root)}
            finally:
                plugin.close()
            for case, path in wanted:
                ff = facts.get(path.name)
                if ff is None:
                    out.append(Result(case=case, error="the reader returned nothing"))
                elif ff.errors:
                    out.append(Result(case=case, error="; ".join(ff.errors)))
                else:
                    out.append(Result(case=case, got=[c.callee_expr for c in ff.calls]))
    return sorted(out, key=lambda r: (r.case.rule, r.case.id))


def report(results: Sequence[Result], lang: str) -> list[str]:
    """The run as lines a person reads. **Unexercised is its own answer**, never a pass.

    A conformance report saying *8 of 8* about a language with no syntax for three of the
    rules is a report that means nothing, so the skipped ones are counted and named
    separately (design rule 1 and rule 32).
    """
    lines: list[str] = []
    ran = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in ran if not r.passed]

    for r in results:
        if r.skipped:
            mark, said = "–", f"{lang} has no syntax for rule {r.case.rule}"
        elif r.passed:
            mark, said = "✓", ("no call recorded, as required"
                               if r.expect_nothing else r.case.expect)
        else:
            mark = "✗"
            said = r.error or f"wanted {r.case.expect!r}, got {r.got!r}"
        lines.append(f"  {mark} rule {r.case.rule}  {r.case.id:22} {said}")

    lines.append("")
    lines.append(
        f"{len(ran) - len(failed)} of {len(ran)} exercised case(s) pass"
        + (f", {len(skipped)} not exercised by {lang}" if skipped else "")
        + "."
    )
    if skipped:
        rules = sorted({r.case.rule for r in skipped})
        lines.append(
            f"Rules {', '.join(str(x) for x in rules)} are not exercised here and are "
            f"**not** counted as passing: a rule this language cannot express is a rule "
            f"this run says nothing about."
        )
    return lines
