# DunneFlow — ground truth, and the gates that use it

`CLAUDE.md` carries the three verification gates as commands; this file carries **the
corpora they are run against, what each one is for, and the figure each is expected to
reproduce** — plus the two probes that are not tests: `tools/ordering.py` and
`tools/fingerprints.py`.

**Read this before quoting a figure, retaking one, or rebuilding the comparison pair.** A
row here states its conditions where they are load-bearing, and a measurement taken without
reproducing them is a different measurement under the same label (rule 24). The four
Society clones are read-only and only two of them are the pair; getting that wrong cost a
whole analysis once, and the result looked perfectly healthy.

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

**All three run on Windows and on Linux as well, and the suite is expected to be green on all
three.** Two tests skip off their own platform, by name — the macOS and Linux maps roots, each
asserting its own layout — and nothing else is conditional. Everything else that is
platform-shaped is tested by **monkeypatching `sys.platform`** rather than by skipping, so the
Linux picker and the Windows stop rungs are exercised on whichever machine is running:
`tests/test_desktop.py` says why, and the two-of-four guard drift in `analysis.py` is what
happens when they are not.

`mypy` is worth running with `--platform darwin`, `--platform linux` and `--platform win32`
from any machine when anything under a `sys.platform` branch has moved: it checks the branches
this machine cannot execute, and it is the only gate that can — a Linux-only
`name is not defined` in `reveal_dir` was found exactly that way and no test on any platform
would have caught it.

And when anything under `runtime.py`, `packaging/`, `detectors/` or `extractors/` has
moved, **through the binary as well as beside it** — the tests prove the source tree and
not the artifact:

```bash
DUNNEFLOW_ARCH=host uv run pyinstaller packaging/dunneflow.spec --noconfirm
dist/DunneFlow.app/Contents/MacOS/dunneflow analyze <tree> --name x --output <tmp>   # macOS
dist/dunneflow/dunneflow analyze <tree> --name x --output <tmp>                      # Linux
./packaging/release-linux.sh verify        # does all of it, and compares the fingerprints
```

The one check that is not a ground-truth number, and it is **`tools/fingerprints.py`**:

```bash
uv run python tools/fingerprints.py dist/DunneFlow.app/Contents/MacOS/dunneflow
```

Every stamp the binary writes must equal the one this checkout computes, or the two builds
have stopped being able to read each other's maps (rule 12, and see `PACKAGING.md`). There
are **two kinds now** — the core key and one per language — so it reads a tree that holds
every language this build has a reader for, and **refuses when a registered language
contributed no rows**: a stamp that was never compared is not a stamp that agrees (rule 37).
It proves the property rather than a proxy for it, by having each build open the other's map
and letting `Store(writable=False)` speak.

All three `verify` steps run it and **none of them asks the question itself**. Both of the
two that did were calling `rules_fingerprint()`, which chunk 5 split in two; from then until
chunk 13 they raised `ImportError` — in the step written to defend rule 12, on no test path.
A Python question kept at a shell call site rots as the Python moves (rule 51), and a test
now asserts no release script spells one.

**And `tools/ordering.py` when anything under `render/` or `resolve/` has moved.** The map
may not depend on the order its rows happen to be in — `analyze_tree` collects facts through
`as_completed`, so every rowid varies run to run, and a query with no `ORDER BY` or one
ordering on a column with ties returns whatever the pool finished first (rule 66). It was
like that for a year:

```bash
uv run python tools/ordering.py output/mensores          # reverses every row, re-renders, diffs
uv run python tools/ordering.py output/mensores --api    # every GET route, asked twice
uv run python tools/ordering.py --survey                 # what no ORDER BY, and no key, defends
uv run python tools/ordering.py output/mensores-wide --api   # the comparison lane's own pair
```

**`output/mensores-wide` is the pair the comparison lane is measured against**, and it is
wide on purpose: Society's `main` at `09b9ef11` against the branch head at `03ebbd93`,
**384 Python files against 628**, where the `mensores` pair differs in three. It is what
takes `/api/changes` from three rows to 2,733, and its old side's tree is gone — a sealed
snapshot does not need one (rules 25 and 62). Rebuild it by cloning that repository at
`origin/main` into a scratchpad, analysing it with `--standards ../dunnecorp-standards`,
sealing, and analysing the branch head beside it.

**`--api` is the same argument one surface over, and it is what `web/` is measured by.**
The rendered map is the artifact that gets handed over; the dashboard is where a reader
actually stands, and it had the defect the map no longer had. It asks every route in
`_Handler.ROUTES` of two copies of one program with a **fresh `_Live` each**, because most
of the dashboard is cached and a third of it is filled before the first request arrives.
Three passes and not two: the straight copy is asked twice, so what differs between two
readings of *one* copy is named as noise rather than forgiven by a hand-kept list. A route
that was asked nothing, handed an empty parameter, or raised is **named and fails the run** —
each of those diffs perfectly clean (rule 37). `--survey` says where to look and decides
nothing; it is **rule 101** that says why the probe and not the survey is the authority.

Reversal rather than a second analysis, because two real runs shuffle *some* of the order
and catch *some* of the ties, differently each time. `tests/test_ordering.py` is the same
gate on a fixture; every file in it is a tie the Society map was actually unstable on —
including the three the *comparison* lane needs, which no corpus supplies at all.

**Half of what this gate covers, the reversal cannot see, and that is rule 105.** A
`sorted()` handed a set keeps the set's order for rows equal on the key, and that order is
the hash seed's rather than the rows' — so a route can be reversal-clean and still hand two
readers different pages. `--survey` counts that population beside the `ORDER BY` one and
decides nothing about either; what settles it is a **total** key, and in `web/changes.py`
that is `_settle`.

Then verify against real code, because unit tests on a toy program cannot catch a
resolution defect that only appears at scale:

```bash
uv run dunneflow analyze ../society-2026-08-29/src --name mensores
```

**Four trees, and only two of them are the pair.** `../society-2026-08-26` (e2e658b4,
625 files) and `../society-2026-08-29` (03ebbd93, 628 files) are the sister clones every
recorded temporal figure belongs to; `../mensores-overhaul` is a third copy of 626 files
and is neither end of it. This file named `mensores-overhaul` here for a year and it cost a
wasted analysis in the session that bumped `SCHEMA_VERSION` — the result looked perfectly
healthy, and the tell was the sidecar reporting *"1 read, 625 already held"* where the record
says twelve files differ.

`../society-2026-08-30` (7baa17bf, 628 files) is the checkpoint taken 2026-09-09, and it is
the newest Society there is: 6 commits past 03ebbd93, 43 files changed, and **3 source files**
of them. **`main` is not where Society lives** — it sits at 09b9ef11 from 2026-06-10 with 384
files under `src/`, and the work is on `feat/spec-lifecycle-and-evidence`. Cloning the default
branch gets a tree three months stale that analyses perfectly, which is why the branch is
named here.

**All four are read-only.** They are copies kept for documentation. Never write to any of
them. All output belongs in `output/`.

**None of the four is on the Linux machine, and neither is `../dunnecorp-standards`.** So the
ground truth above cannot be run there and no figure in this file was retaken on it. What a
Linux session can press instead is DunneFlow's own tree and `../dunnenote` — real code, not a
toy, and enough to exercise the binary end to end — and that is what the Linux figures in
**Packaging** were taken against. A session that needs the recorded numbers needs the trees:
clone them, or take the measurement on the Mac. Do not restate a Mensores figure measured
somewhere else as though it had been reproduced (rule 24).

Rebuilding the pair after a schema bump is two analyses and a seal, in this order — a
sealed snapshot is never re-analysed in place, by design (rules 25 and 62):

```bash
uv run dunneflow analyze ../society-2026-08-26/src --name mensores
uv run dunneflow revisions output/mensores --seal --label "Society at e2e658b4 - 2026-08-26"
uv run dunneflow analyze ../society-2026-08-29/src --name mensores \
    --standards ../dunnecorp-standards
```

**The third command carries `--standards` and the recipe said nothing about it for two days.**
`standards.db` is a document store like the corpus: a change to `detectors/docs/` or
`extractors/docs/` moves `doc_rules_fingerprint()` and stales it with everything else — and
`serve` **refuses to boot** on a stale one, before a page is served. Rebuilding the pair
without it leaves a map that analyses perfectly and cannot be opened. The directory is an
outside standard the reader names; if the one a map was built with is gone, the store can be
dropped and the conformance lane says so in its own words. Found 2026-09-08, the hard way.

**It lives at `../dunnecorp-standards/` now, and that is not a detail.** The store records
the root it was built from, and the first two were built from a session's scratchpad — so
`standards.db` recorded a path that no longer existed and the standard's provenance was
unreproducible twice. Not inside this repository, deliberately: DunneFlow's documentation
root is its package root, so a standards directory there would be read back as DunneFlow's
own prose and mint three naming rules this program never stated — rule 57's argument, one
directory over. `naming.md` is identical to the `CORP` fixture in `tests/test_standards.py`.

**A snapshot whose map was lost gets it back without an analysis.** `dunneflow render
<dir>` writes the map of every revision here that has a graph and no map, read-only, from
the stores already on disk — so it is not analysis and rules 25 and 62 never arise. It also
takes `--revision` to rewrite one. What it will not do is invent inputs: a `docs@` store is
resolved by name and never by newest, and a `standards.db` captured against another snapshot
is held out of the comparison with the naming page saying so.

**A superseded sealed snapshot is still dropped by hand**, and that is deliberate:
`sourcedb.py` owns no `DROP` and `test_source.py:171` asserts it against the source text. Each
rebuild leaves one behind — delete its `graph@…db` and `docs@…db`, then its rows in `paths`
and `revisions` in **both** sidecars. Blobs are shared by content and are left alone.

Ground truth for documentation: the pantheon table in
`.groma/milestones/v1.1-harness-ownership/NAMING.md` yields `groma`, `disceptator`,
`quaestor` and the rest with their Latin glosses; its three BINDING rules appear in the
**Vocabulary** lane, quoted whole; `.groma/PROJECT.md` and `docs/reference/glossary.md`
both define `mensor` from *mētior*. And the precision half, which matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about*
building a naming-standards importer, and must yield **zero** naming rules. If it yields
any, the detector is wrong, not the corpus.

Ground truth for code: the four executables declared in its
`pyproject.toml [project.scripts]` — `mensores`, `mensores-mcp`, `mensores-signator`,
`mensores-scriba` — must all appear in "Where to start" with plausible reach. If one
collapses to a reach of 1 or 2, a registration idiom is being missed.
