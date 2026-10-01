"""The document renderer: `prose.js`, and the line it is allowed to stand on.

Document mode's lane 1 turns 2,019 Markdown documents into pages. It is the only place in
DunneFlow that uses a third-party parser, and the whole of its legitimacy is a distinction
that has to be enforced rather than merely stated:

  **`extractors/docs/` is scanned by hand — no markdown library.** That rule is about
  *facts*. The extractor's output is a contract, it is hashed into the cache key by
  `doc_extraction_inputs()`, and it must never depend on a third party's reading of a
  document. A **renderer** produces pixels, sits in no cache key, and no fact depends on it.

`VERSIONS.json` has claimed *"a test asserts it"* since the library was vendored, and until
this file there was no such test — which is rule 43's shape exactly: a claim about a guard
is not a guard, and `shorten()`'s docstring promised a `selfCheck` for a session without one.

The rest is what the renderer must not do: load a library at boot for a mode most sessions
never open, render raw HTML, follow a relative link out of the dashboard, or fetch an image.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "dunneflow"
STATIC = SRC / "web" / "static"
VENDOR = SRC / "web" / "vendor"


def _read(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _strip(js: str) -> str:
    """JavaScript with its comments blanked, **block comments included**.

    `test_web_controls` blanks comment *lines* only, and says why: a general stripper has to
    track template literals, and the first attempt there ate their bodies. That is the right
    call for a 14,000-line shell — and it is not enough here.

    This file's comments are long block comments whose continuation lines are plain indented
    prose, so a line-based strip leaves them standing. It cost a survived mutation
    immediately: dropping `noreferrer` from the code passed a guard checking for
    `"noreferrer"`, because the paragraph *explaining why `noreferrer` is there* was still
    in the text being searched. That is the exact defect `_code()`'s own docstring records,
    reproduced in a new file.

    So this tracks `/* … */` across lines, which is exact for `prose.js` because it contains
    no `/*` inside any string or template literal — asserted below, so the day one arrives
    this stripper fails by name rather than eating code.
    """
    out, in_block = [], False
    for line in js.split("\n"):
        st = line.lstrip()
        if in_block:
            out.append("")
            if "*/" in line:
                in_block = False
            continue
        if st.startswith("//"):
            out.append("")
            continue
        if st.startswith("/*"):
            out.append("")
            in_block = "*/" not in line
            continue
        out.append(line)
    return "\n".join(out)


def test_the_stripper_this_file_depends_on_is_exact() -> None:
    """Rule 43: a check that cries wolf has already failed, and so has one that cannot see.

    `_strip` blanks `/* … */` across lines, which is exact only while no string or template
    literal in `prose.js` contains the opening of a block comment. If one ever does, this
    fails here rather than silently blanking live code and passing every guard below it.
    """
    src = _read("prose.js")
    stripped = _strip(src)
    assert len(stripped.split("\n")) == len(src.split("\n")), (
        "the stripper changed the line count, so it is not blanking in place"
    )
    # The literals in this file, with their comment markers, must survive.
    for kept in ("html: false", "linkify: false", 'el.src = "/vendor/markdown-it.min.js"'):
        assert kept in stripped, f"the stripper ate live code: {kept!r} is gone"
    # And the prose must not.
    assert "the whole XSS answer" not in stripped, "a block comment survived the strip"
    assert "because which local document a reader" not in stripped, (
        "a block comment's continuation line survived — the defect this stripper exists for"
    )


# ─────────────────────────────────── the line, enforced ─────────────────────────────── #

def test_nothing_under_extractors_imports_the_renderer() -> None:
    """The claim `VERSIONS.json` makes, made true.

    The extractor's output is hashed into the cache key. A third party's reading of a
    document reaching it would put every fact in `docs.db` — 29,980 headings, 235
    definitions — behind a library version, and a bump would silently change what the tool
    says a program's documentation *contains*. The renderer changes what a page looks like
    and nothing else.
    """
    # The library's own names and the path it is vendored at. **Not the word "Prose"** —
    # the first draft of this guard checked for it and fired on
    # `extractors/docs/markdown.py`'s docstring, *"Prose definition shapes"*. A check that
    # cries wolf has already failed (rule 43), and it would have failed silently: the way
    # that gets fixed is by loosening the guard.
    names = ("markdown-it", "markdownit", "markdown_it", "prose.js", "web/vendor")
    offenders = []
    for py in (SRC / "extractors").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for n in names:
            if n in text:
                offenders.append(f"{py.relative_to(SRC)} mentions {n}")
    assert not offenders, (
        "the renderer has reached the extractor: " + "; ".join(offenders) + ". Its output "
        "is a contract hashed into the cache key and must not depend on a third party's "
        "reading of a document"
    )
    # And it has to be able to see one, or it is a guard over an empty set.
    assert list((SRC / "extractors").rglob("*.py")), "no extractor files found; guard is blind"


def test_the_vendored_library_is_recorded_with_its_reason() -> None:
    """A library in the tree with no version, licence or reason is what that file prevents."""
    rec = json.loads((VENDOR / "VERSIONS.json").read_text(encoding="utf-8"))
    assert rec.get("markdown-it"), "the renderer's library has no recorded version"
    assert re.fullmatch(r"\d+\.\d+\.\d+", rec["markdown-it"]), (
        f"the version is not an exact one: {rec['markdown-it']!r}"
    )
    assert rec.get("licenses", {}).get("markdown-it") == "MIT"
    why = rec.get("why-markdown-it", "")
    # The two properties it was chosen for, and neither is "it parses markdown".
    assert "map" in why and "html:false" in why.replace(" ", ""), (
        "the record does not say what this library was chosen for — the line map, which is "
        "what lets a citation open at its line, and `html:false`"
    )
    assert rec.get("why-a-renderer-may-be-vendored-when-the-extractor-may-not"), (
        "the record does not state the extractor/renderer line, so the next reader will "
        "correctly call this library a violation"
    )
    assert (VENDOR / "markdown-it.min.js").exists(), "the library is recorded and absent"


# ─────────────────────────────────── how it is loaded ───────────────────────────────── #

def test_the_library_is_loaded_lazily_and_once() -> None:
    """125 KB for a mode most sessions never open, and two callers must not fetch it twice.

    The same bargain `graphviz()` strikes over 822 KB of wasm. The in-flight promise is the
    half that is easy to leave out and impossible to see: without it, opening a document
    while one is already loading fetches the library again and builds a second instance.
    """
    js = _strip(_read("prose.js"))
    assert "let loading = null" in js, "there is no in-flight promise, so two calls both fetch"
    load = js.split("function load()", 1)[1].split("\n  }", 1)[0]
    assert "if (md) return" in load, "the library is re-created on every call"
    assert "if (loading) return loading" in load, (
        "a second call while the first is in flight starts its own fetch"
    )
    assert 'el.src = "/vendor/markdown-it.min.js"' in load, "it is not the vendored copy"
    assert "onerror" in load, (
        "a failed load resolves to nothing and the pane blames the document"
    )


def test_the_renderer_refuses_raw_html_and_bare_urls() -> None:
    """`html: false` is the whole XSS answer, and it is one word to lose.

    These are files off the reader's own disk, but *the input is trusted* is the assumption
    every such hole was dug under — and a documentation corpus is exactly where a copied-in
    snippet lives. `linkify: false` is a different question: turning text into links is the
    renderer deciding something the author did not write, and in 2,019 plans and research
    notes a great deal of text looks like a URL without being one.
    """
    js = _strip(_read("prose.js"))
    assert "html: false" in js, (
        "the renderer builds elements out of raw HTML found in a document"
    )
    assert "linkify: false" in js, "bare text is turned into links the author did not write"
    assert "html: true" not in js


def test_it_renders_through_tokens_so_every_block_carries_its_line() -> None:
    """The line map is the whole reason this library is here.

    `md.render()` throws the tokens away before anything can be stamped on them. Without
    `data-line` a glossary citation cannot open a document at the line it was read from
    (design rule 13) and a heading nav has nothing to scroll to.
    """
    js = _strip(_read("prose.js"))
    assert "md.parse(" in js, "the renderer does not go through tokens"
    assert "md.render(" not in js.replace("md.renderer.render(", ""), (
        "`md.render()` is used somewhere, which discards the token maps"
    )
    assert "md.renderer.render(tokens" in js, "the stamped tokens are not what is rendered"
    assert 't.attrSet("data-line"' in js, "no block carries the line it came from"
    # A closing tag has no map and wants none; an `inline` token's map covers its whole
    # paragraph and would put a second, wrong, line on the text inside it.
    guard = js.split('t.attrSet("data-line"', 1)[0].rsplit("if (", 1)[1]
    assert "t.map" in guard and "nesting >= 0" in guard and '!== "inline"' in guard, (
        "the stamp is not restricted to opening block tokens that have a map"
    )


# ───────────────────────────── what a link is allowed to do ─────────────────────────── #

def test_a_relative_link_cannot_navigate_the_dashboard() -> None:
    """Chunk 1's open item, and it is the reason this half of chunk 3 exists.

    `<a href="./rel.md">` in this page navigates the **dashboard** away — off the page, out
    of the session, losing the selection and the trail. 666 of them in Mensores' corpus.
    Removing the `href` is the fix rather than a precaution: an element with one is a link
    the browser will follow whatever else is bound to it.
    """
    js = _strip(_read("prose.js"))
    body = js.split('if (kind === "anchor" || kind === "relative")', 1)[1].split("continue;", 1)[0]
    assert "c.attrs = null" in body, (
        "the href survives, so clicking a relative link leaves the dashboard"
    )
    assert "data-doclink" in body and "data-docanchor" in body, (
        "a routed link carries nowhere to go, so it is a control wired to nothing"
    )
    assert 'c.attrSet("tabindex", "0")' in body and 'c.attrSet("role", "link")' in body, (
        "dropping the href also drops keyboard reach; the element must say what it is"
    )


def test_an_external_link_opens_away_from_this_page_and_leaks_nothing() -> None:
    """3,522 of them, and they stay links — the documentation doing its job.

    `noopener` because a new tab handed `window.opener` can navigate the tab it came from,
    and `noreferrer` because which local document a reader has open is not a third party's
    business.
    """
    js = _strip(_read("prose.js"))
    body = js.split('if (kind === "external")', 1)[1].split("continue;", 1)[0]
    assert 'c.attrSet("target", "_blank")' in body, (
        "an external link replaces the dashboard rather than opening beside it"
    )
    # The **attribute**, not the words. Checking for `"noreferrer"` anywhere in the block
    # passed with the code changed, because the paragraph explaining why it is there was
    # still in the text being searched.
    assert 'c.attrSet("rel", "noreferrer noopener")' in body, (
        "the rel is not both: `noopener` alone still sends the referrer, and `noreferrer` "
        "alone leaves the new tab able to navigate the one it came from"
    )


def test_a_scheme_nobody_can_follow_is_not_drawn_as_a_link() -> None:
    """`graph:`, `xs:`, `node:` — six in this corpus, all of them prose that looks like a link.

    Drawn as links they are design rule 16's dead control: they render, they invite a click,
    and nothing can happen. The text stays; only the anchor goes.
    """
    js = _strip(_read("prose.js"))
    kind = js.split("function linkKind(", 1)[1].split("\n  }", 1)[0]
    assert '"other"' in kind, "an unknown scheme is not told apart from a corpus path"
    assert 'h.startsWith("//")' in kind, (
        "a protocol-relative `//host/path` is treated as a corpus path, so an external "
        "address resolves to something that looks like a document"
    )


def test_an_image_is_never_fetched() -> None:
    """The one that is egress rather than navigation.

    `![](https://tracker/x.png)` fires a request the moment it is rendered — no click, no
    consent — out of a tool whose whole posture is deterministic and local (design rule 14:
    egress is scoped, never a switch). Five images in this corpus and all of them relative,
    but the rule is about what a document *can* contain.
    """
    js = _strip(_read("prose.js"))
    body = js.split('if (c.type === "image")', 1)[1].split("continue;", 1)[0]
    assert 'c.type = "html_inline"' in body, "the image token still renders as an element"
    assert "docimg" in body, "nothing is drawn in its place, so the reader sees a gap"
    assert "attrGet(\"src\")" in body, (
        "the placeholder does not name the source, so the reader cannot tell what was there"
    )
    assert "<img" not in js, "an `<img>` is emitted somewhere in this renderer"


# ─────────────────────────────── the paths and the slugs ────────────────────────────── #

def test_a_relative_path_resolves_against_the_linking_document() -> None:
    """Read off the source, because the arithmetic is the kind that looks right.

    `.groma/PROJECT.md` really does link to `../../Society-Specs/01-naming-standards.md`,
    which is outside the corpus. That resolves to a path with nothing behind it, and saying
    so is the caller's job — a renderer that clamped it to something inside the tree would
    have invented a document.
    """
    js = _strip(_read("prose.js"))
    fn = js.split("function resolvePath(", 1)[1].split("\n  }", 1)[0]
    assert 'split("#")[0]' in fn and 'split("?")[0]' in fn, (
        "a fragment or query reaches the path, and `docs.db` is keyed on paths"
    )
    assert 'part === ".."' in fn and "out.pop()" in fn, "`..` does not climb"
    assert "slice(0, -1)" in fn, (
        "the link is resolved against the document rather than against its directory, so "
        "`./x.md` beside `a/b.md` lands on `a/b.md/x.md`"
    )


def test_two_headings_cannot_share_an_anchor() -> None:
    """Which of them a `#anchor` reached would depend on document order (rule 30)."""
    js = _strip(_read("prose.js"))
    fn = js.split("function slug(", 1)[1].split("\n  }", 1)[0]
    assert "seen[base]" in fn, "collisions are not counted, so two headings share an id"
    assert '|| "section"' in fn, (
        "a heading of pure punctuation slugs to the empty string and every one of them "
        "collides on it"
    )


def test_a_document_that_is_not_markdown_renders_as_itself() -> None:
    """45 `.txt` documents are the ordinary case, not a fallback.

    `.rst` and `.adoc` land here too: `DOC_SUFFIXES` admits them, this corpus has **zero**
    of either, and rendering them as text is the honest treatment until a corpus needs
    otherwise. The caller is told *which* happened so it can say so — a document silently
    degraded is design rule 1's defect.
    """
    js = _strip(_read("prose.js"))
    assert 'if (fmt !== "MARKDOWN")' in js, "everything is fed to the markdown parser"
    body = js.split('if (fmt !== "MARKDOWN")', 1)[1].split("}", 1)[0]
    assert "doctext" in body and "<pre" in body, "plain text is not rendered as written"
    assert 'as: "text"' in body and "fmt:" in body, (
        "the caller cannot tell a rendered document from one shown as text, so it cannot "
        "state which it is"
    )
    assert 'as: "markdown"' in js, "a rendered document does not say that it was rendered"


def test_the_renderer_knows_nothing_about_this_page() -> None:
    """The boundary `graph.js` keeps, kept here.

    This turns text into markup. Which document is open, what a link should do when it is
    clicked, and what exists in the corpus are the shell's. A renderer that called the
    shell's functions would be a second place deciding what a click means (rule 51), and it
    could not be tested without the whole application around it.
    """
    js = _strip(_read("prose.js"))
    for name in ("state.", "render()", "DOCPAGE", "DOCINDEX", "selectFromNav", "openDoc",
                 "fetch("):
        assert name not in js, (
            f"the renderer reaches into the shell ({name}); what it has to say must leave "
            "as data attributes"
        )
    assert "window.Prose = Prose" in js, "it exports nothing, so nothing can use it"


# ──────────────────────────── frontmatter, and the line map it could break ──────────── #

def test_frontmatter_is_blanked_and_never_removed() -> None:
    """Half the corpus, and the fix has a trap that would fail silently.

    markdown-it knows nothing about frontmatter, so a document opening
    `---\\nkind: reference\\ntitle: Glossary\\n---` parses it as a **setext heading**: the
    metadata becomes an `<h2>` at the top of the page, before the document's own title, with
    an id of `kind-referencetitle-glossary`. **989 of Mensores' 2,019 Markdown documents**
    begin with a frontmatter block.

    The trap is the fix. Cut the lines out and every `token.map` below shifts up by the
    number removed — so every `data-line` is wrong by a constant, every heading in the nav
    scrolls to the wrong block, and a citation opens a document *near* the line it was read
    from. The page renders perfectly and every number on it is off by four. Blanking the
    lines cannot get the arithmetic wrong because there is no arithmetic.
    """
    js = _strip(_read("prose.js"))
    fn = js.split("function splitFrontmatter(", 1)[1].split("\n  }", 1)[0]
    assert "blanked[j] = \"\"" in fn, (
        "the frontmatter lines are removed rather than blanked, so every data-line below "
        "them is short by the number of lines taken out"
    )
    for bad in ("lines.splice(", "slice(i + 1).join", "shift()"):
        assert bad not in fn, f"the lines are being cut out ({bad}), which shifts the map"
    # A closed block at the very top, and nothing else.
    assert 'lines[0].trim() !== "---"' in fn, (
        "a `---` anywhere is treated as frontmatter, so a horizontal rule mid-document "
        "blanks everything above it"
    )
    assert "return { body: text, front: \"\" };" in fn.rsplit("\n", 3)[-2] or \
           fn.count('front: ""') >= 2, (
        "an opening fence that is never closed is treated as frontmatter, so a document "
        "beginning with a horizontal rule loses its whole body"
    )
    assert "front" in js.split('as: "markdown"', 1)[1].split("}", 1)[0], (
        "the frontmatter is dropped rather than returned, so the caller cannot show what "
        "the document says about itself"
    )
