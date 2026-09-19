"""Read a tree too large for one analysis, one part at a time.

**Driven by `walk.parts_under`, which is the guard's own answer** -- so what this reads is
exactly what `dunneflow analyze <tree>` refuses with, rather than a second opinion about the
tree that can drift from it (rule 51). Point it at a tree and it runs the commands the
refusal would have printed.

    uv run python tools/ingest_parts.py <tree> --output output

Every part goes into one maps root named for the tree, so `dunneflow serve` lists them side
by side. A part that fails is reported and the rest still run: eighty-odd analyses where one
bad file stops the other eighty-five would be a worse tool than one that says which part it
could not read.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dunneflow.walk import parts_under  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ingest_parts")
    p.add_argument("tree", type=Path)
    p.add_argument("--output", type=Path, default=Path("output"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    root = args.tree.resolve()
    print(f"cutting {root} …", flush=True)
    t0 = time.perf_counter()
    cut = parts_under(root)
    print(f"  {cut.total:,} files in {len(cut.parts)} parts "
          f"({time.perf_counter() - t0:.0f}s to decide)", flush=True)
    if cut.uncovered:
        n = sum(k for _, k in cut.uncovered)
        print(f"  {n:,} files reach no part: "
              + ", ".join(f"{d.relative_to(root)} ({k})" for d, k in cut.uncovered), flush=True)
    if cut.whole:
        print("  already one part — analyse it directly")
        return 0

    dest = args.output / root.name
    done = failed = 0
    started = time.perf_counter()
    for i, (d, n) in enumerate(cut.parts, 1):
        name = ".".join(d.relative_to(root).parts) or root.name
        cmd = ["uv", "run", "dunneflow", "analyze", str(d),
               "--name", name, "--output", str(dest)]
        head = f"[{i}/{len(cut.parts)}] {name} ({n:,} files)"
        if args.dry_run:
            print(head + " — " + " ".join(cmd), flush=True)
            continue
        t = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True)
        took = time.perf_counter() - t
        if r.returncode == 0:
            done += 1
            # The summary line the CLI prints last, which carries the figures.
            tail = [ln for ln in r.stderr.splitlines() if ln.startswith(f"{name}:")]
            said = tail[-1] if tail else ""
            drained = [ln.strip() for ln in r.stderr.splitlines()
                       if "write-ahead log was drained" in ln]
            print(f"{head} — {took:.0f}s   {said}", flush=True)
            for ln in drained:
                print(f"      {ln}", flush=True)
        else:
            failed += 1
            last = [ln for ln in r.stderr.splitlines() if ln.strip()]
            print(f"{head} — FAILED after {took:.0f}s: "
                  f"{last[-1] if last else f'exit {r.returncode}'}", flush=True)

    print(f"\n{done} parts read, {failed} failed, "
          f"{(time.perf_counter() - started) / 60:.0f} minutes", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
