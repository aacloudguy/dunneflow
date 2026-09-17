# 6. Document

Two lanes sharing one pane, and they are genuinely two subjects rather than two views of
one:

- **the documents DunneFlow writes** about your program — fifteen of them, generated from
  the graph;
- **the documents your program already carries** — the prose its authors wrote, read and
  indexed.

## Lane 2: the map's own documents

![Document mode showing the generated Routines document for web.serve, headed "web.serve 121" with columns ROUTINE, SIGNATURE, WHY and WHERE. Rows for columnar, emit, default_level and read_level each carry a full signature, a paragraph of explanation, and a clickable location badge such as web/serve.py:137](images/06-document-map-lane.jpg)

This is the Routines document for `web.serve` — 121 of them — with a signature, an
explanation and a location for each.

The location badges (`web/serve.py:137`) are the thing to notice. **Every row here carries
the graph node that produced it**, so a row is an ordinary selection: click it and the
stack lights up, the inspector fills, the trail records the hop, and Back will bring you
home. It is not a report you read and leave; it is another way into the same map.

The fifteen documents are the same ones `dunneflow analyze` writes to disk — entrypoints,
flows, routines, data, boundaries, governance and the rest. You can read them in the
dashboard or hand the directory to someone who does not have DunneFlow installed.

## Lane 1: your program's own prose

The other lane is the corpus: every Markdown, reStructuredText and plain-text file found
beside the source, rendered, searchable, and cross-referenced with the code.

DunneFlow's own analysis found **26 documents** carrying **29 definitions** and **45
governance ids**. Those documents are `CLAUDE.md`, `BRIEFING.md`, `RULES.md`, the sixteen
reference chapters — and, the next time you run it, these tutorials.

That last one is not a throwaway. **Re-run the analysis after reading this and this chapter
appears in the corpus lane**, indexed, searchable, and counted in the document total. Try it:

```bash
uv run dunneflow analyze src/dunneflow --name dunneflow
```

The number goes up by however many chapters exist when you run it. The tool makes no
distinction between documentation about a program and documentation that happens to be
about itself, which is the correct amount of distinction to make.

## What the corpus lane is for

Three things, and none of them is "display a README":

**It is where definitions come from.** When the glossary tells you what a word means in
this program, the meaning was quoted out of one of these files, and the citation opens to
the line it came from.

**It is checked against the code.** DunneFlow can tell you which words the documentation
defines that the code never uses, and which words the code uses that nothing defines. Both
lists are useful and they are useful for opposite reasons.

**It is evidence, not decoration.** A design rule says so in as many words: documentation
is evidence, even though it is never code. The corpus is read to find out what the authors
*meant*; it is never read as though it were a description of what the program *does*.

## Four states, not two

A document needs two stores to display: the index that says it exists, and the sidecar that
holds its bytes. Either can be missing on its own, so there are four answers rather than
two, each with its own sentence:

- never scanned;
- scanned, but the bytes were not captured;
- captured, but not for the version you are looking at;
- captured, but not this path.

They look identical on a blank pane and the thing to do about each is different. This is a
pattern you will have noticed by now — DunneFlow would rather write four sentences than let
you mistake one problem for another.

## A note on rendering

The document renderer is the only third-party parser in the entire tool, and it is fenced
off carefully: it turns text into markup and is allowed to know nothing else. Raw HTML is
refused outright, and **an image is never fetched** — an `<img>` would fire a network
request with no click and no consent, out of a tool whose whole posture is that nothing
leaves your machine.

You saw that posture as a number on the cover in [chapter 2](02-the-cover.md). This is the
same decision, one pane over.

---

Next: [7. Diagram](07-diagram.md)
