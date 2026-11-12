/* The start page: what is here, and the two things that can be done about it.
 *
 * Small on purpose. Everything hard — the analyse dialog, the pre-flight, the progress
 * panel, the stop button — is `analyze.js`, shared with the shell; this page supplies the
 * four host functions that module cannot know and draws a list.
 *
 * **One route lists programs, and it is the shell's.** `/api/programs` answers with nothing
 * open: `serving` is empty, `files` is null for every row, and `root` rides along. A second
 * endpoint for "what is here at boot" would be a second answer to one question, and the two
 * would drift the first time a column was added to either (rule 51).
 */
(function () {
  "use strict";

  const esc = (s) => String(s).replace(/[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const Analyze = window.DunneFlowAnalyze;
  let ROOT = "";
  let SERVING = "";        // the program this server has open, or "" — see `paintOpen`
  let OPENING = "";        // the program being opened, so the list can say which

  /* This page has no scrim, no usage counter and nothing else to repaint, and every one of
     those is a real answer rather than a gap. `changed` reloads the list because the only
     thing that changes here is which programs exist.
   *
   * **Returned, not fired and forgotten.** `analyze.js` awaits this before it paints the
     offer to open what an analysis just made, so a `load()` whose promise is dropped means
     the offer is drawn against a list that has not landed. This wiring was always right about
     *what* to do; it is the one line of the pair that never needed changing. */
  Analyze.wire({
    used: () => {},
    changed: () => load(),
    clearOverlays: () => {},
    openProgram: (name) => open(name),
    /* No map is open, so the shell's sentence would be a false one on the surface a
       first-time reader sees. What is true here is that the list fills in when it lands. */
    whileRunning: () => "It runs here — the program appears in the list when it is done.",
  });

  /* -- what is here ------------------------------------------------------- */

  async function load() {
    let d;
    try {
      d = await fetch("/api/programs").then(r => r.json());
    } catch (err) {
      /* The server is this page's only source of truth, and a page that silently shows an
         empty list when it could not ask is the exact failure design rule 21 is about: a
         blank canvas that does not say why it is blank. */
      document.getElementById("lead").textContent =
        "the server could not be asked: " + err.message;
      return;
    }
    ROOT = d.root || "";
    SERVING = d.serving || "";
    document.getElementById("rootpath").textContent = ROOT;
    document.getElementById("revealBtn").hidden = false;
    document.getElementById("moveBtn").hidden = false;
    /* **Said, not silent.** `root_gone` is empty unless the reader's chosen maps directory
       is on a disk that is not connected, in which case the path above is a fallback and
       the list below is the fallback's contents. Rule 49 is about substitutions that hide
       the failure; this one is stated in the loudest place on the page. */
    const gone = d.root_gone || "";
    document.getElementById("rootGone").hidden = !gone;
    if (gone) document.getElementById("rootGoneWhy").textContent = gone;
    paintOpen();
    paint(d.programs || []);
  }

  /* The banner, from the field `/api/programs` already carries.
   *
   * **No second endpoint**, on this module's own standing rule: one route lists programs and
   * it is the shell's, and a second answer to *what is here* drifts from the first the day a
   * column is added to either (rule 51). `serving` is `""` from cold and the program's name
   * otherwise, which is the whole of what this needs. */
  function paintOpen() {
    document.getElementById("openNow").hidden = !SERVING;
    if (SERVING) document.getElementById("openName").textContent = SERVING;
  }

  function paint(rows) {
    const lead = document.getElementById("lead");
    const mount = document.getElementById("programs");
    if (!rows.length) {
      lead.textContent = "No map has been made yet.";
      /* Design rule 21, in the largest place it applies. An empty list is not the same
         fact as a list that could not be read, and neither is the same as a directory that
         holds programs this build refuses — so each of the three says its own thing, and
         this one says what to do next rather than leaving the reader to guess. */
      mount.innerHTML = `<p class="start-empty">Nothing has been read into
        <code class="mono">${esc(ROOT)}</code> yet. Choose a directory of source and
        DunneFlow will map what moves through it — where it starts, what it runs, what it
        touches, and why.</p>`;
      return;
    }
    lead.textContent = rows.length === 1
      ? "One program has been mapped. Open it, or read another tree."
      : `${rows.length} programs have been mapped. Open one, or read another tree.`;
    mount.innerHTML = rows.map(row).join("") + unfinishedControl(rows);
  }

  /* **The Setting "Unfinished maps", where the rows it governs are** -- and only when one of
     them is. This page has no Settings pane, and the choice is the machine's rather than a
     program's (`settings.js` says why), so the shell's row and this one read and write the
     same key. Absent when nothing here is unfinished: a control with nothing to govern is
     furniture (design rule 29's other half). */
  function unfinishedControl(rows) {
    if (!rows.some(p => !p.serving && p.openable && !p.finished && !p.analysing)) return "";
    const now = window.DunneFlowSettings.unfinishedChoice();
    return `<div class="start-unfinished">
      <span class="start-unfinishedk">Unfinished maps</span>
      <div class="seg" role="group" aria-label="Unfinished maps">
        ${[["refuse", "Refuse"], ["open", "Open with a warning"]].map(([v, l]) =>
          `<button data-unfinished-set="${v}" aria-pressed="${now === v}">${l}</button>`
        ).join("")}
      </div>
      <span class="hint">A map whose analysis stopped part way holds part of a program.
        Opened, a warning above the view says which step it stopped in.</span>
    </div>`;
  }

  /* A row for every directory the walk found, **including the ones that cannot be opened**.
     Design rule 1, and `/api/programs`' own bargain: a program that refuses and a program
     that does not exist are different facts, and only one of them is worth a sentence. A
     reader who started an analysis that died will come back looking for it. */
  function row(p) {
    const revs = Number(p.revisions) || 0;
    const points = revs > 1 ? `${revs} points in time` : (revs === 1 ? "one point in time" : "");
    /* **The one being read is a link, not a switch.** It used to render as an ordinary
       button, and pressing it posted `/api/program` for the program already open, which
       `_p_program` refuses by name -- correct on the server and a dead end on this page.
       Dimming it and stopping there would be worse: design rule 30's test is *would pressing
       it do something useful*, and this one has somewhere to go. It goes there. */
    if (p.serving) {
      return `<a class="start-prog start-progopen" href="/">
        <span class="start-progname">${esc(p.name)}</span>
        <span class="start-progwhat">being read now — back to it</span>
      </a>`;
    }
    let why = "";
    const run = p.analysing;
    if (run) {
      /* **Unfinished and still being worked on**: the third answer, from the run's own
         sidecar. Without it this row said "never finished — analyse it again" over a run
         two hours into finishing, and the button that sentence points at would have
         started a second analysis into the same directory. */
      const steps = Number(run.steps) || 0;
      why = `being analysed from a terminal — ${run.step || "starting"}${
        run.detail ? " (" + run.detail + ")" : ""}${
        steps ? `, step ${(Number(run.done_steps) || 0) + 1} of ${steps}` : ""}`;
    } else if (!p.openable) {
      why = "no map in it — an analysis was started here and wrote nothing";
    } else if (!p.finished) {
      /* The store's own three states, not two: an analysis that was killed leaves a graph
         that opens perfectly and lies. Named here so the row is not a click into a refusal
         with no warning. */
      why = window.DunneFlowSettings.unfinishedChoice() === "open"
        ? "its analysis never finished — opens with a warning"
        : "its analysis never finished — analyse it again";
    }
    const busy = OPENING === p.name;
    /* Unfinished is openable exactly when the reader's Setting says so; the server is asked
       with the same choice and decides again, so this only spares a click into a refusal. */
    const halted = !p.finished && window.DunneFlowSettings.unfinishedChoice() !== "open";
    return `<button class="start-prog" data-open="${esc(p.name)}"
                    ${(!p.openable || halted || run || busy) ? "disabled" : ""}>
      <span class="start-progname">${esc(p.name)}</span>
      <span class="start-progwhat">${busy ? "opening…" : esc(why || points)}</span>
    </button>`;
  }

  /* -- opening one -------------------------------------------------------- */

  /* The same route the shell's program `<select>` posts to, and the same code on the server:
     `switch_program` builds the new base before it closes anything, so a first open is a
     switch with nothing to close. A second route would be a second copy of the widest blast
     radius in `serve.py` (rule 51). */
  async function open(name) {
    if (OPENING) return;
    OPENING = name;
    load();
    let d;
    try {
      d = await fetch("/api/program?name=" + encodeURIComponent(name) + "&unfinished="
                      + window.DunneFlowSettings.unfinishedChoice(),
                      { method: "POST", headers: { "X-DunneFlow": "1" } }).then(r => r.json());
    } catch (err) {
      OPENING = "";
      say("the server could not be asked: " + err.message);
      return;
    }
    if (!d.started) {
      OPENING = "";
      say(d.reason || "it was refused, with no reason given");
      load();
      return;
    }
    watch(name);
  }

  /* The build reports each step, and this page waits for it rather than reloading blind:
     a reload while the base is half-built serves the start page again, which reads exactly
     like a button that did nothing. */
  async function watch(name) {
    let d;
    try {
      d = await fetch("/api/base").then(r => r.json());
    } catch {
      setTimeout(() => watch(name), 500);
      return;
    }
    if (d.state === "failed") {
      OPENING = "";
      say(d.reason || "it could not be opened");
      load();
      return;
    }
    /* On the fact, never on the state word. `open` is the server saying a base exists,
       which is exactly what decides whether `/` is the shell — so the page reloads on the
       same answer the server would give itself (rule 30: a label is not an identity). */
    if (d.open) {
      /* Reloaded rather than routed: `/` is the shell now, because the server decides which
         page that is from whether it has a base. One decision, on the server, where the
         base is (rule 51). */
      location.reload();
      return;
    }
    const step = d.step ? ` — ${d.step}` : "";
    say(`opening ${name}${step}…`);
    setTimeout(() => watch(name), 350);
  }

  function say(msg) {
    document.getElementById("lead").textContent = msg;
  }

  /* -- where maps are kept -------------------------------------------------
   *
   * The dialog is markup in `start.html` rather than a template in here, unlike the analyse
   * dialog: that one is shared by two pages and has to travel, this one belongs to the page
   * that owns the root readout it sits under. What it borrows is the *styling* — the same
   * `analyze-*` classes — because a second set would be a second answer to what a dialog
   * looks like (rule 71).
   */

  let MOVING = false;      // a move is in flight; the dialog is blocked, not dismissed

  function moveEl(id) { return document.getElementById(id); }

  function openMove() {
    moveEl("moveScrim").hidden = false;
    /* **Nothing pre-filled.** A path is the one thing this page cannot guess, and an
       invented one that looks right is worse than an empty field. */
    moveEl("movePath").value = "";
    moveEl("moveCarry").checked = true;
    verdictMove();
    moveEl("movePath").focus();
  }

  function closeMove() {
    if (MOVING) return;    // a move in flight is not a thing to dismiss
    moveEl("moveScrim").hidden = true;
  }

  /* The live pre-flight, from the same function the POST calls (rule 41): the sentence under
     the field and the refusal at the button cannot disagree, because there is one of them. */
  async function verdictMove() {
    const path = moveEl("movePath").value.trim();
    const carry = moveEl("moveCarry").checked ? "1" : "0";
    moveEl("moveCarryWhat").textContent = carry === "1"
      ? "Move the maps that are here now"
      : "Leave the maps that are here now where they are";
    if (!path) {
      showVerdict({ ok: false, refusal: "", note: "" });
      return;
    }
    let d;
    try {
      d = await fetch(`/api/root?path=${encodeURIComponent(path)}&move=${carry}`)
        .then(r => r.json());
    } catch (err) {
      showVerdict({ ok: false, refusal: "the server could not be asked: " + err.message });
      return;
    }
    /* The field may have moved on while that was in flight. Answering about a path the
       reader has stopped typing is a claim about a state the page is not in. */
    if (moveEl("movePath").value.trim() !== path) return;
    showVerdict(d);
  }

  function showVerdict(d) {
    const refusal = moveEl("moveRefusal");
    const note = moveEl("moveNote");
    refusal.textContent = d.refusal || "";
    refusal.hidden = !d.refusal;
    note.textContent = d.note || "";
    note.hidden = !d.note;
    moveEl("moveGo").disabled = !d.ok || MOVING;
  }

  async function doMove() {
    const path = moveEl("movePath").value.trim();
    const carry = moveEl("moveCarry").checked ? "1" : "0";
    MOVING = true;
    moveEl("moveGo").disabled = true;
    moveEl("moveGo").textContent = carry === "1" ? "Moving…" : "Setting…";
    let d;
    try {
      d = await fetch(`/api/root?path=${encodeURIComponent(path)}&move=${carry}`,
                      { method: "POST", headers: { "X-DunneFlow": "1" } }).then(r => r.json());
    } catch (err) {
      MOVING = false;
      moveEl("moveGo").textContent = "Use it";
      showVerdict({ ok: false, refusal: "the server could not be asked: " + err.message });
      return;
    }
    MOVING = false;
    moveEl("moveGo").textContent = "Use it";
    if (!d.started) {
      /* A refusal leaves everything exactly as it was — the maps and the recorded location
         both — so the dialog stays open with the reason in it and the reader can try
         another directory without starting over. */
      showVerdict({ ok: false, refusal: d.reason || "it was refused, with no reason given" });
      return;
    }
    closeMove();
    load();
  }

  /* -- the two gestures that reach outside the browser --------------------- */

  document.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.closest) return;

    const choice = t.closest("[data-unfinished-set]");
    if (choice) {
      window.DunneFlowSettings.setUnfinishedChoice(choice.dataset.unfinishedSet);
      load();
      return;
    }
    const opener = t.closest("[data-open]");
    if (opener && !opener.disabled) { open(opener.getAttribute("data-open")); return; }

    if (t.closest("[data-startanalyze]")) {
      /* Nothing pre-filled. A path is the one thing this page cannot guess, and an invented
         one that looks right is worse than an empty field (rule 60's neighbourhood). */
      Analyze.open();
      return;
    }

    /* Close the map. **`load()` afterwards, never `location.reload()`** -- `/start` is
       unconditional, so this page is already the right page for both states and re-fetching
       the list is the whole of the update: the banner hides, and the row that said *being
       read now* becomes an ordinary one. That property is why `/start` is its own address
       rather than a flag on `/`. */
    if (t.closest("[data-closemap]")) {
      const note = document.getElementById("closeNote");
      note.textContent = "closing…";
      let d;
      try {
        d = await fetch("/api/close", { method: "POST", headers: { "X-DunneFlow": "1" } }).then(r => r.json());
      } catch (err) {
        note.textContent = err.message;
        return;
      }
      /* A 409 arrives here as a failed parse or a `started: false`, and both mean the same
         thing on this page: somebody else closed it first. That is not an error to report,
         it is the state the reader asked for -- so the list is reloaded and it simply
         becomes true. A refusal that *is* worth saying is a switch still running. */
      if (d && d.started === false && d.reason) note.textContent = d.reason;
      else note.textContent = "";
      load();
      return;
    }

    if (t.closest("[data-movemaps]")) { openMove(); return; }
    if (t.closest("[data-movecancel]")) { closeMove(); return; }
    if (t.closest("[data-movego]")) { doMove(); return; }
    /* Reconnecting the disk is a restart of the server, because the root is the server's
       state and is read once at boot. A reload is the closest this page can offer, and it
       is honest: if the disk came back, the reader gets a working list; if it did not, they
       get the same banner. */
    if (t.closest("[data-tryagain]")) { location.reload(); return; }

    /* The folder picker, from the route the analyse dialog already uses. Nothing about it
       is analysis-specific: it asks the operating system for a directory and hands back an
       absolute path, which is exactly what this field wants (rule 51 — one picker). */
    if (t.closest("[data-movepick]")) {
      /* **It says while it is opening**, for `analyze.js`' reason and in its words: the
         dialog belongs to a helper process, the first of those on a machine pays to load the
         toolkit it draws with, and for all of that time an untouched button is
         indistinguishable from one wired to nothing (design rule 16). Restored in a
         `finally`, so a throw cannot leave the page saying "Opening..." for ever. */
      const btn = t.closest("[data-movepick]");
      const was = btn.innerHTML;
      btn.innerHTML = "Opening&hellip;";
      btn.disabled = true;
      let d;
      try {
        d = await fetch("/api/pickdir", { method: "POST", headers: { "X-DunneFlow": "1" } }).then(r => r.json());
      } catch (err) {
        showVerdict({ ok: false, refusal: err.message });
        return;
      } finally {
        btn.innerHTML = was;
        btn.disabled = false;
      }
      /* Cancelling is the ordinary way out of a dialog and is not a failure — `_p_pickdir`
         tells the two apart by AppleScript's own words and sends an empty reason for one. */
      if (d.picked) {
        document.getElementById("movePath").value = d.picked;
        verdictMove();
      } else if (d.reason) {
        showVerdict({ ok: false, refusal: d.reason });
      }
      return;
    }

    if (t.closest("[data-reveal]")) {
      const note = document.getElementById("revealNote");
      note.textContent = "";
      let d;
      try {
        d = await fetch("/api/reveal?path=" + encodeURIComponent(ROOT),
                        { method: "POST", headers: { "X-DunneFlow": "1" } }).then(r => r.json());
      } catch (err) {
        note.textContent = err.message;
        return;
      }
      /* A refusal is said out loud. A button that reports nothing and does nothing is
         indistinguishable from one that worked (design rule 16). */
      if (!d.revealed) note.textContent = d.reason || "it could not be shown";
    }
  });

  /* The pre-flight, as the reader types and as they change their mind about carrying the
     maps across — the second matters because ticking the box is what brings the free-space
     question into scope, and a verdict that ignored it would be answering the wrong one. */
  document.addEventListener("input", (ev) => {
    if (ev.target && ev.target.id === "movePath") verdictMove();
  });
  document.addEventListener("change", (ev) => {
    if (ev.target && ev.target.id === "moveCarry") verdictMove();
  });
  /* Escape closes it, like the analyse dialog — but never out from under a move in flight. */
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !document.getElementById("moveScrim").hidden) closeMove();
  });

  load();
  /* A run outlives the page that started it, and on this page that is the ordinary case:
     an analysis takes ninety seconds and a reader may well reload. The server is the truth
     about what is running, not anything the browser remembered. */
  Analyze.resume();
})();
