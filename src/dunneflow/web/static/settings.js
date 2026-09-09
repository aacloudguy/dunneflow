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
/* Bumped to 4 for the second level of detail. `level` and `minDisk` are new keys and would
 * merge safely on their own -- `loadSettings` gives a key `DEFAULTS` declares and storage
 * does not its default. `diskOrder` is the reason: it was one array and is now one array
 * *per level*, and a v3 blob merged into that shape would hand `mount` a list of plate ids
 * where it expects a map. A half-applied layout is harder to recognise as wrong than a
 * reset one, which is this file's own rule. */
/* Bumped to 5 because `triage` changed **meaning** rather than shape. It was keyed by the
 * finding's position in the served list while both of its declarations said `finding id ->`,
 * and findings are served sorted by count -- so a count that moved, a detector that was
 * added, or a base switch landed every saved decision on a different finding. Measured on
 * Mensores' pair: a decision filed against `siq__rebuild_87_02h` read back after a switch as
 * an acknowledgement of `tags`, silently. An index-keyed blob read as ident-keyed is a
 * *wrong* answer, not an absent one, so it may not merge.
 *
 * Which is a different case from every bump before it, and it is why this one carries
 * forward. A blob that cannot be read at all is the reason those discarded everything;
 * here exactly one key is unreadable and the other sixty-five -- the shelf, the plate
 * colours, the panel layout -- are as good as they were. Discarding them would be this
 * file's own rule applied where its reasoning does not reach. */
const SETTINGS_VERSION = 6;

/* What a bump may carry over from the version below it, and what it must drop.
 *
 * Keyed by the version being *left*, so it is a statement about one specific blob rather
 * than a licence to vouch for any older one -- the same gate `migrate.py` puts on
 * re-stamping a fingerprint (rule 62). A version not named here carries nothing, which is
 * what every bump before 5 did.
 *
 * The value is what to **drop**. Everything else merges by the ordinary rules.
 */
const CARRY_FORWARD = {
  4: {
    drop: ['triage'],
    /* The **name** of what was dropped, and nothing more. The reason belongs to the surface
     * that lost it -- the worklist knows why a position is not a finding and this store does
     * not -- and a sentence in both places renders as the same claim twice. It did, on the
     * first drive: 'triage decisions — they were filed against a position in the list, not a
     * finding: they were filed against a position in this list rather than against a
     * finding'. Rule 40 in prose: two renderings of one fact, side by side. */
    why: 'Triage decisions',
  },
  /* 5 → 6 adds `plateLayout` and takes nothing away. A key that is merely *new* needs no
   * entry here — the merge fills it from `DEFAULTS` — but the version had to move all the
   * same, because a v5 blob has no opinion about how a plate arranges itself and a reader
   * who had one saved would otherwise inherit silence as a choice. Nothing to drop, so the
   * list is empty and there is no sentence: `resetSettings` names what a reader *lost*, and
   * this bump loses nothing. */
  5: { drop: [], why: '' },
};

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
  /* **Per level**, and the two are genuinely different lists: the module level holds
   * different plates and merges different ones into `<small>`, so an order worked out for
   * one does not describe the other. Kept apart rather than discarded on every switch,
   * because `mount` validates a saved order against the plate set and throws it away when
   * it does not match -- so one shared array would mean a reader who arranged the routine
   * stack lost the arrangement the moment they looked at modules and came back. */
  diskOrder: { routine: null, module: null },   // null = the server's default order
  diskColors: {},         // diskId -> "#rrggbb"
  /* Which altitude the stack is drawn at, and how small a plate may be before it is
   * merged into `<small>`.
   *
   * `routine` is every thing the program declares -- 10,015 nodes on Mensores. `module`
   * folds each file into one node and each boundary kind into one: 578. It is a second way
   * to look at the same facts and not a filter, so nothing is dropped and every folded
   * node says what it stands for.
   *
   * `minDisk` is per level for the same reason the server's default is (design rule 2, and
   * `graph.py` states the arithmetic): what a plate *holds* changes with the level, so 8
   * is right for routines and folds 21 of Mensores' 45 packages away at module level. Null
   * means "whatever the server's default for this level is", which is a third state and
   * not a number -- a stored 8 would silently become an explicit choice about a level the
   * reader had never visited. */
  level: 'routine',       // 'routine' | 'module'
  minDisk: { routine: null, module: null },
  /* What colour means in the stack. `change` appears only where there are two versions
     to compare, and a stored `change` on a program with one falls back to `kind` and
     says so -- see `resolveColorBy` in shell.js. */
  colorBy: 'kind',        // 'kind' | 'disk' | 'change'
  sortMode: 'nodes',      // 'nodes' | 'name' | 'kind' | 'manual'
  filterMode: 'dim',      // 'dim' | 'hide'
  direction: 'both',      // 'callers' | 'callees' | 'both'
  /* How much clear space a node keeps, as a multiple of its own diameter. It replaced
     `nodeSize`: a node's radius is derived from the room its plate gives it, so the reader
     sets the room and not the radius. Smaller means bigger dots. */
  nodeSpacing: 1.5,
  /* Whether a node's size says how sparse its plate is, or only its degree. Design rule 2:
     both readings are good, so both are built. `plate` is the default. */
  nodeScaling: "plate",
  /* Three independent axes. X and Y widen a plate, which is what separates nodes that
   * fuse into a mass at large sizes; Z is the gap between plates. All three moving
   * together is what zoom already does, so there is no linked control. Version 3: the
   * single `spread` these replace was Z alone. */
  spreadX: 1,
  spreadY: 1,
  spreadZ: 0.35,
  /* How much a plate's *width* says about how much it holds.
   *
   * A strength, not a size. 0 is the uniform stack -- every plate drawn the same width
   * whether it holds 991 things or 6 -- and 1 is area proportional to content, so the
   * footprint means *how much is here* and two plates read as equally dense. The dial
   * interpolates between the two, which is what makes it reversible: 0 comes home
   * exactly, the same reason the engine keeps an unscaled copy of every position.
   *
   * The reversal is deliberate and is recorded in `layout.py`, which drew every disk the
   * same size on the argument that density would then carry the information. It did not:
   * a plate of 6 nodes and a plate of 991 at one width are a sparse ring and a solid
   * mass, and the reader has to compare two textures to learn a number. Area says it.
   *
   * **Per level**, because it is a question about two pictures. Mensores' routine level
   * spans 12.85x from largest plate to smallest and its module level 5.32x, so full
   * strength is a far more dramatic silhouette at one altitude than at the other and the
   * judgment does not carry across. The same argument `minDisk` and `diskOrder` make. */
  plateSize: { routine: 1, module: 1 },
  /* **How a plate arranges what it holds.** Two layouts, both built, and design rule 2 says
   * real use retires the loser.
   *
   * `structural` is the sunflower spiral ordered by degree — even, instant, and blind to
   * which nodes are connected, so edges cross it at every angle. `force` runs
   * Fruchterman–Reingold over each plate until connected things sit near each other,
   * shadows pulling for the plates they stand in for, which is the reason a shadow exists
   * (rule 23). Measured on Mensores' busiest plate: 328,531 crossings down to 27,291,
   * **91.7% fewer**.
   *
   * `structural` is the default because it is the one that costs nothing and because
   * nothing already working should change until a reader asks. `force` is 89 ms on a GPU
   * and 9.7 s without one — paid on demand, and the page says which of the two ran. */
  plateLayout: 'structural',   // 'structural' | 'force'
  collapseUnused: false,  // close the gap a plate nothing is looking at leaves behind
  /* Draw what the selection has lit as labelled boxes rather than as dots.
   *
   * Off by default, and that is design rule 2 rather than timidity: the dots are what
   * fifteen thousand nodes can be drawn as at all (rule 18), and boxes are an order of
   * magnitude larger, so this is a second way of looking rather than a better one. It is a
   * switch in the controls box beside `plates`, because it is something a reader flips
   * while reading and not a preference they set once. */
  diagram: false,
  /* Which compartment the Diagram mode has open. Persisted because it is where the reader
     was, and coming back to a different compartment than you left is the same forgetting
     `codeFile` exists to prevent. Null means "decide from the selection, or the largest". */
  diagramId: null,
  /* Whether the diagram draws its crossings to other compartments. Off by default:
     drawn, they connect what was disconnected so nothing packs, and on a small
     compartment they outnumber the subject. The count is stated either way. */
  diagramPorts: false,
  /* **`nodeShapes` was a default here and is not one now.** Which shapes the boxes are
   * drawn in, as a set -- `kind` spends the channel on five silhouettes and frees colour to
   * carry what changed (design rule 4); `rect` and `round` are one outline for everything.
   * The reasoning stands and is worth keeping; what does not stand is calling it a setting.
   *
   * No control was ever mounted for it, so this default was the only value it ever held.
   * Left in `DEFAULTS` it did one active harm: `resetSettings` walks these keys, so a reset
   * reported clearing *"which shapes the boxes take"* -- naming a setting the reader had
   * never been offered and could not have changed. A default is a promise that something
   * can be different.
   *
   * The engine keeps its side (`SILHOUETTE`, `Graph.silhouettes`, the `nodeShapes` branch
   * of `setOptions`), and `shell.js` still holds `state.nodeShapes` and hands it over at
   * mount. Restore this entry when the layered-layout view brings the boxes back. */
  /* The cursor over a pickable thing in the diagram, and how thick a flow arrow is drawn.
   * Both design rule 2, and both Tom's, from driving it rather than from reading the CSS.
   *
   * **The hand was the complaint, and it was not about size.** `cursor: pointer` is the
   * web's "this is a link" hand, and a diagram is not a page of links -- it is a drawing
   * you *aim* at. The hand's hotspot is a fingertip whose exact pixel is a guess, and the
   * glyph is broad enough to cover the thing being aimed at, which is worst on precisely
   * the thin target that prompted this. An arrow has a sharp, unambiguous tip; a crosshair
   * has one too and says "precision instrument" besides. All three are defensible and
   * which one *reads* right is a matter of taste, which is what design rule 2 is for.
   *
   * `arrow` is the default because it is what Tom chose. Note what it costs: the hand was
   * also the only thing on the page saying an arrow could be clicked at all, so with it
   * gone the hover highlight is carrying that signal alone -- see `tokens.css`.
   *
   * **Thickness is in user units, not pixels, and that is not a slip of design rule 3.**
   * The drawing carries its own pixel size and `dgmFit()` scales it with a transform, so a
   * stroke here scales with the picture the way every other mark in it does. A rem would
   * scale it with the *chrome* instead, so zooming in would thin the line relative to the
   * boxes beside it. 1 is Graphviz's own default and so is what the drawing has always
   * had -- offered rather than raised, because a heavier line is easier to hit and a
   * lighter picture is easier to read, and only the reader knows which they are doing. */
  /* The topbar search's three flags, and they are the Code box's three under different
   * names. Two boxes that look alike and behave differently is the complaint that produced
   * this whole line of work -- one searches names and one searches text, which is a real
   * difference and stays -- so what *can* be the same is: `Aa`, `|ab|`, `.*`, spelled and
   * behaving identically in both.
   *
   * Kept as their own keys rather than shared with `searchCase`/`searchWord`/`searchRegex`,
   * because the two boxes answer different questions and a reader hunting a name literally
   * while grepping the source by pattern is an ordinary thing to be doing. One switch
   * governing both would make that unreachable (design rule 2's reasoning, inverted). */
  navCase: false,            // `Quaestor` and `quaestor` are different names
  navWord: false,            // `emit`, not `_emit_all`
  navRegex: false,           // and then whole-word is off: a pattern writes its own \b
  diagramCursor: 'arrow',    // 'arrow' | 'crosshair' | 'hand'
  diagramEdgeWidth: 1,       // user units, scaling with the drawing; 1 = Graphviz's default
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
  /* Whether the code browser draws the difference from the compared version over the
   * lines it is showing. On, because a reader who has set a compared version has already
   * said what they are here for -- and off is a real want, because a file with four
   * hundred marked lines is a file whose *code* is harder to read than it was.
   *
   * It says nothing when there is no comparison: with one version there is no overlay to
   * suppress, and a switch that governs nothing is design rule 16's dead control. */
  codeOverlay: true,
  /* Whether the provenance line under the code is open. Remembered because it is the same
     sentence on every file: a reader meets it once and then decides for good. */
  codeProv: true,
  /* Whether the code's margin column is drawn. Remembered because reading code and reading
     marks are different sittings, and a reader who folded it means it. */
  codeMarks: true,
  /* Where the *rail* is — its list, or the open file. Separate from `codeFile`, which is what
     is open: the rail browses while the centre reads. */
  codeRailList: false,
  /* Which of the map's eight documents Document mode has open. A document rather than a
     chooser, because the pane's own claim is *the selection, read as a document, scrolled
     to the routine you have picked* — and a page that opens on a menu cannot do that on
     arrival. `routines` holds a row for the thing most selections are. */
  docId: 'routines',
  /* Which lane of Document mode. `map` is the eight documents this tool generates about the
     program; `program` is the 2,064 the program itself carries. Two subjects sharing a pane
     rather than two views of one thing, so the switch is real and is remembered. */
  docLane: 'map',
  /* Which of the program's own documents is open, '' for the list. */
  docPath: '',
  /* Whether a document's author comments -- HTML comments, hidden by whoever wrote them --
     are shown. Off: `html:false` escapes them into visible prose, and 7,317 of them across
     505 of Mensores' documents would read as body text. Folded, never dropped, and counted
     on the page (design rule 1). */
  docComments: false,
  /* The same question asked of the routine list and the table: do these rows say what the
   * comparison found about them. A **second** switch rather than one governing both, and
   * the reason is what each costs. The code overlay fetches a per-file difference and
   * marks up to four hundred lines; these marks are free, drawn from an answer already
   * held. Wanting the cheap ones in the list while reading clean code is ordinary, and one
   * switch cannot express it.
   *
   * Like its neighbour it governs nothing with one version, and the switch is not drawn. */
  tableOverlay: true,
  /* And the same question asked of the **findings**: does this worklist say what the
   * comparison found about each one -- which of them the compared version also has, and
   * whose count, severity or confidence moved.
   *
   * A third switch for the reason there is a second: what it costs is different again, and
   * it is the most expensive of the three. Findings are not rows to be joined; they are
   * what thirteen detectors conclude, so the compared end means running them over a graph
   * this process has never opened -- 1.3 s to 4.1 s the first time, and nothing at all
   * afterwards. That is why it is fetched when the worklist is *opened* rather than with
   * the cover, and why a reader who does not want to pay it has somewhere to say so.
   *
   * Like both its neighbours it governs nothing with one version, and is not drawn. */
  anomalyOverlay: true,

  /* ── the shell ───────────────────────────────────────────────────────────── */
  theme: 'system',        // 'system' | 'light' | 'dark'
  scale: 1,               // design rule 3: one multiplier over every dimension
  startup: 'cover',       // 'cover' | 'graph'
  mode: 'graph',          // which centre view: 'graph' | 'table' | 'doc'
  menuOrder: 'waysin',    // 'waysin' | 'explore' -- a genuine tie, so both exist
  trailShown: true,
  trailCap: 12,
  density: 'comfortable', // 'compact' | 'comfortable' | 'spacious'
  /* Whether the cover's two ranked lists draw a proportion bar beside their counts.
   *
   * On, because a bar is how a ranked list says *how far ahead* the top one is, which the
   * numbers alone make a reader compute. Off reclaims the column for the **name**, and on a
   * narrow centre pane that is not a small difference: measured at a 315px row, the bar took
   * **104px of it** and the name was left 29px -- `mensores-signator` drawn as `me...r`.
   * Design rule 2: two genuinely different readings of one list, so both exist. */
  coverBars: true,
  /* Whether a way-in row drops its tags to a second line **when the name will not fit
   * beside them**. Conditional rather than always: a short name and its two tags sit on
   * one line comfortably, and giving every row a second line to suit the three that need
   * one spends fourteen rows' height to fix three.
   *
   * Off, because a fixed row height is what makes a ranked list scannable -- the eye runs
   * down a column of names. On, the long ones stop being four characters and an ellipsis. */
  rowTagsWrap: false,
  /* Whether the evidence line under a name wraps instead of ending in an ellipsis.
   *
   * Measured on the cover: **all fourteen rows are truncated**, and the line needs up to
   * 955px in a box 141px wide -- about a sixth of it is on screen. What is cut is often the
   * part that tells two rows apart: five rows here are all named `main` with identical
   * evidence text, and only the file path in the tail distinguishes them.
   *
   * Off, because a rank is meant to be scanned and a wrapped line makes rows of uneven
   * height that the eye has to re-find. The full text is on hover either way, and clicking
   * the row has always shown it whole. */
  coverWhatWrap: false,
  /* Whether a change-worklist band scrolls inside itself instead of running its full
   * length. Off, because rule 8 says a reference list is never bounded and the cap put a
   * 512px scroller inside the page's own 401px one -- scrolling a box to find a box. On
   * keeps all four band headings in reach at once, which is a real preference and not an
   * obviously worse one, so both exist and usage retires the loser (design rule 2). */
  bandScroll: false,

  /* ── what to do when the window is narrower than the thing in it ──────────────
   *
   * Three settings, one subject: a surface that cannot fit what it holds. Each ships
   * **today's behaviour as its default**, because each of the three alternatives is a real
   * preference rather than a repair, and design rule 2 says the usage counter retires the
   * loser rather than an argument. */

  /* What a navigator name does when it is wider than the room left for it.
   *
   * `'over' | 'clip' | 'wrap'`, and `over` is what ships. Measured 2026-09-08: **335 of
   * 1,395 rows print their name straight over their counts, 24%**, worst case **101px of
   * overprint where a 62px box holds 170px of text**. It is neither wrapping nor truncating,
   * whatever the two comments over `.navlabel` used to say: `overflow-wrap: normal` forbids
   * a break inside `_schema_validator`, so the flex item cannot shrink below its min-content
   * width, and `.n` is `flex: none; margin-left: auto`, so it is painted *over* rather than
   * pushed aside. That is why nothing reported it.
   *
   * The default is the defect, deliberately. Both alternatives are mechanisms the stylesheet
   * argued against in writing, so neither is imposed on a reader who has been reading this
   * navigator for a fortnight — and both objections turn out to be answerable:
   *
   * **`clip`** — *"truncating would hide a name with nothing beside it."* It does not: a
   * routine row is `data-card`, so its hover card already carries the leaf name **and** the
   * qualified one, and clicking has always shown it whole.
   *
   * **`wrap`** — *"`do_PO / ST` is worse than small type."* True of a break chosen by where
   * the box ends, which is exactly the argument `breakable()` was written from one surface
   * over. `jointed()` marks the name's own seams with `<wbr>` — after a dot, after an
   * underscore, before a camel hump — so the break lands on `do_ / POST`. The count stays on
   * the first line, which is what the other comment asks for.
   *
   * **And a name with no seam at all was the half that promise did not cover**, found by
   * looking at a screenshot on 2026-09-08 after five controls had been measured clean:
   * `disabled` drawn as `disable / d`, 160 of 1,604 rows on screen. `overflow-wrap:
   * break-word` was doing the work for those, which is the arbitrary break this whole
   * paragraph refuses, in the one place nobody had a seam to point at. Such a name is now
   * divided evenly at the corpus' **own median run of five characters** — 13,175 runs over
   * 4,823 names, longest 15 — with no piece shorter than three, so `adjudicate` breaks
   * `adjud / icate` and `review` breaks `rev / iew`. Names shorter than six cannot be
   * divided without orphaning a letter and keep `break-word` as a floor: 224 of 1,013.
   * A name that *has* seams is untouched, because a mid-run mark would be preferred by the
   * browser over the underscore beside it (rule 1). */
  navName: 'over',

  /* Whether the toolbar shrinks to fit the window instead of running off it.
   *
   * Off, which is today. Measured this session: at `innerWidth 1224` the **document is 1336
   * wide**, so `#settingsBtn` sits off the right edge and is reachable only by scrolling the
   * whole page sideways. Tom: *"keep the top Toolbar items always visible, but smaller."*
   *
   * **Narrower first, and smaller only for what is left** — his call on the mechanism. The
   * search box, the two selects and the right-hand group are given permission to yield width
   * they do not have today, which costs no legibility at all; a local multiplier then takes
   * up whatever the yielding could not, floored at 0.85 and stated when the floor is reached.
   *
   * **It also releases `.app`'s column, and that half is not optional.** `.app` is a grid
   * with one implicit `auto` column and no `min-width: 0` on its children, so the widest of
   * the three rows sets the width of all three. A toolbar that only shrank itself would sit
   * inside a page still 1336 wide with Settings still off the edge — design rule 16 from the
   * layout rather than from the wiring. */
  topFit: false,

  /* Whether the version strip holds to one line and scrolls, instead of wrapping.
   *
   * Off, which is today: `.verstrip` is `flex-wrap: wrap` and its own comment says why —
   * it is prose rather than a row of controls, and the alternative to wrapping is truncating
   * the thing it exists to say. That argument still stands and is still the default.
   *
   * What it does not weigh is the **cost**: `.app`'s middle row is `auto`, so a second line
   * comes off `.body`'s height. On, the strip is one line that clips and scrolls sideways.
   * A genuine trade between two scarce axes, which is design rule 2 exactly. */
  verStrip: false,

  /* Whether the panes stay inside the window when the toolbar does not.
   *
   * Off, which is today. The toolbar running off the window is a behaviour that was chosen
   * -- `topFit` above is the switch for it, and its default is *off*. What was never chosen
   * is that the **panes go with it**: `.app` is a grid whose single column is sized to its
   * widest row, so the toolbar's max-content width is `.body`'s width too, and every rail on
   * the right-hand side is carried out of the window along with it.
   *
   * **A rail is the only way back to a collapsed pane** (design rule 24), so that is not a
   * cosmetic overhang. Measured this session at `innerWidth 1220`, with the legend and the
   * inspector both folded:
   *
   * | | legend rail | inspector rail |
   * |---|---|---|
   * | off, which ships | 1281-1309 | 1309-1337 |
   * | on | 1164-1192 | 1192-1220 |
   *
   * Both are entirely outside the window at the default, and `document.elementFromPoint`
   * returns `null` over either. They are still reachable by scrolling the whole page
   * sideways, which is what makes this a preference and not a repair -- and is why it ships
   * off, beside the three settings it belongs with.
   *
   * **The toolbar keeps running off; it just does it in its own row.** Pinning the column
   * alone would make the toolbar *wrap* instead -- measured 63px to 67px, a third behaviour
   * nobody asked for and one `topFit` exists to rule out. So the row is given the version
   * strip's own clip mechanism: `overflow-x: auto`, with `flex-shrink: 0` on the children so
   * they overflow rather than squeeze (which is `test_the_version_strip_clips_its_children_
   * as_well_as_its_box` one row up). `flex-shrink` and not `flex: none`: `.tb-searchwrap`
   * still has to *grow* into a wide window, and `flex: none` would take that with it.
   *
   * **It composes with `topFit` rather than competing with it**, and the specificity is what
   * makes that true: every `[data-topfit="on"]` rule that hands a child permission to yield
   * is a class selector and outranks `.topbar > *` here, so with both on the toolbar shrinks
   * to fit exactly as it does today and this reaches only what the 0.85 floor could not
   * absorb -- scrolled in the toolbar's own row instead of dragging the page. */
  paneFit: false,

  /* Whether a pane folds itself when the window has no room for it.
   *
   * **On, and it is the only one of the five that ships on** -- Tom's call, 2026-09-08:
   * *"Item 8 should auto-collapse."* Off is what the dashboard did before, which is design
   * rule 2's other half.
   *
   * The four settings above are about a window that is *narrow*; this is about one that is
   * too narrow to hold three panes at all. Until 2026-09-08 two breakpoints in `tokens.css`
   * answered that by setting `display: none` on a pane whose track and whose
   * `state.panels` entry both stayed -- open, undrawn, and with no rail to press, which is
   * design rule 24 broken in the one place it matters most. They were deleted and `.body`
   * was given a centre floor and a horizontal scrollbar instead, so nothing vanishes at any
   * width. That is a floor rather than an answer: at 380px the reader reaches the centre by
   * dragging a bar.
   *
   * So a pane folds *properly* -- the fold that leaves a rail -- when the window is under
   * `NAV_MIN_REM + CENTRE_FLOOR_REM` plus the inspector's track, the inspector first and
   * the navigator second (design rule 25: the primary way in is a pane). Three things make
   * it a rule rather than a rearrangement:
   *
   * - **It is laid over the arrangement, never written into it.** `state.panels` is
   *   untouched, exactly as `inspectorAuto` leaves it, so widening the window gives the
   *   reader back what they had rather than what the rule left.
   * - **A rail the reader presses wins**, for as long as the window stays narrow. Without
   *   that the press opens the pane and the rule folds it in the same frame -- *"which
   *   reads as broken"*, and it is the trap this feature was deferred on for a day.
   * - **Measured off `innerWidth` and the root font size, never in a media query.** A `rem`
   *   inside `@media` resolves against the browser's font size and ignores `:root` (rule
   *   28), so the CSS version of this rule folds at 800px for one reader and 1200px for the
   *   next. That is the same mistake as the breakpoints it replaces, one layer down. */
  paneAuto: true,
  /* The two versions. `baseRev` is the one being read — the whole map shows it — and
   * `comparedRev` is the version it is held against.
   *
   * **Three states, and the third is why this is not just a revision id.** `''` is *nothing
   * chosen yet*, and the dashboard fills it in with the next comparable version so a first
   * visit marks its file list without anyone opening the worklist. `'alone'` is *chosen: on
   * its own*, which that fallback must not touch. They were one value until 2026-09-02, and
   * the cost was the whole "on its own" option: it was offered, selected, and handled, and
   * the comparison came straight back — see the note on `comparedRev` in `shell.js`.
   *
   * `'alone'` cannot collide with a revision: those are instants.
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
  /* Which of the two versions is the newer one. `'auto' | 'yes' | 'no'`.
   *
   * Not something the *store* can see: the only instant it records is when the bytes were
   * read. But the **program** often says, and Tom's rule is that an inference is used only
   * when nothing more obvious is available — so `auto` compares the two versions where
   * both state one, and falls back to "the compared is newer" where they do not. Either
   * way the strip prints which of the two happened.
   *
   * Three states rather than a boolean, and the third is the point: `auto` re-derives when
   * the reader moves to a different pair, where an explicit choice made about one pair
   * would be carried silently onto another (rule 51). Design rule 24's shape — an
   * automatic rule may decide, and an explicit choice outranks it. */
  comparedIsNewer: 'auto',
  /* Which colour set carries the two channels where colour separates one *meaning* from
   * another: the difference channel and severity. Tom's call — colour decisions are
   * personal and belong here, offered as broad sets rather than as a picker per token.
   *
   * `'default'` stamps no attribute at all, so the shipped look is the base token block
   * rather than a special case of itself. The values and the reasoning are in
   * `tokens.css`; nothing about a colour is written down in JavaScript, because the graph
   * already reads its palette off the same tokens and a second table is a second answer. */
  palette: 'default',      // 'default' | 'safe' | 'muted'
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
  colWidths: { q: 26, why: 30, fan: 5, chg: 7 },  // the columns the routine list can fill
  // today; lines/returns/params/touches come back with an endpoint that serves them
  /* `value` open because it is the whole point of a constant's pane; `reads` closed because
     it states a limit rather than a finding, and a caveat that opens itself every time
     reads as the answer. Both are named here rather than left to `state.insp[key]` being
     `undefined`: an unlisted key toggles from nothing on its first click -- so it starts
     closed whatever it wanted -- and "Collapse all" cannot see it until someone has opened
     it once, because it flips `Object.values(state.insp)` and an absent key is not among
     them.

     **Three keys were in exactly that position, and the record named one.** `holds` is the
     fold pane's contents and a plate's; `stands` is what a *merged* plate stands for;
     `calls` is the call sites behind an arrow. Each is the answer its pane exists to give
     rather than a caveat on one it already had -- `loops` and `shape`'s test, one pane
     over -- so all three open. A section a reader has to find before it says anything is a
     feature nobody meets.

     `test_every_inspector_section_declares_its_default` is what stops the fourth: it reads
     the `sec("…")` keys out of the shell and requires each to be named here, in the
     direction that catches an addition rather than a removal.

     `loops` and `shape` are ALGORITHMS chunk 5's, and both open: they are the answer the
     pane gained rather than a caveat on one it already had, and a section that has to be
     found before it says anything is a feature nobody meets. Named here for the reason
     above -- `sec()` renders `data-open="undefined"` for an unlisted key, which the
     stylesheet does not collapse and the toggle cannot change on its first click. */
  insp: { in: true, out: true, touches: true, gov: true, sig: false,
          value: true, reads: false, loops: true, shape: true, cols: true,
          holds: true, stands: true, calls: true },
  sortKey: 'fan',
  sortAsc: false,

  /* ── egress, and what has been looked at ─────────────────────────────────── */
  egress: 'off',          // design rule 14: scoped, never a switch, off until turned on
  aiOps: { harvest: true },
  triage: {},             // finding id -> 'ack' | 'notbug' | 'tooldefect'
  /* Words the reader put back into the glossary's worklist by hand, lowercased.
     889 of Society's words occur only inside a compound constant name -- `CHARS` is the
     unit on somebody else's constant -- and holding them back is what makes the worklist
     readable. But the split cannot tell `MENSORES_MAX_LEN`'s subject from its unit, and
     that word may occur nowhere else in the program: only a person can say which is
     which, so the judgement is offered back rather than kept. Tom, 2026-09-08.

     A decision about the *program*, like `triage` beside it, so it is stored per program
     and outlives the visit. */
  promoted: {},           // word (lowercased) -> true
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

/* The blob one version below this one, if `CARRY_FORWARD` says this bump may read it.
 *
 * **The old key is left where it is.** Deleting it would be a read path destroying the
 * evidence it read -- rule 20 exactly, and the cost of being wrong is asymmetric: the
 * saving is a few kilobytes, and the loss is every arrangement a reader has made, gone the
 * moment they run an older build. Orphaned blobs are the cheaper mistake, and they are why
 * `dunneflow:mensores:v1` through `v3` are still readable on a machine that has had this
 * dashboard since the first bump.
 *
 * Only the version immediately below, and only when it is named: a v2 blob is not
 * something this bump has any claim to understand.
 */
function carryForward(program) {
  const spec = CARRY_FORWARD[SETTINGS_VERSION - 1];
  if (!spec) return { raw: null, carried: null };
  const raw = window.localStorage.getItem(
    `dunneflow:${program}:v${SETTINGS_VERSION - 1}`);
  if (!raw) return { raw: null, carried: null };
  return { raw, carried: { from: SETTINGS_VERSION - 1, dropped: spec.drop, why: spec.why } };
}

function loadSettings(program) {
  const out = freshDefaults();
  let raw = null;
  let carried = null;
  try {
    raw = window.localStorage.getItem(storageKey(program));
    if (!raw) ({ raw, carried } = carryForward(program));
  } catch {
    return out;                       // storage unavailable; defaults are a fine answer
  }
  /* What was carried and what was dropped, for whoever is about to render the surface the
   * dropped key belonged to. Not a persisted setting: `persist()` writes the `PERSISTED`
   * list and nothing else, so this rides along without ever being written back. Said at
   * all because a worklist that has quietly forgotten every decision and one nobody has
   * triaged yet are identical to look at, and only one of them is a claim (design rule 1,
   * and `resetSettings`'s own reason for naming what it cleared). */
  if (carried) out.__carried = carried;
  if (!raw) return out;
  let saved;
  try {
    saved = JSON.parse(raw);
  } catch {
    return out;                       // unparseable is the same as absent
  }
  if (!saved || typeof saved !== 'object') return out;
  /* Dropped **before** the merge rather than deleted after it, so a dropped group cannot
   * reach `Object.assign` and leave half of itself behind. */
  if (carried) for (const k of carried.dropped) delete saved[k];
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
    level: 'how much detail the stack draws', minDisk: 'the smallest plate drawn',
    sortMode: 'sort', filterMode: 'filter mode', direction: 'direction',
    nodeSpacing: 'node spacing', nodeScaling: 'node sizing',
    picks: 'selection', followMode: 'following a neighbour',
    spreadX: 'spread across', spreadY: 'spread deep', spreadZ: 'spread between plates',
    plateSize: 'how much a plate\'s width says about what it holds',
    plateLayout: 'how a plate arranges what it holds',
    collapseUnused: 'collapsed plates',
    diagram: 'the plate drawn as a diagram',
    diagramId: 'which compartment the diagram has open',
    diagramPorts: 'whether the diagram draws its crossings',
    navCase: 'the search matching capitals exactly',
    navWord: 'the search matching whole words',
    navRegex: 'the search reading a regular expression',
    diagramCursor: 'the cursor over the diagram',
    diagramEdgeWidth: 'how thick a flow arrow is drawn',
    showPlates: 'the plates themselves', edgesInMotion: 'edges while moving',
    pointerShown: 'the you-are-here pointer', pointerColor: 'the pointer colour',
    pointerPlace: 'where the pointer stands',
    reticuleShown: 'the focus reticule', focusLocked: 'focus locked to the selection',
    mode: 'centre view', panels: 'panel layout',
    inspectorAuto: 'auto-collapse the inspector', navWidth: 'navigator width',
    codeWidth: 'code pane width', codeFile: 'which file the code pane has open',
    codeOverlay: 'the change overlay on the code',
    codeProv: 'the provenance line under the code',
    codeMarks: 'the margin column beside the code',
    codeRailList: 'whether the code rail is showing its file list',
    docId: 'which of the map\'s documents is open',
    docLane: 'which lane of document mode',
    docPath: 'which of the program\'s own documents is open',
    docComments: 'whether a document shows its author comments',
    tableOverlay: 'the change overlay on the routine list and the table',
    anomalyOverlay: 'the change overlay on the findings',
    navGroups: 'how many navigator groups open at once', navOpen: 'which groups are open',
    navCap: 'how many routines a package lists',
    graphLayout: 'graph layout', graphTheme: 'graph theme',
    theme: 'theme', palette: 'the colour set', scale: 'interface scale',
    startup: 'startup screen',
    menuOrder: 'menu order', trailShown: 'the trail', trailCap: 'how many steps the trail shows',
    density: 'row density', bandScroll: 'scrolling change bands',
    coverBars: 'proportion bars on the cover',
    rowTagsWrap: 'tags on their own line', coverWhatWrap: 'wrapped evidence lines',
    navName: 'what a long navigator name does',
    topFit: 'the toolbar fitting the window',
    verStrip: 'the version strip on one line',
    paneFit: 'the panes keeping inside the window',
    paneAuto: 'a pane folding when the window cannot fit it',
    baseRev: 'which version is being read', comparedRev: 'what it is compared with',
    comparedIsNewer: 'which version is taken to be newer',
    searchCase: 'case-sensitive search', searchWord: 'whole-word search',
    searchRegex: 'regular-expression search',
    ambient: 'ambient badges', hideInferred: 'inferred edges',
    colWidths: 'column widths', insp: 'inspector sections',
    sortKey: 'table sort', sortAsc: 'table sort direction',
    egress: 'egress posture', aiOps: 'model operations',
    triage: 'triage decisions', pins: 'the shelf', usage: 'usage counts',
    promoted: 'words put back into the glossary worklist',
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
