/* What the reader has arranged, kept between visits.
 *
 * Per program, because a disk order and a set of colours worked out for one codebase mean
 * nothing in another. Versioned, because state written by a different build of the tool
 * must not be silently trusted -- that is rule 12 in another key: a cached thing is valid
 * only if the thing that wrote it is unchanged. A blob from an older version is discarded
 * whole rather than merged field by field, since a half-applied layout is harder to
 * recognise as wrong than a reset one.
 *
 * Storage can fail or be unavailable -- a private window, cleared site data, a browser
 * refusing it outright -- and none of that is worth breaking the map over. Every read and
 * write is guarded, and the page must work perfectly with nothing stored.
 */
'use strict';

/* Wrapped: a classic script's top-level declarations are globals, and a global here
 * collides with the same name imported in app.js. One exported name each, no leakage. */
(function () {

/* Bumped to 2 when the graph and the shell became one application. Before that there were
 * two stores for one reader -- the graph persisted its arrangement per program and the
 * shell persisted nothing at all, so a theme and a scale chosen deliberately were gone on
 * reload while a disk order nobody remembered setting survived. A blob written by v1 is
 * discarded whole rather than merged, which is the rule this file already stated: a
 * half-applied layout is harder to recognise as wrong than a reset one. */
const SETTINGS_VERSION = 3;

const DEFAULTS = {
  /* ── the graph ───────────────────────────────────────────────────────────── */
  diskOrder: null,        // null = the server's default order
  diskColors: {},         // diskId -> "#rrggbb"
  colorBy: 'kind',        // 'kind' | 'disk'
  sortMode: 'nodes',      // 'nodes' | 'name' | 'kind' | 'manual'
  filterMode: 'dim',      // 'dim' | 'hide'
  direction: 'both',      // 'callers' | 'callees' | 'both'
  nodeSize: 1,            // multiplier: 1 = the tiny dots the 60 fps figure was taken on
  /* Three independent axes. X and Y widen a plate, which is what separates nodes that
   * fuse into a mass at large sizes; Z is the gap between plates. All three moving
   * together is what zoom already does, so there is no linked control. Version 3: the
   * single `spread` these replace was Z alone. */
  spreadX: 1,
  spreadY: 1,
  spreadZ: 0.35,
  collapseUnused: false,  // close the gap a plate nothing is looking at leaves behind
  showPlates: false,
  edgesInMotion: true,    // links stay up while the camera turns -- see graph.js
  graphLayout: 'stack',   // 'stack' | 'packages' -- both built, use retires the loser
  graphTheme: 'follow',   // 'follow' | 'dark' -- design rule 2; see the Settings page
  picks: [],              // the selection itself, so a session survives a reload
  /* Which panes are open. Read by `applyPanels()` in the shell, which routes every one of
   * these through the `PANELS` table -- and a key here with no entry there is a named
   * error, because that is exactly how two of them died. For a long time the whole group
   * was persisted, named in the reset dialog, and read by nothing at all; then it was
   * wired up for `navigator` and `inspector` only, leaving `hud` and `controls` dead
   * inside a live key where the guard written for the first failure could not see them.
   *
   * `legend` needs no version bump: `loadSettings` merges a group member by member
   * precisely so that a group gaining one keeps its default for it. */
  panels: { navigator: true, inspector: true, legend: true, hud: true, controls: true },
  inspectorAuto: true,    // rail the inspector while nothing is selected
  /* Navigator width, in rem so the scale multiplier reaches it (design rule 3).
     Wider than the old fixed 14.5: it holds the routine list now, and a qualified
     name is the thing it has to be able to show. */
  navWidth: 21,

  /* ── the shell ───────────────────────────────────────────────────────────── */
  theme: 'system',        // 'system' | 'light' | 'dark'
  scale: 1,               // design rule 3: one multiplier over every dimension
  startup: 'cover',       // 'cover' | 'graph'
  mode: 'graph',          // which centre view: 'graph' | 'table' | 'doc'
  menuOrder: 'waysin',    // 'waysin' | 'explore' -- a genuine tie, so both exist
  trailShown: true,
  trailCap: 12,
  density: 'comfortable', // 'compact' | 'comfortable' | 'spacious'
  ambient: false,         // anomaly badges wherever a thing appears
  hideInferred: false,
  colWidths: { q: 26, why: 30, fan: 5 },   // the columns the routine list can fill
  // today; lines/returns/params/touches come back with an endpoint that serves them
  insp: { in: true, out: true, touches: true, gov: true, sig: false },
  sortKey: 'fan',
  sortAsc: false,

  /* ── egress, and what has been looked at ─────────────────────────────────── */
  egress: 'off',          // design rule 14: scoped, never a switch, off until turned on
  aiOps: { harvest: true },
  triage: {},             // finding id -> 'ack' | 'notbug' | 'tooldefect'
  pins: [],               // the shelf: what was found while looking for something else

  /* Counted locally, and only so a Setting can be retired on evidence rather than on
   * opinion. Starts at zero for every program: seeded with invented numbers it would
   * retire settings on fiction, which is worse than not counting at all. */
  usage: {},
};

function storageKey(program) {
  return `dunneflow:${program}:v${SETTINGS_VERSION}`;
}

/* A deep-enough clone that callers can mutate freely without writing through to the
 * defaults. Only plain data is stored, so this is sufficient and needs no library. */
function freshDefaults() {
  return JSON.parse(JSON.stringify(DEFAULTS));
}

function loadSettings(program) {
  const out = freshDefaults();
  let raw = null;
  try {
    raw = window.localStorage.getItem(storageKey(program));
  } catch {
    return out;                       // storage unavailable; defaults are a fine answer
  }
  if (!raw) return out;
  let saved;
  try {
    saved = JSON.parse(raw);
  } catch {
    return out;                       // unparseable is the same as absent
  }
  if (!saved || typeof saved !== 'object') return out;
  /* Merge only keys the current version knows about. A key the saved blob carries and
   * this build does not is dropped, and a key this build has and the blob lacks keeps its
   * default -- so adding a setting never has to migrate anything. */
  for (const k of Object.keys(out)) {
    if (!(k in saved)) continue;
    /* A nested group merges key by key rather than being replaced whole, so a group that
     * gains a member -- another inspector section, another column -- keeps its default for
     * the new one instead of losing it to an older blob. Arrays are values, not groups:
     * `picks` and `pins` are replaced entire. Named by shape rather than by a list, so
     * adding a group does not mean remembering to add it here too. */
    const isGroup = (v) => v && typeof v === 'object' && !Array.isArray(v);
    if (isGroup(out[k]) && isGroup(saved[k])) Object.assign(out[k], saved[k]);
    else out[k] = saved[k];
  }
  return out;
}

function saveSettings(program, settings) {
  try {
    window.localStorage.setItem(storageKey(program), JSON.stringify(settings));
    return true;
  } catch {
    return false;                     // quota, private mode; not worth interrupting for
  }
}

/* Reset says what it cleared. A reset that silently reverts everything leaves the reader
 * wondering which of the things they had arranged were theirs -- the same reason a
 * filtered view states what it removed. */
function resetSettings(program, current) {
  const base = freshDefaults();
  const cleared = [];
  const named = {
    diskOrder: 'disk order', diskColors: 'disk colours', colorBy: 'colour source',
    sortMode: 'sort', filterMode: 'filter mode', direction: 'direction',
    nodeSize: 'node size', picks: 'selection',
    spreadX: 'spread across', spreadY: 'spread deep', spreadZ: 'spread between plates',
    collapseUnused: 'collapsed plates',
    showPlates: 'disk plates', edgesInMotion: 'edges while moving',
    mode: 'centre view', panels: 'panel layout',
    inspectorAuto: 'auto-collapse the inspector', navWidth: 'navigator width',
    graphLayout: 'graph layout', graphTheme: 'graph theme',
    theme: 'theme', scale: 'interface scale', startup: 'startup screen',
    menuOrder: 'menu order', trailShown: 'the trail', trailCap: 'trail length',
    density: 'row density', ambient: 'ambient badges', hideInferred: 'inferred edges',
    colWidths: 'column widths', insp: 'inspector sections',
    sortKey: 'table sort', sortAsc: 'table sort direction',
    egress: 'egress posture', aiOps: 'model operations',
    triage: 'triage decisions', pins: 'the shelf', usage: 'usage counts',
  };
  /* Walk the *defaults*, not the label table. Walking the labels meant a setting added
   * without a label was cleared and never mentioned -- a reset that under-reports itself,
   * which is the same silent-omission defect as a filter that does not say what it
   * removed. An unnamed key falls back to its own name: ugly on screen is far better than
   * absent, and it is visible enough to get a label written for it. */
  for (const k of Object.keys(base)) {
    if (JSON.stringify(current[k]) !== JSON.stringify(base[k])) cleared.push(named[k] || k);
  }
  try {
    window.localStorage.removeItem(storageKey(program));
  } catch { /* nothing stored is the state we were after anyway */ }
  return { settings: base, cleared };
}

window.DunneFlowSettings = { DEFAULTS, SETTINGS_VERSION, loadSettings, saveSettings,
                             resetSettings, freshDefaults };
})();
