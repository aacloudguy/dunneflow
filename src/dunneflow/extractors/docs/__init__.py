"""The documentation extractor: one document in, `DocFacts` out.

The same contract the Python extractor keeps. Nothing downstream knows whether a fact
came from Markdown, reStructuredText, or a plain text file -- adding a documentation
format means writing one function here, exactly as adding a language means writing one
extractor under `extractors/`.

Ingest never fails on a bad document. An unreadable file yields a recorded error and an
otherwise empty `DocFacts`, because a corpus that stops at its first malformed file
documents a smaller project than the one that exists.
"""

from __future__ import annotations

import re
from pathlib import Path

from ...schema import DocFacts, DocFormat, Heading, hash_source, stored_path
from .markdown import _text, scan_markdown, scan_with

MARKDOWN_SUFFIXES = frozenset({".md", ".markdown", ".mdx"})
DOC_SUFFIXES = MARKDOWN_SUFFIXES | {".rst", ".txt", ".adoc"}

FORMATS = {
    ".md": DocFormat.MARKDOWN,
    ".markdown": DocFormat.MARKDOWN,
    ".mdx": DocFormat.MARKDOWN,
    ".rst": DocFormat.RST,
    ".txt": DocFormat.TEXT,
    ".adoc": DocFormat.ADOC,
}

# reStructuredText marks a heading by underlining it with punctuation. The level is the
# order in which each punctuation character is first seen, which is the convention the
# format actually uses rather than a fixed table.
RST_UNDERLINE = re.compile(r"^([=\-`:'\"~^_*+#<>])\1{2,}\s*$")


def _rst_headings(lines: list[str], start: int, mask: list[bool]) -> list[Heading]:
    order: list[str] = []
    out: list[Heading] = []
    stack: list[tuple[int, str]] = []
    for i in range(start, len(lines)):
        m = RST_UNDERLINE.match(lines[i])
        if not m or i == start:
            continue
        title = lines[i - 1].strip()
        if not title or len(title) > len(lines[i].strip()) + 2:
            continue
        char = m.group(1)
        if char not in order:
            order.append(char)
        level = order.index(char) + 1
        while stack and stack[-1][0] >= level:
            stack.pop()
        trail = " > ".join(t for _, t in stack)
        out.append(Heading(level=level, text=_text(title), line=i, path=trail))
        stack.append((level, _text(title)))
    return out


def _no_headings(lines: list[str], start: int, mask: list[bool]) -> list[Heading]:
    return []


def extract_doc(path: Path, root: Path) -> DocFacts:
    """Read one document. The worker entry point; must stay picklable and pure."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # Keyed the same way as a document that *was* read. An unreadable file recorded
        # under a different spelling of its own name is a row nothing else can join to.
        try:
            unread = stored_path(path.resolve().relative_to(root.resolve()))
        except ValueError:
            unread = stored_path(path)
        return DocFacts(path=unread, fmt=DocFormat.TEXT, content_hash="",
                        errors=[f"unreadable: {exc}"])

    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path

    # `rel` is the key as well as the classifier's input. It was computed here from the
    # first day and then thrown away, with `str(path)` -- one machine's absolute layout --
    # stored as the identity of every document. See `extract_file` for why that is wrong
    # in three separate ways; the argument is the same for prose as for code.
    key = stored_path(rel)

    fmt = FORMATS.get(path.suffix.lower(), DocFormat.TEXT)
    try:
        if fmt is DocFormat.MARKDOWN:
            facts = scan_markdown(key, rel, text, fmt)
        elif fmt is DocFormat.RST:
            facts = scan_with(key, rel, text, fmt, _rst_headings)
        else:
            facts = scan_with(key, rel, text, fmt, _no_headings)
    except Exception as exc:  # a malformed document is a fact, not a crash
        facts = DocFacts(path=key, fmt=fmt, content_hash=hash_source(text))
        facts.errors.append(f"{type(exc).__name__}: {exc}")
    return facts


__all__ = ["DOC_SUFFIXES", "extract_doc"]
