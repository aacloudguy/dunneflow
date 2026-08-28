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

from ..sourcedb import SourceStore
from ..store import Store
from . import packages
from .cover import anomalies as build_anomalies
from .cover import build as build_cover
from .detail import describe
from .graph import GraphModel, build
from .layout import structural

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
        "/api/packages": "_r_packages",
        "/api/anomalies": "_r_anomalies",
        "/api/documents": "_r_documents",
        "/api/document": "_r_document",
        "/api/node": "_r_node",
        "/api/source": "_r_source",
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
    live.cover = build_cover(live.store, live.source, out_dir.name)

    # Named so the browser can key stored settings per program. A disk order and a set of
    # colours worked out for one codebase mean nothing in another, and silently applying
    # one to the other would be the worst kind of persistence.
    payload["program"] = out_dir.name

    s = payload["stats"]
    # Shadows are never drawn -- they are placement devices, standing in on a plate so its
    # layout feels the pull of something living elsewhere. Reporting them as drawn would
    # overstate the picture by half.
    emit(f"{s['nodes']:,} nodes across {s['disks']} disks (largest {s['largest_disk']:,}), "
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
