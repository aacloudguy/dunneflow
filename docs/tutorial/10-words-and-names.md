# 10. Words and names

Open **VOCABULARY** in the navigator. There are four rows:

![The VOCABULARY group in the navigator, counted 4, with Glossary selected. Its rows read Glossary 223, Stated naming rules 0, Stated rules, checked 3, and Derived naming standard 16](images/10-vocabulary-group.png)

| | |
|---|---|
| Glossary | 223 |
| Stated naming rules | 0 |
| Stated rules, checked | 3 |
| Derived naming standard | 16 |

Two questions, and they are not the same one. *What do this program's words mean* is the
glossary. *How are its names spelled* is the other three, which look like one question and
are three — what the code does, what somebody wrote down, and whether they agree.

## The glossary

![The glossary page. Four provenance tiers are listed at the top: DECLARED · code "quoted from a docstring in this program", DECLARED · docs "quoted from the project's own documents — none here", CITED "a model found it in prose and cited the line — checkable — none here", INFERRED "nothing in the project explains it; this is a guess — none here". A highlighted paragraph reads "82 of the 223 words this program uses as names are defined somewhere it can quote. 2 definitions were found across 52 distinct documents — a byte-identical copy is read once — and every one of them names the file and the line it came from. The 141 the program does not define are listed below rather than left out: a word carried by fifty constants and explained nowhere is a finding. A further 197 are held back at the foot of this page — they occur only inside a compound constant name — and any of them can be put in the worklist. Every citation here opens — in the bytes this map measured, not the tree as it stands now." Below, a filter box reading "Filter 223 words…" and "82 defined and 141 undefined — nothing hidden", then the entry for calls — 11 constants, 5 modules, 2 tables — with DECLARED · code definitions such as "Call sites, their arguments as written, and the boundaries the rules recognise." from cpp/calls.py:1 and kotlin/calls.py:1, "Turning call expressions into edges — the driver." from resolve/calls.py:1, "Which definition a Python call expression meant." from python/calls.py:1, and "Which definition a TypeScript call meant — looked up, never argued for.", each with a show me button](images/10-glossary.jpg)

DunneFlow mines the words this program uses as *names* — packages, classes, tables, ways
in, constants — and then goes looking for somewhere they are defined. On itself:

> **82 of the 223 words this program uses as names are defined somewhere it can quote.**

The four tiers at the top are the whole provenance system in one block, and on this map
three of them say **none here**:

| | |
|---|---|
| DECLARED · code | quoted from a docstring in this program |
| DECLARED · docs | quoted from the project's own documents — **none here** |
| CITED | a model found it in prose and cited the line — checkable — **none here** |
| INFERRED | nothing in the project explains it; this is a guess — **none here** |

The lower two tiers exist, are declared, and are empty — and stay empty, because nothing
on the analysis path calls a model. That is not a placeholder waiting to be filled in.
It is the shape of the promise: *if* inference ever happens, it will arrive in a tier of
its own and be labelled, rather than mixed in with the quotations.

The empty **DECLARED · docs** tier is a different kind of empty, and an honest one. The
documents *were* read — two definitions were found across them — but neither defines a
word the program uses as a name, so every one of the 82 definitions on this page is a
docstring quoted out of the code. ([Chapter 13](13-the-command-line.md)'s `mirror` says
what became of the two.) And it counts the documents honestly: 52 *distinct* ones, because
one of the 53 files is a byte-identical copy of another, and a copy is read once.

Every definition carries a file and a line, and a **show me** button that opens the
bytes — out of the copy captured when the map was made, not out of the tree as it stands
today. That distinction matters the first time you read a map of a version you no longer
have checked out.

### The 141 and the 197

Two numbers on that page are about things DunneFlow *could not* do, and both are printed
rather than quietly dropped.

**141 undefined** words are listed with the rest. A word carried by fifty constants and
explained nowhere is a finding, not a gap in the report.

**197 held back** is subtler and worth understanding, because it is the difference
between a useful worklist and a useless one. A constant's name is split on underscores,
so `_GLOSSARY_DEFINITION_MAX_LEN` contributes `glossary`, `definition`, `max` and `len` —
and three of those four are the name's type and its unit, not the program's vocabulary.
Any word that is *only ever* a fragment inside a constant's name, and that nothing
defines, is set aside at the foot of the page with the reason. It is one click to put any
of them back.

The held-back list opens with `ROUTINE`, `CURIO`, `HOVER` and `BOUNDARY` — out of names
like `CODE_FILE_ROUTINE_COUNTS`, `CURIO_ARGUMENT`, `HOVER_ANNOTATIONS` and `BOUNDARY_NODES`.
Without the rule, words like those would sit in the undefined list between the ones
actually worth defining.

## What the code does with names

Click **Derived naming standard**.

![The derived naming standard page. Three highlighted notes: "This standard was derived from the code, not required of it. Every convention below was found by counting what the program actually does. None of it was imposed by anyone, and none of it is measured against a standard your team wrote — that is stated rules, checked, and it measures a rule somebody stated rather than a convention found here. So a convention holding 100% of the time means the code is consistent, not that it is correct.", followed by "A leading underscore is counted as a violation here, which is the strict reading. Settings can allow it as a privacy mark."; "Somebody may also have written naming rules down. Those are quoted rather than counted, and they live on their own page so that neither can be mistaken for the other. Neither page compares them", with a link reading "Stated naming rules — 0 read from your documents"; and "Every figure here is counted, not guessed. The exceptions are the point." Below, a section headed HOW NAMES ARE SPELLED · 11 with the line "Measured per row rather than per distinct name", and the first convention: "Python routines", graded B, "Python routines are named in snake_case.", a bar reading 1,231 of 1,247, and a list headed 16 EXCEPTIONS beginning do_GET web/serve.py:3644 and do_POST web/serve.py:3669](images/10-derived.jpg)

Sixteen conventions, each with a grade, a count and every exception named:

```
[B] 1,231/1,247  Python routines are named in snake_case.          (16 exceptions)
[B]     611/621  A routine marked private is called only
                 from its own module.                               (10 exceptions)
[B]     432/434  Python parameters are named in snake_case.          (2 exceptions)
[B]     211/213  Python database tables are named in snake_case.     (2 exceptions)
[D]     165/182  Python classes are named in PascalCase.            (17 exceptions)
[D]     146/157  Python data structures are named in PascalCase.    (11 exceptions)
[A]     131/131  Python modules are named in snake_case.
[A]     120/120  TypeScript routines are named in camelCase.
[A]       80/80  TypeScript parameters are named in camelCase.
[C]       48/50  TypeScript data structures are named in PascalCase. (2 exceptions)
[A]       16/16  Python commands are named in kebab-case.
[A]       15/15  A routine beginning with `cmd` is registered as a way in.
[D]       12/13  A class ending in `Kind` is an enumeration.         (1 exception)
[A]       11/11  TypeScript modules are named in snake_case.
[A]       11/11  TypeScript modules begin with `plugins`.
[A]         6/6  A routine ending in `meta` is touching the DATABASE boundary.
```

**The exceptions are the point**, and the page says so. Sixteen Python routines are not
`snake_case`, and reading them tells you something no percentage could: `do_GET`,
`do_POST`, and fourteen `visit_ClassDef`-shaped names. Those are not sloppiness. They are
two protocols — `http.server` wants `do_GET`, `ast.NodeVisitor` wants `visit_ClassDef` —
and the spelling is not this program's to choose.

That is the whole argument for grading rather than scoring. A convention that holds every
time tells you how to read the program; one that holds nearly every time tells you *where
to look*.

**Every spelling convention names a language.** DunneFlow's own source is Python and
TypeScript, and *"routines are named in snake_case"*, measured over both at once, used to
come out a `D` — with every one of its exceptions a TypeScript name spelled the way
TypeScript spells names. One grade made of two answers that were each nearly perfect.
**A convention is a fact about a population**, and *"this program spells names like
this"* is not a question a mixed corpus can answer, so the population is split by the one
thing the map can actually be asked: what language each file is in. The *affix*
conventions (`cmd`, `Kind`, `meta`) are deliberately **not** split: an affix is a word a
team chose rather than a way of spelling one, and a team that says `cmd` says it in every
language it writes.

And the note at the top is the other half:

> This standard was derived from the code, not required of it. … So a convention holding
> 100% of the time means the code is consistent, not that it is correct.

## What somebody wrote down

Click **Stated naming rules**. It says **0**.

![The stated naming rules page with no rules. The first note reads "These are quoted, not counted, and nothing on this page is measured. Every rule below was written by somebody and read out of a document with a file and a line you can open. Measuring one against this program is stated rules, checked; here a rule and a convention on the derived naming standard may contradict each other and neither page will say so." The second reads "53 documents were read (1 of them a byte-identical copy of another), and not one of them states a naming rule. That is a finding rather than an absence of one: the derived naming standard shows what the code does about names, and nothing in this project records what it was supposed to do. A rule has to name a class of identifier or a house word to be recognised here; a paragraph that merely discusses naming is deliberately not mined, because a research paper about naming standards once yielded ten confident rules that were not rules at all." A panel headed WHAT THE CODE ACTUALLY DOES, marked "the other lane", explains that this page is what your documents say and the derived naming standard is what the code was found to do, and links to the derived naming standard's 16 conventions](images/10-stated-none.jpg)

A zero is the most interesting thing on this page, because of how carefully it is
distinguished from two other zeros that look identical:

| | |
|---|---|
| no documentation was read at all | *we did not look* |
| documents were read and there were none | *there was nothing to look at* |
| **53 documents were read, and not one states a naming rule** | *we looked, and this is the answer* |

All three arrive at the browser as an empty list. Flattening them would turn *"we did not
look"* into *"there is nothing there"*, so the count travels beside the list and the page
picks its sentence from it.

And the answer is true. DunneFlow's own corpus is 53 documents, among them a file of more
than a hundred engineering rules, and not one of them is a naming rule. The detector will
not mine a paragraph that merely *discusses* naming — the note says why, and it is a
scar: a research paper *about* building a naming-standards importer once yielded ten
confident rules that were not rules at all.

## Whether they agree

Click **Stated rules, checked**. This is the page the other two keep pointing at.

![The stated rules, checked page. A note reads "This page is the comparison, and it is the only one that is. The stated naming rules quote what somebody wrote and count nothing; the derived naming standard counts what the code does and quotes nobody. Here each stated rule is measured over the population its own document says it governs — and a rule this map cannot answer says so rather than passing quietly.", then "A leading underscore is counted as a violation here, which is the strict reading. Settings can allow it as a privacy mark.", then "3 of 3 rules could be checked, finding 18 exceptions." Below, a section headed CHECKED · 3 with the line "Measured over the population the rule governs. Every exception is listed — the exceptions are the product." The first card reads "classes · PascalCase", tagged IMPORTED, sourced from naming.md:13, quoting "Classes: PascalCase", with a bar reading 165 of 182, the note "over classes — scoped by **/*.py, which the rule's own document declares", and 17 EXCEPTIONS beginning ClassDef_ schema.py:617, Exception_ resolve/naming.py:208, Field_ schema.py:213, _AppResolver resolve/cli.py:35, _AsyncCost anomalies.py:45, _Base web/serve.py:330, _Clock web/serve.py:515, _Extractor python/extract.py:175, _FieldPlan ingest/codec.py:92, _Handler web/serve.py:1443 and _Index python/calls.py:63](images/10-checked.jpg)

> 3 of 3 rules could be checked, finding 18 exceptions.

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

**Every exception is listed**, and the seventeen are the interesting part again. Fourteen
of them — `_Base`, `_Handler`, `_Live`, `_Scanner` and friends — are PascalCase with a
leading underscore, and `ClassDef_`, `Exception_`, `Field_` have a trailing one to avoid
colliding with a name they wrap. The other two rules account for the eighteenth: one
constant, `Decision`, is not SCREAMING_SNAKE_CASE, and all 131 modules are snake_case.

**165 of 182.** You have seen that number before — it is exactly what the *derived* page
graded D for `Python classes are named in PascalCase`. The same population, the same count,
reached from two directions: one by asking the code what it does, the other by asking a
document what it requires and measuring it. They agree because they are measuring the same
thing, and the tool still keeps them on separate pages, because the day they disagree is
the day you need to know which one you are reading.

### Is `_Handler` PascalCase?

Strictly, no: it does not begin with a capital. It is also the commonest way a codebase
marks something private, and whether your standard meant to cover that is a question for
the standard, not for DunneFlow. So the answer is yours to choose, in **Settings**, on the
row **A leading underscore in a name**:

| | |
|---|---|
| **Counted as a violation** | the strict reading, and the default |
| **Allowed** | the underscore is read as a privacy mark, and the rest of the name is judged |

Both naming pages follow it, and each says in its opening note which reading is in force.
Choose **Allowed** and come back:

![The stated rules, checked page with the Setting changed. The note now reads "A leading underscore is allowed here — read as a privacy mark, not part of the spelling. Strictly it is a violation; Settings has the choice.", then "3 of 3 rules could be checked, finding 4 exceptions." The classes · PascalCase card, IMPORTED from naming.md:13, now reads 179 of 182, with 3 EXCEPTIONS: ClassDef_ schema.py:617, Exception_ resolve/naming.py:208 and Field_ schema.py:213, followed by "How this number was counted — show the query" and "Read the rule as it was written — go". The next card, constants · SCREAMING_SNAKE_CASE from naming.md:14, begins below](images/10-checked-allowed.jpg)

> 3 of 3 rules could be checked, finding 4 exceptions.

**179 of 182**, and the three left are the trailing underscores, which no reading of a
privacy mark excuses. The derived page moves with it: classes go to 179 of 182 and data
structures to 154 of 157, both graded B, and every convention the choice applies to says
*(a leading underscore allowed)* in its claim. The Setting changes which question is asked,
never what was counted — switch it back and the seventeen return.

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
  [B] 1,231/1,247  Python routines are named in snake_case.  (16 exceptions)
  …
```

`naming --allow-leading-underscore` is the Setting from the last section, for a terminal:
the classes line becomes `[B] 179/182 Python classes are named in PascalCase (a leading
underscore allowed).`

`mirror` is the third question and the one with no page of its own: **words the documents
define that the code never uses.** On DunneFlow it reads two definitions, and both are
wrong in an instructive way — they are headings out of this tutorial, as it stood when the
map was made, that happen to be shaped like definitions: *The 111 and the 159*, and
chapter 13's *The vocabulary, without a browser*. Both are set aside as phrases rather than
words, so nothing is carried forward and every row of its table reads 0. (*The glossary*,
at the top of this chapter, used to be read as a third; a heading whose next line is only an
image no longer counts as defining anything.) The command's own last line is the blind
spot, and it is read off the map rather than written into the program:

> only Python and TypeScript are extracted: absent from this graph is not absent from the
> product.

That sentence said *only Python* until DunneFlow could read a second language, and it was
one of five places that claimed it. None of them says it any more because none of them
decides it: the languages are `SELECT DISTINCT lang FROM files`, so a map read by a build
with a third reader in it says so without anybody editing a sentence.

---

Next: [11. Worth a look](11-worth-a-look.md)
