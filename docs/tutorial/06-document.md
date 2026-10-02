# 6. Document

Two lanes sharing one pane, and they are genuinely two subjects rather than two views of
one:

- **the documents DunneFlow writes** about your program — eight of them in the dashboard,
  generated from the graph;
- **the documents your program already carries** — the prose its authors wrote, read and
  indexed.

## Lane 2: the map's own documents

![Document mode showing the generated Routines document at the section headed "resolve.entrypoints 12", with columns ROUTINE, SIGNATURE, WHY and WHERE. The selected row is entrypoints_from_manifests, with the signature "entrypoints_from_manifests(readings, store, tree) -> list[Entrypoint]", its docstring paragraph beginning "Bind, mint and record every way in the manifests declared.", and a location badge reading resolve/entrypoints.py:252. Above it the end of the previous row's paragraph shows; below it collisions, "collisions(readings) -> list[str]" at resolve/entrypoints.py:305, begins a paragraph of its own. The trail ends "entrypoints_from_manifests › Table › Code › Table › Document"](images/06-document-map-lane.jpg)

This is the Routines document, opened at your selection: the section for
`resolve.entrypoints`, 12 routines, with a signature, an explanation and a location for each.

The location badges (`resolve/entrypoints.py:252`) are the thing to notice. **Every row here carries
the graph node that produced it**, so a row is an ordinary selection: click it and the
stack lights up, the inspector fills, the trail records the hop, and Back will bring you
home. It is not a report you read and leave; it is another way into the same map.

The eight documents here — entrypoints, routines, data, constants, boundaries, database,
network and artefacts — cover the same ground as the fifteen Markdown files
`dunneflow analyze` writes to disk, which you can hand to someone who does not have
DunneFlow installed. They are not those files read back. A Markdown file has already thrown
away which node each line came from, so the dashboard builds its documents again from the
graph, and every row keeps its node.

## Lane 1: your program's own prose

The other lane is the corpus: every Markdown, reStructuredText and plain-text file found
beside the source, rendered, searchable, and cross-referenced with the code.

![Document mode with "The program's own 53" chosen over "The map". A blue note reads "No document in this map is about entrypoints_from_manifests. It carries no plan, ticket or decision id, so there is nothing for a document to have in common with it. What follows is the whole corpus — DunneFlow relates code to prose through the plan, ticket and decision ids they both name, and this one shares none." Beside a "Filter by path or title…" box: "All 53 documents." Under OTHER 47 are listed, each with its title, path, word count and section count: Backlog BACKLOG.md 1,178w 3 §, the design rules, ground truth, adding a language, packaging, the measured budgets PERFORMANCE.md 13,404w 27 §, the rules RULES.md 28,188w 1 §, third-party notices, then the user guide's chapters from 1. Installing docs/01-installing.md 2,108w 9 § down to 5. The shell](images/06-corpus-lane.jpg)

DunneFlow's own analysis found **53 documents** carrying **2 definitions** and **13
governance ids**. Those documents are `CLAUDE.md`, `README.md`, `RULES.md` and the other
reference files at the top of the tree, the sixteen chapters of the user guide, the
licence texts the tree carries — and these tutorials, this chapter included.

That last one is not a throwaway. The map was made from a tree that already held this
chapter, so **it is in the corpus lane now**, indexed, searchable, and counted in the 53.
Add a chapter of your own and re-run the analysis, and the number goes up by one. The tool
makes no distinction between documentation about a program and documentation that happens
to be about itself, which is the correct amount of distinction to make.

Notice what the note above the list says, too. Nothing in the corpus is *about*
`entrypoints_from_manifests`, and the lane says so and why, instead of showing you a list
and letting you assume it was filtered. Prose and code are related here through the plan,
ticket and decision ids they both name, and this routine names none.

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
