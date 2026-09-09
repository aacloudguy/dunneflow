"""Nothing open is a state, and it is the state a packaged DunneFlow starts in.

`serve` used to raise *"no graph in … — run `dunneflow analyze` first"* and stop. A
double-clicked application has neither an argument nor, on a fresh machine, a map, so that
refusal is the difference between an application that opens and one that does not.

The tests here go **over a real socket** for one reason: the first spelling of the refusal
put its sentence in `send_error`'s message argument, which is the HTTP status line, which
`http.server` encodes as latin-1. The em dash this project writes everywhere raised
`UnicodeEncodeError` from inside the error handler and the socket closed with nothing on it
at all — a refusal that could not be delivered, which is worse than the confident empty
answer the gate exists to prevent. Nothing that calls a handler directly can see that.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from dunneflow import revisions
from dunneflow.extractors.python.extract import extract_file
from dunneflow.store import Store
from dunneflow.web.serve import _Handler, _Live, where

STATIC = Path(__file__).resolve().parents[1] / "src" / "dunneflow" / "web" / "static"

ONE = '''\
"""A program small enough to analyse in a test and real enough to open."""
import sqlite3


def open_it(path):
    """Open the database."""
    return sqlite3.connect(path)


def use_it(path):
    return open_it(path)
'''


def _make_program(root: Path, name: str) -> Path:
    """A program directory with a graph that really opens.

    Written through `Store` and the real extractor rather than by touching a file: the
    point of these tests is that a base can be built from cold, and an empty file of the
    right name proves only that the *listing* works.
    """
    out = root / name
    out.mkdir(parents=True)
    src = root / f"{name}_src"
    src.mkdir()
    (src / "one.py").write_text(ONE)
    revision = "2026-01-01T00:00:00Z"
    store = Store(revisions.db_path(out, revisions.GRAPH, revision))
    store.write_file_facts(extract_file(src / "one.py", src))
    store.set_meta("revision", revision)
    store.conn.commit()
    store.close()
    return out


@pytest.fixture
def cold(tmp_path):
    """A server on an output root, with nothing open. Yields its base URL."""
    root = tmp_path / "maps"
    root.mkdir()
    _make_program(root, "alpha")
    _make_program(root, "beta")

    out_dir, out_root = where(root)
    live = _Live(out_dir / "source.db", out_dir, out_root)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Handler, live=live))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", live, root
    finally:
        httpd.shutdown()
        httpd.server_close()
        live.close()


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:      # noqa: S310 -- localhost
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _post(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:      # noqa: S310 -- localhost
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


# --------------------------------------------------------------------------- #
# The page


def test_the_root_serves_the_start_page_and_not_the_shell(cold):
    base, _live, _root = cold
    status, body = _get(base + "/")
    assert status == 200
    # On the `<script>` tags, never on the text: `start.html`'s own comment explains why the
    # dialog came out of `shell.js`, and a substring search reads that as a script tag. Rule
    # 34's shape — the thing being looked for hiding in the prose about it, for the third
    # time this session.
    assert '<script src="/static/start.js"></script>' in body
    assert '<script src="/static/shell.js"></script>' not in body


def test_the_start_page_exists_and_loads_the_shared_dialog(cold):
    """`analyze.js` is the shell's file, and the start page is why it left `shell.js`."""
    base, _live, _root = cold
    _, body = _get(base + "/")
    assert '<script src="/static/analyze.js"></script>' in body
    assert (STATIC / "analyze.js").is_file()
    for asset in ("start.js", "analyze.js", "tokens.css"):
        status, _ = _get(f"{base}/static/{asset}")
        assert status == 200, asset


# --------------------------------------------------------------------------- #
# What can and cannot be asked


def test_the_list_and_the_root_answer_with_nothing_open(cold):
    base, _live, root = cold
    _, body = _get(base + "/api/programs")
    d = json.loads(body)
    assert d["serving"] == ""
    assert d["root"] == str(root)
    assert [p["name"] for p in d["programs"]] == ["alpha", "beta"]
    # `files` costs an open and is `None` for a program that is not being read; `revisions`
    # is a directory listing and is there for every row.
    assert all(p["files"] is None for p in d["programs"])
    assert all(p["revisions"] == 1 for p in d["programs"])


def test_the_base_readout_says_there_is_none(cold):
    """The start page polls this while the first program is being built."""
    base, _live, _root = cold
    _, body = _get(base + "/api/base")
    d = json.loads(body)
    assert d["open"] is False
    assert d["base"] == ""


@pytest.mark.parametrize("route", ["/api/cover", "/api/graph", "/api/glossary",
                                   "/api/node", "/api/files", "/api/algorithms"])
def test_a_route_that_needs_a_base_refuses_and_says_why(cold, route):
    """**Over the socket**, because that is where the first spelling of this died.

    A 409 with a sentence is a thing that can be found. An empty payload would be
    indistinguishable from a version with nothing in it (rule 49), and a connection that
    closes with nothing on it is worse than either.
    """
    base, _live, _root = cold
    status, body = _get(base + route)
    assert status == 409, f"{route} answered {status}"
    assert "nothing is open" in body
    assert route in body


def test_the_refusal_survives_the_em_dash(cold):
    """The exact defect, pinned: the sentence must reach the reader.

    `send_error`'s message argument is the status line and is latin-1; its `explain`
    argument is the body and is UTF-8. This project writes em dashes everywhere, so the
    sentence belongs in the second one.
    """
    base, _live, _root = cold
    _, body = _get(base + "/api/cover")
    assert "—" in body, "the sentence lost its punctuation, or is not being sent"


def test_a_post_that_needs_a_base_is_refused_too(cold):
    base, _live, _root = cold
    status, _ = _post(base + "/api/base?revision=whatever")
    assert status == 409


@pytest.mark.parametrize("route", ["/api/programs", "/api/analysis", "/api/base"])
def test_the_exemptions_are_the_short_list(cold, route):
    base, _live, _root = cold
    status, _ = _get(base + route)
    assert status == 200


def test_the_two_exemption_lists_are_kept_apart():
    """`/api/base` is a readout from cold and a base *switch* when posted to.

    One list covering both tables would exempt the switch by accident, which is
    `POST_ROUTES`' own argument for being a separate table (design rule 16).
    """
    assert "/api/base" in _Handler.GET_WITHOUT_BASE
    assert "/api/base" not in _Handler.POST_WITHOUT_BASE
    # Every exemption must name a route that exists, or it is a line nobody will notice
    # has stopped meaning anything (rule 35).
    for r in _Handler.GET_WITHOUT_BASE:
        assert r in _Handler.ROUTES, r
    for r in _Handler.POST_WITHOUT_BASE:
        assert r in _Handler.POST_ROUTES, r


# --------------------------------------------------------------------------- #
# Opening the first one


def test_opening_a_program_from_cold_makes_the_shell_the_page(cold):
    """The first open and a switch are one route, and this is the half that had none."""
    base, live, _root = cold
    status, body = _post(base + "/api/program?name=alpha")
    assert status == 200
    assert json.loads(body)["started"] is True

    for _ in range(200):                         # the build runs on its own thread
        if live.opened:
            break
        _get(base + "/api/base")
    assert live.opened, "the base was never built"

    _, page = _get(base + "/")
    assert '<script src="/static/shell.js"></script>' in page
    assert '<script src="/static/start.js"></script>' not in page
    assert _get(base + "/api/cover")[0] == 200
    d = json.loads(_get(base + "/api/programs")[1])
    assert d["serving"] == "alpha"
    assert [p["files"] for p in d["programs"] if p["name"] == "alpha"] != [None]


def test_a_program_that_is_not_here_is_refused_by_name(cold):
    base, _live, root = cold
    d = json.loads(_post(base + "/api/program?name=nowhere")[1])
    assert d["started"] is False
    # Named `under <root>` rather than "beside this one": from cold there is no this one.
    assert str(root) in d["reason"]


def test_a_name_that_could_address_another_directory_is_refused(cold):
    """The list is the authority on what may be opened (rule 30), and it always was.

    Worth pinning here because the cold path builds that list differently -- the served
    program is no longer added to it -- and a lookup table is only as safe as its keys.
    """
    base, _live, _root = cold
    for name in ("../..", "/etc", "alpha/../beta"):
        assert json.loads(_post(base + f"/api/program?name={name}")[1])["started"] is False
