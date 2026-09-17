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
| `RULES.md` · `DESIGN-RULES.md` | carried over **verbatim, numbering intact**. The numbers are addresses: never reused, never renumbered, never closed up. **v2 continues at engineering rule 95.** |
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

## The gate everything is measured against

`output/GOLDEN-v1.txt` holds row counts, distributions, and **seven identity digests** —
sorted `routines.id`, `structures.id`, `entrypoints.id`, `calls.site_id`,
`control.point_id`, plus body hashes and resolved-call tuples.

`make_id` is derived from names and never from positions, so **while `extractors/python/`
is unchanged, every one of those digests must stay byte-identical.** Not "the counts should
match" — a total can hold while its contents swap. Re-take it with the script recorded in
`HANDOFF.md`'s v2 entries, or re-derive it from the same statements.

Two of the baseline's figures reproduce numbers written in `CLAUDE.md` exactly — 43,926 call
arguments over 30,544 call sites, and 9,625 control points — which is what says the baseline
is faithful rather than merely plausible.

## What is next

The rest of chunk 1, in reviewable pieces:

1. Wire `walk.py` to the registry — `discover()` takes the suffix union, `analyze_tree`
   groups by language and dispatches. **Gate: the seven digests do not move.**
2. `rules_fingerprint(lang)` and `code_extraction_inputs(lang)`, per-language `meta`, and a
   `files.extractor` column. A rule change in one language must not discard another
   language's graph.
3. Four confirmed v1 defects, each verified by hand — see `PLAN-v2.md`'s amendment block:
   `BKIND_GLYPH` spells `CLOUD` where the enum says `CLOUD_SDK`; `flows.py:215` decides
   *declared* by finding `"[project.scripts]"` inside a prose sentence; `writable=False`
   does not make the connection read-only; and `is_test_path` cannot see a `*.test.ts`.
4. `Store(readonly=True)` opening `?mode=ro`, which the MCP `query` tool depends on.

## Three things not to re-open

* **The rule numbers.** Addresses, not an ordering. v2 continues at 95.
* **No `BROWSER` boundary kind.** Settled on measurement — `BoundaryKind` is read in only six
  places outside `schema.py`, but changing the enum changes the meaning of a fact and
  discards every stored map; and it is not needed. `fetch`/WebSocket are the network under
  another name, `localStorage`/IndexedDB/cookies are persistent named storage shared across
  an origin, and the DOM is the program's own output rather than its environment. The
  residue is stated in words instead.
* **The seed came from the working tree, not HEAD.** Deliberate, and recorded in `e6da9b5`.
