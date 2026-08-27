"""The dashboard: a local server, and the 2.5D graph it serves.

Nothing in here extracts or resolves anything. It reads the fact stores and shapes what
is already known for a reader, which is why it can open them `writable=False` and can
never damage the map it is showing.
"""
