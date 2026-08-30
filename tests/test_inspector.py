"""The inspector's backend: reading an id, and answering honestly when there is nothing."""

from __future__ import annotations

from pathlib import Path

from dunneflow.schema import hash_source
from dunneflow.sourcedb import SourceStore
from dunneflow.store import Store
from dunneflow.web.detail import classify, describe

# ----------------------------------------------------------------- id parsing --- #

def test_a_constant_id_splits_at_the_last_dot() -> None:
    """A module path holds dots and an identifier does not, so no other split is right.

    `const:mensores.disceptator._prompts.JTBD_OPENERS` is one module and one name, and
    splitting anywhere else looks up a constant that does not exist -- which the store
    answers with "no such node" rather than with an error, so getting this wrong would be
    invisible.
    """
    kind, params = classify("const:mensores.disceptator._prompts.JTBD_OPENERS")
    assert kind == "CONSTANT"
    assert params == {"module": "mensores.disceptator._prompts", "name": "JTBD_OPENERS"}


def test_a_boundary_target_may_hold_colons() -> None:
    """A URL or a host:port is a legitimate target. Eating its colons finds nothing."""
    kind, params = classify("bnd:NETWORK:https://example.test:8443/v1")
    assert kind == "BOUNDARY"
    assert params == {"kind": "NETWORK", "target": "https://example.test:8443/v1"}


def test_an_unnamed_boundary_keeps_its_empty_target() -> None:
    """Boundary touches with no named target still happened; they are one node per kind."""
    kind, params = classify("bnd:FILE:")
    assert kind == "BOUNDARY"
    assert params == {"kind": "FILE", "target": ""}


def test_an_artefact_name_may_hold_dots() -> None:
    kind, params = classify("art:tabularium.db")
    assert kind == "ARTEFACT"
    assert params == {"name": "tabularium.db"}


def test_an_unprefixed_id_is_left_opaque() -> None:
    """Routines and structures carry hashes and are told apart by looking, not by parsing."""
    kind, params = classify("9a473a44db0a0256")
    assert kind == "OPAQUE"
    assert params == {"id": "9a473a44db0a0256"}


# -------------------------------------------------------------------- routines --- #

def _a_routine(store: Store, name: str) -> str:
    row = store.query("SELECT id FROM routines WHERE name = ?", (name,))[0]
    return str(row["id"])


def test_a_routine_answers_in_out_touches_and_why(analyzed: Store) -> None:
    """The four sections, in the order the inspector reads them."""
    d = describe(analyzed, _a_routine(analyzed, "load_config"))
    assert d["found"] is True
    assert d["kind"] == "ROUTINE"
    assert d["label"] == "load_config"
    # IN, OUT, TOUCHES, GOVERNANCE all present as shapes even when a list is empty --
    # an absent key and an empty list are different claims to anything reading this.
    assert set(d["in"]) == {"callers", "entrypoints"}
    assert "calls" in d["out"]
    assert set(d["touches"]) == {"boundaries", "sql", "net", "artefacts"}
    assert set(d["governance"]) == {"annotations", "comments"}
    # It reads an environment variable and a file; both are boundary touches.
    assert {b["kind"] for b in d["touches"]["boundaries"]} >= {"ENV"}


def test_a_routine_carries_the_comment_that_says_why(analyzed: Store) -> None:
    """The WHY is the point. A comment reaches the inspector or it reaches nobody."""
    d = describe(analyzed, _a_routine(analyzed, "load_config"))
    texts = " ".join(c["text"] for c in d["governance"]["comments"])
    assert "fails closed" in texts


def test_confidence_is_carried_not_flattened(analyzed: Store) -> None:
    """Rule 6: CERTAIN and INFERRED are never blurred, so both must survive the trip.

    The client draws the difference as shape rather than colour, which it cannot do with
    a value the server decided not to send.
    """
    d = describe(analyzed, _a_routine(analyzed, "main"))
    assert d["out"]["calls"], "main calls something"
    assert all("confidence" in c for c in d["out"]["calls"])


def test_a_missing_node_says_so_rather_than_looking_empty(analyzed: Store) -> None:
    """`found: False` and "a routine with no callers" must never render the same.

    An empty shape is indistinguishable on screen from a real thing nothing calls, and
    one of those two means the map is wrong.
    """
    d = describe(analyzed, "no-such-id-at-all")
    assert d["found"] is False
    assert "no such node" in d["reason"]


# ---------------------------------------------------------------------- source --- #

def test_source_is_absent_with_a_reason_when_there_is_no_sidecar(analyzed: Store) -> None:
    """Three different absences, and the reader must be able to tell which one this is."""
    d = describe(analyzed, _a_routine(analyzed, "load_config"), None)
    assert d["source"]["available"] is False
    assert "no source sidecar" in d["source"]["reason"]


def test_source_opens_on_the_definition_when_the_sidecar_holds_it(
    analyzed: Store, sample_tree: Path, tmp_path: Path,
) -> None:
    """Design rule 13: provenance must open, with the thing itself in its own context."""
    rid = _a_routine(analyzed, "load_config")
    row = analyzed.query(
        "SELECT file, line_start, line_end FROM routines WHERE id = ?", (rid,)
    )[0]
    # `routines.file` is relative to the analysed tree, as every stored path is. Joining
    # the tree back on is what reading a body from disk costs, and nothing but a test
    # fixture and `analyze` itself ever has to do it.
    body = (sample_tree / str(row["file"])).read_text(encoding="utf-8")

    src = SourceStore(tmp_path / "source.db")
    src.add_blob(body, hash_source(body))
    src.map_path(row["file"], hash_source(body), lang="python")
    src.commit()

    d = describe(analyzed, rid, src)
    assert d["source"]["available"] is True
    assert d["source"]["focus"] == [row["line_start"], row["line_end"]]
    # The span reaches past the definition on both sides: a routine shown with no
    # surroundings is a routine you have to find twice.
    assert d["source"]["first"] < row["line_start"]
    text = "\n".join(line["text"] for line in d["source"]["lines"])
    assert "def load_config" in text


def test_an_external_says_nothing_was_read_rather_than_no_source(analyzed: Store) -> None:
    """A boundary has no file by definition, and that is not a missing sidecar."""
    d = describe(analyzed, "bnd:ENV:API_TOKEN")
    assert d["kind"] == "BOUNDARY"
    assert d["identity"]["source_status"] == "OPAQUE"
    assert d["source"]["available"] is False
    assert "outside the program" in d["source"]["reason"]
