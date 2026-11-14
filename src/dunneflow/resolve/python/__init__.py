"""Python's resolver.

Beside `extractors/python/` and `canonical/python.py`, and that is now the third place
adding a language touches: something to **read** a file, something to say when two
expressions are the **same**, and something to say which definition a call **meant**.

`resolve/calls.py`'s `RESOLVERS` table imports the resolver, and `resolve/cli.py` borrows
`_absolute` for relative imports; nothing else in `src/` imports from here.
"""
