"""Flow diagrams.

One diagram per way in, drawn so the eye reads it the way the program runs it:
entry at the top, routines beneath, and the outside world at the edges. Boundary
nodes are shaped by kind so that "this writes to a database" is visible without
reading a label.

Diagrams are bounded on purpose. A picture of 4,500 routines is not a picture.
"""

from __future__ import annotations

from ..resolve.flows import Flow
from ..schema import BoundaryKind, Direction

# Distinct shapes so kind is legible before the label is read.
_SHAPE = {
    BoundaryKind.ENV: ("([", "])"),
    BoundaryKind.FILE: ("[(", ")]"),
    BoundaryKind.DATABASE: ("[(", ")]"),
    BoundaryKind.NETWORK: ("{{", "}}"),
    BoundaryKind.PROCESS: ("[/", "/]"),
    BoundaryKind.QUEUE: ("{{", "}}"),
    BoundaryKind.STDIO: (">", "]"),
    BoundaryKind.CLOUD_SDK: ("{{", "}}"),
    BoundaryKind.LLM_API: ("{{", "}}"),
    BoundaryKind.CRYPTO: ("[[", "]]"),
}

_CLASS = {
    BoundaryKind.ENV: "env",
    BoundaryKind.FILE: "file",
    BoundaryKind.DATABASE: "db",
    BoundaryKind.NETWORK: "net",
    BoundaryKind.PROCESS: "proc",
    BoundaryKind.QUEUE: "queue",
    BoundaryKind.STDIO: "io",
    BoundaryKind.CLOUD_SDK: "cloud",
    BoundaryKind.LLM_API: "llm",
    BoundaryKind.CRYPTO: "crypto",
}

STYLES = """    classDef entry fill:#1f4e79,stroke:#0d2b45,color:#fff,font-weight:bold
    classDef rout  fill:#f5f5f5,stroke:#999,color:#222
    classDef env   fill:#fff3cd,stroke:#b8860b,color:#5c4400
    classDef file  fill:#d1e7dd,stroke:#0f5132,color:#0f5132
    classDef db    fill:#cfe2ff,stroke:#084298,color:#084298
    classDef net   fill:#f8d7da,stroke:#842029,color:#842029
    classDef proc  fill:#e2d9f3,stroke:#432874,color:#432874
    classDef queue fill:#ffe5d0,stroke:#8a4b08,color:#8a4b08
    classDef io    fill:#eeeeee,stroke:#666,color:#333
    classDef cloud fill:#d3f2f2,stroke:#0b5e5e,color:#0b5e5e
    classDef llm   fill:#ede7f6,stroke:#4527a0,color:#4527a0
    classDef crypto fill:#fce4ec,stroke:#880e4f,color:#880e4f"""


def _san(text: str, limit: int = 34) -> str:
    """Mermaid labels cannot carry the characters source code is full of."""
    out = (text or "").replace('"', "'").replace("\n", " ")
    for ch in "[]{}()<>|#;":
        out = out.replace(ch, "")
    out = out.strip()
    return out if len(out) <= limit else out[: limit - 1] + "…"


def flow_diagram(flow: Flow, max_boundaries_per_node: int = 3) -> str:
    """Render one flow as a Mermaid flowchart."""
    if not flow.nodes:
        return ""

    lines = ["flowchart TD"]
    ids = {n.routine_id: f"R{i}" for i, n in enumerate(flow.nodes)}

    entry_id = "ENTRY"
    lines.append(f'    {entry_id}["{_san(flow.entry_name, 40)}"]:::entry')
    if flow.nodes:
        lines.append(f"    {entry_id} --> {ids[flow.nodes[0].routine_id]}")

    for n in flow.nodes:
        lines.append(f'    {ids[n.routine_id]}["{_san(n.name)}"]:::rout')

    seen_edges: set[tuple[str, str]] = set()
    for caller, callee in flow.edges:
        if caller in ids and callee in ids:
            key = (ids[caller], ids[callee])
            if key not in seen_edges and caller != callee:
                seen_edges.add(key)
                lines.append(f"    {ids[caller]} --> {ids[callee]}")

    # Boundaries are deduplicated per routine: the same table written four times in
    # one routine is one fact about that routine, not four.
    bcount = 0
    for n in flow.nodes:
        shown: set[tuple[str, str]] = set()
        for b in n.boundaries:
            key = (b.kind.value, b.target)
            if key in shown:
                continue
            shown.add(key)
            if len(shown) > max_boundaries_per_node:
                break
            bid = f"B{bcount}"
            bcount += 1
            open_s, close_s = _SHAPE.get(b.kind, ("[", "]"))
            label = f"{b.kind.value}: {_san(b.target or b.evidence, 26)}"
            lines.append(f'    {bid}{open_s}"{label}"{close_s}:::{_CLASS.get(b.kind, "io")}')
            if b.direction is Direction.IN:
                lines.append(f"    {bid} -.->|reads| {ids[n.routine_id]}")
            else:
                lines.append(f"    {ids[n.routine_id]} -.->|writes| {bid}")

    lines.append(STYLES)
    return "\n".join(lines)


def command_tree_diagram(tree: dict, max_commands: int = 6) -> str:
    """Render a CLI application tree: the executable and what it can be told to do.

    The drawing shows a few commands per group to stay legible; the complete tree is
    always written out as a list beneath it, so nothing is lost from the record.
    """
    if not tree:
        return ""
    lines = ["flowchart LR"]
    counter = [0]

    def walk(node: dict, parent: str | None) -> None:
        counter[0] += 1
        nid = f"A{counter[0]}"
        label = node.get("mounted_as") or node.get("title") or node["var"]
        lines.append(f'    {nid}["{_san(label, 24)}"]:::entry')
        if parent:
            lines.append(f"    {parent} --> {nid}")
        for cmd in node.get("commands", [])[:max_commands]:
            counter[0] += 1
            cid = f"A{counter[0]}"
            lines.append(f'    {cid}("{_san(cmd["name"], 24)}"):::rout')
            lines.append(f"    {nid} --> {cid}")
        extra = len(node.get("commands", [])) - max_commands
        if extra > 0:
            counter[0] += 1
            cid = f"A{counter[0]}"
            lines.append(f'    {cid}("+{extra} more"):::rout')
            lines.append(f"    {nid} --> {cid}")
        for child in node.get("children", []):
            walk(child, nid)

    walk(tree, None)
    lines.append(STYLES)
    return "\n".join(lines)
