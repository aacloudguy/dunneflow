/* The 2.5D stack.
 *
 * Everything the GPU draws is built once into flat typed arrays and handed to deck.gl as
 * binary attributes. That is the whole performance story: with per-object accessors,
 * fifteen thousand nodes means fifteen thousand function calls per attribute per update,
 * and the frame budget is gone before anything is drawn. With binary attributes the data
 * is uploaded once and re-drawn for free, so panning costs the same at 15,000 nodes as at
 * 500.
 *
 * Level of detail is the other half. While the camera moves, only nodes are drawn. Labels
 * appear when it stops. That is a requirement, not an optimisation -- text is the
 * expensive layer and it is also the layer nobody can read while the view is sliding.
 */
'use strict';

const {
  Deck, OrbitView, ScatterplotLayer, LineLayer, TextLayer, PolygonLayer,
  COORDINATE_SYSTEM,
} = deck;

const CARTESIAN = COORDINATE_SYSTEM.CARTESIAN;

/* Colour carries one dimension at a time (design rule 4). Here it carries node kind;
 * shadows are the exception, because "this is not really here" outranks what kind of
 * thing it is -- a shadow you mistake for a real node is a lie about where code lives. */
const KIND_COLOR = {
  ROUTINE:   [ 45, 212, 191],
  STRUCTURE: [147, 197, 253],
  CONSTANT:  [148, 163, 184],
  BOUNDARY:  [196, 181, 253],
};
const SHADOW_COLOR = [ 90, 104, 124];
const EDGE_COLOR   = [ 68,  86, 110, 130];
const CROSS_COLOR  = [125, 211, 252,  90];   // transposition: shadow → its real self
const DISK_FILL    = [ 22,  30,  41, 110];
const DISK_LINE    = [ 44,  56,  73, 200];

/* Labels are capped, and the cap is stated. Fifteen thousand labels is not a picture and
 * not a reading; the cap picks the busiest nodes, and the HUD says how many it hid --
 * design rule 1, no filter is ever silent. */
const NODE_LABEL_CAP = 400;
const EDGE_LABEL_CAP = 150;
const EDGE_LABEL_ZOOM = 1.5;      // edge labels only once genuinely zoomed in

const el = (id) => document.getElementById(id);
const state = {
  data: null, deckgl: null, moving: false, stopTimer: 0,
  viewState: { target: [0, 0, 0], zoom: -4, rotationX: 35, rotationOrbit: 20,
               minZoom: -9, maxZoom: 6 },
  hiddenLabels: 0,
};

/* Frame the whole stack from its actual extent rather than from a guessed constant.
 * The stack's height depends on how many disks a program has -- 51 for Mensores, 14 for
 * DunneFlow -- so any fixed target and zoom is right for exactly one program and shows
 * the others as a speck or from inside. Opening onto nothing is indistinguishable from
 * opening onto a failure. */
function fitView(d, rotationX = 35) {
  let lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < d.n; i++) {
    for (let a = 0; a < 3; a++) {
      const v = d.positions[i * 3 + a];
      if (v < lo[a]) lo[a] = v;
      if (v > hi[a]) hi[a] = v;
    }
  }
  const target = [0, 1, 2].map((a) => (lo[a] + hi[a]) / 2);
  const span = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1);
  const px = Math.min(window.innerWidth, window.innerHeight) * 0.82;
  return { ...state.viewState, target, rotationX, zoom: Math.log2(px / span) };
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
    const shadow = raw.nodes.shadow[i] === 1;
    const c = shadow ? SHADOW_COLOR : (KIND_COLOR[raw.nodes.kind[i]] || KIND_COLOR.ROUTINE);
    colors[i * 4]     = c[0];
    colors[i * 4 + 1] = c[1];
    colors[i * 4 + 2] = c[2];
    colors[i * 4 + 3] = shadow ? 120 : 235;
    // Busier things are bigger, damped so a hub does not swamp its neighbours.
    radii[i] = (shadow ? 3.5 : 5) + Math.min(14, Math.sqrt(degree[i]) * 2.2);
  }

  const e = raw.edges.from.length;
  const eSrc = new Float32Array(e * 3);
  const eDst = new Float32Array(e * 3);
  for (let i = 0; i < e; i++) {
    const a = raw.edges.from[i] * 3, b = raw.edges.to[i] * 3;
    eSrc[i * 3] = positions[a]; eSrc[i * 3 + 1] = positions[a + 1]; eSrc[i * 3 + 2] = positions[a + 2];
    eDst[i * 3] = positions[b]; eDst[i * 3 + 1] = positions[b + 1]; eDst[i * 3 + 2] = positions[b + 2];
  }

  /* Transpositions: the Z line from a shadow to the real node it proxies. This is the
   * one thing that makes the stack a single graph rather than a pile of unrelated
   * pictures, so it gets its own layer and its own colour. */
  const links = [];
  for (let i = 0; i < n; i++) {
    const r = raw.nodes.real[i];
    if (raw.nodes.shadow[i] === 1 && r >= 0) links.push([i, r]);
  }
  const tSrc = new Float32Array(links.length * 3);
  const tDst = new Float32Array(links.length * 3);
  links.forEach(([i, r], k) => {
    tSrc[k * 3] = positions[i * 3]; tSrc[k * 3 + 1] = positions[i * 3 + 1]; tSrc[k * 3 + 2] = positions[i * 3 + 2];
    tDst[k * 3] = positions[r * 3]; tDst[k * 3 + 1] = positions[r * 3 + 1]; tDst[k * 3 + 2] = positions[r * 3 + 2];
  });

  // Label candidates, busiest first, real nodes only.
  const ranked = [];
  for (let i = 0; i < n; i++) if (raw.nodes.shadow[i] === 0) ranked.push(i);
  ranked.sort((a, b) => degree[b] - degree[a]);

  // The unscaled Z of every drawn thing, kept so the deck can be fanned or squeezed
  // without asking the server again. Spread is a look, not a fact.
  const baseZ = new Float32Array(n);
  for (let i = 0; i < n; i++) baseZ[i] = positions[i * 3 + 2];

  return { raw, n, positions, colors, radii, degree, eSrc, eDst, e,
           tSrc, tDst, tCount: links.length, ranked, baseZ, links, spread: 1 };
}

function applySpread(d, spread) {
  /* Fan the deck. Only Z changes, and every array carrying a Z has to be re-derived --
   * nodes, both ends of every edge, and both ends of every transposition. Missing one of
   * them leaves edges hanging in the gap between plates, which looks like a rendering
   * bug and is really a forgotten array. */
  d.spread = spread;
  for (let i = 0; i < d.n; i++) d.positions[i * 3 + 2] = d.baseZ[i] * spread;
  for (let i = 0; i < d.e; i++) {
    d.eSrc[i * 3 + 2] = d.baseZ[d.raw.edges.from[i]] * spread;
    d.eDst[i * 3 + 2] = d.baseZ[d.raw.edges.to[i]] * spread;
  }
  d.links.forEach(([i, r], k) => {
    d.tSrc[k * 3 + 2] = d.baseZ[i] * spread;
    d.tDst[k * 3 + 2] = d.baseZ[r] * spread;
  });
  for (const p of d.plates) for (const pt of p.polygon) pt[2] = p.baseZ * spread;
  d.gpu = null;                 // one re-upload, on change, not per frame
}

function diskPlates(raw) {
  /* One translucent plate per disk, so the stack reads as a stack even where a disk is
   * sparse. Drawn as a polygon rather than a circle mesh: 64 segments is plenty and
   * costs nothing at fifty-odd plates. */
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

/* ------------------------------------------------------------------ layers --- */

/* deck.gl re-uploads a layer's buffers when the `data` reference changes. Building a
 * fresh object literal inside `buildLayers` would therefore push half a megabyte of
 * vertex data to the GPU on *every frame of a drag* -- the exact cost the binary
 * attributes were chosen to avoid, reintroduced by an object literal in the wrong place.
 * The wrappers are built once and only replaced when the geometry genuinely changes. */
function gpuData(d) {
  if (d.gpu) return d.gpu;
  d.gpu = {
    nodes: { length: d.n, attributes: {
      getPosition: { value: d.positions, size: 3 },
      getFillColor: { value: d.colors, size: 4, normalized: true },
      getRadius: { value: d.radii, size: 1 } } },
    edges: { length: d.e, attributes: {
      getSourcePosition: { value: d.eSrc, size: 3 },
      getTargetPosition: { value: d.eDst, size: 3 } } },
    trans: { length: d.tCount, attributes: {
      getSourcePosition: { value: d.tSrc, size: 3 },
      getTargetPosition: { value: d.tDst, size: 3 } } },
  };
  return d.gpu;
}

function buildLayers(d) {
  const showLabels = !state.moving;
  const gpu = gpuData(d);
  const layers = [
    new PolygonLayer({
      id: 'plates', data: d.plates, coordinateSystem: CARTESIAN,
      getPolygon: (p) => p.polygon, filled: true, stroked: true, extruded: false,
      getFillColor: DISK_FILL, getLineColor: DISK_LINE, getLineWidth: 2,
      lineWidthUnits: 'pixels', pickable: false, parameters: { depthTest: false },
      updateTriggers: { getPolygon: d.spread },
    }),
    new LineLayer({
      id: 'transpositions', coordinateSystem: CARTESIAN, data: gpu.trans,
      getColor: CROSS_COLOR, getWidth: 1, widthUnits: 'pixels', pickable: false,
    }),
    new LineLayer({
      id: 'edges', coordinateSystem: CARTESIAN, data: gpu.edges,
      getColor: EDGE_COLOR, getWidth: 1, widthUnits: 'pixels', pickable: false,
    }),
    new ScatterplotLayer({
      id: 'nodes', coordinateSystem: CARTESIAN, data: gpu.nodes,
      radiusUnits: 'pixels', radiusMinPixels: 1.5, radiusMaxPixels: 22,
      pickable: true, autoHighlight: true,
      highlightColor: [255, 255, 255, 255],
    }),
  ];

  if (showLabels) {
    const labels = pickLabels(d);
    layers.push(new TextLayer({
      id: 'node-labels', data: labels, coordinateSystem: CARTESIAN,
      getPosition: (o) => o.pos, getText: (o) => o.text,
      getSize: 11, sizeUnits: 'pixels', getColor: [230, 236, 243, 235],
      getTextAnchor: 'start', getAlignmentBaseline: 'center',
      getPixelOffset: [8, 0], background: true,
      getBackgroundColor: [11, 17, 25, 190], backgroundPadding: [3, 1],
      characterSet: 'auto', fontFamily: 'ui-monospace, Menlo, monospace',
      pickable: false,
    }));
  }
  return layers;
}

function pickLabels(d) {
  /* Cap by rank, and report what the cap hid. The alternative -- drawing every label and
   * letting them overlap into a grey mat -- is not more honest, it is just unreadable. */
  const out = [];
  const cap = Math.min(NODE_LABEL_CAP, d.ranked.length);
  for (let k = 0; k < cap; k++) {
    const i = d.ranked[k];
    out.push({ pos: [d.positions[i * 3], d.positions[i * 3 + 1], d.positions[i * 3 + 2]],
               text: d.raw.nodes.label[i] });
  }
  state.hiddenLabels = d.ranked.length - cap;
  return out;
}

/* ------------------------------------------------------------------- motion --- */

function setMoving(moving) {
  if (state.moving === moving) return;
  state.moving = moving;
  el('mode').textContent = moving ? 'moving · nodes only' : 'static · labels';
  render();
}

function onViewStateChange({ viewState }) {
  state.viewState = viewState;
  setMoving(true);
  clearTimeout(state.stopTimer);
  // Long enough that a pause mid-drag does not flash labels in and out.
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
  const hidden = state.moving
    ? 'labels off while moving'
    : (state.hiddenLabels ? `${state.hiddenLabels.toLocaleString()} labels hidden by cap` : 'all labels shown');
  el('counts').innerHTML =
    `${s.drawn_nodes.toLocaleString()} drawn · ${s.edges.toLocaleString()} edges · ` +
    `${s.disks} disks<br><span class="muted">${hidden}</span>`;
}

/* ---------------------------------------------------------------------- fps --- */

let frames = 0, lastReport = performance.now(), samples = [];
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

/* A hand-driven frame rate is an anecdote. This orbits the camera on a fixed path for a
 * fixed time and reports the median, so the number can be compared between runs. */
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
      const low = samples[0] || 0;
      el('bench').textContent =
        `median ${med.toFixed(0)} fps · worst ${low.toFixed(0)} · ${samples.length} samples`;
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

/* --------------------------------------------------------------------- boot --- */

async function boot() {
  const t0 = performance.now();
  const raw = await (await fetch('/api/graph')).json();
  state.data = raw;
  state.prepared = prepare(raw);
  state.prepared.plates = diskPlates(raw);

  state.viewState = fitView(state.prepared, 35);

  state.deckgl = new Deck({
    parent: el('stage'),
    views: [new OrbitView({ orbitAxis: 'Z', fovy: 50 })],
    viewState: state.viewState,
    controller: { inertia: 250 },
    onViewStateChange,
    getTooltip: ({ index }) => {
      if (index < 0) return null;
      const n = raw.nodes;
      const shadow = n.shadow[index] === 1 ? ' (shadow)' : '';
      return { html: `<b>${n.label[index]}</b>${shadow}<br>` +
                     `<span class="k">${n.kind[index]} · ${n.disk[index]}</span>`,
               style: { background: '#161e29', color: '#e6ecf3',
                        border: '1px solid #2c3849', borderRadius: '4px',
                        fontSize: '12px' } };
    },
    layers: buildLayers(state.prepared),
  });

  updateCounts();
  el('hint').textContent =
    `loaded in ${((performance.now() - t0) / 1000).toFixed(1)}s · drag orbit · scroll zoom`;
  tick();
}

/* Live control: update in place, re-render on the value. The mockup session recorded the
 * opposite -- a settings pane that re-rendered on every `input` event destroyed the native
 * colour picker mid-drag -- so a continuous control must never rebuild the thing it sits
 * in. Only the graph is rebuilt here; the slider is left alone. */
document.getElementById('spread').addEventListener('input', (ev) => {
  const v = parseFloat(ev.target.value);
  document.getElementById('spreadval').textContent = v.toFixed(2) + '\u00d7';
  applySpread(state.prepared, v);
  // Nothing about the camera changed, so keep the frame and just redraw.
  render();
});

document.addEventListener('click', (ev) => {
  const act = ev.target?.dataset?.act;
  if (!act) return;
  if (act === 'bench') return benchmark();
  // Re-fit rather than only re-tilt: a top-down frame and a tilted one need different
  // zooms, because the stack is wide seen from above and tall seen from the side.
  onViewStateChange({ viewState: fitView(state.prepared, act === 'top' ? 90 : 35) });
});

boot();
