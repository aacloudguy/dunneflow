/* The 2.5D stack.
 *
 * Rules that came from use, each correcting something this file did wrong:
 *
 * 1. **The stack is an abstraction, not an object.** Plates are not drawn. Nodes are dots
 *    at heights that mean something; a disk is the idea grouping them, and an idea gets
 *    no surface.
 * 2. **Edges are shown on demand.** Thirteen thousand lines erase a program rather than
 *    describe it. Nothing but nodes until something is selected, then only the edges the
 *    selection touches, and only once the camera has stopped.
 * 3. **Only nodes while moving.**
 * 4. **The session accumulates.** Selection is a set of picks, not one value, because the
 *    way this is used is: take the busiest disk, add a few routines by hand, push the
 *    rest out of the way, then frame what is left.
 *
 * Performance comes from binary attributes: everything drawn is uploaded once as flat
 * typed arrays, so panning costs the same at fifteen thousand nodes as at five hundred.
 * The `data` wrappers are built once and dropped only when geometry changes -- building
 * them inside the per-frame layer function would re-upload half a megabyte every frame of
 * a drag, which is the exact cost the typed arrays exist to avoid. Both are load-bearing
 * for the 60 fps figure.
 */
'use strict';

const {
  Deck, OrbitView, ScatterplotLayer, LineLayer, TextLayer, PolygonLayer,
  COORDINATE_SYSTEM, CollisionFilterExtension,
} = deck;
/* Reached through their namespaces rather than destructured. These files are classic
 * scripts sharing one global scope, so `const loadSettings = ...` here would redeclare the
 * function of that name over there -- which is a SyntaxError that stops the page dead
 * before anything renders. */
const Settings = window.DunneFlowSettings;
const Shading = window.DunneFlowShading;

const CARTESIAN = COORDINATE_SYSTEM.CARTESIAN;

const KIND_COLOR = {
  ROUTINE:   [ 45, 212, 191],
  STRUCTURE: [147, 197, 253],
  CONSTANT:  [148, 163, 184],
  BOUNDARY:  [196, 181, 253],
  // A file the program names is not a boundary it touches: naming is a choice the authors
  // made, touching is something the code does. Different act, different colour.
  ARTEFACT:  [251, 191,  36],
};
const DISK_DEFAULT = { package: [ 45, 212, 191], external: [196, 181, 253] };
const SHADOW_COLOR = [ 88, 102, 122];
const DIM_COLOR    = [ 52,  64,  82];
const EDGE_COLOR   = [ 94, 234, 212, 150];
const CROSS_COLOR  = [125, 211, 252, 130];
const PLATE_FILL   = [ 22,  30,  41,  70];
const PLATE_LINE   = [ 44,  56,  73, 140];

const DOT_MIN = 1.4;
const DOT_MAX = 3.6;
/* Above this multiplier the dots are big enough that flatness would show, so the sphere
 * shading is switched on. Below it the extra fragment work buys nothing a reader can see.
 * It is a look, not a mode: the same layer, the same draw call, the same buffers. */
const SPHERE_FROM = 2.2;

const DISK_GAP = 190;
const NODE_LABEL_CAP = 250;
const NODE_LABEL_ZOOM = -1.2;
const SEARCH_CAP = 200;

const el = (id) => document.getElementById(id);

const state = {
  program: 'program', settings: null,
  data: null, prepared: null, deckgl: null,
  moving: false, stopTimer: 0,
  viewState: { target: [0, 0, 0], zoom: -4, rotationX: 35, rotationOrbit: 20,
               minZoom: -9, maxZoom: 8 },
  picks: [],              // [{kind:'disk', id} | {kind:'node', index}] -- ordered
  members: new Set(),
  hiddenLabels: 0,
  benching: false,
};

/* ------------------------------------------------------------------ helpers --- */

const hexToRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const rgbToHex = (c) => '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');

function persist() {
  const s = state.settings;
  s.picks = state.picks;
  Settings.saveSettings(state.program, s);
}

/* ---------------------------------------------------------------- geometry --- */

function bounds(d, subset = null) {
  let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  const visit = (i) => {
    for (let a = 0; a < 3; a++) {
      const v = d.positions[i * 3 + a];
      if (v < lo[a]) lo[a] = v;
      if (v > hi[a]) hi[a] = v;
    }
  };
  if (subset && subset.size) subset.forEach(visit);
  else for (let i = 0; i < d.n; i++) visit(i);
  if (!Number.isFinite(lo[0])) return { centre: [0, 0, 0], radius: 1, height: 1 };

  const centre = [0, 1, 2].map((a) => (lo[a] + hi[a]) / 2);
  let r = 0;
  const radial = (i) => {
    const h = Math.hypot(d.positions[i * 3] - centre[0], d.positions[i * 3 + 1] - centre[1]);
    if (h > r) r = h;
  };
  if (subset && subset.size) subset.forEach(radial);
  else for (let i = 0; i < d.n; i++) radial(i);
  return { centre, radius: r || 1, height: (hi[2] - lo[2]) || 1 };
}

/* Fit the bounding *cylinder*, at the tilt in force. A sphere is rotation-invariant and
 * therefore safe at every angle by being wrong at nearly all of them. Orbiting about Z
 * leaves the footprint circular, so tilt is the only term that changes the silhouette.
 *
 * With a selection it frames the selection: having pushed everything else out of the way,
 * the next thing anyone wants is to see what is left, filling the screen. */
function fitView(d, rotationX = state.viewState.rotationX, subset = null) {
  const b = bounds(d, subset ?? (state.members.size ? state.members : null));
  const t = (rotationX * Math.PI) / 180;
  const vertical = Math.abs(b.height * Math.cos(t)) + Math.abs(2 * b.radius * Math.sin(t));
  const wide = state.settings.panels.disks ? 0.60 : 0.90;   // room for the menu, if open
  const scale = Math.min(
    (window.innerWidth * wide) / (2 * b.radius),
    (window.innerHeight * 0.88) / vertical,
  );
  return { ...state.viewState, target: b.centre, rotationX, zoom: Math.log2(scale) };
}

/* ---------------------------------------------------------------- data prep --- */

function prepare(raw) {
  const n = raw.nodes.id.length;
  const positions = new Float32Array(n * 3);
  const colors = new Uint8Array(n * 4);
  const radii = new Float32Array(n);
  const degree = new Uint16Array(n);

  for (let i = 0; i < n; i++) {
    positions[i * 3]     = raw.nodes.x[i];
    positions[i * 3 + 1] = raw.nodes.y[i];
  }
  for (let i = 0; i < raw.edges.from.length; i++) {
    degree[raw.edges.from[i]]++;
    degree[raw.edges.to[i]]++;
  }

  const byDisk = new Map();
  for (let i = 0; i < n; i++) {
    const k = raw.nodes.disk[i];
    if (!byDisk.has(k)) byDisk.set(k, []);
    byDisk.get(k).push(i);
  }

  /* Inbound and outbound kept apart. "What calls this" is a different question from
   * "what does this call", and merging them makes the commonest question unanswerable. */
  const inbound = new Map(), outbound = new Map();
  for (let e = 0; e < raw.edges.from.length; e++) {
    const a = raw.edges.from[e], b = raw.edges.to[e];
    if (!outbound.has(a)) outbound.set(a, []);
    outbound.get(a).push(e);
    if (!inbound.has(b)) inbound.set(b, []);
    inbound.get(b).push(e);
  }

  const ranked = [];
  for (let i = 0; i < n; i++) if (raw.nodes.shadow[i] === 0) ranked.push(i);
  ranked.sort((a, b) => degree[b] - degree[a]);

  /* One lowercase haystack per node, over everything the payload carries: name, qualified
   * name, module, file, class, visibility, async, structure kind, boundary kind and
   * direction. Fifteen thousand strings is nothing to hold and makes "search by pretty
   * much any metadata" a substring test rather than a query language. */
  const haystack = new Array(n);
  for (let i = 0; i < n; i++) {
    const det = raw.nodes.detail[i] || {};
    const parts = [raw.nodes.label[i], raw.nodes.kind[i], raw.nodes.disk[i]];
    for (const [k, v] of Object.entries(det)) {
      if (v === null || v === undefined || v === '') continue;
      if (typeof v === 'boolean') { if (v) parts.push(k); continue; }
      parts.push(String(v));
    }
    haystack[i] = parts.join(' ').toLowerCase();
  }

  return { raw, n, positions, colors, radii, degree, byDisk, inbound, outbound,
           ranked, haystack, plates: [], diskZ: new Map() };
}

/* ------------------------------------------------------------------ layout --- */

/* Z is a **view property, not a fact**. The server supplies a default order; the reader
 * owns it from then on, which is what makes drag-and-drop reordering, the spread slider
 * and any future shuffling the same single operation. */
function applyLayout(d) {
  const order = state.settings.diskOrder;
  const spread = state.settings.spread;
  d.diskZ.clear();
  order.forEach((id, i) => d.diskZ.set(id, (order.length - i) * DISK_GAP * spread));

  for (let i = 0; i < d.n; i++) {
    d.positions[i * 3 + 2] = d.diskZ.get(d.raw.nodes.disk[i]) ?? 0;
  }
  for (const p of d.plates) {
    const z = d.diskZ.get(p.disk.id) ?? 0;
    for (const pt of p.polygon) pt[2] = z;
  }
  d.gpu = null;
  if (state.picks.length) buildSelectionGeometry(d);
}

function defaultOrder(raw) {
  // Packages above, externals below; within each, biggest nearest the middle.
  const pkgs = raw.disks.filter((d) => d.kind === 'package').sort((a, b) => b.nodes - a.nodes);
  const ext = raw.disks.filter((d) => d.kind === 'external').sort((a, b) => b.nodes - a.nodes);
  return [...pkgs, ...ext].map((d) => d.id);
}

function diskPlates(raw) {
  const R = 1060, SEG = 64;
  return raw.disks.map((disk) => {
    const ring = [];
    for (let k = 0; k <= SEG; k++) {
      const t = (k / SEG) * Math.PI * 2;
      ring.push([Math.cos(t) * R, Math.sin(t) * R, 0]);
    }
    return { polygon: ring, disk };
  });
}

/* ----------------------------------------------------------------- colours --- */

function diskColor(diskId) {
  const s = state.settings;
  if (s.diskColors[diskId]) return hexToRgb(s.diskColors[diskId]);
  const info = state.data.disks.find((d) => d.id === diskId);
  return DISK_DEFAULT[info?.kind ?? 'package'];
}

function paintNodes(d) {
  /* Colour carries one dimension at a time (design rule 4): either what a thing *is*, or
   * which disk it sits on -- never both at once. Selection state is carried by dimming,
   * a separate channel, so it never competes with either. */
  const byDisk = state.settings.colorBy === 'disk';
  const hide = state.settings.filterMode === 'hide';
  const sel = state.members.size ? state.members : null;
  const size = state.settings.nodeSize;

  for (let i = 0; i < d.n; i++) {
    const shadow = d.raw.nodes.shadow[i] === 1;
    const out = sel && !sel.has(i);
    let c, a;
    if (out && hide) {
      c = DIM_COLOR; a = 0;
    } else if (out) {
      c = DIM_COLOR; a = 110;
    } else {
      c = shadow ? SHADOW_COLOR
        : byDisk ? diskColor(d.raw.nodes.disk[i])
        : (KIND_COLOR[d.raw.nodes.kind[i]] || KIND_COLOR.ROUTINE);
      a = shadow ? 150 : 255;
    }
    d.colors[i * 4] = c[0]; d.colors[i * 4 + 1] = c[1];
    d.colors[i * 4 + 2] = c[2]; d.colors[i * 4 + 3] = a;
    const base = Math.min(DOT_MAX, DOT_MIN + Math.sqrt(d.degree[i]) * 0.28);
    d.radii[i] = (out && hide) ? 0 : base * size;
  }
  d.gpu = null;
}

/* --------------------------------------------------------------- selection --- */

function neighbours(d, index) {
  const dir = state.settings.direction;
  const edges = [];
  if (dir !== 'callees') for (const e of d.inbound.get(index) ?? []) edges.push(e);
  if (dir !== 'callers') for (const e of d.outbound.get(index) ?? []) edges.push(e);
  return edges;
}

function recomputeMembers(d) {
  const m = new Set();
  for (const pick of state.picks) {
    if (pick.kind === 'disk') {
      for (const i of d.byDisk.get(pick.id) ?? []) m.add(i);
    } else {
      m.add(pick.index);
      for (const e of neighbours(d, pick.index)) {
        m.add(d.raw.edges.from[e]);
        m.add(d.raw.edges.to[e]);
      }
    }
  }
  state.members = m;
}

function pickKey(p) { return p.kind === 'disk' ? `d:${p.id}` : `n:${p.index}`; }

function togglePick(d, pick, mode = 'replace') {
  const key = pickKey(pick);
  const at = state.picks.findIndex((p) => pickKey(p) === key);
  if (mode === 'replace') {
    state.picks = at >= 0 && state.picks.length === 1 ? [] : [pick];
  } else if (mode === 'remove' || at >= 0) {
    if (at >= 0) state.picks.splice(at, 1);
  } else {
    state.picks.push(pick);
  }
  afterSelectionChange(d);
}

function clearSelection(d) {
  state.picks = [];
  afterSelectionChange(d);
}

function afterSelectionChange(d) {
  recomputeMembers(d);
  buildSelectionGeometry(d);
  paintNodes(d);
  markMenu();
  markResults();
  persist();
}

function buildSelectionGeometry(d) {
  /* Only the edges the selection actually touches. A disk pick draws the edges *within*
   * it; a node pick draws the edges at that node in the chosen direction. Both are small
   * by construction, so this is rebuilt rather than cached -- a stale buffer costs more
   * than a rebuild. */
  if (!state.picks.length) { state.selGeom = null; return; }
  const wanted = new Set();
  for (const pick of state.picks) {
    if (pick.kind === 'node') {
      for (const e of neighbours(d, pick.index)) wanted.add(e);
    } else {
      const members = new Set(d.byDisk.get(pick.id) ?? []);
      for (let e = 0; e < d.raw.edges.from.length; e++) {
        if (members.has(d.raw.edges.from[e]) && members.has(d.raw.edges.to[e])) wanted.add(e);
      }
    }
  }
  const list = [...wanted];
  const src = new Float32Array(list.length * 3);
  const dst = new Float32Array(list.length * 3);
  const wid = new Float32Array(list.length);
  list.forEach((e, k) => {
    const a = d.raw.edges.from[e] * 3, b = d.raw.edges.to[e] * 3;
    src[k * 3] = d.positions[a]; src[k * 3 + 1] = d.positions[a + 1]; src[k * 3 + 2] = d.positions[a + 2];
    dst[k * 3] = d.positions[b]; dst[k * 3 + 1] = d.positions[b + 1]; dst[k * 3 + 2] = d.positions[b + 2];
    /* Width from the edge's own weight -- how many times the connection appears in the
     * source. This is the channel a profiler will later feed: importing a run becomes a
     * second source for something already drawn, not a change to how it is drawn. */
    wid[k] = 0.8 + Math.min(3.2, Math.log2(1 + (d.raw.edges.weight?.[e] ?? 1)) * 1.1);
  });

  const links = [];
  for (const i of state.members) {
    const r = d.raw.nodes.real[i];
    if (d.raw.nodes.shadow[i] === 1 && r >= 0) links.push([i, r]);
  }
  const tS = new Float32Array(links.length * 3), tD = new Float32Array(links.length * 3);
  links.forEach(([i, r], k) => {
    tS[k * 3] = d.positions[i * 3]; tS[k * 3 + 1] = d.positions[i * 3 + 1]; tS[k * 3 + 2] = d.positions[i * 3 + 2];
    tD[k * 3] = d.positions[r * 3]; tD[k * 3 + 1] = d.positions[r * 3 + 1]; tD[k * 3 + 2] = d.positions[r * 3 + 2];
  });

  state.selGeom = { count: list.length, src, dst, wid,
                    transCount: links.length, transSrc: tS, transDst: tD, gpu: null };
}

/* ------------------------------------------------------------------ layers --- */

function gpuData(d) {
  if (d.gpu) return d.gpu;
  d.gpu = { nodes: { length: d.n, attributes: {
    getPosition: { value: d.positions, size: 3 },
    getFillColor: { value: d.colors, size: 4, normalized: true },
    getRadius: { value: d.radii, size: 1 } } } };
  return d.gpu;
}

function selGpu(g) {
  if (g.gpu) return g.gpu;
  g.gpu = {
    edges: { length: g.count, attributes: {
      getSourcePosition: { value: g.src, size: 3 },
      getTargetPosition: { value: g.dst, size: 3 },
      getWidth: { value: g.wid, size: 1 } } },
    trans: { length: g.transCount, attributes: {
      getSourcePosition: { value: g.transSrc, size: 3 },
      getTargetPosition: { value: g.transDst, size: 3 } } },
  };
  return g.gpu;
}

function buildLayers(d) {
  const still = !state.moving;
  const s = state.settings;
  const layers = [];

  if (s.showPlates) {
    layers.push(new PolygonLayer({
      id: 'plates', data: d.plates, coordinateSystem: CARTESIAN,
      getPolygon: (p) => p.polygon, filled: true, stroked: true, extruded: false,
      getFillColor: PLATE_FILL, getLineColor: PLATE_LINE, getLineWidth: 1,
      lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: { getPolygon: [s.spread, s.diskOrder] },
    }));
  }

  if (state.selGeom && still && state.selGeom.count) {
    const g = selGpu(state.selGeom);
    layers.push(new LineLayer({
      id: 'sel-edges', coordinateSystem: CARTESIAN, data: g.edges,
      getColor: EDGE_COLOR, widthUnits: 'pixels', pickable: false,
    }));
    if (state.selGeom.transCount && s.showTranspositions) {
      layers.push(new LineLayer({
        id: 'sel-trans', coordinateSystem: CARTESIAN, data: g.trans,
        getColor: CROSS_COLOR, getWidth: 1.2, widthUnits: 'pixels', pickable: false,
      }));
    }
  }

  /* One layer, one draw call, whatever the size. Above `SPHERE_FROM` the shading
   * extension turns each disc into a ball -- same buffers, same call, a few extra
   * arithmetic operations per fragment. Real geometry would have cost fifteen thousand
   * mesh instances and a lighting pass for a difference nobody can see. */
  const spheres = s.nodeSize >= SPHERE_FROM;
  layers.push(new ScatterplotLayer({
    id: 'nodes', coordinateSystem: CARTESIAN, data: gpuData(d).nodes,
    radiusUnits: 'pixels', radiusMinPixels: 0, radiusMaxPixels: DOT_MAX * 2 * s.nodeSize,
    pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 255],
    extensions: spheres ? [new Shading.SphereShadingExtension()] : [],
    parameters: spheres ? { depthCompare: 'less-equal', depthWriteEnabled: true } : {},
  }));

  if (still && state.viewState.zoom >= NODE_LABEL_ZOOM) {
    const labels = pickLabels(d);
    if (labels.length) {
      layers.push(new TextLayer({
        id: 'node-labels', data: labels, coordinateSystem: CARTESIAN,
        getPosition: (o) => o.pos, getText: (o) => o.text,
        getSize: 11, sizeUnits: 'pixels', getColor: [230, 236, 243, 240],
        getTextAnchor: 'start', getAlignmentBaseline: 'center',
        getPixelOffset: [7, 0], background: true,
        getBackgroundColor: [11, 17, 25, 200], backgroundPadding: [3, 1],
        characterSet: 'auto', fontFamily: 'ui-monospace, Menlo, monospace',
        billboard: true, pickable: false,
        extensions: [new CollisionFilterExtension()],
        collisionEnabled: true, collisionTestProps: { sizeScale: 1.5 },
        getCollisionPriority: (o) => o.priority,
      }));
    }
  }
  return layers;
}

function pickLabels(d) {
  const pool = state.members.size
    ? [...state.members].sort((a, b) => d.degree[b] - d.degree[a])
    : d.ranked;
  const cap = Math.min(NODE_LABEL_CAP, pool.length);
  const out = [];
  for (let k = 0; k < cap; k++) {
    const i = pool[k];
    out.push({ pos: [d.positions[i * 3], d.positions[i * 3 + 1], d.positions[i * 3 + 2]],
               text: d.raw.nodes.label[i], priority: d.degree[i] });
  }
  state.hiddenLabels = pool.length - cap;
  return out;
}

/* --------------------------------------------------------------- disk menu --- */

function sortedDisks() {
  const s = state.settings;
  const byId = new Map(state.data.disks.map((d) => [d.id, d]));
  if (s.sortMode === 'manual') return s.diskOrder.map((id) => byId.get(id)).filter(Boolean);
  const list = state.data.disks.slice();
  if (s.sortMode === 'nodes') list.sort((a, b) => b.nodes - a.nodes);
  else if (s.sortMode === 'name') list.sort((a, b) => a.name.localeCompare(b.name));
  else list.sort((a, b) => (a.kind === b.kind ? b.nodes - a.nodes
                                             : a.kind === 'package' ? -1 : 1));
  return list;
}

function buildMenu() {
  /* Three columns, interleaved a fraction of a row apart so rows nest rather than share
   * baselines -- fifty-one entries in a third of the height one column needs. Each row is
   * a button, a swatch and a drag handle, because with edges hidden by default this menu
   * is the way into the graph rather than an index beside it. */
  const host = el('menu');
  host.innerHTML = '';
  for (const disk of sortedDisks()) {
    const row = document.createElement('div');
    row.className = `leg ${disk.kind}`;
    row.dataset.disk = disk.id;
    row.draggable = true;
    row.title = `${disk.nodes} nodes · ${disk.shadows} shadows · ${disk.edges} edges`;
    row.innerHTML =
      `<input class="sw" type="color" value="${rgbToHex(diskColor(disk.id))}" ` +
      `title="colour this disk" aria-label="colour for ${disk.name}">` +
      `<button class="nm" type="button">${disk.name}</button>` +
      `<span class="ct">${disk.nodes}</span>`;
    host.appendChild(row);
  }
  markMenu();
}

function markMenu() {
  const on = new Set(state.picks.filter((p) => p.kind === 'disk').map((p) => p.id));
  for (const row of document.querySelectorAll('.leg')) {
    row.classList.toggle('on', on.has(row.dataset.disk));
  }
}

/* ------------------------------------------------------------------ search --- */

let searchHits = [];

function runSearch() {
  const q = el('q').value.trim().toLowerCase();
  const d = state.prepared;
  searchHits = [];
  if (q) {
    for (let i = 0; i < d.n && searchHits.length < SEARCH_CAP; i++) {
      if (d.raw.nodes.shadow[i] === 0 && d.haystack[i].includes(q)) searchHits.push(i);
    }
    searchHits.sort((a, b) => d.degree[b] - d.degree[a]);
  }
  const total = q ? countMatches(d, q) : 0;
  el('results').innerHTML = searchHits.map((i) =>
    `<button class="hit" data-i="${i}">` +
    `<span class="nm">${d.raw.nodes.label[i]}</span>` +
    `<span class="ct">${d.raw.nodes.disk[i].replace(/^(pkg|ext):/, '')}</span></button>`
  ).join('');
  el('searchnote').textContent = !q ? ''
    : total > searchHits.length
      ? `${searchHits.length} of ${total} shown — refine to see the rest`
      : `${total} match${total === 1 ? '' : 'es'}`;
  markResults();
}

function countMatches(d, q) {
  let n = 0;
  for (let i = 0; i < d.n; i++) {
    if (d.raw.nodes.shadow[i] === 0 && d.haystack[i].includes(q)) n++;
  }
  return n;
}

function markResults() {
  for (const b of document.querySelectorAll('.hit')) {
    b.classList.toggle('on', state.members.has(Number(b.dataset.i)));
  }
}

/* ------------------------------------------------------------------ motion --- */

function setMoving(moving) {
  if (state.moving === moving) return;
  state.moving = moving;
  el('mode').textContent = moving ? 'moving · nodes only' : 'still';
  render();
}

function onViewStateChange({ viewState }) {
  state.viewState = viewState;
  setMoving(true);
  clearTimeout(state.stopTimer);
  state.stopTimer = setTimeout(() => setMoving(false), 180);
  render();
}

function render() {
  if (!state.deckgl || !state.prepared) return;
  state.deckgl.setProps({ layers: buildLayers(state.prepared), viewState: state.viewState });
  updateCounts();
}

function updateCounts() {
  const s = state.data.stats;
  const n = state.members.size;
  let line;
  if (state.moving) {
    line = 'nodes only while moving';
  } else if (n) {
    const names = state.picks.map((p) => p.kind === 'disk'
      ? (state.data.disks.find((x) => x.id === p.id)?.name ?? p.id)
      : state.data.nodes.label[p.index]);
    const shown = names.slice(0, 3).join(', ') + (names.length > 3 ? ` +${names.length - 3}` : '');
    // Never a silent filter: what is not being shown is stated, in counts.
    const rest = s.drawn_nodes - n;
    line = `${shown} · ${n.toLocaleString()} nodes · ` +
           `${(state.selGeom?.count ?? 0).toLocaleString()} edges · ` +
           `${rest.toLocaleString()} ${state.settings.filterMode === 'hide' ? 'hidden' : 'dimmed'}`;
  } else {
    line = `nothing selected — all ${s.edges.toLocaleString()} edges hidden; ` +
           'pick a disk, search, or click a node';
  }
  el('counts').innerHTML = `${s.drawn_nodes.toLocaleString()} drawn · ${s.disks} disks` +
                           `<br><span class="muted">${line}</span>`;
  el('clear').hidden = !n;
}

/* ---------------------------------------------------------------------- fps --- */

let frames = 0, lastReport = performance.now(), samples = [];
let framesDrawn = 0;
function tick() {
  frames++;
  const now = performance.now();
  if (now - lastReport >= 500) {
    const fps = (frames * 1000) / (now - lastReport);
    el('fps').textContent = fps.toFixed(0);
    if (state.benching) samples.push(fps);
    frames = 0; lastReport = now;
  }
  requestAnimationFrame(tick);
}

function benchmark(seconds = 6) {
  samples = []; state.benching = true;
  el('bench').textContent = 'benchmarking…';
  const t0 = performance.now();
  const start = { ...state.viewState };
  function step() {
    const t = (performance.now() - t0) / 1000;
    if (t >= seconds) {
      state.benching = false;
      samples.sort((a, b) => a - b);
      const med = samples[Math.floor(samples.length / 2)] || 0;
      const worst = samples[0] || 0;
      /* 60 is the vsync ceiling, not a measurement of capacity. When median and worst
       * both sit on it the honest statement is "no frames dropped, headroom unknown" --
       * reporting it as a score invites reading a ceiling as a limit. */
      const capped = med >= 59 && worst >= 59;
      el('bench').textContent =
        `median ${med.toFixed(0)} fps · worst ${worst.toFixed(0)} · ` +
        `${state.data.stats.drawn_nodes.toLocaleString()} nodes` +
        (state.settings.nodeSize >= SPHERE_FROM ? ' · spheres' : '') +
        (state.selGeom?.count ? ` · ${state.selGeom.count.toLocaleString()} edges` : '') +
        (capped ? ' · no frames dropped (60 is the vsync cap; headroom unmeasured)' : '');
      setMoving(false);
      return;
    }
    onViewStateChange({ viewState: { ...start,
      rotationOrbit: start.rotationOrbit + t * 60,
      rotationX: 55 + Math.sin(t) * 20,
      zoom: start.zoom + Math.sin(t * 0.8) * 0.6 } });
    requestAnimationFrame(step);
  }
  step();
}

/* -------------------------------------------------------------- diagnostics --- */

function diagnose() {
  const lines = [];
  const canvas = document.querySelector('#stage canvas');
  const gl = canvas && (canvas.getContext('webgl2') || canvas.getContext('webgl'));
  const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');
  lines.push(`canvas ${canvas ? canvas.width + '×' + canvas.height : 'MISSING'}` +
             ` · dpr ${window.devicePixelRatio}`);
  lines.push(`gl ${gl ? 'ok' : 'NONE'}` +
             (dbg ? ` · ${gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)}` : ''));
  const vp = state.deckgl?.getViewports?.()[0];
  if (vp) {
    const b = bounds(state.prepared, state.members.size ? state.members : null);
    const p = vp.project(b.centre).map(Math.round);
    const inside = p[0] > 0 && p[1] > 0 && p[0] < vp.width && p[1] < vp.height;
    lines.push(`zoom ${state.viewState.zoom.toFixed(2)} · tilt ${Math.round(state.viewState.rotationX)}` +
               ` · centre [${p}] ${inside ? 'ON' : 'OFF'} screen`);
  }
  lines.push(`layers ${state.deckgl?.props?.layers?.length ?? 0} · frames ${framesDrawn}`);
  el('diag').innerHTML = lines.join('<br>');
}

/* --------------------------------------------------------------------- boot --- */

function applyPanels() {
  const p = state.settings.panels;
  for (const [id, open] of Object.entries(p)) {
    const node = el(`panel-${id}`);
    if (node) node.classList.toggle('closed', !open);
  }
}

function syncControls() {
  const s = state.settings;
  el('spread').value = s.spread;
  el('spreadval').textContent = (+s.spread).toFixed(2) + '×';
  el('size').value = s.nodeSize;
  el('sizeval').textContent = (+s.nodeSize).toFixed(1) + '×' +
    (s.nodeSize >= SPHERE_FROM ? ' spheres' : '');
  el('sort').value = s.sortMode;
  el('filter').value = s.filterMode;
  el('direction').value = s.direction;
  el('colorby').value = s.colorBy;
  el('plates').checked = s.showPlates;
  el('trans').checked = s.showTranspositions;
}

async function boot() {
  const t0 = performance.now();
  const raw = await (await fetch('/api/graph')).json();
  state.data = raw;
  state.program = raw.program || 'program';
  state.settings = Settings.loadSettings(state.program);

  state.prepared = prepare(raw);
  state.prepared.plates = diskPlates(raw);

  // A saved order from a graph that has since changed must not silently drop disks.
  const ids = new Set(raw.disks.map((d) => d.id));
  const saved = state.settings.diskOrder;
  const usable = Array.isArray(saved) && saved.length &&
                 saved.every((id) => ids.has(id)) && saved.length === ids.size;
  state.settings.diskOrder = usable ? saved : defaultOrder(raw);

  state.picks = (state.settings.picks || []).filter((p) =>
    p.kind === 'disk' ? ids.has(p.id) : p.index >= 0 && p.index < state.prepared.n);

  applyLayout(state.prepared);
  recomputeMembers(state.prepared);
  buildSelectionGeometry(state.prepared);
  paintNodes(state.prepared);
  buildMenu();
  syncControls();
  applyPanels();
  state.viewState = fitView(state.prepared, 35);

  state.deckgl = new Deck({
    parent: el('stage'),
    /* Orthographic: under perspective the near plates magnify and the far ones shrink,
     * rendering a stack of equal disks as a tapered cylinder -- the exact shape the model
     * exists not to be. It also makes zoom map world units to pixels exactly. */
    views: [new OrbitView({ orbitAxis: 'Z', orthographic: true })],
    viewState: state.viewState,
    controller: { inertia: 250 },
    onViewStateChange,
    onClick: (info, event) => {
      if (info.index < 0) return;
      const mode = event?.srcEvent?.altKey ? 'remove'
                 : (event?.srcEvent?.shiftKey || event?.srcEvent?.metaKey) ? 'add'
                 : 'replace';
      togglePick(state.prepared, { kind: 'node', index: info.index }, mode);
      render();
    },
    getTooltip: ({ index }) => {
      if (index < 0) return null;
      const n = raw.nodes;
      const det = n.detail[index] || {};
      const extra = det.qualname || det.module || det.bkind || '';
      return { html: `<b>${n.label[index]}</b>${n.shadow[index] ? ' (shadow)' : ''}<br>` +
                     `<span class="k">${n.kind[index]} · ${n.disk[index]}</span>` +
                     (extra ? `<br><span class="k">${extra}</span>` : ''),
               style: { background: '#161e29', color: '#e6ecf3',
                        border: '1px solid #2c3849', borderRadius: '4px',
                        fontSize: '12px', padding: '4px 6px' } };
    },
    onError: (err) => {
      const gpuOff = /Failed to create WebGL context|GL_RENDERER = Disabled/.test(err.message);
      el('err').innerHTML = gpuOff
        ? '<b>This browser cannot draw.</b> Hardware acceleration is off, so no page ' +
          'here can get a WebGL context — nothing to do with your machine.<br>' +
          'Turn it on at <code>chrome://settings/system</code>, then relaunch Chrome. ' +
          '<code>chrome://gpu</code> says why. Safari works without changing anything.' +
          `<br><span class="muted">${err.message}</span>`
        : `deck.gl: ${err.message}`;
      el('err').hidden = false;
    },
    onAfterRender: () => { framesDrawn++; },
    layers: buildLayers(state.prepared),
  });

  window.__deck = state.deckgl; window.__d = state.prepared; window.__state = state;
  setTimeout(diagnose, 1500);
  updateCounts();
  el('hint').textContent =
    `loaded in ${((performance.now() - t0) / 1000).toFixed(1)}s · ` +
    'shift-click adds · alt-click removes';
  tick();
}

/* ----------------------------------------------------------------- controls --- */

/* Live controls update in place and re-render only the graph. A settings pane that
 * rebuilds itself on every `input` event destroys the control being dragged -- that cost
 * a colour picker in the mockup session, and it is why nothing here rebuilds the menu
 * while a swatch is being dragged. */
el('spread').addEventListener('input', (ev) => {
  state.settings.spread = parseFloat(ev.target.value);
  el('spreadval').textContent = state.settings.spread.toFixed(2) + '×';
  applyLayout(state.prepared);
  render();
});
el('spread').addEventListener('change', persist);

el('size').addEventListener('input', (ev) => {
  state.settings.nodeSize = parseFloat(ev.target.value);
  el('sizeval').textContent = state.settings.nodeSize.toFixed(1) + '×' +
    (state.settings.nodeSize >= SPHERE_FROM ? ' spheres' : '');
  paintNodes(state.prepared);
  render();
});
el('size').addEventListener('change', persist);

el('menu').addEventListener('click', (ev) => {
  const row = ev.target.closest('.leg');
  if (!row || ev.target.classList.contains('sw')) return;
  const mode = ev.shiftKey || ev.metaKey ? 'add' : ev.altKey ? 'remove' : 'replace';
  togglePick(state.prepared, { kind: 'disk', id: row.dataset.disk }, mode);
  render();
});

el('menu').addEventListener('input', (ev) => {
  if (!ev.target.classList.contains('sw')) return;
  const row = ev.target.closest('.leg');
  state.settings.diskColors[row.dataset.disk] = ev.target.value;
  // Choosing a colour for a disk is a statement that colour should mean *disk*.
  state.settings.colorBy = 'disk';
  el('colorby').value = 'disk';
  paintNodes(state.prepared);
  render();                       // the graph repaints; the swatch is left alone
});
el('menu').addEventListener('change', (ev) => {
  if (ev.target.classList.contains('sw')) persist();
});

/* Drag to reorder. Reordering is the stack order, so dropping a row moves a plate. */
let dragId = null;
el('menu').addEventListener('dragstart', (ev) => {
  const row = ev.target.closest('.leg');
  if (!row) return;
  dragId = row.dataset.disk;
  row.classList.add('dragging');
  ev.dataTransfer.effectAllowed = 'move';
});
el('menu').addEventListener('dragover', (ev) => {
  ev.preventDefault();
  const row = ev.target.closest('.leg');
  if (row) row.classList.add('over');
});
el('menu').addEventListener('dragleave', (ev) => {
  ev.target.closest('.leg')?.classList.remove('over');
});
el('menu').addEventListener('drop', (ev) => {
  ev.preventDefault();
  const row = ev.target.closest('.leg');
  document.querySelectorAll('.leg').forEach((r) => r.classList.remove('over', 'dragging'));
  if (!row || !dragId || row.dataset.disk === dragId) return;
  const order = state.settings.diskOrder;
  order.splice(order.indexOf(dragId), 1);
  order.splice(order.indexOf(row.dataset.disk), 0, dragId);
  // A hand-made order is only visible under manual sort, so say so by switching to it.
  state.settings.sortMode = 'manual';
  el('sort').value = 'manual';
  dragId = null;
  applyLayout(state.prepared);
  buildMenu();
  persist();
  render();
});
el('menu').addEventListener('dragend', () => {
  document.querySelectorAll('.leg').forEach((r) => r.classList.remove('over', 'dragging'));
});

el('sort').addEventListener('change', (ev) => {
  state.settings.sortMode = ev.target.value;
  buildMenu();
  persist();
});
el('filter').addEventListener('change', (ev) => {
  state.settings.filterMode = ev.target.value;
  paintNodes(state.prepared);
  persist();
  render();
});
el('direction').addEventListener('change', (ev) => {
  state.settings.direction = ev.target.value;
  afterSelectionChange(state.prepared);
  render();
});
el('colorby').addEventListener('change', (ev) => {
  state.settings.colorBy = ev.target.value;
  paintNodes(state.prepared);
  persist();
  render();
});
for (const [id, key] of [['plates', 'showPlates'], ['trans', 'showTranspositions']]) {
  el(id).addEventListener('change', (ev) => {
    state.settings[key] = ev.target.checked;
    persist();
    render();
  });
}

el('q').addEventListener('input', runSearch);
el('results').addEventListener('click', (ev) => {
  const b = ev.target.closest('.hit');
  if (!b) return;
  const mode = ev.shiftKey || ev.metaKey ? 'add' : ev.altKey ? 'remove' : 'replace';
  togglePick(state.prepared, { kind: 'node', index: Number(b.dataset.i) }, mode);
  render();
});

document.addEventListener('click', (ev) => {
  const head = ev.target.closest('[data-panel]');
  if (head) {
    const name = head.dataset.panel;
    state.settings.panels[name] = !state.settings.panels[name];
    applyPanels();
    persist();
    return;
  }
  const act = ev.target?.dataset?.act;
  if (!act) return;
  if (act === 'bench') return benchmark();
  if (act === 'clear') { clearSelection(state.prepared); return render(); }
  if (act === 'reset') {
    const { settings, cleared } = Settings.resetSettings(state.program, state.settings);
    state.settings = settings;
    state.settings.diskOrder = defaultOrder(state.data);
    state.picks = [];
    applyLayout(state.prepared);
    recomputeMembers(state.prepared);
    buildSelectionGeometry(state.prepared);
    paintNodes(state.prepared);
    buildMenu(); syncControls(); applyPanels();
    // A reset that silently reverts everything leaves you guessing what was yours.
    el('bench').textContent = cleared.length
      ? `reset to defaults — cleared ${cleared.join(', ')}`
      : 'already at defaults';
    onViewStateChange({ viewState: fitView(state.prepared, 35) });
    return;
  }
  const tilt = act === 'top' ? 90 : act === 'tilt' ? 35 : state.viewState.rotationX;
  onViewStateChange({ viewState: fitView(state.prepared, tilt) });
});

document.addEventListener('keydown', (ev) => {
  if (ev.metaKey || ev.ctrlKey || !state.prepared) return;
  if (ev.target.tagName === 'INPUT') return;          // typing in search is not a shortcut
  if (ev.key === 'f') onViewStateChange({ viewState: fitView(state.prepared) });
  if (ev.key === 'Escape') { clearSelection(state.prepared); render(); }
  if (ev.key === '/') { ev.preventDefault(); el('q').focus(); }
});

boot();
