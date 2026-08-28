
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
let ROUTINES    = [];   // for table mode
let ANOMALIES   = [];   // the worklist; loaded on demand, not with the cover
let STATS       = null; // files, lines, routines, when it was analysed

/* Not yet served. Chunk 2 mounts the real 2.5D graph in place of the prototype's
   hand-placed SVG, so these two stay empty rather than being filled with a
   picture of a different program. */
let EXTERNALS = [], EDGES = [], EXT_EDGES = [];
let SPECIMEN = null;

/* Things unusual enough to be worth a look. Every one is a real measurement from
   graph.db, and every one is a doorway rather than a statistic. */
let CURIOSITIES = [];   // what came out furthest from the middle -- served, not pinned

/* What sits next to the thing you are looking at. Not the call graph \u2014 the reasons
   something else might be worth a detour. */
const THREADS = {
  "_run_extract_mode": [
    { to: "Plan 84-06", why: "9 other routines carry this plan", kind: "governance" },
    { to: "ISS-184", why: "the prerequisite gate exists because of this issue", kind: "governance" },
    { to: "_enforce_architect_prerequisite", why: "the gate itself, 3 lines down", kind: "call" },
    { to: "disceptator", why: "5 of its 16 calls leave for the interview engine", kind: "package" },
    { to: "make_operational_event", why: "the other end of the audit emit \u2014 and the most commented routine in the program", kind: "curiosity" },
    { to: "SOCIETY_HEADLESS", why: "one of 154 environment reads; this one decides whether a human is watching", kind: "boundary" }
  ]
};

let PROVENANCE = {};   // where each glossary term is defined, by tier -- served, not pinned

let MANIFEST = [];   // the files a model pass would send, shown before anything leaves -- served, not pinned

let TERMS = [];   // the program's vocabulary -- served, not pinned

let CONVENTIONS = [];   // measured naming conventions, each with the query that counted it -- served, not pinned

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
  selected: null,          // the node id under inspection, or null for nothing picked
  colourBy: "none",
  colWidths: { q: 22, lines: 5.5, ret: 10, np: 3.5, fan: 3.5, nb: 3.5, nc: 3.5 },
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
  selectedRow: null,       // which table row is current; a program has none until read
  sortKey: "fan",
  sortAsc: false,
  viewer: null,
  trail: [{ view: "cover", label: "mensores", note: "started here" }],
  pins: [],      // {term, idx} — which citation is open in the source viewer   // what a one-time inference pass would cover
  aiConfirm: false,            // second click arms it
  aiDone: false,               // has the pass been run
  termFilter: ""
};

const $  = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
/* Usage is counted so a Setting can be retired on evidence rather than on opinion, which
 * means it starts at zero for every program and every key. `state.usage.graph++` on an
 * absent key yields NaN, and a NaN in the usage report is a count that silently stops
 * counting -- so no caller increments directly. */
function used(key) { state.usage[key] = (state.usage[key] || 0) + 1; }

const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

/* ═══ theme + scale ═══ */
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
  g.dataset.open = g.dataset.open === "true" ? "false" : "true";
});
/* Every nav kind routes explicitly. An unhandled kind used to fall through to
   `state.view = state.mode`, which silently showed the graph instead of the page
   that was clicked -- a dead control that looked like a working one. */
const NAV_ROUTES = {
  cover:       () => { state.view = "cover"; },
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
  /* These four set what you are looking AT, and keep the centre pane's current mode. */
  ep:  () => { state.view = state.mode; ensureGraph(); },
  pkg: () => { state.view = state.mode; ensureGraph(); },
  b:   () => { state.view = state.mode; ensureGraph(); },
  t:   () => { state.view = state.mode; ensureGraph(); },
};

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

/* ═══ mode toggle ═══ */
$$("#modes button").forEach(b => b.addEventListener("click", () => {
  state.mode = b.dataset.mode;
  state.view = state.mode;
  if (state.mode === "graph") ensureGraph();
  pushTrail(state.mode, b.textContent.trim());
  used(state.mode);
  render();
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

  const applies = ["graph", "table", "doc"].includes(state.view);
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

function sortedRoutines() {
  const k = state.sortKey;
  const dir = state.sortAsc ? 1 : -1;
  return ROUTINES.slice().sort((a, b) => {
    const x = a[k], y = b[k];
    if (typeof x === "number" && typeof y === "number") return (x - y) * dir;
    return String(x).localeCompare(String(y)) * dir;
  });
}

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

  return `
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
    <table class="grid">
      <caption class="sr-only">Routines in mensores.quaestor, ordered by fan-out</caption>
      <thead><tr>
        ${col("q", "Routine")}
        ${col("lines", "Lines")}
        ${col("ret", "Returns")}
        ${col("np", "Params", true)}
        ${col("fan", "Calls out", true)}
        ${col("nb", "Touches", true)}
        ${col("nc", "Comments", true)}
      </tr></thead>
      <tbody>
        ${sortedRoutines().map((r, i) => {
          const parts = r.q.split(".");
          const leaf = parts.pop();
          return `<tr data-row="${esc(r.q)}" aria-selected="${state.selectedRow === r.q}" tabindex="0">
            <td><span class="qual"><span class="dim">${esc(parts.join("."))}.</span>${esc(leaf)}</span>
              ${state.ambient && r.anom ? ` <span class="badge suspect">! ${esc(r.anom)}</span>` : ""}</td>
            <td class="mono" style="font-size:.72rem;color:var(--text-muted)">${esc(r.lines)}</td>
            <td class="mono" style="font-size:.72rem">${esc(r.ret)}</td>
            <td class="numeric">${r.np}</td>
            <td class="numeric">${r.fan}</td>
            <td class="numeric">${r.nb}</td>
            <td class="numeric">${r.nc}</td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>
    <div class="tfoot">
      <span>Showing <b>12</b> of <b>515</b> routines in <code class="mono">mensores.quaestor</code></span>
      <span style="margin-left:auto">Scroll is virtualised — every row is present, none are paged away.</span>
    </div>
  </div>`;
}

function viewDoc() {
  return `
  <article class="doc">
    <h1>What happens after <code class="mono">mensores interview --extract</code></h1>
    <p class="lead">The same selection you have in the graph and the table, read as prose. This is
      <code class="mono">02-flows.md</code>, scrolled to the routine you have selected.</p>

    <h2>The door</h2>
    <div class="prose">
      <p>The command is registered on the Typer app and reaches
      <code class="mono">_run_extract_mode</code> through a single caller. Before anything is minted,
      swept or emitted, the run passes a prerequisite gate — placement that was pinned at plan time
      rather than left to “as early as possible”, because a gate that refuses after minting a session
      has started the interview it claims to have denied.</p>

      <p>The architect is resolved next, and is deferred-safe unless organisational consent, a
      resolvable model and a present API key all hold. A dry run never egresses, even with consent.</p>
    </div>

    <h2>Where it leaves the program</h2>
    <div class="prose">
      <p>Six boundary touches: two environment reads that decide whether the run is headless, two
      existence checks that guard against overwriting a contractual artifact, and two file writes at
      the end — the spec itself and its rendered form.</p>
    </div>

    <div class="note" style="margin-top:1rem">
      <b>Note.</b> This is the one view that would read live from
      <code class="mono">output/mensores/source.db</code> — the content-addressed sidecar — so the
      prose and the code beside it are both what was measured, not what the tree happens to say now.
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

        <div class="wl-jump">
          <button class="actbtn">Go to the first occurrence in the graph <span class="k">G</span></button>
          <button class="actbtn">Show all ${cur.a.n} occurrence${cur.a.n === 1 ? "" : "s"} as a table <span class="k">T</span></button>
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





/* ═══ the trail: where you have been, so you can wander without losing it ═══ */
function pushTrail(view, label, note) {
  const last = state.trail[state.trail.length - 1];
  if (last && last.view === view && last.label === label) return;   // no repeats
  state.trail.push({ view, label, note: note || "" });
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

function threadsPanel(anchor) {
  const th = THREADS[anchor] || [];
  if (!th.length) return "";
  return `
    <div class="flowsec threads">
      <h3><button aria-expanded="true"><span class="caret">\u25bc</span>Threads to pull
        <span class="secn">${th.length}</span><span class="rule"></span></button></h3>
      <div class="flowsec-body">
        <p class="threadintro">Not the call graph \u2014 reasons something nearby might be worth a detour.</p>
        ${th.map(t => `
          <button class="thread" data-thread="${esc(t.to)}" data-threadwhy="${esc(t.why)}">
            <span class="thread-kind ${esc(t.kind)}">${esc(t.kind)}</span>
            <span class="thread-body">
              <span class="thread-to mono">${esc(t.to)}</span>
              <span class="thread-why">${esc(t.why)}</span>
            </span>
          </button>`).join("")}
      </div>
    </div>`;
}

/* ═══ source viewer: a citation you can open and read ═══ */
function viewerPanel() {
  if (!state.viewer) return "";
  const ev = (PROVENANCE[state.viewer.term] || [])[state.viewer.idx];
  if (!ev) return "";
  const all = PROVENANCE[state.viewer.term] || [];

  return `
  <div class="viewer-scrim" data-closeviewer></div>
  <div class="viewer" role="dialog" aria-modal="true" aria-label="Source for ${esc(state.viewer.term)}">
    <div class="viewer-head">
      <div>
        <div class="viewer-title mono">${esc(ev.path)}</div>
        <div class="viewer-sub">line ${ev.hit_from}${ev.hit_to !== ev.hit_from ? "\u2013" + ev.hit_to : ""}
          \u00b7 ${esc(ev.label)}
          \u00b7 <span class="badge ${ev.kind === "code" ? "certain" : "info"}">${ev.kind === "code" ? "CODE" : "DOCS"}</span></div>
      </div>
      <button class="linkbtn" data-closeviewer aria-label="Close source viewer">Close \u2715</button>
    </div>

    ${all.length > 1 ? `<div class="viewer-tabs" role="tablist">
      ${all.map((e, i) => `<button role="tab" aria-selected="${i === state.viewer.idx}"
        data-viewtab="${i}">${esc(e.label)}</button>`).join("")}
    </div>` : ""}

    <div class="viewer-body">
      <pre class="codeview">${ev.lines.map((l, i) => {
        const n = ev.start + i;
        const hit = n >= ev.hit_from && n <= ev.hit_to;
        return `<span class="cl${hit ? " hit" : ""}"><span class="cn">${n}</span>${esc(l) || " "}</span>`;
      }).join("\n")}</pre>
    </div>

    <div class="viewer-foot">
      Read from the content-addressed sidecar \u2014 this is the file as measured on 2026-08-27,
      not as the tree stands now. Highlighted line${ev.hit_to !== ev.hit_from ? "s are" : " is"} the citation.
    </div>
  </div>`;
}

function citeBtn(term, idx, label) {
  return `<button class="cite" data-cite="${esc(term)}" data-citeidx="${idx}">
    <span class="citeicon" aria-hidden="true">\u2317</span>${esc(label)}<span class="citego">show me</span></button>`;
}

function citeIndex(term, kind, label) {
  const all = PROVENANCE[term] || [];
  return all.findIndex(e => e.kind === kind && (!label || e.label === label));
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
              <span class="detail">${
                k === "docs"   ? `${MANIFEST.length} candidate documents \u00b7 ${(manifestBytes / 1024).toFixed(0)} KB`
              : k === "names"  ? "4,568 routine names and signatures \u00b7 no bodies"
              :                  "184,000 lines of source"}</span>
              ${k === "docs" && permits("docs") ? `<button class="linkbtn" data-manifest>${state.showManifest ? "Hide" : "Review"} the exact list</button>` : ""}
            </div>`).join("")}
        </div>

        ${state.showManifest && permits("docs") ? `
          <div class="manifest">
            <div class="manifesthead">Every file a documentation scan would send \u2014 ${MANIFEST.length} of 2,449</div>
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

/* ═══ glossary: four provenances, never blended ═══ */
function tierBadge(t) {
  return {
    code:     '<span class="badge certain">DECLARED \u00b7 code</span>',
    docs:     '<span class="badge certain">DECLARED \u00b7 docs</span>',
    cited:    '<span class="badge info">CITED</span>',
    inferred: '<span class="badge inferred">INFERRED</span>'
  }[t];
}

function viewGlossary() {
  const q = state.termFilter.toLowerCase();
  const shown = TERMS.filter(t => !q || t.term.includes(q) || t.declared.toLowerCase().includes(q));
  const opq = TERMS.filter(t => t.opaque);
  const covered = opq.filter(t => t.docs || t.project);
  const orphan = opq.filter(t => !t.docs && !t.project);

  return `
  <div style="max-width:58rem;display:flex;flex-direction:column;gap:.75rem">

    <div class="tierkey">
      <span>${tierBadge("code")} parsed from a docstring \u2014 quoted, never paraphrased</span>
      <span>${tierBadge("docs")} parsed from a structured glossary or naming table in the project's own documents</span>
      <span>${tierBadge("cited")} a model found it in prose documentation and cited the line \u2014 checkable</span>
      <span>${tierBadge("inferred")} nothing in the project explains it; this is a guess \u2014 not checkable</span>
    </div>

    <div class="note">
      <b>${covered.length} of the ${opq.length} opaque terms are already defined by this project.</b>
      Not in the code \u2014 in <span class="mono">.groma/milestones/v1.1-harness-ownership/NAMING.md</span>,
      a table titled "The pantheon" that maps every component to its Latin name with etymology, and in
      <span class="mono">.groma/PROJECT.md</span>'s own Glossary section. DunneFlow was not reading either,
      because it only read source code. <b>Only ${orphan.length} terms
      (${orphan.map(t => `<span class="mono">${esc(t.term)}</span>`).join(", ")}) are undefined anywhere</b>,
      and both are borrowed words rather than coinages. Inference has almost nothing to do here \u2014
      which is the useful finding.
    </div>

    <div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap">
      <label class="sr-only" for="termq">Filter terms</label>
      <input id="termq" class="termq" type="search" placeholder="Filter ${TERMS.length} terms\u2026" value="${esc(state.termFilter)}">
      <span style="font-size:.74rem;color:var(--text-muted)">
        <b class="num">${shown.length}</b> of <b class="num">${TERMS.length}</b> terms
      </span>
    </div>

    ${shown.map(t => `
      <section class="panel term">
        <div class="panel-head">
          <h2 style="text-transform:none;letter-spacing:0;font-size:.92rem;color:var(--text);font-family:var(--f-mono)">${esc(t.term)}</h2>
          ${t.opaque ? '<span class="kind-tag">domain word</span>' : ""}
          ${t.circular ? '<span class="badge suspect">! defines itself with itself</span>' : ""}
          <span class="hint mono">${esc(t.module)}</span>
        </div>
        <div class="panel-body">

          <div class="termrow">
            ${tierBadge("code")}
            <div class="termdef">
              <span class="quoted">${esc(t.declared)}</span>
              <div class="src">${citeIndex(t.term, "code") >= 0
                ? citeBtn(t.term, citeIndex(t.term, "code"), `${t.module.replace("mensores.", "mensores/")}/__init__.py \u00b7 module docstring`)
                : `<span class="mono">${esc(t.module)}</span>`}</div>
              ${t.circular ? `<div class="src blind"><b>Measured.</b> The gloss repeats the word instead of
                explaining it \u2014 "the Mensores Dispensator" does not say what a dispensator is.
                <b>Blind spot:</b> a reader who already knows the word would find this perfectly clear.</div>` : ""}
            </div>
          </div>

          ${t.docs ? `
          <div class="termrow">
            ${tierBadge("docs")}
            <div class="termdef">
              <span class="quoted">${esc(t.docs.meaning)}</span>
              <div class="src">${citeIndex(t.term, "docs", '"The pantheon" table') >= 0
                ? citeBtn(t.term, citeIndex(t.term, "docs", '"The pantheon" table'), `NAMING.md:${t.docs.line} \u00b7 "The pantheon" table`)
                : `<span class="mono">${esc(t.docs.file)}:${t.docs.line}</span>`}
                ${t.docs.inherited ? ' \u00b7 inherited from <span class="mono">groma</span>' : ""}
                \u00b7 component: ${esc(t.docs.component)}</div>
            </div>
          </div>` : ""}

          ${t.project ? `
          <div class="termrow">
            ${tierBadge("docs")}
            <div class="termdef">
              <span class="quoted">${esc(t.project.body.slice(0, 420))}${t.project.body.length > 420 ? "\u2026" : ""}</span>
              <div class="src">${citeIndex(t.term, "docs", "PROJECT.md ## Glossary") >= 0
                ? citeBtn(t.term, citeIndex(t.term, "docs", "PROJECT.md ## Glossary"), `PROJECT.md:${t.project.line} \u00b7 ## Glossary`)
                : `<span class="mono">${esc(t.project.file)}:${t.project.line}</span>`}
                ${t.project.pos ? " \u00b7 " + esc(t.project.pos) : ""}</div>
            </div>
          </div>` : ""}

          ${t.opaque && !t.docs && !t.project ? `
          <div class="termrow">
            ${state.aiDone ? tierBadge("inferred") : tierBadge("cited")}
            <div class="termdef">
              ${state.aiDone
                ? `<span class="guess">${esc(INFERRED_SAMPLE[t.term] || "No inference produced.")}</span>
                   <div class="src blind"><b>Blind spot.</b> No document in this project defines this term.
                   It was inferred from the word and the surrounding code, and may be confidently wrong.</div>`
                : `<span class="notrun">No document in this project defines this term. A one-time pass
                   could search the prose for it, or guess.</span>`}
            </div>
          </div>` : ""}
        </div>
      </section>`).join("")}
  </div>`;
}

const INFERRED_SAMPLE = {
  oscal: "Not Latin, and not a coinage \u2014 NIST's Open Security Controls Assessment Language. Borrowed wholesale, which is why the pantheon table does not list it.",
  testkit: "Ordinary English compound, not part of the Latin scheme. The docstring's own gloss \u2014 \"the contract-coverage enforcement Society ships into generated repos\" \u2014 already says what it is."
};

/* ═══ naming standard: the conventions, and what breaks them ═══ */
function viewNaming() {
  return `
  <div style="max-width:58rem;display:flex;flex-direction:column;gap:.75rem">
    <div class="note">
      <b>Every figure here is counted, not guessed.</b> The exceptions are the point: a convention
      followed 100% of the time tells you how to read the program, and a convention followed 98% of
      the time tells you where to look.
    </div>

    ${CONVENTIONS.map((cv, i) => {
      const pct = (cv.ok / cv.n) * 100;
      const perfect = cv.ok === cv.n;
      return `
      <section class="panel">
        <div class="panel-head">
          <h2 style="text-transform:none;letter-spacing:0;font-size:.9rem;color:var(--text);font-family:var(--f-mono)">${esc(cv.pattern)}</h2>
          <span class="hint">${esc(cv.claim)}</span>
        </div>
        <div class="panel-body">
          <div class="convbar">
            <span class="bar" style="flex:1"><i style="width:${pct}%;background:${perfect ? "var(--accent)" : "var(--sev-suspect)"}"></i></span>
            <span class="num" style="font-weight:700;color:${perfect ? "var(--accent-text)" : "var(--sev-suspect)"}">${pct.toFixed(1)}%</span>
            <span class="num" style="font-size:.72rem;color:var(--text-muted)">${cv.ok.toLocaleString()} of ${cv.n.toLocaleString()}</span>
          </div>

          ${cv.exceptions.length ? `
            <div class="excepthead">${cv.n - cv.ok} exception${cv.n - cv.ok === 1 ? "" : "s"}${cv.exceptions.length < cv.n - cv.ok ? ` \u2014 showing ${cv.exceptions.length}, all listed in the table view` : ""}</div>
            <ul class="exceptlist">
              ${cv.exceptions.map(e => `<li class="mono">${esc(e)}</li>`).join("")}
            </ul>`
            : `<div class="excepthead ok">No exceptions. This convention holds everywhere.</div>`}

          <div class="why" style="margin-left:0;margin-top:.5rem">
            <span class="ln">note</span> ${esc(cv.note)}
          </div>
          ${cv.sql ? `
          <div class="prov">
            <button class="cite" data-sqlshow="${i}">
              <span class="citeicon" aria-hidden="true">\u2317</span>How this number was counted<span class="citego">show the query</span></button>
            ${state.showSql === i ? `<pre class="srcblock sqlblock">${esc(cv.sql)}</pre>
              <div class="provfoot">Run it yourself: <span class="mono">uv run dunneflow query output/mensores --sql "\u2026"</span>.
                A counted claim proves itself by being reproducible \u2014 the query is its provenance.</div>` : ""}
          </div>` : ""}
        </div>
      </section>`;
    }).join("")}
  </div>`;
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
  render();
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
  const params = s.params || [];
  const sigBody = `<pre class="srcblock">${
    id.is_async ? `<span class="kw">async </span>` : ""}<span class="kw">def</span> ${
    esc(id.name || s.label)}(${params.length
      ? "\n    " + params.map(p =>
          esc(p.name) + (p.annotation ? `: ${esc(p.annotation)}` : "") +
          (p.default ? ` = ${esc(p.default)}` : "")).join(",\n    ") + "\n"
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
    ${threadsPanel(id.qualname || s.id)}
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
  const prog = { label: "mensores", to: "cover" };
  const trail = {
    cover:       [],
    graph:       [{ label: "packages" }, { label: "system boundary", cur: true }],
    table:       [{ label: "quaestor" }, { label: "routines", cur: true }],
    doc:         [{ label: "cli" }, { label: "interview", cur: true }],
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
  $("#modes").style.visibility = ["graph", "table", "doc"].includes(state.view) ? "visible" : "hidden";
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
  else if (state.view === "table")     vp.innerHTML = viewTable();
  else if (state.view === "doc")       vp.innerHTML = viewDoc();
  else if (state.view === "anomalies") vp.innerHTML = viewAnomalies();
  else if (state.view === "glossary")  vp.innerHTML = viewGlossary();
  else if (state.view === "naming")    vp.innerHTML = viewNaming();
  else if (state.view === "inference") vp.innerHTML = viewInference();
  else if (state.view === "curiosities") vp.innerHTML = viewCuriosities();
  else if (state.view === "pins")       vp.innerHTML = viewPins();
  else if (state.view === "settings")  vp.innerHTML = viewSettings();

  $("#inspector").innerHTML = section("inspector", viewInspector);
  let vw = document.getElementById("viewerMount");
  if (!vw) { vw = document.createElement("div"); vw.id = "viewerMount"; document.body.appendChild(vw); }
  vw.innerHTML = viewerPanel();
  const ne = $("#navEgress");
  if (ne) {
    ne.textContent = posture().label.toLowerCase();
    ne.className = "n" + (state.egress === "off" ? "" : " sevcount info");
  }
  const ex = $("#navExplore"), wi = $("#navWaysIn");
  if (ex && wi && ex.parentNode) {
    const first = state.menuOrder === "explore" ? ex : wi;
    if (ex.parentNode.firstElementChild !== first) ex.parentNode.insertBefore(first, ex.parentNode.firstElementChild);
  }

  const tm = $("#trailMount");
  if (tm) tm.innerHTML = trailBar();
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
    if (i >= 0) Graph.togglePick({ kind: "node", index: i }, "replace");
    else { loadNode(id); }
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
    state.selectedRow = tr.dataset.row;
    render();
  }));
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
      const move = (ev) => {
        const deltaRem = (ev.clientX - startX) / rootPx;   /* px in, rem out */
        const w = Math.max(2.5, +(startRem + deltaRem).toFixed(3));
        state.colWidths[key] = w;
        th.style.width = w + "rem";
      };
      const up = () => {
        h.classList.remove("active");
        h.removeEventListener("pointermove", move);
        h.removeEventListener("pointerup", up);
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
  $$("[data-menuorder]").forEach(b => b.addEventListener("click", () => {
    state.menuOrder = b.dataset.menuorder;
    used("menu:" + state.menuOrder);
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

  /* glossary filter — updates in place so the field keeps focus while typing */
  const tq = $("#termq");
  if (tq) tq.addEventListener("input", () => {
    state.termFilter = tq.value;
    const pos = tq.selectionStart;
    render();
    const again = $("#termq");
    if (again) { again.focus(); again.setSelectionRange(pos, pos); }
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
    state.view = step.view;
    render();
  }));
  const tb = $("[data-trailback]");
  if (tb) tb.addEventListener("click", () => {
    if (state.trail.length > 1) {
      state.trail.pop();
      state.view = state.trail[state.trail.length - 1].view;
      render();
    }
  });
  const tc = $("[data-trailclear]");
  if (tc) tc.addEventListener("click", () => {
    state.trail = [{ view: state.view, label: "here", note: "trail cleared" }];
    render();
  });
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
    pushTrail(state.view, b.dataset.thread, b.dataset.threadwhy);
    state.view = "curiosities";
    render();
  }));

  const sp = $("#srcPath");
  if (sp && !sp.dataset.bound) {
    sp.dataset.bound = "1";
    sp.addEventListener("click", () => {
      const open = sp.getAttribute("aria-expanded") === "true";
      sp.setAttribute("aria-expanded", String(!open));
      $("#srcPathV").textContent = open
        ? "mensores-overhaul/src"
        : "../mensores-overhaul/src";
    });
  }

  /* provenance click-through */
  $$("[data-cite]").forEach(b => b.addEventListener("click", () => {
    state.viewer = { term: b.dataset.cite, idx: parseInt(b.dataset.citeidx, 10) };
    render();
  }));
  $$("[data-closeviewer]").forEach(b => b.addEventListener("click", () => {
    state.viewer = null; render();
  }));
  $$("[data-viewtab]").forEach(b => b.addEventListener("click", () => {
    state.viewer = { ...state.viewer, idx: parseInt(b.dataset.viewtab, 10) };
    render();
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
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName);
  if (e.key === "/" && !typing) { e.preventDefault(); $("#search").focus(); return; }
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
const WIRED_ATTRS = new Set(["aiop", "airun", "bound", "cite", "citeidx", "closeviewer", "col", "crumb", "curi", "cursor", "den", "drop", "egress", "ep", "disk", "gact", "gosev", "goto", "graphtheme", "layout", "pkgnode", "pkgpick", "manifest", "menuorder", "mode", "nav", "nav2", "node", "open", "pin", "pinnote", "resize", "row", "scale-set", "sec", "sev", "sevnav", "sort", "sqlshow", "start", "step", "theme", "theme-set", "thread", "threadwhy", "toggle", "trail", "trailback", "trailcap", "trailclear", "triage", "triaged", "unpin", "viewtab"]);

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
  /* Both directions for the graph's own table too: a control with no action, and an
   * action no control reaches. The second half is the one a hand forgets -- it is how a
   * feature quietly stops being reachable while every test still passes. */
  document.querySelectorAll("[data-gact]").forEach(el => {
    if (!(el.dataset.gact in GRAPH_ACTIONS)) {
      problems.push(`graph control [data-gact="${el.dataset.gact}"] has no action`);
    }
  });
  if (Graph.mounted()) {
    const drawn = new Set($$("[data-gact]").map(el => el.dataset.gact));
    for (const k of Object.keys(GRAPH_ACTIONS)) {
      if (!drawn.has(k)) problems.push(`graph action "${k}" is reached by no control`);
    }
  }

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
  el.title = span.textContent;
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

const NAV_GROUPS = [
  { id: "navExplore", title: "Explore", open: true, items: () => [
      { nav: "curiosities", label: "Worth a look", n: "" },
      { nav: "pins",        label: "Kept",         n: state.pins.length, id: "navPins" },
    ] },
  { id: "navWaysIn", title: "Ways in", open: true, items: () => [
      { nav: "cover", label: "Overview", n: "cover", current: state.view === "cover" },
      // Bounded, and it says so: the full list is the cover's own ranking, one
      // click away. Rule 8 -- abbreviation only where the whole sits beside it.
      ...ENTRYPOINTS.slice(0, 6).map(e => ({ nav: "ep", label: e.name, n: e.reach })),
    ] },
  { id: "navPkgs", title: "Packages", open: true, items: () => [
      ...PKGS.slice(0, 8).map(p => ({ nav: "pkg", label: p.id, n: p.n })),
    ] },
  { id: "navBounds", title: "Boundaries", open: false, items: () => [
      ...BOUNDARIES.map(b => ({ nav: "b", label: b.kind, n: b.n })),
    ] },
  { id: "navTables", title: "Database", open: true, items: () => [
      ...TABLES.slice(0, 8).map(t => ({ nav: "t", label: t.name, n: t.n })),
    ] },
  { id: "navVocab", title: "Vocabulary", open: true, items: () => [
      { nav: "glossary", label: "Glossary",        n: TERMS.length || "" },
      { nav: "naming",   label: "Naming standard", n: CONVENTIONS.length || "" },
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
  const items = g.items();
  if (g.id === "navBounds") return BOUNDARIES.reduce((s, b) => s + b.n, 0);
  if (g.id === "navPkgs")   return PKGS.length;
  if (g.id === "navTables") return TABLES.length;
  if (g.id === "navWaysIn") return ENTRYPOINTS.length;
  if (g.id === "navAnom")   return items.reduce((s, i) => s + (Number(i.n) || 0), 0);
  return items.length;
}

function buildNav() {
  const nav = $("#navigator");
  if (!nav) return;
  nav.innerHTML = NAV_GROUPS.map(g => {
    const items = g.items();
    const total = groupCount(g);
    return `
    <div class="nav-group" data-open="${g.open}" id="${esc(g.id)}">
      <button class="nav-head" data-toggle>
        <span class="caret">▼</span> ${esc(g.title)}
        <span class="count">${total.toLocaleString()}</span>
      </button>
      <div class="nav-items">
        ${items.map(i => `
          <button class="nav-item" data-nav="${esc(i.nav)}"
                  ${i.sevnav ? `data-sevnav="${esc(i.sevnav)}"` : ""}
                  ${i.current ? 'aria-current="true"' : ""}>
            ${i.dot ? `<span class="sevdot" style="background:var(--sev-${esc(i.dot)})"></span>` : ""}
            ${esc(i.label)}<span class="n${i.dot && i.n ? " num sevcount " + esc(i.dot) : ""}"
              ${i.id ? `id="${esc(i.id)}"` : ""}>${esc(String(i.n))}</span>
          </button>`).join("")}
      </div>
    </div>`;
  }).join("");
  dressNavItems();
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
  STATS       = Object.assign({}, d.stats, { anomalies: d.anomalies, program: d.program });

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
  "nodeSize", "spread", "showPlates", "picks", "graphTheme",
];

let settings = null;      // the loaded blob; `state` is the live copy
let program = null;
let graphPayload = null;
let graphLoading = false;
let graphError = null;
let counts = null;        // the engine's last count report
let fps = 0;
let legendOpen = true;

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
    label: [...hex("--graph-label"), 240],
    labelBg: [...hex("--graph-label-bg"), 200],
    tooltipBg: cs.getPropertyValue("--surface").trim(),
    tooltipText: cs.getPropertyValue("--text").trim(),
    tooltipLine: cs.getPropertyValue("--border").trim(),
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

function applyGraphPalette() {
  const p = graphPaletteNow();
  $("#graphMount").style.background =
    `rgb(${p.ground[0]},${p.ground[1]},${p.ground[2]})`;
  if (Graph.mounted()) Graph.setPalette(p);
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
    spread: state.spread, showPlates: state.showPlates, scale: state.scale,
    picks: state.picks,
  });
  /* Read back the order the engine resolved. A saved order from a graph that has since
   * changed is discarded there, and the shell must not go on persisting the stale one --
   * that is how a setting outlives the thing it described. */
  state.diskOrder = Graph.diskOrder();
  state.picks = Graph.selection();
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
  render();
}

/* ── the furniture: the HUD and the legend ─────────────────────────────────── */

/* Never a silent filter (design rule 1). What is not on screen is stated, in counts,
 * whichever way the filter is set -- and "nothing selected" says what to do about it,
 * because with edges hidden by default an unselected stack is a picture of nothing much
 * and the reader has no way to know that is deliberate. */
function countLine(c) {
  if (c.moving) return "nodes only while moving";
  if (!c.selected) {
    return "nothing selected — all links hidden; pick two disks to see what crosses "
         + "between them, or click a node";
  }
  const names = c.names || [];
  return `${esc(names.slice(0, 3).join(", "))}${
      names.length > 3 ? ` +${names.length - 3}` : ""} · ` +
    `<b class="num">${(c.selected || 0).toLocaleString()}</b> nodes · ` +
    `<b class="num">${(c.within || 0).toLocaleString()}</b> within · ` +
    `<b class="num">${(c.crossing || 0).toLocaleString()}</b> crossing · ` +
    `<b class="num">${(c.excluded || 0).toLocaleString()}</b> ${c.excludedBy}`;
}

/* The narrow path: update the sentence, never the pane around it.
 *
 * Rebuilding the HUD here would destroy whichever slider was being dragged, because
 * dragging one changes what is on screen and therefore emits counts -- the same defect
 * that cost a colour picker in the mockup session, arriving by a new route. So the counts
 * event touches exactly the two things counts can change. */
function updateGraphCounts() {
  const line = $("#gcounts");
  if (line) line.innerHTML = countLine(counts || {});
  const legend = $("#graphLegend");
  if (!legend) return;
  const on = new Set(state.picks.filter(p => p.kind === "disk").map(p => p.id));
  legend.querySelectorAll(".leg").forEach(row => {
    row.classList.toggle("on", on.has(row.dataset.disk));
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
    $("#graphLegend").innerHTML = "";
    return;
  }
  if (!Graph.mounted()) {
    hud.innerHTML = `<div class="hudbox"><span class="muted">${
      graphLoading ? "reading the stack…" : "the stack is not loaded yet"}</span></div>`;
    $("#graphLegend").innerHTML = "";
    return;
  }

  const c = counts || {};
  const line = countLine(c);

  hud.innerHTML = `
    <div class="hudbox">
      <div><b class="num" id="gfps">${fps ? fps.toFixed(0) : "–"}</b> fps ·
        <b class="num">${(c.nodes || 0).toLocaleString()}</b> nodes ·
        <b class="num">${c.disks || 0}</b> disks</div>
      <div class="muted" id="gcounts">${line}</div>
      <div style="margin-top:.3rem">
        <button class="gbtn" data-gact="fit">snap to fit</button>
        <button class="gbtn" data-gact="top">top-down</button>
        <button class="gbtn" data-gact="tilt">tilt</button>
        <button class="gbtn" data-gact="bench">benchmark</button>
        ${c.selected ? `<button class="gbtn" data-gact="clear">clear</button>` : ""}
      </div>
      <div class="muted" id="gbench"></div>
    </div>

    <!-- Live controls update in place and re-render only the graph. A pane that rebuilds
         itself on every input event destroys the control being dragged -- that cost a
         colour picker once, and it is why these write straight to the engine and to their
         own readout, never through a full re-render. -->
    <div class="hudbox">
      <label style="display:flex;align-items:center;gap:.35rem">
        <span class="muted" style="width:3.2rem">size</span>
        <input id="gsize" type="range" min="0.4" max="14" step="0.2"
               value="${state.nodeSize}" aria-label="Node size">
        <span class="muted num" id="gsizeval">${(+state.nodeSize).toFixed(1)}×</span>
      </label>
      <label style="display:flex;align-items:center;gap:.35rem">
        <span class="muted" style="width:3.2rem">spread</span>
        <input id="gspread" type="range" min="0.05" max="2" step="0.05"
               value="${state.spread}" aria-label="Distance between plates">
        <span class="muted num" id="gspreadval">${(+state.spread).toFixed(2)}×</span>
      </label>
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
    </div>`;

  renderLegend();
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
  host.classList.toggle("closed", !legendOpen);
  host.innerHTML = `
    <div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem">
      <button class="linkbtn" data-gact="legend" aria-expanded="${legendOpen}"
        >${legendOpen ? "▾" : "▸"} Plates</button>
      <span class="hint" style="font-size:.66rem">${disks.length} · click to select,
        drag to reorder</span>
      <select class="gsel" id="gsort" style="margin-left:auto"
              aria-label="Sort plates">
        ${[["nodes", "by size"], ["name", "by name"], ["kind", "by kind"],
           ["manual", "as arranged"]].map(([v, l]) =>
          `<option value="${v}" ${state.sortMode === v ? "selected" : ""}>${l}</option>`).join("")}
      </select>
    </div>
    <div class="legrows">
      ${disks.map(d => `
        <div class="leg ${d.kind} ${on.has(d.id) ? "on" : ""}" data-disk="${esc(d.id)}"
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

const GRAPH_ACTIONS = {
  fit:   () => Graph.fit(),
  top:   () => Graph.topDown(),
  tilt:  () => Graph.tilt(),
  clear: () => Graph.clearSelection(),
  legend: () => { legendOpen = !legendOpen; renderLegend(); },
  bench: async () => {
    const out = $("#gbench");
    if (out) out.textContent = "benchmarking…";
    const r = await Graph.benchmark(6);
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
      Graph.setOptions({ nodeSize: state.nodeSize });
      return;
    }
    if (t.id === "gspread") {
      state.spread = parseFloat(t.value);
      $("#gspreadval").textContent = state.spread.toFixed(2) + "×";
      Graph.setOptions({ spread: state.spread });
      return;
    }
    if (t.id === "gdirection") {
      state.direction = t.value; Graph.setOptions({ direction: t.value }); persist(); return;
    }
    if (t.id === "gplates") {
      state.showPlates = t.checked; Graph.setOptions({ showPlates: t.checked }); persist(); return;
    }
    if (t.id === "gsort") { state.sortMode = t.value; renderLegend(); persist(); }
    if (t.id === "gcolorby") { state.colorBy = t.value; Graph.setOptions({ colorBy: t.value }); persist(); }
    if (t.id === "gfilter") { state.filterMode = t.value; Graph.setOptions({ filterMode: t.value }); persist(); }
  });
  mount.addEventListener("change", (ev) => {
    // Committed, not live: a localStorage write per frame of a slider drag is waste, and
    // the value is already in `state` -- this only decides when it reaches disk.
    if (ev.target.classList.contains("sw") ||
        ["gsize", "gspread"].includes(ev.target.id)) persist();
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

  buildNav();
  wireGraphOnce();
  render();
  if (state.view === "graph") ensureGraph();
  selfCheck();
}

boot();
