# The probe tree the fingerprint gate reads

**Not a test fixture in the usual sense.** Nothing asserts what is in these files; what the
gate needs is that every reader this build registers finds *something here to read*, so that
its stamp is compared against a real map rather than against nothing (rule 37).

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

## Why the three files do not share a stem

They were `probe.py`, `probe.ts` and `probe.cpp`, and that tree **cannot be analysed**:

    sqlite3.IntegrityError: UNIQUE constraint failed: routines.id

Python and TypeScript both derive a module name from the path with the suffix removed, so
both files are module `probe`, both declare `main`, and `probe.main` is one id in two
languages. It is a defect between the two readers that were here before C++ — the C++ reader
puts the file in every identity and is immune — and it is in `BACKLOG.md` with this
reproduction rather than fixed in passing, because the fix changes how an id is derived and
that discards every stored map.

So the stems differ, and the reason is written down instead of being a detail nobody can
account for. `kotlin_probe.kt` joined them when Kotlin was registered, which is the rule
this directory exists to enforce: the test fails until the new language has a file here.
