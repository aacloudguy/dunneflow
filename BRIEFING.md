# DunneFlow — briefing

**Read this first, then stop.** It is an index, not a fourth copy of the documentation.
It exists so a fresh context can be useful in a few minutes instead of an hour.

| Read | For |
|---|---|
| `CLAUDE.md` | The rules. 90 engineering rules — numbered to 91, since 21 does not exist — and 30 dashboard design rules, each earned from a false result on real code. **Binding.** |
| `HANDOFF.md` | The chronological record — what was built when, what it cost, what broke. ~1,700 lines. Read *sections*, not the whole thing. |
| **this file** | Where things are, what is done, what we are doing now, what not to re-open. |
| Artifact `f993d319-d2b7-4217-9130-cdbba698d1bc` | The ratified dashboard design — a complete working UI, the source of truth for every view. Read it with the **Artifact tool**, not from a screenshot. |

---

## What the tool is

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. **What moves is the subject; internal computation is not.** Local variables,
arithmetic and private helpers that touch no boundary are deliberately absent — leaving
them out is most of what makes the output readable.

**Control flow was on that list until 2026-09-07 and the amendment is narrow**: a loop or a
decision is a subject *only where something moves inside it*. A loop that increments a
counter is the internal computation nobody asked for; a loop that issues one call per item
is a rate, and a rate is flow. `resolve/shape.py` is the one place that judgement is made,
and Shape mode is where a reader sees it.

The reader is someone who **reads code but does not write it**, orienting in a codebase
they did not build. Judge every change by whether it helps them orient, not by how many
pages it emits.

## Where the code lives

```
source ──► extract ──► graph.db ──► resolve ──► render (Markdown + Mermaid)
docs   ──► extract ──► docs.db  ──────ATTACH──┘
                       source.db     (file bodies, content-addressed)
                       docsource.db  (document bodies, the same store, its own kind)
```

| Module | What it is |
|---|---|
| `schema.py` | The fact contract. Every extractor in any language emits these types. |
| `store.py` | SQLite. **The spine, not an export format.** Nothing holds the program in memory. |
| `docstore.py` | `docs.db` — parallel to the graph, never inside it. |
| `sourcedb.py` | `source.db` — file bodies. The one store that is never discarded (rule 25). And `DocSourceStore`: the same class with a different `kind`, writing `docsource.db`. |
| `migrate.py` | Stored paths absolute → relative, in place. The prior state it can speak for, named (rules 60–62). |
| `extractors/python/` | stdlib `ast` + `tokenize` only. No third-party parser. |
| `extractors/docs/` | Markdown / rST / text, scanned by hand. No markdown library. |
| `detectors/*.yaml` | **The extension point.** Teach a framework here, not in code. |
| `canonical/` | Whether two writings are the same expression, per language. **Beside** the extractors, never inside one — see the cache-key note in `CLAUDE.md`. |
| `resolve/` | Call graph, CLI trees, flows, naming, glossary, traceability, mirror. `naming.py` is the **derived** lane, `stated.py` the **quoted** one — read in one place, by three readers. |
| `resolve/shape.py` | **The amendment, judged once.** What moves inside a loop or a decision, by a range join, and whether that makes it a subject. Nothing is dropped for failing it. |
| `render/` | Markdown and Mermaid, complete — never abbreviated (rule 8). |
| `anomalies.py` | What looks wrong. Every finding states what would make it a false alarm. |
| `sql.py` | Reads schemas out of the `CREATE TABLE` statements the code contains. |

### `web/` — one application

The dashboard is **vanilla JS + deck.gl on stdlib `http.server`**. No Node, no framework,
no build step. deck.gl is vendored into `web/vendor/`.

| File | What it is |
|---|---|
| `serve.py` | the server — two route tables (GET reads, the one POST switches the base), and `_Base`: everything one version decides, swapped whole |
| `queries.py` | every dashboard query as **SQL text**, in one place |
| `cover.py` · `detail.py` | the cover · the inspector and the hover card |
| `threads.py` | adjacency by *interest* — why a neighbour is worth a detour |
| `curiosities.py` | the doorway panel — ten measured extrema, each with **its middle** |
| `vocabulary.py` | the three naming lanes served — derived, **stated**, glossary — and matched against one name |
| `graph.py` · `layout.py` | the 2.5D model at two levels of detail, and where things sit |
| `packages.py` | the package overview — the other graph layout |
| `code.py` | the code browser — a file, its clickable names and what each line *is* |
| `documents.py` | the map's **own** eight documents — lane 2, every row a selection |
| `static/prose.js` | the document renderer — markdown to markup, `data-line` on every block |
| `corpus.py` | the program's **own** documents served — the list, one document, one span. Lane 1; `documents.py` is lane 2 |
| `shape.py` | ALGORITHMS: the five lanes with their denominators (`/api/algorithms`), and one routine's outline (`/api/shape`) |
| `search.py` | searching the **text** — files first, then one file's lines with their margin |
| `static/shell.js` | **the application**: state, routing, every view, the self-check |
| `static/graph.js` | **the engine**: payload to pixels, and nothing about this page |
| `static/forcelayout.js` | the second plate layout — Fruchterman–Reingold on the GPU, 91.7% fewer crossings; shadows pull for the plates they stand in for |
| `static/settings.js` | the store — per program, versioned |
| `static/shading.js` | the sphere shading, one extension class per lighting |
| `static/tokens.css` | the tokens and the three colour sets; **no colour is declared outside this file** |

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
document, glossary, **both naming lanes**, settings) with the 2.5D stack and the package overview as two
layouts inside graph mode and **two levels of detail inside the stack**, one inspector
reading `/api/node`, and the graph following the theme. The reading loop: the navigator is the routine list grouped by package, hovering a
node gives a card, picking one lights its hop and fills the inspector, threads lead sideways,
and ⌘Z takes any of it back. **Finding and keeping your place**: an arrow at the plate's rim
aimed at what you picked and clickable to go there, a reticule on it, a *focus* lock so only
the lit set answers a hover or a click, and *you are here* to restore the view you found it
in.

**ALGORITHMS — built 2026-09-06/07, chunks 1 to 4 of 6.** Tom's, and the one place this
tool's founding exclusion is amended: *"algorithms are FLOW, that's our namesake"*. A
`ControlPoint` is **a span and nothing more** — routine, line range, depth, arms, and the
header as written — and a `ControlArm` is the same one level in, so a decision can be asked
*which way out writes*. What a loop **does** is a range join over the tables that already
carry `routine_id` and `line`.

The judgement is one sentence in one module: **a loop or a decision is a subject only where
something moves inside it.** The navigator's **Algorithms** group lists what passes, in five
lanes with their denominators — 250 rates of 1,950 loops, 78 forks and 69 ladders of 2,213
decisions, 396 recoveries of 1,531 handlers, and 0 `match`, which is a named row rather than
an absent lane. The mode toggle's **Shape** draws one routine's whole outline, guards
included, nested as it is written — Nassi and Shneiderman's drawing, which is nested boxes
and no arrows at all.

**Reading one node:** hovering a routine in the picture *or in the navigator* gives a card,
painted in two stages, leading with the **invocation line** — the name, its arguments with
their types, and what comes back. `Enter` over a card opens a **detail window**: callers left,
the routine between, callees right, what it touches, threads leading away; every name is a
hop, and every hop is an ordinary selection so the stack, the navigator, the trail and undo
all follow. `?view=detail` puts that window in a **second tab or window**, two peers in
bidirectional sync over a `BroadcastChannel`.

**Code viewing — built 2026-08-29.** `source.db` is a content-addressed, compressed sidecar
(626 files, 7.8 MB of text in 3.1 MB). The inspector opens a definition ±3 lines from
`/api/node` and the glossary's citation viewer opens any span from `/api/source`; both say
the source is *as measured*, not as the tree stands now.

**The code browser** runs in three places over one `CODEFILE`: the **navigator's Code
group**, stacked as a file list that collapses once a file is picked with that file's lines
beneath it — so code and the stack are readable at once inside one window; **`Code` as a
fourth centre mode**, the same file with room for the margin to say what a line *is* rather
than stand for it; and **`?view=code`**, a peer over the same `BroadcastChannel` the detail
window uses. Clicking a name is an ordinary `selectFromNav`, and selecting anything anywhere
walks the code to the file it lives in. **No syntax colour, deliberately** — design rule 4.

Links are lookups, never name matches: `calls.callee_id` is the resolver's own answer. What
it does not carry is a *column*, so a call is underlined only where its expression occurs
exactly once on its line, and the counts of what was and was not placed ride with the payload.

**Search inside the source — built 2026-08-29.** The Code group's box asks two questions at
once: what matches a **path**, filtered instantly over rows already in the page, and what
matches the **text**, fetched. Files first — "782 lines in 166 files", 626 rows at worst and
never bounded — and the top one opens itself once the answer has narrowed, saying so when it
has not. A hit carries what the map knows about it: the routine it sits in (a line-range
lookup, innermost first), its margin, and its clickable names, all of them `code.py`'s own
answers narrowed to the matching lines. Literal and case-insensitive by default, with case,
whole-word and regex switches; a regex turns whole word off and says why.

Scanning all 184,722 lines is 20–30 ms, so rule 45 lands on the *answer* rather than on the
search. FTS5 was rejected on evidence: token-based, so it cannot find `_emit` inside
`self._emit`.

Still not built: syntax highlighting (a design-rule-2 pair if ever wanted, done server-side
with stdlib `tokenize`).

**The temporal overlays are complete.** The code browser, the routine views and the stack
were layered 2026-08-30; the **anomaly worklist joined them 2026-09-01**, once a finding
carried an identity to be paired on.

**Not built:** `dunneflow infer` (the model pass) · attestation · the project profile ·
any language but Python. **Packaging is built as of 2026-09-09** — a 31 MB unsigned
`DunneFlow.app` that opens on a machine which has never run it, with the ground truth
retaken *through the binary*; what remains is signing, an icon, and Windows. **The Inference page is withdrawn as of
2026-09-09** — built as a mockup, never wired, and now delinked from every control and
document with the code kept whole behind `INFERENCE_SHIPPED`. **Document mode is complete** — chunks 1, 2,
3, both lanes of 4, and **chunk 5 as of 2026-09-04**. The pane reads the map's eight documents
and the program's own 2,064, and a glossary citation into the corpus **opens**: `senseOpens()`
is a capability test rather than a provenance test, the viewer serves the span out of
`docsource.db`, and its foot hops into the document itself at the block holding the line.
Design rule 13 is met for both tiers.

*The number that was carried for two sessions was wrong.* The plan and this file both said
*"235 documentation-derived definitions render a dead end"*. **235 is `definitions_seen`** —
every definition the scan mined — and only **32 of them bind to a term the code uses as an
identifier** and become citations; the other 203 define words this program never names and
belong to the *mirror*. So chunk 5 fixed **32 citations across 22 terms in 10 documents**:
60 citation buttons on the glossary page before, **92 after** (60 code, 32 docs). *Retaken
2026-09-08: **91** (60 code, 31 docs). The one that went was the constraint gloss on the word*
definition*, refused by the rule at the top of this file — a citation lost by a definition
ceasing to be one, which is the fix working rather than the feature regressing.*

**The revision spine is in, and both ends of a pair are readable.** `WORKING` is a *state*
rather than an id, and a revision is identified by when it was captured; `seal()` keeps the
current snapshot under its own name so the next `analyze` opens a second one beside it rather
than replacing it. `dunneflow revisions <dir>` lists them and `--seal` keeps one.

**A comparison is two directories**: the **base** is what the whole map shows and the
**compared** is what it is held against, neither claimed to be older — *added* / *deleted* is
an interpretation the reader owns, derived from the two versions where they say enough. Both
ends are settable from the toolbar; changing the base makes the server rebuild everything
from that graph (1.2–3.0 s warm, 35 s cold), and `serve --revision` chooses it at boot.

**The doorway panel is on screen — built 2026-09-01.** Design rule 15's fourth piece of
furniture, and the last of the four. `curiosities.py` measures ten extrema over the whole
program and every card states **the middle it is being read against**, because every
program has a most-commented routine and a maximum alone is a claim nobody can weigh.

## What we are doing now

**A map of another program was being read as this one's documentation, and only the packaged
application did it — fixed 2026-09-15, and it is engineering rule 92.** Found by looking at
what five days of real use had left in `~/Library/Application Support/DunneFlow`, not by a
test. DunneFlow's own map as the signed binary built it: **122 of 147 documents** out of
`output/`, **122 of 122** stated naming rules mined from generated reports *about Mensores*,
655 of 680 definitions likewise, and a **289 MB** document store beside a 6 MB graph.

The exclusion was correct and content-tested — `program_dirs(out_root)`, a directory holding a
graph and never the name `output` — and it was **assembled from where the run writes**. From a
checkout that is `./output`, inside the tree being read; frozen it is a directory in the
reader's Library with no bearing on the tree, so a checkout's own maps went back into the
corpus. `discover_docs` asks the question of the tree now, off the listing `os.walk` already
took, and names what it pruned. 147 → **26** documents, 122 → **0** rules, 289 MB → **0.64 MB**,
verified *through the binary*; the hand-written page sitting loose in `output/` is still read.
`names_a_map`/`holds_a_map` replaced three separate spellings of one glob (rule 51), with an AST
guard refusing a fourth. **1,408** tests, mypy and ruff clean. Full record in `HANDOFF.md` under
2026-09-15.

**`/Applications/DunneFlow.app` is still the 2026-09-10 build and does not carry this fix.** Its
poisoned map has been replaced with a correct one, but the application goes on reproducing the
defect until a release is cut — which is now item 1 below.

**The user guide is written, 2026-09-10 — `docs/`, and it is the first documentation this tool
has ever had for the person it is built for.** Seventeen files, 1,879 lines, **29 screenshots
taken from a live server**, and `README.md` rewritten: it still ended *"the interactive
dashboard is designed but not yet built"*, which was the most wrong sentence in the repository.
**1,402** tests, mypy and ruff clean.

**Read `docs/README.md` before writing another page of it.** Three rules held throughout and
each was paid for: name every control by the words on it (all 44 quoted labels are grepped back
against `web/static/`), state what a thing costs because the product does, and never cite a rule
number — `RULES.md` is for whoever builds the tool.

**`docs/` is DunneFlow's own corpus now**, 9 documents to 26, which is the one way a tutorial
can put a false fact into the map. Measured before and after: **zero** naming rules from
`docs/`, and one definition, which was a heading of mine reading as a glossary section and is
reworded. **Re-measure this after adding a page** — the command is in `HANDOFF.md`'s
**2026-09-10** entry, second of that date.

**One defect, found by driving the product to photograph it and not by a test.** The
version-pair control named a pair it was not showing: `buildRevControls()` derived its compared
end from `chosenPair()`, which cannot tell *nothing chosen yet* from *chosen: on its own*, so a
first visit read **on its own** while the strip, the routine marks and the code overlay all ran
a comparison. It asks `comparedRevInForce()` now — the third surface to be given that same fix,
and the only one the reader can click. The guard that stood over it could only see that *a* key
was read (rule 37); there is a real one beside it now.

**Every map in `output/` was stale** and nothing said so until one was opened. The screenshot
corpus is **DunneFlow itself against `../dunneflow-2026-09-08`** (a worktree at `f795bc3`,
sealed) — a better corpus for a guide than Society, because every routine a screenshot names is
one the reader can go and read.

### Milestone 4 — built and installed, 2026-09-10

**Nothing is owed and nothing is half-done.**
`DunneFlow.app` in `/Applications` is **universal2, Developer ID signed under the hardened
runtime, notarised by Apple and stapled** — Gatekeeper says `accepted / source=Notarized
Developer ID`, and all **53** Mach-O files in the installed bundle are `x86_64 arm64`, checked
in place rather than in `dist/`. **1,401** tests, mypy clean over **139** source files, ruff
clean. The binary still stamps `extractor = 9:e8c9ac8a851c41b7` — the checkout's, so the two
builds read each other's maps (rule 12).

**Both once-only commands that were Tom's are done.** The universal2 interpreter is installed
and `.venv-universal` builds from it; notarytool credentials sit in the keychain under the
profile `dunneflow`. `./packaging/release.sh all` now runs end to end unattended, and
**`universal2` is the default** — `host` has to be asked for, and `require_universal` gates the
four steps whose output reaches another machine.

**None of that was the asked-for work**, and that is the thing to carry forward. The rename that
started the session took twenty minutes; **eight defects** came out of *running the signed
build*, and not one was reported by a test — the suite proves the source tree, and every one of
these lived in the artifact or in the first surface a new reader meets. `HANDOFF.md`'s
**2026-09-10** section carries each with its evidence.

| Fixed | Was |
|---|---|
| an analysis reporting itself frozen for ever | `analyze.js` reached for a `shell.js` global; three finished maps looked hung |
| no way back to the start page | `/` was the shell for the life of the process |
| the Dock had no running indicator | a CLI in a bundle never connects to the window server |
| relaunching made a second server | three double-clicks left three servers on three ports |
| a false refusal on a reader's first analysis | the output root was offered as *the program being read* |
| snap-to-fit framing one node as a giant sphere | `radius: r \|\| 1` — two world units, at every tilt |
| `standards.db` leaked on every program switch | a list of two where the tuple had three |
| a checkout writing the packaged app's maps pointer | the two worlds share a home directory |

**New and reader-facing:** maps can be kept on another disk (`Move…` on the start page — 287 MB
onto an external volume in 2.3 s, through the signed binary), a map can be closed back to the
start page, and `/start` is reachable by URL when the shell has stopped working.

### Where to pick up

0. ~~**Cut a release**, so the installed application carries rule 92's fix.~~ *Done
   2026-09-15, and it carried the icon with it.* `./packaging/release.sh all` ran unattended,
   all seven steps: universal2, Developer ID, **notarised (Accepted) and stapled**,
   `DunneFlow-0.1.0.dmg` at 22.7 MB, and installed. Verified in the installed bundle rather
   than from the build log — Gatekeeper `accepted / source=Notarized Developer ID`, **53 of 53
   Mach-O files universal**, and the shipped binary reports **0 stated rules** on this
   checkout, so the defect that started the day cannot be reproduced with the application that
   shipped. It stamps `9:e8c9ac8a851c41b7`, the checkout's (rule 12), which is the first time a
   *universal* build has been asked. See `HANDOFF.md` under 2026-09-15.
1. ~~**The icon.**~~ *Settled and shipped 2026-09-15.* `icon=None` is gone: the spec names
   `packaging/icon/dunneflow.icns` and **refuses to build without it** rather than shipping the
   generic bundle icon in silence (rule 49).

   It is Tom's rabbit head — `packaging/icon/rabbit-head.png`, 800×528, committed beside the
   `.icns` it regenerates byte for byte. **Head-only rather than the whole leaping animal, and
   that was settled by looking**: it is the only framing that still reads as a rabbit at 32px
   and 16px, where the full-body drawing is a smudge. Three candidates were built and compared
   at 128 · 64 · 32 · 16, and the answer was checked against what macOS itself draws from the
   installed bundle rather than against the source files.

   *What the drawing that replaced the first crop bought, measured:* the upscale to a 1024
   canvas fell from **3.85× to 1.28×**, so 512 and 1024 stopped being soft. Fill contrast
   against the ground is unchanged at **1.75:1** — the geometric hare is 4.74:1 on the same
   blue — and that number is not what decides it: the **dark outline** carries the silhouette
   where the fill cannot, and it is heavier here. The four-point star reads where the old fan
   of thin rays turned to mush below 64px.

   `build_supplied_icon.py` is the conditioner — it squares, scales, rounds and ladders a
   supplied drawing under `build_icon.py`'s own canvas rules, and prints the contrast and the
   upscale factor so a candidate is judged on evidence. **It keeps whatever bleed the artist
   drew**: an edge the subject already runs off is a decision, and centring undid it — the
   rabbit is cut level at the neck to run off the bottom, and centring floated that cut in
   mid-canvas with blue underneath, where it read as an image that failed to load. The rule is
   read off the source, never set by a flag (rule 30).

   `build_icon.py` and `dunneflow.svg` are **kept**, though the icon they draw is not the one
   that ships: that docstring is where the 32px contrast rule was earned, and it is what every
   candidate since has been measured against.

   *Still open, and it is a drawing question rather than a code one:* the geometric icon's
   **bottom corners are square** — the river bands are drawn over the rounded rect and run to
   `SIZE` without being clipped, so three sides round and one does not. Untouched, since that
   icon is not the one that ships.

2. **A `.dmg`**, whenever something needs handing to somebody. `release.sh dmg` builds, signs,
   notarises and staples one, and works now that the credentials exist.
3. **Windows**, last, and still deliberately after everything else.

**The port-8787 collision recorded below on 2026-09-09 is closed.** `already_serving` joins an
existing DunneFlow reading the same root rather than taking a new port, so a double-click on a
running application opens the browser at it. Two *different* roots are still two servers.

### Before that: milestone 3 — signed with a Developer ID (2026-09-09)

**Milestone 3 — signing — is built and installed, 2026-09-09.** `DunneFlow.app` is signed with
`Developer ID Application: Thomas Williams (G3RLJWV327)` under the hardened runtime with a
secure timestamp, and it is in `/Applications`. **1,368** tests, mypy clean over **134** source
files, ruff clean.

**The ground truth was retaken through the signed binary** and every figure held: 628 files,
the four executables at **1,381 · 423 · 292 · 112**, `naming.md` byte-identical to the `CORP`
fixture, the research paper yielding **zero** naming rules, conformance at **4 checked · 1 no
population · 10 not checkable**, and `extractor = 9:e8c9ac8a851c41b7` — the checkout's, so the
two builds still read each other's maps (rule 12).

**Where to pick up: two once-only commands that are Tom's**, and everything downstream of them
is written and waiting in `packaging/release.sh`.

1. **The universal2 interpreter.** `sudo installer -pkg python-3.12.10-macos11.pkg -target /`
   after downloading it from python.org. uv's Pythons and Homebrew's are single-arch by
   construction, so a universal build cannot be made without it, and the spec **refuses** to
   pretend otherwise (rule 49).
2. **Notarisation credentials.** An App Store Connect API key, then
   `xcrun notarytool store-credentials dunneflow --key … --key-id … --issuer …`. Until that
   runs, Gatekeeper says *"rejected — source=Unnotarized Developer ID"*, which is the honest
   state of a correctly signed app rather than a defect.

Then `./packaging/release.sh all` does the rest. After that: an icon (`icon=None` in the spec
today), and Windows last.

**The installed `.app` is arm64 and unnotarised**, and that is what it says it is. It is proof
of the signing path rather than the release: the universal build needs command 1 and the
notarisation needs command 2. `dist/` is gitignored, so nothing about the artifact is recorded
anywhere but `packaging/`, which is the point.

**A double-click right now would collide with port 8787**, which a previous session's server
holds. `serve` defaults to 8787 and the application defaults a bare argv to `serve`, so the
Finder launch was checked at `--port 8890` instead: it served the start page, and
`POST /api/pickdir` spawned the folder dialog as a child of the hardened-runtime process with
nothing denied in the AMFI log — which is the whole evidence for an entitlements file that asks
for nothing.

**8787 is still up and is a previous session's, left running on purpose.** It holds
`output/mensores` open and has never seen a changed byte; it is not to be stopped without
asking. Nothing this session wrote to `output/` — every analysis went to a temporary
directory and was removed.

---

**Milestone 2 — packaging — is built, 2026-09-09.** All five blockers are closed and there
is a `DunneFlow.app`: 31 MB, unsigned, and it opens on a machine that has never run it.
Four commits, working tree clean. **1,363** tests, mypy clean over **134** source files,
ruff clean.

The ground truth was retaken **through the binary**, which is the only way it means
anything about an artifact: 628 files in 37.7 s, the four executables at
**1,381 · 423 · 292 · 112**, `naming.md` byte-identical to the `CORP` fixture with its
three rules in the checked lane, the research paper yielding **zero** naming rules, and the
conformance verdicts at **4 checked · 1 no population · 10 not checkable**.

* **`runtime.py` is the one place four two-answer questions are answered** — frozen or not,
  where my files are, where maps go, how to run myself again. Every one was a
  `Path(__file__)` or a hand-written `sys.executable` in whichever module wanted it, and
  frozen each is wrong differently. Two AST guards hold the line, and both had to be
  rewritten to *parse* rather than scan: the first spelling of each reported its own
  explanation of the rule as a violation (rule 34, three times in one session).
* **The fingerprint refuses rather than returning the hash of nothing.** Blocker 1 was two
  failures: an empty glob hashing to `e3b0c44298fc1c14`, which looks exactly like a
  fingerprint, *and* `doc_extraction_inputs()`' `Path(__file__)`, which frozen is a name
  with no file — a list that is never empty, so an emptiness check alone passes it through
  to a `FileNotFoundError` raised from inside a hash.
* **The binary and the checkout agree on a fingerprint**, and that was the whole reason for
  the bundle layout: `extractor = 9:e8c9ac8a851c41b7` from the binary is the checkout's, and
  the checkout opens the binary's maps. A build-time constant was considered and rejected
  for exactly that — it would make the two builds refuse each other under rule 12.
* **Nothing open is a state, and it is what a double-click begins in.** `serve` takes a
  program, a root, or nothing; with nothing to show it serves a **start page** rather than
  refusing to exist. Tom's call, over drawing the shell empty.
* **The analyse dialog is out of `shell.js`** into `analyze.js`, because the start page needs
  every part of it and a second copy in a reader's first minute is rule 51 at its worst.
* **A native folder picker and a reveal**, `osascript` and `open`, no dependency. The picker
  sits *beside* the typed field, never instead of it.
* **Rule 91 was minted and it cost the thing it is about.** The 409's sentence was written
  into the HTTP status line, which is latin-1; the em dash raised inside the error handler
  and the socket closed empty. Found by pressing the route, not by any test — and the test
  that holds it now binds a real port and asserts the em dash comes back.

**One candidate rule is filed rather than minted, for Tom.** *A module's `__file__` is a
name, not a place.* It is the shape behind four of this session's defects — the two rule
directories, both extractor trees, and `web/`'s `static` and `vendor`, which frozen is a
server that starts perfectly and serves 404s. It may be rule 60's family (*a stored path is
a key before it is a location*) rather than a rule of its own, and that is Tom's call. The
guard exists either way: `test_frozen.py` refuses any `__file__` under `src/` outside
`runtime.py`.

**What is left before this ships**, and none of it is code that does not exist yet:

1. ~~**Signing and notarisation.**~~ **Signing is done, 2026-09-09** — see *Milestone 3* at the
   head of this file. Notarisation is written and waits on Tom storing an App Store Connect API
   key with `xcrun notarytool store-credentials dunneflow`.
2. **A universal build**, which was not on this list and should have been: the build was
   arm64-only and would not have started on an Intel Mac at all. Written, and waiting on
   python.org's universal2 3.12.10 being installed.
3. **An icon.** `icon=None` in the spec today.
4. **Windows**, last, as agreed. Two branches in `default_output_root()` are written and
   marked **untested**; a `.spec` and a picker are not.

*Deliberately not done, and offered rather than assumed:* `pywebview`. The browser start is
what is built and measured, and the `osascript` picker closed the one gap that was the
argument for a native window.

**Before that, the same day: the deck was cleared.** Tom's decisions on the
open list, taken in one pass, so that what is left before packaging is the packaging.
Four commits, working tree clean, nothing half-done and nothing owed. **1,304** tests,
mypy clean over **129** source files, ruff clean; ground truth retaken, not assumed — the
four executables at **1,381 · 423 · 292 · 112**, all four resolved.

* **`one size` zooming the picture in is signed off**, and now says so. The cap is doing its
  job; the silence was the defect (design rule 6).
* **`touches --routine` no longer answers about something else.** Three answers, never two.
* **Every page of a map states its snapshot**, not just the cover. One header, one place.
* **Stack orientation is closed by decision** — camera roll is not required, and the reason
  is recorded beside `OrbitView` rather than in a backlog.
* **Inference is withdrawn**, delinked from every control and document, code kept whole
  behind one constant.

*Before that, the same day:* a new Society checkpoint, the filed item built, and node sizing
made a property of the plate a node sits on. Commits: the checkpoint itself
(`../society-2026-08-30`, 7baa17bf, analysed into `output/mensores` as
`2026-09-09T15:32:15Z`), **a map needs neither tree and the cover says which snapshot it
is**, **`dunneflow render`** — which gave the two sealed snapshots the maps they lost — and
**node size follows the plate it sits on**, which took 4,990 overlapping nodes to 0 — with
**one size** kept as a Setting beside it, and the graph's HUD bounded so a tall control box
scrolls instead of being clipped.

**Next is packaging — milestone 2 — and it has not been planned yet.** The five blockers are
found rather than predicted and are filed at *Packaging* near the foot of this file, with the
reasoning and the measurements beside each. Tom, 2026-09-09: *"Once these are done, work on
the packaging issues and then we can build it. May take a couple of milestones."*

**Where to start when this resumes:** blockers 1 to 3 first. They are defects in code that
already exists, so they can be fixed and tested *before* anything is frozen — a frozen build
that fails is a much harder thing to read than a failing test. Then the cold start (4 and 5),
which is a feature rather than packaging: it decides what double-clicking the thing actually
does. Then the spec file, and signing last. `output/mensores` is unchanged by this session —
the verification analysis went to a temporary directory and was removed.

**The graph has been looked at, and the instrument's limitation is now diagnosed rather
than described.** A page whose only job was to count animation frames reported **0 frames in
2 seconds**, a total of 1, and a fresh one-shot `requestAnimationFrame` that never fired,
while `setTimeout` ran normally: rAF is **stopped, not throttled**, whenever the tab is not
the visible one. That is one cause for all three symptoms — no frame means deck.gl never
ticks, never resizes its drawing buffer (hence 300×150 for ever), and `Graph.resize()` queues
work for a frame that never comes. **The fix is the tab in front**, which Tom did: the canvas
resized to 1113×649 and drew at 60 fps. Chrome's backgrounding flags are only a partial
substitute — they cover an occluded *window*, not a background *tab*.

**8787 is up and it is a previous session's, left running on purpose** — it was stopped as
cleanup while Tom was reading it once, which is what produced the *"the server could not be
asked: Failed to fetch"* he reported, and it is not to be stopped again without asking. It
held `output/mensores` open through a seal, an analysis and two renders and never saw a
changed byte; it is still serving `2026-09-08T13:39:50Z`, which is now sealed rather than
working. 8899 was his and is **not** listening.

**`output/mensores` now holds three revisions and three maps.**

| Revision | State | Files | Tree |
|---|---|---:|---|
| `2026-09-09T15:32:15Z` | WORKING | 628 | Society at 7baa17bf — 2026-08-30 |
| `2026-09-08T13:39:50Z` | FOR_COMPARISON | 628 | “Society at 03ebbd93 - 2026-08-29” |
| `2026-09-07T15:32:31Z` | FOR_COMPARISON | 625 | “Society at e2e658b4 - 2026-08-26” |

The fourteen flat documents from before maps were named are still beside them, listed by
`README.md` and left alone: which revision they describe is recorded nowhere.

### Clearing the deck: four decisions and a withdrawal (2026-09-09)

Tom's call on five open items in one message, and none of them needed a design conversation
because he had made the design decisions already.

**`one size` zooms the picture in, and that is correct.** *"One size is fine, I sign off on
that. We can mention the behavior in the documentation."* So nothing changed in the layout
and two sentences changed: `nodeCeilingNote()`'s uniform branch and the button's own title
now say that a smaller smallest node raises the view's floor and the framing follows it
(−4.88 → −3.30 at `plateSize 0`, `spreadZ 0.9`). Design rule 6 gains the general form: **a
clamp is felt through whichever control moves it, so that control has to name it** — the
clamp is not always where the reader's hand is.

**`touches --routine` refuses to answer about something else.** `_find_routine` matched a
qualname or a name exactly and then fell back to `qualname LIKE '%needle%'` *silently*, so
`--routine mensores.cli.app` answered about `mensores.cli.apply.apply` with a reach of 1.
Rule 49 wrapped around rule 5, in the one command a reader would use to check an
executable's reach. The fallback is kept — a half-remembered name is a real way to arrive —
and may no longer wear an exact match's clothes: `Found` carries `exact`, and one helper
both `touches` and `impact` call says which it is holding (rule 51 — the defect was in
both). Three answers, never two.

*And the case that bit gets its true answer*, which is worth more than any number of
near-misses:

```
no routine is named 'mensores.cli.app'.
  mensores.cli is a module here — mensores/cli/__init__.py — and declares no routines at
  all; nothing in it is named 'app'.
  1 routine name contains it — a name search, not the routine you asked for:
```

**The module test asks `files`, not `routines`, and that is the whole of why it fires.** A
package `__init__` declares nothing of its own, so `routines.module` reports `mensores.cli`
as unknown — *"not a module here"* about a file the analysis had read. `<module>` is
excluded from the count for the reason it is excluded everywhere else: nobody declared it,
and *"declares 1 routine"* about a package holding a docstring and two assignments is the
opposite of the sentence's job. Two silences went with it: `LIMIT 25` then `--limit` could
show one of forty and say nothing, in the exact branch as well as the fallback, so both
count and both state it (rule 32).

**One header, on every page of a map.** The cover stated which snapshot it described and the
other fourteen pages said only `Generated <now>`, so a reader arriving at `07-database.md`
from a link had the whole problem the cover had just solved. It was not fixed in passing
because it could not be: eight renderers each built that line inline and `markdown._header`
was a ninth copy. `render/page.py` is the one place now — `Stamp` (generated · revision ·
analysed), `Stamp.of(store, when)` reading the graph once for fifteen pages, and `header()`.
Its own module because `markdown.py` imports all eight renderers, so a header living there
and imported back is a cycle.

*`_what_this_describes` is retired*, on Tom's call: all three instants survive in the
header, on fifteen pages instead of one, and keeping the section as well would have made the
cover state the same three facts twice. A map written before either key existed keeps the
line it always had — missing and blank are different answers, and inventing a snapshot for
it would be rule 30. Verified where it matters: re-rendering pulled the two instants apart
on an inner page, *source read 19:02 · these documents written 19:03*.

**Stack orientation, closed by decision.** *"I think stack orientation is acceptable as-is,
adding camera roll is not required. I can already move the camera quite a lot."* Recorded
beside the `OrbitView` construction in `graph.js`, so the next reader finds the decision
where the constraint is.

**Inference withdrawn, and withdrawn is not deleted.** *"The infer parts can be disabled as
features and the links can be removed (but the code left in place and marked for use in the
next version). Be sure to remove all mentions of the feature from any other controls or
documentation, but don't destroy any code that may already exist for it."*

It had never been wired. `MANIFEST` was a `let` nothing assigns, so the page said *"the
document manifest is not served yet"* for ever; `data-airun="go"` set `state.aiDone = true`
and reported **"✓ Pass complete."** having done nothing at all — design rule 16 with a false
claim on top — and its costs and volumes were the ratified artifact's pinned figures for one
program (rule 34).

**One constant decides**, `INFERENCE_SHIPPED` in `shell.js` (rule 51). Guarded off: the
navigator row, the Settings panel and its link, the route, the breadcrumb, the off-mode
label and the dispatch — each kept in a shape the source guard can still read, because a
route written any other way would report the withdrawn row as *unrouted* and the guard would
fail on the sentence describing what it checks (rule 43). Kept whole: `viewInference()`,
`AI_OPS`, `POSTURES`, `MANIFEST`, `posture()`, `permits()`, `chosenOps()`, every handler,
every state field, the CSS.

`egress` and `aiOps` left `DEFAULTS` and `PERSISTED` on **`nodeShapes`' precedent**, which is
about the reset dialog rather than about storage: `resetSettings` walks the defaults, so a
key left there makes a reset report clearing *"egress posture"* — naming a setting the reader
was never offered. A default is a promise that something can be different.

*Untouched, and none of it is the feature:* **edge confidence** `INFERRED` and the *hide
inferred edges* toggle (design rule 5, built and working), the **version tier** `INFERRED`,
`Provenance`'s four tiers, and **About this map**'s two rows — which say no fact here was
inferred and no model read it, a guarantee this makes more true rather than less. Design
rules 14 and 28 stay and say what changed; rule 14 keeps its paragraph as *what the next
version has to satisfy before the constant becomes true*.

**Guarded from both sides**, because either half fails silently alone:
`tests/test_inference_withdrawn.py` asserts every door is behind the constant **and** that
every part of the feature is still there. `selfCheck()` gained the runtime half.

**Seen, not only tested.** Served on 8901 against a fresh analysis of the 08-30 checkpoint:
no navigator row (VOCABULARY reads 4 and lists four), no Settings panel, `selfCheck()`
returns `[]` on the cover and on Settings, no door in the DOM anywhere, and a fresh settings
blob carries neither key. 8787 was left alone throughout.

### One size is a Setting, and a tall panel scrolls (2026-09-09)

Two from Tom on seeing the sizing work — *"it looks very good"*, so per-plate stays the
default.

**`nodes: by plate / one size`**, on the controls panel under the width dial, which is the
same question one step down: that dial says how much a *plate's* area tells you, this says
how much a *node's* does. Design rule 2, and turning it off is how a reader goes back to
the picture they had. **One size is the tightest plate's**, never an average — every other
plate can afford it by construction, so the separation guarantee survives the mode change
rather than being quietly given up by the mode that is meant to be the safe one. Verified
in the engine: 0 touching pairs of 2,681,114 in both modes, at both ends of the width dial.
The ceiling note says something different under one size, because there the ceiling is not
what binds and *"0 plates are at the ceiling"* would be true about the wrong constraint
(rule 32).

**A HUD box taller than the picture was clipped with no way to reach the rest.** Tom:
*"when I open a control such as the spacing control… there is no method to scroll down…
I have to make the window taller."* `.graphcanvas` is `overflow: hidden`, so the bottom of
the spacing row was simply past the edge. The HUD is bounded to `calc(100% - 1rem)` of the
canvas — a real percentage against a positioned ancestor with a definite height, so no
script and no media query — and **`.hudbody` is the scroller, not the HUD** (rule 50):
scrolling the whole thing would carry the headers off the top, and `.graphhud` is
`pointer-events: none`, so its own scrollbar could be seen and never dragged.
`overscroll-behavior: contain` is not a nicety — past the last row the wheel would chain
into the canvas and zoom the stack.

Measured in the page at a 557×353 canvas: the controls body is **195 px tall holding 292**,
and the bottom control — invisible before — is reachable after 97 px of scroll.

**And the fix undid half of itself, which the measurement caught.** A `render()` rewrites
the HUD, so pressing the control you had just scrolled to put it back at the top and off
the screen — *"which reads as broken"*, the same shape as `paneHeld`. `hudScrolls` /
`restoreHudScrolls` keep each body's offset across the rebuild, keyed on the body's **id**
because the boxes are conditional and an index restores one panel's position onto another.
Recorded and restored in the one function that replaces the markup, not at each caller that
causes a render (rule 51). After: 97 → 84, the control still on screen — 84 rather than 97
because that click shortens the note, so the browser clamps to the new bottom, which is the
honest outcome rather than a scroll past the end.

~~***The pointer still could not be used.***~~ *Discharged 2026-09-09 — Tom: "Confirmed
good. Much improved." Both the toggle and the scrolling panel were used at his own screen,
which is the half a scripted click cannot reach (rule 48). The instrument's own account
stands and is worth keeping:* a capturing
`pointerdown` listener recorded **0 hits** from a press aimed at a button `elementFromPoint`
confirms is there, with `document.visibilityState` reading `hidden` — the window was behind
another one, which is **rule 90** exactly, and it accounts for both missed presses this
session. The coordinate mapping was right all along.

### Node size follows the plate it sits on (2026-09-09)

Tom: *"All plates should maintain node separation… If they are small, making them larger
helps to make that point and to see them — two axes of information in one render."*

**It was a units bug.** A dot was `min(3.6, 1.4 + sqrt(degree)*0.28)` **pixels**, the same
on every plate at every zoom; a plate was `1000 * (1 + (sqrt(n/nmax) - 1) * plateSize)`
**world units**, shrinking with zoom and with how little it held. So a node knew nothing
about the space it had. Measured on Society at the default framing, **4,990 of 10,052 drawn
nodes touched or overlapped a neighbour**, and the smallest plate was a disc **5.5 px in
radius holding six of them**.

**The fix is one measured fact.** The tightest pair on a phyllotaxis disk of `n` points is
`1.546 * R / sqrt(n)`, and 1.546 does not move with `n` — 1.5460 at 6, 9, 12, 26, 58, 151,
475, 991 and 4,000. So a radius can be *chosen* that never overlaps:

    r = min( half the drawn gap to the plate above ,  1.546 * R / (2 * spacing * sqrt(n)) )

in **world units**, so it holds at every zoom instead of at the one it was picked at.

**Tom's two regimes fall out of it rather than being imposed.** At `plateSize 1` the node
radius is **16.4 world on every one of the 53 plates** — one size — because area per node is
already constant there; the plate widths do the work. Per-plate node sizing appears only as
the dial moves toward one width, which is *"only resize nodes once the plate size is
fixed"*, arrived at from the other end. At `plateSize 0` a six-node plate draws its dots
**2.0× the radius** of the 991-node plate on a disc of the same width.

**Verified through the renderer's own buffers, not from the formula.** `Graph.separation()`
reads the positions and radii the engine is about to hand the GPU and reports the closest two
surfaces anywhere on the stack:

| | pairs | touching | tightest clearance |
|---|---:|---:|---:|
| spiral, width 1 | 2,681,114 | **0** | 16.37 world |
| spiral, width 0 | 2,681,114 | **0** | 19.39 world |
| spiral, spreadZ 1.0 | 2,681,114 | **0** | 16.37 world |
| force (GPU, 84 ms) | 2,681,114 | 2,164 (0.08%) | −37.77 world |

**Force stays as it is, on Tom's instruction, and its 0.08% is the clusters.** Under force a
plate's node size is derived from the circle the solver gave it as if its `n` nodes were
spread evenly, so nodes inside a cluster can still touch — which is the arrangement saying
they are tightly related, and what force does today. *Measuring the real tightest pair was
built first and withdrawn on evidence*: it does reach 0 touching pairs, but a solver can
leave two nodes nearly coincident, that one pair then sets the whole plate's size, and the
view cap — taken on the smallest node in the stack — zoomed the entire picture in until it
was a pixel. **A 101-pixel dot everywhere else**, from one outlier. Rule 49's shape.

**Two defects the work found, and neither by review.**

* *A placement change did not resize what it moved.* `applyLayout` moves every node and
  clears the box cache "because the code that causes the staleness is the code that clears
  it" — and left the radii alone, which under a pixel constant nothing could stale. Switching
  to the force arrangement therefore drew spiral-sized dots over clustered positions:
  **1,494 overlapping pairs on an arrangement whose own rule says none can.** Found by the
  instrument, one layout after the change.
* *A lone node and a lone shadow both went to the centre.* `phyllotaxis` returns the origin
  for a single point, where a rotation cannot separate anything. Found by a test on its
  first run. The centre belongs to the drawn nodes.

**The placement had to change for any of it to be true.** Drawn nodes and shadows shared one
spiral ordered by degree, and the two kinds *segregate* by degree — so the drawn nodes came
out in contiguous runs, packed at the density of all the placed points. `ext:<small outside>`
drew its six nodes from slots 0–2 and 32–34 of 42, two blobs rather than six dots;
`ext:FILE` drew 151 in one unbroken block of 788. **A shadow has no claim on the plate's area
budget** — it is a device for the third dimension and its slot is empty screen space (rule
23) — so it now gets a spiral of its own, half a turn out of phase.

*Tested and rejected before proposing it:* sizing the plate by placed points rather than
drawn nodes, which looked like the clean one-line fix. 49.6% → **53.0%** touching. Worse.

**The ceiling binds, and the page says so.** A node may not grow past half the *drawn* gap to
the plate above, and at the default `spreadZ` of 0.35 that is **33.2 world** — so at
`plateSize 0` **43 of 53 plates** draw at the ceiling rather than at what their own spacing
allows. Design rule 1: `nodeCeilingNote()` states the count beside the width slider and names
`stack` as the lever, because the ceiling moves with that slider and not with the two the
reader will otherwise blame. It is refreshed from `updateControlsSummary`, where every slider
passes — the first version put it in the width branch alone, which is rule 78 written and
committed in the same edit.

**`nodeSize` is retired and `spacing` replaces it** — Tom's call. A radius is derived now, so
a slider setting it directly sets a number the next layout change overwrites, and one that
could be pushed past the spacing would exist to break the guarantee beside it. Smaller means
bigger dots, and the label says so. Range 1.05–4.0, default 1.5.

**Never smaller than can be drawn, and the floor is on the view.** `radiusMinPixels` would
hold every dot at a pixel while its plate went on shrinking, which is how they ended up on
top of each other; `applyViewCap` raises `minZoom` instead so the smallest node is always at
least 1 px. The whole stack still frames in a graph pane about **465 px tall** at the default
settings; below that the reader pans.

~~***Not looked at.***~~ *Seen and confirmed by Tom, 2026-09-09: "it looks very good", and
after the Setting and the scrolling panel, "Confirmed good. Much improved."*

*Every figure here was measured inside the running engine on the real payload —
`Graph.separation()`, `nodeCeiling()`, `nodePixels()` — and not one is a screenshot, because
deck.gl reports `frames 0` in the automation tab: the graph pane is hidden at boot, the canvas
mounts at 300×150 and never resizes, and four ways round it failed. **That limitation stands
and is worth knowing before the next graph change** — the engine's numbers can be taken there,
the picture cannot.*

### The checkpoint, and what "a lot of changes" turned out to be (2026-09-09)

Tom: *"pull a new version of society… There have been a lot of changes lately."* **The
remote says otherwise, and the reason is worth keeping.** `main` is at 09b9ef11 from
**2026-06-10** with 384 Python files — three months stale, and it clones without complaint
into a tree that analyses perfectly. Society lives on `feat/spec-lifecycle-and-evidence`,
whose head `7baa17bf` is dated **2026-08-30**: 6 commits past what was already analysed,
43 files changed, 6,044 insertions — and **3 source `.py` files** among them, the rest
tests and ADRs.

The analysis confirmed the diff independently and that is the useful part: the sidecar read
**3 files and already held 625**, which is the git delta arriving through a completely
different measurement. 628 files · 4,823 routines · 6,441 internal calls · 4,070 boundary
touches · 178 ways in, in 2m 27s.

**Every ground truth in `CLAUDE.md` was retaken, not assumed.** The four executables at
reach **1,381 · 423 · 292 · 112** — identical to the recorded figures. 12 stated rules: 5
VOCABULARY from `NAMING.md`, 7 FORM from the `harness/rules/style.md` table. The research
paper `conventions-naming-and-documentation.md` yields **0**.

*One thing found and not chased:* `dunneflow touches --routine mensores.cli.app` matches
**`mensores.cli.apply.apply`** and reports a reach of 1. `app` is a Typer object rather than
a routine, so the command falls back to a prefix search — rule 5's shape in a place nobody
had looked. Filed below.

**The standards directory has a durable home at last.** `standards.db` records the root it
was built from, and the previous two were built from session scratchpads that no longer
exist — the provenance was unreproducible twice, and `HANDOFF` admits it once. It is
`../dunnecorp-standards/` now, outside this repository on purpose: DunneFlow's documentation
root is its package root, so a standards directory inside it would be read back as
DunneFlow's own prose and mint three naming rules this program never stated.

### Rendering a named revision's map from the graph it already has (2026-09-09)

The item filed 2026-09-08 by the work that made maps revision-named — which kept the
promise going forward and could not reach backwards. Two sealed graphs, no map of either.

`dunneflow render <dir> [--revision <rev>]`. With no revision it writes the map of **every
revision here that has a graph and no map**; naming one rewrites that one, so a re-render is
always something the reader asked for by name. Both mapless snapshots in 33 s.

**Not analysis, and that is why it is allowed.** Nothing is extracted, no fingerprint is
re-stamped, every store is opened read-only. Rules 25 and 62 forbid re-analysing a sealed
snapshot *in place* and are untouched; rule 20 holds by construction. A test digests the
graph before and after and requires it byte-identical — which is the assertion those rules
are actually about, rather than a promise in a docstring.

**It was only possible because a map needs neither tree, and nothing said so.** `root` and
`docs_root` were threaded through **twenty-eight** render functions and read by **none** of
them: the nine path-stripping copies they existed for went when paths became relative, and
the parameters stayed for a month. A signature asking for a source root is a claim one is
needed. Removing them is what let the new command avoid inventing a plausible path, which is
rule 49 in a shape mypy cannot see.

**`Generated` is not `analysed`.** A map written by `analyze` carries one instant for both,
so a lone *"Generated 2026-09-09"* line was true twice over by accident; re-rendering pulls
them apart and that line becomes a claim about the wrong fortnight. The cover now states
three facts — snapshot, when that source was read, when these documents were written — read
from the graph's own `meta` rather than carried down by every caller (rule 51). On the
sealed `2026-09-07T15:32:31Z` all three differ: the id is 09-07 15:32, the source was read
09-08 13:38, the documents were written 09-09. **A revision id is when the working revision
was opened, not when its source was read**, and nothing had ever put the two on a page
together.

**Three refusals, three sentences** (design rule 21): a revision whose stores were dropped
by hand — and it lists what *is* here, because a mistyped instant and a deleted snapshot are
indistinguishable from a command line (rule 89); an unfinished graph, which opens perfectly
and lies (rule 80); and a stale graph, whose refusal is passed on rather than caught.

**And one thing stated rather than refused.** `standards.db` holds one revision, so an older
snapshot finds a standard that is not about it — rule 70 one store over. Its rules are held
out of the comparison and the naming page says which snapshot they *do* describe. The
sentence says what is **held out** and never that nothing is checked: the program's own
stated rules travel in `docs@<rev>` and are still checked directly beneath it, so the other
wording contradicted the verdicts under it. **The first draft did exactly that** — *"nothing
here is checked against it"* printed above `### Checked — 1` — and a test now asserts that
phrase's absence (rule 13).

The document store is resolved **by name, never by newest**: the fallback is rule 70 exactly.

`index.py`'s cell read *"not written — `--no-render`, or analysed before maps were named"*
and now names the command that writes one; its docstring said re-rendering *"is not
something this tool offers yet"*, which is the sentence a feature has to come back and
correct.

### Before that: paused 2026-09-08

**Paused 2026-09-08.** Two commits: **item 8 answered and built** — a pane now folds itself
when the window has no room for it, which makes **five** settings for what the window cannot
fit and is the only one of the five that ships **on** — and one item pulled from the standing
backlog, **a map belongs to a revision**, so a second analysis no longer writes over the
first one's and the program directory opens on a listing of what it holds. Before them, on
the same day: a bug-fix pass, two features, the counts that could be one, item 0 of the
scheduled pass paid at the pointer, and three defects that each turned out to be something
other than what was filed.
**1,253** tests, mypy clean over **123** source files, ruff clean, `check` 0 broken, working
tree clean.
**8787 is up and it is this session's, left running on purpose** — it was stopped as cleanup
while Tom was reading it once, which is what produced the *"the server could not be asked:
Failed to fetch"* he reported, and it is not to be stopped again without asking. 8899 was
his and is **not** listening.
**`output/mensores` is untouched by today's map work.** 8787 is serving it, and an analysis
aimed at a served directory can empty the map under a live reader; its next analysis is what
gives it the new layout, and that run needs `--standards` (rule 88). It holds
`2026-09-08T13:39:50Z` (628 files, Society at 08-29) working and `2026-09-07T15:32:31Z` (625,
at 08-26) sealed — the sealed one has **no map of its own**, which is the item filed below.

~~**Owed, and it is one minute of Tom's screen:** the auto-fold was verified scripted.~~
*Discharged 2026-09-09 — Tom: "Auto-fold confirmed." The scripted evidence stands and the
look behind it is now his rather than the harness's (rule 90).*
**Two servers are up and both are deliberate:** 8899 is Tom's, and **8787 is this
session's, left running on purpose** — it was stopped as cleanup while he was reading it, which
is what produced the *"the server could not be asked: Failed to fetch"* he reported, and it is
not to be stopped again without asking. **All four program directories in `output/` now open.** *Every figure on this line is retaken rather than incremented (rule 24) —
the count this file carried was 1,213 against a real 1,216 before a line of today's work, so
adding to it would have carried the drift forward.*
`output/mensores` holds the pair rebuilt under the new documentation rule:
`2026-09-08T13:39:50Z` (628 files, Society at 08-29) working, `2026-09-07T15:32:31Z` (625,
at 08-26) sealed.

### A map belongs to a revision (2026-09-08)

Pulled from the standing backlog, where it had sat since 2026-08-31 as one line. It is the
only entry on that list where **a sealed snapshot loses something it was sealed to keep**:
its graph and its documents are revision-named and survive, and the fifteen documents of its
*written map* went flat into the program directory and were overwritten by the next analysis
— the half a reader who does not write code actually reads. Nothing on screen ever showed
it, because the dashboard reads the databases, which is why it stood for eight days.

**`map@<revision>/`**, the same `@` idiom as the databases beside it. A **directory** rather
than `01-entrypoints@<rev>.md`, and the links decided it: the map's README points at its
fourteen siblings by bare name, and inside a directory those are already right. Decided at
the call site, so `render_all` goes on knowing nothing about revisions — *which* directory is
a question about time.

**The program directory's `README.md` is now a listing**: every revision, its state, capture
instant, file count and label, with a link into its map. Built from what is on disk, so three
absences each get their own sentence (design rule 21) — a revision with no map, a map with no
graph, and the older flat map, which is **named in full and left alone** because which
revision those files describe is recorded nowhere. The rows come from the sidecar handle
`analyze` already holds open, never a second one (rule 58).

**The sharp edge is rule 57, not the layout.** A map is Markdown inside the output tree, and
that is where rule 57 was minted. `discover_docs` prunes an excluded directory out of
`dirnames`, so excluding the program directory covers everything under it — a reading the
call site does not make obvious, and whose opposite would read every map back in as prose. It
is asserted directly and end-to-end. Measured analysing DunneFlow itself twice: **9
documents, then 9**, with 15 map files and an index on disk for the second run.

Verified at scale into fresh directories, never the served one: Society at 08-29, 628 files
and 4,823 routines in 36 s, and the four executables at reach 1,381 · 423 · 292 · 112.

*Filed rather than built:* **rendering a named revision's map from the graph it already
has** — it would give the sealed `2026-09-07T15:32:31Z` the map it lost, and it is not
analysis, so rules 25 and 62 are untouched. Going forward the promise holds without it.

### A pane that folds itself, and the trap it was deferred on (2026-09-08)

Item 8, answered and closed the day after it was offered. Tom: *"Item 8 should
auto-collapse."*

The narrow-window fix above stopped panes being *deleted* and gave `.body` a centre floor and
a scrollbar instead. **That is a floor rather than an answer** — at 380px the reader reaches
the centre by dragging a bar — so a pane now folds *properly*, the fold that leaves a rail.

**One question in one place.** `panelIsOpen` weighs three rules in order: the window, then
the inspector's own *nothing to say* rule, then the reader's fold. The window is first
because it outranks both — an inspector with a subject is still a pane that does not fit.

**Asked at the panes' narrowest**, never at the width the reader dragged: `applyNavWidth`
already clamps the navigator down to make room, so the fold is decided against `NAV_MIN_REM +
CENTRE_FLOOR_REM +` the inspector's track — narrower first, folded for what is left, which is
`topFit`'s mechanism one surface over. It is also what keeps it out of a loop, since
`navMaxRem()` asks `panelIsOpen("inspector")`. **Never a media query** (rule 28), which is the
other half of why the breakpoints it replaces were wrong. The inspector's track is a token
now, `--insp-w`, for `--centre-floor`'s reason.

**The trap is closed and it is what the feature sat behind.** `paneHeld` records that the
reader pressed a rail at a width the rule would fold at, so the press is not undone in the
same frame — *"which reads as broken"*. Not persisted, unlike `inspectorAuto`: it is an answer
about *this* window, and a widening one releases it.

**Rule 78 arrived through the divisor.** The rule is `innerWidth / rootPx` and `--scale` *is*
that divisor, so the scale slider narrows the page in exactly the units this counts: at
1,215px, 160% is a **47.5rem** window with no room for three panes. `refitPanes()` is invited
from `applyScale`, which all four scale routes pass through. Found while verifying.

Measured in the page at `innerWidth 1215`, driven through the scale because `resize_window`
changes nothing:

| | window | rule wants | held | drawn |
|---|---|---|---|---|
| narrow | 27.1rem | inspector + navigator | — | `nav=off insp=off`, both rails drawn |
| press the rail | 27.1rem | inspector + navigator | inspector | `nav=off insp=on` |
| refit, same width | 27.1rem | inspector + navigator | inspector | `nav=off insp=on` |
| widen | 75.9rem | — | — | `nav=on insp=on` |
| narrow again | 27.1rem | inspector + navigator | — | `nav=off insp=off` |

`state.panels` reads `nav=true insp=true` throughout: the fold is laid over the reader's
arrangement, never written into it. Nine mutations, nine catches — two of them found by the
harness and not by review, one a guard whose span reached the wrong `resize` listener
entirely. *The pointer was not used: the window was `hidden` the whole time (rule 90), so
this is scripted evidence and one press with the window in front would finish it.*

*Noted and not fixed:* `fitTopbar` has the same dependency on the scale and does not hear
about it either. Pre-existing, and refitting on every frame of a drag is a measurement nobody
asked for.

### A narrow window deleted a pane instead of collapsing it (2026-09-08)

Tom, with a picture: *"the left Navigator pane collapses and cannot be brought back without
making the window wide again. It would be better to collapse it and permit horizontal
scrolling, with a visible bar at the bottom of the screen. The BASE works like this, and
that is fine."*

**It was not collapsed, it was deleted.** Two breakpoints did `display: none` on the pane
while `state.panels.navigator` stayed **true**, so `applyPanels` hid the rail — a rail is
only drawn for a pane that is *closed*. Open, undrawn, nothing to press. Reproduced at
`innerWidth 380`: `data-navtrack="on"`, the column really **192px**, `.navigator` at
`display: none` inside it. **The hole the comment four rules above it warns about**, in the
same file.

**The inspector had it too**, at 1088 instead of 768, and it was not in the report only
because Tom's inspector was already folded. Same cause, found by opening it.

**And neither `grid-template-columns` in those blocks ever applied** — rule 29, in the block
whose own comment cites rule 29 for its sibling. A media query has no specificity, so the
bare `.body` lost to `.body[data-insp="off"]`: at 380 the columns were still
`192px 152.5px 28px`, three tracks for two visible panes, survivors auto-placed one track
left. Only the `display: none` won, because it alone was written `.body >`.

Replaced by Tom's mechanism, which is the version strip's a third time: `--centre-floor:
16rem` (a token, because `CENTRE_FLOOR_REM` in JS is the same number and a test keeps them
equal), `minmax(var(--centre-floor), 1fr)` in **all four** `.body` track declarations, and
`overflow-x: auto; overflow-y: hidden; scrollbar-width: thin` on `.body`.

| `innerWidth` | columns | `.body` | page |
|---|---|---|---|
| 380 | `192px 256px 352px`, all three drawn | 380 of **800**, scrolls, 5px bar | does not scroll |
| 950 | `288px 310px 352px`, all three drawn | fits | does not scroll |

The cycle that was impossible, at 380: fold → rail drawn at 28@0 → press it → pane back.

*No **automatic** collapse was built.* With the row scrolling there is no need for one, and a
window that rearranges the reader's panes by itself is a separate call — `inspectorAuto`
shows the shape it would take, trap included. Offered rather than assumed.

### A name with no seam, divided rather than cut anywhere (2026-09-08)

Item 7, closed the day it was filed. Tom: *"proceed with a reasonable fix that breaks words
at smart intervals, not just arbitrary characters. Re-use what's been written where
possible."* — a fourth option none of the three I had listed.

**The interval is measured, not chosen.** `jointed()`'s three seams cut Mensores' 4,823
routine names into **13,175 runs whose median length is 5** and whose longest is 15. So a
break this program invents aims at five characters — the length the language's own
underscores and humps already produce — and a divided name looks like a name an underscore
broke rather than one the edge of a box did. No piece may be shorter than **three**, because
orphaning one letter is the entire defect: `disable / d`.

| | |
|---|---|
| seamless names divided | **789 of 1,013** (524 of them `<module>`) |
| left to the `break-word` floor | **224** — `run`, `name`, `get`, `id`, `up`, `ok` |
| shortest piece anywhere in the corpus | **3** |
| names with seams, untouched | **3,810 of 4,823** |

**Only names with no seam at all are touched, and that is rule 1 rather than laziness.** All
`<wbr>` are equal to a browser, which takes the last opportunity that fits with no notion
that an underscore is a better place than the middle of a word. Marking the long runs inside
an already-seamed name would hand it a mid-run opportunity it would prefer, turning today's
`_assert_no_ / forbidden_phrase` into `_assert_no_forbi / dden`. The fix would have made the
good case worse to improve the bad one.

**`break-word` stays, as a floor rather than as the mechanism**, and it says so where it
lives. A name shorter than six cannot be divided without orphaning a letter, and for those
the choice is breaking badly or painting over the count — which is the defect the whole
setting exists to end. It is now reached by 224 of 1,013 rather than by all of them.

`seamlessParts` slices the **raw** name and leaves escaping to its caller, which is not
tidiness: slicing an already-escaped string cuts `&lt;` in half, and 524 of this corpus'
seamless names are `<module>`. Confirmed in the live DOM — `&lt;mod<wbr>ule&gt;`.

Measured in the page: `disa<wbr>bled`, `rev<wbr>iew`, `adjud<wbr>icate`, `rele<wbr>ase`,
`&lt;mod<wbr>ule&gt;`; 2,674 → **3,018** marks, and 72 of 1,654 labels left with none, every
one of them a short word. *The rendering itself was **not** seen: the automation's tab was
hidden, and a hidden tab has no layout at all — every box is zero — so the geometry half of
rule 90 is as blind as the pointer half. What is verified is the markup and the corpus, not
the picture.*

### Item 0 paid: the five controls, pressed — and one thing only looking found (2026-09-08)

Tom: *"it's in front now, go."* It was, and every control was reachable at the first attempt.
Against **his** arrangement — `navName: wrap`, `topFit: on`, `verStrip: on`, `paneFit: on`,
which he had turned on himself — at a 1227×522 window he sized and the automation never
touched (rule 72). Mapping measured from a `pointerdown` probe, `viewport = pointer × 1.5667`
against 1.7111 the session before. Every press preceded by an `elementFromPoint` pre-check
that the control really was under the target pixel, and judged by its **consequence**.

| # | Control | Shown to have done |
|---|---|---|
| 1 | As it is | no `data-navname` at all — the default stamps nothing — and **2,309 → 0** `<wbr>` |
| 2 | Cut it | `clip`; **1,039 of 1,604** labels overflowing, worst 196px in a 104px box, ellipsis, one line |
| 3 | Wrap it | `wrap`; **0 → 2,674** `<wbr>` into rows *already drawn*; overflowing **1,039 → 0**; 15px → 45px |
| 4 | Fit the toolbar | note *"Fitted at 95%"* against a multiplier of **0.9538** — they agree (rule 13); ⚙ Settings 1363 → **1216**, inside a 1227 window |
| 5 | Version strip | 39 → **55px** off, and `.body` **426 → 409** — the second line's cost comes off the pane being read |

Number 3 is the one that mattered: the seams go into rows the navigator had already drawn,
nothing rebuilt it — **rule 78 observed rather than argued**, and the half a scripted handler
call would also have shown while proving nothing about whether the button could be hit.

**Then the screenshot found what none of the five measurements had.** In the navigator,
`disabled` is drawn as **`disable / d`**. Under `wrap` the label computes `overflow-wrap:
break-word`, so a name `jointed()` finds **no seam in** breaks at an arbitrary character —
**160 of 1,604** visible rows, `review` at six letters among them. The comment and the
Settings copy both promise *"the name's own seams (`do_ / POST`, not `do_PO / ST`)"*, which is
kept for a name that has seams and false for one that has none. Not fixed: it is a trade
between breaking anywhere, overflowing, and an ellipsis, and that is Tom's. Item 7 of the
scheduled pass.

*The first count was 375 and it was wrong — a one-line row is 17–19px here and the threshold
was 18. 375 have no seam; **160** are actually broken across lines.*

### The rail that could not be reached, and a fourth fit setting (2026-09-08)

Item 6 of the scheduled pass, filed as *"the legend rail does not restore the pane"*. **It
does.** Pressed with a real pointer, `data-legend` goes `off` → `on` and the rail re-hides;
a scripted click agrees and is idempotent on a second press; the navigator rail is the same.
The diagnosis was wrong and the symptom was real, which is **rule 39** in one line.

**What could not be done was reach it.** `.app` is a grid with one *implicit* column, and an
implicit column is `auto` — sized to the widest of its three rows. The toolbar does not wrap,
so its max-content width is the column's and therefore `.body`'s, and every rail on the
right-hand edge is carried out of the window with it. At `innerWidth 1220`, both panes
folded:

| | legend rail | inspector rail |
|---|---|---|
| as it ships | **1281–1309** | **1309–1337** |
| `paneFit` on | 1164–1192 | 1192–1220 |

Both are wholly outside the window at the default and `elementFromPoint` returns **null**
over either. They are still reachable by scrolling the whole page sideways, which is what
keeps this a preference rather than a repair — and **a rail is the only way back to a folded
pane** (design rule 24), which is what makes it different in kind from the overhang `topFit`
is about.

**Tom's call was design rule 2**: build both and make it a Setting, today's behaviour as the
default. So `paneFit` joins the three from earlier the same day and the family is now
**four** — in its own comment, in the Settings copy, and in the shared design-rule-29 guard.

Three declarations, and the middle one is the half that would have failed silently.
`grid-template-columns: minmax(0, 1fr)` bounds the column, which is the whole fix for
`.body` — 1336 → **1220**. `overflow-x: auto` on `.topbar` gives the toolbar back what the
column used to give it: **pinned and left alone the row does not run off, it gets taller**,
63 → 67 px as its items squeeze and wrap inside themselves, a third behaviour neither setting
offers. `flex-shrink: 0` on the children, because `nowrap` alone squeezes rather than
overflows — the version strip's own lesson one row up — and **`flex-shrink` rather than
`flex: none`**, because `.tb-searchwrap` still has to grow into a wide window.

**The two settings compose, and the specificity is why.** Every `[data-topfit="on"]` rule
that hands a child permission to yield is a class selector and outranks `.topbar > *`, so
with both on the toolbar shrinks to fit exactly as today and only what the 0.85 floor could
not absorb ever scrolls.

Verified at the pointer on the real control: `aria-pressed` true, the stamp on, document
1336 → 1220, `.body` 1337 → 1220, the toolbar's box 1220 with a `scrollWidth` of **1377** —
running off in its own row. Persisted, and the stamp survives a reload (rule 68). And the
sentence in the Settings copy was measured rather than asserted: scrolling the toolbar's own
row brings ⚙ Settings from 1285–1363 to **1127–1206**, inside the window, while `scrollX`
stays 0 and the inspector rail does not move.

*Item 0 was paid later the same day, and the reason recorded here first was wrong.* This
file said the pointer stopped arriving above a **floor that drifted** — y=45 landing and
y=40 not, y=88 failing after a reload on a page where y=109 had worked. That is a coherent
diagnosis and there is no floor: the automation's window had gone behind another one, and
`document.visibilityState` said `hidden` the moment anybody asked. A screenshot is captured
from the tab and a click is delivered to the screen, so every other instrument kept
addressing the right page while the pointer did not — and the tool reported success either
way (rule 76). **Rule 90** is minted from it. Struck rather than deleted, because the wrong
reason was acted on: the sentence *"⚙ Settings cannot be pressed at the pointer here"* is
false, and with the window in front it was pressed at the first attempt.

*And rule 88 was already minted the day before, so item 4 of that pass was closed before this
session opened. The entry outlived its own closure by a day.*

### The toolbar fit, reported from a real window and fixed (2026-09-08)

Tom, an hour after it shipped, with a picture: *"Toolbar icon text overlaps the icon on the
right when total window width is too small for them all. In this shot, the SOURCE DIRECTORY
and the Font Size are the worst two."*

**He was right, and it is `.navlabel`'s own defect wearing a toolbar.** `min-width: 0` is not
*be narrower*, it is **a licence to overflow** — and `topFit` handed it to `.tb-right` and
`.scale-group`, neither of which can absorb anything. The slider and `100%` were drawn through
*System* and *Settings*. The same mechanism the navigator setting in the same commit exists to
give a reader a way out of, reproduced by the fix for the toolbar. The rule is now written
where the licence is granted: **yielding is for things that have somewhere to put what they
give up.** `.tb-right` and `.scale-group` are `flex: none`; the slider yields instead, to a
`2.5em` floor (design rule 30 — a 2.5em thumb is still a thumb you can drag).

`SOURCE DIRECTORY` is a caption, not prose: two words in a narrow box wrapped, which made the
button taller than the row and pushed its value out of the bottom of its own rounded rect.
One line, eliding, opening the whole thing on click — which is what Tom proposed and what the
button already did.

**Three more, each found by measuring the fix rather than looking at it.** A clip cannot
shrink a box sized to its own content (`.srcpath` is a column flex, so `max-width: 100%` was
the missing half). A cap a later rule of equal specificity discards is not a cap — the value
carried `100%` and `11em` and source order threw away the one that mattered, **rule 29's
mechanism one stylesheet over**, now `min(11em, 100%)`. And an out-of-flow child does not
shrink with its parent, it **escapes** it: the search flags are `position: absolute`, so they
contribute nothing to a min-content width and hung out of the wrapper's *left* edge over the
revision menu — 4 px at 900, **50 px at 700**.

Measured after, at 1220 · 1000 · 900 · 800 · 700 · 620: **every pair that can touch is a gap,
worst −5 px**, the caption and value are inside their button at every width, and the button is
one line at 37 px of a 54 px row. Yielding alone still reaches a 700 px toolbar. Five
mutations, five catches.

*And the second screenshot — "the server could not be asked: Failed to fetch" — was **not** a
defect: I stopped the 8787 server as cleanup while Tom was reading it. Restarted immediately.
Recorded because the dialog is indistinguishable from a real fault, and because stopping a
server you started is the wrong move when somebody else is on it.*

### Three settings for what the window cannot fit (2026-09-08)

Tom's request, and his two calls on the mechanism: a Setting each for the navigator's names,
the toolbar, and the BASE row — **and today's behaviour is the default for all three**. The
toolbar *narrower first, smaller only for what is left*; the BASE row's alternative *one line,
clipped, scrolling*.

| setting | default (today) | the alternatives |
|---|---|---|
| `navName` | **As it is** — a long name paints over its count | **Cut it** · **Wrap it** |
| `topFit` | off — the toolbar runs off the window | on — it yields, then shrinks |
| `verStrip` | off — the strip wraps to a second line | on — one line, clipped, scrolling |

**Measured on this window, 1,404 navigator rows with their counts drawn:**

| `navName` | paints outside its box | of those, onto the count | worst | on two lines |
|---|---|---|---|---|
| `over` **(default)** | **374 of 1,404 — 26.6%** | **268** | **56 px** | 0 |
| `clip` | 0 | 0 | — | 0 |
| `wrap` | 0 | 0 | — | 414 |

*The 26.6% is this window's own number, retaken rather than carried (rule 24) — the record's
24% was a different window, and the same measurement with the counts **not** yet drawn gives
11.4%, which is why the condition is stated beside the figure.*

**Both objections the stylesheet raised turned out to be answerable, and that is the whole
reason these are worth building.** *"Truncating would hide a name with nothing beside it"* —
a routine row is `data-card`, so its hover card already carries the leaf **and** the qualified
name. *"`do_PO / ST` is worse than small type"* — true of a break chosen by where the box
ends, which is the argument `breakable()` was written from one surface over. `jointed()` marks
the seams with `<wbr>`, and the screen shows
`open_graph_composition_` / `read_backend` with its `1←` still on the first line.

**The toolbar setting is two halves and the second is not optional.** `.app` is a grid with
one implicit `auto` column and **no `min-width: 0` on its children**, so the widest of the
three rows sets the width of all three. A toolbar that only shrank itself would sit inside a
page still 1336 wide with Settings still off the edge — design rule 16 arriving from the
layout. Measured at `innerWidth 1280`:

| | off (default) | on |
|---|---|---|
| document width | **1336** | **1280** |
| ⚙ Settings' right edge | 1323 — **43 px past the window** | 1266 — **14 px inside it** |
| what shrank | — | **nothing**: `--topbar-fit` stayed at 1 |

**Yielding alone carries it to a 820 px toolbar** with no type change at all. Below that the
multiplier takes over: 87% at 700, and the clamp at **85%** from 600 down. It says which:
*"Fitted at 87% and 20px still will not fit — something in this row has a width it will not
give up"* is a different sentence from *"85% — as small as this may go"*, because they send
the reader different ways (rule 13 — the first version claimed the clamp at 95%, and the clamp
had not fired).

**The BASE row's trade, measured with a comparison running:**

| body width | wraps (default) | clips (on) | height returned to `.body` |
|---|---|---|---|
| 1280 | 34 px, one line | 34 px | — |
| 900 | **55 px, two lines** | 39 px, 345 px scrolled | **+24 px** |
| 700 | **77 px, three lines** | 39 px, 545 px scrolled | **+46 px** |

Design rule 29's distinction was checked rather than asserted: under `clip` the assumption
button sits at x=831 in a 700 px strip, and **focusing it scrolls the strip 545 px**, brings it
to x=286, and `elementFromPoint` returns the button itself. `display`, `visibility` and
`pointer-events` are untouched — which is exactly what `visibility: hidden` would have broken.

### The defect the looking found, and it is the one rule 47 exists for

**`data-navname` was both the stamp on `:root` and the route on the control**, and
`$$("[data-navname]")` walks the whole document — so the moment a reader chose anything but
the default, the setting's click handler was bound to `<html>` and **every click in the
application ran it**. While a value was stamped that was merely redundant; the moment they
chose the default again the attribute was *removed*, `dataset.navname` became `undefined`, and
the next click anywhere stamped `data-navname="undefined"` on the root — a value no rule
matches, from a setting the reader had just set correctly.

`data-palette` / `data-palette-set` is the shape and its comment says exactly this; the route
is `data-navname-set` now. **`test_a_pane_track_attribute_is_never_also_a_route_attribute`
could not see it**: that guard covers `PANELS`' fold attributes, and settings stamps are a
different family. The new guard asserts the rule over both — no attribute written to
`documentElement` may also be a selector this shell binds a listener to.

*It was found by looking at the DOM, not by a test, and its own wreckage is in this record:*
the usage counter had `navname:undefined: 120` and `navname:clip: 239` against 11 real
choices. Those counts were cleared from `dunneflow:mensores:v6` before the session ended,
because design rule 2 retires a setting on exactly that evidence.

**A second defect, from the same look.** `dressNavItems()` runs from `buildNav()` and at boot;
nothing rebuilds the navigator when a centre-pane setting changes, so choosing `wrap` stamped
the stylesheet and left every row on screen unmarked — the name broke wherever its box ended,
which is the picture the setting exists to avoid, produced by the setting itself. Rule 78. It
is idempotent now and the control calls it. **And a third:** the fit is a ratio against the
window, so it was stale the instant the window moved; `fitTopbar()` joined the resize handler,
which is rule 78 again with the window as the control.

*Nine guards, every one mutation-tested* — reverting its own half fails it and nothing else.

*What could not be done this session: **the pointer.** `resize_window` reports success and
then no synthetic click reaches the page at all, in that tab or any tab created afterwards —
rule 72, and the same tool the record already warns about. The pluralisation work earlier in
this session **was** verified at the pointer, before any resize, so the tell is clean. Every
control here was driven through its own handler and every number is a measurement off the live
page, but a scripted click proves the handler and only a pointer proves the path to it (rule
48). The three toggles are `id`-bound like their six siblings, so `selfCheck` cannot see them
either — which is why each has a guard naming its id.*

### The counts that can be one, and there were eight of them

The scheduled item read *"two pluralisations, `1 boxes` and `1 call sites`, need nobody"*.
There were **eight**, seven of them in one sentence, and the entry named the two that had
been seen rather than the ones that are there — so measuring first was the whole of the work
(rule 24).

| the sentence | how often it is one, on Mensores 2026-09-08 |
|---|---|
| `N boxes` — the compartment picker's every option | **8 of 53** compartments hold one box |
| `N routines` — the second level, of an opened box | **97 of 250** boxes hold one routine |
| `N other boxes` — what it crosses to | **43 of 250** |
| `N flows within` | **24 of 250**, and 3 of 53 compartments |
| `N other compartments` | 2 of 53 |
| `reaching N boxes` · `N arrows drawn` | 2 of 53 carry one entered box |
| `N call sites` — a kept arrow's note on the shelf | **116 of 476** arrows carry one call site |
| `N touches` — the same note | 17 of 476 |

`crossing` is deliberately **left alone**, and that is the one judgement here rather than a
transcription: it is a reduced relative — *"5 [flows] crossing to 2 other boxes"* — and reads
correctly at one. `${id.weight} along it` beside the note needs nothing either; there is no
noun in it. Both are stated in the guard rather than left for the next reader to rediscover.

**Two guards, each mutation-tested against the defect it was written for**, on the precedent
of `test_a_file_band_states_a_count_of_one_in_english` — which had already earned this lesson
one surface over. The diagram-head guard is over the **shape** and not over a list of nouns:
every `<b class="num">…</b> word` must choose its own ending, so a count added to that
sentence later fails it. The noun is the **last** word of the phrase and not the first, since
`other box${…}` counts boxes and reading `other` as the noun passes *"1 other boxes"* — the
first version of the guard did exactly that and was caught by its own run.

*And one guard broke, correctly.* `test_the_diagram_head_says_which_altitude_it_is_at`
asserted the literal `"routines ·"`, which the interpolated plural dissolves. Its marker is
now `</b> routine` — the noun beside its own count, which is what the assertion always meant.

**Seen at the pointer, not only tested.** `conventions ▸ _schemas.py`, opened by a real
double-click, reads ***"1 routine · 1 flow within · 1 crossing to 1 other box"***; `_config`
reads ***"1 box over 3 routines"***; and the picker lists ***`CRYPTO — 1 box`*** through
***`_config — 1 box`***. The arrow `frontmatter.py → _schemas.py` was kept and sits on the
shelf as ***"1 call site, 0 touches"***, then dropped — `dunneflow:mensores:v6` back to zero
pins. **Rule 83's pointer factor re-measured this session: `pointer = css × 0.641`**, so
`css = pointer × 1.560` — near the 1.5581 of two sessions ago and nothing like the 1.0 of the
one between. Measure it every session; it is a property of the window.

*One thing noticed and not acted on:* at `innerWidth 1224` the page's `scrollWidth` is
**1336**, so the inspector's own controls sit off the right edge and the document scrolls
sideways. That is below Tom's real window and above the 1088 breakpoint the navigator band
uses, so it is a third band nobody has looked at. Filed below, not fixed.

**Four defects were outstanding, and the record had two of them by half.**

| | |
|---|---|
| `navIds` split every row's ids on a space | filed as latent, and it was — but the fix is a row that *says* it carries several, not a separator no name can contain |
| `holds` had no default, so the fold pane's section started closed | **three** keys were in that position, not one: `holds`, `stands` and `calls`, each the answer its pane exists to give |
| a constraint was being read as a definition | `1 ≤ len ≤ 5000 chars`, glossing the word *definition* on the glossary page |
| the undefined list's head was fragments of constant names | 889 of 1,154, with `witness` and `posture` and `claim` buried under `DDL`, `EXTRAS`, `BYTES` |

**The two shell defects came with the guard that found the other two.**
`test_every_inspector_section_declares_its_default` reads the `sec("…")` keys out of the
shell and requires each to be named in the settings — written because a note about one
section had stood for six days while two more joined it silently.

**A constraint is not a definition, and the judgement is on the opening.** A gloss that
*begins* with a bound, a bare type, a regex or a placeholder value states a shape; a
sentence that reaches a number partway through is prose. Measured over all 240 definitions
Society yields: **5 refused**, every one a field constraint, and the three definitions that
quote a bound mid-sentence kept. The rule is in `detectors/docs/prose.yaml` and refused in
`_add_def`, the one place every definition of every form passes.

*The section rule was measured and deliberately left standing.* A heading that merely
mentions the glossary still admits definitions — 29 of these came from
`"AC-19: Performance budget for glossary tools"`. Requiring the word to head its phrase
drops **77 of 240** and takes 60 defined terms to 58. Tom's call, on the numbers: refuse the
constraint alone.

**A word is not a fragment of somebody else's constant name.** Three conditions: never the
whole name of anything, only ever inside a constant's name, and **nothing defines it** —
which is why 889 words leave the worklist and no defined term goes with them. Measured after
the constraint fix: **59 of 324 defined (18%)** against 60 of 1,214 (5%), **265 undefined**
headed by `DDL`, `witness`, `posture`, `claim`, `probe`, and **890 held back**.

**Held back, listed, and every one offered back** — Tom: *"offer a chance to promote them
back to the list manually… a term might appear such as MENSORES_MAX_LEN, where the MAX and
LEN are modifiers but MENSORES has real meaning."* The report lists all 890 with the reason,
the command says how many and where, and the dashboard draws a **Held back** band where each
word says *a word*; persisted per program beside `triage`, with *hold back* on the way out.
The worklist and the band are one split read from its two ends.

**Looked at, and the looking found the fifth commit.** In three CSS columns a button
labelled *"it is a word"* wrapped onto three lines and made every row a different height —
890 of them. No test could have said so. Verified at the **pointer**, which is the half a
scripted click cannot reach: promoting `EXTRAS` moved it from 890 held to 266 undefined and
wrote `{extras: true}` into `dunneflow:mensores:v6`; *hold back* undid both. Eight views
walked, no console error, self-check reporting every control wired.

### The stale-text pass, and it found two sentences arguing with their own pages

Tom scheduled it as the third pass, and the figures were the smaller half. Retaken rather
than carried (rule 24): rule citations **2,775 → 2,832** over 107 files, definitions mined
**235 → 230**, glossary citation buttons **92 → 91** — the lost one being the constraint gloss
on the word *definition*, which is the fix working rather than the feature regressing.
`PERFORMANCE.md`'s 999 ms row is deliberately **not** retaken and says why: its 1,214 terms
are now drawn in three lists rather than two and the population is exactly unchanged.

**The larger half was two claims about a capability, written as fixed prose.** The glossary
page said *"Documents are scanned but not stored… cannot be opened here"* — true until
2026-09-04, false since, and still printed above 31 documentation citations that open. The
stated-rules lane said *"DunneFlow does not yet run one"* — careful when it was written, false
since `conformance.py` began running exactly those on 2026-09-06. Both now read the thing they
describe: the first from the same `SIDECARS` block the buttons are drawn from, the second by
naming the lane that answers instead of claiming the answer. Neither was catchable by a test
that did not know the sentence existed, which is why both are now guarded by name.

*The shape worth keeping:* a sentence stating what the tool **can** do is a claim, and rule 13
applies to it exactly as to a number — it has to be readable off the thing that decides it.
Both of these were prose beside a control that already disagreed with them.

### What the rebuild cost, and it is worth knowing before the next one

The documentation rule moved `doc_rules_fingerprint()`, so the pair had to be rebuilt — two
analyses and a seal, exactly as this file says. **What this file does not say is that
`standards.db` is a document store too.** It went stale with the rest, and `serve` refuses to
boot on it: *"written by a different version of DunneFlow"*, before a single page is served.
The recipe is now three commands and the third is `--standards`, which is written into the
Commands section above.

*Candidate rule, for Tom to mint or refuse:* **a rebuild recipe must name every store the
change invalidates, including the ones nothing else mentions.** Rule 12 says a cached fact is
only as good as the tool that read it; this is the other end of it — the recipe that repairs
the staleness has to be as complete as the fingerprint that detects it.

~~**One thing is left undone and it needs a hand.**~~ *Closed 2026-09-08 — Tom ran it.*
Dropping the superseded sealed snapshot is a manual pass by design (`sourcedb.py` owns no
`DROP`, and `test_source.py:171` asserts it): the two `.db` files went first, and the
**sidecar rows** needed the one command this entry carried. Verified — both sidecars now hold
exactly the two live snapshots, `2026-09-08T13:39:50Z` (628 paths) and `2026-09-07T15:32:31Z`
(625), and `2026-09-07T14:55:40Z` is gone from `paths` and `revisions` in each.

### The plates, ordered by what they link to (2026-09-08)

Tom's request: the force layout improves *verticality* using the shadow nodes — can the same
mechanism minimise vertical **distance** and choose the plate order? **Not that mechanism,
but yes the idea.** Plates as springs on a line, relaxed and ranked, is `forcelayout.js` one
dimension over and gives **-11.3%**; searching the *permutation* directly — weighted minimum
linear arrangement — gives **-82.8%**. Same evidence, different solver, and `plateorder.py`
says so rather than letting the next reader assume one mechanism does both.

| how far a crossing travels | by size | by what they link to |
|---|---|---|
| the plate next door | 190 (3.7%) | **1,724 (33.8%)** |
| **21 or more plates** | **3,738 (73.3%)** | **121 (2.4%)** |

Mean crossing height **30.78 → 5.31** plates over 5,101 crossings; module level -74.1%. **And
the picture says it without the numbers**: the stack stops being a funnel and becomes a
*spindle*, the hubs pulled to the middle where everything can reach them and the leaves sent
to both ends.

**Both variants are built and `by size` is still the default** — Tom's two calls. Interleaved
puts `ext:DATABASE` beside `storage`; grouped holds packages above externals and keeps 31.5%.
The control says **"by what they link to"** and never *"by connection"*, which the
plate-layout button already means about something else (rule 71). `/api/plateorder`, on demand
and held on the base: 1.50 s cold, 10 ms warm, keyed on level, threshold and grouping (rule
81).

**The control it joined did not order plates**, and that had to be fixed first. `sortMode` was
read only in `sortedDisks()`, called only from `renderLegend()`, and the handler never handed
the engine an order — so *by name* and *by kind* renumbered a legend and left every plate
where it was. Invisible because the default very nearly agrees with `defaultOrder`; the two
disagreed even at boot. `applyOrder()` is the missing half, called from the one handler rather
than each branch (rule 78), and fixing it repaired the other two modes as a side effect.

*Three instrument failures on the way, and the lesson is one line:* **when a result looks like
the code is broken, check the instrument first — twice out of three times it was.** A
mis-dispatched `change` where the handler listens on `input`; a cached `<select>` reference
that `renderLegend` had already replaced; and rule 83's pointer factor, **1.0 in this window
against 1.5581 in the last**, so it is a property of the window and must be re-measured every
session.

### The looking pass, which answered two questions and asked three

**A kept fold and a kept flow both open from the shelf**, verified at the pointer in
`pkg:standards`. The fold returns to Diagram mode and its compartment, outlines the box, lits
its routines and files a trail step; the flow fills the inspector with the arrow itself —
`class → file`, *1 along it*, the call site with its argument bound — and lights both ends.
Opened from a *different* compartment, `PIN_ROUTES.flow`'s stated limitation holds exactly as
written: nothing lights, the inspector opens on the arrow, and nothing false is said.

**The hover card's shadow sentence is dead code, and rules 23 and 31 are what killed it.**
*Withdrawn 2026-09-08 on Tom's call — this is the finding as it stood.*
*"A stand-in. This routine lives on X — the copy you are pointing at is a placement device"*
was drawn when `h.shadow` was true, which is `raw2.shadow[i]` at the **picked** index. A shadow
is given radius 0 and alpha 0, so it is never drawn and never picked — **1,989 picks over 562
distinct nodes returned not one**, against 5,855 shadows in the payload — and the only other
path in, the rim arrow, builds every mark as `realIndex(...)` under a comment citing those
same two rules. The reticule over the top is `pickable: false`, so there is no third path.
Design rule 16 from the far side: the branch rendered for nobody *because the rule it describes
was applied correctly everywhere else*. **Withdrawn**, along with the payload field — the
*resolution* stays, since that is what makes rules 23 and 31 true from that handler. A guard
asserts the two facts that closed it **before** the consequence, so a level that ever draws a
shadow fails at the fact rather than at the deletion.

*The instrument could not have shown this either way, and that is worth knowing.* deck.gl's
own `pickObject` answers correctly at every one of those points; what fails is the extension's
synthetic `mousemove`, which never becomes the `pointermove` mjolnir listens for. **The hover
card cannot be verified at the pointer with this instrument at all** — which is what
`e60c050` was really recording. Rule 72.

**And the thing nobody scheduled: 335 of 1,395 navigator rows print their name over their
counts** — 24%, worst case 101 px of overprint where a 62 px box holds 170 px of text.
`_schema_validator` runs straight through its own `1← 1→`. **Rule 53**: the remedy in the
stylesheet is two shrink classes chosen from the **character count alone**, and the budget is
not a property of the name — `.navsub` takes up to 11rem, so the room left swings from ~200 px
to ~68 px on how long the *module path* is. 65 of 84 `xlong` rows still overlap and so do 103
rows carrying no class at all. `selfCheck` only inspects `[data-fit]` elements and a
`.navlabel` has none, so it reports every control wired.

**Tom's call, taken the same day: let the module path yield its width first.** `.navsub` was
`flex: none` at up to 11rem — a fixed cost the name had to fit around — and is now `flex: 0 1
auto` with a 4rem floor, keeping the ellipsis it already had. It is the one field in the row
already built to lose its head, so nothing that was not already designed to be shortened gets
shortened. Measured as a controlled pair, one declaration toggled on one page:
**335 rows / 101 px → 266 / 49 px** at the declared 21rem; 1,037 → 951 at 16rem; and
**almost nothing at 12rem**, where the name alone is wider than the row.

**A fifth better, and still open.** The remainder needs a decision about the *name* — wrap,
truncate, or let the row grow (rule 84) — and each is rejected by one of the two comments over
`.navlabel`. `navWidth` was widened from 14.5 to 21 with the note *"a qualified name is the
thing it has to be able to show"*, and 266 rows still say it cannot.

*And a band nobody had looked at:* `@media (max-width: 1088px)` drops the navigator to
**12rem**, where 1,289 of 1,346 rows overprint and this fix buys four of them. **Check
`innerWidth` against 1088 before trusting any navigator figure** — two of this session's own
numbers were taken either side of it and read as a fourfold regression that was not there
(rule 24).

### And the maps in `output/`, three of which refused and were sent to the wrong command

The scheduled item read *"two maps cannot be opened, both refusing exactly as designed and
both one command away."* **Three refused, and the command was not one away.**

`Store._refuse_if_stale` exists to name *which* of two fixes applies, and its reasoning is
right: a graph written before paths went relative needs `migrate`, which rewrites in place
and keeps a sealed snapshot whose source tree may be long gone. But it tested
`paths_are_relative` — *when* the store was written — where the migration tests
`_require_previous`, which admits **one** fingerprint on the claim that making paths relative
is the only thing that changed. Two facts, one test. Every store older than that single
version was told to migrate, and the migration refused it in turn: rule 49's shape in prose.

`migration_speaks_for` is now in `migrate.py` beside the gate, and both refusals ask it —
the graph on `PREVIOUS_CODE_EXTRACTOR`, the document store on `PREVIOUS_DOC_EXTRACTOR`, the
compared value the only difference (rule 51). It tests the fingerprint and **not** the
recorded root: that root is read per revision from a graph which may not be the store being
refused, and it is reachable only past this gate — so a store admitted here and refused there
is told the truth twice rather than plausibly once. The old guard built its legacy store
*with* the gated fingerprint and still passes; the new one stamps an older fingerprint and
asserts `migrate_program` would in fact have refused it (rule 13).

**`dunneflow` and `beads` were then re-analysed and both open** — 71 files and 849 routines,
14 files and 239. `beads` is a **Go** program with 30 Python files, so it was always a probe
rather than a subject; a probe that lists in the selector and refuses is still worth one
command.

**The fourth is a decision, and it is open.** `output/mensores@2026-08-29T19-43-39Z` is an
old-style directory whose *name* is a revision stamp from before the revision layout, and its
`source_root` is `mensores-overhaul` — the third tree `CLAUDE.md` warns is neither end of the
pair, and which cost a wasted analysis once already. Re-analysing it would re-read exactly
that tree into a directory named after a layout that is gone. **Drop it, or leave it listed
and refusing?** Tom's call; nothing is broken either way, and the refusal now names a command
that would work.

### Before that: the plates, coupled and framed (2026-09-07/08)

Four commits that were built and never recorded here; `CLAUDE.md` and `PERFORMANCE.md`
carry them in full and the commit messages carry the reasoning.

**A second layout, and `layout.py` had named it in its own docstring since the day it was
written.** Fruchterman–Reingold per plate, seeded from the spiral, in a WebGPU compute
shader with a web-worker fallback: **89 ms against 9.7 s**, and 328,531 edge crossings down
to 27,291 on the busiest plate. A toggle on the panel that arranges plates, so design rule 2
holds: both layouts are built and the reader chooses.

**Then Tom asked why the links between plates are not vertical**, and the answer was that a
shadow took part in its plate's forces and nothing pulled back. Coupling every slot that
stands for one entity toward their common middle doubled the upright crossings; **one
coordinate frame for the whole stack** took them to 3,878 of 5,101 and co-located every one
of the 4,050 entities to a spread of exactly zero. It costs the within-plate reduction —
about 90% down to 75–83% — and Tom took that trade on the numbers.

**A plate is no longer centred on the stack axis**, which three things assumed, so the
plate's circle is now reported by the layout and read by the outline, the rim arrow and the
framing alike (rule 51).

### Before that: the review worklist, closed (2026-09-07)

Six findings, and F1 is the one a reader was being lied to by: `_r_about` took the sidecar
inside the lock and queried it after the block closed, so `/api/about` and `/api/revisions`
— fired back to back at boot — shared one SQLite connection. 2 of 60 concurrent reads came
back wrong and the topbar printed *"no sidecar here to ask"* over a map whose sidecar holds
the name. Rule 49 exactly. The guard that watches for it looks at where a store is *used*
rather than where it is read, because an alias carried past the `with` was invisible to the
one that already existed.

The other five: the node-shape orphans withdrawn with the view that drew them, a second
serialiser of a model with one serialiser, the structure bands given the denominator they
were already computing, two measurements that now explain themselves, and four unreferenced
functions. `detectors/__init__.py` was left alone deliberately — deleting one dead predicate
there changes `rules_fingerprint()` and discards every graph on the machine.

### Before that: ALGORITHMS chunk 6, and the pause it ended on

**Paused 2026-09-07 after ALGORITHMS chunk 6. Nothing is half-written.** Five commits,
1,187 tests, mypy clean over 120 source files, ruff clean, `check` 0 broken, working tree
clean, no servers running. `output/mensores` holds exactly the pair at `SCHEMA_VERSION` 9:
`2026-09-07T15:32:31Z` (628 files, Society at 08-29) working, `2026-09-07T14:55:40Z` (625,
at 08-26) sealed.

**ALGORITHMS is complete, and chunk 6 corrected the feature's own headline on the way.**

**The detector, as recorded, reported its own blind spot.** `LOOPED_BOUNDARY` read as
`net_calls` inside a loop fires twice on Society, and both are `wait_until_serving` —
`while True:` poll loops with a deadline, which is the blind spot the record itself names.
Two of two findings would have been false. Measuring it before building it is what
`CLAUDE.md` asks for, and it is what turned this into a different session.

**An iterable is not a body, and 11 of the 261 rates were not rates.** `for row in
conn.execute(q).fetchall():` runs one query, not one per row — but it is written on a line
inside the loop's own span, so `line BETWEEN line_start AND line_end` read it as a rate and
said *once per pass* about it. `ControlPoint` now records the lines a loop evaluates once,
and it is **the iterable's lines minus every line a repeated part also occupies**: the
iterable's span alone reclassifies 45 loops and 34 of them wrongly, because a one-line
comprehension writes its element and its iterable on the same line.

| | Was | Is |
|---|---|---|
| loops + comprehensions reaching a boundary | 219 + 42 = 261 | 211 + 39 = **250** |
| bands over 1,950 loops | 261 · 467 · 1,222 | **250 · 470 · 1,230** |
| significant of 9,625 points | 797 | **786** |
| rates at depth > 1, and inside another loop | 104 and 10 | **98 and 9** |
| the four lanes' rows | 804 *and* 803, in different files | **793** |

**Three surfaces were saying it and one of them was already right.** Checking the four SQL
statements against the resolver over all 64 tables found two disagreements, and the SQL won
both: `shape.enclosing` — chunk 5's *"and vice versa"* half — still counted a loop's own
iterable, so a table's pane said *"reached from inside 1 loop"* about a query the loop is
written over. Also fixed: the ribbon gated its `why` sentence on `significant`, so the 11
corrected loops lost the explanation they most needed.

**`LOOPED_BOUNDARY` is in, at 35 of 74.** The other 39 say how many passes they make and
are named in the detail rather than dropped — 29 over a collection this program declares,
4 over a literal at the loop, 6 on a `while`. INFO/PROBABLE, never SUSPECT, with four
measured blind spots including the one it cannot see past: a local SQLite file is not a
network.

**Every outstanding rule candidate is minted.** Tom: *"Accept and mint all outstanding
rules."* That session left **86 engineering rules numbered to 87** — 21 still does not
exist — and **30 design rules**. *(88 and 89 joined them on 2026-09-08; the live count is
in the table at the top of this file.)* There were six, not the three I first reported: sweeping
the record for *every* unminted candidate rather than the ones I had in hand found three
more, two of them standing since 2026-09-06.

| | |
|---|---|
| **83** | an instrument's two coordinate systems can differ, and the one you can see is not the one you touch — raised 2026-09-06, measured 2026-09-07, and it had cost four sessions |
| **84** | a grid does not overflow, it grows a row |
| **85** | a span cannot tell what a loop is over from what it does — this session's, and the one with reach: anything derived by containment inherits it, which `shape.enclosing` proved while the fix was being verified |
| **86** | a guard can only see that a function was called, never what it returned — the `minDisk=null` defect, which no source check could have caught |
| **87** | a derivation from the picture is only as available as the picture — rule 13's own cost, and the trap you fall into while obeying it |
| **design 30** | a dimmed control still acts — Tom's sentence, and design rule 29's companion |

86 and 87 were checked against rules 37, 42, 44 and 13 before a number was taken, on the
2026-09-05 precedent: a rule that restates an existing one would spend an address on
nothing.

**The stale snapshots are gone, by hand, and the tool still cannot do it.** There were
five, not four — a rebuild adds one each time. `dunneflow revisions --drop` was built and
proved, then reverted: `test_source.py:171` asserts against the source text that
`sourcedb.py` owns no `DROP`, on the grounds that *a store whose whole job is to be the
thing that survives has no business owning one*. Tom's call was to honour the guard and
drop by hand this once, so **the next accumulation needs the same manual pass**. Bodies
were left alone, which is the store's own behaviour rather than a shortcut.

### Before that: chunk 5, the links back

**Paused 2026-09-07 after ALGORITHMS chunk 5. Nothing is half-written.** 1,177 tests, mypy
clean over 120 source files, ruff clean, working tree clean, no servers running. `output/`
is unchanged — this session wrote no maps.

**ALGORITHMS is complete but for chunk 6.** Chunk 5 is the *"and vice versa"* half Tom
named when he asked for the feature, and it is in: a table and a boundary each say what
loops over them and open the list, a routine's pane carries its Shape, two threads lead to
code that runs the same shape, a loop can be **kept**, and two curiosities measure it.

**A table is a subject now, and that was a defect rather than a feature.** Selecting one
fetched the routines that touch it and *threw the table away*, so the crumb named a table
and the inspector answered about whichever routine sorted first. `web/table.py` on
`plate.py`'s model, and `state.dbtable` — never `state.table`, because `state.mode ===
"table"` is the centre pane's routine table.

**Two things Tom found by looking that no test would have.** *Shape locked on to the last
routine viewed* — the bag was keyed from the day it was written and no renderer read the
key, and `ensureShape` was invited from one branch, so the new inspector section was wired
to nothing (design rule 16). Both fixed the way the 2026-09-03 session settled: the
reconcile runs from `render()`, every early return empties the bag, and both renderers read
the key.

**What is left: chunk 6**, the detector. `LOOPED_BOUNDARY` in `anomalies.py` — a remote
call inside a loop, INFO or SUSPECT and never BROKEN, with the two blind spots that make it
honest: *the iterable may hold one item, and nothing static can count it*, and *a retry loop
is this shape on purpose*.

**Still waiting on Tom's eye**, and now more than before: the **instrument cannot show the
inspector at all**. The capture is a fixed 784 px of a 1,200 px viewport, `resize_window`
does not move the page viewport, and the pane sits at x=848 whatever is collapsed. Every
layout claim about the table pane this session was **measured in the DOM, not seen**. Also
open: the worklist's and ribbon's row layouts, and whether *"a grid does not overflow, it
grows a row"* and *"an instrument's two coordinate systems can differ"* are rules or notes.

### Before that: chunks 2 to 4, and four sealed snapshots the schema bump left behind

**Paused 2026-09-07 after four commits. Nothing is half-written.** 1,145 tests, mypy clean
over 117 source files, ruff clean, working tree clean, `check` 0 broken on
`output/mensores`, no servers running. ALGORITHMS chunks 2 to 4 are built; 5 and 6 are not
started.

**`output/mensores` changed, and in two ways worth knowing.** The pair is rebuilt and
resealed at `SCHEMA_VERSION` 8 — `2026-09-06T21:37:35Z` is Society at 08-26 (625 files),
the working `2026-09-07T00:01:16Z` is 08-29 (628). And the **four older sealed snapshots
are now stale**: two at schema 6, one at 6, one at 7, all of them 08-26 under the same
label. They open as a refusal with the store's own sentence, which is correct behaviour
(rule 20 — a read may refuse, it may never repair) and is also clutter accumulated by four
rebuild dances. Whether to drop them is Tom's call: a sealed snapshot exists to outlive its
source tree, so nothing here deletes one on its own.

| Commit | What |
|---|---|
| `9bf688d` | **chunk 4** — the ribbon, and a place is not two things because it was written down twice |
| `22667dc` | **chunk 3** — the worklist, and a row that names its own step |
| `4bdc0e8` | **chunk 2** — the join, the judgement, and the arm that carries them |

**The feature, in one sentence Tom can check:** the navigator's **Algorithms** group lists
the loops and decisions this program is worth reading — 261 rates, 78 forks, 69 ladders,
396 recoveries, 0 `match` — and the mode toggle's **Shape** draws any routine's whole
outline, guards included, nested as it is written.

**The judgement lives in one place** (`resolve/shape.py`, rule 51): *a loop or a decision
is a subject only where something moves inside it.* Nothing is dropped for failing it —
three bands, a `why` on every point, and the quiet numbers stated on the page, because it
is the 1,222 loops that move nothing that make the 261 credible.

**The arms were the missing fact.** A point says a decision has four ways out; only an arm
says which one writes. `control_arms`, 4,125 of them over 9,625 points, recorded only where
a point has more than one way through it — and they are the *bodies*, so a boundary reached
from inside a test belongs to the decision and to neither arm.

**Three figures were corrected, all in the same direction — the plan reasoned, the store
measured.**

| Was | Is | Why |
|---|---|---|
| 80 forks | **78** | the plan's script counted each `elif` tail as a ladder of its own; then places, not rows |
| 10 nested, from `depth` | **10, from containment** | `depth` counts every enclosing `if` — the two answers are 104 and 10 |
| 742 handlers touching | **750** | the plan measured two spans; the store measures the `try` |

**A place is one act; a row is one description of it.** An `INSERT` is a `DATABASE` row and
a `SQL` row on one line — 569 of Mensores' 991 SQL operations are such a pair — so counting
rows said *two things move here* about one write, in the sentence that gives 33 of the 261
rates their number. `places()` is the one place a count is taken now.

**Two defects found by looking, not by testing.** One pointer click on a worklist row filed
**two trail steps** — the dispatcher's step landing on the subject being left, which on a
page of its own is nothing, so nothing could deduplicate it (rule 33's fourth variant). And
the ribbon's line numbers stepped right with the indentation, under a comment of mine
saying that is exactly what they must not do.

**What is next: chunks 5 and 6.** Chunk 5 is the links back — a table's pane saying
*"written from inside 3 loops"*, threads for *other loops over this table*, a `PIN_ROUTES`
kind so a loop can be kept, two curiosities. That is the *"and vice versa"* half of what
Tom asked for. Chunk 6 is `LOOPED_BOUNDARY` in `anomalies.py`, with the blind spot that
makes it honest.

**Waiting on Tom's eye:** the worklist's row layout and the ribbon's, both of which are
design calls; and whether *"a grid does not overflow, it grows a row"* and *"an
instrument's two coordinate systems can differ"* are rules or notes. The second is now
measured rather than suspected — clicks are in the screenshot's frame, `zoom` regions are
in the page's, and the pair differs by the device pixel ratio.

### Before that: the trail names its own hops, and a grid that grew a row (2026-09-07)

**Paused 2026-09-07 after two commits. Nothing is half-written.** 1,103 tests, mypy clean over
113 source files, ruff clean, working tree clean, `check` 0 broken on `output/mensores`, no
servers running. `output/` is unchanged — this session wrote no maps.

| Commit | What |
|---|---|
| `3df8730` | **a trail step takes the name of the move that files it** — seven callers, and the open entry describing it was wrong |
| `a7ea9ba` | **a search hit's keep button gets a cell** — the looking debt from 2026-09-06, paid, and the columns were wrong |

**The open entry was wrong, and measuring is what said so.** It read *"clicking a change row
files two trail steps"*. No path files two, and **the change row is not among the affected
paths at all** — it sets its subject synchronously, so the dispatcher's step lands correctly;
verified by clicking one. What is real is quieter: opening the kept cohort `AC-4`, which opens
112 routines, filed a step called **`resolve_cli_invocation`** — one arbitrary member — and
wrote *"a plan or decision id"* onto the `kept things` step the reader was **leaving**. A
sentence about one subject printed under another, in the surface built so a detour does not
cost you your thread.

**A caller about to move now names the step the move will file, and never files one of its
own.** `selectFromNav(want, name)` and `followThread(subject, name)` carry `{label, note}` to
the one recorder, so there is one step, named when it is made. Both orders lost before: filed
*before* the move a step carries the subject being left and donates only its note; filed
*after* it lands on the step the move already made and is dropped whole. The note-adoption
branch is **deleted** rather than kept — it put the note on the right step and about the wrong
thing. `NAV_NAMES_ITSELF` declares the one navigator route that fetches before it selects
(rule 30), because the dispatcher names a step *after* calling a route.

*A seventh caller was found by sweep rather than by the entry:* the glossary term row mints
the same cohort a thread does, and `mensores` opens 628 modules — one of them standing in for
the word is rule 74 in the trail.

**Seen on all six affected paths and the three that were already right.** `AC-4` reads `AC-4`
from a panel and from the shelf, a glossary term reads `quaestor — 45 modules, 1 constant`, a
table row is named for the table, and a routine, package and change row each still file
exactly one step. Back and Forward still walk it.

**The looking debt is paid and the columns were wrong.** `.srch-hit` declared five columns for
five children — and `.srch-in` spans `2 / -1`, so it fills the rest of its row and anything
after it starts a new one. The keep button added in the previous session flowed onto a **third**
row into the 3.2 rem line-number column: **51 × 54, "Keep this" wrapped onto two lines**, under
a 17 px line of code, on every one of 126 hits — 101–108 px of pane each. Now 78 × 22 on the
code's own line, rows 45–53 px. Nothing reported it and nothing could, so the new guard asserts
the *rule* — after a child that spans to the last column, every later child is placed by hand —
and matches the button by its `pinBtn(` call, because a child a source scan cannot see is the
one that gets forgotten when columns are counted. **The placement is Tom's to change.**

*Minted 2026-09-07 on Tom's call:* **rule 84 — a grid does not overflow, it grows a row.**

### Before that: "keep this" on everything (2026-09-06)

| Commit | What |
|---|---|
| `c53d0a0` | **"keep this" on everything** — a thread, a curiosity, a search hit and a convention, over two id spaces kept apart |
| `85e000a` | **design rule 29 minted** — a hidden control is not a dimmed one |

A thread, a curiosity, a search hit and a naming convention can each be kept now; before this
every one of `pinBtn`'s five call sites was an inspector pane, so the four things a reader
actually wanders into could be *followed* and not *kept*. **Tom chose the shape first: two
routes, not one reconciled table.**

**What a cohort is** — the question that decided the shape, answered from `threads.py` rather
than by reasoning: *a set of routines that share a value, named by that value, resolved on
demand and never shipped.* Its `key` is always a value string — a plan id, a table name, a
glob, a glossary word — never an id this map minted. That is exactly why the two spaces stay
apart: a `fold` id belongs to the drawing and is valid only at the altitude it was drawn at, a
cohort key is something the *program* says and survives re-analysis. And `kind` already means
different things in the two, so one table would be one word carrying two meanings — rule 47's
companion, paid for once by `data-nav`.

**A thread whose subject is already a node is kept as a node**, translated into the map space,
so keeping a routine from a curiosity and from its own pane is one pin rather than two rows
naming one thing. Verified on screen.

**A kept cohort never prints a remembered count.** `cohort_subject` gained a `noun` that counts
nothing; the number is asked for when the shelf paints. On screen: *counting…*, then *"a plan
or decision id · opens 112 routines"* — the same 112 the corpus measurement gives for `AC-4`.
The count is deliberately **not** reused by the open, because that would be the shelf opening a
cohort past `THREAD_SUBJECTS`.

**A line is the first kept subject that moves**, so it records the revision it was kept at and
says the line may have moved — only when the versions differ.

*Found while building it:* the conventions page had been minting a cohort subject in JavaScript
since it was written, invisible to the guard that refuses exactly that one module over. Harmless
until `noun` existed; the subject comes from `vocabulary.py` now.

*Two the tests could not have caught.* **`visibility: hidden` is not dimming, it is disabling** —
a real pointer click landed inside the keep button's own rectangle and hit the row, because a
hidden element is not hit-tested and is out of the tab order, so `:focus-within` can never
rescue it. And a label centred in the middle of its own row, which then exposed
`.pinrow .linkbtn { margin-left: auto }` matching the label as well as *Drop* (rule 71).

*Not seen:* the search hit row's **column alignment** — its structure and subject were read from
the DOM, the columns were not looked at, and the renderer wedged twice before the retry limit.
Said rather than claimed. *Looked at 2026-09-07, and they were wrong: the keep button was on a
third row in the line-number column. See the top of this file.*

**Before that, paused 2026-09-06 between features.** `output/` holds what it held at the start
plus `mensores/standards.db`, which is that session's own feature and belongs there.

**Six commits, and the thread running through five of them is one idea Tom stated once:**
*"We're a rabbit-chasing application — it should work. If a panel lists 7 things, clicking
on that panel should lead to a screen that lists all 7 things in detail, no matter what
they are."*

| Commit | What |
|---|---|
| `9000550` | **the looking debt is paid** — five surfaces seen, and the instrument had two coordinate systems differing by exactly the dpr |
| `22e82ff` | **standards 4 then 3** — import an outside standard, and measure the program against it |
| `deb97c8` | **the cover's bars become a Setting**, and the name gets the column |
| `392d1e1` | **two more cover Settings** — tags to their own line, and the evidence line wraps |
| `e54df9b` | **a figure that counts things opens those things** — the comparison's nine tiles |
| `3cfce1b` | **the worklist's jump buttons act** — a finding opens what it found |

**Two items came off the open list, and both were recorded as harder than they were.**
Standards step 3 was *"compare against the graph"*, which measurement showed would make the
tool confidently wrong. The worklist's jump buttons were *"blocked on precision, not
effort"*, when every detector already had the ids in hand and was throwing them away. In
both cases the record was written from reasoning and the correction came from measuring.

**What is open** after that session: *"keep this" on everything* — **closed 2026-09-06, see the
top of this file** — the three filed defects (a change row files two trail steps, `holds`
missing from `insp`'s defaults, `navIds` splitting on a space), `m.<module>` as a language
feature, and per-plate sphere scaling with stack orientation.

*The two-trail-steps defect is now measured rather than filed from one surface.* Opening a kept
cohort files the subject **and** one arbitrary member of it; the untouched `[data-thread]` path
does the same, so it belongs to the selection path and not to any one lane, exactly as recorded.

**Two mistakes worth carrying forward.**

*`git checkout <file>` is not an undo.* Proving a guard non-vacuous, a cleanup line read
`git checkout src/dunneflow/anomalies.py || cp /tmp/a.bak …` — a backup that never existed,
after a command that cannot fail. It reverted ~200 lines of uncommitted work. The lesson is
the fallback rather than the checkout: `||` after a command that always succeeds is a
comment, not a safety net, and the VCS is no undo for work it has never seen. **Take the
backup first and restore from that.**

*A stale readout that looked like a false claim was self-inflicted.* The topbar read *"no
sidecar here to ask"* while `/api/about` answered fine — from re-analysing the map underneath
a running server and then driving `state` by hand. On a clean boot it is correct. Verified
before reporting, and it dissolved.

**Design rule 29 was minted on Tom's call: *a hidden control is not a dimmed one.*** The counts
are now **81 engineering rules numbered to 82** — 21 still does not exist — and **29 design
rules**. `visibility: hidden` and `display: none` take an element out of hit-testing **and** the
tab order, so a rule revealing it on `:hover` or `:focus-within` can never be reached by the
route that would rescue it — every way in is closed by the one declaration meant to make the
control quiet, and nothing reports it. In `DESIGN-RULES.md` in full, indexed in `CLAUDE.md`.

**One candidate is still open** for Tom to mint or refuse: *an instrument's two coordinate
systems can differ, and the one you can see is not the one you touch.*

### Before the pause: a plate is a subject (2026-09-05)

Tom's, and pre-existing. `pkg` routed to `selectFromNav({ disks })`, which sets no subject —
so the crumb read *"nothing selected"*, the table showed all 4,786 rows, and the inspector
offered *"Pick … a package from the navigator"*, naming the gesture that had just failed.

**What it decided is what selecting a package is.** Not a nominated member — that is what
`detail.fold` exists to undo, and a plate holding 926 would make it twenty times over. So
`state.plate` is a fourth subject, `web/plate.py` answers, and the pane is routed on the kind
above the first line that reads a routine's shape. Five plate kinds; `answers` is **declared**
by the server, because a package with no callers and a plate outside the program both arrive
as `[]` and mean opposite things — for one draft the external plates got the package queries
and `ext:STDIO` reported *0 in, 0 out, 0 touches*, which on screen says nothing in Mensores
writes to standard output.

**Three things measurement changed and no source check could have seen.** A ways-in query of
my own (`WHERE parent_id IS NULL`) dropped all 32 MCP tools and two of the four executables
`CLAUDE.md` names as ground truth — `waysin.listing()` is the one answer (rule 51). Members
read off the drawn payload marked *0 of 4,786 rows* in Table mode, which never mounts the
graph. And `&minDisk=${minDiskNow()}` spelled an unset threshold `null`, got a 400, and sent
every click to *"Not in this map"*.

2.4–9.7 ms for a package plate, a flat ~15 ms beyond the boundary line, in `PERFORMANCE.md`.
**Never seen** — measured entirely through the DOM.

### Before that: `<module>` is answered as what it is (2026-09-05)

Two false statements, not one. The three-way *"way in, dead code, or a call DunneFlow cannot
see"* hint fires on all 487 module nodes, every one of which has **0 callers and 0
entrypoints** — nothing can call module scope, because module scope is what runs *instead* of
being called, and the true sentence was already on the page underneath it. And `def
<module>():` — a copyable declaration of a routine nobody wrote, which `hoverSigHtml` already
refuses one surface over and which was not in the filed entry.

Not a separate pane: Out, Touches and Governance are all correct for module scope.

### Before that: a read never brings a database into being (2026-09-05)

Caused and then found. A one-line probe opened `output/mensores/graph.db` read-only — a path
that does not exist there — and `sqlite3.connect` **created** it. The failed query was not the
harm; the 0-byte file was, because `revisions.py` reads a bare `graph.db` as that program's one
legacy revision. Rule 20 from the side nobody expects: the read repaired nothing, it wrote.

Rule 51 with the count as the argument — **seven** read paths each carried their own
`if not path.exists()`, every one correct, and the caller that forgot was none of them.

### Before that: Document mode is about the selection (2026-09-05)

**Tom's screenshot was the bug report**, and it was two defects. `state.docPath` held whatever
was last opened and nothing connected it to the selection, while the mode toggle claims *"five
ways of reading one selection"*. And `.docnav` is `position: sticky` inside a `flex-wrap` box:
right while it is a side column, and at a 24px root its bases (12 + 26 + 1.2 rem ≈ 941px)
exceed the centre pane, so it wraps to a full-width row and pins itself over the prose.

**The obvious relation does not exist and is written down so nobody mines it again**:
`doc_refs`' 37,150 PATH entries are *document* paths, and a source file matches **zero**; its
CODE entries are CLI flags. What exists is the governance join — and **naming an id is not
being related**: a routine carries a median of 2 ids named by a median of **281** documents,
14% of the corpus. The **intersection** is selective, median **4**. So the pane ranks rather
than filters, states both numbers, and answers in 6.8 ms per selection rather than the 4.7 s
`traceability.measure()` takes for the whole program.

On Tom's call an open document **stays open** and says which it is — related, it names the
shared ids; unrelated, it says so and how you got there. 59% of routines carry no id at all
and get a sentence, not an empty list.

The contents fix is a **container query**: `@media` answers about the viewport and its `rem` is
not the page's (rule 28), `@container` answers about the pane and its `rem` is. Measured
sticky at 43.8rem, static and stacked at 35.0rem.

*And one I caused:* the doc chrome repaints only when `docDomKey()` changes, so the related
block froze on "Looking for…" seven milliseconds before the answer landed. The key carries it
now.

### Before that: ways in are nodes on the Diagram (2026-09-05)

Tom's option (iii), taken up an hour after being deferred. A way in is a **box on every
compartment it enters**, with bold arrows into what it starts, and the ordinary arrows carry on
inward from there — `pkg:signator` reads as `mensores-signator` → `__main__.py`,
`WitnessHandler.do_POST` → `WitnessHandler`, `serve` → `_server.py`, and down through
`_keygen`, `_custody`, `_signing`.

**Drawn by default, unlike a port, and the difference is measured.** Rule 19 turned ports off
because they are median 13 and max 41 per compartment against a median of 10 boxes. Ways in
are **max 3 and absent from 46 of 53**. Same rule, opposite answer, because it is a different
population; both numbers are in the docstring. Told apart by a **note silhouette**, never
colour (design rule 4).

**The arrow bound is one compartment's number.** `mensores` enters **39 of `pkg:cli`'s boxes**;
unbounded that compartment goes from 734×650pt at 1.1:1 to **3647×428pt at 8.5:1**, and
bounded at eight it is 1017×674 at 1.5:1. **No other compartment reaches the bound** — the next
largest fan-out in 53 is three. Bounded *per way in*, or one fan-out would push another's single
arrow out of the picture; the panel says *"entered from 1 way in, reaching 43 boxes — 8 arrows
drawn"* and opening the box lists all 106 (rule 8, design rule 1).

`entries` and `entered` are their **own list and lane**, so every count the panel already
printed is unchanged and a compartment with no way in emits a byte-identical drawing (rule 32).
Clicking a way-in box opens the way-in pane, so (ii) and (iii) are one path. An **entry arrow
refuses to open as a flow** and says why: the caller is the operating system, so there is no
call site to list.

### Before that: ways in say what they are, and an application opens as one (2026-09-05)

**Tom's question was the bug report.** *"They don't make sense in the way that code does… what
is `mensores`, `mensores-mcp`, `run`?"* A way in is **how the outside world starts this
program**; Mensores' fourteen are four *declared* executables from `pyproject.toml`, one HTTP
route, and nine *guesses* from a conventional name or a `__main__` guard — and the cover drew
all fourteen as a name, a kind tag and a bar. `ways_in()` computed the evidence and `cover.py`
threw it away before the wire. Five rows are called `main`.

**The row now says which**, with the evidence verbatim and unparsed (rule 30) and where it
lives — or, for a command tree, what it *spans*, because `mensores.cli:app` is a Typer object
with no definition site and inventing one would mean picking one of 44 files (rule 1). Neither
badge is coloured: green already means *here is a route* on that page (design rule 4).

**And clicking an application opens the application.** `web/waysin.py` + `/api/wayin` answer
with the tree — where execution begins, the 22 sub-applications with what each holds, and the
commands hung directly on it, every row carrying the node id that makes it an ordinary
selection. A sub-application opens too, with **every count recomputed for it** (rule 24), and
its id verified to be mounted under this way in rather than trusted (rule 49). Driven end to
end with a real pointer: cover → pane → `quaestor` → `accept_cmd` → `mensores/cli/audit.py`.

*Three found while building it, all in the record:* the application listed **itself** as one of
its own commands (rule 74); keeping it out then made the program's own front door read as a
limitation of the tool (rule 32); and a group counted by direct children read `telemetry 0` for
a group holding commands one mount down (rule 13).

***And one that was mine.*** `selectionSnapshot` and `sameSelection` were two hand-kept lists of
the same fields, and `wayIn` went into one — so a step carrying its subject perfectly was
deduplicated away, which is rule 33's symptom with nothing missing. `SUBJECT_KEYS` is the one
list now, and the guard asserting the two agree **immediately caught a second field**.

*Two things not proven, and said rather than claimed:* the **pointer path** for the
sub-application button — three real clicks reported success and delivered no event, the harness
having stopped mid-session (rule 48; the cover row and command row were pointer-proven before
it stopped) — and a **one-off boot failure** from a stale `localStorage` blob that cleared on
reset and did not reproduce. Both are in `HANDOFF.md`.

*A mistake worth knowing:* `git checkout <file>` to undo a one-line probe reverted the whole
day's work in that file. Recovered from a scratchpad copy plus nine re-applied edits. Revert
the probe, not the file.

### Before that: a root elected by no vote, and a package row that selects nothing (2026-09-05)

**Tom opened the throwaway `nodocs` map and found it broken. He was right, and it was two
things.** Mine: the map was `analyze src/dunneflow`, and the prescribed shape is the *parent*
(`analyze .../src`, whose child is the package). The tool's: it then failed twice.

**1. `root_package` could not fail.** It elected the modal first dotted segment. Analyse a
directory that already *is* a package and no segment is the root, so the biggest subpackage
wins — `web`, 20 of 63 files — and `package_expr` sent everything else down its `ELSE` branch
as `<external>`. **750 of 752 routines drawn as somebody else's code**, on the largest plate
in the picture. The tell is not marginal: a real root covers **628/628** and **63/63**, a wrong
one **20/63** and **19/61**, so no threshold is invented — a root accounts for every file or
there is none, and `""` is a real answer meaning *the tree itself is the root*.

*And the right test was already in the file.* `COVER_ROOT` asks the same question by grouping,
counted **16 heads** and answered *no root* — same process, same store — while `root_package`
elected `web`. `<external>` is `<outside the root>` now: it fired **0 of 4,786** times on
Mensores and only ever when the root was wrong (rules 26 and 30).

**2. `COVER_PACKAGES` was a second decomposition.** Second dotted segment, no root; its own
comment claimed it matched the disks and `PACKAGE_SIZES` called the difference a hazard a
hundred lines below — both standing for two months. The navigator selects **by plate id**, so
a row with no plate selects nothing and the pane says *"Nothing to show."* **1 dead row of 46
on Mensores**, 36 of 48 on the broken map. One expression, three callers (rule 51).

Both are serve-time, so every map is fixed with no re-analysis; `output/dunneflow` had the same
wrong root. 1,007 tests, and the three that matter fail without the fix — verified by stashing
the *source* and keeping the tests, since stashing both proves nothing.

### Before that: the stated naming lane, on screen at last (2026-09-05)

**`doc_rules` has held naming rules somebody wrote since the document scanner existed, and the
dashboard had never shown one of them.** `11-naming.md` quoted them from the day the column was
added; `/api/naming` served the derived lane and nothing else. This is standards **step 2**, and
it is exposure rather than comparison.

Measured before it was built, which is what shaped it: `output/mensores` states **12** rules
(7 FORM, 5 VOCABULARY) out of 2,064 documents; `output/dunneflow` states **0** out of 9. Both
cases were already on disk, so the good one and the blank one were each looked at.

**Two pages, and Tom chose which.** The obvious move was one page retitled *"Naming standard, as
found"* to match the Markdown report. Tom took the other option — keep *Derived naming standard*
and add a second row — because *derived* is load-bearing, and a rule somebody wrote on that page
would have made the word false of half its contents while leaving it standing. Stated sits above
derived: what was written comes before what was done. Each page names the other and says in the
same sentence that **nothing compares them**.

**One reading, three readers.** `resolve/stated.py`, beside `resolve/naming.py`'s Form lane,
takes the query, `StatedRule` and the `checkable` sentence out of `render/naming.py`. The
report's output is byte-identical across the move. **`scope` and `pattern` are drawn for the
first time** — in the schema since the scanner was written and read by nothing — which is what
makes *"Step names: snake_case"* legible as the one rule here that names a spelling and no
identifier class, kept rather than dropped (design rule 1).

**Three absences, three answers**, all driven on real maps: `--no-docs`, nine documents that
state nothing, and a scan that found none. `read` travels beside the counts because no count can
stand in for it. *(`output/beads` was a fourth candidate and refused to open — unmigrated
absolute paths, rule 60's refusal naming `dunneflow migrate`, not repaired on the way past.)*

**The hop is a capability test, not a hope.** `/api/stated` carries a `corpus` block for the
reason `/api/glossary` carries `sidecars`, and where it says no the reason is printed rather than
the button dropped. Driven with a real pointer: `NAMING.md:17` opened the document scrolled to
the *Latin-only* block with `docflash` on it, rendered as prose.

**And the thing only looking caught.** The first drawing gave **CHECKABLE the accent green** the
glossary spends on a DECLARED tier — on screen it read as pass/fail, which is not the claim: a
Latin-only rule is not a worse rule, it is one no query can decide. Green already means *here is
a route* on that page. Both badges are neutral now (design rule 4).

*Worth keeping:* the **old-style** `output/dunneflow/docs.db` yields **136** stated rules and all
136 come out of DunneFlow's own generated `11-naming.md` files — rule 57's hazard, closed by
`b92dec0`, preserved in a stale artefact. The current revision yields 0. It is why the page
renders an unbounded list grouped by document rather than assuming twelve.

*The harness trap, re-measured because it is not stable between tabs:* this tab took **clicks at
viewport × 0.395** and **captured at viewport × 0.79**, cropped to the top-left quadrant.
Calibrate with labelled markers at known viewport coordinates *and* a click listener reading back
`clientX/clientY` — that is the only method that settles both scales at once. Viewport 1,920×991
at a **16px root**, so rule 38's debt is reduced again and **not paid**. Two smaller ones: a
collapsed pane's own fold button has zero size, so the way back is the **rail** and a scripted
click on the fold is a silent no-op; and `state.view` is not persisted for any page, so a reload
landing on the cover is design rule 17 rather than a regression.

### Before that: a stopped analysis, and the map it leaves behind (2026-09-04)

Tom asked what happens when a background analysis hangs, crashes, or gets in the way of the
next one — *"the user disagrees, or asks to override."* Four things were checked against the
running code. Three were defects. **The fourth was worse than the question.**

**A killed `analyze` left a map that opens and lies.** Measured by stopping one twelve
seconds into the Society tree: 628 files, 4,786 routines, 4,070 boundary touches — and
`resolved_calls = 0`, a program that calls nothing — carrying a timestamp, a tool version and
chunk 2's determinism guarantee, listed by `program_dirs` and opened by the switch without a
word. **Reachable with no stop button anywhere**: Ctrl-C, a sleeping laptop, an OOM kill. So
the marker was the prerequisite, not an extra: cancelling without it would have turned a rare
accident into a button.

`analyze` now commits `complete = ""` on the way in, the **step** as it goes, and `"yes"` on
the way out. Three states and not two — missing means *predates the key* and is fine, which
matters because every map made before today lacks it. Verified against a real `kill -9`:
`complete = ''`, `step = 'reading the documents'`. **Re-analysing recovers it in 34 s**,
because the extraction is content-hashed, so *Analyse it again* is a fix rather than advice.

**Three defects that existed and are fixed:**

1. **Nothing could stop a run.** The `Popen` was a local inside `analysis.run` — no route, no
   button, and a hung child held the slot until somebody killed the server.
2. **The slot trusted a label.** `state == "working"` is true for ever if the watcher dies
   without noting. It asks `poll()` now, and clears the stale lock (rule 30). That is the
   *"or locked"* half of the question.
3. **A reload orphaned the run.** Nothing asked `/api/analysis` at boot, so the panel vanished
   while the run continued and the next attempt was refused by a sentence naming a job with
   nothing on screen to point at. The refusal was also a dead end — it now carries the running
   job and a **Stop it**.

**And the jam came back through the fix for it, which is the finding worth keeping.**
`analyze` runs a `ProcessPoolExecutor` and its workers inherit the pipes. `terminate()` on the
parent killed the parent and left **eleven workers** alive holding stdout open, so `run`'s
read loop never returned and the report said `working` over a child that had gone —
`state: working` beside `running: false`, the exact label-outlives-fact shape this chunk
exists to remove. The child gets its own session now and the signal goes to the **group**.
Found by looking at `ps`, not by a test.

**The silence is stated and acted on by nothing.** `moved` bumps only when something actually
changed — a timestamp refreshed by being polled would say a run was moving because it was
being watched — and the panel says *"Nothing new for 48 s. Some steps are quiet for a while…
so this may be working. It may also be stuck."* Resolution is legitimately silent for tens of
seconds, so the judgement is the reader's, not the server's.

***Minted as rule 80** on Tom's call:* **a job that can be interrupted must leave something
that cannot be mistaken for a finished one.** In `RULES.md` in full, indexed in `CLAUDE.md`,
cited six times across `store.py`, `cli.py` and the tests. *(The stated rule count was already
stale by one when 79 was minted; it now reads 79 rules **numbered to 80**, since 21 does not
exist and the numbers are addresses.)*

***`query` warns rather than refusing** — closed by Tom, not open:* *"I like the fact that
query returns but warns, that seems correct behavior for that feature."* It is the one reader
that opens an unfinished map, because its whole contract is that you get the rows that are
there; the other five refuse.

**Driven in a browser**, all four cases: the panel came back after a mid-run reload with its
elapsed time correctly reconstructed; the refusal named the running job and its Stop worked;
the selector reads *"coldrun2 — never finished being read"*; and the switch to it is refused
with the store's own sentence over an **Analyse it again** that opens the dialog name-filled —
after clearing the switch scrim, which would otherwise have sat at z-96 over a dialog at 92.

### Before that: "About this map" — what read it, and whether anything was guessed (2026-09-04)

**Tom asked for the model an analysis used. There is none, and checking that first turned the
feature from a placeholder into a guarantee.** Nothing on the analysis path calls a model or
touches a network: stdlib `ast` and `tokenize`, a hand-written document scanner, and
`Provenance`'s two paid tiers declared and unbuilt. On being told: *"Perfect, keep it that way
as much as possible! Inference should always be voluntary and secondary."*

So the two rows read *none — every fact here was read, not guessed* and *none — this analysis
is deterministic and local*, and a test asserts nothing under `extractors/`, `resolve/` or
`canonical/` imports an HTTP client or an LLM SDK — a claim on screen that no query can return
is prose (rule 13).

**Missing and blank are different answers**, and that distinction is the whole thing. Every
field arrives as `{recorded, value, none}`; `output/dunneflow`, analysed before these keys
existed, renders *"not recorded — written before this map could say"* in italic, visibly
apart from the guarantee. Both cases were looked at on real maps.

**`none` is the server's decision.** `inference` stores the word `none` so `dunneflow query`
over `meta` reads as prose; `model` stores blank, because there is no word for the model that
did not run. The page owned one spelling for an hour and rendered *"Inferred facts: none"* —
a bare word where the sentence was the point — which is rule 51 caught on screen.

**The row that was planned and struck.** *"Would a newer build read this differently?"* can
only ever answer no for the map on screen: `Store` opened read-only calls `_refuse_if_stale`,
so a mismatched graph never becomes the base. What is stated is the guarantee that produces.
The honest *read it again?* signal is the date and the **tree leaf** — a leaf, never a path
(rule 60).

**The topbar's `source directory` readout is the doorway**, and four guards flipped with it
rather than being deleted. It was a `<div>` with no pointer and no hover *because nothing
bound a tree*; its own markup set the condition — *"it becomes interactive when something
needs to open a file from disk"* — and this met it. So: it is a `<button>`, it carries the
affordances it used to have to refuse, and **the clip came back with the binding**, which is
what its own guard's failure message asked for in as many words. Each guard now protects the
new decision, in the same rule read the other way round.

*Candidate design rule, for Tom to mint or refuse:* **inference is voluntary and secondary, and
a map states whether any was used.** One step over from design rule 14, which scopes *egress*;
this scopes whether a fact was *guessed*.

*A second harness trap, and it cost another false start:* **click coordinates and screenshot
coordinates are not the same scale, and neither is stable between tabs.** One tab took clicks
at viewport×0.62 and captured at viewport×0.62; the next took clicks at viewport×0.62 and
captured at viewport×1.25 — a *crop* of a magnified render, not a downscale. Calibrate with
markers at known viewport coordinates before trusting either. Clicks below about viewport
y=48 never reached the page at all, so **the topbar cannot be clicked in this harness**; the
button was proven from the real keyboard instead, which is the better proof for a control
that has to be reachable without a pointer.

### Before that: "+ Analyze a directory…" works (2026-09-04)

**The dashboard can now make a program, not only choose one.** The `<select>`'s last option
opens a dialog, the server reads a source tree in a subprocess, a panel reports each step,
and the new program appears in the list with an *Open it* that is the program switch already
built. It is the second half of the selector entry, and it closes it.

**Four decisions, and the first is the one everything else follows from.** It runs
`dunneflow analyze` as a **subprocess**: every store this process holds is `writable=False`
by rule 20, and an in-process analysis would make the serving process a writer to the tree
it serves. It also keeps `walk.py`'s `ProcessPoolExecutor` out of a request thread, and makes
what runs *exactly* the tested command (rule 51).

**It is not the switch overlay, and that is the shape of the whole feature.** A base switch
blocks the page because every count underneath belongs to the version being replaced. This
reads some *other* tree into some *other* directory, so nothing on screen becomes untrue and
nothing is taken away — a dismissible panel, and a **second slot** on `_Live` beside the
build one, or a ninety-second read of an unrelated program would lock the reader out of
changing versions for no reason anybody could state.

**`--progress-json` is a contract, not a scrape.** stdout is one JSON object per line;
stderr, emptied by `--quiet`, is where a failure says why. The step list is **computed for
the run** — `--no-docs` makes it five and not seven — because a bar drawn against a total
this run can never reach is a run that looks like it died at step five (rule 32). Verified on
the real corpus: 63 lines, one total, 628 files and 2,064 documents, empty stderr.

**Eight refusals, each with its own sentence**, from one `analysis.check` that both the
dialog's live warning and the endpoint's answer go through (rule 41). The sharpest is the
**served program**, and it is not caution: `Store._discard_if_stale` drops every table of a
graph written by another build, and this server is holding that graph open. Analysing into a
name that already exists is *allowed* and says it rewrites that program's working snapshot —
Tom's call.

**Two defects found by looking rather than by testing**, which is the whole argument for
rule 38:

1. **A disabled `.linkbtn` did not look disabled.** The class sets an explicit background and
   colour, which overrides everything the browser does to say a control cannot act — design
   rule 16's defect arriving through a stylesheet. The rule existed under `.trailbar` and has
   moved beside `.linkbtn` itself, where both callers pass (rule 51).
2. **A failed analysis handed the reader a fourteen-line traceback with the useful line
   last.** The reason now **leads with the child's last line** and keeps the rest as evidence.
   And the case that produced it — a file sitting where the program directory would go — is
   a pre-flight sentence now, not a `FileExistsError`.

**Looked at in a browser, with a real pointer.** `elementFromPoint` confirms every control is
reachable rather than merely wired (rule 48); 75 characters typed into the path field
survived 75 repaints with the caret held; and `/` does not leak to the topbar search, which
matters because every path on this machine starts with one. The full loop was driven from a
real click: analysed, appeared in the selector, opened, served. **Still the automation tab
though** — 1,259×523 at a 16px root, and screenshots crop at 784×326, so the surfaces were
seen by parking the dialog inside the frame. Rule 38's debt is *reduced*, not paid.

*A coordinate trap worth knowing:* the `computer` tool's coordinates are **screenshot space**,
not viewport space. A click asked for at (626, 186) landed at (1005, 298) — the 1.606× ratio
of 1,259 to 784. That is the "clicks did not land where `getBoundingClientRect` said" note
from chunk 5, explained: multiply viewport coordinates by `784 / innerWidth`. It cost one
false bug report before it was checked.

*Candidate engineering rule, for Tom to mint or refuse:* **a long job is not a switch — a slot
names what is being replaced, not what is running.** Not minted.

**Chunk 2 is planned and not built:** *"About this map"* — what read this directory, shown so
a reader can decide to read it again. See "What is next" below.

---

**Before all three — the earlier pause of 2026-09-04, five features back.** 951 tests, mypy clean,
ruff clean, console clean, working tree clean, `check` reports 0 broken. Five things landed
that day, each whole and committed on its own:

| Commit | What |
|---|---|
| `94858d5` | Document mode **chunk 5** — a glossary citation into the corpus opens; **rule 79** minted |
| `3ce4c4a` | the naming standard says it was **derived**, not required |
| `427bace` | a naming standard written as a **table** is read — corpus FORM rules 0 → 7 |
| `b92dec0` | the mode toggle **dims** instead of vanishing; a program's own output leaves its corpus |
| `36a6439` | the **program selector** works |

**Next, and Tom has asked for it in this order:** *"+ Analyze a directory…"* — running an
analysis from the server, with progress, failure, and a new program appearing in the
selector. It is deliberately **not** in the `<select>` yet, because a third option that does
nothing is the defect the selector just fixed. No plan written; the approved plan file
`~/.claude/plans/async-hugging-whistle.md` holds the selector's, now built.

*Document mode is finished — chunk 5's approved plan was at
`~/.claude/plans/polymorphic-finding-swan.md`, superseded on the day by two decisions: the
viewer keeps its raw span **and** gains a hop into the prose reader, and rule 79 was minted.*

**Two servers were running at the pause and are stopped now**: `serve output/mensores` and
`serve output/dunneflow`. Both directories are current — the pair was rebuilt after the table
detector bumped the documentation fingerprint, and `output/dunneflow` was re-analysed after
the corpus fix. `output/beads` is stale by design and is what the selector's failure path was
tested against; `output/mensores@2026-08-29T19-43-39Z` and two `2026-08-31…` revisions inside
`output/mensores` are orphans, named in the record and left for Tom to delete or keep.

**Three things are waiting on Tom, one of them now closed, and none blocks anything:**

1. ~~**A candidate engineering rule, not minted.**~~ *Minted 2026-09-04 as **rule 79** —
   a lifetime change is an access-pattern change — on Tom's call. In `RULES.md` in full,
   indexed in `CLAUDE.md`.*
2. **A real window is owed a look.** Every figure in three sessions was taken at a 537–1,285px
   centre pane and a **16px root font**, in a browser context that reports 1,267×539, refuses
   `resize_window`, and crops its screenshots. His Chrome is **24px on a 4K screen**, where
   rows are taller and the pane proportionally narrower. Rule 38, still open, and the
   sticky-overlap defect in lane 2 was caught only because it happened to fall in the visible
   crop. The column weights in lane 2 (`DOC_COL_WEIGHT`) and lane 1's list row are the two
   places most likely to want adjusting.
3. **The extractor records 3–4 headings that are inside fenced code blocks** — examples of
   headings, not headings. 3 or 4 of 29,980, found by the renderer disagreeing with the map.
   Rule 12 is holding; this is the residue. Not fixed: correcting it changes `docs.db`'s
   contract, busts every cached graph, and rewrites 29,980 rows for four of them. Named here
   rather than filed, because it may never be worth doing.

**Next: whatever Tom picks.** Document mode is done and the open list below owns the rest.
The two nearest things are both his eye rather than my keyboard: the three surfaces never seen
in a real window (rule 38's debt, and chunk 5 added a fourth — the viewer's foot is 56rem wide
and never appeared in a capture), and the `<module>` inspector routing that he found on the
way past the Code-pane defect.

**Both lanes work.** Lane 2 is the map's own eight documents, every row an ordinary
selection. Lane 1 is the program's own 2,064 — a list grouped by class, a filter, a reader
with the document's headings beside it, and all three link kinds routed.

*Earlier the same day:* chunk B of the shortening work, rule 78, and three rounds of looking at
the code view — the greenbar, the margin fold, three broken buttons, and the rail/centre split.

*The paragraphs below are that day's earlier work, kept because the reasoning is recent and
load-bearing; the current task is the one named above.*

### Before that: the program selector works (2026-09-04)

The topbar's first control has never worked — three options and no change handler in the
ratified artifact, one served option in every shipped build, and no endpoint to fill it. It
switches programs now: `/api/programs` lists every directory under the output root holding a
map, `POST /api/program` rebuilds against one.

**It is the revision switch one axis over, and the reload is what made it small.** A program
switch cannot keep the selection, the trail or the revision; the reload discards them and
`loadSettings(program)` restores the arrived-at program's own settings, which have been keyed
per program all along. `serve` needed no CLI change — the siblings come from
`revisions.program_dirs()`, written that morning for the docs-corpus fix.

**Two things are not a mirror image.** The sidecars are repointed, because `source.db` and
`docsource.db` belong to the program. And **every** cache is cleared, because `findings` is
keyed on a graph's *basename* and `filepairs` on a pair of revision strings — two program
directories collide on both, without needing a coincidence. `PROGRAM_CACHES` is written out
rather than derived from `COMPARISON_CACHES` (rule 36 in both directions).

Verified on the real output root: `mensores` → `dunneflow` moves cover, navigator, graph and
glossary; the sidecars follow; settings stay apart. **And a switch to the genuinely stale
`beads` failed with the store's own sentence and left `dunneflow` still being served** — the
mode that would otherwise take the dashboard down. **9 mutations, all CAUGHT**, after two
survivors that were both my own guards failing to reach the code.

### Before that: a naming standard written as a table is read at last (2026-09-04)

**The FORM lane was empty across 2,064 documents**, and the reason was one shape: `_table()`
consumes a table whole and the loop `continue`s, so the prose rule detector is never offered
its lines. A naming standard is usually a table. `harness/rules/style.md:30` states seven
conventions as `Type | Convention | Example` — every row a class of identifier and the
spelling it must have — and DunneFlow could not read one of them. **`checkable` had therefore
never once been true**, and the whole point of that field is to be a comparison's input.

`table_rule_columns()` decides which column names the thing and which gives its spelling, on
the model of `term_columns`/`meaning_columns` beside it and keeping the rule that matters:
**both halves, on different columns.** A column qualifies on its **header or its cells** —
headers vary between organisations, and cells alone miss a column headed `Convention` whose
contents are too terse to score.

**Measured over the whole corpus before a line was written: 5,230 tables, one fires.** It
mints 7 rules, 6 of them checkable. The 100-row *Key Decisions* table does not fire; nor does
the pantheon, which is a glossary in a naming standard under a naming heading and is the most
dangerous near-miss there is. Corpus-wide FORM rules: **0 → 7**. VOCABULARY unchanged at 5.

**Two things the plan got wrong and measuring caught.** The two table-cell regexes added for
`CAPS_UNDERSCORES` and `colon separator` earn **nothing** on this corpus — the column is
headed `Convention`, which the header list matches, so it yields all seven rules with them
removed. What they earn is the *cell* path, which is what has to carry a standard written by
somebody who does not work here; the comment now says that instead of overclaiming. And the
seven new rules would have had **seven dead links**: the handbook links each stated rule to
`[the rule in full](#slug)` and only the Vocabulary section ever emitted a heading to slug,
so a FORM rule pointed at nothing. That is the `where_` defect's shape and it is why **Form**
now has a *Stated* half above its *Measured* half.

**And a sentence that had never been printed said something false the first time it was.**
`checkable` had no true branch in practice, so *"Mechanically checkable."* went out beside
"Type attributes: colon separator" — for which this tool has no population and no check. It
now says what is true: a check *could* be written, and DunneFlow does not run one.

**10 mutations, all CAUGHT** — after a first pass where 5 survived, every one of them a
fixture missing *both* column halves rather than one, so a mutation dropping either still
passed. Rule 37, in the guards written for it.

### Before that: Document mode, chunk 5 — a citation into the corpus opens (2026-09-04)

Design rule 13's last unmet half. **`senseOpens()` is a capability test rather than a
provenance test** — `s.provenance === "DECLARED_CODE"` was true of the tool until chunk 1 gave
the document corpus a sidecar, and stopped being true the moment it landed. `/api/glossary`
now carries a `sidecars` block, `{opens, reason}` per tier, computed from the live stores and
the base's two revisions, because whether a corpus can be read is a fact about the *directory
and the base* that the page has no other way to learn.

**Both halves of the reading are offered.** The viewer shows the span out of `docsource.db` —
the bytes **as measured**, Markdown syntax and all, which is what proves the citation — and
its foot offers *Read it in the document →*, which closes the viewer, opens lane 1 and scrolls
to the block holding the line. Verified live: `mensores` → `.groma/PROJECT.md:474` → the
paragraph spanning 474–475 flashed, **55,810px into 459 blocks**. That is chunk 4's
`data-line-end` innermost-containing lookup doing the thing it was named for.

**The refusal is per corpus and was verified on a real asymmetric base.** `output/mensores`
holds source bodies for both revisions and document bodies only for the newer, so serving the
2026-08-26 base gives code citations that open and documentation citations that do not, with
the version reason stated — and `/api/docsource` refuses rather than serving newer prose under
older headings (rule 70). On that base the 32 documentation rows render as plain text with no
button at all: no control that resolves to nothing.

**Reading the sentence out loud is what caught the defect.** The server's four reasons are not
one part of speech, and embedding a clause in `because there is …` produced *"because there is
this sidecar holds nothing for the version on screen"*. Every test passed. A dash takes both,
the wording stays the server's, and the guard that the shell carries none of the three
sentences tripped on the comment explaining the fix — the sixth time a guard in that file has
failed on its own prose.

**17 mutations, all CAUGHT.** 928 tests. Every measured figure is in `PERFORMANCE.md`; the one
worth carrying is that a documentation citation costs **999 ms** and a code citation costs
**999 ms**, which is the glossary's own repaint and not either route.

### Before that: Document mode, chunk 4 lane 1 — the program's documents, read (2026-09-03)

The last piece. 2,064 documents mined for 29,980 headings and readable nowhere now have a
list, a filter, a reader and a side nav.

**Two lanes sharing a pane — two subjects, not two views of one thing.** One mount, one
subtree cache, one `render()` branch, so the cache key carries the lane: a subtree keyed on
the other lane's page is handed back on a switch, which looks exactly like a switch that did
not work. **The filter hides rows rather than rebuilding** — 2,064 rows per keystroke is the
cost, and rebuilding also destroys the `<input>` being typed into. The reader wraps to one
column by **flex-wrap rather than a breakpoint**, because this depends on the *centre pane* and
`@media` can only ask about the *window*.

**The screenshot found what nothing else could.** `html: false` does not hide an HTML comment
— **it un-hides one**: markdown-it disables the `html_block` rule entirely, so a comment
arrives as an ordinary paragraph and renders as body prose. **7,317 of them across 505 of
2,019 documents.** The first fix, written against `html_block` tokens, counted zero — there
are none. They are lifted out before parsing, replaced by their own newlines, and listed with
their lines rather than dropped.

**And a heading that was not one found what chunk 5 will need.** One of 1,566 stopped matching
after the comment strip: `## Discoveries` **inside a code fence**, recorded by the extractor as
a real heading (3–4 such in 29,980). What it exposed is that blocks carried only their *start*
line — and the lines anybody opens at are mostly not the first line of anything. **A definition
sits mid-paragraph, which is exactly what chunk 5 opens against.** Every block now carries
`data-line-end` and the lookup takes the innermost containing block. Zero unreachable headings.

**Three of my own guards survived their mutations, all the same way**: each checked that a
*name appeared* rather than that anything happened. Rule 37, three times, in a chunk whose own
defects are rule 37's shape.

**23 mutations, all CAUGHT** on the second pass. The list is 56 ms to paint and 5 ms to
repaint; the filter over 2,064 rows is 2 ms; the 1.32 MB worst case is 668 ms to open.

### Before that: Document mode, chunk 3 — the renderer (2026-09-03)

`prose.js` and the vendored `markdown-it`. **Its own file, and the boundary is `graph.js`'s**:
it turns text into markup and knows nothing about this page, and what it has to say leaves as
data attributes the shell routes.

**The line CLAUDE.md draws is enforced now rather than stated.** `VERSIONS.json` has claimed
*"a test asserts it"* since the library was vendored and there was no such test — rule 43's
shape, the same as `shorten()`'s docstring promising a `selfCheck`. Nothing under
`extractors/` may mention the library: its output is a contract hashed into the cache key,
and a renderer is in no cache key at all.

**The property it was chosen for, verified rather than assumed**: every heading `docs.db`
recorded found in the rendered DOM at exactly its own line — **825 of 825** across 60
documents, 782 of 782 across another 41. That is the chain design rule 13 rests on.

**Every link and image decision came from the corpus**: 3,516 https · 6 http · 666 relative ·
16 anchors · 6 unfollowable schemes · 5 images. External links stay links in a new tab;
relative links and anchors **lose their href entirely**; `graph:` and friends render as text.
**An image is never fetched** — that is egress rather than navigation, no click and no
consent (design rule 14). Swept over 230 documents and 4.0 MB: zero errors, zero hrefs that
could navigate away, zero `<img>`, zero `<script>`.

**Frontmatter is half the corpus and the obvious fix was the trap.** 989 of 2,019 documents
open with YAML that markdown-it renders as a setext heading. *Cutting* those lines shifts
every `token.map` below by a constant — a page that renders perfectly with every line number
on it wrong. They are **blanked** instead: no arithmetic, none to get wrong.

**Two process findings.** A guard passed on the *comment* explaining it — dropping
`noreferrer` survived a mutation because the paragraph saying why it was there was still in
the searched text, which is `_code()`'s own recorded defect reproduced within an hour of
reading it. And a mutation harness killed by a timeout **leaves the tree mutated**, which
`git checkout` cannot undo for a new untracked file: commit before mutating.

**22 mutations, all CAUGHT.** The library is 29 ms lazily; 1.32 MB parses and renders in
40–72 ms.

### Before that: Document mode, chunk 4 lane 2 — the narrative view delivered (2026-09-03)

**The ratified design's own sentence, built at last**: *"the same selection, as a document,
scrolled to the routine you have selected."* `documents.py` has carried a graph node id on
every row since it was written precisely so this could exist, so a row is an **ordinary
selection** — the stack lights, the inspector fills, the navigator marks and reveals, the
trail records the hop, undo reaches it. Driven and read back off the page, not asserted.

**The `where_` bug is fixed and it was worse than it sounded.** All eight `DOC_*` statements
aliased their location column `AS where_` — `where` is a SQL keyword — while `documents.py`
keyed it `Column("where", …)`, so the **"Where" cell of every row of all eight documents**
rendered blank. Now `AS "where"`, and every statement in the family is prepared against the
real schema with each `Column` key asserted to be one it returns. 0 blank cells on Mensores.

**The first draft cost 9,568 ms per `render()`** — the code browser's own defect at six times
the size, written by someone who had just read the comment about it. And **two of three
fixes did nothing** (rule 39): 566 tables against one was 2,049 ms against 2,103; 4,786
`<button>` cells against spans was inside the noise. What worked was not repainting, plus
`content-visibility: auto` per group (**61 ms against 3,205**) and `table-layout: fixed`
(1,769 against 2,389). First paint is now **631 ms** on the largest document and repaints
are 19–94 ms.

**Two defects found by looking and by clicking.** The group name and the column headers were
both sticky at `top: 0` inside one container, so the name covered **every column label** the
moment a group reached the top of the pane — nothing threw, and only a screenshot showed it.
And the **trail note never landed in three routes**, one of them a year old: `codelink`,
`docrow` and `doctable` all push a note after `selectFromNav` has already recorded the step,
and the dedupe threw it away whole. A deduped step now adopts a note the standing one lacks.

**21 mutations, all CAUGHT.** The rule-38 debt stands and grew: every figure was taken at a
537px centre pane and a 16px root font in a window that refuses to resize and crops its
screenshots at 784px. **A real window is still owed a look.**

### Before that: Document mode, chunk 2 — the corpus served (2026-09-03)

Every figure the plan predicted came back exactly: **2,064 documents** (2,019 Markdown, 45
text), 29,980 headings, 235 definitions, 8 duplicates, all openable, and the class breakdown
to the row — PLAN 1601 · OTHER 286 · DECISION 92 · RESEARCH 33 · TOOLING 12 · README 9 ·
REFERENCE 8 · ROADMAP 6 · SPEC 6 · NAMING_STANDARD 5 · GLOSSARY 3 · ISSUE 2 · CONTRIBUTING 1.
The list is 546 KB of JSON at **18 ms warm**; the worst case, `.groma/ISSUES.md` at 1.33 MB
and 18,299 lines, is **6–7 ms warm**. Both whole, neither paged.

**The document store is held on `_Base` now, and the 148 MB per-switch leak its old close was
written against has moved rather than gone** — the swap closes it, `_Live.close()` closes it,
and so does the failure path of `open()`. Three closes where there was one, all three guarded,
one of them exercised by asking the outgoing connection a question after the switch.

**Two defects, and neither could have been found by a test.**

*A 000 and a stack trace on the first request.* `DocStore` had no `shared` parameter at all,
because it had only ever been opened, read and closed on one thread. Held on the base and read
from a request thread, sqlite refuses it **by name, from inside the request, and only on the
routes that touch it**. Every unit test passed, because a unit test calls the builder on the
thread that opened the store. Its guard starts a real `threading.Thread`.

*And rule 70, one corpus over from where it was first paid for.* `_sidecar_revision` returns
`None` for *this sidecar cannot serve the version on screen*; every store reads `revision=None`
as *the current one*. Two meanings, one spelling, and the newer won: Mensores' 08-26 base
listed all 2,041 of its documents as openable and served the **08-29** prose under them, every
heading's line landing wherever the text had since moved. The source sidecar never showed it
because it holds both snapshots — the older base is the first version anything here has ever
had no bodies for. `serving()` is the fix: `revision=None` is a refusal with a sentence, never
a fallback. `_span`, which `/api/source` shares, had the identical hole.

**Fifteen mutations, all CAUGHT.** Four absences, four sentences — never scanned, not
captured, not for this version, not this path — because they look identical on a blank pane
and the thing to do about each is different.

*The shortening work is complete.* The remaining twelve `text-overflow: ellipsis` sites were
measured before being changed, and measuring struck three of them, changed the mechanism from
a constant budget to one taken off the box at render time, and found that `shorten()`'s
docstring had been **promising a `selfCheck` assertion for a session without it existing**.
That assertion is real now, and it could not have been written against constants (rule 43).

**Four defects in the fitter, every one found on screen and three of them with a comment
beside them asserting the opposite** — a pane measured mid-transition, a box shrunk by the
pass's own previous write, the border box measured instead of the content box, and two floats
compared for exact equality. And two *layouts* that had been wearing a shortening rule's
clothes: the trail squeezing its steps rather than scrolling them, and a caller row that
cannot hold a name and a module on one line at all.

**Two of Tom's calls, both put to him with the alternatives measured against each other.**
A worklist title is **two lines then a mark**, with the whole of it on the hover — it had been
one clipped line, *94 of 94 rows*, showing the first thirty characters of every finding and
never the predicate. A caller row **stacks** its module under its name — side by side, every
split measured as a trade rather than a fix, and all 11 rows now show both entire where 7 of
11 used to overflow.

*Chunk 2 is done — it is the entry above.*

*Still queued behind the plan:* the flow panel's real worst case — `session.add_turn` at
`_extraction_state.py:742`, 3,323 bytes over 53 lines, on a *resolved* call, so its arrow can
be opened. One outlier and not a class: the next largest resolved call argument in the corpus
is 923 bytes.

**A server is running on 8787**, on the **08-29** base. Bring one
back with `uv run dunneflow serve output/mensores --port 8787 --no-open`, and add
`--revision 2026-08-31T22:53:15Z` to open the older one — which is the base with **no document
bodies**, and is worth keeping in mind: it is the only version anything here has ever had none
for, and it is what turned up the rule-70 defect. `output/mensores` also holds `docsource.db`
(17 MB on disk). `pkill -f "dunneflow serve"` ends it. Note that `--port` yields to any free
port if the asked-for one is taken, so a second server started over a stale one lands
somewhere else and says so on its last line.

**The debt is unchanged and it is rule 38's.** Everything in chunk B was measured at 1396px in
a browser context that reports `outerWidth: 0`, refuses to resize, and whose **screenshots did
not track the live DOM** — the region under a freshly measured element kept rendering the pane
beside it. Every number above is a measurement and every guard is a guard; what none of them is
is a look. Three things now wait on a real window: the constants surface, the blank-graph fix,
and this.

### Before that: Document mode, chunk 1 of 6 — a body sidecar for documents (2026-09-03)

**Paused mid-feature. The approved plan is at `~/.claude/plans/polymorphic-finding-swan.md`;
read it before resuming.**

**Document mode was never "browse documentation", and that is what makes the question
interesting.** The ratified `viewDoc()` is a hand-written sample of narrative prose *about the
current selection*. Half of it arrived as Code mode; the other half — the selection read as a
document, scrolled to the routine you picked — has been buildable since `documents.py` started
putting a graph node id on every row, and simply had no view. Meanwhile the **name** promises
something real and entirely unmet: nothing in DunneFlow could read a program's documentation.
2,064 documents mined for 29,980 headings and 235 definitions, and **zero** of them readable.

Tom's direction, and it shaped the plan: *"I don't want to abandon the old code, I want to
resolve it."* The narrative view's two claims each get a home and the eight generated
documents get the reader they never had — nothing is deleted for being unfinished.

**Chunk 1 is built and committed.** `sourcedb.py` was already a generic blob store; the only
thing hard-coded to code was the `kind` stamp, so `DocSourceStore` is that class with a
different one, in its own file because design rule 14 turns on documentation and source being
separately handable. **`capture()` needed no change at all** — `DocStore.known_hashes()`
returns exactly the map it wants — so there is no new capture path and no change to `walk.py`.
Measured: **2,056 bodies for 2,064 paths, 38.7 MB of prose in 14.8 MB**, against a predicted
14.87.

**Two defects found in the building.** `adopt_revision` exists because the first build had
none: `open_working` mints an id from the clock, which is right for the store that *is* the
authority, and a second sidecar is not — without it the capture wrote 2,064 path rows and left
`revisions` **empty**, so nothing could resolve them (*"2,056 bodies for 0 paths"*). And **rule
16 had a hole**: `set_meta` does not commit and `close()` does not either, so a sidecar created
and closed landed with an empty `meta` — no kind — and the wrong class then opened and
**restamped** it. Production never reached it because `analyze` always commits afterwards,
which is the hazard exactly: *the guard was intact everywhere it was exercised*. It took a
second kind to be mistaken for before anyone could see it.

**`markdown-it 14.3.1` is vendored and recorded**, with the line that matters written beside
it: `CLAUDE.md`'s *"no markdown library"* governs the **extractor**, whose output is a contract
hashed into the cache key. A renderer is in no cache key and no fact depends on it, and nothing
under `extractors/` may import it. Both properties it was chosen for are verified in the
browser — `token.map` on every block, and `html: false` rendering a `<script>` as text.

*Open and not yet handled:* relative links (`./rel.md`, `#anchor`) render as **live hrefs** and
would navigate the dashboard. Chunk 3 must route them.

**Next was chunk 2, and it is built** — see the entry at the top of this section.

### Before that: one file, two panes, and one button for both (2026-09-03)

**Reported as a question about whether the tool was telling the truth**, which is the form the
useful ones take: *"Once again, I'm told there is no file open... The list of files is on the
left side, and I had clicked on one of them, so it must have been open, right? What was
supposed to happen when I clicked on those buttons?"*

`‹ files` in the rail and `files ›` in the centre were **the same control** — both
`data-codeback`, both `openCodeFile("")` — and `state.codeFile` is **one value serving two
panes**, with `codeList()` deciding list-or-file purely by it. So a button reading *show me
the list* closed the file everywhere. The reader was right and the pane was wrong.

The centre's copy was the worse of the two: `viewCode()` has **no file list at all**, so its
whole effect was to remove what the reader was looking at and print *"Open the Code group in
the navigator and pick one"* — a control that empties a pane it cannot refill. It is gone.

**And it was mine to have surfaced, which is worth recording as a shape.** `openCodeFile` had
never called `render()` until earlier the same day; before that the rail's button looked
pane-scoped *by accident*, because the centre kept its already-painted chrome until something
else repainted it. The state was global the whole time. **A fix that makes an inconsistency
visible gets reported as the fix's fault, and is not.**

Two questions, two fields now: `codeRailList` is where the **rail** is, `codeFile` is what is
**open**. Tom's own argument for code in the rail is quoted a few lines above `codeList` —
*"I want to be able to see code and graph at the same time"* — and a rail that must empty the
centre to show its list is that undone, as it had been since Code became a fourth centre mode.

*Four mutations CAUGHT and one control case correctly **not** caught*: a `data-codeback` in
the rail must not trip the guard, because that is where the button belongs. A guard firing on
both would assert the opposite of the fix.

### Before that: three broken buttons on the Code panel (2026-09-03)

**Reported in one line each, all three real, and no two of them the same bug.**

**`margin 35` did nothing** — the fold built an hour earlier and tested at the keyboard before
it shipped. `wire()` runs at the end of *every* `render()` and calls `addEventListener` with a
fresh closure; for a control in `#viewMount` or `#inspector` that is harmless, because those
are rewritten each render. **The code chrome is the one surface that is not** — it repaints
only when `codeDomKey()` moves, so a 1.37 MB subtree is not re-attached on every keystroke.
The button survives and the listeners pile up. Measured: five renders after a paint, **one
click ran the handler six times**. An even number, so nothing happens; one, three or five all
work, which is why it passed its own test and my own look at it. `CODE_ROUTES` is the answer
and its comment already said so — **a route cannot accumulate** — and the guard is now about
the whole surface rather than the two buttons.

**`files ›` fired every time and the reader was watching the wrong pane.** `state.codeFile`
went to `""` and the navigator's list came back; `loadCodeFile("")` returns at its first line
and `openCodeFile` never called `render()`, so the centre kept the file, its title and its
footer. Rule 77's companion one route over: **a route correct for the caller it was written
for is wrong for the caller it has just acquired** — `openCodeFile` was the navigator's, and
`Code` became a centre mode after it.

**Back then Forward did not restore the file.** `selectionSnapshot()` records where the
*drawing* is and not where the *code* is, so a file open — which changes no selection — filed
a step that `sameSelection` deduplicated away. The comment beside `diagramId` says this about
itself in those words; the lesson was written one view over and never carried across.
`codeFile` is in all three places now — recorded, compared and restored — because a field in
one or two of them is worse than none.

**What they have in common is worth more than any of them.** Every one was a control whose
*state* was right and whose *pane* was not, and none was visible to a check: the listener was
attached, the route ran, the step was filed. The tell in all three was a reader clicking and
watching — rule 38's debt, paid by Tom for the third session running.

### Before that: the code view, looked at (2026-09-03)

**Four things in one screenshot, at Tom's own keyboard and his own window.** Three were real
and one was a question that answered itself.

**The greenbar was a row breaking twice.** `rows.join("\n")` is the reflex, and inside a
`<pre>` it is not whitespace between tags — it is content. `white-space: pre` renders it as a
line break and the row span is already `display: block`, so every row was followed by an empty
one: **1,703 rows in 58,932px, 34.6px a row against a 17.28px line-height.** Now 29,520px.
**Three surfaces had it** — the centre's table, the navigator's pane, the glossary's citation
viewer — and only one was reported; the others were found by looking at the remaining `<pre>`
builders. `srcPane` keeps its newline and that is the rule rather than an exception: its rows
are not wrapped in a block. **A row breaks once**, and the guard asserts both directions.

**The indent was not an indent** — it is the margin column, and a fixed 12rem reserve fails
from both ends at once: **92.4% of rows carry no mark** and pay it in full, while **37.7% of
the marks that exist are clipped** by it. (A comment records it was already narrowed once from
15rem, which treated the symptom; the mark widths run median 185px to **max 1,263**, so no one
width can serve both.) Three ways out were measured and put to Tom. **His call: fold it** —
248px down to **76px**, and at his 24px root that is 258px of code back. Folded, a marked line
still says so with a glyph carrying the whole mark on its title (rule 45, design rule 1), and
a file with **no** marks renders no mark elements at all.

**The line numbers were asked about and left alone.** `3.5rem`, right-aligned, four digits —
exactly the reason Tom guessed, on a 1,703-line file.

**The grey area is provenance**, and it folds now per his standing rule. *That fold was itself
a dead control in its first draft*, which is worth more than the fold: `render()` repaints the
code chrome only when `codeDomKey()` moves, so flipping the state and calling `render()` set
the field and changed nothing on screen — design rule 16 with every part working, in a control
added to satisfy a rule about controls.

*Two guards went blind rather than green on the way*, which is the only reason they were
survivable — one matching a class attribute that gained a second token, one `_fn_body` unable
to see an `async function`. And one self-inflicted `SyntaxError`: two `const bare` in one
scope, caught by `test_the_javascript_parses` on the next run.

### Before that: no pane assumes what it was showing is still true (2026-09-03)

**Found by Tom mid-rabbit, and it relocated the defect twice.** *"When I change the center
panel to Code, that panel shows `mensores/_internal/_governed_gates.py` which is not what I
expect to see."* It was not: `/api/node` gave `mensores/disceptator/_extraction_state.py` for
that node all along. What was on screen was `state.codeFile`, which is **persisted** — the
file a session two days earlier left open, from a package the reader had never touched, drawn
with a title and a path and nothing to say it was stale.

`followSelectionIntoCode()` is guarded on the pane being on screen, which is right, and was
invited from **exactly one place**. The condition has two halves — the selection changed, and
the pane became visible — and only the first was ever served.

**Tom's rule is larger than the defect, and this file already contained it in one branch.**
*"Every possible venue that can change the point of view should be considered, so no control
should ever expect that it 'knows' what it was showing before is still true."* The table's own
comment has said exactly that since it was written: *"there are five ways into table mode ...
a call at each is exactly the list rule 51 says grows. Every one of them arrives here."*

The audit found three panes on each side of that lesson. **Reconciling inside `render()`:**
table, glossary/naming, curiosities. **Relying on every call site to remember:** the code pane
(1 site, and the wrong one), the stack (4), the diagram (7). All three moved.

**The four stack calls were mis-ordered as well as incomplete** — every one sat *before* its
own `render()`, so each was mounting into the previous view's layout. That is the defect
recorded as *"the graph should have been there"*, fixed on the mode toggle in 2026-08 and left
standing at the other three. In `render()` they are ordered right by construction, for routes
nobody has written yet.

**The price of a render-time reconcile is that it must be silent when there is nothing to do**,
because `render()` runs on every keystroke. `ensureDiagram` claimed its lock before asking, and
finished by rewriting the mount that exists so `render()` will not touch it — taking the
laid-out SVG and the reader's pan with it. And the code walk had to stop fighting a deliberate
file open: `codeFollowedFor` records **which subject** the pane was walked for, never merely
that it was, so a reader may open anything they like inside one selection and is still followed
the moment they pick something new.

*One guard was blind first and found by mutation*: it asserted `codeFollowedFor` was **named**
in the walk and passed with the early return deleted. Rule 37, again.

### Before that: every field fits its own box (2026-09-03)

**A constant is arithmetic wearing a measurement's clothes.** `MODULE_BUDGET_NAV = 30` is
honest because `.navsub` is `max-width: 11rem` — all 1,175 rows are the same box at any window
and any root size. None of the seven fields left over is like that: they are flex children
whose width is what a badge, a count and a line number leave them, and it differs *per row
inside one window*. `.rank-name code` is 156px on one cover row and 112px on the next, because
the `kind-tag` beside it is a different width. Rule 53, with rule 24 underneath it.

So `fitFields` measures the box each string is in. Reads batched before writes; candidates
measured on a **canvas**, never in the DOM, because `shorten()` is monotonic in its budget
(0 non-monotonic steps over module names, qualnames, paths and command lines) and the widest
budget that fits is therefore a seven-call bisection with no layout in the middle. **4 ms over
120 fields, 4.5 ms over 1,175** — so it runs at the end of every `render()` rather than waiting
for a frame, because a frame painted before the pass is a frame of the untruncated string.

*Three fields came off the list by being measured.* `.wl-title` is **prose** — every one of
the 107 findings contains a space and 80 contain a dot, so the middle-elide would decide the
head was ``self``, the leaf was the whole predicate, and elide the subject out of a sentence.
`.srcpath-v` is a **dead field**: `#srcPathV` is written by nothing and holds a 28-character
literal that fits. `.callhead code` was a **contradiction** — `breakable()` marks its joints
with `<wbr>` and `white-space: nowrap` made every mark inert, while its two siblings render the
same strings through the same function and carry 98 and 88 characters with no overflow (rule 13).

*A label is not the text on screen.* Every label reader goes through `labelOf` — `data-label`,
then the unshortened `data-full`, then the text — or a trail step records `stor…items` as the
place you were, which is rule 33 and rule 30 in the one surface built to take a reader back.

*The band tables now say what kind of string each column holds*, with **no default behind
them**: `modules_explained` prints a path where every other band prints a module and a module
where every other band prints a leaf name, exactly inverted, so a kind guessed from the markup
would strip a program root off a path, find none, and look deliberate.

**Twelve guards, each run against the defect it names, all twelve CAUGHT.** One existing guard
earned its keep on the way: four explanations were first written as HTML comments *inside
template literals*, where a backtick closes the literal and the page comes up empty — the third
occurrence of the defect `test_no_backtick_hides_in_an_html_comment` was written for. They
belonged above their functions anyway; inside a `.map()` body each shipped once per row.

### Before that: two dead controls, reported at the keyboard (2026-09-02)

**"On its own" could not be chosen.** The option existed, was selected, and the handler was
correct — it even carried a comment saying *"On its own is a real answer"*. Two things put
the comparison back. `comparedRevInForce()` could not tell *nothing chosen yet* from
*chosen: on its own* (both `""`), so the fallback that marks a first visit's file list
invented the pair back — **rule 49**. And fixing that changed nothing on screen, because
`versionStrip()` derived the compared end **again** with its own copy of that fallback, and
its "on its own" branch tested whether the *program* had a second version rather than whether
a comparison was running — **rule 51**. `comparedRev` has three states now, with `ALONE` a
named state rather than an id.

**The shelf could drop a thing and never open it.** A pin was `{label, note}` — neither is an
identity, so dropping worked (it needs only the row's position) and opening was impossible,
in the one surface built so a detour does not cost you your thread. The subject is carried
now, and **the three kinds are not one shape**: a node, a box whose id belongs to the drawing,
and a flow that needs its compartment. Pins were also keyed by *label*, which collides every
`__init__` in the program.

*Seven guards, each run against the defect it names. Two were blind first — one tripped on
the comment quoting the code it checks (the sixth time in that file), and one reported MISSED
when the **mutation** was wrong rather than the guard: `replace(…, 1)` hit the first of eight
occurrences, in another function. Rule 59 from the other side.*

### Before that: the constants surface (2026-09-02)

**Measuring first moved the target twice.** The record named a 6,924-character line as the
problem; `GOVERNED_GATES` is **8,586** and nobody had noticed it. And it is a class, not an
outlier: **739 of 2,638 constants exceed one card line, 301 exceed 300 characters, 23 (0.9%)
exceed a whole card** — Tom's "rare cases", quantified. Every value is a single line, because
`_literal` is `ast.unparse`.

**And the real defect was not the line length.** A constant rendered in the *routine-shaped*
inspector, which answered three questions a constant cannot be asked — nothing calls it *"a
way in, dead code, or a call DunneFlow cannot see"*, it calls nothing, *"everything it does,
it does in memory"* — while the 8,586 characters it had read were absent. Three plausible
sentences inviting the reader to conclude the analysis had failed. `viewInspectorConstant` is
routed on kind now, beside `FOLD` and `FLOW`.

**The value is whole in the one box that scrolls**, which is what lets the card bound itself
at 240 characters and say so: rule 8 allows abbreviation only where the complete content sits
beside it, and that pane is where *beside it* lives. The card's `-webkit-line-clamp: 3` was a
silent filter inside the surface whose whole job is to answer *what is this*. It counts
**characters, not lines** — no value carries a newline, so "94 more lines" would report the
pane as the program (rule 32).

**Tom's three calls.** The card stays non-interactive and a click opens the value — put to
him because `.hovercard` is `pointer-events: none` by a recorded decision, and settled by
measurement: the longest qualname is 107 characters, so *names never need a scroll box*.
**Head and leaf, middle elided**, one rule for all kinds. And a moved constant shows **a mark
only**, with the name clickable and opening on both values.

**Every presence row was a bare `<code>`** — `Constants ◈7` named seven constants and not one
could be opened. They carry a route and a subject from the server now; ways in carry none and
stay text, because their route wants the routines they start and that table cannot reach them.
`EXPECTED_SCHEMA_VERSION` opens to **28 beside 27**, labelled by revision.

**`shorten()` replaces `moduleTail`**, and the program root is dropped first — all 566 modules
begin `mensores.`, so keeping the head spends nine characters saying what every row says and,
for a three-segment module, elides the *package* to afford them. `COVER_ROOT` answers the
question `COVER_PACKAGES` had a comment saying it could not. **742 of 1,019 navigator rows now
show whole**; the CSS backstop fired **0 times**.

*Four defects found in the doing, three of them mine — `state.insp` declared in two files with
only one winning, a root lookup that stripped nothing because `mensores` is itself a package,
moved rows built with no route, and a floor that guaranteed the overflow it prevented. All
four in `HANDOFF.md` under this session's heading.*

### Before that: the topbar search does what it says (2026-09-02)

**Reported as a question:** *"I can't find `frozenset` by searching for it. Nothing appears."*
Then the better one — *"What does search DO, exactly? Is it a filter, a focus, or a
highlighter?"*

**A filter, on one list.** It matched a substring of a routine's name or module and nothing
else, while the box said *"Search routines, tables, boundaries…"*. `audit_blobs` — a real
table — matched **4 routines** by substring while the Database group holding that table said
nothing, which is the worst kind of pass: it looks like it worked. `VIRTUAL_ENV`, a real
boundary, said *nothing matches*. And `frozenset` is in the source **408 times in 136 files**,
found by the *other* search, which nothing on screen mentioned.

**Now every named group filters**, through one predicate handed to each (rule 36), and each
filters **before** it slices — searching a bounded list would answer about the first eight of
forty-three. `structures` rides with `/api/routines` (671 rows against 4,786) and there is a
**Structures group**, which the search had nowhere to put before.

*Two defects found in the doing.* **Rule 44 committed inside the fix for rule 44** — the first
draft filtered on `b.target`, a field the cover has never sent. And four groups had no note at
all, so a search matching nothing left a heading above an empty body (design rule 1).

*What it still cannot do, and says so:* a boundary **target** is not findable — 1,741 of them,
mostly expressions, against nine kinds in memory. The note names the source search instead.

**And it takes a regular expression now.** *"Does that mean I can use regex in the Search
box?"* — yes, but in the *other* one: the Code box has taken a pattern since it was built and
the topbar was a substring test. Tom's call, give the topbar the same three flags. `Aa`,
`|ab|`, `.*`, with their own keys so a literal name hunt and a pattern grep can be in force at
once. Compiled **once per keystroke** and cached on the query plus the flags — 5,560 names
means a per-row compile would be 5,560 of them per character. A pattern that will not compile
**says why** rather than reading as *nothing matches*, which is the false conclusion this
whole thread began with.

### Before that: the cursor over a diagram (2026-09-02)

**Opened as "the arrow stroke is 1 px, thin to aim at" and that was the smaller half.** Tom
drove it: the `cursor: pointer` hand is the web's *this is a link* glyph, wrong for a drawing
you **aim** at — its hotspot is a guess and it covers what you are aiming at. Both the cursor
and the stroke are Settings now (design rule 2): arrow / crosshair / hand, defaulting to
**arrow**, and 1–4× on the stroke, which had no width set at all and so took Graphviz's
default of 1.

**The first fix was wrong and the report corrected it.** It styled only what was *pickable*
and left `.dgm-canvas { cursor: grab }` alone — *"still Hand most of the time, it only
switches to arrow when near the link."* The canvas is most of what a pointer is ever over.

**And then it turned out not to be an aiming fix at all:** *"This change resolved a major
confusion for me… now I understand how the diagrams work — click to view Inspector."* The
canvas's `grab` was a claim that the surface pans, and it **wins on area**; the boxes' own
`pointer` was visible only in the instant the pointer crossed one, so the drawing read as a
picture to pan rather than a set of things to click. Every control was wired and the
self-check passed the whole time — nobody found out clicking a box opened the inspector.
That is **design rule 27**, and it is design rule 16 from the far side.

*Also fixed on the way: `:active` was the wrong moment for the grabbing hand — it fires on
any press, so it flashed on every click of a box. It is on the real `dragging` flag now, past
the slop, which is rule 72's own lesson in a cursor.*

### Before that: structures, compared at last (2026-09-02)

**The last prose surface, and it was three lanes rather than one.** A class docstring was
compared by nothing — and so was the *presence* of a class, which is why the docstring had
been left out: there was no row for it to be a tag on. On Mensores' pair that hid **8
structures that appear or vanish**, reported nowhere, on a page free to say *no differences
found*.

**The subject question was settled by measuring the wrong answer first.** Rule 74 says a
diagram box *is* a class, so routing through `state.fold` looks obvious. A box is built from
**routine** nodes, so it exists only where a class has methods: 192 of 671, with **every**
TYPE_ALIAS, ENUM and TYPEDDICT having none and never able to — and 4 of the 8 rows that
actually move have no methods. Rule 77, a third time, caught by counting. Nothing had to be
minted instead: `describe()` already resolves a `structures.id`, verified live on a
methodless TYPE_ALIAS before a line was written, so these rows carry an **id** where the four
presence lines carry only a name — rule 30 applied honestly rather than uniformly.

Tom took **Structures** for the name (the store's own word; "Classes" would be wrong for the
138 aliases and enums) and added the *declares differently* lane on top of what he asked for,
so nothing about a structure is left uncompared: `7 · 1 · 1 · 0` on the pair.

**A defect shipped and caught within the hour, and it is rule 40.** `structures_explained`
returned 5 against a ground truth of 0 — every one already a presence row, because
`_moved_prose` compares the **union** of the id sets and a structure on one side only carries
its docstring with it. Two lanes recording one act. Caught only because the number disagreed
with a measurement taken before the code existed; the routine and module lanes each guard it
in a different place, so this was the third application of one rule.

**A surviving mutation that was the guard's fault.** Keying fields on `idx` rather than
`name` survived the reorder test, because the fixture's two fields differed only in name —
swap them and *either* key gives the same set. They differ in type now and it is caught. Rule
59's companion: ask whether the guard is weak before changing either.

**+13.3 ms**, median of four alternating builds of HEAD and this in one process on a warm
disk — inside the 20 ms `/api/changes` had left. Driven in Chrome on the real pair: bands,
counts, singulars, tags and stat tiles all correct, the row reachable by `elementFromPoint`
and clicked through a **real pointer sequence** landing on a child element, and the inspector
answering `ClaimVerdict · ANALYZED · STRUCTURE` — the structure, not one of its members.

*Found in passing and left alone: clicking a change row files **two** trail steps. Verified
pre-existing — a routine row does it too — so it is rule 76's family and not this work's.*

### Before that: the record split into files that can be carried (2026-09-02)

`CLAUDE.md` had reached 162,893 bytes, past the 150,000 a session loads — so it was being
**truncated silently**, and the part falling off the end was whatever sat there. Two thirds
of it was 102 rules, cited as bare numbers 768 times across `src/` and `tests/`, so nothing
could be deleted or renumbered. The bodies moved and the titles stayed:

**Figures as measured at the split, 2026-09-02, and left as taken.** Every count and byte
size below is of that day — the rules have been added to since, and rewriting one column
without retaking the other is a different measurement under the same label (rule 24). The
live counts are at the head of this file.

| File | Was | Now | Holds |
|---|---|---|---|
| `CLAUDE.md` | 162,893 | **34,583** | commands, gates, architecture, the **index** of all 102 rules |
| `BRIEFING.md` | 122,578 | **46,056** | state; the `Before that:` chain became a 26-row pointer table |
| `RULES.md` | — | 92,158 | the 76 engineering rules, verbatim |
| `DESIGN-RULES.md` | — | 27,029 | the 26 design rules, verbatim |
| `PERFORMANCE.md` | — | 22,154 | every measured figure, verbatim |
| `HANDOFF.md` | 443,524 | unchanged | the archive, read on demand rather than loaded |

Proved lossless by construction rather than by reading a 3,194-line diff: the split
**reconstructs the original byte for byte**; 1,972 of 1,974 substantive lines were found
verbatim in the new set, the two misses being the two deliberately rewritten; rule numbers
were **enumerated**, 1–77 with 21 correctly absent; all 33 pointer anchors resolved before
the cut; and the cut region was scanned for open items, which found **two that lived nowhere
else in this file** — the blank-graph fix and the `m.<module>` research — now restored to
the open list below. Analysing both trees gave identical doc figures, so the duplicated
titles cost nothing: the index is fenced, and rule 12 keeps prose out of a fence.

**Read `RULES.md` before working in an area a rule governs.** A title is enough to recognise
that a rule applies and not enough to apply it — that is the one risk this split carries.

### Before that: what a routine says about itself, and what a module says it is (2026-09-01)


**The last item on the open list, and it turned out to be two.** `routines.docstring` was in
the store and compared by nothing; so was `files.doc`, and they need different subjects.

**The routine lane corrects a reason, not an absence — which is what makes it unlike the
comment lane.** A leading comment sits above the `def` and so outside `body_hash`, which is
why rewriting one could vanish entirely. A docstring is *inside* the `def`, so it is always
inside `body_hash` and always reported — filed under **edited only**, the band this tool
describes in its own words as *internal computation, what it exists not to report*. On
Mensores' pair `_production_audit_db_path` had a deprecation notice and its whole reasoning
rewritten and sat exactly there. So `docstring` is a **tag** beside `comments`, and it can
never be a band: `explained_only` holds what would be in no band, and nothing reaches it by
this route.

**The canonical question, asked a fourth time and answered differently — by measurement.**
`_constants_moved` predicted this would come round and said the answer would depend on how
the column is filled. It does. A comment reaches the store as one row per *physical line*
with no paragraph structure left to keep, so the comment lane joins the lot and collapses.
A docstring arrives as one string through `inspect.cleandoc`, **blank lines intact**, so the
structure is there to keep. Two experiments over the real 3,769:

```
re-wrapped at 72 / 79 / 88,      as written    2,060 · 1,652 · 1,602 falsely reported
not one word altered             collapsed         0 ·     0 ·     0
                                 by paragraph      0 ·     0 ·     0

every paragraph merged,          collapsed         0 reported   ← blind
1,996 affected                   by paragraph  1,996 reported
```

Both forms are silent on the noise, so the re-wrap does not choose between them. Merging
paragraphs does: it changes no word and destroys the separation PEP 257 gives the summary
line, and a full collapse cannot see it. Same zero on the noise, 1,996 more on the signal.

**The module lane is a new subject, and it is Tom's call.** `files.doc` states what a module
*is* — 619 of 628 files. The cheap implementation is to hang it on `<module>`, and it covers
**487 of 628** while missing 141 *silently*: `<module>` exists only where a file runs
something at import, so in a file that runs nothing, a rewritten module docstring moves no
body hash, no fact and no row, and the page states **"No differences found."** That is
**rule 77**, and it was caught by counting rather than by a false result — 619 against 487,
one query each. `modules_explained` rows carry a **path**, and the route opens the file.

**Two live defects found on the way, neither of them in this work.**

*The navigator's note had been wrong since the comment lane landed.* `changeNote()` decided
"no differences found" from `only_in_base + only_in_compared + behaves + edited_only` — so a
pair whose one difference is a rewritten comment, a table that appeared, or a constant whose
value moved said **no differences found** in the group a reader lands in first, while the
page below listed it. The same false claim the explained band was built to remove, surviving
in the other of the two surfaces (rule 51). `identical` is the server's own answer and is now
what is asked.

*And the file route did nothing visible.* Found by clicking the row, not by any test:
`openCodeFile` opens the pane and leaves the centre alone, which is right inside the Code
group and wrong from a worklist page — state set, file loaded, not a pixel moved. Rule 77's
companion, and rule 51 in the shape that rule is about.

```
18/18 mutations caught over a baseline proved green first
three passes: five survived the first (three unguarded surfaces, one weak fixture, and two
weak mutations — the `behaves` one wrote to `moved` after `behaves` was computed); one
survived the second, and it was my own guard summing two overlapping substring counts so
either site could drop the plural and still clear the bar
```

**+3 ms, and it is measured like for like**: 451 → 454, median of eight alternating builds
of HEAD and this in one process against a warm disk. The two lanes are 3.2 ms and 2.2 ms in
isolation, and the shared bound takes the docstring lane from 22.3 ms over all 628 files to
3.2 over the fifteen that differ — 19 ms, which is almost exactly the 20 ms of headroom that
row has. That bound now has a guard of its own, because no *answer* can catch it being
removed: every prose lane returns the same rows bounded or not.

**Absent rather than estimated: a picture of the band.** The automation tab's capture is
fixed at 784×349 whatever the window (rule 38), so the worklist below the fold cannot be
photographed. What *was* driven: both docstring tags on the real Mensores pair, the edited
tooltip, the band and its stat tile, the row reachable by `elementFromPoint` and clicked
through a real pointer event to the file, the navigator group joining the same accordion,
and the singular. The stat tile's violet is visible in the one capture that fits.

### Two things waiting on Tom's eye, and neither is a bug

1. ~~**The flow panel's arrow stroke is 1 px**, which is thin to aim at.~~ *Closed
   2026-09-02, and it was never really about the arrow — see the top of this file. The
   stroke is a Setting now, and the **cursor** turned out to be the larger half: `grab` on
   the canvas was claiming the whole pane pans, which drowned out the boxes saying they are
   clickable. That earned **design rule 27**.*
2. ~~**A 1,347-line `frozenset` argument exists in this corpus**~~ *Closed 2026-09-02, and
   the constants half of it is built. The entry had already been corrected once: the
   `frozenset` is **not reachable from the flow panel at all** — external, `at_boundary = 0`,
   a builtin, so no arrow is drawn — and the same expression sits in the store twice, as
   91,224 bytes in `call_args` and as **6,924 on one line** in `constants`. The constants
   surface now shows a value whole in a box that scrolls, and the card bounds itself and says
   by how much. Its real worst case turned out to be `GOVERNED_GATES` at **8,586**, which
   nobody had named. The `call_args` side keeps its recorded* wrapped, not elided *decision.*

*There was a third — the routine lane drawing* behaves differently *in `--text-muted` while
the legend and the findings drew the same idea in `--diff-moved`. Put to Tom on 2026-09-01
and unified on `--diff-moved`; see the top of this file.*

### The next pass, as scheduled

Tom, 2026-09-08, on the four defects: *"add the other items for the next pass after this
one."* This is that list, and it is drawn from the entries below rather than kept beside
them — the entries are still where an item is closed, and this is only the order.

0. ~~**Press the five new settings controls with a real pointer.**~~ *Paid 2026-09-08. All
   five pressed at the pointer against Tom's own arrangement, at a window he sized and the
   automation never touched, each with an `elementFromPoint` pre-check before and its
   **consequence** after — never `aria-pressed` alone. The strongest is **Wrap it**: 0 →
   **2,674** `<wbr>` seams inserted into rows the navigator had already drawn, which is rule
   78 observed rather than argued. See the top of this file and `HANDOFF.md`. The obstacle
   recorded earlier the same day — a "pointer floor" just above the toolbar — did not exist;
   it was **rule 90**, and the window had gone behind another one.*
1. **Three things have never been *looked* at.** *Two are answered 2026-09-08 — see the top
   of this file.* The **kept fold** and **kept flow** both open from the shelf, verified at
   the pointer, and the stated cross-compartment limitation is honest. The **hover card's
   shadow sentence** turns out to be **dead code**: a shadow is drawn at radius 0 and alpha 0
   and both paths into `onHover` resolve through `realIndex`, so `h.shadow` can never be
   true — 1,989 picks over 562 distinct nodes returned not one shadow. *Withdrawing it is
   Tom's call, below.* Still open: the **worklist's and the ribbon's row layouts**, which are
   design calls waiting on Tom's eye — and the navigator's rows have joined them with a
   number (below). The instrument reaches all of them, and rule 83 is now measured rather than
   described: pointer space and capture space are both 784 px wide and differ by **exactly
   2×**, so `pointer = viewport / 1.5581` and `viewport = screenshot × 0.779`. **A body pan
   breaks hovering while it lasts** — pan to find a target, un-pan to touch it.
2. ~~**Two maps in `output/` cannot be opened**, both refusing exactly as designed and both
   one command away.~~ *Closed 2026-09-08, and it was wrong on both counts — see the top of
   this file. There were **three**, not two, and the command each was sent to would have
   refused it: `_refuse_if_stale` branched on absolute paths where the migration branches on
   a fingerprint. Three of the four now open; the fourth is a decision below rather than a
   defect.*
3. ~~**The superseded snapshot's sidecar rows.**~~ *Closed 2026-09-08 — Tom ran the command,
   and it is verified at the top of this file.*
4. ~~**The rebuild-recipe rule**, to mint or refuse.~~ *Minted as **rule 88** in the session
   that filed this — `RULES.md:1644`, and `CLAUDE.md`'s index carries it. The entry outlived
   its own closure by a day.*
5. **Three found while looking. Tom answered two the same day.** The **dead shadow branch**
   is *withdrawn*, with a guard that asserts the two facts closing it before it asserts the
   consequence. The **navigator rows** got Tom's mechanism — the module path yields its width
   first — which is **335 → 266 rows and 101 px → 49 px at the declared 21rem**, a fifth
   better and *not closed*: the remainder needs a decision about the **name** (wrap, truncate,
   or let the row grow, rule 84), and each is rejected by one of the two comments over
   `.navlabel`. ~~**Still open.**~~ *Answered 2026-09-08: Tom's call was **build both and make
   it a Setting** (design rule 2), and `navName` does — as it is · cut it · wrap it, with the
   present behaviour the default. The remainder is therefore no longer a decision anybody
   owes; what is left is which option real use retires, and the usage counter answers that.*
   ~~Two pluralisations, *"1 boxes"* and *"1 call sites"*, need
   nobody and are not done.~~ *Closed 2026-09-08 — and it was **eight** counts rather than
   two; see the top of this file.* ~~**One more found the same way and untouched:** at
   `innerWidth 1224` the document is **1336** wide, so the inspector's own controls sit off
   the right edge and the whole page scrolls sideways.~~ *Closed 2026-09-08 by `topFit`,
   which releases `.app`'s column while it is on — 1336 → 1280 at `innerWidth 1280`, with
   ⚙ Settings 14 px inside the window instead of 43 px past it.*
6. ~~**The legend rail does not restore the pane.**~~ *Closed 2026-09-08, and the diagnosis
   was wrong while the symptom was real — rule 39 exactly. **It restores the pane**: pressed
   with a real pointer at (970, 471) `data-legend` goes `off` → `on`, and a scripted click
   agrees and is idempotent. What could not be done was **reach** it. `.app` is a grid with
   one implicit column, sized to its widest row, so the toolbar's width is `.body`'s width
   and every right-hand rail is carried out of the window with it — at `innerWidth 1220` the
   legend rail sits at **1281–1309** and the inspector rail at **1309–1337**, both wholly
   outside, with `elementFromPoint` returning null over either. Tom's call on the fix was
   design rule 2, so `paneFit` is a fourth setting beside the three from the same day, off by
   default; see the top of this file.*
7. ~~**`wrap` breaks a seamless name at an arbitrary character.**~~ *Closed 2026-09-08 —
   Tom's call was a fourth option nobody had listed: divide it at **smart intervals**, reusing
   what was written. `jointed()` now does, at the corpus' own median run of five characters.
   See the top of this file.*
8. ~~**An automatic collapse at narrow widths — offered 2026-09-08, unanswered.**~~ *Answered
   and built 2026-09-08 — see the top of this file. Tom: "Item 8 should auto-collapse." The
   trap the entry below records is closed by `paneHeld`, and a fifth setting joins the
   family as the only one that ships on. The entry as it was filed:* The
   narrow-window fix removed the breakpoints that *deleted* a pane and gave `.body` a floor
   and a scrollbar instead, so nothing vanishes and both rails work at every width. What was
   deliberately **not** built is a window that collapses a pane *by itself* when it will not
   fit. With the row scrolling there is no longer a need for one, and it is a different call
   — a window rearranging what the reader arranged. `inspectorAuto` is the shape it would
   have to take, and its own comment records the trap: an auto-close makes the rail
   unclickable, because pressing it reopens the pane and the rule immediately re-collapses
   it, *"which reads as broken"*. So it needs a per-pane "the reader asked for this" flag
   that a widening window resets. Tom's call, and no work until he makes it.
9. Then the standing backlog below, none of it scheduled.

### What is next, and it is open

Nothing in the anomaly worklist's chunk 5 is outstanding, the argument gap is closed, and
the two small things filed as known are done. *(That is the worklist's chunk 5, written here
2026-09-01 and unrelated to Document mode's chunk 5, which landed 2026-09-04 and is at the top
of this file. Two features numbered their chunks from one; the sentence was unambiguous until
the second one existed.)*

1. ~~**`CURIOSITIES` has never been put on screen.**~~ *Built 2026-09-01.*
2. ~~**A rewritten docstring is not compared either.**~~ *Built 2026-09-01, and it was two
   lanes rather than one — see the top of this file.*

**This file owns the open list. There is no second copy.** `HANDOFF.md` used to keep one at
its foot and the two drifted twice in two days — an audit on 2026-09-02 found each carrying
something the other had closed, and then the same session closed the class docstring in one
copy and not the other. Rule 51 in the documents: one truth, one place that owns it. Record
*how* an item was closed in `HANDOFF` under its own dated heading; record *whether* it is
open here.

Audited entry by entry on 2026-09-02, none of it scheduled:

*Struck in that audit:* **"what is an occurrence for `LOST_EDGE`"** had stood as a question
for Tom that decided a whole feature. It **dissolved** on 2026-08-31 rather than being
answered — the detector groups by `callee_expr`, so a finding is one per expression, the
callers are its count and the rivals are in its title — and the anomaly worklist it was said
to block was built the same day. It had been telling every session since that the largest
feature was blocked on an answer nobody owed.

- ~~**A class docstring is still compared by nothing.**~~ *Built 2026-09-02, and it was
  three lanes rather than one — presence, declaration and docstring. See the top of this
  file.*
- ~~**Chunk B of the shortening work: twelve fields still cut the tail.**~~ *Built
  2026-09-03, and measuring first struck three of the twelve and changed the mechanism — see
  the top of this file. The budgets are **measured at render time**, not constants; the
  `selfCheck` assertion exists and is honest; `.wl-title` is prose and refuses the
  middle-elide; `.srcpath-v` was a dead field; `.callhead code` wraps. `.navsub` keeps its
  constant and the boundary is stated. `.argrow` keeps its* wrapped, not elided *decision;
  `.leg .nm` is left alone.*
- ~~**A program selector**~~ *— built 2026-09-04.* ~~**"+ Analyze a directory…"**~~ *— built
  2026-09-04 too, and the option is in the `<select>` now that it does something. See the top
  of this file. The original entry:* Tom, 2026-09-04: *"What is
  missing is a way to switch between the two — that used to exist… I definitely want to add
  the Analyze a directory part next. That's what I'm looking for at the moment."* The
  ratified artifact `f993d319` has the selector — three options, `mensores — 623 files`,
  `dunneflow — 23 files`, `+ Analyze a directory…` — and **no change handler even there**.
  The port carried the markup and emptied the options with every other pinned array; unlike
  the others it never got the endpoint that fills it. What exists to build on: `_Live.open()`
  already rebuilds a whole base atomically against a different graph and refuses without
  leaving a broken one behind, which is the revision switch — a program switch is the same
  operation pointed at a different directory. What has to be decided: `serve` takes a
  program directory today and would take the root while still accepting either; a program
  switch cannot keep the selection, the trail or the revision, all of which belong to the old
  program; and the list must say what it found *and* what it cannot open, because
  `output/` here holds four candidates of which two are stale or old-style.
- ~~**"About this map": what read this directory, and whether anything was inferred.**~~
  *Built 2026-09-04 — see the top of this file. The entry as it was filed:* Tom asked that an
  analysis record **what model was used**, in an *"About this directory"* dialog, so a reader
  might analyse again when a better one exists.

  **No model is used**, and that was checked before it was planned: the extractors are
  stdlib `ast` and `tokenize`, the document scanner is hand-written, and there is no LLM call
  and no network egress anywhere on the analysis path. `Provenance` declares four tiers and
  only the two free ones are built — `CITED` and `INFERRED` are designed and unbuilt.

  Tom, on being told: *"Perfect, keep it that way as much as possible! Inference should
  always be voluntary and secondary."* So the row is **a standing guarantee, not a
  placeholder** — *nothing in this map was inferred, and nothing was read by a model* — and
  the model field exists so that a reader who ever turns inference on **voluntarily** can see
  which facts it paid for.

  **And the live re-analysis trigger already exists and is surfaced nowhere.** Every store
  records `extractor = f"{SCHEMA_VERSION}:{rules_fingerprint()}"`, and `_is_stale` compares
  it against this build's — today only to refuse. That comparison *is* "would a newer
  DunneFlow read this differently?", which is the question Tom wants answered; it has never
  had a reader. The plan is at `~/.claude/plans/wondrous-crunching-ocean.md`.

  *Candidate design rule, for Tom to mint or refuse:* **inference is voluntary and secondary,
  and a map states whether any was used.** One step over from design rule 14, which scopes
  *egress*; this scopes whether a fact was *guessed*.

- ~~**Five surfaces have never been *looked* at in a real window.**~~ *Discharged
  2026-09-06 — all five seen, and the obstacle was never the surfaces. See the top of this
  file and `HANDOFF.md` under that date. The instrument was misread for four sessions: the
  automation tab's **screenshot** covers `inner ÷ dpr` — the top-left quarter — while its
  **click** frame covers the whole viewport, so the two differ by exactly the device pixel
  ratio. The pointer could always reach the inspector at x=985; only sight stopped halfway.
  A click computed as `784 / innerWidth` lands on the element (verified against a capturing
  `pointerdown` listener), and `transform: translate(-x,-y)` on the app root pans the capture
  window over the real page at full fidelity. `resize_window` does not refuse — it reports
  success and changes nothing.*
- ~~**Ways in as nodes on the Diagram**~~ — *built 2026-09-05, an hour after being deferred.
  Drawn by default on a measurement (ports max 41 per compartment, ways in max 3), arrows
  bounded at 8 per way in with the bound stated, and clicking one opens the way-in pane. An
  entry arrow refuses to open as a flow and says why: the caller is the operating system.*
- ~~**A package row does not make a selection.**~~ *Built 2026-09-05 — see the top of this
  file. A plate is a fourth subject beside `flow`, `fold` and `selected`, answered by
  `web/plate.py` and drawn by `viewInspectorPlate` on the `viewInspectorConstant` precedent.
  It decided what selecting a package **is**: not a nominated member (rules 30 and 74), and
  **mark-and-state rather than a filter** — the fold's settled shape one level up, so the
  rows are marked, the count says how many, and the table stays the whole program. Three
  pre-existing gaps went with it: the table marked on `state.selected` alone, the crumb read
  `state.selected` alone, and the package row lost its own `aria-current` to the rebuild its
  own click triggers.*

- ~~**`<module>` is answered in a routine-shaped inspector.**~~ *Built 2026-09-05 — see the
  top of this file. It was **two** false statements rather than one: the three-way "way in,
  dead code, or a call DunneFlow cannot see" hint, false of all 487 module nodes (0 callers,
  0 entrypoints, measured); and `def <module>():`, a copyable declaration of a routine
  nobody wrote, which `hoverSigHtml` already refuses one surface over. Not a separate pane —
  Out, Touches and Governance are all correct for module scope, and copying them would be
  rule 51's own defect.*

- ~~**Clicking a change row files two trail steps**~~ *— closed 2026-09-07, and* **corrected**
  *rather than merely struck. No path files two, and the change row is not among the affected
  paths at all: it sets its subject synchronously, so the dispatcher's step lands correctly.
  What was real is that seven callers named a step* around *an async move and lost what they
  were saying — the label replaced by one arbitrary member of the selection, the note written
  onto the step being left. The half the entry got right is that it belonged to the selection
  path. See the top of this file. Filed from reasoning in 2026-09-02, and both descriptions of
  it were wrong until it was measured.*
- ~~**A kept fold and a kept flow have never been opened on screen.**~~ *Closed
  2026-09-08 — both open from the shelf, verified at the pointer, and the stated
  cross-compartment limitation is honest. It is recorded under item 1 of the scheduled pass
  and was never struck here; this file owns the open list and the two disagreed for a day.*
- ~~**Every surface that offers "keep this" is an inspector pane.**~~ *Built 2026-09-06 — see
  the top of this file. Four surfaces gained it, not three: the naming convention row mints the
  same cohort a thread does. **Two routes, Tom's call**, because `PIN_ROUTES` is keyed on `kind`
  ∈ {node, fold, flow, plate, line} and `THREAD_SUBJECTS` on `type` ∈ {node, cohort} — one word
  meaning two things in one table is rule 47's companion. A thread's node subject is translated
  into the map space so the two doors mint one pin; a cohort's note is a `noun` that counts
  nothing and its size is asked for live; a kept **line** records the revision it was kept at.
  The search hit was in the plan on evidence: `goToCode(path, line)` already existed, which is
  the third item in two days recorded as blocked and found not to be.*
- ~~**`holds` is not in `insp`'s defaults.**~~ *Fixed 2026-09-08, and it was **three** keys
  rather than one — `holds` (a fold's contents and a plate's), `stands` (what a merged plate
  stands for) and `calls` (the call sites behind an arrow). Each is the answer its pane
  exists to give rather than a caveat on one it already had, which is the test `loops` and
  `shape` were named under, so all three open. The entry stood for six days as a note about
  one section while two more joined it in silence, which is what a guard is for:
  `test_every_inspector_section_declares_its_default` reads the `sec("…")` keys out of the
  shell and requires each to be named in the settings.*
- ~~**`navIds` splits `data-navid` on a space.**~~ *Fixed 2026-09-08, and the fix is not the
  one the entry implied. A separator no name can contain — a control character — gives up the
  one thing the space was chosen for, an attribute a person can read when something goes
  wrong. Instead the **row declares** whether it holds several: `data-navmulti`, written by
  the single producer that joins any (the ways-in rows, whose ids are digests), and a single
  id comes back whole whatever characters it holds.*
- ~~**The blank-graph fix (rule 49) is reasoned and guarded, never *seen*.**~~ *Seen
  2026-09-06. The premise was false: the graph **does** mount in the automation tab —
  `canvas MISSING` was a read taken while the pane still said "reading the stack…". Four
  seconds later there is a canvas, 10,015 nodes and 53 plates, and WebGL was available all
  along. `Snap to fit` pressed with the pointer framed the selection to the real 621×333
  canvas.*
- **A known-standards directory, to compare reality against intent.** Tom, 2026-09-04:
  *"I am interested in creating a known standards directory as a baseline against which to
  compare what is really found. The goal is to show reality, not the plan."* The wording
  change of that date is the honest stopgap, not the feature. What was found while surveying
  it, all measured on Mensores:

  - **Ingest exists and is narrow.** `_maybe_rule()` mines `doc_rules` during the ordinary
    docs scan — `lane`, `scope`, `pattern`, `checkable` all in the schema already. Gated to
    six rule-bearing classes on evidence (a research paper *about* naming standards yielded
    ten confident false FORM rules). There is **no import gesture**: `--docs` takes one root
    and replaces the default, so an outside standards directory cannot be added to a scan.
  - **Yield: 5 rules, from 1 of 29 rule-bearing documents.** All VOCABULARY, all
    `checkable = 0`. **Zero FORM rules across the whole corpus**, so the checkable machinery
    has never had an input.
  - **Nothing compares.** `checkable` is read by one thing: a sentence in the report saying
    whether it is checkable. `scope` and `pattern` are stored and consumed by nothing.
  - **The best standard in the corpus is a table, and the detector cannot see it.**
    `harness/rules/style.md:30`, heading "Naming Conventions", header
    `Type | Convention | Example`, **seven rows** — Files kebab-case, Commands
    `paul:kebab-case`, Step names snake_case, Bash variables CAPS_UNDERSCORES, Type
    attributes colon separator, Phase directories `NN-kebab-name`, Plan files
    `NN-NN-PLAN.md`. Every row is a `scope` and a `pattern`, which is exactly the pair the
    FORM lane needs. The table **is fully captured** in `doc_tables`/`doc_table_rows`; the
    rule detector returns on `text.startswith("|")` at `markdown.py:468` and never sees it.
    A table is how most enterprises write a naming standard.
  - **The scoping mechanism is already in the store and read by nothing.**
    `harness/rules/style.md` carries frontmatter `paths: ['src/**/*.md']`, and **62 documents
    in this corpus carry a `paths`, `area` or `applies_to` key** — captured in
    `documents.frontmatter`. That is the "only some parts are relevant" half, present and
    unused. `Society-Specs/01-naming-standards.md` is Society's own spec asking for exactly
    this: *"a naming standard directory that contains multiple documents, each of which
    identifies one or more subsystems."*

  Order, cheapest and highest-value first: ~~**(1)** read a table as rules~~ — *built
  2026-09-04, see the record: 0 FORM rules became 7, and one table of 5,230 fires*;
  ~~**(2)** serve the stated lane to the dashboard~~ — *built 2026-09-05, and it is two pages
  rather than one section: see the top of this file. `scope` and `pattern` reach a screen for
  the first time, and the three ways a program can state nothing each got their own sentence*;
  ~~**(3)** compare a checkable rule against the graph~~ and ~~**(4)** `--standards <dir>`~~ —
  *both built 2026-09-06, and **in that reversed order, on evidence**. Step 3 as written would
  have made the tool confidently wrong: none of the six checkable rules is a question about
  `graph.db`, and checked against it "Files: kebab-case" scores 0 of 628 Python files for a
  rule its own document scopes to three markdown files. The population is now never inferred
  from the scope word. See the top of this file.*

  *Also corrected here: this list said **62 documents carry a `paths`, `area` or
  `applies_to` key**. By key rather than by substring it is `paths` **5**, `applies_to` **4**,
  `area` **8** — and only `harness/rules/style.md` carries both a scope and any rules.*
- **`m.<module>` as a language feature, with research owed on prior art** — how other tools
  present a construct the *language* put there rather than an author. Decided 2026-08-30:
  not filtered and not bare, but a curiosity carrying its own explanation, scoped to the
  language that produced it rather than special-cased in the diff.
- ~~**The worklist's two jump buttons are half done.**~~ *Built 2026-09-06. It was less
  blocked than recorded: every detector already selected rows identifying its occurrences and
  threw the identity away, keeping the names as prose in `detail` — rule 41. `Anomaly` now
  carries `occurrences` (each naming a route `NAV_ROUTES` already has, so nothing translates)
  and `unenumerated` for a finding that can list nothing. All 107 of Mensores' findings
  enumerate; `LOST_EDGE` opens its **call sites**, because the callee not resolving is the
  finding and opening a rival would be rule 5's guess dressed as a destination.*
- ~~**Per-plate sphere scaling**~~ *— built 2026-09-09, and it turned out to be a units
  bug rather than a feature: a node's radius was a pixel constant and a plate's width a
  world quantity, so a dot knew nothing about the room it had. See the top of this file.*
  ~~**Stack orientation** is still open and is structural: `OrbitView` has no camera roll.~~
  *Closed 2026-09-09 by decision. Tom: "I think stack orientation is acceptable as-is,
  adding camera roll is not required. I can already move the camera quite a lot." Recorded
  beside the `OrbitView` construction in `graph.js`, where the constraint is.*
- ~~**The two vocabulary-lane precision defects.**~~ *Both fixed 2026-09-08 — see the top of
  this file. A DASH_GLOSS mined out of a constraint table is no longer counted as a
  definition (5 refused of 240, all constraints), and the undefined list's head is words
  again rather than the tails of SCREAMING_SNAKE constant names (1,154 → 265, with 890 held
  back, listed, and each one offered back to the worklist by hand).*
- ~~**The rendered markdown is not revision-named.**~~ *Built 2026-09-08 — see the top of
  this file. Maps are `map@<revision>/` and the program directory opens on a listing of what
  it holds.*
- ~~**Rendering a named revision's map from the graph it already has.**~~ *Built
  2026-09-09 — `dunneflow render`, see the top of this file. Both mapless snapshots in
  `output/mensores` have their maps, in 33 s, with 8787 holding the directory open
  throughout. It cost twenty-eight signatures first: `root` and `docs_root` were read by no
  renderer and a map needs neither tree, which is the fact that makes the feature possible
  and which nothing had ever stated.*
- ~~**Switching to `one size` zooms the picture in, and nothing on the control says so.**~~
  *Closed 2026-09-09 **by decision**, which is the third way out and neither of the two that
  were offered. Tom: "One size is fine, I sign off on that. We can mention the behavior in
  the documentation." The behaviour stands; the silence does not. See the top of this file,
  and design rule 6, which gained the general form: a clamp is felt through whichever control
  moves it, so that control has to name it.*
- ~~**`touches --routine` prefix-matches a name that is not a routine.**~~ *Fixed
  2026-09-09 — see the top of this file. Three answers, never two, and the substring
  fallback is kept and labelled rather than removed. The true answer for the case that bit
  turned out to come from `files` rather than `routines`: a package `__init__` declares no
  routines of its own, so the obvious query says "not a module here" about a file the
  analysis had read. Two bounded-answer silences went with it, in the exact branch as well
  as the fallback (rule 32).*
- ~~**A map's fourteen inner pages still say only `Generated <now>`.**~~ *Fixed 2026-09-09
  — see the top of this file. `render/page.py` is the one header, and the cover's own
  three-line section is retired into it on Tom's call: all three instants survive on fifteen
  pages instead of one. Verified where it matters, by re-rendering: `source read 19:02 ·
  these documents written 19:03` on an inner page.*
- The filed small things: `--revision` on `analyze` (it exists on `serve` only), the
  navigator's search box pinned-when-open (decided 2026-08-30, never built).

### Packaging — **built 2026-09-09**; the five blockers, and what each turned out to be

Tom, 2026-09-09: *"Once these are done, work on the packaging issues and then we can build
it. May take a couple of milestones."* A single double-clickable binary is the product and
not for convenience: DunneFlow reads private source and `source.db` contains it, so a hosted
model would send an unfamiliar codebase to a server (design rule 14).

**All five are closed**, in the order written below, which was the record's own. What each
*turned out* to be is marked under it, and the entries are left as they were filed because
two of them were incomplete — which is worth being able to see.

**Five blockers, read out of the code on 2026-09-09.** The first three are defects in code
that already exists and can be fixed and tested *before* anything is frozen; the last two are
a feature — the app's cold start — rather than packaging.

1. **`rules_fingerprint()` would silently return the hash of nothing.**
   `code_extraction_inputs()` globs `detectors/*.yaml` and `extractors/python/**/*.py`, and
   `doc_extraction_inputs()` includes `Path(__file__)`. Frozen, those globs come back empty
   and `fingerprint_files([])` returns `e3b0c44298fc1c14` — the sha256 of nothing, which looks
   exactly like a fingerprint. `SCHEMA_VERSION` still carries the other half of the key, so
   what dies is precisely the half added so a forgotten manual bump would stop being
   load-bearing (rule 12). Bundle the readers as data, **and** make `fingerprint_files` refuse
   an empty input.
   *Closed, and it was **two** failures rather than one. `doc_extraction_inputs()` returns
   `Path(__file__)` unconditionally, so frozen that list is never **empty** — it holds a name
   with no file, and an emptiness check alone passes it straight through to a
   `FileNotFoundError` raised from inside a hash. `RulesMissing` refuses both, and a directory
   where a file was meant.*
2. **`multiprocessing.freeze_support()` is nowhere.** `walk.py` opens a
   `ProcessPoolExecutor` in two places and macOS spawns, so a frozen app re-executes itself
   per worker. It has to be the first statement in the entry point.
   *Closed, in both entry points. Worth adding, because it reads like a safety net and is
   not: **`walk.py`'s serial fallback cannot catch this.** The `try` wraps the whole `with
   ProcessPoolExecutor(…)` block, and nothing in the parent raises — the parent is fine and
   the children are the program. Observed working: 628 files through the binary, sixteen
   workers, one application.*
3. **`analysis.argv()` is dead in a frozen app.** It builds
   `[sys.executable, "-m", "dunneflow.cli", …]`, and `-m` means nothing to a frozen binary —
   so **+ Analyze a directory…**, the only way a first-time reader gets a map at all, would
   never run. Small fix, and `argv` was already split out so a test can read it.
   *Closed — `runtime.self_argv`, with a guard refusing any `sys.executable` under `src/`
   outside that module.*
4. **`serve` cannot boot with nothing to serve.** It raises *"no graph in … — run
   `dunneflow analyze` first"*, and a double-clicked app has neither an argument nor, on a
   fresh machine, a map. It needs a cold start: open on the output root, list what is there,
   offer the analyze dialog. Everything needed exists and opens no graph —
   `revisions.program_dirs()`, `/api/programs`, `analysis.check`; what does not exist is a
   `_Live` that is legitimately **empty**. Design rule 21 in the largest place it has applied.
   *Closed, and **not** by drawing the shell empty: Tom's call was a start page whose whole job
   is to say there is nothing yet. `_Live.current` raises rather than returning `None`, which
   is how sixty use sites were left alone; the gate is two exemption lists, one per route
   table, each naming the exceptions so a route added tomorrow needs a base by default.*
5. **`DEFAULT_OUTPUT = Path("output")` is relative to a working directory** a double-clicked
   app does not have. `serve`'s `out_dir` positional has to become optional, which is the
   shape `CLAUDE.md` already records: *serve takes a program directory today and would take
   the root while still accepting either.*
   *Closed. The root is a **field** on `_Live` now — four routes derived it as
   `out_dir.parent`, which is right only while there is an `out_dir` to take the parent of.
   `where()` tells a program from a root by whether it holds a map, never by its name. And
   the root is **created only when nobody named one**, which a fresh machine found: it did
   not exist, so the page named a place the reader could not open and* Show me *refused a
   directory that was simply not there.*

Then, and each smaller — **all done except the last two**: bundling `detectors/*.yaml`,
`web/static` (1.7 MB) and `web/vendor` (5.9 MB of deck.gl), all found through
`Path(__file__).parent` — *and `web/`'s two were **not** on this list when it was written,
which is the whole argument for the guard that now refuses a `__file__` under `src/`:
frozen they are a server that starts perfectly and serves 404s*; `_tool_version()`, which
returns `""` with no dist-info — *answered by `copy_metadata('dunneflow')` in the spec
rather than by a frozen branch, so there is still one answer to which DunneFlow read a map,
and the binary records `0.1.0`*; **how a directory is chosen** — *`osascript`, no dependency
and no `pywebview`, beside the typed field rather than instead of it*; the spec file —
*`packaging/dunneflow.spec`*; and **signing**, which is what decides the non-technical
experience and for which the Apple Developer account already exists. Windows last. **Those
two are what is left.**

**The 1,363 tests prove the source tree, not the artifact.** So the ground truth was run
*through the binary*, and every figure held: the four executables at
**1,381 · 423 · 292 · 112**, `naming.md` byte-identical to the `CORP` fixture, the research
paper yielding **zero** naming rules, and — added because a packaged build can fail this way
where a source tree cannot — the conformance verdicts at **4 checked · 1 no population · 10
not checkable**, and the binary's stamped `extractor` equal to the checkout's
`rules_fingerprint()`. `PERFORMANCE.md` carries the timings with their conditions.

### Before this, in order — the full record is `HANDOFF.md`

Each session below was summarised here and is recorded **in full** in `HANDOFF.md`, with
what it cost, what it found, and what was rejected on the way. The anchor is what to search
for; chunk labels (`5v`, `6a`) and dated headings are stable, line numbers are not.

| When | What was built | Search `HANDOFF.md` for |
|---|---|---|
| 2026-09-10 | The user guide, and the one control that named a pair it was not showing | `the user guide, and the one control` |
| 2026-09-10 | Milestone 4: the application says what it is doing, and a build that runs anywhere | `milestone 4: the application` |
| 2026-09-09 | Milestone 3: signed with a Developer ID, and a universal build that refuses to lie | `milestone 3: signed` |
| 2026-09-09 | Milestone 2: packaging, and a `DunneFlow.app` that opens on a fresh machine | `milestone 2: packaging` |
| 2026-09-09 | Clearing the deck: four decisions and a withdrawal | `clearing the deck before the binary` |
| 2026-09-01 | Curiosities: the doorway panel, each extremum stating its middle | `Curiosities: the doorway panel` |
| 2026-09-01 | The change worklist sees a rewritten comment | `sees a rewritten comment` |
| 2026-09-01 | A presence line says what it left out; one idea stops having two colours | `A presence line says what it left out` |
| 2026-09-01 | What a call passes, and what a constant is | `what a call passes` |
| 2026-09-01 | The overlay on the findings, and the key it had to be built on | `The overlay on the findings` |
| 2026-08-31 | A finding says what makes it that finding — the identity question, answered | `what makes it that finding` |
| 2026-08-31 | An edge says what flows, and the echo that had been eating the subject | `An edge says what flows` |
| 2026-08-31 | The call-site arguments, as written | `The arguments, as written` |
| 2026-08-31 | Diagram mode, reading both ways; the box that answers about itself | `Diagram mode — built` · `A box answers about itself` |
| 2026-08-31 | The plate diagram — withdrawn, then built | `Withdrawn — Tom, 2026-08-31` · `The plate as a diagram` |
| 2026-08-31 | Sizing a plate by what it holds | `Sizing a plate by what it holds` |
| 2026-08-31 | The second altitude — the module level of detail | `The second altitude` |
| 2026-08-30 | One history — the trail and undo unified | `6i.` |
| 2026-08-30 | The comparison over the routines: tables and the list (chunk C) | `6g.` |
| 2026-08-30 | The comparison over the code: the code browser (chunk C) | `6f.` |
| 2026-08-30 | Colour sets in Settings (chunk B) | `6e.` |
| 2026-08-30 | Switching the base | `6d.` |
| 2026-08-30 | The default read from the versions, not guessed | `6c.` |
| 2026-08-30 | Base and compared — two directories, no claim about which is newer | `6b.` |
| 2026-08-30 | Stored paths are relative, and the root is not recorded | `6a.` |
| 2026-08-30 | The change worklist, looked at for the first time; choosing two points in time | `5y.` · `5z.` |
| 2026-08-29 | Two points in time, and the change worklist | `5w.` · `5x.` |
| 2026-08-29 | Search inside the source | `5v.` |
| 2026-08-29 | The code browser, and a snapshot that has a name | `5u.` |
| 2026-08-29 | Four panes, and the pop-up that learned to be read | `5t.` |
| 2026-08-28/29 | The navigator that survives a long list; you-are-here; focus | `5o.` · `5p.` · `5q.` · `5r.` |

### And before that

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

**Owed and now discharged:** the two "spheres" rows in the `CLAUDE.md` budget table were
retaken 2026-08-28 — 60 median, nothing dropped, on a 2652×1537 canvas framed with snap to
fit, shading confirmed by eye first. Both the canvas size and the framing are recorded this
time, because their absence is what made the original pair impossible to reproduce.

**Also done 2026-08-28 (`HANDOFF.md` 5g):** the side panes fold to a labelled rail, and
the inspector rails itself while nothing is selected. Found doing it: `panels` had been a
persisted, reset-by-name setting that **nothing read** since the chunk-2 merge. Design rule
24, and design rule 16 extended.

**Also done 2026-08-28 (`HANDOFF.md` 5f):** three independent spread axes (X and Y widen a
plate, Z is the gap between plates; all three together is what zoom already is), and
hide/collapse as separate switches so a selection of eight plates out of fifty-two stops
reading as eight plates down a tower of empty slots. Design rules 22 and 23. **Still owed
from that conversation: per-plate sphere scaling, and stack orientation** — laying the column
on its side, which is structural because `OrbitView` has no camera roll.

**Also done 2026-08-28 (`HANDOFF.md` 5e):** three layout and navigator defects found while
clearing that debt. A `rem` inside `@media` resolves against the browser's font size, not
the page's, so five breakpoints silently meant the wrong width; the narrow layout's
`display: none` lost to a later equal-specificity rule and never hid anything; and all four
navigator routes that set a subject carried no subject, so forty rows did the same nothing.
Rules 28, 29 and 30.

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
| The legend is a **pane with its own track**, never an overlay; open by default | design rule 25 |
| The **navigator is the routine list** — not a split centre pane, not a fourth mode | design rule 26 |
| Selecting never moves the camera; off-screen is *stated* with one click to frame it | design rule 26 |
| Clicking an already-selected node still clears it — undo makes it recoverable | rule 33 |
| The pop-up is a **hover card**; the clickable depth stays in the inspector | `HANDOFF.md` 5l |
| A thread carries a **subject**, never a label; the click routes from a table | rule 30; design rule 16 |
| Threads sort **rarest first** — three routines is a detour, three hundred is a category | `threads.py` |
| Following a neighbour: **both** replace and walk, a Setting, usage retires the loser | design rule 2 |
| The naming and glossary lanes are computed **at start**, not lazily; their bodies are fetched when their page opens, their sizes ride with the cover | `CLAUDE.md` budget; `HANDOFF.md` 5n |
| A citation is opened from `/api/source`, never pinned into the page | `HANDOFF.md` 5n |
| Plates a selection touches are drawn faintly and named, though plates stay off | design rule 26 |
| **Plate**, never disk or plane, in every word a reader sees | `HANDOFF.md` 5p; a guard |
| The you-are-here arrow is a billboard at the plate's rim, aimed by a screen angle | `HANDOFF.md` 5p; rule 22 |
| The way back restores the view the selection was *found* in, not a computed fit | `HANDOFF.md` 5p |
| Clicking the arrow selects that node alone and frames it — it **sets**, never toggles | rule 47; rule 33 |
| Focus separates *what may answer* from *what is drawn*; the fog stays on screen | rule 47; design rule 19 |
| The navigator is a fixed header over a scrolling body; group headings are sticky | rule 45's session; `HANDOFF.md` 5o |
| The routine list is grouped by package, and the package is the **plates'** package | `queries.py` `NAV_ROUTINES`; rule 30 |
| How many routines a package lists is the reader's, `All` included | `HANDOFF.md` 5o |
| A search opens what it matched only while the answer is small, and says when it did not | rule 45 |
| The centre pane's **mode is not part of where you were** — Back restores the subject and leaves you in the mode you are reading in | `HANDOFF.md` 5t; `CENTRE_MODES` |
| The pop-up stays `pointer-events: none`; drilling in is a **key**, never a click on the card | rule 48; `HANDOFF.md` 5l |
| The detail window holds **open or not**, never *which* — it reads the one selection | rule 51 |
| Two windows are **peers over a `BroadcastChannel`**, never opener and child | `HANDOFF.md` 5t |
| A detached view is the **same application** under `?view=detail`, never a second page | `HANDOFF.md` 5t |
| One renderer for a signature, `schema.signature_parts`, for the documents and the card alike | rule 13; `HANDOFF.md` 5t |
| A clickable name in source is `calls.callee_id`, **never** a name match; no column means no inline span | rule 1; rule 5; `code.py` |
| **No syntax colour** in the code browser — kind is the dimension colour is spent on | design rule 4; `HANDOFF.md` 5u |
| The code browser runs in three places over **one** `CODEFILE`; a file is not a node and selects nothing | rule 51; rule 30 |
| `WORKING` is a **state**; a revision is identified by when it was captured | rule 20; `sourcedb.py` |
| A read defaults to the newest revision, never only to WORKING — sealing must not blind the dashboard | `sourcedb.py` `current_revision` |
| The navigator's width cap is what the window can spare; the Code group keeps its own width | rule 28; `HANDOFF.md` 5u |
| One box, two lanes: file names filtered here, source text asked of the server | `HANDOFF.md` 5v |
| Files first, then lines — a flat hit list is the haystack again | rule 45; `HANDOFF.md` 5v |
| One compiled pattern for the count and for the lines beneath it | rule 13; `search.py` |
| A regex turns whole word **off**; a bad pattern is named, never answered with no rows | rule 46; rule 20 |
| Where a hit sits is a line range, innermost span first — never a name match | rule 5; rule 10 |
| No index: FTS5 is token-based and cannot find `_emit` inside `self._emit` | `search.py` |
| The inflate cache is **bounded and says so** — 64 MB, keyed by content hash | `sourcedb.py` |
| A program dir holds `graph@<rev>.db` and `docs@<rev>.db` per revision, beside one `source.db` | `revisions.py`; `HANDOFF.md` 5w |
| The filename is a convenience; the identity is `meta.revision` **inside** the file | rule 30; `revisions.py` |
| A legacy bare `graph.db` is **read**, never rewritten into the new shape | rule 20; `revisions.py` |
| The layer work leads with a **change worklist**, and the picture follows the list | Tom, 2026-08-29; design rule 9 |
| No comparison key contains a **position** — one inserted import would move every fact | `make_id`; `changes.py` |
| A routine that arrived is not also counted as behaving differently | rule 40; `changes.py` |
| The search box is a **design-rule-2 pair**: sticky or scrolling, a Setting | Tom, 2026-08-29 |
| Stored paths are **relative to the tree that was read**; the root is used and never recorded | Tom, 2026-08-30; rule 60 |
| Legacy stores are migrated **in place**, never rebuilt — rebuilding orphans a snapshot whose tree is gone | Tom, 2026-08-30; rule 62 |
| A binding is **deferred** until something opens a file from disk; the control says `not bound` | Tom, 2026-08-30; design rule 16 |
| A call site has an **identity**, and it holds no position — an ordinal among identical expressions in one caller | Tom, 2026-08-31; `call_site_id`; `make_id` |
| An argument is recorded **as the caller wrote it**, never `ast.unparse`, never shortened | Tom, 2026-08-31; rule 8; rule 75 |
| The temporal pair is the **two society clones**; `mensores-overhaul` is a third tree | 2026-08-31; "How to verify" |
| An arrow is a **subject**, like a box and a node; the three are exclusive by construction | rule 74; rule 76 |
| An argument binds to a parameter **only where the source settles it**, and says why not | Tom, 2026-08-31; rule 1 |
| Call sites are listed, never grouped and never bounded — the aggregate is on the arrow | rule 32; rule 8 |
| The engine's **echo** of a selection it was handed is not a new act by the reader | rule 76 |
| A rewritten comment is a **fifth band**, never a sixth fact kind — `behaves` promises what a routine *does* | Tom, 2026-09-01; rule 32 |
| `explained_only` holds only what would be in **no** band; a routine already in one gets a tag | rule 32 |
| Comments are compared **joined in line order and collapsed**, never as written | rule 1; measured |
| The comment scan is bounded by **files whose bytes differ** — equal hash, equal comments | `filediff`'s argument |
| The headline count takes `explained_only` and still leaves `edited_only` out | this tool's subject |
| *Behaves differently* is **in the difference channel**, on every surface that draws it | Tom, 2026-09-01; rule 51; rule 69 |
| `edited` stays **out** of that channel — the channel holds three directions and a ground | rule 69 |
| A presence group's unfold is keyed on the **band**, never on the sign that swaps with the assumption | rule 65; rule 30 |
| A presence line names six and puts the **whole** set one click away, never the remainder | rule 8; design rule 1 |

## How to verify — all three, before saying anything is done

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

Then against real code, because unit tests on a toy program cannot catch a resolution
defect that only appears at scale:

```bash
uv run dunneflow analyze ../society-2026-08-29/src --name mensores
uv run dunneflow serve output/mensores
```

**The pair is the two society clones, not `../mensores-overhaul`.** That is a third copy
of 626 files and is neither end of the comparison; this file and `CLAUDE.md` both named it
here and it cost a wasted analysis. All three trees are read-only; all output belongs in
`output/`. Rebuilding the pair after a schema bump is in `CLAUDE.md` — two analyses and a
seal, in that order, because a sealed snapshot is never re-analysed in place.

**Do not re-analyse into `output/mensores` while verifying two versions.** It holds the two
revisions everything temporal is checked against — `2026-08-31T22:53:57Z` (WORKING, 628
files, from `../society-2026-08-29`) and `2026-08-31T22:53:15Z` (FOR_COMPARISON, *Society at
e2e658b4 — 2026-08-26*, 625 files, from `../society-2026-08-26`) — and a third would change the setup the recorded figures belong to. It is enough on
its own to verify a base switch, both directions, with no scratch corpus.

Ground truth is in `CLAUDE.md` — both halves. Positive: the four executables must all
appear in "Where to start" with plausible reach, **and they must still be there after a base
switch**, which is the cheapest check that a switch rebuilt everything rather than most
things. On the older revision that is 175 ways in and 3,950 boundary touches, with
`mensores` / `mensores-mcp` / `mensores-scriba` / `mensores-signator` at 1,366 / 421 / 265 /
111. Negative, and it matters more:
`.groma/research/v0.2/conventions-naming-and-documentation.md` is a paper *about* naming
standards and must yield **zero** naming rules.

### The traps that cost this session

- **The automation tab gets no animation frames.** `ResizeObserver` never fires and `rAF`
  never ticks in it, so anything needing a rendered frame cannot be observed there — a
  confident, reproducible and entirely false finding came out of measuring through one.
  Static DOM facts (grid tracks, widths, classes) survive; everything else must be driven
  by a human in a real window. Rule 38.
- **`grep` can silently answer "no matches" about a file it has decided is binary.**
  `shell.js` is 412 KB of UTF-8 and `file` calls it text, but `grep` without `-a` returned
  *nothing* for `srcPath`, `getElementById` and `source_root` — all three of which are in
  it. Acting on that false negative, a live control reading a field the server no longer
  sent was declared safe; it rendered an empty box on every load (rule 44). **Use `grep -a`
  on the client sources**, and treat "no matches" in a large file as a claim to check
  rather than an answer. Rule 43 in the instrument, and the cheapest one yet to avoid.
- **A `/* */` block whose continuation lines are plain indented prose is invisible to
  `_code()`.** It blanks comment *lines* — those starting `/*`, `*` or `//` — and this
  codebase uses both that style and bare indented continuation. A new guard tripped on the
  paragraph explaining the defect it was written from, which is the fourth time in this
  file. Write client comments in the `*`-prefixed style. CSS has its own `_css_code()`:
  with no template literals and no nested comments, the whole-block strip that is unsafe
  in JavaScript is exact there.
- **The browser writes to your controls.** Chrome restores a `<select>`'s value across a
  reload, outranking the `selected` attribute the code wrote — so a control can name a state
  the page is not in while every source-reading check passes. Rule 67: assign the value from
  state. More generally, `elementFromPoint` answers *can the reader reach it*; nothing in a
  test answers *what has the browser since done to it*, and only driving does.
- **A guard that checks a name appears has not checked anything happens.** Three guards
  written this session passed against their own defect first time. Run every new one against
  the defect it came from *and* against a half-working version. Rule 37.
- **A rule about drawing is usually also a rule about reading.** Rule 23 said a shadow is
  never an endpoint; the code that *drew* edges obeyed it and the code that *read* them did
  not, which silently deleted every cross-plate caller from the selection. Rule 31.
- **A guard that names the right case may still not catch it.** `selectionOnScreen()`
  documented itself as returning null when there is no viewport and guarded with `?.` —
  while deck.gl asserts *inside* `getViewports()`. The `?.` was what made it look guarded.
  Rule 42.
- **A check that cries wolf has already failed.** The runtime self-check reported four dead
  controls on every page load for two sessions and was wrong about all four. Rule 43.

- **A scripted click proves the handler, not the path to it.** `element.click()` fires the
  listener whatever is painted on top. A whole session's driving verified every control on
  the detail window and could not see that its scrim was over it. Use `elementFromPoint`.
  Rule 48.
- **A class the generator emits around every item cannot name one item.** `buildNav()` wraps
  every group body in `.nav-items`, so `querySelector(".nav-items")` inside a group returns
  the **wrapper** — and the file filter had been replacing the box it was typed into on every
  keystroke since it was written, with a guard for exactly that passing throughout. Rule 54.
- **A component with two shapes needs two sets of rules, and must say which it is in.** One
  flex chain served both and squashed the list state to 118px while 1,900px overflowed it and
  painted over the panels below. Every row present, sized, correct and unclickable.
- **Your mutation harness is a check too.** Both of this session's reported every mutation as
  surviving, because they read pytest's output rather than its exit code. Rule 43.
- **Three times now: a control correctly wired to a stylesheet that could not carry it.**
  `[hidden]` beaten by a later `display`, a `th` width ignored under `table-layout: auto`,
  a sticky header bound to a box that never scrolls. Markup and handlers both check out.
- **A blindness check keyed to the design erodes; key it to the instrument.** A guard
  asserted four distinct `rtnchg-` class names existed "or this guard is blind". Moving one
  of them into the difference channel left three, and the obvious fix -- lower the floor to
  3 -- is how such a check reaches zero over a few sessions without anyone deciding to
  weaken it. It counts what the regex *found* now (one `cls:` literal per state), which is a
  fact about the instrument rather than about the design it is pointed at.
- **A guard that passes first time has not been tested.** Twelve did this session. Every one
  was a containment check over too wide a span, or against a name where the claim was about
  a behaviour. Run every new guard against its own defect *and* a half-working version.
- **A comment explaining a defect will trip the check for it.** Three did; `_code()` strips
  comment lines. Its first version stripped string bodies too — which in this codebase is
  where the checked code lives — so every check passed against an empty string.
- **A promise can be printed rather than wired.** Three keyboard badges — `S`, `G`, `T` —
  named keys nothing listened for, and two of them sat on buttons with *no attributes at
  all*. The runtime self-check enumerates `data-*`, so a control carrying none is one it
  cannot see. Design rule 16 one level further out than any check here was looking.
- **A search for a class name cannot see a class that is computed.** The fact lane spelled
  the third difference `tone-mod` -- a fourth spelling of one idea, with a rule of its own
  painting it grey a class name away from the `.tone-moved` everything else used. No search
  for `tone-moved` could find it, because the renderer writes `tone-${tone}` itself and what
  travels from the caller is a bare `"mod"`. The guard that checks the tone *vocabulary*
  passed throughout; only a guard naming the surface caught it, and it was the one mutation
  to survive a first pass.
- **An equal-specificity class rule loses to a later one, and a colour is the quietest place
  for that.** `.hc-chg` sets a colour on the very element a `.tone-*` class lands on, so the
  two tie and source order decides -- the hover card would have said *behaves differently*
  in grey while the row that opened it said it in violet, with the markup, the class and the
  handler all correct. Found by working the specificity out by hand, not by anything that
  ran. Rule 29, which was filed under media queries and is not about media queries.
- **A guard that reads past its subject vouches for the wrong thing.** `_fn` stopped at
  `\nfunction` and swallowed the `async function` after it; a badge check took "everything
  after the keydown listener" as the handler. Both passed against their own defects.

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
- **CSS has four defaults that look like absence and are not.** A `rem` inside `@media`
  silently means the *browser's* font size, not the page's. A media query adds no
  specificity, so its `display: none` loses to any equal selector declared later. A grid
  item is `min-height: auto`, so it refuses to shrink and hands its overflow to the
  document — the first three were live in one stylesheet at once and produced one symptom.
  And a **sticky child sticks to its scroller's padding box**, so a strip of padding there
  is a gap the content scrolls through *above* the header meant to be covering it.
- **`outerWidth`/`outerHeight` are device pixels; `inner*` are CSS pixels.** Mixing them
  made 88px of ordinary browser chrome read as 677px and sent a diagnosis chasing a docked
  panel that did not exist.
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
