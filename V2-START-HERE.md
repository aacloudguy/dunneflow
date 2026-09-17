# v2 — start here

This tree is **DunneFlow v2**: the same tool, being reshaped so that ingest is modular and
multi-language. v1 lives at `../DunneFlow`, is untouched, and still runs — use it whenever
you need a working map while this one is mid-change.

**`CLAUDE.md`, `BRIEFING.md` and `HANDOFF.md` in this tree are still v1's** and have not
been rewritten yet. Where they describe the tool they are accurate; where they describe
*state* they are v1's state, not this one's. This file and `PLAN-v2.md` are the v2 state.

## Read in this order

| File | For |
|---|---|
| `PLAN-v2.md` | the whole design: the plugin protocol, the registry, the fingerprint split, the TypeScript plugin, the MCP server, the 14 chunks and the gate on each |
| `CLAUDE.md` | the standing orders — **binding**, and the rules index |
| `RULES.md` · `DESIGN-RULES.md` | carried over **verbatim, numbering intact**. The numbers are addresses: never reused, never renumbered, never closed up. **v2 continues at engineering rule 96** — 95 is the fingerprint's blind spot, minted 2026-09-17. A rule is never closed; the `sql.py` gap it was minted from was shut by chunk 6, and the general remedy it names is not built. |
| `PERFORMANCE.md` | v1's figures. **Every one of them was measured on v1** and none has been reproduced here — do not restate one as though it had been (rule 24). |

## The four decisions, already taken

* **Where** — sibling clone, fresh history. v1 is never edited.
* **Parsers** — out-of-process plugins over native toolchains. Python stays in-process on
  stdlib `ast`. Chosen on a measurement: `tree-sitter` ships no macOS universal2 wheel, and
  neither does `pydantic-core`, which the official `mcp` SDK needs. This tool freezes to a
  universal2 bundle and its entire runtime dependency list is `pyyaml`.
* **API** — a hand-written stdlib MCP server over stdio, for the same reason.
* **First language** — TypeScript (against `../DunneNote`), then React/TSX (against
  `../DunneCorp`).

## What is done

* **Chunk 0.** Tree seeded from v1's *working tree* at `4f2796c` — v1 had 22 documentation
  files edited and uncommitted, and copying HEAD would have dropped them. Gates green on the
  untouched clone: ruff, mypy, **1,451 passed · 1 skipped** (the skip is `test_frozen.py:207`,
  the Linux maps-root layout, correct on macOS). Note that is 1,452 tests where `CLAUDE.md`
  still says 1,447.
* **The golden baseline** — `output/GOLDEN-v1.txt`, with the graph it came from beside it in
  `output/mensores-v1/`. Society (`../society-2026-08-29/src`, 628 files) read by **v1's**
  code with `--standards ../dunnecorp-standards`.
* **The `ingest/` seam** — contract, registry, in-process wrapper, `plugins/python/plugin.json`.
* **The gate is runnable** — `tools/golden.py`, and the section below says what it reproduces.
* **A read means a read.** `Store(writable=False)` opens `?mode=ro`, so the fourteen sites
  that open a map to read it can no longer write to one. Nothing on the analysis path
  changed, so the golden is untouched.
* **`walk.py` is wired to it** — `discover()` takes the suffix union off the manifests and
  a plugin's own skip and test rules, `analyze_tree` groups by language and dispatches, and
  `is_test_path` is gone in favour of `DiscoveryRules.is_test`. The walk says what it left
  out: unread suffixes, tests, pruned directories. **Gate run and green: 7 of 7 digests
  identical against the v1 graph**, every row count and distribution byte-identical, the
  four executables still at 1,381 · 423 · 292 · 112 and conformance still 4 · 1 · 10.
  **1,540 passed · 1 skipped**, mypy clean over 157 files, ruff clean.
* **`lang` is load-bearing** — the two `"python"` defaults on `Routine` and
  `DataStructure` are gone, `ingest.stamp_lang` is the one place a language is written onto
  a record and refuses a record that brings its own, the host verifies what a reader
  claimed against what it was handed, `load_rules` lost its default and now answers
  *declared* · *declared none* · *refused* instead of returning an empty rule set for a
  missing file, and four of the five hardcoded "only Python is extracted" claims are read
  off `SELECT DISTINCT lang FROM files`. A run says `read: python 628` on all three
  channels, the About dialog included. **1,562 passed · 1 skipped**, mypy clean over 159
  files, ruff clean, golden unmoved.
* **Rule 12 is split.** Three keys instead of one: `meta.extractor` for what every reader
  passes through (now including `schema.py` and `ingest/*.py`), and `files.extractor` per
  row for the reader that produced it — a version and a hash of its rules and its bytes.
  Editing one language's reader costs that language a re-read and costs the others
  nothing; a read of a map whose reader has moved is refused **by name**. Pressed end to
  end, and through the frozen binary: both builds compute the same two stamps and open
  each other's maps. `SCHEMA_VERSION` is **10** and no longer load-bearing. **1,575 passed
  · 1 skipped**, mypy clean over 160 files, ruff clean, golden unmoved.
* **The codec and the wire.** A reader on the far side of a pipe now works and is proved
  against the one extractor whose output is known exactly: `tests/plugins/python-oop/` runs
  **the Python extractor itself** through a subprocess, and Society comes back with **0 of
  628 files differing** and **7 of 7 golden digests identical** — against the v1 graph and
  against the in-process v2 one. `ingest/codec.py` is reflective over `dataclasses.fields()`
  and strict four ways; `ingest/worker.py` spawns, shakes hands, correlates on an id, drains
  stderr without ever parsing it, and respawns once without retrying the file that killed
  it. `ingest/dotted.py` writes down the normalisation contract that every rule in every
  detectors YAML has always been matched against, with `dunneflow ingest-conform` to check a
  reader keeps it and `dunneflow ingest-schema` to generate a plugin's types from. **The
  transport is free** — 0.022 ms a round trip, 0.3% of the run — and the codec is 98% of the
  1.48× overhead, so pipelining would buy nothing. **1,647 passed · 1 skipped**, mypy clean
  over 171 files, ruff clean.
* **The resolver is split.** `resolve/python/` holds Python's name rules, `RESOLVERS`
  says who answers for which language, and the driver in `resolve/calls.py` groups by
  `files.lang`. Two things hoisted into it so a new resolver inherits them: the
  `at_boundary` suppression (rule 2), so a boundary row never reaches a resolver at all,
  and the missing-target bookkeeping, so **one place** writes `UPDATE calls SET callee_id`
  where v1 had three. A resolver returns `Edge` or `NoEdge` and does no arithmetic. A
  language with **no** resolver has every call left external and is **named** with its
  count — which is what chunk 9 needs, since TypeScript extraction lands a chunk before
  its supplied edges do. `_BUILTINS` is `detectors/python.yaml` now, the measured union
  over CPython 3.9–3.13, so a map no longer depends on the analysing machine's version;
  on Society **no call site spells any of the seven names that differ**, and the digest is
  unmoved. `sql.py` joined the core key, which shuts the gap rule 95 was minted from. **1,588 passed · 1 skipped**,
  mypy clean over 164 files, ruff clean, **7 of 7 digests identical**.
* **`dunneflow mcp`** — the whole of `PLAN-v2.md` §3, brought forward and shipped. Twelve
  tools, two resources, one base at a time with `programs`/`open` as the topbar's controls,
  and `analyze`/`analysis_status`/`analysis_stop` for making a map rather than reading one.
  `.mcp.json` is committed, so a session started in this tree finds it. **1,529 passed ·
  1 skipped**, mypy clean over 156 files, ruff clean; the golden has not moved.

## The gate everything is measured against

`output/GOLDEN-v1.txt` holds row counts, distributions, and **seven identity digests** —
sorted `routines.id`, `structures.id`, `entrypoints.id`, `calls.site_id`,
`control.point_id`, plus body hashes and resolved-call tuples.

`make_id` is derived from names and never from positions, so **while `extractors/python/`
is unchanged, every one of those digests must stay byte-identical.** Not "the counts should
match" — a total can hold while its contents swap.

**The script is `tools/golden.py`**, written 2026-09-17, because the one this file used to
point at — "recorded in `HANDOFF.md`'s v2 entries" — was never written, so the gate could be
read and not run. It regenerates the report byte-for-byte apart from two digests:
`routines.body` and `calls.resolved` record a value whose statement was not recorded and was
not recovered by a **bounded** sweep — column permutations up to three wide over ten
candidate columns, six orderings, ten field-and-row separators and three renderings of
NULL. Bounded, not exhaustive: the search space is larger than that and was abandoned
rather than finished, which is worth saying plainly because "we could not find it" and
"it is not there" are different claims. So both are **redefined in that file** and are
compared graph to graph rather than against the report.
The other five reproduce exactly, which is what says the serialisation there is the
original's and not a second convention that happens to be self-consistent.

```bash
uv run python tools/golden.py output/mensores-v1/graph@*.db --against output/GOLDEN-v1.txt
uv run python tools/golden.py <v1.db> <v2.db>    # the gate: all seven, both sides computed here
```

Two of the baseline's figures reproduce numbers written in `CLAUDE.md` exactly — 43,926 call
arguments over 30,544 call sites, and 9,625 control points — which is what says the baseline
is faithful rather than merely plausible.

## What is next

**The MCP server was brought forward** on 2026-09-17, from `PLAN-v2.md`'s chunk 4 to the
front, and the walk was wired behind it the same day — so the ordering that remains is the
plan's own, and chunks 5, 6 and 7 were taken in it. Tom's call on the front-loading, and his reasoning is recorded: the existing
tool is usable as-is, so v1 defects found along the way are rolled into whichever feature
chunk owns them rather than scheduled as work of their own.

1. **The string-literal split** — `PLAN-v2.md` chunk 8. `FileFacts.literals`, the
   plugin-side `6 ≤ len ≤ 200_000` bound with **the count it dropped reported** rather than
   silently filtered, and SQL and artefact scanning moved out of the Python extractor into
   `ingest/literals.py` so the host judges what a string *means*. Done **before** TypeScript
   exists, so TypeScript never sees the old shape. **Gate: golden unchanged**, which is the
   proof the split is faithful — and `sql.py` is already in the core key, which is where
   that judgement now belongs.
2. **TypeScript, extraction only** — chunk 9. The pnpm package, the esbuild bundle,
   `detectors/typescript.yaml`, and the dotted fixture's rules 5, 6 and 7 stopping being
   unexercised — clause 7 brings `CallSite.is_construction` with the reader that fills it.
   **Gate: DunneNote's ground truth**, `PLAN-v2.md` §5, and the Tauri seam is the sharp one:
   30 files import `@tauri-apps/api/core` and **29 are tests**.

**Of the four confirmed v1 defects, three are closed.** `BKIND_GLYPH` went in `679d772`;
`writable=False` now opens `?mode=ro` and genuinely refuses a write, which is what the MCP
`query` tool needed; and `is_test_path` is gone, replaced by `DiscoveryRules.is_test` per
language, so `client.test.ts` is a test rather than 42% of a corpus read as program code.
The one that remains is scheduled where it belongs rather than outstanding:
`flows.py:215`'s substring test for *declared* becomes a field on `Entrypoint` when the
manifest providers land, which is the first point a `package.json` `bin` exists to outrank
a guessed `main`.

## Three things not to re-open

* **The rule numbers.** Addresses, not an ordering. v2 continues at 96.
* **No `BROWSER` boundary kind.** Settled on measurement — `BoundaryKind` is read in only six
  places outside `schema.py`, but changing the enum changes the meaning of a fact and
  discards every stored map; and it is not needed. `fetch`/WebSocket are the network under
  another name, `localStorage`/IndexedDB/cookies are persistent named storage shared across
  an origin, and the DOM is the program's own output rather than its environment. The
  residue is stated in words instead.
* **The seed came from the working tree, not HEAD.** Deliberate, and recorded in `e6da9b5`.
