"""What it costs to start an async call and drop the result, per language.

**A detector with no test, wrong for a year, in the command that gates CI.**
`ASYNC_NOT_AWAITED` said *"The coroutine is created and never run"* at **BROKEN** of every
language. That is exactly true of Python — `f()` on an `async def` builds a coroutine and
nothing runs until something awaits it — and false of JavaScript, where the promise runs
whether or not anybody holds it.

Put to `gstack-main`, a TypeScript tree no chunk had read, it produced **two BROKEN**
findings and `dunneflow check` exits non-zero only on BROKEN. Both were wrong:

* `browse/src/terminal-agent.ts:493` sits three lines under the comment *"No await; this is
  fire-and-forget"* and ends in `.catch(() => {})` — the rejection handled explicitly.
* `browse/src/cookie-import-browser.ts:933` is `new WebSocket(wsUrl)`, which
  `detectors/typescript.yaml` declared `async: true`. It is a **constructor**: the bundled
  `lib.dom.d.ts` says `new(url: string | URL, protocols?: string | string[]): WebSocket`.
  Nothing there returns a promise, so *never awaited* was trivially true and meaningless.

Rule 98 twice over in one finding — a judgement unchanged for a year handed a population it
had never been shown, and a data file asserting something about a language that was not so.

**The language declares what it costs and `anomalies.py` names none of them**
(`unawaited_async` in each reader's rules file), so a third language answers for itself on
the day it is registered rather than inheriting Python's answer in silence.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dunneflow import ingest
from dunneflow.anomalies import _ASYNC_COST, BROKEN, SUSPECT, detect
from dunneflow.detectors import RulesMissing, load_rules
from dunneflow.store import Store
from dunneflow.walk import analyze_tree

LANG = "typescript"
PLUGIN = ingest.PLUGINS.get(LANG)
HAS_TS = PLUGIN is not None and shutil.which("node") is not None

PY_FIRE_AND_FORGET = '''\
"""A coroutine created and dropped, which in Python is work that never happens."""
import aiohttp


async def sync_the_ledger(url: str) -> None:
    aiohttp.request("POST", url)
'''

TS_FIRE_AND_FORGET = """\
export function syncTheLedger(url: string): void {
  fetch(url, { method: 'POST' }).catch(() => {});
}
"""

TS_WEBSOCKET = """\
export function openTheChannel(url: string): WebSocket {
  const ws = new WebSocket(url);
  return ws;
}
"""


def _findings(root: Path, name: str, body: str) -> list:
    root.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(body, encoding="utf-8")
    store = Store(root / "g.db")
    try:
        analyze_tree(root, store)
        return [a for a in detect(store).items if a.kind == "ASYNC_NOT_AWAITED"]
    finally:
        store.close()


# -- what each language says ---------------------------------------------------- #


def test_a_dropped_coroutine_is_broken_and_says_why(tmp_path):
    """Python's answer, which was always right and is the one that must not move.

    An un-awaited coroutine is work that does not happen, which is BROKEN's own
    definition: the program cannot be correct as written.
    """
    found = _findings(tmp_path, "sync.py", PY_FIRE_AND_FORGET)
    assert len(found) == 1, [a.title for a in found]
    assert found[0].severity == BROKEN
    assert "never run" in found[0].detail, found[0].detail


@pytest.mark.skipif(not HAS_TS, reason="needs the TypeScript reader and node")
def test_a_dropped_promise_is_not_broken_because_the_work_happens(tmp_path):
    """The defect, stated as the thing it got wrong.

    `dunneflow check` exits non-zero only on BROKEN, so this is not a wording quibble — it
    is whether a CI job fails over code that is fine.
    """
    found = _findings(tmp_path, "sync.ts", TS_FIRE_AND_FORGET)
    assert len(found) == 1, [a.title for a in found]
    assert found[0].severity == SUSPECT, "a running promise was reported as broken work"


@pytest.mark.skipif(not HAS_TS, reason="needs the TypeScript reader and node")
def test_a_promise_is_never_described_as_a_coroutine(tmp_path):
    """Rule 24, in a sentence: the finding has to describe the language it is about.

    *"The coroutine is created and never run"* is not a softer way of saying what happens
    in JavaScript. It is false — the request is made — and it sends a reader looking for a
    call that did not happen when what they have is one whose result nobody waited for.
    """
    found = _findings(tmp_path, "sync.ts", TS_FIRE_AND_FORGET)
    said = found[0].detail + " " + found[0].blind_spot
    assert "coroutine" not in said.lower(), said
    assert "asyncio" not in said.lower(), said
    assert "async with" not in said.lower(), said
    assert "promise" in said.lower(), said


@pytest.mark.skipif(not HAS_TS, reason="needs the TypeScript reader and node")
def test_the_blind_spot_names_the_thing_that_makes_it_a_false_alarm(tmp_path):
    """The anomaly discipline's one rule: every finding states what would make it wrong.

    The instance this was found on ends in `.catch(() => {})`, which handles the very
    rejection the finding warns about — and this check cannot see it.
    """
    found = _findings(tmp_path, "sync.ts", TS_FIRE_AND_FORGET)
    assert "catch" in found[0].blind_spot.lower(), found[0].blind_spot
    assert "fire-and-forget" in found[0].blind_spot.lower(), found[0].blind_spot


# -- the constructor that was declared async ------------------------------------ #


@pytest.mark.skipif(not HAS_TS, reason="needs the TypeScript reader and node")
def test_a_constructor_is_not_an_async_call(tmp_path):
    """`new WebSocket(u)` returns a WebSocket, not a promise, so it cannot be awaited.

    Reported as BROKEN *"never awaited"* until 2026-09-18, on a line where awaiting would
    be meaningless. It is still a NETWORK boundary — the defect was the `async` flag beside
    it, not the row.
    """
    found = _findings(tmp_path, "chan.ts", TS_WEBSOCKET)
    assert found == [], [a.title for a in found]


@pytest.mark.parametrize("name", ["WebSocket", "EventSource"])
def test_the_rules_do_not_call_a_constructor_asynchronous(name):
    """Asserted against the declaration rather than the finding, so the data cannot drift
    back while a test of the *detector* keeps passing (rule 13)."""
    profile = load_rules(LANG).network_profile(name)
    assert profile is not None, f"{name} stopped being a network library"
    _protocol, is_async = profile
    assert is_async is False, f"{name} is declared async, and it is a constructor"


# -- the declaration itself ----------------------------------------------------- #


def test_both_readers_have_answered_the_question():
    """Two languages, two different answers — which is the whole reason it is declared."""
    assert load_rules("python").unawaited_async == "inert"
    assert load_rules(LANG).unawaited_async == "runs"
    assert _ASYNC_COST["inert"].severity == BROKEN
    assert _ASYNC_COST["runs"].severity == SUSPECT


def test_a_language_that_has_not_answered_gets_no_finding_made_for_it():
    """Rule 49: a severity is a claim, and this one is read by the command CI trusts.

    Empty is a legitimate answer meaning *nobody has decided*, and the detector skips
    rather than reaching for whichever answer happens to be first in the table.
    """
    assert "" not in _ASYNC_COST
    assert _ASYNC_COST.get("") is None


def test_a_word_the_table_does_not_know_is_refused_rather_than_defaulted(tmp_path):
    """A misspelling would otherwise arrive as a severity nobody chose.

    `RulesMissing` is the class, because a rules file saying something this build cannot
    read is a build or an edit that has to be fixed, never worked around in place — and
    `_ASYNC_COST.get` would turn `inret` into silence, which is the same finding
    disappearing rather than the same finding being wrong (rule 49).
    """
    from dunneflow.detectors import _unawaited_async

    for bad in ("inret", "true", "BROKEN", 1, ["inert"]):
        with pytest.raises(RulesMissing) as caught:
            _unawaited_async(bad, "madeup", tmp_path / "madeup.yaml")
        said = str(caught.value)
        assert "unawaited_async" in said, said
        assert "inert" in said and "runs" in said, said

    # And the two that are answers, plus the absence that is also one.
    assert _unawaited_async("inert", "x", tmp_path) == "inert"
    assert _unawaited_async("runs", "x", tmp_path) == "runs"
    assert _unawaited_async("", "x", tmp_path) == ""
    assert _unawaited_async(None, "x", tmp_path) == ""
