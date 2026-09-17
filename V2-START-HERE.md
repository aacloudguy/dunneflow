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
| `RULES.md` · `DESIGN-RULES.md` | carried over **verbatim, numbering intact**. The numbers are addresses: never reused, never renumbered, never closed up. **v2 continues at engineering rule 96** — 95 is the fingerprint's blind spot, minted 2026-09-17. |
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
  **Not wired.** `walk.py` is untouched and the fingerprint is untouched, so the golden cannot
  have moved.
* **The gate is runnable** — `tools/golden.py`, and the section below says what it reproduces.
* **A read means a read.** `Store(writable=False)` opens `?mode=ro`, so the fourteen sites
  that open a map to read it can no longer write to one. Nothing on the analysis path
  changed, so the golden is untouched.
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

**The MCP server was brought forward**, 2026-09-17, from `PLAN-v2.md`'s chunk 4 to the
front. It is the one chunk that delivers a new capability without touching ingest at all,
so it can be written against a tool that is not moving underneath it, and it gives an agent
something to drive before two gated refactors land. Tom's call, and his reasoning is
recorded: the existing tool is usable as-is, so v1 defects found along the way are rolled
into whichever feature chunk owns them rather than scheduled as work of their own.

1. Wire `walk.py` to the registry — `discover()` takes the suffix union, `analyze_tree`
   groups by language and dispatches. **Gate: the seven digests do not move.**
3. `rules_fingerprint(lang)` and `code_extraction_inputs(lang)`, per-language `meta`, and a
   `files.extractor` column. A rule change in one language must not discard another
   language's graph. **Rule 95 belongs here**: `sql.py` shapes every `sql_ops` row and is in
   no key, so editing it leaves every cached graph stale and undiscarded.

**Of the four confirmed v1 defects, two are closed.** `BKIND_GLYPH` went in `679d772`;
`writable=False` now opens `?mode=ro` and genuinely refuses a write, which is what the MCP
`query` tool needed. The two that remain are scheduled where they belong rather than
outstanding: `is_test_path` is *replaced* by `DiscoveryRules` when `walk.py` is wired, and
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
