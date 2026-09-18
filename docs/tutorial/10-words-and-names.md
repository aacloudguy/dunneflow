# 10. Words and names

Open **VOCABULARY** in the navigator. There are four rows:

| | |
|---|---|
| Glossary | 155 |
| Stated naming rules | 0 |
| Stated rules, checked | 3 |
| Derived naming standard | 10 |

*(Those are the recorded session's counts — see [a note on the
numbers](README.md#a-note-on-the-numbers). Run it today and the glossary reads 198 and the
derived standard 15, for the reason set out under **What the code does with names** below,
which is the one place this chapter's subject has changed rather than its figures.)*

Two questions, and they are not the same one. *What do this program's words mean* is the
glossary. *How are its names spelled* is the other three, which look like one question and
are three — what the code does, what somebody wrote down, and whether they agree.

## The glossary

![The glossary page. Four provenance tiers are listed at the top: DECLARED · code "quoted from a docstring in this program", DECLARED · docs "quoted from the project's own documents", CITED "a model found it in prose and cited the line — checkable — none here", INFERRED "nothing in the project explains it; this is a guess — none here". A highlighted paragraph reads "44 of the 155 words this program uses as names are defined somewhere it can quote. 29 definitions were found across 26 documents, and every one of them names the file and the line it came from. The 111 the program does not define are listed below rather than left out: a word carried by fifty constants and explained nowhere is a finding. A further 159 are held back at the foot of this page — they occur only inside a compound constant name — and any of them can be put in the worklist. Every citation here opens — in the bytes this map measured, not the tree as it stands now." Below, a filter box reading "Filter 155 words…" and "44 defined and 111 undefined — nothing hidden", then entries for calls, docs and constants, each with a DECLARED · code definition, a file and line, and a "show me" button](images/10-glossary.jpg)

DunneFlow mines the words this program uses as *names* — packages, classes, tables, ways
in, constants — and then goes looking for somewhere they are defined. On itself:

> **44 of the 155 words this program uses as names are defined somewhere it can quote.**

The four tiers at the top are the whole provenance system in one block, and two of them
say **none here**:

| | |
|---|---|
| DECLARED · code | quoted from a docstring in this program |
| DECLARED · docs | quoted from the project's own documents |
| CITED | a model found it in prose and cited the line — checkable — **none here** |
| INFERRED | nothing in the project explains it; this is a guess — **none here** |

The lower two tiers exist, are declared, and are empty — and stay empty, because nothing
on the analysis path calls a model. That is not a placeholder waiting to be filled in.
It is the shape of the promise: *if* inference ever happens, it will arrive in a tier of
its own and be labelled, rather than mixed in with the quotations.

Every definition carries a file and a line, and a **show me** button that opens the
bytes — out of the copy captured when the map was made, not out of the tree as it stands
today. That distinction matters the first time you read a map of a version you no longer
have checked out.

### The 111 and the 159

Two numbers on that page are about things DunneFlow *could not* do, and both are printed
rather than quietly dropped.

**111 undefined** words are listed with the rest. A word carried by fifty constants and
explained nowhere is a finding, not a gap in the report.

**159 held back** is subtler and worth understanding, because it is the difference
between a useful worklist and a useless one. A constant's name is split on underscores,
so `_GLOSSARY_DEFINITION_MAX_LEN` contributes `glossary`, `definition`, `max` and `len` —
and three of those four are the name's type and its unit, not the program's vocabulary.
Any word that is *only ever* a fragment inside a constant's name, and that nothing
defines, is set aside at the foot of the page with the reason. It is one click to put any
of them back.

Without that rule, the undefined list opens with `DDL`, `EXTRAS`, `BYTES` and `CHARS`,
and the words actually worth defining are somewhere below the fold.

## What the code does with names

Click **Derived naming standard**.

![The derived naming standard page. Three highlighted notes: "This standard was derived from the code, not required of it. Every convention below was found by counting what the program actually does. None of it was imposed by anyone, and none of it is measured against a standard your team wrote — that is stated rules, checked, and it measures a rule somebody stated rather than a convention found here. So a convention holding 100% of the time means the code is consistent, not that it is correct."; "Somebody may also have written naming rules down. Those are quoted rather than counted, and they live on their own page so that neither can be mistaken for the other. Neither page compares them", with a button reading "Stated naming rules — 0 read from your documents"; and "Every figure here is counted, not guessed. The exceptions are the point." Below, a section headed HOW NAMES ARE SPELLED · 7 and the first convention: "routines", graded B, "Routines are named in snake_case", a bar reading 790 of 806, and a list headed 16 EXCEPTIONS beginning do_GET, do_POST, visit_Assign, visit_AsyncWith, visit_Await, visit_Call, visit_ClassDef, visit_Constant](images/10-derived.jpg)

Ten conventions, each with a grade, a count and every exception named:

```
[B] 790/806  Routines are named in snake_case.            (16 exceptions)
[B] 383/388  A routine marked private is called only
             from its own module.                          (5 exceptions)
[B] 332/334  Parameters are named in snake_case.           (2 exceptions)
[B] 198/200  Database tables are named in snake_case.      (2 exceptions)
[D] 113/124  Classes are named in PascalCase.             (11 exceptions)
[D] 107/115  Data structures are named in PascalCase.      (8 exceptions)
[A]   78/78  Modules are named in snake_case.
[A]   14/14  A routine beginning with `is` is a predicate: it returns a boolean.
[A]   13/13  Commands are named in snake_case.
[A]   12/12  A routine beginning with `cmd` is registered as a way in.
```

> ### This page has changed shape since that screenshot, and the reason is worth the detour
>
> DunneFlow reads **two languages** now, and its own `src/dunneflow` is 107 Python files
> and 11 TypeScript. Run the same page today and you get **fifteen** conventions, not ten,
> and the spelling ones each name a language:
>
> ```
> [B] 991/1,007  Python routines are named in snake_case.        (16 exceptions)
> [A]   116/116  TypeScript routines are named in camelCase.
> [B]   388/390  Python parameters are named in snake_case.       (2 exceptions)
> [A]     79/79  TypeScript parameters are named in camelCase.
> [A]   107/107  Python modules are named in snake_case.
> [A]     11/11  TypeScript modules are named in snake_case.
> ```
>
> **The old line was not merely out of date — it was wrong, and by 100 names.** Measured
> across both languages at once, *"routines are named in snake_case"* scored **1,014 of
> 1,114**, a `D` with a hundred exceptions; and every single one of those hundred was a
> TypeScript name spelled the way TypeScript spells names. One number, 91%, made of two
> answers that are 98% and 100%.
>
> That is this chapter's own argument arriving one level up. **A convention is a fact about
> a population**, and *"this program spells names like this"* is not a question a mixed
> corpus can answer — so the population is split by the one thing the map can actually be
> asked, which is what language each file is in. The *affix* conventions (`cmd`, `is`) are
> deliberately **not** split: an affix is a word a team chose rather than a way of spelling
> one, and a team that says `cmd` says it in every language it writes.
>
> Everything else on the page is exactly as the screenshots show it: the grade, the bar,
> the named exceptions, and the two notes about what a derived standard is and is not.

**The exceptions are the point**, and the page says so. Sixteen routines are not
`snake_case`, and reading them tells you something no percentage could: `do_GET`,
`do_POST`, and fourteen `visit_ClassDef`-shaped names. Those are not sloppiness. They are
two protocols — `http.server` wants `do_GET`, `ast.NodeVisitor` wants `visit_ClassDef` —
and the spelling is not this program's to choose.

That is the whole argument for grading rather than scoring. A convention that holds every
time tells you how to read the program; one that holds nearly every time tells you *where
to look*.

And the note at the top is the other half:

> This standard was derived from the code, not required of it. … So a convention holding
> 100% of the time means the code is consistent, not that it is correct.

## What somebody wrote down

Click **Stated naming rules**. It says **0**.

![The stated naming rules page with no rules. The first note reads "These are quoted, not counted, and nothing on this page is measured. Every rule below was written by somebody and read out of a document with a file and a line you can open. Measuring one against this program is stated rules, checked; here a rule and a convention on the derived naming standard may contradict each other and neither page will say so." The second reads "26 documents were read, and not one of them states a naming rule. That is a finding rather than an absence of one: the derived naming standard shows what the code does about names, and nothing in this project records what it was supposed to do. A rule has to name a class of identifier or a house word to be recognised here; a paragraph that merely discusses naming is deliberately not mined, because a research paper about naming standards once yielded ten confident rules that were not rules at all." A panel headed WHAT THE CODE ACTUALLY DOES explains that this page is what your documents say and links to the derived naming standard's 10 conventions](images/10-stated-none.jpg)

A zero is the most interesting thing on this page, because of how carefully it is
distinguished from two other zeros that look identical:

| | |
|---|---|
| no documentation was read at all | *we did not look* |
| documents were read and there were none | *there was nothing to look at* |
| **26 documents were read, and not one states a naming rule** | *we looked, and this is the answer* |

All three arrive at the browser as an empty list. Flattening them would turn *"we did not
look"* into *"there is nothing there"*, so the count travels beside the list and the page
picks its sentence from it.

And the answer is true. DunneFlow's own corpus is 26 documents including a file of
ninety-three engineering rules, and not one of them is a naming rule. The detector will
not mine a paragraph that merely *discusses* naming — the note says why, and it is a
scar: a research paper *about* building a naming-standards importer once yielded ten
confident rules that were not rules at all.

## Whether they agree

Click **Stated rules, checked**. This is the page the other two keep pointing at.

![The stated rules, checked page. A note reads "This page is the comparison, and it is the only one that is. The stated naming rules quote what somebody wrote and count nothing; the derived naming standard counts what the code does and quotes nobody. Here each stated rule is measured over the population its own document says it governs — and a rule this map cannot answer says so rather than passing quietly. 3 of 3 rules could be checked, finding 11 exceptions." Below, a section headed CHECKED · 3 with the line "Measured over the population the rule governs. Every exception is listed — the exceptions are the product." The first card reads "classes · PascalCase", tagged IMPORTED, sourced from naming.md:13, quoting "Classes: PascalCase", with a bar reading 113 of 124, the note "over classes — scoped by **/*.py, which the rule's own document declares", and 11 EXCEPTIONS listed: ClassDef_, Exception_, Field_, _AppResolver, _Base, _Extractor, _Handler, _Index, _Live, _Progress, _Scanner. Two links read "How this number was counted — show the query" and "Read the rule as it was written — go"](images/10-checked.jpg)

> 3 of 3 rules could be checked, finding 11 exceptions.

Where did three rules come from, when the last page said zero? From outside. This map was
built with a standards directory:

```bash
uv run dunneflow analyze src/dunneflow --name dunneflow --standards ../dunnecorp-standards
```

`--standards` reads somebody else's naming standard through the same document scan as
your own corpus, into a store of its own, and every rule it yields is tagged **IMPORTED**
and cites the document it came from — here `naming.md:13`.

Three things on this page are worth more than the numbers.

**The population is never inferred from the wording.** The rule says *Classes:
PascalCase*, and the card says what it measured that over: `over classes — scoped by
**/*.py, which the rule's own document declares`. A rule that named a population this map
cannot supply would say *no population here*, and one whose spelling cannot be tested —
a template like `NN-kebab-name` — would be quoted back and declared **not checkable**.
Three verdicts, never two, because collapsing any of them lets *"we could not check"*
read as *"it passes"*.

**Every exception is listed**, and the eleven are the interesting part again: `_Base`,
`_Handler`, `_Live`, `_Scanner` and friends are PascalCase with a leading underscore, and
`ClassDef_`, `Exception_`, `Field_` have a trailing one to avoid colliding with a name
they wrap. Whether your standard meant to cover those is a question for the standard, and
DunneFlow's job is to hand you the eleven names rather than a verdict.

**113 of 124.** You have seen that number before — it is exactly what the *derived* page
graded D for `Classes are named in PascalCase`. The same population, the same count,
reached from two directions: one by asking the code what it does, the other by asking a
document what it requires and measuring it. They agree because they are measuring the same
thing, and the tool still keeps them on separate pages, because the day they disagree is
the day you need to know which one you are reading.

## From the command line

```bash
uv run dunneflow glossary output/dunneflow
uv run dunneflow naming   output/dunneflow
uv run dunneflow mirror   output/dunneflow
```

`naming` prints both lanes at once, and leads with the empty one:

```
STATED — nothing in this program's documentation states a naming rule

MEASURED — counted against the code
  [B] 790/806  Routines are named in snake_case.  (16 exceptions)
  …
```

Run today, that second lane leads with the split described above — `[B] 991/1,007 Python
routines are named in snake_case` and `[A] 116/116 TypeScript routines are named in
camelCase` — over the same fifteen conventions the page draws.

`mirror` is the third question and the one with no page of its own: **words the documents
define that the code never uses.** On DunneFlow it finds three, and all three are wrong in
an instructive way — they are sentences lifted out of a session journal that happen to be
shaped like definitions. The command's own last line is the blind spot, and it is read off
the map rather than written into the program:

> only Python and TypeScript are extracted: absent from this graph is not absent from the
> product.

That sentence said *only Python* until DunneFlow could read a second language, and it was
one of five places that claimed it. None of them says it any more because none of them
decides it: the languages are `SELECT DISTINCT lang FROM files`, so a map read by a build
with a third reader in it says so without anybody editing a sentence.

---

Next: [11. Worth a look](11-worth-a-look.md)
