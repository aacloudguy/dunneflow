# DunneFlow — briefing

**Read this first, then stop.** It is an index, not a fourth copy of the documentation.
It exists so a fresh context can be useful in a few minutes instead of an hour.

| Read | For |
|---|---|
| `CLAUDE.md` | The rules. 27 engineering rules and 21 dashboard design rules, each earned from a false result on real code. **Binding.** |
| `HANDOFF.md` | The chronological record — what was built when, what it cost, what broke. ~1,150 lines. Read *sections*, not the whole thing. |
| **this file** | Where things are, what is done, what we are doing now, what not to re-open. |
| Artifact `f993d319-d2b7-4217-9130-cdbba698d1bc` | The ratified dashboard design — a complete working UI, the source of truth for every view. Read it with the **Artifact tool**, not from a screenshot. |

---

## What the tool is

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. **What moves is the subject; internal computation is not.** Local variables,
arithmetic and control flow are deliberately absent — leaving them out is most of what
makes the output readable.

The reader is someone who **reads code but does not write it**, orienting in a codebase
they did not build. Judge every change by whether it helps them orient, not by how many
pages it emits.

## Where the code lives

```
source ──► extract ──► graph.db ──► resolve ──► render (Markdown + Mermaid)
docs   ──► extract ──► docs.db  ──────ATTACH──┘
                       source.db  (file bodies, content-addressed)
```

| Module | What it is |
|---|---|
| `schema.py` | The fact contract. Every extractor in any language emits these types. |
| `store.py` | SQLite. **The spine, not an export format.** Nothing holds the program in memory. |
| `docstore.py` | `docs.db` — parallel to the graph, never inside it. |
| `sourcedb.py` | `source.db` — file bodies. The one store that is never discarded (rule 25). |
| `extractors/python/` | stdlib `ast` + `tokenize` only. No third-party parser. |
| `extractors/docs/` | Markdown / rST / text, scanned by hand. No markdown library. |
| `detectors/*.yaml` | **The extension point.** Teach a framework here, not in code. |
| `resolve/` | Call graph, CLI trees, flows, naming, glossary, traceability, mirror. |
| `render/` | Markdown and Mermaid, complete — never abbreviated (rule 8). |
| `anomalies.py` | What looks wrong. Every finding states what would make it a false alarm. |
| `sql.py` | Reads schemas out of the `CREATE TABLE` statements the code contains. |

### `web/` — one application

The dashboard is **vanilla JS + deck.gl on stdlib `http.server`**. No Node, no framework,
no build step. deck.gl is vendored into `web/vendor/`.

| File | What it is |
|---|---|
| `serve.py` | the server — a route table, one handler per endpoint |
| `queries.py` | every dashboard query as **SQL text**, in one place |
| `cover.py` · `detail.py` · `documents.py` | the cover · the inspector · document mode |
| `graph.py` · `layout.py` | the 2.5D model, and where things sit |
| `packages.py` | the package overview — the other graph layout |
| `static/shell.js` | **the application**: state, routing, every view, the self-check |
| `static/graph.js` | **the engine**: payload to pixels, and nothing about this page |
| `static/settings.js` | the store — per program, versioned |
| `static/shading.js` | the sphere shading, one extension class per lighting |
| `static/tokens.css` | the tokens; **no colour is declared outside this file** |

> **The boundary that matters** is the container. The engine draws inside the element it is
> handed and touches no DOM outside it; what it has to say — selection, counts, fps,
> diagnostics, errors — leaves as events. The shell owns the selection, the settings, the
> search, the legend and the breadcrumb. Before chunk 2 both halves existed twice, and
> `index.html` loaded only one of them.

## Built, and not

Working and verified against Society of Mensores (623 files, 184k lines):

Python extraction · call resolution incl. inheritance and CLI registration idioms · CLI
command trees · flows · boundaries · data structures · database read/write matrix ·
network with timeouts and retries · messaging · anomalies with severity, confidence and
blind spots · Markdown + Mermaid · documentation ingest · glossary · naming standard ·
traceability across both stores · named artefacts · the mirror · comments (18,208 of
18,208) · constants and type aliases · stable identity · source sidecar.

**Dashboard:** one application — the ratified shell (cover, navigator, worklist, table,
document, glossary, naming, settings) with the 2.5D stack and the package overview as two
layouts inside graph mode, one inspector reading `/api/node`, and the graph following the
theme.

**Not built:** `dunneflow infer` (the model pass) · temporal layers · attestation · the
project profile · document mode's narrative view · packaging as a binary · any language
but Python.

## What we are doing now

**Chunk 2, "one application" — done 2026-08-28.** The two applications are one: the stack
mounts inside the shell, there is one state, one settings store, one inspector and one
self-check; the package overview is computed rather than hand-placed and sits beside the
stack as a *layout*; and the graph follows the theme. See `HANDOFF.md` 5d for what it cost
and what it found — including that the sphere shading had never actually run.

**Next: packaging.** A single double-clickable binary is the product, and not for
convenience: DunneFlow reads private source and `source.db` contains it, so a hosted model
would send an unfamiliar codebase to a server, and design rule 14 says egress is scoped and
never a switch. PyInstaller or py2app, opens at localhost, full SQLite underneath, no Node.
Signing decides the experience, and there is already an Apple Developer account.

Deferred deliberately: the layered "stack of architecture drawings" layout (`HANDOFF.md`
5b); temporal layers; attestation; `dunneflow infer`.

**One thing owed:** the two "spheres" rows in the `CLAUDE.md` budget table are withdrawn and
want retaking on a visible, focused window — they measured flat discs while printing the
word spheres, and the lighting now actually runs. One click on **benchmark** in the graph
HUD, reproducing the eight-plate selection named in `CLAUDE.md`, or it is a different
measurement under the same label. It could not be done from automation: a hidden tab is
given no animation frames at all, so the benchmark now refuses rather than hanging and says
why. Worth retaking **with edges kept up while moving**, since that is now the default and
is the more expensive frame.

## Decided — do not re-open these

| Decision | Where it is recorded |
|---|---|
| The dashboard is the parent; the graph is a view inside it, **no iframe** | `HANDOFF.md` "Chunk 2, next" |
| `graph.js` is the engine, renamed not removed | same |
| Astro 5 + Tailwind 4 **struck**; vanilla + deck.gl, no Node | `CLAUDE.md` dashboard preamble |
| SQLite is the spine — never replaced with in-memory graphs | `CLAUDE.md` Architecture |
| `docs.db` stays parallel to `graph.db`, never inside it | same |
| **Both** a package graph and the 2.5D stack; the SVG is not the endpoint | `HANDOFF.md` "Opening screen", "Wanted later" |
| The graph follows the theme — both palettes, a Setting, usage retires the loser | `HANDOFF.md`; design rule 2 |
| One multiplier resizes everything, **graph nodes included** | design rule 3 |
| The legend is HTML, 51 disks in three interleaved columns, the main way in | design rule 19 |
| Edges on demand only, and only when still; **one** hop | design rule 19 |
| Confidence is shape, not colour; external is neither | design rule 5; rule 26 |
| Settings persist per program, versioned, discarded whole on mismatch | `settings.js` preamble |
| Route from a table; self-check derived from the DOM | design rule 16 |
| Egress is scoped, never a switch; nothing infers during `analyze` | design rule 14 |
| DunneFlow **never** talks to a VCS to fetch code | `HANDOFF.md` "Version control must stay pluggable" |
| A single binary is the product; sqlite-wasm is the *export* format | `HANDOFF.md` "Distribution" |
| **Nodes are billboarded circles, lit to read as spheres** — the technique, not an approximation | `HANDOFF.md` "why the nodes are flat circles" |
| Edges stay up while the camera turns; a Setting, default on | design rule 19, amended |

## How to verify — all three, before saying anything is done

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then against real code, because unit tests on a toy program cannot catch a resolution
defect that only appears at scale:

```bash
uv run dunneflow analyze ../mensores-overhaul/src --name mensores
uv run dunneflow serve output/mensores
```

**`../mensores-overhaul` is read-only.** All output belongs in `output/`.

Ground truth is in `CLAUDE.md` — both halves. Positive: the four executables must all
appear in "Where to start" with plausible reach. Negative, and it matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about* naming
standards and must yield **zero** naming rules.

### The traps that cost this session

Each of these looked like working code and passed every automated check.

- **The nodes are flat circles on purpose.** Billboarded circles lit to *simulate* spheres
  is the performance technique that lets the stack hold ten thousand nodes at full speed —
  it came out of prior research and is not an approximation of something better. The
  lighting is load-bearing: without it they render as coins, not balls. Do not "fix" this
  into real geometry.
- **A shader effect that does nothing is not an error.** Three separate causes did it here
  — an unrecognised inject hook, a GLSL name collision with deck.gl's own scope, and a
  shader never reassembled because deck.gl resolves one per extension *class*. Each
  compiles, each draws. Check by eye after touching the layer.
- **A backtick inside an HTML comment inside a template literal** closes the literal. The
  page comes up blank; nothing else fails. Two guards now catch it.
- **`render()` rewrites the centre pane on every keystroke.** Anything with state of its
  own — a canvas, a colour picker, a slider being dragged — must live outside it or be
  updated narrowly.
- **A check may only claim what its instrument can prove.** The DOM can show a control with
  no handler; it cannot show a handler no control reaches, because half the controls are
  conditional. That direction belongs in a test that reads the source.

### Three habits this project paid for

- **Look, don't only test.** Two defects in two sessions passed every scripted check and
  were obvious in one screenshot — a graph running at 60 fps under an opaque panel, and a
  filter strip announcing a slice over a view filtering nothing. Screenshot the UI.
- **Doubt the tool first.** On the first run against live code, *six confident findings in
  a row were defects in DunneFlow*, not in the program being read.
- **Assert your inputs.** Three bugs in one day came from a step that silently operated on
  the wrong input and reported success. A string replacement that matches nothing is the
  most expensive kind of edit.

## Shared library

This project consumes `github.com/aacloudguy/dunnecorp-shared` (local checkout
`../SharedCode`). **Check its `catalog.json` before writing any new utility, helper,
workflow, skill or template.** Read it freely; never write there without asking.
