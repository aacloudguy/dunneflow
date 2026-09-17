"""Python's resolver.

Beside `extractors/python/` and `canonical/python.py`, and that is now the third place
adding a language touches: something to **read** a file, something to say when two
expressions are the **same**, and something to say which definition a call **meant**.

Nothing here is imported by anything but `resolve/calls.py`'s `RESOLVERS` table.
"""
