/* ══ prose.js — a document's text, turned into a page ═══════════════════════════════
 *
 * The renderer for Document mode's **lane 1**: the 2,064 documents the analysed program
 * carries, which until now were mined for 29,980 headings and 230 definitions and readable
 * nowhere in the tool. Lane 2 — the map's own eight documents — is tables and needs none of
 * this.
 *
 * **The line CLAUDE.md draws, and it is drawn here as well as there.** The rule is that
 * `extractors/docs/` is scanned by hand, *no markdown library*. That rule is about **facts**:
 * the extractor's output is a contract, it is hashed into the cache key by
 * `doc_extraction_inputs()`, and it must never depend on a third party's reading of a
 * document. A **renderer** produces pixels, sits in no cache key, and no fact depends on it.
 * Nothing under `extractors/` may import `markdown-it`, and a test asserts it.
 *
 * **Its own file, and the boundary is the one `graph.js` keeps.** This turns text into
 * markup and knows nothing about this page: which document is open, what a link should do
 * when it is clicked, what exists in the corpus. What it has to say leaves as **data
 * attributes** — `data-line` on every block, `data-doclink` on a link into the corpus,
 * `data-docanchor` on a link within the document — and the shell routes them. A renderer
 * that called `openDoc()` would be a second place that decides what a click means.
 *
 * ── what the corpus actually contains, because the handling was chosen from it ──
 *
 * Measured over Mensores' 2,019 Markdown documents:
 *
 *   3,516 https links · 6 http · 666 relative · 16 anchors · 6 other schemes
 *   (`graph:`, `xs:`, `node:` — prose that happens to look like a link)
 *   5 images, all relative
 *
 * So: **external links stay links** and open in a new tab, because 3,522 of them is the
 * documentation doing its job and a reader clicking one is their own act. **Relative links
 * are routed, not followed** — 666 of them, and an `<a href="./rel.md">` in this page
 * navigates the *dashboard* away, which is the open item chunk 1 recorded. **Anchors are
 * routed** to a heading in the same document. Anything else renders as **text**: a `graph:`
 * href is not a link anybody can follow, and drawing it as one is design rule 16's dead
 * control.
 *
 * **And images are never loaded.** That is the one that matters. `![](https://tracker/x.png)`
 * fires a request the moment it is rendered, with no click and no consent, out of a tool
 * whose whole posture is deterministic and local (design rule 14: egress is scoped, never a
 * switch). Five images in this corpus and all of them relative — but the rule is about what a
 * document *can* contain, not what this one does. Each renders as a placeholder naming its
 * source, so the reader knows something was there.
 */

const Prose = (function () {
  "use strict";

  /* The configured instance, and the in-flight load so two callers cannot fetch it twice.
   * Lazily and once, copying `graphviz()`: 125 KB, and most sessions never open a document,
   * so paying for it at boot would slow the screen everyone sees for the one many never do. */
  let md = null;
  let loading = null;

  function load() {
    if (md) return Promise.resolve(md);
    if (loading) return loading;
    loading = (async () => {
      await new Promise((ok, no) => {
        const el = document.createElement("script");
        el.src = "/vendor/markdown-it.min.js";
        el.onload = ok;
        el.onerror = () => no(new Error("the document renderer could not be loaded"));
        document.head.appendChild(el);
      });
      if (!window.markdownit) throw new Error("the renderer loaded but exported nothing");
      md = window.markdownit({
        /* **The whole XSS answer, and it is one word.** A document containing a `<script>`
           renders as text rather than becoming an element. These are files off the reader's
           own disk, but "the input is trusted" is the assumption every such hole was dug
           under, and a documentation corpus is exactly where a copied-in snippet lives. */
        html: false,
        /* Bare URLs in prose stay prose. Turning text into links is the renderer deciding
           something the author did not write, and in a corpus of plans and research notes a
           great deal of text looks like a URL without being one. */
        linkify: false,
        typographer: false,
      });
      return md;
    })();
    return loading;
  }

  function ready() { return md !== null; }

  const AMP = /[&<>"']/g;
  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  function esc(s) { return String(s == null ? "" : s).replace(AMP, c => ESCAPES[c]); }

  /* A heading's id, so a `#anchor` in the same document has something to reach.
   *
   * GitHub's shape, because that is what the authors of these documents were writing
   * against: lowercased, punctuation dropped, spaces to hyphens. Collisions are numbered
   * rather than allowed — two headings sharing an id means one of them is unreachable, and
   * which one would depend on document order (rule 30). */
  function slug(text, seen) {
    const base = String(text || "")
      .toLowerCase().trim()
      .replace(/[^\w\- ]+/g, "")
      .replace(/\s+/g, "-") || "section";
    const n = (seen[base] = (seen[base] || 0) + 1);
    return n === 1 ? base : `${base}-${n}`;
  }

  /* Where a relative href points, as a corpus path.
   *
   * Resolved against the **directory of the document doing the linking**, because that is
   * what a relative link means, and returned as a plain corpus path so the caller can look
   * it up in the document list it already holds. A target that climbs out of the tree is
   * returned as it resolves — `.groma/PROJECT.md` really does link to
   * `../../Society-Specs/01-naming-standards.md`, which is outside the corpus, and saying so
   * is the caller's job. Guessing that it must have meant something inside would be worse
   * than useless.
   *
   * The query and the fragment are dropped: `docs.db` is keyed on paths and neither is part
   * of one. A fragment on a cross-document link would want the target's heading, which is a
   * second question and is not asked here. */
  function resolvePath(href, from) {
    const clean = String(href).split("#")[0].split("?")[0];
    if (!clean) return "";
    const base = String(from || "").split("/").slice(0, -1);
    const out = clean.startsWith("/") ? [] : base.slice();
    for (const part of clean.replace(/^\//, "").split("/")) {
      if (part === "" || part === ".") continue;
      if (part === "..") { out.pop(); continue; }
      out.push(part);
    }
    return out.join("/");
  }

  /* What kind of link this is, which is the whole of the routing decision.
   *
   * From the href alone, and deliberately not from whether the target exists: this module
   * does not hold the document list and should not learn to. A `data-doclink` that resolves
   * to nothing is a real answer the caller states (design rule 1); a renderer that silently
   * downgraded it to text would have decided the same thing with no way to say so. */
  const EXTERNAL = /^(https?|mailto):/i;
  function linkKind(href) {
    const h = String(href || "");
    if (!h) return "none";
    if (h.startsWith("#")) return "anchor";
    if (EXTERNAL.test(h)) return "external";
    /* `//host/path` is protocol-relative — an *external* address wearing a relative
       spelling, and treating it as a corpus path would resolve it to `host/path` and look
       like a document. */
    if (h.startsWith("//")) return "external";
    if (/^[a-zA-Z][a-zA-Z0-9+.\-]*:/.test(h)) return "other";
    return "relative";
  }

  /* YAML frontmatter, blanked rather than removed — and the difference is the whole point.
   *
   * markdown-it knows nothing about frontmatter, so a document opening `---\nkind:
   * reference\ntitle: Glossary\n---` parses as a **setext heading**: the metadata becomes an
   * `<h2>` with an id of `kind-referencetitle-glossary`, at the top of the page, before the
   * document's own title. **989 of Mensores' 2,019 Markdown documents** begin with a
   * frontmatter block, so this is half the corpus opening with its own machine-readable
   * header rendered as prose.
   *
   * **Blanked, never deleted**, because `data-line` is the reason this library is here. Cut
   * the lines out and every `token.map` below shifts up by the number removed — so every
   * stamped line is wrong by a constant, every heading in the side nav scrolls to the wrong
   * block, and a glossary citation opens a document *near* the line it was read from. That
   * failure is invisible: the page renders perfectly and every number on it is off by four.
   * Replacing the lines with empty ones costs nothing and cannot get the arithmetic wrong,
   * because there is no arithmetic.
   *
   * Only a **closed** block at the very top counts. A document that opens with a horizontal
   * rule and never closes one is not carrying frontmatter, and 30 of this corpus' 989 are
   * cases the extractor could not parse as YAML — those are still not prose, and are still
   * not a heading. The raw text is returned so the caller can show it as what it is. */
  const FENCE = /^(-{3}|\.{3})\s*$/;
  function splitFrontmatter(text) {
    const lines = String(text).split("\n");
    if (!lines.length || lines[0].trim() !== "---") return { body: text, front: "" };
    for (let i = 1; i < lines.length; i++) {
      if (!FENCE.test(lines[i].trim())) continue;
      const front = lines.slice(1, i).join("\n");
      const blanked = lines.slice();
      for (let j = 0; j <= i; j++) blanked[j] = "";
      return { body: blanked.join("\n"), front };
    }
    return { body: text, front: "" };          // opened and never closed: not frontmatter
  }

  /* Author comments, lifted out before the parser sees them — and **counted, never
   * dropped**.
   *
   * `html: false` does not hide an HTML comment; it un-hides one. With raw HTML refused
   * markdown-it disables the html_block rule entirely, so `<!-- Plan 14-01 seeds this
   * template -->` is not an `html_block` token at all — it is an ordinary **paragraph** of
   * text, escaped and drawn as body prose. Verified rather than assumed: parsing a document
   * with three HTML constructs in it yields `html_block: 0`. So there is nothing to catch at
   * the token level, and this has to happen to the text.
   *
   * **7,317 comments across 505 of Mensores' 2,019 documents** — a quarter of the corpus
   * showing editorial notes nobody wrote for the reader.
   *
   * Replaced by **exactly as many newlines as they contained**, which is the frontmatter
   * rule and is here for the frontmatter reason: `data-line` is what a citation and a
   * heading nav open against, and shortening the text by four lines would put every block
   * below four lines out — a page that renders perfectly with every number on it wrong.
   *
   * Returned with their line numbers rather than binned, because a silent filter is what
   * design rule 1 exists to prevent, and in a corpus of templates and plans the comments are
   * occasionally the most useful thing in the file. */
  const COMMENT = /<!--[\s\S]*?-->/g;
  function stripComments(text) {
    const found = [];
    let at = 0, line = 1, out = "";
    for (const m of String(text).matchAll(COMMENT)) {
      const before = text.slice(at, m.index);
      out += before;
      line += (before.match(/\n/g) || []).length;
      found.push({ line, text: m[0] });
      /* The newlines, and only the newlines. Everything else on those lines is the comment
         and is not prose. */
      out += (m[0].match(/\n/g) || []).join("");
      line += (m[0].match(/\n/g) || []).length;
      at = m.index + m[0].length;
    }
    out += text.slice(at);
    return { body: found.length ? out : text, comments: found };
  }

  /* ── the render ───────────────────────────────────────────────────────────────────── */

  /* `md.parse()` to tokens and then the renderer, never `md.render()`.
   *
   * The line map is the whole reason this library is here: every block token carries
   * `map: [startLine, endLine]`, which is what lets a glossary citation open a document at
   * the line it was read from and what a heading nav scrolls to (design rule 13). `render()`
   * throws the tokens away before anything can be stamped onto them.
   *
   * `from` is the path of the document being rendered, used only to resolve relative links.
   */
  function render(text, fmt, from) {
    /* Plain text, and the 45 `.txt` documents in this corpus are the ordinary case rather
       than a fallback. `.rst` and `.adoc` land here too: `DOC_SUFFIXES` admits them, this
       corpus has **zero** of either, and rendering them as text is the honest treatment
       until a corpus needs otherwise. The caller is told which happened and says so — a
       document silently degraded is design rule 1's defect. */
    if (fmt !== "MARKDOWN") {
      return { as: "text", fmt: fmt || "TEXT", front: "",
               html: `<pre class="doctext" data-line="1">${esc(text)}</pre>`,
               links: { anchor: 0, relative: 0, external: 0, other: 0 }, images: 0,
               comments: [] };
    }
    if (!md) throw new Error("Prose.render before Prose.load");

    const split = splitFrontmatter(String(text == null ? "" : text));
    const stripped = stripComments(split.body);
    const tokens = md.parse(stripped.body, {});
    const seen = Object.create(null);
    const links = { anchor: 0, relative: 0, external: 0, other: 0 };
    let images = 0;
    /* A stack, because a link's `link_close` has to know what its `link_open` decided —
       markdown-it emits them as separate flat tokens, and a link containing emphasis has
       other tokens between the two. */
    const closers = [];

    for (const t of tokens) {
      /* **`data-line` on every block that has one**, which is the property chunk 5 opens
         against. `nesting` of 1 is an opening tag and 0 is self-contained (a fence, an
         html_block, a horizontal rule); a closing tag carries no map and needs none. */
      if (t.map && t.nesting >= 0 && t.type !== "inline") {
        t.attrSet("data-line", String(t.map[0] + 1));
        /* **And where the block ends**, because most of the lines anybody wants to open at
         * are not the first line of anything. A heading's recorded line is a block's start
         * and matches exactly; a *definition's* is somewhere in the middle of a paragraph,
         * and that is what chunk 5's citations open against. With only the start stamped,
         * the nearest-at-or-after fallback lands the reader on the block **after** the one
         * their line is in — plausible, adjacent, and wrong.
         *
         * `map[1]` is exclusive, so the inclusive last line is `map[1]` in 1-based terms. */
        t.attrSet("data-line-end", String(t.map[1]));
      }
      if (t.type === "heading_open") {
        /* The id is minted from the *next* token's content, which is the inline run this
           heading opens. Written here rather than in a second pass because the pass would
           have to find the pairing again, and two places that decide which text a heading
           has is how the nav and the anchors come to disagree (rule 51). */
        const i = tokens.indexOf(t);
        const inline = tokens[i + 1];
        t.attrSet("id", slug(inline && inline.content, seen));
      }
      if (t.type !== "inline" || !t.children) continue;

      for (const c of t.children) {
        if (c.type === "image") {
          images++;
          /* Never loaded. See the note at the top of this file: rendering an `<img>` fires
             a request with no click, and this tool does not do that. The token is turned
             into a self-contained span so the alt text and the source both survive — a
             reader can see what was meant to be there and where it came from. */
          const src = c.attrGet("src") || "";
          const alt = (c.content || "").trim();
          c.type = "html_inline";
          c.tag = "";
          c.children = null;
          c.content =
            `<span class="docimg" title="Images are never fetched: this page loads nothing`
            + ` from outside your machine."><span class="docimg-alt">${esc(alt || "image")}`
            + `</span><code class="docimg-src">${esc(src)}</code></span>`;
          continue;
        }
        if (c.type === "link_open") {
          const href = c.attrGet("href") || "";
          const kind = linkKind(href);
          links[kind === "none" ? "other" : kind]++;
          if (kind === "external") {
            /* A real link, and the only kind that stays one. `noopener` because a new tab
               given `window.opener` can navigate the tab it came from, and `noreferrer`
               because which local document a reader is looking at is not a third party's
               business. */
            c.attrSet("target", "_blank");
            c.attrSet("rel", "noreferrer noopener");
            c.attrJoin("class", "docext");
            closers.push("a");
            continue;
          }
          if (kind === "anchor" || kind === "relative") {
            /* **The href is removed, and that is the fix rather than a precaution.** Left
               on, `<a href="./rel.md">` navigates the *dashboard* away — off the page, out
               of the session, losing the selection and the trail. Chunk 1 recorded this as
               the open item and this is it. What is left is a focusable element carrying
               where it wanted to go; the shell decides what that means. */
            c.attrs = null;
            c.attrSet("class", kind === "anchor" ? "docanchor" : "doclink");
            c.attrSet("tabindex", "0");
            c.attrSet("role", "link");
            if (kind === "anchor") {
              c.attrSet("data-docanchor", href.slice(1));
            } else {
              c.attrSet("data-doclink", resolvePath(href, from));
              c.attrSet("data-dochref", href);
            }
            closers.push("a");
            continue;
          }
          /* `graph:`, `xs:`, `node:` and whatever else prose throws up — 6 in this corpus.
             Not a link anybody can follow, so it is not drawn as one. The text stays; only
             the anchor goes. */
          c.type = "text";
          c.content = "";
          c.tag = "";
          c.attrs = null;
          closers.push("");
        } else if (c.type === "link_close") {
          const opened = closers.pop();
          if (opened !== "a") { c.type = "text"; c.content = ""; c.tag = ""; }
        }
      }
    }

    return { as: "markdown", fmt: "MARKDOWN", front: split.front,
             html: md.renderer.render(tokens, md.options, {}), links, images,
             comments: stripped.comments };
  }

  return { load, ready, render, resolvePath, linkKind, slug, splitFrontmatter,
           stripComments };
})();

if (typeof window !== "undefined") window.Prose = Prose;
