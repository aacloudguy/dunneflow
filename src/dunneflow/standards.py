"""A standards directory: somebody else's rules, admitted without being absorbed.

`--docs` reads the prose *this program* carries. This reads prose the program does not
carry and was never asked to: an organisation's naming standard, filed somewhere else and
governing many repositories at once. Tom, 2026-09-04: *"a known standards directory as a
baseline against which to compare what is really found. The goal is to show reality, not
the plan."*

**The rules land in `standards.db`, never in `docs.db`, and that is the whole design.** A
standards document is not prose somebody wrote *about this program*, and `docs.db` is read
by the glossary, the mirror, traceability, Document mode's corpus lane and every count on
the About panel. Marking the rows instead would put a filter in each of those places and
make every one of them a place that has to remember -- the seven-read-paths shape rule 51
was minted from. A separate file means no existing consumer changes and nothing can leak.
It is `docsource.db`'s argument exactly: the same store, a different subject, its own file.

**Rule 57, one directory further out.** That rule was paid for by two stale worktrees under
`.claude/` putting 335 of Mensores' 2,381 documents into the map -- a second copy of the
project's governance documents, from before a rename the ground truth rests on. The walk
learned to refuse a nested checkout. Admitting a root the reader *names* opens three more
ways for a program to read itself as its own standard, and each is refused with its own
sentence: they are indistinguishable as an empty store, and what to do about each differs
(design rule 21).

The refusal is total. A root that overlaps is not quietly scanned-less (rule 20: a read may
refuse, but it may never repair) -- because scanning less would silently drop exactly the
rules the reader pointed at, and report a smaller standard as the whole of one.
"""

from __future__ import annotations

from pathlib import Path

# The name the store takes under a program's output directory. Unversioned, like
# `docsource.db` and unlike `graph@<revision>.db`: a standard is what it was when it was
# read, and the revision it was read alongside is recorded in its own `meta`.
STANDARDS_DB = "standards.db"


def standards_refusal(
    root: Path,
    *,
    tree: Path,
    out_root: Path,
    docs_root: Path | None,
) -> str | None:
    """Why this directory may not be admitted as a standard, or `None` to admit it.

    One function rather than a check at the call site, because the sentence is the product:
    `analyze` prints it, the tests assert it, and a refusal a reader cannot read is a
    refusal they will work around. Rule 51 -- the guard moves to where every caller passes.

    `tree` is the source root being analysed, `out_root` the directory maps are written
    under, and `docs_root` the documentation root this run is already reading (`None` under
    `--no-docs`, which is why the tree is tested separately rather than assumed to be
    inside it).
    """
    root = root.resolve()

    # **Where it is, before whether it is there.** Both questions can be true at once, and
    # the order decides which sentence the reader gets: a path typed into `output/` that
    # does not exist yet is a reader about to make a structural mistake, and telling them
    # only *"does not exist"* invites them to create it and try again. Containment is
    # knowable without touching the disk, so it is asked first and answered first.

    # The tool's own output is the refusal a reader cannot see coming. `output/` holds a map
    # *about* a program, and reading a generated report back as somebody's naming standard
    # would mint rules out of this tool's own prose -- the failure `walk.py` already names
    # for the document corpus, arriving through a flag instead of a walk.
    # `output/` holds a map *about* a program, and reading a generated report back as
    # somebody's naming standard would mint rules out of this tool's own prose -- the
    # failure `walk.py` already names for the document corpus, arriving through a flag.
    if root == out_root or root.is_relative_to(out_root):
        return (f"{root} is inside the output root {out_root} — that is this tool's own "
                "output, and reading a map back as a standard would mint rules from it")

    # Already this program's own prose. Admitting it twice would count one rule as two and
    # present the program's own words back to it as an outside baseline, which is the one
    # comparison this feature exists not to make.
    if docs_root is not None and (root == docs_root or root.is_relative_to(docs_root)):
        return (f"{root} is inside the documentation root {docs_root} — it is already read "
                "as this program's own prose, and a standard is what somebody else states")

    # Under `--no-docs` the documentation root is not being read at all, so the source tree
    # is the live test rather than a subset of one already made.
    if root == tree or root.is_relative_to(tree):
        return (f"{root} is inside the analysed tree {tree} — a standard the program "
                "carries is its own documentation, not a baseline to measure it against")

    # Only now: it is in a legitimate place, so the remaining question is whether it is
    # usable. A missing root is refused rather than scanned as nothing, because an empty
    # store and a directory that was never there look identical downstream and only one of
    # them is a program with no standard to meet (design rule 21).
    if not root.exists():
        return f"{root} does not exist"
    if not root.is_dir():
        return f"{root} is a file, and a standards root is a directory"

    return None
