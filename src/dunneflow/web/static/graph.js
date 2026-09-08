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
 *    selection touches.
 * 3. **They stay up while the camera moves**, and that is a Setting. Hiding them was a
 *    speed measure from a slower renderer; here the geometry is uploaded once and orbiting
 *    re-uploads nothing. A rotation with the links up is how the connections between
 *    plates read as depth rather than as a flat tangle.
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
  Deck, OrbitView, ScatterplotLayer, LineLayer, TextLayer, PolygonLayer, IconLayer,
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
    // The module level's node: one file, standing for everything it declares. Its own
    // colour rather than the routine's, because a file is not a routine -- and measured
    // rather than picked (rule 69): worst separation ΔE 51.7 dark and 42.7 light against
    // the other five, across normal vision, deuteranopia and protanopia.
    MODULE:    [107, 107, 255],
  },
  /* What the comparison says about a node, in the shape `kind` already uses so
     `setPalette`'s merge treats the two the same way.
     **Keyed by tone, not by band.** Which band is drawn in which of the two directional
     tones is the reader's assumption about which version is newer, and that assumption
     belongs to the page rather than to the engine -- it arrives as `opts.changeTone`. Five
     bands and four tones: `edited` and `same` share `quiet`, because "the body changed and
     nothing it does did" is internal computation, which this tool exists not to report. */
  change: {
    gone:      [248, 113, 113],
    new:       [ 74, 222, 128],
    moved:     [167, 139, 250],
    quiet:     [114, 133, 151],
    unclaimed: [ 89, 115, 166],
    // More than one direction of difference in one node, which only the module level can
    // be in. Not part of a colour set -- see `tokens.css`, where the arithmetic is.
    mixed:     [ 71,  71, 245],
  },
  dim:        [ 52,  64,  82],
  dimAlpha:   110,
  edge:       [ 94, 234, 212, 150],
  plateFill:  [ 22,  30,  41,  70],
  plateLine:  [ 44,  56,  73, 140],
  /* The plates a selection touches: context, not content, so quieter than the
   * plates layer proper and quieter still than anything drawn on them. */
  plateTouchFill: [ 45, 212, 191,  16],
  plateTouchLine: [ 45, 212, 191,  70],
  label:      [230, 236, 243, 240],
  labelBg:    [ 11,  17,  25, 200],
  diskS: 0.62, diskL: 0.58,          // packages
  extS:  0.45, extL:  0.78,          // externals, a cooler paler band
  /* Ambient floor and specular strength for the sphere shading. On a dark ground a ball
   * is lit up out of the background; on a light one it must darken away from the light,
   * and an additive white highlight vanishes. So they are parameters, not constants. */
  ambient: 0.42, diffuse: 0.72, specular: 0.5,
  pointer: [251, 191, 36],           // "you are here" -- see `tokens.css` for why amber
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
/* The radius of a plate, in the layout's own units. Hoisted out of `diskPlates` because
 * the pointer stands on this circle: an arrow at the side of the stack has to know where
 * the side is, and two copies of that number is a signpost that drifts off the edge. */
const PLATE_R = 1060;
/* How far the frustum reaches, in view-space units. deck's default is 500 and the stack
 * crosses it at `maxZoom` exactly -- see `mount`, where the measurement is recorded. */
const FAR_PLANE = 5000;
const NODE_LABEL_CAP = 250;
const NODE_LABEL_ZOOM = -1.2;

/* ── the plate as a diagram ──────────────────────────────────────────────────────
 *
 * A box carrying a name, lying flat on the plate its node lives on, for everything the
 * selection has lit. Flat rather than billboarded, which is Tom's call and the opposite of
 * rule 22's decision about the nodes -- and the two do not contradict each other. A sphere
 * has **no orientation**, so a picture of one must not have one either; a labelled box
 * *does* -- it has a top and a reading direction -- and one held facing the camera has
 * stopped being on the plate it belongs to. Held flat it foreshortens with the tilt, which
 * costs 18% of its height at the default 35 degrees and none at all top-down. If that turns
 * out to be the wrong trade the billboard is a one-line change, and it is deliberately not
 * being made until there is a picture to judge.
 *
 * Sized in **pixels**, like the dots and the labels, so a box is readable at any zoom and
 * the reader zooms in to get more of them rather than to make each one bigger. That is what
 * makes the overflow answer work: boxes are placed where they fit and everything else stays
 * a dot, so nothing leaves the picture (rule 19) and the count of what is still a dot is
 * stated (design rule 1).
 */
const BOX_H = 17;                 // one line of 11px text plus its padding, in pixels
const BOX_PAD = 7;                // pixels either side of the text
const BOX_CHAR = 6.2;             // advance of the 11px monospace face the labels use
const BOX_CHARS_MAX = 28;         // past this a name is elided; the card carries it whole
const BOX_GAP = 4;                // pixels between two boxes before they count as touching
/* How many lit nodes are *considered* for a box. Distinct from how many are drawn, which
 * is whatever fits: this bounds the placement work rather than the picture. A plate pick
 * can light 926 and the greedy pass is quadratic in what it has already placed, so the
 * pool is capped busiest-first and the remainder are dots without being measured. */
const BOX_POOL = 600;

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
  // A fit was asked for while the container had no size; owed until it has one.
  fitOwed: false,
  viewState: { target: [0, 0, 0], zoom: -4, rotationX: 35, rotationOrbit: 20,
               minZoom: -9, maxZoom: 8 },
  moving: false, stopTimer: 0,
  picks: [],              // [{kind:'disk', id} | {kind:'node', index}] -- ordered
  members: new Set(),
  selGeom: null,
  /* The view the reader found this selection in, and whether we are still waiting for one.
   * See `rememberWhere()`. Null when nothing is selected, and null while a selection has
   * been made but never yet seen. */
  anchor: null,
  anchorArmed: false,
  anchorRetry: 0,
  hiddenLabels: 0,
  /* Whether the positions on screen came from a solve that tried to line the plates up.
   * A lean means something under a coupled layout and nothing under the spiral, so this
   * decides whether a lean is reported at all rather than how it is worded. */
  coupled: false,
  /* What the last diagram pass drew, and the placement it drew it from.
   *
   * The cache is keyed on the camera and the settings that move a box on screen; it is
   * **cleared** by whoever moves the positions underneath it, rather than by naming every
   * spread, order and collapse in the key. One truth about when it is stale, and the code
   * that invalidates it is the code that caused the staleness (rule 51) -- a key listing
   * the inputs it happens to know about is the shape that goes wrong when a fourth is
   * added beside them. */
  boxCache: null,
  boxCount: 0,
  boxDotted: 0,
  benching: false,
  mounted: false,
};

/* The view options the application owns and the engine obeys. Defaults match
 * `settings.js`, which is where their real values live. */
const opts = {
  diskOrder: null,
  diskColors: {},
  colorBy: 'kind',
  /* id -> status, for `colorBy: 'change'`. Id-keyed rather than an array in this engine's
     index order, following `diskColors` exactly: the shell has no API that would let it
     confirm that order, and a caller asserting an index space it cannot check is how a
     silent mismatch gets built. An id the map does not carry is `unclaimed` -- nothing was
     claimed about it -- which is a different answer from `same`. */
  nodeChange: null,
  /* band -> tone, from `diffWords()`. Here rather than baked into `PALETTE.change` so that
     flipping which version is assumed newer costs this table and not a walk over every
     node -- and so that the engine holds no opinion about which side is which. */
  changeTone: null,
  /* Moves whenever `nodeChange` does, because a deck update trigger is compared by value
     and a mutated map is the same object. */
  changeStamp: 0,
  filterMode: 'dim',
  direction: 'both',
  nodeSize: 1,
  /* Three axes, independent, because they answer different questions. X and Y widen a
   * plate and pull apart nodes that fuse into a solid mass once they are big enough to
   * look at; Z is the gap between plates. There is deliberately no fourth "linked"
   * control: under the orthographic projection this view uses, scaling all three by the
   * same factor *is* zoom, and building a second way to zoom would be a control that
   * duplicates the mouse wheel. */
  spreadX: 1,
  spreadY: 1,
  spreadZ: 0.35,
  plateSize: 1,        // 0 = every plate one width; 1 = area by what it holds
  diagram: false,      // draw what is lit as labelled boxes rather than as dots
  nodeShapes: 'kind',  // 'kind' | 'rect' | 'round' -- a set, never a shape per kind
  /* Close the gap left by a plate nothing is looking at, rather than leaving a hole.
   * Independent of `filterMode`, which decides whether those plates draw at all. */
  collapseUnused: false,
  showPlates: false,
  /* The "you are here" pointer: an arrow standing over every node the reader picked.
   *
   * It exists because a selection of one node in nine thousand is a dot that is lit
   * differently from its neighbours, and "lit differently" is not findable -- the reader
   * has to already know where to look, which is the thing they do not know. Off is a real
   * choice, so it is a Setting; the colour is theirs too, clamped (design rule 6).
   *
   * `pointerColor` null means "whatever the palette says", so a reader who never touches
   * it follows the theme like everything else. */
  pointerShown: true,
  pointerColor: null,
  /* Where the arrow stands. `rim` is at the side of the stack on the node's own bearing,
   * `node` is directly over it. Design rule 2: both are good and usage decides. */
  pointerPlace: 'rim',
  /* The reticule, and the focus it names. See `focusable()`. */
  reticuleShown: true,
  focusLocked: true,
  /* Keeping the links up while the camera turns is what makes a rotation *say* something:
   * relationships are what the stack is for, and stripping them the moment anyone moves
   * hides the thing they are moving to see. It was only ever a performance measure, and on
   * this renderer it is not needed -- the geometry is uploaded once as typed arrays and a
   * turning camera re-uploads nothing. Still a Setting, because a slower machine or a very
   * large selection may want it back. */
  edgesInMotion: true,
  scale: 1,               // design rule 3: one multiplier resizes everything, nodes too
};

/* ------------------------------------------------------------------- events --- */

/* The engine says what happened; the application decides what to show. Anything that used
 * to be `el('counts').innerHTML = ...` is one of these. */
const listeners = { select: [], counts: [], fps: [], error: [], ready: [], hover: [] };

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
  /* `clientWidth` of the container the engine was handed, and the 0.90 is margin -- not a
   * correction for anything sitting on top of the picture.
   *
   * It was once `panels.disks ? 0.60 : 0.90`, because the legend was a 26rem opaque panel
   * floating over the canvas and fit had to be told to aim away from it. That is a fudge
   * kept in sync with a UI state by hand, and when the two applications merged the term
   * was dropped while the panel stayed: fit went on centring the stack across the full
   * container and burying nearly half the subject under the legend. The legend is a grid
   * track now, so `clientWidth` *is* the drawable width and this is plain arithmetic
   * again -- the same reason design rule 20 chose orthographic over perspective.
   *
   * If a factor like that is ever wanted back here, something has gone back to floating
   * over the canvas, and that is the thing to fix instead. */
  /* **A hidden container has no size, and the window is not a substitute for it.**
   *
   * This read `clientWidth || window.innerWidth`, which turns "I cannot measure this" into
   * a confident wrong number: mounted while the pane was hidden, the stack was framed for a
   * 1275px window and drawn into a 496px canvas, so it landed off screen and the graph came
   * up blank. A fallback that produces a plausible measurement is worse than one that
   * refuses -- the same lesson as every other silent substitution in this codebase.
   *
   * So a fit against an unlaid-out container is **deferred**, not guessed: the view state is
   * returned untouched and `resize()` performs it on the first draw that has a size. */
  const w = g.container?.clientWidth || 0;
  const h = g.container?.clientHeight || 0;
  if (!w || !h) {
    g.fitOwed = true;
    return { ...g.viewState, rotationX };
  }
  g.fitOwed = false;
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

  /* The payload's own X and Y, kept unscaled.
   *
   * `positions` is what gets drawn and is rewritten by `applyLayout` on every spread
   * change, so scaling it in place would compound: 2× then 2× again is 4×, and dragging
   * a slider back to 1 would not come home. The base is written once and every spread is
   * computed from it, which makes the operation idempotent and the slider reversible. */
  const baseXY = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) {
    baseXY[i * 2]     = raw.nodes.x[i];
    baseXY[i * 2 + 1] = raw.nodes.y[i];
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

  /* How wide each plate would be drawn if its area meant what it holds: `sqrt(n / nmax)`,
   * so a plate with four times as much in it is twice as wide and the two read as equally
   * dense. `applyLayout` interpolates between this and a uniform 1 -- the ratio is a fact
   * about the payload, the strength is the reader's.
   *
   * **On real nodes, never nodes plus shadows.** A shadow is never drawn (rule 23), so the
   * density a reader actually sees is nodes over area however many placement devices share
   * the disc: `ext:<outside>` carries ten nodes and 378 shadows and has to read as ten.
   * Sizing on the total would make that plate four times too wide and say nothing true.
   *
   * Anchored at the largest plate, so nothing grows past the radius the server placed it
   * at. That anchor is arithmetic rather than a decision to defend: nodes are drawn in
   * pixels and `fitView` frames whatever it is handed, so anchoring at the other end is
   * the same picture at a different zoom -- and under an orthographic projection uniform
   * scaling *is* zoom (design rule 22).
   *
   * A plate holding no drawn node is floored at one rather than collapsed to a point. It
   * still carries shadows, and a plate of radius zero is a plate whose outline and whose
   * rim pointer have nowhere to be. */
  const diskRatio = new Map();
  let biggest = 1;
  for (const k of raw.disks) biggest = Math.max(biggest, k.nodes || 0);
  for (const k of raw.disks) diskRatio.set(k.id, Math.sqrt(Math.max(1, k.nodes || 0) / biggest));

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

  /* The payload's own placement, kept so a reader can come back to it.
   *
   * `baseXY` is the *current* arrangement and the force layout overwrites it; without a
   * copy of what the server sent, turning the setting off would have nothing to return to
   * and the only way back would be a refetch. The payload is the one thing here that is a
   * fact rather than a view, so it is the thing worth keeping. */
  const serverXY = baseXY.slice();

  return { raw, n, positions, baseXY, serverXY, colors, radii, degree, byDisk, inbound,
           outbound, links, ranked, haystack, plates: [], diskZ: new Map(), diskRatio,
           /* What the spiral earns each plate, kept apart from `diskRatio` for the same
            * reason `serverXY` is kept: `diskRatio` is whatever the layout on screen says,
            * and this is what to put back. */
           serverRatio: new Map(diskRatio),
           /* Where each plate's circle is, once a layout has decided. `null` means the
            * server's own placement, where every plate is a disc of `PLATE_R` on the axis
            * and there is nothing to record. */
           circles: null,
           diskScale: new Map(), collapsed: new Set() };
}

/* ------------------------------------------------------------------ layout --- */

/* Z is a **view property, not a fact**. The server supplies a default order; the reader
 * owns it from then on, which is what makes drag-and-drop reordering, the spread slider
 * and any future shuffling the same single operation. */
function applyLayout(d) {
  const order = opts.diskOrder;

  /* Collapsing closes the *gap* a plate leaves; hiding stops its nodes being drawn. They
   * are separate switches because they answer separate questions -- "don't show me that"
   * and "don't leave a hole where it was" -- and the pair is what makes a selection of
   * eight plates out of fifty-two read as eight plates rather than as eight plates
   * scattered down a tower of empty slots.
   *
   * A collapsed plate is only ever one nothing is looking at. With no selection every
   * plate is in play, so nothing collapses and the control quietly does nothing rather
   * than emptying the stack -- the same reasoning as edges being drawn on demand. */
  d.collapsed.clear();
  if (opts.collapseUnused && g.members.size) {
    for (const [id, idx] of d.byDisk) {
      if (!idx.some((i) => g.members.has(i))) d.collapsed.add(id);
    }
  }

  d.diskZ.clear();
  let slot = 0;
  const kept = order.filter((id) => !d.collapsed.has(id));
  order.forEach((id) => {
    if (d.collapsed.has(id)) {
      // Parked on the slot its neighbour takes rather than left at its old height: a
      // collapsed plate is not drawn, but its nodes still carry a position, and one left
      // behind would drag a crossing's endpoint to a place nothing is.
      d.diskZ.set(id, (kept.length - slot) * DISK_GAP * opts.spreadZ);
      return;
    }
    d.diskZ.set(id, (kept.length - slot) * DISK_GAP * opts.spreadZ);
    slot++;
  });

  /* **Plate width, by what the plate holds.** `plateSize` is a strength between the
   * uniform stack (0) and area proportional to content (1), and the interpolation is what
   * makes the dial reversible -- 0 comes home to exactly the arrangement the server sent,
   * for the same reason `baseXY` is kept unscaled at all.
   *
   * It **multiplies** the spread rather than replacing it, and the two answer different
   * questions: spread widens every plate together, this says how much of that width each
   * plate has earned. Both are applied from the base copy, so neither compounds.
   *
   * Every plate is still drawn and nothing is removed, so design rule 1 has nothing to
   * state here -- but the range *is* stated beside the slider, because a stack of plates
   * that differ in width and one whose program differs in shape look the same. */
  const strength = Math.max(0, Math.min(1, opts.plateSize ?? 0));
  d.diskScale.clear();
  for (const [id, ratio] of d.diskRatio) d.diskScale.set(id, 1 + (ratio - 1) * strength);

  /* Three axes, independent. X and Y widen a plate, which is what separates nodes that
   * fuse into a mass at large sizes; Z is the gap between plates. All three moving
   * together is *zoom* -- under an orthographic projection uniform scaling and zoom are
   * the same operation -- so there is no linked slider here, and none is wanted. */
  for (let i = 0; i < d.n; i++) {
    const f = d.diskScale.get(d.raw.nodes.disk[i]) ?? 1;
    d.positions[i * 3]     = d.baseXY[i * 2]     * opts.spreadX * f;
    d.positions[i * 3 + 1] = d.baseXY[i * 2 + 1] * opts.spreadY * f;
    d.positions[i * 3 + 2] = d.diskZ.get(d.raw.nodes.disk[i]) ?? 0;
  }
  for (const p of d.plates) {
    const z = d.diskZ.get(p.disk.id) ?? 0;
    const f = d.diskScale.get(p.disk.id) ?? 1;
    for (const pt of p.polygon) {
      pt[0] = pt.base[0] * opts.spreadX * f;
      pt[1] = pt.base[1] * opts.spreadY * f;
      pt[2] = z;
    }
  }
  d.gpu = null;
  // Every box was placed by projecting a position that has just moved. Rule 51: the code
  // that causes the staleness is the code that clears it.
  g.boxCache = null;
  if (g.picks.length) buildSelectionGeometry(d);
}

function defaultOrder(raw) {
  // Packages above, externals below; within each, biggest nearest the middle.
  const pkgs = raw.disks.filter((d) => d.kind === 'package').sort((a, b) => b.nodes - a.nodes);
  const ext = raw.disks.filter((d) => d.kind === 'external').sort((a, b) => b.nodes - a.nodes);
  return [...pkgs, ...ext].map((d) => d.id);
}

/* The outline of each plate, as a ring of points.
 *
 * **Where the middle is, and how wide, are asked rather than assumed.** Under the spiral
 * every plate is a disc of `PLATE_R` centred on the stack's axis, and three expressions
 * were built on that. Under a coupled force layout the whole stack shares one coordinate
 * frame — which is what lets a routine and its stand-ins hold the same position on every
 * plate they appear on — and a plate then sits wherever its own contents put it. Measured:
 * within 0.023 plate-widths of the axis on average, 0.127 at worst. Small, and not zero,
 * and an outline drawn on the axis regardless is a circle with its own nodes outside it.
 *
 * `circles` is the solver's own record, handed in. Absent for the spiral, where the old
 * assumption is simply true. */
function diskPlates(raw, circles) {
  const SEG = 64;
  return raw.disks.map((disk) => {
    const c = circles && circles.get(disk.id);
    const R = c ? c.r : PLATE_R;
    const cx = c ? c.x : 0, cy = c ? c.y : 0;
    const ring = [];
    for (let k = 0; k <= SEG; k++) {
      const t = (k / SEG) * Math.PI * 2;
      const pt = [cx + Math.cos(t) * R, cy + Math.sin(t) * R, 0];
      // Its own unscaled copy, for the same reason the nodes keep one: the plate must
      // widen with the spread it outlines, and rescaling in place would compound.
      pt.base = [pt[0], pt[1]];
      ring.push(pt);
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
  /* Colour carries one dimension at a time (design rule 4): what a thing *is*, or which
   * disk it sits on, or what a comparison says about it -- never two at once. Selection
   * state is carried by dimming, a separate channel, so it never competes with any of
   * them: dim means *not in your selection* and the hue means *what this is*, and the two
   * never answer the same question.
   *
   * `change` takes the channel over rather than tinting the changed nodes and leaving the
   * rest on plate colour. That was refused deliberately: it puts two meanings in one
   * channel, and a red dot would then mean either *deleted* or *the plate whose
   * golden-angle hue landed on red*. */
  const byDisk = opts.colorBy === 'disk';
  const byChange = opts.colorBy === 'change' && !!opts.nodeChange;
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
      if (byChange) {
        /* An id the map does not carry is `unclaimed`, never `same`. The stack draws
           boundaries, constants, structures and artefacts and the comparison speaks about
           routines only, so "nothing was asked about this" is the answer for more than
           half the nodes -- and it is a different claim from "we looked and found
           nothing" (design rule 1). */
        const band = opts.nodeChange[d.raw.nodes.id[i]];
        const tone = band && opts.changeTone ? opts.changeTone[band] : null;
        c = PALETTE.change[tone || 'unclaimed'] || PALETTE.change.unclaimed;
      } else {
        c = byDisk ? diskColor(d.raw.nodes.disk[i])
                   : (PALETTE.kind[d.raw.nodes.kind[i]] || PALETTE.kind.ROUTINE);
      }
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

/* A shadow is never an endpoint (rule 23), and that applies to *reading* an edge as much
 * as to drawing one.
 *
 * `d.links` resolves every edge back to its two real ends, because the model stores each
 * crossing twice -- once per plate, each copy ending in a shadow. `recomputeMembers` did
 * not: it added `raw.edges.from/to` unresolved, so for a call that leaves the plate it put
 * the **shadow** into the member set instead of the routine the shadow stands in for.
 *
 * Both halves of the selection then failed, quietly and consistently:
 *
 *   - the real neighbour was not a member, so it was never lit;
 *   - `buildSelectionGeometry` requires *both resolved ends* to be members, so the crossing
 *     was skipped -- and crossings are exactly the edges that leave the plate.
 *
 * So picking a routine drew its callers and callees **only where they happened to sit on
 * the same plate**, and a routine whose connections all cross drew as a single unconnected
 * dot. `console_script` has four callers and three callees and drew one node; `guarded_cwd`
 * has eleven connections and drew seven. Nothing reported it, because a selection that
 * genuinely has no neighbours looks identical.
 *
 * This is rule 23 read in the other direction, and the rule already said so in as many
 * words: ending an edge at a stand-in stops a real connection at a stand-in. */
function realIndex(d, i) {
  return d.raw.nodes.shadow[i] === 1 ? d.raw.nodes.real[i] : i;
}

function recomputeMembers(d) {
  const m = new Set();
  for (const pick of g.picks) {
    if (pick.kind === 'disk') {
      for (const i of d.byDisk.get(pick.id) ?? []) m.add(i);
    } else {
      m.add(realIndex(d, pick.index));
      for (const e of neighbours(d, pick.index)) {
        const a = realIndex(d, d.raw.edges.from[e]);
        const b = realIndex(d, d.raw.edges.to[e]);
        if (a >= 0) m.add(a);
        if (b >= 0) m.add(b);
      }
    }
  }
  g.members = m;
}

function pickKey(p) { return p.kind === 'disk' ? `d:${p.id}` : `n:${p.index}`; }

/* May this node be hovered or clicked?
 *
 * With focus locked, only the lit set answers -- the picks and the one hop rule 19 draws
 * around them. The dimmed nine thousand are *context*: rule 19 keeps them on screen so a
 * subset stays legible inside the shape it belongs to, and that is a reason to draw them,
 * not a reason to let them answer questions. A card about a routine the reader did not
 * mean to point at is worse than no card, because it is indistinguishable from one about
 * the routine they did.
 *
 * With nothing selected, everything is focusable. That is not an exception to the rule but
 * the rule read honestly: the lit set is the whole program until someone lights part of
 * it, and a lock that made an empty selection uninteractable would be a mode nobody could
 * get out of by clicking.
 *
 * Not a filter on what is *drawn* -- design rule 1 would demand a count for that, and
 * removing the context is precisely what rule 19 refused to do. */
function focusable(d, i) {
  if (!opts.focusLocked || !g.members.size) return true;
  return g.members.has(realIndex(d, i));
}

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

/* The view the reader **found this in**, kept so they can come back to it.
 *
 * The camera is theirs to move and moving it is not leaving: orbiting, panning and hovering
 * are how the picture gets read, and a reader who has turned the stack around three times
 * has not decided to go anywhere. They have lost the place they were standing, and until
 * this nothing on screen could give it back. Design rule 20's rule -- nothing may strand
 * the reader with no way back -- applied to the reader's *own* framing rather than to the
 * stack's.
 *
 * "Found it in" is not "was looking at when it was selected", and the difference is the
 * whole of why this is two functions. Design rule 26 says picking a routine must never move
 * the camera, so a selection made in the list usually happens while the thing is nowhere on
 * screen -- and a view with the subject outside it is not somewhere anyone wants taking
 * back to. So the anchor is *armed* by a selection and *set* by the first view in which the
 * selection can actually be seen, whether the reader got there by orbiting, by zooming, or
 * by pressing `find it`.
 *
 * Then it stops. The alternative -- keep re-recording while the selection stays visible, so
 * "back" means the last good view rather than the first -- is a real second answer and might
 * be the better one; it is written down here rather than built, because two ways back is a
 * Setting and this does not yet have the use behind it that design rule 2 asks for.
 *
 * `selectionOnScreen()` answers null for "cannot say" -- before there is a viewport at all
 * -- and that must not be read as "no". Rule 42 is that mistake in the guard rather than in
 * the answer, and the two are the same mistake. */
function rememberWhere() {
  if (!g.picks.length) { g.anchor = null; g.anchorArmed = false; return; }
  g.anchor = null;
  g.anchorArmed = true;
  captureWhere();
}

function captureWhere() {
  if (!g.anchorArmed) return;
  const where = selectionOnScreen();
  /* Three answers, not two, and treating the third as a "no" is what made this fail on the
   * commonest path of all: picking a routine in the list *mounts* the graph, and deck has
   * no viewport during the same turn it is constructed in. So the selection was plainly on
   * screen, the question could not be answered yet, and nothing ever asked again -- because
   * the reader had not moved the camera, so no settle came. Ask once more on the next tick
   * when the answer was "cannot say"; a definite "no" needs no retry, since the settle path
   * is exactly what a reader moving to look at it produces. Rule 42's distinction, acted on
   * rather than merely documented. */
  if (!where) {
    if (!g.anchorRetry) {
      g.anchorRetry = setTimeout(() => { g.anchorRetry = 0; captureWhere(); }, 0);
    }
    return;
  }
  if (!where.onScreen) return;
  g.anchor = { ...g.viewState };
  g.anchorArmed = false;
  announceCounts();                            // the button is disabled until this happens
}

function afterSelectionChange(d) {
  recomputeMembers(d);
  /* Strictly after `recomputeMembers`, and it was not, which is the whole of why a
   * selection made in the list armed nothing: `selectionOnScreen()` measures the bounds of
   * `g.members`, so asking it before they are recomputed asks about the *previous*
   * selection. It answered honestly about a question nobody had asked. */
  rememberWhere();
  /* Which plates are in play is a function of the selection, so collapsing has to be
   * recomputed here and not only when a control moves -- otherwise the stack keeps the
   * shape of the *previous* selection while confidently showing the current one.
   * Strictly after `recomputeMembers`, which is what it reads, and it rebuilds the
   * selection geometry itself because every Z it just changed is an edge endpoint. */
  if (opts.collapseUnused) applyLayout(d);
  else buildSelectionGeometry(d);
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
  /* **How many of these stand upright**, measured here and nowhere else.
   *
   * A crossing runs from a real node on one plate to a real node on another. Where both
   * ends sit over the same place, the line is vertical and says *this routine, and that
   * one, in the same position in two different parts of the program*. Where it leans, the
   * two plates want that routine somewhere different and no arrangement satisfies both —
   * which is a fact about the program, not a blemish on the drawing.
   *
   * Measured **in the loop that places the lines**, out of the very coordinates submitted,
   * because rule 24 is rule 13 in a renderer's clothing: a claim about geometry that was
   * never drawn is the defect that rule was written from. Recomputing it in the shell from
   * the payload would be a second answer about the same lines (`plateRangeNote` makes the
   * same argument about plate widths).
   *
   * The lean is in **plate-widths**, so it means the same thing on a plate of 12 nodes and
   * one of 1,519 — and `PLATE_R` is the width the positions were normalised to, so it is
   * the unit already in force rather than a constant chosen here. */
  const UPRIGHT = PLATE_R * 0.25;
  let upright = 0;
  let k = 0;
  for (const [a, b, e] of crossing) {
    const ca = diskColor(d.raw.nodes.disk[a]);
    const cb = diskColor(d.raw.nodes.disk[b]);
    const w = widthOf(e);
    /* Off `baseXY`, not `positions`: the spreads scale X and Y independently and the plate
     * dial scales each plate by its own factor, so a lean measured after them would move
     * when a reader dragged a slider, and the sentence would be about the sliders. */
    if (Math.hypot(d.baseXY[a * 2] - d.baseXY[b * 2],
                   d.baseXY[a * 2 + 1] - d.baseXY[b * 2 + 1]) < UPRIGHT) upright++;
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
                interCount: crossing.length, upright, segs: crossing.length * SEG,
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

/* Which disks the current selection sits on -- itself and its one hop. Module scope
 * because both the layer builder and the public API need it, and a second walk would be a
 * second answer to one question. */
function selectedDisks() {
  const d = g.prepared;
  if (!d || !g.members.size) return [];
  const seen = new Set();
  for (const i of g.members) seen.add(d.raw.nodes.disk[i]);
  return [...seen];
}

function buildLayers(d) {
  const still = !g.moving;
  const layers = [];
  const size = opts.nodeSize * opts.scale;

  /* The plates the selection actually reaches, drawn faintly even when plates are off.
   *
   * Rule 18 says the stack is an abstraction and the plates are not the content, which is
   * why they are not drawn -- at fifteen thousand nodes drawing them all reads as a solid
   * cylinder. That argument is about drawing *all* of them. Drawing the two or three a
   * selection touches is the opposite: it is the only thing on screen that answers "which
   * plate am I looking at", which is otherwise unanswerable because a routine and its
   * callers are dots at heights with nothing to say what a height means.
   *
   * Faint on purpose. The plate is context for the nodes, never a thing competing with
   * them, and a selected plate (the legend's own selection) still reads differently. */
  const touched = new Set(selectedDisks());
  if (!opts.showPlates && touched.size && touched.size < d.plates.length) {
    layers.push(new PolygonLayer({
      id: 'plates-touched', data: d.plates.filter(p => touched.has(p.id)),
      coordinateSystem: CARTESIAN,
      getPolygon: (p) => p.polygon, filled: true, stroked: true, extruded: false,
      getFillColor: PALETTE.plateTouchFill, getLineColor: PALETTE.plateTouchLine,
      getLineWidth: 1, lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: { getPolygon: [opts.spreadX, opts.spreadY, opts.spreadZ,
                                     opts.plateSize, opts.diskOrder, opts.collapseUnused],
                        data: [...touched].join(',') },
    }));
  }

  if (opts.showPlates) {
    layers.push(new PolygonLayer({
      id: 'plates', data: d.plates, coordinateSystem: CARTESIAN,
      getPolygon: (p) => p.polygon, filled: true, stroked: true, extruded: false,
      getFillColor: PALETTE.plateFill, getLineColor: PALETTE.plateLine, getLineWidth: 1,
      lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: { getPolygon: [opts.spreadX, opts.spreadY, opts.spreadZ,
                                      opts.plateSize, opts.diskOrder, opts.collapseUnused] },
    }));
  }

  /* One layer, one draw call, whatever the size. Above `SPHERE_FROM` the shading
   * extension turns each disc into a ball -- same buffers, same call, a few extra
   * arithmetic operations per fragment. Real geometry would have cost fifteen thousand
   * mesh instances and a lighting pass for a difference nobody can see. */
  const spheres = size >= SPHERE_FROM;
  /* The id carries the shading, and that is load-bearing rather than tidy.
   *
   * A layer's shader is assembled once, when its model is built. deck.gl matches an
   * incoming layer to the drawn one **by id** and updates it in place, so a layer that
   * first rendered without the sphere extension -- which is every session, because the
   * default node size is below the threshold -- keeps its plain shader forever. Passing
   * the extension later changed the props and nothing else: `getShaders()` was never
   * asked again, the extension was demonstrably attached, and the nodes stayed flat discs.
   *
   * Changing the id makes it a different layer, so a new model is built and the shader is
   * assembled again. It costs one re-upload of the position, colour and radius buffers,
   * which happens when the reader crosses the size threshold or switches theme -- not per
   * frame, and not while dragging within one side of the threshold.
   *
   * This is the third time the sphere shading has silently done nothing, and all three
   * failed the same way: an unrecognised inject hook, a GLSL name collision, and now a
   * shader that was never reassembled. None of them is an error. Each compiles, draws, and
   * skips the effect -- and each was found only by looking at one node close up. */
  const shadingId = spheres
    ? `-sphere-${PALETTE.ambient}-${PALETTE.diffuse}-${PALETTE.specular}`
    : '';
  layers.push(new ScatterplotLayer({
    id: `nodes${shadingId}`, coordinateSystem: CARTESIAN, data: gpuData(d).nodes,
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
    extensions: spheres ? [Shading.SphereShadingExtension({
      ambient: PALETTE.ambient, diffuse: PALETTE.diffuse, specular: PALETTE.specular,
    })] : [],
    /* `opts.changeStamp` rather than `opts.nodeChange`: deck compares trigger values with
       shallow equality, so a map whose identity has not moved would not fire. `paintNodes`
       setting `d.gpu = null` is the stronger mechanism and does the real work; this is
       belt and braces. */
    updateTriggers: {
      getFillColor: [opts.colorBy, opts.filterMode, opts.changeStamp,
                     opts.changeTone && opts.changeTone.only_base],
    },
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
  /* Whether edges survive a moving camera is now the reader's call, and on by default.
   *
   * Hiding them was a speed measure from a slower renderer. Here everything drawn is
   * uploaded once as flat typed arrays, so orbiting re-uploads nothing and the links cost
   * the same turning as they do still -- and a rotation with the edges up is the whole
   * point of the stack: it is how the connections between plates read as depth rather than
   * as a flat tangle.
   *
   * `benching` still forces them on regardless. A benchmark measures the most expensive
   * frame the reader can ask for, and that frame has edges in it; with the setting off, an
   * orbit would otherwise measure nodes only while the readout printed an edge count beside
   * the number -- a claim about geometry that was never drawn (rule 24). The override stays
   * scoped to the two link layers, so the run isolates edge cost rather than also pulling
   * in the collision-filtered labels. */
  const drawEdges = still || g.benching || opts.edgesInMotion;
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

  /* Drawn after everything, and that is the point of it: a pointer buried behind the
   * geometry it points at would be a signpost facing the wrong way. Same argument as the
   * edges being drawn after the nodes -- information the reader asked for must not be
   * occluded by decoration they also asked for.
   *
   * Not `pickable`: clicking the arrow would have to mean something, and the only honest
   * meaning is "select the node under it", which is what clicking the node already does. */
  if (opts.pointerShown) {
    const pts = pointerData(d);
    if (pts.length) {
      const rgb = opts.pointerColor || PALETTE.pointer;
      const icon = pointerIcon(rgb);
      /* Asked once per draw, not once per pointer, and inside a try because deck asserts
       * from inside `getViewports()` before it has one rather than returning nothing --
       * the same trap `selectionOnScreen()` was written from. */
      let vp = null;
      try { vp = g.deckgl?.getViewports?.()[0] ?? null; } catch { vp = null; }
      for (const o of pts) {
        o.angle = pointerAngle(vp, o);
        /* No angle means no viewport, so nothing can be said about screen directions. The
         * arrow stands on its node pointing down -- true without projecting anything --
         * rather than at the rim aiming somewhere invented. It corrects on the next draw. */
        if (o.angle === null) { o.pos = o.at; o.angle = 0; }
      }
      layers.push(new IconLayer({
        id: `pointers-${icon.id}`, coordinateSystem: CARTESIAN, data: pts,
        getPosition: (o) => o.pos, getIcon: () => icon, getAngle: (o) => o.angle,
        /* `opts.scale` and nothing else: design rule 3 says one multiplier resizes the
         * whole surface together, and a pointer that stayed 26 px while the type and the
         * nodes grew would be the one thing on screen the slider could not reach.
         * Deliberately *not* tied to `nodeSize`: the arrow's job is to be findable, and it
         * is needed most when the nodes are dots. */
        getSize: POINTER_SIZE * opts.scale, sizeUnits: 'pixels',
        /* Clear of what it points at, along the arrow's own line. The apex is the icon's
         * anchor, so this is the only gap that has to be reasoned about; at the rim the
         * gap is world-space distance already and a pixel nudge there would fight the
         * geometry rather than help it. */
        getPixelOffset: (o) => (o.pos === o.at ? [0, -Math.round(4 * opts.scale)] : [0, 0]),
        billboard: true,
        /* Clickable, because an arrow that says "it is over there" and cannot take you
         * there is half a control. The click routes by *layer*, in `onClick` below: an
         * `info.index` from this layer is an index into two dozen pointers and would
         * otherwise be read as a node index -- which is a different node, silently. */
        pickable: true,
        /* Every frame of an orbit changes where these point, so the accessors have to be
         * re-read. The data array is rebuilt per draw anyway -- two dozen items -- and
         * without this deck would keep the first frame's angles and the arrows would swing
         * with the stack instead of staying aimed at it. */
        updateTriggers: { getAngle: pts.map(o => o.angle).join(','),
                          getPosition: opts.pointerPlace },
      }));
    }
  }

  /* The reticule, over everything including the pointers.
   *
   * Rule 19 dims the rest of the program rather than hiding it, which is right -- a subset
   * is only legible inside the shape it belongs to. But dimming answers "what is not mine"
   * and leaves "*which* one is mine" to be inferred from a colour difference among nine
   * thousand dots, with a dimmed node in front of or behind the lit one looking much the
   * same. This says it outright. */
  if (opts.reticuleShown) {
    const marks = pointerData(d);
    if (marks.length) {
      const icon = reticuleIcon(opts.pointerColor || PALETTE.pointer);
      layers.push(new IconLayer({
        id: `reticules-${icon.id}`, coordinateSystem: CARTESIAN, data: marks,
        getPosition: (o) => o.at, getIcon: () => icon,
        // Fixed on screen, not scaled by node size: it identifies rather than decorates,
        // and it is needed most at dot sizes where the nodes are two pixels across.
        getSize: RETICULE_SIZE * opts.scale, sizeUnits: 'pixels',
        billboard: true, pickable: false,
      }));
    }
  }

  /* **The diagram.** Boxes for what is lit, dots for the rest, and the labels below are
   * skipped while it is on -- a name beside a dot and a name inside a box are two answers
   * to one question, and the loose one would sit over the boxes it duplicates.
   *
   * Only when the camera is **still**, for the reason the labels already are: the placement
   * is a screen-space pass over what the selection lit, and running it inside a drag would
   * re-solve a hundred rectangles per frame to draw a picture nobody is reading yet. It is
   * cached on the view state besides, so coming to rest costs one pass and not one per
   * frame after it.
   *
   * Drawn **after** the nodes and before the edges. The dot stays under its box on purpose:
   * it is where the edges terminate, so a box without one would leave every line stopping
   * short of the thing it connects -- and at 1.4 to 3.6 pixels it reads as the anchor it is
   * rather than as a second mark. */
  const boxes = opts.diagram && still ? placeBoxes(d) : null;
  g.boxCount = boxes ? boxes.placed.length : 0;
  g.boxDotted = boxes ? boxes.dotted : 0;
  if (boxes && boxes.placed.length) {
    const unit = Math.pow(2, -g.viewState.zoom);
    const spinDeg = boxSpinDeg();
    const spin = (spinDeg * Math.PI) / 180;
    layers.push(new PolygonLayer({
      id: `boxes-${opts.nodeShapes}`, data: boxes.placed, coordinateSystem: CARTESIAN,
      getPolygon: (b) => boxPolygon(b, unit, spin),
      filled: true, stroked: true, extruded: false,
      getFillColor: PALETTE.labelBg,
      /* The node's own colour, read from the same buffer the dot is painted from, so the
       * box and the dot under it cannot disagree about what the reader chose to colour by
       * (rule 13). A second call to the colour logic here would be a second answer. */
      getLineColor: (b) => [d.colors[b.index * 4], d.colors[b.index * 4 + 1],
                            d.colors[b.index * 4 + 2], 255],
      getLineWidth: 1.2 * opts.scale, lineWidthUnits: 'pixels', pickable: false,
      updateTriggers: {
        getPolygon: [unit, spin, opts.nodeShapes],
        getLineColor: [opts.colorBy, opts.filterMode, opts.changeStamp],
      },
    }));
    layers.push(new TextLayer({
      id: 'box-labels', data: boxes.placed, coordinateSystem: CARTESIAN,
      getPosition: (b) => b.pos, getText: (b) => b.text,
      /* In world units and **not billboarded**, so the text lies on the plate with the box
       * around it. Sized from the same `unit` the outline is, or the two would part company
       * the moment the reader zoomed. */
      getSize: 11 * opts.scale * unit, sizeUnits: 'common',
      getColor: PALETTE.label, billboard: false,
      // The same turn the outline takes, from the one function that decides it.
      getAngle: spinDeg,
      getTextAnchor: 'middle', getAlignmentBaseline: 'center',
      characterSet: 'auto', fontFamily: 'ui-monospace, Menlo, monospace',
      pickable: false,
      updateTriggers: { getSize: [unit, opts.scale], getAngle: [spinDeg] },
    }));
  }

  /* **Zeroed whenever the labels are not drawn**, and that is not tidiness. `pickLabels`
   * is the only writer, and it runs only past the label zoom with the boxes off — so a
   * reader who zoomed in far enough to hide 1,269 names and then zoomed back out left the
   * count standing over a picture with no labels in it at all. The number was announced
   * and read by nothing for as long as that was true, which is how it survived; the moment
   * it became a sentence it became a claim that had to go quiet with its subject. */
  g.hiddenLabels = 0;
  if (still && !boxes && g.viewState.zoom >= NODE_LABEL_ZOOM) {
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

/* ── the "you are here" pointer ─────────────────────────────────────────────────
 *
 * An arrow standing over each node the reader picked, so a selection of one in nine
 * thousand can be *found* rather than merely being lit differently from its neighbours.
 *
 * Drawn as an icon rather than as geometry, for the reason rule 22 gives for the nodes: a
 * billboard is a flat quad held facing the camera, and a picture of something with no
 * orientation must not have one. An arrow that foreshortened as the stack tilted would
 * read as a shape lying on a plate rather than as a pointer at the reader.
 *
 * The shading is baked into the texture rather than done in a shader, and that is the one
 * place this deliberately differs from the nodes. The nodes are fifteen thousand instances
 * of one quad and their shading has to be per-fragment arithmetic; there are at most a
 * couple of dozen pointers, all one colour, so a texture drawn once per colour change is
 * cheaper in every way that matters and is a thing anyone can look at and understand.
 * Tinting with `mask: true` would have been simpler still and throws the shading away --
 * a mask has no colour of its own to shade.
 */
const POINTER_W = 44;
const POINTER_H = 62;
const POINTER_SIZE = 26;            // pixels at scale 1; design rule 3 multiplies it
/* How many pointers are drawn. A thread can select ninety-nine routines at once, and
 * ninety-nine arrows is not a signpost, it is weather. The most recently picked come
 * first, because the last thing clicked is the thing being looked at, and what is left
 * out is stated (design rule 1) -- `announceCounts` carries the number. */
const POINTER_CAP = 24;

/* The reticule: a ring with four ticks, standing on the node the reader is actually
 * researching. Same size at every zoom, because its job is *identification* and a mark that
 * shrinks with the picture stops doing it exactly when the picture gets crowded.
 *
 * Transparent in the middle, so it frames the node rather than replacing it -- the reader
 * has to be able to see the thing they are being pointed at, including its colour and its
 * size relative to its neighbours. */
const RETICULE_PX = 96;
const RETICULE_SIZE = 34;

/* ── the cursor over the picture ──
 *
 * deck.gl's default is a hand -- `grab` over the canvas, `pointer` over anything pickable
 * -- and a hand is the one shape that cannot be used to aim. It is opaque, it is drawn
 * *below and right* of the hotspot on every platform, and at dot sizes the node being
 * aimed at disappears underneath it. The reader is pointing at a 3px dot; the instrument
 * for that is a reticule with a hole in it.
 *
 * **Deliberately not the selection reticule.** That mark is a ring plus four ticks and it
 * means *this is the one you picked*; this one means *this is where you are pointing*, and
 * two marks saying different things must not look alike. So: the ticks alone, no ring.
 * Related enough to read as the same family, different enough that neither can be mistaken
 * for the other when both are on screen at once -- which is the ordinary case, since you
 * hover with something already picked.
 *
 * White over a dark halo, and **not the accent**. Design rule 4 spends colour on one
 * dimension at a time, and the accent is already spent: it is what every pressed control,
 * the navigator's current row and the legend's selected plate use to say *in force*. A
 * cursor is not a state, it is where the hand is. The halo is what makes it legible on
 * both grounds, the same trick and the same reason as `reticuleIcon`.
 *
 * `crosshair` is the fallback and it is a real one, not a formality: if the data URI ever
 * fails to load, the reader gets a thin plus rather than deck.gl's hand back.
 *
 * **It does not scale with the reader's multiplier, and cannot.** A cursor's size is the
 * OS's, so design rule 3 does not reach it -- the second real exception after the media
 * queries of rule 28, and written down here for the same reason: a dimension that looks
 * like a member of the scaling family and is not one is worse than an obvious exception.
 * 32x32 because that is the size every platform honours without argument.
 */
const CURSOR_PX = 32;

function reticuleCursor() {
  const m = CURSOR_PX / 2, inner = 5, outer = 14;
  // Four ticks on the axes, with `inner` of clear space at the centre. The gap is the
  // whole feature: at dot sizes the node is 1.4 to 3.6 pixels across, so a 10px hole
  // leaves it visible with room to spare.
  const ticks = [
    [m, m - outer, m, m - inner], [m, m + inner, m, m + outer],
    [m - outer, m, m - inner, m], [m + inner, m, m + outer, m],
  ];
  const line = ([x1, y1, x2, y2]) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  /* `butt`, not `round`. A round cap on the halo overhangs the tick's inner end by half
   * its width, which quietly eats 1.7px off each side of the gap and makes the clear disc
   * radius 3.3 while every comment and guard here says 5. The selection reticule's ticks
   * are butt for the same reason. */
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${CURSOR_PX}" height="${CURSOR_PX}" ` +
    `viewBox="0 0 ${CURSOR_PX} ${CURSOR_PX}">` +
    `<g stroke="#000" stroke-opacity=".55" stroke-width="3.4" stroke-linecap="butt">` +
    ticks.map(line).join('') + `</g>` +
    `<g stroke="#fff" stroke-width="1.6" stroke-linecap="butt">` +
    ticks.map(line).join('') + `</g></svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}") ${m} ${m}, crosshair`;
}

/* Built once. `_updateCursor` runs on every change of deck's cursor state, so composing
 * the data URI in there would rebuild the same string on every drag frame. */
const CURSOR_RETICULE = reticuleCursor();

const pointerCache = new Map();
const reticuleCache = new Map();

function shade(rgb, f) {
  return rgb.map((c) => Math.max(0, Math.min(255, Math.round(f > 0
    ? c + (255 - c) * f
    : c * (1 + f)))));
}

/* One arrow, drawn once per colour into a canvas and cached.
 *
 * Lit from the upper left, which is where `shading.js` puts the light on the spheres --
 * two light sources in one picture is how a scene stops reading as a scene. The dark
 * outline is not ornament: this must be findable against a pale ground and a near-black
 * one, and a shape that relies on its fill for contrast is legible on exactly one of them. */
function pointerIcon(rgb) {
  const key = rgb.join(',');
  const hit = pointerCache.get(key);
  if (hit) return hit;

  const c = document.createElement('canvas');
  c.width = POINTER_W; c.height = POINTER_H;
  const x = c.getContext('2d');
  const [w, h] = [POINTER_W, POINTER_H];
  const tip = h - 3, headTop = h * 0.52, halfHead = w * 0.42, halfStem = w * 0.15;

  x.beginPath();
  x.moveTo(w / 2, tip);                       // the point, at the bottom, at the node
  x.lineTo(w / 2 - halfHead, headTop);
  x.lineTo(w / 2 - halfStem, headTop);
  x.lineTo(w / 2 - halfStem, 4);
  x.lineTo(w / 2 + halfStem, 4);
  x.lineTo(w / 2 + halfStem, headTop);
  x.lineTo(w / 2 + halfHead, headTop);
  x.closePath();

  const grad = x.createLinearGradient(0, 0, w, h);
  grad.addColorStop(0, `rgb(${shade(rgb, 0.45).join(',')})`);
  grad.addColorStop(0.45, `rgb(${rgb.join(',')})`);
  grad.addColorStop(1, `rgb(${shade(rgb, -0.42).join(',')})`);
  x.fillStyle = grad;
  x.fill();

  x.lineWidth = 2.5;
  x.strokeStyle = 'rgba(0,0,0,0.55)';
  x.stroke();

  // The lit edge, up the left side, so the arrow reads as a solid rather than a sticker.
  x.beginPath();
  x.moveTo(w / 2 - halfStem + 1.5, 6);
  x.lineTo(w / 2 - halfStem + 1.5, headTop);
  x.lineTo(w / 2 - halfHead + 4, headTop);
  x.lineWidth = 1.6;
  x.strokeStyle = `rgba(${shade(rgb, 0.75).join(',')},0.9)`;
  x.stroke();

  /* Did anything actually get drawn? A texture that comes out empty is a pointer that
   * renders perfectly and points at nothing, with no error anywhere -- the exact family of
   * failure the sphere shading produced three times. Sampled rather than scanned: one
   * opaque pixel on the stem is all this needs to know, and it is checked once per colour
   * rather than once per frame. */
  const probe = x.getImageData(Math.round(w / 2), Math.round(h * 0.3), 1, 1).data;
  const blank = probe[3] === 0;
  if (blank) console.error("DunneFlow: the you-are-here pointer drew an empty texture");

  const icon = { url: c.toDataURL(), width: w, height: h, anchorX: w / 2, anchorY: h,
                 mask: false, id: `pointer-${key}`, blank };
  pointerCache.set(key, icon);
  return icon;
}

function reticuleIcon(rgb) {
  const key = rgb.join(',');
  const hit = reticuleCache.get(key);
  if (hit) return hit;

  const c = document.createElement('canvas');
  c.width = RETICULE_PX; c.height = RETICULE_PX;
  const x = c.getContext('2d');
  const m = RETICULE_PX / 2, r = RETICULE_PX * 0.33;
  const stroke = `rgb(${rgb.join(',')})`;

  /* A dark halo under every stroke. The ground is the reader's -- pale or near-black -- and
   * a ring that relies on its own colour for contrast is legible against one of them.
   * Same reasoning as the arrow's outline, and the same two grounds. */
  const ring = (w, colour) => {
    x.beginPath(); x.arc(m, m, r, 0, Math.PI * 2);
    x.lineWidth = w; x.strokeStyle = colour; x.stroke();
  };
  const ticks = (w, colour, from, to) => {
    x.lineWidth = w; x.strokeStyle = colour; x.lineCap = 'butt';
    for (let k = 0; k < 4; k++) {
      const t = (k * Math.PI) / 2;
      x.beginPath();
      x.moveTo(m + Math.cos(t) * from, m + Math.sin(t) * from);
      x.lineTo(m + Math.cos(t) * to, m + Math.sin(t) * to);
      x.stroke();
    }
  };
  ring(7, 'rgba(0,0,0,0.5)');
  ticks(7, 'rgba(0,0,0,0.5)', r * 1.12, r * 1.75);
  ring(3.5, stroke);
  ticks(3.5, stroke, r * 1.12, r * 1.75);

  const probe = x.getImageData(Math.round(m + r), Math.round(m), 1, 1).data;
  const blank = probe[3] === 0;
  if (blank) console.error("DunneFlow: the focus reticule drew an empty texture");

  const icon = { url: c.toDataURL(), width: RETICULE_PX, height: RETICULE_PX,
                 anchorX: m, anchorY: m, mask: false, id: `reticule-${key}`, blank };
  reticuleCache.set(key, icon);
  return icon;
}

/* Where the pointers stand: the nodes the reader *picked*, never the one-hop neighbours
 * those pulled in. The neighbours are the answer; the picks are the question, and an arrow
 * over everything would point at the haystack again.
 *
 * A picked *plate* gets none. A plate is not a place -- pointing at the middle of 645 nodes
 * says nothing about where any of them is, and rule 23 is the same argument for shadows.
 *
 * Two placements, and they are a genuine pair (design rule 2). **Rim** stands the arrow at
 * the side of the stack, at the height of the plate holding the node and on the node's own
 * bearing, so the line through it leads the eye inward: findable from across the whole
 * picture, and never buried in the mass it is pointing into. **Node** stands it directly
 * over the node: exact, and at full node size it can be swallowed by its own neighbours.
 * Rim is the default because finding is the job; usage decides.
 *
 * The rim point is collinear with the origin and the node, and that is not a coincidence
 * worth relying on quietly: plates are circles centred on the axis, and X and Y scale the
 * node and the plate by the same factors, so a bearing taken before the spread survives it.
 * The arrow therefore points *through* its node rather than merely near it. */
function pointerData(d) {
  const out = [];
  for (let k = g.picks.length - 1; k >= 0 && out.length < POINTER_CAP; k--) {
    const p = g.picks[k];
    if (p.kind !== 'node') continue;
    const i = realIndex(d, p.index);     // a shadow is never an endpoint (rules 23, 31)
    if (i < 0 || i >= d.n) continue;
    const at = [d.positions[i * 3], d.positions[i * 3 + 1], d.positions[i * 3 + 2]];
    /* `index` is the whole reason the arrow can be clicked. Rule 30: a control that
     * renders and carries no identity is a control that resolves to nothing, and an arrow
     * knowing only where it stands could take the reader nowhere. */
    out.push({ index: i, at, pos: opts.pointerPlace === 'node' ? at : rimPoint(d, i, at) });
  }
  return out;
}

/* The point on the side of the stack that the node's own bearing passes through.
 *
 * Taken from the *base* coordinates rather than the drawn ones, because the spread turns
 * the plate's circle into an ellipse and the two have to be stretched by the same pair of
 * factors or the arrow stops lining up the moment either slider moves.
 *
 * A node exactly on the axis has no bearing. It gets +X, which is arbitrary and is still a
 * line through the node -- the alternative is no pointer at all for the one node in the
 * program that is hardest to describe the position of. */
function rimPoint(d, i, at) {
  /* **The bearing is taken from the plate's own middle**, which is the origin under the
   * spiral and is not under a coupled force layout — there the whole stack shares one
   * frame and a plate sits where its contents put it. Measured from the origin regardless,
   * the arrow leaves the bearing that makes it point *through* its node: the invariant is
   * that the rim point, the plate's centre and the node are collinear, and the centre is
   * the term that stopped being zero. */
  const c = d.circles && d.circles.get(d.raw.nodes.disk[i]);
  const cx = c ? c.x : 0, cy = c ? c.y : 0;
  const bx = d.baseXY[i * 2] - cx, by = d.baseXY[i * 2 + 1] - cy;
  const t = (bx === 0 && by === 0) ? 0 : Math.atan2(by, bx);
  /* The plate's *own* width, not one radius for all of them. Once a plate's width says
   * what it holds, `PLATE_R` is the width of the largest plate and nothing else -- an
   * arrow placed on that circle for a node on a plate a tenth as wide stands a long way
   * outside the plate it is pointing into, still on the right bearing and no longer on
   * the rim of anything. Rule 51: one number described the whole stack until it did not. */
  const f = d.diskScale.get(d.raw.nodes.disk[i]) ?? 1;
  const R = c ? c.r : PLATE_R;
  return [(cx + Math.cos(t) * R) * opts.spreadX * f,
          (cy + Math.sin(t) * R) * opts.spreadY * f,
          at[2]];
}

/* Which way the arrow points, on screen.
 *
 * A billboard has no world orientation to inherit -- that is the whole of rule 22 -- so
 * pointing at something means computing the direction in *screen* space and rotating the
 * icon by it. Under this projection that is two `project()` calls per pointer and at most
 * two dozen pointers, which is nothing beside a frame that draws ten thousand nodes.
 *
 * `atan2(dx, dy)`, not the usual `atan2(dy, dx)`, and no sign flip. That is read out of
 * deck's own icon shader rather than guessed at, because an arrow aimed the wrong way is a
 * working-looking signpost pointing at nothing, and this is a tab that draws no frames to
 * check it in. The shader rotates by `mat2(cos, -sin, sin, cos)` -- column-major, so
 * `(x cos + y sin, -x sin + y cos)` -- and then flips y. The icon's anchor is its tip and
 * its body runs up the image, so a body point `(0, -h)` lands at `(-h sin, h cos)` in a
 * y-up space; the arrow therefore points along `(sin, cos)` once y is put back down, which
 * is the screen direction from the icon to the thing it aims at. Hence sin = dx, cos = dy.
 *
 * The tip sits *on* the anchor, so at the rim the arrow's point is on the cylinder and its
 * body sticks outward, which is the way round that reads as pointing in.
 *
 * Returns null when there is no viewport to ask -- which is not "straight down", and the
 * caller falls back to standing the arrow on the node, the one placement that needs no
 * projection to be truthful. Rule 42 again: cannot say is its own answer. */
function pointerAngle(vp, item) {
  if (!vp) return null;
  const a = vp.project(item.pos), b = vp.project(item.at);
  const dx = b[0] - a[0], dy = b[1] - a[1];
  if (!dx && !dy) return 0;
  return (Math.atan2(dx, dy) * 180) / Math.PI;
}

function pointerCount() {
  return g.picks.filter((p) => p.kind === 'node').length;
}

/* ── the plate as a diagram ─────────────────────────────────────────────────────
 *
 * Five kinds, five silhouettes, offered as a **set** rather than as a shape per kind --
 * the same decision the colour sets took, and for the same reason: a reader who assigns
 * shapes one at a time can land two kinds on one outline, which is the channel saying
 * nothing, and a sixth kind arrives with no shape at all. `kind` is the set that spends
 * the channel; `rect` and `round` are the two Tom originally asked for, one outline for
 * everything, and they leave kind where it already is, on colour.
 *
 * Shape carrying kind is what frees colour to go on saying *what changed* (design rule 4:
 * colour is the scarcest channel, spend it on one dimension at a time). It is also what a
 * diagram has always done -- these five are Mermaid's own vocabulary, which is the thing
 * the request asked for by name.
 *
 * Returned as a unit outline in [-1, 1] and scaled by the caller, so the shapes are stated
 * once and the sizing is stated once. A shape a set does not name falls back to the
 * rectangle rather than throwing: an unknown kind is a payload this build has not been
 * taught, and drawing it plainly is a better answer than drawing nothing.
 */
const SILHOUETTE = {
  // A routine is a thing that runs: Mermaid's plain process box.
  ROUTINE:   () => [[-1, -1], [1, -1], [1, 1], [-1, 1]],
  // A shape data takes: soft corners, cut rather than curved, because eight points read as
  // rounded at box size and cost a quarter of what an arc costs.
  STRUCTURE: (r = 0.34) => [[-1 + r, -1], [1 - r, -1], [1, -1 + r * 3], [1, 1 - r * 3],
                            [1 - r, 1], [-1 + r, 1], [-1, 1 - r * 3], [-1, -1 + r * 3]],
  // A name pinned to a value: Mermaid's hexagon, `{{ }}`.
  CONSTANT:  () => [[-1 + 0.3, -1], [1 - 0.3, -1], [1, 0], [1 - 0.3, 1], [-1 + 0.3, 1], [-1, 0]],
  // Where it leaves: Mermaid's stadium, `([ ])` -- the shape it spends on start and end.
  BOUNDARY:  () => {
    const out = [];
    for (let k = 0; k <= 8; k++) {
      const t = -Math.PI / 2 + (k / 8) * Math.PI;
      out.push([1 - 0.5 + Math.cos(t) * 0.5, Math.sin(t)]);
    }
    for (let k = 0; k <= 8; k++) {
      const t = Math.PI / 2 + (k / 8) * Math.PI;
      out.push([-1 + 0.5 + Math.cos(t) * 0.5, Math.sin(t)]);
    }
    return out;
  },
  // A file it names: Mermaid's parallelogram, `[/ /]`, which it spends on input and output.
  ARTEFACT:  () => [[-1 + 0.28, -1], [1, -1], [1 - 0.28, 1], [-1, 1]],
  // A file folded whole, at the module altitude. Not one of Mermaid's, and it does not need
  // to be: it stands for many things, so it is a box with a shoulder.
  MODULE:    () => [[-1, -1], [1 - 0.3, -1], [1, -1 + 0.6], [1, 1], [-1, 1]],
};

/* The set is a parameter rather than a read of `opts`, so the key on the Settings page can
 * ask for the outlines of a set the reader is only *considering* — and so that the key and
 * the stack are answered by one function (rule 13). A key drawn from its own copy of these
 * shapes is a second answer to what a kind looks like. */
function silhouette(kind, set = opts.nodeShapes) {
  if (set === 'rect') return SILHOUETTE.ROUTINE();
  if (set === 'round') return SILHOUETTE.STRUCTURE();
  return (SILHOUETTE[kind] ?? SILHOUETTE.ROUTINE)();
}

/* What goes on a box, which is **not** always what goes beside a dot.
 *
 * The name, for every kind, and that is a decision that **changed once shape started
 * carrying kind**. Four of the five are box-sized already: routines, constants, structures
 * and artefacts run a median of 13 to 18 characters and a 99th percentile of 37. A boundary
 * is the exception -- its label is the *expression it touches*, a median of 50 characters
 * and up to 1,388 of embedded Python, because what identifies a boundary is where it goes
 * rather than what it is called.
 *
 * The first version led a boundary box with its kind -- `DATABASE`, `STDIO` -- and that was
 * right while colour was the only thing saying what a node is. It is wrong now: the stadium
 * outline already says *boundary*, so the box would spend its one line repeating the shape
 * while dropping the only thing the shape cannot carry. It says what it touches instead,
 * prefixed by the direction, which shape cannot carry either.
 *
 * Rule 8 forbids truncating at **ingest** and this is not that: the value is recorded whole,
 * stored whole and shown whole one hover away. An ellipsis on a box is the bounded diagram
 * rule 8 explicitly allows, with the complete content sitting beside it.
 */
const BOX_ARROW = { IN: '←', OUT: '→', BOTH: '↔' };

function boxText(d, i) {
  const det = d.raw.nodes.detail[i] || {};
  let text = d.raw.nodes.label[i] || '';
  if (d.raw.nodes.kind[i] === 'BOUNDARY') {
    const arrow = BOX_ARROW[det.direction];
    if (arrow) text = `${arrow} ${text}`;
  }
  return text.length > BOX_CHARS_MAX ? text.slice(0, BOX_CHARS_MAX - 1) + '…' : text;
}

/* Which lit nodes get a box, decided in **screen space** at the zoom in force.
 *
 * Busiest first, and a box is kept only where it does not touch one already placed. That
 * ordering is the same one the layout itself uses -- what a package mostly does ends up
 * where the eye lands first -- so the boxes that survive a crowd are the ones worth reading.
 *
 * Everything not placed stays a **dot**. Nothing leaves the picture, which is rule 19's own
 * argument for dimming rather than hiding, and the number still a dot is stated on the count
 * line, which is design rule 1's. Zooming in spreads the plate in screen space without
 * changing the boxes, so more of them fit -- the reader's way of asking for more detail is
 * the one they already have.
 *
 * Returns null rather than an empty answer when there is no viewport to ask. Rule 42: deck
 * asserts inside `getViewports()` before its first frame, so the guard is a `try` and not an
 * optional chain -- and "cannot say" is a different answer from "nothing fits".
 */
function placeBoxes(d) {
  let vp;
  try {
    vp = g.deckgl?.getViewports?.()[0];
  } catch {
    return null;
  }
  if (!vp || !g.members.size) return null;

  /* Keyed on the **selection**, never on how big it is: two different routines with the
   * same number of neighbours would share a key and the second would be drawn with the
   * first one's boxes -- a confident picture of the wrong thing, which is the failure this
   * whole file keeps finding. `direction` is in it because it decides what a pick lights. */
  const key = [vp.width, vp.height, g.viewState.zoom, g.viewState.rotationX,
               g.viewState.rotationOrbit, (g.viewState.target || []).join(','),
               g.picks.map(pickKey).join(','), opts.direction,
               opts.nodeShapes, opts.scale].join('|');
  if (g.boxCache && g.boxCache.key === key) return g.boxCache.value;

  const pool = [...g.members].sort((a, b) => d.degree[b] - d.degree[a]);
  const considered = Math.min(BOX_POOL, pool.length);
  const scale = opts.scale;
  const half = BOX_H * scale / 2;
  const placed = [];
  const rects = [];
  for (let k = 0; k < considered; k++) {
    const i = pool[k];
    if (i < 0 || i >= d.n) continue;
    const text = boxText(d, i);
    if (!text) continue;
    const w = (text.length * BOX_CHAR + BOX_PAD * 2) * scale;
    const at = vp.project([d.positions[i * 3], d.positions[i * 3 + 1], d.positions[i * 3 + 2]]);
    // Off the canvas is not a reason to say a box was suppressed: it is not competing for
    // room with anything, and counting it would make the readout a claim about the window.
    if (at[0] < -w || at[1] < -half || at[0] > vp.width + w || at[1] > vp.height + half) continue;
    const r = [at[0] - w / 2 - BOX_GAP, at[1] - half - BOX_GAP,
               at[0] + w / 2 + BOX_GAP, at[1] + half + BOX_GAP];
    let clear = true;
    for (let j = 0; j < rects.length; j++) {
      const o = rects[j];
      if (r[0] < o[2] && r[2] > o[0] && r[1] < o[3] && r[3] > o[1]) { clear = false; break; }
    }
    if (!clear) continue;
    rects.push(r);
    placed.push({ index: i, text, halfW: w / 2, halfH: half,
                  kind: d.raw.nodes.kind[i],
                  pos: [d.positions[i * 3], d.positions[i * 3 + 1], d.positions[i * 3 + 2]] });
  }
  const value = { placed, dotted: g.members.size - placed.length };
  g.boxCache = { key, value };
  return value;
}

/* A box's outline in world units, lying flat on its plate and turned to face the reader.
 *
 * Under an orthographic projection one screen pixel is a fixed number of world units --
 * `2 ** -zoom`, which is the same identity `fitView` inverts to frame the stack -- so a box
 * with a pixel size has an exact world size and needs no per-frame fudge. Design rule 20
 * chose orthographic so that framing would be arithmetic rather than a factor that holds at
 * one window size; this is the same dividend, spent on a different question.
 *
 * **Turned about Z by the orbit angle, and that was found by looking.** Built flat and left
 * alone -- which is what was asked for, and rightly: rule 22 billboards a node because a
 * sphere has no orientation, and a labelled box *does* have one, so a box held facing the
 * camera has stopped lying on the plate it belongs to. Flat was tried first to find out
 * whether that mattered. It does, and not where it was expected to: the **tilt** is not the
 * problem -- at 35 degrees a label loses 43% of its height and stays perfectly readable --
 * the **orbit** is. Text lying in the plate inherits the in-plane rotation, so turning the
 * stack twenty degrees turns every label twenty degrees, and looking straight down at a
 * plate gives a page of names set on a diagonal.
 *
 * So the box keeps its plate and gives up only its bearing: rotated about Z alone, it still
 * lies flat, still foreshortens with the tilt, still reads as something *on* a plate, and
 * its reading direction faces the reader at every orbit angle. At orbit zero this is
 * identical to leaving it alone, which is the test that it takes nothing away.
 *
 * This is the whole of the billboard question, answered at the one angle it actually needed
 * answering, and it leaves the other two axes exactly where flat put them. */
function boxPolygon(b, unit, spin) {
  const c = Math.cos(spin), s = Math.sin(spin);
  return silhouette(b.kind).map(([dx, dy]) => {
    const x = dx * b.halfW * unit, y = dy * b.halfH * unit;
    return [b.pos[0] + x * c - y * s, b.pos[1] + x * s + y * c, b.pos[2]];
  });
}

/* The in-plane turn that puts a box's reading direction across the screen.
 *
 * `rotationOrbit` spins the world about Z, so undoing it on the box is what holds the label
 * still while the stack turns underneath it. Degrees out, because that is what `TextLayer`
 * wants for `getAngle`, and radians in `boxPolygon`, because that is what `Math.cos` wants
 * -- stated once here so the outline and the text inside it cannot be turned by different
 * amounts (rule 13, between two layers drawing one object). */
function boxSpinDeg() { return -(g.viewState.rotationOrbit || 0); }

/* The worst lean among one node's crossings, in plate-widths, or `null` if it has none.
 *
 * Computed on demand for one node rather than carried for fifteen thousand — the hover
 * card's own bargain, stated where `onHover` explains why the pop-up is an event and not a
 * tooltip. A node's links are a handful, so this is a few dozen operations.
 *
 * Off `baseXY`, matching `buildSelectionGeometry`: the same measurement in two places has
 * to be the same arithmetic, or the card and the count line disagree about one line on the
 * screen (rule 13). */
function leanOf(d, i) {
  if (!opts.coupled) return null;
  let worst = null;
  for (const link of d.links) {
    if (link[3]) continue;                       // stays on one plate: nothing to lean
    const other = link[0] === i ? link[1] : link[1] === i ? link[0] : -1;
    if (other < 0) continue;
    const lean = Math.hypot(d.baseXY[i * 2] - d.baseXY[other * 2],
                            d.baseXY[i * 2 + 1] - d.baseXY[other * 2 + 1]) / PLATE_R;
    if (worst === null || lean > worst) worst = lean;
  }
  return worst;
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
  /* Once the camera has come to rest, this may be the view the selection is finally
   * visible in -- and that is the one worth keeping. Only on the way to *still*, because
   * every frame of a drag is a view nobody chose. */
  if (!moving) captureWhere();
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
    /* **How many of those crossings stand upright**, and it is a fact about the picture
     * rather than about the program — the same kind as `boxes` and `collapsed` below, and
     * it has to be worded as one (rule 32). `within` and `crossing` count connections in
     * the program; this counts lines on the screen, and two numbers in one sentence that
     * do not agree about what they are is that rule's own defect. Only meaningful under
     * the force layout, which is why nothing states it under the spiral. */
    upright: g.selGeom?.upright ?? 0,
    excluded: s.nodes - g.members.size,
    excludedBy: opts.filterMode === 'hide' ? 'hidden' : 'dimmed',
    // Design rule 1: a plate whose gap has been closed has left the picture, and the
    // reader has no other way to tell a short stack from a small program.
    collapsed: g.prepared?.collapsed.size ?? 0,
    hiddenLabels: g.hiddenLabels,
    /* **What the diagram drew, and what it could not.** Design rule 1: boxes are placed
     * only where they fit, so a plate pick of 926 draws a few dozen and leaves the rest as
     * dots -- and a diagram of forty boxes over a selection of nine hundred looks exactly
     * like a selection of forty. Two numbers because they answer different questions, and
     * rule 32 because each is named after what it counts. */
    boxes: g.boxCount,
    boxesDotted: g.boxDotted,
    /* How many pointers stand in the picture, and how many were asked for. Two numbers
     * because a thread can select ninety-nine routines and only two dozen get an arrow --
     * design rule 1, and rule 32: the number has to say what it counts. */
    pointers: opts.pointerShown ? Math.min(pointerCount(), POINTER_CAP) : 0,
    pointersWanted: opts.pointerShown ? pointerCount() : 0,
    /* Whether there is a view to go back to. The shell disables its own control from this
     * rather than guessing, because "no anchor" and "the anchor is where you already are"
     * are different states and only the engine can tell them apart. */
    anchored: !!g.anchor,
    /* Whether the fog is answering. Design rule 1 in the only form that fits: this removes
     * nothing from the picture, so there is no count to state -- but a reader whose hover
     * has gone quiet over most of the screen is owed the reason, and "it is a mode you
     * turned on" is that reason. */
    focusLocked: opts.focusLocked && g.members.size > 0,
    moving: g.moving && !g.benching,
    edgesInMotion: opts.edgesInMotion,
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
  return new Promise((resolve, reject) => {
    /* A hidden tab gets no animation frames at all -- not throttled, none -- so the run
     * would sit at "benchmarking..." for as long as the reader was looking at something
     * else, and resolve minutes later with a number taken over a window that included the
     * time they were away. Refusing is the only honest answer, and it is the same rule the
     * readout follows: a measurement must measure the thing it names. */
    if (document.visibilityState !== 'visible') {
      reject(new Error('this tab is not visible, so the browser is drawing no frames — '
                     + 'bring the window to the front and run it again'));
      return;
    }
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
  const where = selectionOnScreen();
  if (where) {
    lines.push(`zoom ${g.viewState.zoom.toFixed(2)} · tilt ${Math.round(g.viewState.rotationX)}` +
               ` · centre [${where.at}] ${where.onScreen ? 'ON' : 'OFF'} screen`);
  }
  lines.push(`layers ${g.deckgl?.props?.layers?.length ?? 0} · frames ${framesDrawn}`);
  /* The pointer, on the page, because a texture that came out blank draws nothing and
   * reports nothing -- and this codebase has paid three times for a shader effect that
   * compiled, drew, and silently did nothing. Design rule 21's argument exactly: a
   * developer cannot open a console in someone else's browser, so what cannot be seen has
   * to be stated where the picture is. */
  if (opts.pointerShown) {
    const rgb = opts.pointerColor || PALETTE.pointer;
    const icon = pointerIcon(rgb);
    /* Where the first arrow projects, and which way it points. Design rule 21 asks for
     * exactly this -- where the geometry lands in screen space -- because an arrow drawn
     * off the edge and an arrow not drawn at all are indistinguishable by looking, and at
     * the rim placement the first is a thing that genuinely happens: `fit` frames the
     * selection, and the rim is a plate's width away from it. */
    let vp = null;
    try { vp = g.deckgl?.getViewports?.()[0] ?? null; } catch { vp = null; }
    const first = g.prepared ? pointerData(g.prepared)[0] : null;
    const where = first && vp
      ? ` · at [${vp.project(first.pos).slice(0, 2).map(Math.round)}]` +
        ` ∠${Math.round(pointerAngle(vp, first))}°` +
        ` → node [${vp.project(first.at).slice(0, 2).map(Math.round)}]`
      : '';
    lines.push(`pointer rgb(${rgb}) · ${opts.pointerPlace}` +
               ` · ${Math.min(pointerCount(), POINTER_CAP)} drawn` +
               ` · texture ${icon.blank ? 'BLANK' : `${Math.round(icon.url.length / 1024)} KB`}` +
               where +
               (g.anchor ? ' · anchored' : g.anchorArmed ? ' · waiting for a view of it'
                                                         : ' · no anchor'));
  }
  return lines;
}

/* Where the current selection projects, and whether it is on screen.
 *
 * One function, because two things need the answer: the diagnostics line, and the HUD note
 * that offers to fly to a selection the reader cannot see. Computing it twice is how a
 * readout comes to disagree with the thing beside it -- rule 13's shape, and rule 24's:
 * a claim must be produced by the thing it claims about.
 *
 * Returns null rather than a guess when there is no viewport or no payload yet: "we cannot
 * say" and "it is off screen" are different answers and must not look alike.
 *
 * **The guard has to be a try/catch, and `?.` is not enough.** deck.gl does not return a
 * falsy viewport before it has one -- it asserts *inside* `getViewports()`, so optional
 * chaining protects against a missing `deckgl` and not against the case this was written
 * for. The comment above described the intended behaviour correctly and the code did not
 * achieve it, which is the quietest kind of wrong.
 *
 * It fires on an ordinary path: pick a routine in the navigator before ever opening the
 * graph, and `selectFromNav` mounts the engine and calls `applyWanted()` in the same
 * breath -- synchronously, before deck.gl has rendered a frame and therefore before it has
 * a view manager. The throw propagated out of `applyWanted`, so `persist()`,
 * `recordSelection()` and `render()` after it never ran: the selection happened, the
 * undo stack did not record it, and nothing repainted. */
function selectionOnScreen() {
  let vp;
  try {
    vp = g.deckgl?.getViewports?.()[0];
  } catch {
    return null;                      // no view manager yet; that is "cannot say"
  }
  if (!vp || !g.prepared) return null;
  const b = bounds(g.prepared, g.members.size ? g.members : null);
  const at = vp.project(b.centre).map(Math.round);
  return { at, onScreen: at[0] > 0 && at[1] > 0 && at[0] < vp.width && at[1] < vp.height };
}

/* -------------------------------------------------------------------- mount --- */

/* **Adopting a payload, in one place.** Everything here is a fact about *these arrays*
 * rather than about the page or the canvas -- the prepared buffers, the plate polygons,
 * the id index, which of a saved plate order still applies, which picks still point at
 * something, and where the camera has to be to see it.
 *
 * It is one function because there are now two callers: the first mount, and a change of
 * level. A second setter doing nine tenths of what the first does is rule 68 exactly --
 * `setGroupOpen` did the work and the boot that restored the same state did not -- and the
 * tenth it forgot would be a stale `idIndex`, which is a lookup that answers confidently
 * about a payload that is no longer here.
 *
 * `picks` are filtered rather than carried: an index is a position in *one* payload, so
 * the same number means a different routine in the next one. The shell re-resolves the
 * selection from ids afterwards, which is the only form that survives a swap. */
function adoptPayload(raw, picks) {
  g.data = raw;
  g.idIndex = null;          // a fact about this payload; see `indexOfId`
  g.boxCache = null;         // an index is a position in *one* payload (see `picks` below)

  g.prepared = prepare(raw);
  g.prepared.plates = diskPlates(raw);

  // A saved order from a graph that has since changed must not silently drop disks.
  const ids = new Set(raw.disks.map((d) => d.id));
  const saved = opts.diskOrder;
  const usable = Array.isArray(saved) && saved.length &&
                 saved.every((id) => ids.has(id)) && saved.length === ids.size;
  opts.diskOrder = usable ? saved : defaultOrder(raw);

  g.picks = (picks || []).filter((p) =>
    p.kind === 'disk' ? ids.has(p.id) : p.index >= 0 && p.index < g.prepared.n);

  applyLayout(g.prepared);
  recomputeMembers(g.prepared);
  buildSelectionGeometry(g.prepared);
  paintNodes(g.prepared);

  g.viewState = fitView(g.prepared);

  /* **The diagnostics follow the payload.** These are set for looking at the engine from a
   * console -- design rule 21 puts diagnostics where a developer can reach them, because
   * "drawn off-screen" and "not drawn" are indistinguishable by looking. They were written
   * once in `mount`, so after a change of level `window.__d` went on describing 15,870
   * routine-level rows while the engine drew 2,069 module-level ones: a diagnostic that
   * lies is worse than none, and it cost half an hour of chasing a defect that was not
   * there. Rule 43's family -- an instrument nobody can trust is an instrument nobody
   * reads. */
  window.__d = g.prepared;
  window.__graph = g;
}

/* A different altitude of the same program: 10,015 nodes and 52 plates, or 578 and 38.
 *
 * The camera is **refit** rather than kept, and the tilt is the one in force. The stack is
 * a different size and a different height, so holding the old view state frames the new
 * one at a scale worked out for something else -- which is design rule 20's own reasoning
 * about why a snap-to-fit exists at all. Keeping the tilt keeps the reader's sense of
 * which way they were looking. */
function setPayload(raw) {
  if (!g.mounted) return false;
  adoptPayload(raw, []);
  draw();
  announceSelection();
  announceCounts();
  emit('ready', { disks: raw.disks, stats: raw.stats });
  return true;
}

function mount(container, raw, options = {}) {
  if (g.mounted) return;
  g.container = container;
  Object.assign(opts, options);
  adoptPayload(raw, options.picks);

  g.deckgl = new Deck({
    parent: container,
    /* Orthographic: under perspective the near plates magnify and the far ones shrink,
     * rendering a stack of equal disks as a tapered cylinder -- the exact shape the model
     * exists not to be. It also makes zoom map world units to pixels exactly. */
    /* ── the far plane, and it was the near one for two sessions ──
     *
     * Zooming all the way in used to lose a quarter of the stack. The diagnosis on file
     * said the nodes *nearest* the camera crossed the near plane; that was wrong, and it
     * was wrong in the way a plausible explanation usually is -- it was never measured,
     * only reasoned from the fact that `OrbitView` scales world units by `2 ** zoom` about
     * a target the camera sits a fixed distance from.
     *
     * Measured, by projecting every drawn node through deck's own view-projection and
     * counting the ones whose clip-space z leaves [-1, 1]: **nothing clips anywhere in the
     * range except at `maxZoom` exactly, where 4,063 of 15,869 go past +1** -- the *far*
     * plane, at deck's default of 500. The near plane is never reached at any zoom this
     * view allows. It is a cliff at the very top of the range rather than a gradual onset,
     * which is exactly how it was reported: *"when I zoom in, the clipping cuts in"*.
     *
     * So `far` is raised and `near` is left where it is. That is the whole fix, it costs
     * nothing, and it is measured on both counts that matter: the on-screen scale is
     * identical to the pixel (24,574.8 px per 100 world units at maxZoom either way), and
     * `unproject` round-trips to zero error -- which is the thing that must be checked,
     * because the *previous* attempt at this was a negative `near`.
     *
     * **That attempt is why this comment is long, and it stays a warning.** Under an
     * orthographic projection the frustum is a box rather than a pyramid, so a negative
     * near is geometrically meaningful and looks like the obvious fix. It breaks pan and
     * zoom outright: deck.gl's orbit controller implements both through
     * `viewport.unproject()` -- zoom anchors the point under the cursor, pan drags it --
     * while rotate is angle arithmetic that never unprojects, so exactly the two controls
     * that unproject stop and the one that does not carries on.
     *
     * 5,000 rather than something larger: it clears `maxZoom` with the furthest node at
     * clip-space -0.43, and a far plane pushed to 50,000 puts the whole stack past -0.94,
     * which spends depth precision on nothing. */
    views: [new OrbitView({ orbitAxis: 'Z', orthographic: true, far: FAR_PLANE })],
    viewState: g.viewState,
    controller: { inertia: 250 },
    /* A reticule to aim with, and `grabbing` while the camera is actually being dragged --
     * which is honest, because that gesture genuinely is a grab.
     *
     * **Never keyed on `isHovering`**, and that is a decision rather than an omission. A
     * cursor that changed over a pickable node would be promising *this one will answer*,
     * and with focus locked that promise is false: deck sets `isHovering` from its own
     * picking pass, which knows nothing about `focusable()`, so it is true over a fogged
     * node that the hover handler is about to refuse. A control that says a click will do
     * something when it will not is the failure this codebase keeps paying for.
     *
     * Making it honest is possible -- `onHover` already knows, and could set a flag this
     * reads -- and it would be the visible half of the focus lock. Not built: it is a
     * second feature, and it wants a look at whether a cursor changing shape as the pointer
     * crosses a crowded plate reads as information or as flicker. */
    getCursor: ({ isDragging }) => (isDragging ? 'grabbing' : CURSOR_RETICULE),
    onViewStateChange,
    /* Routed by *layer*, not by index. Two pickable layers now report through one handler,
     * and `info.index` from the pointer layer is an index into two dozen arrows -- read as
     * a node index it would select a different routine, silently and plausibly. Design
     * rule 16's argument one level down: route from a table, and let an unknown case be
     * an error rather than a default that looks deliberate. */
    onClick: (info, event) => {
      if (info.index < 0 || !g.prepared) return;
      if (String(info.layer?.id || '').startsWith('pointers-')) {
        /* The arrow taking the reader to what it points at: select that node alone, then
         * frame it. `setSelection` rather than `togglePick`, because the node the arrow
         * stands over is by definition already picked -- and `replace` on an already-single
         * pick is the deliberate toggle-off (rule 33), so the one control whose whole
         * purpose is *go there* would have cleared the selection instead. */
        const node = info.object;
        if (!node) return;
        g.picks = [{ kind: 'node', index: node.index }];
        afterSelectionChange(g.prepared);
        onViewStateChange({ viewState: fitView(g.prepared) });
        return;
      }
      if (!focusable(g.prepared, info.index)) return;
      const mode = event?.srcEvent?.altKey ? 'remove'
                 : (event?.srcEvent?.shiftKey || event?.srcEvent?.metaKey) ? 'add'
                 : 'replace';
      togglePick({ kind: 'node', index: info.index }, mode);
    },
    /* The pop-up is a `hover` event, not a `getTooltip`.
     *
     * deck.gl's own tooltip returns finished HTML synchronously, which fixes two things
     * this card must not be fixed on. It can only ever say what the payload already holds
     * -- so no touch counts, no governance ids, no WHY, because carrying those for fifteen
     * thousand nodes would charge every node for the handful anybody hovers. And it cannot
     * be filled in two stages, so the moment anything is fetched the card either blocks or
     * flickers.
     *
     * So the engine reports what it knows -- which is everything the picture knows -- and
     * the application decides what to draw and what else to go and ask for. Same boundary
     * as `select`: the engine touches no DOM it was not handed.
     *
     * A shadow is resolved to its real node first. Rule 23 says a shadow is a placement
     * device and never an endpoint, and rule 31 says that applies to *reading* as much as
     * to drawing -- hovering one and being told about "a routine on this plate" would put
     * a routine somewhere it does not live, in the one surface whose whole job is to say
     * what a thing is.
     *
     * **A `shadow` flag travelled with it until 2026-09-08, and nothing could ever set it.**
     * It was here so the card could say "you are pointing at a stand-in", written when a
     * shadow could still be pointed at. It cannot: `prepare` gives one radius 0 and alpha 0,
     * so picking never returns one -- 1,989 picks over 562 distinct nodes returned none --
     * and the rim arrow below resolves through `realIndex` for these same two rules. The
     * resolution stays because it is what makes both of those true from here; the flag went
     * because a field that is always `false` is a claim the card cannot use. */
    onHover: (info) => {
      let i = info.index;
      if (i < 0 || !g.prepared) { emit('hover', null); return; }
      /* Pointing at the arrow says what the arrow points at. It is a control that stands a
       * long way from its subject, and a card naming that subject is how the reader learns
       * the two are connected -- as well as what the arrow will do if they click it. */
      if (String(info.layer?.id || '').startsWith('pointers-')) {
        if (!info.object) { emit('hover', null); return; }
        i = info.object.index;
      } else if (!focusable(g.prepared, i)) {
        /* The fog answers nothing while focus is locked. Silent rather than a card saying
         * "not in your selection": the reader's cursor crosses hundreds of these on the way
         * anywhere, and a message that fires hundreds of times is noise, not information. */
        emit('hover', null);
        return;
      }
      const raw2 = g.data.nodes;
      const real = raw2.shadow[i] ? raw2.real[i] : i;
      emit('hover', {
        index: real, id: raw2.id[real], label: raw2.label[real],
        kind: raw2.kind[real], disk: raw2.disk[real],
        detail: raw2.detail[real] || {},
        /* The fan counts come from here and only from here. The navigator prints the same
         * `3<- 5->` off the same maps, and the selection is drawn from them too, so all
         * three agree by construction. Rule 32 is what happens when they do not. */
        degIn: (g.prepared.inbound.get(real) ?? []).length,
        degOut: (g.prepared.outbound.get(real) ?? []).length,
        /* **How far this routine's plates disagree about where it should be.**
         *
         * A fact about the drawing, like `shadow` above it, and reported the same way: the
         * engine says what the picture knows and the application decides whether to draw a
         * sentence about it. The furthest of this node's crossings, in plate-widths, taken
         * off `baseXY` so a spread slider cannot move it.
         *
         * `null` under the spiral, and that is the honest answer rather than zero: nothing
         * has tried to line anything up there, so a lean is a coincidence and not a
         * measurement of tension. */
        lean: leanOf(g.prepared, real),
        x: info.x, y: info.y,
      });
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
  window.__deck = g.deckgl;
  if (!ticking) { ticking = true; tick(); }
  announceSelection();
  emit('ready', { disks: raw.disks, stats: raw.stats });
}

/* ---------------------------------------------------------------------- api --- */

/* Everything the application can ask of the renderer, and nothing about the page it
 * happens to be on. */
window.DunneFlowGraph = {
  mount,
  /* A different altitude of the same program. Everything payload-derived is rebuilt and
   * the selection is not carried, because a pick is an index into one payload -- the shell
   * re-resolves it from ids, which is the only form that means the same thing in both. */
  setPayload,
  level: () => g.data?.level ?? null,
  mounted: () => g.mounted,
  on,

  /* The reader's settings arrive here. Each option says what it invalidates, because
   * repainting everything on a slider drag is how a 60 fps budget is lost. */
  setOptions(partial) {
    const before = { ...opts };
    Object.assign(opts, partial);
    if (!g.prepared) return;
    if (partial.spreadX !== undefined || partial.spreadY !== undefined ||
        partial.spreadZ !== undefined || partial.plateSize !== undefined ||
        partial.diskOrder !== undefined ||
        partial.collapseUnused !== undefined) {
      applyLayout(g.prepared);
    }
    if (partial.direction !== undefined && partial.direction !== before.direction) {
      recomputeMembers(g.prepared);
      buildSelectionGeometry(g.prepared);
    }
    /* Neither moves a node, so neither relays to `applyLayout` -- but both change which
     * boxes fit, and the placement is cached on a key that cannot see a shape set changing
     * the width of every box on screen. `nodeShapes` is in that key; `diagram` turns the
     * pass on and off and needs no invalidation at all. */
    if (partial.nodeShapes !== undefined) g.boxCache = null;
    if (partial.pointerColor !== undefined || partial.pointerShown !== undefined ||
        partial.focusLocked !== undefined || partial.reticuleShown !== undefined) {
      announceCounts();       // the readout states the pointers and whether focus is on
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

  /* Where a plate's nodes sit, replaced. `null` puts the server's own placement back.
   *
   * **Into `baseXY`, never into `positions`.** `positions` is what is drawn and is
   * rewritten from `baseXY` on every spread change, so writing there would be undone by
   * the next slider and would compound with the one after (the same argument the base copy
   * exists for). Writing the base means the whole existing transform — three spreads, the
   * width dial, collapsed plates, the plate outlines — applies to the new arrangement
   * untouched, and no payload is refetched.
   *
   * The width ratios travel with it. Under the spiral a plate's drawn width is
   * `sqrt(n / nmax)`, a claim about how much it holds; under a force layout the solver has
   * already decided how much room a plate needs, so the ratio it hands back is that answer
   * instead. Same dial, same meaning at both ends — 0 uniform, 1 area proportional to what
   * the layout earned — and a different source for the number in between.
   *
   * `applyLayout` then does everything else, including clearing the box cache, because it
   * is the code that moves a node and rule 51 says that is where the clearing belongs. */
  setPlateXY(xy, circles) {
    const d = g.prepared;
    if (!d) return false;
    if (xy && xy.length !== d.n * 2) return false;
    d.baseXY.set(xy || d.serverXY);
    /* **Where every plate's circle is, or nothing for the server's own placement.** Under
     * the spiral each plate is a disc of `PLATE_R` on the axis and the outline needs no
     * telling; under a coupled layout the stack shares one frame, so the circles are the
     * solver's to report and the renderer's to draw. Rebuilt here rather than scaled,
     * because a plate's *position* changed and not only its width. */
    d.circles = xy ? circles || null : null;
    d.plates = diskPlates(d.raw, d.circles);
    /* Nothing further to scale: under the shared frame the positions already carry how
     * wide each plate came out, so a second factor would apply it twice. The width dial
     * therefore has nothing to say under this layout, and `plateRangeNote` says so rather
     * than leaving a control that moves and changes nothing (design rule 16). */
    d.diskRatio = xy ? new Map([...d.serverRatio.keys()].map((k) => [k, 1]))
                     : new Map(d.serverRatio);
    /* A solved arrangement is one that tried to line the plates up; the server's is not.
     * Set here rather than passed in, because this is the one call that knows which of the
     * two is now on screen. */
    opts.coupled = !!xy;
    applyLayout(d);
    draw();
    announceCounts();
    return true;
  },

  /* The arrangement a caller would have to solve for, so a layout can be computed without
   * the engine having to know what a force is. Returns the payload rather than a copy of
   * the positions: the solver reads `edges.from/to`, which is per plate and shadow-
   * terminated, and is the one edge set that expresses a crossing as a within-plate pull.
   * `links` is the other one and would be the wrong answer (rules 23 and 31). */
  payload: () => (g.data || null),

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

  /* Where the selection is, and whether the reader can see it. The shell offers to fly to
   * it when it cannot; the diagnostics line reads the same function, so the note and the
   * readout beside it cannot come to disagree. */
  selectionOnScreen,

  /* Callers and callees, counted separately.
   *
   * This replaced a single `degree` in the navigator, and the difference is not cosmetic:
   * every other list in the navigator counts *things* -- 14 ways in, 8 packages -- so one
   * bare number beside a routine reads as "how many nodes", and degree is how many *edges*.
   * A routine with 3 callers and 5 callees showed "8" and drew 7 nodes, and there was no
   * way to tell that both were right. Rule 13's family: a number must say what it counts.
   *
   * Counted off the same `inbound`/`outbound` maps the selection uses, so the figure and
   * the picture cannot disagree about what is connected to what. */
  connections(id) {
    const d = g.prepared;
    if (!d) return null;
    const i = this.indexOfId(id);
    if (i < 0) return null;
    return { in: (d.inbound.get(i) ?? []).length, out: (d.outbound.get(i) ?? []).length };
  },

  /* Which plates the current selection actually sits on -- itself and its one hop.
   *
   * "I can't tell which plate I'm viewing" is the commonest thing to be unable to answer
   * about this picture, because plates are an abstraction and are not drawn (rule 18). The
   * members are already computed for drawing; naming their disks costs a walk. */
  selectedDisks,

  /* A node the graph does not draw is a real case, not an error: constants can be switched
   * off, and an external whose plate is folded away has no index. The caller is told so
   * and can still show it -- refusing to *show* something because it cannot be *drawn*
   * would make the picture the limit of the map. */
  /* A map, built once, not a scan.
   *
   * This walked all 15,601 nodes -- 9,874 real and 5,727 shadows -- on every call, which is
   * fine for the handful of lookups it was written for and catastrophic for the one caller
   * that arrived later. Table mode asks it **once per row**: 4,734 rows against 15,601
   * nodes is 73.8 million comparisons, and the table took **2,418 ms** to build. Sorting by
   * Connections asks twice per comparison and is worse by another two orders.
   *
   * Rule 45 exactly, in the engine rather than in a pane: work proportional to the whole
   * program, per row. Reported as *lag that is not obvious* -- and it is not obvious,
   * because a table that takes two and a half seconds to appear looks like a slow page
   * rather than like a defect.
   *
   * Shadows are skipped when the map is built, so a shadow's id never wins over its real
   * node -- rule 23 again, in an index. Invalidated with the payload, since it is a fact
   * about that payload and nothing else. */
  indexOfId(id) {
    if (!g.data) return -1;
    if (!g.idIndex) {
      const raw = g.data.nodes;
      g.idIndex = new Map();
      for (let i = 0; i < raw.id.length; i++) {
        if (!raw.shadow[i] && !g.idIndex.has(raw.id[i])) g.idIndex.set(raw.id[i], i);
      }
    }
    const hit = g.idIndex.get(id);
    return hit === undefined ? -1 : hit;
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
    /* `degree` rides along because the shell's routine list wants "how busy is this" and
     * the count already exists here -- computed once at prepare, off the edge arrays. The
     * alternative is the shell counting edges it does not hold, which is the sort of
     * second implementation that ends up disagreeing with the first. */
    return { index: i, id: raw.id[i], label: raw.label[i], kind: raw.kind[i],
             disk: raw.disk[i], detail: raw.detail[i] || {},
             degree: g.prepared ? g.prepared.degree[i] : 0 };
  },

  /* The outlines a set draws, keyed by kind, for a key beside the control that chooses it.
   * Unit coordinates in [-1, 1]; the caller scales. Read out of the engine rather than
   * redrawn on the page, because a key that keeps its own copy of these shapes is a second
   * answer to what a kind looks like, and the two part company on the day a shape moves. */
  silhouettes: (set) => Object.fromEntries(
    Object.keys(SILHOUETTE).map((k) => [k, silhouette(k, set)])),

  disks: () => (g.data?.disks ?? []).slice(),
  /* The order actually in force, which is not always the one handed in: a saved
   * order from a graph that has since changed is discarded at mount. */
  diskOrder: () => (opts.diskOrder ?? []).slice(),
  diskColorHex: (id) => rgbToHex(diskColor(id)),
  defaultOrder: () => (g.data ? defaultOrder(g.data) : []),
  stats: () => g.data?.stats ?? null,

  /* The widest and narrowest plate actually drawn, as multiples of the widest.
   *
   * Read out of `diskScale` -- the very map `applyLayout` scaled the positions with --
   * rather than recomputed from the disk counts beside it. Rule 13: the number printed
   * beside a control must be produced by the thing it describes, or a clamp, a floor or
   * an interpolation the shell does not know about makes the readout a confident
   * disagreement with the picture. `null` while there is nothing prepared, because "no
   * stack yet" and "every plate one width" are different claims. */
  plateWidths() {
    const d = g.prepared;
    if (!d || !d.diskScale.size) return null;
    const vs = [...d.diskScale.values()];
    return { min: Math.min(...vs), max: Math.max(...vs), plates: vs.length };
  },

  /* Guarded, because these are buttons and a reader can press one while the payload is
   * still arriving. Nine thousand nodes take a moment, the HUD is on screen throughout,
   * and "snap to fit" before the stack exists is an ordinary thing to do -- not an error
   * to throw on. */
  fit(tilt) { if (g.prepared) onViewStateChange({ viewState: fitView(g.prepared, tilt ?? g.viewState.rotationX) }); },

  /* Back to the view this selection was found in.
   *
   * Not `fit`, and the difference is the whole feature. `fit` frames the selection, which
   * is a view nobody chose and which throws away the angle, the distance and the context
   * the reader had arranged around it. This restores the framing they were actually
   * standing in -- their own picture, not a computed one.
   *
   * Returns false when there is nothing to go back to, so the shell can say why rather
   * than offering a control that does nothing (design rule 16). */
  hasAnchor: () => !!g.anchor,
  toAnchor() {
    if (!g.prepared || !g.anchor) return false;
    onViewStateChange({ viewState: { ...g.anchor } });
    return true;
  },
  /* How many pointers are drawn and how many were asked for, so the count beside them can
   * state what it left out rather than quietly showing two dozen of ninety-nine. */
  pointers: () => ({ shown: Math.min(pointerCount(), POINTER_CAP), total: pointerCount() }),
  topDown() { if (g.prepared) onViewStateChange({ viewState: fitView(g.prepared, 90) }); },
  tilt() { if (g.prepared) onViewStateChange({ viewState: fitView(g.prepared, 35) }); },

  /* deck.gl sizes itself to its container, and a container that was `hidden` has no size.
   * Coming back to graph mode needs a nudge or the canvas stays at whatever it was when
   * the shell first laid it out. */
  /* Called when the pane is revealed. If a fit was deferred because the container had no
   * size when it was asked for, this is the first moment it can be answered -- and doing it
   * here rather than always re-fitting is what keeps the reader's camera when they simply
   * switch away and back (design rule 26). */
  resize() {
    if (!g.deckgl) return;
    if (g.fitOwed && g.prepared && g.container?.clientWidth && g.container?.clientHeight) {
      /* Through the same path a drag or a snap takes, so the HUD's readout and the "way
         back" anchor see this exactly as they see any other camera move. A private
         `setProps` here would be a second way the view state changes, and only one of them
         would be watched. */
      onViewStateChange({ viewState: fitView(g.prepared) });
    }
    draw();
  },

  benchmark,
  diagnostics,
  SPHERE_FROM,
};

})();
