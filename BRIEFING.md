# DunneFlow — briefing

**Read this first, then stop.** It is an index, not a fourth copy of the documentation.
It exists so a fresh context can be useful in a few minutes instead of an hour.

| Read | For |
|---|---|
| `CLAUDE.md` | The rules. 75 engineering rules and 26 dashboard design rules, each earned from a false result on real code. **Binding.** |
| `HANDOFF.md` | The chronological record — what was built when, what it cost, what broke. ~1,700 lines. Read *sections*, not the whole thing. |
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
| `migrate.py` | Stored paths absolute → relative, in place. The prior state it can speak for, named (rules 60–62). |
| `extractors/python/` | stdlib `ast` + `tokenize` only. No third-party parser. |
| `extractors/docs/` | Markdown / rST / text, scanned by hand. No markdown library. |
| `detectors/*.yaml` | **The extension point.** Teach a framework here, not in code. |
| `canonical/` | Whether two writings are the same expression, per language. **Beside** the extractors, never inside one — see the cache-key note in `CLAUDE.md`. |
| `resolve/` | Call graph, CLI trees, flows, naming, glossary, traceability, mirror. |
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
| `cover.py` · `detail.py` · `documents.py` | the cover · the inspector and the hover card · document mode |
| `threads.py` | adjacency by *interest* — why a neighbour is worth a detour |
| `vocabulary.py` | the naming and glossary lanes, served and matched against one name |
| `graph.py` · `layout.py` | the 2.5D model at two levels of detail, and where things sit |
| `packages.py` | the package overview — the other graph layout |
| `code.py` | the code browser — a file, its clickable names and what each line *is* |
| `search.py` | searching the **text** — files first, then one file's lines with their margin |
| `static/shell.js` | **the application**: state, routing, every view, the self-check |
| `static/graph.js` | **the engine**: payload to pixels, and nothing about this page |
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
document, glossary, naming, settings) with the 2.5D stack and the package overview as two
layouts inside graph mode and **two levels of detail inside the stack**, one inspector
reading `/api/node`, and the graph following the theme. The reading loop: the navigator is the routine list grouped by package, hovering a
node gives a card, picking one lights its hop and fills the inspector, threads lead sideways,
and ⌘Z takes any of it back. **Finding and keeping your place**: an arrow at the plate's rim
aimed at what you picked and clickable to go there, a reticule on it, a *focus* lock so only
the lit set answers a hover or a click, and *you are here* to restore the view you found it
in.

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
document mode's narrative view · `CURIOSITIES` on screen · packaging as a binary · any
language but Python.

**The revision spine is in, and both ends of a pair are readable.** `WORKING` is a *state*
rather than an id, and a revision is identified by when it was captured; `seal()` keeps the
current snapshot under its own name so the next `analyze` opens a second one beside it rather
than replacing it. `dunneflow revisions <dir>` lists them and `--seal` keeps one.

**A comparison is two directories**: the **base** is what the whole map shows and the
**compared** is what it is held against, neither claimed to be older — *added* / *deleted* is
an interpretation the reader owns, derived from the two versions where they say enough. Both
ends are settable from the toolbar; changing the base makes the server rebuild everything
from that graph (1.2–3.0 s warm, 35 s cold), and `serve --revision` chooses it at boot.

**Built but not on screen:** `CURIOSITIES`. `threads.py` computes the outlier family per
package already — most commented, most called, deepest closure, most lopsided table — and
running that program-wide is most of design rule 15's doorway panel. It says honestly that it
is not computed yet.

## What we are doing now

**Paused 2026-09-01. Chunk 5 is complete, the change worklist sees an argument, and two
things filed as known are closed.** 747 tests, mypy clean, ruff clean, working tree clean.
Nothing is half-done.

### The latest: a presence line says what it left out (2026-09-01)

Two small things Tom took together, and they shared a shape: each was a surface saying less
than the map already knew.

**`Constants +23` printed six names and stopped.** The count was right, so nothing looked
wrong — a reader simply had no way to know six was not twenty-three, and there was no full
listing anywhere in the product. The server had been sending every name whole the whole
time; the defect was `names.slice(0, 6)` in the renderer. Open, the group names the **whole**
set rather than the remainder, and the way back is drawn whichever way it is open, because
"showing six of 23" and "showing all 23" are both answers.

**The unfold is keyed on the band, never on the sign.** `+` and `−` swap when the reader
changes which version they take to be newer and the names do not move, so an unfold filed
against "the plus group" comes back attached to a different set — rule 65 in a control.
Driven both ways: `+23` green with 23 open becomes `−23` red with the same 23 still open.

**Driving it found what no test could.** Twenty-three names separated by a single space,
several 76 characters long and wrapping mid-name, is a wall of monospace. *The bound had
been hiding a legibility problem as much as it had been hiding names* — at six it reads as
a list. Each name is a chip now, inline rather than `inline-block`, because a chip that
cannot break is a 76-character box that overflows a narrow pane.

**And *behaves differently* stopped having two colours.** It drew in `--text-muted` on the
routine lane while the stack, the graph legend and the findings' mark drew the same idea in
`--diff-moved`. Tom's call. Eight surfaces; the stylesheet comment is rewritten as the
reversal it is rather than left standing beside code that contradicts it. `edited` stays
out, and that is the channel being **full** rather than an oversight (rule 69).

Two near-misses out of it, both rule 71's family. The fact lane spelled it `tone-mod` — a
fourth spelling of the third direction, with a rule of its own painting it grey one class
name away from the `.tone-moved` everything else used, and the one surface no search for
`tone-moved` could find because the renderer spells the class itself. And `.hc-chg` sets a
colour on the very element the tone lands on, so it **ties** with the unscoped rule and wins
on source order — the hover card would have said it in grey while the row that opened it
said it in violet. Caught by working the specificity out by hand, then proved in the browser
by deleting the rule live.

```
21/21 mutations caught over a baseline proved green first
one existing guard's blindness check rewritten rather than lowered — it counts what the
regex found, not how many classes the design happens to have
```

**Absent rather than estimated:** a picture of the four figures side by side. The automation
tab's screenshot viewport captures roughly the left half of a 1258 px page, so the violet
figure is off the frame. Everything static was driven — classes, computed colours on all six
surfaces, the unfold both ways with `elementFromPoint`, and the assumption flip carrying the
open set with it. Rule 38.

### Before that: what a call passes, and what a constant is (2026-09-01)

`FACTS` compared `calls` without their arguments and `constants` by name alone, so
`f(db_path=None)` becoming `f(policy_path=…)` and `EXPECTED_SCHEMA_VERSION` going 27 → 28
both read as **no change at all**.

```
arguments   53 callers differ as written · 13 genuine after canonicalising · 2 new to the band
constants    7 values moved, of 2,615 in both versions
/api/changes 266 ms -> 480 ms warm, against a < 500 ms budget — 20 ms of headroom
```

All thirteen were checked against real source. **The fourteenth was noise and is the reason
there is a canonical pass**: a `typer.echo` message re-wrapped across two lines with its
content unchanged, which lands in *behaves differently* — the band that promises what a
routine **does** moved. Arguments are stored as written on purpose (rules 8 and 75), so the
comparison has to ask a different question of the same string.

**Constants are deliberately not canonicalised**, and the asymmetry is the finding:
`_literal` already unparses them on the way in, so a pass there was written, measured at
384 ms, found unable to change any answer, and removed. Two columns, two answers, and the
difference is how each is filled.

**`canonical/` sits beside `extractors/`, not inside it.** Put in `extractors/python/` it
made both graphs read as stale — that folder is globbed into the cache key — so every edit
to a canonicaliser would have discarded every graph on the machine, sealed snapshots
included, for a module extraction never reads. Moved on Tom's call; the fingerprint returned
to its stored value and no re-analysis was needed. `LANG_SUFFIX` came with it from `walk.py`,
where it had been declared and read by nothing at all.

`site_id` is deliberately **out** of the argument key: it carries an ordinal among identical
expressions, so inserting a third `emit()` would renumber every site after it. 18/18
mutations caught over a proved-green baseline; four survived first passes, three were the
guard and one was the mutation.

**Left out on Tom's scoping call: comments.** A rewritten explanation above unchanged code is
still invisible, and 18,208 comments are the governance layer and the only source of WHY. It
wants its own thought — a reflowed comment is the re-wrap problem again, larger, and prose
has no `ast.unparse` to appeal to.

**Pre-existing, now easier to notice:** a presence line named at most six of its members
with no full listing anywhere (`Constants +23` showed six), which is rule 8's bound without
rule 8's companion. *Closed 2026-09-01 — see the top of this file.*

### Before that: chunk 5c, the overlay on the findings (2026-09-01)

**5c put the anomaly comparison on screen, and it opened by reproducing a defect rather
than by building anything.** `state.triage` was keyed by the finding's **array index**
while both of its declarations said `finding id ->`. Reproduced over Mensores' pair and
then in the browser, end to end:

```
index 104   base 22:53:57  `siq__rebuild_87_02h` is written but never read back
            base 22:53:15  `tags` is written but never read back
```

File a decision against the first, switch the base, and storage restores `{"104": "ack"}`
— now an acknowledgement of a different table, with the finding actually acknowledged not
even in that version. Nothing on screen, nothing in the console. `loadAnomalies()` was
dropping `ident`, `ident_parts` and `subject` on the way in, all three sent since 5a; the
last of those had been `undefined` in a live sentence for as long as the sentence existed
(rule 44).

`triageOf` / `setTriage` are now the **only** two places `state.triage` is subscripted, and
the guard is an absence over the whole file rather than a check on the sites that existed.

**`SETTINGS_VERSION` is 5, and it is the first bump that carries forward.** An index-keyed
blob read as ident-keyed is a wrong answer, not an absent one, so it may not merge — but
exactly one key of sixty-six is unreadable and the shelf, the plate colours and the panel
layout are as good as they were. `CARRY_FORWARD` is keyed by the version being *left*, the
way `migrate.py` gates re-stamping a fingerprint (rule 62); the old blob is **left in
place**, because deleting it is a read path destroying what it read (rule 20); and the load
says what it dropped, once, on the surface that lost it.

```
5c  /api/anomalychanges on screen   default on, fetched when the worklist is opened
    base 22:53:57  1 / 0 / 4        base 22:53:15  0 / 1 / 4, and the word inverts with it
    0 ms held · five states that must not look alike, and do not
    20/20 mutations caught over a baseline proved green first
```

Findings only the compared version has are **counted in the head with the set one unfold
away**, never given rows and never triageable — Tom's call, and it keeps the list, `j`/`k`
and "left to triage" all counting one thing (rule 32). The `moved` mark spends
`--diff-moved`, which already existed: violet in all three sets and both themes, measured
for separation (rule 69), and already the graph legend's `tone-moved`. *Still here,
claiming something different* is a direction of difference, not an absence of one.

**Two things driving it found that no test could have.** The note counted all 106 findings
while everything beside it was per severity, so the Suspect tab read `◈ 4 claiming
something different` with not one marked row on it — all five banded findings are INFO
(rule 32, and the same shape that retired `degree`). And the carried-forward note rendered
one fact twice side by side, because both the store and the view wrote a reason for it
(rule 40, in prose). Fifth consecutive session in which looking at the pane paid for
itself.

**Absent rather than estimated: a picture of it.** The automation tab's viewport is fixed
at 1262×556 whatever the window is, and this app puts ~320px of chrome above the list, so
the marked rows do not fit a frame. Everything static was driven there — classes, computed
colours, the titles with both numbers in them, per-tab counts, the switch both ways, and
`elementFromPoint` on the unfold and the switch to prove they are reachable rather than
merely wired. Rule 38: the picture wants a real window.

### Two things waiting on Tom's eye, and neither is a bug

1. **The flow panel's arrow stroke is 1 px**, which is thin to aim at. The same flow is
   reachable from a row in the pane, which is a button, so this may be enough.
2. **A 1,347-line `frozenset` argument exists in this corpus** (`quaestor/_envelope.py`,
   91 KB in one argument) and the pane **wraps** it rather than eliding, because rule 8
   allows abbreviation only where the complete value sits beside it. It may read badly.
   Whatever replaces it has to keep the whole value reachable.

*There was a third — the routine lane drawing* behaves differently *in `--text-muted` while
the legend and the findings drew the same idea in `--diff-moved`. Put to Tom on 2026-09-01
and unified on `--diff-moved`; see the top of this file.*

### What is next, and it is open

Nothing in chunk 5 is outstanding, the argument gap is closed, and the two small things
filed as known are done. Still open and unblocked, and these are now the whole list:

1. **The change worklist does not see a rewritten comment.** `changes.FACTS` does not
   compare them at all, so a rewritten explanation above unchanged code is invisible — and
   18,208 comments are the governance layer and the only source of WHY. Left out on Tom's
   scoping call and wanting its own thought: a reflowed comment is the re-wrap problem
   again, larger, and prose has no `ast.unparse` to appeal to.
2. **`CURIOSITIES` has never been put on screen.** `threads.py` computes the outlier family
   per package already — most commented, most called, deepest closure, most lopsided table
   — and running that program-wide is most of design rule 15's doorway panel. It says
   honestly that it is not computed yet.

### Before that: a finding says what makes it that finding (2026-08-31)

**The question that blocked the anomaly worklist since 2026-08-30 was answered**, and it
was measurable rather than a matter of taste. *What makes two findings in two versions the
same finding:* over Mensores' pair, `kind + subject` is a total key with zero collisions —
106 of 106 paired, one genuinely new — while adding `file` *loses* three pairings, because
for a grouped detector it is `MIN(file)`, a tiebreak that moves when an unrelated file
changes. The old sub-question dissolved: `LOST_EDGE` is already one finding per expression,
and the callers and the rivals are what it *reports*.

**Tom took an explicit identity per detector**, and his reason set the shape: *"to later on
permit different languages such as Kotlin or C++ … keep the input possibilities wide
enough."* Detectors are query-driven, so another language's facts already run through them
and will bring detectors of their own; a central rule inferring identity would have to go
on being right about every one.

```
5a  ident_parts has no default, so a detector that cannot answer cannot construct a finding
    all 17 sites declare theirs · Mensores 106/106 and 107/107 distinct · zero ordinals used
5b  /api/anomalychanges   only_in_base · only_in_compared · moved   (rule 65, never a time)
    inverts exactly when the ends swap: 1/0/4 one way, 0/1/4 the other
    62 ms → 0.9 ms on /api/anomalies · 1.3–4.1 s cold for the pair · 0 ms once both held
```

Compared is what a finding **claims** — count, severity, confidence — never its title or
detail, which are renderings of exactly those (rule 40), and never its blind spot, which
describes DunneFlow rather than the program. Findings are held per **graph**, not per pair,
so a base switch does not throw away the expensive half; `COMPARISON_CACHES` names what a
switch *does* clear and a guard asserts what must survive it. A graph this DunneFlow
refuses to read is stated with its reason and `dunneflow migrate`, sends no bands, and does
not stop the base's own findings answering — driven end to end, not trusted to a guard.

Guards mutation-tested 10/10 and 11/11 over baselines proved green first. Four survived
first passes and every one was the guard, including the sharpest of the session: **the
ordinal that breaks a genuine tie was hiding weak keys from the uniqueness test**, so the
corpus guard now asserts no declared key needs tie-breaking at all.

See `HANDOFF.md`, "The overlay on the findings, and the key it had to be built on" and
"A finding says what makes it that finding".

### Before that: an edge says what flows (2026-08-31)

**Chunk 4 landed 2026-08-31: an edge says what flows.** The last thing Diagram mode was
missing, and the one Tom asked for in the same breath as the arguments.

```
/api/flow?from=&to=[&inside=]   1-2 ms warm    119 arrows ride with the drawing, 0 hover requests
17 arrows drawn · 17 with an id · 17 reachable by elementFromPoint · 14 call sites rendered
10,668 of 11,570 arguments on a resolved call bind -- 92.2%, and every refusal says why
```

A lane is `pair -> Counter[kind]` rather than `pair -> weight`, so a TOUCH and a CALL are
told apart and the weight *is* the sum by construction; `dot()` writes `id=` on every edge;
the panel lists **call sites, never grouped** (the aggregate is the number already on the
arrow) and never bounded.

**The binding line is on the screen, not only in the source.** A keyword binds by name
always, a position only when the callee is resolved, takes no `*args`, and the receiver
question is answered — `self.f(x)` skips one, `obj.f(x)` cannot be told from `Cls.f(obj,x)`
and so binds nothing. The refusal costs 3.7%, measured before deciding it was not too
cautious.

**And it uncovered a defect that was not its own.** `Graph.setSelection` announces
*synchronously*, so `onGraphSelect` re-subjected to `sel.node` — one arbitrary member of
whatever had just been installed. **The fold has had this since the day it was built**, and
it was invisible because with the stack unmounted nothing echoes at all: the feature is
correct exactly as long as nobody opens the graph. Rule 76.

**Wanted from Tom's eye** (rule 38 — the automation tab's screenshot viewport is narrower
than the page's): the arrow stroke is 1 px, which is thin to aim at, though the same flow
is reachable from a row in the pane; and a 1,347-line `frozenset` argument exists in this
corpus and wraps rather than elides, because rule 8 allows abbreviation only beside the
full value.

*Its "next" was chunk 5, blocked on what makes two findings in two versions the same
finding. That question is answered and all of chunk 5 is built — see the top of this file.*
*(The argument gap that paragraph named is closed — 2026-09-01, see the top of this file.)*

### Before that: the call-site arguments (2026-08-31)

**Chunk 3 landed 2026-08-31: the call-site arguments, as written.** Tom's call over
approximating a call from the callee's declaration. `CallArg` is `{idx, expr, keyword,
splat}`, a call site has an identity, and `SCHEMA_VERSION` is 6.

```
43,926 arguments over 30,544 call sites    14,222 keywords · 49 splats · 0 blank ids
287 sites where (caller, expression, line) would have merged two calls into one
235 of 44,344 arguments a character slice would have got wrong -- col_offset is bytes
```

**Recorded as written and not re-rendered**: `ast.unparse` was one line away and returns
something equivalent rather than identical (`d["k"]` comes back `d['k']`), so a reader who
goes looking in the file for the string the panel showed them does not find it. The
expression is sliced out of the file's own text, on **byte** offsets — rule 75, measured
over the real tree, and the 235 it catches are all messages with a symbol in them.

**The corpus was rebuilt, both ends, and both reproduce their figures exactly** —
625/4,733/175/3,950 and 628/4,786/178/4,070, with zero naming rules from the research
paper. On the way it turned out this file and `CLAUDE.md` **both named the wrong tree** to
verify against; see "How to verify", which now names the pair.

Honestly absent at the time: the change worklist did not yet see an argument change
(`changes.FACTS` compared `calls` without them) — closed 2026-09-01 — and the boot figure is
withdrawn for this session rather
than reported — four runs of identical work spanning 16 s to 135 s at 3% CPU is not a
measurement (rule 24). Every request timing against the running server is inside budget.

**Next: chunk 4 — an edge says what flows.** `dot()` writes `id=` on every edge, the
compartment keeps the edge *kind* beside the weight (dropped today, so a TOUCH and a CALL
are indistinguishable), and `/api/flow?from=&to=` answers on demand: every call site with
its arguments and the callee's declared parameters, or the SQL and network operations for
an edge into a boundary. A third specimen shape in the same pane, every call site carrying
`data-gotocode` — Tom's *"ultimately where it all goes"*.

### Before that: Diagram mode reading both ways (2026-08-31)

**Paused 2026-08-31, with Diagram mode reading both ways and at two levels.** Tom drove the
approved mode and reported three things over two rounds; all three were defects, and the
last beat two rounds of verification because of *how* it was being verified.

**A box is a fold, and the inspector answers about the fold.** Clicking `KernelDecl` (61
methods) used to fill the pane with `KernelDecl._profile_name_or_none` — `selectFromNav`
electing `members[0]`. `/api/fold` answers in the same skeleton every other specimen uses,
so the pane that exists renders it: 61 members with their invocation lines, 8 neighbours,
what it touches, the span of the whole class. Rule 74.

**Two things it was hiding, and one it was not.** The pane rendered and *railed itself* (the
auto-rail read `state.selected`, which a fold leaves null) — Tom's "nothing is visible" from
the other end; the trail filed every box click as "nothing selected"; and, unrelated and live
since the day it was written, the inspector's **SQL rows never showed their table** and the
**network rows never their destination** (rule 44).

**The navigator now follows.** It marked `state.selected === r.id`, so a fold marked nothing
and moved nothing — design rule 26's back half, dead. It marks every member (61 rows), opens
the package and scrolls to the first.

**A second click on the same box opens it** into its own routines — `build_inside` returns a
`Compartment`, the same type the first level uses, so both are drawn by one renderer.
`_authorization.py` opens to 18 routines, 3 boundary cylinders, 36 flows within, 0 unlinked,
in 15 ms.

**And the click that never arrived.** `dgmGestures` captured the pointer on every press, and
a captured pointer retargets `click`/`dblclick` to the capturing element — so every handler
in the view was handed the canvas instead of the box and returned having done nothing.
Nothing failed. **The automation could not reproduce it**: `setPointerCapture` throws for a
pointerId the injected pointer never made active, so the capture took for a real mouse and
never for the instrument. Reproduced in the end without a pointer at all, because a
retargeted click *is* a click whose target is the container. Rule 72. Its companion, rule 73:
the drawing moved **139 px** between the two clicks because the browser was fitting it, so
the second landed on a different box.

```
one compartment drawn        93–179 ms      opening a box    15 ms (18) · 170 ms (61)
KernelDecl                   61 routines · 0 flows within · 77 crossing to 8 boxes
_authorization.py            18 routines · 36 flows within · 0 unlinked
```

**Tom, after the last fix: _"Fixed! I love this, thank you!"_**

**Next, confirmed by Tom at the pause — _"Call site arguments and edges will be next."_**
From the approved plan (`~/.claude/plans/squishy-conjuring-kay.md`), chunks 3 and 4, in that
order: the panel in 2 wants what 1 records.

1. **The call-site arguments, as written** — Tom's call over approximating them from the
   callee's declaration. `CallSite` gains `args`, the Python extractor reads each argument's
   source segment whole (rule 8), `calls` gains a stable `site_id`, `SCHEMA_VERSION` bumps
   and Mensores re-analyses. The precision line is stated in the product: the expression as
   written, never an inferred type, and a parameter binding only where it is unambiguous.
2. **An edge says what flows along it** — `dot()` writes `id=` on every edge, the compartment
   keeps the edge *kind* alongside the weight (it is dropped today, so a TOUCH and a CALL are
   indistinguishable), and `/api/flow?from=&to=` answers on demand: every call site with its
   arguments and the callee's declared parameters, or the SQL and network operations for an
   edge into a boundary. A third specimen shape in the same pane, and every call site carries
   the `data-gotocode` button — Tom's *"ultimately where it all goes"*.
3. **The anomaly worklist overlay**, still blocked on one question — what makes two findings
   in two versions the same finding. 93 of Mensores' 106 are `LOST_EDGE`, so pairing them
   would invent an identity (rule 1). *(Answered 2026-08-31, and all of chunk 5 is built —
   5c landed 2026-09-01. This paragraph is what was true when the plan was approved; see
   "What we are doing now".)*

**Withdrawn and not to be rebuilt without reading why:** boxes drawn on the stack at
phyllotaxis positions (a sunflower is not a diagram), and shadows for cross-compartment edges
(the better model, the worse picture — measured, dropped on Tom's call).

See `HANDOFF.md`, "A box answers about itself, and the click that never arrived".

### Before that: the plate diagram, withdrawn (2026-08-31)

**Chunk 3's first attempt was built, driven by Tom, and WITHDRAWN.** Plate sizing (chunk 2)
stands; boxes-on-the-stack did not.

*"This is just nodes that are boxes, that's totally different. Mermaid diagrams have
completely different layouts than graph plates, they use a different layout algorithm."* He
is right. It drew labelled boxes **at the positions the plate layout already had** — and that
layout is `phyllotaxis`, a sunflower, whose own docstring says the ordering "is the only
structure this layout imposes". Nothing is ranked by what calls what, so every edge crosses
every other. **A diagram's readability comes from its layout algorithm, not from the outline
of its nodes**, and the chunk was spent on the outlines.

His bar was set before it was built — *"they must be easy to read or we have failed"* — with
the instruction to withdraw rather than ship with a caveat. Both controls are gone; a guard
asserts the absence of a door until `layout.py` has a layered layout. Everything else is
kept, because the shapes, the box text, the pixel sizing and the overflow rule are all
correct components of the right view.

**The rebuild, in his words:** *"create the Mermaid diagram first, then render it
orthogonally, and stack them up. Show how each connects to the others with edges between the
layers."* A **second layout beside `structural()`** — ranks by call direction, ordering within
a rank to reduce crossings, then coordinates — computed server-side and deterministically,
which `layout.py` already requires. Design rule 2's shape: the sunflower is right for ten
thousand dots and wrong for eighty boxes.

Two smaller failures to fix in the rebuild: the glyphs render **scrambled**
(`selected_backend` → `s/lec-uh-cc-e·u`; suspect `sizeUnits: 'common'` on a non-billboarded
`TextLayer`), and some lit nodes stayed dots beside boxes at a selection of eight where
everything should have fitted.

<details><summary>what the withdrawn chunk built</summary>

Labelled boxes for whatever is lit, in five silhouettes that carry kind.

Tom's decisions: **boxes for whatever is lit** (which already means the whole plate when you
pick a plate, and a routine plus its hop when you pick a routine); **shape carries kind, as a
set in Settings** — *By kind*, *All rectangles*, *All rounded*; and **box what fits, dot the
rest, state the number**, so zooming in turns more dots into boxes and nothing ever leaves
the picture.

```
pkg:mcp, 360 lit    496x361 → 21 boxes   1280x760 → 102 boxes   1920x1080 → 157
pkg:quaestor, 1,319 lit                  1280x760 →  86 boxes, 1,233 still dots, 2.3 ms
```

- **The billboard question is answered, and not where either of us expected.** Built flat, as
  Tom asked. The **tilt** costs nothing — a label loses 43% of its height at 35° and stays
  readable — and the **orbit** costs everything, because flat text inherits the in-plane
  rotation, so *top-down was worse than tilted*. A box now gives up its bearing and nothing
  else: turned about Z alone, still flat on its plate.
- **A boundary box says what it touches, not what kind it is** — the stadium outline already
  says *boundary*, so spending the one line on the word would drop the only thing shape
  cannot carry.
- **Rule 38 held**: zero animation frames even at 1600×1000, so the geometry was rasterised
  from the layers deck was handed. **A picture of what would be drawn, not a screenshot of
  the renderer** — and the harness was wrong twice before it was right (a perspective
  viewport where the product is orthographic, and mirrored text).
- Guards mutation-tested at **23/23**, after 20/23 with all three survivors the guard being
  weak.

**Looked at by Tom, and it found two defects.** The diagram switch was inside a HUD box he
had collapsed, so it measured 0×0 and Settings › Shape was a page that appeared to do nothing
— design rule 16 arriving through a *layout* rather than through the wiring. The switch is in
the Shape panel too now (one owner, `setDiagram`), and the collapsed strip names the mode.
And the **clipping is fixed**: rule 39 blamed the near plane for two sessions and it is the
**far** one, at `maxZoom` exactly — 4,063 of 15,869 nodes past the frustum with deck's default
of 500, zero with 5,000, at no cost to the scale or to `unproject`.

See `HANDOFF.md`, "Withdrawn — Tom, 2026-08-31, on the plate diagram".

</details>

**Also fixed 2026-08-31: the inspector could not be collapsed while it was empty.** Its fold
control lived in the header of a *populated* specimen, so "Nothing selected" — the state a
reader most wants to fold away — rendered without one. It is painted at the paint site now,
outside every `return` the content has. The first fix was wrong in a way `elementFromPoint`
does not catch: `float` on a flex item does nothing, so the button stretched to the pane's
full width while hit-testing said it was perfectly reachable.

**Next: nothing is scheduled.** Three chunks now rest on a picture nobody with a real window
has seen. The one open piece of work is the **anomaly worklist overlay**, still blocked on
one question — what makes two findings in two versions the same finding. *(Answered
2026-08-31; the overlay's server halves are built. See "What we are doing now".)*

### Before that: sizing a plate by what it holds (2026-08-31)

**A plate's width now says how much is on it.** The first of the two recorded feature
requests.

A fifth control joined the three spread axes in the HUD, and it is not an axis: `sqrt(n /
n_largest)` on **real nodes**, a *strength* between the uniform stack (0) and area
proportional to content (1), **per level**. Tom took all three recommendations: full on by
default, beside the spreads, one scale for code and externals alike.

```
routine   1.00x → 0.10x across 52 plates      module   1.00x → 0.25x across 16 plates
```

- **The anchor is arithmetic, not a decision.** Marks are drawn in pixels and fit frames
  what it is handed, so anchoring at the largest plate or the smallest is one picture at two
  zooms. Measured: the bounding cylinder is **999.8 x 3391.5 at both ends of the dial**, so
  design rule 20's framing never moves.
- **The dial comes home.** At 0 the worst node is 3e-5 world units from the payload's own
  coordinate on a 2000-unit stack — Float32 rounding, not compounding.
- **Called width and not density**, because `density` is already this product's word for the
  table's row height. The `disk`/`plate` collision arriving a second time, caught before it
  shipped.
- **`followMode` has never survived a reload** — declared, set by a live control that calls
  `persist()`, named in the reset dialog, and absent from `PERSISTED`. The guard written for
  exactly that failure ran one direction only. Fixed, and it runs both ways now.
- Guards mutation-tested at **24/24** over a proved-green baseline. **What it looks like is
  still not verified** — 0 fps, rule 38, the picture wants Tom's eye.

See `HANDOFF.md`, "Sizing a plate by what it holds — built 2026-08-31".

**Next: chunk 3, the plate as a diagram** — flat first, no billboards until there is a
problem to see, at the altitude that makes it a readable number of boxes. *"They must be
easy to read or we have failed."*

### Before that: the second altitude (2026-08-31)

**Density is answered by a level of detail as well as by plate width.**

*"A graph with this many nodes and edges is hard to comprehend."* That was Tom's one
complaint after driving the change colours, and the answer is a **level of detail** rather
than bigger nodes or fewer of them — his call, and this file's own reasoning: if a plate
cannot be read at a useful number of nodes, the number of nodes is what is wrong.

```
routines   10,015 nodes · 14,254 edges · 52 plates · largest plate 926
modules       578 nodes ·  1,505 edges · 38 plates · largest plate  85
```

`module` folds each file into one node and each boundary kind into one, on a single plate
below the code. **Another way to look at the same facts, never a filter**: the routine level
is untouched, nothing is dropped, and every folded node states what it stands for. The
*Detail* control sits in the legend beside "colour by", with the `<small>` threshold beside
it as a Setting (design rule 2) — both per level, because what a plate holds changes with
the altitude.

- **A selection travels, and it is stated.** Going up, a routine becomes the file holding
  it; going down, a file becomes the things inside it. Driven: 107 routines from one way in
  became *"the 44 nodes holding them"*.
- **A module takes the change band of what it holds, and `mixed` says so** — with `same` as
  the ground, measured before it was built. Counted the other way every changed file reads
  mixed and the tone says nothing; this way, **14 files carry the whole comparison** and 7
  are genuinely mixed.
- **The difference channel is full**, and that is the session's second find. No hue clears a
  useful bar in both themes against every colour in all three sets; a seventh meaning cannot
  be added by colour at all. Rule 69 says so now.
- **A pre-existing defect surfaced**: a small *external* plate has been merging onto
  `pkg:<small>` — a package plate — since the day `<small>` existed, so six of Mensores'
  externals were drawn among the code that reaches them, badged as ours.
- **Three defects found by driving**, and the first is the lesson: the switch threw on every
  attempt, silently in the page and loudly in the console, **which I did not read for half
  an hour**. Guards mutation-tested at 49/49 over a proved-green baseline; every survivor in
  the earlier runs was the guard being weak.

**What is not verified is what it looks like.** A browser-automation tab gets no animation
frames — the HUD reads 0 fps — so rule 38 applies: the counts, the controls, the
translation, the key and the colour buffer are checked; the picture wants a real window.

**Next: chunk 2, sizing a plate by its density**, on **nodes** (Tom's answer), a Setting,
with `layout.py`'s comment rewritten as the reversal it is. Two things changed about it: the
range is 10.5× rather than the 31× the note assumed (`MIN_DISK` floors the smallest plate at
9, not 1), and it is now a question about *two* pictures, so the Setting is per level or it
is wrong at one of them. **Then chunk 3, the plate as a diagram** — flat first, no
billboards until there is a problem to see (Tom's call), at the altitude that makes it a
readable number of boxes. His bar stands: *"they must be easy to read or we have failed."*

See `HANDOFF.md`, "The second altitude — built 2026-08-31".

## Before that: chunk C and the exploration work

**Paused 2026-08-30, after one history.** Chunk C is complete and has been looked at, and
the exploration work it uncovered is **done**: Back is one history with ⌘Z (`6i`), the
toggle-off that empties the picture is recoverable through a visible control, and density —
the third — is answered by the section above.

The two feature requests recorded in Tom's own words are still the next work and are
unchanged in substance: **size a plate by its density** and **draw a plate as a readable
diagram**, with his acceptance test for the second — *"they must be easy to read or we have
failed."* Both are re-shaped by the second altitude rather than superseded by it; see the
section above for how.

---

**All three overlays are on screen — the stack, the routines, and the code.** Chunk C is
complete. The stack came last and leads here; the routines and the code browser follow.

**The comparison over the stack — built 2026-08-30 (`colorBy: 'change'`).** A third value in
the "colour by" selector beside *what it is* and *which plate*. Colour **takes the channel
over** (Tom's call) rather than tinting the changed nodes and leaving the rest on plate hue,
because two meanings in one channel makes a red dot mean either *deleted* or *the plate whose
golden-angle hue landed on red*. **Crossings keep their plate gradient** (rule 23), and that
is free: `setOptions` repaints the nodes and never rebuilds the selection geometry.

```
10,015 drawn nodes:  53 +  ·  18 ○ behave differently
                     4,715 unchanged (15 of them edited without changing what they do)
                     5,229 not compared — the comparison speaks about routines
```

- **Three colours and a ground.** *Edited only* folds into unchanged on principle — internal
  computation is what this tool exists not to report — and the key states the fold.
- **"Not compared" is its own tone**, because more than half the stack is boundaries,
  constants, structures and artefacts that nothing claimed anything about.
- **A third difference colour clears rule 69 comfortably** (violet, ΔE 66–151). The finding
  is the opposite one: the *shipped* red/green pair is the weakest thing in the product at
  **ΔE 9.5**, so the guard's bar is derived — the new colour may never become the new floor.
- **Six defects found by driving**, including a palette that pinned a side to a colour (so
  flipping the assumption swapped the words and left the dots red) and a map that made every
  unchanged routine read as *not compared*. Guards mutation-tested at **23/23**, after two
  rounds in which every survivor was the guard being weak.
- **Looked at, and approved** — see `HANDOFF.md`, "Looked at, at the keyboard". Tom's
  verdict: *"the colors are a reasonable differentiating factor, and the edges do seem to
  make sense"*, and *"an absolute delight to work with so far"*. Three problems came out of
  it and they are **one line of work: the stack is legible enough to say what changed and
  not yet legible enough to explore.**

### Before that, in the same session: the routine marks (2026-08-30)

**The routines are marked too — built 2026-08-30 (chunk C, tables and the list).** The
second overlay, and it needed no server: `/api/changes` already carries every band with the
node id on every row, so table mode and the navigator's routine list say what the comparison
found about each routine — **arrived**, **went**, **behaves differently**, **edited and
behaving the same**, **unchanged** — from an answer the page already holds.

```
4,786 routines:  53 −  ·  18 ○ behave differently  ·  15 ≈ edited only  ·  4,700 unchanged
   …and from the other end of the pair, 53 stated and not listed: they have no row here
```

Three of Tom's decisions settled it. **Routines only** — the change worklist already *is*
the comparison, and the *anomaly* worklist is blocked on a question rather than on work
(what makes two findings in two versions the same finding; a finding has no id and 93 of
106 are `LOST_EDGE`). **Two switches**, because the code overlay fetches per file and these
marks are free. **The navigator never fetches** — its routine group is open by default, so
asking there would cost every session 13–28 s cold; it draws the marks when something else
has asked and says which of three states it is in.

- **A routine only the compared version has is counted and never marked** (rule 1). It has
  no row — both surfaces list the version on screen — so inventing one would name a routine
  among what this version contains. It is stated instead.
- **The counts are walked from the rows that are drawn**, never read off the band lengths
  (rule 32), so no number here names something no scrolling could find.
- **Four defects found by looking**, none by any check: a glyph that was also its own
  punctuation; a pane telling the reader to open the pane they were in (rule 68); one answer
  stated twice and differently in one view (rule 51); and — older than this chunk — a table
  left empty for ever by a routine list that had already arrived (rule 35's family). No new
  numbered rule: every one is an existing rule in a new costume.

Guards mutation-tested at **20/20** over a proved-green baseline, after a first run at 14/17
with **all three survivors the guard being weak** — the eleventh, twelfth and thirteenth time
in four sessions.

**Paused here 2026-08-30 with chunk C complete and looked at.**
See `HANDOFF.md` `6h`, `6g`, `6f`, and "Looked at, at the keyboard" for what driving it
found.

**Next, and it now outranks the worklist because Tom hit it at the keyboard: exploring the
stack.** Three problems, one line of work:

1. **← Back could not reverse a click in the stack — fixed 2026-08-30, `HANDOFF.md` `6i`:
   one history.** `state.trail` and `selHistory` are merged, with `state.trail` the history
   and `trailAt` the cursor. Back, ⌘Z and the HUD's undo are three doors onto one function;
   Back stopped destroying and the bar gained a **Forward**; dedup moved from the label to
   the subject (two routines called `<module>` are two steps); and **the cap split in two**
   — `TRAIL_CAP` (50) is the history, `trailCap` is how many the bar shows, and the bar
   states what falls off *both* edges. Guards mutation-tested at 20/20.
2. **A click to look is also a click that filters — half-answered by the above.** Rule 33
   kept `togglePick`'s toggle-off because *undo makes it recoverable*; that promise is now
   true through a visible control, and driven: clicking the node you are on empties the
   picture and **one Back restores it**. Whether the toggle should still exist is a separate
   question and **wants Tom's eye before anything else is done to it**.
3. **10,015 nodes is hard to comprehend**, which is what the two recorded feature requests
   exist to answer — sizing a plate by its density, and the readable plate diagram. **This
   is what is left of the three**, and it is the one Tom's *"easy to read or we have
   failed"* bar was set for.

**After that: the anomaly worklist overlay, blocked on a question** — what makes two
findings in two versions the same finding. A finding carries no id today and 93 of Mensores'
106 are `LOST_EDGE`, so pairing them would invent an identity (rule 1). Answer that first.

<details><summary>the colour-channel decision, now built</summary>

**Next: the graph as `colorBy: 'change'`, and it is unblocked.** The colour channel was decided at the keyboard: **change takes the
channel over** — a third value beside *what it is* and *which plate*, with plate hue stepping
aside while it is on, because tinting only the changed nodes would put two meanings in one
channel and a red dot would mean either *deleted* or *the plate whose hue landed on red*.
**Crossings keep their plate gradient** (rule 23): nodes and links are separate buffers, so
the dots can say what changed while the lines go on saying which plate each end is on. See
`HANDOFF.md`, "The colour channel, decided 2026-08-30", for the three things that follow
from it.

</details>

### Before that, in the same session: the comparison over the code (2026-08-30)

**The comparison over the code — built 2026-08-30 (chunk C, the code browser).** The first
of the overlays. Two lanes: the **text** lane marks the lines of the open file the compared
version does not have and draws the ones it has and this one does not where they belong, in
their own numbering; the **fact** lane beside it names the routines here that *behave*
differently, which is the half a text diff cannot state. The file list marks all 628 files.

```
628 files:  613 same · 12 with different text · 3 on one side only
                       …and pairing them reads no bodies at all
```

The sidecar is content-addressed, so an unchanged file holds the **same hash** at both
revisions and comparing two path maps *is* the file-level diff — 37 ms warm, 1 ms cached.
That is what makes `difflib` affordable: it runs only on a file the reader opened, and only
where the hashes already say it differs. The worst file in the corpus is 42 ms.

**Rule 70 is the find, and it was a prerequisite rather than a discovery.** The code browser
did not read the version the map was showing. One sidecar holds every revision and its own
default is the newest — right only while the newest is also the base, which stopped being
true the day the base became switchable. Serving Mensores' older graph returned `_queue.py`
at **674 lines with the 595-line version's marks over it**, and nothing raised. Six readers
had it; the base names the revision now and hands it to all of them.

- **Nothing is elided** (rule 8) — four hundred inserted lines is four hundred rows, and the
  overlay switches off, which is a different thing from a summary.
- **A routine only the other version has is listed, never marked**: its line number belongs
  to the other version (rule 1), and the page says so.
- **The tone comes from `diffWords()`**, so flipping which version is assumed newer swaps
  the colours with the words, for zero fetches.
- **Rule 71**: `.chg-mod` was already the worklist's module label, so every *modified* file
  row rendered fainter than the unchanged ones; and `dressNavItems` moved the chip in front
  of the file name. Both found by looking.

Guards mutation-tested at **17/17** over a proved-green baseline, after a first run at
11/13 — both survivors the guard being weak, one of them over the headline defect.

## Before that: colour sets in Settings (2026-08-30)

**Colour sets in Settings — built 2026-08-30.** Tom's call: colour decisions are personal
and belong in Settings, offered as broad sets rather than a picker per token, each with a
light and a dark variant, customisable within the a11y bounds.

A set covers the two channels where colour separates one *meaning* from another, and they
are the two that both spend red: **the difference channel** and **severity**. Three sets —
**Red and green** (what shipped), **Blue and orange**, **Muted**.

**Rule 69 is the find, and it is why the chunk grew.** Contrast says whether a colour can be
*read* and nothing about whether two can be told *apart* — and the shipped palette had been
failing that second bar since the day it was written. `--sev-broken` and `--sev-suspect` are
6.47:1 and 7.09:1 on white and, simulated for deuteranopia, **ΔE 5.3 apart**: the same
colour. Every check that existed passed, because they all asked the answerable question.

```
                      contrast (worst)   separation (worst)
  Red and green            5.34:1              ΔE  5     ← broken against suspect
  Blue and orange          4.86:1              ΔE 43
  Muted                    4.84:1              ΔE 10
```

- **The sets are CSS; JavaScript stamps `data-palette`.** `tokens.css` says no component
  declares a colour outside it, and the graph already depends on that. Overrides only, and
  the ladder is **specificity, never source order** (rule 29), counted by a guard.
- **`separation()`** implements Viénot, Brettel & Mollon 1999 and takes the **worst** of
  normal vision, deuteranopia and protanopia — never an average. Computed in the page from
  the tokens it is drawing, so no number beside a swatch is a claim nobody can check.
- **The difference channel is finally spent.** `--diff-gone` / `--diff-new` had sat in all
  three token blocks since the comparison vocabulary landed, with `diffWords()` carrying a
  `tone` per side and *nothing* drawing it. Without this the setting would have been a
  swatch that changed nothing.
- **The dead "Colour" demo is gone** — two pickers, a live ratio and a verdict, reading
  `state._fg` / `state._bg`, which were in no `DEFAULTS`, persisted nowhere and applied to
  nothing since the ratified prototype. A control wired to itself, invisible to both guards
  written for that family.

Two things the arithmetic settled: **red and green cannot be rescued by tuning** (every
chroma and lightness in that hue family measures 4–14, so `muted` is quieter and not safer,
and says so beside its own numbers), and **a lightness difference survives colour blindness
where a hue difference does not** — so forcing a pair to equal contrast throws away the one
axis that always works.

Guards mutation-tested at **13/13** over a proved-green baseline, after a first run at 8/13;
three of the five survivors were the *guard* being weak.

**Paused 2026-08-30.** See `HANDOFF.md` `6e`. Its "next" — the overlays, code browser
first — is the section above.

## Before that: switching the base (2026-08-30)

**Switching the base — built 2026-08-30.** The reading end is settable. `buildRevControls`'
trailing disabled row — `— reading a past revision arrives next —` — is gone, and removing
it was the work.

One payload set is live, always (Tom's call), so a switch is the **server** opening another
graph and rebuilding the payload, the file list, both vocabulary lanes and the cover from
it. Measured **1.2–3.0 s warm and 35 s cold** on the external volume.

- **`_Base`**, a frozen record holding everything one version decides — graph, store,
  payload, root, files, naming, glossary, cover — swapped in **one binding** under the lock.
  Built *outside* the lock and committed inside it, so the rebuild costs other requests
  nothing and a failure leaves the reader the map they had (rule 20 applied to a swap).
- **One door.** `_Live.open()` is the boot *and* the switch; a second builder would be two
  ways to produce one thing.
- **`POST /api/base`** with its own route table, because every other route here is a read
  and a GET that replaces the map is one a browser prefetch fires by itself. **`GET
  /api/base`** is the progress, behind its own lock, naming each of six steps as it runs.
- **`serve --revision <rev>`** — where "which version does this server open" honestly lives.
- **The overlay is blocking, over the whole application**, and says the version underneath
  is still the one on screen. On `done` the page **reloads**: every module-level array in
  `shell.js` is base-derived, and a hand-kept invalidation list is rule 36's defect.
- **The options are the pairs, and all of them are real**, grouped by reading end, each
  naming both ends because a closed `<select>` never shows its group's label.

**Six defects found by driving and one by reading the served JSON, none by any test.** Two
became rules. **67**: Chrome restores a `<select>`'s value across a reload and that outranks
the `selected` attribute the code wrote — so the control named the pair the reader had been
on *before* the switch while the strip named the new one. **68**: a group restored open at
boot never fired its `onOpen`, so Changes sat open saying *"open to compare them"* with
nothing to open — present since the group was built, reachable only by reloading, and a base
switch reloads.

**Guards** mutation-tested at 12/12 and 20/20 over proved-green baselines. Both first-run
survivors were the *guard* being weak rather than the mutation — the fourth and fifth time
in two sessions.

See `HANDOFF.md` `6d` and "Paused 2026-08-30, after switching the base".

## Before that: base and compared (2026-08-30)

**Base and compared — built 2026-08-30.** A comparison is **two directories**, and the tool
makes no claim about which is older. One is the **base** (what the whole map shows,
unchanged) and the other is the **compared**; it may be higher, lower, or identical, and
identical is reported as *no differences found* rather than as four empty bands.

That replaces the ordering question rather than answering it. The store only records when
*we* read the bytes, so `captured first` was an honest label on a claim the tool should not
have been making. `changes.py` now reports **`only_in_base` / `only_in_compared`** — named
for where a thing is, which is a fact — and *added* / *deleted* are an interpretation laid
over that by the reader's own assumption.

- **`comparedIsNewer`** is a Setting, default true, surfaced **on the strip** rather than
  buried in Settings. Flipping it costs **zero fetches** — the sets are already held.
- **A persistent strip** in its own `.app` grid row, on every screen, including a
  one-version program where it says *"on its own, nothing compared"*. It names both trees,
  each version with its provenance tier, the assumption in force, and — as a plain
  observation beside it, never a correction — what capture order we can actually see.
- **Version detection in tiers**: `pyproject.toml [project] version` → module-scope
  `__version__` (routing *around* the deliberate dunder filter, not removing it) → a guess
  off the directory leaf, marked `INFERRED` and rendered faint and italic.
- **`revisions.tree`** records the **package root's** leaf, and `README.md` now documents
  what a handed-over program directory contains about your machine.

**The default is read from the versions, not guessed** (Tom's call, taken on the evidence).
`comparedIsNewer` is `'auto' | 'yes' | 'no'`: `auto` compares the two versions where both
state one — even an inferred one, because that is still more obvious than no evidence — and
falls back to "the compared is newer" where they do not, saying so with a dashed border.
Three states rather than a boolean so `auto` re-derives on a change of pair. The comparison
is the **server's**: `version_kind` and `version_key` ride with each version, because
`1.10.0` sorts below `1.2.0` as a string and a date and a release number must never be
ranked against each other. A prerelease suffix and an equal pair both rank nothing (rule 1).

On the two Society trees this opens on **53 added** with no click; on `output/mensores`,
whose versions predate the column, it says *"no versions to compare"*.

See `HANDOFF.md`, "Paused 2026-08-30, after base and compared". Everything it named as next
— switching the base — is built; see above.

## Before that: paths stored relative (2026-08-30)

**Paths are stored relative — done 2026-08-30, and it moved the ground under the layer
work.** Tom's ask, and his three reasons: an absolute path leaks one machine's directory
layout, breaks when a tree is moved to free disk space, and breaks when a program
directory is copied to another machine. A survey found a fourth that mattered more here —
two revisions read from two different trees gave the same file **two unrelated keys**, so
nothing could pair a file with itself across two points in time.

```
Mensores' pair, joined as stored:  0 identical · 0 modified · 628 added · 625 removed
                    …and now:    613 identical · 12 modified · 3 added · 0 removed
```

One query, **zero body reads** — the sidecar is content-addressed, so a hash comparison
*is* the file-level diff. That is the code viewer's diff view most of the way built, and
it also says which twelve files are worth the expensive text lane.

**Two decisions of Tom's settle the shape.** Migrate **in place**, not by re-analysis: a
sealed snapshot exists to be readable after its source tree is gone, and rebuilding would
orphan exactly those. And **record nothing** — the original root does not ship, because
only the repo-named directory is stable and everything else is dated or version-suffixed
and therefore ephemeral, so compelling the reader to name one is expected. Nothing at read
time needs one anyway: bodies come from `source.db` by content hash, never by opening a
path.

- **The origin was one line**, and it had been announcing itself: `rel = str(path)`, with
  `module_name(path, root)` computing the genuine relative form on the next line. One
  choke point carried it into all eighteen graph tables.
- **A net deletion.** Nine identical `_rel()` clones plus `_short()` and `_resolve_path()`
  retired — and they were not the no-ops they looked like: `Path("a/b.py").resolve()`
  resolves against the *working directory*.
- **`dunneflow migrate`** rewrote 115,546 paths across five stores in 1.2 s. `output/mensores`
  is migrated; both revisions open, the worklist still reports 53 added / 0 removed / 18
  behaving differently, and the ground truth holds both ways.
- **A move is now free**: 0 cache hits and 628 files pruned under the old key, 628 cached
  and nothing pruned under the new one.
- **Verified by handing it over** — `output/mensores` copied to a path that has never
  existed on this machine and served from there: cover, routine list, code browser, search,
  citations, both revisions and the change worklist, with no root bound and none needed.

**Rules 60, 61 and 62** came out of it. 61 is the one worth reading: `entrypoints_from_packaging`
is a second way into the store that never goes through the extractor, so four rows stayed
absolute — in the one place the ground truth lives — while 54,746 moved, which looks exactly
like success. Found by scanning **every column of every table in every store**, not the
columns the change had touched.

**Two defects found by looking, neither caused by the path work.** The cover has reported
**0 lines** for every program since revisions landed (`_lines` asked for the legacy revision
`''`; Mensores is 186,786) — fixed. And the `source directory` control had been filled by
nothing and listened to by nothing since it was written; it is a **readout** now, stating
`not bound — none needed here`, and becomes the binding when something actually opens a
file from disk. Removing the served root turned its filler into rule 44 exactly — a live
control reading a field nothing sends, painting an empty box beside its own label — which
is what looking caught.

**Paused here. The next chunk is the ordering, and it is a wrong answer on screen today** —
see `HANDOFF.md`, "Paused 2026-08-30, after the path work", which carries the four steps in
the order they unblock each other. In short: demonstrate the inversion (capture order is
not code chronology, and `_r_changes` takes the newest *capture* as the later end), then
`--revision` so a reader can declare, then say "captured first" and never "earlier", then a
direction control on the pair — which is the control the reading end needs anyway.

Then the reading end, with its 10.2 s-per-switch cost decision. Then the code viewer's diff
view: **two lanes, and only one is faked** — real `difflib` over the bodies `source.db`
already holds, beside `changes.py`'s fact diff, which is the half nothing else can give.

**Open, and never answered:** Tom said *"the difference is the important part, and we can
call that out on every screen."* What shape that takes was asked and not answered before the
conversation moved on. **Ask before building it.** And *selecting a version from the
source-directory control* is reshaped rather than owed — that control is a readout now and a
path is not a key, so put it back to him rather than building the original ask.

## Before that: two points in time, and the worklist (2026-08-29)

**Paused 2026-08-29 with two points in time on disk and the change worklist's engine
built, guarded and measured — but not yet on screen.** See `HANDOFF.md` 5w.

The corpus is now a fair pair of clean clones, 27 commits apart:

```
../society-2026-08-26   e2e658b4   point A'   ─┐
../society-2026-08-29   03ebbd93   point B    ─┘ output/mensores holds both revisions
../mensores-overhaul               frozen, never written to
```

`output/mensores` holds `graph@<revision>.db` and `docs@<revision>.db` per revision beside
one `source.db`, and `dunneflow revisions` lists both — the older sealed as
FOR_COMPARISON. **Point A' reproduces the recorded figures exactly** (30,209 calls, 3,950
boundary touches, 175 ways in).

What the pair says: **53 routines added, 0 removed, 18 behaving differently, 15 edited
without changing anything they do**, +23 documents, and `work_items` as a new table. Four
of the eighteen have an **unchanged body** — they stopped resolving `queue.claim` because
a new module brought a second routine of that name, which is the one thing here that
`git diff` cannot say.

Three rules earned: **56** (a file restored to disk is not a module restored to memory —
a same-size mutation outlived its own restore via `__pycache__`), **57** (admitting a
directory for its documents must not admit a copy of the program — 335 phantom
documents), and the left-associative `EXCEPT`/`UNION ALL` defect that made the diff
one-sided while nine guards passed over it.

**The worklist is on screen — see `HANDOFF.md` 5x.** `/api/revisions` and `/api/changes`
are served; the navigator has a Changes group (absent from a program with one revision) and
the centre pane a worklist of four bands, every row carrying the node id so a click is the
same selection every other row makes.

**Rule 58 is the session's best find.** The diff opened a second read-only handle to a
graph the dashboard already holds open — 8,855 ms against 137 ms attached onto the
connection that already had it. Every earlier timing was taken with the server stopped,
where it is 242 ms and healthy, so it would have shipped as fast and been 84 s behind the
first click. **Rule 59** came from the harness: a mutation run scored 7/7 over an
already-red suite; the honest score was 6/7.

**The worklist has now been looked at, and it did not work — `HANDOFF.md` 5y.** Six
defects in an hour, none visible to any check, four of them meaning the feature was dead:
it **could not be reached at all** (a closed loop — the row that starts the comparison was
built only after the comparison had started); the navigator never learnt the answer once
it arrived; **every routine name rendered three pixels wide**, laid into the anomaly
worklist's severity-stripe column; and **clicking a row did nothing**, because the handler
matched a class while the routes are keyed on an attribute. Also: "Ways in" printed raw
node ids, and the trail step was the whole row. All fixed and driven.

**The best find came from the fix.** Matching on `data-nav` immediately reported `nav "on"
has no route`: `.body` carried `data-nav` as pane-fold *grid-track state* while every
routed control carried it as a *route* — one attribute, two meanings, harmless only while
the handler matched a class. It is `data-navtrack` now, with a test keeping the two
disjoint. Found by reading the console, which no test does.

**New Setting: `bandScroll`** (design rule 2). A change band capped at `32rem` put the
largest band inside a scroller nested in the page's own; rule 8 sets the default to
uncapped, and the Setting turns the caps back on.

**The pair selector is built — `HANDOFF.md` 5z.** The toolbar's revision control is real:
**one control whose options are the pairs** (`current · on its own`, `current ← Society at
e2e658b4 · 2026-08-29 23:46:24`), and the source-directory control shows both trees, because
the two revisions genuinely have different roots. Two decisions of Tom's settle the shape: **a
pair has a reading end** — `revB` is what the whole map shows, `revA` is what it is compared
with, so "what am I looking at" keeps one answer — and **pair first, then the switch**.

Four things found by driving it, all invisible to the code: both revisions read `2026-08-29`
because the id is the *capture* instant and these were captured 29 seconds apart; **the chosen
pair never survived a reload** (`PERSISTED` had it, `DEFAULTS` did not, and `loadSettings`
merges only what `DEFAULTS` declares); the guard for that found the **three search switches
with the identical defect since the day they were built**; and the notice about a dropped
revision was rendered only in the graph HUD, which a reader may never open.

**Next: the reading end** — and Tom's framing at the pause decides its shape. See
`HANDOFF.md`, "The next chunk's framing". The comparison must run to an **older or newer**
version, **by our own analysis**, so it works with any version control or with none at all:
*a source copy somebody hands you that was never documented*, which is the case where
nothing else can answer.

Two consequences. `serve()` builds the payload, the 628-file code list, both vocabulary
lanes and the cover from one graph opened at boot — the whole 10.2 s start — so switching
the displayed revision means paying that per switch or holding two sets live. And, more
urgently: **capture order is not code chronology.** `revisions.known()` sorts by filename —
the instant the snapshot was taken — and `_r_changes` takes the newest as the later end, so
analysing an old copy today makes it the *later* revision and inverts the whole worklist
with no symptom. Read from the code, not yet demonstrated; it is the first thing to try.

**Owed, and it is Tom's ask:** selecting a version *from* the source-directory control. A
path is a label, not a key — analyse the same tree twice and both revisions carry the same
one — so it needs a decision about what two identical rows should look like.

**Owed from this session:** the rendered markdown is not revision-named, so a second
analysis overwrites the first's map; `--revision` is still unimplemented.

**Two decisions taken 2026-08-30, recorded and not yet built** — `HANDOFF.md`, "Two
decisions taken 2026-08-30". The navigator's search box is **pinned when open and an icon
on the toolbar when closed**, so the 64 px is paid only by a reader using it. And
`m.<module>` appearing because a file gained its first module-level comment is **a
language feature reported as one** — not filtered, not bare: a curiosity in design rule
15's sense, carrying its own explanation, and **scoped to the language that produced it**
rather than special-cased in the diff. Research owed on how other tools present a
construct the language put there rather than an author.

## Before that: search inside the source (2026-08-29)

**Paused 2026-08-29 with search inside the source built.** Three chunks — the server, the
client, and the measurements — each verified against Mensores and driven in a real window;
see `HANDOFF.md` 5v. It was the thing Tom named at the last pause, and its shape was his:
files first, one box with two lanes, the full margin on a hit.

- **`/api/search`, two answers behind one route.** Without `path`: which files hold the
  query and how many lines each, complete and unbounded. With it: that one file's hits, each
  carrying the routine it sits in, its margin and its clickable names — `code.py`'s own
  answers narrowed to the matching lines, never a second copy of them.
- **One compiled pattern for both passes**, so the count on a row and the lines beneath it
  cannot disagree. Case, whole word and regex are switches; a regex turns whole word off and
  says why; a pattern that will not compile is named rather than answered with no rows.
- **`SourceStore` holds a bounded inflate cache**, 64 MB, keyed by content hash — and the
  bound is stated rather than pretended away.
- **The measurement decided the design.** Scanning all 184,722 lines is 20–30 ms, so rule 45
  lands on the answer and not on the search. FTS5 was rejected on evidence.

**Four defects found by driving it, three of them pre-existing, none visible to any test.**
The file filter had been destroying the box it was typed into on every keystroke since it was
written; the search results overflowed their group and painted over the four below, clicks
landing on the headings; the code pane measured 0px on a short window; and my own auto-open
marked 84 files open that nothing fetched. **Rules 54 and 55** came out of the first and the
last.

**Also worth knowing: both mutation harnesses lied before either one did**, reporting every
mutation as surviving because they were reading pytest's output rather than its exit code.
Rule 43 in the instrument, twice in one session.

**Reported, then decided.** The search box scrolls away with the list — the group note is
sticky and carries the whole answer, but the input and its three switches are ordinary
content in a group 1,900px tall on a broad search. Making them sticky costs ~64px of
always-visible navigator, which is the vertical budget already flagged at the last pause
(nine group headings cost ~306px open or closed). **Answered 2026-08-30: pinned when open,
an icon on the toolbar when closed** — the reader pays the 64px only while using it. Not
yet built.

**Next: the layer selection UI** — a time slider, a revision list, a two-point comparison, or
all three. Nothing else stands between the spine and a second point in time on screen, and
**the second point now exists to compare against.**

> **Society has been updated and pushed** (Tom, at the 2026-08-29 pause). Pull it, re-run
> `analyze`, and there are two revisions. The design conversation comes first — the shape of
> the answer, as it did for the search — but this is no longer a feature that has to be built
> against one snapshot and imagined.

Four things about that, verified rather than assumed at the pause:

- **The sealed snapshot survives the pull.** `source.db` is content-addressed and
  `prune_missing` never touches blobs, so the bodies of `2026-08-29T19:43:39Z` are safe once
  the tree moves on. That snapshot is labelled *"before Society is pulled fresh"* — it was
  made for exactly this.
- **The next `analyze` opens a second revision beside it, rather than replacing it.** Checked
  on a copy of the real sidecar: `open_working()` on a store whose only revision is
  `FOR_COMPARISON` creates a new `WORKING` one and leaves the sealed bodies readable.
- **DunneFlow never talks to a VCS** (decided; `HANDOFF.md` "Version control must stay
  pluggable"). The pull is a shell command someone runs, not something the tool does.
- **`../mensores-overhaul` is present and read-only**, holding the bodies of the sealed
  snapshot until it is pulled. Its tree is `../mensores-overhaul/src`, which is what
  `source_root` in the graph records. All output belongs in `output/`.

**Two feature requests, recorded 2026-08-30 and not scheduled.** Both are Tom's and both
are written up in `HANDOFF.md`, "Two feature requests, recorded 2026-08-30". **Size a plate
by its density** — a Setting, so a plate holding thirty nodes is small and one holding nine
hundred is large enough for them to spread; note that this *reverses* `layout.py`'s written
decision that every disk is drawn the same size so density rather than area carries the
information, and that no per-plate size exists in the model today (`spreadX`/`spreadY` are
global). And **draw a plate as a diagram** rather than a field of dots — labelled
rectangles or circles (a Setting), linking between plates, with the dimming and the hover
card carried over unchanged. Its projection question is already answered by design rule 20
(orthographic, for Tom's own reason); whether to billboard a *labelled* rectangle the way
rule 22 billboards a dot is open, and Tom says so. Rule 18 is the constraint that shapes
it: a node that carries readable text cannot be all 9,874 at once. **Tom's bar, and it is
the acceptance test:** *"they must be easy to read or we have failed"* — so a diagram that
is drawn and cannot be read is withdrawn, not shipped with a caveat.

**Still owed from before, unchanged:** `CURIOSITIES`; the worklist's two jump buttons (a
server change — `anomalies.py` carrying the node ids it already knows); the two
vocabulary-lane precision defects; per-plate sphere scaling and stack orientation; packaging
as a binary. One question is open on the worklist and was never answered: **what is an
occurrence for LOST_EDGE** — the 142 callers, or the rival definitions? 93 of Mensores' 106
findings are LOST_EDGE, so it decides the feature.

**Owed and still not looked at:** the blank-graph fix (rule 49). The automation tab never
mounts the graph — `canvas MISSING`, `frames 0` — so it is reasoned and guarded, not seen.

## Before that: the navigator (2026-08-28/29)

**The navigator, before the orientation work — 2026-08-28/29.** The three symptoms Tom gave
at the keyboard are `HANDOFF.md` 5o, and the two rules they earned are 45 and 46.

**The glossary and naming pages are ported — 2026-08-28.** See `HANDOFF.md` 5n. They were the
last two screens admitting to being unported: both lanes were computed, tested and served, and
the two views were still the prototype's, written against a shape the server does not send. A
convention is followable by its `glob` (rule 41), a term shows however many senses anything
said about it, a citation opens from `/api/source`, and the lane sizes ride with the cover.
**Rule 44** came out of it: a live control reading a field the server does not send renders
`NaN` at zero width beside a claim that is true, and nothing throws.

**The pop-up and the threads are built — 2026-08-28.** See `HANDOFF.md` 5l–5m.

- **The pop-up is a card, painted in two stages.** `getTooltip` is gone; the engine emits a
  `hover` event and the shell draws. The first paint is free from the payload — name,
  qualified name, `file:line`, plate, `3← 5→` — and `/api/hover` fills in the lines, the
  comment count, what it touches grouped and named, the governance ids and one line of WHY
  with the label saying whether it came from a docstring, a leading comment or a quotation.
- **Threads to pull are computed, in four kinds**: governance kin, the other end of a
  boundary, outliers nearby, and vocabulary. Every one carries a **subject** the router acts
  on, ordered rarest-first, with the count beside it. What they replaced was six hand-written
  rows about one routine, every one of which went to the same empty page.
- **Following a neighbour is a Setting** (design rule 2): `replace` starts a fresh hop,
  `walk` keeps the path lit. Both built, ⌘Z drops the last hop, and the walked length is
  stated.
- **`/api/naming` and `/api/glossary` are served**, computed once at start. The graph uses
  them; the two pages were ported the same day — see above.

**Known and not fixed: the near-plane clipping.** Zooming far enough in clips the nodes
nearest the camera. It is deck.gl's default frustum, the diagnosis is in `graph.js`, and the
obvious remedy — a negative `near`, which is geometrically sound under an orthographic
projection — **breaks pan and zoom**. Do not retry it without a way to drive the controls.
Rule 39.

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
