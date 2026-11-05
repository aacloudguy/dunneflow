"""How long an analysis will take, said before it starts, so the reader can decide.

Unreal's `Engine/Source/Runtime` is 18,263 files: under the 20,000-file size gate, so it
started without a word and took 2 h 19 m to extract and another hour after that. Nothing
was wrong with it -- the tree is that big -- and what was wrong was that nobody was asked.
The maintainer's rule (2026-11-03): *if it takes time, alert the user and let them choose.*

**An estimate is a range and a reason, never a number.** The same Runtime run has been
measured at 8 m 54 s and at 45 m 42 s on the same machine (PERFORMANCE.md, the external
volume), so a single figure would be a promise this tool cannot keep. What it can say is
what it is based on:

- **this program's own last run**, when there was one: its sidecar (`runstate`) records the
  phases it took and the files it read, and the next run is scaled from those;
- **otherwise, the measured rates per language** below, each sourced to the PERFORMANCE.md
  row it came from, scaled by the machine's CPU count against the 8 they were taken on.

The low end assumes every file's facts are still in a graph this version of the tool can
read and nothing has changed; the high end assumes every file is read. The run itself decides
which, by hashing, and the gate cannot know that without doing the extraction's first half --
so it says both. **The cache is the graph's `files` table, not `source.db`**, which holds
bodies and skips no reading: Runtime's graph went stale with `source.db` intact and the next
run read all 18,263 files for 2 h 53 m. A reader that declares `facts_span_files` reads all
of its files after any one edit, so one changed file lands it at the high end.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

#: Minutes an estimated run may take before it is put to the reader first. The maintainer's
#: choice (2026-11-03): `--warn-after` in a terminal, a field in the dashboard's dialog.
#: Clamped, and the clamp says why (design rule 6): under a minute every run would ask, and
#: ten hours is past any run measured here.
WARN_AFTER_DEFAULT = 10
WARN_AFTER_MIN = 1
WARN_AFTER_MAX = 600

#: The CPU count the default rates were measured on (Apple M1, PERFORMANCE.md).
REFERENCE_CPUS = 8

#: Seconds per file, wall clock, at `REFERENCE_CPUS`: (extracting, everything after it).
#: Every row is a measurement, and its source is the comment above it. A language with no row takes
#: `FALLBACK`, and the basis sentence says so.
RATES: dict[str, tuple[float, float]] = {
    # Unreal's Engine/Source/Runtime, 18,263 files, 2026-11-04: 10,363 s extracting, 615 s
    # after. The dearest tree per file measured, because headers grow with the tree: OpenUSD
    # took 0.176 s a file and Runtime/Core 0.068 s, so it prices those high.
    "cpp": (0.567, 0.034),
    # Society, 628 files: 37.7 s whole, cold. The split is unrecorded, so it is halved.
    "python": (0.030, 0.030),
    # 443 files: 1.5 s extracting, 1.83 s wall.
    "typescript": (0.0034, 0.0007),
    # beads, 484 files: 6.3 s extracting, 7.1 s wall.
    "go": (0.013, 0.0017),
    # pdfcraft, 250 files: 37.3 s reading, 42.9 s wall.
    "rust": (0.149, 0.022),
    # traccar, 1,059 files: 13.5 s in the reader, 22.9 s wall.
    "java": (0.013, 0.009),
}
FALLBACK = (0.06, 0.05)
#: A file whose facts are in a current graph is hashed and skipped: Runtime, nothing changed,
#: 18,263 files in 39.7 s off the external volume.
CACHED_S = 0.0022

#: The phase `_Progress` times the extraction under. Every other phase is "after".
EXTRACT_PHASE = "reading the source tree"


@dataclass(frozen=True)
class Estimate:
    low_s: float
    high_s: float
    basis: str

    def words(self) -> str:
        """`about 12 min`, or `between 40 min and 2 h 30 min`."""
        lo, hi = _span(self.low_s), _span(self.high_s)
        return f"about {hi}" if lo == hi else f"between {lo} and {hi}"


def _span(s: float) -> str:
    if s < 60:
        return "under a minute"
    m = round(s / 60)
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    # Rounded to five minutes past the hour: a two-hour estimate given to the minute
    # claims a precision the measurements above do not have.
    m = 5 * round(m / 5)
    if m == 60:
        h, m = h + 1, 0
    return f"{h} h" if not m else f"{h} h {m} min"


def estimate(by_lang: Mapping[str, int], *, prior: Mapping[str, Any] | None = None,
             cached_possible: bool = False, cpus: int | None = None) -> Estimate:
    """The range for reading these files, from this program's last run or from the rates.

    `prior` is a finished run's sidecar (`state == "done"`, with `timings` and `files`), or
    `None`. `cached_possible` is whether a current graph exists for the extraction to skip
    from, which is the only thing that lets the low end fall below the high one.
    """
    total = sum(by_lang.values())
    n = max(1, cpus if cpus is not None else (os.cpu_count() or REFERENCE_CPUS))
    scale = REFERENCE_CPUS / n
    used = _from_prior(prior, total)
    if used is not None:
        extract_per_file, after, basis = used
        high = total * extract_per_file + after
    else:
        high = after = 0.0
        missing = []
        for lang, k in by_lang.items():
            ex, af = RATES.get(lang, FALLBACK)
            if lang not in RATES:
                missing.append(lang)
            high += k * ex * scale
            after += k * af * scale
        high += after
        named = ", ".join(sorted(lang for lang in by_lang if lang in RATES)) or "none"
        basis = (f"measured rates for {named}, scaled to {n} CPUs"
                 + (f"; no measurement for {', '.join(sorted(missing))}" if missing else ""))
    low = total * CACHED_S + after if cached_possible else high
    return Estimate(round(low, 1), round(high, 1), basis)


def _from_prior(prior: Mapping[str, Any] | None,
                total: int) -> tuple[float, float, str] | None:
    """(seconds per file extracted, seconds for everything after, the basis), or `None`."""
    if not prior or prior.get("state") != "done":
        return None
    timings = prior.get("timings") or []
    files = prior.get("files") or {}
    parsed = int(prior.get("parsed") or 0)
    was = sum(int(v) for v in files.values()) if isinstance(files, dict) else 0
    if not timings or was <= 0 or parsed < 20:
        # A run that read almost nothing fresh says nothing about the cost of reading:
        # a cached re-run of 18,263 files extracts in 40 s and would price a cold one at that.
        return None
    extract_ms = sum(int(ms) for label, ms in timings if label == EXTRACT_PHASE)
    after_ms = sum(int(ms) for label, ms in timings if label != EXTRACT_PHASE)
    per_file = extract_ms / 1000 / parsed
    after = after_ms / 1000 * (total / was)
    return per_file, after, (f"this program's last run, {was:,} files "
                             f"({parsed:,} read fresh), scaled to {total:,}")
