/* The 2.5D stack.
 *
 * Three rules here came from Tom, and each corrects something this file did wrong.
 *
 * 1. **The stack is an abstraction, not an object.** The plates were being drawn as if
 *    the scaffolding were the content. They are not there. Nodes are tiny dots at
 *    heights that mean something; the disk is the idea that groups them, and an idea
 *    does not get a surface.
 *
 * 2. **Edges are shown on demand, never by default.** Thirteen thousand lines do not
 *    describe a program, they erase it -- whatever else is on screen goes under a haze.
 *    So: nodes alone until something is selected, then only the edges touching the
 *    selection, and only once the camera has stopped.
 *
 * 3. **Only nodes while moving.** Lines and text are the expensive layers and also the
 *    ones nobody can read while the view slides.
 *
 * Performance comes from binary attributes: everything drawn is built once into flat
 * typed arrays and handed to deck.gl as buffers, so panning costs the same at fifteen
 * thousand nodes as at five hundred. The `data` wrappers are cached deliberately --
 * building them inside the per-frame layer function would re-upload half a megabyte
 * every frame of a drag, which is the exact cost the typed arrays exist to avoid.
 */
'use strict';

const {
  Deck, OrbitView, ScatterplotLayer, LineLayer, TextLayer, PolygonLayer,
  COORDINATE_SYSTEM, CollisionFilterExtension,
} = deck;

const CARTESIAN = COORDINATE_SYSTEM.CARTESIAN;

/* Colour carries one dimension at a time (design rule 4). Here it carries node kind;
 * shadows are the exception, because "this is not really here" outranks what kind of
 * thing it is -- a shadow mistaken for a real node is a lie about where code lives. */
const KIND_COLOR = {
  ROUTINE:   [ 45, 212, 191],
  STRUCTURE: [147, 197, 253],
  CONSTANT:  [148, 163, 184],
  BOUNDARY:  [196, 181, 253],
};
const SHADOW_COLOR = [ 88, 102, 122];
const DIM_COLOR    = [ 52,  64,  82];        // unselected, while a selection stands
const EDGE_COLOR   = [ 94, 234, 212, 150];   // only ever drawn for a selection
const CROSS_COLOR  = [125, 211, 252, 130];
const PLATE_FILL   = [ 22,  30,  41,  70];
const PLATE_LINE   = [ 44,  56,  73, 140];

/* Tiny. A node is a position, not an object with a surface -- at fifteen thousand of
 * them any radius that reads as a disc turns the stack into a solid mass. Degree still
 * moves the size, but across two pixels rather than twenty. */
const DOT_MIN = 1.4;
const DOT_MAX = 3.6;

const NODE_LABEL_CAP = 250;
const NODE_LABEL_ZOOM = -1.2;     // below this the stack is an overview, not a reading
const DEFAULT_SPREAD = 0.35;

const el = (id) => document.getElementById(id);

const state = {
  data: null, prepared: null, deckgl: null,
  moving: false, stopTimer: 0,
  viewState: { target: [0, 0, 0], zoom: -4, rotationX: 35, rotationOrbit: 20,
               minZoom: -9, maxZoom: 8 },
  /* The filter *is* the interface. Nothing but nodes is drawn until this is set, so
   * selecting is how a reader asks for detail rather than being handed all of it. */
  selection: null,
  showPlates: false,
  showTranspositions: false,
  testPattern: false,
  hiddenLabels: 0,
};

/* ---------------------------------------------------------------- geometry --- */

function bounds(d) {
  let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < d.n; i++) {
    for (let a = 0; a < 3; a++) {
      const v = d.positions[i * 3 + a];
      if (v < lo[a]) lo[a] = v;
      if (v > hi[a]) hi[a] = v;
    }
  }
  const centre = [0, 1, 2].map((a) => (lo[a] + hi[a]) / 2);
  // A true radius about the axis, not half the X extent, which would be wrong for any
  // disk that is not a full circle.
  let r = 0;
  for (let i = 0; i < d.n; i++) {
    const h = Math.hypot(d.positions[i * 3] - centre[0], d.positions[i * 3 + 1] - centre[1]);
    if (h > r) r = h;
  }
  return { centre, radius: r || 1, height: (hi[2] - lo[2]) || 1 };
}

/* Fit the bounding *cylinder*, at the tilt actually in force.
 *
 * A bounding sphere is rotation-invariant and therefore safe at every angle by being
 * wrong at nearly all of them: it reserves room for the worst case, so the stack sits
 * small in frame whichever way it is turned. The stack is a cylinder, and orbiting about
 * Z leaves its footprint a circle -- so tilt is the only term that changes the
 * silhouette, and a snug fit is a two-term formula rather than a guess.
 */
function fitView(d, rotationX = state.viewState.rotationX) {
  const b = bounds(d);
  const t = (rotationX * Math.PI) / 180;
  const vertical = Math.abs(b.height * Math.cos(t)) + Math.abs(2 * b.radius * Math.sin(t));
  const scale = Math.min(
    (window.innerWidth * 0.60) / (2 * b.radius),   // room for the legend at the side
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
    positions[i * 3 + 2] = raw.nodes.z[i];
  }
  for (let i = 0; i < raw.edges.from.length; i++) {
    degree[raw.edges.from[i]]++;
    degree[raw.edges.to[i]]++;
  }
  for (let i = 0; i < n; i++) {
    radii[i] = Math.min(DOT_MAX, DOT_MIN + Math.sqrt(degree[i]) * 0.28);
  }

  const baseZ = new Float32Array(n);
  for (let i = 0; i < n; i++) baseZ[i] = positions[i * 3 + 2];

  // Members of each disk, so selecting a plate is a lookup rather than a scan.
  const byDisk = new Map();
  for (let i = 0; i < n; i++) {
    const k = raw.nodes.disk[i];
    if (!byDisk.has(k)) byDisk.set(k, []);
    byDisk.get(k).push(i);
  }

  // Incident edges per node, for the same reason.
  const incident = new Map();
  for (let i = 0; i < raw.edges.from.length; i++) {
    for (const end of [raw.edges.from[i], raw.edges.to[i]]) {
      if (!incident.has(end)) incident.set(end, []);
      incident.get(end).push(i);
    }
  }

  const ranked = [];
  for (let i = 0; i < n; i++) if (raw.nodes.shadow[i] === 0) ranked.push(i);
  ranked.sort((a, b) => degree[b] - degree[a]);

  const d = { raw, n, positions, colors, radii, degree, baseZ, byDisk, incident,
              ranked, spread: 1, plates: [] };
  paintNodes(d);
  return d;
}

function paintNodes(d) {
  /* Colour depends on the selection, so it is recomputed rather than baked. Everything
   * outside the selection goes to near-background: dimming is what makes a subset
   * legible without hiding the shape it sits in. */
  const sel = state.selection?.members ?? null;
  for (let i = 0; i < d.n; i++) {
    const shadow = d.raw.nodes.shadow[i] === 1;
    let c, a;
    if (sel && !sel.has(i)) {
      c = DIM_COLOR; a = 110;
    } else {
      c = shadow ? SHADOW_COLOR : (KIND_COLOR[d.raw.nodes.kind[i]] || KIND_COLOR.ROUTINE);
      a = shadow ? 150 : 255;
    }
    d.colors[i * 4] = c[0]; d.colors[i * 4 + 1] = c[1];
    d.colors[i * 4 + 2] = c[2]; d.colors[i * 4 + 3] = a;
  }
  d.gpu = null;
}

function applySpread(d, spread) {
  d.spread = spread;
  for (let i = 0; i < d.n; i++) d.positions[i * 3 + 2] = d.baseZ[i] * spread;
  for (const p of d.plates) for (const pt of p.polygon) pt[2] = p.baseZ * spread;
  d.gpu = null;
  if (state.selection) buildSelectionGeometry(d);
}

function diskPlates(raw) {
  const zByDisk = new Map();
  for (let i = 0; i < raw.nodes.id.length; i++) {
    if (!zByDisk.has(raw.nodes.disk[i])) zByDisk.set(raw.nodes.disk[i], raw.nodes.z[i]);
  }
  const R = 1060, SEG = 64;
  return raw.disks.map((d) => {
    const z = zByDisk.get(d.id) ?? 0;
    const ring = [];
    for (let k = 0; k <= SEG; k++) {
      const t = (k / SEG) * Math.PI * 2;
      ring.push([Math.cos(t) * R, Math.sin(t) * R, z]);
    }
    return { polygon: ring, disk: d, baseZ: z };
  });
}

/* --------------------------------------------------------------- selection --- */

function selectDisk(d, diskId) {
  const members = new Set(d.byDisk.get(diskId) ?? []);
  const info = d.raw.disks.find((x) => x.id === diskId);
  state.selection = { kind: 'disk', id: diskId, label: info?.name ?? diskId, members };
  buildSelectionGeometry(d);
  paintNodes(d);
}

function selectNode(d, index) {
  /* A node and its immediate neighbours. One hop, because the point of selecting is to
   * see what *this* touches; two hops is most of the program again. */
  const members = new Set([index]);
  for (const e of d.incident.get(index) ?? []) {
    members.add(d.raw.edges.from[e]);
    members.add(d.raw.edges.to[e]);
  }
  state.selection = { kind: 'node', id: index, label: d.raw.nodes.label[index], members };
  buildSelectionGeometry(d);
  paintNodes(d);
}

function clearSelection(d) {
  state.selection = null;
  paintNodes(d);
}

function buildSelectionGeometry(d) {
  /* Only the edges the selection actually touches. Built fresh on each selection: the
   * subset is small by construction, and a stale buffer is worse than a rebuilt one. */
  const sel = state.selection;
  if (!sel) return;
  const wanted = [];
  if (sel.kind === 'node') {
    const seen = new Set();
    for (const e of d.incident.get(sel.id) ?? []) {
      if (!seen.has(e)) { seen.add(e); wanted.push(e); }
    }
  } else {
    for (let e = 0; e < d.raw.edges.from.length; e++) {
      if (sel.members.has(d.raw.edges.from[e]) && sel.members.has(d.raw.edges.to[e])) {
        wanted.push(e);
      }
    }
  }
  const src = new Float32Array(wanted.length * 3);
  const dst = new Float32Array(wanted.length * 3);
  wanted.forEach((e, k) => {
    const a = d.raw.edges.from[e] * 3, b = d.raw.edges.to[e] * 3;
    src[k * 3] = d.positions[a]; src[k * 3 + 1] = d.positions[a + 1]; src[k * 3 + 2] = d.positions[a + 2];
    dst[k * 3] = d.positions[b]; dst[k * 3 + 1] = d.positions[b + 1]; dst[k * 3 + 2] = d.positions[b + 2];
  });
  sel.edgeCount = wanted.length;
  sel.edgeSrc = src;
  sel.edgeDst = dst;

  // Transpositions for the selection only: a shadow in the set, joined to its real self.
  const links = [];
  for (const i of sel.members) {
    const r = d.raw.nodes.real[i];
    if (d.raw.nodes.shadow[i] === 1 && r >= 0) links.push([i, r]);
  }
  const tS = new Float32Array(links.length * 3), tD = new Float32Array(links.length * 3);
  links.forEach(([i, r], k) => {
    tS[k * 3] = d.positions[i * 3]; tS[k * 3 + 1] = d.positions[i * 3 + 1]; tS[k * 3 + 2] = d.positions[i * 3 + 2];
    tD[k * 3] = d.positions[r * 3]; tD[k * 3 + 1] = d.positions[r * 3 + 1]; tD[k * 3 + 2] = d.positions[r * 3 + 2];
  });
  sel.transCount = links.length;
  sel.transSrc = tS;
  sel.transDst = tD;
  sel.gpu = null;
}

/* ------------------------------------------------------------------ layers --- */

function gpuData(d) {
  if (d.gpu) return d.gpu;
  d.gpu = {
    nodes: { length: d.n, attributes: {
      getPosition: { value: d.positions, size: 3 },
      getFillColor: { value: d.colors, size: 4, normalized: true },
      getRadius: { value: d.radii, size: 1 } } },
  };
  return d.gpu;
}

function selectionGpu(sel) {
  if (sel.gpu) return sel.gpu;
  sel.gpu = {
    edges: { length: sel.edgeCount, attributes: {
      getSourcePosition: { value: sel.edgeSrc, size: 3 },
      getTargetPosition: { value: sel.edgeDst, size: 3 } } },
    trans: { length: sel.transCount, attributes: {
      getSourcePosition: { value: sel.transSrc, size: 3 },
      getTargetPosition: { value: sel.transDst, size: 3 } } },
  };
  return sel.gpu;
}

function buildLayers(d) {
  const still = !state.moving;
  const layers = [];

  if (state.showPlates) {
    layers.push(new PolygonLayer({
      id: 'plates', data: d.plates, coordinateSystem: CARTESIAN,
      getPolygon: (p) => p.polygon, filled: true, stroked: true, extruded: false,
      getFillColor: PLATE_FILL, getLineColor: PLATE_LINE, getLineWidth: 1,
      lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: { getPolygon: d.spread },
    }));
  }

  /* Edges only for a selection, and only once the camera has stopped. Both halves
   * matter: all thirteen thousand at once is a haze that erases the nodes, and even the
   * selected few are noise while the view is sliding. */
  const sel = state.selection;
  if (sel && still && sel.edgeCount) {
    const g = selectionGpu(sel);
    layers.push(new LineLayer({
      id: 'sel-edges', coordinateSystem: CARTESIAN, data: g.edges,
      getColor: EDGE_COLOR, getWidth: 1.2, widthUnits: 'pixels', pickable: false,
    }));
    if (sel.transCount && state.showTranspositions) {
      layers.push(new LineLayer({
        id: 'sel-trans', coordinateSystem: CARTESIAN, data: g.trans,
        getColor: CROSS_COLOR, getWidth: 1.2, widthUnits: 'pixels', pickable: false,
      }));
    }
  }

  layers.push(new ScatterplotLayer({
    id: 'nodes', coordinateSystem: CARTESIAN, data: gpuData(d).nodes,
    radiusUnits: 'pixels', radiusMinPixels: DOT_MIN, radiusMaxPixels: DOT_MAX * 2,
    pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 255],
  }));

  if (state.testPattern) {
    const b = bounds(d);
    layers.push(new ScatterplotLayer({
      id: 'test-pattern', coordinateSystem: CARTESIAN,
      data: [
        { p: b.centre, c: [255, 0, 200] },
        { p: [b.centre[0], b.centre[1], b.centre[2] + b.height / 2], c: [255, 220, 0] },
        { p: [b.centre[0], b.centre[1], b.centre[2] - b.height / 2], c: [0, 200, 255] },
      ],
      getPosition: (o) => o.p, getFillColor: (o) => o.c,
      getRadius: 24, radiusUnits: 'pixels', radiusMinPixels: 18, pickable: false,
    }));
  }

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
        /* Overlapping labels are not a denser reading, they are a grey mat. The filter
         * keeps the higher-priority label, and priority is degree -- so what survives a
         * crowded patch is its busiest node. */
        extensions: [new CollisionFilterExtension()],
        collisionEnabled: true,
        collisionTestProps: { sizeScale: 1.5 },
        getCollisionPriority: (o) => o.priority,
      }));
    }
  }
  return layers;
}

function pickLabels(d) {
  // A selection names itself; with none, the busiest nodes stand in for the whole.
  const pool = state.selection
    ? [...state.selection.members].sort((a, b) => d.degree[b] - d.degree[a])
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

/* ------------------------------------------------------------------ legend --- */

function buildLegend(raw) {
  /* Multiple columns, interleaved: consecutive disks fill across the columns and every
   * second column is nudged down half a row, so the rows nest instead of lining up.
   * That is what lets fifty-one entries stay legible in the space eighteen would
   * otherwise take.
   *
   * HTML rather than text in the scene. A legend that spins away with the camera is not
   * a legend, and this one has to be clickable -- selecting a plate is the main way into
   * the graph, and the graph draws nothing but dots until something is selected. */
  const host = el('legend');
  host.innerHTML = '';
  raw.disks
    .slice()
    .sort((a, b) => (a.kind === b.kind ? b.nodes - a.nodes : a.kind === 'package' ? -1 : 1))
    .forEach((d) => {
      const item = document.createElement('button');
      item.className = `leg ${d.kind}`;
      item.dataset.disk = d.id;
      item.innerHTML = `<span class="nm">${d.name}</span><span class="ct">${d.nodes}</span>`;
      item.title = `${d.nodes} nodes · ${d.shadows} shadows · ${d.edges} edges`;
      host.appendChild(item);
    });
}

function markLegend() {
  const id = state.selection?.kind === 'disk' ? state.selection.id : null;
  for (const b of document.querySelectorAll('.leg')) {
    b.classList.toggle('on', b.dataset.disk === id);
  }
}

/* ------------------------------------------------------------------- motion --- */

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
  state.deckgl.setProps({
    layers: buildLayers(state.prepared),
    viewState: state.viewState,
  });
  updateCounts();
}

function updateCounts() {
  const s = state.data.stats;
  const sel = state.selection;
  let line;
  if (state.moving) {
    line = 'nodes only while moving';
  } else if (sel) {
    line = `${sel.label} · ${sel.members.size.toLocaleString()} nodes · ` +
           `${(sel.edgeCount || 0).toLocaleString()} edges drawn` +
           (state.hiddenLabels ? ` · ${state.hiddenLabels.toLocaleString()} labels capped` : '');
  } else {
    line = `nothing selected — all ${s.edges.toLocaleString()} edges hidden; ` +
           'pick a disk or click a node';
  }
  el('counts').innerHTML =
    `${s.drawn_nodes.toLocaleString()} drawn · ${s.disks} disks` +
    `<br><span class="muted">${line}</span>`;
  el('clear').hidden = !sel;
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

/* A hand-driven frame rate is an anecdote. This orbits on a fixed path for a fixed time
 * and reports the median, so the number can be compared between runs and machines. */
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
       * reporting it as a score would invite reading a ceiling as a limit, and the
       * difference matters the first time this is pointed at something larger. */
      const capped = med >= 59 && worst >= 59;
      el('bench').textContent =
        `median ${med.toFixed(0)} fps · worst ${worst.toFixed(0)} · ` +
        `${state.data.stats.drawn_nodes.toLocaleString()} nodes` +
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
             ` · css ${window.innerWidth}×${window.innerHeight} · dpr ${window.devicePixelRatio}`);
  lines.push(`gl ${gl ? 'ok' : 'NONE'}` +
             (dbg ? ` · ${gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)}` : ''));
  const vp = state.deckgl?.getViewports?.()[0];
  if (vp) {
    const b = bounds(state.prepared);
    const on = [b.centre,
                [b.centre[0], b.centre[1], b.centre[2] + b.height / 2],
                [b.centre[0], b.centre[1], b.centre[2] - b.height / 2]]
      .map((w) => vp.project(w).map(Math.round));
    lines.push(`zoom ${state.viewState.zoom.toFixed(2)} · tilt ${Math.round(state.viewState.rotationX)}` +
               ` · centre [${on[0]}]`);
    const inside = on.some(([x, y]) => x > 0 && y > 0 && x < vp.width && y < vp.height);
    lines.push(inside ? 'geometry projects ON screen' : 'geometry projects OFF screen');
  }
  lines.push(`layers ${state.deckgl?.props?.layers?.length ?? 0} · frames ${framesDrawn}`);
  el('diag').innerHTML = lines.join('<br>');
}

/* --------------------------------------------------------------------- boot --- */

async function boot() {
  const t0 = performance.now();
  const raw = await (await fetch('/api/graph')).json();
  state.data = raw;
  state.prepared = prepare(raw);
  state.prepared.plates = diskPlates(raw);
  applySpread(state.prepared, DEFAULT_SPREAD);
  buildLegend(raw);
  state.viewState = fitView(state.prepared, 35);

  state.deckgl = new Deck({
    parent: el('stage'),
    /* Orthographic, not perspective: under perspective the near plates are magnified
     * and the far ones shrink, so a stack of equal disks renders as a tapered cylinder
     * -- the exact shape the model is trying not to be. It also makes zoom map world
     * units to pixels exactly, so framing is arithmetic rather than a fudge. */
    views: [new OrbitView({ orbitAxis: 'Z', orthographic: true })],
    viewState: state.viewState,
    controller: { inertia: 250 },
    onViewStateChange,
    onClick: ({ index }) => {
      if (index >= 0) { selectNode(state.prepared, index); markLegend(); render(); }
    },
    getTooltip: ({ index }) => {
      if (index < 0) return null;
      const n = raw.nodes;
      return { html: `<b>${n.label[index]}</b>${n.shadow[index] ? ' (shadow)' : ''}<br>` +
                     `<span class="k">${n.kind[index]} · ${n.disk[index]}</span>`,
               style: { background: '#161e29', color: '#e6ecf3',
                        border: '1px solid #2c3849', borderRadius: '4px',
                        fontSize: '12px', padding: '4px 6px' } };
    },
    onError: (err) => {
      /* A raw driver string is a fact, not an answer. The failure a reader will actually
       * hit is a browser with hardware acceleration off -- the canvas then stays blank
       * with no clue the cause is a setting rather than the program -- so that case is
       * named and the remedy given. Same discipline as a finding stating its blind spot. */
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
    `loaded in ${((performance.now() - t0) / 1000).toFixed(1)}s · drag orbit · scroll zoom`;
  tick();
}

/* ----------------------------------------------------------------- controls --- */

el('spread').addEventListener('input', (ev) => {
  const v = parseFloat(ev.target.value);
  el('spreadval').textContent = v.toFixed(2) + '×';
  applySpread(state.prepared, v);
  render();
});

el('legend').addEventListener('click', (ev) => {
  const b = ev.target.closest('.leg');
  if (!b) return;
  if (state.selection?.id === b.dataset.disk) clearSelection(state.prepared);
  else selectDisk(state.prepared, b.dataset.disk);
  markLegend();
  render();
});

for (const [id, key] of [['plates', 'showPlates'], ['trans', 'showTranspositions'],
                         ['test', 'testPattern']]) {
  el(id).addEventListener('change', (ev) => { state[key] = ev.target.checked; render(); });
}

document.addEventListener('click', (ev) => {
  const act = ev.target?.dataset?.act;
  if (!act) return;
  if (act === 'bench') return benchmark();
  if (act === 'clear') {
    clearSelection(state.prepared); markLegend(); return render();
  }
  // `fit` keeps the angle you are looking from; the view buttons choose one. Re-framing
  // is not optional either way -- the stack is wide from above and tall from the side.
  const tilt = act === 'top' ? 90 : act === 'tilt' ? 35 : state.viewState.rotationX;
  onViewStateChange({ viewState: fitView(state.prepared, tilt) });
});

document.addEventListener('keydown', (ev) => {
  if (ev.metaKey || ev.ctrlKey || !state.prepared) return;
  if (ev.key === 'f') onViewStateChange({ viewState: fitView(state.prepared) });
  if (ev.key === 'Escape') { clearSelection(state.prepared); markLegend(); render(); }
});

boot();
