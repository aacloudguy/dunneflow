"""What a run cost the machine, beside what it cost the clock.

**A wall-clock figure cannot say whether a run worked or waited.** `Engine/Source/Runtime` has
taken 8,353, 10,363, 18,206, 18,584 and 30,660 seconds to read, and nothing any of those runs
recorded could tell a slower reader from a busier machine (rule 38: an instrument that cannot
see cannot report). So `--timings` now reads three more things, each where the platform can
answer and said to be unmeasured where it cannot, never estimated (rule 49):

- **CPU seconds**, this process and its children, user and system together. Divided by the
  wall clock it is how many CPUs were busy on average: a phase that took longer at the same CPU
  time waited for something.
- **Peak memory**: this process's, and the largest of its children's.
- **The machine**, at the start and the end: load average and swap in use, the two things that
  say a run was sharing it.

**A child's CPU is counted when it exits.** The operating system adds a child to
`RUSAGE_CHILDREN` once it has been waited for, so a reader's whole cost lands in the phase it
ends in, which for every out-of-process reader is the reading of the tree.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Cpu:
    """CPU seconds so far: this process, and the children it has waited for."""

    own: float
    # `None` where the platform does not say (Windows), which is not zero.
    children: float | None

    def total(self) -> float | None:
        return None if self.children is None else self.own + self.children


def cpu() -> Cpu:
    if sys.platform == "win32":
        # `process_time` is this process's user and system time; Windows has no counterpart
        # to `RUSAGE_CHILDREN` in the standard library.
        import time
        return Cpu(time.process_time(), None)
    import resource
    me = resource.getrusage(resource.RUSAGE_SELF)
    kids = resource.getrusage(resource.RUSAGE_CHILDREN)
    return Cpu(me.ru_utime + me.ru_stime, kids.ru_utime + kids.ru_stime)


def peaks() -> tuple[int | None, int | None]:
    """Peak resident memory in bytes: this process's, and its largest child's."""
    if sys.platform == "win32":
        return None, None
    import resource
    # `ru_maxrss` is bytes on macOS and kilobytes on Linux.
    scale = 1 if sys.platform == "darwin" else 1024
    me = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
    kids = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * scale
    return me, kids or None


def _swap() -> tuple[int, int] | None:
    """Swap (used, total) in bytes, or `None` where this cannot be read."""
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True,
                                 text=True, timeout=5, check=True).stdout
            # "total = 3072.00M  used = 1840.69M  free = 1231.31M  (encrypted)"
            words = out.replace("=", " ").split()
            vals = {words[i]: words[i + 1] for i in range(len(words) - 1)
                    if words[i] in ("total", "used")}
            unit = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}
            def size(v: str) -> int:
                return round(float(v[:-1]) * unit[v[-1]])
            return size(vals["used"]), size(vals["total"])
        if sys.platform == "linux":
            info: dict[str, int] = {}
            with open("/proc/meminfo", encoding="ascii") as f:
                for line in f:
                    k, _, v = line.partition(":")
                    if k in ("SwapTotal", "SwapFree"):
                        info[k] = int(v.split()[0]) * 1024
            return info["SwapTotal"] - info["SwapFree"], info["SwapTotal"]
    except (OSError, subprocess.SubprocessError, KeyError, ValueError, IndexError):
        return None
    return None


def machine() -> dict[str, object]:
    """Load average and swap now. A key is absent where the platform cannot say."""
    out: dict[str, object] = {}
    if hasattr(os, "getloadavg"):
        with contextlib.suppress(OSError):
            out["load"] = [round(x, 2) for x in os.getloadavg()]
    swap = _swap()
    if swap is not None:
        out["swap_used"], out["swap_total"] = swap
    return out


def describe_machine(m: dict[str, object]) -> str:
    parts = []
    load = m.get("load")
    if isinstance(load, list):
        parts.append("load " + " ".join(f"{x:.2f}" for x in load))
    used, total = m.get("swap_used"), m.get("swap_total")
    if isinstance(used, int) and isinstance(total, int):
        parts.append(f"swap {mb(used)} of {mb(total)} in use")
    return ", ".join(parts) or "not measured on this platform"


def mb(n: int) -> str:
    return f"{n / (1 << 20):,.0f} MB"
