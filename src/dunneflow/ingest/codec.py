"""`FileFacts` on the wire, and the three different ways it may refuse.

`schema.py` says what a fact *is*; this says how one crosses a pipe and comes back the
same. It is the whole of what makes a reader on the far side of a process boundary
indistinguishable from one in this interpreter, which is the claim everything from the
TypeScript plugin onward rests on.

**Reflective over `dataclasses.fields()` and `get_type_hints()`, never a table of
hand-written pairs**, for the reason `core_extraction_inputs()`' own docstring gives: a
hand-kept list drifts the moment somebody adds a field. Here the drift is silent in the
worst possible direction — a field that stops travelling is a *fact that stops existing*,
in a map that opens perfectly and reports a smaller program.

**A shape this module has never seen is refused at encode** rather than falling through to
`str()` (rule 49). `schema.py`'s dataclasses use exactly ten field shapes today; adding an
eleventh should fail loudly on the first file rather than arrive at the far end as the
repr of something.

**Decoding is strict, and the failures are four different answers** because they are four
different facts and the thing to do about each differs:

| What arrived | Answer |
|---|---|
| an unknown key | dropped, and **named in `FileFacts.errors`** — a newer plugin may
  know more than this build does, and that is not an error |
| a missing field with no default, or a value of the wrong type | **refuses the record**,
  naming the class, the field, and what came |
| an enum value that is not a member | **refuses the record and quotes it**, listing the
  members. Never coerced and never defaulted |
| a line that is not JSON | not this module's — `worker.py` raises `ProtocolError` once, loudly |

**A refused record refuses its whole file.** Keeping the other thirty-nine routines would
be a map that is quietly smaller, with the reason attached to nothing and nowhere on screen
saying a file was read badly. The host stores it as a failed file carrying the sentence,
which is the same shape a file that will not parse already takes.

**`lang` is refused on a nested record**, and this is stricter than `stamp_lang`'s test on
purpose. `stamp_lang` refuses a *disagreement*, which is right for a reader in this process
that cannot disagree with itself. Over a pipe, a plugin that sends the field at all is
offering a second answer to a question `FileFacts.lang` has already answered, and the two
are only ever noticed when they differ — long after the map was written.
"""

from __future__ import annotations

import dataclasses
import types
import typing
from enum import Enum
from functools import cache
from typing import Any, Literal, Union, get_args, get_origin

from ..schema import DataStructure, Entrypoint, FileFacts, Routine


class CodecError(ValueError):
    """This record cannot be trusted, and the sentence says exactly why.

    Carried up to the file: a record that will not decode fails its file rather than
    quietly leaving it. Separate from `ProtocolError` because that one means the *channel*
    is carrying something else and every fact taken from it is suspect, where this means
    one record was wrong and the rest of the session is fine.
    """


# Fields the **host** owns, which a reader may therefore never send. `lang` travels in
# exactly one place, `FileFacts.lang`, and is written down onto these two by
# `ingest.stamp_lang` after decode (rule 51). Named per class rather than by field name
# alone, because `FileFacts.lang` is required and is the very answer being protected.
_HOST_OWNED: dict[type, frozenset[str]] = {
    Routine: frozenset({"lang"}),
    DataStructure: frozenset({"lang"}),
    # `declared` says a way in was read out of a **manifest**, which happens in this
    # process after extraction (`resolve/manifests`). A reader has not seen a manifest
    # and cannot answer the question, so a reader that sends the field is refused rather
    # than believed -- the same argument `lang` is protected by, one record over.
    Entrypoint: frozenset({"declared", "target_kind"}),
}


class _NoDefault:
    __slots__ = ()

    def __repr__(self) -> str:
        return "<required>"


_NO_DEFAULT = _NoDefault()


@dataclasses.dataclass(frozen=True, slots=True)
class _FieldPlan:
    """One field, with everything the codec needs about it worked out once."""

    name: str
    hint: Any
    default: Any            # `_NO_DEFAULT` where there is none
    factory: Any            # the `default_factory`, or None
    host_owned: bool

    def default_value(self) -> Any:
        """A fresh default. The factory is called per use — a shared `[]` is a bug."""
        return self.factory() if self.factory is not None else self.default


@typing.no_type_check
@cache
def _plan(cls: type) -> tuple[tuple[_FieldPlan, ...], dict[str, _FieldPlan]]:
    """Everything reflection can tell us about one record type, worked out once.

    **Cached, and that was a measurement rather than a habit.** `typing.get_type_hints()`
    resolves and re-evaluates a class's annotations on every call and caches nothing; asked
    once per record it made serialising a file's facts cost **four times what parsing the
    file cost** — 18.3 ms against 4.6 — and 99% of the whole protocol's overhead. The same
    assumption `lang_fingerprint` had to be corrected on, in the same words: an application
    does not become a source checkout halfway through a run, and a dataclass does not grow
    a field between two files.

    The plan is still *derived*. What is cached is the derivation, not a hand-written copy
    of it, so a field added tomorrow is still picked up — on the first record rather than
    on every one.
    """
    hints = typing.get_type_hints(cls)
    host_owned = _HOST_OWNED.get(cls, frozenset())
    for name, hint in hints.items():
        # **Checked here rather than at the first value**, which is a correctness point
        # and not an optimisation. `encode` omits a field left at its default, so a field
        # of a shape this codec cannot carry would pass silently until the day somebody
        # set it — and then fail in whatever run happened to be first. Checking the
        # *declared* type catches it on the first record of the type instead, and the plan
        # is cached so it costs nothing per record.
        _refuse_unsupported(hint, f"{cls.__name__}.{name}")
    plans = tuple(
        _FieldPlan(
            name=f.name,
            hint=hints[f.name],
            default=(f.default if f.default is not dataclasses.MISSING else _NO_DEFAULT),
            factory=(None if f.default_factory is dataclasses.MISSING else f.default_factory),
            host_owned=f.name in host_owned,
        )
        for f in dataclasses.fields(cls)
    )
    return plans, {p.name: p for p in plans}


# The shapes a field may be declared as. `schema.py` uses exactly these, and a new one has
# to be taught here deliberately — the alternative is a field that silently stops meaning
# anything on the far side of the pipe.
_SCALARS = (bool, int, str)


def _refuse_unsupported(hint: Any, where: str) -> None:
    """Can a field of this declared type cross the wire at all? Refuse now if not."""
    origin = get_origin(hint)
    if origin in (Union, types.UnionType):
        arms = [a for a in get_args(hint) if a is not type(None)]
        if len(arms) != 1:
            raise CodecError(
                f"{where} is a union of {len(arms)} types other than None. This codec "
                f"carries `X | None` and refuses to guess which arm a value belongs to."
            )
        _refuse_unsupported(arms[0], where)
        return
    if origin is Literal:
        return
    if origin in (list, tuple, dict):
        for arg in get_args(hint):
            _refuse_unsupported(arg, where)
        return
    if isinstance(hint, type):
        if issubclass(hint, Enum) or hint in _SCALARS or hint is type(None):
            return
        if dataclasses.is_dataclass(hint):
            _plan(hint)         # recursively validated, and cached on the way past
            return
    raise CodecError(
        f"{where} is declared as {_name_of(hint)}, which this codec has never been taught "
        f"to send. A field of a new shape must fail here rather than arrive at the far end "
        f"as the repr of something."
    )


# --------------------------------------------------------------------------- #
# Encode
# --------------------------------------------------------------------------- #

def encode(obj: Any) -> dict[str, Any]:
    """One dataclass as a JSON-ready dict, omitting every field left at its default.

    The omission is not a micro-optimisation: Comitia yields 43,926 `CallArg`s, and each
    one carrying `"splat": false` and `"keyword": null` is most of the payload. It is also
    what makes the wire readable when somebody has to look at it.
    """
    if not dataclasses.is_dataclass(obj) or isinstance(obj, type):
        raise CodecError(f"{obj!r} is not a fact record and cannot be encoded.")
    cls = type(obj)
    plans, _ = _plan(cls)
    out: dict[str, Any] = {}
    for f in plans:
        if f.host_owned:
            # Never sent, so a reader on the far side cannot learn to send it by watching
            # what the host does. The host writes it after decode.
            continue
        value = getattr(obj, f.name)
        if value == f.default_value():
            continue
        out[f.name] = _encode_value(value, f.hint, f"{cls.__name__}.{f.name}")
    return out


def _encode_value(value: Any, hint: Any, where: str) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool | int | str) or value is None:
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return encode(value)
    if isinstance(value, list | tuple):
        inner = get_args(hint)
        item_hint = inner[0] if inner else Any
        if get_origin(hint) is tuple and len(inner) > 1:
            return [_encode_value(v, h, where) for v, h in zip(value, inner, strict=False)]
        return [_encode_value(v, item_hint, where) for v in value]
    if isinstance(value, dict):
        inner = get_args(hint)
        v_hint = inner[1] if len(inner) > 1 else Any
        return {str(k): _encode_value(v, v_hint, where) for k, v in value.items()}
    raise CodecError(
        f"{where} holds {type(value).__name__}, which this codec has never been taught to "
        f"send. Adding a field of a new shape must fail here rather than arrive at the far "
        f"end as the repr of something."
    )


# --------------------------------------------------------------------------- #
# Decode
# --------------------------------------------------------------------------- #

def decode[T](cls: type[T], data: Any, notes: list[str] | None = None,
              where: str = "") -> T:
    """One dict back into a record of `cls`, strictly.

    `notes` collects the things that were survivable — unknown keys, and nothing else —
    so the caller can attach them to `FileFacts.errors`. Passing `None` means the caller
    does not want them, which is only ever a test.
    """
    where = where or cls.__name__
    if not isinstance(data, dict):
        raise CodecError(
            f"{where} arrived as {type(data).__name__} and a record has to be an object."
        )
    plans, by_name = _plan(cls)

    for key in data:
        if (known := by_name.get(key)) is not None and known.host_owned:
            raise CodecError(
                f"{where} carries {key!r}, which is the host's to write and never a "
                f"reader's to send. The language travels in one place, on the file, and a "
                f"record that brings its own is a second answer to one question."
            )
        # Survivable, and deliberately so: a plugin built against a later schema knows
        # about fields this build does not. Dropped, and **said out loud** (design rule 1)
        # rather than absorbed.
        if known is None and notes is not None:
            notes.append(f"{where}: unknown field {key!r} was dropped")

    kwargs: dict[str, Any] = {}
    for f in plans:
        if f.host_owned:
            continue
        if f.name not in data:
            if f.default is _NO_DEFAULT and f.factory is None:
                raise CodecError(
                    f"{where} is missing {f.name!r}, which has no default. A record "
                    f"without it is not this fact with a gap in it, it is a different fact."
                )
            continue
        kwargs[f.name] = _decode_value(data[f.name], f.hint, f"{where}.{f.name}", notes)
    return cls(**kwargs)


def _decode_value(value: Any, hint: Any, where: str, notes: list[str] | None) -> Any:
    origin = get_origin(hint)

    # `X | None`, and nothing else: `schema.py` has no other union, and admitting one
    # would mean guessing which arm a value belongs to (rule 49).
    if origin in (Union, types.UnionType):
        arms = [a for a in get_args(hint) if a is not type(None)]
        if value is None:
            return None
        if len(arms) != 1:
            raise CodecError(
                f"{where} is declared as a union of {len(arms)} types other than None. "
                f"This codec decodes `X | None` and refuses to guess which arm a value "
                f"belongs to."
            )
        return _decode_value(value, arms[0], where, notes)

    if origin is Literal:
        allowed = get_args(hint)
        if value not in allowed:
            raise CodecError(
                f"{where} came as {value!r}, and the only values it may take are "
                f"{', '.join(repr(a) for a in allowed)}."
            )
        return value

    if isinstance(hint, type) and issubclass(hint, Enum):
        try:
            return hint(value)
        except ValueError:
            members = ", ".join(str(m.value) for m in hint)
            raise CodecError(
                f"{where} came as {value!r}, which is not a {hint.__name__}. The members "
                f"are: {members}. A value outside them is never coerced and never "
                f"defaulted — a fact about a kind nobody defined is not a fact."
            ) from None

    if hint is bool:
        # Before `int`, because `bool` is a subclass of it and `True` would otherwise
        # satisfy an `int` field and `1` a `bool` one.
        if not isinstance(value, bool):
            raise CodecError(_wrong(where, "a boolean", value))
        return value
    if hint is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise CodecError(_wrong(where, "a whole number", value))
        return value
    if hint is str:
        if not isinstance(value, str):
            raise CodecError(_wrong(where, "text", value))
        return value

    if origin in (list, tuple):
        if not isinstance(value, list):
            raise CodecError(_wrong(where, "a list", value))
        args = get_args(hint)
        if origin is tuple:
            if len(args) != len(value):
                raise CodecError(
                    f"{where} came with {len(value)} item(s) and is declared as a "
                    f"{len(args)}-tuple. A short tuple is not this fact with a gap in it."
                )
            return tuple(
                _decode_value(v, h, f"{where}[{i}]", notes)
                for i, (v, h) in enumerate(zip(value, args, strict=True))
            )
        item = args[0] if args else Any
        return [_decode_value(v, item, f"{where}[{i}]", notes)
                for i, v in enumerate(value)]

    if origin is dict:
        if not isinstance(value, dict):
            raise CodecError(_wrong(where, "an object", value))
        args = get_args(hint)
        v_hint = args[1] if len(args) > 1 else Any
        return {str(k): _decode_value(v, v_hint, f"{where}[{k!r}]", notes)
                for k, v in value.items()}

    if dataclasses.is_dataclass(hint) and isinstance(hint, type):
        return decode(hint, value, notes, where)

    raise CodecError(
        f"{where} is declared as {hint!r}, which this codec has never been taught to read."
    )


def _wrong(where: str, wanted: str, got: Any) -> str:
    return (
        f"{where} has to be {wanted} and came as {type(got).__name__} ({got!r}). It is "
        f"refused rather than converted: a reader that sends the wrong shape is a reader "
        f"whose other answers are worth doubting."
    )


# --------------------------------------------------------------------------- #
# The one shape the host actually sends and receives
# --------------------------------------------------------------------------- #

def encode_facts(facts: FileFacts) -> dict[str, Any]:
    """One file's facts, ready for `json.dumps`."""
    return encode(facts)


def decode_facts(data: Any) -> FileFacts:
    """One file's facts, with every survivable complaint appended to `errors`.

    The notes go on the **end** of `errors`, after whatever the reader itself reported,
    because the reader's own sentence is the one that says why a file failed to parse and
    a note about a dropped field must not push it out of the way.
    """
    notes: list[str] = []
    facts = decode(FileFacts, data, notes, "FileFacts")
    facts.errors.extend(notes)
    return facts


def describe() -> dict[str, Any]:
    """Every fact type this build speaks, as data — what `dunneflow ingest-schema` prints.

    **Out of the same reflection the codec uses**, so the descriptor a plugin generates its
    types from and the wire it then talks cannot describe two different shapes (rule 13). A
    second hand-written description of `schema.py` would be exactly the drift this module
    exists to avoid, one file over.
    """
    from .. import schema as schema_mod

    records: dict[str, Any] = {}
    enums: dict[str, list[str]] = {}
    for name in sorted(dir(schema_mod)):
        obj = getattr(schema_mod, name)
        if isinstance(obj, type) and issubclass(obj, Enum) and obj is not Enum:
            enums[name] = [str(m.value) for m in obj]
        elif dataclasses.is_dataclass(obj) and isinstance(obj, type):
            plans, _ = _plan(obj)
            records[name] = [
                {
                    "name": f.name,
                    "type": _name_of(f.hint),
                    "required": f.default is _NO_DEFAULT and f.factory is None,
                    "default": _json_default(f.default_value()),
                    "host_owned": f.host_owned,
                }
                for f in plans
            ]
    return {
        "schema_version": schema_mod.SCHEMA_VERSION,
        "doc_schema_version": schema_mod.DOC_SCHEMA_VERSION,
        "enums": enums,
        "records": records,
    }


def _name_of(hint: Any) -> str:
    """A type as a plugin's build script can read it, not as Python reprs it."""
    origin = get_origin(hint)
    if origin in (Union, types.UnionType):
        return " | ".join(_name_of(a) for a in get_args(hint))
    if origin is Literal:
        return "Literal[" + ", ".join(repr(a) for a in get_args(hint)) + "]"
    if origin is not None:
        inner = ", ".join(_name_of(a) for a in get_args(hint))
        return f"{origin.__name__}[{inner}]" if inner else origin.__name__
    if hint is type(None):
        return "None"
    return getattr(hint, "__name__", str(hint))


def _json_default(value: Any) -> Any:
    if value is _NO_DEFAULT:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool | int | str) or value is None:
        return value
    if isinstance(value, list | tuple):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return str(value)
