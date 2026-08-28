/* The inspector: what one selected thing is, in the order that matters.
 *
 * **Flow-first, not signature-first.** IN (how it is reached) → OUT (what it calls, with
 * confidence) → TOUCHES → GOVERNANCE → source. A signature says what types cross the
 * boundary of a function; it does not say what moves through the program, so it is
 * demoted into the params view rather than leading.
 *
 * Three disciplines from `CLAUDE.md` are load-bearing here, not decoration:
 *
 * 1. **No filter is ever silent.** Where a list is bounded for space, the count of what
 *    was left out is stated and one click opens the rest. A reader who mistakes a slice
 *    for the whole has been misled by the tool, not by the program.
 * 2. **Confidence is shape, not colour** (design rule 5). Solid left edge = CERTAIN,
 *    dashed = INFERRED. Colour is spent on one dimension at a time, and here it is spent
 *    on *outside the program*, which is the distinction a reader acts on.
 * 3. **Provenance must open** (design rule 13). Every claim carries its file and line,
 *    and the source view puts the thing itself in the code it came from, highlighted.
 *    Where the source cannot be shown, the reason is stated — "no source" and "source not
 *    kept" are different facts and must not read the same.
 */
'use strict';

(function () {

/* How many rows of a list are shown before it is bounded. Rule 8: abbreviation is allowed
 * only where the complete content sits beside it, so every bounded list here gets a
 * control that opens the remainder in place — never a truncation the reader cannot undo. */
const PAGE = 25;

const esc = (s) => String(s ?? '').replace(/[&<>"]/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const el = (id) => document.getElementById(id);

/* Which lists the reader has opened fully, kept across re-renders of the same node so
 * that expanding "callers" and then clicking something does not silently re-collapse it. */
let expanded = new Set();
let current = null;

function short(path) {
  const s = String(path || '');
  const cut = s.lastIndexOf('/');
  return cut < 0 ? s : s.slice(cut + 1);
}

/* ------------------------------------------------------------------ sections --- */

function section(key, title, count, inner, opts = {}) {
  const empty = !count;
  const note = opts.note ? `<span class="muted tiny">${esc(opts.note)}</span>` : '';
  return `<div class="sect${empty ? ' none' : ''}" data-sect="${esc(key)}">
    <h3>${esc(title)} <span class="n">${count.toLocaleString()}</span> ${note}</h3>
    ${empty ? `<p class="muted tiny">${esc(opts.emptyText || 'none')}</p>` : inner}
  </div>`;
}

/* A list that states what it is not showing. The count of hidden rows is part of the
 * control, so the reader never has to wonder whether 25 was the answer or the limit. */
function boundedList(key, rows, render) {
  const open = expanded.has(key);
  const shown = open ? rows : rows.slice(0, PAGE);
  const hidden = rows.length - shown.length;
  const more = hidden > 0
    ? `<button class="item muted" data-expand="${esc(key)}">
         … ${hidden.toLocaleString()} more not shown — click to open all
       </button>`
    : (open && rows.length > PAGE
        ? `<button class="item muted" data-collapse="${esc(key)}">show fewer</button>`
        : '');
  return shown.map(render).join('') + more;
}

/* ------------------------------------------------------------------ pieces --- */

function callRow(c, dir) {
  /* `external` means the call leaves the program: design rule 8 says an external is a
   * first-class thing badged as outside our control, not an edge trailing off the side. */
  const outside = !!c.external || !c.id;
  /* Confidence shape is for *internal* calls only.
   *
   * The store labels every external call INFERRED -- all 23,829 of them on Mensores --
   * because it never resolved to a local routine. But design rule 5 spends the dashed
   * edge on "we are not sure this call exists", and that is not the claim here: we are
   * certain the call happens, we simply cannot see the other end of it. Drawing the two
   * the same way blurs exactly the distinction rule 6 says never to blur, so an external
   * gets its own mark and no confidence shape at all. */
  const cls = [
    'item',
    outside ? 'outside'
            : ((c.confidence || '').toUpperCase() === 'CERTAIN' ? 'certain' : 'inferred'),
    c.ambiguous ? 'ambiguous' : '',
  ].filter(Boolean).join(' ');
  const label = dir === 'in'
    ? (c.qualname || c.name || c.callee_expr)
    : (c.qualname || c.name || c.callee_expr);
  const tag = c.id ? `data-goto="${esc(c.id)}"` : '';
  const el = c.id ? 'button' : 'div';
  const where = c.line ? `:${c.line}` : '';
  const marks = [
    c.ambiguous ? 'ambiguous' : '',
    c.at_boundary ? 'boundary' : '',
    outside ? 'leaves the program'
            : ((c.confidence || '').toUpperCase() === 'INFERRED' ? 'inferred' : ''),
  ].filter(Boolean).join(' · ');
  return `<${el} class="${cls}" ${tag}>
    <span class="nm">${esc(label)}</span>
    <span class="where"> ${esc(short(c.file) + where)}${marks ? ' · ' + esc(marks) : ''}</span>
  </${el}>`;
}

function boundaryRow(b) {
  return `<div class="item certain">
    <span class="nm">${esc(b.kind)}</span>
    <span class="where"> ${esc(b.direction || '')} ${esc(b.target || '(unnamed)')}
      · line ${esc(b.line)} · ${esc(b.evidence || 'no evidence recorded')}</span>
  </div>`;
}

function sqlRow(s) {
  return `<div class="item certain">
    <span class="nm">${esc(s.operation)} ${esc(s.tbl || '?')}</span>
    <span class="where"> ${esc(s.direction || '')} · line ${esc(s.line)}</span>
    <div class="why">${esc(s.sql || '')}</div>
  </div>`;
}

/* The full network record. Rule 8 again: a timeout nobody set is a fact about the
 * program, so an absent value is printed as "none set" rather than omitted — a missing
 * row and a row saying nothing are not the same claim. */
function netRow(n) {
  const bits = [
    ['protocol', n.protocol], ['verb', n.verb], ['destination', n.destination],
    ['port', n.port], ['timeout', n.timeout], ['retries', n.retries],
    ['tls', n.tls], ['topic', n.topic], ['ack', n.ack],
    ['async', n.is_async], ['awaited', n.awaited], ['payload', n.payload],
  ];
  const rows = bits.map(([k, v]) =>
    `<dt>${esc(k)}</dt><dd>${v === null || v === undefined || v === ''
      ? '<span class="muted">none set</span>' : esc(v)}</dd>`).join('');
  return `<div class="item certain">
    <span class="nm">${esc(n.expr || '(call)')}</span>
    <span class="where"> line ${esc(n.line)}</span>
    <dl class="kv">${rows}</dl>
  </div>`;
}

function artefactRow(a) {
  return `<div class="item certain">
    <span class="nm">${esc(a.name)}</span>
    <span class="where"> ${esc(a.kind || '')} · line ${esc(a.line)}
      ${a.is_pattern ? '· pattern' : ''}</span>
    ${a.literal ? `<div class="why">${esc(a.literal)}</div>` : ''}
  </div>`;
}

/* Comments placed against the line they explain, not pooled in a block. That placement is
 * the whole reason closing the comment gap was worth doing: 53% of them never reached the
 * store, and the ones that did were only useful once they sat beside their subject. */
function commentRow(c) {
  if (!String(c.text || '').trim()) return '';
  return `<div class="note"><span class="ln">${esc(c.line)}</span> ${esc(c.text)}</div>`;
}

function annotationRow(a) {
  return `<div class="note">
    <span class="ann">${esc(a.kind)} ${esc(a.value)}</span>
    <span class="ln">line ${esc(a.line)}</span>
    ${a.text ? `<div>${esc(a.text)}</div>` : ''}
  </div>`;
}

function sourceBlock(src) {
  if (!src) return '';
  if (!src.available) {
    return section('source', 'source', 0, '', {
      emptyText: src.reason || 'not available',
    });
  }
  const [f0, f1] = src.focus || [];
  const rows = src.lines.map((l) => {
    const on = f0 && l.n >= f0 && l.n <= f1;
    return `<tr class="${on ? 'focus' : ''}"><td class="n">${l.n}</td><td>${esc(l.text)}</td></tr>`;
  }).join('');
  return `<div class="sect" data-sect="source">
    <h3>source <span class="n">${esc(short(src.file))}</span>
      <span class="muted tiny">lines ${src.first}–${src.last}</span></h3>
    <div class="src"><table>${rows}</table></div>
    <button class="item muted" data-whole="${esc(src.file)}">open the whole file</button>
  </div>`;
}

/* -------------------------------------------------------------------- render --- */

function renderRoutine(d) {
  const i = d.identity;
  const sig = `${i.is_async ? 'async ' : ''}${i.name}(${
    (d.params || []).map((p) => p.name).join(', ')})${i.returns ? ' → ' + i.returns : ''}`;
  const comments = (d.governance.comments || []).filter((c) => String(c.text || '').trim());

  return `
  <div class="ins-head">
    <h2>${esc(i.name)}</h2>
    <div class="sub">${esc(i.qualname || '')}</div>
    <div class="sub">${esc(i.module || '')} · ${esc(short(i.file))}:${esc(i.line_start)}</div>
    <div class="sub"><span class="ins-badge">${esc(i.visibility || 'public')}</span>
      ${i.is_method ? '<span class="ins-badge">method</span>' : ''}
      ${i.is_nested ? '<span class="ins-badge">nested</span>' : ''}
      ${i.is_async ? '<span class="ins-badge">async</span>' : ''}</div>
  </div>

  ${d.docstring_shown === false ? '' : (i.docstring
    ? `<div class="why">${esc(i.docstring)}</div>` : '')}

  ${section('in', 'in — how it is reached',
    d.in.callers.length + d.in.entrypoints.length,
    (d.in.entrypoints.length
      ? `<div class="muted tiny">a way in: ${d.in.entrypoints.map(
          (e) => esc(e.kind + ' ' + (e.name || ''))).join(', ')}</div>` : '')
    + boundedList('in', d.in.callers, (c) => callRow(c, 'in')),
    { emptyText: 'nothing in this map calls it — it may be a way in, dead, or reached '
                 + 'by something the extractor cannot see' })}

  ${section('out', 'out — what it does next', d.out.calls.length,
    boundedList('out', d.out.calls, (c) => callRow(c, 'out')))}

  ${section('boundaries', 'touches — boundaries', d.touches.boundaries.length,
    boundedList('boundaries', d.touches.boundaries, boundaryRow))}
  ${section('sql', 'touches — database', d.touches.sql.length,
    boundedList('sql', d.touches.sql, sqlRow))}
  ${section('net', 'touches — network', d.touches.net.length,
    boundedList('net', d.touches.net, netRow))}
  ${section('artefacts', 'touches — files it names', d.touches.artefacts.length,
    boundedList('artefacts', d.touches.artefacts, artefactRow))}

  ${section('ann', 'governance', d.governance.annotations.length,
    boundedList('ann', d.governance.annotations, annotationRow))}
  ${section('why', 'why — the comments', comments.length,
    boundedList('why', comments, commentRow))}

  ${section('params', 'signature', (d.params || []).length,
    `<div class="why">${esc(sig)}</div>` + (d.params || []).map((p) =>
      `<div class="item certain"><span class="nm">${esc(p.name)}</span>
       <span class="where"> ${esc(p.type || 'untyped')}${
         p.dflt ? ' = ' + esc(p.dflt) : ''} · ${esc(p.kind || '')}</span></div>`).join(''),
    { note: 'demoted: what moves through a routine is the subject, its types are not' })}

  ${sourceBlock(d.source)}`;
}

function renderStructure(d) {
  const i = d.identity;
  return `
  <div class="ins-head">
    <h2>${esc(i.name)}</h2>
    <div class="sub">${esc(i.kind)} · ${esc(i.module || '')} · ${esc(short(i.file))}:${esc(i.line)}</div>
    ${i.bases ? `<div class="sub">bases: ${esc(i.bases)}</div>` : ''}
  </div>
  ${i.docstring ? `<div class="why">${esc(i.docstring)}</div>` : ''}
  ${section('fields', 'fields', (d.fields || []).length,
    boundedList('fields', d.fields || [], (f) =>
      `<div class="item certain"><span class="nm">${esc(f.name)}</span>
        <span class="where"> ${esc(f.type || 'untyped')}${
          f.dflt ? ' = ' + esc(f.dflt) : ''}</span>
        ${f.comment ? `<div class="why">${esc(f.comment)}</div>` : ''}</div>`))}
  ${section('ann', 'governance', d.governance.annotations.length,
    boundedList('ann', d.governance.annotations, annotationRow))}
  ${sourceBlock(d.source)}`;
}

function renderConstant(d) {
  const i = d.identity;
  return `
  <div class="ins-head">
    <h2>${esc(i.name)}</h2>
    <div class="sub">${esc(i.module || '')} · ${esc(short(i.file))}:${esc(i.line)}</div>
    <div class="sub">${i.is_final ? '<span class="ins-badge">final</span>' : ''}
      ${i.private ? '<span class="ins-badge">private</span>' : ''}
      ${i.type ? `<span class="ins-badge">${esc(i.type)}</span>` : ''}</div>
  </div>
  ${section('value', 'value', i.value ? 1 : 0,
    `<div class="src"><table><tr><td>${esc(i.value)}</td></tr></table></div>`)}
  ${section('why', 'why — the comment', i.comment ? 1 : 0,
    `<div class="note">${esc(i.comment)}</div>`,
    { emptyText: 'no comment says why this value is what it is' })}
  ${sourceBlock(d.source)}`;
}

/* An external. The question is never "what is this" — it is "which of my code talks to
 * it", so the answer is the callers, and the badge says we never looked inside. */
function renderExternal(d) {
  const i = d.identity;
  const rows = d.in.callers;
  return `
  <div class="ins-head">
    <h2>${esc(d.label)}</h2>
    <div class="sub"><span class="ins-badge outside">${esc(i.source_status)}</span>
      outside this program — nothing here was analysed</div>
    ${i.bkind ? `<div class="sub">${esc(i.bkind)}</div>` : ''}
  </div>
  ${section('touchers', d.kind === 'ARTEFACT' ? 'named by' : 'reached from', rows.length,
    boundedList('touchers', rows, (r) => `<div class="item certain">
      <span class="nm">${esc(r.qualname || r.routine || r.name || '(module scope)')}</span>
      <span class="where"> ${esc(short(r.file))}:${esc(r.line)}
        ${r.evidence ? '· ' + esc(r.evidence) : ''}</span>
    </div>`))}
  <p class="muted tiny">Point DunneFlow at this system's source and it becomes
     <code>ANALYZED</code> in place — cross-program stitching is a fuller map, not a
     different one.</p>`;
}

function render(d) {
  const box = el('inspector');
  if (!d) {
    box.innerHTML = '<p class="muted empty">Nothing selected. Click a node, or pick a '
                  + 'disk from the navigator.</p>';
    return;
  }
  if (!d.found) {
    box.innerHTML = `<p class="muted empty">${esc(d.reason || 'not in this map')}
      <br><span class="tiny">${esc(d.id || '')}</span></p>`;
    return;
  }
  const by = {
    ROUTINE: renderRoutine,
    STRUCTURE: renderStructure,
    CONSTANT: renderConstant,
    BOUNDARY: renderExternal,
    ARTEFACT: renderExternal,
  };
  const fn = by[d.kind];
  if (!fn) {
    // Routed from a table, so an unhandled kind says so rather than rendering blank.
    console.error('[dunneflow] inspector has no renderer for kind', d.kind);
    box.innerHTML = `<p class="muted empty">No inspector view for
      <code>${esc(d.kind)}</code> yet.</p>`;
    return;
  }
  box.innerHTML = fn(d);
}

/* ---------------------------------------------------------------- behaviour --- */

let seq = 0;

async function show(nodeId, opts = {}) {
  if (!nodeId) { current = null; render(null); return; }
  if (opts.keepExpanded !== true && nodeId !== (current && current.id)) expanded = new Set();
  const mine = ++seq;
  try {
    const r = await fetch(`/api/node?id=${encodeURIComponent(nodeId)}`);
    const d = await r.json();
    // A slower earlier request must never overwrite a faster later one: clicking through
    // three nodes quickly would otherwise settle on whichever server call finished last.
    if (mine !== seq) return;
    current = d;
    render(d);
    el('inspector').scrollTop = 0;
  } catch (err) {
    if (mine !== seq) return;
    el('inspector').innerHTML =
      `<p class="muted empty">Could not read that node: ${esc(err.message)}</p>`;
  }
}

async function openWholeFile(path) {
  const r = await fetch(`/api/source?path=${encodeURIComponent(path)}`);
  const d = await r.json();
  const box = el('inspector');
  if (!d.available) {
    box.insertAdjacentHTML('beforeend',
      `<p class="muted tiny">${esc(d.reason || 'not available')}</p>`);
    return;
  }
  const rows = d.lines.map((l) =>
    `<tr><td class="n">${l.n}</td><td>${esc(l.text)}</td></tr>`).join('');
  box.insertAdjacentHTML('beforeend', `<div class="sect"><h3>whole file
    <span class="n">${esc(short(d.file))}</span>
    <span class="muted tiny">${d.lines.length.toLocaleString()} lines</span></h3>
    <div class="src" style="max-height:40rem"><table>${rows}</table></div></div>`);
}

/* One delegated listener. Every control the inspector draws is declarative — `data-goto`,
 * `data-expand`, `data-collapse`, `data-whole` — so a control that renders and does
 * nothing is impossible to add without adding a branch here too. */
function wire(onGoto) {
  el('inspector').addEventListener('click', (ev) => {
    const t = ev.target.closest('[data-goto],[data-expand],[data-collapse],[data-whole]');
    if (!t) return;
    if (t.dataset.goto) return onGoto(t.dataset.goto);
    if (t.dataset.whole) return openWholeFile(t.dataset.whole);
    if (t.dataset.expand) expanded.add(t.dataset.expand);
    if (t.dataset.collapse) expanded.delete(t.dataset.collapse);
    render(current);
  });
}

window.DunneFlowInspector = { show, wire, render };
})();
