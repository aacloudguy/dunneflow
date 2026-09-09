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
  let OPENING = "";        // the program being opened, so the list can say which

  /* This page has no scrim, no usage counter and nothing else to repaint, and every one of
     those is a real answer rather than a gap. `changed` reloads the list because the only
     thing that changes here is which programs exist. */
  Analyze.wire({
    used: () => {},
    changed: () => { load(); },
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
    document.getElementById("rootpath").textContent = ROOT;
    document.getElementById("revealBtn").hidden = false;
    paint(d.programs || []);
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
    mount.innerHTML = rows.map(row).join("");
  }

  /* A row for every directory the walk found, **including the ones that cannot be opened**.
     Design rule 1, and `/api/programs`' own bargain: a program that refuses and a program
     that does not exist are different facts, and only one of them is worth a sentence. A
     reader who started an analysis that died will come back looking for it. */
  function row(p) {
    const revs = Number(p.revisions) || 0;
    const points = revs > 1 ? `${revs} points in time` : (revs === 1 ? "one point in time" : "");
    let why = "";
    if (!p.openable) {
      why = "no map in it — an analysis was started here and wrote nothing";
    } else if (!p.finished) {
      /* The store's own three states, not two: an analysis that was killed leaves a graph
         that opens perfectly and lies. Named here so the row is not a click into a refusal
         with no warning. */
      why = "its analysis never finished — analyse it again";
    }
    const busy = OPENING === p.name;
    return `<button class="start-prog" data-open="${esc(p.name)}"
                    ${(!p.openable || !p.finished || busy) ? "disabled" : ""}>
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
      d = await fetch("/api/program?name=" + encodeURIComponent(name),
                      { method: "POST" }).then(r => r.json());
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

  /* -- the two gestures that reach outside the browser --------------------- */

  document.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.closest) return;

    const opener = t.closest("[data-open]");
    if (opener && !opener.disabled) { open(opener.getAttribute("data-open")); return; }

    if (t.closest("[data-startanalyze]")) {
      /* Nothing pre-filled. A path is the one thing this page cannot guess, and an invented
         one that looks right is worse than an empty field (rule 60's neighbourhood). */
      Analyze.open();
      return;
    }

    if (t.closest("[data-reveal]")) {
      const note = document.getElementById("revealNote");
      note.textContent = "";
      let d;
      try {
        d = await fetch("/api/reveal?path=" + encodeURIComponent(ROOT),
                        { method: "POST" }).then(r => r.json());
      } catch (err) {
        note.textContent = err.message;
        return;
      }
      /* A refusal is said out loud. A button that reports nothing and does nothing is
         indistinguishable from one that worked (design rule 16). */
      if (!d.revealed) note.textContent = d.reason || "it could not be shown";
    }
  });

  load();
  /* A run outlives the page that started it, and on this page that is the ordinary case:
     an analysis takes ninety seconds and a reader may well reload. The server is the truth
     about what is running, not anything the browser remembered. */
  Analyze.resume();
})();
