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
  /* `disk` in the keys, **plate** in every word a reader sees.
   *
   * They are one thing under two names, and the reader's name is the one that had to be
   * settled: the fps line said "52 disks" while the size menu said "plates", which is two
   * words for one idea in a tool whose whole subject is a program's vocabulary. Plate won
   * because it is rare enough that this product gets to define it and common enough to be
   * guessed at, which is the same argument the glossary lane makes about any house word.
   *
   * The keys stay `disk` for now, and that is a debt rather than a decision: renaming a
   * persisted key discards every reader's saved arrangement unless the version is bumped
   * for it, and the code has a *second* live meaning for "plate" -- the polygon that draws
   * a disk (`showPlates`, `diskPlates`, `plateFill`). Renaming half of that pair would
   * leave the collision it was meant to remove. See `HANDOFF.md`. */
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
  /* The "you are here" pointer: an arrow standing over each node the reader picked.
   *
   * A selection of one node in nine thousand is a dot lit differently from its
   * neighbours, and "lit differently" is only findable by someone who already knows where
   * to look -- which is the thing they do not know. Off is a real choice, so it is here.
   *
   * `pointerColor` empty means "whatever `tokens.css` says", so a reader who never touches
   * it follows the theme like everything else on the page. A colour they *do* choose is
   * clamped: below 3:1 against the graph's own ground it is refused, and the refusal says
   * why (design rule 6). 3:1 rather than 4.5:1 because this is a large graphic object
   * rather than body text. */
  pointerShown: true,
  pointerColor: '',       // '' = the token, whichever theme is in force
  /* Where the arrow stands. Design rule 2, and a genuine pair.
   *
   * `rim` puts it at the side of the stack, at the height of the plate holding the node and
   * on that node's own bearing, so the line through it leads the eye inward. It is findable
   * from across the whole picture and is never buried in the mass it points into -- and it
   * leaves the frame when the reader snaps to fit, because fit frames the selection and the
   * rim is the width of a plate away from it. `node` stands the arrow directly over the
   * node: exact at any zoom, and at full node size swallowed by its own neighbours. */
  pointerPlace: 'rim',    // 'rim' | 'node'
  /* A ring with four ticks around every node the reader picked.
   *
   * Rule 19 dims the rest of the program rather than hiding it, and that is right: a subset
   * is only legible inside the shape it belongs to. But dimming answers "what is not mine"
   * and leaves *which one is mine* to be read off a colour difference among nine thousand
   * dots, with a dimmed node in front of or behind the lit one looking much the same. */
  reticuleShown: true,
  /* Whether the dimmed nine thousand answer a hover or a click.
   *
   * Locked, they do not: only the picks and the one hop drawn around them. Exploring wants
   * the opposite -- point at anything, learn what it is -- so this is a switch and it sits
   * on the HUD rather than in here, because it is a mode a reader flips while reading and
   * not a preference they set once. With nothing selected everything answers, or the lock
   * would be a mode nobody could click their way out of. */
  focusLocked: true,
  edgesInMotion: true,    // links stay up while the camera turns -- see graph.js
  graphLayout: 'stack',   // 'stack' | 'packages' -- both built, use retires the loser
  graphTheme: 'follow',   // 'follow' | 'dark' -- design rule 2; see the Settings page
  /* What following a neighbour does to the picture. Design rule 2: both are genuinely
   * good and real use decides, so both are built and usage retires the loser.
   *
   * `replace` is one hop from wherever you land -- the cleanest picture, and what design
   * rule 19 asks for. `walk` keeps every node you followed picked, so the hops you took
   * stay drawn and a few clicks build a visible route through the program. Rule 19 warns
   * that two hops is most of the program again; a walk is bounded by what the reader
   * actually clicked, which is a different limit and one they control.
   *
   * No new selection machinery either way: `togglePick` has taken a mode since the
   * multi-pick work, and this chooses between two values it already accepts. */
  followMode: 'replace',  // 'replace' | 'walk'
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
  /* How many navigator groups may stand open at once. Design rule 2: both are genuinely
   * good, so both are built and usage retires the loser.
   *
   * `one` is an accordion -- opening a group closes the rest, so the pane is never longer
   * than a single list and the group headings stay within a wheel's reach of the top.
   * `many` is what the navigator always did: every group open, the whole index visible at
   * a glance, and 4,734 routines between the top of the pane and everything under them.
   *
   * The default is `one` because the failure it fixes was observed: scrolling into
   * Routines put the reader two hundred rows away from every menu below it. */
  navGroups: 'one',       // 'one' | 'many'
  /* How many routines a package lists before the rest are left to the table.
   *
   * 200 was a judgment about `render()`, which rebuilds the navigator on every keystroke,
   * and it turned out to be a tease: most of Mensores' packages hold 200-400, so the notice
   * read `200 of 377` and `200 of 357` over lists that were nearly whole. The reader's
   * machine and the reader's patience are theirs to spend, so this is a Setting, and `0`
   * means all of them -- a long pane being a thing someone may legitimately want.
   *
   * Under `all` there is no notice, because nothing is left out and design rule 1 is about
   * what was *removed*, not about announcing that nothing was. */
  navCap: 200,            // 0 = every routine, however many there are
  /* Which groups are open, by the id in the shell's `NAV_GROUPS` table. An arrangement
   * rather than a question being asked right now, so unlike the search box it is kept.
   *
   * Empty means "not chosen yet", not "all closed": the shell falls back to each group's
   * own default, which is the only way a group added later can arrive open. A blob from an
   * older session carrying an id this build has dropped is harmless -- `buildNav` reads by
   * id and never enumerates this. */
  navOpen: {},
  /* Navigator width, in rem so the scale multiplier reaches it (design rule 3).
     Wider than the old fixed 14.5: it holds the routine list now, and a qualified
     name is the thing it has to be able to show. */
  navWidth: 21,
  /* The Code group's own width and the file it has open. Two panes wearing one track hold
   * different things -- a list of names and a page of source -- so one width for both means
   * the reader retunes it on every switch. `codeQ` is deliberately *not* here: a filter is a
   * question being asked right now, exactly like the routine search box, and a question is
   * not an arrangement. */
  codeWidth: 44,
  codeFile: '',

  /* ── the shell ───────────────────────────────────────────────────────────── */
  theme: 'system',        // 'system' | 'light' | 'dark'
  scale: 1,               // design rule 3: one multiplier over every dimension
  startup: 'cover',       // 'cover' | 'graph'
  mode: 'graph',          // which centre view: 'graph' | 'table' | 'doc'
  menuOrder: 'waysin',    // 'waysin' | 'explore' -- a genuine tie, so both exist
  trailShown: true,
  trailCap: 12,
  density: 'comfortable', // 'compact' | 'comfortable' | 'spacious'
  /* Whether a change-worklist band scrolls inside itself instead of running its full
   * length. Off, because rule 8 says a reference list is never bounded and the cap put a
   * 512px scroller inside the page's own 401px one -- scrolling a box to find a box. On
   * keeps all four band headings in reach at once, which is a real preference and not an
   * obviously worse one, so both exist and usage retires the loser (design rule 2). */
  bandScroll: false,
  /* The two versions. `baseRev` is the one being read — the whole map shows it — and
   * `comparedRev` is the version it is held against, "" for none. Empty means "whatever
   * is being served", which is the only honest default before any version has been read.
   *
   * Here as well as in `PERSISTED`, and that pairing is the point: `loadSettings` merges
   * only keys this object declares, so a key saved but not declared here is written on
   * every change and dropped on every load. That is exactly what these two did — the
   * chosen pair survived a reload in `localStorage` and never once came back.
   *
   * They were `revB` and `revA` until 2026-08-30. The rename orphans whatever those held
   * in `localStorage`, which is deliberate and harmless: the value is a revision id, the
   * merge above simply will not see it, and the pair falls back to the served default. */
  baseRev: '',
  comparedRev: '',
  /* Which of the two versions the reader takes to be the newer one.
   *
   * Not something this tool can see. The only instant it records is when the bytes were
   * read, so "newer" is an assumption, and it decides whether what the base has and the
   * compared lacks reads as deleted or as added. Default: the compared is newer — the
   * case the feature exists for, reading a copy somebody handed you and asking what has
   * happened since. Stated on the strip, because an assumption nobody can see is one
   * they cannot correct. */
  comparedIsNewer: true,
  /* How a search decides a match — not what is being looked for, which is a question
   * being asked right now and never an arrangement. `shell.js` has said these are
   * persisted since the day they were written and they were not: listed in `PERSISTED`,
   * absent from here, therefore saved on every keystroke and dropped on every load. Found
   * by the guard written for the revision pair, which had the identical defect. */
  searchCase: false,
  searchWord: false,
  searchRegex: false,
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
    diskOrder: 'plate order', diskColors: 'plate colours', colorBy: 'colour source',
    sortMode: 'sort', filterMode: 'filter mode', direction: 'direction',
    nodeSize: 'node size', picks: 'selection', followMode: 'following a neighbour',
    spreadX: 'spread across', spreadY: 'spread deep', spreadZ: 'spread between plates',
    collapseUnused: 'collapsed plates',
    showPlates: 'the plates themselves', edgesInMotion: 'edges while moving',
    pointerShown: 'the you-are-here pointer', pointerColor: 'the pointer colour',
    pointerPlace: 'where the pointer stands',
    reticuleShown: 'the focus reticule', focusLocked: 'focus locked to the selection',
    mode: 'centre view', panels: 'panel layout',
    inspectorAuto: 'auto-collapse the inspector', navWidth: 'navigator width',
    codeWidth: 'code pane width', codeFile: 'which file the code pane has open',
    navGroups: 'how many navigator groups open at once', navOpen: 'which groups are open',
    navCap: 'how many routines a package lists',
    graphLayout: 'graph layout', graphTheme: 'graph theme',
    theme: 'theme', scale: 'interface scale', startup: 'startup screen',
    menuOrder: 'menu order', trailShown: 'the trail', trailCap: 'trail length',
    density: 'row density', bandScroll: 'scrolling change bands',
    baseRev: 'which version is being read', comparedRev: 'what it is compared with',
    comparedIsNewer: 'which version is assumed newer',
    searchCase: 'case-sensitive search', searchWord: 'whole-word search',
    searchRegex: 'regular-expression search',
    ambient: 'ambient badges', hideInferred: 'inferred edges',
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
