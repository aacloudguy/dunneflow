"""A broken program must still document, and every finding must state its doubt."""

from __future__ import annotations

import ast
from pathlib import Path

from dunneflow import anomalies
from dunneflow.anomalies import BROKEN, INFO, SUSPECT, detect
from dunneflow.resolve.calls import resolve_calls
from dunneflow.schema import make_id
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

BROKEN_PROGRAM = '''
import os


def handler(a):          # no return type, untyped parameter
    return a


def handler(a, b):       # redefinition: the first is now unreachable
    return a + b


def orphan():
    """Never called, never a way in."""
    return os.getenv("NOTHING")
'''

UNPARSEABLE = "def broken( :\n    pass\n"

# A second module redefining the *same* name. Without it a key of the bare name and a
# key of (module, name) are indistinguishable, and a mutation dropping the module half
# survives every guard -- which is what it did.
OTHER_MODULE = """
def handler(a):
    return a


def handler(a, b):
    return a + b
"""


def _analyze(tmp_path: Path, files: dict[str, str]) -> Store:
    root = tmp_path / "prog"
    root.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (root / name).write_text(body, encoding="utf-8")
    store = Store(tmp_path / "g.db")
    analyze_tree(root, store)
    resolve_calls(store)
    return store



# A loop reaching a database on every pass, and the three shapes that are not that.
#
# The negatives are the point. `LOOPED_BOUNDARY`'s blind spots are only worth the words
# if the cases they name are actually exercised: read as a plain range join over
# `net_calls`, this detector fired twice on Comitia and *both* were poll loops -- two of
# two findings, false. Each routine below is one of the answers the query has to give.
LOOPING = '''
import sqlite3

INDEXES = ("CREATE INDEX one", "CREATE INDEX two")


def per_pass(conn, rows):
    """A query on every pass, over something nothing static can count. The finding."""
    for row in rows:
        conn.execute("INSERT INTO widgets (id) VALUES (?)", (row,))


def over_a_query(conn):
    """The query is what the loop is *over*: one query, however many rows come back."""
    out = []
    for row in conn.execute("SELECT id FROM widgets").fetchall():
        out.append(row[0])
    return out


def polling(conn):
    """A poll loop is this shape on purpose, and says so on its `while`."""
    while conn.execute("SELECT done FROM widgets").fetchone() is None:
        pass


def over_a_constant(conn):
    """A bound the program declares, and a reader can read it off the line above."""
    for stmt in INDEXES:
        conn.execute(stmt)


def over_a_literal(conn):
    """A bound written at the loop itself."""
    for name in ("a", "b"):
        conn.execute("DELETE FROM widgets WHERE name=?", (name,))
'''


def _looped(store):
    found = [a for a in detect(store).items if a.kind == "LOOPED_BOUNDARY"]
    assert len(found) == 1, f"expected one grouped finding, got {len(found)}"
    return found[0]


def test_a_loop_that_queries_on_every_pass_is_reported(tmp_path):
    """One grouped finding on `NO_TIMEOUT`'s model: one thing to think about, and every
    place to look at it. The count comes off the same list the occurrences do, so the
    two cannot disagree (rule 13)."""
    found = _looped(_analyze(tmp_path, {"m.py": LOOPING}))
    assert found.severity == INFO, "never SUSPECT: a local store is not a network"
    assert found.count == len(found.occurrences) == 1
    assert "per_pass" in found.occurrences[0].label
    assert found.occurrences[0].nav == "routine", "a span is not a node in the graph"


def test_a_query_the_loop_is_over_is_not_a_query_per_pass(tmp_path):
    """`for row in conn.execute(q).fetchall():` runs one query, not one per row.

    9 of Comitia's 74 are this shape, and reporting them would be reporting the
    detector's own defect back at the reader.
    """
    found = _looped(_analyze(tmp_path, {"m.py": LOOPING}))
    assert not [o for o in found.occurrences if "over_a_query" in o.label], found.detail


def test_the_three_bounded_shapes_are_named_and_not_reported(tmp_path):
    """No filter is silent (design rule 1), and it is the ones left out that make the
    ones reported credible -- exactly as the 1,222 still loops make the 261 rates.

    A poll loop, a declared collection and a literal at the loop each say how many
    passes they make, so each is stated in the detail rather than dropped from it.
    """
    found = _looped(_analyze(tmp_path, {"m.py": LOOPING}))
    for name in ("polling", "over_a_constant", "over_a_literal"):
        assert not [o for o in found.occurrences if name in o.label], name
    assert "while loop" in found.detail
    assert "this program declares" in found.detail
    assert "written at the loop" in found.detail


def test_a_program_with_no_looped_query_reports_nothing(tmp_path):
    """A detector that fires on a clean program is a detector nobody can trust."""
    store = _analyze(tmp_path, {"m.py": BROKEN_PROGRAM})
    assert not [a for a in detect(store).items if a.kind == "LOOPED_BOUNDARY"]


def test_a_broken_program_still_produces_a_graph(tmp_path):
    """Ingest must never fail on bad input -- that is the whole point."""
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    assert store.counts()["files"] == 2
    assert store.counts()["routines"] > 0  # the good file survived
    store.close()


def test_parse_failure_is_reported_as_broken(tmp_path):
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE})
    report = detect(store)
    parse = [a for a in report.items if a.kind == "PARSE_ERROR"]
    assert parse and parse[0].severity == BROKEN
    store.close()


def test_redefinition_is_found(tmp_path):
    store = _analyze(tmp_path, {"good.py": BROKEN_PROGRAM})
    kinds = {a.kind for a in detect(store).items}
    assert "REDEFINITION" in kinds
    store.close()


def test_dead_code_states_that_tests_were_excluded(tmp_path):
    """The blind spot that would have prevented six wrong conclusions."""
    store = _analyze(tmp_path, {"good.py": BROKEN_PROGRAM})
    dead = [a for a in detect(store, include_tests=False).items if a.kind == "DEAD_CODE"]
    assert dead
    assert "excluded" in dead[0].blind_spot.lower()
    included = [
        a for a in detect(store, include_tests=True).items if a.kind == "DEAD_CODE"
    ]
    assert "included" in included[0].blind_spot.lower()
    store.close()


def test_every_finding_carries_a_blind_spot(tmp_path):
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    for a in detect(store).items:
        assert a.blind_spot.strip(), f"{a.kind} has no blind spot"
        assert a.severity in (BROKEN, SUSPECT, INFO)
        assert a.title.strip()
    store.close()


def test_severity_and_confidence_are_independent(tmp_path):
    """A finding can be certain but harmless, or severe but uncertain."""
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    items = detect(store).items
    pairs = {(a.severity, a.confidence) for a in items}
    assert len({s for s, _ in pairs}) > 1
    store.close()


def test_report_sorts_broken_first(tmp_path):
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    order = [a.severity for a in detect(store).sorted()]
    assert order == sorted(order, key=lambda s: {BROKEN: 0, SUSPECT: 1, INFO: 2}[s])
    store.close()


def test_clean_program_reports_nothing_broken(analyzed):
    assert detect(analyzed).broken == 0


# --------------------------------------------------------------------------- #
# Identity: what makes two findings in two versions the same finding.
#
# The question these answer was open from 2026-08-30 until it was measured. It blocks
# the comparison overlay, because a finding that cannot be paired can only be reported
# as *new*, and a false new is rule 1's defect with a colour on it.
# --------------------------------------------------------------------------- #


def test_every_detector_declares_what_identifies_its_finding():
    """Asserted as an absence over the whole module, not case by case.

    The failure this guards against is a **new detector** rather than a change to an
    existing one -- which is exactly what a second language brings, since detectors are
    query-driven and a Kotlin or C++ extractor's facts will want detectors of their own.
    A test naming the ones that exist today would pass the day the next is
    written without an identity.

    `ident_parts` has no default, so omitting it is already a `TypeError`. This says the
    same thing one level up, where it can be read: it is the *rule*, and the constructor
    is one enforcement of it.
    """
    src = ast.parse(Path(anomalies.__file__).read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(src)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Anomaly"
    ]
    # The guard cannot pass by finding nothing (rule 37).
    assert len(calls) >= 18, f"only {len(calls)} findings constructed -- guard is blind"
    for call in calls:
        named = {kw.arg for kw in call.keywords}
        kind = next(
            (ast.literal_eval(kw.value) for kw in call.keywords
             if kw.arg == "kind" and isinstance(kw.value, ast.Constant)),
            f"line {call.lineno}",
        )
        assert "ident_parts" in named, f"{kind} does not say what identifies it"


def test_no_finding_is_identified_by_where_it_sits():
    """A key holding a position renders the comparison as noise.

    Measured on Lictores' pair: keyed with `file`, three of the 106 pairings are lost and
    reported as a removal plus an addition. For a detector that groups, `file` is
    `MIN(file)` -- it names one member of the group arbitrarily and moves when an
    unrelated file changes. `line` moves whenever anything above it does, for anyone.
    That is `make_id`'s own argument, and `changes.py` makes it again for facts.

    One rule, and it has no exception list:

    * a part is never the `line`;
    * a part is never the `file`, **unless the file is also the subject** -- unless, that
      is, the finding is *about* that file.

    `PARSE_ERROR` is the whole reason the second half is conditional: it reports one
    finding per error in a file and the path genuinely is what it is about, so it is
    admitted by the rule rather than excused from it. `UNRESOLVED_MOUNT` sits one inch
    away and is not: a mount moved to another module is the same unresolved mount.

    Compared as *expressions*, never by name, because `MIN(file) f` reaches the
    construction site as `row["f"]` -- and a guard reading the word "file" passes over
    the exact defect it was written to catch. That is not hypothetical: it is what the
    first version of this test did.
    """
    src = ast.parse(Path(anomalies.__file__).read_text(encoding="utf-8"))
    checked = 0
    for node in ast.walk(src):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "Anomaly"):
            continue
        by = {kw.arg: kw.value for kw in node.keywords}
        parts = by.get("ident_parts")
        if parts is None:
            continue
        elts = parts.elts if isinstance(parts, ast.Tuple) else [parts]
        dumps = {ast.dump(e) for e in elts}

        if (line := by.get("line")) is not None:
            assert ast.dump(line) not in dumps, (
                f"line {node.lineno}: a finding identified by its line"
            )
            checked += 1

        if (fl := by.get("file")) is not None:
            subject = by.get("subject")
            about_that_file = subject is not None and ast.dump(subject) == ast.dump(fl)
            if not about_that_file:
                assert ast.dump(fl) not in dumps, (
                    f"line {node.lineno}: identified by a file it is not about"
                )
            checked += 1
    # The guard cannot pass by finding nothing to compare (rule 37).
    assert checked >= 12, f"only {checked} comparisons made -- guard is blind"


def test_a_finding_that_counts_a_set_is_not_identified_by_a_member_of_it():
    """`count=len(rows)` says the finding is *about* the set it counted.

    Keyed by one of them -- the first routine with no timeout, the first dead one -- it
    would move whenever that member changed, which is churn about a finding that has not
    changed at all. It is rule 32 in an identity: the key must name what the finding
    counts, and what it counts is the whole set.
    """
    src = ast.parse(Path(anomalies.__file__).read_text(encoding="utf-8"))
    checked = 0
    for node in ast.walk(src):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "Anomaly"):
            continue
        by = {kw.arg: kw.value for kw in node.keywords}
        count = by.get("count")
        counts_a_set = (
            isinstance(count, ast.Call) and isinstance(count.func, ast.Name)
            and count.func.id == "len"
        )
        if not counts_a_set:
            continue
        parts = by.get("ident_parts")
        assert isinstance(parts, ast.Tuple) and not parts.elts, (
            f"line {node.lineno}: counts a set and is identified by something in it"
        )
        checked += 1
    assert checked >= 3, f"only {checked} set-counting findings -- guard is blind"


def test_a_finding_that_is_about_the_whole_program_says_so(tmp_path):
    """`()` is a statement -- there is one of these per program -- not an omission.

    Before this it was an empty `subject` that fell out of a default argument, which
    reads the same and claims nothing. The two are told apart by asking whether the
    findings of such a kind are unique on kind alone.
    """
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    items = detect(store).items
    whole = [a for a in items if not a.ident_parts]
    assert whole, "no whole-program finding fired -- guard is blind"
    kinds = [a.kind for a in whole]
    assert len(kinds) == len(set(kinds)), (
        f"a kind claiming to be one per program appears twice: {kinds}"
    )
    store.close()


def test_no_two_findings_of_one_report_share_an_identity(tmp_path):
    """Two findings under one id means the comparison speaks about one of them twice."""
    store = _analyze(tmp_path, {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM})
    idents = [a.ident for a in detect(store).items]
    assert len(idents) == len(set(idents))
    store.close()


def test_a_genuine_repeat_is_disambiguated_rather_than_merged():
    """Four detectors do not group, so their key can honestly repeat.

    Two errors in one file, two indexes of one name over one table. The ordinal is the
    same residue `_identity()` gives colliding qualnames -- a position of last resort,
    stated rather than hidden -- and the point is that neither finding is lost.
    """
    r = anomalies.Report()
    for _ in range(3):
        r.add(anomalies.Anomaly(
            kind="PARSE_ERROR", severity=BROKEN, confidence="CERTAIN",
            title="t", detail="d", blind_spot="b", ident_parts=("a.py", "boom"),
        ))
    assert len({a.ident for a in r.items}) == 3
    assert [a.ident_parts[-1] for a in r.items] == ["boom", "#2", "#3"]


def test_an_identity_survives_the_same_source_read_somewhere_else(tmp_path):
    """The one claim the whole feature rests on.

    Two versions of a program are two directories, so an id that depended on where the
    tree was read from would pair nothing at all -- which is exactly what stored absolute
    paths did to the file-level diff before rule 60.
    """
    files = {"bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM}
    here = _analyze(tmp_path / "one", files)
    there = _analyze(tmp_path / "two", files)
    assert {a.ident for a in detect(here).items} == {a.ident for a in detect(there).items}
    here.close()
    there.close()


def test_the_same_name_redefined_in_two_modules_is_two_findings(tmp_path):
    """The corpus has to be able to tell the key apart from a weaker one.

    A key of the bare name looks perfectly correct against a program with one module,
    which is what the fixtures were until this: the mutation dropping `module` survived
    every guard in this file. Two modules each redefining `handler` is the smallest
    program that can see the difference.
    """
    store = _analyze(tmp_path, {"good.py": BROKEN_PROGRAM, "other.py": OTHER_MODULE})
    redefs = [a for a in detect(store).items if a.kind == "REDEFINITION"]
    assert len(redefs) == 2, [a.subject for a in redefs]
    assert len({a.ident for a in redefs}) == 2, "one module's redefinition ate the other's"
    store.close()


def test_two_errors_in_one_file_are_two_findings():
    """Asserted of the key rather than through the extractor, deliberately.

    Python stops at the first syntax error, so no fixture in *this* language can produce
    a file with two -- and that is exactly the reason to state it here. Detectors are
    query-driven, so a Kotlin or C++ extractor's `files.errors` runs through this same
    detector, and those compilers report many. A key of the path alone is correct only
    for the language that happens to be first.
    """
    r = anomalies.Report()
    for message in ("expected ')'", "unexpected indent"):
        r.add(anomalies.Anomaly(
            kind="PARSE_ERROR", severity=BROKEN, confidence="CERTAIN",
            title="t", detail=message, blind_spot="b",
            ident_parts=("a.kt", message), subject="a.kt", file="a.kt",
        ))
    assert len({a.ident for a in r.items}) == 2
    # …and neither took the ordinal: they are told apart by what they say, not by order.
    assert not any(p.startswith("#") for a in r.items for p in a.ident_parts)


def test_a_finding_can_never_wear_a_routine_s_identity():
    """Both are `make_id` over names, and the dashboard selects by id.

    Without the `"finding"` prefix a `DEAD_CODE` finding keyed by a qualname would carry
    the id of the routine of that name, and a click would land on whichever the lookup
    reached first. The prefix is the same namespacing `make_id("ep", ...)` already uses.
    """
    name = "lictores.cli.main"
    finding = anomalies.Anomaly(
        kind="DEAD_CODE", severity=INFO, confidence="POSSIBLE",
        title="t", detail="d", blind_spot="b", ident_parts=(name,),
    )
    assert finding.ident != make_id(name)
    assert finding.ident != make_id("DEAD_CODE", name)


def test_a_key_carries_every_loop_the_finding_is_emitted_inside():
    """A detector that emits per iteration and keys on less than it iterates over.

    `_parse_failures` loops over files and then over each file's errors: keyed on the
    path alone, every error in one file is one id, and all but the first vanish into the
    ordinal `Report.add` gives a genuine repeat. That is the merge this whole design
    exists to prevent, wearing the costume of the mechanism written to prevent it.

    Stated structurally because it cannot be reached behaviourally *in Python* -- the
    interpreter stops at the first syntax error, so no fixture here can produce a file
    with two. A Kotlin or C++ front end reports many, and detectors are query-driven, so
    the same detector will read them. The guard has to see what the fixtures cannot.
    """
    src = ast.parse(Path(anomalies.__file__).read_text(encoding="utf-8"))
    parents = {child: node for node in ast.walk(src) for child in ast.iter_child_nodes(node)}

    def enclosing_loop_targets(node: ast.AST) -> set[str]:
        names: set[str] = set()
        while (node := parents.get(node)) is not None:
            if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
            if isinstance(node, ast.FunctionDef):
                break
        return names

    checked = 0
    for node in ast.walk(src):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "Anomaly"):
            continue
        parts = next((kw.value for kw in node.keywords if kw.arg == "ident_parts"), None)
        if parts is None:
            continue
        targets = enclosing_loop_targets(node)
        if not targets:
            continue
        used = {n.id for n in ast.walk(parts) if isinstance(n, ast.Name)}
        assert targets <= used, (
            f"line {node.lineno}: emitted once per {sorted(targets - used)} and "
            f"identified by none of it"
        )
        checked += 1
    assert checked >= 8, f"only {checked} looping findings -- guard is blind"


def test_the_declared_keys_need_no_tie_breaking_on_this_corpus(tmp_path):
    """The ordinal is a last resort, and a guard has to be able to see it being one.

    `Report.add` disambiguates an exact repeat rather than merging it, which is right --
    and it means a **weak key looks fine to a uniqueness test**: two findings that should
    have had different keys get different ids anyway, told apart by their order rather
    than by anything about them. That is how a mutation dropping `module` from
    `REDEFINITION`'s key survived every guard here.

    So this asserts the stronger thing: on a corpus with no genuine repeat in it, no
    finding falls back on the ordinal at all. Measured the same way on Lictores, both
    versions: zero. If a fixture is ever added that *does* hold a legitimate repeat --
    two indexes of one name, a language reporting two errors in a file -- this test has
    to say so out loud rather than be relaxed quietly.
    """
    store = _analyze(tmp_path, {
        "bad.py": UNPARSEABLE, "good.py": BROKEN_PROGRAM, "other.py": OTHER_MODULE,
    })
    residues = [
        (a.kind, a.ident_parts) for a in detect(store).items
        if a.ident_parts and a.ident_parts[-1].startswith("#")
    ]
    assert not residues, f"a declared key could not tell two findings apart: {residues}"
    store.close()
