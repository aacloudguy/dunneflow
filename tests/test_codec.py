"""Facts across a pipe, and every way that can go wrong.

The round trip over real source is the gate and it lives in `test_wire.py` with the rest
of the out-of-process proof. What is here is the codec on its own: what it omits, what it
refuses, and — the one that matters most — that it refuses a *shape* it has never seen
rather than sending the repr of something.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from dunneflow.ingest.codec import (
    CodecError,
    decode,
    decode_facts,
    describe,
    encode,
    encode_facts,
)
from dunneflow.schema import (
    SCHEMA_VERSION,
    BoundaryHit,
    BoundaryKind,
    CallArg,
    CallSite,
    DataStructure,
    Direction,
    FileFacts,
    Param,
    Routine,
    StructureKind,
    TableSchema,
)


def _routine(**kw: object) -> Routine:
    base = dict(id="m:f", name="f", qualname="f", module="m", file="m.py",
                line_start=1, line_end=2)
    base.update(kw)
    return Routine(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------ omission --- #

def test_a_field_left_at_its_default_is_not_sent():
    """43,926 `CallArg`s each carrying `"splat": false` is most of the payload."""
    blob = encode(CallArg(idx=0, expr="x"))
    assert blob == {"idx": 0, "expr": "x"}
    assert "splat" not in blob
    assert "keyword" not in blob


def test_an_omitted_field_comes_back_as_its_default():
    assert decode(CallArg, {"idx": 0, "expr": "x"}) == CallArg(idx=0, expr="x")


def test_a_default_factory_is_called_per_record_and_never_shared():
    """A list default handed out by reference is two records writing to one list."""
    a = decode(Routine, {"id": "m:f", "name": "f", "qualname": "f", "module": "m",
                         "file": "m.py", "line_start": 1, "line_end": 2})
    b = decode(Routine, {"id": "m:g", "name": "g", "qualname": "g", "module": "m",
                         "file": "m.py", "line_start": 3, "line_end": 4})
    a.params.append(Param(name="x"))
    assert b.params == []


# ------------------------------------------------------------------ the ten --- #

@pytest.mark.parametrize("value", [
    CallArg(idx=1, expr="x", keyword="k", splat=True),                  # str|None, bool
    Param(name="p", type="int", default="3", kind="keyword"),           # Literal
    BoundaryHit(routine_id="r", kind=BoundaryKind.FILE,                 # two enums
                direction=Direction.IN, target="t", line=4),
    TableSchema(name="t", columns=[("a", "TEXT", "")],                  # list[tuple[...]]
                file="f.py", line=1),
    DataStructure(id="d", name="D", kind=StructureKind.DATACLASS,
                  module="m", file="m.py", line=1),
    CallSite(caller_id="c", callee_expr="a.b", line=1,                  # nested records
             args=[CallArg(idx=0, expr="1")]),
])
def test_every_field_shape_in_the_schema_survives_a_round_trip(value):
    """The ten shapes `schema.py` actually uses, each named by an instance that has it."""
    back = decode(type(value), json.loads(json.dumps(encode(value))))
    assert back == value


def test_the_whole_of_file_facts_round_trips():
    facts = FileFacts(
        path="a/b.py", lang="python", module="a.b", content_hash="deadbeef",
        doc="what this module is",
        routines=[_routine(comments=[], decorators=["app.get"], is_async=True)],
        calls=[CallSite(caller_id="m:f", callee_expr="x.y", line=3, site_id="s")],
        errors=["something the reader wanted to say"],
    )
    assert decode_facts(json.loads(json.dumps(encode_facts(facts)))) == facts


# ------------------------------------------------------------------ refusals --- #

def test_an_unknown_key_is_dropped_and_named_in_errors():
    """A plugin built against a later schema knows more than this build, and that is
    survivable — but design rule 1 says no filter is silent."""
    blob = encode_facts(FileFacts(path="a.py", lang="python", module="a",
                                  content_hash="h", routines=[_routine()]))
    blob["routines"][0]["invented_by_a_newer_plugin"] = True
    facts = decode_facts(blob)
    assert len(facts.routines) == 1
    assert any("invented_by_a_newer_plugin" in e and "dropped" in e
               for e in facts.errors), facts.errors


def test_a_bad_enum_value_refuses_the_record_and_quotes_it():
    with pytest.raises(CodecError) as exc:
        decode(BoundaryHit, {"routine_id": "r", "kind": "BROWSER",
                             "direction": "IN", "target": "t", "line": 1})
    said = str(exc.value)
    assert "'BROWSER'" in said
    assert "FILE" in said and "NETWORK" in said     # the members, so it can be corrected


def test_a_missing_required_field_refuses_the_record():
    with pytest.raises(CodecError, match="missing 'line_end'"):
        decode(Routine, {"id": "m:f", "name": "f", "qualname": "f", "module": "m",
                         "file": "m.py", "line_start": 1})


def test_a_wrong_type_is_refused_rather_than_converted():
    """`"7"` is not `7`. A reader that sends the wrong shape is one whose other answers
    are worth doubting, so nothing here coerces (rule 49)."""
    with pytest.raises(CodecError, match="whole number"):
        decode(CallArg, {"idx": "0", "expr": "x"})


def test_a_boolean_is_not_a_number_and_a_number_is_not_a_boolean():
    """`bool` is a subclass of `int`, so the naive order silently accepts both."""
    with pytest.raises(CodecError):
        decode(CallArg, {"idx": True, "expr": "x"})
    with pytest.raises(CodecError):
        decode(CallArg, {"idx": 0, "expr": "x", "splat": 1})


def test_a_value_outside_a_literal_is_refused():
    with pytest.raises(CodecError, match="'positional'"):
        decode(Param, {"name": "p", "kind": "sideways"})


def test_a_short_tuple_is_refused():
    with pytest.raises(CodecError, match="2-tuple|3-tuple|item"):
        decode(TableSchema, {"name": "t", "columns": [["a", "TEXT"]],
                             "file": "f.py", "line": 1})


def test_a_shape_the_codec_has_never_seen_is_refused_at_encode():
    """The defence that matters most: adding a field of a new kind must fail on the first
    record rather than arrive at the far end as the repr of something.

    **Refused on the declared type, not on a value**, and the difference was found by this
    test: `encode` omits a field left at its default, so a `complex` field that nobody had
    set yet sailed straight through. It would have failed on the day somebody set it, in
    whichever run happened to be first.
    """

    @dataclasses.dataclass
    class Odd:
        when: complex = 1 + 2j

    with pytest.raises(CodecError, match="never been taught to send"):
        encode(Odd())                   # at its default, and still refused


def test_a_union_of_two_real_types_is_refused_rather_than_guessed():
    """Which arm does `3` belong to? Guessing is how a fact changes type in transit."""

    @dataclasses.dataclass
    class Ambiguous:
        either: int | str = 0

    with pytest.raises(CodecError, match="refuses to guess"):
        encode(Ambiguous())


def test_an_unsupported_shape_nested_in_a_list_is_refused_too():
    """A defence that only looks at the top level is not a defence (rule 92's shape)."""

    @dataclasses.dataclass
    class Nested:
        many: list[complex] = dataclasses.field(default_factory=list)

    with pytest.raises(CodecError, match="never been taught to send"):
        encode(Nested())


def test_a_reader_may_not_send_the_language_on_a_nested_record():
    """`lang` is the host's to write. A record that brings its own is a second answer to a
    question `FileFacts.lang` has already answered, and the two are only ever noticed when
    they differ — long after the map was written."""
    for cls, blob in (
        (Routine, {"id": "m:f", "name": "f", "qualname": "f", "module": "m",
                   "file": "m.py", "line_start": 1, "line_end": 2, "lang": "python"}),
        (DataStructure, {"id": "d", "name": "D", "kind": "DATACLASS", "module": "m",
                         "file": "m.py", "line": 1, "lang": "python"}),
    ):
        with pytest.raises(CodecError, match="host's to write"):
            decode(cls, blob)


def test_the_host_owned_field_is_never_encoded_either():
    """So a plugin author cannot learn to send it by watching what the host does."""
    assert "lang" not in encode(_routine(lang="python"))


def test_a_record_that_is_not_an_object_is_refused():
    with pytest.raises(CodecError, match="has to be an object"):
        decode(CallArg, [0, "x"])


# ----------------------------------------------------------------- describe --- #

def test_the_descriptor_is_the_same_reflection_the_wire_uses():
    """A second, hand-written description of `schema.py` would be exactly the drift the
    codec was made reflective to avoid (rule 13)."""
    shape = describe()
    assert shape["schema_version"] == SCHEMA_VERSION
    names = {f["name"] for f in shape["records"]["CallArg"]}
    assert names == {f.name for f in dataclasses.fields(CallArg)}
    assert shape["enums"]["Direction"] == [d.value for d in Direction]


def test_the_descriptor_marks_the_fields_a_reader_must_not_send():
    """The one thing a plugin author will otherwise get wrong."""
    owned = {r: [f["name"] for f in fs if f["host_owned"]]
             for r, fs in describe()["records"].items()}
    assert owned["Routine"] == ["lang"]
    assert owned["DataStructure"] == ["lang"]
    assert owned["FileFacts"] == []          # the file's own answer, and required


def test_the_descriptor_is_json():
    json.dumps(describe())
