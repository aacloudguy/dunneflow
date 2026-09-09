"""The packaged application's entry point.

Two lines of it are load-bearing and neither belongs in `cli.py`.

**`freeze_support()` is the first statement executed, before any import that matters.**
`walk.py` runs a `ProcessPoolExecutor` and macOS spawns rather than forks, so every worker
starts by re-executing this program. In a checkout that re-executes the interpreter and
`multiprocessing` sorts itself out; frozen it re-executes *the application* -- for `serve`,
up to sixteen more servers each opening a browser, and for `analyze` sixteen more analyses.
Nothing in the parent raises, so `walk.py`'s serial fallback never sees it: the parent is
fine and the children are the program. `cli.main` calls it too, and both is right rather
than redundant -- whichever is the real entry point of a given build, the first statement
executed has made the call, and it is a no-op every other time.

**No arguments means `serve`, and that is this file's decision rather than the CLI's.** A
command-line tool run with no arguments should say what it takes; an application that has
just been double-clicked has no way to say anything back, and printing usage into a window
nobody opened is the same as doing nothing. So the default lives with the double-click and
`dunneflow` from a checkout still prints its usage. `serve` with no directory then opens the
output root and, finding nothing, serves the start page -- which is the whole of what
double-clicking DunneFlow does on a machine that has never run it.
"""

import multiprocessing

multiprocessing.freeze_support()

import sys  # noqa: E402  -- after freeze_support, deliberately; see above

from dunneflow.cli import main  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("serve")
    raise SystemExit(main())
