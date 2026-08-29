
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
let TABLES      = [];   // declared tables, busiest first
/* Every routine, each carrying the graph's own node id. Loaded on demand by
   `loadRoutines()` and read by two things: the navigator's routine list and table mode.
   One array, because they are the same list and a second copy is a second thing to get
   out of step. For a long time this was declared here and **assigned by nothing** -- so
   table mode rendered no rows at all, under a footer stating a count from another
   program. A `let X = []` nothing writes to is an empty view with no symptom. */
let ROUTINES    = [];
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

/* A line to reveal once the file it is in has arrived. Not in `state`: it is a debt owed
 * across one fetch, not a place the reader is, and persisting it would restore a scroll to
 * a hit from a search nobody remembers making. Cleared as soon as it is paid, so a later
 * `render()` cannot move the pane a second time under someone reading it. */
let codeGoto = 0;

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
  collapseUnused: false,  // close the gap a plate nothing is looking at leaves behind
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
  ambient: false,         // anomaly badges on nodes
  hideInferred: false,
  density: "comfortable",
  followMode: "replace",   // "replace" | "walk" -- what following a neighbour does
  threadsAll: false,       // the threads panel bounded (rule 8) or opened whole
  selected: null,          // the node id under inspection, or null for nothing picked
  /* What the reader asked for, in id space, before it is resolved to drawn indices.
   * Held here rather than only in the engine so a choice made from the navigator while
   * the centre pane is showing a table or a document is still a real choice. */
  wanted: null,            // {nodes: [id], disks: [id]} | null
  navNote: "",             // what that choice could not draw, stated (design rule 1)
  colourBy: "none",
  colWidths: { q: 26, why: 30, fan: 5 },
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
  triage: {},              // finding id -> "ack" | "notbug" | "tooldefect"
  insp: { in: true, out: true, touches: true, gov: true, sig: false },
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
const PANELS = {
  navigator: { how: "track", grid: ".body",       attr: "nav",    rail: "#navigatorRail" },
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
     * reopen underneath them. */
    return Boolean(state.selected);
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
};

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
};

document.addEventListener("click", (ev) => {
  for (const kind of Object.keys(CODE_ROUTES)) {
    const b = ev.target.closest(`[data-${kind}]`);
    if (b) { CODE_ROUTES[kind](b); return; }
  }
});

document.addEventListener("click", (ev) => {
  const b = ev.target.closest(".nav-item");
  if (!b) return;
  const kind = b.dataset.nav;
  const route = NAV_ROUTES[kind];
  if (!route) {                       // never fail silently again
    console.error("DunneFlow: no route for nav kind", kind, b);
    return;
  }
  $$(".nav-item").forEach(x => x.setAttribute("aria-current", "false"));
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
  if (name === "inspector" && opening && !state.selected) state.inspectorAuto = false;
  if (name === "inspector" && !opening) state.inspectorAuto = true;
  persist();
  applyPanels();
  if (Graph.mounted()) requestAnimationFrame(() => Graph.resize());
});

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
}));

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
    return qual(a).localeCompare(qual(b)) * (k === "fan" ? 1 : dir);
  });
}

/* The columns, in order, in one place. The table's own width is their sum -- see the note
 * on `table.grid` -- and a hand-kept second list of them is how the two would drift. */
const TABLE_COLS = ["q", "why", "fan"];

function viewTable() {
  const cw = state.colWidths;
  const col = (k, label, numeric) =>
    `<th style="width:${cw[k]}rem" class="${numeric ? "numeric" : ""}" data-col="${k}" scope="col">
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
  </div>

  <div class="tablewrap">
    <table class="grid" style="width:${TABLE_COLS.reduce((n, k) => n + cw[k], 0)}rem">
      <caption class="sr-only">Every routine in ${esc(STATS ? STATS.program : "this program")}</caption>
      <thead><tr>
        ${col("q", "Routine")}
        ${col("why", "WHY")}
        ${col("fan", "Connections", true)}
      </tr></thead>
      <tbody>
        ${rows.map(r => `
          <tr data-row="${esc(r.id)}" aria-selected="${state.selected === r.id}" tabindex="0">
            <td><span class="qual"><span class="dim">${esc(r.module)}.</span>${esc(r.name)}</span></td>
            <td style="font-size:.72rem;color:var(--text-muted)">${esc(r.why)}</td>
            <td class="numeric">${esc(String(routineFan(r.id)))}</td>
          </tr>`).join("")}
      </tbody>
    </table>
    <div class="tfoot">
      <span>${ROUTINES.length
        ? `All <b>${ROUTINES.length.toLocaleString()}</b> routines — this is the complete list the
           navigator abbreviates.`
        : "Reading the routine list\u2026"}</span>
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
function triagedCount(sev) {
  return ANOMALIES.filter((a, i) => a.sev === sev && state.triage[i]).length;
}
function worklistFor(sev) {
  return ANOMALIES.map((a, i) => ({ a, i })).filter(x => x.a.sev === sev);
}

const TRIAGE_LABELS = {
  ack:        { label: "Acknowledged",        cls: "info"    },
  notbug:     { label: "Not a bug \u2014 blind spot applies", cls: "certain" },
  tooldefect: { label: "DunneFlow defect",    cls: "broken"  }
};

function viewAnomalies() {
  const counts = sevCounts();
  const list = worklistFor(state.sev);
  if (state.cursor >= list.length) state.cursor = 0;
  const cur = list[state.cursor];
  const done = triagedCount(state.sev);
  const total = list.length;
  const pct = total ? (done / total) * 100 : 0;

  const tab = (k, label, n, colour) => `
    <button role="tab" data-sev="${k}" aria-selected="${state.sev === k}" ${n === 0 ? "disabled" : ""}>
      <span class="sevdot" style="background:${colour}"></span>${label}
      <span class="tabn num">${n}</span>
    </button>`;

  const item = (x, idx) => {
    const t = state.triage[x.i];
    return `<li>
      <button class="wl-item" data-cursor="${idx}" aria-current="${idx === state.cursor}"
              ${t ? 'data-triaged="' + t + '"' : ""}>
        <span class="wl-stripe" style="background:var(--sev-${x.a.sev})"></span>
        <span class="wl-title">${esc(x.a.title)}</span>
        <span class="wl-meta">
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
      </div>
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
          <button class="actbtn triage ${state.triage[cur.i] === "notbug" ? "on" : ""}" data-triage="notbug">
            Not a bug \u2014 the blind spot applies <span class="k">1</span></button>
          <button class="actbtn triage ${state.triage[cur.i] === "ack" ? "on" : ""}" data-triage="ack">
            Real \u2014 acknowledged, leave it for now <span class="k">2</span></button>
          <button class="actbtn triage ${state.triage[cur.i] === "tooldefect" ? "on" : ""}" data-triage="tooldefect">
            This is a DunneFlow defect, not the program's <span class="k">3</span></button>
          ${state.triage[cur.i] ? `<button class="linkbtn" data-triage="" style="align-self:flex-start">Undo</button>` : ""}
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

function viewSettings() {
  const fg = state._fg || "#0d7f75";
  const bg = state._bg || "#ffffff";
  const r = contrast(fg, bg);
  const pass = r >= 4.5;
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
      <div class="panel-head"><h2>Colour</h2><span class="hint">clamped so text stays legible</span></div>
      <div class="panel-body">
        <div class="contrast-demo">
          <div class="swatchrow">
            <label for="fgPick" style="font-size:.78rem;min-width:5rem">Accent</label>
            <input type="color" id="fgPick" value="${fg}">
            <label for="bgPick" style="font-size:.78rem;min-width:5rem">On surface</label>
            <input type="color" id="bgPick" value="${bg}">
            <span class="ratio ${pass ? "pass" : "fail"}" id="ratioOut">${r.toFixed(2)}:1</span>
            <span class="preview-chip" id="previewChip" style="background:${bg};color:${fg}">Sample text</span>
          </div>
          <div id="clampOut">${pass
            ? `<span style="font-size:.72rem;color:var(--text-muted)">Passes WCAG AA for body text — 4.5:1 required.</span>`
            : `<span class="clampnote"><b>✕</b><span>Rejected — ${r.toFixed(2)}:1 is below the 4.5:1 AA minimum for body text.
                 Darken the accent or lighten the surface. The setting says why rather than silently refusing.</span></span>`}</div>
        </div>
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
          <div><div class="lbl">Trail length</div>
            <div class="desc">Oldest steps are dropped past this. Pruned on every step whether
              the trail is shown or not.</div></div>
          <div class="seg" role="group" aria-label="Trail length">
            ${[6, 12, 25].map(n => `<button data-trailcap="${n}"
              aria-pressed="${state.trailCap === n}">${n} steps</button>`).join("")}
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
const SELECTION_HISTORY_CAP = 50;
let selHistory = [];
let selAt = -1;
let restoringSelection = false;

function selectionSnapshot() {
  return { picks: (state.picks || []).slice(), selected: state.selected };
}

function sameSelection(a, b) {
  return a && b && a.selected === b.selected &&
         a.picks.length === b.picks.length &&
         a.picks.every((p, i) => {
           const q = b.picks[i];
           return p.kind === q.kind && p.id === q.id && p.index === q.index;
         });
}

/* Called wherever a selection settles, from either direction -- the graph announcing a
 * click, or the list driving one. One recorder, because two would disagree about order. */
function recordSelection() {
  publishSelection();
  if (restoringSelection) return;
  const now = selectionSnapshot();
  if (sameSelection(selHistory[selAt], now)) return;   // a repaint is not a step
  selHistory = selHistory.slice(0, selAt + 1);         // a new move drops the redo branch
  selHistory.push(now);
  if (selHistory.length > SELECTION_HISTORY_CAP) selHistory.shift();
  selAt = selHistory.length - 1;
}

function applySelectionStep(step) {
  restoringSelection = true;
  try {
    state.picks = step.picks.slice();
    state.selected = step.selected;
    if (Graph.mounted()) Graph.setSelection(state.picks);
    if (state.selected) loadNode(state.selected);
    else { inspectorFor = null; SPECIMEN = null; }
    persist();
    buildNav();
    revealSelectedRoutine();
    render();
  } finally {
    restoringSelection = false;
  }
}

function canUndoSelection() { return selAt > 0; }
function canRedoSelection() { return selAt >= 0 && selAt < selHistory.length - 1; }

function undoSelection() {
  if (!canUndoSelection()) return;
  applySelectionStep(selHistory[--selAt]);
}

function redoSelection() {
  if (!canRedoSelection()) return;
  applySelectionStep(selHistory[++selAt]);
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
const CENTRE_MODES = ["graph", "table", "doc", "code"];

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

function pushTrail(view, label, note) {
  const last = state.trail[state.trail.length - 1];
  if (last && last.view === view && last.label === label) return;   // no repeats
  state.trail.push({ view, label, note: note || "", subject: selectionSnapshot() });
  // Prune on every step whether the trail is on screen or not: a hidden trail that
  // grows without bound is a leak nobody can see.
  const cap = Math.max(2, state.trailCap);
  if (state.trail.length > cap) state.trail.splice(0, state.trail.length - cap);
}

function trailBar() {
  if (!state.trailShown) return "";
  if (state.trail.length < 2 && !state.pins.length) return "";
  return `
  <div class="trailbar">
    <span class="trail-label">Trail</span>
    <ol class="trail">
      ${state.trail.map((t, i) => `
        <li><button class="trailstep ${i === state.trail.length - 1 ? "here" : ""}"
              data-trail="${i}" title="${esc(t.note || t.label)}">${esc(t.label)}</button></li>`).join("")}
    </ol>
    ${state.trail.length > 1 ? `<button class="linkbtn" data-trailback>\u2190 Back</button>` : ""}
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
  return `<pre class="codetable" id="codeTable">${
    CODEFILE.lines.map((text, i) => {
      const n = i + 1;
      const ms = marks.get(n) || [];
      return `<span class="crow" id="crow-${n}"><span class="cnum">${n}</span>` +
        `<span class="cmark">${ms.map(m => `<span class="mk mk-${esc(m.kind)}"` +
              ` title="${esc(m.kind)}${m.note ? " · " + esc(m.note) : ""}"` +
              `>${esc(m.label)}${m.detail ? `<i>${esc(m.detail)}</i>` : ""}</span>`).join("")}</span>` +
        `<span class="ccode">${codeLineHtml(text, links.get(n))}</span></span>`;
    }).join("\n")
  }</pre>`;
}

function viewCuriosities() {
  /* Not yet computed from the store. Said plainly rather than shown as an empty grid,
     because "nothing unusual here" and "nobody has looked yet" are opposite claims and
     an empty list reads as the first one. */
  if (!CURIOSITIES.length) {
    return `<div class="note" style="max-width:56rem">
      <b>Curiosities are not computed yet.</b>
      They are what came out furthest from the middle — 264 comments on one routine, four
      closures deep, a table written twice as often as it is read. Doorways rather than
      problems. This panel stays empty until they are measured from this program rather
      than described from another.</div>`;
  }
  return `
  <div style="max-width:56rem;display:flex;flex-direction:column;gap:.75rem">
    <div class="note">
      <b>${CURIOSITIES.length || "No"} thing${CURIOSITIES.length === 1 ? "" : "s"} about this program unusual enough to be worth a look.</b>
      None of them is a problem. Each is a measurement that came out further from the middle
      than the rest, which is usually where the interesting story is. Pull one and see where it goes.
    </div>
    <div class="curigrid">
      ${CURIOSITIES.map((c, i) => `
        <button class="curi" data-curi="${i}">
          <span class="curi-icon" aria-hidden="true">${c.icon}</span>
          <span class="curi-body">
            <span class="curi-head">${esc(c.head)}<span class="kind-tag">${esc(c.tag)}</span></span>
            <span class="curi-text">${c.body}</span>
            <span class="curi-go">follow this \u2192</span>
          </span>
        </button>`).join("")}
    </div>
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
                 r.module ? `<span class="dim">${esc(moduleTail(r.module))}</span>` : ""}</button>`
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

/* "Not asked for yet", "on its way", "the server refused" and "there is nothing here" are
 * four different things and a blank panel states the wrong one whichever it is. */
function laneState(lane, err, what) {
  if (!VOCAB[lane]) return `<div class="note">${esc(what)} has not been asked for yet.</div>`;
  if (VOCAB[lane] === "loading") return `<div class="note">Reading ${esc(what)}…</div>`;
  if (VOCAB[lane] === "failed") {
    return `<div class="note"><b>${esc(what)} could not be read.</b>
      ${esc(VOCAB[err] || "no reason given")}. Nothing is being shown rather than something
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
        <button class="cite" data-sqlshow="${i}">
          <span class="citeicon" aria-hidden="true">⌗</span>How this number was counted<span class="citego">show the query</span></button>
        ${state.showSql === i ? `<pre class="srcblock sqlblock">${esc(cv.sql)}</pre>
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
  const waiting = laneState("naming", "namingError", "the naming standard");
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
  const waiting = laneState("glossary", "glossaryError", "the glossary");
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

async function loadNode(id) {
  if (id === inspectorFor) return;
  inspectorFor = id;
  SPECIMEN = null;
  render();
  try {
    const r = await fetch(`/api/node?id=${encodeURIComponent(id)}`);
    if (!r.ok) throw new Error(`the server answered ${r.status}`);
    const d = await r.json();
    if (inspectorFor !== id) return;        // the reader moved on while this was in flight
    SPECIMEN = d.found ? d : { notFound: true, id, reason: d.reason };
  } catch (err) {
    if (inspectorFor === id) SPECIMEN = { notFound: true, id, reason: err.message };
  }
  followSelectionIntoCode();
  render();
  loadThreads(id);
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
  const f = FILES.find(x => w.file === x.full || String(w.file).endsWith("/" + x.path));
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
function cut(shown, total, what) {
  if (shown >= total) return "";
  return `<div class="hint" style="margin-top:.35rem">Showing ${shown} of
    ${total.toLocaleString()} ${what}.</div>`;
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
  const touchRow = (glyph, kind, text, line) => `
      <div class="touchrow">
        <span class="gl" aria-hidden="true">${glyph}</span>
        <span class="k">${esc(kind)}</span>
        <span class="t">${text}${line != null
          ? ` <span class="dim" style="color:var(--text-faint)">:${line}</span>` : ""}</span>
      </div>`;
  const touches = [
    ...(t.boundaries || []).map(b => touchRow(BKIND_GLYPH[b.kind] || "◇", b.kind,
        `${esc(b.target)} <span class="dim">${esc(b.direction || "")}</span>`, b.line)),
    /* Direction is the point of a SQL row: a table written twice as often as it is read is
     * a doorway, and read/write is the distinction the database report is built on. */
    ...(t.sql || []).map(q => touchRow("▤", q.operation || "SQL",
        `${esc(q.table || q.statement || "")}`, q.line)),
    /* The full network record, because design rule 8 says an external is a first-class
     * node badged as outside our control, and what makes that useful is knowing the verb,
     * the destination and whether anyone set a timeout. */
    ...(t.net || []).map(nc => touchRow("◆", nc.protocol || "NET",
        `${esc(nc.verb || "")} ${esc(nc.target || nc.host || "")} <span class="dim">${
          nc.timeout ? `timeout ${esc(String(nc.timeout))}` : "no timeout"}${
          nc.retries ? `, ${esc(String(nc.retries))} retries` : ""}</span>`, nc.line)),
    /* A file the program names is not a boundary it touches: naming is a choice the
     * authors made, touching is something the code does. */
    ...(t.artefacts || []).map(a => touchRow("▣", a.kind || "ARTEFACT",
        esc(a.name || a.path || ""), a.line)),
  ];
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
      <button class="panefold" data-fold="inspector" style="float:right"
              title="Collapse the inspector" aria-label="Collapse the inspector">&#x00BB;</button>
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
  $("#graphMount").hidden = !stackOn;
  $("#viewMount").hidden = stackOn;
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
  else if (state.view === "glossary")  { ensureVocabulary(); vp.innerHTML = viewGlossary(); }
  else if (state.view === "naming")    { ensureVocabulary(); vp.innerHTML = viewNaming(); }
  else if (state.view === "inference") vp.innerHTML = viewInference();
  else if (state.view === "curiosities") vp.innerHTML = viewCuriosities();
  else if (state.view === "pins")       vp.innerHTML = viewPins();
  else if (state.view === "settings")  {
    vp.innerHTML = viewSettings();
    /* Painted after the markup, never inside it. The ratio and the refusal are computed
     * against the graph's *current* ground, which depends on the theme and on the graph's
     * own ground setting -- so writing them into the template would freeze a judgment made
     * before either was known, and a clamp stating a stale verdict is worse than none. */
    updatePointerNote();
  }

  $("#inspector").innerHTML = section("inspector", viewInspector);
  applyPanels();
  let vw = document.getElementById("viewerMount");
  if (!vw) { vw = document.createElement("div"); vw.id = "viewerMount"; document.body.appendChild(vw); }
  vw.innerHTML = viewerPanel() + detailPanel();
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
    const id = b.dataset.node;
    if (!id) return;
    const i = Graph.mounted() ? Graph.indexOfId(id) : -1;
    /* `replace` starts a fresh one hop from where you land; `walk` adds, so every node
       you followed stays picked and the hops between them draw themselves -- both ends
       of each are already members, which is all `buildSelectionGeometry` asks. The mode
       argument has existed since the multi-pick work, so this is a choice between two
       values the engine already takes rather than a second way to select. */
    if (i >= 0) Graph.togglePick({ kind: "node", index: i }, followPickMode());
    else { loadNode(id); }
    used("follow:" + state.followMode);
    pushTrail(state.view, b.textContent.trim(), "followed from the inspector");
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
    state.trailCap = parseInt(b.dataset.trailcap, 10);
    const cap = Math.max(2, state.trailCap);
    if (state.trail.length > cap) state.trail.splice(0, state.trail.length - cap);
    render();
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
  const inf = $("#inferredToggle");
  if (inf) inf.addEventListener("click", () => { state.hideInferred = !state.hideInferred; render(); });
  const fgp = $("#fgPick"), bgp = $("#bgPick");
  const liveContrast = () => {
    if (!fgp || !bgp) return;
    state._fg = fgp.value; state._bg = bgp.value;
    const r = contrast(fgp.value, bgp.value);
    const pass = r >= 4.5;
    const out = $("#ratioOut"), chip = $("#previewChip"), verdict = $("#clampOut");
    if (out)  { out.textContent = r.toFixed(2) + ":1"; out.className = "ratio " + (pass ? "pass" : "fail"); }
    if (chip) { chip.style.background = bgp.value; chip.style.color = fgp.value; }
    if (verdict) {
      verdict.innerHTML = pass
        ? `<span style="font-size:.72rem;color:var(--text-muted)">Passes WCAG AA for body text \u2014 4.5:1 required.</span>`
        : `<span class="clampnote"><b>\u2715</b><span>Rejected \u2014 ${r.toFixed(2)}:1 is below the 4.5:1 AA minimum for body text.
             Darken the accent or lighten the surface. The setting says why rather than silently refusing.</span></span>`;
    }
  };
  /* update in place while dragging; only commit to state on release */
  if (fgp) fgp.addEventListener("input", liveContrast);
  if (bgp) bgp.addEventListener("input", liveContrast);

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
    if (v) state.triage[cur.i] = v; else delete state.triage[cur.i];
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

  $$("[data-sqlshow]").forEach(b => b.addEventListener("click", () => {
    const i = parseInt(b.dataset.sqlshow, 10);
    state.showSql = state.showSql === i ? null : i;
    render();
  }));

  $$("[data-crumb]").forEach(b => b.addEventListener("click", () => {
    state.view = b.dataset.crumb;
    pushTrail(state.view, b.textContent.trim());
    render();
  }));

  /* the trail: step back into it, or clear it */
  $$("[data-trail]").forEach(b => b.addEventListener("click", () => {
    const i = parseInt(b.dataset.trail, 10);
    const step = state.trail[i];
    state.trail = state.trail.slice(0, i + 1);
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
  $$("[data-trailback]").forEach(tb => tb.addEventListener("click", () => {
    if (state.trail.length > 1) {
      state.trail.pop();
      goToTrailStep(state.trail[state.trail.length - 1]);
    }
  }));
  $$("[data-trailclear]").forEach(tc => tc.addEventListener("click", () => {
    state.trail = [{ view: state.view, label: "here", note: "trail cleared" }];
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

  /* a curiosity is a doorway */
  $$("[data-curi]").forEach(b => b.addEventListener("click", () => {
    const c = CURIOSITIES[parseInt(b.dataset.curi, 10)];
    pushTrail("curiosities", c.lead, c.head);
    if (c.tag === "anomaly")         { state.view = "anomalies"; state.sev = "suspect"; state.cursor = 0; }
    else if (c.tag === "vocabulary") { state.view = "glossary"; state.termFilter = c.lead; }
    else if (c.tag === "data")       { state.view = "table"; state.mode = "table"; }
    else if (c.tag === "governance") { state.view = "glossary"; state.termFilter = ""; }
    else                             { state.view = "table"; state.mode = "table"; }
    render();
  }));

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

  const sp = $("#srcPath");
  if (sp && !sp.dataset.bound) {
    sp.dataset.bound = "1";
    sp.addEventListener("click", () => {
      const open = sp.getAttribute("aria-expanded") === "true";
      sp.setAttribute("aria-expanded", String(!open));
      /* Long form and short form of the *served* root. It used to toggle between two
         literals naming one developer's disk, which is a confident lie on any other. */
      const full = (STATS && STATS.source_root) || "";
      const parts = full.split("/").filter(Boolean);
      $("#srcPathV").textContent = open ? parts.slice(-2).join("/") : full;
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
    state.triage[cur.i] = { "1": "notbug", "2": "ack", "3": "tooldefect" }[e.key];
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
  "aiop", "airun", "bound", "card", "cite", "citeidx", "closeviewer", "col", "crumb", "curi",
  "cursor", "den", "disk", "drop", "edgesmotion", "egress", "ep", "fold", "gact", "gosev",
  "goto", "graphtheme", "insp", "jump", "layout", "legend", "manifest", "menuorder",
  "mode", "nav", "nav2", "navcap", "navgroups", "pkgopen", "pointerplace", "pointerreset", "pointershown", "reticule",
  "closedetail", "detachdetail", "detail", "detailall", "tablego",
  /* The code browser's three. `codelink` is on every clickable name in the source and
     `CODE_ROUTES` is what listens for all of them -- one table, checked by the guard that
     reads it, so a fourth kind added there without a listener fails by name. */
  "codeback", "codedetach", "codelink", "codeopen", "codemode",
  /* The search's four. `searchline` rides with `searchgo` on the same button and carries no
     handler of its own -- it is the line the click is about, and the roster is a list of
     attributes the shell writes, not only of the ones that are clicked. */
  "searchopen", "searchgo", "searchline", "searchflag",
  "navid", "node", "open", "pane", "pin", "pinnote", "pkgnode", "pkgpick", "qual",
  "resize", "row",
  "scale-set", "sec", "sev", "sevnav", "sort", "sqlshow", "start", "step", "theme",
  "term", "termuse", "theme-set", "thread", "threadlabel", "threadsall", "threadwhy",
  "titled", "toggle",
  "trail", "trailback", "trailcap", "trailclear", "triage", "triaged", "unpin", "viewtab"]);

function selfCheck() {
  const problems = [];
  document.querySelectorAll(".nav-item").forEach(el => {
    if (!NAV_ROUTES[el.dataset.nav]) problems.push(`nav "${el.dataset.nav}" has no route`);
  });
  document.querySelectorAll(".app *, #viewerMount *").forEach(el => {
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
function matchingRoutines() {
  const q = state.routineQ.trim().toLowerCase();
  if (!q) return { rows: ROUTINES, total: ROUTINES.length, filtered: false };
  const rows = [];
  for (const r of ROUTINES) {
    if (r.name.toLowerCase().includes(q) || r.module.toLowerCase().includes(q)) rows.push(r);
  }
  return { rows, total: rows.length, filtered: true };
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
    if (g.open && (g.rows.length < cap || r.id === state.selected)) g.rows.push(r);
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
        ${g.rows.map(r => navItemHtml({
            nav: "routine", label: r.name, sub: moduleTail(r.module), sel: r.id,
            n: routineFan(r.id), qual: `${r.module}.${r.name}`, card: true,
            current: state.selected === r.id,
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

/* The last two segments of a dotted module path.
 *
 * The whole path was shown, clipped from the left with `direction: rtl`, which renders as
 * garbage the moment punctuation is involved -- `mensores._internal._cwd_guard` came out as
 * "...ores_internal_cwd_guard", a string that is not in the program anywhere. Better to
 * choose which part to show than to let the browser cut one arbitrarily; the full path is
 * on the row's title either way. */
function moduleTail(module) {
  const parts = String(module).split(".");
  return parts.length > 2 ? "\u2026" + parts.slice(-2).join(".") : module;
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
  return rows.map(f => `
    <button class="nav-item codefile" data-nav="file" data-navid="${esc(f.path)}"
            data-titled="1" title="${esc(f.module)} — ${f.lines.toLocaleString()} lines, ${
              f.routines} routines, ${f.boundaries} boundaries, ${f.ids} governance ids"
            ${f.path === state.codeFile ? 'aria-current="true"' : ""}>
      <span class="navsub">${esc(dirOf(f.path))}</span>${esc(baseOf(f.path))}
      <span class="n">${f.lines.toLocaleString()}</span>
    </button>`).join("");
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
  return CODEFILE ? `${CODEFILE.file}#${CODEFILE.loading ? "…" : CODEFILE.available}` : "";
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
  return `<div class="codescroll" id="codeScroll"><pre class="codepane">${
    CODEFILE.lines.map((text, i) => {
      const n = i + 1;
      const ms = marksBy.get(n) || [];
      const glyphs = [...new Set(ms.map(m => MARK_GLYPH[m.kind] || "·"))].join("");
      const title = ms.map(markTitle).join("\n");
      return `<span class="cl" id="codeline-${n}"><span class="cn">${n}</span>` +
             `<span class="cm"${title ? ` title="${esc(title)}" data-titled="1"` : ""}>${glyphs}</span>` +
             codeLineHtml(text, byLine.get(n)) + `</span>`;
    }).join("\n")
  }</pre></div>`;
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
      <button class="linkbtn" data-codeopen="1"
              title="Open this file in the centre pane, with its columns">open ▸</button>
    </div>
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
      if (!total) return `nothing matches “${esc(state.routineQ)}”`;
      const pkgs = `${packages.length} package${packages.length === 1 ? "" : "s"}`;
      /* Design rule 1, and note what it does *not* have to say here: the packages are all
         of them. What a package leaves out is stated on that package.
         The third state is the one worth writing down -- a search too broad to open
         anything must say that is why nothing opened, or the closed packages read as a
         control that failed. */
      if (!filtered) return `${total.toLocaleString()} in ${pkgs} — open one, or search`;
      const q = esc(state.routineQ.trim());
      return autoOpen
        ? `${total.toLocaleString()} match “${q}”, in ${pkgs}`
        : `${total.toLocaleString()} match “${q}” — too many to open, in ${pkgs}. `
          + `Keep typing, or open one.`;
    },
    /* A body rather than items, because these rows are two levels deep. Routed through the
       same `navItemHtml`, so a routine row in a package looks like every other row. */
    body: () => routineList() },
  /* Code: the file list, and the file. Stacked, which is the accordion one level down --
     the same shape `navRoutines` uses, for the same reason. */
  { id: "navCode", title: "Code", open: false,
    count: () => FILES.length,
    note: () => codeNote(),
    body: () => codeList() },
  { id: "navExplore", title: "Explore", open: true, items: () => [
      { nav: "curiosities", label: "Worth a look", n: "" },
      { nav: "pins",        label: "Kept",         n: state.pins.length, id: "navPins" },
    ] },
  { id: "navWaysIn", title: "Ways in", open: true, items: () => [
      { nav: "cover", label: "Overview", n: "cover", current: state.view === "cover" },
      // Bounded, and it says so: the full list is the cover's own ranking, one
      // click away. Rule 8 -- abbreviation only where the whole sits beside it.
      /* `sel` is the identity, and it is the whole point: without it these six rows
       * differed only by the label they printed, and every one of them did the same
       * nothing. A label is not an identity. */
      ...ENTRYPOINTS.slice(0, 6).map(e => ({
        nav: "ep", label: e.name, n: e.reach, sel: (e.nodes || []).join(" "),
      })),
    ] },
  { id: "navPkgs", title: "Packages", open: true, items: () => [
      // A package is a plate, and the plate id is what the legend already selects by.
      ...PKGS.slice(0, 8).map(p => ({ nav: "pkg", label: p.id, n: p.n, sel: `pkg:${p.id}` })),
    ] },
  { id: "navBounds", title: "Boundaries", open: false, items: () => [
      ...BOUNDARIES.map(b => ({ nav: "b", label: b.kind, n: b.n, sel: `ext:${b.kind}` })),
    ] },
  { id: "navTables", title: "Database", open: true, items: () => [
      // A table is not a node and not a plate, so the id here is its name and the route
      // asks the server which routines touch it. See TABLE_ROUTINES in queries.py.
      ...TABLES.slice(0, 8).map(t => ({ nav: "t", label: t.name, n: t.n, sel: t.name })),
    ] },
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
  const first = state.menuOrder === "explore" ? "navExplore" : "navWaysIn";
  const chosen = NAV_GROUPS.find(g => g.id === first);
  if (!chosen) return NAV_GROUPS.slice();
  return [chosen, ...NAV_GROUPS.filter(g => g !== chosen)];
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
  buildNav();
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
  TABLES      = d.tables      || [];
  STATS       = Object.assign({}, d.stats, { anomalies: d.anomalies, program: d.program,
                                             vocabulary: d.vocabulary || null });

  const prog = $("#prog");
  if (prog) {
    prog.innerHTML = `<option>${esc(d.program)} — ${Number(d.stats.files).toLocaleString()} files</option>`;
  }
  const sp = $("#srcPathV"), spb = $("#srcPath");
  if (sp && d.stats.source_root) {
    const parts = String(d.stats.source_root).split("/").filter(Boolean);
    sp.textContent = parts.slice(-2).join("/");
    if (spb) spb.title = d.stats.source_root;
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
    title: f.title,
    kind: f.kind,
    conf: f.confidence,
    n: f.count,
    where: f.line ? `${f.file}:${f.line}` : f.file,
    detail: f.detail,
    blind: f.blind_spot,
    sev: { BROKEN: "broken", SUSPECT: "suspect", INFO: "info" }[f.severity] || "info",
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
  "theme", "scale", "startup", "mode", "menuOrder", "trailShown", "trailCap",
  "density", "ambient", "hideInferred", "colWidths", "insp", "sortKey", "sortAsc",
  "egress", "aiOps", "triage", "pins", "usage", "graphLayout",
  "diskOrder", "diskColors", "colorBy", "sortMode", "filterMode", "direction",
  "nodeSize", "spreadX", "spreadY", "spreadZ", "collapseUnused",
  "searchCase", "searchWord", "searchRegex",
  "panels", "inspectorAuto", "navWidth", "codeWidth", "codeFile", "navGroups",
  "navOpen", "navCap",
  "showPlates", "picks", "graphTheme", "edgesInMotion", "pointerShown", "pointerColor", "pointerPlace", "reticuleShown", "focusLocked",
];

let settings = null;      // the loaded blob; `state` is the live copy
let program = null;
let graphPayload = null;
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
    const r = await fetch("/api/graph");
    if (!r.ok) throw new Error(`the server answered ${r.status} for /api/graph`);
    graphPayload = await r.json();
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

  Graph.mount($("#graphStage"), graphPayload, {
    diskOrder: state.diskOrder, diskColors: state.diskColors, colorBy: state.colorBy,
    filterMode: state.filterMode, direction: state.direction, nodeSize: state.nodeSize,
    spreadX: state.spreadX, spreadY: state.spreadY, spreadZ: state.spreadZ,
    collapseUnused: state.collapseUnused, showPlates: state.showPlates, scale: state.scale,
    edgesInMotion: state.edgesInMotion, picks: state.picks,
    pointerShown: state.pointerShown, pointerColor: pointerRgb(),
    pointerPlace: state.pointerPlace, reticuleShown: state.reticuleShown,
    focusLocked: state.focusLocked,
  });
  /* Read back the order the engine resolved. A saved order from a graph that has since
   * changed is discarded there, and the shell must not go on persisting the stale one --
   * that is how a setting outlives the thing it described. */
  state.diskOrder = Graph.diskOrder();
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
  state.selected = sel.node ? sel.node.id : null;
  if (sel.node) loadNode(sel.node.id);
  else { inspectorFor = null; SPECIMEN = null; }
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
  if (!state.selected) return;
  /* From the routine, not from the row. A closed package draws no rows at all now, so
   * looking the element up first and giving up when it is missing would have quietly
   * retired the back half of the loop -- and it would have looked exactly like a routine
   * that genuinely is not in the list. The data knows which package holds it either way. */
  const r = ROUTINES.find(x => x.id === state.selected);
  if (!r) return;             // not a routine, or the list has not been fetched yet
  const group = NAV_GROUPS.find(g => g.id === "navRoutines");
  const wantGroup = group && !groupOpen(group);
  const wantPkg = !state.routineQ.trim() && !state.navOpen[`pkg:${r.pkg}`];
  /* Opening the group under the accordion closes whatever else the reader had open, and
   * that is the deliberate call: the row is the answer to the node they just clicked. */
  if (wantPkg) state.navOpen[`pkg:${r.pkg}`] = true;
  if (wantGroup) setGroupOpen("navRoutines", true);     // persists and rebuilds
  else if (wantPkg) { persist(); buildNav(); }

  const row = $(`#navRoutines .nav-item[data-navid="${CSS.escape(state.selected)}"]`);
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
};

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
    /* Whole, never shortened here. Rule 8 is about ingest, but a value cut in the one place
       a reader looks at it is the same loss one layer later; the box clamps it visually and
       the full text stays in the DOM. */
    bits.push(`<div class="hc-meas mono hc-value">${esc(String(card.value || ""))}</div>`);
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
  Graph.setSelection(merged);             // the engine announces; onGraphSelect does the rest
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
  // The inspector can answer from an id alone, so it does not wait for the stack.
  const first = (want.nodes || [])[0] || null;
  state.selected = first;
  if (first) loadNode(first); else { inspectorFor = null; SPECIMEN = null; }

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

/* What the controls ribbon says when it is shut. A strip reading only "controls" would be
 * the icon rail design rule 24 rejects, turned on its side: it makes the reader open it to
 * find out what it was. These are the two things the box actually sets. */
function controlsSummary() {
  return `size <b class="num">${(+state.nodeSize).toFixed(1)}×</b> · spread ` +
    `<b class="num">${(+state.spreadX).toFixed(2)}</b> / ` +
    `<b class="num">${(+state.spreadY).toFixed(2)}</b> / ` +
    `<b class="num">${(+state.spreadZ).toFixed(2)}</b>`;
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
    <div class="legfoot">Colour by
      <select class="gsel" id="gcolorby"
              aria-label="Colour nodes by">
        <option value="kind" ${state.colorBy === "kind" ? "selected" : ""}>what it is</option>
        <option value="disk" ${state.colorBy === "disk" ? "selected" : ""}>which plate</option>
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
    </div>`;
}

function sortedDisks() {
  const disks = Graph.disks();
  const byId = new Map(disks.map(d => [d.id, d]));
  if (state.sortMode === "manual" && Array.isArray(state.diskOrder)) {
    return state.diskOrder.map(id => byId.get(id)).filter(Boolean);
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

/* The four sliders are hard to land on a value by hand -- four axes, each 0.05 apart --
 * and the way out of a bad arrangement was reloading or the whole-settings reset, which
 * also throws away the disk order, the colours and the selection. This resets exactly the
 * four and says which, because a reset that does not name what it cleared leaves the
 * reader guessing which of the things they had arranged were theirs.
 *
 * The values come from `Settings.DEFAULTS`, never from numbers written here: a second copy
 * of a default is a second thing to forget when one of them moves. */
const SLIDER_KEYS = ["nodeSize", "spreadX", "spreadY", "spreadZ"];

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
    const changed = SLIDER_KEYS.filter(k => state[k] !== Settings.DEFAULTS[k]);
    for (const k of SLIDER_KEYS) state[k] = Settings.DEFAULTS[k];
    Graph.setOptions(Object.fromEntries(SLIDER_KEYS.map(k => [k, state[k]])));
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
      state.colorBy = "disk";
      Graph.setOptions({ diskColors: state.diskColors, colorBy: "disk" });
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
    if (t.id === "gdirection") {
      state.direction = t.value; Graph.setOptions({ direction: t.value }); persist(); return;
    }
    if (t.id === "gplates") {
      state.showPlates = t.checked; Graph.setOptions({ showPlates: t.checked }); persist(); return;
    }
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
    if (t.id === "gsort") { state.sortMode = t.value; renderLegend(); persist(); }
    if (t.id === "gcolorby") { state.colorBy = t.value; Graph.setOptions({ colorBy: t.value }); persist(); }
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
    if (ev.target.classList.contains("sw") ||
        ["gsize", "gspreadx", "gspready", "gspreadz"].includes(ev.target.id)) persist();
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
    const order = state.diskOrder.slice();
    order.splice(order.indexOf(dragDisk), 1);
    order.splice(order.indexOf(row.dataset.disk), 0, dragDisk);
    state.diskOrder = order;
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
  });
}

async function boot() {
  applyTheme();
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
  buildNav();
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
  loadRoutines().then(buildNav).catch(err => {
    console.error("DunneFlow: the routine list could not be read:", err);
    buildNav();
  });
}

boot();
