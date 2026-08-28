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

const SETTINGS_VERSION = 1;

const DEFAULTS = {
  diskOrder: null,        // null = the server's default order
  diskColors: {},         // diskId -> "#rrggbb"
  colorBy: 'kind',        // 'kind' | 'disk'
  sortMode: 'nodes',      // 'nodes' | 'name' | 'kind' | 'manual'
  filterMode: 'dim',      // 'dim' | 'hide'
  direction: 'both',      // 'callers' | 'callees' | 'both'
  nodeSize: 1,            // multiplier: 1 = the tiny dots the 60 fps figure was taken on
  spread: 0.35,
  showPlates: false,
  panels: { hud: true, disks: true, settings: false },
  picks: [],              // the selection itself, so a session survives a reload
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
    if (k === 'panels') Object.assign(out.panels, saved.panels || {});
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
    nodeSize: 'node size', spread: 'spread', picks: 'selection',
    showPlates: 'disk plates',
  };
  for (const [k, label] of Object.entries(named)) {
    if (JSON.stringify(current[k]) !== JSON.stringify(base[k])) cleared.push(label);
  }
  try {
    window.localStorage.removeItem(storageKey(program));
  } catch { /* nothing stored is the state we were after anyway */ }
  return { settings: base, cleared };
}

window.DunneFlowSettings = { DEFAULTS, SETTINGS_VERSION, loadSettings, saveSettings,
                             resetSettings, freshDefaults };
})();
