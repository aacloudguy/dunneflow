# The probe tree the fingerprint gate reads

**It answers two questions, and it was written for the first.** The gate needs every reader
this build registers to find *something here to read*, so that its stamp is compared against a
real map rather than against nothing (rule 37). Since 2026-09-19 it is also the corpus rule
106 was minted from — see the last section, which is the reason the four files share a stem.

`tools/fingerprints.py` points here by default. It used to point at `src/dunneflow`, which
was the right answer for exactly as long as the languages this tool reads were the languages
this tool is **written in** — 107 Python files and 11 TypeScript, real code, on every machine
that builds DunneFlow. C++ ended that: the package will never hold a `.cpp`, so the probe
tree could no longer exercise every reader and `test_the_default_probe_tree_holds_every_
language_this_build_reads` failed saying so, which is what it was written to do.

**One file per registered language, and each one has to be worth reading.** A file with no
routines and no boundaries produces no rows, and a stamp compared over an empty map is the
same nothing the old probe would have compared C++'s against. So each holds a way in, a
boundary touch, a loop and a branch — enough that both builds have something to disagree
about if they are going to.

Adding a language means adding a file here. The test fails until you do.

## Why the four files share a stem, which is the point

They are `probe.py`, `probe.ts`, `probe.cpp` and `probe.kt` **deliberately**. For a day they
could not be: named that way, this tree could not be analysed at all.

    sqlite3.IntegrityError: UNIQUE constraint failed: routines.id

Python and TypeScript both derive a module name from the path with the suffix removed, so
both files were module `probe`, both declare `main`, and `probe.main` was one id in two
languages. The stems were forced apart, the reproduction written down here, and the fix filed
as `BACKLOG.md` item 6 — because it changes how an id is derived and that discards every
stored map on every machine.

It was taken on 2026-09-19. A definition is keyed on **the file it is in** as well as its
name (`schema.definition_id`, rule 106), so four files can share a stem, one module name, and
a `main` apiece. Putting the stems back is what proves it: this tree is the smallest program
that could not be read, and it is now read.

`tests/test_identity.py` asserts that property against this directory, so the fixture is not
only a probe for the fingerprint gate any more — it is also the corpus rule 106 was minted
from. Adding a language means adding a file here, and it may share the stem.
