/* Analysing a directory: the dialog, the pre-flight, the panel and the stop button.
 *
 * Its own file for `prose.js`' reason rather than for tidiness. **Two pages need all of
 * it** -- the shell, where it is the last option in the program select, and the start
 * page, where it is the only way a first-time reader gets a map at all. A second copy in
 * the surface that is somebody's first minute with this tool is rule 51's own defect in
 * the worst place it could be put.
 *
 * The boundary is `graph.js`': this owns a gesture and knows nothing about the page it
 * sits in. What it needs from a host arrives as four functions and nothing else --
 *
 *   used(key)          the usage counter, or a no-op
 *   changed()          repaint whatever else the host draws
 *   clearOverlays()    take down anything that would sit *over* this dialog
 *   openProgram(name)  open the program an analysis just made
 *
 * -- and `esc` is local, exactly as it is in `prose.js`: a module that turns data into
 * markup carries its own escaper rather than reaching for the page's.
 *
 * `clearOverlays` exists because of a real defect and not for symmetry. The switch scrim
 * is drawn at 96/97 and this dialog at 92/93, so a dialog opened from underneath a switch
 * renders perfectly, greyed, and swallows every click. The shell takes its scrim down; the
 * start page has none and says so with an empty function.
 */
(function () {
  "use strict";

  const esc = (s) => String(s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* Never null, so nothing here has to guard. A host that wires nothing gets a working
     dialog that counts no usage and repaints nothing else, which is exactly right for a
     page that has nothing else. */
  const HOST = {
    used: () => {},
    changed: () => {},
    clearOverlays: () => {},
    openProgram: () => {},
    /* What is true of *this page* while an analysis runs. A claim about the host, so the
       host makes it; the default says only what is true of every page. */
    whileRunning: () => "It runs behind this page — you can carry on.",
  };

  /* -- Analysing a directory -------------------------------------------------
   *
   * The last option in the program select, and the one that makes a program rather than
   * choosing one. It was in the ratified artifact from the beginning and did nothing there
   * either; it is added here only now, because a third option that does nothing is exactly
   * the defect the selector was built to fix (design rule 16).
   *
   * **Not the switch overlay, and that is the whole shape of it.** A base switch blocks the
   * page because every count underneath belongs to the version being replaced. This reads
   * some *other* tree into some *other* directory: nothing on screen becomes untrue, so
   * nothing on screen is taken away. A dismissible panel, a separate slot on the server, and
   * the reader keeps working for the ninety seconds it takes.
   */
  /* A value a directory name **cannot** be, rather than one it is unlikely to be. A program
     name is one path segment, and `analysis.check` refuses any name carrying a separator — so
     a leading slash is the one thing that can never arrive here as a real program (rule 30: a
     label is not an identity, and a sentinel that a name could equal is exactly that mistake).
     It was " analyze" for an hour, which is only unlikely. */
  const ANALYZE_OPTION = "/analyze";

  /* The dialog's fields while it is open, and `null` when it is not. Module-level like
     `REBUILD` rather than in `state`: it belongs to this gesture, not to this program, and
     `settings.js` must not persist a half-typed path across a reload. */
  let ANALYZE = null;
  /* What the server says about the fields as they are typed -- `{ok, refusal, note}` from
     `analysis.check`, which is the same function the POST will use. Asked rather than
     guessed, so the sentence under the field and the sentence on the button cannot differ
     (rule 41). */
  let ANALYZE_CHECK = null;
  let ANALYZE_SEQ = 0;
  /* A run in flight, or the last one to finish. Its own state, not `REBUILD`: they are two
     slots on the server for the reason stated there, and sharing one here would put an
     analysis behind the switch scrim after all. */
  let ANALYSIS = null;

  /* **A run outlives the page that started it, so the page has to ask.**
   *
   * `pollAnalysis` was called from `startAnalyze` and nowhere else, and nothing asked at boot
   * -- so a reload during an analysis left the run going with no panel anywhere, and the next
   * attempt was refused by a sentence naming a job the reader could not see. The server is
   * the truth about what is running, exactly as `/api/base` is the truth about which version
   * is on screen rather than anything the browser remembered.
   *
   * Only a **live** run is picked up. A finished or failed one belongs to the session that
   * asked for it; re-raising it on every reload afterwards would be a panel nobody can get
   * rid of. */
  async function resumeAnalysis() {
    let d;
    try {
      d = await fetch("/api/analysis").then(r => r.json());
    } catch {
      return;
    }
    const a = d.analysis || {};
    if (!a.running) return;
    ANALYSIS = Object.assign({}, a,
      { since: Date.now() - (Number(a.running_for) || 0) * 1000 });
    paintAnalysis();
    pollAnalysis(a.program || "");
  }

  function openAnalyze(prefill) {
    ANALYZE = Object.assign({ path: "", name: "", docs: true, busy: false, blocked: null,
                             pickfail: "" }, prefill || {});
    ANALYZE_CHECK = null;
    paintAnalyze();
    askAnalyzeCheck();
    const el = document.getElementById("anPath");
    if (el) { el.focus(); el.select(); }
  }

  function closeAnalyze() {
    ANALYZE = null;
    ANALYZE_CHECK = null;
    paintAnalyze();
  }

  /* The pre-flight, from the server, debounced by a sequence number rather than a timer.
   *
   * A number rather than `clearTimeout` because the hazard is not extra requests, it is an
   * **older answer landing after a newer one** -- the reader types `/tmp/x` and then
   * `/tmp/xy`, and the first reply arrives second and says the directory does not exist.
   * Every reply checks it is still the newest before it is allowed to speak (rule 49's
   * shape: a stale value that looks plausible has hidden the thing it was meant to report). */
  async function askAnalyzeCheck() {
    if (!ANALYZE) return;
    const seq = ++ANALYZE_SEQ;
    const { path, name } = ANALYZE;
    if (!path.trim()) { ANALYZE_CHECK = null; paintAnalyze(); return; }
    let d;
    try {
      d = await fetch("/api/analysis?path=" + encodeURIComponent(path) +
                      "&name=" + encodeURIComponent(name)).then(r => r.json());
    } catch {
      /* Left as it was rather than replaced with an invented verdict. The button asks the
         server again anyway, and that answer is the one that decides. */
      return;
    }
    if (seq !== ANALYZE_SEQ || !ANALYZE) return;
    ANALYZE_CHECK = d.check || null;
    paintAnalyze();
  }

  /* The name a blank field will use, shown rather than left to be discovered.
   *
   * The server does the same thing (`check` falls through to `source.name`), so this is the
   * *same* rule in two places -- which is only safe because what is drawn is a placeholder
   * the reader can see and correct, not a second decision. */
  function analyzeLeaf(path) {
    const parts = String(path || "").replace(/[/\\]+$/, "").split(/[/\\]/);
    return parts[parts.length - 1] || "";
  }

  function analyzeDialog() {
    if (!ANALYZE) return "";
    const a = ANALYZE;
    const c = ANALYZE_CHECK;
    const leaf = analyzeLeaf(a.path);
    /* Blocked until the server has said yes. A dialog that lets the button be pressed and
       then reports the refusal has made the reader do the work twice -- and `check` already
       knows the answer while they are still typing. */
    const ready = !!(a.path.trim() && c && c.ok && !a.busy);
    return `
    <div class="analyze-scrim" data-closeanalyze></div>
    <div class="analyze" role="dialog" aria-modal="true" aria-label="Analyse a directory">
      <h2 class="analyze-title">Analyse a directory</h2>

      <label class="analyze-field">
        <span>Directory to read</span>
        <div class="analyze-pick">
          <input type="text" id="anPath" data-anfield="path" spellcheck="false"
                 autocomplete="off" value="${esc(a.path)}"
                 placeholder="/Users/you/code/some-project/src">
          <!-- **Beside the field, never instead of it** (design rule 2). A browser cannot
               hand a server what a folder picker chose, so the picker is the operating
               system's, run by the server process. Typing the whole path still works and is
               still the thing the hint describes; this is the shorter way to the same
               value. Disabled while a run is starting, like Analyse beside it. -->
          <button class="linkbtn" data-anpick${a.busy ? " disabled" : ""}>Choose&hellip;</button>
        </div>
        <p class="hint">The whole path, as this machine sees it &mdash; the server reads the
           tree itself, so a path relative to your terminal would mean nothing to it.${
           a.pickfail ? ` <span class="analyze-refusal">${esc(a.pickfail)}</span>` : ""}</p>
      </label>

      <label class="analyze-field">
        <span>Call it</span>
        <input type="text" id="anName" data-anfield="name" spellcheck="false"
               autocomplete="off" value="${esc(a.name)}"
               placeholder="${esc(leaf) || "the directory&rsquo;s own name"}">
        <p class="hint">This names the directory the map is written to, beside the programs
           already in the list.</p>
      </label>

      <label class="analyze-check">
        <input type="checkbox" data-anfield="docs"${a.docs ? " checked" : ""}>
        <span>Read the documentation too</span>
      </label>

      ${c && c.refusal ? `<p class="analyze-refusal">${esc(c.refusal)}</p>` : ""}
      ${c && c.note ? `<p class="analyze-note">${esc(c.note)}</p>` : ""}
      ${a.blocked ? `<div class="analyze-blocked">
        <p>${esc(a.blocked)}</p>
        <div class="an-foot">
          <button class="linkbtn" data-anstop>Stop it</button>
          <span class="hint">Or leave it — this dialog stays, and Analyse works again as
             soon as it finishes.</span>
        </div></div>` : ""}

      <div class="analyze-foot">
        <button class="linkbtn" data-anstart${ready ? "" : " disabled"}>${
          a.busy ? "Starting&hellip;" : "Analyse"}</button>
        <button class="linkbtn" data-closeanalyze>Cancel</button>
        <!-- **The host's sentence, because it is a claim about the host's page.** The
             shell says the map you are reading stays open and stays true, which is the
             whole reason an analysis is a panel rather than a scrim. On the start page
             there *is* no map you are reading, and saying so anyway would be a false
             sentence in the one surface a first-time reader sees (rule 13). -->
        <span class="hint">${esc(HOST.whileRunning())}</span>
      </div>
    </div>`;
  }

  /* Its own mount, like `paintRebuild`: `render()` rewrites four panes and the navigator, and
     a repaint of those under a half-typed field would take the caret with it (rule 78's
     family -- and the corpus filter paid for this one already). */
  function paintAnalyze() {
    let m = document.getElementById("analyzeMount");
    if (!m) {
      m = document.createElement("div");
      m.id = "analyzeMount";
      document.body.appendChild(m);
    }
    /* The caret, kept across a repaint. The verdict under the field arrives while somebody
       is still typing into it, so this element is rewritten mid-word -- and rewriting an
       `<input>` puts the caret at the end of whatever it now holds. Restored by id and
       offset rather than by refocusing, because focus alone moves it. */
    const active = document.activeElement;
    const keep = (active && active.dataset && active.dataset.anfield)
      ? { id: active.id, start: active.selectionStart, end: active.selectionEnd } : null;
    m.innerHTML = analyzeDialog();
    if (keep) {
      const back = document.getElementById(keep.id);
      if (back) {
        back.focus();
        try { back.setSelectionRange(keep.start, keep.end); } catch { /* not a text input */ }
      }
    }
  }

  /* Ask the operating system for a directory, and put what it says in the field.
   *
   * **Into the field, never straight into a run.** What comes back is a value the reader
   * can see, correct and think about, exactly as if they had typed it -- and it goes
   * through the same pre-flight, so the picker cannot produce a path the typed field would
   * have refused (rule 41).
   *
   * Cancelling is the ordinary way out of a dialog and leaves everything as it was. A real
   * failure is **said**, because a button that reports nothing and does nothing is
   * indistinguishable from one that worked (design rule 16).
   */
  async function pickDirectory() {
    if (!ANALYZE || ANALYZE.busy) return;
    ANALYZE.pickfail = "";
    let d;
    try {
      d = await fetch("/api/pickdir", { method: "POST" }).then(r => r.json());
    } catch (err) {
      ANALYZE.pickfail = "the picker could not be asked: " + err.message;
      paintAnalyze();
      return;
    }
    if (!ANALYZE) return;             // cancelled while the dialog was open
    if (d.picked) {
      ANALYZE.path = d.picked;
      paintAnalyze();
      askAnalyzeCheck();
      return;
    }
    ANALYZE.pickfail = d.reason || "";
    paintAnalyze();
  }

  /* Start it, and hand over to the panel. */
  async function startAnalyze() {
    if (!ANALYZE || ANALYZE.busy) return;
    const { path, name, docs } = ANALYZE;
    ANALYZE.busy = true;
    paintAnalyze();
    let d;
    try {
      d = await fetch("/api/analyze?path=" + encodeURIComponent(path) +
                      "&name=" + encodeURIComponent(name) +
                      "&docs=" + (docs ? "1" : "0"), { method: "POST" }).then(r => r.json());
    } catch (err) {
      ANALYZE.busy = false;
      ANALYZE_CHECK = { ok: false, refusal: "the server could not be asked: " + err.message,
                        note: "" };
      paintAnalyze();
      return;
    }
    if (!d.started) {
      /* Back into the dialog rather than into the panel. Nothing is running, so a panel
         reporting a failure would be reporting one about a run that never began -- the
         distinction `_started` makes on the server, kept on this side too. */
      ANALYZE.busy = false;
      ANALYZE_CHECK = { ok: false,
                        refusal: d.reason || "the analysis was refused, with no reason given",
                        note: "" };
      /* **A refusal that can be acted on carries the action.** "An analysis of X is already
         running" was true and a dead end: the one thing the reader might want to do about it
         is end it, and nothing on the page offered that. Asked rather than parsed out of the
         sentence -- the server's words are written for the reader, not for this (rule 30). */
      ANALYZE.blocked = null;
      await watchBlocked();
      paintAnalyze();
      return;
    }
    const asked = (name || analyzeLeaf(path));
    closeAnalyze();
    ANALYSIS = Object.assign({ state: "working", step: "", done_steps: 0, steps: 0,
                               detail: "" }, d,
                             { program: asked, since: Date.now() });
    paintAnalysis();
    pollAnalysis(asked);
  }

  /* **What is blocking this dialog, kept current for as long as it is on screen.**
   *
   * Two things go wrong with a one-shot answer, and both are the same defect: a claim nobody
   * keeps. The elapsed time freezes at the instant the reader pressed Analyse, so a dialog
   * left open says *"going 4.8 s"* about a run five minutes old -- and the sentence beside it
   * promises *"Analyse works again as soon as it finishes"*, which nothing was implementing.
   * A control that states a behaviour and does not have it is design rule 16 in prose (rule
   * 44's family).
   *
   * So it re-asks while it is blocked, and **clears itself the moment the run ends** -- at
   * which point `paintAnalyze` re-enables the button, which is what the sentence said would
   * happen. Stops when the dialog closes, because `ANALYZE` going null ends the chain. */
  async function watchBlocked() {
    if (!ANALYZE) return;
    let live;
    try {
      live = (await fetch("/api/analysis").then(r => r.json())).analysis || {};
    } catch {
      return;                       /* the refusal already on screen says what happened */
    }
    if (!ANALYZE) return;           /* closed while we were asking */
    if (!live.running) {
      /* It finished. Drop the block and let the reader try again -- and say so, because a
         refusal that silently becomes stale is indistinguishable from one still in force. */
      if (ANALYZE.blocked) {
        ANALYZE.blocked = null;
        ANALYZE_CHECK = null;
        askAnalyzeCheck();
      }
      return;
    }
    const quiet = Number(live.silent_for) || 0;
    ANALYZE.blocked =
      `An analysis of ${live.program} is running — ${live.step}, step ${
        (Number(live.done_steps) || 0) + 1} of ${live.steps}, going ${
        forHowLong(live.running_for)}` +
      (quiet > 45 ? `, and nothing new for ${forHowLong(quiet)}.` : ".");
    paintAnalyze();
    window.setTimeout(watchBlocked, 1500);
  }

  /* Ask the server to end the run. It answers with what actually happened -- *stopped* or
   * *killed, it did not stop when asked* -- and the poll already running renders the child's
   * own last word a moment later. Nothing is assumed here: a Stop that failed must not leave
   * a panel claiming success (rule 49). */
  async function stopAnalysis() {
    let d;
    try {
      d = await fetch("/api/analyze/stop", { method: "POST" }).then(r => r.json());
    } catch (err) {
      ANALYSIS = Object.assign({}, ANALYSIS,
        { state: "failed", reason: "the server could not be asked to stop it: " + err.message });
      paintAnalysis();
      return;
    }
    if (!d.started) {
      /* Nothing was running -- which the reader could not have known, because the panel they
         pressed was drawn from a report that had outlived its process. Say so and clear it
         rather than leaving a Stop button over a job that is not there. */
      ANALYSIS = Object.assign({}, ANALYSIS, { state: "stopped",
        reason: d.reason || "there was nothing running to stop" });
    }
    paintAnalysis();
  }

  /* Watch it. `pollBase`'s shape and none of its ending: a finished analysis **does not
     reload the page**, because it did not change what this page is showing. It offers. */
  function pollAnalysis(name) {
    const since = ANALYSIS ? ANALYSIS.since : Date.now();
    const tick = async () => {
      let d;
      try {
        d = await fetch("/api/analysis").then(r => r.json());
      } catch (err) {
        ANALYSIS = { program: name, state: "failed", since: since,
                     reason: "lost contact with the server: " + err.message };
        paintAnalysis();
        return;
      }
      const a = d.analysis || {};
      ANALYSIS = Object.assign({}, a, { program: a.program || name, since: since });
      if (a.state === "done") {
        /* The list, refreshed, so the program that was just made is in the control before
           the reader is invited to open it. Without this the offer below names something the
           `<select>` has never heard of. */
        await loadPrograms();
        paintAnalysis();
        return;
      }
      paintAnalysis();
      /* Three endings, not one. `stopped` settles like `failed` does -- the run is over and
         polling a finished slot for ever is a request every 600 ms that can never say
         anything new. */
      if (a.state === "failed" || a.state === "stopped") return;
      window.setTimeout(tick, 600);
    };
    window.setTimeout(tick, 400);
  }

  /* How long, in words. `4 m 10 s` rather than `250.4 s`, because the number a reader is
     weighing is *has this been quiet too long*, and minutes are the unit that question is
     asked in. Under a minute stays in seconds, where a decimal still means something. */
  function forHowLong(secs) {
    const n = Number(secs) || 0;
    if (n < 60) return `${n.toFixed(1)} s`;
    const m = Math.floor(n / 60);
    return `${m} m ${Math.round(n - m * 60)} s`;
  }

  function analysisPanel() {
    if (!ANALYSIS) return "";
    const a = ANALYSIS;
    const secs = (Date.now() - (a.since || Date.now())) / 1000;
    const steps = Number(a.steps) || 0;
    const done = Number(a.done_steps) || 0;
    /* No bar until the child has said how many steps it is taking, for `rebuildPanel`'s
       reason and one more of its own: the count depends on the flags, so a bar drawn against
       a guess would be a bar against a total this run is never going to reach (rule 44). */
    const pct = steps ? Math.round((done / steps) * 100) : 0;

    let head = "Analysing";
    let body = "";
    if (a.state === "stopped") {
      /* Its own head and its own words. A run the reader ended on purpose must not be
         reported back to them as one that broke -- they know what they did, and being told
         it "did not finish" reads as the tool disagreeing with them. */
      head = "Stopped";
      body = `<p class="an-step">${esc(a.reason || "it was stopped")}</p>
        <div class="an-foot">
          <button class="linkbtn" data-anagain="${esc(a.program || "")}">Analyse it again</button>
          <button class="linkbtn" data-andismiss>Close</button>
        </div>`;
    } else if (a.state === "failed") {
      head = "That analysis did not finish";
      body = `<p class="an-why">${esc(a.reason || "no reason was given")}</p>
        <p class="hint">Nothing was added to the program list. The map you are reading was
           never touched.</p>
        <div class="an-foot"><button class="linkbtn" data-andismiss>Close</button></div>`;
    } else if (a.state === "done") {
      head = "Read";
      const bits = [];
      if (a.files) bits.push(`${Number(a.files).toLocaleString()} files`);
      if (a.routines) bits.push(`${Number(a.routines).toLocaleString()} routines`);
      if (a.documents) bits.push(`${Number(a.documents).toLocaleString()} documents`);
      body = `<p class="an-step">${bits.length ? esc(bits.join(" · ")) : "finished"}
                · ${secs.toFixed(1)} s</p>
        <p class="hint">Opening it reloads the page, because a program switch cannot keep
           the selection, the trail or the version you are on.</p>
        <div class="an-foot">
          <button class="linkbtn" data-anopen="${esc(a.program || "")}">Open it</button>
          <button class="linkbtn" data-andismiss>Not now</button>
        </div>`;
    } else {
      /* **The silence is stated, and nothing acts on it.** A run is legitimately quiet for
         tens of seconds -- resolving the Society tree says nothing at all for a while -- so a
         server that decided for itself when a run had hung would kill healthy work. What the
         reader gets is the fact and the button; the judgement is theirs. */
      const quiet = Number(a.silent_for) || 0;
      body = `<div class="rebuild-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100"
                aria-valuenow="${pct}"><i style="width:${steps ? pct : 0}%"></i></div>
        <p class="an-step">${steps
            ? `${esc(a.step || "")}${a.detail ? " — " + esc(a.detail) : ""} — step ${
                done + 1} of ${steps}`
            : "asking the server&hellip;"} · ${forHowLong(a.running_for ?? secs)}</p>
        ${quiet > 45 ? `<p class="an-quiet">Nothing new for ${forHowLong(quiet)}. Some steps
           are quiet for a while — resolving a large program says nothing until it is
           done — so this may be working. It may also be stuck.</p>` : ""}
        <p class="hint">The map on screen is untouched. Keep reading.</p>
        <div class="an-foot">
          <button class="linkbtn" data-anstop>Stop it</button>
          <span class="hint">What it has written stays, marked unfinished.</span>
        </div>`;
    }
    return `<div class="analysispanel" role="status" aria-live="polite">
        <h3>${head}</h3>
        <p class="an-name">${esc(a.program || "")}</p>
        ${body}
      </div>`;
  }

  function paintAnalysis() {
    let m = document.getElementById("analysisMount");
    if (!m) {
      m = document.createElement("div");
      m.id = "analysisMount";
      document.body.appendChild(m);
    }
    m.innerHTML = analysisPanel();
  }

  /* One delegated listener for both surfaces, because both mounts are rewritten on every
     poll and a listener bound to an element inside them would be bound to a corpse (rule 78's
     neighbourhood). */
  document.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t || !t.closest) return;
    if (t.closest("[data-closeanalyze]")) { closeAnalyze(); return; }
    if (t.closest("[data-anpick]")) { HOST.used("program:analyze:pick"); pickDirectory(); return; }
    const start = t.closest("[data-anstart]");
    if (start) {
      if (!start.disabled) { HOST.used("program:analyze"); startAnalyze(); }
      return;
    }
    if (t.closest("[data-andismiss]")) { ANALYSIS = null; paintAnalysis(); return; }
    if (t.closest("[data-anstop]")) { HOST.used("program:analyze:stop"); stopAnalysis(); return; }
    const again = t.closest("[data-anagain]");
    if (again) {
      /* Straight back into the dialog with the name filled and the **path blank**: a map
         records a tree's leaf and never its path (rule 60), so there is nothing honest to
         pre-fill it with. Same bargain as About's *Analyse this again*. */
      const name = again.getAttribute("data-anagain") || "";
      ANALYSIS = null;
      paintAnalysis();
      /* **And the switch overlay, if that is where this was pressed.** It is drawn at 96/97
         and the analyse dialog at 92/93, so leaving it up would put the dialog underneath a
         scrim -- rendered perfectly, greyed, and swallowing every click. That is the exact
         defect the layer note in `tokens.css` was written from, and this is the second window
         that can open a third. */
      HOST.clearOverlays();
      openAnalyze({ name: name });
      return;
    }
    const open = t.closest("[data-anopen]");
    if (open) {
      const name = open.getAttribute("data-anopen");
      ANALYSIS = null;
      paintAnalysis();
      if (name) HOST.openProgram(name);
    }
  });

  document.addEventListener("input", (ev) => {
    const t = ev.target;
    if (!ANALYZE || !t || !t.dataset || !t.dataset.anfield) return;
    const f = t.dataset.anfield;
    if (f === "docs") return;              // a checkbox answers on `change`, below
    ANALYZE[f] = t.value;
    askAnalyzeCheck();
  });

  document.addEventListener("change", (ev) => {
    const t = ev.target;
    if (!ANALYZE || !t || !t.dataset || t.dataset.anfield !== "docs") return;
    /* The verdict is about the path and the name; the documentation switch changes nothing
       about whether this may run, so it does not ask again. */
    ANALYZE.docs = !!t.checked;
    paintAnalyze();
  });

  document.addEventListener("keydown", (ev) => {
    if (!ANALYZE) return;
    if (ev.key === "Escape") { closeAnalyze(); return; }
    if (ev.key === "Enter" && ANALYZE_CHECK && ANALYZE_CHECK.ok && !ANALYZE.busy) {
      ev.preventDefault();
      HOST.used("program:analyze");
      startAnalyze();
    }
  });

  /* The one global, on `settings.js`' and `graph.js`' precedent: classic scripts sharing
     one scope, and a single named object rather than a dozen loose functions. */
  window.DunneFlowAnalyze = {
    OPTION: ANALYZE_OPTION,
    wire(host) { Object.assign(HOST, host || {}); },
    open(prefill) { openAnalyze(prefill); },
    close() { closeAnalyze(); },
    resume() { return resumeAnalysis(); },
    isOpen() { return !!ANALYZE; },
    running() { return ANALYSIS; },
  };
})();
