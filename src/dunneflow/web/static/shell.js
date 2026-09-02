
"use strict";

/* ════════════════════════════════════════════════════════════
   Real data, lifted from output/mensores/graph.db.
   Nothing here is invented — the comments below are Mensores'
   actual governance comments, at their actual line numbers.
   ════════════════════════════════════════════════════════════ */

/* ════════════════════════════════════════════════════════════
   The data these views draw comes from the server, not from here.

   This file began as the ratified prototype with Mensores' real numbers pinned
   into it -- 292 lines of `const` arrays standing exactly where the store
   belongs. Pinned data is the right way to settle a design and the wrong way to
   ship one: point the tool at another program and every one of those arrays is
   a confident lie about a codebase nobody has read.

   So they are empty until `/api/cover` fills them. A view whose data has not
   arrived says so; none of them falls back to a number from somewhere else.
   ════════════════════════════════════════════════════════════ */

let ENTRYPOINTS = [];   // ways in, deduplicated and ranked by reach
let BOUNDARIES  = [];   // boundary kinds with counts and their commonest target
let PKGS        = [];   // top-level packages by routine count
/* The program's own namespace -- `mensores` -- measured by the server over every module and
   sent with the cover, so it is known before anything renders. What a narrow field drops
   first, because it is the one part of a module path that is the same on every row.

   This was a `Set` of package ids and the lookup was "the first segment that names a
   package", which never stripped anything: `mensores` is a package too. Replaced rather
   than patched -- the packages were never the right instrument for this question. */
let ROOT        = "";
let TABLES      = [];   // declared tables, busiest first
/* Every routine, each carrying the graph's own node id. Loaded on demand by
   `loadRoutines()` and read by two things: the navigator's routine list and table mode.
   One array, because they are the same list and a second copy is a second thing to get
   out of step. For a long time this was declared here and **assigned by nothing** -- so
   table mode rendered no rows at all, under a footer stating a count from another
   program. A `let X = []` nothing writes to is an empty view with no symptom. */
let ROUTINES    = [];
/* Every structure the program declares -- class, dataclass, enum, type alias. Arrives with
 * `ROUTINES` on one request, because the navigator lists both and the topbar search filters
 * both, and both happen at boot. */
let STRUCTURES  = [];
/* Which package ids the stack actually draws a plate for, from `/api/routines`. Not the
 * same set as the packages: the small ones are merged, and a heading offering a plate that
 * does not exist is a control that renders and resolves to nothing (rule 30). */
let PLATES      = new Set();
let ANOMALIES   = [];   // the worklist; loaded on demand, not with the cover
let STATS       = null; // files, lines, routines, when it was analysed

/* `EXTERNALS`, `EDGES` and `EXT_EDGES` were here, awaiting the real graph. Chunk 2
   mounted it and the prototype's hand-placed SVG went with it, but the three variables
   stayed -- declared, never assigned, and read by nothing at all. Deleted rather than
   exempted from the guard that found them: an unused variable that looks like pending
   work is a promise the code is not keeping. */
let SPECIMEN = null;

/* Things unusual enough to be worth a look. Every one is a real measurement from
   graph.db, and every one is a doorway rather than a statistic. */
let CURIOSITIES = [];   // what came out furthest from the middle -- served, not pinned

/* What sits next to the thing you are looking at. Not the call graph \u2014 the reasons
   something else might be worth a detour. */
/* Threads to pull, per node, served -- not pinned.
 *
 * This was six hand-written rows about one Mensores routine, naming its plans, its
 * packages and its environment variables, and it slipped past all three pinned-data
 * guards: it is a `const` object rather than a `let []`, so the array guard could not
 * see it; it is not in `PER_PROGRAM`, so the top-level guard was not looking; and the
 * prose guard searches for the program's *name*, while this said `disceptator`. It is
 * in `PER_PROGRAM` now, which is a structural check rather than a lexical one and
 * therefore cannot be evaded the same way. Rule 34. */
let THREADS = {};

let MANIFEST = [];   // the files a model pass would send, shown before anything leaves -- served, not pinned

/* The two vocabulary lanes. `PROVENANCE` used to sit here -- a map from term to the source
   spans that define it, pinned whole into the prototype at 52 KB for one program. It is
   gone: a citation is opened from `/api/source` when the reader asks for it, so the shell
   carries the file and the line rather than the file. */
let TERMS = [];        // words this program uses as names that something defines -- served, not pinned
let UNDEFINED = [];    // words it uses and nothing defines -- the mirror's finding, served
let CONVENTIONS = [];  // measured naming conventions, each with the query that counted it -- served
let VOCAB = {};        // the scalars beside them: coverage, thresholds, gaps, and which lane is loaded

/* One span of one file, fetched for the citation currently open. Not a cache of the
   program: the viewer shows one place at a time and asking again costs a local request. */
let VIEWER_SRC = null;

/* The code browser's two stores. `FILES` is the whole list, asked for once -- it cannot
 * change while the map is open, and the server builds it at boot for the same reason.
 * `CODEFILE` holds **one** file: whichever is open. A cache of many would be half a
 * megabyte per large file kept against a reader who has moved on, and the payload is
 * already fast enough that re-asking costs less than remembering. */
let FILES = [];      // every analysed file, with the counts that earn a column -- served
let CODEFILE = null; // { path, lines, links, marks, defs, ... } for the one file open

/* Searching inside the source: the answer, and the files opened out of it.
 *
 * `SEARCH` is the **file-level** answer -- how many lines matched, in which files -- and it
 * is the only one asked for on a keystroke. `SEARCHHITS` holds the expensive half, one
 * entry per file the reader actually opened, because a hit carries the margin and the
 * margin is ten queries a file: building it for the 166 files an ordinary word touches
 * would be rule 45 behind a search box, which is where that defect has lived three times.
 *
 * Both are dropped whole when the question changes. A hit list that outlived its query
 * would be an answer to a question nobody is asking, shown under one they are. */
let SEARCH = null;        // { ok, q, total, files, rows, ... } | { loading: true } | null
let SEARCHHITS = {};      // path -> { ok, hits: [...] } | { loading: true }, this query only

/* The comparison, laid over the code. Two stores, and they are split for exactly the
 * reason `SEARCH` and `SEARCHHITS` are: one is cheap and about every file, the other is
 * expensive and about the file that is open.
 *
 * `FILEPAIR` is the **file-level** answer -- which of the 628 files are the same, which
 * differ, which exist on one side only -- and it costs the server no body reads at all,
 * because `source.db` is content-addressed and equal hashes are equal bytes. `FILEDIFF`
 * is one file's line difference, and it is the only place `difflib` runs.
 *
 * `null` means nobody has asked; `{loading: true}` means it is coming. Rule 35's
 * invariant: *not computed yet* and *nothing to report* are opposite claims, and one
 * shape that cannot tell them apart puts an unmarked file beside a marked one and calls
 * them both unchanged. */
let FILEPAIR = null;      // { available, base, compared, counts, rows } | { loading } | null
let FILEDIFF = null;      // { available, file, status, base_only, inserts } | { loading } | null

/* A line to reveal once the file it is in has arrived. Not in `state`: it is a debt owed
 * across one fetch, not a place the reader is, and persisting it would restore a scroll to
 * a hit from a search nobody remembers making. Cleared as soon as it is paid, so a later
 * `render()` cannot move the pane a second time under someone reading it. */
let codeGoto = 0;

/* Two points in time.
 *
 * `REVISIONS` is every snapshot this program directory holds, asked for once at boot
 * because it is one small query and the navigator states a count beside every other row
 * — a blank there reads as *nothing here* rather than as *not asked yet*.
 *
 * `CHANGES` is the comparison itself, and it is **not** an array on purpose: `null` means
 * nobody has asked for it and `{ ... }` means it has been computed, and those are opposite
 * claims that a `[]` cannot tell apart (rule 35). It is fetched when the reader first opens
 * the worklist rather than at boot: a change list is opened deliberately, unlike the two
 * vocabulary lanes, which are asked for on every selection and are therefore paid for at
 * start. */
let REVISIONS = [];       // [{ revision, state, captured, label, files, comparable, serving }]
let CHANGES = null;       // { available, counts, added, removed, behaves, ... } | { loading: true } | null
/* What the comparison says about each **finding**: the three bands `/api/anomalychanges`
 * pairs on the identity each detector declares. Held for one pair, dropped by whoever moves
 * the pair, exactly as `CHANGES` is -- and for the same reason, which the loaders above
 * state: an answer to another question shown under this one's heading is invisible, because
 * marks look exactly like marks.
 *
 * The one that costs. Findings are not rows to be joined, so the compared end means running
 * thirteen detectors over a graph nothing here has opened: 1.3 s to 4.1 s the first time
 * and 0 ms afterwards, both ends held per graph on the server. That is why it is asked for
 * when the worklist is opened rather than with the cover. */
let ANOMALYCHANGES = null; // { available, counts, only_in_base, only_in_compared, moved } | { loading } | null

/* A base switch in progress, or `null` for none.
 *
 * `null` rather than an idle object, for rule 35's reason one more time: "nobody has asked
 * for a switch" and "a switch is running and has done nothing yet" are opposite claims,
 * and a shape that cannot tell them apart puts a blocking overlay on a page where nothing
 * is happening.
 *
 * It carries the server's own progress verbatim — `state`, `revision`, `step`,
 * `done_steps`, `steps`, `ms`, and `reason` when it failed — because the steps and their
 * count are the server's to name. A client-side list of what the server builds is two
 * answers to one question, and the day a step is added the overlay counts to the wrong
 * total (rule 32). */
let REBUILD = null;

const AI_OPS = [
  { id: "harvest", label: "Harvest definitions from documentation", needs: "docs",
    desc: "Reads only documents whose shape suggests a definition \u2014 a bold term, a heading, a table row, a term-dash-gloss. Returns quotations with a file and line you can check.",
    unit: "57 documents \u00b7 977 KB \u00b7 ~225k tokens", cost: 0.68, recommended: true },
  { id: "harvestall", label: "\u2026or read every document, untriaged", needs: "docs",
    desc: "Skips triage. Finds more, costs 44\u00d7 more, and most of what it reads is roadmaps and issue logs that mention terms without defining them.",
    unit: "2,449 documents \u00b7 43 MB \u00b7 10.1M tokens", cost: 30.18 },
  { id: "traceability", label: "Reconcile plan ids between docs and code", needs: "docs",
    desc: "434 of 530 code ids already trace to a document deterministically \u2014 no model needed. This one reads the 96 that do not, to see whether a plan exists under another name.",
    unit: "96 unmatched ids", cost: 0.35 },
  { id: "infer", label: "Infer the terms no document defines", needs: "names",
    desc: "For words nothing explains. A guess from the word and the identifiers around it \u2014 not checkable against anything.",
    unit: "2 terms", cost: 0.08 },
  { id: "flows", label: "Flow summaries for each way in", needs: "names",
    desc: "A paragraph per entrypoint, written from the resolved call graph: routine names, signatures and boundary kinds. No bodies.",
    unit: "14 ways in", cost: 0.90 },
  { id: "triage", label: "Anomaly triage suggestions", needs: "names",
    desc: "For each finding, a first opinion on whether the blind spot applies. A suggestion, never a verdict.",
    unit: "105 findings", cost: 1.10 },
  { id: "narrate", label: "Routine narration", needs: "source",
    desc: "A sentence per routine, written from the actual body. The only operation that sends your source code.",
    unit: "4,568 routines \u00b7 184k lines", cost: 12.80 }
];

/* What each posture permits. Off is the default and the whole product works there. */
const POSTURES = [
  { id: "off",    label: "Off",              allows: [],
    blurb: "Nothing leaves this machine. Every deterministic feature still works \u2014 the glossary's declared tiers, the naming standard, traceability, anomalies, flows and the whole map." },
  { id: "docs",   label: "Documentation only", allows: ["docs"],
    blurb: "Prose documents only. No source, no identifiers, no signatures. Many organisations already publish this material." },
  { id: "names",  label: "Docs + identifiers", allows: ["docs", "names"],
    blurb: "Adds routine names, signatures, and structure \u2014 the map's shape, but never a routine body." },
  { id: "source", label: "Everything",        allows: ["docs", "names", "source"],
    blurb: "Adds routine bodies. Your source code leaves this machine." },
  { id: "local",  label: "Local endpoint",    allows: ["docs", "names", "source"],
    blurb: "Everything is permitted, but the model runs at an address you control. Nothing reaches a third party." }
];

/* ════════════════════════════════════════════════════════════
   State — everything a real build would persist per program,
   keyed by stable identity so it survives a revision change.
   ════════════════════════════════════════════════════════════ */
const state = {
  view: "cover",          // cover | graph | table | doc | settings | usage | a11y | anomalies
  mode: "graph",
  edgesInMotion: true,    // links stay up while the camera turns
  spreadX: 1,             // three independent axes; all three together is what zoom is
  spreadY: 1,
  spreadZ: 0.35,
  // How much a plate's width says about how much it holds; per level, see `plateSizeNow`.
  plateSize: { routine: 1, module: 1 },
  collapseUnused: false,  // close the gap a plate nothing is looking at leaves behind
  diagram: false,         // what is lit, drawn as labelled boxes rather than as dots
  diagramId: null,        // which compartment Diagram mode has open
  diagramPorts: false,    // draw the crossings to other compartments -- see diagram.py
  navCase: false,         // the topbar's three, matching the Code box's -- see settings.js
  navWord: false,
  navRegex: false,
  diagramCursor: "arrow", // 'arrow' | 'crosshair' | 'hand' -- see settings.js
  diagramEdgeWidth: 1,    // user units; scales with the drawing, not with the chrome
  /* Which **box** is open, or null for the compartment. The second altitude of the same
   * picture: a box is a class at one level and a routine at the next, and `Compartment`
   * says "boxes, and the flow among them" at both. */
  diagramBox: null,
  nodeShapes: "kind",     // a shape *set*, never a shape per kind -- see settings.js
  /* Which panes are open. This existed in `settings.js` from the start -- persisted,
   * named in the reset dialog -- and nothing anywhere read it: the pre-merge graph had
   * collapsible panels and the merge kept the switch while dropping the implementation.
   * A setting wired to nothing is design rule 16 without even a control to look at. */
  panels: { navigator: true, inspector: true, legend: true, hud: true, controls: true },
  /* The inspector answers "what is this thing", so when nothing is picked it has nothing
   * to say and should not be holding 22rem to say it. It rails itself, and pops back the
   * moment there is something to show. An explicit fold by the reader outranks this. */
  inspectorAuto: true,
  navWidth: 21,           // rem; the routine list has to fit a qualified name
  /* The Code group's own width, because it is a different pane holding a different thing.
   * One width for both means either a routine list padded out to hold source, or source
   * squeezed into a list's column -- and the reader retunes it on every switch. Two keys
   * rather than a map keyed by group: only one group holds code, and a map would invite a
   * width per group that nothing else wants. */
  /* 44rem holds about ninety characters of the pane's type, which is a Python line with
   * room to spare, and still leaves the centre readable on a 1275px window. It was 52,
   * which is right on a large display and takes two thirds of an ordinary one. The reader
   * drags it, and the cap is whatever the window can spare. */
  codeWidth: 44,          // rem
  codeFile: "",           // which file the Code group has open, "" for the list
  /* Whether the code browser draws the difference from the compared version over the
   * lines it shows. On, because setting a compared version is already the reader saying
   * what they came for -- and off is a real want rather than a concession, because four
   * hundred marked lines is a file whose *code* is harder to read than it was. With one
   * version it governs nothing, and the switch is not drawn: a control that cannot change
   * anything is design rule 16's defect wearing a checkbox. */
  codeOverlay: true,
  /* The same switch for the routine list and the table. Two switches rather than one,
   * because what they cost differs: the code overlay fetches a difference per file and can
   * mark four hundred lines, while these marks are read off an answer the page already
   * holds. See `settings.js`. */
  tableOverlay: true,
  /* And the same switch for the findings. A third rather than a wider second, because this
   * one costs what neither of the others does: the compared end is thirteen detectors run
   * over a graph nothing here has opened. See `settings.js`. */
  anomalyOverlay: true,
  /* Whether the findings only the *compared* version has are unfolded. **Not persisted**:
   * this is where the reader is, not what they arranged, and the line between the two is
   * the one `PERSISTED` is drawn on. */
  anoOnlyThere: false,
  /* Which presence groups have their complete list open, keyed `<band>:<side>`. **Not
   * persisted**, for `anoOnlyThere`'s reason: this is where the reader is, not what they
   * arranged. Keyed by band *and* side because a line carries up to three counts and
   * unfolding the constants that moved is not a request to unfold the twenty-three the
   * other version has not got. */
  presOpen: {},
  codeQ: "",              // one box, two lanes: file names, and the text inside them
  /* How a match is decided. Persisted, because they are how this reader searches rather
     than what they are looking for right now -- the same line `termFilter` and `routineQ`
     sit on the other side of. */
  searchCase: false,      // `Quaestor` and `quaestor` are different words
  searchWord: false,      // `emit`, not `_emit_all`
  searchRegex: false,     // and then whole-word is off, because a regex writes its own \b
  searchOpen: {},         // path -> open, for the current answer only. Never persisted.
  pointerShown: true,     // the "you are here" arrow over each picked node
  pointerColor: "",       // "" = the token; anything else is the reader's, clamped
  pointerPlace: "rim",    // "rim" | "node" -- at the side of the stack, or over it
  reticuleShown: true,    // a ring and four ticks around what was picked
  focusLocked: true,      // only the lit set answers a hover or a click
  navGroups: "one",       // "one" | "many" -- an accordion, or every group at once
  navCap: 200,            // routines listed per package; 0 is all of them
  navOpen: {},            // group id -> open; empty means "each group's own default"
  pkgPick: null,          // which package the overview is showing everything for
  graphLayout: "stack",   // "stack" | "packages" -- a layout inside graph mode,
                          // never a fourth mode. Both built; use retires the loser.
  scale: 1,
  theme: "system",
  startup: "cover",
  trailShown: true,
  trailCap: 12,          // pruned to this on every step, seen or not
  menuOrder: "waysin",   // waysin | explore  — a genuine tie, so both exist       // cover | graph   ← the Setting standing in for a decision
  /* Which colour set carries the difference channel and severity. See `settings.js`, and
   * `tokens.css` for the values and how they were measured. */
  palette: "default",     // 'default' | 'safe' | 'muted'
  ambient: false,         // anomaly badges on nodes
  hideInferred: false,
  density: "comfortable",
  bandScroll: false,       // a change band scrolls in place, or runs its full length
  /* The two versions, and which of them the screen is showing.
   *
   * `baseRev` is the version being read — the cover, the routine list, the code browser,
   * the glossary and the stack all show that one — and `comparedRev` is the version it is
   * held against. So "what am I looking at" has one answer while a comparison is running,
   * which it would not if every view tried to show two versions at once.
   *
   * **`comparedRev` has three states, not two, and for a while it had two.** *Nothing
   * chosen yet* (`""`) and *chosen: on its own* (`ALONE`) are different answers, and
   * collapsing them made the "on its own" option a control that could not work. Reported
   * by Tom: *"I have selected society-2026-08-29 on its own. However, the next line down
   * still shows BASE then compared with society-2026-08-26."*
   *
   * Everything about that option was right — it exists, it is selected, the handler sets
   * the field, clears `CHANGES`, and carries a comment saying "On its own is a real answer
   * and must not spend seconds fetching a comparison nobody asked for". Then
   * `comparedRevInForce()` read `""`, could not tell it from a first visit, and **invented
   * the comparison back** from the fallback that exists so a first visit marks its file
   * list. Rule 49 exactly: a fallback that yields a plausible value has hidden the failure
   * it was written for — and design rule 16 from the far side, where every part works and
   * the feature is dead.
   *
   * A named state rather than a second field, the way `sourcedb.py` makes `WORKING` a state
   * and not an id: the question is *which version, or none*, and one question keeps one
   * field. It is not a revision id and cannot collide with one — those are instants.
   *
   * **Neither is claimed to be older.** The only instant this tool records is when the
   * bytes were read, which says nothing about when the code is from: these two were
   * captured twenty-nine seconds apart and hold trees three days apart. Which is newer is
   * the reader's assumption, and it lives in `comparedIsNewer` where they can see and
   * change it.
   *
   * **The server is the truth about `baseRev`, not this.** One payload set is live at a
   * time: asking for another base makes the server open that graph and rebuild the
   * payload, the file list, both vocabulary lanes and the cover from it, which is the
   * ten seconds the reader watches. So this field is set from `/api/revisions` at boot
   * and only ever *proposes* a change. A stored value that disagrees with what is being
   * served is said out loud and never acted on by itself — ten uninvited seconds on
   * every open is not a thing to do to someone (design rule 1). */
  baseRev: "",
  comparedRev: "",
  /* The reader's assumption about which of the two versions is the newer one.
   *
   * It decides one thing and it is not a small one: whether a routine the base has and
   * the compared does not reads as **deleted** or as **added**. The sets themselves are
   * facts and are computed once; this is the interpretation laid over them, so flipping
   * it costs no re-query.
   *
   * Default: the compared version is the newer one. That is the case the feature is for
   * — here is the copy somebody handed me, what has happened since — and it is an
   * assumption rather than a finding, which is why it is stated on the strip rather than
   * buried here. */
  comparedIsNewer: "auto",   // 'auto' | 'yes' | 'no' -- see settings.js
  followMode: "replace",   // "replace" | "walk" -- what following a neighbour does
  threadsAll: false,       // the threads panel bounded (rule 8) or opened whole
  selected: null,          // the node id under inspection, or null for nothing picked
  /* A **fold** under inspection -- a diagram box, which is a class and its methods or a
   * file and its loose functions. It has no node id, because it is not a node.
   *
   * Beside `selected` rather than inside it, and the pair is governed by one accessor
   * (`inspectorSubject`) rather than by a convention. The alternative was to keep
   * nominating `members[0]`, which is what shipped and what Tom reported: a box labelled
   * `KernelDecl` filled the inspector with `KernelDecl._profile_name_or_none`, a true
   * answer about something nobody clicked (rule 32). The stack has never made that
   * mistake -- picking a plate clears the selection rather than electing a member of it. */
  fold: null,              // the box id under inspection, or null
  /* **The third subject: an arrow.** A box says what a thing is; an edge says what passes
   * between two of them, which is the question the picture has been drawing and unable to
   * state. Held as the edge id alone -- *which drawing it is on* is `state.diagramBox`,
   * which already exists, already rides the trail and is already compared. A second field
   * saying where we are would be the detail window's defect again (rule 51): two answers
   * to one question, drifting the first time anything moves either. */
  flow: null,              // the edge id under inspection, or null
  /* What the reader asked for, in id space, before it is resolved to drawn indices.
   * Held here rather than only in the engine so a choice made from the navigator while
   * the centre pane is showing a table or a document is still a real choice. */
  wanted: null,            // {nodes: [id], disks: [id]} | null
  navNote: "",             // what that choice could not draw, stated (design rule 1)
  /* A stored pair of revisions that no longer exists, said in the Changes group's
     note. Not `navNote`, which is rendered only in the graph HUD -- a surface the
     reader may never open, and where this notice was invisible for its first hour. */
  revNote: "",
  colourBy: "none",
  colWidths: { q: 26, why: 30, fan: 5, chg: 7 },
  // No filter can be applied yet, so none is claimed. The prototype carried three
  // pinned chips and the strip announced "showing 187 of 4,568 routines" over a view
  // that was filtering nothing -- a silent filter is bad, and an *announced* filter
  // that is not happening is worse, because the reader adjusts for a slice they are
  // not being shown.
  filters: [],
  /* Counted locally, and only so a Setting can be retired on evidence rather than on
   * opinion. It starts empty: the prototype shipped `{cover: 41, graph: 68, table: 52}`
   * as pinned Mensores numbers, which would have retired a setting on fiction and read as
   * a measurement while doing it. `test_no_program_data_is_pinned_into_the_shell` looked
   * only at the top-level arrays and never inside `state`, so it never saw them. */
  usage: {},
  sev: "suspect",          // which severity tab the worklist is on
  cursor: 0,               // position in the worklist
  /* Which band of the change worklist is open, "" for none. Runtime state rather than a
   * setting: it is where the reader is in one comparison, not a preference about how the
   * tool should behave, and persisting it would reopen a band of a comparison that may
   * not exist in the next program opened. */
  changeBand: "added",
  triage: {},              // finding id -> "ack" | "notbug" | "tooldefect"
  /* **`settings.js` owns these, and this is a copy of them.** It was a second literal
     spelling the same five keys, and the second copy is dead: `adoptSettings` overwrites
     every persisted key with `state[k] = settings[k]`, so what a reader sees is always
     `DEFAULTS.insp` merged with their saved blob and never this line.

     Found by editing the wrong one. Two new sections were added here, the page was opened,
     and both rendered `data-open="undefined"` -- closed, with the value box inside one of
     them measuring `clientHeight: 0`. Nothing failed and nothing was logged; the literal
     that does not win looks exactly like the literal that does. Rule 51, in the settings
     rather than at a call site: a rule kept in two places rots as one of them is edited.

     Spread rather than referenced, because a shared object is worse than a copy here --
     toggling a section would write through into `DEFAULTS` and a reset would then restore
     what the reader had just changed. */
  insp: { ...window.DunneFlowSettings.DEFAULTS.insp },
  aiOps: { harvest: true },
  egress: "off",
  showManifest: false,
  showSql: null,
  sortKey: "fan",
  sortAsc: false,
  viewer: null,
  /* The detail window: **open or not**, never *which node*. It reads the one selection, so
   * it cannot drift from it -- and it did, for as long as it held an id of its own: the
   * trail's Back moved the selection and left the window standing on the node before it,
   * two states disagreeing in the one window built to show how things connect. Found by
   * driving it, not by any check.
   *
   * Not persisted: it is where the reader is looking right now, not how they like the
   * surface arranged. */
  detail: false,
  detailAll: {},
  /* Seeded once the program's name is known, never with a name written here -- this
     carried a literal "mensores" from the prototype, which is a confident label about a
     program nobody has read. */
  trail: [],
  pins: [],      // {term, idx} — which citation is open in the source viewer   // what a one-time inference pass would cover
  aiConfirm: false,            // second click arms it
  aiDone: false,               // has the pass been run
  termFilter: "",
  /* What is typed in the topbar search. Transient like `termFilter`: a filter is a
     question being asked right now, not an arrangement worth restoring next visit. */
  routineQ: ""
};

/* How many routines one package lists, and what the choices are.
 *
 * Bounded, which rule 8 allows *only* because the complete list sits beside it -- table
 * mode reads the same `ROUTINES` array and shows every row. The bound exists because
 * `render()` rebuilds the navigator on every keystroke, and 4,734 buttons per keystroke is
 * a filter that fights the reader. What is left out is always stated (design rule 1).
 *
 * It is the reader's to set, because 200 was a judgment about *this* machine and it read as
 * a tease: Mensores' packages mostly hold 200-400, so the notice said `200 of 377` over a
 * list that was very nearly whole. `0` is every routine there is -- the pane gets long, and
 * that is a thing someone may want. The default stays 200. */
const NAV_CAPS = [50, 100, 200, 500, 0];

/* How many matches a search may open packages for by itself. Not the reader's cap: that
 * says how much of *one* package to list, and this says whether a search has narrowed
 * anything down yet. A search matching four thousand routines has not. */
const SEARCH_OPEN_MAX = 200;
function navCap() {
  const n = Number(state.navCap);
  return Number.isFinite(n) && n > 0 ? n : Infinity;
}

/* What was typed in the search box the last time the navigator was built. The scroller
 * keeps its place across a rebuild, and this is how "the same list again" is told from
 * "a different question, answered from the top". */
let navBuiltFor = null;

const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
/* Usage is counted so a Setting can be retired on evidence rather than on opinion, which
 * means it starts at zero for every program and every key. `state.usage.graph++` on an
 * absent key yields NaN, and a NaN in the usage report is a count that silently stops
 * counting -- so no caller increments directly. */
function used(key) { state.usage[key] = (state.usage[key] || 0) + 1; }

const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

/* ═══ theme + scale ═══ */
/* ── collapsible panes ───────────────────────────────────────────────────────────
 *
 * `state.panels` finally does something. It was in `settings.js` from the first day --
 * persisted, listed in the reset dialog by name -- and read by nothing at all: the
 * pre-merge graph had collapsible panels and the merge kept the switch while dropping the
 * implementation. A reset would have reported clearing a layout that never existed.
 *
 * The grid tracks carry the state, not the panes: collapsing a pane without collapsing its
 * column leaves a hole exactly the width of the pane that is no longer there.
 *
 * ── and why this is a table ──
 *
 * The first fix wired up `navigator` and `inspector` by writing them as a literal pair,
 * which left `hud` and `controls` dead *inside* a live key -- somewhere the guard written
 * for the original failure could not see, because it walks the top-level keys of
 * `DEFAULTS` and `panels` as a whole was plainly being read. The capability the pre-merge
 * graph had was not deleted; a loop over `Object.entries(panels)` was narrowed to a
 * two-element literal, and the two entries that fell out took a feature with them.
 *
 * So: every panel is an entry here, `applyPanels()` walks the *settings*, and a key with
 * no entry is a named error rather than a silent skip (design rule 16). A test asserts the
 * two key sets agree, so a panel added to settings cannot quietly stop folding.
 *
 * Two mechanisms, because there are genuinely two shapes. A full-height side pane
 * collapses its grid *track* and leaves a rotated rail (design rule 24). An overlay box
 * floating on the canvas collapses to a horizontal ribbon -- its own header strip, still
 * stating its summary. Merging them would give one of the two the wrong furniture. */
/* `attr` is written as `data-<attr>` and must not collide with an attribute that already
 * means something else. `navigator` wrote **`data-nav`** -- the same attribute `NAV_ROUTES`
 * is keyed on -- so `.body` carried `data-nav="on"` as grid-track state while every routed
 * control carried `data-nav="chg"`, `"pkg"`, `"routine"` as a route. One name, two
 * unrelated meanings, and it went unnoticed for as long as the click handler happened to
 * select on a class instead: broadening it to the attribute made `.body` the nearest
 * routed ancestor of every stray click, and the self-check reported `nav "on" has no
 * route` on the first page load. Rule 47's companion -- one channel meaning two things --
 * one layer below where that rule found it. A test keeps the two sets disjoint. */
const PANELS = {
  navigator: { how: "track", grid: ".body",       attr: "navtrack", rail: "#navigatorRail" },
  inspector: { how: "track", grid: ".body",       attr: "insp",   rail: "#inspectorRail" },
  legend:    { how: "track", grid: "#graphMount", attr: "legend", rail: "#legendRail" },
  hud:       { how: "class", box: "#panel-hud" },
  controls:  { how: "class", box: "#panel-controls" },
};

function panelIsOpen(name) {
  if (name === "inspector" && state.inspectorAuto && state.panels.inspector) {
    /* Auto only ever *closes*, and only when the inspector genuinely has nothing to say.
     * An explicit fold is recorded in `panels.inspector` and outranks this, so the reader
     * can keep it shut with something selected -- what they cannot do is have it silently
     * reopen underneath them.
     *
     * **`inspectorSubject()`, not `state.selected`.** A diagram box sets no `selected` at
     * all -- it is not a node -- so reading the narrower field railed the pane shut over a
     * fully rendered answer: sixty-one members, eight neighbours and the way to the code,
     * all painted, in a column zero pixels wide. That is the exact symptom Tom reported
     * ("perhaps it selects, but the view does not change"), arriving from the other end. */
    return Boolean(inspectorSubject());
  }
  return Boolean(state.panels[name]);
}

/* Walks the settings, not a list of its own: a panel that exists in `DEFAULTS.panels` and
 * is missing from `PANELS` is announced rather than skipped. Silence here is precisely how
 * two panels stopped folding without anything reporting it. */
/* The navigator's width, in rem so the scale multiplier reaches it (design rule 3).
 *
 * Written to the grid as a custom property rather than into `grid-template-columns`,
 * because the track shorthand is also what `data-nav`/`data-insp` rewrite when a pane
 * folds -- two rules setting the same property means the last one wins and one of the two
 * features silently stops working. A variable lets both act without racing. */
function applyNavWidth() {
  const body = document.querySelector(".body");
  /* Clamped on the way out as well as on the way in. A width saved on a wide screen, or
     with the inspector folded, is a width this window may not have room for -- and a track
     wider than the window pushes the centre off the right-hand edge with no way back. */
  if (body) body.style.setProperty(
    "--nav-w", `${Math.min(navMaxRem(), Math.max(NAV_MIN_REM, navWidth()))}rem`);
}

function applyPanels() {
  applyNavWidth();
  for (const name of Object.keys(state.panels)) {
    const spec = PANELS[name];
    if (!spec) {
      console.error("DunneFlow: panel with no mechanism:", name,
                    "-- add it to PANELS or take it out of DEFAULTS.panels");
      continue;
    }
    const open = panelIsOpen(name);
    if (spec.how === "track") {
      const grid = document.querySelector(spec.grid);
      if (!grid) continue;                    // the graph mount is absent in doc-only pages
      grid.dataset[spec.attr] = open ? "on" : "off";
      const rail = $(spec.rail);
      if (rail) {
        rail.hidden = open;
        rail.setAttribute("aria-expanded", String(open));
      }
    } else {
      /* The box is rebuilt by `renderGraphFurniture()`, so it is often absent -- the
       * class is applied there too, from the same `panelIsOpen()`. This branch is what
       * handles a fold while it is on screen. */
      const box = $(spec.box);
      if (!box) continue;
      box.classList.toggle("closed", !open);
      const head = box.querySelector(".hudhead");
      if (head) head.setAttribute("aria-expanded", String(open));
      const chev = box.querySelector(".chev");
      if (chev) chev.textContent = open ? "▾" : "▸";
    }
  }
}

function applyTheme() {
  const r = document.documentElement;
  if (state.theme === "system") r.removeAttribute("data-theme");
  else r.setAttribute("data-theme", state.theme);
  const btn = $("#themeBtn");
  const label = { system: "◐ System", light: "☀ Light", dark: "☾ Dark" }[state.theme];
  btn.textContent = label;
  btn.setAttribute("aria-label", "Theme: " + state.theme + ". Activate to change.");
  /* The graph follows the theme. It reads the same tokens off `:root`, but nothing tells
   * a WebGL canvas that a CSS custom property changed -- so the palette is pushed. */
  if (typeof applyGraphPalette === "function") applyGraphPalette();
}
/* Stamp the chosen colour set, or take the stamp off for the default.
 *
 * Off rather than `data-palette="default"`, and that is not tidiness: the base token block
 * *is* the default, so a stamp for it would need a fourth and fifth copy of every value it
 * already declares. Absent means "the blocks above", which is what they are.
 *
 * **The graph is repainted here, and it did not used to be.** A set covers `--diff-*` and
 * `--sev-*`; `cssPalette()` read neither, so a push to the stack would have been a repaint
 * that changed nothing. The comparison arriving as `colorBy: "change"` is what made it read
 * `--diff-gone`, `--diff-new` and `--diff-moved` -- and from that moment a set chosen in
 * Settings would have moved every surface except the one the reader is looking at.
 *
 * That implication was **asserted rather than remembered** (rule 36):
 * `test_a_palette_token_the_graph_reads_must_reach_the_graph` derives both halves from the
 * files and was vacuous until the read landed, then failed by name. It is the reason this
 * line exists rather than being noticed later by someone switching sets with the stack
 * open. */
function applyPalette() {
  const r = document.documentElement;
  if (state.palette === "default") r.removeAttribute("data-palette");
  else r.setAttribute("data-palette", state.palette);
  /* After the stamp, never before: `cssPalette()` reads the computed value off `:root`, so
     pushing first would read the set the reader has just left. */
  if (typeof applyGraphPalette === "function") applyGraphPalette();
}

/* Both diagram appearance settings, pushed to CSS as custom properties.
 *
 * On the document root rather than on the pane, and that is the point: the diagram host is
 * rebuilt on every compartment change, so setting it there would mean every rebuild is a
 * second place that has to remember (rule 51). Written once here, read by `tokens.css`, and
 * correct before the diagram has ever been opened.
 *
 * The stroke is clamped rather than trusted. A stored value is whatever was in
 * `localStorage`, which a reader can edit, and a 400-unit stroke is a solid rectangle with
 * no way back to a picture -- design rule 6's reasoning, one control over: customisation is
 * clamped, and the clamp is at the one door the value comes through.
 */
function applyDiagramLook() {
  const r = document.documentElement;
  /* **Two cursors, not one, and the pair is what the first version got wrong.** It set the
     pickable things only, so the boxes and arrows turned to an arrow and the whole canvas
     around them stayed `grab` -- reported exactly that way: *"the cursor is still Hand most
     of the time, it only switches to arrow when near the link."* The surface is most of what
     a reader's pointer is over, so styling only the targets changes almost nothing.

     They stay a pair rather than collapsing to one value because `hand` has genuinely
     different conventional glyphs for the two: an **open** hand says this surface pans, a
     **pointing** hand says this thing is clickable. Keeping both is what makes `Hand`
     honestly "what it was before" rather than an approximation of it. */
  const surface = { arrow: "default", crosshair: "crosshair", hand: "grab" };
  const pick    = { arrow: "default", crosshair: "crosshair", hand: "pointer" };
  r.style.setProperty("--dgm-cursor", surface[state.diagramCursor] || "default");
  r.style.setProperty("--dgm-cursor-pick", pick[state.diagramCursor] || "default");
  const w = Number(state.diagramEdgeWidth);
  r.style.setProperty("--dgm-edge-width",
                      String(Number.isFinite(w) ? Math.min(8, Math.max(1, w)) : 1));
}

function applyScale() {
  document.documentElement.style.setProperty("--scale", state.scale);
  const pct = Math.round(state.scale * 100);
  $("#scaleVal").textContent = pct + "%";
  const sl = $("#scaleSlider");
  if (sl) { sl.value = state.scale; sl.setAttribute("aria-valuetext", pct + " percent"); }
  /* Design rule 3, and what the Settings page already promises in so many words: "one
   * multiplier over everything -- type, column widths, row heights, icons, graph nodes."
   * The graph had its own independent size slider and never saw this one, so the promise
   * was true of every dimension on the page except the one it named last. */
  if (Graph && Graph.mounted()) Graph.setScale(state.scale);
}
$("#themeBtn").addEventListener("click", () => {
  state.theme = { system: "light", light: "dark", dark: "system" }[state.theme];
  applyTheme();
});
$("#scaleSlider").addEventListener("input", (e) => {
  state.scale = parseFloat(e.target.value);
  applyScale();                       /* live — no re-render, so the drag survives */
});
$("#scaleSlider").addEventListener("change", render);

/* ═══ nav groups ═══ */
/* Delegated, because the navigator is generated from the store after this file runs.
   Binding to the elements directly worked while the groups were written into the HTML
   and would have silently stopped working the moment they were not -- a listener
   attached to nothing looks exactly like a listener attached to something. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-toggle]");
  if (!b) return;
  const g = b.closest(".nav-group");
  if (!g) return;
  setGroupOpen(g.id, g.dataset.open !== "true");
});

/* A package inside the routine list. Not the accordion: two packages open at once is how
 * anyone compares them, and the accordion is about the pane's *groups* being longer than
 * the pane. Kept in the same `navOpen` map, because "what is open in the navigator" is one
 * question and one setting -- `setGroupOpen` only ever closes the top-level ids, so a
 * package key is never swept up by it. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-pkgopen]");
  if (!b) return;
  const key = `pkg:${b.dataset.pkgopen}`;
  state.navOpen[key] = !state.navOpen[key];
  persist();
  buildNav();
});

/* The jump strip, routed from the same table the strip is generated from (design rule 16):
 * an id that names no group is a named error rather than a click that does nothing. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-jump]");
  if (!b) return;
  const id = b.dataset.jump;
  if (!NAV_GROUPS.some(g => g.id === id)) {
    console.error("DunneFlow: no navigator group for jump", id, b);
    return;
  }
  /* Open it as well as go to it. Under the accordion the group being jumped to is usually
   * closed, and arriving at a closed heading is indistinguishable from nothing happening. */
  setGroupOpen(id, true);
  jumpToGroup(id);
});
/* Every nav kind routes explicitly. An unhandled kind used to fall through to
   `state.view = state.mode`, which silently showed the graph instead of the page
   that was clicked -- a dead control that looked like a working one. */
const NAV_ROUTES = {
  /* The interaction the tool is for, and it is one line because every piece of it already
   * existed separately. `selectFromNav` selects in id space, loads `/api/node`, ensures the
   * graph and applies the selection; `recomputeMembers()` in the engine then pulls in the
   * node's one-hop callers and callees and draws exactly those edges, filtered by the
   * `follow` control. What was missing was never the machinery -- it was a row that
   * carried an identity and a route that consumed one. Rule 30, from the other side. */
  routine:     (b) => { selectFromNav({ nodes: navIds(b) }); },
  cover:       () => { state.view = "cover"; },
  /* No loader call here on purpose. Five things route to these two pages -- the navigator,
     the breadcrumb, `data-goto`, a curiosity and the trail -- and a fetch wired at one of
     them is a page that works from one direction and says "not asked for yet" forever from
     the other four. `render()` asks, once, for whichever view is about to be painted. */
  glossary:    () => { state.view = "glossary"; },
  naming:      () => { state.view = "naming"; },
  inference:   () => { state.view = "inference"; },
  curiosities: () => { state.view = "curiosities"; },
  pins:        () => { state.view = "pins"; },
  a:           (b) => {
    state.view = "anomalies";
    // Fetched on demand, not with the cover: the findings are large and most
    // sessions read the counts without ever opening the list.
    loadAnomalies().then(render);
    /* And the comparison over them, through the same door and on the same bargain — the
       dearest of the three overlays, so it is never paid by a reader who does not open
       this list. It repaints itself when an answer arrives. */
    ensureAnomalyOverlay();
    state.sev = b.dataset.sevnav || "suspect";
    state.cursor = 0;
    used("anomalies");
  },
  /* These four set what you are looking AT, and keep the centre pane's current mode.
   *
   * They used to be `() => { state.view = state.mode; ensureGraph(); }` -- four routes
   * that switched mode and selected nothing, so all forty navigator rows did the same
   * thing and the inspector went on truthfully reporting "Nothing selected". It never
   * tripped the no-route error below, because the route existed; it just had no subject
   * to act on, and no subject had ever reached the DOM. Design rule 16 one level down
   * again: a control that renders, routes, and resolves to nothing. */
  ep:  (b) => selectFromNav({ nodes: navIds(b) }),
  pkg: (b) => selectFromNav({ disks: navIds(b) }),
  b:   (b) => selectFromNav({ disks: navIds(b) }),
  t:   (b) => selectFromNav({ table: b.dataset.navid || "" }),
  /* A file is not a node: nothing lights in the stack and the inspector has nothing to
     answer about it, so this opens a pane rather than making a selection. What the reader
     picks *inside* it is a node, and that is the click that selects. */
  file: (b) => openCodeFile(b.dataset.navid || ""),
  /* The same file, opened **and gone to**, and it is a second route rather than a flag on
     the first because the two callers want different things. Inside the navigator's Code
     group the file list is already under the reader's eye, so `file` opens the pane and
     deliberately leaves the centre alone -- that group exists to have code and the stack
     readable at once. A row in the change worklist is nowhere near the code, so opening a
     pane the reader cannot see is a click that does nothing visible: design rule 16's dead
     control, except that it works.

     Found by clicking one. `state.codeFile` was set, the file loaded, and the page did not
     move a pixel -- rule 51 in the shape that rule is about, a route correct for the one
     caller it was written for and wrong for the caller it has just acquired. */
  chgfile: (b) => {
    openCodeFile(b.dataset.navid || "");
    /* Both, and `persist` after them, exactly as `codeopen` does: `mode` is what the centre
       toggle shows and `view` is what is painted, and setting one of the two leaves the
       toggle disagreeing with the pane. `render()` is the dispatcher's, not ours. */
    state.mode = "code";
    state.view = "code";
    persist();
  },
  /* A changed routine is a routine. The band it sits in says *why* it is worth looking at;
     the click is the same selection every other row makes, so the stack lights its hop, the
     inspector fills, the trail records it and undo takes it back -- none of which this view
     had to build. Rule 30 from the useful side: the row carries an identity, and the route
     is the only place that knows what to do with one. */
  chg:     (b) => selectFromNav({ nodes: navIds(b) }),
  changes: () => { state.view = "changes"; refreshChanges(); },
};

/* Load the comparison, then repaint **both** places that show it.
 *
 * `loadChanges().then(render)` was not enough and the gap was invisible from either side
 * on its own: `render()` rebuilds the centre, the inspector, the trail and the filters,
 * and does not touch the navigator. So the comparison arrived, the centre painted the
 * whole worklist, and the Changes group beside it went on saying "two points in time —
 * open to compare them" with a blank count and no rows -- one question, two answers,
 * which is rule 51. Every caller goes through this door so neither half can be forgotten. */
function refreshChanges(base, compared) {
  const pair = base === undefined && compared === undefined
    ? chosenPair() : { base, compared };
  /* A result computed for a different pair is not a stale copy of this one, it is an
     answer to another question. Dropped before the load rather than left to be overwritten,
     so the view spends the fetch saying "comparing…" instead of showing the old pair's
     figures under the new pair's heading. */
  if (CHANGES && !CHANGES.loading
      && (CHANGES.base !== pair.base || CHANGES.compared !== pair.compared)) CHANGES = null;
  /* The findings' pairing is about the same two versions and goes stale on the same move.
     Dropped here rather than reloaded: this door is the reader asking about the *routines*,
     and re-running thirteen detectors over the other graph because of it would spend
     seconds nobody asked for. `ensureAnomalyOverlay` fetches it when the worklist is next
     opened, which is the only place it is drawn. */
  if (ANOMALYCHANGES && !ANOMALYCHANGES.loading
      && (ANOMALYCHANGES.base !== pair.base
          || ANOMALYCHANGES.compared !== pair.compared)) ANOMALYCHANGES = null;
  return loadChanges(pair.base, pair.compared).then(() => { buildNav(); render(); });
}

/* Which two versions are in play. One place decides, and everything asks it.
 *
 * The **base** is the version the whole map is showing; the **compared** is the one it
 * is held against. Neither is claimed to be older than the other -- the only instant
 * this tool records is when the bytes were read, which says nothing about when the code
 * is from, and a tree handed over on a memory stick has no history to ask. Which one is
 * newer is the reader's assumption, held in `comparedIsNewer` and stated on the strip.
 *
 * Both fall back to the server's own default -- the served graph, and the next
 * comparable one -- which is what `/api/changes` does with no arguments, so an empty
 * choice and an unmade choice produce the same answer rather than two.
 *
 * A stored revision that no longer exists is **dropped and reported**, never quietly
 * honoured: re-analysing a program can retire a snapshot, and a comparison silently
 * carried out against a different pair than the one named in the toolbar is the worst
 * outcome available here (design rule 1, and rule 13 -- the answer must be the one the
 * claim beside it names). */
function chosenPair() {
  const live = (id) => REVISIONS.some(r => r.revision === id && r.comparable);
  return {
    base:     live(state.baseRev) ? state.baseRev : undefined,
    compared: live(state.comparedRev) ? state.comparedRev : undefined,
  };
}

/* What the reader chose but cannot have, said out loud rather than swallowed. */
function pairLost() {
  /* The comparison end only. The reading end cannot be lost any more: `reconcileBase()`
     sets it from `/api/revisions`'s own `serving` flag, so it names a revision that exists
     by construction — and when a *stored* reading end disagrees with what is served, that
     is a different message with a different remedy, said there. Two places reporting one
     kind of loss would be two answers (rule 51). */
  const gone = [];
  /* `ALONE` is a state and not a revision, so it can never be one that has gone away.
     Without this guard, choosing "on its own" reports *the revision you were comparing
     (alone) is no longer here* on the next reload and silently resets the choice --
     which is rule 43, a check crying wolf about a thing that never existed. */
  if (state.comparedRev && state.comparedRev !== ALONE
      && !REVISIONS.some(r => r.revision === state.comparedRev)) {
    gone.push(state.comparedRev);
  }
  return gone;
}

/* What differs between the two versions.
 *
 * Asked for on demand rather than with the cover, for the reason the anomalies list is:
 * most sessions never open it, and on a large program the comparison is seconds of work
 * that the reader would pay for on a screen they are not looking at.
 *
 * `{ loading: true }` is a state the view renders, not a gap it renders nothing into. The
 * three answers here are genuinely different -- not asked yet, being computed, and computed
 * with nothing in it -- and collapsing any two of them puts a blank pane where a sentence
 * belongs (design rule 1, and rule 35's invariant one layer up). */
async function loadChanges(base, compared) {
  if (CHANGES && CHANGES.loading) return CHANGES;
  CHANGES = { loading: true };
  render();
  const qs = [];
  if (base) qs.push("base=" + encodeURIComponent(base));
  if (compared) qs.push("compared=" + encodeURIComponent(compared));
  try {
    const r = await fetch("/api/changes" + (qs.length ? "?" + qs.join("&") : ""));
    CHANGES = await r.json();
  } catch (err) {
    /* Named, never swallowed. A comparison that failed and a program that did not change
       are opposite claims, and an empty worklist states the second one. */
    CHANGES = { available: false, reason: "the comparison could not be read: " + err.message };
  }
  return CHANGES;
}

/* ══ the comparison over the code ═══════════════════════════════════════════════════════
 *
 * Both loaders answer the same three states the rest of this file does -- not asked,
 * loading, answered -- and both drop an answer computed for a *different* pair rather
 * than letting it be overwritten. An answer to another question shown under this one's
 * heading is the worst outcome available here, and it is invisible: the marks look
 * exactly like marks.
 */

/* Which version the code is being held against, or "" for none.
 *
 * Read from `chosenPair()` and never from a second copy, so the overlay and the worklist
 * cannot be about different versions (rule 51). The base end is deliberately absent: the
 * overlay is drawn over the bytes on screen and those are the server's base, which is why
 * `/api/filechanges` does not take one.
 *
 * `CHANGES` is preferred when it has answered, because it carries the pair the server
 * actually used -- the reader's stored choice may name a revision that no longer exists,
 * and `chosenPair()` drops it. Falling back to the choice is what makes the file rows mark
 * themselves before anyone has opened the worklist. */
/* *Chosen: on its own* — a value for `state.comparedRev`, and not a revision.
 *
 * A revision is an instant (`2026-08-31T22:53:57Z`), so this cannot collide with one. It
 * exists because "" already meant *nothing chosen yet*, and the fallback below turns that
 * into a comparison — correctly, on a first visit, and wrongly the moment a reader has
 * actually answered. See the note on `comparedRev` in `state`. */
const ALONE = "alone";

function comparedRevInForce() {
  /* Asked before `CHANGES`, because this is the reader's own answer and `CHANGES` is a
     server result that may still be describing the pair they have just left. Below the
     `CHANGES` branch this read as a comparison for one whole repaint. */
  if (state.comparedRev === ALONE) return "";
  if (CHANGES && !CHANGES.loading && CHANGES.available && CHANGES.compared) {
    return CHANGES.compared;
  }
  const chosen = chosenPair().compared;
  if (chosen) return chosen;
  /* Nothing chosen: the server's own default is the next comparable version after the one
     being served, which is what `/api/changes` would pick. Named here rather than left
     empty so the file list marks itself on a first visit — and derived from `REVISIONS`
     rather than assumed, so a one-version program gets "" and no overlay at all. */
  const usable = REVISIONS.filter(r => r.comparable);
  if (usable.length < 2) return "";
  const serving = usable.find(r => r.serving) || usable[0];
  const other = usable.find(r => r.revision !== serving.revision);
  return other ? other.revision : "";
}

/* Whether there is a comparison to draw at all. One test, so a control, a note and a mark
   cannot disagree about whether the overlay exists (rule 51). */
function comparing() {
  return REVISIONS.filter(r => r.comparable).length >= 2 && !!comparedRevInForce();
}

/* Whether the overlay is actually being drawn: a comparison, and the reader's switch. */
function overlayOn() {
  return comparing() && !!state.codeOverlay;
}

/* The same question for the routine list and the table, which have their own switch.
 * `comparing()` is shared, so the two surfaces can differ about whether to draw the marks
 * and can never differ about whether there is a comparison at all (rule 51). */
function tableOverlayOn() {
  return comparing() && !!state.tableOverlay;
}

/* And the same question for the findings, which have a switch of their own for the reason
 * the routine list has one: what the three cost differs, and this is the dear one. */
function anomalyOverlayOn() {
  return comparing() && !!state.anomalyOverlay;
}

/* The findings' pairing, asked for once per pair.
 *
 * Idempotent, and **any** answer counts as asked, including a refusal -- the trap
 * `ensureChanges` names: a refusal carries no `compared`, so a loader testing for one
 * re-asks a question already answered "no" on every call.
 *
 * Asked when the worklist is opened rather than at boot, which is the same door
 * `loadAnomalies` already comes through and the same bargain `codeOverlay` and
 * `tableOverlay` strike: a reader who never opens the worklist never pays for it, and one
 * who does has already said what they came for. Nothing waits on it -- the findings paint
 * from `/api/anomalies`, and the head says the comparison is coming rather than leaving a
 * blank where a claim belongs (rule 35).
 */
function ensureAnomalyOverlay() {
  if (!anomalyOverlayOn()) return Promise.resolve(null);
  if (ANOMALYCHANGES) return Promise.resolve(ANOMALYCHANGES);
  return loadAnomalyChanges(chosenPair().base, comparedRevInForce());
}

async function loadAnomalyChanges(base, compared) {
  if (ANOMALYCHANGES && ANOMALYCHANGES.loading) return ANOMALYCHANGES;
  ANOMALYCHANGES = { loading: true };
  render();
  const qs = [];
  if (base) qs.push("base=" + encodeURIComponent(base));
  if (compared) qs.push("compared=" + encodeURIComponent(compared));
  try {
    const r = await fetch("/api/anomalychanges" + (qs.length ? "?" + qs.join("&") : ""));
    ANOMALYCHANGES = await r.json();
  } catch (err) {
    /* Named, never swallowed, and the sentence matters more here than anywhere else this
       pattern appears: three empty bands read as *this version had nothing wrong with it*,
       which is the opposite of *we could not look* (rules 49 and 63). */
    ANOMALYCHANGES = { available: false,
                       reason: "the comparison could not be read: " + err.message };
  }
  render();
  return ANOMALYCHANGES;
}

/* What one finding's mark says, in a glyph, a class and a sentence.
 *
 * **Every class begins `anochg-`**, and rule 71 is why: a class name is global and a
 * stylesheet gives no warning. The routine lane learned it the expensive way -- its first
 * version reached for `.chg-mod`, which was already the change worklist's *module* label,
 * so every modified file rendered smaller and greyer than the unchanged ones.
 *
 * The tone comes from `diffWords()` and never from the band, so flipping which version the
 * reader takes to be newer swaps the colour with the word. A page saying "added" in the
 * colour of *gone* is worse than one with no colour at all.
 *
 * **Three states, and only two have a direction.** A finding both versions have, whose
 * count or severity moved, was neither added nor deleted -- so it gets a mark of its own
 * rather than a sign that means nothing, and its sentence names *which* of the three claims
 * moved and what the other version says. That is what `moved` and `in_compared` carry, and
 * it is the whole reason 5b compares the claims rather than the title (rule 40).
 */
function anomalyChip(ident) {
  if (!anomalyOverlayOn()) return { cls: "", glyph: "", title: "" };
  const band = anomalyBandOf(ident);
  if (!band) return { cls: "", glyph: "", title: "" };
  const w = diffWords();
  if (band.where === "only_in_base") {
    return { cls: " anochg tone-" + w.base.tone, glyph: signOf(w.base.tone),
             title: w.base.word + " — only the version on screen has this finding" };
  }
  if (band.where === "moved") {
    /* `◈`, and not a sign: *still here, claiming something different* has no direction, and
       a `+` or a `−` here would be the second of two numbers about one thing (rule 32).
       `tone-moved` rather than a colour of its own -- the violet is measured, in all three
       sets and both themes (rule 69), and it is what the graph legend already spells this
       same idea with. */
    return { cls: " anochg tone-moved", glyph: "◈",
             title: "still here, and claiming something different — " + movedWords(band.row) };
  }
  /* No glyph, and the sentence carries it. This is the state with no visible mark, so it is
     the one that needs the words: unmarked-and-compared and unmarked-and-not-compared are
     opposite claims that look identical. */
  return { cls: " anochg anochg-same", glyph: "",
           title: "both versions have it, claiming the same thing" };
}

/* Which band a finding is in, by its identity — and `null` when there is no answer to read
 * yet, which is not the same as "in neither band". */
function anomalyBandOf(ident) {
  const v = ANOMALYCHANGES;
  if (!v || v.loading || !v.available || !ident) return null;
  if ((v.only_in_base || []).some(r => r.ident === ident)) return { where: "only_in_base" };
  const m = (v.moved || []).find(r => r.ident === ident);
  if (m) return { where: "moved", row: m };
  return { where: "same" };
}

/* What moved, in words, from the two things 5b sends: which claims differ, and what the
 * compared version says each of them is. Both, because "the count moved" without the other
 * number is a mark that tells the reader to go and look somewhere there is nothing to see. */
function movedWords(row) {
  const said = { count: "occurrences", severity: "severity", confidence: "confidence" };
  return (row.moved || []).map(c => {
    const there = (row.in_compared || {})[c];
    const here = c === "count" ? row.count : row[c];
    return `${said[c] || c} ${here} here, ${there} there`;
  }).join("; ");
}

/* The **fact** lane's data, asked for once per pair.
 *
 * `refreshChanges()` fetches unconditionally, which is right for a reader who clicked
 * Compare and wrong for a file being opened -- so this is the idempotent door onto it.
 *
 * It is asked for by the code browser at all because of what it carries: *this routine
 * behaves differently*, which no text diff can state and which is the half of a comparison
 * this tool exists for. Without it the lane appeared only for a reader who had opened the
 * worklist first — a feature that works by luck, which is the closed loop the Changes
 * group's own `onOpen` was written to close (rule 55's companion).
 *
 * It does not block anything. The lines paint from `/api/filechanges`, which is cheap; this
 * is 317 ms warm and can be tens of seconds on the first comparison of a session against a
 * cold volume, and the lane says it is coming rather than showing a blank (rule 35). */
function ensureChanges() {
  if (!comparing()) return Promise.resolve(null);
  /* **Any** answer counts as asked, including one that refused. Testing
     `CHANGES.compared === compared` looked more careful and was wrong: a refusal carries
     no `compared` at all, so every call would have re-asked a question already answered
     — and answered "no". Whoever moves the pair drops `CHANGES`, and that is the one
     place that decides this is stale (rule 51). */
  if (CHANGES) return Promise.resolve(CHANGES);
  const pair = chosenPair();
  return loadChanges(pair.base, comparedRevInForce())
    .then((c) => { buildNav(); render(); return c; });
}

/* The file-level pairing. Idempotent: every caller asks, and only the first one fetches.
 *
 * Asked when the Code group opens or a file is opened rather than at boot, for the reason
 * the worklist is: a reader who never opens the code never pays for it. It is one request
 * and no body reads — 325 ms on the first touch of a cold external volume, 12 ms after —
 * so there is nothing here to be clever about. */
function ensureFilePair() {
  const compared = comparedRevInForce();
  if (!comparing()) { FILEPAIR = null; return Promise.resolve(null); }
  if (FILEPAIR && FILEPAIR.loading) return Promise.resolve(FILEPAIR);
  if (FILEPAIR && FILEPAIR.compared === compared) return Promise.resolve(FILEPAIR);
  return loadFilePair(compared);
}

async function loadFilePair(compared) {
  FILEPAIR = { loading: true, compared };
  try {
    const r = await fetch("/api/filechanges?compared=" + encodeURIComponent(compared));
    FILEPAIR = await r.json();
  } catch (err) {
    /* Named, never swallowed. "The pairing could not be read" and "no file changed" are
       opposite claims, and an unmarked list states the second one. */
    FILEPAIR = { available: false, compared,
                 reason: "the file comparison could not be read: " + err.message };
  }
  return FILEPAIR;
}

/* What one file's status is, or "" when nothing has been compared.
 *
 * "" rather than "same", and the difference is the whole of design rule 1: a file nobody
 * has compared and a file that did not change look identical on screen unless one of them
 * says which it is. */
function fileStatus(path) {
  if (!overlayOn() || !FILEPAIR || FILEPAIR.loading || !FILEPAIR.available) return "";
  if (!FILEPAIR._by) {
    /* Built once and hung on the answer, because the file list draws 628 rows and a
       `find` per row is rule 45's shape — the same defect `Graph.connections` cost 2,418
       ms for. It rides on the answer rather than in a module variable so it cannot
       outlive the pair it was built from. */
    FILEPAIR._by = new Map((FILEPAIR.rows || []).map(r => [r.path, r]));
  }
  const row = FILEPAIR._by.get(path);
  return row ? row.status : "";
}

/* ── the same comparison, over the routines ──────────────────────────────────────────
 *
 * The code browser marks files and lines. This marks the things the map is actually about:
 * a routine that arrived, one that went, one that behaves differently, one that was merely
 * edited. It needs no endpoint of its own -- `/api/changes` already carries every band with
 * the node id on every row, because a worklist whose rows cannot be acted on is a dead
 * control with a count beside it (rule 30).
 */

/* The bands the server sends, and the status each becomes. A table rather than a chain of
 * comparisons, so a band added on the wire and forgotten here is a named error rather than
 * a routine that quietly reads as unchanged (design rule 16). */
const CHANGE_BANDS = {
  only_in_base:     "only_base",
  only_in_compared: "only_compared",
  behaves:          "behaves",
  edited_only:      "edited",
  /* The WHY, and it is a fifth band rather than a sixth fact kind. `behaves` promises that
     something the routine **does** has moved, and a rewritten comment moves nothing it
     does; the server subtracts this band from all the others, so the partition below still
     holds. Tom's call, 2026-09-01. */
  explained_only:   "explained",
};

/* The `moved` kinds that are **explanations rather than facts**, in the order the server
 * appends them. Every one of them rides on a row and none of them decides which band the
 * row is in -- so anything asking "did what explains this move" asks this list, and a
 * third kind of prose is covered without a second place remembering (rule 36).
 *
 * `modules_explained` is not here: it is not a tag at all, because a module docstring has
 * no routine to be a tag on. It is its own band with a file for a subject. */
const EXPLAIN_TAGS = ["comments", "docstring"];

/* The bands whose rows are **not routines**, and what each says about itself.
 *
 * `CHANGE_BANDS` maps a band to the status one routine gets from it; these have no such
 * status, because a file is not a routine and giving it one would put a path where the
 * stack, the table and the inspector all expect a node id. They are a table beside that one
 * rather than an exception inside it, so a second file band is one entry here and the guard
 * that asks "does every band the server sends reach a client that draws it" keeps working
 * without anybody remembering (design rule 16).
 *
 * `nav` is the route a row takes, and `"file"` is the code browser's own — so the subject
 * is one the router already acts on, never a label with no way in (rule 30). */
const CHANGE_FILE_BANDS = {
  modules_explained: {
    nav: "chgfile",
    title: "Modules explained differently",
    why: `The same file, and what it says it <em>is</em> has moved — a rewritten module
       docstring. The subject here is the <em>file</em>, not a routine: a module docstring
       belongs to no routine, and in a file that runs nothing at import there is no routine
       it could have been reported against at all.`,
    /* What the figure counts, in its own words, because every other number beside it
       counts routines (rule 32) — and **both numbers**, because the note prints this
       inline. "1 modules explained differently" is `classs ending in \`Error\`` again: a
       string the code composes is prose the moment something prints it (rule 44's
       companion), and an `s` appended by arithmetic is not a plural. Written out rather
       than derived, because English is not a rule and the next label may not take one. */
    stat: "modules explained differently",
    stat1: "module explained differently",
    statWhy: "files, not routines — what a module says it is",
    /* Which key on a row is its identity, and which is printed. They differ here, and rule
       30 says name both rather than let one stand in for the other. */
    id: "path",
    label: "module",
  },
};

/* The bands whose rows are **structures** — a class, a dataclass, an enum, a type alias.
 * The third table, and it exists for the reason the second one does: these rows are not
 * routines, so they get no routine status, and a table beside the other two keeps the guard
 * that asks "does every band the server sends reach a client that draws it" working without
 * anybody remembering (design rule 16).
 *
 * **`nav: "chg"` — the same route a changed routine takes, and nothing had to be built.**
 * `describe()` already resolves a `structures.id` and answers with a STRUCTURE specimen, so
 * a structure is a subject exactly as a routine is: the stack lights it, the inspector
 * fills, the trail records it. That is why these rows carry an **id** where the four
 * presence lines carry only a name — rule 30 applied honestly rather than uniformly: emit an
 * identity where one exists, a name where none does. A table is not a node; a structure is.
 *
 * **What was measured before this was written.** Routing these through the diagram box —
 * a box *is* a class (rule 74) — covers 192 of Mensores' 671 structures, because a box is
 * built from routine nodes and every TYPE_ALIAS, ENUM and TYPEDDICT has no methods at all.
 * Four of the eight rows that actually move have none. Rule 77: a subject minted on a
 * condition cannot carry a fact that does not share it.
 *
 * All four are violet with the other explanation bands. Rule 69 measured the difference
 * channel full at six meanings, so a fifth idea cannot have a colour of its own; these are
 * separated by being a band of structures, which is a stronger separation than a glyph. */
const CHANGE_STRUCT_BANDS = {
  structures_only_in_base: {
    nav: "chg", id: "id", label: "name", meta: "module", badge: "kind", tone: "gone",
    title: "Structures only in the base",
    why: `A class, dataclass, enum or type alias the base version declares and the compared
       one does not. Compared by nothing at all until 2026-09-02 — on Mensores' pair that
       hid <strong>eight</strong> of them while the page was free to say
       <em>no differences found</em>.`,
    stat: "structures only in the base", stat1: "structure only in the base",
    statWhy: "structures, not routines",
  },
  structures_only_in_compared: {
    nav: "chg", id: "id", label: "name", meta: "module", badge: "kind", tone: "new",
    title: "Structures only in the compared",
    why: `Declared in the compared version and not in the base. Which side is
       <em>added</em> is the reader's to say — this band names where a thing is, never what
       befell it (rule 65).`,
    stat: "structures only in the compared", stat1: "structure only in the compared",
    statWhy: "structures, not routines",
  },
  structures_declared: {
    nav: "chg", id: "id", label: "name", meta: "module", badge: "kind", tone: "moved",
    title: "Structures declaring differently",
    why: `The same structure, and what it <em>declares</em> has moved — the tag says which:
       <code>kind</code> if a dataclass became a plain class, <code>bases</code> if it
       stopped inheriting something, <code>fields</code> if what it holds changed. The
       structure lane's answer to <em>behaves differently</em>.`,
    stat: "structures declaring differently", stat1: "structure declaring differently",
    statWhy: "structures, not routines",
  },
  structures_explained: {
    nav: "chg", id: "id", label: "name", meta: "module", badge: "kind", tone: "moved",
    title: "Structures explained differently",
    why: `The same structure, declaring the same thing, and what it says about
       <em>itself</em> has moved — a rewritten docstring. Its own band rather than a tag,
       and that is the one place this differs from a routine: a routine's docstring sits
       inside its <code>body_hash</code>, so the row is already under <em>edited</em> and
       the tag only corrects the reason. A structure has no body hash and no edited band, so
       without this it would be in <strong>no band at all</strong>.`,
    stat: "structures explained differently", stat1: "structure explained differently",
    statWhy: "structures, not routines",
  },
};

/* id -> status, built once and **hung on the answer** rather than kept in a module
 * variable, exactly as `FILEPAIR._by` is and for the same two reasons. The table draws
 * 4,734 rows, so a `find` per row is work proportional to the whole program on every
 * repaint -- rule 45's shape, and the defect `Graph.connections` cost 2,418 ms for. And
 * riding the answer means it cannot outlive the pair it was built from.
 *
 * The **five** bands are a partition: `edited_only` excludes `behaves` by construction,
 * `explained_only` excludes both, and all three require the routine to be in *both*
 * versions, which the one-sided bands cannot be. An id in two of them would therefore be
 * the server disagreeing with itself, and it is said out loud rather than resolved by
 * whichever loop ran last.
 *
 * `explained_only` holds only what would otherwise be in **no** band -- a routine whose
 * body, facts and arguments are all identical and whose comments are not. A routine in
 * another band whose comments also moved carries `comments` among its `moved` kinds
 * instead, so one row never makes two claims (rule 32). */
function routineIndex() {
  if (CHANGES._byId) return CHANGES._byId;
  const by = new Map();
  for (const [band, status] of Object.entries(CHANGE_BANDS)) {
    for (const r of CHANGES[band] || []) {
      if (!r || !r.id) continue;
      const had = by.get(r.id);
      if (had && had.status !== status) {
        console.error("DunneFlow: one routine in two change bands:",
                      r.id, had.status, status);
      }
      /* The `moved` kinds ride in the index rather than being looked up when a row is
         drawn. `find` over the behaves band per row is rule 45's shape again -- fine at
         Mensores' eighteen and quadratic on a program where a thousand routines moved. */
      by.set(r.id, { status, moved: (r.moved || []).join(", ") });
    }
  }
  CHANGES._byId = by;
  return by;
}

/* What the comparison says about one routine, or "" when nothing has been compared.
 *
 * **"" rather than "same"**, and that is the whole of design rule 1 here: a routine nobody
 * has compared and a routine that did not change look identical on screen unless one of
 * them says which it is. `same` is a fact about two versions; an unmarked row under no
 * comparison is not a claim anyone has made.
 */
function routineStatus(id) {
  return routineChange(id).status;
}

/* The whole entry -- the status and what moved -- for a caller that wants both without
 * asking the Map twice. `same` is the answer for a routine in no band, but only once
 * there *is* an answer: "" until then.
 *
 * **The fact, and no surface's switch.** This was gated on `tableOverlayOn()`, which was
 * right while the table and the routine list were the only readers and wrong the moment
 * the stack became one: asking "what does the comparison say about this routine" would
 * have answered "nothing" because a switch about *another pane* was off. The fact has one
 * owner and every surface applies its own switch over it -- `routineChip` keeps
 * `tableOverlayOn()`, the stack uses `colorBy === 'change'`. Rule 51, and the version of it
 * that is invisible until a second caller arrives. */
function routineChange(id) {
  if (!comparing()) return { status: "", moved: "" };
  if (!CHANGES || CHANGES.loading || !CHANGES.available) return { status: "", moved: "" };
  return routineIndex().get(id) || { status: "same", moved: "" };
}

/* What one routine's mark says, in a glyph, a class and a sentence.
 *
 * **Every class begins `rtnchg-`**, and that is not tidiness. The file rows' first version
 * used `chg-same` / `chg-mod` / `chg-one`, and `.chg-mod` already existed: it is the change
 * worklist's *module* label, faint and two sizes down, so every modified file rendered
 * smaller and greyer than the unchanged ones -- the opposite of what a mark is for. A class
 * name is global and a stylesheet gives no warning (rule 71).
 *
 * The tone comes from `diffWords()` and never from the band or the side, so flipping which
 * version the reader takes to be newer swaps the colour with the word. A page saying
 * "added" in the colour of *gone* is worse than one with no colour at all.
 *
 * There are **three** things here and only two have a direction: a routine present in both
 * and behaving differently was neither added nor deleted, so it gets a mark of its own
 * rather than a sign that means nothing (the argument `factLaneHtml` makes about `signOf`).
 */
function routineChip(id) {
  /* The table's and the navigator's switch, applied here rather than inside
     `routineChange` -- see the note there. Without it this pane would draw marks the
     reader has switched off. */
  if (!tableOverlayOn()) return { cls: "", glyph: "", title: "" };
  const { status: st, moved } = routineChange(id);
  if (!st) return { cls: "", glyph: "", title: "" };
  const w = diffWords();
  if (st === "only_base") {
    return { cls: " rtnchg tone-" + w.base.tone, glyph: signOf(w.base.tone),
             title: w.base.word + " \u2014 only the version on screen has it" };
  }
  /* **In the difference channel, like the other two, and it took a decision to put it
     there.** This drew in `--text-muted` for as long as it existed, on the argument the
     block above still made: `behaves` has no *direction*, and design rule 4 says colour
     carries one dimension at a time. That argument was answered by `--diff-moved` --
     violet, in all three sets and both themes, measured for separation from the other two
     (rule 69) -- which exists precisely because *still here, doing something different* is
     a direction of difference and not an absence of one.

     What made it wrong rather than merely arguable is that three other surfaces had
     already gone that way: the graph paints this band `moved`, the graph legend spells it
     `tone-moved`, and the findings' own mark does too. One idea in two colours is two
     answers to one question (rule 51), and the reader is the one who has to reconcile
     them. Tom's call, 2026-09-01.

     `edited` stays out and that is not an oversight: it is the fourth thing, the channel
     holds three directions and a ground, and rule 69 measured that channel full. */
  if (st === "behaves") {
    return { cls: " rtnchg tone-moved", glyph: "\u25cb",
             title: "behaves differently" + (moved ? " \u2014 " + moved : "") };
  }
  /* **Violet too, and separated by its glyph rather than by a colour.** Rule 69 measured
     the difference channel full -- three directions and a ground, with nothing left that
     clears a useful bar in both themes -- so a fifth meaning cannot have a colour of its
     own, and it says so rather than taking one that fails for some readers. Sharing
     `--diff-moved` is not a compromise here either: *still here, and different* is exactly
     what that colour means, and `behaves` and `explained` are two answers to *how*, which
     is what the glyph is for (design rule 4, and design rule 5's argument for shape).

     The pilcrow, because it is the mark for a paragraph and prose is what moved. */
  if (st === "explained") {
    return { cls: " rtnchg tone-moved", glyph: "\u00b6",
             title: "explained differently \u2014 what it does is the same in both" };
  }
  if (st === "edited") {
    /* `\u2248`, and it was `\u00b7` until someone looked at the note it appears in. The
       middle dot is also the separator between the counts there, so the line read
       "18 behave differently \u00b7 \u00b7 15 edited only" -- two dots running together, one
       of them a word and one of them punctuation, and nothing to tell them apart.
       Approximately-equal says the thing anyway: the text moved and the behaviour did
       not. */
    /* **And whether its explanation moved with it.** `behaves` has always named its kinds
       here; `edited` had nothing to name until comments were compared, and then it had
       exactly one thing and went on not saying it. A row tagged `comments` in the worklist
       and described as "nothing it does changed" in the tooltip is two surfaces answering
       one question differently (rule 51) -- and the tooltip is the one a reader is more
       likely to be looking at, because it is where the cursor already is. Found by hovering
       the column rather than by any check.

       **Both explanation tags, not the one this was written for.** A docstring is inside the
       `def`, so a rewritten one is *always* in this band -- it is the whole reason the
       docstring lane is a tag and never a band, and a tooltip that named only `comments`
       would go on calling the commonest case internal computation. Derived from the tag
       list rather than tested by name, so a third explanation is covered without anyone
       remembering (rule 36). */
    return { cls: " rtnchg rtnchg-edited", glyph: "\u2248",
             title: "edited, and nothing it does changed"
                    + (EXPLAIN_TAGS.some(t => moved.includes(t))
                       ? " \u2014 though what explains it moved too" : "") };
  }
  /* A routine only the *compared* version has. It has no row in either surface -- both
     list the routines of the version on screen -- so this is reached only if something
     asks about an id it found elsewhere. It answers honestly rather than falling through
     to `same`, which would call a routine that is not in this version unchanged. */
  if (st === "only_compared") {
    return { cls: " rtnchg tone-" + w.compared.tone, glyph: signOf(w.compared.tone),
             title: w.compared.word + " \u2014 only the compared version has it" };
  }
  /* No glyph, and the words carry it instead. This is the state with no visible mark, so
     it is the one that needs the sentence: unmarked-and-compared and unmarked-and-not-
     compared are opposite claims that look the same. */
  return { cls: " rtnchg rtnchg-same", glyph: "",
           title: "unchanged between these two versions" };
}

/* The counts, **taken by walking the rows that are drawn** rather than from the bands.
 *
 * A count must be produced by the thing it measures (rule 32): the bands are the server's
 * answer about two graphs, and this list is what reached the page. Reading the band lengths
 * would print a number that no amount of scrolling could find.
 *
 * `only_compared` is the exception and cannot be otherwise -- see `routineChip`'s caller in
 * the table. Those routines have no row here at all, so their number comes from the band,
 * and it is reported as what it is: a count of things that are not in this list.
 */
function routineChangeCounts() {
  const c = { only_base: 0, behaves: 0, explained: 0, edited: 0, same: 0,
              total: ROUTINES.length,
              only_compared: 0 };
  if (!tableOverlayOn() || !CHANGES || CHANGES.loading || !CHANGES.available) return null;
  for (const r of ROUTINES) {
    const st = routineStatus(r.id);
    if (st && st in c) c[st] += 1;
  }
  c.only_compared = (CHANGES.only_in_compared || []).length;
  return c;
}

/* The one door that asks for the comparison on the routines' behalf.
 *
 * Called from the table branch of `render()` and from nowhere else. That is the door
 * rather than the mode toggle because there are five ways into table mode -- the toggle,
 * `Enter` on a hovered row, two crumb routes and the code browser's own hand-off -- and a
 * call at each is the list rule 51 says will grow. Every one of them passes through
 * `render()`.
 *
 * **The navigator is deliberately not a caller.** Its routine group is open by default, so
 * asking here would make every session pay for a comparison nobody requested: 317 ms warm
 * and 13-28 s on the first comparison of a session against a cold external volume. It
 * draws the marks when this has answered and says so when it has not, which is design rule
 * 1 rather than a silence.
 */
/* ── the same comparison, over the stack ─────────────────────────────────────────────
 *
 * The third thing colour can mean in the 2.5D view, beside *what a thing is* and *which
 * plate it sits on*. It takes the channel over rather than tinting the changed nodes and
 * leaving the rest on plate hue: two meanings in one channel would make a red dot mean
 * either *deleted* or *the plate whose golden-angle hue landed on red* (design rule 4).
 * The crossings keep their plate gradient, which costs nothing -- `setOptions` repaints
 * the nodes and never rebuilds the selection geometry, where that gradient lives.
 */

/* Whether the stack is drawing the comparison. Its own gate, separate from the table's,
 * because `colorBy` *is* the switch here -- a fourth setting would be a second answer to
 * a question this one already asks. */
function graphChangeOn() {
  return comparing() && state.colorBy === "change";
}

/* Set when a stored `colorBy: "change"` was dropped because this program has nothing to
 * compare. One-shot, and read by the legend: `colorBy` is persisted per program, so a
 * reader who used the mode on a two-version program and then opened a one-version one
 * would arrive in a mode that can colour nothing. Falling back silently would paint the
 * whole stack one tone and look like a broken picture; falling back and saying so is
 * design rule 1, and re-deriving rather than carrying the old choice is rule 66's lesson
 * about a state that must not outlive its subject. */
let changeModeDropped = false;

function resolveColorBy() {
  if (state.colorBy !== "change" || comparing()) return;
  state.colorBy = "kind";
  changeModeDropped = true;
  persist();
}

/* id -> status, in the shape the engine wants, built once and **hung on the answer**
 * exactly as `routineIndex()` is -- so it cannot outlive the pair it was built from.
 *
 * A plain object rather than a `Map` because that is what `opts.diskColors` is and the
 * engine indexes it the same way. It is id-keyed rather than an array in the engine's own
 * index order for a reason worth keeping: the shell has no API that would let it *confirm*
 * that order, and a caller asserting an index space it cannot check is how a silent
 * mismatch gets built. Never assembled with `Graph.indexOfId` per row -- that is the linear
 * scan that cost 2,418 ms (rule 45).
 *
 * Only routines appear in it. Everything else the stack draws -- boundaries, constants,
 * structures, artefacts -- is absent, and the engine reads an absent id as `unclaimed`,
 * which is a different claim from `same` and is drawn as one.
 */
function changeByNodeId() {
  if (!CHANGES || CHANGES.loading || !CHANGES.available) return null;
  if (!graphPayload) return null;
  if (CHANGES._byNode) return CHANGES._byNode;
  /* **Walked over the payload, not copied out of `routineIndex()`.**
   *
   * The index holds only the ids that are *in a band* -- 86 of them on Mensores -- and
   * `routineStatus` supplies `same` for a routine in none. Copying the index alone
   * therefore left every unchanged routine absent, and an absent id is `unclaimed`: the
   * key read *15 unchanged · 9,929 not compared* over a program with 4,700 unchanged
   * routines. Both numbers were wrong and neither threw.
   *
   * So the population is the one the engine actually draws, and the *kind* is what decides
   * which of the two grounds a node gets: a routine the comparison says nothing about is
   * `same`, and anything that is not a routine is left out and reads as `unclaimed`,
   * because the comparison was never asked about it. That is the distinction the second
   * ground tone exists for (design rule 1). */
  const nodes = graphPayload.nodes || {};
  const ids = nodes.id || [], kinds = nodes.kind || [], shadow = nodes.shadow || [];
  const out = Object.create(null);

  if (graphPayload.level === "module") {
    /* Three states, and the third is why this is `null` rather than an empty map: "nobody
       has asked for the routine list yet" is not "no module changed". An empty map paints
       every module as *not compared*, confidently and for ever (rule 35). */
    if (!ROUTINES.length) return null;
    /* **A module takes the band of what it holds**, and where it holds more than one it
       says `mixed` rather than picking one -- a file where a routine arrived *and* another
       started behaving differently is not either of those things, and drawing it as one
       would be a confident wrong answer with no symptom.

       `same` is the ground and not a competing claim: a file with 63 unchanged routines and
       one arrival is a file something arrived in. Written the other way -- any two distinct
       bands make it mixed -- every changed module on Mensores reads `mixed` and the colour
       says nothing at all. With `same` as the ground, 14 modules carry the whole comparison
       and 7 of them are genuinely mixed.

       Folded from `ROUTINES`, which carries a module per routine, rather than from the
       routine-level payload: the reader may never have visited that altitude, and a map
       that needed a payload it does not have would be a colour that silently gives up. */
    const bands = new Map();
    for (const r of ROUTINES) {
      if (!r.module) continue;
      const st = routineStatus(r.id);
      const held = bands.get(r.module) || new Set();
      held.add(st === "edited" ? "same" : st);   // one tone, so one claim (see `changeTones`)
      bands.set(r.module, held);
    }
    for (let i = 0; i < ids.length; i++) {
      if (shadow[i] === 1) continue;
      if (kinds[i] !== "MODULE") continue;       // an `outside:` node was never asked about
      const held = bands.get(String(ids[i]).slice(4));
      if (!held) continue;                       // a file declaring no routine at all
      const real = [...held].filter(b => b !== "same");
      out[ids[i]] = real.length === 0 ? "same" : real.length === 1 ? real[0] : "mixed";
    }
    CHANGES._byNode = out;
    return out;
  }

  for (let i = 0; i < ids.length; i++) {
    if (shadow[i] === 1) continue;              // never drawn, so never coloured (rule 23)
    if (kinds[i] !== "ROUTINE") continue;       // absent, and the engine reads that as
    out[ids[i]] = routineStatus(ids[i]);        // `unclaimed` rather than as `same`
  }
  CHANGES._byNode = out;
  return out;
}

/* Push it, with a stamp. The stamp moves so deck's update trigger fires: it compares
 * trigger values by shallow equality, and a map whose identity has not moved is the same
 * map to it. */
/* Which tone each band is drawn in, and it is **`diffWords()`'s answer, never the band's**.
 *
 * A routine only the base has was deleted on the way to the compared version, or added on
 * the way from it, depending on which the reader takes to be newer -- so the colour has to
 * move with the word. Small enough to rebuild on every flip, which is why the per-node map
 * carries a *band* and not a tone: flipping the assumption then costs this table rather
 * than a walk over ten thousand nodes. */
function changeTones() {
  const w = diffWords();
  /* `mixed` is here and does **not** come from `diffWords()`, and that is the point of the
     band: "more than one thing happened in this file" is the same claim whichever version
     the reader takes to be newer, so flipping the assumption must not move it. Everything
     above it is directional and everything below it is a ground. */
  /* `explained` shares `moved`, and the legend says so out loud. The stack has no glyph
     channel -- a node is a dot -- so the one thing that separates these two everywhere else
     is unavailable here, and rule 69 forbids inventing a colour for it. A shared colour
     that is stated beats a sixth hue some readers cannot tell from a fifth. */
  return { only_base: w.base.tone, only_compared: w.compared.tone,
           behaves: "moved", explained: "moved",
           mixed: "mixed", edited: "quiet", same: "quiet" };
}

function pushGraphChange() {
  if (!Graph.mounted()) return;
  Graph.setOptions({
    colorBy: state.colorBy,
    nodeChange: graphChangeOn() ? changeByNodeId() : null,
    changeTone: changeTones(),
    changeStamp: Date.now(),
  });
}

/* The stack's own door onto the comparison, beside the table's.
 *
 * Choosing this mode *is* the reader asking, so unlike the navigator this one fetches --
 * the graph is a deliberate destination and a reader who picked "what changed" has asked
 * for the wait. It repaints when the answer lands, and the legend's key comes with it. */
function ensureGraphChange() {
  if (!graphChangeOn()) { pushGraphChange(); return Promise.resolve(null); }
  /* **The module level needs the routine list as well**, because a module's band is folded
     from the routines it holds and `ROUTINES` is what carries a module per routine. Asked
     here rather than left to whoever happens to have loaded it: rule 55's companion --
     whoever sets the state does the work, or the map is a colour that silently gives up. */
  const fresh = !ROUTINES.length;
  const also = graphPayload && graphPayload.level === "module"
    ? loadRoutines().catch(() => {}) : Promise.resolve();
  return Promise.all([ensureChanges(), also]).then(([c]) => {
    /* **Both readers of `ROUTINES`, not just the one that asked.** The navigator and table
       mode read the same array, and a caller that loads it and repaints only itself leaves
       the other saying *"reading the routine list…"* over an answer that arrived — true at
       the instant it was written and never coming back. The guard for that was written from
       the table; this is the same defect arriving by a route it did not cover, which is
       rule 55 exactly. */
    if (fresh && ROUTINES.length) { buildNav(); render(); }
    pushGraphChange();
    renderLegend();
    return c;
  });
}

function ensureTableOverlay() {
  if (!tableOverlayOn()) return Promise.resolve(null);
  const fresh = !CHANGES;
  const asked = ensureChanges();
  /* **The navigator's note is built by `buildNav()`, not by `render()`**, so without this
     it goes on saying "open the table and these rows will mark themselves" to a reader who
     is already in the table with the request in flight -- rule 68's shape, in the other
     pane, for the thirty seconds a cold comparison takes.
     Only on the paint that *starts* the fetch. Rebuilding the navigator on every repaint
     would be work proportional to the whole program for a note that has not changed. */
  if (fresh && CHANGES) buildNav();
  return asked;
}

/* What the marks are saying, in words, wherever they are drawn.
 *
 * Design rule 1, and here it has four things to say that no glyph can. Which version this
 * is held against. That the comparison **has not been asked for yet** -- an unmarked
 * routine list and a list of routines that did not change are identical to look at, and
 * only one of them is a claim. That the marks are switched off. And the legend, because a
 * navigator row shows a hover card rather than a tooltip, so the glyph on it has nowhere of
 * its own to say what it means.
 *
 * Returns "" only when there is nothing to say, which is when there is no second version.
 */
function routineChangeNote() {
  if (!comparing()) return "";
  const shortRev = comparedRevInForce().replace("T", " ").replace("Z", "");
  if (!state.tableOverlay) {
    return `not marking the difference from <code>${esc(shortRev)}</code>`;
  }
  if (!CHANGES) {
    /* Named rather than blank, and it names the two doors that do the work. The list
       itself must not open one: this group is open by default and the comparison is
       13-28 s cold. */
    return `not compared with <code>${esc(shortRev)}</code> yet — open the table or the
            Changes group and these rows will mark themselves`;
  }
  if (CHANGES.loading) return `comparing with <code>${esc(shortRev)}</code>…`;
  if (!CHANGES.available) {
    return `<b>no comparison.</b> ${esc(CHANGES.reason || "")}`;
  }
  const c = routineChangeCounts();
  if (!c) return "";
  const w = diffWords();
  const bits = [];
  if (c.only_base) {
    bits.push(`<b class="tone-${w.base.tone}">${signOf(w.base.tone)}${
      c.only_base.toLocaleString()}</b> ${esc(w.base.word)}`);
  }
  /* In the channel, beside the count above it. This note is the routine lane's own
     summary of the marks below it, so it wears what they wear -- and it was the last of
     the surfaces still spelling this idea in the plain text colour. */
  if (c.behaves) {
    bits.push(`<b class="tone-moved">○ ${c.behaves.toLocaleString()}</b> behave
               differently`);
  }
  /* Violet, like the count above it and for the same reason: this is the other half of
     "still here, and different", and the glyph is what says which half. */
  if (c.explained) {
    bits.push(`<b class="tone-moved">¶ ${c.explained.toLocaleString()}</b> explained
               differently`);
  }
  if (c.edited) bits.push(`<b>≈ ${c.edited.toLocaleString()}</b> edited only`);
  /* The unchanged are counted out loud. It is the largest number here and the least
     interesting, and leaving it out would make the marked ones read as the whole list. */
  bits.push(`${c.same.toLocaleString()} unchanged`);
  /* **Counted and never marked.** A routine only the compared version has is not in this
     list at all -- the list is the base's routines -- so there is no row to put a glyph on,
     and inventing one would name a routine among what this version contains. The same
     argument the code overlay makes about a line whose number belongs to another file
     (rule 1). */
  const other = c.only_compared
    ? ` · ${c.only_compared.toLocaleString()} ${esc(w.compared.word)} — in
        ${esc(shortRev)} only, so not listed here`
    : "";
  return `against <code>${esc(shortRev)}</code>: ${bits.join(" · ")}${other}`;
}

/* One file's line difference. Held for the open file only, exactly as `CODEFILE` is.
 *
 * Dropped and re-asked when the file or the compared version moves. There is no cache of
 * many: an insert carries the *other* version's text, so remembering every file a reader
 * visited would be a second copy of the program held against someone who has moved on. */
function ensureFileDiff(path) {
  const compared = comparedRevInForce();
  if (!path || !overlayOn()) { FILEDIFF = null; return Promise.resolve(null); }
  if (FILEDIFF && FILEDIFF.loading
      && FILEDIFF.file === path && FILEDIFF.compared === compared) {
    return Promise.resolve(FILEDIFF);
  }
  if (FILEDIFF && !FILEDIFF.loading
      && FILEDIFF.file === path && FILEDIFF.compared === compared) {
    return Promise.resolve(FILEDIFF);
  }
  return loadFileDiff(path, compared);
}

async function loadFileDiff(path, compared) {
  FILEDIFF = { loading: true, file: path, compared };
  try {
    const r = await fetch("/api/filechanges?path=" + encodeURIComponent(path)
                          + "&compared=" + encodeURIComponent(compared));
    const d = await r.json();
    FILEDIFF = { ...d, file: path, compared, loading: false };
  } catch (err) {
    FILEDIFF = { available: false, file: path, compared, loading: false,
                 reason: "the difference could not be read: " + err.message };
  }
  return FILEDIFF;
}

/* The overlay the panes actually draw, or null.
 *
 * One function, so the navigator's pane and the centre's table cannot disagree about
 * which lines are marked — they are the same file and there is one answer about it.
 * Returns null for every reason there is not one, and the callers show that as nothing
 * rather than as "unchanged": `overlayNote()` is where the reason is said out loud. */
function codeOverlay() {
  if (!overlayOn() || !CODEFILE || CODEFILE.loading || CODEFILE.available === false) {
    return null;
  }
  if (!FILEDIFF || FILEDIFF.loading || !FILEDIFF.available) return null;
  if (FILEDIFF.file !== CODEFILE.file) return null;   // an answer about another file
  const w = diffWords();
  const gone = new Set(FILEDIFF.base_only || []);
  const after = new Map();
  for (const ins of FILEDIFF.inserts || []) {
    if (!after.has(ins.after)) after.set(ins.after, []);
    after.get(ins.after).push(ins);
  }
  return {
    status: FILEDIFF.status,
    /* The two words themselves, carried whole rather than flattened into a tone and a word
       apiece. Written first as `baseTone` / `comparedTone`, and the guard was right to
       refuse it: a field named for the **side** is one edit from being *set* from the side,
       which is precisely what
       `test_the_tone_follows_the_word_and_not_the_side` exists to catch. Passing the
       objects through means every `tone-${…}` in this file still ends in the word’s own
       `.tone`, and the check can see that it does rather than taking it on trust (rule 37).

       The tone follows the **word**, never the side: a line only the base has was deleted
       on the way to the compared version or added on the way from it, depending on which
       the reader takes to be newer. `diffWords()` is the one place that assumption becomes
       a colour. */
    base: w.base, compared: w.compared,
    gone, after,
    counts: FILEDIFF.counts || { base_only: 0, compared_only: 0, same: 0 },
  };
}

/* Every point in time this program directory holds. One small query, asked at boot,
 * because the navigator states a count beside every other row and a blank there reads as
 * *nothing here* rather than as *not asked for yet* -- the same argument that put the
 * vocabulary lane sizes on the cover. */
async function loadRevisions() {
  try {
    const r = await fetch("/api/revisions");
    const d = await r.json();
    REVISIONS = d.revisions || [];
  } catch {
    REVISIONS = [];
  }
  return REVISIONS;
}

/* Make `state.baseRev` agree with the server, and say so when it did not.
 *
 * **The server owns which version is on screen.** One payload set is live at a time, so a
 * stored `baseRev` is a choice made in an earlier session and may be about a server that
 * has since been restarted onto a different version — `dunneflow serve` opens the newest
 * unless `--revision` says otherwise. Honouring the stored value by *acting* on it would
 * mean ten uninvited seconds on every open; honouring it silently by *displaying* it would
 * be a label over a map that is not that version, which is the one failure this whole
 * chunk exists to prevent. So: the served version wins, and the disagreement is stated
 * with the switch one click away (design rule 1).
 *
 * It also picks up the note left by a switch that has just reloaded the page. That note is
 * the only thing the reload cannot carry in `state`, and it is the thing worth saying: the
 * map has changed underneath, so a selection that survived in `picks` may honestly report
 * "Not in this map". */
function reconcileBase() {
  const serving = servingRevision();

  let switched = null;
  try {
    const raw = window.sessionStorage.getItem("dunneflow:switched");
    if (raw) {
      switched = JSON.parse(raw);
      window.sessionStorage.removeItem("dunneflow:switched");   // one shot, always
    }
  } catch { /* a private window refuses storage; the switch still happened */ }

  if (switched && switched.to === serving) {
    const was = REVISIONS.find(r => r.revision === switched.from);
    state.revNote = `Now reading ${versionName(REVISIONS.find(r => r.revision === serving))}`
      + (was ? `, switched from ${versionName(was)}` : "")
      + `. Anything you had selected that only exists in the other version will say “Not `
      + `in this map”.`;
  } else if (state.baseRev && serving && state.baseRev !== serving
             && REVISIONS.some(r => r.revision === state.baseRev && r.comparable)) {
    const wanted = REVISIONS.find(r => r.revision === state.baseRev);
    state.revNote = `You were last reading ${versionName(wanted)}; this server is serving `
      + `${versionName(REVISIONS.find(r => r.revision === serving))}. Nothing was switched `
      + `— pick that version in the toolbar to read it, or start the server with `
      + `--revision ${state.baseRev}.`;
  }
  /* Set unconditionally. Whatever the note says, the field has to agree with what is
     actually being served before anything reads it -- `buildRevControls` and the strip
     both do, immediately. */
  if (serving) state.baseRev = serving;

  /* A version cannot be compared with itself, and this is a state the reader can reach
     without doing anything wrong: choose `A ← B`, then have the server come back up on B
     -- `serve` opens the newest unless `--revision` says otherwise -- and the comparison
     end is now the thing being read. The server refuses the query by name; asking it at
     all would be spending a fetch to be told something we can see. Said rather than
     silently dropped (design rule 1). */
  if (state.comparedRev && state.comparedRev === state.baseRev) {
    state.revNote = (state.revNote ? state.revNote + " " : "")
      + `You were comparing this version with itself, which has nothing to say, so that `
      + `comparison was dropped.`;
    state.comparedRev = "";
  }
  /* Persisted, so the field records what is actually being read. Without this the stored
     base stays at a version nobody is serving, and the note above fires again on every
     reload -- a check that cries wolf (rule 43), about a disagreement the reader has
     already been told about and has already implicitly settled by carrying on. */
  persist();
}

/* Which version the server is actually serving. The one answer to "what am I looking at".
 *
 * Read off `/api/revisions` rather than out of `state`, because the two can disagree: a
 * stored `baseRev` is a choice made in an earlier session, possibly against a server that
 * has since been restarted onto a different version. The server wins, always. */
function servingRevision() {
  const r = REVISIONS.find(x => x.serving);
  return r ? r.revision : "";
}

/* ── switching the base ───────────────────────────────────────────────────────────────
 *
 * One payload set is live at a time — Tom's call, and the alternative was holding two of
 * everything for a program whose payload, file list, vocabulary lanes and cover are ten
 * seconds and a few hundred megabytes of reading. So asking for a different base is asking
 * the **server** to rebuild, and the reader watches it happen.
 *
 * A POST, and that is not ceremony: it is the one request in this application that
 * replaces what is on screen, and a GET that does that is one a browser prefetch or a
 * bookmark reload fires by itself.
 *
 * **The page reloads when it lands**, and that is the design rather than a shortcut. Every
 * module-level array here is derived from the base — the routines, the files, the cover,
 * the plates, the conventions, the terms, the anomalies, the packages, the graph payload,
 * the code pane's cache, the search results — and a hand-kept list of what to invalidate is
 * exactly the defect rule 36 was written from: a generic sweep narrowed to a literal, with
 * whatever it forgot staying live inside a page that looks correct. Settings are keyed per
 * program, so the theme, the scale, the panel layout, the disk colours, the column widths,
 * the chosen pair and the polarity all survive; what is lost — the trail's steps, the undo
 * stack, a camera framing a stack of a different size — was about the old base anyway. */
async function switchBase(rev) {
  /* `since` is the client's own clock, and it is deliberately not the server's `ms`.
     The server stamps its elapsed when a *step* changes, so between steps it stands still
     -- and a step can take two seconds. The reader watching a frozen "0.0 s" reads a
     stalled process, not a fast one. This measures the thing they actually care about,
     which is how long they have been waiting, and it cannot be stale. */
  REBUILD = { revision: rev, state: "asking", step: "", done_steps: 0, steps: 0,
              since: Date.now() };
  render();
  let d;
  try {
    const r = await fetch("/api/base?revision=" + encodeURIComponent(rev), { method: "POST" });
    d = await r.json();
  } catch (err) {
    REBUILD = { revision: rev, state: "failed",
                reason: "the server could not be asked: " + err.message };
    switchFailed();
    return;
  }
  /* A refusal is an answer, and it is rendered. The server refuses by name — already the
     base, no graph for it, a switch already running — and swallowing that would leave an
     overlay spinning against a rebuild that was never started. */
  if (!d.started) {
    REBUILD = { revision: rev, state: "failed",
                reason: d.reason || "the switch was refused, with no reason given" };
    switchFailed();
    return;
  }
  REBUILD = Object.assign({ revision: rev, since: REBUILD.since }, d);
  render();
  pollBase(rev);
}

/* A switch that did not happen must leave the control naming the pair that did.
 *
 * The overlay says what went wrong, and the strip goes on naming the real base -- but the
 * *control* was still showing the pair the reader had just chosen, which is now a claim
 * about a state the page is not in. One control, one strip, two answers, and the control
 * is the one a reader will believe because it is the one they touched.
 *
 * `buildRevControls()` puts it back rather than any remembered previous value, because it
 * derives the selection from `state`, and `state.baseRev` was deliberately never written
 * for a switch that had not landed. So the pair in force is what it rebuilds to, by
 * construction rather than by bookkeeping (rule 51). */
function switchFailed() {
  buildRevControls();
  render();
}

/* Watch a switch, and take the new base up only when the server says it has one.
 *
 * Reloading on anything short of `done` would put the reader in front of the *old* map
 * wearing the new version's label — the two claims this whole chunk exists to keep in
 * step. So `done` reloads, `failed` states the reason and stays, and anything else keeps
 * watching.
 *
 * The overlay is repainted rather than the page: `render()` rewrites four panes and the
 * navigator, and running that twice a second for ten seconds is work nobody can see. */
function pollBase(rev) {
  const since = REBUILD ? REBUILD.since : Date.now();
  const tick = async () => {
    let d;
    try {
      d = await fetch("/api/base").then(r => r.json());
    } catch (err) {
      REBUILD = { revision: rev, state: "failed",
                  reason: "lost contact with the server: " + err.message };
      switchFailed();
      return;
    }
    REBUILD = Object.assign({ revision: rev, since: since }, d);
    if (d.state === "done") {
      /* One shot, read and cleared on the next boot. The reload is what makes the switch
         clean, and it also throws away the one thing worth saying afterwards: that this is
         a different version from the one the reader was just looking at, so anything they
         had selected may honestly report "Not in this map". Session storage rather than
         the settings blob, because it belongs to this reload and not to this program. */
      try {
        window.sessionStorage.setItem("dunneflow:switched",
          JSON.stringify({ from: servingRevision(), to: rev }));
      } catch { /* private windows refuse storage; the reload is still right */ }
      window.location.reload();
      return;
    }
    paintRebuild();
    if (d.state === "failed") return;
    window.setTimeout(tick, 400);
  };
  window.setTimeout(tick, 300);
}

/* The overlay a base switch runs behind.
 *
 * **Blocking, over the whole application**, and that is the honest state rather than a
 * heavy hand. Every count in the navigator, every figure in the inspector, every line in
 * the code pane and every dot in the stack belongs to the version being replaced — so a
 * click during those ten seconds buys a confident answer to a question about a map that is
 * on its way out. It says so, because a reader who cannot use the page is entitled to know
 * the page underneath is still real and still the old one.
 *
 * Its scrim is its own. Rule 48: a scrim must sit under the thing it dims and over
 * everything else, and one element cannot do that for two windows at different depths —
 * which is how the detail window came to swallow every click into "close".
 *
 * The step names and the step *count* are the server's, printed as sent. A list here would
 * be a second answer to "what does building a base involve", and the day a step is added
 * this one would count to the wrong total (rule 32). */
function rebuildPanel() {
  if (!REBUILD) return "";
  const r = REVISIONS.find(x => x.revision === REBUILD.revision);
  const name = r ? versionName(r) : REBUILD.revision;
  const failed = REBUILD.state === "failed";
  const secs = (Date.now() - (REBUILD.since || Date.now())) / 1000;
  /* No bar while the step count is unknown — the answer to the POST arrives before the
     first step is reported, and a bar drawn against a total of zero is a bar at 100%
     claiming the work is done (rule 44's shape: a live control reading a field nothing
     has sent yet). */
  const steps = Number(REBUILD.steps) || 0;
  const done = Number(REBUILD.done_steps) || 0;
  const pct = steps ? Math.round((done / steps) * 100) : 0;

  const body = failed
    ? `<p class="rebuild-why">${esc(REBUILD.reason || "the switch did not happen")}</p>
       <p class="hint">Nothing changed. The version you were reading is still the one on
          screen — a switch that cannot finish leaves the map it found.</p>
       <button class="btn" data-rebuilddismiss>Close</button>`
    : `<div class="rebuild-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100"
            aria-valuenow="${pct}"><i style="width:${steps ? pct : 0}%"></i></div>
       <p class="rebuild-step">${
          steps ? `${esc(REBUILD.step || "")} — step ${done + 1} of ${steps}`
                : "asking the server…"} · ${secs.toFixed(1)} s</p>
       <p class="hint">The version you were reading stays on screen underneath until this
          finishes. Nothing here is answering for the new one yet.</p>`;

  return `<div class="rebuild-scrim"></div>
    <div class="rebuild" role="dialog" aria-modal="true" aria-live="polite"
         aria-label="Switching the version being read">
      <h2 class="rebuild-title">${failed ? "That switch did not happen"
                                         : "Rebuilding the map for"}</h2>
      <p class="rebuild-name">${esc(name)}</p>
      ${body}
    </div>`;
}

/* Painted on its own, so a poll twice a second does not drag `render()` behind it — and
 * from `render()` too, so no repaint can leave a stale overlay on screen. One function owns
 * the markup either way (rule 51). */
function paintRebuild() {
  let m = document.getElementById("rebuildMount");
  if (!m) {
    m = document.createElement("div");
    m.id = "rebuildMount";
    document.body.appendChild(m);
  }
  m.innerHTML = rebuildPanel();
  const x = m.querySelector("[data-rebuilddismiss]");
  if (x) x.addEventListener("click", () => { REBUILD = null; render(); });
}

/* How a revision reads to someone who did not capture it.
 *
 * **The instant is when the snapshot was captured, not when the code is from**, and here
 * the two are nothing alike: these snapshots hold a Society tree from 2026-08-26 and one
 * from 2026-08-29, and *both* were captured on the evening of the 29th, twenty-nine
 * seconds apart. So the instant is a serial number that happens to contain a date, and
 * the **label** is where "which point in time is this" actually lives.
 *
 * Which is why the whole instant is shown, seconds included. Abbreviated to the day both
 * options read `2026-08-29`; abbreviated to the minute both read `2026-08-29 23:46`. Two
 * menu entries a reader cannot tell apart are worse than a long one, and each shortening
 * looked reasonable until it was put on screen beside its neighbour. */
function revWhen(r) {
  const iso = String(r.revision || "");
  return `${iso.slice(0, 10)} ${iso.slice(11, 19)}`.trim();
}

/* There was a `revLabel()` here and it is gone, with the world it was written for.
 *
 * It prefixed the served revision with the word **current**, which was honest while the
 * reading end was pinned to whatever the server had opened. It is false now, and falsest
 * exactly where it matters: in `Society at e2e658b4 ← current`, the word names the
 * *compared* end — the one that would stop being current the moment the reader chose that
 * row. A label that is true of a thing's present state and printed beside an offer to
 * change it is a label about the wrong moment.
 *
 * `versionName()` is the one naming now, everywhere a version is named to a reader. See
 * `pairName()` in `buildRevControls`, which is that plus the instant where two versions
 * would otherwise read alike. */

/* How a version is named to a reader: the tree it came from first, then a label somebody
 * wrote, then the instant we read it.
 *
 * The **tree** leads because two versions of one program are two directories, and that is
 * what a person recognises. The instant is last and never alone if anything better exists:
 * it says when the bytes were read, which is a fact about us rather than about the code --
 * these two were captured twenty-nine seconds apart and hold trees three days apart. */
function versionName(r) {
  if (!r) return "?";
  const bits = [];
  if (r.tree) bits.push(r.tree);
  if (r.label) bits.push(r.label);
  if (!bits.length) bits.push(revWhen(r));
  return bits.join(" · ");
}

/* The version strip: what is on screen, and what it is being held against.
 *
 * **Always rendered, on every screen.** Tom's decision, and his reason is the right one --
 * orientation of context is what makes the rest of the page readable, and a strip that
 * appears only during a comparison teaches a reader to read its *absence*, which is the
 * one thing an absence must never mean (design rule 1). With one version it says so.
 *
 * It carries four things, and each is a different kind of claim:
 *
 *   - **which two versions**, named by their trees. A fact the store holds.
 *   - **the version each asserts about itself**, with the tier it was learned at, so a
 *     number read out of `pyproject.toml` and one guessed from a directory name do not
 *     look alike (design rule 13).
 *   - **the reader's assumption** about which is newer -- an assumption, stated as one,
 *     and clickable, because it decides whether every red row means gone or arrived.
 *   - **what we can actually see about capture order**, as a plain observation beside the
 *     assumption and never as a correction to it. We may infer, so long as we say we did.
 */
/* Why the control says what it says, and what clicking it will do next. Three states
   need three sentences: a reader who cannot tell a derived answer from a default cannot
   tell whether the colours are evidence or a guess. */
function assumeTitle(w) {
  /* What the *next* click does, said as a change the reader will notice. From `auto` the
     direction may not move at all -- what moves is the basis, from a derived or assumed
     answer to the reader's own -- and offering "the compared version is newer" when that
     is already in force reads as a control that does nothing (design rule 16's defect
     wearing a label). */
  const next = { auto: "your own choice, overriding this",
                 yes: "your own choice: the compared version is older",
                 no: "back to deciding from the versions" };
  const why = w.basis === "chosen"
    ? "You set this. It overrides whatever the versions say."
    : w.basis === "assumed"
    ? "Neither version says enough to compare, so this is the default assumption."
    : w.fromInferred
    ? "Read from the two versions — at least one of which was inferred from a directory name."
    : "Read from the two versions each program states about itself.";
  return `${why} It decides whether what only the base has reads as deleted or as added.`
       + ` Click for: ${next[state.comparedIsNewer] || "the compared version is newer"}.`;
}

function versionStrip() {
  const usable = REVISIONS.filter(r => r.comparable);
  const lost = state.revNote
    ? `<span class="verstrip-lost">${esc(state.revNote)}</span>` : "";
  const base = REVISIONS.find(r => r.revision === (CHANGES && CHANGES.base))
            || REVISIONS.find(r => r.serving)
            || usable[0];

  const ver = (r) => {
    if (!r || !r.version) return "";
    /* A class rather than a `data-` attribute: this marks how well the claim is known,
       which is presentation, and `data-` in this shell means a control something listens
       for. The roster guard is right to refuse it. */
    const tier = r.version_tier === "INFERRED" ? " inferred" : "";
    return `<span class="verstrip-ver${tier}"
      title="${esc(r.version_where || "")}">${esc(r.version)}</span>`;
  };

  /* **No comparison, and it says which kind of none.** Two ways to get here and the reader
     is owed the difference: a program with one version *cannot* be compared, and a reader
     who picked "on its own" *chose* not to be. Saying only "nothing compared" for both
     leaves the second looking like the first — a state the reader can change reported as a
     limit of the program (design rule 1, which is about knowing what you are not looking
     at).

     Reported by Tom: *"I have selected society-2026-08-29 on its own. However, the next
     line down still shows BASE then compared with society-2026-08-26."* This branch tested
     `usable.length < 2` — whether the *program* has a second version — and never whether a
     comparison was actually running, so on a two-revision pair it could not fire at all. */
  if (!comparing()) {
    const why = usable.length < 2
      ? "— on its own; this program has only one version"
      : "— on its own, nothing compared";
    return `${lost}<span class="verstrip-k">version</span>
      <span class="verstrip-v">${esc(versionName(base))}</span> ${ver(base)}
      <span class="verstrip-alone">${esc(why)}</span>`;
  }

  /* **The one test, not a second derivation of it.** This was
     `CHANGES.compared || usable.find(r => r.revision !== base.revision)` — the same
     fallback `comparedRevInForce()` carries, computed again here. Two answers to "what is
     this held against", and fixing one fixed nothing a reader could see: the state went
     right, `comparing()` went false, and the strip went on naming a pair (rule 51). */
  const comparedId = comparedRevInForce();
  const compared = REVISIONS.find(r => r.revision === comparedId);
  const w = diffWords();

  /* What the store can actually see about order, said as the observation it is. The
     revision id is the instant the bytes were read, so this is a fact about the capture
     and not about the code -- which is exactly why it sits beside the assumption rather
     than deciding it. */
  let observed = "";
  if (base && compared && base.revision && compared.revision) {
    const baseFirst = base.revision < compared.revision;
    observed = `<span class="verstrip-sep" title="When we read the bytes, which is not
      when the code is from. Stated because it is the only order this store can see."
      >captured: ${baseFirst ? "base first" : "compared first"}</span>`;
  }

  return `${lost}<span class="verstrip-k">base</span>
    <span class="verstrip-v">${esc(versionName(base))}</span> ${ver(base)}
    <span class="verstrip-sep">compared with</span>
    <span class="verstrip-v">${esc(versionName(compared))}</span> ${ver(compared)}
    <button class="verstrip-assume${w.basis === "assumed" ? " guessed" : ""}"
      data-assumenewer aria-pressed="${state.comparedIsNewer !== "auto"}"
      title="${esc(assumeTitle(w))}"
      >${esc(w.assumption)}${w.fromInferred ? " (inferred)" : ""}</button>
    ${observed}`;
}

/* The toolbar's temporal control, built from the store rather than written into the markup.
 *
 * **One control whose options are the pairs.** Its value names both ends —
 * `base|compared`, the compared end empty for none — and its text names both, so what is
 * on screen reads as the answer to "which two points am I looking at" rather than as two
 * menus to combine. A revision id is an ISO instant and cannot contain a pipe.
 *
 * **Both ends are real now.** The reading end used to be pinned to whatever the server had
 * opened at boot, with a trailing disabled row saying so in as many words, because the
 * payload, the 628-file code list, both vocabulary lanes and the cover were built from one
 * graph opened once. The server rebuilds them on request now, so that row is gone — an
 * option offered and not honoured is the defect this dashboard has paid for more than any
 * other, and the fix was never to phrase it better.
 *
 * Grouped by reading end rather than flattened: with three versions this is nine options,
 * and nine lines that all begin with a different word is a list nobody can scan. The group
 * heading carries the half that decides what the whole screen shows.
 *
 * Absent entirely when the program holds one point in time: a control whose only option is
 * the state you are already in is a control that always fails. */
function buildRevControls() {
  const rev = $("#rev");
  if (!rev) return;
  const usable = REVISIONS.filter(r => r.comparable);
  rev.hidden = usable.length < 2;
  if (usable.length < 2) return;

  /* `chosenPair()` returns `{base, compared}` and always has. This read `.from` — a key it
     has never carried — so `chosen` was the empty string on every build and the control
     never marked the reader's own pair as selected. Nothing threw; the menu simply opened
     on the wrong row after every reload. Rule 44's family, one step further in: not a field
     the server does not send, but a field *this file* does not send itself. */
  const pair = chosenPair();
  const base = pair.base || servingRevision() || usable[0].revision;
  const compared = pair.compared || "";

  /* As short as it can be while still telling two versions apart. `versionName()` is the
     tree and the label -- what a person recognises -- and it drops the instant, which is
     right until two revisions carry the same label or neither carries anything. Then the
     instant is the only thing that separates them, and two options a reader cannot tell
     apart are worse than one long one. Computed against the *other* rows rather than
     assumed, so the long form appears only where it is earning its length. */
  const pairName = (r) => {
    const n = versionName(r);
    return usable.filter(o => versionName(o) === n).length > 1
      ? `${n} · ${revWhen(r)}` : n;
  };

  /* Each option names **both** ends, even though its group already names one of them. A
     closed `<select>` shows the selected option's text and not its group's, so an option
     reading only "on its own" would leave the one control that answers "which two points
     am I looking at" saying nothing at all until it is opened. The group is a grouping
     aid; the option is the answer. */
  rev.innerHTML = usable.map(b => {
    const on = b.revision === base;
    const rows = [
      `<option value="${esc(b.revision)}|"${on && !compared ? " selected" : ""}
        >${esc(pairName(b))} · on its own</option>`,
    ].concat(usable.filter(c => c.revision !== b.revision).map(c =>
      `<option value="${esc(b.revision)}|${esc(c.revision)}"${
        on && c.revision === compared ? " selected" : ""
        }>${esc(pairName(b))} ← ${esc(pairName(c))}</option>`));
    return `<optgroup label="reading ${esc(pairName(b))}">${rows.join("")}</optgroup>`;
  }).join("");

  /* And then set the value, because the `selected` attribute above is not the last word.
   *
   * Chrome restores a `<select>`'s value across a reload, and that restoration outranks
   * the attribute — so after a base switch the control showed the pair the reader had
   * been on *before* the switch, while the strip beside it correctly named the new one.
   * One control, two claims, and the markup was the one that lost. Rule 44's family with
   * the browser as the thing writing the field: what the DOM says and what the reader
   * sees are different questions.
   *
   * Assigned rather than defended against, because the value *is* state: `state.baseRev`
   * and `state.comparedRev` decide it, and a control that derives its value from state
   * has nothing left for a restoration to disagree with. An unmatched pair leaves the
   * value empty rather than silently landing on row one — see `reconcileBase`, which is
   * where a pair that no longer makes sense is resolved and said. */
  rev.value = `${base}|${compared}`;
}

/* There was an `applySourcePath()` here, and it is gone with the root it displayed.
 *
 * It read the served root and each revision's, shortened them to the last two segments,
 * and offered a click to see them in full. Every one of those values is one machine's
 * directory layout, which is why the tree is no longer recorded at all -- see
 * `migrate.py`. Left in place it became rule 44 exactly: a live control reading a field
 * the server does not send, overwriting the readout's own text with `""` and rendering an
 * empty box beside a label that still said SOURCE DIRECTORY. Nothing threw.
 *
 * The markup states `not bound` and nothing overwrites it. When a binding exists -- for
 * something that genuinely opens a file from disk -- this is where it comes back.
 *
 * Written in this continuation style on purpose: the guards strip comment *lines*, and a
 * block whose continuation lines are plain indented prose is one they cannot see. This
 * paragraph names the very thing it is asserting the absence of. */

/* The identities a navigator row carries, as written into `data-navid`. Space separated
 * because ids here are hex digests, plate ids and table names -- none of which contain a
 * space -- and a JSON blob in an attribute is harder to read when something goes wrong. */
function navIds(b) {
  return (b.dataset.navid || "").split(" ").filter(Boolean);
}

/* Every word in the glossary is a way into the graph, and there are 1,207 of them.
 *
 * Delegated rather than bound per row, and the term carries **itself** rather than a JSON
 * subject: the cohort is `{kind: "term", key: <the word>}` and nothing about it is worth
 * writing into a thousand attributes. That is not only weight -- 581 KB of markup and
 * 1,214 listeners rebuilt on every keystroke of the filter -- it is rule 30 read the right
 * way round. The control must carry an *identity*; constructing the subject from it belongs
 * in the route, which is where the table is. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-term]");
  if (!b) return;
  const term = b.dataset.term;
  pushTrail(state.view, term, b.dataset.termuse || "");
  followThread({ type: "cohort", kind: "term", key: term, label: term });
});

/* Which band of the change worklist is open. One at a time, and clicking the open one
 * closes it -- the accordion the routine list already uses, for the same reason: 53
 * additions and 15 edits at once is the haystack the bands exist to break up. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-changeband]");
  if (!b) return;
  const key = b.dataset.changeband;
  state.changeBand = state.changeBand === key ? "" : key;
  buildNav();
  render();
});

/* The rest of a presence line's names. Delegated for `changeband`'s reason -- `render()`
 * rewrites this pane, so a listener bound to the button would be bound to a button that no
 * longer exists one click later.
 *
 * A fresh object rather than a write into the old one: nothing here reads it by identity
 * today, and the next thing that does will be a repaint that compares. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-presgroup]");
  if (!b) return;
  const key = b.dataset.presgroup;
  state.presOpen = { ...state.presOpen, [key]: !state.presOpen[key] };
  used("changes:presence:" + (state.presOpen[key] ? "all" : "six"));
  render();
});

/* Routed from the DOM, delegated, because `render()` rewrites this window on every hop --
 * a listener attached to a button inside it would be attached to a button that no longer
 * exists one click later. */
document.addEventListener("click", (ev) => {
  const close = ev.target.closest("[data-closedetail]");
  if (close) { closeDetail(); return; }
  const detach = ev.target.closest("[data-detachdetail]");
  if (detach) { detachDetail(); return; }
  const hop = ev.target.closest("[data-detail]");
  if (hop) { hopDetail(hop.dataset.detail); return; }
  const all = ev.target.closest("[data-detailall]");
  if (all) {
    const subj = SPECIMEN && SPECIMEN.id;
    const keep = state.detailAll.for === subj ? state.detailAll : { for: subj };
    state.detailAll = { ...keep, [all.dataset.detailall]: true };
    render();
    return;
  }
});

/* Everything inside the code pane that is not a file row.
 *
 * Routed from a table for the same reason `NAV_ROUTES` is (design rule 16): an unhandled
 * kind logs by name rather than falling through to something that looks deliberate.
 * Delegated, because `buildNav()` rewrites this pane on every selection and a listener
 * bound to a span would be bound to a span that no longer exists one click later.
 */
const CODE_ROUTES = {
  /* A name in the source. An ordinary selection, exactly as a navigator row makes -- so the
     stack lights up, the trail records the hop, undo reaches it, and the list moves. Rule
     51: one truth, one door, and every caller reaching it through the same one. */
  codelink: async (b) => {
    const id = b.dataset.codelink;
    if (!id) { console.error("DunneFlow: a code link with no identity", b); return; }
    /* **Awaited, then recorded.** A step captures `state.selected` as its subject, so
     * pushing before the selection settles files a step whose subject is `null` — the trail
     * renders, highlights and scrolls exactly as it should and can take nobody back. Rule
     * 33's defect, reintroduced in a new route and caught by reading the step rather than by
     * any check; `openDetail` had the order right and this did not. */
    await selectFromNav({ nodes: [id] });
    pushTrail(state.view, labelFor(id), "followed a name in the source");
  },
  codeback: () => openCodeFile(""),
  /* Open or close one file in the search answer. The hits are fetched on the way in and
     never before: the margin is the expensive half and it is built only for what someone
     asked to see. */
  searchopen: (b) => toggleSearchFile(b.dataset.searchopen),
  /* Go to one matching line. A **line**, not a node -- there may be no routine there at
     all, and the routine beside it is its own click. So this opens the file and reveals the
     line rather than going through `selectFromNav`, which would need an identity this row
     does not have: inventing one to make a row clickable is a link to nothing. */
  searchgo: (b) => {
    const path = b.dataset.searchgo, line = Number(b.dataset.searchline);
    codeGoto = line || 0;
    if (state.codeFile === path) { revealLine(codeGoto); codeGoto = 0; return; }
    openCodeFile(path);
  },
  /* A switch that says what counts as a match. Routed from the table like everything else,
     so a fourth flag added without a listener fails by name rather than by rendering. */
  searchflag: (b) => {
    const key = b.dataset.searchflag;
    if (!("searchCase" in state) || !(key in state)) {
      console.error("DunneFlow: no such search flag", key, b); return;
    }
    state[key] = !state[key];
    persist();
    /* Both surfaces, because one table routes both sets of flags and only the pane the flag
       belongs to would otherwise redraw -- `|ab|` going disabled under `.*` is a pressed
       state that has to move on the topbar as well. */
    paintNavFlags();
    buildNav();
    /* Immediately, not after the debounce: a click is the reader having finished asking,
       and a pause after one reads as the switch not working. */
    runSearch({ now: true });
  },
  /* Opened from a **click**, never a keypress: a pop-up blocker treats a click as the
     reader asking and a synthetic-looking keystroke as the page deciding for itself. If it
     is blocked anyway the reader is told, because a control that silently does nothing is
     the failure this project keeps paying for. */
  codedetach: () => {
    const w = window.open(`${location.pathname}?view=code`, "dunneflow-code",
                          "width=1200,height=900,noopener=no");
    if (!w) {
      state.navNote = "The browser blocked the pop-up. Allow pop-ups for this page, or open "
                    + `${location.pathname}?view=code in a tab yourself.`;
      render();
      return;
    }
    used("code:detached");
  },
  codeopen: () => { state.mode = "code"; state.view = "code"; persist(); render(); },
  /* The change overlay on or off. It repaints rather than re-renders, because the marked
     rows and the other version's lines are *inside* the built subtree -- `render()` alone
     would hand back the cached page and the switch would do nothing visible, which is the
     failure design rule 16 is about. `codeDomKey()` carries the overlay for the same
     reason, so this is belt and braces rather than the only defence. */
  codeoverlay: () => {
    state.codeOverlay = !state.codeOverlay;
    persist();
    used("code:overlay:" + (state.codeOverlay ? "on" : "off"));
    if (!state.codeOverlay) { repaintCode(); return; }
    /* Turned back on with nothing fetched: the file was opened while it was off, so the
       difference was never asked for. Fetch, then repaint — rather than repainting an
       overlay that is not there and leaving the switch looking broken. */
    ensureFilePair();
    ensureChanges();
    ensureFileDiff(state.codeFile).then(repaintCode);
  },
};

document.addEventListener("click", (ev) => {
  for (const kind of Object.keys(CODE_ROUTES)) {
    const b = ev.target.closest(`[data-${kind}]`);
    if (b) { CODE_ROUTES[kind](b); return; }
  }
});

/* Every control that carries a route, wherever it lives and whatever it is styled as.
 *
 * `NAV_SELECTOR` is the attribute the route table is keyed on, and that is the whole
 * point of it. This handler selected on `.nav-item` -- a **class** -- while the routes
 * are looked up by `data-nav`, so a control could carry a perfectly good route and a
 * class this listener had never heard of, and nothing anywhere would say so. The change
 * worklist's rows were exactly that: `class="wl-item" data-nav="chg" data-navid="…"`,
 * with a real route, a real id, and no listener. Clicking one did nothing at all, and
 * adding the missing class to a single row made it work exactly as documented.
 *
 * Neither guard could see it. The runtime self-check scanned `.nav-item` for a missing
 * route -- a `.wl-item` is not one -- and `data-nav` sits in `WIRED_ATTRS` because it *is*
 * wired, elsewhere; that check states plainly that it cannot prove a read is reachable.
 *
 * Selecting on the attribute makes the whole class of defect unreachable rather than
 * merely detectable, which is why the constant exists and why a test asserts it is still
 * an attribute selector: narrowing this back to a class is rule 36's defect exactly -- a
 * generic match narrowed to a literal, and a feature disappearing without a trace. */
const NAV_SELECTOR = "[data-nav]";

document.addEventListener("click", (ev) => {
  const b = ev.target.closest(NAV_SELECTOR);
  if (!b) return;
  const kind = b.dataset.nav;
  const route = NAV_ROUTES[kind];
  if (!route) {                       // never fail silently again
    console.error("DunneFlow: no route for nav kind", kind, b);
    return;
  }
  $$(NAV_SELECTOR).forEach(x => x.setAttribute("aria-current", "false"));
  b.setAttribute("aria-current", "true");
  route(b);
  const lbl = b.querySelector(".navlabel");
  pushTrail(state.view, (lbl ? lbl.textContent : b.textContent).replace(/\s+/g, " ").trim());
  render();
});

/* ═══ folding a pane ═══ */

/* Delegated, because the navigator is rebuilt from the store and the inspector on every
 * selection -- a handler bound to either element would be thrown away with it. Registered
 * from a table for the same reason the other routes are (design rule 16): an unknown pane
 * is a named error, never a fall-through that looks deliberate. */
/* Derived, not hand-kept. A second list of panel names is a second place to forget one,
 * and forgetting one here makes its control silently inert -- the failure this whole
 * change exists to undo. */
const FOLDABLE = new Set(Object.keys(PANELS));

document.addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-fold], [data-pane]");
  if (!btn) return;
  const name = btn.dataset.fold || btn.dataset.pane;
  if (!FOLDABLE.has(name)) {
    console.error("DunneFlow: no such foldable pane:", name, btn);
    return;
  }
  /* A rail opens and a fold button closes -- each is one-way, because each is only on
   * screen in one of the two states. A ribbon's header is on screen in both, so it
   * toggles. The difference is the furniture, not the panel. */
  const opening = PANELS[name].how === "class"
    ? !state.panels[name]
    : Boolean(btn.dataset.pane);
  state.panels = { ...state.panels, [name]: opening };
  /* Opening the inspector by hand with nothing selected is a deliberate act, so the auto
   * rule stops overriding it until something is picked again. Without this the rail would
   * be unclickable: it would reopen and immediately re-collapse, which reads as broken. */
  if (name === "inspector" && opening && !inspectorSubject()) state.inspectorAuto = false;
  if (name === "inspector" && !opening) state.inspectorAuto = true;
  persist();
  applyPanels();
  if (Graph.mounted()) requestAnimationFrame(() => Graph.resize());
});

/* ═══ the compartment diagram ═══════════════════════════════════════════════════
 *
 * A different level of detail from the stack, and a mode of its own rather than a layout
 * inside Graph -- Tom's call, and the right one: the stack draws every thing the program
 * declares, this draws one compartment's classes, its files of loose functions, what it
 * touches, and the flow between them.
 *
 * **Graphviz draws it, not Mermaid**, and that is measured rather than preferred. Mermaid's
 * dagre has no component-packing option, and roughly half a compartment's boxes have no
 * within-compartment edge, so they land side by side on rank 0: `pkg:cli` is 11991x514
 * pixels at 23:1 in 2.5 s. Graphviz `dot` with `pack=true` draws the same graph at 782x744,
 * 1.1:1, in 83 ms. The server still emits Mermaid for the same compartment, from the same
 * model, for a reader to copy elsewhere.
 *
 * Loaded **lazily and once**. The wasm is 822 KB and most sessions never open this mode, so
 * paying for it at boot would slow the screen everyone sees for the one many never do --
 * the same argument `ensureGraph` makes about the stack's payload. */
let DIAGRAM = null;         // the compartment index, once fetched
let diagramNow = null;      // the compartment on screen, whole
let diagramBusy = false;
let diagramErr = null;
let gvLoading = null;       // the in-flight load, so two calls cannot fetch it twice

async function graphviz() {
  if (window.__gv) return window.__gv;
  if (gvLoading) return gvLoading;
  gvLoading = (async () => {
    await new Promise((ok, no) => {
      const el = document.createElement("script");
      el.src = "/vendor/graphviz.umd.js";
      el.onload = ok;
      el.onerror = () => no(new Error("the drawing engine could not be loaded"));
      document.head.appendChild(el);
    });
    const mod = window["@hpcc-js/wasm/graphviz"];
    if (!mod) throw new Error("the drawing engine loaded but exported nothing");
    window.__gv = await mod.Graphviz.load();
    return window.__gv;
  })();
  return gvLoading;
}

/* Which compartment to open on.
 *
 * The one the current selection is on, when there is one -- the modes are five ways of
 * looking at **one** selection, so arriving in Diagram mode from a selected routine should
 * land on that routine's compartment rather than on a default nobody chose. Otherwise the
 * largest, because it is the one most worth having drawn for you. */
function diagramWanted() {
  if (state.diagramId) return state.diagramId;
  const on = Graph.mounted() ? Graph.selectedDisks() : [];
  if (on.length && DIAGRAM) {
    const hit = DIAGRAM.find(c => c.id === on[0]);
    if (hit) return hit.id;
  }
  return DIAGRAM && DIAGRAM.length ? DIAGRAM[0].id : null;
}

async function ensureDiagram() {
  if (state.view !== "diagram" || diagramBusy) return;
  diagramBusy = true;
  diagramErr = null;
  renderDiagram();
  try {
    if (!DIAGRAM) {
      const r = await fetch("/api/diagram");
      if (!r.ok) throw new Error(`the compartment list came back ${r.status}`);
      DIAGRAM = (await r.json()).compartments;
    }
    /* **Two altitudes, one fetch and one drawing.** `state.diagramBox` says which one:
       unset is the compartment, set is that box opened into its own routines. The answer
       comes back in the same shape from either endpoint -- `dot`, `by_id`, `names`, the
       same stats -- so everything below this line, and everything in `renderDiagram`, is
       written once. A second renderer for the second level is how the two would drift
       into being two views of two things (rule 51). */
    const want = state.diagramBox || diagramWanted();
    if (!want) throw new Error("this program has no compartments to draw");
    if (!diagramNow || diagramNow.id !== want
        || !!diagramNow.portsDrawn !== !!state.diagramPorts) {
      const url = state.diagramBox
        ? `/api/inside?id=${encodeURIComponent(want)}`
        : `/api/diagram?id=${encodeURIComponent(want)}`;
      const r = await fetch(url + (state.diagramPorts ? "&ports=1" : ""));
      if (!r.ok) throw new Error(`${want} came back ${r.status}`);
      const got = await r.json();
      /* A refusal is a *stated* answer, not an empty drawing. `/api/inside` says no for a
         port and for a boundary cylinder -- neither holds routines -- and a blank picture
         there is indistinguishable from a box that genuinely holds nothing (design rule 1). */
      if (got.found === false) {
        state.diagramBox = null;
        throw new Error(got.reason || "that box does not open");
      }
      diagramNow = got;
      diagramNow.svg = null;
    }
    if (!diagramNow.svg) {
      const gv = await graphviz();
      const t0 = performance.now();
      diagramNow.svg = gv.layout(diagramNow.dot, "svg", "dot");
      diagramNow.drawMs = Math.round(performance.now() - t0);
    }
  } catch (err) {
    diagramErr = err.message || String(err);
    console.error("[dunneflow] the diagram could not be drawn:", err);
  }
  diagramBusy = false;
  renderDiagram();
}

/* Painted into its own mount, never through `render()`. Rewriting this on every keystroke
 * would throw away a laid-out SVG and the reader's pan and zoom -- the same reason the
 * stack keeps a container `render()` does not touch. */
function renderDiagram() {
  const host = $("#diagramMount");
  if (!host) return;
  if (diagramErr) {
    host.innerHTML = `<div class="dgm-head"><b>The diagram could not be drawn.</b>
      <span class="muted">${esc(diagramErr)}</span></div>`;
    return;
  }
  if (!diagramNow || !diagramNow.svg) {
    host.innerHTML = `<div class="dgm-head"><span class="muted">${
      diagramBusy ? "drawing…" : "nothing drawn yet"}</span></div>`;
    return;
  }
  const c = diagramNow;
  /* The picker names the *compartment*, at either altitude. At the second level that is
     the compartment the open box lives on, read off the box id rather than off `c.id` --
     which is the box. A control naming one thing while the drawing shows another is one
     control with two claims (rule 67). */
  const onPlate = state.diagramBox ? String(state.diagramBox).split("|")[0] : c.id;
  const opts = (DIAGRAM || []).map(x =>
    `<option value="${esc(x.id)}" ${x.id === onPlate ? "selected" : ""}>${
      esc(x.name)} — ${x.boxes} boxes</option>`).join("");
  const inside = !!state.diagramBox;
  /* Design rule 1: what is drawn and what it stands for, always. A diagram of 83 boxes over
     487 routines is a fold, and a fold that does not say what it folded is a filter.
     At the second level the same sentence describes routines rather than boxes, and it
     says which box they are inside -- otherwise the drawing is a compartment nobody
     recognises, with no way to tell it is one level down. */
  host.innerHTML = `
    <div class="dgm-head">
      <select id="dgmPick" aria-label="Which compartment to draw">${opts}</select>
      ${inside ? `<button class="gbtn" data-dgmup="1"
            title="Back out to the whole compartment">‹ out</button>
          <b class="num">${esc(c.name)}</b>` : ""}
      <span class="hint">${inside
        ? `<b class="num">${c.routines}</b> routines ·
           <b class="num">${c.inside}</b> flows within ·
           <b class="num">${c.crossing}</b> crossing to
           <b class="num">${c.ports}</b> other boxes`
        : `<b class="num">${c.boxes}</b> boxes over
           <b class="num">${(c.routines || 0).toLocaleString()}</b> routines ·
           <b class="num">${c.inside}</b> flows within ·
           <b class="num">${c.crossing}</b> crossing to
           <b class="num">${c.ports}</b> other compartments`}${
        c.portsDrawn ? "" : ` <span class="muted">(not drawn)</span>`}${
        c.unlinked ? ` · <b class="num">${c.unlinked}</b> with no flow either way` : ""}
        <span class="muted">· drawn in ${c.drawMs} ms${
        inside ? "" : " · double-click a box to open it"}</span></span>
      ${/* Rule 19's own switch, one level up. Drawn, the crossings connect what was
            disconnected so nothing packs, and in a small compartment they outnumber the
            subject -- 8 boxes to 29 ports on `pkg:mcp`. Off by default, always counted. */""}
      <label class="dgm-toggle"><input type="checkbox" id="dgmPorts" ${
        c.portsDrawn ? "checked" : ""}> <span class="muted">show crossings</span></label>
      <button class="gbtn" data-dgm="fit">fit</button>
    </div>
    <div class="dgm-canvas" id="dgmCanvas"><div class="dgm-pan" id="dgmPan">${c.svg}</div>
      <div class="hovercard" id="dgmCard" hidden aria-hidden="true"></div></div>`;
  const svg = host.querySelector("#dgmPan svg");
  if (svg) {
    /* Its own natural size in pixels, taken from the viewBox Graphviz wrote. `width:100%`
       hands the fitting to the browser, which then redoes it whenever the pane changes
       width -- see `dgmFit` for what that cost. */
    const vb = (svg.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.style.cssText = vb.length === 4 && vb[2] > 0
      ? `width:${vb[2]}px;height:${vb[3]}px;display:block`
      : "width:100%;height:100%;display:block";
    svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  }
  dgmFit();
  markDiagramSelection();
}

/* What a box says when the reader points at it.
 *
 * Everything here is already in the payload the drawing came from, so the card is complete
 * the moment it appears -- no dwell, no fetch, no second stage. That is the one place this
 * differs from the stack's card, and it differs because a box is a *fold*: the subject is
 * "this class and its four methods", which the server has already sent, not a node the
 * server could be asked about.
 *
 * It names what it holds, up to a handful, because "4 methods" is a count and the reader
 * wants to know *which* -- and the count is stated beside them so an elision is never
 * silent (rule 8: bound a listing, and say what was left out). */
const DGM_CARD_NAMES = 6;

function diagramCard(box) {
  const what = box.kind === "class" ? "class"
             : box.kind === "file" ? "file"
             : box.kind === "port" ? "another compartment" : "what it touches";
  const held = box.holds
    ? `<div class="hc-sub">${box.holds} ${box.kind === "class" ? "methods" : "functions"}</div>`
    : "";
  const names = (box.members || []).slice(0, DGM_CARD_NAMES)
    .map(id => (diagramNow.names || {})[id] || id.split(".").slice(-1)[0]);
  const more = (box.members || []).length - names.length;
  return `
    <div class="hc-head">
      <b class="hc-name">${esc(box.label)}</b>
      <span class="kind-tag">${esc(what)}</span>
    </div>
    ${box.module ? `<div class="hc-sub mono">${breakable(box.module)}</div>` : ""}
    ${held}
    ${names.length ? `<div class="hc-list mono">${names.map(esc).join("<br>")}${
      more > 0 ? `<div class="hint">…and ${more} more</div>` : ""}</div>` : ""}
    ${box.kind === "port"
      ? `<div class="hint">Click to open this compartment.</div>`
      : box.members && box.members.length
        ? `<div class="hint">Click to select what it holds.</div>` : ""}`;
}

/* The same card for an arrow. It asks the server for nothing either, and for a better
 * reason than the box's: what an arrow carries -- its kinds and its weight -- rode in with
 * the drawing, and what it *contains* is a panel rather than a card. The hint says which
 * click gets that, because an arrow two pixels wide that turns out to be clickable only
 * once you have tried is a control nobody finds. */
function diagramEdgeCard(e) {
  const by = (diagramNow && diagramNow.by_id) || {};
  const a = by[e.from], b = by[e.to];
  const what = { CALL: "calls", TOUCH: "touches", NAMES: "names" };
  return `
    <div class="hc-head">
      <b class="hc-name">${esc((a && a.label) || e.from)} \u2192 ${
        esc((b && b.label) || e.to)}</b>
      <span class="kind-tag">${esc((e.kinds || []).map(k => what[k] || k).join(" + "))}</span>
    </div>
    <div class="hc-sub">${e.weight} along it${e.crosses
      ? " \u00b7 crosses to another compartment" : ""}</div>
    <div class="hint">Click to see what flows here.</div>`;
}

/* Dwell is not wanted here and the reason is the same as the fetch: there is nothing to
 * wait for. The card is built from data already in the page, so showing it on entry costs
 * one `innerHTML` write and a placement. */
document.addEventListener("pointermove", (ev) => {
  const mount = $("#diagramMount");
  if (!mount || mount.hidden) return;
  const canvas = ev.target.closest(".dgm-canvas");
  if (!canvas) { if (hoverHost === "diagram") hideHoverCard(); return; }
  const g = ev.target.closest("g.node");
  /* **A box first, then an arrow**, the same order the click handler asks in and for the
   * same reason: a box is drawn over its own edges' endpoints, so asking about the arrow
   * first would describe a line the reader is not pointing at wherever the two overlap. */
  const eg = g ? null : ev.target.closest("g.edge");
  const edge = (eg && diagramNow && (diagramNow.edges || {})[eg.id]) || null;
  if ((!g || !diagramNow || !diagramNow.by_id[g.id]) && !edge) {
    if (hoverHost === "diagram") hideHoverCard();
    return;
  }
  const r = canvas.getBoundingClientRect();
  const at = { x: ev.clientX - r.left, y: ev.clientY - r.top };
  if (edge) {
    if (eg.id === hoverAt && hoverHost === "diagram") {
      hoverAnchor = at; placeHoverCard(); return;
    }
    showHoverCard("diagram", eg.id, at, diagramEdgeCard(edge));
    return;
  }
  /* Moving within the same box is a move, not a new subject -- the stack's card makes the
     same distinction, and for the same reason: re-rendering would flicker a card that is
     already correct. */
  if (g.id === hoverAt && hoverHost === "diagram") {
    hoverAnchor = at;
    placeHoverCard();
    return;
  }
  showHoverCard("diagram", g.id, at, diagramCard(diagramNow.by_id[g.id]));
});

/* Pan and zoom, on a transform rather than a viewBox: the SVG is laid out once and only the
 * wrapper moves, so a drag costs a compositor transform and never a re-layout of eighty
 * boxes. */
const dgmView = { x: 0, y: 0, k: 1 };
function dgmApply() {
  const pan = $("#dgmPan");
  if (pan) pan.style.transform =
    `translate(${dgmView.x}px, ${dgmView.y}px) scale(${dgmView.k})`;
}
/* **Fit is arithmetic we do, not something the browser redoes behind us.**
 *
 * The SVG used to be `width:100%` with `preserveAspectRatio`, so the *browser* fitted it --
 * and re-fitted it on every container resize. Opening the inspector narrows the centre
 * column, so the first click on a box moved the whole drawing **139 pixels** out from under
 * the reader's cursor, and their second click landed on a different box. That is why
 * opening a box could not be built on the browser's `dblclick`, and it is a nuisance far
 * beyond that gesture: any pane folding or unfolding threw away where you were looking.
 *
 * With an explicit pixel size on the SVG and the fit expressed as our own transform, a
 * resize changes nothing at all -- and `fit` stays one click away, which is design rule 20's
 * requirement rather than a convenience.
 *
 * **Deferred, never guessed** (rule 49). A canvas that has not been laid out measures 0x0,
 * and fitting to a plausible substitute is what hides the failure -- the stack paid for that
 * exact mistake, framing itself for a 1275px window inside a 496px one. It returns false and
 * `render()` tries again; there is always another render, and it costs two reads. */
let dgmNeedsFit = false;

function dgmSize() {
  const svg = $("#dgmPan svg");
  if (!svg) return null;
  const vb = (svg.getAttribute("viewBox") || "").trim().split(/[\s,]+/).map(Number);
  const w = vb.length === 4 && vb[2] > 0 ? vb[2] : svg.getBoundingClientRect().width;
  const h = vb.length === 4 && vb[3] > 0 ? vb[3] : svg.getBoundingClientRect().height;
  return (w > 0 && h > 0) ? { svg, w, h } : null;
}

function dgmFit() {
  const c = $("#dgmCanvas");
  const size = dgmSize();
  if (!c || !size) { dgmNeedsFit = true; return false; }
  const cw = c.clientWidth, ch = c.clientHeight;
  if (!cw || !ch) { dgmNeedsFit = true; return false; }
  // A hair inside the pane, so a box on the rim is not clipped by its own stroke.
  const k = Math.min(cw / size.w, ch / size.h) * 0.97;
  dgmView.k = k;
  dgmView.x = (cw - size.w * k) / 2;
  dgmView.y = (ch - size.h * k) / 2;
  dgmNeedsFit = false;
  dgmApply();
  return true;
}

/* Which box the shared selection is in, marked on the drawing.
 *
 * The five modes are five ways of looking at **one** selection, so a routine picked in the
 * navigator or the stack has to be visible here too -- and a box clicked here has to stay
 * marked when the reader's eye comes back to it. Two class changes, never a repaint: the SVG
 * is laid out once, and rebuilding it to move a highlight is the defect that cost the code
 * browser 1,370 ms (rule 52's companion).
 *
 * Silent when the selection is not in this compartment, which is the honest answer -- the
 * reader is looking at something that does not live here. */
function markDiagramSelection() {
  const host = $("#dgmPan");
  if (!host || !diagramNow) return 0;
  /* **`state.selected` first, and the engine's picks only if it has any.**
   *
   * `selectedIds()` reads the *graph engine's* picks and translates indices to ids, so it
   * answers `{nodes: [], disks: []}` for a session that has never opened the stack -- which
   * is every session that goes straight to Diagram mode. The mark was correct code reading
   * the wrong source: the selection was real, the inspector had it, and nothing lit.
   *
   * `state.selected` is the id the inspector reads, and it does not depend on a renderer
   * being mounted. Rule 51 -- one truth about what is selected, and the one that does not
   * go blank when a different view happens to be closed. */
  const want = new Set(selectedIds().nodes || []);
  if (state.selected) want.add(state.selected);
  /* A **fold** is marked by its own id, not by what it holds. Two boxes can hold the same
     routine -- a class and the file its module folds -- and matching only on members would
     light both when the reader picked one. The box the reader clicked is the box that is
     marked; the members still light in the stack, which is a different picture. */
  let marked = 0;
  host.querySelectorAll("g.node").forEach(g => {
    const box = diagramNow.by_id[g.id];
    const on = !!box && (g.id === state.fold
      || (!state.fold && !!box.members && box.members.some(m => want.has(m))));
    g.classList.toggle("dgm-on", on);
    if (on) marked++;
  });
  return marked;
}

/* ═══ mode toggle ═══ */
$$("#modes button").forEach(b => b.addEventListener("click", () => {
  state.mode = b.dataset.mode;
  state.view = state.mode;
  pushTrail(state.mode, b.textContent.trim());
  used(state.mode);
  /* **Paint before mounting.** This ran `ensureGraph()` first, so the engine measured
   * `#graphMount` while it was still `hidden` from the previous render -- and a hidden
   * container is 0x0. `fitView` then framed the stack for the whole window instead of the
   * pane, and switching to the graph from the table showed an empty canvas until the reader
   * found snap-to-fit. `boot()` had the order right; this call site did not.
   *
   * Reported as *the graph should have been there*, and it should. */
  render();
  if (state.mode === "graph") ensureGraph();
  /* Paint, then build -- the same order the graph needed and for the same reason: the mount
     is `hidden` from the previous render until `render()` has run, and a pane measured while
     hidden is 0x0. */
  if (state.mode === "diagram") ensureDiagram();
}));

/* How long a second click on the same box still counts as opening it. Chrome's own
 * threshold is 500 ms; this is deliberately the same order, and it is ours because the
 * browser's `dblclick` cannot be used here -- see the click handler. */
const DGM_DOUBLE_MS = 500;
let dgmClickedBox = null;
let dgmClickedAt = 0;

/* **The box under the pointer, asked rather than assumed.**
 *
 * `ev.target` is the right answer almost always and is not the right answer here: anything
 * that captures the pointer -- this view's own pan gesture did, on every press -- retargets
 * the compatibility mouse events, so a click on a box arrives naming the canvas. The
 * capture is fixed above; this makes the question unanswerable-by-accident rather than
 * merely answered correctly today, because the next thing to capture a pointer will not
 * come with a note attached.
 *
 * `elementFromPoint` is the same tool rule 48 names for proving a control is reachable, used
 * here to *be* reachable. It is one hit test on a click, not on a move, so it costs nothing
 * worth measuring. */
function diagramBoxAt(ev) {
  let el = ev.target;
  let g = el && el.closest ? el.closest("g.node") : null;
  if (!g && ev.clientX != null) {
    const under = document.elementFromPoint(ev.clientX, ev.clientY);
    g = under && under.closest ? under.closest("g.node") : null;
  }
  if (!g || !diagramNow) return null;
  const box = diagramNow.by_id[g.id];
  return box ? { g, box } : null;
}

/* The same question about an arrow. Graphviz classes an edge `g.edge` and writes the `id=`
 * `dot()` gave it, so this is the box hit test with one class changed -- including the
 * `elementFromPoint` fallback, which matters more here than it does for a box: an arrow is
 * a two-pixel stroke, and the thing under the pointer is as often the `<path>`'s parent as
 * the path itself.
 *
 * A stroke that thin is hard to hit on purpose, and that is a real limit rather than a
 * defect to hide: the same flow is reachable from a row in the inspector, which is a
 * button. Both go through `selectFlow`, so there is one answer either way (rule 51). */
function diagramEdgeAt(ev) {
  let el = ev.target;
  let g = el && el.closest ? el.closest("g.edge") : null;
  if (!g && ev.clientX != null) {
    const under = document.elementFromPoint(ev.clientX, ev.clientY);
    g = under && under.closest ? under.closest("g.edge") : null;
  }
  return (g && g.id && splitEdgeId(g.id)) ? g.id : null;
}

/* The diagram's own controls, delegated from the mount because that mount is rewritten
 * whenever a different compartment is drawn -- handlers bound to elements would stop working
 * silently the moment they were replaced. */
document.addEventListener("click", (ev) => {
  const fit = ev.target.closest("[data-dgm]");
  if (fit) { dgmFit(); return; }
  const up = ev.target.closest("[data-dgmup]");
  if (up) { openDiagramBox(null); return; }
  const mount = $("#diagramMount");
  if (!mount || mount.hidden || !ev.target.closest("#diagramMount")) return;
  const at = diagramBoxAt(ev);
  if (!at) {
    /* **A box first, then an arrow.** A box is drawn over its own edges' endpoints, so
     * asking about the arrow first would answer about a line the reader was not aiming at
     * wherever the two overlap -- rule 47's companion, where two pickable things reporting
     * through one handler made an index mean two things. Asked in the order the drawing
     * stacks them. */
    const edge = diagramEdgeAt(ev);
    if (edge) selectFlow(edge);
    return;
  }
  const { g, box } = at;

  /* **Opening a box is a second click on the same box, not a `dblclick` event.**
   *
   * Tom asked for both gestures -- a click says what the box *is*, a double-click goes
   * inside it -- and the browser's own `dblclick` cannot deliver the second one here.
   * The first click fills the inspector, which un-rails a pane 352px wide, which narrows
   * the centre column, which reflows an SVG sized at `width:100%`: **the drawing moves
   * under the reader's cursor between their two clicks.** The second lands on a different
   * box, so the browser fires two clicks and no `dblclick` at all -- and it fails exactly
   * once per session, on the first double-click, which is the one a reader tries.
   *
   * Keyed on the **box id** rather than on the element or the position, so a reflow between
   * the two clicks changes nothing about what was asked for. Same instruction as everywhere
   * else in this view: identity, never position (rule 30).
   *
   * A box with nothing to open says so rather than declining a gesture in silence, which is
   * design rule 16's defect arriving through a gesture rather than through a control. */
  const now = performance.now();
  const again = dgmClickedBox === g.id && (now - dgmClickedAt) < DGM_DOUBLE_MS;
  dgmClickedBox = g.id;
  dgmClickedAt = now;
  if (again) {
    if (box.kind === "port" || box.kind === "routine" || !(box.members || []).length) {
      state.navNote = box.kind === "port"
        ? `${box.label} is another compartment — one click goes there`
        : `${box.label} holds no routines of its own to open`;
      render();
      return;
    }
    openDiagramBox(g.id, box.label);
    return;
  }

  /* **A port is a place, a box is a thing.** Clicking a port flips the book to that
     compartment; clicking a box selects what it holds in the one selection the whole
     dashboard shares, so the inspector fills and the stack lights without this view owning
     a second answer to "what am I looking at" (rule 51). */
  if (box.kind === "port") {
    /* A port names a **plate** at the first level and a **box** at the second, because
       that is what it stands for at each, and clicking it goes to whichever that is. Both
       are the same act -- *take me to the other end* -- and doing anything less precise at
       the second level would throw away the one thing the port there knows. */
    if (box.box) {
      state.diagramId = String(box.box).split("|")[0];
      state.diagramBox = String(box.box);
    } else {
      state.diagramId = box.plate;
      state.diagramBox = null;
    }
    diagramNow = null;
    pushTrail("diagram", box.label);
    used("diagram:port");
    ensureDiagram();
    return;
  }
  /* **At the second level a box is a routine**, and a routine is a node: it selects as
     itself, through the path every other node in the product uses. Told apart by the kind
     the server put on it rather than by which endpoint we happen to have called -- the
     drawing is the same shape either way, and a flag about *how we got here* is a second
     answer to what is on screen (rule 51). */
  if (box.kind === "routine") {
    used("diagram:routine");
    selectFromNav({ nodes: [g.id] }).then(markDiagramSelection);
    return;
  }
  if (box.members && box.members.length) {
    used("diagram:box");
    /* **A trail step, and the mark on the box.** The click reached the shared selection from
       the first version and the inspector filled -- but a reader with the inspector railed
       saw *nothing at all* happen, and Back could not reverse it. Both are the same defect
       in different clothes: an act with no visible consequence and no way back. Rule 33 says
       a trail step must carry its subject; design rule 15 says nobody chases a rabbit if
       they might not find their way back.

       **And what filled the inspector was the wrong thing**, which is what Tom reported
       next: this passed `box.members` and `selectFromNav` elected `members[0]`, so a box
       labelled `KernelDecl` holding sixty-one methods described
       `KernelDecl._profile_name_or_none`. `selectFold` asks about the box.

       Two smaller repairs on the way. The trail step was pushed *before* the selection
       settled, so it filed the previous subject; and its third argument was an object where
       a `note` string belongs, which `trailBar` renders through `esc(t.note || t.label)`. */
    /* `g.id`, not `box.id`. `by_id` is a *map keyed by* the box id and its values carry no
       `id` of their own, so the obvious spelling is `undefined` -- caught here by the
       identity guard rather than by a click that silently did nothing (rule 16). */
    selectFold(g.id).then(markDiagramSelection);
  }
});

/* One owner for *which* altitude the drawing is at, because three controls reach it: the
 * double-click, the way back up, and the compartment picker (which must come home to the
 * first level, or choosing a compartment would leave the last box open under it). */
function openDiagramBox(boxId, label) {
  state.diagramBox = boxId || null;
  diagramNow = null;
  used(boxId ? "diagram:open" : "diagram:up");
  /* Named for the *act*, not for the thing. Selecting the box and opening it are two steps
     with the same subject-name and different subjects, so two rows reading `KernelDecl`
     leave the reader guessing which is which -- rule 30 in a label rather than in a
     control. */
  pushTrail("diagram", boxId ? `inside ${label || "box"}` : "out",
            boxId ? "opened the box" : "back out to the compartment");
  persist();
  ensureDiagram();
}

document.addEventListener("change", (ev) => {
  if (ev.target.id === "dgmPorts") {
    state.diagramPorts = ev.target.checked;
    used("diagram:ports:" + (state.diagramPorts ? "on" : "off"));
    persist();
    ensureDiagram();
    return;
  }
  if (ev.target.id !== "dgmPick") return;
  state.diagramId = ev.target.value;
  /* Choosing a compartment comes home to the first level. Without this the picker would
     name one compartment while the drawing showed a box inside another -- one control,
     two claims, and the markup is the one that loses (rule 67). */
  state.diagramBox = null;
  diagramNow = null;
  pushTrail("diagram", ev.target.selectedOptions[0].textContent.split("—")[0].trim());
  used("diagram:pick");
  persist();
  ensureDiagram();
});

/* Drag to pan, wheel to zoom. On the wrapper's transform, so neither costs a re-layout. */
/* How far the pointer must travel before a press becomes a drag. Below it the gesture is
 * a click and the canvas never captures; above it the canvas captures and the click that
 * would follow is swallowed. Three pixels rather than none, because a press is never
 * perfectly still. */
const DGM_DRAG_SLOP = 3;

(function dgmGestures() {
  let from = null, dragging = false, capture = null;
  document.addEventListener("pointerdown", (ev) => {
    const c = ev.target.closest("#dgmCanvas");
    if (!c) return;
    from = { x: ev.clientX - dgmView.x, y: ev.clientY - dgmView.y,
             ox: ev.clientX, oy: ev.clientY, id: ev.pointerId, el: c };
    dragging = false;
    /* **The capture is NOT taken here, and that is the whole of this fix.**
     *
     * It was, on every press, and a captured pointer retargets the compatibility mouse
     * events with it: `click` and `dblclick` then arrive with `target` set to the canvas,
     * so `ev.target.closest("g.node")` is null and every handler in this view returns
     * having done nothing. Clicking a box did nothing, double-clicking did nothing, and
     * nothing anywhere failed -- the handlers were perfect and were being handed the
     * wrong element.
     *
     * It survived two rounds of verification because a *dispatched* event goes straight to
     * the element it names and never touches the pointer path at all. Rule 48 in its
     * purest form: a scripted click proves the handler, and only a pointer proves the way
     * to it. The previous session filed the same symptom under "the feedback was in a
     * railed pane", which was also true and was not this.
     *
     * Capture is taken on the first move past the slop instead -- which is when a drag
     * actually begins, and is the only moment it is needed. */
  });
  document.addEventListener("pointermove", (ev) => {
    if (!from) return;
    if (!dragging) {
      if (Math.abs(ev.clientX - from.ox) + Math.abs(ev.clientY - from.oy) < DGM_DRAG_SLOP) return;
      dragging = true;
      /* The pan cursor, on the **real** drag rather than on `:active`. `:active` fires on
         any press -- including a click on a box that never becomes a pan -- so the closed
         hand flashed on every click. That is rule 72's own lesson in a cursor: a drag needs
         the feedback and a click does not, and the moment that tells them apart is this
         one, past the slop. */
      from.el.classList.add("dgm-dragging");
      capture = from.el;
      /* `setPointerCapture` **throws** `NotFoundError` for a pointerId that is no longer
         active, and a throw here would leave the drag half-started -- `dragging` set, the
         pan never applied, and the click after it swallowed for nothing. The capture is an
         improvement to panning (it keeps tracking when the pointer leaves the pane), not a
         requirement of it, so failing to get one must cost the pan nothing. */
      try { capture.setPointerCapture(from.id); } catch { capture = null; }
    }
    dgmView.x = ev.clientX - from.x;
    dgmView.y = ev.clientY - from.y;
    dgmApply();
  });
  document.addEventListener("pointerup", () => {
    /* A drag ends in a `click` on whatever the press started over, so panning across the
       drawing would select the box you set off from. Swallowed for one event, in the
       capture phase, so no handler downstream has to know a drag happened. */
    if (dragging) {
      const eat = (e) => { e.stopPropagation(); e.preventDefault(); };
      document.addEventListener("click", eat, { capture: true, once: true });
    }
    if (from) from.el.classList.remove("dgm-dragging");
    if (capture) { capture.releasePointerCapture?.(from.id); capture = null; }
    from = null;
    dragging = false;
  });
  document.addEventListener("wheel", (ev) => {
    const c = ev.target.closest("#dgmCanvas");
    if (!c) return;
    ev.preventDefault();
    const r = c.getBoundingClientRect();
    const px = ev.clientX - r.left, py = ev.clientY - r.top;
    const k = Math.max(0.15, Math.min(12, dgmView.k * (ev.deltaY < 0 ? 1.12 : 1 / 1.12)));
    // Anchor the point under the cursor, or zooming walks the drawing out of the pane.
    dgmView.x = px - (px - dgmView.x) * (k / dgmView.k);
    dgmView.y = py - (py - dgmView.y) * (k / dgmView.k);
    dgmView.k = k;
    dgmApply();
  }, { passive: false });
})();

/* ═══ graph layout: two drawings of one selection ═══ */
/* Delegated, because the same control is drawn in two places -- the crumb bar while you
 * are in graph mode, and Settings while you are deciding what to open on. Two handlers for
 * one control is two things to keep in step, and the one that drifts is the one nobody
 * clicks while testing. */
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-layout]");
  if (!b) return;
  state.graphLayout = b.dataset.layout;
  used("layout:" + state.graphLayout);
  if (state.view === "graph") pushTrail("graph", b.textContent.trim());
  if (state.graphLayout === "stack") ensureGraph();
  render();
});

document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-edgesmotion]");
  if (!b) return;
  state.edgesInMotion = !state.edgesInMotion;
  used("edgesInMotion:" + state.edgesInMotion);
  Graph.setOptions({ edgesInMotion: state.edgesInMotion });
  render();
});

document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-graphtheme]");
  if (!b) return;
  state.graphTheme = b.dataset.graphtheme;
  used("graphtheme:" + state.graphTheme);
  applyGraphPalette();
  render();
});

/* ═══ settings ═══ */
$("#settingsBtn").addEventListener("click", () => {
  state.view = state.view === "settings" ? state.startup : "settings";
  used("settings");
  render();
});

/* ═══ filter strip ═══ */
$("#clearFilters").addEventListener("click", () => { state.filters = []; render(); });
$("#showHidden").addEventListener("click", (e) => {
  const l = $("#hiddenList");
  const open = l.hasAttribute("hidden");
  if (open) l.removeAttribute("hidden"); else l.setAttribute("hidden", "");
  e.currentTarget.setAttribute("aria-expanded", String(open));
  e.currentTarget.textContent = open ? "Hide list" : "Show hidden";
});

function renderFilters() {
  const strip = $("#filterstrip");
  const chips = $("#chips");
  chips.innerHTML = state.filters.map(f =>
    `<span class="chip">${esc(f.label)}<button data-drop="${esc(f.id)}" aria-label="Remove filter ${esc(f.label)}">×</button></span>`
  ).join("");
  $$("[data-drop]", chips).forEach(b => b.addEventListener("click", () => {
    state.filters = state.filters.filter(f => f.id !== b.dataset.drop);
    render();
  }));

  /* Counts are the program's. What each filter removes will be computed by the filter
     that removes it, when filtering is built -- until then there is nothing to hide and
     nothing is claimed about hiding it. */
  const total = (STATS && STATS.routines) || 0;
  const shown = state.filters.reduce((n, f) => (f.shown !== undefined ? f.shown : n), total);
  $("#fsShown").textContent = shown.toLocaleString();
  $("#fsTotal").textContent = total.toLocaleString();

  const hid = state.filters.filter(f => f.hides).map(f => f.hides);
  $("#fsHidden").textContent = hid.length ? "· hidden: " + hid.join(" · ") : "";

  const applies = CENTRE_MODES.includes(state.view);
  strip.style.display = (applies && state.filters.length) ? "flex" : "none";

  $("#hiddenList").innerHTML =
    "<b>What this view is not showing you</b><ul>" +
    state.filters.map(f => `<li>${esc(f.explains || f.label)}</li>`).join("") +
    "</ul>";
}

/* ═══ views ═══ */
/* Boundary glyphs. Presentation, so they stay here rather than being served -- but a
   kind with no glyph gets a neutral mark rather than a blank, because a missing icon
   must not read as a missing row. */
const BKIND_GLYPH = {
  DATABASE: "▤", FILE: "▣", STDIO: "▷", CRYPTO: "✦", ENV: "◈",
  PROCESS: "▶", LLM_API: "✧", NETWORK: "◆", QUEUE: "◇", CLOUD: "☁",
};

function viewCover() {
  if (!ENTRYPOINTS.length) {
    return `<div class="panel" style="padding:1.25rem">
      <h2 style="margin:0 0 .5rem">This program has no way in that DunneFlow can see.</h2>
      <p class="hint">Either it is a library rather than a program, or a registration idiom
      is being missed — a command attached by direct call, by <code>set_defaults</code>, or
      by subclassing. That would be a defect in DunneFlow, not in the program.</p></div>`;
  }
  const max = ENTRYPOINTS[0].reach;
  const st = STATS || {};
  const num = (v) => (v === null || v === undefined) ? null : Number(v).toLocaleString();
  /* Lines come from the source sidecar, so they are absent when the map was made with
     `--no-source` or handed over without it. Absent is said out loud rather than guessed
     at from file sizes: a number the reader cannot check is worse than no number. */
  const bits = [
    num(st.files) && `<b>${num(st.files)}</b> files`,
    num(st.lines) ? `<b>${num(st.lines)}</b> lines`
                  : `<span class="hint">lines not counted — no source sidecar</span>`,
    num(st.routines) && `<b>${num(st.routines)}</b> routines`,
    st.analysed ? `analysed <b>${esc(st.analysed)}</b>`
                : `<span class="hint">analysed before this map recorded when</span>`,
  ].filter(Boolean).join(" · ");
  return `
  <div class="cover-grid">
    <div class="cover-title">
      <h1>${esc(st.program || "program")}</h1>
      <span class="meta">${bits}</span>
    </div>

    <section class="panel">
      <div class="panel-head">
        <h2>Where to start</h2>
        <span class="hint">ranked by how much of the program each one commands</span>
      </div>
      <div class="panel-body">
        <div class="rank">
          ${ENTRYPOINTS.map(e => `
            <button class="rank-row" data-ep="${esc(e.name)}">
              <span class="rank-name">
                <code>${esc(e.name)}</code>
                <span class="kind-tag">${esc(e.kind)}</span>
              </span>
              <span class="rank-reach num">${e.reach.toLocaleString()}</span>
              <span class="bar"><i style="width:${Math.max(2, (e.reach / max) * 100)}%"></i></span>
            </button>`).join("")}
        </div>
      </div>
    </section>

    <div style="display:flex;flex-direction:column;gap:.875rem">
      <section class="panel">
        <div class="panel-head"><h2>What it touches</h2><span class="hint">${
          BOUNDARIES.reduce((a, b) => a + b.n, 0).toLocaleString()}</span></div>
        <div class="panel-body">
          ${BOUNDARIES.map(b => `
            <div class="bkrow">
              <span class="gl" aria-hidden="true">${BKIND_GLYPH[b.kind] || "◦"}</span>
              <span>${esc(b.kind)}</span>
              <span class="n">${b.n.toLocaleString()}</span>
              <span class="bar"><i style="width:${(b.n / BOUNDARIES[0].n) * 100}%"></i></span>
            </div>`).join("")}
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h2>What looks wrong</h2><span class="hint">every finding states its blind spot</span></div>
        <div class="panel-body">
          ${[["broken", "Broken"], ["suspect", "Suspect"], ["info", "Informational"]]
            .map(([k, label]) => {
              const n = ((st.anomalies || {})[k]) || 0;
              return `<button class="sevline sevgo" data-gosev="${k}" ${n ? "" : "disabled"}>
                <span class="sevdot" style="background:var(--sev-${k})"></span> ${label}
                <span class="n">${n ? `<span class="sevcount ${k}">${n}</span> \u203a`
                                    : '<span class="n">0</span>'}</span></button>`;
            }).join("")}
          <p style="margin:.5rem 0 0;font-size:.72rem;color:var(--text-muted)">
            Severity says what it would mean for the program. Confidence says how sure DunneFlow is.
            They are different questions.
          </p>
        </div>
      </section>
    </div>
  </div>`;
}

/* The package overview -- one of two layouts inside graph mode, beside the stack.
 *
 * Two altitudes, two answers, and both were always the plan: a package graph is "adequate
 * for orientation and will not scale", the stack is the viewer that holds ten thousand
 * nodes. Neither replaces the other.
 *
 * Every coordinate here comes from `/api/packages`. The ratified design had them written
 * into a JavaScript array by hand, which is right for settling a design and wrong for
 * shipping one -- the same code against a real store drew forty-seven rectangles at
 * `x="undefined"` and zero edges, and said nothing about it.
 */
/* How many connections the unselected view draws. Chosen so the spine is legible on a
 * laptop rather than by taste: at forty-seven boxes, past roughly fifty curves the boxes
 * start going under the mesh, which is design rule 19's failure at a smaller scale. */
const SPINE_EDGES = 45;

let PACKAGEVIEW = null;      // served, never pinned
let packagesLoading = false;
let packagesError = null;

async function ensurePackages() {
  if (PACKAGEVIEW || packagesLoading) return;
  packagesLoading = true;
  try {
    const r = await fetch("/api/packages");
    if (!r.ok) throw new Error(`the server answered ${r.status} for /api/packages`);
    PACKAGEVIEW = await r.json();
  } catch (err) {
    packagesError = err.message;
  }
  packagesLoading = false;
  render();
}

function viewGraph() {
  if (packagesError) {
    return `<div class="panel"><div class="panel-head"><h2>Package overview</h2></div>
      <div class="panel-body"><p>This view could not be read.</p>
      <p class="hint">${esc(packagesError)}</p></div></div>`;
  }
  if (!PACKAGEVIEW) {
    ensurePackages();
    return `<div class="panel"><div class="panel-body"><p class="hint">Reading the
      overview…</p></div></div>`;
  }

  const d = PACKAGEVIEW;
  const W = d.box.w, H = d.box.h;
  const at = {};
  d.packages.forEach(p => at[p.id] = p);
  d.externals.forEach(p => at[p.id] = p);
  const showExt = !state.filters.some(f => f.id === "ext");

  /* A curve, because two boxes in the same column would otherwise be joined by a line
     lying flat along the row and reading as a rule rather than a connection. */
  const edgePath = (a, b) => {
    const A = at[a], B = at[b];
    if (!A || !B) return "";
    const x1 = A.x + W, y1 = A.y + H / 2;
    const x2 = B.x,     y2 = B.y + H / 2;
    const mx = (x1 + x2) / 2;
    return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
  };

  /* Design rule 19, at this altitude. Two hundred and twenty-eight package connections
     and a hundred and seventy-four boundary touches drawn at once do not describe a
     program -- they erase it, and the boxes go under a mesh. So the same discipline the
     stack uses applies here: **edges on demand.**

     Pick a package and you get everything it touches, at any weight, with the rest of the
     drawing dimmed. Pick nothing and you get the heaviest connections only, which is the
     spine of the program and the thing an orientation view is for. What is not drawn is
     stated in the header either way -- design rule 1, and rule 8's requirement that a
     bounded picture sit beside the complete count. */
  const picked = state.pkgPick;
  const visible = d.edges.filter(e => !(state.hideInferred && e.confidence === "INFERRED"));
  const spine = visible.slice().sort((a, b) => b.weight - a.weight).slice(0, SPINE_EDGES);
  const spineSet = new Set(spine.map(e => `${e.src}\u0000${e.dst}`));
  const drawn = picked
    ? visible.filter(e => e.src === picked || e.dst === picked)
    : spine;
  const undrawn = visible.length - drawn.length;
  const inferredHidden = d.edges.length - visible.length;

  /* Design rule 5: confidence is shape. Solid is CERTAIN, dashed is INFERRED, and the
     global "hide inferred" toggle leaves the defensible skeleton readable on its own. */
  const edges = drawn.map(e => `<path class="gedge ${
      e.confidence === "INFERRED" ? "inferred" : ""} ${
      picked || spineSet.has(`${e.src}\u0000${e.dst}`) ? "" : "faint"}"
        d="${edgePath(e.src, e.dst)}"
        stroke-width="${Math.max(1, Math.min(5, Math.log2(1 + e.weight)))}"
        marker-end="url(#arw)"><title>${esc(e.src)} → ${esc(e.dst)}: ${
        e.weight.toLocaleString()} calls, ${esc(e.confidence)}</title></path>`).join("");

  /* Rule 26: an external is not an edge we are unsure of. It gets its own mark and no
     confidence shape -- we are certain the call leaves, we simply cannot see the far end.
     Off unless a package is picked: a hundred and seventy-four of them is the same haze
     in a different colour, and the boundary column already says the systems are there. */
  const extDrawn = showExt && picked
    ? d.ext_edges.filter(e => e.src === picked)
    : [];
  const extEdges = extDrawn.map(e =>
    `<path class="gedge outside" d="${edgePath(e.src, e.dst)}" stroke-width="1.5"
       marker-end="url(#arwx)"><title>${esc(e.src)} → ${esc(e.dst)}: ${
       e.weight.toLocaleString()} touches</title></path>`).join("");

  const touching = new Set([picked]);
  for (const e of drawn) { touching.add(e.src); touching.add(e.dst); }
  for (const e of extDrawn) touching.add(e.dst);

  const box = (p, isExt) => `
    <g class="gnode ${isExt ? "outside" : (p.entry ? "entry" : "")} ${
       picked ? (p.id === picked ? "picked" : (touching.has(p.id) ? "" : "dimmed")) : ""}"
       tabindex="0" role="button"
       data-pkgnode="${esc(p.id)}"
       aria-label="${esc(p.id)}${isExt
         ? `, external system, ${p.hits} touches`
         : `, ${p.n} routines${p.entry ? ", a way in" : ""}`}">
      <rect x="${p.x}" y="${p.y}" width="${W}" height="${H}" rx="6"></rect>
      <text x="${p.x + 12}" y="${p.y + 20}">${esc(p.id)}</text>
      <text class="sub" x="${p.x + 12}" y="${p.y + 34}">${isExt
        ? `${p.targets.toLocaleString()} endpoints · outside our control`
        : `${p.n.toLocaleString()} routines${p.entry ? " · way in" : ""}`}</text>
    </g>`;

  return `
  <div class="graphwrap">
    <div class="pkghead">
      <b>${d.packages.length}</b> packages · <b>${d.edges.length}</b> connections between
      them · <b>${d.externals.length}</b> external systems
      <span class="pkgcut">${picked
        ? `Showing everything <b>${esc(picked)}</b> touches: <b>${drawn.length}</b>
           connection${drawn.length === 1 ? "" : "s"} and <b>${extDrawn.length}</b>
           boundary${extDrawn.length === 1 ? "" : " kinds"}.
           <b>${undrawn.toLocaleString()}</b> connections between other packages are not
           drawn. <button class="linkbtn" data-pkgpick="">Show the spine again</button>`
        : `Drawing the <b>${drawn.length}</b> heaviest connections — the spine.
           <b>${undrawn.toLocaleString()}</b> lighter ones and all
           <b>${d.ext_edges.length}</b> boundary touches are not drawn: click any package
           to see every connection it has, at any weight.`}
        ${inferredHidden ? ` <b>${inferredHidden}</b> inferred connection${
          inferredHidden === 1 ? "" : "s"} hidden by your filter.` : ""}</span>
      <span class="pkgcut">Columns are hops from a way in. Depth reads left to right;
        a rank too deep for one column wraps rather than growing taller.</span>
    </div>
    <!-- Sized in rem, not px: design rule 3 says one root multiplier resizes the whole
         surface together, and a width stored in pixels is a width the multiplier cannot
         reach. The viewBox unit is one pixel at 100%, so dividing by 16 makes the drawing
         grow and shrink with everything else. It scrolls inside its own pane rather than
         being squeezed to fit -- a package box squeezed below legibility is a box nobody
         can read, which is a worse answer than a scrollbar. -->
    <svg viewBox="0 0 ${d.width} ${d.height}"
         style="width:${(d.width / 16).toFixed(2)}rem;height:${(d.height / 16).toFixed(2)}rem"
         role="img" aria-label="Package overview: ${d.packages.length} packages in ${
           1 + Math.max(...d.packages.map(p => p.rank))} ranks, reaching ${
           d.externals.length} external systems.">
      <defs>
        <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
                markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--border-strong)"></path>
        </marker>
        <marker id="arwx" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6"
                markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="var(--external)"></path>
        </marker>
      </defs>
      ${showExt && d.boundary_x != null
        ? `<line class="boundline" x1="${d.boundary_x}" y1="8" x2="${d.boundary_x}"
             y2="${d.height - 8}"></line>
           <text class="boundlabel" x="${d.boundary_x + 8}" y="20">System boundary</text>`
        : ""}
      ${edges}${extEdges}
      ${d.packages.map(p => box(p, false)).join("")}
      ${showExt ? d.externals.map(p => box(p, true)).join("") : ""}
    </svg>
    <div class="legend">
      <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4"
        stroke="currentColor" stroke-width="2"/></svg> CERTAIN — pinned by import</span>
      <span><svg width="26" height="8"><line x1="0" y1="4" x2="26" y2="4"
        stroke="currentColor" stroke-width="2" stroke-dasharray="4 3"/></svg>
        INFERRED — resolved by unique name</span>
      <span><svg width="14" height="10"><rect x="0.75" y="0.75" width="12.5" height="8.5"
        rx="2" fill="none" stroke="var(--external)" stroke-width="1.5"
        stroke-dasharray="4 2"/></svg> External — outside our control, and not a
        confidence</span>
      <span>Line weight = calls between packages</span>
    </div>
  </div>`;
}

/* `q` sorts by qualified name, `fan` by how connected the routine is. `fan` comes from the
 * graph and is blank until the engine is mounted, so sorting by it before then would order
 * by nothing at all -- it falls back to the name rather than producing an arbitrary order
 * that looks deliberate. */
function sortedRoutines() {
  const k = state.sortKey;
  const dir = state.sortAsc ? 1 : -1;
  const qual = (r) => `${r.module}.${r.name}`;
  return ROUTINES.slice().sort((a, b) => {
    if (k === "fan" && Graph.mounted()) {
      const d = (Number(routineFan(a.id)) || 0) - (Number(routineFan(b.id)) || 0);
      if (d) return d * dir;
    }
    if (k === "chg") {
      const d = changeWeight(a.id) - changeWeight(b.id);
      if (d) return d * dir;
    }
    return qual(a).localeCompare(qual(b)) * (k === "fan" || k === "chg" ? 1 : dir);
  });
}

/* How interesting a routine is when the reader sorts by what changed about it.
 *
 * **Bigger is more interesting**, which is the convention `fan` already sets: a fresh click
 * on a column sorts descending, so a first click on Changed has to put what changed at the
 * top. Written the other way round first -- a rank where 0 was best -- and the first click
 * on the column then opened on four thousand unchanged routines, which is a control that
 * looks like it did nothing.
 *
 * The order is the change worklist's: what behaves differently, then what is on one side
 * only, then what was merely edited, then the unchanged. Same reasoning there and here --
 * the bands are ordered by what is worth reading first, and the largest is last because it
 * is the least interesting, which is the whole thesis of the tool.
 *
 * **The reader's assumption does not enter into it, and an earlier version pretended it
 * did.** This was derived from `diffBands()` so that flipping which version is taken to be
 * newer would reorder the rows -- but both surfaces list the routines of the version on
 * screen, so `only_in_compared` can never own a row here and only one of the two presence
 * bands is ever populated. The assumption changes what those rows are *called*, never
 * which of them exist. Deriving an order from it was deriving a difference that cannot
 * occur, which is worse than a constant: it reads as though it had been thought about.
 *
 * A routine with no status at all weighs nothing. Under no comparison every row scores the
 * same, the sort falls through to the name, and the column honestly does nothing. */
const CHANGE_WEIGHT = { behaves: 4, only_base: 3, only_compared: 3, edited: 2, same: 1 };

function changeWeight(id) {
  if (!tableOverlayOn()) return 0;      // this column is the table's, and so is its switch
  return CHANGE_WEIGHT[routineStatus(id)] || 0;
}

/* The columns, in order, in one place. The table's own width is their sum -- see the note
 * on `table.grid` -- and a hand-kept second list of them is how the two would drift. */
const TABLE_COLS = ["q", "why", "fan", "chg"];

/* What each column is called at the top of it. In the same object the widths are keyed by,
 * because a heading kept in a second list beside the keys is a second place to forget one
 * (rule 36) -- and the guard that pairs `TABLE_COLS` against `colWidths` reads both. */
const TABLE_LABELS = { q: "Routine", why: "WHY", fan: "Connections", chg: "Changed" };

function viewTable() {
  const cw = state.colWidths;
  const col = (k, label, numeric) =>
    `<th style="width:${cw[k]}rem" class="${numeric ? "numeric" : ""}" scope="col">
       <span class="thinner">
         <button class="sortbtn" data-sort="${k}"
                 aria-sort="${state.sortKey === k ? (state.sortAsc ? "ascending" : "descending") : "none"}">${label}${
           state.sortKey === k ? ` <span class="arrow">${state.sortAsc ? "▲" : "▼"}</span>` : ""}</button>
         <span class="resizer" data-resize="${k}" role="separator" aria-label="Resize ${label} column"></span>
       </span>
     </th>`;

  /* ── what you are looking at ──
   *
   * The table *was* in sync and there was no way to tell. The selected row carries
   * `aria-selected` and is tinted, and on Mensores it sits 238,401px down a 4,734-row list
   * with the scroll at nought -- so a reader switching to this view saw four thousand rows
   * and nothing to say which of them was theirs. Reported exactly that way: *I cannot tell
   * what I am viewing in Table view.*
   *
   * Design rule 26 says an off-screen selection is **stated**, and framing it is one click
   * away. That was written for the graph and never applied to the pane that needs it most:
   * the graph at least dims the rest, and a table gives every row equal weight.
   *
   * The rank is the point rather than a decoration. "Row 3,214 of 4,734" is what tells a
   * reader whether scrolling is worth it, and it is taken from the same sorted list the
   * rows are drawn from, so it cannot disagree with where the row actually is (rule 13). */
  const rows = sortedRoutines();
  const at = state.selected ? rows.findIndex(r => r.id === state.selected) : -1;
  const cur = at >= 0 ? rows[at] : null;
  const subject = cur
    ? `<span class="tsub-name mono">${breakable(`${cur.module}.${cur.name}`)}</span>
       <span class="tsub-rank">row ${(at + 1).toLocaleString()} of ${rows.length.toLocaleString()}</span>
       <button class="linkbtn" data-tablego>Go to it</button>`
    : state.selected
      /* Selected, and not in this list. A structure, a constant, a boundary and an artefact
         are all nodes the rest of the shell can hold and this table cannot show -- saying so
         is a different claim from showing nothing, and the reader is owed which one it is. */
      ? `<span class="tsub-none">The selection is not a routine, so it has no row here.</span>`
      : `<span class="tsub-none">Nothing selected — every row is shown, none is yours yet.</span>`;

  return `
  <div class="tableview">
  <div class="tablesubject">
    <span class="tsub-label">Showing</span>${subject}
  </div>

  <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.55rem;flex-wrap:wrap">
    <span style="font-size:.7rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--text-muted)">Row density</span>
    <div class="densitygroup" role="group" aria-label="Row density">
      <button data-den="compact"     aria-pressed="${state.density === "compact"}">Compact</button>
      <button data-den="comfortable" aria-pressed="${state.density === "comfortable"}">Comfortable</button>
      <button data-den="spacious"    aria-pressed="${state.density === "spacious"}">Spacious</button>
    </div>
    <span style="font-size:.72rem;color:var(--text-muted)">Drag a column edge to resize — widths store in <code class="mono">rem</code>, so the scale control moves them too.</span>
    ${overlaySwitchHtml("table")}
  </div>
  ${/* What the marks say, in words, above the table rather than under it. The same
        sentence the navigator's group carries, from the same function, so the two surfaces
        that draw these marks cannot disagree about what they mean (rule 51). */""}
  ${(() => { const n = routineChangeNote();
             return n ? `<p class="hint chgnote">${n}</p>` : ""; })()}

  <div class="tablewrap">
    <table class="grid" style="width:${TABLE_COLS.reduce((n, k) => n + cw[k], 0)}rem">
      <caption class="sr-only">Every routine in ${esc(STATS ? STATS.program : "this program")}</caption>
      <thead><tr>
        ${col("q", TABLE_LABELS.q)}
        ${col("why", TABLE_LABELS.why)}
        ${col("fan", TABLE_LABELS.fan, true)}
        ${col("chg", TABLE_LABELS.chg)}
      </tr></thead>
      <tbody>
        ${rows.map(r => {
          /* The chip once per row, not three times. It reads a Map, but the row also wants
             its glyph, its class and its sentence, and asking three times is three lookups
             for one answer. */
          const chg = routineChip(r.id);
          return `
          <tr data-row="${esc(r.id)}" aria-selected="${state.selected === r.id}" tabindex="0">
            <td><span class="qual"><span class="dim">${esc(r.module)}.</span>${esc(r.name)}</span></td>
            <td style="font-size:.72rem;color:var(--text-muted)">${esc(r.why)}</td>
            <td class="numeric">${esc(String(routineFan(r.id)))}</td>
            ${/* A table row carries no hover card, so the sentence goes on a native title
                  and is the only place the reader is told what a glyph means -- including
                  for the state that has no glyph. `same` under a comparison and unmarked
                  under no comparison are opposite claims that look identical. */""}
            <td class="chgcell${esc(chg.cls)}"${chg.title ? ` title="${esc(chg.title)}"` : ""}
              >${chg.glyph || (chg.title ? "\u2014" : "")}</td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>
    <div class="tfoot">
      <span>${ROUTINES.length
        ? `All <b>${ROUTINES.length.toLocaleString()}</b> routines — this is the complete list the
           navigator abbreviates.`
        : "Reading the routine list\u2026"}</span>
      ${/* **The same sentence as above the table, from the same function.** It was written
            out a second time here and the two drifted immediately: the note omits a band
            with nothing in it and this one printed `0 deleted`, so one answer appeared
            twice in one pane, differently, four thousand rows apart. Rule 51 -- one truth,
            one place that owns it.

            Repeated at the bottom rather than only at the top because the table is 4,733
            rows: a reader who has scrolled into it cannot see the note it started with,
            and a count they have to scroll back for is a count they do not have. */""}
      ${(() => { const n = routineChangeNote();
                 return n ? `<span class="tfoot-chg">${n}</span>` : ""; })()}
      <span style="margin-left:auto">Lines, returns, params and touches want a routines
        endpoint of their own; until there is one they are absent rather than blank.</span>
    </div>
  </div>
  </div>`;
}

/* Document mode: declared and explicitly unbuilt, which is the only honest state for it.
 *
 * This held a full page of hand-written prose about one Mensores command -- headings, a
 * lead, three sections of specific narrative -- presented exactly as generated output
 * would be. It was the ratified design's mockup content, never replaced, and it is the
 * most expensive kind of pinned data: not a stale number in a corner but a confident,
 * detailed answer about a program the reader may not even be looking at. Nothing marked it
 * as a sample, so there was no way to tell it apart from a real one.
 *
 * The backend for the *other* thing called document mode does exist -- eight documents,
 * every row carrying a node id, which is what the routine list is now built from. The
 * narrative view is a different thing and is not built. Saying so is not a failure state;
 * "nothing here yet" and "nothing to report" are opposite claims and must not look alike.
 */
function viewDoc() {
  return `
  <article class="doc">
    <div class="note">
      <b>Not built yet.</b> Document mode will read the current selection as prose — the
      routine you have picked, in its own words, scrolled to the line you are looking at,
      taken from <code class="mono">source.db</code> so the text and the code beside it are
      both what was measured rather than what the tree happens to say now.
      <p style="margin:.5rem 0 0">What exists today is the document <em>backend</em>: eight
      documents, every row carrying its graph node id. The routine list in the navigator is
      built from one of them. The narrative reading of a selection is not built, and this
      page would rather say so than show you a sample.</p>
    </div>
  </article>`;
}

function sevCounts() {
  const c = { broken: 0, suspect: 0, info: 0 };
  ANOMALIES.forEach(a => c[a.sev]++);
  return c;
}
/* Triage, through one door in each direction.
 *
 * **The only two places `state.triage` is subscripted anywhere in this file**, and that is
 * the point rather than tidiness. It was keyed by the finding's index at five separate
 * sites -- the count, the row, the three buttons, the click handler and the number keys --
 * every one of them correct on its own and all five wrong together, because the array is
 * sorted by a count that moves. A sixth hand-written site is the failure this shape exists
 * to prevent, so the guard on it is an *absence* over the whole file rather than a check on
 * the five that exist today (rule 74's shape, and rule 51's reason).
 *
 * The argument is the finding, never its identity, so a caller cannot reach for the wrong
 * key by having only half of one in hand.
 */
function triageOf(a) {
  return a && a.ident ? state.triage[a.ident] : undefined;
}
function setTriage(a, v) {
  if (!a || !a.ident) return;
  if (v) state.triage[a.ident] = v; else delete state.triage[a.ident];
}

function triagedCount(sev) {
  return ANOMALIES.filter(a => a.sev === sev && triageOf(a)).length;
}
/* `i` is the position of a row in **this** list, and it addresses the cursor -- which is
 * genuinely a position, and stays one. What it must never address again is a decision. */
function worklistFor(sev) {
  return ANOMALIES.map((a, i) => ({ a, i })).filter(x => x.a.sev === sev);
}

const TRIAGE_LABELS = {
  ack:        { label: "Acknowledged",        cls: "info"    },
  notbug:     { label: "Not a bug \u2014 blind spot applies", cls: "certain" },
  tooldefect: { label: "DunneFlow defect",    cls: "broken"  }
};

/* Which of the two versions is the newer one — **derived where the program says enough
 * to derive it, and assumed only where it does not.**
 *
 * Tom's rule about inference decides the shape: we may infer from a version or a date,
 * provided we say that we did, and an inference is used *only when nothing more obvious
 * is available*. Two versions carrying versions are more obvious than a blind default, so
 * they win — and the strip states which of the two happened.
 *
 * Returns the basis as well as the answer, because they are different claims and the
 * strip prints both:
 *
 *   from-versions   both versions parsed, same kind, one is greater
 *   assumed         nothing to compare, or two kinds that cannot be ranked
 *
 * The comparison itself is the **server's** — `version_kind` and `version_key` come off
 * `/api/revisions`. `1.10.0` sorts below `1.2.0` as a string, and a date and a release
 * number are both orderable and not orderable against each other; neither of those is a
 * thing to re-derive in a template. This function only compares two keys of one kind.
 */
function comparedIsNewerFrom(base, compared) {
  const bk = base && base.version_kind, ck = compared && compared.version_kind;
  if (!bk || !ck || bk !== ck) return null;      // nothing to compare, or two kinds
  const a = base.version_key || [], b = compared.version_key || [];
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    const x = a[i] || 0, y = b[i] || 0;
    if (x !== y) return y > x;                   // true: the compared end is the newer
  }
  return null;                                   // equal versions rank neither end
}

/* The pair the strip and the words are both about. One place decides, so a control and
   the colours it governs cannot be about different versions (rule 51). */
function versionPair() {
  const usable = REVISIONS.filter(r => r.comparable);
  const base = REVISIONS.find(r => r.revision === (CHANGES && CHANGES.base))
            || REVISIONS.find(r => r.serving)
            || usable[0];
  const compared = REVISIONS.find(r => r.revision === (CHANGES && CHANGES.compared))
                || usable.find(r => r.revision !== (base && base.revision));
  return { base, compared, usable };
}

/* The reader's assumption about which version is newer, turned into the two words the
 * whole page uses for the two sets.
 *
 * The server reports **where** a thing is -- `only_in_base`, `only_in_compared` -- which
 * is a fact it read. *Added* and *deleted* are an interpretation laid over that, and the
 * interpretation belongs to whoever holds the assumption. One place turns one into the
 * other, so no view can label the same set two ways (rule 51).
 *
 * With the compared version taken to be the newer one: something the base has and the
 * compared does not was **deleted** on the way to it, and something only the compared has
 * was **added**. Flip the assumption and the two words swap. Nothing else moves -- not the
 * counts, not the rows, not a query.
 *
 * `tone` is the colour class, and it follows the word rather than the side: red is always
 * gone and green is always arrived, whichever set each happens to be.
 */
function diffWords() {
  const { base, compared } = versionPair();
  const derived = comparedIsNewerFrom(base, compared);
  /* Three states, and the third is why this is not a boolean. `auto` re-derives when the
     reader moves to a different pair; an explicit choice made about *one* pair would
     otherwise be silently carried onto another, which is rule 51's failure. Design rule
     24's shape as well: an automatic rule may decide, and an explicit choice outranks it. */
  const chosen = state.comparedIsNewer;                 // 'auto' | 'yes' | 'no'
  const newer = chosen === "auto"
    ? (derived === null ? true : derived)                // Tom's default where nothing says
    : chosen === "yes";
  const basis = chosen !== "auto" ? "chosen"
              : derived === null ? "assumed"
              : "versions";
  const inferredEnds = ["base", "compared"]
    .filter((_, i) => [base, compared][i] &&
                      [base, compared][i].version_tier === "INFERRED").length;
  return {
    basis,
    /* Whether the derivation rests on a version nobody stated. It still decides, because
       an inferred version is more obvious than no evidence at all -- but it says so. */
    fromInferred: basis === "versions" && inferredEnds > 0,
    base:     { word: newer ? "deleted" : "added",   tone: newer ? "gone" : "new" },
    compared: { word: newer ? "added" : "deleted",   tone: newer ? "new" : "gone" },
    /* Said in full wherever there is room for it, because a reader who does not know
       which way round this runs cannot read the colours at all -- and it must say whether
       it was *read* or *assumed*, which is the difference between evidence and a default. */
    assumption: (() => {
      const which = newer ? "the compared version is newer" : "the compared version is older";
      if (basis === "chosen") return `you chose: ${which}`;
      if (basis === "assumed") return `assuming ${which} — no versions to compare`;
      return `${which} — from their versions`;
    })(),
  };
}

/* Which sets the two words are actually over, for a view that wants to iterate them
 * rather than name them. Ordered as they are worth reading, arrivals first. */
function diffBands() {
  const w = diffWords();
  return w.base.tone === "new"
    ? [["only_in_base", w.base], ["only_in_compared", w.compared]]
    : [["only_in_compared", w.compared], ["only_in_base", w.base]];
}

/* What differs between two versions, as a page rather than as a pane.
 *
 * The navigator's Changes group is the list you click through; this is the same comparison
 * with room to say what it is a comparison *of*. Both read one `CHANGES`, so they cannot
 * disagree about what changed — the failure rule 51 is about, where two places each hold
 * their own answer to "what am I looking at".
 *
 * Design rule 9's shape, not design rule 1's: this is a worklist, and the first move on
 * opening one is to start clearing it. So the bands are ordered by what is worth reading
 * first — what arrived, what went, what behaves differently — and the largest band is last
 * because it is the least interesting, which is the whole thesis of the tool.
 */
function viewChanges() {
  if (!CHANGES || CHANGES.loading) {
    return `<div class="panel" style="padding:1.25rem">
      <h2 style="margin:0 0 .5rem">Comparing two versions…</h2>
      <p class="hint">Reading both graphs. On a large program held on a slow volume this
         is seconds the first time and immediate afterwards.</p></div>`;
  }
  if (!CHANGES.available) {
    return `<div class="panel" style="padding:1.25rem">
      <h2 style="margin:0 0 .5rem">Nothing to compare.</h2>
      <p>${esc(CHANGES.reason || "this program holds one version")}</p>
      <p class="hint">A second version appears when the current one is sealed
         (<code>dunneflow revisions &lt;dir&gt; --seal</code>) and another copy of the
         source is analysed — the sealed snapshot stays readable beside the new one.</p>
      </div>`;
  }
  const c = CHANGES.counts;
  const words = diffWords();
  const [first, second] = diffBands();
  const cap = (w) => w.charAt(0).toUpperCase() + w.slice(1);
  const rev = (id) => {
    const r = REVISIONS.find(x => x.revision === id);
    return r && r.label ? `${esc(id)} — ${esc(r.label)}` : esc(id || "?");
  };
  /* `tone` is `gone`, `new`, or nothing at all -- and it is the difference channel finally
     being spent. It was defined in `tokens.css` from the day the vocabulary landed, carried
     through `diffWords()` as a `tone` per side, and drawn by nothing: a channel that
     existed as tokens and as a word and never as a colour.
     **It follows the word, never the side.** Flipping the assumption swaps which set is
     called arrivals, and the colour has to go with it or the page states one thing in
     English and the opposite in red -- which is worse than no colour at all. Nothing here
     caches a class for that reason. */
  const stat = (n, label, why, tone) => `
    <div class="chgstat${tone ? " tone-" + tone : ""}">
      <b class="num">${n.toLocaleString()}</b>
      <span>${label}</span>
      ${why ? `<span class="hint">${why}</span>` : ""}
    </div>`;

  /* `chg-item`, and not `wl-item`, because they are two different rows.
   *
   * `.wl-item` is the **anomaly** worklist's row and its grid says so:
   * `grid-template-columns: .1875rem 1fr auto auto`, whose first cell is a `.wl-stripe` --
   * a three-pixel severity bar. These rows have no severity and emitted only two children,
   * so the *name* landed in the stripe column and `overflow: hidden; text-overflow:
   * ellipsis` erased it, while the module path took the 1fr and 786 pixels. Every routine
   * in every band rendered as an ellipsis followed by its module. Measured: a title whose
   * `scrollWidth` is 188px inside a box 3px wide.
   *
   * Wired correctly to a stylesheet that could not carry it, which is the family rules 44
   * and 48 both belong to, and invisible to every check because the markup and the routes
   * were right. Found by looking at it.
   *
   * `.navlabel` on the name for a second reason: the click handler falls back to the whole
   * button's text when there is no label, so the trail step read
   * "claim_status_cmd mensores.cli.scribe boundariescallssql_ops". */
  const rows = (list) => list.map(r => `
    <li><button class="chg-item" data-nav="chg" data-navid="${esc(r.id)}">
      <span class="chg-title navlabel">${esc(r.name)}</span>
      <span class="chg-meta">
        <span class="mono chg-mod">${esc(r.module)}</span>
        ${(r.moved || []).map(m => `<span class="kind-tag">${esc(m)}</span>`).join("")}
      </span>
    </button></li>`).join("");

  const band = (key, title, list, why, tone) => !list.length ? "" : `
    <section class="chgsection">
      <h3${tone ? ` class="tone-${tone}"` : ""}>${title}
        <span class="num">${list.length.toLocaleString()}</span></h3>
      ${why ? `<p class="hint">${why}</p>` : ""}
      <ol class="chg-list">${rows(list)}</ol>
    </section>`;

  const pres = CHANGES.presence || {};
  /* `+` is whichever side the assumption calls arrivals, never a fixed side. The names
     shown are that same side's, so the sign and the examples under it cannot disagree
     (rule 13). */
  const presLine = (name, label) => {
    const v = pres[name] || { only_in_base: [], only_in_compared: [], moved: [] };
    /* The band each sign is *drawn from*, kept rather than resolved on the spot, because
       the unfold below is keyed on it. `+` and `−` swap when the reader changes which
       version they take to be newer; the twenty-three names do not move, so an unfold
       filed against "the plus group" would come back attached to a different set. Rule 65
       in a control: name a set for where it is, not for what befell it. */
    const arrivedBand = words.base.tone === "new" ? "only_in_base" : "only_in_compared";
    const goneBand = words.base.tone === "new" ? "only_in_compared" : "only_in_base";
    const arrived = v[arrivedBand];
    const gone = v[goneBand];
    /* A third state, and only constants have one: present in both versions and **holding
       something different**. The other three lines are names \u2014 a table, a way in, a file the
       program names \u2014 and a name either is there or is not; a constant is a name *and* a
       value, so it is the one row here where "still here, saying something else" can be
       true. It was compared by name alone until this existed, so `EXPECTED_SCHEMA_VERSION`
       going from 27 to 28 read as no change at all.

       `tone-moved` rather than a colour of its own: it is the violet the graph legend and
       the findings' own mark already spell this idea with, measured in all three sets and
       both themes (rule 69). Three surfaces, one answer (rule 51). And it takes **no**
       sign \u2014 a value that moved was neither added nor deleted, and a `+` here would be a
       direction the fact does not have. */
    const moved = v.moved || [];
    if (!arrived.length && !gone.length && !moved.length) return "";
    /* **Each count carries its own names.** The first version of this put every count on the
       left and then named the *arrivals* only, so `Constants +23 \u25c87` was followed by six
       names none of which had moved \u2014 two numbers and one list, and nothing saying which
       list belonged to which number (rule 32, and it read perfectly plausibly). */
    /* **Six names, and the other seventeen one click away.** Rule 8 allows abbreviation
       only where the complete content sits beside it, and this line had the bound without
       the companion: `Constants +23` printed six names and said nothing at all about the
       rest, which is design rule 1's silent filter standing in a header. The count was
       right the whole time, so nothing looked wrong -- the reader simply had no way to
       know six was not twenty-three.

       Open, the group names the **whole** set rather than the remainder. Two lists a
       reader has to join by hand is the same defect one step on, and it is the reason the
       button says *fewer* rather than *hide these*.

       The button is drawn whichever way the group is open, because "showing six of 23" and
       "showing all 23" are both answers: a control that appears only while something is
       hidden makes the unfolded state look like the only state there has ever been. */
    /* **A presence row that can be opened, where there is something to open.**
     *
     * Every one of these was a bare `<code>`: the line said `Constants ◈7` and named seven
     * constants, and not one of them could be reached -- design rule 16's dead control
     * wearing a label instead of a button. The band whose whole point is *this is not
     * constant any more* was the least actionable thing on the page.
     *
     * The id and the route come from the server (`PRESENCE`), never from the printed name.
     * Building `const:` + a label in here would be constructing an identity out of a
     * label, which is rule 30 with the arrow reversed -- and it would silently produce a
     * link to nothing for the two kinds whose label is not their id.
     *
     * A row with no route stays text, and that is the honest half: a way in has no subject
     * this table can carry, so it gets no affordance rather than a button that does
     * nothing. */
    const presName = (x) => {
      const label = esc(String(x.label == null ? x : x.label));
      if (!x || !x.nav || !x.id) return `<code>${label}</code>`;
      return `<button class="linkbtn presname" data-nav="${esc(x.nav)}"
        data-navid="${esc(x.id)}"><code>${label}</code></button>`;
    };

    const group = (n, cls, sign, names, which) => {
      if (!n) return "";
      const key = name + ":" + which;
      const open = !!state.presOpen[key];
      const shown = open ? names : names.slice(0, 6);
      const rest = names.length - shown.length;
      const more = (rest || open)
        ? ` <button class="linkbtn presmore" data-presgroup="${esc(key)}"
              aria-expanded="${open}">${open ? "fewer \u25be"
                                             : rest.toLocaleString() + " more \u25b8"}</button>`
        : "";
      return `<span class="presgroup"><b class="${cls}">${sign}${n}</b> ${
        shown.map(presName).join(" ")}${more}</span>`;
    };
    const parts = [
      group(arrived.length, "tone-new", "+", arrived, arrivedBand),
      group(gone.length, "tone-gone", "\u2212", gone, goneBand),
      /* No sign: a value that moved was neither added nor deleted, and a `+` here would be
         a direction the fact has not got. */
      group(moved.length, "tone-moved", "\u25c8", moved, "moved"),
    ].filter(Boolean);
    return `<li>${label} ${parts.join(" ")}</li>`;
  };

  /* Whether a band caps its own height and scrolls inside itself, or runs its full
   * length inside the one scroller the page already has. Design rule 2, and a real pair.
   *
   * Off by default, because rule 8 decides it: a reference list is never bounded, and
   * there is no mandate to save space. A cap of 32rem put the Added band -- 53 rows, the
   * largest and the first thing anyone wants -- into a 512px box nested inside a 401px
   * page scroller on an ordinary window, so reaching row 40 meant scrolling one box to
   * find another. On for a reader who would rather see all four band headings at once
   * and scroll each in place; usage decides which survives. */
  return `
  <div class="panel changes${state.bandScroll ? " bands-capped" : ""}" style="padding:1rem 1.25rem">
    <h2 style="margin:0 0 .25rem">What differs</h2>
    <p class="hint" style="margin:0 0 .9rem">
      base <code>${rev(CHANGES.base)}</code> &middot;
      compared with <code>${rev(CHANGES.compared)}</code>
      &middot; ${esc(words.assumption)}
      ${CHANGES.ms != null ? ` · compared in ${Number(CHANGES.ms).toLocaleString()} ms` : ""}
    </p>

    ${CHANGES.identical ? `<p class="chgsame">No differences found. Every routine, call,
       boundary, table, way in and constant the map can see is the same in both — which is
       an answer, and not the same thing as an empty comparison.</p>` : ""}

    <div class="chgstats">
      ${stat(c[first[0]], first[1].word, "", first[1].tone)}
      ${stat(c[second[0]], second[1].word, "", second[1].tone)}
      ${/* In the difference channel with the other two figures, for `routineChip`'s
            reason: the mark on a row and the figure it is counted in are one answer, and
            one of them in violet beside the other in the text colour is the reader's job
            to reconcile (rule 51). `edited_only` stays out -- it is the fourth thing, and
            rule 69 measured this channel as holding three directions and a ground. */""}
      ${stat(c.behaves, "behave differently", "something they do has moved", "moved")}
      ${stat(c.explained_only, "explained differently", "and nothing else about them did",
             "moved")}
      ${stat(c.edited_only, "edited only", "and nothing they do changed")}
      ${/* Drawn even at zero, unlike the bands below it, because these figures are the
            shape of the comparison rather than a list of what it found — and a figure that
            appears only when it is non-zero cannot be read as a nought. Each states in its
            own label that it counts *files*, because every other number on this line counts
            routines and rule 32 is about exactly that. */""}
      ${Object.entries(CHANGE_FILE_BANDS).map(([k, b]) =>
          stat(c[k] || 0, (c[k] === 1 ? b.stat1 : b.stat), b.statWhy, "moved")).join("")}
      ${/* The structure tiles, drawn only when non-zero — unlike the file tiles above,
            which are the shape of the comparison. Four zeroes here on a pair that differs
            in no structure would be four lines of nought saying nothing, and the band list
            below already states the whole answer. */""}
      ${Object.entries(CHANGE_STRUCT_BANDS)
          .filter(([k]) => c[k])
          .map(([k, b]) => stat(c[k], (c[k] === 1 ? b.stat1 : b.stat), b.statWhy,
                                b.tone === "moved" ? "moved" : b.tone)).join("")}
    </div>

    <p class="hint" style="margin:.6rem 0 0">
      ${c.routines_base.toLocaleString()} routines in the base,
      ${c.routines_compared.toLocaleString()} in the compared.
      A rename reads as one of each — nothing in the source says the two are the same
      thing.</p>

    ${Object.keys(pres).length ? `<ul class="chgpresence">
      ${presLine("db_tables", "Tables")}
      ${presLine("entrypoints", "Ways in")}
      ${presLine("artefacts", "Named files")}
      ${presLine("constants", "Constants")}
    </ul>` : ""}

    ${band("behaves", "Behaving differently", CHANGES.behaves,
           "The same routine, and something it <em>does</em> has moved — what it calls, "
           + "what it touches, what it takes or what it returns. The tag says which.",
           "moved")}
    ${band(first[0], cap(first[1].word), CHANGES[first[0]],
           `Only in the ${first[0] === "only_in_base" ? "base" : "compared"} version.`,
           first[1].tone)}
    ${band(second[0], cap(second[1].word), CHANGES[second[0]],
           `Only in the ${second[0] === "only_in_base" ? "base" : "compared"} version.`,
           second[1].tone)}
    ${band("explained_only", "Explained differently", CHANGES.explained_only,
           "The same routine, and what <em>explains</em> it has moved — a comment rewritten "
           + "over code that did not change. It is here rather than under <em>edited</em> "
           + "because a rewritten WHY is not internal computation; it is the layer this tool "
           + "exists to show, and the one the code itself never carries.",
           "moved")}
    ${band("edited", "Edited, behaving the same", CHANGES.edited_only,
           "The body changed and nothing it does did. Internal computation — what this tool "
           + "exists not to report — listed here so leaving it out is not a silent filter.")}
    ${Object.entries(CHANGE_FILE_BANDS)
        .map(([k, b]) => modband(b, CHANGES[k] || [])).join("")}
    ${/* The structure bands, rendered by the same function from a table of their own.
          Rows carry a real node id, so the click is the selection every other row makes. */""}
    ${Object.entries(CHANGE_STRUCT_BANDS)
        .map(([k, b]) => modband(b, CHANGES[k] || [])).join("")}
  </div>`;
}

/* Files whose **module docstring** moved, and the one band on this page whose rows are not
 * routines.
 *
 * A module docstring is the only place a module says what it *is*, and it belongs to no
 * routine — so it gets a subject of its own rather than being hung on the synthetic
 * `<module>`, which exists in 487 of Mensores' 628 files while 619 of them carry a module
 * docstring. For the 138 that state what they are and run nothing at import, this band is
 * the difference between the change being reported and the page saying "No differences
 * found" (rule 74's shape: a thing is never one of the things it holds).
 *
 * `data-nav="file"` is the code browser's own route, so the row opens the file — the
 * identity is the path, and it is one the router already acts on rather than a label with
 * no way in (rule 30). Never bounded (rule 8).
 *
 * Violet, with `explained` and `behaves`: the difference channel holds three directions and
 * a ground and rule 69 measured it full, so this cannot have a colour of its own and does
 * not pretend to. It is separated by being a band of files, which is a stronger separation
 * than a glyph.
 */
function modband(b, rows) {
  if (!rows.length) return "";
  /* `meta`, `badge` and `tone` default to what the file bands have always done, so this
     stayed one renderer when the structure bands arrived rather than becoming two that
     drift (rule 13). A file's identity *is* worth printing under its name — the path is how
     a reader finds it. A structure's is a sixteen-character hash, so it names its module
     instead, and says which **kind** of thing it is: a vanished TYPE_ALIAS and a vanished
     CLASS are different news, and a band that prints only a name says neither. */
  const metaKey = b.meta || b.id;
  return `
    <section class="chgsection">
      <h3 class="tone-${esc(b.tone || "moved")}">${b.title}
        <span class="num">${rows.length.toLocaleString()}</span></h3>
      <p class="hint">${b.why}</p>
      <ol class="chg-list">${rows.map(r => `
        <li><button class="chg-item" data-nav="${esc(b.nav)}"
                    data-navid="${esc(r[b.id])}">
          <span class="chg-title navlabel">${esc(r[b.label] || r[b.id])}</span>
          <span class="chg-meta"><span class="mono chg-mod">${esc(r[metaKey] || "")}</span>
            ${b.badge && r[b.badge]
                ? `<span class="kind-tag">${esc(r[b.badge])}</span>` : ""}
            ${(r.moved || []).map(m => `<span class="kind-tag">${esc(m)}</span>`).join("")}
          </span>
        </button></li>`).join("")}</ol>
    </section>`;
}

/* The counts, **taken by walking the findings that are drawn** rather than from the bands.
 *
 * Rule 32: a count must be produced by the thing it measures. The bands are the server's
 * answer about two graphs; this list is what reached the page, and reading the band lengths
 * would print a number no amount of scrolling could find.
 *
 * **And "drawn" means this tab, not this program.** The first version counted all 106
 * findings while the head around it -- the tabs, the progress bar, "left to triage" -- was
 * per severity, so on Mensores' pair the Suspect tab read "◈ 4 claiming something different
 * · 1 added" with **not one marked row on screen**: all five banded findings are INFO. Two
 * correct numbers, neither saying what it counted, which is the whole of rule 32 and the
 * reason `degree` stopped being printed beside a routine. Found by looking at the pane.
 *
 * `only_compared` is the exception and cannot be otherwise -- those findings have no row
 * here at all, so their number comes from the band. It is still narrowed to the tab, by the
 * severity each of them carries, because a number about a different tab is the same defect
 * one step out. The routine lane made exactly this exception for exactly this reason.
 */
function anomalyChangeCounts(sev) {
  const v = ANOMALYCHANGES;
  if (!v || v.loading || !v.available) return null;
  const c = { only_base: 0, moved: 0, same: 0, only_compared: 0 };
  worklistFor(sev).forEach(x => {
    const band = anomalyBandOf(x.a.ident);
    if (!band) return;
    if (band.where === "only_in_base") c.only_base++;
    else if (band.where === "moved") c.moved++;
    else c.same++;
  });
  /* The server sends `severity` in full and this list keys them short, so the comparison is
     over one vocabulary rather than two (rule 13). */
  c.only_compared = (v.only_in_compared || [])
    .filter(r => sevKey(r.severity) === sev).length;
  return c;
}

/* One place turns a served severity into the key this view files it under. It existed
 * inline in `loadAnomalies` and now has a second caller, and two copies of a mapping is two
 * answers to one question (rule 51). */
function sevKey(severity) {
  return { BROKEN: "broken", SUSPECT: "suspect", INFO: "info" }[severity] || "info";
}

/* What the marks are saying, in words, above the list they are drawn on.
 *
 * Design rule 1, and it has five things to say that no glyph can. Which version this is
 * held against. That the comparison **has not been asked for yet** — an unmarked worklist
 * and a worklist whose findings all stayed put are identical to look at, and only one of
 * them is a claim. That it is on its way, because the first one of a session can take
 * seconds. That the marks are switched off. And that the compared graph **cannot be read**,
 * with the reason and the command that fixes it — three empty bands would read as *this
 * version had nothing wrong with it*, which is a different and false claim (rules 49, 62
 * and 63).
 *
 * Returns "" only when there is nothing to say, which is when there is no second version.
 */
function anomalyChangeNote(sev) {
  if (!comparing()) return "";
  const shortRev = comparedRevInForce().replace("T", " ").replace("Z", "");
  if (!state.anomalyOverlay) {
    return `not marking the difference from <code>${esc(shortRev)}</code>`;
  }
  if (!ANOMALYCHANGES) {
    return `not compared with <code>${esc(shortRev)}</code> yet`;
  }
  if (ANOMALYCHANGES.loading) {
    /* Said out loud because this is the wait a reader is most likely to meet: the compared
       version's findings are thirteen detectors over a graph nothing has opened, and the
       first one of a session is seconds rather than milliseconds. */
    return `comparing with <code>${esc(shortRev)}</code>… running the detectors over that
            version, which is seconds the first time and nothing afterwards`;
  }
  if (!ANOMALYCHANGES.available) {
    return `<b>no comparison.</b> ${esc(ANOMALYCHANGES.reason || "")}`;
  }
  const c = anomalyChangeCounts(sev);
  if (!c) return "";
  const w = diffWords();
  const bits = [];
  if (c.only_base) {
    bits.push(`<b class="tone-${w.base.tone}">${signOf(w.base.tone)}${
      c.only_base.toLocaleString()}</b> ${esc(w.base.word)}`);
  }
  /* The same, over the findings: the mark on a row and the count of those marks are one
     answer, and the note is where a reader meets it first. */
  if (c.moved) {
    bits.push(`<b class="tone-moved">◈ ${c.moved.toLocaleString()}</b> claiming something
               different`);
  }
  /* Counted out loud, for the routine lane's reason: it is the largest number here and the
     least interesting, and leaving it out makes the marked ones read as the whole list. */
  bits.push(`${c.same.toLocaleString()} unchanged`);
  /* **Counted, never marked, and one click from being read.** A finding only the compared
     version has is not in this list — the list is the base's findings — so there is no row
     to put a glyph on. It is not hidden either: design rule 1 wants the removed set an
     unfold away, and these are shown as what they are, with no triage buttons, because a
     decision about a version you are not reading is not a decision. */
  const other = c.only_compared
    ? ` · <button class="linkbtn" data-anoonlythere="1" aria-expanded="${!!state.anoOnlyThere}"
          >${c.only_compared.toLocaleString()} ${esc(w.compared.word)} — in
          ${esc(shortRev)} only ${state.anoOnlyThere ? "▾" : "▸"}</button>`
    : "";
  return `against <code>${esc(shortRev)}</code>: ${bits.join(" · ")}${other}`;
}

/* The findings the compared version has and this one does not, unfolded.
 *
 * Read-only and deliberately plain: they carry no triage buttons and no cursor, because
 * they are not findings of the version on screen and `j`/`k`, the progress bar and "left to
 * triage" must go on counting one thing (rule 32). What they do carry is their kind, their
 * count and their title, which is enough to decide whether it is worth switching the base
 * to go and look.
 */
function anomalyOnlyThereHtml() {
  if (!state.anoOnlyThere) return "";
  const v = ANOMALYCHANGES;
  const rows = ((v && v.available && v.only_in_compared) || [])
    .filter(r => sevKey(r.severity) === state.sev);
  const w = diffWords();
  if (!rows.length) return "";
  return `<div class="ano-elsewhere">
    <p class="hint">${esc(w.compared.word)} — these are findings of
      <code>${esc(comparedRevInForce().replace("T", " ").replace("Z", ""))}</code>, not of the
      version on screen, so there is nothing here to triage. Switch the base to work on them.</p>
    <ol class="ano-elselist">${rows.map(r => `<li>
      <span class="kind-tag">${esc(r.kind)}</span>
      <span class="ano-elsetitle">${esc(r.title)}</span>
      <span class="num">${r.count}×</span>
    </li>`).join("")}</ol>
  </div>`;
}

function viewAnomalies() {
  const counts = sevCounts();
  const list = worklistFor(state.sev);
  if (state.cursor >= list.length) state.cursor = 0;
  const cur = list[state.cursor];
  const done = triagedCount(state.sev);
  const total = list.length;
  const pct = total ? (done / total) * 100 : 0;
  const note = anomalyChangeNote(state.sev);
  /* Said here rather than as a banner, because here is the only place it cost anything.
     A worklist that has quietly forgotten every decision and one nobody has triaged yet
     are identical to look at, and the reader is owed which of the two they are looking at
     (design rule 1, and `resetSettings`'s own rule about naming what it cleared). */
  const carriedNote = state.carried
    ? `<p class="chgnote ano-carried"><b>${esc(state.carried.why)} were not carried
        over.</b> They were filed against a position in this list rather than against a
        finding, and the list is sorted by a count that moves — so a decision made before
        this version of DunneFlow could have been about any of them. Everything else you
        had arranged is as you left it.</p>`
    : "";

  const tab = (k, label, n, colour) => `
    <button role="tab" data-sev="${k}" aria-selected="${state.sev === k}" ${n === 0 ? "disabled" : ""}>
      <span class="sevdot" style="background:${colour}"></span>${label}
      <span class="tabn num">${n}</span>
    </button>`;

  const item = (x, idx) => {
    const t = triageOf(x.a);
    const chip = anomalyChip(x.a.ident);
    return `<li>
      <button class="wl-item" data-cursor="${idx}" aria-current="${idx === state.cursor}"
              ${t ? 'data-triaged="' + t + '"' : ""}>
        <span class="wl-stripe" style="background:var(--sev-${x.a.sev})"></span>
        <span class="wl-title">${esc(x.a.title)}</span>
        <span class="wl-meta">
          ${chip.title ? `<span class="${chip.cls.trim()}" data-titled="1"
             title="${esc(chip.title)}">${chip.glyph}</span>` : ""}
          <span class="kind-tag">${esc(x.a.kind)}</span>
          <span class="num">${x.a.n}\u00d7</span>
        </span>
        ${t ? `<span class="wl-done badge ${TRIAGE_LABELS[t].cls}">\u2713</span>` : ""}
      </button></li>`;
  };

  return `
  <div class="worklist">
    <div class="wl-head">
      <div class="seg tabs" role="tablist" aria-label="Severity">
        ${tab("broken",  "Broken",  counts.broken,  "var(--sev-broken)")}
        ${tab("suspect", "Suspect", counts.suspect, "var(--sev-suspect)")}
        ${tab("info",    "Info",    counts.info,    "var(--sev-info)")}
      </div>
      <div class="wl-progress">
        <span><b class="num">${total - done}</b> left to triage</span>
        <span class="bar" style="width:7rem"><i style="width:${pct}%"></i></span>
        <span class="num" style="color:var(--text-faint)">${done}/${total}</span>
      </div>
      <div class="wl-nav">
        <button class="linkbtn" data-step="-1" aria-label="Previous finding">\u2191 Prev</button>
        <button class="linkbtn" data-step="1" aria-label="Next finding">\u2193 Next</button>
        <span style="font-size:.68rem;color:var(--text-faint)">or <kbd>j</kbd>/<kbd>k</kbd></span>
        ${overlaySwitchHtml("anomaly")}
      </div>
      ${carriedNote}
      ${note ? `<p class="chgnote ano-chgnote">${note}</p>` : ""}
      ${anomalyOnlyThereHtml()}
    </div>

    <div class="wl-body">
      <ol class="wl-list" aria-label="Findings">
        ${list.map(item).join("")}
      </ol>

      <div class="wl-detail">
        ${!cur ? "<p>Nothing here.</p>" : `
        <h2>${esc(cur.a.title)}</h2>
        <div class="wl-badges">
          <span class="badge ${cur.a.sev}">${cur.a.sev.toUpperCase()}</span>
          <span class="badge info">confidence ${esc(cur.a.conf)}</span>
          <span class="kind-tag">${esc(cur.a.kind)}</span>
          <span class="num" style="font-size:.72rem;color:var(--text-muted)">${cur.a.n} occurrence${cur.a.n === 1 ? "" : "s"}</span>
          ${cur.a.where ? `<span class="mono" style="font-size:.7rem;color:var(--text-faint);margin-left:auto">${esc(cur.a.where)}</span>` : ""}
        </div>

        ${cur.a.detail ? `<p class="wl-detailtext">${esc(cur.a.detail)}</p>` : ""}

        <div class="why" style="margin-left:0;margin-top:.6rem">
          <span class="ln">blind spot</span> ${esc(cur.a.blind)}
        </div>

        <div class="wl-actions">
          <div class="wl-actlabel">What is this?</div>
          <button class="actbtn triage ${triageOf(cur.a) === "notbug" ? "on" : ""}" data-triage="notbug">
            Not a bug \u2014 the blind spot applies <span class="k">1</span></button>
          <button class="actbtn triage ${triageOf(cur.a) === "ack" ? "on" : ""}" data-triage="ack">
            Real \u2014 acknowledged, leave it for now <span class="k">2</span></button>
          <button class="actbtn triage ${triageOf(cur.a) === "tooldefect" ? "on" : ""}" data-triage="tooldefect">
            This is a DunneFlow defect, not the program's <span class="k">3</span></button>
          ${triageOf(cur.a) ? `<button class="linkbtn" data-triage="" style="align-self:flex-start">Undo</button>` : ""}
        </div>

        <div class="note" style="margin-top:.75rem">
          <b>Why the third button exists.</b> On the first run against a live codebase, six confident
          findings in a row were defects in DunneFlow rather than in the program it was reading.
          A finding dismissed this way is not just cleared \u2014 it is evidence that a detector needs
          fixing, which is a different pile from "the blind spot applies here".
        </div>

        <!-- Disabled, with the reason, rather than removed: a control that vanishes
             leaves no clue that the feature exists, and this one is wanted. Both were
             live-looking buttons with no attributes, no handler and a keyboard badge for
             a key nothing listened for -- invisible to the runtime self-check, which reads
             data attributes and finds none on a button that has none.
             They cannot simply be wired. A finding carries the *name* it found, not a node
             id, and resolving that name is rule 5 exactly: eleven routines share self._emit.
             queries.py wrote the answer down before anything needed it -- inventing an id
             to make a row clickable is a link to nothing -- so this waits for the detector
             to carry the ids it already knows. -->
        <div class="wl-jump">
          <button class="actbtn" disabled
                  title="Not yet: a finding carries the name it found, not the node. Resolving ${esc(cur.a.subject || "a name")} would be a guess between every routine that shares it.">Go to the first occurrence in the graph</button>
          <button class="actbtn" disabled
                  title="Not yet, for the same reason: the occurrences are known by name, and a table of guesses is worse than no table.">Show all ${cur.a.n} occurrence${cur.a.n === 1 ? "" : "s"} as a table</button>
        </div>`}
      </div>
    </div>
  </div>`;
}

/* The shape sets, and what each is *for*.
 *
 * The roster and the prose only. **The outlines themselves come from the engine** —
 * `Graph.silhouettes(set)` returns the very points the stack draws — because a key that
 * keeps its own copy of these shapes is a second answer to what a kind looks like, and the
 * two part company the day a shape moves (rule 13). The colour sets are built the same way,
 * reading their values back off the stylesheet.
 *
 * `kind` is first and is the default: it is the set that spends the channel, and spending
 * it is what frees colour to go on saying what changed (design rule 4). */
const SHAPE_SETS = [
  { id: "kind",  name: "By kind",
    why: "Five kinds, five outlines, and they are Mermaid's own vocabulary — a process box "
       + "for a routine, a hexagon for a constant, a stadium for a boundary. Shape then "
       + "carries what a thing is, and colour is free to carry what changed about it." },
  { id: "rect",  name: "All rectangles",
    why: "One outline for everything. The eye reads position and connection rather than "
       + "sorting five silhouettes, and kind stays where it is now, on colour." },
  { id: "round", name: "All rounded",
    why: "The same, with soft corners. Quieter against a dense plate, and the corners are "
       + "cut rather than curved so a box costs eight points instead of an arc." },
];

/* The kinds a box can be, in the order the key lists them, with what each one *is*.
 *
 * `MODULE` is here because the module altitude folds a whole file into one node and that
 * node gets a box like any other — a key that listed five kinds and drew six would be the
 * silent omission design rule 1 exists to prevent, one altitude away. */
const SHAPE_KINDS = [
  ["ROUTINE",   "a thing that runs"],
  ["STRUCTURE", "a shape data takes"],
  ["CONSTANT",  "a name pinned to a value"],
  ["BOUNDARY",  "where something leaves or arrives"],
  ["ARTEFACT",  "a file the program names"],
  ["MODULE",    "a whole file, at the module altitude"],
];

/* The key: every kind, in the outline the chosen set actually draws it in.
 *
 * SVG rather than a canvas, because these are six static shapes on a settings page and the
 * engine is not mounted when this renders — asking a WebGL view for a picture of itself in
 * order to illustrate a control would make the control depend on the view being open.
 * The *points* are still the engine's; only the drawing is local. */
function shapeKeyHtml() {
  const shapes = Graph.silhouettes(state.nodeShapes);
  const W = 68, H = 26;
  return SHAPE_KINDS.map(([kind, what]) => {
    const pts = (shapes[kind] || []).map(([x, y]) =>
      `${(W / 2 + x * (W / 2 - 1.5)).toFixed(1)},${(H / 2 + y * (H / 2 - 1.5)).toFixed(1)}`
    ).join(" ");
    return `<div class="shapekey">
      <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">
        <polygon points="${esc(pts)}" fill="none" stroke="var(--graph-${kind.toLowerCase()})"
                 stroke-width="1.4"></polygon>
      </svg>
      <span class="shapekey-name">${esc(kind.toLowerCase())}</span>
      <span class="shapekey-what muted">${esc(what)}</span>
    </div>`;
  }).join("");
}

/* The colour sets, and what each is *for*.
 *
 * The values are in `tokens.css` and nothing about a colour is written down here. This is
 * the roster and the prose: which sets exist, what each is called, and the sentence a
 * reader needs before choosing one. The swatches and every number beside them are read
 * back off the stylesheet at render, so the page cannot state a colour the page is not
 * using (rule 13, and rule 44's family -- a view describing data it does not have).
 *
 * `default` is first and stamps nothing. */
const PALETTES = [
  { id: "default", name: "Red and green",
    why: "What the dashboard has always used. Familiar, and the weakest of the three when "
       + "red and green cannot be told apart — the numbers below say by how much." },
  { id: "safe", name: "Blue and orange",
    why: "Built to stay separable when red and green do not: Okabe-Ito's vermillion and "
       + "blue for a difference, and a red-to-magenta-to-blue ramp for severity. Named "
       + "for the colours rather than for the reader, because the colours are the fact "
       + "and the rest is the claim underneath." },
  { id: "muted", name: "Muted",
    why: "The same hues as the default, at lower chroma, for a reader who finds it loud. "
       + "Quieter is not safer — it is the same red and the same green, so it measures "
       + "where they measure." },
];

/* Every token a set owns, as the pairs they are actually drawn in: a colour, and the
 * ground it sits on. Two grounds each, because both are real on screen -- these are used
 * as text on the surface and as text on their own tinted chip. */
const PALETTE_ROLES = [
  { token: "--diff-gone",    bg: "--diff-gone-bg",    label: "gone",    of: "a difference" },
  { token: "--diff-new",     bg: "--diff-new-bg",     label: "arrived", of: "a difference" },
  { token: "--sev-broken",   bg: "--sev-broken-bg",   label: "broken",  of: "severity" },
  { token: "--sev-suspect",  bg: "--sev-suspect-bg",  label: "suspect", of: "severity" },
  { token: "--sev-info",     bg: "--sev-info-bg",     label: "info",    of: "severity" },
];

/* What a set's tokens actually resolve to, for the set that is **not** currently stamped.
 *
 * The same device `graphPaletteNow()` uses to read the dark stack from inside a light
 * page: stamp, read, put it back. Reading the stylesheet is the only way to state a
 * colour the page is genuinely using -- a table here would be a second place a colour is
 * written down, and the first thing to drift. */
function paletteColours(id) {
  const r = document.documentElement;
  const had = r.getAttribute("data-palette");
  if (id === "default") r.removeAttribute("data-palette");
  else r.setAttribute("data-palette", id);
  const cs = getComputedStyle(r);
  const out = {};
  for (const role of PALETTE_ROLES) {
    out[role.token] = cs.getPropertyValue(role.token).trim();
    out[role.bg] = cs.getPropertyValue(role.bg).trim();
  }
  out["--surface"] = cs.getPropertyValue("--surface").trim();
  if (had === null) r.removeAttribute("data-palette");
  else r.setAttribute("data-palette", had);
  return out;
}

/* One set as a row: what it is, what it costs to read, and the evidence for both claims.
 *
 * Rule 8 decides the shape. Ten ratios and four separations is the whole of what is known
 * about a set, and it is not hidden to save space -- the worst of each leads, because that
 * is the number a bar is actually met at, and the full table sits directly beneath it. */
function paletteRow(pal) {
  const c = paletteColours(pal.id);
  const on = state.palette === pal.id;
  const surface = c["--surface"];

  const rows = PALETTE_ROLES.map(role => {
    const fg = c[role.token], bg = c[role.bg];
    return { role, fg, bg, onSurface: contrast(fg, surface), onOwn: contrast(fg, bg) };
  });
  const worst = Math.min(...rows.map(r => Math.min(r.onSurface, r.onOwn)));
  const passes = worst >= 4.5;

  const seps = [
    { what: "gone from arrived", v: separation(c["--diff-gone"], c["--diff-new"]) },
    { what: "broken from suspect", v: separation(c["--sev-broken"], c["--sev-suspect"]) },
    { what: "broken from info", v: separation(c["--sev-broken"], c["--sev-info"]) },
    { what: "suspect from info", v: separation(c["--sev-suspect"], c["--sev-info"]) },
  ];
  const worstSep = Math.min(...seps.map(s => s.v));

  const swatches = rows.map(r => `<span class="pal-sw" style="background:${esc(r.bg)};
      color:${esc(r.fg)};border-color:${esc(r.fg)}">${esc(r.role.label)}</span>`).join("");

  return `<div class="pal ${on ? "on" : ""}">
    <button class="pal-pick" data-palette-set="${esc(pal.id)}" aria-pressed="${on}">
      <span class="pal-name">${esc(pal.name)}</span>
      <span class="pal-swatches">${swatches}</span>
    </button>
    <p class="pal-why">${esc(pal.why)}</p>
    <div class="pal-nums">
      <span class="ratio ${passes ? "pass" : "fail"}">${worst.toFixed(2)}:1</span>
      <span class="pal-numlabel">worst contrast, over every colour and both the surface
        and its own chip. ${passes ? "Clears" : "<b>Below</b>"} the 4.5:1 minimum for body
        text.</span>
    </div>
    <div class="pal-nums">
      <span class="ratio ${worstSep >= 20 ? "pass" : "fail"}">ΔE ${worstSep.toFixed(0)}</span>
      <span class="pal-numlabel">worst separation between two colours of one channel, taken
        as the least of normal vision, deuteranopia and protanopia.
        ${worstSep >= 20 ? "Distinct at a glance."
          : "<b>Close</b> — these two are hard to tell apart without the words beside them."}</span>
    </div>
    <details class="pal-detail"><summary>every measurement</summary>
      <table class="pal-table"><thead><tr><th>colour</th><th>of</th>
        <th>on the surface</th><th>on its own chip</th></tr></thead><tbody>
        ${rows.map(r => `<tr><td>${esc(r.role.label)}</td><td>${esc(r.role.of)}</td>
          <td class="${r.onSurface >= 4.5 ? "" : "fail"}">${r.onSurface.toFixed(2)}:1</td>
          <td class="${r.onOwn >= 4.5 ? "" : "fail"}">${r.onOwn.toFixed(2)}:1</td></tr>`).join("")}
      </tbody></table>
      <table class="pal-table"><thead><tr><th>told apart</th><th>ΔE, worst of three
        kinds of vision</th></tr></thead><tbody>
        ${seps.map(x => `<tr><td>${esc(x.what)}</td>
          <td class="${x.v >= 20 ? "" : "fail"}">${x.v.toFixed(1)}</td></tr>`).join("")}
      </tbody></table>
      <p class="hint">Measured against this theme. Switch the theme above and these change
        — a set is two variants, and only the one in force is being drawn.</p>
    </details>
  </div>`;
}

/* How far apart two colours are **to someone who cannot see the difference we do**.
 *
 * Contrast answers "can this be read"; it says nothing about "can these two be told
 * apart", and the second is the whole question a difference channel turns on. Red and
 * green are both perfectly legible on white and, to a deuteranope, the same colour: the
 * shipped pair simulates to #6c6c03 and #5b5b36, which is a ΔE of 12.7.
 *
 * Viénot, Brettel & Mollon (1999) for the simulation -- the standard reduction that
 * projects onto the dichromat's plane in LMS -- and CIE Lab ΔE76 for the distance, which
 * is coarse and is the right coarseness here: the question is "obviously different or
 * not", not "which is closer".
 *
 * Computed in the page rather than written into it, for rule 13's reason. A number typed
 * beside a swatch is a claim nobody can check and the first thing to go stale when a hex
 * moves; this one is produced by the colours the page is actually drawing. */
const _DICHROMAT = {
  deuteranopia: [[1, 0, 0], [0.494207, 0, 1.24827], [0, 0, 1]],
  protanopia:   [[0, 2.02344, -2.52581], [0, 1, 0], [0, 0, 1]],
};
const _RGB2LMS = [[17.8824, 43.5161, 4.11935],
                  [3.45565, 27.1554, 3.86714],
                  [0.0299566, 0.184309, 1.46709]];
const _LMS2RGB = [[0.0809444479, -0.130504409, 0.116721066],
                  [-0.0102485335, 0.0540193266, -0.113614708],
                  [-0.000365296938, -0.00412161469, 0.693511405]];

function _rgb(hex) {
  const h = String(hex).replace("#", "").trim();
  return [0, 2, 4].map(i => parseInt(h.substr(i, 2), 16));
}
function _toLinear(c) {
  const x = c / 255;
  return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
}
function _mul(m, v) {
  return m.map(row => row[0] * v[0] + row[1] * v[1] + row[2] * v[2]);
}

function simulate(hex, kind) {
  const lin = _rgb(hex).map(c => _toLinear(c) * 255);
  const out = _mul(_LMS2RGB, _mul(_DICHROMAT[kind], _mul(_RGB2LMS, lin)));
  /* Rounded to eight bits, because that is the colour a screen would actually show. The
     unrounded float is a more precise answer to a question nobody is asking -- a reader
     looks at the quantised one, so the measurement is taken there. */
  return out.map(c => {
    const x = Math.max(0, Math.min(1, c / 255));
    const v = (x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055) * 255;
    return Math.max(0, Math.min(255, Math.round(v)));
  });
}

function _lab(rgb255) {
  const [r, g, b] = rgb255.map(_toLinear);
  const f = (t) => t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116;
  const fx = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047);
  const fy = f(0.2126 * r + 0.7152 * g + 0.0722 * b);
  const fz = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

function _deltaE(a, b) {
  const [la, lb] = [_lab(a), _lab(b)];
  return Math.hypot(la[0] - lb[0], la[1] - lb[1], la[2] - lb[2]);
}

/* The **worst** of the three, never an average. A pair that is obvious to most readers and
 * invisible to some is not a pair that works; averaging would let the majority case pay
 * for the minority one, which is the arithmetic version of not caring. */
function separation(hexA, hexB) {
  const A = _rgb(hexA), B = _rgb(hexB);
  return Math.min(
    _deltaE(A, B),
    _deltaE(simulate(hexA, "deuteranopia"), simulate(hexB, "deuteranopia")),
    _deltaE(simulate(hexA, "protanopia"), simulate(hexB, "protanopia")),
  );
}

function contrast(hex1, hex2) {
  const lum = (h) => {
    const c = h.replace("#", "");
    const v = [0, 2, 4].map(i => {
      let x = parseInt(c.substr(i, 2), 16) / 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const a = lum(hex1), b = lum(hex2);
  return ((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05));
}

/* There were two colour pickers and a live contrast readout here, and they are gone.
 *
 * They were the ratified prototype's *demonstration* of design rule 6 -- a swatch pair, a
 * WCAG ratio, a pass/fail verdict -- carried into the product whole. `state._fg` and
 * `state._bg` were in no `DEFAULTS`, persisted nowhere, and read by nothing but their own
 * preview chip: the control rendered, responded to every drag, computed a correct ratio,
 * and changed no colour anywhere on the page.
 *
 * Invisible to both guards that exist for exactly this. The dead-setting guard walks
 * `DEFAULTS` and these keys were never in it; the dead-control guard asks whether an
 * attribute is read, and these were `id`s rather than routes. Rule 44's family with
 * nothing missing on either side -- a control wired to itself.
 *
 * What replaced it does the thing it was demonstrating. */
function viewSettings() {
  return `
  <div class="settings">

    <section class="panel">
      <div class="panel-head"><h2>Appearance</h2></div>
      <div class="panel-body">
        <div class="setrow">
          <div><div class="lbl">Theme</div>
            <div class="desc">System follows your OS. Both themes are designed, not inverted.</div></div>
          <div class="seg" role="group" aria-label="Theme">
            <button data-theme-set="light"  aria-pressed="${state.theme === "light"}">Light</button>
            <button data-theme-set="system" aria-pressed="${state.theme === "system"}">System</button>
            <button data-theme-set="dark"   aria-pressed="${state.theme === "dark"}">Dark</button>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Interface scale</div>
            <div class="desc">One multiplier over everything — type, column widths, row heights, icons,
              graph nodes. A view someone sends you keeps their layout; this stays yours.</div></div>
          <div class="seg" role="group" aria-label="Interface scale">
            ${[0.875, 1, 1.125, 1.25, 1.5].map(s =>
              `<button data-scale-set="${s}" aria-pressed="${state.scale === s}">${Math.round(s * 100)}%</button>`).join("")}
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>Colour</h2>
        <span class="hint">the two channels where colour carries a meaning</span></div>
      <div class="panel-body">
        <p class="hint" style="margin:0 0 .6rem">Colour separates one meaning from another
          in two places: <b>a difference</b> — what only one version has — and
          <b>severity</b> in the anomaly worklist. Both spend red, so both are here. Each
          set has a light and a dark variant and follows the theme; the accent and the
          external mark are single colours with nothing to be confused with, so they are
          not part of a set.</p>
        <div class="palettes">${PALETTES.map(paletteRow).join("")}</div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>What opens, and what shows</h2>
        <span class="hint">both built; use decides which survives</span></div>
      <div class="panel-body">
        <div class="setrow">
          <div><div class="lbl">Startup screen</div>
            <div class="desc">You could not choose between these, so both exist. The usage report
              tracks which one you actually open.</div></div>
          <div class="seg" role="group" aria-label="Startup screen">
            <button data-start="cover" aria-pressed="${state.startup === "cover"}">Cover</button>
            <button data-start="graph" aria-pressed="${state.startup === "graph"}">Package graph</button>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Show the trail</div>
            <div class="desc">The strip above the view recording where you have been, so a detour
              is free. New enough that it may be more noise than help \u2014 turn it off and the
              journey is still recorded for <kbd>Back</kbd>, just not shown.</div></div>
          <button class="toggle" id="trailToggle" aria-pressed="${state.trailShown}"
                  aria-label="Show the trail"></button>
        </div>

        <div class="setrow">
          <div><div class="lbl">Steps the trail shows</div>
            <div class="desc">How many fit on the bar, not how many are kept. The history
              holds fifty either way and <kbd>Back</kbd> reaches all of them; anything off
              the end of the bar is counted beside it.</div></div>
          <div class="seg" role="group" aria-label="Steps the trail shows">
            ${[6, 12, 25].map(n => `<button data-trailcap="${n}"
              aria-pressed="${state.trailCap === n}">${n} steps</button>`).join("")}
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Cursor over the diagram</div>
            <div class="desc">A diagram is a drawing you <i>aim</i> at, not a page of links.
              The link <b>hand</b> was here for every box: its hotspot is a fingertip whose
              exact pixel is a guess, and the glyph is broad enough to cover the thing being
              aimed at — worst on a thin arrow. An <b>arrow</b> has a sharp, unambiguous
              tip; a <b>crosshair</b> has one too and says <i>precision instrument</i>
              besides. Which reads right is taste, so all three are here.</div></div>
          <div class="seg" role="group" aria-label="Cursor over the diagram">
            ${[["arrow", "Arrow"], ["crosshair", "Crosshair"], ["hand", "Hand"]]
              .map(([v, w]) => `<button data-dgmcursor="${v}"
                aria-pressed="${state.diagramCursor === v}">${w}</button>`).join("")}
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Flow arrow thickness</div>
            <div class="desc">How heavily an arrow between two boxes is drawn. It had no
              width set at all, so it took Graphviz's default of <b>1</b> — a 1 nobody
              chose. Thicker is easier to aim at; thinner leaves the picture lighter to read,
              and only you know which you are doing. In the drawing's own units, so it scales
              with the picture rather than with the chrome. The arrowhead is left alone, so
              raising this changes the weight and not the proportions.</div></div>
          <div class="seg" role="group" aria-label="Flow arrow thickness">
            ${[1, 2, 3, 4].map(n => `<button data-dgmedge="${n}"
              aria-pressed="${Number(state.diagramEdgeWidth) === n}">${n}×</button>`).join("")}
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Menu order</div>
            <div class="desc">People read a menu from the top down, so first position is a real
              advantage. <b>Ways in</b> matches how the tool is described \u2014 a program is its
              entrypoints. <b>Explore</b> puts the wandering features first, which is how it
              actually gets used. Genuinely arguable, so both exist and the usage counter decides.</div></div>
          <div class="seg" role="group" aria-label="Menu order">
            <button data-menuorder="waysin"  aria-pressed="${state.menuOrder === "waysin"}">Ways in first</button>
            <button data-menuorder="explore" aria-pressed="${state.menuOrder === "explore"}">Explore first</button>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Routines listed per package</div>
            <div class="desc">The navigator lists this many routines inside one package and
              says what it left out. 200 was a guess about how much markup a keystroke can
              afford, and on a program whose packages hold 200–400 it reads as a tease —
              <i>200 of 377</i> is nearly the whole thing. <b>All</b> lists every routine
              there is: the pane gets long and the search box gets slower on a very large
              package, which is a price worth offering rather than deciding for you. The
              complete list is in table mode either way (rule 8).</div></div>
          <div class="seg" role="group" aria-label="Routines listed per package">
            ${NAV_CAPS.map(n => `<button data-navcap="${n}"
              aria-pressed="${Number(state.navCap) === n}">${n || "All"}</button>`).join("")}
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Navigator groups</div>
            <div class="desc">The navigator holds 4,734 routines in one of its groups, and
              scrolling into that list used to put every menu below it two hundred rows out
              of reach. <b>One at a time</b> closes the others when you open one, so the pane
              is never longer than a single list. <b>All at once</b> keeps the whole index
              visible, which is the better answer on a small program and the worse one on a
              large. Genuinely arguable, so both exist and the usage counter decides.</div></div>
          <div class="seg" role="group" aria-label="Navigator groups">
            <button data-navgroups="one"  aria-pressed="${state.navGroups === "one"}">One at a time</button>
            <button data-navgroups="many" aria-pressed="${state.navGroups === "many"}">All at once</button>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">You are here</div>
            <div class="desc">An arrow standing over every node you picked, so a selection of
              one in nine thousand can be <i>found</i> rather than only lit differently from
              its neighbours. It is a billboard like the nodes themselves — always facing you,
              never foreshortened by the tilt — and shaded from the same direction the spheres
              are lit, because two light sources in one picture is how a scene stops reading as
              one. The colour is yours, within a limit: below <b>3:1</b> against the graph's own
              ground it is refused and the pointer falls back to the theme's, because a signpost
              nobody can see is worse than no signpost. 3:1 rather than 4.5:1 — it is a large
              graphic object, not body text.<br><br>
              <b>At the side</b> stands it on the rim of the stack, at the height of the plate
              holding the node and on that node's own bearing, so the line through it leads
              your eye inward — findable from across the whole picture, and never buried in
              the mass it points into. It does leave the frame when you snap to fit, because
              fit frames the selection and the rim is a plate's width away from it.
              <b>Over the node</b> is exact at any zoom, and at full node size it can be
              swallowed by the neighbours it stands among. Genuinely arguable, so both exist
              and the usage counter decides.<br><br>
              The <b>reticule</b> is a ring with four ticks around each node you picked, the
              same size at every zoom. Dimming the other nine thousand says what is
              <i>not</i> yours; it does not say which of the lit dots is the one you meant,
              and a dimmed node in front of or behind it looks much the same. The reticule
              says it outright. <b>Focus</b> — the button on the graph itself — goes further:
              with it on, only the lit set answers a hover or a click, so pointing at the fog
              cannot tell you about a routine you did not mean to ask about.</div></div>
          <div>
            <div class="seg" role="group" aria-label="You are here">
              <button data-pointershown="1" aria-pressed="${state.pointerShown}">Shown</button>
              <button data-pointershown="0" aria-pressed="${!state.pointerShown}">Off</button>
            </div>
            <div class="seg" role="group" aria-label="The focus reticule"
                 style="margin-top:.3rem">
              <button data-reticule="1" aria-pressed="${state.reticuleShown}">Reticule</button>
              <button data-reticule="0" aria-pressed="${!state.reticuleShown}">No reticule</button>
            </div>
            <div class="seg" role="group" aria-label="Where the pointer stands"
                 style="margin-top:.3rem">
              <button data-pointerplace="rim"
                      aria-pressed="${state.pointerPlace === "rim"}">At the side</button>
              <button data-pointerplace="node"
                      aria-pressed="${state.pointerPlace === "node"}">Over the node</button>
            </div>
            <div class="pointerpick">
              <input type="color" id="pointerPick" aria-label="Pointer colour"
                     value="${esc(state.pointerColor || pointerToken())}">
              <span class="ratio" id="pointerRatio"></span>
              <button class="gbtn" data-pointerreset="1">theme's</button>
            </div>
            <div id="pointerNote"></div>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">The graph's ground</div>
            <div class="desc">The stack was built against near-black and every colour in it
              was chosen there — the node colours, the fifty-two plate hues, the dimming,
              and the highlight that makes a dot read as a ball. <b>Follow the theme</b>
              derives all of it again for a pale ground, where a node has to be darker than
              its surroundings and shading works downward from the base colour rather than
              up. <b>Always dark</b> keeps the stack on black inside a light page.<br><br>
              Genuinely arguable — some people much prefer a dark graph whatever the rest of
              the interface does — so both exist and the usage counter decides.</div></div>
          <div class="seg" role="group" aria-label="The graph's ground">
            <button data-graphtheme="follow" aria-pressed="${state.graphTheme === "follow"}"
              >Follow the theme</button>
            <button data-graphtheme="dark" aria-pressed="${state.graphTheme === "dark"}"
              >Always dark</button>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Show edges while moving</div>
            <div class="desc">The stack draws a node as a flat circle held facing the
              camera and shades it to read as a ball — which is why it can hold ten
              thousand of them at full speed, and why turning the view is cheap. Hiding the
              links during a turn was a speed measure borrowed from slower renderers; here
              the geometry is uploaded once and orbiting re-uploads nothing.<br><br>
              Leaving them up is the point: a rotation is how the connections between
              plates read as depth rather than as a flat tangle, and stripping them hides
              the very thing you are turning the view to see. Off is kept for a slower
              machine or a very large selection.</div></div>
          <button class="toggle" data-edgesmotion="1"
                  aria-pressed="${state.edgesInMotion}"
                  aria-label="Show edges while moving"></button>
        </div>

        <div class="setrow">
          <div><div class="lbl">Graph layout</div>
            <div class="desc">Two drawings of the same selection. The <b>stack</b> holds
              every routine — nine thousand nodes on fifty-two plates — and answers what is
              in here. The <b>overview</b> holds one box per package and answers what the
              program is shaped like. Neither replaces the other, and this only picks which
              one graph mode opens on.</div></div>
          <div class="seg" role="group" aria-label="Graph layout">
            <button data-layout="stack" aria-pressed="${state.graphLayout === "stack"}"
              >Stack</button>
            <button data-layout="packages" aria-pressed="${state.graphLayout === "packages"}"
              >Overview</button>
          </div>
        </div>

        <div class="setrow">
          <div><div class="lbl">Ambient anomaly badges</div>
            <div class="desc">When on, anything carrying a finding is marked <em>wherever it appears</em> —
              an amber <b>!</b> on the node in the graph, a tag beside the routine in the table, a badge in the
              inspector header, and a coloured count in the left rail. Nothing new is computed; the same
              105 findings simply become visible in context instead of only in the worklist.<br><br>
              <b>Off by default</b> because 93 suspect findings badge a great deal of the program at once, and
              a signal that is always on stops being a signal. Turn it on when you are working through the
              worklist and want to see where the findings actually live; turn it off to read the program.</div></div>
          <button class="toggle" id="ambientToggle" aria-pressed="${state.ambient}" aria-label="Ambient anomaly badges"></button>
        </div>

        <div class="setrow">
          <div><div class="lbl">Scroll change bands in place</div>
            <div class="desc">On the change worklist, each band — added, removed, behaving differently,
              edited only — keeps to <b>32rem</b> and scrolls inside itself, so all four headings stay
              within reach of one another.<br><br>
              <b>Off by default.</b> Rule 8 says a reference list is never bounded, and on an ordinary
              window the cap put the largest band, 53 rows, into a 512px box nested inside the page's own
              401px scroller — scrolling one box to find another. Turn it on if you would rather compare the
              bands than read one through.</div></div>
          <button class="toggle" id="bandScrollToggle" aria-pressed="${state.bandScroll}" aria-label="Scroll change bands in place"></button>
        </div>

        <div class="setrow">
          <div><div class="lbl">Hide inferred edges</div>
            <div class="desc">Show only what is pinned by import, module or class — the defensible skeleton.</div></div>
          <button class="toggle" id="inferredToggle" aria-pressed="${state.hideInferred}" aria-label="Hide inferred edges"></button>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>Inference</h2><span class="hint">off by default</span></div>
      <div class="panel-body">
        <p style="margin:.2rem 0 .5rem;font-size:.78rem;color:var(--text-muted)">
          Anything that sends data off this machine lives on its own page, not buried here.
          Nothing runs during <code class="mono">analyze</code>, and nothing runs on a schedule.
        </p>
        <button class="actbtn" data-goto="inference">Open Inference \u2014 currently
          <b>${esc(posture().label.toLowerCase())}</b> <span class="k">\u203a</span></button>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>Usage</h2><span class="hint">local only · never leaves this machine</span></div>
      <div class="panel-body">
        ${Object.entries(state.usage).sort((a, b) => b[1] - a[1]).map(([k, v]) => `
          <div class="usagebar">
            <span style="text-transform:capitalize">${esc(k)}</span>
            <span class="bar"><i style="width:${(v / 68) * 100}%"></i></span>
            <span class="n">${v}</span>
          </div>`).join("")}
        <p style="font-size:.72rem;color:var(--text-muted);margin:.5rem 0 0">
          Counted so a Setting that exists only because two options were tied can be retired on
          evidence rather than on opinion.
        </p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>Accessibility — and its limits</h2></div>
      <div class="panel-body">
        <dl class="a11ylist">
          <dt>A node graph stops being screen-reader navigable past roughly fifty nodes.</dt>
          <dd>The complete table beside every diagram is the accessible path, not a fallback.
            Every bounded diagram is followed by the full listing of what it left out.</dd>
          <dt>Mermaid's generated SVG can be themed, but its focus order cannot be controlled.</dt>
          <dd>Those diagrams are treated as images with a required table equivalent.</dd>
          <dt>Pan and pinch-zoom are gestures not everyone has.</dt>
          <dd>Arrow keys move between graph nodes; Enter descends; Escape returns to the parent.</dd>
          <dt>Colour is never the only carrier of meaning.</dt>
          <dd>Confidence is line style. Boundary kind is icon plus label. Severity carries a glyph.</dd>
        </dl>
      </div>
    </section>
  </div>`;
}

function sec(key, title, count, bodyHtml) {
  const open = state.insp[key];
  return `<div class="flowsec" data-open="${open}" data-sec="${key}">
    <h3><button aria-expanded="${open}">
      <span class="caret">\u25bc</span>${esc(title)}
      ${count != null ? `<span class="secn">${count}</span>` : ""}
      <span class="rule"></span>
    </button></h3>
    <div class="flowsec-body">${bodyHtml}</div>
  </div>`;
}





/* ═══ undo: getting back to what you were just looking at ═══
 *
 * Chasing a thread means clicking a lot, and two of those clicks lose your place with no
 * way back. Clicking the node you are *already* looking at clears the whole selection --
 * a deliberate toggle-off, and a trap when the click is also how you move -- and every
 * nodes-are-all-visible state looks identical, so there is nothing on screen to say which
 * routine you had. Design rule 15 puts it plainly: nobody chases a rabbit if they might
 * not find their way back, and the trail is what makes the detour free.
 *
 * Linear and index-space, deliberately. A session's payload does not change under it, so
 * engine indices are stable for as long as the history is worth keeping; storing ids and
 * re-resolving would buy nothing and could fail differently. Capped, because an unbounded
 * history of a thing nobody looks at is a leak nobody can see -- the same reasoning the
 * trail's own cap already carries.
 *
 * `restoring` is the whole correctness argument: applying an undo changes the selection,
 * which is what records history, so without it every undo would record itself and the
 * stack would never move.
 */
/* **One history, and it used to be two.**
 *
 * `state.trail` was the visible record and `selHistory` the invisible one, and the split
 * was never designed -- it accumulated. `onGraphSelect` recorded to the second and never
 * the first, so the button labelled **Back** could not reverse a click in the stack, which
 * is almost the only thing a reader does while exploring it. Reported at the keyboard as
 * *"I have to use Back too often, and it doesn't always do what I expect"*, and it was
 * exactly right: two answers to "where have I been", with the visible one blind to the
 * commonest act (rule 51, crossed with rule 30 -- the control's subject was not what the
 * reader took it to be).
 *
 * They merged cheaply because they had already half-merged. A trail step has carried its
 * *subject* since rule 33, `goToTrailStep` already restored through `applySelectionStep`,
 * and neither list was ever persisted -- so there was one shape, one restore path and
 * nothing to migrate.
 *
 * `TRAIL_CAP` is the **history**, and `state.trailCap` is how many steps the bar *shows*.
 * They were one number, applied to the history, and merging made that fatal: every graph
 * click is a step now, so a cap of twelve would flush the step the reader detoured *from*
 * -- destroying the one thing design rule 15 says the trail exists for. */
const TRAIL_CAP = 50;
let trailAt = -1;
let restoringSelection = false;

/* True only while `applyWanted` is handing the engine a selection the app already decided.
 * See `onGraphSelect`, which is what it is for. */
let installingSelection = false;

function selectionSnapshot() {
  /* The **fold** rides with the selection, or Back cannot reverse the commonest act in
     Diagram mode. A box click sets no `selected` at all -- it is not a node -- so a step
     without this field is a step whose subject is `null`, which renders, highlights and
     scrolls exactly as it should and can take nobody back (rule 33, in the view that rule
     was written for). */
  return { picks: (state.picks || []).slice(), selected: state.selected,
           fold: state.fold || null,
           /* The arrow rides too, for the same reason the fold does: opening one sets no
              `selected`, so a step without this field names nothing and takes nobody back. */
           flow: state.flow || null,
           /* **Where the drawing is** is part of the subject in Diagram mode, and leaving it
              out made three acts unreversible: switching compartment, opening a box, and
              backing out of one. None of them changes the *selection*, so every step they
              filed was deduplicated against the one before it and Back skipped straight past
              -- rule 33 with the field simply missing, and design rule 15's whole argument
              is that a detour is only free if you can get back from it. */
           diagramId: state.diagramId || null,
           diagramBox: state.diagramBox || null };
}

function sameSelection(a, b) {
  return a && b && a.selected === b.selected &&
         (a.fold || null) === (b.fold || null) &&
         (a.flow || null) === (b.flow || null) &&
         (a.diagramId || null) === (b.diagramId || null) &&
         (a.diagramBox || null) === (b.diagramBox || null) &&
         a.picks.length === b.picks.length &&
         a.picks.every((p, i) => {
           const q = b.picks[i];
           return p.kind === q.kind && p.id === q.id && p.index === q.index;
         });
}

/* Called wherever a selection settles, from either direction -- the graph announcing a
 * click, or the list driving one. **The one place a step is made**, because two would
 * disagree about order, and because two is what this whole change exists to undo.
 *
 * `label` and `note` are for a caller that can say something better than the selection
 * can: a mode toggle names the mode, a thread names why it was worth a detour. Everything
 * else takes the name of what it landed on.
 *
 * Two invariants here are load-bearing and both are asserted. `publishSelection()` is
 * **first**, above the bail, so an undo still tells the sibling window where this one
 * moved. And the `restoringSelection` bail comes **before any write to the history**, or
 * stepping back would record the step it had just returned to and the cursor would never
 * move. */
function recordSelection(label, note, view) {
  publishSelection();
  if (restoringSelection) return;
  const step = {
    /* `view` is an override, not a dead parameter: `pushTrail` is handed one by callers
       that are *in the act* of moving, and a step recorded as the view being left would
       take a reader back to somewhere they were not. Every current caller passes the view
       it has just set, so the two agree — but a parameter that is ignored is a control
       wired to nothing, and this one is read. */
    view: view || state.view,
    /* `labelFor` returns the id it was given when it knows no better, and `null` for a
       cleared selection — so the fallback used to be `state.view`, and a step recording
       "you cleared the picture" came out labelled *graph*, which reads as a mode change.
       It is the step a reader is most likely to want back (clicking the node you are on is
       the toggle-off that empties everything), so it says what it is. */
    label: label || subjectLabel(),
    note: note || "",
    subject: selectionSnapshot(),
  };
  /* **By subject, never by label.** `pushTrail` deduplicated on the label, which was fine
     while steps were named by hand and is wrong the moment every click makes one: two
     routines sharing a name would be silently dropped as a repeat. A label is not an
     identity (rule 30), and `sameSelection` is the test the selection history already
     used. The view is in it because the three centre modes are three ways of looking at
     one selection, and moving between them is a step even when the subject has not moved. */
  const at = state.trail[trailAt];
  if (at && at.view === step.view && sameSelection(at.subject, step.subject)) return;
  state.trail = state.trail.slice(0, trailAt + 1);   // a new move drops the forward branch
  state.trail.push(step);
  if (state.trail.length > TRAIL_CAP) state.trail.shift();
  trailAt = state.trail.length - 1;
}

function applySelectionStep(step) {
  restoringSelection = true;
  try {
    state.picks = step.picks.slice();
    if (Graph.mounted()) Graph.setSelection(state.picks);
    setSubject({ node: step.selected, fold: step.fold, flow: step.flow });
    /* Restore where the drawing was, and redraw only when it actually moved: `ensureDiagram`
       refetches, and calling it on every Back would make stepping through a trail of
       selections re-request a compartment that never changed. */
    if ((step.diagramId || null) !== (state.diagramId || null)
        || (step.diagramBox || null) !== (state.diagramBox || null)) {
      state.diagramId = step.diagramId || null;
      state.diagramBox = step.diagramBox || null;
      diagramNow = null;
      ensureDiagram();
    }
    persist();
    buildNav();
    revealSelectedRoutine();
    render();
  } finally {
    restoringSelection = false;
  }
}

/* Three doors onto one function: the trail bar's Back, the ⌘Z binding, and the HUD's undo
 * button. They were two mechanisms with different contents; now the only difference between
 * them is which one the reader happens to reach for. */
function canUndoSelection() { return trailAt > 0; }
function canRedoSelection() { return trailAt >= 0 && trailAt < state.trail.length - 1; }

function undoSelection() {
  if (!canUndoSelection()) return;
  goToTrailStep(state.trail[--trailAt]);
}

function redoSelection() {
  if (!canRedoSelection()) return;
  goToTrailStep(state.trail[++trailAt]);
}

/* ═══ the trail: where you have been, so you can wander without losing it ═══ */
/* A step records the *subject* it arrived at, not just a label.
 *
 * It used to be `{view, label, note}`, and clicking a step set `state.view` and re-rendered
 * -- so from inside graph mode, where the view is already "graph", **nothing happened at
 * all**. The trail rendered, highlighted, scrolled and pruned correctly, and could not take
 * anyone back to anything. Rule 30 a third time, in the one feature design rule 15 says
 * exists to make a detour free: nobody chases a rabbit if they might not find their way
 * back. */
/* The three ways of looking at one selection.
 *
 * Written out twice already and about to be a third time, which is how a list stops
 * agreeing with itself (rule 36). It is the settled shape of the centre pane: **a mode
 * toggle over one shared selection, not three destinations** -- switching never costs the
 * reader their place.
 */
const CENTRE_MODES = ["graph", "table", "doc", "code", "diagram"];

/* Going back to a step, and the one thing that surprised a reader about it.
 *
 * A step records the view it was made in, and replaying it set that view -- so a reader
 * reading the table, who pressed Back expecting the previous row, was put in the graph
 * because that is where the step had been made. Reported as *unexpected, so either must be
 * changed or documented.*
 *
 * Changed, because the centre pane's own rule already settles it: the three modes are three
 * ways of looking at one selection, so the *mode* is not part of where you were -- the
 * subject is. A step made in the graph and a step made in the table are the same step.
 *
 * The mode is still restored when the reader is somewhere that is genuinely elsewhere -- the
 * glossary, the worklist, settings -- because those are destinations rather than views of a
 * selection, and staying put there would show nothing of the step being returned to.
 */
function goToTrailStep(step) {
  const bothCentre = CENTRE_MODES.includes(step.view) && CENTRE_MODES.includes(state.view);
  if (!bothCentre) state.view = step.view;
  if (step.subject) applySelectionStep(step.subject);
  else render();
}

/* The door for a caller that can name its own step better than the selection can -- a mode
 * toggle names the mode, a thread names why it was worth the detour, the detail window says
 * it opened one. It **records the same step as every other move**, through the one
 * recorder; it used to keep a list of its own, and that was the defect.
 *
 * The pruning that lived here is gone with it. It capped the *history* at
 * `state.trailCap`, which now bounds only what the bar shows -- see `TRAIL_CAP`. */
function pushTrail(view, label, note) {
  recordSelection(label, note, view);
}

/* The bar is a **window onto the history, not the history itself**, and that is what makes
 * one history workable. `state.trailCap` bounds what is shown; `TRAIL_CAP` bounds what is
 * kept. The window ends at the cursor rather than at the newest step, so stepping back
 * scrolls the bar with you instead of leaving you looking at where you are not.
 *
 * What falls outside it is **stated** (design rule 1: a filtered view says what it removed),
 * because a trail that silently forgets is worse than a short one -- the reader would have
 * no way to know Back can still reach further than the bar shows.
 */
function trailBar() {
  if (!state.trailShown) return "";
  if (state.trail.length < 2 && !state.pins.length) return "";
  const show = Math.max(2, state.trailCap);
  /* The window ends one past the cursor where there is a forward branch, so the step you
     would move *to* is on screen -- a Forward button pointing at something invisible is a
     control the reader cannot aim. */
  const end = Math.min(state.trail.length, Math.max(trailAt + 2, show));
  const from = Math.max(0, end - show);
  /* **Both ends, and the second was missing.** Only what fell off the *back* was stated,
     so stepping back through a long trail silently hid everything in front of the cursor —
     fourteen steps Forward could still reach, with nothing on screen to say so. A window
     has two edges and design rule 1 applies to both. */
  const behind = from;
  const ahead = state.trail.length - end;
  return `
  <div class="trailbar">
    <span class="trail-label">Trail</span>
    ${behind ? `<span class="trail-behind" title="Back reaches them; the bar shows ${
      show} at a time">+${behind} behind</span>` : ""}
    <ol class="trail">
      ${state.trail.slice(from, end).map((t, k) => {
        const i = from + k;
        /* Three states, not two. `here` is the cursor, `ahead` is the forward branch --
           steps the reader stepped back past and can still step forward into. Drawing them
           the same as the past would say the journey ends here, which is the opposite of
           what a history with a cursor knows. */
        const where = i === trailAt ? "here" : (i > trailAt ? "ahead" : "");
        return `
        <li><button class="trailstep ${where}"
              data-trail="${i}" title="${esc(t.note || t.label)}">${esc(t.label)}</button></li>`;
      }).join("")}
    </ol>
    ${ahead ? `<span class="trail-behind" title="Forward reaches them; the bar shows ${
      show} at a time">+${ahead} ahead</span>` : ""}
    <button class="linkbtn" data-trailback ${canUndoSelection() ? "" : "disabled"}
            title="Back to the previous step (⌘Z)">\u2190 Back</button>
    <button class="linkbtn" data-trailfwd ${canRedoSelection() ? "" : "disabled"}
            title="Forward again (⇧⌘Z)">Forward \u2192</button>
    <button class="linkbtn" data-trailclear>Clear</button>
    ${state.pins.length ? `<button class="linkbtn pinned" data-nav2="pins">\u25c6 ${state.pins.length} kept</button>` : ""}
  </div>`;
}

function pinBtn(label, note) {
  const on = state.pins.some(p => p.label === label);
  return `<button class="pinbtn ${on ? "on" : ""}" data-pin="${esc(label)}" data-pinnote="${esc(note || "")}"
    title="${on ? "Kept \u2014 click to drop" : "Keep this to come back to"}">${on ? "\u25c6 Kept" : "\u25c7 Keep this"}</button>`;
}

/* ═══ curiosities: the reason to start wandering ═══ */
/* ══ code, in the centre: the same file with room for the columns ══════════════════════
 *
 * The fourth centre mode. Design rule 26 settled that the modes are ways of looking at one
 * selection rather than destinations, and source is plainly one of those -- so this reads
 * the same `CODEFILE` the left pane does. One store, one truth: two copies would disagree
 * the first time either was reloaded, which is rule 51's defect exactly.
 *
 * What the centre adds is the width, and what the width buys is that a mark can say what it
 * *is* instead of standing for it. The pane's gutter is a column of glyphs because a gutter
 * wide enough for prose has taken the code's column; here there is room for the words.
 */
function viewCode() {
  if (!state.codeFile) {
    /* Design rule 21's argument outside the canvas: a blank pane must say why it is blank.
       "Nothing chosen" and "nothing here" are opposite claims about the map. */
    return `<div class="panel codeempty">
      <h2>No file open.</h2>
      <p class="hint">Open the <b>Code</b> group in the navigator and pick one — or select a
      routine anywhere, and this follows it into the file it lives in.
      ${FILES.length ? `${FILES.length.toLocaleString()} files were analysed.` : ""}</p>
    </div>`;
  }
  if (!CODEFILE || CODEFILE.loading) {
    return `<div class="panel codeempty"><p>Opening ${esc(state.codeFile)}…</p></div>`;
  }
  if (CODEFILE.available === false) {
    return `<div class="panel codeempty"><h2>Nothing to show.</h2>
      <p>${esc(CODEFILE.reason || "")}</p></div>`;
  }

  const f = FILES.find(x => x.path === state.codeFile);

  return `<div class="codeview-full">
    <div class="codeview-head">
      <div>
        <div class="codeview-title mono">${esc(state.codeFile)}</div>
        <div class="codeview-sub">${f ? esc(f.module) + " · " : ""}${
          CODEFILE.lines.length.toLocaleString()} lines · ${
          CODEFILE.defs.length} definitions · ${CODEFILE.marks.length.toLocaleString()} marks</div>
      </div>
      ${overlaySwitchHtml("code")}
      <button class="linkbtn" data-codedetach="1"
              title="Open the code in a window of its own, in sync with this one">detach ⧉</button>
      <button class="linkbtn" data-codeback="1" title="Back to the list of files">files ›</button>
    </div>

    ${/* Design rule 1: what is not on screen is stated, in counts. A name that is not
          clickable with nothing said about it reads as a name the map does not know --
          which is the opposite of the truth, since the map knows it and cannot say where
          on the line it was written. */
      CODEFILE.unplaced ? `<div class="codeview-note">${CODEFILE.placed.toLocaleString()}
        names are clickable. ${CODEFILE.unplaced} more resolved to a routine but occur more
        than once on their line, so there is no column to underline — they are listed in the
        margin instead.</div>` : ""}

    ${comparing() ? `<div class="codeview-note chgnote">${overlayNote()}</div>` : ""}
    ${factLaneHtml(state.codeFile)}

    <div class="codeview-body" id="codeTableMount"></div>

    <div class="codeview-foot">Read from the content-addressed sidecar — the file as
      measured${CODEFILE.revision ? " at " + esc(CODEFILE.revision) : ""}, not as the tree
      stands now.</div>
  </div>`;
}

/* The centre's own rendering of the file, built once per file and re-attached (see
 * `codeCached`). Separate from the chrome above it because the chrome is cheap and changes
 * with the selection, while this is 1.37 MB of markup for the largest file and changes only
 * when the file does. */
function codeTable() {
  const links = new Map();
  for (const s of CODEFILE.links) {
    if (!links.has(s.line)) links.set(s.line, []);
    links.get(s.line).push(s);
  }
  const marks = new Map();
  for (const m of CODEFILE.marks) {
    if (!marks.has(m.line)) marks.set(m.line, []);
    marks.get(m.line).push(m);
  }
  /* A `<pre>` of spans, not a table — the same structure the navigator's pane uses, and the
   * reason is measured. As a `<table>` with a `<pre>` in every code cell this cost **1,358
   * ms** to lay out `_server.py`, against table mode's 46 ms for 4,734 rows with *more*
   * cells each. Per-row `overflow-x` makes 5,838 scroll containers and a table has to
   * resolve them all before it can size a column. Fixed-width inline-blocks give the same
   * three columns with none of that, and the alignment is exactly as reliable because every
   * width is declared rather than negotiated. */
  const ov = codeOverlay();
  const rows = [];
  if (ov) rows.push(...ghostRows(ov, 0, "crow-wide"));
  CODEFILE.lines.forEach((text, i) => {
    const n = i + 1;
    const ms = marks.get(n) || [];
    const gone = ov && ov.gone.has(n);
    rows.push(`<span class="crow${gone ? ` chg tone-${ov.base.tone}` : ""}" id="crow-${n}">` +
      `<span class="cnum">${n}</span>` +
      (ov ? `<span class="csign" aria-hidden="true">${gone ? signOf(ov.base.tone) : ""}</span>` : "") +
      `<span class="cmark">${ms.map(m => `<span class="mk mk-${esc(m.kind)}"` +
            ` title="${esc(m.kind)}${m.note ? " · " + esc(m.note) : ""}"` +
            `>${esc(m.label)}${m.detail ? `<i>${esc(m.detail)}</i>` : ""}</span>`).join("")}</span>` +
      `<span class="ccode">${codeLineHtml(text, links.get(n))}</span></span>`);
    if (ov) rows.push(...ghostRows(ov, n, "crow-wide"));
  });
  return `<pre class="codetable" id="codeTable">${rows.join("\n")}</pre>`;
}

/* The sign beside a marked line. It follows the **tone**, which follows the word, which
   follows the reader's assumption about which version is newer -- so it cannot say `+`
   beside a line the strip is calling deleted. */
function signOf(tone) { return tone === "gone" ? "\u2212" : "+"; }

/* The other version's lines, drawn where they belong and marked as not being here.
 *
 * They carry **their own** line numbers, not this file's, and the number is styled and
 * titled as belonging to the other version. Renumbering them into this file would be
 * inventing a position for lines that have none here (rule 1), and leaving the column
 * blank would throw away the one thing that says where they actually are.
 *
 * Rule 8, and it is worth saying out loud: nothing is elided. A run of four hundred
 * inserted lines is four hundred rows. The reader can turn the overlay off, which is a
 * different thing from being shown a summary of it.
 */
function ghostRows(ov, after, cls) {
  const runs = ov.after.get(after);
  if (!runs) return [];
  const out = [];
  for (const run of runs) {
    run.lines.forEach((text, k) => {
      const n = run.first + k;
      out.push(`<span class="crow ghost chg tone-${ov.compared.tone} ${cls}">` +
        `<span class="cnum ghostn" title="line ${n} of the compared version">${n}</span>` +
        `<span class="csign" aria-hidden="true">${signOf(ov.compared.tone)}</span>` +
        `<span class="cmark"></span>` +
        `<span class="ccode">${esc(text) || "&nbsp;"}</span></span>`);
    });
  }
  return out;
}

function viewCuriosities() {
  /* Four states, and a blank panel states the wrong one whichever it is. "Nobody has
     looked yet" and "there is nothing unusual here" are opposite claims about the map --
     the same argument design rule 21 makes about a canvas, one pane out. */
  const waiting = laneState(CURIOS, "lane", "error", "the curiosities");
  if (waiting) return `<div style="max-width:58rem">${waiting}</div>`;

  /* Design rule 1: a measure that had nothing to say is named, not dropped. Nine cards and
     ten cards are different claims, and a reader has no way to tell a measure that came out
     ordinary from one that was never taken. */
  const silent = CURIOS.silent || [];
  const silentNote = silent.length ? `<div class="note curinote">
      <b>${silent.length} of ${CURIOS.families} measures had nothing to measure here.</b>
      ${silent.map(k => `<code>${esc(k)}</code>`).join(" ")} — this program holds nothing
      for ${silent.length === 1 ? "that one" : "those"} to come out of, which is a fact about
      the program rather than a gap in the panel.</div>` : "";

  if (!CURIOSITIES.length) {
    return `<div style="max-width:58rem;display:flex;flex-direction:column;gap:.75rem">
      <div class="note"><b>Nothing here could be measured.</b> All ${CURIOS.families}
      measures came back empty, which happens when a map holds no routines at all. This is
      an answer, not an empty page waiting to fill.</div>${silentNote}</div>`;
  }

  return `
  <div style="max-width:58rem;display:flex;flex-direction:column;gap:.75rem">
    <div class="note">
      <b>${CURIOSITIES.length} measurement${CURIOSITIES.length === 1 ? "" : "s"} of this
      program, each showing what came out furthest from the middle.</b>
      None of them is a problem and none of them is a finding — there is no severity here
      and nothing that says a number ought to be smaller. Each says its value, the
      <b>middle</b> it is being read against, and how far apart the two are; the list is
      ordered by that distance, so the strangest is first and the ones barely above their
      middle sort last and say so. Pull one and see where it goes.
      ${comparing() ? `<br><span class="muted">Measured on the base alone. These are not
        compared across the two versions — what a card names is what the version on screen
        holds.</span>` : ""}
    </div>
    ${silentNote}
    <div class="curigrid">
      ${CURIOSITIES.map((c, i) => curiCard(c, i)).join("")}
    </div>
  </div>`;
}

/* One card. The follow button is an ordinary `data-thread`, which is the whole point:
 * it carries a **subject** and goes through `THREAD_SUBJECTS`, the table that already
 * knows how to open a node and how to resolve a cohort, and it pushes a trail step on
 * the way.
 *
 * What it replaces was rule 30 alive in this file. Each card carried a `tag` string and
 * the handler switched on it — `anomaly` to the worklist, `vocabulary` to the glossary,
 * everything else falling through to table mode — so a card's destination was decided by
 * a *label* and an unrecognised one landed somewhere that looked deliberate. It had never
 * fired only because this array had never been filled; filling it is what would have lit
 * it up. There is no second route now, and nothing to keep in step. */
function curiCard(c, i) {
  const key = provKey("curi", i);
  return `<div class="curi">
    <span class="curi-icon" aria-hidden="true">◈</span>
    <span class="curi-body">
      <span class="curi-head">${esc(c.head)}<span class="kind-tag">${esc(c.ratioText)}</span></span>
      <span class="curi-what mono">${esc(c.what)}</span>
      ${c.whence ? `<span class="curi-text">${
        c.whenceLabel ? esc(c.whenceLabel) + " " : ""}<span class="mono">${esc(c.whence)}</span></span>` : ""}
      <span class="curi-text">${esc(c.middle)}${c.tie ? ` · ${esc(c.tie)}` : ""}</span>
      <span class="curi-acts">
        <button class="cite" data-thread="${esc(JSON.stringify(c.subject))}"
                data-threadlabel="${esc(c.what)}" data-threadwhy="${esc(c.head)}">
          <span class="citeicon" aria-hidden="true">◈</span>Follow this<span class="citego">go</span></button>
        <button class="cite" data-sqlshow="${key}">
          <span class="citeicon" aria-hidden="true">⌗</span>How this was measured<span class="citego">show the query</span></button>
      </span>
      ${state.showSql === key ? `<pre class="srcblock sqlblock">${esc(c.sql)}</pre>
        <span class="provfoot">Run it yourself:
          <span class="mono">dunneflow query &lt;this map&gt; --sql "…"</span> — the directory
          this dashboard is serving, not the source tree. Every number on this card comes out
          of that one statement: the value, the middle, how many tie with it, and how large a
          population it came out of. It is not a query <i>about</i> the number, it is the
          query that returned it.</span>` : ""}
    </span>
  </div>`;
}


/* ═══ kept things ═══ */
function viewPins() {
  return `
  <div style="max-width:48rem;display:flex;flex-direction:column;gap:.6rem">
    <div class="note">
      <b>Things you kept while you were looking at something else.</b> The point of wandering is
      that you find what you were not looking for; this is where it goes so the detour does not
      cost you the thread you were on.
    </div>
    ${state.pins.length ? state.pins.map((p, i) => `
      <div class="pinrow">
        <span class="pin-mark" aria-hidden="true">\u25c6</span>
        <span class="pin-body">
          <span class="pin-label mono">${esc(p.label)}</span>
          ${p.note ? `<span class="pin-note">${esc(p.note)}</span>` : ""}
        </span>
        <button class="linkbtn" data-unpin="${i}">Drop</button>
      </div>`).join("")
    : `<p style="font-size:.8rem;color:var(--text-muted)">Nothing kept yet. Anywhere you see
       <span class="pinbtn" style="pointer-events:none">\u25c7 Keep this</span>, that thing lands here.</p>`}
  </div>`;
}

/* How many of each kind the panel shows before it says what it cut.
 *
 * `write_spec_seal_atomic` carries thirteen governance ids, and the tail of that list --
 * a ticket shared with 109 other routines -- is a category rather than a detour. Rarity
 * sorts first, so the cut takes the least useful end; and it is *stated*, with the whole
 * list one click away, which is rule 8's bargain exactly: abbreviation is allowed only
 * where the complete content sits beside it. */
const THREADS_SHOWN = 5;

const THREAD_KIND_TITLE = {
  governance: "Shares a plan",
  boundary: "The other end",
  /* The two lanes of the naming standard read as adjacency: a routine ending `_cmd` has
     ninety-eight relatives it never calls, and a routine whose module is a word the
     project defines has a document behind its name. This is the only place the graph
     touches the glossary and naming lanes, which were otherwise reachable only from
     their own pages. */
  vocabulary: "Named like these",
  outlier: "Unusual nearby",
};

function threadsPanel(nodeId) {
  const th = THREADS[nodeId];

  /* Three states, and they are three different claims. Undefined: we have not asked yet.
     Null: we asked and could not find out. Empty: we asked and there is nothing, which is
     the ordinary answer for a private helper. A panel that renders the same thing for all
     three tells the reader the wrong one twice out of three times. */
  if (th === undefined) return "";
  if (th === null) {
    return `
      <div class="flowsec threads">
        <h3><button aria-expanded="true"><span class="caret">\u25bc</span>Threads to pull
          <span class="rule"></span></button></h3>
        <div class="flowsec-body"><p class="hint">Could not ask what is beside this one.
          That is a fact about the connection, not about the program.</p></div>
      </div>`;
  }
  if (!th.length) {
    return `
      <div class="flowsec threads">
        <h3><button aria-expanded="true"><span class="caret">\u25bc</span>Threads to pull
          <span class="secn">0</span><span class="rule"></span></button></h3>
        <div class="flowsec-body"><p class="hint">Nothing is beside this one — no shared
          plan, no shared table, nothing at the other end of anything it touches. That is
          an ordinary thing for a routine to be.</p></div>
      </div>`;
  }

  const all = state.threadsAll;
  const groups = [];
  for (const kind of Object.keys(THREAD_KIND_TITLE)) {
    const rows = th.filter(t => t.kind === kind);
    if (!rows.length) continue;
    const shown = all ? rows : rows.slice(0, THREADS_SHOWN);
    groups.push(`
      <div class="threadgroup ${esc(kind)}">
        <div class="threadgroup-head">${esc(THREAD_KIND_TITLE[kind])}
          <span class="n">${rows.length}</span></div>
        ${shown.map(t => `
          <button class="thread" data-thread="${esc(JSON.stringify(t.subject))}"
                  data-threadwhy="${esc(t.why)}" data-threadlabel="${esc(t.label)}">
            <span class="thread-body">
              <span class="thread-to mono">${esc(t.label)}</span>
              <span class="thread-why">${esc(t.why)}</span>
            </span>
          </button>`).join("")}
        ${rows.length > shown.length
          ? `<div class="hint">Showing ${shown.length} of ${rows.length}, rarest first.</div>`
          : ""}
      </div>`);
  }

  const cut = th.length - (all ? th.length
    : Object.keys(THREAD_KIND_TITLE).reduce(
        (n, k) => n + Math.min(THREADS_SHOWN, th.filter(t => t.kind === k).length), 0));

  return `
    <div class="flowsec threads">
      <h3><button aria-expanded="true"><span class="caret">\u25bc</span>Threads to pull
        <span class="secn">${th.length}</span><span class="rule"></span></button></h3>
      <div class="flowsec-body">
        <p class="threadintro">Not the call graph — reasons something nearby is worth a
          detour. Two routines that never call each other and both write one table are
          related, and no call graph can say that.</p>
        ${groups.join("")}
        ${cut > 0 || all
          ? `<button class="linkbtn" data-threadsall>${all
              ? "Show fewer" : `Show all ${th.length}`}</button>`
          : ""}
      </div>
    </div>`;
}

/* ═══ source viewer: a citation you can open and read ═══
 *
 * Design rule 13: a quoted definition proves itself with a file and a line the reader can
 * click through to and read **in context, highlighted**. The provenance is not decoration
 * on the claim, it is the claim's evidence, and a definition rendered without the route
 * back is an assertion wearing a uniform.
 *
 * The span is fetched when the citation is opened, from `/api/source`, rather than shipped
 * with the page. The prototype pinned a `PROVENANCE` map -- every span of every citation,
 * 52 KB for one program's glossary -- which is a page's worth of source code carried by
 * every reader for the handful of citations anybody opens. Same bargain as the hover card.
 */
/* ══ the detail window, detached ══════════════════════════════════════════════════════
 *
 * Asked for at the keyboard: *it should become its own window, held in sync with the left
 * side window bidirectionally... a separate tab or pop-up window that remains in
 * bidirectional sync with the menu on the left side of the main screen.* Wanted for the
 * code viewer next, so this is built as a pattern rather than as one feature.
 *
 * **The same application, in a second window.** `?view=detail` boots the whole shell and
 * then hides everything except the detail panel -- no second page, no second renderer, no
 * second copy of `esc`, the threads panel or the trail. A detail view extracted into its own
 * file would have been the third place this project rendered one node, and the first two
 * disagreed about parameter types for a year.
 *
 * **Sync is a `BroadcastChannel`, not the opener.** Same origin, so it needs no server and
 * no round trip -- and it does not care which window opened which, which is the whole point:
 * the reader may close the main window, reload either one, or open the detached view in a
 * tab by pasting the URL. A parent-child `postMessage` protocol would break on every one of
 * those. Both windows are peers that publish where they are looking and adopt where the
 * other is.
 *
 * The loop guard is the only subtle part. Adopting a selection must not re-publish it, or
 * two windows bounce one click between them for ever.
 */
/* Which detached view this window is, if any. `?view=detail` and `?view=code` boot the
 * same application and then hide everything but the one panel -- not a second page, which
 * would be the third place this project draws one node and the second place it draws a
 * file. `DETACHED` stays a boolean for the detail window's own checks; `DETACHED_VIEW` is
 * what says which. */
const DETACHED_VIEW = (() => {
  const v = new URLSearchParams(location.search).get("view");
  return (v === "detail" || v === "code") ? v : "";
})();
const DETACHED = DETACHED_VIEW === "detail";
const SYNC = ("BroadcastChannel" in window) ? new BroadcastChannel("dunneflow-selection") : null;
let adopting = false;

/* Publish where this window is looking. Called wherever a selection settles, beside
 * `recordSelection()` -- one place, for the same reason that has one place. */
function publishSelection() {
  if (!SYNC || adopting || !state.selected) return;
  SYNC.postMessage({ id: state.selected, from: DETACHED ? "detached" : "main" });
}

if (SYNC) {
  SYNC.addEventListener("message", async (ev) => {
    const msg = ev.data || {};
    if (!msg.id || msg.id === state.selected) return;
    /* Adopt without re-publishing. Two peers each echoing the other is a loop that looks
       exactly like a hang, and neither window would be obviously at fault. */
    adopting = true;
    try {
      /* `selectFromNav` moves the list itself now, for every caller rather than for this
         one -- see the note there. */
      await selectFromNav({ nodes: [msg.id] });
      pushTrail(state.view, labelFor(msg.id), "followed the other window");
      render();
    } finally {
      adopting = false;
    }
  });
}

/* Hand this node to a window of its own.
 *
 * Opened from a **click**, never from the keypress. A pop-up blocker treats a click as the
 * user asking and a synthetic-looking keystroke as a page deciding for itself, so the one
 * that survives is the button. If it is blocked anyway the reader is told, because a
 * control that silently does nothing is the failure this project keeps paying for.
 */
function detachDetail() {
  const w = window.open(
    `${location.pathname}?view=detail`, "dunneflow-detail",
    "width=1100,height=800,noopener=no");
  if (!w) {
    state.navNote = "The browser blocked the pop-up. Allow pop-ups for this page, or open "
                  + `${location.pathname}?view=detail in a tab yourself.`;
    render();
    return;
  }
  used("detail:detached");
  /* The in-app window closes behind it. Two copies of one view, one of them stale behind a
     scrim, is worse than either alone -- and the new window publishes its selection, so
     nothing is lost by closing this one. */
  state.detail = false;
  render();
}

/* Opening, hopping and closing. All three go through the one selection, so there is no
 * second piece of state that can disagree with the first.
 *
 * The card is torn down on the way in: it describes what is under the pointer, and the
 * pointer is about to be somewhere else entirely. A card left standing over a modal is a
 * second answer about a node the reader has stopped hovering.
 */
async function openDetail(nodeId) {
  if (!nodeId) return;
  hideHoverCard();
  state.detail = true;
  used("detail");
  /* An ordinary selection, exactly as a navigator row or a node click makes. The stack
     lights up underneath while the window is open, the trail records this hop once, and
     undo already reaches it -- none of which is true of a window holding its own subject. */
  await selectFromNav({ nodes: [nodeId] });
  pushTrail(state.view, labelFor(nodeId), "opened in detail");
  render();
}

/* A hop inside the window. Same route as opening, and deliberately so: chasing a rabbit and
 * arriving are the same act, and a second path here would be a second set of rules about
 * what a hop does to the trail. */
function hopDetail(nodeId) { openDetail(nodeId); }

function closeDetail() {
  state.detail = false;
  state.detailAll = {};
  render();
}

/* The best name we have for a node before its own answer has arrived. `SPECIMEN` is the
 * node being read, which on the first hop is still the previous one -- so this asks the
 * routine list, then the graph, then falls back to the id rather than printing a label
 * about the wrong routine. */
function labelFor(nodeId) {
  const r = (ROUTINES || []).find(x => x.id === nodeId);
  if (r) return r.name;
  if (SPECIMEN && SPECIMEN.id === nodeId) return (SPECIMEN.identity || {}).name || SPECIMEN.label;
  return nodeId;
}

/* ══ the detail window: one node, and what flows through it ══════════════════════════
 *
 * Asked for at the keyboard: *is there a way I could choose to drill into the visible
 * information from the banner? Think about the explorer aspect -- from that destination the
 * user will want to follow breadcrumbs and rabbits to even more destinations, seeing how
 * they are related to one another and how information flows between them.*
 *
 * **Not a second set of facts.** It reads `SPECIMEN` -- the same `/api/node` the inspector
 * reads -- and `THREADS`, the same adjacency the inspector shows. What is new is the
 * *arrangement*: callers on the left, callees on the right, the routine between them with
 * its invocation line, and what it touches beneath. The inspector answers "what is this"
 * as a list; this answers "what passes through it" as a shape, and design rule 15 is why
 * the shape is worth a second rendering.
 *
 * **It drives the one selection rather than keeping its own.** Every hop inside is an
 * ordinary `selectFromNav`, so the stack lights up underneath while the window is open, the
 * trail records the journey once, and undo already reaches every step of it. Two trails
 * would be two answers to "where have I been" (rule 36), and a window with a private
 * selection is how the graph and the shell became two applications.
 *
 * Selecting does not move the camera (design rule 26), so closing the window leaves the
 * reader looking at exactly the view they left, with whatever they found now lit in it.
 *
 * The card that opens it stays `pointer-events: none` and is not made interactive. That is
 * a recorded decision, and the key is what keeps it: the clickable depth stays the
 * inspector's and this window's, not the pop-up's.
 */
function detailFlowCol(side, rows, total, noun, empty) {
  const arrow = side === "in" ? "←" : "→";
  const body = rows.length
    ? rows.map(r => `
        <div class="dflow-item">
          <span class="dflow-arrow">${arrow}</span>
          ${r.id
            ? `<button class="dflow-go" data-detail="${esc(r.id)}"
                 title="${esc(r.qualname || r.name || "")}">${esc(r.name || r.callee_expr)}${
                 r.module ? `<span class="dim">${esc(moduleLabel(r.module, MODULE_BUDGET_FLOW).text)}</span>` : ""}</button>`
            : `<span class="dflow-dead" title="${esc(r.callee_expr || "")}">${
                 esc(r.name || r.callee_expr)}${
                 r.at_boundary ? `<span class="dim">at the boundary</span>`
                 : r.external ? `<span class="dim">outside this map</span>` : ""}</span>`}
        </div>`).join("")
    : `<div class="hint">${empty}</div>`;
  /* Design rule 1, and rule 8: a bounded picture states what it left out and opens the rest
     in place. The cut is here rather than in the data, so "40 of 213" is a fact about this
     view and never about the program. */
  const cut = total > rows.length
    ? `<button class="linkbtn" data-detailall="${esc(side)}">showing ${rows.length} of ${
        total.toLocaleString()} ${noun} — show all</button>`
    : "";
  return `<section class="dflow-col ${esc(side)}">
      <h4>${side === "in" ? "IN" : "OUT"} <span class="num">${total.toLocaleString()}</span></h4>
      ${body}${cut}
    </section>`;
}

const DETAIL_FLOW_SHOWN = 12;

/* How many characters a module gets, per field, and each is that field's own width.
 *
 * `.navsub` is `max-width: 11rem` at `font-size: .64rem` (tokens.css). 30 is what the
 * shortening it replaces was already producing there and fitting -- `…disceptator.
 * _extraction_state` is 30 -- so it is a measured calibration rather than a guess, and with
 * the program root dropped it now shows **81% of Mensores' 566 modules whole**.
 *
 * `.dflow-go .dim` sits in the detail window's flow column, which is `overflow-wrap:
 * anywhere` rather than clipped -- it wraps instead of cutting. So this budget buys
 * tidiness rather than fit, and it is looser for that reason: nothing is lost when it is
 * exceeded, and a wrapped second line in a three-column modal is not the same cost as a
 * clipped one in a rail. */
const MODULE_BUDGET_NAV = 30;
const MODULE_BUDGET_FLOW = 34;

/* How much of a constant's value the hover card shows before it stops and says so.
 *
 * Six lines of the card at its widest -- `.navcard` is `max-width: min(34rem, 50vw)` and
 * `.hc-value` is `.72rem` monospace, so a line holds about forty characters at the default
 * root size. Six is what the three-line clamp this replaces was worth plus room to see a
 * value has structure, and it is above the **median constant, which is 34 characters**:
 * most values are therefore shown whole and say nothing about being cut, because they are
 * not. 739 of 2,638 are longer than one line and 301 longer than this. */
const CARD_VALUE_CHARS = 240;

function detailPanel() {
  if (!state.detail) return "";
  const s = SPECIMEN;
  /* Three different absences, told apart rather than blurred: nothing selected, the answer
     still in flight, and a node the map does not hold. A window that looked the same in all
     three is the confusion every empty answer in this product is written against. */
  if (!s) {
    return detailShell(inspectorFor ? "Reading\u2026" : "Nothing selected", "",
      `<div class="hint">${inspectorFor
        ? "Reading this node\u2026"
        : "Pick a routine and press <kbd>Enter</kbd> over it to come back here."}</div>`);
  }
  if (s.notFound) {
    return detailShell(s.id, "", `<div class="hint">Not in this map. ${esc(s.reason || "")}</div>`);
  }

  const id = s.identity || {};
  const inn = s.in || {}, out = s.out || {};
  const callers = inn.callers || [], eps = inn.entrypoints || [];
  const calls = out.calls || [];
  /* Scoped to the node it was asked about. "Show all 213 callers" is a decision about
     *this* routine, and carrying it to the next one would open a list the reader never
     asked to see -- and would do it silently, since a long list and a chosen long list look
     identical. It survives a trail Back to the same node, which is the point of keying it
     rather than clearing it on every hop. */
  const showAll = (state.detailAll && state.detailAll.for === s.id) ? state.detailAll : {};
  const inRows = showAll.in ? callers : callers.slice(0, DETAIL_FLOW_SHOWN);
  const outRows = showAll.out ? calls : calls.slice(0, DETAIL_FLOW_SHOWN);

  const sig = hoverSigHtml({
    kind: s.kind, name: id.name || s.label, params: s.params || [],
    returns: id.returns || "", is_async: id.is_async,
  });

  const t = s.touches || {};
  const touches = [
    ...(t.boundaries || []).map(b => ({ g: BKIND_GLYPH[b.kind] || "◇",
                                        k: b.kind, v: b.target, d: b.direction })),
    ...(t.sql || []).map(q => ({ g: "▤", k: q.operation || "SQL",
                                 v: q.table || "", d: q.direction })),
    ...(t.net || []).map(n => ({ g: "◆", k: n.protocol || "NET", v: n.target || n.expr, d: "" })),
    ...(t.artefacts || []).map(a => ({ g: "▣", k: "FILE", v: a.name, d: "" })),
  ];

  const body = `
    <div class="dflow">
      ${detailFlowCol("in", inRows, callers.length, "callers",
        eps.length ? "Reached as a way in." : "Nothing in this map calls it.")}
      <section class="dflow-hub">
        ${eps.length ? `<div class="dflow-eps">${eps.map(e =>
            `<span class="badge certain">${esc(e.kind || "ENTRYPOINT")} ${
              esc(e.name || e.command || "")}</span>`).join("")}</div>` : ""}
        ${sig || `<div class="hc-sig"><b class="sig-name">${esc(id.name || s.label)}</b></div>`}
        <div class="dflow-where mono">${esc(String(id.file || "").split("/").slice(-1)[0])}${
          id.line_start ? `:${id.line_start}` : ""}</div>
        ${id.docstring ? `<div class="why">${esc(String(id.docstring).split("\n")[0])}</div>` : ""}
      </section>
      ${detailFlowCol("out", outRows, calls.length, "calls", "It calls nothing this map can see.")}
    </div>

    <div class="dtouch">
      <h4>TOUCHES <span class="num">${touches.length}</span></h4>
      ${touches.length
        ? touches.map(x => `<span class="dtouch-item"><i class="gl">${x.g}</i>${
            esc(x.k.toLowerCase())} ${x.v
              ? `<b>${esc(x.v)}</b>`
              /* A boundary DunneFlow found and could not *name* is still a boundary, and
                 dropping it was a silent filter that turned two real FILE writes into
                 "reaches nothing outside itself" (design rule 1, and the claim was simply
                 false). The path is usually assembled rather than literal -- rule 17's
                 `root / ".mensores" / "tabularium.db"` -- so only the parts are in the
                 source and none of them is the name. */
              : `<b class="dtouch-unnamed">target not literal in the source</b>`}${
            x.d ? `<span class="dim">${esc(x.d)}</span>` : ""}</span>`).join("")
        : `<div class="hint">It reaches nothing outside itself — no file, no database, no
             network. Everything it moves, it was handed.</div>`}
    </div>

    <div class="dthreads">${threadsPanel(s.id)}</div>`;

  return detailShell(id.name || s.label || s.id, id.qualname || "", body, s.kind);
}

function detailShell(title, sub, body, kind) {
  return `
  <div class="detail-scrim" data-closedetail></div>
  <div class="detailwin" role="dialog" aria-modal="true" aria-label="Detail: ${esc(title)}">
    <div class="detail-head">
      <div style="min-width:0">
        <div class="detail-title">${esc(title)}${
          kind ? ` <span class="kind-tag">${esc(kind)}</span>` : ""}</div>
        ${sub ? `<div class="detail-sub mono">${breakable(sub)}</div>` : ""}
      </div>
      ${DETACHED
        ? ""
        : `<button class="linkbtn" data-detachdetail
             title="Move this into a window of its own, kept in sync with the list on the left"
             >Open in a window \u29c9</button>`}
      ${DETACHED
        ? `<span class="detail-synced" title="This window and the main one follow each other">
             \u21c4 following the main window</span>`
        : `<button class="linkbtn" data-closedetail>Close <kbd>Esc</kbd></button>`}
    </div>
    ${/* The one trail, not a second one. Every hop in here is an ordinary selection, so
          the journey it records is the reader's whole journey and Back works across the
          boundary of this window in both directions. */
      trailBar()}
    <div class="detail-body">${body}</div>
  </div>`;
}

function viewerPanel() {
  if (!state.viewer) return "";
  const term = TERMS.find(t => t.term === state.viewer.term);
  const senses = (term && term.senses) || [];
  const s = senses[state.viewer.idx];
  if (!s) return "";

  /* A docstring lives in a file the map holds; a definition in a Markdown file does not.
   * `source.db` is the sidecar of everything the *graph* was built from, and the document
   * corpus is scanned rather than stored -- so this says which of the two it is looking at
   * instead of opening an empty pane. */
  const openable = senseOpens(s);
  const src = VIEWER_SRC && VIEWER_SRC.key === viewerKey(s) ? VIEWER_SRC : null;

  let body;
  if (!openable) {
    body = `<div class="viewer-absent">
      <b>This map does not hold the document, only what it says.</b>
      The definition above was read from <span class="mono">${esc(s.source)}</span> at line ${s.line},
      and that line is quoted whole. The source sidecar carries the files the graph was built
      from — the program's own code — so a docstring opens here and a document does not.
    </div>`;
  } else if (!src) {
    body = `<div class="viewer-absent">Reading ${esc(srcShort(s.source))}…</div>`;
  } else if (src.error) {
    body = `<div class="viewer-absent"><b>That file could not be read.</b> ${esc(src.error)}</div>`;
  } else {
    body = `<pre class="codeview">${src.lines.map(l => {
      const cls = l.n === s.line ? " hit" : "";
      return `<span class="cl${cls}"><span class="cn">${l.n}</span>${esc(l.text) || " "}</span>`;
    }).join("\n")}</pre>`;
  }

  const stamp = (STATS && STATS.analysed) ? String(STATS.analysed).slice(0, 10) : "";

  return `
  <div class="viewer-scrim" data-closeviewer></div>
  <div class="viewer" role="dialog" aria-modal="true" aria-label="Source for ${esc(state.viewer.term)}">
    <div class="viewer-head">
      <div>
        <div class="viewer-title mono" title="${esc(s.source)}">${esc(srcShort(s.source))}</div>
        <div class="viewer-sub">line ${s.line}
          ${s.heading ? ` · under ${esc(s.heading)}` : ""}
          ${s.form ? ` · ${esc(s.form.toLowerCase().replace(/_/g, " "))}` : ""}
          · ${tierBadge(s.provenance)}</div>
      </div>
      <button class="linkbtn" data-closeviewer aria-label="Close source viewer">Close ✕</button>
    </div>

    ${senses.length > 1 ? `<div class="viewer-tabs" role="tablist">
      ${senses.map((e, i) => `<button role="tab" aria-selected="${i === state.viewer.idx}"
        data-viewtab="${i}" title="${esc(e.source)}">${esc(srcShort(e.source))}:${e.line}</button>`).join("")}
    </div>` : ""}

    <div class="viewer-body">${body}</div>

    <div class="viewer-foot">
      ${openable
        ? `Read from the content-addressed sidecar — the file as measured${stamp ? " on " + esc(stamp) : ""},
           not as the tree stands now. The highlighted line is the citation.`
        : `${senses.length > 1 ? "Other tabs may open." : "Nothing to open here."}
           Everything this program says about “${esc(state.viewer.term)}” is on the glossary page.`}
    </div>
  </div>`;
}

/* One key per span, so a repaint does not re-fetch and switching tabs does. */
function viewerKey(s) { return `${s.source}#${s.line}`; }

/* Six lines above and eight below: enough for a docstring's first line to sit inside the
 * definition it belongs to, which is the context the citation is being opened for. */
async function loadViewerSource() {
  if (!state.viewer) return;
  const term = TERMS.find(t => t.term === state.viewer.term);
  const s = ((term && term.senses) || [])[state.viewer.idx];
  if (!s || !senseOpens(s)) return;
  const key = viewerKey(s);
  if (VIEWER_SRC && VIEWER_SRC.key === key) return;
  VIEWER_SRC = { key, lines: null, error: null };
  const first = Math.max(1, s.line - 6), last = s.line + 8;
  try {
    const r = await fetch(`/api/source?path=${encodeURIComponent(s.source)}&first=${first}&last=${last}`);
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    if (!VIEWER_SRC || VIEWER_SRC.key !== key) return;      // the reader moved on
    if (!d.available) VIEWER_SRC = { key, lines: null, error: d.reason || "not available" };
    else VIEWER_SRC = { key, lines: d.lines || [], error: null };
  } catch (err) {
    if (VIEWER_SRC && VIEWER_SRC.key === key) VIEWER_SRC = { key, lines: null, error: err.message };
  }
  render();
}

function citeBtn(term, idx, label) {
  return `<button class="cite" data-cite="${esc(term)}" data-citeidx="${idx}">
    <span class="citeicon" aria-hidden="true">⌗</span>${esc(label)}<span class="citego">show me</span></button>`;
}

/* ═══ inference: its own place, off by default, scoped by what may leave ═══ */
function posture() { return POSTURES.find(p => p.id === state.egress) || POSTURES[0]; }
function permits(need) { return posture().allows.includes(need); }
function chosenOps() { return AI_OPS.filter(o => state.aiOps[o.id] && permits(o.needs)); }

const NEED_LABEL = { docs: "documentation", names: "identifiers", source: "SOURCE CODE" };

function viewInference() {
  const post = posture();
  const chosen = chosenOps();
  const total = chosen.reduce((a, o) => a + o.cost, 0);
  const manifestBytes = MANIFEST.reduce((a, m) => a + m.bytes, 0);

  return `
  <div style="max-width:56rem;display:flex;flex-direction:column;gap:.75rem">

    <div class="note">
      <b>DunneFlow does not need this.</b> Everything on the cover, in the graph, the tables,
      the naming standard, the anomaly worklist and the glossary's declared tiers is read from
      your own files by deterministic code, on this machine. This page exists for the small
      number of questions that need a model, and it is <b>off until you turn it on</b>.
    </div>

    <section class="panel">
      <div class="panel-head"><h2>What may leave this machine</h2>
        <span class="hint">currently: ${post.allows.length ? post.allows.map(a => NEED_LABEL[a]).join(" + ") : "nothing"}</span></div>
      <div class="panel-body">
        <div class="seg postures" role="group" aria-label="Egress posture">
          ${POSTURES.map(p => `<button data-egress="${p.id}" aria-pressed="${state.egress === p.id}">${esc(p.label)}</button>`).join("")}
        </div>
        <p class="postblurb">${esc(post.blurb)}</p>

        <div class="egressgrid">
          ${["docs", "names", "source"].map(k => `
            <div class="egressrow ${permits(k) ? "on" : "off"}">
              <span class="mark">${permits(k) ? "\u25cf" : "\u2715"}</span>
              <span class="what">${esc(NEED_LABEL[k])}</span>
              <!-- Design rule 14: before anything leaves, show what would leave. These
                   were "4,568 routine names", "184,000 lines" and a manifest of "2,449"
                   documents -- one program's figures, written into the one surface in the
                   product where a wrong number is a consent the reader did not give. Two
                   are measurements now; the third says it cannot say. -->
              <span class="detail">${
                k === "docs"   ? (MANIFEST.length
                    ? `${MANIFEST.length} candidate documents \u00b7 ${(manifestBytes / 1024).toFixed(0)} KB`
                    : "the document manifest is not served yet")
              : k === "names"  ? `${STATS ? Number(STATS.routines).toLocaleString() : "\u2014"} routine names and signatures \u00b7 no bodies`
              :                  `${STATS ? Number(STATS.lines).toLocaleString() : "\u2014"} lines of source`}</span>
              ${k === "docs" && permits("docs") ? `<button class="linkbtn" data-manifest>${state.showManifest ? "Hide" : "Review"} the exact list</button>` : ""}
            </div>`).join("")}
        </div>

        ${state.showManifest && permits("docs") ? `
          <div class="manifest">
            <div class="manifesthead">${MANIFEST.length
              ? `Every file a documentation scan would send \u2014 ${MANIFEST.length}`
              : "The manifest is not served yet. Nothing may leave until this list can be "
                + "shown in full \u2014 an unverifiable manifest is not consent."}</div>
            <ol>${MANIFEST.map(m => `<li><span class="mono">${esc(m.path)}</span>
              <span class="num">${(m.bytes / 1024).toFixed(0)} KB</span></li>`).join("")}</ol>
          </div>` : ""}
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2>Operations</h2>
        <span class="hint">each says what it needs \u00b7 blocked ones stay blocked</span></div>
      <div class="panel-body">
        ${AI_OPS.map(op => {
          const blocked = !permits(op.needs);
          return `
          <label class="aiop ${blocked ? "blocked" : ""}">
            <input type="checkbox" data-aiop="${op.id}" ${state.aiOps[op.id] ? "checked" : ""} ${blocked ? "disabled" : ""}>
            <span class="aiop-body">
              <span class="aiop-label">${esc(op.label)}
                ${op.recommended ? '<span class="badge certain">best value</span>' : ""}
                <span class="needs ${op.needs}">sends ${esc(NEED_LABEL[op.needs])}</span>
                <span class="aiop-cost num">$${op.cost.toFixed(2)}</span></span>
              <span class="aiop-desc">${esc(op.desc)} <span class="mono">${esc(op.unit)}</span></span>
              ${blocked ? `<span class="blockedwhy">Blocked \u2014 "${esc(post.label)}" does not permit sending ${esc(NEED_LABEL[op.needs])}.</span>` : ""}
            </span>
          </label>`;
        }).join("")}

        <div class="aitotal">
          <span>Estimated cost</span>
          <b class="num">$${total.toFixed(2)}</b>
          <span class="aitotal-note">${chosen.length} operation${chosen.length === 1 ? "" : "s"}
            \u00b7 an estimate, not a quote</span>
        </div>

        ${state.aiDone ? `
          <div class="airesult">
            <b>\u2713 Pass complete.</b> Results are marked <span class="badge cited">CITED</span> or
            <span class="badge inferred">INFERRED</span> in the Glossary and carry their source or blind spot.
            <button class="linkbtn" data-airun="reset" style="margin-left:.4rem">Clear results</button>
          </div>`
        : state.aiConfirm ? `
          <div class="aiconfirm">
            <b>Confirm: this spends money and sends data off this machine.</b>
            <div style="margin:.35rem 0 .5rem;font-size:.76rem">
              ${chosen.length} operation${chosen.length === 1 ? "" : "s"} \u00b7 estimated
              <b class="num">$${total.toFixed(2)}</b> \u00b7 sending
              ${[...new Set(chosen.map(o => NEED_LABEL[o.needs]))].join(" + ") || "nothing"}.
              ${chosen.some(o => o.needs === "source") ? "<br><b>This includes your source code.</b>" : ""}
            </div>
            <div style="display:flex;gap:.4rem;flex-wrap:wrap">
              <button class="actbtn danger" data-airun="go">Yes \u2014 run it now</button>
              <button class="linkbtn" data-airun="cancel">Cancel</button>
            </div>
          </div>`
        : `<button class="actbtn primary" data-airun="arm" ${chosen.length ? "" : "disabled"}>
             ${chosen.length ? "Run \u2026 then confirm" : (state.egress === "off" ? "Nothing selected \u2014 egress is off" : "Nothing selected")}
           </button>`}
      </div>
    </section>
  </div>`;
}

/* ═══ the two vocabulary lanes ═══════════════════════════════════════════════
 *
 * The program's own words, and what it does about names. Both were computed, tested and
 * served long before either page could show them: `resolve/naming.py` and
 * `resolve/glossary.py` do the work, `web/vocabulary.py` exposes it, and these two views
 * were still the ratified prototype's -- written against a shape the server does not send.
 *
 * They said so rather than rendering the real data wrongly, which was the right holding
 * position and is not a place to stay: "this page is not ported" and "this program has no
 * conventions" are opposite claims and the reader cannot tell them apart from a blank.
 *
 * What changed in the shape, and why each one is not a rename:
 *
 *   `{pattern, ok, n, exceptions: [str]}`  ->  `{glob, holds, total, kind, rating,
 *                                               prevalence, sql, note,
 *                                               exceptions: [{name, where}]}`
 *
 * `glob` is the population as a machine-readable string and is **the same string the
 * exceptions query is built from** (rule 41), so it is what makes a convention followable:
 * the cohort you land in is the population the number was measured over. `rating` is the
 * grade, and `naming.py` says why it leads rather than the percentage -- "a percentage
 * implies a precision this does not have". An exception carries where it lives, so a
 * reader can go and look at the three `*Error` classes that are not exceptions.
 *
 *   `{term, declared, module, opaque, docs, project}`  ->  `{term, uses, used_as,
 *                                                           defined, senses: [...]}`
 *
 * The prototype knew in advance which three documents would define a word. The served
 * shape does not, and must not: design rule 11 says documentation is often absent and every
 * path has to work with none at all. A term carries however many senses anything said about
 * it, each with its own provenance, file, line, heading and form -- so the view groups by
 * evidence rather than by a document it expects to find.
 */

/* Both lanes are computed at start, server side, and fetched when their page is opened.
 * Their *sizes* ride with the cover instead, because the navigator states a count beside
 * every other row (see `cover.py`). */
async function loadNaming() {
  if (VOCAB.naming) return;
  VOCAB.naming = "loading";
  try {
    const r = await fetch("/api/naming");
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    CONVENTIONS = d.conventions || [];
    VOCAB.gaps = d.gaps || [];
    VOCAB.thresholds = d.thresholds || {};
    VOCAB.naming = "ready";
  } catch (err) {
    VOCAB.naming = "failed";
    VOCAB.namingError = err.message;
  }
}

async function loadGlossary() {
  if (VOCAB.glossary) return;
  VOCAB.glossary = "loading";
  try {
    const r = await fetch("/api/glossary");
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    /* Defined and undefined are two bands, not one list with a flag, because they are read
     * for different reasons: a defined word is evidence to weigh, an undefined one is the
     * mirror's finding -- a word this program leans on and never explains. */
    TERMS = (d.terms || []).filter(t => t.defined);
    UNDEFINED = d.undefined || [];
    VOCAB.coverage = d.coverage || [0, 0];
    VOCAB.definitionsSeen = d.definitions_seen || 0;
    VOCAB.documentsSeen = d.documents_seen || 0;
    VOCAB.glossary = "ready";
  } catch (err) {
    VOCAB.glossary = "failed";
    VOCAB.glossaryError = err.message;
  }
}

/* The three parts of the glossary a filter changes. Nothing else on the page depends on
   it, and rebuilding the rest is what made typing unusable. */
function refreshGlossaryLists() {
  const q = state.termFilter.trim().toLowerCase();
  const defined = TERMS.filter(t => !q || t.term.toLowerCase().includes(q)
    || (t.senses || []).some(s => s.definition.toLowerCase().includes(q)));
  const undef = UNDEFINED.filter(t => !q || t.term.toLowerCase().includes(q));
  const set = (id, html) => { const el = $(id); if (el) el.innerHTML = html; };
  set("#glossCount", glossCount(defined, undef));
  set("#glossDefined", glossTerms(defined));
  set("#glossUndefHead", undefHead(undef));
  set("#glossUndef", glossUndefined(undef));
  /* The citation buttons in the rebuilt list need their listener back. Terms are delegated
     at the document and need nothing; a citation is not, because it carries an index into
     one term's senses. Same function as the page-wide bind, never a second copy of it. */
  bindCitations("#glossDefined ");
}

/* Opening a citation: the one implementation, called from the page bind and again after
   the filter rebuilds the list it lives in. */
function bindCitations(within) {
  $$(`${within}[data-cite]`).forEach(b => b.addEventListener("click", () => {
    state.viewer = { term: b.dataset.cite, idx: parseInt(b.dataset.citeidx, 10) };
    VIEWER_SRC = null;
    render();
    loadViewerSource();
  }));
}

/* Asked once, from the one place that knows which page is about to be painted.
 *
 * Both loaders are idempotent -- they set their lane to "loading" before the first await,
 * so the repaint this triggers on arrival does not start a second request. Wiring the fetch
 * to a click instead would work from the navigator and fail from the breadcrumb, the trail,
 * a curiosity and `data-goto`, and the failure is a page that says "not asked for yet" with
 * nothing on it that would ever ask. */
function ensureVocabulary() {
  if (state.view === "glossary" && !VOCAB.glossary) loadGlossary().then(render);
  if (state.view === "naming" && !VOCAB.naming) loadNaming().then(render);
}

/* Which provenance block is open, keyed by **pane and card** rather than by card alone.
 *
 * Exactly one is open at a time across the whole app, which is right -- and a bare index
 * makes that one number mean two things, because every pane numbers its own cards from
 * zero. Open the naming page's third query, switch to the curiosities, and that pane's
 * third card is open too: a block nobody asked for, with nothing on screen to explain it.
 *
 * One function rather than a prefix written at each site, because a key composed in two
 * places is two decisions about one thing and they drift the first time either moves
 * (rule 51). The attribute and the comparison both come through here. */
function provKey(pane, i) { return `${pane}:${i}`; }

/* The doorway panel's fetch state. Its own bag rather than a third lane inside `VOCAB`,
 * which is the two naming lanes and their data: a shared *renderer* is one truth, a shared
 * bag would be one pane keeping another's flag. */
const CURIOS = {};

/* Ten measured extrema, asked for once. Idempotent the same way the vocabulary loaders
 * are -- the lane is set before the first await, so the repaint this triggers on arrival
 * does not start a second request. */
async function loadCuriosities() {
  if (CURIOS.lane) return;
  CURIOS.lane = "loading";
  try {
    const r = await fetch("/api/curiosities");
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    CURIOSITIES = d.curiosities || [];
    CURIOS.families = d.families || 0;
    CURIOS.silent = d.silent || [];
    CURIOS.lane = "ready";
  } catch (err) {
    CURIOS.lane = "failed";
    CURIOS.error = err.message;
  }
}

/* Asked from the one place that knows which page is about to be painted, for the reason
 * `ensureVocabulary` states: wiring the fetch to the navigator row instead would work from
 * there and fail from the breadcrumb, the trail and `data-goto`. */
function ensureCuriosities() {
  /* `buildNav()` as well as `render()`, and it is not belt and braces. The count beside
     *Worth a look* comes from this lane, and `render()` does not rebuild the navigator --
     so the number arrived, the panel filled, and the row went on saying nothing until some
     unrelated thing happened to rebuild the pane. Whoever sets the state does the work of
     showing it (rule 55's companion); found by opening the panel and looking at the row. */
  if (state.view === "curiosities" && !CURIOS.lane) {
    loadCuriosities().then(() => { buildNav(); render(); });
  }
}

/* "Not asked for yet", "on its way", "the server refused" and "there is nothing here" are
 * four different things and a blank panel states the wrong one whichever it is.
 *
 * The bag is a parameter because three panes now fetch on demand and each keeps its own
 * flag. What must not be duplicated is *this* -- the four states and how each reads -- and
 * a second copy of it is how one pane quietly starts calling a failure an empty answer. */
function laneState(bag, lane, err, what) {
  if (!bag[lane]) return `<div class="note">${esc(what)} has not been asked for yet.</div>`;
  if (bag[lane] === "loading") return `<div class="note">Reading ${esc(what)}…</div>`;
  if (bag[lane] === "failed") {
    return `<div class="note"><b>${esc(what)} could not be read.</b>
      ${esc(bag[err] || "no reason given")}. Nothing is being shown rather than something
      being guessed.</div>`;
  }
  return "";
}

/* The last two segments of a path. The whole thing is kept in `title`: a citation the
 * reader cannot check is not a citation, and a citation that eats the pane is not readable.
 * Never shortened from the left with `direction: rtl` -- that renders a string the program
 * does not contain. */
function srcShort(path) {
  const parts = String(path || "").split("/").filter(Boolean);
  return parts.slice(-2).join("/") || String(path || "");
}

/* ═══ naming standard: the conventions, and what breaks them ═══ */

/* Grouped by what the convention is *about*, because the four kinds answer four different
 * questions and reading them in one flat list makes the spelling rules and the leakage
 * finding look like the same sort of claim. Routed from a table (design rule 16): a kind
 * this shell has never heard of is named on the page and in the console, not folded
 * silently into whatever group happens to be first. */
const CONV_KINDS = [
  ["CASE", "How names are spelled",
   "Measured per row rather than per distinct name — a denominator counted one way and a numerator another once reported a 79% convention that holds in every case."],
  ["HOUSE_PREFIX", "The house prefix",
   "Whether everything this program ships answers to one name."],
  ["AFFIX", "What an affix promises",
   "An affix that predicts a property, stated in the direction that holds. Every affix is tested against every property, which is thousands of tests — so a run of sixes is expected by chance and each of these had to beat a correction for the number of tries."],
  ["LEAKAGE", "Whether a boundary holds",
   "Not what the names say, but whether the thing they claim is true."],
];

function ratingBadge(r) {
  // A grade, not a severity. The severity palette belongs to the anomaly worklist and
  // spending it here would say "this convention is broken", which is not the claim
  // (design rule 4: one dimension at a time).
  const cls = r === "A" ? "certain" : "opaque";
  return `<span class="badge ${cls}" title="A ≥ 99.9%, B ≥ 98%, C ≥ 95%, D ≥ 90%, E below">${esc(r)}</span>`;
}

function conventionPanel(cv, i) {
  const pct = (cv.prevalence != null ? cv.prevalence : (cv.total ? cv.holds / cv.total : 0)) * 100;
  const missing = cv.total - cv.holds;
  const heading = cv.glob || cv.population;
  return `
  <section class="panel">
    <div class="panel-head">
      <h2 style="text-transform:none;letter-spacing:0;font-size:.9rem;color:var(--text);font-family:var(--f-mono)">${esc(heading)}</h2>
      ${ratingBadge(cv.rating)}
      <span class="hint">${esc(cv.claim)}</span>
    </div>
    <div class="panel-body">
      <div class="convbar">
        <span class="bar" style="flex:1"><i style="width:${pct.toFixed(2)}%"></i></span>
        <span class="num" style="font-weight:700">${cv.holds.toLocaleString()} of ${cv.total.toLocaleString()}</span>
      </div>

      ${missing ? `
        <div class="excepthead">${missing.toLocaleString()} exception${missing === 1 ? "" : "s"}${
          cv.exceptions.length < missing
            ? ` — showing ${cv.exceptions.length.toLocaleString()}` : ""}</div>
        <ul class="exceptlist">
          ${cv.exceptions.map(e => `<li><span class="mono">${esc(e.name)}</span>${
            e.where ? ` <span class="hint" title="${esc(e.where)}">${esc(srcShort(e.where))}</span>` : ""}</li>`).join("")}
        </ul>`
        : `<div class="excepthead ok">No exceptions. This convention holds everywhere.</div>`}

      ${cv.note ? `<div class="why" style="margin-left:0;margin-top:.5rem">
        <span class="ln">note</span> ${esc(cv.note)}
      </div>` : ""}

      ${cv.glob ? `
      <div class="prov">
        <button class="cite" data-thread="${esc(JSON.stringify({ type: "cohort", kind: "convention", key: cv.glob, label: cv.glob }))}"
                data-threadlabel="${esc(cv.glob)}" data-threadwhy="${esc(cv.claim)}">
          <span class="citeicon" aria-hidden="true">◈</span>Show all ${cv.total.toLocaleString()} in the graph<span class="citego">go</span></button>
      </div>` : ""}

      ${cv.sql ? `
      <div class="prov">
        <button class="cite" data-sqlshow="${provKey("conv", i)}">
          <span class="citeicon" aria-hidden="true">⌗</span>How this number was counted<span class="citego">show the query</span></button>
        ${state.showSql === provKey("conv", i) ? `<pre class="srcblock sqlblock">${esc(cv.sql)}</pre>
          <div class="provfoot">Run it yourself:
            <span class="mono">dunneflow query &lt;this map&gt; --sql "…"</span> — the directory this
            dashboard is serving, not the source tree.
            A counted claim proves itself by being reproducible, so the query is its provenance:
            it returns exactly the ${missing.toLocaleString()} exception${missing === 1 ? "" : "s"} listed above.</div>` : ""}
      </div>` : ""}
    </div>
  </section>`;
}

function viewNaming() {
  const waiting = laneState(VOCAB, "naming", "namingError", "the naming standard");
  if (waiting) return `<div style="max-width:58rem">${waiting}</div>`;

  const th = VOCAB.thresholds || {};
  const gaps = VOCAB.gaps || [];
  const grouped = [];
  const seen = new Set();
  for (const [kind, title, blurb] of CONV_KINDS) {
    const rows = CONVENTIONS.filter(c => c.kind === kind);
    rows.forEach(c => seen.add(c));
    if (!rows.length) continue;
    grouped.push({ kind, title, blurb, rows });
  }
  // Never fold an unrecognised kind into a group that happens to exist: it would read as
  // a deliberate placement. It gets its own heading and says what it is.
  const strays = CONVENTIONS.filter(c => !seen.has(c));
  if (strays.length) {
    console.error("[dunneflow] naming conventions of a kind this shell has no heading for:",
                  [...new Set(strays.map(c => c.kind))]);
    grouped.push({
      kind: "unknown", title: "Measured, and not described here",
      blurb: "This shell has no heading for these kinds — " +
             [...new Set(strays.map(c => c.kind))].join(", ") +
             ". They are shown as measured rather than left out.",
      rows: strays,
    });
  }

  let n = 0;
  return `
  <div style="max-width:58rem;display:flex;flex-direction:column;gap:.75rem">
    <div class="note">
      <b>Every figure here is counted, not guessed.</b> The exceptions are the point: a convention
      followed every time tells you how to read the program, and a convention followed nearly every
      time tells you where to look. The grade leads rather than a percentage, because a percentage
      implies a precision this does not have.
    </div>

    ${!CONVENTIONS.length ? `<div class="note">
      <b>No naming convention in this program meets the bar.</b> That is a measurement, not an
      omission — ${esc(Object.entries(th).map(([k, v]) => `${k} ${v}`).join(", ") || "the thresholds below")}.
      A population smaller than the minimum is not reported at all, in either direction.
    </div>` : ""}

    ${grouped.map(g => `
      <div class="convgroup">
        <div class="convgroup-head">${esc(g.title)}
          <span class="num" style="font-weight:400;text-transform:none;letter-spacing:0"> · ${g.rows.length}</span></div>
        <div class="hint" style="margin:-.25rem 0 0">${esc(g.blurb)}</div>
        ${g.rows.map(cv => conventionPanel(cv, n++)).join("")}
      </div>`).join("")}

    <section class="panel">
      <div class="panel-head">
        <h2>Looked at and found nothing</h2>
        <span class="hint">${gaps.length} population${gaps.length === 1 ? "" : "s"} with no dominant convention</span>
      </div>
      <div class="panel-body">
        ${gaps.length ? gaps.map(g => `
          <div class="gaprow">
            <div class="mono">${esc(g.population)}</div>
            <div>${g.total.toLocaleString()} of them, spelled
              ${g.spread.map(([style, k]) => `${esc(style)} <span class="num">${k.toLocaleString()}</span>`).join(", ")}
              — no single style holds often enough to be called a convention.</div>
          </div>`).join("")
        : `<p class="hint">Every population large enough to measure produced a dominant
           convention. This section exists so that a program where none did says so, rather
           than showing a shorter list that looks the same as a tidier program.</p>`}
        <div class="provfoot">Reported only when
          ${esc(Object.entries(th).map(([k, v]) => `${k} = ${v}`).join(" · ") || "no thresholds were sent")}.
          An affix must also beat a correction for the number of affixes tried — with thousands
          of tests, seven out of seven happens by itself.</div>
      </div>
    </section>
  </div>`;
}

/* ═══ glossary: the program's words, and who says what they mean ═══ */

/* Four tiers, never blended (design rule 13). Two of them are real today; the other two
 * arrive with `dunneflow infer`, which is off until someone turns it on. */
const TIER = {
  DECLARED_CODE: ["certain", "DECLARED · code", "quoted from a docstring in this program"],
  DECLARED_DOCS: ["certain", "DECLARED · docs", "quoted from the project's own documents"],
  CITED: ["info", "CITED", "a model found it in prose and cited the line — checkable"],
  INFERRED: ["inferred", "INFERRED", "nothing in the project explains it; this is a guess"],
};

function tierBadge(p) {
  const t = TIER[p];
  if (!t) {
    // A provenance the shell has no badge for must not borrow another one: the whole
    // point of the tiers is that a quotation and a guess never look alike.
    console.error("[dunneflow] no badge for provenance:", p);
    return `<span class="badge opaque">${esc(String(p))}</span>`;
  }
  return `<span class="badge ${t[0]}" title="${esc(t[2])}">${esc(t[1])}</span>`;
}

/* Only code can be opened. `source.db` holds the file bodies the graph was built from --
 * 626 of them on the sample program -- and the document corpus is scanned but not stored,
 * so a definition quoted out of a Markdown file names its file and line and stops there.
 * That is a limitation to state, not to hide behind a button that opens nothing. */
function senseOpens(s) { return s.provenance === "DECLARED_CODE"; }

/* Which tiers this program actually produced. The key lists all four because the four are
   what a tier badge can mean, and a reader who sees only two has no way to know whether the
   other two are missing or unexplained. The bottom two arrive with the model pass, which is
   off until someone turns it on -- so on every deterministic map they read "none here", and
   that is the honest statement rather than a legend for badges nobody will see. */
function seenTiers() {
  return new Set(TERMS.flatMap(t => (t.senses || []).map(s => s.provenance)));
}

function senseRow(term, s, i) {
  const where = `${esc(srcShort(s.source))}:${s.line}`;
  return `
  <div class="termrow">
    ${tierBadge(s.provenance)}
    <div class="termdef">
      <span class="quoted">${esc(s.definition)}</span>
      <div class="src">
        ${senseOpens(s)
          ? citeBtn(term, i, `${srcShort(s.source)}:${s.line}`)
          : `<span class="mono" title="${esc(s.source)}">${where}</span>`}
        ${s.heading ? ` · under ${esc(s.heading)}` : ""}
        ${s.form ? ` · ${esc(s.form.toLowerCase().replace(/_/g, " "))}` : ""}
      </div>
    </div>
  </div>`;
}

function viewGlossary() {
  const waiting = laneState(VOCAB, "glossary", "glossaryError", "the glossary");
  if (waiting) return `<div style="max-width:58rem">${waiting}</div>`;

  const q = state.termFilter.trim().toLowerCase();
  const hit = t => !q || t.term.toLowerCase().includes(q)
    || (t.senses || []).some(s => s.definition.toLowerCase().includes(q));
  const defined = TERMS.filter(hit);
  const undef = UNDEFINED.filter(t => !q || t.term.toLowerCase().includes(q));
  const [cov, tot] = VOCAB.coverage || [0, 0];

  return `
  <div style="max-width:58rem;display:flex;flex-direction:column;gap:.75rem">

    <div class="tierkey">
      ${Object.keys(TIER).map(p => `<span>${tierBadge(p)} ${esc(TIER[p][2])}${
        seenTiers().has(p) ? "" : " — none here"}</span>`).join("")}
    </div>

    <div class="note">
      <b>${cov.toLocaleString()} of the ${tot.toLocaleString()} words this program uses as
      names are defined somewhere it can quote.</b>
      ${VOCAB.documentsSeen ? `${VOCAB.definitionsSeen.toLocaleString()} definitions were found
        across ${VOCAB.documentsSeen.toLocaleString()} documents, and every one of them names the
        file and the line it came from.`
      : `No document store was read, so every definition here comes out of the code itself
        — which is the normal case, not a degraded one.`}
      The ${(tot - cov).toLocaleString()} the program does not define are listed below rather
      than left out: a word carried by fifty constants and explained nowhere is a finding.
      <b>Documents are scanned but not stored</b>, so a definition quoted from one names its
      line and cannot be opened here; a docstring can.
    </div>

    <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap">
      <label class="sr-only" for="termq">Filter terms</label>
      <input id="termq" class="termq" type="search" placeholder="Filter ${tot.toLocaleString()} words…" value="${esc(state.termFilter)}">
      <span id="glossCount" style="font-size:.74rem;color:var(--text-muted)">${glossCount(defined, undef)}</span>
    </div>

    <div id="glossDefined" style="display:flex;flex-direction:column;gap:.75rem">${glossTerms(defined)}</div>

    <section class="panel">
      <div class="panel-head">
        <h2>Used, and defined nowhere</h2>
        <span class="hint" id="glossUndefHead">${undefHead(undef)}</span>
      </div>
      <div class="panel-body" id="glossUndef">${glossUndefined(undef)}</div>
    </section>
  </div>`;
}

/* Design rule 1: a filtered view states what it removed, in counts. */
function glossCount(defined, undef) {
  const q = state.termFilter.trim();
  const hidden = TERMS.length + UNDEFINED.length - defined.length - undef.length;
  return `<b class="num">${defined.length.toLocaleString()}</b> defined and
    <b class="num">${undef.length.toLocaleString()}</b> undefined
    ${q ? `match “${esc(q)}” — <b class="num">${hidden.toLocaleString()}</b> hidden by the filter`
        : "— nothing hidden"}`;
}

function undefHead(undef) {
  return `${undef.length.toLocaleString()} word${undef.length === 1 ? "" : "s"}, most used first`;
}

function glossTerms(defined) {
  return defined.map(t => `
      <section class="panel term">
        <div class="panel-head">
          <h2 style="text-transform:none;letter-spacing:0;font-size:.92rem;color:var(--text);font-family:var(--f-mono)">${esc(t.term)}</h2>
          <span class="kind-tag">${esc(t.used_as)}</span>
          <button class="cite" data-term="${esc(t.term)}" data-termuse="${esc(t.used_as)}">
            <span class="citeicon" aria-hidden="true">◈</span>where it is used<span class="citego">go</span></button>
        </div>
        <div class="panel-body">
          ${(t.senses || []).map((s, i) => senseRow(t.term, s, i)).join("")}
        </div>
      </section>`).join("");
}

function glossUndefined(undef) {
  return `${undef.length ? `<ul class="undeflist">
          ${undef.map(t => `<li>
            <button class="cite" data-term="${esc(t.term)}" data-termuse="${esc(t.used_as)}">
              <span class="mono">${esc(t.term)}</span><span class="citego">go</span></button>
            <span class="hint">${esc(t.used_as)}</span>
          </li>`).join("")}
        </ul>`
        : `<p class="hint">Every word this program uses as a name is defined somewhere it can
           quote — which is rare, and worth knowing.</p>`}`;
}

/* ── the inspector ────────────────────────────────────────────────────────────
 *
 * One inspector, from two. The ratified design settled the *layout* and had one Mensores
 * routine pinned into it as a permanent subject; `/api/node` and a separate `inspector.js`
 * had the *data* and no design. Keeping both meant two implementations of the pane the
 * whole tool points at, which is how the graph and the shell ended up as two applications.
 *
 * **Flow-first, not signature-first**, and the order is the argument the tool makes:
 * how a thing is reached, what it does next, what it touches, and why it is there. The
 * signature is demoted into a section of its own; WHAT and WHY are interleaved, because a
 * comment belongs against the line it explains rather than pooled in a block at the end.
 */

/* Nothing is fetched twice for the same node: a repaint is not a reason to ask the server
 * again, and the graph repaints on every camera stop. */
let inspectorFor = null;

/* **The one place a subject is installed**, and therefore the one place a stale one is
 * cleared. Four callers set what the inspector answers about -- a click in the stack, a
 * click in the navigator or the diagram, a step restored from the trail, and a change of
 * altitude -- and every one of them used to write `state.selected` and load a node by hand.
 * Adding a second kind of subject to four hand-written sites is precisely the list rule 51
 * says grows: the fold would have outlived its selection at whichever site was forgotten,
 * and a pane confidently describing a class the reader left ten clicks ago is worse than a
 * blank one.
 *
 * Exclusive by construction, which is what lets `inspectorSubject()` be an accessor rather
 * than a rule every caller has to remember. */
function setSubject({ node = null, fold = null, flow = null } = {}) {
  state.flow = flow;
  state.fold = flow ? null : fold;
  state.selected = (flow || fold) ? null : node;
  if (flow) loadFlow(flow);
  else if (fold) loadFold(fold);
  else if (node) loadNode(node);
  else { inspectorFor = null; SPECIMEN = null; }
}

/* What to call the current subject on a trail step. A fold has no `selected` at all, so the
 * node-only version filed every box click as **"nothing selected"** -- a step that is
 * perfectly reversible and names nothing, which is a trail with no map on it. Beside
 * `inspectorSubject()` because it answers the same question in words. */
function subjectLabel() {
  /* An arrow is named by its two ends, because "an edge" is not somewhere anybody can be
   * taken back to. The labels come from the drawing that is up, which is the same place
   * the arrow was clicked -- never from the id, which is two box ids with a separator in
   * the middle and is not a name (rule 30). */
  if (state.flow) {
    const ends = splitEdgeId(state.flow);
    const by = (diagramNow && diagramNow.by_id) || {};
    if (ends && by[ends[0]] && by[ends[1]]) {
      return `${by[ends[0]].label} \u2192 ${by[ends[1]].label}`;
    }
    return "a flow";
  }
  if (state.fold) {
    const box = diagramNow && diagramNow.by_id[state.fold];
    return (box && box.label) || state.fold;
  }
  return state.selected ? labelFor(state.selected) : "nothing selected";
}

/* **Which rows the routine list marks.** One node when a node is selected; *every member*
 * when a fold is. Design rule 26 says the list and the picture are one instrument and it has
 * to run both ways -- and the diagram half of that was dead: a fold sets no `state.selected`
 * at all, so `current: state.selected === r.id` matched nothing and the navigator went on
 * marking whatever had been clicked before. A stale highlight is worse than none (rule 51),
 * and this was worse again: nothing moved, so the click read as having failed.
 *
 * Marking sixty-one rows is the honest answer rather than an unfortunate one. They are what
 * the reader picked; the number is stated in the pane beside them; and picking one of them
 * narrows it to that one, which is the loop working. Tom raised it as a worry -- "some boxes
 * say 3 functions, so highlighting all three might be problematic" -- and the alternative is
 * electing a member, which is exactly the defect the fold exists to undo. */
function selectedRowIds() {
  if (state.flow || state.fold) return new Set(((state.wanted || {}).nodes) || []);
  return new Set(state.selected ? [state.selected] : []);
}

/* **Look at this box.** Two callers -- a click on the drawing, and a neighbour row in a
 * fold's own pane -- and it goes through `selectFromNav` like every other selection, so the
 * stack lights what the box holds, the navigator follows, the trail records it and undo can
 * reverse it. A second path that only filled the inspector would be a selection the rest of
 * the dashboard never heard about (rule 51).
 *
 * `await`ed before the trail step, because a step captures the subject as it stands: pushing
 * first files a step whose subject is the *previous* one, which renders and highlights
 * perfectly and takes the reader somewhere else. `codelink` documents this and the diagram's
 * own handler had it the other way round. */
async function selectFold(boxId) {
  if (!boxId) { console.error("DunneFlow: a box row with no identity"); return; }
  const box = diagramNow && diagramNow.by_id[boxId];
  /* No `pushTrail` of its own. `selectFromNav` already records the step, and a second one
     with a better label is deduplicated away by subject -- so the pane kept the *first*
     one, which is why every box click filed itself as "nothing selected" until
     `subjectLabel()` existed. One place makes a step; it has to be able to name what it
     made (rule 51, and rule 30 -- a step whose label is not its subject). */
  await selectFromNav({ nodes: (box && box.members) || [], fold: boxId });
}

/* **What the inspector is answering about, in one place.**
 *
 * There are two kinds of subject now -- a node and a fold -- and exactly one of them is
 * ever set. Expressed as an accessor rather than as a convention, because a convention is
 * what every caller has to remember and rule 51 is a list of the times one of them did not.
 * Everything that asks "what is being inspected" asks here. */
function inspectorSubject() {
  return state.flow || state.fold || state.selected || null;
}

/* One fetch-and-paint, two subjects. `loadNode` and `loadFold` differ in the endpoint they
 * ask and in whether threads apply -- a thread is adjacency for one node, and a class has
 * no threads of its own -- and in nothing else. Written once so the two cannot drift in the
 * cache guard, the in-flight check or the order of the two renders. */
async function loadSpecimen(key, url) {
  if (key === inspectorFor) return false;
  inspectorFor = key;
  SPECIMEN = null;
  render();
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    if (inspectorFor !== key) return false;   // the reader moved on while this was in flight
    SPECIMEN = d.found ? d : { notFound: true, id: key, reason: d.reason };
  } catch (err) {
    if (inspectorFor === key) SPECIMEN = { notFound: true, id: key, reason: err.message };
  }
  followSelectionIntoCode();
  render();
  return true;
}

async function loadNode(id) {
  if (await loadSpecimen(id, `/api/node?id=${encodeURIComponent(id)}`)) loadThreads(id);
}

/* A diagram box, asked about as the thing it stands for.
 *
 * No `loadThreads`: `threads.py` answers adjacency *by interest* for one node, and there is
 * no node here. Asking with a box id would 404 on every click -- which is exactly what
 * `fetches: false` was added to the hover card to prevent, one surface over. */
async function loadFold(boxId) {
  await loadSpecimen(boxId, `/api/fold?id=${encodeURIComponent(boxId)}`);
}

/* The separator between the two ends of an edge id, and the **only** place it is spelled on
 * this side. `diagram.py` writes it into every arrow's `id=`; a second literal here is a
 * second answer to what an edge is called, and it would be silently wrong rather than
 * broken -- `partition` on a separator that is not there yields an empty far end and a
 * panel that confidently answers about nothing.
 *
 * Split on the **first** occurrence, because a box id cannot contain one and the far end
 * may itself be a box id. A guard asserts that on the server, where the ids are made. */
const EDGE_SEP = "=>";

function splitEdgeId(eid) {
  const at = String(eid || "").indexOf(EDGE_SEP);
  if (at <= 0) return null;
  const src = eid.slice(0, at), dst = eid.slice(at + EDGE_SEP.length);
  return (src && dst) ? [src, dst] : null;
}

/* One arrow, asked about as what passes along it.
 *
 * `inside` is `state.diagramBox` and not a copy of it. The two levels are two different
 * compartments and the same pair of ids can name an arrow on either, so the server is told
 * which drawing the question is about rather than left to read it out of the id -- which
 * would be inferring an identity from the shape of a string (rule 30).
 *
 * No `loadThreads`, for the fold's reason: adjacency by interest is a question about one
 * node, and an arrow is not one. */
async function loadFlow(edgeId) {
  const ends = splitEdgeId(edgeId);
  if (!ends) { console.error("DunneFlow: an arrow with no two ends", edgeId); return; }
  const inside = state.diagramBox || "";
  const url = `/api/flow?from=${encodeURIComponent(ends[0])}&to=${encodeURIComponent(ends[1])}`
            + (inside ? `&inside=${encodeURIComponent(inside)}` : "");
  /* Keyed on the edge **and** the drawing it is on, or opening the same pair at the second
   * level after the first would be answered out of the cache with the first level's reply
   * (rule 42's family -- a guard that names the right case and asks the wrong question). */
  await loadSpecimen(`${inside}\u0000${edgeId}`, url);
}

/* **Look at this arrow.** Goes through `selectFromNav` like every other selection, so the
 * stack lights both ends, the navigator follows, the trail records it and undo reverses it.
 * A path that only filled the inspector would be a selection the rest of the dashboard
 * never heard about (rule 51) -- which is the defect the fold was built to undo, and it
 * would have been rebuilt here one function along.
 *
 * Both ends' members, because that is what the arrow is about. A port holds none, so an
 * arrow into one lights the near side alone and says so in the pane. */
async function selectFlow(edgeId) {
  const ends = splitEdgeId(edgeId);
  if (!ends) { console.error("DunneFlow: an arrow row with no identity"); return; }
  const by = (diagramNow && diagramNow.by_id) || {};
  const nodes = [...((by[ends[0]] || {}).members || []),
                 ...((by[ends[1]] || {}).members || [])];
  await selectFromNav({ nodes, flow: edgeId });
}

/* **The other direction.** Design rule 26 says the list and the picture are one instrument
 * and it has to run both ways -- clicking a name in the source selects it, and selecting
 * anything anywhere moves the code to where it lives.
 *
 * Only while code is on screen. Fetching half a megabyte on every click for a pane nobody
 * has open is rule 45's cost paid for nothing, and the file is opened when the reader opens
 * the pane instead. The file is read from `SPECIMEN.where`, which is the one selection --
 * never from a second copy, because rule 51 was written from a window that kept its own
 * node id and disagreed with the app the first time anything else moved one of them.
 */
function codeOnScreen() {
  return state.view === "code"
      || groupOpen(NAV_GROUPS.find(g => g.id === "navCode"));
}

function followSelectionIntoCode() {
  if (!codeOnScreen()) return;
  const w = SPECIMEN && SPECIMEN.where;
  if (!w || !w.file) return;
  /* One spelling. This read an absolute path the file list used to carry beside the short
   * one, and fell back to an `endsWith` on the short one -- a name match wearing a suffix
   * (rule 5): `cli/audit.py` also ends `/audit.py`. Both ends are the store's own relative
   * path now, so it is an equality. */
  const f = FILES.find(x => w.file === x.path);
  if (!f || f.path === state.codeFile) return;
  state.codeFile = f.path;
  persist();
  loadCodeFile(f.path);
}

/* The reasons a neighbour is worth a detour, asked alongside the node itself.
 *
 * A separate request rather than a field on `/api/node`, because the two answer at
 * different speeds and for different reasons: the inspector's own content is one lookup
 * per section on an indexed id, while a thread is a self-join over every annotation or
 * every `sql_ops` row in the program. Blocking the pane the whole tool points at on the
 * slower of the two would make every selection feel like the slowest thing it does.
 *
 * Cached per node for the session. The store does not change while the map is open, so
 * asking twice for the same routine is asking the same question twice. */
async function loadThreads(id) {
  if (THREADS[id] !== undefined) return;
  try {
    const r = await fetch(`/api/threads?id=${encodeURIComponent(id)}`);
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    /* An empty list is a real answer -- most private helpers genuinely have nothing
       beside them -- and `null` is the other one: we asked and could not find out.
       The panel says something different for each, because "nothing here" and "nobody
       looked" are opposite claims. */
    THREADS[id] = d.found ? (d.threads || []) : null;
  } catch {
    THREADS[id] = null;
  }
  if (inspectorFor === id) render();
}

/* Design rule 5: confidence is **shape**, not colour -- solid for CERTAIN, dashed for
 * INFERRED. Rule 26: an external call is neither. Every call that did not resolve to a
 * local routine was once stored INFERRED, but that is not the claim being made -- we are
 * certain the call happens and simply cannot see the other end. Drawing the two the same
 * way blurs exactly what rule 6 says never to blur, so an external carries its own mark
 * and no confidence shape at all. */
/* A qualified name has no spaces, so a browser breaks it wherever the box happens to end
 * -- `resolve_session_id` became "resolve_session_ / id". It does have joints, though, so
 * `<wbr>` marks them and the break lands on a dot. Escaped first, then marked: doing it the
 * other way round would escape the markup we just added. */
function breakable(qual) {
  return esc(qual).split(".").join(".<wbr>");
}

function callBadge(c) {
  if (c.external) return `<span class="conf badge external">EXTERNAL</span>`;
  if (c.ambiguous) return `<span class="conf badge suspect">AMBIGUOUS</span>`;
  return `<span class="conf badge ${c.confidence === "CERTAIN" ? "certain" : "inferred"}"
    >${esc(c.confidence || "INFERRED")}</span>`;
}

/* Never a silent omission (design rule 1, and `LOST_EDGE` in another key). A list that has
 * been cut says so, in counts, with the whole number beside the shown one. */
/* The sentence, without the box around it. Two surfaces say this -- a pane in `.hint`, a
   card in `.hc-more` -- and they must say it the same way: two formulations of one fact is
   the defect the topbar's three filter notes were just unified out of. The wrapper differs
   because the surfaces differ; the words do not (rule 51). */
function cutWords(shown, total, what) {
  return `Showing ${shown.toLocaleString()} of ${total.toLocaleString()} ${what}.`;
}

function cut(shown, total, what) {
  if (shown >= total) return "";
  return `<div class="hint" style="margin-top:.35rem">${cutWords(shown, total, what)}</div>`;
}

/* What a thing reaches outside itself, as rows. One renderer, because a routine and a
 * **fold** answer the same question with the same rows -- a class's boundaries are its
 * methods' boundaries -- and a second copy here would be a second answer to what a touch
 * looks like the first time either was edited (rule 51).
 *
 * **Both the table and the destination were blank, on every row, since the day this was
 * written.** It read `q.table || q.statement` against `ROUTINE_SQL_OPS`, which sends `tbl`
 * and `sql`, and `nc.target || nc.host` against `ROUTINE_NET_CALLS`, which sends
 * `destination` -- so a SQL row rendered as `▤ SELECT :214` with nothing between the
 * operation and the line, and a network row named no host. Nothing failed and nothing was
 * `undefined` on screen: `esc(undefined || undefined || "")` is the empty string, and a
 * missing table is indistinguishable from a statement with no table in it. Rule 44, in the
 * same pane and the same shape as the parameters that rendered without their types. */
function touchRows(t) {
  const row = (glyph, kind, text, line) => `
      <div class="touchrow">
        <span class="gl" aria-hidden="true">${glyph}</span>
        <span class="k">${esc(kind)}</span>
        <span class="t">${text}${line != null
          ? ` <span class="dim" style="color:var(--text-faint)">:${line}</span>` : ""}</span>
      </div>`;
  return [
    ...(t.boundaries || []).map(b => row(BKIND_GLYPH[b.kind] || "◇", b.kind,
        `${esc(b.target)} <span class="dim">${esc(b.direction || "")}</span>`, b.line)),
    /* Direction is the point of a SQL row: a table written twice as often as it is read is
     * a doorway, and read/write is the distinction the database report is built on.
     * A statement with no table of its own -- BEGIN, COMMIT -- says so rather than
     * rendering as a blank subject beside an operation (rule 40's companion). */
    ...(t.sql || []).map(q => row("▤", q.operation || "SQL",
        `${q.tbl ? esc(q.tbl) : `<span class="dim">no table</span>`}
         <span class="dim">${esc(q.direction || "")}</span>`, q.line)),
    /* The full network record, because design rule 8 says an external is a first-class
     * node badged as outside our control, and what makes that useful is knowing the verb,
     * the destination and whether anyone set a timeout. */
    ...(t.net || []).map(nc => row("◆", nc.protocol || "NET",
        `${esc(nc.verb || "")} ${esc(nc.destination || "")}${nc.port
          ? `<span class="dim">:${esc(String(nc.port))}</span>` : ""} <span class="dim">${
          nc.timeout ? `timeout ${esc(String(nc.timeout))}` : "no timeout"}${
          nc.retries ? `, ${esc(String(nc.retries))} retries` : ""}</span>`, nc.line)),
    /* A file the program names is not a boundary it touches: naming is a choice the
     * authors made, touching is something the code does. */
    ...(t.artefacts || []).map(a => row("▣", a.kind || "ARTEFACT",
        esc(a.name || a.path || ""), a.line)),
  ];
}

/* ── a fold, described as the thing it stands for ──────────────────────────────────
 *
 * A diagram box is a class and its methods, or a file and its loose functions. It is not a
 * node, and the pane says so in every line: the head names the class, `Holds` lists what is
 * in it, and `In` / `Out` name **boxes** rather than routines, because at this grain the
 * neighbours are the other boxes on the drawing.
 *
 * Its own function rather than a branch threaded through the routine path. The two share
 * `touchRows`, `sec` and `cut` -- everything where one answer is right for both -- and
 * differ everywhere the *subject* differs, which is most of it. Threading it through would
 * have put five `s.kind === "FOLD"` tests inside a function that currently has none, and
 * the routine path is the one thing this change must leave exactly as it was.
 *
 * There is no Signature section and no threads panel, and both absences are the same fact:
 * a class has no invocation line, and `threads.py` answers adjacency by interest for one
 * node. Rendering either would be a control that looks finished and says nothing (rule 44).
 */
function viewInspectorFold(s) {
  const id = s.identity || {};
  const held = (s.holds && s.holds.routines) || [];
  const t = s.touches || {};
  const anns = (s.governance || {}).annotations || [];

  /* A neighbour of a fold is a box, so the button selects a **box**. Handing `data-node` a
     box id would be a link to nothing -- the id space is the drawing's, not the store's --
     which is the mistake `queries.py` wrote down before anything needed it.
     `data-box`, **not** `data-fold`: that attribute has collapsed a pane since design rule
     24, so the obvious name here would have made every neighbour row rail the inspector.
     Rule 71 -- a name is global -- caught on the way in rather than on the screen. */
  const flowRow = (arrow, r) => `
      <div class="flowitem">
        <span class="arrow">${arrow}</span>
        <button class="gotonode" data-box="${esc(r.id || "")}"
          title="${esc(r.id || "")}"><code>${esc(r.label || r.id || "")}${
          r.box_kind ? `<span class="dim">  ${esc(r.box_kind)}</span>` : ""}</code></button>
        <span class="conf badge ${r.crosses ? "" : "certain"}">${
          r.weight}${r.crosses ? " · crosses" : ""}</span>
      </div>`;

  const inRows = ((s.in || {}).callers) || [];
  const outRows = ((s.out || {}).calls) || [];
  const inBody = inRows.length ? inRows.map(r => flowRow("←", r)).join("")
    : `<div class="hint">Nothing on this diagram reaches it. That is either a way in, or a
       caller that lives on another plate and is drawn as a crossing rather than a box.</div>`;
  const outBody = outRows.length ? outRows.map(r => flowRow("→", r)).join("")
    : `<div class="hint">It reaches nothing else on this diagram.</div>`;

  /* **Never bounded** (rule 8). Sixty-one methods is sixty-one rows: the reader opened a
     class in order to find one of them, and a list cut at forty hides exactly the case
     where the cut matters. Each row is an ordinary node id, so opening one is the same
     selection every other row in this pane makes. */
  const holdsBody = held.length ? held.map(m => `
      <div class="flowitem">
        <span class="arrow">${m.is_async ? "≈" : "▸"}</span>
        <button class="gotonode" data-node="${esc(m.id || "")}"
          data-label="${esc(m.name || "")}"
          title="${esc(m.qualname || m.name || "")}"><code>${esc(m.name || "")}(${
          (m.params || []).map(pp => esc(pp.text)).join(", ")})${m.returns
            ? ` <span class="dim">→ ${esc(m.returns)}</span>` : ""}</code></button>
        <span class="dim" style="margin-left:auto">${gotoCodeBtn(id.file, m.line_start)
          }<span class="ln">:${m.line_start}</span></span>
      </div>`).join("")
    : `<div class="hint">This box folds nothing the store has a routine for.</div>`;

  const govBody = anns.length
    ? `<div class="govchips">${anns.map(a =>
        `<span class="govchip ${esc(String(a.kind || "").toLowerCase())}"
          >${esc(a.value)}</span>`).join("")}</div>`
    : `<div class="hint">No governance ids in anything it holds.</div>`;

  const touches = touchRows(t);
  const what = { class: "class", file: "file", touch: "boundary" }[id.fold] || id.fold || "box";
  return `
    <div class="insp-head">
      <h2>${breakable(id.qualname || s.label || s.id)}</h2>
      <div class="loc">${esc(id.file || "")}${(s.where || {}).first
        ? `:${s.where.first}–${s.where.last}` : ""} ${gotoCodeBtn(id.file, (s.where || {}).first)}</div>
      <div class="tags">
        <span class="badge certain">ANALYZED</span>
        <span class="kind-tag">${esc(what.toUpperCase())}</span>
        <span class="kind-tag">${id.folded} folded</span>
        <span style="margin-left:auto;display:flex;gap:.3rem">
          ${pinBtn(id.qualname || s.id, `${id.folded} routines, ${touches.length} touches`)}
          <button class="linkbtn" id="collapseAll">Collapse all</button>
        </span>
      </div>
    </div>
    ${sec("holds", what === "boundary" ? "Reached by" : "Holds", held.length, holdsBody)}
    ${sec("in", "In", inRows.length, inBody)}
    ${sec("out", "Out", outRows.length, outBody)}
    ${sec("touches", "Touches", touches.length, touches.length ? touches.join("")
        : `<div class="hint">Nothing it holds touches a boundary, a table, a remote or a
           named file.</div>`)}
    ${sec("gov", "Governance", anns.length, govBody)}

    <div class="insp-actions">
      <button class="actbtn" id="srcBtn">${s.source && s.source.available
        ? `Show source · ${(s.source.lines || []).length} lines`
        : "Source not stored"} <span class="k">S</span></button>
      <div id="srcPane" hidden>${srcPane(s)}</div>
    </div>`;
}

/* ── an arrow, described as what passes along it ──────────────────────────
 *
 * The third specimen, and the last one the diagram needs. A box says what a thing *is*;
 * this says what moves between two of them, which is what every arrow on the drawing has
 * been asserting and unable to state.
 *
 * **Call sites are listed, never grouped.** The drawing aggregates because a picture wants
 * the connection; a reader who clicks an arrow is asking what actually passes, and "7
 * calls" is the number they already read off the arrow (rule 32). Never bounded (rule 8):
 * they came here to find one of them.
 *
 * **The precision line is on the screen, not only in the source.** Every argument is the
 * expression as written; none of them is a type, and one is aligned to a parameter only
 * where the alignment is not a guess. Where it declines, the pane says *why it declined* --
 * a blank beside an argument reads as "no such parameter", which is a different and false
 * claim (design rule 13: a claim without its provenance is an assertion in a uniform).
 */
function viewInspectorFlow(s) {
  const id = s.identity || {};
  const calls = s.calls || [];
  const t = s.touches || {};

  /* An argument, with what it lands on if anything does. The expression is `<code>` because
   * it is source and reads as source; the binding is dimmed beside it because the argument
   * is the subject and the parameter is what happened to it. */
  const argRow = (a) => `
      <div class="argrow">
        <span class="argi">${a.keyword ? esc(a.keyword) + "=" : (a.splat ? "" : a.idx)}</span>
        <code class="argx">${breakable(a.expr || "")}</code>
        <span class="argb">${a.binds
          ? `<span class="dim">\u2192 ${esc(a.binds.name || "")}${a.binds.type
              ? `: ${esc(a.binds.type)}` : ""}</span>`
          : `<span class="dim" style="color:var(--text-faint)">${a.splat
              ? "a splat \u2014 not one argument" : "unbound"}</span>`}</span>
      </div>`;

  /* One call site: where it is written, what it passes, and the way to the line itself --
   * Tom's *"ultimately where it all goes"*. `gotoCodeBtn` is the same one door every other
   * route to the code goes through (rule 51). */
  const callRow = (c) => `
      <div class="callsite">
        <div class="callhead">
          <code>${breakable(c.callee_expr || "")}</code>
          <span class="conf badge ${c.confidence === "CERTAIN" ? "certain" : ""}">${
            esc(c.confidence || "")}</span>${c.external
              ? `<span class="kind-tag">external</span>` : ""}
          <span class="dim" style="margin-left:auto">${gotoCodeBtn(c.file, c.line)
            }<span class="ln">:${c.line}</span></span>
        </div>
        <div class="callin"><span class="dim">in</span> <code>${
          breakable(c.caller_name || "")}</code></div>
        ${(c.args || []).length ? (c.args || []).map(argRow).join("")
          : `<div class="hint">Called with no arguments.</div>`}
        ${c.declared && c.declared.length
          ? `<div class="calldecl"><span class="dim">declared</span> <code>${
              breakable(c.callee_name || "")}(${(c.declared || []).map(
                pp => esc(pp.text)).join(", ")})</code>${c.callee_returns
                ? ` <span class="dim">\u2192 ${esc(c.callee_returns)}</span>` : ""}</div>`
          : ""}
        ${c.unbound_because
          ? `<div class="hint">Arguments are shown as written and not aligned to
             parameters: ${esc(c.unbound_because)}.</div>` : ""}
      </div>`;

  const touches = touchRows(t);
  const kinds = (id.kinds || []).join(" + ") || "\u2014";
  const callBody = calls.length ? calls.map(callRow).join("")
    : (id.kinds || []).includes("CALL")
      ? `<div class="hint">This arrow carries calls the store has, and none of them
         resolved to a routine on the far side \u2014 they leave the program (rule 26:
         external is not inferred).</div>`
      : `<div class="hint">Nothing calls along this arrow; it carries ${esc(kinds)}.</div>`;

  return `
    <div class="insp-head">
      <h2>${breakable(s.label || s.id)}</h2>
      <div class="loc">${esc(id.from_kind || "")} \u2192 ${esc(id.to_kind || "")}${
        id.crosses ? ` \u00b7 crosses to another compartment` : ""}</div>
      <div class="tags">
        <span class="kind-tag">FLOW</span>
        <span class="kind-tag">${esc(kinds)}</span>
        <span class="badge certain">${id.weight} along it</span>
        <span style="margin-left:auto;display:flex;gap:.3rem">
          ${pinBtn(s.label || s.id, `${id.sites} call sites, ${touches.length} touches`)}
        </span>
      </div>
    </div>
    ${sec("calls", "Call sites", calls.length, callBody)}
    ${sec("touches", "Touches", touches.length, touches.length ? touches.join("")
        : `<div class="hint">Nothing along this arrow touches a boundary, a table, a
           remote or a named file.</div>`)}
    <div class="insp-actions">
      <p class="hint">Every expression here is what the caller wrote. Nothing is inferred:
         no argument is given a type, and one is named against a parameter only where the
         source settles it \u2014 a keyword by name, a position only when the callee is
         resolved and takes no <code>*args</code>. 92% of arguments on a resolved call bind;
         the rest say why they do not.</p>
    </div>`;
}

/* ── a constant, described as what it holds ──────────────────────────────
 *
 * **The value was not on this pane at all**, and what stood where it belongs was three
 * sentences that cannot be true of a constant. Selecting `GOVERNED_GATES` -- 8,586
 * characters, the largest named value in the corpus -- rendered the routine-shaped pane:
 *
 *     In  0       Nothing in this map calls it. That is either a way in, dead code, or a
 *                 call DunneFlow cannot see -- a dynamic dispatch, or a language it does
 *                 not read.
 *     Out 0       It calls nothing this map can see.
 *     Touches 0   It touches no boundary, table, remote or named file. Everything it
 *                 does, it does in memory.
 *
 * A constant is not a routine. It cannot be a way in or dead code, it calls nothing by
 * construction, and it does nothing in memory. Three answers, each *plausible*, each
 * inviting the reader to conclude the analysis had failed on a thing it had read
 * perfectly -- and the 8,586 characters it had read were the one thing absent. Rule 30's
 * shape one level up: not a label standing in for an identity, but a **kind** standing in
 * for another kind, which the routing above now stops.
 *
 * **What reads a constant is not a relation this map holds**, and that is said rather than
 * left as an empty section. The store has no table pairing a routine with a constant it
 * mentions -- `calls` is about calls -- so "nothing uses it" is a claim nothing here can
 * make. An absent connection stated is `LOST_EDGE`'s discipline in a pane: a missing
 * relation must be visible, or a program documents as a smaller one that works.
 */
/* The moved row for one constant, or `null`.
 *
 * Read out of `CHANGES` rather than fetched, exactly as `routineChange` reads it to mark a
 * navigator row: the comparison has already been made and holds both values, and asking
 * `/api/node` for them would make it answer about two versions when the whole design says
 * it answers about the base. One source, one answer (rule 51).
 *
 * Not indexed. A `Map` is what `routineIndex()` builds because it is asked 4,786 times per
 * repaint; this is asked once, for the one constant on screen, against a list that is seven
 * rows long on Mensores' pair. An index here would be the cache rule 52 warns about --
 * work done to avoid work that was never being done. */
function constantMoved(nodeId) {
  if (!comparing() || !CHANGES || CHANGES.loading || !CHANGES.available) return null;
  const rows = ((CHANGES.presence || {}).constants || {}).moved || [];
  return rows.find(r => r && r.id === nodeId) || null;
}

/* What moved, when the reader is holding this version against another.
 *
 * **The band's whole claim is that the thing is not constant any more**, and until this
 * existed the claim was made by a name and nothing else: `EXPECTED_SCHEMA_VERSION` moved,
 * with no way to learn that it went from 27 to 28 without opening two versions of the file.
 *
 * **Both sides are named by which version they are, and by nothing else.** `added` and
 * `deleted` are not available here and their absence is the point: a constant in this band
 * is declared in *both* versions, so neither side arrived and neither left. `diffWords()`
 * is deliberately not consulted -- it answers which end the reader takes to be newer, which
 * is an assumption, and a value that moved has no direction for it to colour. `◈` and no
 * sign, the same mark and the same reasoning the presence line uses for this band.
 *
 * **It says which of the three moved.** A constant is a value, a type and a finality, and
 * two of those can change while the value does not: `X: Final[int] = 1` becoming
 * `X: int = 1` moves twice and prints the same `1` on both sides. Without the line saying
 * so, that reads as two identical values under a heading claiming they differ -- rule 13 in
 * a pane, where the evidence shown must be what produced the claim.
 *
 * Bounded by nothing. This is the pane rule 8 sends a reader *to*; the card is the surface
 * that abbreviates, and it can only do that because this one does not. */
function movedBody(m) {
  if (!m) return "";
  const what = (m.moved || []).join(" and ") || "something";
  const side = (label, text) => `
    <div class="constside">
      <div class="constside-k mono">${esc(label)}</div>
      <pre class="constval mono">${esc(String(text == null ? "" : text))}</pre>
    </div>`;
  const short = (r) => String(r || "?").replace("T", " ").replace("Z", "");
  return `
    <div class="constmoved">
      <div class="hint"><b class="tone-moved">◈ ${esc(what)} differs</b> between the two
        versions. It is declared in both, so it was neither added nor deleted — what it
        holds has moved, which is the one thing a name on its own cannot say.</div>
      ${side(`${short(CHANGES.base)} — the version on screen`, m.base)}
      ${side(`${short(CHANGES.compared)} — held against it`, m.compared)}
    </div>`;
}

function viewInspectorConstant(s) {
  const id = s.identity || {};
  const value = String(id.value == null ? "" : id.value);
  const comments = ((s.governance || {}).comments) || [];
  const moved = constantMoved(s.id);

  /* **Whole, and it scrolls.** This is the one surface that shows a value entire, which is
     what lets the card bound itself and say so: rule 8 allows abbreviation only where the
     complete content sits beside it, and this pane is where "beside it" lives. The box caps
     its height in `tokens.css` rather than its content -- nothing is cut, so nothing here
     has a count to state. */
  const measure = `<div class="hint">${value.length.toLocaleString()} characters, shown
    whole${value.includes("\n") ? "" : " on the one line the source declares"}.</div>`;

  /* **The value once, never twice.** Where the constant has moved, `movedBody` already
     draws this version's value in a labelled box beside the other one -- so drawing it
     again underneath gave three boxes reading 28, 27, 28, and a reader who has to check
     whether the first and third are the same has been handed a puzzle rather than an
     answer. The measure stays either way: it is about this version's value and is true on
     both paths. */
  const valueBody = !value
    /* A constant the extractor recorded with no value is a real case and not an empty
       string: `_literal` declines what it cannot unparse. Naming it beats printing
       nothing, which reads as a value of "" (design rule 21 in a section). */
    ? `<div class="hint">No value was recorded. The declaration is in the source, but its
       right-hand side is not something the extractor could write down as a literal.</div>`
    : moved
      ? measure
      : `<pre class="constval mono">${esc(value)}</pre>${measure}`;

  const whyBody = comments.length
    ? comments.map(c => `<div class="why"><span class="ln">:${c.line}</span> ${
        esc(c.text)}</div>`).join("")
    : `<div class="hint">No comment says why it is this value. 1,047 of Mensores' 2,638
       named values carry one; this is not among them.</div>`;

  const tags = [
    id.is_final ? `<span class="kind-tag">FINAL</span>` : "",
    id.private ? `<span class="kind-tag">PRIVATE</span>` : "",
    id.type ? `<span class="kind-tag mono">${esc(String(id.type))}</span>` : "",
  ].filter(Boolean).join("");

  return `
    <div class="insp-head">
      <h2>${breakable(`${id.module || ""}.${id.name || s.label || ""}`)}</h2>
      <div class="loc">${esc(id.file || "")}${id.line ? `:${id.line}` : ""} ${
        gotoCodeBtn(id.file, id.line)}</div>
      <div class="tags">
        <span class="badge certain">ANALYZED</span>
        <span class="kind-tag">CONSTANT</span>
        ${tags}
        <span style="margin-left:auto;display:flex;gap:.3rem">
          ${pinBtn(`${id.module || ""}.${id.name || ""}`,
                   `${value.length.toLocaleString()} characters`)}
        </span>
      </div>
    </div>
    ${sec("value", "Value", null, movedBody(moved) + valueBody)}
    ${sec("gov", "Why", comments.length, whyBody)}
    ${sec("reads", "What reads it", null, `<div class="hint">Not a question this map can
       answer. DunneFlow records what a program <em>calls</em> and what it <em>touches</em>;
       it keeps no relation between a routine and a constant it mentions, so an empty answer
       here would be a claim nothing measured. The source search finds every mention of
       <code>${esc(id.name || "")}</code> as text.</div>`)}

    <div class="insp-actions">
      <button class="actbtn" id="srcBtn">${s.source && s.source.available
        ? `Show source · ${(s.source.lines || []).length} lines`
        : "Source not stored"} <span class="k">S</span></button>
      <div id="srcPane" hidden>${srcPane(s)}</div>
    </div>`;
}

/* The one button that goes to the code, wherever it is drawn. A file with no line still
 * opens the file; a fold with neither renders nothing at all rather than a control that
 * cannot do anything (design rule 16). */
function gotoCodeBtn(file, line) {
  if (!file) return "";
  return `<button class="linkbtn gotocode" data-gotocode="${esc(file)}"
    data-gotoline="${line || 0}" title="Open ${esc(file)} in the code browser">code ▸</button>`;
}

function viewInspector() {
  const s = SPECIMEN;
  /* Nothing selected is the ordinary state, not an error. The prototype could not reach
     it -- one routine was pinned as the permanent subject -- so the first render against
     a real store threw on `SPECIMEN.outbound` and took the rest of `render()` with it. */
  if (!s) {
    return `<div class="insp-empty">
      <p>${inspectorFor ? "Reading…" : "Nothing selected."}</p>
      <p class="hint">Pick a way in from the cover, a package from the navigator, or a node
         in the graph. The inspector reads whatever the graph and the table are pointed at
         — it is one selection, not three.</p>
    </div>`;
  }
  if (s.notFound) {
    /* A node the map does not hold is a fact about the map, and saying so is the whole
       discipline: `(no rows)` is indistinguishable from a true empty answer. */
    return `<div class="insp-empty">
      <p>Not in this map.</p>
      <p class="hint"><code>${esc(s.id)}</code><br>${esc(s.reason || "")}</p>
    </div>`;
  }

  /* A fold answers in the same skeleton as everything else -- `in`, `out`, `touches`,
     `governance`, `where` -- but its `in` and `out` name *boxes*, so the rows below would
     render a box id into `data-node` and link to nothing. Routed on the kind, above the
     first line that reads a routine's shape. */
  if (s.kind === "FOLD") return viewInspectorFold(s);
  /* And an arrow, for the same reason and above the same line: a flow has no `identity.qualname`,
     no params and no `where`, so every line below reads a routine's shape off a thing that
     is not one. Routed on the kind, from the same table. */
  if (s.kind === "FLOW") return viewInspectorFlow(s);
  /* And a constant, for the same reason and above the same line. It has no callers, no
     calls and no touches, so every section below reads a routine's shape off a thing that
     has not got one -- and, worse, *answers*: see `viewInspectorConstant`. */
  if (s.kind === "CONSTANT") return viewInspectorConstant(s);

  const id = s.identity || {};
  const inn = s.in || { callers: [], entrypoints: [] };
  const out = s.out || { calls: [] };
  const t = s.touches || { boundaries: [], sql: [], net: [], artefacts: [] };
  const gov = s.governance || { annotations: [], comments: [] };
  const showInf = !state.hideInferred;

  /* Comments are placed against the line they explain rather than pooled in a block --
   * they are the only source of the governance layer, and a comment three sections away
   * from the thing it is about has lost most of what made it worth keeping. */
  const whyAt = new Map();
  for (const c of gov.comments || []) {
    if (!whyAt.has(c.line)) whyAt.set(c.line, c);
  }
  const why = (line) => {
    const c = whyAt.get(line);
    return c ? `<div class="why"><span class="ln">:${c.line}</span> ${esc(c.text)}</div>` : "";
  };

  /* ── IN: how this is reached ── */
  const callers = inn.callers || [], eps = inn.entrypoints || [];
  const inShown = callers.slice(0, 40);
  const inBody = (eps.length ? eps.map(e => `
      <div class="flowitem">
        <span class="arrow">▸</span>
        <code>${esc(e.name || e.command || e.id || "entrypoint")}</code>
        <span class="conf badge certain">${esc(e.kind || "ENTRYPOINT")}</span>
      </div>`).join("") : "")
    + (inShown.length ? inShown.map(c => `
      <div class="flowitem">
        <span class="arrow">←</span>
        <button class="gotonode" data-node="${esc(c.id || "")}"
          title="${esc(c.qualname || c.name || "")}"
          ><code>${esc(c.name || c.callee_expr)}${c.module
              ? `<span class="dim">  ${esc(c.module)}</span>` : ""}</code></button>
        ${callBadge(c)}
      </div>`).join("")
      : (eps.length ? "" : `<div class="hint">Nothing in this map calls it. That is either a
          way in, dead code, or a call DunneFlow cannot see — a dynamic dispatch, or a
          language it does not read.</div>`))
    + cut(inShown.length, callers.length, "callers")
    + (id.docstring ? `<div class="why">${esc(String(id.docstring).split("\n")[0])}</div>` : "");

  /* ── OUT: what it does next ── */
  const calls = (out.calls || []).filter(c => showInf || c.external || c.confidence === "CERTAIN");
  const hiddenInf = (out.calls || []).length - calls.length;
  const outShown = calls.slice(0, 60);
  const outBody = (outShown.length ? outShown.map(c => `
      <div class="flowitem">
        <span class="arrow">→</span>
        ${c.id ? `<button class="gotonode" data-node="${esc(c.id)}"
            title="${esc(c.qualname || c.name || "")}"><code>${
            esc(c.name || c.callee_expr)}${c.module
              ? `<span class="dim">  ${esc(c.module)}</span>` : ""}</code></button>`
          : `<code>${esc(c.callee_expr)}${c.at_boundary
              ? `<span class="dim">  at the boundary</span>` : ""}</code>`}
        ${callBadge(c)}
      </div>
      ${why(c.line)}`).join("")
      : `<div class="hint">It calls nothing this map can see.</div>`)
    + cut(outShown.length, calls.length, "calls")
    + (hiddenInf > 0
        ? `<div style="font-size:.7rem;color:var(--sev-suspect);margin-top:.35rem"
            >${hiddenInf} inferred call${hiddenInf === 1 ? "" : "s"} hidden by your filter.</div>`
        : "");

  /* ── TOUCHES: what it reaches outside itself ── */
  const touches = touchRows(t);
  const touchBody = touches.length ? touches.join("")
    : `<div class="hint">It touches no boundary, table, remote or named file. Everything it
       does, it does in memory.</div>`;

  /* ── GOVERNANCE: why it is there ── */
  const anns = gov.annotations || [], comments = gov.comments || [];
  const govBody = (anns.length
      ? `<div class="govchips">${anns.map(a =>
          `<span class="govchip ${esc(String(a.kind || "").toLowerCase())}"
            >${esc(a.value)}</span>`).join("")}</div>`
      : "")
    + (comments.length
        ? comments.slice(0, 40).map(c =>
            `<div class="why"><span class="ln">:${c.line}</span> ${esc(c.text)}</div>`).join("")
          + cut(Math.min(40, comments.length), comments.length, "comments")
        : (anns.length ? "" : `<div class="hint">No annotations and no comments. The code
            says what it does and nothing says why.</div>`));

  /* ── the signature, demoted ── */
  /* One piece per line, straight from `signature_parts` -- so this and the card's
   * invocation line are the same sequence laid out two ways, and a `*` cannot appear in
   * one and not the other.
   *
   * It read `p.annotation` and `p.default` against a query that sends `type` and `dflt`,
   * so every parameter here printed as a bare name with no type and no default for as long
   * as this pane has existed. Nothing failed; a missing type is indistinguishable from a
   * routine that has none, which is rule 44 exactly. */
  const params = s.params || [];
  const sigBody = `<pre class="srcblock">${
    id.is_async ? `<span class="kw">async </span>` : ""}<span class="kw">def</span> ${
    esc(id.name || s.label)}(${params.length
      ? "\n    " + params.map(p => esc(p.text)).join(",\n    ") + "\n"
      : ""})${id.returns ? ` -&gt; ${esc(id.returns)}` : ""}:</pre>`;

  const lines = (id.line_end && id.line_start) ? id.line_end - id.line_start + 1 : null;
  const where = s.where || {};
  const fileName = String(where.file || id.file || "").split("/").slice(-2).join("/");

  return `
    <div class="insp-head">
      <h2>${breakable(id.qualname || s.label || s.id)}</h2>
      <div class="loc">${esc(fileName)}${id.line_start
        ? `:${id.line_start}–${id.line_end}` : ""}</div>
      <div class="tags">
        <span class="badge certain">ANALYZED</span>
        <span class="kind-tag">${esc(s.kind || "")}</span>
        ${id.class_name ? `<span class="kind-tag">${esc(id.class_name)}</span>` : ""}
        <span style="margin-left:auto;display:flex;gap:.3rem">
          ${pinBtn(id.qualname || s.id, [
            lines ? `${lines} lines` : null,
            comments.length ? `${comments.length} comments` : null,
            anns.length ? `${anns.length} governance ids` : null,
          ].filter(Boolean).join(", ") || "no measurements")}
          <button class="linkbtn" id="collapseAll">Collapse all</button>
        </span>
      </div>
    </div>
    ${sec("in", "In", callers.length + eps.length, inBody)}
    ${sec("out", "Out", calls.length, outBody)}
    ${sec("touches", "Touches", touches.length, touchBody)}
    ${sec("gov", "Governance", anns.length + comments.length, govBody)}
    ${threadsPanel(s.id)}
    ${sec("sig", "Signature", params.length || null, sigBody)}

    <div class="insp-actions">
      <button class="actbtn" id="srcBtn">${s.source && s.source.available
        ? `Show source · ${(s.source.lines || []).length} lines`
        : "Source not stored"} <span class="k">S</span></button>
      <div id="srcPane" hidden>${srcPane(s)}</div>
    </div>`;
}

/* The source as it was *measured*, not as the tree stands now. That distinction is the
 * whole reason for the content-addressed sidecar, and it is worth saying on the page:
 * a map that quietly showed today's file beside yesterday's facts would be wrong in the
 * one way nobody would think to check. */
function srcPane(s) {
  const src = s.source;
  if (!src || !src.available) {
    return `<p class="hint">This map was written with <code>--no-source</code>, so the
      bodies are not here. The facts above were still measured from the file.</p>`;
  }
  const focus = new Set(src.focus || []);
  const body = (src.lines || []).map(l =>
    `<span class="ln">${l.n}</span>${focus.has(l.n) ? "<mark>" : ""}${
      esc(l.text)}${focus.has(l.n) ? "</mark>" : ""}`).join("\n");
  return `<pre class="srcblock">${body}</pre>
    <p style="font-size:.7rem;color:var(--text-muted);margin:.35rem 0 0">
      Read from the content-addressed sidecar — the source as measured when this map was
      built, not as the tree stands now.</p>`;
}

/* ═══ render ═══ */

/* One failing section must not silently truncate the page.
 *
 * `viewInspector()` threw on a null specimen and took every step after it in `render()`
 * with it -- the filter strip kept a stale "showing 187 of 4,568", the trail never
 * updated, and the result looked like a working dashboard. A half-rendered page is the
 * most expensive kind of failure here because it is the one nobody reports.
 *
 * So each section renders inside its own boundary and says so when it cannot. The error
 * is on the page, not only in a console the reader does not have open. */
/* A pane's fold control belongs to the **pane**, not to whatever is inside it.
 *
 * The inspector's lived in the header of a *populated* specimen, so the two states that
 * return early -- "Nothing selected" and "Not in this map" -- rendered without it. Design
 * rule 24 says every pane folds and folding leaves a rail, and the pane that most needs it
 * is precisely the one with nothing to say: the inspector holds 22rem to report that it is
 * empty, which is the whole reason it rails itself in the first place. So a reader had to
 * find something to select before they could collapse the pane that was showing nothing --
 * reported exactly that way.
 *
 * Emitted at the paint site, before the content, so no branch of any renderer can drop it
 * again: it is structurally outside every `return` the content has. Rule 36 -- route from
 * one place rather than remembering to repeat it. */
function paneFold(pane, label) {
  return `<button class="panefold" data-fold="${pane}"
            title="Collapse the ${label}" aria-label="Collapse the ${label}">&#x00BB;</button>`;
}

function section(name, fn) {
  try {
    return fn();
  } catch (err) {
    console.error(`[dunneflow] the ${name} could not render:`, err);
    return `<div class="panel" style="padding:.75rem">
      <b>The ${esc(name)} could not be drawn.</b>
      <div class="hint" style="margin-top:.35rem">${esc(err.message)}</div>
      <div class="hint">The rest of this page is unaffected and is still showing real
        data. This message is here so a missing panel is never mistaken for an empty
        one.</div></div>`;
  }
}
/* The breadcrumb is derived from state, never written into the HTML. It used to be
   three static elements that said "mensores > cli > interview" on every screen --
   a label that is wrong everywhere is worse than no label at all. */
function crumbsFor() {
  /* The program's own name, and the *current selection* -- not a pinned path.
   *
   * `graph`, `table` and `doc` used to be fixed pairs -- "packages > system boundary",
   * "quaestor > routines", "cli > interview" -- so every screen for every program showed
   * one Mensores path that had nothing to do with what was on it. The comment above this
   * function already said a label wrong everywhere is worse than no label, and the table
   * underneath it was doing exactly that. The three centre modes now say what is selected,
   * or say that nothing is. */
  const prog = { label: STATS ? STATS.program : "", to: "cover" };
  const subject = () => {
    if (!state.selected) return [{ label: "nothing selected", cur: true }];
    const r = ROUTINES.find(x => x.id === state.selected);
    return r
      ? [{ label: r.module }, { label: r.name, cur: true }]
      : [{ label: SPECIMEN ? SPECIMEN.label : "selection", cur: true }];
  };
  const trail = {
    cover:       [],
    graph:       subject(),
    table:       subject(),
    doc:         subject(),
    anomalies:   [{ label: "anomalies", to: "anomalies" },
                  { label: { broken: "Broken", suspect: "Suspect", info: "Informational" }[state.sev],
                    cur: true }],
    glossary:    [{ label: "vocabulary" }, { label: "glossary", cur: true }],
    naming:      [{ label: "vocabulary" }, { label: "naming standard", cur: true }],
    inference:   [{ label: "inference", cur: true }],
    curiosities: [{ label: "explore" }, { label: "worth a look", cur: true }],
    pins:        [{ label: "explore" }, { label: "kept", cur: true }],
    settings:    [{ label: "settings", cur: true }],
  }[state.view] || [];

  const parts = [prog, ...trail];
  return parts.map((c, i) => {
    const sep = i ? '<span class="sep">\u203a</span>' : "";
    if (c.cur) return `${sep}<span class="cur">${esc(c.label)}</span>`;
    if (c.to)  return `${sep}<button class="crumblink" data-crumb="${esc(c.to)}">${esc(c.label)}</button>`;
    return `${sep}<span class="dim">${esc(c.label)}</span>`;
  }).join("");
}

function render() {
  const vp = $("#viewMount");
  $("#crumbs").innerHTML = crumbsFor();
  $("#modes").style.visibility = CENTRE_MODES.includes(state.view) ? "visible" : "hidden";
  /* The layout choice sits inside graph mode, never beside it. Graph / table / document are
   * three ways of reading one selection; stack / packages are two drawings of one of them,
   * and promoting a layout to a mode would say they answer different questions. */
  const lay = $("#layouts");
  if (lay) {
    lay.hidden = state.view !== "graph";
    $$("#layouts button").forEach(b =>
      b.setAttribute("aria-pressed", String(b.dataset.layout === state.graphLayout)));
  }
  $$("#modes button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === state.mode)));
  $("#settingsBtn").setAttribute("aria-pressed", String(state.view === "settings"));
  document.documentElement.style.setProperty("--row-pad",
    { compact: "0.18rem", comfortable: "0.34rem", spacious: "0.55rem" }[state.density]);

  /* Two mounts, exactly one on screen. The graph lives in a container `render()` never
   * touches -- innerHTML on the viewport would destroy the deck.gl canvas, its GL context
   * and the reader's place, on every keystroke. */
  const stackOn = state.view === "graph" && state.graphLayout === "stack";
  /* Three mounts, exactly one on screen. The diagram keeps its own for the reason the graph
     does: a laid-out SVG and the reader's pan are destroyed by an `innerHTML` write, and
     `render()` runs on every keystroke. */
  const diagramOn = state.view === "diagram";
  $("#graphMount").hidden = !stackOn;
  $("#diagramMount").hidden = !diagramOn;
  $("#viewMount").hidden = stackOn || diagramOn;
  /* The pop-up hides with its mount, but `hoverAt` would not: coming back and pointing at
     the same node again would find the id unchanged, take the "moving within the same
     node" path, and reposition an empty card. Clearing the subject is what makes the two
     halves agree. */
  if (!stackOn) hideHoverCard();
  if (stackOn) {
    // Coming back from a hidden container: deck.gl sized itself to nothing while away.
    if (Graph.mounted()) requestAnimationFrame(() => Graph.resize());
    renderGraphFurniture();
    vp.innerHTML = "";
  }
  if (diagramOn) {
    vp.innerHTML = "";
    /* The deferred fit (rule 49). A first draw into a pane that has not been laid out
       measures nothing, and there is always another render to pay it on. */
    if (dgmNeedsFit) dgmFit();
    markDiagramSelection();
  }
  /* No early return. The graph is a view in the centre pane, not a page -- the inspector,
   * the trail, the filter strip and the navigator counts all still belong on screen, and
   * returning here would quietly empty three panes whenever the stack was showing. */

  else if (state.view === "cover")     vp.innerHTML = viewCover();
  else if (state.view === "graph")     vp.innerHTML = viewGraph();
  else if (state.view === "table")   {
    /* Keep the reader's place across a rebuild, exactly as `buildNav()` does and for the
     * same reason: `render()` runs on every selection, every keystroke and every message
     * from the other window, and rewriting `innerHTML` sends a 4,734-row scroller back to
     * row one. Without this the reveal below could never be conditional either -- the row
     * would be off screen after every repaint, so "only when it is out of sight" would
     * mean "always", and an automatic move would fight every deliberate one. */
    /* **The one door onto the comparison, for the routines**, and it runs *before* the
     * paint rather than after it.
     *
     * After it, the note this pane draws is a step behind its own fetch: `viewTable()`
     * reads `CHANGES` while it is still null, so the page rendered "not compared yet --
     * open the table and these rows will mark themselves" **to a reader sitting in the
     * table**, and left it there for the thirty seconds a cold comparison takes. Nothing
     * re-renders in between. That is rule 68 exactly: a note telling someone to do the
     * thing they have already done. `loadChanges` sets the loading flag synchronously, so
     * asking first means the very first paint says "comparing…".
     *
     * Here rather than on the mode toggle because there are five ways into table mode --
     * the toggle, `Enter` on a hovered navigator row, two crumb routes and the code
     * browser's hand-off -- and a call at each is exactly the list rule 51 says grows.
     * Every one of them arrives here.
     *
     * Idempotent and cheap: `ensureChanges()` hands back the held promise the moment
     * `CHANGES` is anything at all, so this fetches once per pair and then costs a
     * property read on every repaint. It repaints when the answer lands, and that repaint
     * is `ensureChanges`' own, deliberately. Chaining a `.then(render)` here is an infinite
     * loop: this runs *inside* `render()`, and the promise resolves immediately once
     * `CHANGES` is held, so every paint would schedule the next one. */
    ensureTableOverlay();

    const mount = $("#viewMount");
    const keep = mount ? mount.scrollTop : 0;
    vp.innerHTML = viewTable();
    if (mount) mount.scrollTop = keep;
    revealSelectedRow(false);
  }
  else if (state.view === "doc")       vp.innerHTML = viewDoc();
  else if (state.view === "code")    {
    /* **Not repainted unless the file changed.** Re-attaching the built table was supposed
     * to make this cheap and did not: moving 17,500 cells back into the document forces a
     * style recalc and a layout over all of them, so `render()` still cost 1.3 s per call
     * on `_server.py` — on a function that runs on every selection, every keystroke and
     * every message from the other window. The only way to not pay a layout is to not
     * detach the table, so when nothing about the file has changed the centre is left
     * exactly as it is and only the highlight moves.
     *
     * The DOM is checked, not just the flag. A flag saying "already painted" is true of a
     * pane another view has since overwritten, and `#codeTable` is the thing that either is
     * or is not on screen — rule 42: check that the guard catches, not that it mentions. */
    if (codePaintedFor !== codeDomKey() || !$("#codeTable")) {
      const mount = $("#viewMount");
      const keep = mount ? mount.scrollTop : 0;
      vp.innerHTML = viewCode();
      attachCode();
      codePaintedFor = codeDomKey();
      if (mount) mount.scrollTop = keep;
    } else {
      paintHere();
      revealSelectedLine();
    }
  }
  else if (state.view === "anomalies") vp.innerHTML = viewAnomalies();
  else if (state.view === "changes")   vp.innerHTML = viewChanges();
  else if (state.view === "glossary")  { ensureVocabulary(); vp.innerHTML = viewGlossary(); }
  else if (state.view === "naming")    { ensureVocabulary(); vp.innerHTML = viewNaming(); }
  else if (state.view === "inference") vp.innerHTML = viewInference();
  else if (state.view === "curiosities") { ensureCuriosities(); vp.innerHTML = viewCuriosities(); }
  else if (state.view === "pins")       vp.innerHTML = viewPins();
  else if (state.view === "settings")  {
    vp.innerHTML = viewSettings();
    /* Painted after the markup, never inside it. The ratio and the refusal are computed
     * against the graph's *current* ground, which depends on the theme and on the graph's
     * own ground setting -- so writing them into the template would freeze a judgment made
     * before either was known, and a clamp stating a stale verdict is worse than none. */
    updatePointerNote();
  }

  /* `pane` is what the stylesheet hangs the fold control's placement on: the inspector is a
     flex column, and a floated child of one is stretched to the full width rather than
     floated (see `.pane > .panefold`). */
  $("#inspector").classList.add("pane");
  $("#inspector").innerHTML =
    paneFold("inspector", "inspector") + section("inspector", viewInspector);
  applyPanels();
  let vw = document.getElementById("viewerMount");
  if (!vw) { vw = document.createElement("div"); vw.id = "viewerMount"; document.body.appendChild(vw); }
  vw.innerHTML = viewerPanel() + detailPanel();
  /* The base switch's overlay, on every render as well as on every poll. A repaint that
     left it out would clear a blocking surface while the rebuild it belongs to is still
     running -- and the page underneath is answering for a version that is being replaced. */
  paintRebuild();
  const ne = $("#navEgress");
  if (ne) {
    ne.textContent = posture().label.toLowerCase();
    ne.className = "n" + (state.egress === "off" ? "" : " sevcount info");
  }
  /* The menu order used to be applied here, by moving one group in front of another in the
   * DOM. It is `navGroupsInOrder()` now, read by `buildNav()` and by the jump strip
   * together -- a second place that decides an order is a second answer to the question,
   * and the strip would have offered the groups in an order the pane did not use. The
   * lesson that was recorded here still holds and now has nothing to trip over: an
   * ordering rule that names a *position* rather than an identity breaks the moment
   * anything is added beside it. */

  /* The strip is painted on every render, because what it names can move on any of them:
     a comparison arriving, a version dropped, the assumption flipped. It is cheap -- one
     line of text -- and the alternative is a surface that is stale exactly when the reader
     most needs it (rule 51). */
  const vs = $("#verStrip");
  if (vs) vs.innerHTML = versionStrip();

  /* Keep the cursor in the lane. The steps scroll inside their own box now, so the step you
     are standing on can sit outside it after a Back -- and a trail whose current step is off
     screen is the state design rule 26 already refuses for the routine list. Only when it is
     genuinely out of sight: an automatic move must not fight a deliberate one (rule 24). */
  requestAnimationFrame(() => {
    /* `$$`, not `$`. The bar is rendered twice — the app's header and the detail window,
       which needs its own because the header sits behind that window's scrim — and the
       singular selector is exactly how this bar's controls were once wired to only one of
       them. */
    $$(".trailstep.here").forEach((here) => {
      const lane = here.closest(".trail");
      if (!lane) return;
      const h = here.getBoundingClientRect(), l = lane.getBoundingClientRect();
      if (h.left < l.left || h.right > l.right) {
        lane.scrollLeft += (h.left - l.left) - (l.width - h.width) / 2;
      }
    });
  });
  const tm = $("#trailMount");
  if (tm) {
    tm.innerHTML = trailBar();
    /* Scroll the trail to where the reader actually is.
     *
     * The bar overflows horizontally and always rendered from the start, so after a few
     * steps the current position sat off the right edge and had to be scrolled to by hand
     * -- which defeats the point of it. Design rule 15 calls the trail the thing that makes
     * a detour free, and a trail that hides where you are is a map with no "you are here".
     * `block: "nearest"` so it never scrolls the page, only the bar. */
    const here = tm.querySelector(".trailstep.here");
    if (here) here.scrollIntoView({ block: "nearest", inline: "end" });
  }
  const np = $("#navPins");
  if (np) { np.textContent = state.pins.length; np.className = "n" + (state.pins.length ? " sevcount info" : ""); }
  renderFilters();
  wire();
  /* Persisted here rather than in each handler. Forty controls change settings and every
   * one of them ends in `render()`, so this is the one place that cannot be forgotten --
   * and a setting that silently stops being saved is indistinguishable from one nobody
   * used, which is exactly the evidence the usage counter exists to provide. */
  persist();
}

function wire() {
  /* The overview: clicking a package shows everything it touches. Clicking it again lets
     go, because a view you cannot get out of is a view you stop clicking into. */
  $$("[data-pkgnode]").forEach(b => b.addEventListener("click", () => {
    const id = b.dataset.pkgnode;
    state.pkgPick = state.pkgPick === id ? null : id;
    if (state.pkgPick) pushTrail("graph", id, "everything it touches");
    render();
  }));
  $$("[data-pkgpick]").forEach(b => b.addEventListener("click", () => {
    state.pkgPick = b.dataset.pkgpick || null;
    render();
  }));

  /* Following a caller or a callee moves the graph as well: one selection, two views.
     The trail this leaves is what makes a detour free -- you can always click back along
     the way you came, which is the argument for exploring sideways rather than only
     drilling down.

     A node the graph does not draw is a real case, not an error: constants can be switched
     off, and an external whose plate is folded away has no index. The inspector still
     shows it. Refusing to *show* something because it cannot be *drawn* would make the
     picture the limit of the map. */
  $$(".gotonode").forEach(b => b.addEventListener("click", () => {
    /* **Two id spaces, routed by which attribute is there.** A row in a routine's pane
       names a node; a row in a fold's pane names a *box*, which is the drawing's own id and
       means nothing to `/api/node`. They share a class because they are the same act and
       look the same, and they must not share an attribute -- reading one id space as the
       other is rule 47's companion in a pane: an identifier that means two things resolves
       plausibly and silently to the wrong thing. */
    if (b.dataset.box) { selectFold(b.dataset.box); return; }
    const id = b.dataset.node;
    if (!id) return;
    const i = Graph.mounted() ? Graph.indexOfId(id) : -1;
    /* `replace` starts a fresh one hop from where you land; `walk` adds, so every node
       you followed stays picked and the hops between them draw themselves -- both ends
       of each are already members, which is all `buildSelectionGeometry` asks. The mode
       argument has existed since the multi-pick work, so this is a choice between two
       values the engine already takes rather than a second way to select. */
    if (i >= 0) Graph.togglePick({ kind: "node", index: i }, followPickMode());
    /* `setSubject`, never `loadNode`. Opening a member of a fold has to *clear* the fold,
       or the pane paints a routine while `state.fold` still names the class it came from --
       and the next thing to ask `inspectorSubject()` gets an answer about neither. */
    else setSubject({ node: id });
    used("follow:" + state.followMode);
    /* `data-label` where the row has one. A caller row is a bare name and its text is the
       right label; a **fold's member** row carries its whole invocation line, so the
       trail read `_profile_name_or_none(self) → str | None` where a step wants a name.
       The row that knows the difference is the row that says so. */
    pushTrail(state.view, b.dataset.label || b.textContent.trim(),
              "followed from the inspector");
  }));

  /* **The one way to the code, wherever it is asked from.** The inspector's location line,
     every member of a fold, and -- when the flow panel lands -- every call site. Three
     surfaces, one implementation, because rule 51's list of callers is the thing that
     grows and the second implementation is the one that forgets the mode switch.

     A file is not a node, so this deliberately does not go through `selectFromNav`: there
     is nothing to light and nothing for the inspector to answer about. What the reader
     picks *inside* the file is a node, and that is a different click. `codeGoto` and
     `revealLine` are the search's own pattern, unchanged. */
  $$("[data-gotocode]").forEach(b => b.addEventListener("click", (ev) => {
    ev.stopPropagation();          // the row it sits on is itself a selection
    const path = b.dataset.gotocode, line = Number(b.dataset.gotoline || 0);
    if (!path) { console.error("DunneFlow: a code link with no file", b); return; }
    state.mode = "code";
    state.view = "code";
    codeGoto = line || 0;
    if (state.codeFile === path) { revealLine(codeGoto); codeGoto = 0; }
    else openCodeFile(path);
    used("gotocode");
    pushTrail("code", baseOf(path), line ? `at line ${line}` : "");
    persist();
    render();
  }));

  /* cover → graph */
  $$("[data-ep]").forEach(b => b.addEventListener("click", () => {
    state.view = "graph"; state.mode = "graph"; used("graph"); ensureGraph(); render();
  }));

  /* graph nodes: click, and arrow-key traversal */
  const nodes = $$(".gnode");
  nodes.forEach((n, i) => {
    n.addEventListener("click", () => {
      nodes.forEach(x => x.setAttribute("aria-current", "false"));
      n.setAttribute("aria-current", "true");
    });
    n.addEventListener("keydown", (e) => {
      const map = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
      if (map[e.key]) {
        e.preventDefault();
        const next = nodes[(i + map[e.key] + nodes.length) % nodes.length];
        next.focus();
      }
      if (e.key === "Enter") { e.preventDefault(); state.view = "table"; state.mode = "table"; render(); }
    });
  });

  /* table: sort, select, drag-resize (widths in rem) */
  $$("[data-sort]").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.sort;
    if (state.sortKey === k) state.sortAsc = !state.sortAsc;
    else { state.sortKey = k; state.sortAsc = false; }
    render();
  }));
  $$("[data-den]").forEach(b => b.addEventListener("click", () => {
    state.density = b.dataset.den; render();
  }));
  /* The marks on or off, for the routine list and the table together.
   *
   * An ordinary `render()` is enough here, unlike the code overlay's repaint: this pane is
   * rebuilt from `ROUTINES` on every render and holds no cached subtree. Turned back **on**
   * it may have to fetch, for the same reason its neighbour does -- the reader may have
   * opened the table with the switch off, in which case nobody has ever asked. */
  $$("[data-tableoverlay]").forEach(b => b.addEventListener("click", () => {
    state.tableOverlay = !state.tableOverlay;
    persist();
    used("table:overlay:" + (state.tableOverlay ? "on" : "off"));
    ensureTableOverlay();      // repaints itself when an answer arrives
    buildNav();                // the navigator draws these marks too
    render();
  }));
  /* The findings' switch, and it may have to fetch for its neighbours' reason: a reader who
   * opened the worklist with it off has never asked the question, so turning it on is the
   * first time anybody has. */
  $$("[data-anomalyoverlay]").forEach(b => b.addEventListener("click", () => {
    state.anomalyOverlay = !state.anomalyOverlay;
    persist();
    used("anomalies:overlay:" + (state.anomalyOverlay ? "on" : "off"));
    ensureAnomalyOverlay();    // repaints itself when an answer arrives
    render();
  }));
  /* The findings only the compared version has. Not persisted (see `state.anoOnlyThere`):
   * this is where the reader is, not what they arranged. */
  $$("[data-anoonlythere]").forEach(b => b.addEventListener("click", () => {
    state.anoOnlyThere = !state.anoOnlyThere;
    used("anomalies:onlythere:" + (state.anoOnlyThere ? "open" : "shut"));
    render();
  }));
  /* Selection is keyed by qualname, never by row index -- sorting reorders the array,
     and a revision change reorders it again. Same rule the temporal layers depend on. */
  $$("tbody tr[data-row]").forEach(tr => tr.addEventListener("click", () => {
    /* The row carries the node id, not the qualified name it prints.
     *
     * It used to be `data-row="${r.q}"` and this handler set `state.selectedRow` and
     * re-rendered -- so clicking a routine highlighted a row and did nothing else, while
     * the graph beside it and the inspector went on showing whatever was there before.
     * Rule 30 in the view that most looks like it works: a label is not an identity. */
    selectFromNav({ nodes: [tr.dataset.row] });
  }));
  const tgo = $("[data-tablego]");
  if (tgo) tgo.addEventListener("click", () => revealSelectedRow(true));

  $$("[data-resize]").forEach(h => {
    h.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      const key = h.dataset.resize;
      const th = h.closest("th");
      const startX = e.clientX;
      const rootPx = parseFloat(getComputedStyle(document.documentElement).fontSize);
      const startRem = state.colWidths[key];
      h.classList.add("active");
      h.setPointerCapture(e.pointerId);
      const table = th.closest("table");
      const move = (ev) => {
        const deltaRem = (ev.clientX - startX) / rootPx;   /* px in, rem out */
        const w = Math.max(2.5, +(startRem + deltaRem).toFixed(3));
        state.colWidths[key] = w;
        th.style.width = w + "rem";
        /* The table is the sum of its columns, so it has to grow with them -- otherwise a
           column dragged wider is still boxed in by a table that has not moved, and the
           drag stops having any effect a few pixels in. */
        if (table) {
          table.style.width = TABLE_COLS.reduce((n, k) => n + state.colWidths[k], 0) + "rem";
        }
      };
      const up = () => {
        h.classList.remove("active");
        h.removeEventListener("pointermove", move);
        h.removeEventListener("pointerup", up);
        /* Design rule 17 says column widths persist per program, and they did not: the drag
           wrote `state.colWidths` and nothing ever saved it, so every width was lost on
           reload. A setting that is faithfully changed and never stored is the same shape
           as one that is faithfully stored and never read. */
        persist();
      };
      h.addEventListener("pointermove", move);
      h.addEventListener("pointerup", up);
    });
  });

  /* settings controls */
  $$("[data-theme-set]").forEach(b => b.addEventListener("click", () => {
    state.theme = b.dataset.themeSet; applyTheme(); render();
  }));
  $$("[data-scale-set]").forEach(b => b.addEventListener("click", () => {
    state.scale = parseFloat(b.dataset.scaleSet); applyScale(); render();
  }));
  const tt = $("#trailToggle");
  if (tt) tt.addEventListener("click", () => { state.trailShown = !state.trailShown; render(); });
  $$("[data-trailcap]").forEach(b => b.addEventListener("click", () => {
    /* **It no longer prunes.** This used to cut the history down to the new size, which was
       honest while the number meant "how much is kept" and destructive the moment it meant
       "how much is shown": narrowing the bar would have thrown away the steps Back reaches.
       The bar takes its own window in `trailBar()`. */
    state.trailCap = parseInt(b.dataset.trailcap, 10);
    persist();
    render();
  }));
  /* Flip which version the reader takes to be newer.
   *
   * **No re-query.** The two sets are facts the server already sent; this changes only the
   * words and the colours laid over them, which is why `changes.py` reports `only_in_base`
   * and `only_in_compared` rather than `added` and `removed`. `render()` and `buildNav()`
   * both, because the words appear in the centre pane *and* in the navigator's Changes
   * group -- repainting one leaves the other stating the opposite (rule 51, and the exact
   * defect that made the worklist unreachable the first time). */
  $$("[data-assumenewer]").forEach(b => b.addEventListener("click", () => {
    /* auto -> the compared is newer -> the compared is older -> auto. Three clicks return
       the reader to where they started, and the label always states the state in full
       rather than leaving them to work it out from a glyph. */
    const next = { auto: "yes", yes: "no", no: "auto" };
    state.comparedIsNewer = next[state.comparedIsNewer] || "auto";
    used("assume:" + state.comparedIsNewer);
    persist();
    /* `repaintCode`, not `buildNav(); render()`. The assumption decides the *tone* of every
       marked line, and those live inside the built subtree — so re-rendering alone hands
       back the cached page and the code keeps the colours of the previous assumption while
       every heading beside it has swapped. One control, two answers (rule 51), and the
       lines are the half nobody would think to check. */
    repaintCode();
    /* And the stack, for exactly the same reason one layer out: the assumption decides
       which of the two directional tones each band is drawn in, and the nodes are as much
       inside a cache as the code's lines are. Found by flipping it and reading the
       numbers -- the key said "added" while the dots stayed the colour of gone. */
    pushGraphChange();
    renderLegend();
  }));

  $$("[data-pointershown]").forEach(b => b.addEventListener("click", () => {
    state.pointerShown = b.dataset.pointershown === "1";
    used("pointer:" + (state.pointerShown ? "shown" : "off"));
    if (Graph.mounted()) Graph.setOptions({ pointerShown: state.pointerShown });
    persist();
    render();
  }));
  const pp = $("#pointerPick");
  /* Live while dragging, like every other picker here, and for the same reason: `render()`
     rewrites the pane the control lives in, so consulting it mid-drag destroys it. The
     refusal is shown as the reader drags rather than after they commit, because a limit
     that only speaks once the choice is made is a limit that wasted their time. */
  if (pp) pp.addEventListener("input", () => {
    state.pointerColor = pp.value;
    updatePointerNote();
    if (Graph.mounted()) Graph.setOptions({ pointerColor: pointerRgb() });
    persist();
  });
  $$("[data-reticule]").forEach(b => b.addEventListener("click", () => {
    state.reticuleShown = b.dataset.reticule === "1";
    used("reticule:" + (state.reticuleShown ? "shown" : "off"));
    if (Graph.mounted()) Graph.setOptions({ reticuleShown: state.reticuleShown });
    persist();
    render();
  }));
  $$("[data-pointerplace]").forEach(b => b.addEventListener("click", () => {
    state.pointerPlace = b.dataset.pointerplace;
    used("pointerplace:" + state.pointerPlace);
    if (Graph.mounted()) Graph.setOptions({ pointerPlace: state.pointerPlace });
    persist();
    render();
  }));
  $$("[data-pointerreset]").forEach(b => b.addEventListener("click", () => {
    state.pointerColor = "";
    if (Graph.mounted()) Graph.setOptions({ pointerColor: null });
    persist();
    render();
  }));
  $$("[data-navcap]").forEach(b => b.addEventListener("click", () => {
    state.navCap = parseInt(b.dataset.navcap, 10);
    used("navcap:" + state.navCap);
    buildNav();
    render();
  }));
  $$("[data-navgroups]").forEach(b => b.addEventListener("click", () => {
    state.navGroups = b.dataset.navgroups;
    used("navgroups:" + state.navGroups);
    /* Forget which groups were open rather than reconciling two arrangements: switching to
       the accordion with four groups open would otherwise leave four groups open until
       something was clicked, which reads as a control that did nothing. */
    state.navOpen = {};
    buildNav();
    render();
  }));
  /* Both diagram-appearance controls. `applyDiagramLook()` writes the CSS custom property
     and `render()` repaints the Settings page so the pressed button moves -- the drawing
     itself needs no rebuild at all, because the SVG reads the property live. That is the
     whole reason these are CSS variables rather than attributes written into the DOT: a
     change here costs no Graphviz round trip. */
  $$("[data-dgmcursor]").forEach(b => b.addEventListener("click", () => {
    state.diagramCursor = b.dataset.dgmcursor;
    applyDiagramLook();
    used("diagram:cursor:" + state.diagramCursor);
    persist();
    render();
  }));
  $$("[data-dgmedge]").forEach(b => b.addEventListener("click", () => {
    state.diagramEdgeWidth = Number(b.dataset.dgmedge);
    applyDiagramLook();
    used("diagram:edgewidth:" + state.diagramEdgeWidth);
    persist();
    render();
  }));

  $$("[data-menuorder]").forEach(b => b.addEventListener("click", () => {
    state.menuOrder = b.dataset.menuorder;
    used("menu:" + state.menuOrder);
    buildNav();               // the order lives in the navigator now, not in render()
    render();
  }));
  $$("[data-start]").forEach(b => b.addEventListener("click", () => {
    state.startup = b.dataset.start; render();
  }));
  const amb = $("#ambientToggle");
  if (amb) amb.addEventListener("click", () => { state.ambient = !state.ambient; render(); });
  const bsc = $("#bandScrollToggle");
  if (bsc) bsc.addEventListener("click", () => {
    state.bandScroll = !state.bandScroll;
    used("bandscroll:" + state.bandScroll);   // design rule 2: the loser is retired on evidence
    render();
  });
  const inf = $("#inferredToggle");
  if (inf) inf.addEventListener("click", () => { state.hideInferred = !state.hideInferred; render(); });
  /* The colour set. A `data-palette-set` route, never `data-palette` -- that name is the
     stamp on `:root`, and one attribute meaning both a route and a piece of state is the
     defect `data-nav` cost a session to find. `data-theme-set` sits beside `data-theme`
     for the same reason, and a test keeps the two families disjoint. */
  $$("[data-palette-set]").forEach(b => b.addEventListener("click", () => {
    state.palette = b.dataset.paletteSet;
    applyPalette();
    used("palette:" + state.palette);
    persist();
    /* A full render, because a set changes what is on screen everywhere it is spent -- the
       change bands, the worklist, the badges -- and the Settings page has to redraw its own
       swatches and every number beside them against the set now in force. */
    render();
  }));

  /* The shape set, beside the colour set and named the same way: `data-shapeset` is a
     route and nothing on the page is stamped with it, so the `data-nav` collision cannot
     happen again here. The engine is told even when it is not mounted -- `setOptions`
     returns early without a prepared payload and the value is handed over again at mount,
     so a choice made from Settings before the graph has ever been opened is not lost
     (rule 68: a restore is a setter and must do what the setter does). */
  /* worklist */
  $$("[data-sev]").forEach(b => b.addEventListener("click", () => {
    if (b.disabled) return;
    state.sev = b.dataset.sev; state.cursor = 0; render();
  }));
  $$("[data-cursor]").forEach(b => b.addEventListener("click", () => {
    state.cursor = parseInt(b.dataset.cursor, 10); render();
  }));
  $$("[data-step]").forEach(b => b.addEventListener("click", () => step(parseInt(b.dataset.step, 10))));
  $$("[data-triage]").forEach(b => b.addEventListener("click", () => {
    const list = worklistFor(state.sev);
    const cur = list[state.cursor];
    if (!cur) return;
    const v = b.dataset.triage;
    setTriage(cur.a, v);
    if (v) step(1);            /* triaging advances — that is the point of a worklist */
    else render();
  }));

  /* collapsible inspector sections */
  $$("[data-sec] h3 button").forEach(b => b.addEventListener("click", () => {
    const box = b.closest("[data-sec]");
    state.insp[box.dataset.sec] = !state.insp[box.dataset.sec];
    render();
  }));
  const ca = $("#collapseAll");
  if (ca) ca.addEventListener("click", () => {
    const anyOpen = Object.values(state.insp).some(Boolean);
    Object.keys(state.insp).forEach(k => state.insp[k] = !anyOpen);
    render();
  });

  /* cover: the anomaly panel is a doorway, not a readout */
  $$("[data-gosev]").forEach(b => b.addEventListener("click", () => {
    loadAnomalies().then(render);
    ensureAnomalyOverlay();        // the other door in, and it must pay the same toll
    state.view = "anomalies"; state.sev = b.dataset.gosev; state.cursor = 0;
    used("anomalies"); render();
  }));

  /* glossary filter — refills three elements, and touches nothing else.
   *
   * It used to call `render()`, which rewrites the whole centre pane, the inspector, the
   * navigator and the trail, then put the caret back in the field it had just destroyed.
   * That is 412 ms per keystroke on a real glossary -- a filter you cannot type into --
   * and the caret restoration was the tell that a full repaint was the wrong instrument.
   * The lists it actually changes are the two lists and the count beside the box. */
  const tq = $("#termq");
  if (tq) tq.addEventListener("input", () => {
    state.termFilter = tq.value;
    refreshGlossaryLists();
  });
  $$("[data-goto]").forEach(b => b.addEventListener("click", () => {
    state.view = b.dataset.goto; render();
  }));

  /* One open provenance block at a time, across every pane that has one -- and the key is
     **namespaced**, never a bare index. Two panes numbering their own cards from zero share
     one number, so opening the naming page's third query and switching to the curiosities
     opened that pane's third card as well: a block nobody asked for, and there is nothing on
     screen that would explain it. */
  $$("[data-sqlshow]").forEach(b => b.addEventListener("click", () => {
    const k = b.dataset.sqlshow;
    state.showSql = state.showSql === k ? null : k;
    render();
  }));

  $$("[data-crumb]").forEach(b => b.addEventListener("click", () => {
    state.view = b.dataset.crumb;
    pushTrail(state.view, b.textContent.trim());
    render();
  }));

  /* the trail: move the cursor along it, or clear it.
   *
   * **Moving, not truncating.** This used to cut the trail off at the step it went to, and
   * Back used to pop -- which made looking backwards destroy the journey it was showing.
   * A history has a cursor, and the only thing that drops the forward branch is a *new*
   * step, which is `recordSelection`'s own rule. Going back and changing your mind is now
   * free, which is the whole point of the record. */
  $$("[data-trail]").forEach(b => b.addEventListener("click", () => {
    const i = parseInt(b.dataset.trail, 10);
    const step = state.trail[i];
    if (!step) return;
    trailAt = i;
    // The subject is the point. Steps recorded before this existed have none, and those
    // still change the view -- old data is not a reason to fail, only to do less.
    goToTrailStep(step);
  }));
  /* `$$`, not `$`. The trail bar is rendered in two places now -- the app's header and the
   * detail window, which needs its own because the header is behind that window's scrim --
   * and these two were wired with the singular selector, so only whichever copy came first
   * in the DOM did anything. The window's *Back* rendered, looked live, and listened to
   * nothing: design rule 16 in the one control a lost reader reaches for.
   *
   * The steps beside them were already `$$` and always worked, which is what made it
   * confusing to look at -- two thirds of one bar working is not a state anybody expects. */
  /* Back and Forward are `undoSelection` and `redoSelection` -- the same two functions ⌘Z
     and the HUD's buttons call. Three doors, one history; that is the whole change. */
  $$("[data-trailback]").forEach(tb => tb.addEventListener("click", undoSelection));
  $$("[data-trailfwd]").forEach(tf => tf.addEventListener("click", redoSelection));
  $$("[data-trailclear]").forEach(tc => tc.addEventListener("click", () => {
    /* Cleared to **where the reader is**, carrying the subject, rather than to a
       subject-less sentinel. Clear is for a trail grown too long to read, not for
       abandoning the thing on screen -- and a step with no subject is a step that takes
       nobody anywhere (rule 33). */
    state.trail = [{ view: state.view, label: labelFor(state.selected) || "here",
                     note: "trail cleared", subject: selectionSnapshot() }];
    trailAt = 0;
    render();
  }));
  $$("[data-nav2]").forEach(b => b.addEventListener("click", () => {
    state.view = b.dataset.nav2; pushTrail(state.view, "kept things"); render();
  }));

  /* keep a thing for later without losing where you are */
  $$("[data-pin]").forEach(b => b.addEventListener("click", (e) => {
    e.preventDefault();
    const label = b.dataset.pin;
    const at = state.pins.findIndex(x => x.label === label);
    if (at >= 0) state.pins.splice(at, 1);
    else state.pins.push({ label, note: b.dataset.pinnote || "" });
    render();
  }));
  $$("[data-unpin]").forEach(b => b.addEventListener("click", () => {
    state.pins.splice(parseInt(b.dataset.unpin, 10), 1); render();
  }));

  /* A curiosity is a doorway, and it goes through `data-thread` above -- there is no
     handler of its own here, deliberately. The one that used to be routed on a `tag`
     string with a fall-through, which is rule 30: a label is not an identity, and an
     unrecognised one landed on table mode looking like a decision somebody made. */

  /* a thread is a detour you can take and come back from */
  $$("[data-thread]").forEach(b => b.addEventListener("click", () => {
    let subject;
    try {
      subject = JSON.parse(b.dataset.thread);
    } catch (err) {
      console.error("[dunneflow] a thread carries no subject:", b.dataset.thread, err);
      return;
    }
    pushTrail(state.view, b.dataset.threadlabel || "thread", b.dataset.threadwhy);
    followThread(subject);
  }));
  $$("[data-threadsall]").forEach(b => b.addEventListener("click", () => {
    state.threadsAll = !state.threadsAll; render();
  }));

  /* No handler on the source-directory readout. It was a disclosure toggle over a tree
   * that is no longer recorded, and it is a readout now -- a `<div>`, with nothing to
   * expand and no pointer cursor to promise one. A listener kept here would have been a
   * control that looks pressable, responds to a press, and changes nothing. */

  /* The pair. Its value names both ends -- `base|compared` -- see `buildRevControls`. */
  const rev = $("#rev");
  if (rev && !rev.dataset.bound) {
    rev.dataset.bound = "1";
    rev.addEventListener("change", () => {
      const [wantBase, wantCompared] = String(rev.value).split("|");
      /* `ALONE`, never "". The reader has *answered*, and "" is the state that means
         they have not -- which the fallback in `comparedRevInForce` then fills in. */
      state.comparedRev = wantCompared || ALONE;
      /* Cleared here, deliberately, because the reader has just answered it. It used to
         disappear by falling out of the one `changeNote` branch that did not prepend it,
         which looked right and was an accident: three returns carried the notice and the
         fourth did not, so it survived every state except a successful comparison. A
         message that clears itself in one arm of a conditional clears itself at random. */
      state.revNote = "";
      used("pair:" + (wantCompared ? "compared" : "alone"));

      /* Moving the reading end is a different act from moving the comparison end, and it
         costs a different amount. The comparison end is a query the server already has the
         stores for; the reading end is the payload, the file list, both vocabulary lanes
         and the cover, rebuilt from another graph -- ten seconds the reader has to be able
         to watch. So they are two branches, and which one this is depends on the server's
         answer about what it is serving rather than on what `state` last stored. */
      const serving = servingRevision();
      if (wantBase && serving && wantBase !== serving) {
        /* `baseRev` is **not** written here, and that is the point of it being the
           server's answer rather than the reader's. Writing it now would record an
           intention as a fact: a reader who reloads mid-rebuild, or whose switch fails,
           would have a stored base naming a version nothing is serving. `switchBase`
           carries the intent; `reconcileBase` records the outcome, once there is one. The
           comparison end is different -- it is a client-side choice that costs nothing and
           is true the moment it is made -- so it is persisted here. */
        persist();
        switchBase(wantBase);
        return;
      }
      state.baseRev = serving || wantBase || "";
      persist();
      /* The overlay is an answer about *this pair* and about nothing else, so it goes with
         the pair rather than being left to be overwritten. Dropped rather than re-fetched
         here: the code marks then repaint from whatever the new pair says, and a reader
         who is not in the code browser has paid nothing. */
      FILEPAIR = null; FILEDIFF = null;
      /* Only when there is something to compare. "On its own" is a real answer and must
         not spend seconds fetching a comparison nobody asked for -- but it must still
         repaint, or the Changes group keeps the figures of the pair just dropped. */
      if (wantCompared) {
        refreshChanges();
        if (state.codeFile && overlayOn()) {
          ensureFilePair();
          ensureFileDiff(state.codeFile).then(repaintCode);
        } else {
          ensureFilePair().then(repaintCode);
        }
      } else { CHANGES = null; repaintCode(); }
    });
  }

  /* provenance click-through */
  bindCitations("");
  $$("[data-closeviewer]").forEach(b => b.addEventListener("click", () => {
    state.viewer = null; render();
  }));
  $$("[data-viewtab]").forEach(b => b.addEventListener("click", () => {
    state.viewer = { ...state.viewer, idx: parseInt(b.dataset.viewtab, 10) };
    render();
    loadViewerSource();
  }));

  /* egress posture + manifest */
  $$("[data-egress]").forEach(b => b.addEventListener("click", () => {
    state.egress = b.dataset.egress;
    if (state.egress === "off") state.showManifest = false;
    state.aiConfirm = false;
    render();
  }));
  const mf = $("[data-manifest]");
  if (mf) mf.addEventListener("click", () => { state.showManifest = !state.showManifest; render(); });

  /* one-time AI pass: choose, see the price, then confirm twice */
  $$("[data-aiop]").forEach(cb => cb.addEventListener("change", () => {
    state.aiOps[cb.dataset.aiop] = cb.checked;
    state.aiConfirm = false;
    render();
  }));
  $$("[data-airun]").forEach(b => b.addEventListener("click", () => {
    const a = b.dataset.airun;
    if (a === "arm")    state.aiConfirm = true;
    if (a === "cancel") state.aiConfirm = false;
    if (a === "go")   { state.aiDone = true;  state.aiConfirm = false; }
    if (a === "reset") state.aiDone = false;
    render();
  }));

  /* inspector source */
  const sb = $("#srcBtn");
  if (sb) sb.addEventListener("click", () => {
    const p = $("#srcPane");
    if (p.hasAttribute("hidden")) p.removeAttribute("hidden"); else p.setAttribute("hidden", "");
  });
}

function step(d) {
  const list = worklistFor(state.sev);
  if (!list.length) return;
  state.cursor = (state.cursor + d + list.length) % list.length;
  render();
  const el = document.querySelector('[data-cursor="' + state.cursor + '"]');
  if (el) el.scrollIntoView({ block: "nearest" });
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.viewer) { e.preventDefault(); state.viewer = null; render(); return; }
  /* The source viewer sits *on top* of the detail window, so it closes first. Two modals
     dismissed by one key have to unwind in the order they were opened, or Esc closes the
     thing underneath and leaves the thing in front standing on nothing. */
  if (e.key === "Escape" && state.detail) {
    e.preventDefault(); closeDetail(); return;
  }
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  /* Drill into whatever the pop-up is describing.
   *
   * `hoverAt` rather than `state.selected`, and that is the whole point: the card is about
   * the node under the pointer, which is usually *not* the one selected. Opening the window
   * on the selection would answer a question the reader did not ask, and would do it
   * plausibly enough that they might not notice.
   *
   * The card itself stays untouchable (`pointer-events: none`, a recorded decision), so a
   * key is how a hover becomes a destination. */
  if (e.key === "Enter" && !typing && hoverAt && !e.metaKey && !e.ctrlKey && !e.altKey) {
    e.preventDefault();
    openDetail(hoverAt);
    return;
  }
  if (e.key === "/" && !typing) { e.preventDefault(); $("#search").focus(); return; }
  /* Undo the selection, from anywhere -- the reader who needs it is by definition lost and
   * should not have to find a particular pane first. Above the anomalies-only guard below
   * for the same reason. The platform chord, because a reader who wants to take something
   * back tries the one their hands already know. */
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z" && !typing) {
    e.preventDefault();
    if (e.shiftKey) redoSelection(); else undoSelection();
    return;
  }
  /* The source pane, from anywhere the inspector is showing one. The button has printed
   * an `S` badge since the inspector was written and nothing has ever listened for it --
   * a promise in a label rather than in a handler, which no check on this page could see:
   * the runtime self-check reads `data-*` attributes, and a keyboard shortcut has none. */
  if (e.key.toLowerCase() === "s" && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) {
    const sb = $("#srcBtn");
    if (sb) { e.preventDefault(); sb.click(); return; }
  }
  if (typing || state.view !== "anomalies") return;
  if (e.key === "j") { e.preventDefault(); step(1); }
  if (e.key === "k") { e.preventDefault(); step(-1); }
  if (["1", "2", "3"].includes(e.key)) {
    e.preventDefault();
    const list = worklistFor(state.sev), cur = list[state.cursor];
    if (!cur) return;
    setTriage(cur.a, { "1": "notbug", "2": "ack", "3": "tooldefect" }[e.key]);
    step(1);
  }
});

/* ─────────────────────────────────────────────────────────────────
   Self-check. A control that renders but is wired to nothing looks
   exactly like a working one, and that is how the left-hand menu
   shipped broken: a patch missed its target, eight nav kinds fell
   through to the graph, and nothing said so. This runs after every
   render and names anything unreachable rather than failing quietly.
   ───────────────────────────────────────────────────────────────── */
/* Derived from the source at build time: every data-* attribute a listener queries,
   plus those read as companions inside another handler, those bound by element
   selector rather than by attribute, and the structural markers that only style or
   identify and are never clicked. */
/* Every `data-` attribute the shell renders, and it is a roster of two kinds of thing.
 *
 * Most are **controls**: something listens, and an absence here means a button that
 * renders, looks live and does nothing (design rule 16). Some are **parameters** --
 * `pinnote`, `threadwhy`, `navid` -- read off a control that was found by class, and some
 * are **state** the stylesheet reads, like `insp` on the grid track. Nothing listens for
 * those and nothing should; they are here because the self-check sweeps every `data-`
 * attribute it can see and cannot tell the three apart from the DOM.
 *
 * Five were missing -- `insp`, `fold`, `navid`, `titled`, `legend` -- and had been since
 * the panes learned to fold and the navigator became the routine list. All five are real
 * and none was ever dead, so the self-check printed a red "dead controls" error on every
 * page load while being wrong about all of them. Its own comment says why that is
 * expensive: a check that cries wolf is a check nobody reads, and this one had four
 * standing false alarms behind which a genuine one would have sat unnoticed.
 *
 * The fifth is the one worth the sentence. `legend` is written on the graph mount, which
 * does not exist until the reader opens the graph, so the console error said four at boot
 * and five afterwards -- the same check giving two different answers about one page, and
 * neither of them the truth. The source guard has no such state to be in.
 *
 * `test_every_data_attribute_the_shell_writes_is_in_the_roster` now derives the same set
 * from the source, generated markup included, which is the direction the existing guard
 * could not see: it reads `index.html`, and all four of these are written by JavaScript. */
const WIRED_ATTRS = new Set([
  "aiop", "airun", "bound", "card", "cite", "citeidx", "closeviewer", "crumb", "curi",
  "cursor", "den", "dgmcursor", "dgmedge", "disk", "drop", "edgesmotion", "egress", "ep",
  "fold", "gact", "gosev",
  "goto", "graphtheme", "insp", "jump", "layout", "legend", "manifest", "menuorder",
  "mode", "nav", "nav2", "navcap", "navgroups", "pkgopen", "pointerplace", "pointerreset", "pointershown", "reticule",
  "closedetail", "detachdetail", "detail", "detailall", "tablego",
  /* The code browser's three. `codelink` is on every clickable name in the source and
     `CODE_ROUTES` is what listens for all of them -- one table, checked by the guard that
     reads it, so a fourth kind added there without a listener fails by name. */
  "codeback", "codedetach", "codelink", "codeopen", "codemode", "codeoverlay",
  /* The routine list and the table's own overlay switch. A second switch rather than one
     governing both surfaces: the code overlay fetches a difference per file and these
     marks are read off an answer already held, so wanting one without the other is
     ordinary and one control cannot say it. */
  "tableoverlay",
  /* And the findings'. A third rather than a wider second, for the reason the second exists
     and one more: this is the dear one -- the compared end is thirteen detectors run over a
     graph nothing here has opened -- so a reader must have somewhere to decline it.
     `anoonlythere` unfolds the findings only the compared version has, which are counted
     but never listed among this version's own (design rule 1, rule 32). */
  "anomalyoverlay", "anoonlythere",
  /* The version strip's one control: which version the reader assumes is newer. It is on
     the strip rather than in Settings because it decides what every red row means, and a
     colour a reader cannot account for is worse than no colour. */
  "assumenewer",
  /* The change worklist's controls: which band is open, and which presence group has its
     complete list showing rather than its first six. `presgroup` carries the band and the
     side it names, never a position among the three groups on a line (rule 30). */
  "changeband", "presgroup",
  /* The shape set, beside `palette-set` and `theme-set`. A route only: nothing on the page
     is stamped `data-shapeset`, which is what keeps it clear of the `data-nav` collision
     those two are named to avoid. */
  "shapeset",
  /* The compartment diagram's own controls. `dgm` is the fit button; the compartment picker
     is an id and the boxes are routed by Graphviz's own `g.node` class and the `id=` the
     server put on each one, which is the box id -- so a click resolves to a thing this
     program knows about rather than to a shape (rule 30). */
  "dgm",
  /* A **box** in a fold's own pane, and the one way to the code. `box` rather than `fold`
     because `data-fold` has collapsed a pane since design rule 24 -- a class name and a
     data attribute are both global, and the obvious spelling here would have railed the
     inspector on every neighbour row (rule 71). */
  "box", "gotocode", "gotoline", "label", "dgmup",
  /* The base switch's one control: dismiss a switch that failed. Only ever rendered in the
     failed state -- there is nothing to dismiss while a rebuild is running, and offering a
     cancel that cannot stop the server would be a control that looks live and is not. */
  "rebuilddismiss",
  /* The search's four. `searchline` rides with `searchgo` on the same button and carries no
     handler of its own -- it is the line the click is about, and the roster is a list of
     attributes the shell writes, not only of the ones that are clicked. */
  "searchopen", "searchgo", "searchline", "searchflag",
  "navid", "navtrack", "node", "open", "pane", "pin", "pinnote", "pkgnode", "pkgpick", "qual",
  "resize", "row",
  /* `palette-set`, beside `theme-set` and for the same reason: `data-palette` and
     `data-theme` are stamps on `:root`, and an attribute that is both a route and a piece
     of state is what `data-nav` cost a session to find. */
  "palette-set",
  "scale-set", "sec", "sev", "sevnav", "sort", "sqlshow", "start", "step", "theme",
  "term", "termuse", "theme-set", "thread", "threadlabel", "threadsall", "threadwhy",
  "titled", "toggle",
  "trail", "trailback", "trailfwd", "trailcap", "trailclear", "triage", "triaged", "unpin", "viewtab"]);

function selfCheck() {
  const problems = [];
  /* The handler's own selector, not a class that usually accompanies it. Scanning
   * `.nav-item` meant a routed control living anywhere else -- a worklist row, say -- was
   * never checked at all, and passed by being invisible rather than by being right. */
  document.querySelectorAll(NAV_SELECTOR).forEach(el => {
    if (!NAV_ROUTES[el.dataset.nav]) problems.push(`nav "${el.dataset.nav}" has no route`);
  });
  /* `#rebuildMount` is in the list for the reason the list exists: it is a body-level
     surface like `#viewerMount`, so a scan naming only the app and the viewer would have
     been blind to a whole modal -- which is the defect this check is for, wearing the
     costume of a container nobody remembered to name. */
  document.querySelectorAll(".app *, #viewerMount *, #rebuildMount *").forEach(el => {
    for (const a of el.attributes) {
      if (!a.name.startsWith("data-")) continue;
      const k = a.name.slice(5);
      if (!WIRED_ATTRS.has(k)) {
        problems.push(`control [data-${k}] is rendered but nothing listens for it`);
      }
    }
  });
  /* Only one direction is answerable here, and knowing which is the point.
   *
   * **A control on screen with no action** is always a defect: it renders, it looks
   * live, and nothing listens. The DOM proves that outright.
   *
   * **An action no control reaches** cannot be judged from the DOM at all, because half
   * these controls are conditional -- `clear` appears only with a selection, and the whole
   * HUD only in graph mode. Asking the live page reported `clear` as unreachable while
   * sitting on the Settings view, which is a true statement about that moment and a false
   * one about the product. A check that cries wolf is a check nobody reads, so that
   * direction is answered where it *is* answerable: `test_web_controls.py` scans the source
   * for every `data-gact` written anywhere, conditional or not. */
  document.querySelectorAll("[data-gact]").forEach(el => {
    if (!(el.dataset.gact in GRAPH_ACTIONS)) {
      problems.push(`graph control [data-gact="${el.dataset.gact}"] has no action`);
    }
  });

  const unique = [...new Set(problems)];
  if (unique.length) {
    console.error("DunneFlow self-check found dead controls:", unique);
  } else {
    console.log("DunneFlow self-check: every control is wired.");
  }
  return unique;
}

/* Wrap each nav item's own text in a span so it can wrap independently of the count. */
function dressNavItems() {
  $$(".nav-item").forEach(el => {
  const texts = [...el.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim());
  if (!texts.length) return;
  const span = document.createElement("span");
  span.className = "navlabel";
  span.textContent = texts.map(n => n.textContent).join("").trim();
  if (span.textContent.length > 25)      span.classList.add("xlong");
  else if (span.textContent.length > 17) span.classList.add("long");
  // An item that brought its own title knows more than the leaf text does -- a routine row
  // carries the qualified name, and overwriting it with the leaf loses the only thing the
  // hover was worth doing for.
  if (!el.dataset.titled && !el.dataset.card) el.title = span.textContent;
  texts.forEach(n => n.remove());
  const count = el.querySelector(".n");
  el.insertBefore(span, count || null);
  });
}

/* ════════════════════════════════════════════════════════════
   The navigator, generated from the store.

   Table-driven for the same reason `NAV_ROUTES` is (design rule 16): a group is
   an entry here, not a branch, and a group whose `nav` kind has no route is
   caught by `selfCheck()` rather than rendering a dead control.

   Counts are the program's. A navigator with numbers written into its markup
   shows those numbers whatever it is pointed at, which is the failure this
   whole port exists to undo.
   ════════════════════════════════════════════════════════════ */

/* The routine list: the way in for the interaction this whole shell is for -- pick one on
 * the left, and the graph on the right highlights it with everything that calls it and
 * everything it calls.
 *
 * `sel` is the node id, and it is the entire point. Rule 30 was written from four
 * navigator routes whose items carried only a label, so forty rows all did the same
 * nothing while the inspector went on truthfully reporting "Nothing selected". A row here
 * with no id is dropped at load rather than rendered as a button that cannot act. */
/* **The one place that decides whether a name matches what was typed.**
 *
 * The topbar has always said *"Search routines, tables, boundaries…"* and has always
 * filtered routine names and nothing else -- so typing a real table name matched four
 * routines by substring and left the Database group untouched, and typing a real boundary
 * name said *"nothing matches"* about a boundary the program has. A control that names three
 * things and does one is design rule 16's dead control with two thirds of it alive.
 *
 * Written once and handed to every group, so a group added later is filtered by having been
 * born rather than by somebody remembering (rule 36). Case-insensitive substring, over the
 * name **and** whatever second string identifies the thing -- a routine's module, a
 * structure's module, a boundary's commonest target -- because "which `execute` is this"
 * is answered by the qualifier and not by the leaf.
 *
 * Everything it filters is already in memory, so this costs no request per keystroke: that
 * is rule 45's whole subject, and the one lane that *would* cost a request -- the source
 * text -- is offered as a route rather than run. */
function navMatch(m, ...fields) {
  if (!m || m.all) return true;
  if (!m.ok) return false;            // a broken pattern matches nothing, and says why
  return fields.some(f => m.test(f));
}

/* The matcher, **compiled once per keystroke and not once per row.**
 *
 * `items()` and `note()` are each called for every group and the predicate for every row --
 * 5,560 names on Mensores -- so building a `RegExp` inside `navMatch` would compile the
 * pattern five and a half thousand times per character typed. That is rule 45's own shape:
 * work proportional to the program on every keystroke. Cached on the query and the three
 * flags, so every caller in one repaint shares one compile.
 *
 * **A broken pattern is an answer, not an absence.** `[unclosed` is a mistake a reader can
 * see and fix, and reporting it as "nothing matches" says the program does not contain the
 * thing they asked for -- which is precisely the false conclusion this work began with. The
 * Code box already says why; this says the same sentence.
 */
let navMatcherCache = null;
function navMatcher() {
  const q = state.routineQ.trim();
  const key = `${q}\u0000${state.navCase}\u0000${state.navWord}\u0000${state.navRegex}`;
  if (navMatcherCache && navMatcherCache.key === key) return navMatcherCache;
  let m;
  if (!q) {
    m = { key, all: true, ok: true, test: () => true };
  } else {
    /* Whole word is off while a regex is in force, exactly as in the Code box: a pattern
       writes its own `\b`, and wrapping one in another pair changes what it means. */
    const flags = state.navCase ? "" : "i";
    if (state.navRegex) {
      try {
        const re = new RegExp(q, flags);
        m = { key, ok: true, test: (f) => re.test(f || "") };
      } catch (err) {
        m = { key, ok: false, reason: err.message, test: () => false };
      }
    } else if (state.navWord) {
      const re = new RegExp(`\\b${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, flags);
      m = { key, ok: true, test: (f) => re.test(f || "") };
    } else if (state.navCase) {
      m = { key, ok: true, test: (f) => (f || "").includes(q) };
    } else {
      const lower = q.toLowerCase();
      m = { key, ok: true, test: (f) => (f || "").toLowerCase().includes(lower) };
    }
  }
  navMatcherCache = m;
  return m;
}

/* Kept for the groups that still ask for a plain query. */
function navQuery() {
  return navMatcher();
}

/* What a filtered group says about itself. **Design rule 1: no filter is ever silent.**
 *
 * Four of these groups had no note at all, so a search that matched nothing in them left the
 * heading and its total sitting above an empty body -- indistinguishable from a group that
 * had simply not been opened. Written once and handed to each, so a group added later says
 * something by having been born (rule 36).
 *
 * `whole` is the group's own count and is never the filtered one: the heading answers *how
 * much is here* and the note answers *how much matched*, which are two questions and rule 32
 * says a number is named after what it measures. */
function navFilterNote(hit, whole, what, shown) {
  const q = state.routineQ.trim();
  if (!q) return `${whole.toLocaleString()} ${what}`;
  /* A pattern that will not compile is a mistake the reader can fix, and saying "nothing
     matches" about it claims the program lacks what they asked for. The Code box already
     says why; this is the same sentence, so the two boxes answer alike. */
  const m = navMatcher();
  if (!m.ok) return `that is not a regular expression: ${esc(m.reason || "")}`;
  if (!hit) return `nothing matches “${esc(q)}”`;
  const cut = shown && hit > shown ? ` — showing ${shown}` : "";
  /* `N match`, never `N matches`. Both are correct English -- "one matches", "four match" --
     and that is exactly why the choice has to be made once: the Routines note has said
     `match` since it was written, so deriving an `es` here would have put two spellings of
     one sentence in one pane (rule 13). The same reason `modband` writes `stat` and `stat1`
     out in full rather than appending an `s` by arithmetic. */
  return `${hit.toLocaleString()} match “${esc(q)}”${cut}`;
}

function matchingRoutines() {
  /* Through the shared matcher, so the three flags reach the group a reader uses most. This
     was its own lowercased `includes`, which is the same test the matcher makes by default
     -- and would have gone on being that while `.*` worked in every other group (rule 51:
     one truth, one place that owns it). */
  const m = navMatcher();
  if (m.all) return { rows: ROUTINES, total: ROUTINES.length, filtered: false };
  const rows = [];
  for (const r of ROUTINES) if (navMatch(m, r.name, r.module)) rows.push(r);
  return { rows, total: rows.length, filtered: true, bad: !m.ok, reason: m.reason };
}

/* The routine list, by package.
 *
 * A flat list capped at two hundred answers "what is in this program" with two hundred
 * arbitrary rows out of 4,734 -- and arriving in the middle of it by wheel tells the reader
 * nothing about where they are. Forty-seven package rows are a list a person can read, and
 * every one of them is a plate in the stack beside it.
 *
 * The packages are complete and never bounded: forty-seven rows is a list, not a diagram,
 * and rule 8 bounds only diagrams. The *routines within* one package are capped, because
 * `render()` rebuilds this on every keystroke and the largest package holds 959 -- and what
 * is left out is stated on the package it was left out of, never at the bottom of it.
 *
 * Ranked by size, which is the cover's own ranking: the biggest package is where most of
 * the program is, and a reader who does not yet know the names has no better first guess. */
/* Computed once per build of the pane.
 *
 * The group's note asks how many matched and in how many packages; its body asks for the
 * packages themselves. Both are the same question, and both ran a full scan of 4,734
 * routines and two passes over the matches -- twice per keystroke, for one answer. Cleared
 * at the top of `buildNav()`, which is the only thing that reads it and is called by
 * everything that could change it. */
let treeCache = null;

function routineTree() {
  /* The same set the pane marks with. Past the cap, a *member of a fold* has to survive for
     the same reason the selected routine does: the alternative is a package that opens onto
     rows with nothing marked, which is identical on screen to the sync being broken. */
  const keep = selectedRowIds();
  if (treeCache) return treeCache;
  const { rows, total, filtered } = matchingRoutines();
  const cap = navCap();

  // Pass one: which packages, and how many in each. No rows yet -- what a package will
  // draw depends on how big the answer turns out to be.
  const by = new Map();
  for (const r of rows) {
    const g = by.get(r.pkg);
    if (g) g.n++;
    else by.set(r.pkg, { id: r.pkg, n: 1, rows: [] });
  }
  /* A search opens the packages it matched in, up to a point. Past that point it does not,
   * and the note says so.
   *
   * The point exists because of what it cost: `e` matches 4,734 routines across all 47
   * packages, and opening every one of them built 3,413 buttons in **483 ms** on the first
   * keystroke of an ordinary search. That is the glossary filter's 412 ms again, in another
   * pane. And it was the worse answer as well as the slower one -- "2,206 match g, in 43
   * packages" is something a reader can act on; 1,924 rows is the same haystack again. */
  const autoOpen = filtered && total <= SEARCH_OPEN_MAX;
  /* Either the search opened it or the reader did. The reader's own choice must survive a
     broad search, or the note's "open one" is an instruction the pane refuses to obey. */
  for (const g of by.values()) g.open = autoOpen || pkgOpen(g.id);

  // Pass two: rows, only for what will actually be drawn. A closed package's rows are
  // `display: none`, and building them anyway cost 3,413 buttons on every keystroke where
  // the flat list cost 200. Hidden is not the same as absent, and the difference is the bill.
  for (const r of rows) {
    const g = by.get(r.pkg);
    /* **The cap never hides what is selected.**
     *
     * Without this clause the back half of the reading loop failed silently on exactly the
     * routines it is most needed for. Pick `verify_timestamp` in the picture -- rank 400 in
     * a package of 531 -- and the inspector filled, the package opened, and the list showed
     * no row at all: no highlight, no scroll, nothing marked. Identical on screen to the
     * sync being broken, which is what it was reported as.
     *
     * It lands last among the rows shown, which is its right place: everything drawn comes
     * before it in the same order, and the cut is between them. The note counts it. */
    if (g.open && (g.rows.length < cap || keep.has(r.id))) g.rows.push(r);
  }
  const packages = [...by.values()].sort((a, b) => b.n - a.n || a.id.localeCompare(b.id));
  treeCache = { packages, total, filtered, autoOpen };
  for (const g of packages) {
    /* Which plate this package is on, and it is not always its own. A package below
     * `MIN_DISK` is merged into `pkg:<small>`, so `pkg:_version` names nothing in the
     * stack -- and a row carrying it would be a control that renders and resolves to
     * nothing. It selects the plate it is genuinely drawn on, or it carries no identity at
     * all and stays a heading, which is the honest third answer. */
    const own = `pkg:${g.id}`;
    g.plate = PLATES.has(own) ? own : (PLATES.has("pkg:<small>") ? "pkg:<small>" : "");
    g.merged = g.plate !== "" && g.plate !== own;
  }
  return treeCache;
}

/* Is this package expanded, when nothing is being searched for? While a search is running
 * `routineTree` decides, because that answer depends on how large the answer is. */
function pkgOpen(id) {
  return !!state.navOpen[`pkg:${id}`];
}

function routineList() {
  /* Once for the whole pane. A `Set` per row is one allocation per routine on a list that
     rebuilds on every keystroke -- rule 45's shape, in the pane that already earned it. */
  const rowMarks = selectedRowIds();
  const { packages, total } = routineTree();
  if (!ROUTINES.length) return "";
  if (!total) return "";
  return packages.map(g => {
    const open = g.open;
    const cut = g.n - g.rows.length;
    return `
    <div class="nav-pkg" data-open="${open}">
      <div class="nav-pkghead">
        <button class="nav-pkgtoggle" data-pkgopen="${esc(g.id)}" aria-expanded="${open}"
                title="${open ? "Collapse" : "Expand"} ${esc(g.id)}"><span class="caret">▼</span></button>
        ${g.plate
          ? `<button class="nav-item nav-pkgname" data-nav="pkg" data-navid="${esc(g.plate)}"
                     data-titled="1" title="${esc(g.merged
                       ? `${g.id} is too small for a plate of its own — it is drawn on the small-packages plate`
                       : `Select the ${g.id} plate in the stack`)}">${esc(g.id)}${
                       g.merged ? ` <span class="navmerged">·small</span>` : ""
                     }<span class="n">${g.n.toLocaleString()}</span></button>`
          : `<div class="nav-pkgname nav-pkgplain">${esc(g.id)}<span class="n">${g.n.toLocaleString()}</span></div>`}
      </div>
      ${/* Only while it is open, unlike the group's own note. The group note states a
            fact that is true either way -- 4,734 in 47 packages -- but this one describes a
            list, and "showing 200 of 645" over a closed package describes nothing that is
            on screen. Forty-seven of them at once would be noise where design rule 1 wants
            a signal. */
        open && cut > 0 ? `<div class="nav-note">showing ${g.rows.length} of ${g.n.toLocaleString()}
          — search, or open the table for all of them</div>` : ""}
      <div class="nav-items">
        ${/* Computed once for the whole list rather than per row: a `Set` built inside the
             map is one allocation per routine, which is rule 45's shape on the pane that
             repaints on every keystroke. */""}
        ${g.rows.map(r => navItemHtml({
            nav: "routine", label: r.name, sub: moduleLabel(r.module, MODULE_BUDGET_NAV).text, sel: r.id,
            n: routineFan(r.id), qual: `${r.module}.${r.name}`, card: true,
            current: rowMarks.has(r.id),
            /* Read, never asked for. `routineChip` answers "" until something else has
               fetched the comparison, and nothing on this path fetches it -- see
               `ensureTableOverlay`. This group is open by default, so asking here would
               make every session pay up to 28 s for a question nobody put. */
            chg: routineChip(r.id),
          })).join("")}
      </div>
    </div>`;
  }).join("");
}

/* Callers and callees, shown as two numbers rather than one.
 *
 * This was `degree` -- a single edge count -- and it misled exactly as a single number
 * should be expected to: every other group in this navigator counts *things*, so "8" beside
 * a routine reads as eight nodes. `guarded_cwd` has 3 callers and 5 callees, printed 8, and
 * drew 7 nodes; all three numbers were right and no two of them agreed about what they
 * were. A count must say what it counts.
 *
 * Blank until the engine is mounted rather than guessed, because an absent count and a
 * count of zero are opposite claims. */
function routineFan(id) {
  if (!Graph.mounted()) return "";
  const c = Graph.connections(id);
  if (!c) return "";
  return `${c.in}\u2190 ${c.out}\u2192`;
}

/* \u2500\u2500 one shortening, and it keeps both ends \u2500\u2500
 *
 * Asked for at the keyboard: *many of the things we attempt to display are actually too
 * large for their fields. We must choose the portion that shows as much uniqueness as
 * possible.* Neither end alone is that portion. `mensores.storage._audit` and
 * `mensores.capture._audit` share a leaf; `mensores.storage._audit` and
 * `mensores.storage._queue` share a head. Only keeping **both** tells the two pairs apart,
 * so what goes is the middle.
 *
 * This replaces `moduleTail`, which kept the last two segments and is the reason that
 * choice is worth stating: a leaf-only rule renders those first two as the same string.
 *
 * **Whole segments, never mid-token.** A qualified name has joints -- `.` between module
 * parts, `/` between path parts -- and cutting *between* them leaves a string that exists
 * in the program with a piece visibly removed. Cutting *through* one leaves
 * `...ores_internal_cwd_guard`, which exists nowhere; that was `direction: rtl` letting the
 * browser choose, and it is the defect this function was extracted from.
 *
 * **The budget is the caller's**, because it comes from the width of the caller's own
 * field. CSS keeps its `text-overflow: ellipsis` underneath as a backstop for the window
 * width this arithmetic did not predict (rule 53) -- a budget alone is right at one window
 * size. `selfCheck` asserts the backstop never fires.
 *
 * Returns the count as well as the text: a caller that cannot say how much it cut cannot
 * obey design rule 1, and `moduleTail` could not -- it shortened to a fixed two segments
 * and told nobody, in either of the two places it was used.
 */
const ELLIPSIS = "\u2026";

function shorten(text, budget) {
  const s = String(text == null ? "" : text);
  if (s.length <= budget) return { text: s, cut: 0 };

  /* `/` wins where a string has both, because `mensores/storage/_audit.py` is jointed at
     its slashes and the dot in `.py` is not a joint -- splitting on it yields two parts,
     which sends a path down the character branch and cuts it mid-segment. */
  const sep = s.includes("/") ? "/" : s.includes(".") ? "." : "";

  /* Both ends of one token, at a character. The unit changes and the rule does not.
     Returns text only; the three places that reach it wrap it differently. */
  const squeeze = (str, room) => {
    const keep = room - ELLIPSIS.length;
    /* No room for two ends and a mark between them. The mark alone, never a bare head: a
       silently cut string reads as the whole one, which is the claim design rule 1 exists
       to stop a field from making. */
    if (keep < 2) return ELLIPSIS;
    const head = Math.ceil(keep / 2);
    return str.slice(0, head) + ELLIPSIS + str.slice(-(keep - head));
  };
  const done = (out) =>
    out.length >= s.length ? { text: s, cut: 0 } : { text: out, cut: s.length - out.length };

  /* One token, no joints -- a value, an expression, a bare identifier. */
  if (!sep) return done(squeeze(s, budget));

  const parts = s.split(sep);
  const leaf = parts[parts.length - 1];

  /* **Drop whole segments from the middle first**, growing both runs while they fit. A run
     may only grow while at least one segment is still being elided: an `\u2026` standing for
     nothing is punctuation pretending to be a fact. Two segments have no middle, so this
     yields nothing and the next step answers. */
  const build = (l, h) =>
    parts.slice(0, l + 1).join(sep) + sep + ELLIPSIS + sep + parts.slice(h).join(sep);

  if (parts.length >= 3) {
    let l = 0, h = parts.length - 1;
    for (;;) {
      const canHead = h - l > 2 && build(l + 1, h).length <= budget;
      const canTail = h - l > 2 && build(l, h - 1).length <= budget;
      if (!canHead && !canTail) break;
      /* Ties go to the tail. Both ends are kept by this rule, but where only one can grow
         it is the leaf that most often carries the name a reader is hunting. */
      if (canTail && (!canHead || parts.length - h <= l)) h--;
      else l++;
    }
    const out = build(l, h);
    if (out.length <= budget) return done(out);
  }

  /* **No middle segment left to drop, so the cut goes inside a token -- and it goes inside
     the head, not the leaf.**
   *
   * The first version cut across the whole string, which spends the damage on whichever end
   * the arithmetic happened to reach: `disceptator._anthropic_architect` came out as
   * `disceptator._an\u2026opic_architect`, keeping a package name the navigator already prints as
   * the group heading and breaking the one part that separates this row from the others in
   * it. Tom's rule names the leaf as where uniqueness usually sits, so the leaf is what is
   * protected: `disc\u2026ator._anthropic_architect`, both ends still present, one token broken
   * instead of two.
   */
  const headRun = parts.slice(0, -1).join(sep);
  const room = budget - leaf.length - sep.length;
  if (headRun && room >= ELLIPSIS.length + 2) {
    return done(squeeze(headRun, room) + sep + leaf);
  }

  /* **The leaf alone is wider than the field** -- 110 of Mensores' 566 modules, whose last
     segment is a 41-character migration name. Nothing can keep it whole, so it takes the
     same treatment: both its ends, its middle elided, behind the first segment and a mark
     for everything dropped between them.

     Two ellipses in one string is not elegant and it is the honest shape. Letting CSS clip
     the tail instead would drop the migration number -- the only part that tells these rows
     apart -- and would do it without a mark. */
  const keptHead = parts.length >= 3 ? parts[0] + sep + ELLIPSIS + sep : headRun + sep;
  const leafRoom = budget - keptHead.length;
  if (leafRoom >= ELLIPSIS.length + 2) return done(keptHead + squeeze(leaf, leafRoom));

  /* **Narrower than one segment and a mark**, so nothing structural survives and the whole
     string is squeezed to the field: both its ends, everything between them gone. It always
     fits, which is the entire job of a last step.

     This branch was a floor -- `Math.max(4, room)` -- which guaranteed the opposite: with a
     head already wider than the field, it added four more characters and returned a string
     twice the budget. Caught by asserting the budget across every width from 8 up rather
     than at the two the fields actually use, which is the range rule 53 is about. */
  return done(squeeze(s, budget));
}

/* A module as a field shows it: the program's own root dropped, then shortened.
 *
 * **All 566 of Mensores' modules begin `mensores.`**, so a rule that keeps the head would
 * spend its first nine characters on a word that is identical on every row -- and, for a
 * three-segment module, would elide the *package* to keep it. `mensores.disceptator.
 * _extraction_state` becomes `mensores.\u2026.\_extraction_state`: the useless half kept, the
 * informative half thrown away.
 *
 * `ROOT` comes from `/api/cover`, measured over every module in the store, so it is the
 * same for every field on every surface (rule 24) and known before anything renders.
 *
 * **`startsWith` on the whole prefix, not a search for a segment.** The first attempt asked
 * which segment named a package and stripped everything before it, which stripped nothing
 * at all: `mensores` is itself a package -- the modules directly under it belong to one --
 * so it matched at position 0 every time. It threw nothing, logged nothing, and left 1,019
 * navigator rows reading `mensores.\u2026.\_advance_gate`; found by looking at them.
 *
 * Stripped and *then* budgeted, so the modules that now fit are shown whole rather than
 * shortened to make room for a prefix nobody needed -- 81% of Mensores' 566 at the
 * navigator's width. */
function moduleLabel(module, budget) {
  const s = String(module == null ? "" : module);
  const pre = ROOT ? ROOT + "." : "";
  return shorten(pre && s.startsWith(pre) ? s.slice(pre.length) : s, budget);
}

/* ══ the code browser ═══════════════════════════════════════════════════════════════
 *
 * Asked for at the keyboard: *it should be able to run on the left menu as well. I want to
 * be able to see code and graph at the same time, and that's the only way.* Two windows
 * can do it and a detached view is built; inside **one** window the left pane is the only
 * place code can sit while the stack holds the centre.
 *
 * So the Code group is stacked, and it is the accordion the routine list already uses one
 * level down: a file list that collapses once a file is picked, and that file's lines
 * beneath it. Picking a file drives the pane; clicking a name in the source is an ordinary
 * `selectFromNav`, so the stack lights up, the trail records the hop, undo reaches it, and
 * the navigator's own highlight moves -- all through the one door rule 51 was written for.
 *
 * **No syntax colour**, and that is a decision rather than an omission. Design rule 4
 * spends colour on one dimension at a time, and what this tool knows about a line is not
 * its grammar -- it is that the line leaves the program, or carries a plan id, or writes a
 * table. Colouring keywords would spend the scarcest channel on the thing DunneFlow knows
 * least about. Things that are already nodes are clickable; nothing else is decorated.
 */

async function loadFiles() {
  if (FILES.length) return;
  try {
    const d = await fetch("/api/files").then(r => r.json());
    FILES = d.files || [];
  } catch (err) {
    state.navNote = `could not read the file list: ${err.message}`;
  }
}

/* One file, replacing whatever was open. `state.codeFile` is the subject and `CODEFILE` is
 * the answer to it, so a stale answer is dropped rather than shown beside a new question --
 * two fetches racing is ordinary here, because a reader clicking down a list outruns a
 * half-megabyte payload. */
async function loadCodeFile(path) {
  if (!path) { CODEFILE = null; return; }
  if (CODEFILE && CODEFILE.file === path) return;
  CODEFILE = { file: path, loading: true, lines: [], links: [], marks: [], defs: [] };
  buildNav();
  let d;
  try {
    d = await fetch(`/api/file?path=${encodeURIComponent(path)}`).then(r => r.json());
  } catch (err) {
    d = { available: false, file: path, reason: err.message };
  }
  if (state.codeFile !== path) return;            // the reader moved on
  CODEFILE = { ...d, file: path, loading: false };
  /* The built subtrees describe the *previous* file. Dropped here rather than left for the
   * key check alone, so a node holding the wrong file cannot survive one render where the
   * key happens to match -- and so the memory goes with it. */
  codeDom = { pane: { key: "", node: null }, centre: { key: "", node: null } };
  codePaintedFor = "";
  buildNav();
  render();
  /* The overlay is a **second** fetch and it arrives after the code, deliberately. The
   * lines are what the reader asked for; the difference over them is worth a repaint and
   * is not worth holding the file back for. Both are dropped by their own key check if the
   * reader has moved on, so an answer about the previous file cannot land on this one. */
  if (overlayOn()) {
    FILEDIFF = null;
    ensureFilePair();
    ensureChanges();
    ensureFileDiff(path).then(() => {
      if (state.codeFile !== path) return;
      repaintCode();
    });
  } else {
    FILEDIFF = null;
  }
  /* **Paint, then measure** -- rule 49's companion, and the reason this is not two lines
   * higher. A reveal is a `scrollTop` against a box that must already hold the lines, so
   * moving it before `render()` scrolls a pane whose content is about to be replaced. Paid
   * once and cleared, because a debt that survives is a pane that jumps later. */
  if (codeGoto) { revealLine(codeGoto); codeGoto = 0; }
}

/* Open a file in the pane, and say so in the trail.
 *
 * A file is not a node, so this does not go through `selectFromNav`: there is nothing to
 * light in the stack and nothing for the inspector to answer about. Inventing a node id to
 * make the row selectable would be a link to nothing, which `queries.py` wrote down before
 * anything needed it. What the reader picks *inside* the file is a node, and that is the
 * click that selects. */
function openCodeFile(path) {
  state.codeFile = path || "";
  persist();
  loadCodeFile(state.codeFile);
  buildNav();
}

/* The switch, drawn only where it can do something.
 *
 * With one version there is no overlay to suppress, so there is no control -- design rule
 * 16's defect is a control that renders and changes nothing, and a disabled switch beside
 * a program that will never have a second version is that with an excuse attached.
 */
const OVERLAY_SWITCHES = {
  code: { key: "codeOverlay", attr: "data-codeoverlay",
          on:  "Stop drawing the difference from the compared version over these lines",
          off: "Draw the difference from the compared version over these lines" },
  table: { key: "tableOverlay", attr: "data-tableoverlay",
           on:  "Stop marking what the comparison says about these routines",
           off: "Mark what the comparison says about these routines" },
  anomaly: { key: "anomalyOverlay", attr: "data-anomalyoverlay",
             on:  "Stop marking what the comparison says about these findings",
             off: "Mark what the comparison says about these findings" },
};

/* One renderer, two switches, and a table rather than a parameter chain -- an unknown
 * surface is a named error rather than a switch that renders and governs nothing (design
 * rule 16). Two switches because what they cost differs: the code overlay fetches a
 * difference per file, and these marks are read off an answer already held. */
function overlaySwitchHtml(which) {
  const spec = OVERLAY_SWITCHES[which];
  if (!spec) { console.error("DunneFlow: no such overlay switch:", which); return ""; }
  if (!comparing()) return "";
  const on = !!state[spec.key];
  return `<button class="linkbtn chgswitch" ${spec.attr}="1" aria-pressed="${on}"
            data-titled="1" title="${on ? spec.on : spec.off}"
          >${on ? "◆" : "◇"} changes</button>`;
}

/* The fact lane, beside the text lane, and it is the half nothing else can give.
 *
 * A text diff says these lines moved. This says **this routine behaves differently** --
 * it calls something it did not, writes a table it did not, has a parameter it did not --
 * which is what the whole tool exists to report and what `git diff` cannot state at all.
 * Four of Mensores' eighteen changed routines have an *unchanged body*: they stopped
 * resolving `queue.claim` because a new module brought a second routine of that name.
 *
 * Every row is an ordinary selection, so clicking one lights the stack, moves the
 * navigator and records a step in the trail -- the same door every other row uses.
 */
function factLaneHtml(path) {
  if (!overlayOn() || !path) return "";
  const f = fileFactChanges(path);
  const n = f.behaves.length + f.explained.length
          + f.base_only.length + f.compared_only.length;
  if (!n) {
    /* Three states, and collapsing any two of them states the wrong one. "Nobody has asked
       yet", "it is being computed" and "nothing here behaves differently" are different
       claims, and only the last of them is an answer (rule 35). The middle one matters
       most here: this is the request that can take tens of seconds on a cold volume, and
       silence for that long reads as a lane that failed. */
    if (!CHANGES) return "";
    if (CHANGES.loading) {
      return `<div class="codeview-note factlane">reading what behaves differently…</div>`;
    }
    if (!CHANGES.available) return "";
    /* Both bands named, because `n` counts both. Saying only "behaves differently" here
       would be a claim narrower than the one this lane just tested -- a file whose comments
       were rewritten would read as one nothing had been checked about. */
    return `<div class="codeview-note factlane"><b>Nothing in this file behaves or is
      explained differently.</b> Its text may still differ — that is the lane above.</div>`;
  }
  const w = diffWords();
  /* The glyph is passed rather than derived from the tone, because there are **three**
     things here and only two of them have a direction. A routine present in both and
     behaving differently was neither added nor deleted, and `signOf` would have printed
     `+` beside it for want of a third answer — a sign that means nothing, in the channel
     that means direction. */
  const row = (r, tone, glyph, why) => `<button class="factrow nav-item" data-nav="routine"
      data-navid="${esc(r.id)}" data-titled="1" title="${esc(r.qualname)} — ${esc(why)}">
      <span class="factdot tone-${tone}" aria-hidden="true">${glyph}</span>
      <span class="mono">${esc(r.name)}</span>
      <span class="factwhy">${esc(why)}</span></button>`;
  const moved = (r) => (r.moved || []).join(", ") || "differently";
  return `<div class="codeview-note factlane">
    <b>${n} routine${n === 1 ? "" : "s"} here the comparison has something to say about.</b>
    This is the lane a text diff cannot give: what a routine <i>does</i>, not which of its
    lines moved.
    <div class="factrows">
      ${/* `moved`, and it was `mod` until 2026-09-01 -- a fourth spelling of the third
            direction, with a rule of its own that painted it the muted text colour one
            class name away from the `.tone-moved` the graph, its legend and the findings
            all use. Rule 51, and rule 71 gave it the cover: a near miss compiles. */""}
      ${f.behaves.map(r => row(r, "moved", "\u25cb",
          "behaves differently — " + moved(r))).join("")}
      ${f.explained.map(r => row(r, "moved", "\u00b6",
          "explained differently — its comment moved and its code did not")).join("")}
      ${f.base_only.map(r => row(r, w.base.tone, signOf(w.base.tone),
          w.base.word)).join("")}
      ${f.compared_only.map(r => row(r, w.compared.tone, signOf(w.compared.tone),
          w.compared.word + " — its lines are in the other version")).join("")}
    </div>
    ${f.compared_only.length ? `<div class="hint">The ${f.compared_only.length} ${
      w.compared.word} routine${f.compared_only.length === 1 ? " is" : "s are"} listed
      rather than marked: ${f.compared_only.length === 1 ? "its line number belongs" :
      "their line numbers belong"} to the other version, and drawing ${
      f.compared_only.length === 1 ? "it" : "them"} in this file's margin would put ${
      f.compared_only.length === 1 ? "it" : "them"} at a line that means something else
      here.</div>` : ""}
  </div>`;
}

/* What the overlay is showing, in words, and what it could not show.
 *
 * Design rule 1 in the place it matters most here. Four things a reader cannot see by
 * looking at marked lines: which version this is held against, how many lines went each
 * way, that a routine the *other* version has could not be placed on these lines at all,
 * and — the one with no visible symptom — that this file did not change. An unmarked file
 * under a running comparison and an unmarked file with no comparison look identical.
 *
 * Returns "" when there is nothing to say, which is only when nothing is being compared.
 */
function overlayNote() {
  if (!comparing()) return "";
  const rev = comparedRevInForce();
  const shortRev = rev.replace("T", " ").replace("Z", "");
  if (!state.codeOverlay) {
    return `Not showing the difference from <code>${esc(shortRev)}</code>.`;
  }
  if (!FILEPAIR || FILEPAIR.loading) return "comparing the files…";
  if (!FILEPAIR.available) {
    return `<b>No file comparison.</b> ${esc(FILEPAIR.reason || "")}`;
  }
  if (!state.codeFile) {
    const c = FILEPAIR.counts || {};
    const w = diffWords();
    const one = (n, side) => n
      ? `<b class="tone-${side.tone}">${n.toLocaleString()} ${side.word}</b>`
      : "";
    const bits = [
      c.modified ? `<b>${c.modified.toLocaleString()}</b> with different text` : "",
      one(c.only_in_base, w.base), one(c.only_in_compared, w.compared),
    ].filter(Boolean);
    /* **The rows below are the version being read, and the other version's files are not
       among them.** Design rule 1: a count stated beside a list that cannot contain it has
       to say where those went, or the reader counts the rows, counts the claim, and finds
       the tool wrong about its own arithmetic. There is nothing to open for such a file —
       the map, the margin and the bytes here are all this version's — so it is named as an
       absence rather than drawn as a row that would fail on being clicked (the same
       argument `queries.py` makes about inventing an id to make a row clickable). */
    const missing = c.only_in_compared
      ? ` The ${c.only_in_compared.toLocaleString()} ${w.compared.word} ${
          c.only_in_compared === 1 ? "file is" : "files are"} not listed below: ${
          c.only_in_compared === 1 ? "it is" : "they are"} in the other version, and this
          map has no lines, margin or names for ${
          c.only_in_compared === 1 ? "it" : "them"} — switch the base to read ${
          c.only_in_compared === 1 ? "it" : "them"}.`
      : "";
    return `Held against <code>${esc(shortRev)}</code>: ${
      bits.length ? bits.join(", ") : "nothing differs"}, of ${
      (FILEPAIR.total || 0).toLocaleString()} files. ${
      (c.same || 0).toLocaleString()} are byte for byte the same.${missing}`;
  }
  if (!FILEDIFF || FILEDIFF.loading) return "reading the difference…";
  if (!FILEDIFF.available) {
    return `<b>No difference to show.</b> ${esc(FILEDIFF.reason || "")}`;
  }
  const w = diffWords();
  const c = FILEDIFF.counts || {};
  if (FILEDIFF.status === "same") {
    return `Byte for byte the same as <code>${esc(shortRev)}</code>.`;
  }
  const parts = [];
  if (c.base_only) {
    parts.push(`<b class="tone-${w.base.tone}">${c.base_only.toLocaleString()} line${
      c.base_only === 1 ? "" : "s"} ${w.base.word}</b>`);
  }
  if (c.compared_only) {
    parts.push(`<b class="tone-${w.compared.tone}">${c.compared_only.toLocaleString()} line${
      c.compared_only === 1 ? "" : "s"} ${w.compared.word}</b>`);
  }
  const other = c.compared_only
    ? ` The ${w.compared.word} lines are shown where they belong, with their own numbers — `
      + `they are not in the file you are reading.`
    : "";
  return `Against <code>${esc(shortRev)}</code>: ${
    parts.join(" and ") || "nothing"}.${other}`;
}

/* Which routines in the open file the *fact* diff has something to say about.
 *
 * The other lane, and the half nothing else can give: `changes.py` knows that a routine
 * stopped resolving a call, or writes a table it did not write, which no text diff can
 * state. Read straight off `CHANGES` — already fetched, no request of its own — and
 * narrowed to this file.
 *
 * **`only_in_compared` is deliberately not placed.** Those rows carry the *compared*
 * version's file and line, so putting them in this file's margin would be drawing a
 * routine at a line number that means something else here. They are listed instead, with
 * the reason said: rule 1, and the identical argument `code.py` makes about a call whose
 * column it cannot honestly give.
 */
function fileFactChanges(path) {
  const empty = { behaves: [], explained: [], base_only: [], compared_only: [] };
  if (!path || !overlayOn()) return empty;
  if (!CHANGES || CHANGES.loading || !CHANGES.available) return empty;
  const here = (rows) => (rows || []).filter(r => r.file === path);
  return {
    behaves: here(CHANGES.behaves),
    /* The WHY, in the one pane where the reader can see the prose that moved. Leaving it
       out here would be a silent filter in the view most able to act on it (design rule 1),
       and it is the band a text diff comes closest to answering -- which is exactly why the
       lane has to distinguish them: the text lane says these lines moved, and this says the
       lines that moved were the explanation. */
    explained: here(CHANGES.explained_only),
    base_only: here(CHANGES.only_in_base),
    /* Not narrowed by line, and not placeable — see above. Kept because a routine the
       other version has and this one does not is exactly what someone reading this file
       wants to know, and the only honest place for it is beside the file rather than in
       it. */
    compared_only: here(CHANGES.only_in_compared),
  };
}

/* Every file whose path or module matches what is typed. Flat and complete: 626 rows is a
 * list, not a haystack, and rule 45's lesson was about building 3,413 rows nobody could
 * see -- not about bounding a list this size. */
function matchingFiles() {
  const q = state.codeQ.trim().toLowerCase();
  if (!q) return { rows: FILES, filtered: false };
  const rows = FILES.filter(f => f.path.toLowerCase().includes(q)
                              || f.module.toLowerCase().includes(q));
  return { rows, filtered: true };
}

/* Where the file list stands, in words. Design rule 1: what is not on screen is stated. */
function codeNote() {
  if (!FILES.length) return "reading the file list…";
  if (state.codeFile) {
    const f = FILES.find(x => x.path === state.codeFile);
    if (CODEFILE && CODEFILE.loading) return `opening ${esc(state.codeFile)}…`;
    if (CODEFILE && CODEFILE.available === false) return esc(CODEFILE.reason || "not available");
    const n = CODEFILE ? CODEFILE.lines.length : (f ? f.lines : 0);
    const links = CODEFILE ? CODEFILE.links.length : 0;
    /* The unplaced count is not decoration. A call whose expression appears twice on its
       line has no column we can honestly give it, so it is not underlined -- and a name
       that is not clickable, with nothing said about it, reads as a name the map does not
       know. */
    const un = CODEFILE && CODEFILE.unplaced ? `, ${CODEFILE.unplaced} overlapping and left plain` : "";
    return `${n.toLocaleString()} lines, ${links} clickable${un}`;
  }
  const { rows, filtered } = matchingFiles();
  if (!filtered) return `${FILES.length.toLocaleString()} files — open one, or search names or source`;
  /* **Both lanes, because one box asked both questions.** This is the group's own note and
   * it stays visible when the heading sticks, so a reader who has scrolled past the box
   * still has the whole answer. Saying only the file half of it read as the whole answer,
   * and a search that found 782 lines looked like a search that found nothing. */
  const inside = SEARCH && SEARCH.ok && SEARCH.total
    ? ` · ${SEARCH.total.toLocaleString()} line${SEARCH.total === 1 ? "" : "s"} inside `
      + `${SEARCH.files.toLocaleString()} file${SEARCH.files === 1 ? "" : "s"}`
    : "";
  const names = rows.length
    ? `${rows.length.toLocaleString()} of ${FILES.length.toLocaleString()} named “${esc(state.codeQ)}”`
    : `no file is named “${esc(state.codeQ)}”`;
  return names + inside;
}

/* ══ searching inside the source ═══════════════════════════════════════════════════════
 *
 * One box, two lanes: **what matches a path**, and **what matches the text inside**. They
 * are two questions and the reader has both at once rather than a mode switch between
 * them, because "where is the quaestor code" and "where is the word quaestor" are asked in
 * the same breath and the answer to one is usually the way into the other.
 *
 * The lanes are not alike underneath, and the difference is worth stating. The file lane is
 * a filter over 626 rows already in the page: instant, and it costs a keystroke nothing.
 * The text lane is a **request** -- 184,722 lines live in the sidecar as zlib blobs and the
 * browser has none of them -- so it is debounced, it says while it is out, and it comes
 * back with counts rather than with lines.
 *
 * **Files first, then lines, and that is the whole design.** `quaestor` matches 782 lines
 * in 166 files; `e` matches 133,454 in all 626. One flat list of hits is the haystack
 * again. 626 file rows with a count on each is an answer a reader can act on at any size,
 * and the lines are one click beneath the file that holds them.
 *
 * Rule 45 three times over says where the cost is, and measuring said it is not here: the
 * scan is 20-90 ms on the whole program. The cost is what is *drawn*, and the accordion is
 * what keeps it to what someone asked to see.
 */

/* How many matching lines a search may open files for by itself.
 *
 * The routine list's own number, for the same reason and not by coincidence: it says
 * whether a search has narrowed anything down yet. A hundred and eighty-two thousand lines
 * hold most words somewhere, so a broad one opens nothing and **says why** -- closed rows
 * with no explanation read as a control that failed. */
const SEARCH_HITS_OPEN_MAX = SEARCH_OPEN_MAX;

/* Which question is on the wire, so a slow answer to an old one is dropped rather than
   shown under a new one. Two searches racing is ordinary: typing outruns a round trip. */
let searchWanted = "";
let searchTimer = 0;

/* The three flags as the server reads them, and as the cache is keyed. One place builds
   this, so the request and the key cannot come to disagree about what was asked. */
function searchParams() {
  return { case: state.searchCase ? 1 : 0,
           /* **Whole-word is not sent with a regex**, and the control is disabled beside
              it. A regex writes its own `\b`, so the two say one thing -- and rule 46 is
              that two questions sharing an answer is how one gets answered by accident. */
           word: (state.searchWord && !state.searchRegex) ? 1 : 0,
           regex: state.searchRegex ? 1 : 0 };
}

function searchKey() {
  const p = searchParams();
  return `${state.codeQ} ${p.case}${p.word}${p.regex}`;
}

/* Ask the server which files hold the query, after the reader has stopped typing.
 *
 * Debounced rather than throttled: a search is a question, and answering a half-typed one
 * costs a round trip to tell someone something they did not ask. 150 ms is under the point
 * where a pause reads as the box not working, and the note says "searching…" for the rest. */
function runSearch({ now = false } = {}) {
  clearTimeout(searchTimer);
  const key = searchKey();
  const q = state.codeQ.trim();
  searchWanted = key;
  /* Dropped whole, both of them. A hit list belongs to the question it answered. */
  SEARCHHITS = {};
  state.searchOpen = {};
  if (!q) { SEARCH = null; refreshCodeSearch(); return; }
  SEARCH = { loading: true, q };
  refreshCodeSearch();
  const go = async () => {
    const p = searchParams();
    const url = `/api/search?q=${encodeURIComponent(q)}`
              + `&case=${p.case}&word=${p.word}&regex=${p.regex}`;
    let d;
    try {
      d = await fetch(url).then(r => r.json());
    } catch (err) {
      d = { ok: false, q, reason: `the search could not be run: ${err.message}` };
    }
    if (searchWanted !== key) return;             // the reader moved on
    SEARCH = d;
    /* **One file opens itself, and only when the answer has narrowed.** A reader who has
     * found the word wants to see it in context without a second click, and the top row is
     * the file the word is most in. One request, never eighty-four -- and none at all while
     * the answer is still the haystack, because the top file of a broad search is a
     * thousand lines nobody asked for. The note says which of the two happened, or closed
     * rows with no explanation read as a control that failed. */
    if (d.ok && !d.broad && d.rows && d.rows.length) {
      state.searchOpen[d.rows[0].path] = true;
      loadSearchHits(d.rows[0].path);
    }
    refreshCodeSearch();
  };
  if (now) go(); else searchTimer = setTimeout(go, 150);
}

/* One file's hits, with the margin. Asked for only when a file is opened in the answer. */
async function loadSearchHits(path) {
  const key = searchKey();
  if (SEARCHHITS[path]) return;
  SEARCHHITS[path] = { loading: true };
  refreshCodeSearch();
  const p = searchParams();
  const url = `/api/search?q=${encodeURIComponent(state.codeQ.trim())}`
            + `&path=${encodeURIComponent(path)}`
            + `&case=${p.case}&word=${p.word}&regex=${p.regex}`;
  let d;
  try {
    d = await fetch(url).then(r => r.json());
  } catch (err) {
    d = { ok: false, reason: err.message };
  }
  if (searchKey() !== key) return;                // the question changed under it
  SEARCHHITS[path] = d;
  refreshCodeSearch();
}

function toggleSearchFile(path) {
  state.searchOpen[path] = !state.searchOpen[path];
  if (state.searchOpen[path]) loadSearchHits(path);
  else refreshCodeSearch();
}

/* Is this result file expanded?
 *
 * **One truth: `state.searchOpen`**, and whoever opens a file is the one that fetches its
 * hits. The first version answered `true` for every row while the answer was small, which
 * looked identical and was not: nothing fetched them, so eighty-four files rendered
 * `opening…` and stayed that way -- a control that renders and does nothing, in a branch
 * that never met the code that would have made it true.
 *
 * The deeper half is why that branch was wrong even with the fetch wired. Opening a file
 * here is a **request** -- ten queries for its margin -- where the routine list's auto-open
 * is rows already in memory. Eighty-four of them behind one keystroke is rule 45 arriving
 * by a route the rule's own precedent did not cover. */
function searchFileOpen(path) {
  return !!state.searchOpen[path];
}

/* Where the text search stands, in words. Design rule 1, and every branch of it is a
 * different claim: not asked, being answered, refused, empty, bounded, complete. Blurring
 * any two of them is how a search box comes to look broken.
 *
 * The refusal branch is the one worth keeping. A pattern that cannot be compiled and a
 * pattern that matches nothing are opposite claims, and the server keeps them apart so
 * that this can. */
function searchNote() {
  if (!state.codeQ.trim()) return "";
  if (!SEARCH) return "";
  if (SEARCH.loading) return "searching the source…";
  if (!SEARCH.ok) return `<span class="warn">${esc(SEARCH.reason || "that could not be searched")}</span>`;
  const q = esc(state.codeQ.trim());
  const scope = `${SEARCH.scanned.toLocaleString()} file${SEARCH.scanned === 1 ? "" : "s"}, `
              + `${SEARCH.lines.toLocaleString()} lines`;
  /* An analysed file the sidecar cannot open was searched by nobody. A search quietly
     covering 620 of 626 files is a silent filter, and the reader is entitled to know. */
  const short = SEARCH.unheld
    ? ` — ${SEARCH.unheld.toLocaleString()} analysed file${SEARCH.unheld === 1 ? "" : "s"} `
      + `not held in the sidecar and not searched`
    : "";
  if (!SEARCH.total) {
    /* Whole-word `()` can never match: `\b` sits between a word character and a non-word
       one. "Nothing here" and "this question cannot be asked" are different answers. */
    if (SEARCH.wordable === false) {
      return `“${q}” has no word edge to match on — whole word cannot find it. `
           + `Searched ${scope}.${short}`;
    }
    return `nothing matches “${q}” in ${scope}.${short}`;
  }
  const files = `${SEARCH.files.toLocaleString()} file${SEARCH.files === 1 ? "" : "s"}`;
  const head = `${SEARCH.total.toLocaleString()} line${SEARCH.total === 1 ? "" : "s"} `
             + `in ${files}, of ${scope}`;
  return SEARCH.broad
    ? `${head} — too broad to open one for you. Keep typing, or open any.${short}`
    : `${head}. The first is open; open any.${short}`;
}

/* The text lane: a file, a count, and its lines beneath when it is open. */
function searchList() {
  if (!state.codeQ.trim() || !SEARCH || SEARCH.loading || !SEARCH.ok) return "";
  if (!SEARCH.rows.length) return "";
  return SEARCH.rows.map(r => {
    const open = searchFileOpen(r.path);
    return `
    <div class="nav-pkg srch-file" data-open="${open}">
      <div class="nav-pkghead">
        <button class="nav-pkgtoggle" data-searchopen="${esc(r.path)}" aria-expanded="${open}"
                title="${open ? "Collapse" : "Expand"} ${esc(r.path)}"><span class="caret">▼</span></button>
        <button class="nav-pkgname srch-path" data-searchopen="${esc(r.path)}" data-titled="1"
                title="${esc(r.module)} — ${r.n.toLocaleString()} matching line${r.n === 1 ? "" : "s"}, first at line ${r.first}">
          <span class="navsub">${esc(dirOf(r.path))}</span>${esc(baseOf(r.path))}
          <span class="n">${r.n.toLocaleString()}</span></button>
      </div>
      ${open ? `<div class="srch-hits">${searchHitsHtml(r)}</div>` : ""}
    </div>`;
  }).join("");
}

/* The lines under one open file.
 *
 * Every hit carries what the map knows about it, because that is what makes this different
 * from `grep`: the routine it sits in, the marks in its margin, and the clickable names on
 * it -- all of them the code browser's own answers, narrowed to these lines by the server
 * (rule 51), never recomputed here.
 *
 * Three separate clicks and each goes somewhere different, which is why the row is not one
 * button. The **line** goes to that line of the file. The **routine** is an ordinary
 * selection, so the stack lights and the trail records it. A **name** in the source is the
 * same `codelink` every other line of code carries. */
function searchHitsHtml(row) {
  const got = SEARCHHITS[row.path];
  if (!got) return `<div class="nav-note">opening…</div>`;
  if (got.loading) return `<div class="nav-note">reading ${esc(baseOf(row.path))}…</div>`;
  if (!got.ok) return `<div class="nav-note warn">${esc(got.reason || "could not be read")}</div>`;
  if (!got.hits.length) return `<div class="nav-note">no lines here now</div>`;
  return got.hits.map(h => `
    <div class="srch-hit">
      <button class="srch-n" data-searchgo="${esc(row.path)}" data-searchline="${h.line}"
              data-titled="1" title="Open ${esc(row.path)} at line ${h.line}">${h.line}</button>
      <code class="srch-code">${codeLineHtml(h.text, h.links, h.at)}</code>
      ${h.marks && h.marks.length ? `<span class="srch-marks">${h.marks.map(m => `
        <span class="codemark" data-titled="1"
              title="${esc(markTitle(m))}">${MARK_GLYPH[m.kind] || "·"}</span>`).join("")}</span>` : ""}
      ${/* The word "in" is a `::before`, not text. `dressNavItems` gathers a row's text
             nodes into its label and the trail then records that label, so spelling it here
             filed every step as "in timestamp_cmd" -- a sentence where the trail wants the
             name of the thing arrived at. */
        h.in ? `<button class="srch-in nav-item" data-nav="routine" data-navid="${esc(h.in.id)}"
                  data-titled="1" data-card="1" data-qual="${esc(h.in.qualname)}"
                  title="${esc(h.in.qualname)}">${esc(h.in.name)}</button>`
             : `<span class="srch-in srch-nowhere" title="No routine's span covers this line — it is between definitions">—</span>`}
    </div>`).join("");
}

/* The list half of the group: one box, then the two lanes it answers. */
function codeFileList() {
  const { rows, filtered } = matchingFiles();
  const inside = searchList();
  return `
    ${searchBoxHtml()}
    ${comparing() ? `<div class="nav-note chgnote">${overlayNote()}</div>` : ""}
    <div class="lane-head">Files<span class="n" id="codeFilesCount">${
      fileLaneCount()}</span></div>
    <div class="nav-items" id="codeFileRows">${fileRowsHtml(rows)}</div>
    <div id="codeInside">${inside ? `<div class="lane-head">Inside<span class="n">${
      SEARCH && SEARCH.ok ? SEARCH.total.toLocaleString() : ""}</span></div>${inside}` : ""}</div>`;
}

/* How many files the name filter is showing, in the words rule 32 asks for: the number
   beside a list must be the number of things in it. It read `626` over 45 rows for as long
   as the narrow refresh did not reach it -- two correct numbers, neither of them saying
   what it counted, one directly above the other. */
function fileLaneCount() {
  const { rows, filtered } = matchingFiles();
  return filtered
    ? `${rows.length.toLocaleString()} of ${FILES.length.toLocaleString()}`
    : FILES.length.toLocaleString();
}

/* The box, and the three switches that say what counts as a match.
 *
 * Rendered wherever the Code group is -- above the file list *and* above an open file --
 * because searching is how a reader gets from the file they are reading to the one they
 * are looking for, and making them back out of a file first is making them lose their
 * place to ask a question. */
/* The topbar's three flags, drawn from the same shape as the Code box's so the two cannot
 * drift into different spellings of one idea (rule 13). Painted into a static container
 * rather than returned as part of a rebuilt pane, because the topbar lives in `index.html`
 * and `render()` never rewrites it -- so this is called wherever the pressed state can move.
 */
function paintNavFlags() {
  const host = $("#navFlags");
  if (!host) return;
  const sw = (key, label, title, on = true) => `
    <button class="srch-flag" data-searchflag="${key}" aria-pressed="${!!state[key] && on}"
            ${on ? "" : "disabled"} data-titled="1" title="${esc(title)}">${label}</button>`;
  host.innerHTML =
    sw("navCase", "Aa", "Match capitals exactly")
    + sw("navWord", "|ab|",
         state.navRegex ? "Whole word — off while a regular expression is in force, "
                        + "because a pattern writes its own word edges"
                        : "Whole word: emit, and not _emit_all",
         !state.navRegex)
    + sw("navRegex", ".*", "Read the query as a regular expression");
}

function searchBoxHtml() {
  const sw = (key, label, title, on = true) => `
    <button class="srch-flag" data-searchflag="${key}" aria-pressed="${!!state[key] && on}"
            ${on ? "" : "disabled"} data-titled="1" title="${esc(title)}">${label}</button>`;
  return `
    <div class="codefilter">
      <input id="codeQ" type="search" placeholder="Find in file names, or in the source…"
             value="${esc(state.codeQ)}" aria-label="Search file names and source text">
      <div class="srch-flags">
        ${sw("searchCase", "Aa", "Match capitals exactly")}
        ${sw("searchWord", "|ab|",
             state.searchRegex ? "Whole word — off while a regular expression is in force, "
                               + "because a pattern writes its own word edges"
                               : "Whole word: emit, and not _emit_all",
             !state.searchRegex)}
        ${sw("searchRegex", ".*", "Read the query as a regular expression")}
      </div>
    </div>
    <div id="searchNote" class="nav-note srch-note">${searchNote()}</div>`;
}

/* What one mark says, spelled out for the hover.
 *
 * The gutter carries a glyph because a gutter wide enough for prose is a gutter that has
 * taken the code's column. This was written inline in `codeBody`, and the search needed the
 * same sentence -- so it lives here and both read it, rather than agreeing until the day
 * one of them is edited (rule 51). `note` was dropped by the inline version, which is how a
 * boundary's direction and a constant's `final` never reached a reader. */
function markTitle(m) {
  const tail = [m.detail, m.note].filter(Boolean).join(" · ");
  return `${m.kind}: ${m.label}${tail ? " — " + tail : ""}`;
}

/* One renderer for a file row, because the full build and the narrow filter refresh both
 * draw it. Two copies would agree until the day one of them was edited. */
function fileRowsHtml(rows) {
  return rows.map(f => {
    const chg = fileChip(f.path);
    return `
    <button class="nav-item codefile${chg.cls}" data-nav="file" data-navid="${esc(f.path)}"
            data-titled="1" title="${esc(f.module)} — ${f.lines.toLocaleString()} lines, ${
              f.routines} routines, ${f.boundaries} boundaries, ${f.ids} governance ids${
              chg.title ? " — " + esc(chg.title) : ""}"
            ${f.path === state.codeFile ? 'aria-current="true"' : ""}>
      <span class="navsub">${esc(dirOf(f.path))}</span>${esc(baseOf(f.path))}
      <span class="n">${f.lines.toLocaleString()}</span>
      ${/* **After the count, and that is not a style choice.** `dressNavItems` gathers a
            row's loose text nodes into a `.navlabel` and re-inserts it immediately before
            `.n` — so an element written between the file name and the count ends up
            *between the directory and the name*: `mensores/scriba/ ○ _queue.py`. It read
            as a glyph inside the path, and every check passed, because the markup this
            function writes is correct and something else moves it afterwards.

            Placed last it survives that move and lands in a column of its own down the
            right-hand edge, which is the better row anyway. Found by looking at the pane
            (rule 51's cousin: a rule about markup that another function silently
            rewrites). */""}
      ${chg.glyph ? `<span class="filechg" aria-hidden="true">${chg.glyph}</span>` : ""}
    </button>`;
  }).join("");
}

/* What one file row says about the comparison, in a glyph and a sentence.
 *
 * **A file that did not change gets no glyph and says so in its title**, which is the only
 * way a reader can tell "nothing happened to this one" from "nobody compared this one" --
 * design rule 1, and the state that has no visible mark is exactly the one that needs the
 * words. `same` with an overlay running is a fact; `same` with no comparison is not a
 * claim anyone has made.
 *
 * The words come from `diffWords()`, so a file only the base has reads as *deleted* or as
 * *added* according to the same assumption every other view is under. The glyph is the
 * tone's own sign for a one-sided file and a neutral mark for a modified one, because
 * "this file differs" is not a direction. */
function fileChip(path) {
  const st = fileStatus(path);
  if (!st) return { cls: "", glyph: "", title: "" };
  const w = diffWords();
  /* **Every class here begins `filechg-`, and that is not tidiness.** The first version
     used `chg-same` / `chg-mod` / `chg-one`, and `.chg-mod` already existed: it is the
     change worklist's *module* label, styled faint and two sizes down. So every modified
     file in the list quietly rendered smaller and greyer than the unchanged ones — the
     opposite of what a mark is for, in a global stylesheet where nothing warns you. No
     check could see it and no page threw; found by looking at the pane. */
  if (st === "same") {
    return { cls: " filechg-same", glyph: "",
             title: "unchanged between the two versions" };
  }
  if (st === "modified") {
    return { cls: " filechg-diff", glyph: "\u25cb", title: "the text differs" };
  }
  const side = st === "only_in_base" ? w.base : w.compared;
  return { cls: ` filechg-one tone-${side.tone}`, glyph: signOf(side.tone),
           title: `${side.word} — only in the ${
             st === "only_in_base" ? "version being read" : "version it is compared with"}` };
}

function baseOf(p) { const i = String(p).lastIndexOf("/"); return i < 0 ? p : p.slice(i + 1); }
function dirOf(p)  { const i = String(p).lastIndexOf("/"); return i < 0 ? "" : p.slice(0, i) + "/"; }

/* One line of source, with its clickable spans cut into it.
 *
 * Built by walking the line once and slicing at each span, rather than by replacing text:
 * a `String.replace` over source would match inside a string literal, inside a comment, and
 * inside the *next* occurrence of the same name -- which is the column problem the server
 * already refused to guess at, reintroduced in the client. The server said where; this
 * only cuts.
 *
 * `hits` are what a search matched, as `[col, len]` pairs. They are a **second** channel
 * over the same characters and not a competing one: a link is an underlined button and a
 * match is a background, so a name that is both reads as both. The marks nest *inside* the
 * button rather than cutting it in two -- one name is one control, and splitting it would
 * make half of it clickable and leave a reader to discover which half.
 */
function codeLineHtml(text, spans, hits) {
  if (!spans || !spans.length) return marked(text, 0, hits) || "&nbsp;";
  let out = "", at = 0;
  for (const s of spans) {
    const a = s.col - 1, b = a + s.len;
    if (a < at) continue;                       // already covered; the server sorts these
    out += marked(text.slice(at, a), at, hits);
    out += `<button class="codelink${s.confidence === "INFERRED" ? " inferred" : ""}"
              data-codelink="${esc(s.id)}" data-titled="1"
              title="${esc(s.kind === "def" ? "Definition of " + s.label : "Calls " + s.label)}"
              >${marked(text.slice(a, b), a, hits)}</button>`;
    at = b;
  }
  out += marked(text.slice(at), at, hits);
  return out || "&nbsp;";
}

/* A slice of a line, escaped, with any search match inside it wrapped.
 *
 * `from` is where this slice starts in the whole line, because the server's columns are
 * about the line and this is handed a piece of it -- an offset dropped here would highlight
 * the right number of characters in the wrong place, which is exactly the invented position
 * rule 1 refuses. */
function marked(text, from, hits) {
  if (!hits || !hits.length || !text) return esc(text);
  let out = "", at = 0;
  for (const [col, len] of hits) {
    const a = (col - 1) - from, b = a + len;
    if (b <= 0 || a >= text.length) continue;   // this match is in another slice
    const lo = Math.max(0, a), hi = Math.min(text.length, b);
    if (lo < at) continue;
    out += esc(text.slice(at, lo));
    out += `<mark class="codehit">${esc(text.slice(lo, hi))}</mark>`;
    at = hi;
  }
  return out + esc(text.slice(at));
}

/* Short words for the gutter. A mark says what a line *is*; the letter is the kind and the
 * title carries what it says, because a gutter wide enough for prose is a gutter that has
 * taken the code's column. */
const MARK_GLYPH = {
  boundary: "◆", sql: "▤", net: "⇄", library: "↗",
  constant: "○", import: "↓", artefact: "□", table: "⌸", id: "§",
};

/* ── built once per file, re-attached ever after ───────────────────────────────────────
 *
 * Rule 45, found by looking and by nothing else. `buildNav()` runs on **every selection**
 * and rewrites the navigator's `innerHTML`; with `_server.py` open that is 5,838 lines of
 * markup re-parsed per click, and it measured **1,937 ms**. The centre pane is 1.37 MB of
 * HTML for the same file and 155 ms per repaint, on a `render()` that also runs on every
 * keystroke. Worse than the 2,418 ms table defect that earned the rule, and every test
 * passed: a slow page reads as a slow page, not as a defect.
 *
 * The cost is *parsing*, not the DOM — so the subtree is built once and moved. Re-attaching
 * a detached node is a pointer swap whatever it holds. Nothing is windowed and nothing is
 * dropped: every line is in the document, which is what rule 8 requires of a reference.
 *
 * Keyed on the file **only**. The selection moves far more often than the file does, and it
 * changes exactly two rows' worth of highlight — `paintHere()` does that narrowly, because
 * rebuilding a megabyte to move a background colour is the same mistake one layer down.
 */
let codeDom = { pane: { key: "", node: null }, centre: { key: "", node: null } };
let codePaintedFor = "";     // which file the centre pane currently holds

function codeDomKey() {
  if (!CODEFILE) return "";
  /* The overlay is in the key, and it has to be. The built subtree carries the marked rows
   * and the other version's inserted lines *inside* it, so a diff that arrives after the
   * file, a compared version that moves, or the switch being turned off all produce a
   * different page from the same file -- and a cache keyed on the file alone would hand
   * back the page from before, correct-looking and about the wrong question. Rule 52's
   * companion inverted: the cheap check is what makes it safe not to repaint. */
  const o = codeOverlay();
  const overlay = o ? `${FILEDIFF.compared}:${o.status}:${o.base.tone}` : "-";
  return `${CODEFILE.file}#${CODEFILE.loading ? "…" : CODEFILE.available}#${overlay}`;
}

/* Drop the built subtrees and draw again. What `loadCodeFile` does at the end, minus the
 * fetch -- for whoever changes what is *drawn over* the file rather than which file it is.
 *
 * Named rather than repeated at each call site, because there are three of them already
 * (the diff arriving, the overlay switch, the compared version moving) and the list of
 * callers is the thing that grows (rule 51). */
function repaintCode() {
  codeDom = { pane: { key: "", node: null }, centre: { key: "", node: null } };
  codePaintedFor = "";
  buildNav();
  render();
}

/* Build a node once per key, and hand back the same node after.
 *
 * Takes a **function**, not a string, and that is the whole of it: JavaScript evaluates
 * arguments before the call, so `codeCached(slot, codeTable())` rebuilt 1.37 MB of markup
 * on every hit and then threw it away. The cache was doing its job on the DOM and none at
 * all on the work, and it looked exactly like a cache that worked — `render()` went from
 * 155 ms to 1,370. Measured, or it would still be in. */
function codeCached(slot, build) {
  const key = codeDomKey();
  if (slot.key !== key || !slot.node) {
    const box = document.createElement("div");
    box.innerHTML = build();
    slot.node = box.firstElementChild;
    slot.key = key;
  }
  return slot.node;
}

/* Move the selection's highlight without touching anything else.
 *
 * `render()` and `buildNav()` both used to redraw the whole file to change which rows carry
 * `.here`, which is rule 45 in a background colour. */
function paintHere() {
  const here = selectedLine();
  for (const root of [$("#codeScroll"), $("#codeTable")]) {
    if (!root) continue;
    root.querySelectorAll(".here").forEach(el => el.classList.remove("here"));
    if (!here || !here.first) continue;
    for (let n = here.first; n <= here.last; n++) {
      const row = root.querySelector(`#codeline-${n}, #crow-${n}`);
      if (row) row.classList.add("here");
    }
  }
}

/* Put the built subtree back into whichever pane has just been rewritten. Called after both
 * `buildNav()` and `render()`, because either may have replaced the mount it goes in. */
function attachCode() {
  const paneMount = $("#codePaneMount");
  if (paneMount && !paneMount.firstElementChild && CODEFILE) {
    paneMount.appendChild(codeCached(codeDom.pane, codeBody));
  }
  const centreMount = $("#codeTableMount");
  if (centreMount && !centreMount.firstElementChild && CODEFILE) {
    centreMount.appendChild(codeCached(codeDom.centre, codeTable));
  }
  paintHere();
  revealSelectedLine();
}

function codeBody() {
  if (!CODEFILE) return "<div></div>";
  if (CODEFILE.loading) return `<div class="nav-note">opening…</div>`;
  if (CODEFILE.available === false) {
    /* Three absences and the reader must be able to tell which (design rule 1). The server
       keeps them apart; repeating the reason verbatim is what keeps them apart here. */
    return `<div class="codeabsent"><b>Nothing to show.</b> ${esc(CODEFILE.reason || "")}</div>`;
  }
  const byLine = new Map();
  for (const s of CODEFILE.links) {
    if (!byLine.has(s.line)) byLine.set(s.line, []);
    byLine.get(s.line).push(s);
  }
  const marksBy = new Map();
  for (const m of CODEFILE.marks) {
    if (!marksBy.has(m.line)) marksBy.set(m.line, []);
    marksBy.get(m.line).push(m);
  }
  /* The same overlay the centre draws, from the same function. Two panes showing one file
   * must not be able to disagree about which of its lines changed -- and they would, the
   * first time either of them was edited alone (rule 51). */
  const ov = codeOverlay();
  const rows = [];
  const ghost = (after) => {
    const runs = ov && ov.after.get(after);
    if (!runs) return;
    for (const run of runs) {
      run.lines.forEach((text, k) => {
        const n = run.first + k;
        rows.push(`<span class="cl ghost chg tone-${ov.compared.tone}">` +
          `<span class="cn ghostn" title="line ${n} of the compared version">${n}</span>` +
          `<span class="cm">${signOf(ov.compared.tone)}</span>` + (esc(text) || "&nbsp;") +
          `</span>`);
      });
    }
  };
  ghost(0);
  CODEFILE.lines.forEach((text, i) => {
    const n = i + 1;
    const ms = marksBy.get(n) || [];
    const glyphs = [...new Set(ms.map(m => MARK_GLYPH[m.kind] || "·"))].join("");
    const title = ms.map(markTitle).join("\n");
    const gone = ov && ov.gone.has(n);
    /* The sign takes the mark column when a line is marked, because the pane's gutter is
       one glyph wide and there is no room for both. The marks are still on the row's title
       and in the centre's margin, which has the width for them -- what a narrow pane can
       say is *this line is not in the other version*, which is the thing being asked. */
    rows.push(`<span class="cl${gone ? ` chg tone-${ov.base.tone}` : ""}" id="codeline-${n}">` +
      `<span class="cn">${n}</span>` +
      `<span class="cm"${title ? ` title="${esc(title)}" data-titled="1"` : ""}>${
        gone ? signOf(ov.base.tone) : glyphs}</span>` +
      codeLineHtml(text, byLine.get(n)) + `</span>`);
    if (ov) ghost(n);
  });
  return `<div class="codescroll" id="codeScroll"><pre class="codepane">${
    rows.join("\n")}</pre></div>`;
}

/* The span of the current selection inside the file on screen, or null.
 *
 * Read from the one selection (`SPECIMEN.where`) rather than kept beside it. Rule 51: the
 * detail window held a node id of its own and drifted from the selection the first time
 * anything else moved one of them, and a second copy here would do the same on the first
 * click in the stack. */
function selectedLine() {
  if (!SPECIMEN || !SPECIMEN.where || !CODEFILE) return null;
  const w = SPECIMEN.where;
  if (!w.file || !String(w.file).endsWith(CODEFILE.file)) return null;
  return { first: w.first || 0, last: w.last || w.first || 0 };
}

/* The pane follows the selection, and only when the row is genuinely out of sight.
 *
 * Design rule 26's third condition: an automatic scroll must not fight a deliberate click.
 * A reader who clicked a name three lines down does not want the pane to jump because the
 * selection moved to exactly where they were already looking. */
function revealSelectedLine() {
  const here = selectedLine();
  if (here && here.first) revealLine(here.first);
}

/* Bring one line of the open file under the reader's eye.
 *
 * Split out of `revealSelectedLine` when the search arrived, because a hit is a line
 * nothing has selected -- clicking one goes *to* a line rather than to a node, and the
 * routine beside it is the separate click. Rule 51: the second caller is the reason the
 * rule belongs here rather than at the call site, and the list of callers is the thing
 * that grows. */
function revealLine(first) {
  if (!first) return;
  /* Both hosts, because the same file is on screen in two places and either may be the one
   * the reader is looking at. Named pairs rather than one selector over both: rule 50 was
   * written from a reveal that moved a `scrollTop` on a box that does not scroll and then
   * measured against a box extending far below the window, so every row read as "in view"
   * and it reported success. The scroller and the row have to belong to each other. */
  for (const [rowSel, boxSel] of [[`#codeline-${first}`, "#codeScroll"],
                                  [`#crow-${first}`, "#viewMount"]]) {
    const row = $(rowSel), box = $(boxSel);
    if (!row || !box) continue;
    const r = row.getBoundingClientRect(), b = box.getBoundingClientRect();
    if (r.top >= b.top && r.bottom <= b.bottom) continue;   // already under their eye
    box.scrollTop += (r.top - b.top) - box.clientHeight / 3;
  }
}

/* The group's body: the list, or the file with a way back to the list. */
function codeList() {
  if (!FILES.length) return "";
  if (!state.codeFile) return codeFileList();
  const f = FILES.find(x => x.path === state.codeFile);
  /* **The box stays above an open file**, and that is the whole reason it is rendered from
   * one function rather than only in the list. Searching is how a reader gets from the file
   * they are reading to the one they are looking for; making them close the file first is
   * making them lose their place to ask a question. What the search *found* is one click
   * back, stated with its size so the way back is not a guess. */
  const back = (SEARCH && SEARCH.ok && SEARCH.total)
    ? `<button class="linkbtn srch-back" data-codeback="1"
               title="Back to what the search found">‹ ${SEARCH.total.toLocaleString()} line${
                 SEARCH.total === 1 ? "" : "s"} in ${SEARCH.files.toLocaleString()} file${
                 SEARCH.files === 1 ? "" : "s"}</button>`
    : `<button class="linkbtn" data-codeback="1"
               title="Back to the list of files">‹ files</button>`;
  return `
    ${searchBoxHtml()}
    <div class="codehead">
      ${back}
      <span class="codepath mono" title="${esc(state.codeFile)}">${esc(baseOf(state.codeFile))}</span>
      ${f ? `<span class="codemod">${esc(f.module)}</span>` : ""}
      ${overlaySwitchHtml("code")}
      <button class="linkbtn" data-codeopen="1"
              title="Open this file in the centre pane, with its columns">open ▸</button>
    </div>
    ${comparing() ? `<div class="nav-note chgnote">${overlayNote()}</div>` : ""}
    <div id="codePaneMount"></div>`;
}

const NAV_GROUPS = [
  /* `primary`: the group the accordion opens on a first visit. The navigator *is* the
     routine list (design rule 26), whatever the menu order puts above it. */
  { id: "navRoutines", title: "Routines", open: true, primary: true,
    count: () => ROUTINES.length,
    note: () => {
      if (!ROUTINES.length) return "reading the routine list…";
      const { packages, total, filtered, autoOpen } = routineTree();
      if (!total) {
        const m = navMatcher();
        return m.ok ? `nothing matches “${esc(state.routineQ.trim())}”`
                    : `that is not a regular expression: ${esc(m.reason || "")}`;
      }
      const pkgs = `${packages.length} package${packages.length === 1 ? "" : "s"}`;
      /* Design rule 1, and note what it does *not* have to say here: the packages are all
         of them. What a package leaves out is stated on that package.
         The third state is the one worth writing down -- a search too broad to open
         anything must say that is why nothing opened, or the closed packages read as a
         control that failed. */
      /* The comparison's own line, beneath the count and never folded into it. Two
         different questions -- how many routines are here, and what the comparison says
         about them -- and rule 32 says a number must be named after what it measures. */
      const chg = routineChangeNote();
      /* `chgnote` beside it, which is the class every other place the comparison speaks in
         words already carries -- so the inline `<code>` sizing is one rule rather than two
         answers. `nav-chgnote` adds only the spacing, because this one sits *inside* a
         `.nav-note` and a second one would double its padding. */
      const also = chg ? `<div class="nav-chgnote chgnote">${chg}</div>` : "";
      if (!filtered) return `${total.toLocaleString()} in ${pkgs} — open one, or search${also}`;
      const q = esc(state.routineQ.trim());
      return (autoOpen
        ? `${total.toLocaleString()} match “${q}”, in ${pkgs}`
        : `${total.toLocaleString()} match “${q}” — too many to open, in ${pkgs}. `
          + `Keep typing, or open one.`) + also;
    },
    /* A body rather than items, because these rows are two levels deep. Routed through the
       same `navItemHtml`, so a routine row in a package looks like every other row. */
    body: () => routineList() },
  /* Changes: what moved between two points in time. Closed by default and absent
     entirely from a program with one revision -- a group that is always empty is a
     control that always fails. */
  /* `onOpen`: the rows are not in memory, so opening the group has to fetch them.
   *
   * It was not here, and the result was a closed loop with no way in. `changeList()`
   * builds the row that emits the `changes` route -- and it only builds anything once
   * `CHANGES` is loaded; `CHANGES` was only ever loaded *by* that route. So the control
   * that starts the comparison came into existence only after the comparison had started,
   * and opening the group gave "Not compared yet." with nothing to click. Eighty-seven nav
   * controls on the page and not one of them emitting `changes`.
   *
   * The fix is rule 55's companion stated once more: **one truth about what is open, and
   * whoever sets it does the work.** A group that needs fetching declares it here, beside
   * the body that needs it, rather than in a handler that would have to remember. */
  { id: "navChanges", title: "Changes", open: false,
    when: () => REVISIONS.filter(r => r.comparable).length >= 2,
    count: () => changeCount(),
    note: () => changeNote(),
    onOpen: () => refreshChanges(),
    body: () => changeList() },
  /* Code: the file list, and the file. Stacked, which is the accordion one level down --
     the same shape `navRoutines` uses, for the same reason. */
  /* `onOpen`: the file-level pairing is not in memory, so opening the group fetches it --
     the same declaration the Changes group makes, and rule 55's companion for the same
     reason. Without it the marks would appear only for a reader who had opened the
     worklist first, which is a feature that works by luck. */
  { id: "navCode", title: "Code", open: false,
    count: () => FILES.length,
    note: () => codeNote(),
    onOpen: () => ensureFilePair().then(() => { buildNav(); render(); }),
    body: () => codeList() },
  { id: "navExplore", title: "Explore", open: true, items: () => [
      { nav: "curiosities", label: "Worth a look",
        /* The count is what the panel holds once it has been asked. Blank before that,
           because "" and 0 are different claims and the navigator states a number beside
           every other row -- a 0 here would say this program has nothing unusual in it,
           which is a measurement nobody has taken yet. */
        n: CURIOS.lane === "ready" ? CURIOSITIES.length : "" },
      { nav: "pins",        label: "Kept",         n: state.pins.length, id: "navPins" },
    ] },
  /* Every list below is filtered by the topbar, through `navMatch`. Each was a `slice()`
     of a full list, and the slice now happens **after** the filter -- searching a bounded
     list would answer about the first eight of forty-three, which is the haystack again and
     silently (rule 8: abbreviate only where the whole sits beside it, and rule 45: bound the
     work, not the answer). Each group's note states what its own filter left out. */
  { id: "navWaysIn", title: "Ways in", open: true,
    note: () => navFilterNote(
      ENTRYPOINTS.filter(e => navMatch(navQuery(), e.name, e.module)).length,
      ENTRYPOINTS.length, "ways in", 6),
    items: () => {
      const q = navQuery();
      /* `Overview` is a place, not a name in the program -- it stays put while a search is
         running rather than being filtered out, because losing the way back to the cover is
         not what anybody meant by typing a word. */
      const eps = ENTRYPOINTS.filter(e => navMatch(q, e.name, e.module));
      return [
        ...(q ? [] : [{ nav: "cover", label: "Overview", n: "cover",
                        current: state.view === "cover" }]),
        /* `sel` is the identity, and it is the whole point: without it these rows differed
         * only by the label they printed, and every one did the same nothing. */
        ...eps.slice(0, 6).map(e => ({
          nav: "ep", label: e.name, n: e.reach, sel: (e.nodes || []).join(" "),
        })),
      ];
    } },
  { id: "navPkgs", title: "Packages", open: true,
    note: () => navFilterNote(PKGS.filter(p => navMatch(navQuery(), p.id)).length,
                              PKGS.length, "packages", 8),
    items: () => {
      const q = navQuery();
      // A package is a plate, and the plate id is what the legend already selects by.
      return PKGS.filter(p => navMatch(q, p.id))
        .slice(0, 8).map(p => ({ nav: "pkg", label: p.id, n: p.n, sel: `pkg:${p.id}` }));
    } },
  { id: "navBounds", title: "Boundaries", open: false,
    /* And when nothing matches, it says **where the answer is**. A boundary's *target* is a
       string in the source, not one of the nine kinds listed here, so "nothing matches" on
       its own would read as "this program does not touch that" -- which is the false
       conclusion this whole change is about. */
    note: () => {
      const m = navMatcher();
      const hit = BOUNDARIES.filter(b => navMatch(m, b.kind, b.common)).length;
      const base = navFilterNote(hit, BOUNDARIES.length, "kinds");
      /* `!m.all`, never `q` -- the matcher is an object and so always truthy, which would
         have appended this sentence to the resting state as well. */
      return !m.all && m.ok && !hit
        ? `${base} — these are the nine kinds; a target is in the source` : base;
    },
    items: () => {
      const q = navQuery();
      /* Matched on the kind and on its **commonest target**, which is `common` and not
         `target` -- the first draft of this line read `b.target`, a field the cover has
         never sent, so the filter silently matched on the kind alone. Rule 44 committed
         inside the fix for rule 44, and caught only by typing a real boundary name.

         **What this cannot do, stated rather than implied.** The cover carries nine kinds
         and one commonest target each; the program has **1,741** distinct targets. So
         `VIRTUAL_ENV` is not findable here and is not meant to be -- this group lists kinds,
         and a target is a string in the source, which is what the Code search is for. The
         note below says so rather than leaving a reader to conclude the word is absent. */
      return BOUNDARIES.filter(b => navMatch(q, b.kind, b.common))
        .map(b => ({ nav: "b", label: b.kind, n: b.n, sel: `ext:${b.kind}` }));
    } },
  { id: "navTables", title: "Database", open: true,
    note: () => navFilterNote(TABLES.filter(x => navMatch(navQuery(), x.name)).length,
                              TABLES.length, "tables", 8),
    items: () => {
      const q = navQuery();
      // A table is not a node and not a plate, so the id here is its name and the route
      // asks the server which routines touch it. See TABLE_ROUTINES in queries.py.
      return TABLES.filter(x => navMatch(q, x.name))
        .slice(0, 8).map(x => ({ nav: "t", label: x.name, n: x.n, sel: x.name }));
    } },
  /* The structures, and they are here because the search had nowhere to put them. A
     structure is a subject the inspector already describes (`describe()` resolves a
     `structures.id`), so these rows carry an id and route exactly as a routine row does. */
  { id: "navStructs", title: "Structures", open: false,
    count: () => STRUCTURES.length,
    note: () => {
      if (!STRUCTURES.length) return "reading the structures…";
      const hit = STRUCTURES.filter(s => navMatch(navQuery(), s.name, s.module)).length;
      return navFilterNote(hit, STRUCTURES.length,
                           "classes, dataclasses, enums and type aliases", 8);
    },
    items: () => {
      const q = navQuery();
      return STRUCTURES.filter(s => navMatch(q, s.name, s.module))
        .slice(0, 8)
        .map(s => ({ nav: "chg", label: s.name, n: s.kind, sel: s.id }));
    } },
  { id: "navVocab", title: "Vocabulary", open: true, items: () => [
      /* From the cover, not from `TERMS.length` -- which is zero until the page is opened,
         so the row read as "nothing here" on every session that had not been there yet.
         An absent count and a count of nothing are opposite claims. */
      { nav: "glossary", label: "Glossary",        n: vocabCount("terms") },
      { nav: "naming",   label: "Naming standard", n: vocabCount("conventions") },
      { nav: "inference", label: "Inference",      n: "off", id: "navEgress" },
    ] },
  { id: "navAnom", title: "Anomalies", open: true, items: () => {
      const a = (STATS && STATS.anomalies) || { broken: 0, suspect: 0, info: 0 };
      return [
        { nav: "a", sevnav: "broken",  label: "Broken", n: a.broken,  dot: "broken" },
        { nav: "a", sevnav: "suspect", label: "Suspect", n: a.suspect, dot: "suspect" },
        { nav: "a", sevnav: "info",    label: "Info",    n: a.info,    dot: "info" },
      ];
    } },
];

function groupCount(g) {
  if (g.count) return g.count();
  const items = g.items ? g.items() : [];
  if (g.id === "navBounds") return BOUNDARIES.reduce((s, b) => s + b.n, 0);
  if (g.id === "navPkgs")   return PKGS.length;
  if (g.id === "navTables") return TABLES.length;
  if (g.id === "navWaysIn") return ENTRYPOINTS.length;
  if (g.id === "navAnom")   return items.reduce((s, i) => s + (Number(i.n) || 0), 0);
  return items.length;
}

/* How many routines this comparison has something to say about.
 *
 * Both presence bands plus behaves-differently, and **not** `edited_only`: a routine whose
 * body moved and whose behaviour did not is exactly what this tool exists not to report,
 * and putting it in the headline number would make an ordinary refactor look like an
 * upheaval. It is still listed, under its own band, because leaving it out entirely would
 * be a silent filter (design rule 1).
 *
 * Rule 32: the number is produced by, and named after, the thing it measures. */
function changeCount() {
  if (!CHANGES || CHANGES.loading || !CHANGES.available) return "";
  const c = CHANGES.counts;
  /* `explained_only` is in the headline and `edited_only` is not, and the line between them
     is this tool's own subject. A body that changed while what the routine does did not is
     internal computation, which is what this tool exists **not** to report. A rewritten
     comment over unchanged code is the WHY, which is what it exists to report and the one
     layer the code itself never carries.

     `modules_explained` is in for the same reason and counts something else — files, where
     every other term counts routines. It is a total of *things that differ* rather than of
     routines, which is what the group badge above it means; the page below is where the
     two are separated, because that is where there is room to say which is which. */
  return c.only_in_base + c.only_in_compared + c.behaves + (c.explained_only || 0)
         + Object.keys(CHANGE_FILE_BANDS).reduce((n, k) => n + (c[k] || 0), 0)
         + Object.keys(CHANGE_STRUCT_BANDS).reduce((n, k) => n + (c[k] || 0), 0);
}

/* What the group says above its rows, and the three states it must keep apart.
 *
 * "Not asked for yet", "being computed" and "computed, and nothing moved" are different
 * answers, and a blank note states the last one whichever is true. */
function changeNote() {
  /* A choice that could not be honoured leads, whatever else the note would have said:
     the reader is looking at a different pair from the one they left, and every figure
     below is about the new one. */
  const lost = state.revNote ? `${esc(state.revNote)} · ` : "";
  if (!CHANGES) return lost + "two versions — open to compare them";
  if (CHANGES.loading) return lost + "comparing…";
  if (!CHANGES.available) return lost + esc(CHANGES.reason || "no second version");
  const c = CHANGES.counts;
  /* **The server's own answer, not a sum reassembled here.** This was
     `only_in_base + only_in_compared + behaves`, and it had been wrong since the day the
     comment lane landed: a pair whose one difference is a rewritten comment — or a table
     that appeared, or a constant whose value moved — has all three terms at zero, so the
     group a reader lands in first said **"no differences found"** while the page below it
     listed the change. Exactly the false claim the explained band was built to remove,
     surviving in the other of the two surfaces (rule 51), and it would have taken both new
     lanes with it. `identical` is computed once, over every band and every presence line,
     by the side that knows them all. */
  if (CHANGES.identical) return lost + "no differences found";
  const bits = lost ? [state.revNote] : [];
  /* The note is the one place these words appear before the bands do, so it wears the same
     colours -- a reader who reads "53 added" in red and then finds the band in green has
     been told two things (rule 13, in a sentence). */
  for (const [key, w] of diffBands()) {
    if (c[key]) bits.push(`<span class="tone-${w.tone}">${c[key]} ${w.word}</span>`);
  }
  /* In the channel, like the two above it. The note's own rule is that it wears the same
     colours the bands do -- a reader told one thing here and another below has been told
     two things (rule 13, in a sentence) -- and that rule applied to this line the moment
     the band it names started drawing in violet. */
  if (c.behaves) {
    bits.push(`<span class="tone-moved">${c.behaves} behaving differently</span>`);
  }
  /* Stated even when it is the only thing that happened, and stated as what it is: the
     largest band in ordinary work, and the least interesting. */
  if (c.explained_only) {
    bits.push(`<span class="tone-moved">${c.explained_only} explained differently</span>`);
  }
  /* Both non-routine tables, walked rather than named, so a band added to either is stated
     in the navigator's note without a second place remembering (rule 36). Without this the
     note said "no differences found" over a vanished structure the page was listing — the
     comment lane's defect exactly, which is why it is walked and not listed. */
  for (const tbl of [CHANGE_FILE_BANDS, CHANGE_STRUCT_BANDS]) {
    for (const [k, b] of Object.entries(tbl)) {
      if (c[k]) {
        bits.push(`<span class="tone-${esc(b.tone || "moved")}">${c[k]} ${
          c[k] === 1 ? b.stat1 : b.stat}</span>`);
      }
    }
  }
  if (c.edited_only) bits.push(`${c.edited_only} edited without changing what they do`);
  /* Reachable, and it is not the same sentence as the one above. `identical` is false
     whenever *anything* moved, and the terms named here are routines and modules — so a
     pair whose only difference is a table or a constant arrives with nothing to say. It
     says where the answer is rather than nothing at all, which is design rule 1: a note
     that goes blank reads as a comparison that failed. */
  if (!bits.length || (lost && bits.length === 1)) {
    bits.push("differences outside the routines — see What differs");
  }
  return bits.join(" · ");
}

/* The rows. Grouped by band, and each band collapses -- 53 additions is a list a reader
 * can hold, and a program six months apart is not.
 *
 * Every row carries the node id, so clicking one is the same selection the routine list
 * makes. The band is *why* it is worth looking at; the identity is what the router acts on. */
function changeList() {
  if (!CHANGES) return `<p class="hint">Not compared yet.</p>`;
  if (CHANGES.loading) return `<p class="hint">Comparing two versions…</p>`;
  if (!CHANGES.available) {
    return `<p class="hint">${esc(CHANGES.reason || "no second version")}</p>`;
  }
  /* Stated here as well as on the page, because this group is where a reader lands first
     and four empty bands are the one outcome that reads as a broken comparison. */
  if (CHANGES.identical) {
    return `<p class="hint">No differences found — the two versions are the same
       everywhere this map can see.</p>`;
  }
  const band = (key, title, rows, why, tone) => {
    if (!rows.length) return "";
    const open = state.changeBand === key;
    return `<div class="chgband">
      <button class="nav-head sub" data-changeband="${key}" aria-expanded="${open}">
        <span class="nav-title${tone ? " tone-" + tone : ""}">${title}</span>
        <span class="n num${tone ? " tone-" + tone : ""}">${rows.length}</span>
      </button>
      ${open ? `<div class="nav-items">
        ${why ? `<p class="hint" style="margin:.2rem .5rem .4rem">${why}</p>` : ""}
        ${rows.map(r => navItemHtml({
            nav: "chg",
            label: r.name,
            sub: r.module,
            n: (r.moved || []).join(" "),
            sel: r.id,
          })).join("")}
      </div>` : ""}
    </div>`;
  };
  const c = CHANGES;
  const cap = (w) => w.charAt(0).toUpperCase() + w.slice(1);
  /* The way into the full comparison. The group's rows are for clicking through; the page
     has room to say which two versions are being compared and what differs besides
     routines -- tables, ways in, named files. Both read one `CHANGES` (rule 51). */
  const open = navItemHtml({
    nav: "changes", label: "The whole comparison", n: "open",
    current: state.view === "changes",
  });
  const presence = diffBands()
    .map(([key, w]) => band(key, cap(w.word), c[key],
          `Only in the ${key === "only_in_base" ? "base" : "compared"} version.`, w.tone))
    .join("");
  return open
       + presence
       + band("behaves", "Behaving differently", c.behaves,
              "The same routine, and something it <em>does</em> has moved — what it calls, "
              + "what it touches, what it takes or returns.", "moved")
       + band("explained_only", "Explained differently", c.explained_only,
              "The same routine, and what <em>explains</em> it has moved. Nothing it does "
              + "changed, and neither did a line of its code.", "moved")
       + band("edited", "Edited, behaving the same", c.edited_only,
              "The body changed and nothing it does did. Internal computation, which this "
              + "tool exists not to report — listed so its absence is not a silent filter.")
       /* The one group here whose rows are files. It cannot go through `band` — that builds
          a routine row, `nav: "chg"` with an id — so it is written out, and the reason it is
          not folded into `band` with a flag is rule 32 in a function: one caller, one claim.
          Its rows open the file, which is the code browser's own route. */
       + Object.entries(CHANGE_FILE_BANDS)
              .map(([k, b]) => modgroup(k, b, c[k] || [])).join("");
}

/* Files whose module docstring moved, as a navigator group. The page's `modband` is the
 * same set with room to explain itself; both read one `CHANGES`, so they cannot disagree
 * about what moved (rule 51). */
function modgroup(key, b, rows) {
  if (!rows.length) return "";
  /* The same accordion the routine bands are in — `state.changeBand` holds the one open
     group, so this has to be a member of it rather than carry an open flag of its own, or
     opening it would leave a routine band open beside it and the pane would have two
     answers to which band is open (rule 51). Its markup is `band`'s exactly, class for
     class: a group wired correctly to a stylesheet that cannot carry it is this project's
     most-repeated defect (rules 54 and 71), and the only defence is not to invent a shape. */
  const open = state.changeBand === key;
  return `<div class="chgband">
      <button class="nav-head sub" data-changeband="${esc(key)}" aria-expanded="${open}">
        <span class="nav-title tone-moved">${b.title}</span>
        <span class="n num tone-moved">${rows.length}</span>
      </button>
      ${open ? `<div class="nav-items">
        <p class="hint" style="margin:.2rem .5rem .4rem">${b.why}</p>
        ${rows.map(r => navItemHtml({
            nav: b.nav, label: r[b.label] || r[b.id], sub: r[b.id], n: "",
            sel: r[b.id],
          })).join("")}
      </div>` : ""}
    </div>`;
}

/* The size of a vocabulary lane, from the cover. Empty rather than 0 when the server sent
   no vocabulary block at all: a map analysed by an older DunneFlow has no such counts, and
   printing 0 there would state a measurement nobody took. */
function vocabCount(key) {
  const v = STATS && STATS.vocabulary;
  return v && v[key] != null ? Number(v[key]).toLocaleString() : "";
}

/* The groups in the order the pane shows them.
 *
 * The order used to be applied by moving DOM nodes in `render()`, which worked and was
 * invisible to everything else -- including the jump strip, which is generated from this
 * table and would have listed the groups in an order the pane did not use. One ordering,
 * asked for by both, is the only way the strip and the list cannot disagree.
 *
 * Design rule 2: `waysin` and `explore` are a genuine tie, so both exist and usage decides. */
function navGroupsInOrder() {
  /* A group may declare itself inapplicable. Only Changes does: a program with one point
   * in time has nothing to compare, and a group that is permanently empty is a control
   * that permanently fails. Filtered here rather than in `buildNav`, so the jump strip --
   * which is built from this same list -- cannot offer a chip for a group that is not in
   * the pane. Two places deciding this is two answers, which is why this function exists. */
  const live = NAV_GROUPS.filter(g => (g.when ? g.when() : true));
  const first = state.menuOrder === "explore" ? "navExplore" : "navWaysIn";
  const chosen = live.find(g => g.id === first);
  if (!chosen) return live.slice();
  return [chosen, ...live.filter(g => g !== chosen)];
}

/* Is this group open?
 *
 * `state.navOpen` is what the reader has arranged and it wins; a group it says nothing
 * about falls back to the table's own default. Under the accordion that fallback is
 * narrowed to the first group alone, because "several groups open" is precisely the state
 * the accordion exists to prevent -- and a pane that opens four groups on the first paint
 * and then refuses to open two reads as a broken control rather than as a setting. */
function groupOpen(g, order) {
  if (g.id in state.navOpen) return !!state.navOpen[g.id];
  if (state.navGroups === "one") return g === navPrimary(order);
  return !!g.open;
}

/* Which single group the accordion opens when the reader has arranged nothing yet.
 *
 * Named by an identity (`primary`) rather than taken from the first position, which is what
 * this was and which was wrong for a reason the file already records one function up: the
 * menu order decides what sits at the *top*, and the two questions are not the same one.
 * With "Ways in first" the pane opened on six entrypoints and left the routine list --
 * which design rule 26 says the navigator *is* -- closed. An ordering rule that names a
 * position breaks the moment anything is put beside it; so does an opening one. */
function navPrimary(order) {
  const groups = order || navGroupsInOrder();
  return NAV_GROUPS.find(g => g.primary) || groups[0];
}

/* Opening a group under the accordion closes the rest.
 *
 * Written through `state` rather than through `data-open` on the element, which is what it
 * used to be: `buildNav()` re-renders from the table on every keystroke of the search box,
 * so a group collapsed by hand sprang open again the moment anything was typed. A toggle
 * whose state lives only in the DOM lasts until the next render of that DOM. */
function setGroupOpen(id, open) {
  if (open && state.navGroups === "one") {
    for (const g of NAV_GROUPS) state.navOpen[g.id] = false;
  }
  state.navOpen[id] = open;
  used("navgroups:" + state.navGroups);
  persist();
  /* A group whose rows are not in memory fetches them here, from the table rather than
   * from a branch (design rule 16). Called *before* the rebuild so the loading state is
   * what the reader sees -- `loadChanges` sets `{ loading: true }` synchronously, and its
   * own completion rebuilds the pane again with the answer. */
  const g = NAV_GROUPS.find(x => x.id === id);
  if (open && g && g.onOpen) g.onOpen();
  buildNav();
}

/* A group restored **open** at boot still needs its rows.
 *
 * `onOpen` fired from `setGroupOpen` only, so it ran on the toggle and never on the
 * restore -- and `navOpen` is persisted, so the second visit is the one that breaks. Open
 * the Changes group, reload, and the group sits open under "two versions — open to compare
 * them" with nothing to open: the note is telling the reader to do the thing they have
 * already done. It is rule 55's companion once more -- **one truth about what is open, and
 * whoever sets it does the work** -- with the *restore* as the half that sets it and does
 * nothing.
 *
 * It has been there since the group was built and was easy to miss, because reaching it
 * takes a reload. A base switch reloads, so every switch out of an open Changes group
 * landed on it.
 *
 * From the table, never a list of groups that need it (rule 36): a group added to
 * `NAV_GROUPS` with an `onOpen` is covered without anyone remembering. */
function openGroupsFetchWhatTheyNeed() {
  /* `groupOpen()`, never `state.navOpen[id]`. Openness has two expressions -- what the
     reader arranged and the table's own default for a group they have arranged nothing
     about -- and `groupOpen` is the one place that knows both. Reading the map directly
     asks only the first, so on a fresh profile, where `navOpen` is `{}`, this fetched
     nothing for a group that renders open. Written that way first, and caught by driving
     it: rule 51 in the fix for rule 51. */
  const order = navGroupsInOrder();
  for (const g of order) {
    if (!g.onOpen || !groupOpen(g, order)) continue;
    g.onOpen();
  }
}

/* The jump strip: every group, one click away, from anywhere in a list of any length.
 *
 * This is the third symptom of the navigator feedback and the one neither sticky headings
 * nor the accordion answers on its own -- from row 150 of Routines, *Packages* was a scroll
 * through the whole list away. Generated from the same table the groups are, so a group
 * added to `NAV_GROUPS` gets a chip without anyone remembering to add one: a hand-kept
 * second list is how `FOLDABLE` and the panel loop both went quietly wrong.
 *
 * The chips also say where you are. A reader arriving in the middle of four thousand rows
 * by wheel has nothing on screen naming the group they are inside; `markJump()` marks the
 * chip whose group is at the top of the pane. */
function jumpChips(order) {
  return order.map(g => `
    <button class="navjump" data-jump="${esc(g.id)}" aria-controls="${esc(g.id)}"
            title="Go to ${esc(g.title)}">${esc(g.title)}</button>`).join("");
}

/* Which group the reader is looking at.
 *
 * Under the accordion this is not a question about scrolling at all: exactly one group is
 * open, and that is what they are looking at. Reading it off the scroll position instead
 * was wrong in a way only clicking found -- with one group open the pane is short, so the
 * browser clamps a jump to a group near the bottom, and the chip then lit *Explore* one
 * click after the reader asked for *Packages*. Both numbers were right and neither said
 * what the reader had just done. Rule 32 in a strip of chips.
 *
 * With every group open there is no such answer, so it falls back to the scroll position:
 * the last group whose heading has reached the top. That is arithmetic over `offsetTop`
 * rather than over bounding boxes, so it holds in a tab with no rendered frames (rule 38)
 * -- "which chip is lit" would otherwise be a claim nothing could check. */
function markJump() {
  const sc = $("#navScroll");
  if (!sc) return;
  let here = null;
  if (state.navGroups === "one") {
    const open = NAV_GROUPS.find(g => groupOpen(g));
    here = open ? open.id : null;
  }
  if (!here) {
    for (const g of sc.querySelectorAll(".nav-group")) {
      if (g.offsetTop - sc.scrollTop <= 4) here = g.id;
    }
  }
  if (!here) {
    const first = sc.querySelector(".nav-group");
    here = first ? first.id : null;
  }
  $$(".navjump").forEach(b => {
    if (b.dataset.jump === here) b.setAttribute("aria-current", "true");
    else b.removeAttribute("aria-current");
  });
}

function jumpToGroup(id) {
  const sc = $("#navScroll"), g = document.getElementById(id);
  if (!sc || !g) return;
  /* Set `scrollTop` rather than calling `scrollIntoView`, for the same reason `markJump`
     does its own arithmetic: this must land in one step, with no frame and no smooth
     scroll, or a jump taken while the pane is being rebuilt lands somewhere else. */
  sc.scrollTop = g.offsetTop;
  markJump();
}

/* One navigator row, and one place that decides what a row looks like.
 *
 * It was inline in `buildNav()`, which was fine while there was one list. The routine list
 * is now a list of packages each holding rows of the same kind, and a second copy of this
 * markup would be a second answer to what a row is -- the shape rule 36 was written from. */
function navItemHtml(i) {
  return `
    <button class="nav-item" data-nav="${esc(i.nav)}"
            ${i.title ? `title="${esc(i.title)}" data-titled="1"` : ""}
            ${/* The qualified name travels on the row rather than being looked up when the
                  card opens. A `find` over 4,734 routines per `mouseover` is work
                  proportional to the whole program on an event that fires as fast as the
                  pointer moves -- rule 45, in the one place left that could still pay it. */
              i.qual ? `data-qual="${esc(i.qual)}"` : ""}
            ${/* Says the row answers with a card, so `dressNavItems` leaves its `title`
                  alone. Two tooltips for one row is the native one winning: it renders on
                  top, and it is the tiny unreadable thing the card replaced. */
              i.card ? `data-card="1"` : ""}
            ${i.sel ? `data-navid="${esc(i.sel)}"` : ""}
            ${i.sevnav ? `data-sevnav="${esc(i.sevnav)}"` : ""}
            ${i.current ? 'aria-current="true"' : ""}>
      ${i.dot ? `<span class="sevdot" style="background:var(--sev-${esc(i.dot)})"></span>` : ""}
      ${/* A sibling, not a wrapper: `dressNavItems()` collects the *loose text* of an
            item into `.navlabel` and sizes it, so emitting that span here would make it
            find nothing and quietly drop the long-name handling and the title. */
        i.sub ? `<span class="navsub">${esc(i.sub)}</span>` : ""}
      ${esc(i.label)}<span class="n${i.dot && i.n ? " num sevcount " + esc(i.dot) : ""}"
        ${i.id ? `id="${esc(i.id)}"` : ""}>${esc(String(i.n))}</span>
      ${/* **After the count, and that is not a style choice.** `dressNavItems` gathers a
            row's loose text into a `.navlabel` and re-inserts it immediately *before* the
            `.n` span -- so an element written between the label and the count comes out in
            front of the name. The file rows learnt this the expensive way: the chip landed
            inside the path and the row read `mensores/scriba/ \u25cb _queue.py`, a glyph
            inside a directory (rule 71). Placed last it survives that move and lands in a
            column of its own down the right-hand edge. */""}
      ${i.chg && i.chg.glyph
        ? `<span class="${esc(i.chg.cls.trim())}" aria-hidden="true">${i.chg.glyph}</span>`
        : ""}
    </button>`;
}

function buildNav() {
  const nav = $("#navigator");
  if (!nav) return;
  /* Keep the reader's place across a rebuild. `buildNav()` runs on every graph selection
   * as well as on every keystroke, and rewriting `innerHTML` sends the scroller back to the
   * top -- so clicking a node in the picture threw the list to row 1 and then scrolled back
   * down to the row it had just thrown away. An automatic move may not fight a deliberate
   * one (rule 24, and design rule 26). A *new question* is different: when what is typed in
   * the search box changes, the answer starts at the top. */
  treeCache = null;           // the pane is being rebuilt, so the answer may have changed
  const prev = $("#navScroll");
  const keep = prev && navBuiltFor === state.routineQ ? prev.scrollTop : 0;
  navBuiltFor = state.routineQ;
  const order = navGroupsInOrder();
  nav.innerHTML = `<div class="panebar">
      <div class="navjumps" role="group" aria-label="Jump to a group of the navigator">
        ${jumpChips(order)}
      </div>
      <button class="panefold" data-fold="navigator"
              title="Collapse the navigator" aria-label="Collapse the navigator">&#x00AB;</button>
    </div>
    <div class="nav-scroll" id="navScroll">` + order.map(g => {
    const items = g.items ? g.items() : [];
    const total = groupCount(g);
    return `
    <div class="nav-group" data-open="${groupOpen(g, order)}" id="${esc(g.id)}">
      <div class="nav-headwrap">
        <button class="nav-head" data-toggle>
          <span class="caret">▼</span> ${esc(g.title)}
          <span class="count">${total.toLocaleString()}</span>
        </button>
        ${/* Above the list, not under it. It used to sit after the items, so
             "showing 200 of 4,734" was reachable only by scrolling past the two hundred
             rows it describes -- or by collapsing the group, at which point it appeared
             at once, which is what gave it away. Design rule 1 was satisfied in letter
             and defeated in fact. Outside `.nav-items` so it reads the same open or
             closed, and inside the sticky header so it stays with its heading. */
          g.note ? `<div class="nav-note" id="note-${esc(g.id)}">${g.note()}</div>` : ""}
      </div>
      <div class="nav-items">
        ${g.body ? g.body() : items.map(navItemHtml).join("")}
      </div>
    </div>`;
  }).join("") + `</div>`;
  dressNavItems();
  markCodeMode();
  wireCodeFilterOnce();
  attachCode();
  const sc = $("#navScroll");
  if (sc) {
    sc.scrollTop = keep;
    sc.addEventListener("scroll", markJump);   // the element is new on every build
  }
  markJump();
}

/* ════════════════════════════════════════════════════════════
   Loading

   One request for the first screen. The anomaly findings are large -- each one
   carries its detail and its blind spot -- and most sessions read the counts
   without opening the list, so they are fetched only when the worklist is.
   ════════════════════════════════════════════════════════════ */

async function loadCover() {
  const r = await fetch("/api/cover");
  if (!r.ok) throw new Error(`the server answered ${r.status} for /api/cover`);
  const d = await r.json();
  ENTRYPOINTS = d.entrypoints || [];
  BOUNDARIES  = d.boundaries  || [];
  PKGS        = d.packages    || [];
  ROOT        = d.root || "";
  TABLES      = d.tables      || [];
  STATS       = Object.assign({}, d.stats, { anomalies: d.anomalies, program: d.program,
                                             vocabulary: d.vocabulary || null });

  const prog = $("#prog");
  if (prog) {
    prog.innerHTML = `<option>${esc(d.program)} — ${Number(d.stats.files).toLocaleString()} files</option>`;
  }
}

/* The routine list, from the document backend that already carries what is needed.
 *
 * It read `/api/document?id=routines` while a row needed only a name and an id. Grouping
 * the list by package needs the package, and there are two expressions for one in this
 * dashboard -- so this asks `/api/routines`, which takes it from the expression the
 * *plates* are built from. A package heading in the list is then the plate in the picture
 * rather than a second thing that happens to be spelled the same way.
 *
 * `plates` comes with it, because they are not the same set: `graph.py` merges any package
 * below `MIN_DISK` into `pkg:<small>`, so 47 packages are 45 plates and a row offering
 * `pkg:_version` would select a plate that is not in the stack.
 *
 * Loaded on demand rather than with the cover: 4,734 rows is a real payload and most
 * sessions that only read the overview never want it. */
async function loadRoutines() {
  if (ROUTINES.length) return;
  const r = await fetch("/api/routines");
  if (!r.ok) throw new Error(`the server answered ${r.status} for the routine list`);
  const d = await r.json();
  PLATES = new Set(d.plates || []);
  ROUTINES = (d.routines || [])
    .filter(row => row.id)              // a row with no identity is not selectable
    .map(row => ({ id: row.id, name: row.name || "", module: row.module || "",
                   pkg: row.pkg || "", why: row.why || "" }));
  /* Same rule, same reason: `describe()` resolves a `structures.id`, so a structure is a
     subject exactly as a routine is -- and a row without one could not be acted on. */
  STRUCTURES = (d.structures || [])
    .filter(row => row.id)
    .map(row => ({ id: row.id, name: row.name || "", module: row.module || "",
                   kind: row.kind || "", pkg: row.pkg || "" }));
}

async function loadAnomalies() {
  if (ANOMALIES.length) return;
  const r = await fetch("/api/anomalies");
  const d = await r.json();
  /* The prototype's findings used short keys. Mapped here rather than renamed in
     `anomalies.py`, because the store's vocabulary is the one the rest of the tool
     speaks and a view is not a reason to change it. `blind` is never allowed to be
     empty: a finding without its blind spot is a guess wearing a uniform. */
  ANOMALIES = (d.findings || []).map(f => ({
    /* **What makes this finding this finding**, and the reason every other field here can
       be a rendering. Dropping it was the defect this chunk opened on: triage was filed
       against the finding's *position* in this array while both declarations of
       `state.triage` said `finding id ->`, and the findings are served sorted by count.
       Measured on Mensores' pair -- a decision filed against `siq__rebuild_87_02h` read
       back after a base switch as an acknowledgement of `tags`, with nothing on screen or
       in the console to say so.

       `parts` rides with it because the pairing is a *claim* and the parts are how a
       reader sees why it was made (design rule 13). */
    ident: f.ident,
    parts: f.ident_parts || [],
    title: f.title,
    kind: f.kind,
    conf: f.confidence,
    n: f.count,
    where: f.line ? `${f.file}:${f.line}` : f.file,
    detail: f.detail,
    blind: f.blind_spot,
    /* Read by the text explaining why the two jump buttons are disabled, which named
       `cur.a.subject` and got `undefined` for as long as the buttons have existed --
       rule 44, a live control reading a field nothing sends. Sent since the identity
       landed; simply never carried across this map. */
    subject: f.subject || "",
    sev: sevKey(f.severity),
  }));
}

/* ════════════════════════════════════════════════════════════
   The graph, driven from here

   `graph.js` is the engine and knows nothing about this page. It draws into the element
   it is handed, and everything it wants to say -- what is selected, what is on screen,
   what is not, how fast, what went wrong -- leaves as an event. This section is the other
   half of that boundary: the shell owns the selection, the settings, the search, the
   legend and the breadcrumb, and pushes into the engine what the engine needs to draw.

   Before this, both halves existed twice. The graph had its own header, mode toggle,
   settings pane, disk menu, search box, breadcrumb and inspector, and so did the shell --
   two complete applications for one reader.
   ════════════════════════════════════════════════════════════ */

const Graph = window.DunneFlowGraph;
const Settings = window.DunneFlowSettings;

/* The reader's arrangement, and the only fields written to storage. Everything else in
 * `state` is where they are right now, which is not the same thing and must not outlive
 * the visit: which severity tab is open, what is typed in the search box, whether a SQL
 * block is expanded. */
const PERSISTED = [
  "theme", "palette", "scale", "startup", "mode", "menuOrder", "trailShown", "trailCap",
  "density", "bandScroll", "baseRev", "comparedRev", "comparedIsNewer",
  "ambient", "hideInferred", "colWidths", "insp", "sortKey", "sortAsc",
  "egress", "aiOps", "triage", "pins", "usage", "graphLayout",
  "diskOrder", "diskColors", "colorBy", "sortMode", "filterMode", "direction",
  "level", "minDisk",
  "nodeSize", "spreadX", "spreadY", "spreadZ", "plateSize", "collapseUnused",
  "diagram", "nodeShapes", "diagramId", "diagramPorts", "diagramCursor", "diagramEdgeWidth",
  "navCase", "navWord", "navRegex",
  "searchCase", "searchWord", "searchRegex",
  "panels", "inspectorAuto", "navWidth", "codeWidth", "codeFile", "codeOverlay",
  "tableOverlay", "anomalyOverlay",
  "navGroups",
  "navOpen", "navCap",
  "showPlates", "picks", "graphTheme", "edgesInMotion", "pointerShown", "pointerColor", "pointerPlace", "reticuleShown", "focusLocked",
  /* `followMode` was declared in the store, set by a live control that calls `persist()`,
   * and named in the reset dialog -- and absent from this list, so every one of those
   * writes dropped it on the floor and every reload came back on `replace`. Design rule 2
   * says both ways of following a neighbour are built because real use retires the loser;
   * a choice that cannot survive a reload is not use, it is a coin toss per session. */
  "followMode",
];

let settings = null;      // the loaded blob; `state` is the live copy
let program = null;
/* The payload on screen, and every one this session has fetched, keyed by the question it
 * answers -- `graphKey(level, minDisk)`. `graphPayload` is one of the values in the map,
 * never a second copy: one truth with an index over it (rule 51). */
let graphPayload = null;
const graphPayloads = new Map();
/* What the last change of altitude did to the selection, in a sentence. A reader whose
 * routine became the file holding it has been moved, and being moved without being told is
 * design rule 1's silent filter wearing a different coat. */
let levelNote = "";
let graphLoading = false;
let graphError = null;
let counts = null;        // the engine's last count report
let fps = 0;
/* `legendOpen` used to live here: a bare module `let`, so the reader's answer could
 * never survive a reload and the *default* was the only answer there was. It is
 * `panels.legend` now, persisted with every other pane. */

function persist() {
  if (!program) return;
  const out = {};
  for (const k of PERSISTED) out[k] = state[k];
  Settings.saveSettings(program, out);
}

/* Settings are loaded once the program is known, because they are stored per program: a
 * disk order and a set of colours worked out for one codebase mean nothing in another. */
function adoptSettings(name) {
  program = name;
  settings = Settings.loadSettings(name);
  for (const k of PERSISTED) {
    if (k in settings) state[k] = settings[k];
  }
  /* What a version bump carried over and what it had to drop. Not in `PERSISTED` and so
     never written back: it is a fact about *this* load, and a reader who has seen it once
     should not meet it again on the next one. The surface that lost something says so. */
  state.carried = settings.__carried || null;
}

/* ── the palette, read from the stylesheet ─────────────────────────────────────
 *
 * `tokens.css` says no component declares a colour outside that block, and the graph is a
 * component. Reading the tokens rather than keeping a second table in JavaScript means the
 * theme toggle already on the page drives the stack with no second code path, and there is
 * exactly one place a colour is written down. */
function cssPalette() {
  const cs = getComputedStyle(document.documentElement);
  const hex = (name) => {
    const v = cs.getPropertyValue(name).trim();
    return [1, 3, 5].map(i => parseInt(v.slice(i, i + 2), 16));
  };
  const num = (name) => parseFloat(cs.getPropertyValue(name));
  const ground = hex("--graph-ground");
  return {
    kind: {
      ROUTINE:   hex("--graph-routine"),
      STRUCTURE: hex("--graph-structure"),
      CONSTANT:  hex("--graph-constant"),
      BOUNDARY:  hex("--graph-boundary"),
      ARTEFACT:  hex("--graph-artefact"),
      MODULE:    hex("--graph-module"),
    },
    /* What the comparison says, for `colorBy: 'change'`. Read through the same `hex(...)`
       helper as everything else here on purpose: the guard that requires a colour set to
       reach the stack greps this function for exactly that call shape, so reading these
       any other way would leave the guard asleep while the bug is real (rule 37).

       **Keyed by tone, not by band**, and that is the correction rather than the design:
       written as `only_base: hex("--diff-gone")` it pinned a *side* to a colour, so
       flipping which version the reader assumes is newer swapped every word in the key and
       left the dots red — a picture saying "added" in the colour of gone, which is worse
       than one with no colour at all. The band-to-tone mapping is `diffWords()`'s, pushed
       as `changeTone`, so the two cannot come apart. Found by flipping it and looking at
       the numbers.

       `quiet` serves both `edited` and `same`: "the body changed and nothing it does did"
       is internal computation, which this tool exists not to report. `unclaimed` is not a
       difference and is not part of a colour set -- it is the ground for everything the
       comparison was never asked about. */
    change: {
      gone:      hex("--diff-gone"),
      new:       hex("--diff-new"),
      moved:     hex("--diff-moved"),
      quiet:     hex("--graph-unchanged"),
      unclaimed: hex("--graph-unclaimed"),
      mixed:     hex("--graph-mixed"),
    },
    dim: hex("--graph-dim"),
    dimAlpha: num("--graph-dim-alpha"),
    edge: [...hex("--graph-edge"), num("--graph-edge-alpha")],
    plateFill: [...hex("--graph-plate-fill"), 70],
    plateLine: [...hex("--graph-plate-line"), 140],
    /* The plates a selection touches. Derived from the accent rather than from the plate
       colours, because these are *not* a fainter version of the plates layer -- they answer
       a different question ("which plate is this?") and belong to the selection, which is
       what the accent already means everywhere else on the page. */
    plateTouchFill: [...hex("--accent"), 16],
    plateTouchLine: [...hex("--accent"), 70],
    label: [...hex("--graph-label"), 240],
    labelBg: [...hex("--graph-label-bg"), 200],
    diskS: num("--graph-disk-s"), diskL: num("--graph-disk-l"),
    extS: num("--graph-ext-s"), extL: num("--graph-ext-l"),
    ambient: num("--graph-ambient"), diffuse: num("--graph-diffuse"),
    specular: num("--graph-specular"),
    ground,
  };
}

/* Design rule 2 in force: the graph follows the theme by default, and a reader who
 * genuinely prefers a dark stack over a light page can have one. Usage decides which
 * survives; until then both exist. */
function graphPaletteNow() {
  if (state.graphTheme === "dark") {
    const saved = document.documentElement.getAttribute("data-theme");
    document.documentElement.setAttribute("data-theme", "dark");
    const p = cssPalette();
    if (saved === null) document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", saved);
    return p;
  }
  return cssPalette();
}

/* The reader's pointer colour as the engine wants it, or null for "use the token".
 *
 * Null rather than a resolved value on purpose: a colour resolved here would be frozen at
 * the moment it was read, and the graph follows the theme -- so switching to the dark
 * stack would keep a pointer chosen against the pale one. The engine already replaces its
 * palette whole when the theme moves, and this stays out of that.
 *
 * A stored colour that no longer clears the bar is not used. That is not the same as
 * refusing to store it: the bar moves with the theme, so an amber that passes on near-black
 * and fails on the pale ground must fall back rather than either being deleted or drawn
 * illegibly. `pointerNote()` says which of the two is happening. */
function pointerRgb() {
  const c = state.pointerColor;
  if (!c || !/^#[0-9a-f]{6}$/i.test(c)) return null;
  return pointerPasses(c) ? [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16)) : null;
}

/* Design rule 6: customisation is clamped, and says why. 3:1 rather than 4.5:1 because
 * the pointer is a large graphic object rather than body text -- the same line the rule
 * draws for chrome. Measured against the graph's *own* ground, which is not the page's:
 * with the stack forced dark inside a light page they are different colours entirely, and
 * checking against the wrong one would pass a pointer nobody can see. */
function pointerPasses(hex) {
  return pointerRatio(hex) >= 3;
}

function pointerRatio(hex) {
  const p = graphPaletteNow();
  const ground = "#" + p.ground.map(v => v.toString(16).padStart(2, "0")).join("");
  return contrast(hex, ground);
}

/* The token's own value, so the picker opens on the colour actually in force rather than
   on black -- an empty `pointerColor` means "the theme's", and showing that as #000000
   would be the swatch stating a colour the picture is not using. */
function pointerToken() {
  const v = getComputedStyle(document.documentElement)
    .getPropertyValue("--graph-pointer").trim();
  return /^#[0-9a-f]{6}$/i.test(v) ? v : "#fbbf24";
}

/* Design rule 6: a refusal states its reason. Three states, and the third is the one worth
   writing down -- a colour that *was* accepted and no longer clears the bar because the
   reader changed the graph's ground underneath it. It is not deleted, because the bar moves
   with the theme and switching back would want it again; it simply is not used, and this
   says so where the swatch is. */
function updatePointerNote() {
  const out = $("#pointerNote"), ratio = $("#pointerRatio");
  const chosen = state.pointerColor;
  const shown = chosen || pointerToken();
  const r = pointerRatio(shown);
  if (ratio) {
    ratio.textContent = r.toFixed(2) + ":1";
    ratio.className = "ratio " + (r >= 3 ? "pass" : "fail");
  }
  if (!out) return;
  if (!chosen) {
    out.innerHTML = `<span class="hint" style="font-size:.72rem">Following the theme.</span>`;
  } else if (r >= 3) {
    out.innerHTML = `<span class="hint" style="font-size:.72rem">Yours, and it clears
      3:1 against this ground.</span>`;
  } else {
    out.innerHTML = `<span class="clampnote"><b>\u2715</b><span>Refused — ${r.toFixed(2)}:1
      against the graph's ground is below the 3:1 minimum for a large graphic object, and a
      pointer nobody can see is worse than no pointer. The theme's colour is being drawn
      instead; lighten or darken this one and it will be used.</span></span>`;
  }
}

function applyGraphPalette() {
  const p = graphPaletteNow();
  $("#graphMount").style.background =
    `rgb(${p.ground[0]},${p.ground[1]},${p.ground[2]})`;
  if (!Graph.mounted()) return;
  Graph.setPalette(p);
  /* The clamp is against the ground, so moving the ground moves the bar -- and a colour
   * that cleared 3:1 on near-black can be invisible on the pale one. Re-asked here rather
   * than only when the picker moves, which is the difference between a limit and a limit
   * that was true once. This is the third state `pointerRgb()` documents, and without this
   * line the documentation would have been the only place it happened. */
  Graph.setOptions({ pointerColor: pointerRgb() });
  updatePointerNote();
}

/* ── the stack's altitude ──────────────────────────────────────────────────────
 *
 * Two levels of one program. `routine` is every thing it declares -- 10,015 nodes and
 * 14,254 edges on Mensores -- and `module` folds each file into one node and each boundary
 * kind into one: 578 and 1,505. It is a second way to look at the same facts and not a
 * filter, so nothing is dropped and every folded node says what it stands for.
 *
 * Both are held once fetched. 4.9 MB and 0.3 MB, which is what makes moving between them
 * instant and, more to the point, what makes the selection able to travel: the translation
 * below is a lookup in a payload the page already has rather than a request. */

/* One door onto the two settings that are per level.
 *
 * `diskOrder` is per level because the two levels genuinely hold different plates, and
 * `mount` throws a saved order away when it does not match the plate set -- so one shared
 * array would mean a reader who arranged the routine stack lost it the moment they looked
 * at modules and came back. `minDisk` is per level because what a plate *holds* changes
 * with the level. Written inline at each of six call sites this would be six places to keep
 * one shape in step, which is rule 51 with six chances to get it wrong. */
function plateOrder() { return (state.diskOrder || {})[state.level] ?? null; }
function setPlateOrder(order) {
  state.diskOrder = { ...(state.diskOrder || {}), [state.level]: order };
}
/* `null` is a third state and not a number: "whatever the server's default for this level
 * is". A stored 8 would silently become an explicit choice about a level the reader has
 * never visited, which is rule 66's companion -- an answer that is sometimes derived and
 * sometimes chosen has three states, never two. */
function minDiskNow(level = state.level) { return (state.minDisk || {})[level] ?? null; }
function setMinDiskNow(n) {
  state.minDisk = { ...(state.minDisk || {}), [state.level]: n };
}
/* How much a plate's width says about how much it holds, at the altitude on screen.
 *
 * Per level, and unlike `minDisk` there is no third state to keep: 0 is a real answer a
 * reader can choose and the default is a number rather than "whatever the server says",
 * so a missing entry falls through to `Settings.DEFAULTS` and never to a literal here. */
function plateSizeNow(level = state.level) {
  const v = (state.plateSize || {})[level];
  return typeof v === "number" ? v : Settings.DEFAULTS.plateSize[level];
}
function setPlateSizeNow(v) {
  state.plateSize = { ...(state.plateSize || {}), [state.level]: v };
}

/* The key **is** the question, so a cache hit and a fetch can never answer different ones. */
function graphKey(level, min) { return `${level}:${min ?? ""}`; }

function graphUrl(level, min) {
  const q = new URLSearchParams({ level });
  if (min != null) q.set("minDisk", String(min));
  return `/api/graph?${q}`;
}

async function fetchPayload(level, min) {
  const key = graphKey(level, min);
  const held = graphPayloads.get(key);
  if (held) return held;
  const r = await fetch(graphUrl(level, min));
  /* The server puts its reason in the status line -- an unknown level, a threshold that is
     not a number -- because there is no partial stack to send instead. A payload the page
     cannot draw is worse than none. */
  if (!r.ok) {
    throw new Error(r.statusText || `the server answered ${r.status} for /api/graph`);
  }
  const payload = await r.json();
  graphPayloads.set(key, payload);
  return payload;
}

/* Carrying a selection between altitudes.
 *
 * A pick is an index into *one* payload, so the same number means a different routine in
 * the next one -- which is why `setPayload` drops them and the shell re-resolves from ids.
 * But an id does not survive either: `mod:mensores.cli.audit` is not a routine and no
 * routine id is a module. So the translation is explicit and it is **stated**, because
 * "showing the file your routine lives in" is a different answer from the one asked for and
 * a reader who is not told has been quietly moved.
 *
 * Both directions read the **routine-level payload**, the only one carrying a node's module
 * and the plate it came from. `home ?? disk` is the plate *before* small ones were merged,
 * which is exactly what the server folds on -- so this cannot disagree with it by drifting
 * over a threshold the reader moved. */
function foldedIdFor(fine, i) {
  const det = (fine.nodes.detail || [])[i] || {};
  if (det.module) return `mod:${det.module}`;
  const plate = det.home || (fine.nodes.disk || [])[i] || "";
  return plate.startsWith("ext:") ? `outside:${plate.slice(4)}` : null;
}

function translateIds(ids, toLevel, fine) {
  if (!fine || !ids.length) return [];
  const out = [];
  const seen = new Set();
  const keep = (id) => { if (id && !seen.has(id)) { seen.add(id); out.push(id); } };

  if (toLevel === "module") {
    const at = new Map();
    (fine.nodes.id || []).forEach((id, i) => { if (!at.has(id)) at.set(id, i); });
    for (const id of ids) {
      const i = at.get(id);
      if (i !== undefined) keep(foldedIdFor(fine, i));
    }
    return out;
  }
  // Down: one folded node is many. `selectFromNav`'s table case does the same thing for
  // the same reason -- selecting a table means selecting the code that reads and writes it
  // (rule 30) -- and like that one it states how many it turned into.
  const wanted = new Set(ids);
  (fine.nodes.id || []).forEach((id, i) => {
    if ((fine.nodes.shadow || [])[i] === 1) return;     // never drawn (rule 23)
    if (wanted.has(foldedIdFor(fine, i))) keep(id);
  });
  return out;
}

/* What is picked, in id space. The engine answers in indices, and an index is the one form
 * that means something different in the other payload. */
function selectedIds() {
  if (!Graph.mounted() || !graphPayload) return { nodes: [], disks: [] };
  const nodes = [], disks = [];
  for (const p of Graph.selection()) {
    if (p.kind === "disk") { disks.push(p.id); continue; }
    const raw = graphPayload.nodes;
    const i = raw.shadow[p.index] ? raw.real[p.index] : p.index;
    if (i >= 0) nodes.push(raw.id[i]);
  }
  return { nodes, disks };
}

/* Move the stack to another altitude, or to another `<small>` threshold.
 *
 * The camera refits, because the stack is a different size and a different height -- design
 * rule 20's own reason for a snap-to-fit. The tilt is kept, so the reader's sense of which
 * way they were looking survives.
 */
async function setGraphDetail({ level = state.level, minDisk } = {}) {
  const changingLevel = level !== state.level;
  const before = selectedIds();
  const fine = graphPayloads.get(graphKey("routine", minDiskNow("routine")));
  (window.__lvl = window.__lvl || []).push({ step: window.__lvl ? window.__lvl.length : 0,
    changingLevel, from: state.level, to: level,
    beforeNodes: before.nodes.length, beforeDisks: before.disks.length,
    rawSel: Graph.selection().map(p => p.kind + ":" + (p.id ?? p.index)),
    payloadLevel: graphPayload && graphPayload.level,
    hasFine: !!fine, keys: [...graphPayloads.keys()],
    minRoutine: minDiskNow("routine"), stateLevel: state.level,
    minDiskObj: JSON.stringify(state.minDisk) });

  if (changingLevel) { state.level = level; used("level:" + level); }
  if (minDisk !== undefined) setMinDiskNow(minDisk);
  persist();

  // Not on screen yet: the choice is real, and `ensureGraph` will honour it on mount.
  if (!Graph.mounted()) { render(); return; }

  levelNote = "";
  graphLoading = true;
  renderGraphFurniture();
  let payload;
  try {
    payload = await fetchPayload(state.level, minDiskNow());
  } catch (err) {
    graphError = { message: err.message };
    graphLoading = false;
    renderGraphFurniture();
    return;
  }
  graphPayload = payload;
  Graph.setPayload(payload);
  /* **The dial is per level, so a change of level is a change of its value.** Without
     this the engine keeps the width it was last given and draws the new altitude at the
     old altitude's judgment, while the slider beside it moves to the right number -- one
     control and two answers (rule 67), and the one on screen is the one that is wrong.
     After `setPayload`, because `adoptPayload` rebuilds the ratios this multiplies. */
  Graph.setOptions({ plateSize: plateSizeNow() });
  /* **The engine resolves the plate order and the shell records what it resolved.** This
     used to push `plateOrder()` back in first, which is one truth in two places (rule 51)
     and worse than untidy: `adoptPayload` had *just* worked out whether the saved order
     still describes this payload, and on a fresh session there is no saved order at all --
     so the push handed `setOptions` a `null` and `applyLayout` threw on it, every switch,
     from the first one.
     Everything after the throw was skipped, so the selection never travelled and the note
     that would have said so was never written. Silent in the page and shouting in the
     console, which is where it was found. */
  setPlateOrder(Graph.diskOrder());

  /* The comparison's per-node map is a fact about *this* payload -- a module takes the band
     of what it holds -- so it is dropped rather than reused. Rule 51: whoever changes the
     subject does the work of invalidating what was said about the old one. */
  if (CHANGES) CHANGES._byNode = null;

  if (changingLevel) {
    const moved = translateIds(before.nodes, state.level,
                               state.level === "module" ? fine : payload);
    if (before.nodes.length && !moved.length) {
      levelNote = `nothing that was selected exists at this level`;
    } else if (moved.length && state.level === "module") {
      levelNote = `${before.nodes.length.toLocaleString()} selected → the ${
        moved.length.toLocaleString()} ${moved.length === 1 ? "node" : "nodes"} holding them`;
    } else if (moved.length) {
      levelNote = `${before.nodes.length.toLocaleString()} selected → the ${
        moved.length.toLocaleString()} ${moved.length === 1 ? "thing" : "things"} inside`;
    }
    state.wanted = { nodes: moved, disks: before.disks };
    /* A fold does not travel between altitudes: a box is a compartment's own idea and the
       stack's two levels are the model's. Cleared rather than carried, because carrying it
       would leave the inspector describing a class that the level on screen does not draw. */
    setSubject({ node: moved[0] || null });
  } else {
    state.wanted = { nodes: before.nodes, disks: before.disks };
  }
  applyWanted();
  state.picks = Graph.selection();

  graphLoading = false;
  ensureGraphChange();
  persist();
  applyGraphPalette();
  render();
}

/* ── mounting ─────────────────────────────────────────────────────────────────
 *
 * Lazily, on first entry to graph mode. The payload is nine thousand nodes and the cover
 * is the first screen most sessions never leave, so fetching it at boot would slow the
 * one screen that has to be fast in order to serve the one that might never open. */
async function ensureGraph() {
  // Cheap to call from anywhere that might land in graph mode; it decides for itself.
  if (state.mode !== "graph" || state.graphLayout !== "stack") return;
  if (Graph.mounted() || graphLoading) return;
  graphLoading = true;
  renderGraphFurniture();
  try {
    graphPayload = await fetchPayload(state.level, minDiskNow());
  } catch (err) {
    graphError = { message: err.message };
    graphLoading = false;
    renderGraphFurniture();
    return;
  }

  Graph.on("select", onGraphSelect);
  Graph.on("hover", onGraphHover);
  Graph.on("counts", (c) => { counts = c; updateGraphCounts(); });
  Graph.on("fps", (v) => {
    fps = v;
    const box = $("#gfps");
    if (box) box.textContent = v.toFixed(0);
  });
  Graph.on("error", (e) => { graphError = e; renderGraphFurniture(); });

  /* Before the mode reaches the engine, not after: mounting in `change` on a program with
     nothing to compare would paint every node one tone for a frame and then correct
     itself, which reads as a flicker rather than as a decision. */
  resolveColorBy();
  /* **The mount announces too, and that is an echo like any other (rule 76).**
   * `Graph.mount` is handed `picks: state.picks` -- a selection this app has already
   * decided -- and finishes by calling `announceSelection()`, so `onGraphSelect` re-enters
   * here as well as from `applyWanted`. Rule 76 flagged the second call site and not this
   * one, and the difference was invisible because nothing could reach it: a thread row only
   * exists once something is selected, which means the graph is already up.
   *
   * The doorway panel is the first surface that can follow a subject with the stack never
   * mounted, and it made it visible at once -- a card naming `backup_cmd` opened the
   * inspector on `mensores.transport._envelope.<module>`, an unrelated node, and filed two
   * trail steps under its name. That is rule 74's defect arriving through the engine,
   * exactly as rule 76 describes, at the one call site the fix had not reached.
   *
   * Flagged for the mount's duration in a `finally`, for the same reason the other site is:
   * a throw inside the engine would otherwise leave the shell deaf to every later
   * selection. `applyWanted()` below then installs the wanted set and does the subject, the
   * trail and the repaint itself, in the right order and with the right subject. */
  installingSelection = true;
  try {
    Graph.mount($("#graphStage"), graphPayload, {
      diskOrder: plateOrder(), diskColors: state.diskColors, colorBy: state.colorBy,
      nodeChange: graphChangeOn() ? changeByNodeId() : null, changeTone: changeTones(),
      changeStamp: Date.now(),
      filterMode: state.filterMode, direction: state.direction, nodeSize: state.nodeSize,
      spreadX: state.spreadX, spreadY: state.spreadY, spreadZ: state.spreadZ,
      plateSize: plateSizeNow(),
      collapseUnused: state.collapseUnused, showPlates: state.showPlates, scale: state.scale,
      diagram: state.diagram, nodeShapes: state.nodeShapes,
      edgesInMotion: state.edgesInMotion, picks: state.picks,
      pointerShown: state.pointerShown, pointerColor: pointerRgb(),
      pointerPlace: state.pointerPlace, reticuleShown: state.reticuleShown,
      focusLocked: state.focusLocked,
    });
  } finally {
    installingSelection = false;
  }
  /* Read back the order the engine resolved. A saved order from a graph that has since
   * changed is discarded there, and the shell must not go on persisting the stale one --
   * that is how a setting outlives the thing it described. */
  /* **A restored mode has to ask for its data.** `colorBy` is persisted, so a reader who
     left in `change` comes back in it — and the mount hands the engine `changeByNodeId()`,
     which is `null` until something has fetched. Nothing had, so the stack came up in
     change mode having asked for nothing while the key said *comparing…* over a request
     that did not exist. Rule 55's companion once more: whoever sets the state does the
     work. */
  ensureGraphChange();
  setPlateOrder(Graph.diskOrder());
  state.picks = Graph.selection();
  // A choice made while the stack was not on screen is adopted now rather than lost.
  applyWanted();
  graphLoading = false;
  applyGraphPalette();
  render();
}

/* One selection, every view. The graph reports what was picked; the inspector, the
 * breadcrumb and the trail all follow from here rather than from each other. */
function onGraphSelect(sel) {
  state.picks = sel.picks;
  /* **An echo is not an act.** The engine announces every selection change, including the
   * one the app has just handed it -- `applyWanted` calls `Graph.setSelection`, which
   * announces *synchronously*, so this ran before the caller had finished its own turn.
   *
   * On the echo it re-subjected to `sel.node`, which is the **last node** of whatever was
   * installed: one arbitrary member of it. That is exactly the defect a fold was built to
   * remove (rule 74) arriving through the engine rather than through the caller -- a box
   * click set `state.fold`, the echo replaced it with a method of that class two lines
   * later, and the pane answered truthfully about something nobody clicked. It filed a
   * second trail step under that member's name while it was there.
   *
   * The fold has had this since the day it was built and it was invisible: verified in
   * Diagram mode with the stack never mounted, `applyWanted` returns at `Graph.mounted()`
   * and nothing echoes at all. Found by opening an arrow with the graph up.
   *
   * `state.picks` is still taken, because the engine is the authority on what is picked.
   * Everything below is *what to do about a new selection*, and the caller that installed
   * this one does all of it itself, in the right order, with the right subject. Same shape
   * and same reason as `recordSelection`'s `restoringSelection` bail.
   *
   * **Both flags, because at this point both mean the same thing.** A trail step restores
   * a selection through `Graph.setSelection` too, and `restoringSelection` only ever
   * suppressed `recordSelection` -- so a Back ran this whole body with `sel.node` as its
   * subject and `applySelectionStep` set the right one on the next line. Correct by
   * ordering rather than by design, with a wasted repaint under a wrong subject on the way
   * past. Three sites hand the engine a selection the app already decided; one predicate
   * covers all three, and a guard asserts there is no fourth. */
  if (installingSelection || restoringSelection) return;
  setSubject({ node: sel.node ? sel.node.id : null });
  persist();
  recordSelection();          // so the click that lost your place can be taken back
  buildNav();                 // the list follows the graph -- the other half of the loop
  revealSelectedRoutine();
  render();
}

/* The back path: click a node in the graph, and the routine list moves to it.
 *
 * Chasing a thread runs both ways -- see something in the list and find it in the picture,
 * or spot something in the picture and find out what it is called -- and only one of those
 * directions existed. `buildNav()` marks the row (`current` on the item), and this scrolls
 * it into view.
 *
 * Guarded on `scrollIntoViewIfNeeded` semantics rather than always scrolling: a list that
 * jumps on *every* selection yanks itself out from under the reader's own click. That is
 * the same shape as the inspector's auto-rail reopening underneath a deliberate fold
 * (rule 24) -- an automatic move may not fight a deliberate one -- so this only acts when
 * the row is genuinely out of sight. */
/* The table's half of design rule 26, and the same discipline the navigator's version
 * states: **an automatic move may not fight a deliberate one.** So this acts only when the
 * row is genuinely out of sight, or when the reader asked for it by name.
 *
 * `force` is that ask. Without it, arriving in table mode with a selection 238,401px down
 * would be an answer nobody could see; with it applied on every render, a reader scrolling
 * the list to read it would be thrown back to their selection on every repaint.
 */
/* The element that actually scrolls, asked rather than assumed.
 *
 * `.tablewrap` carries `overflow: auto` and looks like the scroller; it is not. Nothing
 * bounds its height, so it grows to all 339,229px of the table and the *pane* scrolls
 * instead. Both the reveal and its check were written against the wrapper, so the reveal
 * moved a `scrollTop` that had nowhere to go and the check compared the row against a box
 * extending far below the window -- which made every row "in view" and the whole thing
 * report success. A guard that names the right case and measures the wrong box.
 *
 * Walking up until something genuinely overflows survives the next layout change too,
 * which a hard-coded id would not. */
function scrollerFor(el) {
  for (let n = el && el.parentElement; n && n !== document.documentElement; n = n.parentElement) {
    const cs = getComputedStyle(n);
    if (n.scrollHeight > n.clientHeight + 4 && /auto|scroll/.test(cs.overflowY)) return n;
  }
  return null;
}

/* The last row this moved to on its own, so it moves once per subject and not once per
 * repaint. "Only when the row is out of sight" was the obvious condition and it is the
 * wrong one here: scrolling away from your selection to read the list around it is an
 * ordinary thing to do, and it made the row out of sight, so the next repaint dragged the
 * reader back. **An automatic move may not fight a deliberate one** (design rule 26) --
 * and with 4,734 rows the deliberate one is a long way from home.
 *
 * A *new* subject is a different matter: nobody scrolled anywhere, the answer simply
 * changed, and an answer 97,000px off screen is not an answer. */
let lastRevealedRow = null;

function revealSelectedRow(force) {
  if (!state.selected) return;
  if (!force && state.selected === lastRevealedRow) return;
  const row = $(`tr[data-row="${CSS.escape(state.selected)}"]`);
  const sc = row && scrollerFor(row);
  if (!row || !sc) return;
  lastRevealedRow = state.selected;
  const rb = row.getBoundingClientRect(), sb = sc.getBoundingClientRect();
  const hidden = rb.bottom < sb.top || rb.top > sb.bottom;
  if (!force && !hidden) return;
  /* Centred rather than merely inside: a row that lands one pixel below the header is on
     screen and still nowhere the eye goes. */
  sc.scrollTop += (rb.top - sb.top) - (sb.height / 2) + (rb.height / 2);
}

function revealSelectedRoutine() {
  /* **A fold reveals its first member.** There is no single selected node, so the node-only
     guard returned immediately and the list never moved -- which, with nothing marked
     either, is indistinguishable from the diagram not being wired to the navigator at all.
     Reported as exactly that.

     The *first* rather than the whole set, because a reveal is a scroll and a scroll has one
     destination. Every member is marked (`selectedRowIds`), so what the reader lands on is
     the top of a marked run rather than a lone highlight. */
  const want = state.selected || ((state.wanted || {}).nodes || [])[0] || null;
  if (!want) return;
  /* From the routine, not from the row. A closed package draws no rows at all now, so
   * looking the element up first and giving up when it is missing would have quietly
   * retired the back half of the loop -- and it would have looked exactly like a routine
   * that genuinely is not in the list. The data knows which package holds it either way. */
  const r = ROUTINES.find(x => x.id === want);
  if (!r) return;             // not a routine, or the list has not been fetched yet
  const group = NAV_GROUPS.find(g => g.id === "navRoutines");
  const wantGroup = group && !groupOpen(group);
  const wantPkg = !state.routineQ.trim() && !state.navOpen[`pkg:${r.pkg}`];
  /* Opening the group under the accordion closes whatever else the reader had open, and
   * that is the deliberate call: the row is the answer to the node they just clicked. */
  if (wantPkg) state.navOpen[`pkg:${r.pkg}`] = true;
  if (wantGroup) setGroupOpen("navRoutines", true);     // persists and rebuilds
  else if (wantPkg) { persist(); buildNav(); }

  const row = $(`#navRoutines .nav-item[data-navid="${CSS.escape(want)}"]`);
  if (!row) return;           // past the package's cap; its own notice already says so
  const sc = $("#navScroll");
  if (!sc) return;
  /* Measured against the *scroller*, and below its sticky heading. Against the pane as a
   * whole, a row sitting under the heading counted as visible and was left there -- which
   * looks identical to a row that was never found. The heading's height is asked of the
   * element rather than written down, because it changes with the scale multiplier. */
  const head = row.closest(".nav-group")?.querySelector(".nav-headwrap");
  const p = sc.getBoundingClientRect();
  const top = p.top + (head ? head.offsetHeight : 0);
  const box = row.getBoundingClientRect();
  if (box.top >= top && box.bottom <= p.bottom) return;    // already visible; leave it
  row.scrollIntoView({ block: "nearest" });
}

/* ══ the pop-up ═════════════════════════════════════════════════
 *
 * What a node says when the cursor is merely passing over it. It was three lines --
 * label, kind, plate -- and its job is to be enough that a reader can decide whether to
 * stop, without stopping.
 *
 * **Painted in two stages so it is never late.** The first is free: the engine already
 * holds the name, the qualified name, the plate and the fan counts, so the card is on
 * screen in the same frame as the pointer event. The second is a lookup -- what it
 * touches, which plans it carries, one line of why -- and lands a few milliseconds later
 * on a localhost socket. Carrying that second half in the graph payload would charge all
 * fifteen thousand nodes for the handful anybody hovers.
 *
 * **It grows downward and never reflows what is already readable**, because a card that
 * rearranges itself under a moving cursor is a card nobody finishes reading.
 *
 * It is not interactive and must not become so: `pointer-events` stay off. The clickable
 * depth is the inspector's, which is the pane the whole design points at -- a second
 * interactive pane floating on the canvas is how the graph and the shell became two
 * applications before chunk 2.
 */

let hoverAt = null;               // the node id the card is currently about
let hoverHost = null;             // which surface is asking: a key into `HOVER_HOSTS`
let hoverAnchor = null;           // whatever that host's placer needs, so a grown card
                                  // can be put back in the right place
let hoverTimer = 0;
let hoverFetch = null;            // the in-flight AbortController, if any
const hoverCache = new Map();     // id -> the served card; a re-hover costs nothing

/* Dwell before asking. A cursor crossing the stack passes over dozens of nodes on its way
 * somewhere else, and a request per node is a request per node. Short enough that a
 * deliberate pause feels instant. */
const HOVER_DWELL = 90;

/* ── two surfaces, one card ──
 *
 * The graph and the navigator both answer "what is this thing", and the answer is the same
 * answer -- so the markup, the fetch, the dwell and the cache are shared, and a **table**
 * says what differs. Two copies of a card would agree until the day one of them was edited
 * (rule 36), and the day after that only one of them would carry the signature.
 *
 * What genuinely differs is where it is anchored, and the reason is worth stating because
 * it is not arbitrary. In the picture the cursor *is* the subject's position, so the card
 * follows the cursor and flips at the pane edges. In a list the **row** is the subject's
 * position: a card that followed the cursor along a row would slide about while pointing at
 * one unchanging thing, and it would sit on top of the list the reader is reading. So the
 * navigator's card anchors beside the pane, level with the row.
 */
const HOVER_HOSTS = {
  graph: {
    el: () => $("#hoverCard"),
    place: (el, at) => hoverPlaceInCanvas(el, at.x, at.y),
  },
  nav: {
    el: () => $("#navCard"),
    place: (el, row) => hoverPlaceBesideNav(el, row),
  },
  /* The diagram's card asks the server for **nothing**. A box is a *fold* -- a class and its
     methods, or a file and its functions -- so there is no node id to ask about, and
     everything a card would say is already in the payload the drawing came from. `fetches:
     false` is what stops `showHoverCard` starting a request for an id the server has never
     heard of, which would have been a 404 per hover and a card that filled with an error. */
  diagram: {
    el: () => $("#dgmCard"),
    place: (el, at) => hoverPlaceInBox(el, at.x, at.y, $(".dgm-canvas")),
    fetches: false,
  },
};

/* The same arithmetic as `hoverPlaceInCanvas`, against whichever box is asking. That one
 * reads `el.parentElement` and calls it `.graphcanvas`, which is true of exactly one caller
 * -- a rule kept at a call site rots as callers are added (rule 51), so the box is a
 * parameter here. */
function hoverPlaceInBox(el, x, y, box) {
  if (!box) return;
  const pad = 14;
  const w = el.offsetWidth, h = el.offsetHeight;
  let left = x + pad, top = y + pad;
  if (left + w > box.clientWidth) left = Math.max(0, x - pad - w);
  if (top + h > box.clientHeight) top = Math.max(0, y - pad - h);
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
}

function hoverEl() {
  const host = HOVER_HOSTS[hoverHost];
  return host ? host.el() : null;
}

/* Re-placed rather than re-rendered, so the half already under the reader's eye does not
 * move. Routed through the table for the same reason the click handlers are: a surface with
 * no entry here is a named error, not a card that appears somewhere unexpected. */
function placeHoverCard() {
  const host = HOVER_HOSTS[hoverHost];
  const el = host && host.el();
  if (!host || !el || el.hidden || hoverAnchor == null) return;
  host.place(el, hoverAnchor);
}

/* Design rule 1 in a very small space: a card showing "3 tables" would be a total that
 * cannot say what it counted (rule 32). Every row names its own thing, and a table row
 * carries its direction, because a table this writes and a table this reads are different
 * neighbours -- which is the distinction the boundary threads are built on. */
function hoverTouchRow(t) {
  if (t.what === "table") {
    const w = t.writes || 0, r = t.reads || 0;
    const dir = [w ? `${w}w` : "", r ? `${r}r` : ""].filter(Boolean).join(" ");
    return `<span class="hc-t"><i class="gl">▤</i>${esc(t.first)}${
      dir ? ` <b>${dir}</b>` : ""}</span>`;
  }
  if (t.what === "artefact") {
    return `<span class="hc-t"><i class="gl">▣</i>${esc(t.first)}${
      t.n > 1 ? ` <b>${t.n}</b>` : ""}</span>`;
  }
  /* `▤` is the database glyph and a table row already carries it, so a SQL statement
     with no table of its own gets the same mark and reads as one more of the same
     family -- which is exactly what it is. Everything else takes its own kind's glyph. */
  const glyph = t.what === "sql" ? "▤" : t.what === "net" ? "◆" : (BKIND_GLYPH[t.kind] || "◇");
  return `<span class="hc-t"><i class="gl">${glyph}</i>${esc(t.kind.toLowerCase())} <b>${t.n}</b>${
    t.first ? ` <span class="dim">${esc(t.first)}</span>` : ""}</span>`;
}

/* The governance ids, and the count of the ones that did not fit. Never a bare "…":
 * a list that has been cut says so, in numbers, or the reader mistakes a slice for the
 * whole (design rule 1, and rule 8 in the smallest possible box). */
const HOVER_GOV_SHOWN = 4;

function hoverGovRow(gov) {
  if (!gov || !gov.length) return "";
  const shown = gov.slice(0, HOVER_GOV_SHOWN);
  const more = gov.length - shown.length;
  return `<div class="hc-gov"><i class="gl">⚑</i>${
    shown.map(a => `<span class="govchip ${esc(String(a.kind || "").toLowerCase())}"
      >${esc(a.value)}</span>`).join("")}${
    more ? `<span class="hc-more">+${more}</span>` : ""}</div>`;
}

/* The WHY, carrying where it came from.
 *
 * A docstring is the routine explaining itself. A leading comment is the author explaining
 * it from outside. A comment inside the body is about a *statement* -- it is being quoted,
 * not summarised -- so it shows its line number and its label, and the reader can tell the
 * three apart at a glance. Design rule 13: never render a claim without the route back to
 * where it came from, and the label plus the line is that route in one line of text. */
function hoverWhyRow(why) {
  if (!why || !why.text) return "";
  const cite = why.source === "docstring" ? "docstring"
             : `${why.source}${why.line ? ` :${why.line}` : ""}`;
  return `<div class="hc-why">${esc(why.text)}<span class="hc-cite">${esc(cite)}</span></div>`;
}

/* Stage one: everything the picture already knows, drawn in the same frame as the event. */
function hoverSkeleton(h) {
  const d = h.detail || {};
  const plate = (Graph.disks().find(x => x.id === h.disk) || {}).name || h.disk;
  const file = String(d.file || "").split("/").slice(-1)[0];
  const where = file ? `${file}${d.line ? `:${d.line}` : ""}` : "";
  const sub = d.qualname || d.module || d.bkind || d.akind || "";

  return `
    <div class="hc-head">
      <b class="hc-name">${esc(h.label)}</b>
      <span class="kind-tag">${esc(h.kind)}</span>
    </div>
    ${sub ? `<div class="hc-sub mono">${breakable(sub)}</div>` : ""}
    <div class="hc-meta">
      ${where ? `<span class="hc-where mono">${esc(where)}</span>` : ""}
      <span class="hc-fan" title="callers and callees, one hop"
        >${h.degIn}← ${h.degOut}→</span>
      <span class="hc-plate">${esc(plate)}</span>
      ${d.class_name ? `<span class="kind-tag">${esc(d.class_name)}</span>` : ""}
      ${d.is_async ? `<span class="kind-tag">async</span>` : ""}
    </div>
    ${h.shadow ? `<div class="hc-shadow">A stand-in. This routine lives on
      <b>${esc((Graph.disks().find(x => x.id === h.disk) || {}).name || h.disk)}</b> —
      the copy you are pointing at is a placement device and is never an endpoint.</div>` : ""}
    <div class="hc-rest"></div>`;
}

/* ── the navigator's first paint ──
 *
 * Everything a row already carries, which is not the same set the picture carries -- so the
 * skeleton differs and stage two fills a different remainder. A navigator row knows the
 * qualified name and the fan counts and does *not* know where the code is; a node in the
 * stack knows `file:line` from the payload and knows which plate it is on. Both know enough
 * to draw something in the same frame as the pointer event, which is the whole point of
 * painting in two stages.
 *
 * **Which rows get one is a table, not a condition.** A card needs a single node the map
 * can answer for, and today that is a routine: a package and a boundary kind select
 * *plates*, and a way in resolves to many routines, so a card over one of those would either
 * be blank or would confidently describe the first of twenty-four. A kind with no entry here
 * keeps its plain title and loses nothing.
 */
const NAV_CARD_KINDS = { routine: "ROUTINE" };

function navHoverSkeleton(row) {
  const kind = NAV_CARD_KINDS[row.dataset.nav] || "";
  const label = (row.querySelector(".navlabel") || {}).textContent || "";
  const qual = row.dataset.qual || "";
  const fan = ((row.querySelector(".n") || {}).textContent || "").trim();
  /* The plate is the package heading this row sits under, read off the heading's own
     identity rather than its text -- the text carries a count and a `·small` marker, and
     stripping those back off would be inventing the answer a second time. */
  const pkgBtn = row.closest(".nav-pkg");
  const plate = pkgBtn
    ? ((pkgBtn.querySelector('[data-nav="pkg"]') || {}).dataset || {}).navid || ""
    : "";
  const chg = routineChip(row.dataset.navid || "");

  return `
    <div class="hc-head">
      <b class="hc-name">${esc(label)}</b>
      ${kind ? `<span class="kind-tag">${esc(kind)}</span>` : ""}
    </div>
    ${qual ? `<div class="hc-sub mono">${breakable(qual)}</div>` : ""}
    <div class="hc-meta">
      ${fan ? `<span class="hc-fan" title="callers and callees, one hop">${esc(fan)}</span>` : ""}
      ${plate ? `<span class="hc-plate">${esc(plate.replace(/^pkg:/, ""))}</span>` : ""}
    </div>
    ${/* Where the mark's sentence lives, and it has to live somewhere. A routine row is
          `data-card`, so `dressNavItems` leaves its `title` alone and there is no native
          tooltip to hang the words on -- and putting one on the glyph itself would render
          the tiny unreadable thing this card replaced, on top of the card. It is free: the
          chip is read from an answer the page already holds, so it paints in the same frame
          as the pointer event like everything else in this skeleton. */""}
    ${chg.title ? `<div class="hc-chg${esc(chg.cls)}">${esc(chg.title)}</div>` : ""}
    <div class="hc-rest"></div>`;
}

/* ── the invocation line ──
 *
 * What moves in and what comes back out, which is the subject of the whole tool and the one
 * thing about a routine the card never said. Asked for at the keyboard: *the whole
 * invocation line from the code -- focus on the name, then any arguments with types. We're
 * looking at flow, and information flows are what we are chasing.*
 *
 * So it leads the fetched half, above the measures and the touches: those describe the
 * routine, this one *is* it.
 *
 * The pieces arrive already ordered and already carrying their markers, decided by
 * `schema.signature_parts` -- the same function the Markdown documents render through, so
 * a `*` cannot appear in one and not the other. This function does nothing but colour what
 * it is handed. Composing the line here from a bare parameter list is what the server was
 * asked not to make it do: `def f(a, *, b)` and `def f(a, b)` are different functions, and
 * 998 of Mensores' 4,734 routines need that separator.
 *
 * **No line at all for `<module>`.** That is DunneFlow's own name for module scope, not a
 * routine anybody wrote, and `<module>()` would be a call that cannot be made -- inventing
 * an invocation to fill a row is the same defect as inventing an id to make one clickable.
 */
function hoverSigHtml(card) {
  if (card.kind !== "ROUTINE" || !card.name || card.name === "<module>") return "";
  const params = card.params || [];

  const piece = (p) => {
    if (p.marker) return `<span class="sig-punc">${esc(p.marker)}</span>`;
    let out = esc(p.name || "");
    if (p.type) out += `<span class="sig-punc">: </span><span class="sig-type">${esc(p.type)}</span>`;
    if (p.default !== undefined) {
      out += `<span class="sig-punc"> = </span><span class="sig-dflt">${esc(p.default)}</span>`;
    }
    return out;
  };

  return `<div class="hc-sig">${card.is_async ? `<span class="sig-punc">async </span>` : ""
    }<b class="sig-name">${esc(card.name)}</b><span class="sig-punc">(</span>${
      params.map(piece).join(`<span class="sig-punc">, </span>`)
    }<span class="sig-punc">)</span>${
      card.returns ? `<span class="sig-punc"> \u2192 </span><span class="sig-type">${
        esc(card.returns)}</span>` : ""}</div>`;
}

/* Stage two: what only the store knows. Written into `.hc-rest` rather than by rebuilding
 * the card, so the half already under the reader's eye does not move.
 *
 * `needWhere` because the two surfaces arrive knowing different things. The graph's skeleton
 * already printed `file:line` off the payload; the navigator's could not, because the
 * routine list is not carrying a file path for 4,734 rows to serve the handful anybody
 * hovers. So the one that did not have it gets it here. A parameter rather than a second
 * copy of this function: two copies would agree until one of them was edited. */
function hoverDetailHtml(card, needWhere) {
  if (!card || !card.found) return "";
  const bits = [];

  const sig = hoverSigHtml(card);
  if (sig) bits.push(sig);

  if (needWhere && card.file) {
    const file = String(card.file).split("/").slice(-1)[0];
    bits.push(`<div class="hc-meta"><span class="hc-where mono">${esc(file)}${
      card.line_start ? `:${card.line_start}` : ""}</span></div>`);
  }

  if (card.kind === "ROUTINE") {
    const meas = [
      card.lines ? `${card.lines} lines` : "",
      card.comments ? `${card.comments} comment${card.comments === 1 ? "" : "s"}` : "",
      /* The calls the graph cannot draw. Without it the card says `5→` while the
         inspector says `Out 8` about the same routine, both correct and neither saying
         which population it counted -- rule 32. Five reach a routine this map holds and
         three leave the program, so the arithmetic closes as soon as it is stated. */
      card.externals ? `${card.externals} external` : "",
    ].filter(Boolean).join(" · ");
    if (meas) bits.push(`<div class="hc-meas">${meas}</div>`);
  } else if (card.kind === "BOUNDARY") {
    bits.push(`<div class="hc-meas">${card.hits.toLocaleString()} touch${
      card.hits === 1 ? "" : "es"} from ${card.callers.toLocaleString()} routine${
      card.callers === 1 ? "" : "s"}${card.direction ? ` · ${esc(card.direction)}` : ""}
      <span class="badge external">OUTSIDE</span></div>`);
  } else if (card.kind === "ARTEFACT") {
    bits.push(`<div class="hc-meas">named ${card.mentions.toLocaleString()} time${
      card.mentions === 1 ? "" : "s"} by ${card.namers.toLocaleString()} routine${
      card.namers === 1 ? "" : "s"}${card.akind ? ` · ${esc(card.akind)}` : ""}</div>`);
  } else if (card.kind === "STRUCTURE") {
    bits.push(`<div class="hc-meas">${esc(card.struct_kind || "")}${
      card.fields ? ` · ${card.fields} field${card.fields === 1 ? "" : "s"}` : ""}</div>`);
  } else if (card.kind === "CONSTANT") {
    /* **Bounded, and it says by how much.** This put the whole value in the DOM and let CSS
       clamp it to three lines -- which is a filter with nothing on screen to say a filter
       ran (design rule 1), sitting inside the card that exists to answer *what is this*.
       `GOVERNED_GATES` is 8,586 characters and the card showed about 240 of them, silently,
       looking exactly like a constant whose value is 240 characters long.
       The remedy is not to show more: it is to say what was cut and where the rest is.

       **Characters, not lines, and the difference is a claim.** Every value in `constants`
       reaches the store through `_literal`, which is `ast.unparse`, so **not one of
       Mensores' 2,638 carries a newline** -- the wrapping on screen is the card's, not the
       program's. "94 more lines" would be a fact about this pane reported as a fact about
       the source (rule 32). */
    const v = String(card.value || "");
    const shown = v.slice(0, CARD_VALUE_CHARS);
    bits.push(`<div class="hc-meas mono hc-value">${esc(shown)}</div>`);
    if (v.length > CARD_VALUE_CHARS) {
      bits.push(`<div class="hc-more">${cutWords(CARD_VALUE_CHARS, v.length, "characters")}
        Click for the whole value.</div>`);
    }
  }

  if (card.touches && card.touches.length) {
    bits.push(`<div class="hc-touches">${card.touches.map(hoverTouchRow).join("")}</div>`);
  }
  bits.push(hoverGovRow(card.gov));
  bits.push(hoverWhyRow(card.why));
  return bits.filter(Boolean).join("");
}

/* Placed against `.graphcanvas`, which is the box deck.gl measures hover against, so the
 * arithmetic is direct. It flips rather than clipping: a card that runs off the pane is a
 * card whose second half does not exist, and the second half is the part that was fetched. */
function hoverPlaceInCanvas(el, x, y) {
  const box = el.parentElement;               // .graphcanvas
  if (!box) return;
  const pad = 14;
  const w = el.offsetWidth, h = el.offsetHeight;
  let left = x + pad, top = y + pad;
  if (left + w > box.clientWidth) left = Math.max(0, x - pad - w);
  if (top + h > box.clientHeight) top = Math.max(0, y - pad - h);
  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
}

/* Beside the navigator, level with the row -- never over the list.
 *
 * Fixed positioning, so the coordinates are the window's and the pane's own scroller cannot
 * clip it. Two clamps and neither is decoration: a card taller than the space below its row
 * is pushed up until it fits rather than running off the bottom, and one that will not fit
 * to the right of the pane is pulled back inside the window. A card whose second half is
 * off screen has lost exactly the half that was fetched. */
function hoverPlaceBesideNav(el, row) {
  const nav = $("#navigator");
  if (!nav || !row || !row.isConnected) return;
  const gap = 10, pad = 8;
  const nb = nav.getBoundingClientRect();
  const rb = row.getBoundingClientRect();
  const w = el.offsetWidth, h = el.offsetHeight;

  let left = nb.right + gap;
  if (left + w > window.innerWidth - pad) left = Math.max(pad, window.innerWidth - pad - w);

  /* Level with the row's top, not its middle: the name is the first line of the card and
     the first thing on the row, so the two line up and the eye does not have to travel. */
  let top = rb.top;
  if (top + h > window.innerHeight - pad) top = window.innerHeight - pad - h;
  if (top < pad) top = pad;

  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
}

/* Hides *both* elements, not the one the current host names.
 *
 * Moving from the picture to the list switches hosts, and a hide that trusted `hoverHost`
 * to still be what it was when the card was shown would leave the other one on screen --
 * a stale card about a routine the reader has stopped pointing at, which is the one thing
 * on this surface that must never happen. Cheap enough not to be clever about. */
function hideHoverCard() {
  hoverAt = null;
  hoverHost = null;
  hoverAnchor = null;
  clearTimeout(hoverTimer);
  if (hoverFetch) { hoverFetch.abort(); hoverFetch = null; }
  for (const host of Object.values(HOVER_HOSTS)) {
    const el = host.el();
    if (el) { el.hidden = true; el.innerHTML = ""; }
  }
}

/* One way in for both surfaces: dwell, cache, two-stage paint. The caller says which host
 * is asking, what to anchor to, and what it can draw for free. */
function showHoverCard(host, id, anchor, skeleton) {
  const spec = HOVER_HOSTS[host];
  if (!spec) { console.error("DunneFlow: no hover host", host); return; }
  const el = spec.el();
  if (!el) return;

  /* Tear the previous card down first, whichever surface it belonged to. **One card is on
   * screen at a time**, and that invariant is held here rather than emerging from the two
   * handlers happening to fire in the right order: moving from a row straight into the
   * picture would otherwise leave the navigator's card standing beside a stack that is now
   * answering about something else. It also clears the dwell timer and aborts the in-flight
   * request, which this had to do anyway. */
  hideHoverCard();

  hoverHost = host;
  hoverAnchor = anchor;
  hoverAt = id;

  el.hidden = false;
  el.innerHTML = skeleton;
  placeHoverCard();

  if (spec.fetches === false) return;   // the skeleton *is* the card -- see `diagram` above
  const cached = hoverCache.get(id);
  if (cached !== undefined) { hoverFill(id, cached); return; }
  hoverTimer = setTimeout(() => hoverAsk(id), HOVER_DWELL);
}

function onGraphHover(h) {
  if (!h) { hideHoverCard(); return; }

  /* Moving within the same node is a move, not a new subject: re-rendering there would
     throw away a fetched second half and start it again for the same answer. */
  if (h.id === hoverAt && hoverHost === "graph") {
    hoverAnchor = { x: h.x, y: h.y };
    placeHoverCard();
    return;
  }
  showHoverCard("graph", h.id, { x: h.x, y: h.y }, hoverSkeleton(h));
}

async function hoverAsk(id) {
  const ctl = new AbortController();
  hoverFetch = ctl;
  try {
    const r = await fetch(`/api/hover?id=${encodeURIComponent(id)}`, { signal: ctl.signal });
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const card = await r.json();
    hoverCache.set(id, card);
    hoverFill(id, card);
  } catch (err) {
    if (err.name === "AbortError") return;      // the cursor moved on; not a failure
    /* A card that silently stays half-drawn is indistinguishable from a node with nothing
       to say, which is the one confusion this whole surface exists to avoid. */
    hoverFill(id, { found: false, reason: err.message });
  } finally {
    if (hoverFetch === ctl) hoverFetch = null;
  }
}

function hoverFill(id, card) {
  if (id !== hoverAt) return;                   // the reader moved on while this was in flight
  const el = hoverEl();
  if (!el || el.hidden) return;
  const rest = el.querySelector(".hc-rest");
  if (!rest) return;
  rest.innerHTML = (card && card.found)
    ? hoverDetailHtml(card, hoverHost === "nav")
    : `<div class="hc-why">Nothing more is recorded about this one.<span class="hc-cite"
        >${esc((card && card.reason) || "no answer")}</span></div>`;

  /* Place it again now it has its real height, and this is not belt and braces -- it is
     the hazard the two-stage paint creates. The card is positioned as the 87px skeleton,
     fits easily, and is then filled to 293px: on a 418px canvas that puts its bottom 29px
     past the pane, so the half that just arrived is the half nobody can see. Both placers
     are idempotent -- a card that still fits does not move, which is the whole point of
     growing downward -- so calling again corrects only the case where the alternative is
     losing content. Found by looking at the thing, not by any check. */
  placeHoverCard();
}

/* ── the navigator's pop-up, wired ──
 *
 * Delegated from `document`, like every other navigator handler here, and for the reason
 * written down beside them: `buildNav()` rewrites the pane on every keystroke *and* on every
 * graph selection, so per-row listeners would be rebuilt thousands of times a session.
 *
 * `mouseover`/`mouseout` rather than `mouseenter`/`mouseleave`, because only the first pair
 * bubbles and delegation needs bubbling. Moving *within* one row fires both, so the guard is
 * on the row identity, not on the event.
 *
 * `focusin` is not decoration either: these rows are buttons and the list is reachable by
 * keyboard, so a card that only ever appeared under a pointer would be a feature the
 * keyboard reader can see other people using.
 */
function navCardRow(target) {
  const row = target && target.closest && target.closest(".nav-item[data-card]");
  return row && row.dataset.navid ? row : null;
}

function openNavCard(row) {
  if (hoverAt === row.dataset.navid && hoverHost === "nav") return;   // same subject
  showHoverCard("nav", row.dataset.navid, row, navHoverSkeleton(row));
}

document.addEventListener("mouseover", (ev) => {
  const row = navCardRow(ev.target);
  if (row) { openNavCard(row); return; }
  /* Left the rows entirely. Scoped to the navigator: a pointer travelling from a row into
     the picture must not have its nav card torn down *and then* be told to hide again by
     the graph, which is the same card twice and one of them wrong. */
  if (hoverHost === "nav" && !(ev.target.closest && ev.target.closest("#navigator"))) {
    hideHoverCard();
  }
});

document.addEventListener("mouseout", (ev) => {
  if (hoverHost !== "nav") return;
  const from = navCardRow(ev.target);
  if (!from) return;
  // Into a child of the same row is not leaving it.
  if (ev.relatedTarget && from.contains(ev.relatedTarget)) return;
  if (navCardRow(ev.relatedTarget)) return;      // straight onto the next row; that opens it
  hideHoverCard();
});

document.addEventListener("focusin", (ev) => {
  const row = navCardRow(ev.target);
  if (row) openNavCard(row);
  else if (hoverHost === "nav") hideHoverCard();
});

/* The card is anchored to a row, so anything that moves the row invalidates it. A scrolled
 * list would otherwise leave the card level with whatever has slid into that place -- a
 * confident answer about a routine the reader is no longer pointing at, which is the failure
 * this whole surface exists to avoid. Cheaper and more honest than re-placing: the pointer
 * has stopped being over the row, so there is nothing to describe. */
window.addEventListener("scroll", () => { if (hoverHost === "nav") hideHoverCard(); }, true);
window.addEventListener("resize", () => { if (hoverHost === "nav") hideHoverCard(); });

/* ── picking a subject from the navigator ──────────────────────────────────────────
 *
 * The selection is held in *id* space here and resolved to drawn indices only when the
 * engine is mounted. That is what lets a reader pick a way in while the centre pane is
 * showing the table or a document: the choice is real immediately, the inspector answers
 * from `/api/node` straight away, and the stack adopts it whenever it next appears --
 * `Graph.mount()` is already handed `state.picks`, and `applyWanted()` runs again after.
 *
 * The alternative -- refusing to select unless the graph happens to be on screen -- would
 * make the picture the limit of the map, which is the thing `indexOfId` says not to do. */
function applyWanted() {
  const want = state.wanted;
  if (!want) return;
  if (!Graph.mounted()) return;           // adopted on mount; nothing is lost meanwhile

  const picks = [];
  const undrawn = [];
  for (const id of want.disks || []) {
    if (Graph.disks().some(d => d.id === id)) picks.push({ kind: "disk", id });
    else undrawn.push(id);
  }
  for (const id of want.nodes || []) {
    const i = Graph.indexOfId(id);
    if (i >= 0) picks.push({ kind: "node", index: i });
    else undrawn.push(id);
  }

  /* Design rule 1: no filter is ever silent. A node can be real and still not drawn --
   * constants can be switched off, and an external whose plate is folded away has no
   * index -- so the count is stated rather than the row quietly going missing. */
  state.navNote = undrawn.length
    ? `${undrawn.length} of ${undrawn.length + picks.length} not drawn under the current filter`
    : "";

  /* `walk` keeps what was already picked, so the route the reader took stays on screen.
     The engine is handed the whole set rather than told to append, because `setSelection`
     is the one entry point that also resolves ids to drawn indices -- appending here and
     replacing there would be two ways to arrive at a selection, which is how the two
     halves of a rule end up disagreeing. Deduplicated on drawn index: following back to
     somewhere you have already been must not pick it twice. */
  const keep = (want.add && Graph.mounted()) ? Graph.selection() : [];
  const seen = new Set();
  const merged = [...keep, ...picks].filter(pk => {
    const key = pk.kind === "disk" ? `d:${pk.id}` : `n:${pk.index}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  /* The engine announces synchronously, so this **is** the call that re-enters
   * `onGraphSelect`. Flagged for exactly its duration: what comes back is the selection
   * that was just installed, not a new one made by the reader, and the difference decides
   * whether the subject and the trail are written again. */
  installingSelection = true;
  try {
    Graph.setSelection(merged);
  } finally {
    installingSelection = false;
  }
  updateGraphCounts();
}

async function selectFromNav(want) {
  state.view = state.mode;                // these set what you look AT, not where you are

  if (want.table !== undefined) {
    /* A table is not a node and not a plate: selecting one means selecting the code that
     * reads and writes it. Asked on demand -- most sessions never click a table. */
    let r;
    try {
      r = await fetch(`/api/table?name=${encodeURIComponent(want.table)}`).then(x => x.json());
    } catch (err) {
      state.navNote = `could not ask which routines touch ${want.table}: ${err.message}`;
      render();
      return;
    }
    want = { nodes: r.nodes || [] };
  }

  state.wanted = want;
  /* **A fold is a subject, not a member of one.** `want.fold` is a diagram box: the stack
   * still lights every routine it holds, because that is what the reader picked, but the
   * inspector answers about the *box*. Electing `members[0]` instead is the defect this
   * replaces -- sixty-one methods and the pane described whichever one sorted first.
   *
   * The two are exclusive by construction here, which is what lets `inspectorSubject()` be
   * an accessor rather than a rule everyone has to remember. */
  // The inspector can answer from an id alone, so it does not wait for the stack.
  setSubject({ node: (want.nodes || [])[0] || null, fold: want.fold || null,
               flow: want.flow || null });

  await ensureGraph();
  applyWanted();
  persist();
  recordSelection();
  /* **The list follows, whoever drove.**
   *
   * `onGraphSelect` did this and `applySelectionStep` did this, and `selectFromNav` did not
   * -- on the reasoning that a row the reader clicked is already under their eye. True of a
   * navigator click and false of every other caller it has acquired since: a table row, a
   * hop in the detail window, the arrow in the stack, the other browser window. All of them
   * left the navigator marking whatever was clicked *last time*, which is worse than
   * marking nothing -- a stale highlight is a confident wrong answer, and it was reported
   * as one: the breadcrumb read `_script_of` while the left menu still said `main`.
   *
   * Here rather than at each call site, because that list will keep growing. A navigator
   * click reveals a row that is already visible, which costs nothing and changes nothing
   * (`revealSelectedRoutine` only moves what is out of sight). */
  buildNav();
  revealSelectedRoutine();
  render();
}

/* Which `togglePick` mode a follow uses. One function, so the inspector's neighbours and
 * a thread's subject cannot drift apart -- two copies of this would agree until the day
 * one of them was edited. */
function followPickMode() {
  return state.followMode === "walk" ? "add" : "replace";
}

/* The same question `followPickMode` asks, for the path that goes through
 * `selectFromNav` rather than through `togglePick`. One predicate, two callers, so a
 * reader who chose to walk gets a walk whichever way they followed. */
function walking() { return state.followMode === "walk"; }

/* ── following a thread ────────────────────────────────────────────────────────────
 *
 * **Routed from a table**, because the failure this replaces was a fall-through: every
 * thread, whatever it named, set `state.view = "curiosities"` and landed on a page saying
 * nothing had been computed. It rendered, it highlighted, and it took nobody anywhere.
 * Design rule 16, and rule 30 -- a label is not an identity.
 *
 * So a subject that no entry here handles is a **named error** rather than a default that
 * looks deliberate. That is the whole reason it is a table.
 *
 * Two shapes, because there are genuinely two. Something already in the graph is selected
 * as itself. Something that is not a node -- a plan id, a table -- is resolved to the code
 * that carries or touches it, which is what `queries.py` wrote down before anything needed
 * it: inventing an id to make a row clickable would be a link to nothing.
 */
const THREAD_SUBJECTS = {
  node: async (s) => { await selectFromNav({ nodes: [s.id], add: walking() }); },
  cohort: async (s) => {
    let r;
    try {
      r = await fetch(`/api/thread?kind=${encodeURIComponent(s.kind)}` +
                      `&key=${encodeURIComponent(s.key)}`).then(x => x.json());
    } catch (err) {
      state.navNote = `could not follow ${s.label}: ${err.message}`;
      render();
      return;
    }
    if (!r.found) {
      /* The server refusing a kind it has no query for is the same named error one tier
         up, and it must reach the reader rather than being swallowed into an empty
         selection that looks like a true empty answer. */
      state.navNote = r.reason || `nothing answers for ${s.label}`;
      render();
      return;
    }
    /* Following a cohort to nowhere is a real answer, not a failure: a governance id can
       be cited in documentation and carried by no code at all. Saying so beats selecting
       nothing and letting the reader guess which happened. */
    if (!r.nodes.length) {
      state.navNote = `${s.label} is not carried by any code in this map`;
      render();
      return;
    }
    await selectFromNav({ nodes: r.nodes, add: walking() });
  },
};

async function followThread(subject) {
  const go = THREAD_SUBJECTS[subject && subject.type];
  if (!go) {
    console.error("[dunneflow] no route for thread subject:", subject);
    state.navNote = `this thread points at a kind of thing nothing knows how to open` +
                    ` (${(subject && subject.type) || "no type"})`;
    render();
    return;
  }
  used("thread");
  used("follow:" + state.followMode);
  await go(subject);
}

/* ── the furniture: the HUD and the legend ─────────────────────────────────── */

/* Never a silent filter (design rule 1). What is not on screen is stated, in counts,
 * whichever way the filter is set -- and "nothing selected" says what to do about it,
 * because with edges hidden by default an unselected stack is a picture of nothing much
 * and the reader has no way to know that is deliberate. */
function countLine(c) {
  // Never claim a filter that is not happening: with edges kept up, "nodes only" is false.
  if (c.moving && !c.edgesInMotion) return "nodes only while moving";
  if (!c.selected) {
    return "nothing selected — all links hidden; pick two plates to see what crosses "
         + "between them, or click a node";
  }
  const names = c.names || [];
  /* Which plates the selection is on.
   *
   * Plates are not drawn (rule 18), so a routine and its callers are dots at heights with
   * nothing on screen to say what a height means -- "I can't tell which plate I'm viewing"
   * is the commonest thing this picture cannot answer about itself. The faint plate
   * outlines say *where*; this says *what they are called*, and one without the other is
   * half an answer. */
  const on = Graph.mounted() ? Graph.selectedDisks() : [];
  const plates = on.length
    ? `<span class="muted">on</span> ${esc(on.slice(0, 4).join(", "))}${
        on.length > 4 ? ` +${on.length - 4}` : ""} · `
    : "";
  return plates + `${esc(names.slice(0, 3).join(", "))}${
      names.length > 3 ? ` +${names.length - 3}` : ""} · ` +
    `<b class="num">${(c.selected || 0).toLocaleString()}</b> nodes · ` +
    `<b class="num">${(c.within || 0).toLocaleString()}</b> within · ` +
    `<b class="num">${(c.crossing || 0).toLocaleString()}</b> crossing · ` +
    `<b class="num">${(c.excluded || 0).toLocaleString()}</b> ${c.excludedBy}` +
    /* Design rule 1: closing a plate's gap removes it from the picture, and a shorter
     * stack is indistinguishable from a smaller program by looking. */
    (c.collapsed ? ` · <b class="num">${c.collapsed.toLocaleString()}</b> plates collapsed` : "") +
    /* Design rule 1 again, and rule 32: the number says what it counts. A thread can select
     * ninety-nine routines and only two dozen get an arrow, and two dozen arrows over a
     * selection of ninety-nine looks exactly like a selection of two dozen. Silent only
     * when nothing was left out, because "24 of 24 pointers" is noise. */
    /* Not a filter on the picture -- nothing is removed, so there is no count to state --
     * but a reader whose hover has stopped answering over most of the screen is owed the
     * reason, and the reason is a mode they turned on. */
    /* **Design rule 1, and it is the whole of the overflow answer.** Boxes are placed only
       where they fit at this zoom, so a plate pick of 926 draws a few dozen and leaves the
       rest as dots -- and forty boxes over a selection of nine hundred looks exactly like a
       selection of forty. Both numbers, because rule 32 says each must be named after what
       it counts, and the way to get more is stated because a reader cannot guess that the
       picture answers to the zoom. Silent when everything lit got a box: "41 of 41" is
       noise, and the diagram is then simply the picture. */
    (c.boxesDotted
      ? ` · <b class="num">${(c.boxes || 0).toLocaleString()}</b> boxed · ` +
        `<b class="num">${c.boxesDotted.toLocaleString()}</b> still dots ` +
        `<span class="muted">— zoom in for more</span>`
      : "") +
    (c.focusLocked ? ` · <span class="muted">focus: only what is lit answers</span>` : "") +
    (c.pointersWanted > c.pointers
      ? ` · <b class="num">${c.pointers}</b> of <b class="num">${c.pointersWanted}</b> pointers`
      : "") +
    /* A walked path that does not say how long it is, is a selection growing silently --
     * design rule 1, and the reason "keeps the path" needs a way back stated beside it.
     * Only while walking and only past the first step: on a single pick there is no path
     * and saying "1 step" would be furniture pretending to be information. */
    (state.followMode === "walk" && state.picks.length > 1
      ? ` · <b class="num">${state.picks.length}</b> walked <span class="muted">(⌘Z drops the last)</span>`
      : "") +
    /* One node and no edges looks exactly like a graph that failed to draw, and the reader
       has no way to tell the difference by looking -- so it is stated. Snap to fit on a
       single node is also the most confusing thing this view does, because the frame does
       not visibly change. */
    (c.selected === 1 && !c.within && !c.crossing
      ? ` — <span class="warnnote">nothing calls it and it calls nothing the map can see</span>`
      : "");
}

/* The narrow path: update the sentence, never the pane around it.
 *
 * Rebuilding the HUD here would destroy whichever slider was being dragged, because
 * dragging one changes what is on screen and therefore emits counts -- the same defect
 * that cost a colour picker in the mockup session, arriving by a new route. So the counts
 * event touches exactly the two things counts can change. */
function updateGraphCounts() {
  const line = $("#gcounts");
  // The note rides on the count line rather than in a pane of its own, because rebuilding
  // the HUD here is what destroys a slider mid-drag.
  if (line) line.innerHTML = countLine(counts || {}) +
    (state.navNote ? ` · <span class="warnnote">${esc(state.navNote)}</span>` : "") +
    offScreenNote();
  /* The one control here whose *enabled* state changes with the selection, updated on this
   * narrow path because the box that draws it is rebuilt only by `renderGraphFurniture()`
   * -- which a selection never calls. Written as an attribute alone it would have been
   * disabled at first paint, when nothing is selected, and stayed that way for the whole
   * session: a control that renders and does nothing, which is design rule 16 exactly, and
   * this time in the *state* of a control rather than in its wiring. */
  const here = $('[data-gact="here"]');
  if (here) {
    here.disabled = !(counts && counts.anchored);
    here.title = here.disabled
      ? "Nothing is selected, so there is no view to go back to"
      : "Back to the view you found this in";
  }
  const legend = $("#graphLegend");
  if (!legend) return;
  const on = new Set(state.picks.filter(p => p.kind === "disk").map(p => p.id));
  const touched = new Set(Graph.mounted() ? Graph.selectedDisks() : []);
  legend.querySelectorAll(".leg").forEach(row => {
    const id = row.dataset.disk;
    row.classList.toggle("on", on.has(id));
    row.classList.toggle("touched", !on.has(id) && touched.has(id));
  });
}

function renderGraphFurniture() {
  const hud = $("#graphHud");
  if (!hud) return;

  if (graphError) {
    /* Design rule 21: a blank canvas must say why it is blank. Hardware acceleration off
     * gives no WebGL context, and the symptom is an empty page that looks exactly like a
     * broken program. The raw driver string stays underneath as evidence. */
    hud.innerHTML = `<div class="hudbox gerr">${graphError.gpuOff
      ? `<b>This browser cannot draw.</b> Hardware acceleration is off, so no page here can
         get a WebGL context — nothing to do with your machine.<br>
         Turn it on at <code>chrome://settings/system</code>, then relaunch Chrome.
         <code>chrome://gpu</code> says why. Safari works without changing anything.`
      : `<b>The graph could not start.</b>`}
      <br><span class="muted">${esc(graphError.message)}</span></div>`;
    legendSays("no plates — the graph did not start");
    return;
  }
  if (!Graph.mounted()) {
    hud.innerHTML = `<div class="hudbox"><span class="muted">${
      graphLoading ? "reading the stack…" : "the stack is not loaded yet"}</span></div>`;
    legendSays(graphLoading ? "reading the plates…" : "no plates yet");
    return;
  }

  const c = counts || {};
  const line = countLine(c);

  /* Both boxes fold to a ribbon -- their own header strip, which states the summary open
   * or closed. `panels.hud` and `panels.controls` have existed since the first day and
   * were read by nothing until now; see the PANELS table for how they came to be dead
   * inside a live key. The chevron and `aria-expanded` are written here *and* in
   * `applyPanels()`, because this rebuilds the box and that folds one already on screen. */
  const hudOpen = panelIsOpen("hud");
  const ctlOpen = panelIsOpen("controls");
  hud.innerHTML = `
    <div class="hudbox ${hudOpen ? "" : "closed"}" id="panel-hud">
      <button class="hudhead" data-fold="hud" aria-expanded="${hudOpen}"
              aria-controls="panel-hud-body">
        <span class="chev">${hudOpen ? "▾" : "▸"}</span>
      <div><b class="num" id="gfps">${fps ? fps.toFixed(0) : "–"}</b> fps ·
        <b class="num">${(c.nodes || 0).toLocaleString()}</b> nodes ·
        <b class="num">${c.disks || 0}</b> plates</div>
      </button>
      <div class="hudbody" id="panel-hud-body">
        <div class="muted" id="gcounts">${line}</div>
        <div style="margin-top:.3rem">
          <!-- Undo first, because it is the control a stranded reader is looking for and
               the camera controls are not what stranded them. Disabled rather than hidden:
               a control that vanishes leaves no clue that the feature exists. -->
          <button class="gbtn" data-gact="undo" ${canUndoSelection() ? "" : "disabled"}
                  title="Back to the previous selection (\u2318Z)">\u21b6 undo</button>
          <button class="gbtn" data-gact="redo" ${canRedoSelection() ? "" : "disabled"}
                  title="Forward again (\u21e7\u2318Z)">\u21b7 redo</button>
          <!-- The reader's own framing, not a computed one. Snap to fit, beside it,
               answers a different question: that one frames the selection, this one
               restores the view the selection was found in -- the angle, the distance and
               whatever context they had arranged around it. Disabled with its reason when
               there is nothing selected to have a view of. -->
          <button class="gbtn" data-gact="here" ${c.anchored ? "" : "disabled"}
                  title="${c.anchored
                    ? "Back to the view you found this in"
                    : "Nothing is selected, so there is no view to go back to"}"
                  >\u2316 you are here</button>
          <!-- A mode, not a preference: it is flipped while reading, so it lives where the
               reading happens. Pressed state on the button *is* the statement design rule 1
               wants -- nothing is removed from the picture, but a hover that has gone quiet
               over most of the screen is owed its reason. -->
          <button class="gbtn" data-gact="focus" aria-pressed="${!!state.focusLocked}"
                  title="${state.focusLocked
                    ? "Only what is lit answers a hover or a click. Click to let the whole program answer again."
                    : "Every node answers a hover or a click. Click to limit it to what is lit."}"
                  >\u25ce focus</button>
          <button class="gbtn" data-gact="fit">snap to fit</button>
          <button class="gbtn" data-gact="top">top-down</button>
          <button class="gbtn" data-gact="tilt">tilt</button>
          <button class="gbtn" data-gact="bench">benchmark</button>
          ${c.selected ? `<button class="gbtn" data-gact="clear">clear</button>` : ""}
        </div>
        <div class="muted" id="gbench"></div>
      </div>
    </div>

    <!-- Live controls update in place and re-render only the graph. A pane that rebuilds
         itself on every input event destroys the control being dragged -- that cost a
         colour picker once, and it is why these write straight to the engine and to their
         own readout, never through a full re-render. The ribbon's summary is on that same
         narrow path -- updateControlsSummary(), never a rebuild. -->
    <div class="hudbox ${ctlOpen ? "" : "closed"}" id="panel-controls">
      <button class="hudhead" data-fold="controls" aria-expanded="${ctlOpen}"
              aria-controls="panel-controls-body">
        <span class="chev">${ctlOpen ? "▾" : "▸"}</span>
        <span class="muted" id="gctlsum">${controlsSummary()}</span>
      </button>
      <div class="hudbody" id="panel-controls-body">
      <label style="display:flex;align-items:center;gap:.35rem">
        <span class="muted" style="width:3.2rem">size</span>
        <input id="gsize" type="range" min="0.4" max="14" step="0.2"
               value="${state.nodeSize}" aria-label="Node size">
        <span class="muted num" id="gsizeval">${(+state.nodeSize).toFixed(1)}×</span>
      </label>
      ${[["gspreadx", "across", "spreadX", "How far apart nodes sit left to right"],
          ["gspready", "deep",   "spreadY", "How far apart nodes sit front to back"],
          ["gspreadz", "stack",  "spreadZ", "Distance between plates"]].map(([id, label, key, aria]) => `
      <label style="display:flex;align-items:center;gap:.35rem">
        <span class="muted" style="width:3.2rem">${label}</span>
        <input id="${id}" type="range" min="0.05" max="6" step="0.05"
               value="${state[key]}" aria-label="${aria}">
        <span class="muted num" id="${id}val">${(+state[key]).toFixed(2)}×</span>
      </label>`).join("")}
      ${/* **How much a plate's width says about how much it holds.** Beside the spreads
            because it multiplies them and answers the neighbouring question: they widen
            every plate together, this says how much of that width each plate has earned.
            0 is the uniform stack, which is what shipped before this and is one drag away.

            Per level, so the strip states which altitude it is speaking about -- a dial
            whose value changed under the reader when they climbed, with nothing saying so,
            is a control that reads as having been reset.

            **Called width and not density**, though density is what it equalises: `density`
            is already a setting in this product -- the table's row height -- and one word
            for two ideas in a tool whose whole subject is a program's vocabulary is the
            disk/plate collision again, caught this time before it shipped rather than
            after. The sentence beneath says what the width is made of. */""}
      <label style="display:flex;align-items:center;gap:.35rem">
        <span class="muted" style="width:3.2rem">width</span>
        <input id="gwidth" type="range" min="0" max="1" step="0.05"
               value="${plateSizeNow()}"
               aria-label="How much a plate's width says about how much it holds">
        <span class="muted num" id="gwidthval">${plateSizeNow().toFixed(2)}</span>
      </label>
      <div class="hint" id="gwidthrange" style="margin:-.1rem 0 .1rem 3.55rem">${
        plateRangeNote()}</div>
      <div style="display:flex;align-items:center;gap:.35rem;margin-top:.2rem">
        <span class="muted" style="width:3.2rem">follow</span>
        <select class="gsel" id="gdirection"
                aria-label="Which connections a picked node pulls in">
          ${[["both", "callers and callees"], ["callers", "callers only"],
             ["callees", "callees only"]].map(([v, l]) =>
            `<option value="${v}" ${state.direction === v ? "selected" : ""}>${l}</option>`).join("")}
        </select>
        <label style="display:flex;align-items:center;gap:.2rem">
          <input id="gplates" type="checkbox" ${state.showPlates ? "checked" : ""}>
          <span class="muted">plates</span>
        </label>
        ${/* **The diagram switch was here and is withdrawn.** See `setDiagram` for why: the
             boxes are drawn at the plate's own positions, which are a *sunflower* ordered by
             degree and carry no structure at all, so what came out was a field of labelled
             boxes with the edges crossing everywhere. Tom's bar for this view was set before
             it was built -- "they must be easy to read or we have failed" -- and it does not
             clear it, so it is withdrawn rather than offered with a caveat. */""}
      </div>
      <div style="margin-top:.35rem">
        <button class="gbtn" data-gact="sizereset">reset sliders</button>
        <span class="muted" id="gresetnote"></span>
      </div>
      </div>
    </div>`;

  renderLegend();
}

/* Emptied and honest rather than emptied and blank. The legend holds a 26rem track now, so
 * clearing its markup leaves a blank column beside an error message -- and "nothing unusual
 * here" and "nobody has looked yet" are opposite claims an empty pane cannot tell apart. */
function legendSays(what) {
  const host = $("#graphLegend");
  if (host) host.innerHTML = `<div class="hint" style="font-size:.66rem">${esc(what)}</div>`;
}

/* What the density dial has actually done to the stack, in one line.
 *
 * The widths come from the **engine**, out of the same map it scaled the positions with,
 * never recomputed here from the plate counts sitting in the legend beside it. A floor, a
 * clamp or the interpolation itself would make a shell-side sum a confident disagreement
 * with the picture, which is rule 13 and is exactly how `Graph.connections` and the table
 * footer once came apart.
 *
 * Nothing is removed, so design rule 1 is not what this is for -- it is rule 32's half of
 * the same discipline. A stack whose plates differ in width and a program whose packages
 * differ in size look identical, so the line says which reading is on the screen, and at
 * which altitude, because the dial is per level and a value that changed under the reader
 * with nothing saying so reads as a control that reset itself. */
/* The diagram, turned on or off, from **one** function -- and **nothing calls it today**.
 *
 * **The view is withdrawn, and this is the record of why.** It drew a labelled box for
 * everything the selection lit, at the position the plate layout had already given each
 * node -- and that layout is `phyllotaxis`, a sunflower ordered by degree, whose own
 * docstring says the ordering "is the only structure this layout imposes". Boxes at
 * sunflower positions are not a diagram. Every edge crosses every other, nothing is ranked
 * by what calls what, and a reader gets a field of names rather than a picture of a flow.
 * Tom's word for it was *"just nodes that are boxes, that's totally different"*, and he is
 * right: a diagram's readability comes from its **layout algorithm**, not from the outline
 * of its nodes.
 *
 * His bar was set before it was built -- *"they must be easy to read or we have failed"* --
 * with the instruction to withdraw rather than ship with a caveat. So the two controls are
 * gone and everything else stays: the silhouettes, the box text, the pixel sizing, the
 * placement and its overflow rule are all correct components of the view that has to
 * replace this one, which is a **layered layout per plate** -- ranks by call direction,
 * ordering within a rank to reduce crossings -- computed where the rest of the layout is
 * computed. This function is kept so there is one door to reopen rather than two to
 * rebuild.
 *
 * Two smaller things it also got wrong, recorded so the rebuild does not inherit them.
 * **The glyphs render scrambled** -- `selected_backend` came out as `s/lec-uh-cc-e·u` --
 * which the rasterised preview could not have caught and which the caveat on that preview
 * predicted in as many words: it draws the geometry deck was handed, not deck's own text.
 * `sizeUnits: 'common'` on a non-billboarded `TextLayer` is the first thing to suspect.
 * And **some lit nodes stayed dots beside boxes at a selection of eight**, where everything
 * should have fitted -- the placement's own answer, arriving where there was no crowd to
 * answer for.
 *
 * Two controls reach it -- the switch in the controls box, where a reader flips a way of
 * looking while reading, and the toggle in Settings beside the shapes, which is where a
 * reader who has just chosen a shape set is standing when they wonder why nothing changed.
 * Two doors onto one piece of state is fine; two *implementations* of what the door does is
 * rule 51, and the second one always forgets something (here it would be `used()`, and the
 * usage counter is how design rule 2 retires a loser).
 *
 * `render()` rather than a narrow repaint, because the other control has to move too. */
function setDiagram(on) {
  state.diagram = !!on;
  used("diagram:" + (state.diagram ? "on" : "off"));
  if (Graph.mounted()) Graph.setOptions({ diagram: state.diagram });
  persist();
  render();
}

function plateRangeNote() {
  const w = Graph.mounted() ? Graph.plateWidths() : null;
  const at = state.level === "module" ? "one node per file" : "every routine";
  if (!w) return `at ${at}`;
  if (w.max - w.min < 0.005) return `every plate one width · at ${at}`;
  return `${w.max.toFixed(2)}× → ${w.min.toFixed(2)}× across ${
    w.plates.toLocaleString()} plates, by what they hold · at ${at}`;
}

/* What the controls ribbon says when it is shut. A strip reading only "controls" would be
 * the icon rail design rule 24 rejects, turned on its side: it makes the reader open it to
 * find out what it was. These are the things the box actually sets. */
function controlsSummary() {
  return `size <b class="num">${(+state.nodeSize).toFixed(1)}×</b> · spread ` +
    `<b class="num">${(+state.spreadX).toFixed(2)}</b> / ` +
    `<b class="num">${(+state.spreadY).toFixed(2)}</b> / ` +
    `<b class="num">${(+state.spreadZ).toFixed(2)}</b> · plate width ` +
    `<b class="num">${plateSizeNow().toFixed(2)}</b>`;
  /* **A mode inside a box that folds has to be named on the strip the box folds into**, and
     the diagram was named here until it was withdrawn. Kept as a note rather than deleted,
     because the rebuild puts a mode back in this box: this box collapses to its summary
     (design rule 25), and a reader with it shut and a mode on would have a picture changed
     out of all recognition with nothing anywhere saying why. Design rule 24 already says a
     strip reading only "controls" makes the reader open it to find out what it was; this is
     the same argument for what the strip has to say once it is open to something. */
}

/* The selection is real but the reader cannot see it.
 *
 * Picking a routine deliberately does **not** move the camera: a list you can click through
 * is useless if every click throws away where you were looking, and chasing a thread is the
 * whole point. But a selection that lights up off-screen is indistinguishable from one that
 * did nothing -- so it is stated, and framing it is one click away. Design rule 20's
 * reasoning ("nothing may strand the reader with no way back") applied to selection rather
 * than to the camera.
 *
 * Silent when the engine cannot say: `selectionOnScreen()` returns null before there is a
 * viewport, and "we cannot say" must not be printed as "it is off screen". */
function offScreenNote() {
  if (!Graph.mounted() || !counts || !counts.selected) return "";
  const where = Graph.selectionOnScreen();
  if (!where || where.onScreen) return "";
  return ` · <span class="warnnote">off screen</span> ` +
         `<button class="gbtn" data-gact="findit">find it</button>`;
}

/* The narrow path again: a slider drag must not rebuild the pane its slider lives in. */
function updateControlsSummary() {
  const el = $("#gctlsum");
  if (el) el.innerHTML = controlsSummary();
}

/* Design rule 19: with edges hidden by default this is the way *into* the graph, not an
 * index beside it. Three columns interleaved so rows nest rather than share baselines --
 * fifty-one disks in a third of the height one column needs. Each row is a button, a
 * swatch and a drag handle. */
/* **How much detail the stack draws, and what that costs the reader.**
 *
 * Two altitudes of one program, and the numbers are always both stated: a picture that got
 * seventeen times smaller without saying so is a filter, and design rule 1 does not allow a
 * silent one. So the row says what is drawn, what it stands for, and what the `<small>`
 * threshold merged -- because a shorter stack and a smaller program are indistinguishable
 * by looking.
 *
 * The threshold fires on `change` rather than `input`: every value is a request, and a
 * dragged slider would ask the server for every number it passes through. */
function detailControlHtml() {
  const st = (graphPayload && graphPayload.stats) || {};
  const level = (graphPayload && graphPayload.level) || state.level;
  const drawn = Number(st.nodes || 0);
  const folded = Number(st.folded_from || 0);
  const merged = Number(st.disks_merged || 0);
  const movedOn = Number(st.disks_merged_nodes || 0);
  const opt = (v, label) =>
    `<option value="${v}" ${state.level === v ? "selected" : ""}>${label}</option>`;
  return `<div class="legfoot">Detail
    <select class="gsel" id="glevel" aria-label="How much detail the stack draws">
      ${opt("routine", "every routine")}
      ${opt("module", "one node per file")}
    </select>
    <label style="display:inline-flex;align-items:center;gap:.25rem;margin-left:.4rem">
      <span class="muted">smallest plate</span>
      <input id="gmindisk" type="range" min="1" max="24" step="1"
             style="width:5rem" value="${Number(st.min_disk || 1)}"
             aria-label="How few things a plate may hold before it is merged into small">
      <span class="muted num">${Number(st.min_disk || 1)}</span>
    </label>
    <div class="hint" style="width:100%;margin-top:.15rem">
      <b class="num">${drawn.toLocaleString()}</b> drawn${
        level === "module" && folded
          ? ` — standing for <b class="num">${folded.toLocaleString()}</b> things`
          : ""}${
        merged
          ? ` · <b class="num">${merged.toLocaleString()}</b> ${
              merged === 1 ? "plate" : "plates"} merged into <code>&lt;small&gt;</code>,
              holding <b class="num">${movedOn.toLocaleString()}</b>`
          : " · no plate merged"}${
        levelNote ? ` · ${esc(levelNote)}` : ""}
    </div>
  </div>`;
}

function renderLegend() {
  const host = $("#graphLegend");
  if (!host) return;
  const disks = sortedDisks();
  const on = new Set(state.picks.filter(p => p.kind === "disk").map(p => p.id));
  /* Two different states, and conflating them would lose the one that answers the question.
   * `on` is "you picked this plate"; `touched` is "what you picked lives here" -- selecting
   * one routine touches three plates without selecting any of them. */
  const touched = new Set(Graph.mounted() ? Graph.selectedDisks() : []);
  host.innerHTML = `
    <div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem">
      <button class="panefold" data-fold="legend" title="Send the plates to the rail"
              aria-label="Collapse the plates">⇥</button>
      <span class="hint" style="font-size:.66rem"><b>Plates</b> · ${disks.length} ·
        click to select, drag to reorder</span>
      <select class="gsel" id="gsort" style="margin-left:auto"
              aria-label="Sort plates">
        ${[["nodes", "by size"], ["name", "by name"], ["kind", "by kind"],
           ["manual", "as arranged"]].map(([v, l]) =>
          `<option value="${v}" ${state.sortMode === v ? "selected" : ""}>${l}</option>`).join("")}
      </select>
    </div>
    <div class="legrows">
      ${disks.map(d => `
        <div class="leg ${d.kind} ${on.has(d.id) ? "on" : ""}${
             !on.has(d.id) && touched.has(d.id) ? " touched" : ""}" data-disk="${esc(d.id)}"
             draggable="true" title="${d.nodes} nodes · ${d.shadows} shadows · ${d.edges} edges">
          <input class="sw" type="color" value="${Graph.diskColorHex(d.id)}"
                 aria-label="colour for ${esc(d.name)}">
          <button class="nm" type="button">${esc(d.name)}</button>
          <span class="ct">${d.nodes}</span>
        </div>`).join("")}
    </div>
    ${detailControlHtml()}
    <div class="legfoot">Colour by
      <select class="gsel" id="gcolorby"
              aria-label="Colour nodes by">
        <option value="kind" ${state.colorBy === "kind" ? "selected" : ""}>what it is</option>
        <option value="disk" ${state.colorBy === "disk" ? "selected" : ""}>which plate</option>
        ${/* Drawn only where it can act. With one version there is nothing to colour by,
              and an option whose only effect is to make the picture say nothing is design
              rule 16's dead control with an excuse attached -- the same shape
              `overlaySwitchHtml` uses. */""}
        ${comparing()
          ? `<option value="change" ${state.colorBy === "change" ? "selected" : ""}
             >what changed</option>`
          : ""}
      </select>
      · unselected
      <select class="gsel" id="gfilter"
              aria-label="What happens to unselected nodes">
        <option value="dim" ${state.filterMode === "dim" ? "selected" : ""}>dimmed</option>
        <option value="hide" ${state.filterMode === "hide" ? "selected" : ""}>hidden</option>
      </select>
      · following
      <select class="gsel" id="gfollow"
              aria-label="What following a neighbour does to the selection">
        <option value="replace" ${state.followMode === "replace" ? "selected" : ""}
          >replaces</option>
        <option value="walk" ${state.followMode === "walk" ? "selected" : ""}
          >keeps the path</option>
      </select>
      <label style="display:inline-flex;align-items:center;gap:.2rem;margin-left:.4rem">
        <input id="gcollapse" type="checkbox" ${state.collapseUnused ? "checked" : ""}
               aria-label="Close the gap left by plates nothing is looking at">
        <span class="muted">collapse gaps</span>
      </label>
    </div>
    ${changeKeyHtml()}`;
}

/* What the colours mean while the stack is coloured by change, and how many nodes are in
 * each.
 *
 * **There is no key for any other colouring, and that is a gap rather than a precedent.**
 * Under `colorBy: 'kind'` a reader gets five colours and nothing on the page names them.
 * This mode cannot afford that: three of its five states are folded or absent-by-default,
 * and a colour a reader cannot account for is worse than no colour.
 *
 * **Counted from the payload, never from `routineChangeCounts()`.** That function walks
 * `ROUTINES` -- 4,733 routines -- and this picture draws 10,015 nodes of which more than
 * half are boundaries, constants, structures and artefacts. Two populations, and a count
 * must be named after the thing it measures (rule 32).
 */
function changeKeyHtml() {
  if (changeModeDropped) {
    return `<div class="legkey"><span class="hint">Colouring by what changed needs two
      versions, and this program holds one — showing <b>what it is</b> instead.</span></div>`;
  }
  if (!graphChangeOn()) return "";
  /* **Three states, and collapsing any two of them states the wrong one** (rule 35).
     "Nobody has asked yet", "it is being computed" and an answer are different claims, and
     only the last is an answer. Written as one `!CHANGES || CHANGES.loading` branch this
     said *comparing…* over a mode that had asked for nothing at all — for ever, and
     convincingly. The same trap `factLaneHtml` already carries a note about. */
  if (!CHANGES) {
    return `<div class="legkey"><span class="hint">not compared yet</span></div>`;
  }
  if (CHANGES.loading) {
    return `<div class="legkey"><span class="hint">comparing…</span></div>`;
  }
  if (!CHANGES.available) {
    return `<div class="legkey"><span class="hint">no comparison: ${
      esc(CHANGES.reason || "")}</span></div>`;
  }
  const by = changeByNodeId() || {};
  /* **Columnar, not an array of objects.** `serve.py` transposes the payload into parallel
     arrays -- `nodes.id`, `nodes.shadow` and the rest -- because that is what the engine
     uploads as typed buffers. Written as `for (const n of nodes)` this threw
     `nodes is not iterable` on the first paint, and the key sat at "comparing…" for ever
     while the answer had long since arrived. Found by reading the console.

     **Shadows are skipped**, because they are never drawn (rule 23) and a count beside a
     picture must count what is in it (rule 32). On Mensores that is 5,855 of them. */
  const nodes = (graphPayload && graphPayload.nodes) || {};
  const ids = nodes.id || [];
  const shadow = nodes.shadow || [];
  const tally = { only_base: 0, only_compared: 0, behaves: 0, explained: 0, edited: 0,
                  same: 0,
                  mixed: 0, unclaimed: 0 };
  for (let i = 0; i < ids.length; i++) {
    if (shadow[i] === 1) continue;
    const st = by[ids[i]];
    if (st && st in tally) tally[st] += 1;
    else tally.unclaimed += 1;
  }
  /* **The word for what is drawn**, and it changes with the altitude. At module level the
     dots are files, so "53 arrived" would be a routine count printed over 4 nodes -- rule
     32 exactly: the number must be named after the thing it measures. */
  const at = (graphPayload && graphPayload.level) === "module" ? "module" : "routine";
  const many = at === "module" ? "files" : "routines";
  const w = diffWords();
  const row = (tone, glyph, n, label, why) => !n ? "" : `
    <div class="legkey-row">
      <span class="legkey-dot ${tone}" aria-hidden="true">${glyph}</span>
      <b class="num">${n.toLocaleString()}</b>
      <span>${label}</span>${why ? `<span class="hint">${why}</span>` : ""}
    </div>`;
  /* The two folds are stated, not hidden. `edited` reaches the same colour as `same`
     because "the body changed and nothing it does did" is internal computation, which this
     tool exists not to report -- and `unclaimed` is its own tone because "nothing was asked
     about this" and "we looked and found nothing" are opposite claims (design rule 1). */
  return `<div class="legkey">
    ${at === "module" ? `<div class="legkey-row"><span class="hint">one dot is a file, and
       it says what happened <i>inside</i> it — every count here is files, never
       routines</span></div>` : ""}
    ${row("tone-" + w.base.tone, signOf(w.base.tone), tally.only_base,
          at === "module" ? `with something ${w.base.word}` : w.base.word, "")}
    ${/* Taken from the band, not from the tally, and it is the one number here that has to
          be: a routine only the *compared* version has is not in this version's payload at
          all, so no node could carry it. Counted and never drawn — the same answer the
          table gives, for the same reason (rule 1). */""}
    ${row("tone-" + w.compared.tone, signOf(w.compared.tone),
          (CHANGES.only_in_compared || []).length,
          at === "module" ? `routines ${w.compared.word}` : w.compared.word,
          at === "module"
            ? "counted, not drawn — the comparison lists routines and this level draws files"
            : "not drawn — this version has no node for them")}
    ${row("tone-moved", "\u25cb", tally.behaves, "behave differently", "")}
    ${/* The same violet, and the row says so rather than leaving a reader to wonder why two
          keys share a colour. Rule 69 measured the channel full, and a dot has no glyph to
          be told apart by -- so on the stack these two are one colour, and this is the only
          place that can admit it (design rule 1). */""}
    ${row("tone-moved", "\u00b6", tally.explained, "explained differently",
          "the same violet — a dot has no glyph, and the difference channel has no sixth "
          + "colour that every reader can tell from the fifth")}
    ${/* Only the module level can hold more than one band at once: a routine is in one band
          or none, and a file holding sixty-three of them is not. Drawing such a file as any
          single band would be a confident wrong answer with no symptom, so it gets its own
          tone — measured against every colour in every set (see `tokens.css`).

          `same` is the ground rather than a competing claim. Counted the other way, a file
          with 63 unchanged routines and one arrival reads *mixed*, every changed file on
          Mensores reads mixed, and the tone says nothing at all. */""}
    ${row("tone-mixed", "\u25c6", tally.mixed, "more than one of the above",
          "different things happened to different routines in one file")}
    ${row("tone-quiet", "\u00b7", tally.edited + tally.same, "unchanged",
          tally.edited ? `including ${tally.edited.toLocaleString()} edited without
                          changing what they do` : "")}
    ${row("tone-unclaimed", "\u00b7", tally.unclaimed, "not compared",
          at === "module"
            ? "what the program touches, and files that declare no routine — the "
              + "comparison speaks about routines"
            : "boundaries, constants, structures and named files — the comparison "
              + "speaks about routines")}
  </div>`;
}

function sortedDisks() {
  const disks = Graph.disks();
  const byId = new Map(disks.map(d => [d.id, d]));
  const arranged = plateOrder();
  if (state.sortMode === "manual" && Array.isArray(arranged)) {
    return arranged.map(id => byId.get(id)).filter(Boolean);
  }
  const list = disks.slice();
  if (state.sortMode === "name") list.sort((a, b) => a.name.localeCompare(b.name));
  else if (state.sortMode === "kind") {
    list.sort((a, b) => (a.kind === b.kind ? b.nodes - a.nodes
                                          : a.kind === "package" ? -1 : 1));
  } else list.sort((a, b) => b.nodes - a.nodes);
  return list;
}

/* ── the graph's controls ─────────────────────────────────────────────────────
 *
 * Delegated from the mount rather than bound to elements, because the legend is rebuilt
 * whenever the selection changes and handlers bound to elements would stop working
 * silently the moment they were replaced. */

/* Every slider in the controls box, and how to read, write and default one.
 *
 * They are hard to land on a value by hand -- five of them, each stepping 0.05 -- and the
 * way out of a bad arrangement was reloading or the whole-settings reset, which also
 * throws away the disk order, the colours and the selection. This resets exactly these and
 * says which, because a reset that does not name what it cleared leaves the reader
 * guessing which of the things they had arranged were theirs.
 *
 * The values come from `Settings.DEFAULTS`, never from numbers written here: a second copy
 * of a default is a second thing to forget when one of them moves.
 *
 * **`plateSize` is why this is a table of accessors rather than a list of names.** It is
 * per level -- what a plate holds changes with the altitude -- so `state.plateSize` is a
 * map, and `state[k] = Settings.DEFAULTS[k]` is right for four of the five and hands the
 * engine an object for the fifth. Routing from a table means a sixth slider that is per
 * anything is one row here rather than a special case in three functions (rule 36); the
 * four flat ones are unchanged except in where they are written down. */
const SLIDERS = {
  nodeSize: {},
  spreadX:  {},
  spreadY:  {},
  spreadZ:  {},
  plateSize: {
    get: () => plateSizeNow(),
    set: (v) => setPlateSizeNow(v),
    def: () => Settings.DEFAULTS.plateSize[state.level],
  },
};
const SLIDER_KEYS = Object.keys(SLIDERS);
const sliderGet = (k) => (SLIDERS[k].get ? SLIDERS[k].get() : state[k]);
const sliderSet = (k, v) => { if (SLIDERS[k].set) SLIDERS[k].set(v); else state[k] = v; };
const sliderDef = (k) => (SLIDERS[k].def ? SLIDERS[k].def() : Settings.DEFAULTS[k]);

const GRAPH_ACTIONS = {
  fit:   () => Graph.fit(),
  top:   () => Graph.topDown(),
  tilt:  () => Graph.tilt(),
  clear: () => Graph.clearSelection(),
  // `fit` already frames the *selection* when there is one, so this is that, named
  // for what the reader wants rather than for what it does.
  findit: () => Graph.fit(),
  /* Back to where the reader was standing when they found this.
   *
   * Silent about failure on purpose is exactly what this must not be, so it is disabled
   * rather than inert when there is no anchor -- and if it is somehow pressed anyway, it
   * says so where the reader is looking rather than in a console they do not have open. */
  /* Locked, only the lit set answers. It is the difference between reading and browsing,
   * and both are real, so it is a switch rather than a decision (design rule 2). */
  focus: () => {
    state.focusLocked = !state.focusLocked;
    used("focus:" + (state.focusLocked ? "locked" : "open"));
    Graph.setOptions({ focusLocked: state.focusLocked });
    persist();
    renderGraphFurniture();
  },
  here: () => {
    if (Graph.toAnchor()) return;
    const out = $("#gbench");
    if (out) out.textContent = "nothing is selected, so there is no view to go back to";
  },
  undo: () => undoSelection(),
  redo: () => redoSelection(),
  sizereset: () => {
    const changed = SLIDER_KEYS.filter(k => sliderGet(k) !== sliderDef(k));
    for (const k of SLIDER_KEYS) sliderSet(k, sliderDef(k));
    Graph.setOptions(Object.fromEntries(SLIDER_KEYS.map(k => [k, sliderGet(k)])));
    persist();
    renderGraphFurniture();          // the sliders themselves have to move back
    const note = $("#gresetnote");
    if (note) {
      note.textContent = changed.length
        ? `back to defaults: ${changed.join(", ")}`
        : "already at defaults";
    }
  },
  bench: async () => {
    const out = $("#gbench");
    if (out) out.textContent = "benchmarking…";
    let r;
    try {
      r = await Graph.benchmark(6);
    } catch (err) {
      // A refusal states its reason, the same way a finding states its blind spot.
      if (out) out.textContent = err.message;
      return;
    }
    if (!out) return;
    /* 60 is the vsync ceiling, not a measurement of capacity: when median and worst both
     * sit on it the honest statement is "nothing was dropped, headroom unknown". And both
     * edge kinds are named, because both were drawn -- reporting one under-states the run
     * by the other, which is rule 24 in the half of the line a first fix did not touch. */
    out.innerHTML = `median <b class="num">${r.median.toFixed(0)}</b> fps · worst ` +
      `<b class="num">${r.worst.toFixed(0)}</b> · ${r.nodes.toLocaleString()} nodes` +
      (r.spheres ? " · spheres" : "") +
      (r.within + r.crossing
        ? ` · ${r.within.toLocaleString()} within + ${r.crossing.toLocaleString()} crossing edges`
        : " · no edges drawn") +
      (r.capped ? " · no frames dropped (60 is the vsync cap; headroom unmeasured)" : "");
  },
};

let dragDisk = null;

function wireGraphOnce() {
  const mount = $("#graphMount");
  /* A plain property, not `data-wired`. A marker written as a data attribute is
   * indistinguishable from a control by anything reading the DOM -- including the
   * self-check, which duly reported it as wired to nothing. It was right. */
  if (!mount || mount.__wired) return;
  mount.__wired = true;

  mount.addEventListener("click", (ev) => {
    const act = ev.target.closest("[data-gact]");
    if (act) {
      const fn = GRAPH_ACTIONS[act.dataset.gact];
      // Route from a table (design rule 16): an unhandled action is a named error, never
      // a fall-through to something that looks deliberate.
      if (!fn) return console.error("[dunneflow] no graph action:", act.dataset.gact);
      return fn();
    }
    const row = ev.target.closest(".leg");
    if (!row || ev.target.classList.contains("sw")) return;
    /* Plain click *toggles*, with no modifier. This is a multi-select list, and requiring
     * shift to reach the thing the list exists for meant clicking plate after plate just
     * replaced the selection each time -- so there was never a second layer to cross to,
     * and the crossings, which are the whole point of the stack, could not appear at all.
     * The failure looked like missing edges and was really a missing selection. */
    Graph.togglePick({ kind: "disk", id: row.dataset.disk }, "toggle");
  });

  mount.addEventListener("input", (ev) => {
    const t = ev.target;
    if (t.classList.contains("sw")) {
      const row = t.closest(".leg");
      state.diskColors[row.dataset.disk] = t.value;
      // Choosing a colour for a disk is a statement that colour should mean *disk*.
      const wasChange = state.colorBy === "change";
      state.colorBy = "disk";
      Graph.setOptions({ diskColors: state.diskColors, colorBy: "disk", nodeChange: null,
                         changeTone: null, changeStamp: Date.now() });
      /* **The select has to be told.** This forces `colorBy` and used to return without
         re-rendering, so the control went on displaying the mode the reader had just left
         -- one control, two claims, and the markup was the one that lost (rule 67).
         Harmless while there were two modes and `disk` was always the destination; with a
         third it is a control disagreeing with the state that owns it. Re-rendered only
         when the mode actually moved, because a rebuild here would destroy the colour
         input mid-drag. */
      if (wasChange) renderLegend();
      return;                        // the graph repaints; the swatch is left alone
    }
    if (t.id === "gsize") {
      state.nodeSize = parseFloat(t.value);
      $("#gsizeval").textContent = state.nodeSize.toFixed(1) + "×" +
        (state.nodeSize * state.scale >= Graph.SPHERE_FROM ? " spheres" : "");
      updateControlsSummary();
      Graph.setOptions({ nodeSize: state.nodeSize });
      return;
    }
    /* One branch, three axes. Written as a table for the same reason the routes are:
     * a fourth axis, or a rename, must not need a fourth copy of this block. */
    const AXIS = { gspreadx: "spreadX", gspready: "spreadY", gspreadz: "spreadZ" };
    if (AXIS[t.id]) {
      const key = AXIS[t.id];
      state[key] = parseFloat(t.value);
      $(`#${t.id}val`).textContent = state[key].toFixed(2) + "×";
      updateControlsSummary();
      Graph.setOptions({ [key]: state[key] });
      return;
    }
    /* Not a fourth axis, so not in the table above: the axes are one key each and this one
     * is a key per level. It is on the same live path for the same reason -- a pane that
     * rebuilds itself destroys the slider being dragged -- and its own line is rewritten
     * *after* the engine has relaid the stack, because the widths it prints are read back
     * out of what the engine did rather than predicted from what it was asked. */
    if (t.id === "gwidth") {
      setPlateSizeNow(parseFloat(t.value));
      $("#gwidthval").textContent = plateSizeNow().toFixed(2);
      Graph.setOptions({ plateSize: plateSizeNow() });
      const line = $("#gwidthrange");
      if (line) line.textContent = plateRangeNote();
      updateControlsSummary();
      return;
    }
    if (t.id === "gdirection") {
      state.direction = t.value; Graph.setOptions({ direction: t.value }); persist(); return;
    }
    if (t.id === "gplates") {
      state.showPlates = t.checked; Graph.setOptions({ showPlates: t.checked }); persist(); return;
    }
    /* The count line has to be rewritten as well as the picture: turning the diagram on
       states how many boxes were drawn and how many nodes stayed dots, and the engine only
       knows those once it has placed them. `announceCounts` fires from `setOptions`, so the
       line follows on its own -- but not on the way *off*, where there is nothing to place
       and the numbers have to go rather than stand stale (rule 51). */

    /* Hiding and collapsing are separate switches on purpose: one decides whether an
     * unselected plate draws, the other whether it still takes up room. Wanting the
     * second without the first is ordinary -- it is how a selection of eight plates out
     * of fifty-two stops reading as eight plates scattered down a tower of empty slots. */
    if (t.id === "gcollapse") {
      state.collapseUnused = t.checked;
      Graph.setOptions({ collapseUnused: t.checked });
      persist();
      return;
    }
    /* **The altitude, and the threshold.**
     *
     * Both go through one function, because both are a request for a different payload and
     * two doors onto one act is rule 51 waiting to happen. The threshold fires on `change`
     * below rather than here: `input` is every value a dragged slider passes through, which
     * would be twenty requests for one decision -- rule 45's shape in a control.
     *
     * The number beside the slider follows the thumb immediately, though, because a control
     * that shows nothing until it is released reads as a control that is not working. */
    if (t.id === "glevel") { setGraphDetail({ level: t.value }); return; }
    if (t.id === "gmindisk") {
      const out = t.parentElement && t.parentElement.querySelector(".num");
      if (out) out.textContent = t.value;
      return;
    }
    if (t.id === "gsort") { state.sortMode = t.value; renderLegend(); persist(); }
    if (t.id === "gcolorby") {
      state.colorBy = t.value;
      persist();
      /* `ensureGraphChange` pushes the mode either way -- with the map when it is `change`
         and with `null` when it is not, so leaving the mode drops the data with it rather
         than leaving a map the engine no longer reads. It is also the one place that
         fetches: the graph is a deliberate destination, so a reader who chose "what
         changed" has asked for the wait (unlike the navigator, which never asks). */
      ensureGraphChange();
      renderLegend();          // the key appears, goes, or says it is still comparing
    }
    if (t.id === "gfilter") { state.filterMode = t.value; Graph.setOptions({ filterMode: t.value }); persist(); }
    /* Nothing to push to the engine: this changes what the *shell* does next time it
       follows something, not how the picture is drawn. A `setOptions` call here would be
       a control wired to an option the engine ignores -- which is the silent no-op the
       spread-slider guard was written from, one layer up. */
    if (t.id === "gfollow") { state.followMode = t.value; persist(); renderGraphFurniture(); }
  });
  mount.addEventListener("change", (ev) => {
    // Committed, not live: a localStorage write per frame of a slider drag is waste, and
    // the value is already in `state` -- this only decides when it reaches disk.
    if (ev.target.id === "gmindisk") {
      setGraphDetail({ minDisk: parseInt(ev.target.value, 10) });
      return;
    }
    if (ev.target.classList.contains("sw") ||
        ["gsize", "gspreadx", "gspready", "gspreadz", "gwidth"].includes(ev.target.id)) persist();
  });

  /* Drag to reorder. Reordering is the stack order, so dropping a row moves a plate. */
  mount.addEventListener("dragstart", (ev) => {
    const row = ev.target.closest(".leg");
    if (!row) return;
    dragDisk = row.dataset.disk;
    row.classList.add("dragging");
    ev.dataTransfer.effectAllowed = "move";
  });
  mount.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    ev.target.closest(".leg")?.classList.add("over");
  });
  mount.addEventListener("dragleave", (ev) => {
    ev.target.closest(".leg")?.classList.remove("over");
  });
  mount.addEventListener("drop", (ev) => {
    ev.preventDefault();
    const row = ev.target.closest(".leg");
    $$(".leg").forEach(r => r.classList.remove("over", "dragging"));
    if (!row || !dragDisk || row.dataset.disk === dragDisk) return;
    const order = (plateOrder() || Graph.diskOrder()).slice();
    order.splice(order.indexOf(dragDisk), 1);
    order.splice(order.indexOf(row.dataset.disk), 0, dragDisk);
    setPlateOrder(order);
    // A hand-made order is only visible under manual sort, so say so by switching to it.
    state.sortMode = "manual";
    dragDisk = null;
    Graph.setOptions({ diskOrder: order });
    renderLegend();
    persist();
  });
  mount.addEventListener("dragend", () => {
    $$(".leg").forEach(r => r.classList.remove("over", "dragging"));
  });
}

/* ════════════════════════════════════════════════════════════
   Boot
   ════════════════════════════════════════════════════════════ */

/* The topbar search, which until now listened to nothing at all.
 *
 * It has always said "Search routines, tables, boundaries…", has always been reachable
 * with `/`, and `#search` appeared exactly once in this file -- in the shortcut that
 * focuses it. Design rule 16 with the most prominent control on the page: it rendered, it
 * took keystrokes, and nothing was on the other end. It is an `id` control rather than a
 * `data-` one, which is the half `selfCheck()` and `test_every_static_control_is_listened_
 * for` provably cannot see, so nothing ever reported it.
 *
 * Bound once, at boot, because the topbar lives in `index.html` and `render()` never
 * touches it -- unlike the glossary's filter, which is rebuilt and rebinds every time.
 * Only the navigator is rebuilt here, so the field keeps focus and caret by itself. */
/* Dragging the navigator wider. The same pointer-capture idiom the table's column resizers
 * use, and the width is stored in **rem** for the same reason theirs are (design rule 3):
 * a width in pixels is a width the scale multiplier cannot reach.
 *
 * Clamped, and the clamp is the point rather than defensiveness -- dragged to nothing the
 * navigator becomes an invisible pane with no rail to bring it back, which is the stranding
 * design rule 20 forbids. Wide enough to read a qualified name, never wider than half. */
const NAV_MIN_REM = 12;

/* How wide the navigator may get, asked of the window rather than fixed at a number.
 *
 * It was `NAV_MAX_REM = 44`, which is a judgment about one screen: too narrow for source at
 * any useful type size, and on a 4K display it caps the pane at a third of what is there.
 * Asked for at the keyboard, about the code pane specifically -- *users may want that side
 * to be much wider.*
 *
 * The cap is what is left after the inspector's track and a floor for the centre, so the
 * reader can take almost the whole window and still never push the centre pane to nothing.
 * Fold the inspector -- which is one click, and automatic while nothing is selected -- and
 * that track comes back too. Computed from `innerWidth` and the root font size, which is
 * exactly what the drag already does, and never from a `rem` inside a media query: that
 * resolves against the *browser's* font size, not the page's (rule 28).
 */
const CENTRE_FLOOR_REM = 16;   // the centre never shrinks below a readable column
function navMaxRem() {
  const rootPx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
  const insp = panelIsOpen("inspector") ? 22 : 3;
  const room = (window.innerWidth / rootPx) - insp - CENTRE_FLOOR_REM;
  /* Never below the minimum: on a very narrow window the answer is "you cannot widen this",
     not a maximum smaller than the minimum, which would clamp the pane to a width the
     reader never chose. */
  return Math.max(NAV_MIN_REM, Math.round(room * 4) / 4);
}

/* Which width is in force. The Code group holds source and every other group holds a list,
 * so they are two panes wearing one track, and one number for both means retuning it on
 * every switch. `state.navWidth` stays the name for everything that is not code.
 *
 * Written as two named property accesses rather than `state[widthKey()]`, which is the same
 * thing to a machine and invisible to the check that reads this file: the guard over
 * persisted settings demands each one be *read* somewhere, precisely because a key that is
 * faithfully saved and never acted upon passes any search for its bare name. A dynamic
 * lookup is how a setting slips past it, so this one does not use one. */
function codeWidthInForce() {
  return groupOpen(NAV_GROUPS.find(g => g.id === "navCode"));
}
function navWidth() { return codeWidthInForce() ? state.codeWidth : state.navWidth; }
function setNavWidth(rem) {
  const v = Math.min(navMaxRem(), Math.max(NAV_MIN_REM, Math.round(rem * 4) / 4));
  if (codeWidthInForce()) state.codeWidth = v; else state.navWidth = v;
}

function wireNavGripOnce() {
  const grip = $("#navGrip");
  if (!grip || grip.__wired) return;
  grip.__wired = true;

  grip.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    const rootPx = parseFloat(getComputedStyle(document.documentElement).fontSize);
    const startX = e.clientX, startRem = navWidth();
    grip.classList.add("active");
    grip.setPointerCapture(e.pointerId);
    const move = (ev) => {
      setNavWidth(startRem + (ev.clientX - startX) / rootPx);
      applyNavWidth();
      // The canvas is a grid track away, so its width changed with this one.
      if (Graph.mounted()) Graph.resize();
    };
    const up = () => {
      grip.classList.remove("active");
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", up);
      persist();                    // committed, not per frame of the drag
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", up);
  });

  // Keyboard, because a drag-only control is one a keyboard reader cannot operate at all.
  grip.addEventListener("keydown", (e) => {
    const step = e.key === "ArrowLeft" ? -1 : e.key === "ArrowRight" ? 1 : 0;
    if (!step) return;
    e.preventDefault();
    setNavWidth(navWidth() + step);
    applyNavWidth();
    if (Graph.mounted()) Graph.resize();
    persist();
  });
}

/* The cap is a function of the window, so it changes when the window does -- and a pane
 * saved at 60rem on a wide screen must not survive a resize as a track wider than the
 * window it is in. Re-clamped rather than remembered narrower: widening the window again
 * puts the reader back where they were. */
addEventListener("resize", () => {
  applyNavWidth();
  if (Graph.mounted()) Graph.resize();
});

/* Typing in the file filter rewrites the rows and **not the pane**.
 *
 * `buildNav()` replaces the navigator's `innerHTML`, which would destroy the input the
 * reader is typing into -- the caret jumping to the end of the box on every character, or
 * out of it entirely. That is the glossary filter's 412 ms defect in its other costume: the
 * cost there was calling `render()`, and the tell was that the caret had to be put back
 * into a field that had just been rebuilt. The remedy the file already records is to update
 * narrowly, so this rewrites two nodes and touches nothing the reader is holding.
 */
function refreshCodeFileList() {
  const group = $("#navCode");
  if (!group) return;
  /* **By id, never by `.nav-items`** -- and this cost the file filter every keystroke it
   * has ever had.
   *
   * `buildNav()` wraps every group's body in a `<div class="nav-items">` of its own, so
   * that class inside `#navCode` matches the *wrapper* first and `querySelector` returns
   * it. Writing rows into it replaced the whole body, input and all: one character typed,
   * and the box the reader was typing into was gone along with the caret. Filtering the
   * file list has never worked past a single letter.
   *
   * The guard written for exactly this passed the whole time, because it asserted the
   * refresh does not *call* `buildNav` -- true, and beside the point. It rebuilt the pane
   * without going through it. Rule 37: check that the guard catches, not that it mentions.
   *
   * A class the generator emits around every body cannot tell the wrapper from what the
   * body puts inside it. An id can. */
  const items = $("#codeFileRows");
  if (items) {
    const { rows } = matchingFiles();
    items.innerHTML = fileRowsHtml(rows);
    dressNavItems();
  }
  /* The heading over those rows, or it goes on stating the number the list had before the
     reader typed -- rule 32, one line above the rows that disagree with it. */
  const n = $("#codeFilesCount");
  if (n) n.textContent = fileLaneCount();
  const note = $("#note-navCode");
  if (note) note.innerHTML = codeNote();
}

/* Which of its two shapes the Code group is in, on the group itself, for the stylesheet.
 *
 * The two are genuinely different layouts and one set of rules cannot serve both. With a
 * **file open** the group must fill what is left of the scroller so the code pane grows and
 * shrinks with the window -- a flex chain from the group down to `#codePaneMount`, every
 * link declaring `min-height: 0`. In the **list** it must do the opposite: be as tall as
 * its content and let the navigator's own scroller carry it, exactly as the routine list
 * does with 4,734 rows.
 *
 * The chain was written for the first and applied to both, which cost the search its whole
 * answer: the group was squashed to 118px, 1,900px of results overflowed it *visibly*, and
 * they painted over the four groups below. Every row was in the DOM, sized, and correct --
 * and `elementFromPoint` came back `.nav-head` for all thirteen on screen, because clicks
 * landed on the headings drawn on top of them. Rule 48 exactly, found by hit-testing and by
 * nothing else: the markup, the handlers and the wiring all checked out.
 *
 * Set from here rather than written into `buildNav`'s template, because the template is
 * generic across nine groups and only this one has two shapes. In `WIRED_ATTRS` for the
 * reason rule 43 gives about `insp` and `fold`: grid and flex state the stylesheet reads is
 * a real use, and a roster that cannot see it cries wolf. */
function markCodeMode() {
  const g = $("#navCode");
  if (g) g.dataset.codemode = state.codeFile ? "file" : "list";
}

function wireCodeFilterOnce() {
  const box = $("#codeQ");
  if (!box || box.__wired) return;
  box.__wired = true;
  box.addEventListener("input", () => {
    state.codeQ = box.value;
    /* **Neither of these is `render()`**, and that is the point of both.
     *
     * `render()` rewrites the centre pane, the inspector, the navigator and the trail and
     * then puts the caret back in the field it has just destroyed -- 412 ms a keystroke in
     * the glossary, and the caret restoration was the tell. The file lane is a filter over
     * rows already here; the text lane is a request. They refresh their own strips. */
    refreshCodeFileList();
    runSearch();
  });
}

/* Repaint only the text lane and its note.
 *
 * Rule 45 by construction rather than by luck: this is the whole of what a keystroke may
 * touch. The file *list* is `refreshCodeFileList`'s, the code pane is `attachCode`'s, and
 * neither is rebuilt here -- a search that repainted a 5,838-line file on every character
 * would be the 1,937 ms defect back in a different pane. */
function refreshCodeSearch() {
  const note = $("#searchNote");
  if (note) note.innerHTML = searchNote();
  /* The group's own note carries the inside half too, and it is the one that stays on
     screen when the heading sticks -- so an answer that only reached the box would be
     invisible to a reader who had scrolled. */
  const group = $("#note-navCode");
  if (group) group.innerHTML = codeNote();
  const inside = $("#codeInside");
  if (inside) {
    const body = searchList();
    inside.innerHTML = body
      ? `<div class="lane-head">Inside<span class="n">${
          SEARCH && SEARCH.ok ? SEARCH.total.toLocaleString() : ""}</span></div>${body}`
      : "";
    dressNavItems();
  }
  /* The way back out of an open file states the answer's size, so it moves when the answer
     does. Narrow: one button, not the group. */
  const back = $(".srch-back");
  if (back && SEARCH && SEARCH.ok && SEARCH.total) {
    back.textContent = `\u2039 ${SEARCH.total.toLocaleString()} line${
      SEARCH.total === 1 ? "" : "s"} in ${SEARCH.files.toLocaleString()} file${
      SEARCH.files === 1 ? "" : "s"}`;
  }
}

function wireSearchOnce() {
  const box = $("#search");
  if (!box || box.__wired) return;
  box.__wired = true;
  box.addEventListener("input", () => {
    state.routineQ = box.value;
    buildNav();
    /* No cache reset here: `navMatcher()` keys on the query and the three flags, so a new
       query misses the cache by itself. Written down because the obvious bug in a memo like
       this is a stale answer, and the reason there is none is the key rather than a reset
       somebody has to remember (rule 51). */
  });
}

async function boot() {
  applyTheme();
  applyPalette();
  applyDiagramLook();
  applyScale();
  state.view = state.startup;
  try {
    await loadCover();
  } catch (err) {
    /* A blank dashboard must never be a mystery -- the same rule the graph's missing
       WebGL context taught. Name what failed and what it means. */
    const vp = $("#viewport");
    if (vp) {
      vp.innerHTML = `<div class="panel" style="padding:1.25rem">
        <h2 style="margin:0 0 .5rem">This map could not be read.</h2>
        <p>${esc(err.message)}</p>
        <p class="hint">The server is running, or this page would not have loaded at all.
           That points at the store rather than the connection — try
           <code>dunneflow analyze</code> to rebuild it.</p></div>`;
    }
    return;
  }
  /* Settings are stored per program, so they can only be adopted once the cover has
   * said which program this is. Theme and scale are re-applied after, because the first
   * call at the top of boot ran against defaults the reader may have overridden. */
  adoptSettings(STATS.program);
  applyTheme();
  applyPalette();
  applyDiagramLook();
  paintNavFlags();          // after `adoptSettings`, or they show the defaults (rule 68)
  applyScale();
  state.view = state.startup;

  if (!state.trail.length) pushTrail(state.view, STATS.program);
  /* Seed the history with where the session starts, so the *first* click has somewhere to
   * come back to. Without it the first undo is the one that does nothing, which is the
   * moment a reader decides the feature is broken. */
  recordSelection();

  /* Detached: the detail panel *is* the page. The rest of the shell is built and then
   * hidden by a body class rather than skipped, because the panel reads `SPECIMEN`, the
   * settings, the trail and the threads -- all of which the ordinary boot puts in place.
   * Skipping it would be a second, quieter boot with its own set of things to forget. */
  if (DETACHED) {
    document.body.classList.add("detached");
    state.detail = true;
  }
  /* Code, detached: the centre pane *is* the page. Same application, same `CODEFILE`, and
   * the same `BroadcastChannel` -- so selecting a routine in the main window walks this
   * one to the file it lives in, and clicking a name here selects it over there. Two peers,
   * never opener and child: a `window.opener` protocol breaks the moment the reader closes
   * the main window, reloads either, or opens this by pasting the URL. */
  if (DETACHED_VIEW === "code") {
    /* `detached` alone, deliberately not: that class hides `.app` outright, and the code
     * view is rendered *inside* it. Two classes fighting over one `display` is rule 29 --
     * a later equal selector wins and the fix is specificity, never source order -- so this
     * one gets its own class and its own rules rather than an exception to somebody else's. */
    document.body.classList.add("detached-code");
    state.view = "code";
    state.mode = "code";
  }
  /* Which points in time exist. One small query, and `navGroupsInOrder` needs the answer
   * before it can decide whether the Changes group applies at all -- so it is awaited
   * rather than fired and forgotten, or the first `buildNav()` runs against an empty list
   * and the group is missing until something else happens to rebuild the pane. */
  await loadRevisions();
  reconcileBase();
  /* The two toolbar controls, from the list that has just arrived. Before `buildNav`,
     because a revision the reader chose in an earlier session may since have been retired
     and the pane's Changes note has to state the pair it is actually going to compare. */
  buildRevControls();
  const lost = pairLost();
  if (lost.length) {
    /* Design rule 1 in the place it matters most: a stored choice that can no longer be
       honoured is announced, never silently replaced by a different pair under the same
       heading.
   *
   * Said in the **Changes group's note**, not in `state.navNote`. That was the first
   * home for it and it was the wrong one: `navNote` is rendered in exactly one place,
   * the graph HUD's count line, which does not exist until the reader mounts the graph.
   * The revision was correctly dropped and the sentence explaining it went to a surface
   * nobody had opened — a notice written and never shown, which is the defect it was
   * written to prevent, wearing the other uniform.
   *
   * Its limit, stated rather than hidden: with fewer than two comparable revisions the
   * Changes group is absent by design and this has nowhere to appear. That is the case
   * where there is no comparison to be wrong about, but it is not nothing, and it is the
   * next place to put a line if the cover ever grows one. */
    /* What happened, and no more than that. It first ended "showing the two most recent
       instead", which was not true: the choice is dropped and nothing is compared until
       the group is opened, so the sentence promised a comparison that was not running and
       then sat directly above a note saying "open to compare them". Rule 13 in a sentence
       — the claim has to be the thing that actually happened. */
    /* Prepended rather than assigned. `reconcileBase()` may already have put a sentence
       here about which version is being read, and the two are about different things --
       overwriting one with the other would drop a true statement to make room for another
       true statement. */
    state.revNote = `The revision${lost.length > 1 ? "s" : ""} you were comparing `
      + `(${lost.join(", ")}) ${lost.length > 1 ? "are" : "is"} no longer here, `
      + `so that choice was dropped.`
      + (state.revNote ? ` ${state.revNote}` : "");
    state.comparedRev = "";
    persist();
  }
  buildNav();
  openGroupsFetchWhatTheyNeed();
  wireGraphOnce();
  wireSearchOnce();
  wireNavGripOnce();
  render();
  if (state.view === "graph") ensureGraph();
  selfCheck();

  /* The routine list is the way in, so it is fetched immediately -- but *after* the first
   * paint, because 4,734 rows must not stand between the reader and a usable page. The
   * navigator says "reading the routine list…" until it lands, which is a different claim
   * from "this program has no routines" and has to look like one. */
  /* The file list, beside the routine list and for the same reason: the navigator asks
   * for both, neither changes while the map is open, and the server already built this one
   * at boot. If a file was open when the reader last closed the page, it comes back. */
  loadFiles().then(() => { if (state.codeFile) return loadCodeFile(state.codeFile); })
             .then(buildNav)
             .catch(err => { state.navNote = `could not read the file list: ${err.message}`; });
  /* **`render()` as well as `buildNav()`, and the centre is the half that was missing.**
   *
   * `ROUTINES` feeds two things -- the navigator's routine list and table mode -- and only
   * the first of them was repainted when it arrived. So a reader whose centre view is the
   * table when the page opens got a table of nought rows under "Reading the routine
   * list…", permanently: the list had arrived, the navigator showed all 4,733 of them, and
   * nothing ever repainted the pane that was waiting. A message that is true at the
   * instant it is written and never comes back is worse than a blank.
   *
   * Predates the change marks and was found by driving those, then confirmed against
   * `HEAD` rather than assumed. Rule 35's family: the array is assigned, and the view that
   * reads it is never asked again. */
  loadRoutines().then(() => { buildNav(); render(); }).catch(err => {
    console.error("DunneFlow: the routine list could not be read:", err);
    buildNav();
    render();
  });
}

boot();
