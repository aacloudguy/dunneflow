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

from ..store import Store
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


class _Handler(BaseHTTPRequestHandler):
    """Static files and one JSON endpoint. No routing framework, no state."""

    server_version = "DunneFlow"

    def __init__(self, *args: Any, payload: dict[str, Any], **kw: Any) -> None:
        self._payload = payload
        super().__init__(*args, **kw)

    def log_message(self, fmt: str, *args: Any) -> None:
        return                                    # a reading tool is not a web log

    def do_GET(self) -> None:                     # noqa: N802  (stdlib's spelling)
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._file(STATIC / "index.html")
        elif path == "/api/graph":
            self._json(self._payload)
        elif path.startswith("/static/"):
            self._file(STATIC / path[len("/static/"):])
        elif path == "/favicon.ico":
            # Browsers always ask. Answering "nothing here" is quieter than a 404 in
            # everyone's console.
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif path.startswith("/vendor/"):
            self._file(VENDOR / path[len("/vendor/"):])
        else:
            self.send_error(404)

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

    store = Store(graph_db, writable=False)
    try:
        model = build(store)
        payload = columnar(model)
    finally:
        store.close()

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
    handler = partial(_Handler, payload=payload)
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
