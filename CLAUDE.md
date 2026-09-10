# DunneFlow

Maps what moves through a program: where it starts, what it runs, what it touches, and
why. Built for a reader who reads code but does not write it, and who thinks in
entrypoints, flows, routines, and boundaries.

**New here? Read `BRIEFING.md` first** — where the code lives, what is built, what we are
doing now, and which decisions are closed. This file is the standing orders; `HANDOFF.md`
is the chronological record.

The rules moved out of this file when it outgrew what a session can carry, and the split is
by *how often you need it*, not by importance:

| File | What it holds | When to read it |
|---|---|---|
| `CLAUDE.md` | commands, verification gates, architecture, and the **index** of every rule | every session — it is loaded for you |
| `RULES.md` | the 90 engineering rules **in full**, with the false result each came from — numbered to 91, because 21 does not exist and the numbers are addresses | before working in the area a rule governs |
| `DESIGN-RULES.md` | the 30 dashboard design rules in full | before building or changing a view |
| `PERFORMANCE.md` | every measured figure, with its budget and its conditions | before quoting or retaking a number |
| `BRIEFING.md` | state: what is built, what is next, what is closed | at the start of a session |
| `HANDOFF.md` | the full chronological record, session by session | when you need why something is the way it is |

A rule is cited as a bare number — "rule 45", "design rule 19" — from code comments, tests
and both records; **3,132** such citations across `src/` and `tests/` as of 2026-09-09 —
2,326 to the engineering rules and 806 to the design ones, over 124 files. `RULES.md` carries
the command that counts them, because the first retake gave two different answers in two
shells. **The numbers are
addresses. Never reuse one, never renumber, never close a gap.**

## What this tool is for

A program is started, fed inputs at its boundary, pulls more from its environment
through listeners, moves things through internal routines, and pushes results back out.
**What moves is the subject. Internal computation is not.**

Deliberately *not* reported: local variables, arithmetic, and private helpers that
neither touch a boundary nor sit on a path to one. Leaving those out is most of what
makes the output readable — do not "improve" the tool by adding them.

**Control flow was on that list until 2026-09-07, and the amendment is narrow.** A loop
or a decision is a subject **only where something moves inside it**: a loop that
increments a counter is still the internal computation nobody asked for, a loop that
issues one network call per item is a *rate*, and a rate is flow. What is recorded is a
span — routine, line range, depth, arms, and the header as written — and never a
variable, an operator or a value. See `resolve/shape.py`, which is the one place that
judgement is made.

The goal is **comprehension, not documentation**. Judge a change by whether it helps
someone orient in an unfamiliar codebase, not by how many pages it emits.

## Commands

```bash
uv run dunneflow analyze  <path> --name <program>   # extract, resolve, write the map
uv run dunneflow touches  <path> --routine <name>   # what does this reach?
uv run dunneflow impact   <path> --routine <name>   # what breaks if I change it?
uv run dunneflow glossary <path>                    # what its words mean, and who says so
uv run dunneflow naming   <path>                    # the naming standard as found: derived, and quoted
uv run dunneflow mirror   <path>                    # words the docs define that the code never uses
uv run dunneflow query    <path> --sql "..."        # ask the graph directly
uv run dunneflow migrate  <dir>                     # stored paths: absolute -> relative
uv run dunneflow render   <dir> [--revision <rev>]  # a snapshot's map, from the graph it has
uv run dunneflow serve    [dir] [--revision <rev>]  # the dashboard; a program, a root, or neither
uv run dunneflow analyze  <path> --standards <dir>  # measure it against somebody else's rules
```

`analyze --progress-json` reports one JSON object per line on stdout instead of the summary,
which is how `serve` runs it. See the `serve` section below.

**`serve` takes a program, an output root, or nothing at all**, and tells the two apart by
the same question `analyze` asks to keep a program's own output out of its own corpus:
*does this directory hold a map*. Never by name — `output/` is a fine name for a directory
of hand-written prose (rule 30). Handed a root with nothing open it **serves the start
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

`POST /api/pickdir` runs `osascript` for a folder, because `analysis.check` refuses a
relative path and a browser cannot hand a server what a picker chose. `activate` comes first
— the dialog belongs to a process with no window, and without it the panel opens *behind*
the browser (rule 90, one process over). The typed field stays, always: the picker is a
convenience over a control that still works (design rule 2). `POST /api/reveal` opens the
root in the Finder and is bounded to it, which is the answer to the one cost of
`~/Library/Application Support` — the correct place for an application's data, never swept
into iCloud Drive, and invisible to a reader who wants to hand a colleague a map (rule 89).

## Packaging — the frozen application

```bash
uv run pyinstaller packaging/dunneflow.spec --noconfirm    # → dist/DunneFlow.app (31 MB)
```

That is the **development** build: this machine's architecture, ad-hoc signed, seven seconds.
A **release** is `packaging/release.sh`, one verb per step so any of them can be run alone:

```bash
./packaging/release.sh venv      # the universal2 build environment
./packaging/release.sh build     # DUNNEFLOW_ARCH=universal2 — arm64 and x86_64
./packaging/release.sh sign      # Developer ID, hardened runtime, secure timestamp
./packaging/release.sh notarize   # submit the .app, wait, staple it
./packaging/release.sh dmg       # build, sign, notarise and staple DunneFlow-<version>.dmg
./packaging/release.sh verify    # architectures, signature, Gatekeeper, staple
./packaging/release.sh install   # ditto the stapled .app into /Applications
./packaging/release.sh all
```

**`DUNNEFLOW_ARCH` has two answers and no third**, and the spec **refuses rather than falling
back** (rule 49): asked for `universal2` under an interpreter that cannot produce one it raises
and names both. A universal build that quietly came out arm64 would sign, notarise and ship,
and be found by a colleague on an Intel Mac rather than here.

**A universal build needs a universal interpreter, and it cannot be uv's.** uv's managed
Pythons and Homebrew's are single-arch by construction; python-build-standalone ships no
universal2 build at all. `python-3.12.10-macos11.pkg` from python.org is the last universal2
3.12 — 3.12.11 is source-only — and `release.sh venv` builds `.venv-universal` from it. It is a
build-only interpreter and disturbs neither uv nor the project environment.

**PyYAML's C extension is dropped from the bundle**, `excludes = ["yaml.cyaml", "yaml._yaml"]`,
and both names are needed: excluding the extension alone leaves `yaml.cyaml` importing something
that is not there, which is an `ImportError` where `yaml/__init__.py` has a fallback. It is the
one file in the bundle that cannot be built for both architectures — **PyPI has no universal2
PyYAML wheel for any version** — and it is never used: every call site here is `yaml.safe_load`,
which is the pure-Python `SafeLoader` whatever `_yaml` does. `test_frozen.py` holds both halves,
reading the *syntax* rather than the text, because this file's own explanation of the rule
contains every word a scan would look for (rule 34).

**`packaging/entitlements.plist` asks for nothing, and that is the measurement.** Every
PyInstaller guide carries the same four entitlements copied from each other, and none is
indicated: the picker spawns `/usr/bin/osascript`, whose `activate` and `choose folder` run
inside osascript itself so no Apple Event leaves this process; CPython 3.12 has no JIT and
nothing builds a ctypes closure; and every Mach-O file in the bundle is signed by the identity
that signs the bundle, so library validation has nothing to refuse. **Pressed rather than
assumed**: `POST /api/pickdir` against the signed app in `/Applications` spawned osascript as a
child and held the dialog open, with nothing denied in the AMFI log. A key added there needs the
failure that earned it recorded beside it. The file's own XML is stricter than most — a comment
before the `DOCTYPE`, or a double hyphen inside one, is `AMFIUnserializeXML: syntax error`, and
both were paid for.

**The Dock presence is bought without spending one, and that is why it is shaped as it is.**
`macapp.py` calls AppKit through `ctypes` so the application registers with the window server
— the frozen app showed a Dock icon with **no running indicator**, and `lsappinfo` named the
cause exactly: `type="Foreground"` but `!cgsConnection`, because a command line tool in a
bundle never touches AppKit. `LSBackgroundOnly` was already false; the plist was never it.
Every call is *out* to a function that already exists, so `allow-unsigned-executable-memory`
stays unnecessary — which is what rules out an `NSApplicationDelegate`, since defining an
Objective-C class with Python methods is precisely that closure. Quit is `NSApplication`'s own
default handling of the quit Apple Event, so ⌘Q and Dock → Quit work with no delegate at all;
the one-line version that only connects would have given a dot and an application nobody could
quit. `tests/test_frozen.py` asserts the module contains no `CFUNCTYPE`, so the claim above
cannot quietly stop being true. Measured on the Developer ID build with `flags=0x10000(runtime)`
and the dictionary empty: registers, serves, quits, nothing denied in the AMFI log.

**Nothing uses `codesign --deep`.** Apple deprecates it and it applies the *outer* bundle's
entitlements to everything nested, which is the opposite of what an empty entitlements file is
for. Every Mach-O file is found — never listed, so a dependency's dylib cannot arrive ad-hoc
signed inside a Developer ID bundle — and signed on its own, deepest first, the bundle last.
The `.app` is notarised and stapled **before** the `.dmg` is built, and the image is notarised
and stapled in its own right: a stapled image alone leaves the dragged-out app needing a network
round trip on first launch, and a reader opening an unfamiliar tool offline is the case this has
to survive.

**Four questions have two answers, and `runtime.py` is the only place either is given**
(rule 51): am I frozen, where do my files live, where do maps go, and how do I run myself.
Every one of them was `Path(__file__)` or a spelled-out `sys.executable` somewhere, and
frozen each is wrong in a different way. A fifth — *what does an application look like on
this operating system* — is `macapp.py` rather than a fifth branch here, because it is one
long macOS-only answer read by `serve` alone, and `runtime` stays four short ones read by
everything.

* **`resource_root()` keeps `dunneflow` as its last segment in both worlds**, and that is
  load-bearing rather than tidy. `fingerprint_files` labels every input relative to it, so
  the binary and the checkout agree on a fingerprint at the same commit — measured: the
  binary stamps `extractor = 9:e8c9ac8a851c41b7`, which is the checkout's, and the checkout
  opens the binary's maps. Laid out any other way the two builds refuse each other's maps
  under rule 12, which is the opposite of what that rule is for. A build-time constant was
  considered and rejected for exactly that.
* **`fingerprint_files` refuses an empty input and a named-but-absent one**, each with its
  own sentence. A hash of nothing is `e3b0c44298fc1c14` and looks exactly like a
  fingerprint; a `Path(__file__)` that is not a file raises `FileNotFoundError` from inside
  a hash. `RulesMissing` is the class, and it is always a build defect.
* **`multiprocessing.freeze_support()` is the first statement of both entry points.** macOS
  spawns, so a frozen pool worker re-executes *the application* — sixteen more servers, or
  sixteen more analyses. `walk.py`'s serial fallback cannot catch it: nothing in the parent
  raises, because the parent is fine and the children are the program.
* **`self_argv()`** is how the analysis subprocess runs this same build. `-m dunneflow.cli`
  means nothing to a binary, and that would have broken **+ Analyze a directory…** on the
  one build where it is the only way in.
* **`default_output_root()`** is `./output` from a checkout and, frozen, **whatever the
  reader chose** — `platform_output_root()` when they have not. That platform answer is
  `~/Library/Application Support/DunneFlow` and never `~/Documents`: `source.db` holds the
  private source of whatever was read, and Documents is swept into iCloud Drive on a
  signed-in Mac — egress by accident, out of a tool whose posture is deterministic and local
  (design rule 14). `serve` **creates it only when nobody named a directory**; one the
  reader typed is never created, because a mistyped path would otherwise become a new empty
  root reporting no programs in a place they have never used (rule 49).
* **The root moves, and a one-line pointer at `<platform root>/root` remembers where.**
  Maps are not small and Application Support is on the boot disk, so `Move…` on the start
  page re-points and optionally carries the existing programs across (`web/roots.py`,
  `POST /api/root`) — copy every program, verify every copy, and only then delete, so a
  failure leaves the originals untouched and takes the partial copies with it.
  **Three states, never two**: no pointer, one that resolves, and one naming a disk that is
  not connected. The third **raises** `MapsRootGone`, and the reason is `cmd_serve`'s
  `mkdir(parents=True)`: `/Volumes` is an ordinary directory *on the boot disk*, so a
  pointer's target that got created would put a new empty maps root on precisely the drive
  the reader was clearing, and then report no programs in it (rule 49). **A pointer's target
  is never created.** `serve` falls back to the platform root and *says so* — on the terminal
  and in a banner on the start page, because a stated substitution is recoverable and a
  silent one is the failure. And **a checkout never reads or writes it**: the two worlds share
  a home directory, and a checkout that stamped the pointer once sent the packaged
  application to a scratchpad that no longer existed.

`packaging/dunneflow.spec` bundles as **data** everything something reads as a *file*: the
rules (loaded as YAML) and the detectors' loader plus both extractor trees (**hashed**, not
imported — rule 12 puts the reader in the key), `web/static`, `web/vendor`, and
`copy_metadata('dunneflow')` so `tool_version()` needs no frozen branch. Destination
`dunneflow/…`, per `resource_root()`. `packaging/dunneflow_app.py` defaults a bare argv to
`serve` — the **application's** decision, not the CLI's, which keeps its usage message.

**The 1,363 tests prove the source tree, not the artifact**, so the ground truth is run
*through the binary*. Taken 2026-09-09 on `../society-2026-08-29/src` with
`--standards ../dunnecorp-standards`, 628 files in **37.7 s**: the four executables at
**1,381 · 423 · 292 · 112**, `naming.md` byte-identical to the `CORP` fixture with its three
rules in the checked lane, the research paper yielding **zero** naming rules, and the
conformance verdicts at **4 checked · 1 no population · 10 not checkable**.

**Signing is done and notarisation waits on two things only Tom can do.** The identity is
`Developer ID Application: Thomas Williams (G3RLJWV327)`, and a signed build reports
`flags=0x10000(runtime)`, the full Apple authority chain and a secure timestamp. Gatekeeper's
answer is then *"rejected — source=Unnotarized Developer ID"*, which is honest rather than
broken: notarisation is a round trip to Apple and needs credentials. The two once-only steps,
both recorded in `packaging/release.sh`'s own header:

```bash
curl -LO https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg
sudo installer -pkg python-3.12.10-macos11.pkg -target /       # the universal2 interpreter

xcrun notarytool store-credentials dunneflow \
    --key ~/.appstoreconnect/AuthKey_XXXXXXXXXX.p8 \
    --key-id XXXXXXXXXX --issuer <issuer-uuid>                 # from App Store Connect
```

After that the key, its id and the issuer id are the keychain's business; `release.sh` knows
only the profile name. Still to do: **notarisation** (the credentials), the **universal build**
(the interpreter), an **icon** — `icon=None` in the spec — and **Windows**.

**`serve` also *makes* a program.** The `<select>`'s last option, `+ Analyze a directory…`,
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
* **`claim_analysis` asks `poll()`, not `state == "working"`** (rule 30). A watcher that dies
  without noting used to leave that label true for ever; the stale lock is now cleared rather
  than left for somebody to notice. This is the *"or locked"* half.
* **The child gets its own session and the signal goes to the group.** `analyze` runs a
  `ProcessPoolExecutor` whose workers inherit the pipes: signalling the parent alone left
  **eleven workers** holding stdout open, so `run`'s read loop never returned and the report
  said `working` over a child that had gone — the very jam, arriving through the fix for it.
* A stopped run is `state: "stopped"`, **not `failed`** — the reader did it on purpose, and a
  negative exit code is the child's own evidence rather than a flag set from outside (rule 13).

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

## Verification — run before marking anything complete

```bash
uv run pytest        # all tests
uv run mypy .        # src must be clean
uv run ruff check .  # must pass
```

And when anything under `runtime.py`, `packaging/`, `detectors/` or `extractors/` has
moved, **through the binary as well as beside it** — the tests prove the source tree and
not the artifact:

```bash
uv run pyinstaller packaging/dunneflow.spec --noconfirm
dist/DunneFlow.app/Contents/MacOS/dunneflow analyze <tree> --name x --output <tmp>
```

The one check that is not a ground-truth number: the `extractor` the binary stamps must
equal the checkout's `rules_fingerprint()`, or the two builds have stopped being able to
read each other's maps (rule 12, and see **Packaging**).

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

### Performance budgets — `PERFORMANCE.md`

Every measured figure lives there: analysis, the interactive map, the dashboard's panes,
the change worklist, search, and the documentation scan, each with the budget it was taken
against. **A cold row is the external volume and nothing else**, and a row states its
conditions where they are load-bearing — retaking one without reproducing those is a
different measurement under the same label (rule 24).

## Architecture

```
source ──► extract ──► graph.db (SQLite) ──► resolve ──► render
           per file,    the one source                   Markdown + Mermaid
           parallel,     of truth                        ▲
           hash-cached                                   │
docs   ──► extract ──► docs.db  (SQLite) ──────────ATTACH┘
           per file,    a parallel store, never
           parallel,    the same one
           stat-gated
```

- `runtime.py` — **what this build is and where it lives**, and the only place any of it
  is answered (rule 51). Four questions with two answers each — frozen or not, where my
  files are, where maps go, how to run myself again — and every one of them used to be a
  `Path(__file__)` or a hand-written `sys.executable` in whichever module needed it. See
  **Packaging** above; the layout of `resource_root()` is what makes a binary's map and a
  checkout's map the same map.
- `schema.py` — the fact contract. Every extractor, in any language, emits these types.
  A **call site has an identity** (`call_site_id`) and carries the arguments the caller
  wrote (`CallArg`), because two identical expressions in one routine are two calls and
  the arguments of one must not land on the other — 287 such pairs on Mensores. The id
  holds no position, like every other id here: an ordinal among identical expressions in
  the same caller, with the residue stated in the docstring rather than hidden.
- `store.py` — SQLite. **The spine, not an export format.** Nothing holds the whole
  program in memory; reachability is recursive SQL over indexed edges. This is the one
  decision that lets the tool survive growth — do not replace it with in-memory graphs.
- `extractors/python/` — stdlib `ast` + `tokenize` only. No third-party parser.
- `canonical/` — whether two writings are **the same expression**, one module per language.
  Beside the extractors rather than inside one, and that placement is load-bearing:
  `code_extraction_inputs()` globs `extractors/python/*.py` into the cache key, so a
  canonicaliser living there would discard every graph on the machine — sealed snapshots
  included — each time it was edited, for a module extraction never reads and that cannot
  change one fact. A language with no entry compares its expressions as written.
- `extractors/docs/` — Markdown, reStructuredText and plain text, scanned by hand for
  the same reason: no markdown library. Emits `DocFacts`.

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
  styles are tested, through `naming.case_style` so `kebab-case` means one thing (rule 51);
  a template like `NN-kebab-name` is quoted back and declared untestable rather than guessed
  at. It reuses `POPULATIONS` **and `DOTTED`**: taking the first without the second
  reproduced rule 51's own defect exactly, reporting `modules / snake_case` as **1 of 628**
  because a dotted path was read as one identifier.
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
- `resolve/` — call graph, CLI command trees, flows, naming conventions, glossary.
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
- `web/curiosities.py` — **the doorway panel**: ten measured extrema over the whole
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
- `web/filediff.py` — the **text lane** of a comparison, beside `changes.py`'s fact lane.
  The file-level answer costs **no body reads at all**: the sidecar is content-addressed,
  so equal hashes are equal bytes and comparing two path maps *is* the file-level diff.
  That is what makes the expensive lane affordable — `difflib` runs only on a file the
  reader opened, and only where the hashes already say it differs. `autojunk=False`,
  measured rather than preferred (see the budget below).
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

## Rules learned the hard way

These each came from a false result on real code. Keep them.

*There is no engineering rule 21, and nothing is missing.* The numbers are cited from code
comments, tests and `HANDOFF.md`, so they are addresses rather than an ordering and are
never reused or closed up. Every "design rule 21" in the codebase refers to the dashboard
rule of that number — a blank canvas must say why it is blank — which does exist.

**The index is below; the rules themselves are in `RULES.md`.** A title is the rule and is
enough to recognise that one applies — it is not enough to apply it. **Read the body before
working in the area it governs**, because every one of these was, at the time, the obvious
thing to do, and the title alone will let you agree with a rule and reimplement the defect
it was written from.

```
  1. Precision beats recall.
  2. A call that touches a boundary is never also an internal edge.
  3. Builtins never resolve to local routines.
  4. Names imported from outside the program stay outside it.
  5. Never match on a bare common method name.
  6. Mark confidence honestly.
  7. Registration is not always a decorator.
  8. Bound every diagram — and only a diagram.
  9. Documentation is never code.
 10. A nested function must carry its enclosing scope in its qualname.
 11. Follow base classes when resolving `self.x`.
 12. A fenced block is code, not prose — rule 9 in the mirror.
 13. A claim's query must return exactly what is printed beside it.
 14. With thousands of tests, agreement is expected.
 15. A branch that consumes lines must offer them to every detector that wants them.
 16. Never open a database as the wrong kind.
 17. A program names its files, and those names are vocabulary.
 18. Every comment must land on something, and the module scope owns what no function
     does.
 19. A constant is a name, and a `Literal` alias is an enum.
 20. A read may refuse, but it may never repair.
 22. A node is a billboard, not a disc.
 23. A shadow is never drawn, and never an endpoint. The crossings are the point.
 24. A measurement must measure the thing it names.
 25. The one store that is not derived must never be discarded.
 26. External is not inferred.
 27. A marker counts only where it touches.
 28. A `rem` inside `@media` is not the page's `rem`.
 29. A media query contributes no specificity, so equal selectors go to source order.
 30. A label is not an identity.
 31. A shadow is never an endpoint — when *reading* an edge as much as when drawing one.
 32. A count must say what it counts.
 33. A trail step must carry its subject, or the trail cannot take anyone back.
 34. Pinned data hides in prose, and that is the hiding place the guards missed.
 35. A `let X = []` that nothing assigns is an empty view with no symptom.
 36. A generic loop narrowed to a literal is how a feature disappears without a trace.
 37. A guard that checks a name appears has not checked that anything happens.
 38. An instrument that cannot see cannot report.
 39. A plausible diagnosis of a real symptom is still a guess, and this one named the
     wrong plane for two sessions.
 40. Two detectors recording one act is two numbers about one thing.
 41. A prose claim and a machine-readable population are two things, and only one of
     them can be asked a question.
 42. A guard that names the right case may still not catch it.
 43. A check that cries wolf has already failed, and it fails silently.
 44. A live control reading a field the server does not send renders nothing and throws
     nothing.
 45. Hidden is not absent, and the difference is the whole bill.
 46. An opening rule that names a position breaks exactly as an ordering one does.
 47. Dimming says what is not yours; it does not say which one is.
 48. A scripted click proves the handler; only a pointer proves the path to it.
 49. A fallback that yields a plausible value has hidden the failure it was written for.
 50. A scroller is the element that scrolls, not the one that declares `overflow`.
 51. A rule kept at a call site rots as callers are added; move it to where they all
     pass.
 52. A cache that takes a value has already done the work it exists to avoid.
 53. A layout bounded by arithmetic is right at one window size.
 54. A guard that names the wrong container has not guarded anything, and the container
     is usually the generated one.
 55. A bound must be on the work, not only on the answer.
 56. A file restored to disk is not a module restored to memory.
 57. Admitting a directory for its documents must not admit a copy of the program.
 58. A second read-only handle to a database this process already holds open is 36x
     slower, and it is only slow while the tool is doing its job.
 59. A mutation harness must prove its baseline is green, or every mutation reads as
     caught.
 60. A stored path is a key before it is a location, and an absolute one is a bad key.
 61. A second way into the store must obey the rule the first one was taught.
 62. A migration may re-stamp the fingerprint it satisfies, and only that one.
 63. A store's reader must read the columns that exist, not the ones this version of the
     code knows about.
 64. The leaf that identifies a tree is the package root's, not the analysed
     directory's.
 65. Name a set for where it is, not for what befell it.
 66. An order the tool cannot defend is not an order.
 67. A control's value is state, and the browser will supply one if you do not.
 68. A restore is a setter, and it must do what the setter does.
 69. Contrast says whether a colour can be *read*; it says nothing about whether two
     colours can be told *apart*.
 70. The version on screen decides which bytes, and the sidecar cannot know which that
     is.
 71. A class name is global, and a stylesheet gives no warning.
 72. A gesture's target is not what is under the pointer, and an instrument that cannot
     reproduce that reports its absence just as confidently.
 73. A picture must not move under a gesture, and identity is what survives when it
     does.
 74. A fold is not one of the things it folds.
 75. A column offset is a *byte* offset, and a character slice is silently short.
 76. An echo is not an act, and the engine cannot tell you which it is sending.
 77. A synthetic subject is minted on a condition, so it cannot carry a fact that does
     not share it.
 78. A pane brought up to date by the control that moved it is only as correct as the
     last person to add a control.
 79. A lifetime change is an access-pattern change.
 80. A job that can be interrupted must leave something that cannot be mistaken for
     a finished one.
 81. A key that decides whether to skip work must carry everything the work depends on.
 82. A long job is not a switch — a slot names what is being replaced, not what is
     running.
 83. An instrument's two coordinate systems can differ, and the one you can see is not
     the one you touch.
 84. A grid does not overflow, it grows a row.
 85. A span cannot tell what a loop is over from what it does.
 86. A guard can only see that a function was called, never what it returned.
 87. A derivation from the picture is only as available as the picture.
 88. A rebuild recipe must name every store the change invalidates, including the ones
     nothing else mentions.
 89. A refusal must name a command that can act on the thing it is refusing, and the
     sentence has to be readable off whatever decides that.
 90. An instrument's pointer lands on the window in front, not on the tab you addressed —
     and every other instruction still reaches the right one.
 91. A sentence written for a reader has to fit the channel it is put in, and a channel
     that is narrower than prose will not say so.
```

## Anomalies: the discipline

`anomalies.py` reports what looks wrong. It exists under one rule:

> **Every finding must state what would make it a false alarm.**

This is not politeness. On the first run against a live codebase, *six confident
findings in a row were defects in this tool*, not in the program being read. A
finding without its `blind_spot` is a guess wearing a uniform.

- **Severity** (BROKEN / SUSPECT / INFO) says what it would mean for the program.
- **Confidence** (CERTAIN / PROBABLE / POSSIBLE) says how sure the tool is.
- These are different questions. Never blur them.

Ingest must never fail on a broken program: unparseable files yield recorded errors,
colliding definitions keep separate identities, and an edge lost to ambiguity is
recorded as `LOST_EDGE` rather than silently omitted — a missing connection must be
visible, or a broken program documents as a smaller working one.

`dunneflow check` exits non-zero only on BROKEN, so it can gate CI.

**Before adding a detector**, verify a sample of its findings against real source. If
the first thing it reports is a limitation of DunneFlow, fix the limitation instead of
shipping the detector.

## Dashboard: design rules

A reading tool for someone orienting in code they did not write. Settled shape: a local
server (`dunneflow serve`), three panes — navigator, centre view, inspector — where the
centre pane is a mode toggle (graph / table / document) over one shared selection, not
three destinations. **Vanilla JS + deck.gl, served by `http.server`** — no framework, no
Node at runtime or build, deck.gl vendored into `web/vendor/`.

*Astro 5 + Tailwind 4 was ratified here and has been struck, on evidence.* It was chosen
before the graph became the defining requirement and before the ratified mockup turned
out to be vanilla with a hand-authored 832-line token stylesheet and no Tailwind at all.
The graph must be WebGL whichever stack wins, so Astro bought a build step and Tailwind
bought a rewrite of settled CSS, neither of which serves the thing the tool is for.

**The index is below; the rules themselves are in `DESIGN-RULES.md`.** Several exist only
as reasoning — what was tried, what it cost, and why the obvious alternative was rejected —
so read the body before building against one.

```
  1. No filter is ever silent.
  2. When two options are genuinely interchangeable, build both and make it a Setting.
  3. Everything dimensional is stored in `rem`, never `px`.
  4. Colour is the scarcest channel; spend it on one dimension at a time.
  5. Confidence is shape, not colour.
  6. Customisation is clamped, and says why.
  7. Accessibility limits are documented in the product, not apologised for.
  8. A program is never alone.
  9. The anomaly view is a worklist, not a report.
 10. Documentation is evidence, even though it is never code.
 11. Documentation and source are equal inputs; neither may be assumed present.
 12. A cached graph is valid only if the source AND the tool that read it are unchanged.
 13. Every reported meaning must carry its provenance, and the provenance must open.
 14. Deterministic by default; egress is scoped, never a switch.
 15. Build for the explorer, not only the navigator.
 16. A control that renders but is wired to nothing looks exactly like one that works.
 17. View state is local, and exported deliberately.
 18. The stack is an abstraction, not an object — so do not draw it.
 19. Edges are shown on demand, never by default.
 20. Frame the bounding cylinder at the tilt in force, and always offer a way back.
 21. A blank canvas must say why it is blank.
 22. Spread is three axes, and the fourth control is zoom.
 23. Hiding and collapsing are separate switches.
 24. A pane collapses to a rail, and the rail says which pane it is.
 25. The primary way in is a pane, not furniture.
 26. The list and the picture are one instrument, and it has to run both ways.
 27. A container's affordance drowns out the affordances inside it, because it wins on
     area.
 28. Inference is voluntary and secondary, and a map states whether any was used.
 29. A hidden control is not a dimmed one.
 30. A dimmed control still acts.
```

## Adding a language

Write one extractor that emits `FileFacts`. Nothing else changes — the resolver,
renderers, and orientation queries know nothing about any specific language. Swift is
the obvious next one.

## Shared library: dunnecorp-shared

This project consumes `github.com/aacloudguy/dunnecorp-shared`, DunneCorp's
shared library of code, Claude Code skills, governance templates, and CI
patterns.

**Before writing any new utility, helper, workflow, skill, or template, check
whether it already exists there.** The library exists specifically because the
same concepts were being rebuilt independently in each repository.

How to check, in order:

1. Read `catalog.json` in the shared library and match the task against the
   `use_when` field of each asset.
2. If an asset matches, use it. Add the dependency rather than reimplementing.
3. If something close but not exact exists, prefer extending it in the shared
   library (via a PR there) over writing a local variant here.
4. Only write something new here when nothing comparable exists, or when the
   need is genuinely specific to this project.

If the library is not checked out locally, read the catalog directly:

```bash
gh api repos/aacloudguy/dunnecorp-shared/contents/catalog.json \
  --jq '.content' | base64 -d
```

A local checkout exists at `../SharedCode`.

### Contributing back

If you build something here that is reusable, it belongs in the shared library.
Open a PR against `dunnecorp-shared` following its `CONTRIBUTING.md`: add the
asset, register it in `catalog.json` with a `use_when` trigger, and include the
required ADR/CMR record. Then depend on the new tag from here.

DunneFlow itself is a candidate for `packages/python/` once it settles.
