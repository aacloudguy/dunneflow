"""The network view.

A program that spans machines cannot be read as one call graph. The witness service
runs on a different host from the code that calls it, and the difference between
"this function calls that function" and "this process asks another machine and waits"
is the most important distinction in the whole map — it is where trust, latency, and
failure all change character.

So network hops are never drawn like local calls. Each executable is a separate zone,
local flow stays inside its zone, and anything crossing a zone edge is drawn as a
thick dashed hop that the eye cannot confuse with a function call.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from ..resolve.flows import ways_in
from ..store import Store

INBOUND_KINDS = ("HTTP_ROUTE", "QUEUE_CONSUMER")
_URL = re.compile(r"https?://[^\s'\"<>)]+", re.IGNORECASE)


def _esc(text: str | None) -> str:
    """Table-safe, and complete. Never truncates -- see render/markdown.py."""
    if not text:
        return ""
    return " ".join(str(text).split()).replace("|", "\\|")


# There was a `path` here, and in eight other renderers -- nine copies of the
# same four lines, each stripping the analysed root off a stored absolute path so a reader
# would not be shown one machine's directory layout. Paths are stored relative now, so
# every one of them had nothing left to strip.
#
# They were removed rather than left as harmless no-ops, because they were not harmless:
# `Path("mensores/cli.py").resolve()` resolves against the *working directory*, so run from
# anywhere inside the analysed tree the strip would succeed and silently prepend the
# intervening directories to every path on the page.


# When no URL is written down, the library being called still names the destination.
_LIBRARY_DESTINATION = {
    "anthropic": "Anthropic API",
    "openai": "OpenAI API",
    "boto3": "AWS",
    "botocore": "AWS",
    "google": "Google Cloud",
    "azure": "Azure",
    "socket": "raw socket",
    "requests": "HTTP (host built at runtime)",
    "httpx": "HTTP (host built at runtime)",
    "urllib": "HTTP (host built at runtime)",
    "aiohttp": "HTTP (host built at runtime)",
    "http": "HTTP (host built at runtime)",
}


def _host_of(target: str, evidence: str) -> str:
    """The destination of a call: the literal host when written down, else the library.

    A great many outbound calls never name their host in the source -- it arrives from
    configuration. Reporting those as "unknown" is true but useless; naming the library
    at least says *what kind of* remote thing is being talked to.
    """
    m = _URL.search(target or "") or _URL.search(evidence or "")
    if m:
        try:
            netloc = urlparse(m.group(0)).netloc
            if netloc:
                return netloc
        except ValueError:
            pass
    root = (evidence or "").split(".")[0]
    if root in _LIBRARY_DESTINATION:
        return _LIBRARY_DESTINATION[root]
    for key, label in _LIBRARY_DESTINATION.items():
        if f".{key}." in f".{evidence}." or (evidence or "").startswith(f"{key}."):
            return label
    if "messages.create" in (evidence or "") or "_client" in (evidence or ""):
        return "Anthropic API"
    if target and ("{" in target or "?" in target):
        return "(built at runtime)"
    return "(host not stated in source)"


def _san(text: str, limit: int = 30) -> str:
    out = (text or "").replace('"', "'").replace("\n", " ")
    for ch in "[]{}()<>|#;":
        out = out.replace(ch, "")
    out = out.strip()
    return out if len(out) <= limit else out[: limit - 1] + "…"


def render_network(store: Store, out: Path, program: str, stamp: str) -> Path | None:
    outbound = store.query(
        "SELECT b.target, b.evidence, b.direction, b.line, r.qualname, r.module, r.file,"
        "       b.routine_id"
        "  FROM boundaries b JOIN routines r ON b.routine_id = r.id"
        " WHERE b.kind IN ('NETWORK','CLOUD_SDK','LLM_API')"
        " ORDER BY r.qualname"
    )
    inbound = store.query(
        f"SELECT e.name, e.kind, e.module, e.routine_id, e.evidence, r.file, r.line_start"
        f"  FROM entrypoints e LEFT JOIN routines r ON e.routine_id = r.id"
        f" WHERE e.kind IN ({','.join('?' * len(INBOUND_KINDS))})"
        f" ORDER BY e.name",
        INBOUND_KINDS,
    )
    net_any = store.query("SELECT COUNT(*) n FROM net_calls")[0]["n"]
    if not outbound and not inbound and not net_any:
        return None

    # Which executable does each routine belong to? A routine can serve more than one.
    # Only things you can actually start are zones. An inbound handler runs *inside*
    # an executable; treating it as its own zone would answer "which process is this
    # in?" with the handler's own name.
    executables = [d for d in ways_in(store) if d["kind"] in ("CLI", "MAIN")]
    zones: dict[str, set[str]] = {}
    for d in executables:
        zones[d["name"]] = store.reachable_from_many(d["roots"])

    # Which module each routine lives in, and which modules each executable reaches.
    module_of = {
        r["id"]: r["module"] for r in store.query("SELECT id, module FROM routines")
    }
    zone_modules = {
        name: {module_of.get(i, "") for i in ids} for name, ids in zones.items()
    }

    def zone_of(routine_id: str) -> str:
        owners = [name for name, ids in zones.items() if routine_id in ids]
        if owners:
            # The narrowest executable containing it is the most specific answer.
            return min(owners, key=lambda n: len(zones[n]))
        # A handler is never called by the program that hosts it -- the server calls
        # it at runtime -- so reachability cannot place it. Its module can: if an
        # executable reaches anything else in the same module, that is where it runs.
        mod = module_of.get(routine_id)
        if mod:
            by_module = [n for n, mods in zone_modules.items() if mod in mods]
            if by_module:
                return min(by_module, key=lambda n: len(zones[n]))
        return "(not started by this program)"

    lines = [f"# {program} — Network and process boundaries\n\n*Generated {stamp} by DunneFlow.*\n"]
    lines.append(
        "Where this program stops being one program. Everything above a network hop "
        "runs in one process; everything below it runs somewhere else and can fail "
        "independently.\n"
    )

    # -- inbound ------------------------------------------------------------ #
    if inbound:
        lines.append("## What this program serves\n")
        lines.append(
            "Inbound endpoints — other processes, possibly on other machines, call "
            "these.\n"
        )
        lines.append("| Endpoint | Kind | Runs in | Module | Where |\n|---|---|---|---|---|")
        for i in inbound:
            z = zone_of(i["routine_id"]) if i["routine_id"] else "—"
            where = f"{i['file'] or ''}:{i['line_start'] or 0}"
            lines.append(
                f"| `{_esc(i['name'])}` | {i['kind']} | `{_esc(z)}` "
                f"| `{_esc(i['module'])}` | {_esc(where)} |"
            )
        lines.append("")

    # -- outbound ----------------------------------------------------------- #
    if outbound:
        by_host: dict[str, list] = defaultdict(list)
        for o in outbound:
            by_host[_host_of(o["target"], o["evidence"])].append(o)

        lines.append("## What this program calls out to\n")
        lines.append("| Destination | Calls | From executable(s) |\n|---|---:|---|")
        for host in sorted(by_host, key=lambda h: -len(by_host[h])):
            zs = sorted({zone_of(o["routine_id"]) for o in by_host[host]})
            lines.append(
                f"| `{_esc(host)}` | {len(by_host[host])} "
                f"| {_esc(', '.join(zs))} |"
            )
        lines.append("")

        lines.append("<details><summary>Every outbound call</summary>\n")
        lines.append("| Routine | Destination | Via | Where |\n|---|---|---|---|")
        for o in outbound:
            where = f"{o['file']}:{o['line']}"
            lines.append(
                f"| `{_esc(o['qualname'])}` "
                f"| `{_esc(o['target'] or _host_of(o['target'], o['evidence']))}` "
                f"| `{_esc(o['evidence'])}` | {_esc(where)} |"
            )
        lines.append("\n</details>\n")

    # -- remote call signatures --------------------------------------------- #
    net = store.query(
        "SELECT n.*, r.qualname, r.file AS rfile FROM net_calls n"
        " JOIN routines r ON n.routine_id = r.id"
        " ORDER BY n.protocol, r.qualname, n.line"
    )
    if net:
        lines.append("## Remote call signatures\n")
        lines.append(
            "A remote call has a longer signature than a local one. These are the "
            "fields that decide how it behaves when the far end is slow, absent, or "
            "lying.\n"
        )
        lines.append("| Protocol | Calls | Blocking | Awaited | Has timeout | Has retry |"
                     "\n|---|---:|---:|---:|---:|---:|")
        protos: dict[str, list] = defaultdict(list)
        for n in net:
            protos[n["protocol"]].append(n)
        for proto in sorted(protos, key=lambda p: -len(protos[p])):
            items = protos[proto]
            blocking_count = sum(1 for i in items if not (i["is_async"] and i["awaited"]))
            lines.append(
                f"| {proto} | {len(items)} | {blocking_count} "
                f"| {sum(1 for i in items if i['awaited'])} "
                f"| {sum(1 for i in items if i['timeout'])} "
                f"| {sum(1 for i in items if i['retries'])} |"
            )
        lines.append("")

        no_timeout = [n for n in net if not n["timeout"]]
        no_retry = [n for n in net if not n["retries"]]
        if no_timeout or no_retry:
            lines.append("### Operational exposure\n")
            if no_timeout:
                lines.append(
                    f"- **{len(no_timeout)} of {len(net)} remote calls set no timeout.** "
                    f"Each is a place where an unresponsive peer stops the caller "
                    f"indefinitely rather than failing."
                )
            if no_retry:
                lines.append(
                    f"- **{len(no_retry)} of {len(net)} set no retry policy**, so a "
                    f"single transient failure propagates."
                )
            lines.append("")

        lines.append("### Every remote call\n")
        lines.append(
            "| Caller | Protocol | Verb | Destination | Port | Blocking | Timeout "
            "| Retries | Payload | Where |\n"
            "|---|---|---|---|---|---|---|---|---|---|"
        )
        for n in net:
            where = f"{n['rfile']}:{n['line']}"
            if n["is_async"] and n["awaited"]:
                blocking_label = "no (awaited)"
            elif n["is_async"]:
                blocking_label = "**yes — async client not awaited**"
            else:
                blocking_label = "yes"
            dest = n["destination"] or _host_of(n["destination"], n["expr"])
            lines.append(
                f"| `{_esc(n['qualname'])}` | {n['protocol']} "
                f"| {n['verb'] or '—'} | `{_esc(dest)}` | {_esc(n['port']) or '—'} "
                f"| {blocking_label} | {_esc(n['timeout']) or '**none**'} "
                f"| {_esc(n['retries']) or '—'} | {_esc(n['payload']) or '—'} "
                f"| {_esc(where)} |"
            )
        lines.append("")

    # -- messaging ---------------------------------------------------------- #
    MESSAGING = {"Kafka", "AMQP", "MQTT", "NATS", "ZeroMQ", "Redis", "Celery",
                 "STOMP", "ServiceBus", "PubSub"}
    msg = [n for n in net if n["protocol"] in MESSAGING]
    queue_hits = store.query(
        "SELECT b.direction, b.target, b.evidence, b.line, r.qualname, r.file AS rfile"
        "  FROM boundaries b JOIN routines r ON b.routine_id = r.id"
        " WHERE b.kind = 'QUEUE' ORDER BY b.direction, r.qualname"
    )
    if msg or queue_hits:
        lines.append("## Messaging\n")
        lines.append(
            "Messaging is listed apart from request/response because it fails "
            "differently. A send that returns successfully means a broker accepted "
            "the message, not that anything received it — so who produces, who "
            "consumes, and whether delivery is acknowledged are separate facts.\n"
        )
        if msg:
            lines.append(
                "| Routine | Protocol | Operation | Topic/queue | Ack/durability "
                "| Blocking | Where |\n|---|---|---|---|---|---|---|"
            )
            for n in msg:
                where = f"{n['rfile']}:{n['line']}"
                msg_blocking = "no (awaited)" if (n["is_async"] and n["awaited"]) else "yes"
                lines.append(
                    f"| `{_esc(n['qualname'])}` | {n['protocol']} "
                    f"| {n['verb'] or '—'} | `{_esc(n['topic'] or n['destination']) or '—'}` "
                    f"| {_esc(n['ack']) or '**not set**'} | {msg_blocking} "
                    f"| {_esc(where)} |"
                )
            lines.append("")
        if queue_hits:
            produce = [q for q in queue_hits if q["direction"] == "OUT"]
            consume = [q for q in queue_hits if q["direction"] == "IN"]
            lines.append(
                f"Producers: **{len(produce)}** · consumers: **{len(consume)}** · "
                f"other queue operations: **{len(queue_hits) - len(produce) - len(consume)}**\n"
            )
            lines.append("<details><summary>Every queue operation</summary>\n")
            lines.append("| Direction | Routine | Target | Via | Where |\n|---|---|---|---|---|")
            for q in queue_hits:
                where = f"{q['rfile']}:{q['line']}"
                arrow = {"OUT": "produces", "IN": "consumes"}.get(q["direction"], q["direction"])
                lines.append(
                    f"| {arrow} | `{_esc(q['qualname'])}` | `{_esc(q['target'])}` "
                    f"| `{_esc(q['evidence'])}` | {_esc(where)} |"
                )
            lines.append("\n</details>\n")
    elif net:
        lines.append("## Messaging\n")
        lines.append(
            "No message broker, queue, or pub/sub client was found. All remote "
            "communication in this program is request/response.\n"
        )

    # -- the picture -------------------------------------------------------- #
    lines.append("## Process map\n")
    lines.append(
        "Each box is a separate process. **Solid arrows are calls inside one process. "
        "Thick dashed arrows are network hops** — a different machine, a different "
        "failure mode, a different trust boundary.\n"
    )
    lines.append("```mermaid")
    lines.append(_process_map(store, zones, inbound, outbound, zone_of))
    lines.append("```\n")

    path = out / "08-network.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _process_map(store: Store, zones: dict[str, set[str]], inbound: list,
                 outbound: list, zone_of: Callable[[str], str]) -> str:
    lines = ["flowchart LR"]
    n = [0]

    # Group each executable's network-relevant nodes inside its own subgraph, so the
    # zone edge is drawn rather than implied.
    inbound_by_zone: dict[str, list] = defaultdict(list)
    for i in inbound:
        if i["routine_id"]:
            inbound_by_zone[zone_of(i["routine_id"])].append(i)

    outbound_by_zone: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for o in outbound:
        outbound_by_zone[zone_of(o["routine_id"])][_host_of(o["target"], o["evidence"])] += 1

    node_ids: dict[tuple[str, str], str] = {}
    active = sorted(set(inbound_by_zone) | set(outbound_by_zone))

    for zname in active:
        n[0] += 1
        sub = f"Z{n[0]}"
        lines.append(f'    subgraph {sub}["process: {_san(zname, 28)}"]')
        lines.append("        direction TB")
        for i in inbound_by_zone.get(zname, []):
            n[0] += 1
            nid = f"N{n[0]}"
            node_ids[(zname, "in:" + i["name"])] = nid
            lines.append(f'        {nid}["serves {_san(i["name"], 26)}"]:::inbound')
        for host in outbound_by_zone.get(zname, {}):
            n[0] += 1
            nid = f"N{n[0]}"
            node_ids[(zname, "out:" + host)] = nid
            lines.append(f'        {nid}["calls out"]:::caller')
        lines.append("    end")

    # Remote destinations sit outside every process box, which is the point.
    remote_ids: dict[str, str] = {}
    for hosts in outbound_by_zone.values():
        for host in hosts:
            if host not in remote_ids:
                n[0] += 1
                remote_ids[host] = f"H{n[0]}"
                lines.append(f'    {remote_ids[host]}[/"{_san(host, 30)}"/]:::remote')

    for zname, hosts in outbound_by_zone.items():
        for host, count in hosts.items():
            src = node_ids.get((zname, "out:" + host))
            if src:
                lines.append(f"    {src} ==>|network ×{count}| {remote_ids[host]}")

    lines.append("""    classDef inbound fill:#d1e7dd,stroke:#0f5132,color:#0f5132,font-weight:bold
    classDef caller  fill:#f5f5f5,stroke:#999,color:#222
    classDef remote  fill:#f8d7da,stroke:#842029,color:#842029,stroke-width:3px,\
stroke-dasharray: 6 3""")
    return "\n".join(lines)
