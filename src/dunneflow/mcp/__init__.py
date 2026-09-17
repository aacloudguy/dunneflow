"""`dunneflow mcp` — the map, answered to a program instead of to a person.

The dashboard is one surface over the stores and this is the second. It serves the same
facts to an agent orienting in code it did not write, over MCP: JSON-RPC 2.0, one object
per line, on stdin and stdout, hand-written against the standard library.

**Hand-written because the official SDK cannot ship here.** `mcp` needs `pydantic-core`,
which publishes `macosx_10_9_x86_64` and `macosx_11_0_arm64` wheels and no universal2 one;
this tool freezes to a universal2 bundle and its entire runtime dependency list is
`pyyaml`. That is the same measurement that chose out-of-process parser plugins over
`tree-sitter`, arrived at twice independently.

**The shape, and why it is three modules rather than one.** `jsonrpc.py` is the frame and
knows nothing above it. `tools.py` holds the bodies and returns plain dictionaries: it
knows the map and nothing about the wire, so if a second API surface is ever wanted it is
a second caller rather than a second assembly of the same steps (rule 51). `server.py` is
the only place that knows both.

**Every tool body calls what the dashboard calls.** `web/cover.py`, `web/detail.py`,
`web/shape.py`, `web/search.py`, `resolve/flows.py`, `resolve/glossary.py` — none of it is
reimplemented here, and the three answers that *were* reachable from one surface only were
moved out to where both callers pass before this module existed. An agent and a reader
looking at the same map must not be told different things about it.

**Read-only, and now that means something.** Every store this process opens is
`writable=False`, which as of 2026-09-17 opens `?mode=ro` and genuinely refuses a write
rather than merely declaring an intention (rule 20). The `query` tool is gated twice over,
and `tools.py` says why one gate is not enough.

*This module is deliberately outside the no-egress guard in `tests/test_about.py`*, which
walks `extractors/`, `resolve/` and `canonical/`. That guarantee is about **what produced
the facts** — it is what lets *About this map* say no model read this analysis — and it
excludes `web/` for exactly this reason: a surface that serves facts is not a surface that
makes them. This is `web/`'s sibling and belongs on the same side of that line. `ingest/`
is the opposite case and does belong in the guard; it goes in when it is wired.
"""
