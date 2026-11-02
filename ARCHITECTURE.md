# DunneFlow — the architecture, and the surfaces over it

`CLAUDE.md` carries the command list and the rules index; this file carries **what each
module owns, and what each surface answers** — the store, the ingest seam, the resolvers,
the renderers, and the four ways a reader reaches any of it.

**Read the entry for a module before working in it.** Most of them state a decision that
was taken against an alternative that looks obviously better until you read why it was not:
SQLite as the spine rather than an in-memory graph, a parallel document store rather than a
column, six manifest providers rather than one reader with six branches.

**Two sections, because a reader arrives from one of two directions.** *The surfaces* is
what `serve`, `mcp` and `query` answer and how; *Architecture* is what is underneath them.
They were one file's worth of prose filed in two places — 126 lines under `## Commands` and
**217 more under `## Packaging — the frozen application`**, where nobody looking for the
analyse dialog would ever have found them.

## The surfaces

**`mcp` is the second surface over the same stores, and it is `serve`'s shape without a
browser.** `dunneflow mcp` speaks JSON-RPC 2.0 over stdin and stdout — hand-written against
the standard library, because the official `mcp` SDK needs `pydantic-core` and there is no
universal2 wheel for it, which is the same measurement that chose out-of-process parser
plugins over `tree-sitter`. It takes the same argument `serve` does and asks the same
question of it (`web.serve.where`), binds one base at a time, and switches with `programs`
and `open`.

**Three modules and the seam is the point.** `mcp/jsonrpc.py` is the frame and knows
nothing above it; `mcp/tools.py` holds the twelve bodies, returns plain dictionaries and
knows nothing about the wire; `mcp/server.py` is the only place that knows both. Every body
calls what the dashboard calls — nothing under `mcp/` reimplements an answer, and the three
that were reachable from one surface only (`lookup.py`, `flows.ways_in_affected` and
`flows.governance_over`, `serve.glossary_sidecars`) were moved out to where both callers
pass before the module existed (rule 51).

**stdout carries protocol and nothing else**, which is `--progress-json`'s discipline one
degree stricter: a progress reader skips a line it cannot parse and an MCP client may fail
the session. Every sentence goes to stderr. **A refusal is an answer**, so it is `isError`
on a successful call and never a JSON-RPC error — a protocol fault is the other thing —
and `mcp.Refused` is the type that says the message is already a whole sentence, because
`serve.why()` puts a class name in front of anything else and the reader here is a model
that will repeat what it is given.

**`query` is gated twice and the residue is stated.** `mode=ro` refuses every write
including `WITH x AS (…) DELETE FROM t`, which `sql.parse` reads as READ; the classifier
refuses `ATTACH`, which `mode=ro` allows and which would reach a database that is not the
map; `sqlite3` refuses two statements in one `execute`. A statement that cannot be
classified at all is refused rather than admitted for looking harmless (rule 49).
`PRAGMA writable_schema=ON` passes both gates and does nothing.

*This module is deliberately outside the no-egress guard in `tests/test_about.py`.* That
guarantee is about what **produced** the facts, which is why it excludes `web/` too; this
is `web/`'s sibling. `ingest/` is the opposite case and joins the guard when it is wired.

**`serve` takes a program, an output root, or nothing at all**, and tells the two apart by
the same question `analyze` asks to keep a program's own output out of its own corpus:
*does this directory hold a map*. Never by name — `output/` is a fine name for a directory
of hand-written prose (rule 30). **Literally the same function**, `revisions.holds_a_map`
and its listing form `names_a_map`: the glob was written out three times, twice in
`program_dirs` and once here, with this file's own sentence claiming they were one question
while they were three answers (rule 51). A test over the source refuses a fourth.

**And `program_dirs` resolves its root, which is what makes its answer a set** (rule 103).
`_r_programs` unions it with the directory being served — `out_dir.resolve()`, resolved
since the day it was written — so an unresolved listing made two unequal `Path` objects out
of one directory under a symlinked root, and the open program came back twice with the
*unmarked* copy supplied by the listing. `/tmp` and `/var/folders` are both symlinks on
macOS. The **root** is canonicalised and the children are not: `resolve()` on a child that
is itself a symlink would name a program outside the root that is listing it, and a map
kept on another disk and linked in is still this root's program. `programs_under` is the
same question without the root, because five callers spelled that exclusion as
`if d != out_root` — which is false for exactly the directory it excludes when the root
arrives unresolved, the same defect wearing the other face. Handed a root with nothing open it **serves the start
page** rather than refusing: `web/static/start.html`, whose whole job is to say there is
nothing yet and offer the two things that can be done about it. That is the state a
double-clicked application begins in.

The shell is *not* drawn empty, and that was a decision rather than an economy. It is an
application about one version of one program; drawing it over nothing would be forty panes
each having to say why it is blank, which is design rule 21 applied where it helps least —
the answer is the same for all of them and the reader has asked none of the questions yet.
Once a base exists, `/` is the shell, and the shell never boots without one.

`_Live.current` **raises** with nothing open (`NothingOpen`), which is how sixty use sites
were left alone. The gate is `_Handler.GET_WITHOUT_BASE` and `POST_WITHOUT_BASE` — **two
lists for the two route tables**, because `/api/base` is a readout from cold and a base
*switch* when posted to, and one list would exempt the second by accident. Each names the
*exceptions*, so a route added tomorrow needs a base by default and refuses visibly from
cold rather than answering out of nothing (rule 49). The refusal is a 409 whose sentence
rides in `send_error`'s `explain`, never its message — **rule 91**, and it cost the whole
refusal until it was pressed rather than tested.

`web/static/analyze.js` is the analyse dialog, the pre-flight, the progress panel and the
stop button, out of `shell.js` because the **start page needs all of it**. `prose.js`'
boundary: it owns a gesture and knows nothing about the page, and what it needs from a host
arrives as five functions — `used`, `changed`, `clearOverlays`, `openProgram`, and
`whileRunning`, which is a *claim about the host's page* and so is the host's to make. The
shell says the map you are reading stays open and stays true; the start page has no map to
say that about.

`POST /api/pickdir` asks the operating system for a folder, because `analysis.check` refuses
a relative path and a browser cannot hand a server what a picker chose. **`pick_folder` is
the one place the platform is decided** (rule 51) — `osascript` on macOS, a Windows Forms
folder dialog through `powershell -STA` on Windows — and most of what either costs is making
the dialog open *in front*: this process has no window, so its dialog is placed behind the
one that does, which is always the browser the reader just clicked in. macOS needs
`activate`; Windows needs a topmost owner form to hand `ShowDialog`. Rule 90, twice. Three
outcomes and not two: a path, a *cancel* (empty, with no reason, and not an error), and a
failure that says why. The typed field stays, always: the picker is a convenience over a
control that still works (design rule 2).

**Linux is a list rather than a command, and rule 90 costs nothing there.** macOS and Windows
each ship exactly one thing that can ask a person for a folder; a Linux desktop ships whichever
its toolkit brought, so `_LINUX_PICKERS` is the one ordered list — zenity, kdialog — promoted
by `XDG_CURRENT_DESKTOP` so Plasma is offered the Qt dialog, *promoted and never excluded*, and
a machine with neither refuses naming both (rule 89). The dialog takes focus on its own,
measured. `org.freedesktop.portal.FileChooser` is deliberately absent: its result arrives on a
signal, which means a D-Bus binding this tool will not grow for a convenience.

**And `_desktop_session` is what makes a cancel readable there.** Measured on zenity 3.44.2, a
cancel exits **1 with an empty stderr** and a failure to open the display exits **1 with a line
on it** — one code, told apart only by text that a healthy desktop also writes for harmless
reasons. So the display is checked *before anything is spawned* and the failure that actually
happens is refused by name, which leaves exit 1 meaning one thing. The residue is stated: a
dialog that opened and then broke reads as a cancel.

`POST /api/reveal` opens the root in the Finder, in Explorer or in the desktop's file manager
and is bounded to it — the bound is judged in the handler, before anything is spawned, and
`reveal_dir` asks nothing about permission. It is the answer to the one cost of
`~/Library/Application Support`, of `%LOCALAPPDATA%\DunneFlow`, and of
`$XDG_DATA_HOME/DunneFlow`: each is the correct place for an application's data, none is swept
into a sync folder, and all three are invisible to a reader who wants to hand a colleague a map
(rule 89). Windows' `explorer` **exits 1 on success**, so its return code is deliberately not
read.

**Linux is two rungs, and `xdg-open` is the second.** `org.freedesktop.FileManager1.ShowFolders`
is the desktop's own *reveal* — an activatable D-Bus service every major file manager
implements, so it starts one that is not running and consults no MIME default at all.
`xdg-open` is what everybody reaches for first and answers a slightly different question: it
hands the directory to whatever the desktop says opens `inode/directory`, and **measured on the
machine this was written on that is `org.gnome.baobab.desktop`**, a disk usage analyser. It
opened Thunar regardless, because XFCE's `xdg-open` routes through `exo-open` and never reads
that default. One rung is right by construction and the other was right by luck.
`--print-reply` is load-bearing: without it `dbus-send` exits 0 for having *sent* a message
nobody may be listening for, and the second rung would never run (rule 76). An exhausted ladder
reports the **last** rung's reason, because `xdg-open` is the one every desktop has.

**`serve` also *makes* a program.** The `<select>`'s last option, `+ Analyse a directory…`,
reads a source tree into a new directory under the output root and puts it in the list —
`POST /api/analyze`, `GET /api/analysis`, `web/analysis.py`. Four things about it:

* **A subprocess running `dunneflow analyze`, never an in-process call.** Every store this
  process opens is `writable=False` (rule 20), and an in-process analysis would make the
  serving process a writer to the tree it serves. It also keeps `walk.py`'s
  `ProcessPoolExecutor` out of a request thread, and makes what runs *exactly* the tested
  command rather than a second assembly of the same steps (rule 51).
* **Two channels, and `--progress-json` is why.** The child's **stdout** is one JSON object
  per line; its **stderr**, emptied by `--quiet`, is where a failure says why. Scraping
  prose written for a human would promote a sentence to a contract (rule 30). The step list
  is **computed for the run** — four flags remove work, so a fixed total is a bar a
  `--no-docs` run can never reach (rule 32) — and is printed as sent all the way to the
  screen. A failure's reason **leads with the child's last line** and keeps the rest as
  evidence: a traceback says the useful thing last, and this reader does not write code.
* **And the walk's residue rides that channel, because design rule 1 held for the command
  line and not for the application.** `walk_residue` has worded *unread: 4,120 `.go`*,
  *left out as tests: 315 typescript* and *declined by you* since the walk became
  multi-language, and `analyze` prints them through `_emit` — which is stderr, which
  `--quiet` empties. So the one surface that could not see what had been filtered out of a
  map was the dialog that made it. A `residue` record goes on the stream **once**, the
  moment the walk knows, and `note_analysis` carries it across exactly as it carries
  `began`: the report is replaced whole, so without that stickiness the panel would show it
  for the fraction of a second before the next line arrived. Its arrival counts as movement
  and being carried does not, or a watched run would never look silent. It is recorded on
  the map as well (`meta.walk_residue`, a JSON list) — a panel is dismissed and a map is
  kept, and *what is not in this map* is the other half of every count in **About this
  map**. **Three answers there and not two**: not recorded is a map written before `analyze`
  could say, an empty list is *nothing was left out*, and lines say which (design rule 21).
  The panel flattens the first two deliberately — a running commentary announcing *nothing
  was left out* on every healthy analysis is noise on the common case.
* **Its own slot, not the switch's.** `claim_analysis` beside `claim`. A switch replaces
  what is on screen; an analysis replaces nothing, so one slot would mean a ninety-second
  read of an unrelated tree locking the reader out of changing versions. That is also why
  the panel is dismissible rather than the base switch's blocking scrim — *the map on
  screen stays true for the whole run*, and it says so.
* **The served program is refused, and it is not caution.** `Store._discard_if_stale` drops
  every table of a graph written by another build, and this server is holding that graph
  open — so an analysis aimed here can empty the map under a live reader. Every other
  refusal has its own sentence too (`analysis.check`, one function for the dialog's live
  warning and the endpoint's answer, rule 41); analysing into a name that **already exists**
  is allowed and *says* it rewrites that program's working snapshot.

**A map records whether its own analysis finished, and every reader that vouches for one
checks.** `analyze` commits `complete = ""` as it opens the graph and `"yes"` as its last
act, and commits the **step** as it goes. This is not housekeeping: a killed `analyze` leaves
a graph that *opens perfectly and lies* — one stopped twelve seconds into Society reported
628 files, 4,786 routines and **`resolved_calls = 0`**, over a timestamp, a tool version and
the determinism guarantee. Reachable with no stop button anywhere: Ctrl-C, a sleeping laptop,
an OOM kill.

**Three states, never two** (`Store.finished`): missing means *written before this key
existed* and is fine, `""` means *started and never finished*, `"yes"` means finished.
Refusing on absence would refuse every map made before it. `UnfinishedMapError` is raised on
**read** paths only — `_Live.open`, `_open_store` and so `check`, and `serve`'s boot — with
`analyze` deliberately exempt, because opening one is how it recovers (34 s on Society, since
the extraction is content-hashed). `query` is the one reader that proceeds, and **warns**:
its contract is that you get the rows that are there. `unfinished_sentence` is the one place
those words live, and `serve.why()` strips the class name from the two exceptions written to
be read.

**An analysis can be stopped, and the slot asks the process rather than a flag.**
`POST /api/analyze/stop`. Three things make it work:

* `_Live.analysis_proc` holds the child. It was a local inside `analysis.run`, so nothing
  could stop a run at all — no route, no button, and a hung child held the slot until
  somebody killed the server.
* **The slot asks the claim *and* the child, and neither alone is enough** (rule 104).
  Asking `state == "working"` is asking a label, and a label outlives the thing it names: a
  watcher that dies without noting leaves it true for ever, which is why the question moved
  to the process. But the process does not exist yet — between `claim_analysis` returning
  and `on_start` handing the child over there is a thread start and a `Popen`, and through
  that window a second claim succeeded, overwrote the report, and then overwrote
  `analysis_proc`, leaving the **first** child unreachable and still writing into the same
  output root. Measured in three lines and no timing at all. So `analysis_running` is
  `claimed and (no child yet or the child is alive)`; it is not a superset of either half
  (rule 36), and the stale lock is still cleared rather than left for somebody to notice.
* **`_Live.start_analysis` is the only place a claim is taken, started or released**, and
  the release is the watching thread's own `finally`. That is what makes *claimed* safe to
  trust: a claim given back by a caller saying it is finished can outlive the work, and one
  given back by the work stopping cannot. It was eleven duplicated lines in `_p_analyze`
  and in `mcp/session.py`, so whatever either did about a claim that never became a child
  it had to do twice (rule 51).
* **The child gets a group of its own and the stop goes to the group.** `analyze` runs a
  `ProcessPoolExecutor` whose workers inherit the pipes: signalling the parent alone left
  **eleven workers** holding stdout open, so `run`'s read loop never returned and the report
  said `working` over a child that had gone — the very jam, arriving through the fix for it.
  `own_group()` is the one place the platform's spelling of that is decided: a new session on
  POSIX, `CREATE_NEW_PROCESS_GROUP` on Windows. The wrong one there is not an error —
  `start_new_session` is *accepted and ignored* — it is a stop that does nothing, and the jam
  was reproduced whole on Windows before this existed: 17 descendants, `terminate()`, and the
  read loop still running 60 s later.
* **Two rungs, and each platform spells both.** `SIGTERM` then `SIGKILL` to the group; a
  **console break** then `taskkill /F /T` on Windows, measured to take a pool of eight from 8
  descendants to 0 where `terminate()` took it from 9 to 9.
* A stopped run is `state: "stopped"`, **not `failed`** — the reader did it on purpose, and
  the exit code is the child's own evidence rather than a flag set from outside (rule 13).
  `was_stopped` knows the two spellings: a negative code on POSIX, `STATUS_CONTROL_C_EXIT` on
  Windows. **The one exception is bounded and stated**: a packaged Windows build is windowed,
  so it has no console to raise a break in and must use the forceful rung, which leaves exit
  1 — indistinguishable from a broken analysis. `note_forced` records that this process did
  the killing, *before* the kill because `taskkill` returns after the child is already gone
  and a note taken afterwards loses the race, and **withdrawn if the kill could not be
  delivered**, which is what keeps it a record of what happened rather than of what was asked.

The slot records `began` and `moved`, and `moved` bumps **only when something changed** — a
timestamp refreshed by being polled would say a run was moving because it was being watched,
and *silent for 4 m* is the only thing separating a wedged child from a long step. The panel
**states the silence and acts on nothing**: resolution is legitimately quiet for tens of
seconds, so the judgement is the reader's. A refusal to start a second analysis carries the
running job and a **Stop it**, kept live while the dialog is open and clearing itself the
moment the run ends — the sentence promises that, so something has to keep it (rule 44). And
the page asks `/api/analysis` at boot, because a run outlives the page that started it.

**`serve` says what read the map, and whether anything in it was guessed.** The topbar's
`source directory` control — a readout until there was something true to put in it — opens
*About this map*: `GET /api/about`, and the two rows it exists for are

| Inferred facts | none — every fact here was read, not guessed |
| Read by a model | none — this analysis is deterministic and local |

**A standing guarantee, not a placeholder waiting for a model.** Nothing on the analysis
path calls a model or touches a network: the extractors are stdlib `ast` and `tokenize`, the
document scanner is hand-written, and `Provenance`'s two paid tiers (`CITED`, `INFERRED`) are
declared and unbuilt. Tom, 2026-09-04: *"Inference should always be voluntary and secondary."*
A test asserts nothing under `extractors/`, `resolve/` or `canonical/` imports an HTTP client
or an LLM SDK, because a claim on screen that no query can return is prose (rule 13).

**The Inference page is withdrawn as of 2026-09-09**, and these two rows are untouched by
that — they were a guarantee rather than a placeholder, so removing the feature makes them
more true and not less. Tom: *"The infer parts can be disabled as features and the links can
be removed (but the code left in place and marked for use in the next version)."* It had
never been wired: `MANIFEST` was a `let` nothing assigned, so the page said *"not served
yet"* for ever, and `data-airun="go"` set `state.aiDone` and reported **"Pass complete"**
having done nothing at all — design rule 16 with a false claim on top. **One constant
decides**, `INFERENCE_SHIPPED` in `shell.js` (rule 51): while it is false there is no
navigator row, no Settings link, no route, no breadcrumb and no dispatch, `selfCheck`
asserts no control on screen carries `data-goto="inference"`, `data-airun`, `data-aiop` or
`data-egress`, and `tests/test_inference_withdrawn.py` asserts both halves over the source —
every door guarded, **and** every part of the feature still there. `egress` and `aiOps` left
`DEFAULTS` and `PERSISTED` on `nodeShapes`' precedent, because a reset naming a setting the
reader was never offered is what a default promises and cannot deliver. Untouched, and none
of it is the feature: *edge confidence* `INFERRED` and the *hide inferred edges* toggle
(design rule 5), the *version tier* `INFERRED`, and `Provenance`'s four tiers.

**Missing and blank are different answers**, and flattening them would turn a silence into a
promise. Every field arrives as `{recorded, value, none}`: a map written before `analyze`
recorded any of this reports `recorded: false` and says *"not recorded — written before this
map could say"*. **`none` is the server's decision**, never a test for the word on the page —
`inference` stores `none` so `dunneflow query` over `meta` reads as prose and `model` stores
blank because there is no word for the model that did not run, and the page owns neither
spelling (rule 51).

*What is deliberately **not** offered is a "would a newer build read this differently?" row.*
For the map on screen it can only ever answer no: `Store` opened read-only calls
`_refuse_if_stale`, so a mismatched graph never becomes the base at all. What is stated is the
guarantee that produces. The honest *should I read this again?* signal is the date beside it
and the **tree leaf** it was read from — a leaf, never a path (rule 60).

`serve` also switches **program**, which is the same operation one axis over. The topbar's
first control lists every directory under the output root that holds a map —
`revisions.program_dirs()`, the same question `analyze` asks to keep a program's own output
out of its own corpus — and `POST /api/program` rebuilds against one of them. Two things
differ from a revision switch and both are in `_Live.switch_program`: the sidecars are
repointed, because `source.db` and `docsource.db` belong to the *program*; and **every**
cache is cleared, because `findings` is keyed on a graph's *basename* and `filepairs` on a
pair of revision strings, and two program directories collide on both. `PROGRAM_CACHES` is
stated separately from `COMPARISON_CACHES` rather than derived from it (rule 36). Nothing is
closed or repointed until the new base is built, so a stale program leaves the reader looking
at what they had, with the store's own sentence in the progress report (rule 20).

`serve --revision` chooses which point in time the server opens as the **base** -- the
version the cover, the routine list, the code browser, the glossary and the stack all
show. It defaults to the newest. The reader can switch it from the toolbar, and that
switch survives a page reload; this is how it survives a restart of the server, because
the base is the server's state and not the browser's.

`GET /api/graph` takes `?level=routine|module` and `?minDisk=<n>` — the stack's **level of
detail** and how few things a plate may hold before it is merged into `<small>`. An unknown
level is refused with a 400 rather than defaulted, because a silent fallback answers a
question nobody asked with a picture that looks exactly right; the threshold is clamped
instead, because the two are different mistakes. On screen it is the *Detail* control in
the legend, which states what the altitude costs: what is drawn, what it stands for, and
what the threshold merged.

`migrate` rewrites a program directory written before paths were relative (rule 60), **in
place** — 115,546 paths across five stores in 1.2 s on Mensores. In place rather than by
re-analysis, because a sealed snapshot exists to be readable after its source tree is
gone and rebuilding would orphan exactly those. A reader refuses an unmigrated store and
names this command; it never repairs one on the way past (rule 20).

`analyze` reads documentation as well as source, from the package root by default
(`--docs <path>`, `--no-docs`, `--recheck-docs`).

The dashboard also searches the **text** of the source — `/api/search`, the Code group's
box. That is a different question from `touches`, `impact` and the glossary, which search
names and meanings: this finds a word inside a comment, inside a string literal, or on a
line that carries neither.

`analyze` is incremental: unchanged files are not re-parsed.

**Diagram mode has two levels too**, and the second is asked on demand rather than built
with the others: a compartment is fifty-three drawings from one pass over the model, and a
*box* is one of nine thousand. Measured on Mensores 2026-08-31:

| Measure | Budget | Measured |
|---|---|---|
| One compartment, drawn in the browser | < 500 ms | 93–179 ms |
| Opening a box — three grouped queries | < 200 ms | 15 ms (18 routines) · 170 ms (61) |
| `/api/fold`, a class of 61 methods | < 500 ms | 0.77 s cold, ~40 ms warm |

**ALGORITHMS is a page and a mode, and they are two questions.** The navigator's
*Algorithms* group opens `/api/algorithms` — five lanes over the whole program, each with
its denominator, held on the base. The mode toggle's **Shape** opens `/api/shape?node=` —
the selected routine's own outline, answered on demand. 115 ms and 0.1 ms; see
`PERFORMANCE.md`.

## Architecture

```
                  ┌── python ── in this interpreter ──┐
source ──► walk ──┤                                   ├──► graph.db ──► resolve ──► render
           per    └── typescript ── node, over a pipe ┘    (SQLite)     per lang    Markdown
           suffix        one reader per language,           the one      RESOLVERS   + Mermaid
                         one plugin.json each                source                     ▲
                                                             of truth                   │
docs   ──► extract ──► docs.db  (SQLite) ──────────────────────────────────────────ATTACH┘
           per file,    a parallel store, never
           parallel,    the same one
           stat-gated
```

**Which reader sees a file is decided by its suffix and by nothing else** — `LANG_SUFFIX`,
built from the manifests, where a suffix belongs to exactly one language and two plugins
claiming one is refused at load. The walk groups by language and dispatches; `resolve/`
groups by `files.lang` and dispatches again. Neither the renderers nor the orientation
queries know a language exists.

- `runtime.py` — **what this build is and where it lives**, and the only place any of it
  is answered (rule 51). Four questions with two answers each — frozen or not, where my
  files are, where maps go, how to run myself again — and every one of them used to be a
  `Path(__file__)` or a hand-written `sys.executable` in whichever module needed it. See
  `PACKAGING.md`; the layout of `resource_root()` is what makes a binary's map and a
  checkout's map the same map.
- `schema.py` — the fact contract. Every extractor, in any language, emits these types.
  A **call site has an identity** (`call_site_id`) and carries the arguments the caller
  wrote (`CallArg`), because two identical expressions in one routine are two calls and
  the arguments of one must not land on the other — 287 such pairs on Mensores. The id
  holds no position, like every other id here: an ordinal among identical expressions in
  the same caller, with the residue stated in the docstring rather than hidden.

  **Every id a reader mints is one of four functions here, and no reader spells one
  itself.** `definition_id(file, qualname[, ordinal])` for a routine or a structure,
  `entrypoint_id(file, …)` for a way in, then `call_site_id` and `control_point_id`, which
  are derived from a routine's. The file is in the first two and that is **rule 106**: a
  qualified name is only unique inside one language's naming, so `probe.py` and `probe.ts`
  in one directory were module `probe` twice and `probe.main` was one id in two languages —
  a tree that could not be analysed at all. `plugins/typescript/src/ids.ts` is the one
  deliberate second implementation, on the far side of a pipe where rule 51 cannot reach,
  and it is pinned from both sides by a test.

  **A stored path is an identity too, which is why `stored_path` lives here** beside
  `make_id` — the one place a `path` or `file` column is spelled, and every writer passes
  through it (rule 51). Rule 60 made those paths relative because an absolute one names one
  machine's directory layout; **rule 93 is the same argument about the separator**, because
  `web\\serve.py` and `web/serve.py` are one file and two keys, so the pair cannot be
  compared and a Windows build and a macOS build cannot read each other's maps. It was six
  spellings in six modules and every one was right where it was written. The reading side
  never was in doubt: `conformance` reaches for `PurePosixPath`, `migrate` matches
  `LIKE '/%'`, the shell takes a leaf with `split("/")` — every consumer had already decided
  a stored path is POSIX, and only the writers had never been asked.
- `store.py` — SQLite. **The spine, not an export format.** Nothing holds the whole
  program in memory; reachability is recursive SQL over indexed edges. This is the one
  decision that lets the tool survive growth — do not replace it with in-memory graphs.

  **A burst of writes is one transaction and also has a ceiling**, which is rule 107 and
  `settle_if_large`. SQLite cannot checkpoint a write-ahead log inside an open write
  transaction, so "one transaction per reader" grew a log nothing could drain and then paid
  to read its own writes back out of it: 734 MB and 0.1% CPU on a tree of 84,159 files.
  `WAL_CAP_BYTES` carries the measurement and sits beside the `cache_size` it is derived
  from. What it buys beyond speed is that a killed run **keeps what it committed**.

  **A boundary a signature names lives in `declared_boundaries`, never in `boundaries`**
  (schema 18). Go's reader reads `go.yaml`'s `signatures:` -- a parameter or result typed
  `*net.UnixListener` -- for a routine whose body shows nothing of that kind, which is what
  a stub that only panics looks like. Same columns, its own table, because 45 queries count
  or detect `boundaries` and a filter each of them has to remember is rule 51 at 45 call
  sites. `counts()` and the analysis summary say them separately; the dashboard does not
  show them yet (BACKLOG 48).
- `walk.py` — discovery, and **the size guard**. `parts_under` cuts a tree into parts no
  larger than `TOO_BIG`, descending only into what is oversized, and `Breakdown.uncovered`
  states the one thing a cut of directories cannot cover: a directory that had to be split
  cannot also be a part, because the command for it would read its children again. The bound
  is the edge of what has been read end to end — 18,191 files — rather than a limit somebody
  chose, and `cli.py` says so in the refusal. `serve` is not involved: it runs `analyze` as a
  child and promotes the child's own last line, so the refusal reaches the analysis pane
  without a second copy of the sentence (rule 51).

  **`judge_root` is where a path-shaped rule is measured from, and `root` is still the
  program.** A reader's `skip_dirs` and `is_test`'s `test_dirs` both walk `rel.parts`, so
  the same file is judged differently depending on where the walk started —
  `Engine/Source/ThirdParty` is 620 files from the top of Unreal and **57,373** as a root
  of its own. `analyze --part-of <tree>` supplies the tree: discovery judges as the tree
  would while the root stays the part, so module names, stored paths and the store key are
  untouched. The flag is on **every** command a breakdown prints (`cli.part_argv`, the one
  spelling both the refusal and `tools/ingest_parts.py` use), because for a part crossing
  no such name the two answers are identical and one rule is cheaper to keep right than a
  condition at two call sites. With it, `Breakdown.uncovered` holds only the split-directory
  half and Unreal is **86 parts covering all 88,356 files** where it was 84 covering 84,590.
- `ingest/` — **the seam a language arrives through, and the only place a fact becomes
  this program's.** Six modules and the split is the point.

  `contract.py` is what a reader may say and what a manifest may claim — `PluginManifest`,
  `DiscoveryRules`, `Toolchain`, the `IngestPlugin` protocol, and four exceptions that are
  four different facts: `ToolchainMissing` is never a defect and always recoverable,
  `PluginRefused` and `RulesMissing` are always build defects, and `ProtocolError` means the
  channel is carrying something other than this protocol, so every fact already taken from
  it is suspect (raised once and loudly, never absorbed per file). `codec.py` is the wire
  form, reflective over `dataclasses.fields()` so a field added to `schema.py` needs no
  second declaration. `worker.py` spawns, shakes hands, correlates on an id, **drains stderr
  without ever parsing it**, and respawns once without retrying the file that killed it.
  `inprocess.py` and `outofprocess.py` are the two kinds of reader. `literals.py` runs the
  SQL and artefact scanning for every language **in the host** — see `FileFacts.literals`
  below. **`acts.py` is the other judgement made there for every reader**: `one_act` drops a
  boundary or a remote call whose spelling extends another one's on the same line, in the
  same routine and of the same kind, because the dotted contract folds `f(x).g()` into
  `f.g` and a rule that matched `f` matched the chain again (rule 40). Society had 257 such
  DATABASE rows.

  **`stamp_lang` is the one place a language is written onto a record**, and it refuses a
  record that brings its own: a reader says which language it *is* once, in the handshake,
  and the host verifies what came back against what it was handed. `Routine` and
  `DataStructure` each carried `lang: str = "python"` until chunk 3, which is a default that
  is right for exactly one reader and silently wrong for every other.

  **`SOURCE_TEXT` is a term of the protocol and was paid for.** Python reads text with
  universal newlines and Node does not, so every CRLF file hashed differently on the two
  sides and came back refused as *changed while it was being read* — a whole corpus lost on
  Windows, to a difference neither side could see.

  **In the core fingerprint, and `canonical/` still is not** (see below): the registry
  decides which reader sees a file, the contract decides what a reader may say, and
  `stamp_lang` writes a field into every record. All three shape what a fact *is*.
- `plugins/<lang>/plugin.json` — **one manifest per language, and it is the extension
  point at the scale `detectors/*.yaml` is at the scale of a framework.** It declares the
  suffixes, the skip and test rules, the receiver words, whether the reader supplies edges
  or reports literals, its rules file, its toolchain, and the files its stamp is computed
  from.

  **`fingerprint` names files and never globs**, and the asymmetry between the two kinds of
  reader is deliberate. An out-of-process reader is its **built bundle** — `plugin.json` and
  `main.bundle.cjs`, never its source tree and never `node_modules` — because a glob over a
  directory that was not bundled returns `[]`, which hashes to nothing and blames the whole
  build for one missing plugin (rule 49, in a fingerprint). An in-process reader is a
  package in this program, so its whole tree is globbed and it cannot forget a file somebody
  adds.

  **`plugins/typescript/` is a pnpm package built by esbuild into one committed
  `main.bundle.cjs`**, with the TypeScript compiler inlined — and with its `lib*.d.ts`
  inlined too, which is rule 97: esbuild cannot carry them because the compiler opens them
  **by path**, and without them it does not refuse, it builds a program with no `Array` and
  no DOM and answers anyway. `src/facts.ts` is **generated** from `schema.py` and a test
  compares, so the two sides of the wire cannot drift. The bundle is committed and a test
  asserts it is the committed source (rule 37).

  **`plugins/go/` is shipped as source and built on the machine that reads**, which is the
  third shape a reader can take and the reason `plugin.json` has a `build` field. Go's
  checker needs the `go` toolchain at run time anyway, to read the standard library's
  source, so building with it costs nothing beyond being able to run at all; one binary per
  platform would instead have meant one `fingerprint` per platform, and a map written on one
  machine refused as stale on another (rule 12). `ingest/outofprocess.built_reader` builds it
  once per stamp, platform and toolchain into `runtime.reader_cache_root()`, with
  `GOTOOLCHAIN=local` so that a build can never download a toolchain. It is stdlib-only, so
  nothing is ever fetched; `facts.go` is generated from `schema.py` by
  `tools/gen_facts_go.py` and compared by a test that needs no Go, and its hand-written
  BLAKE2b and Python-compatible decoding are pinned by `tests/fixtures/ids/vectors.json`.

  **`plugins/rust/` is the same shape with its dependencies vendored**: `syn`, `proc-macro2`,
  `quote` and `unicode-ident` under `vendor/`, built `--offline --locked`, every file in the
  fingerprint. `{workdir}`, `product` and `build_env` exist in `plugin.json` for it
  (`PACKAGING.md`). Its edges come from **`src/edges.rs`, a path resolver**, not a checker:
  each crate's module tree is built from `mod x;`, `use` and `#[path]`; `src/types.rs` follows
  a receiver's *declared* type; `src/deps.rs` reads the direct dependencies `Cargo.lock` pins
  out of the local cargo cache, never fetched, to confirm where a call leaves the program.
  Every call without an edge carries `calls.frontier` and `calls.reason`. The edge pass also
  answers one question no file can — **which files only a `#[cfg(test)] mod x;` reaches** —
  as `edges_done.test_only`, and `walk._leave_out_test_modules` drops them, holding the set
  with each file's hash in `meta` (`test_modules:<lang>`) so an unchanged one is never
  parsed again.

  **`plugins/java/` is javac's public tree API behind the pipe**, built by `java Build.java`
  into a jar that `run` starts (`PACKAGING.md`), with no dependency: `Json.java`, `Ids.java`
  (BLAKE2b) and `Text.java` (Python's maximal-subpart decoding) are written by hand and
  pinned by `vectors.json` through the reader's own `--self-test`. `Extract.java` parses one
  file from the host's text and never from the file; `Edges.java` parses every file in one
  `JavacTask`, walks each with the extractor's own walk **before** attribution so every site
  carries the facts' `site_id`, then `analyze()`s with `-XDshould-stop.ifError=FLOW` so a
  missing class does not end attribution. Its dispatch rule is Tom's (2026-11-01, in the
  class comment), narrowed to overrides that can answer the receiver's static type, and a
  javac pick among overloads under an argument it could not type is refused as `untyped`.
  For each `dynamic` call it sends the location of every body that may answer
  (`SuppliedEdge.answers`). `Deps.java` reads the jars the build files declare out of the
  local Maven and Gradle caches, never fetched, onto the edge pass's own classpath.

  **A toolchain that is not installed declines its language and the rest is read.**
  `walk._runnable` asks each language that has files whether its reader can run, before any
  cache key is read, and a missing `node`, `go` or `cargo` removes that language's files from the
  walk with its own residue line, *not read, no toolchain*, which is neither *unread* (no
  reader) nor *declined by you* (design rule 21). Until 2026-11-01 nothing asked, and a
  machine without `node` lost the Python half of a mixed tree to an uncaught refusal.
- `extractors/python/` — stdlib `ast` + `tokenize` only. No third-party parser. It is the
  **in-process plugin's reader**, named by `plugins/python/plugin.json`'s `reader:` field
  rather than imported by the walk: the one language that runs in this interpreter still
  arrives through the same seam as the one on the far side of a pipe, and
  `tests/plugins/python-oop/` runs *this extractor* through a subprocess worker to prove the
  two paths produce byte-identical facts.
- `canonical/` — whether two writings are **the same expression**, one module per language.
  Beside the readers rather than inside one, and that placement is load-bearing: a plugin's
  own files are globbed into **that language's** stamp, so a canonicaliser living in
  `extractors/python/` would discard every Python row in every graph on the machine —
  sealed snapshots included — each time it was edited, for a module extraction never reads
  and that cannot change one fact. A language with no entry compares its expressions as
  written.

  *That sentence used to say `code_extraction_inputs()` and **every graph on the machine**,
  which was the whole truth while there was one key.* The split made the cost smaller and
  did not make it acceptable: a sealed snapshot losing its Python rows is still the one
  store that is not derived losing facts nothing can rebuild (rules 25 and 62). And
  `canonical/` is in **neither** key, which is the same test both keys apply — what does
  extraction actually *read*. A canonicaliser cannot change a fact, only whether two facts
  compare equal.
- `extractors/docs/` — Markdown, reStructuredText and plain text, scanned by hand for
  the same reason: no markdown library. Emits `DocFacts`.

  **A map is pruned out of the corpus by the walk, not by a set of paths — rule 92.**
  `discover_docs` asks `revisions.names_a_map` of the listing `os.walk` already took, so a
  directory holding a `graph*.db` goes with everything beneath it, `map@<revision>/`
  included, wherever in the tree it sits. It used to be an `exclude` set built from
  `program_dirs(out_root)`, which is right from a checkout — where the output root is
  `./output`, inside the tree being read — and empty of anything relevant from the
  **packaged application**, whose root is `~/Library/Application Support/DunneFlow`.
  Measured on DunneFlow's own map as the signed binary built it: **122 of 147 documents**
  out of `output/`, **all 122** stated naming rules mined from them, and a 289 MB document
  store. `exclude` remains for the one thing a marker cannot see — this run's own `out_dir`,
  created before the scan and holding no graph until after — and both walks **name what they
  pruned**, in their own words, because a corpus 83% smaller than the directory is design
  rule 1's whole subject. Unlike the checkout marker this one applies at the root too: a
  corpus is itself a checkout and is never itself a map.

  **A constraint is not a definition, and the judgement is on the opening.**
  `- `definition`: 1 ≤ len ≤ 5000 chars` is a validation rule for a field, written in the
  shape a gloss is written in, inside a section whose heading reads *"AC-19: Performance
  budget for glossary tools"* — and it reached Society's glossary as one of sixty defined
  terms, saying this program defines the word *definition* and meaning a bound on a string's
  length. A gloss that **begins** with a bound, a bare type, a regex or a placeholder value
  states a shape; a sentence that reaches a number partway through is prose about a budget.
  Measured over all 240 definitions the corpus yields: **5 refused**, every one a field
  constraint, and the three that quote a bound mid-sentence kept. The pattern is
  `constraint_glosses` in `detectors/docs/prose.yaml` — the stated extension point — and it is
  applied in `_add_def`, the one place every definition of every form passes (rule 51): a
  table row can carry a constraint exactly as a dash gloss can.

  *What is deliberately not changed is the section rule.* A heading that merely **mentions**
  the glossary still admits definitions, and 29 of these came from that one heading. Requiring
  the word to head its phrase drops 77 of 240 corpus-wide and takes 60 defined terms to 58;
  measured, offered, and Tom's call was to refuse the constraint alone.

  **A naming standard is usually a table, and `_table()` reads one.** The FORM lane was
  empty across all 2,064 of Mensores' documents — 5 rules, all VOCABULARY, none
  `checkable` — because `_table()` consumes a table whole and the loop `continue`s, so the
  prose rule detector is never offered its lines. `table_rule_columns()` decides which
  column names the thing and which gives its spelling, on the model of
  `term_columns`/`meaning_columns` beside it and with the rule that matters kept: **both
  halves are required, on different columns.** A column qualifies on its **header or its
  cells** — headers vary between organisations, and cells alone miss a column headed
  `Convention` whose contents are too terse to score. Measured over 5,230 tables: it fires
  on **one**, `harness/rules/style.md:30`, and mints its seven rows; the 100-row *Key
  Decisions* table and the pantheon glossary do not fire. A row whose scope names no
  identifier class is **kept, not dropped** (design rule 1) with `scope=""`, so it is a
  rule this tool has no population for rather than a rule that vanished.

  **That rule governs the extractor, and only the extractor.** Its output is a contract,
  hashed into the cache key by `doc_extraction_inputs()`, so a third party's reading of a
  document must never become a fact this tool asserts. A **renderer** produces pixels, is
  in no cache key, and no fact depends on it — which is why `markdown-it` is vendored in
  `web/vendor/` and why nothing under `extractors/` may import it. State the line rather
  than blur it, or the next reader will correctly call the library a violation.
- `resolve/manifests/` — **what a program declares about itself**, one provider per
  filename: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `Package.swift`,
  `build.gradle.kts`. Six small modules rather than one reader with six branches, because
  `web/waysin.py:120` renders the **evidence verbatim** and a `package.json` entry
  claiming to come from `pyproject.toml` would be a visible falsehood in the one string a
  reader is shown unparsed.

  **Entrypoints and version are independent columns.** `go.mod` declares a module path and
  no version of the program — its `go` directive is a toolchain floor, and reporting
  `1.25.6` would be a number certainly in the file and certainly not the answer; what it
  *does* declare is a `/vN` major suffix, which is Go's only way to say *this is major
  version 2*. `Package.swift` declares executables and no version at all. `"scripts"` in a
  `package.json` is **never** a way in — it is a task runner, and the four JavaScript
  corpora here hold 31 of them and not one `bin` at their roots (rule 30). Every refusal
  is a sentence the run prints, one line per *kind* of refusal: DunneNote's twenty
  manifests produce twenty-one notes and eleven are the same one.

  **Discovery is the whole tree, not a walk up it.** Tom's criterion, 2026-09-17: *any
  module that has inputs and/or outputs is included, because that is flow — it must
  include the entire application.* A `bin` is a way in, so a member declaring one is part
  of the program whether or not it sits at the top. `walk.discover` collects manifests off
  the listing it already took, so which directories count is answered once (rule 92); the
  package root is read as well, because a `src/` layout puts it above the analysed tree.
  **The root's manifests answer the program's version and a member's does not** — and when
  two roots declare different versions, both are recorded and neither is picked.

  **Three states for a way in, never two** (design rule 21). `Entrypoint.declared` is a
  *field* — it was `"[project.scripts]" in e.evidence` at `flows.py:259`, a substring test
  against a prose sentence that a `package.json` `bin` can never match (rule 30) — and a
  declared way in that bound nothing is kept, with `binding_note` saying which of five
  things happened. Only one of the five is a fault; see rule 98 for the false SUSPECT that
  taught it. The `manifests` table records what was read, so the sentence on the cover has
  a query behind it (design rule 13).

- `standards.py` + `standards.db` — **somebody else's rules, admitted without being
  absorbed.** `--standards <dir>` reads an outside naming standard through the *same* walk
  as the corpus (so `discover_docs` refuses a nested checkout for it too, rule 57) into a
  store of its own. Its own **file**, never a column on `documents`: `docs.db` is read by
  the glossary, the mirror, traceability and Document mode's corpus lane, and a flag would
  make every one of those a place that must remember to filter — the seven-read-paths shape
  rule 51 was minted from. `docsource.db`'s argument, one subject over. Rule 57 gains three
  refusals a reader can trigger by naming a root — inside the output tree, inside the
  documentation root, inside the analysed tree — **each with its own sentence**, and all of
  them judged *before* anything is opened, so a refusal never abandons a half-written map.
- `resolve/glossary.py` — **which words are vocabulary at all**, and it is the denominator
  under every coverage figure the tool prints. Words are mined from the names a person chose
  for a *thing* — a package, a way in, a table, a constant — and a constant is split on
  underscores, which is where the recall goes wrong: `_GLOSSARY_DEFINITION_MAX_LEN` is one
  name, and three of its four words are its type and its unit. **889 of Society's 1,154
  undefined words were fragments like that**, so the worklist opened with `DDL`, `EXTRAS`,
  `REASON`, `KEYS`, `BYTES`, `CHARS` and buried `witness`, `posture`, `claim` and `probe`
  beneath them (rule 1, in the mirror).

  `Term.only_inside_a_name` is the test, on three conditions and the third is what keeps it
  honest: never the whole name of anything, only ever inside a **constant's** name, and
  **nothing defines it** — a word somebody troubled to define is vocabulary whatever the code
  does with it, which is why this loses no defined term on any corpus. A table's or a way in's
  own fragments are left alone: they were not measured, and a rule that reaches past its
  evidence is a guess. Measured: **59 of 324 defined** against 60 of 1,214, 265 undefined,
  **890 held back**.

  **Held back, never dropped** (design rule 1), and the reason is that the split cannot tell
  `MENSORES_MAX_LEN`'s subject from its unit. The report lists all 890 with the reason, the
  command says how many and where to read them, and the dashboard draws them in a band where
  each says *a word* — one click, persisted per program beside `triage`, with *hold back* on
  the way out. The judgement is offered, not taken.
- `resolve/naming.py` — **the derived lane, and the one place a spelling is judged.**
  `styles_of` returns **every** style a name satisfies rather than the first one tested,
  because for a one-token name several are true at once: `widget` is snake_case, camelCase
  and kebab-case, `DDL` is SCREAMING_SNAKE and PascalCase. Returning one answer meant the
  tie was settled by the order five `if`s happened to be in — Python's order, invisibly,
  in every corpus (**rule 100**). `resolve_styles` lets the population's own unambiguous
  names decide instead, and where a population offers none the stated `PREFERENCE` settles
  it **and the claim says so**. `case_style` survives for a caller holding one name and no
  population, derived from the same set so the two cannot drift (rule 51).

  **A dotted name is a list of names**, judged segment by segment. Substituting `.` for `_`
  asked the question of a string nobody wrote: `apps.desktop.lib.calendar-nav` became
  `apps_desktop_lib_calendar-nav`, which holds both separators and matches nothing, and
  **387 of DunneNote's 389 unreadable module names contain a dash**. `DOTTED_STYLE_PREDICATE`
  is written out beside `STYLE_PREDICATE` rather than produced by patching it — the three
  `str.replace` calls that did the patching touched none of the kebab predicate's substrings,
  so a dotted kebab claim carried a query answering a different question and only DunneNote
  having no module convention kept it off the screen.

  **Spelling is a language's decision, so the case and house-prefix lanes split per
  language** and nothing else does. On DunneFlow's own tree — 107 Python files and 11
  TypeScript — the joint answer was *"routines are named in snake_case, 1,014 of 1,114"*, a
  D with 100 exceptions, all 100 of them TypeScript names spelled the way TypeScript spells
  names; split it is **982 of 998** and **116 of 116**. `languages.read` decides, and a map
  holding one language is measured exactly as it was before: no language in a claim, none in
  a query, and every figure recorded against a single-language corpus still reproduces. The
  affix lane is **deliberately not split** — an affix is a word a team chose rather than a
  way of spelling one. **The privacy lane is split, by what `private` means** in each
  language (`RuleSet.private_means`: *module*, *package* or *surface*, the last not
  measured). It was unsplit while `visibility = 'private'` was a Python spelling nobody else
  recorded; by 2026-11-01 Go, Rust, Kotlin and C++ all recorded it, and pdfcraft's Rust
  "leaked" 624 times under Python's reading, 440 of them `pub(crate)`.

  **A split may not lose a row** (rule 32). `dunneflow` is declared in `pyproject.toml`,
  which no reader claims and which has no row in `files`; scoped by its own file it belonged
  to no language and simply vanished, and the report read *15 commands* over a map holding
  16. A command's language is the language of the code it starts, asked first and the
  declaring file only then.
- `resolve/conformance.py` — **reality against intent**, and the third naming question.
  `naming.py` counts and quotes nobody; `stated.py` quotes and counts nothing; this asks
  whether the program does what a rule says. **The population is never inferred from the
  scope word**, and that is the whole feature. *Measured 2026-09-06, before `--standards`
  existed:* all six of Mensores' `checkable` rules came from a harness standard and **none**
  was a question about `graph.db`. Checked against the graph, *"Files: kebab-case"* is
  **0 of 628** Python files — a catastrophic claim about a rule its own document scopes to
  `src/**/*.md`, three documents. *Retaken 2026-09-08, with a standards directory admitted:*
  **4 checked, 1 no population, 10 not checkable** — `files / kebab-case` from the harness
  standard, and `modules`, `classes` and `constants` from `naming.md` in the standards
  directory, which is what an outside standard was admitted to make possible. So a **path-shaped scope
  requires a declared `paths:`** and is refused without one (rule 49: a plausible population
  is what hides the failure), while an **entity scope** names its own population and a glob
  narrows it. **Three verdicts, never two** — checked, no population here, not checkable —
  because collapsing any two lets *"we could not check"* read as *"it passes"*. Only case
  styles are tested, through `naming.styles_in` so `kebab-case` means one thing (rule 51);
  a template like `NN-kebab-name` is quoted back and declared untestable rather than guessed
  at. It reuses `POPULATIONS` **and `DOTTED`**: taking the first without the second
  reproduced rule 51's own defect exactly, reporting `modules / snake_case` as **1 of 628**
  because a dotted path was read as one identifier.

  **A rule that names no path is measured once per language, and that is not the refusal
  above.** A path-shaped scope is refused because *nothing supplies which paths*; an entity
  scope in a mixed map is the opposite case, because **the map supplies which languages it
  holds** — splitting reads a fact where widening guessed a population. Unsplit, DunneFlow's
  own tree scores *"Functions: snake_case"* at **1,014 of 1,114** with 100 exceptions, every
  one a TypeScript name obeying TypeScript: one number, 91%, made of two answers that are
  98% and 0%. `check_rule` returns a **list** for that reason, and each result carries a
  `blind_spot` — a rule measured against a language its document never mentions is a true
  count of a question nobody may have asked. A standard that declares `paths: ['**/*.py']`
  has closed the axis itself and is never labelled: only the languages that actually hold
  some of the population are split, so one is one.
- `resolve/shape.py` — **the amendment, and the one place it is judged.** `CLAUDE.md`'s
  founding exclusion read *"local variables, arithmetic, control flow"* until 2026-09-07,
  and the rule behind it has not changed: **a loop or a decision is a subject only where
  something *moves* inside it.** A loop that increments a counter is the internal
  computation nobody asked for; a loop that issues one call per item is a **rate**, and a
  rate is flow. A branch whose arms compute different numbers is arithmetic; one where an
  arm writes to a table and another does not is a decision about what leaves the program.
  That test lives here and nowhere else (rule 51) — the worklist, the ribbon and the panes
  all ask this module.

  **Nothing is dropped for failing it** (design rule 1). Three bands, never two: something
  moves · it only calls something of this program · nothing happens here that this map can
  see — and every point carries a `why`, including the ones that pass. It is the 1,230
  loops that move nothing that make the 250 credible.

  **The join is a range, never a relationship.** `boundaries`, `net_calls`, `sql_ops` and
  `calls` each already carry `routine_id` and `line`, so *inside* is
  `line BETWEEN line_start AND line_end` — the inverse of the lookup `web/search.py` does.
  A table joining a loop to a boundary would be a second copy of a fact those two already
  state between them (rule 40).

  **A place is one act; a row is one description of it.** An `INSERT` is a `DATABASE` row
  *and* a `SQL` row on one line, and 569 of Mensores' 991 SQL operations are such a pair —
  so counting rows said *two things move here* about one write, in the sentence that gives
  28 of the 250 rates their number. `places()` is the one place a count is taken; the rows
  stay as the descriptions, and a surface draws a place once, led by the row that says the
  most about it.

  **`in_loop`, and not `depth > 1`.** `depth` counts every enclosing control point, so a
  loop written inside an `if` has depth 2 and is nested in nothing. On Mensores the two
  answers are **98 and 9**, and the nine are the quadratic reaches into the outside world
  this feature exists to find. Filled by a stack sweep per routine, with `depth` breaking
  the one tie lines cannot — `[a for a in [b for b in c]]` is two comprehensions on one
  line.

  **`enclosing()` is the reverse and is `outline` per routine, never a query of its own**
  (rule 51): the judgement, the nesting sweep and `places` are the ones the worklist asks,
  so a point cannot be banded one way at a pane and another way on a page. `nesting()`
  follows `in_loop` and never `depth`. The bound is the routines that touch the thing, and
  the `EXISTS` is a bound on the *work* rather than on the answer (rule 55) — 524 routines
  touch Society's unnamed `FILE` boundary and 389 hold a point around it.

  Measured over Mensores: 211 loops + 39 comprehensions reach a boundary · 470 only call ·
  1,230 move nothing · 78 of 2,213 decisions fork · 69 are ladders of three or more ·
  396 of 1,531 handlers recover by moving something · 3,931 guards · 0 `match`. 105 ms warm
  for all 9,625 points.
- `web/table.py` — **a table, described as the thing it is.** `selectFromNav` fetched the
  routines that touch one and then threw the table away, so the crumb named a table and the
  inspector answered about whichever routine sorted first — `detail.fold`'s defect and
  `plate.py`'s, a third time, in the surface a reader reaches by clicking the busiest thing
  on the cover. It has **no id of its own and none is minted**: `id` is the name the program
  states and `kind: "TABLE"` is what stops a reader taking it for a node id (rule 30).
  `_r_table` serves the specimen *beside* the nodes, because the three doors into that route
  ask two questions — the navigator, the document row and the ribbon want the table
  *selected*, and the inspector wants it *described*. Where it is declared is three answers
  and not two (design rule 21): declared once, declared in more than one file, and never
  declared here — 12 of Society's 65 tables are the third, and only the first can hand the
  source pane a place to open.
- `web/shape.py` — the same facts served twice, for two questions. **`/api/algorithms`** is
  the whole program in five lanes, held on the base and computed on the first ask; each
  lane states its **denominator** (*250 of 1,950*, never *250 loops*) and the page states
  the quiet bands above the list, because four lanes holding 793 of 9,625 points is a claim
  about the other 8,832. **`/api/shape?node=`** is one routine's outline, answered on demand
  and held on nothing (rule 45).

  **The ribbon is a nested outline and not a graph.** Nassi and Shneiderman drew structured
  code in 1972 as nested boxes with **no arrows at all**, because structured code has no
  `goto` to draw and Python source never lost the structure — so there is no control-flow
  graph, no dominator analysis, no layout pass and no library. Guards are drawn *here*, and
  only here: 3,931 refusals are a list of the program on a worklist and the truth about a
  routine in its own shape.

  **`shape` is the mode and `algorithms` is the page**, and the two words are kept apart on
  purpose: `selectFromNav` sets `state.view = state.mode`, so one word for both would make
  selecting a routine land on the worklist — `data-nav`'s defect, which cost a session.

  **`loops_around` is the other direction**, and it is `resolve/shape.enclosing` worded.
  A reader standing at a table asks what loops over them, which is the question the
  Algorithms page puts to a loop, reversed. **The sentence counts loops and states the
  places separately** (rule 32): *3 loops* and *3 writes* are different numbers, and the
  nesting clause states a **depth** rather than a count, because `deepest` is a maximum and
  89 loops with a deepest of 1 may have forty nested ones. The verb is **"reached from
  inside"** and never "written from" — 8 of `worktree_allocations`' 27 operations are reads.

  **The bag is keyed and the renderers read the key.** `SHAPE` carried its node id from the
  day it was written and nothing checked it, so once a reader found one routine it was drawn
  under everything they selected afterwards. Reported by Tom as *"it locks on to whatever was
  viewed last"*. Two halves, and either alone leaves it broken: a renderer must refuse a bag
  about something else, and `ensureShape` must **empty** it rather than return early holding
  the last one. It is invited from `render()` where every route arrives, not from the one
  branch that used to invite it — `followSelectionIntoCode`'s own defect (rule 78).
- `docstore.py` — `docs.db`. **Parallel to the graph, never inside it.** A doc rescan
  never touches `graph.db`, code-only analysis stays cheap, and the corpus stays a
  separately handable artifact — many will hand over a charter and never a line of
  source. The join is one `ATTACH DATABASE` away.

  **It records what a document *says*, never what it is.** `DocSourceStore` in
  `sourcedb.py` holds the bodies in `docsource.db` — the same content-addressed blob store
  as `source.db` with a different `kind` stamp, in its own file for design rule 14's
  reason, and one per program holding every revision. 2,056 bodies for 2,064 paths, 38.7 MB
  of prose in 14.8 MB; the eight duplicates cost nothing. `--no-doc-source` beside
  `--no-source`, separately, because the two travel separately.
- **Document mode is two lanes sharing one pane**, and they are two subjects rather than two
  views of one thing: `documents.py` is prose this tool *generates* about the program,
  `corpus.py` is prose somebody *wrote*. One mount, one subtree cache and one `render()`
  branch serve both, so the cache key carries the lane — a subtree keyed on the other lane's
  page is handed back on a switch, and that looks exactly like a switch that did not work.
  The filter over the 2,064 documents **hides rows rather than rebuilding**: the query is
  deliberately out of the cache key, because rebuilding also destroys the `<input>` being
  typed into and takes the focus with it. A document is **rendered once when it is fetched**,
  never at paint time — parsing is the one cost a subtree cache cannot save. A relative link
  is **checked against the corpus before it is followed** (666 of them, and many point
  outside the scanned tree), and the refusal goes in `docNote`, never `navNote`: that is
  rendered only in the graph HUD, which nobody reading a document is looking at.
- `web/static/prose.js` — **the document renderer**, and the only third-party parser in the
  tool. Its own file because the boundary is `graph.js`'s: it turns text into markup and
  knows nothing about this page, and what it has to say leaves as **data attributes** —
  `data-line` on every block, `data-doclink`, `data-docanchor` — which the shell routes.
  Rendered through `md.parse()` to tokens and never `md.render()`, because the line map is
  the whole reason the library is here: **825 of 825 headings** verified findable in the DOM
  at exactly the line `docs.db` recorded, which is the chain design rule 13 rests on.
  `html: false` is the whole XSS answer; `linkify: false` because in 2,019 plans and research
  notes a great deal of text looks like a URL without being one. **An image is never
  fetched** — an `<img>` fires a request with no click and no consent, out of a tool whose
  posture is deterministic and local (design rule 14) — and a **relative link never keeps its
  href**, because `<a href="./rel.md">` navigates the dashboard away. Chosen from the corpus
  rather than in general: 3,522 external links, 666 relative, 16 anchors, 6 schemes nobody
  can follow, 5 images. **YAML frontmatter is blanked, never removed**: markdown-it parses it
  as a setext heading, 989 of 2,019 documents open with one, and *deleting* the lines would
  shift every `token.map` below by a constant — a page that renders perfectly with every
  number on it wrong. **An HTML comment is lifted out the same way and for a sharper reason:
  `html: false` does not hide one, it un-hides one.** With raw HTML refused, markdown-it
  disables the `html_block` rule *entirely*, so a comment is not a token to catch — it
  arrives as an ordinary paragraph and renders as body prose. 7,317 of them across 505
  documents. They are listed with their lines rather than dropped (design rule 1). Every
  block also carries `data-line-end`, because the lines anybody opens at are mostly **not**
  the first line of a block: a definition sits mid-paragraph, and reaching for the next block
  instead lands one paragraph past what was asked for.
- `web/documents.py` — **lane 2 of Document mode: the map's own eight documents**, and
  `corpus.py` below is lane 1. Close names for different subjects: this is prose the tool
  *generates* about the program, that is the prose somebody *wrote*. Every row carries the
  graph node id that produced it, selected in the same statement as its text — which is the
  whole reason this does not reuse `render/markdown.py`, because linking rendered prose back
  to nodes would mean matching names against the store and rule 5 says how that ends. So a
  row is an **ordinary selection**: the stack lights, the inspector fills, the trail records
  the hop, undo reaches it. A `Section` also declares `table_col` where its rows name a
  declared **table** rather than a node — `DOC_DB_TABLES` selects `NULL AS node` on purpose,
  and selecting a table means selecting the code that reads and writes it. Declared rather
  than inferred from a null id, because *"this row names a table"* and *"this row's node
  could not be resolved"* are different facts that look identical on the wire (rule 30).
  The location column is aliased `AS "where"`, **in quotes** — `where` is a SQL keyword, it
  was `where_` for as long as the family existed, and `Column("where", …)` therefore read
  `None` and rendered the cell blank in **every row of all eight documents**. A guard now
  prepares every statement and asserts each `Column` key is a column it returns.
- `web/corpus.py` — the corpus **served**: `/api/docs`, `/api/doc`, `/api/docsource`. Two
  stores answer together and either can be missing on its own, so there are **four**
  states and not two — never scanned, scanned but not captured, captured but not for the
  version on screen, and captured but not this path — each with its own sentence, because
  they look identical on a blank pane and the thing to do about each is different (design
  rule 21). `revision=None` is a **refusal** from here down, never "the newest": that `None`
  meeting the store's `None` served 2026-08-29's prose under 2026-08-26's headings, which
  is rule 70 one corpus over from where it was first paid for. A document is sent **whole
  and as one string**, unlike `/api/source`'s numbered lines, because a renderer needs
  block structure intact and takes its line numbers from `token.map`.

  `serving()` is the one decision *"can this sidecar serve the version on screen"*, and it
  answers for **both** corpora: its two sentences are arguments with document defaults, so
  `/api/source`, `/api/docsource` and the glossary's capability block share one reading of
  the question and differ only in wording (rule 51).
- **A glossary citation is a *capability* test, not a provenance test.** `senseOpens()` in
  the shell was `s.provenance === "DECLARED_CODE"` for as long as `source.db` was the only
  sidecar, so every documentation-derived definition rendered a dead end and design rule 13
  went unmet for the tier that quotes the program's own words. `/api/glossary` now carries a
  `sidecars` block — one entry per tier, `{opens, reason}` — computed from the live stores
  and the base's two revisions, so the question is *does the corpus this tier quotes have a
  sidecar this base can read*. Deliberately **not per path**: whether the corpus opens is
  what decides whether a button is drawn at all, and a sidecar that holds bodies but not
  *this* path is a fourth state stated by `_span` when the reader asks — pre-empting it
  would be a `held_paths` lookup per citation to grey out a button that already says what
  happened when it is pressed. The block rides on the route rather than in `bind_glossary`
  because the two have different lifetimes: the terms belong to the base, the sidecars to
  the process and to which version is on screen.

  **The two tiers are two routes**, `VIEWER_ROUTE` in the shell, for `_r_docsource`'s
  reason: a `corpus=` parameter with a default is right until somebody omits it. And the
  viewer offers a documentation citation a second reading — *Read it in the document →* —
  because the pane above it is the bytes **as measured**, Markdown syntax and all, which is
  what proves the citation and is not how that sentence was meant to be read. The hop holds
  its line until the paint that has a block to scroll to; `openDocumentAt` returns two
  awaits before there is one.
- `call_args` — what a caller passed, **as written**, hanging off `calls.site_id` rather
  than off a rowid: an argument has to stay attached to its call site across two versions
  of the same program. Sliced out of the file's own text on **byte** offsets (rule 75),
  never re-rendered by `ast.unparse`, and never shortened — one argument on Mensores is a
  1,347-line `frozenset` and is stored whole (rule 8). 43,926 arguments over 30,544 call
  sites. `forget_file` deletes them *through* `calls`, before emptying it.
- `detectors/*.yaml` — **the extension point.** Teaching the tool a new framework is a
  config edit here, not a code change. Prefer adding a rule over adding a branch.

  It also declares what a language *means* where a judgement above the graph has to know —
  `builtins`, which `resolve/traceability.py` strikes out of its evidence, and
  `unawaited_async`, which decides whether dropping an async call is BROKEN or SUSPECT.
  Both were Python's answer given to every corpus until 2026-09-18 (rule 98, twice).

  **One file per language, named by that language's manifest**, plus `annotations.yaml`,
  which belongs to no language and so to all of them — it mines governance markers out of
  comments and prose alike. A language's own rules file is hashed with **its** reader, so
  editing `typescript.yaml` costs a re-read of the TypeScript half and costs Python
  nothing; `annotations.yaml` is in the core key and costs everything. `load_rules` has no
  default and answers three ways — *declared* · *declared none* · *refused* — because
  returning an empty rule set for a file that is missing is a reader that quietly finds
  nothing (rule 49). The glob is the bundle's too: the spec globs this directory rather
  than naming files, or a new language's rules would be left out of the signed application
  and `RulesMissing` would arrive on the first `.ts` file and nowhere else (rule 92).
- `resolve/` — call graph, CLI command trees, flows, naming conventions, glossary.
  **`resolve/<lang>/` holds the name rules and `RESOLVERS` says who answers for which**;
  the driver in `resolve/calls.py` groups by `files.lang`. Two things are hoisted into the
  driver so a new resolver inherits them rather than reimplementing them: the `at_boundary`
  suppression (rule 2), so a boundary row never reaches a resolver at all, and the
  missing-target bookkeeping, so **one place** writes `UPDATE calls SET callee_id` where
  there were three. A resolver returns `Edge` or `NoEdge` and does no arithmetic.

  **A language with no resolver has every call left external and is *named* with its
  count**, which is a shippable state rather than a gap: TypeScript extraction landed a
  chunk before its edges did, and a map with routines, boundaries and SQL and no internal
  edges is honest. **Where a reader's own toolchain names the far end, it is taken rather
  than re-guessed** — `resolve/supplied.py` turns a location into an id for every reader
  that supplies edges, and names none of them (it was `resolve/typescript/calls.py` until Go
  needed the same lookup, and that address now delegates to it). The
  1,935 internal edges DunneNote gained that way are supplied, not inferred: an import
  alias that collides with a local name and a method reached through a typed receiver are
  two cases a name cannot get right (rule 5).

  **`resolve/ipc.py` is the crossing between two languages, and it names neither.** A Tauri
  front end calls a Rust `#[tauri::command]` by sending its *name*, so no reference crosses
  and no resolver can draw it. The server side is facts a reader sent: an `IPC_COMMAND` way
  in for each attributed fn, and an `ipc_registrations` row for each path in a registrar
  (`rust.yaml` `ipc.command_attrs`, `ipc.registrars`). The client side is a declaration:
  `typescript.yaml` `ipc.clients` names `@tauri-apps/api/core`'s `invoke`. A site **sends**
  when it calls that client directly or calls a **carrier**, meaning a routine that hands
  its own first parameter on as a first argument, from a file that imports the client, carried
  further only along CERTAIN edges. DunneNote's 179 sends all go through
  `call(command)` → `active(command)`, a variable, which is why a carrier is judged by what it
  does with its parameter rather than by what it calls. The linker runs at the end of
  `resolve_calls`, so every caller gets it (rule 51), and writes `ipc_links`, one row per site,
  with a status:
  - `linked` (`how = "by name"`, INFERRED);
  - `unknown`, `unregistered` or `ambiguous`;
  - `dynamic`, where the name is not a literal and nothing is guessed;
  - `foreign`, a `plugin:` prefix (`rust.yaml` `ipc.foreign_prefixes`).

  Two applications in one tree are told apart by the registration sharing the longest
  directory run with the site, and a tie links nothing (rule 1). **Rule 2 holds by shape:
  `calls.callee_id` is never written.** Only the walks cross. Every recursive query in
  `store.py` has a second arm over `linked` rows, and `_reach_graph` adds them, except
  `reachable_from_many(cross=False)`, which `render/network.py` uses so that a process zone
  never contains a command another process answers. It surfaces as:
  - `touches` and `impact`, "matched by name";
  - MCP `by_name`;
  - the inspector's `in.by_name` and `out.by_name`;
  - a dashed `IPC` edge in the graph;
  - *About this map*'s "Between languages" row;
  - `08-network.md`'s "Commands called by name";
  - the anomalies UNREGISTERED_COMMAND and UNKNOWN_COMMAND, both SUSPECT.
- `resolve/dispatch.py` — **the bodies a dispatched call may reach** (Tom, 2026-11-02). A
  call a reader marked `dynamic` is resolved to a slot several bodies fill; the reader sends
  each body's location (`SuppliedEdge.answers`, stored as JSON in `supplied_edges.answers`)
  and this module locates them through `supplied.py`'s own index, checks each name, and
  replaces `dispatch_links` whole. It names no language and is not inference: the checker
  named every body. **Rule 2 holds by shape** here too. Every recursive query in `store.py`
  has a third arm over `dispatch_links`, and `_reach_graph` adds them to **both** in-memory
  graphs, `cross=False` included, because dispatch never leaves the process. A writable store
  walks in memory as a read-only one does, its cache stamped with `total_changes`, because
  the recursive query's `(id, depth)` revisits made the arm sixteen times slower there. It
  surfaces as `touches` and `impact` ("by dispatch … may run"), MCP `by_dispatch`, *About
  this map*'s "Dispatch" row and UNREACHABLE's detail, and it is not drawn (BACKLOG 44).
- `render/` — Markdown and Mermaid. **A map needs neither the source tree nor the
  documentation tree**, and saying so cost twenty-eight signatures: `root` and `docs_root`
  were threaded through every renderer and read by none of them, left behind when the nine
  path-stripping copies went with relative paths. That fact is the whole of why
  `render/snapshot.py` can write the map of a sealed snapshot whose tree is gone. The cover
  states **three** instants — the snapshot, when its source was read, and when these
  documents were written — because `analyze` writes a map where the last two are one moment
  and a re-render is where they come apart by a fortnight.
- `web/layout.py` — where things sit, and **how big a thing is drawn on it**. A node's
  radius was a pixel constant and a plate's width a world quantity, so a dot knew nothing
  about the room it had: **4,990 of Society's 10,052 drawn nodes touched a neighbour** at
  the default framing, and the smallest plate was 5.5 px across holding six. The fix is one
  measured fact — the tightest pair on a phyllotaxis disk of `n` points is
  `PHYLLOTAXIS_TIGHTEST * R / sqrt(n)` and that constant is **1.546 at every `n` from 6 to
  4,000** — so a radius can be *chosen* that never overlaps rather than one that usually
  does not. It is in world units now, capped at half the drawn gap to the plate above so a
  node cannot collide with a z-neighbour, and the reader sets the **spacing** (`nodeSize`
  is retired: a derived radius has no slider). Measured through the renderer's own buffers,
  `Graph.separation()`: **0 touching pairs of 2,681,114** under the spiral at every setting;
  0.08% under force, which is the clusters and is left alone deliberately.

  **Both readings are built** (design rule 2): `by plate` is the default and says how sparse
  a plate is as well as a node's degree; `one size` draws the whole stack at **the tightest
  plate's** size — never an average, so every other plate can afford it and the guarantee
  survives the mode change. The ceiling note says something else under one size, because
  there the ceiling is not what binds (rule 32).

  **Drawn nodes and shadows get separate spirals**, and that is what makes the law true. They
  shared one ordered by degree and the two kinds segregate, so the drawn nodes came out in
  contiguous runs at the density of *all* the placed points — `ext:<small outside>` drew six
  nodes from slots 0–2 and 32–34 of 42. A shadow is a device for the third dimension and its
  slot is empty screen space (rule 23); it has no claim on the plate's area budget.

  `DISK_RADIUS` is the width of the **widest**
  plate rather than of every plate; how wide each one is actually drawn is a *view*
  property owned by the renderer, like Z and the spreads, because `phyllotaxis` is radially
  uniform and scaling a plate's coordinates is exactly computing it at a smaller radius.
  Its old note — every disk one size, density carries the information — is rewritten as the
  reversal it is rather than left standing beside code that contradicts it.
- `web/static/forcelayout.js` — **the second layout, and the one `layout.py` has named in
  its own docstring since it was written.** A plate arranged by connection rather than by
  degree: Fruchterman–Reingold per plate, seeded from the spiral, in a WebGPU compute
  shader with a web-worker fallback. **89 ms against 9.7 s**, and 328,531 edge crossings
  down to 27,291 on the busiest plate — **91.7% fewer**. Its own file for `prose.js`'s
  reason: it turns a payload into numbers and touches no DOM.

  **It solves over `payload.edges`, never over the engine's `links`**, and that one line is
  the feature. The model stores every crossing twice, once per plate, each copy ending in a
  shadow — so the payload's edge list is the only place a cross-plate call is expressed as
  a force *within* a plate. `links` is real-to-real and deduped for drawing; solving over
  it would arrange the whole stack as one graph and dissolve the plates. This is what rule
  23 means by *"which is exactly what lets both plates lay out under the same forces"*, and
  the first thing a shadow has ever been asked to do.

  **Every failure here is silent, and three are guarded by name.** `meta` is a reserved
  word in WGSL: the shader failed to compile, the pipeline dispatched, and the stack
  "solved" in 6 ms with the output bit-identical to the input — only counting crossings
  caught it. `layout: "auto"` derives each pipeline's bind-group layout from the bindings
  that entry point uses, so one bind group for both passes is refused asynchronously into
  an error scope nobody popped. So `getCompilationInfo()` is read, the scope is popped and
  thrown on, and a result that moved nothing is refused.

  **The two backends agree on quality, not on coordinates**, and the difference is stated
  rather than smoothed: WGSL may fuse a multiply-add, and a force layout is chaotic enough
  that one last bit is a different arrangement a hundred iterations later. Forcing every JS
  operation through `Math.fround` matched **1.15%** of coordinates and cost tenfold. What
  holds is equivalence — every plate within 0.07% of the same radius, the same 91.7% cut —
  and each backend is bit-identical run to run. The page says which one drew it.

  **The plates are coupled through their shadows**, which is the half rule 23 always
  implied and nothing had ever asked for. Solved plate by plate a shadow pulled its
  borrowing plate and the plate never pulled back — 0.678 plate-radii from the node it
  stood for, against 0.907 for two random points in a disc. Now every slot standing for one
  entity is pulled toward their common middle, so **twice as many cross-plate links stand
  upright** (749 → 1,539 of 5,101) for about a point of the crossing reduction. **The
  residual is the measurement**: a link that stays diagonal is one two plates each want
  somewhere different, and the worst case on Mensores has *two* shadows, not thirty-nine.
  Stated above the picture, and per node on the hover card.

  **The coupling needs one coordinate frame, and that is the whole of why it works.**
  Normalising each plate onto its own middle at its own radius undoes the pull *after* the
  solve, and pulling harder cannot reach past it: snapping every slot onto its group's mean
  every single iteration still left **20 of 5,101** crossings upright. Under one frame the
  count is **3,878 of 5,101**, and all 4,050 entities co-locate to a spread of exactly zero.
  It costs the within-plate reduction, ~90% down to 75–83% — the reader's trade, and Tom's
  call on the numbers. A plate then sits where its contents put it rather than on the axis
  (0.015 plate-widths off at the median, 0.127 at worst), so **the plate's circle is
  reported by the layout** and read by the outline and the rim arrow alike; three
  expressions built on `PLATE_R` had stopped being true (rule 51). The width dial has
  nothing left to say under this layout and says so.

  **The reduction uses a fixed group table and never an atomic**, in two passes — the mean
  taken from positions nothing is writing, then applied. One pass would average a mixture of
  moved and unmoved siblings, decided by whichever invocation ran first, which is
  nondeterminism arriving through a *read*. And **coupling is the one thing a worker cannot
  do**: a group's members are on different plates and so in different workers, so the
  fallback runs in rounds with the consensus between them, on an interval both backends
  share — measured free, so it is chosen for the fallback's benefit.

  **Each plate is normalised to `DISK_RADIUS` and its earned size leaves as a width ratio**,
  which is why `PLATE_R`, `rimPoint` and `fitView` are untouched: they all read one radius
  for every plate, and they still can. The natural sizes reach the picture through the
  plate-width dial that already existed — `diskRatio`, `sqrt(n/nmax)` under the spiral and
  the solver's answer under force. Written into `baseXY`, never `positions`, so the three
  spreads, the width dial and collapsed plates all apply to it untouched and no payload is
  refetched.
- `web/plateorder.py` — **which order to stack the plates in**, so a crossing does not have
  to travel far. The stack ordered by size until 2026-09-08 and **73.3% of Society's 5,101
  cross-plate crossings spanned more than twenty plates** — a line no reader can follow to
  its other end. The force layout made those crossings *upright*; this makes them **short**,
  and the two are orthogonal because uprightness is a fact about X/Y and this moves only Z.

  **It is not the force solver, and that is worth stating because it is the first thing
  anyone asks.** The literal reading was built and measured first — plates as particles on a
  line, springs weighted by shared links, relaxed and ranked, which is `forcelayout.js` one
  dimension over: **-11.3%**. A spring relaxation minimises `sum(w·dz²)` and the question is
  `sum(w·|dz|)`, and the continuous optimum ranks plates in nearly the order it started
  from. Searching the *permutation* directly — weighted minimum linear arrangement, NP-hard
  in general and trivial at 53 plates — gives **-82.8%**: mean crossing height 30.78 → 5.31
  plates, and a third of all crossings landing on the plate next door against 4% before.
  Same evidence as the force solver, different solver.

  **A crossing is counted once**, not once per plate: the model holds every one twice, each
  copy ending in a shadow (rule 23), and the doubling is uniform — so it changes no ordering
  and makes every number printed beside it wrong (rule 32). **Deterministic and seeded**
  from the order the stack uses today, taking the first strict improvement in a fixed
  traversal, because an order the tool cannot defend is not an order (rule 66) — and it is
  never claimed to be optimal, only better by a stated amount than the order it started from.

  **Both variants are built** (design rule 2). Interleaved is the best order and it puts
  `ext:DATABASE` beside `storage` and `ext:STDIO` between `scriba` and `cli`, which reads
  well and overturns what the current default *means*; holding packages above externals
  keeps 31.5% of the saving. Neither is the default: `by size` still is, so this is opt-in
  exactly as the force layout is. The control calls them **"by what they link to"** and
  never *"by connection"* — the plate-layout button already says that about the arrangement
  of nodes *within* a plate, and one phrase for two controls is rule 71 in the reader's
  language.

  Served by `/api/plateorder?level=&minDisk=&grouped=`, on demand and held on the base: a
  second of work that must not be at boot for a reader who never asks, and must not be paid
  again each time somebody toggles between two orders to compare them. Keyed on level,
  threshold *and* grouping, because `minDisk` decides which plates exist and an order names
  plates (rule 81).

  **The control it joins did not order plates.** `state.sortMode` was read only in
  `sortedDisks()`, called only from `renderLegend()`, and the handler never handed the
  engine an order — so *by name* and *by kind* renumbered a legend and left every plate
  where it was, invisibly, because the default very nearly agrees with `defaultOrder`.
  `applyOrder()` is the missing half and is called from the one handler rather than from
  each branch (rule 78).
- `web/graph.py` — the 2.5D model, at **two levels of detail**. `routine` is every thing
  the program declares; `module` folds each file into one node and each boundary kind into
  one, on a single plate below the code. 10,015 nodes and 52 plates become 578 and 38, and
  it is a second way to look at the same facts rather than a filter — nothing is dropped
  and every folded node states what it stands for. The fold happens **on the way in from
  the store**, never over `m.edges`, which holds each crossing twice by design (rule 23);
  `packages.py` wrote that warning down before anything needed it. `MIN_DISK` is per level
  and settable, because what a plate *holds* changes with the level.
- `web/diagram.py` — the compartment, at **two levels**, and **every arrow carries its
  identity and its kind**. A lane is `pair -> Counter[kind]` rather than `pair -> weight`,
  so a TOUCH and a CALL between the same two boxes are one arrow that can say which it is;
  the weight *is* the sum, by construction, so the two cannot disagree (rule 13). `dot()`
  writes `id=` on every edge as well as every node, which is what makes an arrow clickable
  at all. The separator is `=>` and no box id may contain one — asserted over the whole
  program, because the split is on the **first** occurrence and a box id that held one
  would name a box that does not exist. A box is a class, a file's loose
  functions, or a boundary kind; opening one returns a **`Compartment` of routines** — the
  same type, so `dot()` and `mermaid()` draw both and a fix to one is a fix to both. A fold
  is a subject in its own right, never one of the things it folds (rule 74).

  **It has a *colour by* control, and it spends the channel on one thing at a time**
  (design rule 4, one drawing over from the stack's). Its first dimension is **what a box
  does in the flow** — `Compartment.roles()`: receives only, emits only, both, or nothing
  either way. Reported by Tom, who noticed some boxes only ever have arrows in and some
  only ever out. **Four states, not three**: the one nobody names is the largest, 30–44% on
  every corpus measured, and folding it into the others would say something false about a
  third of the drawing (design rule 21). It is the untinted ground, which is also why three
  tints suffice.

  **The role counts flow that crosses out of the compartment**, so it is a fact about the
  program rather than about the `ports` toggle — the same reading `unlinked` has always
  taken, and `role_none` equals it by construction. The cost is stated on the legend rather
  than left to be discovered: with crossings undrawn a box can be coloured with no arrow
  leaving it, and that sentence is dropped the moment they are drawn.

  **It rides into the SVG as a `class`, never a `fillcolor`**, which is what makes the
  control free. Graphviz writes `class=` into the `<g>`, so the browser recolours by
  setting one attribute on the container — no refetch, no second `gv.layout()` on a picture
  that takes 93–179 ms to lay out, and the reader's pan and zoom survive. It also keeps the
  colours in `tokens.css` with every other colour. `mermaid()` is the one place a fill is
  written twice, and deliberately: its whole job is source a reader copies somewhere our
  stylesheet does not exist.

  **A fourth hue was tried and does not exist.** Blue for *receives* against violet for
  *both* is ΔE **1.4** under deuteranopia — the same colour — which is `tokens.css`'s own
  note about the difference channel being at capacity, one channel over. Direction goes on
  blue against amber, the axis dichromacy leaves alone, and *both* is separated by lightness
  and chroma (rule 69's remedy, as `--diff-moved` is). Worst separation **26.1 light, 19.3
  dark** against the shipped difference pair's 12.7 and 9.5, and every tint carries
  `--text` at 7.4:1 or better, because these are fills with a label written across them.
- `/api/flow?from=&to=[&inside=]` — one arrow, opened: every call site with the arguments
  **as written** and the callee's declared parameters, or the SQL and network operations
  for an edge into a boundary. Answered on demand — rule 45 where it belongs, bounded by
  the reader opening one arrow rather than by the picture drawing a hundred. `inside` names
  the fold when the arrow is on the second level and is refused rather than guessed from
  the shape of an id (rule 30). Call sites are **listed, never grouped**: the aggregate is
  the number already on the arrow (rule 32), and never bounded (rule 8).
- **The binding line, and it is on the screen.** An argument is aligned to a parameter only
  where the source settles it — a keyword by name always, a position only when the callee
  is resolved, takes no `*args`, and the receiver question is answered (`self.f(x)` skips
  one; `obj.f(x)` cannot be told from `Cls.f(obj, x)` and so binds nothing). Measured over
  the corpus: **10,668 of 11,570 arguments on a resolved call bind, 92.2%**, and every
  refusal states its reason, because a blank beside an argument reads as *no such
  parameter* — a different and false claim.
- `web/curiosities.py` — **the doorway panel**: twelve measured extrema over the whole
  program, each with **its middle stated**. Every program has a most-commented routine, so
  a maximum alone is a claim nobody can weigh — 1,126 comments against a middle of 3 is a
  discovery, 3 levels of nesting against a middle of 2 is not, and the panel says the
  second as plainly as the first. The list is fixed and complete, so rule 8's bound never
  arises; a measure with nothing to measure is *named* rather than dropped (design rule 1).
  Ordered by distance from the middle. **A curiosity is a measurement, never a judgement**:
  no severity, no blind spot, nothing implying a number ought to be smaller — that is what
  `anomalies.py` is for. One statement per family returns the value, the median, the ties
  and the population *together*, so the query a card offers is not a query about the number
  but the query that returned it (design rule 13), reproducible verbatim through
  `dunneflow query`. Subjects are minted in `threads.py` and nowhere else.
- `web/threads.py` — **adjacency by interest, not by edge.** Five lanes now: `algorithm`
  joined them for ALGORITHMS chunk 5, and it is a kind of its own rather than a second sort
  of boundary thread — the others answer *what else touches the same thing*, this answers
  *what else runs the same shape*. Two routines looping over one table never call each
  other, and two branching on the same written test are coupled through a decision. Both
  new cohort kinds resolve to **exactly the population they counted** (rule 32,
  commit `3cfce1b`): `looped_table` is not `table`, because the figure counts the routines
  that *loop* over a table — 15 on Society against 190 that touch one at all. A decision is
  compared by its header **as written**, which is the whole blind spot and is stated on the
  thread: `x == 1` and `x==1` are two values here. Measured: the table thread fires on 8
  routines of 4,823 and the decision thread on 660, and a thread that fires rarely states
  its own size rather than being dropped (design rule 1). Why a neighbour is worth a
  detour: shares a plan, the other end of a table you write, the most commented routine on
  your plate, named like ninety-eight others. Every thread carries a *subject* the router
  can act on, never a label (rule 30), and states its size so the reader can weigh it.
- `static/tokens.css` — every colour, and the three **colour sets**. A set covers the two
  channels where colour separates one meaning from another — a difference, and severity —
  and carries a light and a dark variant; `data-palette` on `:root` chooses one. In CSS
  rather than in a script because `cssPalette()` already reads the stack's colours off
  these tokens, so a second table would be a second answer. Each set states its contrast
  **and** its separation (rule 69). `--graph-unchanged`, `--graph-unclaimed` and
  `--graph-mixed` sit outside the sets on purpose: a set covers the *directions* of
  difference, and a ground — or "more than one direction" — is not one of them.
- `web/vocabulary.py` — the three naming lanes served, and matched against one name. The
  membership test is `Convention.glob`, which is the same string the exceptions query is
  built from, so the claim and the population cannot drift (rule 41).

  **Derived and stated are two pages, and the word *derived* is why.** A page of conventions
  holding 100% of the time, headed "Naming standard", reads as conformance to a rule somebody
  wrote — which DunneFlow has no evidence for and cannot yet import a standard to get any. So
  *Derived naming standard* counts what the code does, *Stated naming rules* quotes what
  somebody wrote, and they never share a screen a reader could take for a comparison. The
  Markdown report carries both under one title, *as found*, because a document is read top to
  bottom and its two sections announce themselves; a navigator row is read one word at a time.
  Flattening the two under one word would relabel a quotation as an inference, which is what
  the four provenance tiers exist to prevent.

  **The stated lane is read in one place**, `resolve/stated.py`, beside `resolve/naming.py`'s
  Form lane — the query, `StatedRule`, and the `checkable` sentence. It lived beside the
  renderer while the renderer was its only caller (rule 51). `checkable` means the rule *names
  both a class of identifier and a spelling*, so a check could be written; **no check is run**,
  and both surfaces print the one sentence that says so. `scope` and `pattern` were in the
  schema from the day the scanner was written and read by nothing until the stated page drew
  them — a rule that names a spelling and no identifier class is kept with an empty `scope`
  and says which half it is missing (design rule 1).

  **Three absences, three answers** (design rule 21). No documentation was read at all; some
  was read and there was none; documents were read and none of them states a naming rule. They
  arrive as the same empty list, so `read` travels beside the counts — flattening them turns
  *"we did not look"* into *"there is nothing there"*. And *"read it in the document"* is drawn
  only where `/api/stated`'s `corpus` block says `docsource.db` can serve the version on screen,
  which is the glossary's `sidecars` argument one page over: a capability, never a hope.
- `web/changes.py` — the **fact lane**: what a routine does differently, which routines and
  tables and constants each version has, **what a caller passes**, and **what explains it**. `call_args` is
  compared by joining through `calls.site_id` to reach an owner — and `site_id` itself is
  kept *out* of the key, because it carries an ordinal among identical expressions and
  inserting a third `emit()` would renumber every site after it. Arguments are canonicalised
  before being judged different, because they are stored as written (rules 8 and 75) and a
  re-wrapped message is not a change to what a routine does; **constants are not**, because
  `_literal` already unparses them on the way in. Two columns, two answers, and the
  difference is how each is filled rather than what it holds. **Comments are a third
  answer to the same question, and a band of their own.** A leading comment sits above the
  `def` and so outside that routine's `body_hash` — rewritten, it surfaced as `<module>` in
  *edited only* or as *"No differences found"*, depending only on whether the file had
  module-level code. `explained_only` holds what would otherwise be in no band and a routine
  already in one carries a `comments` tag instead, so the four bands stay a partition. They
  are compared **joined in line order and collapsed**, never as written: 86% of Mensores'
  18,731 comment lines live in a run of two or more, and a corpus-wide re-wrap that changes
  no word reports 1,561 false differences as written and none joined. Bounded to the files
  whose `content_hash` differs — 41 ms to 5.2 ms, same answer — which is why it costs
  `/api/changes` nothing measurable (451 → 448 ms).

  **A docstring is the same question from the other side, and it is a tag rather than a
  band.** A comment can sit *outside* a routine's `body_hash` and vanish; a docstring is
  inside the `def` and never does — it lands in *edited only*, the band whose whole claim is
  *internal computation, the one thing this tool exists not to report*. So what is corrected
  is the reason a row gives, not its absence: `docstring` rides beside `comments` and neither
  decides a band. The **canonical form differs from the comment lane's, and the difference is
  measured rather than preferred** — paragraphs are kept. Over Mensores' 3,769 docstrings,
  re-wrapping every one at three widths without altering a word reports 2,060 · 1,652 · 1,602
  as written and **none** under either canonical form; merging every docstring's paragraphs,
  which destroys the separation PEP 257 gives the summary line, is reported by a full
  collapse **not at all** and by the paragraph-preserving form for all 1,996. Same zero on
  the noise, 1,996 more on the signal — which is what chose it.

  **A module docstring is a third subject, and it is a file.** `files.doc` states what a
  module *is* — 619 of Mensores' 628 files — and belongs to no routine. `modules_explained`
  carries a path, because a row must be able to open something (rule 30) and the code
  browser's route already does. Both new lanes together are **+3 ms** (451 → 454, median of
  eight alternating builds on a warm disk), and `_changed_files` is one bound three lanes
  take rather than three copies waiting to disagree.

  **Every list here is ordered by something total, and `_settle` is the one place the
  closer is spelled** (rule 51). `(module, qualname)` and `(module, name)` both look unique
  and neither is: `_identity` mints a second declaration of one name a `#2` id of its own so
  colliding definitions keep separate identities, and a nested class is keyed on
  `module.Outer.Config` while its `name` column says only `Config`. Eight sites ordered on
  those pairs alone until 2026-09-18 — four `ORDER BY`s and four Python `sorted()`s — and
  the four in Python are **rule 105**: their input is a set, so what decided a tie was the
  hash seed rather than the rows, and the reversal probe that gates every other route here
  structurally could not see it. Source order, closed by the id; a position orders and never
  keys, which is this module's own rule.
- `web/filediff.py` — the **text lane** of a comparison, beside `changes.py`'s fact lane.
  The file-level answer costs **no body reads at all**: the sidecar is content-addressed,
  so equal hashes are equal bytes and comparing two path maps *is* the file-level diff.
  That is what makes the expensive lane affordable — `difflib` runs only on a file the
  reader opened, and only where the hashes already say it differs. `autojunk=False`,
  measured rather than preferred (the budget is in `PERFORMANCE.md`).
- `web/search.py` — searching the **text**, which is the one question the graph cannot
  answer: `touches`, `impact` and the glossary search names and meanings, and none of them
  can find a word inside a comment or a string. **Files first** — 626 rows with a count on
  each, never bounded — and one file's lines only when someone opens it, because the margin
  is ten queries a file and a broad word touches 166. One compiled pattern serves both
  passes so the count on a row and the lines beneath it cannot disagree (rule 13). Where a
  hit sits is a line-range lookup, innermost span first; there is no name in the question,
  so rule 5 never arises and rule 10 decides which scope wins.
- `web/code.py` — the code browser. **Links are lookups, never name matches**: `calls`
  already carries `callee_id`, so a clickable name in the source is the resolver's own
  answer. What it does *not* carry is a column, so a call is underlined only where its
  expression occurs exactly once on its line and goes to the margin otherwise — inventing a
  column is inventing a position (rule 1).
- `sourcedb.py` — `WORKING` is a **state**, not an id; a revision is identified by when it
  was captured. `seal()` keeps the current snapshot under its own name so the next capture
  is a second one rather than a replacement. Nothing reads a second revision yet.
- `sql.py` — reads schemas out of the `CREATE TABLE` statements the code contains.

