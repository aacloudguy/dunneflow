/* The 2.5D stack — the rendering engine, and nothing else.
 *
 * This file used to be the whole page: it owned a header, a mode toggle, a settings pane,
 * a disk menu, a search box, an inspector and a breadcrumb, and it booted itself. All of
 * those exist in the shell as well, which is how the project ended up with two complete
 * applications that had never been joined. **The shell is the application; this is a view
 * inside it.** So everything here that was a shell concern is gone, and what remains is
 * the part nothing else can do: turn a payload into pixels at sixty frames a second.
 *
 * The boundary is drawn at the container. The engine draws inside the element it is handed
 * and touches no DOM outside it -- counts, fps, hints, diagnostics and errors leave as
 * events, because a renderer that writes into `#counts` is a renderer that can only ever
 * live on one page.
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

/* Wrapped: a classic script's top-level declarations are globals, and a global here
 * collides with the same name in the shell. One exported name, no leakage. */
(function () {

const {
  Deck, OrbitView, ScatterplotLayer, LineLayer, TextLayer, PolygonLayer,
  COORDINATE_SYSTEM, CollisionFilterExtension,
} = deck;
const Shading = window.DunneFlowShading;

const CARTESIAN = COORDINATE_SYSTEM.CARTESIAN;

/* ------------------------------------------------------------------ palette --- */

/* Every colour the engine draws with, in one object, replaceable at runtime.
 *
 * It is a parameter rather than a constant because the graph follows the theme, and the
 * theme is the shell's to know: `tokens.css` says no component declares a colour outside
 * that block, and a second hand-kept table here would be exactly that. The defaults below
 * are the dark values the 60 fps figure was measured on, so an engine mounted without a
 * palette still draws what it always drew.
 *
 * `diskS` and `diskL` are the saturation and lightness band the golden-angle disk hues are
 * generated at. They are a band and not a list because there are fifty-two disks and a
 * hand-written palette of fifty-two is a palette nobody maintains. */
const PALETTE = {
  kind: {
    ROUTINE:   [ 45, 212, 191],
    STRUCTURE: [147, 197, 253],
    CONSTANT:  [148, 163, 184],
    BOUNDARY:  [196, 181, 253],
    // A file the program names is not a boundary it touches: naming is a choice the
    // authors made, touching is something the code does. Different act, different colour.
    ARTEFACT:  [251, 191,  36],
  },
  dim:        [ 52,  64,  82],
  dimAlpha:   110,
  edge:       [ 94, 234, 212, 150],
  plateFill:  [ 22,  30,  41,  70],
  plateLine:  [ 44,  56,  73, 140],
  label:      [230, 236, 243, 240],
  labelBg:    [ 11,  17,  25, 200],
  tooltipBg:  '#161e29',
  tooltipText:'#e6ecf3',
  tooltipLine:'#2c3849',
  diskS: 0.62, diskL: 0.58,          // packages
  extS:  0.45, extL:  0.78,          // externals, a cooler paler band
  /* Ambient floor and specular strength for the sphere shading. On a dark ground a ball
   * is lit up out of the background; on a light one it must darken away from the light,
   * and an additive white highlight vanishes. So they are parameters, not constants. */
  ambient: 0.42, diffuse: 0.72, specular: 0.5,
};

function hslToRgb(h, sl, l) {
  const a = sl * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h * 12) % 12;
    return Math.round(255 * (l - a * Math.max(-1, Math.min(k - 3, 9 - k, 1))));
  };
  return [f(0), f(8), f(4)];
}

const DOT_MIN = 1.4;
const DOT_MAX = 3.6;
/* Above this multiplier the dots are big enough that flatness would show, so the sphere
 * shading is switched on. Below it the extra fragment work buys nothing a reader can see.
 * It is a look, not a mode: the same layer, the same draw call, the same buffers. */
const SPHERE_FROM = 2.2;

const DISK_GAP = 190;
const NODE_LABEL_CAP = 250;
const NODE_LABEL_ZOOM = -1.2;

const hexToRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const rgbToHex = (c) => '#' + c.map((v) => v.toString(16).padStart(2, '0')).join('');

/* ------------------------------------------------------------------- state --- */

/* Engine state: what is on screen right now. It is deliberately *not* the reader's
 * settings -- those belong to the application, which pushes the ones the engine needs in
 * through `setOptions`. The split is the whole point of this file: the reader's choices
 * survive a reload and travel between views, and none of that is a renderer's business. */
const g = {
  container: null,
  data: null, prepared: null, deckgl: null,
  viewState: { target: [0, 0, 0], zoom: -4, rotationX: 35, rotationOrbit: 20,
               minZoom: -9, maxZoom: 8 },
  moving: false, stopTimer: 0,
  picks: [],              // [{kind:'disk', id} | {kind:'node', index}] -- ordered
  members: new Set(),
  selGeom: null,
  hiddenLabels: 0,
  benching: false,
  mounted: false,
};

/* The view options the application owns and the engine obeys. Defaults match
 * `settings.js`, which is where their real values live. */
const opts = {
  diskOrder: null,
  diskColors: {},
  colorBy: 'kind',
  filterMode: 'dim',
  direction: 'both',
  nodeSize: 1,
  spread: 0.35,
  showPlates: false,
  scale: 1,               // design rule 3: one multiplier resizes everything, nodes too
};

/* ------------------------------------------------------------------- events --- */

/* The engine says what happened; the application decides what to show. Anything that used
 * to be `el('counts').innerHTML = ...` is one of these. */
const listeners = { select: [], counts: [], fps: [], error: [], ready: [] };

function on(event, fn) {
  if (!(event in listeners)) throw new Error(`DunneFlowGraph: no such event "${event}"`);
  listeners[event].push(fn);
  return () => {
    const i = listeners[event].indexOf(fn);
    if (i >= 0) listeners[event].splice(i, 1);
  };
}

function emit(event, payload) {
  for (const fn of listeners[event]) {
    try { fn(payload); } catch (err) { console.error(`[dunneflow] ${event} listener:`, err); }
  }
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
 * the next thing anyone wants is to see what is left, filling the screen.
 *
 * Measured against the *container*, not the window. As a page of its own those were the
 * same number; inside a three-pane shell they are not, and framing against the window
 * puts the stack partly under the inspector. */
function fitView(d, rotationX = g.viewState.rotationX, subset = null) {
  const b = bounds(d, subset ?? (g.members.size ? g.members : null));
  const t = (rotationX * Math.PI) / 180;
  const vertical = Math.abs(b.height * Math.cos(t)) + Math.abs(2 * b.radius * Math.sin(t));
  const w = g.container?.clientWidth || window.innerWidth;
  const h = g.container?.clientHeight || window.innerHeight;
  const scale = Math.min((w * 0.90) / (2 * b.radius), (h * 0.88) / vertical);
  return { ...g.viewState, target: b.centre, rotationX, zoom: Math.log2(scale) };
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

  /* Every connection, resolved to the nodes that really exist.
   *
   * **A shadow is never drawn and never an endpoint.** It is a placement device: a proxy
   * standing in on a plate so that plate's layout feels the pull of something living
   * elsewhere. Drawing one would put a copy of a routine somewhere it is not, which is a
   * lie about where code lives -- and drawing an edge *to* one would end a real
   * connection at a stand-in.
   *
   * So each crossing, which the model stores twice (once per plate, each copy ending in
   * a shadow), is resolved back to its two real ends and kept once. What is left is the
   * connection the reader is actually after: this routine reaching that one, wherever
   * each of them truly sits. `same` records whether it stays on one plate or spans the
   * stack, because those are drawn differently and counted separately. */
  const linkSeen = new Set();
  const links = [];
  for (let e = 0; e < raw.edges.from.length; e++) {
    const a = raw.edges.from[e], b = raw.edges.to[e];
    const ra = raw.nodes.shadow[a] === 1 ? raw.nodes.real[a] : a;
    const rb = raw.nodes.shadow[b] === 1 ? raw.nodes.real[b] : b;
    if (ra < 0 || rb < 0 || ra === rb) continue;
    const key = ra < rb ? `${ra}:${rb}` : `${rb}:${ra}`;
    if (linkSeen.has(key)) continue;
    linkSeen.add(key);
    links.push([ra, rb, e, raw.nodes.disk[ra] === raw.nodes.disk[rb]]);
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
           links, ranked, haystack, plates: [], diskZ: new Map() };
}

/* ------------------------------------------------------------------ layout --- */

/* Z is a **view property, not a fact**. The server supplies a default order; the reader
 * owns it from then on, which is what makes drag-and-drop reordering, the spread slider
 * and any future shuffling the same single operation. */
function applyLayout(d) {
  const order = opts.diskOrder;
  d.diskZ.clear();
  order.forEach((id, i) => d.diskZ.set(id, (order.length - i) * DISK_GAP * opts.spread));

  for (let i = 0; i < d.n; i++) {
    d.positions[i * 3 + 2] = d.diskZ.get(d.raw.nodes.disk[i]) ?? 0;
  }
  for (const p of d.plates) {
    const z = d.diskZ.get(p.disk.id) ?? 0;
    for (const pt of p.polygon) pt[2] = z;
  }
  d.gpu = null;
  if (g.picks.length) buildSelectionGeometry(d);
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
  if (opts.diskColors[diskId]) return hexToRgb(opts.diskColors[diskId]);
  const i = g.data.disks.findIndex((d) => d.id === diskId);
  const external = g.data.disks[i]?.kind === 'external';
  const hue = ((i < 0 ? 0 : i) * 0.381966) % 1;          // golden angle around the wheel
  return external ? hslToRgb(hue, PALETTE.extS, PALETTE.extL)
                  : hslToRgb(hue, PALETTE.diskS, PALETTE.diskL);
}

function paintNodes(d) {
  /* Colour carries one dimension at a time (design rule 4): either what a thing *is*, or
   * which disk it sits on -- never both at once. Selection state is carried by dimming,
   * a separate channel, so it never competes with either. */
  const byDisk = opts.colorBy === 'disk';
  const hide = opts.filterMode === 'hide';
  const sel = g.members.size ? g.members : null;
  const size = opts.nodeSize * opts.scale;

  for (let i = 0; i < d.n; i++) {
    /* A shadow is never drawn. It exists so a plate's layout can feel the pull of
     * something living elsewhere; putting a dot there would place a copy of a routine
     * somewhere it is not. Zero radius rather than a filtered buffer -- the vertex is
     * degenerate and costs nothing, and keeping one index space means picking, selection
     * and search all stay honest without a translation table between them. */
    if (d.raw.nodes.shadow[i] === 1) {
      d.radii[i] = 0;
      d.colors[i * 4 + 3] = 0;
      continue;
    }
    const out = sel && !sel.has(i);
    let c, a;
    if (out && hide) { c = PALETTE.dim; a = 0; }
    else if (out) { c = PALETTE.dim; a = PALETTE.dimAlpha; }
    else {
      c = byDisk ? diskColor(d.raw.nodes.disk[i])
                 : (PALETTE.kind[d.raw.nodes.kind[i]] || PALETTE.kind.ROUTINE);
      a = 255;
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
  const dir = opts.direction;
  const edges = [];
  if (dir !== 'callees') for (const e of d.inbound.get(index) ?? []) edges.push(e);
  if (dir !== 'callers') for (const e of d.outbound.get(index) ?? []) edges.push(e);
  return edges;
}

function recomputeMembers(d) {
  const m = new Set();
  for (const pick of g.picks) {
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
  g.members = m;
}

function pickKey(p) { return p.kind === 'disk' ? `d:${p.id}` : `n:${p.index}`; }

function togglePick(pick, mode = 'replace') {
  const d = g.prepared;
  const key = pickKey(pick);
  const at = g.picks.findIndex((p) => pickKey(p) === key);
  if (mode === 'replace') {
    g.picks = at >= 0 && g.picks.length === 1 ? [] : [pick];
  } else if (mode === 'remove') {
    if (at >= 0) g.picks.splice(at, 1);
  } else if (at >= 0) {
    g.picks.splice(at, 1);              // 'toggle' and 'add' both drop an existing pick
  } else {
    g.picks.push(pick);
  }
  afterSelectionChange(d);
}

function afterSelectionChange(d) {
  recomputeMembers(d);
  buildSelectionGeometry(d);
  paintNodes(d);
  draw();
  announceSelection();
}

/* One shared selection, three views. The inspector follows the *last node* picked rather
 * than the whole set, because "what is this thing" has one answer and a set of forty-two
 * does not -- while disks stay a set, since the graph's question genuinely is plural.
 * Shadows are resolved to their real node first: a shadow is a placement device and never
 * an endpoint, so inspecting one would show a routine as living somewhere it does not.
 *
 * The engine reports; the shell decides what to do about it. That is what lets one
 * selection drive the graph, the inspector, the breadcrumb and the table without any of
 * them knowing about the others. */
function announceSelection() {
  const last = [...g.picks].reverse().find((p) => p.kind === 'node');
  let node = null;
  if (last) {
    const raw = g.data.nodes;
    const i = raw.shadow[last.index] ? raw.real[last.index] : last.index;
    node = { index: i, id: raw.id[i], label: raw.label[i], disk: raw.disk[i],
             kind: raw.kind[i] };
  }
  const disks = g.picks.filter((p) => p.kind === 'disk').map((p) => ({
    id: p.id, name: g.data.disks.find((x) => x.id === p.id)?.name ?? p.id,
  }));
  emit('select', { picks: g.picks.slice(), node, disks, members: g.members.size });
  announceCounts();
}

function buildSelectionGeometry(d) {
  /* Only the connections the selection actually touches, and every one of them ending at
   * a node that exists. Both ends must be in the selection: picking two plates therefore
   * shows exactly what passes between them, which is the question the stack is for.
   *
   * Two kinds, counted apart because they answer different things. A link that stays on
   * one plate says what a package does among itself. A link that crosses says how the
   * program hangs together -- and those are the ones worth the screen. */
  if (!g.picks.length) { g.selGeom = null; return; }

  const within = [], crossing = [];
  for (const link of d.links) {
    if (!g.members.has(link[0]) || !g.members.has(link[1])) continue;
    (link[3] ? within : crossing).push(link);
  }

  const widthOf = (e) => 0.9 + Math.min(3.0, Math.log2(1 + (d.raw.edges.weight?.[e] ?? 1)));

  const src = new Float32Array(within.length * 3);
  const dst = new Float32Array(within.length * 3);
  const wid = new Float32Array(within.length);
  within.forEach(([a, b, e], k) => {
    for (let ax = 0; ax < 3; ax++) {
      src[k * 3 + ax] = d.positions[a * 3 + ax];
      dst[k * 3 + ax] = d.positions[b * 3 + ax];
    }
    wid[k] = widthOf(e);
  });

  /* Crossings are cut into segments whose colour walks from one plate's colour to the
   * other's. A crossing may pass visually through plates it has nothing to do with, and a
   * single flat colour there is unreadable -- the gradient says which end you are looking
   * at without tracing the line back. `LineLayer` carries one colour per line, so the
   * gradient is made of lines rather than of a shader. */
  const SEG = 10;
  const iSrc = new Float32Array(crossing.length * SEG * 3);
  const iDst = new Float32Array(crossing.length * SEG * 3);
  const iCol = new Uint8Array(crossing.length * SEG * 4);
  const iWid = new Float32Array(crossing.length * SEG);
  let k = 0;
  for (const [a, b, e] of crossing) {
    const ca = diskColor(d.raw.nodes.disk[a]);
    const cb = diskColor(d.raw.nodes.disk[b]);
    const w = widthOf(e);
    for (let seg = 0; seg < SEG; seg++) {
      const t0 = seg / SEG, t1 = (seg + 1) / SEG, tm = (t0 + t1) / 2;
      for (let ax = 0; ax < 3; ax++) {
        const pa = d.positions[a * 3 + ax], pb = d.positions[b * 3 + ax];
        iSrc[k * 3 + ax] = pa + (pb - pa) * t0;
        iDst[k * 3 + ax] = pa + (pb - pa) * t1;
      }
      for (let c = 0; c < 3; c++) iCol[k * 4 + c] = Math.round(ca[c] + (cb[c] - ca[c]) * tm);
      iCol[k * 4 + 3] = 215;
      iWid[k] = w;
      k++;
    }
  }

  g.selGeom = { count: within.length, src, dst, wid,
                interCount: crossing.length, segs: crossing.length * SEG,
                iSrc, iDst, iCol, iWid, gpu: null };
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

function selGpu(sg) {
  if (sg.gpu) return sg.gpu;
  sg.gpu = {
    edges: { length: sg.count, attributes: {
      getSourcePosition: { value: sg.src, size: 3 },
      getTargetPosition: { value: sg.dst, size: 3 },
      getWidth: { value: sg.wid, size: 1 } } },
    inter: { length: sg.segs, attributes: {
      getSourcePosition: { value: sg.iSrc, size: 3 },
      getTargetPosition: { value: sg.iDst, size: 3 },
      getColor: { value: sg.iCol, size: 4, normalized: true },
      getWidth: { value: sg.iWid, size: 1 } } },
  };
  return sg.gpu;
}

function buildLayers(d) {
  const still = !g.moving;
  const layers = [];
  const size = opts.nodeSize * opts.scale;

  if (opts.showPlates) {
    layers.push(new PolygonLayer({
      id: 'plates', data: d.plates, coordinateSystem: CARTESIAN,
      getPolygon: (p) => p.polygon, filled: true, stroked: true, extruded: false,
      getFillColor: PALETTE.plateFill, getLineColor: PALETTE.plateLine, getLineWidth: 1,
      lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: { getPolygon: [opts.spread, opts.diskOrder] },
    }));
  }

  /* One layer, one draw call, whatever the size. Above `SPHERE_FROM` the shading
   * extension turns each disc into a ball -- same buffers, same call, a few extra
   * arithmetic operations per fragment. Real geometry would have cost fifteen thousand
   * mesh instances and a lighting pass for a difference nobody can see. */
  const spheres = size >= SPHERE_FROM;
  layers.push(new ScatterplotLayer({
    id: 'nodes', coordinateSystem: CARTESIAN, data: gpuData(d).nodes,
    radiusUnits: 'pixels', radiusMinPixels: 0, radiusMaxPixels: DOT_MAX * 2 * size,
    pickable: true, autoHighlight: true, highlightColor: [255, 255, 255, 255],
    /* Billboarded: the disc always faces the camera.
     *
     * Without this the circle lies in the plane of its own disk, so tilting the stack
     * foreshortens every node into an ellipse -- and an ellipse does not read as a ball,
     * it reads as a coin seen edge-on. A sphere has no orientation, so a picture of one
     * must not either. At dot sizes nobody notices; the moment the nodes are big enough
     * to be worth looking at, it is the whole illusion.
     *
     * The shading in `shading.js` is computed from the disc's own uv, which is now always
     * screen-facing, so the highlight stays put as the view turns. A real light that
     * moved with the model would be better still and is worth doing later; a fixed one
     * on a billboard is already convincing, and costs nothing. */
    billboard: true,
    extensions: spheres ? [new Shading.SphereShadingExtension({
      ambient: PALETTE.ambient, diffuse: PALETTE.diffuse, specular: PALETTE.specular,
    })] : [],
    updateTriggers: { getFillColor: [opts.colorBy, opts.filterMode] },
    /* No depth writing. A billboard is a flat quad held facing the camera, so two of them
     * at slightly different depths intersect along a straight line -- which renders as a
     * clean slice taken out of a ball and looks like a clipping bug, because it is one.
     * Nodes composite in draw order instead, which is what a graph wants anyway: nothing
     * here is solid, and a node hidden behind another is a node the reader cannot click. */
  }));

  /* Edges are drawn *after* the nodes, so they are never buried.
   *
   * Under them is the conventional order and it fails the moment the size slider is used
   * in anger: at full size the spheres cover every within-plate link, and the map goes
   * quiet exactly when the reader has zoomed in to look at something. Information the
   * reader asked for must not be occluded by decoration they also asked for.
   *
   * The two kinds are guarded separately. Nesting the crossings inside the within-count
   * meant a selection with nothing internal drew nothing at all -- which is precisely the
   * case of two plates that only talk to each other. */
  /* Edges are hidden while the camera moves (rule 19) -- but a benchmark exists to
   * measure the most expensive frame the reader can ask for, and that frame has edges in
   * it. Orbiting with the ordinary gate in force measured nodes only, while the readout
   * still printed the selection's edge count beside the number: a claim about geometry
   * that was never drawn. The override is scoped to the two link layers, so the run
   * isolates edge cost rather than also pulling in the collision-filtered labels. */
  const drawEdges = still || g.benching;
  const sg = g.selGeom && drawEdges ? selGpu(g.selGeom) : null;
  if (sg && g.selGeom.count) {
    layers.push(new LineLayer({
      id: 'sel-edges', coordinateSystem: CARTESIAN, data: sg.edges,
      getColor: PALETTE.edge, widthUnits: 'pixels', pickable: false,
    }));
  }
  if (sg && g.selGeom.interCount) {
    layers.push(new LineLayer({
      id: 'inter-edges', coordinateSystem: CARTESIAN, data: sg.inter,
      widthUnits: 'pixels', pickable: false,
    }));
  }

  if (still && g.viewState.zoom >= NODE_LABEL_ZOOM) {
    const labels = pickLabels(d);
    if (labels.length) {
      layers.push(new TextLayer({
        id: 'node-labels', data: labels, coordinateSystem: CARTESIAN,
        getPosition: (o) => o.pos, getText: (o) => o.text,
        getSize: 11 * opts.scale, sizeUnits: 'pixels', getColor: PALETTE.label,
        getTextAnchor: 'start', getAlignmentBaseline: 'center',
        getPixelOffset: [7, 0], background: true,
        getBackgroundColor: PALETTE.labelBg, backgroundPadding: [3, 1],
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
  const pool = g.members.size
    ? [...g.members].sort((a, b) => d.degree[b] - d.degree[a])
    : d.ranked;
  const cap = Math.min(NODE_LABEL_CAP, pool.length);
  const out = [];
  for (let k = 0; k < cap; k++) {
    const i = pool[k];
    out.push({ pos: [d.positions[i * 3], d.positions[i * 3 + 1], d.positions[i * 3 + 2]],
               text: d.raw.nodes.label[i], priority: d.degree[i] });
  }
  g.hiddenLabels = pool.length - cap;
  return out;
}

/* ------------------------------------------------------------------ motion --- */

function setMoving(moving) {
  if (g.moving === moving) return;
  g.moving = moving;
  draw();
  announceCounts();
}

function onViewStateChange({ viewState }) {
  g.viewState = viewState;
  setMoving(true);
  clearTimeout(g.stopTimer);
  g.stopTimer = setTimeout(() => setMoving(false), 180);
  draw();
}

function draw() {
  if (!g.deckgl || !g.prepared) return;
  g.deckgl.setProps({ layers: buildLayers(g.prepared), viewState: g.viewState });
}

/* What is on screen, and -- design rule 1 -- what is not. Never a silent filter: the
 * excluded count is always stated, in numbers, whichever way the filter is set. */
function announceCounts() {
  if (!g.data) return;
  const s = g.data.stats;
  emit('counts', {
    nodes: s.nodes,
    disks: s.disks,
    selected: g.members.size,
    within: g.selGeom?.count ?? 0,
    crossing: g.selGeom?.interCount ?? 0,
    excluded: s.nodes - g.members.size,
    excludedBy: opts.filterMode === 'hide' ? 'hidden' : 'dimmed',
    hiddenLabels: g.hiddenLabels,
    moving: g.moving && !g.benching,
    names: g.picks.map((p) => p.kind === 'disk'
      ? (g.data.disks.find((x) => x.id === p.id)?.name ?? p.id)
      : g.data.nodes.label[p.index]),
  });
}

/* ---------------------------------------------------------------------- fps --- */

let frames = 0, lastReport = performance.now(), samples = [];
let framesDrawn = 0;
let ticking = false;

function tick() {
  frames++;
  const now = performance.now();
  if (now - lastReport >= 500) {
    const fps = (frames * 1000) / (now - lastReport);
    emit('fps', fps);
    if (g.benching) samples.push(fps);
    frames = 0; lastReport = now;
  }
  requestAnimationFrame(tick);
}

/* Measure the most expensive frame the reader can ask for -- and report the geometry that
 * was actually submitted, which is rule 24. */
function benchmark(seconds = 6) {
  return new Promise((resolve) => {
    samples = []; g.benching = true;
    const t0 = performance.now();
    const start = { ...g.viewState };
    function step() {
      const t = (performance.now() - t0) / 1000;
      if (t >= seconds) {
        g.benching = false;
        samples.sort((a, b) => a - b);
        const med = samples[Math.floor(samples.length / 2)] || 0;
        const worst = samples[0] || 0;
        const within = g.selGeom?.count ?? 0;
        const crossing = g.selGeom?.interCount ?? 0;
        setMoving(false);
        /* 60 is the vsync ceiling, not a measurement of capacity. When median and worst
         * both sit on it the honest statement is "no frames dropped, headroom unknown" --
         * reporting it as a score invites reading a ceiling as a limit. */
        resolve({
          median: med, worst, capped: med >= 59 && worst >= 59,
          nodes: g.data.stats.nodes,
          spheres: opts.nodeSize * opts.scale >= SPHERE_FROM,
          /* Both kinds, because both were drawn. Reporting `count` alone under-stated a
           * run by its crossings -- 2,199 against 4,253 submitted -- which is rule 24
           * surviving in the half of the line the first fix did not touch. They are named
           * separately because they answer different questions, and summing them here
           * would lose that as surely as omitting one did. */
          within, crossing,
        });
        return;
      }
      onViewStateChange({ viewState: { ...start,
        rotationOrbit: start.rotationOrbit + t * 60,
        rotationX: 55 + Math.sin(t) * 20,
        zoom: start.zoom + Math.sin(t * 0.8) * 0.6 } });
      requestAnimationFrame(step);
    }
    step();
  });
}

/* -------------------------------------------------------------- diagnostics --- */

/* On the page, not in a console: "drawn off-screen" and "not drawn" are indistinguishable
 * by looking, and a developer cannot open a console in someone else's browser. */
function diagnostics() {
  const lines = [];
  const canvas = g.container?.querySelector('canvas');
  const gl = canvas && (canvas.getContext('webgl2') || canvas.getContext('webgl'));
  const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');
  lines.push(`canvas ${canvas ? canvas.width + '×' + canvas.height : 'MISSING'}` +
             ` · dpr ${window.devicePixelRatio}`);
  lines.push(`gl ${gl ? 'ok' : 'NONE'}` +
             (dbg ? ` · ${gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL)}` : ''));
  const vp = g.deckgl?.getViewports?.()[0];
  if (vp && g.prepared) {
    const b = bounds(g.prepared, g.members.size ? g.members : null);
    const p = vp.project(b.centre).map(Math.round);
    const inside = p[0] > 0 && p[1] > 0 && p[0] < vp.width && p[1] < vp.height;
    lines.push(`zoom ${g.viewState.zoom.toFixed(2)} · tilt ${Math.round(g.viewState.rotationX)}` +
               ` · centre [${p}] ${inside ? 'ON' : 'OFF'} screen`);
  }
  lines.push(`layers ${g.deckgl?.props?.layers?.length ?? 0} · frames ${framesDrawn}`);
  return lines;
}

/* -------------------------------------------------------------------- mount --- */

function mount(container, raw, options = {}) {
  if (g.mounted) return;
  g.container = container;
  g.data = raw;
  Object.assign(opts, options);

  g.prepared = prepare(raw);
  g.prepared.plates = diskPlates(raw);

  // A saved order from a graph that has since changed must not silently drop disks.
  const ids = new Set(raw.disks.map((d) => d.id));
  const saved = opts.diskOrder;
  const usable = Array.isArray(saved) && saved.length &&
                 saved.every((id) => ids.has(id)) && saved.length === ids.size;
  opts.diskOrder = usable ? saved : defaultOrder(raw);

  g.picks = (options.picks || []).filter((p) =>
    p.kind === 'disk' ? ids.has(p.id) : p.index >= 0 && p.index < g.prepared.n);

  applyLayout(g.prepared);
  recomputeMembers(g.prepared);
  buildSelectionGeometry(g.prepared);
  paintNodes(g.prepared);

  g.viewState = fitView(g.prepared, 35);

  g.deckgl = new Deck({
    parent: container,
    /* Orthographic: under perspective the near plates magnify and the far ones shrink,
     * rendering a stack of equal disks as a tapered cylinder -- the exact shape the model
     * exists not to be. It also makes zoom map world units to pixels exactly. */
    views: [new OrbitView({ orbitAxis: 'Z', orthographic: true })],
    viewState: g.viewState,
    controller: { inertia: 250 },
    onViewStateChange,
    onClick: (info, event) => {
      if (info.index < 0) return;
      const mode = event?.srcEvent?.altKey ? 'remove'
                 : (event?.srcEvent?.shiftKey || event?.srcEvent?.metaKey) ? 'add'
                 : 'replace';
      togglePick({ kind: 'node', index: info.index }, mode);
    },
    getTooltip: ({ index }) => {
      if (index < 0) return null;
      const n = raw.nodes;
      const det = n.detail[index] || {};
      const extra = det.qualname || det.module || det.bkind || '';
      return { html: `<b>${n.label[index]}</b>${n.shadow[index] ? ' (shadow)' : ''}<br>` +
                     `<span class="k">${n.kind[index]} · ${n.disk[index]}</span>` +
                     (extra ? `<br><span class="k">${extra}</span>` : ''),
               style: { background: PALETTE.tooltipBg, color: PALETTE.tooltipText,
                        border: `1px solid ${PALETTE.tooltipLine}`, borderRadius: '4px',
                        fontSize: '12px', padding: '4px 6px' } };
    },
    onError: (err) => {
      /* A blank canvas must say why it is blank (design rule 21). Hardware acceleration
       * switched off gives no WebGL context, and the symptom is an empty page that looks
       * exactly like a broken program. */
      const gpuOff = /Failed to create WebGL context|GL_RENDERER = Disabled/.test(err.message);
      emit('error', { gpuOff, message: err.message });
    },
    onAfterRender: () => { framesDrawn++; },
    layers: buildLayers(g.prepared),
  });

  g.mounted = true;
  window.__deck = g.deckgl; window.__d = g.prepared; window.__graph = g;
  if (!ticking) { ticking = true; tick(); }
  announceSelection();
  emit('ready', { disks: raw.disks, stats: raw.stats });
}

/* ---------------------------------------------------------------------- api --- */

/* Everything the application can ask of the renderer, and nothing about the page it
 * happens to be on. */
window.DunneFlowGraph = {
  mount,
  mounted: () => g.mounted,
  on,

  /* The reader's settings arrive here. Each option says what it invalidates, because
   * repainting everything on a slider drag is how a 60 fps budget is lost. */
  setOptions(partial) {
    const before = { ...opts };
    Object.assign(opts, partial);
    if (!g.prepared) return;
    if (partial.spread !== undefined || partial.diskOrder !== undefined) {
      applyLayout(g.prepared);
    }
    if (partial.direction !== undefined && partial.direction !== before.direction) {
      recomputeMembers(g.prepared);
      buildSelectionGeometry(g.prepared);
    }
    paintNodes(g.prepared);
    draw();
    announceCounts();
  },

  setScale(multiplier) {
    opts.scale = multiplier;
    if (!g.prepared) return;
    paintNodes(g.prepared);
    draw();
  },

  /* The palette is replaced whole, never merged field by field: a half-applied theme is
   * harder to recognise as wrong than a reset one, which is the same argument
   * `settings.js` makes about a version mismatch. */
  setPalette(palette) {
    Object.assign(PALETTE, palette);
    if (!g.prepared) return;
    paintNodes(g.prepared);
    buildSelectionGeometry(g.prepared);   // crossings carry plate colour along their length
    draw();
  },

  setSelection(picks) {
    if (!g.prepared) return;
    g.picks = picks.slice();
    afterSelectionChange(g.prepared);
  },
  togglePick(pick, mode) { if (g.prepared) togglePick(pick, mode); },
  clearSelection() { if (g.prepared) { g.picks = []; afterSelectionChange(g.prepared); } },
  selection: () => g.picks.slice(),
  isSelected: (pick) => g.picks.some((p) => pickKey(p) === pickKey(pick)),

  /* A node the graph does not draw is a real case, not an error: constants can be switched
   * off, and an external whose plate is folded away has no index. The caller is told so
   * and can still show it -- refusing to *show* something because it cannot be *drawn*
   * would make the picture the limit of the map. */
  indexOfId(id) {
    if (!g.data) return -1;
    const raw = g.data.nodes;
    for (let i = 0; i < raw.id.length; i++) {
      if (raw.id[i] === id && !raw.shadow[i]) return i;
    }
    return -1;
  },

  /* The haystack lives with the payload, so matching belongs here; what to do with the
   * hits does not. Returns indices, ranked by degree, plus the true total -- because a
   * capped list that does not say what it capped is a silent filter. */
  search(query, cap = 200) {
    const d = g.prepared;
    const q = String(query).trim().toLowerCase();
    if (!d || !q) return { hits: [], total: 0 };
    const hits = [];
    let total = 0;
    for (let i = 0; i < d.n; i++) {
      if (d.raw.nodes.shadow[i] === 1 || !d.haystack[i].includes(q)) continue;
      total++;
      hits.push(i);
    }
    hits.sort((a, b) => d.degree[b] - d.degree[a]);
    return { hits: hits.slice(0, cap), total };
  },

  node(index) {
    const raw = g.data?.nodes;
    if (!raw || index < 0 || index >= raw.id.length) return null;
    const i = raw.shadow[index] ? raw.real[index] : index;
    return { index: i, id: raw.id[i], label: raw.label[i], kind: raw.kind[i],
             disk: raw.disk[i], detail: raw.detail[i] || {} };
  },

  disks: () => (g.data?.disks ?? []).slice(),
  /* The order actually in force, which is not always the one handed in: a saved
   * order from a graph that has since changed is discarded at mount. */
  diskOrder: () => (opts.diskOrder ?? []).slice(),
  diskColorHex: (id) => rgbToHex(diskColor(id)),
  defaultOrder: () => (g.data ? defaultOrder(g.data) : []),
  stats: () => g.data?.stats ?? null,

  /* Guarded, because these are buttons and a reader can press one while the payload is
   * still arriving. Nine thousand nodes take a moment, the HUD is on screen throughout,
   * and "snap to fit" before the stack exists is an ordinary thing to do -- not an error
   * to throw on. */
  fit(tilt) { if (g.prepared) onViewStateChange({ viewState: fitView(g.prepared, tilt ?? g.viewState.rotationX) }); },
  topDown() { if (g.prepared) onViewStateChange({ viewState: fitView(g.prepared, 90) }); },
  tilt() { if (g.prepared) onViewStateChange({ viewState: fitView(g.prepared, 35) }); },

  /* deck.gl sizes itself to its container, and a container that was `hidden` has no size.
   * Coming back to graph mode needs a nudge or the canvas stays at whatever it was when
   * the shell first laid it out. */
  resize() { if (g.deckgl) { draw(); } },

  benchmark,
  diagnostics,
  SPHERE_FROM,
};

})();
