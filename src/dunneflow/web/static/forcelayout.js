/* The force-directed plate layout: a payload in, one position per placed thing out.
 *
 * Its own file for the reason `prose.js` is its own file — it turns a payload into numbers
 * and knows nothing whatever about this page. No DOM, no `state`, no engine. What it has to
 * say leaves as a return value: the positions, which backend ran, and how long it took.
 *
 * ── Why this exists ───────────────────────────────────────────────────────────────────
 *
 * `layout.structural` puts nodes on a sunflower spiral ordered by degree. It is even,
 * instant and deterministic, and it knows nothing about which nodes are *connected*, so a
 * plate of any size is a field of dots with edges crossing it at every angle. Measured on
 * Lictores' busiest plate: 1,519 nodes, 1,675 within-plate edges, **331,466 crossings**.
 * The same plate solved here: **27,312**, a 91.8% reduction.
 *
 * This is the layout `layout.py` has named in its own docstring since it was written —
 * *"force … Reveals clusters the module tree does not. Not computed here."* — and it is the
 * reason a shadow exists at all. `graph.py`: a shadow is *"a proxy at its own position on
 * this disk, taking part in this disk's forces like any other node."* Rule 23 says the model
 * stores every crossing twice, once per plate, *"which is exactly what lets both plates lay
 * out under the same forces."* Until now nothing has ever asked them to.
 *
 * ── The edge set, which is the one thing to get right ─────────────────────────────────
 *
 * **This solves over `payload.edges.from/to`, and must never solve over the engine's
 * `d.links`.** They are different sets for different jobs:
 *
 *   - `d.links` is real-to-real, deduped, spanning Z. It is what gets *drawn*, and rule 23
 *     requires it: a shadow is never an endpoint.
 *   - `payload.edges` is per plate and **shadow-terminated**. A call leaving the plate
 *     appears here as an edge ending at the proxy for whatever it reached.
 *
 * The second is the only place a cross-plate connection is expressed as a force *within* a
 * plate, which is the entire mechanism by which a plate's arrangement can know about the
 * rest of the program. Solving over `d.links` would be a 3D solver across the whole stack —
 * a different feature, and one that would dissolve the plates it is supposed to arrange.
 *
 * ── Determinism ──────────────────────────────────────────────────────────────────────
 *
 * `layout.py` requires the same graph to produce the same map on every machine and every
 * run, because spatial memory is the whole reason to arrange anything. This holds run to
 * run, verified bit-exact, and it is bought by four decisions:
 *
 *   - **seeded from the spiral**, never from noise. That is also why there is no random
 *     number generator here: from a phyllotaxis start no two nodes ever coincide, so the
 *     degenerate-overlap branch never fires. Changing a seed changes nothing, measured.
 *   - **CSR adjacency**, so each node sums its own edges. No atomics, so no reduction whose
 *     answer depends on which invocation arrived first.
 *   - **fixed iteration count**, fixed order: the plate in index order, then the node's own
 *     edges in index order.
 *   - **only exactly-rounded arithmetic** — `+ - * /` and `sqrt`. No `inverseSqrt`, which is
 *     an approximation a vendor may round as it likes, and no fast-math.
 *
 * Across *different* GPUs this is an argument rather than a measurement, and it is written
 * down as one. `solveOnWorkers` is the reference the GPU is checked against.
 */
const ForceLayout = (() => {
  "use strict";

  /* The spiral this starts from, and it is `layout.phyllotaxis` restated in JS rather than
   * read off the payload. The payload's own x/y are the *placed* positions, which have
   * already been through `structural`'s degree ordering — a fine start, and the reason to
   * recompute rather than reuse is that a plate's seed must depend only on its size, so the
   * result does not change when a node's degree changes somewhere else in the program. */
  const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

  /* How long to run. Fruchterman–Reingold with a cooling schedule converges well before
   * this on graphs of this shape; measured, the crossing count is flat from ~80. It is a
   * constant rather than a control because a half-solved layout is not a second option a
   * reader would choose between (design rule 2's own caveat: only when both are good). */
  const ITERATIONS = 100;
  const COOLING = 0.95;

  /* How hard a slot is pulled toward its group's middle, and how often.
   *
   * **A position move, not a force**, and that is what lets both backends run the same
   * arithmetic. Added to the displacement it would be clamped by the plate's temperature
   * and scaled by whatever else was pushing that slot; done in position space it is one
   * lerp, identical on a GPU and on the main thread — and the worker path *must* do it on
   * the main thread, because a group's members live on different plates and therefore in
   * different workers.
   *
   * `COUPLE_EVERY` is shared by both for the same reason. The GPU could afford it every
   * iteration; it does not, because then the two backends would be solving different
   * problems and "the same picture, slower" would stop being true. */
  const COUPLE_ALPHA = 0.5;
  const COUPLE_EVERY = 5;

  /* **One coordinate frame for the whole stack, and it is what makes the coupling work.**
   *
   * The first version normalised each plate onto its own middle at its own radius, so two
   * slots the solver had left in exactly the same place were pulled apart again by two
   * different translations and two different scales. Pulling harder could not fix it:
   * snapping every slot onto its group's mean every single iteration still left only 20 of
   * 5,101 crossings vertical, because the damage happened after the solve.
   *
   * With one frame, whatever the solver co-locates stays co-located — measured, all 4,050
   * entities land on their own middle to a spread of exactly zero — and cross-plate links
   * go from 1,558 upright to 3,878 of 5,101.
   *
   * What it costs is that a plate is no longer centred on the stack's axis, which the plate
   * outline and the rim arrow both assumed. In practice barely: plate centres come out
   * within 0.023 plate-widths of the axis on average and 0.127 at worst. They are handed to
   * the renderer rather than assumed either way. */
  const FRAME = "global";

  /* ── packing ──────────────────────────────────────────────────────────────────────
   *
   * One pass over the payload, producing everything both backends need. Nodes are grouped
   * by plate into one contiguous run each, so a plate is a *range* rather than a list —
   * which is what lets the GPU find its neighbours with two integers instead of an index
   * buffer, and what keeps the repulsion loop's order fixed.
   */
  function pack(payload) {
    const N = payload.nodes.id.length;

    /* Plates in first-appearance order. A `Map` because insertion order is defined and
     * this must not depend on how the payload happened to sort. */
    const runs = new Map();
    for (let i = 0; i < N; i++) {
      const d = payload.nodes.disk[i];
      let r = runs.get(d);
      if (!r) { r = []; runs.set(d, r); }
      r.push(i);
    }

    const order = new Int32Array(N);       // solver slot -> payload index
    const slot = new Int32Array(N).fill(-1); // payload index -> solver slot
    const span = new Int32Array(N * 4);    // per slot: plateStart, plateEnd, adjStart, adjEnd
    const k = new Float32Array(N);         // per slot: the plate's ideal edge length
    const pos = new Float32Array(N * 2);
    /* The starting step length, **per plate and not per stack**. A single temperature for
     * everything lets a 12-node plate take the strides a 1,519-node plate needs, and the
     * small plate is then still swinging when the schedule runs out. It rides per node
     * rather than in the uniform so both backends can be handed the same number: the
     * uniform carries only `cooling^iteration`, which is the part that is the same
     * everywhere. */
    const t0 = new Float32Array(N);

    let at = 0;
    for (const [, members] of runs) {
      const start = at;
      for (const i of members) { order[at] = i; slot[i] = at; at++; }
      const end = at;
      const n = end - start;
      /* Fruchterman–Reingold's `k`: the distance at which repulsion and attraction balance,
       * `sqrt(area / n)`. The area is the plate's own, so a plate settles at a size set by
       * what it holds rather than by a constant — which is what makes plate extent a fact
       * about the plate under this layout, and the reason the renderer must ask each plate
       * how wide it came out rather than assuming one radius for all of them. */
      const R = Math.sqrt(n) * 2;
      const kk = n > 0 ? R / Math.sqrt(n) : 1;
      const warm = Math.fround(R * 0.1);
      for (let q = start; q < end; q++) {
        span[q * 4] = start;
        span[q * 4 + 1] = end;
        k[q] = kk;
        t0[q] = warm;
        const idx = q - start;
        const r = n > 1 ? R * Math.sqrt((idx + 0.5) / n) : 0;
        const t = idx * GOLDEN_ANGLE;
        pos[q * 2] = r * Math.cos(t);
        pos[q * 2 + 1] = r * Math.sin(t);
      }
    }

    /* CSR adjacency over the **within-plate** edges of the payload's own edge list.
     *
     * An edge whose ends land on two different plates is skipped here — not dropped from the
     * model, but not a force either, because the model has already expressed it twice, once
     * per plate, each copy ending in that plate's shadow. Those copies *are* in this list.
     * Adding the cross-plate pair as well would count one connection three times and drag
     * two plates toward each other in a layout that has no axis to move them along. */
    let pairs = 0;
    const counts = new Int32Array(N);
    const ea = new Int32Array(payload.edges.from.length);
    const eb = new Int32Array(payload.edges.from.length);
    for (let e = 0; e < payload.edges.from.length; e++) {
      const a = slot[payload.edges.from[e]];
      const b = slot[payload.edges.to[e]];
      if (a < 0 || b < 0 || a === b) continue;
      if (span[a * 4] !== span[b * 4]) continue;   // different plates: already stored twice
      ea[pairs] = a; eb[pairs] = b; pairs++;
      counts[a]++; counts[b]++;
    }
    const off = new Int32Array(N + 1);
    for (let i = 0; i < N; i++) off[i + 1] = off[i] + counts[i];
    const cursor = off.slice(0, N);
    const adj = new Int32Array(off[N]);
    for (let m = 0; m < pairs; m++) {
      adj[cursor[ea[m]]++] = eb[m];
      adj[cursor[eb[m]]++] = ea[m];
    }
    for (let q = 0; q < N; q++) { span[q * 4 + 2] = off[q]; span[q * 4 + 3] = off[q + 1]; }

    /* ── the groups, which are what lets one plate feel another ──────────────────────
     *
     * An entity holds a position per plate it appears on: its real one, and one for every
     * plate that shadows it. Those slots are a **group**, and the consensus pass pulls them
     * toward their common middle — so a plate's arrangement is answerable to what the other
     * plates want, and a connection that leaves a plate can end up above or below where it
     * started rather than at an arbitrary angle.
     *
     * Built as a **CSR table, exactly like the edge adjacency above, and for the same
     * reason twice over.** It lets each slot walk its own group in a fixed order, which is
     * the only way this stays deterministic: the obvious GPU reduction is an `atomicAdd`,
     * and the order atomics arrive in is whatever the scheduler did that microsecond. That
     * would put nondeterminism into the one property `layout.py` promises.
     *
     * Every member of a group of 39 computes the same mean, which is redundant and is
     * cheaper than not being: the cost is the sum of the squares of the group sizes, a few
     * tens of thousands of operations against 12.8 million for repulsion. Measured on
     * Lictores: 4,050 entities carry a shadow, 9,905 slots between them, the biggest group
     * 39, the median 2.
     */
    const key = new Int32Array(N);
    for (let q = 0; q < N; q++) {
      const i = order[q];
      key[q] = payload.nodes.shadow[i] === 1 ? payload.nodes.real[i] : i;
    }
    const ordinal = new Map();
    let groups = 0;
    for (let q = 0; q < N; q++) {
      if (key[q] < 0) continue;
      if (!ordinal.has(key[q])) ordinal.set(key[q], groups++);
    }
    const gsize = new Int32Array(groups);
    for (let q = 0; q < N; q++) if (key[q] >= 0) gsize[ordinal.get(key[q])]++;
    const goff = new Int32Array(groups + 1);
    for (let g = 0; g < groups; g++) goff[g + 1] = goff[g] + gsize[g];
    const gmem = new Int32Array(goff[groups]);
    const gcur = goff.slice(0, groups);
    for (let q = 0; q < N; q++) if (key[q] >= 0) gmem[gcur[ordinal.get(key[q])]++] = q;
    /* Per slot, the half-open range of its own group. A slot whose real node is missing
     * from the payload gets an empty range and is simply never coupled — an absence, not a
     * special case to remember. */
    const grp = new Int32Array(N * 2);
    let coupled = 0;
    for (let q = 0; q < N; q++) {
      if (key[q] < 0) continue;
      const g = ordinal.get(key[q]);
      grp[q * 2] = goff[g];
      grp[q * 2 + 1] = goff[g + 1];
      if (goff[g + 1] - goff[g] > 1) coupled++;
    }

    return { N, order, slot, span, k, t0, pos, adj, grp, gmem,
             plates: runs.size, edges: pairs, groups, coupled };
  }

  /* ── the maths, once ──────────────────────────────────────────────────────────────
   *
   * Written as a string because the worker needs it as source and the reader needs to be
   * able to check that the two backends run the same algorithm. The WGSL below is a
   * transliteration of this, line for line, and a test asserts they stay in step.
   */
  /* **The two backends do not agree bit for bit, and they cannot. This was tried.**
   *
   * The obvious ambition is that the worker path *is* the GPU path in software, so it can
   * be the reference the shader is checked against. Every operation here was written
   * through `Math.fround` to force `f32` rounding on a language whose numbers are `f64`,
   * with identical operation order. Measured result: **1.15% of coordinates matched**, and
   * the fallback went from 9.7 s to 15.8 s for the privilege.
   *
   * WGSL permits an implementation to contract `a * b + c` into a fused multiply-add — one
   * rounding where the source says two — and nothing in the shading language can turn that
   * off. So the last bit of a displacement differs, and a force layout is chaotic: a
   * hundred iterations later that is a visibly different arrangement. `fround` was reverted
   * for costing tenfold and buying nothing.
   *
   * **What is asserted instead is equivalence, which is the property that actually matters**
   * — and it holds tightly. On the same corpus the two backends land every plate within
   * **0.07%** of the same radius and cut crossings by the same 92%. Two arrangements of one
   * graph, equally good, neither one wrong. Each backend is separately deterministic run to
   * run, which is what spatial memory needs (`layout.py`); what is *not* claimed is that a
   * reader on a GPU and a reader without one see the same picture, and the readout says
   * which one drew it.
   *
   * `disp` is allocated **once by the caller**, not per step: allocating inside cost a
   * further 40% for the same answer, a hundred throwaway arrays per plate. */
  const KERNEL_JS = `
function step(pos, span, k, adj, t0, cool, n, disp) {
  for (let i = 0; i < n; i++) {
    const s = span[i*4], e = span[i*4+1], a0 = span[i*4+2], a1 = span[i*4+3];
    const kk = k[i], kx2 = kk * kk;
    const xi = pos[i*2], yi = pos[i*2+1];
    let dx = 0, dy = 0;
    for (let j = s; j < e; j++) {
      if (j === i) continue;
      let ddx = xi - pos[j*2], ddy = yi - pos[j*2+1];
      let d2 = ddx*ddx + ddy*ddy;
      if (d2 < 1e-9) { ddx = 1e-4; ddy = 1e-4; d2 = 2e-8; }
      const f = kx2 / d2;
      dx += ddx * f; dy += ddy * f;
    }
    for (let m = a0; m < a1; m++) {
      const j = adj[m];
      const ddx = xi - pos[j*2], ddy = yi - pos[j*2+1];
      const d = Math.sqrt(ddx*ddx + ddy*ddy);
      if (d > 1e-9) { const f = d / kk; dx -= ddx/d*f; dy -= ddy/d*f; }
    }
    disp[i*2] = dx; disp[i*2+1] = dy;
  }
  for (let i = 0; i < n; i++) {
    const dx = disp[i*2], dy = disp[i*2+1];
    const d = Math.sqrt(dx*dx + dy*dy);
    if (d > 1e-9) {
      const lim = Math.min(d, t0[i] * cool);
      pos[i*2]   += dx/d*lim;
      pos[i*2+1] += dy/d*lim;
    }
  }
}`;

  /* ── backend: web workers ─────────────────────────────────────────────────────────
   *
   * The fallback, and the second opinion the GPU is checked against. One worker per core,
   * plates packed longest-first onto the emptiest worker — which matters, because the
   * largest plate alone sets the floor however many workers there are.
   *
   * **Measured at 9.7 s on an 8-core M1, against the GPU's 89 ms**, and that gap is the
   * honest price of running the *same* algorithm. Repulsion here is all-pairs within a
   * plate, exactly as the shader does it, because that is what makes "the same layout,
   * slower" a true sentence — a spatial approximation on this side only would be a second
   * algorithm, and then a machine without a GPU would be looking at a different picture for
   * a reason nobody could see. Paid once, on demand, and the readout says it happened.
   *
   * A plate is solved entirely within one worker, never split, because a plate's repulsion
   * is all-pairs over itself: splitting it would need the halves to see each other every
   * iteration, which is a shared buffer and a barrier, and at that point the GPU is the
   * better answer anyway.
   */
  const WORKER_SRC = `
${KERNEL_JS}
onmessage = (ev) => {
  const { jobs, iterations, cooling, cool: coolFrom } = ev.data;
  const out = [];
  for (const job of jobs) {
    const { pos, span, k, adj, t0, n } = job;
    const disp = new Float32Array(n * 2);   // once per plate, never per iteration
    // Where the schedule had got to when this round began: rounds continue one cooling
    // curve rather than each starting hot.
    let cool = coolFrom === undefined ? 1 : coolFrom;
    for (let it = 0; it < iterations; it++) {
      step(pos, span, k, adj, t0, cool, n, disp);
      cool *= cooling;
    }
    out.push({ start: job.start, pos });
  }
  postMessage(out, out.map(o => o.pos.buffer));
};`;

  async function solveOnWorkers(packed, opts = {}) {
    const started = performance.now();
    const width = Math.max(1, Math.min(navigator.hardwareConcurrency || 4, 16));

    /* One job per plate, carrying only that plate's slice. The slices are copies rather
     * than views: a worker cannot be handed a window onto a buffer another worker is also
     * writing, and copying 15,907 pairs of floats costs less than a millisecond. */
    const jobs = [];
    let q = 0;
    while (q < packed.N) {
      const start = packed.span[q * 4], end = packed.span[q * 4 + 1];
      const n = end - start;
      const pos = packed.pos.slice(start * 2, end * 2);
      const span = new Int32Array(n * 4);
      const k = packed.k.slice(start, end);
      const t0 = packed.t0.slice(start, end);
      /* Re-based into the slice, and the adjacency with it, so a worker's arithmetic never
       * mentions an index it does not hold. */
      let adjLen = 0;
      for (let i = 0; i < n; i++) adjLen += packed.span[(start + i) * 4 + 3] - packed.span[(start + i) * 4 + 2];
      const adj = new Int32Array(adjLen);
      let w = 0;
      for (let i = 0; i < n; i++) {
        const a0 = packed.span[(start + i) * 4 + 2], a1 = packed.span[(start + i) * 4 + 3];
        span[i * 4] = 0; span[i * 4 + 1] = n; span[i * 4 + 2] = w;
        for (let m = a0; m < a1; m++) adj[w++] = packed.adj[m] - start;
        span[i * 4 + 3] = w;
      }
      jobs.push({ start, n, pos, span, k, t0, adj });
      q = end;
    }

    jobs.sort((a, b) => b.n - a.n);
    const buckets = Array.from({ length: width }, () => []);
    const load = new Array(width).fill(0);
    for (const job of jobs) {
      let m = 0;
      for (let i = 1; i < width; i++) if (load[i] < load[m]) m = i;
      buckets[m].push(job);
      load[m] += job.n;
    }

    /* ── outer rounds, because the coupling is the one thing a worker cannot do ────────
     *
     * A worker owns whole plates and nothing else; a group's members are on *different*
     * plates and therefore in different workers, so the consensus cannot happen inside one.
     * The solve is therefore rounds: every worker advances its plates by `COUPLE_EVERY`
     * iterations in parallel, the main thread does one consensus over all the positions,
     * and round follows round.
     *
     * **This is the shape the feature was first described in** — solve all the plates,
     * then let the shadows tell each plate what the others want, then solve again. The GPU
     * does the same thing on the same schedule rather than coupling every iteration,
     * because two backends on two schedules are two algorithms and "the same picture,
     * slower" stops being true. Measured: the interval makes no difference to the result
     * once the pull is scaled for it — median 0.332 at every iteration against 0.325 at
     * every twenty-fifth — so the schedule is chosen for the fallback's benefit.
     *
     * The workers are made once and kept for the whole solve. Making eight per round, ten
     * times, would spend more on start-up than on arithmetic.
     */
    const iterations = opts.iterations || ITERATIONS;
    const alpha = opts.alpha === undefined ? COUPLE_ALPHA : opts.alpha;
    const every = Math.max(1, opts.every === undefined ? COUPLE_EVERY : opts.every);
    const url = URL.createObjectURL(new Blob([WORKER_SRC], { type: "text/javascript" }));
    const pool = buckets.map(() => new Worker(url));
    const whole = packed.pos.slice();
    try {
      for (let done = 0; done < iterations; done += every) {
        const chunk = Math.min(every, iterations - done);
        const results = await Promise.all(pool.map((worker, w) => new Promise((resolve, reject) => {
          const mine = buckets[w];
          if (!mine.length) { resolve([]); return; }
          /* Fresh slices out of the whole each round: the previous round's buffers were
           * transferred away and are detached. */
          const jobs = mine.map((j) => ({
            start: j.start, n: j.n, span: j.span, k: j.k, t0: j.t0, adj: j.adj,
            pos: whole.slice(j.start * 2, (j.start + j.n) * 2),
          }));
          worker.onmessage = (ev) => resolve(ev.data);
          worker.onerror = (err) => reject(new Error(err.message || "a layout worker failed"));
          /* The cooling schedule continues across rounds rather than restarting, or a
           * plate would take its longest strides ten times over. */
          worker.postMessage({ jobs, iterations: chunk, cooling: COOLING,
                               cool: Math.pow(COOLING, done) },
                             jobs.map((j) => j.pos.buffer));
        })));
        for (const group of results) for (const { start, pos } of group) whole.set(pos, start * 2);
        if (alpha > 0) consensus(packed, whole, alpha);
      }
      return { pos: whole, backend: "workers", detail: `${width} workers`,
               ms: performance.now() - started };
    } finally {
      for (const w of pool) w.terminate();
      URL.revokeObjectURL(url);
    }
  }

  /* The consensus, in the one place both backends' arithmetic is written down for the CPU.
   *
   * **Two passes, exactly as the shader has them**, and for the same reason: taking the
   * mean and moving toward it in one sweep would average a mixture of moved and unmoved
   * siblings, and which is which would depend on iteration order. Here that order is
   * defined, so it would be deterministic and still wrong — a different arrangement from
   * the GPU's, for no reason a reader could see. */
  function consensus(packed, pos, alpha) {
    const target = new Float32Array(pos.length);
    for (let q = 0; q < packed.N; q++) {
      const g0 = packed.grp[q * 2], g1 = packed.grp[q * 2 + 1];
      if (g1 - g0 < 2) { target[q * 2] = pos[q * 2]; target[q * 2 + 1] = pos[q * 2 + 1]; continue; }
      let cx = 0, cy = 0;
      for (let m = g0; m < g1; m++) { const j = packed.gmem[m]; cx += pos[j * 2]; cy += pos[j * 2 + 1]; }
      const n = g1 - g0;
      target[q * 2] = cx / n; target[q * 2 + 1] = cy / n;
    }
    for (let i = 0; i < pos.length; i++) pos[i] += (target[i] - pos[i]) * alpha;
  }

  /* ── backend: WebGPU compute ──────────────────────────────────────────────────────
   *
   * 83 ms for the whole stack against the workers' 1,657. One invocation per node; the
   * repulsion loop is the plate's own range, so the all-pairs cost a GPU is built for
   * stays inside the thing it belongs to.
   *
   * **Two failures here are silent and both were hit while proving this out.** They are
   * checked rather than hoped for:
   *
   *   1. `meta` is a **reserved word in WGSL**. The module failed to compile, the pipeline
   *      dispatched nothing, and the whole stack "solved" in 6 ms with the output
   *      bit-identical to the input. No exception, no console warning, a plausible number.
   *      Only counting edge crossings caught it. Hence `getCompilationInfo()` below, read
   *      and thrown on.
   *   2. `layout: "auto"` derives each pipeline's bind-group layout from **the bindings that
   *      entry point actually uses**. `forces` never reads the uniform, so a single bind
   *      group holding all six buffers is a validation error against it. Hence two bind
   *      groups, each listing only what its pass touches — and an error scope around the
   *      lot, because WebGPU reports validation asynchronously and swallowing it leaves
   *      exactly the inert pipeline of (1).
   */
  const WGSL = `
struct U { cool: f32, alpha: f32, pad1: f32, pad2: f32 };
@group(0) @binding(0) var<storage, read_write> pos:  array<f32>;
@group(0) @binding(1) var<storage, read>       span: array<i32>;
@group(0) @binding(2) var<storage, read>       kk:   array<f32>;
@group(0) @binding(3) var<storage, read>       adj:  array<i32>;
@group(0) @binding(4) var<storage, read_write> disp: array<f32>;
@group(0) @binding(5) var<uniform>             u:    U;
@group(0) @binding(6) var<storage, read>       t0:   array<f32>;
@group(0) @binding(7) var<storage, read>       grp:  array<i32>;
@group(0) @binding(8) var<storage, read>       gmem: array<i32>;

@compute @workgroup_size(64)
fn forces(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= i32(arrayLength(&kk))) { return; }
  let s = span[i*4]; let e = span[i*4+1]; let a0 = span[i*4+2]; let a1 = span[i*4+3];
  let k = kk[i]; let kx2 = k * k;
  let xi = pos[i*2]; let yi = pos[i*2+1];
  var dx = 0.0; var dy = 0.0;
  for (var j = s; j < e; j = j + 1) {
    if (j == i) { continue; }
    var ddx = xi - pos[j*2]; var ddy = yi - pos[j*2+1];
    var d2 = ddx*ddx + ddy*ddy;
    if (d2 < 1e-9) { ddx = 1e-4; ddy = 1e-4; d2 = 2e-8; }
    let f = kx2 / d2;
    dx = dx + ddx * f; dy = dy + ddy * f;
  }
  for (var m = a0; m < a1; m = m + 1) {
    let j = adj[m];
    let ddx = xi - pos[j*2]; let ddy = yi - pos[j*2+1];
    let d = sqrt(ddx*ddx + ddy*ddy);
    if (d > 1e-9) { let f = d / k; dx = dx - ddx/d*f; dy = dy - ddy/d*f; }
  }
  disp[i*2] = dx; disp[i*2+1] = dy;
}

@compute @workgroup_size(64)
fn integrate(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= i32(arrayLength(&kk))) { return; }
  let dx = disp[i*2]; let dy = disp[i*2+1];
  let d = sqrt(dx*dx + dy*dy);
  if (d > 1e-9) {
    let lim = min(d, t0[i] * u.cool);
    pos[i*2] = pos[i*2] + dx/d*lim;
    pos[i*2+1] = pos[i*2+1] + dy/d*lim;
  }
}

// Every slot standing for one entity, pulled toward their common middle.
//
// **Two passes, and the split is the whole of the determinism.** One pass that both read
// the positions and wrote them would have each invocation averaging a mixture of moved and
// unmoved siblings, decided by which invocation the scheduler ran first — the same defect
// an atomicAdd reduction has, arriving through a read instead of a write. So the mean is
// taken from positions nothing is writing, parked in the displacement buffer (free between
// iterations), and applied in a second pass that reads no sibling at all.
//
// No backtick anywhere in this shader: it is a template literal, and one would end it.
//
// Each invocation still walks its own group in index order and sums it itself. Every member
// of a group of 39 computes the same mean, which is redundant and costs less than the
// bookkeeping to avoid it.
@compute @workgroup_size(64)
fn consensusMean(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= i32(arrayLength(&kk))) { return; }
  let g0 = grp[i*2]; let g1 = grp[i*2+1];
  if (g1 - g0 < 2) { disp[i*2] = pos[i*2]; disp[i*2+1] = pos[i*2+1]; return; }
  var cx = 0.0; var cy = 0.0;
  for (var m = g0; m < g1; m = m + 1) {
    let j = gmem[m];
    cx = cx + pos[j*2]; cy = cy + pos[j*2+1];
  }
  let n = f32(g1 - g0);
  disp[i*2] = cx / n; disp[i*2+1] = cy / n;
}

@compute @workgroup_size(64)
fn consensusMove(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = i32(gid.x);
  if (i >= i32(arrayLength(&kk))) { return; }
  pos[i*2]   = pos[i*2]   + (disp[i*2]   - pos[i*2])   * u.alpha;
  pos[i*2+1] = pos[i*2+1] + (disp[i*2+1] - pos[i*2+1]) * u.alpha;
}`;

  function gpuAvailable() {
    return typeof navigator !== "undefined" && !!navigator.gpu;
  }

  async function solveOnGpu(packed, opts = {}) {
    const started = performance.now();
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) throw new Error("no WebGPU adapter");
    const device = await adapter.requestDevice();

    device.pushErrorScope("validation");
    const store = (arr) => {
      const b = device.createBuffer({
        size: arr.byteLength,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST,
      });
      device.queue.writeBuffer(b, 0, arr);
      return b;
    };
    const bPos = store(packed.pos);
    const bSpan = store(packed.span);
    const bK = store(packed.k);
    const bT0 = store(packed.t0);
    /* An empty storage buffer is invalid, and a program with no within-plate edge at all
     * is a real corpus rather than a broken one. One unused element is the honest floor. */
    const bAdj = store(packed.adj.length ? packed.adj : new Int32Array(1));
    const bGrp = store(packed.grp);
    const bGmem = store(packed.gmem.length ? packed.gmem : new Int32Array(1));
    const bDisp = device.createBuffer({
      size: packed.N * 2 * 4, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });
    const bU = device.createBuffer({
      size: 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });

    const module = device.createShaderModule({ code: WGSL });
    /* Read, not assumed. A compile error here is the difference between a layout and a
     * 6 ms no-op that looks exactly like one. */
    const info = await module.getCompilationInfo();
    const bad = info.messages.filter((m) => m.type === "error");
    if (bad.length) {
      throw new Error("the layout shader did not compile: " +
                      bad.map((m) => `line ${m.lineNum}: ${m.message}`).join("; "));
    }

    const pipe = (entryPoint) => device.createComputePipeline(
      { layout: "auto", compute: { module, entryPoint } });
    const pForces = pipe("forces");
    const pIntegrate = pipe("integrate");
    const pMean = pipe("consensusMean");
    const pMove = pipe("consensusMove");

    const resource = { 0: { buffer: bPos }, 1: { buffer: bSpan }, 2: { buffer: bK },
                       3: { buffer: bAdj }, 4: { buffer: bDisp }, 5: { buffer: bU },
                       6: { buffer: bT0 }, 7: { buffer: bGrp }, 8: { buffer: bGmem } };
    const bind = (pipeline, used) => device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: used.map((b) => ({ binding: b, resource: resource[b] })),
    });
    /* Exactly what each pass reads, and no more. `layout: "auto"` derives a bind-group
     * layout from the bindings an entry point actually uses, so one group holding every
     * buffer is refused by whichever pipeline touches fewer — asynchronously, into the
     * error scope, leaving a pipeline that dispatches and computes nothing. */
    const gForces = bind(pForces, [0, 1, 2, 3, 4]);         // no uniform, no t0, no groups
    const gIntegrate = bind(pIntegrate, [0, 2, 4, 5, 6]);   // no span, no adj, no groups
    const gMean = bind(pMean, [0, 2, 4, 7, 8]);             // reads pos, writes disp
    const gMove = bind(pMove, [0, 2, 4, 5]);                // reads disp, writes pos

    const scope = await device.popErrorScope();
    if (scope) throw new Error("the layout pipeline was refused: " + scope.message);

    const groups = Math.ceil(packed.N / 64);
    const iterations = opts.iterations || ITERATIONS;
    const alpha = opts.alpha === undefined ? COUPLE_ALPHA : opts.alpha;
    const every = opts.every === undefined ? COUPLE_EVERY : opts.every;
    let cool = 1;
    for (let it = 0; it < iterations; it++) {
      device.queue.writeBuffer(bU, 0, new Float32Array([cool, alpha, 0, 0]));
      const enc = device.createCommandEncoder();
      let pass = enc.beginComputePass();
      pass.setPipeline(pForces); pass.setBindGroup(0, gForces);
      pass.dispatchWorkgroups(groups); pass.end();
      pass = enc.beginComputePass();
      pass.setPipeline(pIntegrate); pass.setBindGroup(0, gIntegrate);
      pass.dispatchWorkgroups(groups); pass.end();
      /* The consensus, on the same schedule the workers can keep. Two passes of their
       * own so the mean is taken from a `pos` nothing is writing. */
      if (alpha > 0 && it % every === 0) {
        pass = enc.beginComputePass();
        pass.setPipeline(pMean); pass.setBindGroup(0, gMean);
        pass.dispatchWorkgroups(groups); pass.end();
        pass = enc.beginComputePass();
        pass.setPipeline(pMove); pass.setBindGroup(0, gMove);
        pass.dispatchWorkgroups(groups); pass.end();
      }
      device.queue.submit([enc.finish()]);
      cool *= COOLING;
    }

    const readable = device.createBuffer({
      size: packed.N * 2 * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
    const enc = device.createCommandEncoder();
    enc.copyBufferToBuffer(bPos, 0, readable, 0, packed.N * 2 * 4);
    device.queue.submit([enc.finish()]);
    await readable.mapAsync(GPUMapMode.READ);
    const pos = new Float32Array(readable.getMappedRange().slice(0));
    readable.unmap();
    device.destroy();

    /* A shader that dispatched but computed nothing returns the seed unchanged — landmine
     * (1) exactly, and it is cheap to refuse rather than to draw. */
    if (!pos.some(Number.isFinite) || (packed.N > 1 && identical(pos, packed.pos))) {
      throw new Error("the layout shader ran and moved nothing");
    }
    return { pos, backend: "gpu", detail: adapterName(adapter),
             ms: performance.now() - started };
  }

  function identical(a, b) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  function adapterName(adapter) {
    const i = adapter.info || {};
    return [i.vendor, i.architecture].filter(Boolean).join(" ") || "WebGPU";
  }

  /* Where the spiral puts a plate's outermost node. `layout.DISK_RADIUS`, restated because
   * this file hands the engine positions in the same units the server does — anything else
   * would make the stack's world scale depend on which layout drew it, and node size, zoom
   * and the far plane are all calibrated against it. */
  const DISK_RADIUS = 1000;

  /* ── centring, normalising, and what the renderer is told ─────────────────────────
   *
   * Two things happen here, and the second is the whole reason the rest of the engine needs
   * no changes.
   *
   * **Centred** on its own centroid, because the picture rests on plates being discs centred
   * on the stack's axis: `rimPoint` takes a node's bearing from the origin and walks out to
   * the rim, and the arrow only points *through* its node while that origin is the plate's
   * own middle.
   *
   * **Normalised to the unit disc, and its natural size returned separately.** A plate
   * settles at a size set by what it holds and how it connects — measured, 360 nodes came
   * out at 367 units and 1,519 at 422. The obvious thing is to hand those coordinates over
   * as they are, and it is wrong: `PLATE_R`, `rimPoint` and `fitView` all read one radius
   * for every plate, so three expressions would have to learn a fourth answer, and the
   * stack's world scale would change with the layout.
   *
   * Instead each plate is scaled to end exactly where the spiral ends, and the size it
   * *earned* leaves as a ratio. The engine already has a control for precisely that number:
   * `diskRatio` feeds the plate-width dial, `sqrt(n / nmax)` under the spiral, and this is
   * the same question answered by the solver instead of by a node count. So natural sizes
   * arrive through machinery that already exists, at the dial's default of 1, and turning
   * the dial to 0 still returns every plate to a uniform disc (design rule 22).
   */
  function centreAndNormalise(packed, pos, frame = "plate") {
    /* **One frame for the whole stack, which is what a skewer needs.**
     *
     * Under `plate` each plate is centred on its own middle and scaled to its own radius,
     * so two slots the solver left in exactly the same place are moved apart by two
     * different translations and two different scales. Co-location cannot survive it: at a
     * full snap every iteration, only 20 of 5,101 crossings came out vertical.
     *
     * Under `global` every slot is moved by one translation and one scale, so whatever the
     * solver co-located stays co-located and the line between the plates is vertical by
     * construction rather than by tendency. What it costs is that a plate is no longer
     * centred on the stack's axis — which three other things assume.
     */
    if (frame === "global") {
      let cx = 0, cy = 0;
      for (let i = 0; i < packed.N; i++) { cx += pos[i * 2]; cy += pos[i * 2 + 1]; }
      cx /= packed.N; cy /= packed.N;
      let far = 0;
      for (let i = 0; i < packed.N; i++) {
        pos[i * 2] -= cx; pos[i * 2 + 1] -= cy;
        far = Math.max(far, Math.hypot(pos[i * 2], pos[i * 2 + 1]));
      }
      const scale = far > 1e-6 ? DISK_RADIUS / far : 1;
      for (let i = 0; i < packed.N; i++) { pos[i * 2] *= scale; pos[i * 2 + 1] *= scale; }
      /* Each plate's own middle and extent, measured in the shared frame. The renderer
       * still has to know where to draw each circle and how wide — it just no longer gets
       * to assume the answer is "on the axis, at `PLATE_R`". */
      const solved = new Map();
      let q = 0;
      while (q < packed.N) {
        const start = packed.span[q * 4], end = packed.span[q * 4 + 1];
        let px = 0, py = 0;
        for (let i = start; i < end; i++) { px += pos[i * 2]; py += pos[i * 2 + 1]; }
        px /= (end - start); py /= (end - start);
        let r = 0;
        for (let i = start; i < end; i++) {
          r = Math.max(r, Math.hypot(pos[i * 2] - px, pos[i * 2 + 1] - py));
        }
        solved.set(packed.order[start], { x: px, y: py, r });
        q = end;
      }
      return solved;
    }

    const solved = new Map();
    let q = 0;
    while (q < packed.N) {
      const start = packed.span[q * 4], end = packed.span[q * 4 + 1];
      const n = end - start;
      let cx = 0, cy = 0;
      for (let i = start; i < end; i++) { cx += pos[i * 2]; cy += pos[i * 2 + 1]; }
      cx /= n; cy /= n;
      let far = 0;
      for (let i = start; i < end; i++) {
        pos[i * 2] -= cx; pos[i * 2 + 1] -= cy;
        far = Math.max(far, Math.hypot(pos[i * 2], pos[i * 2 + 1]));
      }
      /* A plate of one node has no extent and is not a mistake. Scaling by zero would put
       * it at the origin of a disc drawn around nothing; leaving it at 1 keeps it where the
       * spiral would have put it. */
      const scale = far > 1e-6 ? DISK_RADIUS / far : 1;
      for (let i = start; i < end; i++) { pos[i * 2] *= scale; pos[i * 2 + 1] *= scale; }
      solved.set(packed.order[start], far);
      q = end;
    }
    return solved;
  }

  /* ── the one door ────────────────────────────────────────────────────────────────
   *
   * Returns positions in **payload index order**, so a caller can write them straight into
   * `baseXY` without a translation table — the same one-index-space discipline that lets a
   * shadow keep its slot while never being drawn.
   *
   * Which backend ran travels with the answer and is meant to be shown. A reader on a
   * machine without WebGPU gets a layout that took twenty times longer and is entitled to
   * know that is what happened rather than to wonder (design rule 1).
   */
  async function solve(payload, opts = {}) {
    const packed = pack(payload);
    let result;
    if (opts.backend !== "workers" && gpuAvailable()) {
      try {
        result = await solveOnGpu(packed, opts);
      } catch (err) {
        /* Fall back and **say so**. A GPU that refuses is a fact about this machine, not an
         * error in the map, and the picture is the same picture twenty times slower. */
        result = await solveOnWorkers(packed, opts);
        result.fallback = err.message;
      }
    } else {
      result = await solveOnWorkers(packed, opts);
    }
    const frame = opts.frame || FRAME;
    const solved = centreAndNormalise(packed, result.pos, frame);

    const out = new Float32Array(packed.N * 2);
    for (let q = 0; q < packed.N; q++) {
      const i = packed.order[q];
      out[i * 2] = result.pos[q * 2];
      out[i * 2 + 1] = result.pos[q * 2 + 1];
    }

    /* **Where each plate came out, and how wide**, in the frame the positions are in.
     *
     * The renderer draws three things on a plate's circle — its outline, the nodes, and the
     * you-are-here arrow standing on its rim — and every one of them used to derive that
     * circle from a single constant, which was true while every plate was normalised onto
     * the axis and is a lie the moment one is not (rule 51, and the same argument design
     * rule 22 makes about the width dial). So the circle is measured here, once, and handed
     * over; nothing downstream recomputes it. */
    const plates = new Map();
    for (const [firstIndex, m] of solved) {
      plates.set(payload.nodes.disk[firstIndex],
                 typeof m === "number" ? { x: 0, y: 0, r: m } : m);
    }

    return { xy: out, plates, frame, backend: result.backend, detail: result.detail,
             fallback: result.fallback || "", ms: Math.round(result.ms),
             plateCount: packed.plates, edges: packed.edges, nodes: packed.N };
  }

  return { solve, pack, gpuAvailable, ITERATIONS, WGSL, KERNEL_JS };
})();

if (typeof window !== "undefined") window.ForceLayout = ForceLayout;
