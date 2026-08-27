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
  COORDINATE_SYSTEM, CollisionFilterExtension,
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
const EDGE_COLOR   = [ 68,  86, 110,  70];
const CROSS_COLOR  = [125, 211, 252,  70];   // transposition: shadow → its real self
const DISK_FILL    = [ 22,  30,  41, 110];
const DISK_LINE    = [ 44,  56,  73, 200];

/* Labels are capped, and the cap is stated. Fifteen thousand labels is not a picture and
 * not a reading; the cap picks the busiest nodes, and the HUD says how many it hid --
 * design rule 1, no filter is ever silent.
 *
 * There are two label regimes, because there are two questions. Looking at the whole
 * stack the question is "what are these plates", so the plates are named and the nodes
 * are not -- 250 node labels in a 700-pixel overview all collide, and a collision filter
 * doing its job correctly then renders nothing at all, which reads as a bug. Zoomed in,
 * the question is "what is this thing", and the nodes are named. The HUD says which
 * regime is in force so the absence of node labels is never mistaken for their failure. */
const NODE_LABEL_CAP = 250;
const NODE_LABEL_ZOOM = -1.2;     // below this the stack is an overview, not a reading

/* Every disk is drawn the same size, so fifty-one of them at any generous spacing is a
 * column rather than a deck -- and a column is exactly what the stack must not look
 * like, because it hides the one thing the model exists to show. The default fans them
 * close: wide enough to see the plates apart, flat enough to read as cards. */
const DEFAULT_SPREAD = 0.35;

const el = (id) => document.getElementById(id);
const state = {
  data: null, deckgl: null, moving: false, stopTimer: 0,
  viewState: { target: [0, 0, 0], zoom: -4, rotationX: 35, rotationOrbit: 20,
               minZoom: -9, maxZoom: 6 },
  hiddenLabels: 0,
  /* Transpositions are off by default, and that is a correction rather than a
   * preference. Five thousand two hundred lines running the whole height of the stack
   * fill its interior with a solid wash -- frame it a little tighter than the whole
   * silhouette and the screen is simply blue. They are how you follow *one* thread, so
   * they belong to a selection, not to the ambient picture. */
  showTranspositions: false,
  // On until the blank-canvas report is settled, then it goes.
  testPattern: true,
};

/* Frame the whole stack from its actual extent rather than from a guessed constant.
 * The stack's height depends on how many disks a program has -- 51 for Mensores, 14 for
 * DunneFlow -- so any fixed target and zoom is right for exactly one program and shows
 * the others as a speck or from inside. Opening onto nothing is indistinguishable from
 * opening onto a failure. */
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
  // The stack is a cylinder, so measure it as one: a true radius about the axis rather
  // than half the X extent, which would be wrong for any disk that is not a full circle.
  let r = 0;
  for (let i = 0; i < d.n; i++) {
    const dx = d.positions[i * 3] - centre[0], dy = d.positions[i * 3 + 1] - centre[1];
    const h = Math.hypot(dx, dy);
    if (h > r) r = h;
  }
  return { centre, radius: r || 1, height: (hi[2] - lo[2]) || 1 };
}

/* Fit the *bounding cylinder*, at the tilt actually in force.
 *
 * A bounding sphere is rotation-invariant and therefore safe at every angle, but safe by
 * being wrong at nearly all of them: it reserves room for the worst case, so the stack
 * sits small in the frame whichever way it is turned. The stack is a cylinder, and
 * orbiting about Z leaves its footprint a circle -- so the only thing that changes the
 * silhouette is tilt, and that makes a snug fit a two-term formula rather than a guess.
 *
 * Vertical extent goes from the full height seen edge-on to the full diameter seen from
 * above; horizontal extent is the diameter at every angle.
 */
function fitView(d, rotationX = state.viewState.rotationX) {
  const b = bounds(d);
  const t = (rotationX * Math.PI) / 180;
  const vertical = Math.abs(b.height * Math.cos(t)) + Math.abs(2 * b.radius * Math.sin(t));
  const horizontal = 2 * b.radius;
  const margin = 0.88;
  const scale = Math.min(
    (window.innerWidth * margin) / horizontal,
    (window.innerHeight * margin) / vertical,
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
  if (d.diskLabels) for (const l of d.diskLabels) l.pos[2] = l.plate.baseZ * spread;
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

function diskLabels(plates) {
  /* At the rim, not the centre: a disk's centre is where its busiest nodes are, and a
   * name dropped there is unreadable over its own contents. */
  return plates.map((p) => ({
    pos: [1090, 0, p.baseZ],
    text: `${p.disk.name}  ${p.disk.nodes}`,
    plate: p,
  }));
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
      lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: { getPolygon: d.spread },
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

  if (state.testPattern) {
    /* Three large markers at known world positions: the centre of the stack and its two
     * ends. They exist to split one question into two that have different answers.
     *
     * If these draw and the graph does not, WebGL is fine and the fault is in our
     * geometry or scale. If they do not draw either, nothing is reaching the screen and
     * the fault is the context, the canvas, or the driver. A blank canvas cannot tell
     * those apart, and every hour spent staring at one is spent guessing. */
    const b = bounds(d);
    layers.push(new ScatterplotLayer({
      id: 'test-pattern', coordinateSystem: CARTESIAN,
      data: [
        { p: b.centre, c: [255, 0, 200] },
        { p: [b.centre[0], b.centre[1], b.centre[2] + b.height / 2], c: [255, 220, 0] },
        { p: [b.centre[0], b.centre[1], b.centre[2] - b.height / 2], c: [0, 200, 255] },
      ],
      getPosition: (o) => o.p, getFillColor: (o) => o.c,
      getRadius: 26, radiusUnits: 'pixels', radiusMinPixels: 20, pickable: false,
    }));
  }

  if (state.showTranspositions) {
    layers.splice(1, 0, new LineLayer({
      id: 'transpositions', coordinateSystem: CARTESIAN, data: gpu.trans,
      getColor: CROSS_COLOR, getWidth: 1, widthUnits: 'pixels', pickable: false,
    }));
  }

  if (showLabels) {
    layers.push(new TextLayer({
      id: 'disk-labels', data: d.diskLabels, coordinateSystem: CARTESIAN,
      getPosition: (o) => o.pos, getText: (o) => o.text,
      getSize: 12, sizeUnits: 'pixels', getColor: [147, 161, 179, 240],
      getTextAnchor: 'start', getAlignmentBaseline: 'center',
      getPixelOffset: [10, 0], background: true,
      getBackgroundColor: [11, 17, 25, 210], backgroundPadding: [4, 2],
      characterSet: 'auto', fontFamily: 'ui-monospace, Menlo, monospace',
      billboard: true, pickable: false,
    }));
  }

  if (showLabels && state.viewState.zoom >= NODE_LABEL_ZOOM) {
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
      /* Overlapping labels are not a denser reading, they are a grey mat. The collision
       * filter drops the ones that would collide and keeps the higher-priority label --
       * priority here is degree, so what survives a crowded patch is its busiest node. */
      extensions: [new CollisionFilterExtension()],
      collisionEnabled: true,
      collisionTestProps: { sizeScale: 1.6 },
      getCollisionPriority: (o) => o.priority,
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
               text: d.raw.nodes.label[i], priority: d.degree[i] });
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
  let hidden;
  if (state.moving) {
    hidden = 'labels off while moving';
  } else if (state.viewState.zoom < NODE_LABEL_ZOOM) {
    hidden = `disk names only \u2014 zoom in to name nodes (${s.drawn_nodes.toLocaleString()} unlabelled)`;
  } else {
    hidden = state.hiddenLabels
      ? `${state.hiddenLabels.toLocaleString()} node labels hidden by cap and collision`
      : 'all node labels shown';
  }
  el('counts').innerHTML =
    `${s.drawn_nodes.toLocaleString()} drawn · ${s.edges.toLocaleString()} edges · ` +
    `${s.disks} disks<br><span class="muted">${hidden}</span>`;
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

/* -------------------------------------------------------------- diagnostics --- */

/* Everything needed to tell "drawn off-screen" apart from "not drawn", printed on the
 * page. A blank canvas has many causes and they are indistinguishable by looking at it;
 * the one thing that separates them is where the geometry landed in screen space, so
 * that is computed and shown rather than described.
 */
function diagnose() {
  const lines = [];
  const canvas = document.querySelector('#stage canvas');
  const gl = canvas && (canvas.getContext('webgl2') || canvas.getContext('webgl'));
  const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');
  lines.push(`canvas ${canvas ? canvas.width + '\u00d7' + canvas.height : 'MISSING'}` +
             ` · css ${window.innerWidth}\u00d7${window.innerHeight} · dpr ${window.devicePixelRatio}`);
  lines.push(`gl ${gl ? 'ok' : 'NONE'}` +
             (dbg ? ` · ${gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)}` : ''));

  const vp = state.deckgl?.getViewports?.()[0];
  if (vp) {
    const b = bounds(state.prepared);
    const probe = [b.centre,
                   [b.centre[0], b.centre[1], b.centre[2] + b.height / 2],
                   [b.centre[0], b.centre[1], b.centre[2] - b.height / 2]];
    const on = probe.map((w) => vp.project(w).map(Math.round));
    lines.push(`viewport ${Math.round(vp.width)}\u00d7${Math.round(vp.height)}` +
               ` · zoom ${state.viewState.zoom.toFixed(2)} · tilt ${Math.round(state.viewState.rotationX)}`);
    lines.push(`centre \u2192 [${on[0]}] · top \u2192 [${on[1]}] · base \u2192 [${on[2]}]`);
    const inside = on.some(([x, y]) => x > 0 && y > 0 && x < vp.width && y < vp.height);
    lines.push(inside ? 'geometry projects ON screen' : 'geometry projects OFF screen');
  } else {
    lines.push('no viewport — deck did not initialise');
  }
  lines.push(`layers ${state.deckgl?.props?.layers?.length ?? 0}` +
             ` · nodes ${state.prepared?.n ?? 0} · frames ${framesDrawn}`);
  el('diag').innerHTML = lines.join('<br>');
}

/* --------------------------------------------------------------------- boot --- */

async function boot() {
  const t0 = performance.now();
  const raw = await (await fetch('/api/graph')).json();
  state.data = raw;
  state.prepared = prepare(raw);
  state.prepared.plates = diskPlates(raw);
  state.prepared.diskLabels = diskLabels(state.prepared.plates);

  applySpread(state.prepared, DEFAULT_SPREAD);
  state.viewState = fitView(state.prepared, 35);

  state.deckgl = new Deck({
    parent: el('stage'),
    /* Orthographic, not perspective. Two reasons, and the first is the one that
     * matters: under perspective the near plates are magnified and the far ones shrink,
     * so a stack of equal disks renders as a tapered cylinder -- which is precisely the
     * shape the model is trying not to be. The second is that orthographic zoom maps
     * world units to pixels exactly, so framing the stack is arithmetic rather than a
     * fudge factor that holds at one window size. */
    views: [new OrbitView({ orbitAxis: 'Z', orthographic: true })],
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
    onError: (err) => {
      /* A raw driver string is a fact, not an answer. The one failure a reader will
       * actually hit is a browser with hardware acceleration switched off -- the canvas
       * then stays blank with no clue that the cause is a setting rather than the
       * program -- so that case is named and the remedy is given. Same discipline as a
       * finding stating its blind spot: say what would make this go away. */
      const gpuOff = /Failed to create WebGL context|GL_RENDERER = Disabled/.test(err.message);
      el('err').innerHTML = gpuOff
        ? '<b>This browser cannot draw.</b> Hardware acceleration is off, so no page ' +
          'here can get a WebGL context \u2014 nothing to do with your machine.<br>' +
          'Turn it on at <code>chrome://settings/system</code> ' +
          '(&ldquo;Use graphics acceleration when available&rdquo;), then relaunch Chrome. ' +
          '<code>chrome://gpu</code> says why it is off. Safari works today without changing anything.' +
          `<br><span class="muted">${err.message}</span>`
        : `deck.gl: ${err.message}`;
      el('err').hidden = false;
    },
    onAfterRender: () => { framesDrawn++; },
  });

  // Handles for headless inspection; harmless, and the alternative is guessing.
  window.__deck = state.deckgl; window.__d = state.prepared; window.__state = state;
  setTimeout(diagnose, 1500);
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

document.getElementById('test').addEventListener('change', (ev) => {
  state.testPattern = ev.target.checked;
  render();
});

document.getElementById('trans').addEventListener('change', (ev) => {
  state.showTranspositions = ev.target.checked;
  render();
});

document.addEventListener('click', (ev) => {
  const act = ev.target?.dataset?.act;
  if (!act) return;
  if (act === 'bench') return benchmark();
  // `fit` keeps the angle you are looking from and only re-frames; the view buttons
  // choose an angle and re-frame for it. Re-framing is not optional either way: the
  // stack is wide seen from above and tall seen from the side, so a tilt without a
  // re-fit walks straight off the edge of the screen.
  const tilt = act === 'top' ? 90 : act === 'tilt' ? 35 : state.viewState.rotationX;
  onViewStateChange({ viewState: fitView(state.prepared, tilt) });
});

document.addEventListener('keydown', (ev) => {
  if (ev.key === 'f' && !ev.metaKey && !ev.ctrlKey && state.prepared) {
    onViewStateChange({ viewState: fitView(state.prepared) });
  }
});

boot();
