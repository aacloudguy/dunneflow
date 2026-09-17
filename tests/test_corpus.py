"""Serving the document corpus: the list, one document, and every way it is absent.

Two stores answer together and either can be missing on its own, which is four states and
not two: documentation scanned and captured, scanned but not captured, captured for a path
this version does not hold, and never scanned at all. Each has its own sentence. A blank
pane cannot tell them apart, and the thing a reader does about each one is different --
re-analyse without `--no-docs`, re-analyse without `--no-doc-source`, switch versions, or
nothing at all because the file genuinely is not in this program.

Every test here is a way that can go wrong while looking right:

  - a document list bounded, so a corpus of 2,064 quietly shows 500 (rule 8);
  - a class count that no longer counts the rows printed under it (rule 13);
  - the document routes reading the *source* sidecar, which holds no `.md` path and would
    report every document missing (rule 16's spirit -- two stores, two routes);
  - a body read at the newest revision while the map is showing an older one (rule 70);
  - an absence rendered as an empty list, which reads as "this program has no
    documentation" and is a different and false claim (design rule 21).
"""

from __future__ import annotations

import ast
import inspect
import re
from collections import Counter
from pathlib import Path

import pytest

from dunneflow import revisions
from dunneflow.docstore import DocStore
from dunneflow.extractors.docs import extract_doc
from dunneflow.extractors.python.extract import extract_file
from dunneflow.sourcedb import DocSourceStore, SourceStore, capture
from dunneflow.store import Store
from dunneflow.web import corpus
from dunneflow.web import serve as serve_mod

REV = "2026-09-03T10:00:00Z"

# One of each class the detector recognises, so the group counts have something to be
# wrong about. Three deliberate things in here:
#
#   * the **fenced block** spans lines, and a body sent as anything but one string cuts it
#     in half;
#   * `notes.txt` is not markdown, and the corpus admits 45 such files on Mensores;
#   * `docs/copy.md` is byte-identical to `docs/glossary.md`. Mensores has eight real
#     duplicates, and without one here every guard about `duplicate_of` -- including the
#     one that says the class counts count the rows they are printed over -- passes on a
#     corpus that has nothing to be filtered out of it.
GLOSSARY = "# Glossary\n\n**mensor** — one who measures.\n"
CORPUS = {
    "README.md": "# The program\n\nWhat it is for.\n\n## Running it\n\n```sh\nrun --now\n```\n",
    "docs/glossary.md": GLOSSARY,
    "docs/copy.md": GLOSSARY,
    "notes.txt": "Not markdown. Just words.\n",
}


def _corpus(tmp_path: Path, *, bodies: bool = True) -> tuple[Path, Path]:
    """A tree of documents and the program directory a scan of it would leave.

    With a graph beside them, small but real: `_Live.open` builds a base out of one, and
    the document store this chunk added is a field of that base. A fixture with documents
    and no graph could exercise `corpus.py` and nothing that serves it.
    """
    tree = tmp_path / "tree"
    out = tmp_path / "prog"
    out.mkdir()
    for rel, text in CORPUS.items():
        f = tree / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    (tree / "m.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    graph = Store(revisions.db_path(out, revisions.GRAPH, REV))
    graph.write_file_facts(extract_file(tree / "m.py", tree))
    graph.set_meta("revision", REV)
    graph.conn.commit()
    graph.close()

    docs = DocStore(revisions.db_path(out, revisions.DOCS, REV))
    docs.set_meta("revision", REV)
    for rel in CORPUS:
        docs.write_doc_facts(extract_doc(tree / rel, tree))
    # As `analyze` does. Without it `duplicate_of` is empty on every row and the copy is
    # indistinguishable from an ordinary document.
    assert docs.mark_duplicates() == 1, "the fixture's duplicate is not being recognised"
    docs.conn.commit()
    docs.close()

    if bodies:
        store = DocSourceStore(out / "docsource.db")
        store.adopt_revision(REV, tree="tree")
        reopened = DocStore(revisions.db_path(out, revisions.DOCS, REV), writable=False)
        capture(reopened.known_hashes(), store, root=tree, revision=REV)
        reopened.close()
        store.close()
    return out, tree


def _open(out: Path, *, bodies: bool = True) -> tuple[DocStore, DocSourceStore | None]:
    docs = DocStore(revisions.db_path(out, revisions.DOCS, REV), writable=False)
    src = (DocSourceStore(out / "docsource.db", writable=False) if bodies else None)
    return docs, src


# --------------------------------------------------------- the list --- #

def test_the_list_is_every_document_and_its_counts_come_from_those_rows(
        tmp_path: Path) -> None:
    """Rule 8 and rule 13 in one answer, because they fail together.

    A `LIMIT` here would show 500 of 2,064 with a heading saying 2,064, and the heading is
    the only thing that would look wrong. So the group counts are a `Counter` over the rows
    this returns rather than a second `GROUP BY`: the two cannot disagree because there is
    only one query.
    """
    out, _tree = _corpus(tmp_path)
    docs, src = _open(out)
    got = corpus.build_corpus(docs, src, revision=REV)

    assert got["available"] is True
    assert {d["path"] for d in got["documents"]} == set(CORPUS), (
        "the list is not every document the scan read"
    )
    assert got["total"] == len(got["documents"]), (
        "the total and the rows behind it are two numbers about one thing (rule 32)"
    )
    counted = {c["name"]: c["n"] for c in got["classes"]}
    assert counted == dict(Counter(d["class"] for d in got["documents"])), (
        "a class count no longer counts the rows printed under it"
    )
    assert sum(counted.values()) == got["total"], (
        "the groups do not partition the list — a document is in none of them or in two"
    )
    # The copy is *listed*, not filtered. `duplicate_of` is a fact about the corpus, and a
    # reader who cannot see the copies cannot tell a deduplicated list from a short one.
    copies = [d for d in got["documents"] if d["duplicateOf"]]
    assert len(copies) == 1, "the copy is not in the list, or both twins were marked"
    # Which of the two is called the original is `mark_duplicates`' business, not this
    # module's -- what matters here is that the copy names one, and that the one it names
    # is a document the reader can actually go to.
    assert copies[0]["duplicateOf"] in {d["path"] for d in got["documents"]}, (
        "a copy points at a document that is not in the list"
    )
    docs.close()
    if src is not None:
        src.close()


def test_the_list_has_no_limit_in_its_sql() -> None:
    """Read off the statement, because a bound added later has no symptom at this size.

    Three documents in a fixture cannot notice a `LIMIT 500`. Mensores' 2,064 can, and by
    then the number on the heading and the rows under it disagree in a way that looks like
    a filter working.
    """
    assert "LIMIT" not in corpus.CORPUS_DOCUMENTS.upper(), (
        "the document list is bounded — rule 8 bounds a diagram, and only a diagram"
    )


def test_every_row_says_whether_its_body_can_be_opened(tmp_path: Path) -> None:
    """A complete list where nothing opens is a real state, and it must say so.

    `--no-doc-source` leaves `docs.db` entire and captures no bodies at all. The list is
    still worth having — it is what the program documents — but every row is unopenable,
    and a reader who clicks one is owed the reason rather than a blank pane.
    """
    out, _tree = _corpus(tmp_path, bodies=False)
    docs, _ = _open(out, bodies=False)
    got = corpus.build_corpus(docs, None, revision=None)

    assert got["available"] is True, "no bodies is not the same as no documents"
    assert got["sidecar"] is False
    assert got["openable"] == 0
    assert not any(d["held"] for d in got["documents"])
    assert got["reason"] and "--no-doc-source" in got["reason"], (
        "a list where nothing opens does not say why (design rule 21)"
    )
    docs.close()


def test_no_documentation_at_all_is_stated_and_not_an_empty_list() -> None:
    """`--no-docs` and "this program has no documentation" are different claims.

    An empty list makes the second one, and it is false. Rule 11: documentation and source
    are equal inputs and neither may be *assumed* — which cuts both ways, because assuming
    its absence is a claim too.
    """
    got = corpus.build_corpus(None, None)
    assert got["available"] is False
    assert "--no-docs" in got["reason"]
    assert "documents" not in got, (
        "an unavailable corpus still ships a list — the caller cannot tell it from an "
        "analysed program with nothing in it"
    )


# ----------------------------------------------------- one document --- #

def test_a_document_arrives_whole_with_its_headings(tmp_path: Path) -> None:
    """The body is one string, and the fenced block is the reason.

    A renderer needs the document entire because block structure spans lines: a fence cut
    into numbered lines is not a fence any more, and `token.map` — the property the library
    was chosen for — is what supplies the line numbers instead.
    """
    out, _tree = _corpus(tmp_path)
    docs, src = _open(out)
    got = corpus.build_document(docs, src, "README.md", revision=REV)

    assert got["available"] is True
    assert got["document"]["title"] == "The program"
    assert [h["text"] for h in got["headings"]] == ["The program", "Running it"]
    assert all(h["line"] > 0 for h in got["headings"]), (
        "a heading with no line cannot be navigated to"
    )
    assert got["headings"] == sorted(got["headings"], key=lambda h: h["line"]), (
        "headings are not in reading order — a table of contents that does not describe "
        "the document it is over"
    )
    assert got["body"]["available"] is True
    assert got["body"]["text"] == CORPUS["README.md"], (
        "the body came back changed — it is the bytes that were captured, or it is not "
        "what was measured"
    )
    assert "```sh\nrun --now\n```" in got["body"]["text"]
    docs.close()
    if src is not None:
        src.close()


def test_the_three_absences_of_one_document_are_three_sentences(tmp_path: Path) -> None:
    """Never scanned, no sidecar, not held. They look identical on a blank pane.

    And they are three different things to do about it: nothing, re-analyse without
    `--no-doc-source`, or switch to the version that holds the file.
    """
    out, _tree = _corpus(tmp_path)
    docs, src = _open(out)

    never = corpus.build_document(docs, src, "docs/nowhere.md", revision=REV)
    assert never["available"] is False
    assert never["reason"] == corpus.NOT_SCANNED

    # The row is a fact of `docs.db` and survives a missing sidecar, so the refusal is on
    # the **body** rather than on the document. That distinction is the answer to a real
    # question -- what does this program document -- being available when the prose is not.
    nosidecar = corpus.build_document(docs, None, "README.md")
    assert nosidecar["available"] is True
    assert nosidecar["body"]["available"] is False
    assert nosidecar["body"]["reason"] == corpus.NO_SIDECAR

    # Scanned, and a sidecar that holds nothing at this revision -- which is what a base
    # switch onto a version captured before the sidecar existed looks like.
    unheld = corpus.build_document(docs, src, "README.md", revision="2020-01-01T00:00:00Z")
    assert unheld["available"] is True, "the row is still known; only the body is missing"
    assert unheld["body"]["available"] is False
    assert unheld["body"]["reason"] == corpus.NOT_HELD

    assert len({corpus.NOT_SCANNED, corpus.NO_SIDECAR, corpus.NO_DOCS, corpus.NOT_HELD}) == 4, (
        "two absences share a sentence, so the reader cannot tell them apart"
    )
    docs.close()
    if src is not None:
        src.close()


# ------------------------------------------------------- the routes --- #

def test_a_version_with_no_bodies_is_refused_not_served_from_the_newest(
        tmp_path: Path) -> None:
    """The defect the running server found, and the reason a curl beat 859 tests.

    `_sidecar_revision` returns `None` for *this sidecar cannot serve the version on
    screen*. Every store here reads `revision=None` as *the current one*. Two meanings,
    one spelling, and the newer one won: Mensores' 2026-08-26 base listed all 2,041 of its
    documents as openable and served the **2026-08-29** prose under them — every heading's
    line landing wherever the text had since moved.

    It is rule 70's own failure, one corpus over. The source sidecar never showed it
    because it holds both snapshots; the document sidecar holds one, so the older base is
    the first version anything has ever had no bodies for.
    """
    out, _tree = _corpus(tmp_path)
    docs, src = _open(out)

    listed = corpus.build_corpus(docs, src, revision=None)
    assert listed["available"] is True, "the documents are still known; the prose is not"
    assert listed["openable"] == 0, (
        "a version with no bodies marked its documents openable — they would open at the "
        "newest snapshot, under this version's line numbers"
    )
    assert listed["reason"] == corpus.NO_REVISION, (
        "the list does not say which absence this is, so 'this map has no document "
        "bodies' and 'this version has none' read the same"
    )
    assert listed["sidecar"] is True, (
        "a program that *has* a document sidecar is reported as having none — two "
        "different things to do about it, and re-analysing is only one of them (rule 32)"
    )

    one = corpus.build_document(docs, src, "README.md", revision=None)
    assert one["body"]["available"] is False
    assert one["body"]["reason"] == corpus.NO_REVISION
    assert corpus.NO_REVISION != corpus.NO_SIDECAR, "the two absences share a sentence"
    docs.close()
    if src is not None:
        src.close()


def test_the_span_reader_refuses_a_version_it_has_no_bodies_for() -> None:
    """The same hole in the other reader, which `/api/source` shares.

    A span asked for at a `None` revision resolves to the newest snapshot below, so the
    refusal has to be above it. Read off the source because the alternative is standing up
    a server: what matters is that the check exists *before* the store is asked.
    """
    src = inspect.getsource(serve_mod._Handler._span)
    body = ast.parse(src.strip())
    guarded = [n for n in ast.walk(body) if isinstance(n, ast.If)
               and "rev is None" in ast.unparse(n.test)]
    assert guarded, (
        "`_span` passes a `None` revision to the store, which reads it as 'the newest' — "
        "the bytes of a version nobody is looking at, under this version's marks (rule 70)"
    )


def test_the_three_document_routes_are_in_the_table() -> None:
    """Design rule 16: a control wired to nothing looks exactly like one that works."""
    routes = serve_mod._Handler.ROUTES
    assert routes["/api/docs"] == "_r_docs"
    assert routes["/api/doc"] == "_r_doc"
    assert routes["/api/docsource"] == "_r_docsource"
    for name in ("_r_docs", "_r_doc", "_r_docsource"):
        assert callable(getattr(serve_mod._Handler, name)), f"{name} is routed to nothing"


def test_the_document_routes_read_the_document_sidecar(tmp_path: Path) -> None:
    """Two stores, two routes, nothing guessed — and the failure is silent, not loud.

    `source.db` and `docsource.db` have identical schemas, so a document route pointed at
    the source sidecar does not raise. It looks up `docs/glossary.md` in a store of Python
    files, finds nothing, and reports the document as missing — which is indistinguishable
    from a document that really is not held.
    """
    for name in ("_r_docs", "_r_doc", "_r_docsource"):
        src = inspect.getsource(getattr(serve_mod._Handler, name))
        assert "self._live.docsource" in src, (
            f"{name} does not name the document sidecar"
        )
        assert "self._live.source" not in src, (
            f"{name} reads the *source* sidecar — every document would report as missing"
        )
        assert "docsource_revision" in src, (
            f"{name} does not name this version's document revision (rule 70): the newest "
            "snapshot's prose under an older version's headings"
        )


def test_the_source_and_document_spans_are_one_implementation() -> None:
    """Rule 51: the rule lives where both callers pass, not at each call site.

    Four refusals, two stores. Copied, the copy would be right on the day it was written
    and would then be one refusal short of the original for as long as nobody looked.
    """
    for name in ("_r_source", "_r_docsource"):
        body = ast.parse(inspect.getsource(getattr(serve_mod._Handler, name)).strip())
        calls = [n for n in ast.walk(body) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "_span"]
        assert len(calls) == 1, f"{name} no longer routes through the shared span reader"


def test_the_document_sidecar_is_opened_as_its_own_kind() -> None:
    """Rule 16, at the one place the server opens it.

    `SourceStore` would open `docsource.db` perfectly happily — the schemas are identical
    — and would then serve prose while believing it held code. The stamp is the only thing
    between them, and it only bites if the right class is asked for.
    """
    src = inspect.getsource(serve_mod._Live._open_docsource)
    assert "DocSourceStore(" in src, (
        "the document sidecar is opened as something other than a document sidecar"
    )
    assert "SourceStore(" not in src.replace("DocSourceStore(", ""), (
        "it can be opened as a code sidecar, which the identical schemas would allow"
    )
    assert "writable=False" in src, "rule 20: serving may refuse, it may never repair"
    # **Two callers now, and that is why the open was lifted out of `__init__`.** A
    # program switch repoints the sidecars at another directory, and boot and switch
    # opening them two different ways is how the `try` drifts (rule 51). This guard used
    # to read `__init__` and went blind the moment the code moved — it failed loudly,
    # which is the only reason it was noticed.
    for caller in (serve_mod._Live.__init__, serve_mod._Live.switch_program):
        body = inspect.getsource(caller)
        assert "_open_docsource(" in body and "_open_source(" in body, (
            f"{caller.__name__} opens a sidecar without going through the shared opener"
        )


def test_a_document_sidecar_of_the_wrong_kind_is_refused_not_served(tmp_path: Path) -> None:
    """The guard exercised, because reading the class name off the source is not opening it.

    A `source.db` renamed to `docsource.db` is exactly the accident this catches, and the
    server must end up with no document sidecar rather than with the wrong one.
    """
    out = tmp_path / "prog"
    out.mkdir()
    SourceStore(out / "docsource.db").close()          # the wrong kind, under the right name
    lv = serve_mod._Live(out / "source.db", out)
    try:
        assert lv.docsource is None, (
            "the server opened a source sidecar as the document one — every document would "
            "report as missing, and nothing would say why"
        )
    finally:
        lv.close()


def test_the_two_sidecar_revisions_are_asked_separately() -> None:
    """One rule, two stores, two answers — and they part on `--no-doc-source`.

    `analyze` has both adopt the graph's revision, so they agree on any program analysed in
    one pass. Agreeing today is what rule 51 is about: a version captured without document
    bodies holds none, and reusing the source sidecar's answer would name a revision the
    document store has never heard of.
    """
    src = inspect.getsource(serve_mod._Live.open)
    assert src.count("_sidecar_revision(") == 2, (
        "the two sidecars no longer answer the revision question separately"
    )
    assert "self._sidecar_revision(self.docsource" in src
    params = inspect.signature(serve_mod._Live._sidecar_revision).parameters
    assert "sidecar" in params, (
        "the rule reads `self.source` again — copied to the second caller, it rots at the "
        "first (rule 51)"
    )


def test_a_held_document_store_can_be_read_from_a_request_thread(tmp_path: Path) -> None:
    """The defect this chunk shipped and the server found, which no unit test could see.

    Every test above calls `build_corpus` on the thread that opened the store, and passes.
    `ThreadingHTTPServer` hands each request to its own thread, and sqlite refuses a
    connection made on another one — *by name*, from inside the request, and only for the
    routes that read it. `/api/docs` returned a 000 and a stack trace; `/api/cover` beside
    it was fine, because a graph store has always been opened `shared`.

    It only became possible when the base started **holding** this store. Opened, read and
    closed on one thread, it never needed the flag — which is why nothing was there to
    notice its absence.
    """
    import threading

    out, _tree = _corpus(tmp_path)
    lv = serve_mod._Live(out / "source.db", out)
    lv.open(revisions.db_path(out, revisions.GRAPH, REV))
    failed: list[BaseException] = []

    def read() -> None:
        try:
            with lv.lock:
                got = corpus.build_corpus(lv.current.docs, lv.docsource,
                                          revision=lv.current.docsource_revision)
            assert got["available"] is True and got["total"] == len(CORPUS)
        except BaseException as exc:                          # noqa: BLE001 -- reported
            failed.append(exc)

    t = threading.Thread(target=read)
    t.start()
    t.join()
    lv.close()
    assert not failed, (
        f"a request thread cannot read the held document store: {failed[0]!r}. Every "
        "other store this server holds is opened `shared`."
    )


@pytest.mark.parametrize("field", ["docs", "docsource_revision"])
def test_a_base_carries_what_document_mode_needs(field: str) -> None:
    """Both are facts about *this version*, so both must die with it.

    `docs.db` is per revision and a body is read at a revision. Held anywhere else, a base
    switch would leave this version's headings over the last version's prose — which is
    exactly what rule 70 was written from, one corpus over.
    """
    assert field in serve_mod._Base.__dataclass_fields__, (
        f"`{field}` is not part of the base, so a switch does not replace it"
    )


# --------------------------------------------------------------------------- #
# Chunk 5: which corpora a citation can open
#
# `senseOpens` in the shell was a *provenance* test for as long as `source.db` was
# the only sidecar. It is a *capability* test now, and the capability is a fact
# about this directory and this base -- which only the server knows.
# --------------------------------------------------------------------------- #

def test_the_glossary_says_which_corpora_can_be_opened() -> None:
    """One entry per tier a citation can be read from, each with `opens` and a reason.

    Sent with the terms because it is the answer the page's test *is*. Not folded into
    `bind_glossary`, because the two have different lifetimes: the terms belong to the base
    and are built once, the sidecars belong to the process and to which version the base is
    on -- so a base switched to a version whose bodies were never captured must change this
    without rebuilding a glossary that has not changed.
    """
    route = inspect.getsource(serve_mod._Handler._r_glossary)
    block = inspect.getsource(serve_mod.glossary_sidecars)
    assert '"sidecars"' in route, (
        "the glossary payload states nothing about which sidecars this map has, so the page "
        "has to decide for itself and every documentation citation is a guess"
    )
    # The route sends the block and `glossary_sidecars` builds it -- two places since the
    # MCP server became its second caller, so the guard asks each one for its own half.
    for tier in ("DECLARED_CODE", "DECLARED_DOCS"):
        assert f'"{tier}"' in block, f"{tier} citations have no capability to test"
    # A shallow copy, never a mutation: the base's glossary is built once and served on
    # every request, and writing into it would make one request's answer the next one's.
    assert "**base.glossary" in route, (
        "the cached payload is mutated by the route that serves it"
    )


@pytest.mark.parametrize("bodies,revision,opens", [
    (True, REV, True),      # a sidecar that can serve this version
    (True, None, False),    # a sidecar with nothing for the version on screen (rule 70)
    (False, REV, False),    # no sidecar at all
])
def test_a_sidecars_capability_is_the_stores_own_decision(
        tmp_path: Path, bodies: bool, revision: str | None, opens: bool) -> None:
    """Three states, and `_sidecar_state` reaches all of them through `corpus.serving`.

    Deliberately *not* per path. Whether this corpus can be read at all is what decides
    whether a citation renders a button; a sidecar that holds bodies but not *this* path is
    a fourth state, cannot be known without asking, and is stated by `_span` when the reader
    asks. Pre-empting it would mean a `held_paths` lookup per citation to grey out a button
    that already says what happened when it is pressed.
    """
    out, _ = _corpus(tmp_path, bodies=bodies)
    _, docsource = _open(out, bodies=bodies)
    try:
        state = serve_mod._sidecar_state(docsource, revision,
                                         absent=serve_mod.NO_DOC_SIDECAR)
        assert state["opens"] is opens
        # Never both, and never neither: a refusal with no reason reads as an empty program
        # (design rule 21), and a reason beside `opens: true` is a sentence nothing shows.
        assert (state["reason"] is None) is opens, (
            f"opens={state['opens']} with reason={state['reason']!r}"
        )
    finally:
        if docsource is not None:
            docsource.close()


def test_one_decision_answers_for_both_sidecars() -> None:
    """Rule 51 again, and this is the second reader `corpus.serving` was written for.

    "Can this store serve the version on screen" is one question asked of two stores, and
    only the wording of the refusal is each corpus's own. A second implementation beside
    `serving` would be correct on the day it was written and would then be the thing that
    drifts -- which is how `revision=None` came to mean both "the newest" and "cannot serve
    this version" in the first place.
    """
    body = ast.parse(inspect.getsource(serve_mod._sidecar_state).strip())
    calls = [n for n in ast.walk(body) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "serving"]
    assert len(calls) == 1, (
        "the capability is decided somewhere other than `corpus.serving`, so the page and "
        "the span route can disagree about whether a version has bodies"
    )


def test_each_absence_is_defined_once_and_never_written_out_again() -> None:
    """The sentences are constants because three readers say them.

    `/api/source`, `/api/docsource` and the glossary's capability block. Written out at each
    of those, "there is no sidecar here" would have three spellings, and a reader would be
    told two different things about one program depending on which door they came through.
    The shell must carry none of them either, which is
    `test_the_refusal_names_which_sidecar_and_does_not_paraphrase_it`'s half.
    """
    src = Path(serve_mod.__file__).read_text(encoding="utf-8")
    for name in ("NO_SOURCE_SIDECAR", "NO_DOC_SIDECAR", "SIDECAR_NO_VERSION"):
        sentence = getattr(serve_mod, name)
        assert src.count(f'"{sentence}"') == 1, (
            f"{name}'s sentence is written out as a literal as well as defined, so the two "
            "can be reworded apart (rule 51)"
        )


def test_the_two_sidecars_are_asked_about_their_own_revisions() -> None:
    """`source_revision` for the code corpus and `docsource_revision` for the documents.

    They agree on every program analysed in one pass, which is exactly the kind of
    coincidence rule 51 is about: `--no-doc-source` on one run and not the next parts them,
    and crossing them here would report a documentation citation as openable because the
    *code* sidecar has bodies for this version.
    """
    body = inspect.getsource(serve_mod.glossary_sidecars)
    code = body.split('"DECLARED_CODE"', 1)[1].split('"DECLARED_DOCS"', 1)[0]
    docs = body.split('"DECLARED_DOCS"', 1)[1]
    assert "source_revision" in code and "docsource_revision" not in code, (
        "the code corpus is asked about the document sidecar's revision"
    )
    assert "docsource_revision" in docs, (
        "the document corpus is asked about the source sidecar's revision, so its citations "
        "open at a version whose prose was never captured (rule 70)"
    )


def test_the_client_routes_exactly_the_tiers_the_server_reports() -> None:
    """The two tables are two halves of one contract, and nothing checks them but this.

    `SIDECARS` decides whether a citation offers to open; `VIEWER_ROUTE` decides where its
    bytes come from. A tier in one and not the other is either a button that opens nothing
    (design rule 16) or a route nobody can reach — and both look exactly like working code
    from either end alone.
    """
    shell = (Path(serve_mod.__file__).parent / "static" / "shell.js").read_text(
        encoding="utf-8")
    routed = set(re.findall(r"(\w+): \"/api/\w+\"",
                            shell.split("const VIEWER_ROUTE = {", 1)[1].split("}", 1)[0]))
    reported = set(re.findall(r'"(DECLARED_\w+)": _sidecar_state',
                              inspect.getsource(serve_mod.glossary_sidecars)))
    assert routed == reported, (
        f"the shell routes {sorted(routed)} and the server reports {sorted(reported)}: a "
        "tier in one and not the other is a dead control or an unreachable route"
    )
