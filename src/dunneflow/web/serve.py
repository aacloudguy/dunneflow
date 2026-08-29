"""The local server: `dunneflow serve output/<program>`.

`http.server` from the standard library, deliberately. The dashboard is a reading tool
someone opens on their own machine, not a service, and adding a web framework to a program
whose only dependency is a YAML parser would be paying a permanent cost for a one-machine
problem. The same command works on macOS and Windows because nothing here is platform-
specific.

Both stores are opened `writable=False`. Serving must never be able to damage the map it
is showing -- see rule 20, which exists because a read command once dropped every table it
came to read.

The graph is sent **columnar**: parallel arrays rather than one object per node. At
fifteen thousand drawn nodes the difference is several megabytes of repeated key names,
and deck.gl wants flat arrays anyway, so the object form would be built only to be taken
apart again.
"""

from __future__ import annotations

import json
import socket
import threading
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from ..docstore import DocStore
from ..sourcedb import SourceStore
from ..store import Store
from . import packages, queries
from .code import build_file, build_files
from .cover import anomalies as build_anomalies
from .cover import build as build_cover
from .detail import describe, hover_card
from .graph import GraphModel, build, pkg_params, root_package
from .layout import structural
from .threads import cohort, for_node
from .vocabulary import bind_glossary, measure_naming

STATIC = Path(__file__).parent / "static"
VENDOR = Path(__file__).parent / "vendor"

_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
}


def columnar(model: GraphModel) -> dict[str, Any]:
    """The whole stack as parallel arrays, with every drawn thing already positioned.

    Shadows are appended after real nodes and carry `real[i]`, the index of the node they
    proxy. That is what the transposition lines are drawn from, and it means the client
    never has to build a lookup to find where a shadow's real self lives.
    """
    pos = structural(model)
    index: dict[tuple[str, str], int] = {}

    ids: list[str] = []
    labels: list[str] = []
    kinds: list[str] = []
    disks: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    shadow_flags: list[int] = []
    real_of: list[int] = []
    detail: list[dict[str, Any]] = []

    def emit(node_id: str, label: str, kind: str, disk: str,
             is_shadow: bool, real: int, extra: dict[str, Any]) -> int:
        x, y, z = pos.get((node_id, disk), (0.0, 0.0, 0.0))
        i = len(ids)
        index[(node_id, disk)] = i
        ids.append(node_id)
        labels.append(label)
        kinds.append(kind)
        disks.append(disk)
        xs.append(x)
        ys.append(y)
        zs.append(z)
        shadow_flags.append(1 if is_shadow else 0)
        real_of.append(real)
        detail.append(extra)
        return i

    for n in model.nodes:
        emit(n.id, n.label, n.kind, n.disk, False, -1, n.detail)

    by_id = {n.id: n for n in model.nodes}
    for s in model.shadows:
        origin = by_id.get(s.node_id)
        if origin is None:
            continue
        home = index.get((s.node_id, origin.disk), -1)
        emit(s.node_id, origin.label, origin.kind, s.disk, True, home, {})

    # Edges reference drawn-node indices, so the client draws them without a lookup.
    e_from: list[int] = []
    e_to: list[int] = []
    e_kind: list[str] = []
    e_conf: list[str] = []
    e_disk: list[str] = []
    # How many times this connection appears in the source. It is carried through to the
    # client and drives edge width, which is the whole preparation for flow replay: when
    # a profile is imported later it becomes a *second source for a channel that already
    # exists*, rather than a reason to rewrite the renderer. Reserving storage for the
    # profiler now would be building the feature, not preparing for it.
    e_weight: list[int] = []
    dropped = 0
    for e in model.edges:
        a = index.get((e.src, e.disk))
        b = index.get((e.dst, e.disk))
        if a is None or b is None:
            dropped += 1
            continue
        e_from.append(a)
        e_to.append(b)
        e_kind.append(e.kind)
        e_conf.append(e.confidence)
        e_disk.append(e.disk)
        e_weight.append(e.weight)

    stats = dict(model.stats)
    stats["edges_unplaced"] = dropped

    return {
        "nodes": {"id": ids, "label": labels, "kind": kinds, "disk": disks,
                  "x": xs, "y": ys, "z": zs, "shadow": shadow_flags, "real": real_of,
                  "detail": detail},
        "edges": {"from": e_from, "to": e_to, "kind": e_kind,
                  "confidence": e_conf, "disk": e_disk, "weight": e_weight},
        "disks": model.disks,
        "stats": stats,
    }


class _Live:
    """The read-only stores the dashboard queries while it is open.

    One sqlite connection per store, guarded by a lock. `ThreadingHTTPServer` hands each
    request to its own thread and a sqlite connection refuses to be used from a thread it
    was not created on, so the choice is a connection per thread or a lock -- and for a
    reading tool with one reader, contention is not a thing that happens. The lock is the
    smaller of the two mistakes to have made.

    Both stores are opened `writable=False`. Rule 20: serving may refuse, it may never
    repair, and it must never be able to damage the map it came to show.
    """

    def __init__(self, graph_db: Path, source_db: Path) -> None:
        self.lock = threading.Lock()
        self.store = Store(graph_db, writable=False, shared=True)
        # A sidecar is optional by design -- `--no-source`, or a map handed over without
        # it. Absent is a state the inspector states plainly, never one it hides.
        self.source: SourceStore | None = None
        if source_db.exists():
            try:
                self.source = SourceStore(source_db, writable=False, shared=True)
            except (ValueError, OSError):
                self.source = None

        # Built once: nothing here changes while the map is open, and 175 reachability
        # queries on every navigation would make the first screen the slowest one.
        self.cover: dict[str, Any] = {}

        # The program's own root package, read from the data rather than assumed -- one
        # aggregate over `files`, and it is what scopes an outlier thread to the plate the
        # reader is standing on. Computed here because it cannot change while the map is
        # open and a per-request GROUP BY over every file would be a cost paid for nothing.
        self.root: str = root_package(self.store)

        # The tree that was analysed, so a path can be shown relative to it. Absolute paths
        # are right for a store that must find the bytes again and wrong for a screen: they
        # are one machine's directory layout, identical on all 626 rows, and they cost a
        # column's width to say nothing. Read from the store, never assumed.
        self.source_root: str = self.store.get_meta("source_root") or ""

        # The two lanes of the naming standard, filled at start rather than here -- see
        # `serve()`, which pays for them where it can say so.
        self.naming: dict[str, Any] = {}
        self.glossary: dict[str, Any] = {}

        # The file list, filled at start for the same reason the two lanes are: it cannot
        # change while the map is open, the navigator asks for it on load, and its cost is
        # all in the first touch of two databases on a slow volume -- 550 ms cold against
        # 23 ms warm. Paid at boot it sits inside a start that is already building a
        # payload, a cover and two vocabulary passes; paid lazily it is half a second of
        # the reader's first click.
        self.files: dict[str, Any] = {}

    def close(self) -> None:
        self.store.close()
        if self.source is not None:
            self.source.close()


class _Handler(BaseHTTPRequestHandler):
    """Static files and the JSON endpoints, routed from a table.

    A table rather than an `if`/`elif` chain, because design rule 16 was written after
    eight of eleven controls silently did the wrong thing: a chain ends in a fallback,
    and a fallback that looks deliberate is indistinguishable from a route that works.
    An unknown path here fails loudly and by name.
    """

    server_version = "DunneFlow"

    def __init__(self, *args: Any, payload: dict[str, Any], live: _Live,
                 **kw: Any) -> None:
        self._payload = payload
        self._live = live
        super().__init__(*args, **kw)

    def log_message(self, fmt: str, *args: Any) -> None:
        return                                    # a reading tool is not a web log

    # -- the table --------------------------------------------------------- #

    def _r_index(self, q: dict[str, list[str]]) -> None:
        self._file(STATIC / "index.html")

    def _r_graph(self, q: dict[str, list[str]]) -> None:
        self._json(self._payload)

    def _r_packages(self, q: dict[str, list[str]]) -> None:
        """The overview altitude: every package as a box, and what passes between them.

        Built per request rather than at startup. It is two aggregations over indexed
        columns, the payload is a few kilobytes, and most sessions never open it -- caching
        it would trade a measurable startup cost for a saving nobody can perceive.
        """
        with self._live.lock:
            self._json(packages.build(self._live.store))

    def _r_cover(self, q: dict[str, list[str]]) -> None:
        """The first screen. Built once at startup -- see `cover.py`."""
        self._json(self._live.cover)

    def _r_routines(self, q: dict[str, list[str]]) -> None:
        """Every routine, with the package the stack puts it on.

        The navigator used to read this off `/api/document?id=routines`, which was right
        while a routine row needed only a name and an id. Grouping the list by package needs
        the package, and there are two expressions for one in this dashboard -- so it comes
        from the one the *plates* use, and a package heading in the list is the plate in the
        picture rather than a second thing spelled the same way.

        On demand rather than with the cover: 4,734 rows is a real payload and a session
        that reads only the overview never asks for it.
        """
        with self._live.lock:
            rows = [dict(r) for r in self._live.store.query(
                queries.NAV_ROUTINES, pkg_params(self._live.root))]
        # Which packages actually have a plate. `graph.py` merges any package below
        # `MIN_DISK` into `pkg:<small>`, so 47 packages become 45 plates -- and a list row
        # offering `pkg:_version` would be selecting a plate that is not in the stack.
        # `queries.py` wrote down why that is the wrong fix before anything needed it:
        # inventing an id to make a row clickable is a link to nothing.
        plates = [d["id"] for d in self._payload["disks"] if d["id"].startswith("pkg:")]
        self._json({"routines": rows, "plates": plates})

    def _r_anomalies(self, q: dict[str, list[str]]) -> None:
        """The worklist. Separate from the cover, which carries only the counts.

        The findings are large -- every one carries its detail and its blind spot -- and
        most sessions read the counts without ever opening the list. Sending them with
        the cover would put that weight behind the first paint of every map.
        """
        with self._live.lock:
            self._json({"findings": build_anomalies(self._live.store)})

    def _r_documents(self, q: dict[str, list[str]]) -> None:
        """What document mode can show."""
        from .documents import index
        self._json({"documents": index()})

    def _r_document(self, q: dict[str, list[str]]) -> None:
        """One document, whole, every row carrying its graph node id."""
        from .documents import build as build_doc
        doc_id = (q.get("id") or [""])[0]
        with self._live.lock:
            self._json(build_doc(self._live.store, doc_id))

    def _r_node(self, q: dict[str, list[str]]) -> None:
        """Everything the inspector shows about one node."""
        node_id = (q.get("id") or [""])[0]
        if not node_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        with self._live.lock:
            body = describe(self._live.store, node_id, self._live.source)
        self._json(body)

    def _r_hover(self, q: dict[str, list[str]]) -> None:
        """The compact card behind the pop-up.

        Separate from `/api/node` rather than a slice of it, because the two answer
        different questions and cost different amounts. `/api/node` returns every caller,
        every callee, every comment and a span of source -- right for something the reader
        has chosen, wildly wrong for something the cursor is passing over on its way
        somewhere else.
        """
        node_id = (q.get("id") or [""])[0]
        if not node_id:
            self._json({"found": False, "reason": "no id asked for"})
            return
        with self._live.lock:
            body = hover_card(self._live.store, node_id)
        self._json(body)

    def _r_threads(self, q: dict[str, list[str]]) -> None:
        """The reasons a neighbour is worth a detour, for one node.

        The subject's module comes out of the store here rather than being asked for by
        the client: an outlier thread is scoped to the package the reader is standing on,
        and a module supplied from outside is a parameter that can disagree with the id
        beside it. There is one right answer and the store has it.
        """
        node_id = (q.get("id") or [""])[0]
        if not node_id:
            self._json({"found": False, "reason": "no id asked for", "threads": []})
            return
        with self._live.lock:
            row = self._live.store.query(
                "SELECT module, name FROM routines WHERE id = :id", {"id": node_id})
            module = str(row[0]["module"]) if row else ""
            name = str(row[0]["name"]) if row else ""
            body = for_node(self._live.store, node_id,
                            module=module, root=self._live.root, name=name,
                            naming=self._live.naming, glossary=self._live.glossary)
        self._json(body)

    def _r_thread(self, q: dict[str, list[str]]) -> None:
        """What one thread's subject resolves to.

        Only cohorts come here. A thread whose subject is already a node needs nothing
        resolved -- it is selected as itself -- and asking the server about it would be
        a round trip to be told what the client already knew.
        """
        kind = (q.get("kind") or [""])[0]
        key = (q.get("key") or [""])[0]
        if not kind or not key:
            self._json({"found": False, "nodes": [],
                        "reason": "a thread needs both a kind and a key"})
            return
        with self._live.lock:
            body = cohort(self._live.store, kind, key)
        self._json(body)

    def _r_naming(self, q: dict[str, list[str]]) -> None:
        """The Form lane: what this program does about names, counted."""
        self._json(self._live.naming)

    def _r_glossary(self, q: dict[str, list[str]]) -> None:
        """The Vocabulary lane: the program's words and who says what they mean."""
        self._json(self._live.glossary)

    def _r_table(self, q: dict[str, list[str]]) -> None:
        """The routines that touch one table.

        A table is not a node in the graph, so selecting one means selecting the code
        that reads and writes it. Answered on demand rather than shipped with the cover:
        Mensores has 1,042 operations across its tables and most sessions never click a
        table at all.
        """
        name = (q.get("name") or [""])[0]
        if not name:
            self._json({"found": False, "reason": "no table asked for", "nodes": []})
            return
        with self._live.lock:
            rows = self._live.store.query(queries.TABLE_ROUTINES, {"name": name})
        nodes = [r["node"] for r in rows]
        # `found: False` for a real table nothing touches would read as "no such table".
        # They are different answers and the client shows different things for each.
        self._json({"found": True, "table": name, "nodes": nodes})

    def _r_files(self, q: dict[str, list[str]]) -> None:
        """Every analysed file, complete. Rule 8: a reference list is never bounded."""
        with self._live.lock:
            self._json(self._live.files)

    def _r_file(self, q: dict[str, list[str]]) -> None:
        """One file, whole, with what the map knows about every line of it.

        Separate from `/api/source`, which serves a *span* and is what a citation and a
        definition open. This answers a different question -- what is this file, all of it,
        and what is on each line -- and sending the margin with every citation would put a
        file's worth of facts behind a click that wanted fifteen lines.
        """
        path = (q.get("path") or [""])[0]
        with self._live.lock:
            self._json(build_file(self._live.store, self._live.source, path,
                                  self._live.source_root))

    def _r_source(self, q: dict[str, list[str]]) -> None:
        """A span of one file, straight out of the sidecar.

        Separate from `/api/node` because the inspector opens a definition first and the
        surrounding file only if asked. Sending a whole file with every selection would
        put a megabyte behind every click for a view most clicks never open.
        """
        path = (q.get("path") or [""])[0]
        if not path:
            self._json({"available": False, "reason": "no path asked for"})
            return
        if self._live.source is None:
            self._json({"available": False, "file": path,
                        "reason": "no source sidecar beside this map"})
            return
        try:
            first = int((q.get("first") or ["1"])[0])
            last = int((q.get("last") or ["0"])[0])
        except ValueError:
            self._json({"available": False, "file": path,
                        "reason": "line numbers must be numbers"})
            return
        with self._live.lock:
            if last <= 0:
                whole = self._live.source.text(path)
                lines = list(enumerate((whole or "").split("\n"), 1)) if whole else []
            else:
                lines = self._live.source.lines(path, first, last)
        if not lines:
            self._json({"available": False, "file": path,
                        "reason": "the sidecar does not hold this file"})
            return
        self._json({"available": True, "file": path,
                    "first": lines[0][0], "last": lines[-1][0],
                    "lines": [{"n": n, "text": t} for n, t in lines]})

    def _r_favicon(self, q: dict[str, list[str]]) -> None:
        # Browsers always ask. Answering "nothing here" is quieter than a 404 in
        # everyone's console.
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    ROUTES: dict[str, str] = {
        "/": "_r_index",
        "/index.html": "_r_index",
        "/api/graph": "_r_graph",
        "/api/cover": "_r_cover",
        "/api/routines": "_r_routines",
        "/api/packages": "_r_packages",
        "/api/anomalies": "_r_anomalies",
        "/api/documents": "_r_documents",
        "/api/document": "_r_document",
        "/api/node": "_r_node",
        "/api/hover": "_r_hover",
        "/api/threads": "_r_threads",
        "/api/thread": "_r_thread",
        "/api/naming": "_r_naming",
        "/api/glossary": "_r_glossary",
        "/api/table": "_r_table",
        "/api/source": "_r_source",
        "/api/files": "_r_files",
        "/api/file": "_r_file",
        "/favicon.ico": "_r_favicon",
    }

    # Served directories, checked in order. Kept beside the route table rather than
    # inside the dispatch so both are readable as one list of what this server answers.
    TREES: tuple[tuple[str, Path], ...] = (("/static/", STATIC), ("/vendor/", VENDOR))

    def do_GET(self) -> None:                     # noqa: N802  (stdlib's spelling)
        raw, _, query = self.path.partition("?")
        handler = self.ROUTES.get(raw)
        if handler is not None:
            getattr(self, handler)(parse_qs(query))
            return
        for prefix, root in self.TREES:
            if raw.startswith(prefix):
                self._file(root / raw[len(prefix):])
                return
        self.send_error(404, f"no route for {raw}")

    def _json(self, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        # A served path must stay inside the directory it was resolved against, or a
        # request for ../../ walks the disk. Cheap to check, expensive to omit.
        try:
            resolved = path.resolve(strict=True)
            root = (STATIC if str(path).startswith(str(STATIC)) else VENDOR).resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            self.send_error(404)
            return
        body = resolved.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _TYPES.get(resolved.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _free_port(preferred: int) -> int:
    """Take the asked-for port, or any free one, rather than failing on a stale server."""
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve(out_dir: Path, *, port: int = 8787, open_browser: bool = True,
          emit: Any = print) -> None:
    """Build the payload once, then serve it until interrupted."""
    graph_db = out_dir / "graph.db"
    if not graph_db.exists():
        raise FileNotFoundError(f"no graph at {graph_db} -- run `dunneflow analyze` first")

    live = _Live(graph_db, out_dir / "source.db")
    model = build(live.store)
    payload = columnar(model)

    # The program's own words, both lanes, computed once.
    #
    # Not lazily, and the reason is where they are *used*: a vocabulary thread is part of
    # `/api/threads`, which is asked on every selection, so a lazy first call would stall
    # the reading loop on the first click of every session. Measured on Mensores at 0.4 s
    # for the naming pass and 2.1 s for the glossary -- the latter reads a 176 MB document
    # store -- against a start that is already building a payload and a cover.
    #
    # Documentation is optional by design (design rule 11): with no `docs.db` the glossary
    # keeps every code-derived term and loses only the tier that quotes a document. It is
    # never a prerequisite for a code-derived fact.
    docs_db = out_dir / "docs.db"
    docs = None
    if docs_db.exists():
        try:
            docs = DocStore(docs_db, writable=False)
        except (ValueError, OSError):
            docs = None
    live.files = build_files(live.store, live.source, live.source_root)
    live.naming = measure_naming(live.store)
    live.glossary = bind_glossary(live.store, docs)
    if docs is not None:
        docs.close()
    emit(f"{live.files['total']:,} files listed for the code browser")
    emit(f"{len(live.naming['conventions'])} naming conventions measured; "
         f"{live.glossary['coverage'][0]:,} of {live.glossary['coverage'][1]:,} "
         f"terms defined somewhere")

    # After the two lanes, not before, so the first screen can state their sizes. The
    # bodies stay where they are -- a quarter of a megabyte between them, fetched when
    # their pages are opened -- and only the three counts travel with the cover.
    defined, total = live.glossary["coverage"]
    live.cover = build_cover(live.store, live.source, out_dir.name, vocabulary={
        "conventions": len(live.naming["conventions"]),
        "terms": total,
        "defined": defined,
    })

    # Named so the browser can key stored settings per program. A disk order and a set of
    # colours worked out for one codebase mean nothing in another, and silently applying
    # one to the other would be the worst kind of persistence.
    payload["program"] = out_dir.name

    s = payload["stats"]
    # Shadows are never drawn -- they are placement devices, standing in on a plate so its
    # layout feels the pull of something living elsewhere. Reporting them as drawn would
    # overstate the picture by half.
    emit(f"{s['nodes']:,} nodes across {s['disks']} plates (largest {s['largest_disk']:,}), "
         f"{s['edges']:,} edges, {s['shadows']:,} shadows for placement only")

    port = _free_port(port)
    handler = partial(_Handler, payload=payload, live=live)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"
    emit(f"serving {url}  (ctrl-c to stop)")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        emit("stopped")
    finally:
        httpd.server_close()
        live.close()
